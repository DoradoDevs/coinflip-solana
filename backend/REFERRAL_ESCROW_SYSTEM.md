# Referral Escrow Wallet System

## Overview

Each user gets their own **permanent referral payout escrow wallet** where referral commissions accumulate over time. This is separate from the temporary bet escrow wallets.

## Architecture

### Two Types of Escrow Wallets

#### 1. Bet Escrow Wallets (Temporary)
- **Purpose**: Hold wager amounts during PVP games
- **Lifespan**: Created fresh for each bet, abandoned after game completes
- **Quantity**: 2 per bet (one for creator, one for acceptor)
- **Storage**: `Wager` model
  - `creator_escrow_address` / `creator_escrow_secret`
  - `acceptor_escrow_address` / `acceptor_escrow_secret`
- **Security**: Encrypted private keys, isolated per wager

#### 2. Referral Payout Escrow Wallets (Permanent)
- **Purpose**: Accumulate referral commissions for each user
- **Lifespan**: Created on first commission, persists for user's lifetime
- **Quantity**: ONE per user
- **Storage**: `User` model
  - `referral_payout_escrow_address` - Wallet address
  - `referral_payout_escrow_secret` - Encrypted private key
  - `referral_earnings` - Total lifetime earnings (counter)
  - `total_referral_claimed` - Total amount claimed (counter)
- **Security**: Fernet encrypted private keys, same security as bet escrows

## How It Works

### Commission Flow

1. **Game Completes**
   ```python
   # Winner pays tier-based fees
   game_fees = amount * winner.tier_fee_rate * 2  # From both escrows

   # Fees swept to treasury
   treasury_receives = game_fees + transaction_fees + dust
   ```

2. **Referral Commission Calculated** (if winner was referred)
   ```python
   # Referrer earns commission based on THEIR tier
   commission_rate = referrer.tier_fee_rate  # e.g., 2.5% for Bronze
   commission_amount = game_fees * commission_rate
   ```

3. **Commission Sent to Referrer's Escrow**
   ```python
   # Treasury sends commission to referrer's individual escrow
   tx_sig = await send_referral_commission(
       referrer=referrer,
       commission_amount=commission_amount,
       from_wallet_secret=treasury_wallet_secret,
       to_escrow=referrer.referral_payout_escrow_address
   )

   # Update lifetime earnings counter
   referrer.referral_earnings += commission_amount
   ```

4. **User Watches Balance Grow**
   - Users can check their referral escrow balance anytime via API
   - Balance visible in UI (psychological benefit of watching it accumulate)
   - No automatic payouts - user decides when to claim

5. **User Claims When Ready**
   ```python
   # User initiates claim via API
   success, message, amount = await claim_referral_earnings(user)

   # 1% treasury fee on claims
   treasury_fee = escrow_balance * 0.01
   user_receives = escrow_balance - treasury_fee - tx_fees

   # Funds sent to user's payout wallet
   transfer(from=user.referral_escrow, to=user.payout_wallet, amount=user_receives)
   ```

## API Endpoints

### POST /api/referral/claim
Claim referral earnings from escrow to payout wallet.

**Request:**
```json
{
  "user_wallet": "5xR7yT..."
}
```

**Response:**
```json
{
  "success": true,
  "message": "Successfully claimed 0.145000 SOL!\n\nSent to: 5xR7yT...abc\nTreasury fee (1%): 0.001450 SOL\nTransaction: 2ZqK...",
  "amount_claimed": 0.145000,
  "escrow_balance_before": 0.147500,
  "total_lifetime_claimed": 0.523000,
  "total_lifetime_earnings": 0.678000
}
```

**Rate Limit:** 5 claims per hour

**Errors:**
- 400: "You must set a payout wallet before claiming"
- 400: "Insufficient balance to claim. Minimum 0.01 SOL required"
- 500: "Failed to process claim"

### GET /api/referral/balance
Get user's referral earnings balance.

**Request:**
```
GET /api/referral/balance?user_wallet=5xR7yT...
```

**Response:**
```json
{
  "success": true,
  "user_id": 12345,
  "referral_escrow_address": "8kPq2W...",
  "current_balance": 0.147500,
  "total_lifetime_earnings": 0.678000,
  "total_lifetime_claimed": 0.530500,
  "total_referrals": 12,
  "tier": "Silver",
  "referral_code": "FLIP-A3B9"
}
```

## Database Schema

### User Model Updates

```python
@dataclass
class User:
    # ... existing fields ...

    # Referral System
    referral_code: Optional[str] = None
    referred_by: Optional[int] = None
    referral_earnings: float = 0.0  # Total SOL earned (lifetime counter)
    total_referrals: int = 0

    # Referral Payout Escrow (NEW)
    referral_payout_escrow_address: Optional[str] = None
    referral_payout_escrow_secret: Optional[str] = None  # Encrypted
    total_referral_claimed: float = 0.0  # Total SOL claimed (lifetime counter)
```

