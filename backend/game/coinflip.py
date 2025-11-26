"""
Core coinflip game logic with provably fair randomness.
"""
import hashlib
import logging
import uuid
from datetime import datetime
from typing import Optional, Tuple
from database.models import Game, GameType, GameStatus, CoinSide, User
from .solana_ops import (
    transfer_sol,
    get_latest_blockhash,
    payout_winner,
    collect_fee,
    get_sol_balance
)

logger = logging.getLogger(__name__)

# Fee configuration
HOUSE_FEE_PCT = 0.02  # 2% fee


def generate_game_id() -> str:
    """Generate unique game ID."""
    return f"game_{uuid.uuid4().hex[:12]}"


def get_house_wallet_address(house_wallet_secret: str) -> str:
    """Get house wallet public address from secret key."""
    from .solana_ops import keypair_from_base58
    kp = keypair_from_base58(house_wallet_secret)
    return str(kp.pubkey())


def flip_coin(blockhash: str, game_id: str) -> CoinSide:
    """Provably fair coin flip using Solana blockhash.

    Uses SHA-256 hash of (blockhash + game_id) to determine outcome.
    Even hash = HEADS, Odd hash = TAILS

    Args:
        blockhash: Solana blockhash for randomness
        game_id: Game ID for uniqueness

    Returns:
        CoinSide (HEADS or TAILS)
    """
    # Combine blockhash and game_id for unique seed
    seed = f"{blockhash}{game_id}"

    # Hash the seed
    hash_digest = hashlib.sha256(seed.encode()).hexdigest()

    # Convert first byte to integer and check if even/odd
    first_byte = int(hash_digest[:2], 16)

    # Even = HEADS, Odd = TAILS
    result = CoinSide.HEADS if first_byte % 2 == 0 else CoinSide.TAILS

    logger.info(f"Coin flip result: {result.value} (blockhash: {blockhash[:8]}..., hash: {hash_digest[:16]}...)")
    return result


async def play_house_game(
    rpc_url: str,
    house_wallet_secret: str,
    treasury_address: str,
    player: User,
    player_side: CoinSide,
    amount: float,
) -> Game:
    """Play a game against the house.

    Args:
        rpc_url: Solana RPC URL
        house_wallet_secret: House wallet secret key
        treasury_address: Treasury wallet address for fees
        player: Player user object
        player_side: Player's chosen side (HEADS or TAILS)
        amount: Wager amount in SOL

    Returns:
        Completed Game object
    """
    game_id = generate_game_id()

    # Check if player has custodial wallet (Telegram) or connected wallet (Web)
    player_wallet = player.wallet_address or player.connected_wallet
    if not player_wallet:
        raise Exception("Player has no wallet")

    # Check player has sufficient balance
    player_balance = await get_sol_balance(rpc_url, player_wallet)
    if player_balance < amount:
        raise Exception(f"Insufficient balance. Required: {amount} SOL, Available: {player_balance} SOL")

    # Create game
    game = Game(
        game_id=game_id,
        game_type=GameType.HOUSE,
        player1_id=player.user_id,
        player1_side=player_side,
        player1_wallet=player_wallet,
        amount=amount,
        status=GameStatus.IN_PROGRESS,
        created_at=datetime.utcnow(),
    )

    try:
        # STEP 1: COLLECT WAGER (ESCROW)
        # For Telegram custodial: Transfer from player's wallet to house wallet
        if player.platform == "telegram" and player.encrypted_secret:
            from utils import decrypt_secret
            import os
            encryption_key = os.getenv("ENCRYPTION_KEY")
            player_secret = decrypt_secret(player.encrypted_secret, encryption_key)

            # Transfer player's wager to house wallet (escrow)
            deposit_tx = await transfer_sol(
                rpc_url,
                player_secret,
                get_house_wallet_address(house_wallet_secret),
                amount
            )
            game.deposit_tx = deposit_tx
            logger.info(f"Collected {amount} SOL from player (tx: {deposit_tx})")

        # For Web users: They would send SOL to escrow address before calling this
        # For now, we trust they have the balance (checked above)
        elif player.platform == "web":
            logger.warning(f"Web game - assuming player will send {amount} SOL (not enforced yet)")

        # STEP 2: FLIP COIN
        # Get latest blockhash for provably fair randomness
        blockhash = await get_latest_blockhash(rpc_url)
        game.blockhash = blockhash

        # Flip the coin
        result = flip_coin(blockhash, game_id)
        game.result = result

        # STEP 3: DETERMINE WINNER AND PAYOUT
        player_won = (result == player_side)

        if player_won:
            game.winner_id = player.user_id

            # Calculate payout (2x wager - 2% fee)
            total_pot = amount * 2
            fee = total_pot * HOUSE_FEE_PCT
            payout = total_pot - fee

            # Pay winner from house wallet (which now has the escrowed funds)
            payout_tx = await transfer_sol(
                rpc_url,
                house_wallet_secret,
                player_wallet,
                payout
            )
            game.payout_tx = payout_tx

            # Collect fee
            if fee > 0:
                fee_tx = await transfer_sol(
                    rpc_url,
                    house_wallet_secret,
                    treasury_address,
                    fee
                )
                game.fee_tx = fee_tx

            logger.info(f"Player won {payout} SOL (tx: {payout_tx}), fee: {fee} SOL")

        else:
            # House wins - player's escrowed funds stay in house wallet
            game.winner_id = 0  # House

            # Collect fee to treasury (house keeps the rest)
            if player.platform == "telegram":
                # Funds already in house wallet, just move fee to treasury
                fee = amount * HOUSE_FEE_PCT
                if fee > 0:
                    fee_tx = await transfer_sol(
                        rpc_url,
                        house_wallet_secret,
                        treasury_address,
                        fee
                    )
                    game.fee_tx = fee_tx

            logger.info(f"House won {amount} SOL")

        # Mark game as completed
        game.status = GameStatus.COMPLETED
        game.completed_at = datetime.utcnow()

        return game

    except Exception as e:
        logger.error(f"House game failed: {e}")
        game.status = GameStatus.CANCELLED
        raise


