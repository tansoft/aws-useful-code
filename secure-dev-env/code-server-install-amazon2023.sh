#!/bin/bash
set -e
cloud-init status --wait
dnf update -y
dnf install -y git nodejs npm make gcc g++
dnf copr enable -y @caddy/caddy epel-9-`uname -m`
dnf install -y caddy
systemctl enable --now caddy

tee /etc/caddy/Caddyfile <<EOF
http://${DomainName} {
  reverse_proxy 127.0.0.1:8889
}
EOF

systemctl restart caddy

cat <<"EOT" | sudo -E -H -u ec2-user bash
set -e

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
code-server --install-extension ms-kubernetes-tools.vscode-kubernetes-tools --force
code-server --install-extension redhat.vscode-yaml --force

EOT

systemctl restart code-server@ec2-user
