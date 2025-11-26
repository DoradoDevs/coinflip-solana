"""Game logic module for Coinflip."""
from .coinflip import play_house_game, play_pvp_game, play_pvp_game_with_escrows, verify_game_result, flip_coin, TRANSACTION_FEE
from .solana_ops import (
    generate_wallet,
    get_sol_balance,
    transfer_sol,
    get_latest_blockhash,
    payout_winner,
    collect_fee,
    verify_deposit_transaction
)
from .escrow import (
    create_escrow_wallet,
    payout_from_escrow,
    collect_fees_from_escrow,
    refund_from_escrow,
    check_escrow_balance
)

__all__ = [
    "play_house_game",
    "play_pvp_game",
    "play_pvp_game_with_escrows",
    "verify_game_result",
    "flip_coin",
    "TRANSACTION_FEE",
    "generate_wallet",
    "get_sol_balance",
    "transfer_sol",
    "get_latest_blockhash",
    "payout_winner",
    "collect_fee",
    "verify_deposit_transaction",
    "create_escrow_wallet",
    "payout_from_escrow",
    "collect_fees_from_escrow",
    "refund_from_escrow",
    "check_escrow_balance",
]
