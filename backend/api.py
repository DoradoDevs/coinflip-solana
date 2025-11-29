"""
FastAPI web backend for Solana Coinflip game.
Supports both custodial (like Telegram) and wallet connect modes.
"""
import os
import logging
from typing import List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import our modules
from database import Database, User, Game, Wager, GameType, CoinSide, GameStatus, UsedSignature
from game import (
    play_house_game,
    play_pvp_game_with_escrows,
    generate_wallet,
    get_sol_balance,
    transfer_sol,
    get_latest_blockhash,
    verify_deposit_transaction,
    TRANSACTION_FEE,
    create_escrow_wallet,
    payout_from_escrow,
    collect_fees_from_escrow,
    refund_from_escrow,
    check_escrow_balance,
)
from game.coinflip import get_house_wallet_address
from utils import (
    encrypt_secret,
    decrypt_secret,
    format_sol,
    format_win_rate,
)
from notifications import notify_wager_accepted
from referrals import claim_referral_earnings, get_referral_escrow_balance

# Load environment
load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
RPC_URL = os.getenv("RPC_URL")
HOUSE_WALLET_SECRET = os.getenv("HOUSE_WALLET_SECRET")
TREASURY_WALLET = os.getenv("TREASURY_WALLET")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

# Database
db = Database()

# SECURITY: Emergency stop flag
def is_emergency_stop_enabled() -> bool:
    """Check if emergency stop is enabled."""
    return os.path.exists("EMERGENCY_STOP")

def check_emergency_stop():
    """Raise exception if emergency stop enabled."""
    if is_emergency_stop_enabled():
        raise HTTPException(
            status_code=503,
            detail="Platform is temporarily unavailable for maintenance. Please try again later."
        )

# SECURITY: Simple in-memory rate limiter
# Format: {ip_address: {endpoint: [(timestamp1, timestamp2, ...)]}}
rate_limit_store = defaultdict(lambda: defaultdict(list))

def check_rate_limit(request: Request, endpoint: str, max_requests: int, window_seconds: int):
    """Simple rate limiter using IP address.

    Args:
        request: FastAPI request object
        endpoint: Endpoint identifier (e.g., "quick_flip")
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds

    Raises:
        HTTPException: If rate limit exceeded
    """
    client_ip = request.client.host
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=window_seconds)

    # Get request history for this IP + endpoint
    requests = rate_limit_store[client_ip][endpoint]

    # Remove old requests outside the window
    requests = [ts for ts in requests if ts > window_start]
    rate_limit_store[client_ip][endpoint] = requests

    # Check if limit exceeded
    if len(requests) >= max_requests:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {max_requests} requests per {window_seconds} seconds."
        )

    # Add current request
    requests.append(now)

# FastAPI app
app = FastAPI(title="Solana Coinflip API", version="1.0.0")

# CORS - SECURITY: Restrict to your domain in production
# Development: allow_origins=["*"]
# Production: allow_origins=["https://yourdomain.com", "https://www.yourdomain.com"]
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Only needed methods
    allow_headers=["*"],
)

# Serve frontend
app.mount("/static", StaticFiles(directory="../frontend"), name="static")


# ===== MODELS =====

class CreateUserRequest(BaseModel):
    wallet_address: str


class QuickFlipRequest(BaseModel):
    wallet_address: str
    side: str  # "heads" or "tails"
    amount: float
    deposit_tx_signature: Optional[str] = None  # Required for Web users (Phantom/Solflare)


class CreateWagerRequest(BaseModel):
    creator_wallet: str
    side: str
    amount: float
    deposit_tx_signature: Optional[str] = None  # Required for Web users


class AcceptWagerRequest(BaseModel):
    wager_id: str
    acceptor_wallet: str
    deposit_tx_signature: Optional[str] = None  # Required for Web users


class CancelWagerRequest(BaseModel):
    wager_id: str
    creator_wallet: str


class ClaimReferralRequest(BaseModel):
    """Request to claim referral earnings."""
    user_wallet: str  # User's wallet address (for web users)


class UserResponse(BaseModel):
    user_id: int
    wallet_address: Optional[str]
    games_played: int
    games_won: int
    total_wagered: float
    total_won: float
    total_lost: float
    win_rate: str


