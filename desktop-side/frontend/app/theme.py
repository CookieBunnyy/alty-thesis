"""Abellar / Alty design system for the PyQt6 desktop application.

One place defines the visual language (dark charcoal + lime accent) shared
with the website (``website-side/frontend/src/index.css`` uses the same
token values):

* ``TOKENS``            – colour tokens
* ``global_stylesheet`` – QSS for standard widgets (tables, inputs, menus…)
* ``install``           – Fusion style, dark palette, global QSS, and a
  translator that maps the original light-green inline styles of every page
  onto the tokens by role (background / text / border). Pages keep their
  code and behaviour; only colours change.
"""

from __future__ import annotations

import re

from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QApplication, QWidget

DARK_TOKENS = {
    "bg": "#080B0D", "sidebar": "#0C1012", "card": "#111719", "card_2": "#151B1D",
    "input": "#0F1416", "hover": "#1A2224", "hover_2": "#222C2E", "row_alt": "#131A1C",
    "border": "#232B2E", "border_strong": "#2F393C",
    "text": "#F2F5F0", "text_muted": "#A3ADA6", "text_faint": "#6E7872",
    "accent": "#C7F000", "accent_hover": "#D6FF33", "accent_ink": "#0B0F10",
    "accent_soft": "#1F2A08", "accent_soft_2": "#2A3A0B",
    "success": "#3DD68C", "success_soft": "#0F2A1E", "warning": "#F5B83D", "warning_soft": "#2E2410",
    "danger": "#F0616D", "danger_soft": "#2E1316", "info": "#5AB4F0", "info_soft": "#0F2230",
    "disabled": "#2A3235", "chart_bar": "#E8ECE6", "login_glow": "#141C0A",
    # Login backdrop: deep charcoal-green gradient with soft lime light.
    "backdrop_top": "#0E1512", "backdrop_bottom": "#06090A", "backdrop_shape": "#C7F000",
    "backdrop_line": "#16201B", "shadow": "#000000",
}
# Light mode: white surfaces, dark text; the lime is deepened so it stays
# readable as text on white while buttons keep dark ink on lime.
LIGHT_TOKENS = {
    "bg": "#F4F6F2", "sidebar": "#FFFFFF", "card": "#FFFFFF", "card_2": "#F7F8F5",
    "input": "#FFFFFF", "hover": "#EEF1EA", "hover_2": "#E4E9DF", "row_alt": "#FAFBF8",
    "border": "#E1E5DC", "border_strong": "#CBD2C4",
    "text": "#111719", "text_muted": "#566158", "text_faint": "#879087",
    "accent": "#8DB600", "accent_hover": "#9FCC00", "accent_ink": "#0B0F10",
    "accent_soft": "#EEF6D6", "accent_soft_2": "#E1EFB8",
    "success": "#178A4E", "success_soft": "#E2F5EA", "warning": "#A86A0C", "warning_soft": "#FBF0DC",
    "danger": "#C9343F", "danger_soft": "#FBE4E6", "info": "#1F6FAE", "info_soft": "#E2EEF8",
    "disabled": "#E4E8E1", "chart_bar": "#CBD2C4", "login_glow": "#EEF6D6",
    # Login backdrop: soft neutral green tint (never plain white).
    "backdrop_top": "#E9EFE1", "backdrop_bottom": "#D6E1CA", "backdrop_shape": "#8DB600",
    "backdrop_line": "#CCD8BE", "shadow": "#3D4A33",
}
MODES = {"dark": DARK_TOKENS, "light": LIGHT_TOKENS}
THEME_SETTING = "theme"

# The active tokens. Mutated in place on a mode change so every module that
# imported TOKENS (or T) sees the new values.
TOKENS: dict[str, str] = dict(DARK_TOKENS)
T = TOKENS
_mode = "dark"
FONT_FAMILY = "Inter"
FONT_FALLBACKS = ["Inter", "Segoe UI Variable", "Segoe UI", "Arial"]

# Status badge colours (text, background), rebuilt for the active mode.
BADGES: dict[str, tuple[str, str]] = {}
_BACKGROUND_MAP: dict[str, str] = {}
_SIDEBAR_BACKGROUND: dict[str, str] = {}
_TEXT_MAP: dict[str, str] = {}
_BORDER_MAP: dict[str, str] = {}


