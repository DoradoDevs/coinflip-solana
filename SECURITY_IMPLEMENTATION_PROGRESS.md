# Security Implementation Progress

## 🎯 Overview

Implementing **isolated escrow wallets per wager** to eliminate single point of failure and prevent multiple attack vectors.

---

## ✅ Completed (Phase 1 & 2)

### Database Schema Updates

**1. Wagers Table - New Escrow Fields:**
```sql
ALTER TABLE wagers ADD COLUMN:
- creator_escrow_address TEXT       -- Unique wallet for creator's deposit
- creator_escrow_secret TEXT         -- Encrypted private key
- creator_deposit_tx TEXT            -- Transaction signature (prevent reuse)
- acceptor_escrow_address TEXT       -- Unique wallet for acceptor's deposit
- acceptor_escrow_secret TEXT        -- Encrypted private key
- acceptor_deposit_tx TEXT           -- Transaction signature
```
✅ **Status:** DONE ([repo.py:71-93](backend/database/repo.py#L71-L93))

**2. Used Signatures Table - Prevent Reuse Attacks:**
```sql
CREATE TABLE used_signatures (
    signature TEXT PRIMARY KEY,
    user_wallet TEXT NOT NULL,
    used_for TEXT NOT NULL,
    used_at TEXT NOT NULL
);
```
✅ **Status:** DONE ([repo.py:110-118](backend/database/repo.py#L110-L118))

**3. Database Models Updated:**
- Wager model with escrow fields ✅ ([models.py:90-116](backend/database/models.py#L90-L116))
- UsedSignature model added ✅ ([models.py:132-142](backend/database/models.py#L132-L142))

**4. Database Methods Added:**
- `save_wager()` updated for escrow fields ✅
- `_row_to_wager()` updated for escrow fields ✅
- `save_used_signature()` ✅ ([repo.py:404-419](backend/database/repo.py#L404-L419))
- `signature_already_used()` ✅ ([repo.py:421-433](backend/database/repo.py#L421-L433))
- `get_used_signature()` ✅ ([repo.py:435-457](backend/database/repo.py#L435-L457))

---

## 🚧 In Progress (Phase 3)

### Escrow Wallet Generation

Need to implement helper functions in a new file:

**File:** `backend/game/escrow.py` (NEW)

```python
async def create_wager_escrow(
    amount: float,
    creator_user: User,
    creator_wallet: str,
    rpc_url: str,
    encryption_key: str
) -> Tuple[str, str, str]:
    """Create escrow wallet for wager creator.

    Returns:
        (escrow_address, encrypted_secret, deposit_tx_signature)
    """
    # Generate unique wallet
    escrow_addr, escrow_secret = generate_wallet()

    # Encrypt secret
    encrypted_secret = encrypt_secret(escrow_secret, encryption_key)

    # For Telegram: Transfer from user wallet to escrow
    # For Web: Verify user sent to escrow

    return escrow_addr, encrypted_secret, deposit_tx
```

**Status:** 🔨 NEXT TASK

---

## 📋 Remaining (Phases 4-7)

### Phase 4: Update Create Wager Flow

**Files to Modify:**
- `backend/bot.py` - Telegram create wager handler
- `backend/api.py` - Web create wager endpoint

**Changes:**
1. Generate unique escrow wallet for creator
2. Verify/collect deposit to escrow (not house)
3. Save escrow details to wager
4. Mark signature as used
5. Return escrow address to user

**Status:** ⏳ PENDING

---

### Phase 5: Update Accept Wager Flow

**Files to Modify:**
- `backend/bot.py` - Telegram accept handler
- `backend/api.py` - Web accept endpoint

**Changes:**
1. Lock wager (prevent double-accept)
2. Change status: `open` → `accepting`
3. Generate unique escrow for acceptor
4. Verify/collect deposit to acceptor escrow
5. Mark signature as used
6. Change status: `accepting` → `accepted`
7. Execute game with both escrows

**Wager Status Flow:**
```
open → accepting → accepted → completed
  ↓
cancelled (only from "open")
```

**Status:** ⏳ PENDING

---

### Phase 6: Update Game Execution

**File:** `backend/game/coinflip.py`

**New Function:** `play_pvp_game_with_escrows()`

**Flow:**
1. Decrypt both escrow secrets
2. Flip coin (provably fair)
3. Determine winner
4. Pay winner from winner's escrow (0.0196 SOL)
5. Transfer ALL remaining from BOTH escrows → house wallet
   - Winner's escrow: ~0.0154 SOL remaining
   - Loser's escrow: ~0.035 SOL remaining
   - Total to house: ~0.0504 SOL (fees)
6. Escrows now empty (except dust for rent)

**Status:** ⏳ PENDING

---

### Phase 7: Cancel Wager Logic

**Files to Modify:**
- `backend/bot.py` - Telegram cancel handler
- `backend/api.py` - Web cancel endpoint

**New Fee Structure:**
1. **Check:** Can only cancel if `status == "open"`
2. **Refund:** Wager amount (0.01 SOL) → creator
3. **Keep:** Transaction fee (0.025 SOL) → house
4. **No 2% Fee:** Game fee only applies to completed games
5. **Transfer:** Remaining escrow balance → house
6. **Mark:** Status = `cancelled`

**Status:** ⏳ PENDING

---

### Phase 8: Security Enhancements

**1. House Balance Monitoring:**
```python
async def check_house_balance():
    balance = await get_sol_balance(RPC_URL, house_address)
    if balance < MIN_BALANCE:
        logger.warning(f"House balance low: {balance} SOL")
        # Alert admin
```

**2. Signature Reuse Prevention:**
```python
# Before accepting deposit
if db.signature_already_used(deposit_tx_signature):
    raise HTTPException(400, "Transaction signature already used")

# After accepting
db.save_used_signature(UsedSignature(
    signature=deposit_tx_signature,
    user_wallet=user_wallet,
    used_for=wager_id
))
```

**3. Atomic Wager Acceptance:**
```python
# Use database transaction to prevent race conditions
with db_transaction():
    wager = db.get_wager(wager_id)
    if wager.status != "open":
        raise Exception("Already accepted")
    wager.status = "accepting"
    db.save_wager(wager)
```

**Status:** ⏳ PENDING

---

## 🔍 Testing Checklist

Before deployment:

- [ ] Create wager with escrow (Telegram)
- [ ] Create wager with escrow (Web)
- [ ] Accept wager (Telegram ↔ Telegram)
- [ ] Accept wager (Web ↔ Web)
- [ ] Accept wager (Telegram ↔ Web)
- [ ] Cancel wager (verify refund logic)
- [ ] Test signature reuse (should fail)
- [ ] Test double-accept (should fail)
- [ ] Test cancel after accept started (should fail)
- [ ] Verify all escrows empty after games
- [ ] Verify house wallet receives fees
- [ ] Load test: 10 simultaneous wager accepts
- [ ] Penetration test: Try to exploit escrow system

---

## 📊 Implementation Status

| Phase | Description | Status | Files Modified |
|-------|-------------|--------|----------------|
| 1 | Database schema | ✅ DONE | repo.py, models.py |
| 2 | Signature tracking | ✅ DONE | repo.py, models.py, __init__.py |
| 3 | Escrow generation | 🔨 IN PROGRESS | escrow.py (new) |
| 4 | Create wager flow | ⏳ PENDING | bot.py, api.py |
| 5 | Accept wager flow | ⏳ PENDING | bot.py, api.py |
| 6 | Game execution | ⏳ PENDING | coinflip.py |
| 7 | Cancel logic | ⏳ PENDING | bot.py, api.py |
| 8 | Security enhancements | ⏳ PENDING | Multiple files |
| 9 | Testing | ⏳ PENDING | test_security.py (new) |

**Overall Progress:** 22% Complete (2/9 phases done)

---

## 🚀 Next Steps

1. **Implement escrow wallet generation helpers** (escrow.py)
2. **Update create_wager in bot.py** to use escrows
3. **Update create_wager in api.py** to use escrows
4. **Test create wager flow** on both platforms
5. **Move to accept wager implementation**

---

## ⚠️ Important Notes

### Migration Strategy

**Existing Database:**
- Old wagers in database won't have escrow fields
- Need to handle NULL escrow addresses gracefully
- Could add migration to cancel all old "open" wagers

**Deployment:**
1. Deploy new code (backward compatible)
2. Run migration script to cancel old wagers
3. Monitor logs for issues
4. Gradually enable new escrow system

### Breaking Changes

- ❌ Old wagers cannot be accepted (no escrow)
- ❌ Need to cancel all existing "open" wagers
- ✅ New wagers use secure escrow system

---

## 💡 Key Security Improvements

| Vulnerability | Before | After |
|---------------|--------|-------|
| **Single Point of Failure** | ❌ All funds → 1 wallet | ✅ Isolated escrows |
| **Signature Reuse** | ❌ Possible | ✅ Tracked & prevented |
| **Race Conditions** | ❌ Possible | ✅ Status transitions |
| **Cancel Spam** | ❌ Full refund | ✅ Keep 0.025 SOL fee |
| **Attack Surface** | ❌ Large (one target) | ✅ Small (distributed) |

---

**This is a major security overhaul that will take significant implementation time, but dramatically improves the system's security posture.** 🛡️

Current focus: Implementing escrow wallet generation and integration.
