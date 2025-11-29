#!/bin/bash
# ========================================
# COINFLIP COMPLETE DEPLOYMENT SCRIPT
# Run this on volt-production (157.245.13.24)
# ========================================

set -e  # Exit on any error

echo "╔════════════════════════════════════════╗"
echo "║  🚀 COINFLIP PRODUCTION DEPLOYMENT     ║"
echo "╚════════════════════════════════════════╝"
echo ""

# ========================================
# PART 1: CLONE & SETUP BACKEND
# ========================================
echo "📦 Part 1: Setting up Coinflip Backend..."
echo "=========================================="

cd /opt

# Clone or update repository
if [ -d "coinflip" ]; then
    echo "⚠️  Coinflip directory exists - updating..."
    cd coinflip
    git pull
else
    echo "📥 Cloning from GitHub..."
    git clone https://github.com/DoradoDevs/coinflip-solana.git coinflip
    cd coinflip
fi

cd backend

# Create .env file
echo "📝 Creating production .env..."
cat > .env << 'ENVEOF'
# === COINFLIP PRODUCTION CONFIGURATION ===

# === NETWORK ===
SOLANA_NETWORK=mainnet-beta

# === TELEGRAM BOT ===
BOT_TOKEN=8118580040:AAF8leNlsAPgmzo6HiWw6isQls5aU9EvDsc
TELEGRAM_BOT_ENABLED=true
TELEGRAM_BOT_MODE=webhook
TELEGRAM_WEBHOOK_URL=https://api.coinflipvp.com/telegram/webhook

# === RPC ENDPOINTS (with failover) ===
RPC_URL=https://mainnet.helius-rpc.com/?api-key=f5bdd73b-a16d-4ab1-9793-aa2b445df328
HELIUS_RPC_URL=https://mainnet.helius-rpc.com/?api-key=f5bdd73b-a16d-4ab1-9793-aa2b445df328
BACKUP_RPC_URL_1=https://weathered-fabled-dawn.solana-mainnet.quiknode.pro/92b7cc6c8dae38865c77c3f32542d55f8a69358d/
QUICKNODE_RPC_URL=https://weathered-fabled-dawn.solana-mainnet.quiknode.pro/92b7cc6c8dae38865c77c3f32542d55f8a69358d/
BACKUP_RPC_URL_2=https://api.mainnet-beta.solana.com

# === HOUSE WALLET ===
HOUSE_WALLET_SECRET=53zReUfEZKZ5YVj4XzwtzGg44yJWW7R6ooctGDgz6X8LwNNWRN6KCGQTEGK66Bq2R34m993FDFgGycs5dpuTWYdD

# === TREASURY WALLET - LEDGER ===
TREASURY_WALLET=N7G9UdmkpsFkyzJpT74NpJ3Dghjt1iBeL4mTtwCunL3

# === ENCRYPTION ===
ENCRYPTION_KEY=2IpSdsd9xKQ118iTZrFqDGIoo3PYbQGPPpRbtlioud8=

# === ADMIN CONFIGURATION ===
ADMIN_EMAIL=coinflipsolmfa@gmail.com

# === SMTP CONFIGURATION (for 2FA) ===
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=coinflipsolmfa@gmail.com
SMTP_PASSWORD=clbhbnkzygdkpcnz

# === PLATFORM CONFIGURATION ===
PLATFORM_NAME=Coinflip
PLATFORM_URL=https://coinflipvp.com

# === DATABASE ===
DB_PATH=coinflip.db

# === API SERVER ===
API_HOST=0.0.0.0
API_PORT=8000

# === RATE LIMITING ===
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60

# === LOGGING ===
LOG_LEVEL=INFO

# === BACKUP CONFIGURATION ===
BACKUP_ENABLED=true
BACKUP_INTERVAL_HOURS=6
BACKUP_RETENTION_DAYS=30
BACKUP_LOCATION=backups/
ENVEOF

echo "✅ .env created"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip > /dev/null
pip install -r requirements.txt

echo "✅ Dependencies installed"

# Initialize database
echo "🗄️  Initializing database..."
python3 << 'PYEOF'
try:
    from database import Database
    db = Database()
    print("✅ Database initialized successfully")
except Exception as e:
    print(f"❌ Database initialization failed: {e}")
    exit(1)
PYEOF

# Create logs directory
mkdir -p /opt/coinflip/logs

# ========================================
# PART 2: CREATE SYSTEMD SERVICE
# ========================================
echo ""
echo "⚙️  Part 2: Creating systemd service..."
echo "=========================================="

