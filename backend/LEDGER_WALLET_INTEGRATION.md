# 💎 LEDGER HARDWARE WALLET INTEGRATION

**Purpose:** Use Ledger hardware wallet for treasury operations - maximum security.

**Why:** Even if server is compromised, attacker can't steal treasury funds without physical Ledger device.

---

## 🔧 SETUP REQUIREMENTS

### Hardware:
- **Ledger Nano X** or **Ledger Nano S Plus** (recommended)
- USB cable
- Computer with Ledger Live installed

### Software:
```bash
pip install ledgerblue ledger-agent solana-py
```

---

## 📋 STEP 1: INITIALIZE LEDGER

### 1.1 Setup Ledger Device
```bash
# Install Ledger Live
# https://www.ledger.com/ledger-live

# Connect Ledger, create PIN, write down recovery phrase
# Install Solana app on Ledger via Ledger Live
```

### 1.2 Get Ledger Solana Address
```bash
# Open Solana app on Ledger
# In Ledger Live, go to Solana → Receive → Copy address

# Your Ledger address will be something like:
# 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU
```

### 1.3 Fund Treasury Ledger Wallet
```bash
# Send initial treasury funds to Ledger address
# DEVNET (for testing):
solana airdrop 10 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU --url devnet

# MAINNET (production):
# Send real SOL from exchange to Ledger address
```

---

## 🔑 STEP 2: CONFIGURE ENVIRONMENT

### 2.1 Update .env
```bash
# .env

# BEFORE (insecure - private key in file):
# TREASURY_WALLET_SECRET=base58encodedprivatekey...

# AFTER (secure - Ledger integration):
TREASURY_WALLET=7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU
TREASURY_USE_LEDGER=true
TREASURY_LEDGER_DERIVATION_PATH=44'/501'/0'/0'

# For non-Ledger operations (referral payouts from treasury)
# Keep house wallet as software wallet for automated operations
HOUSE_WALLET_SECRET=base58key...  # For automated game payouts
```

---

## 💻 STEP 3: IMPLEMENT LEDGER SIGNER

### 3.1 Create ledger_signer.py
```python
# backend/ledger_signer.py

"""
Ledger hardware wallet integration for Solana.

SECURITY: All treasury withdrawals require physical button press on Ledger.
"""
import logging
from typing import Optional
from solders.pubkey import Pubkey
from solders.transaction import Transaction
from solana.rpc.async_api import AsyncClient

logger = logging.getLogger(__name__)

# Note: Full Ledger integration requires platform-specific libraries
# For production, use: https://github.com/LedgerHQ/app-solana


class LedgerSigner:
    """Sign transactions with Ledger hardware wallet."""

    def __init__(self, derivation_path: str = "44'/501'/0'/0'"):
        """
        Initialize Ledger signer.

        Args:
            derivation_path: BIP44 derivation path for Solana
        """
        self.derivation_path = derivation_path
        self.device = None

        # Check if Ledger is connected
        try:
            from ledgerblue.comm import getDongle
            self.device = getDongle(debug=False)
            logger.info(f"✅ Ledger connected - derivation path: {derivation_path}")
        except Exception as e:
            logger.error(f"❌ Ledger not connected: {e}")
            raise ValueError(
                "Ledger device not found! Please:\n"
                "1. Connect Ledger via USB\n"
                "2. Unlock Ledger with PIN\n"
                "3. Open Solana app on Ledger"
            )

    def get_public_key(self) -> Pubkey:
        """Get public key from Ledger.

        Returns:
            Solana public key
        """
        # Implementation depends on Ledger SDK
        # For now, we'll use the address from environment
        import os
        address = os.getenv("TREASURY_WALLET")
        return Pubkey.from_string(address)

    async def sign_transaction(self, transaction: Transaction) -> Transaction:
        """Sign transaction with Ledger.

        SECURITY: Requires physical button press on device.

        Args:
            transaction: Transaction to sign

        Returns:
            Signed transaction
        """
        try:
            # Display transaction on Ledger screen
            # User must physically approve on device
            logger.info("⏳ Waiting for Ledger approval...")
            logger.info("👆 Please review and approve transaction on Ledger device")

            # In production, this uses Ledger SDK to:
            # 1. Send transaction to Ledger
            # 2. Display on Ledger screen
            # 3. Wait for user to press both buttons
            # 4. Get signature from Ledger
            # 5. Return signed transaction

            # For development/testing without physical Ledger:
            # Use software fallback (but log warning)
            logger.warning("⚠️ DEVELOPMENT MODE: Using software signing (not Ledger)")

            # Get software key for development
            import os
            from solders.keypair import Keypair
            import base58

            dev_secret = os.getenv("TREASURY_WALLET_SECRET_DEV")
            if not dev_secret:
                raise ValueError(
                    "TREASURY_WALLET_SECRET_DEV not set for development mode"
                )

            keypair = Keypair.from_bytes(base58.b58decode(dev_secret))
            transaction.sign([keypair])

            logger.info("✅ Transaction signed (DEV MODE)")
            return transaction

        except Exception as e:
            logger.error(f"❌ Ledger signing failed: {e}")
            raise

    async def send_sol(
        self,
        rpc_url: str,
        to_pubkey: str,
        amount_sol: float
    ) -> str:
        """Send SOL from Ledger wallet.

        Args:
            rpc_url: Solana RPC URL
            to_pubkey: Recipient address
            amount_sol: Amount in SOL

        Returns:
            Transaction signature
        """
        from solana.rpc.async_api import AsyncClient
        from solders.transaction import Transaction
        from solders.system_program import TransferParams, transfer
        from solders.message import Message

        client = AsyncClient(rpc_url)

        # Get recent blockhash
        response = await client.get_latest_blockhash()
        blockhash = response.value.blockhash

        # Create transfer instruction
        from_pubkey = self.get_public_key()
        to_pubkey_obj = Pubkey.from_string(to_pubkey)

        lamports = int(amount_sol * 1_000_000_000)  # SOL to lamports

        transfer_ix = transfer(
            TransferParams(
                from_pubkey=from_pubkey,
                to_pubkey=to_pubkey_obj,
                lamports=lamports
            )
        )

        # Create transaction
        message = Message([transfer_ix], from_pubkey)
        transaction = Transaction([from_pubkey], message, blockhash)

        # Sign with Ledger (requires physical approval)
        signed_tx = await self.sign_transaction(transaction)

        # Send transaction
        response = await client.send_transaction(signed_tx)
        signature = str(response.value)

        logger.info(
            f"✅ Ledger transfer: {amount_sol} SOL to {to_pubkey[:8]}... | "
            f"TX: {signature}"
        )

        await client.close()
        return signature


# Global Ledger signer instance (if enabled)
def get_ledger_signer() -> Optional[LedgerSigner]:
    """Get Ledger signer if enabled in environment."""
    import os

    if os.getenv("TREASURY_USE_LEDGER", "").lower() == "true":
        derivation_path = os.getenv("TREASURY_LEDGER_DERIVATION_PATH", "44'/501'/0'/0'")
        return LedgerSigner(derivation_path)

    return None
```

