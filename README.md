# Coinflip Web App

**Provably Fair PVP Coinflip on Solana**

A web-based Player-vs-Player coinflip game with provable fairness using Solana blockhash for randomness.

## Features

- Provably Fair - Uses Solana blockhash for verifiable randomness
- PVP Wagers - Create and accept coinflip challenges
- 2% Fee - Low commission on wins
- Instant Payouts - Winners paid immediately
- No wallet connection required - Manual deposit to escrow

## Live

- Website: https://coinflipvp.com
- API: https://api.coinflipvp.com

## Architecture

```
Coinflip/
├── backend/
│   ├── api.py              # FastAPI web backend
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
│   └── js/app.js
├── .env                    # Configuration
└── requirements.txt        # Python dependencies
```

## Quick Start

### 1. Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and configure:

```
RPC_URL=https://api.mainnet-beta.solana.com
HOUSE_WALLET_SECRET=encrypted_house_wallet
TREASURY_WALLET=your_treasury_address
ENCRYPTION_KEY=your_32_byte_hex_key
DATABASE_PATH=coinflip.db
```

### 3. Run Web Server

```bash
cd backend
python api.py
```

Server runs at `http://localhost:8000`

## How It Works

### Game Flow (PVP)

1. **Create Wager**
   - Choose side (HEADS/TAILS) and amount
   - Enter your wallet address for payouts
   - Deposit wager + fee to escrow wallet

2. **Accept Wager**
   - Browse open wagers
   - Accept one (automatically assigned opposite side)
   - Deposit to escrow

3. **Coin Flip**
   - System fetches latest Solana blockhash
   - Generates result: `SHA-256(blockhash + wager_id)`
   - Even hash = HEADS, Odd hash = TAILS

4. **Payout**
   - Winner receives `(wager * 2) - 2% fee`
   - Fee sent to treasury wallet

### Provable Fairness

Every game uses Solana's blockhash for randomness:

```python
def flip_coin(blockhash: str, game_id: str) -> CoinSide:
    seed = f"{blockhash}{game_id}"
    hash_digest = hashlib.sha256(seed.encode()).hexdigest()
    first_byte = int(hash_digest[:2], 16)
    return CoinSide.HEADS if first_byte % 2 == 0 else CoinSide.TAILS
```

Verify any game by running the same hash with the stored blockhash.

## API Endpoints

- `GET /api/wagers/open` - List open wagers
- `POST /api/wager/create` - Create new wager
- `POST /api/wager/{id}/verify-deposit` - Verify creator deposit
- `POST /api/wager/{id}/prepare-accept` - Prepare to accept
- `POST /api/wager/{id}/accept` - Accept and execute flip

## Fee Structure

- **Platform Fee**: 2% on wins
- **Example**: 1 SOL wager -> Winner gets 1.96 SOL

## Deployment

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name coinflipvp.com;

    location / {
        root /opt/coinflip/frontend;
        try_files $uri $uri/ /index.html;
    }
}

server {
    listen 80;
    server_name api.coinflipvp.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Systemd Service

```ini
[Unit]
Description=Coinflip API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/coinflip/backend
ExecStart=/opt/coinflip/venv/bin/python api.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## Related

- Telegram Bot: See `Coinflip-Telegram` repository

## License

MIT License
