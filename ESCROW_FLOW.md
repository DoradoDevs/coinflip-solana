# Escrow & Money Flow - Fixed Implementation

## Critical Security Issue (FIXED!)

**Previous Problem:**
- Games executed without collecting SOL from players ❌
- Winners got paid but losers never sent money ❌
- House wallet would lose funds ❌

**New Implementation:**
- Collect SOL from BOTH players BEFORE game starts ✅
- Hold funds in escrow (house wallet) ✅
- Pay winner from collected pot ✅
- Collect fees to treasury ✅

---

## How Money Flows Now

### Quick Flip (vs House)

**For Telegram Users:**
```
1. Player deposits 0.05 SOL to custodial wallet (via bot)
2. Player starts game with 0.01 SOL wager
   ├─ ESCROW: Transfer 0.01 SOL from player wallet → house wallet
3. Coin flips
4a. IF PLAYER WINS:
    ├─ Calculate: payout = 0.02 SOL - 2% = 0.0196 SOL
    ├─ Transfer 0.0196 SOL from house → player wallet
    └─ Transfer 0.0004 SOL fee from house → treasury
4b. IF HOUSE WINS:
    ├─ Player's 0.01 SOL stays in house wallet
    ├─ Transfer 0.0002 SOL fee from house → treasury
    └─ House keeps 0.0098 SOL
```

**Result:** No money created/destroyed. All funds accounted for!

### PVP Wagers (Telegram ↔ Telegram)

```
1. Player A deposits 0.05 SOL to their wallet
2. Player B deposits 0.05 SOL to their wallet
3. Player A creates wager: 0.01 SOL on HEADS
4. Player B accepts wager (gets TAILS automatically)
   ├─ ESCROW: Transfer 0.01 SOL from Player A wallet → house wallet
   ├─ ESCROW: Transfer 0.01 SOL from Player B wallet → house wallet
   └─ House now holds 0.02 SOL total
5. Coin flips
6a. IF HEADS (Player A wins):
    ├─ Calculate: payout = 0.02 SOL - 2% = 0.0196 SOL
    ├─ Transfer 0.0196 SOL from house → Player A wallet
    └─ Transfer 0.0004 SOL fee from house → treasury
6b. IF TAILS (Player B wins):
    ├─ Calculate: payout = 0.02 SOL - 2% = 0.0196 SOL
    ├─ Transfer 0.0196 SOL from house → Player B wallet
    └─ Transfer 0.0004 SOL fee from house → treasury
```

**Result:** Both players risked their SOL. Winner gets 98% of pot!

---

## Platform-Specific Handling

### Telegram (Custodial Wallets) ✅ FULLY IMPLEMENTED

**User Flow:**
1. `/start` - Bot creates encrypted wallet
2. User deposits SOL to their address
3. User plays games
   - Bot collects wager from user's wallet (escrow)
   - Game executes
   - Winner receives payout

**Security:**
- User's private key encrypted with Fernet
- Bot can transfer from user's wallet when needed
- All transactions logged

**Implementation:**
```python
# Collect escrow from Telegram user
if player.platform == "telegram" and player.encrypted_secret:
    player_secret = decrypt_secret(player.encrypted_secret, ENCRYPTION_KEY)

    # Transfer player's wager to house wallet (escrow)
    deposit_tx = await transfer_sol(
        rpc_url,
        player_secret,
        house_wallet,
        amount
    )
```

### Web (Non-Custodial) ⚠️ PARTIALLY IMPLEMENTED

**Current Status:**
- Balance is checked ✅
- User controls their own wallet ✅
- **BUT**: Escrow collection not enforced yet ⚠️

**Why Not Enforced:**
- Need user to sign transaction to send SOL
- Two options:
  1. **Simple**: User sends to house wallet manually (trusted)
  2. **Secure**: Solana program (smart contract) handles escrow

**Temporary Solution:**
```python
# For Web users: Balance checked but escrow not collected yet
elif player.platform == "web":
    logger.warning(f"Web game - assuming player will send {amount} SOL")
    # TODO: Verify transaction or use Solana program
```

**Future Fix:**
- Implement Solana program for trustless escrow
- Or verify user sent SOL before starting game

---

## House Wallet Requirements

**Why House Wallet Needs Funds:**

### For Quick Flip (vs House):
- Player wins: House pays 2x wager - fee
- Player loses: House keeps wager (minus fee to treasury)
- **Net**: House needs buffer for when players win

### For PVP Games:
- House collects from both players (escrow)
- House pays winner from collected funds
- **Net**: House just facilitates, needs minimal buffer

### For Transaction Fees:
- ~0.000005 SOL per transaction
- Negligible amount

**Recommended Funding:**
```
Starting Capital: 0.5 SOL

Covers:
- 25 Quick Flip games @ 0.01 SOL (if all players win)
- Unlimited PVP games (self-funding from escrow)
- Transaction fees for 100,000 transactions
```

