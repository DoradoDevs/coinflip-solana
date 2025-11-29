# 🛡️ COMPLETE FUND RECOVERY GUIDE

## Mission Critical: ZERO LOSS GUARANTEE

**As soon as funds leave a user's wallet and enter our system, we are 100% responsible for safe custody and delivery.**

This guide covers EVERY possible scenario where funds could be stuck and how to recover them.

---

## 📍 Fund Lifecycle Stages

### Stage 1: User's Original Wallet → Deposit Transaction Pending
**Location:** User's wallet (not yet received by us)
**Risk:** Transaction could fail, get dropped, or user loses internet

**Recovery Method:**
- Transaction hasn't confirmed yet
- User still has funds if tx fails
- **No action needed from us**

**Verification:**
```python
# Check if transaction confirmed
from game.solana_ops import verify_deposit_transaction

confirmed = await verify_deposit_transaction(
    rpc_url=RPC_URL,
    tx_signature=user_tx_sig,
    expected_recipient=escrow_address,
    expected_amount=wager_amount
)

if not confirmed:
    # Transaction failed - user still has funds
    logger.info("Transaction not confirmed - user retains funds")
```

---

### Stage 2: Funds in Bet Escrow (Creator Side) - Wager Status: OPEN
**Location:** `wager.creator_escrow_address`
**Database:** `wagers` table
**Private Key:** `wager.creator_escrow_secret` (encrypted)

**Risk:**
- User changes mind, wants refund
- Wager expires without acceptance
- Bug prevents normal flow

**Recovery Method 1: Normal Cancellation**
```python
# User calls /api/wager/cancel
# Returns: wager_amount - 0.025 SOL (transaction fee)

from game.escrow import refund_from_escrow

refund_tx, fee_tx = await refund_from_escrow(
    rpc_url=RPC_URL,
    escrow_secret=decrypt_secret(wager.creator_escrow_secret, ENCRYPTION_KEY),
    escrow_address=wager.creator_escrow_address,
    user_wallet=wager.creator_wallet,
    treasury_wallet=TREASURY_WALLET,
    wager_amount=wager.amount,
    fee_amount=0.025
)
```

**Recovery Method 2: Admin Recovery**
```python
# If user can't cancel (bug, API down, etc.)
from admin_recovery_tools import RecoveryTools

recovery = RecoveryTools(db, ENCRYPTION_KEY, RPC_URL)

result = await recovery.recover_escrow_funds(
    wager_id=wager.wager_id,
    recipient_wallet=user.payout_wallet,  # User's payout wallet
    admin_id=ADMIN_USER_ID,
    reason="User unable to cancel - manual refund"
)

# Returns: {'creator_escrow': 'tx_signature_here'}
# Sends FULL balance minus tx fee to user
```

**Verification:**
```bash
# Check escrow balance
solana balance <creator_escrow_address> --url <RPC_URL>

# Check if funds arrived at user's wallet
solana balance <user_payout_wallet> --url <RPC_URL>
```

---

### Stage 3: Funds in Both Escrows - Wager Status: ACCEPTED
**Location:**
- Creator: `wager.creator_escrow_address`
- Acceptor: `wager.acceptor_escrow_address`

**Database:** `wagers` table
**Private Keys:**
- `wager.creator_escrow_secret` (encrypted)
- `wager.acceptor_escrow_secret` (encrypted)

**Risk:**
- Game execution fails mid-flip
- RPC connection lost during payout
- Code bug during game completion

**Recovery Method 1: Determine Winner Manually**
```python
# If game started but didn't complete, check what the result SHOULD be
from game.coinflip import flip_coin, get_latest_blockhash

# Get the blockhash that was used (or should have been used)
blockhash = game.blockhash  # If stored
# OR get current one if game never started
blockhash = await get_latest_blockhash(RPC_URL)

# Calculate result
result = flip_coin(blockhash, game.game_id)

# Determine winner
if result == wager.creator_side:
    winner_wallet = user_creator.payout_wallet
    winner_user = user_creator
else:
    winner_wallet = user_acceptor.payout_wallet
    winner_user = user_acceptor

# Recover to winner
await recovery.recover_escrow_funds(
    wager_id=wager.wager_id,
    recipient_wallet=winner_wallet,
    admin_id=ADMIN_USER_ID,
    reason=f"Game failed - manual payout to winner (result: {result.value})"
)

# This will send from BOTH escrows to winner
```

