#!/usr/bin/env bash
# Richtet den automatischen Start nach dem Hochfahren ein (Linux/WSL mit systemd, macOS).
# Windows: siehe README, Abschnitt "Autostart unter Windows".
set -euo pipefail
cd "$(dirname "$0")/.."
DIR="$(pwd)"

if [[ "$(uname -s)" == "Darwin" ]]; then
    plist="$HOME/Library/LaunchAgents/com.contentcrew.jarvis.plist"
    mkdir -p "$(dirname "$plist")"
    cat >"$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.contentcrew.jarvis</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$DIR/scripts/start.sh</string></array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$DIR/data/crew.log</string>
  <key>StandardErrorPath</key><string>$DIR/data/crew.log</string>
</dict></plist>
EOF
    launchctl unload "$plist" 2>/dev/null || true
    launchctl load "$plist"
    echo "Autostart eingerichtet. Log: $DIR/data/crew.log"
    exit 0
fi

if ! systemctl --user status >/dev/null 2>&1; then
    echo "systemd ist nicht aktiv. Unter WSL: in /etc/wsl.conf '[boot]' 'systemd=true' eintragen," >&2
    echo "dann in PowerShell 'wsl --shutdown' und WSL neu öffnen." >&2
    exit 1
fi
mkdir -p "$HOME/.config/systemd/user" data
cat >"$HOME/.config/systemd/user/content-crew.service" <<EOF
[Unit]
Description=Jarvis Content Crew
After=network-online.target

[Service]
WorkingDirectory=$DIR
ExecStart=/bin/bash $DIR/scripts/start.sh
Restart=always
RestartSec=30
StandardOutput=append:$DIR/data/crew.log
StandardError=append:$DIR/data/crew.log

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now content-crew.service
loginctl enable-linger "$USER" 2>/dev/null || sudo loginctl enable-linger "$USER" || true
echo "Autostart eingerichtet. Status: systemctl --user status content-crew   Log: $DIR/data/crew.log"