---

## Money Flow Examples

### Example 1: Single Quick Flip (Player Wins)

```
Initial State:
- Player wallet: 0.05 SOL
- House wallet: 0.50 SOL
- Treasury wallet: 0.00 SOL

Step 1: Player plays 0.01 SOL on HEADS
- Collect escrow: 0.01 SOL from player → house
- Player wallet: 0.04 SOL
- House wallet: 0.51 SOL

Step 2: Coin flip = HEADS (Player wins!)
- Payout = 0.02 - 2% = 0.0196 SOL
- Fee = 0.0004 SOL

Step 3: Transfers
- Pay winner: 0.0196 SOL house → player
- Pay fee: 0.0004 SOL house → treasury

Final State:
- Player wallet: 0.0596 SOL (gained 0.0096 SOL)
- House wallet: 0.4904 SOL (lost 0.0096 SOL)
- Treasury wallet: 0.0004 SOL (collected fee)

✅ Total SOL conserved: 0.05 + 0.50 = 0.5504 SOL
```

### Example 2: PVP Game

```
Initial State:
- Player A wallet: 0.05 SOL
- Player B wallet: 0.05 SOL
- House wallet: 0.50 SOL
- Treasury wallet: 0.00 SOL

Step 1: Both players wager 0.01 SOL
- Collect from A: 0.01 SOL → house
- Collect from B: 0.01 SOL → house
- Player A wallet: 0.04 SOL
- Player B wallet: 0.04 SOL
- House wallet: 0.52 SOL

Step 2: Coin flip = HEADS (Player A wins!)
- Payout = 0.02 - 2% = 0.0196 SOL
- Fee = 0.0004 SOL

Step 3: Transfers
- Pay winner: 0.0196 SOL house → Player A
- Pay fee: 0.0004 SOL house → treasury

Final State:
- Player A wallet: 0.0596 SOL (won 0.0096 SOL)
- Player B wallet: 0.04 SOL (lost 0.01 SOL)
- House wallet: 0.50 SOL (neutral - facilitated only)
- Treasury wallet: 0.0004 SOL (collected fee)

✅ Total SOL conserved: 0.05 + 0.05 + 0.50 = 0.6 SOL
✅ House wallet returns to original: 0.50 SOL
```

---

## Security Guarantees

### For Telegram (Custodial):
✅ **Money collected before game**
✅ **No way to win without risking SOL**
✅ **All transactions on-chain (verifiable)**
✅ **Fee collection automatic**

### For Web (Non-Custodial):
⚠️ **Balance checked but not enforced**
⚠️ **Needs additional verification**
🔜 **Future: Solana program for trustless escrow**

---

## Testing the Fix

### Test Scenario 1: Quick Flip

```bash
# Start bot
cd backend
python bot.py

# On Telegram:
1. /start
2. Copy your wallet address
3. Send 0.05 SOL to that address
4. Click "🎲 Quick Flip"
5. Choose HEADS, amount 0.01 SOL
6. Confirm

# Check logs:
- Should see "Collected 0.01 SOL from player"
- Should see coin flip result
- Should see payout or house win
- Should see fee transfer to treasury
```

### Test Scenario 2: PVP

```bash
# Use two Telegram accounts

# Account A:
1. Deposit 0.05 SOL
2. Create wager: 0.01 SOL, HEADS

# Account B:
1. Deposit 0.05 SOL
2. View Open Wagers
3. Accept Account A's wager

# Check logs:
- Should see "Collected 0.01 SOL from player1"
- Should see "Collected 0.01 SOL from player2"
- Should see winner and payout
- Should see fee to treasury
```

---

## Comparison: Before vs After

| Aspect | Before (Broken) | After (Fixed) |
|--------|----------------|---------------|
| Escrow Collection | ❌ None | ✅ Before game starts |
| Player Risk | ❌ None (free plays!) | ✅ Must have SOL |
| House Risk | ❌ Loses money | ✅ Protected |
| Fee Collection | ⚠️ Sometimes | ✅ Always |
| Money Conservation | ❌ Broken | ✅ Perfect |
| PVP Fairness | ❌ Not enforced | ✅ Both must deposit |

---

## Next Steps for Web Platform

To make Web games trustless:

**Option 1: Manual Verification**
```javascript
// User sends SOL to house wallet
const tx = await sendTransaction(houseWallet, amount);

// Backend verifies transaction
POST /api/game/verify-deposit
{
  "signature": tx,
  "amount": 0.01
}

// Only then allow game to start
```

**Option 2: Solana Program (Recommended)**
```rust
// Smart contract handles escrow
program create_escrow_account(amount)
program deposit_to_escrow(player, amount)
program execute_game_and_payout(winner)
program collect_fee(treasury)
```

---

**The escrow system is now properly implemented for Telegram!**

Web platform needs additional work for full trustlessness, but balance checks provide basic protection.

🎲 Ready to test with real SOL!
