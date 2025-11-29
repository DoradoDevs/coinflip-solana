"""
Escrow wallet management for secure wager handling.

SECURITY: Each wager gets TWO unique escrow wallets (one for creator, one for acceptor).
This eliminates the single point of failure of using one house wallet for everything.

Inspired by VolT's battle-tested transaction patterns.
"""
import logging
from typing import Tuple, Optional
from datetime import datetime

from .solana_ops import (
    generate_wallet,
    transfer_sol,
    get_sol_balance,
    verify_deposit_transaction
)
from utils import encrypt_secret, decrypt_secret
from database import User, UsedSignature

logger = logging.getLogger(__name__)

# Solana rent-exempt minimum (from VolT)
RENT_EXEMPT_LAMPORTS = 890880
RENT_EXEMPT_SOL = RENT_EXEMPT_LAMPORTS / 1_000_000_000  # ~0.00089 SOL


async def create_escrow_wallet(
    rpc_url: str,
    encryption_key: str,
    amount: float,
    transaction_fee: float,
    user: User,
    user_wallet: str,
    deposit_tx_signature: Optional[str],
    wager_id: str,
    db
) -> Tuple[str, str, str]:
    """Create a unique escrow wallet and collect deposit.

    SECURITY:
    - Generates unique wallet per wager side
    - Verifies deposit on-chain (Web users)
    - Prevents signature reuse
    - Tracks used signatures in database

    Args:
        rpc_url: Solana RPC endpoint
        encryption_key: Encryption key for secrets
        amount: Wager amount in SOL
        transaction_fee: Fixed transaction fee (0.025 SOL)
        user: User object (creator or acceptor)
        user_wallet: User's wallet address
        deposit_tx_signature: Transaction signature (for Web) or None (for Telegram)
        wager_id: Wager ID for tracking
        db: Database instance

    Returns:
        Tuple of (escrow_address, encrypted_secret, deposit_tx_signature)

    Raises:
        Exception: If deposit verification fails or signature already used
    """
    total_required = amount + transaction_fee

    # Generate unique escrow wallet
    escrow_address, escrow_secret = generate_wallet()
    logger.info(f"[ESCROW] Generated unique wallet {escrow_address} for wager {wager_id}")

    # Encrypt secret for storage
    encrypted_secret = encrypt_secret(escrow_secret, encryption_key)

    # COLLECT DEPOSIT based on platform
    deposit_tx = None

    if user.platform == "telegram" and user.encrypted_secret:
        # TELEGRAM (Custodial): Transfer from user's wallet to escrow
        logger.info(f"[ESCROW] Collecting {total_required} SOL from Telegram user {user.user_id}")

        # Decrypt user's wallet secret
        user_secret = decrypt_secret(user.encrypted_secret, encryption_key)

        # Transfer to escrow wallet (REAL MAINNET TRANSFER)
        deposit_tx = await transfer_sol(
            rpc_url,
            user_secret,
            escrow_address,
            total_required
        )

        logger.info(f"[REAL MAINNET] Collected {total_required} SOL from {user_wallet} → escrow {escrow_address} (tx: {deposit_tx})")

    elif user.platform == "web":
        # WEB (Non-Custodial): Verify user sent to escrow
        if not deposit_tx_signature:
            raise Exception(
                f"Web users must send {total_required} SOL to escrow wallet {escrow_address} "
                f"and provide transaction signature"
            )

        # SECURITY: Check if signature already used
        if db.signature_already_used(deposit_tx_signature):
            used_sig = db.get_used_signature(deposit_tx_signature)
            raise Exception(
                f"Transaction signature already used for {used_sig.used_for} "
                f"by {used_sig.user_wallet} at {used_sig.used_at}"
            )

        # Verify deposit on-chain
        is_valid = await verify_deposit_transaction(
            rpc_url,
            deposit_tx_signature,
            user_wallet,  # sender
            escrow_address,  # recipient (unique escrow)
            total_required  # amount
        )

        if not is_valid:
            raise Exception(
                f"Invalid deposit transaction. Please send exactly {total_required} SOL "
                f"({amount} wager + {transaction_fee} fee) to escrow wallet {escrow_address}"
            )

        # SECURITY: Mark signature as used
        db.save_used_signature(UsedSignature(
            signature=deposit_tx_signature,
            user_wallet=user_wallet,
            used_for=wager_id,
            used_at=datetime.utcnow()
        ))

        deposit_tx = deposit_tx_signature
        logger.info(f"[REAL MAINNET] Verified Web deposit {total_required} SOL from {user_wallet} → escrow {escrow_address} (tx: {deposit_tx})")

    # Verify escrow balance
    escrow_balance = await get_sol_balance(rpc_url, escrow_address)
    logger.info(f"[ESCROW] Wallet {escrow_address} balance: {escrow_balance} SOL (required: {total_required} SOL)")

    if escrow_balance < total_required:
        raise Exception(
            f"Escrow wallet underfunded: {escrow_balance} SOL available, "
            f"{total_required} SOL required"
        )

    return escrow_address, encrypted_secret, deposit_tx