def _rebuild_tables() -> None:
    """(Re)build badge colours and legacy-colour maps from the active tokens."""
    BADGES.clear()
    for statuses, (text, background) in (
        (("AVAILABLE", "SUCCESS", "ACTIVE", "COMPLETED", "GOOD"), ("success", "success_soft")),
        (("RESERVED",), ("accent", "accent_soft")),
        (("PROSPECT", "ACCEPTABLE", "ON_HOLD", "PENDING"), ("warning", "warning_soft")),
        (("PROCESSING", "SOLD"), ("info", "info_soft")),
        (("FAILED", "CANCELLED", "POOR", "INVALID"), ("danger", "danger_soft")),
        (("UNAVAILABLE", "INACTIVE", "ARCHIVED", "SUPERSEDED"), ("text_muted", "card_2")),
    ):
        for status in statuses:
            BADGES[status] = (T[text], T[background])

    # Legacy light-green palette -> tokens, by the role the colour plays.
    _BACKGROUND_MAP.clear()
    _BACKGROUND_MAP.update({
        "#eef3e5": T["bg"], "#f7f9f3": T["card"], "#ffffff": T["card_2"], "#fff": T["card_2"],
        "white": T["card_2"], "#f5f7f2": T["row_alt"], "#f9f6f2": T["card"], "#f5f3ee": T["card"],
        "#e7eedc": T["hover"], "#dce8ce": T["hover_2"], "#cfddc1": T["border_strong"],
        "#dcebd3": T["accent_soft_2"], "#d6e8c9": T["accent_soft_2"], "#c8dfb7": T["accent_soft_2"],
        "#e5efdc": T["accent_soft"], "#d8ecb6": T["accent_soft"], "#cddfc1": T["accent_soft_2"],
        "#e4ebdf": T["card_2"], "#edf2e7": T["card_2"], "#f1f5eb": T["input"], "#f0f5eb": T["hover"],
        "#edf3e7": T["hover"], "#eef3ee": T["hover"], "#e8ede3": T["border"], "#edf0eb": T["border"],
        "#f3ecd6": T["warning_soft"], "#f2dfdc": T["danger_soft"], "#d9e8ef": T["info_soft"],
        "#aeb8a7": T["disabled"], "#e5e7e3": T["card_2"], "#f0f0f0": T["card_2"], "#e8e8e8": T["card_2"],
        "#17310a": T["accent"], "#285214": T["accent_hover"], "#486b2a": T["accent"],
        "#294c16": T["accent"], "#1e4010": T["accent_hover"],
        "#e4eddb": T["card_2"], "#dee0dc": T["card_2"], "#d5e2ca": T["hover_2"],
        "#e8f0dc": T["accent_soft"], "#dcebf1": T["info_soft"], "#e4eff7": T["info_soft"],
        "#eef0ed": T["card_2"], "#fff3cd": T["warning_soft"], "#f8dedc": T["danger_soft"],
        "#edf0e9": T["input"], "#102406": T["accent_hover"], "#203b12": T["accent_hover"],
        "#b4b4b4": T["disabled"], "#aacc00": T["accent_hover"],
    })
    _SIDEBAR_BACKGROUND.clear()
    _SIDEBAR_BACKGROUND.update({"#17310a": T["sidebar"], "#285214": T["hover"]})
    _TEXT_MAP.clear()
    _TEXT_MAP.update({
        **{c: T["text"] for c in ("#17310a", "#17240f", "#26351f", "#294c16", "#314329", "#183c32",
                                  "#1f2a1a", "#2c3a25", "#f7f9f3", "#f1f5eb", "#edf5df", "#f3efe7")},
        **{c: T["text_muted"] for c in ("#65745b", "#60705a", "#526449", "#708064", "#a9b39f",
                                        "#71817a", "#b8c4ad", "#65755b")},
        "#9aa58f": T["text_faint"],
        **{c: T["accent"] for c in ("#486b2a", "#5d8138", "#6f9348", "#6b8e52", "#5d7d4e", "#285214")},
        "#9b3030": T["danger"], "#9b5555": T["danger"], "#9a6a13": T["warning"], "#9a874d": T["warning"],
        "#477489": T["info"], "#1d6384": T["info"], "#2f6f95": T["info"], "#8b4c85": T["info"],
        "#999999": T["text_faint"], "#9aa894": T["text_faint"], "#c8c8c8": T["text_faint"],
        "#dee0dc": T["text"], "#e0a0a0": T["danger"], "#607e49": T["accent"], "#2b4713": T["accent"],
    })
    _BORDER_MAP.clear()
    _BORDER_MAP.update({
        **{c: T["border"] for c in (
            "#d9e2d0", "#cbd8be", "#cbd5c4", "#cbd6c1", "#d4dccf", "#dfe7d5", "#d1ddc4", "#c9d5bb",
            "#e8ede3", "#edf0eb", "#d5dfcc", "#d8d8d8", "#c8c8c8", "#e8e8e8", "#dfe7df", "#ffffff",
            "#c9c2b9",
        )},
        **{c: T["accent"] for c in ("#6b8e52", "#5d7d4e", "#486b2a", "#17310a", "#294c16", "#b8d0a8",
                                    "#9eb78e", "#607e49", "#2b4713")},
        **{c: T["border_strong"] for c in ("#b9cdaa", "#aebca4", "#6b8058", "#b4b4b4", "#d4ddcc")},
    })


