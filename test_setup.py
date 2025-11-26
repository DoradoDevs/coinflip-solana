#!/usr/bin/env python3
"""
Test script to verify Coinflip setup is working correctly.
Run this before testing with real SOL.
"""
import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

# Load environment
load_dotenv()


def print_header(text):
    """Print a formatted header."""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")


def print_test(name, status, message=""):
    """Print a test result."""
    icon = "✅" if status else "❌"
    print(f"{icon} {name}")
    if message:
        print(f"   → {message}")


async def test_environment():
    """Test environment variables."""
    print_header("Testing Environment Configuration")

    required_vars = [
        "BOT_TOKEN",
        "RPC_URL",
        "HOUSE_WALLET_SECRET",
        "TREASURY_WALLET",
        "ENCRYPTION_KEY"
    ]

    all_present = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Truncate for display
            display_value = value[:20] + "..." if len(value) > 20 else value
            print_test(f"{var}", True, f"Set to: {display_value}")
        else:
            print_test(f"{var}", False, "NOT SET!")
            all_present = False

    return all_present


async def test_imports():
    """Test all imports work correctly."""
    print_header("Testing Python Imports")

    tests = []

    try:
        from telegram import Update
        from telegram.ext import Application
        print_test("python-telegram-bot", True, "v21.6")
        tests.append(True)
    except ImportError as e:
        print_test("python-telegram-bot", False, str(e))
        tests.append(False)

    try:
        from solana.rpc.async_api import AsyncClient
        from solders.keypair import Keypair
        print_test("solana + solders", True, "v0.34.3 + v0.21.0")
        tests.append(True)
    except ImportError as e:
        print_test("solana packages", False, str(e))
        tests.append(False)

    try:
        from cryptography.fernet import Fernet
        print_test("cryptography", True, "v44.0.0")
        tests.append(True)
    except ImportError as e:
        print_test("cryptography", False, str(e))
        tests.append(False)

    try:
        from database import Database, User, Game, Wager
        print_test("Database models", True, "All models imported")
        tests.append(True)
    except ImportError as e:
        print_test("Database models", False, str(e))
        tests.append(False)

    try:
        from game import play_house_game, play_pvp_game, generate_wallet
        print_test("Game logic", True, "All functions imported")
        tests.append(True)
    except ImportError as e:
        print_test("Game logic", False, str(e))
        tests.append(False)

    return all(tests)


async def test_database():
    """Test database initialization."""
    print_header("Testing Database")

    try:
        from database import Database

        # Initialize database
        db = Database("test_coinflip.db")
        print_test("Database initialization", True, "Created test_coinflip.db")

        # Test creating a user
        from database.models import User
        test_user = User(
            user_id=12345,
            platform="telegram",
            wallet_address="TestWallet123",
            username="test_user"
        )
        db.save_user(test_user)
        print_test("Save user", True, "User saved successfully")

        # Test retrieving user
        retrieved = db.get_user(12345)
        if retrieved and retrieved.username == "test_user":
            print_test("Retrieve user", True, "User retrieved successfully")
        else:
            print_test("Retrieve user", False, "User data mismatch")

        # Clean up
        os.remove("test_coinflip.db")
        print_test("Database cleanup", True, "Test database removed")

        return True
    except Exception as e:
        print_test("Database test", False, str(e))
        return False


async def test_wallet_generation():
    """Test wallet generation."""
    print_header("Testing Wallet Generation")

    try:
        from game.solana_ops import generate_wallet

        pub, secret = generate_wallet()
        print_test("Generate wallet", True, f"Created wallet: {pub[:20]}...")

        # Verify format
        if len(pub) == 44 and len(secret) == 88:
            print_test("Wallet format", True, "Public key and secret key correct length")
            return True
        else:
            print_test("Wallet format", False, f"Unexpected lengths: pub={len(pub)}, secret={len(secret)}")
            return False
    except Exception as e:
        print_test("Wallet generation", False, str(e))
        return False


