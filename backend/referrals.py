"""
Referral commission system with individual escrow wallets.

Each user gets their own referral payout escrow where commissions accumulate.
Users can claim earnings whenever they want (with 1% treasury fee).
"""
import logging
from typing import Tuple
from solders.keypair import Keypair

from database import Database, User
from game.solana_ops import transfer_sol, get_sol_balance
from utils.encryption import encrypt_secret, decrypt_secret
from security import audit_logger, AuditEventType, AuditSeverity

logger = logging.getLogger(__name__)


async def get_or_create_referral_escrow(
    user: User,
    encryption_key: str,
    db: Database
) -> Tuple[str, str]:
    """Get or create referral payout escrow for user.

    Args:
        user: User object
        encryption_key: Encryption key for storing private key
        db: Database instance

    Returns:
        Tuple of (escrow_address, encrypted_secret)
    """
    # If user already has referral escrow, return it
    if user.referral_payout_escrow_address and user.referral_payout_escrow_secret:
        return user.referral_payout_escrow_address, user.referral_payout_escrow_secret

    # Generate new escrow wallet
    escrow_keypair = Keypair()
    escrow_address = str(escrow_keypair.pubkey())
    encrypted_secret = encrypt_secret(str(escrow_keypair.secret()), encryption_key)

    # Save to user
    user.referral_payout_escrow_address = escrow_address
    user.referral_payout_escrow_secret = encrypted_secret
    db.save_user(user)

    logger.info(f"Created referral escrow for user {user.user_id}: {escrow_address}")

    # Log to audit system
    audit_logger.log(
        event_type=AuditEventType.ESCROW_CREATED,
        severity=AuditSeverity.INFO,
        user_id=user.user_id,
        details=f"Referral payout escrow created: {escrow_address}"
    )

    return escrow_address, encrypted_secret


async def send_referral_commission(
    referrer: User,
    commission_amount: float,
    from_wallet_secret: str,
    rpc_url: str,
    encryption_key: str,
    db: Database,
    game_id: str
) -> str:
    """Send referral commission to referrer's escrow wallet.

    Args:
        referrer: Referrer user object
        commission_amount: Amount to send (in SOL)
        from_wallet_secret: Treasury wallet secret key
        rpc_url: Solana RPC URL
        encryption_key: Encryption key
        db: Database instance
        game_id: Game ID for tracking

    Returns:
        Transaction signature
    """
    # Get or create referrer's escrow
    escrow_address, _ = await get_or_create_referral_escrow(referrer, encryption_key, db)

    # Send commission to escrow
    tx_sig = await transfer_sol(
        rpc_url=rpc_url,
        from_secret=from_wallet_secret,
        to_pubkey=escrow_address,
        amount_sol=commission_amount
    )

    # Update referrer's total earnings
    referrer.referral_earnings += commission_amount
    db.save_user(referrer)

    logger.info(
        f"Sent {commission_amount:.6f} SOL referral commission to user {referrer.user_id} "
        f"(escrow: {escrow_address[:8]}...{escrow_address[-4:]}) | TX: {tx_sig}"
    )

    # Log to audit system
    audit_logger.log(
        event_type=AuditEventType.REFERRAL_COMMISSION,
        severity=AuditSeverity.INFO,
        user_id=referrer.user_id,
        details=f"Referral commission: {commission_amount:.6f} SOL for game {game_id} | TX: {tx_sig}"
    )

    return tx_sig


async def get_referral_escrow_balance(
    user: User,
    rpc_url: str
) -> float:
    """Get current balance of user's referral escrow wallet.

    Args:
        user: User object
        rpc_url: Solana RPC URL

    Returns:
        Balance in SOL
    """
    if not user.referral_payout_escrow_address:
        return 0.0

    try:
        balance = await get_sol_balance(rpc_url, user.referral_payout_escrow_address)
        return balance
    except Exception as e:
        logger.error(f"Failed to get referral escrow balance for user {user.user_id}: {e}")
        return 0.0


