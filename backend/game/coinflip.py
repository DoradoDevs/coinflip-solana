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
from token_config import (
    TOKEN_ENABLED,
    get_fee_discount as get_token_fee_discount,
    calculate_combined_discount,
    BASE_FEE_RATE,
)

logger = logging.getLogger(__name__)

# Fee configuration
HOUSE_FEE_PCT = 0.02  # 2% of prize pool
TRANSACTION_FEE = 0.025  # Fixed 0.025 SOL per player (covers gas + profit)
# Total fees per game: 2% of pot + 0.05 SOL fixed (0.025 from each player)


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

    # Get player's connected wallet (Web non-custodial)
    player_wallet = player.connected_wallet
    if not player_wallet:
        raise Exception("Player has no wallet")

    # Check player has sufficient balance (wager + transaction fee)
    total_required = amount + TRANSACTION_FEE
    player_balance = await get_sol_balance(rpc_url, player_wallet)
    if player_balance < total_required:
        raise Exception(f"Insufficient balance. Required: {total_required} SOL ({amount} wager + {TRANSACTION_FEE} fee), Available: {player_balance} SOL")

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
        # STEP 1: VERIFY DEPOSIT (Web non-custodial)
        # Escrow verification happens in API layer before calling this function
        # The transaction signature is verified on-chain to ensure SOL was sent
        total_required = amount + TRANSACTION_FEE
        logger.info(f"[REAL MAINNET] Web user deposit verified in API layer: {total_required} SOL ({amount} wager + {TRANSACTION_FEE} fee)")

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

            # Calculate payout (2x wager - 2% game fee)
            # Note: Transaction fee (0.025 SOL) already collected, kept separate
            total_pot = amount * 2
            game_fee = total_pot * HOUSE_FEE_PCT
            payout = total_pot - game_fee

            # Pay winner from house wallet (REAL MAINNET TRANSFER)
            payout_tx = await transfer_sol(
                rpc_url,
                house_wallet_secret,
                player_wallet,
                payout
            )
            game.payout_tx = payout_tx

            # Send all fees to treasury (game fee + transaction fee)
            total_fees = game_fee + TRANSACTION_FEE
            if total_fees > 0:
                fee_tx = await transfer_sol(
                    rpc_url,
                    house_wallet_secret,
                    treasury_address,
                    total_fees
                )
                game.fee_tx = fee_tx

            logger.info(f"[REAL MAINNET] Player won {payout} SOL (tx: {payout_tx}), game fee: {game_fee} SOL, tx fee: {TRANSACTION_FEE} SOL, total fees: {total_fees} SOL")

        else:
            # House wins - player's escrowed funds stay in house wallet
            game.winner_id = 0  # House
            logger.info(f"[REAL MAINNET] House won {amount} SOL")

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
        house_wallet_secret: House wallet secret key
        treasury_address: Treasury wallet for fees
        player1: First player (wager creator)
        player2: Second player (wager acceptor)
        player1_side: Player 1's chosen side
        amount: Wager amount in SOL (per player)

    Returns:
        Completed Game object
    """
    game_id = generate_game_id()

    # Get player wallets (Web non-custodial)
    player1_wallet = player1.connected_wallet
    player2_wallet = player2.connected_wallet

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
        # STEP 1: VERIFY DEPOSITS (Web non-custodial)
        # Escrow verification happens in API layer before calling this function
        # The transaction signatures are verified on-chain for both creator and acceptor
        total_required = amount + TRANSACTION_FEE
        logger.info(f"[REAL MAINNET] Web deposits verified in API layer: {total_required} SOL each")

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

        # Calculate payout (2x wager - 2% game fee)
        # Note: Transaction fees (0.025 SOL × 2 players) already collected separately
        total_pot = amount * 2
        game_fee = total_pot * HOUSE_FEE_PCT
        payout = total_pot - game_fee

        # Pay winner from house wallet (REAL MAINNET TRANSFER)
        payout_tx = await transfer_sol(
            rpc_url,
            house_wallet_secret,
            winner_wallet,
            payout
        )
        game.payout_tx = payout_tx

        # Send all fees to treasury (game fee + transaction fees from both players)
        total_transaction_fees = TRANSACTION_FEE * 2  # Both players paid 0.025 each
        total_fees = game_fee + total_transaction_fees
        if total_fees > 0:
            fee_tx = await transfer_sol(
                rpc_url,
                house_wallet_secret,
                treasury_address,
                total_fees
            )
            game.fee_tx = fee_tx

        logger.info(f"[REAL MAINNET] Player {game.winner_id} won {payout} SOL in PVP game, game fee: {game_fee} SOL, tx fees: {total_transaction_fees} SOL, total fees: {total_fees} SOL")

        # Mark game as completed
        game.status = GameStatus.COMPLETED
        game.completed_at = datetime.utcnow()

        return game

    except Exception as e:
        logger.error(f"PVP game failed: {e}")
        game.status = GameStatus.CANCELLED
        raise


async def play_pvp_game_with_escrows(
    rpc_url: str,
    treasury_address: str,
    creator: 'User',
    creator_side: CoinSide,
    creator_escrow_secret: str,
    creator_escrow_address: str,
    acceptor: 'User',
    acceptor_escrow_secret: str,
    acceptor_escrow_address: str,
    amount: float,
) -> Game:
    """Play a PVP game using isolated escrow wallets.

    SECURITY: Each player's funds are in separate escrow wallets.
    Winner is paid from their own escrow.
    Referral commissions paid from escrow before sweeping.
    All remaining funds (fees) from both escrows go to treasury.

    Args:
        rpc_url: Solana RPC URL
        treasury_address: Treasury wallet for all game fees
        creator: Creator user object
        creator_side: Creator's chosen side
        creator_escrow_secret: Creator's escrow wallet secret (encrypted, will decrypt)
        creator_escrow_address: Creator's escrow wallet address
        acceptor: Acceptor user object
        acceptor_escrow_secret: Acceptor's escrow wallet secret (encrypted, will decrypt)
        acceptor_escrow_address: Acceptor's escrow wallet address
        amount: Wager amount in SOL (per player)

    Returns:
        Completed Game object
    """
    from .escrow import payout_from_escrow, collect_fees_from_escrow
    from utils import decrypt_secret
    import os

    game_id = generate_game_id()
    encryption_key = os.getenv("ENCRYPTION_KEY")

    # Get player wallets (Web non-custodial)
    creator_wallet = creator.connected_wallet
    acceptor_wallet = acceptor.connected_wallet

    if not creator_wallet or not acceptor_wallet:
        raise Exception("One or both players have no wallet")

    # Acceptor takes opposite side
    acceptor_side = CoinSide.TAILS if creator_side == CoinSide.HEADS else CoinSide.HEADS

    # Create game
    game = Game(
        game_id=game_id,
        game_type=GameType.PVP,
        player1_id=creator.user_id,
        player1_side=creator_side,
        player1_wallet=creator_wallet,
        player2_id=acceptor.user_id,
        player2_side=acceptor_side,
        player2_wallet=acceptor_wallet,
        amount=amount,
        status=GameStatus.IN_PROGRESS,
        created_at=datetime.utcnow(),
    )

    try:
        # Decrypt escrow secrets
        creator_escrow_key = decrypt_secret(creator_escrow_secret, encryption_key)
        acceptor_escrow_key = decrypt_secret(acceptor_escrow_secret, encryption_key)

        logger.info(f"[ESCROW GAME] Starting PVP game with escrows: creator={creator_escrow_address}, acceptor={acceptor_escrow_address}")

        # STEP 1: FLIP COIN (Provably fair randomness)
        blockhash = await get_latest_blockhash(rpc_url)
        game.blockhash = blockhash

        result = flip_coin(blockhash, game_id)
        game.result = result

        logger.info(f"[ESCROW GAME] Coin flip result: {result.value}")

        # STEP 2: DETERMINE WINNER
        if result == creator_side:
            winner = creator
            winner_wallet = creator_wallet
            winner_escrow_secret = creator_escrow_key
            winner_escrow_address = creator_escrow_address
            loser_escrow_secret = acceptor_escrow_key
            loser_escrow_address = acceptor_escrow_address
            game.winner_id = creator.user_id
        else:
            winner = acceptor
            winner_wallet = acceptor_wallet
            winner_escrow_secret = acceptor_escrow_key
            winner_escrow_address = acceptor_escrow_address
            loser_escrow_secret = creator_escrow_key
            loser_escrow_address = creator_escrow_address
            game.winner_id = acceptor.user_id

        # STEP 3: CALCULATE PAYOUT (TIER-BASED FEES + TOKEN HOLDER DISCOUNT)
        # Use winner's combined discount (volume tier + token holdings, capped at 40%)
        # - Winner gets: (100% - fee_rate) from both escrows
        # - Treasury gets: fee_rate from both escrows + tx fees
        # - Loser gets: Nothing

        # Start with volume tier fee rate
        winner_fee_rate = winner.tier_fee_rate  # e.g., 0.019 for Bronze, 0.015 for Diamond

        # Apply token holder discount if enabled
        if TOKEN_ENABLED and hasattr(winner, 'token_tier') and winner.token_tier != "Normie":
            # Calculate combined discount (volume + token, capped at 40%)
            volume_discount = 1 - (winner.tier_fee_rate / BASE_FEE_RATE)
            token_discount = get_token_fee_discount(winner.token_tier)
            combined_discount = calculate_combined_discount(volume_discount, token_discount)
            winner_fee_rate = BASE_FEE_RATE * (1 - combined_discount)
            logger.info(f"[ESCROW GAME] Winner {winner.tier} + {winner.token_tier} token holder (combined: {combined_discount*100:.0f}% off)")

        payout_per_escrow = amount * (1 - winner_fee_rate)  # (100% - fee%) from each escrow
        total_payout = payout_per_escrow * 2  # Winner gets from both escrows
        fee_per_escrow = amount * winner_fee_rate  # Fee from each escrow
        total_fees = fee_per_escrow * 2 + (TRANSACTION_FEE * 2)  # Fees + tx costs

        logger.info(f"[ESCROW GAME] Winner tier: {winner.tier} (effective fee rate: {winner_fee_rate*100:.2f}%)")
        logger.info(f"[ESCROW GAME] Total payout to winner: {total_payout:.6f} SOL ({payout_per_escrow:.6f} from each escrow)")
        logger.info(f"[ESCROW GAME] Total fees to treasury: {total_fees:.6f} SOL ({fee_per_escrow:.6f} + {TRANSACTION_FEE} from each escrow)")

        # STEP 4: PAY WINNER FROM BOTH ESCROWS
        # Send 98% of bet from winner's own escrow
        winner_payout_tx = await payout_from_escrow(
            rpc_url,
            winner_escrow_secret,
            winner_wallet,
            payout_per_escrow
        )

        # Send 98% of bet from loser's escrow
        loser_payout_tx = await payout_from_escrow(
            rpc_url,
            loser_escrow_secret,
            winner_wallet,
            payout_per_escrow
        )

        game.payout_tx = f"{winner_payout_tx},{loser_payout_tx}"  # Store both tx signatures
        logger.info(f"[ESCROW GAME] Paid winner {total_payout} SOL (winner escrow: {winner_payout_tx}, loser escrow: {loser_payout_tx})")

        # STEP 5: SEND REFERRAL COMMISSION (if winner was referred)
        # Commission comes from loser's escrow BEFORE sweeping to treasury
        referral_commission_amount = 0.0
        if winner.referred_by:
            # Import here to avoid circular dependency
            from database import repo
            from tiers import calculate_referral_commission, get_referral_commission_rate
            from referrals import get_or_create_referral_escrow

            # Get referrer
            referrer = repo.Database().get_user(winner.referred_by)
            if referrer:
                # Calculate commission based on referrer's tier
                game_fees_only = fee_per_escrow * 2  # Exclude tx fees from commission
                referral_commission_amount = calculate_referral_commission(game_fees_only, referrer)

                # Send commission from loser's escrow to referrer's escrow wallet
                try:
                    # Get or create referrer's escrow
                    referrer_escrow, _ = await get_or_create_referral_escrow(
                        referrer, encryption_key, repo.Database()
                    )

                    # Transfer from loser's escrow to referrer's escrow
                    commission_tx = await transfer_sol(
                        rpc_url,
                        loser_escrow_secret,
                        referrer_escrow,
                        referral_commission_amount
                    )

                    # Update referrer's total earnings
                    referrer.referral_earnings += referral_commission_amount
                    repo.Database().save_user(referrer)

                    commission_rate = get_referral_commission_rate(referrer)
                    logger.info(f"[REFERRAL] Winner {winner.user_id} referred by {referrer.user_id}")
                    logger.info(f"[REFERRAL] Commission sent from escrow: {referral_commission_amount:.6f} SOL ({referrer.tier} tier: {commission_rate*100:.1f}%) | TX: {commission_tx}")
                except Exception as e:
                    logger.error(f"[REFERRAL] Failed to send commission: {e}", exc_info=True)
                    # Don't fail the game if referral payment fails
                    referral_commission_amount = 0.0

        # STEP 6: SWEEP ALL REMAINING FUNDS TO TREASURY
        # After paying winner and referral commission, sweep whatever is left
        # This includes: 2% game fees + 0.025 tx fees - referral commission + any dust
        winner_fee_tx = await collect_fees_from_escrow(
            rpc_url,
            winner_escrow_secret,
            winner_escrow_address,
            treasury_address  # Sweep everything remaining
        )

        loser_fee_tx = await collect_fees_from_escrow(
            rpc_url,
            loser_escrow_secret,
            loser_escrow_address,
            treasury_address  # Sweep everything remaining
        )

        logger.info(f"[ESCROW GAME] Swept remaining funds to treasury (winner escrow: {winner_fee_tx}, loser escrow: {loser_fee_tx})")
        net_treasury = total_fees - referral_commission_amount
        logger.info(f"[ESCROW GAME] Net revenue: ~{net_treasury:.6f} SOL (fees - {referral_commission_amount:.6f} referral)")

        # STEP 7: UPDATE TIER FOR BOTH PLAYERS (volume-based auto-upgrade)
        from tiers import update_user_tier

        # Update creator tier
        creator_upgraded = update_user_tier(creator)
        if creator_upgraded:
            repo.Database().save_user(creator)
            logger.info(f"[TIER] Creator {creator.user_id} upgraded to {creator.tier}")

        # Update acceptor tier
        acceptor_upgraded = update_user_tier(acceptor)
        if acceptor_upgraded:
            repo.Database().save_user(acceptor)
            logger.info(f"[TIER] Acceptor {acceptor.user_id} upgraded to {acceptor.tier}")

        # Mark game as completed
        game.status = GameStatus.COMPLETED
        game.completed_at = datetime.utcnow()

        logger.info(f"[ESCROW GAME] Game {game_id} completed - winner: {game.winner_id}, referral commission: {referral_commission_amount:.6f} SOL")

        return game

    except Exception as e:
        logger.error(f"Escrow PVP game failed: {e}")
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
