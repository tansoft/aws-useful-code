#!/bin/bash
set -e
DomainName=${1:-dev.example.com}
CodeServerPassword=${2:-simplepass}

sudo dnf update -y
sudo dnf install -y git nodejs npm make gcc g++
sudo dnf copr enable -y @caddy/caddy epel-9-`uname -m`
sudo dnf install -y caddy
sudo systemctl enable --now caddy

sudo tee /etc/caddy/Caddyfile <<EOF
http://${DomainName} http://*.${DomainName} {
  reverse_proxy 127.0.0.1:8889
}
EOF

mkdir -p ~/environment

curl -fsSL https://code-server.dev/install.sh | sh
sudo systemctl enable --now code-server@ec2-user

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

mkdir -p ~/environment/.vscode
tee ~/environment/.vscode/settings.json <<EOF
{
  "files.exclude": {
    "**/.*": true
  }
}
EOF

echo '{ "query": { "folder": "/home/ec2-user/environment" } }' > ~/.local/share/code-server/coder.json
#code-server --install-extension ms-kubernetes-tools.vscode-kubernetes-tools --force
#code-server --install-extension redhat.vscode-yaml --force
#code-server --install-extension amazonwebservices.amazon-q-vscode --force

sudo systemctl restart caddy
sudo systemctl restart code-server@ec2-user
