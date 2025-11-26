# Solana Coinflip - Complete Project Context

## Project Overview

**Solana Coinflip** is a provably fair, Player-vs-Player coinflip game built on Solana blockchain. It operates on **both Web and Telegram** platforms, allowing users to create and accept coinflip wagers with 2% house fees.

### Key Decisions & Evolution

1. **Initial Request**: Build a coinflip game with both house and PVP modes
2. **Pivot**: Changed to **PVP-only** - no house games. This reduces risk and simplifies the model (just collect 2% fees from player wagers)
3. **Dual Platform**: Web app (wallet connect) + Telegram bot (custodial wallets)
4. **Provable Fairness**: Use Solana blockhash for verifiable randomness

## Technical Heritage - VolT & FUGAZI Trading Bots

This project builds on knowledge from **two previous Solana trading bots**:

### VolT Telegram Bot
- Original trading bot for $VolT token
- Features: Jupiter swaps, snipe buying, limit orders, referrals
- Located at: `/opt/volt-bot` on VPS (165.227.186.124)
- Platform fee: 1.5% (FEE_BPS = 150)

### FUGAZI Telegram Bot
- White-label fork of VolT for $FUGAZI token
- 100% rebranded version with same architecture
- Located at: `/opt/fugazi-bot` on VPS
- Platform fee: 1.5%
- CA: `CgK9rq3ysnS4z5FG7pMNNE4B3hXZ8KDQsQnXV85Lpump`
- GitHub: https://github.com/DoradoDevs/fugazi-bot

### Key Learnings Applied to Coinflip

#### 1. Solana Transaction Handling
**Critical Pattern** (from withdrawal bug fixes):

```python
async def transfer_sol(rpc_url: str, from_secret: str, to_address: str, amount_sol: float):
    kp = keypair_from_base58(from_secret)
    to_pubkey = Pubkey.from_string(to_address)
    lamports = math.floor(amount_sol * LAMPORTS_PER_SOL)

    rpc = Client(rpc_url)

    # Get fresh blockhash
    blockhash_resp = await asyncio.to_thread(rpc.get_latest_blockhash, Confirmed)
    recent_blockhash = blockhash_resp.value.blockhash

    # Create transfer instruction
    transfer_ix = transfer(TransferParams(
        from_pubkey=kp.pubkey(),
        to_pubkey=to_pubkey,
        lamports=lamports,
    ))

    # Build and sign - USE THIS PATTERN!
    tx = Transaction.new_signed_with_payer(
        [transfer_ix],
        kp.pubkey(),
        [kp],
        recent_blockhash
    )

    # Send with skip_preflight to avoid blockhash expiration
    opts = TxOpts(skip_preflight=True)
    resp = await asyncio.to_thread(rpc.send_raw_transaction, bytes(tx), opts)
    return str(resp.value)
```

**Why This Pattern?**
- `Transaction.new_signed_with_payer()` - Proper way to build transactions
- `send_raw_transaction(bytes(tx), opts)` - NOT `send_transaction(tx)`
- `skip_preflight=True` - Avoids "BlockhashNotFound" errors in simulation
- Fresh blockhash on every tx - Solana blockhashes expire in ~60 seconds

**Historical Bug Journey**:
1. First attempt: `Transaction([kp], msg)` → Missing blockhash arg error
2. Second attempt: `Transaction([kp], msg, blockhash)` → Attribute error
3. Third attempt: `Transaction.new_signed_with_payer()` → Still failed
4. Fourth attempt: `send_transaction(tx)` → Attribute error (needs bytes!)
5. **FINAL FIX**: `send_raw_transaction(bytes(tx), opts)` + `skip_preflight=True` ✅

#### 2. Database Architecture
**Pattern from trading bots** (applied to Coinflip):

```python
# SQLite-based with simple CRUD operations
class Database:
    def __init__(self, db_path: str = "database.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        # Create tables with proper indexes
        # Support for multiple users, games, transactions

    def save_user(self, user: User):
        # INSERT OR REPLACE pattern for upserts

    def get_user(self, user_id: int) -> Optional[User]:
        # Fetch with row_factory for easy dict access
```

