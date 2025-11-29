# ☁️ AWS KMS (KEY MANAGEMENT SERVICE) SETUP

**Purpose:** Store and manage encryption keys in AWS instead of .env file.

**Why:** Even if server is compromised and .env is stolen, attacker can't decrypt private keys without AWS credentials.

---

## 🎯 WHAT IS AWS KMS?

**AWS KMS** = Amazon's Key Management Service
- Stores encryption keys securely
- Keys never leave AWS
- All encryption/decryption happens in AWS
- Full audit trail via CloudTrail
- FIPS 140-2 validated

### Before (Insecure):
```bash
# .env file
ENCRYPTION_KEY=my-super-secret-key-12345
```
↓ Server compromised → Attacker gets this → All private keys decrypted → All funds stolen

### After (Secure):
```python
# Keys stored in AWS KMS
# Encryption happens in AWS
# App only gets encrypted data back
# Can't decrypt without AWS IAM permissions
```
↓ Server compromised → Attacker has nothing → Funds safe

---

## 📋 STEP 1: AWS ACCOUNT SETUP

### 1.1 Create AWS Account
```bash
# Go to: https://aws.amazon.com
# Click "Create an AWS Account"
# Follow signup process
```

### 1.2 Create IAM User for Application
```bash
# AWS Console → IAM → Users → Add User

Name: coinflip-app
Access type: ✓ Programmatic access

# Attach policy: AWSKeyManagementServicePowerUser
# Or create custom policy (recommended):
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "kms:Decrypt",
        "kms:Encrypt",
        "kms:DescribeKey"
      ],
      "Resource": "arn:aws:kms:us-east-1:YOUR_ACCOUNT_ID:key/*"
    }
  ]
}

# Save Access Key ID and Secret Access Key
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

### 1.3 Install AWS CLI
```bash
# Windows:
msiexec.exe /i https://awscli.amazonaws.com/AWSCLIV2.msi

# Mac:
brew install awscli

# Linux:
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure AWS CLI:
aws configure
AWS Access Key ID: <your_access_key>
AWS Secret Access Key: <your_secret_key>
Default region: us-east-1
Default output format: json
```

---

## 🔑 STEP 2: CREATE KMS KEY

### 2.1 Create Master Key
```bash
# Via AWS CLI:
aws kms create-key \
  --description "Coinflip Platform Master Encryption Key" \
  --key-usage ENCRYPT_DECRYPT \
  --origin AWS_KMS \
  --region us-east-1

# Output:
{
  "KeyMetadata": {
    "KeyId": "12345678-1234-1234-1234-123456789012",
    "Arn": "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
  }
}

# Save this KeyId!
```

### 2.2 Create Alias (Easier to Reference)
```bash
aws kms create-alias \
  --alias-name alias/coinflip-master-key \
  --target-key-id 12345678-1234-1234-1234-123456789012 \
  --region us-east-1
```

### 2.3 Verify Key Created
```bash
aws kms describe-key \
  --key-id alias/coinflip-master-key \
  --region us-east-1
```

---

## 💻 STEP 3: IMPLEMENT KMS ENCRYPTION

### 3.1 Install boto3
```bash
pip install boto3
```

### 3.2 Create kms_encryption.py
```python
# backend/kms_encryption.py

