"""
Data models for Coinflip game.
"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class GameType(Enum):
    """Type of coinflip game."""
    HOUSE = "house"  # Player vs House
    PVP = "pvp"      # Player vs Player


class GameStatus(Enum):
    """Status of a game."""
    PENDING = "pending"      # Waiting for opponent (PVP only)
    IN_PROGRESS = "in_progress"  # Game is being played
    COMPLETED = "completed"   # Game finished
    CANCELLED = "cancelled"   # Wager cancelled by creator


class CoinSide(Enum):
    """Side of the coin."""
    HEADS = "heads"
    TAILS = "tails"


@dataclass
class User:
    """User account."""
    user_id: int  # Telegram user ID or web wallet pubkey hash
    platform: str  # "telegram" or "web"

    # For Telegram users (custodial)
    wallet_address: Optional[str] = None
    encrypted_secret: Optional[str] = None

    # For Web users (non-custodial)
    connected_wallet: Optional[str] = None

    # Stats
    games_played: int = 0
    games_won: int = 0
    total_wagered: float = 0.0
    total_won: float = 0.0
    total_lost: float = 0.0

    # Metadata
    username: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Game:
    """A completed or in-progress coinflip game."""
    game_id: str
    game_type: GameType

    # Players
    player1_id: int
    player1_side: CoinSide
    player1_wallet: str

    player2_id: Optional[int] = None  # None for house games
    player2_side: Optional[CoinSide] = None
    player2_wallet: Optional[str] = None

    # Game details
    amount: float = 0.0
    status: GameStatus = GameStatus.PENDING

    # Results
    result: Optional[CoinSide] = None
    winner_id: Optional[int] = None
    blockhash: Optional[str] = None  # For provably fair randomness

    # Transactions
    deposit_tx: Optional[str] = None
    payout_tx: Optional[str] = None
    fee_tx: Optional[str] = None

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


@dataclass
class Wager:
    """An open wager waiting to be accepted (PVP only)."""
    wager_id: str
    creator_id: int
    creator_wallet: str
    creator_side: CoinSide

    amount: float
    status: str = "open"  # open, accepted, cancelled

    # When accepted
    acceptor_id: Optional[int] = None
    game_id: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


@dataclass
class Transaction:
    """Transaction history for accounting."""
    tx_id: str
    user_id: int
    tx_type: str  # deposit, withdrawal, game_win, game_loss, fee
    amount: float
    signature: str

    game_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
