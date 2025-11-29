"""
Security audit logging system.
Tracks all security-relevant events for forensics and monitoring.
"""
import logging
import sqlite3
from datetime import datetime
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of security events to audit."""
    # Authentication & Authorization
    USER_CREATED = "user_created"
    USER_LOGIN = "user_login"
    INVALID_WALLET = "invalid_wallet"

    # Transaction Security
    SIGNATURE_REUSE = "signature_reuse"
    INVALID_TRANSACTION = "invalid_transaction"
    SIGNATURE_VERIFIED = "signature_verified"

    # Rate Limiting
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_PATTERN = "suspicious_pattern"

    # Game Security
    GAME_CREATED = "game_created"
    GAME_COMPLETED = "game_completed"
    ESCROW_CREATED = "escrow_created"

    # Referrals & Tiers
    REFERRAL_USED = "referral_used"
    TIER_UPGRADED = "tier_upgraded"
    REFERRAL_COMMISSION = "referral_commission"

    # Admin Actions
    ADMIN_ACTION = "admin_action"
    PAYOUT_PROCESSED = "payout_processed"


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AuditLogger:
    """Audit logging system for security events."""

    def __init__(self, db_path: str = "coinflip.db"):
        self.db_path = db_path
        self._init_audit_table()

    def _init_audit_table(self):
        """Initialize audit log table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                user_id INTEGER,
                ip_address TEXT,
                user_agent TEXT,
                details TEXT,
                severity TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

        # Indexes for common queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_logs(severity)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_logs(event_type)")

        conn.commit()
        conn.close()

    def log(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity = AuditSeverity.INFO,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[str] = None,
    ):
        """Log a security event.

        Args:
            event_type: Type of event
            severity: Severity level
            user_id: User ID if applicable
            ip_address: IP address if applicable
            user_agent: User agent if applicable
            details: Additional details (JSON string or text)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO audit_logs (
                    event_type, user_id, ip_address, user_agent, details, severity, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                event_type.value,
                user_id,
                ip_address,
                user_agent,
                details,
                severity.value,
                datetime.utcnow().isoformat()
            ))

            conn.commit()
            conn.close()

            # Also log to application logger
            log_msg = f"[AUDIT] {event_type.value}"
            if user_id:
                log_msg += f" | user={user_id}"
            if ip_address:
                log_msg += f" | ip={ip_address}"
            if details:
                log_msg += f" | {details}"

            if severity == AuditSeverity.CRITICAL:
                logger.critical(log_msg)
            elif severity == AuditSeverity.WARNING:
                logger.warning(log_msg)
            else:
                logger.info(log_msg)

        except Exception as e:
            logger.error(f"Failed to write audit log: {e}", exc_info=True)

    def get_recent_events(
        self,
        limit: int = 100,
        severity: Optional[AuditSeverity] = None,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[int] = None
    ) -> list:
        """Get recent audit events.

        Args:
            limit: Maximum number of events to return
            severity: Filter by severity
            event_type: Filter by event type
            user_id: Filter by user ID

        Returns:
            List of audit log dictionaries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []

        if severity:
            query += " AND severity = ?"
            params.append(severity.value)

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.value)

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_security_summary(self, hours: int = 24) -> dict:
        """Get security summary for last N hours.

        Args:
            hours: Number of hours to analyze

        Returns:
            Dict with security metrics
        """
        from datetime import timedelta

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

        # Count by severity
        cursor.execute("""
            SELECT severity, COUNT(*) as count
            FROM audit_logs
            WHERE timestamp > ?
            GROUP BY severity
        """, (cutoff,))

        severity_counts = dict(cursor.fetchall())

        # Count by event type
        cursor.execute("""
            SELECT event_type, COUNT(*) as count
            FROM audit_logs
            WHERE timestamp > ?
            GROUP BY event_type
            ORDER BY count DESC
            LIMIT 10
        """, (cutoff,))

        event_counts = dict(cursor.fetchall())

        # Get suspicious IPs (multiple rate limit violations)
        cursor.execute("""
            SELECT ip_address, COUNT(*) as violations
            FROM audit_logs
            WHERE timestamp > ? AND event_type = 'rate_limit_exceeded'
            GROUP BY ip_address
            HAVING violations > 5
            ORDER BY violations DESC
        """, (cutoff,))

        suspicious_ips = cursor.fetchall()

        conn.close()

        return {
            "period_hours": hours,
            "severity_counts": severity_counts,
            "top_events": event_counts,
            "suspicious_ips": suspicious_ips,
            "total_critical": severity_counts.get("critical", 0),
            "total_warnings": severity_counts.get("warning", 0),
        }


# Global audit logger instance
audit_logger = AuditLogger()
