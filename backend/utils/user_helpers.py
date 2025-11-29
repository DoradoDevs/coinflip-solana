"""
User helper functions for validation and setup.
"""
import logging
from typing import Tuple
from database import User
from utils.validation import is_valid_solana_address

logger = logging.getLogger(__name__)


def validate_payout_wallet_set(user: User) -> Tuple[bool, str]:
    """Validate that user has set a payout wallet.

    Args:
        user: User object to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not user.payout_wallet:
        return False, (
            "⚠️ You must set a payout wallet before betting!\n\n"
            "This is where your winnings will be sent.\n\n"
            "📱 Telegram: Use /set_payout_wallet command\n"
            "🌐 Web: Set payout wallet in settings\n\n"
            "💡 Tip: This protects your funds - we can always return "
            "your winnings to your payout wallet even if something goes wrong!"
        )

    # Validate wallet format
    is_valid, error_msg = is_valid_solana_address(user.payout_wallet)
    if not is_valid:
        return False, f"Invalid payout wallet address: {error_msg}"

    return True, ""


def auto_set_payout_wallet(user: User) -> bool:
    """Auto-set payout wallet if user has a wallet address.

    For Telegram users: Use their custodial wallet
    For Web users: Use their connected wallet

    Args:
        user: User object to update

    Returns:
        True if payout wallet was set, False otherwise
    """
    if user.payout_wallet:
        return False  # Already set

    if user.platform == "telegram" and user.wallet_address:
        user.payout_wallet = user.wallet_address
        logger.info(f"Auto-set payout wallet for Telegram user {user.user_id}: {user.wallet_address}")
        return True
    elif user.platform == "web" and user.connected_wallet:
        user.payout_wallet = user.connected_wallet
        logger.info(f"Auto-set payout wallet for Web user {user.user_id}: {user.connected_wallet}")
        return True

    return False


def can_create_wager(user: User) -> Tuple[bool, str]:
    """Check if user can create a wager.

    Args:
        user: User object to validate

    Returns:
        Tuple of (can_create, error_message)
    """
    # Check payout wallet
    is_valid, error_msg = validate_payout_wallet_set(user)
    if not is_valid:
        return False, error_msg

    # For Telegram users, check they have a custodial wallet
    if user.platform == "telegram" and not user.wallet_address:
        return False, (
            "⚠️ No wallet found!\n\n"
            "Use /start to create your wallet first."
        )

    return True, ""


def can_accept_wager(user: User) -> Tuple[bool, str]:
    """Check if user can accept a wager.

    Args:
        user: User object to validate

    Returns:
        Tuple of (can_accept, error_message)
    """
    # Same requirements as creating a wager
    return can_create_wager(user)


def get_payout_wallet(user: User) -> str:
    """Get user's payout wallet address.

    Args:
        user: User object

    Returns:
        Payout wallet address

    Raises:
        ValueError: If no payout wallet is set
    """
    if not user.payout_wallet:
        raise ValueError("User has no payout wallet set")

    return user.payout_wallet


def format_user_info(user: User) -> str:
    """Format user info for display.

    Args:
        user: User object

    Returns:
        Formatted user info string
    """
    info = f"👤 User ID: {user.user_id}\n"
    info += f"📱 Platform: {user.platform.title()}\n"
    info += f"🏆 Tier: {user.tier}\n"
    info += f"💰 Fee Rate: {user.tier_fee_rate * 100:.1f}%\n"
    info += f"🎮 Games Played: {user.games_played}\n"
    info += f"🏅 Games Won: {user.games_won}\n"

    if user.games_played > 0:
        win_rate = (user.games_won / user.games_played) * 100
        info += f"📊 Win Rate: {win_rate:.1f}%\n"

    info += f"💵 Total Wagered: {user.total_wagered:.4f} SOL\n"

    if user.payout_wallet:
        info += f"\n✅ Payout Wallet: {user.payout_wallet[:8]}...{user.payout_wallet[-4:]}\n"
    else:
        info += f"\n⚠️ Payout Wallet: Not Set\n"

    if user.referral_code:
        info += f"🔗 Referral Code: {user.referral_code}\n"

    if user.pending_referral_balance > 0:
        info += f"💸 Pending Referral Balance: {user.pending_referral_balance:.6f} SOL\n"

    return info