"""
AWS KMS encryption utilities.

SECURITY: All encryption/decryption happens in AWS KMS.
Keys never leave AWS infrastructure.
"""
import boto3
import base64
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class KMSEncryption:
    """AWS KMS encryption manager."""

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize KMS client.

        Args:
            region: AWS region
        """
        self.region = region

        # Initialize KMS client
        self.kms = boto3.client(
            'kms',
            region_name=region,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
        )

        # Get KMS key ID from environment
        self.key_id = os.getenv("AWS_KMS_KEY_ID") or "alias/coinflip-master-key"

        logger.info(f"✅ KMS initialized - Region: {region}, Key: {self.key_id}")

    def encrypt_secret(self, plaintext: str) -> str:
        """Encrypt secret using AWS KMS.

        Args:
            plaintext: Secret to encrypt (e.g., private key)

        Returns:
            Base64-encoded encrypted ciphertext
        """
        try:
            response = self.kms.encrypt(
                KeyId=self.key_id,
                Plaintext=plaintext.encode('utf-8')
            )

            # Get ciphertext blob and encode as base64
            ciphertext = base64.b64encode(response['CiphertextBlob']).decode('utf-8')

            logger.debug(f"✅ Encrypted secret using KMS (length: {len(ciphertext)})")

            return ciphertext

        except Exception as e:
            logger.error(f"❌ KMS encryption failed: {e}")
            raise

    def decrypt_secret(self, ciphertext: str) -> str:
        """Decrypt secret using AWS KMS.

        Args:
            ciphertext: Base64-encoded encrypted secret

        Returns:
            Decrypted plaintext secret
        """
        try:
            # Decode base64
            ciphertext_blob = base64.b64decode(ciphertext.encode('utf-8'))

            # Decrypt using KMS
            response = self.kms.decrypt(
                CiphertextBlob=ciphertext_blob
            )

            # Get plaintext
            plaintext = response['Plaintext'].decode('utf-8')

            logger.debug(f"✅ Decrypted secret using KMS")

            return plaintext

        except Exception as e:
            logger.error(f"❌ KMS decryption failed: {e}")
            raise


# Global KMS instance
def get_kms_encryption() -> Optional[KMSEncryption]:
    """Get KMS encryption if enabled."""
    if os.getenv("USE_AWS_KMS", "").lower() == "true":
        region = os.getenv("AWS_REGION", "us-east-1")
        return KMSEncryption(region=region)

    return None


# Helper functions for backward compatibility
def encrypt_secret(plaintext: str, encryption_key: Optional[str] = None) -> str:
    """Encrypt secret (with KMS if enabled, otherwise Fernet).

    Args:
        plaintext: Secret to encrypt
        encryption_key: Fernet key (only used if KMS disabled)

    Returns:
        Encrypted ciphertext
    """
    kms = get_kms_encryption()

    if kms:
        # Use AWS KMS
        return kms.encrypt_secret(plaintext)

    else:
        # Fallback to Fernet (old method)
        from cryptography.fernet import Fernet

        if not encryption_key:
            encryption_key = os.getenv("ENCRYPTION_KEY")
            if not encryption_key:
                raise ValueError("ENCRYPTION_KEY not set")

        fernet = Fernet(encryption_key.encode())
        return fernet.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str, encryption_key: Optional[str] = None) -> str:
    """Decrypt secret (with KMS if enabled, otherwise Fernet).

    Args:
        ciphertext: Encrypted secret
        encryption_key: Fernet key (only used if KMS disabled)

    Returns:
        Decrypted plaintext
    """
    kms = get_kms_encryption()

    if kms:
        # Use AWS KMS
        return kms.decrypt_secret(ciphertext)

    else:
        # Fallback to Fernet
        from cryptography.fernet import Fernet

        if not encryption_key:
            encryption_key = os.getenv("ENCRYPTION_KEY")
            if not encryption_key:
                raise ValueError("ENCRYPTION_KEY not set")

        fernet = Fernet(encryption_key.encode())
        return fernet.decrypt(ciphertext.encode()).decode()
```

### 3.3 Update utils/encryption.py
```python
# backend/utils/encryption.py

"""
Encryption utilities with KMS support.

SECURITY: Uses AWS KMS if enabled, otherwise falls back to Fernet.
"""

# Import from kms_encryption (handles both KMS and Fernet)
from kms_encryption import encrypt_secret, decrypt_secret

__all__ = ['encrypt_secret', 'decrypt_secret']
```

---

## 🔄 STEP 4: MIGRATE EXISTING KEYS TO KMS

### 4.1 Backup Current Database
```bash
python -c "from backup_system import BackupSystem; BackupSystem().create_backup()"
```

### 4.2 Create Migration Script
```python
# backend/migrate_to_kms.py

"""
Migrate existing Fernet-encrypted keys to AWS KMS.

