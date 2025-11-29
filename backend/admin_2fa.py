"""
Two-Factor Authentication for Admin Dashboard via Email.

SECURITY: All admin operations require valid OTP sent to admin email.
"""
import os
import secrets
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class Admin2FA:
    """Two-factor authentication manager for admin operations."""

    def __init__(self):
        """Initialize 2FA system."""
        self.otp_store = {}  # {email: {'otp': '123456', 'expires': datetime}}
        self.otp_length = 6
        self.otp_valid_minutes = 10  # OTP valid for 10 minutes

        # Email configuration from environment
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.smtp_from_email = os.getenv("SMTP_FROM_EMAIL", self.smtp_username)

        if not self.smtp_username or not self.smtp_password:
            logger.warning(
                "⚠️ SMTP credentials not configured. "
                "Set SMTP_USERNAME and SMTP_PASSWORD in .env"
            )

    def generate_otp(self) -> str:
        """Generate random 6-digit OTP.

        Returns:
            6-digit OTP code
        """
        return ''.join([str(secrets.randbelow(10)) for _ in range(self.otp_length)])

    def send_otp_email(self, email: str, operation: str = "Admin Access") -> bool:
        """Send OTP to admin email.

        Args:
            email: Admin email address
            operation: Description of operation (for email subject)

        Returns:
            True if email sent successfully
        """
        # Generate OTP
        otp = self.generate_otp()

        # Store OTP with expiry
        expires_at = datetime.utcnow() + timedelta(minutes=self.otp_valid_minutes)
        self.otp_store[email] = {
            'otp': otp,
            'expires': expires_at,
            'attempts': 0
        }

        # Create email
        subject = f"🔐 Coinflip Admin 2FA Code - {operation}"

        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                <h1 style="color: white; margin: 0;">🔐 Admin 2FA Code</h1>
            </div>

            <div style="padding: 30px; background: #f7f7f7;">
                <h2>Your One-Time Password:</h2>

                <div style="background: white; padding: 20px; text-align: center; border-radius: 10px; margin: 20px 0;">
                    <span style="font-size: 36px; font-weight: bold; color: #667eea; letter-spacing: 8px;">
                        {otp}
                    </span>
                </div>

                <p><strong>Operation:</strong> {operation}</p>
                <p><strong>Valid for:</strong> {self.otp_valid_minutes} minutes</p>

                <div style="background: #fff3cd; padding: 15px; border-left: 4px solid #ffc107; margin-top: 20px;">
                    <p style="margin: 0; color: #856404;">
                        ⚠️ <strong>Security Notice:</strong><br>
                        Never share this code with anyone. Coinflip staff will never ask for your 2FA code.
                    </p>
                </div>

                <p style="color: #666; font-size: 12px; margin-top: 30px;">
                    If you didn't request this code, please ignore this email and secure your admin account.
                </p>
            </div>

            <div style="background: #333; padding: 20px; text-align: center; color: white;">
                <p style="margin: 0; font-size: 12px;">
                    Coinflip Admin Dashboard • Security Alert
                </p>
            </div>
        </body>
        </html>
        """

        # Send email
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_from_email
            msg['To'] = email

            # Attach HTML body
            html_part = MIMEText(body, 'html')
            msg.attach(html_part)

            # Connect to SMTP server
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()  # Enable TLS
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logger.info(f"✅ 2FA code sent to {email}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send 2FA email to {email}: {e}")
            return False

    def verify_otp(self, email: str, otp: str) -> Tuple[bool, str]:
        """Verify OTP code.

        Args:
            email: Admin email address
            otp: OTP code to verify

        Returns:
            Tuple of (is_valid, message)
        """
        # Check if OTP exists for this email
        if email not in self.otp_store:
            return False, "No OTP found. Please request a new code."

        stored_data = self.otp_store[email]

        # Check if expired
        if datetime.utcnow() > stored_data['expires']:
            del self.otp_store[email]
            return False, "OTP expired. Please request a new code."

        # Check attempt limit (prevent brute force)
        if stored_data['attempts'] >= 3:
            del self.otp_store[email]
            return False, "Too many failed attempts. Please request a new code."

        # Verify OTP
        if otp == stored_data['otp']:
            # Success - remove OTP (can only be used once)
            del self.otp_store[email]
            logger.info(f"✅ 2FA verification successful for {email}")
            return True, "Authentication successful!"

        else:
            # Failed attempt
            stored_data['attempts'] += 1
            remaining = 3 - stored_data['attempts']
            logger.warning(f"❌ 2FA verification failed for {email} (attempt {stored_data['attempts']}/3)")

            return False, f"Invalid code. {remaining} attempts remaining."

    def is_authenticated(self, session_id: str) -> bool:
        """Check if session is authenticated.

        Args:
            session_id: Session identifier

        Returns:
            True if authenticated
        """
        # In production, use Redis or database for session storage
        # For now, simple in-memory check
        return hasattr(self, f'_session_{session_id}')

    def create_session(self, email: str) -> str:
        """Create authenticated session.

        Args:
            email: Admin email

        Returns:
            Session ID
        """
        session_id = secrets.token_urlsafe(32)
        setattr(self, f'_session_{session_id}', {
            'email': email,
            'created': datetime.utcnow(),
            'expires': datetime.utcnow() + timedelta(hours=24)
        })

        logger.info(f"✅ Session created for {email}")
        return session_id


# Global 2FA instance
admin_2fa = Admin2FA()


# CLI helper functions
def request_2fa_login(email: str) -> bool:
    """Request 2FA login for admin dashboard.

    Args:
        email: Admin email address

    Returns:
        True if OTP sent successfully
    """
    print(f"\n🔐 Sending 2FA code to {email}...")

    if admin_2fa.send_otp_email(email, "Admin Dashboard Login"):
        print(f"✅ Code sent! Check your email.")
        print(f"⏰ Valid for {admin_2fa.otp_valid_minutes} minutes")
        return True
    else:
        print("❌ Failed to send code. Check SMTP configuration.")
        return False


def verify_2fa_login(email: str) -> bool:
    """Verify 2FA code for admin dashboard.

    Args:
        email: Admin email address

    Returns:
        True if authenticated
    """
    print("\n🔐 Two-Factor Authentication Required")

    for attempt in range(3):
        otp = input(f"Enter 6-digit code from email ({3-attempt} attempts left): ").strip()

        success, message = admin_2fa.verify_otp(email, otp)

        if success:
            print(f"✅ {message}")
            return True
        else:
            print(f"❌ {message}")

    return False


# Decorator for protecting admin functions
def require_2fa(func):
    """Decorator to require 2FA for admin functions.

    Usage:
        @require_2fa
        async def sensitive_operation():
            ...
    """
    import functools

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Get admin email
        admin_email = os.getenv("ADMIN_EMAIL")

        if not admin_email:
            print("❌ ADMIN_EMAIL not set in environment!")
            return None

        # Request 2FA
        if not request_2fa_login(admin_email):
            print("❌ 2FA setup failed")
            return None

        # Verify 2FA
        if not verify_2fa_login(admin_email):
            print("❌ 2FA verification failed")
            return None

        # Execute protected function
        print("✅ 2FA authenticated - executing operation...")
        return await func(*args, **kwargs)

    return wrapper


if __name__ == "__main__":
    # Test 2FA system
    import asyncio

    async def test():
        print("\n" + "="*60)
        print("🧪 TESTING 2FA SYSTEM")
        print("="*60)

        # Get admin email
        email = input("\nEnter admin email: ").strip()

        # Send OTP
        print("\n1️⃣ Sending OTP...")
        success = admin_2fa.send_otp_email(email, "Test Login")

        if not success:
            print("❌ Failed to send OTP. Check SMTP configuration in .env:")
            print("   SMTP_HOST=smtp.gmail.com")
            print("   SMTP_PORT=587")
            print("   SMTP_USERNAME=your_email@gmail.com")
            print("   SMTP_PASSWORD=your_app_password")
            return

        print("✅ OTP sent! Check your email.")

        # Verify OTP
        print("\n2️⃣ Verifying OTP...")
        otp = input("Enter 6-digit code: ").strip()

        valid, message = admin_2fa.verify_otp(email, otp)

        if valid:
            print(f"✅ {message}")
            print("\n🎉 2FA system working correctly!")
        else:
            print(f"❌ {message}")

    asyncio.run(test())
