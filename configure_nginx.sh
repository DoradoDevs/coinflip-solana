#!/bin/bash
# Nginx + SSL Configuration for Coinflip
# Run this AFTER deploy_coinflip.sh

set -e

echo "🌐 Configuring Nginx for Coinflip..."
echo "===================================="

# Install nginx and certbot if not already installed
apt update
apt install -y nginx certbot python3-certbot-nginx

# Create API nginx config
echo "📝 Creating Nginx config for API..."
cat > /etc/nginx/sites-available/coinflip-api << 'EOF'
server {
    listen 80;
    server_name api.coinflipvp.com;

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
}
EOF

# Enable site
ln -sf /etc/nginx/sites-available/coinflip-api /etc/nginx/sites-enabled/

# Test nginx config
nginx -t

# Reload nginx
systemctl reload nginx

echo "✅ Nginx configured"

# Get SSL certificate
echo "🔒 Getting SSL certificate..."
echo "This will ask for your email and agreement to Terms of Service"

certbot --nginx -d api.coinflipvp.com --non-interactive --agree-tos --email coinflipsolmfa@gmail.com || echo "⚠️ SSL setup failed - you may need to run certbot manually"

echo ""
echo "===================================="
echo "✅ Nginx + SSL Configuration Complete!"
echo "===================================="
echo ""
echo "Test API: curl https://api.coinflipvp.com/health"
echo "View logs: tail -f /var/log/nginx/access.log"
echo ""
echo "Next: Test the deployment!"
