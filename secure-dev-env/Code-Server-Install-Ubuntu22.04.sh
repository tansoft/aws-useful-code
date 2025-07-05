#!/bin/bash
set -e
DomainName=${1:-dev.example.com}
CodeServerPassword=${2:-simplepass}

# Update package lists and install dependencies
sudo apt update -y
sudo apt install -y git nodejs npm make gcc g++

# Install Caddy using their official repository
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update -y
sudo apt install -y caddy
sudo systemctl enable --now caddy

# Configure Caddy
sudo tee /etc/caddy/Caddyfile <<EOF
http://${DomainName} http://*.${DomainName} {
  reverse_proxy 127.0.0.1:8889
}
EOF

# Create environment directory
mkdir -p ~/environment

# Install code-server
curl -fsSL https://code-server.dev/install.sh | sh
sudo systemctl enable --now code-server@ubuntu

# Configure code-server
HASHED_PASSWORD=$(echo -n "${CodeServerPassword}" | npx argon2-cli -e)
mkdir -p ~/.config/code-server
touch ~/.config/code-server/config.yaml
tee ~/.config/code-server/config.yaml <<EOF
cert: false
auth: password
hashed-password: "$HASHED_PASSWORD"
bind-addr: 127.0.0.1:8889
proxy-domain: ${DomainName}
EOF

# Configure VS Code settings
mkdir -p ~/.local/share/code-server/User
touch ~/.local/share/code-server/User/settings.json
tee ~/.local/share/code-server/User/settings.json <<EOF
{
  "extensions.autoUpdate": false,
  "extensions.autoCheckUpdates": false,
  "security.workspace.trust.enabled": false,
  "task.allowAutomaticTasks": "on",
  "telemetry.telemetryLevel": "off",
  "workbench.startupEditor": "terminal"
}
EOF

# Configure workspace settings
mkdir -p ~/environment/.vscode
tee ~/environment/.vscode/settings.json <<EOF
{
  "files.exclude": {
    "**/.*": true
  }
}
EOF

# Set default folder and install extensions
echo '{ "query": { "folder": "/home/ubuntu/environment" } }' > ~/.local/share/code-server/coder.json
code-server --install-extension ms-kubernetes-tools.vscode-kubernetes-tools --force
code-server --install-extension redhat.vscode-yaml --force
code-server --install-extension amazonwebservices.amazon-q-vscode --force

# Restart services
sudo systemctl restart caddy
sudo systemctl restart code-server@ubuntu
