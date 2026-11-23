#!/usr/bin/env bash
set -euo pipefail

APP_NAME="PromptWrit"
BIN_NAME="promptwrit"
INSTALL_BIN="${HOME}/.local/bin/${BIN_NAME}"
INSTALL_APP_DIR="${HOME}/.local/share/${BIN_NAME}"
DESKTOP_DIR="${HOME}/.local/share/applications"
AUTOSTART_DIR="${HOME}/.config/autostart"
CONFIG_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/${BIN_NAME}"

echo "==> Uninstalling ${APP_NAME}..."

pkill -f "${INSTALL_APP_DIR}/${BIN_NAME}" >/dev/null 2>&1 || true

if [[ -L "${INSTALL_BIN}" || -f "${INSTALL_BIN}" ]]; then
  rm -f "${INSTALL_BIN}"
  echo "    Removed ${INSTALL_BIN}"
fi

if [[ -d "${INSTALL_APP_DIR}" ]]; then
  rm -rf "${INSTALL_APP_DIR}"
  echo "    Removed ${INSTALL_APP_DIR}"
fi

if [[ -f "${DESKTOP_DIR}/${BIN_NAME}.desktop" ]]; then
  rm -f "${DESKTOP_DIR}/${BIN_NAME}.desktop"
  echo "    Removed ${DESKTOP_DIR}/${BIN_NAME}.desktop"
fi

if [[ -f "${AUTOSTART_DIR}/${BIN_NAME}.desktop" ]]; then
  rm -f "${AUTOSTART_DIR}/${BIN_NAME}.desktop"
  echo "    Removed ${AUTOSTART_DIR}/${BIN_NAME}.desktop"
fi

if command -v gsettings >/dev/null 2>&1; then
  SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
  KEY_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/promptwrit/"
  CURRENT="$(gsettings get "${SCHEMA}" custom-keybindings)"

  if [[ "${CURRENT}" == *"${KEY_PATH}"* ]]; then
    UPDATED="$(python3 -c '
import ast, sys
items = ast.literal_eval(sys.argv[1].replace("@as ", ""))
filtered = [x for x in items if x != sys.argv[2]]
print(repr(filtered) if filtered else "@as []")
' "${CURRENT}" "${KEY_PATH}")"
    gsettings set "${SCHEMA}" custom-keybindings "${UPDATED}"
    gsettings reset-recursively "${SCHEMA}.custom-keybinding:${KEY_PATH}" || true
    echo "    Removed GNOME global shortcut (Ctrl + ')"
  fi
fi

if [[ "${1:-}" == "--purge" && -d "${CONFIG_DIR}" ]]; then
  rm -rf "${CONFIG_DIR}"
  echo "    Purged user config at ${CONFIG_DIR}"
elif [[ -d "${CONFIG_DIR}" ]]; then
  echo "    Kept user config at ${CONFIG_DIR} (pass --purge to remove)"
fi

echo ""
echo "Done! ${APP_NAME} has been uninstalled."
