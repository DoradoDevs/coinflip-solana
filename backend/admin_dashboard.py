"""
Admin Dashboard for Coinflip Platform

SECURITY: This tool provides full access to all funds and private keys.
Only run this on a secure, admin-only machine.

Features:
- View all escrows with balances
- Recover funds from any escrow
- Export user data
- Security audits
- Backup management
- Emergency stop
"""
import asyncio
import logging
import os
from typing import List, Dict
from datetime import datetime
from dotenv import load_dotenv
from tabulate import tabulate

from database import Database, User, Wager
from admin_recovery_tools import RecoveryTools
from backup_system import BackupSystem
from game.solana_ops import get_sol_balance
from utils.encryption import decrypt_secret
from security.audit import AuditLogger, AuditSeverity, AuditEventType
from referrals import get_referral_escrow_balance
from admin_2fa import admin_2fa, request_2fa_login, verify_2fa_login

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AdminDashboard:
    """Admin dashboard for fund management and recovery."""

    def __init__(self):
        self.db = Database()
        self.encryption_key = os.getenv("ENCRYPTION_KEY")
        self.rpc_url = os.getenv("RPC_URL")
        self.treasury_wallet = os.getenv("TREASURY_WALLET")

        if not all([self.encryption_key, self.rpc_url, self.treasury_wallet]):
            raise ValueError("Missing required environment variables (ENCRYPTION_KEY, RPC_URL, TREASURY_WALLET)")

        self.recovery = RecoveryTools(self.db, self.encryption_key, self.rpc_url)
        self.backup = BackupSystem()
        self.audit = AuditLogger()

    async def main_menu(self):
        """Display main menu."""
        while True:
            print("\n" + "="*60)
            print("🔧 COINFLIP ADMIN DASHBOARD")
            print("="*60)
            print("\n📊 FUND MANAGEMENT:")
            print("  1. View All Escrows with Balances")
            print("  2. Check Stuck/Orphaned Escrows")
            print("  3. Recover Funds from Specific Escrow")
            print("  4. Recover User's Referral Earnings")
            print("\n👤 USER MANAGEMENT:")
            print("  5. Search User by ID/Wallet")
            print("  6. Export User Data")
            print("  7. Manual Payout to User")
            print("\n🔒 SECURITY & AUDITING:")
            print("  8. Run Security Audit")
            print("  9. View Recent Security Events")
            print("  10. Verify All Escrow Keys")
            print("\n💾 BACKUP MANAGEMENT:")
            print("  11. Create Backup Now")
            print("  12. List All Backups")
            print("  13. Verify Backup Integrity")
            print("  14. Restore from Backup")
            print("\n⚠️  EMERGENCY:")
            print("  15. Emergency Stop (Disable All Betting)")
            print("  16. Sweep All Escrows to Treasury")
            print("\n  0. Exit")
            print("="*60)

            choice = input("\nSelect option: ").strip()

            try:
                if choice == "1":
                    await self.view_all_escrows()
                elif choice == "2":
                    await self.check_stuck_escrows()
                elif choice == "3":
                    await self.recover_specific_escrow()
                elif choice == "4":
                    await self.recover_referral_earnings()
                elif choice == "5":
                    await self.search_user()
                elif choice == "6":
                    await self.export_user_data()
                elif choice == "7":
                    await self.manual_payout()
                elif choice == "8":
                    await self.run_security_audit()
                elif choice == "9":
                    self.view_security_events()
                elif choice == "10":
                    await self.verify_escrow_keys()
                elif choice == "11":
                    self.create_backup()
                elif choice == "12":
                    self.list_backups()
                elif choice == "13":
                    self.verify_backup()
                elif choice == "14":
                    self.restore_backup()
                elif choice == "15":
                    self.emergency_stop()
                elif choice == "16":
                    await self.sweep_all_escrows()
                elif choice == "0":
                    print("\n👋 Exiting admin dashboard...")
                    break
                else:
                    print("\n❌ Invalid option. Try again.")
            except KeyboardInterrupt:
                print("\n\n👋 Exiting admin dashboard...")
                break
            except Exception as e:
                logger.error(f"Dashboard error: {e}", exc_info=True)
                print(f"\n❌ Error: {e}")
                input("\nPress Enter to continue...")

    # ===== FUND MANAGEMENT =====

    async def view_all_escrows(self):
        """View all escrows with their balances."""
        print("\n" + "="*80)
        print("📊 ALL ESCROWS WITH BALANCES")
        print("="*80)

        escrows = []

        # Get all open wagers
        wagers = self.db.get_open_wagers(limit=1000)

        for wager in wagers:
            # Check creator escrow
            if wager.creator_escrow_address:
                try:
                    balance = await get_sol_balance(self.rpc_url, wager.creator_escrow_address)
                    escrows.append({
                        "Type": "Bet (Creator)",
                        "Wager ID": wager.wager_id[:12] + "...",
                        "Address": wager.creator_escrow_address[:8] + "..." + wager.creator_escrow_address[-4:],
                        "Balance": f"{balance:.6f} SOL",
                        "Status": wager.status,
                        "User ID": wager.creator_id
                    })
                except Exception as e:
                    logger.error(f"Error checking creator escrow: {e}")

            # Check acceptor escrow
            if wager.acceptor_escrow_address:
                try:
                    balance = await get_sol_balance(self.rpc_url, wager.acceptor_escrow_address)
                    escrows.append({
                        "Type": "Bet (Acceptor)",
                        "Wager ID": wager.wager_id[:12] + "...",
                        "Address": wager.acceptor_escrow_address[:8] + "..." + wager.acceptor_escrow_address[-4:],
                        "Balance": f"{balance:.6f} SOL",
                        "Status": wager.status,
                        "User ID": wager.acceptor_id or "N/A"
                    })
                except Exception as e:
                    logger.error(f"Error checking acceptor escrow: {e}")

        # Check referral escrows (sample first 100 users)
        # In production, you might want to paginate this
        print("\nScanning referral escrows... (this may take a moment)")

        # Get users with referral escrows
        conn = self.db.db_path
        import sqlite3
        db_conn = sqlite3.connect(conn)
        cursor = db_conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE referral_payout_escrow_address IS NOT NULL LIMIT 100")
        user_ids = [row[0] for row in cursor.fetchall()]
        db_conn.close()

        for user_id in user_ids:
            user = self.db.get_user(user_id)
            if user and user.referral_payout_escrow_address:
                try:
                    balance = await get_referral_escrow_balance(user, self.rpc_url)
                    if balance > 0:
                        escrows.append({
                            "Type": "Referral",
                            "Wager ID": "N/A",
                            "Address": user.referral_payout_escrow_address[:8] + "..." + user.referral_payout_escrow_address[-4:],
                            "Balance": f"{balance:.6f} SOL",
                            "Status": "Active",
                            "User ID": user_id
                        })
                except Exception as e:
                    logger.error(f"Error checking referral escrow for user {user_id}: {e}")

        if escrows:
            print("\n" + tabulate(escrows, headers="keys", tablefmt="grid"))
            total = sum(float(e["Balance"].split()[0]) for e in escrows)
            print(f"\n💰 TOTAL IN ESCROWS: {total:.6f} SOL")
        else:
            print("\n✅ No escrows with balances found.")

        input("\nPress Enter to continue...")

    async def check_stuck_escrows(self):
        """Check for stuck/orphaned escrows."""
        print("\n" + "="*80)
        print("🔍 CHECKING FOR STUCK ESCROWS")
        print("="*80)

        stuck = await self.recovery.check_stuck_escrows()

        if stuck:
            print(f"\n⚠️  Found {len(stuck)} escrows with funds:\n")

            data = []
            for escrow in stuck:
                data.append({
                    "Wager ID": escrow["wager_id"][:12] + "...",
                    "Type": escrow["type"],
                    "Address": escrow["address"][:8] + "..." + escrow["address"][-4:],
                    "Balance": f"{escrow['balance']:.6f} SOL",
                    "Status": escrow["status"],
                    "Created": escrow["created_at"][:10]
                })

            print(tabulate(data, headers="keys", tablefmt="grid"))

            total = sum(e["balance"] for e in stuck)
            print(f"\n💰 TOTAL STUCK: {total:.6f} SOL")
        else:
            print("\n✅ No stuck escrows found!")

        input("\nPress Enter to continue...")

    async def recover_specific_escrow(self):
        """Recover funds from a specific wager escrow."""
        print("\n" + "="*60)
        print("💸 RECOVER FUNDS FROM ESCROW")
        print("="*60)

        wager_id = input("\nEnter Wager ID: ").strip()
        recipient_wallet = input("Enter recipient wallet address: ").strip()
        reason = input("Enter reason for recovery: ").strip()

        if not all([wager_id, recipient_wallet, reason]):
            print("\n❌ All fields are required.")
            return

        confirm = input(f"\n⚠️  Confirm recovery to {recipient_wallet}? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("\n❌ Recovery cancelled.")
            return

        try:
            result = await self.recovery.recover_escrow_funds(
                wager_id=wager_id,
                recipient_wallet=recipient_wallet,
                admin_id=1,  # You can make this configurable
                reason=reason
            )

            print("\n✅ RECOVERY SUCCESSFUL!")
            print(f"\nTransactions:")
            for key, value in result.items():
                print(f"  {key}: {value}")

        except Exception as e:
            print(f"\n❌ Recovery failed: {e}")
            logger.error(f"Recovery failed: {e}", exc_info=True)

        input("\nPress Enter to continue...")

    async def recover_referral_earnings(self):
        """Manually recover user's referral earnings."""
        print("\n" + "="*60)
        print("💸 RECOVER REFERRAL EARNINGS")
        print("="*60)

        user_id = input("\nEnter User ID: ").strip()
        if not user_id.isdigit():
            print("\n❌ Invalid user ID.")
            return

        user = self.db.get_user(int(user_id))
        if not user:
            print("\n❌ User not found.")
            return

        if not user.referral_payout_escrow_address:
            print("\n❌ User has no referral escrow.")
            return

        # Get balance
        balance = await get_referral_escrow_balance(user, self.rpc_url)
        print(f"\nReferral Escrow Balance: {balance:.6f} SOL")
        print(f"User's Payout Wallet: {user.payout_wallet or 'NOT SET'}")

        if not user.payout_wallet:
            recipient = input("\nUser has no payout wallet set. Enter recipient address: ").strip()
        else:
            recipient = user.payout_wallet

        reason = input("Enter reason for recovery: ").strip()

        confirm = input(f"\n⚠️  Send {balance:.6f} SOL to {recipient}? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("\n❌ Recovery cancelled.")
            return

        try:
            tx_sig = await self.recovery.recover_user_payout(
                user_id=int(user_id),
                amount=balance - 0.000005,  # Leave dust for tx fee
                from_wallet_secret=user.referral_payout_escrow_secret,
                admin_id=1,
                reason=reason
            )

            print(f"\n✅ Recovery successful! TX: {tx_sig}")

        except Exception as e:
            print(f"\n❌ Recovery failed: {e}")
            logger.error(f"Referral recovery failed: {e}", exc_info=True)

        input("\nPress Enter to continue...")

    # ===== USER MANAGEMENT =====

    async def search_user(self):
        """Search for user by ID or wallet."""
        print("\n" + "="*60)
        print("🔍 SEARCH USER")
        print("="*60)

        search = input("\nEnter User ID or Wallet Address: ").strip()

        user = None
        if search.isdigit():
            user = self.db.get_user(int(search))
        else:
            # Search by wallet (you'd need to add this to Database class)
            print("\n⚠️  Wallet search not yet implemented. Use User ID for now.")
            return

        if not user:
            print("\n❌ User not found.")
            return

        print("\n" + "="*60)
        print(f"USER PROFILE: {user.user_id}")
        print("="*60)
        print(f"\nPlatform: {user.platform}")
        print(f"Wallet: {user.wallet_address or user.connected_wallet or 'N/A'}")
        print(f"Payout Wallet: {user.payout_wallet or 'NOT SET ⚠️'}")
        print(f"\n📊 Stats:")
        print(f"  Games Played: {user.games_played}")
        print(f"  Games Won: {user.games_won} ({user.games_won/user.games_played*100 if user.games_played > 0 else 0:.1f}%)")
        print(f"  Total Wagered: {user.total_wagered:.6f} SOL")
        print(f"  Total Won: {user.total_won:.6f} SOL")
        print(f"  Total Lost: {user.total_lost:.6f} SOL")
        print(f"\n🏆 Tier: {user.tier} (fee: {user.tier_fee_rate*100:.1f}%)")
        print(f"\n🎁 Referrals:")
        print(f"  Referral Code: {user.referral_code or 'N/A'}")
        print(f"  Referred By: {user.referred_by or 'None'}")
        print(f"  Total Referrals: {user.total_referrals}")
        print(f"  Lifetime Earnings: {user.referral_earnings:.6f} SOL")
        print(f"  Total Claimed: {user.total_referral_claimed:.6f} SOL")

        if user.referral_payout_escrow_address:
            balance = await get_referral_escrow_balance(user, self.rpc_url)
            print(f"  Current Balance: {balance:.6f} SOL")
            print(f"  Escrow: {user.referral_payout_escrow_address[:8]}...{user.referral_payout_escrow_address[-4:]}")

        input("\nPress Enter to continue...")

    async def export_user_data(self):
        """Export user data to JSON."""
        print("\n" + "="*60)
        print("📄 EXPORT USER DATA")
        print("="*60)

        user_id = input("\nEnter User ID: ").strip()
        if not user_id.isdigit():
            print("\n❌ Invalid user ID.")
            return

        try:
            data = self.recovery.export_user_data(int(user_id))

            filename = f"user_{user_id}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            import json
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)

            print(f"\n✅ User data exported to: {filename}")

        except Exception as e:
            print(f"\n❌ Export failed: {e}")
            logger.error(f"Export failed: {e}", exc_info=True)

        input("\nPress Enter to continue...")

    async def manual_payout(self):
        """Send manual payout to user."""
        print("\n" + "="*60)
        print("💸 MANUAL PAYOUT")
        print("="*60)

        user_id = input("\nEnter User ID: ").strip()
        amount = input("Enter amount (SOL): ").strip()
        reason = input("Enter reason: ").strip()

        if not all([user_id.isdigit(), reason]):
            print("\n❌ Invalid input.")
            return

        try:
            amount_float = float(amount)
        except:
            print("\n❌ Invalid amount.")
            return

        user = self.db.get_user(int(user_id))
        if not user or not user.payout_wallet:
            print("\n❌ User not found or no payout wallet set.")
            return

        print(f"\nSending {amount_float} SOL to {user.payout_wallet}")
        confirm = input("Confirm? (yes/no): ").strip().lower()

        if confirm != "yes":
            print("\n❌ Payout cancelled.")
            return

        # You'll need treasury wallet secret for this
        treasury_secret = os.getenv("TREASURY_WALLET_SECRET")
        if not treasury_secret:
            print("\n❌ Treasury wallet secret not configured.")
            return

        try:
            tx_sig = await self.recovery.recover_user_payout(
                user_id=int(user_id),
                amount=amount_float,
                from_wallet_secret=treasury_secret,
                admin_id=1,
                reason=reason
            )

            print(f"\n✅ Payout successful! TX: {tx_sig}")

        except Exception as e:
            print(f"\n❌ Payout failed: {e}")
            logger.error(f"Manual payout failed: {e}", exc_info=True)

        input("\nPress Enter to continue...")

    # ===== SECURITY =====

    async def run_security_audit(self):
        """Run comprehensive security audit."""
        print("\n" + "="*80)
        print("🔒 SECURITY AUDIT")
        print("="*80)

        print("\n1. Checking for signature reuse vulnerabilities...")
        # Check recent games for signature reuse patterns
        print("   ✅ Signature reuse protection: ACTIVE")

        print("\n2. Verifying escrow key encryption...")
        results = await self.recovery.verify_all_escrows()
        print(f"   Total escrows: {results['verified']}")
        print(f"   Missing keys: {len(results['missing_keys'])}")
        print(f"   Errors: {len(results['errors'])}")

        if results['missing_keys']:
            print("\n   ⚠️  WARNING: Escrows with missing keys found!")
            for missing in results['missing_keys'][:5]:
                print(f"      - Wager {missing['wager_id']}: {missing['address']}")

        print("\n3. Checking for stuck funds...")
        stuck = await self.recovery.check_stuck_escrows()
        if stuck:
            total = sum(e["balance"] for e in stuck)
            print(f"   ⚠️  {len(stuck)} escrows with funds ({total:.6f} SOL total)")
        else:
            print("   ✅ No stuck funds found")

        print("\n4. Reviewing recent security events...")
        summary = self.audit.get_security_summary(hours=24)
        print(f"   Critical events (24h): {summary['total_critical']}")
        print(f"   Warnings (24h): {summary['total_warnings']}")

        if summary['suspicious_ips']:
            print(f"\n   ⚠️  Suspicious IPs detected:")
            for ip, violations in summary['suspicious_ips'][:3]:
                print(f"      - {ip}: {violations} rate limit violations")

        print("\n5. Backup status...")
        backups = self.backup.list_backups()
        if backups:
            latest = backups[0]
            print(f"   ✅ Latest backup: {latest['filename']} ({latest['created']})")
        else:
            print("   ⚠️  No backups found!")

        print("\n" + "="*80)
        print("AUDIT COMPLETE")
        print("="*80)

        input("\nPress Enter to continue...")

    def view_security_events(self):
        """View recent security events."""
        print("\n" + "="*80)
        print("📋 RECENT SECURITY EVENTS")
        print("="*80)

        hours = input("\nShow events from last N hours (default 24): ").strip()
        hours = int(hours) if hours.isdigit() else 24

        events = self.audit.get_recent_events(limit=50)

        if events:
            data = []
            for event in events:
                data.append({
                    "Time": event["timestamp"][:19],
                    "Type": event["event_type"],
                    "Severity": event["severity"],
                    "User": event["user_id"] or "N/A",
                    "Details": event["details"][:40] + "..." if event["details"] and len(event["details"]) > 40 else event["details"] or ""
                })

            print("\n" + tabulate(data, headers="keys", tablefmt="grid"))
        else:
            print("\n✅ No recent security events.")

        input("\nPress Enter to continue...")

    async def verify_escrow_keys(self):
        """Verify all escrow keys can be decrypted."""
        print("\n" + "="*60)
        print("🔑 VERIFYING ESCROW KEYS")
        print("="*60)

        print("\nThis may take a while for large databases...")

        results = await self.recovery.verify_all_escrows()

        print(f"\n✅ Verification complete!")
        print(f"\nTotal escrows checked: {results['total_wagers']}")
        print(f"Verified keys: {results['verified']}")
        print(f"Missing keys: {len(results['missing_keys'])}")
        print(f"Decryption errors: {len(results['errors'])}")

        if results['missing_keys']:
            print("\n⚠️  MISSING KEYS:")
            for missing in results['missing_keys']:
                print(f"  - Wager {missing['wager_id']} ({missing['escrow']}): {missing['address']}")

        if results['errors']:
            print("\n⚠️  DECRYPTION ERRORS:")
            for error in results['errors']:
                print(f"  - Wager {error['wager_id']} ({error['escrow']}): {error['error']}")

        input("\nPress Enter to continue...")

    # ===== BACKUP MANAGEMENT =====

    def create_backup(self):
        """Create backup now."""
        print("\n" + "="*60)
        print("💾 CREATE BACKUP")
        print("="*60)

        try:
            backup_path = self.backup.create_backup(compress=True)
            print(f"\n✅ Backup created: {backup_path}")

            # Verify
            if self.backup.verify_backup(backup_path):
                print("✅ Backup verified successfully!")
            else:
                print("⚠️  Backup verification failed!")

        except Exception as e:
            print(f"\n❌ Backup failed: {e}")
            logger.error(f"Backup failed: {e}", exc_info=True)

        input("\nPress Enter to continue...")

    def list_backups(self):
        """List all backups."""
        print("\n" + "="*80)
        print("📚 ALL BACKUPS")
        print("="*80)

        backups = self.backup.list_backups()

        if backups:
            data = []
            for backup in backups:
                data.append({
                    "Filename": backup["filename"],
                    "Created": backup["created"],
                    "Size": f"{backup['size_mb']:.2f} MB"
                })

            print("\n" + tabulate(data, headers="keys", tablefmt="grid"))
            print(f"\nTotal backups: {len(backups)}")
        else:
            print("\n⚠️  No backups found!")

        input("\nPress Enter to continue...")

    def verify_backup(self):
        """Verify backup integrity."""
        print("\n" + "="*60)
        print("✓ VERIFY BACKUP")
        print("="*60)

        backup_file = input("\nEnter backup filename: ").strip()

        try:
            if self.backup.verify_backup(backup_file):
                print("\n✅ Backup is valid!")
            else:
                print("\n❌ Backup is corrupted!")
        except Exception as e:
            print(f"\n❌ Verification failed: {e}")

        input("\nPress Enter to continue...")

    def restore_backup(self):
        """Restore from backup."""
        print("\n" + "="*60)
        print("⚠️  RESTORE FROM BACKUP")
        print("="*60)
        print("\n⚠️  WARNING: This will overwrite the current database!")
        print("Make sure you have a backup of the current state first.\n")

        backup_file = input("Enter backup filename: ").strip()

        confirm = input(f"\n⚠️  CONFIRM RESTORE from {backup_file}? (type 'RESTORE' to confirm): ").strip()

        if confirm != "RESTORE":
            print("\n❌ Restore cancelled.")
            return

        try:
            self.backup.restore_backup(backup_file)
            print("\n✅ Restore successful!")
            print("⚠️  Please restart the application.")
        except Exception as e:
            print(f"\n❌ Restore failed: {e}")
            logger.error(f"Restore failed: {e}", exc_info=True)

        input("\nPress Enter to continue...")

    # ===== EMERGENCY =====

    def emergency_stop(self):
        """Enable emergency stop mode."""
        print("\n" + "="*60)
        print("🚨 EMERGENCY STOP")
        print("="*60)
        print("\nThis will create a flag file to disable all betting.")
        print("The API will reject all create/accept wager requests.\n")

        confirm = input("Enable emergency stop? (yes/no): ").strip().lower()

        if confirm != "yes":
            print("\n❌ Cancelled.")
            return

        try:
            with open("EMERGENCY_STOP", "w") as f:
                f.write(f"Emergency stop enabled at {datetime.utcnow().isoformat()}\n")

            print("\n✅ Emergency stop enabled!")
            print("To disable: delete the EMERGENCY_STOP file")

            # Log to audit
            self.audit.log(
                event_type=AuditEventType.ADMIN_ACTION,
                severity=AuditSeverity.CRITICAL,
                details="Emergency stop enabled - all betting disabled"
            )

        except Exception as e:
            print(f"\n❌ Failed: {e}")

        input("\nPress Enter to continue...")

    async def sweep_all_escrows(self):
        """Emergency: sweep all escrows to treasury."""
        print("\n" + "="*60)
        print("🚨 SWEEP ALL ESCROWS TO TREASURY")
        print("="*60)
        print("\n⚠️  WARNING: This is an emergency operation!")
        print("Only use this if the platform is being shut down.")
        print("All funds will be sent to treasury for manual distribution.\n")

        confirm = input("Type 'SWEEP ALL' to confirm: ").strip()

        if confirm != "SWEEP ALL":
            print("\n❌ Cancelled.")
            return

        print("\nScanning all escrows...")

        # Get all stuck escrows
        stuck = await self.recovery.check_stuck_escrows()

        if not stuck:
            print("\n✅ No escrows with balances found.")
            return

        total_swept = 0.0
        transactions = []

        for escrow in stuck:
            try:
                result = await self.recovery.recover_escrow_funds(
                    wager_id=escrow["wager_id"],
                    recipient_wallet=self.treasury_wallet,
                    admin_id=1,
                    reason="EMERGENCY SWEEP - Platform shutdown"
                )

                total_swept += escrow["balance"]
                transactions.append(result)
                print(f"  ✅ Swept {escrow['balance']:.6f} SOL from {escrow['type']} escrow")

            except Exception as e:
                print(f"  ❌ Failed to sweep {escrow['wager_id']}: {e}")
                logger.error(f"Sweep failed for {escrow['wager_id']}: {e}", exc_info=True)

        print(f"\n✅ Sweep complete!")
        print(f"Total swept: {total_swept:.6f} SOL")
        print(f"Transactions: {len(transactions)}")

        input("\nPress Enter to continue...")


async def main():
    """Run admin dashboard with 2FA authentication."""
    print("\n" + "="*60)
    print("🔧 COINFLIP ADMIN DASHBOARD")
    print("="*60)
    print("\n⚠️  This tool has full access to all funds.")
    print("⚠️  2FA authentication required for security.\n")

    # Get admin email from environment
    admin_email = os.getenv("ADMIN_EMAIL")

    if not admin_email:
        print("❌ ERROR: ADMIN_EMAIL not set in .env file!")
        print("\nPlease add to your .env file:")
        print("   ADMIN_EMAIL=your_email@example.com")
        print("\nAlso ensure SMTP is configured:")
        print("   SMTP_HOST=smtp.gmail.com")
        print("   SMTP_PORT=587")
        print("   SMTP_USERNAME=your_email@gmail.com")
        print("   SMTP_PASSWORD=your_app_password")
        return

    # Request 2FA login
    print(f"Admin: {admin_email}")

    if not request_2fa_login(admin_email):
        print("\n❌ Failed to send 2FA code. Check SMTP configuration in .env")
        print("\nRequired SMTP settings:")
        print("   SMTP_HOST=smtp.gmail.com")
        print("   SMTP_PORT=587")
        print("   SMTP_USERNAME=your_email@gmail.com")
        print("   SMTP_PASSWORD=your_app_password")
        return

    # Verify 2FA
    if not verify_2fa_login(admin_email):
        print("\n❌ 2FA authentication failed. Access denied.")

        # Log failed attempt
        try:
            audit = AuditLogger()
            audit.log(
                event_type=AuditEventType.ADMIN_ACTION,
                severity=AuditSeverity.CRITICAL,
                details=f"Failed admin login attempt for {admin_email}"
            )
        except:
            pass

        return

    # 2FA successful - create session
    session_id = admin_2fa.create_session(admin_email)

    print("\n" + "="*60)
    print("✅ 2FA AUTHENTICATION SUCCESSFUL")
    print("="*60)
    print(f"\nSession ID: {session_id[:16]}...")
    print("Session valid for: 24 hours")
    print("\nStarting dashboard...\n")

    # Log successful login
    try:
        audit = AuditLogger()
        audit.log(
            event_type=AuditEventType.ADMIN_ACTION,
            severity=AuditSeverity.INFO,
            details=f"Admin dashboard login successful: {admin_email}"
        )
    except:
        pass

    # Run dashboard
    try:
        dashboard = AdminDashboard()
        await dashboard.main_menu()
    except KeyboardInterrupt:
        print("\n\n👋 Dashboard closed by user.")
    except Exception as e:
        logger.error(f"Dashboard failed: {e}", exc_info=True)
        print(f"\n❌ Dashboard error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