**Key Insights**:
- Use dataclasses for models (clean, type-safe)
- SQLite is fine for moderate scale (both bots use it successfully)
- Always create indexes on foreign keys and frequently queried fields
- `INSERT OR REPLACE` for simple upserts

#### 3. Telegram Bot Structure
**Pattern** (from VolT/FUGAZI):

```python
# Main bot.py structure:
# 1. Configuration & logging
# 2. Database initialization
# 3. User session management (in-memory dict)
# 4. Command handlers (/start, /help)
# 5. Callback query router (handles all button clicks)
# 6. Conversation handlers (for multi-step flows)
# 7. Helper functions (ensure_user, formatting, etc.)

# Session management example:
user_sessions = {}

def get_session(user_id: int) -> dict:
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    return user_sessions[user_id]

# Callback routing pattern:
async def button_callback(update: Update, context):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "action1":
        await handle_action1(update, context)
    elif data.startswith("action2:"):
        param = data.split(":")[1]
        await handle_action2(update, context, param)
    # etc.
```

**Menu System**:
```python
# menus.py - Separate file for all keyboards
def main_menu() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("Option 1", callback_data="opt1")],
        [InlineKeyboardButton("Option 2", callback_data="opt2")],
    ]
    return InlineKeyboardMarkup(keyboard)
```

#### 4. Wallet Management
**Custodial Pattern** (Telegram):

```python
from utils import encrypt_secret, decrypt_secret

# Generate wallet for new user
wallet_addr, wallet_secret = generate_wallet()
encrypted_secret = encrypt_secret(wallet_secret, ENCRYPTION_KEY)

# Store encrypted secret in database
user = User(
    user_id=user_id,
    wallet_address=wallet_addr,
    encrypted_secret=encrypted_secret,
)

# Decrypt when needed for transactions
secret = decrypt_secret(user.encrypted_secret, ENCRYPTION_KEY)
```

**Encryption** (Fernet/AES-128):
```python
from cryptography.fernet import Fernet

def generate_encryption_key() -> str:
    return Fernet.generate_key().decode('utf-8')

def encrypt_secret(secret: str, key: str) -> str:
    f = Fernet(key.encode())
    return f.encrypt(secret.encode()).decode('utf-8')

def decrypt_secret(encrypted: str, key: str) -> str:
    f = Fernet(key.encode())
    return f.decrypt(encrypted.encode()).decode('utf-8')
```

#### 5. Fee Collection System
**Pattern from trading bots** (1.5% fee):

```python
# In trading bot:
FEE_BPS = 150  # 1.5%
fee_amount = total_amount * (FEE_BPS / 10000)

# Silent fee collection (not shown to user in FUGAZI)
# But tracked in backend for accounting

# In Coinflip (2% fee):
HOUSE_FEE_PCT = 0.02
total_pot = amount * 2
fee = total_pot * HOUSE_FEE_PCT
payout = total_pot - fee
```

#### 6. Environment Configuration
**.env pattern**:
```env
# Bot Token
BOT_TOKEN=your_token_here

# Solana RPC
RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_KEY

# Wallets
HOUSE_WALLET_SECRET=encrypted_secret_here
TREASURY_WALLET=public_address_here

# Security
ENCRYPTION_KEY=your_fernet_key_here

# Database
DB_PATH=database.db
```

**CRITICAL**: Always use `.env` for secrets, never hardcode!

## Coinflip Game Architecture

### Core Game Logic

#### Fair Coin Flip (Provably Fair)

```python
def flip_coin(blockhash: str, game_id: str) -> CoinSide:
    """
    Provably fair coin flip using Solana blockhash.

    Algorithm:
    1. Combine blockhash + game_id for unique seed
    2. SHA-256 hash the seed
    3. Convert first byte to integer
    4. Even = HEADS, Odd = TAILS
    """
    seed = f"{blockhash}{game_id}"
    hash_digest = hashlib.sha256(seed.encode()).hexdigest()
    first_byte = int(hash_digest[:2], 16)
    return CoinSide.HEADS if first_byte % 2 == 0 else CoinSide.TAILS
```

