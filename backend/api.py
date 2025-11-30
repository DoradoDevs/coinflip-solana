"""
FastAPI web backend for Solana Coinflip game.
Web-only with wallet connect (non-custodial).
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
from database import Database, User, Game, Wager, GameType, CoinSide, GameStatus, UsedSignature, SupportTicket
import uuid
import secrets
from game import (
    play_pvp_game_with_escrows,
    generate_wallet,
    get_sol_balance,
    transfer_sol,
    get_latest_blockhash,
    verify_deposit_transaction,
    TRANSACTION_FEE,
    create_escrow_wallet,
    verify_escrow_deposit,
    payout_from_escrow,
    collect_fees_from_escrow,
    refund_from_escrow,
    check_escrow_balance,
)
# All game fees go directly to TREASURY_WALLET
# Referral commissions are paid from escrow before sweeping
from utils import (
    encrypt_secret,
    decrypt_secret,
    format_sol,
    format_win_rate,
)
from referrals import claim_referral_earnings, get_referral_escrow_balance, get_claimable_referral_balance, REFERRAL_ESCROW_RENT_MINIMUM
from auth import (
    hash_password,
    verify_password,
    create_session,
    generate_referral_code,
    validate_email,
    validate_username,
    validate_password,
    validate_referral_code,
    calculate_tier,
    TIER_THRESHOLDS,
    TIER_REFERRAL_RATES,
)

# Load environment
load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
RPC_URL = os.getenv("RPC_URL")
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
        endpoint: Endpoint identifier (e.g., "create_wager")
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


class CreateWagerRequest(BaseModel):
    creator_wallet: str
    side: str
    amount: float
    deposit_tx_signature: Optional[str] = None  # Required for Web users


class AcceptWagerRequest(BaseModel):
    acceptor_wallet: str
    deposit_tx_signature: Optional[str] = None  # Required for Web users
    source: Optional[str] = None  # "web" or "telegram"


class VerifyDepositRequest(BaseModel):
    tx_signature: str


class CancelWagerRequest(BaseModel):
    wager_id: str
    creator_wallet: str


class ClaimReferralRequest(BaseModel):
    """Request to claim referral earnings."""
    user_wallet: str  # User's wallet address (for web users)


# === AUTH MODELS ===

class RegisterRequest(BaseModel):
    """User registration request."""
    email: str
    password: str
    username: str
    referral_code: Optional[str] = None  # Optional referrer code


class LoginRequest(BaseModel):
    """User login request."""
    username: str
    password: str


class UpdateProfileRequest(BaseModel):
    """Update user profile."""
    display_name: Optional[str] = None
    payout_wallet: Optional[str] = None


class UpdateReferralCodeRequest(BaseModel):
    """Update custom referral code."""
    referral_code: str


# === SUPPORT TICKET MODELS ===

class SubmitTicketRequest(BaseModel):
    """Submit a support ticket or password reset request."""
    email: str
    ticket_type: str  # "support", "password_reset", "bug_report"
    subject: str
    message: str


class AdminResetPasswordRequest(BaseModel):
    """Admin request to reset a user's password."""
    user_id: int
    new_password: str  # Admin-generated password to send to user


class AdminResolveTicketRequest(BaseModel):
    """Admin request to resolve a ticket."""
    admin_notes: Optional[str] = None


class ProfileResponse(BaseModel):
    """User profile response."""
    user_id: int
    email: str
    username: str
    display_name: Optional[str]
    payout_wallet: Optional[str]
    games_played: int
    games_won: int
    total_wagered: float
    total_won: float
    total_lost: float
    win_rate: str
    tier: str
    tier_progress: dict  # Progress to next tier
    referral_code: str
    total_referrals: int
    pending_referral_earnings: float
    total_referral_claimed: float
    created_at: str


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
    creator_username: Optional[str] = None  # Display name for the creator
    creator_side: str
    amount: float
    status: str
    created_at: str
    escrow_wallet: Optional[str] = None  # Returned during creation for deposit
    id: Optional[str] = None  # Alias for wager_id (frontend compatibility)


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


# ===== HELPER: Get current user from session =====

def get_session_token(request: Request) -> Optional[str]:
    """Extract session token from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def get_current_user(request: Request) -> Optional[User]:
    """Get current authenticated user from session."""
    token = get_session_token(request)
    if not token:
        return None
    return db.get_user_by_session(token)


def require_auth(request: Request) -> User:
    """Require authenticated user, raise 401 if not."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated. Please login.")
    return user


