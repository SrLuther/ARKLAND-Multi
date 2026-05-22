"""
Constantes de UI, paleta de cores, helpers globais e Tooltip.
Importado por app.py e demais módulos de dialogs/pages.
"""
from __future__ import annotations

import os
import re
import socket
import sys
import zipfile
from datetime import datetime, timezone, timedelta
from typing import Any, List

import tkinter as tk

try:
    import winreg as _winreg
except ImportError:
    _winreg = None  # type: ignore[assignment]

from .server_config import (
    SERVER_STATUS_STOPPED, SERVER_STATUS_STARTING, SERVER_STATUS_RUNNING,
    SERVER_STATUS_STOPPING, SERVER_STATUS_CRASHED, SERVER_STATUS_UPDATING,
)

# ── Fuso horário de Brasília (UTC-3 fixo — BR não usa horário de verão desde 2019)
_TZ_BRASILIA = timezone(timedelta(hours=-3))


def now_brasilia() -> datetime:
    """Retorna datetime atual no fuso de Brasília (naive, sem tzinfo)."""
    return datetime.now(tz=_TZ_BRASILIA).replace(tzinfo=None)


# ── Paleta de cores ────────────────────────────────────────────────────────────
_GREEN       = "#4CAF50"
_GREEN_DARK  = "#2d7a3e"
_GREEN_HOVER = "#1f5c2d"
_RED_DARK    = "#7a2d2d"
_RED_HOVER   = "#5c1f1f"
_BLUE        = "#1a3a6a"
_BLUE_HOVER  = "#102650"
_SIDEBAR_BG  = "#161622"
_CARD_BG     = "#1e1e30"
_BG          = "#111118"

_MAX_SYNC_CYCLES  = 5
_MAX_SYNC_FOLDERS = 5

# Fontes/cores nativas (tk.Label / tk.Frame) para formulários em scroll —
# evitam canvas por widget, reduzindo objetos de ~4 canvas/linha para ~1.
_FORM_FONT_BOLD = ("Segoe UI", 12, "bold")
_FORM_FONT_HINT = ("Segoe UI", 10)
_FORM_LABEL_FG  = "#a3a3bc"   # equivalente a gray65 no dark theme
_FORM_HINT_FG   = "#55556a"   # equivalente a gray40 no dark theme

_STATUS_COLOR = {
    SERVER_STATUS_STOPPED:  "#ff6666",
    SERVER_STATUS_STARTING: "#ffaa44",
    SERVER_STATUS_RUNNING:  _GREEN,
    SERVER_STATUS_STOPPING: "#ffaa44",
    SERVER_STATUS_CRASHED:  "#ff3333",
    SERVER_STATUS_UPDATING: "#ffaa44",
}
_STATUS_LABEL = {
    SERVER_STATUS_STOPPED:  "⬛ PARADO",
    SERVER_STATUS_STARTING: "🟡 INICIANDO",
    SERVER_STATUS_RUNNING:  "🟢 RODANDO",
    SERVER_STATUS_STOPPING: "🟡 PARANDO",
    SERVER_STATUS_CRASHED:  "🔴 TRAVADO",
    SERVER_STATUS_UPDATING: "🟡 ATUALIZANDO",
}

# Eventos oficiais ARK: Survival Evolved  (valor → rótulo exibido)
_ARK_OFFICIAL_EVENTS: List[tuple] = [
    ("",                     "(nenhum evento)"),
    ("FearEvolved",          "FearEvolved — Halloween 🎃"),
    ("WinterWonderland",     "WinterWonderland — Natal / Ano Novo 🎄"),
    ("TurkeyTrial",          "TurkeyTrial — Ação de Graças 🦃"),
    ("ARKEaster",            "ARKEaster — Páscoa / Primavera 🐣"),
    ("Summer",               "Summer — Festa de Verão ☀️"),
    ("LoveEvolved",          "LoveEvolved — Dia dos Namorados 💝"),
    ("Anniversary",          "Anniversary — Aniversário do ARK 🎂"),
    ("PAX",                  "PAX — Evento PAX Prime 🎮"),
    ("ExtinctionChronicles", "ExtinctionChronicles — Extinction Chronicles 🌍"),
    ("Genesis",              "Genesis — Evento Genesis 🧬"),
]
_ARK_EVENT_ID_TO_LABEL = {k: v for k, v in _ARK_OFFICIAL_EVENTS}
_ARK_EVENT_LABEL_TO_ID = {v: k for k, v in _ARK_OFFICIAL_EVENTS}


def _parse_listplayers(response: str) -> list:
    """Parseia a resposta do RCON ListPlayers em lista de dicts {name, steam_id}."""
    players = []
    for line in response.strip().splitlines():
        m = re.match(r"^\d+\.\s+(.+?),\s+(\d{15,})", line.strip())
        if m:
            players.append({"name": m.group(1).strip(), "steam_id": m.group(2).strip()})
    return players


# ── Helpers globais ────────────────────────────────────────────────────────────

def _set_windows_startup(enable: bool) -> None:
    if _winreg is None:
        return
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_key = "ARKLAND-ServerManager"
    try:
        if getattr(sys, "frozen", False):
            exe = sys.executable
        else:
            main_py = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py"
            )
            exe = f'"{sys.executable}" "{main_py}"'
        with _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, key_path, 0, _winreg.KEY_SET_VALUE) as key:
            if enable:
                _winreg.SetValueEx(key, app_key, 0, _winreg.REG_SZ, exe)
            else:
                try:
                    _winreg.DeleteValue(key, app_key)
                except FileNotFoundError:
                    pass
    except OSError:
        pass


def _resource_path(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, relative)


def _hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "PC"


def _safe_extract_zip(zf: "zipfile.ZipFile", dest: str) -> None:
    """Extrai membros de um ZIP validando paths para prevenir Zip Slip (CWE-22)."""
    dest_real = os.path.realpath(dest)
    for member in zf.infolist():
        target = os.path.realpath(os.path.join(dest_real, member.filename))
        if not target.startswith(dest_real + os.sep) and target != dest_real:
            raise ValueError(f"Membro inválido no ZIP (path traversal): {member.filename!r}")
        zf.extract(member, dest_real)


# ── Tooltip helper ────────────────────────────────────────────────────────────

class _Tooltip:
    """Tooltip flutuante com delay. Aparece ao passar o mouse sobre um widget."""

    def __init__(self, widget: Any, text: str, delay: int = 350) -> None:
        self._widget   = widget
        self._text     = text
        self._delay    = delay
        self._tip: Any = None
        self._job: Any = None
        widget.bind("<Enter>",       self._schedule, add="+")
        widget.bind("<Leave>",       self._hide,     add="+")
        widget.bind("<ButtonPress>", self._hide,     add="+")

    def _schedule(self, _event=None) -> None:
        self._cancel()
        self._job = self._widget.after(self._delay, self._show)

    def _cancel(self) -> None:
        if self._job:
            self._widget.after_cancel(self._job)
            self._job = None

    def _show(self) -> None:
        if self._tip:
            return
        x = self._widget.winfo_rootx() + self._widget.winfo_width() + 6
        y = self._widget.winfo_rooty()
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_attributes("-topmost", True)
        self._tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self._tip, text=self._text,
            justify="left",
            bg="#1a2030", fg="#c8dff8",
            relief="flat", bd=0,
            font=("Consolas", 10),
            padx=14, pady=10,
        ).pack()

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._tip:
            self._tip.destroy()
            self._tip = None
