"""
Authentication module for Coinflip.
Handles password hashing, session management, and referral code generation.
"""
import hashlib
import secrets
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

# Use bcrypt for password hashing (secure, industry standard)
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

from database import User


# Session settings
SESSION_DURATION_DAYS = 30  # Sessions last 30 days
REFERRAL_CODE_LENGTH = 8


def hash_password(password: str) -> str:
    """Hash password using bcrypt (or fallback to SHA-256 + salt)."""
    if BCRYPT_AVAILABLE:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    else:
        # Fallback: SHA-256 with random salt (less secure than bcrypt)
        salt = secrets.token_hex(16)
        hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return f"sha256${salt}${hashed}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against stored hash."""
    if BCRYPT_AVAILABLE and password_hash.startswith("$2"):
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    elif password_hash.startswith("sha256$"):
        # Fallback verification
        parts = password_hash.split("$")
        if len(parts) != 3:
            return False
        salt, stored_hash = parts[1], parts[2]
        computed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return computed == stored_hash
    return False


def generate_session_token() -> str:
    """Generate a secure random session token."""
    return secrets.token_urlsafe(32)


def generate_referral_code() -> str:
    """Generate a unique referral code."""
    # Generate 8 character alphanumeric code (uppercase)
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # Exclude confusing chars (0, O, 1, I)
    return "".join(secrets.choice(chars) for _ in range(REFERRAL_CODE_LENGTH))


def create_session(user: User) -> Tuple[str, datetime]:
    """Create a new session for user. Returns (token, expires_at)."""
    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=SESSION_DURATION_DAYS)
    return token, expires_at


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_username(username: str) -> Tuple[bool, str]:
    """
    Validate username format.
    Returns (is_valid, error_message).
    """
    if not username:
        return False, "Username is required"

    if len(username) < 3:
        return False, "Username must be at least 3 characters"

    if len(username) > 20:
        return False, "Username must be 20 characters or less"

    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Username can only contain letters, numbers, and underscores"

    if username[0].isdigit():
        return False, "Username cannot start with a number"

    return True, ""


def validate_password(password: str) -> Tuple[bool, str]:
    """
    Validate password strength.
    Returns (is_valid, error_message).
    """
    if not password:
        return False, "Password is required"

    if len(password) < 8:
        return False, "Password must be at least 8 characters"

    if len(password) > 128:
        return False, "Password is too long"

    # Check for at least one number and one letter
    has_letter = any(c.isalpha() for c in password)
    has_number = any(c.isdigit() for c in password)

    if not (has_letter and has_number):
        return False, "Password must contain at least one letter and one number"

    return True, ""


# Tier thresholds (volume in SOL)
TIER_THRESHOLDS = {
    "Starter": 0,
    "Bronze": 10,
    "Silver": 50,
    "Gold": 200,
    "Diamond": 500
}

# Fee rates per tier (all 2% for now, can adjust later)
TIER_FEE_RATES = {
    "Starter": 0.02,
    "Bronze": 0.02,
    "Silver": 0.02,
    "Gold": 0.02,
    "Diamond": 0.02
}


def calculate_tier(total_wagered: float) -> Tuple[str, float]:
    """
    Calculate user's tier based on total wagered volume.
    Returns (tier_name, fee_rate).
    """
    tier = "Starter"

    for tier_name, threshold in sorted(TIER_THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
        if total_wagered >= threshold:
            tier = tier_name
            break

    fee_rate = TIER_FEE_RATES.get(tier, 0.02)
    return tier, fee_rate


# Referral reward rates by tier (percentage of platform fee)
TIER_REFERRAL_RATES = {
    "Starter": 0.0,      # 0%
    "Bronze": 0.025,     # 2.5%
    "Silver": 0.05,      # 5%
    "Gold": 0.075,       # 7.5%
    "Diamond": 0.10      # 10%
}


def calculate_referral_reward(platform_fee: float, referrer_tier: str = "Starter") -> float:
    """Calculate referral reward from platform fee based on referrer's tier."""
    rate = TIER_REFERRAL_RATES.get(referrer_tier, 0.0)
    return platform_fee * rate


def validate_referral_code(code: str) -> Tuple[bool, str]:
    """
    Validate custom referral code format.
    Returns (is_valid, error_message).
    """
    if not code:
        return False, "Referral code is required"

    if len(code) < 3:
        return False, "Referral code must be at least 3 characters"

    if len(code) > 16:
        return False, "Referral code must be 16 characters or less"

    if not re.match(r'^[a-zA-Z0-9_]+$', code):
        return False, "Referral code can only contain letters, numbers, and underscores"

    return True, ""
