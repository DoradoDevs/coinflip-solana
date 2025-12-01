"""
Token Balance Checker for $FLIP Token

Checks SPL token balances on Solana and caches results.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
import base58

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

from token_config import (
    TOKEN_MINT,
    TOKEN_DECIMALS,
    TOKEN_ENABLED,
    BALANCE_CACHE_TTL,
    get_tier_for_balance,
    get_tier_info,
    get_next_tier
)

logger = logging.getLogger(__name__)

# In-memory cache for token balances
# Format: {wallet_address: (balance, tier, timestamp)}
_balance_cache: dict[str, Tuple[float, str, datetime]] = {}


def get_associated_token_address(wallet: str, token_mint: str) -> str:
    """
    Derive the Associated Token Account (ATA) address for a wallet and token mint.

    ATA = PDA of [wallet, TOKEN_PROGRAM_ID, mint]
    """
    TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
    ASSOCIATED_TOKEN_PROGRAM_ID = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")

    wallet_pubkey = Pubkey.from_string(wallet)
    mint_pubkey = Pubkey.from_string(token_mint)

    # Derive ATA address
    seeds = [
        bytes(wallet_pubkey),
        bytes(TOKEN_PROGRAM_ID),
        bytes(mint_pubkey)
    ]

    ata, _ = Pubkey.find_program_address(seeds, ASSOCIATED_TOKEN_PROGRAM_ID)
    return str(ata)


async def fetch_token_balance(rpc_url: str, wallet: str) -> float:
    """
    Fetch the $FLIP token balance for a wallet.

    Returns balance in token units (not raw lamports).
    """
    if not TOKEN_ENABLED or TOKEN_MINT == "PLACEHOLDER_CONTRACT_ADDRESS":
        logger.debug(f"Token not enabled, returning 0 balance for {wallet[:8]}...")
        return 0.0

    try:
        # Get the Associated Token Account address
        ata_address = get_associated_token_address(wallet, TOKEN_MINT)

        async with AsyncClient(rpc_url) as client:
            # Fetch token account info
            response = await client.get_token_account_balance(Pubkey.from_string(ata_address))

            if response.value is None:
                # No token account = 0 balance
                return 0.0

            # Parse balance (already in UI amount with decimals)
            balance = float(response.value.ui_amount or 0)
            logger.debug(f"Token balance for {wallet[:8]}...: {balance:,.0f} {TOKEN_MINT[:8]}...")
            return balance

    except Exception as e:
        # Account doesn't exist or other error = 0 balance
        logger.debug(f"Error fetching token balance for {wallet[:8]}...: {e}")
        return 0.0


async def get_holder_status(rpc_url: str, wallet: str, force_refresh: bool = False) -> dict:
    """
    Get the token holder status for a wallet.

    Returns cached result if available and fresh, otherwise fetches new balance.

    Returns:
        {
            "wallet": str,
            "balance": float,
            "tier": str,
            "tier_info": dict,
            "next_tier": dict | None,
            "cached": bool,
            "cache_expires": datetime | None
        }
    """
    global _balance_cache

    # Check cache first
    if not force_refresh and wallet in _balance_cache:
        balance, tier, cached_at = _balance_cache[wallet]
        cache_age = (datetime.utcnow() - cached_at).total_seconds()

        if cache_age < BALANCE_CACHE_TTL:
            # Cache is still fresh
            return {
                "wallet": wallet,
                "balance": balance,
                "tier": tier,
                "tier_info": get_tier_info(tier),
                "next_tier": get_next_tier(tier),
                "cached": True,
                "cache_expires": cached_at + timedelta(seconds=BALANCE_CACHE_TTL)
            }

    # Fetch fresh balance
    balance = await fetch_token_balance(rpc_url, wallet)
    tier = get_tier_for_balance(balance)

    # Update cache
    now = datetime.utcnow()
    _balance_cache[wallet] = (balance, tier, now)

    return {
        "wallet": wallet,
        "balance": balance,
        "tier": tier,
        "tier_info": get_tier_info(tier),
        "next_tier": get_next_tier(tier),
        "cached": False,
        "cache_expires": now + timedelta(seconds=BALANCE_CACHE_TTL)
    }


def get_cached_tier(wallet: str) -> str:
    """
    Get the cached tier for a wallet (synchronous, for quick lookups).

    Returns "Normie" if not cached.
    """
    if wallet in _balance_cache:
        _, tier, cached_at = _balance_cache[wallet]
        cache_age = (datetime.utcnow() - cached_at).total_seconds()
        if cache_age < BALANCE_CACHE_TTL:
            return tier
    return "Normie"


def clear_cache(wallet: Optional[str] = None):
    """Clear the balance cache for a wallet or all wallets."""
    global _balance_cache
    if wallet:
        _balance_cache.pop(wallet, None)
    else:
        _balance_cache.clear()


def get_cache_stats() -> dict:
    """Get cache statistics."""
    now = datetime.utcnow()
    valid_entries = sum(
        1 for _, (_, _, cached_at) in _balance_cache.items()
        if (now - cached_at).total_seconds() < BALANCE_CACHE_TTL
    )
    return {
        "total_entries": len(_balance_cache),
        "valid_entries": valid_entries,
        "cache_ttl": BALANCE_CACHE_TTL
    }


# =============================================================================
# UTILITY FUNCTIONS FOR API
# =============================================================================

async def check_and_update_user_tier(rpc_url: str, wallet: str, db, user_id: int) -> dict:
    """
    Check token balance and update user's tier in database.

    Call this before processing bets to ensure accurate fee calculation.
    """
    status = await get_holder_status(rpc_url, wallet)

    # Update user in database if tier changed
    user = db.get_user(user_id)
    if user:
        old_tier = getattr(user, 'token_tier', 'Normie')
        if old_tier != status['tier']:
            user.token_tier = status['tier']
            user.token_balance = status['balance']
            user.token_balance_checked_at = datetime.utcnow()
            db.save_user(user)
            logger.info(f"User {user_id} token tier updated: {old_tier} -> {status['tier']}")

    return status


def calculate_fee_with_holder_discount(amount: float, wallet: str) -> Tuple[float, float, str]:
    """
    Calculate fee with holder discount.

    Returns: (fee_amount, effective_rate, tier_name)
    """
    from token_config import BASE_FEE_RATE, calculate_effective_fee

    tier = get_cached_tier(wallet)
    fee = calculate_effective_fee(amount, tier)
    tier_info = get_tier_info(tier)

    return fee, tier_info['fee_rate'], tier
