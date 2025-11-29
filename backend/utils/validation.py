"""
Input validation utilities for security.
"""
import re
from typing import Tuple


def is_valid_solana_address(address: str) -> Tuple[bool, str]:
    """Validate Solana public key format.

    Args:
        address: Solana wallet address to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not address:
        return False, "Wallet address is required"

    # Solana addresses are base58 encoded, 32-44 characters
    if not isinstance(address, str):
        return False, "Wallet address must be a string"

    if len(address) < 32 or len(address) > 44:
        return False, "Invalid wallet address length"

    # Check for valid base58 characters (no 0, O, I, l)
    valid_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    if not all(c in valid_chars for c in address):
        return False, "Wallet address contains invalid characters"

    # Try to decode as base58
    try:
        import base58
        decoded = base58.b58decode(address)
        if len(decoded) != 32:
            return False, "Invalid wallet address format (must be 32 bytes when decoded)"
    except Exception as e:
        return False, f"Failed to decode wallet address: {str(e)}"

    return True, ""


def is_valid_amount(amount: float, min_amount: float = 0.001, max_amount: float = 1000.0) -> Tuple[bool, str]:
    """Validate wager amount.

    Args:
        amount: Amount in SOL
        min_amount: Minimum allowed amount
        max_amount: Maximum allowed amount

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(amount, (int, float)):
        return False, "Amount must be a number"

    if amount <= 0:
        return False, "Amount must be greater than 0"

    if amount < min_amount:
        return False, f"Amount must be at least {min_amount} SOL"

    if amount > max_amount:
        return False, f"Amount cannot exceed {max_amount} SOL"

    return True, ""


def is_valid_transaction_signature(signature: str) -> Tuple[bool, str]:
    """Validate Solana transaction signature format.

    Args:
        signature: Transaction signature to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not signature:
        return False, "Transaction signature is required"

    if not isinstance(signature, str):
        return False, "Transaction signature must be a string"

    # Solana signatures are base58 encoded, typically 87-88 characters
    if len(signature) < 80 or len(signature) > 90:
        return False, "Invalid transaction signature length"

    # Check for valid base58 characters
    valid_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    if not all(c in valid_chars for c in signature):
        return False, "Transaction signature contains invalid characters"

    return True, ""


def is_valid_referral_code(code: str) -> Tuple[bool, str]:
    """Validate referral code format.

    Args:
        code: Referral code to validate (e.g., "FLIP-A3B9")

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not code:
        return False, "Referral code is required"

    if not isinstance(code, str):
        return False, "Referral code must be a string"

    # Expected format: FLIP-XXXX (where X is alphanumeric)
    pattern = r'^FLIP-[A-Z0-9]{4}$'
    if not re.match(pattern, code):
        return False, "Invalid referral code format (expected: FLIP-XXXX)"

    return True, ""


def sanitize_username(username: str, max_length: int = 32) -> str:
    """Sanitize username for safe storage.

    Args:
        username: Username to sanitize
        max_length: Maximum length

    Returns:
        Sanitized username
    """
    if not username:
        return ""

    # Remove control characters and trim
    sanitized = ''.join(c for c in username if c.isprintable())
    sanitized = sanitized.strip()

    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized
