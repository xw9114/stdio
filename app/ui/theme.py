from __future__ import annotations

# Neutral graphite palette: layers are told apart by lightness rather than by
# borders or hue, so the only saturated colours on screen carry meaning
# (status, agent role, focus). Keep it that way when adding widgets.
SIDEBAR_BG = "#171717"
WINDOW_BG = "#212121"
SURFACE = "#282828"
SURFACE_RAISED = "#303030"
HOVER = "#383838"
BORDER = "#333333"
BORDER_STRONG = "#454545"
TEXT = "#ececec"
TEXT_MUTED = "#9a9a9a"
TEXT_FAINT = "#6b6b6b"

# Primary actions are near-white on dark, like the send button of most
# desktop agent apps; the blue accent is reserved for focus and selection.
PRIMARY = "#ececec"
PRIMARY_HOVER = "#ffffff"
PRIMARY_TEXT = "#171717"
ACCENT = "#7aa2f7"
ACCENT_HOVER = "#93b4f9"

DANGER = "#e5696b"
BRAIN_COLOR = "#d9a46c"
EXECUTOR_COLOR = "#6cc3c9"
USER_BUBBLE = "#303030"
PENDING_COLOR = "#4f4f4f"
ACTIVE_COLOR = "#e6b450"
DONE_COLOR = "#5fbf86"

