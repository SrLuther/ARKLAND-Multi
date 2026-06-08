"""
TEK — Diálogo "Novo Servidor ASM".
Modos: Novo servidor | Importar servidor existente | Importar .arkprofile
"""
from __future__ import annotations

import configparser
import re
import tkinter as tk
from pathlib import Path
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


# ── Helper: importar a partir de instalação existente ─────────────────────────

def _import_from_install_dir(install_dir: str) -> AsmServerConfig:
    """
    Lê GameUserSettings.ini e Game.ini de uma instalação existente e
    preenche os campos correspondentes de AsmServerConfig.
    """
    cfg = AsmServerConfig()
    cfg.install_dir = install_dir

    gus = Path(install_dir) / "ShooterGame" / "Saved" / "Config" / "WindowsServer" / "GameUserSettings.ini"
    gme = Path(install_dir) / "ShooterGame" / "Saved" / "Config" / "WindowsServer" / "Game.ini"

    # Tenta também localizar RunServer.bat / ShooterGameServer.exe para inferir porta/mapa
    _read_gus(gus, cfg)
    _read_game(gme, cfg)
    _read_cmdline(install_dir, cfg)
    return cfg


def _parse_ini(path: Path) -> configparser.RawConfigParser:
    parser = configparser.RawConfigParser()
    parser.optionxform = str  # preserva case
    if path.exists():
        try:
            parser.read(path, encoding="utf-8")
        except Exception:
            try:
                parser.read(path, encoding="latin-1")
            except Exception:
                pass
    return parser


def _read_gus(gus: Path, cfg: AsmServerConfig):
    p = _parse_ini(gus)

    def _get(section, key, default=None):
        try:
            return p.get(section, key)
        except Exception:
            return default

    cfg.session_name    = _get("/Script/Engine.GameSession", "MaxPlayers") and cfg.session_name
    cfg.session_name    = _get("ServerSettings", "SessionName") or cfg.session_name
    cfg.admin_password  = _get("ServerSettings", "ServerAdminPassword") or ""
    cfg.server_password = _get("ServerSettings", "ServerPassword") or ""
    cfg.spectator_password = _get("ServerSettings", "SpectatorPassword") or ""
    cfg.max_players     = int(_get("ServerSettings", "MaxPlayers") or 70)
    cfg.rcon_enabled    = (_get("ServerSettings", "RCONEnabled") or "False").lower() == "true"
    cfg.rcon_port       = int(_get("ServerSettings", "RCONPort") or 27020)

    # Multiplicadores básicos
    try:
        cfg.xp_multiplier            = float(_get("ServerSettings", "XPMultiplier") or 1.0)
        cfg.harvest_amount_multiplier= float(_get("ServerSettings", "HarvestAmountMultiplier") or 1.0)
        cfg.taming_speed_multiplier  = float(_get("ServerSettings", "TamingSpeedMultiplier") or 1.0)
        cfg.mating_interval_multiplier = float(_get("ServerSettings", "MatingIntervalMultiplier") or 1.0)
        cfg.egg_hatch_speed_multiplier = float(_get("ServerSettings", "EggHatchSpeedMultiplier") or 1.0)
        cfg.baby_mature_speed_multiplier = float(_get("ServerSettings", "BabyMatureSpeedMultiplier") or 1.0)
        cfg.player_damage_multiplier  = float(_get("ServerSettings", "PlayerDamageMultiplier") or 1.0)
        cfg.dino_damage_multiplier    = float(_get("ServerSettings", "DinoMultiplier") or
                                              _get("ServerSettings", "DinoMult") or 1.0)
    except (TypeError, ValueError):
        pass


def _read_game(gme: Path, cfg: AsmServerConfig):
    p = _parse_ini(gme)

    def _getm(section, key, default=None):
        try:
            return p.get(section, key)
        except Exception:
            return default

    try:
        cfg.player_resistance_multiplier = float(
            _getm("/script/shootergame.shootergamemode", "PlayerResistanceMultiplier") or 1.0)
    except (TypeError, ValueError):
        pass


