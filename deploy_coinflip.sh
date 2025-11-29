#!/bin/bash
# Coinflip Production Deployment Script
# Run this on volt-production server (157.245.13.24)

set -e  # Exit on error

echo "🚀 Coinflip Deployment Starting..."
echo "=================================="

# Navigate to /opt
cd /opt

# Check if coinflip directory exists
if [ -d "coinflip" ]; then
    echo "⚠️  Coinflip directory exists. Updating..."
    cd coinflip
    git pull
else
    echo "📦 Cloning Coinflip from GitHub..."
    git clone https://github.com/DoradoDevs/coinflip-solana.git coinflip
    cd coinflip
fi

# Go to backend
cd backend

# Create .env file
echo "📝 Creating .env file..."
cat > .env << 'EOF'
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
EOF

echo "✅ .env created"

# Create virtual environment
echo "📦 Setting up Python environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate venv and install dependencies
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Dependencies installed"

# Initialize database
echo "🗄️  Initializing database..."
python3 -c "from database import Database; db = Database(); print('✅ Database initialized')"

# Create systemd service
echo "⚙️  Creating systemd service..."
cat > /etc/systemd/system/coinflip.service << 'EOF'
[Unit]
Description=Coinflip API Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/coinflip/backend
Environment="PATH=/opt/coinflip/backend/venv/bin"
ExecStart=/opt/coinflip/backend/venv/bin/python /opt/coinflip/backend/api.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and start service
systemctl daemon-reload
systemctl enable coinflip
systemctl start coinflip

echo "✅ Coinflip service started"

# Check status
sleep 2
systemctl status coinflip --no-pager -l | head -20

echo ""
echo "=================================="
echo "✅ Coinflip Deployment Complete!"
echo "=================================="
echo ""
echo "Service: systemctl status coinflip"
echo "Logs: journalctl -u coinflip -f"
echo ""
echo "Next: Configure Nginx + SSL"
