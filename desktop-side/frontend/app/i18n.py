"""Interface language for the desktop app shell.

``tr("English text")`` returns the text in the selected language (falls back
to English). Covered: login window, sidebar, page titles, header, menus and
the Settings page. The choice is stored on this computer (QSettings) and
applied by rebuilding the windows, like the theme.
"""

from __future__ import annotations

from PyQt6.QtCore import QSettings

LANGUAGES = {"en": "English", "fil": "Filipino"}
SETTING = "language"

_FILIPINO = {
    # Navigation sections and pages
    "MAIN": "PANGUNAHIN",
    "INTELLIGENCE": "PAGSUSURI",
    "OPERATIONS": "OPERASYON",
    "Dashboard": "Dashboard",
    "Properties": "Mga Ari-arian",
    "Buyers & Sellers": "Mga Mamimili at Nagbebenta",
    "Transactions": "Mga Transaksyon",
    "Agents": "Mga Ahente",
    "Partners / Developers": "Mga Kasosyo / Developer",
    "Analytics": "Analitika",
    "Forecasting": "Pagtataya",
    "Decision Support": "Suporta sa Pagpapasya",
    "Digital Preview": "Digital na Preview",
    "Document Repository": "Imbakan ng Dokumento",
    "Workforce": "Mga Kawani",
    "Users & Access": "Mga User at Access",
    "Audit Logs": "Mga Audit Log",
    "Settings": "Mga Setting",
    "Property Operations": "Operasyon ng Ari-arian",
    # Header and menus
    "Search properties, clients, transactions, agents, documents… (press Enter)":
        "Maghanap ng ari-arian, kliyente, transaksyon, ahente, dokumento… (pindutin ang Enter)",
    "Type at least 2 characters, then press Enter": "Mag-type ng hindi bababa sa 2 titik, saka pindutin ang Enter",
    "Search all records": "Hanapin sa lahat ng tala",
    "Collapse / expand the sidebar": "Itago / ipakita ang sidebar",
    "Logout": "Mag-logout",
    "About": "Tungkol",
    "Switch to light mode": "Lumipat sa maliwanag na mode",
    "Switch to dark mode": "Lumipat sa madilim na mode",
    "Minimize": "I-minimize",
    "Maximize": "I-maximize",
    "Close": "Isara",
    # Settings page
    "System Settings": "Mga Setting ng Sistema",
    "Appearance": "Itsura",
    "Theme": "Tema",
    "Dark mode": "Madilim na mode",
    "Light mode": "Maliwanag na mode",
    "Language": "Wika",
    "Applies immediately and is remembered on this computer.": "Agad na ilalapat at tatandaan sa computer na ito.",
    "Choose your appearance and language.": "Piliin ang itsura at wika.",
    "Server configuration, storage, processing engines and synchronization state. Secrets are never shown.":
        "Konpigurasyon ng server, imbakan, mga processing engine at kalagayan ng synchronization. "
        "Hindi kailanman ipinapakita ang mga lihim na susi.",
    "Page contents stay in English; the menus, titles and this page follow your language.":
        "Nananatiling Ingles ang laman ng mga pahina; sumusunod sa iyong wika ang mga menu, pamagat at pahinang ito.",
    # Login window
    "Welcome back": "Maligayang pagbabalik",
    "Sign in to the Abellar Realty Management System.": "Mag-sign in sa Abellar Realty Management System.",
    "USERNAME": "USERNAME",
    "PASSWORD": "PASSWORD",
    "Stay signed in": "Manatiling naka-sign in",
    "Sign In": "Mag-sign In",
    "Signing in": "Nagsa-sign in",
    "Please enter both username and password.": "Pakilagay ang username at password.",
    "CAN'T SIGN IN?  v13.0.8": "HINDI MAKA-SIGN IN?  v13.0.8",
    # Notifications panel
    "Notifications": "Mga Abiso",
    "Mark all as read": "Markahang nabasa lahat",
    "All": "Lahat",
    "Unread": "Hindi pa nabasa",
    "You're all caught up": "Wala kang bagong abiso",
    "New alerts about documents, transactions, reviews and the system appear here.":
        "Dito lalabas ang mga bagong abiso tungkol sa dokumento, transaksyon, review at sistema.",
    "Could not load notifications": "Hindi ma-load ang mga abiso",
    "Generated from system records": "Galing sa mga rekord ng sistema",
    "Refresh": "I-refresh",
    "just now": "ngayon lang",
    # Dashboard greeting
    "Good morning": "Magandang umaga",
    "Good afternoon": "Magandang hapon",
    "Good evening": "Magandang gabi",
}

_TABLES = {"fil": _FILIPINO}
_language = "en"


def saved_language() -> str:
    value = str(QSettings("Alty", "Desktop").value(SETTING, "en") or "en")
    return value if value in LANGUAGES else "en"


def current_language() -> str:
    return _language


def set_language(code: str, persist: bool = True) -> None:
    global _language
    if code not in LANGUAGES:
        raise ValueError(f"Unknown language {code!r}")
    _language = code
    if persist:
        QSettings("Alty", "Desktop").setValue(SETTING, code)


def tr(text: str) -> str:
    return _TABLES.get(_language, {}).get(text, text)