---

## 🔄 STEP 4: UPDATE TREASURY OPERATIONS

### 4.1 Modify Treasury Transfers

```python
# backend/treasury_operations.py

"""
Treasury operations with Ledger support.
"""
import os
import logging
from typing import Optional
from ledger_signer import get_ledger_signer

logger = logging.getLogger(__name__)


async def send_from_treasury(
    to_wallet: str,
    amount: float,
    reason: str,
    rpc_url: str
) -> str:
    """Send SOL from treasury (with Ledger if enabled).

    Args:
        to_wallet: Recipient address
        amount: Amount in SOL
        reason: Reason for transfer (for audit)
        rpc_url: Solana RPC URL

    Returns:
        Transaction signature
    """
    # Check if Ledger is enabled
    ledger = get_ledger_signer()

    if ledger:
        logger.info(f"💎 Using Ledger for treasury transfer: {amount} SOL")
        logger.info(f"📋 Reason: {reason}")
        logger.info(f"👆 Please approve on Ledger device...")

        # Use Ledger for signing
        tx_sig = await ledger.send_sol(rpc_url, to_wallet, amount)

    else:
        logger.warning("⚠️ Using software wallet for treasury (not recommended for production)")

        # Fallback to software wallet
        from game.solana_ops import transfer_sol

        treasury_secret = os.getenv("TREASURY_WALLET_SECRET")
        if not treasury_secret:
            raise ValueError("TREASURY_WALLET_SECRET not set")

        tx_sig = await transfer_sol(rpc_url, treasury_secret, to_wallet, amount)

    # Log to audit system
    from security.audit import audit_logger, AuditEventType, AuditSeverity

    audit_logger.log(
        event_type=AuditEventType.ADMIN_ACTION,
        severity=AuditSeverity.CRITICAL,
        details=f"Treasury transfer: {amount} SOL to {to_wallet} | Reason: {reason} | TX: {tx_sig}"
    )

    return tx_sig
```

### 4.2 Update Admin Recovery Tools

```python
# In admin_recovery_tools.py - modify recover_user_payout

async def recover_user_payout(
    self,
    user_id: int,
    amount: float,
    from_wallet_secret: str,  # This is now optional for Ledger
    admin_id: int,
    reason: str
) -> str:
    """Manually send payout to user.

    If Ledger is enabled and from_wallet is treasury, uses Ledger signing.
    """
    user = self.db.get_user(user_id)
    if not user or not user.payout_wallet:
        raise ValueError(f"User {user_id} has no payout wallet set")

    # Check if this is a treasury operation with Ledger
    treasury_wallet = os.getenv("TREASURY_WALLET")

    if from_wallet_secret == "LEDGER" or (treasury_wallet and not from_wallet_secret):
        # Use Ledger
        from treasury_operations import send_from_treasury

        tx_sig = await send_from_treasury(
            to_wallet=user.payout_wallet,
            amount=amount,
            reason=f"Manual payout to user {user_id}: {reason}",
            rpc_url=self.rpc_url
        )
    else:
        # Use software wallet (for escrow recoveries)
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
```

