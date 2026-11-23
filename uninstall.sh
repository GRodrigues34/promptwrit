#!/usr/bin/env bash
set -euo pipefail

APP_NAME="PromptWrit"
BIN_NAME="promptwrit"
INSTALL_DIR="${HOME}/.local/bin"
DESKTOP_DIR="${HOME}/.local/share/applications"
CONFIG_DIR="${XDG_CONFIG_HOME:-${HOME}/.config}/${BIN_NAME}"

echo "==> Uninstalling ${APP_NAME}..."

if [[ -f "${INSTALL_DIR}/${BIN_NAME}" ]]; then
  rm -f "${INSTALL_DIR}/${BIN_NAME}"
  echo "    Removed ${INSTALL_DIR}/${BIN_NAME}"
fi

if [[ -f "${DESKTOP_DIR}/${BIN_NAME}.desktop" ]]; then
  rm -f "${DESKTOP_DIR}/${BIN_NAME}.desktop"
  echo "    Removed ${DESKTOP_DIR}/${BIN_NAME}.desktop"
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
