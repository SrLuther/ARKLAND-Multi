"""
Interface gráfica principal do ARKLAND - Server Manager.
"""
from __future__ import annotations

import io
import json
import os
import socket
import sys
import threading
import tkinter as tk
import urllib.parse
import urllib.request
import re
import uuid
import webbrowser
import zipfile
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Dict, List, Optional

try:
    import winreg as _winreg
except ImportError:
    _winreg = None  # type: ignore[assignment]

try:
    import pystray  # type: ignore[reportMissingImports]
    from PIL import Image as _PILImage  # type: ignore[reportMissingImports]
    _PYSTRAY_OK = True
except ImportError:
    pystray = None  # type: ignore[assignment]
    _PILImage = None  # type: ignore[assignment]
    _PYSTRAY_OK = False

import customtkinter as ctk  # type: ignore[reportMissingImports]

from .config_manager import ConfigManager
from .sync_engine import SyncEngine
from .server_config import (
    ServerConfig,
    ARK_MAPS, ARK_MAP_NAMES,
    SERVER_STATUS_STOPPED, SERVER_STATUS_STARTING, SERVER_STATUS_RUNNING,
    SERVER_STATUS_STOPPING, SERVER_STATUS_CRASHED, SERVER_STATUS_UPDATING,
)
from .server_manager import ServerManager
from .mod_manager import ModManager
from .ark_ini import ArkIniManager
from .rcon_client import RconClient, RconError
from .updater import UpdateChecker
from .mod_auto_updater import ModAutoUpdater
from .buff_manager import (
    BuffManager, BuffEvent, BuffPreset, BuffRates,
    BUFF_TYPE_XP, BUFF_TYPE_DOMA, BUFF_TYPE_BREEDING, BUFF_TYPE_FARM,
    BUFF_TYPE_LABELS, BUFF_RATE_FIELDS, QUICK_PRESETS,
    BUFF_STATUS_ACTIVE, BUFF_STATUS_SCHEDULED, BUFF_STATUS_FINISHED,
    BUFF_STATUS_CANCELLED, BUFF_MAX_DAYS,
)
from .version import APP_VERSION, BUILD_DATE, CHANGELOG

APP_NAME = "ARKLAND - Server Manager"

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
    ("",                    "(nenhum evento)"),
    ("FearEvolved",         "FearEvolved — Halloween 🎃"),
    ("WinterWonderland",    "WinterWonderland — Natal / Ano Novo 🎄"),
    ("TurkeyTrial",         "TurkeyTrial — Ação de Graças 🦃"),
    ("ARKEaster",           "ARKEaster — Páscoa / Primavera 🐣"),
    ("Summer",              "Summer — Festa de Verão ☀️"),
    ("LoveEvolved",         "LoveEvolved — Dia dos Namorados 💝"),
    ("Anniversary",         "Anniversary — Aniversário do ARK 🎂"),
    ("PAX",                 "PAX — Evento PAX Prime 🎮"),
    ("ExtinctionChronicles","ExtinctionChronicles — Extinction Chronicles 🌍"),
    ("Genesis",             "Genesis — Evento Genesis 🧬"),
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
            raise ValueError(f"Membro inv�lido no ZIP (path traversal): {member.filename!r}")
        zf.extract(member, dest_real)


