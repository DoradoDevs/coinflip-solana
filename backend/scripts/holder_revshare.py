"""
$FLIP Token Holder Revenue Share Distribution

Uses hybrid square root distribution model for fair payouts:
- Takes square root of each holder's balance
- Distributes proportionally based on sqrt(balance)
- Larger holders get more, but not disproportionately more

Example with 1 SOL to distribute:
- Holder A (1M tokens): sqrt(1M) = 1000 → 70.6%
- Holder B (100K tokens): sqrt(100K) = 316 → 22.3%
- Holder C (10K tokens): sqrt(10K) = 100 → 7.1%

vs Pure Proportional:
- A: 90.1%, B: 9%, C: 0.9%

Much fairer to smaller holders while still rewarding whales!
"""

import asyncio
import logging
import math
import os
import sys
from datetime import datetime
from typing import List, Dict, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.system_program import transfer, TransferParams
from solders.transaction import Transaction
from solders.message import Message
import base58
import httpx

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TOKEN_MINT = os.getenv("FLIP_TOKEN_MINT", "PLACEHOLDER_CONTRACT_ADDRESS")
RPC_URL = os.getenv("RPC_URL")
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "")  # For fetching top holders

# Distribution settings
TOP_HOLDERS_COUNT = 100  # Distribute to top 100 holders
MIN_BALANCE_FOR_REWARDS = 100_000  # Minimum tokens to qualify (100K)
MIN_PAYOUT_AMOUNT = 0.001  # Minimum SOL payout (to avoid dust)

# Excluded wallets (LP only - team wallets receive their share!)
EXCLUDED_WALLETS = [
    # Add LP wallet address here after token launch
    # "LiquidityPoolAddress...",
]


@dataclass
class HolderInfo:
    """Token holder information."""
    wallet: str
    balance: float  # Token balance
    sqrt_balance: float = 0.0  # Square root of balance
    share_percent: float = 0.0  # Percentage share
    payout_amount: float = 0.0  # SOL to receive


async def get_top_holders_helius(token_mint: str, limit: int = 100) -> List[Dict]:
    """
    Fetch top token holders using Helius API.

    Helius provides a convenient endpoint for this.
    """
    if not HELIUS_API_KEY:
        logger.error("HELIUS_API_KEY not set - cannot fetch holders")
        return []

    url = f"https://api.helius.xyz/v0/token-accounts?api-key={HELIUS_API_KEY}"

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={
            "mint": token_mint,
            "limit": limit * 2,  # Fetch extra to account for exclusions
            "displayOptions": {
                "showZeroBalance": False
            }
        })

        if response.status_code != 200:
            logger.error(f"Helius API error: {response.status_code} - {response.text}")
            return []

        data = response.json()
        return data.get("token_accounts", [])


async def get_top_holders_rpc(token_mint: str, rpc_url: str, limit: int = 100) -> List[Dict]:
    """
    Fetch top token holders using standard RPC.

    Note: This is slower and may not return all holders.
    For production, use Helius or similar indexed API.
    """
    async with AsyncClient(rpc_url) as client:
        # Get largest token accounts
        response = await client.get_token_largest_accounts(Pubkey.from_string(token_mint))

        if response.value is None:
            return []

        holders = []
        for account in response.value[:limit]:
            # Get the owner of each token account
            account_info = await client.get_account_info(account.address)
            if account_info.value:
                # Parse token account to get owner
                # This is simplified - real implementation needs proper parsing
                holders.append({
                    "address": str(account.address),
                    "amount": float(account.amount.ui_amount or 0),
                    "owner": "unknown"  # Would need to parse account data
                })

        return holders


def calculate_sqrt_distribution(
    holders: List[HolderInfo],
    total_sol: float
) -> List[HolderInfo]:
    """
    Calculate distribution using square root model.

    Each holder's share = sqrt(their_balance) / sum(sqrt(all_balances))
    """
    # Calculate square root of each balance
    for holder in holders:
        holder.sqrt_balance = math.sqrt(holder.balance)

    # Calculate total sqrt
    total_sqrt = sum(h.sqrt_balance for h in holders)

    if total_sqrt == 0:
        logger.error("Total sqrt balance is 0 - no distribution possible")
        return holders

    # Calculate each holder's share
    for holder in holders:
        holder.share_percent = (holder.sqrt_balance / total_sqrt) * 100
        holder.payout_amount = (holder.sqrt_balance / total_sqrt) * total_sol

    return holders


