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
    """Get SOL balance for a wallet."""
    try:
        async with AsyncClient(rpc_url) as client:
            pubkey = Pubkey.from_string(wallet_address)
            resp = await client.get_balance(pubkey, Confirmed)
            if resp.value is not None:
                return resp.value / LAMPORTS_PER_SOL
            return 0.0
    except Exception as e:
        logger.error(f"Error getting balance for {wallet_address}: {e}")
        return 0.0


async def transfer_sol(
    rpc_url: str,
    from_secret: str,
    to_address: str,
    amount_sol: float,
) -> Optional[str]:
    """Transfer SOL from one wallet to another.

    Returns:
        Transaction signature if successful, None otherwise.
    """
    if amount_sol <= 0:
        return None

    try:
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
            return str(resp.value)

    except Exception as e:
        logger.error(f"Transfer failed: {e}")
        raise Exception(f"Transfer failed: {e}")


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