# ══════════════════════════════════════════════════════════════════════════════
class ARKServerManagerApp(ctk.CTk):

    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self.title(f"{APP_NAME}  v{APP_VERSION}")
        self.geometry("1280x780")
        self.minsize(1000, 640)

        # Ícone
        try:
            self.iconbitmap(_resource_path(os.path.join("ig", "ArkLandBR.ico")))
        except Exception:
            try:
                from PIL import Image, ImageTk  # type: ignore[reportMissingImports]
                _pil = Image.open(_resource_path(os.path.join("ig", "ArkLandBR.png"))).resize((32, 32))
                self._app_icon = ImageTk.PhotoImage(_pil)
                self.iconphoto(True, self._app_icon)
            except Exception:
                pass

        # ── Gerenciadores ────────────────────────────────────────────────────
        self.config_manager = ConfigManager()

        self.server_manager = ServerManager(
            on_status_change=self._on_server_status_change,
            on_log=self._on_server_log,
            on_visibility_change=self._on_server_visibility_change,
        )
        self.mod_manager = ModManager(
            steamcmd_path=self.config_manager.config.steamcmd_path,
            on_log=lambda m, level: self._global_log(m, level),
        )
        self.update_checker = UpdateChecker(on_log=lambda m, level: self._global_log(m, level))

        # Carrega servidores salvos no ServerManager
        for srv in self.config_manager.servers:
            self.server_manager.add_server(srv)

        # ── Estado UI ────────────────────────────────────────────────────────
        self._frames: Dict[str, Any] = {}
        self._server_frames: Dict[str, ctk.CTkFrame] = {}
        self._server_widgets: Dict[str, Dict[str, Any]] = {}
        self._rcon_clients: Dict[str, RconClient] = {}
        self._current_frame: str = "dashboard"
        self._sidebar_server_btns: Dict[str, ctk.CTkButton] = {}
        self._global_log_buf: List[str] = []
        self._tray_icon: Any = None
        self._sync_engine: Optional[SyncEngine] = None
        # widgets do painel sync (referenciados fora de _build_sync_panel)
        self._sync_log_box: Any = None
        self._sync_status_lbl: Any = None
        self._sync_stats_lbl: Any = None
        self._sync_toggle_btn: Any = None
        self._sync_cycles_frame: Any = None
        self._sync_cycle_vars: list = []
        self._sync_add_cycle_btn: Any = None
        # auto-update de mods
        self._mod_auto_updater: Optional[ModAutoUpdater] = None
        self._auto_updater_log_box: Any = None

        # BUFFs
        self._buff_manager: Optional[BuffManager] = None
        self._buffs_body_frame: Any = None          # frame reconstruído no refresh
        self._buffs_server_var: Any = None           # StringVar servidor selecionado

        self._build_ui()
        self.after(500, self._auto_start_sync)
        self.after(4000, self._check_updates_on_start)
        self.after(2000, self._start_mod_auto_updater)
        self.after(600, self._init_buff_manager)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ══════════════════════════════════════════════════════════════════════════
    # UI — Estrutura principal
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_static_frames()
        self._rebuild_server_sidebar()
        self._show_frame("dashboard")

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> None:
        sb = ctk.CTkFrame(self, width=210, corner_radius=0, fg_color=_SIDEBAR_BG)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)
        self._sidebar = sb

        # Logo
        try:
            from PIL import Image  # type: ignore[reportMissingImports]
            _logo = Image.open(_resource_path(os.path.join("ig", "ArkLandBR.png")))
            self._logo_img = ctk.CTkImage(light_image=_logo, dark_image=_logo, size=(120, 120))
            ctk.CTkLabel(sb, image=self._logo_img, text="").grid(
                row=0, column=0, padx=20, pady=(16, 0))
        except Exception:
            ctk.CTkLabel(
                sb, text="⚡ ARKLAND",
                font=ctk.CTkFont(size=20, weight="bold"), text_color=_GREEN,
            ).grid(row=0, column=0, padx=20, pady=(24, 0))

        ctk.CTkLabel(sb, text="Server Manager",
                     font=ctk.CTkFont(size=12), text_color="#88d4a0").grid(row=1, column=0)
        ctk.CTkLabel(sb, text=f"v{APP_VERSION}",
                     font=ctk.CTkFont(size=10), text_color="gray50").grid(
            row=2, column=0, pady=(0, 8))

        ctk.CTkFrame(sb, height=1, fg_color="#2a2a44").grid(
            row=3, column=0, sticky="ew", padx=12, pady=4)

        self._nav_buttons: Dict[str, ctk.CTkButton] = {}
        for i, (label, key) in enumerate([
            ("🏠  Dashboard",      "dashboard"),
            ("🔄  Sincronização",  "sync"),
            ("⚡  BUFFs",          "buffs"),
            ("⚙️  Configurações",  "config"),
            ("ℹ️  Sobre",           "sobre"),
        ]):
            btn = ctk.CTkButton(
                sb, text=label, anchor="w", width=185, height=38,
                fg_color="transparent", text_color="#d8d8e8",
                hover_color="#252540", corner_radius=8,
                command=lambda k=key: self._show_frame(k),
            )
            btn.grid(row=i + 4, column=0, padx=12, pady=2, sticky="ew")
            self._nav_buttons[key] = btn

        ctk.CTkFrame(sb, height=1, fg_color="#2a2a44").grid(
            row=9, column=0, sticky="ew", padx=12, pady=8)

        # Título "Servidores" + botão "+"
        srv_hdr = ctk.CTkFrame(sb, fg_color="transparent")
        srv_hdr.grid(row=10, column=0, padx=12, pady=(0, 4), sticky="ew")
        srv_hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(srv_hdr, text="SERVIDORES",
                     font=ctk.CTkFont(size=10, weight="bold"), text_color="gray50").grid(
            row=0, column=0, sticky="w", padx=4)
        ctk.CTkButton(
            srv_hdr, text="＋", width=28, height=24,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._dialog_add_server,
        ).grid(row=0, column=1)

        # Frame scrollable para lista de servidores
        self._servers_list_sb = ctk.CTkScrollableFrame(
            sb, fg_color="transparent", height=280)
        self._servers_list_sb.grid(row=11, column=0, sticky="ew", padx=6)
        self._servers_list_sb.grid_columnconfigure(0, weight=1)

        self._sidebar_update_lbl = ctk.CTkLabel(
            sb, text="", font=ctk.CTkFont(size=10), text_color="#ffaa44", wraplength=180)
        self._sidebar_update_lbl.grid(row=12, column=0, padx=10, pady=4)

    def _rebuild_server_sidebar(self) -> None:
        """Reconstrói a lista de botões de servidores na sidebar."""
        for w in self._servers_list_sb.winfo_children():
            w.destroy()
        self._sidebar_server_btns.clear()

        servers = self.config_manager.servers
        if not servers:
            ctk.CTkLabel(self._servers_list_sb, text="Nenhum servidor.\nClique ＋ para adicionar.",
                         text_color="gray50", font=ctk.CTkFont(size=11), justify="center").pack(
                pady=10)
            return

        for srv in servers:
            inst = self.server_manager.get_instance(srv.id)
            status = inst.status if inst else SERVER_STATUS_STOPPED
            color = _STATUS_COLOR.get(status, "#ff6666")

            btn_frame = ctk.CTkFrame(self._servers_list_sb, fg_color="transparent")
            btn_frame.pack(fill="x", pady=2)
            btn_frame.grid_columnconfigure(0, weight=1)

            btn = ctk.CTkButton(
                btn_frame,
                text=f"  {srv.name}",
                anchor="w", height=36, corner_radius=8,
                fg_color="transparent", text_color="#d8d8e8",
                hover_color="#252540",
                command=lambda sid=srv.id: self._open_server_panel(sid),
            )
            btn.grid(row=0, column=0, sticky="ew")

            status_dot = ctk.CTkLabel(btn_frame, text="●", text_color=color,
                                       font=ctk.CTkFont(size=10), width=18)
            status_dot.grid(row=0, column=1, padx=(0, 4))

            self._sidebar_server_btns[srv.id] = btn
            btn._status_dot = status_dot  # type: ignore[attr-defined]

    # ── Frames estáticos ──────────────────────────────────────────────────────

    def _build_static_frames(self) -> None:
        dash = ctk.CTkFrame(self, corner_radius=0, fg_color=_BG)
        dash.grid(row=0, column=1, sticky="nsew")
        self._build_dashboard(dash)
        self._frames["dashboard"] = dash

        sync = ctk.CTkFrame(self, corner_radius=0, fg_color=_BG)
        sync.grid(row=0, column=1, sticky="nsew")
        self._build_sync_panel(sync)
        self._frames["sync"] = sync

        buffs = ctk.CTkFrame(self, corner_radius=0, fg_color=_BG)
        buffs.grid(row=0, column=1, sticky="nsew")
        self._build_buffs_panel(buffs)
        self._frames["buffs"] = buffs

        conf = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color=_BG)
        conf.grid(row=0, column=1, sticky="nsew")
        self._build_global_config(conf)
        self._frames["config"] = conf

        sobre = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color=_BG)
        sobre.grid(row=0, column=1, sticky="nsew")
        self._build_about(sobre)
        self._frames["sobre"] = sobre

    # ══════════════════════════════════════════════════════════════════════════
    # Painel de Sincronização
    # ══════════════════════════════════════════════════════════════════════════

    def _build_sync_panel(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(5, weight=1)

        # ── Cabeçalho ─────────────────────────────────────────────────────────
        ctk.CTkLabel(parent, text="Sincronização de Cluster",
                     font=ctk.CTkFont(size=24, weight="bold")).grid(
            row=0, column=0, padx=24, pady=(24, 2), sticky="w")
        ctk.CTkLabel(
            parent,
            text=(f"Até {_MAX_SYNC_CYCLES} ciclos independentes · "
                  f"até {_MAX_SYNC_FOLDERS} pastas por ciclo · sync N-way bidirecional."),
            text_color="gray60").grid(row=1, column=0, padx=24, pady=(0, 12), sticky="w")

        # ── Card de Status ────────────────────────────────────────────────────
        status_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        status_card.grid(row=2, column=0, padx=20, pady=(0, 8), sticky="ew")
        status_card.grid_columnconfigure(1, weight=1)

        self._sync_status_lbl = ctk.CTkLabel(
            status_card, text="⬜  Parado",
            font=ctk.CTkFont(size=14, weight="bold"), text_color="gray60")
        self._sync_status_lbl.grid(row=0, column=0, padx=20, pady=(14, 6), sticky="w")

        self._sync_stats_lbl = ctk.CTkLabel(
            status_card, text="Ciclos: 0  |  Arquivos: 0  |  Erros: 0  |  Último: —",
            text_color="gray50", font=ctk.CTkFont(size=11))
        self._sync_stats_lbl.grid(row=1, column=0, columnspan=2, padx=20, pady=(0, 14), sticky="w")

        btn_frame = ctk.CTkFrame(status_card, fg_color="transparent")
        btn_frame.grid(row=0, column=1, padx=12, pady=10, sticky="e")

        self._sync_toggle_btn = ctk.CTkButton(
            btn_frame, text="▶  Iniciar Sync", width=150, height=36,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=self._toggle_sync)
        self._sync_toggle_btn.grid(row=0, column=0, padx=(0, 8))

        ctk.CTkButton(
            btn_frame, text="⟳  Sincronizar Agora", width=160, height=36,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            command=self._force_sync_once).grid(row=0, column=1)

        # ── Card de Ciclos ────────────────────────────────────────────────────
        cycles_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        cycles_card.grid(row=3, column=0, padx=20, pady=(0, 8), sticky="ew")
        cycles_card.grid_columnconfigure(0, weight=1)

        # Cabeçalho do card: título + intervalo + salvar
        ch = ctk.CTkFrame(cycles_card, fg_color="transparent")
        ch.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        ch.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(ch, text="Ciclos de Sincronização",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="gray70").grid(row=0, column=0, sticky="w")

        cf_right = ctk.CTkFrame(ch, fg_color="transparent")
        cf_right.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(cf_right, text="Intervalo (s):", text_color="gray60",
                     font=ctk.CTkFont(size=12)).grid(row=0, column=0, padx=(0, 4))
        self._sync_interval_var = tk.StringVar(
            value=str(self.config_manager.config.sync_interval))
        ctk.CTkEntry(cf_right, textvariable=self._sync_interval_var,
                     width=64, height=30).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(cf_right, text="💾  Salvar", width=110, height=30,
                      fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                      command=self._save_sync_config).grid(row=0, column=2)

        # Frame rolável com os cards de cada ciclo
        self._sync_cycles_frame = ctk.CTkScrollableFrame(
            cycles_card, fg_color="transparent", height=200)
        self._sync_cycles_frame.grid(row=1, column=0, padx=8, pady=0, sticky="ew")
        self._sync_cycles_frame.grid_columnconfigure(0, weight=1)

        # Botão "+ Adicionar Ciclo"
        self._sync_add_cycle_btn = ctk.CTkButton(
            cycles_card, text="＋  Adicionar Ciclo", height=30, width=160,
            fg_color="#2a2a40", hover_color="#363656",
            command=self._add_sync_cycle)
        self._sync_add_cycle_btn.grid(row=2, column=0, padx=12, pady=(4, 10), sticky="w")

        # ── Log de Sync ────────────────────────────────────────────────────────
        ctk.CTkLabel(parent, text="Log de Sincronização",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="gray70").grid(
            row=4, column=0, padx=24, pady=(4, 4), sticky="w")

        self._sync_log_box = ctk.CTkTextbox(
            parent, state="disabled", font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0d0d18", text_color="#c8c8d8", corner_radius=8)
        self._sync_log_box.grid(row=5, column=0, padx=20, pady=(0, 20), sticky="nsew")

        # Carrega ciclos salvos na config
        self._sync_cycle_vars = []
        saved = self.config_manager.config.sync_cycles or []
        if not saved:
            saved = [[""]]  # 1 ciclo vazio por padrão
        for cycle_paths in saved[:_MAX_SYNC_CYCLES]:
            self._add_sync_cycle(cycle_paths if isinstance(cycle_paths, list) else [""])

    # ── Sync helpers ──────────────────────────────────────────────────────────

    def _browse_sync_folder(self, var: tk.StringVar) -> None:
        d = filedialog.askdirectory(parent=self)
        if d:
            var.set(d)

    # ── Gestão de ciclos ──────────────────────────────────────────────────────

    def _add_sync_cycle(self, initial_paths: Optional[list] = None) -> None:
        """Adiciona um card de ciclo no painel de sincronização."""
        if len(self._sync_cycle_vars) >= _MAX_SYNC_CYCLES:
            return
        folder_vars: List[tk.StringVar] = []
        self._sync_cycle_vars.append(folder_vars)
        cycle_num = len(self._sync_cycle_vars)

        card = ctk.CTkFrame(self._sync_cycles_frame, corner_radius=8, fg_color="#17172a")
        card.grid(row=cycle_num - 1, column=0, padx=4, pady=(0, 8), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        # Título + botão remover ciclo
        th = ctk.CTkFrame(card, fg_color="transparent")
        th.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        th.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(th, text=f"Ciclo {cycle_num}",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="gray60").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            th, text="🗑", width=30, height=24,
            fg_color="transparent", hover_color=_RED_DARK, text_color="gray50",
            command=lambda c=card, fv=folder_vars: self._remove_sync_cycle(c, fv),
        ).grid(row=0, column=1, sticky="e")

        # Container das linhas de pasta (pack facilita remoção individual)
        folders_frame = ctk.CTkFrame(card, fg_color="transparent")
        folders_frame.grid(row=1, column=0, padx=8, pady=0, sticky="ew")

        # Botão "+ Pasta" (criado antes para ser passado aos helpers)
        add_folder_btn = ctk.CTkButton(
            card, text="＋  Pasta", height=26, width=100,
            fg_color="transparent", hover_color="#363656",
            border_width=1, border_color="#363656")
        add_folder_btn.configure(
            command=lambda ff=folders_frame, fv=folder_vars, ab=add_folder_btn:
                self._add_sync_folder(ff, fv, ab))
        add_folder_btn.grid(row=2, column=0, padx=8, pady=(4, 8), sticky="w")

        # Popula pastas iniciais
        paths = initial_paths if initial_paths else [""]
        for p in paths[:_MAX_SYNC_FOLDERS]:
            self._add_sync_folder(folders_frame, folder_vars, add_folder_btn, str(p))

        self._refresh_add_cycle_btn()

    def _remove_sync_cycle(self, card, folder_vars: list) -> None:
        """Remove um ciclo do painel."""
        if folder_vars in self._sync_cycle_vars:
            self._sync_cycle_vars.remove(folder_vars)
        card.destroy()
        self._refresh_add_cycle_btn()
        # Renumera os labels dos ciclos restantes
        for i, child in enumerate(self._sync_cycles_frame.winfo_children()):
            for sub in child.winfo_children():
                if not isinstance(sub, ctk.CTkFrame):
                    continue
                for lbl in sub.winfo_children():
                    if isinstance(lbl, ctk.CTkLabel) and lbl.cget("text").startswith("Ciclo "):
                        lbl.configure(text=f"Ciclo {i + 1}")
                        break
                break

    def _add_sync_folder(
        self, folders_frame, folder_vars: list, add_btn, path: str = ""
    ) -> None:
        """Adiciona uma linha de pasta em um ciclo."""
        if len(folder_vars) >= _MAX_SYNC_FOLDERS:
            return
        var = tk.StringVar(value=path)
        folder_vars.append(var)
        idx = len(folder_vars) - 1

        row = ctk.CTkFrame(folders_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)
        row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(row, text=f"Pasta {idx + 1}:",
                     text_color="gray50", width=60, anchor="e",
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(0, 4))
        ctk.CTkEntry(row, textvariable=var, height=28,
                     placeholder_text="Caminho da pasta...").grid(
            row=0, column=1, padx=(0, 4), sticky="ew")
        ctk.CTkButton(
            row, text="📁", width=30, height=28,
            fg_color="#2a2a40", hover_color="#363656",
            command=lambda v=var: self._browse_sync_folder(v),
        ).grid(row=0, column=2, padx=(0, 4))
        ctk.CTkButton(
            row, text="✕", width=28, height=28,
            fg_color="transparent", hover_color=_RED_DARK, text_color="gray50",
            command=lambda v=var, r=row, ff=folders_frame, fv=folder_vars, ab=add_btn:
                self._remove_sync_folder(ff, fv, v, r, ab),
        ).grid(row=0, column=3)

        add_btn.configure(
            state="disabled" if len(folder_vars) >= _MAX_SYNC_FOLDERS else "normal")

    def _remove_sync_folder(
        self, folders_frame, folder_vars: list,
        var: tk.StringVar, row_frame, add_btn
    ) -> None:
        """Remove uma linha de pasta de um ciclo (mantém pelo menos 1)."""
        if len(folder_vars) <= 1:
            var.set("")
            return
        if var in folder_vars:
            folder_vars.remove(var)
        row_frame.destroy()
        # Re-numera labels das linhas restantes
        for i, child in enumerate(folders_frame.winfo_children()):
            for lbl in child.winfo_children():
                if isinstance(lbl, ctk.CTkLabel):
                    lbl.configure(text=f"Pasta {i + 1}:")
                    break
        add_btn.configure(state="normal")

    def _refresh_add_cycle_btn(self) -> None:
        """Habilita/desabilita o botão '+ Adicionar Ciclo' conforme o limite."""
        if self._sync_add_cycle_btn:
            state = "normal" if len(self._sync_cycle_vars) < _MAX_SYNC_CYCLES else "disabled"
            self._sync_add_cycle_btn.configure(state=state)

    def _save_sync_config(self) -> None:
        cfg = self.config_manager.config
        # Coleta ciclos: apenas pastas com caminho preenchido
        cycles = []
        for folder_vars in self._sync_cycle_vars:
            paths = [v.get().strip() for v in folder_vars if v.get().strip()]
            if paths:
                cycles.append(paths)
        cfg.sync_cycles = cycles
        try:
            cfg.sync_interval = max(1, int(self._sync_interval_var.get()))
        except ValueError:
            cfg.sync_interval = 5
        self._sync_interval_var.set(str(cfg.sync_interval))
        self.config_manager.save()
        messagebox.showinfo("Salvo", "Configurações de sync salvas!", parent=self)
        # Recria engine com os novos ciclos
        if self._sync_engine and self._sync_engine.is_running:
            self._sync_engine.stop()
            self._sync_engine = None
            self._start_sync_engine()

    def _auto_start_sync(self) -> None:
        """Inicia o sync automaticamente ao abrir, se houver ciclos configurados."""
        cycles = self.config_manager.config.sync_cycles or []
        has_paths = any(
            any(str(p).strip() for p in cycle)
            for cycle in cycles
            if isinstance(cycle, list)
        )
        if has_paths:
            self._start_sync_engine()

    def _toggle_sync(self) -> None:
        if self._sync_engine and self._sync_engine.is_running:
            self._sync_engine.stop()
        else:
            self._start_sync_engine()

    def _start_sync_engine(self) -> None:
        if self._sync_engine is None:
            self._sync_engine = SyncEngine(
                self.config_manager.config,
                on_log=self._on_sync_log,
                on_status_change=self._on_sync_status,
                on_stats_update=self._on_sync_stats,
            )
        self._sync_engine.start()

    def _force_sync_once(self) -> None:
        if self._sync_engine is None:
            self._sync_engine = SyncEngine(
                self.config_manager.config,
                on_log=self._on_sync_log,
                on_status_change=self._on_sync_status,
                on_stats_update=self._on_sync_stats,
            )
        self._sync_engine.sync_once()

    def _on_sync_log(self, msg: str, level: str = "info") -> None:
        ts = __import__("datetime").datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        def _do():
            if self._sync_log_box:
                self._sync_log_box.configure(state="normal")
                self._sync_log_box.insert("end", line)
                self._sync_log_box.see("end")
                self._sync_log_box.configure(state="disabled")
        self.after(0, _do)

    def _on_sync_status(self, status: str) -> None:
        def _do():
            if self._sync_toggle_btn is None or self._sync_status_lbl is None:
                return
            if status == "running":
                self._sync_status_lbl.configure(
                    text="🟢  Sincronizando", text_color=_GREEN)
                self._sync_toggle_btn.configure(
                    text="⏹  Parar Sync", fg_color=_RED_DARK, hover_color=_RED_HOVER)
            else:
                self._sync_status_lbl.configure(
                    text="⬜  Parado", text_color="gray60")
                self._sync_toggle_btn.configure(
                    text="▶  Iniciar Sync", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER)
        self.after(0, _do)

    def _on_sync_stats(self, stats: dict) -> None:
        def _do():
            if self._sync_stats_lbl:
                self._sync_stats_lbl.configure(
                    text=(f"Ciclos: {stats.get('cycles', 0)}  |  "
                          f"Arquivos: {stats.get('total_synced', 0)}  |  "
                          f"Erros: {stats.get('errors', 0)}  |  "
                          f"Último: {stats.get('last_sync', '—')}"))
        self.after(0, _do)

    # ══════════════════════════════════════════════════════════════════════════
    # BUFFs — Rates Temporários
    # ══════════════════════════════════════════════════════════════════════════

    def _init_buff_manager(self) -> None:
        """Inicializa o BuffManager após a UI ser construída."""
        data_dir = Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager"
        self._buff_manager = BuffManager(
            data_dir=data_dir,
            get_server_config=lambda sid: next(
                (s for s in self.config_manager.servers if s.id == sid), None
            ),
            start_server=self.server_manager.start_server,
            stop_server=self.server_manager.stop_server,
            get_server_status=lambda sid: (
                inst.status
                if (inst := self.server_manager.get_instance(sid))
                else SERVER_STATUS_STOPPED
            ),
            on_log=self._global_log,
        )
        self._buff_manager.add_change_callback(
            lambda: self.after(0, self._refresh_buffs_ui)
        )
        self._refresh_buffs_ui()

    def _build_buffs_panel(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # ── Cabeçalho ──────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 6))
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            hdr, text="⚡  BUFFs — Rates Temporários",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            hdr,
            text="Eventos globais de rates com início e fim automáticos — estilo servidores oficiais.",
            text_color="gray60",
        ).grid(row=1, column=0, sticky="w", pady=(0, 4))

        btn_bar = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_bar.grid(row=0, column=2, rowspan=2, sticky="e", padx=(0, 0))
        ctk.CTkButton(
            btn_bar, text="⚡  Criar BUFF", height=38, width=150,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._open_create_buff_dialog,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_bar, text="📋  Presets", height=38, width=120,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            command=self._open_presets_manager,
        ).pack(side="left")

        # ── Seletor de servidor ─────────────────────────────────────────────
        sel_bar = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=10)
        sel_bar.grid(row=0, column=0, sticky="ew", padx=20, pady=(80, 4))
        sel_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            sel_bar, text="Servidor:", text_color="gray60",
            font=ctk.CTkFont(size=12),
        ).grid(row=0, column=0, padx=(16, 8), pady=10, sticky="w")

        self._buffs_server_var = tk.StringVar()
        srv_names = [s.name for s in self.config_manager.servers]
        srv_combo = ctk.CTkComboBox(
            sel_bar,
            variable=self._buffs_server_var,
            values=srv_names if srv_names else ["(nenhum servidor)"],
            state="readonly",
            width=300,
            command=lambda _: self._refresh_buffs_ui(),
        )
        if srv_names:
            self._buffs_server_var.set(srv_names[0])
        srv_combo.grid(row=0, column=1, padx=(0, 16), pady=10, sticky="w")

        # ── Body scrollável (reconstruído no refresh) ───────────────────────
        body = ctk.CTkScrollableFrame(parent, fg_color=_BG)
        body.grid(row=1, column=0, sticky="nsew", padx=0, pady=(4, 0))
        body.grid_columnconfigure(0, weight=1)
        self._buffs_body_frame = body

    def _refresh_buffs_ui(self) -> None:
        """Reconstrói o conteúdo dinâmico do painel BUFFs."""
        body = self._buffs_body_frame
        if body is None:
            return

        # Limpa conteúdo anterior
        for w in body.winfo_children():
            w.destroy()

        bm = self._buff_manager
        servers = self.config_manager.servers

        # Resolve servidor selecionado
        srv_id: Optional[str] = None
        srv_name_sel = self._buffs_server_var.get() if self._buffs_server_var else ""
        for s in servers:
            if s.name == srv_name_sel:
                srv_id = s.id
                break

        row_idx = 0

        # ── BUFF Ativo ──────────────────────────────────────────────────────
        ctk.CTkLabel(
            body, text="BUFF ATIVO",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#88d4a0",
        ).grid(row=row_idx, column=0, padx=20, pady=(16, 4), sticky="w")
        row_idx += 1

        active = bm.get_active_event(srv_id) if bm and srv_id else None
        if active:
            self._build_active_buff_card(body, row_idx, active)
        else:
            none_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
            none_card.grid(row=row_idx, column=0, padx=20, pady=(0, 8), sticky="ew")
            ctk.CTkLabel(
                none_card, text="Nenhum BUFF ativo no momento.",
                text_color="gray50", font=ctk.CTkFont(size=12),
            ).pack(padx=20, pady=18)
        row_idx += 1

        # ── BUFFs Agendados ─────────────────────────────────────────────────
        ctk.CTkLabel(
            body, text="BUFFs AGENDADOS",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#88d4a0",
        ).grid(row=row_idx, column=0, padx=20, pady=(12, 4), sticky="w")
        row_idx += 1

        scheduled = bm.get_scheduled_events(srv_id) if bm and srv_id else []
        if scheduled:
            for evt in scheduled:
                self._build_scheduled_buff_row(body, row_idx, evt)
                row_idx += 1
        else:
            empty = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
            empty.grid(row=row_idx, column=0, padx=20, pady=(0, 4), sticky="ew")
            ctk.CTkLabel(empty, text="Nenhum BUFF agendado.",
                         text_color="gray50").pack(padx=20, pady=12)
            row_idx += 1

        # ── Presets Salvos ──────────────────────────────────────────────────
        presets = bm.get_presets() if bm else []
        if presets:
            ctk.CTkLabel(
                body, text="PRESETS SALVOS",
                font=ctk.CTkFont(size=12, weight="bold"), text_color="#88d4a0",
            ).grid(row=row_idx, column=0, padx=20, pady=(12, 4), sticky="w")
            row_idx += 1
            grid_f = ctk.CTkFrame(body, fg_color="transparent")
            grid_f.grid(row=row_idx, column=0, padx=20, pady=(0, 4), sticky="ew")
            grid_f.grid_columnconfigure((0, 1, 2), weight=1)
            row_idx += 1
            for ci, preset in enumerate(presets):
                self._build_preset_chip(grid_f, ci // 3, ci % 3, preset, srv_id)

        # ── Histórico ───────────────────────────────────────────────────────
        finished = bm.get_finished_events(srv_id) if bm and srv_id else []
        if finished:
            ctk.CTkLabel(
                body, text="HISTÓRICO",
                font=ctk.CTkFont(size=12, weight="bold"), text_color="#88d4a0",
            ).grid(row=row_idx, column=0, padx=20, pady=(12, 4), sticky="w")
            row_idx += 1
            for evt in finished[:10]:
                self._build_history_row(body, row_idx, evt)
                row_idx += 1

        # Espaço final
        ctk.CTkFrame(body, fg_color="transparent", height=30).grid(
            row=row_idx, column=0)

    def _build_active_buff_card(self, parent, row: int, event: BuffEvent) -> None:
        card = ctk.CTkFrame(parent, fg_color="#1a2a1a", corner_radius=12)
        card.grid(row=row, column=0, padx=20, pady=(0, 8), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, padx=16, pady=(14, 4), sticky="ew")
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            top, text="🟢  BUFF ATIVO",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=_GREEN,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            top,
            text=f"Fim: {event.end_datetime().strftime('%d/%m/%Y  %H:%M')}",
            text_color="gray60", font=ctk.CTkFont(size=11),
        ).grid(row=0, column=2, sticky="e")

        ctk.CTkLabel(
            card, text=event.name,
            font=ctk.CTkFont(size=18, weight="bold"), text_color="#e8e8ff",
        ).grid(row=1, column=0, padx=16, pady=(0, 4), sticky="w")

        types_str = "  ·  ".join(BUFF_TYPE_LABELS.get(t, t) for t in event.types)
        ctk.CTkLabel(
            card, text=types_str,
            text_color="#ffaa44", font=ctk.CTkFont(size=12),
        ).grid(row=2, column=0, padx=16, pady=(0, 4), sticky="w")

        ctk.CTkLabel(
            card, text=event.rates.summary(),
            text_color="gray60", font=ctk.CTkFont(size=11),
            wraplength=700, justify="left",
        ).grid(row=3, column=0, padx=16, pady=(0, 14), sticky="w")

    def _build_scheduled_buff_row(self, parent, row: int, event: BuffEvent) -> None:
        card = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=10)
        card.grid(row=row, column=0, padx=20, pady=3, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card,
            text=f"🕐  {event.start_datetime().strftime('%d/%m/%Y  %H:%M')}  →  "
                 f"{event.end_datetime().strftime('%d/%m/%Y  %H:%M')}",
            text_color="gray55", font=ctk.CTkFont(size=11),
        ).grid(row=0, column=0, padx=(16, 8), pady=(10, 2), sticky="w")

        ctk.CTkLabel(
            card, text=event.name,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=1, column=0, padx=(16, 8), pady=(0, 2), sticky="w")

        types_str = "  ·  ".join(BUFF_TYPE_LABELS.get(t, t) for t in event.types)
        ctk.CTkLabel(card, text=types_str, text_color="#ffaa44",
                     font=ctk.CTkFont(size=11)).grid(
            row=2, column=0, padx=(16, 8), pady=(0, 10), sticky="w")

        ctk.CTkButton(
            card, text="✕  Cancelar", width=110, height=30,
            fg_color=_RED_DARK, hover_color=_RED_HOVER,
            font=ctk.CTkFont(size=11),
            command=lambda eid=event.id: self._cancel_buff(eid),
        ).grid(row=0, column=2, rowspan=3, padx=16, pady=10)

    def _build_preset_chip(self, parent, row: int, col: int,
                           preset: BuffPreset, srv_id: Optional[str]) -> None:
        card = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=10)
        card.grid(row=row, column=col, padx=6, pady=4, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card, text=preset.name,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, padx=12, pady=(10, 2), sticky="w")

        types_str = "  ·  ".join(BUFF_TYPE_LABELS.get(t, t) for t in preset.types)
        ctk.CTkLabel(card, text=types_str, text_color="#ffaa44",
                     font=ctk.CTkFont(size=11)).grid(
            row=1, column=0, padx=12, pady=(0, 8), sticky="w")

        if srv_id:
            ctk.CTkButton(
                card, text="⚡  Usar", height=28, width=80,
                fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                font=ctk.CTkFont(size=11),
                command=lambda p=preset, sid=srv_id: self._open_create_buff_dialog(
                    preset=p, server_id=sid),
            ).grid(row=2, column=0, padx=12, pady=(0, 10), sticky="w")

    def _build_history_row(self, parent, row: int, event: BuffEvent) -> None:
        is_cancelled = event.status == BUFF_STATUS_CANCELLED
        card = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=8)
        card.grid(row=row, column=0, padx=20, pady=2, sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        icon = "✕" if is_cancelled else "✔"
        color = "gray45" if is_cancelled else "gray55"
        status_lbl = "Cancelado" if is_cancelled else "Finalizado"
        ctk.CTkLabel(
            card,
            text=f"{icon}  {event.name}  —  {status_lbl}  "
                 f"({event.start_datetime().strftime('%d/%m/%Y')} — "
                 f"{event.end_datetime().strftime('%d/%m/%Y')})",
            text_color=color, font=ctk.CTkFont(size=11),
        ).pack(padx=16, pady=8, side="left")

    def _cancel_buff(self, event_id: str) -> None:
        if messagebox.askyesno(
            "Cancelar BUFF",
            "Confirmar cancelamento do BUFF agendado?",
            parent=self,
        ):
            if self._buff_manager:
                self._buff_manager.cancel_event(event_id)

    # ── Diálogo: Criar BUFF ────────────────────────────────────────────────────

    def _open_create_buff_dialog(
        self,
        preset: Optional[BuffPreset] = None,
        server_id: Optional[str] = None,
    ) -> None:
        servers = self.config_manager.servers
        if not servers:
            messagebox.showwarning(
                "Sem Servidores",
                "Adicione ao menos um servidor antes de criar um BUFF.",
                parent=self,
            )
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Criar BUFF")
        dlg.geometry("780x740")
        dlg.resizable(True, True)
        dlg.grab_set()
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            dlg, text="⚡  Criar Novo BUFF",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(18, 4), sticky="w")

        body = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        body.grid_columnconfigure(0, weight=1)

        r = 0

        # ── Nome + Servidor ──────────────────────────────────────────────
        top_row = ctk.CTkFrame(body, fg_color="transparent")
        top_row.grid(row=r, column=0, sticky="ew", padx=16, pady=(8, 4))
        top_row.grid_columnconfigure(1, weight=1)
        top_row.grid_columnconfigure(3, weight=1)
        r += 1

        ctk.CTkLabel(top_row, text="Nome do BUFF:", width=110, anchor="w").grid(
            row=0, column=0, sticky="w")
        name_var = tk.StringVar(value=preset.name + " (cópia)" if preset else "")
        ctk.CTkEntry(top_row, textvariable=name_var, height=36).grid(
            row=0, column=1, sticky="ew", padx=(8, 16))

        ctk.CTkLabel(top_row, text="Servidor:", width=80, anchor="w").grid(
            row=0, column=2, sticky="w")
        srv_var = tk.StringVar()
        srv_names = [s.name for s in servers]
        if server_id:
            presel = next((s.name for s in servers if s.id == server_id), srv_names[0])
        else:
            presel = self._buffs_server_var.get() if self._buffs_server_var else srv_names[0]
        srv_var.set(presel)
        ctk.CTkComboBox(
            top_row, variable=srv_var, values=srv_names,
            state="readonly", width=220,
        ).grid(row=0, column=3, sticky="w", padx=(8, 0))

        # ── Tipos ────────────────────────────────────────────────────────
        ctk.CTkLabel(
            body, text="TIPOS DE BUFF",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#88d4a0",
        ).grid(row=r, column=0, padx=18, pady=(12, 4), sticky="w")
        r += 1

        types_frame = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
        types_frame.grid(row=r, column=0, padx=16, pady=(0, 6), sticky="ew")
        r += 1

        type_vars: Dict[str, tk.BooleanVar] = {}
        preset_types = preset.types if preset else []
        for ci, btype in enumerate([BUFF_TYPE_XP, BUFF_TYPE_DOMA, BUFF_TYPE_BREEDING, BUFF_TYPE_FARM]):
            var = tk.BooleanVar(value=(btype in preset_types) if preset_types else True)
            type_vars[btype] = var
            ctk.CTkCheckBox(
                types_frame,
                text=BUFF_TYPE_LABELS[btype],
                variable=var,
                font=ctk.CTkFont(size=13),
            ).grid(row=0, column=ci, padx=20, pady=14, sticky="w")

        # ── Preset rápido ────────────────────────────────────────────────
        ctk.CTkLabel(
            body, text="PRESET RÁPIDO",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#88d4a0",
        ).grid(row=r, column=0, padx=18, pady=(10, 4), sticky="w")
        r += 1

        quick_frame = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
        quick_frame.grid(row=r, column=0, padx=16, pady=(0, 6), sticky="ew")
        r += 1

        rate_vars: Dict[str, tk.StringVar] = {}

        def _fill_quick(mult: int) -> None:
            vals = QUICK_PRESETS.get(mult, {})
            for btype, fields in vals.items():
                if type_vars[btype].get():
                    for fname, fval in fields.items():
                        if fname in rate_vars:
                            rate_vars[fname].set(str(fval))

        ctk.CTkLabel(quick_frame, text="Aplicar multiplicador a todos os tipos selecionados:",
                     text_color="gray60", font=ctk.CTkFont(size=11)).grid(
            row=0, column=0, columnspan=5, padx=16, pady=(12, 4), sticky="w")
        for ci, mult in enumerate((5, 10, 15)):
            ctk.CTkButton(
                quick_frame, text=f"{mult}x", width=72, height=34,
                fg_color="#2a2a44", hover_color="#1e2a3a",
                command=lambda m=mult: _fill_quick(m),
            ).grid(row=1, column=ci, padx=(16 if ci == 0 else 8, 0), pady=(4, 14))

        # Preset salvo
        presets_list = self._buff_manager.get_presets() if self._buff_manager else []
        if presets_list:
            ctk.CTkLabel(quick_frame, text="Usar preset salvo:",
                         text_color="gray60", font=ctk.CTkFont(size=11)).grid(
                row=1, column=3, padx=(24, 4), pady=(4, 14))

            def _apply_preset_combo(pname: str) -> None:
                found = next((p for p in presets_list if p.name == pname), None)
                if not found:
                    return
                for t in [BUFF_TYPE_XP, BUFF_TYPE_DOMA, BUFF_TYPE_BREEDING, BUFF_TYPE_FARM]:
                    type_vars[t].set(t in found.types)
                for fname in rate_vars:
                    val = getattr(found.rates, fname, None)
                    rate_vars[fname].set(str(val) if val is not None else "")

            ctk.CTkComboBox(
                quick_frame,
                values=[p.name for p in presets_list],
                state="readonly", width=200,
                command=_apply_preset_combo,
            ).grid(row=1, column=4, padx=(0, 16), pady=(4, 14))

        # ── Campos de rate por tipo ───────────────────────────────────────
        ctk.CTkLabel(
            body, text="MULTIPLICADORES",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#88d4a0",
        ).grid(row=r, column=0, padx=18, pady=(10, 4), sticky="w")
        r += 1

        rates_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
        rates_card.grid(row=r, column=0, padx=16, pady=(0, 6), sticky="ew")
        rates_card.grid_columnconfigure((1, 3, 5, 7), weight=1)
        r += 1

        preset_rates = preset.rates if preset else None
        fr = 0
        for btype, fields in BUFF_RATE_FIELDS.items():
            # Separador de tipo
            ctk.CTkLabel(
                rates_card,
                text=BUFF_TYPE_LABELS[btype],
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#ffaa44",
            ).grid(row=fr, column=0, columnspan=8, padx=16, pady=(12, 4), sticky="w")
            fr += 1

            col = 0
            for fname, label, is_inv in fields:
                hint = " ↓" if is_inv else ""
                ctk.CTkLabel(
                    rates_card, text=f"{label}{hint}:",
                    text_color="gray60", font=ctk.CTkFont(size=11),
                    anchor="e", width=110,
                ).grid(row=fr, column=col, padx=(16 if col == 0 else 4, 4),
                       pady=6, sticky="e")
                col += 1

                init_val = ""
                if preset_rates:
                    v = getattr(preset_rates, fname, None)
                    if v is not None:
                        init_val = str(v)
                sv = tk.StringVar(value=init_val)
                rate_vars[fname] = sv
                ctk.CTkEntry(
                    rates_card, textvariable=sv, width=80, height=32,
                    placeholder_text="1.0",
                ).grid(row=fr, column=col, padx=(0, 16), pady=6, sticky="w")
                col += 1

                if col >= 8:
                    col = 0
                    fr += 1

            if col > 0:
                fr += 1

        # ── Agendamento ──────────────────────────────────────────────────
        ctk.CTkLabel(
            body, text="AGENDAMENTO",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#88d4a0",
        ).grid(row=r, column=0, padx=18, pady=(10, 4), sticky="w")
        r += 1

        sched_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
        sched_card.grid(row=r, column=0, padx=16, pady=(0, 6), sticky="ew")
        r += 1

        now_str = datetime.now().strftime("%d/%m/%Y %H:00")
        ctk.CTkLabel(sched_card, text="Início:", text_color="gray60").grid(
            row=0, column=0, padx=(16, 4), pady=14, sticky="w")
        start_var = tk.StringVar(value=now_str)
        ctk.CTkEntry(sched_card, textvariable=start_var, width=160,
                     placeholder_text="DD/MM/AAAA HH:MM").grid(
            row=0, column=1, padx=(0, 24), pady=14, sticky="w")

        ctk.CTkLabel(sched_card, text="Fim:", text_color="gray60").grid(
            row=0, column=2, padx=(0, 4), pady=14, sticky="w")
        end_var = tk.StringVar(value=now_str)
        ctk.CTkEntry(sched_card, textvariable=end_var, width=160,
                     placeholder_text="DD/MM/AAAA HH:MM").grid(
            row=0, column=3, padx=(0, 16), pady=14, sticky="w")

        ctk.CTkLabel(sched_card,
                     text="Formato: DD/MM/AAAA HH:MM  —  Máx. 30 dias",
                     text_color="gray45", font=ctk.CTkFont(size=10)).grid(
            row=1, column=0, columnspan=4, padx=16, pady=(0, 10), sticky="w")

        # ── Salvar como preset ───────────────────────────────────────────
        save_preset_var = tk.BooleanVar(value=False)
        preset_name_var = tk.StringVar()
        sp_frame = ctk.CTkFrame(body, fg_color="transparent")
        sp_frame.grid(row=r, column=0, padx=16, pady=(4, 4), sticky="ew")
        r += 1

        ctk.CTkCheckBox(sp_frame, text="Salvar como Preset", variable=save_preset_var).pack(
            side="left", padx=(0, 12))
        ctk.CTkEntry(sp_frame, textvariable=preset_name_var, width=220,
                     placeholder_text="Nome do Preset").pack(side="left")

        # ── Status / erro ─────────────────────────────────────────────────
        err_var = tk.StringVar()
        err_lbl = ctk.CTkLabel(body, textvariable=err_var,
                               text_color="#ff6666", font=ctk.CTkFont(size=11),
                               wraplength=700, justify="left")
        err_lbl.grid(row=r, column=0, padx=18, pady=(4, 0), sticky="w")
        r += 1

        # ── Botões ────────────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.grid(row=2, column=0, pady=(8, 16), padx=16, sticky="e")

        def _parse_dt(s: str) -> Optional[str]:
            """Converte DD/MM/AAAA HH:MM para ISO 8601."""
            s = s.strip()
            for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
                try:
                    return datetime.strptime(s, fmt).isoformat()
                except ValueError:
                    pass
            return None

        def _collect_rates() -> BuffRates:
            kwargs: Dict[str, float] = {}
            for fname, sv in rate_vars.items():
                raw = sv.get().strip()
                if raw:
                    try:
                        kwargs[fname] = float(raw.replace(",", "."))
                    except ValueError:
                        pass
            return BuffRates(**kwargs)

        def _do_schedule() -> None:
            name = name_var.get().strip()
            selected_types = [t for t, v in type_vars.items() if v.get()]

            start_iso = _parse_dt(start_var.get())
            end_iso   = _parse_dt(end_var.get())
            if not start_iso or not end_iso:
                err_var.set("Data/hora inválida. Use DD/MM/AAAA HH:MM.")
                return

            srv_name = srv_var.get()
            sel_srv = next((s for s in servers if s.name == srv_name), None)
            if not sel_srv:
                err_var.set("Servidor não encontrado.")
                return

            rates = _collect_rates()

            event = BuffEvent(
                id=str(uuid.uuid4()),
                name=name,
                server_id=sel_srv.id,
                types=selected_types,
                rates=rates,
                start_dt=start_iso,
                end_dt=end_iso,
                status=BUFF_STATUS_SCHEDULED,
            )

            if not self._buff_manager:
                err_var.set("BuffManager não inicializado.")
                return

            # Salva preset se solicitado
            if save_preset_var.get():
                pname = preset_name_var.get().strip() or name
                self._buff_manager.save_preset(BuffPreset(
                    id=str(uuid.uuid4()),
                    name=pname,
                    types=selected_types,
                    rates=rates,
                ))

            err = self._buff_manager.add_event(event)
            if err:
                err_var.set(err)
                return

            dlg.destroy()

        ctk.CTkButton(btn_row, text="Cancelar", width=120, height=40,
                      fg_color="#2a2a44", hover_color="#1e2a3a",
                      command=dlg.destroy).pack(side="left", padx=(0, 12))
        ctk.CTkButton(btn_row, text="⚡  Agendar BUFF", width=180, height=40,
                      fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=_do_schedule).pack(side="left")

    # ── Diálogo: Gerenciar Presets ─────────────────────────────────────────────

    def _open_presets_manager(self) -> None:
        if not self._buff_manager:
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Gerenciar Presets de BUFF")
        dlg.geometry("680x540")
        dlg.resizable(True, True)
        dlg.grab_set()
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(dlg, text="📋  Presets de BUFF",
                     font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=20, pady=(18, 4), sticky="w")

        def _rebuild() -> None:
            for w in list_frame.winfo_children():
                w.destroy()
            presets = self._buff_manager.get_presets() if self._buff_manager else []
            if not presets:
                ctk.CTkLabel(list_frame, text="Nenhum preset salvo.",
                             text_color="gray50").pack(pady=30)
                return
            for preset in presets:
                row_f = ctk.CTkFrame(list_frame, fg_color=_CARD_BG, corner_radius=10)
                row_f.pack(fill="x", padx=16, pady=4)
                row_f.grid_columnconfigure(0, weight=1)

                ctk.CTkLabel(row_f, text=preset.name,
                             font=ctk.CTkFont(size=13, weight="bold")).grid(
                    row=0, column=0, padx=14, pady=(10, 2), sticky="w")
                types_str = "  ·  ".join(BUFF_TYPE_LABELS.get(t, t) for t in preset.types)
                ctk.CTkLabel(row_f, text=types_str, text_color="#ffaa44",
                             font=ctk.CTkFont(size=11)).grid(
                    row=1, column=0, padx=14, pady=(0, 4), sticky="w")
                ctk.CTkLabel(row_f,
                             text=preset.rates.summary(),
                             text_color="gray55",
                             font=ctk.CTkFont(size=10),
                             wraplength=480, justify="left").grid(
                    row=2, column=0, padx=14, pady=(0, 10), sticky="w")

                btn_f = ctk.CTkFrame(row_f, fg_color="transparent")
                btn_f.grid(row=0, column=1, rowspan=3, padx=14, pady=10)
                ctk.CTkButton(
                    btn_f, text="🗑", width=40, height=34,
                    fg_color=_RED_DARK, hover_color=_RED_HOVER,
                    command=lambda pid=preset.id: _delete(pid),
                ).pack()

        def _delete(pid: str) -> None:
            if messagebox.askyesno("Excluir Preset", "Confirmar exclusão?", parent=dlg):
                if self._buff_manager:
                    self._buff_manager.delete_preset(pid)
                _rebuild()

        list_frame = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        list_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=4)
        _rebuild()

        ctk.CTkButton(dlg, text="Fechar", height=38,
                      fg_color="#2a2a44", hover_color="#1e2a3a",
                      command=dlg.destroy).grid(
            row=2, column=0, padx=20, pady=(4, 16), sticky="e")

    # ══════════════════════════════════════════════════════════════════════════
    # Dashboard
    # ══════════════════════════════════════════════════════════════════════════

    def _build_dashboard(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=24, pady=(24, 4), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="Dashboard",
                     font=ctk.CTkFont(size=24, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(hdr, text="Gerencie todos os seus servidores ARK em um só lugar.",
                     text_color="gray60").grid(row=1, column=0, sticky="w")

        ctk.CTkButton(
            hdr, text="＋  Novo Servidor", width=160, height=36,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._dialog_add_server,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        ctk.CTkFrame(parent, height=1, fg_color="#2a2a44").grid(
            row=1, column=0, padx=20, pady=(8, 0), sticky="ew")

        self._dashboard_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self._dashboard_scroll.grid(row=2, column=0, padx=12, pady=12, sticky="nsew")
        self._dashboard_scroll.grid_columnconfigure((0, 1), weight=1)

        self._refresh_dashboard()

    def _refresh_dashboard(self) -> None:
        frame = self._dashboard_scroll
        for w in frame.winfo_children():
            w.destroy()

        servers = self.config_manager.servers
        if not servers:
            ctk.CTkLabel(
                frame,
                text="Nenhum servidor configurado.\nClique em '＋ Novo Servidor' para começar.",
                font=ctk.CTkFont(size=15), text_color="gray50", justify="center",
            ).grid(row=0, column=0, columnspan=2, pady=60)
            return

        for idx, srv in enumerate(servers):
            row, col = divmod(idx, 2)
            self._build_server_card(frame, srv, row, col)

    def _build_server_card(self, parent, srv: ServerConfig, row: int, col: int) -> None:
        inst = self.server_manager.get_instance(srv.id)
        status = inst.status if inst else SERVER_STATUS_STOPPED
        color = _STATUS_COLOR.get(status, "#ff6666")
        status_txt = _STATUS_LABEL.get(status, "PARADO")

        card = ctk.CTkFrame(parent, corner_radius=14, fg_color=_CARD_BG, border_width=1,
                            border_color="#2a2a44")
        card.grid(row=row, column=col, padx=8, pady=8, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, padx=16, pady=(14, 4), sticky="ew")
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top, text=srv.name,
                     font=ctk.CTkFont(size=16, weight="bold")).grid(row=0, column=0, sticky="w")

        vis_mode  = inst.online_mode if inst else "—"
        vis_text  = "🌐 WAN" if vis_mode == "WAN" else ("🏠 LAN" if vis_mode == "LAN" else "")
        vis_color = _GREEN if vis_mode == "WAN" else ("#ffaa44" if vis_mode == "LAN" else "gray50")
        if vis_text:
            ctk.CTkLabel(top, text=vis_text, text_color=vis_color,
                         font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=1, padx=(0, 8), sticky="e")

        ctk.CTkLabel(top, text=status_txt, text_color=color,
                     font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=2, sticky="e")

        map_name = ARK_MAP_NAMES.get(srv.map, srv.map)
        info_lines = [
            f"🗺  {map_name}",
            f"🔌  Porta: {srv.server_port}  |  Query: {srv.query_port}",
            f"👥  Máx Jogadores: {srv.max_players}",
        ]
        if srv.mods:
            info_lines.append(f"🔧  Mods: {len(srv.mods)}")
        if inst and hasattr(inst, "uptime") and inst.uptime != "—":
            info_lines.append(f"⏱  Uptime: {inst.uptime}")

        ctk.CTkLabel(card, text="\n".join(info_lines),
                     text_color="gray60", justify="left",
                     font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, padx=16, pady=(0, 10), sticky="w")

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.grid(row=2, column=0, padx=12, pady=(0, 14), sticky="ew")

        is_running = status == SERVER_STATUS_RUNNING
        is_busy    = status in (SERVER_STATUS_STARTING, SERVER_STATUS_STOPPING)

        if is_busy:
            _d_text, _d_fg, _d_hover = "⚡ Cancelar", "#7a4a00", "#5c3600"
            def _d_cmd(sid=srv.id): self.server_manager.stop_server(sid, force=True)
        elif is_running:
            _d_text, _d_fg, _d_hover = "⏹ Parar", _RED_DARK, _RED_HOVER
            def _d_cmd(sid=srv.id): self._stop_server(sid)
        else:
            _d_text, _d_fg, _d_hover = "▶ Iniciar", _GREEN_DARK, _GREEN_HOVER
            def _d_cmd(sid=srv.id): self._start_server(sid)

        ctk.CTkButton(
            btn_row, text=_d_text, width=100, height=32,
            fg_color=_d_fg, hover_color=_d_hover,
            command=_d_cmd,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_row, text="🔄 Restart", width=90, height=32,
            fg_color="#3a3a5a", hover_color="#252540",
            state="disabled" if is_busy or not is_running else "normal",
            command=lambda sid=srv.id: self._restart_server(sid),
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            btn_row, text="⚙ Configurar", width=110, height=32,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            command=lambda sid=srv.id: self._open_server_panel(sid),
        ).pack(side="right")

    # ══════════════════════════════════════════════════════════════════════════
    # Painel de Servidor
    # ══════════════════════════════════════════════════════════════════════════

    def _open_server_panel(self, server_id: str) -> None:
        if server_id not in self._server_frames:
            srv = self.config_manager.get_server(server_id)
            if not srv:
                return
            frame = ctk.CTkFrame(self, corner_radius=0, fg_color=_BG)
            frame.grid(row=0, column=1, sticky="nsew")
            self._server_frames[server_id] = frame
            self._server_widgets[server_id] = {}
            self._build_server_panel(frame, srv)
            self._frames[f"server_{server_id}"] = frame

        self._show_frame(f"server_{server_id}")

    def _build_server_panel(self, parent: ctk.CTkFrame, srv: ServerConfig) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)  # row 2 = tabs (row 1 = lock banner)

        # Cabeçalho
        hdr = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=0, height=64)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            hdr, text="◀", width=36, height=36,
            fg_color="transparent", hover_color="#252540",
            command=lambda: self._show_frame("dashboard"),
        ).grid(row=0, column=0, padx=(12, 0), pady=14)

        inst = self.server_manager.get_instance(srv.id)
        status = inst.status if inst else SERVER_STATUS_STOPPED

        self._server_widgets[srv.id]["_name_title_var"] = tk.StringVar(value=srv.name)
        ctk.CTkLabel(
            hdr, textvariable=self._server_widgets[srv.id]["_name_title_var"],
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=1, padx=8, pady=14, sticky="w")

        status_var = tk.StringVar(value=_STATUS_LABEL.get(status, "PARADO"))
        status_lbl = ctk.CTkLabel(
            hdr, textvariable=status_var,
            text_color=_STATUS_COLOR.get(status, "#ff6666"),
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        status_lbl.grid(row=0, column=2, padx=12, pady=14)
        self._server_widgets[srv.id]["_status_var"] = status_var
        self._server_widgets[srv.id]["_status_lbl"] = status_lbl

        # Badge de visibilidade LAN/WAN (preenchido pelo callback _on_server_visibility_change)
        inst_now = self.server_manager.get_instance(srv.id)
        vis_mode = inst_now.online_mode if inst_now and hasattr(inst_now, "online_mode") else "—"
        vis_text  = "🌐 WAN" if vis_mode == "WAN" else ("🏠 LAN" if vis_mode == "LAN" else "")
        vis_color = _GREEN if vis_mode == "WAN" else ("#ffaa44" if vis_mode == "LAN" else "gray50")
        vis_lbl = ctk.CTkLabel(
            hdr, text=vis_text, text_color=vis_color,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        vis_lbl.grid(row=0, column=3, padx=(0, 8), pady=14)
        self._server_widgets[srv.id]["_visibility_lbl"] = vis_lbl

        ctrl = ctk.CTkFrame(hdr, fg_color="transparent")
        ctrl.grid(row=0, column=4, padx=(0, 16), pady=14)

        is_running = status == SERVER_STATUS_RUNNING
        is_busy    = status in (SERVER_STATUS_STARTING, SERVER_STATUS_STOPPING)

        def _toggle_server() -> None:
            inst = self.server_manager.get_instance(srv.id)
            if not inst:
                return
            if inst.status == SERVER_STATUS_RUNNING:
                self._stop_server(srv.id)
            elif inst.status in (SERVER_STATUS_STARTING, SERVER_STATUS_STOPPING):
                self.server_manager.stop_server(srv.id, force=True)
            else:
                self._start_server(srv.id)

        if is_busy:
            _ss_text   = "⚡ Cancelar"
            _ss_fg     = "#7a4a00"
            _ss_hover  = "#5c3600"
        elif is_running:
            _ss_text   = "⏹ Parar"
            _ss_fg     = _RED_DARK
            _ss_hover  = _RED_HOVER
        else:
            _ss_text   = "▶ Iniciar"
            _ss_fg     = _GREEN_DARK
            _ss_hover  = _GREEN_HOVER

        start_stop_btn = ctk.CTkButton(
            ctrl,
            text=_ss_text, width=110, height=34,
            fg_color=_ss_fg, hover_color=_ss_hover,
            command=_toggle_server,
        )
        start_stop_btn.pack(side="left", padx=(0, 6))
        self._server_widgets[srv.id]["_start_stop_btn"] = start_stop_btn

        ctk.CTkButton(
            ctrl, text="🔄", width=36, height=34,
            fg_color="#3a3a5a", hover_color="#252540",
            command=lambda: self._restart_server(srv.id),
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            ctrl, text="🗑 Remover", width=100, height=34,
            fg_color=_RED_DARK, hover_color=_RED_HOVER,
            command=lambda: self._confirm_remove_server(srv.id),
        ).pack(side="left")

        # Banner de bloqueio (visível apenas quando servidor não está parado)
        lock_banner = ctk.CTkFrame(parent, fg_color="#3a1a00", corner_radius=0, height=32)
        lock_banner.grid(row=1, column=0, sticky="ew")
        lock_banner.grid_propagate(False)
        lock_banner.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            lock_banner,
            text="🔒  Configurações bloqueadas — pare o servidor para editar",
            text_color="#ffaa44", font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, pady=6)
        self._server_widgets[srv.id]["_lock_banner"] = lock_banner
        is_stopped = status == SERVER_STATUS_STOPPED
        if is_stopped:
            lock_banner.grid_remove()

        # Abas
        tabs = ctk.CTkTabview(
            parent, fg_color=_CARD_BG, corner_radius=12,
            segmented_button_fg_color=_SIDEBAR_BG,
            segmented_button_selected_color=_GREEN_DARK,
            segmented_button_selected_hover_color=_GREEN_HOVER,
        )
        tabs.grid(row=2, column=0, padx=14, pady=12, sticky="nsew")
        self._server_widgets[srv.id]["_tabs"] = tabs

        for tab_name in ("Geral", "Jogo", "Avançado", "Mods", "Admins", "Jogadores", "Plugins", "Console RCON", "Logs"):
            tabs.add(tab_name)

        self._build_tab_general   (tabs.tab("Geral"),         srv)
        self._build_tab_game      (tabs.tab("Jogo"),          srv)
        self._build_tab_advanced  (tabs.tab("Avançado"),      srv)
        self._build_tab_mods      (tabs.tab("Mods"),          srv)
        self._build_tab_admins    (tabs.tab("Admins"),        srv)
        self._build_tab_jogadores (tabs.tab("Jogadores"),     srv)
        self._build_tab_plugins   (tabs.tab("Plugins"),       srv)
        self._build_tab_rcon      (tabs.tab("Console RCON"),  srv)
        self._build_tab_logs      (tabs.tab("Logs"),          srv)

        # Aplicar estado inicial de bloqueio se servidor não estiver parado
        if not is_stopped:
            self.after(100, lambda: self._set_config_editable(srv.id, False))

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Geral
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_general(self, parent, srv: ServerConfig) -> None:
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=4)
        scroll.grid_columnconfigure(1, weight=1)

        w = self._server_widgets[srv.id]

        def row(label: str, hint: str, var, row_n: int, is_pass: bool = False,
                browse: bool = False, combo: Optional[List] = None) -> None:
            lbl_fr = ctk.CTkFrame(scroll, fg_color="transparent")
            lbl_fr.grid(row=row_n, column=0, padx=(16, 8), pady=(4, 0), sticky="w")
            ctk.CTkLabel(lbl_fr, text=label, width=200, anchor="w",
                         text_color="gray65",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
            if hint:
                ctk.CTkLabel(lbl_fr, text=hint, width=200, anchor="w",
                             text_color="gray40",
                             font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))
            if combo:
                ent = ctk.CTkComboBox(scroll, variable=var, values=combo, width=340, height=34)
                ent.grid(row=row_n, column=1, padx=(0, 16), pady=4, sticky="w")
            elif browse:
                fr = ctk.CTkFrame(scroll, fg_color="transparent")
                fr.grid(row=row_n, column=1, padx=(0, 16), pady=4, sticky="ew")
                fr.grid_columnconfigure(0, weight=1)
                ctk.CTkEntry(fr, textvariable=var, height=34).grid(
                    row=0, column=0, sticky="ew", padx=(0, 6))
                ctk.CTkButton(fr, text="📁", width=34, height=34,
                              command=lambda v=var: self._browse_dir(v)).grid(row=0, column=1)
            else:
                ctk.CTkEntry(scroll, textvariable=var, height=34,
                             show="*" if is_pass else "").grid(
                    row=row_n, column=1, padx=(0, 16), pady=4, sticky="ew")

        w["name"]            = tk.StringVar(value=srv.name)
        w["install_dir"]     = tk.StringVar(value=srv.install_dir)
        w["server_name"]     = tk.StringVar(value=srv.server_name)
        w["map"]             = tk.StringVar(value=srv.map)
        w["server_password"] = tk.StringVar(value=srv.server_password)
        w["admin_password"]  = tk.StringVar(value=srv.admin_password)
        w["rcon_password"]   = tk.StringVar(value=srv.rcon_password)
        w["max_players"]     = tk.StringVar(value=str(srv.max_players))
        w["server_port"]     = tk.StringVar(value=str(srv.server_port))
        w["query_port"]      = tk.StringVar(value=str(srv.query_port))
        w["rcon_port"]       = tk.StringVar(value=str(srv.rcon_port))
        w["extra_args"]      = tk.StringVar(value=srv.extra_args)
        # active_event: armazena o label exibido; salvar converte de volta para ID
        _evt_label = _ARK_EVENT_ID_TO_LABEL.get(srv.active_event, srv.active_event)
        w["active_event"]    = tk.StringVar(value=_evt_label)
        w["auto_save"]       = tk.StringVar(value=str(srv.auto_save_period))

        self._section_lbl(scroll, 0, "🖥️  Identificação")
        row("Nome interno:",
            "Label exibido na barra lateral do app.",
            w["name"], 1)
        row("Diretório de Instalação:",
            "Pasta onde o ARK Server será instalado/atualizado.",
            w["install_dir"], 2, browse=True)
        row("Nome do Servidor:",
            "Nome visível na lista de servidores do jogo (Session Name).",
            w["server_name"], 3)

        self._section_lbl(scroll, 4, "🗺️  Mapa")
        row("Mapa:",
            "Selecione o mapa que o servidor irá rodar.",
            w["map"], 5, combo=[
                f"{ARK_MAP_NAMES.get(m, m)} ({m})" for m in ARK_MAPS
            ])

        self._section_lbl(scroll, 6, "🔌  Rede e Portas")
        row("Porta do Servidor:",
            "Porta principal UDP. Padrão: 7777. Liberar no roteador (UDP).",
            w["server_port"], 7)
        row("Porta de Query:",
            "Porta de consulta Steam. Padrão: 27015. Liberar no roteador (UDP).",
            w["query_port"], 8)
        row("Porta RCON:",
            "Porta do console remoto. Padrão: 27020. Só abrir se usar RCON externo.",
            w["rcon_port"], 9)

        self._section_lbl(scroll, 10, "🔒  Acesso")
        row("Senha do Servidor:",
            "Senha para entrar. Deixe vazio para servidor público.",
            w["server_password"], 11, is_pass=True)
        row("Senha de Admin:",
            "Usada para ativar cheats in-game (enablecheats). Mantenha secreta.",
            w["admin_password"], 12, is_pass=True)
        row("Senha RCON:",
            "Senha para conexão via console RCON. Geralmente igual à de admin.",
            w["rcon_password"], 13, is_pass=True)
        row("Máx. Jogadores:",
            "Limite de jogadores simultâneos no servidor.",
            w["max_players"], 14)

        self._section_lbl(scroll, 15, "⚙️  Opções de Inicialização")
        row("Evento Ativo:",
            "Selecione o evento oficial ou deixe vazio para nenhum.",
            w["active_event"], 16,
            combo=[v for _, v in _ARK_OFFICIAL_EVENTS])
        row("Auto-Save (min):",
            "Intervalo de salvamento automático em minutos. Padrão: 15.",
            w["auto_save"], 17)
        row("Argumentos Extras:",
            "Parâmetros adicionais de linha de comando. Ex: -ForceAllowCaveFlyers.",
            w["extra_args"], 18)

        w["rcon_enabled"]       = tk.BooleanVar(value=srv.rcon_enabled)
        w["use_battleye"]       = tk.BooleanVar(value=srv.use_battleye)
        w["use_allcores"]       = tk.BooleanVar(value=srv.use_allcores)
        w["force_respawn"]      = tk.BooleanVar(value=srv.force_respawn_dinos)
        w["whitelist_only"]     = tk.BooleanVar(value=srv.whitelist_only)
        w["auto_restart_crash"] = tk.BooleanVar(value=srv.auto_restart_on_crash)
        w["auto_update_start"]  = tk.BooleanVar(value=srv.auto_update_on_start)

        self._section_lbl(scroll, 19, "🔧  Flags")
        checkboxes = [
            ("Habilitar RCON",
             "Ativa o console remoto. Necessário para usar a aba Console RCON.",
             w["rcon_enabled"]),
            ("Usar BattlEye (anti-cheat)",
             "Proteção anti-cheat oficial. Desative para servidores com mods incompatíveis.",
             w["use_battleye"]),
            ("Usar todos os núcleos de CPU",
             "Permite que o servidor use todos os núcleos disponíveis na máquina.",
             w["use_allcores"]),
            ("Forçar respawn de dinos",
             "Reseta todos os dinos selvagens ao iniciar o servidor.",
             w["force_respawn"]),
            ("Apenas whitelist",
             "Somente jogadores na whitelist podem entrar no servidor.",
             w["whitelist_only"]),
            ("Auto-restart ao travar",
             "Reinicia o servidor automaticamente caso ocorra um crash.",
             w["auto_restart_crash"]),
            ("Atualizar servidor ao iniciar",
             "Verifica e aplica atualizações via SteamCMD antes de iniciar.",
             w["auto_update_start"]),
        ]
        for ci, (txt, hint_txt, var) in enumerate(checkboxes):
            cb_fr = ctk.CTkFrame(scroll, fg_color="transparent")
            cb_fr.grid(row=20 + ci, column=0, columnspan=2, padx=16, pady=(4, 0), sticky="w")
            ctk.CTkCheckBox(cb_fr, text=txt, variable=var,
                            checkmark_color="white", fg_color=_GREEN_DARK,
                            hover_color=_GREEN_HOVER).pack(anchor="w")
            ctk.CTkLabel(cb_fr, text=hint_txt, text_color="gray40",
                         font=ctk.CTkFont(size=10), anchor="w").pack(
                anchor="w", padx=(26, 0), pady=(0, 2))

        self._save_btn_row(scroll, 27, srv.id)

        # ── Seção Instalação ─────────────────────────────────────────────────
        self._section_lbl(scroll, 28, "⬇️  Instalação / Atualização do Servidor")
        inst_card = ctk.CTkFrame(scroll, corner_radius=12, fg_color=_CARD_BG)
        inst_card.grid(row=29, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="ew")
        inst_card.grid_columnconfigure(0, weight=1)

        btn_row = ctk.CTkFrame(inst_card, fg_color="transparent")
        btn_row.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="w")

        inst_btn = ctk.CTkButton(
            btn_row, text="⬇  Instalar / Atualizar Servidor",
            height=38, width=230,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=lambda sid=srv.id: self._run_server_install(sid, validate=False))
        inst_btn.grid(row=0, column=0, padx=(0, 10))

        val_btn = ctk.CTkButton(
            btn_row, text="✅  Verificar Arquivos (validate)",
            height=38, width=230,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            command=lambda sid=srv.id: self._run_server_install(sid, validate=True))
        val_btn.grid(row=0, column=1)

        ctk.CTkLabel(inst_card,
                     text="Usa o SteamCMD para baixar/atualizar os arquivos do servidor ARK: Survival Evolved (App 376030).\n"
                          "O 'Diretório de Instalação' acima deve estar preenchido. Salve antes de instalar.",
                     text_color="gray45", font=ctk.CTkFont(size=10), justify="left").grid(
            row=1, column=0, padx=16, pady=(0, 6), sticky="w")

        # status + log
        inst_status = ctk.CTkLabel(inst_card, text="", text_color="gray60",
                                   font=ctk.CTkFont(size=11))
        inst_status.grid(row=2, column=0, padx=16, pady=(0, 4), sticky="w")

        inst_log = ctk.CTkTextbox(
            inst_card, height=160, state="disabled",
            font=ctk.CTkFont(family="Consolas", size=10),
            fg_color="#0d0d18", text_color="#c8c8d8", corner_radius=6)
        inst_log.grid(row=3, column=0, padx=16, pady=(0, 14), sticky="ew")

        # guarda referências indexadas por server_id
        self._server_widgets[srv.id]["_inst_status"] = inst_status
        self._server_widgets[srv.id]["_inst_log"]    = inst_log
        self._server_widgets[srv.id]["_inst_btn"]    = inst_btn
        self._server_widgets[srv.id]["_val_btn"]     = val_btn

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Jogo
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_game(self, parent, srv: ServerConfig) -> None:
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=4)
        scroll.grid_columnconfigure(1, weight=1)

        w  = self._server_widgets[srv.id]
        gs = srv.game_settings

        def frow(label: str, hint: str, field: str, val: float, row_n: int,
                 frm: float = 0.0, to: float = 10.0) -> None:
            var = tk.DoubleVar(value=val)
            w[f"gs_{field}"] = var

            # Coluna 0: nome + dica
            lbl_fr = ctk.CTkFrame(scroll, fg_color="transparent")
            lbl_fr.grid(row=row_n, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
            ctk.CTkLabel(lbl_fr, text=label, width=290, anchor="w",
                         text_color="gray65",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
            if hint:
                ctk.CTkLabel(lbl_fr, text=hint, width=290, anchor="w",
                             text_color="gray40",
                             font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))

            # Coluna 2: entry editável
            entry_var = tk.StringVar(value=f"{val:.2f}")
            entry = ctk.CTkEntry(scroll, textvariable=entry_var, width=72, height=28,
                                 justify="right", text_color=_GREEN,
                                 font=ctk.CTkFont(size=12, weight="bold"))
            entry.grid(row=row_n, column=2, padx=(4, 14), pady=4)

            # Coluna 1: slider
            slider = ctk.CTkSlider(
                scroll, from_=frm, to=to, variable=var,
                command=lambda v, ev=entry_var: ev.set(f"{float(v):.2f}"),
            )
            slider.grid(row=row_n, column=1, padx=4, pady=4, sticky="ew")

            def _commit(event=None, _var=var, _ev=entry_var, _frm=frm, _to=to):
                try:
                    v = float(_ev.get().replace(",", "."))
                    v = max(_frm, min(_to, v))
                    _var.set(v)
                    _ev.set(f"{v:.2f}")
                except ValueError:
                    _ev.set(f"{_var.get():.2f}")

            entry.bind("<Return>", _commit)
            entry.bind("<FocusOut>", _commit)

        def irow(label: str, hint: str, field: str, val: int, row_n: int) -> None:
            w[f"gs_{field}"] = tk.StringVar(value=str(val))
            lbl_fr = ctk.CTkFrame(scroll, fg_color="transparent")
            lbl_fr.grid(row=row_n, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
            ctk.CTkLabel(lbl_fr, text=label, width=290, anchor="w",
                         text_color="gray65",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
            if hint:
                ctk.CTkLabel(lbl_fr, text=hint, width=290, anchor="w",
                             text_color="gray40",
                             font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))
            ctk.CTkEntry(scroll, textvariable=w[f"gs_{field}"], width=120, height=28).grid(
                row=row_n, column=1, padx=4, pady=4, sticky="w")

        def brow(label: str, field: str, val: bool, row_n: int) -> None:
            w[f"gs_{field}"] = tk.BooleanVar(value=val)
            ctk.CTkCheckBox(scroll, text=label, variable=w[f"gs_{field}"],
                            checkmark_color="white", fg_color=_GREEN_DARK,
                            hover_color=_GREEN_HOVER).grid(
                row=row_n, column=0, columnspan=3, padx=16, pady=4, sticky="w")

        r = 0
        self._section_lbl(scroll, r, "⚙️  Dificuldade")
        r += 1
        frow("Nível de Dificuldade",
             "Padrão: 0.20 — Aumentar eleva o nível máximo dos dinos selvagens.",
             "difficulty_offset", gs.difficulty_offset, r, 0, 1)
        r += 1
        frow("Dificuldade Máxima (Override)",
             "Ex: 5.0 = dinos até nível 150. Aumente para dinos mais difíceis.",
             "override_official_difficulty", gs.override_official_difficulty, r, 1, 10)
        r += 1

        self._section_lbl(scroll, r, "📈  XP")
        r += 1
        frow("Multiplicador de XP Geral",
             "Multiplica todo o XP ganho. Aumente para progredir mais rápido.",
             "xp_multiplier", gs.xp_multiplier, r)
        r += 1
        frow("XP por Abate",
             "Multiplica o XP ganho ao matar criaturas.",
             "kill_xp_multiplier", gs.kill_xp_multiplier, r)
        r += 1
        frow("XP por Coleta",
             "Multiplica o XP ganho ao coletar recursos.",
             "harvest_xp_multiplier", gs.harvest_xp_multiplier, r)
        r += 1
        frow("XP por Craft",
             "Multiplica o XP ganho ao fabricar itens.",
             "craft_xp_multiplier", gs.craft_xp_multiplier, r)
        r += 1
        frow("XP Genérico",
             "Multiplica o XP de fontes diversas.",
             "generic_xp_multiplier", gs.generic_xp_multiplier, r)
        r += 1
        frow("XP Especial",
             "Multiplica o XP de eventos e fontes especiais.",
             "special_xp_multiplier", gs.special_xp_multiplier, r)
        r += 1

        self._section_lbl(scroll, r, "👤  Jogador")
        r += 1
        frow("Dano do Jogador",
             "Aumenta o dano causado pelo jogador. Ex: 2.0 = dano dobrado.",
             "player_damage_multiplier", gs.player_damage_multiplier, r)
        r += 1
        frow("Resistência do Jogador",
             "Reduz o dano recebido. Menor = mais resistente ao dano.",
             "player_resistance_multiplier", gs.player_resistance_multiplier, r)
        r += 1
        frow("Consumo de Água",
             "Taxa de consumo de água. Menor = seca mais devagar.",
             "player_character_water_drain_multiplier",
             gs.player_character_water_drain_multiplier, r)
        r += 1
        frow("Consumo de Comida",
             "Taxa de consumo de comida. Menor = fica com fome mais devagar.",
             "player_character_food_drain_multiplier",
             gs.player_character_food_drain_multiplier, r)
        r += 1
        frow("Regeneração de Vida",
             "Velocidade de recuperação de HP. Maior = recupera mais rápido.",
             "player_character_health_recovery_multiplier",
             gs.player_character_health_recovery_multiplier, r)
        r += 1
        frow("Consumo de Stamina",
             "Taxa de consumo de stamina. Menor = cansa mais devagar.",
             "player_character_stamina_drain_multiplier",
             gs.player_character_stamina_drain_multiplier, r)
        r += 1

        self._section_lbl(scroll, r, "🦖  Dinos")
        r += 1
        frow("Dano dos Dinos",
             "Aumenta o dano causado pelos dinos selvagens.",
             "dino_damage_multiplier", gs.dino_damage_multiplier, r)
        r += 1
        frow("Resistência dos Dinos",
             "Reduz o dano recebido pelos dinos. Menor = dinos mais resistentes.",
             "dino_resistance_multiplier", gs.dino_resistance_multiplier, r)
        r += 1
        frow("Regeneração dos Dinos",
             "Velocidade de recuperação de HP dos dinos.",
             "dino_character_health_recovery_multiplier",
             gs.dino_character_health_recovery_multiplier, r)
        r += 1
        frow("Consumo de Comida dos Dinos",
             "Taxa de consumo de comida dos dinos. Menor = comem mais devagar.",
             "dino_character_food_drain_multiplier",
             gs.dino_character_food_drain_multiplier, r)
        r += 1
        frow("Quantidade de Dinos no Mapa",
             "Multiplica a quantidade de dinos. Ex: 2.0 = dobro de dinos selvagens.",
             "dino_count_multiplier", gs.dino_count_multiplier, r)
        r += 1
        irow("Máx. Dinos Domesticados",
             "Limite total de dinos domesticados no servidor.",
             "max_tamed_dinos", gs.max_tamed_dinos, r)
        r += 1

        self._section_lbl(scroll, r, "🥚  Criação / Imprinting")
        r += 1
        frow("Velocidade de Domesticação",
             "Maior = domestica mais rápido. Ex: 3.0 = 3× mais rápido.",
             "taming_speed_multiplier", gs.taming_speed_multiplier, r)
        r += 1
        frow("Intervalo de Acasalamento",
             "Menor = pode acasalar com mais frequência.",
             "mating_interval_multiplier", gs.mating_interval_multiplier, r)
        r += 1
        frow("Velocidade de Chocagem",
             "Maior = ovos chocam mais rápido.",
             "egg_hatch_speed_multiplier", gs.egg_hatch_speed_multiplier, r)
        r += 1
        frow("Intervalo de Postura de Ovos",
             "Menor = dinos põem ovos com mais frequência.",
             "lay_egg_interval_multiplier", gs.lay_egg_interval_multiplier, r)
        r += 1
        frow("Velocidade de Crescimento do Filhote",
             "Maior = filhotes crescem mais rápido.",
             "baby_mature_speed_multiplier", gs.baby_mature_speed_multiplier, r, 0, 100)
        r += 1
        frow("Velocidade de Nascimento do Filhote",
             "Maior = filhotes vivíparos nascem mais rápido.",
             "baby_hatch_speed_multiplier", gs.baby_hatch_speed_multiplier, r, 0, 100)
        r += 1
        frow("Consumo de Comida do Filhote",
             "Menor = filhotes comem menos (mais fácil de criar).",
             "baby_food_consumption_speed_multiplier",
             gs.baby_food_consumption_speed_multiplier, r)
        r += 1
        frow("Intervalo de Carinho (Imprint)",
             "Menor = menos tempo entre os pedidos de carinho do filhote.",
             "baby_cuddle_interval_multiplier", gs.baby_cuddle_interval_multiplier, r)
        r += 1
        frow("Tolerância de Atraso do Imprint",
             "Maior = mais tempo para responder ao pedido de carinho sem perder %.",
             "baby_cuddle_grace_period_multiplier",
             gs.baby_cuddle_grace_period_multiplier, r)
        r += 1
        frow("Bônus de Stats por Imprint",
             "Maior = mais bônus de stats ao completar 100% de imprint.",
             "baby_imprinting_stat_scale_multiplier",
             gs.baby_imprinting_stat_scale_multiplier, r)
        r += 1

        self._section_lbl(scroll, r, "🌾  Coleta / Recursos")
        r += 1
        frow("Quantidade de Coleta",
             "Mais recursos por coleta. Ex: 3.0 = 3× mais recursos.",
             "harvest_amount_multiplier", gs.harvest_amount_multiplier, r)
        r += 1
        frow("Durabilidade dos Recursos",
             "Maior = rochas/árvores duram mais antes de destruir.",
             "harvest_health_multiplier", gs.harvest_health_multiplier, r)
        r += 1
        frow("Reaparecimento de Recursos",
             "Menor = recursos reaparecem mais rápido no mapa.",
             "resource_respawn_period_multiplier",
             gs.resource_respawn_period_multiplier, r)
        r += 1
        frow("Velocidade de Crescimento das Plantas",
             "Maior = plantas nas estufas crescem mais rápido.",
             "crop_growth_speed_multiplier", gs.crop_growth_speed_multiplier, r)
        r += 1
        frow("Apodrecimento das Plantas",
             "Menor = plantas demoram mais para apodrecer.",
             "crop_decay_speed_multiplier", gs.crop_decay_speed_multiplier, r)
        r += 1
        frow("Tamanho de Stack",
             "Multiplica o limite de empilhamento. Ex: 2.0 = stacks dobrados.",
             "item_stack_size_multiplier", gs.item_stack_size_multiplier, r)
        r += 1
        frow("Tempo de Estragamento",
             "Maior = comida demora mais para estragar.",
             "spoiling_time_multiplier", gs.spoiling_time_multiplier, r)
        r += 1
        frow("Tempo de Decomposição de Itens",
             "Maior = itens largados no chão demoram mais para sumir.",
             "item_decomposition_time_multiplier",
             gs.item_decomposition_time_multiplier, r)
        r += 1
        frow("Qualidade de Loot de Pesca",
             "Maior = itens de melhor qualidade ao pescar.",
             "fishing_loot_quality_multiplier", gs.fishing_loot_quality_multiplier, r)
        r += 1

        self._section_lbl(scroll, r, "🏗️  Estruturas")
        r += 1
        frow("Dano às Estruturas",
             "Aumenta o dano causado às estruturas por jogadores/dinos.",
             "structure_damage_multiplier", gs.structure_damage_multiplier, r)
        r += 1
        frow("Resistência das Estruturas",
             "Menor = estruturas mais resistentes (recebem menos dano).",
             "structure_resistance_multiplier", gs.structure_resistance_multiplier, r)
        r += 1
        irow("Cooldown de Reparo (s)",
             "Segundos de espera para reparar após receber dano.",
             "structure_damage_repair_cooldown",
             gs.structure_damage_repair_cooldown, r)
        r += 1
        frow("Decaimento de Estruturas (PvE)",
             "Maior = estruturas sem dono demoram mais para decair.",
             "pve_structure_decay_period_multiplier",
             gs.pve_structure_decay_period_multiplier, r)
        r += 1
        frow("Estruturas em Plataformas",
             "Multiplica o limite de estruturas em platform saddles.",
             "per_platform_max_structures_multiplier",
             gs.per_platform_max_structures_multiplier, r)
        r += 1
        frow("Área de Build em Saddles",
             "Multiplica a área construível ao redor de platform saddles.",
             "platform_saddle_build_area_bounds_multiplier",
             gs.platform_saddle_build_area_bounds_multiplier, r)
        r += 1

        self._section_lbl(scroll, r, "🏆  Tribal / Misc")
        r += 1
        irow("Tamanho Máximo da Tribo",
             "Número máximo de membros por tribo.",
             "max_tribe_size", gs.max_tribe_size, r)
        r += 1
        frow("Tempo para Expulsar AFK (s)",
             "Segundos até expulsar jogadores inativos. 0 = desativado.",
             "kick_idle_players_period", gs.kick_idle_players_period, r, 0, 7200)
        r += 1
        irow("XP Máximo do Jogador (Override)",
             "Substitui o limite padrão de XP dos jogadores.",
             "override_max_experience_points_player",
             gs.override_max_experience_points_player, r)
        r += 1
        irow("XP Máximo do Dino (Override)",
             "Substitui o limite padrão de XP dos dinos.",
             "override_max_experience_points_dino",
             gs.override_max_experience_points_dino, r)
        r += 1

        self._section_lbl(scroll, r, "🎮  Opções do Servidor")
        r += 1
        brow("PvP Ativado",                              "server_pvp",                  gs.server_pvp,                  r)
        r += 1
        brow("Modo Hardcore (morte permanente)",         "server_hardcore",             gs.server_hardcore,             r)
        r += 1
        brow("Dinos Voadores Carregam Jogadores (PvE)",  "allow_flyer_carry_pve",       gs.allow_flyer_carry_pve,       r)
        r += 1
        brow("Terceira Pessoa Permitida",                "allow_third_person_player",   gs.allow_third_person_player,   r)
        r += 1
        brow("Mostrar Localização no Mapa",              "show_map_player_location",    gs.show_map_player_location,    r)
        r += 1
        brow("Desativar Decaimento de Estruturas (PvE)", "disable_structure_decay_pve", gs.disable_structure_decay_pve, r)
        r += 1
        brow("Desativar Decaimento de Dinos (PvE)",      "disable_dino_decay_pve",      gs.disable_dino_decay_pve,      r)
        r += 1
        brow("Proteção Offline (ORP)",                   "prevent_offline_pvp",         gs.prevent_offline_pvp,         r)
        r += 1
        brow("Bloquear Downloads de Tributos",           "no_tribute_downloads",        gs.no_tribute_downloads,        r)
        r += 1
        brow("Notificar quando Jogador Entrar",          "always_notify_player_joined", gs.always_notify_player_joined, r)
        r += 1
        brow("Notificar quando Jogador Sair",            "always_notify_player_left",   gs.always_notify_player_left,   r)
        r += 1

        self._save_btn_row(scroll, r + 1, srv.id)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Avançado / Cross-ARK
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_advanced(self, parent, srv: ServerConfig) -> None:
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=4)
        scroll.grid_columnconfigure(1, weight=1)

        w   = self._server_widgets[srv.id]
        adv = srv.advanced_settings
        cl  = srv.cluster

        def brow(label: str, hint: str, field: str, val: bool, row_n: int, prefix: str = "adv_") -> None:
            w[f"{prefix}{field}"] = tk.BooleanVar(value=val)
            cb_fr = ctk.CTkFrame(scroll, fg_color="transparent")
            cb_fr.grid(row=row_n, column=0, columnspan=2, padx=16, pady=(4, 0), sticky="w")
            ctk.CTkCheckBox(cb_fr, text=label, variable=w[f"{prefix}{field}"],
                            checkmark_color="white", fg_color=_GREEN_DARK,
                            hover_color=_GREEN_HOVER).pack(anchor="w")
            if hint:
                ctk.CTkLabel(cb_fr, text=hint, text_color="gray40",
                             font=ctk.CTkFont(size=10), anchor="w").pack(
                    anchor="w", padx=(26, 0), pady=(0, 2))

        def frow(label: str, hint: str, field: str, val: float, row_n: int, prefix: str = "adv_") -> None:
            w[f"{prefix}{field}"] = tk.StringVar(value=str(val))
            lbl_fr = ctk.CTkFrame(scroll, fg_color="transparent")
            lbl_fr.grid(row=row_n, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
            ctk.CTkLabel(lbl_fr, text=label, width=310, anchor="w",
                         text_color="gray65",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
            if hint:
                ctk.CTkLabel(lbl_fr, text=hint, width=310, anchor="w",
                             text_color="gray40",
                             font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))
            ctk.CTkEntry(scroll, textvariable=w[f"{prefix}{field}"], width=120, height=28).grid(
                row=row_n, column=1, padx=4, pady=4, sticky="w")

        r = 0
        self._section_lbl(scroll, r, "🌐  Cross-ARK (Cluster)")
        r += 1
        brow("Habilitar Cluster (Cross-ARK)",
             "Permite que múltiplos servidores compartilhem tribos, dinos e itens entre si.",
             "enabled", cl.enabled, r, "cl_")
        r += 1

        w["cl_cluster_id"]  = tk.StringVar(value=cl.cluster_id)
        w["cl_cluster_dir"] = tk.StringVar(value=cl.cluster_dir_override)

        cid_fr = ctk.CTkFrame(scroll, fg_color="transparent")
        cid_fr.grid(row=r, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
        ctk.CTkLabel(cid_fr, text="ID do Cluster:", width=310, anchor="w",
                     text_color="gray65",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(cid_fr, text="Identificador único do cluster. Todos os servidores do mesmo cluster devem usar o mesmo ID.",
                     width=310, anchor="w", text_color="gray40",
                     font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))
        ctk.CTkEntry(scroll, textvariable=w["cl_cluster_id"], height=30,
                     placeholder_text="Ex: MeuCluster123").grid(
            row=r, column=1, padx=4, pady=4, sticky="ew")
        r += 1

        cdir_fr = ctk.CTkFrame(scroll, fg_color="transparent")
        cdir_fr.grid(row=r, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
        ctk.CTkLabel(cdir_fr, text="Pasta do Cluster:", width=310, anchor="w",
                     text_color="gray65",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(cdir_fr, text="Pasta compartilhada para transferência de dados entre servidores. Opcional.",
                     width=310, anchor="w", text_color="gray40",
                     font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))
        dir_fr = ctk.CTkFrame(scroll, fg_color="transparent")
        dir_fr.grid(row=r, column=1, padx=4, pady=4, sticky="ew")
        dir_fr.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(dir_fr, textvariable=w["cl_cluster_dir"], height=30).grid(
            row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(dir_fr, text="📁", width=34, height=30,
                      command=lambda: self._browse_dir(w["cl_cluster_dir"])).grid(row=0, column=1)
        r += 1

        self._section_lbl(scroll, r, "🚫  Restrições de Transferência (Cross-ARK)")
        r += 1
        brow("Bloquear Download de Sobreviventes",
             "Impede jogadores de importar personagens de outros servidores do cluster.",
             "prevent_download_survivors", adv.prevent_download_survivors, r)
        r += 1
        brow("Bloquear Download de Itens",
             "Impede jogadores de trazer itens de outros servidores do cluster.",
             "prevent_download_items",     adv.prevent_download_items,     r)
        r += 1
        brow("Bloquear Download de Dinos",
             "Impede jogadores de trazer dinos domesticados de outros servidores.",
             "prevent_download_dinos",     adv.prevent_download_dinos,     r)
        r += 1
        brow("Bloquear Upload de Sobreviventes",
             "Impede jogadores de enviar seus personagens para o cluster.",
             "prevent_upload_survivors",   adv.prevent_upload_survivors,   r)
        r += 1
        brow("Bloquear Upload de Itens",
             "Impede jogadores de enviar itens ao cluster.",
             "prevent_upload_items",       adv.prevent_upload_items,       r)
        r += 1
        brow("Bloquear Upload de Dinos",
             "Impede jogadores de enviar dinos ao cluster.",
             "prevent_upload_dinos",       adv.prevent_upload_dinos,       r)
        r += 1
        brow("Bloquear Transferência por Filtro",
             "Impede transferências bloqueadas por restrições de filtro de mapa.",
             "no_transfer_from_filtering", adv.no_transfer_from_filtering, r)
        r += 1

        self._section_lbl(scroll, r, "⚙️  Game.ini Avançado")
        r += 1
        brow("Nerf de Criôpod Ativado",
             "Aplica penalidade de dano em dinos recém-lançados do criôpod. Útil para PvP.",
             "enable_cryopod_nerf",                       adv.enable_cryopod_nerf,                       r)
        r += 1
        frow("Duração do Nerf de Criôpod (s)",
             "Quantos segundos dura a penalidade após sair do criôpod.",
             "cryopod_nerf_duration",                     adv.cryopod_nerf_duration,                     r)
        r += 1
        frow("Mult. de Dano do Nerf",
             "Fator de dano enquanto o nerf está ativo. Ex: 0.01 = apenas 1% do dano normal.",
             "cryopod_nerf_damage_mult",                  adv.cryopod_nerf_damage_mult,                  r)
        r += 1
        brow("Spawnar Supply Crates em Estruturas",
             "Permite que supply crates apareçam sobre estruturas construídas.",
             "allow_crateSpawns_on_top_of_structures",    adv.allow_crateSpawns_on_top_of_structures,    r)
        r += 1
        brow("Otimizar HP de Coleta",
             "Melhora a performance ao calcular HP de recursos coletáveis.",
             "use_optimized_harvesting_health",           adv.use_optimized_harvesting_health,           r)
        r += 1
        brow("Defesas Passivas Atacam Dinos sem Cavaleiro",
             "Torretas e armadilhas atacam dinos selvagens e sem piloto.",
             "b_passive_defenses_damage_riderless_dinos", adv.b_passive_defenses_damage_riderless_dinos, r)
        r += 1
        brow("Chat de Voz Global",
             "Todos os jogadores se ouvem independente da distância.",
             "global_voice_chat",                         adv.global_voice_chat,                         r)
        r += 1
        brow("Chat de Voz por Proximidade",
             "Somente jogadores próximos se ouvem. Tem prioridade sobre o Chat Global.",
             "proximity_chat",                            adv.proximity_chat,                            r)
        r += 1
        brow("Alimentar Dino de Raid",
             "Permite que o Titanossauro (raid dino) seja alimentado.",
             "allow_raid_dino_feeding",                   adv.allow_raid_dino_feeding,                   r)
        r += 1
        frow("Consumo de Comida do Dino de Raid",
             "Taxa de consumo de comida do Titanossauro. Menor = come mais devagar.",
             "raid_dino_character_food_drain_multiplier", adv.raid_dino_character_food_drain_multiplier, r)
        r += 1
        frow("Mult. Velocidade de Nado (Oxigênio)",
             "Multiplica a velocidade de nado baseada no stat de oxigênio.",
             "oxygen_swim_speed_stat_multiplier",         adv.oxygen_swim_speed_stat_multiplier,         r)
        r += 1
        frow("Dano de Coleta dos Dinos",
             "Multiplica o dano que dinos causam ao coletar recursos.",
             "dino_harvesting_damage_multiplier",         adv.dino_harvesting_damage_multiplier,         r)
        r += 1
        frow("Dano de Coleta dos Jogadores",
             "Multiplica o dano que jogadores causam ao coletar recursos.",
             "player_harvesting_damage_multiplier",       adv.player_harvesting_damage_multiplier,       r)
        r += 1
        frow("Habilidade em Receitas Customizadas",
             "Influencia as stats da receita baseado na habilidade do personagem.",
             "custom_recipe_skill_multiplier",            adv.custom_recipe_skill_multiplier,            r)
        r += 1
        frow("Efetividade de Receitas Customizadas",
             "Multiplica os bônus de stats obtidos em receitas customizadas.",
             "custom_recipe_effectiveness_multiplier",    adv.custom_recipe_effectiveness_multiplier,    r)
        r += 1
        brow("PvE Automático com Timer",
             "Alterna automaticamente entre PvP e PvE conforme o horário definido.",
             "b_auto_pve_timer",                          adv.b_auto_pve_timer,                          r)
        r += 1
        brow("PvE Automático usa Hora do Sistema",
             "Usa o horário do servidor (SO) para calcular o timer de PvE automático.",
             "b_auto_pve_use_system_time",                adv.b_auto_pve_use_system_time,                r)
        r += 1
        frow("Início do PvE Automático (s do dia)",
             "Segundo do dia (0–86400) em que o PvE começa. Ex: 0 = meia-noite.",
             "auto_pve_start_time_seconds",               adv.auto_pve_start_time_seconds,               r)
        r += 1
        frow("Fim do PvE Automático (s do dia)",
             "Segundo do dia (0–86400) em que o PvE termina.",
             "auto_pve_stop_time_seconds",                adv.auto_pve_stop_time_seconds,                r)
        r += 1
        brow("Forçar Bloqueio em Estruturas",
             "Todas as estruturas são criadas bloqueadas por padrão.",
             "force_all_structure_locking",               adv.force_all_structure_locking,               r)
        r += 1
        brow("Forçar Explosivos em Voadores",
             "Dinos voadores podem transportar C4 e explosivos em PvP.",
             "force_flyer_explosives",                    adv.force_flyer_explosives,                    r)
        r += 1

        # ── Importar / Sincronizar INI ────────────────────────────────────────
        self._section_lbl(scroll, r + 1, "📂  GameUserSettings.ini / Game.ini")
        r += 2
        ini_card = ctk.CTkFrame(scroll, corner_radius=10, fg_color=_CARD_BG)
        ini_card.grid(row=r, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="ew")
        ini_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            ini_card,
            text="Importe as configurações diretamente dos arquivos INI do servidor, "
                 "ou copie os INIs para outros servidores do cluster.",
            text_color="gray55", font=ctk.CTkFont(size=10), justify="left",
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(10, 6), sticky="w")

        btn_row_ini = ctk.CTkFrame(ini_card, fg_color="transparent")
        btn_row_ini.grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 12), sticky="w")

        ctk.CTkButton(
            btn_row_ini,
            text="⬆️  Importar INI do Disco",
            height=36, width=200,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            command=lambda sid=srv.id: self._import_ini_from_disk(sid),
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row_ini,
            text="🔄  Sincronizar INI com Servidores",
            height=36, width=230,
            fg_color="#6a3aaa", hover_color="#7a4abb",
            command=lambda sid=srv.id: self._open_sync_ini_dialog(sid),
        ).pack(side="left")
        r += 1

        self._save_btn_row(scroll, r + 2, srv.id)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Mods
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_mods(self, parent, srv: ServerConfig) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        w = self._server_widgets[srv.id]

        add_card = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
        add_card.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        add_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(add_card, text="🔧  Steam Workshop Mod ID:",
                     text_color="gray60").grid(row=0, column=0, padx=16, pady=(14, 4))
        w["new_mod_id"] = tk.StringVar()
        ctk.CTkEntry(add_card, textvariable=w["new_mod_id"], height=34,
                     placeholder_text="Ex: 731604991").grid(
            row=0, column=1, padx=(0, 8), pady=(14, 4), sticky="ew")
        ctk.CTkButton(
            add_card, text="➕ Adicionar", width=110, height=34,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=lambda: self._add_mod(srv.id),
        ).grid(row=0, column=2, padx=(0, 8), pady=(14, 4))
        ctk.CTkButton(
            add_card, text="🔍 Buscar Workshop", width=150, height=34,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            command=lambda: self._open_mod_search_dialog(srv.id),
        ).grid(row=0, column=3, padx=(0, 16), pady=(14, 4))

        ctk.CTkLabel(
            add_card,
            text="💡  Cole o ID do mod (número) ou use 🔍 para buscar pelo nome. Você pode encontrar o ID na URL da página do Workshop.",
            text_color="gray45", font=ctk.CTkFont(size=10), wraplength=700, justify="left",
        ).grid(row=1, column=0, columnspan=4, padx=16, pady=(0, 10), sticky="w")

        if not self.mod_manager.is_steamcmd_available():
            ctk.CTkLabel(
                add_card,
                text="⚠️  SteamCMD não configurado. Configure o caminho nas Configurações Globais.",
                text_color="#ffaa44", font=ctk.CTkFont(size=11),
            ).grid(row=2, column=0, columnspan=4, padx=16, pady=(0, 10), sticky="w")

        mods_card = ctk.CTkScrollableFrame(parent, corner_radius=10, fg_color=_CARD_BG)
        mods_card.grid(row=1, column=0, padx=12, pady=6, sticky="nsew")
        mods_card.grid_columnconfigure(0, weight=1)
        w["_mods_list_frame"] = mods_card

        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.grid(row=2, column=0, padx=12, pady=(4, 12), sticky="ew")

        ctk.CTkButton(
            actions, text="⬇️  Baixar / Atualizar Todos os Mods",
            height=38, fg_color=_BLUE, hover_color=_BLUE_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: self._download_all_mods(srv.id),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            actions, text="💾  Salvar Lista de Mods",
            height=38, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=lambda: self._save_server_config(srv.id),
        ).pack(side="left")

        self._refresh_mods_list(srv.id)
        self._build_auto_update_panel(parent, srv)

    def _build_auto_update_panel(self, parent, srv: ServerConfig) -> None:
        """Card de atualização automática de mods, embutido na aba Mods."""
        w = self._server_widgets[srv.id]
        card = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
        card.grid(row=3, column=0, padx=12, pady=(4, 12), sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        # ── Título ────────────────────────────────────────────────────────────
        ctk.CTkLabel(
            card, text="🔄  Atualização Automática de Mods",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, columnspan=4, padx=16, pady=(12, 4), sticky="w")

        ctk.CTkLabel(
            card,
            text="Verifica periodicamente o Steam Workshop. Quando um mod for atualizado, "
                 "avisa os jogadores via broadcast, aguarda o tempo configurado e reinicia o servidor.",
            text_color="gray55", font=ctk.CTkFont(size=10), wraplength=750, justify="left",
        ).grid(row=1, column=0, columnspan=4, padx=16, pady=(0, 8), sticky="w")

        # ── Linha de configurações ────────────────────────────────────────────
        cfg_row = ctk.CTkFrame(card, fg_color="transparent")
        cfg_row.grid(row=2, column=0, columnspan=4, padx=12, pady=(0, 8), sticky="ew")

        ctk.CTkLabel(cfg_row, text="Intervalo de verificação (min):",
                     text_color="gray70").pack(side="left", padx=(4, 4))
        w["_au_interval_var"] = tk.StringVar(value="15")
        ctk.CTkEntry(cfg_row, textvariable=w["_au_interval_var"], width=60, height=30,
                     justify="center").pack(side="left", padx=(0, 16))

        ctk.CTkLabel(cfg_row, text="Aviso antecipado (min):",
                     text_color="gray70").pack(side="left", padx=(0, 4))
        w["_au_warning_var"] = tk.StringVar(value="5")
        ctk.CTkEntry(cfg_row, textvariable=w["_au_warning_var"], width=60, height=30,
                     justify="center").pack(side="left", padx=(0, 16))

        # ── Botão ligar/desligar ──────────────────────────────────────────────
        is_active = (
            self._mod_auto_updater is not None and self._mod_auto_updater.enabled
        )
        w["_au_toggle_btn"] = ctk.CTkButton(
            cfg_row,
            text="⏸ Parar" if is_active else "▶ Ativar",
            width=110, height=30,
            fg_color=_RED_DARK if is_active else _GREEN_DARK,
            hover_color=_RED_HOVER if is_active else _GREEN_HOVER,
            command=lambda sid=srv.id: self._toggle_mod_auto_updater(sid),
        )
        w["_au_toggle_btn"].pack(side="left", padx=(0, 8))

        # status pill
        w["_au_status_lbl"] = ctk.CTkLabel(
            cfg_row,
            text="● ATIVO" if is_active else "● INATIVO",
            text_color=_GREEN if is_active else "gray50",
            font=ctk.CTkFont(size=11, weight="bold"),
        )
        w["_au_status_lbl"].pack(side="left")

        # ── Log ───────────────────────────────────────────────────────────────
        log_box = ctk.CTkTextbox(card, height=100, state="disabled",
                                 font=ctk.CTkFont(family="Courier New", size=10))
        log_box._textbox.tag_configure("info",    foreground="#e0e0e0")
        log_box._textbox.tag_configure("warning", foreground="#ffaa44")
        log_box._textbox.tag_configure("error",   foreground="#ff6666")
        log_box._textbox.tag_configure("debug",   foreground="#888888")
        log_box.grid(row=3, column=0, columnspan=4, padx=12, pady=(0, 12), sticky="ew")
        w["_au_log_box"] = log_box
        # Registra o log box global (última instância criada serve como painel)
        self._auto_updater_log_box = log_box

    def _toggle_mod_auto_updater(self, server_id: str) -> None:
        """Liga/desliga o verificador automático de mods."""
        w = self._server_widgets.get(server_id, {})
        try:
            interval  = max(1, int(w.get("_au_interval_var", tk.StringVar(value="15")).get()))
            warn_mins = max(1, int(w.get("_au_warning_var",  tk.StringVar(value="5")).get()))
        except ValueError:
            interval, warn_mins = 15, 5

        if self._mod_auto_updater and self._mod_auto_updater.enabled:
            self._mod_auto_updater.stop()
            for sid, ww in self._server_widgets.items():
                btn = ww.get("_au_toggle_btn")
                lbl = ww.get("_au_status_lbl")
                if btn:
                    btn.configure(text="▶ Ativar", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER)
                if lbl:
                    lbl.configure(text="● INATIVO", text_color="gray50")
        else:
            if self._mod_auto_updater is None:
                self._mod_auto_updater = ModAutoUpdater(
                    server_manager=self.server_manager,
                    mod_manager=self.mod_manager,
                    get_servers=lambda: self.config_manager.servers,
                    on_log=self._on_auto_updater_log,
                    check_interval_minutes=interval,
                    warning_minutes=warn_mins,
                )
            else:
                self._mod_auto_updater.set_interval(interval)
                self._mod_auto_updater.set_warning_minutes(warn_mins)
            self._mod_auto_updater.start()
            for sid, ww in self._server_widgets.items():
                btn = ww.get("_au_toggle_btn")
                lbl = ww.get("_au_status_lbl")
                if btn:
                    btn.configure(text="⏸ Parar", fg_color=_RED_DARK, hover_color=_RED_HOVER)
                if lbl:
                    lbl.configure(text="● ATIVO", text_color=_GREEN)

    def _refresh_mods_list(self, server_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return
        w = self._server_widgets.get(server_id, {})
        frame: Optional[ctk.CTkScrollableFrame] = w.get("_mods_list_frame")
        if not frame:
            return

        for child in frame.winfo_children():
            child.destroy()

        if not srv.mods:
            ctk.CTkLabel(frame, text="Nenhum mod adicionado.",
                         text_color="gray50").pack(pady=20)
            return

        missing_names = [mid for mid in srv.mods if not srv.mod_names.get(mid)]
        if missing_names:
            self._fetch_mod_names_async(server_id, missing_names)

        for idx, mod_id in enumerate(srv.mods):
            row_bg = "#252538" if idx % 2 == 0 else "transparent"
            row_f = ctk.CTkFrame(frame, fg_color=row_bg, corner_radius=6, height=40)
            row_f.pack(fill="x", pady=1)
            row_f.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(row_f, text=f"#{idx+1}", width=32, text_color="gray50",
                         font=ctk.CTkFont(size=11)).grid(row=0, column=0, padx=(8, 4))

            mod_name = srv.mod_names.get(mod_id, "")
            display = f"{mod_id} - {mod_name}" if mod_name else mod_id
            ctk.CTkLabel(row_f, text=display,
                         font=ctk.CTkFont(family="Courier New", size=13)).grid(
                row=0, column=1, padx=4, sticky="w")

            installed = self.mod_manager.check_mod_installed(srv.install_dir, mod_id)
            status_txt = "✅ instalado" if installed else "❌ não instalado"
            ctk.CTkLabel(row_f, text=status_txt, text_color="gray55",
                         font=ctk.CTkFont(size=11)).grid(row=0, column=2, padx=8)

            has_ini = bool(srv.mod_ini_configs.get(mod_id, {}).get("game_ini", "").strip()
                           or srv.mod_ini_configs.get(mod_id, {}).get("gus_ini", "").strip())
            ini_color = "#5a3a8a" if has_ini else "#2a2a3a"
            ctk.CTkButton(
                row_f, text="⚙️ INI", width=58, height=28,
                fg_color=ini_color, hover_color="#5a3a8a",
                command=lambda mid=mod_id, sid=server_id: self._open_mod_ini_dialog(sid, mid),
            ).grid(row=0, column=3, padx=2)

            ctk.CTkButton(
                row_f, text="🌐", width=32, height=28,
                fg_color="#1a3a6a", hover_color=_BLUE_HOVER,
                command=lambda mid=mod_id: self._open_workshop_page(mid),
            ).grid(row=0, column=4, padx=2)

            ctk.CTkButton(
                row_f, text="⬇️", width=36, height=28,
                fg_color=_BLUE, hover_color=_BLUE_HOVER,
                command=lambda mid=mod_id, sid=server_id: self._download_mod(sid, mid),
            ).grid(row=0, column=5, padx=2)

            ctk.CTkButton(
                row_f, text="🗑", width=32, height=28,
                fg_color=_RED_DARK, hover_color=_RED_HOVER,
                command=lambda mid=mod_id, sid=server_id: self._remove_mod(sid, mid),
            ).grid(row=0, column=6, padx=(2, 8))

    def _open_mod_search_dialog(self, server_id: str) -> None:
        dlg = ctk.CTkToplevel(self)
        dlg.title("Buscar no Steam Workshop")
        dlg.geometry("640x500")
        dlg.resizable(True, True)
        dlg.grab_set()
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(dlg, text="🔍  Buscar Workshop — ARK: Survival Evolved",
                     font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, padx=20, pady=(16, 2), sticky="w")
        ctk.CTkLabel(
            dlg,
            text="Digite um ID numérico para buscar diretamente. Para busca por nome, clique em 🌐 Browser.",
            text_color="gray50", font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")

        search_fr = ctk.CTkFrame(dlg, fg_color="transparent")
        search_fr.grid(row=2, column=0, padx=16, pady=(0, 6), sticky="ew")
        search_fr.grid_columnconfigure(0, weight=1)

        search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(
            search_fr, textvariable=search_var, height=38,
            placeholder_text="ID do mod (ex: 731604991) ou nome para buscar no browser",
        )
        search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(search_fr, text="🔍 Buscar", height=38, width=100,
                      fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                      command=lambda: _do_search()).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(search_fr, text="🌐 Browser", height=38, width=100,
                      fg_color="#1a3a6a", hover_color=_BLUE_HOVER,
                      command=lambda: webbrowser.open(
                          "https://steamcommunity.com/app/346110/workshop/"
                      )).grid(row=0, column=2)

        results_frame = ctk.CTkScrollableFrame(dlg, fg_color=_CARD_BG, corner_radius=8)
        results_frame.grid(row=3, column=0, padx=16, pady=(4, 4), sticky="nsew")
        results_frame.grid_columnconfigure(0, weight=1)

        status_lbl = ctk.CTkLabel(dlg, text="", text_color="gray50",
                                  font=ctk.CTkFont(size=11))
        status_lbl.grid(row=4, column=0, padx=16, pady=(0, 12), sticky="w")

        def _show_result(title: str, mod_id: str, description: str = "") -> None:
            for child in results_frame.winfo_children():
                child.destroy()
            row_f = ctk.CTkFrame(results_frame, fg_color="#1a1a2e", corner_radius=8)
            row_f.pack(fill="x", padx=8, pady=8)
            row_f.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row_f, text=f"🔧  {title}",
                         font=ctk.CTkFont(size=14, weight="bold")).grid(
                row=0, column=0, columnspan=2, padx=14, pady=(12, 2), sticky="w")
            ctk.CTkLabel(row_f, text=f"ID: {mod_id}",
                         text_color="gray55",
                         font=ctk.CTkFont(family="Courier New", size=12)).grid(
                row=1, column=0, padx=14, pady=(0, 4), sticky="w")
            if description:
                clean_desc = description.replace("\r", " ").replace("\n", " ").strip()
                preview = (clean_desc[:160] + "…") if len(clean_desc) > 160 else clean_desc
                ctk.CTkLabel(row_f, text=preview, text_color="gray50",
                             font=ctk.CTkFont(size=10),
                             wraplength=560, justify="left").grid(
                    row=2, column=0, padx=14, pady=(0, 6), sticky="w")
            btn_row_f = ctk.CTkFrame(row_f, fg_color="transparent")
            btn_row_f.grid(row=3, column=0, padx=10, pady=(0, 12), sticky="w")
            ctk.CTkButton(btn_row_f, text="➕  Adicionar ao Servidor", height=34,
                          fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                          command=lambda t=title, m=mod_id: _add_and_close(m, t)).pack(side="left", padx=(0, 10))
            ctk.CTkButton(btn_row_f, text="🌐  Ver na Steam", height=34,
                          fg_color="#1a3a6a", hover_color=_BLUE_HOVER,
                          command=lambda: self._open_workshop_page(mod_id)).pack(side="left")

        def _add_and_close(mod_id: str, mod_name: str = "") -> None:
            w = self._server_widgets.get(server_id, {})
            if "new_mod_id" in w:
                w["new_mod_id"].set(mod_id)
            self._add_mod(server_id, mod_name=mod_name)
            dlg.destroy()

        def _do_search(*_) -> None:
            query = search_var.get().strip()
            if not query:
                return
            for child in results_frame.winfo_children():
                child.destroy()
            if query.isdigit():
                status_lbl.configure(text="⏳  Buscando mod…")

                def _fetch(qid=query) -> None:
                    try:
                        data = urllib.parse.urlencode({
                            "itemcount": "1",
                            "publishedfileids[0]": qid,
                        }).encode()
                        req = urllib.request.Request(
                            "https://api.steampowered.com"
                            "/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
                            data=data,
                            headers={"Content-Type": "application/x-www-form-urlencoded"},
                        )
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            result = json.loads(resp.read().decode())
                        files = result.get("response", {}).get("publishedfiledetails", [])
                        if files and files[0].get("result") == 1:
                            f = files[0]
                            dlg.after(0, lambda: _show_result(
                                f.get("title", "Mod sem nome"),
                                qid,
                                f.get("description", ""),
                            ))
                            dlg.after(0, lambda: status_lbl.configure(text="✅  Mod encontrado."))
                        else:
                            dlg.after(0, lambda: status_lbl.configure(
                                text=f"❌  ID {qid} não encontrado no Workshop."))
                    except Exception as exc:
                        err_msg = str(exc)
                        dlg.after(0, lambda m=err_msg: status_lbl.configure(
                            text=f"⚠️  Erro ao buscar: {m}"))

                threading.Thread(target=_fetch, daemon=True).start()
            else:
                url = (
                    "https://steamcommunity.com/workshop/browse/?appid=346110"
                    f"&searchtext={urllib.parse.quote(query)}&section=readytouseitems"
                )
                webbrowser.open(url)
                status_lbl.configure(
                    text="🌐  Busca por texto aberta no navegador. Cole o ID do mod no campo acima.")

        search_entry.bind("<Return>", _do_search)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Plugins (ArkApi)
    # ══════════════════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Admins
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _fetch_steam_name(steam_id: str, callback) -> None:
        """Busca o nome do perfil Steam em thread separada e chama callback(name_or_none)."""
        def _worker():
            try:
                url = f"https://steamcommunity.com/profiles/{steam_id}?xml=1"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    raw = resp.read().decode("utf-8", errors="replace")
                # Extrai <steamID><![CDATA[Nome]]></steamID>
                m = re.search(r"<steamID(?:[^>]*)>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</steamID>", raw, re.DOTALL)
                name = m.group(1).strip() if m else None
                callback(name)
            except Exception:
                callback(None)
        threading.Thread(target=_worker, daemon=True).start()

    def _build_tab_admins(self, parent, srv: ServerConfig) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        w = self._server_widgets[srv.id]

        add_card = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
        add_card.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        add_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(add_card, text="👤  Steam ID (64-bit):",
                     text_color="gray60").grid(row=0, column=0, padx=16, pady=(14, 4))
        w["new_admin_id"] = tk.StringVar()
        entry = ctk.CTkEntry(add_card, textvariable=w["new_admin_id"], height=34,
                             placeholder_text="Ex: 76561198000000000")
        entry.grid(row=0, column=1, padx=(0, 8), pady=(14, 4), sticky="ew")
        entry.bind("<Return>", lambda _e: self._add_admin_id(srv.id))

        ctk.CTkButton(
            add_card, text="➕ Adicionar", width=110, height=34,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=lambda: self._add_admin_id(srv.id),
        ).grid(row=0, column=2, padx=(0, 16), pady=(14, 4))

        # Label de preview do nome Steam
        w["_admin_name_preview"] = ctk.CTkLabel(
            add_card, text="", text_color="gray50",
            font=ctk.CTkFont(size=11), anchor="w",
        )
        w["_admin_name_preview"].grid(row=1, column=1, padx=(0, 8), pady=(0, 4), sticky="w")

        # Debounce: inicia lookup 1s após parar de digitar
        w["_admin_lookup_after"] = None

        def _on_id_change(*_):
            if w.get("_admin_lookup_after"):
                try:
                    self.after_cancel(w["_admin_lookup_after"])
                except Exception:
                    pass
            steam_id = w["new_admin_id"].get().strip()
            if not steam_id or not steam_id.isdigit() or len(steam_id) < 15:
                w["_admin_name_preview"].configure(text="", text_color="gray50")
                return
            w["_admin_name_preview"].configure(text="🔍  Buscando...", text_color="gray50")
            w["_admin_lookup_after"] = self.after(900, lambda: self._lookup_admin_preview(srv.id, steam_id))

        w["new_admin_id"].trace_add("write", _on_id_change)

        ctk.CTkLabel(
            add_card,
            text="💡  Cole o Steam ID de 64-bit (17 dígitos). Encontre em steamid.io ou em Detalhes do Perfil no Steam.",
            text_color="gray45", font=ctk.CTkFont(size=10), wraplength=700, justify="left",
        ).grid(row=2, column=0, columnspan=3, padx=16, pady=(0, 10), sticky="w")

        admins_card = ctk.CTkScrollableFrame(parent, corner_radius=10, fg_color=_CARD_BG)
        admins_card.grid(row=1, column=0, padx=12, pady=6, sticky="nsew")
        admins_card.grid_columnconfigure(0, weight=1)
        w["_admins_list_frame"] = admins_card

        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.grid(row=2, column=0, padx=12, pady=(4, 12), sticky="ew")
        ctk.CTkButton(
            actions, text="💾  Salvar",
            height=38, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=lambda: self._save_server_config(srv.id),
        ).pack(side="left")
        ctk.CTkLabel(
            actions,
            text="IDs são gravados em AllowedCheaterSteamIDs.txt ao salvar.",
            text_color="gray45", font=ctk.CTkFont(size=11),
        ).pack(side="left", padx=12)

        self._refresh_admins_list(srv.id)

    def _lookup_admin_preview(self, server_id: str, steam_id: str) -> None:
        """Busca o nome Steam e atualiza o label de preview."""
        w = self._server_widgets.get(server_id, {})
        # Só atualiza se o campo ainda contém o mesmo ID que disparou o lookup
        if w.get("new_admin_id") and w["new_admin_id"].get().strip() != steam_id:
            return

        def _done(name: Optional[str]):
            # Executa na thread principal via after
            def _update():
                lbl = w.get("_admin_name_preview")
                if not lbl:
                    return
                # Verifica novamente se o ID não mudou
                if w.get("new_admin_id") and w["new_admin_id"].get().strip() != steam_id:
                    return
                if name:
                    lbl.configure(text=f"✅  {name}", text_color="#4ade80")
                else:
                    lbl.configure(text="⚠️  Perfil privado ou ID inválido", text_color="#f87171")
            try:
                self.after(0, _update)
            except Exception:
                pass

        self._fetch_steam_name(steam_id, _done)

    def _refresh_admins_list(self, server_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        w = self._server_widgets.get(server_id, {})
        frame: Optional[ctk.CTkScrollableFrame] = w.get("_admins_list_frame")
        if not frame or not srv:
            return
        for child in frame.winfo_children():
            child.destroy()
        if not srv.admin_ids:
            ctk.CTkLabel(
                frame,
                text="Nenhum admin configurado.\nAdicione um Steam ID acima.",
                text_color="gray50",
            ).pack(pady=20)
            return
        for steam_id in srv.admin_ids:
            row_fr = ctk.CTkFrame(frame, corner_radius=8, fg_color="#252535")
            row_fr.pack(fill="x", padx=8, pady=3)
            row_fr.grid_columnconfigure(0, weight=1)
            display_name = srv.admin_names.get(steam_id, "")
            label_text = f"🎮  {steam_id}" + (f"  •  {display_name}" if display_name else "")
            ctk.CTkLabel(
                row_fr, text=label_text,
                font=ctk.CTkFont(size=13), anchor="w",
            ).grid(row=0, column=0, padx=12, pady=8, sticky="w")
            ctk.CTkButton(
                row_fr, text="✕", width=32, height=28,
                fg_color=_RED_DARK, hover_color=_RED_HOVER,
                command=lambda sid=steam_id: self._remove_admin_id(server_id, sid),
            ).grid(row=0, column=1, padx=(0, 8), pady=4)

    def _add_admin_id(self, server_id: str) -> None:
        w = self._server_widgets.get(server_id, {})
        var: Optional[tk.StringVar] = w.get("new_admin_id")
        if not var:
            return
        steam_id = var.get().strip()
        if not steam_id:
            return
        if not steam_id.isdigit() or len(steam_id) < 15:
            messagebox.showwarning(
                "Steam ID inválido",
                "Informe um Steam ID válido (somente números, mínimo 15 dígitos).",
                parent=self,
            )
            return
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return
        if steam_id in srv.admin_ids:
            messagebox.showinfo("Já existe", f"O ID {steam_id} já está na lista.", parent=self)
            var.set("")
            return
        srv.admin_ids.append(steam_id)
        # Salva o nome resolvido se o preview mostra um nome válido
        w = self._server_widgets.get(server_id, {})
        lbl = w.get("_admin_name_preview")
        if lbl:
            preview = lbl.cget("text")
            if preview.startswith("✅  "):
                srv.admin_names[steam_id] = preview[3:].strip()
        self.config_manager.update_server(srv)
        var.set("")
        lbl = w.get("_admin_name_preview")
        if lbl:
            lbl.configure(text="", text_color="gray50")
        self._refresh_admins_list(server_id)

    def _remove_admin_id(self, server_id: str, steam_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return
        if steam_id in srv.admin_ids:
            srv.admin_ids.remove(steam_id)
        srv.admin_names.pop(steam_id, None)
        self.config_manager.update_server(srv)
        self._refresh_admins_list(server_id)

    # Aba Jogadores
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_jogadores(self, parent, srv: ServerConfig) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        w = self._server_widgets[srv.id]

        # Header card
        hdr = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
        hdr.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        hdr.grid_columnconfigure(1, weight=1)

        w["_players_count_var"] = tk.StringVar(value="— Jogadores online")
        ctk.CTkLabel(
            hdr, textvariable=w["_players_count_var"],
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, padx=16, pady=12, sticky="w")

        btn_row = ctk.CTkFrame(hdr, fg_color="transparent")
        btn_row.grid(row=0, column=1, padx=8, pady=8, sticky="e")

        w["_players_auto_var"] = tk.BooleanVar(value=False)
        w["_players_auto_job"] = None
        ctk.CTkCheckBox(
            btn_row, text="Auto (30s)", variable=w["_players_auto_var"],
            command=lambda: self._toggle_players_auto(srv.id),
        ).pack(side="left", padx=(0, 12))
        ctk.CTkButton(
            btn_row, text="🔄  Atualizar", width=120, height=32,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            command=lambda: self._refresh_players(srv.id),
        ).pack(side="left", padx=(0, 16))

        ctk.CTkLabel(
            hdr,
            text="⚡  Requer conexão RCON ativa (aba Console RCON). Ações: Kick, Ban, Adicionar como Admin.",
            text_color="gray45", font=ctk.CTkFont(size=10), wraplength=700, justify="left",
        ).grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 10), sticky="w")

        # Lista de jogadores
        players_frame = ctk.CTkScrollableFrame(parent, corner_radius=10, fg_color=_CARD_BG)
        players_frame.grid(row=1, column=0, padx=12, pady=6, sticky="nsew")
        players_frame.grid_columnconfigure(0, weight=1)
        w["_players_list_frame"] = players_frame

        ctk.CTkLabel(
            players_frame,
            text="Clique em 'Atualizar' para listar os jogadores conectados.",
            text_color="gray50",
        ).pack(pady=20)

    def _refresh_players(self, server_id: str) -> None:
        client = self._rcon_clients.get(server_id)
        w = self._server_widgets.get(server_id, {})
        frame = w.get("_players_list_frame")
        count_var: Optional[tk.StringVar] = w.get("_players_count_var")
        if not frame:
            return
        if not client or not client.is_connected:
            for child in frame.winfo_children():
                child.destroy()
            ctk.CTkLabel(
                frame,
                text="⚠️  RCON não conectado.\nVá até a aba 'Console RCON' e clique em 'Conectar' primeiro.",
                text_color="#f87171",
            ).pack(pady=20)
            if count_var:
                count_var.set("— Sem conexão RCON")
            return
        if count_var:
            count_var.set("⏳ Buscando jogadores...")

        def _do():
            ok, result = client.send_command_safe("ListPlayers")
            self.after(0, lambda: self._update_players_list(server_id, ok, result or ""))

        threading.Thread(target=_do, daemon=True).start()

    def _update_players_list(self, server_id: str, ok: bool, response: str) -> None:
        w = self._server_widgets.get(server_id, {})
        frame = w.get("_players_list_frame")
        count_var: Optional[tk.StringVar] = w.get("_players_count_var")
        if not frame:
            return
        for child in frame.winfo_children():
            child.destroy()
        if not ok:
            ctk.CTkLabel(frame, text=f"Erro RCON: {response}", text_color="#f87171").pack(pady=20)
            if count_var:
                count_var.set("Erro ao listar jogadores")
            return
        players = _parse_listplayers(response)
        if not players:
            ctk.CTkLabel(
                frame, text="Nenhum jogador conectado no momento.", text_color="gray50",
            ).pack(pady=20)
            if count_var:
                count_var.set("0 jogadores online")
            return
        n = len(players)
        if count_var:
            count_var.set(f"{n} jogador{'es' if n != 1 else ''} online")
        for p in players:
            self._build_player_row(frame, server_id, p["name"], p["steam_id"])

    def _build_player_row(self, parent, server_id: str, name: str, steam_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        row_fr = ctk.CTkFrame(parent, corner_radius=8, fg_color="#252535")
        row_fr.pack(fill="x", padx=8, pady=3)
        row_fr.grid_columnconfigure(0, weight=1)

        info = ctk.CTkFrame(row_fr, fg_color="transparent")
        info.grid(row=0, column=0, padx=12, pady=6, sticky="w")
        ctk.CTkLabel(
            info, text=f"🧑  {name}",
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            info, text=steam_id,
            font=ctk.CTkFont(size=10), text_color="gray55", anchor="w",
        ).pack(anchor="w")

        btns = ctk.CTkFrame(row_fr, fg_color="transparent")
        btns.grid(row=0, column=1, padx=(0, 8), pady=4, sticky="e")

        is_admin = srv and steam_id in srv.admin_ids
        if not is_admin:
            ctk.CTkButton(
                btns, text="⭐ Admin", width=82, height=28,
                fg_color="#2d4a2d", hover_color="#3d6a3d",
                command=lambda: self._player_add_admin(server_id, steam_id, name),
            ).pack(side="left", padx=3)
        ctk.CTkButton(
            btns, text="👢 Kick", width=74, height=28,
            fg_color="#4a3a1a", hover_color="#6a5020",
            command=lambda: self._player_kick(server_id, steam_id, name),
        ).pack(side="left", padx=3)
        ctk.CTkButton(
            btns, text="🔨 Ban", width=74, height=28,
            fg_color=_RED_DARK, hover_color=_RED_HOVER,
            command=lambda: self._player_ban(server_id, steam_id, name),
        ).pack(side="left", padx=3)

    def _player_kick(self, server_id: str, steam_id: str, name: str) -> None:
        if not messagebox.askyesno(
            "Confirmar Kick",
            f"Kickar o jogador '{name}'?\n\nSteam ID: {steam_id}",
            parent=self,
        ):
            return
        self._rcon_exec(server_id, f"KickPlayer {steam_id}")
        self.after(1500, lambda: self._refresh_players(server_id))

    def _player_ban(self, server_id: str, steam_id: str, name: str) -> None:
        if not messagebox.askyesno(
            "Confirmar Ban",
            f"Banir permanentemente '{name}'?\n\nSteam ID: {steam_id}\n\nPara desfazer use o console: UnbanPlayer {steam_id}",
            parent=self,
        ):
            return
        self._rcon_exec(server_id, f"BanPlayer {steam_id}")
        self.after(1500, lambda: self._refresh_players(server_id))

    def _player_add_admin(self, server_id: str, steam_id: str, name: str) -> None:
        srv = self.config_manager.get_server(server_id)
        if not srv or steam_id in srv.admin_ids:
            return
        srv.admin_ids.append(steam_id)
        if name:
            srv.admin_names[steam_id] = name
        self.config_manager.update_server(srv)
        self._refresh_admins_list(server_id)
        self._refresh_players(server_id)
        messagebox.showinfo(
            "Admin adicionado",
            f"'{name}' foi adicionado à lista de admins.\nLembre-se de salvar as configurações.",
            parent=self,
        )

    def _toggle_players_auto(self, server_id: str) -> None:
        w = self._server_widgets.get(server_id, {})
        auto_var: Optional[tk.BooleanVar] = w.get("_players_auto_var")
        if not auto_var:
            return
        if auto_var.get():
            self._schedule_players_refresh(server_id)
        else:
            job = w.get("_players_auto_job")
            if job:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
                w["_players_auto_job"] = None

    def _schedule_players_refresh(self, server_id: str) -> None:
        w = self._server_widgets.get(server_id, {})
        auto_var: Optional[tk.BooleanVar] = w.get("_players_auto_var")
        if not auto_var or not auto_var.get():
            return
        self._refresh_players(server_id)
        job = self.after(30_000, lambda: self._schedule_players_refresh(server_id))
        w["_players_auto_job"] = job

    # ── helpers de caminho ────────────────────────────────────────────────────

    @staticmethod
    def _arkapi_root(install_dir: str) -> str:
        """Pasta raiz do ArkApi: <install_dir>/ShooterGame/Binaries/Win64/ArkApi"""
        return os.path.join(install_dir, "ShooterGame", "Binaries", "Win64", "ArkApi")

    @staticmethod
    def _plugins_dir(install_dir: str) -> str:
        """Pasta de plugins: <install_dir>/ShooterGame/Binaries/Win64/ArkApi/Plugins"""
        return os.path.join(install_dir, "ShooterGame", "Binaries", "Win64", "ArkApi", "Plugins")

    @staticmethod
    def _is_arkapi_installed(install_dir: str) -> bool:
        """Considera o ArkApi instalado se version.dll estiver em Win64."""
        dll = os.path.join(install_dir, "ShooterGame", "Binaries", "Win64", "version.dll")
        api_dir = os.path.join(install_dir, "ShooterGame", "Binaries", "Win64", "ArkApi")
        return os.path.isfile(dll) or os.path.isdir(api_dir)

    # ── aba principal ─────────────────────────────────────────────────────────

    def _build_tab_plugins(self, parent, srv: ServerConfig) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        w = self._server_widgets[srv.id]

        # ── Card: status do ArkApi ────────────────────────────────────────────
        api_card = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
        api_card.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        api_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(api_card, text="🔌  ArkApi — Framework de Plugins",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, columnspan=4, padx=16, pady=(14, 2), sticky="w")

        api_installed = self._is_arkapi_installed(srv.install_dir) if srv.install_dir else False
        api_status_txt = "✅  ArkApi instalado" if api_installed else "❌  ArkApi não encontrado"
        api_status_color = "#66cc77" if api_installed else "#ff7777"
        w["_api_status_lbl"] = ctk.CTkLabel(
            api_card, text=api_status_txt, text_color=api_status_color,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        w["_api_status_lbl"].grid(row=1, column=0, padx=16, pady=(0, 4), sticky="w")

        ctk.CTkLabel(
            api_card,
            text="O ArkApi é necessário para usar plugins. Baixe e extraia o ZIP na raiz do servidor.",
            text_color="gray45", font=ctk.CTkFont(size=10),
        ).grid(row=2, column=0, columnspan=4, padx=16, pady=(0, 6), sticky="w")

        btn_row = ctk.CTkFrame(api_card, fg_color="transparent")
        btn_row.grid(row=3, column=0, columnspan=4, padx=12, pady=(0, 14), sticky="w")

        ctk.CTkButton(
            btn_row, text="📥  Instalar do ZIP", height=34,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=lambda: self._install_arkapi_from_zip(srv.id),
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            btn_row, text="🌐  Baixar ArkApi", height=34,
            fg_color="#1a3a6a", hover_color=_BLUE_HOVER,
            command=lambda: webbrowser.open("https://ark-server-api.com/resources/ase-server-api.32/"),
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            btn_row, text="📂  Abrir pasta Win64", height=34,
            fg_color="#2a2a4a", hover_color="#3a3a6a",
            command=lambda: self._open_win64_dir(srv.id),
        ).pack(side="left")

        # ── Card: lista de plugins ────────────────────────────────────────────
        hdr_fr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr_fr.grid(row=1, column=0, padx=12, pady=(6, 0), sticky="ew")
        hdr_fr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr_fr, text="🔧  Plugins Instalados",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="w")

        btn_fr2 = ctk.CTkFrame(hdr_fr, fg_color="transparent")
        btn_fr2.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(
            btn_fr2, text="📥  Instalar Plugin (ZIP)", height=32, width=180,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=lambda: self._install_plugin_from_zip(srv.id),
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_fr2, text="🔄  Atualizar Lista", height=32, width=130,
            fg_color="#2a2a4a", hover_color="#3a3a6a",
            command=lambda: self._refresh_plugins_list(srv.id),
        ).pack(side="left")

        plugins_card = ctk.CTkScrollableFrame(parent, corner_radius=10, fg_color=_CARD_BG)
        plugins_card.grid(row=2, column=0, padx=12, pady=(6, 12), sticky="nsew")
        plugins_card.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)
        w["_plugins_list_frame"] = plugins_card

        ctk.CTkLabel(
            parent,
            text="💡  Cada plugin é uma subpasta em  ShooterGame\\Binaries\\Win64\\ArkApi\\Plugins",
            text_color="gray40", font=ctk.CTkFont(size=10),
        ).grid(row=3, column=0, padx=14, pady=(0, 4), sticky="w")

        self._refresh_plugins_list(srv.id)

    # ── atualizar lista ───────────────────────────────────────────────────────

    def _refresh_plugins_list(self, server_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return
        w = self._server_widgets.get(server_id, {})

        # Atualizar status do ArkApi
        status_lbl: Optional[ctk.CTkLabel] = w.get("_api_status_lbl")
        if status_lbl:
            installed = self._is_arkapi_installed(srv.install_dir) if srv.install_dir else False
            status_lbl.configure(
                text="✅  ArkApi instalado" if installed else "❌  ArkApi não encontrado",
                text_color="#66cc77" if installed else "#ff7777",
            )

        frame: Optional[ctk.CTkScrollableFrame] = w.get("_plugins_list_frame")
        if not frame:
            return
        for child in frame.winfo_children():
            child.destroy()

        if not srv.install_dir:
            ctk.CTkLabel(frame,
                         text="Configure o diretório de instalação do servidor primeiro.",
                         text_color="gray50").pack(pady=20)
            return

        plugins_path = self._plugins_dir(srv.install_dir)
        if not os.path.isdir(plugins_path):
            ctk.CTkLabel(frame,
                         text="Pasta de plugins não encontrada. Instale o ArkApi primeiro.",
                         text_color="gray50").pack(pady=20)
            return

        plugin_folders = sorted(
            d for d in os.listdir(plugins_path)
            if os.path.isdir(os.path.join(plugins_path, d))
        )

        if not plugin_folders:
            ctk.CTkLabel(frame, text="Nenhum plugin instalado.",
                         text_color="gray50").pack(pady=20)
            return

        for plugin_name in plugin_folders:
            plugin_path = os.path.join(plugins_path, plugin_name)
            has_dll = any(f.lower().endswith(".dll") for f in os.listdir(plugin_path))
            json_files = sorted(
                f for f in os.listdir(plugin_path)
                if f.lower().endswith(".json")
            )

            card = ctk.CTkFrame(frame, fg_color="#1a1a2e", corner_radius=8)
            card.pack(fill="x", padx=6, pady=4)
            card.grid_columnconfigure(1, weight=1)

            # ── linha do cabeçalho do plugin ─────────────────────────────────
            icon = "🟢" if has_dll else "🟡"
            ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=14), width=28).grid(
                row=0, column=0, padx=(12, 4), pady=(10, 4))
            ctk.CTkLabel(card, text=plugin_name,
                         font=ctk.CTkFont(size=13, weight="bold"),
                         anchor="w").grid(row=0, column=1, padx=4, pady=(10, 4), sticky="ew")

            # badges
            badge_fr = ctk.CTkFrame(card, fg_color="transparent")
            badge_fr.grid(row=0, column=2, padx=4, pady=(10, 4))
            if has_dll:
                ctk.CTkLabel(badge_fr, text="DLL", text_color="#66aaff",
                             font=ctk.CTkFont(size=9), width=28).pack(side="left", padx=2)
            if json_files:
                ctk.CTkLabel(badge_fr, text="JSON", text_color="#ffcc55",
                             font=ctk.CTkFont(size=9), width=32).pack(side="left", padx=2)

            # botões de ação do plugin
            hdr_btn_fr = ctk.CTkFrame(card, fg_color="transparent")
            hdr_btn_fr.grid(row=0, column=3, padx=(4, 12), pady=(10, 4))
            ctk.CTkButton(
                hdr_btn_fr, text="📂", width=32, height=28,
                fg_color="#2a2a4a", hover_color="#3a3a6a",
                command=lambda p=plugin_path: os.startfile(p),
            ).pack(side="left", padx=2)
            ctk.CTkButton(
                hdr_btn_fr, text="🗑", width=32, height=28,
                fg_color=_RED_DARK, hover_color=_RED_HOVER,
                command=lambda n=plugin_name, sid=server_id: self._delete_plugin(sid, n),
            ).pack(side="left", padx=2)

            # ── arquivos JSON de configuração ─────────────────────────────────
            if json_files:
                sep = ctk.CTkFrame(card, height=1, fg_color="#2a2a40")
                sep.grid(row=1, column=0, columnspan=4, padx=12, pady=(0, 4), sticky="ew")

                for jidx, jfile in enumerate(json_files):
                    jpath = os.path.join(plugin_path, jfile)
                    jrow = ctk.CTkFrame(card, fg_color="transparent")
                    jrow.grid(row=2 + jidx, column=0, columnspan=4,
                              padx=(46, 12), pady=2, sticky="ew")
                    jrow.grid_columnconfigure(0, weight=1)

                    ctk.CTkLabel(
                        jrow, text=f"📄  {jfile}",
                        text_color="gray65", font=ctk.CTkFont(family="Courier New", size=11),
                        anchor="w",
                    ).grid(row=0, column=0, sticky="ew")

                    ctk.CTkButton(
                        jrow, text="✏️  Editar", height=26, width=90,
                        fg_color="#333355", hover_color="#444477",
                        font=ctk.CTkFont(size=11),
                        command=lambda p=jpath: self._open_json_editor(p),
                    ).grid(row=0, column=1, padx=(8, 0))

                # padding final
                ctk.CTkFrame(card, height=6, fg_color="transparent").grid(
                    row=2 + len(json_files), column=0, columnspan=4)
            else:
                ctk.CTkLabel(card, text="Sem arquivos de configuração (.json)",
                             text_color="gray40", font=ctk.CTkFont(size=10)).grid(
                    row=1, column=0, columnspan=4, padx=(46, 12), pady=(0, 10), sticky="w")

    # ── instalar ArkApi do ZIP ────────────────────────────────────────────────

    def _install_arkapi_from_zip(self, server_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        if not srv or not srv.install_dir:
            messagebox.showerror("Erro",
                "Configure o diretório de instalação do servidor antes de instalar o ArkApi.",
                parent=self)
            return

        zip_path = filedialog.askopenfilename(
            title="Selecionar ZIP do ArkApi",
            filetypes=[("Arquivo ZIP", "*.zip"), ("Todos", "*.*")],
            parent=self,
        )
        if not zip_path:
            return

        def _extract() -> None:
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    _safe_extract_zip(zf, srv.install_dir)
                self.after(0, lambda: (
                    messagebox.showinfo(
                        "ArkApi Instalado",
                        "ArkApi extraído com sucesso na pasta do servidor.\n\n"
                        "Reinicie o servidor para que o ArkApi seja carregado.",
                        parent=self,
                    ),
                    self._refresh_plugins_list(server_id),
                ))
            except Exception as exc:
                err_msg = str(exc)
                self.after(0, lambda m=err_msg: messagebox.showerror(
                    "Erro ao extrair", m, parent=self))

        threading.Thread(target=_extract, daemon=True).start()

    # ── instalar plugin do ZIP ────────────────────────────────────────────────

    def _install_plugin_from_zip(self, server_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        if not srv or not srv.install_dir:
            messagebox.showerror("Erro",
                "Configure o diretório de instalação do servidor antes de instalar plugins.",
                parent=self)
            return

        plugins_path = self._plugins_dir(srv.install_dir)
        if not os.path.isdir(plugins_path):
            if messagebox.askyesno(
                "Criar pasta de Plugins?",
                "A pasta de Plugins não existe ainda.\n"
                "Deseja criá-la? (O ArkApi precisa estar instalado para que os plugins funcionem.)",
                parent=self,
            ):
                os.makedirs(plugins_path, exist_ok=True)
            else:
                return

        zip_path = filedialog.askopenfilename(
            title="Selecionar ZIP do Plugin",
            filetypes=[("Arquivo ZIP", "*.zip"), ("Todos", "*.*")],
            parent=self,
        )
        if not zip_path:
            return

        def _extract() -> None:
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    # Detectar se o ZIP j� tem uma subpasta raiz
                    names = zf.namelist()
                    top_dirs = {n.split("/")[0] for n in names if "/" in n}
                    # Se todos os membros est�o dentro de uma �nica pasta, extrai direto
                    if len(top_dirs) == 1:
                        _safe_extract_zip(zf, plugins_path)
                        plugin_name = list(top_dirs)[0]
                    else:
                        # Criar pasta com nome do ZIP
                        base = os.path.splitext(os.path.basename(zip_path))[0]
                        dest = os.path.join(plugins_path, base)
                        os.makedirs(dest, exist_ok=True)
                        _safe_extract_zip(zf, dest)
                        plugin_name = base
                self.after(0, lambda: (
                    messagebox.showinfo(
                        "Plugin Instalado",
                        f"Plugin '{plugin_name}' instalado com sucesso!\n\n"
                        "Reinicie o servidor para carregar o plugin.",
                        parent=self,
                    ),
                    self._refresh_plugins_list(server_id),
                ))
            except Exception as exc:
                err_msg = str(exc)
                self.after(0, lambda m=err_msg: messagebox.showerror(
                    "Erro ao extrair", m, parent=self))

        threading.Thread(target=_extract, daemon=True).start()

    # ── deletar plugin ────────────────────────────────────────────────────────

    def _delete_plugin(self, server_id: str, plugin_name: str) -> None:
        if not messagebox.askyesno(
            "Remover Plugin",
            f"Tem certeza que deseja remover o plugin '{plugin_name}'?\n\n"
            "Esta ação é irreversível.",
            parent=self,
        ):
            return
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return
        plugin_path = os.path.join(self._plugins_dir(srv.install_dir), plugin_name)
        try:
            import shutil
            shutil.rmtree(plugin_path)
            self._refresh_plugins_list(server_id)
        except Exception as exc:
            messagebox.showerror("Erro ao remover plugin", str(exc), parent=self)

    # ── abrir pasta Win64 ─────────────────────────────────────────────────────

    def _open_win64_dir(self, server_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        if not srv or not srv.install_dir:
            return
        win64 = os.path.join(srv.install_dir, "ShooterGame", "Binaries", "Win64")
        if os.path.isdir(win64):
            os.startfile(win64)
        else:
            messagebox.showwarning(
                "Pasta não encontrada",
                "A pasta Win64 não foi encontrada. Verifique se o servidor está instalado.",
                parent=self,
            )

    # ── abrir JSON com editor ─────────────────────────────────────────────────

    @staticmethod
    def _open_json_editor(path: str) -> None:
        """
        Abre um arquivo JSON com o melhor editor disponível no sistema.
        Prioridade: Notepad++ → VS Code → Sublime Text → Notepad → os.startfile (padrão).
        """
        import subprocess

        candidates = [
            # Notepad++ (instalações típicas)
            r"C:\Program Files\Notepad++\notepad++.exe",
            r"C:\Program Files (x86)\Notepad++\notepad++.exe",
            # VS Code (instalação de usuário e de sistema)
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         "Programs", "Microsoft VS Code", "Code.exe"),
            r"C:\Program Files\Microsoft VS Code\Code.exe",
            # Sublime Text
            r"C:\Program Files\Sublime Text\sublime_text.exe",
            r"C:\Program Files\Sublime Text 3\sublime_text.exe",
            r"C:\Program Files\Sublime Text 4\sublime_text.exe",
            # Notepad padrão do Windows
            r"C:\Windows\System32\notepad.exe",
        ]

        for editor in candidates:
            if os.path.isfile(editor):
                try:
                    subprocess.Popen([editor, path])
                    return
                except OSError:
                    continue

        # Último recurso: abrir com o aplicativo associado
        os.startfile(path)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Console RCON
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_rcon(self, parent, srv: ServerConfig) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        w = self._server_widgets[srv.id]

        conn_bar = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
        conn_bar.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="ew")
        conn_bar.grid_columnconfigure(4, weight=1)

        ctk.CTkLabel(conn_bar, text="Host:", text_color="gray60").grid(
            row=0, column=0, padx=(14, 4), pady=10)
        w["rcon_host"] = tk.StringVar(value="127.0.0.1")
        ctk.CTkEntry(conn_bar, textvariable=w["rcon_host"], width=120, height=30).grid(
            row=0, column=1, padx=(0, 12), pady=10)

        ctk.CTkLabel(conn_bar, text="Porta:", text_color="gray60").grid(
            row=0, column=2, padx=(0, 4), pady=10)
        w["rcon_port_entry"] = tk.StringVar(value=str(srv.rcon_port))
        ctk.CTkEntry(conn_bar, textvariable=w["rcon_port_entry"], width=70, height=30).grid(
            row=0, column=3, padx=(0, 12), pady=10)

        w["rcon_status_var"] = tk.StringVar(value="⬛ Desconectado")
        ctk.CTkLabel(conn_bar, textvariable=w["rcon_status_var"],
                     text_color="gray50", font=ctk.CTkFont(size=12)).grid(
            row=0, column=4, padx=8, pady=10, sticky="w")

        w["rcon_connect_btn"] = ctk.CTkButton(
            conn_bar, text="🔌 Conectar", width=110, height=30,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=lambda: self._rcon_connect(srv.id),
        )
        w["rcon_connect_btn"].grid(row=0, column=5, padx=(0, 14), pady=10)

        w["rcon_output"] = ctk.CTkTextbox(
            parent, font=ctk.CTkFont(family="Courier New", size=12),
            wrap="word", state="disabled", fg_color="#0a0a14",
        )
        w["rcon_output"].grid(row=1, column=0, padx=12, pady=4, sticky="nsew")
        tw = w["rcon_output"]._textbox
        tw.tag_config("cmd",  foreground="#88d4a0")
        tw.tag_config("resp", foreground="#d0d0e0")
        tw.tag_config("err",  foreground="#ff6666")
        tw.tag_config("sys",  foreground="#888899")

        # Atalhos de comando
        shortcuts_frame = ctk.CTkFrame(parent, corner_radius=8, fg_color=_CARD_BG)
        shortcuts_frame.grid(row=2, column=0, padx=12, pady=(2, 2), sticky="ew")

        common_cmds = [
            ("SaveWorld",        "SaveWorld"),
            ("ListPlayers",      "ListPlayers"),
            ("GetChat",          "GetChat"),
            ("Broadcast",        "Broadcast Olá Sobreviventes!"),
            ("DoExit",           "DoExit"),
            ("DestroyWildDinos", "DestroyWildDinos"),
        ]
        for ci, (lbl, cmd) in enumerate(common_cmds):
            ctk.CTkButton(
                shortcuts_frame, text=lbl, width=130, height=28,
                fg_color="#2a2a44", hover_color="#3a3a5a",
                font=ctk.CTkFont(size=11),
                command=lambda c=cmd, sid=srv.id: self._rcon_exec(sid, c),
            ).grid(row=0, column=ci, padx=4, pady=6)

        input_row = ctk.CTkFrame(parent, fg_color="transparent")
        input_row.grid(row=3, column=0, padx=12, pady=(2, 12), sticky="ew")
        input_row.grid_columnconfigure(0, weight=1)

        w["rcon_input"] = tk.StringVar()
        input_entry = ctk.CTkEntry(
            input_row, textvariable=w["rcon_input"], height=36,
            placeholder_text="Digite um comando RCON e pressione Enter...",
        )
        input_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        input_entry.bind("<Return>", lambda e, sid=srv.id: self._rcon_send(sid))

        ctk.CTkButton(
            input_row, text="Enviar ▶", width=90, height=36,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=lambda: self._rcon_send(srv.id),
        ).grid(row=0, column=1)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Logs
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_logs(self, parent, srv: ServerConfig) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        w = self._server_widgets[srv.id]

        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text=f"Logs do Servidor — {srv.name}",
                     font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="🗑 Limpar", width=90, height=30,
                      fg_color="#3a3a5a", hover_color="#252540",
                      command=lambda: self._clear_server_log(srv.id)).grid(
            row=0, column=1, sticky="e")

        log_box = ctk.CTkTextbox(
            parent, font=ctk.CTkFont(family="Courier New", size=11),
            wrap="word", state="disabled", fg_color="#0a0a14",
        )
        log_box.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        tw = log_box._textbox
        tw.tag_config("info",    foreground="#d0d0e0")
        tw.tag_config("warning", foreground="#ffaa44")
        tw.tag_config("error",   foreground="#ff6666")
        tw.tag_config("debug",   foreground="#555570")
        w["_log_box"] = log_box

    # ══════════════════════════════════════════════════════════════════════════
    # Configurações Globais
    # ══════════════════════════════════════════════════════════════════════════

    def _build_global_config(self, parent) -> None:
        parent.grid_columnconfigure(0, weight=1)
        cfg = self.config_manager.config

        ctk.CTkLabel(parent, text="Configurações Globais",
                     font=ctk.CTkFont(size=24, weight="bold")).grid(
            row=0, column=0, padx=24, pady=(24, 2), sticky="w")
        ctk.CTkLabel(parent, text="Configurações globais do ARKLAND - Server Manager.",
                     text_color="gray60").grid(row=1, column=0, padx=24, pady=(0, 18), sticky="w")

        self._section_lbl(parent, 2, "🎮  SteamCMD")
        sc_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        sc_card.grid(row=3, column=0, padx=20, pady=(0, 14), sticky="ew")
        sc_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(sc_card, text="Caminho do SteamCMD:", width=200, anchor="w",
                     text_color="gray60").grid(row=0, column=0, padx=16, pady=14)
        self._steamcmd_var = tk.StringVar(value=cfg.steamcmd_path)
        fr = ctk.CTkFrame(sc_card, fg_color="transparent")
        fr.grid(row=0, column=1, padx=(0, 16), pady=14, sticky="ew")
        fr.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(fr, textvariable=self._steamcmd_var, height=34,
                     placeholder_text=r"Ex: C:\SteamCMD\steamcmd.exe").grid(
            row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(fr, text="📁", width=34, height=34,
                      command=lambda: self._browse_file(self._steamcmd_var, "steamcmd.exe")).grid(
            row=0, column=1)
        self._steamcmd_dl_btn = ctk.CTkButton(
            sc_card, text="⬇  Baixar SteamCMD", height=34,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=self._download_steamcmd,
        )
        self._steamcmd_dl_btn.grid(row=0, column=2, padx=(0, 16), pady=14)
        self._steamcmd_status_lbl = ctk.CTkLabel(
            sc_card,
            text="O SteamCMD é necessário para instalar/atualizar servidores e baixar mods via Steam Workshop.",
            text_color="gray50", font=ctk.CTkFont(size=11),
        )
        self._steamcmd_status_lbl.grid(row=1, column=0, columnspan=3, padx=16, pady=(0, 10), sticky="w")

        self._section_lbl(parent, 4, "📂  Diretório Padrão de Instalação")
        dir_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        dir_card.grid(row=5, column=0, padx=20, pady=(0, 14), sticky="ew")
        dir_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(dir_card, text="Diretório Padrão:", width=200, anchor="w",
                     text_color="gray60").grid(row=0, column=0, padx=16, pady=(14, 2))
        self._default_dir_var = tk.StringVar(value=cfg.default_install_dir)
        fr2 = ctk.CTkFrame(dir_card, fg_color="transparent")
        fr2.grid(row=0, column=1, padx=(0, 16), pady=(14, 2), sticky="ew")
        fr2.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(fr2, textvariable=self._default_dir_var, height=34).grid(
            row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(fr2, text="📁", width=34, height=34,
                      command=lambda: self._browse_dir(self._default_dir_var)).grid(row=0, column=1)
        ctk.CTkLabel(dir_card,
                     text="Pasta sugerida ao criar um novo servidor. Pode ser sobrescrita individualmente.",
                     text_color="gray45", font=ctk.CTkFont(size=10)).grid(
            row=1, column=0, columnspan=2, padx=16, pady=(0, 12), sticky="w")

        self._section_lbl(parent, 6, "🔧  Opções")
        opt_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        opt_card.grid(row=7, column=0, padx=20, pady=(0, 14), sticky="ew")

        self._cfg_startup_var   = tk.BooleanVar(value=cfg.startup_with_windows)
        self._cfg_minimize_tray_var = tk.BooleanVar(value=cfg.minimize_to_tray)
        self._cfg_log_debug_var = tk.BooleanVar(value=cfg.log_debug)

        ctk.CTkCheckBox(opt_card, text="Iniciar o ARKLAND - Server Manager com o Windows",
                        variable=self._cfg_startup_var,
                        checkmark_color="white", fg_color=_GREEN_DARK,
                        hover_color=_GREEN_HOVER).grid(
            row=0, column=0, padx=16, pady=(16, 2), sticky="w")
        ctk.CTkLabel(opt_card,
                     text="Inicia o app automaticamente quando o Windows ligar.",
                     text_color="gray45", font=ctk.CTkFont(size=10)).grid(
            row=1, column=0, padx=(42, 16), pady=(0, 8), sticky="w")

        ctk.CTkCheckBox(opt_card, text="Minimizar para a bandeja do sistema ao fechar",
                        variable=self._cfg_minimize_tray_var,
                        checkmark_color="white", fg_color=_GREEN_DARK,
                        hover_color=_GREEN_HOVER).grid(
            row=2, column=0, padx=16, pady=(0, 2), sticky="w")
        ctk.CTkLabel(opt_card,
                     text="Mantém o app ativo na bandeja (systray) em vez de fechar. Clique no ícone para restaurar.",
                     text_color="gray45", font=ctk.CTkFont(size=10)).grid(
            row=3, column=0, padx=(42, 16), pady=(0, 8), sticky="w")

        ctk.CTkCheckBox(opt_card, text="Modo de log verbose (debug)",
                        variable=self._cfg_log_debug_var,
                        checkmark_color="white", fg_color=_GREEN_DARK,
                        hover_color=_GREEN_HOVER).grid(
            row=4, column=0, padx=16, pady=(0, 2), sticky="w")
        ctk.CTkLabel(opt_card,
                     text="Registra mensagens detalhadas no log. Útil para diagnosticar problemas.",
                     text_color="gray45", font=ctk.CTkFont(size=10)).grid(
            row=5, column=0, padx=(42, 16), pady=(0, 16), sticky="w")

        ctk.CTkButton(
            parent, text="💾  Salvar Configurações Globais",
            height=44, font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=self._save_global_config,
        ).grid(row=8, column=0, padx=20, pady=(0, 24), sticky="ew")

    # ══════════════════════════════════════════════════════════════════════════
    # Sobre / Atualizações
    # ══════════════════════════════════════════════════════════════════════════

    def _build_about(self, parent) -> None:
        parent.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(parent, text="Sobre & Atualizações",
                     font=ctk.CTkFont(size=24, weight="bold")).grid(
            row=0, column=0, padx=24, pady=(24, 2), sticky="w")
        ctk.CTkLabel(parent, text="Informações do aplicativo e gerenciamento de atualizações.",
                     text_color="gray60").grid(row=1, column=0, padx=24, pady=(0, 18), sticky="w")

        self._section_lbl(parent, 2, "📦  Aplicativo")
        info_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        info_card.grid(row=3, column=0, padx=20, pady=(0, 14), sticky="ew")
        info_card.grid_columnconfigure(1, weight=1)
        for rn, (lbl, val, bold) in enumerate([
            ("Nome:",         APP_NAME,          False),
            ("Versão atual:", f"v{APP_VERSION}", True),
            ("Build:",        BUILD_DATE,        False),
        ]):
            ctk.CTkLabel(info_card, text=lbl, width=160, anchor="w",
                         text_color="gray60").grid(row=rn, column=0, padx=18, pady=8)
            ctk.CTkLabel(info_card, text=val, anchor="w",
                         font=ctk.CTkFont(weight="bold" if bold else "normal"),
                         text_color=_GREEN if bold else "#d8d8e8").grid(
                row=rn, column=1, padx=(0, 18), pady=8, sticky="w")

        self._section_lbl(parent, 4, "🔄  Atualização")
        upd_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        upd_card.grid(row=5, column=0, padx=20, pady=(0, 14), sticky="ew")
        upd_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(upd_card, text="Status:", width=160, anchor="w",
                     text_color="gray60").grid(row=0, column=0, padx=18, pady=(18, 6))
        self._update_status_var = tk.StringVar(value="Não verificado")
        self._update_status_lbl = ctk.CTkLabel(upd_card, textvariable=self._update_status_var,
                                               font=ctk.CTkFont(weight="bold"), text_color="gray50")
        self._update_status_lbl.grid(row=0, column=1, padx=(0, 18), pady=(18, 6), sticky="w")

        ctk.CTkLabel(upd_card, text="Última verificação:", width=160, anchor="w",
                     text_color="gray60").grid(row=1, column=0, padx=18, pady=(0, 10))
        self._last_check_var = tk.StringVar(value="Nunca")
        ctk.CTkLabel(upd_card, textvariable=self._last_check_var,
                     text_color="#d8d8e8").grid(row=1, column=1, padx=(0, 18), sticky="w")

        btn_row = ctk.CTkFrame(upd_card, fg_color="transparent")
        btn_row.grid(row=2, column=0, columnspan=2, padx=18, pady=(4, 14), sticky="w")
        self._check_update_btn = ctk.CTkButton(
            btn_row, text="🔍  Verificar Atualizações", width=210, height=40,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            command=self._check_updates_manual,
        )
        self._check_update_btn.pack(side="left", padx=(0, 10))
        self._install_update_btn = ctk.CTkButton(
            btn_row, text="⬇️  Baixar e Instalar", width=190, height=40,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER, state="disabled",
            command=self._start_download_update,
        )
        self._install_update_btn.pack(side="left")

        self._update_progress       = ctk.CTkProgressBar(upd_card, width=420, height=14)
        self._update_progress.set(0)
        self._update_progress_label = ctk.CTkLabel(upd_card, text="", text_color="gray60",
                                                   font=ctk.CTkFont(size=11))

        self._section_lbl(parent, 6, "📝  Histórico de Versões")
        cl_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        cl_card.grid(row=7, column=0, padx=20, pady=(0, 24), sticky="ew")
        cl_card.grid_columnconfigure(0, weight=1)
        cl_text = ctk.CTkTextbox(cl_card, font=ctk.CTkFont(family="Courier New", size=12),
                                 wrap="word", state="normal", height=200, fg_color="#161622")
        cl_text.grid(row=0, column=0, padx=12, pady=12, sticky="ew")
        tw = cl_text._textbox
        tw.tag_config("ver",  foreground="#4CAF50", font=("Courier New", 13, "bold"))
        tw.tag_config("date", foreground="#888899")
        tw.tag_config("item", foreground="#c0c0d8")
        for entry in CHANGELOG:
            tw.insert("end", f"v{entry['version']}", "ver")
            if entry.get("date"):
                tw.insert("end", f"  ·  {entry['date']}\n", "date")
            else:
                tw.insert("end", "\n")
            for change in entry.get("changes", []):
                tw.insert("end", f"  • {change}\n", "item")
            tw.insert("end", "\n")
        cl_text.configure(state="disabled")

    # ══════════════════════════════════════════════════════════════════════════
    # Ações de Servidor
    # ══════════════════════════════════════════════════════════════════════════

    def _start_server(self, server_id: str) -> None:
        self._save_server_config(server_id, silent=True)
        srv = self.config_manager.get_server(server_id)
        if srv and srv.auto_update_on_start and self.mod_manager.is_steamcmd_available() and srv.install_dir:
            self._global_log(f"[{srv.name}] Atualizando servidor via SteamCMD antes de iniciar...", "info")
            def _on_update_done(ok: bool) -> None:
                if ok:
                    self._global_log(f"[{srv.name}] Atualização concluída. Iniciando servidor...", "info")
                else:
                    self._global_log(f"[{srv.name}] Atualização falhou, iniciando servidor mesmo assim...", "warning")
                self.after(0, lambda: self.server_manager.start_server(server_id))
            self.mod_manager.install_server(srv.install_dir, validate=False, on_done=_on_update_done)
        else:
            self.server_manager.start_server(server_id)

    def _stop_server(self, server_id: str) -> None:
        self.server_manager.stop_server(server_id)

    def _restart_server(self, server_id: str) -> None:
        self.server_manager.restart_server(server_id)

    def _confirm_remove_server(self, server_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        name = srv.name if srv else server_id
        if messagebox.askyesno(
            "Remover Servidor",
            f"Deseja remover o servidor '{name}'?\nEsta ação não pode ser desfeita.",
            parent=self,
        ):
            self.server_manager.remove_server(server_id)
            self.config_manager.remove_server(server_id)
            frame_key = f"server_{server_id}"
            if frame_key in self._frames:
                self._frames[frame_key].destroy()
                del self._frames[frame_key]
            if server_id in self._server_frames:
                del self._server_frames[server_id]
            if server_id in self._server_widgets:
                del self._server_widgets[server_id]
            if server_id in self._rcon_clients:
                try:
                    self._rcon_clients[server_id].disconnect()
                except Exception:
                    pass
                del self._rcon_clients[server_id]
            self._rebuild_server_sidebar()
            self._refresh_dashboard()
            self._show_frame("dashboard")

    def _run_server_install(self, server_id: str, validate: bool = False) -> None:
        """Instala ou valida o servidor ARK via SteamCMD."""
        if not self.mod_manager.is_steamcmd_available():
            messagebox.showwarning(
                "SteamCMD não encontrado",
                "Configure o caminho do SteamCMD nas Configurações Globais antes de instalar.",
                parent=self)
            return

        w = self._server_widgets.get(server_id, {})
        install_dir = w.get("install_dir", tk.StringVar()).get().strip()
        if not install_dir:
            messagebox.showwarning(
                "Diretório não definido",
                "Preencha o 'Diretório de Instalação' na aba Geral e salve antes de instalar.",
                parent=self)
            return

        inst_log: Any = w.get("_inst_log")
        inst_status: Any = w.get("_inst_status")
        inst_btn: Any = w.get("_inst_btn")
        val_btn: Any = w.get("_val_btn")

        def _log(msg: str, level: str = "info") -> None:
            import datetime
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            line = f"[{ts}] {msg}\n"
            def _do():
                if inst_log:
                    inst_log.configure(state="normal")
                    inst_log.insert("end", line)
                    inst_log.see("end")
                    inst_log.configure(state="disabled")
            self.after(0, _do)

        def _set_status(txt: str, color: str = "gray60") -> None:
            def _do():
                if inst_status:
                    inst_status.configure(text=txt, text_color=color)
            self.after(0, _do)

        def _set_btns(state: str) -> None:
            def _do():
                if inst_btn:
                    inst_btn.configure(state=state)
                if val_btn:
                    val_btn.configure(state=state)
            self.after(0, _do)

        def _on_done(ok: bool) -> None:
            if ok:
                _set_status("✅  Instalação concluída com sucesso!", _GREEN)
            else:
                _set_status("❌  Falha na instalação. Veja o log acima.", "#f87171")
            _set_btns("normal")

        _set_btns("disabled")
        action = "Validando" if validate else "Instalando/Atualizando"
        _set_status(f"⏳  {action}... Aguarde.", "#fbbf24")

        # Redireciona o log do mod_manager para o log local
        orig_log = self.mod_manager._on_log
        self.mod_manager._on_log = _log
        def _wrapped_done(ok: bool) -> None:
            self.mod_manager._on_log = orig_log
            _on_done(ok)

        self.mod_manager.install_server(install_dir, validate=validate, on_done=_wrapped_done)

    def _save_server_config(self, server_id: str, silent: bool = False) -> None:
        """Lê todos os widgets do servidor, salva no config e escreve os .ini."""
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return

        # Bloqueia salvamento se o servidor não estiver parado
        inst = self.server_manager.get_instance(server_id)
        if inst and inst.status != SERVER_STATUS_STOPPED:
            messagebox.showwarning(
                "Servidor em execução",
                "Pare o servidor antes de salvar as configurações.",
                parent=self,
            )
            return

        w = self._server_widgets.get(server_id, {})

        # ── Geral ──────────────────────────────────────────────────────────
        if "name" in w:
            srv.name           = w["name"].get().strip() or srv.name
            srv.install_dir    = w["install_dir"].get().strip()
            srv.server_name    = w["server_name"].get().strip()
            map_raw = w["map"].get()
            if "(" in map_raw and map_raw.endswith(")"):
                srv.map = map_raw.split("(")[-1].rstrip(")")
            else:
                srv.map = map_raw
            srv.server_password  = w["server_password"].get()
            srv.admin_password   = w["admin_password"].get()
            srv.rcon_password    = w["rcon_password"].get()
            try:
                srv.max_players  = int(w["max_players"].get())
                srv.server_port  = int(w["server_port"].get())
                srv.query_port   = int(w["query_port"].get())
                srv.rcon_port    = int(w["rcon_port"].get())
            except (ValueError, KeyError):
                pass
            srv.extra_args            = w.get("extra_args",    tk.StringVar()).get().strip()
            _evt_raw = w.get("active_event", tk.StringVar()).get().strip()
            srv.active_event          = _ARK_EVENT_LABEL_TO_ID.get(_evt_raw, _evt_raw)
            try:
                srv.auto_save_period  = float(w.get("auto_save", tk.StringVar(value="15")).get())
            except ValueError:
                pass
            srv.rcon_enabled          = w.get("rcon_enabled",       tk.BooleanVar(value=True)).get()
            srv.use_battleye          = w.get("use_battleye",        tk.BooleanVar()).get()
            srv.use_allcores          = w.get("use_allcores",        tk.BooleanVar()).get()
            srv.force_respawn_dinos   = w.get("force_respawn",       tk.BooleanVar()).get()
            srv.whitelist_only        = w.get("whitelist_only",      tk.BooleanVar()).get()
            srv.auto_restart_on_crash = w.get("auto_restart_crash",  tk.BooleanVar()).get()
            srv.auto_update_on_start  = w.get("auto_update_start",   tk.BooleanVar()).get()

        # ── GameSettings ──────────────────────────────────────────────────
        gs = srv.game_settings
        float_gs = [
            "difficulty_offset", "override_official_difficulty",
            "xp_multiplier", "kill_xp_multiplier", "harvest_xp_multiplier",
            "craft_xp_multiplier", "generic_xp_multiplier", "special_xp_multiplier",
            "taming_speed_multiplier", "harvest_amount_multiplier",
            "resource_respawn_period_multiplier", "harvest_health_multiplier",
            "dino_count_multiplier", "player_damage_multiplier",
            "player_resistance_multiplier", "player_character_water_drain_multiplier",
            "player_character_food_drain_multiplier",
            "player_character_health_recovery_multiplier",
            "player_character_stamina_drain_multiplier",
            "dino_damage_multiplier", "dino_resistance_multiplier",
            "dino_character_health_recovery_multiplier",
            "dino_character_food_drain_multiplier",
            "baby_mature_speed_multiplier", "baby_hatch_speed_multiplier",
            "baby_food_consumption_speed_multiplier", "baby_cuddle_interval_multiplier",
            "mating_interval_multiplier", "egg_hatch_speed_multiplier",
            "lay_egg_interval_multiplier", "baby_imprinting_stat_scale_multiplier",
            "baby_cuddle_grace_period_multiplier", "structure_damage_multiplier",
            "structure_resistance_multiplier", "pve_structure_decay_period_multiplier",
            "crop_growth_speed_multiplier", "crop_decay_speed_multiplier",
            "item_stack_size_multiplier", "spoiling_time_multiplier",
            "item_decomposition_time_multiplier", "fishing_loot_quality_multiplier",
            "per_platform_max_structures_multiplier",
            "platform_saddle_build_area_bounds_multiplier",
            "kick_idle_players_period", "tribe_name_change_cooldown",
        ]
        int_gs = [
            "max_tamed_dinos", "structure_damage_repair_cooldown",
            "override_max_experience_points_player", "override_max_experience_points_dino",
            "max_tribe_size",
        ]
        bool_gs = [
            "allow_flyer_carry_pve", "disable_structure_decay_pve", "disable_dino_decay_pve",
            "prevent_offline_pvp", "show_map_player_location", "allow_third_person_player",
            "always_notify_player_joined", "always_notify_player_left",
            "server_hardcore", "server_pvp", "no_tribute_downloads",
        ]
        for f in float_gs:
            key = f"gs_{f}"
            if key in w:
                try:
                    setattr(gs, f, float(w[key].get()))
                except (ValueError, TypeError, AttributeError):
                    pass
        for f in int_gs:
            key = f"gs_{f}"
            if key in w:
                try:
                    setattr(gs, f, int(float(w[key].get())))
                except (ValueError, TypeError, AttributeError):
                    pass
        for f in bool_gs:
            key = f"gs_{f}"
            if key in w:
                try:
                    setattr(gs, f, bool(w[key].get()))
                except (Exception):
                    pass

        # ── AdvancedSettings ──────────────────────────────────────────────
        adv = srv.advanced_settings
        adv_bool = [
            "prevent_download_survivors", "prevent_download_items", "prevent_download_dinos",
            "prevent_upload_survivors", "prevent_upload_items", "prevent_upload_dinos",
            "no_transfer_from_filtering", "enable_cryopod_nerf",
            "allow_crateSpawns_on_top_of_structures", "use_optimized_harvesting_health",
            "b_passive_defenses_damage_riderless_dinos", "global_voice_chat",
            "proximity_chat", "allow_raid_dino_feeding", "b_auto_pve_timer",
            "b_auto_pve_use_system_time", "force_all_structure_locking",
            "force_flyer_explosives",
        ]
        adv_float = [
            "cryopod_nerf_duration", "cryopod_nerf_damage_mult",
            "raid_dino_character_food_drain_multiplier",
            "oxygen_swim_speed_stat_multiplier", "dino_harvesting_damage_multiplier",
            "player_harvesting_damage_multiplier", "custom_recipe_skill_multiplier",
            "custom_recipe_effectiveness_multiplier",
            "auto_pve_start_time_seconds", "auto_pve_stop_time_seconds",
        ]
        for f in adv_bool:
            if f"adv_{f}" in w:
                try:
                    setattr(adv, f, bool(w[f"adv_{f}"].get()))
                except Exception:
                    pass
        for f in adv_float:
            if f"adv_{f}" in w:
                try:
                    setattr(adv, f, float(w[f"adv_{f}"].get()))
                except (ValueError, TypeError):
                    pass

        # ── Cluster ───────────────────────────────────────────────────────
        cl = srv.cluster
        if "cl_enabled" in w:
            cl.enabled              = bool(w["cl_enabled"].get())
            cl.cluster_id           = w.get("cl_cluster_id",  tk.StringVar()).get().strip()
            cl.cluster_dir_override = w.get("cl_cluster_dir", tk.StringVar()).get().strip()

        # Atualiza título do painel
        if "_name_title_var" in w:
            w["_name_title_var"].set(srv.name)

        # Persiste
        self.config_manager.update_server(srv)
        self.server_manager.update_server_config(srv)

        # Escreve .ini se o diretório existir
        if srv.install_dir and os.path.isdir(srv.install_dir):
            try:
                ini_mgr = ArkIniManager(srv.install_dir)
                ini_mgr.save_all(srv)
            except Exception as exc:
                self._global_log(f"Erro ao salvar .ini para {srv.name}: {exc}", "error")

            # Grava AllowedCheaterSteamIDs.txt
            try:
                import pathlib
                allowed_path = (
                    pathlib.Path(srv.install_dir)
                    / "ShooterGame" / "Saved" / "Config" / "WindowsServer"
                    / "AllowedCheaterSteamIDs.txt"
                )
                allowed_path.parent.mkdir(parents=True, exist_ok=True)
                allowed_path.write_text("\n".join(srv.admin_ids), encoding="utf-8")
            except Exception as exc:
                self._global_log(
                    f"[{srv.name}] Aviso: não foi possível gravar AllowedCheaterSteamIDs.txt: {exc}",
                    "warning",
                )

        self._rebuild_server_sidebar()
        self._refresh_dashboard()

        if not silent:
            messagebox.showinfo("Salvo", f"Configurações de '{srv.name}' salvas!", parent=self)

    # ── Import / Sync INI ─────────────────────────────────────────────────────

    def _import_ini_from_disk(self, server_id: str) -> None:
        """Abre dialog para escolher a pasta de origem e importa GameUserSettings.ini e Game.ini."""
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return

        # ── Dialog de seleção de origem ───────────────────────────────────────
        dlg = ctk.CTkToplevel(self)
        dlg.title("Importar INI do Disco")
        dlg.geometry("620x220")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dlg, text="📂  Importar arquivos INI",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(16, 4), sticky="w")

        ctk.CTkLabel(
            dlg,
            text="Selecione a pasta que contém os arquivos INI.\n"
                 "Pode ser a pasta do servidor ou um diretório de backup qualquer.\n"
                 "Serão procurados: GameUserSettings.ini e Game.ini",
            text_color="gray55", font=ctk.CTkFont(size=11), justify="left",
        ).grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")

        path_fr = ctk.CTkFrame(dlg, fg_color="transparent")
        path_fr.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")
        path_fr.grid_columnconfigure(0, weight=1)

        # Valor padrão: pasta WindowsServer do servidor, se existir
        from .ark_ini import get_ini_path as _get_ini_path2
        default_dir = str(_get_ini_path2(srv.install_dir, "Game.ini").parent) if srv.install_dir else ""
        path_var = tk.StringVar(value=default_dir)

        path_entry = ctk.CTkEntry(path_fr, textvariable=path_var, height=34,
                                  placeholder_text="Caminho da pasta com os arquivos INI")
        path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        def _browse():
            folder = filedialog.askdirectory(
                title="Selecionar pasta com arquivos INI",
                initialdir=path_var.get() or os.path.expanduser("~"),
                parent=dlg,
            )
            if folder:
                path_var.set(folder)

        ctk.CTkButton(path_fr, text="📁", width=40, height=34,
                      fg_color="gray30", hover_color="gray40",
                      command=_browse).grid(row=0, column=1)

        btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_fr.grid(row=3, column=0, padx=20, pady=(0, 16), sticky="e")

        def _do_import():
            folder = path_var.get().strip()
            if not folder or not os.path.isdir(folder):
                messagebox.showwarning(
                    "Pasta inválida",
                    "Selecione uma pasta válida para importar os INIs.",
                    parent=dlg,
                )
                return

            from pathlib import Path
            gus_path  = Path(folder) / "GameUserSettings.ini"
            game_path = Path(folder) / "Game.ini"

            if not gus_path.exists() and not game_path.exists():
                messagebox.showwarning(
                    "Arquivos não encontrados",
                    f"Nenhum arquivo INI (GameUserSettings.ini / Game.ini) encontrado em:\n{folder}",
                    parent=dlg,
                )
                return

            # Usa ArkIniManager apontando para a pasta escolhida,
            # mas lê diretamente os arquivos lá presentes
            def _load_from_folder(target_srv, src_folder: str) -> None:
                from .ark_ini import (
                    _GUS_SERVER_SETTINGS, _GUS_SESSION_SETTINGS,
                    _coerce, read_ini_with_fallback,
                )
                p_gus = Path(src_folder) / "GameUserSettings.ini"
                if p_gus.exists():
                    parser = read_ini_with_fallback(p_gus, strict=False)
                    gs = target_srv.game_settings
                    for field_name, section, key, typ in _GUS_SERVER_SETTINGS:
                        try:
                            if parser.has_option(section, key):
                                setattr(gs, field_name, _coerce(parser.get(section, key), typ))
                        except Exception:
                            pass
                    for field_name, section, key, typ in _GUS_SESSION_SETTINGS:
                        try:
                            if parser.has_option(section, key):
                                setattr(target_srv, field_name, _coerce(parser.get(section, key), typ))
                        except Exception:
                            pass
                    if parser.has_option("ServerSettings", "ActiveMods"):
                        raw_mods = parser.get("ServerSettings", "ActiveMods").strip()
                        target_srv.mods = [m.strip() for m in raw_mods.split(",") if m.strip()]

                p_game = Path(src_folder) / "Game.ini"
                if p_game.exists():
                    parser2 = read_ini_with_fallback(p_game, strict=False)
                    adv = target_srv.advanced_settings
                    section = "/Script/ShooterGame.ShooterGameMode"
                    from .ark_ini import (
                        _str_to_bool as _sb,
                    )
                    bool_fields = [
                        ("prevent_download_survivors", "bPreventDownloadSurvivors"),
                        ("prevent_download_items", "bPreventDownloadItems"),
                        ("prevent_download_dinos", "bPreventDownloadDinos"),
                        ("prevent_upload_survivors", "bPreventUploadSurvivors"),
                        ("prevent_upload_items", "bPreventUploadItems"),
                        ("prevent_upload_dinos", "bPreventUploadDinos"),
                        ("no_transfer_from_filtering", "NoTransferFromFiltering"),
                        ("enable_cryopod_nerf", "EnableCryopodNerf"),
                        ("allow_crateSpawns_on_top_of_structures", "AllowCrateSpawnsOnTopOfStructures"),
                        ("use_optimized_harvesting_health", "UseOptimizedHarvestingHealth"),
                        ("b_passive_defenses_damage_riderless_dinos", "bPassiveDefensesDamageRiderlessDinos"),
                        ("global_voice_chat", "GlobalVoiceChat"),
                        ("proximity_chat", "ProximityChat"),
                        ("allow_raid_dino_feeding", "AllowRaidDinoFeeding"),
                        ("b_auto_pve_timer", "bAutoPvETimer"),
                        ("b_auto_pve_use_system_time", "bAutoPvEUseSystemTime"),
                        ("force_all_structure_locking", "ForceAllStructureLocking"),
                        ("force_flyer_explosives", "ForceFlyerExplosives"),
                    ]
                    float_fields = [
                        ("cryopod_nerf_duration", "CryopodNerfDuration"),
                        ("cryopod_nerf_damage_mult", "CryopodNerfDamageMult"),
                        ("raid_dino_character_food_drain_multiplier", "RaidDinoCharacterFoodDrainMultiplier"),
                        ("oxygen_swim_speed_stat_multiplier", "OxygenSwimSpeedStatMultiplier"),
                        ("dino_harvesting_damage_multiplier", "DinoHarvestingDamageMultiplier"),
                        ("player_harvesting_damage_multiplier", "PlayerHarvestingDamageMultiplier"),
                        ("custom_recipe_effectiveness_multiplier", "CustomRecipeEffectivenessMultiplier"),
                        ("custom_recipe_skill_multiplier", "CustomRecipeSkillMultiplier"),
                        ("auto_pve_start_time_seconds", "AutoPvEStartTimeSeconds"),
                        ("auto_pve_stop_time_seconds", "AutoPvEStopTimeSeconds"),
                    ]
                    for field_name, key in bool_fields:
                        try:
                            if parser2.has_option(section, key):
                                setattr(adv, field_name, _sb(parser2.get(section, key)))
                        except Exception:
                            pass
                    for field_name, key in float_fields:
                        try:
                            if parser2.has_option(section, key):
                                setattr(adv, field_name, float(parser2.get(section, key)))
                        except Exception:
                            pass

            try:
                _load_from_folder(srv, folder)
            except Exception as exc:
                messagebox.showerror("Erro ao importar", str(exc), parent=dlg)
                return

            self.config_manager.update_server(srv)
            dlg.destroy()
            self._rebuild_server_panel(server_id)
            found = []
            if gus_path.exists():
                found.append("GameUserSettings.ini")
            if game_path.exists():
                found.append("Game.ini")
            messagebox.showinfo(
                "INI importado",
                "Configurações importadas com sucesso!\n\nArquivos lidos:\n  " + "\n  ".join(found) + f"\n\nDe: {folder}",
                parent=self,
            )

        ctk.CTkButton(
            btn_fr, text="Cancelar", width=100, height=36,
            fg_color="gray30", hover_color="gray40",
            command=dlg.destroy,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_fr, text="⬆️  Importar", width=130, height=36,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            command=_do_import,
        ).pack(side="left")

    def _rebuild_server_panel(self, server_id: str) -> None:
        """Reconstrói o painel completo de um servidor para refletir valores atualizados."""
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return
        frame_key = f"server_{server_id}"
        old_frame = self._frames.get(frame_key)
        if old_frame is None:
            return

        # Reinicia o dict de widgets para este servidor
        self._server_widgets[server_id] = {}

        new_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=_BG)
        new_frame.grid(row=0, column=1, sticky="nsew")
        self._build_server_panel(new_frame, srv)
        self._frames[frame_key] = new_frame

        old_frame.destroy()
        self._show_frame(frame_key)

    def _open_sync_ini_dialog(self, source_server_id: str) -> None:
        """Abre diálogo para escolher quais servidores receberão os INIs do servidor atual."""
        src = self.config_manager.get_server(source_server_id)
        if not src:
            return
        if not src.install_dir or not os.path.isdir(src.install_dir):
            messagebox.showwarning(
                "Sem diretório",
                "Configure e salve o Diretório de Instalação antes de sincronizar.",
                parent=self,
            )
            return

        from .ark_ini import get_ini_path as _get_ini_path
        gus_path  = _get_ini_path(src.install_dir, "GameUserSettings.ini")
        game_path = _get_ini_path(src.install_dir, "Game.ini")
        if not gus_path.exists() and not game_path.exists():
            messagebox.showwarning(
                "Arquivos não encontrados",
                f"Nenhum INI encontrado em:\n{gus_path.parent}\n\n"
                "Salve as configurações primeiro para gerar os arquivos.",
                parent=self,
            )
            return

        other_servers = [s for s in self.config_manager.servers if s.id != source_server_id]
        if not other_servers:
            messagebox.showinfo(
                "Sem outros servidores",
                "Nenhum outro servidor cadastrado para sincronizar.",
                parent=self,
            )
            return

        # ── Diálogo de seleção ────────────────────────────────────────────────
        dlg = ctk.CTkToplevel(self)
        dlg.title("Sincronizar INI entre servidores")
        dlg.geometry("480x420")
        dlg.resizable(False, False)
        dlg.grab_set()

        ctk.CTkLabel(
            dlg,
            text=f"Copiar INIs de  '{src.name}'  para:",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(padx=24, pady=(20, 4), anchor="w")

        ctk.CTkLabel(
            dlg,
            text="Serão copiados: GameUserSettings.ini e Game.ini\n"
                 "Os arquivos de destino serão substituídos.",
            text_color="gray55", font=ctk.CTkFont(size=10), justify="left",
        ).pack(padx=24, pady=(0, 12), anchor="w")

        chk_vars: dict = {}
        scroll_f = ctk.CTkScrollableFrame(dlg, fg_color="transparent", height=200)
        scroll_f.pack(fill="both", expand=True, padx=20, pady=4)

        for s in other_servers:
            var = tk.BooleanVar(value=True)
            chk_vars[s.id] = var
            row_f = ctk.CTkFrame(scroll_f, fg_color="transparent")
            row_f.pack(fill="x", pady=2)
            ctk.CTkCheckBox(
                row_f, text=s.name,
                variable=var,
                checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            ).pack(side="left", padx=8)
            if s.install_dir:
                ctk.CTkLabel(
                    row_f, text=s.install_dir,
                    text_color="gray45", font=ctk.CTkFont(size=10),
                ).pack(side="left", padx=(4, 0))
            else:
                ctk.CTkLabel(
                    row_f, text="(sem diretório configurado)",
                    text_color="#ff6666", font=ctk.CTkFont(size=10),
                ).pack(side="left", padx=(4, 0))

        # Checkboxes de controle de quais arquivos copiar
        files_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        files_frame.pack(padx=20, pady=(8, 4), anchor="w")
        copy_gus_var  = tk.BooleanVar(value=True)
        copy_game_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            files_frame, text="GameUserSettings.ini",
            variable=copy_gus_var,
            checkmark_color="white", fg_color=_BLUE, hover_color=_BLUE_HOVER,
        ).pack(side="left", padx=(0, 16))
        ctk.CTkCheckBox(
            files_frame, text="Game.ini",
            variable=copy_game_var,
            checkmark_color="white", fg_color=_BLUE, hover_color=_BLUE_HOVER,
        ).pack(side="left")

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(pady=(12, 20))

        def _do_sync():
            import shutil
            targets = [s for s in other_servers if chk_vars[s.id].get()]
            if not targets:
                messagebox.showwarning("Nada selecionado", "Selecione ao menos um servidor.", parent=dlg)
                return
            errors = []
            copied = 0
            for s in targets:
                if not s.install_dir or not os.path.isdir(s.install_dir):
                    errors.append(f"{s.name}: diretório inválido")
                    continue
                dst_dir = _get_ini_path(s.install_dir, "GameUserSettings.ini").parent
                dst_dir.mkdir(parents=True, exist_ok=True)
                if copy_gus_var.get() and gus_path.exists():
                    shutil.copy2(str(gus_path), str(dst_dir / "GameUserSettings.ini"))
                    copied += 1
                if copy_game_var.get() and game_path.exists():
                    shutil.copy2(str(game_path), str(dst_dir / "Game.ini"))
                    copied += 1

            dlg.destroy()
            msg = f"{copied} arquivo(s) copiado(s) para {len(targets)} servidor(es)."
            if errors:
                msg += "\n\nErros:\n" + "\n".join(errors)
                messagebox.showwarning("Sincronização concluída com avisos", msg, parent=self)
            else:
                messagebox.showinfo("Sincronização concluída", msg, parent=self)

        ctk.CTkButton(
            btn_row, text="🔄  Sincronizar", width=140, height=38,
            fg_color="#6a3aaa", hover_color="#7a4abb",
            command=_do_sync,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            btn_row, text="Cancelar", width=100, height=38,
            fg_color="#3a3a5a", hover_color="#252540",
            command=dlg.destroy,
        ).pack(side="left")

    # ── Mods ──────────────────────────────────────────────────────────────────

    def _add_mod(self, server_id: str, mod_name: str = "") -> None:
        w = self._server_widgets.get(server_id, {})
        mod_id = w.get("new_mod_id", tk.StringVar()).get().strip()
        if not mod_id or not mod_id.isdigit():
            messagebox.showwarning("Mod inválido", "Informe um ID numérico válido.", parent=self)
            return
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return
        if mod_id not in srv.mods:
            srv.mods.append(mod_id)
        if mod_name:
            srv.mod_names[mod_id] = mod_name
        self.config_manager.update_server(srv)
        w["new_mod_id"].set("")
        self._refresh_mods_list(server_id)
        if not mod_name and mod_id not in srv.mod_names:
            self._fetch_mod_names_async(server_id, [mod_id])

    def _fetch_mod_names_async(self, server_id: str, mod_ids: list) -> None:
        """Busca nomes dos mods via Steam API em background e atualiza a lista."""
        if not hasattr(self, "_fetching_mod_names"):
            self._fetching_mod_names: set = set()
        to_fetch = [mid for mid in mod_ids if mid not in self._fetching_mod_names]
        if not to_fetch:
            return
        self._fetching_mod_names.update(to_fetch)

        def _worker() -> None:
            names: dict = {}
            try:
                params: dict = {"itemcount": str(len(to_fetch))}
                for i, mid in enumerate(to_fetch):
                    params[f"publishedfileids[{i}]"] = mid
                data = urllib.parse.urlencode(params).encode()
                req = urllib.request.Request(
                    "https://api.steampowered.com"
                    "/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    result = json.loads(resp.read().decode())
                for f in result.get("response", {}).get("publishedfiledetails", []):
                    if f.get("result") == 1:
                        mid = str(f.get("publishedfileid", ""))
                        title = f.get("title", "").strip()
                        if mid and title:
                            names[mid] = title
            except Exception:
                pass
            finally:
                self._fetching_mod_names -= set(to_fetch)

            def _apply() -> None:
                srv = self.config_manager.get_server(server_id)
                if srv and names:
                    srv.mod_names.update(names)
                    self.config_manager.update_server(srv)
                    self._refresh_mods_list(server_id)
            self.after(0, _apply)

        threading.Thread(target=_worker, daemon=True, name="ModNameFetch").start()

    def _remove_mod(self, server_id: str, mod_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return
        if mod_id in srv.mods:
            srv.mods.remove(mod_id)
        srv.mod_names.pop(mod_id, None)
        srv.mod_ini_configs.pop(mod_id, None)
        self.config_manager.update_server(srv)
        self._refresh_mods_list(server_id)

    def _open_mod_ini_dialog(self, server_id: str, mod_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return

        cfg = srv.mod_ini_configs.get(mod_id, {})
        mod_name = srv.mod_names.get(mod_id, "")

        dlg = ctk.CTkToplevel(self)
        mod_label = f"{mod_name} ({mod_id})" if mod_name else mod_id
        dlg.title(f"Configurações INI — Mod {mod_label}")
        dlg.geometry("720x600")
        dlg.resizable(True, True)
        dlg.grab_set()
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(3, weight=1)
        dlg.grid_rowconfigure(5, weight=1)

        # ── Cabeçalho ─────────────────────────────────────────────────────────
        ctk.CTkLabel(
            dlg, text="⚙️  Configurações INI do Mod",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(16, 2), sticky="w")

        # Campo de nome do mod
        name_fr = ctk.CTkFrame(dlg, fg_color="transparent")
        name_fr.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="ew")
        name_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(name_fr, text="Nome do mod:", text_color="gray60", width=110,
                     anchor="w").grid(row=0, column=0, sticky="w")
        name_var = tk.StringVar(value=mod_name)
        ctk.CTkEntry(name_fr, textvariable=name_var, height=32,
                     placeholder_text="Ex: Structures Plus").grid(
            row=0, column=1, sticky="ew", padx=(8, 0))

        ctk.CTkLabel(
            dlg,
            text="Cole abaixo os blocos de configuração fornecidos pelo autor do mod. "
                 "Eles serão adicionados ao final dos respectivos arquivos INI do servidor.",
            text_color="gray50", font=ctk.CTkFont(size=11), wraplength=680, justify="left",
        ).grid(row=2, column=0, padx=20, pady=(0, 6), sticky="w")

        # ── Game.ini ──────────────────────────────────────────────────────────
        ctk.CTkLabel(
            dlg, text="📄  Game.ini",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=3, column=0, padx=20, pady=(4, 2), sticky="w")
        game_ini_box = ctk.CTkTextbox(dlg, font=ctk.CTkFont(family="Courier New", size=12))
        game_ini_box.grid(row=4, column=0, padx=20, pady=(0, 8), sticky="nsew")
        game_ini_box.insert("0.0", cfg.get("game_ini", ""))
        dlg.grid_rowconfigure(4, weight=1)

        # ── GameUserSettings.ini ──────────────────────────────────────────────
        ctk.CTkLabel(
            dlg, text="📄  GameUserSettings.ini",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=5, column=0, padx=20, pady=(4, 2), sticky="w")
        gus_ini_box = ctk.CTkTextbox(dlg, font=ctk.CTkFont(family="Courier New", size=12))
        gus_ini_box.grid(row=6, column=0, padx=20, pady=(0, 8), sticky="nsew")
        gus_ini_box.insert("0.0", cfg.get("gus_ini", ""))
        dlg.grid_rowconfigure(6, weight=1)

        # ── Botões ────────────────────────────────────────────────────────────
        btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_fr.grid(row=7, column=0, padx=20, pady=(0, 16), sticky="e")

        def _save():
            game_txt = game_ini_box.get("0.0", "end").strip()
            gus_txt  = gus_ini_box.get("0.0", "end").strip()
            name_txt = name_var.get().strip()
            if name_txt:
                srv.mod_names[mod_id] = name_txt
            else:
                srv.mod_names.pop(mod_id, None)
            if game_txt or gus_txt:
                srv.mod_ini_configs[mod_id] = {"game_ini": game_txt, "gus_ini": gus_txt}
            else:
                srv.mod_ini_configs.pop(mod_id, None)
            self.config_manager.update_server(srv)
            self._refresh_mods_list(server_id)
            dlg.destroy()

        def _apply_to_files():
            _save()
            from .ark_ini import ArkIniManager
            mgr = ArkIniManager(srv.install_dir)
            try:
                mgr.apply_mod_ini_configs(srv.mod_ini_configs)
                messagebox.showinfo(
                    "INI Aplicado",
                    "Configurações dos mods aplicadas nos arquivos INI do servidor.",
                    parent=self,
                )
            except Exception as exc:
                messagebox.showerror("Erro", str(exc), parent=self)

        ctk.CTkButton(
            btn_fr, text="Cancelar", width=100, height=36,
            fg_color="gray30", hover_color="gray40",
            command=dlg.destroy,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_fr, text="💾  Salvar", width=110, height=36,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=_save,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_fr, text="✅  Salvar e Aplicar nos INIs", width=200, height=36,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            command=_apply_to_files,
        ).pack(side="left")


    def _download_mod(self, server_id: str, mod_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return
        self.mod_manager.steamcmd_path = self.config_manager.config.steamcmd_path
        self.mod_manager.download_mods(
            [mod_id], srv.install_dir,
            on_done=lambda ok: self.after(0, lambda: self._refresh_mods_list(server_id)),
        )

    def _download_all_mods(self, server_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        if not srv or not srv.mods:
            messagebox.showinfo("Mods", "Nenhum mod para baixar.", parent=self)
            return
        self.mod_manager.steamcmd_path = self.config_manager.config.steamcmd_path
        self.mod_manager.download_mods(
            srv.mods, srv.install_dir,
            on_done=lambda ok: self.after(0, lambda: self._refresh_mods_list(server_id)),
        )

    def _open_workshop_page(self, mod_id: str) -> None:
        import webbrowser
        webbrowser.open(self.mod_manager.get_mod_workshop_url(mod_id))

    # ── RCON ──────────────────────────────────────────────────────────────────

    def _rcon_connect(self, server_id: str) -> None:
        w   = self._server_widgets.get(server_id, {})
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return

        host     = w.get("rcon_host",        tk.StringVar(value="127.0.0.1")).get()
        port_str = w.get("rcon_port_entry",   tk.StringVar(value=str(srv.rcon_port))).get()
        password = srv.rcon_password or srv.admin_password

        existing = self._rcon_clients.get(server_id)
        if existing and existing.is_connected:
            existing.disconnect()
            del self._rcon_clients[server_id]
            w.get("rcon_status_var", tk.StringVar()).set("⬛ Desconectado")
            w["rcon_connect_btn"].configure(text="🔌 Conectar",
                                            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER)
            return

        try:
            port = int(port_str)
        except ValueError:
            port = srv.rcon_port

        def _do_connect():
            client = RconClient(host, port, password,
                                on_log=lambda m, level: self._global_log(f"[RCON] {m}", level))
            try:
                client.connect()
                self._rcon_clients[server_id] = client
                def _ok():
                    w.get("rcon_status_var", tk.StringVar()).set(f"🟢 Conectado a {host}:{port}")
                    w["rcon_connect_btn"].configure(text="🔌 Desconectar",
                                                   fg_color=_RED_DARK, hover_color=_RED_HOVER)
                    self._rcon_append(server_id, f"Conectado a {host}:{port}\n", "sys")
                self.after(0, _ok)
            except RconError as exc:
                err_msg = str(exc)
                def _err(msg: str = err_msg):
                    w.get("rcon_status_var", tk.StringVar()).set(f"🔴 Erro: {msg}")
                    self._rcon_append(server_id, f"Erro de conexão: {msg}\n", "err")
                self.after(0, _err)

        threading.Thread(target=_do_connect, daemon=True).start()

    def _rcon_send(self, server_id: str) -> None:
        w = self._server_widgets.get(server_id, {})
        cmd = w.get("rcon_input", tk.StringVar()).get().strip()
        if not cmd:
            return
        w["rcon_input"].set("")
        self._rcon_exec(server_id, cmd)

    def _rcon_exec(self, server_id: str, command: str) -> None:
        client = self._rcon_clients.get(server_id)
        self._rcon_append(server_id, f"> {command}\n", "cmd")

        if not client or not client.is_connected:
            self._rcon_append(server_id, "Não conectado. Clique em 'Conectar' primeiro.\n", "err")
            return

        def _do():
            ok, result = client.send_command_safe(command)
            level = "resp" if ok else "err"
            self.after(0, lambda: self._rcon_append(
                server_id, (result or "(sem resposta)") + "\n", level))

        threading.Thread(target=_do, daemon=True).start()

    def _rcon_append(self, server_id: str, text: str, tag: str = "resp") -> None:
        w = self._server_widgets.get(server_id, {})
        box: Optional[ctk.CTkTextbox] = w.get("rcon_output")
        if not box:
            return
        box.configure(state="normal")
        box._textbox.insert("end", text, tag)
        box._textbox.see("end")
        box.configure(state="disabled")

    # ── Callbacks de status e log ─────────────────────────────────────────────

    def _on_server_status_change(self, server_id: str, status: str) -> None:
        def _do():
            color = _STATUS_COLOR.get(status, "#ff6666")
            label = _STATUS_LABEL.get(status, status)

            w = self._server_widgets.get(server_id, {})
            sv: Optional[tk.StringVar]  = w.get("_status_var")
            sl: Optional[ctk.CTkLabel]  = w.get("_status_lbl")
            ss: Optional[ctk.CTkButton] = w.get("_start_stop_btn")
            if sv:
                sv.set(label)
            if sl:
                sl.configure(text_color=color)
            if ss:
                is_running = status == SERVER_STATUS_RUNNING
                is_busy    = status in (SERVER_STATUS_STARTING, SERVER_STATUS_STOPPING)
                if is_busy:
                    ss.configure(
                        text="⚡ Cancelar",
                        fg_color="#7a4a00", hover_color="#5c3600",
                        state="normal",
                    )
                elif is_running:
                    ss.configure(
                        text="⏹ Parar",
                        fg_color=_RED_DARK, hover_color=_RED_HOVER,
                        state="normal",
                    )
                else:
                    ss.configure(
                        text="▶ Iniciar",
                        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                        state="normal",
                    )

            # Bloquear/desbloquear configurações
            self._set_config_editable(server_id, status == SERVER_STATUS_STOPPED)

            btn = self._sidebar_server_btns.get(server_id)
            if btn and hasattr(btn, "_status_dot"):
                btn._status_dot.configure(text_color=color)

            self._refresh_dashboard()
        self.after(0, _do)

    def _set_config_editable(self, server_id: str, editable: bool) -> None:
        """Habilita ou desabilita todos os widgets de configuração das abas do servidor."""
        w = self._server_widgets.get(server_id, {})

        # Banner de bloqueio
        banner = w.get("_lock_banner")
        if banner:
            if editable:
                banner.grid_remove()
            else:
                banner.grid()

        # Abas de configuração (exceto Console RCON e Logs)
        tabs: Optional[ctk.CTkTabview] = w.get("_tabs")
        if not tabs:
            return

        _CONFIG_TABS = ("Geral", "Jogo", "Avançado", "Mods", "Plugins")
        state = "normal" if editable else "disabled"

        def _set_recursive(widget) -> None:
            try:
                wclass = widget.winfo_class()
                if wclass in ("TButton", "TEntry", "TCheckbutton", "TCombobox", "TSpinbox"):
                    widget.configure(state=state)
                elif hasattr(widget, "configure"):
                    try:
                        widget.configure(state=state)
                    except Exception:
                        pass
            except Exception:
                pass
            for child in widget.winfo_children():
                _set_recursive(child)

        for tab_name in _CONFIG_TABS:
            try:
                tab_frame = tabs.tab(tab_name)
                _set_recursive(tab_frame)
            except Exception:
                pass


    def _on_server_log(self, server_id: str, msg: str, level: str) -> None:
        def _do():
            w = self._server_widgets.get(server_id, {})
            box: Optional[ctk.CTkTextbox] = w.get("_log_box")
            if box:
                box.configure(state="normal")
                box._textbox.insert("end", msg + "\n", level)
                box._textbox.see("end")
                box.configure(state="disabled")
        self.after(0, _do)

    def _clear_server_log(self, server_id: str) -> None:
        inst = self.server_manager.get_instance(server_id)
        if inst and hasattr(inst, "log_buffer"):
            inst.log_buffer.clear()
        w = self._server_widgets.get(server_id, {})
        box: Optional[ctk.CTkTextbox] = w.get("_log_box")
        if box:
            box.configure(state="normal")
            box.delete("1.0", "end")
            box.configure(state="disabled")

    # ── Diálogo "Novo Servidor" ───────────────────────────────────────────────

    def _on_server_visibility_change(self, server_id: str, mode: str) -> None:
        """Callback chamado quando o online_mode de um servidor muda (—/LAN/WAN)."""
        def _do():
            w = self._server_widgets.get(server_id, {})
            vis_lbl: Optional[ctk.CTkLabel] = w.get("_visibility_lbl")
            if vis_lbl:
                if mode == "WAN":
                    vis_lbl.configure(text="🌐 WAN", text_color=_GREEN)
                elif mode == "LAN":
                    vis_lbl.configure(text="🏠 LAN", text_color="#ffaa44")
                else:
                    vis_lbl.configure(text="", text_color="gray50")
            self._refresh_dashboard()
        self.after(0, _do)

    def _on_auto_updater_log(self, msg: str, level: str) -> None:
        def _do():
            box = self._auto_updater_log_box
            if box:
                box.configure(state="normal")
                box._textbox.insert("end", msg + "\n", level)
                box._textbox.see("end")
                box.configure(state="disabled")
            # Também envia para o log global
            self._global_log(msg, level)
        self.after(0, _do)

    def _dialog_add_server(self) -> None:
        dlg = ctk.CTkToplevel(self)
        dlg.title("Novo Servidor ARK")
        dlg.geometry("520x500")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(dlg, text="Novo Servidor",
                     font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=20, pady=(20, 16), sticky="w")

        fields: Dict[str, tk.StringVar] = {}

        def field_row(label: str, key: str, default: str, rn: int,
                      combo: Optional[List] = None, browse: bool = False) -> None:
            ctk.CTkLabel(dlg, text=label, width=170, anchor="w",
                         text_color="gray60").grid(row=rn, column=0, padx=20, pady=6)
            fields[key] = tk.StringVar(value=default)
            if combo:
                ctk.CTkComboBox(dlg, variable=fields[key], values=combo,
                                width=260, height=34).grid(
                    row=rn, column=1, padx=(0, 20), pady=6, sticky="ew")
            elif browse:
                fr = ctk.CTkFrame(dlg, fg_color="transparent")
                fr.grid(row=rn, column=1, padx=(0, 20), pady=6, sticky="ew")
                fr.grid_columnconfigure(0, weight=1)
                ctk.CTkEntry(fr, textvariable=fields[key], height=34).grid(
                    row=0, column=0, sticky="ew", padx=(0, 6))
                ctk.CTkButton(fr, text="📁", width=34, height=34,
                              command=lambda: self._browse_dir(fields[key])).grid(row=0, column=1)
            else:
                ctk.CTkEntry(dlg, textvariable=fields[key], height=34).grid(
                    row=rn, column=1, padx=(0, 20), pady=6, sticky="ew")

        field_row("Nome do Servidor (label):", "name",       "Meu Servidor ARK", 1)
        field_row("Mapa:", "map", "TheIsland", 2, combo=[
            f"{ARK_MAP_NAMES.get(m, m)} ({m})" for m in ARK_MAPS])
        field_row("Diretório de Instalação:", "install_dir", "",                 3, browse=True)
        field_row("Porta do Servidor:",       "port",        "7777",             4)
        field_row("Porta Query:",             "qport",       "27015",            5)
        field_row("Porta RCON:",              "rport",       "27020",            6)
        field_row("Senha de Admin:",          "admin_pass",  "",                 7)

        def _create():
            name = fields["name"].get().strip() or "Servidor ARK"
            map_raw = fields["map"].get()
            if "(" in map_raw and map_raw.endswith(")"):
                map_id = map_raw.split("(")[-1].rstrip(")")
            else:
                map_id = map_raw

            srv = ServerConfig(
                name           = name,
                map            = map_id,
                install_dir    = fields["install_dir"].get().strip(),
                server_name    = name,
                admin_password = fields["admin_pass"].get(),
                rcon_password  = fields["admin_pass"].get(),
            )
            try:
                srv.server_port = int(fields["port"].get())
                srv.query_port  = int(fields["qport"].get())
                srv.rcon_port   = int(fields["rport"].get())
            except ValueError:
                pass

            self.config_manager.add_server(srv)
            self.server_manager.add_server(srv)
            self._rebuild_server_sidebar()
            self._refresh_dashboard()
            dlg.destroy()
            self._open_server_panel(srv.id)

        ctk.CTkButton(
            dlg, text="✅  Criar Servidor", height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=_create,
        ).grid(row=8, column=0, columnspan=2, padx=20, pady=(16, 20), sticky="ew")

    # ── Configurações Globais ─────────────────────────────────────────────────

    def _save_global_config(self) -> None:
        cfg = self.config_manager.config
        cfg.steamcmd_path        = self._steamcmd_var.get().strip()
        cfg.default_install_dir  = self._default_dir_var.get().strip()
        cfg.startup_with_windows = self._cfg_startup_var.get()
        cfg.minimize_to_tray     = self._cfg_minimize_tray_var.get()
        cfg.log_debug            = self._cfg_log_debug_var.get()
        _set_windows_startup(cfg.startup_with_windows)
        self.config_manager.save()
        self.mod_manager.steamcmd_path = cfg.steamcmd_path
        messagebox.showinfo("Salvo", "Configurações globais salvas!", parent=self)

    # ── Update checker ────────────────────────────────────────────────────────

    def _check_updates_on_start(self) -> None:
        url = self.config_manager.config.update_url
        if not url:
            return
        self.update_checker.check_async(
            url, on_result=lambda info: self.after(0, lambda: self._on_update_result(info)))

    def _start_mod_auto_updater(self) -> None:
        """Inicia o verificador automático de mods ao carregar o app."""
        if self._mod_auto_updater is not None and self._mod_auto_updater.enabled:
            return
        if self._mod_auto_updater is None:
            self._mod_auto_updater = ModAutoUpdater(
                server_manager=self.server_manager,
                mod_manager=self.mod_manager,
                get_servers=lambda: self.config_manager.servers,
                on_log=self._on_auto_updater_log,
                check_interval_minutes=15,
                warning_minutes=5,
            )
        self._mod_auto_updater.start()
        # Atualiza botões/labels em todos os painéis já construídos
        for ww in self._server_widgets.values():
            btn = ww.get("_au_toggle_btn")
            lbl = ww.get("_au_status_lbl")
            if btn:
                btn.configure(text="⏸ Parar", fg_color=_RED_DARK, hover_color=_RED_HOVER)
            if lbl:
                lbl.configure(text="● ATIVO", text_color=_GREEN)

    def _check_updates_manual(self) -> None:
        url = self.config_manager.config.update_url
        if not url:
            return
        self._check_update_btn.configure(state="disabled", text="🔍  Verificando...")
        self.update_checker.check_async(
            url,
            on_result=lambda info: self.after(
                0, lambda: self._on_update_result(info, manual=True)))

    def _on_update_result(self, info, manual: bool = False) -> None:
        from datetime import datetime
        self._last_check_var.set(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        self._check_update_btn.configure(state="normal", text="🔍  Verificar Atualizações")
        if info is None:
            if manual:
                self._update_status_var.set("❌  Não foi possível verificar")
                self._update_status_lbl.configure(text_color="#ff6666")
            return
        if info.is_newer_than(APP_VERSION):
            self._update_status_var.set(f"🔔  v{info.version} disponível!")
            self._update_status_lbl.configure(text_color="#ffaa44")
            self._install_update_btn.configure(
                state="normal", text=f"⬇️  Instalar v{info.version}")
            self._sidebar_update_lbl.configure(text=f"🔔 v{info.version} disponível")
            self._nav_buttons.get("sobre", ctk.CTkButton(self)).configure(text="ℹ️  Sobre  🔔")
        else:
            self._update_status_var.set("✅  Versão mais recente")
            self._update_status_lbl.configure(text_color=_GREEN)
            self._install_update_btn.configure(state="disabled", text="⬇️  Baixar e Instalar")
            self._sidebar_update_lbl.configure(text="")

    def _start_download_update(self) -> None:
        info = self.update_checker.latest
        if not info:
            return
        self._install_update_btn.configure(state="disabled", text="⏳  Iniciando agente...")
        self._check_update_btn.configure(state="disabled")
        self.update_checker.download_and_install(
            info,
            on_done=lambda ok, msg: self.after(0, lambda: self._on_download_done(ok, msg)),
        )

    def _on_download_done(self, success: bool, message: str) -> None:
        if success:
            self._update_progress_label.configure(
                text="✅  Agente iniciado. O app será fechado e a atualização instalada automaticamente.")
            self._update_progress_label.grid(row=4, column=0, columnspan=2, padx=18, sticky="w")
            messagebox.showinfo(
                "Atualização",
                "O agente de atualização foi iniciado.\n\n"
                "O ARKLAND será fechado agora. Quando a instalação terminar, o app reiniciará automaticamente.",
                parent=self,
            )
            self._on_close()
        else:
            self._check_update_btn.configure(state="normal")
            self._update_progress_label.configure(text=f"❌  Erro: {message}")
            self._update_progress_label.grid(row=4, column=0, columnspan=2, padx=18, sticky="w")
            self._install_update_btn.configure(state="normal", text="⬇️  Tentar Novamente")

    # ── Logs globais ──────────────────────────────────────────────────────────

    def _global_log(self, msg: str, level: str = "info") -> None:
        self._global_log_buf.append(f"[{level.upper()}] {msg}")

    # ── Navegação ─────────────────────────────────────────────────────────────

    def _show_frame(self, name: str) -> None:
        self._current_frame = name
        for key, frame in self._frames.items():
            if key == name:
                frame.grid()
            else:
                frame.grid_remove()
        for key, btn in self._nav_buttons.items():
            btn.configure(fg_color="#1e2a3a" if key == name else "transparent")
        for srv_id, btn in self._sidebar_server_btns.items():
            active = name == f"server_{srv_id}"
            btn.configure(fg_color="#1e2a3a" if active else "transparent")
        if name == "buffs":
            self.after(50, self._refresh_buffs_ui)

    # ── Helpers de UI ─────────────────────────────────────────────────────────

    def _section_lbl(self, parent, row: int, text: str) -> None:
        ctk.CTkLabel(parent, text=text,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#88d4a0").grid(
            row=row, column=0, columnspan=4, padx=16, pady=(10, 2), sticky="w")

    def _save_btn_row(self, parent, row: int, server_id: str) -> None:
        ctk.CTkButton(
            parent, text="💾  Salvar & Aplicar Configurações",
            height=42, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=lambda: self._save_server_config(server_id),
        ).grid(row=row, column=0, columnspan=4, padx=16, pady=(16, 24), sticky="ew")

    def _browse_dir(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory(parent=self, title="Selecionar pasta")
        if path:
            var.set(path)

    def _browse_file(self, var: tk.StringVar, title: str = "Selecionar arquivo") -> None:
        path = filedialog.askopenfilename(parent=self, title=title,
                                          filetypes=[("Executável", "*.exe"), ("Todos", "*.*")])
        if path:
            var.set(path)

    # ── Download automático do SteamCMD ───────────────────────────────────────

    _STEAMCMD_URL = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"

    def _download_steamcmd(self) -> None:
        """Baixa, extrai e inicializa o SteamCMD automaticamente."""
        dest_dir = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "ARKLAND-ServerManager", "steamcmd",
        )
        steamcmd_exe = os.path.join(dest_dir, "steamcmd.exe")

        # Se já existe, apenas confirma o caminho
        if os.path.isfile(steamcmd_exe):
            self._steamcmd_var.set(steamcmd_exe)
            self._steamcmd_status_lbl.configure(
                text="✅  SteamCMD já instalado. Caminho configurado automaticamente.",
                text_color="#4CAF50",
            )
            return

        self._steamcmd_dl_btn.configure(state="disabled", text="⏳  Baixando...")
        self._steamcmd_status_lbl.configure(
            text="Baixando SteamCMD da Valve... aguarde.", text_color="gray60"
        )

        def _worker() -> None:
            try:
                os.makedirs(dest_dir, exist_ok=True)

                # Download
                self.after(0, lambda: self._steamcmd_status_lbl.configure(
                    text="📥  Baixando steamcmd.zip...", text_color="gray60"))
                with urllib.request.urlopen(self._STEAMCMD_URL, timeout=60) as resp:
                    data = resp.read()

                # Extração
                self.after(0, lambda: self._steamcmd_status_lbl.configure(
                    text="📦  Extraindo...", text_color="gray60"))
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    zf.extractall(dest_dir)

                if not os.path.isfile(steamcmd_exe):
                    raise FileNotFoundError("steamcmd.exe não encontrado após extração.")

                # Primeira execução para atualizar os arquivos do SteamCMD
                self.after(0, lambda: self._steamcmd_status_lbl.configure(
                    text="⚙️  Inicializando SteamCMD (primeira execução)...", text_color="gray60"))
                import subprocess
                subprocess.run(
                    [steamcmd_exe, "+quit"],
                    cwd=dest_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=120,
                )

                # Sucesso
                def _on_success() -> None:
                    self._steamcmd_var.set(steamcmd_exe)
                    self._steamcmd_dl_btn.configure(state="normal", text="⬇  Baixar SteamCMD")
                    self._steamcmd_status_lbl.configure(
                        text="✅  SteamCMD instalado com sucesso! Caminho configurado automaticamente.",
                        text_color="#4CAF50",
                    )
                    # Salva a configuração imediatamente
                    self.config_manager.config.steamcmd_path = steamcmd_exe
                    self.mod_manager.steamcmd_path = steamcmd_exe
                    self.config_manager.save()

                self.after(0, _on_success)

            except Exception as exc:
                def _on_error(e: Exception = exc) -> None:
                    self._steamcmd_dl_btn.configure(state="normal", text="⬇  Baixar SteamCMD")
                    self._steamcmd_status_lbl.configure(
                        text=f"❌  Erro ao baixar SteamCMD: {e}",
                        text_color="#f44336",
                    )
                self.after(0, _on_error)

        threading.Thread(target=_worker, daemon=True, name="SteamCMDDownload").start()

    # ── Encerramento ──────────────────────────────────────────────────────────

    def _on_close(self) -> None:
        if self.config_manager.config.minimize_to_tray and _PYSTRAY_OK:
            self._minimize_to_tray()
            return
        self._do_quit()

    def _do_quit(self) -> None:
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None
        if self._sync_engine and self._sync_engine.is_running:
            self._sync_engine.stop()
        if self._mod_auto_updater and self._mod_auto_updater.enabled:
            self._mod_auto_updater.stop()
        if self._buff_manager:
            self._buff_manager.stop()
        for srv in self.config_manager.servers:
            inst = self.server_manager.get_instance(srv.id)
            if inst and inst.status == SERVER_STATUS_RUNNING:
                self.server_manager.stop_server(srv.id, force=True)
        for client in list(self._rcon_clients.values()):
            try:
                client.disconnect()
            except Exception:
                pass
        self.config_manager.save()
        self.destroy()

    # ── Bandeja do sistema ────────────────────────────────────────────────────

    def _minimize_to_tray(self) -> None:
        if not _PYSTRAY_OK or pystray is None or _PILImage is None:
            messagebox.showwarning(
                "Dependências ausentes",
                "Minimizar para bandeja requer pystray e Pillow instalados.",
                parent=self,
            )
            return

        self.withdraw()
        if self._tray_icon:
            return  # já existe

        try:
            img = _PILImage.open(_resource_path(os.path.join("ig", "ArkLandBR.png"))).resize((64, 64))
        except Exception:
            # Cria ícone genérico verde se a imagem não estiver disponível
            img = _PILImage.new("RGBA", (64, 64), "#4CAF50")

        menu = pystray.Menu(
            pystray.MenuItem("Abrir ARKLAND", self._restore_from_tray, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", lambda icon, item: self.after(0, self._do_quit)),
        )
        self._tray_icon = pystray.Icon(
            "ARKLAND-ServerManager",
            img,
            "ARKLAND - Server Manager",
            menu,
        )
        threading.Thread(
            target=self._tray_icon.run,
            daemon=True,
            name="TrayIconThread",
        ).start()

    def _restore_from_tray(self, icon=None, item=None) -> None:
        self.after(0, self._do_restore)

    def _do_restore(self) -> None:
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None
        self.deiconify()
        self.lift()
        self.focus_force()
