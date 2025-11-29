"""
Telegram bot for Solana Coinflip game.
"""
import os
import logging
import asyncio
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

# Import our modules
from database import Database, User, GameType, CoinSide, Wager
from game import (
    play_pvp_game_with_escrows,
    generate_wallet,
    get_sol_balance,
    transfer_sol,
    TRANSACTION_FEE,
    create_escrow_wallet,
    payout_from_escrow,
    collect_fees_from_escrow,
    refund_from_escrow,
    check_escrow_balance,
)
from utils import (
    encrypt_secret,
    decrypt_secret,
    format_sol,
    format_win_rate,
    truncate_address,
    format_tx_link,
)
import menus
import uuid

# Load environment
load_dotenv()

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
RPC_URL = os.getenv("RPC_URL")
HOUSE_WALLET_SECRET = os.getenv("HOUSE_WALLET_SECRET")
TREASURY_WALLET = os.getenv("TREASURY_WALLET")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

# Database
db = Database()

# Conversation states
AWAITING_AMOUNT, AWAITING_WITHDRAW_ADDRESS, AWAITING_WITHDRAW_AMOUNT = range(3)

# User session storage
user_sessions = {}


def get_session(user_id: int) -> dict:
    """Get or create user session."""
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    return user_sessions[user_id]


async def ensure_user(update: Update) -> User:
    """Ensure user exists in database."""
    user_id = update.effective_user.id
    username = update.effective_user.username

    user = db.get_user(user_id)

    if not user:
        # Create new user with custodial wallet
        wallet_addr, wallet_secret = generate_wallet()
        encrypted_secret = encrypt_secret(wallet_secret, ENCRYPTION_KEY)

        user = User(
            user_id=user_id,
            platform="telegram",
            wallet_address=wallet_addr,
            encrypted_secret=encrypted_secret,
            username=username,
        )
        db.save_user(user)
        logger.info(f"Created new user {user_id} with wallet {wallet_addr}")

    return user


