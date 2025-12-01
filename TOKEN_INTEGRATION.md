# $FLIP Token Integration Plan
**Project:** Coinflip (coinflipvp.com)
**Status:** Infrastructure Ready - Awaiting Token Launch

---

## Token Overview

**Token Name:** $FLIP (or TBD)
**Blockchain:** Solana (SPL Token)
**Contract Address:** `PLACEHOLDER_CONTRACT_ADDRESS`

---

## Holder Benefits Tiers

**Tokenomics:** 1 Billion supply, ~$250k target market cap (~$0.00025/token)

**Philosophy:** Token holding = BONUS that stacks with volume tiers. Max 40% combined discount requires BOTH Diamond volume tier AND Whale token holdings.

### Token Holder Tiers

| Tier | Holdings Required | USD Value* | Fee Discount |
|------|------------------|-----------|--------------|
| **Normie** | 0 | $0 | 0% |
| **Degen** | 1,000,000 $FLIP | ~$250 | 3% |
| **Ape** | 2,000,000 $FLIP | ~$500 | 6% |
| **Chad** | 4,000,000 $FLIP | ~$1,000 | 9% |
| **Gigachad** | 7,000,000 $FLIP | ~$1,750 | 12% |
| **Whale** | 10,000,000 $FLIP | ~$2,500 | 15% |

*USD values at $250k market cap

### Stacking with Volume Tiers

Token discounts STACK with volume tier discounts (capped at 40%):

| Volume Tier | Volume Discount | + Whale (15%) | = Combined |
|-------------|-----------------|---------------|------------|
| Starter | 0% | 15% | **15%** |
| Bronze | 5% | 15% | **20%** |
| Silver | 10% | 15% | **25%** |
| Gold | 15% | 15% | **30%** |
| Diamond | 25% | 15% | **40%** (max) |

**Key Insight:** Only Diamond + Whale achieves the 40% cap. This incentivizes both high betting volume AND high token holdings.

---

## Implementation Checklist

### Backend
- [x] Token config file with placeholder CA
- [x] Token balance checker (Solana RPC)
- [x] Holder tier calculation
- [x] Fee discount application
- [x] Balance caching (refresh every 5 min)
- [ ] Holder-only endpoints (future)
- [ ] Staking/rewards system (future)

### Frontend
- [x] Token holdings display in profile
- [x] Tier badge display
- [x] Fee discount indicator
- [ ] "Buy $FLIP" link (after launch)
- [ ] Leaderboard by holdings (future)

### Database
- [x] User model: token_balance, token_tier, last_balance_check
- [ ] Token transactions log (future)

---

## Technical Architecture

### Token Balance Flow
```
User connects wallet
       ↓
Check SPL token balance via RPC
       ↓
Calculate tier based on holdings
       ↓
Cache balance (5 min TTL)
       ↓
Apply fee discount on bets
```

### RPC Call for Token Balance
```python
# Using Solana RPC to check SPL token balance
async def get_token_balance(wallet: str, token_mint: str) -> float:
    # Get associated token account
    # Fetch balance from ATA
    # Return balance in token units
```

---

## Fee Calculation with Combined Discounts

```python
BASE_FEE = 0.02  # 2%
MAX_COMBINED_DISCOUNT = 0.40  # 40% cap

def calculate_combined_fee(amount: float, volume_tier: str, token_tier: str) -> float:
    # Volume tier discounts (from betting volume)
    volume_discounts = {
        "Starter": 0, "Bronze": 0.05, "Silver": 0.10,
        "Gold": 0.15, "Diamond": 0.25
    }

    # Token tier discounts (from $FLIP holdings)
    token_discounts = {
        "Normie": 0, "Degen": 0.03, "Ape": 0.06,
        "Chad": 0.09, "Gigachad": 0.12, "Whale": 0.15
    }

    # Stack discounts with 40% cap
    combined = volume_discounts.get(volume_tier, 0) + token_discounts.get(token_tier, 0)
    combined = min(combined, MAX_COMBINED_DISCOUNT)

    effective_fee = BASE_FEE * (1 - combined)
    return amount * effective_fee
```

---

## Holder Revenue Share (Pump.fun Creator Rewards)

Distribute Pump.fun creator rewards to top 100 token holders using **sqrt distribution model**.

### How It Works

1. **Square Root Weighting**: Each holder's share = `sqrt(balance) / sum(sqrt(all_balances))`
2. **Fairer Distribution**: Larger holders get more, but not disproportionately more
3. **Example** (1 SOL to distribute):
   - Holder A (1M tokens): sqrt(1M) = 1000 → 70.6% → 0.706 SOL
   - Holder B (100K tokens): sqrt(100K) = 316 → 22.3% → 0.223 SOL
   - Holder C (10K tokens): sqrt(10K) = 100 → 7.1% → 0.071 SOL

### Admin Panel Usage

1. Go to **Admin Panel** → **Holder Revshare** tab
2. Enter total SOL to distribute
3. Click **Preview Distribution** → see all recipients and amounts
4. Review the table, then click **Execute Distribution**
5. Double-confirm, funds are sent in batches

### Configuration Required

Add to `.env` on server:
```env
# Token contract address (after launch)
FLIP_TOKEN_MINT=your_token_mint_address

# Distribution wallet private key (base58)
# This wallet holds collected creator fees and distributes to holders
REVSHARE_WALLET_SECRET=your_wallet_private_key_base58
```

### Distribution Settings (in api.py)

- **Top Holders**: 100 recipients max
- **Minimum Balance**: 100,000 tokens to qualify
- **Minimum Payout**: 0.001 SOL (avoids dust)
- **LP Exclusion**: Add LP wallet address to `EXCLUDED_WALLETS` list after launch

### API Endpoints

```
POST /api/admin/revshare/preview   - Calculate distribution (dry run)
POST /api/admin/revshare/execute   - Send SOL to all holders
```

---

## Future Holder Benefits

1. **Exclusive Games** - Whale-only high-stakes tables
2. **Governance** - Vote on new features
3. **Airdrops** - Partner project airdrops to holders
4. **Burn Mechanism** - % of fees used for buyback and burn

---

## Launch Checklist

1. [ ] Deploy token on Pump.fun
2. [ ] Update `FLIP_TOKEN_MINT` in `.env`
3. [ ] Set `TOKEN_ENABLED = True` in `token_config.py`
4. [ ] Add LP wallet to excluded list in `api.py` (~line 2373)
5. [ ] Set `REVSHARE_WALLET_SECRET` in `.env` for distributions
6. [ ] Test balance checking with real CA
7. [ ] Create "Buy $FLIP" links (Jupiter, Raydium)

---

## Config Locations

| File | Purpose |
|------|---------|
| `backend/token_config.py` | Tier definitions, discounts, settings |
| `backend/token_checker.py` | Balance checking, caching |
| `backend/api.py` | Revshare endpoints (~line 2304) |
| `.env` | `FLIP_TOKEN_MINT`, `REVSHARE_WALLET_SECRET` |

---

*Ready to moon when you are!*