**Why This Is Fair:**
- Blockhash comes from Solana network (not controlled by us)
- It's unpredictable until the block is produced
- It's verifiable on-chain
- SHA-256 ensures uniform distribution
- Anyone can verify results independently

#### Game Flow (PVP)

**Create Wager:**
1. User selects side (HEADS/TAILS) and amount
2. System creates `Wager` record with status="open"
3. Wager appears in public list

**Accept Wager:**
1. Another user accepts wager
2. System creates `Game` record
3. Acceptor automatically gets opposite side
4. Game executes immediately

**Execute Game:**
1. Fetch latest Solana blockhash
2. Calculate result using `flip_coin(blockhash, game_id)`
3. Determine winner
4. Calculate payout: `(amount * 2) - 2% fee`
5. Transfer winnings to winner
6. Transfer fee to treasury
7. Update user stats
8. Save game with blockhash for verification

### Database Models

```python
@dataclass
class User:
    user_id: int                    # Telegram ID or wallet hash
    platform: str                   # "telegram" or "web"

    # Custodial (Telegram)
    wallet_address: Optional[str]
    encrypted_secret: Optional[str]

    # Non-custodial (Web)
    connected_wallet: Optional[str]

    # Stats
    games_played: int = 0
    games_won: int = 0
    total_wagered: float = 0.0
    total_won: float = 0.0
    total_lost: float = 0.0

@dataclass
class Game:
    game_id: str
    game_type: GameType             # PVP only

    player1_id: int
    player1_side: CoinSide          # HEADS or TAILS
    player1_wallet: str

    player2_id: int
    player2_side: CoinSide
    player2_wallet: str

    amount: float
    status: GameStatus              # PENDING, IN_PROGRESS, COMPLETED

    # Results
    result: Optional[CoinSide]      # Final flip result
    winner_id: Optional[int]
    blockhash: Optional[str]        # For provable fairness

    # Transactions
    payout_tx: Optional[str]
    fee_tx: Optional[str]

@dataclass
class Wager:
    wager_id: str
    creator_id: int
    creator_wallet: str
    creator_side: CoinSide
    amount: float
    status: str                     # "open", "accepted", "cancelled"

    acceptor_id: Optional[int]
    game_id: Optional[str]
```

### File Structure

```
Coinflip/
├── backend/
│   ├── bot.py                  # Telegram bot (custodial wallets)
│   ├── api.py                  # FastAPI web backend
│   ├── menus.py                # Telegram keyboards
│   │
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py           # Data models (User, Game, Wager)
│   │   └── repo.py             # Database operations (CRUD)
│   │
│   ├── game/
│   │   ├── __init__.py
│   │   ├── coinflip.py         # Core game logic, fair flip
│   │   └── solana_ops.py       # Blockchain operations
│   │
│   └── utils/
│       ├── __init__.py
│       ├── encryption.py       # Wallet encryption
│       └── formatting.py       # Display helpers
│
├── frontend/
│   ├── index.html              # Main web page
│   ├── css/
│   │   └── style.css           # Modern gaming UI
│   └── js/
│       ├── phantom.js          # Phantom wallet integration
│       └── app.js              # Main web app logic
│
├── .env                        # Configuration (SECRET!)
├── .env.example                # Template
├── .gitignore                  # Prevent secrets in git
├── requirements.txt            # Python dependencies
├── README.md                   # User documentation
└── context.md                  # THIS FILE
```

## Platform-Specific Implementation

### Telegram Bot (Custodial)

**User Flow:**
1. `/start` - Creates encrypted wallet for user
2. User deposits SOL to their bot wallet
3. User plays games (bot manages transactions)
4. User can withdraw anytime

