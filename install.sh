#!/usr/bin/env bash
# =============================================================
# Little AI Bot - Standalone Installer
# Usage:
#   sudo bash install.sh
#   or:
#   bash <(curl -fsSL https://raw.githubusercontent.com/Mahersaber2024/little-ai-bot/main/install.sh)
# =============================================================
set -uo pipefail

# ============================================================
# CONFIGURATION
# ============================================================
SERVICE_NAME="littleai-bot"
DEFAULT_INSTALL_DIR="/opt/littleai_bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
STATE_FILE="/etc/${SERVICE_NAME}.install_dir"
PYTHON_BIN="python3"
REPO_URL="https://github.com/Mahersaber2024/little-ai-bot.git"

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
  title "        Little AI Bot Installer"
  header
  echo
}

ask(){
  local prompt="$1" default="${2:-}" answer
  if [[ -n "$default" ]]; then
    read -rp "$prompt [$default]: " answer
    echo "${answer:-$default}"
  else
    read -rp "$prompt: " answer
    echo "$answer"
  fi
}

ask_secret(){
  local prompt="$1" answer
  read -rsp "$prompt: " answer
  echo
  echo "$answer"
}

random_string(){
  tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24
}

# Run a short Python snippet inside the project's venv, from the install
# dir, with extra args available as sys.argv[1:]. Used everywhere below
# instead of writing values into an .env file — every setting the bot
# needs lives in config/bot_settings.json (see config/bot_settings.py).
run_py(){
    local script="$1"; shift
    (cd "${INSTALL_DIR}" && ./venv/bin/python - "$@" <<-PYEOF
${script}
PYEOF
    )
}

# ============================================================
# MAIN
# ============================================================
show_banner
require_root

# --- Install directory ---
INSTALL_DIR=$(ask "Installation directory" "${DEFAULT_INSTALL_DIR}")
echo "${INSTALL_DIR}" > "${STATE_FILE}"

# --- 1. System packages ---
header
info "Installing system dependencies (python3, venv, pip, postgresql, git)..."
if command -v apt-get &>/dev/null; then
    apt-get update -y
    apt-get install -y python3 python3-venv python3-pip postgresql postgresql-contrib git curl
elif command -v dnf &>/dev/null; then
    dnf install -y python3 python3-pip postgresql postgresql-server postgresql-contrib git curl
    postgresql-setup --initdb 2>/dev/null || true
else
    err "Unsupported package manager. Please install python3, postgresql and git manually."
    exit 1
fi
systemctl enable postgresql --now
ok "System dependencies installed."

# --- 2. Get the code ---
header
info "Setting up project files..."
if [[ -d "${INSTALL_DIR}/.git" ]]; then
    info "Existing installation found, pulling latest changes..."
    git -C "${INSTALL_DIR}" pull
