# 🚨 Security Audit & Architecture Overhaul

## Critical Vulnerabilities Identified

### 🔴 CRITICAL: Single House Wallet (Single Point of Failure)

**Problem:**
- ALL funds go through one house wallet
- If private key is compromised → **TOTAL LOSS**
- One attack vector = catastrophic failure

**Impact:** 🔥 **CATASTROPHIC**

**Solution:** Unique escrow wallets per game/wager

---

### 🔴 HIGH: Transaction Signature Reuse

**Problem:**
- User deposits 0.035 SOL to house wallet
- Gets transaction signature
- Uses same signature for multiple wagers
- System doesn't track used signatures

**Attack:**
```python
# Attacker deposits once
tx_sig = deposit_sol(house_wallet, 0.035)

# Uses same signature for 10 wagers
for i in range(10):
    create_wager(amount=0.01, deposit_tx_signature=tx_sig)  # All accepted!
```

**Impact:** 🔥 **CRITICAL** - Free wagers

**Solution:** Track used signatures in database

---

### 🔴 HIGH: Race Conditions on Wager Acceptance

**Problem:**
- Two users accept same wager simultaneously
- No database locking
- Both think they won

**Attack:**
```python
# User A and User B both click "Accept" at same time
# Both get through balance checks
# Both call play_pvp_game()
# Database inconsistent state
```

**Impact:** 🔥 **CRITICAL** - Double payout

**Solution:** Atomic database operations with locking

---

### 🟡 MEDIUM: Insufficient House Balance

**Problem:**
- House wallet pays winners
- If balance too low → can't pay
- System breaks

**Impact:** ⚠️ **HIGH** - Service disruption

**Solution:** Check house balance before accepting games

---

### 🟡 MEDIUM: Cancel/Refund Spam

**Problem:**
- If we refund transaction fee on cancel
- Users spam create → cancel
- Free to dos attack

**Impact:** ⚠️ **MEDIUM** - Spam/DoS

