#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Please run this script with sudo or as root."
    exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVER_DIR="${REPO_ROOT}/server"
SERVICE_TEMPLATE="${REPO_ROOT}/deploy/server/loglumen-server.service"
SERVICE_PATH="/etc/systemd/system/loglumen-server.service"
BIN_PATH="/usr/local/bin/loglumen-server"
CONFIG_DIR="/etc/loglumen"
CONFIG_FILE="${CONFIG_DIR}/server.toml"
DEFAULT_CONFIG="${REPO_ROOT}/config/server.toml"
EXAMPLE_CONFIG="${REPO_ROOT}/config/server.example.toml"

echo "[+] Building Loglumen server binary..."
if ! command -v cargo >/dev/null 2>&1; then
    echo "cargo is required but not installed. Install Rust toolchain first."
    exit 1
fi

pushd "${SERVER_DIR}" >/dev/null
cargo build --release
install -m 0755 target/release/loglumen-server "${BIN_PATH}"
popd >/dev/null

echo "[+] Ensuring configuration at ${CONFIG_FILE}"
mkdir -p "${CONFIG_DIR}"
if [[ -f "${CONFIG_FILE}" ]]; then
    echo "    Existing configuration detected; leaving it untouched."
else
    SOURCE_CONFIG="${DEFAULT_CONFIG}"
    if [[ ! -s "${SOURCE_CONFIG}" ]]; then
        SOURCE_CONFIG="${EXAMPLE_CONFIG}"
    fi
    cp "${SOURCE_CONFIG}" "${CONFIG_FILE}"
    chmod 600 "${CONFIG_FILE}"
fi

if [[ ! -f "${SERVICE_TEMPLATE}" ]]; then
    echo "Service template missing: ${SERVICE_TEMPLATE}"
    exit 1
fi

echo "[+] Installing systemd service to ${SERVICE_PATH}"
tmp_file="$(mktemp)"
sed \
    -e "s|__WORK_DIR__|${REPO_ROOT}|g" \
    -e "s|__BINARY_PATH__|${BIN_PATH}|g" \
    -e "s|__CONFIG_PATH__|${CONFIG_FILE}|g" \
    "${SERVICE_TEMPLATE}" > "${tmp_file}"
install -m 0644 "${tmp_file}" "${SERVICE_PATH}"
rm -f "${tmp_file}"

echo "[+] Enabling and starting loglumen-server.service"
systemctl daemon-reload
systemctl enable --now loglumen-server.service

echo "[✓] Loglumen server installed and running under systemd."
echo "    Binary: ${BIN_PATH}"
echo "    Config: ${CONFIG_FILE}"
