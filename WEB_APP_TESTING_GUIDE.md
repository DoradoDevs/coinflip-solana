# 🌐 Web App Testing Guide

Complete guide for testing the Coinflip web application before production deployment.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Local Development Testing](#local-development-testing)
4. [Devnet Testing](#devnet-testing)
5. [Test Scenarios](#test-scenarios)
6. [Common Issues](#common-issues)
7. [Pre-Production Checklist](#pre-production-checklist)

---

## Prerequisites

### Required Software

```bash
# Node.js & npm
node --version  # Should be v16+ or v18+
npm --version

# Python
python --version  # Should be 3.8+

# Solana CLI (for devnet testing)
solana --version
```

### Required Wallets

- **Phantom Wallet** (browser extension)
- **Solflare Wallet** (alternative, for compatibility testing)
- Test SOL from devnet faucet

### Required Accounts

- GitHub account (for deployment)
- Email account (for admin 2FA)
- AWS account (if using KMS)

---

## Environment Setup

### 1. Backend Configuration

Create `.env` file in `backend/` directory:

```bash
# === NETWORK CONFIGURATION ===
# For testing: Use devnet
# For production: Use mainnet
SOLANA_NETWORK=devnet
# SOLANA_NETWORK=mainnet-beta  # For production

# === RPC ENDPOINTS ===
# Devnet (FREE)
RPC_URL=https://api.devnet.solana.com

# Mainnet (requires API key)
# RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_KEY
# HELIUS_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_KEY
# QUICKNODE_RPC_URL=https://your-endpoint.solana-mainnet.quiknode.pro/YOUR_KEY/

# === BACKUP RPC ENDPOINTS ===
BACKUP_RPC_URL_1=https://api.devnet.solana.com
# BACKUP_RPC_URL_2=https://your-backup.com

# === ENCRYPTION ===
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your_fernet_key_here

# === WALLET CONFIGURATION ===
# Treasury wallet (receives platform fees)
TREASURY_WALLET=YourDevnetWalletPublicKeyHere

# For testing: You can use a test wallet
# For production: Use Ledger hardware wallet (see LEDGER_WALLET_INTEGRATION.md)
# TREASURY_WALLET_SECRET=[1,2,3,...]  # Only for testing!

# === ADMIN CONFIGURATION ===
ADMIN_EMAIL=your_email@example.com

# === SMTP CONFIGURATION (for 2FA) ===
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
# Get app password: https://myaccount.google.com/apppasswords
SMTP_PASSWORD=your_gmail_app_password

# === PLATFORM CONFIGURATION ===
PLATFORM_NAME=Coinflip
PLATFORM_URL=http://localhost:3000  # For testing
# PLATFORM_URL=https://your-domain.com  # For production

# === RATE LIMITING ===
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60

# === LOGGING ===
LOG_LEVEL=INFO
# LOG_LEVEL=DEBUG  # For detailed debugging
```

### 2. Frontend Configuration

Create `.env` file in `frontend/` directory:

```bash
# === API CONFIGURATION ===
REACT_APP_API_URL=http://localhost:8000
# REACT_APP_API_URL=https://api.your-domain.com  # For production

# === SOLANA CONFIGURATION ===
REACT_APP_NETWORK=devnet
# REACT_APP_NETWORK=mainnet-beta  # For production

REACT_APP_RPC_URL=https://api.devnet.solana.com
# REACT_APP_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_KEY

# === PLATFORM INFO ===
REACT_APP_PLATFORM_NAME=Coinflip
REACT_APP_TREASURY_WALLET=YourDevnetWalletPublicKeyHere
```

### 3. Install Dependencies

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd ../frontend
npm install
```

### 4. Initialize Database

```bash
cd backend
python -c "from database import Database; db = Database(); print('Database initialized!')"
```

---

## Local Development Testing

### 1. Start Backend Server

```bash
cd backend
python api.py
```

**Expected output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

**Test backend health:**
```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-28T10:30:00Z"
}
```

### 2. Start Frontend Development Server

```bash
cd frontend
npm start
```

**Expected output:**
```
Compiled successfully!

You can now view coinflip in the browser.

  Local:            http://localhost:3000
  On Your Network:  http://192.168.1.X:3000
```

### 3. Access Application

Open browser: http://localhost:3000

---

## Devnet Testing

### 1. Get Devnet SOL

**Option A: Solana CLI**
```bash
# Configure for devnet
solana config set --url https://api.devnet.solana.com

# Get your wallet address
solana address

# Request airdrop (2 SOL)
solana airdrop 2

# Check balance
solana balance
```

**Option B: Web Faucet**
- Visit: https://faucet.solana.com/
- Enter your wallet address
- Request 2 SOL

**Option C: Phantom Wallet**
- Switch to Devnet in settings
- Use built-in airdrop feature

### 2. Connect Wallet to Devnet

In Phantom:
1. Click settings (gear icon)
2. Scroll to "Developer Settings"
3. Change Network to "Devnet"
4. Confirm you see "Devnet" badge in wallet

---

## Test Scenarios

### Test 1: Wallet Connection ✅

**Steps:**
1. Open http://localhost:3000
2. Click "Connect Wallet"
3. Select Phantom
4. Approve connection

**Expected:**
- Wallet button shows your address (truncated)
- Balance displays correctly
- No console errors

**Troubleshooting:**
- If wallet doesn't connect: Check network (should be devnet)
- If balance shows 0: Request airdrop
- If errors: Check browser console (F12)

---

### Test 2: User Registration 🆕

**Steps:**
1. Connect wallet (if not already)
2. Application should auto-create user account
3. Check user profile

**Expected:**
- User created in database
- Referral code generated
- Tier set to "Starter"
- Balance shows correctly

**Verify in backend:**
```bash
cd backend
python -c "from database import Database; db = Database(); users = db.get_all_users(); print(f'Total users: {len(users)}'); print(users[0] if users else 'No users')"
```

---

### Test 3: Quick Flip (Instant Game) 🎲

**Steps:**
1. Click "Quick Flip" tab
2. Enter bet amount (e.g., 0.1 SOL)
3. Choose "Heads" or "Tails"
4. Click "Play Now"
5. Approve transaction in Phantom
6. Wait for result

**Expected:**
- Transaction submitted
- Game result shown (Win/Loss)
- Balance updated
- Transaction visible in wallet history

**Verify:**
```bash
# Check game in database
python -c "from database import Database; db = Database(); games = db.get_recent_games(limit=1); print(games[0] if games else 'No games')"
```

**Test cases:**
- ✅ Win game (50% chance)
- ✅ Lose game (50% chance)
- ✅ Balance updates correctly
- ✅ Stats update (games played, won, lost)

---

### Test 4: Create PVP Wager 🆚

**Steps:**
1. Click "PVP" tab
2. Click "Create Wager"
3. Enter bet amount (e.g., 0.5 SOL)
4. Choose your side (Heads/Tails)
5. Set payout wallet (your wallet address)
6. Click "Create Wager"
7. Approve transaction (funds to escrow)

**Expected:**
- Escrow wallet created
- Funds transferred to escrow
- Wager appears in "Open Wagers" list
- Status: "open"

**Verify escrow:**
```bash
# Check escrow balance
solana balance <ESCROW_ADDRESS_FROM_WAGER>
```

**Test cases:**
- ✅ Escrow receives correct amount
- ✅ Wager visible in list
- ✅ Creator balance deducted
- ✅ Wager ID generated

---

### Test 5: Accept PVP Wager 🤝

**Important:** Use a DIFFERENT wallet for this test!

**Steps:**
1. Disconnect current wallet
2. Connect second wallet (with devnet SOL)
3. See open wagers list
4. Click "Accept" on your wager
5. Set payout wallet
6. Confirm acceptance
7. Approve transaction

**Expected:**
- Second escrow created
- Funds transferred from acceptor
- Game executes automatically
- Winner receives 98% × 2 from both escrows
- Treasury receives 2% × 2 fees
- Escrows emptied
- Game marked "complete"

**Verify:**
```bash
# Check game result
python -c "from database import Database; db = Database(); wager = db.get_wager('WAGER_ID'); print(f'Winner: {wager.winner_id}, Status: {wager.status}')"

# Check both escrow balances (should be ~0)
solana balance <CREATOR_ESCROW>
solana balance <ACCEPTOR_ESCROW>
```

**Test cases:**
- ✅ Game executes
- ✅ Winner receives 196% of their bet
- ✅ Loser receives 0%
- ✅ Treasury receives 4% total
- ✅ Stats update for both players

---

### Test 6: Cancel Wager ❌

**Steps:**
1. Create a wager (don't accept)
2. Click "Cancel" on your own wager
3. Confirm cancellation

**Expected:**
- Escrow funds returned (minus 0.025 SOL rent)
- Wager status: "cancelled"
- Wager removed from list

**Verify:**
```bash
# Check refund
python -c "from database import Database; db = Database(); wager = db.get_wager('WAGER_ID'); print(f'Status: {wager.status}')"
```

---

### Test 7: Referral Code System 🎁

**Part A: Generate Referral Code**
1. Connect wallet
2. Go to Profile/Referrals
3. Copy your referral code

**Part B: Use Referral Code**
1. Disconnect wallet
2. Connect NEW wallet (never used before)
3. Paste referral code
4. Submit

**Expected:**
- New user linked to referrer
- Referrer's `total_referrals` increases
- New user shows "Referred by: [CODE]"

**Part C: Earn Commission**
1. Have referred user play a game
2. Check referrer's referral balance
3. Referral commission should appear

**Commission formula:**
- Referrer at **Starter tier** (0 SOL wagered): 0% commission
- Referrer at **Bronze tier** (250+ SOL wagered): 2.5% of loser's fees
- Referrer at **Silver tier** (500+ SOL wagered): 5% of loser's fees
- Referrer at **Gold tier** (1000+ SOL wagered): 7.5% of loser's fees
- Referrer at **Diamond tier** (5000+ SOL wagered): 10% of loser's fees

**Verify:**
```bash
python -c "from database import Database; db = Database(); user = db.get_user(REFERRER_ID); print(f'Referrals: {user.total_referrals}, Earnings: {user.referral_earnings}')"
```

---

### Test 8: Claim Referral Earnings 💰

**Prerequisites:**
- Have referral commissions accumulated
- Have payout wallet set

**Steps:**
1. Go to Referrals page
2. See available balance
3. Click "Claim Earnings"
4. Confirm transaction

**Expected:**
- 1% treasury fee deducted
- 99% sent to payout wallet
- Balance in referral escrow = 0
- `total_referral_claimed` increases

**Example:**
```
Escrow balance: 1.0 SOL
Treasury fee: 0.01 SOL (1%)
You receive: 0.99 SOL
```

---

### Test 9: Tier Progression 📊

**Tiers based on total wagered:**
- **Starter**: 0 SOL → 2.0% fees
- **Bronze**: 250 SOL → 1.9% fees
- **Silver**: 500 SOL → 1.8% fees
- **Gold**: 1000 SOL → 1.7% fees
- **Diamond**: 5000 SOL → 1.5% fees

**Test:**
1. Check starting tier (should be "Starter")
2. Play games totaling 250+ SOL wagered
3. Verify tier upgrades to "Bronze"
4. Verify fees reduced from 2.0% → 1.9%

**Important:** Only WINNER's tier determines fees!

**Verify:**
```bash
python -c "from database import Database; db = Database(); user = db.get_user(USER_ID); print(f'Tier: {user.tier}, Fee: {user.tier_fee_rate*100}%, Wagered: {user.total_wagered}')"
```

---

### Test 10: Payout Wallet Requirement 🔒

**Test:**
1. Create new user (never set payout wallet)
2. Try to create a wager

**Expected:**
- ❌ Request blocked
- Error: "Please set payout wallet first"

**Then:**
1. Set payout wallet in profile
2. Try to create wager again
3. ✅ Should succeed

**Security reason:** Ensures platform can always pay winners.

---

### Test 11: Security Features 🔐

#### A. Signature Replay Prevention

**Test:**
1. Complete a deposit transaction
2. Try to submit SAME transaction signature again

**Expected:**
- ❌ Blocked with error: "Transaction signature already used"

#### B. Double Accept Prevention

**Test:**
1. Create a wager
2. Try to accept it with TWO wallets simultaneously

**Expected:**
- ✅ First wallet accepts successfully
- ❌ Second wallet gets error: "Wager already accepted"

#### C. Self-Referral Prevention

**Test:**
1. Try to use your own referral code

**Expected:**
- ❌ Blocked with error: "Cannot use your own referral code"

#### D. Emergency Stop

**Test:**
1. Create `EMERGENCY_STOP` file in backend directory
2. Try to create/accept wager

**Expected:**
- ❌ All betting disabled
- Error: "Platform temporarily unavailable"

**Disable:**
```bash
rm EMERGENCY_STOP
```

---

## Common Issues

### Issue 1: "Insufficient funds"

**Cause:** Not enough SOL for bet + transaction fees

**Solution:**
```bash
# Get more devnet SOL
solana airdrop 2
```

---

### Issue 2: "Transaction failed"

**Causes:**
- Network congestion
- Insufficient SOL for fees
- RPC endpoint down

**Solutions:**
```bash
# Check RPC health
curl https://api.devnet.solana.com -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'

# Try different RPC
# Edit .env: RPC_URL=https://api.devnet.solana.com
```

---

### Issue 3: Wallet not connecting

**Causes:**
- Wrong network (mainnet vs devnet)
- Phantom not installed
- Pop-up blocked

**Solutions:**
1. Check Phantom settings → Network = Devnet
2. Allow pop-ups for localhost:3000
3. Refresh page
4. Try Solflare wallet as alternative

---

### Issue 4: Backend errors

**Check logs:**
```bash
cd backend
tail -f logs/app.log
```

**Common fixes:**
```bash
# Restart backend
pkill -f "python api.py"
python api.py

# Check database
python -c "from database import Database; Database()"

# Verify .env file
cat .env | grep -v "^#" | grep -v "^$"
```

---

### Issue 5: Frontend not updating

**Solutions:**
```bash
# Clear cache
rm -rf node_modules/.cache

# Restart dev server
npm start
```

---

## Pre-Production Checklist

Before switching to mainnet, verify:

### Backend ✅

- [ ] `.env` configured with mainnet RPC
- [ ] `ENCRYPTION_KEY` is production key (backed up securely)
- [ ] `TREASURY_WALLET` is Ledger hardware wallet
- [ ] `ADMIN_EMAIL` and SMTP configured
- [ ] Database backed up
- [ ] All tests pass
- [ ] Security audit completed

### Frontend ✅

- [ ] `.env` uses production API URL
- [ ] `REACT_APP_NETWORK=mainnet-beta`
- [ ] Built for production: `npm run build`
- [ ] Deployed to hosting (Vercel/Netlify)
- [ ] SSL certificate active (HTTPS)
- [ ] Domain configured

### Security ✅

- [ ] 2FA tested and working
- [ ] Ledger wallet tested
- [ ] AWS KMS configured (optional)
- [ ] Backups automated (every 6 hours)
- [ ] Emergency stop tested
- [ ] Rate limiting active
- [ ] All escrow keys encrypted

### Final Verification ✅

- [ ] Test with REAL SOL on devnet (small amounts)
- [ ] All game flows work end-to-end
- [ ] Referral system working
- [ ] Tier progression working
- [ ] Admin dashboard accessible with 2FA
- [ ] Recovery tools tested
- [ ] Monitoring/alerts configured

---

## Next Steps

After completing web app testing:
1. ✅ Test Telegram bot (see `TELEGRAM_BOT_TESTING_GUIDE.md`)
2. ✅ Test Admin panel (see `ADMIN_PANEL_TESTING_GUIDE.md`)
3. ✅ Production deployment (see `PRODUCTION_DEPLOYMENT_GUIDE.md`)

---

## Support

**Issues?**
- Check logs: `backend/logs/app.log`
- Check database: `python -c "from database import Database; db = Database()"`
- Review security audit: `backend/SECURITY_AUDIT_REPORT.md`

**Emergency?**
- Create `EMERGENCY_STOP` file to disable all betting
- Contact admin immediately
- Check `FUND_RECOVERY_GUIDE.md`

---

**Last Updated:** 2025-11-28
**Version:** 1.0
**Status:** Ready for Testing 🚀