**Solution:** Keep 0.025 SOL fee, refund wager only (User's suggestion ✅)

---

### 🟡 MEDIUM: Timing Attacks on Deposits

**Problem:**
- Web user sends deposit to house
- Immediately tries to reverse/double-spend
- Blockchain confirmation not enforced

**Impact:** ⚠️ **MEDIUM** - Potential double-spend

**Solution:** Require blockchain confirmation + unique escrow wallets

---

## ✅ New Architecture: Isolated Escrow Wallets

### Concept

**OLD (VULNERABLE):**
```
All deposits → Single House Wallet → Catastrophe if compromised
```

**NEW (SECURE):**
```
Wager 1: Creator → Escrow Wallet A ✅
         Acceptor → Escrow Wallet B ✅
         After game → Transfer to house → Empty escrows

Wager 2: Creator → Escrow Wallet C ✅
         Acceptor → Escrow Wallet D ✅
         After game → Transfer to house → Empty escrows
```

### Benefits

1. **Isolation** - Each wager has own escrow wallets
2. **No Single Point of Failure** - Compromising one escrow doesn't affect others
3. **Clear Audit Trail** - One escrow = one wager side
4. **Minimal Risk** - Escrows empty after game
5. **Can't Attack House** - House wallet not exposed

---

## 🏗️ Implementation Plan

### Phase 1: Update Database Schema

**Add to Wager Model:**
```python
# Unique escrow wallets
creator_escrow_address: str  # Public address for creator's deposit
creator_escrow_secret: str   # Encrypted private key
acceptor_escrow_address: str  # Public address for acceptor's deposit
acceptor_escrow_secret: str   # Encrypted private key

# Track deposits
creator_deposit_tx: str  # Creator's transaction signature
acceptor_deposit_tx: str  # Acceptor's transaction signature
```

**Add New Table:**
```sql
CREATE TABLE used_signatures (
    signature TEXT PRIMARY KEY,
    user_wallet TEXT NOT NULL,
    used_for TEXT NOT NULL,  -- wager_id or game_id
    used_at TEXT NOT NULL
);
```

---

### Phase 2: Create Wager Flow (New)

**Step 1: Generate Escrow Wallet**
```python
def create_wager(user, side, amount):
    # Generate UNIQUE escrow wallet for this wager
    escrow_addr, escrow_secret = generate_wallet()
    escrow_secret_encrypted = encrypt_secret(escrow_secret, ENCRYPTION_KEY)

    wager = Wager(
        wager_id=generate_id(),
        creator_escrow_address=escrow_addr,
        creator_escrow_secret=escrow_secret_encrypted,
        amount=amount,
        ...
    )

    return wager, escrow_addr  # Give user the escrow address
```

**Step 2: User Deposits to Escrow**

**Telegram (Custodial):**
```python
# Bot transfers from user's wallet → escrow wallet
deposit_tx = await transfer_sol(
    user_secret,  # User's wallet
    escrow_addr,  # Unique escrow for this wager
    amount + TRANSACTION_FEE  # 0.01 + 0.025 = 0.035 SOL
)

wager.creator_deposit_tx = deposit_tx
mark_signature_as_used(deposit_tx, user_wallet, wager_id)
```

**Web (Non-Custodial):**
```python
# User sends from Phantom → escrow wallet
# Provides transaction signature

# Verify deposit
is_valid = await verify_deposit_transaction(
    deposit_tx_signature,
    user_wallet,  # Sender
    escrow_addr,  # Recipient (unique escrow)
    amount + TRANSACTION_FEE
)

# Check not already used
if signature_already_used(deposit_tx_signature):
    raise HTTPException(400, "Transaction already used")

# Mark as used
mark_signature_as_used(deposit_tx_signature, user_wallet, wager_id)
wager.creator_deposit_tx = deposit_tx_signature
```

**Step 3: Verify Balance in Escrow**
```python
# Check escrow wallet has the funds
escrow_balance = await get_sol_balance(RPC_URL, escrow_addr)

required = amount + TRANSACTION_FEE  # 0.035 SOL

if escrow_balance < required:
    raise Exception("Insufficient escrow balance")

# Wager is now "open" - funds locked in escrow
wager.status = "open"
db.save_wager(wager)
```

---

### Phase 3: Accept Wager Flow (New)

**Step 1: Generate Acceptor Escrow**
```python
def accept_wager(wager_id, acceptor_user):
    # Get wager (with atomic locking)
    wager = db.get_wager_for_update(wager_id)  # Row lock!

    if wager.status != "open":
        raise Exception("Wager no longer available")

    # Generate UNIQUE escrow for acceptor
    acceptor_escrow_addr, acceptor_escrow_secret = generate_wallet()
    acceptor_escrow_secret_encrypted = encrypt_secret(acceptor_escrow_secret, ENCRYPTION_KEY)

    wager.acceptor_escrow_address = acceptor_escrow_addr
    wager.acceptor_escrow_secret = acceptor_escrow_secret_encrypted

    return wager, acceptor_escrow_addr
```

**Step 2: Acceptor Deposits to Escrow**
```python
# Same process as creator
# Telegram: Bot transfers
# Web: User sends, we verify

deposit_tx = ...  # Get deposit transaction

# Verify not already used
if signature_already_used(deposit_tx):
    raise Exception("Transaction already used")

# Verify balance in acceptor's escrow
escrow_balance = await get_sol_balance(RPC_URL, acceptor_escrow_addr)
if escrow_balance < (amount + TRANSACTION_FEE):
    raise Exception("Insufficient escrow balance")

wager.acceptor_deposit_tx = deposit_tx
mark_signature_as_used(deposit_tx, acceptor_wallet, wager_id)
```

**Step 3: Execute Game**
```python
# Both escrows funded → Game can proceed
wager.status = "accepted"

# Play game
game = await play_pvp_game_with_escrows(
    creator_escrow_secret,
    acceptor_escrow_secret,
    amount,
    ...
)
```

---

### Phase 4: Game Execution with Escrows

**Payout Flow:**
```python
async def play_pvp_game_with_escrows(
    creator_escrow_secret,
    acceptor_escrow_secret,
    amount,
    ...
):
    # Both escrows have: wager (0.01) + fee (0.025) = 0.035 SOL each

    # Flip coin
    blockhash = await get_latest_blockhash(RPC_URL)
    result = flip_coin(blockhash, game_id)

    # Determine winner
    if result == creator_side:
        winner_wallet = creator_wallet
        winner_escrow_secret = creator_escrow_secret
        loser_escrow_secret = acceptor_escrow_secret
    else:
        winner_wallet = acceptor_wallet
        winner_escrow_secret = acceptor_escrow_secret
        loser_escrow_secret = creator_escrow_secret

    # Calculate payout
    total_pot = amount * 2  # 0.02 SOL
    game_fee = total_pot * 0.02  # 0.0004 SOL (2%)
    payout = total_pot - game_fee  # 0.0196 SOL

    # PAYOUT: Transfer from winner's escrow to winner's wallet
    payout_tx = await transfer_sol(
        RPC_URL,
        winner_escrow_secret,  # From winner's escrow
        winner_wallet,  # To winner's main wallet
        payout  # 0.0196 SOL
    )

    # COLLECT FEES: Transfer remaining from BOTH escrows to house
    # Winner's escrow: Has 0.035 SOL, paid out 0.0196, left = 0.0154 SOL
    # Loser's escrow: Has 0.035 SOL, paid nothing, left = 0.035 SOL
    # Total fees: 0.0154 + 0.035 = 0.0504 SOL

    house_wallet = get_house_wallet_address(HOUSE_WALLET_SECRET)

    # Transfer all remaining from winner's escrow
    winner_escrow_balance = await get_sol_balance(RPC_URL, winner_escrow_addr)
    if winner_escrow_balance > 0.00001:  # Leave dust for rent
        await transfer_sol(
            RPC_URL,
            winner_escrow_secret,
            house_wallet,
            winner_escrow_balance - 0.00001  # Keep minimal rent
        )

    # Transfer all remaining from loser's escrow
    loser_escrow_balance = await get_sol_balance(RPC_URL, loser_escrow_addr)
    if loser_escrow_balance > 0.00001:
        await transfer_sol(
            RPC_URL,
            loser_escrow_secret,
            house_wallet,
            loser_escrow_balance - 0.00001
        )

    # Escrows now empty (except minimal rent) - can be discarded
```

---

### Phase 5: Cancel Wager Flow (New Fee Structure)

**User's Requirement:**
- Refund wager (0.01 SOL) ✅
- Keep transaction fee (0.025 SOL) ✅
- No 2% game fee (only on completed games) ✅

```python
async def cancel_wager(wager_id, creator_user):
    wager = db.get_wager(wager_id)

    if wager.status != "open":
        raise Exception("Can only cancel open wagers")

    if wager.creator_id != creator_user.user_id:
        raise Exception("Only creator can cancel")

    # Check escrow balance
    escrow_secret = decrypt_secret(wager.creator_escrow_secret, ENCRYPTION_KEY)
    escrow_balance = await get_sol_balance(RPC_URL, wager.creator_escrow_address)

    # Refund ONLY the wager amount (keep transaction fee)
    refund_amount = wager.amount  # 0.01 SOL
    # Transaction fee (0.025 SOL) stays in escrow

    # Refund to creator
    refund_tx = await transfer_sol(
        RPC_URL,
        escrow_secret,
        creator_wallet,
        refund_amount
    )

    # Transfer transaction fee to house
    remaining_balance = await get_sol_balance(RPC_URL, wager.creator_escrow_address)
    if remaining_balance > 0.00001:
        fee_tx = await transfer_sol(
            RPC_URL,
            escrow_secret,
            house_wallet,
            remaining_balance - 0.00001  # Keep dust
        )

    # Mark wager as cancelled
    wager.status = "cancelled"
    db.save_wager(wager)

    logger.info(f"Wager {wager_id} cancelled - refunded {refund_amount} SOL, kept {TRANSACTION_FEE} SOL fee")
```

---

## 🔒 Security Enhancements

### 1. Signature Reuse Prevention

```python
def mark_signature_as_used(signature: str, wallet: str, used_for: str):
    """Mark a transaction signature as used."""
    db.save_used_signature(UsedSignature(
        signature=signature,
        user_wallet=wallet,
        used_for=used_for,
        used_at=datetime.utcnow()
    ))

def signature_already_used(signature: str) -> bool:
    """Check if signature was already used."""
    return db.get_used_signature(signature) is not None
```

### 2. Atomic Wager Acceptance

```python
def get_wager_for_update(wager_id: str) -> Wager:
    """Get wager with row-level lock (prevents race conditions)."""
    conn = sqlite3.connect(db_path)
    # SQLite doesn't have SELECT FOR UPDATE, but we can use transactions
    conn.execute("BEGIN EXCLUSIVE")
    wager = get_wager(wager_id)
    # Transaction held open, commit after acceptance
    return wager, conn
```

### 3. House Balance Checks

```python
async def check_house_balance_sufficient():
    """Ensure house wallet has enough SOL for operations."""
    house_address = get_house_wallet_address(HOUSE_WALLET_SECRET)
    balance = await get_sol_balance(RPC_URL, house_address)

    # House doesn't need much now (escrows handle games)
    # Just need for fees and emergencies
    MIN_HOUSE_BALANCE = 0.1  # SOL

    if balance < MIN_HOUSE_BALANCE:
        logger.warning(f"House balance low: {balance} SOL")
        # Could send alert to admin

    return balance > MIN_HOUSE_BALANCE
```

### 4. Blockchain Confirmation

```python
async def verify_deposit_with_confirmation(
    rpc_url: str,
    tx_signature: str,
    expected_sender: str,
    expected_recipient: str,
    expected_amount: float,
    required_confirmations: int = 1  # Require at least 1 confirmation
) -> bool:
    """Verify deposit with confirmation requirement."""

    # Get transaction
    tx_resp = await client.get_transaction(
        sig,
        commitment=Confirmed,  # Wait for confirmation
        ...
    )

    # Check confirmations (if needed for extra security)
    # For most cases, Confirmed commitment is sufficient

    return is_valid
```

---

## 📊 Comparison: Old vs New

| Aspect | Old Architecture | New Architecture |
|--------|-----------------|------------------|
| **House Wallet Exposure** | ❌ All funds through one wallet | ✅ Isolated escrows |
| **Single Point of Failure** | ❌ YES - catastrophic | ✅ NO - isolated |
| **Signature Reuse** | ❌ Possible | ✅ Tracked & prevented |
| **Race Conditions** | ❌ Possible | ✅ Atomic operations |
| **Cancel Fee** | ❌ Full refund (spam vector) | ✅ Keep 0.025, refund wager |
| **Attack Surface** | ❌ Large (one target) | ✅ Small (distributed) |
| **Audit Trail** | ⚠️ Mixed | ✅ Clear (1 escrow = 1 side) |

---

## 🎯 Security Checklist

Before deploying:

- [ ] Unique escrow wallet per wager side
- [ ] Transaction signature tracking (prevent reuse)
- [ ] Atomic wager acceptance (prevent race conditions)
- [ ] House balance monitoring
- [ ] Blockchain confirmation requirements
- [ ] Cancel fee structure (keep 0.025, no 2%)
- [ ] Escrow cleanup (transfer to house after game)
- [ ] Used signature database table
- [ ] Update all API endpoints
- [ ] Update all bot handlers
- [ ] Test with real SOL on devnet first
- [ ] Penetration testing
- [ ] Load testing (concurrent accepts)

---

## 💰 Economics with New Architecture

### Per Wager Fees (Unchanged):
- Wager: 0.01 SOL
- Transaction Fee: 0.025 SOL
- Total deposit: **0.035 SOL per player**

### Cancellation (NEW):
- Refund: 0.01 SOL (wager)
- Keep: 0.025 SOL (transaction fee)
- Game fee: 0 SOL (no 2% on cancel)

### Completed Game:
- Winner gets: 0.0196 SOL (98% of pot)
- Game fee: 0.0004 SOL (2%)
- Transaction fees: 0.05 SOL (0.025 × 2)
- **Total to house: 0.0504 SOL**

---

## 🚀 Deployment Plan

1. **Test on Devnet**
   - Generate test wallets
   - Test all attack vectors
   - Verify signature tracking
   - Test concurrent accepts

2. **Audit**
   - Code review
   - Penetration testing
   - Load testing

3. **Gradual Rollout**
   - Start with small wager limits
   - Monitor for issues
   - Gradually increase limits

4. **Monitoring**
   - Alert on low house balance
   - Track escrow wallet usage
   - Monitor for suspicious patterns

---

**This architecture eliminates the single point of failure and dramatically reduces attack surface.** 🛡️