**Key Components:**
- `bot.py` - Main bot file with all handlers
- `menus.py` - All InlineKeyboardMarkup definitions
- Session management for multi-step conversations
- Message editing for smooth UX

**Patterns:**
```python
# Ensure user exists
async def ensure_user(update: Update) -> User:
    user_id = update.effective_user.id
    user = db.get_user(user_id)

    if not user:
        # Create new user with custodial wallet
        wallet_addr, wallet_secret = generate_wallet()
        encrypted_secret = encrypt_secret(wallet_secret, ENCRYPTION_KEY)
        user = User(
            user_id=user_id,
            platform="telegram",
            wallet_address=wallet_addr,
            encrypted_secret=encrypted_secret,
        )
        db.save_user(user)

    return user

# Multi-step flow with session
session = get_session(user.user_id)
session["step"] = "choose_amount"
session["side"] = "heads"
```

### Web App (Non-Custodial)

**User Flow:**
1. Connect Phantom/Solflare wallet
2. Play directly with their wallet
3. Sign transactions in-browser
4. No deposits/withdrawals needed

**Key Components:**
- `api.py` - FastAPI backend with REST endpoints
- `phantom.js` - Wallet connection & transaction signing
- `app.js` - Game UI and state management
- WebSocket support for live updates

**Phantom Integration:**
```javascript
class PhantomWallet {
    async connect() {
        const resp = await window.solana.connect();
        this.publicKey = resp.publicKey.toString();
        return true;
    }

    async getBalance() {
        const response = await fetch(`/api/user/${this.publicKey}/balance`);
        const data = await response.json();
        return data.balance;
    }

    async signAndSendTransaction(transaction) {
        const { signature } = await this.provider.signAndSendTransaction(transaction);
        return signature;
    }
}
```

**API Endpoints:**
- `POST /api/user/connect` - Connect wallet
- `GET /api/user/{wallet}/balance` - Get SOL balance
- `POST /api/game/quick-flip` - Play game
- `GET /api/game/{game_id}` - Get game details
- `GET /api/game/verify/{game_id}` - Verify fairness
- `GET /api/wagers/open` - List open wagers
- `POST /api/wager/create` - Create wager
- `POST /api/wager/accept` - Accept wager

## Configuration & Deployment

### Environment Setup

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 4. Create .env file (copy from .env.example)
# Fill in all required values
```

### Running Locally

**Telegram Bot:**
```bash
cd backend
python bot.py
```

**Web Server:**
```bash
cd backend
python api.py
# Accessible at http://localhost:8000
```

### VPS Deployment (Telegram Bot)

**Based on VolT/FUGAZI deployment experience:**

1. **Upload code to VPS:**
```bash
scp -r Coinflip root@your-vps-ip:/opt/
```

2. **Install dependencies on VPS:**
```bash
ssh root@your-vps-ip
cd /opt/Coinflip/backend
python3 -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt
```

3. **Create systemd service:**
```bash
nano /etc/systemd/system/coinflip.service
```

```ini
[Unit]
Description=Solana Coinflip Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/Coinflip/backend
ExecStart=/opt/Coinflip/backend/venv/bin/python /opt/Coinflip/backend/bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
```

4. **Enable and start:**
```bash
systemctl daemon-reload
systemctl enable coinflip
systemctl start coinflip
systemctl status coinflip
```

5. **View logs:**
```bash
journalctl -u coinflip -f
```

**Critical Deployment Notes:**
- Use absolute paths in service file
- Set correct user (usually root on your VPS)
- Use venv Python path for ExecStart
- `PYTHONUNBUFFERED=1` for real-time logging
- Always check logs after start

## Known Issues & Solutions

### Issue 1: BlockhashNotFound Error

**Symptom:** Transactions fail with "BlockhashNotFound" error

**Cause:** Solana blockhashes expire in ~60 seconds. If preflight simulation is slow, the blockhash becomes stale.

**Solution:**
```python
opts = TxOpts(skip_preflight=True)
resp = await client.send_raw_transaction(bytes(tx), opts)
```

**Why it works:** Skips the simulation step that checks blockhash validity. The actual transaction execution is fast enough.

### Issue 2: Transaction Object Attribute Errors

**Symptom:** `'Transaction' object has no attribute 'recent_blockhash'`

**Cause:** Wrong transaction construction method

**Solution:** Use `Transaction.new_signed_with_payer()`:
```python
tx = Transaction.new_signed_with_payer(
    [transfer_ix],
    kp.pubkey(),
    [kp],
    recent_blockhash
)
```

### Issue 3: send_transaction vs send_raw_transaction

**Symptom:** Type errors when calling `send_transaction(tx)`

**Cause:** RPC client expects raw bytes, not Transaction object

**Solution:**
```python
# WRONG:
resp = await client.send_transaction(tx)