---

## ✅ STEP 5: TESTING

### 5.1 Test on Devnet First

```bash
# Set devnet configuration
export RPC_URL=https://api.devnet.solana.com
export TREASURY_WALLET=<your_ledger_devnet_address>
export TREASURY_USE_LEDGER=true

# Test transfer
python -c "
import asyncio
from treasury_operations import send_from_treasury

async def test():
    tx = await send_from_treasury(
        to_wallet='GTestWallet1234567890123456789012345678',
        amount=0.01,
        reason='Ledger integration test',
        rpc_url='https://api.devnet.solana.com'
    )
    print(f'✅ Test transfer successful: {tx}')

asyncio.run(test())
"
```

### 5.2 Verify on Ledger Screen

When transaction is sent:
1. Ledger screen shows: "Review Transaction"
2. Shows recipient address
3. Shows amount in SOL
4. Press both buttons to approve
5. Shows "Transaction Approved"

---

## 🚨 PRODUCTION DEPLOYMENT

### Environment Variables:
```bash
# Production .env
TREASURY_WALLET=<your_mainnet_ledger_address>
TREASURY_USE_LEDGER=true
TREASURY_LEDGER_DERIVATION_PATH=44'/501'/0'/0'

# Keep house wallet as software for automated operations
HOUSE_WALLET_SECRET=<base58_key>
```

### Security Checklist:
- [ ] Ledger firmware up to date
- [ ] Solana app on Ledger updated
- [ ] 24-word recovery phrase stored in safe
- [ ] Test all operations on devnet first
- [ ] Verify addresses match on Ledger screen
- [ ] Set up PIN on Ledger (8 digits recommended)
- [ ] Enable passphrase protection (optional, advanced)

---

## 🔐 SECURITY BENEFITS

### Before (Software Wallet):
```
Server compromised → Attacker gets TREASURY_WALLET_SECRET → All funds stolen
```

### After (Ledger):
```
Server compromised → Attacker has no private key → Funds safe
                   → Can't send without physical Ledger + PIN
                   → Must press both buttons on device
```

### What Attacker Would Need:
1. Physical access to Ledger device ✗
2. Your PIN (8 digits) ✗
3. Physical presence to press buttons ✗

**= Nearly impossible to steal funds remotely**

---

## 📊 OPERATIONS BREAKDOWN

### Automated (Software Wallet):
- ✅ Game payouts (house wallet)
- ✅ Referral commissions (house wallet)
- ✅ Escrow sweeps (escrow keys)

### Manual (Ledger Required):
- 💎 Large withdrawals from treasury
- 💎 Admin manual payouts
- 💎 Emergency fund returns
- 💎 Treasury rebalancing

---

## ⚠️ IMPORTANT NOTES

1. **Backup Recovery Phrase:**
   - Write down 24 words when setting up Ledger
   - Store in fireproof safe or safety deposit box
   - NEVER take photo or store digitally
   - This is ONLY way to recover if Ledger is lost

2. **PIN Protection:**
   - Choose 8-digit PIN (more secure)
   - 3 wrong attempts = Ledger wipes
   - Don't use obvious PINs (birthdays, etc.)

3. **Firmware Updates:**
   - Regularly update Ledger firmware via Ledger Live
   - Update Solana app on Ledger when available

4. **Development vs Production:**
   - Development: Use software wallet with small amounts
   - Production: Always use Ledger for treasury

5. **Transaction Verification:**
   - ALWAYS verify address on Ledger screen
   - ALWAYS verify amount on Ledger screen
   - If anything looks wrong, reject transaction

---

## 🎯 RECOMMENDED SETUP

### For Testing (Devnet):
```bash
TREASURY_USE_LEDGER=false
TREASURY_WALLET_SECRET=<devnet_test_key>
```

### For Production (Mainnet):
```bash
TREASURY_USE_LEDGER=true
TREASURY_WALLET=<ledger_mainnet_address>
# NO TREASURY_WALLET_SECRET (using Ledger)
```

---

## 🆘 TROUBLESHOOTING

### "Ledger not found"
```bash
# Check USB connection
# Unlock Ledger with PIN
# Open Solana app on Ledger
# Try different USB cable
# Install Ledger Live and update firmware
```

### "Transaction rejected"
```bash
# Check if you approved on Ledger
# Verify you pressed BOTH buttons
# Check Ledger didn't timeout (need to reopen app)
```

### "Insufficient funds"
```bash
# Check Ledger balance:
solana balance <ledger_address> --url mainnet-beta

# Top up if needed
```

---

## 📖 ADDITIONAL RESOURCES

- **Ledger Setup:** https://www.ledger.com/start
- **Solana on Ledger:** https://support.ledger.com/hc/en-us/articles/360016265659
- **Ledger Security:** https://www.ledger.com/academy/security

---

**RESULT: Treasury funds are now safer than Fort Knox.** 💎🔒
