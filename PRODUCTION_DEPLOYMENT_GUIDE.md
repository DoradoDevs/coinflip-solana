# 🚀 Production Deployment Guide

Complete guide for deploying Coinflip to production on Solana mainnet.

---

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Security Hardening](#security-hardening)
4. [Mainnet Configuration](#mainnet-configuration)
5. [Database Migration](#database-migration)
6. [Frontend Deployment](#frontend-deployment)
7. [Backend Deployment](#backend-deployment)
8. [Telegram Bot Deployment](#telegram-bot-deployment)
9. [Post-Deployment Testing](#post-deployment-testing)
10. [Monitoring & Alerts](#monitoring--alerts)
11. [Maintenance Procedures](#maintenance-procedures)
12. [Rollback Procedures](#rollback-procedures)

---

## Pre-Deployment Checklist

### Testing Complete ✅

- [ ] All web app tests pass (see `WEB_APP_TESTING_GUIDE.md`)
- [ ] All Telegram bot tests pass (see `TELEGRAM_BOT_TESTING_GUIDE.md`)
- [ ] All admin panel tests pass (see `ADMIN_PANEL_TESTING_GUIDE.md`)
- [ ] Security audit score: 95+/100
- [ ] All game flows work end-to-end
- [ ] Referral system working
- [ ] Tier progression working
- [ ] 2FA working

### Security Verified ✅

- [ ] Ledger wallet ready (see `LEDGER_WALLET_INTEGRATION.md`)
- [ ] AWS KMS configured (see `AWS_KMS_SETUP.md`) - OPTIONAL but recommended
- [ ] All private keys encrypted
- [ ] Backup system tested
- [ ] Emergency stop tested
- [ ] Recovery procedures tested

### Infrastructure Ready ✅

- [ ] Domain purchased and configured
- [ ] SSL certificate obtained
- [ ] Server provisioned (or cloud hosting ready)
- [ ] Database backup location configured
- [ ] RPC endpoints secured (Helius, QuickNode, etc.)
- [ ] SMTP configured for production

### Legal & Compliance ✅

- [ ] Terms of Service written
- [ ] Privacy Policy written
- [ ] Age verification implemented (if required)
- [ ] Gambling licenses obtained (if required by jurisdiction)
- [ ] Tax reporting procedures established
- [ ] User data protection compliance (GDPR, etc.)

---

## Infrastructure Setup

### Option A: Cloud Hosting (Recommended)

#### Backend API (DigitalOcean / AWS / GCP)

**Recommended specs:**
- **CPU:** 2+ vCPUs
- **RAM:** 4+ GB
- **Storage:** 50+ GB SSD
- **OS:** Ubuntu 22.04 LTS

**Setup:**
```bash
# Create droplet/instance
# DigitalOcean: $24/month (2 vCPU, 4GB RAM)
# AWS: t3.medium
# GCP: e2-medium

# SSH into server
ssh root@your-server-ip

# Update system
apt update && apt upgrade -y

# Install Python 3.10+
apt install python3.10 python3-pip python3-venv -y

# Install nginx
apt install nginx -y

# Install certbot (for SSL)
apt install certbot python3-certbot-nginx -y

# Install supervisor (for process management)
apt install supervisor -y
```

#### Frontend (Vercel / Netlify / Cloudflare Pages)

**Recommended:** Vercel (free tier for hobby projects)

**Features:**
- Automatic SSL
- CDN
- Automatic deploys from Git
- Zero config

---

### Option B: VPS (More control)

**Providers:**
- Linode
- Vultr
- Hetzner

**Same setup as Option A but manage everything yourself**

---

## Security Hardening

### 1. Server Security

```bash
# Create non-root user
adduser coinflip
usermod -aG sudo coinflip

# Disable root SSH
nano /etc/ssh/sshd_config
# Set: PermitRootLogin no
# Set: PasswordAuthentication no
systemctl restart sshd

# Setup firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 'Nginx Full'
ufw enable

# Install fail2ban
apt install fail2ban -y
systemctl enable fail2ban
systemctl start fail2ban
```

### 2. SSL Certificate

```bash
# Get certificate
certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal (already configured by certbot)
# Verify:
certbot renew --dry-run
```

### 3. Environment Variables

**NEVER commit `.env` to Git!**

```bash
# Create .env on server
nano /home/coinflip/backend/.env

# Set restrictive permissions
chmod 600 /home/coinflip/backend/.env
chown coinflip:coinflip /home/coinflip/backend/.env
```

---

## Mainnet Configuration

### 1. RPC Endpoints

**Get production RPC endpoints:**

**Helius (Recommended):**
- Visit: https://www.helius.dev/
- Sign up for account
- Create API key
- Free tier: 100,000 requests/day
- Paid: $49+/month for more

**QuickNode (Backup):**
- Visit: https://www.quicknode.com/
- Sign up
- Create Solana endpoint
- Free trial available
- Paid: $49+/month

**Public Fallback:**
- `https://api.mainnet-beta.solana.com` (rate limited)

### 2. Production `.env` Configuration

**Backend `.env`:**

```bash
# === NETWORK CONFIGURATION ===
SOLANA_NETWORK=mainnet-beta

# === RPC ENDPOINTS ===
# Primary
RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_HELIUS_KEY
HELIUS_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_HELIUS_KEY

# Backup
BACKUP_RPC_URL_1=https://your-endpoint.solana-mainnet.quiknode.pro/YOUR_KEY/
QUICKNODE_RPC_URL=https://your-endpoint.solana-mainnet.quiknode.pro/YOUR_KEY/

# Fallback (public)
BACKUP_RPC_URL_2=https://api.mainnet-beta.solana.com

# === ENCRYPTION ===
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=YOUR_PRODUCTION_FERNET_KEY_HERE

# CRITICAL: Back up this key securely! If lost, cannot decrypt wallets!
# Store in: Password manager, KMS, encrypted USB, etc.

# === WALLET CONFIGURATION ===
# CRITICAL: Use Ledger hardware wallet for production!
TREASURY_WALLET=YourLedgerWalletPublicKeyHere

# DO NOT set TREASURY_WALLET_SECRET in production!
# Use Ledger for signing (see LEDGER_WALLET_INTEGRATION.md)

# === ADMIN CONFIGURATION ===
ADMIN_EMAIL=admin@yourdomain.com

# === SMTP CONFIGURATION ===
# Production email (not Gmail - use SendGrid, AWS SES, etc.)
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=YOUR_SENDGRID_API_KEY

# Alternative: AWS SES
# SMTP_HOST=email-smtp.us-east-1.amazonaws.com
# SMTP_USERNAME=YOUR_AWS_SMTP_USERNAME
# SMTP_PASSWORD=YOUR_AWS_SMTP_PASSWORD

# === PLATFORM CONFIGURATION ===
PLATFORM_NAME=Coinflip
PLATFORM_URL=https://yourdomain.com

# === RATE LIMITING ===
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60

# === LOGGING ===
LOG_LEVEL=INFO
# LOG_LEVEL=DEBUG  # Only for debugging issues

# === TELEGRAM BOT ===
TELEGRAM_BOT_TOKEN=YOUR_PRODUCTION_BOT_TOKEN
TELEGRAM_BOT_ENABLED=true
TELEGRAM_BOT_MODE=webhook
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/telegram/webhook

# === AWS KMS (Optional but recommended) ===
# See AWS_KMS_SETUP.md
# AWS_REGION=us-east-1
# AWS_KMS_KEY_ID=your-kms-key-id
# USE_KMS_ENCRYPTION=true

# === BACKUP CONFIGURATION ===
BACKUP_ENABLED=true
BACKUP_INTERVAL_HOURS=6
BACKUP_RETENTION_DAYS=30
BACKUP_LOCATION=/home/coinflip/backups
```

**Frontend `.env`:**

```bash
# === API CONFIGURATION ===
REACT_APP_API_URL=https://api.yourdomain.com

# === SOLANA CONFIGURATION ===
REACT_APP_NETWORK=mainnet-beta
REACT_APP_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_PUBLIC_KEY

# === PLATFORM INFO ===
REACT_APP_PLATFORM_NAME=Coinflip
REACT_APP_TREASURY_WALLET=YourTreasuryWalletPublicKeyHere

# === ANALYTICS (Optional) ===
# REACT_APP_GA_TRACKING_ID=G-XXXXXXXXXX
```

### 3. Secure Encryption Key

**Generate production encryption key:**

```bash
python3 -c "from cryptography.fernet import Fernet; key = Fernet.generate_key().decode(); print(f'ENCRYPTION_KEY={key}')"
```

**Back up this key in MULTIPLE secure locations:**

1. **Password Manager** (1Password, Bitwarden, etc.)
2. **Encrypted USB drive** (store offline)
3. **AWS Secrets Manager / KMS**
4. **Paper backup** (in safe/safety deposit box)

⚠️ **CRITICAL:** If you lose this key, you CANNOT decrypt any wallet private keys!

### 4. Treasury Wallet Setup

**Option A: Ledger (STRONGLY RECOMMENDED)**

See `LEDGER_WALLET_INTEGRATION.md` for complete setup.

**Summary:**
1. Get Ledger Nano S/X
2. Initialize with seed phrase
3. Install Solana app
4. Connect to Solana CLI
5. Get public key → set as TREASURY_WALLET
6. Configure backend to use Ledger for treasury operations

**Benefits:**
- Private key NEVER on server
- Requires physical approval for transactions
- Secure even if server compromised

**Option B: Hot Wallet (NOT RECOMMENDED)**

Only use for testing or if Ledger not available:

```bash
# Generate wallet
solana-keygen new --outfile treasury.json

# Get public key
solana-keygen pubkey treasury.json

# Encrypt and store
# NEVER commit treasury.json to Git!
```

---

## Database Migration

### 1. Backup Devnet Database

```bash
# On local machine
cd backend
python -c "from backup_system import BackupSystem; bs = BackupSystem(); bs.create_backup()"

# Download backup
scp backend/backups/backup_*.db.gz.enc local_backup/
```

### 2. Start Fresh for Production

**CRITICAL:** DO NOT migrate devnet data to production!

**Reasons:**
- Devnet wallets won't work on mainnet
- Test data should not mix with real user data
- Security: Fresh start ensures no test vulnerabilities

**Initialize production database:**

```bash
# On production server
cd /home/coinflip/backend
python3 -c "from database import Database; db = Database(); print('✅ Production database initialized')"
```

### 3. Setup Automated Backups

```bash
# Create backup script
nano /home/coinflip/backup.sh
```

```bash
#!/bin/bash
cd /home/coinflip/backend
/usr/bin/python3 -c "
from backup_system import BackupSystem
bs = BackupSystem()
bs.create_backup(compress=True, encrypt=True)
print('Backup created')
"
```

```bash
# Make executable
chmod +x /home/coinflip/backup.sh

# Add to crontab (every 6 hours)
crontab -e
```

Add:
```
0 */6 * * * /home/coinflip/backup.sh >> /home/coinflip/logs/backup.log 2>&1
```

### 4. Offsite Backup

**Setup S3/Cloud Storage for backups:**

```bash
# Install AWS CLI
apt install awscli -y

# Configure
aws configure

# Sync backups to S3
# Add to backup.sh:
```

```bash
# ... after backup created ...
aws s3 sync /home/coinflip/backups s3://your-bucket/coinflip-backups/
echo "Backup synced to S3"
```

---

## Frontend Deployment

### Using Vercel (Recommended)

**1. Push code to GitHub:**

```bash
# Initialize git (if not already)
cd frontend
git init
git add .
git commit -m "Production ready"
git branch -M main
git remote add origin https://github.com/yourusername/coinflip-frontend.git
git push -u origin main
```

**2. Deploy to Vercel:**

1. Visit https://vercel.com
2. Sign up with GitHub
3. Click "New Project"
4. Import `coinflip-frontend` repo
5. Configure:
   - Framework: Create React App (auto-detected)
   - Root Directory: `./`
   - Build Command: `npm run build`
   - Output Directory: `build`
6. Add Environment Variables:
   ```
   REACT_APP_API_URL=https://api.yourdomain.com
   REACT_APP_NETWORK=mainnet-beta
   REACT_APP_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_KEY
   REACT_APP_TREASURY_WALLET=YourTreasuryPublicKey
   ```
7. Click "Deploy"

**3. Configure Custom Domain:**

1. In Vercel Dashboard → Settings → Domains
2. Add `yourdomain.com` and `www.yourdomain.com`
3. Add DNS records (Vercel provides instructions)
4. Wait for SSL (automatic)

**4. Verify Deployment:**

Visit `https://yourdomain.com`
- ✅ Site loads
- ✅ SSL active (HTTPS)
- ✅ Wallet connection works
- ✅ API calls work

---

### Alternative: Nginx + Build

If self-hosting:

```bash
# Build frontend
cd frontend
npm run build

# Copy to server
scp -r build/* user@server:/var/www/coinflip/

# Configure nginx
nano /etc/nginx/sites-available/coinflip
```

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name yourdomain.com www.yourdomain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Root
    root /var/www/coinflip;
    index index.html;

    # SPA routing
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

```bash
# Enable site
ln -s /etc/nginx/sites-available/coinflip /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

---

## Backend Deployment

### 1. Deploy Code

```bash
# On production server
cd /home/coinflip
git clone https://github.com/yourusername/coinflip-backend.git backend
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env (copy from secure location)
nano .env
# Paste production config

# Test
python -c "from database import Database; Database()"
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print('RPC:', os.getenv('RPC_URL')[:50])"
```

### 2. Configure Gunicorn

```bash
# Install gunicorn
pip install gunicorn

# Create gunicorn config
nano gunicorn_config.py
```

```python
# gunicorn_config.py
bind = "127.0.0.1:8000"
workers = 4  # 2 * CPU cores
worker_class = "uvicorn.workers.UvicornWorker"
keepalive = 120
timeout = 120
accesslog = "/home/coinflip/logs/gunicorn-access.log"
errorlog = "/home/coinflip/logs/gunicorn-error.log"
loglevel = "info"
```

### 3. Setup Supervisor

```bash
nano /etc/supervisor/conf.d/coinflip-api.conf
```

```ini
[program:coinflip-api]
command=/home/coinflip/backend/venv/bin/gunicorn api:app -c gunicorn_config.py
directory=/home/coinflip/backend
user=coinflip
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stderr_logfile=/home/coinflip/logs/api-stderr.log
stdout_logfile=/home/coinflip/logs/api-stdout.log
```

```bash
# Create logs directory
mkdir -p /home/coinflip/logs
chown -R coinflip:coinflip /home/coinflip

# Reload supervisor
supervisorctl reread
supervisorctl update
supervisorctl start coinflip-api

# Check status
supervisorctl status coinflip-api
```

### 4. Configure Nginx (API)

```bash
nano /etc/nginx/sites-available/coinflip-api
```

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    # SSL
    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    # Logs
    access_log /var/log/nginx/api-access.log;
    error_log /var/log/nginx/api-error.log;

    # CORS
    add_header Access-Control-Allow-Origin "https://yourdomain.com" always;
    add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
    add_header Access-Control-Allow-Headers "Content-Type, Authorization" always;

    # Proxy to backend
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Telegram webhook
    location /telegram/webhook {
        proxy_pass http://127.0.0.1:8000/telegram/webhook;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;
}
```

```bash
# Get SSL for API subdomain
certbot --nginx -d api.yourdomain.com

# Enable site
ln -s /etc/nginx/sites-available/coinflip-api /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

### 5. Verify Backend

```bash
# Check API
curl https://api.yourdomain.com/health

# Expected:
# {"status":"healthy","timestamp":"2025-11-28T10:30:00Z"}

# Check logs
tail -f /home/coinflip/logs/api-stdout.log
```

---

## Telegram Bot Deployment

### 1. Production Bot Setup

Create production bot in BotFather:

```
/newbot
Name: Coinflip
Username: coinflip_bot (or your chosen name)
```

Save token → add to `.env` as `TELEGRAM_BOT_TOKEN`

### 2. Configure Supervisor

```bash
nano /etc/supervisor/conf.d/coinflip-telegram.conf
```

```ini
[program:coinflip-telegram]
command=/home/coinflip/backend/venv/bin/python telegram_bot.py
directory=/home/coinflip/backend
user=coinflip
autostart=true
autorestart=true
stderr_logfile=/home/coinflip/logs/telegram-stderr.log
stdout_logfile=/home/coinflip/logs/telegram-stdout.log
```

```bash
supervisorctl reread
supervisorctl update
supervisorctl start coinflip-telegram
supervisorctl status coinflip-telegram
```

### 3. Set Webhook

```bash
# Set webhook URL
curl -X POST https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook \
  -d url=https://api.yourdomain.com/telegram/webhook

# Verify
curl https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo
```

Expected response:
```json
{
  "ok": true,
  "result": {
    "url": "https://api.yourdomain.com/telegram/webhook",
    "has_custom_certificate": false,
    "pending_update_count": 0
  }
}
```

### 4. Test Bot

1. Search for your bot in Telegram
2. Send `/start`
3. Verify response
4. Check logs: `tail -f /home/coinflip/logs/telegram-stdout.log`

---

## Post-Deployment Testing

### Critical Path Testing

**Test with SMALL amounts first!**

#### 1. Web App Quick Flip

1. Connect wallet
2. Play with 0.01 SOL
3. Verify win/loss works
4. Check balance updates

#### 2. Web App PVP

1. Create wager (0.01 SOL)
2. Accept with second wallet
3. Verify game completes
4. Check payouts received

#### 3. Telegram Bot

1. /start
2. Deposit 0.01 SOL
3. /flip 0.005 heads
4. Verify game works

#### 4. Referral System

1. Create referral code
2. Second user applies code
3. Second user plays game
4. Verify commission earned

#### 5. Tier System

1. Play enough to reach Bronze tier
2. Verify fee discount applied

#### 6. Admin Dashboard

1. Launch with 2FA
2. View escrows
3. Run security audit
4. Create backup

---

## Monitoring & Alerts

### 1. Server Monitoring

**Setup Uptime Monitoring:**

- **UptimeRobot** (free): https://uptimerobot.com/
- **Pingdom** (paid): https://www.pingdom.com/

Monitor:
- `https://yourdomain.com` (frontend)
- `https://api.yourdomain.com/health` (API)

Alert when down.

### 2. Log Monitoring

**Setup Logrotate:**

```bash
nano /etc/logrotate.d/coinflip
```

```
/home/coinflip/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 coinflip coinflip
    sharedscripts
    postrotate
        supervisorctl restart coinflip-api coinflip-telegram > /dev/null
    endscript
}
```

### 3. Error Alerting

**Setup error notifications:**

```python
# Add to api.py and telegram_bot.py

import requests

def send_alert(message):
    """Send critical alert to admin"""
    # Option 1: Email
    # send_email(ADMIN_EMAIL, "CRITICAL ALERT", message)

    # Option 2: Telegram (to admin)
    # requests.post(f'https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage',
    #              json={'chat_id': ADMIN_CHAT_ID, 'text': message})

    # Option 3: SMS (Twilio)
    # send_sms(ADMIN_PHONE, message)

# Use in critical errors:
try:
    # ... critical operation ...
except Exception as e:
    send_alert(f"CRITICAL ERROR: {e}")
    raise
```

### 4. Financial Monitoring

**Daily checks:**

```bash
# Create monitoring script
nano /home/coinflip/monitor.sh
```

```bash
#!/bin/bash

# Check treasury balance
BALANCE=$(solana balance $TREASURY_WALLET | awk '{print $1}')
echo "Treasury balance: $BALANCE SOL"

# Alert if below threshold
THRESHOLD=10.0
if (( $(echo "$BALANCE < $THRESHOLD" | bc -l) )); then
    echo "⚠️ Treasury balance low: $BALANCE SOL" | mail -s "Low Treasury Balance" $ADMIN_EMAIL
fi

# Check stuck escrows
cd /home/coinflip/backend
python3 -c "
from admin_recovery_tools import RecoveryTools
from database import Database
import os

recovery = RecoveryTools(Database(), os.getenv('ENCRYPTION_KEY'), os.getenv('RPC_URL'))
stuck = await recovery.check_stuck_escrows()

if stuck:
    total = sum(e['balance'] for e in stuck)
    print(f'⚠️ {len(stuck)} stuck escrows with {total} SOL total')
    # Send alert
"
```

```bash
# Run daily
crontab -e
# Add:
0 8 * * * /home/coinflip/monitor.sh >> /home/coinflip/logs/monitor.log 2>&1
```

---

## Maintenance Procedures

### Daily

```bash
# Check service status
supervisorctl status

# Check logs for errors
tail -n 100 /home/coinflip/logs/api-stderr.log | grep -i error
tail -n 100 /home/coinflip/logs/telegram-stderr.log | grep -i error

# Verify backups exist
ls -lh /home/coinflip/backups/backup_$(date +%Y%m%d)*.db.gz.enc

# Check treasury balance
solana balance $TREASURY_WALLET
```

### Weekly

```bash
# Security audit
cd /home/coinflip/backend
python admin_dashboard.py
# Option 8: Run Security Audit

# Check for updates
cd /home/coinflip/backend
git fetch
git status

# Review user activity
python -c "from database import Database; db = Database(); users = db.get_all_users(); print(f'Total users: {len(users)}'); games = db.get_recent_games(limit=1000); print(f'Games (7 days): {len(games)}')"
```

### Monthly

```bash
# Full backup to cold storage
# Download to external drive / USB

# Review security events
python admin_dashboard.py
# Option 9: View Recent Security Events

# Update dependencies
pip list --outdated
# Carefully update after testing

# Review Terms of Service / Privacy Policy
# Update if needed
```

---

## Rollback Procedures

### Emergency Rollback

**If critical issue detected:**

1. **Enable Emergency Stop:**
   ```bash
   touch /home/coinflip/backend/EMERGENCY_STOP
   ```

2. **Notify Users:**
   - Update website with maintenance notice
   - Post to social media
   - Send email to users (if applicable)

3. **Assess Issue:**
   ```bash
   # Check logs
   tail -f /home/coinflip/logs/*.log

   # Check database
   python -c "from database import Database; Database()"

   # Check RPC
   curl https://api.mainnet-beta.solana.com -X POST -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"getHealth"}'
   ```

4. **Restore from Backup (if needed):**
   ```bash
   # Stop services
   supervisorctl stop coinflip-api coinflip-telegram

   # Restore database
   cd /home/coinflip/backend
   python admin_dashboard.py
   # Option 14: Restore from Backup

   # Restart services
   supervisorctl start coinflip-api coinflip-telegram
   ```

5. **Verify Fix:**
   - Test all critical paths
   - Run security audit
   - Check escrow balances

6. **Resume Operations:**
   ```bash
   rm /home/coinflip/backend/EMERGENCY_STOP
   ```

---

## Cost Estimates

### Monthly Costs (Estimated)

**Infrastructure:**
- VPS (DigitalOcean): $24/month
- Domain: $12/year = $1/month
- SSL: Free (Let's Encrypt)
- **Total:** ~$25/month

**Services:**
- Helius RPC: $49/month (or free tier)
- Vercel: Free (hobby) or $20/month (pro)
- Email (SendGrid): Free (12k/month) or $15/month
- **Total:** $0-84/month

**Optional:**
- AWS KMS: $1/month + $0.03 per 10k requests
- S3 Backup: $0.023/GB/month
- Monitoring: Free (UptimeRobot) or $15/month
- **Total:** ~$1-16/month

**Grand Total:** $26-125/month

---

## Legal Disclaimer

⚠️ **IMPORTANT:**

This software is provided as-is for educational purposes. Deploying a gambling platform may be illegal in your jurisdiction.

**Before launching:**
1. Consult with a lawyer
2. Understand local gambling laws
3. Obtain necessary licenses
4. Implement age verification
5. Set up responsible gambling measures
6. Ensure tax compliance

**The developers assume NO liability for your use of this software.**

---

## Final Checklist

Before going live:

### Technical ✅

- [ ] All tests pass
- [ ] Security audit: 95+/100
- [ ] Ledger wallet configured
- [ ] Backups automated
- [ ] Monitoring setup
- [ ] SSL active
- [ ] Domain configured
- [ ] Emergency stop tested

### Security ✅

- [ ] Encryption key backed up (3+ locations)
- [ ] 2FA working
- [ ] Admin access restricted
- [ ] Rate limiting active
- [ ] HTTPS enforced
- [ ] Private keys never in code/logs

### Business ✅

- [ ] Terms of Service live
- [ ] Privacy Policy live
- [ ] Legal compliance verified
- [ ] Support email/contact ready
- [ ] Social media accounts ready
- [ ] Marketing plan ready

### Go Live! 🚀

```bash
# Final verification
curl https://yourdomain.com
curl https://api.yourdomain.com/health

# Monitor closely for first 24 hours
tail -f /home/coinflip/logs/*.log

# Be ready with emergency stop
echo "Platform is LIVE! 🎉"
```

---

**Last Updated:** 2025-11-28
**Version:** 1.0
**Status:** Production Ready 🚀
