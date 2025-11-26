# 🚀 Solana Coinflip - Quick Start Guide

Get your coinflip game running in 5 minutes!

## Step 1: Install Dependencies

```bash
cd C:\Users\Clock\OneDrive\Desktop\Coinflip

# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate

# Install everything
pip install -r requirements.txt
```

## Step 2: Generate Encryption Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output (looks like: `yl30xewsEa-y3K29sw0MNW76jkLZTxvPl-RYr1i2VxQ=`)

## Step 3: Create .env File

Create `C:\Users\Clock\OneDrive\Desktop\Coinflip\.env`:

```env
# Get this from @BotFather on Telegram
BOT_TOKEN=your_bot_token_here

# Use your Helius RPC (same as FUGAZI bot)
RPC_URL=https://mainnet.helius-rpc.com/?api-key=f5bdd73b-a16d-4ab1-9793-aa2b445df328

# For now, use FUGAZI's house wallet (encrypted)
HOUSE_WALLET_SECRET=your_encrypted_secret_here

# Your treasury wallet (receives 2% fees)
TREASURY_WALLET=your_wallet_address_here

# Paste the key from Step 2
ENCRYPTION_KEY=yl30xewsEa-y3K29sw0MNW76jkLZTxvPl-RYr1i2VxQ=

# Database
DB_PATH=coinflip.db
```

## Step 4: Run Telegram Bot

```bash
cd backend
python bot.py
```

You should see:
```
==================================================
Solana Coinflip Bot Starting...
==================================================
✅ Coinflip Bot is ready!
```

## Step 5: Run Web Server (Optional)

Open a new terminal:

```bash
cd C:\Users\Clock\OneDrive\Desktop\Coinflip\backend
venv\Scripts\activate
python api.py
```

Visit: `http://localhost:8000`

## Testing the Bot

1. Open Telegram
2. Search for your bot (@your_bot_name)
3. Send `/start`
4. Click "🎲 Quick Flip"
5. Choose HEADS or TAILS
6. Select amount
7. Confirm and play!

## What's Working vs What's Coming

### ✅ FULLY WORKING NOW:
- Telegram bot with full UI
- Database layer (User, Game, Wager models)
- Wallet encryption (Fernet/AES-128)
- Coin flip logic (provably fair via Solana blockhash)
- **Quick Flip** (vs House) - Complete
- **PVP Wagers** - COMPLETE! 🎉
  - Create wagers
  - View open wagers
  - Accept wagers
  - Cancel wagers
  - Full game execution
- Real SOL transactions (battle-tested pattern from VolT/FUGAZI)
- Stats tracking (games played, wins, P/L)
- Web API framework
- Web frontend UI

### 🚧 Coming Soon:
- Withdrawal system (currently placeholder)
- Leaderboards
- Referral program (25% fee sharing)
- WebSocket live updates
- Multi-token support

## Next Steps: Test on Mainnet!

### 1. Easy Setup (Recommended)

```bash
# Interactive setup script
python setup_env.py
```

Follow the prompts to configure everything.

### 2. Verify Everything Works

```bash
# Run comprehensive tests
python test_setup.py
```

This checks all components before you test with real SOL.

### 3. Deploy to VPS

Same process as FUGAZI bot:

```bash
# Upload
scp -r Coinflip root@165.227.186.124:/opt/

# On VPS
cd /opt/Coinflip/backend
python3 -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt

# Create service (see context.md for full service file)
sudo nano /etc/systemd/system/coinflip.service

# Start
sudo systemctl enable coinflip
sudo systemctl start coinflip
sudo systemctl status coinflip
```

## Troubleshooting

**Bot won't start:**
- Check BOT_TOKEN is correct
- Check .env file exists in Coinflip directory (not backend/)
- Check Python version (need 3.8+)

**Database errors:**
- Delete coinflip.db and restart (will recreate)
- Check file permissions

**Transaction errors:**
- Check RPC_URL is working
- Try devnet first
- See context.md for transaction patterns

## Resources

- **Full Documentation**: See `README.md`
- **Technical Details**: See `context.md` (READ THIS!)
- **Related Bots**: VolT (/opt/volt-bot), FUGAZI (github.com/DoradoDevs/fugazi-bot)

## Quick Commands Reference

```bash
# Start bot
cd backend && python bot.py

# Start web server
cd backend && python api.py

# View logs (if deployed)
journalctl -u coinflip -f

# Test database
python -c "from database import Database; db = Database(); print('DB OK!')"

# Test coin flip
python -c "from game.coinflip import flip_coin; print(flip_coin('test', 'game1'))"

# Generate wallet
python -c "from game.solana_ops import generate_wallet; print(generate_wallet())"
```

---

**You're ready to flip! 🎲**

For any issues, check `context.md` - it has EVERYTHING from the VolT/FUGAZI bot experience applied to this project.
