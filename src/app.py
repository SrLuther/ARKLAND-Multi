"""
Interface gráfica principal do ARKLAND-Multi.
Abas: Dashboard | Configurações | Logs
"""
import os
import socket
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any
try:
    import winreg as _winreg  # disponível apenas no Windows
except ImportError:
    _winreg = None  # type: ignore[assignment]

import customtkinter as ctk

from .config_manager import ConfigManager
from .sync_engine import SyncEngine
from .updater import UpdateChecker
from .version import APP_VERSION, BUILD_DATE, CHANGELOG

APP_NAME = "[ARKLAND]-Multi"

# ── Cor padrão de destaque (verde ARK) ────────────────────────────────────────
_GREEN = "#4CAF50"
_GREEN_DARK = "#2d7a3e"
_GREEN_HOVER = "#1f5c2d"
_SIDEBAR_BG = "#161622"
_CARD_BG = "#1e1e30"


def _set_windows_startup(enable: bool) -> None:
    """Registra ou remove o app da inicialização do Windows (HKCU Run)."""
    if _winreg is None:
        return
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    app_key = "ARKLAND-Multi"
    try:
        exe = sys.executable if getattr(sys, "frozen", False) else sys.executable
        if getattr(sys, "frozen", False):
            exe = sys.executable  # PyInstaller: caminho do .exe
        else:
            # Modo dev: chama python main.py
            main_py = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
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


def _hostname() -> str:
    try:
        return socket.gethostname()
    except Exception:
        return "PC"