# ===== COMMAND HANDLERS =====

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = await ensure_user(update)

    welcome_msg = (
        "⚔️ *Welcome to Coinflip PVP!*\n\n"
        "The fairest PVP coinflip platform on Solana.\n\n"
        "*How to Play:*\n"
        "• ⚔️ *Create Wager*: Challenge other players\n"
        "• 🎯 *Accept Wagers*: Join existing games\n\n"
        "*Features:*\n"
        "✅ Provably fair using Solana blockhash\n"
        "✅ Instant payouts\n"
        "✅ Only 2% platform fee\n"
        "✅ Secure escrow wallets\n\n"
        f"Your wallet: `{truncate_address(user.wallet_address)}`"
    )

    await update.message.reply_text(
        welcome_msg,
        parse_mode="Markdown",
        reply_markup=menus.main_menu()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_msg = (
        "❓ *Help & Information*\n\n"
        "*PVP Coinflip:*\n"
        "Create or accept wagers against other players.\n"
        "Winner takes 98% of the pot (2% platform fee).\n\n"
        "*How It Works:*\n"
        "1. Create a wager (choose side + amount)\n"
        "2. Funds held in secure escrow\n"
        "3. Another player accepts\n"
        "4. Coin flips using Solana blockhash\n"
        "5. Winner gets paid instantly!\n\n"
        "*Wallet:*\n"
        "• Deposit SOL to play\n"
        "• Withdraw anytime\n"
        "• Your keys are encrypted\n\n"
        "*Fair Play:*\n"
        "All flips use Solana blockhash for randomness.\n"
        "Every game can be verified on-chain!"
    )

    await update.message.reply_text(
        help_msg,
        parse_mode="Markdown",
        reply_markup=menus.main_menu()
    )


# ===== CALLBACK HANDLERS =====

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    user = await ensure_user(update)
    session = get_session(user.user_id)

    # Route to appropriate handler
    if data == "back" or data == "main_menu":
        await show_main_menu(update, context)

    elif data.startswith("side:"):
        await handle_side_selection(update, context, data)

    elif data.startswith("amount:"):
        await handle_amount_selection(update, context, data)

    elif data == "create_wager":
        await create_wager_start(update, context)

    elif data == "confirm_create_wager":
        await execute_create_wager(update, context)

    elif data == "open_wagers":
        await show_open_wagers(update, context)

    elif data.startswith("wager:"):
        await show_wager_detail(update, context, data)

    elif data.startswith("accept_wager:"):
        await accept_wager(update, context, data)

    elif data.startswith("cancel_wager:"):
        await cancel_wager(update, context, data)

    elif data == "wallet":
        await show_wallet(update, context)

    elif data == "deposit":
        await show_deposit(update, context)

    elif data == "withdraw":
        await withdraw_start(update, context)

    elif data == "refresh_balance":
        await refresh_balance(update, context)

    elif data == "stats":
        await show_stats(update, context)

    elif data == "my_wagers":
        await show_my_wagers(update, context)

    elif data == "history":
        await show_history(update, context)

    elif data == "help":
        await help_callback(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu."""
    await update.callback_query.edit_message_text(
        "🎲 *Solana Coinflip*\n\nChoose an option:",
        parse_mode="Markdown",
        reply_markup=menus.main_menu()
    )


# ===== SIDE AND AMOUNT SELECTION =====


async def handle_side_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Handle coin side selection."""
    side = data.split(":")[1]
    session = get_session(update.effective_user.id)
    session["side"] = side
    session["step"] = "choose_amount"

    side_emoji = "🪙" if side == "heads" else "🎯"

    await update.callback_query.edit_message_text(
        f"{side_emoji} *You chose {side.upper()}*\n\nSelect wager amount:",
        parse_mode="Markdown",
        reply_markup=menus.amount_menu()
    )


async def handle_amount_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Handle amount selection."""
    session = get_session(update.effective_user.id)
    amount_str = data.split(":")[1]

    if amount_str == "custom":
        await update.callback_query.edit_message_text(
            "💵 Enter custom amount in SOL (e.g. 0.5):",
            parse_mode="Markdown",
            reply_markup=menus.cancel_button()
        )
        return AWAITING_AMOUNT

    amount = float(amount_str)
    session["amount"] = amount

    # Show confirmation
    await show_game_confirmation(update, context)


async def show_game_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show PVP wager confirmation."""
    user = await ensure_user(update)
    session = get_session(user.user_id)

    side = session.get("side", "heads")
    amount = session.get("amount", 0.1)

    # Get current balance
    balance = await get_sol_balance(RPC_URL, user.wallet_address)

    side_emoji = "🪙" if side == "heads" else "🎯"
    total_required = amount + TRANSACTION_FEE

    potential_win = (amount * 2) * 0.98  # 2% fee

    msg = (
        f"⚔️ *Create PVP Wager*\n\n"
        f"{side_emoji} Side: *{side.upper()}*\n"
        f"💰 Wager: *{format_sol(amount)} SOL*\n"
        f"💳 Fee: *{format_sol(TRANSACTION_FEE)} SOL*\n"
        f"💎 Potential Win: *{format_sol(potential_win)} SOL*\n\n"
        f"📊 Your Balance: `{format_sol(balance)} SOL`\n"
        f"📊 Required: `{format_sol(total_required)} SOL`\n\n"
    )

    if balance < total_required:
        msg += "❌ *Insufficient balance!*\n\nPlease deposit SOL first."
        keyboard = [
            [InlineKeyboardButton("📥 Deposit", callback_data="deposit")],
            [InlineKeyboardButton("« Back", callback_data="back")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
    else:
        msg += "Create this wager?"
        reply_markup = menus.confirm_game_menu("create_wager")

    await update.callback_query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


# ===== WALLET =====

async def show_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show wallet info."""
    user = await ensure_user(update)
    balance = await get_sol_balance(RPC_URL, user.wallet_address)

    msg = (
        f"💰 *Your Wallet*\n\n"
        f"Address:\n`{user.wallet_address}`\n\n"
        f"Balance: *{format_sol(balance)} SOL*\n\n"
        f"Send SOL to your address to deposit.\n"
        f"Use withdraw to cash out."
    )

    await update.callback_query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=menus.wallet_menu()
    )


async def show_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show deposit instructions."""
    user = await ensure_user(update)

    msg = (
        f"📥 *Deposit SOL*\n\n"
        f"Send SOL to your wallet address:\n\n"
        f"`{user.wallet_address}`\n\n"
        f"Deposits are instant!\n"
        f"Minimum: 0.01 SOL"
    )

    await update.callback_query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=menus.wallet_menu()
    )


async def refresh_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Refresh wallet balance."""
    user = await ensure_user(update)
    balance = await get_sol_balance(RPC_URL, user.wallet_address)

    await update.callback_query.answer(f"Balance: {format_sol(balance)} SOL", show_alert=True)


# ===== STATS =====

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user statistics."""
    user = await ensure_user(update)
    balance = await get_sol_balance(RPC_URL, user.wallet_address)

    win_rate = format_win_rate(user.games_played, user.games_won)
    net_profit = user.total_won - user.total_lost

    profit_emoji = "📈" if net_profit >= 0 else "📉"

    msg = (
        f"📊 *Your Statistics*\n\n"
        f"💰 Balance: *{format_sol(balance)} SOL*\n\n"
        f"🎮 Games Played: {user.games_played}\n"
        f"🏆 Games Won: {user.games_won}\n"
        f"📊 Win Rate: *{win_rate}*\n\n"
        f"💎 Total Wagered: {format_sol(user.total_wagered)} SOL\n"
        f"✅ Total Won: {format_sol(user.total_won)} SOL\n"
        f"❌ Total Lost: {format_sol(user.total_lost)} SOL\n"
        f"{profit_emoji} Net P/L: *{format_sol(abs(net_profit))} SOL*"
    )

    await update.callback_query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=menus.main_menu()
    )


# ===== HISTORY =====

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show game history."""
    user = await ensure_user(update)
    games = db.get_user_games(user.user_id, limit=10)

    if not games:
        msg = "📜 *Game History*\n\nNo games yet. Start playing!"
    else:
        msg = "📜 *Recent Games*\n\n"

        for game in games[:5]:
            won = (game.winner_id == user.user_id)
            result_emoji = "✅" if won else "❌"
            game_type = "House" if game.game_type == GameType.HOUSE else "PVP"

            msg += (
                f"{result_emoji} {game_type} - {format_sol(game.amount)} SOL\n"
                f"   Result: {game.result.value.upper() if game.result else 'N/A'}\n\n"
            )

    await update.callback_query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=menus.main_menu()
    )


async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help from callback."""
    help_msg = (
        "❓ *Help*\n\n"
        "PVP coinflip on Solana.\n"
        "2% platform fee on winnings.\n"
        "All games provably fair!"
    )

    await update.callback_query.edit_message_text(
        help_msg,
        parse_mode="Markdown",
        reply_markup=menus.main_menu()
    )


# ===== WAGER SYSTEM (PVP) =====

async def create_wager_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start creating a PVP wager."""
    session = get_session(update.effective_user.id)
    session["game_mode"] = "create_wager"
    session["step"] = "choose_side"

    await update.callback_query.edit_message_text(
        "⚔️ *Create PVP Wager*\n\nChoose your side:",
        parse_mode="Markdown",
        reply_markup=menus.coin_side_menu()
    )


async def execute_create_wager(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Execute create wager with isolated escrow wallet.

    SECURITY: Creates unique escrow wallet and collects deposit before marking wager as open.
    """
    user = await ensure_user(update)
    session = get_session(user.user_id)

    side = CoinSide(session.get("side", "heads"))
    amount = session.get("amount", 0.1)

    # Check balance (wager + transaction fee)
    total_required = amount + TRANSACTION_FEE
    balance = await get_sol_balance(RPC_URL, user.wallet_address)
    if balance < total_required:
        await update.callback_query.edit_message_text(
            f"❌ *Insufficient Balance*\n\n"
            f"Required: *{format_sol(total_required)} SOL*\n"
            f"({format_sol(amount)} wager + {format_sol(TRANSACTION_FEE)} fee)\n\n"
            f"Available: *{format_sol(balance)} SOL*\n\n"
            f"Please deposit more SOL first.",
            parse_mode="Markdown",
            reply_markup=menus.main_menu()
        )
        return

    await update.callback_query.edit_message_text(
        "⚔️ *Creating wager...*\n\n"
        "🔒 Generating secure escrow wallet...\n"
        "💸 Collecting deposit...\n\n"
        "Please wait...",
        parse_mode="Markdown"
    )

    try:
        # Generate wager ID
        wager_id = f"wager_{uuid.uuid4().hex[:12]}"

        # SECURITY: Create unique escrow wallet and collect deposit
        escrow_address, encrypted_secret, deposit_tx = await create_escrow_wallet(
            RPC_URL,
            ENCRYPTION_KEY,
            amount,
            TRANSACTION_FEE,
            user,
            user.wallet_address,
            None,  # Telegram users don't provide signature (custodial)
            wager_id,
            db
        )

        logger.info(f"[ESCROW] Created wager {wager_id} with escrow {escrow_address}")

        # Create wager with escrow details
        wager = Wager(
            wager_id=wager_id,
            creator_id=user.user_id,
            creator_wallet=user.wallet_address,
            creator_side=side,
            amount=amount,
            status="open",
            creator_escrow_address=escrow_address,
            creator_escrow_secret=encrypted_secret,
            creator_deposit_tx=deposit_tx,
        )

        # Save to database
        db.save_wager(wager)

        logger.info(f"Wager created: {wager_id} by user {user.user_id} - {amount} SOL on {side.value} (escrow: {escrow_address})")

        # Show success message
        side_emoji = "🪙" if side == CoinSide.HEADS else "🎯"
        msg = (
            f"✅ *Wager Created!*\n\n"
            f"{side_emoji} Side: *{side.value.upper()}*\n"
            f"💰 Amount: *{format_sol(amount)} SOL*\n"
            f"💳 Fee: *{format_sol(TRANSACTION_FEE)} SOL*\n\n"
            f"🔒 Funds secured in escrow: `{truncate_address(escrow_address)}`\n\n"
            f"Your wager is now live!\n"
            f"Other players can accept it from the Open Wagers list.\n\n"
            f"You can view it in 'My Wagers' or cancel it anytime.\n"
            f"(Cancellation refunds wager, keeps fee)"
        )

        keyboard = [
            [InlineKeyboardButton("🎯 View Open Wagers", callback_data="open_wagers")],
            [InlineKeyboardButton("🎮 My Wagers", callback_data="my_wagers")],
            [InlineKeyboardButton("« Main Menu", callback_data="back")],
        ]

        await update.callback_query.edit_message_text(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        logger.error(f"Create wager failed: {e}")
        await update.callback_query.edit_message_text(
            f"❌ *Wager Creation Failed*\n\nError: {str(e)}\n\nPlease try again.",
            parse_mode="Markdown",
            reply_markup=menus.main_menu()
        )


async def show_open_wagers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show open PVP wagers."""
    user = await ensure_user(update)
    wagers = db.get_open_wagers(limit=20)

    # Filter out user's own wagers
    other_wagers = [w for w in wagers if w.creator_id != user.user_id]

    if not other_wagers:
        msg = (
            "🎯 *Open Wagers*\n\n"
            "No open wagers available right now.\n\n"
            "Be the first to create one!"
        )
        keyboard = [
            [InlineKeyboardButton("⚔️ Create Wager", callback_data="create_wager")],
            [InlineKeyboardButton("« Back", callback_data="back")],
        ]
        await update.callback_query.edit_message_text(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        msg = f"🎯 *Open Wagers*\n\n{len(other_wagers)} wager(s) available:\n\nTap to view details:"
        await update.callback_query.edit_message_text(
            msg,
            parse_mode="Markdown",
            reply_markup=menus.wager_list_menu(other_wagers)
        )


async def show_wager_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Show wager details."""
    user = await ensure_user(update)
    wager_id = data.split(":")[1]

    # Get wager from database
    wagers = db.get_open_wagers(limit=100)
    wager = next((w for w in wagers if w.wager_id == wager_id), None)

    if not wager or wager.status != "open":
        await update.callback_query.answer("This wager is no longer available.", show_alert=True)
        await show_open_wagers(update, context)
        return

    # Get creator info
    creator = db.get_user(wager.creator_id)
    creator_name = creator.username or f"User {wager.creator_id}"

    # Calculate potential winnings
    total_pot = wager.amount * 2
    fee = total_pot * 0.02
    payout = total_pot - fee

    side_emoji = "🪙" if wager.creator_side == CoinSide.HEADS else "🎯"
    opponent_side = "TAILS" if wager.creator_side == CoinSide.HEADS else "HEADS"
    opponent_emoji = "🎯" if wager.creator_side == CoinSide.HEADS else "🪙"

    msg = (
        f"⚔️ *PVP Wager Details*\n\n"
        f"Created by: @{creator_name}\n\n"
        f"{side_emoji} Creator's Side: *{wager.creator_side.value.upper()}*\n"
        f"{opponent_emoji} Your Side: *{opponent_side}*\n\n"
        f"💰 Wager Amount: *{format_sol(wager.amount)} SOL*\n"
        f"💎 Total Pot: *{format_sol(total_pot)} SOL*\n"
        f"📊 Fee (2%): {format_sol(fee)} SOL\n"
        f"🏆 Winner Gets: *{format_sol(payout)} SOL*\n\n"
        f"Accept this wager?"
    )

    is_creator = (wager.creator_id == user.user_id)
    await update.callback_query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=menus.wager_detail_menu(wager_id, is_creator)
    )


async def accept_wager(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Accept a PVP wager with isolated escrow wallets.

    SECURITY: Creates unique escrow wallet for acceptor and uses play_pvp_game_with_escrows().
    """
    user = await ensure_user(update)
    wager_id = data.split(":")[1]

    # Get wager
    wagers = db.get_open_wagers(limit=100)
    wager = next((w for w in wagers if w.wager_id == wager_id), None)

    if not wager or wager.status != "open":
        await update.callback_query.answer("This wager is no longer available.", show_alert=True)
        await show_open_wagers(update, context)
        return

    # Can't accept own wager
    if wager.creator_id == user.user_id:
        await update.callback_query.answer("You can't accept your own wager!", show_alert=True)
        return

    # Check balance (wager + transaction fee)
    total_required = wager.amount + TRANSACTION_FEE
    balance = await get_sol_balance(RPC_URL, user.wallet_address)
    if balance < total_required:
        await update.callback_query.answer(
            f"Insufficient balance! Need {format_sol(total_required)} SOL ({format_sol(wager.amount)} wager + {format_sol(TRANSACTION_FEE)} fee)",
            show_alert=True
        )
        return

    await update.callback_query.edit_message_text(
        "⚔️ *Accepting wager...*\n\n"
        "🔒 Creating your escrow...\n"
        "💸 Collecting deposit...\n\n"
        "Please wait...",
        parse_mode="Markdown"
    )

    try:
        # Get creator
        creator = db.get_user(wager.creator_id)
        if not creator:
            raise Exception("Creator not found")

        # SECURITY: Change status to "accepting" (prevent race conditions)
        wager.status = "accepting"
        wager.acceptor_id = user.user_id
        db.save_wager(wager)

        logger.info(f"[ESCROW] Acceptor {user.user_id} accepting wager {wager_id}, creating escrow...")

        # SECURITY: Create acceptor's escrow wallet and collect deposit
        acceptor_escrow_address, acceptor_encrypted_secret, acceptor_deposit_tx = await create_escrow_wallet(
            RPC_URL,
            ENCRYPTION_KEY,
            wager.amount,
            TRANSACTION_FEE,
            user,
            user.wallet_address,
            None,  # Telegram users don't provide signature (custodial)
            wager_id,
            db
        )

        logger.info(f"[ESCROW] Acceptor escrow created: {acceptor_escrow_address}")

        # Update wager with acceptor's escrow details
        wager.acceptor_escrow_address = acceptor_escrow_address
        wager.acceptor_escrow_secret = acceptor_encrypted_secret
        wager.acceptor_deposit_tx = acceptor_deposit_tx
        wager.status = "accepted"
        db.save_wager(wager)

        # Decrypt house wallet (for receiving fees)
        house_secret = decrypt_secret(HOUSE_WALLET_SECRET, ENCRYPTION_KEY)

        await update.callback_query.edit_message_text(
            "⚔️ *Escrows secured!*\n\n🎲 Flipping coin...\n\nPlease wait...",
            parse_mode="Markdown"
        )

        # Play PVP game with ISOLATED ESCROWS (NEW SECURE METHOD)
        game = await play_pvp_game_with_escrows(
            RPC_URL,
            house_secret,
            TREASURY_WALLET,
            creator,
            wager.creator_side,
            wager.creator_escrow_secret,
            wager.creator_escrow_address,
            user,
            wager.acceptor_escrow_secret,
            wager.acceptor_escrow_address,
            wager.amount
        )

        logger.info(f"[ESCROW] PVP game {game.game_id} completed with escrows")

        # Link game to wager
        wager.game_id = game.game_id
        db.save_wager(wager)

        # Save game
        db.save_game(game)

        # Update both players' stats
        creator.games_played += 1
        creator.total_wagered += wager.amount
        user.games_played += 1
        user.total_wagered += wager.amount

        won = (game.winner_id == user.user_id)
        payout = (wager.amount * 2) * 0.98

        if won:
            user.games_won += 1
            user.total_won += payout
            creator.total_lost += wager.amount
        else:
            creator.games_won += 1
            creator.total_won += payout
            user.total_lost += wager.amount

        db.save_user(creator)
        db.save_user(user)

        # Notify the creator that their wager was accepted (Telegram push notification)
        try:
            creator_msg = (
                f"🔔 *Your Wager Was Accepted!*\n\n"
                f"Someone just accepted your {format_sol(wager.amount)} SOL wager!\n"
                f"Game is complete. "
            )
            if game.winner_id == creator.user_id:
                creator_msg += f"🎉 You WON {format_sol(payout)} SOL!"
            else:
                creator_msg += f"😔 You lost {format_sol(wager.amount)} SOL."

            await context.bot.send_message(
                chat_id=creator.user_id,
                text=creator_msg,
                parse_mode="Markdown"
            )
        except Exception as notify_error:
            logger.warning(f"Failed to notify creator: {notify_error}")

        # Show result
        await show_pvp_result(update, context, game, wager, won)

    except Exception as e:
        logger.error(f"Accept wager failed: {e}")
        # Revert wager status
        wager.status = "open"
        wager.acceptor_id = None
        db.save_wager(wager)

        await update.callback_query.edit_message_text(
            f"❌ *Wager Acceptance Failed*\n\nError: {str(e)}\n\nThe wager is still open.",
            parse_mode="Markdown",
            reply_markup=menus.main_menu()
        )


async def show_pvp_result(update: Update, context: ContextTypes.DEFAULT_TYPE, game, wager, won: bool):
    """Show PVP game result."""
    result_emoji = "🪙" if game.result == CoinSide.HEADS else "🎯"
    payout = (game.amount * 2) * 0.98

    if won:
        msg = (
            f"🎉 *YOU WON THE PVP BATTLE!*\n\n"
            f"{result_emoji} Result: *{game.result.value.upper()}*\n"
            f"💰 Your Wager: {format_sol(game.amount)} SOL\n"
            f"💎 Won: *{format_sol(payout)} SOL*\n\n"
        )
        if game.payout_tx:
            msg += f"📝 [View Transaction]({format_tx_link(game.payout_tx)})\n\n"
    else:
        msg = (
            f"😔 *YOU LOST*\n\n"
            f"{result_emoji} Result: *{game.result.value.upper()}*\n"
            f"💰 Lost: {format_sol(game.amount)} SOL\n\n"
            f"Better luck next time!\n\n"
        )

    msg += f"🔍 *Provably Fair*\nBlockhash: `{game.blockhash[:16]}...`\n\nPlay again?"

    keyboard = [
        [InlineKeyboardButton("⚔️ Create Wager", callback_data="create_wager")],
        [InlineKeyboardButton("🎯 Open Wagers", callback_data="open_wagers")],
        [InlineKeyboardButton("« Main Menu", callback_data="back")],
    ]

    await update.callback_query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )


async def cancel_wager(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Cancel a wager with escrow refund.

    SECURITY: Refunds wager amount to creator, keeps 0.025 SOL transaction fee.
    """
    user = await ensure_user(update)
    wager_id = data.split(":")[1]

    # Get wager
    wagers = db.get_user_wagers(user.user_id)
    wager = next((w for w in wagers if w.wager_id == wager_id), None)

    if not wager:
        await update.callback_query.answer("Wager not found.", show_alert=True)
        return

    if wager.creator_id != user.user_id:
        await update.callback_query.answer("You can't cancel someone else's wager!", show_alert=True)
        return

    if wager.status != "open":
        await update.callback_query.answer("This wager can't be cancelled.", show_alert=True)
        return

    # Verify escrow exists
    if not wager.creator_escrow_address or not wager.creator_escrow_secret:
        # Old wager without escrow - just mark as cancelled
        wager.status = "cancelled"
        db.save_wager(wager)
        logger.warning(f"[CANCEL] Wager {wager_id} has no escrow, just marking cancelled")
        await update.callback_query.edit_message_text(
            f"✅ *Wager Cancelled*\n\nYour wager of {format_sol(wager.amount)} SOL has been cancelled.",
            parse_mode="Markdown",
            reply_markup=menus.main_menu()
        )
        return

    await update.callback_query.edit_message_text(
        "❌ *Cancelling wager...*\n\n💸 Processing refund...\n\nPlease wait...",
        parse_mode="Markdown"
    )

    try:
        # Decrypt house wallet
        house_secret = decrypt_secret(HOUSE_WALLET_SECRET, ENCRYPTION_KEY)
        from game.coinflip import get_house_wallet_address
        house_wallet = get_house_wallet_address(house_secret)

        # Decrypt escrow secret
        creator_escrow_secret = decrypt_secret(wager.creator_escrow_secret, ENCRYPTION_KEY)

        logger.info(f"[CANCEL] Refunding wager {wager_id} from escrow {wager.creator_escrow_address}")

        # Refund from escrow (returns wager, keeps 0.025 SOL fee)
        refund_tx, fee_tx = await refund_from_escrow(
            RPC_URL,
            creator_escrow_secret,
            wager.creator_escrow_address,
            user.wallet_address,
            house_wallet,
            wager.amount,
            TRANSACTION_FEE
        )

        logger.info(f"[CANCEL] Refunded {wager.amount} SOL (tx: {refund_tx}), collected fee (tx: {fee_tx})")

        # Mark wager as cancelled
        wager.status = "cancelled"
        db.save_wager(wager)

        # Success message
        msg = (
            f"✅ *Wager Cancelled*\n\n"
            f"💰 Refunded: *{format_sol(wager.amount)} SOL*\n"
            f"💳 Fee Kept: *{format_sol(TRANSACTION_FEE)} SOL*\n\n"
            f"Your wager has been cancelled and funds returned.\n\n"
        )
        if refund_tx:
            msg += f"📝 [View Refund Transaction]({format_tx_link(refund_tx)})"

        await update.callback_query.edit_message_text(
            msg,
            parse_mode="Markdown",
            reply_markup=menus.main_menu()
        )

    except Exception as e:
        logger.error(f"Cancel wager failed: {e}")
        await update.callback_query.edit_message_text(
            f"❌ *Cancellation Failed*\n\nError: {str(e)}\n\nPlease try again or contact support.",
            parse_mode="Markdown",
            reply_markup=menus.main_menu()
        )


async def show_my_wagers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's created wagers."""
    user = await ensure_user(update)
    wagers = db.get_user_wagers(user.user_id)

    # Filter open wagers
    open_wagers = [w for w in wagers if w.status == "open"]

    if not open_wagers:
        msg = (
            "🎮 *My Wagers*\n\n"
            "You don't have any open wagers.\n\n"
            "Create one to challenge other players!"
        )
        keyboard = [
            [InlineKeyboardButton("⚔️ Create Wager", callback_data="create_wager")],
            [InlineKeyboardButton("« Back", callback_data="back")],
        ]
    else:
        msg = f"🎮 *My Wagers*\n\n{len(open_wagers)} open wager(s):\n"
        keyboard = []

        for wager in open_wagers[:10]:
            side_emoji = "🪙" if wager.creator_side == CoinSide.HEADS else "🎯"
            text = f"{side_emoji} {format_sol(wager.amount)} SOL - {wager.creator_side.value.upper()}"
            keyboard.append([InlineKeyboardButton(text, callback_data=f"wager:{wager.wager_id}")])

        keyboard.append([InlineKeyboardButton("« Back", callback_data="back")])

    await update.callback_query.edit_message_text(
        msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start withdrawal process."""
    await update.callback_query.answer("Withdrawal feature coming soon!", show_alert=True)


# ===== MAIN =====

def main():
    """Start the bot."""
    logger.info("="*50)
    logger.info("Solana Coinflip Bot Starting...")
    logger.info("="*50)

    # Create application
    app = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_callback))

    # Start bot
    logger.info("✅ Coinflip Bot is ready!")
    logger.info("Press Ctrl+C to stop")
    logger.info("="*50)

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