def print_distribution_preview(
    holders: List[HolderInfo],
    total_sol: float
):
    """Print a preview of the distribution."""
    print("\n" + "=" * 70)
    print(f"SQUARE ROOT DISTRIBUTION PREVIEW")
    print(f"Total to distribute: {total_sol:.4f} SOL")
    print(f"Recipients: {len(holders)}")
    print("=" * 70)

    # Sort by payout amount (descending)
    sorted_holders = sorted(holders, key=lambda h: h.payout_amount, reverse=True)

    print(f"\n{'Rank':<6}{'Wallet':<20}{'Balance':<15}{'Share %':<12}{'Payout (SOL)':<15}")
    print("-" * 70)

    for i, h in enumerate(sorted_holders[:20], 1):  # Show top 20
        wallet_short = h.wallet[:8] + "..." + h.wallet[-4:]
        print(f"{i:<6}{wallet_short:<20}{h.balance:>12,.0f}{h.share_percent:>10.2f}%{h.payout_amount:>13.6f}")

    if len(sorted_holders) > 20:
        print(f"... and {len(sorted_holders) - 20} more recipients")

    # Summary stats
    total_payout = sum(h.payout_amount for h in holders)
    avg_payout = total_payout / len(holders) if holders else 0
    max_payout = max(h.payout_amount for h in holders) if holders else 0
    min_payout = min(h.payout_amount for h in holders) if holders else 0

    print("\n" + "-" * 70)
    print(f"Total Payout: {total_payout:.6f} SOL")
    print(f"Average Payout: {avg_payout:.6f} SOL")
    print(f"Largest Payout: {max_payout:.6f} SOL ({(max_payout/total_sol)*100:.1f}%)")
    print(f"Smallest Payout: {min_payout:.6f} SOL ({(min_payout/total_sol)*100:.1f}%)")
    print(f"Max/Min Ratio: {max_payout/min_payout:.1f}x" if min_payout > 0 else "N/A")
    print("=" * 70)


async def send_sol_batch(
    rpc_url: str,
    sender_keypair: Keypair,
    recipients: List[Tuple[str, float]],  # [(wallet, amount), ...]
    batch_size: int = 10
) -> List[str]:
    """
    Send SOL to multiple recipients in batches.

    Returns list of transaction signatures.
    """
    signatures = []

    async with AsyncClient(rpc_url) as client:
        # Get recent blockhash
        blockhash_resp = await client.get_latest_blockhash()
        recent_blockhash = blockhash_resp.value.blockhash

        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]

            # Create transfer instructions for this batch
            instructions = []
            for wallet, amount in batch:
                if amount < MIN_PAYOUT_AMOUNT:
                    logger.info(f"Skipping {wallet} - amount {amount:.6f} below minimum")
                    continue

                lamports = int(amount * 1_000_000_000)  # Convert SOL to lamports

                ix = transfer(TransferParams(
                    from_pubkey=sender_keypair.pubkey(),
                    to_pubkey=Pubkey.from_string(wallet),
                    lamports=lamports
                ))
                instructions.append(ix)

            if not instructions:
                continue

            # Build and send transaction
            try:
                msg = Message.new_with_blockhash(
                    instructions,
                    sender_keypair.pubkey(),
                    recent_blockhash
                )
                tx = Transaction([sender_keypair], msg, recent_blockhash)

                result = await client.send_transaction(tx)

                if result.value:
                    signatures.append(str(result.value))
                    logger.info(f"Batch {i//batch_size + 1}: {len(instructions)} transfers sent - {result.value}")
                else:
                    logger.error(f"Batch {i//batch_size + 1} failed: {result}")

            except Exception as e:
                logger.error(f"Batch {i//batch_size + 1} error: {e}")

            # Small delay between batches
            await asyncio.sleep(0.5)

    return signatures


