"""
ARKLAND TEK — Aplicação principal.
Substitui completamente o ARKLAND-Multi (modo PRIMITIVE).
Replica o comportamento exato do ASM (ARK Server Manager) em Python/CustomTkinter.
"""
from __future__ import annotations

import os
import sys
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Dict, List, Optional
import time
import customtkinter as ctk  # type: ignore[reportMissingImports]

from .asm_engine.asm_config_manager import AsmConfigManager
from .asm_engine.asm_server_config import AsmServerConfig, ASM_STATUS_RUNNING, ASM_STATUS_STOPPED, ASM_STATUS_CRASHED
from .asm_engine.asm_server_manager import AsmServerManager
from .config_manager import ConfigManager
from .server_manager import ServerManager
from .sync_engine import SyncEngine
from .updater import UpdateChecker
from .ui_constants import get_theme, set_tek_variant, get_tek_variant
from .version import APP_VERSION

# ── Constantes de janela ─────────────────────────────────────────────────────
_WINDOW_TITLE  = "ARKLAND TEK — ARK Server Manager"
_WINDOW_MIN_W  = 1100
_WINDOW_MIN_H  = 700
_WINDOW_SIZE   = "1280x780"
_SIDEBAR_W     = 240


def _resource_path(relative: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, relative)


class ARKServerManagerApp(ctk.CTk):
    """Aplicação principal TEK. Única classe de app — sem modo PRIMITIVE."""

    # Frame cache para show_frame_tek
    _frame_cache: Dict[str, Any]

    def __init__(self) -> None:
        super().__init__()

        self._frame_cache: Dict[str, Any] = {}

        # ── Carrega preferência de variante de tema (persiste entre sessões) ──
        self._prefs_file = (
            Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager" / "ui_prefs.json"
        )
        self._load_ui_prefs()

        _ctk_mode = "light" if get_tek_variant() == "light" else "dark"
        ctk.set_appearance_mode(_ctk_mode)
        ctk.set_default_color_theme("dark-blue")

        self.title(_WINDOW_TITLE)
        self.geometry(_WINDOW_SIZE)
        self.minsize(_WINDOW_MIN_W, _WINDOW_MIN_H)

        theme = get_theme("tek")
        self.configure(fg_color=theme["bg"])

        # ── Managers ──────────────────────────────────────────────────────────
        self.asm_config_manager = AsmConfigManager()
        self.asm_server_manager = AsmServerManager(
            on_status_change=self._on_server_status_change
        )
        self.config_manager  = ConfigManager()
        from .pages.init_discord_notifier import init_discord_notifier
        init_discord_notifier(self)
        self.server_manager  = ServerManager(discord_notifier=self._discord_notifier)
        from .backup_manager import BackupManager
        from .db_backup_manager import DbBackupManager
        self._backup_manager = BackupManager(
            get_servers=lambda: self.asm_config_manager.servers,
            on_log=self._global_log,
            discord_notifier=self._discord_notifier,
        )
        self._db_backup_manager = DbBackupManager(on_log=self._global_log)
        self._global_backup_last_run: Optional[datetime] = datetime.now()
        self._db_backup_last_run: Optional[datetime] = datetime.now()
        self._global_backup_running = False
        self._db_backup_running = False
        from .mod_manager import ModManager
        self.mod_manager = ModManager(
            steamcmd_path=self.config_manager.config.steamcmd_path,
            on_log=lambda msg, level: self._global_log(msg, level),
        )
        self._mod_auto_updater = None
        self._auto_updater_log_box = None
        self.update_checker  = UpdateChecker(on_log=lambda m, level: None)
        # Carrega servidores primitivos salvos no server_manager
        for srv in self.config_manager.servers:
            self.server_manager.add_server(srv)

        # ── Estado interno ────────────────────────────────────────────────────
        self._active_mode        = "tek"
        self._asm_dashboard_scroll: Optional[ctk.CTkScrollableFrame] = None
        self._asm_panel_vars: dict = {}
        self._current_frame: Optional[ctk.CTkFrame] = None
        self._sidebar_server_btns: Dict[str, tk.Label] = {}
        self._sidebar_server_rows: Dict[str, Dict[str, Any]] = {}
        self._sidebar_empty_lbl: Any = None
        self._nav_active: str = "dashboard"
        # Sync
        self._sync_engine: Optional[SyncEngine] = None
        self._sync_log_box: Any = None
        self._sync_status_lbl: Any = None
        self._sync_stats_lbl: Any = None
        self._sync_toggle_btn: Any = None
        self._sync_cycles_frame: Any = None
        self._sync_cycle_vars: List = []
        # About / Updates
        self._update_status_var: Any = None
        self._update_status_lbl: Any = None
        self._last_check_var: Any = None
        self._check_update_btn: Any = None
        self._install_update_btn: Any = None
        self._update_progress: Any = None
        self._update_progress_label: Any = None
        self._update_auto_started: bool = False
        # Performance
        self._perf_running: bool = False
        self._asm_status_tick_running: bool = False
        self._perf_cpu_pct_var: Any = None
        self._perf_cpu_bar: Any = None
        self._perf_cpu_info_var: Any = None
        self._perf_cpu_temp_var: Any = None
        self._perf_ram_pct_var: Any = None
        self._perf_ram_bar: Any = None
        self._perf_ram_info_var: Any = None
        self._perf_gpu_pct_var: Any = None
        self._perf_gpu_bar: Any = None
        self._perf_gpu_info_var: Any = None
        self._perf_server_procs: Dict[str, Any] = {}
        self._perf_servers_frame: Any = None
        # BUFFs
        self._buff_manager: Any = None
        self._buffs_server_var: Any = None
        self._buffs_body_frame: Any = None
        self._buff_countdown_job: Any = None
        self._buff_countdown_labels: list = []
        # Clusters
        self._cluster_list_box: Any = None
        self._cluster_detail_fr: Any = None
        self._cluster_selected_id: str = ""
        self._cluster_detail_widgets: dict = {}
        # Remoto
        self._remote_agent: Any = None
        self._remote_toggle_btn: Any = None
        self._remote_status_var: Any = None
        self._remote_status_lbl: Any = None
        self._remote_code_var: Any = None
        self._remote_ip_var: Any = None
        self._udp_discovery: Any = None

        # ── Layout principal: sidebar + conteúdo ──────────────────────────────
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)  # sidebar fixo
        self.grid_columnconfigure(1, weight=1)  # área de conteúdo

        self._build_sidebar()

        self._page_area = ctk.CTkFrame(self, fg_color=theme["bg"], corner_radius=0)
        self._page_area.grid(row=0, column=1, sticky="nsew")
        self._page_area.grid_rowconfigure(0, weight=1)
        self._page_area.grid_columnconfigure(0, weight=1)

        # Mostra dashboard ao iniciar
        self._show_frame("dashboard")
        # Watermark de fundo (aplicado após conteúdo existir)
        self.after(150, self._setup_bg_watermark)
        # Auto-start: sync e agente remoto (após UI estável)
        self.after(2000, self._auto_start_services)
        self.after(2500, self._asm_scan_running_servers)
        self.after(2500, self._ensure_buff_manager)
        self.after(3000, self._start_mod_auto_updater)
        # Auto-start: Web Store (após painel estável)
        self.after(5000, self._auto_start_webstore)
        # Verifica atualização do app ao iniciar
        self.after(4000, self._check_updates_on_start)
        # B2: tick de indicadores ricos de status
        self.after(30_000, self._asm_status_tick)

    # ─────────────────────────────────────────────────────────────────────────
    # B2 — Indicadores Ricos de Status (players, uptime, RAM, versão)
    # ─────────────────────────────────────────────────────────────────────────

    def _asm_status_tick(self) -> None:
        """Atualiza cache de indicadores ricos para todos os servidores (a cada 30s)."""
        import threading

        if self._asm_status_tick_running:
            return
        self._asm_status_tick_running = True

        def _worker():
            try:
                for srv in self.asm_config_manager.servers:
                    rich_key = f"_asm_rich_status_{srv.id}"
                    inst = self.asm_server_manager.get_instance(srv.id)
                    status = inst.status if inst else ASM_STATUS_STOPPED

                    if status != ASM_STATUS_RUNNING:
                        setattr(self, rich_key, {
                            "players": "—", "uptime": "—", "ram": "—", "version": "—"
                        })
                        continue

                    data: dict = {"players": "—", "uptime": "—", "ram": "—", "version": "—"}

                    # Uptime: desde reconexão/start do processo
                    uptime_attr = f"_asm_uptime_start_{srv.id}"
                    inst_uptime_start = getattr(inst, "uptime_start", None) if inst else None
                    uptime_start = inst_uptime_start if inst_uptime_start else getattr(self, uptime_attr, None)
                    if uptime_start:
                        elapsed = int(time.time() - uptime_start)
                        hrs, rem = divmod(elapsed, 3600)
                        mins, secs = divmod(rem, 60)
                        data["uptime"] = f"{hrs}h {mins:02d}m" if hrs else f"{mins}m {secs:02d}s"
                    else:
                        setattr(self, uptime_attr, time.time())
                        data["uptime"] = "0m 00s"

                    # Versão: lê version.txt
                    if srv.install_dir:
                        ver_path = Path(srv.install_dir) / "version.txt"
                        if ver_path.exists():
                            try:
                                data["version"] = ver_path.read_text(encoding="utf-8").strip()[:12]
                            except Exception:
                                pass

                    # Players via RCON (melhor esforço)
                    if srv.rcon_enabled and srv.admin_password:
                        try:
                            from .rcon_client import RconClient
                            host = srv.server_ip or "127.0.0.1"
                            rc = RconClient(host, srv.rcon_port, srv.admin_password)
                            rc.connect()
                            ok, resp = rc.send_command_safe("ListPlayers")
                            rc.disconnect()
                            if ok:
                                lines = [ln for ln in resp.splitlines() if ln.strip()]
                                data["players"] = f"{len(lines)}/{srv.max_players}"
                                try:
                                    from .asm_engine.asm_discord_hooks import poll_tek_player_discord
                                    poll_tek_player_discord(self, srv, players_resp=resp)
                                except Exception:
                                    pass
                            else:
                                data["players"] = "?/?"
                        except Exception:
                            data["players"] = "?/?"

                    # RAM via psutil (melhor esforço)
                    if inst and inst.pid:
                        try:
                            import psutil
                            p = psutil.Process(inst.pid)
                            mem_mb = p.memory_info().rss / (1024 * 1024)
                            data["ram"] = f"{mem_mb:.1f} MB"
                        except Exception:
                            pass

                    setattr(self, rich_key, data)
            finally:
                self._asm_status_tick_running = False
                self.after(0, self._asm_refresh_dashboard)

        threading.Thread(target=_worker, daemon=True).start()

        # Reagenda — 60s se janela minimizada/inativa
        try:
            inactive = self.state() == "iconic" or not self.winfo_viewable()
        except Exception:
            inactive = False
        interval = 60_000 if inactive else 30_000
        self.after(interval, self._asm_status_tick)

    def _on_server_status_change(self, server_id: str, new_status: str) -> None:
        """Chamado pela thread do monitor quando o status de um servidor muda."""
        try:
            from .asm_engine.asm_discord_hooks import (
                clear_tek_player_cache,
                notify_tek_server_status,
            )
            notify_tek_server_status(self, server_id, new_status)
            if new_status in (ASM_STATUS_STOPPED, ASM_STATUS_CRASHED):
                clear_tek_player_cache(self, server_id)
        except Exception:
            pass

        # B2: registra timestamp de início do uptime quando fica RUNNING
        if new_status == ASM_STATUS_RUNNING:
            inst = self.asm_server_manager.get_instance(server_id)
            if inst and inst.uptime_start:
                setattr(self, f"_asm_uptime_start_{server_id}", inst.uptime_start)
            else:
                setattr(self, f"_asm_uptime_start_{server_id}", time.time())
        elif new_status in (ASM_STATUS_STOPPED, ASM_STATUS_CRASHED):
            setattr(self, f"_asm_uptime_start_{server_id}", None)
            rich_key = f"_asm_rich_status_{server_id}"
            setattr(self, rich_key, {"players": "—", "uptime": "—", "ram": "—", "version": "—"})

        self.after(0, self._asm_refresh_dashboard)
        self.after(0, self._rebuild_server_sidebar)

    def _setup_bg_watermark(self) -> None:
        """Pré-computa a imagem de watermark para reutilização em todas as páginas."""
        try:
            from PIL import Image, ImageTk  # type: ignore[reportMissingImports]
            theme = get_theme("tek")
            _bg_hex = theme["bg"].lstrip("#")
            _bg_rgb: tuple = tuple(int(_bg_hex[i:i+2], 16) for i in (0, 2, 4))  # type: ignore[assignment]

            _img = Image.open(_resource_path(os.path.join("ig", "ArkLandBR.png"))).convert("RGBA")
            _img.thumbnail((280, 280), Image.LANCZOS)

            # Blend sobre fundo com ~8% de opacidade
            _r, _g, _b, _a = _img.split()
            _a = _a.point(lambda x: int(x * 0.08))
            _img = Image.merge("RGBA", (_r, _g, _b, _a))
            _bg = Image.new("RGBA", _img.size, _bg_rgb + (255,))
            _composite = Image.alpha_composite(_bg, _img).convert("RGB")

            self._wm_photo = ImageTk.PhotoImage(_composite)
            self._wm_bg_hex = theme["bg"]
        except Exception:
            self._wm_photo = None
            self._wm_bg_hex = "#020617"

    def _apply_watermark_to_frame(self, frame: "ctk.CTkFrame") -> None:
        """Aplica o watermark no canto inferior-direito de um frame de página."""
        import tkinter as _tk
        photo = getattr(self, "_wm_photo", None)
        if not photo:
            return
        bg = getattr(self, "_wm_bg_hex", "#020617")
        lbl = _tk.Label(frame, image=photo, bd=0, highlightthickness=0, bg=bg)
        lbl.place(relx=0.99, rely=0.99, anchor="se")
        # lower() após todos os widgets de grid serem adicionados pelo builder
        frame.after(0, lbl.lower)

    # ─────────────────────────────────────────────────────────────────────────
    # Auto-start de serviços
    # ─────────────────────────────────────────────────────────────────────────

    def _asm_scan_running_servers(self) -> None:
        """Detecta servidores ARK já em execução e reconecta o gerenciamento TEK."""
        import threading

        def _worker() -> None:
            servers = self.asm_config_manager.servers
            count = self.asm_server_manager.scan_running_servers(servers)
            if count:
                self.after(0, self._asm_refresh_dashboard)
                self.after(0, self._rebuild_server_sidebar)

        threading.Thread(target=_worker, daemon=True, name="AsmScanRunning").start()

    def _auto_start_services(self) -> None:
        """Inicia sync e agente remoto automaticamente se configurados."""
        cfg = self.config_manager.config
        # Sync de pastas — inicia se houver ciclos configurados
        cycles = cfg.sync_cycles or []
        has_paths = any(
            any(str(p).strip() for p in (
                c.get("folders", []) if isinstance(c, dict) else c
            ))
            for c in cycles
        )
        if has_paths:
            self._start_sync_engine()
        # Agente remoto — inicia se estava ativo na sessão anterior
        if getattr(cfg, "remote_agent_enabled", False):
            self._start_remote_agent()

    def _auto_start_webstore(self) -> None:
        """Inicia a Web Store automaticamente no boot, sem precisar abrir a aba da Loja."""
        import logging as _log2
        try:
            from .pages.customshop_panel import auto_start_webstore
            auto_start_webstore(self)
        except Exception as _exc:
            _log2.getLogger(__name__).warning(
                "auto_start_webstore error: %s", _exc, exc_info=True
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Preferências de UI (persistência do tema)
    # ─────────────────────────────────────────────────────────────────────────

    def _load_ui_prefs(self) -> None:
        """Lê ui_prefs.json e aplica variante de tema."""
        import json as _json
        try:
            if self._prefs_file.exists():
                data = _json.loads(self._prefs_file.read_text(encoding="utf-8"))
                set_tek_variant(data.get("theme_variant", "dark"))
            else:
                set_tek_variant("dark")
        except Exception:
            set_tek_variant("dark")

    def _save_ui_prefs(self) -> None:
        """Persiste variante de tema em ui_prefs.json."""
        import json as _json
        try:
            self._prefs_file.parent.mkdir(parents=True, exist_ok=True)
            self._prefs_file.write_text(
                _json.dumps({"theme_variant": get_tek_variant()}, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _toggle_theme(self) -> None:
        """Alterna entre modo escuro e modo claro, reconstrói a interface."""
        new_variant = "light" if get_tek_variant() == "dark" else "dark"
        set_tek_variant(new_variant)
        self._save_ui_prefs()

        ctk.set_appearance_mode("light" if new_variant == "light" else "dark")

        theme = get_theme("tek")
        self.configure(fg_color=theme["bg"])
        self._page_area.configure(fg_color=theme["bg"])

        # Reconstrói sidebar com cores novas
        self._sidebar.destroy()
        self._build_sidebar()

        # Reconstrói watermark
        try:
            if hasattr(self, "_bg_watermark_lbl") and self._bg_watermark_lbl.winfo_exists():
                self._bg_watermark_lbl.destroy()
        except Exception:
            pass
        self.after(50, self._setup_bg_watermark)

        # Reconstrói frame atual
        _active = self._nav_active or "dashboard"
        self._show_frame(_active)

    # ─────────────────────────────────────────────────────────────────────────
    # Sidebar
    # ─────────────────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> None:
        self._sidebar_server_rows = {}
        self._sidebar_server_btns = {}
        self._sidebar_empty_lbl = None
        from .pages.build_sidebar_tek import build_sidebar_tek as _build
        _build(self)
        return

    def _build_sidebar_inline(self) -> None:
        """Versão inline original — mantida como fallback, não chamada diretamente."""
        theme = get_theme("tek")
        sb_bg   = theme["sidebar_bg"]
        accent  = theme["accent"]
        sep_col = theme["separator"]
        t_sec   = theme["text_secondary"]
        t_muted = theme["text_muted"]

        sb = ctk.CTkFrame(self, width=_SIDEBAR_W, corner_radius=0, fg_color=sb_bg)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)
        sb.grid_columnconfigure(0, weight=1)
        self._sidebar = sb

        # ── Logo / Título ─────────────────────────────────────────────────────
        logo_f = ctk.CTkFrame(sb, fg_color="transparent")
        logo_f.grid(row=0, column=0, padx=16, pady=(20, 0), sticky="ew")
        logo_f.grid_columnconfigure(1, weight=1)

        logo_loaded = False
        try:
            from PIL import Image  # type: ignore[reportMissingImports]
            _img = Image.open(_resource_path(os.path.join("ig", "ark_manager.png")))
            _logo_ctk = ctk.CTkImage(light_image=_img, dark_image=_img, size=(54, 36))
            ctk.CTkLabel(logo_f, image=_logo_ctk, text="").grid(row=0, column=0, rowspan=2, padx=(0, 10))
            logo_loaded = True
        except Exception:
            pass

        title_col = 1 if logo_loaded else 0
        ctk.CTkLabel(
            logo_f, text="ARKLAND",
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color=accent,
            anchor="w",
        ).grid(row=0, column=title_col, sticky="ew")
        ctk.CTkLabel(
            logo_f, text="Server Manager",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=t_muted,
            anchor="w",
        ).grid(row=1, column=title_col, sticky="ew")

        # ── Separador ────────────────────────────────────────────────────────
        ctk.CTkFrame(sb, height=1, fg_color=sep_col).grid(
            row=1, column=0, sticky="ew", padx=16, pady=(4, 8))

        # ── Navegação principal ───────────────────────────────────────────────
        nav_items = [
            ("⊞", "dashboard",  "Dashboard"),
            ("🔄", "sync",       "Sincronização"),
            ("⚡", "buffs",      "BUFFs"),
            ("📊", "desempenho", "Desempenho"),
            ("🔗", "clusters",   "Clusters"),
            ("🖥", "remoto",     "Remoto"),
            ("⚙", "settings",   "Configurações"),
            ("ℹ", "about",      "Sobre"),
        ]
        self._nav_btns: Dict[str, ctk.CTkButton] = {}
        for i, (icon, key, label) in enumerate(nav_items):
            btn = ctk.CTkButton(
                sb, text=f"  {icon}  {label}", anchor="w",
                width=_SIDEBAR_W - 24, height=40,
                fg_color="transparent",
                text_color=accent if key == self._nav_active else t_sec,
                hover_color=theme["accent_hover"],
                corner_radius=10,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold" if key == self._nav_active else "normal"),
                command=lambda k=key: self._show_frame(k),
            )
            btn.grid(row=3 + i, column=0, padx=12, pady=2, sticky="ew")
            self._nav_btns[key] = btn

        # ── Separador + seção Servidores ──────────────────────────────────────
        ctk.CTkFrame(sb, height=1, fg_color=sep_col).grid(
            row=11, column=0, sticky="ew", padx=16, pady=(8, 6))

        srv_hdr = ctk.CTkFrame(sb, fg_color="transparent")
        srv_hdr.grid(row=12, column=0, padx=16, pady=(0, 4), sticky="ew")
        srv_hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            srv_hdr, text="SERVIDORES",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=t_muted,
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            srv_hdr, text="＋", width=26, height=22,
            fg_color=theme["accent_muted_bg"],
            hover_color=theme["accent_hover"],
            text_color=accent,
            font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=6,
            command=self._asm_add_server_dialog,
        ).grid(row=0, column=1)

        # Frame scrollável para lista de servidores
        self._servers_list_sb = ctk.CTkScrollableFrame(
            sb, fg_color="transparent", height=160,
            scrollbar_button_color=sep_col,
        )
        self._servers_list_sb.grid(row=13, column=0, sticky="ew", padx=8)
        self._servers_list_sb.grid_columnconfigure(0, weight=1)

        # ── Rodapé: relógio + versão + toggle tema ────────────────────────────
        ctk.CTkFrame(sb, height=1, fg_color=sep_col).grid(
            row=14, column=0, sticky="ew", padx=16, pady=(8, 4))
        footer_f = ctk.CTkFrame(sb, fg_color="transparent")
        footer_f.grid(row=15, column=0, padx=16, pady=(0, 4), sticky="ew")
        footer_f.grid_columnconfigure(0, weight=1)
        self._sidebar_clock_lbl = ctk.CTkLabel(
            footer_f, text="",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=t_muted,
        )
        self._sidebar_clock_lbl.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            footer_f, text=f"v{APP_VERSION}",
            font=ctk.CTkFont(size=10), text_color=t_muted,
        ).grid(row=0, column=1, sticky="e")

        # Botão toggle claro/escuro
        _is_light = get_tek_variant() == "light"
        _toggle_icon = "☀ Claro" if _is_light else "🌙 Escuro"
        _toggle_fg   = theme["accent_muted_bg"]
        ctk.CTkButton(
            sb, text=_toggle_icon,
            width=_SIDEBAR_W - 32, height=28,
            fg_color=_toggle_fg,
            hover_color=theme["accent_hover"],
            text_color=accent,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            corner_radius=8,
            command=self._toggle_theme,
        ).grid(row=16, column=0, padx=16, pady=(0, 14), sticky="ew")

        self.after(100, self._sidebar_clock_tick)
        self.after(60_000, self._asm_scheduler_tick)

        # Popula lista de servidores
        self._rebuild_server_sidebar(immediate=True)

    def _sidebar_clock_tick(self) -> None:
        """Atualiza o relógio no rodapé da sidebar."""
        try:
            if not self._sidebar_clock_lbl.winfo_exists():
                return
            now = datetime.now()
            self._sidebar_clock_lbl.configure(text=now.strftime("%d/%m/%Y  %H:%M:%S"))
            self.after(1000, self._sidebar_clock_tick)
        except Exception:
            pass

    def _rebuild_server_sidebar(self, *, immediate: bool = False) -> None:
        """Reconstrói a lista de servidores na sidebar (debounced por padrão)."""
        if immediate:
            self._rebuild_server_sidebar_now()
            return
        job = getattr(self, "_sidebar_rebuild_job", None)
        if job:
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._sidebar_rebuild_job = self.after(400, self._rebuild_server_sidebar_now)

    def _rebuild_server_sidebar_now(self) -> None:
        """Executa rebuild imediato da sidebar."""
        self._sidebar_rebuild_job = None

        theme   = get_theme("tek")
        sb_bg   = theme["sidebar_bg"]
        t_sec   = theme["text_secondary"]
        hover   = theme["accent_hover"]

        servers = self.asm_config_manager.servers
        existing_ids = set(self._sidebar_server_rows.keys())
        current_ids = {srv.id for srv in servers}

        for removed_id in existing_ids - current_ids:
            row = self._sidebar_server_rows.pop(removed_id, None)
            btn = self._sidebar_server_btns.pop(removed_id, None)
            if btn is not None:
                try:
                    btn.destroy()
                except Exception:
                    pass
            if row and row.get("frame") is not None:
                try:
                    row["frame"].destroy()
                except Exception:
                    pass

        if not servers:
            for row in self._sidebar_server_rows.values():
                try:
                    row["frame"].destroy()
                except Exception:
                    pass
            self._sidebar_server_rows.clear()
            self._sidebar_server_btns.clear()
            if not self._sidebar_empty_lbl or not self._sidebar_empty_lbl.winfo_exists():
                self._sidebar_empty_lbl = ctk.CTkLabel(
                    self._servers_list_sb,
                    text="Nenhum servidor.\nClique ＋ para adicionar.",
                    text_color=theme["text_muted"],
                    font=ctk.CTkFont(size=10), justify="center",
                )
            self._sidebar_empty_lbl.pack(pady=12)
            return

        if self._sidebar_empty_lbl and self._sidebar_empty_lbl.winfo_exists():
            self._sidebar_empty_lbl.destroy()
        self._sidebar_empty_lbl = None

        for srv in servers:
            inst   = self.asm_server_manager.get_instance(srv.id)
            status = inst.status if inst else ASM_STATUS_STOPPED
            dot_color = (
                "#22c55e" if status == ASM_STATUS_RUNNING
                else "#f59e0b" if status in ("starting", "stopping", "updating")
                else "#64748b"
            )
            row = self._sidebar_server_rows.get(srv.id)
            if row is None:
                row_f = ctk.CTkFrame(self._servers_list_sb, fg_color="transparent")
                row_f.grid_columnconfigure(1, weight=1)

                dot_lbl = tk.Label(
                    row_f, text="●", fg=dot_color,
                    bg=sb_bg, font=("Segoe UI", 9),
                )
                dot_lbl.grid(row=0, column=0, padx=(4, 2))

                btn = ctk.CTkButton(
                    row_f, text=srv.name, anchor="w", height=32,
                    fg_color="transparent", text_color=t_sec,
                    hover_color=hover, corner_radius=8,
                    font=ctk.CTkFont(size=11),
                    command=lambda sid=srv.id: self._asm_open_server_panel(sid),
                )
                btn.grid(row=0, column=1, sticky="ew", padx=(0, 4))

                row = {"frame": row_f, "dot": dot_lbl, "btn": btn}
                self._sidebar_server_rows[srv.id] = row
                self._sidebar_server_btns[srv.id] = btn
            else:
                row["dot"].configure(fg=dot_color, bg=sb_bg)
                row["btn"].configure(text=srv.name, text_color=t_sec, hover_color=hover)

            row["frame"].pack_forget()
            row["frame"].pack(fill="x", pady=1)

    def _set_nav_active(self, key: str) -> None:
        """Atualiza estilo do botão de navegação ativo."""
        theme  = get_theme("tek")
        accent = theme["accent"]
        t_sec  = theme["text_secondary"]
        self._nav_active = key
        for k, btn in getattr(self, "_nav_btns", {}).items():
            if k == key:
                btn.configure(text_color=accent, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"))
            else:
                btn.configure(text_color=t_sec, font=ctk.CTkFont(family="Segoe UI", size=12))



    # ─────────────────────────────────────────────────────────────────────────
    # Navegação entre frames
    # ─────────────────────────────────────────────────────────────────────────

    def _show_frame(self, name: str, **kwargs) -> None:
        """Troca o conteúdo principal pelo frame indicado (com cache via show_frame_tek)."""
        from .pages.show_frame_tek import show_frame_tek as _show
        _show(self, name, **kwargs)

    def _show_frame_inline(self, name: str, **kwargs) -> None:
        """Versão inline original — mantida como fallback, não chamada diretamente."""
        if self._current_frame:
            self._current_frame.destroy()
            self._current_frame = None

        self._set_nav_active(name if name in ("dashboard", "settings", "about") else "")

        frame = ctk.CTkFrame(self._page_area, fg_color=get_theme("tek")["bg"],
                             corner_radius=0)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        self._current_frame = frame

        if name == "dashboard":
            from .asm_ui.asm_dashboard import build_asm_dashboard
            build_asm_dashboard(self, frame)

        elif name == "sync":
            from .pages.build_sync_panel import build_sync_panel
            build_sync_panel(self, frame)

        elif name == "buffs":
            from .pages.build_buffs_panel import build_buffs_panel
            build_buffs_panel(self, frame)
            if self._buff_manager is None:
                self._init_buff_manager()
            self._refresh_buffs_ui()

        elif name == "desempenho":
            from .pages.performance_panel import build_performance_panel
            build_performance_panel(self, frame)
            self._start_perf_monitor()

        elif name == "clusters":
            from .pages.build_clusters_panel import build_clusters_panel
            build_clusters_panel(self, frame)

        elif name == "remoto":
            scroll = ctk.CTkScrollableFrame(frame, fg_color=get_theme("tek")["bg"], corner_radius=0)
            scroll.grid(row=0, column=0, sticky="nsew")
            scroll.grid_columnconfigure(0, weight=1)
            from .pages.remote_panel import build_remote_panel
            build_remote_panel(self, scroll)

        elif name == "settings":
            scroll = ctk.CTkScrollableFrame(frame, fg_color=get_theme("tek")["bg"], corner_radius=0)
            scroll.grid(row=0, column=0, sticky="nsew")
            scroll.grid_columnconfigure(0, weight=1)
            from .pages.global_config import build_global_config
            build_global_config(self, scroll)

        elif name == "about":
            scroll = ctk.CTkScrollableFrame(frame, fg_color=get_theme("tek")["bg"], corner_radius=0)
            scroll.grid(row=0, column=0, sticky="nsew")
            scroll.grid_columnconfigure(0, weight=1)
            from .pages.build_about import build_about
            build_about(self, scroll)

        elif name == "server_panel":
            from .asm_ui.asm_server_panel import build_asm_server_panel
            srv: AsmServerConfig = kwargs["srv"]
            build_asm_server_panel(self, frame, srv)

        # Watermark em todas as páginas, atrás do conteúdo
        self._apply_watermark_to_frame(frame)

    # ─────────────────────────────────────────────────────────────────────────
    # Dashboard
    # ─────────────────────────────────────────────────────────────────────────

    def _asm_refresh_dashboard(self, *, immediate: bool = False) -> None:
        """Atualiza os cards do dashboard (debounced por padrão)."""
        if immediate:
            self._asm_refresh_dashboard_now()
            return
        job = getattr(self, "_dash_refresh_job", None)
        if job:
            try:
                self.after_cancel(job)
            except Exception:
                pass
        self._dash_refresh_job = self.after(400, self._asm_refresh_dashboard_now)

    def _asm_refresh_dashboard_now(self) -> None:
        """Executa refresh imediato do dashboard."""
        self._dash_refresh_job = None
        from .asm_ui.asm_dashboard import _refresh_asm_dashboard
        _refresh_asm_dashboard(self)

    # ─────────────────────────────────────────────────────────────────────────
    # Diálogo: Novo Servidor
    # ─────────────────────────────────────────────────────────────────────────

    def _asm_add_server_dialog(self) -> None:
        from .asm_ui.asm_add_server_dialog import asm_add_server_dialog
        asm_add_server_dialog(self)

    # ─────────────────────────────────────────────────────────────────────────
    # Painel de configuração
    # ─────────────────────────────────────────────────────────────────────────

    def _asm_open_server_panel(self, server_id: str) -> None:
        srv = self.asm_config_manager.get_server(server_id)
        if srv:
            self._show_frame("server_panel", srv=srv)

    # ─────────────────────────────────────────────────────────────────────────
    # Start / Stop / Restart
    # ─────────────────────────────────────────────────────────────────────────

    def _validate_server_config(self, srv: AsmServerConfig) -> list[str]:
        """Retorna lista de erros de configuração obrigatória em branco ou padrão inseguro."""
        errors = []
        if not srv.install_dir or not srv.install_dir.strip():
            errors.append("Diretório de instalação não configurado")
        from .asm_engine.asm_ini_manager import effective_session_name
        if not effective_session_name(srv).strip():
            errors.append("Nome da sessão está vazio (preencha 'Nome da sessão' ou o nome do servidor no gerenciador)")
        if not srv.admin_password or not srv.admin_password.strip():
            errors.append("Senha admin não definida (obrigatória para RCON e acesso administrativo)")
        return errors

    def _asm_persist_server(
        self, srv: AsmServerConfig, *, write_ini_disk: bool = True,
    ) -> AsmServerConfig:
        """Paridade com o modo primitivo: equivalente a _save_server_config(silent=True).

        O primitivo sempre lê os widgets, grava o JSON e escreve os INIs antes de
        iniciar/instalar. O TEK tinha caminhos paralelos (AsmSteamCmd, asm_ini_manager)
        que pulavam essa etapa e causavam regressões (branch, SessionName).
        """
        import logging
        import os

        fresh = self.asm_config_manager.get_server(srv.id) or srv
        try:
            from .asm_ui.asm_server_panel import _sync_ui_to_cfg
            _sync_ui_to_cfg(self, fresh)
        except Exception:
            pass

        # Igual server_save.py / tab_general_prim: Nome do Servidor = campo OU nome interno
        sn = (fresh.session_name or "").strip()
        if not sn:
            fresh.session_name = (fresh.name or "").strip() or "My ARK Server"

        try:
            self.asm_config_manager.update_server(fresh)
        except Exception as exc:
            logging.getLogger("arkland").warning("persist server JSON falhou: %s", exc)

        if write_ini_disk and fresh.install_dir and os.path.isdir(fresh.install_dir):
            try:
                from .asm_engine.asm_ini_manager import write_ini
                write_ini(fresh)
            except Exception as exc:
                logging.getLogger("arkland").warning("write_ini falhou: %s", exc)

        return fresh

    def _asm_sync_server_cfg(self, srv: AsmServerConfig) -> AsmServerConfig:
        """Alias de _asm_persist_server — mantido para compatibilidade interna."""
        return self._asm_persist_server(srv)

    def _asm_start_server(self, srv: AsmServerConfig, no_mods: bool = False) -> None:
        from tkinter import messagebox

        srv = self._asm_persist_server(srv)
        errors = self._validate_server_config(srv)
        if errors:
            msg = "\n\n".join(f"• {e}" for e in errors)
            messagebox.showerror(
                "Configuração Incompleta",
                f"Não é possível iniciar '{srv.name}':\n\n{msg}\n\n"
                "Corrija as configurações antes de iniciar o servidor.",
                parent=self,
            )
            return

        conflicts = self._check_port_conflicts(srv)
        if conflicts:
            msg = "\n".join(f"• Porta {p} ({label}) já está em uso" for p, label in conflicts)
            messagebox.showwarning(
                "Conflito de Portas",
                f"Não é possível iniciar '{srv.name}':\n\n{msg}\n\n"
                "Verifique se outro processo está usando essas portas.",
                parent=self,
            )
            return

        from .asm_engine.asm_mod_utils import validate_map_mod_on_disk
        map_issues = validate_map_mod_on_disk(srv)
        if map_issues and not no_mods:
            msg = "\n\n".join(f"• {e}" for e in map_issues)
            if not messagebox.askyesno(
                "Mapa mod — possível problema",
                f"O servidor '{srv.name}' pode não carregar o mapa:\n\n{msg}\n\n"
                "Deseja iniciar mesmo assim?",
                parent=self,
            ):
                return

        cfg = srv
        if no_mods and srv.active_mods:
            import copy
            cfg = copy.copy(srv)
            cfg.active_mods = []
        self.asm_server_manager.start(
            cfg,
            on_done=lambda ok, msg: self.after(0, self._asm_refresh_dashboard),
        )
        self._asm_refresh_dashboard()

    def _check_port_conflicts(self, srv: AsmServerConfig) -> list:
        """Retorna lista de (porta, label) que estão em uso."""
        import socket
        conflicts = []
        checks = [
            (srv.server_port, "game"),
            (srv.query_port,  "query"),
        ]
        if srv.rcon_enabled:
            checks.append((srv.rcon_port, "RCON"))
        for port, label in checks:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.3)
                    if s.connect_ex(("127.0.0.1", port)) == 0:
                        conflicts.append((port, label))
            except Exception:
                pass
        return conflicts

    def _clear_perf_critical_log(self) -> None:
        log = getattr(self, "_perf_critical_log", None)
        if log:
            log.configure(state="normal")
            log.delete("1.0", "end")
            log.configure(state="disabled")

    def _asm_stop_server(self, server_id: str) -> None:
        self.asm_server_manager.stop(
            server_id,
            on_done=lambda ok, msg: self.after(0, self._asm_refresh_dashboard),
        )
        self._asm_refresh_dashboard()

    def _asm_restart_server(self, srv: AsmServerConfig) -> None:
        srv = self._asm_persist_server(srv)
        self.asm_server_manager.restart(
            srv,
            on_done=lambda ok, msg: self.after(0, self._asm_refresh_dashboard),
        )
        self._asm_refresh_dashboard()

    def _asm_open_rcon(self, srv: AsmServerConfig) -> None:
        from .asm_ui.asm_rcon_window import open_asm_rcon_window
        open_asm_rcon_window(self, srv)

    def _asm_open_spawn_exact(self, srv: Optional[AsmServerConfig] = None) -> None:
        from .asm_ui.spawn_exact_panel import open_spawn_exact_panel
        open_spawn_exact_panel(self, srv)

    def _asm_open_player_list(self, srv: AsmServerConfig) -> None:
        from .asm_ui.asm_player_list import open_asm_player_list
        open_asm_player_list(self, srv)

    def _asm_open_save_restore(self, srv: AsmServerConfig) -> None:
        from .asm_ui.asm_save_restore import open_asm_save_restore
        open_asm_save_restore(self, srv)

    def _asm_open_workshop(self, srv: AsmServerConfig) -> None:
        from .asm_ui.asm_workshop import open_asm_workshop
        open_asm_workshop(self, srv)

    def _asm_open_file_manager(self, srv: AsmServerConfig) -> None:
        from .asm_ui.asm_file_manager import open_asm_file_manager
        open_asm_file_manager(self, srv)

    def _asm_open_firewall(self, srv: AsmServerConfig) -> None:
        from .asm_ui.asm_firewall import open_asm_firewall_dialog
        open_asm_firewall_dialog(self, srv)

    def _asm_open_perf(self, srv: AsmServerConfig) -> None:
        from .asm_ui.asm_perf_chart import open_asm_perf_window
        open_asm_perf_window(self, srv)

    def _asm_open_tribe_log(self, srv: AsmServerConfig) -> None:
        from .asm_ui.asm_tribe_log import open_asm_tribe_log
        open_asm_tribe_log(self, srv)

    def _asm_open_engram_editor(self, srv: AsmServerConfig) -> None:
        from .asm_ui.asm_engram_editor import open_asm_engram_editor
        open_asm_engram_editor(self, srv)

    def _asm_open_spawner_editor(self, srv: AsmServerConfig) -> None:
        from .asm_ui.asm_spawner_editor import open_asm_spawner_editor
        open_asm_spawner_editor(self, srv)

    def _asm_open_ai_assistant(self, srv: AsmServerConfig) -> None:
        from .asm_ui.asm_ai_assistant import open_asm_ai_assistant
        open_asm_ai_assistant(self, srv)

    def _asm_open_monitor(self, srv: AsmServerConfig) -> None:
        from .asm_ui.asm_monitor_window import open_asm_monitor
        open_asm_monitor(self, srv)

    def _asm_open_server_log(self, srv: AsmServerConfig) -> None:
        from .asm_ui.asm_server_log_window import open_asm_server_log
        open_asm_server_log(self, srv)

    def _asm_update_mods(self, srv: AsmServerConfig) -> None:
        """Baixa/atualiza mods do servidor via SteamCMD (chamável pela bulk action)."""
        if not srv.active_mods:
            return
        from .asm_ui.asm_workshop import open_asm_workshop
        open_asm_workshop(self, srv)

    # ─────────────────────────────────────────────────────────────────────────
    # Scheduler automático (tick a cada 60 s)
    # ─────────────────────────────────────────────────────────────────────────

    def _asm_scheduler_tick(self) -> None:
        """Delega para asm_scheduler_tick.py (auto-restart, update, backup, broadcast)."""
        from .pages.asm_scheduler_tick import asm_scheduler_tick as _tick
        _tick(self)

    def _asm_do_auto_backup(self, srv: AsmServerConfig) -> None:
        """Executa backup automático do servidor (disparado pelo scheduler diário)."""
        self._run_global_backup()

    def _run_global_backup(self) -> None:
        """Backup ZIP de todos os servidores TEK (manual ou agendado)."""
        import threading as _th

        if self._global_backup_running:
            self._global_log("[Backup] Backup global já em andamento.", "warning")
            return
        self._global_backup_running = True
        bk = self.config_manager.config.backup

        def _worker():
            try:
                servers = self.asm_config_manager.servers
                created = self._backup_manager.backup_all_servers(servers, bk)
                active = [s for s in servers if (s.install_dir or "").strip()]
                if not active or created:
                    self._global_backup_last_run = datetime.now()
            except Exception as exc:
                import logging
                logging.getLogger("arkland").warning("global_backup falhou: %s", exc)
            finally:
                self._global_backup_running = False

        _th.Thread(target=_worker, daemon=True).start()

    def _run_scheduled_db_backup(self) -> None:
        """Backup automático do MariaDB usando credenciais salvas."""
        import threading as _th
        from .pages.db_local_server import DbLocalServer

        if self._db_backup_running:
            return
        cfg = self.config_manager.config.db_backup
        if not cfg.enabled:
            return

        prefs = DbLocalServer._load_prefs().get("shop_db") or {}
        shop = getattr(self.config_manager.config, "shop", None)
        host = (prefs.get("host") or getattr(shop, "orders_db_host", "") or "127.0.0.1").strip()
        port = int(prefs.get("port") or getattr(shop, "orders_db_port", None) or 3306)
        user = (prefs.get("user") or getattr(shop, "orders_db_user", "") or "arkland").strip()
        password = prefs.get("password") or getattr(shop, "orders_db_password", "") or ""
        if host in ("127.0.0.1", "localhost", "::1") and user == "root" and not password:
            password = DbLocalServer.get_root_password()

        self._db_backup_running = True

        def _worker():
            try:
                path = self._db_backup_manager.create_backup(
                    cfg, host=host, port=port, user=user, password=password,
                )
                if path:
                    self._db_backup_last_run = datetime.now()
            except Exception as exc:
                import logging
                logging.getLogger("arkland").warning("db_backup falhou: %s", exc)
            finally:
                self._db_backup_running = False

        _th.Thread(target=_worker, daemon=True).start()

    def _asm_do_scheduled_broadcast(self, srv: AsmServerConfig, message: str) -> None:
        """Envia broadcast RCON agendado ao servidor."""
        import threading as _th

        def _worker():
            if not (srv.rcon_enabled and srv.admin_password):
                return
            try:
                from .rcon_client import RconClient
                host = srv.server_ip or "127.0.0.1"
                rc = RconClient(host, srv.rcon_port, srv.admin_password)
                rc.connect()
                rc.send_command_safe(f"broadcast {message}")
                rc.disconnect()
            except Exception as exc:
                import logging
                logging.getLogger("arkland").warning("scheduled_broadcast falhou: %s", exc)

        _th.Thread(target=_worker, daemon=True).start()

    def _asm_do_scheduled_restart(self, srv: AsmServerConfig) -> None:
        """Envia aviso RCON com countdown e reinicia o servidor."""
        import threading as _th  # noqa: PLC0415

        def _worker():
            countdown = max(1, getattr(srv, "restart_countdown_minutes", 15))
            host = srv.server_ip or "127.0.0.1"
            if srv.rcon_enabled and srv.admin_password:
                try:
                    from .rcon_client import RconClient  # noqa: PLC0415
                    rc = RconClient(host, srv.rcon_port, srv.admin_password)
                    rc.connect()
                    rc.send_command_safe(
                        f"broadcast [ARKLAND] Servidor reiniciará em {countdown} minuto(s)."
                    )
                    rc.disconnect()
                except Exception:
                    pass
            self.after(0, lambda: self._asm_restart_server(srv))

        _th.Thread(target=_worker, daemon=True).start()

    def _ensure_buff_manager(self) -> None:
        """Inicia o scheduler de BUFFs ao abrir o app (não só ao abrir a aba)."""
        if self._buff_manager is None:
            self._init_buff_manager()

    def _asm_check_update_worker(self, srv: AsmServerConfig) -> None:
        """Verifica no Steam se há atualização disponível para o servidor."""
        import threading as _th

        def _log(msg: str, level: str = "info") -> None:
            if hasattr(self, "_global_log"):
                self.after(0, lambda m=msg, lv=level: self._global_log(m, lv))

        try:
            from .asm_engine.asm_steamcmd import AsmSteamCmd
            from .asm_engine.asm_server_config import ASM_STATUS_RUNNING

            scmd_path = (
                getattr(getattr(self.config_manager, "config", None), "steamcmd_path", None)
                or AsmSteamCmd.find_steamcmd()
            )
            if not scmd_path:
                _log(f"[AutoUpdate] {srv.name}: SteamCMD não configurado.", "warning")
                return
            if not srv.install_dir:
                _log(f"[AutoUpdate] {srv.name}: pasta de instalação vazia.", "warning")
                return

            build_before = AsmSteamCmd.read_installed_build_id(srv.install_dir)
            was_running = self.asm_server_manager.get_status(srv.id) == ASM_STATUS_RUNNING
            done = _th.Event()
            result: list = [False, ""]

            def _on_done(ok: bool, msg: str) -> None:
                result[0], result[1] = ok, msg
                done.set()

            sc = AsmSteamCmd(scmd_path, on_log=lambda m: _log(f"[AutoUpdate] {m}", "debug"))
            _log(f"[AutoUpdate] Verificando atualização do servidor '{srv.name}'…", "info")
            sc.install_server(
                install_dir=srv.install_dir,
                branch=getattr(srv, "branch_name", ""),
                branch_password=getattr(srv, "branch_password", ""),
                validate=False,
                on_done=_on_done,
            )
            if not done.wait(timeout=3600):
                _log(f"[AutoUpdate] {srv.name}: timeout aguardando SteamCMD.", "error")
                return

            ok, msg = result[0], result[1]
            build_after = AsmSteamCmd.read_installed_build_id(srv.install_dir)
            updated = bool(build_after and build_after != build_before)

            if not ok:
                _log(f"[AutoUpdate] {srv.name}: falhou — {msg}", "error")
                return

            if updated:
                _log(
                    f"[AutoUpdate] {srv.name}: build atualizado "
                    f"({build_before or '?'} → {build_after}). {msg}",
                    "info",
                )
            else:
                _log(f"[AutoUpdate] {srv.name}: já está na versão mais recente ({build_after or msg}).", "info")
                return

            au = getattr(self.config_manager.config, "auto_update", None)
            restart = bool(getattr(au, "replace_restart_after_update", False))
            if was_running and restart:
                _log(f"[AutoUpdate] {srv.name}: reiniciando após atualização…", "info")
                self.after(0, lambda s=srv: self._asm_restart_server(s))
            elif was_running:
                _log(
                    f"[AutoUpdate] {srv.name}: atualizado — reinicie manualmente ou ative "
                    "'Reiniciar após atualização' em Configurações globais.",
                    "warning",
                )
        except Exception as exc:
            _log(f"[AutoUpdate] {srv.name}: erro — {exc}", "error")

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers de UI (usados pelos builders de pages)
    # ─────────────────────────────────────────────────────────────────────────

    def _section_lbl(self, parent, row: int, text: str) -> None:
        theme = get_theme("tek")
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=theme["accent_label"],
        ).grid(row=row, column=0, columnspan=4, padx=16, pady=(10, 2), sticky="w")

    def _browse_dir(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory(parent=self, title="Selecionar pasta")
        if path:
            var.set(path)

    def _browse_file(self, var: tk.StringVar, title: str = "Selecionar arquivo") -> None:
        path = filedialog.askopenfilename(parent=self, title=title)
        if path:
            var.set(path)

    def _browse_sync_folder(self, var: tk.StringVar) -> None:
        self._browse_dir(var)

    # ─────────────────────────────────────────────────────────────────────────
    # SteamCMD
    # ─────────────────────────────────────────────────────────────────────────

    def _download_steamcmd(self) -> None:
        from .pages.download_steamcmd import download_steamcmd
        download_steamcmd(self)

    # ─────────────────────────────────────────────────────────────────────────
    # Configurações Globais
    # ─────────────────────────────────────────────────────────────────────────

    def _save_global_config(self) -> None:
        import winreg as _winreg  # type: ignore[import]
        cfg = self.config_manager.config
        cfg.steamcmd_path        = getattr(self, "_steamcmd_var", tk.StringVar()).get().strip()
        cfg.default_install_dir  = getattr(self, "_default_dir_var", tk.StringVar()).get().strip()
        cfg.startup_with_windows = getattr(self, "_cfg_startup_var", tk.BooleanVar()).get()
        cfg.minimize_to_tray     = getattr(self, "_cfg_minimize_tray_var", tk.BooleanVar()).get()
        cfg.log_debug            = getattr(self, "_cfg_log_debug_var", tk.BooleanVar()).get()
        cfg.steam_api_key        = getattr(self, "_steam_api_key_var", tk.StringVar()).get().strip()
        # Discord
        dc = cfg.discord_notify
        dc.enabled       = getattr(self, "_discord_enabled_var", tk.BooleanVar()).get()
        dc.webhook_url   = getattr(self, "_discord_url_var", tk.StringVar()).get().strip()
        dc.sender_name   = getattr(self, "_discord_sender_var", tk.StringVar()).get().strip() or "ARKLAND"
        dc.notify_start  = getattr(self, "_discord_notify_start", tk.BooleanVar()).get()
        dc.notify_stop   = getattr(self, "_discord_notify_stop", tk.BooleanVar()).get()
        dc.notify_crash  = getattr(self, "_discord_notify_crash", tk.BooleanVar()).get()
        dc.notify_update = getattr(self, "_discord_notify_update", tk.BooleanVar()).get()
        dc.notify_backup = getattr(self, "_discord_notify_backup", tk.BooleanVar()).get()
        dc.mod_changelog_webhook = getattr(self, "_discord_mod_changelog_hook", tk.StringVar()).get().strip()
        # Backup
        bk = cfg.backup
        bk.backup_dir          = getattr(self, "_bk_dir_var",           tk.StringVar()).get().strip()
        bk.include_savegames   = getattr(self, "_bk_include_saves_var", tk.BooleanVar()).get()
        bk.include_config      = getattr(self, "_bk_include_config_var", tk.BooleanVar(value=True)).get()
        bk.limit_backup_count  = getattr(self, "_bk_limit_count_var",   tk.BooleanVar(value=True)).get()
        try:
            bk.max_backup_count = max(1, int(getattr(self, "_bk_max_count_var", tk.StringVar(value="10")).get()))
        except ValueError:
            bk.max_backup_count = 10
        bk.exclude_old_backups = bk.limit_backup_count
        bk.rcon_broadcast_mode = getattr(self, "_bk_rcon_mode_var",     tk.StringVar()).get()
        bk.save_message        = getattr(self, "_bk_save_msg_var",      tk.StringVar()).get()
        bk.auto_backup         = getattr(self, "_bk_auto_var",          tk.BooleanVar()).get()
        bk.backup_interval     = getattr(self, "_bk_interval_var",      tk.StringVar()).get().strip()
        # Auto-update
        au = cfg.auto_update
        au.cache_dir                   = getattr(self, "_au_cache_dir_var",      tk.StringVar()).get().strip()
        au.update_interval             = getattr(self, "_au_interval_var",       tk.StringVar()).get().strip()
        au.smart_cache_copy            = getattr(self, "_au_smart_cache_var",    tk.BooleanVar()).get()
        au.validate_server_files       = getattr(self, "_au_validate_var",       tk.BooleanVar()).get()
        au.update_in_parallel          = getattr(self, "_au_parallel_var",       tk.BooleanVar()).get()
        au.update_delay_seconds        = getattr(self, "_au_delay_var",          tk.IntVar()).get()
        au.show_update_reason          = getattr(self, "_au_show_reason_var",    tk.BooleanVar()).get()
        au.update_reason_prefix        = getattr(self, "_au_reason_prefix_var",  tk.StringVar()).get()
        au.replace_restart_after_update = getattr(self, "_au_replace_restart_var", tk.BooleanVar()).get()
        # Shutdown
        sd = cfg.shutdown
        sd.check_online_players  = getattr(self, "_sd_check_online_var",  tk.BooleanVar()).get()
        sd.send_msgs_to_client   = getattr(self, "_sd_send_msgs_var",     tk.BooleanVar()).get()
        sd.grace_period_minutes  = getattr(self, "_sd_grace_var",         tk.IntVar()).get()
        sd.msg1                  = getattr(self, "_sd_msg1_var",          tk.StringVar()).get()
        sd.msg2                  = getattr(self, "_sd_msg2_var",          tk.StringVar()).get()
        sd.msg3                  = getattr(self, "_sd_msg3_var",          tk.StringVar()).get()
        sd.save_message          = getattr(self, "_sd_save_msg_var",      tk.StringVar()).get()
        sd.cancel_message        = getattr(self, "_sd_cancel_msg_var",    tk.StringVar()).get()
        sd.show_reason_all_msgs  = getattr(self, "_sd_show_reason_var",   tk.BooleanVar()).get()
        # Alert messages
        am = cfg.alert_messages
        am.server_stopped       = getattr(self, "_al_stopped_var",    tk.StringVar()).get()
        am.server_shutting_down = getattr(self, "_al_shutting_var",   tk.StringVar()).get()
        am.server_started       = getattr(self, "_al_started_var",    tk.StringVar()).get()
        am.include_ip_port      = getattr(self, "_al_incl_ip_var",    tk.BooleanVar()).get()
        am.ip_port_format       = getattr(self, "_al_ip_fmt_var",     tk.StringVar()).get()
        am.backup_error         = getattr(self, "_al_bk_err_var",     tk.StringVar()).get()
        am.shutdown_error       = getattr(self, "_al_sd_err_var",     tk.StringVar()).get()
        am.restart_error        = getattr(self, "_al_rst_err_var",    tk.StringVar()).get()
        am.update_error         = getattr(self, "_al_upd_err_var",    tk.StringVar()).get()
        am.update_result        = getattr(self, "_al_upd_res_var",    tk.StringVar()).get()
        am.server_update_msg    = getattr(self, "_al_srv_upd_var",    tk.StringVar()).get()
        am.server_status        = getattr(self, "_al_srv_stat_var",   tk.StringVar()).get()
        am.mod_update_detected  = getattr(self, "_al_mod_upd_var",    tk.StringVar()).get()
        am.players_changed      = getattr(self, "_al_players_var",    tk.StringVar()).get()
        am.dino_respawn         = getattr(self, "_al_dino_var",       tk.StringVar()).get()
        # Discord Bot
        db = cfg.discord_bot
        db.enabled              = getattr(self, "_db_enabled_var",       tk.BooleanVar()).get()
        db.token                = getattr(self, "_db_token_var",         tk.StringVar()).get().strip()
        db.server_id            = getattr(self, "_db_server_id_var",     tk.StringVar()).get().strip()
        db.prefix               = getattr(self, "_db_prefix_var",        tk.StringVar()).get().strip() or "asm!"
        db.log_level            = getattr(self, "_db_log_level_var",     tk.StringVar()).get()
        db.alias_all_profiles   = getattr(self, "_db_alias_var",         tk.StringVar()).get().strip() or "all"
        db.allow_backup         = getattr(self, "_db_allow_backup_var",  tk.BooleanVar()).get()
        db.allow_update         = getattr(self, "_db_allow_update_var",  tk.BooleanVar()).get()
        db.allow_restart        = getattr(self, "_db_allow_restart_var", tk.BooleanVar()).get()
        db.allow_shutdown       = getattr(self, "_db_allow_shutdown_var", tk.BooleanVar()).get()
        db.allow_start          = getattr(self, "_db_allow_start_var",   tk.BooleanVar()).get()
        db.allow_stop           = getattr(self, "_db_allow_stop_var",    tk.BooleanVar()).get()
        db.allow_all_bots       = getattr(self, "_db_all_bots_var",      tk.BooleanVar()).get()
        # SMTP
        sm = cfg.smtp
        sm.host                    = getattr(self, "_smtp_host_var",     tk.StringVar()).get().strip()
        sm.port                    = getattr(self, "_smtp_port_var",     tk.IntVar()).get()
        sm.use_ssl                 = getattr(self, "_smtp_ssl_var",      tk.BooleanVar()).get()
        sm.use_default_credentials = getattr(self, "_smtp_defcred_var",  tk.BooleanVar()).get()
        sm.username                = getattr(self, "_smtp_user_var",     tk.StringVar()).get().strip()
        sm.password                = getattr(self, "_smtp_pass_var",     tk.StringVar()).get()
        sm.from_address            = getattr(self, "_smtp_from_var",     tk.StringVar()).get().strip()
        sm.to_address              = getattr(self, "_smtp_to_var",       tk.StringVar()).get().strip()
        sm.notify_auto_backup      = getattr(self, "_smtp_n_backup_var",  tk.BooleanVar()).get()
        sm.notify_auto_update      = getattr(self, "_smtp_n_update_var",  tk.BooleanVar()).get()
        sm.notify_auto_shutdown    = getattr(self, "_smtp_n_shutdown_var", tk.BooleanVar()).get()
        sm.notify_shutdown_restart = getattr(self, "_smtp_n_restart_var", tk.BooleanVar()).get()
        # Windows startup
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_key  = "ARKLAND-ServerManager"
            exe = sys.executable if getattr(sys, "frozen", False) else (
                f'"{sys.executable}" "{os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")}"'
            )
            with _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, key_path, 0, _winreg.KEY_SET_VALUE) as key:
                if cfg.startup_with_windows:
                    _winreg.SetValueEx(key, app_key, 0, _winreg.REG_SZ, exe)
                else:
                    try:
                        _winreg.DeleteValue(key, app_key)
                    except FileNotFoundError:
                        pass
        except Exception:
            pass
        self.config_manager.save()
        self.mod_manager.steamcmd_path = cfg.steamcmd_path
        if self._mod_auto_updater is not None:
            self._mod_auto_updater.set_steam_api_key(cfg.steam_api_key)
        messagebox.showinfo("Salvo", "Configurações globais salvas!", parent=self)

    # ─────────────────────────────────────────────────────────────────────────
    # Sincronização
    # ─────────────────────────────────────────────────────────────────────────

    def _toggle_sync(self) -> None:
        if self._sync_engine and self._sync_engine.is_running:
            self._sync_engine.stop()
        else:
            self._start_sync_engine()

    def _force_sync_once(self) -> None:
        if self._sync_engine is None:
            self._sync_engine = SyncEngine(
                self.config_manager.config,
                on_log=self._on_sync_log,
                on_status_change=self._on_sync_status,
                on_stats_update=self._on_sync_stats,
            )
        self._sync_engine.sync_once()

    def _start_sync_engine(self) -> None:
        if self._sync_engine is None:
            self._sync_engine = SyncEngine(
                self.config_manager.config,
                on_log=self._on_sync_log,
                on_status_change=self._on_sync_status,
                on_stats_update=self._on_sync_stats,
            )
        self._sync_engine.start()

    def _save_sync_config(self) -> None:
        cfg = self.config_manager.config
        cfg.local_cluster_path = getattr(self, "_sync_local_var", tk.StringVar()).get().strip()
        cfg.shared_path        = getattr(self, "_sync_shared_var", tk.StringVar()).get().strip()
        try:
            cfg.sync_interval = max(1, int(getattr(self, "_sync_interval_var", tk.StringVar(value="5")).get()))
        except ValueError:
            cfg.sync_interval = 5
        # Salva ciclos
        numeric_vars = getattr(self, "_sync_numeric_only_vars", [])
        cycles = []
        for i, folder_vars in enumerate(getattr(self, "_sync_cycle_vars", [])):
            paths = [v.get().strip() for v in folder_vars if v.get().strip()]
            if paths:
                numeric_only = numeric_vars[i].get() if i < len(numeric_vars) else False
                cycles.append({"folders": paths, "numeric_only": numeric_only})
        cfg.sync_cycles = cycles
        self.config_manager.save()
        messagebox.showinfo("Salvo", "Configurações de sync salvas!", parent=self)
        if self._sync_engine and self._sync_engine.is_running:
            self._sync_engine.stop()
            self._sync_engine = None
            self._start_sync_engine()

    def _on_sync_log(self, msg: str, level: str = "info") -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        def _do():
            if self._sync_log_box:
                self._sync_log_box.configure(state="normal")
                self._sync_log_box.insert("end", line)
                self._sync_log_box.see("end")
                self._sync_log_box.configure(state="disabled")
        self.after(0, _do)

    def _on_sync_status(self, status: str) -> None:
        from .ui_constants import _GREEN_DARK, _GREEN_HOVER
        _RED_DARK  = "#7a2d2d"
        _RED_HOVER = "#5c1f1f"
        def _do():
            if not self._sync_toggle_btn or not self._sync_status_lbl:
                return
            if status == "running":
                self._sync_status_lbl.configure(text="🟢  Sincronizando", text_color="#4ade80")
                self._sync_toggle_btn.configure(
                    text="⏹  Parar Sync", fg_color=_RED_DARK, hover_color=_RED_HOVER)
            else:
                self._sync_status_lbl.configure(text="⬜  Parado", text_color="gray60")
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

    # ─────────────────────────────────────────────────────────────────────────
    # Atualizações do App
    # ─────────────────────────────────────────────────────────────────────────

    def _check_updates_on_start(self) -> None:
        url = self.config_manager.config.update_url
        if not url:
            return
        self.update_checker.check_async(
            url,
            on_result=lambda info: self.after(0, lambda: self._on_update_result(info)),
        )

    def _check_updates_manual(self) -> None:
        url = self.config_manager.config.update_url
        if not url:
            return
        if self._check_update_btn:
            self._check_update_btn.configure(state="disabled", text="🔍  Verificando...")
        self.update_checker.check_async(
            url,
            on_result=lambda info: self.after(0, lambda: self._on_update_result(info, manual=True)),
        )

    def _on_update_result(self, info: Any, manual: bool = False) -> None:
        from .version import APP_VERSION
        if self._check_update_btn:
            self._check_update_btn.configure(state="normal", text="🔍  Verificar Atualizações")
        if self._last_check_var:
            self._last_check_var.set(datetime.now().strftime("%d/%m/%Y %H:%M"))
        if info is None:
            if self._update_status_var:
                self._update_status_var.set("Erro ao verificar")
            if self._update_status_lbl:
                self._update_status_lbl.configure(text_color="#ff6666")
            return
        if info.is_newer_than(APP_VERSION):
            if self._update_status_var:
                self._update_status_var.set(f"Nova versão disponível: v{info.version}")
            if self._update_status_lbl:
                self._update_status_lbl.configure(text_color="#4ade80")
            if self._install_update_btn:
                self._install_update_btn.configure(state="normal")
            if not manual and not self._update_auto_started and getattr(sys, "frozen", False):
                self._update_auto_started = True
                self.after(500, self._start_download_update)
        else:
            if self._update_status_var:
                self._update_status_var.set("Você está na versão mais recente ✓")
            if self._update_status_lbl:
                self._update_status_lbl.configure(text_color="#94a3b8")

    def _start_download_update(self) -> None:
        from .pages.start_download_update import start_download_update
        start_download_update(self)

    def _on_download_done(self, ok: bool, msg: str) -> None:
        if ok:
            messagebox.showinfo(
                "Atualização",
                "O agente de atualização foi iniciado.\n\n"
                "O ARKLAND será fechado agora. Quando a instalação terminar, o app reiniciará automaticamente.",
                parent=self,
            )
            self.destroy()
            return
        if self._install_update_btn:
            self._install_update_btn.configure(state="normal", text="⬇️  Baixar e Instalar")
        if self._check_update_btn:
            self._check_update_btn.configure(state="normal")
        if msg:
            messagebox.showerror("Atualização", msg, parent=self)

    # ─────────────────────────────────────────────────────────────────────────
    # Sync — ciclos de pasta
    # ─────────────────────────────────────────────────────────────────────────

    def _add_sync_cycle(
        self,
        folders: Optional[List[str]] = None,
        *,
        initial_numeric_only: bool = False,
    ) -> None:
        from .pages.add_sync_cycle import add_sync_cycle
        add_sync_cycle(self, initial_paths=folders, initial_numeric_only=initial_numeric_only)

    def _add_sync_folder(self, folders_frame: Any, folder_vars: list, add_folder_btn: Any, initial_path: str = "") -> None:
        from .pages.add_sync_folder import add_sync_folder
        add_sync_folder(self, folders_frame, folder_vars, add_folder_btn, initial_path)

    def _remove_sync_cycle(self, card: Any, folder_vars: list) -> None:
        from .pages.remove_sync_cycle import remove_sync_cycle
        remove_sync_cycle(self, card, folder_vars)

    def _refresh_add_cycle_btn(self) -> None:
        from .ui_constants import _MAX_SYNC_CYCLES
        if not hasattr(self, "_sync_add_cycle_btn") or self._sync_add_cycle_btn is None:
            return
        count = len(getattr(self, "_sync_cycle_vars", []))
        state = "normal" if count < _MAX_SYNC_CYCLES else "disabled"
        self._sync_add_cycle_btn.configure(state=state)

    # ─────────────────────────────────────────────────────────────────────────
    # BUFFs
    # ─────────────────────────────────────────────────────────────────────────

    def _open_create_buff_dialog(self, preset=None, server_id: str = "", event=None) -> None:
        from .dialogs.create_buff_dialog import open_create_buff_dialog
        open_create_buff_dialog(self, preset=preset, server_id=server_id, event=event)

    def _on_buff_created(self, buff_event) -> None:
        if self._buff_manager:
            self._buff_manager.add_event(buff_event)
        self._refresh_buffs_ui()

    def _open_presets_manager(self) -> None:
        messagebox.showinfo("Presets", "Gerenciador de presets em breve.", parent=self)

    def _refresh_buffs_ui(self) -> None:
        from .pages.refresh_buffs_ui import refresh_buffs_ui
        refresh_buffs_ui(self)

    def _cancel_buff(self, event_id: str) -> None:
        from .pages.cancel_buff import cancel_buff
        cancel_buff(self, event_id)

    def _init_buff_manager(self) -> None:
        from .pages.init_buff_manager import init_buff_manager
        init_buff_manager(self)

    def _on_auto_updater_log(self, msg: str, level: str = "info") -> None:
        self._global_log(msg, level)
        box = getattr(self, "_auto_updater_log_box", None)
        if box is None:
            return
        try:
            box.configure(state="normal")
            box.insert("end", msg + "\n", level if level in ("info", "warning", "error", "debug") else "info")
            box.see("end")
            box.configure(state="disabled")
        except Exception:
            pass

    def _start_mod_auto_updater(self) -> None:
        from .pages.start_mod_auto_updater import start_mod_auto_updater
        start_mod_auto_updater(self)

    def _toggle_mod_auto_updater(self, server_id: str = "") -> None:
        from .pages.toggle_mod_auto_updater import toggle_mod_auto_updater
        toggle_mod_auto_updater(self, server_id)

    def _build_active_buff_card(self, parent, row: int, event, *, activating: bool = False) -> None:
        from .pages.build_active_buff_card import build_active_buff_card
        build_active_buff_card(self, parent, row, event, activating=activating)

    def _build_scheduled_buff_row(self, parent, row: int, event) -> None:
        from .pages.build_scheduled_buff_row import build_scheduled_buff_row
        build_scheduled_buff_row(self, parent, row, event)

    def _build_preset_chip(self, parent, row: int, col: int, preset, server_id: str = "") -> None:
        from .pages.build_preset_chip import build_preset_chip
        build_preset_chip(self, parent, row, col, preset, server_id)

    def _build_history_row(self, parent, row: int, event) -> None:
        from .pages.build_history_row import build_history_row
        build_history_row(self, parent, row, event)

    def _buff_countdown_tick(self) -> None:
        from .pages.buff_countdown_tick import buff_countdown_tick
        buff_countdown_tick(self)

    def _confirm_remove_primitive_server(self, server_id: str) -> None:
        from .pages.confirm_remove_primitive_server import confirm_remove_primitive_server
        confirm_remove_primitive_server(self, server_id)

    def _global_log(self, msg: str, level: str = "info") -> None:
        import logging
        _logger = logging.getLogger(__name__)
        getattr(_logger, level if level in ("debug","info","warning","error") else "info", _logger.info)(msg)

    def _refresh_remote_instances_list(self) -> None:
        from .pages.refresh_remote_instances_list import refresh_remote_instances_list
        refresh_remote_instances_list(self)

    def _open_remote_control(self, instance: dict) -> None:
        from .dialogs.remote_control_dialog import open_remote_control
        open_remote_control(self, instance)

    # ─────────────────────────────────────────────────────────────────────────
    # Desempenho
    # ─────────────────────────────────────────────────────────────────────────

    def _collect_gpu_info(self) -> None:
        from .pages.collect_gpu_info import collect_gpu_info
        collect_gpu_info(self)

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

    def _start_perf_monitor(self) -> None:
        import threading
        if self._perf_running:
            return
        self._perf_running = True
        t = threading.Thread(
            target=self._perf_monitor_loop, daemon=True, name="PerfMonitor")
        t.start()

    def _perf_monitor_loop(self) -> None:
        from .pages.perf_monitor_loop import perf_monitor_loop
        perf_monitor_loop(self)

    # ─────────────────────────────────────────────────────────────────────────
    # Clusters
    # ─────────────────────────────────────────────────────────────────────────

    def _cluster_new(self) -> None:
        from .pages.cluster_new import cluster_new
        cluster_new(self)

    def _clusters_refresh_list(self) -> None:
        from .pages.clusters_refresh_list import clusters_refresh_list
        clusters_refresh_list(self)

    def _cluster_save(self) -> None:
        from .pages.cluster_save import cluster_save
        cluster_save(self)

    def _cluster_delete(self, cluster_id: str) -> None:
        from .pages.cluster_delete import cluster_delete
        cluster_delete(self, cluster_id)

    def _cluster_detail(self, cluster_id: str) -> None:
        from .pages.cluster_detail import cluster_detail
        cluster_detail(self, cluster_id)

    def _cluster_import_from_manual(self) -> None:
        from .pages.cluster_import_from_manual import cluster_import_from_manual
        cluster_import_from_manual(self)

    def _cluster_sync_start(self, cluster_id: str) -> None:
        from .pages.cluster_sync_start import cluster_sync_start
        cluster_sync_start(self, cluster_id)

    def _cluster_sync_once(self, cluster_id: str) -> None:
        from .pages.cluster_sync_once import cluster_sync_once
        cluster_sync_once(self, cluster_id)

    def _get_cluster_health(self, profile_id: str) -> dict:
        from .pages.get_cluster_health import get_cluster_health
        return get_cluster_health(self, profile_id)

    def _show_cluster_health_dialog(self, profile_id: str) -> None:
        from .pages.show_cluster_health_dialog import show_cluster_health_dialog
        show_cluster_health_dialog(self, profile_id)

    # ─────────────────────────────────────────────────────────────────────────
    # Remoto
    # ─────────────────────────────────────────────────────────────────────────

    def _start_remote_agent(self) -> None:
        from .pages.start_remote_agent import start_remote_agent
        start_remote_agent(self)

    def _stop_remote_agent(self) -> None:
        if self._remote_agent and self._remote_agent.is_running:
            self._remote_agent.stop()
            self._remote_agent = None
        if getattr(self, "_udp_discovery", None):
            self._udp_discovery.stop()
            self._udp_discovery = None

    def _refresh_identity_code(self) -> None:
        from .pages.refresh_identity_code import refresh_identity_code
        refresh_identity_code(self)

    def _show_pair_request(self, req_id: str, name: str, host: str) -> None:
        from .pages.show_pair_request import show_pair_request_dialog
        show_pair_request_dialog(self, req_id, name, host)

    def _fetch_steam_name(self, steam_id: str, lbl: Any) -> None:
        from .pages.fetch_steam_name import fetch_steam_name
        fetch_steam_name(steam_id, lambda name: lbl.configure(text=name or steam_id))

    def _on_bm_update(self, server_id: str) -> None:
        pass  # BattleMetrics não usado em TEK mode

    def _on_server_log(self, server_id: str, msg: str, level: str = "info") -> None:
        pass  # logs de servidor não exibidos na UI TEK por padrão

    def _on_server_visibility_change(self, server_id: str, mode: str) -> None:
        pass

    def _toast(self, msg: str, kind: str = "info") -> None:
        from .pages.toast import toast
        toast(self, msg, kind)

    def _write_allowed_admins(self, server_id: str) -> None:
        from .pages.write_allowed_admins import write_allowed_admins
        write_allowed_admins(self, server_id)


# Alias para TYPE_CHECKING e módulos importados da Fix
ARKTEKApp = ARKServerManagerApp
