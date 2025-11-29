"""
Admin tools for recovering user funds in emergency situations.

SECURITY: These tools require admin authorization and should only be used:
1. When a user reports lost access to funds
2. When a wager/game gets stuck in an error state
3. For manual intervention after thorough investigation

ALL RECOVERY OPERATIONS ARE LOGGED TO AUDIT SYSTEM.
"""
import logging
import asyncio
from typing import Optional, List, Dict
from datetime import datetime

from database import Database, User, Wager, Game
from game.solana_ops import transfer_sol, get_sol_balance
from utils.encryption import decrypt_secret
from security import audit_logger, AuditEventType, AuditSeverity

logger = logging.getLogger(__name__)


class RecoveryTools:
    """Admin tools for fund recovery."""

    def __init__(self, db: Database, encryption_key: str, rpc_url: str):
        self.db = db
        self.encryption_key = encryption_key
        self.rpc_url = rpc_url

    async def recover_escrow_funds(
        self,
        wager_id: str,
        recipient_wallet: str,
        admin_id: int,
        reason: str
    ) -> Dict[str, str]:
        """Recover funds from escrow wallets.

        Args:
            wager_id: Wager ID to recover funds from
            recipient_wallet: Where to send recovered funds
            admin_id: Admin user ID performing recovery
            reason: Reason for recovery (for audit log)

        Returns:
            Dict with transaction signatures
        """
        # Get wager
        wagers = self.db.get_open_wagers(limit=1000)
        wager = next((w for w in wagers if w.wager_id == wager_id), None)

        if not wager:
            # Check if it's a completed wager
            logger.error(f"Wager {wager_id} not found in open wagers")
            raise ValueError(f"Wager {wager_id} not found")

        transactions = {}

        # Log recovery attempt
        audit_logger.log(
            event_type=AuditEventType.ADMIN_ACTION,
            severity=AuditSeverity.CRITICAL,
            user_id=admin_id,
            details=f"FUND RECOVERY: Wager {wager_id} | Recipient: {recipient_wallet} | Reason: {reason}"
        )

        # Recover from creator escrow if exists
        if wager.creator_escrow_address and wager.creator_escrow_secret:
            try:
                escrow_secret = decrypt_secret(wager.creator_escrow_secret, self.encryption_key)
                balance = await get_sol_balance(self.rpc_url, wager.creator_escrow_address)

                if balance > 0.000001:  # Min dust threshold
                    tx_sig = await transfer_sol(
                        self.rpc_url,
                        escrow_secret,
                        recipient_wallet,
                        balance - 0.000005  # Leave dust for rent
                    )
                    transactions["creator_escrow"] = tx_sig
                    logger.info(f"Recovered {balance:.6f} SOL from creator escrow: {tx_sig}")
            except Exception as e:
                logger.error(f"Failed to recover from creator escrow: {e}", exc_info=True)
                transactions["creator_escrow_error"] = str(e)

        # Recover from acceptor escrow if exists
        if wager.acceptor_escrow_address and wager.acceptor_escrow_secret:
            try:
                escrow_secret = decrypt_secret(wager.acceptor_escrow_secret, self.encryption_key)
                balance = await get_sol_balance(self.rpc_url, wager.acceptor_escrow_address)

                if balance > 0.000001:
                    tx_sig = await transfer_sol(
                        self.rpc_url,
                        escrow_secret,
                        recipient_wallet,
                        balance - 0.000005
                    )
                    transactions["acceptor_escrow"] = tx_sig
                    logger.info(f"Recovered {balance:.6f} SOL from acceptor escrow: {tx_sig}")
            except Exception as e:
                logger.error(f"Failed to recover from acceptor escrow: {e}", exc_info=True)
                transactions["acceptor_escrow_error"] = str(e)

        # Log completion
        audit_logger.log(
            event_type=AuditEventType.ADMIN_ACTION,
            severity=AuditSeverity.CRITICAL,
            user_id=admin_id,
            details=f"RECOVERY COMPLETE: Wager {wager_id} | Transactions: {list(transactions.keys())}"
        )

        return transactions

    async def check_stuck_escrows(self) -> List[Dict]:
        """Find escrows with funds that may be stuck.

        Returns:
            List of potentially stuck escrow wallets
        """
        stuck_escrows = []

        # Get all open/accepting wagers
        wagers = self.db.get_open_wagers(limit=1000)

        for wager in wagers:
            # Check creator escrow
            if wager.creator_escrow_address and wager.creator_escrow_secret:
                try:
                    balance = await get_sol_balance(self.rpc_url, wager.creator_escrow_address)
                    if balance > 0:
                        stuck_escrows.append({
                            "wager_id": wager.wager_id,
                            "type": "creator_escrow",
                            "address": wager.creator_escrow_address,
                            "balance": balance,
                            "creator_id": wager.creator_id,
                            "status": wager.status,
                            "created_at": wager.created_at.isoformat(),
                        })
                except Exception as e:
                    logger.error(f"Error checking escrow {wager.creator_escrow_address}: {e}")

            # Check acceptor escrow
            if wager.acceptor_escrow_address and wager.acceptor_escrow_secret:
                try:
                    balance = await get_sol_balance(self.rpc_url, wager.acceptor_escrow_address)
                    if balance > 0:
                        stuck_escrows.append({
                            "wager_id": wager.wager_id,
                            "type": "acceptor_escrow",
                            "address": wager.acceptor_escrow_address,
                            "balance": balance,
                            "acceptor_id": wager.acceptor_id,
                            "status": wager.status,
                            "created_at": wager.created_at.isoformat(),
                        })
                except Exception as e:
                    logger.error(f"Error checking escrow {wager.acceptor_escrow_address}: {e}")

        return stuck_escrows

    async def recover_user_payout(
        self,
        user_id: int,
        amount: float,
        from_wallet_secret: str,
        admin_id: int,
        reason: str
    ) -> str:
        """Manually send payout to user.

        Args:
            user_id: User to send payout to
            amount: Amount in SOL
            from_wallet_secret: Secret key of wallet to send from (e.g., treasury)
            admin_id: Admin performing action
            reason: Reason for manual payout

        Returns:
            Transaction signature
        """
        user = self.db.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        if not user.payout_wallet:
            raise ValueError(f"User {user_id} has no payout wallet set")

        # Log action
        audit_logger.log(
            event_type=AuditEventType.ADMIN_ACTION,
            severity=AuditSeverity.CRITICAL,
            user_id=admin_id,
            details=f"MANUAL PAYOUT: {amount} SOL to user {user_id} ({user.payout_wallet}) | Reason: {reason}"
        )

        # Send payout
        tx_sig = await transfer_sol(
            self.rpc_url,
            from_wallet_secret,
            user.payout_wallet,
            amount
        )

        logger.info(f"Manual payout sent: {amount} SOL to user {user_id} (tx: {tx_sig})")

        # Log completion
        audit_logger.log(
            event_type=AuditEventType.PAYOUT_PROCESSED,
            severity=AuditSeverity.INFO,
            user_id=user_id,
            details=f"Manual payout: {amount} SOL | TX: {tx_sig}"
        )

        return tx_sig

    def export_user_data(self, user_id: int) -> Dict:
        """Export all user data for support/recovery.

        Args:
            user_id: User ID to export

        Returns:
            Dict with all user data
        """
        user = self.db.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Get games
        games = self.db.get_user_games(user_id, limit=1000)

        # Get wagers
        wagers = self.db.get_user_wagers(user_id)

        # Get transactions
        transactions = self.db.get_user_transactions(user_id, limit=1000)

        return {
            "user": {
                "user_id": user.user_id,
                "platform": user.platform,
                "wallet_address": user.wallet_address,
                "payout_wallet": user.payout_wallet,
                "tier": user.tier,
                "tier_fee_rate": user.tier_fee_rate,
                "games_played": user.games_played,
                "games_won": user.games_won,
                "total_wagered": user.total_wagered,
                "total_won": user.total_won,
                "total_lost": user.total_lost,
                "referral_code": user.referral_code,
                "referred_by": user.referred_by,
                "referral_earnings": user.referral_earnings,
                "pending_referral_balance": user.pending_referral_balance,
                "total_referrals": user.total_referrals,
                "created_at": user.created_at.isoformat(),
            },
            "games": [
                {
                    "game_id": g.game_id,
                    "game_type": g.game_type.value,
                    "amount": g.amount,
                    "status": g.status.value,
                    "result": g.result.value if g.result else None,
                    "winner_id": g.winner_id,
                    "created_at": g.created_at.isoformat(),
                }
                for g in games
            ],
            "wagers": [
                {
                    "wager_id": w.wager_id,
                    "amount": w.amount,
                    "status": w.status,
                    "creator_side": w.creator_side.value,
                    "created_at": w.created_at.isoformat(),
                }
                for w in wagers
            ],
            "transactions": [
                {
                    "tx_id": t.tx_id,
                    "tx_type": t.tx_type,
                    "amount": t.amount,
                    "signature": t.signature,
                    "timestamp": t.timestamp.isoformat(),
                }
                for t in transactions
            ],
        }

    async def verify_all_escrows(self) -> Dict:
        """Verify all escrow wallets have keys stored.

        Returns:
            Dict with verification results
        """
        results = {
            "total_wagers": 0,
            "verified": 0,
            "missing_keys": [],
            "errors": [],
        }

        wagers = self.db.get_open_wagers(limit=10000)
        results["total_wagers"] = len(wagers)

        for wager in wagers:
            try:
                # Check creator escrow
                if wager.creator_escrow_address:
                    if not wager.creator_escrow_secret:
                        results["missing_keys"].append({
                            "wager_id": wager.wager_id,
                            "escrow": "creator",
                            "address": wager.creator_escrow_address,
                        })
                    else:
                        # Try to decrypt
                        try:
                            decrypt_secret(wager.creator_escrow_secret, self.encryption_key)
                            results["verified"] += 1
                        except Exception as e:
                            results["errors"].append({
                                "wager_id": wager.wager_id,
                                "escrow": "creator",
                                "error": str(e),
                            })

                # Check acceptor escrow
                if wager.acceptor_escrow_address:
                    if not wager.acceptor_escrow_secret:
                        results["missing_keys"].append({
                            "wager_id": wager.wager_id,
                            "escrow": "acceptor",
                            "address": wager.acceptor_escrow_address,
                        })
                    else:
                        try:
                            decrypt_secret(wager.acceptor_escrow_secret, self.encryption_key)
                            results["verified"] += 1
                        except Exception as e:
                            results["errors"].append({
                                "wager_id": wager.wager_id,
                                "escrow": "acceptor",
                                "error": str(e),
                            })

            except Exception as e:
                logger.error(f"Error verifying wager {wager.wager_id}: {e}", exc_info=True)

        return results


if __name__ == "__main__":
    # Example usage
    import os
    from dotenv import load_dotenv

    load_dotenv()

    logging.basicConfig(level=logging.INFO)

    db = Database()
    encryption_key = os.getenv("ENCRYPTION_KEY")
    rpc_url = os.getenv("RPC_URL")

    recovery = RecoveryTools(db, encryption_key, rpc_url)

    # Verify all escrows
    async def main():
        results = await recovery.verify_all_escrows()
        print("\nEscrow Verification Results:")
        print(f"Total Wagers: {results['total_wagers']}")
        print(f"Verified Escrows: {results['verified']}")
        print(f"Missing Keys: {len(results['missing_keys'])}")
        print(f"Errors: {len(results['errors'])}")

        if results['missing_keys']:
            print("\n⚠️ MISSING KEYS:")
            for missing in results['missing_keys']:
                print(f"  - Wager {missing['wager_id']} ({missing['escrow']}): {missing['address']}")

    asyncio.run(main())
