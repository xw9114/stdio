from __future__ import annotations

# Light, quiet palette after the desktop agent apps the user pointed to: a
# warm off-white page, a slightly darker sidebar, white cards and inputs with
# hairline borders, near-black text. Saturated colour is kept for meaning
# only (status, agent role, focus).
SIDEBAR_BG = "#f4f4f3"
WINDOW_BG = "#fafaf9"
SURFACE = "#ffffff"
SURFACE_RAISED = "#f1f1f0"
HOVER = "#e8e8e6"
BORDER = "#e6e6e4"
BORDER_STRONG = "#d9d9d6"
TEXT = "#1c1c1c"
TEXT_MUTED = "#6f6f6d"
TEXT_FAINT = "#a1a19e"

# Primary actions are near-black with white text; blue only marks focus and
# selection.
PRIMARY = "#1c1c1c"
PRIMARY_HOVER = "#3a3a3a"
PRIMARY_TEXT = "#ffffff"
ACCENT = "#3b82f6"
ACCENT_HOVER = "#2563eb"

DANGER = "#d64545"
BRAIN_COLOR = "#b7791f"
EXECUTOR_COLOR = "#0f8b8d"
USER_BUBBLE = "#efefed"
PENDING_COLOR = "#c9c9c6"
ACTIVE_COLOR = "#d08c00"
DONE_COLOR = "#2f9e64"

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
QLabel#appTitle[sidebar="true"] {{
    font-family: Georgia, "Microsoft YaHei UI";
    font-size: 21px;
    font-weight: 700;
}}
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
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 6px 8px;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border-color: {ACCENT};
}}
QComboBox::drop-down {{ border: 0; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 4px;
    outline: 0;
    selection-background-color: {SURFACE_RAISED};
    selection-color: {TEXT};
}}

QPushButton {{
    background: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 6px 12px;
    font-weight: 500;
}}
QPushButton:hover {{ background: {SURFACE_RAISED}; }}
QPushButton:pressed {{ background: {HOVER}; }}
QPushButton:disabled {{ color: {TEXT_FAINT}; background: {SURFACE_RAISED}; border-color: {BORDER}; }}
QPushButton#primaryButton {{ background: {PRIMARY}; color: {PRIMARY_TEXT}; border-color: {PRIMARY}; }}
QPushButton#primaryButton:hover {{ background: {PRIMARY_HOVER}; border-color: {PRIMARY_HOVER}; }}
QPushButton#primaryButton:disabled {{ background: {BORDER_STRONG}; border-color: {BORDER_STRONG}; color: #ffffff; }}
QPushButton#dangerButton {{ background: {DANGER}; color: #ffffff; border-color: {DANGER}; }}
QPushButton#toolButton {{
    background: transparent;
    color: {TEXT_MUTED};
    border: 0;
    border-radius: 6px;
    padding: 5px 10px;
}}
QPushButton#toolButton:hover {{ background: {SURFACE_RAISED}; color: {TEXT}; }}
QPushButton#toolButton:checked {{ background: {SURFACE_RAISED}; color: {TEXT}; }}
QToolButton#iconButton {{ background: transparent; border: 0; border-radius: 6px; padding: 5px; }}
QToolButton#iconButton:hover {{ background: {HOVER}; }}

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
QHeaderView::section {{ background: {SURFACE_RAISED}; border: 0; border-bottom: 1px solid {BORDER}; padding: 7px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER_STRONG}; min-height: 28px; border-radius: 3px; }}
QScrollBar::handle:horizontal {{ background: {BORDER_STRONG}; min-width: 28px; border-radius: 3px; }}
QScrollBar::handle:hover {{ background: #c4c4c0; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}
QToolTip {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER_STRONG}; padding: 5px; }}
QStatusBar {{ background: {WINDOW_BG}; color: {TEXT_FAINT}; border: 0; font-size: 12px; }}
QStatusBar QLabel {{ color: {TEXT_FAINT}; }}

