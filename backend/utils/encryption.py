"""
Wallet encryption utilities.
"""
from cryptography.fernet import Fernet


def generate_encryption_key() -> str:
    """Generate a new encryption key."""
    return Fernet.generate_key().decode('utf-8')


def encrypt_secret(secret: str, encryption_key: str) -> str:
    """Encrypt a wallet secret key."""
    f = Fernet(encryption_key.encode())
    encrypted = f.encrypt(secret.encode())
    return encrypted.decode('utf-8')


def decrypt_secret(encrypted_secret: str, encryption_key: str) -> str:
    """Decrypt a wallet secret key."""
    f = Fernet(encryption_key.encode())
    decrypted = f.decrypt(encrypted_secret.encode())
    return decrypted.decode('utf-8')
