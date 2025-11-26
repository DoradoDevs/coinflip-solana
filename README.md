# 🎲 Solana Coinflip

**Provably Fair Coinflip Game on Solana**

A dual-platform (Web + Telegram) Player-vs-Player coinflip game with provable fairness using Solana blockhash for randomness.

## Features

✅ **Provably Fair** - Uses Solana blockhash for verifiable randomness
✅ **Dual Platform** - Play on Web (wallet connect) or Telegram (custodial)
✅ **PVP Wagers** - Create and accept coinflip challenges
✅ **2% Fee** - Low commission on all games
✅ **Instant Payouts** - Winners paid immediately
✅ **Secure** - Encrypted wallet management for Telegram users

## Architecture

```
Coinflip/
├── backend/
│   ├── bot.py              # Telegram bot
│   ├── api.py              # FastAPI web backend
│   ├── menus.py            # Telegram keyboards
│   ├── database/           # User & game persistence
│   │   ├── models.py
│   │   └── repo.py
│   ├── game/               # Core game logic
│   │   ├── coinflip.py
│   │   └── solana_ops.py
│   └── utils/              # Encryption, formatting
├── frontend/               # Web interface
│   ├── index.html
│   ├── css/style.css
│   └── js/
│       ├── phantom.js      # Wallet integration
│       └── app.js          # Main app logic
├── .env                    # Configuration
└── requirements.txt        # Python dependencies
```

## Quick Start

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and fill in your configuration:

```bash
cp .env.example .env
```

Required configuration:
- `BOT_TOKEN` - Your Telegram bot token from @BotFather
- `RPC_URL` - Solana RPC endpoint (Helius recommended)
- `HOUSE_WALLET_SECRET` - Encrypted secret for custodial wallet management
- `TREASURY_WALLET` - Public address to receive fees
- `ENCRYPTION_KEY` - Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

### 3. Run Telegram Bot

```bash
cd backend
python bot.py
```

### 4. Run Web Server

```bash
cd backend
python api.py
```

The web interface will be available at `http://localhost:8000`

## How It Works

### Game Flow (PVP)

1. **Create Wager**
   - Player 1 chooses side (HEADS/TAILS) and amount
   - Wager is posted to open wagers list

2. **Accept Wager**
   - Player 2 sees open wagers
   - Accepts a wager (automatically assigned opposite side)

3. **Coin Flip**
   - System fetches latest Solana blockhash
   - Generates result: `SHA-256(blockhash + game_id)`
   - Even hash = HEADS, Odd hash = TAILS

4. **Payout**
   - Winner receives `(wager * 2) - 2% fee`
   - Fee sent to treasury wallet
   - Game result stored with blockhash for verification

### Provable Fairness

Every game uses Solana's blockhash for randomness:

```python
def flip_coin(blockhash: str, game_id: str) -> CoinSide:
    seed = f"{blockhash}{game_id}"
    hash_digest = hashlib.sha256(seed.encode()).hexdigest()
    first_byte = int(hash_digest[:2], 16)
    return CoinSide.HEADS if first_byte % 2 == 0 else CoinSide.TAILS
```

Anyone can verify results by:
1. Getting the game's blockhash from game record
2. Running the same hash function
3. Comparing with stored result

## Platform Differences

### Web (Non-Custodial)
- Users connect Phantom/Solflare wallet
- They manage their own keys
- Transactions signed in-browser
- No wallet creation needed

### Telegram (Custodial)
- Bot generates encrypted wallet for each user
- Bot manages wallet secrets securely
- Users deposit SOL to their bot wallet
- Withdrawals available anytime

## Database Schema

### Users
- `user_id` - Integer (Telegram ID or wallet hash)
- `platform` - "telegram" or "web"
- `wallet_address` - Custodial wallet (Telegram)
- `connected_wallet` - Connected wallet (Web)
- `games_played`, `games_won`, `total_wagered`, etc.

### Games
- `game_id` - Unique game identifier
- `game_type` - "pvp"
- `player1_id`, `player2_id` - User IDs
- `amount` - Wager amount
- `result` - HEADS or TAILS
- `blockhash` - Solana blockhash used
- `winner_id` - Winner's user ID

### Wagers
- `wager_id` - Unique wager identifier
- `creator_id` - User who created wager
- `amount` - Wager amount
- `creator_side` - HEADS or TAILS
- `status` - "open", "accepted", "cancelled"

## Security

- Wallet secrets encrypted with Fernet (AES-128)
- Environment variables never committed to git
- RPC calls use async/await for safety
- Transaction signatures validated on-chain

## Fee Structure

- **House Fee**: 2% on all games
- **Example**: 1 SOL wager → Winner gets 1.96 SOL (2 SOL pot - 2%)

## Development

### Adding New Features

1. **Database**: Add models in `backend/database/models.py`
2. **Game Logic**: Update `backend/game/coinflip.py`
3. **Telegram**: Add handlers in `backend/bot.py`
4. **Web API**: Add endpoints in `backend/api.py`
5. **Frontend**: Update `frontend/js/app.js`

### Testing

```bash
# Test Solana connection
python -c "from game.solana_ops import get_latest_blockhash; import asyncio; print(asyncio.run(get_latest_blockhash('YOUR_RPC_URL')))"

# Test wallet generation
python -c "from game.solana_ops import generate_wallet; print(generate_wallet())"

# Test encryption
python -c "from utils import generate_encryption_key; print(generate_encryption_key())"
```

## Deployment

### VPS Deployment (Telegram Bot)

1. Upload code to server
2. Install dependencies
3. Configure `.env`
4. Create systemd service:

```ini
[Unit]
Description=Solana Coinflip Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/Coinflip/backend
ExecStart=/path/to/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

5. Enable and start:
```bash
sudo systemctl enable coinflip
sudo systemctl start coinflip
```

### Web Deployment

Use nginx as reverse proxy to FastAPI:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Roadmap

- [ ] Complete PVP wager system
- [ ] Add wager expiration
- [ ] Leaderboards
- [ ] Game history with charts
- [ ] Mobile-responsive web UI
- [ ] Solana Pay integration
- [ ] Multi-token support (not just SOL)

## Support

For issues or questions:
- GitHub Issues: [your-repo]
- Telegram: @your_support

## License

MIT License - See LICENSE file

---

**Play Fair. Win Big. All On-Chain.** 🎲
