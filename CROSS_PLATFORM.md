# Cross-Platform Architecture

## Overview

The Solana Coinflip game supports **full cross-platform gameplay** between Telegram and Web users. Wagers created on either platform can be accepted by users on any platform.

## How It Works

### Shared Database Layer

Both platforms use the same SQLite database (`coinflip.db`):

```
┌─────────────────┐
│  Telegram Bot   │────┐
└─────────────────┘    │
                       ├──► SQLite Database
┌─────────────────┐    │
│    Web API      │────┘
└─────────────────┘
```

**Tables:**
- `users` - All users (Telegram + Web)
- `games` - All completed games
- `wagers` - All open/accepted/cancelled wagers

### Platform Identification

Users are identified by their platform:

**Telegram Users:**
```python
User(
    user_id=123456789,          # Telegram user ID
    platform="telegram",
    wallet_address="ABC...xyz",  # Custodial wallet
    encrypted_secret="..."       # Encrypted private key
)
```

**Web Users:**
```python
User(
    user_id=9876543210,         # Hash of wallet address
    platform="web",
    connected_wallet="XYZ...abc" # User's Phantom/Solflare wallet
)
```

## Cross-Platform Scenarios

### 1. Telegram Creates → Web Accepts ✅

1. **Telegram user creates wager:**
   - Bot calls `execute_create_wager()`
   - Saves wager with `creator_wallet` = Telegram custodial wallet
   - Wager appears in database as "open"

2. **Web user sees wager:**
   - `GET /api/wagers/open` returns all open wagers
   - Wager shows in Web UI

3. **Web user accepts:**
   - `POST /api/wager/accept` with acceptor wallet
   - Game executes, winner determined
   - Telegram creator gets **push notification** via bot

### 2. Web Creates → Telegram Accepts ✅

1. **Web user creates wager:**
   - `POST /api/wager/create` with connected wallet
   - Saves wager with `creator_wallet` = user's wallet address
   - Broadcasts to WebSocket clients

2. **Telegram user sees wager:**
   - Bot shows "Open Wagers" menu
   - Fetches from same database

3. **Telegram user accepts:**
   - Bot calls `accept_wager()`
   - Game executes, winner determined
   - Web creator sees update via **WebSocket** (if connected)

### 3. Telegram ↔ Telegram ✅

- Both users use custodial wallets
- Bot handles all transactions
- Push notifications for both users

### 4. Web ↔ Web ✅

- Both users use connected wallets
- Transactions via Phantom/Solflare
- WebSocket updates for real-time UI

## Notification System

### Telegram Notifications (Push)

Telegram uses **native push notifications** via the bot:

```python
# When wager is accepted
await context.bot.send_message(
    chat_id=creator.user_id,
    text="🔔 Your wager was accepted! ..."
)
```

**Advantages:**
- Instant delivery
- Works even if user not in app
- No polling needed

### Web Notifications (WebSocket)

Web uses **WebSocket** for live updates:

```javascript
// Client connects to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws');

// Receives updates
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'wager_accepted') {
    // Update UI in real-time
  }
};
```

**Broadcast Events:**
- `wager_created` - New wager available
- `wager_accepted` - Wager was accepted
- `wager_cancelled` - Wager was cancelled

### Cross-Platform Notifications ✅

The notification system automatically detects platform:

```python
# In Web API when wager is accepted
if creator.platform == "telegram":
    # Send Telegram push notification
    await notify_wager_accepted(creator.user_id, amount, won, payout)
else:
    # Web users get WebSocket update automatically
    await manager.broadcast({...})
```

## API Endpoints (Web)

### Complete REST API

```
# User Management
POST /api/user/connect              - Connect wallet
GET  /api/user/{wallet}             - Get user stats
GET  /api/user/{wallet}/balance     - Get SOL balance

# Games
POST /api/game/quick-flip           - Play vs house
GET  /api/game/{game_id}            - Get game details
GET  /api/game/verify/{game_id}     - Verify fairness

# PVP Wagers
POST /api/wager/create              - Create wager ✅
GET  /api/wagers/open               - List open wagers ✅
POST /api/wager/accept              - Accept wager ✅
POST /api/wager/cancel              - Cancel wager ✅

# WebSocket
WS   /ws                            - Live updates
```

## Telegram Commands

### Complete Bot Interface

```
/start              - Start bot & create wallet
/help               - Show help

Main Menu:
- 🎲 Quick Flip         - Play vs house ✅
- ⚔️ Create Wager       - Create PVP wager ✅
- 🎯 Open Wagers        - View all open wagers ✅
- 💰 Wallet             - Deposit/withdraw ✅
- 📊 Stats              - View statistics ✅
- 🎮 My Wagers          - View your wagers ✅
- 📜 History            - Game history ✅
```

## Wallet Types

### Telegram: Custodial Wallets

**Pros:**
- User-friendly (no wallet setup)
- Fast transactions (bot signs)
- Deposit/withdraw anytime

**Cons:**
- Trust required (bot holds keys)
- Encryption critical