**Recovery Method 2: Refund Both Users (If Fair)**
```python
# If game never truly started, refund both fairly
creator_escrow_secret = decrypt_secret(wager.creator_escrow_secret, ENCRYPTION_KEY)
acceptor_escrow_secret = decrypt_secret(wager.acceptor_escrow_secret, ENCRYPTION_KEY)

# Refund creator
creator_tx = await transfer_sol(
    rpc_url=RPC_URL,
    from_secret=creator_escrow_secret,
    to_pubkey=user_creator.payout_wallet,
    amount_sol=wager.amount - 0.000005  # Full refund minus tx fee
)

# Refund acceptor
acceptor_tx = await transfer_sol(
    rpc_url=RPC_URL,
    from_secret=acceptor_escrow_secret,
    to_pubkey=user_acceptor.payout_wallet,
    amount_sol=wager.amount - 0.000005
)

logger.info(f"Full refund: creator={creator_tx}, acceptor={acceptor_tx}")
```

**Verification:**
```python
# Check both escrows are empty
creator_balance = await get_sol_balance(RPC_URL, wager.creator_escrow_address)
acceptor_balance = await get_sol_balance(RPC_URL, wager.acceptor_escrow_address)

assert creator_balance < 0.00001, "Creator escrow not empty!"
assert acceptor_balance < 0.00001, "Acceptor escrow not empty!"

# Verify users received funds
creator_received = await get_sol_balance(RPC_URL, user_creator.payout_wallet)
acceptor_received = await get_sol_balance(RPC_URL, user_acceptor.payout_wallet)
```

---

### Stage 4: Game Completed, Winner Paid - Remainder Not Swept
**Location:** Dust/fees remaining in escrow wallets
**Risk:** Treasury fees not collected

**Recovery Method:**
```python
# Sweep any remaining balance to treasury
from game.escrow import collect_fees_from_escrow

# Sweep creator escrow
if wager.creator_escrow_address:
    creator_sweep_tx = await collect_fees_from_escrow(
        rpc_url=RPC_URL,
        escrow_secret=decrypt_secret(wager.creator_escrow_secret, ENCRYPTION_KEY),
        escrow_address=wager.creator_escrow_address,
        treasury_address=TREASURY_WALLET
    )

# Sweep acceptor escrow
if wager.acceptor_escrow_address:
    acceptor_sweep_tx = await collect_fees_from_escrow(
        rpc_url=RPC_URL,
        escrow_secret=decrypt_secret(wager.acceptor_escrow_secret, ENCRYPTION_KEY),
        escrow_address=wager.acceptor_escrow_address,
        treasury_address=TREASURY_WALLET
    )
```

**Verification:**
```python
# Check treasury received funds
treasury_balance_before = 1000.5  # From logs
treasury_balance_after = await get_sol_balance(RPC_URL, TREASURY_WALLET)

fees_collected = treasury_balance_after - treasury_balance_before
logger.info(f"Fees collected: {fees_collected:.6f} SOL")
```

---

### Stage 5: Referral Commission Earned - In Transit to Referrer's Escrow
**Location:** Being sent from treasury to `user.referral_payout_escrow_address`
**Risk:** Transaction fails, network issues

**Recovery Method:**
```python
# Check if commission transaction confirmed
tx_confirmed = await verify_transaction_confirmed(RPC_URL, commission_tx_sig)

if not tx_confirmed:
    # Retry commission payment
    from referrals import send_referral_commission

    commission_tx = await send_referral_commission(
        referrer=referrer_user,
        commission_amount=commission_amount,
        from_wallet_secret=TREASURY_WALLET_SECRET,
        rpc_url=RPC_URL,
        encryption_key=ENCRYPTION_KEY,
        db=db,
        game_id=game.game_id
    )
```

**Verification:**
```python
# Check referrer's escrow balance
from referrals import get_referral_escrow_balance

escrow_balance = await get_referral_escrow_balance(referrer_user, RPC_URL)
logger.info(f"Referrer escrow balance: {escrow_balance:.6f} SOL")
```

---

### Stage 6: Referral Commission in User's Escrow - Awaiting Claim
**Location:** `user.referral_payout_escrow_address`
**Database:** `user.referral_payout_escrow_secret` (encrypted)

**Risk:**
- User loses access to account
- User can't figure out how to claim
- Bug in claim function

