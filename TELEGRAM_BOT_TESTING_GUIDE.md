# 🤖 Telegram Bot Testing Guide

Complete guide for testing the Coinflip Telegram bot before production deployment.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Bot Setup](#bot-setup)
3. [Environment Configuration](#environment-configuration)
4. [Local Testing](#local-testing)
5. [Test Scenarios](#test-scenarios)
6. [Common Issues](#common-issues)
7. [Pre-Production Checklist](#pre-production-checklist)

---

## Prerequisites

### Required Software

```bash
# Python 3.8+
python --version

# pip packages
pip install python-telegram-bot python-dotenv solana solders cryptography
```

### Required Accounts

- **Telegram Account** (for testing)
- **BotFather Access** (to create bot)
- **Devnet SOL** (for testing transactions)

### Files Needed

- `backend/telegram_bot.py` (bot code)
- `backend/.env` (configuration)
- `backend/database/` (database system)

---

## Bot Setup

### Step 1: Create Bot with BotFather

1. Open Telegram and search for `@BotFather`
2. Start conversation: `/start`
3. Create new bot: `/newbot`
4. Enter bot name: `Coinflip Test Bot` (for testing)
5. Enter username: `your_coinflip_test_bot` (must end with `bot`)
6. **Save the token** - you'll need it!

**Example output:**
```
Done! Congratulations on your new bot!
You can find it at t.me/your_coinflip_test_bot
Token: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
Keep your token secure!
```

### Step 2: Configure Bot Settings

**Set commands:**
```
/setcommands
@your_coinflip_test_bot

start - Start the bot and get welcome message
help - Show available commands
balance - Check your wallet balance
deposit - Get deposit address
withdraw - Withdraw SOL to external wallet
flip - Play Quick Flip (instant game)
wager - Create PVP wager
mywagers - View your open wagers
accept - Accept an open wager
cancel - Cancel your wager
referral - Get your referral code
stats - View your game statistics
```

**Set description:**
```
/setdescription
@your_coinflip_test_bot

🎲 Coinflip - Provably Fair Coin Flip on Solana

Play instant coin flip games or create PVP wagers. All games use Solana blockchain for transparency.

Commands: /help for full list
```

**Set about text:**
```
/setabouttext
@your_coinflip_test_bot

Provably fair coin flip gambling on Solana blockchain
```

---

## Environment Configuration

### Add to `.env` file:

```bash
# === TELEGRAM BOT CONFIGURATION ===
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_BOT_ENABLED=true

# Mode: polling (for testing) or webhook (for production)
TELEGRAM_BOT_MODE=polling
# TELEGRAM_BOT_MODE=webhook  # For production

# Webhook URL (only for production)
# TELEGRAM_WEBHOOK_URL=https://your-domain.com/telegram/webhook

# === EXISTING CONFIGURATION ===
SOLANA_NETWORK=devnet
RPC_URL=https://api.devnet.solana.com
ENCRYPTION_KEY=your_fernet_key
TREASURY_WALLET=your_treasury_wallet
# ... other settings from backend .env
```

---

## Local Testing

### Step 1: Start the Bot

```bash
cd backend
python telegram_bot.py
```

**Expected output:**
```
INFO:root:🤖 Starting Coinflip Telegram Bot...
INFO:root:Bot mode: polling
INFO:root:Bot username: @your_coinflip_test_bot
INFO:httpx:HTTP Request: GET https://api.telegram.org/bot...
INFO:root:✅ Bot started successfully!
INFO:root:Press Ctrl+C to stop
```

### Step 2: Find Your Bot

1. Open Telegram app/web
2. Search for `@your_coinflip_test_bot`
3. Click "Start" or send `/start`

**Expected response:**
```
🎲 Welcome to Coinflip!

Provably fair coin flip on Solana blockchain.

💰 Your Custodial Wallet:
Address: abc123...xyz789

To get started:
1. Deposit SOL using /deposit
2. Play games with /flip or /wager
3. Withdraw anytime with /withdraw

Commands: /help
```

---

## Test Scenarios

### Test 1: Bot Startup ✅

**Steps:**
1. Send `/start` to bot

**Expected:**
- Welcome message received
- Custodial wallet created
- User registered in database
- Wallet address displayed

**Verify in database:**
```bash
python -c "from database import Database; db = Database(); users = [u for u in db.get_all_users() if u.platform == 'telegram']; print(f'Telegram users: {len(users)}'); print(users[0] if users else 'No users')"
```

**Check:**
- ✅ User created with platform='telegram'
- ✅ Custodial wallet generated
- ✅ Encrypted private key stored
- ✅ Telegram chat_id saved

---

### Test 2: Help Command 📚

**Steps:**
1. Send `/help`

**Expected:**
```
🎲 Coinflip Commands

💰 WALLET:
/balance - Check balance
/deposit - Get deposit address
/withdraw <address> <amount> - Withdraw SOL

🎮 GAMES:
/flip <amount> <heads|tails> - Quick Flip
/wager <amount> <heads|tails> - Create PVP wager
/mywagers - Your open wagers
/accept <wager_id> - Accept a wager
/cancel <wager_id> - Cancel your wager

📊 INFO:
/referral - Get referral code
/stats - Your statistics
/help - This message

Example:
/flip 0.5 heads
/wager 1.0 tails
```

---

### Test 3: Deposit SOL 💵

**Steps:**
1. Send `/deposit`

**Expected response:**
```
💰 Deposit SOL

Send SOL to this address:
`abc123...xyz789`

⚠️ IMPORTANT:
- This is YOUR custodial wallet
- Only send SOL (not tokens)
- Network: Devnet
- Minimum: 0.01 SOL

After sending, use /balance to check
```

**Then:**
2. Send devnet SOL to that address
3. Wait ~30 seconds
4. Send `/balance`

**Expected:**
```
💰 Your Balance

Address: abc123...xyz789
Balance: 1.50 SOL

Available for games: 1.50 SOL
In pending wagers: 0.00 SOL

Play: /flip or /wager
```

**Get devnet SOL:**
```bash
# Using Solana CLI
solana airdrop 2 <YOUR_CUSTODIAL_WALLET_ADDRESS> --url devnet

# Or use web faucet
# https://faucet.solana.com/
```

---

### Test 4: Quick Flip Game 🎲

**Steps:**
1. Ensure balance > 0.1 SOL
2. Send: `/flip 0.1 heads`

**Expected response:**
```
🎲 Quick Flip

Your bet: 0.10 SOL
You chose: Heads
Fee: 0.002 SOL (2.0%)

🎲 Flipping coin...

Result: HEADS! 🎉
You WON!

Payout: 0.196 SOL
New balance: 1.596 SOL

Blockhash: AbCdEf...
Game ID: game_123456

Play again: /flip
```

**Verify:**
```bash
# Check game in database
python -c "from database import Database; db = Database(); games = db.get_user_games(user_id=USER_ID, limit=1); print(games[0].__dict__ if games else 'No games')"
```

**Test variations:**
- `/flip 0.1 heads` - Bet on heads
- `/flip 0.5 tails` - Bet on tails
- `/flip 1.0 heads` - Larger bet

**Test cases:**
- ✅ Win game (balance increases)
- ✅ Lose game (balance decreases)
- ✅ Stats update (games_played, games_won/lost)
- ✅ Fees deducted correctly

---

### Test 5: Invalid Commands ❌

**Test error handling:**

```bash
# No amount
/flip heads
→ "Usage: /flip <amount> <heads|tails>"

# Invalid amount
/flip abc heads
→ "Invalid amount"

# Insufficient balance
/flip 999 heads
→ "Insufficient balance"

# Missing side
/flip 0.1
→ "Usage: /flip <amount> <heads|tails>"

# Invalid side
/flip 0.1 middle
→ "Choose 'heads' or 'tails'"

# Amount too small
/flip 0.001 heads
→ "Minimum bet: 0.01 SOL"
```

---

### Test 6: Create PVP Wager 🆚

**Steps:**
1. Send: `/wager 0.5 heads`

**Expected:**
```
🆚 PVP Wager Created!

Wager ID: wgr_abc123
Amount: 0.50 SOL
Your side: Heads
Opponent gets: Tails

Status: Waiting for opponent...

Share this ID for others to accept:
/accept wgr_abc123

Your wagers: /mywagers
Cancel: /cancel wgr_abc123
```

**Important notes:**
- For Telegram bot, payout wallet = custodial wallet (no need to set separately)
- Funds moved to escrow immediately
- Balance reduced by bet amount

**Verify escrow:**
```bash
# Get wager from database
python -c "from database import Database; db = Database(); wager = db.get_wager('wgr_abc123'); print(f'Escrow: {wager.creator_escrow_address}')"

# Check escrow balance (should be 0.5 SOL + rent)
solana balance <ESCROW_ADDRESS> --url devnet
```

---

### Test 7: View Open Wagers 👀

**Steps:**
1. Send: `/mywagers`

**Expected:**
```
📋 Your Open Wagers

Wager #1
ID: wgr_abc123
Amount: 0.50 SOL
Side: Heads
Status: open
Created: 2025-11-28 10:30

Cancel: /cancel wgr_abc123

Total open: 1
```

**If no wagers:**
```
You have no open wagers.

Create one: /wager <amount> <heads|tails>
```

---

### Test 8: Accept PVP Wager 🤝

**Important:** Use a SECOND Telegram account for this test!

**Steps (Second Account):**
1. Start bot: `/start`
2. Deposit SOL: Send to custodial wallet
3. Check balance: `/balance`
4. Accept wager: `/accept wgr_abc123`

**Expected:**
```
🆚 Accepting Wager...

Wager ID: wgr_abc123
Amount: 0.50 SOL
Your side: Tails (opponent has Heads)

Confirm? Reply with:
YES - to accept
NO - to cancel
```

**Then:**
5. Reply: `YES`

**Expected:**
```
🎲 Game Starting...

Creating escrow...
✅ Escrow funded

🎲 Flipping coin...

Result: TAILS! 🎉
You WON!

Payout: 0.98 SOL
New balance: 1.48 SOL

Blockhash: XyZ789...
Game ID: game_789

Your stats: /stats
```

**Verify both users:**
- ✅ Winner receives 98% of bet × 2 = 0.98 SOL
- ✅ Loser receives 0 SOL
- ✅ Treasury receives 2% × 2 = 0.02 SOL total
- ✅ Both escrows emptied
- ✅ Wager status: "complete"

---

### Test 9: Cancel Wager ❌

**Steps:**
1. Create wager: `/wager 0.2 heads`
2. Cancel it: `/cancel wgr_xyz456`

**Expected:**
```
❌ Wager Cancelled

Wager ID: wgr_xyz456
Refund: 0.20 SOL

Note: 0.025 SOL escrow rent not refunded

New balance: 1.175 SOL

Create new: /wager
```

**Verify:**
- ✅ Funds returned (minus rent)
- ✅ Wager removed from open list
- ✅ Balance updated

---

### Test 10: Withdraw SOL 💸

**Steps:**
1. Get external wallet address (e.g., Phantom devnet address)
2. Send: `/withdraw <ADDRESS> 0.5`

**Expected:**
```
💸 Withdraw Request

From: abc123...xyz (custodial)
To: def456...uvw (your wallet)
Amount: 0.50 SOL
Fee: ~0.000005 SOL

Confirm withdrawal? Reply:
YES - to withdraw
NO - to cancel

⚠️ Cannot undo after confirming!
```

**Then:**
3. Reply: `YES`

**Expected:**
```
✅ Withdrawal Successful!

Transaction: https://explorer.solana.com/tx/...?cluster=devnet

Amount sent: 0.50 SOL
New balance: 0.675 SOL

Check: /balance
```

**Verify in external wallet:**
- ✅ Check Phantom wallet balance increased
- ✅ Transaction visible in Solana Explorer
- ✅ Custodial wallet balance reduced

**Test edge cases:**
```bash
# Withdraw too much
/withdraw <ADDRESS> 999
→ "Insufficient balance"

# Invalid address
/withdraw invalid_address 0.5
→ "Invalid Solana address"

# Amount too small (need to cover fees)
/withdraw <ADDRESS> 0.000001
→ "Amount too small (min: 0.01 SOL)"

# Withdraw all with reserve for fees
/withdraw <ADDRESS> all
→ Sends (balance - 0.01) to leave room for fees
```

---

### Test 11: Referral System 🎁

**Steps:**
1. Send: `/referral`

**Expected:**
```
🎁 Referral Program

Your referral code: ABCD1234

Share with friends:
"Use code ABCD1234 to join Coinflip!"

📊 Your Stats:
Tier: Starter (0% commission)
Total referrals: 0
Lifetime earnings: 0.00 SOL

How it works:
1. Friends use your code when signing up
2. You earn commission when they play
3. Commission rate increases with your tier:
   • Starter (0 SOL): 0%
   • Bronze (250 SOL): 2.5%
   • Silver (500 SOL): 5%
   • Gold (1000 SOL): 7.5%
   • Diamond (5000 SOL): 10%

Your stats: /stats
```

**Test applying code (Second Account):**
1. Start fresh bot conversation
2. Send: `/start`
3. Send referral code: `ABCD1234`

**Expected:**
```
✅ Referral Applied!

You were referred by: ABCD1234

Benefits:
- Support your referrer
- Their tier determines their commission
- No fee discount for you

Start playing: /flip or /wager
```

**Verify:**
```bash
# Check referral link
python -c "from database import Database; db = Database(); user = db.get_user(NEW_USER_ID); print(f'Referred by: {user.referred_by}')"
```

**Test commission earning:**
1. Referred user plays and loses a game
2. Check referrer's stats: `/stats`
3. Verify commission earned (if referrer has tier with commission > 0%)

---

### Test 12: Statistics 📊

**Steps:**
1. Play several games
2. Send: `/stats`

**Expected:**
```
📊 Your Statistics

🎮 Games:
Total played: 15
Won: 8 (53.3%)
Lost: 7 (46.7%)

💰 Volume:
Total wagered: 5.50 SOL
Total won: 6.20 SOL
Total lost: 4.80 SOL
Net profit: +1.40 SOL

🏆 Tier: Bronze
Fee rate: 1.9%
Next tier: Silver (at 500 SOL)
Progress: 5.50 / 500 (1.1%)

🎁 Referrals:
Total referred: 3
Earnings: 0.05 SOL
Commission rate: 2.5%

Balance: /balance
Referral: /referral
```

---

### Test 13: Tier Progression 🏆

**Tier requirements:**
- **Starter**: 0 SOL → 2.0% fees, 0% referral commission
- **Bronze**: 250 SOL → 1.9% fees, 2.5% commission
- **Silver**: 500 SOL → 1.8% fees, 5% commission
- **Gold**: 1000 SOL → 1.7% fees, 7.5% commission
- **Diamond**: 5000 SOL → 1.5% fees, 10% commission

**Test:**
1. Start with Starter tier
2. Play games totaling 250+ SOL wagered
3. Send `/stats`
4. Verify tier upgraded to Bronze

**Important:**
- Cumulative wagered amount (wins + losses count)
- Only winner's tier determines game fees
- Referrer's tier determines commission rate

---

### Test 14: Concurrent Games 🔄

**Test bot handling multiple users:**

1. **User A**: `/flip 0.1 heads`
2. **User B**: `/flip 0.2 tails` (simultaneously)
3. **User C**: `/wager 0.5 heads`

**Expected:**
- ✅ All games process correctly
- ✅ No database conflicts
- ✅ Each game independent
- ✅ Balances update correctly

**Check database integrity:**
```bash
python -c "from database import Database; db = Database(); print('Running integrity check...'); users = db.get_all_users(); games = db.get_recent_games(limit=100); wagers = db.get_open_wagers(limit=100); print(f'Users: {len(users)}, Games: {len(games)}, Wagers: {len(wagers)}'); print('✅ No errors')"
```

---

### Test 15: Security Features 🔐

#### A. Custodial Wallet Encryption

**Verify:**
```bash
# Check database - private keys should be encrypted
python -c "from database import Database; import sqlite3; conn = sqlite3.connect('coinflip.db'); cursor = conn.cursor(); cursor.execute('SELECT custodial_wallet_secret FROM users WHERE platform=\"telegram\" LIMIT 1'); secret = cursor.fetchone()[0]; print(f'Encrypted: {secret[:50]}...'); print('✅ Private key encrypted' if secret.startswith('gAAAAA') else '❌ NOT ENCRYPTED!')"
```

Expected: Encrypted string starting with `gAAAAA` (Fernet encryption)

#### B. Rate Limiting

**Test:**
```bash
# Send 100 /balance commands rapidly
for i in {1..100}; do
  # Send /balance
done
```

**Expected:**
- First ~50 requests: ✅ Succeed
- After limit: ❌ "Too many requests. Please wait."

#### C. Balance Checks

**Test:**
```bash
# Try to play with insufficient balance
/flip 999 heads
→ "Insufficient balance. Your balance: 1.50 SOL"

# Try to withdraw more than balance
/withdraw <ADDRESS> 999
→ "Insufficient balance"
```

---

### Test 16: Error Recovery 🔧

#### A. Bot Restart

**Test:**
1. Stop bot (Ctrl+C)
2. Restart: `python telegram_bot.py`
3. Send `/balance`

**Expected:**
- ✅ User session recovered
- ✅ Balance correct
- ✅ No data lost

#### B. Network Failure

**Test:**
1. Disconnect internet
2. Send `/flip 0.1 heads`

**Expected:**
- ❌ Error message: "Network error. Please try again."
- ✅ Balance NOT deducted
- ✅ No game created

#### C. RPC Failure

**Test:**
1. Set invalid RPC in .env
2. Send `/balance`

**Expected:**
- ❌ Error: "Unable to connect to blockchain. Please try again later."
- ✅ Automatic failover to backup RPC (if configured)

---

## Common Issues

### Issue 1: Bot not responding

**Causes:**
- Bot not running
- Invalid token
- Network issues

**Solutions:**
```bash
# Check if bot running
ps aux | grep telegram_bot.py

# Restart bot
pkill -f telegram_bot.py
python telegram_bot.py

# Check token
cat .env | grep TELEGRAM_BOT_TOKEN

# Test token manually
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe
```

---

### Issue 2: "Insufficient balance" but wallet has SOL

**Causes:**
- Wrong network (mainnet wallet, devnet bot)
- Wallet not synced
- RPC lag

**Solutions:**
```bash
# Check actual balance on chain
solana balance <CUSTODIAL_WALLET> --url devnet

# Wait 30 seconds and retry
# Sometimes RPC needs time to sync
```

---

### Issue 3: Withdrawal fails

**Causes:**
- Invalid recipient address
- Insufficient SOL for fees
- Network congestion

**Solutions:**
```bash
# Verify address format
solana address <ADDRESS>

# Ensure enough for fees
# Keep at least 0.01 SOL in wallet

# Check RPC health
curl https://api.devnet.solana.com -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'
```

---

### Issue 4: Game not processing

**Causes:**
- Escrow creation failed
- Transaction timeout
- Database lock

**Solutions:**
```bash
# Check logs
tail -f backend/logs/app.log

# Check database
python -c "from database import Database; db = Database(); print('Database OK')"

# Verify escrow
# Get escrow address from error message
solana balance <ESCROW_ADDRESS> --url devnet
```

---

### Issue 5: Referral code not working

**Causes:**
- User already used a code
- Self-referral attempt
- Invalid code format

**Solutions:**
```bash
# Check user status
python -c "from database import Database; db = Database(); user = db.get_user(USER_ID); print(f'Referred by: {user.referred_by}')"

# Verify code exists
python -c "from database import Database; db = Database(); from referral_validation import get_user_by_referral_code; referrer = get_user_by_referral_code(db, 'CODE'); print(f'Code valid: {referrer is not None}')"
```

---

## Pre-Production Checklist

Before deploying to production:

### Bot Configuration ✅

- [ ] Production bot created in BotFather
- [ ] Bot token secured in `.env`
- [ ] Bot commands configured
- [ ] Bot description set
- [ ] Bot profile picture uploaded

### Backend Configuration ✅

- [ ] `.env` uses mainnet RPC
- [ ] `TELEGRAM_BOT_MODE=webhook` (for production)
- [ ] Webhook URL configured with SSL
- [ ] Database encrypted and backed up
- [ ] All tests pass on devnet

### Security ✅

- [ ] Custodial wallets encrypted (Fernet)
- [ ] Rate limiting enabled
- [ ] Admin 2FA working
- [ ] Emergency stop tested
- [ ] All private keys secure

### Testing ✅

- [ ] All commands tested
- [ ] Quick Flip works
- [ ] PVP wagers work
- [ ] Deposits work
- [ ] Withdrawals work
- [ ] Referral system works
- [ ] Error handling works
- [ ] Multiple users tested
- [ ] Concurrent games tested

### Production Deployment ✅

- [ ] Webhook configured (not polling)
- [ ] Server with SSL certificate
- [ ] Monitoring/alerts setup
- [ ] Backup system automated
- [ ] Recovery procedures documented

---

## Webhook Setup (Production)

For production, use webhooks instead of polling:

### 1. Setup HTTPS Server

```bash
# Your server needs SSL certificate
# Use nginx or similar

# Example nginx config:
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /telegram/webhook {
        proxy_pass http://localhost:8000/telegram/webhook;
    }
}
```

### 2. Update `.env`

```bash
TELEGRAM_BOT_MODE=webhook
TELEGRAM_WEBHOOK_URL=https://your-domain.com/telegram/webhook
```

### 3. Set Webhook

```bash
# Set webhook with Telegram
curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook \
  -d url=https://your-domain.com/telegram/webhook
```

### 4. Start Bot

```bash
python telegram_bot.py
```

**Verify webhook:**
```bash
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

---

## Next Steps

After completing Telegram bot testing:
1. ✅ Test Admin panel (see `ADMIN_PANEL_TESTING_GUIDE.md`)
2. ✅ Production deployment (see `PRODUCTION_DEPLOYMENT_GUIDE.md`)

---

## Support

**Issues?**
- Check logs: `backend/logs/telegram_bot.log`
- Check database: `python -c "from database import Database; db = Database()"`
- Test RPC: `solana balance <ADDRESS> --url devnet`

**Emergency?**
- Create `EMERGENCY_STOP` file to disable betting
- Check `FUND_RECOVERY_GUIDE.md` for fund recovery
- Use admin dashboard to manage funds

---

**Last Updated:** 2025-11-28
**Version:** 1.0
**Status:** Ready for Testing 🚀
