# Mainnet Setup Guide - Solana Coinflip

## Prerequisites

1. **Telegram Bot Token**
   - Go to [@BotFather](https://t.me/BotFather) on Telegram
   - Send `/newbot` and follow the instructions
   - Copy the bot token provided

2. **Solana RPC URL**
   - Option 1: Helius (Recommended) - https://helius.dev
   - Option 2: QuickNode - https://quicknode.com
   - Option 3: Public RPC (slower) - https://api.mainnet-beta.solana.com

3. **House Wallet**
   - You need a funded Solana wallet for the house (custodial games)
   - This wallet holds funds for Telegram users
   - Keep at least 1-5 SOL for operations

4. **Treasury Wallet**
   - Public address where fees are collected
   - Can be the same as your house wallet or separate

## Step-by-Step Setup

### 1. Generate Encryption Key

Run this command to generate a secure encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save the output - you'll need it for `.env`

### 2. Prepare House Wallet

**Option A: Create New Wallet (Recommended for testing)**
```bash
cd backend
python -c "from game.solana_ops import generate_wallet; pub, sec = generate_wallet(); print(f'Public: {pub}\\nSecret: {sec}')"
```

**Option B: Use Existing Wallet**
- Export your private key from Phantom/Solflare as base58
- Make sure you have at least 1 SOL in it

### 3. Fund the House Wallet

Send SOL to the house wallet address:
- **Minimum**: 0.5 SOL (for testing)
- **Recommended**: 2-5 SOL (for real operations)

### 4. Create `.env` File

In the project root (`Coinflip/`), create a `.env` file:

```bash
# Copy from template
cp .env.example .env

# Edit with your values
nano .env  # or use any text editor
```

Fill in these values:

```env
# Telegram Bot Token (from @BotFather)
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Solana RPC URL (Helius recommended)
RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_API_KEY

# House Wallet Secret (base58 secret key)
HOUSE_WALLET_SECRET=YOUR_BASE58_SECRET_KEY_HERE

# Treasury Wallet (public address for fees)
TREASURY_WALLET=YOUR_TREASURY_PUBLIC_ADDRESS

# Encryption Key (from step 1)
ENCRYPTION_KEY=YOUR_FERNET_KEY_HERE

# Database (leave as default)
DB_PATH=coinflip.db

# API Server (for web, leave as default)
API_HOST=0.0.0.0
API_PORT=8000
```

### 5. Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 6. Test the Bot Locally

```bash
cd backend
python bot.py
```

You should see:
```
==================================================
Solana Coinflip Bot Starting...
==================================================
Database initialized at coinflip.db
✅ Coinflip Bot is ready!
Press Ctrl+C to stop
==================================================
```

### 7. Test on Telegram

1. Find your bot on Telegram (search for the username you created)
2. Send `/start`
3. You should get a welcome message with your custodial wallet
4. **IMPORTANT**: Send a SMALL amount of SOL (0.01-0.05) to test
5. Try Quick Flip first (vs House)
6. Then test PVP wagers

## Testing Checklist

### Quick Flip (House Game) - ✅ Already Working
- [ ] Deposit 0.05 SOL to your bot wallet
- [ ] Play Quick Flip with 0.01 SOL
- [ ] Verify win/loss works correctly
- [ ] Check transaction appears on Solscan

### PVP Wagers - 🆕 Just Implemented
- [ ] Create a wager (0.01 SOL)
- [ ] View it in "Open Wagers" (use second account or ask friend)
- [ ] Accept the wager
- [ ] Verify game executes and winner receives payout
- [ ] Check stats are updated correctly

### Edge Cases
- [ ] Try to accept your own wager (should fail)
- [ ] Try to play with insufficient balance (should fail)
- [ ] Cancel a wager and verify it's removed
- [ ] Check wallet balance before/after games

## Security Notes

1. **NEVER commit `.env` to git** - It's already in `.gitignore`
2. **Encrypt house wallet secret** - Already done with Fernet
3. **Use environment variables** - Already configured
4. **Monitor house wallet** - Check balance regularly
5. **Set reasonable limits** - Consider max wager amounts

## Mainnet vs Devnet

Currently configured for **MAINNET** (real SOL).

To switch to **DEVNET** for testing:
```env
RPC_URL=https://api.devnet.solana.com
```

Then use devnet SOL from faucet: https://faucet.solana.com

## Troubleshooting

### Bot doesn't start
- Check BOT_TOKEN is correct
- Verify Python version (3.9+)
- Check all dependencies installed

### Transactions fail
- Verify house wallet has SOL
- Check RPC URL is correct and working
- Ensure `skip_preflight=True` is set (already done)

### "BlockhashNotFound" error
- Already fixed with `skip_preflight=True` in code
- If still happening, check RPC endpoint latency

### Balance not updating
- Solana transactions take 1-2 seconds
- Click "Refresh Balance" button
- Check transaction on Solscan

## Cost Estimation

With current 2% fee model:

| Daily Volume | Daily Fees | Monthly Fees |
|--------------|------------|--------------|
| 10 SOL       | 0.2 SOL    | ~6 SOL       |
| 50 SOL       | 1 SOL      | ~30 SOL      |
| 100 SOL      | 2 SOL      | ~60 SOL      |

Gas fees per transaction: ~0.000005 SOL (negligible)

## Next Steps After Testing

1. **Deploy to VPS** - See `context.md` for deployment instructions
2. **Add withdrawal feature** - Currently placeholder
3. **Implement leaderboards** - Track top players
4. **Add referral system** - 25% fee sharing (like VolT/FUGAZI)

## Support

- Check logs: `journalctl -u coinflip -f` (after deployment)
- Database viewer: Use DB Browser for SQLite
- Solana explorer: https://solscan.io

---

**Ready to test?** Follow the steps above and start with small amounts!

Good luck! 🎲🚀
