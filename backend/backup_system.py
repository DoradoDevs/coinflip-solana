"""
Automated database backup system with encryption and versioning.

SECURITY: Backups are encrypted to protect sensitive data (private keys).
"""
import os
import shutil
import gzip
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
import sqlite3
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# Backup configuration
BACKUP_DIR = os.getenv("BACKUP_DIR", "./backups")
DB_PATH = os.getenv("DB_PATH", "./coinflip.db")
MAX_BACKUPS = int(os.getenv("MAX_BACKUPS", "30"))  # Keep last 30 backups
BACKUP_INTERVAL_HOURS = int(os.getenv("BACKUP_INTERVAL_HOURS", "6"))  # Every 6 hours


class BackupSystem:
    """Automated backup system with encryption and versioning."""

    def __init__(self, db_path: str = DB_PATH, backup_dir: str = BACKUP_DIR):
        self.db_path = db_path
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Backup system initialized: {self.backup_dir}")

    def create_backup(self, compress: bool = True, encrypt: bool = True) -> str:
        """Create a new database backup.

        SECURITY: Backups are encrypted with the same key used for private keys.
        This prevents unauthorized access to user funds even if backups are stolen.

        Args:
            compress: Whether to compress the backup with gzip
            encrypt: Whether to encrypt the backup (RECOMMENDED)

        Returns:
            Path to the backup file
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_name = f"coinflip_backup_{timestamp}.db"

        if compress:
            backup_name += ".gz"

        if encrypt:
            backup_name += ".enc"

        backup_path = self.backup_dir / backup_name

        try:
            # Use SQLite's backup API for consistent snapshots
            source_conn = sqlite3.connect(self.db_path)

            # Backup to temp file first
            temp_path = backup_path.with_suffix("").with_suffix(".tmp")
            backup_conn = sqlite3.connect(str(temp_path))

            source_conn.backup(backup_conn)

            source_conn.close()
            backup_conn.close()

            current_path = temp_path

            # Compress if requested
            if compress:
                compressed_path = temp_path.with_suffix(".gz.tmp")

                with open(current_path, 'rb') as f_in:
                    with gzip.open(compressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)

                # Remove uncompressed file
                os.remove(current_path)
                current_path = compressed_path

            # Encrypt if requested (RECOMMENDED!)
            if encrypt:
                encrypted_path = self._encrypt_backup(current_path)

                # Remove unencrypted file
                os.remove(current_path)
                current_path = encrypted_path

            # Move to final destination
            shutil.move(str(current_path), str(backup_path))

            file_size = os.path.getsize(backup_path) / 1024  # KB
            logger.info(
                f"Backup created: {backup_name} ({file_size:.2f} KB) "
                f"[compressed: {compress}, encrypted: {encrypt}]"
            )

            # Create metadata file
            self._create_metadata(backup_path, compressed=compress, encrypted=encrypt)

            return str(backup_path)

        except Exception as e:
            logger.error(f"Backup failed: {e}", exc_info=True)

            # Cleanup temp files on failure
            for temp_file in self.backup_dir.glob("*.tmp"):
                try:
                    os.remove(temp_file)
                except:
                    pass

            raise

    def _encrypt_backup(self, backup_path: Path) -> Path:
        """Encrypt backup file.

        Uses same encryption key as database private keys (ENCRYPTION_KEY).

        Args:
            backup_path: Path to backup file to encrypt

        Returns:
            Path to encrypted backup file
        """
        encryption_key = os.getenv("ENCRYPTION_KEY")

        if not encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY not set! Cannot encrypt backup. "
                "Set ENCRYPTION_KEY environment variable."
            )

        # Convert encryption key to Fernet key (must be 32 url-safe base64-encoded bytes)
        # Since ENCRYPTION_KEY might be a password, derive a proper Fernet key
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
        import base64

        # Use fixed salt for backup encryption (not ideal but consistent)
        # In production, could store salt separately or use different approach
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'coinflip_backup_salt_v1',  # Fixed salt
            iterations=100000,
        )

        key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
        fernet = Fernet(key)

        # Read backup file
        with open(backup_path, 'rb') as f:
            data = f.read()

        # Encrypt
        encrypted_data = fernet.encrypt(data)

        # Write to new file
        encrypted_path = backup_path.with_suffix(backup_path.suffix + ".enc")

        with open(encrypted_path, 'wb') as f:
            f.write(encrypted_data)

        logger.info(f"Backup encrypted: {encrypted_path.name}")

        return encrypted_path

    def _decrypt_backup(self, encrypted_path: Path) -> bytes:
        """Decrypt backup file.

        Args:
            encrypted_path: Path to encrypted backup

        Returns:
            Decrypted data
        """
        encryption_key = os.getenv("ENCRYPTION_KEY")

        if not encryption_key:
            raise ValueError("ENCRYPTION_KEY not set! Cannot decrypt backup.")

        # Derive Fernet key (same process as encryption)
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
        import base64

        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'coinflip_backup_salt_v1',
            iterations=100000,
        )

        key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
        fernet = Fernet(key)

        # Read encrypted file
        with open(encrypted_path, 'rb') as f:
            encrypted_data = f.read()

        # Decrypt
        try:
            decrypted_data = fernet.decrypt(encrypted_data)
            return decrypted_data
        except Exception as e:
            raise ValueError(f"Failed to decrypt backup: {e}. Wrong encryption key?")

    def _create_metadata(self, backup_path: Path, compressed: bool = False, encrypted: bool = False):
        """Create metadata file for backup.

        Args:
            backup_path: Path to backup file
            compressed: Whether backup is compressed
            encrypted: Whether backup is encrypted
        """
        metadata_path = backup_path.with_suffix(".json")

        # Get database stats
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}
        for table in ["users", "games", "wagers", "transactions", "used_signatures", "audit_logs"]:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                stats[table] = 0

        conn.close()

        metadata = {
            "timestamp": datetime.utcnow().isoformat(),
            "backup_file": backup_path.name,
            "original_db": self.db_path,
            "file_size_bytes": os.path.getsize(backup_path),
            "compressed": compressed,
            "encrypted": encrypted,
            "table_counts": stats,
        }

        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Metadata created: {metadata_path.name}")

    def cleanup_old_backups(self, keep_count: int = MAX_BACKUPS):
        """Remove old backups, keeping only the most recent ones.

        Args:
            keep_count: Number of backups to keep
        """
        # Get all backup files
        backups = sorted(
            [f for f in self.backup_dir.glob("coinflip_backup_*.db*")],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )

        # Remove old backups
        removed_count = 0
        for backup in backups[keep_count:]:
            # Remove backup file
            backup.unlink()
            # Remove metadata if exists
            metadata_path = backup.with_suffix(".json")
            if metadata_path.exists():
                metadata_path.unlink()
            removed_count += 1
            logger.info(f"Removed old backup: {backup.name}")

        if removed_count > 0:
            logger.info(f"Cleanup complete: Removed {removed_count} old backups")

    def restore_backup(self, backup_path: str, target_path: Optional[str] = None):
        """Restore database from backup.

        Args:
            backup_path: Path to backup file
            target_path: Path to restore to (default: original db_path)
        """
        if target_path is None:
            target_path = self.db_path

        backup_path = Path(backup_path)

        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        try:
            # Decompress if needed
            if backup_path.suffix == ".gz":
                temp_path = backup_path.with_suffix("")
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(temp_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                restore_source = temp_path
            else:
                restore_source = backup_path

            # Copy to target
            shutil.copy2(restore_source, target_path)

            # Clean up temp file if created
            if backup_path.suffix == ".gz":
                os.remove(restore_source)

            logger.info(f"Database restored from backup: {backup_path.name} -> {target_path}")

        except Exception as e:
            logger.error(f"Restore failed: {e}", exc_info=True)
            raise

    def list_backups(self) -> List[dict]:
        """List all available backups with metadata.

        Returns:
            List of backup info dictionaries
        """
        backups = []

        for backup_file in sorted(self.backup_dir.glob("coinflip_backup_*.db*"), reverse=True):
            # Skip metadata files
            if backup_file.suffix == ".json":
                continue

            metadata_path = backup_file.with_suffix(".json")

            info = {
                "file": backup_file.name,
                "path": str(backup_file),
                "size_kb": os.path.getsize(backup_file) / 1024,
                "created": datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat(),
            }

            # Load metadata if available
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                    info["metadata"] = metadata

            backups.append(info)

        return backups

    def get_backup_status(self) -> dict:
        """Get backup system status.

        Returns:
            Dict with backup status info
        """
        backups = self.list_backups()

        latest_backup = backups[0] if backups else None
        oldest_backup = backups[-1] if backups else None

        total_size = sum(b["size_kb"] for b in backups)

        return {
            "backup_count": len(backups),
            "total_size_mb": total_size / 1024,
            "latest_backup": latest_backup,
            "oldest_backup": oldest_backup,
            "backup_dir": str(self.backup_dir),
            "max_backups": MAX_BACKUPS,
        }

    def verify_backup(self, backup_path: str) -> bool:
        """Verify backup integrity.

        Args:
            backup_path: Path to backup file

        Returns:
            True if backup is valid, False otherwise
        """
        backup_path = Path(backup_path)

        try:
            # Decompress if needed
            if backup_path.suffix == ".gz":
                temp_path = backup_path.with_suffix("")
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(temp_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                verify_source = temp_path
            else:
                verify_source = backup_path

            # Try to open as SQLite database
            conn = sqlite3.connect(str(verify_source))
            cursor = conn.cursor()

            # Check integrity
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]

            conn.close()

            # Clean up temp file
            if backup_path.suffix == ".gz":
                os.remove(verify_source)

            if result == "ok":
                logger.info(f"Backup verified OK: {backup_path.name}")
                return True
            else:
                logger.error(f"Backup integrity check failed: {result}")
                return False

        except Exception as e:
            logger.error(f"Backup verification failed: {e}", exc_info=True)
            return False


# Global backup system instance
backup_system = BackupSystem()


async def backup_loop():
    """Background task that creates backups periodically."""
    import asyncio

    logger.info(f"Backup loop started (interval: {BACKUP_INTERVAL_HOURS} hours)")

    while True:
        try:
            # Wait for interval
            await asyncio.sleep(BACKUP_INTERVAL_HOURS * 3600)

            # Create backup
            backup_system.create_backup(compress=True)

            # Cleanup old backups
            backup_system.cleanup_old_backups()

        except asyncio.CancelledError:
            logger.info("Backup loop cancelled")
            break
        except Exception as e:
            logger.error(f"Error in backup loop: {e}", exc_info=True)


if __name__ == "__main__":
    # Manual backup test
    logging.basicConfig(level=logging.INFO)

    print("Creating backup...")
    backup_path = backup_system.create_backup()
    print(f"Backup created: {backup_path}")

    print("\nBackup status:")
    status = backup_system.get_backup_status()
    print(json.dumps(status, indent=2))

    print("\nVerifying backup...")
    is_valid = backup_system.verify_backup(backup_path)
    print(f"Backup valid: {is_valid}")