def require_admin(request: Request) -> User:
    """Require authenticated admin user, raise 401/403 if not."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated. Please login.")
    if not user.is_admin:
        logger.warning(f"Non-admin user {user.email} attempted admin access")
        raise HTTPException(status_code=403, detail="Admin access required.")
    return user


def get_tier_progress(total_wagered: float, current_tier: str) -> dict:
    """Calculate progress to next tier."""
    tier_order = ["Starter", "Bronze", "Silver", "Gold", "Diamond"]
    current_idx = tier_order.index(current_tier)

    if current_idx >= len(tier_order) - 1:
        # Already at max tier
        return {
            "current_tier": current_tier,
            "next_tier": None,
            "current_volume": total_wagered,
            "volume_needed": 0,
            "progress_percent": 100
        }

    next_tier = tier_order[current_idx + 1]
    current_threshold = TIER_THRESHOLDS[current_tier]
    next_threshold = TIER_THRESHOLDS[next_tier]

    volume_in_tier = total_wagered - current_threshold
    tier_range = next_threshold - current_threshold
    progress = min(100, (volume_in_tier / tier_range) * 100) if tier_range > 0 else 0

    return {
        "current_tier": current_tier,
        "next_tier": next_tier,
        "current_volume": total_wagered,
        "volume_needed": max(0, next_threshold - total_wagered),
        "progress_percent": round(progress, 1)
    }


# ===== API ENDPOINTS =====

@app.get("/")
async def root():
    """API root."""
    return {
        "name": "Solana Coinflip API",
        "version": "1.0.0",
        "status": "online"
    }


# === AUTHENTICATION ENDPOINTS ===

@app.post("/api/auth/register")
async def register(request: RegisterRequest, http_request: Request):
    """Register a new user account."""
    # Rate limit: 5 registrations per hour per IP
    check_rate_limit(http_request, "register", max_requests=5, window_seconds=3600)

    # Validate email
    if not validate_email(request.email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Check if email already exists
    if db.email_exists(request.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    # Validate username
    valid, error = validate_username(request.username)
    if not valid:
        raise HTTPException(status_code=400, detail=error)

    # Check if username already taken
    if db.username_exists(request.username):
        raise HTTPException(status_code=400, detail="Username already taken")

    # Validate password
    valid, error = validate_password(request.password)
    if not valid:
        raise HTTPException(status_code=400, detail=error)

    # Handle referral code
    referred_by = None
    if request.referral_code:
        referrer = db.get_user_by_referral_code(request.referral_code)
        if referrer:
            referred_by = referrer.user_id
            logger.info(f"New user referred by user {referrer.user_id} (code: {request.referral_code})")

    # Generate unique referral code for new user
    user_referral_code = generate_referral_code()
    while db.get_user_by_referral_code(user_referral_code):
        user_referral_code = generate_referral_code()

    # Create user
    user = User(
        user_id=None,  # Auto-generated
        platform="web",
        email=request.email.lower(),
        password_hash=hash_password(request.password),
        username=request.username.lower(),
        display_name=request.username,
        referral_code=user_referral_code,
        referred_by=referred_by,
    )

    # Create session
    session_token, session_expires = create_session(user)
    user.session_token = session_token
    user.session_expires = session_expires
    user.last_login = datetime.utcnow()

    # Save user
    user_id = db.save_user(user)
    user.user_id = user_id

    # Update referrer's referral count
    if referred_by:
        referrer = db.get_user(referred_by)
        if referrer:
            referrer.total_referrals += 1
            db.save_user(referrer)

    logger.info(f"New user registered: {user.email} (ID: {user_id})")

    return {
        "success": True,
        "message": "Registration successful",
        "session_token": session_token,
        "user": {
            "user_id": user_id,
            "email": user.email,
            "username": user.username,
            "referral_code": user.referral_code
        }
    }


@app.post("/api/auth/login")
async def login(request: LoginRequest, http_request: Request):
    """Login to existing account using username."""
    # Rate limit: 10 login attempts per minute per IP
    check_rate_limit(http_request, "login", max_requests=10, window_seconds=60)

    # Find user by username
    user = db.get_user_by_username(request.username.lower())

    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Create new session
    session_token, session_expires = create_session(user)
    user.session_token = session_token
    user.session_expires = session_expires
    user.last_login = datetime.utcnow()
    user.last_active = datetime.utcnow()

    db.save_user(user)

    logger.info(f"User logged in: {user.username} ({user.email})")

    return {
        "success": True,
        "message": "Login successful",
        "session_token": session_token,
        "user": {
            "user_id": user.user_id,
            "email": user.email,
            "username": user.username,
            "display_name": user.display_name,
            "tier": user.tier
        }
    }


@app.post("/api/auth/logout")
async def logout(http_request: Request):
    """Logout and invalidate session."""
    user = get_current_user(http_request)

    if user:
        user.session_token = None
        user.session_expires = None
        db.save_user(user)
        logger.info(f"User logged out: {user.email}")

    return {"success": True, "message": "Logged out successfully"}


@app.get("/api/auth/me")
async def get_me(http_request: Request) -> ProfileResponse:
    """Get current authenticated user's profile."""
    user = require_auth(http_request)

    # Update tier based on volume
    tier, fee_rate = calculate_tier(user.total_wagered)
    if tier != user.tier:
        user.tier = tier
        user.tier_fee_rate = fee_rate
        db.save_user(user)

    tier_progress = get_tier_progress(user.total_wagered, user.tier)

    return ProfileResponse(
        user_id=user.user_id,
        email=user.email,
        username=user.username,
        display_name=user.display_name,
        payout_wallet=user.payout_wallet,
        games_played=user.games_played,
        games_won=user.games_won,
        total_wagered=user.total_wagered,
        total_won=user.total_won,
        total_lost=user.total_lost,
        win_rate=format_win_rate(user.games_played, user.games_won),
        tier=user.tier,
        tier_progress=tier_progress,
        referral_code=user.referral_code or "",
        total_referrals=user.total_referrals,
        pending_referral_earnings=user.pending_referral_earnings,
        total_referral_claimed=user.total_referral_claimed,
        created_at=user.created_at.isoformat()
    )


@app.post("/api/profile/update")
async def update_profile(request: UpdateProfileRequest, http_request: Request):
    """Update user profile settings."""
    user = require_auth(http_request)

    if request.display_name is not None:
        if len(request.display_name) > 50:
            raise HTTPException(status_code=400, detail="Display name too long (max 50 chars)")
        user.display_name = request.display_name

    if request.payout_wallet is not None:
        # Basic Solana address validation
        if request.payout_wallet and (len(request.payout_wallet) < 32 or len(request.payout_wallet) > 44):
            raise HTTPException(status_code=400, detail="Invalid Solana wallet address")
        user.payout_wallet = request.payout_wallet

    user.last_active = datetime.utcnow()
    db.save_user(user)

    return {
        "success": True,
        "message": "Profile updated successfully",
        "display_name": user.display_name,
        "payout_wallet": user.payout_wallet
    }


@app.post("/api/profile/referral-code")
async def update_referral_code(request: UpdateReferralCodeRequest, http_request: Request):
    """Update user's custom referral code (max 16 characters, alphanumeric)."""
    user = require_auth(http_request)

    # Validate referral code format
    new_code = request.referral_code.upper()  # Store as uppercase
    valid, error = validate_referral_code(new_code)
    if not valid:
        raise HTTPException(status_code=400, detail=error)

    # Check if code is already taken by another user
    existing_user = db.get_user_by_referral_code(new_code)
    if existing_user and existing_user.user_id != user.user_id:
        raise HTTPException(status_code=400, detail="This referral code is already taken")

    # Update user's referral code
    old_code = user.referral_code
    user.referral_code = new_code
    db.save_user(user)

    logger.info(f"User {user.user_id} updated referral code from {old_code} to {new_code}")

    return {
        "success": True,
        "message": "Referral code updated successfully",
        "referral_code": new_code,
        "referral_link": f"https://coinflipvp.com/?ref={new_code}"
    }