### Database Table

```sql
ALTER TABLE users ADD COLUMN referral_payout_escrow_address TEXT;
ALTER TABLE users ADD COLUMN referral_payout_escrow_secret TEXT;
ALTER TABLE users ADD COLUMN total_referral_claimed REAL DEFAULT 0.0;
```

## Security Features

### Encryption
- All private keys encrypted with Fernet (AES-128)
- Same encryption key as bet escrows
- Keys never exposed in API responses

### Audit Logging
All referral operations logged to audit system:
- `ESCROW_CREATED` - When referral escrow is created
- `REFERRAL_COMMISSION` - When commission is sent to escrow
- `PAYOUT_PROCESSED` - When user claims earnings

### Rate Limiting
- Claim endpoint: 5 requests per hour per IP
- Prevents spam and abuse

### Validation
- User MUST have payout wallet set before claiming
- Minimum claim amount: 0.01 SOL (covers fees)
- Treasury fee deducted automatically (1%)

## Benefits

### For Users
1. **Transparency**: See balance grow in real-time
2. **Control**: Claim whenever they want, not batch schedules
3. **Security**: Individual wallets, no shared funds
4. **Psychology**: Satisfying to watch balance accumulate before claiming

### For Platform
1. **Lower Gas Costs**: Batch claims when users request, not on schedule
2. **Treasury Revenue**: 1% fee on every claim
3. **No Hot Wallet Risk**: No single wallet holding all referral funds
4. **Simplified Accounting**: Each user has own isolated escrow

### For Security
1. **Isolation**: User escrows isolated from each other
2. **Auditability**: Every transaction logged and traceable
3. **Recovery**: Admin tools can recover from any escrow if needed
4. **Encrypted Keys**: All escrow keys encrypted at rest

## Admin Recovery Tools

See [admin_recovery_tools.py](admin_recovery_tools.py) for complete toolkit.

### Recover Referral Escrow Funds
```python
from admin_recovery_tools import RecoveryTools

recovery = RecoveryTools(db, encryption_key, rpc_url)

# Check user's referral escrow balance
user = db.get_user(12345)
balance = await get_referral_escrow_balance(user, rpc_url)

# Manually send to user's payout wallet (emergency)
tx_sig = await recovery.recover_user_payout(
    user_id=12345,
    amount=balance,
    from_wallet_secret=user.referral_payout_escrow_secret,
    admin_id=1,
    reason="User reported stuck funds in referral escrow"
)
```

### Verify All Escrows Have Keys Stored
```python
# Check that all referral escrows have encrypted keys
results = await recovery.verify_all_escrows()

print(f"Total users with escrows: {results['total_wagers']}")
print(f"Verified keys: {results['verified']}")
print(f"Missing keys: {len(results['missing_keys'])}")
```

## Testing Checklist

- [ ] User earns first commission → escrow wallet created
- [ ] Commission appears in user's referral balance
- [ ] Multiple commissions accumulate correctly
- [ ] User can check balance via API
- [ ] User can claim with valid payout wallet
- [ ] 1% treasury fee deducted on claim
- [ ] Claim rejected without payout wallet set
- [ ] Claim rejected if balance too low (< 0.01 SOL)
- [ ] Rate limiting works (5 claims/hour)
- [ ] Audit logs created for all operations
- [ ] Admin can recover funds from escrow
- [ ] Encrypted keys can be decrypted successfully

## Migration Plan

### For Existing Users with Pending Balances

If you have users with `pending_referral_balance` from old system:

1. **One-time migration script:**
   ```python
   # For each user with pending balance
   for user in users:
       if user.pending_referral_balance > 0:
           # Create escrow
           escrow_address, escrow_secret = await get_or_create_referral_escrow(user, key, db)

           # Send pending balance to escrow
           tx_sig = await transfer_sol(
               rpc_url=rpc_url,
               from_secret=treasury_secret,
               to_pubkey=escrow_address,
               amount_sol=user.pending_referral_balance
           )

           # Update counters
           user.referral_earnings += user.pending_referral_balance
           user.pending_referral_balance = 0
           db.save_user(user)
   ```

2. **Deprecate pending_referral_balance field** after migration complete

## Files Modified

1. **database/models.py** - Added referral escrow fields to User model
2. **database/repo.py** - Updated schema and save/load methods
3. **referrals.py** (NEW) - Referral escrow management functions
4. **game/coinflip.py** - Modified STEP 6 to send commissions to escrows
5. **api.py** - Added claim and balance endpoints

## Next Steps

1. Update frontend to display referral escrow balance
2. Add "Claim Referrals" button in UI
3. Add referral dashboard showing:
   - Current balance
   - Total earned
   - Total claimed
   - Recent commission history
4. Send notifications when commissions are earned
5. Consider adding minimum auto-claim threshold (optional)
