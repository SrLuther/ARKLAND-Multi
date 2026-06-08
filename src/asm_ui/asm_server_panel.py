"""
TEK — Painel de configuração de servidor (24 seções, fiel ao ASM).
Estrutura: header + nav lateral + conteúdo dinâmico.
"""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Callable
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


# ── Seções do painel (ordem fiel ao ASM) ─────────────────────────────────────
SECTIONS: list[str] = [
    "Administração",
    "Gerenciamento Automático",
    "Detalhes do Discord Bot",
    "Detalhes do Servidor",
    "Regras",
    "Transferências / Tributo",
    "Bate-papo e Notificações",
    "HUD e Visuais",
    "Configurações do Jogador",
    "Configurações do Dino",
    "Reprodução",
    "Meio Ambiente",
    "Estruturas",
    "Engramas",
    "Arquivos do Servidor",
    "Progressões de Nível",
    "Substituições de Crafting",
    "Substituições de Stack",
    "Substituições de Spawner",
    "Substituições de Supply Crate",
    "Impedir Transferências",
    "Custom GameUserSettings.ini",
    "Custom Game.ini",
    "ARK Procedural (PGM)",
]


def build_asm_server_panel(app: "ARKServerManagerApp",
                           parent: ctk.CTkFrame,
                           srv: AsmServerConfig) -> None:
    """Constrói o painel de configuração TEK dentro de `parent`."""
    theme   = get_theme("tek")
    accent  = theme["accent"]
    bg      = theme["bg"]
    card_bg = theme["card_bg"]
    sep     = theme["separator"]
    nav_bg  = theme["tab_bar_bg"]
    t_pri   = theme["text_primary"]
    t_sec   = theme["text_secondary"]
    t_mut   = theme["text_muted"]
    acc_mb  = theme["accent_muted_bg"]
    acc_dk  = theme["accent_dark"]
    hover   = theme["accent_hover"]

    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=0)
    parent.grid_rowconfigure(1, weight=1)

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = ctk.CTkFrame(parent, fg_color=card_bg, corner_radius=0, height=60)
    hdr.grid(row=0, column=0, sticky="ew")
    hdr.grid_propagate(False)
    hdr.grid_columnconfigure(1, weight=1)

    ctk.CTkButton(
        hdr, text="◀  Dashboard", width=120, height=34,
        fg_color=acc_mb, hover_color=hover,
        text_color=accent, corner_radius=8,
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        border_width=1, border_color=acc_dk,
        command=lambda: app._show_frame("dashboard"),
    ).grid(row=0, column=0, padx=(16, 0), pady=12, sticky="w")

    # Nome do servidor + breadcrumb
    title_f = ctk.CTkFrame(hdr, fg_color="transparent")
    title_f.grid(row=0, column=1, padx=12, pady=10, sticky="w")
    ctk.CTkLabel(
        title_f, text="Configuração  /",
        font=ctk.CTkFont(family="Segoe UI", size=11),
        text_color=t_mut,
    ).pack(side="left")
    ctk.CTkLabel(
        title_f, text=f"  {srv.name}",
        font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        text_color=t_pri,
    ).pack(side="left")

    # ── Botões de gerenciamento do servidor ───────────────────────────────────
    def _get_status() -> str:
        inst = app.asm_server_manager.get_instance(srv.id)
        return inst.status if inst else "stopped"

    def _on_start() -> None:
        _sync_ui_to_cfg(app, srv)   # sincroniza UI → cfg sem salvar nem exibir dialog
        app._asm_start_server(srv)
        _refresh_action_btns()

    def _on_stop() -> None:
        app._asm_stop_server(srv.id)
        _refresh_action_btns()

    def _on_restart() -> None:
        _sync_ui_to_cfg(app, srv)   # sincroniza UI → cfg sem salvar nem exibir dialog
        app._asm_restart_server(srv)
        _refresh_action_btns()

    btn_start   = ctk.CTkButton(
        hdr, text="▶  Iniciar", width=96, height=34,
        fg_color="#052e16", hover_color="#14532d",
        text_color="#4ade80", corner_radius=8,
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        command=_on_start,
    )
    btn_start.grid(row=0, column=2, padx=(0, 4), pady=12, sticky="e")

    btn_stop = ctk.CTkButton(
        hdr, text="⏹  Parar", width=90, height=34,
        fg_color="#7f1d1d", hover_color="#450a0a",
        text_color="#fca5a5", corner_radius=8,
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        command=_on_stop,
    )
    btn_stop.grid(row=0, column=3, padx=(0, 4), pady=12, sticky="e")

    btn_restart = ctk.CTkButton(
        hdr, text="🔄  Restart", width=96, height=34,
        fg_color="#0f172a", hover_color="#1e3a5f",
        text_color=t_sec, border_width=1, border_color=sep,
        corner_radius=8,
        font=ctk.CTkFont(family="Segoe UI", size=11),
        command=_on_restart,
    )
    btn_restart.grid(row=0, column=4, padx=(0, 8), pady=12, sticky="e")

    # Separador vertical
    tk.Frame(hdr, width=1, bg=sep).grid(row=0, column=5, sticky="ns", pady=12)

    def _refresh_action_btns() -> None:
        status = _get_status()
        is_running = status == "running"
        is_busy    = status in ("starting", "stopping", "restarting")
        btn_start.configure(
            state="disabled" if (is_running or is_busy) else "normal",
            fg_color="#052e16" if not (is_running or is_busy) else acc_mb,
            text_color="#4ade80" if not (is_running or is_busy) else t_mut,
        )
        btn_stop.configure(
            state="normal" if is_running else "disabled",
            fg_color="#7f1d1d" if is_running else "#1c0a0a",
            text_color="#fca5a5" if is_running else "#7f3d3d",
        )
        btn_restart.configure(
            state="normal" if is_running else "disabled",
            text_color=t_sec if is_running else t_mut,
        )

    _refresh_action_btns()

    ctk.CTkButton(
        hdr, text="💾  Salvar", width=100, height=34,
        fg_color=acc_mb, hover_color=acc_dk,
        border_width=1, border_color=acc_dk,
        text_color=accent, corner_radius=8,
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        command=lambda: _save(app, srv),
    ).grid(row=0, column=6, padx=(8, 4), pady=12, sticky="e")

    ctk.CTkButton(
        hdr, text="📋  Presets", width=92, height=34,
        fg_color=acc_mb, hover_color=acc_dk,
        border_width=1, border_color=acc_dk,
        text_color=accent, corner_radius=8,
        font=ctk.CTkFont(family="Segoe UI", size=12),
        command=lambda: _open_preset_dialog(app, srv),
    ).grid(row=0, column=7, padx=(0, 6), pady=12, sticky="e")

    ctk.CTkButton(
        hdr, text="📥  Importar INI", width=130, height=34,
        fg_color=acc_mb, hover_color=acc_dk,
        border_width=1, border_color=acc_dk,
        text_color=accent, corner_radius=8,
        font=ctk.CTkFont(family="Segoe UI", size=12),
        command=lambda: _open_import_ini(app, srv),
    ).grid(row=0, column=8, padx=(0, 8), pady=12, sticky="e")

    def _confirm_remove() -> None:
        import tkinter.messagebox as _mb
        if not _mb.askyesno(
            "Remover Servidor",
            f"Remover '{srv.name}' do gerenciador?\n\nOs arquivos do servidor NÃO serão deletados.",
            parent=app,
        ):
            return
        cache_key = f"server_{srv.id}"
        frame_cache = getattr(app, "_frame_cache", {})
        if cache_key in frame_cache:
            try:
                frame_cache[cache_key].destroy()
            except Exception:
                pass
            frame_cache.pop(cache_key, None)
        app.asm_config_manager.remove_server(srv.id)
        try:
            app._rebuild_server_sidebar()
        except Exception:
            pass
        try:
            app._asm_refresh_dashboard()
        except Exception:
            pass
        app._show_frame("dashboard")

    ctk.CTkButton(
        hdr, text="🗑️  Remover", width=100, height=34,
        fg_color="#3d0a0a", hover_color="#7f1d1d",
        text_color="#fca5a5", corner_radius=8,
        font=ctk.CTkFont(family="Segoe UI", size=11),
        command=_confirm_remove,
    ).grid(row=0, column=9, padx=(0, 16), pady=12, sticky="e")

    # Linha separadora
    ctk.CTkFrame(parent, height=1, fg_color=sep).grid(
        row=0, column=0, sticky="ews")

    # ── Body: nav esquerda + conteúdo direito ─────────────────────────────────
    body = ctk.CTkFrame(parent, fg_color=bg, corner_radius=0)
    body.grid(row=1, column=0, sticky="nsew")
    body.grid_columnconfigure(1, weight=1)
    body.grid_rowconfigure(0, weight=1)

    nav_frame = ctk.CTkScrollableFrame(body, fg_color=nav_bg, corner_radius=0, width=210,
                                       scrollbar_button_color=sep)
    nav_frame.grid(row=0, column=0, sticky="nsew")
    nav_frame.grid_columnconfigure(0, weight=1)

    content_area = ctk.CTkFrame(body, fg_color=bg, corner_radius=0)
    content_area.grid(row=0, column=1, sticky="nsew", padx=(1, 0))
    content_area.grid_columnconfigure(0, weight=1)
    content_area.grid_rowconfigure(0, weight=1)

    if not hasattr(app, "_asm_panel_vars"):
        app._asm_panel_vars = {}
    app._asm_panel_vars[srv.id] = {}
    vars_ref = app._asm_panel_vars[srv.id]
    vars_ref["_app"] = app   # referência ao app para builders que precisam iniciar ações

    _builders: dict[str, Callable] = {
        "Administração":                _build_administracao,
        "Gerenciamento Automático":     _build_auto_management,
        "Detalhes do Discord Bot":      _build_discord,
        "Detalhes do Servidor":         _build_server_details,
        "Regras":                       _build_rules,
        "Transferências / Tributo":     _build_transfers,
        "Bate-papo e Notificações":     _build_chat,
        "HUD e Visuais":                _build_hud,
        "Configurações do Jogador":     _build_players,
        "Configurações do Dino":        _build_dinos,
        "Reprodução":                   _build_breeding,
        "Meio Ambiente":                _build_environment,
        "Estruturas":                   _build_structures,
        "Engramas":                     _build_engrams,
        "Arquivos do Servidor":         _build_server_files,
        "Progressões de Nível":         _build_level_progressions,
        "Substituições de Crafting":    _build_crafting_overrides,
        "Substituições de Stack":       _build_stack_overrides,
        "Substituições de Spawner":     _build_spawner_overrides,
        "Substituições de Supply Crate": _build_supply_crate_overrides,
        "Impedir Transferências":       _build_prevent_transfer,
        "Custom GameUserSettings.ini":  _build_custom_gus,
        "Custom Game.ini":              _build_custom_game,
        "ARK Procedural (PGM)":         _build_pgm,
    }

    section_frames: dict[str, ctk.CTkScrollableFrame] = {}
    for sec in SECTIONS:
        sf = ctk.CTkScrollableFrame(content_area, fg_color="transparent", corner_radius=0)
        sf.grid_columnconfigure(1, weight=1)
        builder = _builders.get(sec)
        if builder:
            builder(sf, srv, vars_ref, bg, accent)
        section_frames[sec] = sf

    _active_section: list[str] = [SECTIONS[0]]
    nav_buttons: dict[str, ctk.CTkButton] = {}

    def _show_section(name: str) -> None:
        old = _active_section[0]
        if old in section_frames:
            section_frames[old].grid_remove()
        if old in nav_buttons:
            nav_buttons[old].configure(fg_color="transparent", text_color=t_sec)
        section_frames[name].grid(row=0, column=0, sticky="nsew")
        nav_buttons[name].configure(fg_color=acc_mb, text_color=accent)
        _active_section[0] = name

    for i, sec in enumerate(SECTIONS):
        btn = ctk.CTkButton(
            nav_frame, text=sec, anchor="w",
            fg_color="transparent", hover_color=hover,
            text_color=t_sec, font=ctk.CTkFont(family="Segoe UI", size=11),
            height=32, corner_radius=6,
            command=lambda s=sec: _show_section(s),
        )
        btn.grid(row=i, column=0, padx=4, pady=1, sticky="ew")
        nav_buttons[sec] = btn

    _show_section(SECTIONS[0])


# ════════════════════════════════════════════════════════════════════════════ #
#  Helpers de campo
# ════════════════════════════════════════════════════════════════════════════ #

def _str_entry(parent, label, field, srv, vars_ref, row, accent,
               wide=False, pw=False, placeholder=""):
    ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(size=11), anchor="w").grid(
        row=row, column=0, padx=(8, 4), pady=3, sticky="w")
    v = tk.StringVar(value=str(getattr(srv, field, "")))
    vars_ref[field] = v
    ctk.CTkEntry(parent, textvariable=v, show="*" if pw else "",
                 placeholder_text=placeholder,
                 width=300 if wide else 200).grid(
        row=row, column=1, padx=(0, 8), pady=3, sticky="ew" if wide else "w")


def _int_entry(parent, label, field, srv, vars_ref, row):
    ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(size=11), anchor="w").grid(
        row=row, column=0, padx=(8, 4), pady=3, sticky="w")
    v = tk.StringVar(value=str(getattr(srv, field, 0)))
    vars_ref[field] = v
    ctk.CTkEntry(parent, textvariable=v, width=100).grid(
        row=row, column=1, padx=(0, 8), pady=3, sticky="w")


def _float_entry(parent, label, field, srv, vars_ref, row):
    ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(size=11), anchor="w").grid(
        row=row, column=0, padx=(8, 4), pady=3, sticky="w")
    v = tk.StringVar(value=str(getattr(srv, field, 1.0)))
    vars_ref[field] = v
    ctk.CTkEntry(parent, textvariable=v, width=100).grid(
        row=row, column=1, padx=(0, 8), pady=3, sticky="w")


def _bool_check(parent, label, field, srv, vars_ref, row, accent, col=0, colspan=2):
    v = tk.BooleanVar(value=bool(getattr(srv, field, False)))
    vars_ref[field] = v
    ctk.CTkCheckBox(parent, text=label, variable=v,
                    checkmark_color=accent, border_color=accent,
                    font=ctk.CTkFont(size=11)).grid(
        row=row, column=col, columnspan=colspan, padx=(8, 4), pady=3, sticky="w")


def _section_label(parent, text, row, accent):
    ctk.CTkLabel(parent, text=text,
                 font=ctk.CTkFont(size=12, weight="bold"),
                 text_color=accent).grid(
        row=row, column=0, columnspan=2, padx=8, pady=(10, 2), sticky="w")


def _add_help(sf: ctk.CTkScrollableFrame, items: "list[tuple[str, str]]") -> None:
    """Adiciona seção AJUDA colapsável no rodapé da seção (fechada por padrão)."""
    from ..ui_constants import get_theme as _get_theme
    th = _get_theme("tek")

    base = sf.grid_size()[1]

    # Separador visual
    ctk.CTkFrame(sf, height=1, fg_color=th["separator"]).grid(
        row=base, column=0, columnspan=2, sticky="ew", padx=8, pady=(14, 4))

    # Frame de conteúdo (pré-construído mas invisível)
    content_frame = ctk.CTkFrame(sf, fg_color=th.get("card_bg", "#0d1b2a"), corner_radius=8)
    content_frame.grid_columnconfigure(0, weight=1)
    for i, (label, desc) in enumerate(items):
        row_f = ctk.CTkFrame(content_frame, fg_color="transparent")
        row_f.grid(row=i, column=0, sticky="ew", padx=12, pady=3)
        row_f.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row_f, text=f"• {label}:",
                     font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                     text_color=th["accent"], width=200, anchor="nw",
                     ).grid(row=0, column=0, sticky="nw", padx=(0, 8))
        ctk.CTkLabel(row_f, text=desc,
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=th["text_secondary"],
                     wraplength=460, justify="left", anchor="nw",
                     ).grid(row=0, column=1, sticky="nw")
    ctk.CTkFrame(content_frame, height=8, fg_color="transparent").grid(row=len(items), column=0)

    state = [False]
    arrow_var = tk.StringVar(value="▶  AJUDA")

    def _toggle():
        state[0] = not state[0]
        if state[0]:
            arrow_var.set("▼  AJUDA")
            content_frame.grid(row=base + 2, column=0, columnspan=2,
                               sticky="ew", padx=8, pady=(0, 16))
        else:
            arrow_var.set("▶  AJUDA")
            content_frame.grid_remove()

    ctk.CTkButton(
        sf, textvariable=arrow_var, anchor="w", width=0,
        fg_color="transparent", hover_color=th.get("accent_muted_bg", "#052e16"),
        text_color=th["accent"],
        font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
        height=28, corner_radius=6,
        command=_toggle,
    ).grid(row=base + 1, column=0, columnspan=2, padx=4, pady=(0, 4), sticky="ew")


# ── Mapa: dados e seletor visual ─────────────────────────────────────────────

_ARK_MAP_DATA: list[tuple[str, str, str]] = [
    # (id_interno, nome_exibição, emoji/ícone)
    ("TheIsland",        "The Island",      "🏝"),
    ("TheCenter",        "The Center",      "🌀"),
    ("ScorchedEarth_P",  "Scorched Earth",  "🏜"),
    ("Ragnarok",         "Ragnarok",        "⚔"),
    ("Aberration_P",     "Aberration",      "☢"),
    ("Extinction",       "Extinction",      "💀"),
    ("Valguero_P",       "Valguero",        "🌿"),
    ("Genesis",          "Genesis Pt. 1",   "🧬"),
    ("CrystalIsles",     "Crystal Isles",   "💎"),
    ("Gen2",             "Genesis Pt. 2",   "🌌"),
    ("LostIsland",       "Lost Island",     "🗺"),
    ("Fjordur",          "Fjordur",         "🏔"),
]


def _map_display_name(map_id: str) -> str:
    for mid, name, _ in _ARK_MAP_DATA:
        if mid == map_id:
            return name
    return map_id


class _MapPickerDialog(ctk.CTkToplevel):
    """Dialog simples para selecionar mapa — grade de botões estilizados."""

    def __init__(self, parent, map_var: tk.StringVar, label_ref, accent: str, bg: str):
        super().__init__(parent)
        self.title("Selecionar Mapa")
        self.resizable(False, False)
        self.configure(fg_color="#0f172a")
        self.grab_set()
        self.focus_set()

        self._map_var = map_var
        self._lbl = label_ref

        ctk.CTkLabel(self, text="Escolha o mapa do servidor",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=accent).pack(padx=20, pady=(16, 10))

        grid_f = ctk.CTkFrame(self, fg_color="transparent")
        grid_f.pack(padx=16, pady=(0, 16))

        cols = 4
        for idx, (mid, name, icon) in enumerate(_ARK_MAP_DATA):
            r, c = divmod(idx, cols)
            is_sel = (map_var.get() == mid)
            btn = ctk.CTkButton(
                grid_f,
                text=f"{icon}\n{name}",
                width=110, height=60,
                corner_radius=10,
                font=ctk.CTkFont(size=11),
                fg_color=accent if is_sel else "#1e293b",
                hover_color="#22c55e" if not is_sel else "#16a34a",
                text_color="#0f172a" if is_sel else "#e2e8f0",
                command=lambda m=mid, n=name: self._select(m, n),
            )
            btn.grid(row=r, column=c, padx=4, pady=4)

    def _select(self, map_id: str, map_name: str) -> None:
        self._map_var.set(map_id)
        self._lbl.configure(text=map_name)
        self.destroy()


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 1 — Administração
# ════════════════════════════════════════════════════════════════════════════ #