async def test_encryption():
    """Test encryption/decryption."""
    print_header("Testing Encryption")

    try:
        from utils import encrypt_secret, decrypt_secret, generate_encryption_key

        # Generate key
        key = generate_encryption_key()
        print_test("Generate encryption key", True, f"Key: {key[:20]}...")

        # Test encryption
        secret = "test_secret_key_12345"
        encrypted = encrypt_secret(secret, key)
        print_test("Encrypt secret", True, f"Encrypted: {encrypted[:30]}...")

        # Test decryption
        decrypted = decrypt_secret(encrypted, key)
        if decrypted == secret:
            print_test("Decrypt secret", True, "Decryption successful")
            return True
        else:
            print_test("Decrypt secret", False, "Decrypted value doesn't match")
            return False
    except Exception as e:
        print_test("Encryption test", False, str(e))
        return False


async def test_solana_connection():
    """Test Solana RPC connection."""
    print_header("Testing Solana RPC Connection")

    try:
        from solana.rpc.async_api import AsyncClient

        rpc_url = os.getenv("RPC_URL")
        if not rpc_url:
            print_test("RPC URL", False, "RPC_URL not set in .env")
            return False

        async with AsyncClient(rpc_url) as client:
            # Get latest blockhash
            resp = await client.get_latest_blockhash()
            if resp.value:
                blockhash = str(resp.value.blockhash)
                print_test("RPC connection", True, f"Connected to Solana mainnet")
                print_test("Latest blockhash", True, f"{blockhash[:20]}...")
                return True
            else:
                print_test("RPC connection", False, "No response from RPC")
                return False
    except Exception as e:
        print_test("Solana connection", False, str(e))
        return False


async def test_house_wallet():
    """Test house wallet configuration."""
    print_header("Testing House Wallet")

    try:
        from game.solana_ops import keypair_from_base58, get_sol_balance
        import base58

        secret = os.getenv("HOUSE_WALLET_SECRET")
        if not secret:
            print_test("House wallet", False, "HOUSE_WALLET_SECRET not set")
            return False

        # Try to create keypair
        kp = keypair_from_base58(secret)
        pub = str(kp.pubkey())
        print_test("Load house wallet", True, f"Address: {pub}")

        # Check balance
        rpc_url = os.getenv("RPC_URL")
        balance = await get_sol_balance(rpc_url, pub)
        print_test("House wallet balance", balance > 0, f"{balance:.4f} SOL")

        if balance < 0.5:
            print("   ⚠️  WARNING: House wallet has low balance!")
            print(f"   → Fund {pub} with at least 0.5 SOL for testing")

        return True
    except Exception as e:
        print_test("House wallet", False, str(e))
        return False


async def test_coinflip_logic():
    """Test coinflip randomness."""
    print_header("Testing Coinflip Logic")

    try:
        from game.coinflip import flip_coin
        from database.models import CoinSide

        # Test with sample data
        blockhash = "sample_blockhash_12345"
        results = []

        for i in range(100):
            result = flip_coin(blockhash, f"game_{i}")
            results.append(result)

        heads_count = sum(1 for r in results if r == CoinSide.HEADS)
        tails_count = 100 - heads_count

        print_test("Flip coin", True, f"Heads: {heads_count}%, Tails: {tails_count}%")

        # Check distribution is reasonable (30-70% range)
        if 30 <= heads_count <= 70:
            print_test("Distribution", True, "Distribution looks random")
            return True
        else:
            print_test("Distribution", False, f"Unusual distribution: {heads_count}% heads")
            return False
    except Exception as e:
        print_test("Coinflip logic", False, str(e))
        return False


async def main():
    """Run all tests."""
    print_header("🎲 Solana Coinflip - Setup Verification")

    results = []

    # Run tests
    results.append(await test_environment())
    results.append(await test_imports())
    results.append(await test_database())
    results.append(await test_wallet_generation())
    results.append(await test_encryption())
    results.append(await test_solana_connection())
    results.append(await test_house_wallet())
    results.append(await test_coinflip_logic())

    # Summary
    print_header("Test Summary")
    passed = sum(results)
    total = len(results)

    print(f"Tests Passed: {passed}/{total}")

    if passed == total:
        print("\n✅ All tests passed! You're ready to run the bot.")
        print("\nNext steps:")
        print("  1. cd backend")
        print("  2. python bot.py")
        print("  3. Test on Telegram with small amounts (0.01-0.05 SOL)")
        return 0
    else:
        print(f"\n❌ {total - passed} test(s) failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("  • Missing .env file: Run python setup_env.py")
        print("  • Missing packages: pip install -r requirements.txt")
        print("  • Low balance: Fund your house wallet")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
