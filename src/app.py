"""
Interface gráfica principal do ARKLAND - Server Manager.
"""
from __future__ import annotations

import io
import json
import os
import platform
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
from datetime import datetime, timezone, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Callable, Dict, List, Optional, Tuple

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

try:
    import psutil as _psutil
    _PSUTIL_OK = True
except ImportError:
    _psutil = None  # type: ignore[assignment]
    _PSUTIL_OK = False

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
from .breeding_calculator import open_breeding_calculator
from .rcon_client import RconClient, RconError
from .updater import UpdateChecker
from .arkshop_manager import ArkShopManager, GENERAL_BOOL_LABELS
from .mod_auto_updater import ModAutoUpdater
from .backup_manager import BackupManager
from .discord_notifier import DiscordNotifier
from .buff_manager import (
    BuffManager, BuffEvent, BuffPreset, BuffRates,
    BUFF_TYPE_XP, BUFF_TYPE_DOMA, BUFF_TYPE_BREEDING, BUFF_TYPE_FARM,
    BUFF_TYPE_LABELS, BUFF_RATE_FIELDS, QUICK_PRESETS,
    BUFF_STATUS_SCHEDULED,
    BUFF_STATUS_CANCELLED,
)
from .version import APP_VERSION, BUILD_DATE, CHANGELOG
from .beacon_client import get_beacon_client
from .change_logger import ChangeLogger, snapshot_server, diff_snapshots
from .ark_ini import parse_ini_text_to_sections, sections_to_ini_text
from .ark_ini import build_dynamic_config
from .dynamic_config_server import DynamicConfigServer

APP_NAME = "ARKLAND - Server Manager"

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

        self._discord_notifier = DiscordNotifier(self.config_manager.config.discord_notify)

        self.server_manager = ServerManager(
            on_status_change=self._on_server_status_change,
            on_log=self._on_server_log,
            on_visibility_change=self._on_server_visibility_change,
            get_cluster_profile=self.config_manager.get_cluster,
            get_dynamic_config_url=self._get_dynamic_config_url,
            discord_notifier=self._discord_notifier,
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
        self._config_search_index: Dict[str, List] = {}
        self._rcon_clients: Dict[str, RconClient] = {}
        self._rcon_auto_enabled: Dict[str, bool] = {}   # True = tentar reconectar quando RUNNING
        self._rcon_auto_jobs: Dict[str, Optional[str]] = {}  # after() job id por servidor
        self._chat_poll_jobs: Dict[str, Optional[str]] = {}   # after() job id para chat por servidor
        self._current_frame: str = ""
        self._sidebar_server_btns: Dict[str, ctk.CTkButton] = {}
        self._global_log_buf: List[str] = []
        self._tray_icon: Any = None
        self._sync_engine: Optional[SyncEngine] = None
        self._cluster_sync_engines: Dict[str, SyncEngine] = {}  # engines de sync por cluster ID
        self._dynamic_config_server = DynamicConfigServer()      # HTTP server para DynamicConfigURL
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
        self._buff_countdown_job: Optional[str] = None  # after() job do ticker de countdown
        self._buff_countdown_labels: list = []          # [(label_widget, target_datetime, prefix)]

        # Backup automático
        self._backup_manager: Optional[BackupManager] = None

        # Desempenho
        self._perf_running: bool = False
        self._perf_thread: Optional[threading.Thread] = None
        self._perf_cpu_pct_var: Any = None
        self._perf_cpu_bar: Any = None
        self._perf_cpu_info_var: Any = None
        self._perf_ram_pct_var: Any = None
        self._perf_ram_bar: Any = None
        self._perf_ram_info_var: Any = None
        self._perf_gpu_pct_var: Any = None
        self._perf_gpu_bar: Any = None
        self._perf_gpu_info_var: Any = None
        self._perf_alert_warn_var: Any = None
        self._perf_alert_crit_var: Any = None
        self._perf_critical_log: Any = None
        self._perf_last_state: dict = {"cpu": "ok", "ram": "ok", "gpu": "ok"}

        self._build_ui()
        self.after(200, self._scan_running_servers)
        self.after(500, self._auto_start_sync)
        self.after(1600, self._auto_start_cluster_syncs)
        self.after(1700, self._auto_start_dynamic_configs)
        self.after(4000, self._check_updates_on_start)
        self.after(2000, self._start_mod_auto_updater)
        self.after(600, self._init_buff_manager)
        self.after(800, self._init_backup_manager)
        self.after(1000, self._arkshop_load_presets_file)
        self.after(1200, self._start_perf_monitor)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Unmap>", self._on_unmap_event)

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
        ver_clock = ctk.CTkFrame(sb, fg_color="transparent")
        ver_clock.grid(row=2, column=0, pady=(0, 6))
        ctk.CTkLabel(ver_clock, text=f"v{APP_VERSION}",
                     font=ctk.CTkFont(size=10), text_color="gray50").pack()
        self._sidebar_clock_lbl = ctk.CTkLabel(
            ver_clock, text="",
            font=ctk.CTkFont(size=11), text_color="#88d4a0",
        )
        self._sidebar_clock_lbl.pack(pady=(2, 0))
        self.after(100, self._sidebar_clock_tick)

        ctk.CTkFrame(sb, height=1, fg_color="#2a2a44").grid(
            row=3, column=0, sticky="ew", padx=12, pady=4)

        self._nav_buttons: Dict[str, ctk.CTkButton] = {}
        for i, (label, key) in enumerate([
            ("🏠  Dashboard",      "dashboard"),
            ("🔄  Sincronização",  "sync"),
            ("⚡  BUFFs",          "buffs"),
            ("📊  Desempenho",     "desempenho"),
            ("🏪  ArkShop",        "arkshop"),
            ("🔗  Clusters",       "clusters"),
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
            row=12, column=0, sticky="ew", padx=12, pady=8)

        # Título "Servidores" + botão "+"
        srv_hdr = ctk.CTkFrame(sb, fg_color="transparent")
        srv_hdr.grid(row=13, column=0, padx=12, pady=(0, 4), sticky="ew")
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
        self._servers_list_sb.grid(row=14, column=0, sticky="ew", padx=6)
        self._servers_list_sb.grid_columnconfigure(0, weight=1)

        self._sidebar_update_lbl = ctk.CTkLabel(
            sb, text="", font=ctk.CTkFont(size=10), text_color="#ffaa44", wraplength=180)
        self._sidebar_update_lbl.grid(row=15, column=0, padx=10, pady=4)

        # ── Botões de Perfil ──────────────────────────────────────────────────
        ctk.CTkFrame(sb, height=1, fg_color="#2a2a44").grid(
            row=16, column=0, sticky="ew", padx=12, pady=(2, 4))
        ctk.CTkLabel(sb, text="PERFIL",
                     font=ctk.CTkFont(size=10, weight="bold"), text_color="gray50").grid(
            row=17, column=0, padx=16, pady=(0, 2), sticky="w")
        profile_fr = ctk.CTkFrame(sb, fg_color="transparent")
        profile_fr.grid(row=18, column=0, padx=10, pady=(0, 10), sticky="ew")
        profile_fr.grid_columnconfigure(0, weight=1)
        profile_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkButton(
            profile_fr, text="💾 Exportar", height=28,
            fg_color="#252540", hover_color="#1a1a35",
            font=ctk.CTkFont(size=11),
            command=self._export_profile,
        ).grid(row=0, column=0, padx=(0, 2), sticky="ew")
        ctk.CTkButton(
            profile_fr, text="📂 Importar", height=28,
            fg_color="#252540", hover_color="#1a1a35",
            font=ctk.CTkFont(size=11),
            command=self._import_profile,
        ).grid(row=0, column=1, padx=(2, 0), sticky="ew")

    def _rebuild_server_sidebar(self) -> None:
        """Atualiza a lista de botões de servidores na sidebar.

        Se os IDs já existem, apenas atualiza nome e cor do dot (evita
        destruir+recriar todos os widgets a cada salvamento).
        """
        servers = self.config_manager.servers
        current_ids = [s.id for s in servers]
        existing_ids = list(self._sidebar_server_btns.keys())

        # Verifica se a lista mudou (adição/remoção/reordenação)
        if current_ids != existing_ids:
            # Rebuild completo somente quando necessário
            for w in self._servers_list_sb.winfo_children():
                w.destroy()
            self._sidebar_server_btns.clear()

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
        else:
            # Lista igual — apenas atualiza nome e cor sem recriar widgets
            for srv in servers:
                btn = self._sidebar_server_btns.get(srv.id)
                if not btn:
                    continue
                btn.configure(text=f"  {srv.name}")
                inst = self.server_manager.get_instance(srv.id)
                status = inst.status if inst else SERVER_STATUS_STOPPED
                color = _STATUS_COLOR.get(status, "#ff6666")
                dot = getattr(btn, "_status_dot", None)
                if dot:
                    try:
                        dot.configure(text_color=color)
                    except Exception:
                        pass

    # ── Frames estáticos ──────────────────────────────────────────────────────

    def _build_static_frames(self) -> None:
        dash = ctk.CTkFrame(self, corner_radius=0, fg_color=_BG)
        dash.grid(row=0, column=1, sticky="nsew")
        self._build_dashboard(dash)
        self._frames["dashboard"] = dash
        dash.grid_remove()

        sync = ctk.CTkFrame(self, corner_radius=0, fg_color=_BG)
        sync.grid(row=0, column=1, sticky="nsew")
        self._build_sync_panel(sync)
        self._frames["sync"] = sync
        sync.grid_remove()

        buffs = ctk.CTkFrame(self, corner_radius=0, fg_color=_BG)
        buffs.grid(row=0, column=1, sticky="nsew")
        self._build_buffs_panel(buffs)
        self._frames["buffs"] = buffs
        buffs.grid_remove()

        desemp = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color=_BG)
        desemp.grid(row=0, column=1, sticky="nsew")
        self._build_performance_panel(desemp)
        self._frames["desempenho"] = desemp
        desemp.grid_remove()

        arkshop = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color=_BG)
        arkshop.grid(row=0, column=1, sticky="nsew")
        self._build_arkshop_panel(arkshop)
        self._frames["arkshop"] = arkshop
        arkshop.grid_remove()

        clusters = ctk.CTkFrame(self, corner_radius=0, fg_color=_BG)
        clusters.grid(row=0, column=1, sticky="nsew")
        self._build_clusters_panel(clusters)
        self._frames["clusters"] = clusters
        clusters.grid_remove()

        conf = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color=_BG)
        conf.grid(row=0, column=1, sticky="nsew")
        self._build_global_config(conf)
        self._frames["config"] = conf
        conf.grid_remove()

        sobre = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color=_BG)
        sobre.grid(row=0, column=1, sticky="nsew")
        self._build_about(sobre)
        self._frames["sobre"] = sobre
        sobre.grid_remove()

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

    def _scan_running_servers(self) -> None:
        """Detecta servidores ARK já em execução e reconecta ao iniciar o app.
        Útil após restart automático pelo updater — os servidores continuam rodando
        enquanto o app é atualizado e relançado.
        """
        def _do() -> None:
            count = self.server_manager.scan_running_servers()
            if count:
                self._global_log(
                    f"{count} servidor(es) já em execução detectado(s) e reconectado(s).",
                    "info",
                )
        threading.Thread(target=_do, daemon=True, name="ScanRunningServers").start()

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

    def _init_backup_manager(self) -> None:
        """Inicializa o BackupManager e agenda os timers de auto-backup."""
        self._backup_manager = BackupManager(
            get_servers=lambda: self.config_manager.servers,
            on_log=self._global_log,
        )
        self._backup_manager.restart_all(self.config_manager.servers)

    def _build_buffs_panel(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        # ── Cabeçalho (row 0) ───────────────────────────────────────────────
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

        # ── Seletor de servidor (row 1) ─────────────────────────────────────
        sel_bar = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=10)
        sel_bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 4))
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

        # ── Body scrollável (row 2, reconstruído no refresh) ────────────────
        body = ctk.CTkScrollableFrame(parent, fg_color=_BG)
        body.grid(row=2, column=0, sticky="nsew", padx=0, pady=(4, 0))
        body.grid_columnconfigure(0, weight=1)
        self._buffs_body_frame = body

    def _refresh_buffs_ui(self) -> None:
        """Reconstrói o conteúdo dinâmico do painel BUFFs."""
        body = self._buffs_body_frame
        if body is None:
            return

        # Cancela ticker de countdown anterior
        if self._buff_countdown_job:
            try:
                self.after_cancel(self._buff_countdown_job)
            except Exception:
                pass
            self._buff_countdown_job = None
        self._buff_countdown_labels = []

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

        # Inicia ticker de countdown (1s)
        self._buff_countdown_job = self.after(1000, self._buff_countdown_tick)

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
        ).grid(row=3, column=0, padx=16, pady=(0, 4), sticky="w")

        countdown_lbl = ctk.CTkLabel(
            card, text="",
            text_color="#88d4a0", font=ctk.CTkFont(size=11),
        )
        countdown_lbl.grid(row=4, column=0, padx=16, pady=(0, 14), sticky="w")
        self._buff_countdown_labels.append((countdown_lbl, event.end_datetime(), "⏱ Encerra em: "))

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
            row=2, column=0, padx=(16, 8), pady=(0, 2), sticky="w")

        countdown_lbl = ctk.CTkLabel(
            card, text="",
            text_color="#aaaaff", font=ctk.CTkFont(size=11),
        )
        countdown_lbl.grid(row=3, column=0, padx=(16, 8), pady=(0, 10), sticky="w")
        self._buff_countdown_labels.append((countdown_lbl, event.start_datetime(), "⏳ Inicia em: "))

        ctk.CTkButton(
            card, text="✕  Cancelar", width=110, height=30,
            fg_color=_RED_DARK, hover_color=_RED_HOVER,
            font=ctk.CTkFont(size=11),
            command=lambda eid=event.id: self._cancel_buff(eid),
        ).grid(row=0, column=2, rowspan=4, padx=16, pady=10)

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

    def _sidebar_clock_tick(self) -> None:
        """Atualiza o relógio da sidebar a cada segundo."""
        try:
            n = now_brasilia()
            self._sidebar_clock_lbl.configure(
                text=n.strftime("%d/%m/%Y\n%H:%M:%S")
            )
        except Exception:
            pass
        self.after(1000, self._sidebar_clock_tick)

    @staticmethod
    def _format_countdown(target: "datetime") -> str:
        """Formata o tempo restante até `target` como Xd Xh Xm Xs."""
        delta = target - now_brasilia()
        total = int(delta.total_seconds())
        if total <= 0:
            return "00s"
        d, rem = divmod(total, 86400)
        h, rem = divmod(rem, 3600)
        m, s   = divmod(rem, 60)
        parts = []
        if d:
            parts.append(f"{d}d")
        if h or d:
            parts.append(f"{h:02d}h")
        if m or h or d:
            parts.append(f"{m:02d}m")
        parts.append(f"{s:02d}s")
        return " ".join(parts)

    def _buff_countdown_tick(self) -> None:
        """Atualiza todos os labels de countdown registrados (chamado a cada 1s)."""
        alive = []
        for lbl, target, prefix in self._buff_countdown_labels:
            try:
                if lbl.winfo_exists():
                    lbl.configure(text=prefix + self._format_countdown(target))
                    alive.append((lbl, target, prefix))
            except Exception:
                pass
        self._buff_countdown_labels = alive
        if alive:
            self._buff_countdown_job = self.after(1000, self._buff_countdown_tick)
        else:
            self._buff_countdown_job = None

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

        now_str = now_brasilia().strftime("%d/%m/%Y %H:00")
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
            frame.grid_remove()
            self._server_frames[server_id] = frame
            self._server_widgets[server_id] = {}
            self._build_server_panel(frame, srv)
            self._frames[f"server_{server_id}"] = frame

        self._show_frame(f"server_{server_id}")

    def _build_server_panel(self, parent: ctk.CTkFrame, srv: ServerConfig) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(3, weight=1)  # row 3 = tabs
        self._config_search_index[srv.id] = []

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

        # ── Progresso de instalação/validação (vazio por padrão) ─────────────
        install_progress_var = tk.StringVar(value="")
        ctk.CTkLabel(
            hdr, textvariable=install_progress_var,
            text_color="#fbbf24",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=2, padx=(0, 16), pady=14, sticky="w")
        self._server_widgets[srv.id]["_install_progress_var"] = install_progress_var

        status_var = tk.StringVar(value=_STATUS_LABEL.get(status, "PARADO"))
        status_lbl = ctk.CTkLabel(
            hdr, textvariable=status_var,
            text_color=_STATUS_COLOR.get(status, "#ff6666"),
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        status_lbl.grid(row=0, column=3, padx=12, pady=14)
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
        vis_lbl.grid(row=0, column=4, padx=(0, 8), pady=14)
        self._server_widgets[srv.id]["_visibility_lbl"] = vis_lbl

        ctrl = ctk.CTkFrame(hdr, fg_color="transparent")
        ctrl.grid(row=0, column=5, padx=(0, 16), pady=14)

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
        lock_banner.grid(row=2, column=0, sticky="ew")
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
        self._build_config_search_bar(parent, srv.id)
        tabs = ctk.CTkTabview(
            parent, fg_color=_CARD_BG, corner_radius=12,
            segmented_button_fg_color=_SIDEBAR_BG,
            segmented_button_selected_color=_GREEN_DARK,
            segmented_button_selected_hover_color=_GREEN_HOVER,
        )
        tabs.grid(row=3, column=0, padx=14, pady=12, sticky="nsew")
        self._server_widgets[srv.id]["_tabs"] = tabs

        _TAB_BUILDERS = {
            "Geral":        lambda: self._build_tab_general    (tabs.tab("Geral"),        srv),
            "Jogo":         lambda: self._build_tab_game       (tabs.tab("Jogo"),         srv),
            "Avançado":     lambda: self._build_tab_advanced   (tabs.tab("Avançado"),     srv),
            "Spawns":       lambda: self._build_tab_spawns     (tabs.tab("Spawns"),       srv),
            "Loot":         lambda: self._build_tab_loot       (tabs.tab("Loot"),         srv),
            "Mods":         lambda: self._build_tab_mods       (tabs.tab("Mods"),         srv),
            "📝 INI":       lambda: self._build_tab_ini_mods   (tabs.tab("📝 INI"),       srv),
            "Admins":       lambda: self._build_tab_admins     (tabs.tab("Admins"),       srv),
            "Jogadores":    lambda: self._build_tab_jogadores  (tabs.tab("Jogadores"),    srv),
            "Plugins":      lambda: self._build_tab_plugins    (tabs.tab("Plugins"),      srv),
            "Console RCON": lambda: self._build_tab_rcon       (tabs.tab("Console RCON"), srv),
            "💬 Chat":      lambda: self._build_tab_chat       (tabs.tab("💬 Chat"),      srv),
            "Logs":         lambda: self._build_tab_logs       (tabs.tab("Logs"),         srv),
            "📋 Histórico": lambda: self._build_tab_historico  (tabs.tab("📋 Histórico"), srv),
            "Backup":       lambda: self._build_tab_backup     (tabs.tab("Backup"),       srv),
        }
        _built_tabs: set[str] = set()

        def _on_tab_change() -> None:
            name = tabs.get()
            if name not in _built_tabs:
                _built_tabs.add(name)
                _TAB_BUILDERS[name]()
                # Se o servidor não estiver parado, bloqueia os novos widgets
                inst_chk = self.server_manager.get_instance(srv.id)
                if inst_chk and inst_chk.status != SERVER_STATUS_STOPPED:
                    self.after(50, lambda: self._set_config_editable(srv.id, False))

        for tab_name in _TAB_BUILDERS:
            tabs.add(tab_name)
        tabs.configure(command=_on_tab_change)
        # Armazena o callback para que a barra de busca possa acioná-lo ao navegar via tabs.set()
        self._server_widgets[srv.id]["_on_tab_change"] = _on_tab_change

        # Constrói apenas a aba inicial (Geral) imediatamente
        _built_tabs.add("Geral")
        self._build_tab_general(tabs.tab("Geral"), srv)

        # Pré-constrói as demais abas progressivamente em idle time para eliminar
        # o freeze na primeira visita. Cada aba é construída com intervalo generoso
        # (1500ms) para não interferir com a interação do usuário.
        # "Jogo" é omitida aqui: ela usa chunked rendering (after(0)) e se
        # auto-constrói sem freeze quando visitada pela primeira vez.
        # "Spawns" e "Loot" são abas pesadas e raramente visitadas primeiro —
        # são construídas sob demanda (lazy) para não atrasar o pre-build.
        _prebuild_order = [
            "Avançado", "Console RCON", "Logs", "Admins",
            "Mods", "Jogadores", "Plugins",
            "💬 Chat", "📝 INI", "📋 Histórico", "Backup",
        ]

        def _idle_build(queue: list) -> None:
            if not queue:
                return
            name, *rest = queue
            if name not in _built_tabs:
                _built_tabs.add(name)
                _TAB_BUILDERS[name]()
                inst_chk = self.server_manager.get_instance(srv.id)
                if inst_chk and inst_chk.status != SERVER_STATUS_STOPPED:
                    self._set_config_editable(srv.id, False)
            self.after(1500, lambda: _idle_build(rest))

        # Inicia 1500ms depois para a aba Geral renderizar completamente primeiro
        self.after(1500, lambda: _idle_build(_prebuild_order))

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
        scroll.grid_columnconfigure(2, weight=1)  # espaçador — limita largura dos campos

        w = self._server_widgets[srv.id]

        def row(label: str, hint: str, var, row_n: int, is_pass: bool = False,
                browse: bool = False, combo: Optional[List] = None) -> None:
            self._register_config_item(srv.id, label.rstrip(": "), hint, "Geral")
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
        w["public_ip"]       = tk.StringVar(value=srv.public_ip)
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

        # ── IP Público ────────────────────────────────────────────────────────
        _lbl_ip = ctk.CTkFrame(scroll, fg_color="transparent")
        _lbl_ip.grid(row=10, column=0, padx=(16, 8), pady=(4, 0), sticky="w")
        ctk.CTkLabel(_lbl_ip, text="IP Público:", width=200, anchor="w",
                     text_color="gray65",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(_lbl_ip,
                     text="IP ou hostname que jogadores usam para conectar.\n"
                          "Clique em 'Detectar' para obter o IP público da máquina.",
                     width=200, anchor="w", text_color="gray40",
                     font=ctk.CTkFont(size=10), justify="left").pack(anchor="w", pady=(0, 2))

        _ip_fr = ctk.CTkFrame(scroll, fg_color="transparent")
        _ip_fr.grid(row=10, column=1, padx=(0, 16), pady=(4, 0), sticky="ew")
        _ip_fr.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(_ip_fr, textvariable=w["public_ip"], height=34,
                     placeholder_text="Ex: 189.123.45.67 ou meuservidor.com"
                     ).grid(row=0, column=0, sticky="ew")

        _ip_btn_fr = ctk.CTkFrame(_ip_fr, fg_color="transparent")
        _ip_btn_fr.grid(row=1, column=0, sticky="e", pady=(4, 4))
        _detect_btn = ctk.CTkButton(
            _ip_btn_fr, text="🔄 Detectar IP", width=120, height=26,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            font=ctk.CTkFont(size=11))
        _detect_btn.pack(side="left", padx=(0, 4))
        _copy_ip_btn = ctk.CTkButton(
            _ip_btn_fr, text="📋 Copiar", width=80, height=26,
            fg_color="#2a2a2a", hover_color="#404040",
            font=ctk.CTkFont(size=11))
        _copy_ip_btn.pack(side="left")

        def _detect_public_ip() -> None:
            _detect_btn.configure(state="disabled", text="⏳...")
            def _fetch() -> None:
                try:
                    with urllib.request.urlopen("https://api.ipify.org", timeout=5) as _r:
                        _ip = _r.read().decode().strip()
                    def _apply(_detected=_ip) -> None:
                        w["public_ip"].set(_detected)
                        _detect_btn.configure(state="normal", text="🔄 Detectar")
                    scroll.after(0, _apply)
                except Exception:
                    scroll.after(0, lambda: _detect_btn.configure(state="normal", text="🔄 Detectar"))
            threading.Thread(target=_fetch, daemon=True).start()

        _detect_btn.configure(command=_detect_public_ip)
        _copy_ip_btn.configure(command=lambda: (
            scroll.clipboard_clear(),
            scroll.clipboard_append(w["public_ip"].get()),
        ))

        self._section_lbl(scroll, 11, "🔒  Acesso")
        row("Senha do Servidor:",
            "Senha para entrar. Deixe vazio para servidor público.",
            w["server_password"], 12, is_pass=True)
        row("Senha de Admin:",
            "Usada para ativar cheats in-game (enablecheats). Mantenha secreta.",
            w["admin_password"], 13, is_pass=True)
        row("Senha RCON:",
            "Senha para conexão via console RCON. Geralmente igual à de admin.",
            w["rcon_password"], 14, is_pass=True)
        row("Máx. Jogadores:",
            "Limite de jogadores simultâneos no servidor.",
            w["max_players"], 15)

        self._section_lbl(scroll, 16, "⚙️  Opções de Inicialização")
        row("Evento Ativo:",
            "Selecione o evento oficial ou deixe vazio para nenhum.",
            w["active_event"], 17,
            combo=[v for _, v in _ARK_OFFICIAL_EVENTS])
        row("Auto-Save (min):",
            "Intervalo de salvamento automático em minutos. Padrão: 15.",
            w["auto_save"], 18)
        row("Argumentos Extras:",
            "Parâmetros adicionais de linha de comando. Ex: -ForceAllowCaveFlyers.",
            w["extra_args"], 19)

        self._section_lbl(scroll, 20, "📢  Mensagem do Dia (MOTD)")
        motd_card = ctk.CTkFrame(scroll, corner_radius=12, fg_color=_CARD_BG)
        motd_card.grid(row=21, column=0, padx=20, pady=(0, 14), sticky="ew")
        motd_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(motd_card, text="Mensagem:", width=190, anchor="nw",
                     text_color="gray60").grid(row=0, column=0, padx=16, pady=(12, 2), sticky="nw")
        w["motd"] = ctk.CTkTextbox(motd_card, height=320, corner_radius=6,
                                   fg_color="#1a1a2e", border_color="#3a3a5a",
                                   border_width=1, font=ctk.CTkFont(size=12),
                                   wrap="none")
        w["motd"].grid(row=0, column=1, padx=(0, 12), pady=(12, 4), sticky="ew")
        if srv.motd:
            w["motd"].insert("1.0", srv.motd)

        # ── Dicas de formatação ───────────────────────────────────────────────
        tips_frame = ctk.CTkFrame(motd_card, fg_color="#16162a", corner_radius=8)
        tips_frame.grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 8), sticky="ew")
        tips_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            tips_frame,
            text="💡  Dicas de Formatação",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#a0a0c0",
            anchor="w",
        ).grid(row=0, column=0, padx=10, pady=(8, 4), sticky="w")

        syntax_lbl = ctk.CTkLabel(
            tips_frame,
            text='Cor:  <RichColor Color="R, G, B, 1">seu texto</>     Nova linha:  \\n     Fechar cor:  </>',
            font=ctk.CTkFont(family="Courier New", size=11),
            text_color="#c8c8e8",
            anchor="w",
        )
        syntax_lbl.grid(row=1, column=0, padx=10, pady=(0, 6), sticky="w")

        # Linha de botões de inserção rápida de cor
        colors_frame = ctk.CTkFrame(tips_frame, fg_color="transparent")
        colors_frame.grid(row=2, column=0, padx=8, pady=(0, 8), sticky="w")

        ctk.CTkLabel(colors_frame, text="Inserir cor:",
                     font=ctk.CTkFont(size=11), text_color="gray50",
                     ).pack(side="left", padx=(2, 6))

        _COLOR_BTNS = [
            ("🟢 Verde",    "0, 1, 0, 1",       "#1a3a1a", "#2a5a2a"),
            ("🔴 Vermelho", "1, 0, 0, 1",       "#3a1a1a", "#5a2a2a"),
            ("🟡 Amarelo",  "1, 0.85, 0, 1",    "#3a3a10", "#5a5a18"),
            ("🔵 Azul",     "0, 0.6, 1, 1",     "#102040", "#183060"),
            ("🟠 Laranja",  "1, 0.5, 0, 1",     "#3a2010", "#5a3018"),
            ("⚪ Branco",   "1, 1, 1, 1",       "#2a2a2a", "#404040"),
        ]

        def _make_insert_color(tag_color: str) -> Callable:
            def _insert() -> None:
                tb = w["motd"]
                tag = f'<RichColor Color="{tag_color}">'
                try:
                    tb._textbox.insert("insert", tag)
                except Exception:
                    tb.insert("end", tag)
            return _insert

        for label, color_val, fg, hov in _COLOR_BTNS:
            ctk.CTkButton(
                colors_frame, text=label, height=26,
                font=ctk.CTkFont(size=11),
                fg_color=fg, hover_color=hov,
                command=_make_insert_color(color_val),
            ).pack(side="left", padx=3)

        # Botão fechar tag
        ctk.CTkButton(
            colors_frame, text="</> Fechar", height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#2a2a2a", hover_color="#404040",
            command=lambda: (
                w["motd"]._textbox.insert("insert", "</>")
                if hasattr(w["motd"], "_textbox") else
                w["motd"].insert("end", "</>")
            ),
        ).pack(side="left", padx=(8, 3))

        # Botão nova linha
        ctk.CTkButton(
            colors_frame, text="↵ \\n", height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#2a2a2a", hover_color="#404040",
            command=lambda: (
                w["motd"]._textbox.insert("insert", r"\n")
                if hasattr(w["motd"], "_textbox") else
                w["motd"].insert("end", r"\n")
            ),
        ).pack(side="left", padx=3)

        ctk.CTkLabel(motd_card, text="Duração (s):", width=190, anchor="w",
                     text_color="gray60").grid(row=2, column=0, padx=16, pady=(4, 12))
        w["motd_duration"] = tk.StringVar(value=str(srv.motd_duration))
        ctk.CTkEntry(motd_card, textvariable=w["motd_duration"],
                     height=34, width=80).grid(row=2, column=1, padx=(0, 12), pady=(4, 12), sticky="w")

        w["rcon_enabled"]       = tk.BooleanVar(value=srv.rcon_enabled)
        w["use_battleye"]       = tk.BooleanVar(value=srv.use_battleye)
        w["use_allcores"]       = tk.BooleanVar(value=srv.use_allcores)
        w["cpu_core_count"]     = tk.StringVar()
        w["force_respawn"]      = tk.BooleanVar(value=srv.force_respawn_dinos)
        w["whitelist_only"]     = tk.BooleanVar(value=srv.whitelist_only)
        w["auto_restart_crash"] = tk.BooleanVar(value=srv.auto_restart_on_crash)
        w["auto_update_start"]  = tk.BooleanVar(value=srv.auto_update_on_start)
        w["crossplay"]          = tk.BooleanVar(value=srv.crossplay)
        w["epic_only"]          = tk.BooleanVar(value=srv.epic_only)
        w["use_vivox"]          = tk.BooleanVar(value=srv.use_vivox)
        w["use_item_dupe_check"]= tk.BooleanVar(value=srv.use_item_dupe_check)
        w["prevent_spawn_anim"] = tk.BooleanVar(value=srv.prevent_spawn_animations)
        w["show_floating_dmg"]  = tk.BooleanVar(value=srv.show_floating_damage_text)

        self._section_lbl(scroll, 22, "🔧  Flags")
        checkboxes = [
            ("Habilitar RCON",
             "Ativa o console remoto. Necessário para usar a aba Console RCON.",
             w["rcon_enabled"]),
            ("Usar BattlEye (anti-cheat)",
             "Proteção anti-cheat oficial. Desative para servidores com mods incompatíveis.",
             w["use_battleye"]),
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
            ("Crossplay Epic + Steam",
             "Permite que jogadores da Epic e do Steam se conectem ao mesmo servidor.",
             w["crossplay"]),
            ("Apenas Epic Games",
             "Somente jogadores da Epic Game Store podem se conectar ao servidor.",
             w["epic_only"]),
            ("Vivox (chat de voz)",
             "Ativa o Vivox para comunicação de voz entre jogadores (somente Steam).",
             w["use_vivox"]),
            ("Proteção anti-dupe de itens",
             "Ativa verificação adicional contra duplicação. Pode impactar alguns mods.",
             w["use_item_dupe_check"]),
            ("Sem animação de spawn",
             "Desativa a animação de acordar ao (re)nascer no servidor.",
             w["prevent_spawn_anim"]),
            ("Dano flutuante (estilo RPG)",
             "Exibe texto de dano flutuante no estilo RPG ao atacar/ser atacado.",
             w["show_floating_dmg"]),
        ]
        for ci, (txt, hint_txt, var) in enumerate(checkboxes):
            self._register_config_item(srv.id, txt, hint_txt, "Geral")
            cb_fr = ctk.CTkFrame(scroll, fg_color="transparent")
            cb_fr.grid(row=23 + ci, column=0, columnspan=2, padx=16, pady=(4, 0), sticky="w")
            ctk.CTkCheckBox(cb_fr, text=txt, variable=var,
                            checkmark_color="white", fg_color=_GREEN_DARK,
                            hover_color=_GREEN_HOVER).pack(anchor="w")
            ctk.CTkLabel(cb_fr, text=hint_txt, text_color="gray40",
                         font=ctk.CTkFont(size=10), anchor="w").pack(
                anchor="w", padx=(26, 0), pady=(0, 2))

        self._save_btn_row(scroll, 40, srv.id)

        # ── Seletor de núcleos de CPU ────────────────────────────────────
        import os as _os
        _total_cpu = _os.cpu_count() or 8

        def _int_to_cpu_opt(n: int) -> str:
            if n == -1: return "Todos os núcleos"
            if n == 0:  return "Padrão (ARK decide)"
            return f"{n} núcleo{'s' if n > 1 else ''}"

        _cpu_opts = (
            ["Padrão (ARK decide)", "Todos os núcleos"]
            + [f"{n} núcleo{'s' if n > 1 else ''}" for n in range(1, _total_cpu + 1)]
        )
        w["cpu_core_count"].set(_int_to_cpu_opt(srv.cpu_core_count))

        self._register_config_item(srv.id, "Núcleos de CPU", "Restringe quantos núcleos lógicos o servidor pode usar.", "Geral")
        cpu_fr = ctk.CTkFrame(scroll, fg_color="transparent")
        cpu_fr.grid(row=35, column=0, columnspan=2, padx=16, pady=(4, 0), sticky="w")
        ctk.CTkLabel(cpu_fr, text="Núcleos de CPU:",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(cpu_fr,
                     text="Restringe quantos núcleos lógicos o processo do servidor pode usar.\n"
                          "\"Todos\" usa a flag -useallavailablecores. Número específico aplica afinidade de processo.",
                     text_color="gray40", font=ctk.CTkFont(size=10), anchor="w", justify="left").pack(
            anchor="w", padx=(0, 0), pady=(0, 4))
        ctk.CTkOptionMenu(
            cpu_fr, variable=w["cpu_core_count"],
            values=_cpu_opts, width=220,
        ).pack(anchor="w")

        # ── Seção Agendamentos ────────────────────────────────────────────────
        self._section_lbl(scroll, 36, "⏰  Agendamentos Automáticos")
        sched_outer = ctk.CTkFrame(scroll, corner_radius=12, fg_color=_CARD_BG)
        sched_outer.grid(row=37, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="ew")
        sched_outer.grid_columnconfigure(0, weight=1)

        _DAY_LABELS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        _ACTION_OPTS = ["restart", "stop", "update_restart"]
        _ACTION_LABELS = {"restart": "Reiniciar", "stop": "Desligar", "update_restart": "Atualizar + Reiniciar"}
        _WARN_OPTS = ["0", "5", "10", "15", "30", "60"]

        w["sched_task_rows"] = []
        sched_rows_frame = ctk.CTkFrame(sched_outer, fg_color="transparent")
        sched_rows_frame.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        sched_rows_frame.grid_columnconfigure(0, weight=1)

        def _add_sched_row(task: dict | None = None) -> None:
            ri = len(w["sched_task_rows"])
            row_fr = ctk.CTkFrame(sched_rows_frame, fg_color="#0e1018", corner_radius=6,
                                  border_width=1, border_color="#1e2840")
            row_fr.grid(row=ri, column=0, sticky="ew", pady=(0, 4))

            ev = tk.BooleanVar(value=task.get("enabled", True) if task else True)
            tv = tk.StringVar(value=task.get("time", "03:00") if task else "03:00")
            dv = [tk.BooleanVar(value=(d in (task.get("days", list(range(7))) if task else list(range(7)))))
                  for d in range(7)]
            av = tk.StringVar(value=task.get("action", "restart") if task else "restart")
            wv = tk.StringVar(value=str(task.get("warn_minutes", 15)) if task else "15")

            # linha superior: enable + time + aviso + ação
            top = ctk.CTkFrame(row_fr, fg_color="transparent")
            top.pack(fill="x", padx=8, pady=(6, 2))

            ctk.CTkCheckBox(top, text="", variable=ev, width=20,
                            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                            checkmark_color="white").pack(side="left", padx=(0, 6))
            ctk.CTkLabel(top, text="Hora:", text_color="gray60",
                         font=ctk.CTkFont(size=10)).pack(side="left")
            ctk.CTkEntry(top, textvariable=tv, width=60,
                         font=ctk.CTkFont(size=12), placeholder_text="HH:MM").pack(side="left", padx=(4, 12))

            ctk.CTkLabel(top, text="Ação:", text_color="gray60",
                         font=ctk.CTkFont(size=10)).pack(side="left")
            ctk.CTkOptionMenu(top, variable=av,
                              values=list(_ACTION_LABELS.values()),
                              width=170).pack(side="left", padx=(4, 12))

            ctk.CTkLabel(top, text="Aviso:", text_color="gray60",
                         font=ctk.CTkFont(size=10)).pack(side="left")
            ctk.CTkOptionMenu(top, variable=wv, values=_WARN_OPTS, width=60).pack(side="left", padx=(4, 4))
            ctk.CTkLabel(top, text="min", text_color="gray50",
                         font=ctk.CTkFont(size=10)).pack(side="left", padx=(0, 12))

            def _remove(fr=row_fr, rowdata=None):
                fr.destroy()
                if rowdata in w["sched_task_rows"]:
                    w["sched_task_rows"].remove(rowdata)
            rd: dict = {}
            ctk.CTkButton(top, text="✕", width=28, height=24,
                          fg_color="#3a1515", hover_color="#5a2020",
                          font=ctk.CTkFont(size=11),
                          command=lambda: _remove(row_fr, rd)).pack(side="right")

            # linha inferior: dias da semana
            bot = ctk.CTkFrame(row_fr, fg_color="transparent")
            bot.pack(fill="x", padx=8, pady=(0, 6))
            ctk.CTkLabel(bot, text="Dias:", text_color="gray60",
                         font=ctk.CTkFont(size=10)).pack(side="left", padx=(20, 4))
            for di, (dlbl, dvar) in enumerate(zip(_DAY_LABELS, dv)):
                ctk.CTkCheckBox(bot, text=dlbl, variable=dvar, width=52,
                                fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                                checkmark_color="white",
                                font=ctk.CTkFont(size=10)).pack(side="left", padx=2)

            rd.update({"frame": row_fr, "enabled": ev, "time": tv, "days": dv,
                       "action": av, "warn": wv, "_action_labels": _ACTION_LABELS})
            w["sched_task_rows"].append(rd)

        # Carregar tarefas existentes
        for t in srv.scheduled_tasks:
            _add_sched_row(t)

        ctk.CTkButton(
            sched_outer, text="+ Adicionar agendamento",
            fg_color="#1a2540", hover_color="#243060", text_color="#8eb0d0",
            height=30, font=ctk.CTkFont(size=11),
            command=_add_sched_row,
        ).grid(row=1, column=0, padx=16, pady=(0, 10), sticky="w")

        # ── Seção Instalação ─────────────────────────────────────────────────
        self._section_lbl(scroll, 38, "⬇️  Instalação / Atualização do Servidor")
        inst_card = ctk.CTkFrame(scroll, corner_radius=12, fg_color=_CARD_BG)
        inst_card.grid(row=39, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="ew")
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
        scroll.grid_columnconfigure(3, weight=1)  # espaçador — limita largura dos sliders

        w  = self._server_widgets[srv.id]
        gs = srv.game_settings

        def frow(label: str, hint: str, field: str, val: float, row_n: int,
                 frm: float = 0.0, to: float = 10.0) -> None:
            self._register_config_item(srv.id, label, hint, "Jogo")
            var = tk.DoubleVar(value=val)
            w[f"gs_{field}"] = var

            lbl_fr = ctk.CTkFrame(scroll, fg_color="transparent")
            lbl_fr.grid(row=row_n, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
            ctk.CTkLabel(lbl_fr, text=label, width=290, anchor="w",
                         text_color="gray65",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
            if hint:
                ctk.CTkLabel(lbl_fr, text=hint, width=290, anchor="w",
                             text_color="gray40",
                             font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))

            entry_var = tk.StringVar(value=f"{val:.2f}")
            entry = ctk.CTkEntry(scroll, textvariable=entry_var, width=72, height=28,
                                 justify="right", text_color=_GREEN,
                                 font=ctk.CTkFont(size=12, weight="bold"))
            entry.grid(row=row_n, column=2, padx=(4, 14), pady=4)

            slider = ctk.CTkSlider(
                scroll, from_=frm, to=to, variable=var,  # type: ignore[arg-type]
                command=lambda v, ev=entry_var: ev.set(f"{float(v):.2f}"),
            )
            slider.grid(row=row_n, column=1, padx=4, pady=4, sticky="ew")

            def _sync_entry(*_, _v=var, _ev=entry_var):
                _ev.set(f"{_v.get():.2f}")
            var.trace_add("write", _sync_entry)

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
            self._register_config_item(srv.id, label, hint, "Jogo")
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
            self._register_config_item(srv.id, label, "", "Jogo")
            w[f"gs_{field}"] = tk.BooleanVar(value=val)
            ctk.CTkCheckBox(scroll, text=label, variable=w[f"gs_{field}"],
                            checkmark_color="white", fg_color=_GREEN_DARK,
                            hover_color=_GREEN_HOVER).grid(
                row=row_n, column=0, columnspan=3, padx=16, pady=4, sticky="w")

        def _level_cap_row(label: str, hint: str, field: str, val: int, row_n: int) -> None:
            from .ark_ini import _level_to_xp as _l2xp
            self._register_config_item(srv.id, label, hint, "Jogo")
            w[f"gs_{field}"] = tk.StringVar(value=str(val))
            lbl_fr = ctk.CTkFrame(scroll, fg_color="transparent")
            lbl_fr.grid(row=row_n, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
            ctk.CTkLabel(lbl_fr, text=label, width=290, anchor="w",
                         text_color="gray65",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
            ctk.CTkLabel(lbl_fr, text=hint, width=290, anchor="w",
                         text_color="gray40",
                         font=ctk.CTkFont(size=10), justify="left",
                         wraplength=270).pack(anchor="w", pady=(0, 2))
            right_fr = ctk.CTkFrame(scroll, fg_color="transparent")
            right_fr.grid(row=row_n, column=1, padx=4, pady=4, sticky="w")
            ctk.CTkEntry(right_fr, textvariable=w[f"gs_{field}"],
                         width=80, height=28).pack(side="left")
            xp_lbl = ctk.CTkLabel(right_fr, text="", text_color="gray45",
                                  font=ctk.CTkFont(size=10))
            xp_lbl.pack(side="left", padx=(6, 0))

            def _update_xp_preview(*_):
                try:
                    lvl = int(w[f"gs_{field}"].get())
                    xp_lbl.configure(text="(padrão ARK)" if lvl <= 0 else f"→ {_l2xp(lvl):,} XP")
                except (ValueError, TypeError):
                    xp_lbl.configure(text="")

            w[f"gs_{field}"].trace_add("write", _update_xp_preview)
            _update_xp_preview()

        # ── Coleta de tasks com row pré-calculado ─────────────────────────────
        # Em vez de criar todos os ~350 widgets de uma vez (freeze de ~500ms),
        # as tasks são despachadas em lotes de 6 via after(0), cedendo o
        # controle ao event loop entre cada lote.
        _tasks: list = []
        r = 0

        def _s(text: str) -> None:
            nonlocal r
            _tasks.append(("s", r, text)); r += 1

        def _f(label, hint, field, val, frm=0.0, to=10.0) -> None:
            nonlocal r
            _tasks.append(("f", r, label, hint, field, val, frm, to)); r += 1

        def _i(label, hint, field, val) -> None:
            nonlocal r
            _tasks.append(("i", r, label, hint, field, val)); r += 1

        def _b(label, field, val) -> None:
            nonlocal r
            _tasks.append(("b", r, label, field, val)); r += 1

        def _calc() -> None:
            nonlocal r
            _tasks.append(("calc", r)); r += 1

        def _lcap(label, hint, field, val) -> None:
            nonlocal r
            _tasks.append(("lcap", r, label, hint, field, val)); r += 1

        def _save() -> None:
            _tasks.append(("save", r + 1))

        def _plsm() -> None:
            nonlocal r
            _tasks.append(("plsm", r))
            r += 1

        # ── Definição das rows ────────────────────────────────────────────────
        _s("⚙️  Dificuldade")
        _f("Nível de Dificuldade",
           "Padrão: 0.20 — Aumentar eleva o nível máximo dos dinos selvagens.",
           "difficulty_offset", gs.difficulty_offset, 0, 1)
        _f("Dificuldade Máxima (Override)",
           "Ex: 5.0 = dinos até nível 150. Aumente para dinos mais difíceis.",
           "override_official_difficulty", gs.override_official_difficulty, 1, 10)

        _s("📈  XP")
        _f("Multiplicador de XP Geral",
           "Multiplica todo o XP ganho. Aumente para progredir mais rápido.",
           "xp_multiplier", gs.xp_multiplier)
        _f("XP por Abate",
           "Multiplica o XP ganho ao matar criaturas.",
           "kill_xp_multiplier", gs.kill_xp_multiplier)
        _f("XP por Coleta",
           "Multiplica o XP ganho ao coletar recursos.",
           "harvest_xp_multiplier", gs.harvest_xp_multiplier)
        _f("XP por Craft",
           "Multiplica o XP ganho ao fabricar itens.",
           "craft_xp_multiplier", gs.craft_xp_multiplier)
        _f("XP Genérico",
           "Multiplica o XP de fontes diversas.",
           "generic_xp_multiplier", gs.generic_xp_multiplier)
        _f("XP Especial",
           "Multiplica o XP de eventos e fontes especiais.",
           "special_xp_multiplier", gs.special_xp_multiplier)

        _s("👤  Jogador")
        _f("Dano do Jogador",
           "Aumenta o dano causado pelo jogador. Ex: 2.0 = dano dobrado.",
           "player_damage_multiplier", gs.player_damage_multiplier)
        _f("Resistência do Jogador",
           "Reduz o dano recebido. Menor = mais resistente ao dano.",
           "player_resistance_multiplier", gs.player_resistance_multiplier)
        _f("Consumo de Água",
           "Taxa de consumo de água. Menor = seca mais devagar.",
           "player_character_water_drain_multiplier",
           gs.player_character_water_drain_multiplier)
        _f("Consumo de Comida",
           "Taxa de consumo de comida. Menor = fica com fome mais devagar.",
           "player_character_food_drain_multiplier",
           gs.player_character_food_drain_multiplier)
        _f("Regeneração de Vida",
           "Velocidade de recuperação de HP. Maior = recupera mais rápido.",
           "player_character_health_recovery_multiplier",
           gs.player_character_health_recovery_multiplier)
        _f("Consumo de Stamina",
           "Taxa de consumo de stamina. Menor = cansa mais devagar.",
           "player_character_stamina_drain_multiplier",
           gs.player_character_stamina_drain_multiplier)

        _s("🦖  Dinos")
        _f("Dano dos Dinos",
           "Aumenta o dano causado pelos dinos selvagens.",
           "dino_damage_multiplier", gs.dino_damage_multiplier)
        _f("Resistência dos Dinos",
           "Reduz o dano recebido pelos dinos. Menor = dinos mais resistentes.",
           "dino_resistance_multiplier", gs.dino_resistance_multiplier)
        _f("Regeneração dos Dinos",
           "Velocidade de recuperação de HP dos dinos.",
           "dino_character_health_recovery_multiplier",
           gs.dino_character_health_recovery_multiplier)
        _f("Consumo de Comida dos Dinos",
           "Taxa de consumo de comida dos dinos. Menor = comem mais devagar.",
           "dino_character_food_drain_multiplier",
           gs.dino_character_food_drain_multiplier)
        _f("Quantidade de Dinos no Mapa",
           "Multiplica a quantidade de dinos. Ex: 2.0 = dobro de dinos selvagens.",
           "dino_count_multiplier", gs.dino_count_multiplier)
        _i("Máx. Dinos Domesticados",
           "Limite total de dinos domesticados no servidor.",
           "max_tamed_dinos", gs.max_tamed_dinos)

        _s("📊  Stats por Nível")
        _plsm()

        _s("🥚  Criação / Imprinting")
        _calc()
        _f("Velocidade de Domesticação",
           "Maior = domestica mais rápido. Ex: 3.0 = 3× mais rápido.",
           "taming_speed_multiplier", gs.taming_speed_multiplier)
        _f("Intervalo de Acasalamento",
           "Menor = pode acasalar com mais frequência.",
           "mating_interval_multiplier", gs.mating_interval_multiplier)
        _f("Velocidade de Chocagem",
           "Maior = ovos chocam mais rápido.",
           "egg_hatch_speed_multiplier", gs.egg_hatch_speed_multiplier)
        _f("Intervalo de Postura de Ovos",
           "Menor = dinos põem ovos com mais frequência.",
           "lay_egg_interval_multiplier", gs.lay_egg_interval_multiplier)
        _f("Velocidade de Crescimento do Filhote",
           "Maior = filhotes crescem mais rápido.",
           "baby_mature_speed_multiplier", gs.baby_mature_speed_multiplier, 0, 100)
        _f("Velocidade de Nascimento do Filhote",
           "Maior = filhotes vivíparos nascem mais rápido.",
           "baby_hatch_speed_multiplier", gs.baby_hatch_speed_multiplier, 0, 100)
        _f("Consumo de Comida do Filhote",
           "Menor = filhotes comem menos (mais fácil de criar).",
           "baby_food_consumption_speed_multiplier",
           gs.baby_food_consumption_speed_multiplier)
        _f("Intervalo de Carinho (Imprint)",
           "Menor = menos tempo entre os pedidos de carinho do filhote.",
           "baby_cuddle_interval_multiplier", gs.baby_cuddle_interval_multiplier)
        _f("Tolerância de Atraso do Imprint",
           "Maior = mais tempo para responder ao pedido de carinho sem perder %.",
           "baby_cuddle_grace_period_multiplier",
           gs.baby_cuddle_grace_period_multiplier)
        _f("Bônus de Stats por Imprint",
           "Maior = mais bônus de stats ao completar 100% de imprint.",
           "baby_imprinting_stat_scale_multiplier",
           gs.baby_imprinting_stat_scale_multiplier)

        _s("🌾  Coleta / Recursos")
        _f("Quantidade de Coleta",
           "Mais recursos por coleta. Ex: 3.0 = 3× mais recursos.",
           "harvest_amount_multiplier", gs.harvest_amount_multiplier)
        _f("Durabilidade dos Recursos",
           "Maior = rochas/árvores duram mais antes de destruir.",
           "harvest_health_multiplier", gs.harvest_health_multiplier)
        _f("Reaparecimento de Recursos",
           "Menor = recursos reaparecem mais rápido no mapa.",
           "resource_respawn_period_multiplier",
           gs.resource_respawn_period_multiplier)
        _f("Velocidade de Crescimento das Plantas",
           "Maior = plantas nas estufas crescem mais rápido.",
           "crop_growth_speed_multiplier", gs.crop_growth_speed_multiplier)
        _f("Apodrecimento das Plantas",
           "Menor = plantas demoram mais para apodrecer.",
           "crop_decay_speed_multiplier", gs.crop_decay_speed_multiplier)
        _f("Tamanho de Stack",
           "Multiplica o limite de empilhamento. Ex: 2.0 = stacks dobrados.",
           "item_stack_size_multiplier", gs.item_stack_size_multiplier)
        _f("Tempo de Estragamento",
           "Maior = comida demora mais para estragar.",
           "spoiling_time_multiplier", gs.spoiling_time_multiplier)
        _f("Tempo de Decomposição de Itens",
           "Maior = itens largados no chão demoram mais para sumir.",
           "item_decomposition_time_multiplier",
           gs.item_decomposition_time_multiplier)
        _f("Qualidade de Loot de Pesca",
           "Maior = itens de melhor qualidade ao pescar.",
           "fishing_loot_quality_multiplier", gs.fishing_loot_quality_multiplier)

        _s("🏗️  Estruturas")
        _f("Dano às Estruturas",
           "Aumenta o dano causado às estruturas por jogadores/dinos.",
           "structure_damage_multiplier", gs.structure_damage_multiplier)
        _f("Resistência das Estruturas",
           "Menor = estruturas mais resistentes (recebem menos dano).",
           "structure_resistance_multiplier", gs.structure_resistance_multiplier)
        _i("Cooldown de Reparo (s)",
           "Segundos de espera para reparar após receber dano.",
           "structure_damage_repair_cooldown",
           gs.structure_damage_repair_cooldown)
        _f("Decaimento de Estruturas (PvE)",
           "Maior = estruturas sem dono demoram mais para decair.",
           "pve_structure_decay_period_multiplier",
           gs.pve_structure_decay_period_multiplier)
        _f("Estruturas em Plataformas",
           "Multiplica o limite de estruturas em platform saddles.",
           "per_platform_max_structures_multiplier",
           gs.per_platform_max_structures_multiplier)
        _f("Área de Build em Saddles",
           "Multiplica a área construível ao redor de platform saddles.",
           "platform_saddle_build_area_bounds_multiplier",
           gs.platform_saddle_build_area_bounds_multiplier)

        _s("🏆  Tribal / Misc")
        _i("Tamanho Máximo da Tribo",
           "Número máximo de membros por tribo.",
           "max_tribe_size", gs.max_tribe_size)
        _f("Tempo para Expulsar AFK (s)",
           "Segundos até expulsar jogadores inativos. 0 = desativado.",
           "kick_idle_players_period", gs.kick_idle_players_period, 0, 7200)

        _s("🔢  Teto de Níveis")
        _lcap("Nível Máximo do Jogador",
              "Nível final do jogador, incluindo os desbloqueados por ascensões."
              " 0 = padrão ARK (105 base + ascensões).",
              "player_level_cap", gs.player_level_cap)
        _lcap("Nível Máximo do Dino",
              "Nível máximo que dinos podem atingir ao acumular XP."
              " 0 = padrão ARK.",
              "dino_level_cap", gs.dino_level_cap)

        _s("🎮  Opções do Servidor")
        _b("PvP Ativado",                              "server_pvp",                  gs.server_pvp)
        _b("Modo Hardcore (morte permanente)",         "server_hardcore",             gs.server_hardcore)
        _b("Dinos Voadores Carregam Jogadores (PvE)",  "allow_flyer_carry_pve",       gs.allow_flyer_carry_pve)
        _b("Terceira Pessoa Permitida",                "allow_third_person_player",   gs.allow_third_person_player)
        _b("Mostrar Localização no Mapa",              "show_map_player_location",    gs.show_map_player_location)
        _b("Desativar Decaimento de Estruturas (PvE)", "disable_structure_decay_pve", gs.disable_structure_decay_pve)
        _b("Desativar Decaimento de Dinos (PvE)",      "disable_dino_decay_pve",      gs.disable_dino_decay_pve)
        _b("Proteção Offline (ORP)",                   "prevent_offline_pvp",         gs.prevent_offline_pvp)
        _b("Bloquear Downloads de Tributos",           "no_tribute_downloads",        gs.no_tribute_downloads)
        _b("Notificar quando Jogador Entrar",          "always_notify_player_joined", gs.always_notify_player_joined)
        _b("Notificar quando Jogador Sair",            "always_notify_player_left",   gs.always_notify_player_left)
        _save()

        # ── Despacho em chunks via after(0) ───────────────────────────────────
        # Lotes de 6 tasks — cada after(0) cede o controle ao event loop antes
        # do próximo lote, eliminando o freeze de ~500ms que 44 CTkSliders causavam.
        _CHUNK = 6

        # ── Nomes e descrições dos stats (índices 0-11) ───────────────────────
        _PLSM_STATS = [
            (0,  "❤️",  "Vida",               "HP máx. por ponto. Padrão ARK ≈ +10 HP base por nível."),
            (1,  "⚡",  "Stamina",            "Stamina por ponto. Padrão ≈ +10 stamina por nível."),
            (2,  "💤",  "Torpor",             "Resistência ao torpor. Principalmente relevante para dinos selvagens."),
            (3,  "🫧",  "Oxigênio",           "Oxigênio por ponto. Relevante para dinos aquáticos."),
            (4,  "🍖",  "Comida",             "Capacidade de comida por ponto."),
            (5,  "💧",  "Água",               "Capacidade de água. Relevante principalmente para jogadores."),
            (6,  "🌡️", "Temperatura",        "Resistência à temperatura (raramente ajustado)."),
            (7,  "⚖️", "Peso",               "Carga por ponto. Padrão ≈ +10 por nível."),
            (8,  "⚔️", "Dano Corpo a Corpo", "Dano melee por ponto. Padrão ≈ +2% por nível."),
            (9,  "🏃",  "Velocidade",         "Velocidade de movimento por ponto. Padrão ≈ +1% por nível."),
            (10, "🛡️", "Fortitude",          "Resistência ao frio/calor. Relevante para jogadores."),
            (11, "🔨",  "Craft Skill",        "Habilidade de fabricação. Melhora receitas customizadas."),
        ]

        def _build_plsm_table(rn: int) -> None:
            """Constrói a tabela PerLevelStatsMultiplier (Dino Domado / Selvagem / Jogador)."""
            outer = ctk.CTkFrame(scroll, fg_color=_CARD_BG, corner_radius=10)
            outer.grid(row=rn, column=0, columnspan=4, padx=12, pady=(0, 8), sticky="ew")
            outer.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                outer,
                text="Multiplica o ganho de cada stat a cada ponto investido ao subir nível."
                     "  1.0 = padrão ARK  •  2.0 = dobro do ganho  •  0.0 = desativa o stat.",
                text_color="gray50", font=ctk.CTkFont(size=10), justify="left",
            ).grid(row=0, column=0, padx=14, pady=(10, 4), sticky="w")

            tbl = ctk.CTkFrame(outer, fg_color="transparent")
            tbl.grid(row=1, column=0, padx=10, pady=(0, 12), sticky="ew")
            tbl.grid_columnconfigure(0, weight=1)
            tbl.grid_columnconfigure(1, minsize=82)
            tbl.grid_columnconfigure(2, minsize=82)
            tbl.grid_columnconfigure(3, minsize=82)
            tbl.grid_columnconfigure(4, minsize=82)
            tbl.grid_columnconfigure(5, minsize=82)

            # Cabeçalho
            ctk.CTkLabel(tbl, text="Stat", anchor="w",
                         text_color="gray55",
                         font=ctk.CTkFont(size=10, weight="bold")).grid(
                row=0, column=0, padx=(8, 4), pady=(0, 2), sticky="w")
            for col_i, (col_txt, col_color) in enumerate([
                ("Domado (IdM)",       "#4fc3f7"),
                ("Dom. Bônus (TaM)",  "#ce93d8"),
                ("Dom. Afinid. (TmM)", "#f48fb1"),
                ("Selvagem (IwM)",     "#a5d6a7"),
                ("Jogador",            "#ffcc80"),
            ], start=1):
                ctk.CTkLabel(tbl, text=col_txt, anchor="center",
                             text_color=col_color,
                             font=ctk.CTkFont(size=10, weight="bold")).grid(
                    row=0, column=col_i, padx=4, pady=(0, 2))

            ctk.CTkFrame(tbl, height=1, fg_color="gray30").grid(
                row=1, column=0, columnspan=6, sticky="ew", padx=4, pady=(0, 2))

            # Linhas de stat
            for i, (stat_idx, emoji, stat_name, stat_hint) in enumerate(_PLSM_STATS):
                tr = stat_idx + 2
                self._register_config_item(
                    srv.id, f"{stat_name} — Stats/Nível", stat_hint, "Jogo")

                stripe = "#1c1c2e" if i % 2 == 0 else "#13131c"
                row_fr = ctk.CTkFrame(tbl, fg_color=stripe, corner_radius=4)
                row_fr.grid(row=tr, column=0, columnspan=6, sticky="ew", padx=2, pady=1)
                row_fr.grid_columnconfigure(0, weight=1)
                row_fr.grid_columnconfigure(1, minsize=82)
                row_fr.grid_columnconfigure(2, minsize=82)
                row_fr.grid_columnconfigure(3, minsize=82)
                row_fr.grid_columnconfigure(4, minsize=82)
                row_fr.grid_columnconfigure(5, minsize=82)

                ctk.CTkLabel(
                    row_fr,
                    text=f"{emoji}  {stat_name}",
                    text_color="gray65",
                    font=ctk.CTkFont(size=11),
                    anchor="w", width=188,
                ).grid(row=0, column=0, padx=(8, 4), pady=3, sticky="w")

                for col_i, (group, grp_attr) in enumerate([
                    ("tamed",          "per_level_stats_mult_dino_tamed"),
                    ("tamed_add",      "per_level_stats_mult_dino_tamed_add"),
                    ("tamed_affinity", "per_level_stats_mult_dino_tamed_affinity"),
                    ("wild",           "per_level_stats_mult_dino_wild"),
                    ("player",         "per_level_stats_mult_player"),
                ], start=1):
                    val = getattr(gs, grp_attr)[stat_idx]
                    var = tk.StringVar(value=f"{val:.4g}")
                    w[f"gs_plsm_{group}_{stat_idx}"] = var
                    ent = ctk.CTkEntry(
                        row_fr, textvariable=var,
                        width=82, height=26,
                        justify="center",
                        font=ctk.CTkFont(size=11),
                        fg_color="#0a0a14",
                    )
                    ent.grid(row=0, column=col_i, padx=4, pady=3)

                    def _make_commit(v=var):
                        def _commit(e=None):
                            try:
                                fv = max(0.0, float(v.get().replace(",", ".")))
                                v.set(f"{fv:.4g}")
                            except ValueError:
                                v.set("1")
                        return _commit
                    _cb = _make_commit()
                    ent.bind("<FocusOut>", _cb)
                    ent.bind("<Return>",   _cb)

        def _dispatch_task(task: tuple) -> None:
            kind = task[0]
            if kind == "s":
                _, rn, text = task
                self._section_lbl(scroll, rn, text)
            elif kind == "f":
                _, rn, lbl, hint, field, val, frm, to = task
                frow(lbl, hint, field, val, rn, frm, to)
            elif kind == "i":
                _, rn, lbl, hint, field, val = task
                irow(lbl, hint, field, val, rn)
            elif kind == "b":
                _, rn, lbl, field, val = task
                brow(lbl, field, val, rn)
            elif kind == "lcap":
                _, rn, lbl, hint, field, val = task
                _level_cap_row(lbl, hint, field, val, rn)
            elif kind == "calc":
                _, rn = task
                ctk.CTkButton(
                    scroll,
                    text="🧮  Calculadora de Breeding",
                    width=230,
                    fg_color="#2d4a6f",
                    hover_color="#1b2d45",
                    command=lambda _gs=gs: open_breeding_calculator(
                        self, _gs,
                        self._server_widgets.get(srv.id, {}),
                        lambda: self._save_server_config(srv.id, silent=True, force=True),
                    ),
                ).grid(row=rn, column=0, columnspan=3, sticky="e", padx=16, pady=(2, 8))
            elif kind == "plsm":
                _, rn = task
                _build_plsm_table(rn)
            elif kind == "save":
                _, rn = task
                self._save_btn_row(scroll, rn, srv.id)

        def _exec_chunk(idx: int) -> None:
            for task in _tasks[idx: idx + _CHUNK]:
                _dispatch_task(task)
            nxt = idx + _CHUNK
            if nxt < len(_tasks):
                self.after(0, lambda i=nxt: _exec_chunk(i))
            else:
                # Último lote concluído — aplica lock se servidor estiver rodando
                inst_chk = self.server_manager.get_instance(srv.id)
                if inst_chk and inst_chk.status != SERVER_STATUS_STOPPED:
                    self._set_config_editable(srv.id, False)

        self.after(0, lambda: _exec_chunk(0))

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Avançado / Cross-ARK
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_advanced(self, parent, srv: ServerConfig) -> None:
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=4)
        scroll.grid_columnconfigure(1, weight=1)
        scroll.grid_columnconfigure(2, weight=1)  # espaçador — limita largura dos campos

        w   = self._server_widgets[srv.id]
        adv = srv.advanced_settings
        cl  = srv.cluster

        def brow(label: str, hint: str, field: str, val: bool, row_n: int, prefix: str = "adv_") -> None:
            self._register_config_item(srv.id, label, hint, "Avançado")
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
            self._register_config_item(srv.id, label, hint, "Avançado")
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

        # ── Seletor de Perfil de Cluster ──────────────────────────────────────
        profiles = self.config_manager.clusters
        profile_names = ["— Manual (por servidor) —"] + [p.name for p in profiles]
        profile_ids   = [""] + [p.id for p in profiles]
        current_pid   = srv.cluster_profile_id
        current_idx   = profile_ids.index(current_pid) if current_pid in profile_ids else 0

        w["cl_profile_id_var"] = tk.StringVar(value=profile_ids[current_idx])

        prof_fr = ctk.CTkFrame(scroll, fg_color="transparent")
        prof_fr.grid(row=r, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
        ctk.CTkLabel(prof_fr, text="Perfil de Cluster:", width=310, anchor="w",
                     text_color="gray65",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(prof_fr,
                     text="Selecione um perfil global ou configure manualmente abaixo.",
                     width=310, anchor="w", text_color="gray40",
                     font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))

        def _on_profile_select(choice: str) -> None:
            idx = profile_names.index(choice) if choice in profile_names else 0
            pid = profile_ids[idx]
            w["cl_profile_id_var"].set(pid)
            # Habilita/desabilita campos manuais conforme seleção
            state = "disabled" if pid else "normal"
            for widget_key in ("_cl_id_entry", "_cl_dir_entry", "_cl_dir_btn"):
                wgt = w.get(widget_key)
                if wgt:
                    try:
                        wgt.configure(state=state)
                    except Exception:
                        pass
            if pid:
                prof = self.config_manager.get_cluster(pid)
                if prof:
                    w.get("cl_cluster_id",  tk.StringVar()).set(prof.cluster_id)
                    w.get("cl_cluster_dir", tk.StringVar()).set(prof.cluster_dir)
            _cl_enabled_state = "disabled" if pid else "normal"
            cl_en_cb = w.get("_cl_enabled_cb")
            if cl_en_cb:
                try:
                    cl_en_cb.configure(state=_cl_enabled_state)
                except Exception:
                    pass

        prof_combo = ctk.CTkOptionMenu(
            scroll, values=profile_names, width=280, height=30,
            fg_color=_CARD_BG, button_color=_BLUE, button_hover_color=_BLUE_HOVER,
            command=_on_profile_select,
        )
        prof_combo.set(profile_names[current_idx])
        prof_combo.grid(row=r, column=1, padx=4, pady=4, sticky="w")
        r += 1

        # ─────────────────────────────────────────────────────────────────────
        _manual_locked = bool(current_pid)   # campos bloqueados quando perfil ativo

        _cl_enabled_cb_var = tk.BooleanVar(value=cl.enabled)
        w["cl_enabled"] = _cl_enabled_cb_var
        cb_fr2 = ctk.CTkFrame(scroll, fg_color="transparent")
        cb_fr2.grid(row=r, column=0, columnspan=2, padx=16, pady=(4, 0), sticky="w")
        _cl_en_cb = ctk.CTkCheckBox(
            cb_fr2, text="Habilitar Cluster (Cross-ARK)",
            variable=_cl_enabled_cb_var,
            checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            state="disabled" if _manual_locked else "normal",
        )
        _cl_en_cb.pack(anchor="w")
        ctk.CTkLabel(cb_fr2,
                     text="Permite que múltiplos servidores compartilhem tribos, dinos e itens entre si.",
                     text_color="gray40", font=ctk.CTkFont(size=10), anchor="w").pack(
            anchor="w", padx=(26, 0), pady=(0, 2))
        w["_cl_enabled_cb"] = _cl_en_cb
        r += 1

        w["cl_cluster_id"]  = tk.StringVar(value=cl.cluster_id)
        w["cl_cluster_dir"] = tk.StringVar(value=cl.cluster_dir_override)
        w["cl_alt_save_dir"] = tk.StringVar(value=srv.alt_save_directory_name)

        cid_fr = ctk.CTkFrame(scroll, fg_color="transparent")
        cid_fr.grid(row=r, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
        ctk.CTkLabel(cid_fr, text="ID do Cluster:", width=310, anchor="w",
                     text_color="gray65",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(cid_fr, text="Identificador único do cluster. Todos os servidores do mesmo cluster devem usar o mesmo ID.",
                     width=310, anchor="w", text_color="gray40",
                     font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))
        _cl_id_entry = ctk.CTkEntry(scroll, textvariable=w["cl_cluster_id"], height=30,
                                    placeholder_text="Ex: MeuCluster123",
                                    state="disabled" if _manual_locked else "normal")
        _cl_id_entry.grid(row=r, column=1, padx=4, pady=4, sticky="ew")
        w["_cl_id_entry"] = _cl_id_entry
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
        _cl_dir_entry = ctk.CTkEntry(dir_fr, textvariable=w["cl_cluster_dir"], height=30,
                                     state="disabled" if _manual_locked else "normal")
        _cl_dir_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        _cl_dir_btn = ctk.CTkButton(dir_fr, text="📁", width=34, height=30,
                                    state="disabled" if _manual_locked else "normal",
                                    command=lambda: self._browse_dir(w["cl_cluster_dir"]))
        _cl_dir_btn.grid(row=0, column=1)
        w["_cl_dir_entry"] = _cl_dir_entry
        w["_cl_dir_btn"]   = _cl_dir_btn
        r += 1

        asdir_fr = ctk.CTkFrame(scroll, fg_color="transparent")
        asdir_fr.grid(row=r, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
        ctk.CTkLabel(asdir_fr, text="Nome da Pasta de Saves:", width=310, anchor="w",
                     text_color="gray65",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(asdir_fr,
                     text="Pasta única de saves para este servidor (?AltSaveDirectoryName). "
                          "Obrigatório ao rodar múltiplos servidores na mesma máquina.",
                     width=310, anchor="w", text_color="gray40",
                     font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))
        _cl_asdir_entry = ctk.CTkEntry(scroll, textvariable=w["cl_alt_save_dir"], height=30,
                                       placeholder_text="Ex: Save1",
                                       state="disabled" if _manual_locked else "normal")
        _cl_asdir_entry.grid(row=r, column=1, padx=4, pady=4, sticky="ew")
        w["_cl_asdir_entry"] = _cl_asdir_entry
        r += 1
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

        # ── Config Dinâmica (DynamicConfigURL) ───────────────────────────────
        self._section_lbl(scroll, r, "⚡  Config Dinâmica (sem reinício)")
        r += 1

        dyn_card = ctk.CTkFrame(scroll, corner_radius=10, fg_color=_CARD_BG)
        dyn_card.grid(row=r, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="ew")
        dyn_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            dyn_card,
            text="O ARK suporta -DynamicConfigURL: o servidor busca um arquivo INI periodicamente (~2 min)\n"
                 "e aplica multiplicadores de rate, breeding etc. sem reiniciar. Funciona apenas com\n"
                 "servidores iniciados pelo app após ativar esta opção.",
            text_color="gray55", font=ctk.CTkFont(size=10), justify="left",
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(10, 6), sticky="w")

        self._register_config_item(srv.id,
            "Config Dinâmica", "Aplica mudanças de rate sem reiniciar via DynamicConfigURL.", "Avançado")
        w["dynamic_config_enabled"] = tk.BooleanVar(value=srv.dynamic_config_enabled)
        dyn_cb_fr = ctk.CTkFrame(dyn_card, fg_color="transparent")
        dyn_cb_fr.grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 4), sticky="w")
        ctk.CTkCheckBox(
            dyn_cb_fr, text="Ativar Config Dinâmica",
            variable=w["dynamic_config_enabled"],
            checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        ).pack(side="left")

        dyn_url_var = tk.StringVar(value=(
            self._dynamic_config_server.get_url(srv.id)
            if srv.dynamic_config_enabled else "—"
        ))
        w["_dyn_url_var"] = dyn_url_var
        ctk.CTkLabel(dyn_cb_fr, textvariable=dyn_url_var,
                     text_color="gray45", font=ctk.CTkFont(size=10)).pack(
            side="left", padx=(14, 0))

        dyn_btn_row = ctk.CTkFrame(dyn_card, fg_color="transparent")
        dyn_btn_row.grid(row=2, column=0, columnspan=2, padx=12, pady=(4, 12), sticky="w")

        ctk.CTkButton(
            dyn_btn_row,
            text="⚡  Aplicar Sem Reiniciar",
            height=34, width=200,
            fg_color="#2a6a9a", hover_color="#3a7aaa",
            command=lambda sid=srv.id: self._push_dynamic_config(sid),
        ).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            dyn_btn_row,
            text="Atualiza o conteúdo servido — ARK aplicará na próxima poll.",
            text_color="gray50", font=ctk.CTkFont(size=10),
        ).pack(side="left")
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

        ctk.CTkButton(
            btn_row_ini,
            text="📋  Clonar Configurações",
            height=36, width=200,
            fg_color="#3a5a2a", hover_color="#4a6a3a",
            command=lambda sid=srv.id: self._open_clone_config_dialog(sid),
        ).pack(side="left", padx=(10, 0))
        r += 1

        self._save_btn_row(scroll, r + 2, srv.id)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Spawns de Dinos
    # ══════════════════════════════════════════════════════════════════════════

    # Lista de containers de spawn conhecidos (Island + outros mapas populares)
    _SPAWN_CONTAINERS = [
        # Island
        "DinoSpawnEntriesBeach_C",
        "DinoSpawnEntriesGrassland_C",
        "DinoSpawnEntriesForest_C",
        "DinoSpawnEntriesJungle_C",
        "DinoSpawnEntriesMountain_C",
        "DinoSpawnEntriesSnow_C",
        "DinoSpawnEntriesSwamp_C",
        "DinoSpawnEntriesOcean_C",
        "DinoSpawnEntriesUnderground_C",
        # Scorched Earth
        "DinoSpawnEntries_SE_Beach_C",
        "DinoSpawnEntries_SE_Desert_C",
        "DinoSpawnEntries_SE_HighDesert_C",
        "DinoSpawnEntries_SE_Dunes_C",
        "DinoSpawnEntries_SE_Oasis_C",
        "DinoSpawnEntries_SE_SkyIslands_C",
        # Aberration
        "DinoSpawnEntries_Ab_Surface_C",
        "DinoSpawnEntries_Ab_Fertile_C",
        "DinoSpawnEntries_Ab_Blue_C",
        "DinoSpawnEntries_Ab_Red_C",
        # Extinction
        "DinoSpawnEntriesExtinction_City_C",
        "DinoSpawnEntriesExtinction_Wasteland_C",
        "DinoSpawnEntriesExtinction_Snow_C",
        "DinoSpawnEntriesExtinction_Desert_C",
        # Ragnarok
        "DinoSpawnEntriesRagnarok_Ice_C",
        "DinoSpawnEntriesRagnarok_HighDesert_C",
        "DinoSpawnEntriesRagnarok_Ocean_C",
        # Valguero
        "DinoSpawnEntries_Valguero_Grasslands_C",
        "DinoSpawnEntries_Valguero_UpperForest_C",
        # Crystal Isles
        "DinoSpawnEntries_CrystalIsles_C",
        # Genesis 1 & 2
        "DinoSpawnEntries_Gen1_Bog_C",
        "DinoSpawnEntries_Gen1_Snow_C",
        "DinoSpawnEntries_Gen1_Volcano_C",
        "DinoSpawnEntries_Gen2_Rockwell_C",
    ]

    def _build_tab_spawns(self, parent, srv: ServerConfig) -> None:
        """Constrói a aba de configuração de Spawn de Dinos Customizados."""
        adv = srv.advanced_settings
        w   = self._server_widgets[srv.id]

        outer_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        outer_scroll.pack(fill="both", expand=True, padx=4, pady=4)
        outer_scroll.grid_columnconfigure(0, weight=1)

        # ── Cabeçalho explicativo ─────────────────────────────────────────────
        r = 0
        info_card = ctk.CTkFrame(outer_scroll, corner_radius=10, fg_color=_CARD_BG)
        info_card.grid(row=r, column=0, padx=12, pady=(8, 6), sticky="ew")
        info_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            info_card,
            text="🦖  Spawn de Dinos Customizados",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=14, pady=(10, 2), sticky="w")
        fields_info = (
            "📦 Container de Spawn — a \"zona\" do mapa onde os dinos aparecem (ex: DinoSpawnEntriesBeach_C = praia da Island). "
            "Cada mapa tem seus próprios containers; escolha o da região que deseja modificar.\n"
            "\n"
            "📋 Entry (Registro) — um \"slot\" dentro do container representando um tipo de dino. "
            "Um container pode ter vários entries; o ARK escolhe qual spawnar baseado no peso de cada um.\n"
            "\n"
            "🏷  Nome (AnEntryName) — identificador textual da entry, apenas para referência/debug. "
            "Pode ser qualquer texto sem espaços, ex: \"MeuRex\".\n"
            "\n"
            "⚖  Peso (EntryWeight) — chance relativa de spawn. Peso 2.0 aparece o dobro de vezes que peso 1.0. "
            "Se houver vários entries, o ARK sorteará proporcionalmente (ex: 1.0 + 1.0 + 2.0 = 25 % / 25 % / 50 %).\n"
            "\n"
            "🧬 Blueprint Path — caminho do arquivo do dino no jogo, deve começar com Blueprint' e terminar com '. "
            "Um por linha; com múltiplos paths o ARK escolhe aleatoriamente. "
            "Ex: Blueprint'/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP'\n"
            "\n"
            "🔢 Max Inimigos Mult. (apenas Substituir) — multiplica a quantidade máxima de dinos dessa zona. "
            "1.0 = padrão; 2.0 = dobro de dinos na área; 0.5 = metade."
        )
        ctk.CTkLabel(
            info_card,
            text=fields_info,
            text_color="gray55",
            font=ctk.CTkFont(size=10),
            justify="left",
            anchor="w",
            wraplength=860,
        ).grid(row=1, column=0, padx=14, pady=(0, 12), sticky="w")
        r += 1

        # ── Fábrica de seção (Add / Override) ────────────────────────────────
        def _build_spawn_section(
            parent_frame,
            section_label: str,
            section_hint: str,
            is_override: bool,
            initial_containers: list,
            container_store_key: str,
        ) -> None:
            """Constrói uma seção (Adicionar ou Substituir) de spawn containers."""
            sec_frame = ctk.CTkFrame(parent_frame, corner_radius=10, fg_color=_CARD_BG)
            sec_frame.pack(fill="x", padx=0, pady=(0, 10))
            sec_frame.grid_columnconfigure(0, weight=1)

            hdr = ctk.CTkFrame(sec_frame, fg_color="transparent")
            hdr.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
            hdr.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                hdr, text=section_label,
                font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
            ).grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(
                hdr, text=section_hint,
                text_color="gray50", font=ctk.CTkFont(size=10), anchor="w",
            ).grid(row=1, column=0, sticky="w")

            containers_frame = ctk.CTkFrame(sec_frame, fg_color="transparent")
            containers_frame.grid(row=1, column=0, padx=8, pady=(0, 4), sticky="ew")
            containers_frame.grid_columnconfigure(0, weight=1)

            w[container_store_key] = []  # List[dict]

            def _add_container(initial: dict | None = None) -> None:
                idx = len(w[container_store_key])
                container_data: dict = {}
                w[container_store_key].append(container_data)

                card = ctk.CTkFrame(containers_frame, corner_radius=8,
                                    fg_color="#252535", border_width=1,
                                    border_color="#3a3a55")
                card.grid(row=idx, column=0, padx=0, pady=(0, 8), sticky="ew")
                card.grid_columnconfigure(1, weight=1)
                container_data["_card"] = card

                ci = 0

                # Linha: container class
                lbl_cont_fr = ctk.CTkFrame(card, fg_color="transparent")
                lbl_cont_fr.grid(row=ci, column=0, padx=(10, 4), pady=(8, 2), sticky="w")
                ctk.CTkLabel(lbl_cont_fr, text="Container:", anchor="w",
                             text_color="gray65",
                             font=ctk.CTkFont(size=11, weight="bold")).pack(anchor="w")
                ctk.CTkLabel(lbl_cont_fr,
                             text="Zona do mapa a modificar",
                             anchor="w", text_color="gray40",
                             font=ctk.CTkFont(size=9)).pack(anchor="w")
                container_var = tk.StringVar(
                    value=initial.get("container", "") if initial else "")
                container_data["container_var"] = container_var
                cont_combo = ctk.CTkComboBox(
                    card, variable=container_var,
                    values=self._SPAWN_CONTAINERS,
                    width=420, height=30,
                )
                cont_combo.grid(row=ci, column=1, padx=(0, 4), pady=(8, 2), sticky="w")

                def _remove_this(_card=card, _data=container_data,
                                  _store_key=container_store_key):
                    if _data in w[_store_key]:
                        w[_store_key].remove(_data)
                    _card.destroy()

                ctk.CTkButton(card, text="✖", width=28, height=28,
                              fg_color="#5a2020", hover_color="#7a2020",
                              command=_remove_this).grid(
                    row=ci, column=2, padx=(4, 10), pady=(8, 2))
                ci += 1

                # Linha: MaxDesiredNumEnemiesMultiplier (só Override)
                if is_override:
                    lbl_mult_fr = ctk.CTkFrame(card, fg_color="transparent")
                    lbl_mult_fr.grid(row=ci, column=0, padx=(10, 4), pady=(4, 2), sticky="w")
                    ctk.CTkLabel(lbl_mult_fr, text="Max Inimigos Mult.:", anchor="w",
                                 text_color="gray65",
                                 font=ctk.CTkFont(size=11)).pack(anchor="w")
                    ctk.CTkLabel(lbl_mult_fr,
                                 text="Qtd. máx. de dinos na zona\n(1.0=padrão, 2.0=dobro)",
                                 anchor="w", text_color="gray40",
                                 font=ctk.CTkFont(size=9)).pack(anchor="w")
                    mult_var = tk.StringVar(
                        value=str(initial.get("max_enemies_multiplier", 1.0)) if initial else "1.0")
                    container_data["max_mult_var"] = mult_var
                    ctk.CTkEntry(card, textvariable=mult_var, width=100, height=28).grid(
                        row=ci, column=1, padx=(0, 4), pady=(4, 2), sticky="w")
                    ci += 1

                # Sub-frame de entries
                entries_outer = ctk.CTkFrame(card, fg_color="transparent")
                entries_outer.grid(row=ci, column=0, columnspan=3,
                                   padx=8, pady=(4, 0), sticky="ew")
                entries_outer.grid_columnconfigure(0, weight=1)
                ci += 1

                # Linha de cabeçalhos das entries
                hdr_row = ctk.CTkFrame(entries_outer, fg_color="transparent")
                hdr_row.grid(row=0, column=0, sticky="ew", pady=(0, 2))
                hdr_row.grid_columnconfigure(1, weight=1)
                ctk.CTkLabel(hdr_row,
                             text="Nome  (AnEntryName)",
                             width=130, anchor="w",
                             text_color="gray50",
                             font=ctk.CTkFont(size=10)).grid(row=0, column=0, padx=(2, 4))
                ctk.CTkLabel(hdr_row,
                             text="Peso  (EntryWeight)",
                             width=55, anchor="w",
                             text_color="gray50",
                             font=ctk.CTkFont(size=10)).grid(row=0, column=1, padx=(0, 4))
                ctk.CTkLabel(hdr_row,
                             text="Blueprint Path(s) — um por linha  "
                                  "(Blueprint'/Game/…/NomeDino_Character_BP.NomeDino_Character_BP')",
                             anchor="w", text_color="gray50",
                             font=ctk.CTkFont(size=10)).grid(
                    row=0, column=2, padx=(0, 4), sticky="w")

                entries_frame = ctk.CTkFrame(entries_outer, fg_color="transparent")
                entries_frame.grid(row=1, column=0, sticky="ew")
                entries_frame.grid_columnconfigure(2, weight=1)

                container_data["entries"] = []

                def _add_entry(initial_entry: dict | None = None,
                                _ef=entries_frame,
                                _cd=container_data):
                    ei = len(_cd["entries"])
                    entry_data: dict = {}
                    _cd["entries"].append(entry_data)

                    name_var   = tk.StringVar(
                        value=initial_entry.get("name", "") if initial_entry else "")
                    weight_var = tk.StringVar(
                        value=str(initial_entry.get("weight", 1.0)) if initial_entry else "1.0")
                    bp_var     = tk.StringVar(
                        value="\n".join(initial_entry.get("blueprints", []))
                        if initial_entry else "")
                    entry_data["name_var"]   = name_var
                    entry_data["weight_var"] = weight_var
                    entry_data["bp_var"]     = bp_var

                    row_fr = ctk.CTkFrame(_ef, fg_color="transparent")
                    row_fr.grid(row=ei, column=0, columnspan=4,
                                padx=0, pady=(0, 4), sticky="ew")
                    row_fr.grid_columnconfigure(2, weight=1)

                    ctk.CTkEntry(row_fr, textvariable=name_var,
                                 width=130, height=28,
                                 placeholder_text="Nome").grid(
                        row=0, column=0, padx=(0, 4))
                    ctk.CTkEntry(row_fr, textvariable=weight_var,
                                 width=55, height=28,
                                 placeholder_text="1.0").grid(
                        row=0, column=1, padx=(0, 4))

                    bp_box = ctk.CTkTextbox(row_fr, height=52, wrap="none")
                    bp_box.grid(row=0, column=2, padx=(0, 4), sticky="ew")
                    bp_box.insert("1.0", "\n".join(
                        initial_entry.get("blueprints", [])) if initial_entry else "")
                    entry_data["bp_box"] = bp_box

                    def _remove_entry(_rd=row_fr, _ed=entry_data, _cd2=_cd):
                        if _ed in _cd2["entries"]:
                            _cd2["entries"].remove(_ed)
                        _rd.destroy()

                    ctk.CTkButton(row_fr, text="✖", width=26, height=28,
                                  fg_color="#5a2020", hover_color="#7a2020",
                                  command=_remove_entry).grid(row=0, column=3)

                # Carrega entries iniciais ou cria uma em branco
                if initial and initial.get("entries"):
                    for ie in initial["entries"]:
                        _add_entry(ie)
                else:
                    _add_entry()

                # Botão "Adicionar Entry"
                add_entry_row = ctk.CTkFrame(card, fg_color="transparent")
                add_entry_row.grid(row=ci, column=0, columnspan=3,
                                   padx=8, pady=(2, 8), sticky="w")
                container_data["_add_entry_fn"] = _add_entry
                ctk.CTkButton(
                    add_entry_row, text="➕ Adicionar Entry",
                    width=160, height=28,
                    fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    command=_add_entry,
                ).pack(side="left")

            # Carrega containers iniciais
            for init_c in initial_containers:
                _add_container(init_c)

            # Botão "Adicionar Container"
            add_cont_row = ctk.CTkFrame(sec_frame, fg_color="transparent")
            add_cont_row.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="w")
            ctk.CTkButton(
                add_cont_row, text="➕ Adicionar Container de Spawn",
                width=230, height=30,
                fg_color=_BLUE, hover_color="#253a6a",
                command=_add_container,
            ).pack(side="left")

        # ── Coloca as duas seções no scroll ───────────────────────────────────
        sections_frame = ctk.CTkFrame(outer_scroll, fg_color="transparent")
        sections_frame.grid(row=r, column=0, sticky="ew", padx=4)
        sections_frame.grid_columnconfigure(0, weight=1)
        r += 1

        _build_spawn_section(
            sections_frame,
            "➕  Adicionar Spawns",
            "Adiciona entradas a containers existentes sem remover os spawns padrão.",
            is_override=False,
            initial_containers=adv.npc_spawn_entries_add,
            container_store_key="spawn_add_list",
        )
        _build_spawn_section(
            sections_frame,
            "🔄  Substituir Spawns",
            "Substitui completamente os spawns de um container (remove os padrões).",
            is_override=True,
            initial_containers=adv.npc_spawn_entries_override,
            container_store_key="spawn_override_list",
        )

        # ── Multiplicadores por Classe de Dino ────────────────────────────────
        def _build_dino_mult_section(
            parent_frame,
            title: str,
            hint: str,
            store_key: str,
            initial_data: list,
        ) -> None:
            sec = ctk.CTkFrame(parent_frame, fg_color=_CARD_BG, corner_radius=10)
            sec.grid(row=sec.master.grid_size()[1], column=0, sticky="ew", padx=0, pady=(10, 0))
            sec.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(sec, text=title, font=ctk.CTkFont(size=13, weight="bold")
                         ).grid(row=0, column=0, padx=14, pady=(10, 2), sticky="w")
            ctk.CTkLabel(sec, text=hint, text_color="gray60", wraplength=640, justify="left"
                         ).grid(row=1, column=0, padx=14, pady=(0, 6), sticky="w")

            rows_frame = ctk.CTkFrame(sec, fg_color="transparent")
            rows_frame.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 4))
            rows_frame.grid_columnconfigure(1, weight=1)

            row_list: list[dict] = []
            w[store_key] = row_list

            def _add_row(class_name: str = "", mult: float = 1.0) -> None:
                idx = len(row_list)
                rf = ctk.CTkFrame(rows_frame, fg_color="#1e2a3a", corner_radius=6)
                rf.grid(row=idx, column=0, columnspan=3, sticky="ew", pady=2)
                rf.grid_columnconfigure(1, weight=1)

                ctk.CTkLabel(rf, text="Classe:", text_color="gray60", width=50
                             ).grid(row=0, column=0, padx=(8, 4), pady=4)
                cn_var = tk.StringVar(value=class_name)
                ctk.CTkEntry(rf, textvariable=cn_var, width=280, height=28,
                             placeholder_text="Ex: Rex_Character_BP_C"
                             ).grid(row=0, column=1, padx=4, pady=4, sticky="ew")
                ctk.CTkLabel(rf, text="Mult:", text_color="gray60", width=36
                             ).grid(row=0, column=2, padx=(6, 2), pady=4)
                mt_var = tk.StringVar(value=str(mult))
                ctk.CTkEntry(rf, textvariable=mt_var, width=70, height=28
                             ).grid(row=0, column=3, padx=(0, 4), pady=4)

                rd = {"class_name_var": cn_var, "mult_var": mt_var, "_frame": rf}
                row_list.append(rd)

                def _remove(r=rd, f=rf):
                    row_list.remove(r)
                    f.destroy()

                ctk.CTkButton(rf, text="✖", width=28, height=28,
                              fg_color="#5a1f1f", hover_color="#8a2a2a",
                              command=_remove).grid(row=0, column=4, padx=(4, 8), pady=4)

            for item in initial_data:
                _add_row(item.get("class_name", ""), item.get("multiplier", 1.0))

            add_row_frame = ctk.CTkFrame(sec, fg_color="transparent")
            add_row_frame.grid(row=3, column=0, padx=14, pady=(0, 10), sticky="w")
            ctk.CTkButton(
                add_row_frame, text="➕ Adicionar Classe",
                width=180, height=28,
                fg_color=_BLUE, hover_color="#253a6a",
                command=_add_row,
            ).pack(side="left")

        dino_mult_frame = ctk.CTkFrame(outer_scroll, fg_color="transparent")
        dino_mult_frame.grid(row=r, column=0, sticky="ew", padx=4)
        dino_mult_frame.grid_columnconfigure(0, weight=1)
        r += 1

        _build_dino_mult_section(
            dino_mult_frame,
            "🛡️  Resistência por Classe de Dino (DinoClassResistanceMultipliers)",
            "Multiplica a resistência a dano de dinos selvagens por classe.  "
            "2.0 = recebe metade do dano;  0.5 = recebe o dobro do dano.",
            "dino_res_mult_list",
            adv.dino_class_resistance_multipliers,
        )
        _build_dino_mult_section(
            dino_mult_frame,
            "⚔️  Dano por Classe de Dino (DinoClassDamageMultipliers)",
            "Multiplica o dano causado por dinos selvagens por classe.  "
            "2.0 = causa o dobro de dano;  0.5 = causa metade do dano.",
            "dino_dmg_mult_list",
            adv.dino_class_damage_multipliers,
        )
        _build_dino_mult_section(
            dino_mult_frame,
            "🛡️  Resistência — Domados (TamedDinoClassResistanceMultipliers)",
            "Igual ao anterior, mas aplica-se a dinos domados.",
            "tamed_dino_res_mult_list",
            adv.tamed_dino_class_resistance_multipliers,
        )
        _build_dino_mult_section(
            dino_mult_frame,
            "⚔️  Dano — Domados (TamedDinoClassDamageMultipliers)",
            "Igual ao anterior, mas aplica-se a dinos domados.",
            "tamed_dino_dmg_mult_list",
            adv.tamed_dino_class_damage_multipliers,
        )

        self._save_btn_row(outer_scroll, r, srv.id)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Loot (Supply Crate Overrides)
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_loot(self, parent, srv: ServerConfig) -> None:  # noqa: C901
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        w = self._server_widgets[srv.id]
        adv = srv.advanced_settings
        w["loot_crate_list"] = []

        outer_scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        outer_scroll.grid(row=0, column=0, sticky="nsew")
        outer_scroll.grid_columnconfigure(0, weight=1)

        # ── Cabeçalho ─────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(outer_scroll, fg_color=_CARD_BG, corner_radius=10)
        hdr.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="📦  Substituição de Itens de Supply Crates",
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")
        ctk.CTkLabel(
            hdr,
            text=(
                "ConfigOverrideSupplyCrateItems — substitui completamente os itens de um tipo de crate.\n"
                "Cada override define sets de itens; cada set define entries com as classes dos itens possíveis."
            ),
            text_color="gray60", wraplength=660, justify="left",
        ).grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")

        # ── Container de crates ───────────────────────────────────────────────
        crates_frame = ctk.CTkFrame(outer_scroll, fg_color="transparent")
        crates_frame.grid(row=1, column=0, sticky="ew", padx=4)
        crates_frame.grid_columnconfigure(0, weight=1)

        _KNOWN_CRATES = [
            "SupplyCrate_Level03_C",
            "SupplyCrate_Level06_C",
            "SupplyCrate_Level12_C",
            "SupplyCrate_Level25_C",
            "SupplyCrate_Level35_C",
            "SupplyCrate_Level50_C",
            "SupplyCrate_Cave_C",
            "SupplyCrate_OceanCage_C",
        ]

        def _add_entry_row(entries_frame, entry_list, items="", weight=1.0,
                           min_qty=1.0, max_qty=1.0,
                           min_ql=1.0, max_ql=1.0,
                           force_bp=False, bp_chance=0.0):
            idx = len(entry_list)
            ef = ctk.CTkFrame(entries_frame, fg_color="#1a2535", corner_radius=6)
            ef.grid(row=idx, column=0, sticky="ew", pady=2)
            ef.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(ef, text="Peso:", text_color="gray60", width=42
                         ).grid(row=0, column=0, padx=(8, 2), pady=(6, 2))
            wt_var = tk.StringVar(value=str(weight))
            ctk.CTkEntry(ef, textvariable=wt_var, width=56, height=26
                         ).grid(row=0, column=1, padx=2, pady=(6, 2), sticky="w")

            # Remove button
            def _rem_entry(ed=None, fr=ef):
                if ed in entry_list:
                    entry_list.remove(ed)
                fr.destroy()

            # We'll set up the dict after creating all widgets
            ctk.CTkLabel(ef, text="Classes de Item (uma por linha):",
                         text_color="gray60").grid(row=1, column=0, columnspan=2,
                                                    padx=8, pady=(4, 0), sticky="w")
            items_box = ctk.CTkTextbox(ef, height=60, width=380)
            items_box.grid(row=2, column=0, columnspan=5, padx=8, pady=(0, 4), sticky="ew")
            if items:
                items_box.insert("1.0", items)

            num_frame = ctk.CTkFrame(ef, fg_color="transparent")
            num_frame.grid(row=3, column=0, columnspan=5, padx=8, pady=(0, 6), sticky="w")

            def _lbl(txt): return ctk.CTkLabel(num_frame, text=txt, text_color="gray60")
            def _ent(var, w=64): return ctk.CTkEntry(num_frame, textvariable=var, width=w, height=26)

            min_qty_var = tk.StringVar(value=str(min_qty))
            max_qty_var = tk.StringVar(value=str(max_qty))
            min_ql_var  = tk.StringVar(value=str(min_ql))
            max_ql_var  = tk.StringVar(value=str(max_ql))
            bp_chance_var = tk.StringVar(value=str(bp_chance))
            force_bp_var  = tk.BooleanVar(value=force_bp)

            c = 0
            for lbl, var in (
                ("Qtd Min:", min_qty_var), ("Qtd Máx:", max_qty_var),
                ("Qual Min:", min_ql_var), ("Qual Máx:", max_ql_var),
                ("% Blueprint:", bp_chance_var),
            ):
                _lbl(lbl).grid(row=0, column=c, padx=(4, 1))
                _ent(var).grid(row=0, column=c + 1, padx=(0, 8))
                c += 2
            ctk.CTkLabel(num_frame, text="Forçar BP:", text_color="gray60"
                         ).grid(row=0, column=c, padx=(4, 1))
            ctk.CTkCheckBox(num_frame, text="", variable=force_bp_var, width=24
                            ).grid(row=0, column=c + 1, padx=(0, 8))

            ed = {
                "weight_var": wt_var, "items_box": items_box,
                "min_qty_var": min_qty_var, "max_qty_var": max_qty_var,
                "min_ql_var": min_ql_var, "max_ql_var": max_ql_var,
                "force_bp_var": force_bp_var, "bp_chance_var": bp_chance_var,
                "_frame": ef,
            }
            entry_list.append(ed)

            ctk.CTkButton(ef, text="✖", width=28, height=26,
                          fg_color="#5a1f1f", hover_color="#8a2a2a",
                          command=lambda: _rem_entry(ed)).grid(
                row=0, column=4, padx=(4, 8), pady=(6, 2))

        def _add_item_set_row(sets_frame, set_list, set_data=None):
            if set_data is None:
                set_data = {}
            idx = len(set_list)
            sf = ctk.CTkFrame(sets_frame, fg_color="#17202f", corner_radius=8)
            sf.grid(row=idx, column=0, sticky="ew", pady=4)
            sf.grid_columnconfigure(0, weight=1)

            hf = ctk.CTkFrame(sf, fg_color="transparent")
            hf.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))

            def _lbl(p, txt): return ctk.CTkLabel(p, text=txt, text_color="gray60")
            def _ent(p, var, w=64): return ctk.CTkEntry(p, textvariable=var, width=w, height=26)

            sw_var   = tk.StringVar(value=str(set_data.get("set_weight", 1.0)))
            min_var  = tk.StringVar(value=str(set_data.get("min_items", 1)))
            max_var  = tk.StringVar(value=str(set_data.get("max_items", 2)))
            pow_var  = tk.StringVar(value=str(set_data.get("num_items_power", 1.0)))
            repl_var = tk.BooleanVar(value=set_data.get("items_no_replacement", True))

            c = 0
            for lbl_txt, var, w_px in (
                ("Peso:", sw_var, 64), ("Min Itens:", min_var, 52),
                ("Max Itens:", max_var, 52), ("Power:", pow_var, 56),
            ):
                _lbl(hf, lbl_txt).grid(row=0, column=c, padx=(0 if c == 0 else 4, 2))
                _ent(hf, var, w_px).grid(row=0, column=c + 1, padx=(0, 6))
                c += 2
            _lbl(hf, "Sem Repet.:").grid(row=0, column=c, padx=(4, 2))
            ctk.CTkCheckBox(hf, text="", variable=repl_var, width=24
                            ).grid(row=0, column=c + 1, padx=(0, 4))

            ctk.CTkLabel(sf, text="Entries de Itens:", text_color="gray60",
                         font=ctk.CTkFont(size=11)
                         ).grid(row=1, column=0, padx=14, pady=(4, 0), sticky="w")

            entries_container = ctk.CTkFrame(sf, fg_color="transparent")
            entries_container.grid(row=2, column=0, sticky="ew", padx=14)
            entries_container.grid_columnconfigure(0, weight=1)
            entry_list: list[dict] = []

            for edata in set_data.get("entries", []):
                _add_entry_row(
                    entries_container, entry_list,
                    items="\n".join(edata.get("items", [])),
                    weight=edata.get("weight", 1.0),
                    min_qty=edata.get("min_qty", 1.0),
                    max_qty=edata.get("max_qty", 1.0),
                    min_ql=edata.get("min_quality", 1.0),
                    max_ql=edata.get("max_quality", 1.0),
                    force_bp=edata.get("force_blueprint", False),
                    bp_chance=edata.get("blueprint_chance", 0.0),
                )

            add_e_row = ctk.CTkFrame(sf, fg_color="transparent")
            add_e_row.grid(row=3, column=0, padx=14, pady=(4, 8), sticky="w")
            ctk.CTkButton(
                add_e_row, text="➕ Adicionar Entry", width=160, height=26,
                fg_color=_BLUE, hover_color="#253a6a",
                command=lambda ec=entries_container, el=entry_list: _add_entry_row(ec, el),
            ).pack(side="left")

            sd = {
                "set_weight_var": sw_var, "min_items_var": min_var,
                "max_items_var": max_var, "num_items_power_var": pow_var,
                "items_no_repl_var": repl_var, "entries": entry_list, "_frame": sf,
            }
            set_list.append(sd)

            def _rem_set(sdd=sd, fr=sf):
                if sdd in set_list:
                    set_list.remove(sdd)
                fr.destroy()

            ctk.CTkButton(
                hf, text="✖ Set", width=56, height=26,
                fg_color="#5a1f1f", hover_color="#8a2a2a",
                command=_rem_set,
            ).grid(row=0, column=c + 2, padx=(12, 0))

        def _add_crate_card(crate_data=None):
            if crate_data is None:
                crate_data = {}
            idx = len(w["loot_crate_list"])
            card = ctk.CTkFrame(crates_frame, fg_color=_CARD_BG, corner_radius=10)
            card.grid(row=idx, column=0, sticky="ew", padx=0, pady=(0, 8))
            card.grid_columnconfigure(0, weight=1)

            # Header row
            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
            top_row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(top_row, text="Classe do Crate:", text_color="gray60"
                         ).grid(row=0, column=0, padx=(0, 4))

            crate_class_var = tk.StringVar(value=crate_data.get("crate_class", ""))
            combo = ctk.CTkComboBox(
                top_row, variable=crate_class_var, values=_KNOWN_CRATES,
                width=260, height=28,
            )
            combo.grid(row=0, column=1, padx=(0, 8), sticky="ew")

            def _lbl(p, txt): return ctk.CTkLabel(p, text=txt, text_color="gray60")
            def _ent(p, var, ww=64): return ctk.CTkEntry(p, textvariable=var, width=ww, height=26)

            num_row = ctk.CTkFrame(card, fg_color="transparent")
            num_row.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))

            min_sets_var  = tk.StringVar(value=str(crate_data.get("min_sets", 1)))
            max_sets_var  = tk.StringVar(value=str(crate_data.get("max_sets", 1)))
            pow_sets_var  = tk.StringVar(value=str(crate_data.get("num_sets_power", 1.0)))
            repl_sets_var = tk.BooleanVar(value=crate_data.get("sets_no_replacement", True))

            c = 0
            for lbl_txt, var, wpx in (
                ("Min Sets:", min_sets_var, 52),
                ("Max Sets:", max_sets_var, 52),
                ("NumSetsPower:", pow_sets_var, 64),
            ):
                _lbl(num_row, lbl_txt).grid(row=0, column=c, padx=(0 if c == 0 else 4, 2))
                _ent(num_row, var, wpx).grid(row=0, column=c + 1, padx=(0, 8))
                c += 2
            _lbl(num_row, "Sets Sem Repet.:").grid(row=0, column=c, padx=(4, 2))
            ctk.CTkCheckBox(num_row, text="", variable=repl_sets_var, width=24
                            ).grid(row=0, column=c + 1, padx=(0, 4))

            ctk.CTkLabel(card, text="Item Sets:", text_color="gray60",
                         font=ctk.CTkFont(size=11, weight="bold")
                         ).grid(row=2, column=0, padx=14, pady=(4, 0), sticky="w")

            sets_container = ctk.CTkFrame(card, fg_color="transparent")
            sets_container.grid(row=3, column=0, sticky="ew", padx=12)
            sets_container.grid_columnconfigure(0, weight=1)
            set_list: list[dict] = []

            for sdata in crate_data.get("item_sets", []):
                _add_item_set_row(sets_container, set_list, sdata)

            add_set_row = ctk.CTkFrame(card, fg_color="transparent")
            add_set_row.grid(row=4, column=0, padx=14, pady=(6, 10), sticky="w")
            ctk.CTkButton(
                add_set_row, text="➕ Adicionar Item Set", width=180, height=28,
                fg_color=_BLUE, hover_color="#253a6a",
                command=lambda sc=sets_container, sl=set_list: _add_item_set_row(sc, sl),
            ).pack(side="left")

            cd = {
                "crate_class_var": crate_class_var,
                "min_sets_var": min_sets_var, "max_sets_var": max_sets_var,
                "num_sets_power_var": pow_sets_var, "sets_no_repl_var": repl_sets_var,
                "item_sets": set_list, "_card": card,
            }
            w["loot_crate_list"].append(cd)

            def _rem_crate(cdd=cd, fr=card):
                if cdd in w["loot_crate_list"]:
                    w["loot_crate_list"].remove(cdd)
                fr.destroy()

            ctk.CTkButton(
                top_row, text="✖ Remover Crate", width=120, height=28,
                fg_color="#5a1f1f", hover_color="#8a2a2a",
                command=_rem_crate,
            ).grid(row=0, column=2, padx=(8, 0))

        # Carrega dados existentes
        for cd in adv.supply_crate_overrides:
            _add_crate_card(cd)

        add_crate_row = ctk.CTkFrame(outer_scroll, fg_color="transparent")
        add_crate_row.grid(row=2, column=0, padx=16, pady=(4, 6), sticky="w")
        ctk.CTkButton(
            add_crate_row, text="➕ Adicionar Override de Crate",
            width=220, height=30,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=_add_crate_card,
        ).pack(side="left")

        self._save_btn_row(outer_scroll, 3, srv.id)

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
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            actions, text="🗑️  Apagar Todos os Mods",
            height=38, fg_color="#8B1A1A", hover_color="#B22222",
            command=lambda: self._clear_all_mods(srv.id),
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
    def _sanitize_steam_name(name: str) -> str:
        """Limpa nomes corrompidos com fragmentos XML/CDATA deixados por versões antigas."""
        if not name:
            return ""
        # Tenta extrair o conteúdo real de um fragmento CDATA
        if "CDATA[" in name:
            try:
                extracted = name.split("CDATA[")[-1].split("]]>")[0].strip()
                if extracted:
                    return extracted
            except Exception:
                pass
        # Descarta qualquer string que ainda contenha marcadores XML
        if "<" in name or ">" in name:
            return ""
        return name

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
                m = re.search(r"<steamID><!\[CDATA\[(.*?)\]\]></steamID>", raw)
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
            text="IDs são gravados em ShooterGame/Saved/AllowedCheaterSteamIDs.txt ao salvar.",
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

    def _write_allowed_admins(self, server_id: str) -> None:
        """Grava AllowedCheaterSteamIDs.txt imediatamente, sem depender do botão Salvar."""
        import pathlib
        srv = self.config_manager.get_server(server_id)
        if not srv or not srv.install_dir or not os.path.isdir(srv.install_dir):
            return
        try:
            allowed_path = (
                pathlib.Path(srv.install_dir)
                / "ShooterGame" / "Saved"
                / "AllowedCheaterSteamIDs.txt"
            )
            allowed_path.parent.mkdir(parents=True, exist_ok=True)
            allowed_path.write_text("\n".join(srv.admin_ids), encoding="utf-8")
        except Exception as exc:
            self._global_log(
                f"[{srv.name}] Aviso: não foi possível gravar AllowedCheaterSteamIDs.txt: {exc}",
                "warning",
            )

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
            display_name = self._sanitize_steam_name(srv.admin_names.get(steam_id, ""))
            # Atualiza o dado persistido se estava corrompido
            if display_name != srv.admin_names.get(steam_id, ""):
                if display_name:
                    srv.admin_names[steam_id] = display_name
                else:
                    srv.admin_names.pop(steam_id, None)
                self.config_manager.update_server(srv)
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
                clean = self._sanitize_steam_name(preview[3:].strip())
                if clean:
                    srv.admin_names[steam_id] = clean
        self.config_manager.update_server(srv)
        self._write_allowed_admins(server_id)
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
        self._write_allowed_admins(server_id)
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
    # Aba Chat público
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_chat(self, parent, srv: ServerConfig) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)

        w = self._server_widgets[srv.id]

        sub = ctk.CTkTabview(parent, fg_color=_BG,
                             segmented_button_fg_color=_SIDEBAR_BG,
                             segmented_button_selected_color=_GREEN_DARK,
                             segmented_button_selected_hover_color=_GREEN_HOVER,
                             segmented_button_unselected_color=_SIDEBAR_BG,
                             segmented_button_unselected_hover_color=_CARD_BG)
        sub.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        sub.add("📢 Broadcasts")
        sub.add("💬 Chat ao vivo")

        # ══════════════════════════════════════════════════════════════════════
        # Sub-aba: Broadcasts
        # ══════════════════════════════════════════════════════════════════════
        bt = sub.tab("📢 Broadcasts")
        bt.grid_columnconfigure(0, weight=1)
        bt.grid_rowconfigure(2, weight=1)

        # ── Barra de envio rápido ─────────────────────────────────────────────
        quick_bar = ctk.CTkFrame(bt, fg_color=_CARD_BG, corner_radius=8)
        quick_bar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 3))
        quick_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(quick_bar, text="📡 Envio rápido:",
                     text_color="gray55", font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, padx=(12, 8), pady=8, sticky="w")

        w["bc_quick_var"] = tk.StringVar()
        ctk.CTkEntry(quick_bar, textvariable=w["bc_quick_var"], height=32,
                     placeholder_text="Mensagem de broadcast — todos os jogadores online verão",
                     font=ctk.CTkFont(size=11)
                     ).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=8)

        ctk.CTkButton(quick_bar, text="📢 Enviar", width=100, height=32,
                      fg_color=_BLUE, hover_color=_BLUE_HOVER,
                      font=ctk.CTkFont(size=11),
                      command=lambda: self._broadcast_send_quick(srv.id)
                      ).grid(row=0, column=2, padx=(0, 10), pady=8)

        # ── Formulário: adicionar novo broadcast à biblioteca ─────────────────
        add_fr = ctk.CTkFrame(bt, fg_color=_CARD_BG, corner_radius=8)
        add_fr.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 3))
        add_fr.grid_columnconfigure(1, weight=1)
        add_fr.grid_columnconfigure(2, weight=3)

        ctk.CTkLabel(add_fr, text="+ Novo:",
                     text_color="gray55", font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, padx=(12, 8), pady=(8, 7), sticky="w")

        w["bc_new_label"] = tk.StringVar()
        ctk.CTkEntry(add_fr, textvariable=w["bc_new_label"], height=30,
                     placeholder_text="Rótulo (ex: Reinício em 5min)",
                     font=ctk.CTkFont(size=11), width=180
                     ).grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=(8, 7))

        w["bc_new_msg"] = tk.StringVar()
        ctk.CTkEntry(add_fr, textvariable=w["bc_new_msg"], height=30,
                     placeholder_text="Texto do broadcast...",
                     font=ctk.CTkFont(size=11)
                     ).grid(row=0, column=2, sticky="ew", padx=(0, 6), pady=(8, 7))

        ctk.CTkButton(add_fr, text="Adicionar", width=90, height=30,
                      fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                      font=ctk.CTkFont(size=11),
                      command=lambda: self._broadcast_add(srv.id)
                      ).grid(row=0, column=3, padx=(0, 10), pady=(8, 7))

        # ── Lista de broadcasts salvos ────────────────────────────────────────
        list_hdr = ctk.CTkFrame(bt, fg_color="transparent")
        list_hdr.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 6))
        list_hdr.grid_columnconfigure(0, weight=1)
        list_hdr.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(list_hdr, text="Biblioteca de Broadcasts",
                     text_color="gray45", font=ctk.CTkFont(size=11, weight="bold")
                     ).grid(row=0, column=0, sticky="w", padx=2, pady=(2, 2))

        bc_scroll = ctk.CTkScrollableFrame(list_hdr, fg_color=_CARD_BG, corner_radius=8)
        bc_scroll.grid(row=1, column=0, sticky="nsew")
        bc_scroll.grid_columnconfigure(0, weight=1)
        w["bc_list_scroll"] = bc_scroll

        # Carrega broadcasts existentes
        self._broadcast_refresh_list(srv.id)

        # ══════════════════════════════════════════════════════════════════════
        # Sub-aba: Chat ao vivo
        # ══════════════════════════════════════════════════════════════════════
        ct = sub.tab("💬 Chat ao vivo")
        ct.grid_columnconfigure(0, weight=1)
        ct.grid_rowconfigure(1, weight=1)

        # Barra de controle
        ctrl = ctk.CTkFrame(ct, corner_radius=10, fg_color=_CARD_BG)
        ctrl.grid(row=0, column=0, padx=6, pady=(6, 4), sticky="ew")
        ctrl.grid_columnconfigure(3, weight=1)

        w["chat_auto_poll"] = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            ctrl, text="Auto-atualizar",
            variable=w["chat_auto_poll"],
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            checkmark_color="white",
            command=lambda: self._chat_toggle_poll(srv.id),
        ).grid(row=0, column=0, padx=(14, 8), pady=10)

        ctk.CTkLabel(ctrl, text="Intervalo:", text_color="gray60").grid(
            row=0, column=1, padx=(0, 4), pady=10)
        w["chat_interval"] = tk.StringVar(value="5")
        ctk.CTkOptionMenu(
            ctrl, variable=w["chat_interval"],
            values=["3", "5", "10", "15", "30"], width=70,
        ).grid(row=0, column=2, padx=(0, 2), pady=10, sticky="w")
        ctk.CTkLabel(ctrl, text="seg", text_color="gray50").grid(
            row=0, column=3, padx=(0, 16), pady=10, sticky="w")

        w["chat_status_var"] = tk.StringVar(value="⬛ Inativo")
        ctk.CTkLabel(ctrl, textvariable=w["chat_status_var"],
                     text_color="gray50", font=ctk.CTkFont(size=12)).grid(
            row=0, column=4, padx=8, pady=10, sticky="w")

        ctk.CTkButton(
            ctrl, text="🔄 Buscar", width=100, height=30,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            command=lambda: self._chat_fetch(srv.id),
        ).grid(row=0, column=5, padx=(0, 6), pady=10)
        ctk.CTkButton(
            ctrl, text="🗑 Limpar", width=90, height=30,
            fg_color="#3a3a5a", hover_color="#252540",
            command=lambda: self._chat_clear(srv.id),
        ).grid(row=0, column=6, padx=(0, 14), pady=10)

        # Exibição do chat
        w["chat_box"] = ctk.CTkTextbox(
            ct, font=ctk.CTkFont(family="Courier New", size=12),
            wrap="word", state="disabled", fg_color="#0a0a14",
        )
        w["chat_box"].grid(row=1, column=0, padx=6, pady=4, sticky="nsew")
        tw = w["chat_box"]._textbox
        tw.tag_config("ts",      foreground="#555570")
        tw.tag_config("player",  foreground="#88d4a0")
        tw.tag_config("server",  foreground="#6699ff")
        tw.tag_config("message", foreground="#d0d0e0")
        tw.tag_config("sys",     foreground="#888899")
        tw.tag_config("err",     foreground="#ff6666")
        self._chat_append(
            srv.id,
            "💬  Chat do Servidor — requer RCON conectado (aba 'Console RCON').\n"
            "Ative 'Auto-atualizar' ou clique em '🔄 Buscar' para carregar mensagens.\n",
            "sys",
        )

        # Campo de envio
        input_row = ctk.CTkFrame(ct, fg_color="transparent")
        input_row.grid(row=2, column=0, padx=6, pady=(2, 8), sticky="ew")
        input_row.grid_columnconfigure(0, weight=1)

        w["chat_input"] = tk.StringVar()
        inp = ctk.CTkEntry(
            input_row, textvariable=w["chat_input"], height=36,
            placeholder_text="Mensagem para enviar como [SERVIDOR] via ServerChat — pressione Enter para enviar...",
        )
        inp.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        inp.bind("<Return>", lambda e: self._chat_send(srv.id))

        ctk.CTkButton(
            input_row, text="Enviar ▶", width=90, height=36,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=lambda: self._chat_send(srv.id),
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
    # Aba Backup
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_backup(self, parent, srv: ServerConfig) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        w = self._server_widgets[srv.id]

        _interval_opts = ["1h", "2h", "3h", "6h", "12h", "24h"]
        _interval_map  = {1: "1h", 2: "2h", 3: "3h", 6: "6h", 12: "12h", 24: "24h"}

        # ── Card: configurações ───────────────────────────────────────────
        cfg_card = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
        cfg_card.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        cfg_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            cfg_card, text="💾  Backup Automático",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 4), sticky="w")

        def _lbl(parent_w, text: str, hint: str) -> ctk.CTkFrame:
            fr = ctk.CTkFrame(parent_w, fg_color="transparent")
            ctk.CTkLabel(fr, text=text, width=190, anchor="w",
                         text_color="gray65",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
            ctk.CTkLabel(fr, text=hint, width=190, anchor="w",
                         text_color="gray40",
                         font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))
            return fr

        # Habilitar
        w["backup_enabled"] = tk.BooleanVar(value=srv.backup_enabled)
        _lbl(cfg_card,
             "Habilitar backup automático",
             "Cria backups em segundo plano no intervalo definido."
             ).grid(row=1, column=0, padx=(16, 8), pady=(4, 0), sticky="w")
        ctk.CTkSwitch(
            cfg_card, text="",
            variable=w["backup_enabled"],
        ).grid(row=1, column=1, padx=(0, 16), pady=(4, 0), sticky="w")

        # Intervalo
        w["backup_interval"] = tk.StringVar(value=_interval_map.get(srv.backup_interval_hours, "6h"))
        _lbl(cfg_card,
             "Intervalo entre backups",
             "Com que frequência o backup automático será executado."
             ).grid(row=2, column=0, padx=(16, 8), pady=(4, 0), sticky="w")
        ctk.CTkOptionMenu(
            cfg_card, values=_interval_opts,
            variable=w["backup_interval"], width=110, height=32,
        ).grid(row=2, column=1, padx=(0, 16), pady=4, sticky="w")

        # Manter últimos N backups
        w["backup_keep"] = tk.StringVar(value=str(srv.backup_keep_count))
        _lbl(cfg_card,
             "Manter últimos N backups",
             "Backups mais antigos são excluídos automaticamente."
             ).grid(row=3, column=0, padx=(16, 8), pady=(4, 0), sticky="w")
        ctk.CTkEntry(cfg_card, textvariable=w["backup_keep"], width=80, height=32).grid(
            row=3, column=1, padx=(0, 16), pady=4, sticky="w")

        # O que incluir
        w["backup_inc_saves"]  = tk.BooleanVar(value=srv.backup_include_saves)
        w["backup_inc_config"] = tk.BooleanVar(value=srv.backup_include_config)
        _lbl(cfg_card,
             "O que incluir no backup",
             "Saves = dados de jogadores/mundo.  Config = arquivos .ini."
             ).grid(row=4, column=0, padx=(16, 8), pady=(4, 0), sticky="w")
        chk_row = ctk.CTkFrame(cfg_card, fg_color="transparent")
        chk_row.grid(row=4, column=1, padx=(0, 16), pady=4, sticky="w")
        ctk.CTkCheckBox(chk_row, text="Saves",  variable=w["backup_inc_saves"],  width=100).pack(side="left")
        ctk.CTkCheckBox(chk_row, text="Config", variable=w["backup_inc_config"], width=100).pack(side="left", padx=(8, 0))

        # Pasta personalizada
        w["backup_dir"] = tk.StringVar(value=srv.backup_dir)
        _lbl(cfg_card,
             "Pasta de destino",
             "Deixe vazio para usar o padrão em %APPDATA%."
             ).grid(row=5, column=0, padx=(16, 8), pady=(4, 6), sticky="w")
        dir_fr = ctk.CTkFrame(cfg_card, fg_color="transparent")
        dir_fr.grid(row=5, column=1, padx=(0, 16), pady=(4, 6), sticky="ew")
        dir_fr.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(
            dir_fr, textvariable=w["backup_dir"], height=32,
            placeholder_text="Padrão: %APPDATA%\\ARKLAND-ServerManager\\backups\\",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            dir_fr, text="📁", width=34, height=32,
            command=lambda: self._browse_dir(w["backup_dir"]),
        ).grid(row=0, column=1)

        # Botões Salvar + Backup Manual
        btn_row = ctk.CTkFrame(cfg_card, fg_color="transparent")
        btn_row.grid(row=6, column=0, columnspan=2, padx=12, pady=(4, 14), sticky="w")
        ctk.CTkButton(
            btn_row, text="💾  Salvar Configurações",
            height=36, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=lambda: self._save_backup_config(srv.id),
        ).pack(side="left", padx=(4, 8))
        ctk.CTkButton(
            btn_row, text="📸  Fazer Backup Agora",
            height=36, fg_color=_BLUE, hover_color=_BLUE_HOVER,
            command=lambda: self._do_manual_backup(srv.id),
        ).pack(side="left")

        # ── Card: lista de backups ────────────────────────────────────────
        list_card = ctk.CTkFrame(parent, corner_radius=10, fg_color=_CARD_BG)
        list_card.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        list_card.grid_columnconfigure(0, weight=1)
        list_card.grid_rowconfigure(1, weight=1)

        hdr2 = ctk.CTkFrame(list_card, fg_color="transparent")
        hdr2.grid(row=0, column=0, padx=16, pady=(12, 4), sticky="ew")
        hdr2.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr2, text="📂  Backups Disponíveis",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            hdr2, text="🔄 Atualizar", width=100, height=28,
            fg_color="#3a3a5a", hover_color="#252540",
            command=lambda: self._refresh_backup_list(srv.id),
        ).grid(row=0, column=1, sticky="e")

        scroll = ctk.CTkScrollableFrame(list_card, fg_color="transparent")
        scroll.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        w["_backup_list_frame"] = scroll

        self._refresh_backup_list(srv.id)

    # ── Busca de configurações ─────────────────────────────────────────────────

    def _register_config_item(self, server_id: str, label: str, hint: str, tab: str) -> None:
        self._config_search_index.setdefault(server_id, []).append(
            (label.rstrip(": "), hint, tab)
        )

    def _build_config_search_bar(self, parent: ctk.CTkFrame, server_id: str) -> None:
        """Barra de busca flutuante que filtra todas as configurações por rótulo/dica/aba."""
        bar = ctk.CTkFrame(parent, fg_color=_SIDEBAR_BG, corner_radius=0, height=40)
        bar.grid(row=1, column=0, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bar, text="🔍", font=ctk.CTkFont(size=13), width=28,
                     text_color="gray50").grid(row=0, column=0, padx=(10, 0), pady=8)

        search_var = tk.StringVar()
        entry = ctk.CTkEntry(
            bar, textvariable=search_var, height=26, corner_radius=6,
            placeholder_text="Buscar configuração...",
            fg_color="#16162a", border_color="#2a2a4a", border_width=1,
            font=ctk.CTkFont(size=11),
        )
        entry.grid(row=0, column=1, padx=(4, 12), pady=7, sticky="ew")

        popup: list = [None]

        def _hide() -> None:
            if popup[0]:
                try:
                    popup[0].destroy()
                except Exception:
                    pass
                popup[0] = None

        def _on_change(*_) -> None:
            query = search_var.get().strip().lower()
            w = self._server_widgets.get(server_id, {})
            tabs: Any = w.get("_tabs")
            _hide()
            if len(query) < 2 or not tabs:
                return
            index = self._config_search_index.get(server_id, [])
            matches = [
                (lbl, hint, tab) for lbl, hint, tab in index
                if query in lbl.lower() or query in hint.lower() or query in tab.lower()
            ]
            if not matches:
                return
            n = min(len(matches), 7)
            row_h = 56
            outer = ctk.CTkFrame(
                parent, fg_color="#1a1a2e", corner_radius=8,
                border_color="#3a3a5a", border_width=1,
                height=n * row_h + (22 if len(matches) > 7 else 6),
            )
            outer.grid_propagate(False)
            inner = ctk.CTkScrollableFrame(outer, fg_color="transparent")
            inner.pack(fill="both", expand=True)
            inner.grid_columnconfigure(0, weight=1)
            parent.update_idletasks()
            by = bar.winfo_y() + bar.winfo_height()
            outer.place(x=8, y=by + 2, relwidth=1.0, width=-16)
            outer.lift()
            popup[0] = outer

            def _make_cb(tab_name: str) -> Any:
                def _go() -> None:
                    try:
                        tabs.set(tab_name)
                        # CTkTabview.set() pode não disparar o command; força build da aba
                        on_tc = self._server_widgets.get(server_id, {}).get("_on_tab_change")
                        if callable(on_tc):
                            on_tc()
                    except Exception:
                        pass
                    search_var.set("")
                    _hide()
                return _go

            for i, (lbl, hint, tab) in enumerate(matches[:7]):
                row_fr = ctk.CTkFrame(inner, fg_color="transparent", cursor="hand2", height=row_h)
                row_fr.grid(row=i, column=0, sticky="ew", padx=4, pady=1)
                row_fr.grid_columnconfigure(1, weight=1)
                row_fr.grid_propagate(False)

                badge = ctk.CTkLabel(
                    row_fr, text=tab, width=70, height=20,
                    font=ctk.CTkFont(size=9, weight="bold"),
                    text_color="#5a9ad5", fg_color="#161630", corner_radius=4,
                )
                badge.grid(row=0, column=0, rowspan=2, padx=(6, 8), pady=(8, 4), sticky="nw")

                name_lbl = ctk.CTkLabel(
                    row_fr, text=lbl,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color="gray85", anchor="w",
                )
                name_lbl.grid(row=0, column=1, padx=(0, 8), pady=(8, 0), sticky="w")

                hint_lbl = ctk.CTkLabel(
                    row_fr,
                    text=(hint[:70] + "…") if len(hint) > 70 else hint,
                    font=ctk.CTkFont(size=9), text_color="gray50", anchor="w",
                )
                hint_lbl.grid(row=1, column=1, padx=(0, 8), pady=(0, 6), sticky="w")

                cb = _make_cb(tab)
                for widget in (row_fr, badge, name_lbl, hint_lbl):
                    widget.bind("<Button-1>", lambda _e, c=cb: c())
                    widget.bind("<Enter>",    lambda _e, f=row_fr: f.configure(fg_color="#252550"))
                    widget.bind("<Leave>",    lambda _e, f=row_fr: f.configure(fg_color="transparent"))

            if len(matches) > 7:
                ctk.CTkLabel(
                    inner,
                    text=f"  … e mais {len(matches) - 7} resultado(s)",
                    font=ctk.CTkFont(size=9), text_color="gray45",
                ).grid(row=7, column=0, padx=8, pady=(2, 6), sticky="w")

        search_var.trace_add("write", _on_change)
        entry.bind("<Escape>", lambda _e: (search_var.set(""), _hide()))
        entry.bind("<FocusOut>", lambda _e: self.after(200, _hide))
        self._server_widgets[server_id]["_config_search_var"] = search_var

    # ── Backup ─────────────────────────────────────────────────────────────────

    def _save_backup_config(self, server_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return
        w = self._server_widgets.get(server_id, {})
        _interval_rev = {"1h": 1, "2h": 2, "3h": 3, "6h": 6, "12h": 12, "24h": 24}

        srv.backup_enabled          = w.get("backup_enabled",  tk.BooleanVar()).get()
        srv.backup_interval_hours   = _interval_rev.get(w.get("backup_interval", tk.StringVar(value="6h")).get(), 6)
        srv.backup_include_saves    = w.get("backup_inc_saves",  tk.BooleanVar(value=True)).get()
        srv.backup_include_config   = w.get("backup_inc_config", tk.BooleanVar(value=True)).get()
        srv.backup_dir              = w.get("backup_dir", tk.StringVar()).get().strip()
        try:
            srv.backup_keep_count   = max(1, int(w.get("backup_keep", tk.StringVar(value="10")).get()))
        except ValueError:
            pass

        self.config_manager.update_server(srv)
        self.config_manager.save_servers()

        # Reinicia o timer para este servidor
        if self._backup_manager:
            self._backup_manager.stop_auto_backup(server_id)
            if srv.backup_enabled:
                self._backup_manager.start_auto_backup(srv)

        # Feedback visual
        w_entry = w.get("backup_keep")
        if w_entry:
            w_entry.set(str(srv.backup_keep_count))

    def _do_manual_backup(self, server_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return
        bm = self._backup_manager
        if not bm:
            return

        def _run() -> None:
            result = bm.do_backup(srv)
            def _done() -> None:
                if result:
                    self._refresh_backup_list(server_id)
                else:
                    messagebox.showerror(
                        "Backup falhou",
                        "Não foi possível realizar o backup. Verifique o diretório de instalação.",
                        parent=self,
                    )
            self.after(0, _done)

        threading.Thread(target=_run, daemon=True).start()

    def _refresh_backup_list(self, server_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        w   = self._server_widgets.get(server_id, {})
        frame: Optional[ctk.CTkScrollableFrame] = w.get("_backup_list_frame")
        if not frame or not srv:
            return

        for child in frame.winfo_children():
            child.destroy()

        entries = self._backup_manager.list_backups(srv) if self._backup_manager else []

        if not entries:
            ctk.CTkLabel(
                frame,
                text="Nenhum backup encontrado.\nClique em 📸 Fazer Backup Agora para criar o primeiro.",
                text_color="gray50",
            ).pack(pady=20)
            return

        for entry in entries:
            row_fr = ctk.CTkFrame(frame, corner_radius=8, fg_color="#252535")
            row_fr.pack(fill="x", padx=8, pady=3)
            row_fr.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                row_fr, text=entry.label,
                anchor="w", font=ctk.CTkFont(family="Courier New", size=11),
            ).grid(row=0, column=0, padx=12, pady=8, sticky="ew")

            btn_fr = ctk.CTkFrame(row_fr, fg_color="transparent")
            btn_fr.grid(row=0, column=1, padx=(0, 8))

            ep = str(entry.path)
            ctk.CTkButton(
                btn_fr, text="↩ Restaurar", width=100, height=28,
                fg_color=_BLUE, hover_color=_BLUE_HOVER,
                command=lambda p=ep, sid=server_id: self._confirm_restore_backup(sid, p),
            ).pack(side="left", padx=(0, 6))
            ctk.CTkButton(
                btn_fr, text="🗑", width=36, height=28,
                fg_color=_RED_DARK, hover_color=_RED_HOVER,
                command=lambda p=ep, sid=server_id: self._confirm_delete_backup(sid, p),
            ).pack(side="left")

    def _confirm_restore_backup(self, server_id: str, backup_path: str) -> None:
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return
        inst = self.server_manager.get_instance(server_id)
        if inst and inst.status != SERVER_STATUS_STOPPED:
            messagebox.showwarning(
                "Servidor em execução",
                "Pare o servidor antes de restaurar um backup.",
                parent=self,
            )
            return
        snap = Path(backup_path).name
        if not messagebox.askyesno(
            "Confirmar Restauração",
            f"Restaurar o snapshot '{snap}' para '{srv.name}'?\n\n"
            "Os arquivos atuais de config e/ou saves serão sobrescritos.",
            parent=self,
        ):
            return

        bm = self._backup_manager
        if not bm:
            return

        def _run() -> None:
            ok = bm.restore_backup(srv, backup_path)
            self.after(0, lambda: messagebox.showinfo(
                "Restauração concluída" if ok else "Erro na Restauração",
                f"Backup de '{snap}' restaurado com sucesso." if ok
                else "Falha ao restaurar. Verifique os logs.",
                parent=self,
            ))

        threading.Thread(target=_run, daemon=True).start()

    def _confirm_delete_backup(self, server_id: str, backup_path: str) -> None:
        snap = Path(backup_path).name
        if not messagebox.askyesno(
            "Confirmar Exclusão",
            f"Excluir permanentemente o snapshot '{snap}'?",
            parent=self,
        ):
            return
        if self._backup_manager:
            self._backup_manager.delete_backup(backup_path)
            self._refresh_backup_list(server_id)

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

        # ── Seção Discord ───────────────────────────────────────────
        self._section_lbl(parent, 8, "🔔  Notificações Discord")
        disc_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        disc_card.grid(row=9, column=0, padx=20, pady=(0, 14), sticky="ew")
        disc_card.grid_columnconfigure(1, weight=1)

        dc = cfg.discord_notify
        self._discord_enabled_var    = tk.BooleanVar(value=dc.enabled)
        self._discord_url_var        = tk.StringVar(value=dc.webhook_url)
        self._discord_sender_var     = tk.StringVar(value=dc.sender_name)
        self._discord_notify_start   = tk.BooleanVar(value=dc.notify_start)
        self._discord_notify_stop    = tk.BooleanVar(value=dc.notify_stop)
        self._discord_notify_crash   = tk.BooleanVar(value=dc.notify_crash)
        self._discord_notify_update  = tk.BooleanVar(value=dc.notify_update)
        self._discord_notify_backup  = tk.BooleanVar(value=dc.notify_backup)

        ctk.CTkCheckBox(
            disc_card, text="Ativar notificações Discord",
            variable=self._discord_enabled_var,
            checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(16, 4), sticky="w")
        ctk.CTkLabel(disc_card,
                     text="Envia mensagens para um canal Discord quando eventos de servidor ocorrem.",
                     text_color="gray45", font=ctk.CTkFont(size=10)).grid(
            row=1, column=0, columnspan=2, padx=(42, 16), pady=(0, 10), sticky="w")

        ctk.CTkLabel(disc_card, text="URL do Webhook:", width=160, anchor="w",
                     text_color="gray60").grid(row=2, column=0, padx=16, pady=(4, 0), sticky="w")
        ctk.CTkEntry(disc_card, textvariable=self._discord_url_var, height=32,
                     placeholder_text="https://discord.com/api/webhooks/...").grid(
            row=2, column=1, padx=(0, 16), pady=(4, 0), sticky="ew")
        ctk.CTkLabel(disc_card,
                     text="Obtenha em: Canal Discord → Editar Canal → Integrações → Webhooks → Novo Webhook → Copiar URL",
                     text_color="gray45", font=ctk.CTkFont(size=10)).grid(
            row=3, column=0, columnspan=2, padx=(16, 16), pady=(0, 6), sticky="w")

        ctk.CTkLabel(disc_card, text="Nome do remetente:", width=160, anchor="w",
                     text_color="gray60").grid(row=4, column=0, padx=16, pady=4, sticky="w")
        ctk.CTkEntry(disc_card, textvariable=self._discord_sender_var, height=32,
                     placeholder_text="ARKLAND").grid(
            row=4, column=1, padx=(0, 16), pady=4, sticky="ew")
        ctk.CTkLabel(disc_card,
                     text="Nome exibido como autor das mensagens no Discord.",
                     text_color="gray45", font=ctk.CTkFont(size=10)).grid(
            row=5, column=0, columnspan=2, padx=(16, 16), pady=(0, 6), sticky="w")

        ctk.CTkLabel(disc_card, text="Notificar em:", text_color="gray55",
                     font=ctk.CTkFont(size=11, weight="bold")).grid(
            row=6, column=0, columnspan=2, padx=16, pady=(10, 2), sticky="w")

        evt_fr = ctk.CTkFrame(disc_card, fg_color="transparent")
        evt_fr.grid(row=7, column=0, columnspan=2, padx=12, pady=(0, 14), sticky="w")
        for ci, (txt, var) in enumerate([
            ("🟡 Iniciando / Online",  self._discord_notify_start),
            ("🔴 Parado / Encerrando", self._discord_notify_stop),
            ("💥 Crash",               self._discord_notify_crash),
            ("🔄 Atualização de mods", self._discord_notify_update),
            ("💾 Backup concluído",   self._discord_notify_backup),
        ]):
            ctk.CTkCheckBox(
                evt_fr, text=txt, variable=var, width=200,
                checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                font=ctk.CTkFont(size=11),
            ).grid(row=ci // 3, column=ci % 3, padx=8, pady=3, sticky="w")

        ctk.CTkButton(
            parent, text="💾  Salvar Configurações Globais",
            height=44, font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=self._save_global_config,
        ).grid(row=10, column=0, padx=20, pady=(0, 24), sticky="ew")

    # ══════════════════════════════════════════════════════════════════════════
    # Sobre / Atualizações
    # ══════════════════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════════════════
    # ArkShop Manager
    # ══════════════════════════════════════════════════════════════════════════

    def _build_arkshop_panel(self, parent: ctk.CTkScrollableFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)

        self._arkshop_mgr = ArkShopManager()

        # ── Cabeçalho ────────────────────────────────────────────────────────
        hdr_row = ctk.CTkFrame(parent, fg_color="transparent")
        hdr_row.grid(row=0, column=0, padx=20, pady=(20, 2), sticky="ew")
        hdr_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr_row, text="Gerenciador ArkShop",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            hdr_row, text="🌐  Plugin no ArkServerAPI", width=190, height=32,
            fg_color="#1e3a5a", hover_color="#16304f",
            font=ctk.CTkFont(size=12),
            command=lambda: webbrowser.open("https://ark-server-api.com/resources/ase-arkshop.36/"),
        ).grid(row=0, column=1, padx=(12, 0))

        info_row = ctk.CTkFrame(parent, fg_color="transparent")
        info_row.grid(row=1, column=0, padx=24, pady=(0, 12), sticky="ew")
        info_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            info_row,
            text="Edite as configurações do plugin ArkShop (config.json)  •  Plugin por PANDERAZ",
            font=ctk.CTkFont(size=12), text_color="gray60",
        ).grid(row=0, column=0, sticky="w")

        # ── Seletor de arquivo ────────────────────────────────────────────────
        file_frame = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=10)
        file_frame.grid(row=2, column=0, padx=20, pady=(0, 16), sticky="ew")
        file_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(file_frame, text="Arquivo:", font=ctk.CTkFont(size=13, weight="bold")
                     ).grid(row=0, column=0, padx=(16, 8), pady=14)

        self._arkshop_path_var = tk.StringVar()
        ctk.CTkEntry(file_frame, textvariable=self._arkshop_path_var,
                     placeholder_text="Caminho para o config.json do ArkShop..."
                     ).grid(row=0, column=1, padx=4, pady=14, sticky="ew")

        ctk.CTkButton(
            file_frame, text="Procurar", width=90,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=self._arkshop_browse,
        ).grid(row=0, column=2, padx=4, pady=14)

        ctk.CTkButton(
            file_frame, text="Carregar", width=90,
            fg_color="#2a4a6a", hover_color="#1e3a5a",
            command=self._arkshop_load,
        ).grid(row=0, column=3, padx=(4, 16), pady=14)

        # ── Status ───────────────────────────────────────────────────────────
        self._arkshop_status_var = tk.StringVar(value="Nenhum arquivo carregado.")
        ctk.CTkLabel(parent, textvariable=self._arkshop_status_var,
                     font=ctk.CTkFont(size=11), text_color="gray50",
                     ).grid(row=3, column=0, padx=24, pady=(0, 8), sticky="w")

        # ── Alvos de salvamento adicionais ─────────────────────────────────
        targets_outer = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=10)
        targets_outer.grid(row=4, column=0, padx=20, pady=(0, 8), sticky="ew")
        targets_outer.grid_columnconfigure(0, weight=1)

        th = ctk.CTkFrame(targets_outer, fg_color="transparent")
        th.grid(row=0, column=0, padx=(14, 10), pady=(10, 4), sticky="ew")
        th.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(th, text="Cluster / múltiplos servidores",
                     font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(th, text="Arquivos adicionais que também receberão cada save",
                     font=ctk.CTkFont(size=11), text_color="gray55",
                     ).grid(row=1, column=0, sticky="w")
        ctk.CTkButton(th, text="➕  Adicionar Servidor", width=165, height=28,
                      fg_color="#2a4a2a", hover_color="#1e3a1e",
                      font=ctk.CTkFont(size=11),
                      command=self._arkshop_add_extra_target,
                      ).grid(row=0, column=1, rowspan=2, padx=(8, 0))

        self._arkshop_extra_targets_frame = ctk.CTkFrame(targets_outer, fg_color="transparent")
        self._arkshop_extra_targets_frame.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="ew")
        self._arkshop_extra_targets_frame.grid_columnconfigure(0, weight=1)
        self._arkshop_extra_target_vars: List[Tuple[tk.StringVar, ctk.CTkFrame]] = []

        # ── Presets ──────────────────────────────────────────────────────────
        presets_outer = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=10)
        presets_outer.grid(row=5, column=0, padx=20, pady=(0, 8), sticky="ew")
        presets_outer.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(presets_outer, text="Preset:",
                     font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, padx=(14, 8), pady=12)
        self._arkshop_presets: Dict[str, Any] = {}
        self._arkshop_preset_var = tk.StringVar(value="(nenhum preset)")
        self._arkshop_preset_menu = ctk.CTkOptionMenu(
            presets_outer, variable=self._arkshop_preset_var,
            values=["(nenhum preset)"], width=200,
            fg_color="#252540", button_color="#1a1a30", button_hover_color="#141425",
        )
        self._arkshop_preset_menu.grid(row=0, column=1, padx=4, pady=12, sticky="ew")
        ctk.CTkButton(presets_outer, text="💾  Salvar", width=95, height=30,
                      fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                      font=ctk.CTkFont(size=11),
                      command=self._arkshop_save_preset,
                      ).grid(row=0, column=2, padx=4, pady=12)
        ctk.CTkButton(presets_outer, text="📂  Carregar", width=95, height=30,
                      fg_color="#2a4a6a", hover_color="#1e3a5a",
                      font=ctk.CTkFont(size=11),
                      command=self._arkshop_load_preset,
                      ).grid(row=0, column=3, padx=4, pady=12)
        ctk.CTkButton(presets_outer, text="🗑", width=34, height=30,
                      fg_color="#5a1a1a", hover_color="#4a0a0a",
                      font=ctk.CTkFont(size=11),
                      command=self._arkshop_delete_preset,
                      ).grid(row=0, column=4, padx=(4, 14), pady=12)

        # ── TabView principal ─────────────────────────────────────────────────
        self._arkshop_tabs = ctk.CTkTabview(parent, height=600)
        self._arkshop_tabs.grid(row=6, column=0, padx=20, pady=(0, 8), sticky="ew")

        for tab_name in ("Geral", "MySQL", "Recompensas", "Kits", "Itens da Loja", "Mensagens", "Editor JSON"):
            self._arkshop_tabs.add(tab_name)

        self._arkshop_build_tab_geral()
        self._arkshop_build_tab_mysql()
        self._arkshop_build_tab_recompensas()
        self._arkshop_build_tab_kits()
        self._arkshop_build_tab_shop()
        self._arkshop_build_tab_messages()
        self._arkshop_build_tab_json()

        # ── Botão Salvar ─────────────────────────────────────────────────────
        ctk.CTkButton(
            parent, text="💾  Salvar Arquivo", height=42,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=self._arkshop_save,
        ).grid(row=7, column=0, padx=20, pady=(4, 24), sticky="ew")

    # ── Tabs ─────────────────────────────────────────────────────────────────

    def _arkshop_build_tab_geral(self) -> None:
        tab = self._arkshop_tabs.tab("Geral")
        tab.grid_columnconfigure(0, weight=1)

        # ── Display ──────────────────────────────────────────────────────────
        disp = ctk.CTkFrame(tab, fg_color="#1a1a2e", corner_radius=10)
        disp.grid(row=0, column=0, padx=12, pady=(10, 6), sticky="ew")
        disp.grid_columnconfigure(1, weight=1)
        disp.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(disp, text="Configurações de Exibição",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).grid(row=0, column=0, columnspan=4, padx=14, pady=(10, 6), sticky="w")

        self._arkshop_items_page = tk.StringVar(value="15")
        self._arkshop_display_time = tk.StringVar(value="15.0")
        self._arkshop_text_size = tk.StringVar(value="1.3")

        for col_lbl, col_var, c in [
            ("Itens por Página:", self._arkshop_items_page, 0),
            ("Tempo Exibição (s):", self._arkshop_display_time, 2),
        ]:
            ctk.CTkLabel(disp, text=col_lbl, font=ctk.CTkFont(size=12)
                         ).grid(row=1, column=c, padx=(14, 4), pady=8, sticky="e")
            ctk.CTkEntry(disp, textvariable=col_var, width=80
                         ).grid(row=1, column=c + 1, padx=(0, 14), pady=8, sticky="w")

        ctk.CTkLabel(disp, text="Tamanho do Texto:", font=ctk.CTkFont(size=12)
                     ).grid(row=2, column=0, padx=(14, 4), pady=8, sticky="e")
        ctk.CTkEntry(disp, textvariable=self._arkshop_text_size, width=80
                     ).grid(row=2, column=1, padx=(0, 14), pady=8, sticky="w")

        self._arkshop_db_override = tk.StringVar()
        self._arkshop_default_kit = tk.StringVar()

        ctk.CTkLabel(disp, text="DbPathOverride:", font=ctk.CTkFont(size=12)
                     ).grid(row=3, column=0, padx=(14, 4), pady=8, sticky="e")
        ctk.CTkEntry(disp, textvariable=self._arkshop_db_override
                     ).grid(row=3, column=1, padx=(0, 14), pady=8, sticky="ew")

        ctk.CTkLabel(disp, text="Kit Padrão (DefaultKit):", font=ctk.CTkFont(size=12)
                     ).grid(row=3, column=2, padx=(14, 4), pady=8, sticky="e")
        ctk.CTkEntry(disp, textvariable=self._arkshop_default_kit, width=120
                     ).grid(row=3, column=3, padx=(0, 14), pady=8, sticky="w")

        # ── Booleans ─────────────────────────────────────────────────────────
        bool_frame = ctk.CTkFrame(tab, fg_color="#1a1a2e", corner_radius=10)
        bool_frame.grid(row=1, column=0, padx=12, pady=6, sticky="ew")
        bool_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(bool_frame, text="Comportamento",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).grid(row=0, column=0, columnspan=2, padx=14, pady=(10, 6), sticky="w")

        self._arkshop_bool_vars: Dict[str, tk.BooleanVar] = {}
        for idx, (key, label) in enumerate(GENERAL_BOOL_LABELS):
            var = tk.BooleanVar()
            self._arkshop_bool_vars[key] = var
            r, c = divmod(idx, 2)
            ctk.CTkCheckBox(bool_frame, text=label, variable=var,
                            font=ctk.CTkFont(size=12),
                            checkmark_color="#ffffff",
                            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                            ).grid(row=r + 1, column=c, padx=18, pady=5, sticky="w")

        # extra bottom padding
        ctk.CTkFrame(tab, fg_color="transparent", height=8).grid(row=2, column=0)

    def _arkshop_build_tab_mysql(self) -> None:
        tab = self._arkshop_tabs.tab("MySQL")
        tab.grid_columnconfigure(0, weight=1)

        # ── MySQL ─────────────────────────────────────────────────────────────
        mysql_f = ctk.CTkFrame(tab, fg_color="#1a1a2e", corner_radius=10)
        mysql_f.grid(row=0, column=0, padx=12, pady=(10, 6), sticky="ew")
        mysql_f.grid_columnconfigure(1, weight=1)
        mysql_f.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(mysql_f, text="Conexão MySQL",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).grid(row=0, column=0, columnspan=4, padx=14, pady=(10, 4), sticky="w")

        self._arkshop_use_mysql = tk.BooleanVar()
        ctk.CTkCheckBox(mysql_f, text="Usar MySQL (UseMysql)",
                        variable=self._arkshop_use_mysql,
                        font=ctk.CTkFont(size=12),
                        checkmark_color="#ffffff",
                        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                        ).grid(row=1, column=0, columnspan=4, padx=14, pady=(4, 8), sticky="w")

        self._arkshop_mysql_host = tk.StringVar(value="127.0.0.1")
        self._arkshop_mysql_user = tk.StringVar()
        self._arkshop_mysql_pass = tk.StringVar()
        self._arkshop_mysql_db   = tk.StringVar(value="arkshop")
        self._arkshop_mysql_port = tk.StringVar(value="3306")

        mysql_fields = [
            ("Host:",    self._arkshop_mysql_host,  0, False),
            ("Porta:",   self._arkshop_mysql_port,  2, False),
            ("Usuário:", self._arkshop_mysql_user,  0, False),
            ("Senha:",   self._arkshop_mysql_pass,  2, True),
            ("Banco:",   self._arkshop_mysql_db,    0, False),
        ]
        for i, (lbl, var, col, masked) in enumerate(mysql_fields):
            r = i // 2 + 2
            c = (i % 2) * 2
            ctk.CTkLabel(mysql_f, text=lbl, font=ctk.CTkFont(size=12)
                         ).grid(row=r, column=c, padx=(14, 4), pady=7, sticky="e")
            show = "*" if masked else ""
            ctk.CTkEntry(mysql_f, textvariable=var, show=show
                         ).grid(row=r, column=c + 1, padx=(0, 14), pady=7, sticky="ew")

        # ── Discord ───────────────────────────────────────────────────────────
        disc_f = ctk.CTkFrame(tab, fg_color="#1a1a2e", corner_radius=10)
        disc_f.grid(row=1, column=0, padx=12, pady=6, sticky="ew")
        disc_f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(disc_f, text="Discord Webhook",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).grid(row=0, column=0, columnspan=4, padx=14, pady=(10, 4), sticky="w")

        self._arkshop_discord_enabled    = tk.BooleanVar()
        self._arkshop_discord_sendername = tk.StringVar(value="ArkShop")
        self._arkshop_discord_url        = tk.StringVar()

        ctk.CTkCheckBox(disc_f, text="Habilitado",
                        variable=self._arkshop_discord_enabled,
                        font=ctk.CTkFont(size=12),
                        checkmark_color="#ffffff",
                        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                        ).grid(row=1, column=0, columnspan=4, padx=14, pady=(4, 8), sticky="w")

        for r, (lbl, var) in enumerate([
            ("Nome do Remetente:", self._arkshop_discord_sendername),
            ("URL do Webhook:",    self._arkshop_discord_url),
        ]):
            ctk.CTkLabel(disc_f, text=lbl, font=ctk.CTkFont(size=12)
                         ).grid(row=r + 2, column=0, padx=(14, 6), pady=7, sticky="e")
            ctk.CTkEntry(disc_f, textvariable=var
                         ).grid(row=r + 2, column=1, padx=(0, 14), pady=7, sticky="ew")

    def _arkshop_build_tab_recompensas(self) -> None:
        tab = self._arkshop_tabs.tab("Recompensas")
        tab.grid_columnconfigure(0, weight=1)

        # ── TimedPointsReward ─────────────────────────────────────────────────
        tpr_f = ctk.CTkFrame(tab, fg_color="#1a1a2e", corner_radius=10)
        tpr_f.grid(row=0, column=0, padx=12, pady=(10, 6), sticky="ew")
        tpr_f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(tpr_f, text="TimedPointsReward — Pontos Automáticos por Tempo",
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).grid(row=0, column=0, columnspan=4, padx=14, pady=(10, 4), sticky="w")

        self._arkshop_tpr_enabled = tk.BooleanVar()
        self._arkshop_tpr_interval = tk.StringVar(value="30")
        self._arkshop_tpr_stack    = tk.BooleanVar()

        row_ctrl = ctk.CTkFrame(tpr_f, fg_color="transparent")
        row_ctrl.grid(row=1, column=0, columnspan=4, padx=12, pady=6, sticky="ew")
        row_ctrl.grid_columnconfigure(3, weight=1)

        ctk.CTkCheckBox(row_ctrl, text="Habilitado",
                        variable=self._arkshop_tpr_enabled,
                        font=ctk.CTkFont(size=12),
                        checkmark_color="#ffffff",
                        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                        ).grid(row=0, column=0, padx=(2, 16), pady=4)
        ctk.CTkLabel(row_ctrl, text="Intervalo (min):", font=ctk.CTkFont(size=12)
                     ).grid(row=0, column=1, padx=(8, 4))
        ctk.CTkEntry(row_ctrl, textvariable=self._arkshop_tpr_interval, width=70
                     ).grid(row=0, column=2, padx=(0, 16))
        ctk.CTkCheckBox(row_ctrl, text="Empilhar Recompensas (StackRewards)",
                        variable=self._arkshop_tpr_stack,
                        font=ctk.CTkFont(size=12),
                        checkmark_color="#ffffff",
                        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                        ).grid(row=0, column=3, padx=8)

        # Tabela de grupos
        ctk.CTkLabel(tpr_f, text="Grupos e Recompensas:",
                     font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=2, column=0, columnspan=4, padx=14, pady=(8, 2), sticky="w")

        grp_list_frame = ctk.CTkFrame(tpr_f, fg_color="#101020", corner_radius=8)
        grp_list_frame.grid(row=3, column=0, columnspan=4, padx=14, pady=(0, 8), sticky="ew")
        grp_list_frame.grid_columnconfigure(0, weight=1)
        grp_list_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(grp_list_frame, text="Grupo", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="gray60").grid(row=0, column=0, padx=10, pady=4, sticky="w")
        ctk.CTkLabel(grp_list_frame, text="Pontos", font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="gray60").grid(row=0, column=1, padx=10, pady=4, sticky="w")

        self._arkshop_groups_rows: List[tuple[tk.StringVar, tk.StringVar]] = []
        self._arkshop_groups_frame = grp_list_frame
        self._arkshop_groups_next_row = 1

        # botões de adicionar linha
        add_row_btn = ctk.CTkButton(
            tpr_f, text="+ Adicionar Grupo", width=160, height=30,
            fg_color="#2a4a2a", hover_color="#1e3a1e",
            font=ctk.CTkFont(size=12),
            command=self._arkshop_add_group_row,
        )
        add_row_btn.grid(row=4, column=0, padx=14, pady=(0, 10), sticky="w")

        # Adicionar uma linha vazia por padrão
        self._arkshop_add_group_row()

    def _arkshop_add_group_row(
        self,
        group_name: str = "",
        amount: str = "0",
    ) -> None:
        row_idx = self._arkshop_groups_next_row
        frame = self._arkshop_groups_frame

        name_var   = tk.StringVar(value=group_name)
        amount_var = tk.StringVar(value=amount)
        self._arkshop_groups_rows.append((name_var, amount_var))

        ctk.CTkEntry(frame, textvariable=name_var, placeholder_text="Ex: Default"
                     ).grid(row=row_idx, column=0, padx=6, pady=3, sticky="ew")
        ctk.CTkEntry(frame, textvariable=amount_var, width=80
                     ).grid(row=row_idx, column=1, padx=6, pady=3, sticky="w")

        def _remove(nv=name_var, av=amount_var) -> None:
            self._arkshop_groups_rows.remove((nv, av))
            # reconstruir a tabela completamente
            for child in frame.winfo_children():
                info = child.grid_info()
                if info.get("row", 0) == 0:
                    continue  # manter cabeçalho
                child.destroy()
            self._arkshop_groups_next_row = 1
            for (nv2, av2) in list(self._arkshop_groups_rows):
                self._arkshop_groups_rows.remove((nv2, av2))
            rows_backup = list(self._arkshop_groups_rows)
            self._arkshop_groups_rows.clear()
            self._arkshop_groups_next_row = 1
            for (nv2, av2) in rows_backup:
                self._arkshop_add_group_row(nv2.get(), av2.get())

        ctk.CTkButton(frame, text="✕", width=28, height=28,
                      fg_color="#5a2a2a", hover_color="#4a1a1a",
                      font=ctk.CTkFont(size=11),
                      command=_remove,
                      ).grid(row=row_idx, column=2, padx=4, pady=3)

        self._arkshop_groups_next_row += 1

    def _arkshop_build_tab_kits(self) -> None:
        tab = self._arkshop_tabs.tab("Kits")
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        # ── Painel esquerdo: lista ──────────────────────────────────────────
        left = ctk.CTkFrame(tab, fg_color="#101020", corner_radius=10, width=215)
        left.grid(row=0, column=0, padx=(8, 4), pady=8, sticky="ns")
        left.grid_propagate(False)
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        hdr_f = ctk.CTkFrame(left, fg_color="transparent")
        hdr_f.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        hdr_f.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr_f, text="Kits",
                     font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr_f, text="＋", width=28, height=26,
                      fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._arkshop_new_kit,
                      ).grid(row=0, column=1)

        self._arkshop_kits_list = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self._arkshop_kits_list.grid(row=1, column=0, sticky="nsew", padx=2, pady=(0, 8))
        self._arkshop_kits_list.grid_columnconfigure(0, weight=1)

        # ── Painel direito: detalhe ─────────────────────────────────────────
        self._arkshop_kit_detail_outer = ctk.CTkFrame(tab, fg_color="#0d0d1a", corner_radius=10)
        self._arkshop_kit_detail_outer.grid(row=0, column=1, padx=(4, 8), pady=8, sticky="nsew")
        self._arkshop_kit_detail_outer.grid_columnconfigure(0, weight=1)
        self._arkshop_kit_detail_outer.grid_rowconfigure(0, weight=1)

        self._arkshop_selected_kit_id: Optional[str] = None
        self._arkshop_kit_basic_vars: Dict[str, Any] = {}
        self._arkshop_kit_items_rows: List[Dict[str, Any]] = []
        self._arkshop_kit_dinos_rows: List[Dict[str, Any]] = []
        self._arkshop_kit_cmds_rows:  List[Dict[str, Any]] = []
        self._arkshop_kit_items_frame: Any = None
        self._arkshop_kit_dinos_frame: Any = None
        self._arkshop_kit_cmds_frame:  Any = None

        self._arkshop_kit_placeholder = ctk.CTkLabel(
            self._arkshop_kit_detail_outer,
            text="← Selecione um kit na lista",
            text_color="gray50", font=ctk.CTkFont(size=13),
        )
        self._arkshop_kit_placeholder.place(relx=0.5, rely=0.5, anchor="center")

    def _arkshop_build_tab_shop(self) -> None:
        tab = self._arkshop_tabs.tab("Itens da Loja")
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        # ── Painel esquerdo: lista ──────────────────────────────────────────
        left = ctk.CTkFrame(tab, fg_color="#101020", corner_radius=10, width=215)
        left.grid(row=0, column=0, padx=(8, 4), pady=8, sticky="ns")
        left.grid_propagate(False)
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        hdr_f = ctk.CTkFrame(left, fg_color="transparent")
        hdr_f.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        hdr_f.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr_f, text="Itens da Loja",
                     font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr_f, text="＋", width=28, height=26,
                      fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._arkshop_new_shop_item,
                      ).grid(row=0, column=1)

        self._arkshop_shop_list = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self._arkshop_shop_list.grid(row=1, column=0, sticky="nsew", padx=2, pady=(0, 8))
        self._arkshop_shop_list.grid_columnconfigure(0, weight=1)

        # ── Painel direito: detalhe ─────────────────────────────────────────
        self._arkshop_shop_detail_outer = ctk.CTkFrame(tab, fg_color="#0d0d1a", corner_radius=10)
        self._arkshop_shop_detail_outer.grid(row=0, column=1, padx=(4, 8), pady=8, sticky="nsew")
        self._arkshop_shop_detail_outer.grid_columnconfigure(0, weight=1)
        self._arkshop_shop_detail_outer.grid_rowconfigure(0, weight=1)

        self._arkshop_selected_shop_item_id: Optional[str] = None
        self._arkshop_shop_basic_vars: Dict[str, tk.Variable] = {}
        self._arkshop_shop_items_rows: List[Dict[str, tk.Variable]] = []
        self._arkshop_shop_items_frame: Any = None
        self._arkshop_shop_cmds_rows: List[Dict[str, tk.Variable]] = []
        self._arkshop_shop_cmds_frame: Any = None
        self._arkshop_shop_cmds_next_row: int = 1

        ctk.CTkLabel(
            self._arkshop_shop_detail_outer,
            text="← Selecione um item na lista",
            text_color="gray50", font=ctk.CTkFont(size=13),
        ).place(relx=0.5, rely=0.5, anchor="center")

    # ── Seleção e edição de Kits ──────────────────────────────────────────────

    def _arkshop_select_kit(self, kit_id: str) -> None:
        if self._arkshop_selected_kit_id and self._arkshop_selected_kit_id != kit_id:
            self._arkshop_apply_kit_changes(silent=True)
        self._arkshop_selected_kit_id = kit_id
        for w in self._arkshop_kit_detail_outer.winfo_children():
            w.destroy()
        detail = ctk.CTkScrollableFrame(self._arkshop_kit_detail_outer, fg_color="transparent")
        detail.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        detail.grid_columnconfigure(0, weight=1)
        self._arkshop_build_kit_detail(detail, kit_id, self._arkshop_mgr.kits.get(kit_id, {}))

    def _arkshop_build_kit_detail(self, parent: ctk.CTkScrollableFrame,
                                   kit_id: str, kit: dict) -> None:
        parent.grid_columnconfigure(0, weight=1)

        # título + botões de ação
        title_row = ctk.CTkFrame(parent, fg_color="transparent")
        title_row.grid(row=0, column=0, padx=12, pady=(10, 6), sticky="ew")
        title_row.grid_columnconfigure(0, weight=1)
        id_var = tk.StringVar(value=kit_id)
        id_frame = ctk.CTkFrame(title_row, fg_color="transparent")
        id_frame.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(id_frame, text="Kit:",
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).grid(row=0, column=0, padx=(0, 6), sticky="w")
        ctk.CTkEntry(id_frame, textvariable=id_var, width=220,
                     font=ctk.CTkFont(size=13)
                     ).grid(row=0, column=1, sticky="w")
        ctk.CTkButton(title_row, text="✔ Aplicar Alterações", width=155, height=30,
                      fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                      font=ctk.CTkFont(size=11),
                      command=lambda: self._arkshop_apply_kit_changes(),
                      ).grid(row=0, column=1, padx=(6, 0))
        ctk.CTkButton(title_row, text="🗑 Excluir Kit", width=110, height=30,
                      fg_color="#5a1a1a", hover_color="#4a0a0a",
                      font=ctk.CTkFont(size=11),
                      command=self._arkshop_delete_current_kit,
                      ).grid(row=0, column=2, padx=(6, 0))

        # ── Campos básicos ──────────────────────────────────────────────────
        basic_f = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=8)
        basic_f.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")
        basic_f.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(basic_f, text="Configurações do Kit",
                     font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, columnspan=4, padx=12, pady=(8, 4), sticky="w")

        price_var  = tk.StringVar(value=str(kit.get("Price", 0)))
        amount_var = tk.StringVar(value=str(kit.get("DefaultAmount", 1)))
        desc_var   = tk.StringVar(value=str(kit.get("Description", "")))
        spawn_var  = tk.BooleanVar(value=bool(kit.get("OnlyFromSpawn", False)))
        perms      = kit.get("Permissions", [])
        perm_var   = tk.StringVar(
            value=", ".join(str(p) for p in perms) if isinstance(perms, list) else str(perms))

        for c, (lbl, var) in enumerate([("Preço:", price_var), ("Qtd Padrão:", amount_var)]):
            ctk.CTkLabel(basic_f, text=lbl, font=ctk.CTkFont(size=12)
                         ).grid(row=1, column=c * 2, padx=(12, 4), pady=6, sticky="e")
            ctk.CTkEntry(basic_f, textvariable=var, width=90
                         ).grid(row=1, column=c * 2 + 1, padx=(0, 12), pady=6, sticky="ew")

        ctk.CTkLabel(basic_f, text="Descrição:", font=ctk.CTkFont(size=12)
                     ).grid(row=2, column=0, padx=(12, 4), pady=6, sticky="e")
        ctk.CTkEntry(basic_f, textvariable=desc_var
                     ).grid(row=2, column=1, columnspan=3, padx=(0, 12), pady=6, sticky="ew")

        ctk.CTkLabel(basic_f, text="Permissões (vírgula):", font=ctk.CTkFont(size=12)
                     ).grid(row=3, column=0, padx=(12, 4), pady=6, sticky="e")
        ctk.CTkEntry(basic_f, textvariable=perm_var, placeholder_text="Ex: vip, admin"
                     ).grid(row=3, column=1, columnspan=3, padx=(0, 12), pady=6, sticky="ew")

        ctk.CTkCheckBox(basic_f, text="OnlyFromSpawn (apenas ao spawnar)",
                        variable=spawn_var, font=ctk.CTkFont(size=12),
                        checkmark_color="#ffffff",
                        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                        ).grid(row=4, column=0, columnspan=4, padx=12, pady=(4, 10), sticky="w")

        self._arkshop_kit_basic_vars = {
            "_id": id_var,
            "Price": price_var, "DefaultAmount": amount_var,
            "Description": desc_var, "OnlyFromSpawn": spawn_var, "Permissions": perm_var,
        }

        # ── Itens ───────────────────────────────────────────────────────────
        items_outer = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=8)
        items_outer.grid(row=2, column=0, padx=12, pady=(0, 8), sticky="ew")
        items_outer.grid_columnconfigure(0, weight=1)

        ih = ctk.CTkFrame(items_outer, fg_color="transparent")
        ih.grid(row=0, column=0, padx=10, pady=(8, 4), sticky="ew")
        ih.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(ih, text="Itens", font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(ih, text="+ Item", width=80, height=26,
                      fg_color="#2a4a2a", hover_color="#1e3a1e",
                      font=ctk.CTkFont(size=11),
                      command=lambda: self._arkshop_add_kit_item_row(self._arkshop_kit_items_frame),
                      ).grid(row=0, column=1)

        items_tbl = ctk.CTkFrame(items_outer, fg_color="#101020", corner_radius=6)
        items_tbl.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        items_tbl.grid_columnconfigure(3, weight=1)
        for c, (h, w) in enumerate([("Quality", 70), ("Force BP", 68), ("Qtd", 54), ("Blueprint", None)]):
            ctk.CTkLabel(items_tbl, text=h, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="gray50"
                         ).grid(row=0, column=c, padx=(8 if c == 0 else 4, 4), pady=4, sticky="w")

        self._arkshop_kit_items_frame = items_tbl
        self._arkshop_kit_items_rows = []
        self._arkshop_kit_items_next_row = 1
        for item_data in kit.get("Items", []):
            self._arkshop_add_kit_item_row(items_tbl, item_data)

        # ── Dinos ───────────────────────────────────────────────────────────
        dinos_outer = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=8)
        dinos_outer.grid(row=3, column=0, padx=12, pady=(0, 8), sticky="ew")
        dinos_outer.grid_columnconfigure(0, weight=1)

        dh = ctk.CTkFrame(dinos_outer, fg_color="transparent")
        dh.grid(row=0, column=0, padx=10, pady=(8, 4), sticky="ew")
        dh.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(dh, text="Dinos", font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(dh, text="+ Dino", width=80, height=26,
                      fg_color="#2a4a2a", hover_color="#1e3a1e",
                      font=ctk.CTkFont(size=11),
                      command=lambda: self._arkshop_add_kit_dino_row(self._arkshop_kit_dinos_frame),
                      ).grid(row=0, column=1)

        dinos_tbl = ctk.CTkFrame(dinos_outer, fg_color="#101020", corner_radius=6)
        dinos_tbl.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        dinos_tbl.grid_columnconfigure((2, 3), weight=1)
        for c, h in enumerate(("Nível", "Gênero", "Blueprint", "Saddle BP")):
            ctk.CTkLabel(dinos_tbl, text=h, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="gray50"
                         ).grid(row=0, column=c, padx=(8 if c == 0 else 4, 4), pady=4, sticky="w")

        self._arkshop_kit_dinos_frame = dinos_tbl
        self._arkshop_kit_dinos_rows = []
        self._arkshop_kit_dinos_next_row = 1
        for dino_data in kit.get("Dinos", []):
            self._arkshop_add_kit_dino_row(dinos_tbl, dino_data)

        # ── Comandos ────────────────────────────────────────────────────────
        cmds_outer = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=8)
        cmds_outer.grid(row=4, column=0, padx=12, pady=(0, 10), sticky="ew")
        cmds_outer.grid_columnconfigure(0, weight=1)

        ch = ctk.CTkFrame(cmds_outer, fg_color="transparent")
        ch.grid(row=0, column=0, padx=10, pady=(8, 4), sticky="ew")
        ch.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(ch, text="Comandos", font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, sticky="w")

        _CMD_EXAMPLES = (
            "Variáveis disponíveis nos comandos:\n"
            "  {steamid}   — Steam ID do jogador\n"
            "  {playerid}  — ID interno do jogador\n"
            "  {playername}— Nome do jogador\n"
            "\n"
            "Exemplos de comandos ArkShop:\n"
            "  AddPoints {steamid} 500\n"
            "  RemovePoints {steamid} 100\n"
            "  GiveItem {steamid} \"Blueprint'/Game/...'\" 1 0 false\n"
            "  AddExperience {steamid} 1000 false false\n"
            "  PrintToPlayer {steamid} \"Obrigado pela compra!\"\n"
            "  RenamePlayer {steamid} NovoNome\n"
            "  Cheat GiveEngrams {steamid}\n"
            "  TP {steamid} X Y Z\n"
            "\n"
            "  ExecuteAsAdmin: marque apenas para comandos\n"
            "  que exigem privilégio de admin no servidor."
        )
        help_lbl = ctk.CTkLabel(ch, text=" ? ", width=24, height=24,
                                font=ctk.CTkFont(size=11, weight="bold"),
                                fg_color="#252540", corner_radius=12,
                                text_color="#7ab8f5", cursor="question_arrow")
        help_lbl.grid(row=0, column=1, padx=(4, 6))
        _Tooltip(help_lbl, _CMD_EXAMPLES, delay=200)

        ctk.CTkButton(ch, text="+ Comando", width=100, height=26,
                      fg_color="#2a4a2a", hover_color="#1e3a1e",
                      font=ctk.CTkFont(size=11),
                      command=lambda: self._arkshop_add_kit_command_row(self._arkshop_kit_cmds_frame),
                      ).grid(row=0, column=2)

        cmds_tbl = ctk.CTkFrame(cmds_outer, fg_color="#101020", corner_radius=6)
        cmds_tbl.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        cmds_tbl.grid_columnconfigure(0, weight=1)
        for c, h in enumerate(("Comando", "Exec. como Admin")):
            ctk.CTkLabel(cmds_tbl, text=h, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="gray50"
                         ).grid(row=0, column=c, padx=(8 if c == 0 else 4, 4), pady=4, sticky="w")

        self._arkshop_kit_cmds_frame = cmds_tbl
        self._arkshop_kit_cmds_rows = []
        self._arkshop_kit_cmds_next_row = 1
        for cmd_data in kit.get("Commands", []):
            self._arkshop_add_kit_command_row(cmds_tbl, cmd_data)

    # ── Row helpers: Items ────────────────────────────────────────────────────

    def _arkshop_add_kit_item_row(self,
                                   container: ctk.CTkFrame,
                                   data: Optional[dict] = None) -> None:
        data = data or {}
        rv = {
            "Quality":        tk.StringVar(value=str(data.get("Quality", 0))),
            "ForceBlueprint": tk.BooleanVar(value=bool(data.get("ForceBlueprint", False))),
            "Amount":         tk.StringVar(value=str(data.get("Amount", 1))),
            "Blueprint":      tk.StringVar(value=str(data.get("Blueprint", ""))),
        }
        self._arkshop_kit_items_rows.append(rv)
        self._arkshop_grid_kit_item_row(container, self._arkshop_kit_items_next_row, rv)
        self._arkshop_kit_items_next_row += 1

    def _arkshop_grid_kit_item_row(self, container: ctk.CTkFrame,
                                    row_i: int, rv: dict) -> None:
        ctk.CTkEntry(container, textvariable=rv["Quality"], width=60
                     ).grid(row=row_i, column=0, padx=(8, 4), pady=3)
        ctk.CTkCheckBox(container, text="", variable=rv["ForceBlueprint"],
                        width=30, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                        checkmark_color="#ffffff"
                        ).grid(row=row_i, column=1, padx=4, pady=3)
        ctk.CTkEntry(container, textvariable=rv["Amount"], width=52
                     ).grid(row=row_i, column=2, padx=4, pady=3)
        _bp_frm = ctk.CTkFrame(container, fg_color="transparent")
        _bp_frm.grid(row=row_i, column=3, padx=4, pady=3, sticky="ew")
        _bp_frm.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(_bp_frm, textvariable=rv["Blueprint"],
                     font=ctk.CTkFont(size=11), placeholder_text="Blueprint'..."
                     ).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            _bp_frm, text="🔍", width=28, height=26,
            fg_color="#1e3a5f", hover_color="#2a5285",
            font=ctk.CTkFont(size=11),
            command=lambda v=rv["Blueprint"]: self._open_blueprint_picker(
                on_select=lambda bp, _v=v: _v.set(f"Blueprint'{bp['path']}'"),
                category="items",
            ),
        ).grid(row=0, column=1, padx=(4, 0))
        ctk.CTkButton(container, text="✕", width=26, height=26,
                      fg_color="#5a2a2a", hover_color="#4a1a1a",
                      font=ctk.CTkFont(size=10),
                      command=lambda r=rv: self._arkshop_remove_kit_item(r),
                      ).grid(row=row_i, column=4, padx=(4, 8), pady=3)

    def _arkshop_remove_kit_item(self, rv: dict) -> None:
        if rv in self._arkshop_kit_items_rows:
            self._arkshop_kit_items_rows.remove(rv)
        self._arkshop_refresh_table(
            self._arkshop_kit_items_frame,
            self._arkshop_kit_items_rows,
            self._arkshop_grid_kit_item_row,
        )
        self._arkshop_kit_items_next_row = len(self._arkshop_kit_items_rows) + 1

    # ── Row helpers: Dinos ───────────────────────────────────────────────────

    def _arkshop_add_kit_dino_row(self,
                                   container: ctk.CTkFrame,
                                   data: Optional[dict] = None) -> None:
        data = data or {}
        rv = {
            "Level":          tk.StringVar(value=str(data.get("Level", 1))),
            "Gender":         tk.StringVar(value=str(data.get("Gender", ""))),
            "Blueprint":      tk.StringVar(value=str(data.get("Blueprint", ""))),
            "SaddleBlueprint":tk.StringVar(value=str(data.get("SaddleBlueprint", ""))),
        }
        self._arkshop_kit_dinos_rows.append(rv)
        self._arkshop_grid_kit_dino_row(container, self._arkshop_kit_dinos_next_row, rv)
        self._arkshop_kit_dinos_next_row += 1

    def _arkshop_grid_kit_dino_row(self, container: ctk.CTkFrame,
                                    row_i: int, rv: dict) -> None:
        ctk.CTkEntry(container, textvariable=rv["Level"], width=54
                     ).grid(row=row_i, column=0, padx=(8, 4), pady=3)
        ctk.CTkEntry(container, textvariable=rv["Gender"],
                     width=76, placeholder_text="Random"
                     ).grid(row=row_i, column=1, padx=4, pady=3)
        _bp_frm = ctk.CTkFrame(container, fg_color="transparent")
        _bp_frm.grid(row=row_i, column=2, padx=4, pady=3, sticky="ew")
        _bp_frm.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(_bp_frm, textvariable=rv["Blueprint"],
                     font=ctk.CTkFont(size=11), placeholder_text="Blueprint'..."
                     ).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            _bp_frm, text="🔍", width=28, height=26,
            fg_color="#1e3a5f", hover_color="#2a5285",
            font=ctk.CTkFont(size=11),
            command=lambda v=rv["Blueprint"]: self._open_blueprint_picker(
                on_select=lambda bp, _v=v: _v.set(f"Blueprint'{bp['path']}'"),
                category="creatures",
            ),
        ).grid(row=0, column=1, padx=(4, 0))
        _sbp_frm = ctk.CTkFrame(container, fg_color="transparent")
        _sbp_frm.grid(row=row_i, column=3, padx=4, pady=3, sticky="ew")
        _sbp_frm.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(_sbp_frm, textvariable=rv["SaddleBlueprint"],
                     font=ctk.CTkFont(size=11), placeholder_text="SaddleBP (opcional)"
                     ).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            _sbp_frm, text="🔍", width=28, height=26,
            fg_color="#1e3a5f", hover_color="#2a5285",
            font=ctk.CTkFont(size=11),
            command=lambda v=rv["SaddleBlueprint"]: self._open_blueprint_picker(
                on_select=lambda bp, _v=v: _v.set(f"Blueprint'{bp['path']}'"),
                category="items",
            ),
        ).grid(row=0, column=1, padx=(4, 0))
        ctk.CTkButton(container, text="✕", width=26, height=26,
                      fg_color="#5a2a2a", hover_color="#4a1a1a",
                      font=ctk.CTkFont(size=10),
                      command=lambda r=rv: self._arkshop_remove_kit_dino(r),
                      ).grid(row=row_i, column=4, padx=(4, 8), pady=3)

    def _arkshop_remove_kit_dino(self, rv: dict) -> None:
        if rv in self._arkshop_kit_dinos_rows:
            self._arkshop_kit_dinos_rows.remove(rv)
        self._arkshop_refresh_table(
            self._arkshop_kit_dinos_frame,
            self._arkshop_kit_dinos_rows,
            self._arkshop_grid_kit_dino_row,
        )
        self._arkshop_kit_dinos_next_row = len(self._arkshop_kit_dinos_rows) + 1

    # ── Row helpers: Commands ────────────────────────────────────────────────

    def _arkshop_add_kit_command_row(self,
                                      container: ctk.CTkFrame,
                                      data: Optional[dict] = None) -> None:
        data = data or {}
        rv = {
            "Command":        tk.StringVar(value=str(data.get("Command", ""))),
            "ExecuteAsAdmin": tk.BooleanVar(value=bool(data.get("ExecuteAsAdmin", False))),
        }
        self._arkshop_kit_cmds_rows.append(rv)
        self._arkshop_grid_kit_cmd_row(container, self._arkshop_kit_cmds_next_row, rv)
        self._arkshop_kit_cmds_next_row += 1

    def _arkshop_grid_kit_cmd_row(self, container: ctk.CTkFrame,
                                   row_i: int, rv: dict) -> None:
        ctk.CTkEntry(container, textvariable=rv["Command"],
                     font=ctk.CTkFont(size=11), placeholder_text="cheat command..."
                     ).grid(row=row_i, column=0, padx=(8, 4), pady=3, sticky="ew")
        ctk.CTkCheckBox(container, text="Admin", variable=rv["ExecuteAsAdmin"],
                        width=80, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                        checkmark_color="#ffffff", font=ctk.CTkFont(size=11),
                        ).grid(row=row_i, column=1, padx=4, pady=3)
        ctk.CTkButton(container, text="✕", width=26, height=26,
                      fg_color="#5a2a2a", hover_color="#4a1a1a",
                      font=ctk.CTkFont(size=10),
                      command=lambda r=rv: self._arkshop_remove_kit_cmd(r),
                      ).grid(row=row_i, column=2, padx=(4, 8), pady=3)

    def _arkshop_remove_kit_cmd(self, rv: dict) -> None:
        if rv in self._arkshop_kit_cmds_rows:
            self._arkshop_kit_cmds_rows.remove(rv)
        self._arkshop_refresh_table(
            self._arkshop_kit_cmds_frame,
            self._arkshop_kit_cmds_rows,
            self._arkshop_grid_kit_cmd_row,
        )
        self._arkshop_kit_cmds_next_row = len(self._arkshop_kit_cmds_rows) + 1

    # ── Utilitário de rebuild de tabela ──────────────────────────────────────

    @staticmethod
    def _arkshop_refresh_table(container: Optional[ctk.CTkFrame],
                                rows: list, grid_fn) -> None:
        if container is None:
            return
        for w in container.winfo_children():
            if w.grid_info().get("row", 0) != 0:
                w.destroy()
        for i, rv in enumerate(rows, start=1):
            grid_fn(container, i, rv)

    # ── Apply / New / Delete Kit ─────────────────────────────────────────────

    def _arkshop_apply_kit_changes(self, silent: bool = False) -> None:
        kit_id = self._arkshop_selected_kit_id
        if not kit_id or not self._arkshop_kit_basic_vars:
            return
        existing = dict(self._arkshop_mgr.kits.get(kit_id, {}))
        bv = self._arkshop_kit_basic_vars

        # Verificar renomeação de ID
        id_var = bv.get("_id")
        new_id = id_var.get().strip() if id_var else kit_id
        if not new_id:
            new_id = kit_id
        if new_id != kit_id and new_id in self._arkshop_mgr.kits:
            messagebox.showerror("ArkShop", f"ID '{new_id}' já existe.")
            return
        target_id = new_id

        try:
            existing["Price"] = int(bv["Price"].get())
        except ValueError:
            pass
        try:
            existing["DefaultAmount"] = int(bv["DefaultAmount"].get())
        except ValueError:
            pass
        existing["Description"]  = bv["Description"].get()
        existing["OnlyFromSpawn"] = bv["OnlyFromSpawn"].get()
        perm_str = bv["Permissions"].get().strip()
        existing["Permissions"] = [p.strip() for p in perm_str.split(",") if p.strip()]
        existing["Items"] = [
            {
                "Quality":       self._safe_int(rv["Quality"].get(), 0),
                "ForceBlueprint": rv["ForceBlueprint"].get(),
                "Amount":        self._safe_int(rv["Amount"].get(), 1),
                "Blueprint":     rv["Blueprint"].get(),
            }
            for rv in self._arkshop_kit_items_rows
        ]
        existing["Dinos"] = [
            {
                "Level":          self._safe_int(rv["Level"].get(), 1),
                "Gender":         rv["Gender"].get(),
                "Blueprint":      rv["Blueprint"].get(),
                "SaddleBlueprint": rv["SaddleBlueprint"].get(),
            }
            for rv in self._arkshop_kit_dinos_rows
        ]
        existing["Commands"] = [
            {"Command": rv["Command"].get(), "ExecuteAsAdmin": rv["ExecuteAsAdmin"].get()}
            for rv in self._arkshop_kit_cmds_rows
        ]
        self._arkshop_mgr.set_kit(target_id, existing)
        if target_id != kit_id:
            self._arkshop_mgr.delete_kit(kit_id)
            self._arkshop_selected_kit_id = target_id
            self._arkshop_populate_kits()
        if not silent:
            messagebox.showinfo("ArkShop", f"Kit '{target_id}' atualizado!")

    def _arkshop_new_kit(self) -> None:
        from tkinter.simpledialog import askstring
        kit_id = askstring("Novo Kit", "ID do novo kit (sem espaços):")
        if not kit_id or not kit_id.strip():
            return
        kit_id = kit_id.strip()
        if kit_id in self._arkshop_mgr.kits:
            messagebox.showerror("ArkShop", f"Kit '{kit_id}' já existe.")
            return
        self._arkshop_mgr.set_kit(kit_id, {
            "DefaultAmount": 1, "Price": 0, "Description": "",
            "OnlyFromSpawn": False, "Permissions": [],
            "Items": [], "Dinos": [], "Commands": [],
        })
        self._arkshop_populate_kits()
        self._arkshop_select_kit(kit_id)

    def _arkshop_delete_current_kit(self) -> None:
        kit_id = self._arkshop_selected_kit_id
        if not kit_id:
            return
        if not messagebox.askyesno("Excluir Kit", f"Excluir o kit '{kit_id}'?"):
            return
        self._arkshop_mgr.delete_kit(kit_id)
        self._arkshop_selected_kit_id = None
        self._arkshop_kit_basic_vars = {}
        self._arkshop_kit_items_rows = []
        self._arkshop_kit_dinos_rows = []
        self._arkshop_kit_cmds_rows  = []
        for w in self._arkshop_kit_detail_outer.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._arkshop_kit_detail_outer,
                     text="← Selecione um kit na lista",
                     text_color="gray50", font=ctk.CTkFont(size=13),
                     ).place(relx=0.5, rely=0.5, anchor="center")
        self._arkshop_populate_kits()

    # ── Seleção e edição de Itens da Loja ────────────────────────────────────

    def _arkshop_select_shop_item(self, item_id: str) -> None:
        if self._arkshop_selected_shop_item_id and self._arkshop_selected_shop_item_id != item_id:
            self._arkshop_apply_shop_item_changes(silent=True)
        self._arkshop_selected_shop_item_id = item_id
        for w in self._arkshop_shop_detail_outer.winfo_children():
            w.destroy()
        detail = ctk.CTkScrollableFrame(self._arkshop_shop_detail_outer, fg_color="transparent")
        detail.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        detail.grid_columnconfigure(0, weight=1)
        self._arkshop_build_shop_item_detail(
            detail, item_id, self._arkshop_mgr.shop_items.get(item_id, {}))

    def _arkshop_build_shop_item_detail(self, parent: ctk.CTkScrollableFrame,
                                         item_id: str, item: dict) -> None:
        parent.grid_columnconfigure(0, weight=1)

        title_row = ctk.CTkFrame(parent, fg_color="transparent")
        title_row.grid(row=0, column=0, padx=12, pady=(10, 6), sticky="ew")
        title_row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(title_row, text=f"Item: {item_id}",
                     font=ctk.CTkFont(size=14, weight="bold")
                     ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(title_row, text="✔ Aplicar Alterações", width=155, height=30,
                      fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                      font=ctk.CTkFont(size=11),
                      command=lambda: self._arkshop_apply_shop_item_changes(),
                      ).grid(row=0, column=1, padx=(6, 0))
        ctk.CTkButton(title_row, text="🗑 Excluir Item", width=110, height=30,
                      fg_color="#5a1a1a", hover_color="#4a0a0a",
                      font=ctk.CTkFont(size=11),
                      command=self._arkshop_delete_current_shop_item,
                      ).grid(row=0, column=2, padx=(6, 0))

        # ── Campos básicos ──────────────────────────────────────────────────
        basic_f = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=8)
        basic_f.grid(row=1, column=0, padx=12, pady=(0, 8), sticky="ew")
        basic_f.grid_columnconfigure((1, 3), weight=1)

        ctk.CTkLabel(basic_f, text="Configurações do Item",
                     font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, columnspan=4, padx=12, pady=(8, 4), sticky="w")

        type_var  = tk.StringVar(value=str(item.get("Type", "item")))
        price_var = tk.StringVar(value=str(item.get("Price", 0)))
        desc_var  = tk.StringVar(value=str(item.get("Description", "")))

        ctk.CTkLabel(basic_f, text="Tipo (Type):", font=ctk.CTkFont(size=12)
                     ).grid(row=1, column=0, padx=(12, 4), pady=6, sticky="e")
        ctk.CTkEntry(basic_f, textvariable=type_var, width=120,
                     placeholder_text="item / dino / beacon"
                     ).grid(row=1, column=1, padx=(0, 12), pady=6, sticky="w")
        ctk.CTkLabel(basic_f, text="Preço:", font=ctk.CTkFont(size=12)
                     ).grid(row=1, column=2, padx=(12, 4), pady=6, sticky="e")
        ctk.CTkEntry(basic_f, textvariable=price_var, width=90
                     ).grid(row=1, column=3, padx=(0, 12), pady=6, sticky="ew")
        ctk.CTkLabel(basic_f, text="Descrição:", font=ctk.CTkFont(size=12)
                     ).grid(row=2, column=0, padx=(12, 4), pady=6, sticky="e")
        ctk.CTkEntry(basic_f, textvariable=desc_var
                     ).grid(row=2, column=1, columnspan=3, padx=(0, 12), pady=6, sticky="ew")

        self._arkshop_shop_basic_vars = {
            "Type": type_var, "Price": price_var, "Description": desc_var,
        }

        # ── Itens ───────────────────────────────────────────────────────────
        items_outer = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=8)
        items_outer.grid(row=2, column=0, padx=12, pady=(0, 10), sticky="ew")
        items_outer.grid_columnconfigure(0, weight=1)

        ih = ctk.CTkFrame(items_outer, fg_color="transparent")
        ih.grid(row=0, column=0, padx=10, pady=(8, 4), sticky="ew")
        ih.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(ih, text="Itens", font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(ih, text="+ Item", width=80, height=26,
                      fg_color="#2a4a2a", hover_color="#1e3a1e",
                      font=ctk.CTkFont(size=11),
                      command=lambda: self._arkshop_add_shop_item_row(self._arkshop_shop_items_frame),
                      ).grid(row=0, column=1)

        items_tbl = ctk.CTkFrame(items_outer, fg_color="#101020", corner_radius=6)
        items_tbl.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        items_tbl.grid_columnconfigure(3, weight=1)
        for c, h in enumerate(("Quality", "Force BP", "Qtd", "Blueprint")):
            ctk.CTkLabel(items_tbl, text=h, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="gray50"
                         ).grid(row=0, column=c, padx=(8 if c == 0 else 4, 4), pady=4, sticky="w")

        self._arkshop_shop_items_frame = items_tbl
        self._arkshop_shop_items_rows = []
        self._arkshop_shop_items_next_row = 1
        for item_data in item.get("Items", []):
            self._arkshop_add_shop_item_row(items_tbl, item_data)

        # ── Comandos ────────────────────────────────────────────────
        cmds_outer = ctk.CTkFrame(parent, fg_color="#1a1a2e", corner_radius=8)
        cmds_outer.grid(row=3, column=0, padx=12, pady=(0, 10), sticky="ew")
        cmds_outer.grid_columnconfigure(0, weight=1)

        ch = ctk.CTkFrame(cmds_outer, fg_color="transparent")
        ch.grid(row=0, column=0, padx=10, pady=(8, 4), sticky="ew")
        ch.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(ch, text="Comandos", font=ctk.CTkFont(size=12, weight="bold")
                     ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(ch, text="+ Comando", width=95, height=26,
                      fg_color="#2a4a2a", hover_color="#1e3a1e",
                      font=ctk.CTkFont(size=11),
                      command=lambda: self._arkshop_add_shop_cmd_row(self._arkshop_shop_cmds_frame),
                      ).grid(row=0, column=1)

        cmds_tbl = ctk.CTkFrame(cmds_outer, fg_color="#101020", corner_radius=6)
        cmds_tbl.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        cmds_tbl.grid_columnconfigure(0, weight=1)
        for c, h in enumerate(("Comando", "Admin")):
            ctk.CTkLabel(cmds_tbl, text=h, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="gray50"
                         ).grid(row=0, column=c, padx=(8 if c == 0 else 4, 4), pady=4, sticky="w")

        self._arkshop_shop_cmds_frame = cmds_tbl
        self._arkshop_shop_cmds_rows = []
        self._arkshop_shop_cmds_next_row = 1
        for cmd_data in item.get("Commands", []):
            self._arkshop_add_shop_cmd_row(cmds_tbl, cmd_data)

    def _arkshop_add_shop_item_row(self,
                                    container: ctk.CTkFrame,
                                    data: Optional[dict] = None) -> None:
        data = data or {}
        rv = {
            "Quality":        tk.StringVar(value=str(data.get("Quality", 0))),
            "ForceBlueprint": tk.BooleanVar(value=bool(data.get("ForceBlueprint", False))),
            "Amount":         tk.StringVar(value=str(data.get("Amount", 1))),
            "Blueprint":      tk.StringVar(value=str(data.get("Blueprint", ""))),
        }
        self._arkshop_shop_items_rows.append(rv)
        self._arkshop_grid_shop_item_row(container, self._arkshop_shop_items_next_row, rv)
        self._arkshop_shop_items_next_row += 1

    def _arkshop_grid_shop_item_row(self, container: ctk.CTkFrame,
                                     row_i: int, rv: dict) -> None:
        ctk.CTkEntry(container, textvariable=rv["Quality"], width=60
                     ).grid(row=row_i, column=0, padx=(8, 4), pady=3)
        ctk.CTkCheckBox(container, text="", variable=rv["ForceBlueprint"],
                        width=30, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                        checkmark_color="#ffffff"
                        ).grid(row=row_i, column=1, padx=4, pady=3)
        ctk.CTkEntry(container, textvariable=rv["Amount"], width=52
                     ).grid(row=row_i, column=2, padx=4, pady=3)
        _bp_frm = ctk.CTkFrame(container, fg_color="transparent")
        _bp_frm.grid(row=row_i, column=3, padx=4, pady=3, sticky="ew")
        _bp_frm.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(_bp_frm, textvariable=rv["Blueprint"],
                     font=ctk.CTkFont(size=11), placeholder_text="Blueprint'..."
                     ).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(
            _bp_frm, text="🔍", width=28, height=26,
            fg_color="#1e3a5f", hover_color="#2a5285",
            font=ctk.CTkFont(size=11),
            command=lambda v=rv["Blueprint"]: self._open_blueprint_picker(
                on_select=lambda bp, _v=v: _v.set(f"Blueprint'{bp['path']}'"),
                category="items",
            ),
        ).grid(row=0, column=1, padx=(4, 0))
        ctk.CTkButton(container, text="✕", width=26, height=26,
                      fg_color="#5a2a2a", hover_color="#4a1a1a",
                      font=ctk.CTkFont(size=10),
                      command=lambda r=rv: self._arkshop_remove_shop_item_row(r),
                      ).grid(row=row_i, column=4, padx=(4, 8), pady=3)

    def _arkshop_remove_shop_item_row(self, rv: dict) -> None:
        if rv in self._arkshop_shop_items_rows:
            self._arkshop_shop_items_rows.remove(rv)
        self._arkshop_refresh_table(
            self._arkshop_shop_items_frame,
            self._arkshop_shop_items_rows,
            self._arkshop_grid_shop_item_row,
        )
        self._arkshop_shop_items_next_row = len(self._arkshop_shop_items_rows) + 1

    # ── Row helpers: Shop Commands ────────────────────────────────────────

    def _arkshop_add_shop_cmd_row(self,
                                   container: ctk.CTkFrame,
                                   data: Optional[dict] = None) -> None:
        data = data or {}
        rv = {
            "Command":        tk.StringVar(value=str(data.get("Command", ""))),
            "ExecuteAsAdmin": tk.BooleanVar(value=bool(data.get("ExecuteAsAdmin", False))),
        }
        self._arkshop_shop_cmds_rows.append(rv)
        self._arkshop_grid_shop_cmd_row(container, self._arkshop_shop_cmds_next_row, rv)
        self._arkshop_shop_cmds_next_row += 1

    def _arkshop_grid_shop_cmd_row(self, container: ctk.CTkFrame,
                                    row_i: int, rv: dict) -> None:
        ctk.CTkEntry(container, textvariable=rv["Command"],
                     font=ctk.CTkFont(size=11), placeholder_text="cheat command..."
                     ).grid(row=row_i, column=0, padx=(8, 4), pady=3, sticky="ew")
        ctk.CTkCheckBox(container, text="Admin", variable=rv["ExecuteAsAdmin"],
                        width=80, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                        checkmark_color="#ffffff", font=ctk.CTkFont(size=11),
                        ).grid(row=row_i, column=1, padx=4, pady=3)
        ctk.CTkButton(container, text="✕", width=26, height=26,
                      fg_color="#5a2a2a", hover_color="#4a1a1a",
                      font=ctk.CTkFont(size=10),
                      command=lambda r=rv: self._arkshop_remove_shop_cmd_row(r),
                      ).grid(row=row_i, column=2, padx=(4, 8), pady=3)

    def _arkshop_remove_shop_cmd_row(self, rv: dict) -> None:
        if rv in self._arkshop_shop_cmds_rows:
            self._arkshop_shop_cmds_rows.remove(rv)
        self._arkshop_refresh_table(
            self._arkshop_shop_cmds_frame,
            self._arkshop_shop_cmds_rows,
            self._arkshop_grid_shop_cmd_row,
        )
        self._arkshop_shop_cmds_next_row = len(self._arkshop_shop_cmds_rows) + 1

    # ── Blueprint Picker (Beacon) ────────────────────────────────────────────

    def _open_blueprint_picker(
        self,
        on_select: Callable,
        category: str = "all",
        title: str = "Buscar Blueprint Beacon",
    ) -> None:
        """Abre diálogo de pesquisa de blueprints via API Beacon."""
        client = get_beacon_client()

        dlg = ctk.CTkToplevel(self)
        dlg.title(title)
        dlg.geometry("640x600")
        dlg.resizable(True, True)
        dlg.grab_set()
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(3, weight=1)

        # ── Cabeçalho ────────────────────────────────────────────────────────
        ctk.CTkLabel(
            dlg, text=f"🔍  {title}",
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))

        # ── Linha de controles: filtro de categoria + busca ───────────────────
        ctrl_frame = ctk.CTkFrame(dlg, fg_color="transparent")
        ctrl_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 4))
        ctrl_frame.grid_columnconfigure(3, weight=1)

        cat_var = tk.StringVar(value=category)
        for col, (text, val) in enumerate([
            ("Todos", "all"), ("Itens", "items"), ("Criaturas", "creatures")
        ]):
            ctk.CTkRadioButton(
                ctrl_frame, text=text, variable=cat_var, value=val,
                fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            ).grid(row=0, column=col, padx=(0, 10), pady=4, sticky="w")

        search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(
            ctrl_frame, textvariable=search_var,
            placeholder_text="Pesquisar nome ou classString...",
        )
        search_entry.grid(row=0, column=3, sticky="ew", padx=(8, 0))

        # ── Status ───────────────────────────────────────────────────────────
        status_lbl = ctk.CTkLabel(
            dlg, text="", font=ctk.CTkFont(size=11),
            text_color="gray", anchor="w",
        )
        status_lbl.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 2))

        # ── Lista de resultados ───────────────────────────────────────────────
        results_frame = ctk.CTkScrollableFrame(dlg, fg_color=_CARD_BG)
        results_frame.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 16))
        results_frame.grid_columnconfigure(0, weight=1)

        # ── Rodapé com botão de carga ─────────────────────────────────────────
        footer = ctk.CTkFrame(dlg, fg_color="transparent")
        footer.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 12))

        load_btn = ctk.CTkButton(
            footer, text="⬇  Carregar Blueprints Beacon",
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        )
        load_btn.pack(side="left")

        # ── Painel de auth (criado sempre; mostrado/ocultado conforme estado) ─
        auth_frame = ctk.CTkFrame(footer, fg_color="transparent")
        # pack_forget() por padrão; mostrado quando necessário

        connect_btn = ctk.CTkButton(
            auth_frame,
            text="🔑  Conectar com Beacon",
            fg_color="#3a3a1a", hover_color="#5a5a28",
        )
        connect_btn.pack(side="left", padx=(0, 10))

        code_lbl = ctk.CTkLabel(
            auth_frame, text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#f0d060",
        )
        code_lbl.pack(side="left")

        copy_btn = ctk.CTkButton(
            auth_frame, text="📋 Copiar", width=76,
            fg_color="#3a3a3a", hover_color="#505050",
        )

        def _show_auth_panel(btn_text: str = "🔑  Conectar com Beacon") -> None:
            connect_btn.configure(state="normal", text=btn_text)
            code_lbl.configure(text="")
            copy_btn.pack_forget()
            load_btn.configure(state="disabled")
            auth_frame.pack(side="left", fill="x", expand=True, padx=(10, 0))

        def _hide_auth_panel() -> None:
            auth_frame.pack_forget()

        def _start_auth() -> None:
            connect_btn.configure(state="disabled", text="🔑  Aguardando...")
            status_lbl.configure(
                text="Iniciando autenticação Beacon...", text_color="gray"
            )

            def _on_code(user_code: str, url: str) -> None:
                def _ui() -> None:
                    code_lbl.configure(text=user_code)
                    copy_btn.configure(
                        command=lambda: (
                            dlg.clipboard_clear(),
                            dlg.clipboard_append(user_code),
                        )
                    )
                    copy_btn.pack(side="left", padx=(6, 0))
                    status_lbl.configure(
                        text=f"Autorize em: {url}   (o navegador foi aberto automaticamente)",
                        text_color="gray",
                    )
                dlg.after(0, _ui)

            def _on_success() -> None:
                def _ui() -> None:
                    _hide_auth_panel()
                    status_lbl.configure(
                        text="Autenticado! Carregando blueprints...",
                        text_color="#60c060",
                    )
                    load_btn.configure(state="normal")
                    _do_load()
                dlg.after(0, _ui)

            def _on_error(msg: str) -> None:
                def _ui() -> None:
                    connect_btn.configure(
                        state="normal", text="🔑  Tentar novamente"
                    )
                    status_lbl.configure(
                        text=f"Erro na autenticação: {msg}",
                        text_color="#e05050",
                    )
                dlg.after(0, _ui)

            client.authenticate_async(_on_code, _on_success, _on_error)

        connect_btn.configure(command=_start_auth)

        # ── Funções internas ─────────────────────────────────────────────────

        def _populate(blueprints: list) -> None:
            for w in results_frame.winfo_children():
                w.destroy()
            if not blueprints:
                ctk.CTkLabel(
                    results_frame,
                    text="Nenhum resultado encontrado.",
                    text_color="gray",
                ).pack(pady=12)
                return
            for i, bp in enumerate(blueprints):
                row_bg = "#2b2b2b" if i % 2 == 0 else "#252525"
                row_frm = ctk.CTkFrame(results_frame, fg_color=row_bg, corner_radius=5)
                row_frm.grid(row=i, column=0, sticky="ew", padx=2, pady=2)
                row_frm.grid_columnconfigure(1, weight=1)

                # Badge de tipo
                if bp.get("creatureId"):
                    badge_text, badge_color = "🦕", "#1a3a5a"
                elif bp.get("engramId"):
                    badge_text, badge_color = "🎒", "#1a3a20"
                else:
                    badge_text, badge_color = "📦", "#3a3a3a"

                ctk.CTkLabel(
                    row_frm, text=badge_text,
                    font=ctk.CTkFont(size=13),
                    fg_color=badge_color, corner_radius=4, width=30,
                ).grid(row=0, column=0, rowspan=2, padx=(8, 6), pady=5, sticky="ns")

                ctk.CTkLabel(
                    row_frm, text=bp.get("label", "?"),
                    font=ctk.CTkFont(size=12, weight="bold"),
                    anchor="w",
                ).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(5, 0))

                ctk.CTkLabel(
                    row_frm,
                    text=bp.get("classString", ""),
                    font=ctk.CTkFont(size=10),
                    text_color="gray",
                    anchor="w",
                ).grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 5))

                def _on_click(event=None, _bp=bp) -> None:
                    on_select(_bp)
                    dlg.destroy()

                row_frm.bind("<Button-1>", _on_click)
                for child in row_frm.winfo_children():
                    child.bind("<Button-1>", _on_click)

        def _refresh(*_args) -> None:
            if not client.is_loaded():
                return
            results = client.search(search_var.get(), category=cat_var.get())
            status_lbl.configure(
                text=f"{len(results)} resultado(s)   "
                     f"{'(limitado a 150)' if len(results) == 150 else ''}",
                text_color="gray",
            )
            _populate(results)

        search_var.trace_add("write", _refresh)
        cat_var.trace_add("write", _refresh)

        def _do_load() -> None:
            load_btn.configure(state="disabled", text="Carregando...")
            status_lbl.configure(text="Conectando à API Beacon...", text_color="gray")

            def _worker() -> None:
                try:
                    client.ensure_loaded(
                        on_progress=lambda p, t: dlg.after(
                            0,
                            lambda _p=p, _t=t: status_lbl.configure(
                                text=f"Carregando... página {_p}/{_t}",
                                text_color="gray",
                            ),
                        )
                    )
                    dlg.after(0, _on_loaded)
                except Exception as exc:
                    is_token_err = any(
                        k in str(exc).lower()
                        for k in ("token", "autentic", "auth", "expirad")
                    )
                    def _on_err(_e=exc, _tok=is_token_err) -> None:
                        status_lbl.configure(
                            text=f"Erro: {_e}", text_color="#e05050"
                        )
                        if _tok:
                            _show_auth_panel("🔑  Reconectar com Beacon")
                        else:
                            load_btn.configure(
                                state="normal", text="⬇  Carregar Blueprints Beacon"
                            )
                    dlg.after(0, _on_err)

            threading.Thread(target=_worker, daemon=True).start()

        def _on_loaded() -> None:
            load_btn.configure(state="disabled", text="✔  Carregado")
            _refresh()
            search_entry.focus_set()

        load_btn.configure(command=_do_load)

        # ── Verificar autenticação e decidir estado inicial ───────────────────
        if client.is_loaded():
            # já tem tudo — mostrar resultados direto
            _hide_auth_panel()
            load_btn.configure(state="disabled", text="✔  Carregado")
            _refresh()
            search_entry.focus_set()
        elif client.is_authenticated():
            # token válido, blueprints não carregados ainda
            _hide_auth_panel()
            status_lbl.configure(
                text="Blueprints não carregados. Clique em 'Carregar' para buscar via API."
            )
        else:
            # sem token → mostrar painel de autenticação
            _show_auth_panel()
            status_lbl.configure(
                text="Token não encontrado. Clique em 'Conectar com Beacon' para autenticar.",
                text_color="#e0a030",
            )

    # ── Apply / New / Delete ShopItem ────────────────────────────────────────

    def _arkshop_apply_shop_item_changes(self, silent: bool = False) -> None:
        item_id = self._arkshop_selected_shop_item_id
        if not item_id or not self._arkshop_shop_basic_vars:
            return
        existing = dict(self._arkshop_mgr.shop_items.get(item_id, {}))
        bv = self._arkshop_shop_basic_vars
        existing["Type"]        = bv["Type"].get()
        existing["Description"] = bv["Description"].get()
        try:
            existing["Price"] = int(bv["Price"].get())
        except ValueError:
            pass
        existing["Items"] = [
            {
                "Quality":        self._safe_int(rv["Quality"].get(), 0),
                "ForceBlueprint": rv["ForceBlueprint"].get(),
                "Amount":         self._safe_int(rv["Amount"].get(), 1),
                "Blueprint":      rv["Blueprint"].get(),
            }
            for rv in self._arkshop_shop_items_rows
        ]
        cmds = [
            {
                "Command":        rv["Command"].get(),
                "ExecuteAsAdmin": rv["ExecuteAsAdmin"].get(),
            }
            for rv in self._arkshop_shop_cmds_rows
            if rv["Command"].get().strip()
        ]
        if cmds:
            existing["Commands"] = cmds
        elif "Commands" in existing:
            del existing["Commands"]
        self._arkshop_mgr.set_shop_item(item_id, existing)
        if not silent:
            messagebox.showinfo("ArkShop", f"Item '{item_id}' atualizado!")

    def _arkshop_new_shop_item(self) -> None:
        from tkinter.simpledialog import askstring
        item_id = askstring("Novo Item", "ID do novo item (sem espaços):")
        if not item_id or not item_id.strip():
            return
        item_id = item_id.strip()
        if item_id in self._arkshop_mgr.shop_items:
            messagebox.showerror("ArkShop", f"Item '{item_id}' já existe.")
            return
        self._arkshop_mgr.set_shop_item(item_id, {
            "Type": "item", "Description": "", "Price": 0, "Items": [],
        })
        self._arkshop_populate_shop()
        self._arkshop_select_shop_item(item_id)

    def _arkshop_delete_current_shop_item(self) -> None:
        item_id = self._arkshop_selected_shop_item_id
        if not item_id:
            return
        if not messagebox.askyesno("Excluir Item", f"Excluir o item '{item_id}'?"):
            return
        self._arkshop_mgr.delete_shop_item(item_id)
        self._arkshop_selected_shop_item_id = None
        self._arkshop_shop_basic_vars = {}
        self._arkshop_shop_items_rows = []
        self._arkshop_shop_cmds_rows = []
        for w in self._arkshop_shop_detail_outer.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._arkshop_shop_detail_outer,
                     text="← Selecione um item na lista",
                     text_color="gray50", font=ctk.CTkFont(size=13),
                     ).place(relx=0.5, rely=0.5, anchor="center")
        self._arkshop_populate_shop()

    # ── Utilitário safe_int ──────────────────────────────────────────────────

    @staticmethod
    def _safe_int(value: str, default: int = 0) -> int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def _arkshop_build_tab_messages(self) -> None:
        tab = self._arkshop_tabs.tab("Mensagens")
        tab.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            tab, text="Mensagens do Plugin",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, padx=14, pady=(10, 4), sticky="w")
        ctk.CTkLabel(
            tab, text="Todas as strings de texto exibidas pelo ArkShop no jogo.",
            font=ctk.CTkFont(size=11), text_color="gray55",
        ).grid(row=1, column=0, padx=14, pady=(0, 8), sticky="w")

        self._arkshop_msg_scroll = ctk.CTkScrollableFrame(tab, fg_color="#101020",
                                                          corner_radius=8, height=420)
        self._arkshop_msg_scroll.grid(row=2, column=0, padx=12, pady=(0, 8), sticky="ew")
        self._arkshop_msg_scroll.grid_columnconfigure(0, weight=0)
        self._arkshop_msg_scroll.grid_columnconfigure(1, weight=1)

        self._arkshop_msg_vars: Dict[str, tk.StringVar] = {}

    def _arkshop_build_tab_json(self) -> None:
        tab = self._arkshop_tabs.tab("Editor JSON")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            tab, text="Editor JSON Completo",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, padx=14, pady=(10, 2), sticky="w")
        ctk.CTkLabel(
            tab, text="Edite o JSON diretamente. Ao salvar, este conteúdo substitui o arquivo.",
            font=ctk.CTkFont(size=11), text_color="gray55",
        ).grid(row=1, column=0, padx=14, pady=(0, 6), sticky="w")

        self._arkshop_json_editor = ctk.CTkTextbox(
            tab, font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#0d0d1a", text_color="#e8e8f8",
            wrap="none", height=460,
        )
        self._arkshop_json_editor.grid(row=2, column=0, padx=12, pady=(0, 8), sticky="nsew")

        btn_row = ctk.CTkFrame(tab, fg_color="transparent")
        btn_row.grid(row=3, column=0, padx=12, pady=(0, 8), sticky="ew")
        btn_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_row, text="↩  Recarregar do Arquivo", height=34,
            fg_color="#2a3a4a", hover_color="#1e2e3a",
            font=ctk.CTkFont(size=12),
            command=self._arkshop_reload_json_editor,
        ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

        ctk.CTkButton(
            btn_row, text="↺  Sincronizar Campos → JSON", height=34,
            fg_color="#2a3a4a", hover_color="#1e2e3a",
            font=ctk.CTkFont(size=12),
            command=self._arkshop_sync_fields_to_json,
        ).grid(row=0, column=1, padx=(6, 0), sticky="ew")

    # ── Lógica de arquivo / sincronização ─────────────────────────────────────

    def _arkshop_browse(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecionar config.json do ArkShop",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )
        if path:
            self._arkshop_path_var.set(path)

    def _arkshop_load(self) -> None:
        path = self._arkshop_path_var.get().strip()
        if not path:
            messagebox.showwarning("ArkShop", "Informe o caminho do arquivo config.json.")
            return
        try:
            self._arkshop_mgr.load(path)
            self._arkshop_populate_all()
            self._arkshop_status_var.set(f"✔ Carregado: {path}")
        except FileNotFoundError:
            messagebox.showerror("ArkShop", f"Arquivo não encontrado:\n{path}")
        except json.JSONDecodeError as exc:
            messagebox.showerror("ArkShop", f"JSON inválido:\n{exc}")
        except Exception as exc:
            messagebox.showerror("ArkShop", f"Erro ao carregar:\n{exc}")

    def _arkshop_save(self) -> None:
        path = self._arkshop_path_var.get().strip()
        if not path:
            messagebox.showwarning("ArkShop", "Informe o caminho do arquivo config.json.")
            return
        if not self._arkshop_mgr.is_loaded:
            messagebox.showwarning("ArkShop", "Carregue um arquivo primeiro.")
            return

        # Sincroniza UI → manager → editor antes de salvar
        self._arkshop_collect_fields()
        self._arkshop_reload_json_editor()

        raw = self._arkshop_json_editor.get("1.0", "end").strip()
        try:
            json.loads(raw)
        except json.JSONDecodeError as exc:
            messagebox.showerror("ArkShop", f"JSON inválido:\n{exc}")
            return

        targets = [path] + [
            v.get().strip()
            for v, _ in self._arkshop_extra_target_vars
            if v.get().strip()
        ]
        errors: List[str] = []
        for t in targets:
            try:
                self._arkshop_mgr.save_raw(raw, t)
            except Exception as exc:
                errors.append(f"{t}: {exc}")

        if errors:
            messagebox.showerror("ArkShop", "Erros ao salvar:\n" + "\n".join(errors))
        else:
            count = len(targets)
            self._arkshop_status_var.set(f"✔ Salvo em {count} arquivo(s).")
            messagebox.showinfo("ArkShop", f"Salvo com sucesso em {count} arquivo(s)!")

    # ── Presets & múltiplos alvos ─────────────────────────────────────────────

    def _arkshop_presets_path(self) -> Path:
        data_dir = Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "arkshop_presets.json"

    def _arkshop_load_presets_file(self) -> None:
        """Carrega presets do disco e popula o menu. Chamado no startup."""
        p = self._arkshop_presets_path()
        if p.exists():
            try:
                with open(p, encoding="utf-8") as fh:
                    self._arkshop_presets = json.load(fh)
            except Exception:
                self._arkshop_presets = {}
        self._arkshop_refresh_preset_menu()

    def _arkshop_save_presets_file(self) -> None:
        p = self._arkshop_presets_path()
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(self._arkshop_presets, fh, indent=2, ensure_ascii=False)

    def _arkshop_refresh_preset_menu(self) -> None:
        names = sorted(self._arkshop_presets.keys())
        if not names:
            names = ["(nenhum preset)"]
        self._arkshop_preset_menu.configure(values=names)
        if self._arkshop_preset_var.get() not in names:
            self._arkshop_preset_var.set(names[0])

    def _arkshop_save_preset(self) -> None:
        if not self._arkshop_mgr.is_loaded:
            messagebox.showwarning("ArkShop", "Carregue um arquivo antes de salvar um preset.")
            return
        from tkinter.simpledialog import askstring
        name = askstring("Salvar Preset", "Nome do preset:", parent=self)
        if not name or not name.strip():
            return
        name = name.strip()
        self._arkshop_collect_fields()
        self._arkshop_presets[name] = {
            "config": json.loads(self._arkshop_mgr.to_json_str()),
            "extra_targets": [v.get() for v, _ in self._arkshop_extra_target_vars],
        }
        self._arkshop_save_presets_file()
        self._arkshop_refresh_preset_menu()
        self._arkshop_preset_var.set(name)
        messagebox.showinfo("ArkShop", f"Preset '{name}' salvo!")

    def _arkshop_load_preset(self) -> None:
        name = self._arkshop_preset_var.get()
        if name not in self._arkshop_presets:
            messagebox.showwarning("ArkShop", "Selecione um preset válido.")
            return
        preset = self._arkshop_presets[name]
        self._arkshop_mgr.load_data(preset["config"])
        self._arkshop_populate_all()
        # restaurar alvos extras
        for _, frm in list(self._arkshop_extra_target_vars):
            frm.destroy()
        self._arkshop_extra_target_vars.clear()
        for path in preset.get("extra_targets", []):
            self._arkshop_add_extra_target(path)
        self._arkshop_status_var.set(f"✔ Preset '{name}' carregado.")

    def _arkshop_delete_preset(self) -> None:
        name = self._arkshop_preset_var.get()
        if name not in self._arkshop_presets:
            return
        if not messagebox.askyesno("ArkShop", f"Excluir preset '{name}'?", parent=self):
            return
        del self._arkshop_presets[name]
        self._arkshop_save_presets_file()
        self._arkshop_refresh_preset_menu()

    def _arkshop_add_extra_target(self, path: str = "") -> None:
        idx = len(self._arkshop_extra_target_vars)
        row_frm = ctk.CTkFrame(self._arkshop_extra_targets_frame, fg_color="transparent")
        row_frm.grid(row=idx, column=0, sticky="ew", pady=2)
        row_frm.grid_columnconfigure(1, weight=1)

        var = tk.StringVar(value=path)
        ctk.CTkLabel(row_frm, text=f"#{idx + 1}", width=28,
                     font=ctk.CTkFont(size=11), text_color="gray55",
                     ).grid(row=0, column=0, padx=(0, 4))
        ctk.CTkEntry(row_frm, textvariable=var,
                     placeholder_text="Caminho para config.json...",
                     ).grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(row_frm, text="📁", width=30, height=28,
                      fg_color="#252540", hover_color="#1a1a30",
                      command=lambda v=var: self._arkshop_browse_extra(v),
                      ).grid(row=0, column=2, padx=(4, 2))
        ctk.CTkButton(row_frm, text="✕", width=28, height=28,
                      fg_color="#5a1a1a", hover_color="#4a0a0a",
                      command=lambda frm=row_frm, v=var: self._arkshop_remove_extra_target(frm, v),
                      ).grid(row=0, column=3)
        self._arkshop_extra_target_vars.append((var, row_frm))

    def _arkshop_browse_extra(self, var: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            title="Selecionar config.json adicional",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )
        if path:
            var.set(path)

    def _arkshop_remove_extra_target(self, frm: ctk.CTkFrame, var: tk.StringVar) -> None:
        self._arkshop_extra_target_vars = [
            (v, f) for v, f in self._arkshop_extra_target_vars if f is not frm
        ]
        frm.destroy()
        # renumerar labels
        for i, (_, f) in enumerate(self._arkshop_extra_target_vars):
            lbl = f.winfo_children()[0]
            if hasattr(lbl, "configure"):
                lbl.configure(text=f"#{i + 1}")  # type: ignore[union-attr]

    def _arkshop_reload_json_editor(self) -> None:
        if not self._arkshop_mgr.is_loaded:
            return
        self._arkshop_json_editor.delete("1.0", "end")
        self._arkshop_json_editor.insert("1.0", self._arkshop_mgr.to_json_str())

    def _arkshop_sync_fields_to_json(self) -> None:
        """Coleta os campos estruturados, atualiza _arkshop_mgr e sincroniza o editor."""
        if not self._arkshop_mgr.is_loaded:
            messagebox.showwarning("ArkShop", "Carregue um arquivo primeiro.")
            return
        self._arkshop_collect_fields()
        self._arkshop_reload_json_editor()

    def _arkshop_populate_all(self) -> None:
        """Popula todos os campos com dados de self._arkshop_mgr."""
        mgr = self._arkshop_mgr
        g = mgr.general
        m = mgr.mysql

        # ── Geral ──────────────────────────────────────────────────────────
        self._arkshop_items_page.set(str(g.get("ItemsPerPage", 15)))
        self._arkshop_display_time.set(str(g.get("ShopDisplayTime", 15.0)))
        self._arkshop_text_size.set(str(g.get("ShopTextSize", 1.3)))
        self._arkshop_db_override.set(g.get("DbPathOverride", ""))
        self._arkshop_default_kit.set(g.get("DefaultKit", ""))

        for key, _ in GENERAL_BOOL_LABELS:
            self._arkshop_bool_vars[key].set(bool(g.get(key, False)))

        # ── MySQL ──────────────────────────────────────────────────────────
        self._arkshop_use_mysql.set(bool(m.get("UseMysql", False)))
        self._arkshop_mysql_host.set(str(m.get("MysqlHost", "127.0.0.1")))
        self._arkshop_mysql_user.set(str(m.get("MysqlUser", "")))
        self._arkshop_mysql_pass.set(str(m.get("MysqlPass", "")))
        self._arkshop_mysql_db.set(str(m.get("MysqlDB", "arkshop")))
        self._arkshop_mysql_port.set(str(m.get("MysqlPort", 3306)))

        # ── Discord ──────────────────────────────────────────────────────
        disc = g.get("Discord", {})
        self._arkshop_discord_enabled.set(bool(disc.get("Enabled", False)))
        self._arkshop_discord_sendername.set(str(disc.get("SenderName", "ArkShop")))
        self._arkshop_discord_url.set(str(disc.get("URL", "")))

        # ── TimedPointsReward ────────────────────────────────────────────
        tpr = g.get("TimedPointsReward", {})
        self._arkshop_tpr_enabled.set(bool(tpr.get("Enabled", False)))
        self._arkshop_tpr_interval.set(str(tpr.get("Interval", 30)))
        self._arkshop_tpr_stack.set(bool(tpr.get("StackRewards", True)))

        # repopular linhas de grupos
        for child in self._arkshop_groups_frame.winfo_children():
            info = child.grid_info()
            if info.get("row", 0) == 0:
                continue
            child.destroy()
        self._arkshop_groups_rows.clear()
        self._arkshop_groups_next_row = 1

        for grp_name, grp_val in tpr.get("Groups", {}).items():
            amount = grp_val.get("Amount", 0) if isinstance(grp_val, dict) else grp_val
            self._arkshop_add_group_row(grp_name, str(amount))

        if not tpr.get("Groups"):
            self._arkshop_add_group_row()

        # ── Kits ──────────────────────────────────────────────────────────
        self._arkshop_populate_kits()

        # ── ShopItems ─────────────────────────────────────────────────────
        self._arkshop_populate_shop()

        # ── Messages ─────────────────────────────────────────────────────
        self._arkshop_populate_messages()

        # ── JSON editor ──────────────────────────────────────────────────
        self._arkshop_reload_json_editor()

    def _arkshop_populate_kits(self) -> None:
        for w in self._arkshop_kits_list.winfo_children():
            w.destroy()
        for kit_id, kit in self._arkshop_mgr.kits.items():
            desc = kit.get("Description", "")
            label = f"{kit_id}" + (f"  —  {desc}" if desc else "")
            btn = ctk.CTkButton(
                self._arkshop_kits_list,
                text=label, anchor="w", height=34,
                corner_radius=6, fg_color="transparent",
                text_color="#d8d8e8", hover_color="#252540",
                font=ctk.CTkFont(size=12),
                command=lambda k=kit_id: self._arkshop_select_kit(k),
            )
            btn.pack(fill="x", pady=2, padx=4)

    def _arkshop_populate_shop(self) -> None:
        for w in self._arkshop_shop_list.winfo_children():
            w.destroy()
        for item_id, item in self._arkshop_mgr.shop_items.items():
            desc = item.get("Description", "")
            label = f"{item_id}" + (f"  —  {desc}" if desc else "")
            btn = ctk.CTkButton(
                self._arkshop_shop_list,
                text=label, anchor="w", height=34,
                corner_radius=6, fg_color="transparent",
                text_color="#d8d8e8", hover_color="#252540",
                font=ctk.CTkFont(size=12),
                command=lambda i=item_id: self._arkshop_select_shop_item(i),
            )
            btn.pack(fill="x", pady=2, padx=4)

    def _arkshop_populate_messages(self) -> None:
        scroll = self._arkshop_msg_scroll
        for w in scroll.winfo_children():
            w.destroy()
        self._arkshop_msg_vars.clear()

        for row_i, (msg_key, msg_val) in enumerate(self._arkshop_mgr.messages.items()):
            var = tk.StringVar(value=str(msg_val))
            self._arkshop_msg_vars[msg_key] = var

            ctk.CTkLabel(scroll, text=msg_key, font=ctk.CTkFont(size=11),
                         text_color="gray60", anchor="e",
                         ).grid(row=row_i, column=0, padx=(10, 6), pady=3, sticky="e")
            ctk.CTkEntry(scroll, textvariable=var, font=ctk.CTkFont(size=11),
                         ).grid(row=row_i, column=1, padx=(0, 10), pady=3, sticky="ew")

    def _arkshop_collect_fields(self) -> None:
        """Lê todos os campos e atualiza self._arkshop_mgr._data."""
        mgr = self._arkshop_mgr

        # ── MySQL ──────────────────────────────────────────────────────────
        try:
            port = int(self._arkshop_mysql_port.get())
        except ValueError:
            port = 3306
        mgr.set_section(self._arkshop_use_mysql.get(), "Mysql", "UseMysql")
        mgr.set_section(self._arkshop_mysql_host.get(), "Mysql", "MysqlHost")
        mgr.set_section(self._arkshop_mysql_user.get(), "Mysql", "MysqlUser")
        mgr.set_section(self._arkshop_mysql_pass.get(), "Mysql", "MysqlPass")
        mgr.set_section(self._arkshop_mysql_db.get(), "Mysql", "MysqlDB")
        mgr.set_section(port, "Mysql", "MysqlPort")

        # ── Discord ────────────────────────────────────────────────────────
        mgr.set_section(self._arkshop_discord_enabled.get(),    "General", "Discord", "Enabled")
        mgr.set_section(self._arkshop_discord_sendername.get(), "General", "Discord", "SenderName")
        mgr.set_section(self._arkshop_discord_url.get(),        "General", "Discord", "URL")

        # ── TimedPointsReward ──────────────────────────────────────────────
        try:
            interval = int(self._arkshop_tpr_interval.get())
        except ValueError:
            interval = 30
        mgr.set_section(self._arkshop_tpr_enabled.get(), "General", "TimedPointsReward", "Enabled")
        mgr.set_section(interval,                        "General", "TimedPointsReward", "Interval")
        mgr.set_section(self._arkshop_tpr_stack.get(),   "General", "TimedPointsReward", "StackRewards")

        groups: Dict[str, Dict[str, int]] = {}
        for name_var, amount_var in self._arkshop_groups_rows:
            grp_name = name_var.get().strip()
            if grp_name:
                try:
                    amt = int(amount_var.get())
                except ValueError:
                    amt = 0
                groups[grp_name] = {"Amount": amt}
        mgr.set_timed_groups(groups)

        # ── General scalar ────────────────────────────────────────────────
        try:
            items_page = int(self._arkshop_items_page.get())
        except ValueError:
            items_page = 15
        try:
            disp_time = float(self._arkshop_display_time.get())
        except ValueError:
            disp_time = 15.0
        try:
            text_size = float(self._arkshop_text_size.get())
        except ValueError:
            text_size = 1.3

        mgr.set_general("ItemsPerPage", items_page)
        mgr.set_general("ShopDisplayTime", disp_time)
        mgr.set_general("ShopTextSize", text_size)
        mgr.set_general("DbPathOverride", self._arkshop_db_override.get())
        mgr.set_general("DefaultKit", self._arkshop_default_kit.get())

        for key, _ in GENERAL_BOOL_LABELS:
            mgr.set_general(key, self._arkshop_bool_vars[key].get())

        # ── Kit atual (se editado) ─────────────────────────────────────
        self._arkshop_apply_kit_changes(silent=True)

        # ── Item da loja atual (se editado) ──────────────────────────────
        self._arkshop_apply_shop_item_changes(silent=True)

        # ── Messages ─────────────────────────────────────────────────────
        for msg_key, var in self._arkshop_msg_vars.items():
            mgr.set_message(msg_key, var.get())

    # ══════════════════════════════════════════════════════════════════════════
    # Painel de Desempenho
    # ══════════════════════════════════════════════════════════════════════════

    def _build_performance_panel(self, parent) -> None:
        parent.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(parent, text="Desempenho do Sistema",
                     font=ctk.CTkFont(size=24, weight="bold")).grid(
            row=0, column=0, padx=24, pady=(24, 2), sticky="w")
        ctk.CTkLabel(parent, text="Monitoramento em tempo real dos recursos desta máquina.",
                     text_color="gray60").grid(row=1, column=0, padx=24, pady=(0, 18), sticky="w")

        cards = ctk.CTkFrame(parent, fg_color="transparent")
        cards.grid(row=2, column=0, padx=16, pady=0, sticky="ew")
        cards.grid_columnconfigure((0, 1, 2), weight=1)

        # ── CPU ───────────────────────────────────────────────────────────────
        cpu_card = ctk.CTkFrame(cards, corner_radius=12, fg_color=_CARD_BG)
        cpu_card.grid(row=0, column=0, padx=6, pady=6, sticky="nsew")
        cpu_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(cpu_card, text="🖥  CPU",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#88d4a0").grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        self._perf_cpu_pct_var = tk.StringVar(value="—")
        ctk.CTkLabel(cpu_card, textvariable=self._perf_cpu_pct_var,
                     font=ctk.CTkFont(size=32, weight="bold"),
                     text_color=_GREEN).grid(row=1, column=0, padx=16, pady=(0, 4), sticky="w")

        self._perf_cpu_bar = ctk.CTkProgressBar(cpu_card, height=8, corner_radius=4,
                                                 progress_color=_GREEN)
        self._perf_cpu_bar.set(0)
        self._perf_cpu_bar.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")

        cpu_name = platform.processor() or "Processador"
        ctk.CTkLabel(cpu_card, text=cpu_name, font=ctk.CTkFont(size=10),
                     text_color="gray55", wraplength=230, justify="left").grid(
            row=3, column=0, padx=16, pady=(0, 4), sticky="w")

        self._perf_cpu_info_var = tk.StringVar(value="Aguardando...")
        ctk.CTkLabel(cpu_card, textvariable=self._perf_cpu_info_var,
                     font=ctk.CTkFont(size=11), text_color="gray60").grid(
            row=4, column=0, padx=16, pady=(0, 16), sticky="w")

        # ── RAM ───────────────────────────────────────────────────────────────
        ram_card = ctk.CTkFrame(cards, corner_radius=12, fg_color=_CARD_BG)
        ram_card.grid(row=0, column=1, padx=6, pady=6, sticky="nsew")
        ram_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(ram_card, text="💾  RAM",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#88d4a0").grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        self._perf_ram_pct_var = tk.StringVar(value="—")
        ctk.CTkLabel(ram_card, textvariable=self._perf_ram_pct_var,
                     font=ctk.CTkFont(size=32, weight="bold"),
                     text_color=_GREEN).grid(row=1, column=0, padx=16, pady=(0, 4), sticky="w")

        self._perf_ram_bar = ctk.CTkProgressBar(ram_card, height=8, corner_radius=4,
                                                  progress_color=_GREEN)
        self._perf_ram_bar.set(0)
        self._perf_ram_bar.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")

        self._perf_ram_info_var = tk.StringVar(value="Aguardando...")
        ctk.CTkLabel(ram_card, textvariable=self._perf_ram_info_var,
                     font=ctk.CTkFont(size=11), text_color="gray60").grid(
            row=3, column=0, padx=16, pady=(0, 16), sticky="w")

        # ── GPU ───────────────────────────────────────────────────────────────
        gpu_card = ctk.CTkFrame(cards, corner_radius=12, fg_color=_CARD_BG)
        gpu_card.grid(row=0, column=2, padx=6, pady=6, sticky="nsew")
        gpu_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(gpu_card, text="🎮  GPU",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color="#88d4a0").grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        self._perf_gpu_pct_var = tk.StringVar(value="—")
        ctk.CTkLabel(gpu_card, textvariable=self._perf_gpu_pct_var,
                     font=ctk.CTkFont(size=32, weight="bold"),
                     text_color=_GREEN).grid(row=1, column=0, padx=16, pady=(0, 4), sticky="w")

        self._perf_gpu_bar = ctk.CTkProgressBar(gpu_card, height=8, corner_radius=4,
                                                  progress_color=_GREEN)
        self._perf_gpu_bar.set(0)
        self._perf_gpu_bar.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")

        self._perf_gpu_info_var = tk.StringVar(value="Coletando informações...")
        ctk.CTkLabel(gpu_card, textvariable=self._perf_gpu_info_var,
                     font=ctk.CTkFont(size=11), text_color="gray60",
                     wraplength=230, justify="left").grid(
            row=3, column=0, padx=16, pady=(0, 16), sticky="w")

        threading.Thread(target=self._collect_gpu_info, daemon=True,
                         name="gpu-info").start()

        # ── Seção de Pontos Críticos ─────────────────────────────────────────
        crit_outer = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        crit_outer.grid(row=3, column=0, padx=22, pady=(12, 16), sticky="ew")
        crit_outer.grid_columnconfigure(0, weight=1)

        crit_hdr = ctk.CTkFrame(crit_outer, fg_color="transparent")
        crit_hdr.grid(row=0, column=0, padx=16, pady=(14, 4), sticky="ew")
        crit_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            crit_hdr, text="⚠️  Pontos Críticos",
            font=ctk.CTkFont(size=14, weight="bold"), text_color="#fbbf24",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            crit_hdr, text="🗑 Limpar", width=90, height=28,
            fg_color="#3a1515", hover_color="#5a2020",
            font=ctk.CTkFont(size=11),
            command=self._clear_perf_critical_log,
        ).grid(row=0, column=1)

        thr_fr = ctk.CTkFrame(crit_outer, fg_color="transparent")
        thr_fr.grid(row=1, column=0, padx=16, pady=(0, 8), sticky="w")

        ctk.CTkLabel(thr_fr, text="Registrar quando:",
                     text_color="gray60", font=ctk.CTkFont(size=11)).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(thr_fr, text="Aviso ≥",
                     text_color="#ffaa44", font=ctk.CTkFont(size=11)).pack(side="left")
        warn_var = tk.StringVar(value="80")
        ctk.CTkEntry(thr_fr, textvariable=warn_var, width=48, height=26,
                     justify="center").pack(side="left", padx=(4, 2))
        ctk.CTkLabel(thr_fr, text="%     Crítico ≥",
                     text_color="#ff6666", font=ctk.CTkFont(size=11)).pack(side="left", padx=(4, 0))
        crit_var = tk.StringVar(value="90")
        ctk.CTkEntry(thr_fr, textvariable=crit_var, width=48, height=26,
                     justify="center").pack(side="left", padx=(4, 2))
        ctk.CTkLabel(thr_fr, text="%",
                     text_color="gray60", font=ctk.CTkFont(size=11)).pack(side="left")

        self._perf_alert_warn_var = warn_var
        self._perf_alert_crit_var = crit_var

        log_box = ctk.CTkTextbox(
            crit_outer, height=180, state="disabled",
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0d0d18", text_color="#c8c8d8", corner_radius=6,
        )
        log_box.grid(row=2, column=0, padx=16, pady=(0, 14), sticky="ew")
        self._perf_critical_log = log_box

    # ── Coleta estática de GPU ────────────────────────────────────────────────

    def _collect_gpu_info(self) -> None:
        import subprocess
        try:
            _NO_WINDOW = 0x08000000
            out = subprocess.check_output(
                ["wmic", "path", "Win32_VideoController",
                 "get", "Name,AdapterRAM", "/value"],
                creationflags=_NO_WINDOW,
                stderr=subprocess.DEVNULL,
                timeout=10,
            ).decode(errors="replace")

            gpus: list = []
            current: dict = {}
            for raw in out.splitlines():
                line = raw.strip()
                if not line:
                    if current:
                        gpus.append(current)
                        current = {}
                    continue
                if "=" in line:
                    key, _, val = line.partition("=")
                    current[key.strip()] = val.strip()
            if current:
                gpus.append(current)

            parts = []
            for g in gpus:
                name = g.get("Name", "").strip()
                if not name:
                    continue
                vram_raw = g.get("AdapterRAM", "0")
                try:
                    vram_mb = int(vram_raw) // (1024 * 1024)
                    vram_str = f"{vram_mb:,} MB VRAM" if vram_mb > 0 else ""
                except ValueError:
                    vram_str = ""
                parts.append(f"{name}\n{vram_str}" if vram_str else name)

            info = "\n\n".join(parts) if parts else "Não detectada"
        except Exception:
            info = "Informação indisponível"

        def _set():
            if self._perf_gpu_info_var:
                self._perf_gpu_info_var.set(info)
        try:
            self.after(0, _set)
        except Exception:
            pass

    # ── Monitor em tempo real ─────────────────────────────────────────────────

    def _start_perf_monitor(self) -> None:
        if not _PSUTIL_OK or self._perf_running:
            return
        self._perf_running = True
        self._perf_thread = threading.Thread(
            target=self._perf_monitor_loop, daemon=True, name="perf-monitor")
        self._perf_thread.start()

    def _perf_monitor_loop(self) -> None:
        import time
        assert _psutil is not None
        while self._perf_running:
            try:
                cpu_pct = _psutil.cpu_percent(interval=2)
                if not self._perf_running:
                    break
                mem = _psutil.virtual_memory()
                freq = _psutil.cpu_freq()
                cores_phys = _psutil.cpu_count(logical=False) or 1
                cores_log  = _psutil.cpu_count(logical=True) or 1

                freq_str = f"{freq.current / 1000:.2f} GHz" if freq else ""
                cpu_info = f"{cores_phys} núcleos  /  {cores_log} threads"
                if freq_str:
                    cpu_info += f"  ·  {freq_str}"

                used_gb  = mem.used  / (1024 ** 3)
                total_gb = mem.total / (1024 ** 3)
                ram_info = f"{used_gb:.1f} GB  /  {total_gb:.1f} GB  ({mem.percent:.0f}%)"

                gpu_pct = self._get_nvidia_gpu_pct()

                def _update(cp=cpu_pct, rp=float(mem.percent), ci=cpu_info,
                             ri=ram_info, gp=gpu_pct):
                    try:
                        if self._perf_cpu_pct_var:
                            self._perf_cpu_pct_var.set(f"{cp:.0f}%")
                        if self._perf_cpu_bar:
                            clr = _GREEN if cp < 70 else ("#ffaa44" if cp < 90 else "#ff4444")
                            self._perf_cpu_bar.configure(progress_color=clr)
                            self._perf_cpu_bar.set(cp / 100)
                        if self._perf_cpu_info_var:
                            self._perf_cpu_info_var.set(ci)

                        if self._perf_ram_pct_var:
                            self._perf_ram_pct_var.set(f"{rp:.0f}%")
                        if self._perf_ram_bar:
                            clr = _GREEN if rp < 70 else ("#ffaa44" if rp < 90 else "#ff4444")
                            self._perf_ram_bar.configure(progress_color=clr)
                            self._perf_ram_bar.set(rp / 100)
                        if self._perf_ram_info_var:
                            self._perf_ram_info_var.set(ri)

                        if gp is not None:
                            if self._perf_gpu_pct_var:
                                self._perf_gpu_pct_var.set(f"{gp:.0f}%")
                            if self._perf_gpu_bar:
                                clr = _GREEN if gp < 70 else ("#ffaa44" if gp < 90 else "#ff4444")
                                self._perf_gpu_bar.configure(progress_color=clr)
                                self._perf_gpu_bar.set(gp / 100)
                    except Exception:
                        pass

                try:
                    self.after(0, _update)
                except Exception:
                    break

                # ── Verificação de limiares ────────────────────────────────
                try:
                    _warn = float(self._perf_alert_warn_var.get()) if self._perf_alert_warn_var else 80.0
                    _crit = float(self._perf_alert_crit_var.get()) if self._perf_alert_crit_var else 90.0
                except (ValueError, AttributeError):
                    _warn, _crit = 80.0, 90.0

                def _classify(v: float) -> str:
                    if v >= _crit: return "crit"
                    if v >= _warn: return "warn"
                    return "ok"

                _checks = [
                    ("cpu", cpu_pct),
                    ("ram", float(mem.percent)),
                    ("gpu", gpu_pct if gpu_pct is not None else -1.0),
                ]
                for _metric, _val in _checks:
                    if _val < 0:
                        continue
                    _new_st = _classify(_val)
                    _old_st = self._perf_last_state.get(_metric, "ok")
                    if _new_st != _old_st:
                        self._perf_last_state[_metric] = _new_st
                        self._log_perf_critical(_metric, _val, _new_st)

            except Exception:
                time.sleep(2)

    def _log_perf_critical(self, metric: str, pct: float, state: str) -> None:
        """Registra um ponto crítico no histórico do painel de Desempenho."""
        import datetime
        ts    = datetime.datetime.now().strftime("%d/%m %H:%M:%S")
        label = {"cpu": "CPU", "ram": "RAM", "gpu": "GPU"}.get(metric, metric.upper())
        if state == "ok":
            icon, nivel = "🟢", "recuperado"
        elif state == "warn":
            icon, nivel = "🟡", "AVISO"
        else:
            icon, nivel = "🔴", "CRÍTICO"
        line = f"[{ts}]  {icon}  {label}: {pct:.0f}%  →  {nivel}\n"

        def _do():
            box = self._perf_critical_log
            if box:
                box.configure(state="normal")
                box.insert("end", line)
                box.see("end")
                box.configure(state="disabled")
        try:
            self.after(0, _do)
        except Exception:
            pass

    def _clear_perf_critical_log(self) -> None:
        """Limpa o histórico de pontos críticos."""
        if self._perf_critical_log:
            self._perf_critical_log.configure(state="normal")
            self._perf_critical_log.delete("1.0", "end")
            self._perf_critical_log.configure(state="disabled")

    def _get_nvidia_gpu_pct(self) -> Optional[float]:
        """Tenta obter uso de GPU via nvidia-smi. Retorna None se indisponível."""
        import subprocess
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=utilization.gpu",
                 "--format=csv,noheader,nounits"],
                creationflags=0x08000000,
                stderr=subprocess.DEVNULL,
                timeout=3,
            ).decode().strip()
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
            if lines:
                return float(lines[0])
        except Exception:
            pass
        return None

    # ══════════════════════════════════════════════════════════════════════════
    # Painel Cross-ARK Clusters
    # ══════════════════════════════════════════════════════════════════════════

    def _build_clusters_panel(self, parent: ctk.CTkFrame) -> None:
        from .server_config import ClusterProfile
        parent.grid_columnconfigure(0, weight=0)
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # ── Cabeçalho ─────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.grid(row=0, column=0, columnspan=2, padx=24, pady=(20, 8), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="🔗  Clusters Cross-ARK",
                     font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, sticky="w")
        ctk.CTkLabel(
            hdr,
            text=(
                "Gerencie perfis de cluster para conectar múltiplos servidores (mesmo app) "
                "ou máquinas diferentes na rede via pasta compartilhada."
            ),
            text_color="gray55", font=ctk.CTkFont(size=12),
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        # ── Lista à esquerda ──────────────────────────────────────────────────
        list_fr = ctk.CTkFrame(parent, fg_color=_SIDEBAR_BG, corner_radius=12, width=220)
        list_fr.grid(row=1, column=0, padx=(20, 6), pady=(0, 20), sticky="nsew")
        list_fr.grid_propagate(False)
        list_fr.grid_rowconfigure(1, weight=1)
        list_fr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(list_fr, text="PERFIS", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="gray50").grid(row=0, column=0, padx=14, pady=(12, 4), sticky="w")

        self._cluster_list_box = ctk.CTkScrollableFrame(list_fr, fg_color="transparent")
        self._cluster_list_box.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._cluster_list_box.grid_columnconfigure(0, weight=1)

        add_btn = ctk.CTkButton(
            list_fr, text="＋  Novo Cluster", height=34,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._cluster_new,
        )
        add_btn.grid(row=2, column=0, padx=10, pady=10, sticky="ew")

        # ── Detalhe à direita ─────────────────────────────────────────────────
        self._cluster_detail_fr = ctk.CTkScrollableFrame(parent, fg_color=_BG)
        self._cluster_detail_fr.grid(row=1, column=1, padx=(0, 20), pady=(0, 20), sticky="nsew")
        self._cluster_detail_fr.grid_columnconfigure(0, weight=1)

        self._cluster_selected_id: str = ""
        self._cluster_detail_widgets: dict = {}

        self._clusters_refresh_list()

    def _clusters_refresh_list(self) -> None:
        """Atualiza o painel esquerdo com os perfis de cluster existentes."""
        for w in self._cluster_list_box.winfo_children():
            w.destroy()

        clusters = self.config_manager.clusters
        if not clusters:
            ctk.CTkLabel(self._cluster_list_box, text="Nenhum perfil criado.",
                         text_color="gray50", font=ctk.CTkFont(size=11)).grid(
                row=0, column=0, padx=12, pady=16)
            return

        for i, prof in enumerate(clusters):
            mode_icon = "🖥" if prof.mode == "local" else "🌐"
            row_fr = ctk.CTkFrame(self._cluster_list_box,
                                  fg_color=_CARD_BG if prof.id == self._cluster_selected_id else "transparent",
                                  corner_radius=8)
            row_fr.grid(row=i, column=0, padx=4, pady=2, sticky="ew")
            row_fr.grid_columnconfigure(0, weight=1)
            btn = ctk.CTkButton(
                row_fr,
                text=f"{mode_icon}  {prof.name}",
                anchor="w", fg_color="transparent", hover_color="#252540",
                text_color="#d8d8e8", height=34,
                command=lambda pid=prof.id: self._cluster_select(pid),
            )
            btn.grid(row=0, column=0, sticky="ew", padx=2)

    def _cluster_select(self, cluster_id: str) -> None:
        self._cluster_selected_id = cluster_id
        self._clusters_refresh_list()
        prof = self.config_manager.get_cluster(cluster_id)
        if prof:
            self._cluster_build_detail(prof)

    def _cluster_new(self) -> None:
        from .server_config import ClusterProfile
        prof = ClusterProfile()
        self.config_manager.add_cluster(prof)
        self._cluster_selected_id = prof.id
        self._clusters_refresh_list()
        self._cluster_build_detail(prof)

    def _cluster_build_detail(self, prof) -> None:
        for w in self._cluster_detail_fr.winfo_children():
            w.destroy()
        dw = self._cluster_detail_widgets
        dw.clear()
        parent = self._cluster_detail_fr

        # ── Título ────────────────────────────────────────────────────────────
        self._section_lbl(parent, 0, f"📋  Perfil: {prof.name}")

        card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        card.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="ew")
        card.grid_columnconfigure(1, weight=1)

        def _lbl(text, hint=""):
            fr = ctk.CTkFrame(card, fg_color="transparent")
            ctk.CTkLabel(fr, text=text, anchor="w", text_color="gray65",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
            if hint:
                ctk.CTkLabel(fr, text=hint, anchor="w", text_color="gray40",
                             font=ctk.CTkFont(size=10)).pack(anchor="w")
            return fr

        r = 0
        # Nome
        _lbl("Nome do perfil:").grid(row=r, column=0, padx=(18, 6), pady=(14, 4), sticky="w")
        dw["name"] = tk.StringVar(value=prof.name)
        ctk.CTkEntry(card, textvariable=dw["name"], height=30, width=260).grid(
            row=r, column=1, padx=(0, 18), pady=(14, 4), sticky="w")
        r += 1

        # Modo
        _lbl("Modo:", "Local = mesma máquina | Rede = pasta UNC/mapeada").grid(
            row=r, column=0, padx=(18, 6), pady=4, sticky="w")
        dw["mode"] = tk.StringVar(value=prof.mode)
        mode_menu = ctk.CTkOptionMenu(
            card, variable=dw["mode"], width=200, height=30,
            values=["local", "network"],
            fg_color=_CARD_BG, button_color=_BLUE, button_hover_color=_BLUE_HOVER,
        )
        mode_menu.set(prof.mode)
        mode_menu.grid(row=r, column=1, padx=(0, 18), pady=4, sticky="w")
        r += 1

        # Cluster ID
        _lbl("Cluster ID:",
             "Mesmo ID em todos os servidores do cluster. Gerado automaticamente.").grid(
            row=r, column=0, padx=(18, 6), pady=4, sticky="w")
        dw["cluster_id"] = tk.StringVar(value=prof.cluster_id)
        cid_row = ctk.CTkFrame(card, fg_color="transparent")
        cid_row.grid(row=r, column=1, padx=(0, 18), pady=4, sticky="ew")
        cid_row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(cid_row, textvariable=dw["cluster_id"], height=30).grid(
            row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(cid_row, text="🔄", width=34, height=30,
                      command=lambda: dw["cluster_id"].set(
                          __import__("uuid").uuid4().hex[:20])
                      ).grid(row=0, column=1)
        r += 1

        # Pasta do cluster
        _lbl("Pasta do Cluster:",
             "Local: caminho local (ex: C:\\ARKCluster)\n"
             "Rede: caminho UNC (ex: \\\\servidor\\ARKCluster) ou drive mapeado").grid(
            row=r, column=0, padx=(18, 6), pady=4, sticky="nw")
        dw["cluster_dir"] = tk.StringVar(value=prof.cluster_dir)
        dir_row = ctk.CTkFrame(card, fg_color="transparent")
        dir_row.grid(row=r, column=1, padx=(0, 18), pady=4, sticky="ew")
        dir_row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(dir_row, textvariable=dw["cluster_dir"], height=30,
                     placeholder_text="C:\\ARKCluster  ou  \\\\servidor\\ARKCluster").grid(
            row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(dir_row, text="📁", width=34, height=30,
                      command=lambda: self._browse_dir(dw["cluster_dir"])).grid(row=0, column=1)
        r += 1

        # Restrições
        self._section_lbl(parent, 2, "🚫  Restrições de Transferência")
        rest_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        rest_card.grid(row=3, column=0, padx=20, pady=(0, 12), sticky="ew")
        rest_card.grid_columnconfigure(0, weight=1)

        for rr, (field_key, label, hint) in enumerate([
            ("prevent_download_survivors", "Bloquear Download de Sobreviventes",
             "Impede jogadores de importar personagens de outros servidores."),
            ("prevent_download_items",     "Bloquear Download de Itens",
             "Impede trazer itens de outros servidores."),
            ("prevent_download_dinos",     "Bloquear Download de Dinos",
             "Impede trazer dinos domesticados de outros servidores."),
            ("no_transfer_from_filtering", "Bloquear Transferência por Filtro",
             "Impede transferências bloqueadas por restrições de filtro de mapa."),
        ]):
            dw[field_key] = tk.BooleanVar(value=getattr(prof, field_key))
            cb_fr = ctk.CTkFrame(rest_card, fg_color="transparent")
            cb_fr.grid(row=rr, column=0, padx=16, pady=(8 if rr == 0 else 2, 2), sticky="w")
            ctk.CTkCheckBox(cb_fr, text=label, variable=dw[field_key],
                            checkmark_color="white", fg_color=_GREEN_DARK,
                            hover_color=_GREEN_HOVER).pack(anchor="w")
            ctk.CTkLabel(cb_fr, text=hint, text_color="gray40",
                         font=ctk.CTkFont(size=10), anchor="w").pack(
                anchor="w", padx=(26, 0), pady=(0, 2))

        # ── Sincronização de Dados de Viagem ─────────────────────────────────
        self._section_lbl(parent, 4, "🔄  Sincronização de Dados de Viagem")
        sync_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        sync_card.grid(row=5, column=0, padx=20, pady=(0, 12), sticky="ew")
        sync_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            sync_card,
            text=(
                "Mantém sincronizados os arquivos de personagens, itens e dinos entre a pasta local do ARK\n"
                "e a pasta compartilhada de rede. Necessário quando os servidores estão em máquinas diferentes."
            ),
            text_color="gray50", font=ctk.CTkFont(size=10), justify="left", anchor="w",
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(10, 4), sticky="w")

        def _slbl(text, hint=""):
            fr = ctk.CTkFrame(sync_card, fg_color="transparent")
            ctk.CTkLabel(fr, text=text, anchor="w", text_color="gray65",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
            if hint:
                ctk.CTkLabel(fr, text=hint, anchor="w", text_color="gray40",
                             font=ctk.CTkFont(size=10)).pack(anchor="w")
            return fr

        sr = 1
        dw["sync_enabled"] = tk.BooleanVar(value=getattr(prof, "sync_enabled", False))
        ctk.CTkCheckBox(
            sync_card,
            text="Sincronizar automaticamente com a pasta de rede",
            variable=dw["sync_enabled"],
            checkmark_color="white", fg_color=_BLUE, hover_color=_BLUE_HOVER,
        ).grid(row=sr, column=0, columnspan=2, padx=16, pady=(4, 6), sticky="w")
        sr += 1

        _slbl("Pasta local de dados do cluster:",
              "Onde o ARK desta máquina grava os arquivos de viagem.\n"
              "Ex: C:\\ARK\\ShooterGame\\Saved\\clusters").grid(
            row=sr, column=0, padx=(16, 6), pady=4, sticky="nw")
        dw["local_cluster_dir"] = tk.StringVar(value=getattr(prof, "local_cluster_dir", ""))
        lcd_row = ctk.CTkFrame(sync_card, fg_color="transparent")
        lcd_row.grid(row=sr, column=1, padx=(0, 16), pady=4, sticky="ew")
        lcd_row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(lcd_row, textvariable=dw["local_cluster_dir"], height=30,
                     placeholder_text="C:\\ARK\\ShooterGame\\Saved\\clusters").grid(
            row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(lcd_row, text="📁", width=34, height=30,
                      command=lambda: self._browse_dir(dw["local_cluster_dir"])).grid(row=0, column=1)
        sr += 1

        _slbl("Intervalo (segundos):", "Tempo entre cada ciclo de sincronização automática.").grid(
            row=sr, column=0, padx=(16, 6), pady=4, sticky="w")
        dw["sync_interval_var"] = tk.StringVar(value=str(getattr(prof, "sync_interval", 30)))
        ctk.CTkEntry(sync_card, textvariable=dw["sync_interval_var"],
                     height=30, width=80).grid(
            row=sr, column=1, padx=(0, 16), pady=4, sticky="w")
        sr += 1

        _prof_id_for_sync = prof.id
        _is_running = (_prof_id_for_sync in self._cluster_sync_engines
                       and self._cluster_sync_engines[_prof_id_for_sync].is_running)
        _sync_status_lbl = ctk.CTkLabel(
            sync_card,
            text="● Ativo" if _is_running else "○ Parado",
            text_color=_GREEN if _is_running else "gray50",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        _sync_status_lbl.grid(row=sr, column=0, padx=16, pady=(6, 12), sticky="w")
        dw["_sync_status_lbl"] = _sync_status_lbl

        sync_ctrl_fr = ctk.CTkFrame(sync_card, fg_color="transparent")
        sync_ctrl_fr.grid(row=sr, column=1, padx=(0, 16), pady=(6, 12), sticky="w")

        def _toggle_cluster_sync():
            if (_prof_id_for_sync in self._cluster_sync_engines
                    and self._cluster_sync_engines[_prof_id_for_sync].is_running):
                self._cluster_sync_stop(_prof_id_for_sync)
            else:
                self._cluster_sync_start(_prof_id_for_sync)
            p2 = self.config_manager.get_cluster(_prof_id_for_sync)
            if p2:
                self._cluster_build_detail(p2)

        ctk.CTkButton(
            sync_ctrl_fr,
            text="⏹ Parar" if _is_running else "▶ Iniciar",
            width=100, height=30,
            fg_color="#5a1a1a" if _is_running else _GREEN_DARK,
            hover_color="#8b2222" if _is_running else _GREEN_HOVER,
            command=_toggle_cluster_sync,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            sync_ctrl_fr, text="🔄 Sync Agora", width=120, height=30,
            fg_color=_CARD_BG, hover_color="#252540",
            command=lambda: self._cluster_sync_once(_prof_id_for_sync),
        ).pack(side="left")

        # ── Servidores vinculados ──────────────────────────────────────────────
        self._section_lbl(parent, 6, "🖥  Servidores neste Cluster")
        srv_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        srv_card.grid(row=7, column=0, padx=20, pady=(0, 12), sticky="ew")
        srv_card.grid_columnconfigure(0, weight=1)

        linked = self.config_manager.servers_in_cluster(prof.id)
        all_srvs = self.config_manager.servers
        if not all_srvs:
            ctk.CTkLabel(srv_card, text="Nenhum servidor cadastrado.",
                         text_color="gray50").grid(row=0, column=0, padx=16, pady=12)
        else:
            for si, srv in enumerate(all_srvs):
                is_linked = srv.id in [s.id for s in linked]
                v = tk.BooleanVar(value=is_linked)
                dw[f"srv_{srv.id}"] = v
                map_name = srv.map.replace("_P", "").replace("_", " ")
                ctk.CTkCheckBox(
                    srv_card,
                    text=f"{srv.name}  ({map_name}  ·  :{srv.server_port})",
                    variable=v,
                    checkmark_color="white", fg_color=_BLUE, hover_color=_BLUE_HOVER,
                ).grid(row=si, column=0, padx=16, pady=(8 if si == 0 else 4, 4), sticky="w")

        # ── Botões ────────────────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.grid(row=8, column=0, padx=20, pady=(4, 20), sticky="w")

        ctk.CTkButton(
            btn_row, text="💾  Salvar", width=130, height=36,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=lambda: self._cluster_save(prof.id),
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row, text="🗑  Excluir", width=110, height=36,
            fg_color="#5a1a1a", hover_color="#8b2222",
            command=lambda: self._cluster_delete(prof.id),
        ).pack(side="left")

    def _cluster_save(self, cluster_id: str) -> None:
        prof = self.config_manager.get_cluster(cluster_id)
        if not prof:
            return
        dw = self._cluster_detail_widgets

        prof.name       = dw.get("name",       tk.StringVar()).get().strip() or prof.name
        prof.mode       = dw.get("mode",       tk.StringVar()).get()
        prof.cluster_id = dw.get("cluster_id", tk.StringVar()).get().strip() or prof.cluster_id
        prof.cluster_dir = dw.get("cluster_dir", tk.StringVar()).get().strip()
        prof.prevent_download_survivors = bool(dw.get("prevent_download_survivors", tk.BooleanVar()).get())
        prof.prevent_download_items     = bool(dw.get("prevent_download_items",     tk.BooleanVar()).get())
        prof.prevent_download_dinos     = bool(dw.get("prevent_download_dinos",     tk.BooleanVar()).get())
        prof.no_transfer_from_filtering = bool(dw.get("no_transfer_from_filtering", tk.BooleanVar()).get())
        prof.sync_enabled      = bool(dw.get("sync_enabled", tk.BooleanVar()).get())
        prof.local_cluster_dir = dw.get("local_cluster_dir", tk.StringVar()).get().strip()
        try:
            prof.sync_interval = max(5, int(dw.get("sync_interval_var", tk.StringVar(value="30")).get()))
        except ValueError:
            pass

        self.config_manager.update_cluster(prof)
        # Reinicia engine de sync se configuração mudou
        self._cluster_sync_restart(prof.id)

        # Atualiza vínculos de servidores
        for srv in self.config_manager.servers:
            var = dw.get(f"srv_{srv.id}")
            if var is None:
                continue
            should_link = bool(var.get())
            if should_link and srv.cluster_profile_id != cluster_id:
                srv.cluster_profile_id = cluster_id
                self.config_manager.update_server(srv)
                self.server_manager.update_server_config(srv)
            elif not should_link and srv.cluster_profile_id == cluster_id:
                srv.cluster_profile_id = ""
                self.config_manager.update_server(srv)
                self.server_manager.update_server_config(srv)

        self._clusters_refresh_list()
        self._cluster_build_detail(prof)

    def _cluster_delete(self, cluster_id: str) -> None:
        from tkinter import messagebox
        prof = self.config_manager.get_cluster(cluster_id)
        if not prof:
            return
        linked_count = len(self.config_manager.servers_in_cluster(cluster_id))
        msg = f"Excluir o perfil \"{prof.name}\"?"
        if linked_count:
            msg += f"\n\n{linked_count} servidor(es) serão desvinculados do cluster."
        if not messagebox.askyesno("Confirmar Exclusão", msg, parent=self):
            return
        self.config_manager.remove_cluster(cluster_id)
        self._cluster_sync_stop(cluster_id)
        self._cluster_selected_id = ""
        self._clusters_refresh_list()
        for w in self._cluster_detail_fr.winfo_children():
            w.destroy()

    # ── Cluster sync engine helpers ───────────────────────────────────────────

    def _auto_start_cluster_syncs(self) -> None:
        """Inicia engines de sync para todos os clusters com sync habilitado."""
        for prof in self.config_manager.clusters:
            if prof.sync_enabled and prof.local_cluster_dir and prof.cluster_dir:
                self._cluster_sync_start(prof.id)

    def _cluster_sync_restart(self, cluster_id: str) -> None:
        """Para e reinicia o engine de sync de um cluster (chama após salvar perfil)."""
        self._cluster_sync_stop(cluster_id)
        prof = self.config_manager.get_cluster(cluster_id)
        if prof and prof.sync_enabled and prof.local_cluster_dir and prof.cluster_dir:
            self._cluster_sync_start(cluster_id)

    def _cluster_sync_start(self, cluster_id: str) -> None:
        """Inicia o SyncEngine bidirecional para o cluster."""
        prof = self.config_manager.get_cluster(cluster_id)
        if not prof:
            return
        if not prof.local_cluster_dir or not prof.cluster_dir:
            return
        self._cluster_sync_stop(cluster_id)

        class _ClusterSyncCfg:
            def __init__(self, local_dir: str, net_dir: str, interval: int) -> None:
                self.sync_cycles = [[local_dir, net_dir]]
                self.sync_interval = max(5, interval)
                self.log_debug = False

        engine = SyncEngine(
            config=_ClusterSyncCfg(prof.local_cluster_dir, prof.cluster_dir, prof.sync_interval),
            on_log=lambda msg, lvl: self._cluster_sync_log(cluster_id, msg, lvl),
            on_status_change=lambda s: None,
        )
        self._cluster_sync_engines[cluster_id] = engine
        engine.start()

    def _cluster_sync_stop(self, cluster_id: str) -> None:
        """Para o engine de sync de um cluster (se estiver rodando)."""
        engine = self._cluster_sync_engines.pop(cluster_id, None)
        if engine and engine.is_running:
            engine.stop()

    def _cluster_sync_once(self, cluster_id: str) -> None:
        """Executa um ciclo de sync imediato sem iniciar o loop automático."""
        prof = self.config_manager.get_cluster(cluster_id)
        if not prof or not prof.local_cluster_dir or not prof.cluster_dir:
            return
        if cluster_id in self._cluster_sync_engines:
            self._cluster_sync_engines[cluster_id].sync_once()
        else:
            # Cria engine temporário apenas para o ciclo único
            class _ClusterSyncCfg:
                def __init__(self, local_dir: str, net_dir: str) -> None:
                    self.sync_cycles = [[local_dir, net_dir]]
                    self.sync_interval = 999
                    self.log_debug = False
            SyncEngine(
                config=_ClusterSyncCfg(prof.local_cluster_dir, prof.cluster_dir),
                on_log=lambda msg, lvl: self._cluster_sync_log(cluster_id, msg, lvl),
            ).sync_once()

    def _cluster_sync_log(self, cluster_id: str, msg: str, level: str) -> None:
        prof = self.config_manager.get_cluster(cluster_id)
        name = prof.name if prof else cluster_id[:8]
        self._emit_global_log(f"[Cluster:{name}] {msg}", level)

    # ── Config Dinâmica ───────────────────────────────────────────────────────

    def _auto_start_dynamic_configs(self) -> None:
        """Inicia o HTTP server e popula config para servidores com dynamic_config_enabled=True."""
        enabled = [s for s in self.config_manager.servers if s.dynamic_config_enabled]
        if not enabled:
            return
        ok = self._dynamic_config_server.start()
        if not ok:
            self._global_log(
                f"Aviso: não foi possível iniciar o servidor HTTP de config dinâmica "
                f"(porta {self._dynamic_config_server.port} em uso?). "
                f"DynamicConfigURL não estará disponível.", "warning")
            return
        for srv in enabled:
            content = build_dynamic_config(srv)
            self._dynamic_config_server.update(srv.id, content)
        self._global_log(
            f"Config dinâmica ativa para {len(enabled)} servidor(es) "
            f"→ http://127.0.0.1:{self._dynamic_config_server.port}/", "info")

    def _get_dynamic_config_url(self, server_id: str) -> str:
        """Callback para ServerManager: retorna a URL do servidor dinâmico."""
        if not self._dynamic_config_server.is_running:
            self._dynamic_config_server.start()
        return self._dynamic_config_server.get_url(server_id)

    def _push_dynamic_config(self, server_id: str) -> None:
        """Atualiza o conteúdo INI servido para um servidor — aplicado na próxima poll do ARK."""
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return
        if not self._dynamic_config_server.is_running:
            ok = self._dynamic_config_server.start()
            if not ok:
                self._global_log(
                    f"[{srv.name}] Não foi possível iniciar o servidor HTTP de config dinâmica "
                    f"(porta {self._dynamic_config_server.port} em uso?).", "error")
                return
        content = build_dynamic_config(srv)
        self._dynamic_config_server.update(server_id, content)
        url = self._dynamic_config_server.get_url(server_id)
        self._global_log(
            f"[{srv.name}] Config dinâmica atualizada → {url} "
            f"(ARK aplicará na próxima poll, ~2 min).", "info")
        # Atualiza label de URL na UI se o painel estiver aberto
        w = self._server_widgets.get(server_id, {})
        url_var = w.get("_dyn_url_var")
        if url_var:
            url_var.set(url)


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
    # Aba INI Estruturado
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_ini_mods(self, parent, srv: ServerConfig) -> None:
        """Aba de edição estruturada das seções INI (Mods + Personalizadas)."""
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        w = self._server_widgets[srv.id]

        sub = ctk.CTkTabview(parent, fg_color=_BG, segmented_button_fg_color=_SIDEBAR_BG,
                             segmented_button_selected_color=_GREEN_DARK,
                             segmented_button_selected_hover_color=_GREEN_HOVER,
                             segmented_button_unselected_color=_SIDEBAR_BG,
                             segmented_button_unselected_hover_color=_CARD_BG)
        sub.grid(row=0, column=0, sticky="nsew", padx=4, pady=(4, 4))
        sub.add("GameUserSettings.ini")
        sub.add("Game.ini")

        for file_key, tab_name in [("gus", "GameUserSettings.ini"), ("game", "Game.ini")]:
            t = sub.tab(tab_name)
            t.grid_columnconfigure(0, weight=0)
            t.grid_columnconfigure(1, weight=1)
            t.grid_rowconfigure(1, weight=1)

            # ── Barra de ações ────────────────────────────────────────────────
            bar = ctk.CTkFrame(t, fg_color="transparent")
            bar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(4, 2))

            ctk.CTkLabel(bar, text="Seções INI personalizadas",
                         text_color="gray55",
                         font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(8, 16))

            ctk.CTkButton(bar, text="+ Seção", width=90, height=28,
                          fg_color=_BLUE, hover_color=_BLUE_HOVER,
                          font=ctk.CTkFont(size=11),
                          command=lambda fk=file_key, sid=srv.id:
                              self._ini_add_section(sid, fk)).pack(side="left", padx=(0, 4))

            ctk.CTkButton(bar, text="� Colar Seção", width=115, height=28,
                          fg_color="#3a2a5a", hover_color="#4e3a7a",
                          font=ctk.CTkFont(size=11),
                          command=lambda fk=file_key, sid=srv.id:
                              self._ini_paste_section(sid, fk)).pack(side="left", padx=(0, 4))

            ctk.CTkButton(bar, text="�🔁 Atualizar", width=100, height=28,
                          fg_color="#2a2a2a", hover_color="#404040",
                          font=ctk.CTkFont(size=11),
                          command=lambda fk=file_key, sid=srv.id:
                              self._ini_reload(sid, fk)).pack(side="left", padx=(0, 4))

            ctk.CTkButton(bar, text="💾 Salvar INI", width=110, height=28,
                          fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                          font=ctk.CTkFont(size=11),
                          command=lambda sid=srv.id:
                              self._ini_save(sid)).pack(side="right", padx=8)

            # ── Painel esquerdo: lista de seções ──────────────────────────────
            sec_outer = ctk.CTkFrame(t, fg_color=_CARD_BG, corner_radius=8, width=230)
            sec_outer.grid(row=1, column=0, sticky="nsew", padx=(4, 2), pady=(2, 4))
            sec_outer.grid_columnconfigure(0, weight=1)
            sec_outer.grid_rowconfigure(1, weight=1)
            sec_outer.grid_propagate(False)

            ctk.CTkLabel(sec_outer, text="Seções", text_color="gray45",
                         font=ctk.CTkFont(size=10, weight="bold")).grid(
                row=0, column=0, sticky="w", padx=8, pady=(6, 2))

            sec_scroll = ctk.CTkScrollableFrame(sec_outer, fg_color="transparent",
                                                corner_radius=0)
            sec_scroll.grid(row=1, column=0, sticky="nsew", padx=2, pady=(0, 4))
            sec_scroll.grid_columnconfigure(0, weight=1)
            w[f"_ini_{file_key}_secscroll"] = sec_scroll

            # ── Painel direito: entradas da seção ─────────────────────────────
            kv_outer = ctk.CTkFrame(t, fg_color=_CARD_BG, corner_radius=8)
            kv_outer.grid(row=1, column=1, sticky="nsew", padx=(2, 4), pady=(2, 4))
            kv_outer.grid_columnconfigure(0, weight=1)
            kv_outer.grid_rowconfigure(2, weight=1)

            # Nome da seção selecionada
            sec_name_var = tk.StringVar()
            w[f"_ini_{file_key}_sec_name_var"] = sec_name_var

            kv_hdr = ctk.CTkFrame(kv_outer, fg_color="transparent")
            kv_hdr.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
            kv_hdr.grid_columnconfigure(0, weight=1)

            ctk.CTkEntry(kv_hdr, textvariable=sec_name_var, height=32,
                         font=ctk.CTkFont(size=12, weight="bold"),
                         placeholder_text="(nenhuma seção selecionada)").grid(
                row=0, column=0, sticky="ew")

            # Cabeçalho das colunas Chave / Valor
            col_hdr = ctk.CTkFrame(kv_outer, fg_color="transparent")
            col_hdr.grid(row=1, column=0, sticky="ew", padx=12, pady=(4, 0))
            col_hdr.grid_columnconfigure(0, weight=1)
            col_hdr.grid_columnconfigure(1, weight=2)
            ctk.CTkLabel(col_hdr, text="Chave", text_color="gray45",
                         font=ctk.CTkFont(size=10)).grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(col_hdr, text="Valor", text_color="gray45",
                         font=ctk.CTkFont(size=10)).grid(row=0, column=1, sticky="w", padx=(8, 0))

            kv_scroll = ctk.CTkScrollableFrame(kv_outer, fg_color="transparent",
                                               corner_radius=0)
            kv_scroll.grid(row=2, column=0, sticky="nsew", padx=4, pady=2)
            kv_scroll.grid_columnconfigure(0, weight=1)
            kv_scroll.grid_columnconfigure(1, weight=2)
            w[f"_ini_{file_key}_kvscroll"] = kv_scroll

            kv_footer = ctk.CTkFrame(kv_outer, fg_color="transparent")
            kv_footer.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 8))
            ctk.CTkButton(kv_footer, text="+ Entrada", width=90, height=26,
                          fg_color=_BLUE, hover_color=_BLUE_HOVER,
                          font=ctk.CTkFont(size=11),
                          command=lambda fk=file_key, sid=srv.id:
                              self._ini_add_entry(sid, fk)).pack(side="left")

            # ── Estado da aba ─────────────────────────────────────────────────
            w[f"_ini_{file_key}_sel_section"] = None
            # Dados: lista de seção-dicts já descritos acima
            w[f"_ini_{file_key}_data"] = []

        # Carregamento inicial na sub-aba ativa
        self._ini_reload(srv.id, "gus")
        self._ini_reload(srv.id, "game")

    # ── Helpers do painel INI ─────────────────────────────────────────────────

    def _ini_flush_current(self, server_id: str, file_key: str) -> None:
        """Salva o conteúdo dos StringVars da seção exibida de volta nos dados."""
        w = self._server_widgets.get(server_id, {})
        sel = w.get(f"_ini_{file_key}_sel_section")
        if sel is None:
            return
        data = w.get(f"_ini_{file_key}_data", [])
        sec_data = next((s for s in data if s["section"] == sel), None)
        if sec_data is None:
            return
        # Atualiza nome da seção
        name_var = w.get(f"_ini_{file_key}_sec_name_var")
        if name_var:
            new_name = name_var.get().strip()
            if new_name and new_name != sel:
                sec_data["section"] = new_name
                w[f"_ini_{file_key}_sel_section"] = new_name
        # Atualiza entradas (os StringVars estão in-place no dicionário)
        for entry in sec_data.get("entries", []):
            kv = entry.get("_key_var")
            vv = entry.get("_val_var")
            if kv:
                entry["key"] = kv.get()
            if vv:
                entry["value"] = vv.get()

    def _ini_reload(self, server_id: str, file_key: str) -> None:
        """Recarrega os dados de mod_ini_configs + custom_ini_sections e reconstrói a lista."""
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return
        w = self._server_widgets.get(server_id, {})

        all_sections: list = []
        # Seções vindas dos mods
        ini_key = f"{file_key}_ini"
        for mod_id, cfg in srv.mod_ini_configs.items():
            raw = cfg.get(ini_key, "")
            if raw.strip():
                mod_name = srv.mod_names.get(mod_id, f"Mod {mod_id}")
                for sec in parse_ini_text_to_sections(raw):
                    sec["mod_id"] = mod_id
                    sec["mod_name"] = mod_name
                    all_sections.append(sec)
        # Seções personalizadas (sem mod)
        for sec in srv.custom_ini_sections.get(file_key, []):
            all_sections.append({
                "section": sec.get("section", ""),
                "entries": [dict(e) for e in sec.get("entries", [])],
                "mod_id": None,
                "mod_name": "Personalizado",
            })

        w[f"_ini_{file_key}_data"] = all_sections
        w[f"_ini_{file_key}_sel_section"] = None
        sec_name_var = w.get(f"_ini_{file_key}_sec_name_var")
        if sec_name_var:
            sec_name_var.set("")

        # Limpa o painel KV
        kv_scroll = w.get(f"_ini_{file_key}_kvscroll")
        if kv_scroll:
            for ch in kv_scroll.winfo_children():
                ch.destroy()

        # Reconstrói lista de seções
        sec_scroll = w.get(f"_ini_{file_key}_secscroll")
        if sec_scroll is None:
            return
        for ch in sec_scroll.winfo_children():
            ch.destroy()

        if not all_sections:
            ctk.CTkLabel(sec_scroll,
                         text="Nenhuma seção encontrada.\n"
                              "Adicione uma seção ou configure\n"
                              "o INI de algum mod.",
                         text_color="gray40", font=ctk.CTkFont(size=10),
                         justify="center").pack(pady=20, padx=8)
            return

        for sec in all_sections:
            self._ini_render_section_item(server_id, file_key, sec_scroll, sec)

    def _ini_render_section_item(self, server_id: str, file_key: str,
                                 container, sec: dict) -> None:
        """Cria o item de seção no painel esquerdo."""
        is_custom = sec.get("mod_id") is None
        bg_btn = "#2a4060" if not is_custom else "#2a3a25"
        bg_hover = "#3a5080" if not is_custom else "#3a5230"
        src_text = (sec.get("mod_name") or "Personalizado")[:18]

        row = ctk.CTkFrame(container, fg_color="transparent")
        row.pack(fill="x", pady=1, padx=2)
        row.grid_columnconfigure(0, weight=1)

        btn = ctk.CTkButton(
            row, text=sec["section"], anchor="w", height=28,
            fg_color=bg_btn, hover_color=bg_hover,
            font=ctk.CTkFont(size=11),
            command=lambda s=sec["section"], sid=server_id, fk=file_key:
                self._ini_select_section(sid, fk, s))
        btn.grid(row=0, column=0, sticky="ew")

        del_btn = ctk.CTkButton(
            row, text="×", width=24, height=28,
            fg_color=_RED_DARK, hover_color=_RED_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda s=sec["section"], sid=server_id, fk=file_key:
                self._ini_delete_section(sid, fk, s))
        del_btn.grid(row=0, column=1, padx=(2, 0))

        ctk.CTkLabel(row, text=f"  {src_text}", text_color="gray38",
                     font=ctk.CTkFont(size=9)).grid(row=1, column=0, sticky="w")

    def _ini_select_section(self, server_id: str, file_key: str, section_name: str) -> None:
        """Exibe as entradas da seção selecionada no painel direito."""
        w = self._server_widgets.get(server_id, {})
        # Flush da seção anterior
        self._ini_flush_current(server_id, file_key)

        data = w.get(f"_ini_{file_key}_data", [])
        sec_data = next((s for s in data if s["section"] == section_name), None)
        if sec_data is None:
            return

        w[f"_ini_{file_key}_sel_section"] = section_name
        name_var = w.get(f"_ini_{file_key}_sec_name_var")
        if name_var:
            name_var.set(section_name)

        kv_scroll = w.get(f"_ini_{file_key}_kvscroll")
        if kv_scroll is None:
            return
        for ch in kv_scroll.winfo_children():
            ch.destroy()

        for idx, entry in enumerate(sec_data.get("entries", [])):
            self._ini_render_entry_row(server_id, file_key, kv_scroll, sec_data, entry, idx)

    def _ini_render_entry_row(self, server_id: str, file_key: str,
                              container, sec_data: dict, entry: dict, idx: int) -> None:
        """Cria uma linha Chave=Valor no painel direito."""
        if "_key_var" not in entry:
            entry["_key_var"] = tk.StringVar(value=entry.get("key", ""))
        if "_val_var" not in entry:
            entry["_val_var"] = tk.StringVar(value=entry.get("value", ""))

        row = ctk.CTkFrame(container, fg_color="transparent")
        row.grid(row=idx, column=0, columnspan=3, sticky="ew", pady=1)
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=2)

        ctk.CTkEntry(row, textvariable=entry["_key_var"], height=28,
                     placeholder_text="chave",
                     font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkEntry(row, textvariable=entry["_val_var"], height=28,
                     placeholder_text="valor",
                     font=ctk.CTkFont(size=11)).grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(row, text="×", width=24, height=28,
                      fg_color=_RED_DARK, hover_color=_RED_HOVER,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=lambda e=entry, sd=sec_data, sid=server_id, fk=file_key:
                          self._ini_del_entry(sid, fk, sd, e)).grid(row=0, column=2, padx=(4, 0))

    def _ini_add_section(self, server_id: str, file_key: str) -> None:
        """Adiciona uma nova seção personalizada vazia."""
        w = self._server_widgets.get(server_id, {})
        data = w.get(f"_ini_{file_key}_data", [])
        new_sec = {
            "section": f"NovaSeção_{len(data)+1}",
            "mod_id": None,
            "mod_name": "Personalizado",
            "entries": [],
        }
        data.append(new_sec)
        sec_scroll = w.get(f"_ini_{file_key}_secscroll")
        if sec_scroll:
            # Remove mensagem de vazio se existir
            for ch in list(sec_scroll.winfo_children()):
                if isinstance(ch, ctk.CTkLabel):
                    ch.destroy()
            self._ini_render_section_item(server_id, file_key, sec_scroll, new_sec)
        self._ini_select_section(server_id, file_key, new_sec["section"])

    def _ini_paste_section(self, server_id: str, file_key: str) -> None:
        """Abre diálogo para colar um bloco INI completo (uma ou mais seções)."""
        dlg = ctk.CTkToplevel(self)
        dlg.title("Colar Seção INI")
        dlg.geometry("600x400")
        dlg.resizable(True, True)
        dlg.grab_set()
        dlg.grid_columnconfigure(0, weight=1)
        dlg.grid_rowconfigure(1, weight=1)

        # Instrução
        ctk.CTkLabel(
            dlg,
            text="Cole o bloco INI abaixo. Pode conter uma ou mais seções.",
            text_color="gray60",
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

        txt = ctk.CTkTextbox(dlg, font=ctk.CTkFont(family="Consolas", size=12),
                             fg_color="#1a1a28", border_width=1, border_color="#3a3a5a")
        txt.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 6))

        # Placeholder – inserido e removido ao focar
        _PLACEHOLDER = "[NomeDaSeção]\nChave=Valor\nChave2=Valor2"
        txt.insert("1.0", _PLACEHOLDER)
        txt.configure(text_color="gray45")

        def _on_focus_in(_e):
            if txt.get("1.0", "end-1c") == _PLACEHOLDER:
                txt.delete("1.0", "end")
                txt.configure(text_color="#e0e0f0")

        def _on_focus_out(_e):
            if not txt.get("1.0", "end-1c").strip():
                txt.insert("1.0", _PLACEHOLDER)
                txt.configure(text_color="gray45")

        txt.bind("<FocusIn>",  _on_focus_in)
        txt.bind("<FocusOut>", _on_focus_out)

        # Feedback label
        fb_var = tk.StringVar()
        fb_lbl = ctk.CTkLabel(dlg, textvariable=fb_var, text_color="#ffaa44",
                              font=ctk.CTkFont(size=11))
        fb_lbl.grid(row=2, column=0, padx=16, sticky="w")

        def _import():
            raw = txt.get("1.0", "end-1c").strip()
            if not raw or raw == _PLACEHOLDER:
                fb_var.set("⚠ Cole algum conteúdo antes de importar.")
                return

            parsed = parse_ini_text_to_sections(raw)
            if not parsed:
                fb_var.set("⚠ Nenhuma seção válida encontrada. Verifique o formato.")
                return

            w = self._server_widgets.get(server_id, {})
            data = w.get(f"_ini_{file_key}_data", [])
            sec_scroll = w.get(f"_ini_{file_key}_secscroll")

            imported = 0
            last_sec_name = None
            for sec in parsed:
                sec_name = sec.get("section", "").strip()
                if not sec_name:
                    continue
                # Se a seção já existe, mescla as entradas
                existing = next((s for s in data if s["section"] == sec_name), None)
                if existing:
                    existing_keys = {e["key"] for e in existing["entries"]}
                    for entry in sec.get("entries", []):
                        if entry["key"] not in existing_keys:
                            existing["entries"].append({"key": entry["key"], "value": entry["value"]})
                        else:
                            # Atualiza valor existente
                            for e in existing["entries"]:
                                if e["key"] == entry["key"]:
                                    e["value"] = entry["value"]
                                    break
                else:
                    new_sec = {
                        "section":  sec_name,
                        "mod_id":   None,
                        "mod_name": "Personalizado",
                        "entries":  [{"key": e["key"], "value": e["value"]}
                                     for e in sec.get("entries", [])],
                    }
                    data.append(new_sec)
                imported += 1
                last_sec_name = sec_name

            self._ini_rebuild_section_list(server_id, file_key)
            if last_sec_name:
                self._ini_select_section(server_id, file_key, last_sec_name)
            dlg.destroy()

        btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_fr.grid(row=3, column=0, padx=16, pady=(2, 14), sticky="e")
        ctk.CTkButton(btn_fr, text="Cancelar", width=90, height=30,
                      fg_color="gray30", hover_color="gray40",
                      command=dlg.destroy).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_fr, text="✅ Importar", width=110, height=30,
                      fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                      command=_import).pack(side="left")

    def _ini_delete_section(self, server_id: str, file_key: str, section_name: str) -> None:
        """Remove a seção da lista."""
        w = self._server_widgets.get(server_id, {})
        data = w.get(f"_ini_{file_key}_data", [])
        data[:] = [s for s in data if s["section"] != section_name]
        if w.get(f"_ini_{file_key}_sel_section") == section_name:
            w[f"_ini_{file_key}_sel_section"] = None
            kv_scroll = w.get(f"_ini_{file_key}_kvscroll")
            if kv_scroll:
                for ch in kv_scroll.winfo_children():
                    ch.destroy()
            name_var = w.get(f"_ini_{file_key}_sec_name_var")
            if name_var:
                name_var.set("")
        # Reconstrói lista (mais simples que remover item individual)
        self._ini_rebuild_section_list(server_id, file_key)

    def _ini_rebuild_section_list(self, server_id: str, file_key: str) -> None:
        """Reconstrói a lista de seções no painel esquerdo sem perder os dados."""
        w = self._server_widgets.get(server_id, {})
        sec_scroll = w.get(f"_ini_{file_key}_secscroll")
        if sec_scroll is None:
            return
        for ch in sec_scroll.winfo_children():
            ch.destroy()
        data = w.get(f"_ini_{file_key}_data", [])
        if not data:
            ctk.CTkLabel(sec_scroll,
                         text="Nenhuma seção encontrada.\n"
                              "Adicione uma seção ou configure\n"
                              "o INI de algum mod.",
                         text_color="gray40", font=ctk.CTkFont(size=10),
                         justify="center").pack(pady=20, padx=8)
            return
        for sec in data:
            self._ini_render_section_item(server_id, file_key, sec_scroll, sec)

    def _ini_add_entry(self, server_id: str, file_key: str) -> None:
        """Adiciona uma nova linha vazia na seção selecionada."""
        w = self._server_widgets.get(server_id, {})
        sel = w.get(f"_ini_{file_key}_sel_section")
        if sel is None:
            return
        data = w.get(f"_ini_{file_key}_data", [])
        sec_data = next((s for s in data if s["section"] == sel), None)
        if sec_data is None:
            return
        new_entry = {"key": "", "value": ""}
        sec_data["entries"].append(new_entry)
        kv_scroll = w.get(f"_ini_{file_key}_kvscroll")
        if kv_scroll:
            idx = len(sec_data["entries"]) - 1
            self._ini_render_entry_row(server_id, file_key, kv_scroll, sec_data, new_entry, idx)

    def _ini_del_entry(self, server_id: str, file_key: str,
                       sec_data: dict, entry: dict) -> None:
        """Remove uma entrada da seção e reconstrói o painel de entradas."""
        sec_data["entries"] = [e for e in sec_data["entries"] if e is not entry]
        # Remove os StringVars para forçar recriação
        for e in sec_data["entries"]:
            e.pop("_key_var", None)
            e.pop("_val_var", None)
        self._ini_select_section(server_id, file_key, sec_data["section"])

    def _ini_save(self, server_id: str) -> None:
        """Serializa o conteúdo estruturado de volta para mod_ini_configs e custom_ini_sections."""
        # Flush da seção visível em ambos os file_keys
        for fk in ("gus", "game"):
            self._ini_flush_current(server_id, fk)

        srv = self.config_manager.get_server(server_id)
        if not srv:
            return
        w = self._server_widgets.get(server_id, {})

        for file_key in ("gus", "game"):
            data = w.get(f"_ini_{file_key}_data", [])
            ini_key = f"{file_key}_ini"
            mod_buckets: dict = {}     # mod_id → list of section dicts
            custom_secs: list = []

            for sec in data:
                # Lê de StringVars se presentes
                plain_entries = []
                for entry in sec.get("entries", []):
                    kv = entry.get("_key_var")
                    vv = entry.get("_val_var")
                    key = kv.get().strip() if kv else entry.get("key", "").strip()
                    val = vv.get().strip() if vv else entry.get("value", "").strip()
                    if key:
                        plain_entries.append({"key": key, "value": val})
                plain_sec = {"section": sec["section"], "entries": plain_entries}
                mid = sec.get("mod_id")
                if mid is None:
                    custom_secs.append(plain_sec)
                else:
                    mod_buckets.setdefault(mid, []).append(plain_sec)

            # Atualiza mod_ini_configs
            for mod_id, secs in mod_buckets.items():
                cfg = srv.mod_ini_configs.setdefault(mod_id, {})
                cfg[ini_key] = sections_to_ini_text(secs)

            # Atualiza custom_ini_sections
            srv.custom_ini_sections[file_key] = custom_secs

        self.config_manager.update_server(srv)

        # Aplica nos arquivos .ini se o diretório existir
        applied = False
        if srv.install_dir and os.path.isdir(srv.install_dir):
            try:
                combined = dict(srv.mod_ini_configs)
                custom_gus = sections_to_ini_text(srv.custom_ini_sections.get("gus", []))
                custom_game = sections_to_ini_text(srv.custom_ini_sections.get("game", []))
                if custom_gus or custom_game:
                    combined["_custom_"] = {"gus_ini": custom_gus, "game_ini": custom_game}
                ArkIniManager(srv.install_dir).apply_mod_ini_configs(combined)
                applied = True
            except Exception as exc:
                self._global_log(f"Erro ao aplicar INI de mods: {exc}", "error")

        msg = "Seções INI salvas com sucesso!"
        if applied:
            msg += "\n\nAplicadas nos arquivos .ini do servidor."
        else:
            msg += ("\n\nAs seções serão aplicadas nos arquivos .ini\n"
                    "na próxima vez que o servidor for iniciado\n"
                    "ou quando você clicar em 'Salvar e Aplicar' no diálogo de mod.")
        messagebox.showinfo("INI Salvo", msg, parent=self)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Histórico de Alterações
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_historico(self, parent, srv: ServerConfig) -> None:
        """Exibe o histórico de alterações de configuração do servidor."""
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        # ── Barra de controles ────────────────────────────────────────────────
        bar = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=8)
        bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))

        ctk.CTkLabel(bar, text="📋 Histórico de alterações",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#c0c0d8").pack(side="left", padx=12, pady=8)

        filter_var = tk.StringVar(value="Todas as abas")
        tabs_filter = ["Todas as abas", "Geral", "Jogo", "Avançado"]
        filter_menu = ctk.CTkOptionMenu(bar, variable=filter_var, values=tabs_filter,
                                        width=140, height=28,
                                        fg_color="#2a2a2a", button_color="#3a3a3a",
                                        font=ctk.CTkFont(size=11),
                                        command=lambda _: self._historico_refresh(srv.id, filter_var))
        filter_menu.pack(side="left", padx=(0, 8), pady=8)

        ctk.CTkButton(bar, text="🔁 Atualizar", width=100, height=28,
                      fg_color="#2a2a2a", hover_color="#404040",
                      font=ctk.CTkFont(size=11),
                      command=lambda: self._historico_refresh(srv.id, filter_var)
                      ).pack(side="left", pady=8)

        ctk.CTkButton(bar, text="🗑 Limpar histórico", width=140, height=28,
                      fg_color=_RED_DARK, hover_color=_RED_HOVER,
                      font=ctk.CTkFont(size=11),
                      command=lambda: self._historico_clear(srv.id, filter_var)
                      ).pack(side="right", padx=8, pady=8)

        # ── Textbox de exibição ───────────────────────────────────────────────
        tw = ctk.CTkTextbox(parent, state="disabled", font=ctk.CTkFont(family="Consolas", size=11),
                            fg_color=_BG, text_color="#d0d0e0", corner_radius=8,
                            wrap="none")
        tw.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        # Tags de formatação
        tw.tag_config("ts",    foreground="#7070a0")
        tw.tag_config("tab",   foreground="#5080c0")
        tw.tag_config("label", foreground="#c0c0d8")
        tw.tag_config("arrow", foreground="#606060")
        tw.tag_config("old",   foreground="#c07070")
        tw.tag_config("new",   foreground="#70c070")
        tw.tag_config("empty", foreground="#404050")

        self._server_widgets[srv.id]["_historico_tw"] = tw
        self._server_widgets[srv.id]["_historico_filter_var"] = filter_var
        self._historico_refresh(srv.id, filter_var)

    def _historico_refresh(self, server_id: str, filter_var: tk.StringVar) -> None:
        """Recarrega e exibe as entradas do histórico."""
        w = self._server_widgets.get(server_id, {})
        tw = w.get("_historico_tw")
        if tw is None:
            return
        logger = self._get_change_logger(server_id)
        entries = logger.read_all()

        f_tab = filter_var.get() if filter_var.get() != "Todas as abas" else None
        if f_tab:
            entries = [e for e in entries if e.get("tab") == f_tab]

        tw.configure(state="normal")
        tw.delete("1.0", "end")

        if not entries:
            tw.insert("end", "\n  Nenhuma alteração registrada ainda.\n\n", "empty")
            tw.insert("end", "  As configurações são registradas automaticamente\n"
                             "  cada vez que você salva o servidor (💾 Salvar).\n", "empty")
        else:
            for entry in entries:
                tw.insert("end", f"[{entry.get('ts','??')}]", "ts")
                tw.insert("end", f"  {entry.get('tab','?')}", "tab")
                tw.insert("end", f"  ›  {entry.get('label','?')}", "label")
                tw.insert("end", "   ", "arrow")
                tw.insert("end", entry.get("old", ""), "old")
                tw.insert("end", " → ", "arrow")
                tw.insert("end", entry.get("new", ""), "new")
                tw.insert("end", "\n")
        tw.configure(state="disabled")

    def _historico_clear(self, server_id: str, filter_var: tk.StringVar) -> None:
        """Limpa o arquivo de log após confirmação."""
        if not messagebox.askyesno(
            "Limpar histórico",
            "Tem certeza que deseja apagar todo o histórico\nde alterações deste servidor?",
            parent=self,
        ):
            return
        self._get_change_logger(server_id).clear()
        self._historico_refresh(server_id, filter_var)

    def _get_change_logger(self, server_id: str) -> ChangeLogger:
        """Retorna (ou cria) o ChangeLogger para o servidor."""
        if not hasattr(self, "_change_loggers"):
            self._change_loggers: dict = {}
        if server_id not in self._change_loggers:
            log_dir = Path(os.environ.get("APPDATA", "~")).expanduser() \
                / "ARKLAND-ServerManager" / "logs"
            self._change_loggers[server_id] = ChangeLogger(log_dir, server_id)
        return self._change_loggers[server_id]

    # ══════════════════════════════════════════════════════════════════════════
    # Ações de Servidor
    # ══════════════════════════════════════════════════════════════════════════

    def _start_server(self, server_id: str) -> None:
        self._save_server_config(server_id, silent=True)
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return

        # Verifica mods sem arquivo .mod (ARK ignora silenciosamente sem ele)
        if srv.mods and srv.install_dir:
            missing_dot_mod = [
                mid for mid in srv.mods
                if not self.mod_manager.check_mod_installed(srv.install_dir, mid)
            ]
            if missing_dot_mod:
                ids_str = ", ".join(missing_dot_mod)
                ans = messagebox.askyesno(
                    "Mods incompletos",
                    f"Os seguintes mods estão com arquivo .mod ausente e o ARK não os carregará:\n\n"
                    f"{ids_str}\n\n"
                    "Baixe os mods novamente na aba Mods antes de iniciar.\n\n"
                    "Deseja iniciar mesmo assim?",
                    parent=self,
                )
                if not ans:
                    return

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
        _prog_var: Any  = w.get("_install_progress_var")
        _stat_var: Any  = w.get("_status_var")
        _stat_lbl: Any  = w.get("_status_lbl")

        import re as _re
        _PROGRESS_RE = _re.compile(r'progress:\s*([\d.]+)')

        def _set_progress(txt: str) -> None:
            def _do():
                if _prog_var:
                    _prog_var.set(txt)
            self.after(0, _do)

        def _set_header_status(txt: str, color: str) -> None:
            def _do():
                if _stat_var:
                    _stat_var.set(txt)
                if _stat_lbl:
                    _stat_lbl.configure(text_color=color)
            self.after(0, _do)

        def _log(msg: str, level: str = "info") -> None:
            import datetime
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            line = f"[{ts}] {msg}\n"
            m = _PROGRESS_RE.search(msg)
            if m:
                pct = float(m.group(1))
                icon = "🔍" if validate else "⬇️"
                _set_progress(f"{icon}  {pct:.1f}%")
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
            _set_progress("")
            inst_obj = self.server_manager.get_instance(server_id)
            real_st = inst_obj.status if inst_obj else SERVER_STATUS_STOPPED
            _set_header_status(
                _STATUS_LABEL.get(real_st, "PARADO"),
                _STATUS_COLOR.get(real_st, "#ff6666"),
            )
            _set_btns("normal")

        _set_btns("disabled")
        action = "Validando" if validate else "Instalando/Atualizando"
        _set_status(f"⏳  {action}... Aguarde.", "#fbbf24")
        _hdr_txt   = "VALIDANDO" if validate else "ATUALIZANDO"
        _set_header_status(_hdr_txt, "#fbbf24")
        icon = "🔍" if validate else "⬇️"
        _set_progress(f"{icon}  0.0%")

        # Redireciona o log do mod_manager para o log local
        orig_log = self.mod_manager._on_log
        self.mod_manager._on_log = _log
        def _wrapped_done(ok: bool) -> None:
            self.mod_manager._on_log = orig_log
            _on_done(ok)

        self.mod_manager.install_server(install_dir, validate=validate, on_done=_wrapped_done)

    def _save_server_config(self, server_id: str, silent: bool = False, force: bool = False) -> None:
        """Lê todos os widgets do servidor, salva no config e escreve os .ini."""
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return

        # Bloqueia salvamento se o servidor não estiver parado (a menos que force=True)
        if not force:
            inst = self.server_manager.get_instance(server_id)
            if inst and inst.status != SERVER_STATUS_STOPPED:
                if not silent:
                    messagebox.showwarning(
                        "Servidor em execução",
                        "Pare o servidor antes de salvar as configurações.",
                        parent=self,
                    )
                return

        w = self._server_widgets.get(server_id, {})

        # Snapshot antes das alterações (para o log)
        _snap_before = snapshot_server(srv)

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
            srv.public_ip             = w.get("public_ip", tk.StringVar()).get().strip()
            srv.extra_args            = w.get("extra_args",    tk.StringVar()).get().strip()
            _evt_raw = w.get("active_event", tk.StringVar()).get().strip()
            srv.active_event          = _ARK_EVENT_LABEL_TO_ID.get(_evt_raw, _evt_raw)
            try:
                srv.auto_save_period  = float(w.get("auto_save", tk.StringVar(value="15")).get())
            except ValueError:
                pass
            # MOTD
            motd_box = w.get("motd")
            if motd_box:
                srv.motd = motd_box.get("1.0", "end").rstrip("\n")
            try:
                srv.motd_duration = int(w.get("motd_duration", tk.StringVar(value="60")).get())
            except ValueError:
                pass
            srv.rcon_enabled          = w.get("rcon_enabled",       tk.BooleanVar(value=True)).get()
            srv.use_battleye          = w.get("use_battleye",        tk.BooleanVar()).get()
            srv.use_allcores          = w.get("use_allcores",        tk.BooleanVar()).get()
            srv.force_respawn_dinos   = w.get("force_respawn",       tk.BooleanVar()).get()
            srv.whitelist_only        = w.get("whitelist_only",      tk.BooleanVar()).get()
            srv.auto_restart_on_crash = w.get("auto_restart_crash",  tk.BooleanVar()).get()
            srv.auto_update_on_start  = w.get("auto_update_start",   tk.BooleanVar()).get()
            _cpu_sel = w.get("cpu_core_count", tk.StringVar(value="Padrão (ARK decide)")).get()
            if _cpu_sel.startswith("Todos"):
                srv.cpu_core_count = -1
                srv.use_allcores   = True
            elif _cpu_sel[0].isdigit():
                srv.cpu_core_count = int(_cpu_sel.split()[0])
                srv.use_allcores   = False
            else:
                srv.cpu_core_count = 0
                srv.use_allcores   = False

            # Agendamentos
            _sched_rows = w.get("sched_task_rows", [])
            _al_inv = {"Reiniciar": "restart", "Desligar": "stop", "Atualizar + Reiniciar": "update_restart"}
            _new_tasks = []
            for rd in _sched_rows:
                try:
                    _new_tasks.append({
                        "enabled": rd["enabled"].get(),
                        "time": rd["time"].get().strip() or "03:00",
                        "days": [d for d, bv in enumerate(rd["days"]) if bv.get()],
                        "action": _al_inv.get(rd["action"].get(), rd["action"].get()),
                        "warn_minutes": int(rd["warn"].get() or "0"),
                    })
                except Exception:
                    pass
            srv.scheduled_tasks = _new_tasks

        # Preserva as configurações de backup (gerenciadas pela aba Backup)
        # — não sobrescreve campos backup ao salvar outras abas

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
            "player_level_cap", "dino_level_cap",
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

        # ── PerLevelStatsMultiplier ────────────────────────────────────────────
        for group, attr in [
            ("tamed",          "per_level_stats_mult_dino_tamed"),
            ("tamed_add",      "per_level_stats_mult_dino_tamed_add"),
            ("tamed_affinity", "per_level_stats_mult_dino_tamed_affinity"),
            ("wild",           "per_level_stats_mult_dino_wild"),
            ("player",         "per_level_stats_mult_player"),
        ]:
            vals = list(getattr(gs, attr))
            for i in range(12):
                key = f"gs_plsm_{group}_{i}"
                if key in w:
                    try:
                        vals[i] = max(0.0, float(w[key].get()))
                    except (ValueError, TypeError):
                        pass
            setattr(gs, attr, vals)

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

        # ── Spawn de Dinos (aba Spawns) ───────────────────────────────────
        def _collect_spawn_list(store_key: str, is_override: bool) -> list:
            result = []
            for cd in w.get(store_key, []):
                container_var = cd.get("container_var")
                if container_var is None:
                    continue
                container_class = container_var.get().strip()
                if not container_class:
                    continue
                entries = []
                for ed in cd.get("entries", []):
                    name   = ed.get("name_var", tk.StringVar()).get().strip()
                    try:
                        weight = float(ed.get("weight_var", tk.StringVar(value="1.0")).get())
                    except (ValueError, TypeError):
                        weight = 1.0
                    bp_box = ed.get("bp_box")
                    if bp_box:
                        bps_raw = bp_box.get("1.0", "end").strip()
                    else:
                        bps_raw = ""
                    blueprints = [b.strip() for b in bps_raw.splitlines() if b.strip()]
                    if name or blueprints:
                        entries.append({"name": name, "weight": weight, "blueprints": blueprints})
                mult = 1.0
                if is_override:
                    try:
                        mult = float(cd.get("max_mult_var", tk.StringVar(value="1.0")).get())
                    except (ValueError, TypeError):
                        mult = 1.0
                result.append({
                    "container": container_class,
                    "max_enemies_multiplier": mult,
                    "entries": entries,
                })
            return result

        adv.npc_spawn_entries_add      = _collect_spawn_list("spawn_add_list",      is_override=False)
        adv.npc_spawn_entries_override = _collect_spawn_list("spawn_override_list", is_override=True)

        # ── Multiplicadores por Classe de Dino ────────────────────────────────
        def _collect_dino_mult(store_key: str) -> list:
            result = []
            for rd in w.get(store_key, []):
                class_name = rd.get("class_name_var", tk.StringVar()).get().strip()
                if not class_name:
                    continue
                try:
                    mult = float(rd.get("mult_var", tk.StringVar(value="1.0")).get())
                except ValueError:
                    mult = 1.0
                result.append({"class_name": class_name, "multiplier": mult})
            return result

        adv.dino_class_resistance_multipliers       = _collect_dino_mult("dino_res_mult_list")
        adv.dino_class_damage_multipliers           = _collect_dino_mult("dino_dmg_mult_list")
        adv.tamed_dino_class_resistance_multipliers = _collect_dino_mult("tamed_dino_res_mult_list")
        adv.tamed_dino_class_damage_multipliers     = _collect_dino_mult("tamed_dino_dmg_mult_list")

        # ── Supply Crate Overrides ────────────────────────────────────────────
        def _collect_loot_crates() -> list:
            result = []
            for cd in w.get("loot_crate_list", []):
                crate_class = cd.get("crate_class_var", tk.StringVar()).get().strip()
                if not crate_class:
                    continue
                try:
                    min_sets = int(cd.get("min_sets_var", tk.StringVar(value="1")).get())
                except ValueError:
                    min_sets = 1
                try:
                    max_sets = int(cd.get("max_sets_var", tk.StringVar(value="1")).get())
                except ValueError:
                    max_sets = 1
                try:
                    num_sets_pow = float(cd.get("num_sets_power_var", tk.StringVar(value="1.0")).get())
                except ValueError:
                    num_sets_pow = 1.0
                sets_no_repl = cd.get("sets_no_repl_var", tk.BooleanVar(value=True)).get()

                item_sets = []
                for isd in cd.get("item_sets", []):
                    try:
                        sw = float(isd.get("set_weight_var", tk.StringVar(value="1.0")).get())
                    except ValueError:
                        sw = 1.0
                    try:
                        mi = int(isd.get("min_items_var", tk.StringVar(value="1")).get())
                    except ValueError:
                        mi = 1
                    try:
                        mx = int(isd.get("max_items_var", tk.StringVar(value="2")).get())
                    except ValueError:
                        mx = 2
                    try:
                        pow_ = float(isd.get("num_items_power_var", tk.StringVar(value="1.0")).get())
                    except ValueError:
                        pow_ = 1.0
                    items_no_repl = isd.get("items_no_repl_var", tk.BooleanVar(value=True)).get()

                    entries = []
                    for ed in isd.get("entries", []):
                        try:
                            ew = float(ed.get("weight_var", tk.StringVar(value="1.0")).get())
                        except ValueError:
                            ew = 1.0
                        ib = ed.get("items_box")
                        items_raw = ib.get("1.0", "end").strip() if ib else ""
                        items_list = [x.strip() for x in items_raw.splitlines() if x.strip()]
                        if not items_list:
                            continue
                        try:
                            min_q = float(ed.get("min_qty_var", tk.StringVar(value="1.0")).get())
                        except ValueError:
                            min_q = 1.0
                        try:
                            max_q = float(ed.get("max_qty_var", tk.StringVar(value="1.0")).get())
                        except ValueError:
                            max_q = 1.0
                        try:
                            min_ql = float(ed.get("min_ql_var", tk.StringVar(value="1.0")).get())
                        except ValueError:
                            min_ql = 1.0
                        try:
                            max_ql = float(ed.get("max_ql_var", tk.StringVar(value="1.0")).get())
                        except ValueError:
                            max_ql = 1.0
                        fbp = ed.get("force_bp_var", tk.BooleanVar(value=False)).get()
                        try:
                            bpc = float(ed.get("bp_chance_var", tk.StringVar(value="0.0")).get())
                        except ValueError:
                            bpc = 0.0
                        entries.append({
                            "weight": ew, "items": items_list,
                            "min_qty": min_q, "max_qty": max_q,
                            "min_quality": min_ql, "max_quality": max_ql,
                            "force_blueprint": fbp, "blueprint_chance": bpc,
                        })

                    item_sets.append({
                        "min_items": mi, "max_items": mx,
                        "num_items_power": pow_, "set_weight": sw,
                        "items_no_replacement": items_no_repl, "entries": entries,
                    })

                result.append({
                    "crate_class": crate_class,
                    "min_sets": min_sets, "max_sets": max_sets,
                    "num_sets_power": num_sets_pow,
                    "sets_no_replacement": sets_no_repl,
                    "item_sets": item_sets,
                })
            return result

        adv.supply_crate_overrides = _collect_loot_crates()

        # ── Cluster ───────────────────────────────────────────────────────
        cl = srv.cluster
        if "cl_enabled" in w:
            cl.enabled              = bool(w["cl_enabled"].get())
            cl.cluster_id           = w.get("cl_cluster_id",  tk.StringVar()).get().strip()
            cl.cluster_dir_override = w.get("cl_cluster_dir", tk.StringVar()).get().strip()
            srv.alt_save_directory_name = w.get("cl_alt_save_dir", tk.StringVar()).get().strip()
        # Perfil de cluster vinculado
        if "cl_profile_id_var" in w:
            srv.cluster_profile_id = w["cl_profile_id_var"].get()

        # ── Config Dinâmica ───────────────────────────────────────────────
        if "dynamic_config_enabled" in w:
            srv.dynamic_config_enabled = bool(w["dynamic_config_enabled"].get())
        if srv.dynamic_config_enabled:
            self._push_dynamic_config(srv.id)
        else:
            self._dynamic_config_server.remove(srv.id)
            url_var = w.get("_dyn_url_var")
            if url_var:
                url_var.set("—")

        # Atualiza título do painel
        if "_name_title_var" in w:
            w["_name_title_var"].set(srv.name)

        # Persiste
        self.config_manager.update_server(srv)
        self.server_manager.update_server_config(srv)

        # Registra alterações no histórico
        try:
            _snap_after = snapshot_server(srv)
            _chg_logger = self._get_change_logger(server_id)
            diff_snapshots(_chg_logger, _snap_before, _snap_after)
        except Exception:
            pass

        # Escreve .ini se o diretório existir
        if srv.install_dir and os.path.isdir(srv.install_dir):
            try:
                ini_mgr = ArkIniManager(srv.install_dir)
                ini_mgr.save_all(srv)
            except Exception as exc:
                self._global_log(f"Erro ao salvar .ini para {srv.name}: {exc}", "error")

            # Grava AllowedCheaterSteamIDs.txt
            # Localização correta: ShooterGame/Saved/
            try:
                import pathlib
                allowed_path = (
                    pathlib.Path(srv.install_dir)
                    / "ShooterGame" / "Saved"
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
                import shutil
                from .ark_ini import (
                    populate_config_from_gus,
                    populate_config_from_game_ini,
                    populate_custom_game_ini_from_file,
                    read_ini_with_fallback,
                    find_startup_bat,
                    parse_cmdline_args,
                    apply_cmdline_args_to_config,
                    get_ini_path,
                )
                p_gus = Path(src_folder) / "GameUserSettings.ini"
                if p_gus.exists():
                    parser = read_ini_with_fallback(p_gus, strict=False)
                    populate_config_from_gus(parser, target_srv)

                p_game = Path(src_folder) / "Game.ini"
                if p_game.exists():
                    parser2 = read_ini_with_fallback(p_game, strict=False)
                    populate_config_from_game_ini(parser2, target_srv)
                    populate_custom_game_ini_from_file(p_game, target_srv)

                # Complementa com args de linha de comando do .bat de startup,
                # que têm precedência sobre o INI no ARK (ex: breed multipliers)
                bat = find_startup_bat(Path(src_folder))
                if bat:
                    try:
                        bat_text = bat.read_text(encoding="utf-8", errors="replace")
                        cmdline_args = parse_cmdline_args(bat_text)
                        apply_cmdline_args_to_config(cmdline_args, target_srv)
                    except OSError:
                        pass

                # ── Copia os arquivos brutos para o diretório do servidor ────────
                # Preserva seções de mods (ex: [StructuresPlus], [DinoStorage2])
                # que o app não conhece, evitando que sejam perdidas ao salvar.
                if target_srv.install_dir:
                    dst_gus  = get_ini_path(target_srv.install_dir, "GameUserSettings.ini")
                    dst_game = get_ini_path(target_srv.install_dir, "Game.ini")
                    if p_gus.exists() and dst_gus.resolve() != p_gus.resolve():
                        dst_gus.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(p_gus), str(dst_gus))
                    if p_game.exists() and dst_game.resolve() != p_game.resolve():
                        dst_game.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(p_game), str(dst_game))

            # Desabilita o botão de importar e mostra feedback visual
            import_btn.configure(state="disabled", text="⏳  Importando...")
            btn_cancel.configure(state="disabled")

            import threading

            def _worker():
                try:
                    _load_from_folder(srv, folder)
                    err = None
                except Exception as exc:
                    err = exc

                def _on_done():
                    if err is not None:
                        import_btn.configure(state="normal", text="⬆️  Importar")
                        btn_cancel.configure(state="normal")
                        messagebox.showerror("Erro ao importar", str(err), parent=dlg)
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
                        "Configurações importadas com sucesso!\n\nArquivos lidos:\n  " + "\n  ".join(found) + f"\n\nDe: {folder}"
                        "\n\n⚠️  Confira as portas (Servidor, Query e RCON) na aba Geral — "
                        "cada servidor precisa usar portas únicas para evitar conflitos.",
                        parent=self,
                    )

                self.after(0, _on_done)

            threading.Thread(target=_worker, daemon=True).start()

        btn_cancel = ctk.CTkButton(
            btn_fr, text="Cancelar", width=100, height=36,
            fg_color="gray30", hover_color="gray40",
            command=dlg.destroy,
        )
        btn_cancel.pack(side="left", padx=(0, 8))
        import_btn = ctk.CTkButton(
            btn_fr, text="⬆️  Importar", width=130, height=36,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            command=_do_import,
        )
        import_btn.pack(side="left")

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

    def _open_clone_config_dialog(self, source_server_id: str) -> None:
        """Copia TODAS as configurações de um servidor para outros,
        preservando apenas: nome interno, install_dir, session name e portas."""
        import copy
        src = self.config_manager.get_server(source_server_id)
        if not src:
            return

        other_servers = [s for s in self.config_manager.servers if s.id != source_server_id]
        if not other_servers:
            messagebox.showinfo("Sem outros servidores",
                                "Nenhum outro servidor cadastrado.", parent=self)
            return

        dlg = ctk.CTkToplevel(self)
        dlg.title("Clonar Configurações")
        dlg.geometry("500x440")
        dlg.resizable(False, False)
        dlg.grab_set()

        ctk.CTkLabel(
            dlg, text=f"Clonar configurações de  '{src.name}'  para:",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(padx=24, pady=(20, 4), anchor="w")

        ctk.CTkLabel(
            dlg,
            text="Serão copiados: mapa, senhas, mods, multiplicadores, configurações\n"
                 "avançadas, cluster, admins, backup e argumentos extras.\n"
                 "Preservados no destino: nome, diretório, session name e portas.",
            text_color="gray55", font=ctk.CTkFont(size=10), justify="left",
        ).pack(padx=24, pady=(0, 12), anchor="w")

        chk_vars: dict = {}
        scroll_f = ctk.CTkScrollableFrame(dlg, fg_color="transparent", height=220)
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
            ctk.CTkLabel(
                row_f,
                text=s.install_dir if s.install_dir else "(sem diretório)",
                text_color="gray45" if s.install_dir else "#ff6666",
                font=ctk.CTkFont(size=10),
            ).pack(side="left", padx=(4, 0))

        btn_row = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_row.pack(pady=(12, 20))

        def _do_clone():
            targets = [s for s in other_servers if chk_vars[s.id].get()]
            if not targets:
                messagebox.showwarning("Nada selecionado",
                                       "Selecione ao menos um servidor.", parent=dlg)
                return

            # Campos que NÃO devem ser copiados (identidade do servidor destino)
            _KEEP = {"id", "name", "install_dir", "server_name",
                     "server_port", "query_port", "rcon_port"}

            src_dict = src.to_dict()
            updated = 0
            for dst in targets:
                dst_dict = dst.to_dict()
                # Sobrescreve tudo exceto os campos de identidade
                merged = {k: (dst_dict[k] if k in _KEEP else copy.deepcopy(v))
                          for k, v in src_dict.items()}
                new_cfg = type(dst).from_dict(merged)
                self.config_manager.update_server(new_cfg)
                # Atualiza o server_manager com a nova config
                self.server_manager.update_server_config(new_cfg)
                # Reconstrói o painel do servidor destino se ele estiver criado
                frame_key = f"server_{dst.id}"
                if frame_key in self._frames:
                    self._rebuild_server_panel(dst.id)
                updated += 1

            dlg.destroy()
            messagebox.showinfo(
                "Clonagem concluída",
                f"Configurações copiadas para {updated} servidor(es).\n"
                "Salve cada servidor para gerar os arquivos .ini no disco.",
                parent=self,
            )

        ctk.CTkButton(
            btn_row, text="📋  Clonar", width=130, height=38,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=_do_clone,
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

    def _clear_all_mods(self, server_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        if not srv or not srv.mods:
            return
        count = len(srv.mods)
        if not messagebox.askyesno(
            "Apagar todos os mods",
            f"Remover todos os {count} mod(s) da lista do servidor?\n\nEsta ação não desinstala os arquivos do disco.",
        ):
            return
        srv.mods.clear()
        srv.mod_names.clear()
        srv.mod_ini_configs.clear()
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

        # ── Picker de seções cadastradas ──────────────────────────────────────
        def _show_section_picker(target_box: ctk.CTkTextbox) -> None:
            """Abre popup com as seções cadastradas no painel INI para inserção."""
            all_secs: list = []
            for fk, src_label in [("game", "Game.ini"), ("gus", "GUS.ini")]:
                for sec in srv.custom_ini_sections.get(fk, []):
                    all_secs.append({
                        "section": sec.get("section", ""),
                        "entries": sec.get("entries", []),
                        "source":  src_label,
                    })

            if not all_secs:
                messagebox.showinfo(
                    "Seções", "Nenhuma seção personalizada cadastrada no painel INI.",
                    parent=dlg,
                )
                return

            picker = ctk.CTkToplevel(dlg)
            picker.title("Inserir seções cadastradas")
            picker.geometry("440x420")
            picker.resizable(True, True)
            picker.grab_set()
            picker.grid_columnconfigure(0, weight=1)
            picker.grid_rowconfigure(1, weight=1)

            ctk.CTkLabel(
                picker, text="Selecione as seções a inserir:",
                font=ctk.CTkFont(size=13, weight="bold"),
            ).grid(row=0, column=0, padx=16, pady=(14, 4), sticky="w")

            scroll = ctk.CTkScrollableFrame(picker, fg_color="transparent")
            scroll.grid(row=1, column=0, padx=12, pady=4, sticky="nsew")
            scroll.grid_columnconfigure(0, weight=1)

            check_vars: list = []
            for sec in all_secs:
                var = tk.BooleanVar(value=False)
                sec["_var"] = var
                check_vars.append(var)
                row_fr = ctk.CTkFrame(scroll, fg_color=_CARD_BG, corner_radius=6)
                row_fr.pack(fill="x", pady=2, padx=2)
                row_fr.grid_columnconfigure(1, weight=1)
                ctk.CTkCheckBox(
                    row_fr, text="", variable=var, width=28,
                    checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                ).grid(row=0, column=0, padx=(8, 0), pady=6)
                ctk.CTkLabel(
                    row_fr,
                    text=f"[{sec['section']}]",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    anchor="w",
                ).grid(row=0, column=1, padx=(6, 4), pady=6, sticky="w")
                ctk.CTkLabel(
                    row_fr,
                    text=sec["source"],
                    font=ctk.CTkFont(size=10),
                    text_color="gray50",
                    anchor="e",
                ).grid(row=0, column=2, padx=(0, 10), pady=6, sticky="e")

            btn_fr2 = ctk.CTkFrame(picker, fg_color="transparent")
            btn_fr2.grid(row=2, column=0, padx=16, pady=(4, 14), sticky="e")

            def _insert() -> None:
                selected = [s for s in all_secs if s.get("_var") and s["_var"].get()]
                if not selected:
                    messagebox.showwarning("Inserir", "Selecione ao menos uma seção.", parent=picker)
                    return
                lines: list[str] = []
                for s in selected:
                    lines.append(sections_to_ini_text([
                        {"section": s["section"], "entries": s["entries"]}
                    ]).strip())
                insert_text = "\n\n".join(lines)
                existing = target_box.get("0.0", "end").strip()
                target_box.delete("0.0", "end")
                target_box.insert("0.0", (existing + "\n\n" + insert_text).strip() if existing else insert_text)
                picker.destroy()

            ctk.CTkButton(
                btn_fr2, text="Cancelar", width=90, height=32,
                fg_color="gray30", hover_color="gray40",
                command=picker.destroy,
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                btn_fr2, text="✅  Inserir selecionadas", width=180, height=32,
                fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                command=_insert,
            ).pack(side="left")

        # ── Game.ini ──────────────────────────────────────────────────────────
        game_hdr = ctk.CTkFrame(dlg, fg_color="transparent")
        game_hdr.grid(row=3, column=0, padx=20, pady=(4, 2), sticky="ew")
        game_hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            game_hdr, text="📄  Game.ini",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            game_hdr, text="📋  Inserir seção...", width=150, height=26,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            font=ctk.CTkFont(size=11),
            command=lambda: _show_section_picker(game_ini_box),
        ).grid(row=0, column=1, sticky="e")

        game_ini_box = ctk.CTkTextbox(dlg, font=ctk.CTkFont(family="Courier New", size=12))
        game_ini_box.grid(row=4, column=0, padx=20, pady=(0, 8), sticky="nsew")
        game_ini_box.insert("0.0", cfg.get("game_ini", ""))
        dlg.grid_rowconfigure(4, weight=1)

        # ── GameUserSettings.ini ──────────────────────────────────────────────
        gus_hdr = ctk.CTkFrame(dlg, fg_color="transparent")
        gus_hdr.grid(row=5, column=0, padx=20, pady=(4, 2), sticky="ew")
        gus_hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            gus_hdr, text="📄  GameUserSettings.ini",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            gus_hdr, text="📋  Inserir seção...", width=150, height=26,
            fg_color=_BLUE, hover_color=_BLUE_HOVER,
            font=ctk.CTkFont(size=11),
            command=lambda: _show_section_picker(gus_ini_box),
        ).grid(row=0, column=1, sticky="e")

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
            on_done=lambda ok: self.after(0, lambda: self._refresh_mods_list(server_id)),  # type: ignore[arg-type]
        )

    def _download_all_mods(self, server_id: str) -> None:
        srv = self.config_manager.get_server(server_id)
        if not srv or not srv.mods:
            messagebox.showinfo("Mods", "Nenhum mod para baixar.", parent=self)
            return
        self.mod_manager.steamcmd_path = self.config_manager.config.steamcmd_path
        self.mod_manager.download_mods(
            srv.mods, srv.install_dir,
            on_done=lambda ok: self.after(0, lambda: self._refresh_mods_list(server_id)),  # type: ignore[arg-type]
        )

    def _open_workshop_page(self, mod_id: str) -> None:
        import webbrowser
        webbrowser.open(self.mod_manager.get_mod_workshop_url(mod_id))

    # ── RCON ──────────────────────────────────────────────────────────────────

    # ── RCON auto-reconexão ───────────────────────────────────────────────────

    def _rcon_cancel_auto_job(self, server_id: str) -> None:
        job = self._rcon_auto_jobs.pop(server_id, None)
        if job:
            try:
                self.after_cancel(job)
            except Exception:
                pass

    def _rcon_schedule_auto_connect(self, server_id: str, delay_ms: int = 15_000) -> None:
        self._rcon_cancel_auto_job(server_id)
        job = self.after(delay_ms, lambda: self._rcon_auto_connect_tick(server_id))
        self._rcon_auto_jobs[server_id] = job

    def _rcon_auto_connect_tick(self, server_id: str) -> None:
        """Tenta conectar o RCON silenciosamente se o servidor estiver RUNNING e sem conexão."""
        self._rcon_auto_jobs.pop(server_id, None)

        if not self._rcon_auto_enabled.get(server_id):
            return

        # Se já está conectado, apenas reagenda a verificação
        client = self._rcon_clients.get(server_id)
        if client and client.is_connected:
            self._rcon_schedule_auto_connect(server_id, delay_ms=15_000)
            return

        srv = self.config_manager.get_server(server_id)
        if not srv:
            return

        w        = self._server_widgets.get(server_id, {})
        host     = w.get("rcon_host", tk.StringVar(value="127.0.0.1")).get() or "127.0.0.1"
        port_str = w.get("rcon_port_entry", tk.StringVar(value=str(srv.rcon_port))).get()
        password = srv.rcon_password or srv.admin_password
        try:
            port = int(port_str)
        except ValueError:
            port = srv.rcon_port

        def _try():
            new_client = RconClient(
                host, port, password,
                on_log=lambda m, level: self._global_log(f"[RCON] {m}", level),
            )
            try:
                new_client.connect()
                def _ok():
                    if not self._rcon_auto_enabled.get(server_id):
                        try:
                            new_client.disconnect()
                        except Exception:
                            pass
                        return
                    self._rcon_clients[server_id] = new_client
                    sv = w.get("rcon_status_var")
                    cb = w.get("rcon_connect_btn")
                    if sv:
                        sv.set(f"🟢 Conectado a {host}:{port}")
                    if cb:
                        cb.configure(text="🔌 Desconectar",
                                     fg_color=_RED_DARK, hover_color=_RED_HOVER)
                    self._rcon_append(server_id, f"[Auto] Conectado a {host}:{port}\n", "sys")
                    # reagenda verificação de keep-alive
                    self._rcon_schedule_auto_connect(server_id, delay_ms=15_000)
                self.after(0, _ok)
            except Exception:
                # falha silenciosa — tenta de novo em 15s
                def _retry():
                    if self._rcon_auto_enabled.get(server_id):
                        self._rcon_schedule_auto_connect(server_id, delay_ms=15_000)
                self.after(0, _retry)

        threading.Thread(target=_try, daemon=True).start()

    # ── RCON manual ──────────────────────────────────────────────────────────

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
            # Desconexão manual: desativa auto-connect e cancela o loop
            self._rcon_auto_enabled[server_id] = False
            self._rcon_cancel_auto_job(server_id)
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

    # ── Chat público ──────────────────────────────────────────────────────────

    def _chat_append(self, server_id: str, text: str, tag: str = "message") -> None:
        w = self._server_widgets.get(server_id, {})
        box: Optional[ctk.CTkTextbox] = w.get("chat_box")
        if not box:
            return
        box.configure(state="normal")
        box._textbox.insert("end", text, tag)
        box._textbox.see("end")
        box.configure(state="disabled")

    def _chat_clear(self, server_id: str) -> None:
        w = self._server_widgets.get(server_id, {})
        box: Optional[ctk.CTkTextbox] = w.get("chat_box")
        if not box:
            return
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.configure(state="disabled")

    def _chat_process(self, server_id: str, raw: str) -> None:
        import re
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line or line.lower() == "no chat":
                continue
            # SERVER: message
            m = re.match(r"^SERVER:\s*(.+)$", line, re.IGNORECASE)
            if m:
                self._chat_append(server_id, f"[{ts}] ", "ts")
                self._chat_append(server_id, "[SERVIDOR]", "server")
                self._chat_append(server_id, f": {m.group(1)}\n", "message")
                continue
            # PlayerName (SteamID64): message  or  PlayerName: message
            m = re.match(r"^(.+?)(?:\s+\(\d{17}\))?:\s*(.+)$", line)
            if m:
                self._chat_append(server_id, f"[{ts}] ", "ts")
                self._chat_append(server_id, m.group(1).strip(), "player")
                self._chat_append(server_id, f": {m.group(2).strip()}\n", "message")
            else:
                self._chat_append(server_id, f"[{ts}] {line}\n", "message")

    def _chat_fetch(self, server_id: str) -> None:
        client = self._rcon_clients.get(server_id)
        w = self._server_widgets.get(server_id, {})
        if not client or not client.is_connected:
            self._chat_append(
                server_id,
                "⚠  RCON não conectado. Vá para 'Console RCON' e clique em Conectar primeiro.\n",
                "err",
            )
            # Desativa auto-poll em caso de erro
            if w.get("chat_auto_poll") and w["chat_auto_poll"].get():
                w["chat_auto_poll"].set(False)
                self._chat_cancel_poll(server_id)
            return

        status_var: Optional[tk.StringVar] = w.get("chat_status_var")
        if status_var:
            status_var.set("⏳ Buscando...")

        def _do() -> None:
            ok, result = client.send_command_safe("GetChat")
            from datetime import datetime as _dt
            ts_now = _dt.now().strftime("%H:%M:%S")

            def _apply() -> None:
                if status_var:
                    status_var.set(f"🟢 {ts_now}")
                if ok and result and result.strip().lower() not in ("", "no chat"):
                    self._chat_process(server_id, result)

            self.after(0, _apply)

        threading.Thread(target=_do, daemon=True).start()

    def _chat_send(self, server_id: str) -> None:
        from datetime import datetime
        w = self._server_widgets.get(server_id, {})
        msg = w.get("chat_input", tk.StringVar()).get().strip()
        if not msg:
            return
        w["chat_input"].set("")
        client = self._rcon_clients.get(server_id)
        if not client or not client.is_connected:
            self._chat_append(
                server_id,
                "⚠  RCON não conectado. Vá para 'Console RCON' e clique em Conectar primeiro.\n",
                "err",
            )
            return
        ts = datetime.now().strftime("%H:%M:%S")
        self._chat_append(server_id, f"[{ts}] ", "ts")
        self._chat_append(server_id, "[SERVIDOR]", "server")
        self._chat_append(server_id, f": {msg}\n", "message")
        safe_msg = msg.replace('"', "'")

        def _do() -> None:
            client.send_command_safe(f"ServerChat {safe_msg}")

        threading.Thread(target=_do, daemon=True).start()

    def _chat_toggle_poll(self, server_id: str) -> None:
        w = self._server_widgets.get(server_id, {})
        enabled = w.get("chat_auto_poll", tk.BooleanVar()).get()
        if enabled:
            self._chat_poll_loop(server_id)
        else:
            self._chat_cancel_poll(server_id)
            status_var: Optional[tk.StringVar] = w.get("chat_status_var")
            if status_var:
                status_var.set("⬛ Pausado")

    def _chat_cancel_poll(self, server_id: str) -> None:
        job = self._chat_poll_jobs.pop(server_id, None)
        if job:
            try:
                self.after_cancel(job)
            except Exception:
                pass

    def _chat_poll_loop(self, server_id: str) -> None:
        w = self._server_widgets.get(server_id, {})
        if not w.get("chat_auto_poll", tk.BooleanVar()).get():
            return
        self._chat_fetch(server_id)
        try:
            interval_ms = int(w.get("chat_interval", tk.StringVar(value="5")).get()) * 1000
        except (ValueError, AttributeError):
            interval_ms = 5000
        job = self.after(interval_ms, lambda: self._chat_poll_loop(server_id))
        self._chat_poll_jobs[server_id] = job

    # ── Gerenciamento de Broadcasts ───────────────────────────────────────────

    def _broadcast_rcon(self, server_id: str, message: str) -> None:
        """Envia um Broadcast via RCON para todos os jogadores online."""
        client = self._rcon_clients.get(server_id)
        if not client or not client.is_connected:
            messagebox.showwarning(
                "RCON não conectado",
                "Conecte-se ao RCON na aba 'Console RCON' antes de enviar um broadcast.",
                parent=self,
            )
            return
        safe = message.replace('"', "'")[:900]
        ts = datetime.now().strftime("%H:%M:%S")
        self._chat_append(server_id, f"[{ts}] ", "ts")
        self._chat_append(server_id, "[BROADCAST]", "server")
        self._chat_append(server_id, f": {message}\n", "message")

        def _do() -> None:
            client.send_command_safe(f"Broadcast {safe}")

        threading.Thread(target=_do, daemon=True).start()

    def _broadcast_send_quick(self, server_id: str) -> None:
        """Envia o broadcast da barra de envio rápido."""
        w = self._server_widgets.get(server_id, {})
        msg = w.get("bc_quick_var", tk.StringVar()).get().strip()
        if not msg:
            return
        w["bc_quick_var"].set("")
        self._broadcast_rcon(server_id, msg)

    def _broadcast_add(self, server_id: str) -> None:
        """Adiciona um novo broadcast à biblioteca e persiste."""
        w = self._server_widgets.get(server_id, {})
        label = w.get("bc_new_label", tk.StringVar()).get().strip()
        msg = w.get("bc_new_msg", tk.StringVar()).get().strip()
        if not label or not msg:
            messagebox.showwarning(
                "Campos obrigatórios",
                "Preencha o Rótulo e o Texto do broadcast antes de adicionar.",
                parent=self,
            )
            return
        srv = self.config_manager.get_server(server_id)
        if not srv:
            return
        srv.broadcasts.append({"label": label, "message": msg})
        self.config_manager.update_server(srv)
        w["bc_new_label"].set("")
        w["bc_new_msg"].set("")
        self._broadcast_refresh_list(server_id)

    def _broadcast_delete(self, server_id: str, index: int) -> None:
        """Remove um broadcast da biblioteca pelo índice."""
        srv = self.config_manager.get_server(server_id)
        if not srv or index >= len(srv.broadcasts):
            return
        if not messagebox.askyesno(
            "Remover broadcast",
            f"Remover o broadcast '{srv.broadcasts[index]['label']}'?",
            parent=self,
        ):
            return
        srv.broadcasts.pop(index)
        self.config_manager.update_server(srv)
        self._broadcast_refresh_list(server_id)

    def _broadcast_edit(self, server_id: str, index: int) -> None:
        """Abre diálogo inline para editar rótulo/mensagem de um broadcast salvo."""
        srv = self.config_manager.get_server(server_id)
        if not srv or index >= len(srv.broadcasts):
            return
        bc = srv.broadcasts[index]

        dlg = ctk.CTkToplevel(self)
        dlg.title("Editar Broadcast")
        dlg.geometry("560x180")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(dlg, text="Rótulo:").grid(row=0, column=0, padx=(16, 8), pady=(16, 6), sticky="w")
        lv = tk.StringVar(value=bc["label"])
        ctk.CTkEntry(dlg, textvariable=lv, height=32, font=ctk.CTkFont(size=12)).grid(
            row=0, column=1, sticky="ew", padx=(0, 16), pady=(16, 6))

        ctk.CTkLabel(dlg, text="Mensagem:").grid(row=1, column=0, padx=(16, 8), pady=(0, 6), sticky="w")
        mv = tk.StringVar(value=bc["message"])
        ctk.CTkEntry(dlg, textvariable=mv, height=32, font=ctk.CTkFont(size=12)).grid(
            row=1, column=1, sticky="ew", padx=(0, 16), pady=(0, 6))

        def _save():
            new_label = lv.get().strip()
            new_msg = mv.get().strip()
            if not new_label or not new_msg:
                return
            srv.broadcasts[index] = {"label": new_label, "message": new_msg}
            self.config_manager.update_server(srv)
            self._broadcast_refresh_list(server_id)
            dlg.destroy()

        btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
        btn_fr.grid(row=2, column=0, columnspan=2, pady=(4, 12), padx=16, sticky="e")
        ctk.CTkButton(btn_fr, text="Cancelar", width=90, height=30,
                      fg_color="gray30", hover_color="gray40",
                      command=dlg.destroy).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_fr, text="💾 Salvar", width=100, height=30,
                      fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                      command=_save).pack(side="left")

    def _broadcast_refresh_list(self, server_id: str) -> None:
        """Reconstrói a lista visual de broadcasts da biblioteca."""
        w = self._server_widgets.get(server_id, {})
        scroll = w.get("bc_list_scroll")
        if scroll is None:
            return
        for ch in scroll.winfo_children():
            ch.destroy()

        srv = self.config_manager.get_server(server_id)
        bcs = srv.broadcasts if srv else []

        # Broadcasts do sistema (tarefas agendadas com warn > 0 — somente leitura)
        sys_entries = []
        if srv:
            for task in srv.scheduled_tasks:
                wm = task.get("warn_minutes", 0)
                if wm and wm > 0:
                    action_map = {"restart": "Reiniciar", "stop": "Desligar",
                                  "update_restart": "Atualizar + Reiniciar"}
                    action_lbl = action_map.get(task.get("action", ""), task.get("action", ""))
                    t_time = task.get("time", "??:??")
                    sys_entries.append({
                        "label": f"[Auto] Aviso {action_lbl} às {t_time}",
                        "message": f"⚠ Servidor será {action_lbl} em {wm} minuto(s)!",
                    })
            # MOTD como broadcast
            if srv.motd:
                sys_entries.append({
                    "label": "[Auto] MOTD",
                    "message": srv.motd,
                })

        if not bcs and not sys_entries:
            ctk.CTkLabel(scroll,
                         text="Nenhum broadcast salvo.\n"
                              "Adicione um usando o formulário acima.",
                         text_color="gray40", font=ctk.CTkFont(size=11),
                         justify="center").pack(pady=24)
            return

        # Cabeçalho de colunas
        hdr = ctk.CTkFrame(scroll, fg_color="transparent")
        hdr.pack(fill="x", padx=4, pady=(4, 0))
        hdr.grid_columnconfigure(0, weight=0, minsize=160)
        hdr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(hdr, text="Rótulo", text_color="gray45",
                     font=ctk.CTkFont(size=10, weight="bold")).grid(row=0, column=0, sticky="w", padx=4)
        ctk.CTkLabel(hdr, text="Mensagem", text_color="gray45",
                     font=ctk.CTkFont(size=10, weight="bold")).grid(row=0, column=1, sticky="w", padx=8)

        # Broadcasts do usuário
        for idx, bc in enumerate(bcs):
            self._broadcast_render_row(server_id, scroll, idx, bc, readonly=False)

        # Broadcasts do sistema
        if sys_entries:
            ctk.CTkLabel(scroll, text="Broadcasts automáticos do sistema",
                         text_color="gray40", font=ctk.CTkFont(size=10, weight="bold")
                         ).pack(anchor="w", padx=8, pady=(12, 2))
            for bc in sys_entries:
                self._broadcast_render_row(server_id, scroll, -1, bc, readonly=True)

    def _broadcast_render_row(self, server_id: str, container,
                               index: int, bc: dict, readonly: bool) -> None:
        """Cria uma linha de broadcast na lista."""
        bg = "#252535" if not readonly else "#1e1e2a"
        row = ctk.CTkFrame(container, fg_color=bg, corner_radius=6)
        row.pack(fill="x", padx=4, pady=2)
        row.grid_columnconfigure(1, weight=1)

        # Rótulo
        lbl_color = "#a0a8d0" if not readonly else "#606070"
        ctk.CTkLabel(row, text=bc.get("label", ""), text_color=lbl_color,
                     font=ctk.CTkFont(size=11, weight="bold"),
                     width=160, anchor="w", wraplength=155
                     ).grid(row=0, column=0, sticky="w", padx=(10, 6), pady=6)

        # Mensagem (truncada)
        msg_text = bc.get("message", "")
        display_msg = msg_text if len(msg_text) <= 80 else msg_text[:77] + "..."
        ctk.CTkLabel(row, text=display_msg, text_color="gray55",
                     font=ctk.CTkFont(size=11), anchor="w", wraplength=400
                     ).grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=6)

        # Botões
        btn_fr = ctk.CTkFrame(row, fg_color="transparent")
        btn_fr.grid(row=0, column=2, padx=(4, 8), pady=4)

        ctk.CTkButton(btn_fr, text="📢 Enviar", width=80, height=26,
                      fg_color=_BLUE, hover_color=_BLUE_HOVER,
                      font=ctk.CTkFont(size=10),
                      command=lambda m=msg_text, sid=server_id:
                          self._broadcast_rcon(sid, m)
                      ).pack(side="left", padx=(0, 4))

        if not readonly:
            ctk.CTkButton(btn_fr, text="✏", width=28, height=26,
                          fg_color="#3a3a5a", hover_color="#4a4a7a",
                          font=ctk.CTkFont(size=11),
                          command=lambda i=index, sid=server_id:
                              self._broadcast_edit(sid, i)
                          ).pack(side="left", padx=(0, 4))
            ctk.CTkButton(btn_fr, text="🗑", width=28, height=26,
                          fg_color=_RED_DARK, hover_color=_RED_HOVER,
                          font=ctk.CTkFont(size=11),
                          command=lambda i=index, sid=server_id:
                              self._broadcast_delete(sid, i)
                          ).pack(side="left")

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

            # ── Auto-reconexão RCON ───────────────────────────────────────
            if status == SERVER_STATUS_RUNNING:
                # habilita auto-connect e agenda o primeiro loop
                self._rcon_auto_enabled[server_id] = True
                self._rcon_schedule_auto_connect(server_id, delay_ms=5000)
            elif status == SERVER_STATUS_STOPPED:
                # servidor parou: cancela loop e desconecta RCON
                self._rcon_auto_enabled[server_id] = False
                self._rcon_cancel_auto_job(server_id)
                client = self._rcon_clients.pop(server_id, None)
                if client:
                    try:
                        client.disconnect()
                    except Exception:
                        pass
                w2 = self._server_widgets.get(server_id, {})
                sv2 = w2.get("rcon_status_var")
                cb2 = w2.get("rcon_connect_btn")
                if sv2:
                    sv2.set("⬛ Desconectado")
                if cb2:
                    cb2.configure(text="🔌 Conectar",
                                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER)

            btn = self._sidebar_server_btns.get(server_id)
            if btn:
                dot = getattr(btn, "_status_dot", None)
                if dot:
                    dot.configure(text_color=color)

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

        _CONFIG_TABS = ("Geral", "Jogo", "Avançado", "Spawns", "Loot", "Mods", "Plugins")
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

    # ── Perfil (exportar / importar) ──────────────────────────────────────────

    def _export_profile(self) -> None:
        import datetime
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Exportar Perfil ARKLAND",
            defaultextension=".arkprofile",
            filetypes=[
                ("Perfil ARKLAND", "*.arkprofile"),
                ("JSON", "*.json"),
                ("Todos os arquivos", "*.*"),
            ],
            initialfile=f"arkland-perfil-{datetime.date.today()}.arkprofile",
        )
        if not path:
            return
        try:
            self.config_manager.export_profile(path)
            n = len(self.config_manager.servers)
            messagebox.showinfo(
                "Perfil exportado",
                f"{n} servidor(es) exportado(s) com sucesso:\n{path}",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror("Erro ao exportar", str(exc), parent=self)

    def _import_profile(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Importar Perfil ARKLAND",
            filetypes=[
                ("Perfil ARKLAND", "*.arkprofile"),
                ("JSON", "*.json"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if not path:
            return
        try:
            import json as _json
            with open(path, "r", encoding="utf-8") as fh:
                preview = _json.load(fh)
            servers_raw = preview.get("servers", [])
            count = len(servers_raw)
            if count == 0:
                messagebox.showwarning("Perfil vazio", "O arquivo não contém servidores.", parent=self)
                return
            names_str = "\n".join(f"  • {s.get('name', '?')}" for s in servers_raw[:10])
            if count > 10:
                names_str += f"\n  ... e mais {count - 10}"
            ans = messagebox.askyesnocancel(
                "Importar Perfil",
                f"O perfil contém {count} servidor(es):\n{names_str}\n\n"
                "Sim  → adicionar aos servidores existentes\n"
                "Não  → substituir todos os servidores\n"
                "Cancelar → cancelar",
                parent=self,
            )
            if ans is None:
                return
            replace = not ans  # "Não" = replace=True
            imported = self.config_manager.import_profile(path, replace=replace)
            if replace:
                # Remove instâncias antigas do server_manager
                for inst in self.server_manager.get_all_instances():
                    if inst.status in ("stopped", "crashed"):
                        self.server_manager.remove_server(inst.config.id)
            for srv in imported:
                self.server_manager.add_server(srv)
            self._rebuild_server_sidebar()
            self._refresh_dashboard()
            messagebox.showinfo(
                "Perfil importado",
                f"{len(imported)} servidor(es) importado(s) com sucesso.",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror("Erro ao importar", str(exc), parent=self)

    # ── Configurações Globais ─────────────────────────────────────────────────

    def _save_global_config(self) -> None:
        cfg = self.config_manager.config
        cfg.steamcmd_path        = self._steamcmd_var.get().strip()
        cfg.default_install_dir  = self._default_dir_var.get().strip()
        cfg.startup_with_windows = self._cfg_startup_var.get()
        cfg.minimize_to_tray     = self._cfg_minimize_tray_var.get()
        cfg.log_debug            = self._cfg_log_debug_var.get()
        # Discord
        dc = cfg.discord_notify
        dc.enabled       = self._discord_enabled_var.get()
        dc.webhook_url   = self._discord_url_var.get().strip()
        dc.sender_name   = self._discord_sender_var.get().strip() or "ARKLAND"
        dc.notify_start  = self._discord_notify_start.get()
        dc.notify_stop   = self._discord_notify_stop.get()
        dc.notify_crash  = self._discord_notify_crash.get()
        dc.notify_update = self._discord_notify_update.get()
        dc.notify_backup = self._discord_notify_backup.get()
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
            url, on_result=lambda info: self.after(0, lambda: self._on_update_result(info)))  # type: ignore[arg-type]

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
            on_result=lambda info: self.after(  # type: ignore[arg-type]
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
            on_done=lambda ok, msg: self.after(0, lambda: self._on_download_done(ok, msg)),  # type: ignore[arg-type]
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
            self._do_quit()
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
        prev = self._current_frame
        if prev == name:
            return
        self._current_frame = name

        # Esconde apenas o frame anterior; mostra apenas o novo
        if prev in self._frames:
            self._frames[prev].grid_remove()
        if name in self._frames:
            self._frames[name].grid()

        # Atualiza somente os dois botões afetados
        if prev in self._nav_buttons:
            self._nav_buttons[prev].configure(fg_color="transparent")
        elif prev.startswith("server_"):
            sid = prev[len("server_"):]
            if sid in self._sidebar_server_btns:
                self._sidebar_server_btns[sid].configure(fg_color="transparent")

        if name in self._nav_buttons:
            self._nav_buttons[name].configure(fg_color="#1e2a3a")
        elif name.startswith("server_"):
            sid = name[len("server_"):]
            if sid in self._sidebar_server_btns:
                self._sidebar_server_btns[sid].configure(fg_color="#1e2a3a")

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

    def _on_unmap_event(self, event) -> None:
        """Intercepta o botão − da janela para ir à bandeja se a opção estiver ativa."""
        if event.widget is not self:
            return
        self.after(60, self._check_tray_on_minimize)

    def _check_tray_on_minimize(self) -> None:
        try:
            state = self.state()
        except Exception:
            return
        if state == "iconic" and self.config_manager.config.minimize_to_tray and _PYSTRAY_OK:
            self._minimize_to_tray()

    def _do_quit(self) -> None:
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
            self._tray_icon = None
        if self._sync_engine and self._sync_engine.is_running:
            self._sync_engine.stop()
        for _eng in list(self._cluster_sync_engines.values()):
            if _eng.is_running:
                _eng.stop()
        self._cluster_sync_engines.clear()
        self._dynamic_config_server.stop()
        if self._mod_auto_updater and self._mod_auto_updater.enabled:
            self._mod_auto_updater.stop()
        if self._buff_manager:
            self._buff_manager.stop()
        if self._backup_manager:
            self._backup_manager.shutdown()
        self._perf_running = False
        # Os processos dos servidores (mapas) são mantidos em execução intencionalmente.
        # Apenas recursos internos do app são encerrados.
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

