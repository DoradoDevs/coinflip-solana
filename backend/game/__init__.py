"""Game logic module for Coinflip."""
from .coinflip import play_house_game, play_pvp_game, verify_game_result, flip_coin
from .solana_ops import (
    generate_wallet,
    get_sol_balance,
    transfer_sol,
    get_latest_blockhash,
    payout_winner,
    collect_fee
)

__all__ = [
    "play_house_game",
    "play_pvp_game",
    "verify_game_result",
    "flip_coin",
    "generate_wallet",
    "get_sol_balance",
    "transfer_sol",
    "get_latest_blockhash",
    "payout_winner",
    "collect_fee",
]
