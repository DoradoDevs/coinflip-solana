# DoradoDevs Master Knowledge Document
**Last Updated:** 2025-11-30
**Status:** Production - All Systems Operational

---

## Table of Contents
1. [Project Portfolio](#project-portfolio)
2. [Infrastructure & Servers](#infrastructure--servers)
3. [Coinflip Web App](#coinflip-web-app)
4. [VoLT Web Platform](#volt-web-platform-volume-terminal)
5. [VolT Telegram Trading Bot](#volt-telegram-trading-bot)
6. [FUGAZI Trading Bot](#fugazi-trading-bot)
7. [Fee Structure Summary](#fee-structure-summary)
8. [Technical Patterns & Best Practices](#technical-patterns--best-practices)
9. [Deployment Guide](#deployment-guide)
10. [Wallets & Treasury](#wallets--treasury)

---

## Project Portfolio

### Active Projects

| Project | Type | Status | Location |
|---------|------|--------|----------|
| **Coinflip** | PVP Wager Web App | Production | coinflipvp.com |
| **Coinflip-Telegram** | Telegram Bot | Development | Desktop folder |
| **VoLT Web Platform** | Volume Trading Web App | Production | volumeterminal.com |
| **VolT Bot** | Telegram Trading Bot | Production | 165.227.186.124 |
| **FUGAZI Bot** | Trading Bot (White-label) | Production | 165.227.186.124 |

### Repository Structure
```
Desktop/
├── Coinflip/                 # Web app (coinflipvp.com)
├── Coinflip-Telegram/        # Telegram bot (separate project)
├── volt/volt/                # VoLT Web Platform (volumeterminal.com)
├── volt-bot-main/            # VolT Telegram Trading Bot source
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

### Web Apps Server (Coinflip + VoLT)
- **IP:** 157.245.13.24
- **Provider:** DigitalOcean
- **OS:** Ubuntu
- **Domains:**
  - `coinflipvp.com` - Coinflip frontend (served from `/var/www/html`)
  - `api.coinflipvp.com` - Coinflip API (port 8000, `/opt/coinflip`)
  - `volumeterminal.com` - VoLT frontend (port 8080 via Docker)
  - VoLT API runs on port 5000 via Docker
- **Running Services:**
  - `coinflip.service` - FastAPI backend (systemd)
  - VoLT containers via Docker Compose (`/home/volt/volt/`)
- **Nginx**: Reverse proxy for all domains (ports 80/443)

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
GET  /api/wagers/open                  - List open wagers (includes is_accepting state)
POST /api/wager/create                 - Create new wager (returns escrow address)
POST /api/wager/{id}/verify-deposit    - Verify creator deposit → status: open
POST /api/wager/{id}/prepare-accept    - Create acceptor escrow, set accepting state
POST /api/wager/{id}/abandon-accept    - Clear accepting state (user closed modal)
POST /api/wager/{id}/accept            - Verify acceptor deposit & execute flip
POST /api/wager/cancel                 - Cancel open wager (creator only, refunds deposit)
GET  /api/games/recent                 - Recent completed games with proof + winner_username

# Admin Endpoints
GET  /api/admin/wagers                 - List all wagers with balances
POST /api/admin/wager/{id}/refund      - Refund escrow to payout wallet
POST /api/admin/wager/{id}/cancel      - Mark wager as cancelled
POST /api/admin/wager/{id}/export-key  - Export escrow private key
GET  /api/admin/maintenance            - Check maintenance mode status
POST /api/admin/maintenance/toggle     - Enable/disable all betting (EMERGENCY_STOP file)
POST /api/admin/sweep-escrows          - Sweep all escrow funds to treasury
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

## VoLT Web Platform (Volume Terminal)

### Overview
Professional-grade Solana volume trading automation web platform. Enables users to generate trading activity for tokens through multi-wallet management, automated trading bots, and scheduled campaigns.

**Live URL:** https://volumeterminal.com
**Server:** 157.245.13.24 (`/home/volt/volt/`)
**Deployment:** Docker Compose

### Architecture
```
volt/volt/
├── frontend/                 # React 18 app
│   ├── src/
│   │   ├── App.js           # Main router
│   │   ├── Dashboard.js     # 7-tab interface
│   │   ├── BotControls.js   # Volume bot controls
│   │   ├── WalletManager.js # Multi-wallet UI
│   │   ├── FundsManager.js  # Deposit/withdraw/distribute
│   │   ├── CampaignManager.js # GOD MODE campaigns
│   │   └── LaunchManagerNew.js # Token launches
│   └── build/               # Production build
├── backend/
│   ├── src/
│   │   ├── server.js        # Express app + background services
│   │   ├── controllers/
│   │   │   ├── auth.js      # Signup, login, JWT
│   │   │   └── dashboard.js # All user operations
│   │   ├── services/
│   │   │   ├── solana.js    # Swaps, encryption, RPC management
│   │   │   ├── bot.js       # Volume bot execution
│   │   │   ├── pumpfun.js   # Token creation
│   │   │   ├── campaignExecutor.js  # Background campaign runner
│   │   │   └── schedulerEngine.js   # Campaign scheduler
│   │   ├── models/          # MongoDB schemas
│   │   └── middleware/      # Auth, rate limiting, validation
│   └── scripts/
│       └── migrate-encryption.js  # Key re-encryption tool
└── docker-compose.yml       # Production config (GITIGNORED)
```

### Core Features

**1. Multi-Wallet Management**
- Auto-generate Solana wallets (5-100 based on tier)
- All private keys encrypted with AES-256
- Distribute/consolidate funds across wallets
- Tier-based wallet limits

**2. Volume Bot**
Automated buy/sell trading with four modes:
| Mode | Behavior |
|------|----------|
| Pure | Buy → Sell immediately (wash trading) |
| Growth | Buy → Sell 90%, keep 10% |
| Moonshot | Buy only (accumulation) |
| Human | Random patterns (evade detection) |

**3. Campaign System (GOD MODE)**
- Schedule multi-stage trading campaigns
- Auto-stop conditions (time, volume target, SOL depleted)
- Active trading hours configuration
- Wallet role assignment (buyer/seller/both)

**4. Token Launch (Pump.fun Integration)**
- Create token drafts with metadata
- Upload images to IPFS
- Deploy directly to Pump.fun
- Post-launch volume workflows

**5. Referral & Rewards System**
- 4-level deep referral tracking
- Tier-based fee discounts (10%-50%)
- Tiers: Unranked → Bronze → Silver → Gold → Diamond

### Fee Structure
- **Inbound Fee:** 0.3% on trades (tier discounts apply)
- **Outbound Fee:** 0.25% on withdrawals
- **Fee Wallet:** `71thc93yHSqQGFhg8s95YdxbcbLksqM6b7e7ERm46Wht`
- **Rewards Wallet:** `3U21AaoVePq3DqZPpTUuSf74cSrWkCZVdcD18rsVRCdk`

### Tier System
| Tier | Min Volume | Fee Discount | Max Wallets |
|------|-----------|-------------|-------------|
| Unranked | 0 SOL | 0% | 5 |
| Bronze | 100 SOL | 10% | 15 |
| Silver | 250 SOL | 20% | 30 |
| Gold | 500 SOL | 30% | 50 |
| Diamond | 1000 SOL | 50% | 100 |

### API Endpoints
```
# Authentication
POST /signup              - Create account (auto-gen wallet)
POST /login               - Get JWT token

# Wallets
GET  /wallets/list        - List all wallets
POST /wallets/add-one     - Generate new wallet
POST /wallets/active      - Set active wallets
GET  /wallets/deposit-address  - Get source wallet

# Funds
POST /funds/distribute    - Split to sub-wallets
POST /funds/consolidate   - Collect from sub-wallets
POST /funds/sell-all      - Liquidate token holdings

# Bot
POST /bot/start           - Start volume bot
POST /bot/stop            - Stop bot
GET  /bot/status          - Get status
POST /settings/update     - Update bot config

# Campaigns (GOD MODE)
GET  /campaigns           - List campaigns
POST /campaigns           - Create campaign
POST /campaigns/:id/start - Start campaign
POST /campaigns/:id/stop  - Stop campaign

# Token Launch
POST /draft-launches      - Create draft
POST /draft-launches/:id/deploy  - Deploy to Pump.fun
```

### Security
- JWT authentication (30-day expiry)
- AES-256 encryption for all private keys
- bcrypt password hashing
- Rate limiting (5 limiters)
- Joi input validation

### Docker Deployment
```bash
# On server (157.245.13.24)
cd /home/volt/volt
docker-compose up -d

# Containers:
# - volt-frontend (port 8080:80)
# - volt-backend (port 5000:5000)
```

### Environment Variables (docker-compose.yml)
```env
MONGO_URI=mongodb+srv://...
JWT_SECRET=<secret>
ENCRYPTION_SECRET=<secret>
SOLANA_RPC=https://mainnet.helius-rpc.com/?api-key=...
FEE_WALLET=71thc93yHSqQGFhg8s95YdxbcbLksqM6b7e7ERm46Wht
REWARDS_WALLET_ADDRESS=3U21AaoVePq3DqZPpTUuSf74cSrWkCZVdcD18rsVRCdk
REWARDS_PRIVATE_KEY=<base58>
```

### Key Technical Notes
- **Swap Engine:** Jupiter Aggregator for optimal routing
- **RPC:** Helius with failover to backup RPCs
- **Database:** MongoDB Atlas
- **Encryption:** CryptoJS AES-256 (different from Coinflip's Fernet)
- **Background Services:** 3 engines run on startup (scheduler, campaign executor, workflow executor)

### Update Procedure
```bash
# From local machine
cd volt/volt
git add . && git commit -m "update" && git push

# On server
ssh root@157.245.13.24 "cd /home/volt/volt && git pull && docker-compose up -d --build"
```

---

## VolT Telegram Trading Bot

### Overview
Professional Solana trading/sniper bot for Telegram with advanced features.

**Note:** This is a DIFFERENT project from VoLT Web Platform above. Same name, different products.

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
| **VoLT Web Platform** | 0.3% inbound, 0.25% outbound | 4-level (10-25%) | Gas only |
| **VolT Telegram Bot** | 1.0% | 25% | Gas only |
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
VolT Telegram Bot Fees ────┼──► Treasury Wallet (Ledger)
                           │    N7G9UdmkpsFkyzJpT74NpJ3Dghjt1iBeL4mTtwCunL3
FUGAZI Trading Fees ───────┘

VoLT Web Platform Fees ────────► VoLT Fee Wallet
                                 71thc93yHSqQGFhg8s95YdxbcbLksqM6b7e7ERm46Wht
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

# VoLT Web Platform (Docker)
ssh root@157.245.13.24 "cd /home/volt/volt && git pull && docker-compose up -d --build"

# VolT Telegram Bot
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

**"AttributeError: 'Wager' object has no attribute 'id'"**
- **Cause**: Using `wager.id` instead of `wager.wager_id`
- **Fix**: Wager model uses `wager_id` field, not `id`
- **Files**: Check api.py for any `wager.id` references

**"insufficient lamports" during fee collection**
- **Cause**: RPC returns stale balance after payout transaction
- **Fix**: Delay increased to 10s + 3 retries in `collect_fees_from_escrow()`

**Solscan link shows "Unable to locate"**
- **Cause**: Using blockhash instead of transaction signature
- **Fix**: Use `payout_tx` field for Solscan links, not `proof.blockhash`

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
- **Maintenance Mode**: Toggle button to disable all betting (creates/removes EMERGENCY_STOP file)
- **Sweep All Escrows**: Collects all leftover funds from escrow wallets to treasury

### Solana RPC Sync Issues
**Problem**: After payout, RPC may return stale balance data causing "insufficient lamports" errors when collecting fees.

**Solution** (in `collect_fees_from_escrow()`):
1. Wait 10 seconds after payout for chain finality
2. Retry up to 3 times with 5-second delays between attempts
3. Leave rent-exempt minimum (~0.00089 SOL) as dust

**Manual Recovery**: Use "Sweep All Escrows" button in admin panel to collect any leftover funds periodically.

### Frontend Deployment Gotchas
**Browser Cache**: After frontend updates, users may see old JavaScript. Solutions:
- Hard refresh: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)
- Clear browser cache
- Wait for cache expiry

**Two-Directory Setup**: Remember Coinflip server has TWO locations:
- `/opt/coinflip` - Git repo (source code)
- `/var/www/html` - Nginx serves frontend from here
- **Must copy**: `cp -r frontend/* /var/www/html/` after `git pull`

**Quick Deploy Command** (backend + frontend):
```bash
ssh root@157.245.13.24 "cd /opt/coinflip && git pull && cp -r frontend/* /var/www/html/ && systemctl restart coinflip"
```

---

## Recent Changes (2025-11-29 & 2025-11-30)

### Coinflip Web App (2025-11-30) - Session 3
- **Cancel Button for Open Wagers**:
  - Creator sees red "Cancel" button on their own wagers
  - Clicking Cancel refunds wager amount (minus 0.025 SOL fee) to creator's wallet
  - Added `cancelWager()` function in frontend
  - Added `btn-danger` CSS style for cancel button
- **Accepting State Tracking** (prevents cancel during accept):
  - Added `accepting_at` timestamp and `acceptor_wallet` to Wager model
  - `prepare-accept` sets these fields and broadcasts `wager_accepting` event
  - Open wagers show "Being Accepted..." when someone is accepting
  - 60-second timeout auto-clears stale accepting state
  - `abandon-accept` endpoint clears state when user closes modal (3s delay)
  - Cancel blocked while wager is being accepted
- **New API Endpoints**:
  - `POST /api/wager/{id}/abandon-accept` - Clear accepting state
  - WagerResponse now includes `is_accepting` and `accepting_by` fields
- **Support Form Requires Login**:
  - General support/bug reports: Must be logged in, shows username + email from account (readonly)
  - Password reset: Just asks for account email (no login needed - they forgot password)
  - Admin always sees real user info linked to registered accounts

### Coinflip Web App (2025-11-30) - Session 2
- **Username Display Fixes**:
  - Added `get_user_by_wallet()` to database for username fallback lookup
  - Open wagers now show usernames (with wallet fallback if no username)
  - Recent games show `winner_username` field (with wallet fallback)
- **Solscan Link Fix**: "View on Solscan" now uses actual `payout_tx` signature instead of `proof.blockhash`
  - Fixed `showProofModal()` to receive `payoutTx` parameter
- **Admin Maintenance Mode**:
  - `GET/POST /api/admin/maintenance` - Check/toggle maintenance status
  - Uses `EMERGENCY_STOP` file to disable all betting
  - Button in admin.html shows current status
- **Admin Sweep All Escrows**:
  - `POST /api/admin/sweep-escrows` - Sweeps all escrow wallets to treasury
  - Fixed bug: `wager.id` → `wager.wager_id` (Wager model uses wager_id)
- **Fee Collection Delay**: Increased from 5s to 10s for better Solana RPC sync
  - `collect_fees_from_escrow()` now waits 10 seconds before checking balance
  - Prevents "insufficient lamports" errors from stale RPC data

### Coinflip Web App (2025-11-30) - Session 1
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
