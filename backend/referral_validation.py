"""
Referral code validation with anti-abuse measures.

SECURITY: Prevents referral system exploitation through self-referrals,
circular referrals, and wallet-based abuse detection.
"""
import logging
from typing import Tuple
from database import Database, User

logger = logging.getLogger(__name__)


def validate_and_apply_referral_code(
    user: User,
    referral_code: str,
    db: Database
) -> Tuple[bool, str]:
    """Validate referral code and apply with security checks.

    SECURITY: Prevents:
    - Self-referral (same user_id)
    - Same wallet referral (detect alt accounts)
    - Circular referrals (A refers B, B refers A)
    - Referral chain abuse (multi-level alt farming)

    Args:
        user: User attempting to use referral code
        referral_code: Referral code to apply
        db: Database instance

    Returns:
        Tuple of (success: bool, message: str)
    """
    # Basic validation
    if not referral_code:
        return False, "Referral code is required"

    # User already used a referral code
    if user.referred_by:
        referrer = db.get_user(user.referred_by)
        if referrer:
            return False, f"You already used referral code: {referrer.referral_code}"
        else:
            # Orphaned referral reference
            return False, "You already used a referral code"

    # Find referrer by referral code
    referrer = get_user_by_referral_code(db, referral_code)

    if not referrer:
        return False, "Invalid referral code"

    # SECURITY CHECK 1: Prevent self-referral (same user_id)
    if referrer.user_id == user.user_id:
        logger.warning(f"Self-referral attempt blocked: user {user.user_id}")
        return False, "Cannot use your own referral code"

    # SECURITY CHECK 2: Prevent same wallet referral (detect alt accounts)
    if user.wallet_address and referrer.wallet_address:
        if user.wallet_address == referrer.wallet_address:
            logger.warning(
                f"Same wallet referral blocked: user {user.user_id}, "
                f"referrer {referrer.user_id}, wallet {user.wallet_address}"
            )
            return False, "Cannot use referral code from same wallet"

    if user.connected_wallet and referrer.connected_wallet:
        if user.connected_wallet == referrer.connected_wallet:
            logger.warning(
                f"Same connected wallet referral blocked: user {user.user_id}, "
                f"referrer {referrer.user_id}, wallet {user.connected_wallet}"
            )
            return False, "Cannot use referral code from same wallet"

    # SECURITY CHECK 3: Prevent circular referrals (A → B, B → A)
    if referrer.referred_by == user.user_id:
        logger.warning(
            f"Circular referral blocked: user {user.user_id} → "
            f"referrer {referrer.user_id} → user {user.user_id}"
        )
        return False, "Circular referral detected"

    # SECURITY CHECK 4: Check referrer's referrer (prevent long chains)
    # If referrer was referred by someone with same wallet as current user = abuse
    if referrer.referred_by:
        referrer_parent = db.get_user(referrer.referred_by)
        if referrer_parent:
            # Check wallet matches
            if user.wallet_address and referrer_parent.wallet_address:
                if user.wallet_address == referrer_parent.wallet_address:
                    logger.warning(
                        f"Referral chain abuse detected: user {user.user_id} → "
                        f"referrer {referrer.user_id} → {referrer_parent.user_id} "
                        f"(wallet match: {user.wallet_address})"
                    )
                    return False, "Referral chain abuse detected"

            if user.connected_wallet and referrer_parent.connected_wallet:
                if user.connected_wallet == referrer_parent.connected_wallet:
                    logger.warning(
                        f"Referral chain abuse detected: user {user.user_id} → "
                        f"referrer {referrer.user_id} → {referrer_parent.user_id} "
                        f"(wallet match: {user.connected_wallet})"
                    )
                    return False, "Referral chain abuse detected"

    # SECURITY CHECK 5: Check for suspicious patterns (optional)
    # Could add:
    # - IP address matching
    # - User agent matching
    # - Creation time proximity
    # - Geographic location matching

    # All checks passed - apply referral code
    user.referred_by = referrer.user_id
    referrer.total_referrals += 1

    db.save_user(user)
    db.save_user(referrer)

    logger.info(
        f"Referral code applied: user {user.user_id} referred by "
        f"{referrer.user_id} (code: {referral_code})"
    )

    # Log to audit system
    from security.audit import audit_logger, AuditEventType, AuditSeverity

    audit_logger.log(
        event_type=AuditEventType.REFERRAL_USED,
        severity=AuditSeverity.INFO,
        user_id=user.user_id,
        details=f"Used referral code {referral_code} from user {referrer.user_id}"
    )

    return True, f"Referral code applied! Referred by {referrer.referral_code}"


def get_user_by_referral_code(db: Database, referral_code: str) -> User:
    """Get user by their referral code.

    Args:
        db: Database instance
        referral_code: Referral code to search for

    Returns:
        User object if found, None otherwise
    """
    import sqlite3

    conn = sqlite3.connect(db.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM users WHERE referral_code = ?
    """, (referral_code,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    # Use Database's existing _row_to_user if it exists, otherwise construct manually
    return db.get_user(row["user_id"])


def check_referral_abuse_patterns(db: Database) -> list:
    """Check for suspicious referral patterns.

    Returns:
        List of suspicious patterns detected
    """
    import sqlite3

    suspicious = []

    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    # Check 1: Users with same wallet referring each other
    cursor.execute("""
        SELECT
            u1.user_id as user1_id,
            u2.user_id as user2_id,
            u1.wallet_address as wallet,
            u1.total_referrals as user1_refs,
            u2.total_referrals as user2_refs
        FROM users u1
        JOIN users u2 ON u1.wallet_address = u2.wallet_address
        WHERE
            u1.user_id != u2.user_id
            AND u1.wallet_address IS NOT NULL
            AND (u1.total_referrals > 0 OR u2.total_referrals > 0)
    """)

    for row in cursor.fetchall():
        suspicious.append({
            "type": "same_wallet_referrers",
            "user1_id": row[0],
            "user2_id": row[1],
            "wallet": row[2],
            "details": f"Users {row[0]} and {row[1]} share wallet {row[2]} and have referrals"
        })

    # Check 2: Circular referral chains
    cursor.execute("""
        SELECT
            u1.user_id as user_id,
            u1.referred_by as referred_by,
            u2.referred_by as referrer_referred_by
        FROM users u1
        JOIN users u2 ON u1.referred_by = u2.user_id
        WHERE u2.referred_by = u1.user_id
    """)

    for row in cursor.fetchall():
        suspicious.append({
            "type": "circular_referral",
            "user_id": row[0],
            "referred_by": row[1],
            "details": f"Circular referral: {row[0]} ↔ {row[1]}"
        })

    # Check 3: Users with many referrals but low betting volume
    cursor.execute("""
        SELECT
            user_id,
            total_referrals,
            total_wagered,
            referral_earnings
        FROM users
        WHERE total_referrals > 10 AND total_wagered < 1.0
    """)

    for row in cursor.fetchall():
        suspicious.append({
            "type": "high_refs_low_volume",
            "user_id": row[0],
            "total_referrals": row[1],
            "total_wagered": row[2],
            "referral_earnings": row[3],
            "details": f"User {row[0]} has {row[1]} referrals but only {row[2]} SOL wagered"
        })

    conn.close()

    if suspicious:
        logger.warning(f"Found {len(suspicious)} suspicious referral patterns")
        for pattern in suspicious:
            logger.warning(f"  - {pattern['type']}: {pattern['details']}")

    return suspicious