APPLICATION_STYLE = f"""
QWidget {{
    background: {WINDOW_BG};
    color: {TEXT};
    font-family: "Segoe UI", "Microsoft YaHei UI";
    font-size: 13px;
}}
QMainWindow, QDialog {{ background: {WINDOW_BG}; }}
QLabel {{ background: transparent; }}
QFrame#section {{ background: transparent; border: 0; }}
QLabel#appTitle {{ font-size: 20px; font-weight: 600; color: {TEXT}; }}
QLabel#appTitle[sidebar="true"] {{ font-size: 14px; font-weight: 600; }}
QLabel#sectionTitle {{ font-size: 14px; font-weight: 600; color: {TEXT}; }}
QLabel#muted {{ color: {TEXT_MUTED}; }}
QLabel#statusBadge {{
    background: {SURFACE_RAISED};
    border: 0;
    border-radius: 6px;
    padding: 4px 9px;
    font-weight: 600;
}}

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QListWidget {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 8px;
    selection-background-color: {ACCENT};
    selection-color: {PRIMARY_TEXT};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{ border: 0; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_RAISED};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 4px;
    outline: 0;
    selection-background-color: {HOVER};
    selection-color: {TEXT};
}}

QPushButton {{
    background: {SURFACE_RAISED};
    border: 0;
    border-radius: 8px;
    padding: 7px 12px;
    font-weight: 500;
}}
QPushButton:hover {{ background: {HOVER}; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:disabled {{ color: {TEXT_FAINT}; background: {SURFACE}; }}
QPushButton#primaryButton {{ background: {PRIMARY}; color: {PRIMARY_TEXT}; }}
QPushButton#primaryButton:hover {{ background: {PRIMARY_HOVER}; }}
QPushButton#dangerButton {{ background: {DANGER}; color: {PRIMARY_TEXT}; }}
QPushButton#dangerButton:hover {{ background: #ee8284; }}
QPushButton#toolButton {{
    background: transparent;
    color: {TEXT_MUTED};
    border-radius: 6px;
    padding: 5px 10px;
}}
QPushButton#toolButton:hover {{ background: {SURFACE_RAISED}; color: {TEXT}; }}
QPushButton#toolButton:checked {{ background: {SURFACE_RAISED}; color: {TEXT}; }}

QCheckBox {{ spacing: 7px; color: {TEXT_MUTED}; background: transparent; }}
QCheckBox:hover {{ color: {TEXT}; }}
QCheckBox::indicator {{ width: 14px; height: 14px; }}

QTabWidget::pane {{ border: 0; border-top: 1px solid {BORDER}; background: {WINDOW_BG}; }}
QTabWidget::tab-bar {{ left: 8px; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    border: 0;
    border-bottom: 2px solid transparent;
    padding: 10px 12px 8px 12px;
}}
QTabBar::tab:hover {{ color: {TEXT}; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom-color: {TEXT}; }}
QHeaderView::section {{ background: {SURFACE}; border: 0; border-bottom: 1px solid {BORDER}; padding: 7px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER_STRONG}; min-height: 28px; border-radius: 3px; }}
QScrollBar::handle:horizontal {{ background: {BORDER_STRONG}; min-width: 28px; border-radius: 3px; }}
QScrollBar::handle:hover {{ background: #5a5a5a; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QToolTip {{ background: {SURFACE_RAISED}; color: {TEXT}; border: 1px solid {BORDER_STRONG}; padding: 5px; }}
QStatusBar {{ background: {SIDEBAR_BG}; color: {TEXT_FAINT}; border-top: 1px solid {BORDER}; font-size: 12px; }}
QStatusBar QLabel {{ color: {TEXT_FAINT}; }}

QWidget#sidebar {{ background: {SIDEBAR_BG}; }}
QWidget#sidebar QLabel, QWidget#sidebar QListWidget {{ background: transparent; }}
QLabel#historyHeading {{ color: {TEXT_FAINT}; font-size: 12px; font-weight: 600; }}
QPushButton#newTaskButton {{
    background: transparent;
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 8px 12px;
    text-align: left;
}}
QPushButton#newTaskButton:hover {{ background: {SURFACE}; }}
QPushButton#sidebarButton {{
    background: transparent;
    color: {TEXT_MUTED};
    border: 0;
    border-radius: 8px;
    padding: 7px 10px;
    text-align: left;
}}
QPushButton#sidebarButton:hover {{ background: {SURFACE}; color: {TEXT}; }}
QListWidget#threadList {{ background: transparent; border: 0; padding: 0; outline: 0; }}
QListWidget#threadList::item {{ border-radius: 8px; padding: 6px 8px; margin: 1px 0; }}
QListWidget#threadList::item:hover {{ background: {SURFACE}; }}
QListWidget#threadList::item:selected {{ background: {SURFACE_RAISED}; }}
QWidget#threadItem {{ background: transparent; }}
QLabel#threadItemTitle {{ font-size: 13px; }}
QLabel#threadItemTime {{ color: {TEXT_FAINT}; font-size: 11px; }}

QWidget#chatArea {{ background: {WINDOW_BG}; }}
QFrame#userBubble {{ background: {USER_BUBBLE}; border-radius: 16px; padding: 10px 14px; }}
QLabel#roleLabel {{ font-weight: 600; font-size: 12px; }}
QLabel#roleLabel[role="brain"] {{ color: {BRAIN_COLOR}; }}
QLabel#roleLabel[role="executor"] {{ color: {EXECUTOR_COLOR}; }}
QFrame#stepCard {{ background: transparent; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#stepCard:hover {{ border-color: {BORDER_STRONG}; }}
QToolButton#stepHeader {{ background: transparent; border: 0; text-align: left; color: {TEXT}; }}
QPlainTextEdit#stepLog {{
    background: {SIDEBAR_BG};
    border: 0;
    border-radius: 6px;
    color: {TEXT_MUTED};
    font-family: Consolas, "Microsoft YaHei UI";
    font-size: 12px;
}}
QFrame#resultCard {{ background: {SURFACE}; border: 0; border-radius: 12px; }}
QFrame#resultCard QPushButton#toolButton {{ background: {SURFACE_RAISED}; color: {TEXT}; }}
QFrame#resultCard QPushButton#toolButton:hover {{ background: {HOVER}; }}
QLabel#resultStatus {{ font-weight: 600; }}
QLabel#resultStatus[status="passed"] {{ color: {DONE_COLOR}; }}
QLabel#resultStatus[status="failed"] {{ color: {DANGER}; }}
QLabel#resultStatus[status="muted"] {{ color: {TEXT_MUTED}; }}
QLabel#emptyStateTitle {{ font-size: 24px; font-weight: 600; }}
QFrame#planCard {{ background: {SURFACE}; border: 1px solid {BORDER_STRONG}; border-radius: 12px; }}
QFrame#planCard QLabel, QFrame#planCard QCheckBox {{ background: transparent; }}
QLabel#planTitle {{ font-weight: 600; color: {ACTIVE_COLOR}; }}
QLabel#isolationNote {{ color: {ACTIVE_COLOR}; }}
QLabel#planRoute {{ color: {TEXT}; font-weight: 600; }}
QLabel#planSection {{ color: {TEXT_FAINT}; font-size: 12px; font-weight: 600; }}
QCheckBox#planTask {{ color: {TEXT}; }}
QCheckBox#planTask:disabled {{ color: {TEXT_MUTED}; }}
QPlainTextEdit#planNote {{ background: {WINDOW_BG}; }}

QFrame#composer {{ background: {SURFACE}; border: 1px solid {BORDER_STRONG}; border-radius: 18px; }}
QFrame#composer[focused="true"] {{ border-color: #5c5c5c; }}
QFrame#composer QLabel, QFrame#composer QCheckBox {{ background: transparent; }}
QFrame#composerHost, QScrollArea#composerScroll, QWidget#composerContent {{ background: transparent; border: 0; }}
QPlainTextEdit#composerInput {{ background: transparent; border: 0; padding: 4px; font-size: 14px; }}
QLabel#chipLabel {{ color: {TEXT_FAINT}; font-size: 12px; }}
QComboBox#chip, QSpinBox#chip {{
    background: transparent;
    border: 1px solid {BORDER_STRONG};
    border-radius: 13px;
    padding: 3px 10px;
    font-size: 12px;
    color: {TEXT_MUTED};
}}
QComboBox#chip:hover, QSpinBox#chip:hover {{ background: {SURFACE_RAISED}; color: {TEXT}; }}
QPushButton#sendButton, QPushButton#stopButton {{
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    border: 0;
    border-radius: 16px;
    padding: 0;
    color: {PRIMARY_TEXT};
}}
QPushButton#sendButton {{ background: {PRIMARY}; }}
QPushButton#sendButton:hover {{ background: {PRIMARY_HOVER}; }}
QPushButton#sendButton:disabled {{ background: {BORDER_STRONG}; }}
QPushButton#stopButton {{ background: {PRIMARY}; }}
QPushButton#stopButton:hover {{ background: {DANGER}; }}
QLabel#workspaceLabel {{ color: {TEXT_FAINT}; font-size: 12px; }}
QLineEdit#workspacePath {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 3px 6px;
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLineEdit#workspacePath:hover {{ border-color: {BORDER}; }}
QLineEdit#workspacePath:focus {{ border-color: {ACCENT}; color: {TEXT}; }}

QWidget#headerBar {{ background: {WINDOW_BG}; border-bottom: 1px solid {BORDER}; }}
QLabel#threadTitle {{ font-size: 14px; font-weight: 600; }}
QLabel#phasePill {{
    background: {SURFACE};
    color: {TEXT_MUTED};
    border-radius: 11px;
    padding: 3px 10px;
    font-size: 12px;
    max-height: 22px;
}}
"""