async def claim_referral_earnings(
    user: User,
    rpc_url: str,
    encryption_key: str,
    treasury_wallet: str,
    db: Database
) -> Tuple[bool, str, float]:
    """Claim referral earnings from escrow to payout wallet.

    Takes 1% treasury fee on claims.

    Args:
        user: User object
        rpc_url: Solana RPC URL
        encryption_key: Encryption key for decrypting escrow secret
        treasury_wallet: Treasury wallet address (receives 1% fee)
        db: Database instance

    Returns:
        Tuple of (success, message, amount_claimed)
    """
    # Check user has payout wallet set
    if not user.payout_wallet:
        return False, "⚠️ You must set a payout wallet before claiming referral earnings. Use /set_payout_wallet", 0.0

    # Check user has referral escrow
    if not user.referral_payout_escrow_address or not user.referral_payout_escrow_secret:
        return False, "You have no referral earnings to claim yet.", 0.0

    # Get escrow balance
    balance = await get_referral_escrow_balance(user, rpc_url)

    # Need at least 0.01 SOL to make claim worthwhile (covers fees + minimum)
    if balance < 0.01:
        return False, f"Insufficient balance to claim. You have {balance:.6f} SOL (minimum 0.01 SOL required).", 0.0

    # Decrypt escrow secret
    try:
        escrow_secret = decrypt_secret(user.referral_payout_escrow_secret, encryption_key)
    except Exception as e:
        logger.error(f"Failed to decrypt referral escrow for user {user.user_id}: {e}")
        return False, "Error accessing your referral escrow. Please contact support.", 0.0

    # Calculate amounts (1% treasury fee + 0.000005 SOL for tx fees)
    treasury_fee_amount = balance * 0.01
    tx_fee_reserve = 0.000005 * 2  # Two transactions (to treasury, to user)
    user_claim_amount = balance - treasury_fee_amount - tx_fee_reserve

    if user_claim_amount <= 0:
        return False, f"Balance too low after fees. Need at least {treasury_fee_amount + tx_fee_reserve:.6f} SOL.", 0.0

    try:
        # Send treasury fee
        treasury_tx = await transfer_sol(
            rpc_url=rpc_url,
            from_secret=escrow_secret,
            to_pubkey=treasury_wallet,
            amount_sol=treasury_fee_amount
        )

        logger.info(f"Treasury fee collected: {treasury_fee_amount:.6f} SOL from user {user.user_id} claim | TX: {treasury_tx}")

        # Send remainder to user's payout wallet
        payout_tx = await transfer_sol(
            rpc_url=rpc_url,
            from_secret=escrow_secret,
            to_pubkey=user.payout_wallet,
            amount_sol=user_claim_amount
        )

        # Update user stats
        user.total_referral_claimed += user_claim_amount
        db.save_user(user)

        logger.info(
            f"Referral claim successful: User {user.user_id} claimed {user_claim_amount:.6f} SOL "
            f"(fee: {treasury_fee_amount:.6f} SOL) | TX: {payout_tx}"
        )

        # Log to audit system
        audit_logger.log(
            event_type=AuditEventType.PAYOUT_PROCESSED,
            severity=AuditSeverity.INFO,
            user_id=user.user_id,
            details=f"Referral claim: {user_claim_amount:.6f} SOL (fee: {treasury_fee_amount:.6f}) | TX: {payout_tx}"
        )

        return True, (
            f"✅ Successfully claimed {user_claim_amount:.6f} SOL!\n\n"
            f"Sent to: {user.payout_wallet[:8]}...{user.payout_wallet[-4:]}\n"
            f"Treasury fee (1%): {treasury_fee_amount:.6f} SOL\n"
            f"Transaction: {payout_tx}"
        ), user_claim_amount

    except Exception as e:
        logger.error(f"Failed to claim referral earnings for user {user.user_id}: {e}", exc_info=True)
        return False, f"Failed to process claim: {str(e)}", 0.0
