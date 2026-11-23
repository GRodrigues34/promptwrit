"""CLI entrypoint and single-instance daemon for PromptWrit desktop window."""

from __future__ import annotations

import argparse
import sys

from PySide6.QtGui import QAction, QIcon
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon

from promptwrit.app import PromptWritWindow

_SERVER_NAME = "promptwrit-single-instance"


def _notify_running_instance(cli_cwd: str | None) -> bool:
    """Send SHOW command to an existing PromptWrit instance. Returns True if delivered."""
    socket = QLocalSocket()
    socket.connectToServer(_SERVER_NAME)
    if not socket.waitForConnected(150):
        return False
    payload = f"SHOW:{cli_cwd or ''}\n".encode("utf-8")
    socket.write(payload)
    socket.flush()
    socket.waitForBytesWritten(200)
    socket.disconnectFromServer()
    return True


def _setup_tray(qt_app: QApplication, window: PromptWritWindow) -> QSystemTrayIcon | None:
    """Create a system tray icon with Open / Quit actions if supported."""
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None
    icon = qt_app.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)
    tray = QSystemTrayIcon(QIcon(icon), qt_app)
    tray.setToolTip("PromptWrit")

    menu = QMenu()
    open_act = QAction("Open PromptWrit", menu)
    open_act.triggered.connect(lambda: window.show_from_daemon())
    quit_act = QAction("Quit", menu)
    quit_act.triggered.connect(qt_app.quit)
    menu.addAction(open_act)
    menu.addSeparator()
    menu.addAction(quit_act)

    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: window.show_from_daemon()
        if reason == QSystemTrayIcon.ActivationReason.Trigger
        else None
    )
    tray.show()
    return tray


def main() -> None:
    """Parse CLI arguments and launch or signal the PromptWrit desktop window."""
    parser = argparse.ArgumentParser(
        prog="promptwrit",
        description="Modern dark-mode desktop launcher for composing structured XML prompts.",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="Workspace directory to index for #file autocomplete (defaults to git root or last used).",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Start hidden in the background for instantaneous Ctrl+' launch.",
    )
    args = parser.parse_args()

    qt_app = QApplication(sys.argv[:1])
    qt_app.setApplicationName("PromptWrit")

    if _notify_running_instance(args.cwd):
        sys.exit(0)

    # First instance: become the single-instance server + background daemon.
    QLocalServer.removeServer(_SERVER_NAME)
    server = QLocalServer(qt_app)
    server.listen(_SERVER_NAME)

    qt_app.setQuitOnLastWindowClosed(False)
    window = PromptWritWindow(cli_cwd=args.cwd, daemon_mode=True)

    def _on_new_connection() -> None:
        conn = server.nextPendingConnection()
        if conn is None:
            return
        conn.waitForReadyRead(150)
        raw = bytes(conn.readAll()).decode("utf-8", errors="ignore").strip()
        conn.close()
        if raw.startswith("SHOW"):
            cwd_arg = raw.split(":", 1)[1].strip() if ":" in raw else ""
            window.show_from_daemon(cwd_arg or None)

    server.newConnection.connect(_on_new_connection)
    _tray = _setup_tray(qt_app, window)

    if not args.daemon:
        window.show_from_daemon(args.cwd)

    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
