#!/bin/bash
# Run this script as root on your production server.
# It creates a 'deploy' user with Docker access and sets up SSH key auth.

set -e

echo "=== Setting up deploy user ==="

# Create deploy user (no password login, only SSH key)
useradd -m -s /bin/bash deploy 2>/dev/null || echo "User 'deploy' already exists"

# Add to docker group so it can run docker/compose without sudo
usermod -aG docker deploy

# Create SSH directory
mkdir -p /home/deploy/.ssh
chmod 700 /home/deploy/.ssh

# Generate deploy SSH keypair (if not exists)
if [ ! -f /home/deploy/.ssh/id_ed25519 ]; then
    ssh-keygen -t ed25519 -f /home/deploy/.ssh/id_ed25519 -N "" -C "github-actions-deploy"
    echo ""
    echo "SSH keypair generated."
fi

# Authorize the deploy key
cp /home/deploy/.ssh/id_ed25519.pub /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh

# Move project to /opt and give deploy user ownership
if [ -d /root/TradingSimulator ]; then
    echo "Moving project from /root/TradingSimulator to /opt/TradingSimulator..."
    cp -r /root/TradingSimulator /opt/TradingSimulator 2>/dev/null || true
    chown -R deploy:deploy /opt/TradingSimulator
fi

# If project doesn't exist in /opt yet, clone it
if [ ! -d /opt/TradingSimulator ]; then
    echo "Cloning project to /opt/TradingSimulator..."
    sudo -u deploy git clone https://github.com/huanjou/TradingSimulator.git /opt/TradingSimulator
fi

chown -R deploy:deploy /opt/TradingSimulator

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "1. Copy the PRIVATE key to GitHub Secrets as SSH_PRIVATE_KEY:"
echo "   cat /home/deploy/.ssh/id_ed25519"
echo ""
echo "2. Add these GitHub Secrets (Settings -> Secrets -> Actions):"
echo "   SERVER_HOST = your server IP"
echo "   SSH_PRIVATE_KEY = (contents from step 1)"
echo ""
echo "3. Copy your infra/.env to /opt/TradingSimulator/infra/.env"
echo "   (secrets are not in git)"
echo ""
echo "4. Ensure Docker is installed and running on the server"
echo ""