**Recovery Method 1: Admin Manual Payout**
```python
# Send directly to user's payout wallet
from admin_recovery_tools import RecoveryTools

recovery = RecoveryTools(db, ENCRYPTION_KEY, RPC_URL)

# Get escrow balance
escrow_balance = await get_referral_escrow_balance(user, RPC_URL)

# Manual payout to user's payout wallet
tx_sig = await recovery.recover_user_payout(
    user_id=user.user_id,
    amount=escrow_balance - 0.000005,  # Minus tx fee
    from_wallet_secret=user.referral_payout_escrow_secret,  # Decrypt inside function
    admin_id=ADMIN_USER_ID,
    reason="User unable to claim - manual payout"
)

# Update user's claimed total
user.total_referral_claimed += (escrow_balance - 0.000005)
db.save_user(user)
```

**Recovery Method 2: Export Private Key for User (LAST RESORT)**
```python
# Only if user has secure way to receive it
from utils.encryption import decrypt_secret

escrow_private_key = decrypt_secret(
    user.referral_payout_escrow_secret,
    ENCRYPTION_KEY
)

# Securely send to user via encrypted channel
# User can import to Phantom/Solflare and withdraw themselves
```

**Verification:**
```python
# Verify payout received
user_balance = await get_sol_balance(RPC_URL, user.payout_wallet)
logger.info(f"User received: {user_balance:.6f} SOL")

# Verify escrow now empty
escrow_balance = await get_referral_escrow_balance(user, RPC_URL)
assert escrow_balance < 0.00001, "Escrow should be empty!"
```

---

### Stage 7: Telegram Custodial Wallet (User's Main Wallet)
**Location:** `user.wallet_address`
**Database:** `user.encrypted_secret`

**Risk:**
- User wants to withdraw to external wallet
- Platform shutting down
- User loses Telegram account

**Recovery Method:**
```python
# Send to user's specified external wallet
custodial_secret = decrypt_secret(user.encrypted_secret, ENCRYPTION_KEY)

# Get current balance
balance = await get_sol_balance(RPC_URL, user.wallet_address)

# Send to user's payout wallet (or address they provide)
withdrawal_tx = await transfer_sol(
    rpc_url=RPC_URL,
    from_secret=custodial_secret,
    to_pubkey=user.payout_wallet,  # Or user-provided address
    amount_sol=balance - 0.000005  # Minus tx fee
)

logger.info(f"Custodial withdrawal: {balance:.6f} SOL | TX: {withdrawal_tx}")

# Log in audit system
audit_logger.log(
    event_type=AuditEventType.ADMIN_ACTION,
    severity=AuditSeverity.CRITICAL,
    user_id=user.user_id,
    details=f"Custodial wallet withdrawal: {balance:.6f} SOL to {user.payout_wallet}"
)
```

---

## 🔍 Finding Lost Funds

### Scan All Escrows for Orphaned Funds

```python
from admin_recovery_tools import RecoveryTools

recovery = RecoveryTools(db, ENCRYPTION_KEY, RPC_URL)

# Find ALL escrows with balances
stuck_escrows = await recovery.check_stuck_escrows()

for escrow in stuck_escrows:
    print(f"Found {escrow['balance']:.6f} SOL in {escrow['type']} escrow")
    print(f"  Wager: {escrow['wager_id']}")
    print(f"  Address: {escrow['address']}")
    print(f"  Status: {escrow['status']}")
    print(f"  User: {escrow.get('creator_id') or escrow.get('acceptor_id')}")
```

### Scan Referral Escrows

```python
# Get all users with referral escrows
import sqlite3

conn = sqlite3.connect("coinflip.db")
cursor = conn.cursor()

cursor.execute("""
    SELECT user_id, referral_payout_escrow_address
    FROM users
    WHERE referral_payout_escrow_address IS NOT NULL
""")

for user_id, escrow_address in cursor.fetchall():
    balance = await get_sol_balance(RPC_URL, escrow_address)
    if balance > 0:
        print(f"User {user_id}: {balance:.6f} SOL in referral escrow")
```

### Scan Custodial Wallets

```python
cursor.execute("""
    SELECT user_id, wallet_address
    FROM users
    WHERE wallet_address IS NOT NULL AND platform = 'telegram'
""")

for user_id, wallet_address in cursor.fetchall():
    balance = await get_sol_balance(RPC_URL, wallet_address)
    if balance > 0:
        print(f"User {user_id}: {balance:.6f} SOL in custodial wallet")
```

---

## 🚨 Emergency Procedures

### Emergency: Platform Shutdown - Return All Funds