# CORRECT:
resp = await client.send_raw_transaction(bytes(tx), opts)
```

### Issue 4: Systemd Service Fails to Start

**Symptom:** `status=217/USER` or path errors

**Cause:** Incorrect paths or user in service file

**Solution:**
- Use absolute paths everywhere
- Verify user exists (`root` on your VPS)
- Verify Python path points to venv
- Check WorkingDirectory exists

## Dependencies

### Python Packages
```
python-telegram-bot==21.6    # Telegram bot framework
solana==0.34.3               # Solana Python SDK
solders==0.21.0              # Rust-based Solana types
base58==2.1.1                # Base58 encoding
fastapi==0.115.5             # Web framework
uvicorn[standard]==0.32.1    # ASGI server
websockets==14.1             # WebSocket support
cryptography==44.0.0         # Fernet encryption
python-dotenv==1.0.1         # .env file loading
pydantic==2.10.3             # Data validation
```

### Frontend (CDN-based)
- Solana web3.js (loaded via CDN in production)
- Phantom wallet adapter

## Security Best Practices

### 1. Environment Variables
- **NEVER** commit `.env` to git
- Use `.env.example` as template
- Store production secrets securely (not in code repo)

### 2. Wallet Encryption
- All custodial wallet secrets encrypted with Fernet
- Encryption key must be strong and unique
- Never log decrypted secrets

### 3. Transaction Validation
- Always validate amounts > 0
- Check user balance before transactions
- Verify transaction signatures on-chain

### 4. API Security
- Add rate limiting in production
- Validate all user inputs
- Use HTTPS in production
- Implement CORS properly

### 5. Database
- Use parameterized queries (SQLite protects against SQL injection)
- Back up database regularly
- Consider encryption at rest for production

## Future Enhancements

### Short Term
- [ ] Complete PVP wager creation flow
- [ ] Add wager acceptance flow
- [ ] Implement wager expiration
- [ ] Add game history viewer
- [ ] Mobile-responsive web UI

### Medium Term
- [ ] Leaderboards (top winners, most games, etc.)
- [ ] Achievements/badges system
- [ ] Referral system (25% of fees, like trading bots)
- [ ] Multi-token support (not just SOL)
- [ ] Tournament mode

### Long Term
- [ ] Smart contract for fully decentralized PVP
- [ ] NFT integration (custom coins, rewards)
- [ ] DAO governance for fee distribution
- [ ] Cross-chain support

## Development Tips

### Testing Locally

**Test coin flip fairness:**
```python
from game.coinflip import flip_coin
import hashlib

blockhash = "test_blockhash"
game_id = "test_game_123"

# Run multiple times, should get ~50/50 distribution
results = [flip_coin(blockhash, f"{game_id}_{i}") for i in range(1000)]
heads = sum(1 for r in results if r == CoinSide.HEADS)
print(f"HEADS: {heads/10}%, TAILS: {(1000-heads)/10}%")
```

**Test Solana connection:**
```python
from game.solana_ops import get_latest_blockhash
import asyncio

async def test():
    blockhash = await get_latest_blockhash("YOUR_RPC_URL")
    print(f"Latest blockhash: {blockhash}")

