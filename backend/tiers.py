"""
Tier system for volume-based fee discounts and referral commissions.
"""
import logging
import secrets
from typing import Tuple
from database import User

logger = logging.getLogger(__name__)

# Tier Configuration
TIERS = {
    "Starter": {
        "min_volume": 0,
        "fee_rate": 0.02,  # 2.0% (no discount - default)
        "referral_commission": 0.0,  # 0% (no referral earnings until Bronze)
    },
    "Bronze": {
        "min_volume": 250,
        "fee_rate": 0.019,  # 1.9%
        "referral_commission": 0.025,  # 2.5% of referral's fees
    },
    "Silver": {
        "min_volume": 500,
        "fee_rate": 0.018,  # 1.8%
        "referral_commission": 0.05,  # 5% of referral's fees
    },
    "Gold": {
        "min_volume": 1000,
        "fee_rate": 0.017,  # 1.7%
        "referral_commission": 0.075,  # 7.5% of referral's fees
    },
    "Diamond": {
        "min_volume": 5000,
        "fee_rate": 0.015,  # 1.5%
        "referral_commission": 0.10,  # 10% of referral's fees
    },
}


def calculate_tier(total_wagered: float) -> Tuple[str, float, float]:
    """Calculate user's tier based on total wagered volume.

    Args:
        total_wagered: Total SOL wagered by user

    Returns:
        Tuple of (tier_name, fee_rate, referral_commission)
    """
    # Check from highest to lowest tier
    if total_wagered >= TIERS["Diamond"]["min_volume"]:
        tier = "Diamond"
    elif total_wagered >= TIERS["Gold"]["min_volume"]:
        tier = "Gold"
    elif total_wagered >= TIERS["Silver"]["min_volume"]:
        tier = "Silver"
    elif total_wagered >= TIERS["Bronze"]["min_volume"]:
        tier = "Bronze"
    else:
        tier = "Starter"

    tier_data = TIERS[tier]
    return tier, tier_data["fee_rate"], tier_data["referral_commission"]


def update_user_tier(user: User) -> bool:
    """Update user's tier based on their total wagered volume.

    Args:
        user: User object to update

    Returns:
        True if tier changed, False otherwise
    """
    old_tier = user.tier
    new_tier, new_fee_rate, _ = calculate_tier(user.total_wagered)

    if old_tier != new_tier:
        user.tier = new_tier
        user.tier_fee_rate = new_fee_rate
        logger.info(f"User {user.user_id} upgraded: {old_tier} → {new_tier} (fee: {new_fee_rate*100:.1f}%)")
        return True

    return False


def generate_referral_code() -> str:
    """Generate a unique 8-character referral code.

    Returns:
        Referral code (e.g., "FLIP-A3B9")
    """
    # Generate 4 random uppercase alphanumeric characters
    code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(4))
    return f"FLIP-{code}"


def get_referral_commission_rate(referrer: User) -> float:
    """Get referrer's commission rate based on their tier.

    Args:
        referrer: Referrer user object

    Returns:
        Commission rate (e.g., 0.05 for 5%)
    """
    tier_data = TIERS.get(referrer.tier, TIERS["Bronze"])
    return tier_data["referral_commission"]


def calculate_referral_commission(fee_amount: float, referrer: User) -> float:
    """Calculate referral commission from a game's fees.

    Args:
        fee_amount: Total fees collected from game
        referrer: Referrer user object

    Returns:
        Commission amount to pay referrer
    """
    commission_rate = get_referral_commission_rate(referrer)
    commission = fee_amount * commission_rate

    logger.info(f"Referral commission: {commission:.6f} SOL ({commission_rate*100:.1f}% of {fee_amount:.6f} SOL) for tier {referrer.tier}")

    return commission


def get_tier_info(tier_name: str) -> dict:
    """Get tier information.

    Args:
        tier_name: Name of tier (Starter, Bronze, Silver, Gold, Diamond)

    Returns:
        Dict with tier details
    """
    tier_data = TIERS.get(tier_name, TIERS["Starter"])

    return {
        "name": tier_name,
        "min_volume": tier_data["min_volume"],
        "fee_rate": tier_data["fee_rate"],
        "fee_percentage": tier_data["fee_rate"] * 100,
        "referral_commission": tier_data["referral_commission"],
        "referral_percentage": tier_data["referral_commission"] * 100,
    }


def get_all_tiers() -> list:
    """Get information about all tiers.

    Returns:
        List of tier info dicts
    """
    return [
        get_tier_info("Starter"),
        get_tier_info("Bronze"),
        get_tier_info("Silver"),
        get_tier_info("Gold"),
        get_tier_info("Diamond"),
    ]


def get_next_tier(current_tier: str) -> dict:
    """Get information about the next tier.

    Args:
        current_tier: Current tier name

    Returns:
        Dict with next tier info, or None if already at max tier
    """
    tier_order = ["Starter", "Bronze", "Silver", "Gold", "Diamond"]

    try:
        current_idx = tier_order.index(current_tier)
        if current_idx < len(tier_order) - 1:
            next_tier_name = tier_order[current_idx + 1]
            return get_tier_info(next_tier_name)
    except ValueError:
        pass

    return None
