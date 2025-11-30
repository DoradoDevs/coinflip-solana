# DoradoDevs Master Knowledge Document
**Last Updated:** 2025-11-29
**Status:** Production - All Systems Operational

---

## Table of Contents
1. [Project Portfolio](#project-portfolio)
2. [Infrastructure & Servers](#infrastructure--servers)
3. [Coinflip Web App](#coinflip-web-app)
4. [VolT Trading Bot](#volt-trading-bot)
5. [FUGAZI Trading Bot](#fugazi-trading-bot)
6. [Fee Structure Summary](#fee-structure-summary)
7. [Technical Patterns & Best Practices](#technical-patterns--best-practices)
8. [Deployment Guide](#deployment-guide)
9. [Wallets & Treasury](#wallets--treasury)

---

## Project Portfolio

### Active Projects

| Project | Type | Status | Location |
|---------|------|--------|----------|
| **Coinflip** | PVP Wager Web App | Production | coinflipvp.com |
| **Coinflip-Telegram** | Telegram Bot | Development | Desktop folder |
| **VolT Bot** | Trading Bot | Production | 165.227.186.124 |
| **FUGAZI Bot** | Trading Bot (White-label) | Production | 165.227.186.124 |

### Repository Structure
```
Desktop/
├── Coinflip/                 # Web app (coinflipvp.com)
├── Coinflip-Telegram/        # Telegram bot (separate project)
├── volt-bot-main/            # VolT Trading Bot source
├── fugazi-bot/               # FUGAZI Trading Bot source
└── Backups/2025-11-29/       # Daily backups
```

---

## Infrastructure & Servers

### Bot Server (VolT + FUGAZI)
- **IP:** 165.227.186.124
- **Provider:** DigitalOcean
- **OS:** Ubuntu
- **Running Services:**
  - `voltbot.service` - VolT Trading Bot (`/opt/volt-bot`)
  - `fugazibot.service` - FUGAZI Trading Bot (`/opt/fugazi-bot`)

### Coinflip Server
- **IP:** 157.245.13.24
- **Domains:**
  - `coinflipvp.com` - Frontend (served from `/var/www/html`)
  - `api.coinflipvp.com` - API (port 8000, `/opt/coinflip`)
- **Running Services:**
  - `coinflip.service` - FastAPI backend

### Nginx Configuration
```nginx
# API (api.coinflipvp.com) - /etc/nginx/sites-available/coinflip
server {
    listen 80;
    server_name api.coinflipvp.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Frontend (coinflipvp.com) - served from /var/www/html via default config
# SSL managed by Certbot
```

---

## Coinflip Web App

### Overview
PVP Solana coinflip game with provably fair randomness using Solana blockhash.

**Live URLs:**
- Website: https://coinflipvp.com
- API: https://api.coinflipvp.com

### Architecture
```
Coinflip/
├── backend/
│   ├── api.py              # FastAPI REST API
│   ├── database/
│   │   ├── models.py       # User, Game, Wager, UsedSignature
│   │   └── repo.py         # SQLite operations
│   ├── game/
│   │   ├── coinflip.py     # Core game logic
│   │   ├── solana_ops.py   # Blockchain operations
│   │   └── escrow.py       # Isolated escrow wallets
│   └── utils/
│       └── encryption.py   # Fernet encryption
├── frontend/
│   ├── index.html          # Main page
│   ├── css/style.css       # Styles (no emojis)
│   └── js/app.js           # Frontend logic (no emojis)
└── requirements.txt
```

### Provably Fair Algorithm (VERIFIED 50/50)
```python
def flip_coin(blockhash: str, game_id: str) -> CoinSide:
    """50/50 fair coinflip using Solana blockhash."""
    seed = f"{blockhash}{game_id}"
    hash_digest = hashlib.sha256(seed.encode()).hexdigest()
    first_byte = int(hash_digest[:2], 16)  # 0-255
    return CoinSide.HEADS if first_byte % 2 == 0 else CoinSide.TAILS
```

**Mathematical Proof:**
- SHA-256 first byte: 256 possible values (0-255)
- Even numbers (0,2,4...254): 128 values = HEADS
- Odd numbers (1,3,5...255): 128 values = TAILS
- **Exactly 50/50 distribution**
- Blockhash is unpredictable and verifiable on-chain

### Fee Structure
- **Platform Fee:** 2% on wins
- **Transaction Fee:** 0.025 SOL per player (covers gas)
- **Winner Payout:** 98% of pot (wager x 2 - 2%)

### Game Flow
1. Creator selects side + amount, deposits to unique escrow
2. Acceptor takes opposite side, deposits to separate escrow
3. System fetches Solana blockhash
4. SHA-256(blockhash + wager_id) determines winner
5. Winner receives 98% payout from escrow
6. 2% fee sent to treasury

### Security Features
- Isolated escrow wallets per wager (no single point of failure)
- Transaction signature reuse prevention
- Atomic wager acceptance (prevents race conditions)
- On-chain deposit verification
- Rate limiting

### API Endpoints
```
GET  /api/wagers/open                  - List open wagers
POST /api/wager/create                 - Create new wager (returns escrow address)
POST /api/wager/{id}/verify-deposit    - Verify creator deposit → status: open
POST /api/wager/{id}/prepare-accept    - Create acceptor escrow (returns escrow address)
POST /api/wager/{id}/accept            - Verify acceptor deposit & execute flip
GET  /api/games/recent                 - Recent completed games with proof

# Admin Endpoints
GET  /api/admin/wagers                 - List all wagers with balances
POST /api/admin/wager/{id}/refund      - Refund escrow to payout wallet
POST /api/admin/wager/{id}/cancel      - Mark wager as cancelled
POST /api/admin/wager/{id}/export-key  - Export escrow private key
```

### Complete Wager Flow (CRITICAL - Read Carefully)

**Creator Flow:**
1. `POST /api/wager/create` - Creates wager + creator escrow wallet
2. User deposits `amount + 0.025 fee` to creator escrow **FROM PAYOUT WALLET**
3. `POST /api/wager/{id}/verify-deposit` - Verifies deposit, status → "open"

**Acceptor Flow:**
1. `POST /api/wager/{id}/prepare-accept` - Creates acceptor escrow, saves to wager
2. User deposits `amount + 0.025 fee` to acceptor escrow **FROM PAYOUT WALLET**
3. `POST /api/wager/{id}/accept` - Verifies deposit to **EXISTING** escrow, executes flip

**⚠️ CRITICAL: Accept uses EXISTING escrow from prepare-accept!**
- `prepare-accept` creates escrow, saves address to `wager.acceptor_escrow_address`
- `accept` calls `verify_escrow_deposit()` against that EXISTING address
- If `accept` created a new escrow, user would deposit to escrow A but verify against escrow B = FAIL

### Deposit Verification Rules
- **Sender must match**: Deposit must come from user's payout wallet
- **Recipient must match**: Deposit must go to the escrow shown in UI
- **Amount must match**: Exactly `wager_amount + 0.025 SOL` transaction fee
- **Signature tracked**: Each TX signature can only be used once (prevents double-spend)

---

## VolT Trading Bot

### Overview
Professional Solana trading/sniper bot for Telegram with advanced features.

**Server:** 165.227.186.124 (`/opt/volt-bot`)
**Service:** `systemctl status voltbot`

### Features
- Auto-buy on CA paste
- Manual buy/sell with slippage control
- Advanced orders (TP, SL, Trailing, DCA)
- Multi-type sniping (CA, ticker, wallet, migration)
- Token security analysis
- MEV protection via Jito
- Referral system (25% rewards)
- Batched referral payouts (24-hour cycle)

### Fee Structure
- **Platform Fee:** 1.0% (FEE_BPS = 100)
- **Referral Reward:** 25% of fees to referrer
- **Jupiter Rebates:** Enabled, goes to treasury

### Key Configuration
```python
# bot.py
FEE_BPS = 100  # 1.0% platform fee
DEFAULT_REFERRER_ID = 7782987352
```

### Architecture
```
volt-bot-main/
├── bot.py                  # Main handlers (3200+ lines)
├── config.py               # Environment config
├── trading/
│   ├── jupiter.py          # Jupiter v6 swaps with retry logic
│   ├── security.py         # Token analysis
│   └── referral_payouts.py # Automated 24h payouts
├── ui/menus.py             # Telegram keyboards
├── utils/
│   ├── store.py            # User settings
│   └── wallets.py          # Wallet management
└── database/repo.py        # Multi-backend persistence
```

### Commands
```
/start    - Main menu
/buy      - Buy token by CA
/sell     - Sell positions
/wallets  - Wallet management
/settings - Bot settings
/snipe    - Snipe menu
/orders   - Active orders
/stats    - User statistics
/ref      - Referral link
/testapi  - Test Jupiter connectivity
```

---

## FUGAZI Trading Bot

### Overview
White-label fork of VolT for $FUGAZI community. Identical functionality, different branding.

**Server:** 165.227.186.124 (`/opt/fugazi-bot`)
**Service:** `systemctl status fugazibot`

### Differences from VolT
| Feature | VolT | FUGAZI |
|---------|------|--------|
| Platform Fee | 1.0% | 1.5% |
| Branding | VolT | $FUGAZI |
| Database | state.db | fugazi_state.db |
| Service | voltbot.service | fugazibot.service |

### Official Links
- Website: https://fugazi.life
- X/Twitter: https://x.com/Fugazionsolana
- CA: `CgK9rq3ysnS4z5FG7pMNNE4B3hXZ8KDQsQnXV85Lpump`

### Fee Structure
- **Platform Fee:** 1.5% (FEE_BPS = 150)
- **Referral Reward:** 25% of fees

---

## Fee Structure Summary

### All Projects Comparison

| Project | Platform Fee | Referral Share | Transaction Fee |
|---------|-------------|----------------|-----------------|
| **Coinflip** | 2% on wins | N/A | 0.025 SOL/player |
| **VolT Bot** | 1.0% | 25% | Gas only |
| **FUGAZI Bot** | 1.5% | 25% | Gas only |

### Treasury Wallet (All Projects)
```
N7G9UdmkpsFkyzJpT74NpJ3Dghjt1iBeL4mTtwCunL3
```
All fees from Coinflip, VolT, and FUGAZI flow to this Ledger wallet.

### Fee Collection Flow
```
User Trade → Platform Fee Deducted → Treasury Wallet
                    ↓
            Referrer (25% of fee) → Pending Balance → Payout Wallet
```

---

## Technical Patterns & Best Practices

### Solana Transaction Pattern (CRITICAL)
```python
async def transfer_sol(rpc_url: str, from_secret: str, to_address: str, amount_sol: float):
    """Battle-tested transfer pattern from VolT/FUGAZI."""
    kp = keypair_from_base58(from_secret)
    to_pubkey = Pubkey.from_string(to_address)
    lamports = math.floor(amount_sol * LAMPORTS_PER_SOL)

    async with AsyncClient(rpc_url) as client:
        # ALWAYS get fresh blockhash (expires in ~60 seconds)
        blockhash_resp = await client.get_latest_blockhash(Confirmed)
        recent_blockhash = blockhash_resp.value.blockhash

        transfer_ix = transfer(TransferParams(
            from_pubkey=kp.pubkey(),
            to_pubkey=to_pubkey,
            lamports=lamports,
        ))

        # Use Transaction.new_signed_with_payer (NOT Transaction() constructor)
        tx = Transaction.new_signed_with_payer(
            [transfer_ix],
            kp.pubkey(),
            [kp],
            recent_blockhash
        )

        # ALWAYS skip_preflight to avoid blockhash expiration during simulation
        opts = TxOpts(skip_preflight=True)
        resp = await client.send_raw_transaction(bytes(tx), opts)
        return str(resp.value)
```

### Wallet Encryption
```python
from cryptography.fernet import Fernet

# Generate key (store in .env)
key = Fernet.generate_key()

# Encrypt wallet secret
f = Fernet(key)
encrypted = f.encrypt(secret.encode()).decode()

# Decrypt when needed
decrypted = f.decrypt(encrypted.encode()).decode()
```

### Error Handling Hierarchy
```python
class UnrecoverableError(Exception):
    """Don't retry - insufficient funds, invalid token"""

class RateLimitError(Exception):
    """Retry with backoff - 429 errors"""

class NetworkError(Exception):
    """Retry with failover - DNS, connection issues"""
```

### Retry Pattern
```python
async def with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await func()
        except RateLimitError:
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
        except NetworkError:
            continue  # Try alternate endpoint
        except UnrecoverableError:
            raise  # Don't retry
    raise Exception("Max retries exceeded")
```

---

## Deployment Guide

### Environment Variables Template
```env
# RPC
RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_KEY

# Wallets
TREASURY_WALLET=N7G9UdmkpsFkyzJpT74NpJ3Dghjt1iBeL4mTtwCunL3
HOUSE_WALLET_SECRET=encrypted_base58_secret
ENCRYPTION_KEY=your_fernet_key

# Database
DATABASE_PATH=coinflip.db

# For Telegram bots only
BOT_TOKEN=your_bot_token
```

### Systemd Service Template
```ini
[Unit]
Description=Service Name
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/project
ExecStart=/opt/project/venv/bin/python main.py
Restart=always
RestartSec=10
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
```

### Common Commands
```bash
# Service management
systemctl start voltbot
systemctl stop voltbot
systemctl restart voltbot
systemctl status voltbot
journalctl -u voltbot -f  # Tail logs

# Git workflow
git add . && git commit -m "message" && git push
ssh root@SERVER "cd /opt/project && git pull && systemctl restart service"
```

---

## Wallets & Treasury

### Production Treasury (Ledger)
```
N7G9UdmkpsFkyzJpT74NpJ3Dghjt1iBeL4mTtwCunL3
```
- All platform fees (Coinflip, VolT, FUGAZI)
- Stored on hardware wallet (Ledger)
- Never expose private key

### Fee Flow Architecture
```
Coinflip Game Fees ────────┐
                           │
VolT Trading Fees ─────────┼──► Treasury Wallet (Ledger)
                           │
FUGAZI Trading Fees ───────┘
```

---

## Quick Reference

### Server Access
```bash
# Coinflip server
ssh root@157.245.13.24

# Bot server
ssh root@165.227.186.124
```

### Update Procedures

**IMPORTANT: Coinflip has TWO directories on server!**
- `/opt/coinflip` - Git repo (backend + frontend source)
- `/var/www/html` - Where nginx serves frontend from

```bash
# Coinflip Web - FULL DEPLOYMENT (from local)
cd Coinflip
git add . && git commit -m "update" && git push
ssh root@157.245.13.24 "cd /opt/coinflip && git pull && cp -r frontend/* /var/www/html/"

# Coinflip - Backend only (restart API)
ssh root@157.245.13.24 "cd /opt/coinflip && git pull && systemctl restart coinflip"

# Coinflip - Frontend only (no service restart needed)
ssh root@157.245.13.24 "cd /opt/coinflip && git pull && cp -r frontend/* /var/www/html/"

# VolT Bot
ssh root@165.227.186.124 "cd /opt/volt-bot && git pull && systemctl restart voltbot"

# FUGAZI Bot
ssh root@165.227.186.124 "cd /opt/fugazi-bot && git pull && systemctl restart fugazibot"
```

### Monitoring
```bash
# Check bot logs
journalctl -u voltbot -f
journalctl -u fugazibot -f

# Check Coinflip API
journalctl -u coinflip -f

# Kill process hogging a port (if "address already in use" error)
fuser -k 8000/tcp  # Then restart service
```

---

## Coinflip Troubleshooting

### Common Errors & Fixes

**"Wager creator not found"**
- **Cause**: `wager.creator_id` points to user that doesn't exist
- **Fix**: Accept endpoint has fallback to create user via `ensure_web_user(wager.creator_wallet)`

**"Sender mismatch: expected X, got Y"**
- **Cause**: User deposited from wrong wallet (not their payout wallet)
- **Fix**: UI shows warning "⚠️ Send from your payout wallet address!"
- **User Action**: Must send from the same wallet entered in profile

**"Recipient mismatch: expected X, got Y"**
- **Cause**: Accept endpoint was creating NEW escrow instead of using existing one
- **Fix**: `verify_escrow_deposit()` function verifies against EXISTING escrow from prepare-accept
- **Files**: `backend/game/escrow.py`, `backend/api.py`

**"Invalid deposit transaction" / 500 Internal Server Error**
- **Cause**: Usually one of the above mismatches
- **Debug**: Check server logs with `journalctl -u coinflip -f`

**"422 Unprocessable Content" on accept**
- **Cause**: Request body doesn't match expected schema
- **Fix**: Check AcceptWagerRequest model in api.py (wager_id is in URL path, not body)

### Key Files Reference
```
backend/
├── api.py                    # All endpoints, request models
├── game/
│   ├── escrow.py             # create_escrow_wallet(), verify_escrow_deposit()
│   ├── solana_ops.py         # verify_deposit_transaction() - checks sender/recipient
│   └── coinflip.py           # play_pvp_game_with_escrows()
└── database/
    └── models.py             # Wager model (creator_id, acceptor_escrow_address, etc.)
```

### Admin Panel Functions
- **Refund**: Transfers escrow funds to creator/acceptor payout wallet
- **Cancel**: Marks wager as cancelled (use after refund)
- **Export**: Shows escrow private key for manual recovery

---

## Recent Changes (2025-11-29 & 2025-11-30)

### Coinflip Web App (2025-11-30)
- **CRITICAL FIX**: Accept endpoint now uses EXISTING escrow from prepare-accept
  - Added `verify_escrow_deposit()` function for verifying deposits to existing escrows
  - Fixed "Recipient mismatch" errors caused by creating new escrow during accept
- Admin panel buttons restored: Refund, Cancel, Export Key
- Added "Send from payout wallet" warning on deposit screens
- Fixed admin wagers crash (Wager model has no acceptor_wallet field)
- Fixed AcceptWagerRequest model (wager_id in URL path, not body)
- Creator lookup fallback for old wagers

### Coinflip Web App (2025-11-29)
- Removed all emojis from frontend (index.html, app.js)
- Separated Telegram bot to Coinflip-Telegram folder
- Web-only focus for coinflipvp.com

### VolT & FUGAZI Bots
- Treasury wallet updated to Ledger: `N7G9UdmkpsFkyzJpT74NpJ3Dghjt1iBeL4mTtwCunL3`
- Fee messages hidden from users
- All fees flowing correctly to treasury

---

**Document maintained by DoradoDevs**
*Single source of truth for all projects*
