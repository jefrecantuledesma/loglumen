#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Please run this script with sudo or as root."
    exit 1
fi

SERVICE_PATH="/etc/systemd/system/loglumen-server.service"
BIN_PATH="/usr/local/bin/loglumen-server"

echo "[+] Stopping loglumen-server.service (if running)"
if systemctl list-unit-files | grep -q '^loglumen-server\.service'; then
    systemctl disable --now loglumen-server.service || true
fi

echo "[+] Removing systemd unit ${SERVICE_PATH}"
rm -f "${SERVICE_PATH}"
systemctl daemon-reload

if [[ -f "${BIN_PATH}" ]]; then
    echo "[+] Removing binary ${BIN_PATH}"
    rm -f "${BIN_PATH}"
fi

echo "[✓] Loglumen server service removed."
echo "    Existing configuration in /etc/loglumen/server.toml was left in place."
