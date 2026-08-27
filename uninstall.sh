#!/usr/bin/env bash
# =============================================================
# Little AI Bot - Standalone Uninstaller
# Usage:
#   sudo bash uninstall.sh
#   or:
#   bash <(curl -fsSL https://raw.githubusercontent.com/Mahersaber2024/little-ai-bot/main/uninstall.sh)
# =============================================================
set -uo pipefail

# ============================================================
# CONFIGURATION
# ============================================================
SERVICE_NAME="littleai-bot"
DEFAULT_INSTALL_DIR="/opt/littleai_bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
STATE_FILE="/etc/${SERVICE_NAME}.install_dir"

# ============================================================
# COLORS
# ============================================================
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    BLUE='\033[0;34m'
    MAGENTA='\033[0;35m'
    NC='\033[0m'
    BOLD='\033[1m'
else
    RED=''; GREEN=''; YELLOW=''; CYAN=''; BLUE=''; MAGENTA=''; NC=''; BOLD=''
fi

info(){ echo -e "${CYAN}ℹ️ $1${NC}"; }
ok(){ echo -e "${GREEN}✅ $1${NC}"; }
warn(){ echo -e "${YELLOW}⚠️ $1${NC}"; }
err(){ echo -e "${RED}❌ $1${NC}"; }
header(){ echo -e "${BLUE}${BOLD}═══════════════════════════════════════════════════${NC}"; }
title(){ echo -e "${MAGENTA}${BOLD}$1${NC}"; }

require_root(){
  if [[ $EUID -ne 0 ]]; then
    err "This script must be run with root privileges (using sudo or as root user)."
    exit 1
  fi
}

show_banner(){
  echo
  header
  title "  ██╗     ██╗████████╗████████╗██╗     ███████╗"
  title "  ██║     ██║╚══██╔══╝╚══██╔══╝██║     ██╔════╝"
  title "  ██║     ██║   ██║      ██║   ██║     █████╗  "
  title "  ██║     ██║   ██║      ██║   ██║     ██╔══╝  "
  title "  ███████╗██║   ██║      ██║   ███████╗███████╗"
  title "  ╚══════╝╚═╝   ╚═╝      ╚═╝   ╚══════╝╚══════╝"
  title "        Little AI Bot Uninstaller"
  header
  echo
}

ask(){
  # ask "Prompt text" "default_value" -> echoes the answer
  local prompt="$1" default="${2:-}" answer
  if [[ -n "$default" ]]; then
    read -rp "$prompt [$default]: " answer
    echo "${answer:-$default}"
  else
    read -rp "$prompt: " answer
    echo "$answer"
  fi
}

confirm(){
  # confirm "Prompt text" -> returns 0 for yes, 1 for no
  local prompt="$1" answer
  read -rp "$prompt [y/N]: " answer
  [[ "${answer,,}" == "y" || "${answer,,}" == "yes" ]]
}

# ============================================================
# MAIN
# ============================================================
show_banner
require_root

# --- Resolve install directory ---
if [[ -f "${STATE_FILE}" ]]; then
    INSTALL_DIR=$(cat "${STATE_FILE}")
else
    INSTALL_DIR="${DEFAULT_INSTALL_DIR}"
fi
INSTALL_DIR=$(ask "Installation directory to remove" "${INSTALL_DIR}")

# --- 1. Stop and remove the systemd service ---
header
info "Stopping and removing the systemd service..."
if systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
    systemctl stop "${SERVICE_NAME}" 2>/dev/null || true
    systemctl disable "${SERVICE_NAME}" 2>/dev/null || true
    rm -f "${SERVICE_FILE}"
    systemctl daemon-reload
    systemctl reset-failed 2>/dev/null || true
    ok "Service '${SERVICE_NAME}' stopped and removed."
else
    warn "Service '${SERVICE_NAME}' was not found, skipping."
fi

# --- 2. Optionally drop the PostgreSQL database/user ---
header
if command -v psql &>/dev/null && confirm "Drop the PostgreSQL database and user too?"; then
    DB_NAME=$(ask "Database name" "littleai_bot")
    DB_USER=$(ask "Database user" "littleai_user")

    sudo -u postgres psql -v ON_ERROR_STOP=0 -c "DROP DATABASE IF EXISTS ${DB_NAME};"
    sudo -u postgres psql -v ON_ERROR_STOP=0 -c "DROP ROLE IF EXISTS ${DB_USER};"
    ok "Database '${DB_NAME}' and user '${DB_USER}' removed."
else
    info "Keeping the PostgreSQL database and user (skipped)."
fi

# --- 3. Remove project files ---
header
if [[ -d "${INSTALL_DIR}" ]]; then
    if confirm "Delete project files at ${INSTALL_DIR}? (this also removes the .env file)"; then
        rm -rf "${INSTALL_DIR}"
        ok "Removed ${INSTALL_DIR}."
    else
        info "Keeping project files at ${INSTALL_DIR} (skipped)."
    fi
else
    warn "Install directory ${INSTALL_DIR} not found, skipping."
fi

# --- 4. Clean up state file ---
rm -f "${STATE_FILE}"

# --- Done ---
echo
header
ok "Uninstallation completed!"
info "If you kept the database or project files, remove them manually when ready."
header