async def payout_from_escrow(
    rpc_url: str,
    escrow_secret: str,
    winner_wallet: str,
    payout_amount: float
) -> str:
    """Pay winner from their escrow wallet.

    Args:
        rpc_url: Solana RPC endpoint
        escrow_secret: Decrypted escrow wallet secret
        winner_wallet: Winner's main wallet address
        payout_amount: Amount to pay (98% of pot)

    Returns:
        Transaction signature

    Raises:
        Exception: If transfer fails
    """
    logger.info(f"[ESCROW] Paying winner {payout_amount} SOL from escrow to {winner_wallet}")

    payout_tx = await transfer_sol(
        rpc_url,
        escrow_secret,
        winner_wallet,
        payout_amount
    )

    logger.info(f"[REAL MAINNET] Paid winner {payout_amount} SOL (tx: {payout_tx})")
    return payout_tx


async def collect_fees_from_escrow(
    rpc_url: str,
    escrow_secret: str,
    escrow_address: str,
    house_wallet: str
) -> Optional[str]:
    """Transfer all remaining funds from escrow to house wallet.

    This collects:
    - Remaining SOL from winner's escrow after payout
    - All SOL from loser's escrow
    - Leaves rent-exempt minimum for account cleanup

    Args:
        rpc_url: Solana RPC endpoint
        escrow_secret: Decrypted escrow wallet secret
        escrow_address: Escrow wallet public address
        house_wallet: House wallet address to receive funds

    Returns:
        Transaction signature or None if balance too low

    Raises:
        Exception: If transfer fails
    """
    # Check remaining balance
    escrow_balance = await get_sol_balance(rpc_url, escrow_address)
    logger.info(f"[ESCROW] Collecting remaining balance from {escrow_address}: {escrow_balance} SOL")

    # Keep rent-exempt minimum (following VolT's pattern)
    if escrow_balance <= RENT_EXEMPT_SOL:
        logger.info(f"[ESCROW] Balance too low to collect ({escrow_balance} SOL ≤ {RENT_EXEMPT_SOL} SOL), leaving as dust")
        return None

    # Transfer remaining balance to house
    amount_to_collect = escrow_balance - RENT_EXEMPT_SOL

    fee_tx = await transfer_sol(
        rpc_url,
        escrow_secret,
        house_wallet,
        amount_to_collect
    )

    logger.info(f"[REAL MAINNET] Collected {amount_to_collect} SOL from escrow {escrow_address} → house {house_wallet} (tx: {fee_tx})")
    return fee_tx


async def refund_from_escrow(
    rpc_url: str,
    escrow_secret: str,
    escrow_address: str,
    creator_wallet: str,
    fee_destination: str,
    wager_amount: float,
    transaction_fee: float
) -> Tuple[str, str]:
    """Refund wager from escrow (cancel flow).

    Fee Structure on Cancel:
    - Refund: wager_amount → creator's wallet
    - Keep: transaction_fee → treasury wallet
    - No 2% game fee (only on completed games)

    Args:
        rpc_url: Solana RPC endpoint
        escrow_secret: Decrypted escrow wallet secret
        escrow_address: Escrow wallet public address
        creator_wallet: Creator's main wallet address
        fee_destination: Treasury wallet address for fee collection
        wager_amount: Wager amount to refund
        transaction_fee: Transaction fee to keep (0.025 SOL)

    Returns:
        Tuple of (refund_tx_signature, fee_tx_signature)

    Raises:
        Exception: If transfers fail
    """
    # Check escrow balance
    escrow_balance = await get_sol_balance(rpc_url, escrow_address)
    logger.info(f"[ESCROW REFUND] Escrow {escrow_address} balance: {escrow_balance} SOL")

    # Refund wager amount to creator
    logger.info(f"[ESCROW REFUND] Refunding {wager_amount} SOL to creator {creator_wallet}")
    refund_tx = await transfer_sol(
        rpc_url,
        escrow_secret,
        creator_wallet,
        wager_amount
    )

    logger.info(f"[REAL MAINNET] Refunded {wager_amount} SOL to creator (tx: {refund_tx})")

    # Collect transaction fee + any remaining dust to treasury
    remaining_balance = await get_sol_balance(rpc_url, escrow_address)
    logger.info(f"[ESCROW REFUND] Remaining balance: {remaining_balance} SOL")

    if remaining_balance <= RENT_EXEMPT_SOL:
        logger.info(f"[ESCROW REFUND] No fees to collect (balance ≤ rent minimum)")
        return refund_tx, None

    # Transfer remaining to treasury (transaction fee + dust)
    amount_to_treasury = remaining_balance - RENT_EXEMPT_SOL
    logger.info(f"[ESCROW REFUND] Collecting {amount_to_treasury} SOL (fee + dust) to treasury")

    fee_tx = await transfer_sol(
        rpc_url,
        escrow_secret,
        fee_destination,
        amount_to_treasury
    )

    logger.info(f"[REAL MAINNET] Collected {amount_to_treasury} SOL fee to treasury (tx: {fee_tx})")

    return refund_tx, fee_tx


async def check_escrow_balance(
    rpc_url: str,
    escrow_address: str,
    required_amount: float
) -> bool:
    """Verify escrow wallet has sufficient balance.

    Args:
        rpc_url: Solana RPC endpoint
        escrow_address: Escrow wallet public address
        required_amount: Required balance in SOL

    Returns:
        True if balance sufficient, False otherwise
    """
    balance = await get_sol_balance(rpc_url, escrow_address)
    is_sufficient = balance >= required_amount

    if is_sufficient:
        logger.info(f"[ESCROW CHECK] {escrow_address} has {balance} SOL (≥ {required_amount} SOL) ✓")
    else:
        logger.warning(f"[ESCROW CHECK] {escrow_address} has {balance} SOL (< {required_amount} SOL) ✗")

    return is_sufficient