async def play_pvp_game(
    rpc_url: str,
    house_wallet_secret: str,
    treasury_address: str,
    player1: User,
    player1_side: CoinSide,
    player2: User,
    amount: float,
) -> Game:
    """Play a PVP game between two players.

    Args:
        rpc_url: Solana RPC URL
        house_wallet_secret: House wallet secret (for Telegram custodial games)
        treasury_address: Treasury wallet for fees
        player1: First player (wager creator)
        player2: Second player (wager acceptor)
        player1_side: Player 1's chosen side
        amount: Wager amount in SOL (per player)

    Returns:
        Completed Game object
    """
    game_id = generate_game_id()

    # Get player wallets
    player1_wallet = player1.wallet_address or player1.connected_wallet
    player2_wallet = player2.wallet_address or player2.connected_wallet

    if not player1_wallet or not player2_wallet:
        raise Exception("One or both players have no wallet")

    # Player 2 takes opposite side
    player2_side = CoinSide.TAILS if player1_side == CoinSide.HEADS else CoinSide.HEADS

    # Create game
    game = Game(
        game_id=game_id,
        game_type=GameType.PVP,
        player1_id=player1.user_id,
        player1_side=player1_side,
        player1_wallet=player1_wallet,
        player2_id=player2.user_id,
        player2_side=player2_side,
        player2_wallet=player2_wallet,
        amount=amount,
        status=GameStatus.IN_PROGRESS,
        created_at=datetime.utcnow(),
    )

    try:
        # STEP 1: COLLECT ESCROW FROM BOTH PLAYERS
        # Check both players have sufficient balance
        player1_balance = await get_sol_balance(rpc_url, player1_wallet)
        player2_balance = await get_sol_balance(rpc_url, player2_wallet)

        if player1_balance < amount:
            raise Exception(f"Player 1 insufficient balance. Required: {amount} SOL, Available: {player1_balance} SOL")
        if player2_balance < amount:
            raise Exception(f"Player 2 insufficient balance. Required: {amount} SOL, Available: {player2_balance} SOL")

        # Collect from both Telegram users (custodial wallets)
        if player1.platform == "telegram" and player1.encrypted_secret:
            from utils import decrypt_secret
            import os
            encryption_key = os.getenv("ENCRYPTION_KEY")
            player1_secret = decrypt_secret(player1.encrypted_secret, encryption_key)

            # Transfer player1's wager to house wallet
            await transfer_sol(
                rpc_url,
                player1_secret,
                get_house_wallet_address(house_wallet_secret),
                amount
            )
            logger.info(f"Collected {amount} SOL from player1")

        if player2.platform == "telegram" and player2.encrypted_secret:
            from utils import decrypt_secret
            import os
            encryption_key = os.getenv("ENCRYPTION_KEY")
            player2_secret = decrypt_secret(player2.encrypted_secret, encryption_key)

            # Transfer player2's wager to house wallet
            await transfer_sol(
                rpc_url,
                player2_secret,
                get_house_wallet_address(house_wallet_secret),
                amount
            )
            logger.info(f"Collected {amount} SOL from player2")

        # For Web users: They would send SOL before accepting wager
        # (Not enforced yet - requires transaction verification)

        # STEP 2: FLIP COIN
        # Get latest blockhash for provably fair randomness
        blockhash = await get_latest_blockhash(rpc_url)
        game.blockhash = blockhash

        # Flip the coin
        result = flip_coin(blockhash, game_id)
        game.result = result

        # STEP 3: DETERMINE WINNER AND PAYOUT
        if result == player1_side:
            winner = player1
            winner_wallet = player1_wallet
            game.winner_id = player1.user_id
        else:
            winner = player2
            winner_wallet = player2_wallet
            game.winner_id = player2.user_id

        # Calculate payout
        total_pot = amount * 2
        fee = total_pot * HOUSE_FEE_PCT
        payout = total_pot - fee

        # Pay winner from house wallet (which now has both players' escrowed funds)
        payout_tx = await transfer_sol(
            rpc_url,
            house_wallet_secret,
            winner_wallet,
            payout
        )
        game.payout_tx = payout_tx

        # Collect fee to treasury
        if fee > 0:
            fee_tx = await transfer_sol(
                rpc_url,
                house_wallet_secret,
                treasury_address,
                fee
            )
            game.fee_tx = fee_tx

        logger.info(f"Player {game.winner_id} won {payout} SOL in PVP game (fee: {fee} SOL)")

        # Mark game as completed
        game.status = GameStatus.COMPLETED
        game.completed_at = datetime.utcnow()

        return game

    except Exception as e:
        logger.error(f"PVP game failed: {e}")
        game.status = GameStatus.CANCELLED
        raise


def verify_game_result(game: Game) -> bool:
    """Verify a game's result using the blockhash.

    Allows anyone to verify the game was fair.

    Args:
        game: Game object with blockhash and result

    Returns:
        True if result is valid, False otherwise
    """
    if not game.blockhash or not game.result:
        return False

    expected_result = flip_coin(game.blockhash, game.game_id)
    return expected_result == game.result
