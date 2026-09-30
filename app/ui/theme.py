APPLICATION_STYLE = r"""
QWidget {
    background: #171a1f;
    color: #d8dde5;
    font-family: "Segoe UI";
    font-size: 13px;
}
QMainWindow, QDialog { background: #14171b; }
QFrame#section {
    background: #1d2127;
    border: 1px solid #2c323a;
    border-radius: 6px;
}
QLabel#appTitle { font-size: 20px; font-weight: 600; color: #f2f5f7; }
QLabel#sectionTitle { font-size: 14px; font-weight: 600; color: #f0f3f5; }
QLabel#muted { color: #8e98a5; }
QLabel#statusBadge {
    background: #252b32;
    border: 1px solid #343c45;
    border-radius: 6px;
    padding: 5px 9px;
    font-weight: 600;
}
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QListWidget {
    background: #111419;
    border: 1px solid #343b44;
    border-radius: 5px;
    padding: 7px;
    selection-background-color: #356f62;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #4f9a87;
}
QComboBox::drop-down { border: 0; width: 24px; }
QPushButton {
    background: #292f36;
    border: 1px solid #3a424c;
    border-radius: 5px;
    padding: 7px 12px;
    font-weight: 500;
}
QPushButton:hover { background: #343c45; border-color: #4d5865; }
QPushButton:pressed { background: #20252b; }
QPushButton:disabled { color: #66717e; background: #20242a; border-color: #2b3037; }
QPushButton#primaryButton { background: #2f7d69; border-color: #459c85; color: #ffffff; }
QPushButton#primaryButton:hover { background: #378c76; }
QPushButton#dangerButton { background: #67373b; border-color: #875057; color: #ffe9eb; }
QPushButton#dangerButton:hover { background: #784047; }
QPushButton#toolButton { padding: 6px 9px; }
QCheckBox { spacing: 7px; }
QCheckBox::indicator { width: 15px; height: 15px; }
QTabWidget::pane { border: 1px solid #2c323a; background: #191d22; }
QTabBar::tab {
    background: #1a1e23;
    border: 1px solid #2c323a;
    border-bottom: 0;
    padding: 8px 14px;
    margin-right: 2px;
}
QTabBar::tab:selected { background: #252b31; color: #f1f4f6; border-top-color: #4f9a87; }
QHeaderView::section { background: #22272e; border: 0; border-bottom: 1px solid #343b44; padding: 7px; }
QScrollBar:vertical { background: #15181c; width: 11px; }
QScrollBar::handle:vertical { background: #3a424b; min-height: 28px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QSplitter::handle { background: #2b3138; }
QToolTip { background: #282e35; color: #f0f2f4; border: 1px solid #46505b; padding: 5px; }
"""