def _resource_path(relative: str) -> str:
    """Retorna o caminho correto tanto em dev quanto no .exe PyInstaller."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, relative)


# ══════════════════════════════════════════════════════════════════════════════
class ARKLandMultiApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self.title(f"{APP_NAME}  v{APP_VERSION}")
        self.geometry("980x640")
        self.minsize(840, 560)

        # Ícone da janela e barra de tarefas
        try:
            _ico_path = _resource_path(os.path.join("ig", "ArkLandBR.ico"))
            self.iconbitmap(_ico_path)
        except Exception:
            try:
                from PIL import Image, ImageTk
                _png_path = _resource_path(os.path.join("ig", "ArkLandBR.png"))
                _pil_img = Image.open(_png_path).resize((32, 32), Image.LANCZOS)
                self._app_icon = ImageTk.PhotoImage(_pil_img)
                self.iconphoto(True, self._app_icon)
            except Exception:
                pass

        # ── Configuração e motor de sync ──────────────────────────────────────
        self.config_manager = ConfigManager()
        cfg = self.config_manager.config
        if not cfg.machine_name:
            cfg.machine_name = _hostname()

        self.sync_engine = SyncEngine(
            config=cfg,
            on_log=self._append_log,
            on_status_change=self._on_status_change,
            on_stats_update=self._on_stats_update,
        )
        self.update_checker = UpdateChecker(on_log=self._append_log)

        self._build_ui()

        if cfg.auto_start:
            self.after(1500, self.sync_engine.start)

        self.after(4000, self._check_updates_on_start)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Construção da UI ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_frames()
        self._show_frame("dashboard")

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> None:
        sb = ctk.CTkFrame(self, width=195, corner_radius=0, fg_color=_SIDEBAR_BG)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_rowconfigure(10, weight=1)
        sb.grid_propagate(False)
        self._sidebar = sb

        # Logo (imagem)
        try:
            from PIL import Image
            _logo_path = _resource_path(os.path.join("ig", "ArkLandBR.png"))
            _pil_logo = Image.open(_logo_path)
            self._logo_img = ctk.CTkImage(
                light_image=_pil_logo,
                dark_image=_pil_logo,
                size=(130, 130),
            )
            ctk.CTkLabel(sb, image=self._logo_img, text="").grid(
                row=0, column=0, padx=20, pady=(18, 0)
            )
        except Exception:
            ctk.CTkLabel(
                sb, text="⚡ ARKLAND",
                font=ctk.CTkFont(size=20, weight="bold"),
                text_color=_GREEN,
            ).grid(row=0, column=0, padx=20, pady=(24, 0))

        ctk.CTkLabel(
            sb, text="Multi Sync",
            font=ctk.CTkFont(size=13),
            text_color="#88d4a0",
        ).grid(row=1, column=0)

        ctk.CTkLabel(
            sb, text=f"v{APP_VERSION}",
            font=ctk.CTkFont(size=10),
            text_color="gray50",
        ).grid(row=2, column=0, pady=(0, 10))

        ctk.CTkFrame(sb, height=1, fg_color="#2a2a44").grid(
            row=3, column=0, sticky="ew", padx=14, pady=6
        )

        # Botões de navegação
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        nav = [
            ("🏠  Dashboard", "dashboard"),
            ("⚙️  Configurações", "config"),
            ("📋  Logs", "logs"),
            ("ℹ️  Sobre", "sobre"),
        ]
        for i, (label, key) in enumerate(nav):
            btn = ctk.CTkButton(
                sb, text=label, anchor="w", width=165, height=40,
                fg_color="transparent",
                text_color="#d8d8e8",
                hover_color="#252540",
                corner_radius=8,
                command=lambda k=key: self._show_frame(k),
            )
            btn.grid(row=i + 4, column=0, padx=14, pady=3, sticky="ew")
            self._nav_buttons[key] = btn

        ctk.CTkFrame(sb, height=1, fg_color="#2a2a44").grid(
            row=8, column=0, sticky="ew", padx=14, pady=8
        )

        self._update_notif_label = ctk.CTkLabel(
            sb, text="",
            font=ctk.CTkFont(size=11),
            text_color="#ffaa44",
            wraplength=160,
        )
        self._update_notif_label.grid(row=9, column=0, padx=10, pady=(2, 0))
        self._update_notif_label.bind(
            "<Button-1>", lambda e: self._show_frame("sobre")
        )

        self._status_label = ctk.CTkLabel(
            sb, text="● PARADO",
            text_color="#ff6666",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self._status_label.grid(row=11, column=0, padx=20, pady=14)

    # ── Frames principais ──────────────────────────────────────────────────────

    def _build_frames(self) -> None:
        self._frames: dict[str, Any] = {}

        dash = ctk.CTkFrame(self, corner_radius=0, fg_color=("#111118", "#111118"))
        dash.grid(row=0, column=1, sticky="nsew")
        self._build_dashboard(dash)
        self._frames["dashboard"] = dash

        conf = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color=("#111118", "#111118"))
        conf.grid(row=0, column=1, sticky="nsew")
        self._build_config(conf)
        self._frames["config"] = conf

        logs = ctk.CTkFrame(self, corner_radius=0, fg_color=("#111118", "#111118"))
        logs.grid(row=0, column=1, sticky="nsew")
        self._build_logs(logs)
        self._frames["logs"] = logs

        sobre = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color=("#111118", "#111118"))
        sobre.grid(row=0, column=1, sticky="nsew")
        self._build_sobre(sobre)
        self._frames["sobre"] = sobre

    # ── Dashboard ─────────────────────────────────────────────────────────────

    def _build_dashboard(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure((0, 1), weight=1)
        parent.grid_rowconfigure(3, weight=1)

        # Título
        ctk.CTkLabel(
            parent, text="Dashboard",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, padx=24, pady=(24, 2), sticky="w")
        ctk.CTkLabel(
            parent, text="Monitore e controle a sincronização em tempo real.",
            text_color="gray60",
        ).grid(row=1, column=0, columnspan=2, padx=24, pady=(0, 18), sticky="w")

        # Cards de estatísticas
        stats_row = ctk.CTkFrame(parent, fg_color="transparent")
        stats_row.grid(row=2, column=0, columnspan=2, padx=20, pady=4, sticky="ew")
        stats_row.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self._stat_vars = {
            "status_text": tk.StringVar(value="PARADO"),
            "total": tk.StringVar(value="0"),
            "last_sync": tk.StringVar(value="—"),
            "errors": tk.StringVar(value="0"),
        }
        self._stat_color_labels: dict[str, ctk.CTkLabel] = {}

        cards_def = [
            ("Status", "status_text", "#ff6666", "🔴"),
            ("Arquivos sincronizados", "total", _GREEN, "📁"),
            ("Último sync", "last_sync", "#5b9bd5", "🕐"),
            ("Erros", "errors", "#ff9944", "⚠️"),
        ]
        for col, (title, key, color, icon) in enumerate(cards_def):
            card = ctk.CTkFrame(stats_row, corner_radius=12, fg_color=_CARD_BG)
            card.grid(row=0, column=col, padx=6, pady=4, sticky="ew")
            card.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                card, text=f"{icon}  {title}",
                text_color="gray55", font=ctk.CTkFont(size=11),
            ).grid(row=0, column=0, padx=16, pady=(14, 2), sticky="w")

            lbl = ctk.CTkLabel(
                card, textvariable=self._stat_vars[key],
                font=ctk.CTkFont(size=22, weight="bold"),
                text_color=color,
            )
            lbl.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="w")
            self._stat_color_labels[key] = lbl

        # Área de controle
        ctrl = ctk.CTkFrame(parent, corner_radius=14, fg_color=_CARD_BG)
        ctrl.grid(row=3, column=0, columnspan=2, padx=20, pady=10, sticky="nsew")
        ctrl.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            ctrl, text="Controle",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(18, 10), sticky="w")

        btn_row = ctk.CTkFrame(ctrl, fg_color="transparent")
        btn_row.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")

        self._start_btn = ctk.CTkButton(
            btn_row,
            text="▶  Iniciar Sincronização",
            width=210, height=44,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._toggle_sync,
        )
        self._start_btn.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row,
            text="🔄  Forçar Sync Agora",
            width=190, height=44,
            fg_color="#1a3a6a", hover_color="#102650",
            font=ctk.CTkFont(size=13),
            command=self._force_sync,
        ).pack(side="left")

        # Info da máquina
        cfg = self.config_manager.config
        self._machine_info_label = ctk.CTkLabel(
            ctrl,
            text=self._machine_info_text(cfg),
            text_color="gray50",
            font=ctk.CTkFont(size=12),
        )
        self._machine_info_label.grid(row=2, column=0, padx=20, pady=(4, 18), sticky="w")

    def _machine_info_text(self, cfg) -> str:
        name = cfg.machine_name or _hostname()
        return f"🖥️  Máquina: {name}   ⏱  Intervalo: {cfg.sync_interval}s"

    # ── Configurações ─────────────────────────────────────────────────────────

    def _build_config(self, parent) -> None:
        parent.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            parent, text="Configurações",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, padx=24, pady=(24, 2), sticky="w")
        ctk.CTkLabel(
            parent, text="Configure os caminhos e parâmetros de sincronização.",
            text_color="gray60",
        ).grid(row=1, column=0, padx=24, pady=(0, 18), sticky="w")

        cfg = self.config_manager.config

        # ── Identificação ─────────────────────
        self._section(parent, 2, "🖥️  Identificação da Máquina")

        id_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        id_card.grid(row=3, column=0, padx=20, pady=(0, 14), sticky="ew")
        id_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(id_card, text="Nome da Máquina:", width=185, anchor="w").grid(
            row=0, column=0, padx=18, pady=16
        )
        self._machine_name_var = tk.StringVar(value=cfg.machine_name)
        ctk.CTkEntry(
            id_card, textvariable=self._machine_name_var, height=36,
            placeholder_text="Ex: Servidor-A",
        ).grid(row=0, column=1, padx=(0, 18), pady=16, sticky="ew")

        # ── Caminhos ──────────────────────────
        self._section(parent, 4, "📂  Caminhos de Pasta")

        paths_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        paths_card.grid(row=5, column=0, padx=20, pady=(0, 14), sticky="ew")
        paths_card.grid_columnconfigure(1, weight=1)

        # Pasta local ARK Cluster
        ctk.CTkLabel(
            paths_card, text="Pasta ARK Cluster\n(esta máquina):",
            width=185, anchor="w", justify="left",
        ).grid(row=0, column=0, padx=18, pady=(18, 10), sticky="nw")
        self._local_path_var = tk.StringVar(value=cfg.local_cluster_path)
        ctk.CTkEntry(
            paths_card, textvariable=self._local_path_var, height=36,
            placeholder_text=r"Ex: C:\ARK\ShooterGame\Saved\clusters",
        ).grid(row=0, column=1, padx=(0, 6), pady=(18, 10), sticky="ew")
        ctk.CTkButton(
            paths_card, text="📁", width=38, height=36,
            command=lambda: self._browse(self._local_path_var),
        ).grid(row=0, column=2, padx=(0, 18), pady=(18, 10))

        ctk.CTkFrame(paths_card, height=1, fg_color="#2a2a44").grid(
            row=1, column=0, columnspan=3, sticky="ew", padx=18
        )

        # Pasta compartilhada
        ctk.CTkLabel(
            paths_card, text="Pasta Compartilhada\n(rede/ambas máquinas):",
            width=185, anchor="w", justify="left",
        ).grid(row=2, column=0, padx=18, pady=(10, 18), sticky="nw")
        self._shared_path_var = tk.StringVar(value=cfg.shared_path)
        ctk.CTkEntry(
            paths_card, textvariable=self._shared_path_var, height=36,
            placeholder_text=r"Ex: \\SERVIDOR\ARK-Sync",
        ).grid(row=2, column=1, padx=(0, 6), pady=(10, 18), sticky="ew")
        ctk.CTkButton(
            paths_card, text="📁", width=38, height=36,
            command=lambda: self._browse(self._shared_path_var),
        ).grid(row=2, column=2, padx=(0, 18), pady=(10, 18))

        # ── Parâmetros ────────────────────────
        self._section(parent, 6, "⏱  Intervalo de Sincronização")

        interval_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        interval_card.grid(row=7, column=0, padx=20, pady=(0, 14), sticky="ew")
        interval_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(interval_card, text="Intervalo (segundos):", width=185, anchor="w").grid(
            row=0, column=0, padx=18, pady=18
        )
        self._interval_var = tk.IntVar(value=cfg.sync_interval)
        slider_frame = ctk.CTkFrame(interval_card, fg_color="transparent")
        slider_frame.grid(row=0, column=1, padx=(0, 18), pady=18, sticky="w")

        self._interval_display = ctk.CTkLabel(
            slider_frame, text=f"{cfg.sync_interval}s", width=42,
            font=ctk.CTkFont(size=15, weight="bold"), text_color=_GREEN,
        )
        self._interval_display.pack(side="left", padx=(0, 10))

        ctk.CTkSlider(
            slider_frame, from_=1, to=60, variable=self._interval_var, width=220,
            command=lambda v: self._interval_display.configure(text=f"{int(v)}s"),
        ).pack(side="left")
        ctk.CTkLabel(slider_frame, text="60s", text_color="gray50").pack(side="left", padx=6)

        # ── Opções ────────────────────────────
        self._section(parent, 8, "🔧  Opções")

        opt_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        opt_card.grid(row=9, column=0, padx=20, pady=(0, 14), sticky="ew")

        self._auto_start_var = tk.BooleanVar(value=cfg.auto_start)
        ctk.CTkCheckBox(
            opt_card,
            text="Iniciar sincronização automaticamente ao abrir o programa",
            variable=self._auto_start_var,
            checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        ).grid(row=0, column=0, padx=18, pady=(16, 8), sticky="w")

        self._log_debug_var = tk.BooleanVar(value=cfg.log_debug)
        ctk.CTkCheckBox(
            opt_card,
            text="Mostrar ciclos sem alterações nos logs (modo debug)",
            variable=self._log_debug_var,
            checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        ).grid(row=1, column=0, padx=18, pady=(0, 8), sticky="w")

        self._startup_windows_var = tk.BooleanVar(value=cfg.startup_with_windows)
        ctk.CTkCheckBox(
            opt_card,
            text="Iniciar o ARKLAND-Multi automaticamente com o Windows",
            variable=self._startup_windows_var,
            checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        ).grid(row=2, column=0, padx=18, pady=(0, 16), sticky="w")

        # Botão salvar
        ctk.CTkButton(
            parent,
            text="💾  Salvar Configurações",
            height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            command=self._save_config,
        ).grid(row=10, column=0, padx=20, pady=(0, 24), sticky="ew")

    def _section(self, parent, row: int, text: str) -> None:
        ctk.CTkLabel(
            parent, text=text,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#88d4a0",
        ).grid(row=row, column=0, padx=22, pady=(6, 4), sticky="w")

    # ── Logs ──────────────────────────────────────────────────────────────────

    def _build_logs(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=(20, 8), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Logs de Sincronização",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            header, text="🗑  Limpar", width=110, height=32,
            fg_color="#3a3a5a", hover_color="#252540",
            command=self._clear_logs,
        ).grid(row=0, column=1, sticky="e")

        self._log_text = ctk.CTkTextbox(
            parent,
            font=ctk.CTkFont(family="Courier New", size=12),
            wrap="word",
            state="disabled",
        )
        self._log_text.grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nsew")

        # Cores por nível (acesso à widget tk interna)
        tw = self._log_text._textbox
        tw.tag_config("info",    foreground="#d0d0e0")
        tw.tag_config("success", foreground="#66cc77")
        tw.tag_config("warning", foreground="#ffaa44")
        tw.tag_config("error",   foreground="#ff6666")
        tw.tag_config("debug",   foreground="#666680")

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _toggle_sync(self) -> None:
        if self.sync_engine.is_running:
            self.sync_engine.stop()
        else:
            self.sync_engine.start()

    def _force_sync(self) -> None:
        self._append_log("[manual] Sincronização forçada pelo usuário.", "info")
        self.sync_engine.sync_once()

    def _save_config(self) -> None:
        cfg = self.config_manager.config
        cfg.local_cluster_path = self._local_path_var.get().strip()
        cfg.shared_path        = self._shared_path_var.get().strip()
        cfg.sync_interval      = max(1, int(self._interval_var.get()))
        cfg.machine_name       = self._machine_name_var.get().strip()
        cfg.auto_start              = self._auto_start_var.get()
        cfg.log_debug               = self._log_debug_var.get()
        cfg.startup_with_windows    = self._startup_windows_var.get()
        _set_windows_startup(cfg.startup_with_windows)

        self.config_manager.save()
        self._machine_info_label.configure(text=self._machine_info_text(cfg))
        self._append_log("Configurações salvas com sucesso.", "info")
        messagebox.showinfo("Salvo", "Configurações salvas com sucesso!", parent=self)

    def _browse(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory(parent=self, title="Selecionar pasta")
        if path:
            var.set(path)

    def _clear_logs(self) -> None:
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    # ── Callbacks do motor ────────────────────────────────────────────────────

    def _append_log(self, message: str, level: str = "info") -> None:
        def _do() -> None:
            self._log_text.configure(state="normal")
            self._log_text._textbox.insert("end", message + "\n", level)
            self._log_text._textbox.see("end")
            self._log_text.configure(state="disabled")
        self.after(0, _do)

    def _on_status_change(self, status: str) -> None:
        def _do() -> None:
            if status == "running":
                self._status_label.configure(text="● RODANDO", text_color=_GREEN)
                self._start_btn.configure(
                    text="⏹  Parar Sincronização",
                    fg_color="#7a2d2d", hover_color="#5c1f1f",
                )
                self._stat_vars["status_text"].set("RODANDO")
                self._stat_color_labels["status_text"].configure(text_color=_GREEN)
            else:
                self._status_label.configure(text="● PARADO", text_color="#ff6666")
                self._start_btn.configure(
                    text="▶  Iniciar Sincronização",
                    fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                )
                self._stat_vars["status_text"].set("PARADO")
                self._stat_color_labels["status_text"].configure(text_color="#ff6666")
        self.after(0, _do)

    def _on_stats_update(self, stats: dict) -> None:
        def _do() -> None:
            self._stat_vars["total"].set(str(stats.get("total_synced", 0)))
            self._stat_vars["last_sync"].set(stats.get("last_sync", "—"))
            self._stat_vars["errors"].set(str(stats.get("errors", 0)))
        self.after(0, _do)

    # ── Sobre & Atualizações ──────────────────────────────────────────────────

    def _build_sobre(self, parent) -> None:
        parent.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            parent, text="Sobre & Atualizações",
            font=ctk.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, padx=24, pady=(24, 2), sticky="w")
        ctk.CTkLabel(
            parent,
            text="Informações do aplicativo e gerenciamento de atualizações.",
            text_color="gray60",
        ).grid(row=1, column=0, padx=24, pady=(0, 18), sticky="w")

        # ── Informações do app ────────────────────────────────────────────────
        self._section(parent, 2, "📦  Aplicativo")
        info_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        info_card.grid(row=3, column=0, padx=20, pady=(0, 14), sticky="ew")
        info_card.grid_columnconfigure(1, weight=1)

        for r, (lbl, val, bold) in enumerate([
            ("Nome:",         APP_NAME,          False),
            ("Versão atual:", f"v{APP_VERSION}", True),
            ("Build:",        BUILD_DATE,        False),
        ]):
            ctk.CTkLabel(
                info_card, text=lbl, width=140, anchor="w", text_color="gray60",
            ).grid(row=r, column=0, padx=18, pady=8, sticky="w")
            ctk.CTkLabel(
                info_card, text=val, anchor="w",
                font=ctk.CTkFont(weight="bold" if bold else "normal"),
                text_color=_GREEN if bold else "#d8d8e8",
            ).grid(row=r, column=1, padx=(0, 18), pady=8, sticky="w")

        # ── Status de atualização ─────────────────────────────────────────────
        self._section(parent, 4, "🔄  Atualização")
        upd_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        upd_card.grid(row=5, column=0, padx=20, pady=(0, 14), sticky="ew")
        upd_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            upd_card, text="Status:", width=140, anchor="w", text_color="gray60",
        ).grid(row=0, column=0, padx=18, pady=(18, 6), sticky="w")
        self._update_status_var = tk.StringVar(value="Não verificado")
        self._update_status_lbl = ctk.CTkLabel(
            upd_card,
            textvariable=self._update_status_var,
            font=ctk.CTkFont(weight="bold"),
            text_color="gray50",
            anchor="w",
        )
        self._update_status_lbl.grid(row=0, column=1, padx=(0, 18), pady=(18, 6), sticky="w")

        ctk.CTkLabel(
            upd_card, text="Última verificação:", width=140, anchor="w", text_color="gray60",
        ).grid(row=1, column=0, padx=18, pady=(0, 10), sticky="w")
        self._last_check_var = tk.StringVar(value="Nunca")
        ctk.CTkLabel(
            upd_card, textvariable=self._last_check_var,
            text_color="#d8d8e8", anchor="w",
        ).grid(row=1, column=1, padx=(0, 18), pady=(0, 10), sticky="w")

        btn_row2 = ctk.CTkFrame(upd_card, fg_color="transparent")
        btn_row2.grid(row=2, column=0, columnspan=2, padx=18, pady=(4, 14), sticky="w")

        self._check_update_btn = ctk.CTkButton(
            btn_row2,
            text="🔍  Verificar Atualizações",
            width=210, height=40,
            fg_color="#1a3a6a", hover_color="#102650",
            command=self._check_updates_manual,
        )
        self._check_update_btn.pack(side="left", padx=(0, 10))

        self._install_update_btn = ctk.CTkButton(
            btn_row2,
            text="⬇️  Baixar e Instalar",
            width=190, height=40,
            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            state="disabled",
            command=self._start_download_update,
        )
        self._install_update_btn.pack(side="left")

        # Barra de progresso e label (adicionadas ao grid dinamicamente)
        self._update_progress = ctk.CTkProgressBar(
            upd_card, width=420, height=14, corner_radius=6,
        )
        self._update_progress.set(0)
        self._update_progress_label = ctk.CTkLabel(
            upd_card, text="", text_color="gray60",
            font=ctk.CTkFont(size=11),
        )

        # ── Histórico de versões ──────────────────────────────────────────────
        self._section(parent, 6, "📝  Histórico de Versões")
        cl_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        cl_card.grid(row=7, column=0, padx=20, pady=(0, 24), sticky="ew")
        cl_card.grid_columnconfigure(0, weight=1)

        cl_text = ctk.CTkTextbox(
            cl_card,
            font=ctk.CTkFont(family="Courier New", size=12),
            wrap="word",
            state="normal",
            height=200,
            fg_color="#161622",
        )
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

    def _check_updates_on_start(self) -> None:
        url = self.config_manager.config.update_url
        if not url:
            return
        self.update_checker.check_async(
            url,
            on_result=lambda info: (self.after(0, lambda: self._on_update_result(info)), None)[1],
        )

    def _check_updates_manual(self) -> None:
        url = self.config_manager.config.update_url
        if not url:
            self._update_status_var.set("⚠️  URL não configurada em Configurações")
            self._update_status_lbl.configure(text_color="#ffaa44")
            return
        self._check_update_btn.configure(state="disabled", text="🔍  Verificando...")
        self._update_status_var.set("Verificando...")
        self._update_status_lbl.configure(text_color="gray60")
        self.update_checker.check_async(
            url,
            on_result=lambda info: (self.after(
                0, lambda: self._on_update_result(info, manual=True)
            ), None)[1],
        )

    def _on_update_result(self, info, manual: bool = False) -> None:
        from datetime import datetime
        self._last_check_var.set(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        self._check_update_btn.configure(state="normal", text="🔍  Verificar Atualizações")

        if info is None:
            if manual:
                self._update_status_var.set("❌  Não foi possível verificar atualizações")
                self._update_status_lbl.configure(text_color="#ff6666")
            return

        if info.is_newer_than(APP_VERSION):
            self._update_status_var.set(f"🔔  v{info.version} disponível!")
            self._update_status_lbl.configure(text_color="#ffaa44")
            self._install_update_btn.configure(
                state="normal", text=f"⬇️  Instalar v{info.version}",
            )
            self._update_notif_label.configure(text=f"🔔 v{info.version} disponível")
            if "sobre" in self._nav_buttons:
                self._nav_buttons["sobre"].configure(text="ℹ️  Sobre  🔔")
        else:
            self._update_status_var.set("✅  Você está na versão mais recente")
            self._update_status_lbl.configure(text_color=_GREEN)
            self._install_update_btn.configure(
                state="disabled", text="⬇️  Baixar e Instalar",
            )
            self._update_notif_label.configure(text="")

    def _start_download_update(self) -> None:
        info = self.update_checker.latest
        if not info:
            return
        self._install_update_btn.configure(state="disabled", text="⬇️  Baixando...")
        self._check_update_btn.configure(state="disabled")
        self._update_progress.set(0)
        self._update_progress.grid(
            row=3, column=0, columnspan=2, padx=18, pady=(0, 8), sticky="w"
        )
        self._update_progress_label.configure(text="Iniciando download...")
        self._update_progress_label.grid(
            row=4, column=0, columnspan=2, padx=18, pady=(0, 14), sticky="w"
        )
        self.update_checker.download_and_install(
            info,
            on_progress=lambda p: (self.after(0, lambda: self._on_download_progress(p)), None)[1],
            on_done=lambda ok, msg: (self.after(0, lambda: self._on_download_done(ok, msg)), None)[1],
        )

    def _on_download_progress(self, percent: int) -> None:
        self._update_progress.set(percent / 100)
        self._update_progress_label.configure(text=f"Baixando... {percent}%")

    def _on_download_done(self, success: bool, message: str) -> None:
        self._check_update_btn.configure(state="normal")
        if success:
            self._update_progress.set(1.0)
            self._update_progress_label.configure(
                text="✅  Download concluído. O instalador foi iniciado."
            )
            messagebox.showinfo(
                "Atualização",
                "O instalador foi iniciado.\n"
                "O aplicativo será fechado para concluir a atualização.",
                parent=self,
            )
            self._on_close()
        else:
            self._update_progress.grid_remove()
            self._update_progress_label.configure(text=f"❌  Erro: {message}")
            self._install_update_btn.configure(
                state="normal", text="⬇️  Tentar Novamente",
            )

    # ── Navegação ─────────────────────────────────────────────────────────────

    def _show_frame(self, name: str) -> None:
        for key, frame in self._frames.items():
            if key == name:
                frame.grid()
            else:
                frame.grid_remove()
            btn = self._nav_buttons.get(key)
            if btn:
                btn.configure(fg_color="#1e2a3a" if key == name else "transparent")

    # ── Encerramento ──────────────────────────────────────────────────────────

    def _on_close(self) -> None:
        self.sync_engine.stop()
        self.config_manager.save()
        self.destroy()