QWidget#sidebar {{ background: {SIDEBAR_BG}; }}
QWidget#sidebar QLabel, QWidget#sidebar QListWidget, QWidget#sidebar QWidget#threadItem {{ background: transparent; }}
QPushButton#navButton {{
    background: transparent;
    border: 0;
    border-radius: 8px;
    padding: 8px 10px;
    text-align: left;
    font-size: 14px;
    color: {TEXT};
}}
QPushButton#navButton:hover {{ background: {HOVER}; }}
QPushButton#navButton[active="true"] {{ background: {HOVER}; }}
QLabel#historyHeading {{ color: {TEXT_FAINT}; font-size: 13px; }}
QListWidget#threadList {{ background: transparent; border: 0; padding: 0; outline: 0; }}
QListWidget#threadList::item {{ border-radius: 8px; padding: 0; margin: 0; }}
QListWidget#threadList::item:hover {{ background: {HOVER}; }}
QListWidget#threadList::item:selected {{ background: {HOVER}; }}
QWidget#projectGroup {{ background: transparent; }}
QLabel#projectGroupName {{ font-size: 14px; color: {TEXT}; }}
QLabel#threadItemTitle {{ font-size: 13px; color: {TEXT}; }}
QLabel#threadItemTime {{ color: {TEXT_FAINT}; font-size: 12px; }}
QWidget#sidebarFooter {{ background: transparent; border-top: 1px solid {BORDER}; }}
QLabel#footerStatus {{ color: {TEXT_MUTED}; font-size: 12px; }}

QWidget#chatArea {{ background: {WINDOW_BG}; }}
QFrame#userBubble {{ background: {USER_BUBBLE}; border-radius: 16px; padding: 10px 14px; }}
QLabel#roleLabel {{ font-weight: 600; font-size: 12px; }}
QLabel#roleLabel[role="brain"] {{ color: {BRAIN_COLOR}; }}
QLabel#roleLabel[role="executor"] {{ color: {EXECUTOR_COLOR}; }}
QLabel#roleLabel[role="verify"] {{ color: {TEXT_MUTED}; font-weight: 500; }}
QFrame#stepCard {{ background: transparent; border: 0; border-radius: 8px; }}
QFrame#stepCard:hover {{ background: {SURFACE_RAISED}; }}
QFrame#stepCard[state="active"] {{ background: {SURFACE}; border: 1px solid {BORDER}; }}
QToolButton#stepHeader {{ background: transparent; border: 0; text-align: left; color: {TEXT}; padding: 2px 0; }}
QToolButton#stepHeader[state="done"] {{ color: {TEXT_MUTED}; }}
QToolButton#stepHeader[state="failed"] {{ color: {DANGER}; }}
QLabel#stepMeta {{ color: {TEXT_FAINT}; font-size: 12px; }}
QPlainTextEdit#stepLog {{
    background: {SURFACE_RAISED};
    border: 0;
    border-radius: 6px;
    color: {TEXT_MUTED};
    font-family: Consolas, "Microsoft YaHei UI";
    font-size: 12px;
}}
QFrame#resultCard {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#resultCard QLabel {{ background: transparent; }}
QLabel#resultStatus {{ font-weight: 600; }}
QLabel#resultStatus[status="passed"] {{ color: {DONE_COLOR}; }}
QLabel#resultStatus[status="failed"] {{ color: {DANGER}; }}
QLabel#resultStatus[status="muted"] {{ color: {TEXT_MUTED}; }}
QLabel#emptyStateTitle {{ font-size: 34px; font-weight: 700; color: {TEXT}; }}
QFrame#planCard {{ background: {SURFACE}; border: 1px solid {BORDER_STRONG}; border-radius: 12px; }}
QFrame#planCard QLabel, QFrame#planCard QCheckBox {{ background: transparent; }}
QLabel#planTitle {{ font-weight: 600; color: {ACTIVE_COLOR}; }}
QLabel#planRoute {{ color: {TEXT}; font-weight: 600; }}
QLabel#planSection {{ color: {TEXT_FAINT}; font-size: 12px; font-weight: 600; }}
QCheckBox#planTask {{ color: {TEXT}; }}
QCheckBox#planTask:disabled {{ color: {TEXT_MUTED}; }}
QPlainTextEdit#planNote {{ background: {WINDOW_BG}; }}
QLabel#isolationNote {{
    color: #9a6700;
    background: rgba(208, 140, 0, 0.12);
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 12px;
}}