asyncio.run(test())
```

**Test wallet generation:**
```python
from game.solana_ops import generate_wallet

pubkey, secret = generate_wallet()
print(f"Public: {pubkey}")
print(f"Secret: {secret[:10]}... (hidden)")
```

### Debugging

**Telegram Bot:**
- Check logs: `journalctl -u coinflip -f`
- Test locally first before deploying
- Use `logger.info()` extensively
- Test with `/start` and `/help` commands

**Web App:**
- Use browser console for JavaScript errors
- Check Network tab for API calls
- Test Phantom connection on devnet first
- Use `console.log()` in frontend

**Database:**
- Use DB Browser for SQLite to inspect data
- Check table schemas match models
- Verify indexes are created

## Common Patterns

### Async/Await Pattern
```python
# Always use async for I/O operations
async def do_something():
    # For sync operations in async context:
    result = await asyncio.to_thread(sync_function, args)

    # For async operations:
    result = await async_function(args)
```

### Error Handling
```python
try:
    result = await risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    # Handle gracefully, don't crash
    return None  # or appropriate fallback
```

### User Session Management
```python
# Store temporary state per user
session = get_session(user_id)
session["step"] = "waiting_for_amount"
session["data"] = some_value

# Later retrieve:
if session.get("step") == "waiting_for_amount":
    amount = message.text
    # Process...
```

## FAQs

**Q: Why PVP only, no house games?**
A: Reduces risk. We just collect 2% fees from player wagers. No house funds at risk.

**Q: How do we profit?**
A: 2% fee on every game. Example: 10 SOL wagered per day = 0.2 SOL daily profit.

**Q: Is this actually fair?**
A: Yes! Blockhash from Solana is unpredictable and verifiable. Anyone can verify results.

**Q: Why both Web and Telegram?**
A: Reach more users. Some prefer Telegram convenience, others want wallet control.

**Q: What about gas fees?**
A: Solana transactions are ~0.000005 SOL (negligible). Included in our costs.

**Q: Can users cheat?**
A: No. Blockhash is determined by Solana network after wager is accepted. Results are deterministic from blockhash.

## Support & Resources

### Related Projects
- **VolT Bot**: Trading bot template (located at `/opt/volt-bot`)
- **FUGAZI Bot**: Trading bot fork (https://github.com/DoradoDevs/fugazi-bot)

### Documentation
- Solana: https://docs.solana.com
- python-telegram-bot: https://docs.python-telegram-bot.org
- FastAPI: https://fastapi.tiangolo.com
- Phantom Wallet: https://docs.phantom.app

### Tools
- Solana Explorer: https://solscan.io
- Helius RPC: https://helius.dev
- Telegram BotFather: @BotFather

---

## Summary for Future Sessions

**If you're a new Claude instance reading this:**

This is a **Solana blockchain coinflip game** with two platforms (Web + Telegram). It uses **provably fair randomness** from Solana blockhash. The architecture is based on experience from **VolT and FUGAZI trading bots**, particularly:

1. **Solana transaction handling** - Use `Transaction.new_signed_with_payer()` and `send_raw_transaction()` with `skip_preflight=True`
2. **Database patterns** - SQLite with dataclasses, simple CRUD
3. **Telegram bot structure** - Command handlers, callback routers, menu system
4. **Wallet management** - Fernet encryption for custodial wallets
5. **Fee collection** - 2% on all games, sent to treasury

**Current status:** Core architecture complete. PVP wager system partially implemented. Both Telegram and Web frameworks in place.

**Next steps:** Complete wager creation/acceptance flows, add live wager list, test end-to-end gameplay.

**Key files to know:**
- `backend/bot.py` - Telegram bot
- `backend/api.py` - Web API
- `backend/game/coinflip.py` - Core game logic
- `frontend/js/app.js` - Web app
- This file (`context.md`) - Complete knowledge base

**Deployment:** VPS at 165.227.186.124 (where VolT and FUGAZI bots run). Use systemd service pattern from those bots.

Good luck! 🎲
