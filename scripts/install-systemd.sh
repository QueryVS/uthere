#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${APP_DIR}/.venv"
SERVICE_FILE="/etc/systemd/system/uthere.service"
ENV_FILE="/etc/default/uthere"
BIN_FILE="/usr/local/bin/uthere"
DB_PATH="${UTHERE_DB:-/var/lib/uthere/uthere.db}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script with sudo: sudo scripts/install-systemd.sh" >&2
  exit 1
fi

SERVICE_USER="${SUDO_USER:-${USER}}"
SERVICE_GROUP="$(id -gn "${SERVICE_USER}")"

if ! python3 -m venv "${VENV_DIR}"; then
  cat >&2 <<'EOF'

Python virtualenv could not be created.

On Debian/Ubuntu, the usually missing packages are:
  sudo apt install python3-venv python3-full

You may need the version-specific package:
  sudo apt install python3.13-venv

Then run again:
  sudo scripts/install-systemd.sh

Do not run pip install directly against the system Python. PEP 668 may raise
the "externally-managed-environment" error.
EOF
  exit 1
fi
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -e "${APP_DIR}"

install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0755 "$(dirname "${DB_PATH}")"

cat > "${ENV_FILE}" <<EOF
UTHERE_DB=${DB_PATH}
UTHERE_SOCKET=/tmp/uthere.sock

# Alert channels: mail,telegram,whatsapp or a comma-separated combination.
# UTHERE_ALERT_CHANNELS=
# UTHERE_ALERT_MODE=on_change

# Mail SMTP:
# UTHERE_MAIL_HOST=smtp.example.com
# UTHERE_MAIL_PORT=587
# UTHERE_MAIL_TLS=starttls
# UTHERE_MAIL_USER=
# UTHERE_MAIL_PASSWORD=
# UTHERE_MAIL_FROM=uthere@example.com
# UTHERE_MAIL_TO=ops@example.com

# Telegram:
# UTHERE_TELEGRAM_BOT_TOKEN=
# UTHERE_TELEGRAM_CHAT_ID=

# WhatsApp Cloud API:
# UTHERE_WHATSAPP_TOKEN=
# UTHERE_WHATSAPP_PHONE_NUMBER_ID=
# UTHERE_WHATSAPP_TO=
# UTHERE_WHATSAPP_API_VERSION=v20.0
EOF

cat > "${BIN_FILE}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
if [[ -f /etc/default/uthere ]]; then
  set -a
  . /etc/default/uthere
  set +a
fi
exec "${VENV_DIR}/bin/uthere" "\$@"
EOF
chmod 0755 "${BIN_FILE}"

cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=uthere health check service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
EnvironmentFile=-/etc/default/uthere
ExecStart=/usr/local/bin/uthere serve
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now uthere.service

echo "uthere service installed and started."
echo "Status: systemctl status uthere"
echo "Logs: journalctl -u uthere -f"
echo "CLI: uthere list"
echo "Database: ${DB_PATH}"