cat > /etc/systemd/system/coinflip.service << 'SERVICEEOF'
[Unit]
Description=Coinflip API Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/coinflip/backend
Environment="PATH=/opt/coinflip/backend/venv/bin"
ExecStart=/opt/coinflip/backend/venv/bin/python api.py
Restart=always
RestartSec=10
StandardOutput=append:/opt/coinflip/logs/coinflip.log
StandardError=append:/opt/coinflip/logs/coinflip-error.log

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Reload and start service
systemctl daemon-reload
systemctl enable coinflip
systemctl restart coinflip

echo "✅ Coinflip service created and started"

# ========================================
# PART 3: INSTALL & CONFIGURE NGINX
# ========================================
echo ""
echo "🌐 Part 3: Configuring Nginx + SSL..."
echo "=========================================="

# Install nginx and certbot
apt update > /dev/null 2>&1
apt install -y nginx certbot python3-certbot-nginx > /dev/null 2>&1

# Create nginx config for API
cat > /etc/nginx/sites-available/coinflip-api << 'NGINXEOF'
server {
    listen 80;
    server_name api.coinflipvp.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # CORS
        add_header Access-Control-Allow-Origin "https://coinflipvp.com" always;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Content-Type, Authorization" always;

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

    # Health check
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }
}
NGINXEOF

# Enable site
ln -sf /etc/nginx/sites-available/coinflip-api /etc/nginx/sites-enabled/

# Test nginx config
nginx -t

# Reload nginx
systemctl reload nginx

echo "✅ Nginx configured"

# Get SSL certificate
echo "🔒 Obtaining SSL certificate..."
certbot --nginx -d api.coinflipvp.com --non-interactive --agree-tos --email coinflipsolmfa@gmail.com || {
    echo "⚠️  SSL certificate failed - DNS may not be propagated yet"
    echo "Run this later: certbot --nginx -d api.coinflipvp.com"
}

# ========================================
# PART 4: CONFIGURE TELEGRAM WEBHOOK
# ========================================
echo ""
echo "📱 Part 4: Setting Telegram webhook..."
echo "=========================================="

curl -X POST "https://api.telegram.org/bot8118580040:AAF8leNlsAPgmzo6HiWw6isQls5aU9EvDsc/setWebhook" \
  -d "url=https://api.coinflipvp.com/telegram/webhook" 2>/dev/null | python3 -m json.tool || echo "Webhook will be set once SSL is active"

# ========================================
# PART 5: SETUP AUTOMATED BACKUPS
# ========================================
echo ""
echo "💾 Part 5: Setting up automated backups..."
echo "=========================================="

# Create backup directory
mkdir -p /opt/coinflip/backups

# Create backup cron job (every 6 hours)
(crontab -l 2>/dev/null || echo "") | grep -v "coinflip backup" | cat - << 'CRONEOF' | crontab -
# Coinflip automated backup (every 6 hours)
0 */6 * * * cd /opt/coinflip/backend && /opt/coinflip/backend/venv/bin/python -c "from backup_system import BackupSystem; BackupSystem().create_backup()" >> /opt/coinflip/logs/backup.log 2>&1
CRONEOF

echo "✅ Automated backups configured (every 6 hours)"

# ========================================
# DEPLOYMENT COMPLETE
# ========================================
echo ""
echo "╔════════════════════════════════════════╗"
echo "║  ✅ DEPLOYMENT COMPLETE!               ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "📊 Service Status:"
systemctl status coinflip --no-pager -l | head -15

echo ""
echo "🔍 Quick Tests:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test API health
echo "1️⃣  Testing API health endpoint..."
sleep 2
curl -s http://localhost:8000/health | python3 -m json.tool || echo "⚠️  API not responding yet"

echo ""
echo "2️⃣  Checking service logs..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
tail -20 /opt/coinflip/logs/coinflip.log

echo ""
echo "📋 Useful Commands:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Service status:  systemctl status coinflip"
echo "  View logs:       tail -f /opt/coinflip/logs/coinflip.log"
echo "  Restart:         systemctl restart coinflip"
echo "  Test API:        curl https://api.coinflipvp.com/health"
echo ""
echo "🌐 Your endpoints:"
echo "  API:             https://api.coinflipvp.com"
echo "  Frontend:        https://coinflipvp.com (deploy separately)"
echo "  Telegram Bot:    https://t.me/YOUR_BOT_USERNAME"
echo ""
echo "📧 Admin Dashboard:"
echo "  python3 /opt/coinflip/backend/admin_dashboard.py"
echo ""
echo "🎉 Coinflip is now LIVE on mainnet!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