class GameResponse(BaseModel):
    game_id: str
    game_type: str
    player1_wallet: str
    player2_wallet: Optional[str]
    amount: float
    status: str
    result: Optional[str]
    winner_wallet: Optional[str]
    blockhash: Optional[str]
    created_at: str


class WagerResponse(BaseModel):
    wager_id: str
    creator_wallet: str
    creator_side: str
    amount: float
    status: str
    created_at: str


# ===== UTILITY FUNCTIONS =====

def wallet_to_user_id(wallet_address: str) -> int:
    """Convert wallet address to user ID (hash)."""
    return abs(hash(wallet_address)) % (10 ** 10)


def ensure_web_user(wallet_address: str) -> User:
    """Ensure web user exists."""
    user_id = wallet_to_user_id(wallet_address)
    user = db.get_user(user_id)

    if not user:
        user = User(
            user_id=user_id,
            platform="web",
            connected_wallet=wallet_address,
        )
        db.save_user(user)
        logger.info(f"Created new web user for wallet {wallet_address}")

    return user


# ===== API ENDPOINTS =====

@app.get("/")
async def root():
    """API root."""
    return {
        "name": "Solana Coinflip API",
        "version": "1.0.0",
        "status": "online"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# === USER ENDPOINTS ===

@app.post("/api/user/connect")
async def connect_user(request: CreateUserRequest) -> UserResponse:
    """Connect a web3 wallet."""
    user = ensure_web_user(request.wallet_address)

    return UserResponse(
        user_id=user.user_id,
        wallet_address=user.connected_wallet,
        games_played=user.games_played,
        games_won=user.games_won,
        total_wagered=user.total_wagered,
        total_won=user.total_won,
        total_lost=user.total_lost,
        win_rate=format_win_rate(user.games_played, user.games_won)
    )


@app.get("/api/user/{wallet_address}")
async def get_user_stats(wallet_address: str) -> UserResponse:
    """Get user statistics."""
    user = ensure_web_user(wallet_address)

    return UserResponse(
        user_id=user.user_id,
        wallet_address=user.connected_wallet,
        games_played=user.games_played,
        games_won=user.games_won,
        total_wagered=user.total_wagered,
        total_won=user.total_won,
        total_lost=user.total_lost,
        win_rate=format_win_rate(user.games_played, user.games_won)
    )


@app.get("/api/user/{wallet_address}/balance")
async def get_balance(wallet_address: str):
    """Get wallet SOL balance."""
    try:
        balance = await get_sol_balance(RPC_URL, wallet_address)
        return {"wallet": wallet_address, "balance": balance}
    except Exception as e:
        logger.error(f"Failed to get balance for {wallet_address}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve wallet balance")


# === GAME ENDPOINTS ===

@app.post("/api/game/quick-flip")
async def quick_flip(request: QuickFlipRequest, http_request: Request) -> GameResponse:
    """Play quick flip vs house.

    For Web users: Must provide deposit_tx_signature proving they sent (wager + fee) to house wallet.

    Rate limit: 10 requests per 60 seconds per IP
    """
    # SECURITY: Check emergency stop
    check_emergency_stop()

    # SECURITY: Rate limiting (10 games per minute max)
    check_rate_limit(http_request, "quick_flip", max_requests=10, window_seconds=60)

    try:
        user = ensure_web_user(request.wallet_address)

        # Validate side
        if request.side not in ["heads", "tails"]:
            raise HTTPException(status_code=400, detail="Invalid side. Must be 'heads' or 'tails'")

        # Validate amount
        if request.amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than 0")

        # Decrypt house wallet
        house_secret = decrypt_secret(HOUSE_WALLET_SECRET, ENCRYPTION_KEY)
        house_address = get_house_wallet_address(house_secret)

        # ENFORCE ESCROW FOR WEB USERS
        # Web users must send SOL first and provide transaction signature
        if user.platform == "web":
            if not request.deposit_tx_signature:
                raise HTTPException(
                    status_code=400,
                    detail=f"Web users must first send {request.amount + TRANSACTION_FEE} SOL ({request.amount} wager + {TRANSACTION_FEE} fee) to house wallet {house_address} and provide the transaction signature"
                )

            # Verify the deposit transaction on-chain
            total_required = request.amount + TRANSACTION_FEE
            is_valid = await verify_deposit_transaction(
                RPC_URL,
                request.deposit_tx_signature,
                request.wallet_address,  # sender
                house_address,  # recipient
                total_required  # amount
            )

            if not is_valid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid deposit transaction. Please send exactly {total_required} SOL ({request.amount} wager + {TRANSACTION_FEE} fee) to {house_address}"
                )

            # SECURITY: Check if signature already used (prevent replay attacks)
            if db.signature_already_used(request.deposit_tx_signature):
                used_sig = db.get_used_signature(request.deposit_tx_signature)
                raise HTTPException(
                    status_code=400,
                    detail=f"Transaction signature already used. Each transaction can only be used once."
                )

            logger.info(f"[REAL MAINNET] Verified Web deposit: {total_required} SOL from {request.wallet_address} (tx: {request.deposit_tx_signature})")

        side = CoinSide.HEADS if request.side == "heads" else CoinSide.TAILS

        # Play game
        game = await play_house_game(
            RPC_URL,
            house_secret,
            TREASURY_WALLET,
            user,
            side,
            request.amount
        )

        # Save game
        db.save_game(game)

        # Update user stats
        user.games_played += 1
        user.total_wagered += request.amount

        won = (game.winner_id == user.user_id)
        if won:
            user.games_won += 1
            payout = (request.amount * 2) * 0.98
            user.total_won += payout
        else:
            user.total_lost += request.amount

        db.save_user(user)

        # SECURITY: Mark signature as used (prevent replay attacks)
        if user.platform == "web" and request.deposit_tx_signature:
            db.save_used_signature(UsedSignature(
                signature=request.deposit_tx_signature,
                user_wallet=request.wallet_address,
                used_for=f"quick_flip_{game.game_id}",
                used_at=datetime.utcnow()
            ))
            logger.info(f"[SECURITY] Marked signature {request.deposit_tx_signature[:16]}... as used")

        # Return game result
        winner_wallet = None
        if game.winner_id == user.user_id:
            winner_wallet = user.connected_wallet
        elif game.winner_id == 0:
            winner_wallet = "house"

        return GameResponse(
            game_id=game.game_id,
            game_type=game.game_type.value,
            player1_wallet=game.player1_wallet,
            player2_wallet=game.player2_wallet,
            amount=game.amount,
            status=game.status.value,
            result=game.result.value if game.result else None,
            winner_wallet=winner_wallet,
            blockhash=game.blockhash,
            created_at=game.created_at.isoformat()
        )

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Quick flip failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred processing your game. Please try again.")