elif [[ -f "./little_ai.py" ]]; then
    info "Copying local project files into ${INSTALL_DIR}..."
    mkdir -p "${INSTALL_DIR}"
    cp -r ./* "${INSTALL_DIR}/"
else
    info "Cloning repository into ${INSTALL_DIR}..."
    git clone "${REPO_URL}" "${INSTALL_DIR}"
fi
ok "Project files ready at ${INSTALL_DIR}."

# --- 3. Python virtual environment ---
header
info "Creating Python virtual environment..."
cd "${INSTALL_DIR}"
${PYTHON_BIN} -m venv venv
source venv/bin/activate
pip install --upgrade pip

if ! grep -qi "psycopg2" requirements.txt 2>/dev/null; then
    echo "psycopg2-binary" >> requirements.txt
fi

pip install -r requirements.txt
deactivate
ok "Virtual environment ready and dependencies installed."

# --- 4. PostgreSQL database ---
header
info "Setting up PostgreSQL database..."
DB_NAME=$(ask "Database name" "littleai_bot")
DB_USER=$(ask "Database user" "littleai_user")
DB_PASSWORD=$(ask_secret "Database password (leave empty to auto-generate)")
if [[ -z "$DB_PASSWORD" ]]; then
    DB_PASSWORD=$(random_string)
    warn "Auto-generated database password: ${DB_PASSWORD}"
fi
DB_HOST="localhost"
DB_PORT="5432"

sudo -u postgres psql -v ON_ERROR_STOP=0 <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_USER}') THEN
            CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';
        ELSE
            ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
        END IF;
    END
    \$\$;
EOSQL

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1 \
    || sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"
ok "Database '${DB_NAME}' and user '${DB_USER}' are ready."

header
info "Saving database credentials to config/bot_settings.json..."
run_py '
import sys
from config import bot_settings
host, port, name, user, password = sys.argv[1:6]
bot_settings.set_db_config(host=host, port=port, database=name, user=user, password=password)
' "${DB_HOST}" "${DB_PORT}" "${DB_NAME}" "${DB_USER}" "${DB_PASSWORD}"
ok "Database credentials saved."

# --- 5. Telegram bot token ---
# The token lives in config/bot_settings.json, so re-running this script
# on an existing install never wipes it out.
header
info "Telegram bot token..."

EXISTING_TOKEN=""
if [[ -f "${INSTALL_DIR}/venv/bin/python" ]]; then
    EXISTING_TOKEN=$(run_py '
import sys
sys.path.insert(0, ".")
try:
    from config import bot_settings
    print(bot_settings.get_bot_token())
except Exception:
    pass
' 2>/dev/null)
fi

if [[ -n "${EXISTING_TOKEN}" ]]; then
    ok "Bot token already configured — keeping it."
    BOT_TOKEN="${EXISTING_TOKEN}"
else
    BOT_TOKEN=""
    while [[ -z "${BOT_TOKEN}" ]]; do
        BOT_TOKEN=$(ask_secret "Bot token (from @BotFather)")
        [[ -z "${BOT_TOKEN}" ]] && warn "A bot token is required to start the bot."
    done
fi

header
info "Saving bot token to config/bot_settings.json..."
run_py '
import sys
from config import bot_settings
bot_settings.set_bot_token(sys.argv[1])
' "${BOT_TOKEN}"
ok "Bot token saved."

# --- 6. Owner admin(s) ---
# Seeded once here into bot_settings.json's owner_admin_ids. This is the
# fallback so the bot never ends up with no admin at all — it's not
# editable from /admin (see utils/permissions.py::is_owner_admin).
# Re-running the installer on an existing install shows the existing
# owner list as the default, rather than silently wiping it.
header
EXISTING_OWNERS=$(run_py '
from config import bot_settings
print(",".join(str(x) for x in bot_settings.get_owner_admin_ids()))
' 2>/dev/null)

ADMIN_USER_IDS=$(ask "Owner admin Telegram ID(s), comma-separated" "${EXISTING_OWNERS}")

info "Saving owner admin ID(s) to config/bot_settings.json..."
run_py '
import sys
from config import bot_settings
raw = sys.argv[1] if len(sys.argv) > 1 else ""
ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
bot_settings.set_owner_admin_ids(ids)
' "${ADMIN_USER_IDS}"
ok "Owner admin ID(s) saved."

info "Spotify isn't configured here — once the bot is running, set it from "
info "inside Telegram: /admin → 🎵 Spotify Settings."

# --- 7. systemd service ---
header
info "Creating systemd service..."
cat > "${SERVICE_FILE}" <<-EOF
[Unit]
Description=Little AI Telegram Bot
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/venv/bin/python ${INSTALL_DIR}/little_ai.py
Restart=on-failure
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"
ok "Service '${SERVICE_NAME}' created and started."

# --- Done ---
echo
header
ok "Installation completed!"
info "Check status with: systemctl status ${SERVICE_NAME}"
info "View logs with:    journalctl -u ${SERVICE_NAME} -f"
info "Install directory: ${INSTALL_DIR}"
info "All settings (DB, admins, bot token, Spotify) live in:"
info "  ${INSTALL_DIR}/config/bot_settings.json"
header
