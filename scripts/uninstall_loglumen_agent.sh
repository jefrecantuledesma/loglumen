#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Please run this script with sudo or as root."
    exit 1
fi

SERVICE_PATH="/etc/systemd/system/loglumen-agent.service"

echo "[+] Stopping loglumen-agent.service (if running)"
if systemctl list-unit-files | grep -q '^loglumen-agent\.service'; then
    systemctl disable --now loglumen-agent.service || true
fi

echo "[+] Removing systemd unit ${SERVICE_PATH}"
rm -f "${SERVICE_PATH}"
systemctl daemon-reload

echo "[✓] Loglumen agent service removed."
echo "    Configuration in /etc/loglumen/agent.toml was left in place."
