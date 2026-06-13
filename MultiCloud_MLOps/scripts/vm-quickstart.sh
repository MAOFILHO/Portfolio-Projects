#!/bin/bash
set -e

echo "🚀 Guardian AI - VM Quick Start"
echo "================================"

# Update system
echo "📦 Updating system..."
sudo apt update && sudo apt upgrade -y

# Install Docker
echo "🐳 Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Install kubectl
echo "☸️  Installing kubectl..."
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Install Helm
echo "⎈ Installing Helm..."
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Install Azure CLI
echo "☁️  Installing Azure CLI..."
curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Install Python
echo "🐍 Installing Python..."
sudo apt install -y python3.11 python3.11-venv python3-pip

# Install Node.js
echo "📗 Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Install utilities
echo "🔧 Installing utilities..."
sudo apt install -y git vim curl wget jq

echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "1. Clone repository: git clone <repo-url>"
echo "2. Follow VM_DEPLOYMENT_GUIDE.md"