def _build_administracao(sf, srv, vars_ref, bg, accent):
    _section_label(sf, "Identificação", 0, accent)
    _str_entry(sf, "Nome no gerenciador",      "name",             srv, vars_ref,  1, accent, wide=True)
    _str_entry(sf, "Pasta de instalação",      "install_dir",      srv, vars_ref,  2, accent, wide=True)

    # ── Seletor visual de mapa ────────────────────────────────────────────────
    _section_label(sf, "Mapa", 3, accent)
    map_var = tk.StringVar(value=srv.server_map)
    vars_ref["server_map"] = map_var

    map_display_f = ctk.CTkFrame(sf, fg_color="transparent")
    map_display_f.grid(row=4, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="ew")

    map_lbl = ctk.CTkLabel(
        map_display_f,
        text=_map_display_name(srv.server_map),
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=accent,
    )
    map_lbl.pack(side="left", padx=(0, 8))

    def _open_map_picker():
        _MapPickerDialog(sf, map_var, map_lbl, accent, bg)

    ctk.CTkButton(
        map_display_f, text="Trocar mapa…", width=110, height=26,
        fg_color="#1e293b", hover_color="#334155",
        text_color="#94a3b8", corner_radius=6,
        font=ctk.CTkFont(size=11),
        command=_open_map_picker,
    ).pack(side="left")

    # Campo texto para mapa não oficial / customizado
    manual_f = ctk.CTkFrame(sf, fg_color="transparent")
    manual_f.grid(row=5, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")
    ctk.CTkLabel(manual_f, text="Ou digite o nome interno:",
                 font=ctk.CTkFont(size=10), text_color="#64748b").pack(side="left", padx=(0, 6))
    manual_entry = ctk.CTkEntry(manual_f, textvariable=map_var, width=220,
                                placeholder_text="ex: Svartalfheim, PrimitivePlus_P…")
    manual_entry.pack(side="left")

    _str_entry(sf, "Total Conversion Mod ID",  "total_conversion_mod_id", srv, vars_ref, 6, accent)

    _section_label(sf, "Sessão",          7, accent)
    _str_entry(sf, "Nome da sessão",           "session_name",     srv, vars_ref,  8, accent, wide=True)
    _str_entry(sf, "Alt Save Directory",       "alt_save_directory_name", srv, vars_ref, 9, accent)
    _float_entry(sf,"Auto-save (min)",         "auto_save_period", srv, vars_ref, 10)

    _section_label(sf, "Rede",           11, accent)
    _int_entry(sf,   "Porta (game)",           "server_port",      srv, vars_ref, 12)

    # Porta peer — sempre game_port + 1, read-only
    _peer_row = 13
    ctk.CTkLabel(sf, text="Porta (peer)", font=ctk.CTkFont(size=11), anchor="w").grid(
        row=_peer_row, column=0, padx=(8, 4), pady=3, sticky="w")
    _peer_var = tk.StringVar(value=str(getattr(srv, "server_port", 7777) + 1))
    _peer_entry = ctk.CTkEntry(sf, textvariable=_peer_var, width=100,
                               state="disabled", text_color="#475569")
    _peer_entry.grid(row=_peer_row, column=1, padx=(0, 8), pady=3, sticky="w")
    ctk.CTkLabel(sf, text="(game + 1, automático)", font=ctk.CTkFont(size=9),
                 text_color="#475569").grid(row=_peer_row, column=1, padx=(110, 0), pady=3, sticky="w")
    # Atualiza peer quando game_port muda
    def _on_game_port_change(*_):
        try:
            _peer_var.set(str(int(vars_ref["server_port"].get()) + 1))
        except ValueError:
            pass
    vars_ref["server_port"].trace_add("write", _on_game_port_change)

    _int_entry(sf,   "Porta (query)",          "query_port",       srv, vars_ref, 14)
    _int_entry(sf,   "Max jogadores",          "max_players",      srv, vars_ref, 15)

    # ── IP Bind com botão de detecção automática ─────────────────────────────
    ctk.CTkLabel(sf, text="IP Bind (MultiHome)", font=ctk.CTkFont(size=11), anchor="w").grid(
        row=16, column=0, padx=(8, 4), pady=3, sticky="w")
    _ip_var = tk.StringVar(value=str(getattr(srv, "server_ip", "")))
    vars_ref["server_ip"] = _ip_var
    _ip_frame = ctk.CTkFrame(sf, fg_color="transparent")
    _ip_frame.grid(row=16, column=1, padx=(0, 8), pady=3, sticky="w")
    _ip_entry = ctk.CTkEntry(_ip_frame, textvariable=_ip_var,
                             placeholder_text="vazio = escuta em todas as interfaces", width=160)
    _ip_entry.pack(side="left", padx=(0, 4))

    def _detect_public_ip():
        import threading
        _ip_btn.configure(text="...", state="disabled")
        def _fetch():
            import socket
            ip = ""
            # Obtém o IP da interface de rede local usada para conexões externas.
            # MultiHome deve ser o IP da interface (ex: 192.168.x.x em home server,
            # IP público em VPS) — NÃO o IP externo/NAT do roteador.
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(2)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
            except Exception:
                pass
            if not ip:
                try:
                    ip = socket.gethostbyname(socket.gethostname())
                except Exception:
                    pass
            sf.after(0, lambda: _on_ip_result(ip))
        threading.Thread(target=_fetch, daemon=True).start()

    def _on_ip_result(ip: str):
        _ip_btn.configure(text="Detectar IP", state="normal")
        if ip:
            _ip_var.set(ip)
        else:
            from tkinter import messagebox
            messagebox.showwarning("IP não detectado",
                "Não foi possível detectar o IP da interface de rede.\n"
                "Preencha manualmente com o IP local da máquina (ex: 192.168.x.x).\n\n"
                "Dica: use ipconfig no cmd para encontrar o IP.",
                parent=sf.winfo_toplevel())

    _ip_btn = ctk.CTkButton(_ip_frame, text="Detectar IP", width=90, height=28,
                            command=_detect_public_ip,
                            fg_color=accent, hover_color="#0f766e",
                            font=ctk.CTkFont(size=11))
    _ip_btn.pack(side="left")
    # Não auto-detecta ao abrir — MultiHome deve ficar vazio por padrão.
    # O botão "Detectar IP" existe apenas para uso manual quando o servidor
    # tem múltiplas interfaces e o usuário quer forçar bind em uma específica.

    _section_label(sf, "Senhas",         17, accent)
    _str_entry(sf, "Senha do servidor",        "server_password",  srv, vars_ref, 18, accent, pw=True)
    _str_entry(sf, "Senha admin",              "admin_password",   srv, vars_ref, 19, accent, pw=True)
    _str_entry(sf, "Senha spectator",          "spectator_password", srv, vars_ref, 20, accent, pw=True)

    _section_label(sf, "RCON",           21, accent)
    _bool_check(sf,  "Habilitar RCON",         "rcon_enabled",     srv, vars_ref, 22, accent)
    _int_entry(sf,   "Porta RCON",             "rcon_port",        srv, vars_ref, 23)
    _int_entry(sf,   "Buffer log RCON",        "rcon_log_buffer",  srv, vars_ref, 24)

    _section_label(sf, "Logs / Admin",   25, accent)
    _bool_check(sf,  "Admin logging",          "admin_logging",    srv, vars_ref, 26, accent)
    _int_entry(sf,   "Max tribe logs",         "max_tribe_logs",   srv, vars_ref, 27)
    _bool_check(sf, "Log estruturas destruídas por inimigos", "tribe_log_destroyed_enemy_structures", srv, vars_ref, 28, accent)
    _bool_check(sf, "Ocultar fonte de dano nos logs",         "allow_hide_damage_source",             srv, vars_ref, 29, accent)

    _section_label(sf, "Extinction / Respawn Dinos", 30, accent)
    _bool_check(sf,  "Evento de extinção",      "enable_extinction_event",         srv, vars_ref, 31, accent)
    _int_entry(sf,   "Intervalo extinção (s)",  "extinction_event_interval",        srv, vars_ref, 32)
    _bool_check(sf, "Forçar respawn dinos selvagens",  "enable_auto_respawn_wild_dinos",  srv, vars_ref, 33, accent)
    _int_entry(sf,   "Intervalo respawn (s)",   "auto_respawn_wild_dinos_interval", srv, vars_ref, 34)

    _section_label(sf, "Jogadores Ociosos", 35, accent)
    _bool_check(sf,  "Kickar ociosos",          "enable_kick_idle_players",         srv, vars_ref, 36, accent)
    _float_entry(sf, "Período idle kick (s)",   "kick_idle_players",                srv, vars_ref, 37)

    _section_label(sf, "Cluster / Cross-ARK", 37, accent)
    _str_entry(sf, "Cluster ID",               "cross_ark_cluster_id",             srv, vars_ref, 38, accent)
    _str_entry(sf, "Cluster Dir Override",     "cluster_dir_override",             srv, vars_ref, 39, accent, wide=True)
    _bool_check(sf,"Permitir dinos de outros clusters", "cross_ark_allow_foreign_dino_downloads", srv, vars_ref, 40, accent)

    _section_label(sf, "Branch SteamCMD (Beta)", 43, accent)
    _str_entry(sf, "Branch Name",     "branch_name",     srv, vars_ref, 44, accent)
    _str_entry(sf, "Branch Password", "branch_password", srv, vars_ref, 45, accent, pw=True)
    _add_help(sf, [("Branch Name",     "Ex: 'experimental'. Deixe vazio para a branch estável (padrão)."),
                   ("Branch Password", "Necessário apenas em branches privadas.")])

    _section_label(sf, "Mods (Steam Workshop)", 41, accent)

    # ── Container principal do gerenciador de mods ────────────────────────────
    _mod_frame = ctk.CTkFrame(sf, fg_color="#0d1b2a", corner_radius=8)
    _mod_frame.grid(row=42, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="ew")
    _mod_frame.grid_columnconfigure(0, weight=1)

    # Cache de informações: {mod_id: {"name": ..., "info": ...}}
    _mod_cache: dict = vars_ref.setdefault("_mod_info_cache", {})

    # Hidden textbox — sistema de save lê daqui via vars_ref["_mods_text"]
    _hidden_mods = ctk.CTkTextbox(_mod_frame, height=1,
                                  fg_color="#0d1b2a", text_color="#0d1b2a", border_width=0)
    _hidden_mods.grid(row=99, column=0, sticky="ew")
    _hidden_mods.insert("1.0", "\n".join(srv.active_mods))
    vars_ref["_mods_text"] = _hidden_mods

    _mod_rows: list[dict] = []

    def _sync_hidden():
        ids = [r["id_var"].get().strip() for r in _mod_rows if r["id_var"].get().strip()]
        _hidden_mods.configure(state="normal")
        _hidden_mods.delete("1.0", "end")
        _hidden_mods.insert("1.0", "\n".join(ids))

    def _refresh_mod_labels():
        for r in _mod_rows:
            mid = r["id_var"].get().strip()
            cd = _mod_cache.get(mid)
            if cd:
                r["name_lbl"].configure(text=cd.get("name", "—"))
                r["info_lbl"].configure(text=cd.get("info", "—"))
            elif mid:
                r["name_lbl"].configure(text="(clique em Buscar)")
                r["info_lbl"].configure(text="—")
            else:
                r["name_lbl"].configure(text="")
                r["info_lbl"].configure(text="")

    def _add_mod_row(mod_id: str = ""):
        ridx = len(_mod_rows)
        rf = ctk.CTkFrame(_rows_outer, fg_color="#07101c", corner_radius=3)
        rf.grid(row=ridx, column=0, sticky="ew", padx=4, pady=1)
        rf.grid_columnconfigure(1, weight=1)

        id_var = tk.StringVar(value=mod_id)
        ctk.CTkEntry(rf, textvariable=id_var, width=115, height=26,
                     placeholder_text="ID Steam",
                     font=ctk.CTkFont(family="Consolas", size=11),
                     ).grid(row=0, column=0, padx=(4, 4), pady=2)

        name_lbl = ctk.CTkLabel(rf, text="", font=ctk.CTkFont(size=11),
                                text_color="#94a3b8", anchor="w")
        name_lbl.grid(row=0, column=1, padx=(0, 4), sticky="ew")

        info_lbl = ctk.CTkLabel(rf, text="", font=ctk.CTkFont(size=10),
                                text_color="#475569", width=170, anchor="w")
        info_lbl.grid(row=0, column=2, padx=(0, 4))

        status_lbl = ctk.CTkLabel(rf, text="⏳", font=ctk.CTkFont(size=10),
                                  text_color="gray50", width=90, anchor="e")
        status_lbl.grid(row=0, column=3, padx=(0, 4))

        rd = {"id_var": id_var, "name_lbl": name_lbl, "info_lbl": info_lbl,
              "status_lbl": status_lbl, "frame": rf}

        def _check_status(_mid: str, _lbl=status_lbl) -> None:
            import threading as _th
            from pathlib import Path as _Path
            def _worker():
                idir = srv.install_dir
                if not idir or not _mid:
                    sf.after(0, lambda: _lbl.configure(text=""))
                    return
                base = _Path(idir) / "ShooterGame" / "Content" / "Mods"
                has_folder = (base / _mid).exists()
                has_dot_mod = (base / f"{_mid}.mod").exists()
                if has_folder and has_dot_mod:
                    txt, col = "✅ instalado", "#4ade80"
                elif has_folder:
                    txt, col = "⚠ sem .mod", "#facc15"
                else:
                    txt, col = "❌ não instalado", "#f87171"
                try:
                    sf.after(0, lambda t=txt, c=col: _lbl.configure(text=t, text_color=c))
                except Exception:
                    pass
            _th.Thread(target=_worker, daemon=True).start()

        def _del(r=rd, f=rf):
            f.destroy()
            if r in _mod_rows:
                _mod_rows.remove(r)
            for i, x in enumerate(_mod_rows):
                x["frame"].grid(row=i, column=0, sticky="ew", padx=4, pady=1)
            _sync_hidden()

        ctk.CTkButton(rf, text="✕", width=24, height=24,
                      fg_color="#5c1a1a", hover_color="#7c2020",
                      font=ctk.CTkFont(size=10), corner_radius=4,
                      command=_del).grid(row=0, column=4, padx=(0, 4))

        _mod_rows.append(rd)
        id_var.trace_add("write", lambda *_: (_sync_hidden(), _check_status(id_var.get().strip())))

        cd = _mod_cache.get(mod_id.strip())
        if cd:
            name_lbl.configure(text=cd.get("name", "—"))
            info_lbl.configure(text=cd.get("info", "—"))
        elif mod_id.strip():
            name_lbl.configure(text="(clique em Buscar)")

        # Verifica status de instalação imediatamente
        if mod_id.strip():
            _check_status(mod_id.strip())

    # ── Toolbar ───────────────────────────────────────────────────────────────
    _mods_tb = ctk.CTkFrame(_mod_frame, fg_color="transparent")
    _mods_tb.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))

    ctk.CTkButton(_mods_tb, text="＋ Mod", width=82, height=28,
                  fg_color="#14532d", hover_color="#166534",
                  font=ctk.CTkFont(size=11),
                  command=_add_mod_row).pack(side="left", padx=(0, 4))

    def _do_fetch_workshop():
        import threading
        import requests as _rq
        ids = [r["id_var"].get().strip() for r in _mod_rows if r["id_var"].get().strip()]
        if not ids:
            return
        _fetch_btn.configure(state="disabled", text="⏳  Buscando...")

        def _worker():
            try:
                data = {"itemcount": len(ids)}
                for i, mid in enumerate(ids):
                    data[f"publishedfileids[{i}]"] = mid
                resp = _rq.post(
                    "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/",
                    data=data, timeout=15,
                )
                for d in resp.json().get("response", {}).get("publishedfiledetails", []):
                    fid = d.get("publishedfileid", "")
                    if d.get("result") == 1:
                        from datetime import datetime as _dt
                        ts = d.get("time_updated", 0)
                        date_str = _dt.fromtimestamp(ts).strftime("%d/%m/%Y") if ts else "—"
                        _mod_cache[fid] = {"name": d.get("title", "—"), "info": f"Atualiz.: {date_str}"}
                    else:
                        _mod_cache[fid] = {"name": "❌ ID inválido", "info": "—"}
            except Exception:
                pass
            sf.after(0, lambda: (
                _fetch_btn.configure(state="normal", text="🔍  Buscar Info"),
                _refresh_mod_labels(),
            ))

        threading.Thread(target=_worker, daemon=True).start()

    _fetch_btn = ctk.CTkButton(_mods_tb, text="🔍  Buscar Info", width=118, height=28,
                               fg_color="#0e4a6e", hover_color="#0a3550",
                               font=ctk.CTkFont(size=11),
                               command=_do_fetch_workshop)
    _fetch_btn.pack(side="left", padx=(0, 4))

    def _do_redownload_mods():
        from ..asm_engine.asm_steamcmd import AsmSteamCmd
        _app = vars_ref.get("_app")
        _lines = _hidden_mods.get("1.0", "end").strip().splitlines()
        _ids = [l.strip() for l in _lines if l.strip()]
        if not _ids:
            import tkinter.messagebox as mb
            mb.showinfo("Sem mods", "Nenhum mod configurado na lista.")
            return
        scmd_path = getattr(getattr(getattr(_app, "config_manager", None), "config", None), "steamcmd_path", None)
        sc = AsmSteamCmd(scmd_path, on_log=lambda msg: _app.after(0, lambda m=msg: _log_steamcmd(m)))
        if not sc.is_available:
            import tkinter.messagebox as mb
            mb.showwarning("SteamCMD não encontrado", "steamcmd.exe não localizado.")
            return
        _open_steamcmd_log_window(_app, sf, sc)
        sc.download_mods(
            _ids, srv.install_dir,
            on_done=lambda ok, msg: _app.after(0, lambda: _log_steamcmd(f"[{'OK' if ok else 'ERRO'}] {msg}")),
        )

    ctk.CTkButton(_mods_tb, text="⬇  Redownload Mods", width=155, height=28,
                  fg_color="#1e3a5f", hover_color="#1e40af",
                  font=ctk.CTkFont(size=11),
                  command=_do_redownload_mods).pack(side="left", padx=(0, 4))

    ctk.CTkButton(_mods_tb, text="✅  Validar IDs", width=105, height=28,
                  fg_color="#1c1917", hover_color="#292524",
                  font=ctk.CTkFont(size=11),
                  command=_do_fetch_workshop).pack(side="left")

    # ── Cabeçalho das colunas ─────────────────────────────────────────────────
    _mods_hdr = ctk.CTkFrame(_mod_frame, fg_color="#0f2030", corner_radius=4, height=24)
    _mods_hdr.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 2))
    _mods_hdr.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(_mods_hdr, text="ID Steam", font=ctk.CTkFont(size=9, weight="bold"),
                 text_color="#475569", width=115, anchor="center").grid(row=0, column=0, padx=(4, 4), pady=2)
    ctk.CTkLabel(_mods_hdr, text="Nome do Mod", font=ctk.CTkFont(size=9, weight="bold"),
                 text_color="#475569", anchor="w").grid(row=0, column=1, padx=(0, 4), sticky="w", pady=2)
    ctk.CTkLabel(_mods_hdr, text="Última Atualização", font=ctk.CTkFont(size=9, weight="bold"),
                 text_color="#475569", width=170, anchor="w").grid(row=0, column=2, padx=(0, 4), pady=2)
    ctk.CTkLabel(_mods_hdr, text="", width=28).grid(row=0, column=3)

    # ── Área das linhas ───────────────────────────────────────────────────────
    _rows_outer = ctk.CTkFrame(_mod_frame, fg_color="#060d14", corner_radius=6)
    _rows_outer.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
    _rows_outer.grid_columnconfigure(0, weight=1)

    # Popula com os mods existentes
    for _mid in srv.active_mods:
        _add_mod_row(_mid)
    if not srv.active_mods:
        _add_mod_row()  # linha vazia para o usuário começar

    _section_label(sf, "Args CLI adicionais", 43, accent)
    _str_entry(sf, "Additional Args",          "additional_args",  srv, vars_ref, 44, accent, wide=True)

    _section_label(sf, "Personalização do Card", 45, accent)
    _str_entry(sf, "Cor do card (hex, ex: #22c55e)", "color",      srv, vars_ref, 46, accent)

    ctk.CTkLabel(sf, text="Etiquetas (separadas por vírgula)",
                 font=ctk.CTkFont(size=11), anchor="w").grid(
        row=47, column=0, padx=(8, 4), pady=3, sticky="w")
    tags_var = tk.StringVar(value=", ".join(getattr(srv, "tags", [])))
    vars_ref["_tags_csv"] = tags_var
    ctk.CTkEntry(sf, textvariable=tags_var).grid(
        row=47, column=1, padx=(0, 8), pady=3, sticky="ew")

    # ── Ações do Servidor (SteamCMD) ─────────────────────────────────────────
    _section_label(sf, "Ações do Servidor", 48, accent)

    def _do_install():
        from ..asm_engine.asm_steamcmd import AsmSteamCmd
        _app = vars_ref.get("_app")
        scmd_path = getattr(getattr(getattr(_app, "config_manager", None), "config", None), "steamcmd_path", None)
        sc = AsmSteamCmd(scmd_path, on_log=lambda msg: _app.after(0, lambda m=msg: _log_steamcmd(m)))
        if not sc.is_available:
            import tkinter.messagebox as mb
            mb.showwarning("SteamCMD não encontrado",
                           "steamcmd.exe não foi localizado.\nConfigure o caminho em Configurações ou instale o SteamCMD em C:\\steamcmd\\")
            return
        _open_steamcmd_log_window(_app, sf, sc)
        sc.install_server(
            srv.install_dir,
            branch=srv.branch_name,
            branch_password=srv.branch_password,
            on_done=lambda ok, msg: _app.after(0, lambda: _log_steamcmd(f"[{'OK' if ok else 'ERRO'}] {msg}")),
        )

    def _do_mods():
        from ..asm_engine.asm_steamcmd import AsmSteamCmd
        _app = vars_ref.get("_app")
        if not srv.active_mods:
            import tkinter.messagebox as mb
            mb.showinfo("Sem mods", "Nenhum mod configurado na lista de Mods.")
            return
        scmd_path = getattr(getattr(getattr(_app, "config_manager", None), "config", None), "steamcmd_path", None)
        sc = AsmSteamCmd(scmd_path, on_log=lambda msg: _app.after(0, lambda m=msg: _log_steamcmd(m)))
        if not sc.is_available:
            import tkinter.messagebox as mb
            mb.showwarning("SteamCMD não encontrado",
                           "steamcmd.exe não foi localizado.\nConfigure o caminho em Configurações.")
            return
        _open_steamcmd_log_window(_app, sf, sc)
        sc.download_mods(
            srv.active_mods, srv.install_dir,
            on_done=lambda ok, msg: _app.after(0, lambda: _log_steamcmd(f"[{'OK' if ok else 'ERRO'}] {msg}")),
        )

    def _do_validate():
        from ..asm_engine.asm_steamcmd import AsmSteamCmd
        _app = vars_ref.get("_app")
        scmd_path = getattr(getattr(getattr(_app, "config_manager", None), "config", None), "steamcmd_path", None)
        sc = AsmSteamCmd(scmd_path, on_log=lambda msg: _app.after(0, lambda m=msg: _log_steamcmd(m)))
        if not sc.is_available:
            import tkinter.messagebox as mb
            mb.showwarning("SteamCMD não encontrado",
                           "steamcmd.exe não foi localizado.")
            return
        _open_steamcmd_log_window(_app, sf, sc)
        sc.validate_server(
            srv.install_dir,
            on_done=lambda ok, msg: _app.after(0, lambda: _log_steamcmd(f"[{'OK' if ok else 'ERRO'}] {msg}")),
        )

    # janela de log do SteamCMD (singleton por painel)
    _log_win: list = [None]
    _log_box: list = [None]

    def _log_steamcmd(msg: str):
        if _log_box[0]:
            _log_box[0].configure(state="normal")
            _log_box[0].insert("end", msg + "\n")
            _log_box[0].see("end")
            _log_box[0].configure(state="disabled")

    def _open_steamcmd_log_window(_app, parent, sc):
        if _log_win[0] and _log_win[0].winfo_exists():
            _log_win[0].lift()
            return
        win = ctk.CTkToplevel(_app)
        win.title(f"SteamCMD — {srv.name}")
        win.geometry("700x400")
        win.configure(fg_color=bg)
        _log_win[0] = win
        box = ctk.CTkTextbox(win, state="disabled", font=ctk.CTkFont(family="Consolas", size=11),
                             fg_color="#0a0a0a", text_color="#86efac")
        box.pack(fill="both", expand=True, padx=8, pady=8)
        _log_box[0] = box
        btn_abort = ctk.CTkButton(win, text="⏹  Cancelar", width=110, height=28,
                                  fg_color="#7f1d1d", hover_color="#991b1b",
                                  command=lambda: (sc.abort(), win.destroy()))
        btn_abort.pack(pady=(0, 8))
        win.protocol("WM_DELETE_WINDOW", win.destroy)

    btn_row = ctk.CTkFrame(sf, fg_color="transparent")
    btn_row.grid(row=49, column=0, columnspan=2, padx=8, pady=4, sticky="w")
    ctk.CTkButton(btn_row, text="⬇  Instalar / Atualizar", width=170, height=30,
                  fg_color="#14532d", hover_color="#166534",
                  font=ctk.CTkFont(size=11), command=_do_install).pack(side="left", padx=(0, 6))
    ctk.CTkButton(btn_row, text="📦  Baixar Mods", width=130, height=30,
                  fg_color="#1e3a5f", hover_color="#1e40af",
                  font=ctk.CTkFont(size=11), command=_do_mods).pack(side="left", padx=(0, 6))
    ctk.CTkButton(btn_row, text="✅  Validar Arquivos", width=150, height=30,
                  fg_color="#1c1917", hover_color="#292524",
                  font=ctk.CTkFont(size=11), command=_do_validate).pack(side="left")

    _add_help(sf, [
        ("Nome no gerenciador", "Identificação interna usada apenas no aplicativo. Não afeta o servidor."),
        ("Pasta de instalação", "Caminho onde o servidor está instalado (raiz do SteamCMD, onde fica ShooterGame/)."),
        ("Porta do servidor (game)", "Porta UDP principal do jogo. Padrão: 7777. Deve ser única por servidor."),
        ("Porta peer (game+1)", "Calculada automaticamente como Porta game + 1. Usada para comunicação interna."),
        ("Porta Steam (query)", "Porta UDP para listagem no Steam. Padrão: 27015. Deve ser única por servidor."),
        ("Porta RCON", "Porta TCP para administração remota via RCON. Padrão: 27020."),
        ("Senha do servidor", "Senha exigida para entrar no servidor. Deixe em branco para acesso livre."),
        ("Senha admin", "Senha para usar comandos de admin (enablecheats). Nunca deixe em branco em servidores públicos."),
        ("Mods", "IDs do Steam Workshop separados por vírgula. A ordem importa — mods são carregados nessa sequência."),
        ("Instalar / Atualizar", "Executa SteamCMD para baixar ou atualizar o servidor. Pode demorar vários minutos."),
        ("Validar Arquivos", "Verifica a integridade dos arquivos do servidor e repara os corrompidos."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 2 — Gerenciamento Automático
# ════════════════════════════════════════════════════════════════════════════ #

def _build_auto_management(sf, srv, vars_ref, bg, accent):
    _section_label(sf, "Reinício Programado", 0, accent)
    _bool_check(sf, "Habilitar reinício automático",       "enable_auto_restart",           srv, vars_ref, 1, accent)
    _str_entry(sf,  "Horário de reinício (HH:MM)",         "auto_restart_time",             srv, vars_ref, 2, accent)
    _int_entry(sf,  "Contagem regressiva (min)",           "restart_countdown_minutes",     srv, vars_ref, 3)

    _section_label(sf, "Atualização Automática", 4, accent)
    _bool_check(sf, "Verificar atualizações automaticamente", "enable_auto_update_check",  srv, vars_ref, 5, accent)
    _int_entry(sf,  "Intervalo de verificação (min)",      "auto_update_check_minutes",     srv, vars_ref, 6)

    _section_label(sf, "Notificações", 7, accent)
    _bool_check(sf, "Notificar via Discord em eventos",    "notify_discord_on_events",      srv, vars_ref, 8, accent)

    _add_help(sf, [
        ("Reinício automático", "Reinicia o servidor todo dia no horário configurado (formato HH:MM, 24h)."),
        ("Contagem regressiva", "Avisa os jogadores X minutos antes do reinício via mensagem no chat."),
        ("Verificar atualizações", "Checa periodicamente se há nova versão do servidor no Steam e pode reiniciar para atualizar."),
        ("Notificar via Discord", "Envia mensagem no canal Discord configurado quando eventos ocorrem no servidor."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 3 — Discord Bot
# ════════════════════════════════════════════════════════════════════════════ #

def _build_discord(sf, srv, vars_ref, bg, accent):
    _section_label(sf, "Webhook do Discord", 0, accent)
    _str_entry(sf, "URL do Webhook",            "discord_webhook_url",           srv, vars_ref, 1, accent, wide=True)

    _section_label(sf, "Eventos a notificar", 2, accent)
    _bool_check(sf, "Servidor iniciado",        "discord_notify_server_start",   srv, vars_ref, 3, accent)
    _bool_check(sf, "Servidor parado",          "discord_notify_server_stop",    srv, vars_ref, 4, accent)
    _bool_check(sf, "Jogador entrou (join)",    "discord_notify_player_join",    srv, vars_ref, 5, accent)
    _bool_check(sf, "Jogador saiu (leave)",     "discord_notify_player_leave",   srv, vars_ref, 6, accent)

    _add_help(sf, [
        ("URL do Webhook", "Obtenha em: Configurações do servidor Discord → Integrações → Webhooks → Copiar URL."),
        ("Servidor iniciado/parado", "Notifica quando o processo do servidor é iniciado ou encerrado."),
        ("Jogador join/leave", "Notifica quando um jogador entra ou sai do servidor."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 4 — Detalhes do Servidor
# ════════════════════════════════════════════════════════════════════════════ #

def _build_server_details(sf, srv, vars_ref, bg, accent):
    _section_label(sf, "MOTD (Message of the Day)", 0, accent)
    ctk.CTkLabel(sf, text="Mensagem MOTD:", font=ctk.CTkFont(size=11)).grid(
        row=1, column=0, padx=8, pady=(4, 0), sticky="nw")
    motd_box = ctk.CTkTextbox(sf, height=80, font=ctk.CTkFont(size=11))
    motd_box.grid(row=1, column=1, padx=(0, 8), pady=(4, 0), sticky="ew")
    motd_box.insert("1.0", srv.motd)
    vars_ref["_motd_text"] = motd_box
    _int_entry(sf, "Duração MOTD (s)", "motd_duration", srv, vars_ref, 2)

    _section_label(sf, "BanList", 3, accent)
    _bool_check(sf, "Usar BanList URL", "enable_ban_list_url", srv, vars_ref, 4, accent)
    _str_entry(sf, "URL da BanList",    "ban_list_url",        srv, vars_ref, 5, accent, wide=True)

    _section_label(sf, "Branch SteamCMD", 6, accent)
    _str_entry(sf, "Branch name",    "branch_name",     srv, vars_ref, 7, accent)
    _str_entry(sf, "Branch password","branch_password", srv, vars_ref, 8, accent, pw=True)

    _section_label(sf, "Notas internas", 9, accent)
    ctk.CTkLabel(sf, text="Notas:", font=ctk.CTkFont(size=11)).grid(
        row=10, column=0, padx=8, pady=(4, 0), sticky="nw")
    notes_box = ctk.CTkTextbox(sf, height=60, font=ctk.CTkFont(size=11))
    notes_box.grid(row=10, column=1, padx=(0, 8), pady=(4, 0), sticky="ew")
    notes_box.insert("1.0", srv.notes)
    vars_ref["_notes_text"] = notes_box

    _add_help(sf, [
        ("MOTD", "Mensagem exibida aos jogadores ao entrar no servidor. Duração define por quantos segundos fica visível."),
        ("BanList URL", "URL para uma lista de IDs banidos globalmente. A lista ARK oficial é usada por padrão."),
        ("Branch SteamCMD", "Use para instalar versões beta ou experimental do servidor (ex: 'experimental'). Deixe em branco para versão estável."),
        ("Notas internas", "Campo livre apenas para referência sua. Não afeta o servidor."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 5 — Regras
# ════════════════════════════════════════════════════════════════════════════ #

def _build_rules(sf, srv, vars_ref, bg, accent):
    _section_label(sf, "Modo de Jogo", 0, accent)
    _bool_check(sf, "PvP habilitado",                     "enable_pvp",                              srv, vars_ref,  1, accent)
    _bool_check(sf, "Hardcore",                           "enable_hardcore",                         srv, vars_ref,  2, accent)
    _bool_check(sf, "Construção em caverna (PvE)",        "allow_cave_building_pve",                 srv, vars_ref,  3, accent)
    _bool_check(sf, "Sem fogo amigo PvP",                 "disable_friendly_fire_pvp",               srv, vars_ref,  4, accent)
    _bool_check(sf, "Sem fogo amigo PvE",                 "disable_friendly_fire_pve",               srv, vars_ref,  5, accent)
    _bool_check(sf, "Desativar Loot Crates",              "disable_loot_crates",                     srv, vars_ref,  6, accent)
    _bool_check(sf, "Extra Structure Prevention Volumes", "enable_extra_structure_prevention_volumes",srv, vars_ref,  7, accent)

    _section_label(sf, "Dificuldade", 8, accent)
    _bool_check(sf, "Override dificuldade oficial",       "enable_difficulty_override",              srv, vars_ref,  9, accent)
    _float_entry(sf,"OverrideOfficialDifficulty",         "override_official_difficulty",            srv, vars_ref, 10)
    _float_entry(sf,"DifficultyOffset",                   "difficulty_offset",                       srv, vars_ref, 11)

    _section_label(sf, "Tribos", 12, accent)
    _int_entry(sf,  "Max membros na tribo",               "max_tribe_size",                          srv, vars_ref, 13)
    _bool_check(sf, "Alianças entre tribos",              "allow_tribe_alliances",                   srv, vars_ref, 14, accent)
    _int_entry(sf,  "Max alianças por tribo",             "max_alliances_per_tribe",                 srv, vars_ref, 15)
    _int_entry(sf,  "Max tribos por aliança",             "max_tribes_per_alliance",                 srv, vars_ref, 16)
    _bool_check(sf, "Guerra tribal PvE",                  "allow_tribe_war_pve",                     srv, vars_ref, 17, accent)
    _bool_check(sf, "Cancelar guerra tribal PvE",         "allow_tribe_war_cancel_pve",              srv, vars_ref, 18, accent)
    _int_entry(sf,  "Cooldown mudança de nome (s)",       "tribe_name_change_cooldown",              srv, vars_ref, 19)

    _section_label(sf, "PvP Respawn", 20, accent)
    _bool_check(sf, "Aumentar intervalo PvP respawn",     "increase_pvp_respawn_interval",           srv, vars_ref, 21, accent)
    _int_entry(sf,  "Check period (s)",                   "pvp_respawn_check_period",                srv, vars_ref, 22)
    _float_entry(sf,"Respawn multiplier",                 "pvp_respawn_multiplier",                  srv, vars_ref, 23)
    _int_entry(sf,  "Base amount",                        "pvp_respawn_base_amount",                 srv, vars_ref, 24)

    _section_label(sf, "PvP Offline", 25, accent)
    _bool_check(sf, "Prevenir PvP offline",               "prevent_pvp_offline",                     srv, vars_ref, 26, accent)
    _int_entry(sf,  "Intervalo offline (s)",              "prevent_pvp_offline_interval",            srv, vars_ref, 27)
    _int_entry(sf,  "Invincible interval (s)",            "prevent_pvp_offline_invincible_interval", srv, vars_ref, 28)

    _section_label(sf, "PvE Auto Timer", 29, accent)
    _bool_check(sf, "Auto PvE Timer",                     "auto_pve_timer",                          srv, vars_ref, 30, accent)
    _bool_check(sf, "Usar hora do sistema",               "auto_pve_use_system_time",                srv, vars_ref, 31, accent)
    _int_entry(sf,  "Início PvE (s desde meia-noite)",   "auto_pve_start_time",                     srv, vars_ref, 32)
    _int_entry(sf,  "Fim PvE (s desde meia-noite)",      "auto_pve_stop_time",                      srv, vars_ref, 33)

    _section_label(sf, "Doenças / Gamma", 34, accent)
    _bool_check(sf, "Doenças habilitadas",                "enable_diseases",                         srv, vars_ref, 35, accent)
    _bool_check(sf, "Doenças não permanentes",            "non_permanent_diseases",                  srv, vars_ref, 36, accent)
    _bool_check(sf, "Gamma PvP",                          "allow_pvp_gamma",                         srv, vars_ref, 37, accent)
    _bool_check(sf, "Gamma PvE",                          "allow_pve_gamma",                         srv, vars_ref, 38, accent)

    _section_label(sf, "Receitas / Stasis", 39, accent)
    _bool_check(sf, "Receitas customizadas",              "allow_custom_recipes",                    srv, vars_ref, 40, accent)
    _float_entry(sf,"Effectiveness multiplier",           "custom_recipe_effectiveness_multiplier",  srv, vars_ref, 41)
    _float_entry(sf,"Skill multiplier",                   "custom_recipe_skill_multiplier",          srv, vars_ref, 42)
    _bool_check(sf, "Override NPC Stasis Range Scale",    "override_npc_stasis_range_scale",         srv, vars_ref, 43, accent)
    _int_entry(sf,  "Player count start",                 "npc_stasis_range_scale_start",            srv, vars_ref, 44)
    _int_entry(sf,  "Player count end",                   "npc_stasis_range_scale_end",              srv, vars_ref, 45)
    _float_entry(sf,"Percent end",                        "npc_stasis_range_scale_percent_end",      srv, vars_ref, 46)

    _section_label(sf, "Miscelânea", 47, accent)
    _float_entry(sf,"Oxygen swim speed stat multiplier",  "oxygen_swim_speed_stat_multiplier",       srv, vars_ref, 48)
    _float_entry(sf,"Supply crate loot quality",          "supply_crate_loot_quality_multiplier",    srv, vars_ref, 49)
    _float_entry(sf,"Fishing loot quality",               "fishing_loot_quality_multiplier",         srv, vars_ref, 50)
    _float_entry(sf,"Corpse life span multiplier",        "use_corpse_life_span_multiplier",         srv, vars_ref, 51)
    _float_entry(sf,"Battery durability decrease/s",      "global_powered_battery_durability_decrease", srv, vars_ref, 52)
    _bool_check(sf, "Random supply crate points",         "random_supply_crate_points",              srv, vars_ref, 53, accent)
    _bool_check(sf, "Corpse locator",                     "use_corpse_locator",                      srv, vars_ref, 54, accent)
    _bool_check(sf, "Prevent spawn animations",           "prevent_spawn_animations",                srv, vars_ref, 55, accent)
    _bool_check(sf, "Allow unlimited respecs",            "allow_unlimited_respecs",                 srv, vars_ref, 56, accent)
    _bool_check(sf, "Allow platform saddle multi floors", "allow_platform_saddle_multi_floors",      srv, vars_ref, 57, accent)

    _add_help(sf, [
        ("PvP / PvE", "Define o modo de jogo principal. Em PvP jogadores podem atacar uns aos outros."),
        ("Hardcore", "Ao morrer, o personagem é resetado ao nível 1. Para servidores competitivos."),
        ("OverrideOfficialDifficulty", "Controla o nível máximo dos dinos selvagens. 5.0 = dinos até nível 150."),
        ("DifficultyOffset", "Modificador adicional de dificuldade (0.0–1.0). Geralmente use 1.0 com OverrideOfficialDifficulty."),
        ("Max membros na tribo", "Limite de jogadores por tribo. 0 = sem limite."),
        ("PvP Offline", "Protege bases quando todos os membros da tribo estão offline."),
        ("Auto PvE Timer", "Alterna automaticamente entre PvP e PvE nos horários configurados (em segundos desde meia-noite)."),
        ("Corpse Locator", "Exibe um marcador no mapa indicando onde você morreu."),
        ("Allow Unlimited Respecs", "Permite resetar atributos com Mindwipe Tonic sem limite de uso."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 6 — Transferências / Tributo
# ════════════════════════════════════════════════════════════════════════════ #

def _build_transfers(sf, srv, vars_ref, bg, accent):
    _section_label(sf, "Downloads / Uploads", 0, accent)
    _bool_check(sf, "Permitir downloads de tributo",        "enable_tribute_downloads",   srv, vars_ref,  1, accent)
    _bool_check(sf, "Bloquear download survivors",          "prevent_download_survivors", srv, vars_ref,  2, accent)
    _bool_check(sf, "Bloquear download items",              "prevent_download_items",     srv, vars_ref,  3, accent)
    _bool_check(sf, "Bloquear download dinos",              "prevent_download_dinos",     srv, vars_ref,  4, accent)
    _bool_check(sf, "Bloquear upload survivors",            "prevent_upload_survivors",   srv, vars_ref,  5, accent)
    _bool_check(sf, "Bloquear upload items",                "prevent_upload_items",       srv, vars_ref,  6, accent)
    _bool_check(sf, "Bloquear upload dinos",                "prevent_upload_dinos",       srv, vars_ref,  7, accent)
    _bool_check(sf, "Permitir dinos de outros clusters",    "cross_ark_allow_foreign_dino_downloads", srv, vars_ref, 8, accent)

    _section_label(sf, "Expiração de Tributo", 9, accent)
    _bool_check(sf, "Salvar expiração de personagens",      "save_tribute_char_expiration",    srv, vars_ref, 10, accent)
    _int_entry(sf,  "Expiração personagem (s)",             "tribute_char_expiration_seconds", srv, vars_ref, 11)
    _bool_check(sf, "Salvar expiração de items",            "save_tribute_item_expiration",    srv, vars_ref, 12, accent)
    _int_entry(sf,  "Expiração items (s)",                  "tribute_item_expiration_seconds", srv, vars_ref, 13)
    _bool_check(sf, "Salvar expiração de dinos",            "save_tribute_dino_expiration",    srv, vars_ref, 14, accent)
    _int_entry(sf,  "Expiração dinos (s)",                  "tribute_dino_expiration_seconds", srv, vars_ref, 15)
    _bool_check(sf, "Intervalo mínimo de re-upload de dinos","save_min_dino_reupload_interval", srv, vars_ref, 16, accent)
    _int_entry(sf,  "Min dino reupload interval (s)",       "min_dino_reupload_interval",      srv, vars_ref, 17)

    _section_label(sf, "Exclusive Join", 18, accent)
    _bool_check(sf, "Exclusive Join (somente whitelist)", "exclusive_join", srv, vars_ref, 19, accent)

    _add_help(sf, [
        ("Downloads / Uploads", "Controla o que pode ser transferido via terminal de obelisco ou tribute."),
        ("Bloquear download/upload", "Impede que survivors, items ou dinos sejam transferidos entre servidores do cluster."),
        ("Expiração de tributo", "Items e dinos no terminal de tribute são automaticamente removidos após o tempo configurado."),
        ("Min Dino Reupload Interval", "Tempo mínimo entre uploads de um mesmo dino (evita abusos de buff reset)."),
        ("Exclusive Join", "Apenas jogadores na whitelist podem entrar. Configure os IDs em Arquivos do Servidor."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 7 — Bate-papo e Notificações
# ════════════════════════════════════════════════════════════════════════════ #

def _build_chat(sf, srv, vars_ref, bg, accent):
    _section_label(sf, "Chat", 0, accent)
    _bool_check(sf, "Voice chat global",          "global_voice_chat",           srv, vars_ref, 1, accent)
    _bool_check(sf, "Proximity chat",             "proximity_chat",              srv, vars_ref, 2, accent)
    _bool_check(sf, "Notificar entrada (join)",   "player_joined_notifications", srv, vars_ref, 3, accent)
    _bool_check(sf, "Notificar saída (leave)",    "player_leave_notifications",  srv, vars_ref, 4, accent)

    _add_help(sf, [
        ("Voice chat global", "Quando ativado, todos os jogadores ouvem o chat de voz, independente da distância."),
        ("Proximity chat", "Apenas jogadores próximos ouvem o chat de voz (modo imersivo)."),
        ("Notificar entrada/saída", "Exibe mensagem no chat do servidor quando um jogador entra ou sai."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 8 — HUD e Visuais
# ════════════════════════════════════════════════════════════════════════════ #

def _build_hud(sf, srv, vars_ref, bg, accent):
    _section_label(sf, "HUD / Visual", 0, accent)
    _bool_check(sf, "Crosshair",                 "allow_crosshair",            srv, vars_ref, 1, accent)
    _bool_check(sf, "HUD habilitado",            "allow_hud",                  srv, vars_ref, 2, accent)
    _bool_check(sf, "Terceira pessoa",           "allow_third_person_view",    srv, vars_ref, 3, accent)
    _bool_check(sf, "Mostrar posição no mapa",   "show_map_player_location",   srv, vars_ref, 4, accent)
    _bool_check(sf, "Floating damage text",      "show_floating_damage_text",  srv, vars_ref, 5, accent)
    _bool_check(sf, "Hit markers",               "allow_hit_markers",          srv, vars_ref, 6, accent)

    _add_help(sf, [
        ("Crosshair", "Exibe a mira (ponto de mira) na tela dos jogadores."),
        ("HUD habilitado", "Exibe barras de vida, stamina, comida e demais indicadores na tela."),
        ("Terceira pessoa", "Permite que os jogadores alternem para câmera em terceira pessoa."),
        ("Mostrar posição no mapa", "Exibe a localização do jogador no mapa do jogo."),
        ("Floating damage text", "Exibe números de dano causado flutuando sobre os alvos."),
        ("Hit markers", "Exibe indicador visual (marcador) quando um acerto é registrado."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Helper — grade de multiplicadores por nível
# ════════════════════════════════════════════════════════════════════════════ #

_STAT_NAMES = [
    ("❤",  "Vida"),
    ("⚡",  "Stamina"),
    ("😴",  "Torpor"),
    ("💧",  "Oxigênio"),
    ("🍖",  "Comida"),
    ("💦",  "Água"),
    ("🌡",  "Temperatura"),
    ("⚖",  "Peso"),
    ("⚔",  "Dano Corpo"),
    ("🏃",  "Velocidade"),
    ("🛡",  "Fortitude"),
    ("🔨",  "Crafting"),
]


def _per_level_grid(sf, row_start, srv, vars_ref, col_defs: list, accent: str) -> None:
    """
    Cria uma grade compacta de multiplicadores por nível.
    col_defs: list de (label_coluna, attr_srv)
    Armazena em vars_ref["_pls"][attr_srv] = list[StringVar]
    """
    if "_pls" not in vars_ref:
        vars_ref["_pls"] = {}

    # Frame container
    gf = ctk.CTkFrame(sf, fg_color="#0a0f1a", corner_radius=8, border_width=1, border_color="#1e293b")
    gf.grid(row=row_start, column=0, columnspan=2, padx=8, pady=(4, 8), sticky="ew")

    # Header
    ctk.CTkLabel(gf, text="Stat", font=ctk.CTkFont(size=10, weight="bold"),
                 text_color="#64748b").grid(row=0, column=0, padx=(10, 4), pady=(6, 2), sticky="w")
    for ci, (col_lbl, _) in enumerate(col_defs):
        ctk.CTkLabel(gf, text=col_lbl, font=ctk.CTkFont(size=9, weight="bold"),
                     text_color=accent, anchor="center").grid(
            row=0, column=ci + 1, padx=4, pady=(6, 2), sticky="ew")

    ctk.CTkFrame(gf, height=1, fg_color="#1e293b").grid(
        row=1, column=0, columnspan=len(col_defs) + 1, sticky="ew", padx=4)

    # Linhas de stats
    for ri, (icon, stat_name) in enumerate(_STAT_NAMES):
        row_bg = "#080d16" if ri % 2 == 0 else "#0a0f1a"
        row_f = ctk.CTkFrame(gf, fg_color=row_bg, corner_radius=0)
        row_f.grid(row=ri + 2, column=0, columnspan=len(col_defs) + 1, sticky="ew")
        row_f.grid_columnconfigure(0, weight=0)
        for ci in range(len(col_defs)):
            row_f.grid_columnconfigure(ci + 1, weight=1)

        ctk.CTkLabel(row_f, text=f"{icon}  {stat_name}",
                     font=ctk.CTkFont(size=11), text_color="#94a3b8",
                     anchor="w", width=110).grid(
            row=0, column=0, padx=(10, 8), pady=2, sticky="w")

        for ci, (_, attr) in enumerate(col_defs):
            if attr not in vars_ref["_pls"]:
                cur_list = getattr(srv, attr, None) or []
                vars_ref["_pls"][attr] = [
                    tk.StringVar(value=str(cur_list[i]) if i < len(cur_list) else "1.0")
                    for i in range(12)
                ]
            ctk.CTkEntry(row_f, textvariable=vars_ref["_pls"][attr][ri],
                         width=70, height=24, font=ctk.CTkFont(size=11),
                         justify="center").grid(row=0, column=ci + 1, padx=4, pady=2, sticky="ew")


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 9 — Configurações do Jogador
# ════════════════════════════════════════════════════════════════════════════ #

def _build_players(sf, srv, vars_ref, bg, accent):
    _section_label(sf, "Multiplicadores", 0, accent)
    _float_entry(sf,"XP Multiplier",                  "xp_multiplier",                       srv, vars_ref,  1)
    _float_entry(sf,"Player Damage",                  "player_damage_multiplier",            srv, vars_ref,  2)
    _float_entry(sf,"Player Resistance",              "player_resistance_multiplier",        srv, vars_ref,  3)
    _float_entry(sf,"Water Drain",                    "player_water_drain_multiplier",       srv, vars_ref,  4)
    _float_entry(sf,"Food Drain",                     "player_food_drain_multiplier",        srv, vars_ref,  5)
    _float_entry(sf,"Stamina Drain",                  "player_stamina_drain_multiplier",     srv, vars_ref,  6)
    _float_entry(sf,"Health Recovery",                "player_health_recovery_multiplier",   srv, vars_ref,  7)
    _float_entry(sf,"Harvesting Damage",              "player_harvesting_damage_multiplier", srv, vars_ref,  8)
    _float_entry(sf,"Crafting Skill Bonus",           "crafting_skill_bonus_multiplier",     srv, vars_ref,  9)

    _section_label(sf, "XP por Tipo", 10, accent)
    _float_entry(sf,"Craft XP",                       "craft_xp_multiplier",                srv, vars_ref, 11)
    _float_entry(sf,"Generic XP",                     "generic_xp_multiplier",              srv, vars_ref, 12)
    _float_entry(sf,"Harvest XP",                     "harvest_xp_multiplier",              srv, vars_ref, 13)
    _float_entry(sf,"Kill XP",                        "kill_xp_multiplier",                 srv, vars_ref, 14)
    _float_entry(sf,"Special XP",                     "special_xp_multiplier",              srv, vars_ref, 15)

    _section_label(sf, "Limites / Opções", 16, accent)
    _int_entry(sf,  "Max XP jogador (0=padrão)",      "override_max_xp_player",             srv, vars_ref, 17)
    _bool_check(sf, "Allow Flyer Carry PvE",          "enable_flyer_carry",                 srv, vars_ref, 18, accent)

    _section_label(sf, "Multiplicadores por Nível (Jogador)", 19, accent)
    ctk.CTkLabel(sf, text="Quanto cada atributo cresce por ponto aplicado pelo jogador (1.0 = padrão)",
                 font=ctk.CTkFont(size=10), text_color="#64748b").grid(
        row=20, column=0, columnspan=2, padx=8, pady=(0, 2), sticky="w")
    _per_level_grid(sf, 21, srv, vars_ref,
                    [("Pts/nível", "per_level_player")],
                    accent)

    _add_help(sf, [
        ("Multipliers de jogador (1.0 = vanilla)", "Valores acima de 1.0 aumentam o atributo; abaixo diminuem. Não afeta atributos já investidos."),
        ("XP Multiplier", "Multiplicador geral de XP. Outros XP (Craft, Kill, Harvest) são multiplicados adicionalmente sobre este."),
        ("Max XP (0 = padrão)", "Cap de XP máximo atingível pelo jogador. 0 usa o padrão do jogo."),
        ("Pts/nível", "Quanto cada atributo cresce por ponto investido pelo jogador. 1.0 = vanilla."),
        ("Allow Flyer Carry PvE", "Permite que pterodatos e outros voadores carreguem outros dinos em PvE."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 10 — Configurações do Dino
# ════════════════════════════════════════════════════════════════════════════ #

def _build_dinos(sf, srv, vars_ref, bg, accent):
    _section_label(sf, "Dano e Resistência", 0, accent)
    _float_entry(sf,"Dino Damage",                    "dino_damage_multiplier",              srv, vars_ref,  1)
    _float_entry(sf,"Tamed Dino Damage",              "tamed_dino_damage_multiplier",        srv, vars_ref,  2)
    _float_entry(sf,"Dino Resistance",                "dino_resistance_multiplier",          srv, vars_ref,  3)
    _float_entry(sf,"Tamed Dino Resistance",          "tamed_dino_resistance_multiplier",    srv, vars_ref,  4)
    _float_entry(sf,"Dino Turret Damage",             "dino_turret_damage_multiplier",       srv, vars_ref,  5)
    _float_entry(sf,"Dino Harvesting Damage",         "dino_harvesting_damage_multiplier",   srv, vars_ref,  6)

    _section_label(sf, "Sobrevivência do Dino", 7, accent)
    _float_entry(sf,"Dino Food Drain",                "dino_char_food_drain_multiplier",          srv, vars_ref,  8)
    _float_entry(sf,"Dino Stamina Drain",             "dino_char_stamina_drain_multiplier",        srv, vars_ref,  9)
    _float_entry(sf,"Dino Health Recovery",           "dino_char_health_recovery_multiplier",      srv, vars_ref, 10)
    _float_entry(sf,"Wild Dino Food Drain",           "wild_dino_char_food_drain_multiplier",      srv, vars_ref, 11)
    _float_entry(sf,"Tamed Dino Food Drain",          "tamed_dino_char_food_drain_multiplier",     srv, vars_ref, 12)
    _float_entry(sf,"Wild Dino Torpor Drain",         "wild_dino_torpor_drain_multiplier",         srv, vars_ref, 13)
    _float_entry(sf,"Tamed Dino Torpor Drain",        "tamed_dino_torpor_drain_multiplier",        srv, vars_ref, 14)

    _section_label(sf, "Gestão de Dinos", 15, accent)
    _int_entry(sf,  "Max Tamed Dinos",                "max_tamed_dinos",                           srv, vars_ref, 16)
    _float_entry(sf,"Dino Count Multiplier",          "dino_count_multiplier",                     srv, vars_ref, 17)
    _float_entry(sf,"Taming Speed",                   "taming_speed_multiplier",                   srv, vars_ref, 18)
    _float_entry(sf,"Passive Tame Interval",          "passive_tame_interval_multiplier",          srv, vars_ref, 19)
    _float_entry(sf,"Max Personal Tamed Dinos",       "max_personal_tamed_dinos",                  srv, vars_ref, 20)
    _int_entry(sf,  "Personal saddle structure cost", "personal_tamed_dinos_saddle_structure_cost",srv, vars_ref, 21)
    _int_entry(sf,  "Max XP dino (0=padrão)",         "override_max_xp_dino",                      srv, vars_ref, 22)
    _float_entry(sf,"PvE Dino Decay Period",          "pve_dino_decay_period_multiplier",          srv, vars_ref, 23)
    _float_entry(sf,"Raid Dino Food Drain",           "raid_dino_food_drain_multiplier",           srv, vars_ref, 24)

    _section_label(sf, "Opções", 25, accent)
    _bool_check(sf, "Allow Raid Dino Feeding",        "allow_raid_dino_feeding",            srv, vars_ref, 26, accent)
    _bool_check(sf, "Allow Flying Stamina Recovery",  "allow_flying_stamina_recovery",      srv, vars_ref, 27, accent)
    _bool_check(sf, "Prevent Mate Boost",             "prevent_mate_boost",                 srv, vars_ref, 28, accent)
    _bool_check(sf, "Disable Dino Decay PvE",         "disable_dino_decay_pve",             srv, vars_ref, 29, accent)
    _bool_check(sf, "PvP Dino Decay",                 "pvp_dino_decay",                     srv, vars_ref, 30, accent)
    _bool_check(sf, "Auto Destroy Decayed Dinos",     "auto_destroy_decayed_dinos",         srv, vars_ref, 31, accent)
    _bool_check(sf, "Allow Multiple Attached C4",     "allow_multiple_attached_c4",         srv, vars_ref, 32, accent)
    _bool_check(sf, "Disable Dino Riding",            "disable_dino_riding",                srv, vars_ref, 33, accent)
    _bool_check(sf, "Disable Dino Taming",            "disable_dino_taming",                srv, vars_ref, 34, accent)
    _bool_check(sf, "Use Tame Limit For Structures Only","use_tame_limit_for_structures_only", srv, vars_ref, 35, accent)
    _bool_check(sf, "Disable Imprint Buff",           "disable_imprint_buff",               srv, vars_ref, 36, accent)
    _bool_check(sf, "Allow Anyone Baby Imprint",      "allow_anyone_baby_imprint",          srv, vars_ref, 37, accent)

    _section_label(sf, "Multiplicadores por Nível (Dino)", 38, accent)
    ctk.CTkLabel(sf, text="Wild = selvagem  •  Dom. = domesticado base  •  +Add = bônus fixo por nível  •  +Afi = bônus de afinidade",
                 font=ctk.CTkFont(size=10), text_color="#64748b").grid(
        row=39, column=0, columnspan=2, padx=8, pady=(0, 2), sticky="w")
    _per_level_grid(sf, 40, srv, vars_ref,
                    [
                        ("Wild",   "per_level_dino_wild"),
                        ("Dom.",   "per_level_dino_tamed"),
                        ("+Add",   "per_level_dino_tamed_add"),
                        ("+Afi",   "per_level_dino_tamed_affinity"),
                    ],
                    accent)

    _add_help(sf, [
        ("Dino Damage / Resistance", "Afeta todos os dinos (selvagens e domesticados). 1.5 = 50% mais dano/resistência."),
        ("Max Tamed Dinos", "Limite global de dinos domesticados no servidor. Recomendado: 300–500 para evitar lag."),
        ("Taming Speed", "Multiplica a velocidade de domesticação. >1.0 = mais rápido; <1.0 = mais lento."),
        ("Imprint Buff", "Multiplica o bônus de imprinting. Apenas dinos com 100% de imprint têm efeito máximo."),
        ("Wild / Dom. / +Add / +Afi", "Multiplicadores de atributo por nível: Wild (selvagem), Dom. (domesticado), +Add (bnus adicional) e +Afi (afinidade)."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 11 — Reprodução
# ════════════════════════════════════════════════════════════════════════════ #

def _build_breeding(sf, srv, vars_ref, bg, accent):
    _section_label(sf, "Reprodução e Imprinting", 0, accent)
    _float_entry(sf,"Mating Interval",                "mating_interval_multiplier",                          srv, vars_ref, 1)
    _float_entry(sf,"Egg Hatch Speed",                "egg_hatch_speed_multiplier",                          srv, vars_ref, 2)
    _float_entry(sf,"Baby Mature Speed",              "baby_mature_speed_multiplier",                        srv, vars_ref, 3)
    _float_entry(sf,"Baby Food Consumption",          "baby_food_consumption_multiplier",                    srv, vars_ref, 4)
    _float_entry(sf,"Baby Cuddle Interval",           "baby_cuddle_interval_multiplier",                     srv, vars_ref, 5)
    _float_entry(sf,"Baby Cuddle Grace Period",       "baby_cuddle_grace_period_multiplier",                 srv, vars_ref, 6)
    _float_entry(sf,"Baby Cuddle Lose Imprint Speed", "baby_cuddle_lose_imprint_quality_speed_multiplier",   srv, vars_ref, 7)
    _float_entry(sf,"Baby Imprinting Stat Scale",     "baby_imprinting_stat_scale",                          srv, vars_ref, 8)

    # — Calculadora de Breeding —
    ctk.CTkFrame(sf, height=1, fg_color="#1e293b").grid(
        row=9, column=0, columnspan=2, sticky="ew", padx=8, pady=(10, 6))

    def _open_calc():
        from ..breeding_calculator import open_breeding_calculator
        widgets = {f"gs_{k}": v for k, v in vars_ref.items() if not k.startswith("_")}
        def on_apply():
            # reflecte os valores calculados de volta nas StringVars do painel
            for attr in ("baby_mature_speed_multiplier", "egg_hatch_speed_multiplier",
                         "mating_interval_multiplier", "baby_cuddle_interval_multiplier"):
                sv = vars_ref.get(attr)
                if sv is not None:
                    sv.set(str(getattr(srv, attr, 1.0)))
        open_breeding_calculator(sf, srv, widgets, on_apply)

    ctk.CTkButton(
        sf, text="🧠  Calculadora de Breeding",
        width=220, height=36,
        fg_color="#1e293b", hover_color="#0f172a",
        text_color="#22c55e", border_width=1, border_color="#22c55e",
        corner_radius=8, font=ctk.CTkFont(size=12, weight="bold"),
        command=_open_calc,
    ).grid(row=10, column=0, columnspan=2, padx=8, pady=(0, 10), sticky="w")

    _add_help(sf, [
        ("Mating Interval", "Intervalo entre acasalamentos. <1.0 = mais frequente; 0.1 = 10x mais rápido que o padrão."),
        ("Egg Hatch Speed", "Velocidade de chocagem de ovos. >1.0 = mais rápido."),
        ("Baby Mature Speed", "Velocidade de crescimento do bebê. >1.0 = mais rápido."),
        ("Baby Cuddle Interval", "Intervalo entre carinhos no bebê para imprinting. <1.0 = mais frequente."),
        ("Baby Imprinting Stat Scale", "Multiplica o bônus de atributo conferido pelo imprinting."),
        ("Calculadora de Breeding", "Ferramenta para calcular automaticamente os multiplicadores ideais para seu servidor."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 12 — Meio Ambiente
# ════════════════════════════════════════════════════════════════════════════ #

def _build_environment(sf, srv, vars_ref, bg, accent):
    _section_label(sf, "Coleta e Recursos", 0, accent)
    _float_entry(sf,"Harvest Amount",                 "harvest_amount_multiplier",                   srv, vars_ref,  1)
    _float_entry(sf,"Harvest Health",                 "harvest_health_multiplier",                   srv, vars_ref,  2)
    _float_entry(sf,"Resources Respawn",              "resources_respawn_multiplier",                srv, vars_ref,  3)
    _float_entry(sf,"No Replenish Radius (Players)",  "resource_no_replenish_radius_players",        srv, vars_ref,  4)
    _float_entry(sf,"No Replenish Radius (Structures)","resource_no_replenish_radius_structures",   srv, vars_ref,  5)
    _bool_check(sf, "Use Optimized Harvesting Health","use_optimized_harvesting_health",             srv, vars_ref,  6, accent)
    _bool_check(sf, "Clamp Resource Harvest Damage",  "clamp_resource_harvest_damage",              srv, vars_ref,  7, accent)

    _section_label(sf, "Tempo / Clima", 8, accent)
    _float_entry(sf,"Day Cycle Speed",                "day_cycle_speed_scale",                       srv, vars_ref,  9)
    _float_entry(sf,"Day Time Speed",                 "day_time_speed_scale",                        srv, vars_ref, 10)
    _float_entry(sf,"Night Time Speed",               "night_time_speed_scale",                      srv, vars_ref, 11)
    _float_entry(sf,"Base Temperature",               "base_temperature_multiplier",                 srv, vars_ref, 12)
    _bool_check(sf, "Disable Weather Fog",            "disable_weather_fog",                         srv, vars_ref, 13, accent)

    _section_label(sf, "Decomposição / Spoiling", 14, accent)
    _float_entry(sf,"Global Spoiling Time",           "global_spoiling_time_multiplier",             srv, vars_ref, 15)
    _float_entry(sf,"Item Decomposition Time",        "global_item_decomposition_multiplier",        srv, vars_ref, 16)
    _float_entry(sf,"Corpse Decomposition Time",      "global_corpse_decomposition_multiplier",      srv, vars_ref, 17)
    _bool_check(sf, "Clamp Item Spoiling Times",      "clamp_item_spoiling_times",                   srv, vars_ref, 18, accent)

    _section_label(sf, "Agricultura / Criaturas", 19, accent)
    _float_entry(sf,"Crop Decay Speed",               "crop_decay_speed_multiplier",                 srv, vars_ref, 20)
    _float_entry(sf,"Crop Growth Speed",              "crop_growth_speed_multiplier",                srv, vars_ref, 21)
    _float_entry(sf,"Lay Egg Interval",               "lay_egg_interval_multiplier",                 srv, vars_ref, 22)
    _float_entry(sf,"Poop Interval",                  "poop_interval_multiplier",                    srv, vars_ref, 23)
    _float_entry(sf,"Hair Growth Speed",              "hair_growth_speed_multiplier",                srv, vars_ref, 24)

    _add_help(sf, [
        ("Harvest Amount", "Quantidade de recursos coletados por golpe. 2.0 = coleta dupla."),
        ("Resources Respawn", "Velocidade de reaparecer dos recursos no mapa. <1.0 = mais rápido."),
        ("Day/Night Cycle Speed", "Velocidade do ciclo dia/noite. >1.0 = dias/noites mais curtos."),
        ("Global Spoiling Time", "Multiplica o tempo de estrago dos itens. >1.0 = itens duram mais."),
        ("Corpse Decomposition", "Quanto tempo um corpo fica no mapa antes de desaparecer."),
        ("Crop Growth / Decay", "Velocidade de crescimento e deterioração das plantações."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 13 — Estruturas
# ════════════════════════════════════════════════════════════════════════════ #

def _build_structures(sf, srv, vars_ref, bg, accent):
    _section_label(sf, "Dano e Resistência", 0, accent)
    _float_entry(sf,"Structure Resistance",              "structure_resistance_multiplier",         srv, vars_ref,  1)
    _float_entry(sf,"Structure Damage",                  "structure_damage_multiplier",             srv, vars_ref,  2)
    _int_entry(sf,  "Damage Repair Cooldown (s)",        "structure_damage_repair_cooldown",        srv, vars_ref,  3)
    _bool_check(sf, "PvP Structure Decay",               "pvp_structure_decay",                     srv, vars_ref,  4, accent)
    _float_entry(sf,"PvP Zone Structure Damage",         "pvp_zone_structure_damage_multiplier",    srv, vars_ref,  5)

    _section_label(sf, "Limites", 6, accent)
    _int_entry(sf,  "Max Structures In Range",           "max_structures_in_range",                 srv, vars_ref,  7)
    _float_entry(sf,"Per Platform Max Structures",       "per_platform_max_structures_multiplier",  srv, vars_ref,  8)
    _int_entry(sf,  "Max Platform Saddle Structures",    "max_platform_saddle_structures",          srv, vars_ref,  9)
    _bool_check(sf, "Override Structure Platform Prevention","override_structure_platform_prevention",srv,vars_ref, 10, accent)
    _bool_check(sf, "Flyer Platform Allow Unaligned Dino Basing","flyer_platform_allow_unaligned_dino_basing",srv,vars_ref,11,accent)

    _section_label(sf, "Decay PvE", 12, accent)
    _bool_check(sf, "Enable Structure Decay PvE",        "enable_structure_decay_pve",              srv, vars_ref, 13, accent)
    _float_entry(sf,"PvE Structure Decay Period",        "pve_structure_decay_period_multiplier",   srv, vars_ref, 14)
    _float_entry(sf,"PvE Structure Decay Destruction",   "pve_structure_decay_destruction_period",  srv, vars_ref, 15)
    _float_entry(sf,"Auto Destroy Old Structures",       "auto_destroy_old_structures_multiplier",  srv, vars_ref, 16)
    _bool_check(sf, "PvE Allow Structures At Supply Drops","pve_allow_structures_at_supply_drops",  srv, vars_ref, 17, accent)

    _section_label(sf, "Opções", 18, accent)
    _bool_check(sf, "Force All Structure Locking",       "force_all_structure_locking",             srv, vars_ref, 19, accent)
    _bool_check(sf, "Disable Structure Placement Collision","disable_structure_placement_collision", srv, vars_ref, 20, accent)
    _bool_check(sf, "Only Auto Destroy Core Structures", "only_auto_destroy_core_structures",       srv, vars_ref, 21, accent)
    _bool_check(sf, "Only Decay Unsnapped Core Structures","only_decay_unsnapped_core_structures",  srv, vars_ref, 22, accent)
    _bool_check(sf, "Fast Decay Unsnapped Core Structures","fast_decay_unsnapped_core_structures",  srv, vars_ref, 23, accent)
    _bool_check(sf, "Destroy Unconnected Water Pipes",   "destroy_unconnected_water_pipes",         srv, vars_ref, 24, accent)
    _bool_check(sf, "Passive Defenses Damage Riderless Dinos","passive_defenses_damage_riderless_dinos",srv,vars_ref,25,accent)
    _bool_check(sf, "Enable Fast Decay Interval",        "enable_fast_decay_interval",              srv, vars_ref, 26, accent)
    _int_entry(sf,  "Fast Decay Interval (s)",           "fast_decay_interval",                     srv, vars_ref, 27)

    _section_label(sf, "Torretas", 28, accent)
    _bool_check(sf, "Limit Turrets In Range",             "limit_turrets_in_range",                 srv, vars_ref, 29, accent)
    _int_entry(sf,  "Turrets Range",                      "limit_turrets_range",                    srv, vars_ref, 30)
    _int_entry(sf,  "Turrets Num",                        "limit_turrets_num",                      srv, vars_ref, 31)
    _bool_check(sf, "Hard Limit Turrets In Range",        "hard_limit_turrets_in_range",            srv, vars_ref, 32, accent)

    _add_help(sf, [
        ("Structure Resistance / Damage", "Multiplica dano recebido / causado por estruturas. 1.0 = vanilla."),
        ("Max Structures In Range", "Limite de estruturas em determinado raio. Reduz lag em servidores com muitas bases."),
        ("Decay PvE", "Estruturas sem acesso regular são removidas automaticamente (evita bases abandonadas)."),
        ("Turrets In Range", "Limita o número de torretas em um raio. Recomendado para reduzir lag em cercos."),
        ("Force All Structure Locking", "Todas as estruturas são trancadas por padrão ao serem construídas."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 14 — Engramas
# ════════════════════════════════════════════════════════════════════════════ #

def _build_engrams(sf, srv, vars_ref, bg, accent):
    _section_label(sf, "Opções de Engrama", 0, accent)
    _bool_check(sf, "Only Allow Specified Engrams", "only_allow_specified_engrams", srv, vars_ref, 1, accent)
    _bool_check(sf, "Auto Unlock All Engrams",      "auto_unlock_all_engrams",      srv, vars_ref, 2, accent)

    # Botão para abrir editor visual
    app = vars_ref.get("_app")
    if app:
        th = get_theme("tek")
        ctk.CTkButton(
            sf, text="🎓 Abrir Editor Visual de Engramas", height=30,
            fg_color=th["accent_muted_bg"], hover_color="#052e16",
            border_width=1, border_color=th["accent"], text_color=th["accent"],
            font=ctk.CTkFont(size=11),
            command=lambda: app._asm_open_engram_editor(srv),
        ).grid(row=3, column=0, columnspan=2, padx=8, pady=(6, 4), sticky="w")

    _section_label(sf, "Override de Engramas (Game.ini)", 4, accent)
    ctk.CTkLabel(sf, text="Cole OverrideNamedEngramEntries=(...) — um por linha",
                 font=ctk.CTkFont(size=10), text_color="#7ab8c8").grid(
        row=5, column=0, columnspan=2, padx=8, pady=(0, 2), sticky="w")
    box = ctk.CTkTextbox(sf, height=300, font=ctk.CTkFont(family="Consolas", size=10))
    box.grid(row=6, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")
    box.insert("1.0", srv.engram_entries_raw)
    vars_ref["_raw_engram_entries_raw"] = box

    _add_help(sf, [
        ("Only Allow Specified Engrams", "Bloqueia todos os engramas padrão; apenas os listados aqui estão disponíveis."),
        ("Auto Unlock All Engrams", "Desbloqueia todos os engramas automaticamente ao subir de nível."),
        ("Override de Engramas", "Formato: OverrideNamedEngramEntries=(EngramClassName=\"...\",EngramHidden=False,EngramPointsCost=0,bGiveBlueprint=False,RemoveEngramPreReq=False)"),
        ("Editor Visual", "Use o botão acima para abrir o editor visual que gera os entries automaticamente."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 15 — Arquivos do Servidor
# ════════════════════════════════════════════════════════════════════════════ #

def _build_server_files(sf, srv, vars_ref, bg, accent):
    data = [
        ("IDs de Admin (SteamIDs, um por linha)", "_admin_ids_text",     srv.admin_ids),
        ("IDs Whitelist (um por linha)",           "_whitelist_ids_text",  srv.whitelist_ids),
        ("IDs Exclusive Join (um por linha)",      "_exclusive_ids_text",  srv.exclusive_join_ids),
    ]
    r = 0
    for title, key, items in data:
        _section_label(sf, title, r, accent)
        r += 1
        box = ctk.CTkTextbox(sf, height=80, font=ctk.CTkFont(size=11))
        box.grid(row=r, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="ew")
        box.insert("1.0", "\n".join(items))
        vars_ref[key] = box
        r += 1

    _add_help(sf, [
        ("IDs de Admin", "SteamIDs dos administradores do servidor (um por linha). Esses jogadores têm acesso a comandos admin sem senha."),
        ("IDs Whitelist", "SteamIDs permitidos. Usado junto com Exclusive Join para restringir o acesso ao servidor."),
        ("IDs Exclusive Join", "SteamIDs com acesso exclusivo quando Exclusive Join está ativado na seção Transferências."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 16 — Progressões de Nível
# ════════════════════════════════════════════════════════════════════════════ #

def _build_level_progressions(sf, srv, vars_ref, bg, accent):
    import tkinter as tk

    # ── Helper: gera linhas Game.ini para jogador ─────────────────────────────
    def _gen_player_lines(max_lvl: int, xp_base: int, xp_mult: float, engrams: int) -> str:
        lines = []
        for i in range(max_lvl):
            xp = int(xp_base * (xp_mult ** i))
            lines.append(f"LevelExperienceRampOverrides=(ExperiencePointsForLevel[{i}]={xp})")
        for _ in range(max_lvl):
            lines.append(f"OverridePlayerLevelEngramPoints={engrams}")
        return "\n".join(lines)

    # ── Helper: gera linhas Game.ini para dino ────────────────────────────────
    def _gen_dino_lines(max_lvl: int, xp_base: int, xp_mult: float) -> str:
        lines = []
        for i in range(max_lvl):
            xp = int(xp_base * (xp_mult ** i))
            lines.append(f"DinoMaxLevelExperienceRampOverrides=(ExperiencePointsForLevel[{i}]={xp})")
        return "\n".join(lines)

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    _section_label(sf, "Override de Nível do Jogador (Game.ini)", 0, accent)
    ctk.CTkLabel(sf,
        text="LevelExperienceRampOverrides=(ExperiencePointsForLevel[0]=...) e OverridePlayerLevelEngramPoints=...",
        font=ctk.CTkFont(size=10), text_color="#7ab8c8", wraplength=520).grid(
        row=1, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="w")

    # ── Gerador de Níveis — Jogador ───────────────────────────────────────────
    gen_card = ctk.CTkFrame(sf, fg_color="#0d1b2a", corner_radius=8)
    gen_card.grid(row=2, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")
    gen_card.grid_columnconfigure((1, 3, 5, 7), weight=1)

    ctk.CTkLabel(gen_card, text="⚡ Gerador rápido",
                 font=ctk.CTkFont(size=11, weight="bold"),
                 text_color=accent).grid(row=0, column=0, columnspan=8,
                 padx=12, pady=(8, 4), sticky="w")

    _fields_p = [
        ("Nível máx.", "100"), ("XP base (lv0)", "70"),
        ("Multiplicador XP", "1.15"), ("Engrams/nível", "8"),
    ]
    _vars_p: list[tk.StringVar] = []
    for col, (lbl, default) in enumerate(_fields_p):
        ctk.CTkLabel(gen_card, text=lbl, font=ctk.CTkFont(size=10),
                     text_color="#8899aa").grid(row=1, column=col * 2, padx=(12, 2), pady=(0, 4), sticky="e")
        v = tk.StringVar(value=default)
        _vars_p.append(v)
        ctk.CTkEntry(gen_card, textvariable=v, width=80, height=28).grid(
            row=1, column=col * 2 + 1, padx=(0, 8), pady=(0, 4), sticky="w")

    # ── Preview + Gráfico de curva XP ────────────────────────────────────────
    preview_frame = ctk.CTkFrame(gen_card, fg_color="#060d14", corner_radius=6)
    preview_frame.grid(row=2, column=0, columnspan=8, padx=12, pady=(0, 6), sticky="ew")
    preview_frame.grid_columnconfigure(0, weight=3)
    preview_frame.grid_columnconfigure(1, weight=2)

    # Textbox de preview (primeiras/últimas 5 linhas)
    preview_box = ctk.CTkTextbox(
        preview_frame, height=90, state="disabled",
        font=ctk.CTkFont(family="Consolas", size=9),
        fg_color="#060d14", text_color="#94a3b8",
    )
    preview_box.grid(row=0, column=0, padx=(6, 4), pady=6, sticky="ew")

    # Canvas para mini gráfico de curva
    canvas_xp = tk.Canvas(preview_frame, width=200, height=90,
                          bg="#060d14", highlightthickness=0)
    canvas_xp.grid(row=0, column=1, padx=(0, 6), pady=6, sticky="e")

    def _draw_xp_curve(xp_vals: list, canvas: tk.Canvas):
        canvas.delete("all")
        if not xp_vals:
            return
        w, h = 200, 90
        pad = 8
        max_xp = max(xp_vals) or 1
        pts = []
        n = len(xp_vals)
        for i, xp in enumerate(xp_vals):
            x = pad + (w - 2 * pad) * i / max(n - 1, 1)
            y = h - pad - (h - 2 * pad) * (xp / max_xp)
            pts.append((x, y))
        if len(pts) >= 2:
            flat = [c for p in pts for c in p]
            canvas.create_line(*flat, fill="#22c55e", width=1, smooth=True)
        # Eixos
        canvas.create_line(pad, h - pad, w - pad, h - pad, fill="#1e293b", width=1)
        canvas.create_line(pad, pad, pad, h - pad, fill="#1e293b", width=1)

    def _apply_player_gen():
        try:
            max_lvl = max(1, min(int(_vars_p[0].get()), 500))
            xp_base = max(1, int(_vars_p[1].get()))
            xp_mult = max(1.0, float(_vars_p[2].get()))
            engrams = max(0, int(_vars_p[3].get()))
        except ValueError:
            return
        text = _gen_player_lines(max_lvl, xp_base, xp_mult, engrams)
        box_p.configure(state="normal")
        box_p.delete("1.0", "end")
        box_p.insert("1.0", text)

        # Atualiza preview
        all_lines = text.splitlines()
        if len(all_lines) > 12:
            shown = all_lines[:6] + ["  ..."] + all_lines[-3:]
        else:
            shown = all_lines
        preview_box.configure(state="normal")
        preview_box.delete("1.0", "end")
        preview_box.insert("1.0", "\n".join(shown))
        preview_box.configure(state="disabled")

        # Atualiza gráfico
        xp_vals = [int(xp_base * (xp_mult ** i)) for i in range(max_lvl)]
        _draw_xp_curve(xp_vals, canvas_xp)

    ctk.CTkButton(gen_card, text="Gerar e aplicar",
                  height=28, fg_color="#0e4a6e", hover_color="#0a3550",
                  font=ctk.CTkFont(size=11),
                  command=_apply_player_gen).grid(
        row=3, column=0, columnspan=8, padx=12, pady=(0, 8), sticky="w")

    # ── Textbox raw ───────────────────────────────────────────────────────────
    box_p = ctk.CTkTextbox(sf, height=180, font=ctk.CTkFont(family="Consolas", size=10))
    box_p.grid(row=3, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")
    box_p.insert("1.0", srv.player_level_stats_raw)
    vars_ref["_raw_player_level_stats_raw"] = box_p

    # ── Dino ──────────────────────────────────────────────────────────────────
    _section_label(sf, "Override de Nível do Dino (Game.ini)", 4, accent)
    ctk.CTkLabel(sf,
        text="DinoMaxLevelExperienceRampOverrides=(...)",
        font=ctk.CTkFont(size=10), text_color="#7ab8c8").grid(
        row=5, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="w")

    # ── Gerador de Níveis — Dino ──────────────────────────────────────────────
    gen_card_d = ctk.CTkFrame(sf, fg_color="#0d1b2a", corner_radius=8)
    gen_card_d.grid(row=6, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")
    gen_card_d.grid_columnconfigure((1, 3, 5), weight=1)

    ctk.CTkLabel(gen_card_d, text="⚡ Gerador rápido",
                 font=ctk.CTkFont(size=11, weight="bold"),
                 text_color=accent).grid(row=0, column=0, columnspan=6,
                 padx=12, pady=(8, 4), sticky="w")

    _fields_d = [
        ("Nível máx.", "150"), ("XP base (lv0)", "50"), ("Multiplicador XP", "1.12"),
    ]
    _vars_d: list[tk.StringVar] = []
    for col, (lbl, default) in enumerate(_fields_d):
        ctk.CTkLabel(gen_card_d, text=lbl, font=ctk.CTkFont(size=10),
                     text_color="#8899aa").grid(row=1, column=col * 2, padx=(12, 2), pady=(0, 4), sticky="e")
        v = tk.StringVar(value=default)
        _vars_d.append(v)
        ctk.CTkEntry(gen_card_d, textvariable=v, width=80, height=28).grid(
            row=1, column=col * 2 + 1, padx=(0, 8), pady=(0, 4), sticky="w")

    def _apply_dino_gen():
        try:
            max_lvl = max(1, min(int(_vars_d[0].get()), 500))
            xp_base = max(1, int(_vars_d[1].get()))
            xp_mult = max(1.0, float(_vars_d[2].get()))
        except ValueError:
            return
        text = _gen_dino_lines(max_lvl, xp_base, xp_mult)
        box_d.configure(state="normal")
        box_d.delete("1.0", "end")
        box_d.insert("1.0", text)

    ctk.CTkButton(gen_card_d, text="Gerar e aplicar",
                  height=28, fg_color="#0e4a6e", hover_color="#0a3550",
                  font=ctk.CTkFont(size=11),
                  command=_apply_dino_gen).grid(
        row=2, column=0, columnspan=6, padx=12, pady=(0, 8), sticky="w")

    # ── Textbox raw dino ──────────────────────────────────────────────────────
    box_d = ctk.CTkTextbox(sf, height=150, font=ctk.CTkFont(family="Consolas", size=10))
    box_d.grid(row=7, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")
    box_d.insert("1.0", srv.dino_level_stats_raw)
    vars_ref["_raw_dino_level_stats_raw"] = box_d

    _add_help(sf, [
        ("LevelExperienceRampOverrides", "Define quanto XP é necessário para cada nível do jogador. Um item por nível."),
        ("OverridePlayerLevelEngramPoints", "Quantidade de pontos de engrama ganhos em cada nível. Um item por nível."),
        ("DinoMaxLevelExperienceRampOverrides", "Define a tabela de XP dos dinos. Um item por nível."),
        ("Gerador rápido", "Calcula automaticamente os valores com base em nível máximo, XP base e multiplicador."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 17 — Substituições de Crafting
# ════════════════════════════════════════════════════════════════════════════ #

def _build_crafting_overrides(sf, srv, vars_ref, bg, accent):
    import tkinter as tk
    _section_label(sf, "Substituições de Crafting (Game.ini)", 0, accent)
    ctk.CTkLabel(sf,
        text="Cole ConfigOverrideItemCraftingCosts=(...) do Game.ini",
        font=ctk.CTkFont(size=10), text_color="#7ab8c8").grid(
        row=1, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="w")

    # ── Gerador rápido ────────────────────────────────────────────────────────
    gen = ctk.CTkFrame(sf, fg_color="#0d1b2a", corner_radius=8)
    gen.grid(row=2, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")
    gen.grid_columnconfigure((1, 3, 5), weight=1)

    ctk.CTkLabel(gen, text="⚡ Gerador rápido",
                 font=ctk.CTkFont(size=11, weight="bold"),
                 text_color=accent).grid(row=0, column=0, columnspan=8, padx=12, pady=(8, 4), sticky="w")

    lbl_cfg = [("Item a craftar (ex: PrimalItem_Weapon_Bow_C)", 200),
               ("Ingrediente (ex: PrimalItemResource_Wood_C)",  200),
               ("Qtd. ingrediente", 80)]
    item_v  = tk.StringVar()
    ingr_v  = tk.StringVar()
    qty_v   = tk.StringVar(value="10")
    exact_v = tk.BooleanVar(value=False)

    for col, (lbl, w) in enumerate([("Item a craftar", 180), ("Ingrediente", 180), ("Qtd.", 70)]):
        ctk.CTkLabel(gen, text=lbl, font=ctk.CTkFont(size=10),
                     text_color="#8899aa").grid(row=1, column=col*2, padx=(12,2), pady=(0,4), sticky="e")
    ctk.CTkEntry(gen, textvariable=item_v, width=180, height=28).grid(row=1, column=1, padx=(0,8), pady=(0,4), sticky="w")
    ctk.CTkEntry(gen, textvariable=ingr_v, width=180, height=28).grid(row=1, column=3, padx=(0,8), pady=(0,4), sticky="w")
    ctk.CTkEntry(gen, textvariable=qty_v,  width=70,  height=28).grid(row=1, column=5, padx=(0,8), pady=(0,4), sticky="w")
    ctk.CTkCheckBox(gen, text="Tipo exato", variable=exact_v,
                    font=ctk.CTkFont(size=10)).grid(row=1, column=6, padx=(0,12), pady=(0,4), sticky="w")

    def _add_craft_line():
        item = item_v.get().strip()
        ingr = ingr_v.get().strip()
        try: qty = float(qty_v.get())
        except ValueError: qty = 10.0
        if not item or not ingr: return
        exact = str(exact_v.get()).lower()
        line = (f'ConfigOverrideItemCraftingCosts=(ItemClassString="{item}",'
                f'BaseCraftingResourceRequirements=((ResourceItemTypeString="{ingr}",'
                f'BaseResourceRequirement={qty:.1f},bCraftingRequireExactResourceType={exact})),'
                f'bCraftingRequireExactResourceType={exact})\n')
        box.configure(state="normal")
        box.insert("end", line)

    ctk.CTkButton(gen, text="＋ Adicionar linha", height=28,
                  fg_color="#0e4a6e", hover_color="#0a3550",
                  font=ctk.CTkFont(size=11),
                  command=_add_craft_line).grid(row=2, column=0, columnspan=7, padx=12, pady=(0,8), sticky="w")

    box = ctk.CTkTextbox(sf, height=300, font=ctk.CTkFont(family="Consolas", size=10))
    box.grid(row=3, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")
    box.insert("1.0", srv.crafting_overrides_raw)
    vars_ref["_raw_crafting_overrides_raw"] = box

    _add_help(sf, [
        ("Formato", "ConfigOverrideItemCraftingCosts=(ItemClassString=\"Classe_C\",BaseCraftingResourceRequirements=((ResourceItemTypeString=\"Recurso_C\",BaseResourceRequirement=10.0,...)))"),
        ("bCraftingRequireExactResourceType", "True = exige exatamente a classe informada; False = aceita subclasses (ex: qualquer madeira)."),
        ("Gerador rápido", "Preencha os campos acima e clique em Adicionar linha para gerar a entrada automaticamente."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 18 — Substituições de Stack
# ════════════════════════════════════════════════════════════════════════════ #

def _build_stack_overrides(sf, srv, vars_ref, bg, accent):
    import tkinter as tk
    _section_label(sf, "Substituições de Stack (Game.ini)", 0, accent)
    ctk.CTkLabel(sf,
        text="Cole ConfigOverrideItemMaxQuantity=(...) do Game.ini",
        font=ctk.CTkFont(size=10), text_color="#7ab8c8").grid(
        row=1, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="w")

    # ── Gerador rápido ────────────────────────────────────────────────────────
    gen = ctk.CTkFrame(sf, fg_color="#0d1b2a", corner_radius=8)
    gen.grid(row=2, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")
    gen.grid_columnconfigure((1, 3), weight=1)

    ctk.CTkLabel(gen, text="⚡ Gerador rápido",
                 font=ctk.CTkFont(size=11, weight="bold"),
                 text_color=accent).grid(row=0, column=0, columnspan=6, padx=12, pady=(8, 4), sticky="w")

    item_v = tk.StringVar()
    qty_v  = tk.StringVar(value="500")
    ign_v  = tk.BooleanVar(value=True)

    for col, lbl in enumerate(["Item (ex: PrimalItemAmmo_ArrowTranq_C)", "Qtd. máxima"]):
        ctk.CTkLabel(gen, text=lbl, font=ctk.CTkFont(size=10),
                     text_color="#8899aa").grid(row=1, column=col*2, padx=(12,2), pady=(0,4), sticky="e")
    ctk.CTkEntry(gen, textvariable=item_v, width=220, height=28).grid(row=1, column=1, padx=(0,8), pady=(0,4), sticky="w")
    ctk.CTkEntry(gen, textvariable=qty_v,  width=80,  height=28).grid(row=1, column=3, padx=(0,8), pady=(0,4), sticky="w")
    ctk.CTkCheckBox(gen, text="Ignorar multiplicador", variable=ign_v,
                    font=ctk.CTkFont(size=10)).grid(row=1, column=4, padx=(0,12), pady=(0,4), sticky="w")

    def _add_stack_line():
        item = item_v.get().strip()
        try: qty = int(qty_v.get())
        except ValueError: qty = 500
        if not item: return
        ign = str(ign_v.get())
        line = (f'ConfigOverrideItemMaxQuantity=(ItemClassString="{item}",'
                f'Quantity=(MaxItemQuantity={qty},bIgnoreMultiplier={ign}))\n')
        box.configure(state="normal")
        box.insert("end", line)

    ctk.CTkButton(gen, text="＋ Adicionar linha", height=28,
                  fg_color="#0e4a6e", hover_color="#0a3550",
                  font=ctk.CTkFont(size=11),
                  command=_add_stack_line).grid(row=2, column=0, columnspan=5, padx=12, pady=(0,8), sticky="w")

    box = ctk.CTkTextbox(sf, height=300, font=ctk.CTkFont(family="Consolas", size=10))
    box.grid(row=3, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")
    box.insert("1.0", srv.stack_size_overrides_raw)
    vars_ref["_raw_stack_size_overrides_raw"] = box

    _add_help(sf, [
        ("Formato", "ConfigOverrideItemMaxQuantity=(ItemClassString=\"Classe_C\",Quantity=(MaxItemQuantity=500,bIgnoreMultiplier=True))"),
        ("bIgnoreMultiplier", "True = usa a quantidade absoluta ignorando o multiplicador global de stack."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 19 — Substituições de Spawner
# ════════════════════════════════════════════════════════════════════════════ #

def _build_spawner_overrides(sf, srv, vars_ref, bg, accent):
    import tkinter as tk
    _section_label(sf, "Substituições de Spawner no Mapa (Game.ini)", 0, accent)
    ctk.CTkLabel(sf,
        text="ConfigAddNPCSpawnEntriesContainer / ConfigSubtractNPCSpawnEntriesContainer / ConfigOverrideNPCSpawnEntriesContainer",
        font=ctk.CTkFont(size=10), text_color="#7ab8c8", wraplength=520).grid(
        row=1, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="w")

    # ── Gerador rápido ────────────────────────────────────────────────────────
    gen = ctk.CTkFrame(sf, fg_color="#0d1b2a", corner_radius=8)
    gen.grid(row=2, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")
    gen.grid_columnconfigure((1, 3, 5), weight=1)

    ctk.CTkLabel(gen, text="⚡ Gerador rápido",
                 font=ctk.CTkFont(size=11, weight="bold"),
                 text_color=accent).grid(row=0, column=0, columnspan=8, padx=12, pady=(8, 4), sticky="w")

    mode_v      = tk.StringVar(value="ConfigAddNPCSpawnEntriesContainer")
    container_v = tk.StringVar()
    dino_v      = tk.StringVar()
    chance_v    = tk.StringVar(value="0.1")
    maxpct_v    = tk.StringVar(value="0.1")

    ctk.CTkLabel(gen, text="Modo", font=ctk.CTkFont(size=10),
                 text_color="#8899aa").grid(row=1, column=0, padx=(12,2), pady=(0,4), sticky="e")
    ctk.CTkComboBox(gen, variable=mode_v, width=270, height=28,
                    values=["ConfigAddNPCSpawnEntriesContainer",
                            "ConfigSubtractNPCSpawnEntriesContainer",
                            "ConfigOverrideNPCSpawnEntriesContainer"]).grid(
        row=1, column=1, columnspan=3, padx=(0,8), pady=(0,4), sticky="w")

    for col, (lbl, var, w) in enumerate([
        ("Container (NPCSpawnEntriesContainerClassString)", container_v, 220),
        ("Dino (AnEntryName/NPCClassString)",               dino_v,      200),
        ("EntryChance",                                    chance_v,     70),
        ("MaxPctOf\nClass",                                maxpct_v,     70),
    ]):
        ctk.CTkLabel(gen, text=lbl, font=ctk.CTkFont(size=10),
                     text_color="#8899aa", wraplength=200).grid(row=2, column=col*2, padx=(12,2), pady=(0,4), sticky="e")
        ctk.CTkEntry(gen, textvariable=var, width=w, height=28).grid(
            row=2, column=col*2+1, padx=(0,8), pady=(0,4), sticky="w")

    def _add_spawn_line():
        mode      = mode_v.get().strip()
        container = container_v.get().strip()
        dino      = dino_v.get().strip()
        try: chance  = float(chance_v.get())
        except ValueError: chance = 0.1
        try: maxpct  = float(maxpct_v.get())
        except ValueError: maxpct = 0.1
        if not container or not dino: return
        line = (f'{mode}=(NPCSpawnEntriesContainerClassString="{container}",'
                f'NPCSpawnEntries=((AnEntryName="{dino}",NPCsToSpawnStrings=("{dino}"),'
                f'EntryWeight={chance:.3f})),NPCSpawnLimits=((NPCClassString="{dino}",'
                f'MaxPercentageOfDesiredNumToAllow={maxpct:.3f})))\n')
        box.configure(state="normal")
        box.insert("end", line)

    ctk.CTkButton(gen, text="＋ Adicionar bloco", height=28,
                  fg_color="#0e4a6e", hover_color="#0a3550",
                  font=ctk.CTkFont(size=11),
                  command=_add_spawn_line).grid(row=3, column=0, columnspan=8, padx=12, pady=(0,8), sticky="w")

    # Botão para abrir editor visual de spawner
    app = vars_ref.get("_app")
    if app:
        th = get_theme("tek")
        ctk.CTkButton(
            sf, text="🗺 Abrir Editor Visual de Spawner", height=30,
            fg_color=th["accent_muted_bg"], hover_color="#052e16",
            border_width=1, border_color=th["accent"], text_color=th["accent"],
            font=ctk.CTkFont(size=11),
            command=lambda: app._asm_open_spawner_editor(srv),
        ).grid(row=3, column=0, columnspan=2, padx=8, pady=(4, 0), sticky="w")

    box = ctk.CTkTextbox(sf, height=300, font=ctk.CTkFont(family="Consolas", size=10))
    box.grid(row=4, column=0, columnspan=2, padx=8, pady=(4, 8), sticky="ew")
    box.insert("1.0", srv.npc_spawn_overrides_raw)
    vars_ref["_raw_npc_spawn_overrides_raw"] = box

    _add_help(sf, [
        ("ConfigAddNPCSpawnEntriesContainer", "Adiciona dinos a um container de spawn existente sem remover os originais."),
        ("ConfigSubtractNPCSpawnEntriesContainer", "Remove entradas específicas de um container de spawn."),
        ("ConfigOverrideNPCSpawnEntriesContainer", "Substitui completamente um container de spawn."),
        ("EntryWeight", "Peso relativo do spawn. Valores maiores = mais comum. Use valores entre 0.001 e 1.0."),
        ("MaxPercentageOfDesiredNumToAllow", "Percentual máximo do total de spawns permitido para essa criatura."),
        ("Editor Visual", "Use o botão acima para uma interface gráfica que facilita a criação de spawners."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 20 — Substituições de Supply Crate
# ════════════════════════════════════════════════════════════════════════════ #

def _build_supply_crate_overrides(sf, srv, vars_ref, bg, accent):
    import tkinter as tk
    _section_label(sf, "Substituições de Supply Crate (Game.ini)", 0, accent)
    ctk.CTkLabel(sf,
        text="Cole ConfigOverrideSupplyCrateItems=(...) do Game.ini",
        font=ctk.CTkFont(size=10), text_color="#7ab8c8").grid(
        row=1, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="w")

    # ── Gerador rápido ────────────────────────────────────────────────────────
    gen = ctk.CTkFrame(sf, fg_color="#0d1b2a", corner_radius=8)
    gen.grid(row=2, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")
    gen.grid_columnconfigure((1, 3, 5, 7), weight=1)

    ctk.CTkLabel(gen, text="⚡ Gerador rápido",
                 font=ctk.CTkFont(size=11, weight="bold"),
                 text_color=accent).grid(row=0, column=0, columnspan=8, padx=12, pady=(8, 4), sticky="w")

    crate_v  = tk.StringVar()
    item_v   = tk.StringVar()
    minqty_v = tk.StringVar(value="1")
    maxqty_v = tk.StringVar(value="1")
    chance_v = tk.StringVar(value="1.0")
    prevent_v = tk.BooleanVar(value=False)

    fields = [
        ("Crate (ex: SupplyCrate_Level03_C)",       crate_v,  180),
        ("Item (ex: PrimalItem_WeaponSword_C)",      item_v,   180),
        ("Qtd. mín.",                                minqty_v,  60),
        ("Qtd. máx.",                                maxqty_v,  60),
        ("Chance (0–1)",                             chance_v,  70),
    ]
    for col, (lbl, var, w) in enumerate(fields):
        ctk.CTkLabel(gen, text=lbl, font=ctk.CTkFont(size=10),
                     text_color="#8899aa").grid(row=1, column=col*2, padx=(12,2), pady=(0,4), sticky="e")
        ctk.CTkEntry(gen, textvariable=var, width=w, height=28).grid(
            row=1, column=col*2+1, padx=(0,8), pady=(0,4), sticky="w")
    ctk.CTkCheckBox(gen, text="Impedir duplicatas", variable=prevent_v,
                    font=ctk.CTkFont(size=10)).grid(row=1, column=10, padx=(0,12), pady=(0,4), sticky="w")

    def _add_crate_line():
        crate = crate_v.get().strip()
        item  = item_v.get().strip()
        try: minq = int(minqty_v.get())
        except ValueError: minq = 1
        try: maxq = int(maxqty_v.get())
        except ValueError: maxq = 1
        try: ch   = float(chance_v.get())
        except ValueError: ch = 1.0
        if not crate or not item: return
        prev = str(prevent_v.get())
        line = (f'ConfigOverrideSupplyCrateItems=(SupplyCrateClassString="{crate}",'
                f'ItemSets=((SetWeight={ch:.2f},NumItemSetsPower=1.0,Items=((ItemClassString="{item}",'
                f'ItemQuantity=(MinQuantity={minq},MaxQuantity={maxq},QualityMultiplier=1.0),'
                f'ItemQuality=(MinQuality=0.0,MaxQuality=0.0),bForceBlueprint=False,'
                f'ChanceToBeBlueprint=0.0,ChanceOfPreventingSpawn=0.0)))))\n')
        box.configure(state="normal")
        box.insert("end", line)

    ctk.CTkButton(gen, text="＋ Adicionar bloco", height=28,
                  fg_color="#0e4a6e", hover_color="#0a3550",
                  font=ctk.CTkFont(size=11),
                  command=_add_crate_line).grid(row=2, column=0, columnspan=11, padx=12, pady=(0,8), sticky="w")

    box = ctk.CTkTextbox(sf, height=300, font=ctk.CTkFont(family="Consolas", size=10))
    box.grid(row=3, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")
    box.insert("1.0", srv.supply_crate_overrides_raw)
    vars_ref["_raw_supply_crate_overrides_raw"] = box

    _add_help(sf, [
        ("ConfigOverrideSupplyCrateItems", "Substitui completamente o conteúdo de um supply crate (bea/drop/deep sea). Formato complexo — use o gerador rápido."),
        ("SupplyCrateClassString", "Classe do container alvo (ex: SupplyCrate_Level03_C)."),
        ("MinItemSets / MaxItemSets", "Quantos conjuntos de itens aparecem no drop (mínimo e máximo)."),
        ("SetWeight", "Peso do conjunto. Sets com peso maior aparecem com mais frequência."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 21 — Impedir Transferências
# ════════════════════════════════════════════════════════════════════════════ #

def _build_prevent_transfer(sf, srv, vars_ref, bg, accent):
    _section_label(sf, "Impedir Transferências por Classe (GameUserSettings.ini)", 0, accent)
    ctk.CTkLabel(sf,
        text="Cole PreventTransferForClassNames=... do GameUserSettings.ini",
        font=ctk.CTkFont(size=10), text_color="#7ab8c8").grid(
        row=1, column=0, columnspan=2, padx=8, pady=(0, 2), sticky="w")
    box = ctk.CTkTextbox(sf, height=300, font=ctk.CTkFont(family="Consolas", size=10))
    box.grid(row=2, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")
    box.insert("1.0", srv.prevent_transfer_raw)
    vars_ref["_raw_prevent_transfer_raw"] = box

    _add_help(sf, [
        ("Formato", "PreventTransferForClassNames=ClassName1,ClassName2,...  — Separe várias classes por vírgula."),
        ("Uso típico", "Impede transferência de itens específicos entre servidores de um cluster. Ex: Tekgram Tek Rifle."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Helper compartilhado — editor INI de dois painéis (Seções + Chave/Valor)
# ════════════════════════════════════════════════════════════════════════════ #

def _parse_ini_sections(raw: str) -> "dict[str, list[tuple[str,str]]]":
    sections: dict = {}
    current: "str | None" = None
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(";") or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            current = stripped[1:-1]
            if current not in sections:
                sections[current] = []
        elif "=" in stripped and current is not None:
            k, _, v = stripped.partition("=")
            sections[current].append((k.strip(), v.strip()))
    return sections


def _serialize_ini_sections(sections: "dict[str, list[tuple[str,str]]]") -> str:
    parts = []
    for sec, items in sections.items():
        parts.append(f"[{sec}]")
        for k, v in items:
            parts.append(f"{k}={v}")
        parts.append("")
    return "\n".join(parts).strip()


def _build_ini_editor(sf, title: str, raw_text: str, raw_key: str, vars_ref: dict, accent: str) -> None:
    """Editor INI de dois painéis: Seções (esquerda) + Chave/Valor (direita)."""
    import tkinter as tk

    _PANEL_BG  = "#0b1320"
    _CARD_BG   = "#0d1b2a"
    _HDR_BG    = "#0f2030"
    _BTN_ADD   = "#0e4a6e"
    _BTN_ADD_H = "#0a3550"
    _BTN_DEL   = "#5c1a1a"
    _BTN_DEL_H = "#7c2020"
    _BTN_NEU   = "#1e293b"
    _BTN_NEU_H = "#263347"
    _TXT_DIM   = "#8899aa"
    _TXT_HDR   = "#c8d8e8"

    # Estado em memória
    sections: dict = _parse_ini_sections(raw_text)
    sel_section: list = [None]           # lista mutável para fechar sobre ela

    # ── Textbox oculto (serialização no save) ─────────────────────────────────
    hidden_box = ctk.CTkTextbox(sf, height=1, fg_color="#0a0a0a",
                                text_color="#0a0a0a", border_width=0)
    hidden_box.grid(row=99, column=0, columnspan=2, sticky="ew")
    hidden_box.insert("1.0", raw_text)
    vars_ref[raw_key] = hidden_box

    def _flush():
        txt = _serialize_ini_sections(sections)
        hidden_box.configure(state="normal")
        hidden_box.delete("1.0", "end")
        hidden_box.insert("1.0", txt)

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    _section_label(sf, title, 0, accent)

    # ── Container principal (dois painéis lado a lado) ────────────────────────
    container = ctk.CTkFrame(sf, fg_color="transparent")
    container.grid(row=1, column=0, columnspan=2, padx=8, pady=(4, 8), sticky="nsew")
    container.grid_columnconfigure(0, weight=2, minsize=240)
    container.grid_columnconfigure(1, weight=3)
    container.grid_rowconfigure(0, weight=1)

    # ════════════════════════════════════════════════════
    # Painel ESQUERDO — Seções
    # ════════════════════════════════════════════════════
    lp = ctk.CTkFrame(container, fg_color=_PANEL_BG, corner_radius=8)
    lp.grid(row=0, column=0, padx=(0, 6), sticky="nsew")
    lp.grid_columnconfigure(0, weight=1)
    lp.grid_rowconfigure(1, weight=1)

    # Toolbar esquerda
    lt = ctk.CTkFrame(lp, fg_color=_HDR_BG, corner_radius=0, height=32)
    lt.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
    lt.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(lt, text="Seções Personalizadas",
                 font=ctk.CTkFont(size=11, weight="bold"),
                 text_color=_TXT_HDR).grid(row=0, column=0, padx=10, pady=4, sticky="w")

    tb_l = ctk.CTkFrame(lt, fg_color="transparent")
    tb_l.grid(row=0, column=1, padx=6, pady=4, sticky="e")

    # Lista rolável de seções
    sec_scroll = ctk.CTkScrollableFrame(lp, fg_color="transparent", height=260)
    sec_scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
    sec_scroll.grid_columnconfigure(0, weight=1)

    # Painel DIREITO — Chave/Valor
    rp = ctk.CTkFrame(container, fg_color=_PANEL_BG, corner_radius=8)
    rp.grid(row=0, column=1, sticky="nsew")
    rp.grid_columnconfigure(0, weight=1)
    rp.grid_rowconfigure(1, weight=1)

    # Toolbar direita
    rt = ctk.CTkFrame(rp, fg_color=_HDR_BG, corner_radius=0, height=32)
    rt.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
    rt.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(rt, text="Itens Personalizados",
                 font=ctk.CTkFont(size=11, weight="bold"),
                 text_color=_TXT_HDR).grid(row=0, column=0, padx=10, pady=4, sticky="w")

    tb_r = ctk.CTkFrame(rt, fg_color="transparent")
    tb_r.grid(row=0, column=1, padx=6, pady=4, sticky="e")

    # Cabeçalho da tabela
    col_hdr = ctk.CTkFrame(rp, fg_color=_CARD_BG, height=24)
    col_hdr.grid(row=1, column=0, sticky="ew", padx=4, pady=(4, 0))
    col_hdr.grid_columnconfigure(0, weight=3)
    col_hdr.grid_columnconfigure(1, weight=4)
    ctk.CTkLabel(col_hdr, text="Chave", font=ctk.CTkFont(size=10, weight="bold"),
                 text_color=_TXT_DIM).grid(row=0, column=0, padx=10, pady=2, sticky="w")
    ctk.CTkLabel(col_hdr, text="Valor", font=ctk.CTkFont(size=10, weight="bold"),
                 text_color=_TXT_DIM).grid(row=0, column=1, padx=10, pady=2, sticky="w")

    # Lista rolável de itens
    item_scroll = ctk.CTkScrollableFrame(rp, fg_color="transparent", height=234)
    item_scroll.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
    item_scroll.grid_columnconfigure(0, weight=3)
    item_scroll.grid_columnconfigure(1, weight=4)

    # ── Funções de renderização ───────────────────────────────────────────────

    def _render_items():
        for w in item_scroll.winfo_children():
            w.destroy()
        sec = sel_section[0]
        if sec is None or sec not in sections:
            return
        for idx, (k, v) in enumerate(sections[sec]):
            row_f = ctk.CTkFrame(item_scroll, fg_color="transparent")
            row_f.grid(row=idx, column=0, columnspan=3, sticky="ew", pady=1)
            row_f.grid_columnconfigure(0, weight=3)
            row_f.grid_columnconfigure(1, weight=4)
            kv = tk.StringVar(value=k)
            vv = tk.StringVar(value=v)

            def _on_key_change(name, _idx=idx, _kv=kv):
                if sel_section[0] and sel_section[0] in sections:
                    old_v = sections[sel_section[0]][_idx][1]
                    sections[sel_section[0]][_idx] = (_kv.get(), old_v)
                    _flush()
            def _on_val_change(name, _idx=idx, _vv=vv):
                if sel_section[0] and sel_section[0] in sections:
                    old_k = sections[sel_section[0]][_idx][0]
                    sections[sel_section[0]][_idx] = (old_k, _vv.get())
                    _flush()

            kv.trace_add("write", lambda *a, name=kv, _i=idx: _on_key_change(name, _i))
            vv.trace_add("write", lambda *a, name=vv, _i=idx: _on_val_change(name, _i))

            ctk.CTkEntry(row_f, textvariable=kv, height=26,
                         font=ctk.CTkFont(family="Consolas", size=10)).grid(
                row=0, column=0, padx=(2, 2), pady=1, sticky="ew")
            ctk.CTkEntry(row_f, textvariable=vv, height=26,
                         font=ctk.CTkFont(family="Consolas", size=10)).grid(
                row=0, column=1, padx=(0, 2), pady=1, sticky="ew")
            ctk.CTkButton(row_f, text="✕", width=24, height=24,
                          fg_color=_BTN_DEL, hover_color=_BTN_DEL_H,
                          command=lambda i=idx: _del_item(i)).grid(
                row=0, column=2, padx=(0, 2))

    def _render_sections():
        for w in sec_scroll.winfo_children():
            w.destroy()
        for i, sec in enumerate(sections):
            rf = ctk.CTkFrame(sec_scroll, fg_color="transparent")
            rf.grid(row=i, column=0, sticky="ew", pady=1)
            rf.grid_columnconfigure(0, weight=1)
            is_sel = (sec == sel_section[0])
            btn = ctk.CTkButton(
                rf, text=sec, anchor="w", height=28,
                font=ctk.CTkFont(size=11),
                fg_color=accent if is_sel else _BTN_NEU,
                hover_color=accent if is_sel else _BTN_NEU_H,
                text_color="white",
                command=lambda s=sec: _select_section(s),
            )
            btn.grid(row=0, column=0, padx=(2, 2), sticky="ew")
            ctk.CTkButton(rf, text="✕", width=24, height=26,
                          fg_color=_BTN_DEL, hover_color=_BTN_DEL_H,
                          command=lambda s=sec: _del_section(s)).grid(
                row=0, column=1, padx=(0, 2))

    def _select_section(sec: str):
        sel_section[0] = sec
        _render_sections()
        _render_items()

    # ── Ações seções ──────────────────────────────────────────────────────────

    def _add_section():
        dlg = ctk.CTkInputDialog(text="Nome da seção (sem colchetes):",
                                 title="Nova Seção")
        name = dlg.get_input()
        if name and name.strip():
            name = name.strip()
            if name not in sections:
                sections[name] = []
            sel_section[0] = name
            _flush()
            _render_sections()
            _render_items()

    def _del_section(sec: str):
        sections.pop(sec, None)
        if sel_section[0] == sec:
            sel_section[0] = next(iter(sections), None)
        _flush()
        _render_sections()
        _render_items()

    def _copy_section():
        sec = sel_section[0]
        if sec is None:
            return
        lines = [f"[{sec}]"] + [f"{k}={v}" for k, v in sections.get(sec, [])]
        sf.winfo_toplevel().clipboard_clear()
        sf.winfo_toplevel().clipboard_append("\n".join(lines))

    def _refresh_sections():
        raw = hidden_box.get("1.0", "end").strip()
        sections.clear()
        sections.update(_parse_ini_sections(raw))
        sel_section[0] = next(iter(sections), None)
        _render_sections()
        _render_items()

    # ── Ações itens ───────────────────────────────────────────────────────────

    def _add_item():
        sec = sel_section[0]
        if sec is None:
            return
        sections[sec].append(("Chave", "Valor"))
        _flush()
        _render_items()

    def _del_item(idx: int):
        sec = sel_section[0]
        if sec and sec in sections and idx < len(sections[sec]):
            sections[sec].pop(idx)
            _flush()
            _render_items()

    def _copy_items():
        sec = sel_section[0]
        if sec is None:
            return
        lines = [f"{k}={v}" for k, v in sections.get(sec, [])]
        sf.winfo_toplevel().clipboard_clear()
        sf.winfo_toplevel().clipboard_append("\n".join(lines))

    def _clear_items():
        sec = sel_section[0]
        if sec and sec in sections:
            sections[sec].clear()
            _flush()
            _render_items()

    def _import_from_clipboard():
        try:
            text = sf.winfo_toplevel().clipboard_get()
        except Exception:
            return
        parsed = _parse_ini_sections(text)
        if not parsed:
            return
        for sec, items in parsed.items():
            if sec not in sections:
                sections[sec] = []
            sections[sec].extend(items)
        if not sel_section[0] and sections:
            sel_section[0] = next(iter(sections))
        _flush()
        _render_sections()
        _render_items()

    def _copy_all_sections():
        sf.winfo_toplevel().clipboard_clear()
        sf.winfo_toplevel().clipboard_append(_serialize_ini_sections(sections))

    def _paste_items():
        sec = sel_section[0]
        if sec is None:
            return
        try:
            text = sf.winfo_toplevel().clipboard_get()
        except Exception:
            return
        for line in text.splitlines():
            line = line.strip()
            if "=" in line and not line.startswith(("[", ";", "#")):
                k, _, v = line.partition("=")
                sections[sec].append((k.strip(), v.strip()))
        _flush()
        _render_items()

    # ── Botões toolbar esquerda ───────────────────────────────────────────────
    _BTN_ADD_G  = "#15803d"
    _BTN_ADD_GH = "#14532d"
    _BTN_IMP    = "#0e4a6e"
    _BTN_IMP_H  = "#0a3550"

    for icon, cmd, fg, hv in [
        ("🔄", _refresh_sections,  _BTN_NEU,   _BTN_NEU_H),
        ("➕", _add_section,       _BTN_ADD_G, _BTN_ADD_GH),
        ("📄", _copy_all_sections, _BTN_NEU,   _BTN_NEU_H),
        ("📥", _import_from_clipboard, _BTN_IMP, _BTN_IMP_H),
        ("❌", lambda: _del_section(sel_section[0]) if sel_section[0] else None,
               _BTN_DEL, _BTN_DEL_H),
    ]:
        ctk.CTkButton(tb_l, text=icon, width=26, height=24,
                      fg_color=fg, hover_color=hv,
                      font=ctk.CTkFont(size=12),
                      command=cmd).pack(side="left", padx=2)

    # ── Botões toolbar direita ────────────────────────────────────────────────
    for icon, cmd, fg, hv in [
        ("➕", _add_item,    _BTN_ADD_G, _BTN_ADD_GH),
        ("📄", _paste_items, _BTN_NEU,   _BTN_NEU_H),
        ("❌", _clear_items, _BTN_DEL,   _BTN_DEL_H),
    ]:
        ctk.CTkButton(tb_r, text=icon, width=26, height=24,
                      fg_color=fg, hover_color=hv,
                      font=ctk.CTkFont(size=12),
                      command=cmd).pack(side="left", padx=2)

    # ── Render inicial ────────────────────────────────────────────────────────
    if sections:
        sel_section[0] = next(iter(sections))
    _render_sections()
    _render_items()


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 22 — Custom GameUserSettings.ini
# ════════════════════════════════════════════════════════════════════════════ #

def _build_custom_gus(sf, srv, vars_ref, bg, accent):
    _build_ini_editor(sf, "Conteúdo extra — GameUserSettings.ini",
                      srv.custom_gus_ini_raw, "_raw_custom_gus_ini_raw",
                      vars_ref, accent)
    _add_help(sf, [
        ("Para que serve", "Conteúdo extra adicionado ao final do GameUserSettings.ini gerado pelo app."),
        ("Secções comuns", "[ServerSettings], [SessionSettings], [/Script/ShooterGame.ShooterGameMode]"),
        ("Dica", "Use este campo para configurações avancadas que não possuem campo dedicado no painel."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 23 — Custom Game.ini
# ════════════════════════════════════════════════════════════════════════════ #

def _build_custom_game(sf, srv, vars_ref, bg, accent):
    _build_ini_editor(sf, "Conteúdo extra — Game.ini",
                      srv.custom_game_ini_raw, "_raw_custom_game_ini_raw",
                      vars_ref, accent)
    _add_help(sf, [
        ("Para que serve", "Conteúdo extra adicionado ao final do Game.ini gerado pelo app."),
        ("Seções comuns", "[/script/shootergame.shootergamemode], [DinoSettings_Extra]"),
        ("Dica", "Use para overrides avançados como configurações de dinos específicos e regras de jogo custom."),
    ])



# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 24 — ARK Procedural (PGM)
# ════════════════════════════════════════════════════════════════════════════ #

def _build_pgm(sf, srv, vars_ref, bg, accent):
    _section_label(sf, "ARK Procedural (PGM)", 0, accent)
    _bool_check(sf, "Habilitar ARK Procedural", "pgm_enabled", srv, vars_ref, 1, accent)
    _str_entry(sf,  "Nome do mapa",             "pgm_name",    srv, vars_ref, 2, accent)

    ctk.CTkLabel(sf, text="PGTerrainPropertiesString (raw):",
                 font=ctk.CTkFont(size=11), text_color="#7ab8c8").grid(
        row=3, column=0, columnspan=2, padx=8, pady=(8, 2), sticky="w")
    box = ctk.CTkTextbox(sf, height=200, font=ctk.CTkFont(family="Consolas", size=10))
    box.grid(row=4, column=0, columnspan=2, padx=8, pady=(0, 8), sticky="ew")
    box.insert("1.0", srv.pgm_terrain_string)
    vars_ref["_raw_pgm_terrain_string"] = box

    _add_help(sf, [
        ("ARK Procedural", "Gera mapas procedurais (PGM). Requer DLC e configuração avançada."),
        ("PGTerrainPropertiesString", "String de configuração de terreno procedural. Consulte a wiki oficial do ARK PGM."),
        ("Dica", "Use apenas se seu servidor roda no mapa procedural (PGARK). Ignore em mapas normais."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Salvar
# ════════════════════════════════════════════════════════════════════════════ #

def _sync_ui_to_cfg(app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
    """Sincroniza os widgets do painel para o objeto cfg em memória.
    Não persiste no JSON nem mostra dialogs — usado antes de Iniciar/Restart.
    """
    vars_ref = getattr(app, "_asm_panel_vars", {}).get(srv.id, {})

    from dataclasses import fields as _fields
    field_types = {f.name: f.type for f in _fields(AsmServerConfig)}

    for field_name, var in vars_ref.items():
        if field_name.startswith("_"):
            continue
        ftype = field_types.get(field_name)
        try:
            raw = var.get()
            if ftype in ("bool", bool) or str(ftype) == "bool":
                setattr(srv, field_name, bool(raw))
            elif ftype in ("int", int) or str(ftype) == "int":
                setattr(srv, field_name, int(float(raw)))
            elif ftype in ("float", float) or str(ftype) == "float":
                setattr(srv, field_name, float(raw))
            else:
                setattr(srv, field_name, str(raw))
        except Exception:
            pass

    # Mods
    mods_box = vars_ref.get("_mods_text")
    if mods_box:
        lines = mods_box.get("1.0", "end").strip().splitlines()
        srv.active_mods = [l.strip() for l in lines if l.strip()]

    # MOTD
    motd_box = vars_ref.get("_motd_text")
    if motd_box:
        srv.motd = motd_box.get("1.0", "end").strip()

    # Notes
    notes_box = vars_ref.get("_notes_text")
    if notes_box:
        srv.notes = notes_box.get("1.0", "end").strip()

    # Server files IDs
    for attr, key in (
        ("admin_ids",          "_admin_ids_text"),
        ("whitelist_ids",      "_whitelist_ids_text"),
        ("exclusive_join_ids", "_exclusive_ids_text"),
    ):
        box = vars_ref.get(key)
        if box:
            lines = box.get("1.0", "end").strip().splitlines()
            setattr(srv, attr, [l.strip() for l in lines if l.strip()])

    # Raw textbox fields (prefixed _raw_<fieldname>)
    for key, box in vars_ref.items():
        if key.startswith("_raw_"):
            field_name = key[5:]
            if hasattr(srv, field_name) and hasattr(box, "get"):
                try:
                    setattr(srv, field_name, box.get("1.0", "end").strip())
                except Exception:
                    pass

    # Tags CSV
    tags_var = vars_ref.get("_tags_csv")
    if tags_var:
        raw = tags_var.get().strip()
        srv.tags = [t.strip() for t in raw.split(",") if t.strip()] if raw else []

    # Per-level stat multipliers
    pls = vars_ref.get("_pls")
    if pls:
        for attr, svars in pls.items():
            try:
                setattr(srv, attr, [float(sv.get()) for sv in svars])
            except Exception:
                pass


def _save(app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
    # 1. Sincroniza UI → cfg em memória
    _sync_ui_to_cfg(app, srv)

    # 2. Persiste no JSON
    try:
        app.asm_config_manager.update_server(srv)
    except Exception as _e:
        import tkinter.messagebox as _mb
        _mb.showerror("Erro ao salvar", f"Não foi possível salvar: {_e}", parent=app)
        return

    # 3. Invalida cache do frame deste servidor para forçar reconstrução na próxima abertura
    cache_key = f"server_{srv.id}"
    frame_cache = getattr(app, "_frame_cache", {})
    if cache_key in frame_cache:
        try:
            frame_cache[cache_key].destroy()
        except Exception:
            pass
        frame_cache.pop(cache_key, None)

    # 4. Escreve os INIs imediatamente (se install_dir existir)
    import os as _os
    if srv.install_dir and _os.path.isdir(srv.install_dir):
        try:
            from ..asm_engine.asm_ini_manager import write_ini
            write_ini(srv)
        except Exception:
            pass  # INIs serão escritos no próximo start

    # 5. Atualiza dashboard e sidebar
    try:
        app._asm_refresh_dashboard()
    except Exception:
        pass
    try:
        app._rebuild_server_sidebar()
    except Exception:
        pass

    import tkinter.messagebox as _mb2
    _mb2.showinfo("Salvo", f"Configurações de '{srv.name}' salvas.", parent=app)


# ════════════════════════════════════════════════════════════════════════════ #
#  Importar / Sincronizar INI
# ════════════════════════════════════════════════════════════════════════════ #

def _open_import_ini(app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
    """Abre o diálogo de importação/sincronização de INI."""
    from ..asm_ui.asm_import_ini_dialog import open_asm_import_ini_dialog
    open_asm_import_ini_dialog(app, srv)


# ════════════════════════════════════════════════════════════════════════════ #
#  Diálogo de Presets (S3.3)
# ════════════════════════════════════════════════════════════════════════════ #

def _open_preset_dialog(app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
    """Diálogo para salvar/carregar presets de configuração."""
    from ..asm_engine.asm_preset_manager import AsmPresetManager, PRESET_CATEGORIES
    pm = AsmPresetManager()
    th = get_theme("tek")
    bg      = th["bg"]
    cg      = th["card_bg"]
    sep     = th["separator"]
    accent  = th["accent"]
    t_sec   = th["text_secondary"]
    t_mut   = th["text_muted"]
    acc_mb  = th["accent_muted_bg"]
    acc_dk  = th["accent_dark"]

    dlg = ctk.CTkToplevel(app)
    dlg.title(f"Presets — {srv.name}")
    dlg.geometry("640x500")
    dlg.configure(fg_color=bg)
    dlg.after(100, dlg.lift)
    dlg.after(150, dlg.focus_force)

    ctk.CTkLabel(dlg, text="Gerenciar Presets de Configuração",
                 font=ctk.CTkFont(size=14, weight="bold"),
                 text_color=accent).pack(pady=(16, 8))

    tab = ctk.CTkTabview(dlg, fg_color=cg, corner_radius=8)
    tab.pack(fill="both", expand=True, padx=16, pady=(0, 12))
    tab.add("📋 Aplicar Preset")
    tab.add("💾 Salvar Preset")

    # ── Aba: Aplicar preset ───────────────────────────────────────────────────
    apply_f = tab.tab("📋 Aplicar Preset")
    apply_f.grid_columnconfigure(0, weight=1)
    apply_f.grid_rowconfigure(0, weight=1)

    presets = pm.list_presets()
    if not presets:
        ctk.CTkLabel(apply_f, text="Nenhum preset salvo ainda.",
                     font=ctk.CTkFont(size=12), text_color=t_sec,
                     ).pack(pady=30)
    else:
        preset_scroll = ctk.CTkScrollableFrame(apply_f, fg_color="transparent", corner_radius=0)
        preset_scroll.pack(fill="both", expand=True)
        preset_scroll.grid_columnconfigure(0, weight=1)

        for p in presets:
            pf = ctk.CTkFrame(preset_scroll, fg_color=bg, corner_radius=6,
                              border_width=1, border_color=sep)
            pf.pack(fill="x", padx=4, pady=3)
            pf.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(pf, text=p["name"],
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=t_sec).grid(row=0, column=0, padx=10, pady=(8, 2), sticky="w")
            ctk.CTkLabel(pf, text=f"Categorias: {', '.join(p['categories'])}  •  {p['created_at'][:10]}",
                         font=ctk.CTkFont(size=9), text_color=t_mut,
                         ).grid(row=1, column=0, padx=10, pady=(0, 4), sticky="w")

            btn_f = ctk.CTkFrame(pf, fg_color="transparent")
            btn_f.grid(row=0, column=1, rowspan=2, padx=(0, 10), pady=4, sticky="e")

            def _apply(name=p["name"], path=p["path"]):
                pm.load_preset(path, srv)
                app.asm_config_manager.update_server(srv)
                app._asm_refresh_dashboard()
                dlg.destroy()
                from tkinter import messagebox
                messagebox.showinfo("Preset Aplicado", f"Preset '{name}' aplicado com sucesso.")

            def _delete(name=p["name"]):
                pm.delete_preset(name)
                dlg.destroy()
                _open_preset_dialog(app, srv)

            ctk.CTkButton(btn_f, text="Aplicar", width=70, height=26,
                          fg_color=acc_mb, hover_color="#052e16",
                          border_width=1, border_color=accent, text_color=accent,
                          font=ctk.CTkFont(size=10), command=_apply).pack(side="left", padx=(0, 4))
            ctk.CTkButton(btn_f, text="✕", width=28, height=26,
                          fg_color="#7f1d1d", hover_color="#991b1b",
                          text_color="#fca5a5", corner_radius=4,
                          font=ctk.CTkFont(size=10), command=_delete).pack(side="left")

    # ── Aba: Salvar preset ────────────────────────────────────────────────────
    save_f = tab.tab("💾 Salvar Preset")
    save_f.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(save_f, text="Nome do preset:", font=ctk.CTkFont(size=11),
                 text_color=t_sec, anchor="w").pack(padx=12, pady=(12, 2), anchor="w")
    name_entry = ctk.CTkEntry(save_f, placeholder_text="Meu Preset PvE")
    name_entry.pack(fill="x", padx=12, pady=(0, 8))

    ctk.CTkLabel(save_f, text="Categorias a incluir:", font=ctk.CTkFont(size=11),
                 text_color=t_sec, anchor="w").pack(padx=12, pady=(4, 2), anchor="w")

    cat_vars: dict[str, tk.BooleanVar] = {}
    cats_grid = ctk.CTkFrame(save_f, fg_color="transparent")
    cats_grid.pack(fill="x", padx=12)
    cats_grid.grid_columnconfigure((0, 1, 2), weight=1)

    all_cats = [c for c in PRESET_CATEGORIES if c != "full"]
    for i, cat in enumerate(all_cats):
        v = tk.BooleanVar(value=True)
        cat_vars[cat] = v
        ctk.CTkCheckBox(cats_grid, text=cat.capitalize(), variable=v,
                        font=ctk.CTkFont(size=10), text_color=t_sec,
                        border_color=accent, checkmark_color=accent,
                        ).grid(row=i // 3, column=i % 3, padx=4, pady=2, sticky="w")

    ctk.CTkLabel(save_f, text="Descrição (opcional):", font=ctk.CTkFont(size=11),
                 text_color=t_sec, anchor="w").pack(padx=12, pady=(8, 2), anchor="w")
    desc_entry = ctk.CTkEntry(save_f, placeholder_text="Balanceamento para PvE casual")
    desc_entry.pack(fill="x", padx=12, pady=(0, 12))

    def _save_preset():
        name = name_entry.get().strip()
        if not name:
            return
        cats = [c for c, v in cat_vars.items() if v.get()]
        if not cats:
            return
        desc = desc_entry.get().strip()
        _save(app, srv)  # garante dados atuais no srv
        pm.save_preset(name, srv, cats, desc)
        dlg.destroy()
        from tkinter import messagebox
        messagebox.showinfo("Preset Salvo", f"Preset '{name}' salvo com sucesso.")

    ctk.CTkButton(save_f, text="💾  Salvar Preset", height=32,
                  fg_color=acc_mb, hover_color="#052e16",
                  border_width=1, border_color=accent, text_color=accent,
                  font=ctk.CTkFont(size=12),
                  command=_save_preset).pack(padx=12, pady=(0, 12))
