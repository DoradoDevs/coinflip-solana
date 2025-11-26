"""
Formatting utilities for display.
"""
from datetime import datetime
from typing import Optional


def format_sol(amount: float) -> str:
    """Format SOL amount for display."""
    if amount >= 1000:
        return f"{amount:,.2f}"
    elif amount >= 1:
        return f"{amount:.4f}"
    else:
        return f"{amount:.6f}"


def format_percentage(value: float) -> str:
    """Format percentage for display."""
    return f"{value * 100:.1f}%"


def format_timestamp(dt: Optional[datetime]) -> str:
    """Format timestamp for display."""
    if not dt:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def format_tx_link(signature: str, cluster: str = "mainnet") -> str:
    """Format Solana transaction explorer link."""
    base_url = "https://solscan.io/tx/"
    if cluster != "mainnet":
        base_url += f"?cluster={cluster}"
    return f"{base_url}{signature}"


def format_wallet_link(address: str, cluster: str = "mainnet") -> str:
    """Format Solana wallet explorer link."""
    base_url = "https://solscan.io/account/"
    if cluster != "mainnet":
        base_url += f"?cluster={cluster}"
    return f"{base_url}{address}"


def truncate_address(address: str, start: int = 4, end: int = 4) -> str:
    """Truncate wallet address for display."""
    if len(address) <= start + end:
        return address
    return f"{address[:start]}...{address[-end:]}"


def format_win_rate(games_played: int, games_won: int) -> str:
    """Format win rate percentage."""
    if games_played == 0:
        return "0.0%"
    win_rate = (games_won / games_played) * 100
    return f"{win_rate:.1f}%"
