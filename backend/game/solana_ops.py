"""
Solana blockchain operations for Coinflip game.
"""
import asyncio
import logging
import math
from typing import Optional, Tuple
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction
import base58

logger = logging.getLogger(__name__)

LAMPORTS_PER_SOL = 1_000_000_000


def keypair_from_base58(secret: str) -> Keypair:
    """Create keypair from base58 secret key."""
    secret_bytes = base58.b58decode(secret)
    return Keypair.from_bytes(secret_bytes)


def generate_wallet() -> Tuple[str, str]:
    """Generate a new Solana wallet.

    Returns:
        Tuple of (public_key, base58_secret_key)
    """
    kp = Keypair()
    pubkey = str(kp.pubkey())
    secret = base58.b58encode(bytes(kp)).decode('utf-8')
    return pubkey, secret


async def get_sol_balance(rpc_url: str, wallet_address: str) -> float:
    """Get SOL balance for a wallet.

    IMPORTANT: Raises exception on RPC failure (don't silently return 0).
    """
    max_retries = 3
    last_error = None

    for attempt in range(max_retries):
        try:
            async with AsyncClient(rpc_url) as client:
                pubkey = Pubkey.from_string(wallet_address)
                resp = await client.get_balance(pubkey, Confirmed)
                if resp.value is not None:
                    balance = resp.value / LAMPORTS_PER_SOL
                    logger.info(f"[BALANCE] {wallet_address}: {balance} SOL")
                    return balance
                return 0.0
        except Exception as e:
            last_error = e
            logger.warning(f"[BALANCE] Attempt {attempt + 1}/{max_retries} failed for {wallet_address}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)  # Wait before retry

    # All retries failed - raise the error (don't return 0.0!)
    logger.error(f"[BALANCE] All retries failed for {wallet_address}: {last_error}")
    raise Exception(f"Failed to get balance for {wallet_address}: {last_error}")


async def transfer_sol(
    rpc_url: str,
    from_secret: str,
    to_address: str,
    amount_sol: float,
) -> Optional[str]:
    """Transfer SOL from one wallet to another.

    Returns:
        Transaction signature if successful, raises Exception on failure.
    """
    if amount_sol <= 0:
        raise Exception(f"Invalid amount: {amount_sol}")

    max_retries = 3
    last_error = None

    for attempt in range(max_retries):
        try:
            logger.info(f"[TRANSFER] Attempt {attempt + 1}: {amount_sol} SOL to {to_address}")

            async with AsyncClient(rpc_url) as client:
                kp = keypair_from_base58(from_secret)
                to_pubkey = Pubkey.from_string(to_address)
                lamports = math.floor(amount_sol * LAMPORTS_PER_SOL)

                # Get fresh blockhash
                blockhash_resp = await client.get_latest_blockhash(Confirmed)
                recent_blockhash = blockhash_resp.value.blockhash

                # Create transfer instruction
                transfer_ix = transfer(
                    TransferParams(
                        from_pubkey=kp.pubkey(),
                        to_pubkey=to_pubkey,
                        lamports=lamports,
                    )
                )

                # Build and sign transaction
                tx = Transaction.new_signed_with_payer(
                    [transfer_ix],
                    kp.pubkey(),
                    [kp],
                    recent_blockhash
                )

                # Send transaction (skip preflight to avoid stale blockhash)
                opts = TxOpts(skip_preflight=True)
                resp = await client.send_raw_transaction(bytes(tx), opts)
                tx_sig = str(resp.value)
                logger.info(f"[TRANSFER] Success! TX: {tx_sig}")
                return tx_sig

        except Exception as e:
            last_error = e
            logger.warning(f"[TRANSFER] Attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)

    logger.error(f"[TRANSFER] All retries failed: {last_error}")
    raise Exception(f"Transfer failed after {max_retries} attempts: {last_error}")


async def get_latest_blockhash(rpc_url: str) -> str:
    """Get the latest Solana blockhash for provably fair randomness.

    Returns:
        Blockhash as string
    """
    try:
        async with AsyncClient(rpc_url) as client:
            blockhash_resp = await client.get_latest_blockhash(Confirmed)
            return str(blockhash_resp.value.blockhash)
    except Exception as e:
        logger.error(f"Error getting blockhash: {e}")
        raise


async def create_game_wallet(rpc_url: str, house_secret: str, amount_sol: float) -> Tuple[str, str, str]:
    """Create a temporary game wallet and fund it for PVP games.

    Returns:
        Tuple of (game_wallet_address, game_wallet_secret, funding_tx_signature)
    """
    # Generate temporary game wallet
    game_addr, game_secret = generate_wallet()

    # Fund it with the wager amount from house wallet
    tx_sig = await transfer_sol(rpc_url, house_secret, game_addr, amount_sol)

    if not tx_sig:
        raise Exception("Failed to fund game wallet")

    logger.info(f"Created and funded game wallet {game_addr} with {amount_sol} SOL")
    return game_addr, game_secret, tx_sig


async def payout_winner(
    rpc_url: str,
    from_secret: str,
    winner_address: str,
    amount_sol: float,
    fee_pct: float = 0.02  # 2% fee
) -> Tuple[Optional[str], Optional[str]]:
    """Pay out winnings to winner and collect fee.

    Returns:
        Tuple of (payout_tx_signature, fee_tx_signature)
    """
    fee_amount = amount_sol * fee_pct
    payout_amount = amount_sol - fee_amount

    # Send winnings to winner
    payout_tx = await transfer_sol(rpc_url, from_secret, winner_address, payout_amount)

    # Send fee to treasury (if there's anything left in the wallet)
    # Note: For PVP games, the game wallet might be depleted after payout
    fee_tx = None

    return payout_tx, fee_tx


async def collect_fee(
    rpc_url: str,
    from_secret: str,
    treasury_address: str,
    amount_sol: float,
) -> Optional[str]:
    """Collect fee and send to treasury.

    Returns:
        Fee transaction signature
    """
    return await transfer_sol(rpc_url, from_secret, treasury_address, amount_sol)


async def verify_deposit_transaction(
    rpc_url: str,
    transaction_signature: str,
    expected_sender: str,
    expected_recipient: str,
    expected_amount: float,
    tolerance: float = 0.0001  # Allow small tolerance for rounding
) -> bool:
    """Verify a deposit transaction on-chain.

    Args:
        rpc_url: Solana RPC URL
        transaction_signature: Transaction signature to verify
        expected_sender: Expected sender wallet address
        expected_recipient: Expected recipient wallet address (house wallet)
        expected_amount: Expected amount in SOL
        tolerance: Tolerance for amount matching (default 0.0001 SOL)

    Returns:
        True if transaction is valid, False otherwise
    """
    try:
        from solders.signature import Signature

        async with AsyncClient(rpc_url) as client:
            # Parse signature
            sig = Signature.from_string(transaction_signature)

            # Get transaction details
            tx_resp = await client.get_transaction(
                sig,
                encoding="jsonParsed",
                commitment=Confirmed,
                max_supported_transaction_version=0
            )

            if not tx_resp.value:
                logger.warning(f"Transaction not found: {transaction_signature}")
                return False

            tx = tx_resp.value

            # Check if transaction was successful
            if tx.transaction.meta.err is not None:
                logger.warning(f"Transaction failed: {transaction_signature}")
                return False

            # Parse transaction to find transfer instruction
            # Structure: tx.transaction.transaction.message.instructions
            instructions = tx.transaction.transaction.message.instructions

            # Look for system program transfer instruction
            found_transfer = False
            for ix in instructions:
                # Check if this is a parsed instruction
                if hasattr(ix, 'parsed') and ix.parsed:
                    parsed = ix.parsed

                    # Check if it's a transfer instruction
                    if parsed.get('type') == 'transfer':
                        info = parsed.get('info', {})

                        # Verify sender
                        sender = info.get('source')
                        if sender != expected_sender:
                            logger.warning(f"Sender mismatch: expected {expected_sender}, got {sender}")
                            continue

                        # Verify recipient
                        recipient = info.get('destination')
                        if recipient != expected_recipient:
                            logger.warning(f"Recipient mismatch: expected {expected_recipient}, got {recipient}")
                            continue

                        # Verify amount
                        lamports = info.get('lamports', 0)
                        actual_amount = lamports / LAMPORTS_PER_SOL

                        if abs(actual_amount - expected_amount) > tolerance:
                            logger.warning(f"Amount mismatch: expected {expected_amount}, got {actual_amount}")
                            continue

                        # All checks passed
                        found_transfer = True
                        logger.info(f"Verified deposit: {actual_amount} SOL from {sender} to {recipient}")
                        break

            return found_transfer

    except Exception as e:
        logger.error(f"Error verifying transaction {transaction_signature}: {e}")
        return False


async def check_escrow_deposit(
    rpc_url: str,
    escrow_address: str,
    expected_sender: str,
    expected_amount: float,
    tolerance: float = 0.001
) -> Optional[str]:
    """Check if escrow has received a deposit from expected sender.

    Monitors escrow balance and recent transactions to find a matching deposit.

    Args:
        rpc_url: Solana RPC URL
        escrow_address: Escrow wallet to monitor
        expected_sender: Wallet that should send the deposit
        expected_amount: Expected deposit amount in SOL
        tolerance: Amount tolerance (default 0.001 SOL)

    Returns:
        Transaction signature if deposit found, None otherwise
    """
    try:
        async with AsyncClient(rpc_url) as client:
            # First check balance
            balance = await get_sol_balance(rpc_url, escrow_address)
            logger.info(f"[DEPOSIT_CHECK] Escrow {escrow_address[:8]}... balance: {balance} SOL (expecting {expected_amount} from {expected_sender[:8]}...)")

            if balance < expected_amount - tolerance:
                logger.info(f"[DEPOSIT_CHECK] Balance insufficient: {balance} < {expected_amount}")
                return None

            # Balance is sufficient - now find the transaction from expected sender
            escrow_pubkey = Pubkey.from_string(escrow_address)

            # Get recent signatures (last 10 transactions)
            sigs_resp = await client.get_signatures_for_address(
                escrow_pubkey,
                limit=10,
                commitment=Confirmed
            )

            if not sigs_resp.value:
                logger.warning(f"[DEPOSIT_CHECK] No transactions found for {escrow_address}")
                return None

            logger.info(f"[DEPOSIT_CHECK] Found {len(sigs_resp.value)} transactions to check")

            # Check each transaction
            for sig_info in sigs_resp.value:
                tx_sig = str(sig_info.signature)

                # Get transaction details
                tx_resp = await client.get_transaction(
                    sig_info.signature,
                    encoding="jsonParsed",
                    commitment=Confirmed,
                    max_supported_transaction_version=0
                )

                if not tx_resp.value:
                    continue

                tx = tx_resp.value

                # Skip failed transactions
                if tx.transaction.meta.err is not None:
                    continue

                # Look for transfer instruction
                instructions = tx.transaction.transaction.message.instructions

                for ix in instructions:
                    if hasattr(ix, 'parsed') and ix.parsed:
                        parsed = ix.parsed

                        if parsed.get('type') == 'transfer':
                            info = parsed.get('info', {})

                            sender = info.get('source')
                            recipient = info.get('destination')
                            lamports = info.get('lamports', 0)
                            actual_amount = lamports / LAMPORTS_PER_SOL

                            logger.info(f"[DEPOSIT_CHECK] Found transfer: {actual_amount} SOL from {sender[:8]}... to {recipient[:8]}... (expecting to {escrow_address[:8]}...)")

                            # Check if this matches our expected deposit (ACCEPT FROM ANY WALLET!)
                            # We only check recipient and amount, NOT sender - users can send from any wallet they want
                            if (recipient == escrow_address and
                                abs(actual_amount - expected_amount) <= tolerance):

                                logger.info(f"[DEPOSIT_CHECK] ✅ MATCH! Found deposit: {actual_amount} SOL from {sender} to {recipient} (tx: {tx_sig})")
                                return tx_sig
                            else:
                                logger.info(f"[DEPOSIT_CHECK] No match: recipient={recipient==escrow_address}, amount_match={abs(actual_amount - expected_amount) <= tolerance} (diff={abs(actual_amount - expected_amount)})")

            logger.info(f"[DEPOSIT_CHECK] Balance sufficient but no matching transaction from {expected_sender}")
            return None

    except Exception as e:
        logger.error(f"[DEPOSIT_CHECK] Error checking deposit: {e}")
        return None


async def get_escrow_sender(rpc_url: str, escrow_address: str) -> Optional[str]:
    """Find the wallet that sent SOL to this escrow by checking transaction history.

    Args:
        rpc_url: Solana RPC URL
        escrow_address: Escrow wallet address to check

    Returns:
        Sender wallet address if found, None otherwise
    """
    try:
        async with AsyncClient(rpc_url) as client:
            escrow_pubkey = Pubkey.from_string(escrow_address)

            # Get recent signatures
            sigs_resp = await client.get_signatures_for_address(
                escrow_pubkey,
                limit=10,
                commitment=Confirmed
            )

            if not sigs_resp.value:
                logger.warning(f"[GET_SENDER] No transactions found for {escrow_address}")
                return None

            # Check each transaction to find a transfer TO this escrow
            for sig_info in sigs_resp.value:
                # Get transaction details
                tx_resp = await client.get_transaction(
                    sig_info.signature,
                    encoding="jsonParsed",
                    commitment=Confirmed,
                    max_supported_transaction_version=0
                )

                if not tx_resp.value:
                    continue

                tx = tx_resp.value

                # Skip failed transactions
                if tx.transaction.meta.err is not None:
                    continue

                # Look for transfer instruction TO the escrow
                instructions = tx.transaction.transaction.message.instructions

                for ix in instructions:
                    if hasattr(ix, 'parsed') and ix.parsed:
                        parsed = ix.parsed

                        if parsed.get('type') == 'transfer':
                            info = parsed.get('info', {})
                            sender = info.get('source')
                            recipient = info.get('destination')

                            # Found a transfer TO this escrow
                            if recipient == escrow_address:
                                logger.info(f"[GET_SENDER] Found sender {sender} for escrow {escrow_address}")
                                return sender

            logger.warning(f"[GET_SENDER] No transfer found to escrow {escrow_address}")
            return None

    except Exception as e:
        logger.error(f"[GET_SENDER] Error finding sender: {e}")
        return None


async def verify_deposit_to_escrow(
    rpc_url: str,
    transaction_signature: str,
    expected_recipient: str,
    expected_amount: float,
    tolerance: float = 0.001  # Allow slightly larger tolerance
) -> bool:
    """Verify a deposit transaction to escrow (flexible - only checks recipient and amount).

    This version does NOT check the sender, allowing users to send from any wallet.

    Args:
        rpc_url: Solana RPC URL
        transaction_signature: Transaction signature to verify
        expected_recipient: Expected recipient wallet address (escrow)
        expected_amount: Expected amount in SOL
        tolerance: Tolerance for amount matching (default 0.001 SOL)

    Returns:
        True if transaction is valid, False otherwise
    """
    try:
        from solders.signature import Signature

        logger.info(f"[ESCROW_VERIFY] Verifying tx: {transaction_signature}")
        logger.info(f"[ESCROW_VERIFY] Expected recipient: {expected_recipient}")
        logger.info(f"[ESCROW_VERIFY] Expected amount: {expected_amount} SOL")

        async with AsyncClient(rpc_url) as client:
            # Parse signature
            sig = Signature.from_string(transaction_signature)

            # Get transaction details
            tx_resp = await client.get_transaction(
                sig,
                encoding="jsonParsed",
                commitment=Confirmed,
                max_supported_transaction_version=0
            )

            if not tx_resp.value:
                logger.warning(f"[ESCROW_VERIFY] Transaction not found: {transaction_signature}")
                return False

            tx = tx_resp.value

            # Check if transaction was successful
            if tx.transaction.meta.err is not None:
                logger.warning(f"[ESCROW_VERIFY] Transaction failed on-chain: {transaction_signature}")
                return False

            # Parse transaction to find transfer instruction
            instructions = tx.transaction.transaction.message.instructions

            # Look for system program transfer instruction
            for ix in instructions:
                # Check if this is a parsed instruction
                if hasattr(ix, 'parsed') and ix.parsed:
                    parsed = ix.parsed

                    # Check if it's a transfer instruction
                    if parsed.get('type') == 'transfer':
                        info = parsed.get('info', {})

                        # Verify recipient (escrow)
                        recipient = info.get('destination')
                        logger.info(f"[ESCROW_VERIFY] Found transfer to: {recipient}")

                        if recipient != expected_recipient:
                            logger.warning(f"[ESCROW_VERIFY] Recipient mismatch: expected {expected_recipient}, got {recipient}")
                            continue

                        # Verify amount
                        lamports = info.get('lamports', 0)
                        actual_amount = lamports / LAMPORTS_PER_SOL
                        logger.info(f"[ESCROW_VERIFY] Transfer amount: {actual_amount} SOL")

                        if abs(actual_amount - expected_amount) > tolerance:
                            logger.warning(f"[ESCROW_VERIFY] Amount mismatch: expected {expected_amount}, got {actual_amount} (diff: {abs(actual_amount - expected_amount)})")
                            continue

                        # All checks passed!
                        sender = info.get('source', 'unknown')
                        logger.info(f"[ESCROW_VERIFY] SUCCESS! Verified {actual_amount} SOL from {sender} to {recipient}")
                        return True

            logger.warning(f"[ESCROW_VERIFY] No matching transfer found in transaction")
            return False

    except Exception as e:
        logger.error(f"[ESCROW_VERIFY] Error verifying transaction {transaction_signature}: {e}", exc_info=True)
        return False
