#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${UTHERE_REPO_URL:-https://github.com/QueryVS/uthere.git}"
INSTALL_DIR="${UTHERE_INSTALL_DIR:-/opt/uthere}"
BRANCH="${UTHERE_BRANCH:-main}"

if [[ "${EUID}" -ne 0 ]]; then
  if [[ ! -f "$0" ]]; then
    echo "This installer was not started from a local file." >&2
    echo "Run it as root, for example: su -c 'curl -fsSL https://raw.githubusercontent.com/QueryVS/uthere/${BRANCH}/scripts/install.sh | bash'" >&2
    exit 1
  fi
  SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
  echo "This installer performs a root/systemd install."
  echo "Re-running with su..."
  repo_url_q="$(printf "%q" "${REPO_URL}")"
  install_dir_q="$(printf "%q" "${INSTALL_DIR}")"
  branch_q="$(printf "%q" "${BRANCH}")"
  script_q="$(printf "%q" "${SCRIPT_PATH}")"
  exec su -c "UTHERE_REPO_URL=${repo_url_q} UTHERE_INSTALL_DIR=${install_dir_q} UTHERE_BRANCH=${branch_q} bash ${script_q}"
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required to clone uthere." >&2
  exit 1
fi

if ! command -v make >/dev/null 2>&1; then
  echo "make is required to install uthere." >&2
  exit 1
fi

if [[ -d "${INSTALL_DIR}/.git" ]]; then
  git -C "${INSTALL_DIR}" fetch --tags origin
  git -C "${INSTALL_DIR}" checkout "${BRANCH}"
  git -C "${INSTALL_DIR}" pull --ff-only origin "${BRANCH}"
elif [[ -e "${INSTALL_DIR}" ]]; then
  echo "${INSTALL_DIR} already exists but is not a git repository." >&2
  exit 1
else
  install -d -m 0755 "$(dirname "${INSTALL_DIR}")"
  git clone --branch "${BRANCH}" "${REPO_URL}" "${INSTALL_DIR}"
fi

make -C "${INSTALL_DIR}" install-root
