#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Please run this script with sudo or as root."
    exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
AGENT_DIR="${REPO_ROOT}/agent"
SERVICE_TEMPLATE="${REPO_ROOT}/deploy/agent/loglumen-agent.service"
SERVICE_PATH="/etc/systemd/system/loglumen-agent.service"
PYTHON_BIN="$(command -v python3 || command -v python)"
CONFIG_DIR="/etc/loglumen"
CONFIG_FILE="${CONFIG_DIR}/agent.toml"
DEFAULT_CONFIG="${REPO_ROOT}/config/agent.toml"
EXAMPLE_CONFIG="${REPO_ROOT}/config/agent.example.toml"

if [[ -z "${PYTHON_BIN}" ]]; then
    echo "Python 3 is required but not found."
    exit 1
fi

echo "[+] Installing Python dependencies (if requirements.txt exists)"
if [[ -f "${AGENT_DIR}/requirements.txt" ]]; then
    "${PYTHON_BIN}" -m pip install -r "${AGENT_DIR}/requirements.txt"
fi

echo "[+] Deploying agent configuration to ${CONFIG_FILE}"
mkdir -p "${CONFIG_DIR}"
if [[ -f "${CONFIG_FILE}" ]]; then
    echo "    Existing agent config detected; leaving it untouched."
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

AGENT_ENTRY="${AGENT_DIR}/main.py"
if [[ ! -f "${AGENT_ENTRY}" ]]; then
    echo "Agent entry point not found: ${AGENT_ENTRY}"
    exit 1
fi

echo "[+] Installing systemd service to ${SERVICE_PATH}"
tmp_file="$(mktemp)"
sed \
    -e "s|__WORK_DIR__|${AGENT_DIR}|g" \
    -e "s|__PYTHON_BIN__|${PYTHON_BIN}|g" \
    -e "s|__AGENT_ENTRY__|${AGENT_ENTRY}|g" \
    -e "s|__CONFIG_PATH__|${CONFIG_FILE}|g" \
    "${SERVICE_TEMPLATE}" > "${tmp_file}"
install -m 0644 "${tmp_file}" "${SERVICE_PATH}"
rm -f "${tmp_file}"

echo "[+] Enabling and starting loglumen-agent.service"
systemctl daemon-reload
systemctl enable --now loglumen-agent.service

echo "[✓] Loglumen agent installed and running under systemd."
echo "    Config: ${CONFIG_FILE}"
