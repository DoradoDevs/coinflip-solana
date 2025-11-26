"""
Database repository for Coinflip game.
Supports SQLite with async operations.
"""
import sqlite3
import logging
from typing import Optional, List
from datetime import datetime
from .models import User, Game, Wager, Transaction, GameType, GameStatus, CoinSide

logger = logging.getLogger(__name__)


class Database:
    """Database repository."""

    def __init__(self, db_path: str = "coinflip.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                platform TEXT NOT NULL,
                wallet_address TEXT,
                encrypted_secret TEXT,
                connected_wallet TEXT,
                games_played INTEGER DEFAULT 0,
                games_won INTEGER DEFAULT 0,
                total_wagered REAL DEFAULT 0.0,
                total_won REAL DEFAULT 0.0,
                total_lost REAL DEFAULT 0.0,
                username TEXT,
                created_at TEXT,
                last_active TEXT
            )
        """)

        # Games table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                game_id TEXT PRIMARY KEY,
                game_type TEXT NOT NULL,
                player1_id INTEGER NOT NULL,
                player1_side TEXT NOT NULL,
                player1_wallet TEXT NOT NULL,
                player2_id INTEGER,
                player2_side TEXT,
                player2_wallet TEXT,
                amount REAL NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                winner_id INTEGER,
                blockhash TEXT,
                deposit_tx TEXT,
                payout_tx TEXT,
                fee_tx TEXT,
                created_at TEXT,
                completed_at TEXT,
                FOREIGN KEY (player1_id) REFERENCES users(user_id),
                FOREIGN KEY (player2_id) REFERENCES users(user_id)
            )
        """)

        # Wagers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wagers (
                wager_id TEXT PRIMARY KEY,
                creator_id INTEGER NOT NULL,
                creator_wallet TEXT NOT NULL,
                creator_side TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT DEFAULT 'open',
                acceptor_id INTEGER,
                game_id TEXT,
                created_at TEXT,
                expires_at TEXT,
                FOREIGN KEY (creator_id) REFERENCES users(user_id),
                FOREIGN KEY (game_id) REFERENCES games(game_id)
            )
        """)

        # Transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                tx_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                tx_type TEXT NOT NULL,
                amount REAL NOT NULL,
                signature TEXT NOT NULL,
                game_id TEXT,
                timestamp TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (game_id) REFERENCES games(game_id)
            )
        """)

        # Indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_player1 ON games(player1_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_player2 ON games(player2_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_status ON games(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wagers_status ON wagers(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wagers_creator ON wagers(creator_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id)")

        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")

    # === User Operations ===

    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return User(
            user_id=row["user_id"],
            platform=row["platform"],
            wallet_address=row["wallet_address"],
            encrypted_secret=row["encrypted_secret"],
            connected_wallet=row["connected_wallet"],
            games_played=row["games_played"],
            games_won=row["games_won"],
            total_wagered=row["total_wagered"],
            total_won=row["total_won"],
            total_lost=row["total_lost"],
            username=row["username"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            last_active=datetime.fromisoformat(row["last_active"]) if row["last_active"] else datetime.utcnow(),
        )

    def save_user(self, user: User):
        """Save or update user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO users (
                user_id, platform, wallet_address, encrypted_secret, connected_wallet,
                games_played, games_won, total_wagered, total_won, total_lost,
                username, created_at, last_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user.user_id, user.platform, user.wallet_address, user.encrypted_secret,
            user.connected_wallet, user.games_played, user.games_won, user.total_wagered,
            user.total_won, user.total_lost, user.username,
            user.created_at.isoformat(), user.last_active.isoformat()
        ))

        conn.commit()
        conn.close()

    # === Game Operations ===

    def save_game(self, game: Game):
        """Save or update game."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO games (
                game_id, game_type, player1_id, player1_side, player1_wallet,
                player2_id, player2_side, player2_wallet, amount, status,
                result, winner_id, blockhash, deposit_tx, payout_tx, fee_tx,
                created_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            game.game_id, game.game_type.value, game.player1_id, game.player1_side.value,
            game.player1_wallet, game.player2_id,
            game.player2_side.value if game.player2_side else None,
            game.player2_wallet, game.amount, game.status.value,
            game.result.value if game.result else None,
            game.winner_id, game.blockhash, game.deposit_tx, game.payout_tx, game.fee_tx,
            game.created_at.isoformat(),
            game.completed_at.isoformat() if game.completed_at else None
        ))

        conn.commit()
        conn.close()

    def get_game(self, game_id: str) -> Optional[Game]:
        """Get game by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM games WHERE game_id = ?", (game_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_game(row)

    def get_user_games(self, user_id: int, limit: int = 10) -> List[Game]:
        """Get recent games for a user."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM games
            WHERE player1_id = ? OR player2_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (user_id, user_id, limit))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_game(row) for row in rows]

    def _row_to_game(self, row: sqlite3.Row) -> Game:
        """Convert database row to Game object."""
        return Game(
            game_id=row["game_id"],
            game_type=GameType(row["game_type"]),
            player1_id=row["player1_id"],
            player1_side=CoinSide(row["player1_side"]),
            player1_wallet=row["player1_wallet"],
            player2_id=row["player2_id"],
            player2_side=CoinSide(row["player2_side"]) if row["player2_side"] else None,
            player2_wallet=row["player2_wallet"],
            amount=row["amount"],
            status=GameStatus(row["status"]),
            result=CoinSide(row["result"]) if row["result"] else None,
            winner_id=row["winner_id"],
            blockhash=row["blockhash"],
            deposit_tx=row["deposit_tx"],
            payout_tx=row["payout_tx"],
            fee_tx=row["fee_tx"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        )

    # === Wager Operations ===

    def save_wager(self, wager: Wager):
        """Save or update wager."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO wagers (
                wager_id, creator_id, creator_wallet, creator_side, amount,
                status, acceptor_id, game_id, created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            wager.wager_id, wager.creator_id, wager.creator_wallet,
            wager.creator_side.value, wager.amount, wager.status,
            wager.acceptor_id, wager.game_id,
            wager.created_at.isoformat(),
            wager.expires_at.isoformat() if wager.expires_at else None
        ))

        conn.commit()
        conn.close()

    def get_open_wagers(self, limit: int = 20) -> List[Wager]:
        """Get all open wagers."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM wagers
            WHERE status = 'open'
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_wager(row) for row in rows]

    def get_user_wagers(self, user_id: int) -> List[Wager]:
        """Get user's wagers."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM wagers
            WHERE creator_id = ?
            ORDER BY created_at DESC
        """, (user_id,))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_wager(row) for row in rows]

    def _row_to_wager(self, row: sqlite3.Row) -> Wager:
        """Convert database row to Wager object."""
        return Wager(
            wager_id=row["wager_id"],
            creator_id=row["creator_id"],
            creator_wallet=row["creator_wallet"],
            creator_side=CoinSide(row["creator_side"]),
            amount=row["amount"],
            status=row["status"],
            acceptor_id=row["acceptor_id"],
            game_id=row["game_id"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow(),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
        )

    # === Transaction Operations ===

    def save_transaction(self, tx: Transaction):
        """Save transaction."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO transactions (
                tx_id, user_id, tx_type, amount, signature, game_id, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            tx.tx_id, tx.user_id, tx.tx_type, tx.amount, tx.signature,
            tx.game_id, tx.timestamp.isoformat()
        ))

        conn.commit()
        conn.close()

    def get_user_transactions(self, user_id: int, limit: int = 20) -> List[Transaction]:
        """Get user transaction history."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM transactions
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))

        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_transaction(row) for row in rows]

    def _row_to_transaction(self, row: sqlite3.Row) -> Transaction:
        """Convert database row to Transaction object."""
        return Transaction(
            tx_id=row["tx_id"],
            user_id=row["user_id"],
            tx_type=row["tx_type"],
            amount=row["amount"],
            signature=row["signature"],
            game_id=row["game_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else datetime.utcnow(),
        )