```python
async def emergency_return_all_funds():
    """Emergency procedure: return all funds to users."""

    print("🚨 EMERGENCY FUND RETURN INITIATED")
    print("="*60)

    db = Database()
    recovery = RecoveryTools(db, ENCRYPTION_KEY, RPC_URL)

    returned_funds = {
        "bet_escrows": 0.0,
        "referral_escrows": 0.0,
        "custodial_wallets": 0.0,
        "errors": []
    }

    # 1. Return from all bet escrows
    print("\n1. Scanning bet escrows...")
    stuck = await recovery.check_stuck_escrows()

    for escrow in stuck:
        try:
            # Determine recipient (creator or acceptor based on type)
            wager = next(w for w in db.get_open_wagers(1000) if w.wager_id == escrow['wager_id'])

            if escrow['type'] == 'creator_escrow':
                recipient_user_id = wager.creator_id
            else:
                recipient_user_id = wager.acceptor_id

            user = db.get_user(recipient_user_id)
            if not user or not user.payout_wallet:
                print(f"  ⚠️ User {recipient_user_id} has no payout wallet - skipping")
                continue

            # Recover to user's payout wallet
            result = await recovery.recover_escrow_funds(
                wager_id=escrow['wager_id'],
                recipient_wallet=user.payout_wallet,
                admin_id=1,
                reason="EMERGENCY SHUTDOWN - Returning all funds"
            )

            returned_funds["bet_escrows"] += escrow['balance']
            print(f"  ✅ Returned {escrow['balance']:.6f} SOL to user {recipient_user_id}")

        except Exception as e:
            print(f"  ❌ Failed to return escrow {escrow['wager_id']}: {e}")
            returned_funds["errors"].append(str(e))

    # 2. Return from all referral escrows
    print("\n2. Scanning referral escrows...")

    import sqlite3
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id FROM users
        WHERE referral_payout_escrow_address IS NOT NULL
    """)

    for (user_id,) in cursor.fetchall():
        try:
            user = db.get_user(user_id)
            if not user or not user.payout_wallet:
                print(f"  ⚠️ User {user_id} has no payout wallet - skipping")
                continue

            balance = await get_referral_escrow_balance(user, RPC_URL)

            if balance > 0.00001:
                tx_sig = await recovery.recover_user_payout(
                    user_id=user_id,
                    amount=balance - 0.000005,
                    from_wallet_secret=user.referral_payout_escrow_secret,
                    admin_id=1,
                    reason="EMERGENCY SHUTDOWN - Returning referral earnings"
                )

                returned_funds["referral_escrows"] += balance
                print(f"  ✅ Returned {balance:.6f} SOL to user {user_id}")

        except Exception as e:
            print(f"  ❌ Failed for user {user_id}: {e}")
            returned_funds["errors"].append(str(e))

    # 3. Return from custodial wallets (Telegram users)
    print("\n3. Scanning custodial wallets...")

    cursor.execute("""
        SELECT user_id FROM users
        WHERE wallet_address IS NOT NULL AND platform = 'telegram'
    """)

    for (user_id,) in cursor.fetchall():
        try:
            user = db.get_user(user_id)
            if not user or not user.payout_wallet:
                print(f"  ⚠️ User {user_id} has no payout wallet - skipping")
                continue

            custodial_secret = decrypt_secret(user.encrypted_secret, ENCRYPTION_KEY)
            balance = await get_sol_balance(RPC_URL, user.wallet_address)

            if balance > 0.00001:
                tx_sig = await transfer_sol(
                    rpc_url=RPC_URL,
                    from_secret=custodial_secret,
                    to_pubkey=user.payout_wallet,
                    amount_sol=balance - 0.000005
                )

                returned_funds["custodial_wallets"] += balance
                print(f"  ✅ Returned {balance:.6f} SOL to user {user_id}")

        except Exception as e:
            print(f"  ❌ Failed for user {user_id}: {e}")
            returned_funds["errors"].append(str(e))

    conn.close()

    # Summary
    print("\n" + "="*60)
    print("🚨 EMERGENCY FUND RETURN COMPLETE")
    print("="*60)
    print(f"Bet Escrows: {returned_funds['bet_escrows']:.6f} SOL")
    print(f"Referral Escrows: {returned_funds['referral_escrows']:.6f} SOL")
    print(f"Custodial Wallets: {returned_funds['custodial_wallets']:.6f} SOL")
    print(f"Total Returned: {sum([v for k, v in returned_funds.items() if k != 'errors']):.6f} SOL")
    print(f"Errors: {len(returned_funds['errors'])}")

    if returned_funds['errors']:
        print("\n⚠️ ERRORS:")
        for error in returned_funds['errors']:
            print(f"  - {error}")

    return returned_funds
```

---