**Implementation:**
```python
# Create wallet for new user
wallet_addr, wallet_secret = generate_wallet()
encrypted = encrypt_secret(wallet_secret, ENCRYPTION_KEY)

# Store encrypted secret
user = User(
    wallet_address=wallet_addr,
    encrypted_secret=encrypted
)
```

### Web: Non-Custodial (Phantom/Solflare)

**Pros:**
- User controls keys
- No trust required
- Direct on-chain

**Cons:**
- Requires wallet setup
- User signs each transaction

**Implementation:**
```javascript
// Connect wallet
const provider = window.solana;
await provider.connect();
const wallet = provider.publicKey.toString();

// Sign transaction
const signature = await provider.signAndSendTransaction(tx);
```

## Transaction Flow

### PVP Game Execution

```
1. Wager Created
   ├─ Check balance
   ├─ Save to database
   └─ Status: "open"

2. Wager Accepted
   ├─ Validate acceptor balance
   ├─ Get Solana blockhash
   ├─ Flip coin (provably fair)
   ├─ Calculate winner
   ├─ Transfer payout (amount * 2 - 2% fee)
   ├─ Transfer fee to treasury
   ├─ Update stats
   ├─ Save game record
   └─ Notify users

3. Notifications Sent
   ├─ Telegram: Push notification
   ├─ Web: WebSocket broadcast
   └─ Both platforms updated
```

## Testing Cross-Platform

### Setup Both Platforms

**Terminal 1: Telegram Bot**
```bash
cd backend
python bot.py
```

**Terminal 2: Web API**
```bash
cd backend
python api.py
```

### Test Scenarios

**Scenario 1: Telegram → Web**
1. On Telegram: Create wager (0.05 SOL, HEADS)
2. On Web: Open http://localhost:8000/api/wagers/open
3. Verify wager appears in JSON response
4. Accept via Web API or UI
5. Check Telegram gets push notification

**Scenario 2: Web → Telegram**
1. On Web: Create wager via API
2. On Telegram: View "Open Wagers"
3. Accept wager from Telegram
4. Check WebSocket update on Web

**Scenario 3: Check Stats**
- Both platforms should show same user stats
- Database is single source of truth

## Database Queries

Both platforms use the same database methods:

```python
# Get all open wagers (any platform)
wagers = db.get_open_wagers(limit=20)

# Get user (works for both platforms)
user = db.get_user(user_id)

# Get game history
games = db.get_user_games(user_id, limit=10)
```

## Security Considerations

### Telegram (Custodial)

**Encryption:**
- All wallet secrets encrypted with Fernet
- Encryption key in `.env` (never commit)
- Keys only decrypted for transactions

**Risks:**
- Bot compromise = wallet compromise
- Mitigation: Secure server, limited bot permissions

### Web (Non-Custodial)

**User Responsibility:**
- User signs all transactions
- User manages private keys
- No server-side secrets

**Risks:**
- Phishing attacks
- Malicious frontends
- Mitigation: Verify URLs, use known wallets

## Future Enhancements

### Planned Features

**Notifications:**
- [ ] Email notifications for Web users
- [ ] Discord webhook integration
- [ ] SMS notifications (optional)

**Cross-Platform:**
- [ ] Unified leaderboard (both platforms)
- [ ] Cross-platform referrals
- [ ] Shared tournaments

**Technical:**
- [ ] Redis for session management
- [ ] PostgreSQL for better scalability
- [ ] GraphQL for flexible queries

## Architecture Diagram

```
┌──────────────────────────────────────────────────────┐
│                  Users (Both Platforms)               │
└──────────────────────────────────────────────────────┘
            │                              │
            │                              │
     ┌──────▼─────┐                 ┌─────▼──────┐
     │  Telegram  │                 │  Web App   │
     │    Bot     │                 │  (Browser) │
     └──────┬─────┘                 └─────┬──────┘
            │                              │
            │  Python-Telegram-Bot         │  Phantom/Solflare
            │                              │
     ┌──────▼──────────────────────────────▼──────┐
     │          Backend (FastAPI + Bot)           │
     │                                             │
     │  ┌─────────────┐      ┌─────────────┐     │
     │  │   bot.py    │      │   api.py    │     │
     │  │ (Telegram)  │      │   (Web)     │     │
     │  └──────┬──────┘      └──────┬──────┘     │
     │         │                     │            │
     │         │   ┌─────────────┐   │            │
     │         └──►│  Database   │◄──┘            │
     │             │ (SQLite)    │                │
     │             └──────┬──────┘                │
     │                    │                        │
     │         ┌──────────▼──────────┐            │
     │         │   Shared Services   │            │
     │         │ - game/coinflip.py  │            │
     │         │ - game/solana_ops.py│            │
     │         │ - notifications.py  │            │
     │         └─────────────────────┘            │
     └─────────────────────────────────────────────┘
                         │
                         │
                  ┌──────▼──────┐
                  │   Solana    │
                  │  Blockchain │
                  └─────────────┘
```

## Summary

✅ **Full cross-platform support**
✅ **Shared database architecture**
✅ **Platform-specific notifications**
✅ **Consistent game logic**
✅ **Secure wallet handling**

Users on Telegram and Web can **seamlessly play together** with real-time notifications and updates!

---

**Start both platforms and test live!** 🚀
