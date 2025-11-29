# 🔧 Admin Panel Testing Guide

Complete guide for testing the Coinflip admin dashboard before production deployment.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [2FA Authentication Testing](#2fa-authentication-testing)
4. [Fund Management Testing](#fund-management-testing)
5. [User Management Testing](#user-management-testing)
6. [Security Testing](#security-testing)
7. [Backup Testing](#backup-testing)
8. [Emergency Procedures Testing](#emergency-procedures-testing)
9. [Common Issues](#common-issues)
10. [Pre-Production Checklist](#pre-production-checklist)

---

## Prerequisites

### Required Software

```bash
# Python 3.8+
python --version

# Required packages
pip install python-dotenv cryptography tabulate solana
```

### Required Configuration

- `.env` file with all settings
- SMTP configured (for 2FA)
- Admin email set
- Database initialized

### Security Requirements

⚠️ **CRITICAL:** The admin dashboard has FULL ACCESS to all funds and private keys.

**Only run on:**
- Secure, admin-only machine
- Trusted network
- With 2FA enabled
- After reading FUND_RECOVERY_GUIDE.md

---

## Environment Setup

### 1. Configure Admin Email

Add to `.env`:

```bash
# === ADMIN CONFIGURATION ===
ADMIN_EMAIL=your_email@example.com

# === SMTP CONFIGURATION (for 2FA) ===
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com

# Get from: https://myaccount.google.com/apppasswords
# 1. Enable 2FA on Google account
# 2. Go to "App passwords"
# 3. Generate password for "Mail"
# 4. Copy 16-character password
SMTP_PASSWORD=abcd efgh ijkl mnop  # Remove spaces: abcdefghijklmnop
```

### 2. Verify Configuration

```bash
cd backend

# Test SMTP connection
python -c "
import smtplib
import os
from dotenv import load_dotenv

load_dotenv()
host = os.getenv('SMTP_HOST')
port = int(os.getenv('SMTP_PORT'))
user = os.getenv('SMTP_USERNAME')
password = os.getenv('SMTP_PASSWORD')

try:
    server = smtplib.SMTP(host, port)
    server.starttls()
    server.login(user, password)
    print('✅ SMTP configuration valid')
    server.quit()
except Exception as e:
    print(f'❌ SMTP error: {e}')
"
```

### 3. Verify Database

```bash
python -c "from database import Database; db = Database(); users = db.get_all_users(); wagers = db.get_open_wagers(); print(f'✅ Database OK: {len(users)} users, {len(wagers)} wagers')"
```

---

## 2FA Authentication Testing

### Test 1: Start Admin Dashboard ✅

**Steps:**
```bash
cd backend
python admin_dashboard.py
```

**Expected output:**
```
============================================================
🔧 COINFLIP ADMIN DASHBOARD
============================================================

⚠️  This tool has full access to all funds.
⚠️  2FA authentication required for security.

Admin: your_email@example.com

🔐 Sending 2FA code to your_email@example.com...
✅ Code sent! Check your email.
⏰ Valid for 10 minutes
```

**Verify:**
- ✅ Email received with 6-digit OTP
- ✅ Email has proper formatting
- ✅ OTP is numeric, 6 digits
- ✅ Email shows operation: "Admin Dashboard Login"

---

### Test 2: 2FA Code Verification ✅

**Enter code from email:**
```
🔐 Two-Factor Authentication Required
Enter 6-digit code from email (3 attempts left): 123456
```

**Expected (correct code):**
```
✅ Authentication successful!

============================================================
✅ 2FA AUTHENTICATION SUCCESSFUL
============================================================

Session ID: abc123def456...
Session valid for: 24 hours

Starting dashboard...
```

**Then see main menu:**
```
============================================================
🔧 COINFLIP ADMIN DASHBOARD
============================================================

📊 FUND MANAGEMENT:
  1. View All Escrows with Balances
  2. Check Stuck/Orphaned Escrows
  3. Recover Funds from Specific Escrow
  4. Recover User's Referral Earnings

👤 USER MANAGEMENT:
  5. Search User by ID/Wallet
  6. Export User Data
  7. Manual Payout to User

🔒 SECURITY & AUDITING:
  8. Run Security Audit
  9. View Recent Security Events
  10. Verify All Escrow Keys

💾 BACKUP MANAGEMENT:
  11. Create Backup Now
  12. List All Backups
  13. Verify Backup Integrity
  14. Restore from Backup

⚠️  EMERGENCY:
  15. Emergency Stop (Disable All Betting)
  16. Sweep All Escrows to Treasury

  0. Exit
============================================================

Select option:
```

---

### Test 3: Failed 2FA Attempts ❌

**Test wrong code:**

**Steps:**
1. Start dashboard
2. Receive OTP email
3. Enter WRONG code: `999999`

**Expected:**
```
❌ Invalid code. 2 attempts remaining.
Enter 6-digit code from email (2 attempts left):
```

**Enter wrong again:**
```
❌ Invalid code. 1 attempts remaining.
Enter 6-digit code from email (1 attempts left):
```

**Enter wrong third time:**
```
❌ Invalid code. 0 attempts remaining.
❌ Too many failed attempts. Please request a new code.

❌ 2FA authentication failed. Access denied.
```

**Verify:**
- ✅ 3 attempt limit enforced
- ✅ Dashboard access denied
- ✅ Security event logged

---

### Test 4: Expired OTP ⏰

**Steps:**
1. Start dashboard
2. Wait 11+ minutes (OTP expires after 10 minutes)
3. Enter the expired code

**Expected:**
```
❌ OTP expired. Please request a new code.
❌ 2FA authentication failed. Access denied.
```

---

## Fund Management Testing

### Test 5: View All Escrows 💰

**Steps:**
1. Authenticate with 2FA
2. Select option `1` (View All Escrows)

**Expected:**
```
================================================================================
📊 ALL ESCROWS WITH BALANCES
================================================================================

Scanning referral escrows... (this may take a moment)

┌─────────────────┬──────────────┬────────────────────┬──────────────┬───────────┬─────────┐
│ Type            │ Wager ID     │ Address            │ Balance      │ Status    │ User ID │
├─────────────────┼──────────────┼────────────────────┼──────────────┼───────────┼─────────┤
│ Bet (Creator)   │ wgr_abc123...│ So1Abc...xyz4      │ 0.500000 SOL │ open      │ 1       │
│ Bet (Acceptor)  │ wgr_def456...│ So1Def...uvw8      │ 0.500000 SOL │ in_prog.. │ 2       │
│ Referral        │ N/A          │ So1Ref...qrs9      │ 0.050000 SOL │ Active    │ 3       │
└─────────────────┴──────────────┴────────────────────┴──────────────┴───────────┴─────────┘

💰 TOTAL IN ESCROWS: 1.050000 SOL

Press Enter to continue...
```

**Verify:**
- ✅ All escrows listed
- ✅ Balances accurate
- ✅ Types identified (Bet/Referral)
- ✅ Total calculated correctly

---

### Test 6: Check Stuck Escrows 🔍

**Steps:**
1. Select option `2` (Check Stuck/Orphaned Escrows)

**Expected (if stuck funds found):**
```
================================================================================
🔍 CHECKING FOR STUCK ESCROWS
================================================================================

⚠️  Found 2 escrows with funds:

┌──────────────┬──────────────┬────────────────────┬──────────────┬───────────┬────────────┐
│ Wager ID     │ Type         │ Address            │ Balance      │ Status    │ Created    │
├──────────────┼──────────────┼────────────────────┼──────────────┼───────────┼────────────┤
│ wgr_old123...│ creator      │ So1Old...abc1      │ 0.250000 SOL │ cancelled │ 2025-11-20 │
│ wgr_old456...│ acceptor     │ So1Old...def2      │ 1.000000 SOL │ error     │ 2025-11-25 │
└──────────────┴──────────────┴────────────────────┴──────────────┴───────────┴────────────┘

💰 TOTAL STUCK: 1.250000 SOL

Press Enter to continue...
```

**Expected (if no stuck funds):**
```
✅ No stuck escrows found!
```

**Stuck escrows = escrows with balance but wager is:**
- Cancelled
- Expired
- Error state
- Complete but not swept

---

### Test 7: Recover Specific Escrow 💸

**Prerequisites:**
- Have a stuck escrow (or create one by cancelling a wager)

**Steps:**
1. Select option `3` (Recover Funds from Specific Escrow)
2. Enter wager ID: `wgr_abc123`
3. Enter recipient wallet: `<YOUR_WALLET_ADDRESS>`
4. Enter reason: `Testing recovery procedure`
5. Confirm: `yes`

**Expected:**
```
============================================================
💸 RECOVER FUNDS FROM ESCROW
============================================================

Enter Wager ID: wgr_abc123
Enter recipient wallet address: So1YourWallet...xyz789
Enter reason for recovery: Testing recovery procedure

⚠️  Confirm recovery to So1YourWallet...xyz789? (yes/no): yes

[Processing...]

✅ RECOVERY SUCCESSFUL!

Transactions:
  creator_tx: AbCdEf123456...
  acceptor_tx: GhIjKl789012... (if applicable)
  total_recovered: 0.500000 SOL

Press Enter to continue...
```

**Verify:**
1. Check recipient wallet balance increased
2. Check escrow wallet balance = 0
3. Check audit log for recovery event

```bash
# Verify on-chain
solana balance <RECIPIENT_WALLET> --url devnet
solana balance <ESCROW_WALLET> --url devnet

# Verify audit log
python -c "from security.audit import AuditLogger; logger = AuditLogger(); events = logger.get_recent_events(limit=5); print([e for e in events if 'recovery' in e['details'].lower()])"
```

---

### Test 8: Recover Referral Earnings 🎁

**Prerequisites:**
- User with referral escrow balance > 0

**Steps:**
1. Select option `4` (Recover User's Referral Earnings)
2. Enter user ID: `3`
3. Enter reason: `User requested manual payout`
4. Confirm: `yes`

**Expected:**
```
============================================================
💸 RECOVER REFERRAL EARNINGS
============================================================

Enter User ID: 3

Referral Escrow Balance: 0.050000 SOL
User's Payout Wallet: So1UserWallet...abc123

Enter reason for recovery: User requested manual payout

⚠️  Send 0.050000 SOL to So1UserWallet...abc123? (yes/no): yes

[Processing...]

✅ Recovery successful! TX: XyZ789...

Press Enter to continue...
```

**If user has no payout wallet:**
```
User has no payout wallet set. Enter recipient address:
```

---

## User Management Testing

### Test 9: Search User 🔍

**Steps:**
1. Select option `5` (Search User by ID/Wallet)
2. Enter user ID: `1`

**Expected:**
```
============================================================
🔍 SEARCH USER
============================================================

Enter User ID or Wallet Address: 1

============================================================
USER PROFILE: 1
============================================================

Platform: web
Wallet: So1UserWallet...abc123
Payout Wallet: So1PayoutWallet...def456

📊 Stats:
  Games Played: 25
  Games Won: 13 (52.0%)
  Total Wagered: 125.500000 SOL
  Total Won: 130.250000 SOL
  Total Lost: 120.000000 SOL

🏆 Tier: Silver (fee: 1.8%)

🎁 Referrals:
  Referral Code: ABCD1234
  Referred By: None
  Total Referrals: 5
  Lifetime Earnings: 0.250000 SOL
  Total Claimed: 0.100000 SOL
  Current Balance: 0.150000 SOL
  Escrow: So1RefEscrow...xyz789

Press Enter to continue...
```

---

### Test 10: Export User Data 📄

**Steps:**
1. Select option `6` (Export User Data)
2. Enter user ID: `1`

**Expected:**
```
============================================================
📄 EXPORT USER DATA
============================================================

Enter User ID: 1

[Processing...]

✅ User data exported to: user_1_export_20251128_103045.json

Press Enter to continue...
```

**Verify file created:**
```bash
ls -lh user_1_export_*.json
cat user_1_export_*.json | python -m json.tool
```

**File should contain:**
```json
{
  "user": {
    "user_id": 1,
    "platform": "web",
    "wallet_address": "So1UserWallet...abc123",
    "tier": "Silver",
    "games_played": 25,
    ...
  },
  "games": [
    {
      "game_id": "game_123",
      "amount": 0.5,
      "result": "win",
      ...
    }
  ],
  "wagers": [...],
  "referrals": [...]
}
```

---

### Test 11: Manual Payout 💸

**Prerequisites:**
- Treasury wallet has funds
- User has payout wallet set

**Steps:**
1. Select option `7` (Manual Payout to User)
2. Enter user ID: `1`
3. Enter amount: `0.1`
4. Enter reason: `Compensation for bug`
5. Confirm: `yes`

**Expected:**
```
============================================================
💸 MANUAL PAYOUT
============================================================

Enter User ID: 1
Enter amount (SOL): 0.1
Enter reason: Compensation for bug

Sending 0.1 SOL to So1UserWallet...abc123
Confirm? (yes/no): yes

[Processing...]

✅ Payout successful! TX: AbCdEf123...

Press Enter to continue...
```

**Verify:**
```bash
# Check user received funds
solana balance <USER_PAYOUT_WALLET> --url devnet
```

---

## Security Testing

### Test 12: Run Security Audit 🔒

**Steps:**
1. Select option `8` (Run Security Audit)

**Expected:**
```
================================================================================
🔒 SECURITY AUDIT
================================================================================

1. Checking for signature reuse vulnerabilities...
   ✅ Signature reuse protection: ACTIVE

2. Verifying escrow key encryption...
   Total escrows: 15
   Missing keys: 0
   Errors: 0

3. Checking for stuck funds...
   ✅ No stuck funds found

4. Reviewing recent security events...
   Critical events (24h): 0
   Warnings (24h): 2

5. Backup status...
   ✅ Latest backup: backup_20251128_080000.db.gz.enc (2025-11-28 08:00:00)

================================================================================
AUDIT COMPLETE
================================================================================

Press Enter to continue...
```

**If issues found:**
```
2. Verifying escrow key encryption...
   Total escrows: 15
   Missing keys: 2
   Errors: 0

   ⚠️  WARNING: Escrows with missing keys found!
      - Wager wgr_abc123: So1Escrow...abc1

3. Checking for stuck funds...
   ⚠️  2 escrows with funds (1.250000 SOL total)

4. Reviewing recent security events...
   Critical events (24h): 1
   Warnings (24h): 5

   ⚠️  Suspicious IPs detected:
      - 192.168.1.100: 15 rate limit violations
      - 10.0.0.50: 8 rate limit violations
```

---

### Test 13: View Security Events 📋

**Steps:**
1. Select option `9` (View Recent Security Events)
2. Enter hours: `24` (default)

**Expected:**
```
================================================================================
📋 RECENT SECURITY EVENTS
================================================================================

Show events from last N hours (default 24):

┌──────────────────────┬────────────────┬──────────┬────────┬────────────────────┐
│ Time                 │ Type           │ Severity │ User   │ Details            │
├──────────────────────┼────────────────┼──────────┼────────┼────────────────────┤
│ 2025-11-28 10:30:15  │ ADMIN_ACTION   │ INFO     │ N/A    │ Admin dashboard... │
│ 2025-11-28 10:15:22  │ RATE_LIMIT     │ WARNING  │ 5      │ Rate limit exce... │
│ 2025-11-28 09:45:10  │ REFERRAL_USED  │ INFO     │ 8      │ Used referral c... │
│ 2025-11-28 09:30:05  │ WITHDRAWAL     │ INFO     │ 3      │ Withdrew 1.5 SO... │
└──────────────────────┴────────────────┴──────────┴────────┴────────────────────┘

Press Enter to continue...
```

---

### Test 14: Verify Escrow Keys 🔑

**Steps:**
1. Select option `10` (Verify All Escrow Keys)

**Expected:**
```
============================================================
🔑 VERIFYING ESCROW KEYS
============================================================

This may take a while for large databases...

✅ Verification complete!

Total escrows checked: 50
Verified keys: 50
Missing keys: 0
Decryption errors: 0

Press Enter to continue...
```

**If errors found:**
```
⚠️  MISSING KEYS:
  - Wager wgr_abc123 (creator): So1Escrow...abc1
  - Wager wgr_def456 (acceptor): So1Escrow...def2

⚠️  DECRYPTION ERRORS:
  - Wager wgr_xyz789 (creator): Invalid encryption key
```

---

## Backup Testing

### Test 15: Create Backup 💾

**Steps:**
1. Select option `11` (Create Backup Now)

**Expected:**
```
============================================================
💾 CREATE BACKUP
============================================================

[Creating backup...]
[Compressing...]
[Encrypting...]

✅ Backup created: backups/backup_20251128_103045.db.gz.enc
✅ Backup verified successfully!

Press Enter to continue...
```

**Verify file:**
```bash
ls -lh backend/backups/backup_*.db.gz.enc

# Should see encrypted file (~size of database compressed)
# Example: backup_20251128_103045.db.gz.enc (2.5 MB)
```

---

### Test 16: List Backups 📚

**Steps:**
1. Select option `12` (List All Backups)

**Expected:**
```
================================================================================
📚 ALL BACKUPS
================================================================================

┌────────────────────────────────────────┬─────────────────────┬──────────┐
│ Filename                               │ Created             │ Size     │
├────────────────────────────────────────┼─────────────────────┼──────────┤
│ backup_20251128_103045.db.gz.enc       │ 2025-11-28 10:30:45 │ 2.50 MB  │
│ backup_20251128_080000.db.gz.enc       │ 2025-11-28 08:00:00 │ 2.48 MB  │
│ backup_20251127_200000.db.gz.enc       │ 2025-11-27 20:00:00 │ 2.45 MB  │
└────────────────────────────────────────┴─────────────────────┴──────────┘

Total backups: 3

Press Enter to continue...
```

---

### Test 17: Verify Backup ✓

**Steps:**
1. Select option `13` (Verify Backup Integrity)
2. Enter filename: `backup_20251128_103045.db.gz.enc`

**Expected:**
```
============================================================
✓ VERIFY BACKUP
============================================================

Enter backup filename: backup_20251128_103045.db.gz.enc

[Decrypting...]
[Decompressing...]
[Validating SQLite database...]

✅ Backup is valid!

Press Enter to continue...
```

**If corrupted:**
```
❌ Backup is corrupted!
Error: [specific error message]
```

---

### Test 18: Restore Backup ⚠️

⚠️ **WARNING:** This OVERWRITES the current database!

**Steps:**
1. First create a fresh backup of current state
2. Select option `14` (Restore from Backup)
3. Enter filename: `backup_20251128_080000.db.gz.enc`
4. Type `RESTORE` to confirm

**Expected:**
```
============================================================
⚠️  RESTORE FROM BACKUP
============================================================

⚠️  WARNING: This will overwrite the current database!
Make sure you have a backup of the current state first.

Enter backup filename: backup_20251128_080000.db.gz.enc

⚠️  CONFIRM RESTORE from backup_20251128_080000.db.gz.enc? (type 'RESTORE' to confirm):
```

**Type:** `RESTORE`

**Expected:**
```
[Decrypting...]
[Decompressing...]
[Replacing database...]

✅ Restore successful!
⚠️  Please restart the application.

Press Enter to continue...
```

**Verify restore:**
```bash
# Restart dashboard
python admin_dashboard.py

# Check database state matches backup timestamp
python -c "from database import Database; db = Database(); users = db.get_all_users(); print(f'Users: {len(users)}'); print(f'Last user: {users[-1].user_id if users else None}')"
```

---

## Emergency Procedures Testing

### Test 19: Emergency Stop 🚨

⚠️ **WARNING:** This disables ALL betting platform-wide!

**Steps:**
1. Select option `15` (Emergency Stop)
2. Confirm: `yes`

**Expected:**
```
============================================================
🚨 EMERGENCY STOP
============================================================

This will create a flag file to disable all betting.
The API will reject all create/accept wager requests.

Enable emergency stop? (yes/no): yes

✅ Emergency stop enabled!
To disable: delete the EMERGENCY_STOP file

Press Enter to continue...
```

**Verify file created:**
```bash
ls -l backend/EMERGENCY_STOP
cat backend/EMERGENCY_STOP
```

**Test API blocked:**
```bash
# Try to create wager via API
curl -X POST http://localhost:8000/api/game/create-wager \
  -H "Content-Type: application/json" \
  -d '{...}'

# Expected: 503 Service Unavailable
# {"detail": "Platform temporarily unavailable"}
```

**Disable emergency stop:**
```bash
rm backend/EMERGENCY_STOP
```

---

### Test 20: Sweep All Escrows 💰

⚠️ **CRITICAL:** This is for PLATFORM SHUTDOWN only!

**Prerequisites:**
- Create test wagers with funds in escrows
- Have stuck escrows

**Steps:**
1. Select option `16` (Sweep All Escrows to Treasury)
2. Type: `SWEEP ALL`

**Expected:**
```
============================================================
🚨 SWEEP ALL ESCROWS TO TREASURY
============================================================

⚠️  WARNING: This is an emergency operation!
Only use this if the platform is being shut down.
All funds will be sent to treasury for manual distribution.

Type 'SWEEP ALL' to confirm:
```

**Type:** `SWEEP ALL`

**Expected:**
```
Scanning all escrows...

  ✅ Swept 0.500000 SOL from Bet (Creator) escrow
  ✅ Swept 0.500000 SOL from Bet (Acceptor) escrow
  ✅ Swept 0.050000 SOL from Referral escrow
  ❌ Failed to sweep wgr_error123: [error message]

✅ Sweep complete!
Total swept: 1.050000 SOL
Transactions: 3

Press Enter to continue...
```

**Verify:**
```bash
# Check treasury balance increased
solana balance <TREASURY_WALLET> --url devnet

# Check all escrows emptied
# (Get addresses from database, verify balance = 0)
```

---

## Common Issues

### Issue 1: 2FA Email Not Received

**Causes:**
- SMTP not configured
- Wrong app password
- Email in spam folder

**Solutions:**
```bash
# Test SMTP manually
python backend/admin_2fa.py
# Follow prompts to test email

# Check .env
cat .env | grep SMTP

# Gmail App Password Instructions:
# 1. Go to https://myaccount.google.com/apppasswords
# 2. Select "Mail" and your device
# 3. Copy 16-character password (ignore spaces)
# 4. Update SMTP_PASSWORD in .env
```

---

### Issue 2: "Encryption key not set"

**Cause:** Missing ENCRYPTION_KEY in .env

**Solution:**
```bash
# Generate new key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Add to .env
echo "ENCRYPTION_KEY=<generated_key>" >> .env
```

---

### Issue 3: "Database locked"

**Cause:** Another process accessing database

**Solution:**
```bash
# Find process
ps aux | grep python

# Kill if needed
pkill -f "python api.py"

# Restart dashboard
python admin_dashboard.py
```

---

### Issue 4: Recovery Fails

**Causes:**
- Escrow has no funds
- Invalid encryption key
- Network issues

**Solutions:**
```bash
# Verify escrow balance
solana balance <ESCROW_ADDRESS> --url devnet

# Test decryption
python -c "
from utils.encryption import decrypt_secret
from database import Database
db = Database()
wager = db.get_wager('WAGER_ID')
try:
    secret = decrypt_secret(wager.creator_escrow_secret, 'ENCRYPTION_KEY')
    print('✅ Decryption successful')
except Exception as e:
    print(f'❌ Decryption failed: {e}')
"

# Check RPC
curl https://api.devnet.solana.com -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'
```

---

## Pre-Production Checklist

Before using admin dashboard in production:

### Security ✅

- [ ] 2FA tested and working
- [ ] SMTP properly configured
- [ ] Admin email secured
- [ ] Dashboard only on secure machine
- [ ] VPN/secure network connection
- [ ] Session timeout tested (24 hours)

### Backup System ✅

- [ ] Automated backups every 6 hours
- [ ] Backup encryption working
- [ ] Backup verification working
- [ ] Restore tested successfully
- [ ] Backups stored securely (offsite)

### Recovery Tools ✅

- [ ] Escrow recovery tested
- [ ] Referral recovery tested
- [ ] Manual payout tested
- [ ] All escrow keys verified
- [ ] Stuck fund detection working

### Emergency Procedures ✅

- [ ] Emergency stop tested
- [ ] Sweep all escrows tested
- [ ] Recovery documentation read
- [ ] Contact procedures established
- [ ] Treasury wallet secured (Ledger)

### Monitoring ✅

- [ ] Security audit runs successfully
- [ ] Security events logging
- [ ] Suspicious activity detection
- [ ] Rate limiting effective
- [ ] Audit logs accessible

---

## Production Best Practices

### Daily Operations

**Every day:**
1. Run security audit (option 8)
2. Check for stuck escrows (option 2)
3. Review security events (option 9)
4. Verify latest backup exists (option 12)

**Weekly:**
1. Verify all escrow keys (option 10)
2. Test backup restore (on separate machine)
3. Review user reports
4. Check referral abuse patterns

**Monthly:**
1. Full security audit
2. Review all admin actions
3. Backup archive to cold storage
4. Update documentation

### Security Protocols

**Before ANY recovery:**
1. Verify user identity
2. Document reason
3. Get second admin approval (if possible)
4. Take backup first
5. Test on small amount first

**Emergency contacts:**
1. Have 2+ admins with access
2. Secure communication channel
3. Emergency procedure document
4. Legal/compliance contact

---

## Next Steps

After admin panel testing:
1. ✅ Review all testing guides
2. ✅ Production deployment (see `PRODUCTION_DEPLOYMENT_GUIDE.md`)
3. ✅ Final security audit
4. ✅ Go live! 🚀

---

## Support

**Issues?**
- Check: `FUND_RECOVERY_GUIDE.md`
- Review: `SECURITY_AUDIT_REPORT.md`
- Test: `backend/admin_2fa.py`

**Emergency?**
- Enable emergency stop immediately
- Contact all admins
- Review audit logs
- Document everything

---

**Last Updated:** 2025-11-28
**Version:** 1.0
**Status:** Ready for Testing 🚀
