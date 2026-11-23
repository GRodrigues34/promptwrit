"""Modern dark-slate Qt StyleSheet (QSS) for PromptWrit."""

from pathlib import Path

_CHECK_SVG = (Path(__file__).resolve().parent / "assets" / "check.svg").as_posix()

DARK_SLATE_QSS = """
QWidget {
    background-color: #0d1017;
    color: #d8dee9;
    font-family: "Inter", "Segoe UI", "Ubuntu", sans-serif;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #0d1017;
}

#headerTitle {
    font-size: 17px;
    font-weight: 700;
    color: #eceff4;
    background: transparent;
}

QPushButton#workspaceBtn, QPushButton#settingsBtn {
    background-color: #161c26;
    color: #d8dee9;
    border: 1px solid #2c3646;
    border-radius: 7px;
    padding: 6px 12px;
    font-weight: 500;
}

QPushButton#workspaceBtn:hover, QPushButton#settingsBtn:hover {
    background-color: #1f2735;
    border: 1px solid #5e81ac;
}

QGroupBox {
    background-color: #121720;
    border: 1px solid #2b3442;
    border-radius: 9px;
    margin-top: 10px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
    color: #8f9bb0;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    background-color: #0d1017;
}

QGroupBox#promptGroup {
    background-color: #0f141c;
    border: 1px solid #3c5f7a;
    color: #7eb2d6;
}

QPlainTextEdit#tagsLegend {
    background-color: transparent;
    border: none;
    color: #8b98ab;
    font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", monospace;
    font-size: 12px;
}

QPlainTextEdit#promptEditor {
    background-color: transparent;
    border: none;
    color: #e5e9f0;
    font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", monospace;
    font-size: 13px;
    selection-background-color: #2b4c7e;
    selection-color: #ffffff;
}

QListWidget#autocompletePopup {
    background-color: #161c26;
    border: 1px solid #3e526b;
    border-radius: 8px;
    padding: 4px;
    font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", monospace;
    font-size: 12px;
    outline: none;
}

QListWidget#autocompletePopup::item {
    padding: 6px 10px;
    border-radius: 5px;
    color: #d8dee9;
}

QListWidget#autocompletePopup::item:selected {
    background-color: #2b4c7e;
    color: #ffffff;
}

QLabel#footerBar {
    color: #6f7c8e;
    font-size: 12px;
    padding-top: 4px;
    background: transparent;
}

QLineEdit, QComboBox, QListWidget {
    background-color: #121720;
    border: 1px solid #2c3646;
    border-radius: 6px;
    padding: 6px 8px;
    color: #e5e9f0;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #5e81ac;
}

QPushButton {
    background-color: #1b222e;
    border: 1px solid #2e3847;
    border-radius: 6px;
    padding: 6px 14px;
    color: #e5e9f0;
}

QPushButton:hover {
    background-color: #242e3d;
    border: 1px solid #5e81ac;
}

QPushButton#primaryBtn {
    background-color: #2b5280;
    border: 1px solid #4c78a8;
    color: #ffffff;
    font-weight: 600;
}

QPushButton#primaryBtn:hover {
    background-color: #356399;
}

QCheckBox {
    spacing: 8px;
    color: #d8dee9;
}

QCheckBox::indicator {
    width: 17px;
    height: 17px;
    border-radius: 4px;
    border: 1px solid #3b4759;
    background-color: #121720;
}

QCheckBox::indicator:checked {
    background-color: #2e7d32;
    border: 1px solid #4caf50;
    image: url(__CHECK_SVG__);
}

QTableWidget {
    background-color: #10151d;
    alternate-background-color: #141a24;
    border: 1px solid #2c3646;
    border-radius: 7px;
    gridline-color: #1d2532;
    color: #d8dee9;
    selection-background-color: #223b5e;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #161d28;
    color: #8f9bb0;
    border: none;
    border-bottom: 1px solid #2c3646;
    padding: 6px 8px;
    font-weight: 600;
}
""".replace("__CHECK_SVG__", _CHECK_SVG)