_rebuild_tables()


def current_mode() -> str:
    return _mode


def badge_colors(status: str | None) -> tuple[QColor, QColor]:
    text, background = BADGES.get(str(status or "").upper(), (T["text"], T["card_2"]))
    return QColor(text), QColor(background)


_HEX = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|\bwhite\b", re.IGNORECASE)
_RULE = re.compile(r"([^{}]*)\{([^{}]*)\}")


def _map_colors(value: str, table: dict[str, str]) -> str:
    return _HEX.sub(lambda m: table.get(m.group(0).casefold(), m.group(0)), value)


def _translate_declarations(block: str, selector: str) -> str:
    sidebar = bool(re.search(r"sidebar|navbrand|brand", selector, re.IGNORECASE))
    out: list[str] = []
    background_is_accent = False
    has_color = False
    for declaration in block.split(";"):
        if ":" not in declaration:
            if declaration.strip():
                out.append(declaration)
            continue
        prop, value = declaration.split(":", 1)
        name = prop.strip().casefold()
        if name in {"background", "background-color", "alternate-background-color",
                    "selection-background-color"}:
            table = {**_BACKGROUND_MAP, **_SIDEBAR_BACKGROUND} if sidebar else _BACKGROUND_MAP
            value = _map_colors(value, table)
            if name in {"background", "background-color"} and T["accent"].casefold() in value.casefold():
                background_is_accent = True
        elif name in {"color", "selection-color"}:
            value = _map_colors(value, _TEXT_MAP)
            has_color = name == "color" or has_color
        elif name.startswith("border") or name in {"outline", "gridline-color"}:
            value = _map_colors(value, _BORDER_MAP)
        out.append(f"{prop}:{value}")
    result = ";".join(out)
    if background_is_accent:
        # Lime surfaces always carry dark ink for contrast.
        if has_color:
            result = re.sub(r"(?<![-\w])color\s*:[^;]*", f"color: {T['accent_ink']}", result)
        else:
            result += f"; color: {T['accent_ink']}"
    return result


def translate_stylesheet(qss: str) -> str:
    """Map a legacy light stylesheet onto the Abellar dark tokens."""
    if not qss or "/*alty-raw*/" in qss:
        return qss
    if "{" not in qss:
        return _translate_declarations(qss, "")
    return _RULE.sub(lambda m: m.group(1) + "{" + _translate_declarations(m.group(2), m.group(1)) + "}", qss)


def translate_color(color: str) -> str:
    """Map a legacy icon/foreground colour string to its token."""
    key = str(color).casefold()
    if key in {"#ffffff", "white", "#fff"}:
        return T["accent_ink"]  # white icons sat on the old dark-green primary buttons
    return _TEXT_MAP.get(key, color)


# ---------------------------------------------------------------------------
# Global stylesheet for widgets without their own styling
# ---------------------------------------------------------------------------

