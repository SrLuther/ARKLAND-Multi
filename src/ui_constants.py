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
from pathlib import Path
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


# ── Paleta de cores (legado — usada por app.py/pages) ─────────────────────────
_GREEN       = "#4ade80"    # green-400 (vivid)
_GREEN_DARK  = "#15803d"    # green-700
_GREEN_HOVER = "#14532d"    # green-900
_RED_DARK    = "#7f1d1d"    # red-900
_RED_HOVER   = "#450a0a"    # red-950
_BLUE        = "#1e3a5f"
_BLUE_HOVER  = "#102650"
_SIDEBAR_BG  = "#0a0f14"   # aligned with new theme
_CARD_BG     = "#0f172a"   # slate-900
_BG          = "#020617"   # deepest dark

# ── Temas por modo (PRIMITIVE = verde, TEK = teal/ciano) ─────────────────────
# Inspirado no design do ARKLAND SM (React/Tailwind) — adaptado para CustomTkinter
_THEMES: dict = {
    "primitive": {
        "accent":         "#4CAF50",
        "accent_dark":    "#2d7a3e",
        "accent_hover":   "#1f5c2d",
        "accent_label":   "#86efac",    # green-300
        "accent_muted_bg":"#052e16",    # green-950
        "rail_bg":        "#0a0f14",
        "tab_bar_bg":     "#0d1117",
        "sidebar_bg":     "#0a0f14",
        "card_bg":        "#0f172a",
        "card_border":    "#1e293b",
        "card_hover":     "#0d2a1a",
        "bg":             "#020617",
        "topbar_bg":      "#0a0f14",
        "separator":      "#1e293b",
        "text_primary":   "#e2e8f0",
        "text_secondary": "#94a3b8",
        "text_muted":     "#475569",
        "mode_label":     "PRIMITIVE",
        "mode_short":     "P",
    },
    "tek": {
        "accent":         "#22d3ee",    # cyan-400
        "accent_dark":    "#0e7490",    # cyan-700
        "accent_hover":   "#164e63",    # cyan-900
        "accent_label":   "#67e8f9",    # cyan-300
        "accent_muted_bg":"#083344",    # cyan-950
        "rail_bg":        "#0a0f1c",
        "tab_bar_bg":     "#0d1420",
        "sidebar_bg":     "#0a0f1c",
        "card_bg":        "#0f172a",
        "card_border":    "#1e293b",
        "card_hover":     "#0c2236",
        "bg":             "#020617",
        "topbar_bg":      "#0a0f1c",
        "separator":      "#1e293b",
        "text_primary":   "#e2e8f0",
        "text_secondary": "#94a3b8",
        "text_muted":     "#475569",
        "mode_label":     "TEK",
        "mode_short":     "T",
        "_is_light":      False,
    },
    "tek_light": {
        "accent":         "#0284c7",    # sky-600
        "accent_dark":    "#0369a1",    # sky-700
        "accent_hover":   "#bae6fd",    # sky-200
        "accent_label":   "#0369a1",    # sky-700
        "accent_muted_bg":"#e0f2fe",    # sky-100
        "rail_bg":        "#dde3ea",
        "tab_bar_bg":     "#f8fafc",    # slate-50
        "sidebar_bg":     "#dde3ea",
        "card_bg":        "#ffffff",
        "card_border":    "#cbd5e1",    # slate-300
        "card_hover":     "#e0f2fe",    # sky-100
        "bg":             "#f1f5f9",    # slate-100
        "topbar_bg":      "#dde3ea",
        "separator":      "#cbd5e1",    # slate-300
        "text_primary":   "#0f172a",    # slate-900
        "text_secondary": "#334155",    # slate-700
        "text_muted":     "#64748b",    # slate-500
        "mode_label":     "TEK LIGHT",
        "mode_short":     "TL",
        "_is_light":      True,
    },
}

# Modo ativo — alterado por _switch_mode() em app.py
_active_mode: str = "primitive"

# Variante TEK: "dark" | "light" — controlado por set_tek_variant()
_tek_variant: str = "dark"


def set_tek_variant(variant: str) -> None:
    """Define a variante de tema TEK ativa. variant: 'dark' ou 'light'."""
    global _tek_variant
    _tek_variant = "light" if variant == "light" else "dark"


def get_tek_variant() -> str:
    """Retorna a variante TEK ativa ('dark' ou 'light')."""
    return _tek_variant


def get_theme(mode: str | None = None) -> dict:
    """Retorna o dicionário de cores do modo ativo (ou do modo especificado).
    Se mode=='tek', respeita a variante ativa (_tek_variant).
    """
    resolved = mode or _active_mode
    if resolved == "tek" and _tek_variant == "light":
        return _THEMES["tek_light"]
    return _THEMES.get(resolved, _THEMES["primitive"])

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


def count_listplayers(response: str) -> int:
    """Conta jogadores na resposta RCON ListPlayers (ignora linhas de status)."""
    if not response or "no players" in response.lower():
        return 0
    return len(_parse_listplayers(response))


def read_ark_server_version(install_dir: str) -> str:
    """Versão do jogo (ex. 361.7) — ShooterGame.log ou version.txt."""
    if not install_dir or not str(install_dir).strip():
        return "—"
    root = Path(install_dir)
    log_path = root / "ShooterGame" / "Saved" / "Logs" / "ShooterGame.log"
    if log_path.is_file():
        try:
            with open(log_path, "rb") as fh:
                fh.seek(0, 2)
                size = fh.tell()
                fh.seek(max(0, size - 262144))
                tail = fh.read().decode("utf-8", errors="replace")
            for line in reversed(tail.splitlines()):
                if "ARK Version:" in line:
                    m = re.search(r"ARK Version:\s*([\d.]+)", line)
                    if m:
                        return m.group(1)
        except OSError:
            pass
    for rel in ("version.txt", "ShooterGame/Binaries/Win64/version.txt"):
        ver_path = root / rel
        if ver_path.is_file():
            try:
                text = ver_path.read_text(encoding="utf-8").strip()
                if text:
                    return text[:12]
            except OSError:
                pass
    return "—"


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