@app.get("/api/game/{game_id}")
async def get_game(game_id: str) -> GameResponse:
    """Get game details."""
    game = db.get_game(game_id)

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    winner_wallet = None
    if game.winner_id:
        winner_user = db.get_user(game.winner_id)
        if winner_user:
            winner_wallet = winner_user.connected_wallet or winner_user.wallet_address

    return GameResponse(
        game_id=game.game_id,
        game_type=game.game_type.value,
        player1_wallet=game.player1_wallet,
        player2_wallet=game.player2_wallet,
        amount=game.amount,
        status=game.status.value,
        result=game.result.value if game.result else None,
        winner_wallet=winner_wallet,
        blockhash=game.blockhash,
        created_at=game.created_at.isoformat()
    )


@app.get("/api/game/verify/{game_id}")
async def verify_game(game_id: str):
    """Verify game fairness."""
    from game.coinflip import verify_game_result

    game = db.get_game(game_id)

    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    is_fair = verify_game_result(game)

    return {
        "game_id": game_id,
        "blockhash": game.blockhash,
        "result": game.result.value if game.result else None,
        "is_fair": is_fair,
        "message": "Game result is provably fair!" if is_fair else "Game result verification failed!"
    }


@app.get("/api/games/recent")
async def get_recent_games(limit: int = 10) -> List[GameResponse]:
    """Get recent games (all users)."""
    # This would require a new DB method - simplified for now
    return []


# === WAGER ENDPOINTS (PVP) ===