## 🔐 Security Checklist

### Before ANY Recovery Operation:

- [ ] Verify you have correct ENCRYPTION_KEY
- [ ] Verify you have correct RPC_URL
- [ ] Check user's payout wallet is set and valid
- [ ] Log the recovery operation with reason
- [ ] Test with small amount first if possible
- [ ] Verify transaction confirmed on-chain
- [ ] Update user records after successful recovery
- [ ] Notify user of recovery operation
- [ ] Keep transaction signature for audit trail

### After Recovery:

- [ ] Verify escrow wallet is empty (< 0.00001 SOL)
- [ ] Verify user received funds in payout wallet
- [ ] Update database to reflect fund movement
- [ ] Log completion in audit system
- [ ] Save transaction signature to audit log
- [ ] Mark wager/game status appropriately
- [ ] Respond to user with transaction details

---

## 📞 User Support Scenarios

### User: "I sent SOL but game didn't start"
1. Get transaction signature from user
2. Verify transaction on Solscan
3. Check if funds reached escrow: `await get_sol_balance(RPC_URL, escrow_address)`
4. If yes: Refund from escrow
5. If no: Transaction failed - user still has funds

### User: "Game froze mid-flip, where's my money?"
1. Find wager in database
2. Check both escrow balances
3. Check game status and blockhash
4. If blockhash exists: Calculate result, pay winner
5. If no blockhash: Fair refund to both

### User: "I can't claim my referral earnings"
1. Get user ID
2. Check referral escrow balance
3. If balance > 0: Manual payout to payout wallet
4. Update `total_referral_claimed`
5. Send transaction signature to user

### User: "I want to withdraw everything from Telegram bot"
1. Get user's custodial wallet balance
2. Ask for destination wallet
3. Transfer full balance minus fee
4. Send confirmation with TX signature

---

## 🛡️ Guarantees

### We GUARANTEE:

✅ **Every private key is encrypted and backed up**
- All escrow secrets stored encrypted in database
- Database backed up every 6 hours
- Backups are compressed and verified
- Can decrypt any wallet at any time with ENCRYPTION_KEY

✅ **Every fund movement is logged**
- Audit system logs all critical operations
- Transaction signatures stored
- User actions tracked
- Admin actions logged with admin_id and reason

✅ **Every escrow can be recovered**
- Admin dashboard provides easy recovery tools
- Emergency scripts for mass recovery
- Private keys never lost
- Can always send funds to user's payout wallet

✅ **Every user can get their funds back**
- Multiple recovery methods per stage
- Admin support can manually intervene
- Emergency shutdown procedure returns all funds
- Zero trust - users can verify on blockchain

---

## 🚀 Recovery Tools Reference

### Admin Dashboard
```bash
python admin_dashboard.py
```

Provides menu-driven interface for all recovery operations.

### Admin Recovery Tools (Programmatic)
```python
from admin_recovery_tools import RecoveryTools

recovery = RecoveryTools(db, encryption_key, rpc_url)

# Recover from bet escrow
await recovery.recover_escrow_funds(wager_id, recipient, admin_id, reason)

# Check for stuck escrows
stuck = await recovery.check_stuck_escrows()

# Manual payout
await recovery.recover_user_payout(user_id, amount, wallet_secret, admin_id, reason)

# Export user data
data = recovery.export_user_data(user_id)

# Verify all keys
results = await recovery.verify_all_escrows()
```

### Quick Recovery Script
```python
# Save as quick_recover.py
import asyncio
from admin_recovery_tools import RecoveryTools
from database import Database
import os

async def main():
    db = Database()
    recovery = RecoveryTools(
        db,
        os.getenv("ENCRYPTION_KEY"),
        os.getenv("RPC_URL")
    )

    # Example: Recover specific wager
    result = await recovery.recover_escrow_funds(
        wager_id=input("Wager ID: "),
        recipient_wallet=input("Recipient: "),
        admin_id=1,
        reason=input("Reason: ")
    )

    print(f"✅ Recovery complete: {result}")

asyncio.run(main())
```

---

## 📋 Database Backup Locations

All private keys are stored in encrypted form in:
- `coinflip.db` - Main database
- `backups/coinflip_backup_YYYYMMDD_HHMMSS.db.gz` - Compressed backups

Backup schedule: Every 6 hours (managed by `backup_system.py`)

Retention: Last 30 backups kept automatically

---

**REMEMBER: As long as we have the database + ENCRYPTION_KEY, we can recover ANY funds from ANY stage. ZERO LOSS is possible.**
