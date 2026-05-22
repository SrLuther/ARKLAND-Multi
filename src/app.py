"""
Interface gráfica principal do ARKLAND - Server Manager.
"""
from __future__ import annotations

import os
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog
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

try:
    import psutil as _psutil  # type: ignore[reportMissingModuleSource]
    _PSUTIL_OK = True
except ImportError:
    _psutil = None  # type: ignore[assignment]
    _PSUTIL_OK = False

import customtkinter as ctk  # type: ignore[reportMissingImports]

from .config_manager import ConfigManager
from .sync_engine import SyncEngine
from .server_config import ServerConfig
from .server_manager import ServerManager
from .mod_manager import ModManager
from .rcon_client import RconClient
from .updater import UpdateChecker
from .mod_auto_updater import ModAutoUpdater
from .backup_manager import BackupManager
from .discord_notifier import DiscordNotifier
from .buff_manager import BuffManager, BuffEvent, BuffPreset
from .version import APP_VERSION
from .change_logger import ChangeLogger
from .dynamic_config_server import DynamicConfigServer
from .remote_agent import RemoteAgent
from .ui_constants import (
    _GREEN_DARK, _GREEN_HOVER,
    _MAX_SYNC_CYCLES,
    _resource_path,
)

APP_NAME = "ARKLAND - Server Manager"

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
                self.iconphoto(True, self._app_icon)  # type: ignore[arg-type]
            except Exception:
                pass

        # ── Gerenciadores ────────────────────────────────────────────────────
        self.config_manager = ConfigManager()

        self._discord_notifier = DiscordNotifier(self.config_manager.config.discord_notify)

        self.server_manager = ServerManager(
            on_status_change=self._on_server_status_change,
            on_log=self._on_server_log,
            on_visibility_change=self._on_server_visibility_change,
            on_bm_update=self._on_bm_update,
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
        self._perf_cpu_temp_var: Any = None
        self._perf_gpu_temp_var: Any = None
        self._perf_servers_inner: Any = None
        self._perf_server_procs: dict = {}   # server_id → psutil.Process
        self._perf_last_srv_ids: list = []

        self._remote_agent: Optional[RemoteAgent] = None

        self._build_ui()
        self.after(2000, self._scan_running_servers)
        self.after(500, self._auto_start_sync)
        self.after(1600, self._auto_start_cluster_syncs)
        self.after(1700, self._auto_start_dynamic_configs)
        self.after(4000, self._check_updates_on_start)
        self.after(2000, self._start_mod_auto_updater)
        self.after(600, self._init_buff_manager)
        self.after(800, self._init_backup_manager)
        self.after(1200, self._start_perf_monitor)
        self.after(900, self._auto_start_remote_agent)
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
        from .pages.sidebar import build_sidebar
        build_sidebar(self)

    def _rebuild_server_sidebar(self) -> None:
        from .pages.rebuild_server_sidebar import rebuild_server_sidebar
        rebuild_server_sidebar(self)

    # ── Frames estáticos ──────────────────────────────────────────────────────

    def _build_static_frames(self) -> None:
        from .pages.build_static_frames import build_static_frames
        build_static_frames(self)

    # ══════════════════════════════════════════════════════════════════════════
    # Painel de Sincronização
    # ══════════════════════════════════════════════════════════════════════════

    def _build_sync_panel(self, parent: ctk.CTkFrame) -> None:
        from .pages.build_sync_panel import build_sync_panel
        build_sync_panel(self, parent)

    # ── Sync helpers ──────────────────────────────────────────────────────────

    def _browse_sync_folder(self, var: tk.StringVar) -> None:
        d = filedialog.askdirectory(parent=self)
        if d:
            var.set(d)

    # ── Gestão de ciclos ──────────────────────────────────────────────────────

    def _add_sync_cycle(self, initial_paths: Optional[list] = None) -> None:
        from .pages.add_sync_cycle import add_sync_cycle
        add_sync_cycle(self, initial_paths=initial_paths)

    def _remove_sync_cycle(self, card, folder_vars: list) -> None:
        from .pages.remove_sync_cycle import remove_sync_cycle
        remove_sync_cycle(self, card, folder_vars)

    def _add_sync_folder(
        self, folders_frame, folder_vars: list, add_btn, path: str = ""
    ) -> None:
        from .pages.add_sync_folder import add_sync_folder
        add_sync_folder(self, folders_frame, folder_vars, add_btn, path=path)

    def _remove_sync_folder(
        self, folders_frame, folder_vars: list,
        var: tk.StringVar, row_frame, add_btn
    ) -> None:
        from .pages.remove_sync_folder import remove_sync_folder
        remove_sync_folder(self, folders_frame, folder_vars, var, row_frame, add_btn)

    def _refresh_add_cycle_btn(self) -> None:
        """Habilita/desabilita o botão '+ Adicionar Ciclo' conforme o limite."""
        if self._sync_add_cycle_btn:
            state = "normal" if len(self._sync_cycle_vars) < _MAX_SYNC_CYCLES else "disabled"
            self._sync_add_cycle_btn.configure(state=state)

    def _save_sync_config(self) -> None:
        from .pages.save_sync_config import save_sync_config
        save_sync_config(self)

    def _scan_running_servers(self) -> None:
        from .pages.scan_running_servers import scan_running_servers
        scan_running_servers(self)

    def _auto_start_sync(self) -> None:
        from .pages.auto_start_sync import auto_start_sync
        auto_start_sync(self)

    def _auto_start_remote_agent(self) -> None:
        """Inicia o agente remoto automaticamente se habilitado na configuração."""
        if self.config_manager.config.remote_agent_enabled:
            self._start_remote_agent()

    def _start_remote_agent(self) -> None:
        from .pages.start_remote_agent import start_remote_agent
        start_remote_agent(self)

    def _toggle_sync(self) -> None:
        if self._sync_engine and self._sync_engine.is_running:
            self._sync_engine.stop()
        else:
            self._start_sync_engine()

    def _start_sync_engine(self) -> None:
        from .pages.start_sync_engine import start_sync_engine
        start_sync_engine(self)

    def _force_sync_once(self) -> None:
        from .pages.force_sync_once import force_sync_once
        force_sync_once(self)

    def _on_sync_log(self, msg: str, level: str = "info") -> None:
        from .pages.on_sync_log import on_sync_log
        on_sync_log(self, msg, level=level)

    def _on_sync_status(self, status: str) -> None:
        from .pages.on_sync_status import on_sync_status
        on_sync_status(self, status)

    def _on_sync_stats(self, stats: dict) -> None:
        from .pages.on_sync_stats import on_sync_stats
        on_sync_stats(self, stats)

    # ══════════════════════════════════════════════════════════════════════════
    # BUFFs — Rates Temporários
    # ══════════════════════════════════════════════════════════════════════════

    def _init_buff_manager(self) -> None:
        from .pages.init_buff_manager import init_buff_manager
        init_buff_manager(self)

    def _init_backup_manager(self) -> None:
        from .pages.init_backup_manager import init_backup_manager
        init_backup_manager(self)

    def _build_buffs_panel(self, parent: ctk.CTkFrame) -> None:
        from .pages.build_buffs_panel import build_buffs_panel
        build_buffs_panel(self, parent)

    def _refresh_buffs_ui(self) -> None:
        from .pages.refresh_buffs_ui import refresh_buffs_ui
        refresh_buffs_ui(self)

    def _build_active_buff_card(self, parent, row: int, event: BuffEvent) -> None:
        from .pages.build_active_buff_card import build_active_buff_card
        build_active_buff_card(self, parent, row, event)

    def _build_scheduled_buff_row(self, parent, row: int, event: BuffEvent) -> None:
        from .pages.build_scheduled_buff_row import build_scheduled_buff_row
        build_scheduled_buff_row(self, parent, row, event)

    def _build_preset_chip(self, parent, row: int, col: int,
                           preset: BuffPreset, srv_id: Optional[str]) -> None:
        from .pages.build_preset_chip import build_preset_chip
        build_preset_chip(self, parent, row, col, preset, srv_id=srv_id)

    def _build_history_row(self, parent, row: int, event: BuffEvent) -> None:
        from .pages.build_history_row import build_history_row
        build_history_row(self, parent, row, event)

    def _cancel_buff(self, event_id: str) -> None:
        from .pages.cancel_buff import cancel_buff
        cancel_buff(self, event_id)

    def _sidebar_clock_tick(self) -> None:
        from .pages.sidebar_clock_tick import sidebar_clock_tick
        sidebar_clock_tick(self)

    @staticmethod
    def _format_countdown(target: "datetime") -> str:
        from .pages.format_countdown import format_countdown
        return format_countdown(target)

    def _buff_countdown_tick(self) -> None:
        from .pages.buff_countdown_tick import buff_countdown_tick
        buff_countdown_tick(self)

    # ── Diálogo: Criar BUFF ────────────────────────────────────────────────────

    def _open_create_buff_dialog(
        self,
        preset: Optional[BuffPreset] = None,
        server_id: Optional[str] = None,
    ) -> None:
        from .dialogs.create_buff_dialog import open_create_buff_dialog
        open_create_buff_dialog(self, preset=preset, server_id=server_id)

    # ── Diálogo: Gerenciar Presets ─────────────────────────────────────────────

    def _open_presets_manager(self) -> None:
        from .dialogs.open_presets_manager import open_presets_manager
        open_presets_manager(self)

    # ══════════════════════════════════════════════════════════════════════════
    # Dashboard
    # ══════════════════════════════════════════════════════════════════════════

    def _build_dashboard(self, parent: ctk.CTkFrame) -> None:
        from .pages.build_dashboard import build_dashboard
        build_dashboard(self, parent)

    def _refresh_dashboard(self) -> None:
        from .pages.refresh_dashboard import refresh_dashboard
        refresh_dashboard(self)

    def _build_server_card(self, parent, srv: ServerConfig, row: int, col: int) -> None:
        from .pages.build_server_card import build_server_card
        build_server_card(self, parent, srv, row, col)

    # ══════════════════════════════════════════════════════════════════════════
    # Painel de Servidor
    # ══════════════════════════════════════════════════════════════════════════

    def _open_server_panel(self, server_id: str) -> None:
        from .pages.open_server_panel import open_server_panel
        open_server_panel(self, server_id)

    def _build_server_panel(self, parent: ctk.CTkFrame, srv: ServerConfig) -> None:
        from .pages.server_panel import build_server_panel
        build_server_panel(self, parent, srv)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Geral
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_general(self, parent, srv: ServerConfig) -> None:  # noqa: C901
        from .pages.tab_general import build_tab_general
        build_tab_general(self, parent, srv)

    def _build_tab_game(self, parent, srv: ServerConfig) -> None:
        from .pages.tab_game import build_tab_game
        build_tab_game(self, parent, srv)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Avançado / Cross-ARK
    # ══════════════════════════════════════════════════════════════════════════


    # ══════════════════════════════════════════════════════════════════════════
    # Aba Avançado / Cross-ARK
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_advanced(self, parent, srv: ServerConfig) -> None:  # noqa: C901
        from .pages.tab_advanced import build_tab_advanced
        build_tab_advanced(self, parent, srv)

    # ══════════════════════════════════════════════════════════════════════════
    # Diagnóstico de Cluster
    # ══════════════════════════════════════════════════════════════════════════

    def _get_cluster_health(self, srv: ServerConfig) -> list[tuple[str, str, str]]:
        from .pages.get_cluster_health import get_cluster_health
        return get_cluster_health(self, srv)

    def _show_cluster_health_dialog(self, server_id: str) -> None:
        from .pages.show_cluster_health_dialog import show_cluster_health_dialog
        show_cluster_health_dialog(self, server_id)

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
        from .pages.tab_spawns import build_tab_spawns
        build_tab_spawns(self, parent, srv)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Loot (Supply Crate Overrides)
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_loot(self, parent, srv: ServerConfig) -> None:
        from .pages.tab_loot import build_tab_loot
        build_tab_loot(self, parent, srv)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Mods
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_mods(self, parent, srv: ServerConfig) -> None:
        from .pages.tab_mods import build_tab_mods
        build_tab_mods(self, parent, srv)

    def _build_auto_update_panel(self, parent, srv: ServerConfig) -> None:
        from .pages.build_auto_update_panel import build_auto_update_panel
        build_auto_update_panel(self, parent, srv)

    def _toggle_mod_auto_updater(self, server_id: str) -> None:
        from .pages.toggle_mod_auto_updater import toggle_mod_auto_updater
        toggle_mod_auto_updater(self, server_id)

    _MODS_PAGE = 20  # mods por página

    def _refresh_mods_list(self, server_id: str, page: int = 0) -> None:
        from .pages.refresh_mods_list import refresh_mods_list
        refresh_mods_list(self, server_id, page=page)

    def _open_mod_search_dialog(self, server_id: str) -> None:
        from .dialogs.mod_search_dialog import open_mod_search_dialog
        open_mod_search_dialog(self, server_id)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Plugins (ArkApi / CustomShop)
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_plugins(self, parent, srv: ServerConfig) -> None:  # noqa: C901
        from .pages.tab_plugins import build_tab_plugins
        build_tab_plugins(self, parent, srv)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Admins
    # ══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _sanitize_steam_name(name: str) -> str:
        from .pages.sanitize_steam_name import sanitize_steam_name
        return sanitize_steam_name(name)

    @staticmethod
    def _fetch_steam_name(steam_id: str, callback) -> None:
        from .pages.fetch_steam_name import fetch_steam_name
        fetch_steam_name(steam_id, callback)

    def _build_tab_admins(self, parent, srv: ServerConfig) -> None:
        from .pages.build_tab_admins import build_tab_admins
        build_tab_admins(self, parent, srv)

    def _lookup_admin_preview(self, server_id: str, steam_id: str) -> None:
        from .pages.lookup_admin_preview import lookup_admin_preview
        lookup_admin_preview(self, server_id, steam_id)

    def _write_allowed_admins(self, server_id: str) -> None:
        from .pages.write_allowed_admins import write_allowed_admins
        write_allowed_admins(self, server_id)

    def _refresh_admins_list(self, server_id: str) -> None:
        from .pages.refresh_admins_list import refresh_admins_list
        refresh_admins_list(self, server_id)

    def _add_admin_id(self, server_id: str) -> None:
        from .pages.add_admin_id import add_admin_id
        add_admin_id(self, server_id)

    def _remove_admin_id(self, server_id: str, steam_id: str) -> None:
        from .pages.remove_admin_id import remove_admin_id
        remove_admin_id(self, server_id, steam_id)

    # Aba Jogadores
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_jogadores(self, parent, srv: ServerConfig) -> None:
        from .pages.build_tab_jogadores import build_tab_jogadores
        build_tab_jogadores(self, parent, srv)

    def _refresh_players(self, server_id: str) -> None:
        from .pages.refresh_players import refresh_players
        refresh_players(self, server_id)

    def _update_players_list(self, server_id: str, ok: bool, response: str) -> None:
        from .pages.update_players_list import update_players_list
        update_players_list(self, server_id, ok, response)

    def _build_player_row(self, parent, server_id: str, name: str, steam_id: str) -> None:
        from .pages.build_player_row import build_player_row
        build_player_row(self, parent, server_id, name, steam_id)

    def _player_kick(self, server_id: str, steam_id: str, name: str) -> None:
        from .pages.player_kick import player_kick
        player_kick(self, server_id, steam_id, name)

    def _player_ban(self, server_id: str, steam_id: str, name: str) -> None:
        from .pages.player_ban import player_ban
        player_ban(self, server_id, steam_id, name)

    def _player_add_admin(self, server_id: str, steam_id: str, name: str) -> None:
        from .pages.player_add_admin import player_add_admin
        player_add_admin(self, server_id, steam_id, name)

    def _toggle_players_auto(self, server_id: str) -> None:
        from .pages.toggle_players_auto import toggle_players_auto
        toggle_players_auto(self, server_id)

    def _schedule_players_refresh(self, server_id: str) -> None:
        from .pages.schedule_players_refresh import schedule_players_refresh
        schedule_players_refresh(self, server_id)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Console RCON
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_rcon(self, parent, srv: ServerConfig) -> None:
        from .pages.tab_rcon import build_tab_rcon
        build_tab_rcon(self, parent, srv)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Chat público
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_chat(self, parent, srv: ServerConfig) -> None:
        from .pages.tab_chat import build_tab_chat
        build_tab_chat(self, parent, srv)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Logs
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_logs(self, parent, srv: ServerConfig) -> None:
        from .pages.build_tab_logs import build_tab_logs
        build_tab_logs(self, parent, srv)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Backup
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_backup(self, parent, srv: ServerConfig) -> None:
        from .pages.tab_backup import build_tab_backup
        build_tab_backup(self, parent, srv)

    # ── Busca de configurações ─────────────────────────────────────────────────

    def _register_config_item(self, server_id: str, label: str, hint: str, tab: str) -> None:
        self._config_search_index.setdefault(server_id, []).append(
            (label.rstrip(": "), hint, tab)
        )

    def _build_config_search_bar(self, parent: ctk.CTkFrame, server_id: str) -> None:
        from .pages.build_config_search_bar import build_config_search_bar
        build_config_search_bar(self, parent, server_id)

    # ── Backup ─────────────────────────────────────────────────────────────────

    def _save_backup_config(self, server_id: str) -> None:
        from .pages.save_backup_config import save_backup_config
        save_backup_config(self, server_id)

    def _do_manual_backup(self, server_id: str) -> None:
        from .pages.do_manual_backup import do_manual_backup
        do_manual_backup(self, server_id)

    def _refresh_backup_list(self, server_id: str) -> None:
        from .pages.refresh_backup_list import refresh_backup_list
        refresh_backup_list(self, server_id)

    def _confirm_restore_backup(self, server_id: str, backup_path: str) -> None:
        from .pages.confirm_restore_backup import confirm_restore_backup
        confirm_restore_backup(self, server_id, backup_path)

    def _confirm_delete_backup(self, server_id: str, backup_path: str) -> None:
        from .pages.confirm_delete_backup import confirm_delete_backup
        confirm_delete_backup(self, server_id, backup_path)

    # ══════════════════════════════════════════════════════════════════════════
    # Configurações Globais
    # ══════════════════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════════════════
    # Painel de Acesso Remoto
    # ══════════════════════════════════════════════════════════════════════════

    def _build_remote_panel(self, parent) -> None:  # noqa: C901
        from .pages.remote_panel import build_remote_panel
        build_remote_panel(self, parent)

    def _refresh_identity_code(self) -> None:
        from .pages.refresh_identity_code import refresh_identity_code
        refresh_identity_code(self)

    def _refresh_remote_instances_list(self) -> None:
        from .pages.refresh_remote_instances_list import refresh_remote_instances_list
        refresh_remote_instances_list(self)

    def _open_remote_control(self, inst: dict) -> None:  # noqa: C901
        from .dialogs.remote_control_dialog import open_remote_control
        open_remote_control(self, inst)

    # ══════════════════════════════════════════════════════════════════════════

    def _build_global_config(self, parent) -> None:
        from .pages.global_config import build_global_config
        build_global_config(self, parent)

    # ══════════════════════════════════════════════════════════════════════════
    # Sobre / Atualizações
    # ══════════════════════════════════════════════════════════════════════════


    # ══════════════════════════════════════════════════════════════════════════
    # Painel de Desempenho
    # ══════════════════════════════════════════════════════════════════════════

    def _build_performance_panel(self, parent) -> None:
        from .pages.performance_panel import build_performance_panel
        build_performance_panel(self, parent)

    # ── Coleta estática de GPU ────────────────────────────────────────────────

    def _collect_gpu_info(self) -> None:
        from .pages.collect_gpu_info import collect_gpu_info
        collect_gpu_info(self)

    # ── Monitor em tempo real ─────────────────────────────────────────────────

    def _start_perf_monitor(self) -> None:
        if not _PSUTIL_OK or self._perf_running:
            return
        self._perf_running = True
        self._perf_thread = threading.Thread(
            target=self._perf_monitor_loop, daemon=True, name="perf-monitor")
        self._perf_thread.start()

    def _perf_monitor_loop(self) -> None:
        from .pages.perf_monitor_loop import perf_monitor_loop
        perf_monitor_loop(self)

    def _log_perf_critical(self, metric: str, pct: float, state: str) -> None:
        from .pages.log_perf_critical import log_perf_critical
        log_perf_critical(self, metric, pct, state)

    def _clear_perf_critical_log(self) -> None:
        """Limpa o histórico de pontos críticos."""
        if self._perf_critical_log:
            self._perf_critical_log.configure(state="normal")
            self._perf_critical_log.delete("1.0", "end")
            self._perf_critical_log.configure(state="disabled")

    def _get_nvidia_gpu_pct(self) -> Optional[float]:
        from .pages.get_nvidia_gpu_pct import get_nvidia_gpu_pct
        return get_nvidia_gpu_pct(self)

    def _get_nvidia_gpu_temp(self) -> Optional[float]:
        from .pages.get_nvidia_gpu_temp import get_nvidia_gpu_temp
        return get_nvidia_gpu_temp(self)

    def _get_cpu_temp(self) -> Optional[float]:
        from .pages.get_cpu_temp import get_cpu_temp
        return get_cpu_temp(self)

    def _collect_server_stats(self) -> list:
        from .pages.collect_server_stats import collect_server_stats
        return collect_server_stats(self)

    def _update_perf_servers(self, srv_stats: list) -> None:
        from .pages.update_perf_servers import update_perf_servers
        update_perf_servers(self, srv_stats)

    # ══════════════════════════════════════════════════════════════════════════
    # Painel Cross-ARK Clusters
    # ══════════════════════════════════════════════════════════════════════════

    def _build_clusters_panel(self, parent: ctk.CTkFrame) -> None:
        from .pages.build_clusters_panel import build_clusters_panel
        build_clusters_panel(self, parent)

    def _clusters_refresh_list(self) -> None:
        from .pages.clusters_refresh_list import clusters_refresh_list
        clusters_refresh_list(self)

    def _cluster_select(self, cluster_id: str) -> None:
        self._cluster_selected_id = cluster_id
        self._clusters_refresh_list()
        prof = self.config_manager.get_cluster(cluster_id)
        if prof:
            self._cluster_build_detail(prof)

    def _cluster_import_from_manual(self) -> None:
        from .pages.cluster_import_from_manual import cluster_import_from_manual
        cluster_import_from_manual(self)

    def _cluster_new(self) -> None:
        from .pages.cluster_new import cluster_new
        cluster_new(self)

    def _cluster_build_detail(self, prof) -> None:
        from .pages.cluster_detail import build_cluster_detail
        build_cluster_detail(self, prof)

    def _cluster_save(self, cluster_id: str) -> None:
        from .pages.cluster_save import cluster_save
        cluster_save(self, cluster_id)

    def _cluster_delete(self, cluster_id: str) -> None:
        from .pages.cluster_delete import cluster_delete
        cluster_delete(self, cluster_id)

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
        from .pages.cluster_sync_start import cluster_sync_start
        cluster_sync_start(self, cluster_id)

    def _cluster_sync_stop(self, cluster_id: str) -> None:
        """Para o engine de sync de um cluster (se estiver rodando)."""
        engine = self._cluster_sync_engines.pop(cluster_id, None)
        if engine and engine.is_running:
            engine.stop()

    def _cluster_sync_once(self, cluster_id: str) -> None:
        from .pages.cluster_sync_once import cluster_sync_once
        cluster_sync_once(self, cluster_id)

    def _cluster_sync_log(self, cluster_id: str, msg: str, level: str) -> None:
        prof = self.config_manager.get_cluster(cluster_id)
        name = prof.name if prof else cluster_id[:8]
        self._emit_global_log(f"[Cluster:{name}] {msg}", level)

    # ── Config Dinâmica ───────────────────────────────────────────────────────

    def _auto_start_dynamic_configs(self) -> None:
        from .pages.auto_start_dynamic_configs import auto_start_dynamic_configs
        auto_start_dynamic_configs(self)

    def _get_dynamic_config_url(self, server_id: str) -> str:
        """Callback para ServerManager: retorna a URL do servidor dinâmico."""
        if not self._dynamic_config_server.is_running:
            self._dynamic_config_server.start()
        return self._dynamic_config_server.get_url(server_id)

    def _push_dynamic_config(self, server_id: str) -> None:
        from .pages.push_dynamic_config import push_dynamic_config
        push_dynamic_config(self, server_id)


    def _build_about(self, parent) -> None:
        from .pages.build_about import build_about
        build_about(self, parent)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba INI Estruturado
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_ini_mods(self, parent, srv: ServerConfig) -> None:
        from .pages.tab_ini_mods import build_tab_ini_mods
        build_tab_ini_mods(self, parent, srv)

    # ── Helpers do painel INI ─────────────────────────────────────────────────

    def _ini_flush_current(self, server_id: str, file_key: str) -> None:
        from .pages.ini_flush_current import ini_flush_current
        ini_flush_current(self, server_id, file_key)

    def _ini_reload(self, server_id: str, file_key: str) -> None:
        from .pages.ini_reload import ini_reload
        ini_reload(self, server_id, file_key)

    def _ini_render_section_item(self, server_id: str, file_key: str,
                                 container, sec: dict) -> None:
        from .pages.ini_render_section_item import ini_render_section_item
        ini_render_section_item(self, server_id, file_key, container, sec)

    def _ini_select_section(self, server_id: str, file_key: str, section_name: str) -> None:
        from .pages.ini_select_section import ini_select_section
        ini_select_section(self, server_id, file_key, section_name)

    def _ini_render_entry_row(self, server_id: str, file_key: str,
                              container, sec_data: dict, entry: dict, idx: int) -> None:
        from .pages.ini_render_entry_row import ini_render_entry_row
        ini_render_entry_row(self, server_id, file_key, container, sec_data, entry, idx)

    def _ini_add_section(self, server_id: str, file_key: str) -> None:
        from .pages.ini_add_section import ini_add_section
        ini_add_section(self, server_id, file_key)

    def _ini_paste_section(self, server_id: str, file_key: str) -> None:
        from .pages.ini_paste_section import ini_paste_section
        ini_paste_section(self, server_id, file_key)

    def _ini_delete_section(self, server_id: str, file_key: str, section_name: str) -> None:
        from .pages.ini_delete_section import ini_delete_section
        ini_delete_section(self, server_id, file_key, section_name)

    def _ini_rebuild_section_list(self, server_id: str, file_key: str) -> None:
        from .pages.ini_rebuild_section_list import ini_rebuild_section_list
        ini_rebuild_section_list(self, server_id, file_key)

    def _ini_add_entry(self, server_id: str, file_key: str) -> None:
        from .pages.ini_add_entry import ini_add_entry
        ini_add_entry(self, server_id, file_key)

    def _ini_del_entry(self, server_id: str, file_key: str,
                       sec_data: dict, entry: dict) -> None:
        from .pages.ini_del_entry import ini_del_entry
        ini_del_entry(self, server_id, file_key, sec_data, entry)

    def _ini_save(self, server_id: str) -> None:
        from .pages.ini_save import ini_save
        ini_save(self, server_id)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Crashes
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_crashes(self, parent, srv: ServerConfig) -> None:
        from .pages.tab_crashes import build_tab_crashes
        build_tab_crashes(self, parent, srv)

    # ══════════════════════════════════════════════════════════════════════════
    # Aba Histórico de Alterações
    # ══════════════════════════════════════════════════════════════════════════

    def _build_tab_historico(self, parent, srv: ServerConfig) -> None:
        from .pages.build_tab_historico import build_tab_historico
        build_tab_historico(self, parent, srv)

    def _historico_refresh(self, server_id: str, filter_var: tk.StringVar) -> None:
        from .pages.historico_refresh import historico_refresh
        historico_refresh(self, server_id, filter_var)

    def _historico_clear(self, server_id: str, filter_var: tk.StringVar) -> None:
        from .pages.historico_clear import historico_clear
        historico_clear(self, server_id, filter_var)

    def _get_change_logger(self, server_id: str) -> ChangeLogger:
        from .pages.get_change_logger import get_change_logger
        return get_change_logger(self, server_id)

    # ══════════════════════════════════════════════════════════════════════════
    # Ações de Servidor
    # ══════════════════════════════════════════════════════════════════════════

    def _start_server(self, server_id: str) -> None:
        from .pages.start_server import start_server
        start_server(self, server_id)

    def _stop_server(self, server_id: str) -> None:
        self.server_manager.stop_server(server_id)

    def _restart_server(self, server_id: str) -> None:
        self.server_manager.restart_server(server_id)

    def _confirm_remove_server(self, server_id: str) -> None:
        from .pages.confirm_remove_server import confirm_remove_server
        confirm_remove_server(self, server_id)

    def _run_server_install(self, server_id: str, validate: bool = False) -> None:
        from .pages.run_server_install import run_server_install
        run_server_install(self, server_id, validate=validate)

    def _validate_server_ports(self, server_id: str,
                                server_port: int, query_port: int, rcon_port: int) -> list:
        from .pages.validate_server_ports import validate_server_ports
        return validate_server_ports(self, server_id, server_port, query_port, rcon_port)

    def _save_server_config(self, server_id: str, silent: bool = False, force: bool = False) -> None:
        from .pages.server_save import save_server_config
        save_server_config(self, server_id, silent=silent, force=force)

    # ── Import / Sync INI ─────────────────────────────────────────────────────

    def _import_ini_from_disk(self, server_id: str) -> None:
        from .pages.ini_import import import_ini_from_disk
        import_ini_from_disk(self, server_id)

    def _rebuild_server_panel(self, server_id: str) -> None:
        from .pages.rebuild_server_panel import rebuild_server_panel
        rebuild_server_panel(self, server_id)

    def _open_sync_ini_dialog(self, source_server_id: str) -> None:
        from .dialogs.sync_ini_dialog import open_sync_ini_dialog
        open_sync_ini_dialog(self, source_server_id)

    def _open_clone_config_dialog(self, source_server_id: str) -> None:
        from .dialogs.clone_config_dialog import open_clone_config_dialog
        open_clone_config_dialog(self, source_server_id)

    # ── Mods ──────────────────────────────────────────────────────────────────

    def _add_mod(self, server_id: str, mod_name: str = "") -> None:
        from .pages.add_mod import add_mod
        add_mod(self, server_id, mod_name=mod_name)

    def _fetch_mod_names_async(self, server_id: str, mod_ids: list) -> None:
        from .pages.fetch_mod_names_async import fetch_mod_names_async
        fetch_mod_names_async(self, server_id, mod_ids)

    def _remove_mod(self, server_id: str, mod_id: str) -> None:
        from .pages.remove_mod import remove_mod
        remove_mod(self, server_id, mod_id)

    def _clear_all_mods(self, server_id: str) -> None:
        from .pages.clear_all_mods import clear_all_mods
        clear_all_mods(self, server_id)

    def _open_mod_ini_dialog(self, server_id: str, mod_id: str) -> None:
        from .dialogs.mod_ini_dialog import open_mod_ini_dialog
        open_mod_ini_dialog(self, server_id, mod_id)


    def _download_mod(self, server_id: str, mod_id: str) -> None:
        from .pages.download_mod import download_mod
        download_mod(self, server_id, mod_id)

    def _download_all_mods(self, server_id: str) -> None:
        from .pages.download_all_mods import download_all_mods
        download_all_mods(self, server_id)

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
        from .pages.rcon_auto_connect_tick import rcon_auto_connect_tick
        rcon_auto_connect_tick(self, server_id)

    # ── RCON manual ──────────────────────────────────────────────────────────

    def _rcon_connect(self, server_id: str) -> None:
        from .pages.rcon_connect import rcon_connect
        rcon_connect(self, server_id)

    def _rcon_send(self, server_id: str) -> None:
        w = self._server_widgets.get(server_id, {})
        cmd = w.get("rcon_input", tk.StringVar()).get().strip()
        if not cmd:
            return
        w["rcon_input"].set("")
        self._rcon_exec(server_id, cmd)

    def _rcon_exec(self, server_id: str, command: str) -> None:
        from .pages.rcon_exec import rcon_exec
        rcon_exec(self, server_id, command)

    def _rcon_append(self, server_id: str, text: str, tag: str = "resp") -> None:
        from .pages.rcon_append import rcon_append
        rcon_append(self, server_id, text, tag=tag)

    # ── Chat público ──────────────────────────────────────────────────────────

    def _chat_append(self, server_id: str, text: str, tag: str = "message") -> None:
        from .pages.chat_append import chat_append
        chat_append(self, server_id, text, tag=tag)

    def _chat_clear(self, server_id: str) -> None:
        from .pages.chat_clear import chat_clear
        chat_clear(self, server_id)

    def _chat_process(self, server_id: str, raw: str) -> None:
        from .pages.chat_process import chat_process
        chat_process(self, server_id, raw)

    def _chat_fetch(self, server_id: str) -> None:
        from .pages.chat_fetch import chat_fetch
        chat_fetch(self, server_id)

    def _chat_send(self, server_id: str) -> None:
        from .pages.chat_send import chat_send
        chat_send(self, server_id)

    def _chat_toggle_poll(self, server_id: str) -> None:
        from .pages.chat_toggle_poll import chat_toggle_poll
        chat_toggle_poll(self, server_id)

    def _chat_cancel_poll(self, server_id: str) -> None:
        job = self._chat_poll_jobs.pop(server_id, None)
        if job:
            try:
                self.after_cancel(job)
            except Exception:
                pass

    def _chat_poll_loop(self, server_id: str) -> None:
        from .pages.chat_poll_loop import chat_poll_loop
        chat_poll_loop(self, server_id)

    # ── Gerenciamento de Broadcasts ───────────────────────────────────────────

    def _broadcast_rcon(self, server_id: str, message: str) -> None:
        from .pages.broadcast_rcon import broadcast_rcon
        broadcast_rcon(self, server_id, message)

    def _broadcast_send_quick(self, server_id: str) -> None:
        from .pages.broadcast_send_quick import broadcast_send_quick
        broadcast_send_quick(self, server_id)

    def _broadcast_test(self, server_id: str) -> None:
        from .pages.broadcast_test import broadcast_test
        broadcast_test(self, server_id)

    def _broadcast_add(self, server_id: str) -> None:
        from .pages.broadcast_add import broadcast_add
        broadcast_add(self, server_id)

    def _broadcast_delete(self, server_id: str, index: int) -> None:
        from .pages.broadcast_delete import broadcast_delete
        broadcast_delete(self, server_id, index)

    def _broadcast_edit(self, server_id: str, index: int) -> None:
        from .pages.broadcast_edit import broadcast_edit
        broadcast_edit(self, server_id, index)

    def _broadcast_refresh_list(self, server_id: str) -> None:
        from .pages.broadcast_refresh_list import broadcast_refresh_list
        broadcast_refresh_list(self, server_id)

    def _broadcast_render_row(self, server_id: str, container,
                               index: int, bc: dict, readonly: bool) -> None:
        from .pages.broadcast_render_row import broadcast_render_row
        broadcast_render_row(self, server_id, container, index, bc, readonly)

    # ── Callbacks de status e log ─────────────────────────────────────────────

    def _on_server_status_change(self, server_id: str, status: str) -> None:
        from .pages.on_server_status_change import on_server_status_change
        on_server_status_change(self, server_id, status)

    @staticmethod
    def _fast_fill(scroll: ctk.CTkScrollableFrame, fn: Any) -> None:
        from .pages.fast_fill import fast_fill
        fast_fill(scroll, fn)

    def _set_config_editable(self, server_id: str, editable: bool) -> None:
        from .pages.set_config_editable import set_config_editable
        set_config_editable(self, server_id, editable)


    def _on_server_log(self, server_id: str, msg: str, level: str) -> None:
        from .pages.on_server_log import on_server_log
        on_server_log(self, server_id, msg, level)

    def _clear_server_log(self, server_id: str) -> None:
        from .pages.clear_server_log import clear_server_log
        clear_server_log(self, server_id)

    # ── Diálogo "Novo Servidor" ───────────────────────────────────────────────

    def _on_server_visibility_change(self, server_id: str, mode: str) -> None:
        from .pages.on_server_visibility_change import on_server_visibility_change
        on_server_visibility_change(self, server_id, mode)

    def _on_bm_update(self, server_id: str) -> None:
        from .pages.on_bm_update import on_bm_update
        on_bm_update(self, server_id)

    def _on_auto_updater_log(self, msg: str, level: str) -> None:
        from .pages.on_auto_updater_log import on_auto_updater_log
        on_auto_updater_log(self, msg, level)

    def _dialog_add_server(self) -> None:
        from .dialogs.add_server_dialog import dialog_add_server
        dialog_add_server(self)

    # ── Perfil (exportar / importar) ──────────────────────────────────────────

    def _export_profile(self) -> None:
        from .pages.export_profile import export_profile
        export_profile(self)

    def _import_profile(self) -> None:
        from .pages.import_profile import import_profile
        import_profile(self)

    # ── Configurações Globais ─────────────────────────────────────────────────

    def _save_global_config(self) -> None:
        from .pages.save_global_config import save_global_config
        save_global_config(self)

    # ── Update checker ────────────────────────────────────────────────────────

    def _check_updates_on_start(self) -> None:
        url = self.config_manager.config.update_url
        if not url:
            return
        self.update_checker.check_async(
            url, on_result=lambda info: self.after(0, lambda: self._on_update_result(info)))  # type: ignore[arg-type]

    def _start_mod_auto_updater(self) -> None:
        from .pages.start_mod_auto_updater import start_mod_auto_updater
        start_mod_auto_updater(self)

    def _check_updates_manual(self) -> None:
        from .pages.check_updates_manual import check_updates_manual
        check_updates_manual(self)

    def _on_update_result(self, info, manual: bool = False) -> None:
        from .pages.on_update_result import on_update_result
        on_update_result(self, info, manual=manual)

    def _start_download_update(self) -> None:
        from .pages.start_download_update import start_download_update
        start_download_update(self)

    def _on_download_done(self, success: bool, message: str) -> None:
        from .pages.on_download_done import on_download_done
        on_download_done(self, success, message)

    # ── Logs globais ──────────────────────────────────────────────────────────

    def _global_log(self, msg: str, level: str = "info") -> None:
        self._global_log_buf.append(f"[{level.upper()}] {msg}")

    def _emit_global_log(self, msg: str, level: str = "info") -> None:
        self._global_log(msg, level)

    def _toast(self, msg: str, kind: str = "info") -> None:
        from .pages.toast import toast
        toast(self, msg, kind=kind)

    # ── Navegação ─────────────────────────────────────────────────────────────

    def _show_frame(self, name: str) -> None:
        from .pages.show_frame import show_frame
        show_frame(self, name)

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
        from .pages.download_steamcmd import download_steamcmd
        download_steamcmd(self)

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
        from .pages.do_quit import do_quit
        do_quit(self)

    # ── Bandeja do sistema ────────────────────────────────────────────────────

    def _minimize_to_tray(self) -> None:
        from .pages.minimize_to_tray import minimize_to_tray
        minimize_to_tray(self)

    def _restore_from_tray(self, icon=None, item=None) -> None:
        self.after(0, self._do_restore)

    def _do_restore(self) -> None:
        from .pages.do_restore import do_restore
        do_restore(self)

