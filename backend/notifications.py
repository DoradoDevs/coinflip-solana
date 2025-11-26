"""
Cross-platform notification system.
Sends notifications to Telegram users from API events.
"""
import os
import logging
from typing import Optional
from telegram import Bot
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Telegram bot instance for sending notifications
BOT_TOKEN = os.getenv("BOT_TOKEN")
_bot_instance: Optional[Bot] = None


def get_bot() -> Bot:
    """Get or create Telegram bot instance."""
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = Bot(token=BOT_TOKEN)
    return _bot_instance


async def notify_telegram_user(user_id: int, message: str, parse_mode: str = "Markdown"):
    """Send a notification to a Telegram user.

    Args:
        user_id: Telegram user ID
        message: Message to send
        parse_mode: Message formatting (Markdown or HTML)

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        bot = get_bot()
        await bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode=parse_mode
        )
        logger.info(f"Notification sent to Telegram user {user_id}")
        return True
    except Exception as e:
        logger.warning(f"Failed to send notification to Telegram user {user_id}: {e}")
        return False


async def notify_wager_accepted(creator_user_id: int, amount: float, won: bool, payout: float):
    """Notify a user that their wager was accepted.

    Args:
        creator_user_id: User ID of wager creator
        amount: Wager amount
        won: Whether the creator won
        payout: Payout amount if won
    """
    if won:
        message = (
            f"🔔 *Your Wager Was Accepted!*\n\n"
            f"Someone just accepted your {amount:.4f} SOL wager!\n"
            f"Game is complete. 🎉 You WON {payout:.4f} SOL!"
        )
    else:
        message = (
            f"🔔 *Your Wager Was Accepted!*\n\n"
            f"Someone just accepted your {amount:.4f} SOL wager!\n"
            f"Game is complete. 😔 You lost {amount:.4f} SOL."
        )

    await notify_telegram_user(creator_user_id, message)


async def notify_wager_cancelled(creator_user_id: int, amount: float):
    """Notify a user that a wager they were interested in was cancelled.

    Args:
        creator_user_id: User ID who created the wager
        amount: Wager amount
    """
    message = (
        f"ℹ️ *Wager Cancelled*\n\n"
        f"Your {amount:.4f} SOL wager has been cancelled."
    )

    await notify_telegram_user(creator_user_id, message)