QPushButton#contextChip {{
    background: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 4px 10px;
    font-size: 13px;
    font-weight: 400;
    color: {TEXT};
    text-align: left;
}}
QPushButton#contextChip:hover {{ background: {SURFACE_RAISED}; }}
QPushButton#contextChip:disabled {{ color: {TEXT_FAINT}; background: {SURFACE}; }}
QFrame#composer {{ background: {SURFACE}; border: 1px solid {BORDER_STRONG}; border-radius: 14px; }}
QFrame#composer[focused="true"] {{ border-color: #b9b9b5; }}
QFrame#composer QLabel, QFrame#composer QCheckBox {{ background: transparent; }}
QFrame#composerHost, QScrollArea#composerScroll, QWidget#composerContent {{ background: transparent; border: 0; }}
QPlainTextEdit#composerInput {{ background: transparent; border: 0; padding: 4px; font-size: 14px; }}
QLabel#chipLabel {{ color: {TEXT_MUTED}; font-size: 12px; }}
QComboBox#chip, QSpinBox#chip {{
    background: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: 8px;
    padding: 3px 10px;
    font-size: 12px;
    color: {TEXT};
}}
QComboBox#chip:hover, QSpinBox#chip:hover {{ background: {SURFACE_RAISED}; }}
QComboBox#flatChip {{
    background: transparent;
    border: 0;
    border-radius: 8px;
    padding: 5px 8px;
    font-size: 13px;
    color: {TEXT};
}}
QComboBox#flatChip:hover {{ background: {SURFACE_RAISED}; }}
QComboBox#flatChip::drop-down {{ width: 0; border: 0; }}
QPushButton#optionsButton {{
    background: transparent;
    color: {TEXT_MUTED};
    border: 0;
    border-radius: 8px;
    padding: 5px 8px;
    font-size: 13px;
    font-weight: 400;
    text-align: left;
}}
QPushButton#optionsButton:hover {{ background: {SURFACE_RAISED}; color: {TEXT}; }}
QPushButton#optionsButton:disabled {{ color: {TEXT_FAINT}; background: transparent; }}
QFrame#optionsPopup {{ background: {SURFACE}; border: 1px solid {BORDER_STRONG}; border-radius: 10px; }}
QFrame#optionsPopup QLabel, QFrame#optionsPopup QCheckBox {{ background: transparent; }}
QPushButton#sendButton, QPushButton#stopButton {{
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    border: 0;
    border-radius: 16px;
    padding: 0;
}}
QPushButton#sendButton {{ background: {PRIMARY}; }}
QPushButton#sendButton:hover {{ background: {PRIMARY_HOVER}; }}
QPushButton#sendButton:disabled {{ background: {BORDER_STRONG}; }}
QPushButton#stopButton {{ background: {PRIMARY}; }}
QPushButton#stopButton:hover {{ background: {DANGER}; }}

QWidget#headerBar {{ background: {WINDOW_BG}; border: 0; }}
QLabel#threadTitle {{ font-size: 14px; font-weight: 600; }}
QLabel#phasePill {{
    background: {SURFACE_RAISED};
    color: {TEXT_MUTED};
    border-radius: 11px;
    padding: 3px 10px;
    font-size: 12px;
    max-height: 22px;
}}
"""