⚠️ CRITICAL: Backup database before running!
"""
import asyncio
import logging
import os
from database import Database
from kms_encryption import KMSEncryption
from cryptography.fernet import Fernet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_to_kms():
    """Migrate all encrypted secrets from Fernet to KMS."""

    # Verify KMS is configured
    if not os.getenv("USE_AWS_KMS"):
        print("❌ USE_AWS_KMS not set! Set to 'true' in .env")
        return

    print("\n" + "="*60)
    print("⚠️  KMS MIGRATION SCRIPT")
    print("="*60)
    print("\n🔒 This will re-encrypt ALL private keys using AWS KMS")
    print("📦 Make sure you have a database backup!")
    print()

    confirm = input("Type 'MIGRATE' to proceed: ")

    if confirm != "MIGRATE":
        print("❌ Migration cancelled")
        return

    # Initialize
    db = Database()
    kms = KMSEncryption()

    # Get old Fernet key
    old_encryption_key = input("Enter current ENCRYPTION_KEY (Fernet key): ")
    fernet = Fernet(old_encryption_key.encode())

    # Migrate users
    print("\n📊 Migrating user wallets...")

    import sqlite3
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    # Get all users with encrypted secrets
    cursor.execute("""
        SELECT user_id, encrypted_secret, referral_payout_escrow_secret
        FROM users
        WHERE encrypted_secret IS NOT NULL OR referral_payout_escrow_secret IS NOT NULL
    """)

    users = cursor.fetchall()

    for user_id, encrypted_secret, referral_escrow_secret in users:
        try:
            # Migrate custodial wallet
            if encrypted_secret:
                # Decrypt with Fernet
                plaintext = fernet.decrypt(encrypted_secret.encode()).decode()

                # Re-encrypt with KMS
                kms_ciphertext = kms.encrypt_secret(plaintext)

                # Update database
                cursor.execute("""
                    UPDATE users
                    SET encrypted_secret = ?
                    WHERE user_id = ?
                """, (kms_ciphertext, user_id))

                print(f"  ✅ User {user_id} - custodial wallet migrated")

            # Migrate referral escrow
            if referral_escrow_secret:
                plaintext = fernet.decrypt(referral_escrow_secret.encode()).decode()
                kms_ciphertext = kms.encrypt_secret(plaintext)

                cursor.execute("""
                    UPDATE users
                    SET referral_payout_escrow_secret = ?
                    WHERE user_id = ?
                """, (kms_ciphertext, user_id))

                print(f"  ✅ User {user_id} - referral escrow migrated")

        except Exception as e:
            print(f"  ❌ User {user_id} failed: {e}")

    # Migrate wager escrows
    print("\n📊 Migrating wager escrows...")

    cursor.execute("""
        SELECT wager_id, creator_escrow_secret, acceptor_escrow_secret
        FROM wagers
        WHERE creator_escrow_secret IS NOT NULL OR acceptor_escrow_secret IS NOT NULL
    """)

    wagers = cursor.fetchall()

    for wager_id, creator_secret, acceptor_secret in wagers:
        try:
            if creator_secret:
                plaintext = fernet.decrypt(creator_secret.encode()).decode()
                kms_ciphertext = kms.encrypt_secret(plaintext)

                cursor.execute("""
                    UPDATE wagers
                    SET creator_escrow_secret = ?
                    WHERE wager_id = ?
                """, (kms_ciphertext, wager_id))

                print(f"  ✅ Wager {wager_id[:12]}... - creator escrow migrated")

            if acceptor_secret:
                plaintext = fernet.decrypt(acceptor_secret.encode()).decode()
                kms_ciphertext = kms.encrypt_secret(plaintext)

                cursor.execute("""
                    UPDATE wagers
                    SET acceptor_escrow_secret = ?
                    WHERE wager_id = ?
                """, (kms_ciphertext, wager_id))

                print(f"  ✅ Wager {wager_id[:12]}... - acceptor escrow migrated")

        except Exception as e:
            print(f"  ❌ Wager {wager_id} failed: {e}")

    # Commit changes
    conn.commit()
    conn.close()

    print("\n" + "="*60)
    print("✅ MIGRATION COMPLETE!")
    print("="*60)
    print("\n📝 Next steps:")
    print("1. Verify all keys work: Run test script")
    print("2. Create new backup with KMS-encrypted keys")
    print("3. Remove old ENCRYPTION_KEY from .env")
    print("4. Keep old key in safe place (for old backups)")
    print()


if __name__ == "__main__":
    asyncio.run(migrate_to_kms())
```

### 4.3 Run Migration
```bash
# Set KMS environment variables first
export USE_AWS_KMS=true
export AWS_KMS_KEY_ID=alias/coinflip-master-key
export AWS_ACCESS_KEY_ID=AKIAIO...
export AWS_SECRET_ACCESS_KEY=wJalr...
export AWS_REGION=us-east-1

# Run migration
python migrate_to_kms.py
```

---

## 🧪 STEP 5: TESTING

### 5.1 Test KMS Encryption
```python
# test_kms.py

import asyncio
from kms_encryption import KMSEncryption

async def test():
    kms = KMSEncryption()

    # Test encrypt/decrypt
    secret = "test_private_key_12345"

    print("Encrypting...")
    ciphertext = kms.encrypt_secret(secret)
    print(f"Ciphertext: {ciphertext[:50]}...")

    print("Decrypting...")
    plaintext = kms.decrypt_secret(ciphertext)
    print(f"Plaintext: {plaintext}")

    assert plaintext == secret
    print("✅ KMS encryption/decryption works!")

asyncio.run(test())
```

### 5.2 Test Database Operations
```python
# Verify keys can be decrypted from database
from database import Database
from utils.encryption import decrypt_secret

db = Database()
user = db.get_user(1)  # Get any user

if user and user.encrypted_secret:
    try:
        plaintext = decrypt_secret(user.encrypted_secret)
        print(f"✅ Successfully decrypted user {user.user_id} wallet")
    except Exception as e:
        print(f"❌ Decryption failed: {e}")
```

---

## 🔐 STEP 6: PRODUCTION CONFIGURATION

### 6.1 Update .env
```bash
# BEFORE (Fernet):
ENCRYPTION_KEY=my-super-secret-key-12345

# AFTER (AWS KMS):
USE_AWS_KMS=true
AWS_KMS_KEY_ID=alias/coinflip-master-key
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=us-east-1

# Keep old key for reading old backups
ENCRYPTION_KEY_LEGACY=my-super-secret-key-12345
```

### 6.2 IAM Best Practices

**Create Separate Keys for Different Environments:**
```bash
# Development
alias/coinflip-dev-key

# Staging
alias/coinflip-staging-key

# Production
alias/coinflip-production-key
```

**Use IAM Roles Instead of Access Keys (EC2/ECS):**
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "kms:Decrypt",
      "kms:Encrypt"
    ],
    "Resource": "arn:aws:kms:us-east-1:*:key/*"
  }]
}
```

---

## 📊 COST ANALYSIS

### AWS KMS Pricing (us-east-1):
- **Key Storage:** $1/month per key
- **Encryption/Decryption:** $0.03 per 10,000 requests
- **Free Tier:** 20,000 requests/month free (first year)

### Example Monthly Costs:
```
Users: 10,000
Keys per user: 2 (custodial + referral escrow)
Key encryptions: 20,000
Key decryptions: ~100,000 (games, logins, etc.)

Cost:
- Key storage: $1
- Requests: (120,000 - 20,000 free) / 10,000 * $0.03 = $0.30

Total: ~$1.30/month
```

**= Extremely affordable for bank-grade security!**

---

## 🔒 SECURITY BENEFITS

### Before (Fernet in .env):
```
Attacker gets .env file → Has ENCRYPTION_KEY → Decrypts all private keys → Steals all funds
```

### After (AWS KMS):
```
Attacker gets .env file → Has AWS credentials → But...
  ↓
Need to call KMS API to decrypt
  ↓
CloudTrail logs ALL decryption attempts
  ↓
Can set up alarm: "Alert if > 100 decrypt calls/minute"
  ↓
Can revoke AWS credentials instantly
  ↓
Can enable MFA for KMS operations
  ↓
Keys never leave AWS (can't extract them)
```

### Additional Security:
- **Key Rotation:** Auto-rotate KMS keys annually
- **Audit Trail:** CloudTrail logs every encryption/decryption
- **Access Control:** IAM policies control who can use keys
- **Regional:** Keys can't leave AWS region
- **FIPS 140-2:** Validated hardware security modules

---

## ⚠️ IMPORTANT NOTES

1. **Don't Lose AWS Credentials:**
   - If lost, you can't decrypt keys
   - Store IAM access keys securely
   - Use AWS Secrets Manager or Parameter Store for extra security

2. **Enable CloudTrail:**
   ```bash
   # Monitor all KMS operations
   aws cloudtrail create-trail --name coinflip-kms-audit --s3-bucket-name my-trail-bucket
   ```

3. **Set Up Alarms:**
   ```bash
   # Alert on unusual KMS activity
   aws cloudwatch put-metric-alarm --alarm-name kms-high-usage --metric-name CallCount --namespace AWS/KMS
   ```

4. **Backup Strategy:**
   - Old backups use Fernet (keep ENCRYPTION_KEY_LEGACY)
   - New backups use KMS
   - Test restore from both types

5. **Disaster Recovery:**
   - KMS keys are AWS-managed, can't be lost
   - But if AWS account locked, you're stuck
   - Keep emergency Fernet backup of critical keys

---

## 🆘 TROUBLESHOOTING

### "AccessDeniedException"
```bash
# Check IAM permissions
aws kms describe-key --key-id alias/coinflip-master-key

# Verify AWS credentials
aws sts get-caller-identity
```

### "KMS key not found"
```bash
# List keys
aws kms list-keys

# List aliases
aws kms list-aliases
```

### "Decryption failed"
```bash
# Check if ciphertext is base64 encoded correctly
# Verify using correct KMS key
# Check AWS region matches
```

---

## 📈 MIGRATION CHECKLIST

- [ ] Create AWS account
- [ ] Set up IAM user with KMS permissions
- [ ] Create KMS master key
- [ ] Install boto3
- [ ] Create kms_encryption.py
- [ ] Test KMS encrypt/decrypt
- [ ] Backup current database
- [ ] Run migration script
- [ ] Verify all keys decrypt correctly
- [ ] Create new KMS-encrypted backup
- [ ] Update .env with KMS config
- [ ] Remove old ENCRYPTION_KEY (keep as LEGACY)
- [ ] Set up CloudTrail logging
- [ ] Set up CloudWatch alarms
- [ ] Test in development
- [ ] Deploy to production

---

**RESULT: Your encryption keys are now managed by AWS, not a file on disk. Enterprise-grade security.** ☁️🔒
