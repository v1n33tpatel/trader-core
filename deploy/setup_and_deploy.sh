#!/usr/bin/env bash
# ==============================================================================
# MoneyMakingMachine (trader-core) — Production Deployment Script
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "================================================================================"
echo "   MONEYMAKINGMACHINE (trader-core) — PRODUCTION DEPLOYMENT"
echo "================================================================================"

# 1. Host Persistent Directories
DATA_DIR="/var/lib/trader-core/data"
CONFIG_DIR="/etc/trader-core"

echo "[1/5] Ensuring persistent host directories..."
if [ "$(id -u)" -eq 0 ]; then
    mkdir -p "${DATA_DIR}" "${CONFIG_DIR}"
    if [ -f "${PROJECT_ROOT}/.env" ]; then
        cp -f "${PROJECT_ROOT}/.env" "${CONFIG_DIR}/.env"
        chmod 600 "${CONFIG_DIR}/.env"
        echo "   ✓ Synced .env to ${CONFIG_DIR}/.env"
    fi
else
    echo "   Note: Non-root execution. Ensuring local data dir fallback..."
    mkdir -p "${PROJECT_ROOT}/data"
fi

# Load environment variables (such as OPEN_WEBUI_API_KEY)
if [ -f "${CONFIG_DIR}/.env" ]; then
    set -a
    . "${CONFIG_DIR}/.env"
    set +a
elif [ -f "${PROJECT_ROOT}/.env" ]; then
    set -a
    . "${PROJECT_ROOT}/.env"
    set +a
fi

# 2. Build Container Image
echo "[2/5] Building Podman container image (localhost/trader-core:latest)..."
if command -v podman >/dev/null 2>&1; then
    if podman build --network=host -t localhost/trader-core:latest -f "${PROJECT_ROOT}/Containerfile" "${PROJECT_ROOT}"; then
        echo "   ✓ Image built successfully."
    else
        echo "   ⚠ Podman build failed. Review output above."
    fi
else
    echo "   ⚠ Podman binary not found in PATH. Skipping container build."
fi

# 3. Install Systemd Quadlets
echo "[3/5] Installing Systemd Podman Quadlets..."
if [ "$(id -u)" -eq 0 ]; then
    QUADLET_DEST="/etc/containers/systemd"
    mkdir -p "${QUADLET_DEST}"
    cp "${SCRIPT_DIR}/trader-dashboard-podman.container" "${QUADLET_DEST}/trader-dashboard.container"
    cp "${SCRIPT_DIR}/trader-engine-podman.container" "${QUADLET_DEST}/trader-engine.container"
    systemctl daemon-reload
    echo "   ✓ Quadlets installed in ${QUADLET_DEST} and systemd reloaded."
    echo "   Run: systemctl start trader-dashboard && systemctl start trader-engine"
else
    USER_QUADLET_DEST="${HOME}/.config/containers/systemd"
    mkdir -p "${USER_QUADLET_DEST}" 2>/dev/null || true
    if cp "${SCRIPT_DIR}/trader-dashboard-podman.container" "${USER_QUADLET_DEST}/trader-dashboard.container" 2>/dev/null; then
        cp "${SCRIPT_DIR}/trader-engine-podman.container" "${USER_QUADLET_DEST}/trader-engine.container" 2>/dev/null || true
        if command -v systemctl >/dev/null 2>&1; then
            systemctl --user daemon-reload 2>/dev/null || true
        fi
        echo "   ✓ Quadlets installed in ${USER_QUADLET_DEST}"
    else
        echo "   ⚠ Could not write to ${USER_QUADLET_DEST} (read-only or non-root sandbox)."
        echo "   Quadlet definitions are ready in ${SCRIPT_DIR}/ for host deployment."
    fi
fi

# 4. Open-WebUI Workspace Provisioning
echo "[4/5] Executing Open-WebUI Automated Provisioning..."
if [ -f "${PROJECT_ROOT}/.venv/bin/python" ]; then
    "${PROJECT_ROOT}/.venv/bin/python" "${SCRIPT_DIR}/provision_openwebui.py" \
        --url "http://192.168.2.15:8080" \
        --fast "llama3.1:8b" \
        --deep "deepseek-r1:14b" \
        --non-interactive || {
            echo "   ⚠ Live Open-WebUI provisioning skipped or host unreachable."
            echo "   You can run it anytime via the Web Terminal or CLI."
        }
fi

echo "================================================================================"
echo "   DEPLOYMENT SETUP COMPLETE"
echo "================================================================================"
echo "To start services locally without Podman:"
echo "   ./.venv/bin/python main.py        # Starts Dashboard on :5000"
echo "   ./.venv/bin/python engine.py      # Starts Autonomous Engine"
echo "================================================================================"