def global_stylesheet() -> str:
    _TABLE_RULES = _table_rules()  # noqa: N806 - interpolated below
    return f"""/*alty-raw*/
* {{ font-family: "{FONT_FAMILY}", "Segoe UI Variable", "Segoe UI", Arial; }}
QWidget {{ color: {T['text']}; }}
QMainWindow, QDialog {{ background: {T['bg']}; }}
QDialog QLabel, QGroupBox, QCheckBox, QRadioButton {{ background: transparent; }}
QToolTip {{ background: {T['card_2']}; color: {T['text']}; border: 1px solid {T['border_strong']};
            border-radius: 6px; padding: 6px 8px; }}
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QComboBox {{
    background: {T['input']}; color: {T['text']}; border: 1px solid {T['border']};
    border-radius: 8px; padding: 6px 10px; min-height: 22px;
    selection-background-color: {T['accent']}; selection-color: {T['accent_ink']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus {{ border: 1px solid {T['accent']}; }}
QLineEdit:disabled, QComboBox:disabled {{ color: {T['text_faint']}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: {T['card_2']}; color: {T['text']};
    border: 1px solid {T['border_strong']}; selection-background-color: {T['accent_soft_2']};
    selection-color: {T['accent']}; outline: none; }}
QPushButton {{ background: {T['hover']}; color: {T['text']}; border: 1px solid {T['border']};
    border-radius: 8px; padding: 7px 14px; }}
QPushButton:hover {{ background: {T['hover_2']}; border-color: {T['border_strong']}; }}
QPushButton:pressed {{ background: {T['border_strong']}; }}
QPushButton:disabled {{ color: {T['text_faint']}; background: {T['card']}; }}
QPushButton:focus {{ outline: none; border: 1px solid {T['accent']}; }}
QTreeView, QTreeWidget, QListView, QListWidget {{
    background: {T['card']}; alternate-background-color: {T['row_alt']}; color: {T['text']};
    border: 1px solid {T['border']}; border-radius: 10px;
    selection-background-color: {T['accent_soft_2']}; selection-color: {T['text']}; outline: none;
}}
QTreeView::item, QListView::item {{ padding: 6px; border-bottom: 1px solid {T['border']}; }}
QTreeView::item:hover, QListView::item:hover {{ background: {T['hover']}; }}
QTreeView::item:selected, QListView::item:selected {{ background: {T['accent_soft_2']}; color: {T['text']}; }}
QHeaderView::section {{ background: {T['card_2']}; color: {T['text_muted']}; border: none;
    border-bottom: 1px solid {T['border']}; padding: 9px 8px; font-weight: 600; }}
{_TABLE_RULES}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {T['border_strong']}; border-radius: 4px; min-height: 28px; min-width: 28px; }}
QScrollBar::handle:hover {{ background: {T['text_faint']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollArea {{ background: transparent; border: none; }}
QMenu {{ background: {T['card_2']}; color: {T['text']}; border: 1px solid {T['border_strong']};
    border-radius: 8px; padding: 6px; }}
QMenu::item {{ padding: 7px 18px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {T['accent_soft_2']}; color: {T['accent']}; }}
QMenu::separator {{ height: 1px; background: {T['border']}; margin: 5px 8px; }}
QGroupBox {{ border: 1px solid {T['border']}; border-radius: 12px; margin-top: 14px;
    padding: 14px 12px 10px 12px; background: {T['card']}; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {T['text_muted']}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {T['border_strong']};
    background: {T['input']}; }}
QCheckBox::indicator:checked {{ background: {T['accent']}; border-color: {T['accent']}; }}
QTabWidget::pane {{ border: 1px solid {T['border']}; border-radius: 10px; background: {T['card']}; }}
QTabBar::tab {{ background: transparent; color: {T['text_muted']}; padding: 8px 14px; border: none; }}
QTabBar::tab:selected {{ color: {T['accent']}; border-bottom: 2px solid {T['accent']}; }}
QSplitter::handle {{ background: {T['border']}; }}
QProgressBar {{ background: {T['card_2']}; border: none; border-radius: 5px; height: 8px; text-align: center; }}
QProgressBar::chunk {{ background: {T['accent']}; border-radius: 5px; }}
"""


def _table_rules() -> str:
    return f"""
QTableView {{ background: {T['card']}; alternate-background-color: {T['card']}; color: {T['text']};
    border: 1px solid {T['border']}; border-radius: 12px; gridline-color: transparent; outline: 0;
    selection-background-color: {T['accent_soft']}; selection-color: {T['text']}; font-size: 13px; }}
QTableView::item {{ padding: 0 12px; border: none; border-bottom: 1px solid {T['border']}; }}
QTableView::item:hover {{ background: {T['hover']}; }}
QTableView::item:selected {{ background: {T['accent_soft']}; color: {T['text']}; }}
QTableView QHeaderView {{ background: transparent; border: none; }}
QTableView QHeaderView::section {{ background: {T['card']}; color: {T['text_faint']}; border: none;
    border-bottom: 1px solid {T['border']}; padding: 0 12px; min-height: 40px; }}
QTableView QHeaderView::section:hover {{ color: {T['text']}; }}
QTableView QHeaderView::section:first {{ border-top-left-radius: 12px; }}
QTableView QHeaderView::section:last {{ border-top-right-radius: 12px; }}
QTableCornerButton::section {{ background: {T['card']}; border: none; }}
"""


def table_stylesheet() -> str:
    """Modern table look (applied to every table by ``ui_polish``)."""
    return "/*alty-raw*/" + _table_rules()


