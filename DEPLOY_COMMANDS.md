# Coinflip Deployment Commands

## Step 1: SSH into your server

```bash
ssh -i c:\Users\Clock\.ssh\volt_key root@157.245.13.24
```

(Enter your SSH key passphrase when prompted)

## Step 2: Download and run the deployment script

```bash
curl -o /tmp/deploy.sh https://raw.githubusercontent.com/DoradoDevs/coinflip-solana/main/FULL_DEPLOY.sh
chmod +x /tmp/deploy.sh
bash /tmp/deploy.sh
```

## Alternative: Manual deployment

If you prefer to run commands step-by-step:

```bash
# Clone the repository
cd /opt
git clone https://github.com/DoradoDevs/coinflip-solana.git coinflip
cd coinflip/backend

# The .env will be created automatically by the deployment script
# Or you can create it manually using the template from the repo

# Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Initialize database
python3 -c "from database import Database; db = Database(); print('✅ Database initialized')"

# Create systemd service
curl -o /tmp/coinflip.service https://raw.githubusercontent.com/DoradoDevs/coinflip-solana/main/coinflip.service
sudo mv /tmp/coinflip.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable coinflip
sudo systemctl start coinflip

# Check status
sudo systemctl status coinflip
```

## Step 3: Configure Nginx + SSL

```bash
# Install nginx and certbot
apt update
apt install -y nginx certbot python3-certbot-nginx

# Create nginx config
curl -o /tmp/coinflip-api https://raw.githubusercontent.com/DoradoDevs/coinflip-solana/main/nginx.conf
sudo mv /tmp/coinflip-api /etc/nginx/sites-available/
sudo ln -sf /etc/nginx/sites-available/coinflip-api /etc/nginx/sites-enabled/

# Test and reload nginx
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate (make sure DNS is pointing to this server first!)
sudo certbot --nginx -d api.coinflipvp.com --non-interactive --agree-tos --email coinflipsolmfa@gmail.com
```

## Step 4: Set Telegram Webhook

```bash
curl -X POST "https://api.telegram.org/bot8118580040:AAF8leNlsAPgmzo6HiWw6isQls5aU9EvDsc/setWebhook" \
  -d "url=https://api.coinflipvp.com/telegram/webhook"
```

## Step 5: Verify Deployment

```bash
# Check service status
systemctl status coinflip

# Check logs
tail -f /opt/coinflip/logs/coinflip.log

# Test API
curl https://api.coinflipvp.com/health

# Test locally
curl http://localhost:8000/health
```

## Quick Troubleshooting

**If service fails to start:**
```bash
journalctl -u coinflip -n 50 --no-pager
```

**If SSL fails:**
- Make sure DNS for api.coinflipvp.com points to 157.245.13.24
- Wait a few minutes for DNS propagation
- Then retry: `sudo certbot --nginx -d api.coinflipvp.com`

**To restart service:**
```bash
sudo systemctl restart coinflip
```