def _read_cmdline(install_dir: str, cfg: AsmServerConfig):
    """Tenta ler RunServer.bat para inferir mapa e portas."""
    base = Path(install_dir)
    for fname in ("RunServer.bat", "run_server.bat", "start.bat", "ShooterGame.bat"):
        bat = base / fname
        if bat.exists():
            try:
                txt = bat.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            # Porta: ?Port=XXXX
            m = re.search(r"\?Port=(\d+)", txt, re.IGNORECASE)
            if m:
                cfg.server_port = int(m.group(1))
            # QueryPort: ?QueryPort=XXXX
            m = re.search(r"\?QueryPort=(\d+)", txt, re.IGNORECASE)
            if m:
                cfg.query_port = int(m.group(1))
            # Mapa: primeiro argumento antes de ?
            m = re.search(r"ShooterGameServer\.exe\s+([A-Za-z0-9_/]+)\?", txt, re.IGNORECASE)
            if m:
                cfg.server_map = m.group(1)
            break


# ── Diálogo principal ────────────────────────────────────────────────────────

def asm_add_server_dialog(app: "ARKServerManagerApp") -> None:
    theme   = get_theme("tek")
    accent  = theme["accent"]
    bg      = theme["bg"]
    card_bg = theme["card_bg"]
    sep     = theme["separator"]
    t_sec   = theme["text_secondary"]
    acc_mb  = theme["accent_muted_bg"]
    acc_dk  = theme["accent_dark"]

    dlg = ctk.CTkToplevel(app)
    dlg.title("TEK — Adicionar Servidor")
    dlg.geometry("520x400")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.configure(fg_color=bg)
    dlg.after(100, dlg.lift)
    dlg.after(150, dlg.focus_force)

    ctk.CTkLabel(dlg, text="Adicionar Servidor TEK",
                 font=ctk.CTkFont(size=16, weight="bold"),
                 text_color=accent).pack(pady=(18, 4))

    # ── Seletor de modo ───────────────────────────────────────────────────────
    mode_var = tk.StringVar(value="new")
    mode_f = ctk.CTkFrame(dlg, fg_color=card_bg, corner_radius=8)
    mode_f.pack(fill="x", padx=24, pady=(4, 8))

    modes = [("new", "Novo Servidor"), ("import_dir", "Importar Instalação"), ("import_profile", "Importar .arkprofile")]
    for m, label in modes:
        ctk.CTkRadioButton(
            mode_f, text=label, variable=mode_var, value=m,
            text_color=t_sec, font=ctk.CTkFont(size=11),
            radiobutton_width=16, radiobutton_height=16,
            border_color=accent, fg_color=accent,
        ).pack(side="left", padx=12, pady=8)

    # ── Container de formulário (troca conforme modo) ─────────────────────────
    form_container = ctk.CTkFrame(dlg, fg_color="transparent")
    form_container.pack(fill="both", expand=True, padx=24)

    def _clear_form():
        for w in form_container.winfo_children():
            w.destroy()

    def _entry_row(parent, label: str, row: int, placeholder: str = "", width: int = 0) -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label, anchor="w",
                     font=ctk.CTkFont(size=11), text_color=t_sec,
                     ).grid(row=row, column=0, padx=(0, 8), pady=5, sticky="w")
        kw = {"placeholder_text": placeholder}
        if width:
            kw["width"] = width
        e = ctk.CTkEntry(parent, **kw)
        e.grid(row=row, column=1, pady=5, sticky="ew")
        return e

    # ── Formulário: Novo Servidor ─────────────────────────────────────────────
    def _show_new():
        _clear_form()
        f = ctk.CTkFrame(form_container, fg_color=card_bg, corner_radius=10)
        f.pack(fill="x", pady=4)
        f.grid_columnconfigure(1, weight=1)

        e_name    = _entry_row(f, "Nome no gerenciador",  0, "Meu Servidor TEK")
        e_session = _entry_row(f, "Nome da sessão (INI)", 1, "My ARK Server")
        e_dir     = _entry_row(f, "Pasta de instalação",  2, "C:\\ARK\\")
        e_port    = _entry_row(f, "Porta (game)",         3, "7777", 90)
        e_query   = _entry_row(f, "Porta (query)",        4, "27015", 90)

        btn_row = ctk.CTkFrame(form_container, fg_color="transparent")
        btn_row.pack(fill="x", pady=(10, 0))

        def _save():
            cfg = AsmServerConfig()
            cfg.name         = e_name.get().strip()    or "Servidor TEK"
            cfg.session_name = e_session.get().strip() or "My ARK Server"
            cfg.install_dir  = e_dir.get().strip()
            try:
                cfg.server_port = int(e_port.get().strip() or 7777)
                cfg.query_port  = int(e_query.get().strip() or 27015)
            except ValueError:
                pass
            app.asm_config_manager.add_server(cfg)
            dlg.destroy()
            if getattr(app, "_active_mode", None) == "tek":
                app._asm_refresh_dashboard()
            app._rebuild_server_sidebar()
            app._asm_open_server_panel(cfg.id)

        ctk.CTkButton(btn_row, text="Cancelar", width=100, fg_color=card_bg,
                      hover_color="#1a2830", command=dlg.destroy).pack(side="right", padx=(6, 0))
        ctk.CTkButton(btn_row, text="Criar Servidor", width=140,
                      fg_color=acc_mb, hover_color=acc_dk,
                      border_width=1, border_color=accent, text_color=accent,
                      command=_save).pack(side="right")

    # ── Formulário: Importar Instalação ───────────────────────────────────────
    def _show_import_dir():
        _clear_form()
        f = ctk.CTkFrame(form_container, fg_color=card_bg, corner_radius=10)
        f.pack(fill="x", pady=4)
        f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(f, text="Pasta raiz da instalação ARK:", anchor="w",
                     font=ctk.CTkFont(size=11), text_color=t_sec,
                     ).grid(row=0, column=0, padx=(14, 8), pady=(12, 4), sticky="w")

        dir_var = tk.StringVar()
        dir_row = ctk.CTkFrame(f, fg_color="transparent")
        dir_row.grid(row=1, column=0, columnspan=2, padx=14, pady=(0, 4), sticky="ew")
        dir_row.grid_columnconfigure(0, weight=1)

        e_dir = ctk.CTkEntry(dir_row, textvariable=dir_var,
                             placeholder_text="C:\\ARK\\Server1\\")
        e_dir.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        def _browse():
            from tkinter import filedialog
            path = filedialog.askdirectory(title="Selecione a pasta raiz do servidor")
            if path:
                dir_var.set(path)

        ctk.CTkButton(dir_row, text="📁", width=34, height=28,
                      fg_color=sep, hover_color="#263347",
                      command=_browse).grid(row=0, column=1)

        status_lbl = ctk.CTkLabel(f, text="Aguardando seleção...",
                                  font=ctk.CTkFont(size=10), text_color=t_sec,
                                  wraplength=380, justify="left")
        status_lbl.grid(row=2, column=0, columnspan=2, padx=14, pady=(4, 12), sticky="w")

        def _on_dir_change(*_):
            d = dir_var.get().strip()
            if not d:
                status_lbl.configure(text="Aguardando seleção...")
                return
            gus = Path(d) / "ShooterGame" / "Saved" / "Config" / "WindowsServer" / "GameUserSettings.ini"
            if gus.exists():
                status_lbl.configure(text=f"✅ GameUserSettings.ini encontrado: {gus}", text_color="#4ade80")
            else:
                status_lbl.configure(text="⚠ GameUserSettings.ini não encontrado — campos básicos serão vazios.", text_color="#f59e0b")

        dir_var.trace_add("write", _on_dir_change)

        btn_row = ctk.CTkFrame(form_container, fg_color="transparent")
        btn_row.pack(fill="x", pady=(10, 0))

        def _import():
            d = dir_var.get().strip()
            if not d:
                return
            cfg = _import_from_install_dir(d)
            if not cfg.name:
                cfg.name = Path(d).name or "Servidor Importado"
            app.asm_config_manager.add_server(cfg)
            dlg.destroy()
            if getattr(app, "_active_mode", None) == "tek":
                app._asm_refresh_dashboard()
            app._rebuild_server_sidebar()
            app._asm_open_server_panel(cfg.id)

        ctk.CTkButton(btn_row, text="Cancelar", width=100, fg_color=card_bg,
                      hover_color="#1a2830", command=dlg.destroy).pack(side="right", padx=(6, 0))
        ctk.CTkButton(btn_row, text="Importar Servidor", width=150,
                      fg_color=acc_mb, hover_color=acc_dk,
                      border_width=1, border_color=accent, text_color=accent,
                      command=_import).pack(side="right")

    # ── Formulário: Importar .arkprofile ──────────────────────────────────────
    def _show_import_profile():
        _clear_form()
        f = ctk.CTkFrame(form_container, fg_color=card_bg, corner_radius=10)
        f.pack(fill="x", pady=4)
        f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(f, text="Arquivo .arkprofile:", anchor="w",
                     font=ctk.CTkFont(size=11), text_color=t_sec,
                     ).grid(row=0, column=0, padx=(14, 8), pady=(12, 4), sticky="w")

        file_var = tk.StringVar()
        file_row = ctk.CTkFrame(f, fg_color="transparent")
        file_row.grid(row=1, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="ew")
        file_row.grid_columnconfigure(0, weight=1)

        e_file = ctk.CTkEntry(file_row, textvariable=file_var,
                              placeholder_text="Caminho do .arkprofile...")
        e_file.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        def _browse():
            from tkinter import filedialog
            path = filedialog.askopenfilename(
                title="Selecione o perfil .arkprofile",
                filetypes=[("ARK Profile", "*.arkprofile"), ("JSON", "*.json"), ("Todos", "*.*")],
            )
            if path:
                file_var.set(path)

        ctk.CTkButton(file_row, text="📁", width=34, height=28,
                      fg_color=sep, hover_color="#263347",
                      command=_browse).grid(row=0, column=1)

        btn_row = ctk.CTkFrame(form_container, fg_color="transparent")
        btn_row.pack(fill="x", pady=(10, 0))

        def _import():
            path = file_var.get().strip()
            if not path:
                return
            try:
                cfg = app.asm_config_manager.import_server(path)
            except Exception as exc:
                from tkinter import messagebox
                messagebox.showerror("Erro ao importar", str(exc), parent=dlg)
                return
            dlg.destroy()
            if getattr(app, "_active_mode", None) == "tek":
                app._asm_refresh_dashboard()
            app._rebuild_server_sidebar()
            if cfg is not None:
                app._asm_open_server_panel(cfg.id)

        ctk.CTkButton(btn_row, text="Cancelar", width=100, fg_color=card_bg,
                      hover_color="#1a2830", command=dlg.destroy).pack(side="right", padx=(6, 0))
        ctk.CTkButton(btn_row, text="Importar Perfil", width=140,
                      fg_color=acc_mb, hover_color=acc_dk,
                      border_width=1, border_color=accent, text_color=accent,
                      command=_import).pack(side="right")

    # ── Roteamento de modo ────────────────────────────────────────────────────
    def _on_mode_change(*_):
        m = mode_var.get()
        if m == "new":
            _show_new()
        elif m == "import_dir":
            _show_import_dir()
        else:
            _show_import_profile()

    mode_var.trace_add("write", _on_mode_change)
    _show_new()
