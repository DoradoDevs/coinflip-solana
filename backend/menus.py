"""
Telegram bot keyboard menus.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    """Main menu with all game options."""
    keyboard = [
        [InlineKeyboardButton("🎲 Quick Flip (vs House)", callback_data="quick_flip")],
        [InlineKeyboardButton("⚔️ Create Wager (PVP)", callback_data="create_wager")],
        [InlineKeyboardButton("🎯 Open Wagers", callback_data="open_wagers")],
        [InlineKeyboardButton("💰 Wallet", callback_data="wallet")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")],
        [InlineKeyboardButton("🎮 My Wagers", callback_data="my_wagers")],
        [InlineKeyboardButton("📜 History", callback_data="history")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ]
    return InlineKeyboardMarkup(keyboard)


def coin_side_menu() -> InlineKeyboardMarkup:
    """Choose heads or tails."""
    keyboard = [
        [InlineKeyboardButton("🪙 HEADS", callback_data="side:heads")],
        [InlineKeyboardButton("🎯 TAILS", callback_data="side:tails")],
        [InlineKeyboardButton("« Back", callback_data="back")],
    ]
    return InlineKeyboardMarkup(keyboard)


def amount_menu() -> InlineKeyboardMarkup:
    """Quick amount selection."""
    keyboard = [
        [
            InlineKeyboardButton("0.1 SOL", callback_data="amount:0.1"),
            InlineKeyboardButton("0.5 SOL", callback_data="amount:0.5"),
        ],
        [
            InlineKeyboardButton("1 SOL", callback_data="amount:1.0"),
            InlineKeyboardButton("5 SOL", callback_data="amount:5.0"),
        ],
        [
            InlineKeyboardButton("10 SOL", callback_data="amount:10.0"),
            InlineKeyboardButton("💵 Custom", callback_data="amount:custom"),
        ],
        [InlineKeyboardButton("« Back", callback_data="back")],
    ]
    return InlineKeyboardMarkup(keyboard)


def confirm_game_menu(game_type: str) -> InlineKeyboardMarkup:
    """Confirm game before playing."""
    keyboard = [
        [InlineKeyboardButton("✅ Confirm & Play", callback_data=f"confirm_{game_type}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="back")],
    ]
    return InlineKeyboardMarkup(keyboard)


def wager_list_menu(wagers: list, page: int = 0) -> InlineKeyboardMarkup:
    """Display list of open wagers."""
    keyboard = []

    # Add wager buttons (5 per page)
    start_idx = page * 5
    end_idx = start_idx + 5

    for wager in wagers[start_idx:end_idx]:
        text = f"💰 {wager.amount} SOL - {wager.creator_side.value.upper()}"
        keyboard.append([InlineKeyboardButton(text, callback_data=f"wager:{wager.wager_id}")])

    # Navigation
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"wagers_page:{page-1}"))
    if end_idx < len(wagers):
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"wagers_page:{page+1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data="open_wagers")])
    keyboard.append([InlineKeyboardButton("« Back", callback_data="back")])

    return InlineKeyboardMarkup(keyboard)


def wager_detail_menu(wager_id: str, is_creator: bool = False) -> InlineKeyboardMarkup:
    """Menu for a specific wager."""
    if is_creator:
        keyboard = [
            [InlineKeyboardButton("❌ Cancel Wager", callback_data=f"cancel_wager:{wager_id}")],
            [InlineKeyboardButton("« Back", callback_data="open_wagers")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("✅ Accept Wager", callback_data=f"accept_wager:{wager_id}")],
            [InlineKeyboardButton("« Back", callback_data="open_wagers")],
        ]
    return InlineKeyboardMarkup(keyboard)


def wallet_menu() -> InlineKeyboardMarkup:
    """Wallet management menu."""
    keyboard = [
        [InlineKeyboardButton("📥 Deposit", callback_data="deposit")],
        [InlineKeyboardButton("📤 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton("🔄 Refresh Balance", callback_data="refresh_balance")],
        [InlineKeyboardButton("« Back", callback_data="back")],
    ]
    return InlineKeyboardMarkup(keyboard)


def history_menu(page: int = 0) -> InlineKeyboardMarkup:
    """Game history navigation."""
    keyboard = []

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Prev", callback_data=f"history_page:{page-1}"))
    nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"history_page:{page+1}"))

    keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("« Back", callback_data="back")])

    return InlineKeyboardMarkup(keyboard)


def cancel_button() -> InlineKeyboardMarkup:
    """Simple cancel button."""
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back")]]
    return InlineKeyboardMarkup(keyboard)