def message_box_stylesheet() -> str:
    """QMessageBox in the active theme (raw: applied without translation)."""
    return f"""/*alty-raw*/
QMessageBox {{ background-color: {T['card']}; }}
QMessageBox QWidget {{ background-color: {T['card']}; color: {T['text']}; }}
QMessageBox QLabel {{ background-color: transparent; color: {T['text']}; font-size: 13px; }}
QMessageBox QTextEdit {{ background-color: {T['input']}; color: {T['text']}; border: 1px solid {T['border']};
    border-radius: 8px; }}
QMessageBox QPushButton {{
    background-color: {T['hover']}; color: {T['text']}; border: 1px solid {T['border']};
    border-radius: 8px; padding: 7px 16px; min-width: 76px; min-height: 28px; font-weight: 600;
}}
QMessageBox QPushButton:hover {{ background-color: {T['hover_2']}; }}
QMessageBox QPushButton:default {{ background-color: {T['accent']}; color: {T['accent_ink']};
    border-color: {T['accent']}; }}
QMessageBox QPushButton:default:hover {{ background-color: {T['accent_hover']}; }}
"""


def _palette() -> QPalette:
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: T["bg"], QPalette.ColorRole.WindowText: T["text"],
        QPalette.ColorRole.Base: T["card"], QPalette.ColorRole.AlternateBase: T["row_alt"],
        QPalette.ColorRole.Text: T["text"], QPalette.ColorRole.Button: T["hover"],
        QPalette.ColorRole.ButtonText: T["text"], QPalette.ColorRole.Highlight: T["accent"],
        QPalette.ColorRole.HighlightedText: T["accent_ink"], QPalette.ColorRole.ToolTipBase: T["card_2"],
        QPalette.ColorRole.ToolTipText: T["text"], QPalette.ColorRole.PlaceholderText: T["text_faint"],
        QPalette.ColorRole.Link: T["accent"], QPalette.ColorRole.BrightText: T["accent"],
        QPalette.ColorRole.Mid: T["border"], QPalette.ColorRole.Dark: T["sidebar"],
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(T["text_faint"]))
    return palette


_original_set_stylesheet = QWidget.setStyleSheet


def raw_set_stylesheet(widget: QWidget, qss: str) -> None:
    """Apply a stylesheet without token translation (already themed)."""
    _original_set_stylesheet(widget, qss)


def _themed_set_stylesheet(self: QWidget, qss: str) -> None:
    _original_set_stylesheet(self, translate_stylesheet(qss))


def saved_mode() -> str:
    from PyQt6.QtCore import QSettings

    mode = str(QSettings("Alty", "Desktop").value(THEME_SETTING, "dark") or "dark")
    return mode if mode in MODES else "dark"


def set_mode(mode: str, persist: bool = True) -> None:
    """Switch dark/light: tokens, maps, palette and global QSS.

    Widgets built *after* this call use the new colours; the controller
    rebuilds its windows so the switch is visible immediately.
    """
    global _mode
    if mode not in MODES:
        raise ValueError(f"Unknown theme mode {mode!r}")
    _mode = mode
    TOKENS.clear()
    TOKENS.update(MODES[mode])
    _rebuild_tables()
    app = QApplication.instance()
    if app is not None:
        app.setPalette(_palette())
        app.setStyleSheet(global_stylesheet())
    if persist:
        from PyQt6.QtCore import QSettings

        QSettings("Alty", "Desktop").setValue(THEME_SETTING, mode)


def load_fonts() -> None:
    """Register the bundled Inter weights (app/assets/fonts, SIL OFL)."""
    from pathlib import Path

    from PyQt6.QtGui import QFontDatabase

    for path in sorted((Path(__file__).parent / "assets" / "fonts").glob("Inter-*.ttf")):
        QFontDatabase.addApplicationFont(str(path))


def install(app: QApplication, mode: str | None = None) -> None:
    app.setStyle("Fusion")
    load_fonts()
    font = QFont()
    font.setFamilies(FONT_FALLBACKS)
    font.setPointSizeF(9.5)
    app.setFont(font)
    set_mode(mode or saved_mode(), persist=False)
    QWidget.setStyleSheet = _themed_set_stylesheet  # every inline style uses the tokens

    import qtawesome

    original_icon = qtawesome.icon

    def themed_icon(*names, **options):
        if "color" in options:
            options["color"] = translate_color(options["color"])
        return original_icon(*names, **options)

    qtawesome.icon = themed_icon
