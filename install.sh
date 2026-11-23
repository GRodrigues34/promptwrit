#!/usr/bin/env bash
set -euo pipefail

APP_NAME="PromptWrit"
BIN_NAME="promptwrit"
INSTALL_BIN="${HOME}/.local/bin/${BIN_NAME}"
INSTALL_APP_DIR="${HOME}/.local/share/${BIN_NAME}"
DESKTOP_DIR="${HOME}/.local/share/applications"
AUTOSTART_DIR="${HOME}/.config/autostart"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing ${APP_NAME}..."
mkdir -p "${HOME}/.local/bin" "${INSTALL_APP_DIR}" "${DESKTOP_DIR}" "${AUTOSTART_DIR}"

# Stop any running daemon before replacing files
pkill -f "${INSTALL_APP_DIR}/${BIN_NAME}" >/dev/null 2>&1 || true

if [[ -d "${SCRIPT_DIR}/${BIN_NAME}" && -f "${SCRIPT_DIR}/${BIN_NAME}/${BIN_NAME}" ]]; then
  rm -rf "${INSTALL_APP_DIR:?}"/*
  cp -a "${SCRIPT_DIR}/${BIN_NAME}/." "${INSTALL_APP_DIR}/"
  ln -sf "${INSTALL_APP_DIR}/${BIN_NAME}" "${INSTALL_BIN}"
  chmod +x "${INSTALL_APP_DIR}/${BIN_NAME}"
  echo "    Installed prebuilt app to ${INSTALL_APP_DIR}"
elif [[ -f "${SCRIPT_DIR}/${BIN_NAME}" ]]; then
  cp "${SCRIPT_DIR}/${BIN_NAME}" "${INSTALL_APP_DIR}/${BIN_NAME}"
  ln -sf "${INSTALL_APP_DIR}/${BIN_NAME}" "${INSTALL_BIN}"
  chmod +x "${INSTALL_APP_DIR}/${BIN_NAME}"
  echo "    Installed prebuilt binary to ${INSTALL_APP_DIR}"
elif [[ -f "${SCRIPT_DIR}/pyproject.toml" ]]; then
  echo "    Building standalone app from source..."
  python3 -m venv "${SCRIPT_DIR}/.venv"
  "${SCRIPT_DIR}/.venv/bin/pip" install --quiet --upgrade pip
  "${SCRIPT_DIR}/.venv/bin/pip" install --quiet PySide6 pyperclip pyinstaller
  "${SCRIPT_DIR}/.venv/bin/pyinstaller" --noconfirm --onedir --windowed \
    --name "${BIN_NAME}" \
    --paths "${SCRIPT_DIR}/src" \
    --add-data "${SCRIPT_DIR}/src/promptwrit/assets/check.svg:promptwrit/assets" \
    --distpath "${SCRIPT_DIR}/dist" \
    --workpath "${SCRIPT_DIR}/build" \
    --specpath "${SCRIPT_DIR}/build" \
    "${SCRIPT_DIR}/src/promptwrit/__main__.py"
  rm -rf "${INSTALL_APP_DIR:?}"/*
  cp -a "${SCRIPT_DIR}/dist/${BIN_NAME}/." "${INSTALL_APP_DIR}/"
  ln -sf "${INSTALL_APP_DIR}/${BIN_NAME}" "${INSTALL_BIN}"
  chmod +x "${INSTALL_APP_DIR}/${BIN_NAME}"
  echo "    Built and installed app to ${INSTALL_APP_DIR}"
else
  echo "Error: Neither prebuilt '${BIN_NAME}' nor 'pyproject.toml' found in ${SCRIPT_DIR}." >&2
  exit 1
fi

# Check Qt6 X11 dependency on Debian/Ubuntu
if command -v dpkg >/dev/null 2>&1; then
  if ! dpkg -s libxcb-cursor0 >/dev/null 2>&1; then
    echo ""
    echo "Warning: 'libxcb-cursor0' is required by Qt6 on X11."
    echo "Run: sudo apt update && sudo apt install -y libxcb-cursor0"
  fi
fi

# Desktop entry
cat > "${DESKTOP_DIR}/${BIN_NAME}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=${APP_NAME}
Comment=Compose structured uppercase XML prompts
Exec=${INSTALL_BIN}
Terminal=false
Categories=Utility;Development;
EOF
echo "    Created desktop entry at ${DESKTOP_DIR}/${BIN_NAME}.desktop"

# Autostart background daemon for instantaneous Ctrl+' launch
cat > "${AUTOSTART_DIR}/${BIN_NAME}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=${APP_NAME} Daemon
Comment=Keep PromptWrit ready in the background for instant Ctrl+' launch
Exec=${INSTALL_BIN} --daemon
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
echo "    Enabled login autostart at ${AUTOSTART_DIR}/${BIN_NAME}.desktop"

# Register Ctrl+' global shortcut on GNOME
if command -v gsettings >/dev/null 2>&1; then
  SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
  KEY_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/promptwrit/"
  CURRENT="$(gsettings get "${SCHEMA}" custom-keybindings)"

  if [[ "${CURRENT}" == "@as []" || "${CURRENT}" == "[]" ]]; then
    UPDATED="['${KEY_PATH}']"
  elif [[ "${CURRENT}" == *"${KEY_PATH}"* ]]; then
    UPDATED="${CURRENT}"
  else
    UPDATED="${CURRENT%]}, '${KEY_PATH}']"
  fi

  gsettings set "${SCHEMA}" custom-keybindings "${UPDATED}"
  gsettings set "${SCHEMA}.custom-keybinding:${KEY_PATH}" name "${APP_NAME}"
  gsettings set "${SCHEMA}.custom-keybinding:${KEY_PATH}" command "${INSTALL_BIN}"
  gsettings set "${SCHEMA}.custom-keybinding:${KEY_PATH}" binding "<Primary>apostrophe"
  echo "    Configured GNOME global shortcut: Ctrl + '"
else
  echo "    Non-GNOME environment detected. Bind 'Ctrl + '' to: ${INSTALL_BIN}"
fi

# Start daemon immediately if graphical session is active
if [[ -n "${DISPLAY:-}" || -n "${WAYLAND_DISPLAY:-}" ]]; then
  nohup "${INSTALL_BIN}" --daemon >/dev/null 2>&1 &
  echo "    Started background daemon (instant Ctrl + ' ready)"
fi

echo ""
echo "Done! Press Ctrl + ' (or run '${INSTALL_BIN}') to launch ${APP_NAME}."
