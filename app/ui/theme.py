from __future__ import annotations

WINDOW_BG = "#0f1115"
SIDEBAR_BG = "#15171b"
SURFACE = "#1b1e23"
SURFACE_RAISED = "#23272e"
BORDER = "#2a2e35"
TEXT = "#e6e8eb"
TEXT_MUTED = "#8b919a"
ACCENT = "#3b9c84"
ACCENT_HOVER = "#45ad93"
DANGER = "#c6656d"
BRAIN_COLOR = "#d6a968"
EXECUTOR_COLOR = "#68b69f"
USER_BUBBLE = "#2a2f37"
PENDING_COLOR = "#48515d"
ACTIVE_COLOR = "#d0a94f"
DONE_COLOR = "#4da785"

APPLICATION_STYLE = f"""
QWidget {{
    background: {WINDOW_BG};
    color: {TEXT};
    font-family: "Segoe UI";
    font-size: 13px;
}}
QMainWindow, QDialog {{ background: {WINDOW_BG}; }}
QLabel {{ background: transparent; }}
QFrame#section {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 6px;
}}
QLabel#appTitle {{ font-size: 20px; font-weight: 600; color: {TEXT}; }}
QLabel#appTitle[sidebar="true"] {{ font-size: 15px; }}
QLabel#sectionTitle {{ font-size: 14px; font-weight: 600; color: {TEXT}; }}
QLabel#muted {{ color: {TEXT_MUTED}; }}
QLabel#statusBadge {{
    background: {SURFACE_RAISED};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 9px;
    font-weight: 600;
}}
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QListWidget {{
    background: {SURFACE_RAISED};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 7px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{ border: 0; width: 24px; }}
QPushButton {{
    background: {SURFACE_RAISED};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 7px 12px;
    font-weight: 500;
}}
QPushButton:hover {{ background: {USER_BUBBLE}; border-color: {TEXT_MUTED}; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:disabled {{ color: {TEXT_MUTED}; background: {SURFACE}; border-color: {BORDER}; }}
QPushButton#primaryButton {{ background: {ACCENT}; border-color: {ACCENT}; color: {WINDOW_BG}; }}
QPushButton#primaryButton:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton#dangerButton {{ background: {DANGER}; border-color: {DANGER}; color: {WINDOW_BG}; }}
QPushButton#dangerButton:hover {{ border-color: {TEXT}; }}
QPushButton#toolButton {{ padding: 6px 9px; }}
QCheckBox {{ spacing: 7px; }}
QCheckBox::indicator {{ width: 15px; height: 15px; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; background: {SURFACE}; }}
QTabBar::tab {{
    background: {SIDEBAR_BG};
    border: 1px solid {BORDER};
    border-bottom: 0;
    padding: 8px 14px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{ background: {SURFACE_RAISED}; color: {TEXT}; border-top-color: {ACCENT}; }}
QHeaderView::section {{ background: {SURFACE_RAISED}; border: 0; border-bottom: 1px solid {BORDER}; padding: 7px; }}
QScrollBar:vertical {{ background: {SIDEBAR_BG}; width: 11px; }}
QScrollBar::handle:vertical {{ background: {USER_BUBBLE}; min-height: 28px; border-radius: 4px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QSplitter::handle {{ background: {BORDER}; }}
QToolTip {{ background: {SURFACE_RAISED}; color: {TEXT}; border: 1px solid {BORDER}; padding: 5px; }}

QWidget#sidebar {{ background: {SIDEBAR_BG}; border-right: 1px solid {BORDER}; }}
QLabel#historyHeading {{ color: {TEXT_MUTED}; font-size: 12px; }}
QPushButton#newTaskButton {{
    background: {SURFACE_RAISED};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 10px 12px;
    text-align: left;
}}
QPushButton#newTaskButton:hover {{ background: {USER_BUBBLE}; }}
QPushButton#sidebarButton {{ background: transparent; border: 0; text-align: left; }}
QPushButton#sidebarButton:hover {{ background: {SURFACE_RAISED}; }}
QListWidget#threadList {{ background: transparent; border: 0; padding: 0; }}
QListWidget#threadList::item {{ border-radius: 8px; padding: 8px 10px; }}
QListWidget#threadList::item:selected, QListWidget#threadList::item:hover {{ background: {SURFACE_RAISED}; }}
QWidget#threadItem {{ background: transparent; }}
QLabel#threadItemTitle {{ font-size: 13px; font-weight: 500; }}
QLabel#threadItemTime {{ color: {TEXT_MUTED}; font-size: 12px; }}

QWidget#chatArea {{ background: {WINDOW_BG}; }}
QFrame#userBubble {{ background: {USER_BUBBLE}; border-radius: 14px; padding: 10px 14px; }}
QLabel#roleLabel {{ font-weight: 600; font-size: 12px; }}
QLabel#roleLabel[role="brain"] {{ color: {BRAIN_COLOR}; }}
QLabel#roleLabel[role="executor"] {{ color: {EXECUTOR_COLOR}; }}
QFrame#stepCard {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; }}
QToolButton#stepHeader {{ background: transparent; border: 0; text-align: left; }}
QPlainTextEdit#stepLog {{
    background: {WINDOW_BG};
    border: 0;
    font-family: Consolas;
    font-size: 12px;
}}
QFrame#resultCard {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QLabel#resultStatus[status="passed"] {{ color: {ACCENT}; }}
QLabel#resultStatus[status="failed"] {{ color: {DANGER}; }}
QLabel#resultStatus[status="muted"] {{ color: {TEXT_MUTED}; }}
QLabel#emptyStateTitle {{ font-size: 22px; font-weight: 600; }}

QFrame#composer {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; }}
QFrame#composer[focused="true"] {{ border-color: {ACCENT}; }}
QFrame#composerHost, QScrollArea#composerScroll, QWidget#composerContent {{ background: transparent; border: 0; }}
QPlainTextEdit#composerInput {{ background: transparent; border: 0; padding: 4px; }}
QLabel#chipLabel {{ color: {TEXT_MUTED}; font-size: 12px; }}
QComboBox#chip, QSpinBox#chip {{
    background: {SURFACE_RAISED};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 12px;
}}
QPushButton#sendButton, QPushButton#stopButton {{
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    border: 0;
    border-radius: 16px;
    padding: 0;
    color: {WINDOW_BG};
}}
QPushButton#sendButton {{ background: {ACCENT}; }}
QPushButton#sendButton:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#stopButton {{ background: {DANGER}; }}
QPushButton#stopButton:hover {{ border: 1px solid {TEXT}; }}
QLabel#workspaceLabel {{ color: {TEXT_MUTED}; font-size: 12px; }}
QLineEdit#workspacePath {{ padding: 3px 8px; border-radius: 8px; }}

QWidget#headerBar {{ background: {WINDOW_BG}; border-bottom: 1px solid {BORDER}; }}
QLabel#threadTitle {{ font-size: 15px; font-weight: 600; }}
QLabel#phasePill {{ background: {SURFACE_RAISED}; border-radius: 10px; padding: 2px 10px; }}
"""