@app.get("/api/profile/referrals")
async def get_referral_stats(http_request: Request):
    """Get user's referral statistics and earnings."""
    user = require_auth(http_request)

    # Get claimable balance if user has escrow
    claimable = 0.0
    if user.referral_payout_escrow_address:
        try:
            claimable = await get_claimable_referral_balance(user, RPC_URL)
        except Exception as e:
            logger.error(f"Failed to get referral balance: {e}")

    # Get tier-based referral rate
    tier_rate = TIER_REFERRAL_RATES.get(user.tier, 0.0)
    rate_percent = int(tier_rate * 100) if tier_rate >= 0.01 else tier_rate * 100

    return {
        "success": True,
        "referral_code": user.referral_code,
        "referral_link": f"https://coinflipvp.com/?ref={user.referral_code}",
        "total_referrals": user.total_referrals,
        "pending_earnings": user.pending_referral_earnings,
        "claimable_balance": claimable,
        "total_claimed": user.total_referral_claimed,
        "total_lifetime_earnings": user.referral_earnings,
        "current_tier": user.tier,
        "reward_rate_percent": rate_percent,
        "reward_rate": f"{rate_percent}% of platform fees" if tier_rate > 0 else "Unlock at Bronze tier",
        "tier_rates": {
            "Starter": "0%",
            "Bronze": "2.5%",
            "Silver": "5%",
            "Gold": "7.5%",
            "Diamond": "10%"
        }
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


class RecentGameResponse(BaseModel):
    """Recent game with proof data for public display."""
    game_id: str
    game_type: str
    player1_wallet: str
    player2_wallet: Optional[str]
    amount: float
    result: str
    winner_wallet: str
    winner_username: Optional[str] = None  # Display name for winner
    blockhash: str
    payout_tx: Optional[str]
    completed_at: str
    # Proof verification data
    proof: dict


@app.get("/api/games/recent")
async def get_recent_games(limit: int = 10) -> List[RecentGameResponse]:
    """Get recent completed games with provably fair proof data.

    Each game includes:
    - Game details (players, amount, result)
    - Proof data (blockhash, verification hash, expected result)
    - Transaction signatures for on-chain verification
    """
    import hashlib

    games = db.get_recent_games(limit=min(limit, 50))  # Cap at 50

    results = []
    for game in games:
        if not game.blockhash or not game.result:
            continue  # Skip games without proof data

        # Get winner info (wallet and username)
        winner_wallet = ""
        winner_username = None
        if game.winner_id:
            winner_user = db.get_user(game.winner_id)
            if winner_user:
                winner_wallet = winner_user.connected_wallet or winner_user.payout_wallet or ""
                winner_username = winner_user.username

        # Fallback: use player wallets if winner_wallet still empty
        if not winner_wallet:
            # For PVP games, try to determine winner from result
            if game.player1_wallet:
                winner_wallet = game.player1_wallet  # Default to player1
            if game.player2_wallet and game.result:
                # If player1 picked a side that lost, player2 won
                winner_wallet = game.player2_wallet if game.player2_wallet else game.player1_wallet

        # Fallback: look up by wallet if no username found
        if not winner_username and winner_wallet:
            wallet_user = db.get_user_by_wallet(winner_wallet)
            if wallet_user and wallet_user.username:
                winner_username = wallet_user.username

        # Generate proof data for verification
        seed = f"{game.blockhash}{game.game_id}"
        hash_digest = hashlib.sha256(seed.encode()).hexdigest()
        first_byte = int(hash_digest[:2], 16)
        expected_result = "heads" if first_byte % 2 == 0 else "tails"

        proof = {
            "blockhash": game.blockhash,
            "game_id": game.game_id,
            "seed": seed,
            "hash": hash_digest,
            "first_byte": first_byte,
            "first_byte_hex": hash_digest[:2],
            "is_even": first_byte % 2 == 0,
            "expected_result": expected_result,
            "actual_result": game.result.value,
            "verified": expected_result == game.result.value,
            "algorithm": "SHA-256(blockhash + game_id) first byte: even=HEADS, odd=TAILS"
        }

        # payout_tx may contain multiple TXs separated by comma - use first one for Solscan
        payout_tx = game.payout_tx.split(",")[0] if game.payout_tx else None

        results.append(RecentGameResponse(
            game_id=game.game_id,
            game_type=game.game_type.value,
            player1_wallet=game.player1_wallet,
            player2_wallet=game.player2_wallet,
            amount=game.amount,
            result=game.result.value,
            winner_wallet=winner_wallet,
            winner_username=winner_username,
            blockhash=game.blockhash,
            payout_tx=payout_tx,
            completed_at=game.completed_at.isoformat() if game.completed_at else "",
            proof=proof
        ))

    return results


# === WAGER ENDPOINTS (PVP) ===

@app.post("/api/wager/create")
async def create_wager(request: CreateWagerRequest, http_request: Request) -> WagerResponse:
    """Create a PVP wager with isolated escrow wallet.

    SECURITY: Generates unique escrow wallet for creator's deposit.
    Step 1 of 2-step wager creation (generate escrow, then verify deposit).

    Rate limit: 20 requests per 60 seconds per IP
    """
    # SECURITY: Check emergency stop
    check_emergency_stop()

    # SECURITY: Rate limiting (20 wagers per minute max)
    check_rate_limit(http_request, "create_wager", max_requests=20, window_seconds=60)

    try:
        import uuid
        from game.solana_ops import generate_wallet
        from utils import encrypt_secret

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

        # Generate unique escrow wallet (step 1 - no deposit yet)
        escrow_address, escrow_secret = generate_wallet()
        encrypted_secret = encrypt_secret(escrow_secret, ENCRYPTION_KEY)

        logger.info(f"[ESCROW] Generated escrow {escrow_address} for pending wager {wager_id}")

        # Create wager with pending_deposit status
        wager = Wager(
            wager_id=wager_id,
            creator_id=user.user_id,
            creator_wallet=request.creator_wallet,
            creator_side=side,
            amount=request.amount,
            status="pending_deposit",  # Awaiting creator deposit
            creator_escrow_address=escrow_address,
            creator_escrow_secret=encrypted_secret,
            creator_deposit_tx=None,  # Will be set after verification
        )

        # Save to database
        db.save_wager(wager)

        logger.info(f"Wager created (pending): {wager_id} by {request.creator_wallet} - {request.amount} SOL on {side.value}")

        # Return response with escrow address for user to deposit to
        return WagerResponse(
            wager_id=wager.wager_id,
            creator_wallet=wager.creator_wallet,
            creator_side=wager.creator_side.value,
            amount=wager.amount,
            status=wager.status,
            created_at=wager.created_at.isoformat(),
            escrow_wallet=escrow_address,  # User deposits to this address
            id=wager.wager_id  # Frontend expects 'id' field
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create wager failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create wager. Please try again.")


@app.post("/api/wager/{wager_id}/verify-deposit")
async def verify_wager_deposit(wager_id: str, request: VerifyDepositRequest, http_request: Request):
    """Verify creator's deposit and activate the wager.

    Step 2 of 2-step wager creation.
    Verifies the deposit transaction on-chain and changes status to 'open'.
    """
    # SECURITY: Check emergency stop
    check_emergency_stop()

    # Rate limiting
    check_rate_limit(http_request, "verify_deposit", max_requests=30, window_seconds=60)

    try:
        from game.solana_ops import verify_deposit_to_escrow
        from database import UsedSignature

        # Get the pending wager
        wager = db.get_wager(wager_id)

        if not wager:
            raise HTTPException(status_code=404, detail="Wager not found")

        if wager.status != "pending_deposit":
            raise HTTPException(status_code=400, detail=f"Wager is not awaiting deposit (status: {wager.status})")

        # SECURITY: Check if signature already used
        if db.signature_already_used(request.tx_signature):
            used_sig = db.get_used_signature(request.tx_signature)
            raise HTTPException(
                status_code=400,
                detail=f"Transaction signature already used for {used_sig.used_for}"
            )

        # Calculate expected amount
        total_required = wager.amount + TRANSACTION_FEE

        logger.info(f"[VERIFY] Checking deposit for wager {wager_id}")
        logger.info(f"[VERIFY] Expected: {total_required} SOL to {wager.creator_escrow_address}")
        logger.info(f"[VERIFY] Creator wallet: {wager.creator_wallet}")
        logger.info(f"[VERIFY] TX signature: {request.tx_signature}")

        # Verify deposit on-chain - use flexible verification that only checks recipient and amount
        # (Don't strictly check sender since user might send from any wallet)
        is_valid = await verify_deposit_to_escrow(
            RPC_URL,
            request.tx_signature,
            wager.creator_escrow_address,  # recipient (escrow)
            total_required  # expected amount
        )

        if not is_valid:
            logger.warning(f"[VERIFY] Deposit verification FAILED for wager {wager_id}")
            raise HTTPException(
                status_code=400,
                detail=f"Deposit verification failed. Please ensure you sent exactly {total_required} SOL to {wager.creator_escrow_address}"
            )

        logger.info(f"[VERIFY] Deposit verified successfully for wager {wager_id}")

        # Record used signature
        used_sig = UsedSignature(
            signature=request.tx_signature,
            user_wallet=wager.creator_wallet,
            used_for=f"wager_deposit_{wager_id}",
        )
        db.save_used_signature(used_sig)

        # Update wager status to open
        wager.status = "open"
        wager.creator_deposit_tx = request.tx_signature
        db.save_wager(wager)

        logger.info(f"[DEPOSIT] Verified deposit for wager {wager_id}: {request.tx_signature}")

        # Broadcast to WebSocket clients
        await manager.broadcast({
            "type": "wager_created",
            "wager": {
                "wager_id": wager_id,
                "creator_wallet": wager.creator_wallet,
                "side": wager.creator_side.value,
                "amount": wager.amount
            }
        })

        return {
            "success": True,
            "message": "Deposit verified! Your wager is now live.",
            "wager_id": wager_id,
            "status": "open"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verify deposit failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to verify deposit. Please try again.")


@app.get("/api/wagers/open")
async def get_open_wagers() -> List[WagerResponse]:
    """Get all open wagers."""
    wagers = db.get_open_wagers(limit=20)

    result = []
    for w in wagers:
        # Get creator's username for display
        # Try by ID first, then by wallet (handles different user ID systems)
        creator = db.get_user(w.creator_id)
        creator_username = creator.username if creator and creator.username else None

        # Fallback: look up by wallet address if no username found
        if not creator_username and w.creator_wallet:
            wallet_user = db.get_user_by_wallet(w.creator_wallet)
            if wallet_user and wallet_user.username:
                creator_username = wallet_user.username

        result.append(WagerResponse(
            wager_id=w.wager_id,
            id=w.wager_id,  # Frontend uses 'id' for compatibility
            creator_wallet=w.creator_wallet,
            creator_username=creator_username,
            creator_side=w.creator_side.value,
            amount=w.amount,
            status=w.status,
            created_at=w.created_at.isoformat()
        ))

    return result


class PrepareAcceptRequest(BaseModel):
    acceptor_wallet: str


@app.post("/api/wager/{wager_id}/prepare-accept")
async def prepare_accept_wager(wager_id: str, request: PrepareAcceptRequest, http_request: Request):
    """Prepare to accept a wager - returns escrow address for acceptor deposit.

    Step 1 of accept flow: Get escrow address to deposit to.
    """
    check_emergency_stop()
    check_rate_limit(http_request, "prepare_accept", max_requests=30, window_seconds=60)

    try:
        # Get the wager
        wager = db.get_wager(wager_id)
        if not wager:
            raise HTTPException(status_code=404, detail="Wager not found")

        if wager.status != "open":
            raise HTTPException(status_code=400, detail=f"Wager is not open (status: {wager.status})")

        # Can't accept own wager
        if wager.creator_wallet == request.acceptor_wallet:
            raise HTTPException(status_code=400, detail="Cannot accept your own wager")

        # Generate escrow wallet for acceptor
        escrow_address, escrow_secret = generate_wallet()
        encrypted_secret = encrypt_secret(escrow_secret, ENCRYPTION_KEY)

        # Calculate deposit amount (wager + fee buffer)
        deposit_amount = wager.amount + TRANSACTION_FEE

        # Store the pending accept info temporarily on the wager
        # This will be finalized when they call the accept endpoint
        wager.acceptor_escrow_address = escrow_address
        wager.acceptor_escrow_secret = encrypted_secret
        wager.acceptor_wallet = request.acceptor_wallet
        db.save_wager(wager)

        logger.info(f"[PREPARE-ACCEPT] Wager {wager_id} - escrow {escrow_address} for acceptor {request.acceptor_wallet}")

        return {
            "success": True,
            "wager_id": wager_id,
            "escrow_wallet": escrow_address,
            "deposit_amount": deposit_amount,
            "wager_amount": wager.amount
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prepare accept failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to prepare accept. Please try again.")


@app.post("/api/wager/{wager_id}/accept")
async def accept_wager_endpoint(wager_id: str, request: AcceptWagerRequest, http_request: Request) -> GameResponse:
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

        # Get wager using path parameter
        wager = db.get_wager(wager_id)

        if not wager:
            raise HTTPException(status_code=404, detail="Wager not found")

        # Can't accept own wager
        if wager.creator_wallet == request.acceptor_wallet:
            raise HTTPException(status_code=400, detail="Cannot accept your own wager")

        # Get creator - try by ID first, then by wallet if that fails
        creator = db.get_user(wager.creator_id)
        if not creator:
            # Fallback: ensure creator exists via wallet (handles old wagers)
            creator = ensure_web_user(wager.creator_wallet)
            logger.info(f"[WAGER] Creator not found by ID, created/found via wallet: {wager.creator_wallet}")

        # SECURITY: Atomically accept wager (prevents double-acceptance race condition)
        # This uses an exclusive database lock to ensure only one user can accept
        accepted = db.atomic_accept_wager(wager_id, user.user_id)

        if not accepted:
            raise HTTPException(
                status_code=409,
                detail="Wager already accepted by another user. Please try a different wager."
            )

        # Reload wager to get updated status
        wager = db.get_wager(wager_id)
        if not wager:
            # Shouldn't happen, but handle gracefully
            raise HTTPException(status_code=500, detail="Wager disappeared after acceptance")

        logger.info(f"[WAGER] Atomically accepted wager {wager.wager_id} by user {user.user_id}")

        # SECURITY: Use EXISTING escrow wallet from prepare-accept (not create new!)
        if not wager.acceptor_escrow_address or not wager.acceptor_escrow_secret:
            # Fallback: create escrow if somehow missing (shouldn't happen in normal flow)
            logger.warning(f"[WAGER] No existing acceptor escrow for {wager.wager_id}, creating new one")
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
            wager.acceptor_escrow_address = escrow_address
            wager.acceptor_escrow_secret = encrypted_secret
            wager.acceptor_deposit_tx = deposit_tx
        else:
            # Normal flow: verify deposit to EXISTING escrow from prepare-accept
            logger.info(f"[WAGER] Using existing acceptor escrow {wager.acceptor_escrow_address}")
            deposit_tx = await verify_escrow_deposit(
                RPC_URL,
                wager.acceptor_escrow_address,
                wager.amount,
                TRANSACTION_FEE,
                request.acceptor_wallet,
                request.deposit_tx_signature,
                wager.wager_id,
                db
            )
            wager.acceptor_deposit_tx = deposit_tx

        logger.info(f"[ESCROW] Acceptor escrow ready: {wager.acceptor_escrow_address} for wager {wager.wager_id}")

        # Play PVP game with isolated escrow wallets
        # All fees go to treasury, referral commissions paid from escrow
        game = await play_pvp_game_with_escrows(
            RPC_URL,
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

        logger.info(f"Web user {request.acceptor_wallet} accepted wager {wager_id}")

        # Broadcast to WebSocket clients
        await manager.broadcast({
            "type": "wager_accepted",
            "wager_id": wager_id,
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

        # Decrypt escrow secret
        creator_escrow_secret = decrypt_secret(wager.creator_escrow_secret, ENCRYPTION_KEY)

        logger.info(f"[CANCEL] Refunding wager {request.wager_id} from escrow {wager.creator_escrow_address}")

        # Refund from escrow (returns wager, sends 0.025 SOL fee to treasury)
        refund_tx, fee_tx = await refund_from_escrow(
            RPC_URL,
            creator_escrow_secret,
            wager.creator_escrow_address,
            request.creator_wallet,
            TREASURY_WALLET,  # Fee goes directly to treasury
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

        # Get raw escrow balance and claimable amount
        raw_balance = await get_referral_escrow_balance(user, RPC_URL)
        claimable_balance = await get_claimable_referral_balance(user, RPC_URL)

        return {
            "success": True,
            "user_id": user.user_id,
            "referral_escrow_address": user.referral_payout_escrow_address,
            "raw_balance": raw_balance,  # Actual SOL in escrow
            "claimable_balance": claimable_balance,  # Amount user can claim (above threshold)
            "rent_threshold": REFERRAL_ESCROW_RENT_MINIMUM,  # 0.01 SOL kept for rent
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


# === SUPPORT TICKET ENDPOINTS (PUBLIC) ===

@app.post("/api/support/ticket")
async def submit_support_ticket(request: SubmitTicketRequest, http_request: Request):
    """Submit a support ticket (public - no auth required).

    Ticket types: 'support', 'password_reset', 'bug_report'
    """
    # Rate limit: 5 tickets per hour per IP
    check_rate_limit(http_request, "submit_ticket", max_requests=5, window_seconds=3600)

    # Validate email
    if not validate_email(request.email):
        raise HTTPException(status_code=400, detail="Invalid email format")

    # Validate ticket type
    valid_types = ["support", "password_reset", "bug_report"]
    if request.ticket_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid ticket type. Must be one of: {valid_types}")

    # Validate subject and message
    if not request.subject or len(request.subject) < 3:
        raise HTTPException(status_code=400, detail="Subject is required (min 3 characters)")
    if not request.message or len(request.message) < 10:
        raise HTTPException(status_code=400, detail="Message is required (min 10 characters)")

    # Check if user exists (optional - for linking ticket to user)
    user = db.get_user_by_email(request.email.lower())
    user_id = user.user_id if user else None

    # Create ticket
    ticket_id = f"TKT-{uuid.uuid4().hex[:8].upper()}"
    ticket = SupportTicket(
        ticket_id=ticket_id,
        user_id=user_id,
        email=request.email.lower(),
        ticket_type=request.ticket_type,
        subject=request.subject,
        message=request.message,
        status="open"
    )

    db.save_ticket(ticket)
    logger.info(f"Support ticket created: {ticket_id} ({request.ticket_type}) from {request.email}")

    return {
        "success": True,
        "message": "Ticket submitted successfully. We will respond via email.",
        "ticket_id": ticket_id,
        "ticket_type": request.ticket_type
    }


# === ADMIN ENDPOINTS (SECURE) ===

@app.get("/api/admin/check")
async def admin_check(http_request: Request):
    """Check if current user is admin."""
    user = get_current_user(http_request)
    if not user:
        return {"is_admin": False, "authenticated": False}
    return {"is_admin": user.is_admin, "authenticated": True, "email": user.email}


@app.get("/api/admin/stats")
async def admin_stats(http_request: Request):
    """Get admin dashboard statistics."""
    admin = require_admin(http_request)

    user_count = db.get_user_count()
    open_tickets = db.get_ticket_count(status="open")
    total_tickets = db.get_ticket_count()

    return {
        "success": True,
        "stats": {
            "total_users": user_count,
            "open_tickets": open_tickets,
            "total_tickets": total_tickets,
            "admin_username": admin.username
        }
    }


@app.get("/api/admin/users")
async def admin_list_users(http_request: Request, limit: int = 50, offset: int = 0):
    """List all users (admin only)."""
    require_admin(http_request)

    users = db.get_all_users(limit=min(limit, 100), offset=offset)
    total = db.get_user_count()

    return {
        "success": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "users": [
            {
                "user_id": u.user_id,
                "email": u.email,
                "username": u.username,
                "display_name": u.display_name,
                "payout_wallet": u.payout_wallet,
                "games_played": u.games_played,
                "games_won": u.games_won,
                "total_wagered": u.total_wagered,
                "tier": u.tier,
                "is_admin": u.is_admin,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_login": u.last_login.isoformat() if u.last_login else None
            }
            for u in users
        ]
    }


@app.get("/api/admin/users/search")
async def admin_search_users(http_request: Request, q: str):
    """Search users by email/username (admin only)."""
    require_admin(http_request)

    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="Search query must be at least 2 characters")

    users = db.search_users(q, limit=20)

    return {
        "success": True,
        "query": q,
        "count": len(users),
        "users": [
            {
                "user_id": u.user_id,
                "email": u.email,
                "username": u.username,
                "display_name": u.display_name,
                "payout_wallet": u.payout_wallet,
                "tier": u.tier,
                "is_admin": u.is_admin,
                "created_at": u.created_at.isoformat() if u.created_at else None
            }
            for u in users
        ]
    }


@app.get("/api/admin/tickets")
async def admin_list_tickets(http_request: Request, status: Optional[str] = None,
                             ticket_type: Optional[str] = None, limit: int = 50):
    """List support tickets (admin only)."""
    require_admin(http_request)

    tickets = db.get_tickets(status=status, ticket_type=ticket_type, limit=min(limit, 100))

    return {
        "success": True,
        "count": len(tickets),
        "filters": {"status": status, "ticket_type": ticket_type},
        "tickets": [
            {
                "ticket_id": t.ticket_id,
                "user_id": t.user_id,
                "email": t.email,
                "ticket_type": t.ticket_type,
                "subject": t.subject,
                "message": t.message,
                "status": t.status,
                "admin_notes": t.admin_notes,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "resolved_at": t.resolved_at.isoformat() if t.resolved_at else None,
                "resolved_by": t.resolved_by
            }
            for t in tickets
        ]
    }


@app.post("/api/admin/tickets/{ticket_id}/resolve")
async def admin_resolve_ticket(ticket_id: str, request: AdminResolveTicketRequest, http_request: Request):
    """Resolve a support ticket (admin only)."""
    admin = require_admin(http_request)

    ticket = db.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Update ticket
    ticket.status = "resolved"
    ticket.admin_notes = request.admin_notes
    ticket.resolved_at = datetime.utcnow()
    ticket.resolved_by = admin.user_id

    db.save_ticket(ticket)
    logger.info(f"Admin {admin.email} resolved ticket {ticket_id}")

    return {
        "success": True,
        "message": "Ticket resolved successfully",
        "ticket_id": ticket_id,
        "resolved_by": admin.email
    }


@app.post("/api/admin/user/{user_id}/reset-password")
async def admin_reset_password(user_id: int, request: AdminResetPasswordRequest, http_request: Request):
    """Reset a user's password (admin only).

    Admin generates a new password, updates the user's password,
    then manually sends the new password to the user via email.
    """
    admin = require_admin(http_request)

    # Get user
    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate new password
    valid, error = validate_password(request.new_password)
    if not valid:
        raise HTTPException(status_code=400, detail=error)

    # Hash and save new password
    user.password_hash = hash_password(request.new_password)
    # Invalidate any existing sessions
    user.session_token = None
    user.session_expires = None

    db.save_user(user)

    logger.info(f"Admin {admin.email} reset password for user {user.email} (ID: {user_id})")

    return {
        "success": True,
        "message": f"Password reset for {user.email}. Send the new password to user manually.",
        "user_id": user_id,
        "user_email": user.email,
        "admin_action_by": admin.email
    }


@app.post("/api/admin/user/{user_id}/toggle-admin")
async def admin_toggle_admin(user_id: int, http_request: Request):
    """Toggle admin status for a user (admin only)."""
    admin = require_admin(http_request)

    # Prevent self-demotion
    if admin.user_id == user_id:
        raise HTTPException(status_code=400, detail="Cannot modify your own admin status")

    user = db.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Toggle admin status
    user.is_admin = not user.is_admin
    db.save_user(user)

    action = "granted" if user.is_admin else "revoked"
    logger.info(f"Admin {admin.email} {action} admin access for {user.email}")

    return {
        "success": True,
        "message": f"Admin access {action} for {user.email}",
        "user_id": user_id,
        "is_admin": user.is_admin
    }


# === ADMIN WAGER MANAGEMENT ===

@app.get("/api/admin/wagers")
async def admin_list_wagers(http_request: Request, status: Optional[str] = None, limit: int = 50):
    """List all wagers with escrow info (admin only)."""
    require_admin(http_request)

    wagers = db.get_all_wagers(status=status, limit=min(limit, 100))

    result = []
    for w in wagers:
        # Get acceptor wallet from user if wager was accepted
        acceptor_wallet = None
        if w.acceptor_id:
            acceptor = db.get_user(w.acceptor_id)
            if acceptor:
                acceptor_wallet = acceptor.payout_wallet or acceptor.connected_wallet

        wager_data = {
            "wager_id": w.wager_id,
            "creator_wallet": w.creator_wallet,
            "acceptor_wallet": acceptor_wallet,
            "creator_side": w.creator_side.value if w.creator_side else None,
            "amount": w.amount,
            "status": w.status,
            "escrow_address": w.creator_escrow_address,
            "acceptor_escrow_address": w.acceptor_escrow_address,
            "created_at": w.created_at.isoformat() if w.created_at else None,
            "acceptor_id": w.acceptor_id,
        }

        # Check creator escrow balance
        if w.creator_escrow_address:
            try:
                balance = await get_sol_balance(RPC_URL, w.creator_escrow_address)
                wager_data["escrow_balance"] = balance
            except Exception as e:
                logger.error(f"[ADMIN] Failed to check creator escrow for {w.wager_id}: {e}")
                wager_data["escrow_balance"] = None

        # Check acceptor escrow balance
        if w.acceptor_escrow_address:
            try:
                acceptor_balance = await get_sol_balance(RPC_URL, w.acceptor_escrow_address)
                wager_data["acceptor_escrow_balance"] = acceptor_balance
            except Exception as e:
                logger.error(f"[ADMIN] Failed to check acceptor escrow for {w.wager_id}: {e}")
                wager_data["acceptor_escrow_balance"] = None

        result.append(wager_data)

    return {
        "success": True,
        "count": len(result),
        "wagers": result
    }


@app.post("/api/admin/wager/{wager_id}/refund")
async def admin_refund_wager(wager_id: str, http_request: Request):
    """Recover funds from any wager's escrow to the creator's payout wallet (admin only).

    This works for ANY wager status - admin can always recover stuck funds.
    """
    admin = require_admin(http_request)

    from utils import decrypt_secret

    # Get wager
    wager = db.get_wager(wager_id)
    if not wager:
        raise HTTPException(status_code=404, detail="Wager not found")

    # Admin can recover from ANY status - no status restriction
    # This ensures funds are never stuck

    if not wager.creator_escrow_address or not wager.creator_escrow_secret:
        raise HTTPException(status_code=400, detail="Wager has no escrow wallet")

    # Get creator's payout wallet (preferred) or fall back to creator_wallet
    creator = db.get_user(wager.creator_id)
    refund_destination = wager.creator_wallet  # default fallback
    if creator and creator.payout_wallet:
        refund_destination = creator.payout_wallet
        logger.info(f"[REFUND] Using creator's payout wallet: {refund_destination}")
    else:
        logger.info(f"[REFUND] No payout wallet set, using creator wallet: {refund_destination}")

    # Check escrow balance
    try:
        balance = await get_sol_balance(RPC_URL, wager.creator_escrow_address)
        logger.info(f"[REFUND] Escrow {wager.creator_escrow_address} balance: {balance} SOL")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check escrow balance: {e}")

    if balance < 0.001:
        # Just mark as refunded if no balance
        wager.status = "refunded"
        db.save_wager(wager)
        return {
            "success": True,
            "message": "No balance in escrow. Wager marked as refunded.",
            "wager_id": wager_id,
            "refunded_amount": 0
        }

    # Decrypt escrow secret
    try:
        escrow_secret = decrypt_secret(wager.creator_escrow_secret, ENCRYPTION_KEY)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to decrypt escrow: {e}")

    # Calculate refund (leave tiny amount for tx fee)
    refund_amount = balance - 0.000005

    # Execute refund to payout wallet
    logger.info(f"[REFUND] Sending {refund_amount} SOL to {refund_destination}")
    try:
        tx_sig = await transfer_sol(
            RPC_URL,
            escrow_secret,
            refund_destination,
            refund_amount
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refund transfer failed: {e}")

    # Update wager status
    wager.status = "refunded"
    db.save_wager(wager)

    logger.info(f"Admin {admin.email} refunded wager {wager_id}: {refund_amount} SOL to {refund_destination}")

    return {
        "success": True,
        "message": f"Refunded {refund_amount:.6f} SOL to {refund_destination}",
        "wager_id": wager_id,
        "refunded_amount": refund_amount,
        "refund_destination": refund_destination,
        "tx_signature": tx_sig,
        "solscan_url": f"https://solscan.io/tx/{tx_sig}"
    }


@app.post("/api/admin/wager/{wager_id}/cancel")
async def admin_cancel_wager(wager_id: str, http_request: Request):
    """Cancel any wager (admin only). Use refund first to return funds."""
    admin = require_admin(http_request)

    # Get wager
    wager = db.get_wager(wager_id)
    if not wager:
        raise HTTPException(status_code=404, detail="Wager not found")

    # Admin can cancel any wager - no status restriction

    # Update wager status
    wager.status = "cancelled"
    db.save_wager(wager)

    logger.info(f"Admin {admin.email} cancelled wager {wager_id}")

    return {
        "success": True,
        "message": f"Wager {wager_id} cancelled",
        "wager_id": wager_id
    }


@app.post("/api/admin/wager/{wager_id}/export-key")
async def admin_export_escrow_key(wager_id: str, http_request: Request):
    """Export escrow private keys for manual recovery (admin only)."""
    admin = require_admin(http_request)

    from utils import decrypt_secret

    wager = db.get_wager(wager_id)
    if not wager:
        raise HTTPException(status_code=404, detail="Wager not found")

    result = {
        "success": True,
        "wager_id": wager_id,
        "creator_escrow_address": wager.creator_escrow_address,
        "creator_escrow_key": None,
        "acceptor_escrow_address": wager.acceptor_escrow_address,
        "acceptor_escrow_key": None,
    }

    # Decrypt creator escrow key
    if wager.creator_escrow_secret:
        try:
            result["creator_escrow_key"] = decrypt_secret(wager.creator_escrow_secret, ENCRYPTION_KEY)
        except Exception as e:
            logger.error(f"Failed to decrypt creator escrow key: {e}")
            result["creator_escrow_key"] = f"DECRYPT_ERROR: {str(e)}"

    # Decrypt acceptor escrow key
    if wager.acceptor_escrow_secret:
        try:
            result["acceptor_escrow_key"] = decrypt_secret(wager.acceptor_escrow_secret, ENCRYPTION_KEY)
        except Exception as e:
            logger.error(f"Failed to decrypt acceptor escrow key: {e}")
            result["acceptor_escrow_key"] = f"DECRYPT_ERROR: {str(e)}"

    logger.warning(f"Admin {admin.email} exported escrow keys for wager {wager_id}")

    return result


class AdminRecoverRequest(BaseModel):
    destination_wallet: str
    escrow_type: str = "creator"  # "creator" or "acceptor"


@app.post("/api/admin/wager/{wager_id}/recover")
async def admin_recover_escrow(wager_id: str, request: AdminRecoverRequest, http_request: Request):
    """Recover funds from any escrow to any destination wallet (admin only).

    escrow_type: "creator" or "acceptor"
    destination_wallet: Any valid Solana wallet address
    """
    admin = require_admin(http_request)

    from utils import decrypt_secret

    wager = db.get_wager(wager_id)
    if not wager:
        raise HTTPException(status_code=404, detail="Wager not found")

    # Determine which escrow to recover from
    if request.escrow_type == "acceptor":
        escrow_address = wager.acceptor_escrow_address
        escrow_secret_encrypted = wager.acceptor_escrow_secret
        escrow_label = "acceptor"
    else:
        escrow_address = wager.creator_escrow_address
        escrow_secret_encrypted = wager.creator_escrow_secret
        escrow_label = "creator"

    if not escrow_address or not escrow_secret_encrypted:
        raise HTTPException(status_code=400, detail=f"No {escrow_label} escrow found for this wager")

    # Check balance
    try:
        balance = await get_sol_balance(RPC_URL, escrow_address)
        logger.info(f"[RECOVER] {escrow_label} escrow {escrow_address} balance: {balance} SOL")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check escrow balance: {e}")

    if balance < 0.001:
        return {
            "success": True,
            "message": f"No balance in {escrow_label} escrow ({balance} SOL)",
            "wager_id": wager_id,
            "recovered_amount": 0
        }

    # Decrypt escrow secret
    try:
        escrow_secret = decrypt_secret(escrow_secret_encrypted, ENCRYPTION_KEY)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to decrypt {escrow_label} escrow: {e}")

    # Calculate recovery amount
    recovery_amount = balance - 0.000005

    # Execute transfer
    logger.info(f"[RECOVER] Sending {recovery_amount} SOL from {escrow_label} escrow to {request.destination_wallet}")
    try:
        tx_sig = await transfer_sol(
            RPC_URL,
            escrow_secret,
            request.destination_wallet,
            recovery_amount
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recovery transfer failed: {e}")

    logger.info(f"Admin {admin.email} recovered {recovery_amount} SOL from {escrow_label} escrow of wager {wager_id} to {request.destination_wallet}")

    return {
        "success": True,
        "message": f"Recovered {recovery_amount:.6f} SOL from {escrow_label} escrow to {request.destination_wallet}",
        "wager_id": wager_id,
        "escrow_type": escrow_label,
        "recovered_amount": recovery_amount,
        "destination": request.destination_wallet,
        "tx_signature": tx_sig,
        "solscan_url": f"https://solscan.io/tx/{tx_sig}"
    }


@app.get("/api/admin/maintenance")
async def get_maintenance_status(http_request: Request):
    """Check if maintenance mode (betting disabled) is active."""
    admin = require_admin(http_request)
    return {
        "maintenance_mode": is_emergency_stop_enabled(),
        "message": "Betting is DISABLED" if is_emergency_stop_enabled() else "Betting is ENABLED"
    }


@app.post("/api/admin/maintenance/toggle")
async def toggle_maintenance_mode(http_request: Request):
    """Toggle maintenance mode - disables/enables all betting."""
    admin = require_admin(http_request)

    if is_emergency_stop_enabled():
        # Remove the flag to enable betting
        try:
            os.remove("EMERGENCY_STOP")
            logger.info(f"Admin {admin.email} DISABLED maintenance mode - betting is now ENABLED")
            return {
                "success": True,
                "maintenance_mode": False,
                "message": "Maintenance mode DISABLED - betting is now ENABLED"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to disable maintenance mode: {e}")
    else:
        # Create the flag to disable betting
        try:
            with open("EMERGENCY_STOP", "w") as f:
                f.write(f"Enabled by {admin.email} at {datetime.utcnow().isoformat()}")
            logger.info(f"Admin {admin.email} ENABLED maintenance mode - betting is now DISABLED")
            return {
                "success": True,
                "maintenance_mode": True,
                "message": "Maintenance mode ENABLED - betting is now DISABLED"
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to enable maintenance mode: {e}")


@app.post("/api/admin/sweep-escrows")
async def sweep_all_escrows(http_request: Request):
    """Sweep all remaining funds from escrow wallets to treasury.

    This collects any leftover SOL from completed/cancelled wagers.
    """
    admin = require_admin(http_request)

    from utils import decrypt_secret

    # Get all wagers (we'll check each escrow)
    wagers = db.get_all_wagers()

    swept_count = 0
    total_swept = 0.0
    results = []
    errors = []

    for wager in wagers:
        # Check creator escrow
        if wager.creator_escrow_address and wager.creator_escrow_secret:
            try:
                balance = await get_sol_balance(RPC_URL, wager.creator_escrow_address)
                if balance > 0.001:  # Only sweep if meaningful balance
                    escrow_secret = decrypt_secret(wager.creator_escrow_secret, ENCRYPTION_KEY)
                    sweep_amount = balance - 0.000005  # Leave dust for rent

                    tx_sig = await transfer_sol(
                        RPC_URL,
                        escrow_secret,
                        TREASURY_WALLET,
                        sweep_amount
                    )
                    swept_count += 1
                    total_swept += sweep_amount
                    results.append({
                        "wager_id": wager.wager_id,
                        "escrow_type": "creator",
                        "amount": sweep_amount,
                        "tx": tx_sig
                    })
                    logger.info(f"[SWEEP] Creator escrow {wager.creator_escrow_address}: {sweep_amount} SOL -> treasury")
            except Exception as e:
                errors.append(f"Creator escrow {wager.wager_id}: {str(e)}")

        # Check acceptor escrow
        if wager.acceptor_escrow_address and wager.acceptor_escrow_secret:
            try:
                balance = await get_sol_balance(RPC_URL, wager.acceptor_escrow_address)
                if balance > 0.001:  # Only sweep if meaningful balance
                    escrow_secret = decrypt_secret(wager.acceptor_escrow_secret, ENCRYPTION_KEY)
                    sweep_amount = balance - 0.000005  # Leave dust for rent

                    tx_sig = await transfer_sol(
                        RPC_URL,
                        escrow_secret,
                        TREASURY_WALLET,
                        sweep_amount
                    )
                    swept_count += 1
                    total_swept += sweep_amount
                    results.append({
                        "wager_id": wager.wager_id,
                        "escrow_type": "acceptor",
                        "amount": sweep_amount,
                        "tx": tx_sig
                    })
                    logger.info(f"[SWEEP] Acceptor escrow {wager.acceptor_escrow_address}: {sweep_amount} SOL -> treasury")
            except Exception as e:
                errors.append(f"Acceptor escrow {wager.wager_id}: {str(e)}")

    logger.info(f"Admin {admin.email} swept {swept_count} escrows for {total_swept:.6f} SOL total")

    return {
        "success": True,
        "message": f"Swept {swept_count} escrows for {total_swept:.6f} SOL",
        "swept_count": swept_count,
        "total_swept": total_swept,
        "treasury_wallet": TREASURY_WALLET,
        "results": results,
        "errors": errors if errors else None
    }


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