async def distribute_rewards(
    total_sol: float,
    sender_private_key: str,
    dry_run: bool = True
) -> Dict:
    """
    Main distribution function.

    Args:
        total_sol: Total SOL to distribute
        sender_private_key: Base58 encoded private key of sender wallet
        dry_run: If True, only preview without sending

    Returns:
        Distribution summary
    """
    logger.info(f"Starting holder reward distribution: {total_sol} SOL")

    # Check token mint
    if TOKEN_MINT == "PLACEHOLDER_CONTRACT_ADDRESS":
        logger.error("TOKEN_MINT not configured - set FLIP_TOKEN_MINT in environment")
        return {"error": "Token not configured"}

    # Fetch top holders
    logger.info(f"Fetching top {TOP_HOLDERS_COUNT} holders...")

    if HELIUS_API_KEY:
        raw_holders = await get_top_holders_helius(TOKEN_MINT, TOP_HOLDERS_COUNT)
    else:
        raw_holders = await get_top_holders_rpc(TOKEN_MINT, RPC_URL, TOP_HOLDERS_COUNT)

    if not raw_holders:
        logger.error("No holders found")
        return {"error": "No holders found"}

    logger.info(f"Found {len(raw_holders)} holder accounts")

    # Filter and convert to HolderInfo
    holders = []
    for h in raw_holders:
        wallet = h.get("owner") or h.get("address", "")
        balance = float(h.get("amount") or h.get("tokenAmount", {}).get("uiAmount", 0))

        # Skip excluded wallets
        if wallet in EXCLUDED_WALLETS:
            logger.info(f"Excluding wallet: {wallet[:8]}...")
            continue

        # Skip wallets below minimum
        if balance < MIN_BALANCE_FOR_REWARDS:
            continue

        holders.append(HolderInfo(wallet=wallet, balance=balance))

    # Limit to top N
    holders = sorted(holders, key=lambda h: h.balance, reverse=True)[:TOP_HOLDERS_COUNT]

    if not holders:
        logger.error("No eligible holders after filtering")
        return {"error": "No eligible holders"}

    logger.info(f"Eligible holders: {len(holders)}")

    # Calculate distribution
    holders = calculate_sqrt_distribution(holders, total_sol)

    # Preview
    print_distribution_preview(holders, total_sol)

    if dry_run:
        logger.info("DRY RUN - No transactions sent")
        return {
            "status": "dry_run",
            "total_sol": total_sol,
            "recipients": len(holders),
            "distribution": [
                {
                    "wallet": h.wallet,
                    "balance": h.balance,
                    "share_percent": h.share_percent,
                    "payout_sol": h.payout_amount
                }
                for h in holders
            ]
        }

    # Execute distribution
    logger.info("Executing distribution...")

    try:
        sender_keypair = Keypair.from_base58_string(sender_private_key)
    except Exception as e:
        logger.error(f"Invalid sender private key: {e}")
        return {"error": "Invalid sender key"}

    # Prepare recipients list
    recipients = [(h.wallet, h.payout_amount) for h in holders if h.payout_amount >= MIN_PAYOUT_AMOUNT]

    # Send transactions
    signatures = await send_sol_batch(RPC_URL, sender_keypair, recipients)

    return {
        "status": "completed",
        "total_sol": total_sol,
        "recipients": len(recipients),
        "transactions": signatures,
        "timestamp": datetime.utcnow().isoformat()
    }


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Distribute rewards to $FLIP token holders")
    parser.add_argument("amount", type=float, help="Total SOL to distribute")
    parser.add_argument("--execute", action="store_true", help="Actually send transactions (default is dry run)")
    parser.add_argument("--key", type=str, help="Sender wallet private key (base58)")

    args = parser.parse_args()

    if args.execute and not args.key:
        print("ERROR: --key required when using --execute")
        sys.exit(1)

    result = asyncio.run(distribute_rewards(
        total_sol=args.amount,
        sender_private_key=args.key or "",
        dry_run=not args.execute
    ))

    print(f"\nResult: {result.get('status', 'unknown')}")