@app.post("/api/wager/create")
async def create_wager(request: CreateWagerRequest, http_request: Request) -> WagerResponse:
    """Create a PVP wager with isolated escrow wallet.

    SECURITY: Generates unique escrow wallet for creator's deposit.
    Prevents single point of failure.

    Rate limit: 20 requests per 60 seconds per IP
    """
    # SECURITY: Check emergency stop
    check_emergency_stop()

    # SECURITY: Rate limiting (20 wagers per minute max)
    check_rate_limit(http_request, "create_wager", max_requests=20, window_seconds=60)

    try:
        import uuid

        user = ensure_web_user(request.creator_wallet)

        # Validate side
        if request.side not in ["heads", "tails"]:
            raise HTTPException(status_code=400, detail="Invalid side. Must be 'heads' or 'tails'")

        # Validate amount
        if request.amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than 0")

        side = CoinSide.HEADS if request.side == "heads" else CoinSide.TAILS

        # Generate wager ID
        wager_id = f"wager_{uuid.uuid4().hex[:12]}"

        # SECURITY: Create unique escrow wallet for creator
        # This function:
        # - Generates unique wallet
        # - Collects deposit (Telegram) or verifies deposit (Web)
        # - Prevents signature reuse
        # - Returns encrypted secret for storage
        escrow_address, encrypted_secret, deposit_tx = await create_escrow_wallet(
            RPC_URL,
            ENCRYPTION_KEY,
            request.amount,
            TRANSACTION_FEE,
            user,
            request.creator_wallet,
            request.deposit_tx_signature,
            wager_id,
            db
        )

        logger.info(f"[ESCROW] Created wager {wager_id} with escrow {escrow_address}")

        # Create wager with escrow details
        wager = Wager(
            wager_id=wager_id,
            creator_id=user.user_id,
            creator_wallet=request.creator_wallet,
            creator_side=side,
            amount=request.amount,
            status="open",
            creator_escrow_address=escrow_address,
            creator_escrow_secret=encrypted_secret,
            creator_deposit_tx=deposit_tx,
        )

        # Save to database
        db.save_wager(wager)

        logger.info(f"Wager created: {wager_id} by {request.creator_wallet} - {request.amount} SOL on {side.value} (escrow: {escrow_address})")

        # Broadcast to WebSocket clients
        await manager.broadcast({
            "type": "wager_created",
            "wager": {
                "wager_id": wager_id,
                "creator_wallet": request.creator_wallet,
                "side": side.value,
                "amount": request.amount
            }
        })

        return WagerResponse(
            wager_id=wager.wager_id,
            creator_wallet=wager.creator_wallet,
            creator_side=wager.creator_side.value,
            amount=wager.amount,
            status=wager.status,
            created_at=wager.created_at.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create wager failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create wager. Please try again.")


@app.get("/api/wagers/open")
async def get_open_wagers() -> List[WagerResponse]:
    """Get all open wagers from both Telegram and Web users."""
    wagers = db.get_open_wagers(limit=20)

    return [
        WagerResponse(
            wager_id=w.wager_id,
            creator_wallet=w.creator_wallet,
            creator_side=w.creator_side.value,
            amount=w.amount,
            status=w.status,
            created_at=w.created_at.isoformat()
        )
        for w in wagers
    ]


@app.post("/api/wager/accept")
async def accept_wager_endpoint(request: AcceptWagerRequest, http_request: Request) -> GameResponse:
    """Accept a PVP wager with isolated escrow wallets.

    SECURITY: Creates second escrow wallet for acceptor, executes game using both escrows.

    Rate limit: 20 requests per 60 seconds per IP
    """
    # SECURITY: Check emergency stop
    check_emergency_stop()

    # SECURITY: Rate limiting (20 accepts per minute max)
    check_rate_limit(http_request, "accept_wager", max_requests=20, window_seconds=60)

    try:
        user = ensure_web_user(request.acceptor_wallet)

        # Get wager (initial check only)
        wagers = db.get_open_wagers(limit=100)
        wager = next((w for w in wagers if w.wager_id == request.wager_id), None)

        if not wager:
            raise HTTPException(status_code=404, detail="Wager not found")

        # Can't accept own wager
        if wager.creator_wallet == request.acceptor_wallet:
            raise HTTPException(status_code=400, detail="Cannot accept your own wager")

        # Get creator
        creator = db.get_user(wager.creator_id)
        if not creator:
            raise HTTPException(status_code=404, detail="Wager creator not found")

        # SECURITY: Atomically accept wager (prevents double-acceptance race condition)
        # This uses an exclusive database lock to ensure only one user can accept
        accepted = db.atomic_accept_wager(request.wager_id, user.user_id)

        if not accepted:
            raise HTTPException(
                status_code=409,
                detail="Wager already accepted by another user. Please try a different wager."
            )

        # Reload wager to get updated status
        wagers = db.get_open_wagers(limit=100)
        wager = next((w for w in wagers if w.wager_id == request.wager_id), None)
        if not wager:
            # Shouldn't happen, but handle gracefully
            raise HTTPException(status_code=500, detail="Wager disappeared after acceptance")

        logger.info(f"[WAGER] Atomically accepted wager {wager.wager_id} by user {user.user_id}")

        # SECURITY: Create unique escrow wallet for acceptor
        escrow_address, encrypted_secret, deposit_tx = await create_escrow_wallet(
            RPC_URL,
            ENCRYPTION_KEY,
            wager.amount,
            TRANSACTION_FEE,
            user,
            request.acceptor_wallet,
            request.deposit_tx_signature,
            wager.wager_id,
            db
        )

        logger.info(f"[ESCROW] Created acceptor escrow {escrow_address} for wager {wager.wager_id}")

        # Update wager with acceptor's escrow details
        wager.acceptor_escrow_address = escrow_address
        wager.acceptor_escrow_secret = encrypted_secret
        wager.acceptor_deposit_tx = deposit_tx

        # Decrypt house wallet
        house_secret = decrypt_secret(HOUSE_WALLET_SECRET, ENCRYPTION_KEY)

        # Play PVP game with isolated escrow wallets
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

        # Update wager status to accepted/completed
        wager.status = "accepted"
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

        logger.info(f"Web user {request.acceptor_wallet} accepted wager {request.wager_id}")

        # Notify creator if they're a Telegram user (cross-platform notification)
        if creator.platform == "telegram":
            creator_won = (game.winner_id == creator.user_id)
            await notify_wager_accepted(
                creator.user_id,
                wager.amount,
                creator_won,
                payout
            )

        # Broadcast to WebSocket clients
        await manager.broadcast({
            "type": "wager_accepted",
            "wager_id": request.wager_id,
            "game_id": game.game_id,
            "winner": game.winner_id
        })

        # Return game result
        winner_wallet = None
        if game.winner_id == user.user_id:
            winner_wallet = user.connected_wallet
        elif game.winner_id == creator.user_id:
            winner_wallet = creator.connected_wallet or creator.wallet_address

        return GameResponse(
            game_id=game.game_id,
            game_type=game.game_type.value,
            player1_wallet=game.player1_wallet,
            player2_wallet=game.player2_wallet,
            amount=game.amount,
            status=game.status.value,
            result=game.result.value if game.result else None,
            winner_wallet=winner_wallet,
            blockhash=game.blockhash,
            created_at=game.created_at.isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Accept wager failed: {e}", exc_info=True)
        # Revert wager status on error
        if 'wager' in locals():
            wager.status = "open"
            wager.acceptor_id = None
            db.save_wager(wager)
        raise HTTPException(status_code=500, detail="Failed to accept wager. Please try again.")


@app.post("/api/wager/cancel")
async def cancel_wager_endpoint(request: CancelWagerRequest):
    """Cancel a wager with escrow refund (only creator can cancel).

    SECURITY: Refunds wager amount to creator, keeps 0.025 SOL transaction fee.
    """
    try:
        user = ensure_web_user(request.creator_wallet)

        # Get wager
        wagers = db.get_open_wagers(limit=100)
        wager = next((w for w in wagers if w.wager_id == request.wager_id), None)

        if not wager:
            raise HTTPException(status_code=404, detail="Wager not found")

        # Only creator can cancel
        if wager.creator_wallet != request.creator_wallet:
            raise HTTPException(status_code=403, detail="Only the creator can cancel this wager")

        # Can only cancel open wagers
        if wager.status != "open":
            raise HTTPException(status_code=400, detail="Can only cancel open wagers")

        # Verify escrow exists
        if not wager.creator_escrow_address or not wager.creator_escrow_secret:
            # Old wager without escrow - just mark as cancelled
            wager.status = "cancelled"
            db.save_wager(wager)
            logger.warning(f"[CANCEL] Wager {request.wager_id} has no escrow, just marking cancelled")

            await manager.broadcast({
                "type": "wager_cancelled",
                "wager_id": request.wager_id
            })

            return {
                "success": True,
                "message": "Wager cancelled (no escrow refund - old wager)",
                "wager_id": request.wager_id
            }

        # Decrypt house wallet
        house_secret = decrypt_secret(HOUSE_WALLET_SECRET, ENCRYPTION_KEY)
        house_wallet = get_house_wallet_address(house_secret)

        # Decrypt escrow secret
        creator_escrow_secret = decrypt_secret(wager.creator_escrow_secret, ENCRYPTION_KEY)

        logger.info(f"[CANCEL] Refunding wager {request.wager_id} from escrow {wager.creator_escrow_address}")

        # Refund from escrow (returns wager, keeps 0.025 SOL fee)
        refund_tx, fee_tx = await refund_from_escrow(
            RPC_URL,
            creator_escrow_secret,
            wager.creator_escrow_address,
            request.creator_wallet,
            house_wallet,
            wager.amount,
            TRANSACTION_FEE
        )

        logger.info(f"[CANCEL] Refunded {wager.amount} SOL (tx: {refund_tx}), collected fee (tx: {fee_tx})")

        # Mark wager as cancelled
        wager.status = "cancelled"
        db.save_wager(wager)

        logger.info(f"Web user {request.creator_wallet} cancelled wager {request.wager_id}")

        # Broadcast to WebSocket clients
        await manager.broadcast({
            "type": "wager_cancelled",
            "wager_id": request.wager_id,
            "refund_tx": refund_tx,
            "fee_tx": fee_tx
        })

        return {
            "success": True,
            "message": f"Wager cancelled. Refunded {wager.amount} SOL, kept {TRANSACTION_FEE} SOL fee",
            "wager_id": request.wager_id,
            "refund_amount": wager.amount,
            "fee_kept": TRANSACTION_FEE,
            "refund_tx": refund_tx,
            "fee_tx": fee_tx
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cancel wager failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to cancel wager. Please try again.")


@app.post("/api/referral/claim")
async def claim_referral_endpoint(request: ClaimReferralRequest):
    """Claim referral earnings from escrow to payout wallet.

    Takes 1% treasury fee on claims.
    """
    try:
        # Get user
        user = ensure_web_user(request.user_wallet)

        # Check rate limit
        check_rate_limit(request, "claim_referral", max_requests=5, window_seconds=3600)  # 5 claims per hour

        # Get current escrow balance
        escrow_balance = await get_referral_escrow_balance(user, RPC_URL)

        # Claim earnings
        success, message, amount_claimed = await claim_referral_earnings(
            user=user,
            rpc_url=RPC_URL,
            encryption_key=ENCRYPTION_KEY,
            treasury_wallet=TREASURY_WALLET,
            db=db
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        logger.info(f"User {user.user_id} claimed {amount_claimed:.6f} SOL referral earnings")

        return {
            "success": True,
            "message": message,
            "amount_claimed": amount_claimed,
            "escrow_balance_before": escrow_balance,
            "total_lifetime_claimed": user.total_referral_claimed,
            "total_lifetime_earnings": user.referral_earnings
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Claim referral failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to claim referral earnings. Please try again.")


@app.get("/api/referral/balance")
async def get_referral_balance_endpoint(user_wallet: str):
    """Get user's referral earnings balance."""
    try:
        # Get user
        user = ensure_web_user(user_wallet)

        # Get escrow balance
        escrow_balance = await get_referral_escrow_balance(user, RPC_URL)

        return {
            "success": True,
            "user_id": user.user_id,
            "referral_escrow_address": user.referral_payout_escrow_address,
            "current_balance": escrow_balance,
            "total_lifetime_earnings": user.referral_earnings,
            "total_lifetime_claimed": user.total_referral_claimed,
            "total_referrals": user.total_referrals,
            "tier": user.tier,
            "referral_code": user.referral_code
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get referral balance failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get referral balance.")


# === WEBSOCKET FOR LIVE UPDATES ===

class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for live game updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# ===== MAIN =====

if __name__ == "__main__":
    import uvicorn

    logger.info("="*50)
    logger.info("Solana Coinflip API Starting...")
    logger.info("="*50)

    uvicorn.run(app, host="0.0.0.0", port=8000)
