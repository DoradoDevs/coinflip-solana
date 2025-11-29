#!/bin/bash
# Local: Push Coinflip to GitHub
# Run this after creating GitHub repo

cd "$(dirname "$0")"

echo "🚀 Pushing Coinflip to GitHub..."

# Add remote if not exists
git remote add origin https://github.com/DoradoDevs/coinflip-solana.git 2>/dev/null || true

# Push to GitHub
git push -u origin main

echo "✅ Coinflip pushed to GitHub!"
echo ""
echo "Next: Run DEPLOY_SERVER.sh on your server (157.245.13.24)"
