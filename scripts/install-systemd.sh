#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${APP_DIR}/.venv"

if ! python3 -m venv "${VENV_DIR}"; then
  cat >&2 <<'EOF'

Python virtualenv could not be created.

On Debian/Ubuntu, the usually missing packages are:
  su -c 'apt install python3-venv python3-full'

You may need the version-specific package:
  su -c 'apt install python3.13-venv'

Then run again:
  su -c 'cd /path/to/uthere && scripts/install-systemd.sh'

Do not run pip install directly against the system Python. PEP 668 may raise
the "externally-managed-environment" error.
EOF
  exit 1
fi
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install -e "${APP_DIR}"

if [[ "${EUID}" -ne 0 ]]; then
  USER_ENV_DIR="${HOME}/.config/uthere"
  USER_BIN_DIR="${HOME}/.local/bin"
  USER_STATE_DIR="${HOME}/.local/state/uthere"
  USER_ENV_FILE="${USER_ENV_DIR}/uthere.env"
  USER_BIN_FILE="${USER_BIN_DIR}/uthere"
  USER_DB_PATH="${UTHERE_DB:-${USER_STATE_DIR}/uthere.db}"
  USER_SOCKET_PATH="${UTHERE_SOCKET:-/tmp/uthere-${USER}.sock}"

  install -d -m 0755 "${USER_ENV_DIR}" "${USER_BIN_DIR}" "${USER_STATE_DIR}"

  cat > "${USER_ENV_FILE}" <<EOF
UTHERE_DB=${USER_DB_PATH}
UTHERE_SOCKET=${USER_SOCKET_PATH}

# Alert channels: mail,telegram,whatsapp or a comma-separated combination.
# UTHERE_ALERT_CHANNELS=
# UTHERE_ALERT_MODE=on_change
EOF

  cat > "${USER_BIN_FILE}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
if [[ -f "\${HOME}/.config/uthere/uthere.env" ]]; then
  set -a
  . "\${HOME}/.config/uthere/uthere.env"
  set +a
fi
exec "${VENV_DIR}/bin/uthere" "\$@"
EOF
  chmod 0755 "${USER_BIN_FILE}"

  echo "uthere user-mode CLI installed."
  echo "Binary: ${USER_BIN_FILE}"
  echo "Config: ${USER_ENV_FILE}"
  echo "Database: ${USER_DB_PATH}"
  echo "Socket: ${USER_SOCKET_PATH}"
  echo "This is not a background service. It only runs when you call uthere commands."
  echo "For continuous background checks, install system mode with: su -c 'cd /path/to/uthere && scripts/install-systemd.sh'"
  exit 0
fi

SERVICE_FILE="/etc/systemd/system/uthere.service"
ENV_FILE="/etc/default/uthere"
BIN_FILE="/usr/local/bin/uthere"
DB_PATH="${UTHERE_DB:-/var/lib/uthere/uthere.db}"
SERVICE_USER="${UTHERE_SERVICE_USER:-root}"
SERVICE_GROUP="$(id -gn "${SERVICE_USER}")"

install -d -o "${SERVICE_USER}" -g "${SERVICE_GROUP}" -m 0755 "$(dirname "${DB_PATH}")"
touch "${DB_PATH}"
chown "${SERVICE_USER}:${SERVICE_GROUP}" "${DB_PATH}"
chmod 0644 "${DB_PATH}"

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
echo "Service user: ${SERVICE_USER}"
if [[ "${SERVICE_USER}" == "root" ]]; then
  echo "Run CLI commands that write to the service database from a root shell, for example: su -c 'uthere list'"
fi
