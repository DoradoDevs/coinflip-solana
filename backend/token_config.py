"""
$FLIP Token Configuration

Token holder benefits for Coinflip platform.
Replace PLACEHOLDER with actual contract address after token launch.
"""

# =============================================================================
# TOKEN CONFIG - UPDATE THIS AFTER LAUNCH
# =============================================================================

TOKEN_MINT = "PLACEHOLDER_CONTRACT_ADDRESS"  # SPL Token mint address
TOKEN_SYMBOL = "FLIP"
TOKEN_DECIMALS = 6  # Standard SPL token decimals

# Set to True once token is launched and CA is set
TOKEN_ENABLED = False

# =============================================================================
# HOLDER TIERS & BENEFITS
# =============================================================================
#
# Tokenomics: 1 Billion supply, ~$250k market cap
# Price per token: ~$0.00025
#
# Philosophy: Token holding is a BONUS, not replacement for volume betting.
# Discounts are modest (5-25%) to keep betting volume incentivized.
#

HOLDER_TIERS = {
    "Whale": {
        "min_balance": 10_000_000,   # 10M tokens (~$2,500 at $250k MC)
        "fee_discount": 0.15,         # 15% off (stacks with volume tier, 40% cap)
        "color": "#00D4FF",           # Cyan/Whale blue
        "perks": ["Max token bonus", "Exclusive games", "Priority support"]
    },
    "Gigachad": {
        "min_balance": 7_000_000,    # 7M tokens (~$1,750)
        "fee_discount": 0.12,         # 12% off
        "color": "#FF6B6B",           # Red/Chad energy
        "perks": ["12% fee discount", "Early access"]
    },
    "Chad": {
        "min_balance": 4_000_000,    # 4M tokens (~$1,000)
        "fee_discount": 0.09,         # 9% off
        "color": "#FFD700",           # Gold
        "perks": ["9% fee discount"]
    },
    "Ape": {
        "min_balance": 2_000_000,    # 2M tokens (~$500)
        "fee_discount": 0.06,         # 6% off
        "color": "#8B4513",           # Brown/Ape
        "perks": ["6% fee discount"]
    },
    "Degen": {
        "min_balance": 1_000_000,    # 1M tokens (~$250)
        "fee_discount": 0.03,         # 3% off
        "color": "#9945FF",           # Purple/Degen
        "perks": ["3% fee discount"]
    },
    "Normie": {
        "min_balance": 0,
        "fee_discount": 0.0,          # No discount
        "color": "#808080",           # Gray
        "perks": []
    }
}

# Tier order for iteration (highest to lowest)
TIER_ORDER = ["Whale", "Gigachad", "Chad", "Ape", "Degen", "Normie"]

# Maximum combined discount (volume + token tiers)
# Diamond (25%) + Whale (15%) = 40% (exactly at cap)
# This incentivizes BOTH high volume AND high token holdings
MAX_COMBINED_DISCOUNT = 0.40  # 40% cap - this is the max achievable bonus

# Base platform fee (before discounts)
BASE_FEE_RATE = 0.02  # 2%

# =============================================================================
# BALANCE CACHING
# =============================================================================

BALANCE_CACHE_TTL = 300  # 5 minutes in seconds
BALANCE_CHECK_ON_BET = True  # Re-check balance before each bet


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_tier_for_balance(balance: float) -> str:
    """Get the tier name for a given token balance."""
    for tier_name in TIER_ORDER:
        tier = HOLDER_TIERS[tier_name]
        if balance >= tier["min_balance"]:
            return tier_name
    return "Flipper"


def get_fee_discount(tier_name: str) -> float:
    """Get the fee discount percentage for a tier."""
    tier = HOLDER_TIERS.get(tier_name, HOLDER_TIERS["Flipper"])
    return tier["fee_discount"]


def calculate_effective_fee(amount: float, tier_name: str) -> float:
    """Calculate the fee amount after tier discount."""
    discount = get_fee_discount(tier_name)
    effective_rate = BASE_FEE_RATE * (1 - discount)
    return amount * effective_rate


def get_tier_info(tier_name: str) -> dict:
    """Get full tier information."""
    tier = HOLDER_TIERS.get(tier_name, HOLDER_TIERS["Flipper"])
    return {
        "name": tier_name,
        "min_balance": tier["min_balance"],
        "fee_discount": tier["fee_discount"],
        "fee_rate": BASE_FEE_RATE * (1 - tier["fee_discount"]),
        "color": tier["color"],
        "perks": tier["perks"]
    }


def get_next_tier(current_tier: str) -> dict | None:
    """Get the next tier up and tokens needed."""
    try:
        current_idx = TIER_ORDER.index(current_tier)
        if current_idx == 0:
            return None  # Already at highest tier
        next_tier_name = TIER_ORDER[current_idx - 1]
        next_tier = HOLDER_TIERS[next_tier_name]
        current_min = HOLDER_TIERS[current_tier]["min_balance"]
        return {
            "name": next_tier_name,
            "tokens_needed": next_tier["min_balance"] - current_min,
            "fee_discount": next_tier["fee_discount"],
            "color": next_tier["color"]
        }
    except (ValueError, KeyError):
        return None


def calculate_combined_discount(volume_discount: float, token_discount: float) -> float:
    """
    Calculate combined discount from volume tier + token holdings.

    Both discounts stack additively but are capped at MAX_COMBINED_DISCOUNT (40%).

    Args:
        volume_discount: Discount from volume tier (0.0 to 0.25)
        token_discount: Discount from token holdings (0.0 to 0.15)

    Returns:
        Combined discount rate (capped at 0.40)
    """
    combined = volume_discount + token_discount
    return min(combined, MAX_COMBINED_DISCOUNT)


def calculate_effective_fee_combined(amount: float, volume_tier: str, token_tier: str) -> tuple:
    """
    Calculate fee with both volume and token discounts applied.

    Args:
        amount: Bet amount
        volume_tier: User's volume-based tier (Starter, Bronze, Silver, Gold, Diamond)
        token_tier: User's token-based tier (Normie, Degen, Ape, Chad, Gigachad, Whale)

    Returns:
        Tuple of (fee_amount, effective_rate, combined_discount)
    """
    from tiers import TIERS

    # Get volume discount (convert fee rate to discount)
    volume_tier_data = TIERS.get(volume_tier, TIERS["Starter"])
    volume_fee_rate = volume_tier_data["fee_rate"]
    volume_discount = 1 - (volume_fee_rate / BASE_FEE_RATE)  # e.g., 0.015/0.02 = 0.75, so 0.25 discount

    # Get token discount
    token_discount = get_fee_discount(token_tier)

    # Combine with cap
    combined_discount = calculate_combined_discount(volume_discount, token_discount)

    # Calculate effective rate and fee
    effective_rate = BASE_FEE_RATE * (1 - combined_discount)
    fee_amount = amount * effective_rate

    return fee_amount, effective_rate, combined_discount
