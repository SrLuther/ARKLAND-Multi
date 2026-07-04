"""
TEK — Painel de configuração de servidor (28 seções, fiel ao ASM).
Estrutura: header + nav lateral + conteúdo dinâmico.
"""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Callable
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig, is_config_editable
from ..ui.server_field_labels import get_field_meta
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


# ── Navegação agrupada (7 categorias — Fase 1 TEK v2) ───────────────────────
NAV_GROUPS: list[tuple[str, list[str]]] = [
    ("Servidor", [
        "Todas as opções",
        "Administração",
        "Mods (Workshop)",
        "Gerenciamento Automático",
        "Detalhes do Servidor",
        "Arquivos do Servidor",
    ]),
    ("Regras", [
        "Regras",
        "Transferências / Tributo",
        "Bate-papo e Notificações",
        "HUD e Visuais",
    ]),
    ("Gameplay", [
        "Configurações do Jogador",
        "Configurações do Dino",
        "Reprodução",
        "Meio Ambiente",
    ]),
    ("Construção", [
        "Estruturas",
        "Engramas",
        "Progressões de Nível",
    ]),
    ("Substituições", [
        "Substituições de Crafting",
        "Substituições de Stack",
        "Substituições de Spawner",
        "Substituições de Supply Crate",
        "Impedir Transferências",
    ]),
    ("Agregados", [
        "Coleta por Recurso",
        "Multiplicadores por Classe",
        "Spawn e Domesticação",
    ]),
    ("INI", [
        "Custom GameUserSettings.ini",
        "Custom Game.ini",
        "ARK Procedural (PGM)",
    ]),
    ("Integrações", [
        "Detalhes do Discord Bot",
    ]),
    ("SM / Avançado", [
        "Extensões SM",
    ]),
    ("Ferramentas", [
        "🦕 Gerador SpawnExact",
        "⚡ Console RCON",
        "👥 Jogadores Online",
    ]),
]

# ── Seções do painel (ordem fiel ao ASM) ─────────────────────────────────────
SECTIONS: list[str] = [
    "Todas as opções",
    "Administração",
    "Mods (Workshop)",
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
    "Coleta por Recurso",
    "Multiplicadores por Classe",
    "Spawn e Domesticação",
    "Custom GameUserSettings.ini",
    "Custom Game.ini",
    "ARK Procedural (PGM)",
    "Extensões SM",
    "🦕 Gerador SpawnExact",
    "⚡ Console RCON",
    "👥 Jogadores Online",
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
    surface_bg = theme.get("surface_bg", bg)
    panel_bg   = theme.get("panel_bg", card_bg)
    card_border = theme.get("card_border", sep)
    nav_hover   = theme.get("nav_hover", hover)

    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=0)
    parent.grid_rowconfigure(1, weight=0)
    parent.grid_rowconfigure(2, weight=0)
    parent.grid_rowconfigure(3, weight=1)

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = ctk.CTkFrame(parent, fg_color=card_bg, corner_radius=0, height=60,
                       border_width=1, border_color=card_border)
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
        app._asm_start_server(srv)
        _refresh_action_btns()

    def _on_stop() -> None:
        app._asm_stop_server(srv.id)
        _refresh_action_btns()

    def _on_restart() -> None:
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
        editable   = is_config_editable(status)
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
        _save_state = "normal" if editable else "disabled"
        btn_save.configure(state=_save_state, text_color=accent if editable else t_mut)
        btn_import.configure(state=_save_state, text_color=accent if editable else t_mut)
        if editable:
            lock_banner.grid_remove()
        else:
            lock_banner.grid(row=1, column=0, sticky="ew")
            lock_lbl.configure(
                text=(
                    "Servidor em execução — pare o processo para salvar alterações no perfil e INI."
                    if is_running else
                    "Aguarde o servidor ficar parado para salvar alterações."
                )
            )

    btn_save = ctk.CTkButton(
        hdr, text="💾  Salvar", width=100, height=34,
        fg_color=acc_mb, hover_color=acc_dk,
        border_width=1, border_color=acc_dk,
        text_color=accent, corner_radius=8,
        font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
        command=lambda: _save(app, srv),
    )
    btn_save.grid(row=0, column=6, padx=(8, 4), pady=12, sticky="e")

    ctk.CTkButton(
        hdr, text="📋  Presets", width=92, height=34,
        fg_color=acc_mb, hover_color=acc_dk,
        border_width=1, border_color=acc_dk,
        text_color=accent, corner_radius=8,
        font=ctk.CTkFont(family="Segoe UI", size=12),
        command=lambda: _open_preset_dialog(app, srv),
    ).grid(row=0, column=7, padx=(0, 6), pady=12, sticky="e")

    btn_import = ctk.CTkButton(
        hdr, text="📥  Importar INI", width=130, height=34,
        fg_color=acc_mb, hover_color=acc_dk,
        border_width=1, border_color=acc_dk,
        text_color=accent, corner_radius=8,
        font=ctk.CTkFont(family="Segoe UI", size=12),
        command=lambda: _open_import_ini(app, srv),
    )
    btn_import.grid(row=0, column=8, padx=(0, 8), pady=12, sticky="e")

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

    lock_banner = ctk.CTkFrame(parent, fg_color="#431407" if not theme.get("_is_light") else "#fef3c7",
                               corner_radius=0, height=32)
    lock_banner.grid(row=1, column=0, sticky="ew")
    lock_banner.grid_propagate(False)
    lock_lbl = ctk.CTkLabel(
        lock_banner,
        text="",
        font=ctk.CTkFont(size=11),
        text_color="#fbbf24" if not theme.get("_is_light") else "#92400e",
    )
    lock_lbl.pack(padx=16, pady=6, anchor="w")
    lock_banner.grid_remove()

    if not hasattr(app, "_asm_panel_refreshers"):
        app._asm_panel_refreshers = {}
    app._asm_panel_refreshers[srv.id] = _refresh_action_btns
    _refresh_action_btns()

    # Linha separadora
    ctk.CTkFrame(parent, height=1, fg_color=sep).grid(
        row=2, column=0, sticky="ews")

    # ── Body: nav esquerda + conteúdo direito ─────────────────────────────────
    body = ctk.CTkFrame(parent, fg_color=surface_bg, corner_radius=0)
    body.grid(row=3, column=0, sticky="nsew")
    body.grid_columnconfigure(1, weight=1)
    body.grid_rowconfigure(0, weight=1)

    nav_frame = ctk.CTkScrollableFrame(
        body, fg_color=nav_bg, corner_radius=0, width=240,
        scrollbar_button_color=sep,
        border_width=1, border_color=card_border,
    )
    nav_frame.grid(row=0, column=0, sticky="nsew")
    nav_frame.grid_columnconfigure(0, weight=1)

    content_area = ctk.CTkFrame(
        body, fg_color=surface_bg, corner_radius=0,
        border_width=1, border_color=card_border,
    )
    content_area.grid(row=0, column=1, sticky="nsew", padx=(1, 0))
    content_area.grid_columnconfigure(0, weight=1)
    content_area.grid_rowconfigure(0, weight=1)

    if not hasattr(app, "_asm_panel_vars"):
        app._asm_panel_vars = {}
    app._asm_panel_vars[srv.id] = {}
    vars_ref = app._asm_panel_vars[srv.id]
    vars_ref["_app"] = app   # referência ao app para builders que precisam iniciar ações
    vars_ref["_panel_root"] = body
    vars_ref["_show_section_fn"] = None  # preenchido após _show_section existir

    _builders: dict[str, Callable] = {
        "Todas as opções":              _build_all_options,
        "Administração":                _build_administracao,
        "Mods (Workshop)":              _build_mods_workshop,
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
        "Coleta por Recurso":           _build_harvest_aggregated,
        "Multiplicadores por Classe": _build_dino_class_aggregated,
        "Spawn e Domesticação":       _build_spawn_tame_aggregated,
        "Custom GameUserSettings.ini":  _build_custom_gus,
        "Custom Game.ini":              _build_custom_game,
        "ARK Procedural (PGM)":         _build_pgm,
        "Extensões SM":                 _build_sm_extensions,
        "🦕 Gerador SpawnExact":        _build_tool_spawn_exact,
        "⚡ Console RCON":              _build_tool_rcon,
        "👥 Jogadores Online":          _build_tool_players,
    }

    # Lazy — scroll frame criado só na 1ª visita (evita 31× CTkScrollableFrame upfront)
    section_frames: dict[str, ctk.CTkScrollableFrame] = {}
    section_built: set[str] = set()
    _pending_section: list[str | None] = [None]
    _build_generation: list[int] = [0]
    _CHUNKED_SECTIONS = frozenset({
        "Todas as opções",
        "Regras",
        "Configurações do Jogador",
        "Configurações do Dino",
        "Meio Ambiente",
        "Estruturas",
        "Engramas",
        "Coleta por Recurso",
        "Multiplicadores por Classe",
        "Spawn e Domesticação",
        "Custom GameUserSettings.ini",
        "Custom Game.ini",
    })

    def _create_section_frame(name: str) -> ctk.CTkScrollableFrame:
        sf = section_frames.get(name)
        if sf is not None:
            return sf
        sf = ctk.CTkScrollableFrame(
            content_area,
            fg_color=panel_bg,
            corner_radius=10,
            border_width=1,
            border_color=card_border,
        )
        sf.grid_columnconfigure(0, weight=0)
        sf.grid_columnconfigure(1, weight=1)
        sf.grid_columnconfigure(2, weight=0)
        sf.grid_columnconfigure(3, weight=0)
        section_frames[name] = sf
        return sf

    loading_overlay = ctk.CTkFrame(content_area, fg_color=bg, corner_radius=0)
    loading_overlay.grid(row=0, column=0, sticky="nsew")
    loading_overlay.grid_columnconfigure(0, weight=1)
    loading_overlay.grid_rowconfigure(0, weight=1)
    loading_overlay.grid_remove()

    loading_inner = ctk.CTkFrame(loading_overlay, fg_color="transparent")
    loading_inner.grid(row=0, column=0)
    loading_lbl = ctk.CTkLabel(
        loading_inner, text="Carregando seção…",
        font=ctk.CTkFont(family="Segoe UI", size=13),
        text_color=t_sec,
    )
    loading_lbl.pack(pady=(0, 8))
    loading_prog = ctk.CTkProgressBar(loading_inner, width=220, height=8, mode="indeterminate")
    loading_prog.pack()
    loading_prog.set(0)

    _active_section: list[str] = [SECTIONS[0]]
    nav_buttons: dict[str, ctk.CTkButton] = {}
    nav_row_widgets: list[tk.Misc] = []
    _building: list[bool] = [False]

    def _set_loading(active: bool, section_name: str = "") -> None:
        if active:
            loading_lbl.configure(
                text=f"Carregando: {section_name}…" if section_name else "Carregando seção…"
            )
            loading_overlay.grid(row=0, column=0, sticky="nsew")
            loading_overlay.lift()
            try:
                loading_prog.configure(mode="indeterminate")
                loading_prog.set(0)
                loading_prog.start()
            except Exception:
                pass
        else:
            try:
                loading_prog.stop()
                loading_prog.configure(mode="indeterminate")
                loading_prog.set(0)
            except Exception:
                pass
            loading_overlay.grid_remove()

    def _update_loading_progress(done: int, total: int) -> None:
        if total <= 0:
            return
        try:
            loading_prog.stop()
            if str(loading_prog.cget("mode")) != "determinate":
                loading_prog.configure(mode="determinate")
            loading_prog.set(done / total)
            loading_lbl.configure(
                text=f"Carregando: {_pending_section[0] or _active_section[0]}… ({done}/{total})"
            )
        except Exception:
            pass

    def _clear_section_frame(sf: ctk.CTkScrollableFrame) -> None:
        for w in sf.winfo_children():
            try:
                w.destroy()
            except tk.TclError:
                pass

    def _on_build_error(name: str, gen: int, exc: BaseException | None = None) -> None:
        if gen != _build_generation[0]:
            return
        _building[0] = False
        _pending_section[0] = None
        _set_loading(False)
        section_built.discard(name)
        sf_err = section_frames.get(name)
        if sf_err is not None:
            _clear_section_frame(sf_err)
        if exc is not None:
            try:
                from tkinter import messagebox
                messagebox.showerror(
                    "Erro ao carregar seção",
                    f"Não foi possível montar «{name}».\n\n{exc}",
                    parent=content_area.winfo_toplevel(),
                )
            except Exception:
                pass

    def _on_build_cancelled(name: str, gen: int) -> None:
        if gen != _build_generation[0]:
            return
        _building[0] = False
        _pending_section[0] = None
        _set_loading(False)
        section_built.discard(name)

    def _ensure_section(
        name: str,
        on_done: Callable | None = None,
        *,
        gen: int = 0,
    ) -> None:
        if name in section_built:
            if on_done:
                on_done()
            return

        sf = _create_section_frame(name)
        _clear_section_frame(sf)
        builder = _builders.get(name)

        def _mark_done() -> None:
            if gen and gen != _build_generation[0]:
                return
            section_built.add(name)
            if on_done:
                on_done()

        if not builder:
            _mark_done()
            return

        from ..ui.perf_monitor import timed_build

        is_cancelled = (lambda g=gen: g != _build_generation[0]) if gen else None
        chunk_error = (lambda exc, n=name, g=gen: _on_build_error(n, g, exc))
        chunk_cancelled = (lambda n=name, g=gen: _on_build_cancelled(n, g))

        if name in _CHUNKED_SECTIONS:
            with timed_build("section_build_chunked", name):
                builder(
                    sf, srv, vars_ref, bg, accent,
                    on_done=_mark_done,
                    on_error=chunk_error,
                    on_cancelled=chunk_cancelled,
                    is_cancelled=is_cancelled,
                    on_progress=_update_loading_progress,
                )
            return

        with timed_build("section_build", name):
            builder(sf, srv, vars_ref, bg, accent)
        _mark_done()

    def _show_section_impl(name: str) -> None:
        old = _active_section[0]
        if old in section_frames:
            section_frames[old].grid_remove()
        if old in nav_buttons:
            nav_buttons[old].configure(fg_color="transparent", text_color=t_sec)
        if name in section_frames:
            section_frames[name].grid(row=0, column=0, sticky="nsew")
            try:
                from ..ui.server_field_widgets import refresh_scrollable_frame
                refresh_scrollable_frame(section_frames[name])
            except Exception:
                pass
        nav_buttons[name].configure(fg_color=acc_mb, text_color=accent)
        _active_section[0] = name

    def _finish_section_build(name: str, gen: int) -> None:
        if gen != _build_generation[0]:
            return
        _building[0] = False
        _pending_section[0] = None
        _set_loading(False)
        _show_section_impl(name)
        try:
            from ..ui.perf_monitor import get_perf_monitor
            get_perf_monitor().save_baseline()
        except Exception:
            pass

    def _start_section_build(name: str, *, cancel_previous: bool = False) -> None:
        if cancel_previous:
            _build_generation[0] += 1
        gen = _build_generation[0]
        _building[0] = True
        _pending_section[0] = name
        _set_loading(True, name)
        content_area.update_idletasks()

        def _deferred() -> None:
            if gen != _build_generation[0]:
                return
            try:
                _ensure_section(
                    name,
                    on_done=lambda: _finish_section_build(name, gen),
                    gen=gen,
                )
            except Exception as exc:
                _on_build_error(name, gen, exc)

        content_area.after(0, _deferred)

    def _show_section(name: str) -> None:
        if name in section_built:
            _show_section_impl(name)
            return
        if _building[0]:
            if _pending_section[0] == name:
                _building[0] = False
                _pending_section[0] = None
                _set_loading(False)
                section_built.discard(name)
                sf_retry = section_frames.get(name)
                if sf_retry is not None:
                    _clear_section_frame(sf_retry)
            else:
                _start_section_build(name, cancel_previous=True)
                return
        _start_section_build(name)

    vars_ref["_show_section_fn"] = _show_section

    from ..ui.server_field_labels import field_search_entries, section_search_index

    _search_index = section_search_index()
    _field_entries = field_search_entries()
    for sec in SECTIONS:
        _search_index.setdefault(sec, "")
        _search_index[sec] += " " + sec.lower()

    _group_sections: dict[str, list[str]] = {
        group_name: group_secs for group_name, group_secs in NAV_GROUPS
    }

    search_var = tk.StringVar(value="")
    _search_popup: list[ctk.CTkFrame | None] = [None]

    def _hide_search_popup() -> None:
        if _search_popup[0]:
            try:
                _search_popup[0].destroy()
            except tk.TclError:
                pass
            _search_popup[0] = None

    def _apply_nav_filter(*_args: object) -> None:
        q = search_var.get().strip().lower()
        _hide_search_popup()
        for w in nav_row_widgets:
            try:
                w.grid()
            except tk.TclError:
                pass
        if not q:
            return
        visible_sections: set[str] = set()
        for sec, blob in _search_index.items():
            if q in sec.lower() or q in blob:
                visible_sections.add(sec)
        for sec, btn in nav_buttons.items():
            if sec not in visible_sections:
                btn.grid_remove()
        for w in nav_row_widgets:
            if not isinstance(w, ctk.CTkLabel):
                continue
            grp = getattr(w, "_nav_group", "")
            if grp and not any(s in visible_sections for s in _group_sections.get(grp, [])):
                w.grid_remove()
        if len(q) >= 2:
            matches = [
                (key, sec, pt, blob)
                for key, sec, pt, blob in _field_entries
                if q in blob or q in pt.lower() or q in sec.lower() or q in key
            ][:12]
            if matches:
                n = min(len(matches), 8)
                outer = ctk.CTkFrame(
                    nav_frame, fg_color=panel_bg, corner_radius=8,
                    border_width=1, border_color=card_border,
                )
                outer.grid(row=999, column=0, padx=4, pady=4, sticky="ew")
                _search_popup[0] = outer
                for i, (key, sec, pt, _blob) in enumerate(matches[:n]):
                    def _go(section=sec, field=key):
                        _hide_search_popup()
                        search_var.set("")
                        _show_section(section)
                    row_fr = ctk.CTkFrame(outer, fg_color="transparent")
                    row_fr.pack(fill="x", padx=4, pady=1)
                    ctk.CTkButton(
                        row_fr, text=f"{pt}  →  {sec}", anchor="w",
                        fg_color="transparent", hover_color=nav_hover,
                        text_color=t_sec, font=ctk.CTkFont(size=10),
                        height=28, command=_go,
                    ).pack(fill="x")
                if len(matches) > n:
                    ctk.CTkLabel(
                        outer, text=f"+ {len(matches) - n} resultados — refine a busca",
                        font=ctk.CTkFont(size=9), text_color=t_mut,
                    ).pack(padx=8, pady=(2, 6))
    search_entry = ctk.CTkEntry(
        nav_frame, textvariable=search_var, placeholder_text="🔍  Buscar configuração…",
        height=30, font=ctk.CTkFont(family="Segoe UI", size=11),
        border_color=sep,
    )
    search_entry.grid(row=0, column=0, padx=6, pady=(8, 6), sticky="ew")
    nav_row_widgets.append(search_entry)
    search_var.trace_add("write", _apply_nav_filter)

    nav_row = 1
    for group_name, group_secs in NAV_GROUPS:
        grp_lbl = ctk.CTkLabel(
            nav_frame, text=group_name.upper(),
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=t_mut, anchor="w",
        )
        grp_lbl._nav_group = group_name  # type: ignore[attr-defined]
        grp_lbl.grid(row=nav_row, column=0, padx=(10, 4), pady=(10, 2), sticky="w")
        nav_row_widgets.append(grp_lbl)
        nav_row += 1

        for sec in group_secs:
            btn = ctk.CTkButton(
                nav_frame, text=sec, anchor="w",
                fg_color="transparent", hover_color=nav_hover,
                text_color=t_sec, font=ctk.CTkFont(family="Segoe UI", size=11),
                height=30, corner_radius=6,
                command=lambda s=sec: _show_section(s),
            )
            btn.grid(row=nav_row, column=0, padx=4, pady=1, sticky="ew")
            nav_buttons[sec] = btn
            nav_row_widgets.append(btn)
            nav_row += 1

    def _boot_panel() -> None:
        _start_section_build("Administração")

    content_area.after(0, _boot_panel)


# ════════════════════════════════════════════════════════════════════════════ #
#  Helpers de campo
# ════════════════════════════════════════════════════════════════════════════ #

# ── Instância padrão para comparar campos modificados (Fase 2) ────────────────
_DEFAULT_SRV = AsmServerConfig()
_MOD_DOT_COLOR = "#22d3ee"
_MOD_DOT_MUTED = "#0e4a5a"


def _attach_modified_badge(parent, var: tk.Variable, field: str, default_val, row: int) -> None:
    """Badge '●' e botão '↺' quando campo difere do padrão — colunas dedicadas."""
    badge = ctk.CTkLabel(parent, text="●", font=ctk.CTkFont(size=9),
                         text_color=_MOD_DOT_COLOR, width=12)
    reset = ctk.CTkButton(parent, text="↺", width=22, height=20,
                          fg_color="transparent", hover_color=_MOD_DOT_MUTED,
                          text_color=_MOD_DOT_COLOR, font=ctk.CTkFont(size=11),
                          cursor="hand2")

    def _check(*_):
        try:
            cur = var.get()
            if isinstance(default_val, bool):
                mod = bool(cur) != default_val
            elif isinstance(default_val, (int, float)):
                try:
                    mod = float(cur) != float(default_val)
                except (TypeError, ValueError):
                    mod = str(cur) != str(default_val)
            else:
                mod = str(cur) != str(default_val)
        except tk.TclError:
            mod = False
        if mod:
            badge.grid(row=row, column=2, padx=(4, 0), pady=3, sticky="w")
            reset.grid(row=row, column=3, padx=(2, 8), pady=3, sticky="w")
        else:
            badge.grid_remove()
            reset.grid_remove()

    def _reset():
        if isinstance(var, tk.BooleanVar):
            var.set(bool(default_val))
        else:
            var.set(str(default_val))

    reset.configure(command=_reset)
    var.trace_add("write", _check)
    _check()


def _field_label(field: str, label: str | None) -> str:
    if label is not None:
        return label
    return get_field_meta(field).pt


def _str_entry(parent, label, field, srv, vars_ref, row, accent,
               wide=False, pw=False, placeholder=""):
    from ..ui_constants import get_theme as _gt, tek_entry_kwargs
    _ek = tek_entry_kwargs(_gt("tek"))
    label = _field_label(field, label)
    ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(size=11), anchor="w").grid(
        row=row, column=0, padx=(8, 4), pady=3, sticky="w")
    v = tk.StringVar(value=str(getattr(srv, field, "")))
    vars_ref[field] = v
    ctk.CTkEntry(parent, textvariable=v, show="*" if pw else "",
                 placeholder_text=placeholder,
                 width=300 if wide else 200, **_ek).grid(
        row=row, column=1, padx=(0, 8), pady=3, sticky="ew" if wide else "w")
    if not pw:
        default = str(getattr(_DEFAULT_SRV, field, ""))
        _attach_modified_badge(parent, v, field, default, row)


def _int_entry(parent, label, field, srv, vars_ref, row):
    from ..ui_constants import get_theme as _gt, tek_entry_kwargs
    _ek = tek_entry_kwargs(_gt("tek"))
    label = _field_label(field, label)
    ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(size=11), anchor="w").grid(
        row=row, column=0, padx=(8, 4), pady=3, sticky="w")
    v = tk.StringVar(value=str(getattr(srv, field, 0)))
    vars_ref[field] = v
    ctk.CTkEntry(parent, textvariable=v, width=100, **_ek).grid(
        row=row, column=1, padx=(0, 8), pady=3, sticky="w")
    _attach_modified_badge(parent, v, field, getattr(_DEFAULT_SRV, field, 0), row)


def _float_entry(parent, label, field, srv, vars_ref, row):
    from ..ui_constants import get_theme as _gt, tek_entry_kwargs
    _ek = tek_entry_kwargs(_gt("tek"))
    label = _field_label(field, label)
    ctk.CTkLabel(parent, text=label, font=ctk.CTkFont(size=11), anchor="w").grid(
        row=row, column=0, padx=(8, 4), pady=3, sticky="w")
    v = tk.StringVar(value=str(getattr(srv, field, 1.0)))
    vars_ref[field] = v
    ctk.CTkEntry(parent, textvariable=v, width=100, **_ek).grid(
        row=row, column=1, padx=(0, 8), pady=3, sticky="w")
    _attach_modified_badge(parent, v, field, getattr(_DEFAULT_SRV, field, 1.0), row)


def _event_combo_entry(parent, srv, vars_ref, row, accent):
    """ActiveEvent — eventos oficiais ARK (FearEvolved, WinterWonderland, …)."""
    from ..ui_constants import _ARK_EVENT_ID_TO_LABEL, _ARK_OFFICIAL_EVENTS, get_theme as _gt, tek_entry_kwargs

    _ek = tek_entry_kwargs(_gt("tek"))

    ctk.CTkLabel(
        parent,
        text=get_field_meta("active_event").pt,
        font=ctk.CTkFont(size=11),
        anchor="w",
    ).grid(row=row, column=0, padx=(8, 4), pady=3, sticky="w")

    raw = (getattr(srv, "active_event", "") or "").strip()
    labels = [label for _, label in _ARK_OFFICIAL_EVENTS]
    display = _ARK_EVENT_ID_TO_LABEL.get(raw, raw) or labels[0]
    if display not in labels:
        display = labels[0]

    v = tk.StringVar(value=display)
    vars_ref["active_event"] = v
    ctk.CTkComboBox(
        parent,
        variable=v,
        values=labels,
        width=360,
        height=30,
        dropdown_font=ctk.CTkFont(size=12),
        button_color=accent,
        button_hover_color="#16a34a",
        **_ek,
    ).grid(row=row, column=1, padx=(0, 8), pady=3, sticky="w")

    default_id = (getattr(_DEFAULT_SRV, "active_event", "") or "").strip()
    default_display = _ARK_EVENT_ID_TO_LABEL.get(default_id, default_id) or labels[0]
    _attach_modified_badge(parent, v, "active_event", default_display, row)


def _bool_check(parent, label, field, srv, vars_ref, row, accent, col=0, colspan=2):
    label = _field_label(field, label)
    v = tk.BooleanVar(value=bool(getattr(srv, field, False)))
    vars_ref[field] = v
    frm = ctk.CTkFrame(parent, fg_color="transparent")
    frm.grid(row=row, column=col, columnspan=colspan, padx=(8, 4), pady=3, sticky="w")

    ctk.CTkCheckBox(frm, text=label, variable=v,
                    checkmark_color=accent, border_color=accent,
                    font=ctk.CTkFont(size=11)).pack(side="left")

    badge = ctk.CTkLabel(frm, text="●", font=ctk.CTkFont(size=9),
                         text_color=_MOD_DOT_COLOR, width=14)
    reset = ctk.CTkButton(frm, text="↺", width=22, height=20,
                          fg_color="transparent", hover_color=_MOD_DOT_MUTED,
                          text_color=_MOD_DOT_COLOR, font=ctk.CTkFont(size=11),
                          cursor="hand2")
    default = bool(getattr(_DEFAULT_SRV, field, False))

    def _check(*_):
        mod = bool(v.get()) != default
        if mod:
            badge.pack(side="left", padx=(6, 0))
            reset.pack(side="left", padx=(2, 0))
        else:
            badge.pack_forget()
            reset.pack_forget()

    reset.configure(command=lambda: v.set(default))
    v.trace_add("write", _check)
    _check()


def _section_label(parent, text, row, accent):
    from ..ui_constants import get_theme as _gt
    th = _gt("tek")
    wrap = ctk.CTkFrame(parent, fg_color="transparent")
    wrap.grid(row=row, column=0, columnspan=4, padx=8, pady=(10, 4), sticky="ew")
    ctk.CTkLabel(
        wrap, text=text,
        font=ctk.CTkFont(size=12, weight="bold"),
        text_color=accent,
    ).pack(anchor="w")
    ctk.CTkFrame(wrap, height=1, fg_color=th.get("separator", "#64748b")).pack(
        fill="x", pady=(4, 0))


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
#  Seção 0 — Todas as opções (visão plana)
# ════════════════════════════════════════════════════════════════════════════ #

def _build_all_options(sf, srv, vars_ref, bg, accent, *, on_done=None, is_cancelled=None, on_progress=None, on_error=None, on_cancelled=None):
    from ..ui.tek_all_options_section import build_all_options_section

    show_section = vars_ref.get("_show_section_fn")
    build_all_options_section(
        sf, srv, vars_ref, accent,
        on_goto_section=show_section if callable(show_section) else None,
        on_done=on_done,
        is_cancelled=is_cancelled,
        on_progress=on_progress,
        on_error=on_error,
        on_cancelled=on_cancelled,
    )


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 1 — Administração
# ════════════════════════════════════════════════════════════════════════════ #

def _build_administracao(sf, srv, vars_ref, bg, accent):
    _section_label(sf, "Identificação", 0, accent)
    _str_entry(sf, "Nome no gerenciador",      "name",             srv, vars_ref,  1, accent, wide=True)
    _str_entry(sf, "Pasta de instalação",      "install_dir",      srv, vars_ref,  2, accent, wide=True)
    _str_entry(sf, "Pasta custom de INI (ASE)", "user_config_folder", srv, vars_ref, 3, accent, wide=True)

    # ── Seletor visual de mapa ────────────────────────────────────────────────
    _section_label(sf, "Mapa", 4, accent)
    map_var = tk.StringVar(value=srv.server_map)
    vars_ref["server_map"] = map_var

    map_display_f = ctk.CTkFrame(sf, fg_color="transparent")
    map_display_f.grid(row=5, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="ew")

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
    manual_f.grid(row=6, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="ew")
    ctk.CTkLabel(manual_f, text="Mapa (vanilla ou mod):",
                 font=ctk.CTkFont(size=10), text_color="#64748b").pack(side="left", padx=(0, 6))
    manual_entry = ctk.CTkEntry(manual_f, textvariable=map_var, width=280,
                                placeholder_text="TheIsland  ou  /Game/Mods/123456/funny_map")
    manual_entry.pack(side="left")

    _str_entry(sf, None, "total_conversion_mod_id", srv, vars_ref, 7, accent)

    _section_label(sf, "Sessão",          8, accent)
    _str_entry(sf, None, "session_name",     srv, vars_ref,  9, accent, wide=True)
    _float_entry(sf, None, "auto_save_period", srv, vars_ref, 10)

    _section_label(sf, "Evento sazonal ARK",  11, accent)
    _event_combo_entry(sf, srv, vars_ref, 12, accent)

    _section_label(sf, "Rede",           13, accent)
    _int_entry(sf,   "Porta (game)",           "server_port",      srv, vars_ref, 14)

    # Porta peer — sempre game_port + 1, read-only
    _peer_row = 15
    ctk.CTkLabel(sf, text="Porta (peer)", font=ctk.CTkFont(size=11), anchor="w").grid(
        row=_peer_row, column=0, padx=(8, 4), pady=3, sticky="w")
    _peer_var = tk.StringVar(value=str(getattr(srv, "server_port", 7777) + 1))
    _peer_entry = ctk.CTkEntry(sf, textvariable=_peer_var, width=100,
                               state="disabled", text_color="#475569")
    _peer_entry.grid(row=_peer_row, column=1, padx=(0, 8), pady=3, sticky="w")
    ctk.CTkLabel(sf, text="(game + 1, automático)", font=ctk.CTkFont(size=9),
                 text_color="#475569").grid(row=_peer_row, column=2, columnspan=2, padx=(4, 8), pady=3, sticky="w")
    # Atualiza peer quando game_port muda
    def _on_game_port_change(*_):
        try:
            _peer_var.set(str(int(vars_ref["server_port"].get()) + 1))
        except ValueError:
            pass
    vars_ref["server_port"].trace_add("write", _on_game_port_change)

    _int_entry(sf,   None, "query_port",       srv, vars_ref, 17)
    _int_entry(sf,   "Max jogadores",          "max_players",      srv, vars_ref, 18)

    # ── IP Bind com botão de detecção automática ─────────────────────────────
    ctk.CTkLabel(sf, text=get_field_meta("server_ip").pt, font=ctk.CTkFont(size=11), anchor="w").grid(
        row=19, column=0, padx=(8, 4), pady=3, sticky="w")
    _ip_var = tk.StringVar(value=str(getattr(srv, "server_ip", "")))
    vars_ref["server_ip"] = _ip_var
    _ip_frame = ctk.CTkFrame(sf, fg_color="transparent")
    _ip_frame.grid(row=19, column=1, padx=(0, 8), pady=3, sticky="w")
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

    _section_label(sf, "Senhas",         20, accent)
    _str_entry(sf, "Senha do servidor",        "server_password",  srv, vars_ref, 21, accent, pw=True)
    _str_entry(sf, "Senha admin",              "admin_password",   srv, vars_ref, 22, accent, pw=True)
    _str_entry(sf, "Senha spectator",          "spectator_password", srv, vars_ref, 23, accent, pw=True)

    _section_label(sf, "RCON",           24, accent)
    _bool_check(sf,  None, "rcon_enabled",     srv, vars_ref, 25, accent)
    _int_entry(sf,   None, "rcon_port",        srv, vars_ref, 26)
    _int_entry(sf,   None, "rcon_log_buffer",  srv, vars_ref, 27)

    _section_label(sf, "Logs / Admin",   28, accent)
    _bool_check(sf,  None, "admin_logging",    srv, vars_ref, 29, accent)
    _int_entry(sf,   None, "max_tribe_logs",   srv, vars_ref, 30)
    _bool_check(sf, "Log estruturas destruídas por inimigos", "tribe_log_destroyed_enemy_structures", srv, vars_ref, 31, accent)
    _bool_check(sf, "Ocultar fonte de dano nos logs",         "allow_hide_damage_source",             srv, vars_ref, 32, accent)

    _section_label(sf, "Extinção / Respawn de dinos", 33, accent)
    _bool_check(sf,  "Evento de extinção",      "enable_extinction_event",         srv, vars_ref, 34, accent)
    _int_entry(sf,   "Intervalo extinção (s)",  "extinction_event_interval",        srv, vars_ref, 35)
    _int_entry(sf,   "Próximo evento (UTC)",    "extinction_event_utc",             srv, vars_ref, 36)
    _bool_check(sf, "Forçar respawn dinos selvagens",  "enable_auto_respawn_wild_dinos",  srv, vars_ref, 37, accent)
    _int_entry(sf,   "Intervalo respawn (s)",   "auto_respawn_wild_dinos_interval", srv, vars_ref, 38)

    _section_label(sf, "Jogadores Ociosos", 39, accent)
    _bool_check(sf,  "Kickar ociosos",          "enable_kick_idle_players",         srv, vars_ref, 40, accent)
    _float_entry(sf, "Período idle kick (s)",   "kick_idle_players",                srv, vars_ref, 41)

    from ..ui.cluster_server_section import build_server_cluster_link_asm
    _branch_row = build_server_cluster_link_asm(sf, srv, vars_ref, accent, 42)
    _section_label(sf, "Branch SteamCMD (Beta)", _branch_row, accent)
    _branch_btn_row = ctk.CTkFrame(sf, fg_color="transparent")
    _branch_btn_row.grid(row=_branch_row + 1, column=0, columnspan=2, padx=8, pady=(2, 4), sticky="w")

    def _set_branch(val: str) -> None:
        br = vars_ref.get("branch_name")
        if br is not None:
            br.set(val)
        pw = vars_ref.get("branch_password")
        if pw is not None and not val:
            pw.set("")

    ctk.CTkButton(
        _branch_btn_row, text="✅  Padrão (Estável)", width=160, height=28,
        fg_color="#14532d", hover_color="#166534",
        command=lambda: _set_branch(""),
    ).pack(side="left", padx=(0, 8))
    ctk.CTkButton(
        _branch_btn_row, text="🦕  Pre-Aquatica", width=150, height=28,
        fg_color="#7a3a10", hover_color="#9a4a18",
        command=lambda: _set_branch("preaquatica"),
    ).pack(side="left")

    _str_entry(sf, None, "branch_name",     srv, vars_ref, _branch_row + 2, accent)
    _str_entry(sf, None, "branch_password", srv, vars_ref, _branch_row + 3, accent, pw=True)
    ctk.CTkLabel(
        sf,
        text="preaquatica = ASE v358 (última com ArkApi/plugins). Vazio = versão estável atual.",
        font=ctk.CTkFont(size=10), text_color="#64748b", anchor="w", wraplength=520,
    ).grid(row=_branch_row + 4, column=0, columnspan=2, padx=8, pady=(0, 4), sticky="w")

    def _build_admin_tail() -> None:
        from ..ui.tek_cli_section import build_cli_avancado_section
        _cli_start = max(_branch_row + 5, sf.grid_size()[1])
        _cli_next = build_cli_avancado_section(sf, srv, vars_ref, accent, _cli_start)
        _section_label(sf, "Args CLI adicionais", _cli_next, accent)
        _str_entry(sf, None, "additional_args", srv, vars_ref, _cli_next + 1, accent, wide=True)

        _pers_row = _cli_next + 2
        _section_label(sf, "Personalização do Card", _pers_row, accent)
        _str_entry(sf, "Cor do card (hex, ex: #22c55e)", "color", srv, vars_ref, _pers_row + 1, accent)

        _tags_row = _pers_row + 2
        ctk.CTkLabel(sf, text="Etiquetas (separadas por vírgula)",
                     font=ctk.CTkFont(size=11), anchor="w").grid(
            row=_tags_row, column=0, padx=(8, 4), pady=3, sticky="w")
        tags_var = tk.StringVar(value=", ".join(getattr(srv, "tags", [])))
        vars_ref["_tags_csv"] = tags_var
        ctk.CTkEntry(sf, textvariable=tags_var).grid(
            row=_tags_row, column=1, padx=(0, 8), pady=3, sticky="ew")

        _section_label(sf, "Ações do Servidor", _tags_row + 1, accent)

        def _do_install():
            from .asm_steamcmd_ui import start_server_install
            start_server_install(vars_ref.get("_app"), srv)

        def _do_mods():
            from .asm_steamcmd_ui import start_mods_download
            start_mods_download(vars_ref.get("_app"), srv)

        def _do_validate():
            from .asm_steamcmd_ui import start_server_validate
            start_server_validate(vars_ref.get("_app"), srv)

        btn_row = ctk.CTkFrame(sf, fg_color="transparent")
        btn_row.grid(row=_tags_row + 2, column=0, columnspan=2, padx=8, pady=4, sticky="w")
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
            ("Pasta de instalação", "Diretório raiz do servidor ARK (contém ShooterGame/)."),
            ("Mapa", "Mapa do servidor. Use o seletor visual ou digite o nome interno."),
            ("Evento sazonal ARK", "ActiveEvent — ativa eventos oficiais (Fear Evolved, Winter Wonderland, etc.) na linha de comando e no INI."),
            ("RCON", "Console remoto — necessário para ferramentas de administração in-game."),
            ("Mods", "Use a seção Mods (Workshop) na barra lateral para gerenciar mods."),
        ], _tags_row + 3)

    sf.after(0, _build_admin_tail)


def _build_mods_workshop(sf, srv, vars_ref, bg, accent):
    from .asm_mods_section import build_mods_workshop_section
    build_mods_workshop_section(sf, srv, vars_ref, accent)


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 2 — Gerenciamento Automático
# ════════════════════════════════════════════════════════════════════════════ #

_AUTO_RESTART_DAY_LABELS: tuple[tuple[str, int], ...] = (
    ("Seg", 0), ("Ter", 1), ("Qua", 2), ("Qui", 3),
    ("Sex", 4), ("Sáb", 5), ("Dom", 6),
)


def _build_auto_restart_days(parent, srv, vars_ref, row: int, accent: str, theme: dict) -> int:
    """Checkboxes de dias da semana para reinício programado."""
    card = ctk.CTkFrame(
        parent,
        fg_color=theme.get("card_bg", "#0d1b2a"),
        corner_radius=10,
        border_width=1,
        border_color=theme.get("card_border", "#1e293b"),
    )
    card.grid(row=row, column=0, columnspan=2, padx=8, pady=6, sticky="ew")
    card.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        card, text="Dias da semana (reinício)",
        font=ctk.CTkFont(size=11, weight="bold"), text_color=accent, anchor="w",
    ).grid(row=0, column=0, padx=12, pady=(8, 4), sticky="w")

    days_row = ctk.CTkFrame(card, fg_color="transparent")
    days_row.grid(row=1, column=0, padx=8, pady=(0, 10), sticky="ew")

    enabled = set(getattr(srv, "auto_restart_days", None) or list(range(7)))
    day_vars: dict[int, tk.BooleanVar] = {}
    for label, idx in _AUTO_RESTART_DAY_LABELS:
        var = tk.BooleanVar(value=idx in enabled)
        day_vars[idx] = var
        ctk.CTkCheckBox(
            days_row, text=label, variable=var, width=52,
            font=ctk.CTkFont(size=11),
            checkbox_width=18, checkbox_height=18,
        ).pack(side="left", padx=(4, 6), pady=2)

    vars_ref["_auto_restart_day_vars"] = day_vars
    return row + 1


def _build_auto_management(sf, srv, vars_ref, bg, accent):
    from ..ui.server_field_widgets import CardSpec, add_collapsible_help, begin_tek_section, build_cards_layout

    ctx = begin_tek_section(sf, srv, vars_ref, accent, "Gerenciamento Automático", "Gerenciamento automático")
    row = build_cards_layout(sf, ctx, [
        CardSpec("Reinício programado", ["enable_auto_restart", "auto_restart_time", "restart_countdown_minutes"]),
        CardSpec("Atualização automática", ["enable_auto_update_check", "auto_update_check_minutes"]),
        CardSpec("Notificações", ["notify_discord_on_events"], bool_grid=True),
        CardSpec("Desempenho do processo", ["process_priority"]),
    ])
    row = _build_auto_restart_days(sf, srv, vars_ref, row, accent, ctx.theme)
    perf_card = ctk.CTkFrame(sf, fg_color=ctx.theme.get("card_bg", "#0d1b2a"), corner_radius=10,
                             border_width=1, border_color=ctx.theme.get("card_border", "#1e293b"))
    perf_card.grid(row=row, column=0, columnspan=2, padx=8, pady=6, sticky="ew")
    ctk.CTkLabel(
        perf_card, text="Afinidade de CPU (núcleos)",
        font=ctk.CTkFont(size=11, weight="bold"), text_color=accent, anchor="w",
    ).grid(row=0, column=0, padx=12, pady=(8, 4), sticky="w")
    cores = getattr(srv, "cpu_affinity_cores", []) or []
    cores_var = tk.StringVar(value=", ".join(str(c) for c in cores))
    vars_ref["_cpu_affinity_csv"] = cores_var
    ctk.CTkEntry(
        perf_card, textvariable=cores_var, placeholder_text="vazio = todos os núcleos (ex: 0, 2, 4)",
    ).grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")
    perf_card.grid_columnconfigure(0, weight=1)
    row += 1
    add_collapsible_help(sf, [
        ("Reinício automático", "Reinicia o servidor no horário configurado (HH:MM, 24h) nos dias marcados."),
        ("Dias da semana", "Marque em quais dias o reinício programado deve ocorrer."),
        ("Contagem regressiva", "Avisa os jogadores X minutos antes do reinício via mensagem no chat."),
        ("Verificar atualizações", "Checa periodicamente se há nova versão do servidor no Steam."),
        ("Notificar via Discord", "Envia mensagem no canal Discord quando eventos ocorrem."),
        ("Afinidade de CPU", "Lista de índices de núcleos separados por vírgula. Deixe vazio para usar todos."),
        ("Prioridade do processo", "Eleva a prioridade no Windows. «realtime» requer cuidado em produção."),
    ], row)


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 3 — Discord Bot
# ════════════════════════════════════════════════════════════════════════════ #

def _build_discord(sf, srv, vars_ref, bg, accent):
    from ..ui.server_field_widgets import CardSpec, add_collapsible_help, begin_tek_section, build_cards_layout

    ctx = begin_tek_section(sf, srv, vars_ref, accent, "Detalhes do Discord Bot", "Discord Bot")
    row = build_cards_layout(sf, ctx, [
        CardSpec("Webhook", ["discord_webhook_url"]),
        CardSpec("Eventos a notificar", [
            "discord_notify_server_start", "discord_notify_server_stop",
            "discord_notify_player_join", "discord_notify_player_leave",
        ], bool_grid=True),
    ])
    add_collapsible_help(sf, [
        ("URL do Webhook", "Discord → Integrações → Webhooks → Copiar URL."),
        ("Servidor iniciado/parado", "Notifica quando o processo do servidor inicia ou encerra."),
        ("Jogador entrou / saiu", "Notifica quando um jogador entra ou sai do servidor."),
    ], row)


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 4 — Detalhes do Servidor
# ════════════════════════════════════════════════════════════════════════════ #

def _build_server_details(sf, srv, vars_ref, bg, accent):
    from ..ui.server_field_widgets import (
        CardSpec, add_collapsible_help, add_int_field, begin_tek_section, build_cards_layout,
        make_card, add_card_header,
    )

    ctx = begin_tek_section(sf, srv, vars_ref, accent, "Detalhes do Servidor", "Detalhes do servidor")

    motd_card = make_card(sf, 1, 0, ctx.theme)
    motd_card.grid(columnspan=2, sticky="ew")
    add_card_header(motd_card, "MOTD — Mensagem do Dia", accent)
    ctk.CTkLabel(motd_card, text="Exibida ao jogador ao entrar no servidor (GameUserSettings.ini)",
                 font=ctk.CTkFont(size=10), text_color=ctx.theme["text_muted"]).grid(
        row=1, column=0, padx=12, pady=(0, 4), sticky="w")
    motd_box = ctk.CTkTextbox(motd_card, height=160, font=ctk.CTkFont(size=11))
    motd_box.grid(row=2, column=0, padx=12, pady=(0, 8), sticky="ew")
    motd_box.insert("1.0", srv.motd)
    vars_ref["_motd_text"] = motd_box
    add_int_field(ctx, motd_card, "motd_duration", 3)

    row = build_cards_layout(sf, ctx, [
        CardSpec("BanList", ["enable_ban_list_url", "ban_list_url"]),
    ], start_row=2)

    branch_hint = make_card(sf, row, 0, ctx.theme)
    branch_hint.grid(columnspan=2, sticky="ew")
    add_card_header(branch_hint, "Branch SteamCMD", accent)
    ctk.CTkLabel(
        branch_hint,
        text="Configure a branch (Estável / Pre-Aquatica) em Administração → Branch SteamCMD.",
        font=ctk.CTkFont(size=10), text_color=ctx.theme["text_muted"], anchor="w", wraplength=520,
    ).grid(row=1, column=0, padx=12, pady=(4, 10), sticky="w")
    row += 1

    notes_card = make_card(sf, row, 0, ctx.theme)
    notes_card.grid(columnspan=2, sticky="ew")
    add_card_header(notes_card, "Notas internas", accent)
    ctk.CTkLabel(notes_card, text="Apenas referência — não afeta o servidor",
                 font=ctk.CTkFont(size=10), text_color=ctx.theme["text_muted"]).grid(
        row=1, column=0, padx=12, pady=(0, 4), sticky="w")
    notes_box = ctk.CTkTextbox(notes_card, height=60, font=ctk.CTkFont(size=11))
    notes_box.grid(row=2, column=0, padx=12, pady=(0, 10), sticky="ew")
    notes_box.insert("1.0", srv.notes)
    vars_ref["_notes_text"] = notes_box

    add_collapsible_help(sf, [
        ("MOTD", "Mensagem ao entrar. Duração em segundos."),
        ("Lista de ban (URL)", "URL de lista global de SteamIDs banidos."),
        ("Branch do SteamCMD", "Atalhos e campos em Administração (evita duplicar configuração)."),
        ("Notas internas", "Campo livre para sua referência."),
    ], row + 1)


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 5 — Regras
# ════════════════════════════════════════════════════════════════════════════ #

def _build_rules(sf, srv, vars_ref, bg, accent, *, on_done=None, is_cancelled=None, on_progress=None, on_error=None, on_cancelled=None):
    from ..ui.server_field_widgets import (
        CardSpec, add_collapsible_help, begin_tek_section, build_cards_layout_chunked,
    )

    ctx = begin_tek_section(sf, srv, vars_ref, accent, "Regras", "Regras do servidor")
    cards = [
        CardSpec("Modo de jogo", [
            "enable_pvp", "enable_hardcore", "allow_cave_building_pve",
            "disable_friendly_fire_pvp", "disable_friendly_fire_pve", "disable_loot_crates",
            "enable_extra_structure_prevention_volumes",
        ], bool_grid=True),
        CardSpec("Dificuldade", [
            "enable_difficulty_override", "override_official_difficulty", "difficulty_offset",
        ]),
        CardSpec("Tribos", [
            "max_tribe_size", "allow_tribe_alliances", "max_alliances_per_tribe",
            "max_tribes_per_alliance", "allow_tribe_war_pve", "allow_tribe_war_cancel_pve",
            "tribe_name_change_cooldown",
        ]),
        CardSpec("PvP respawn", [
            "increase_pvp_respawn_interval", "pvp_respawn_check_period",
            "pvp_respawn_multiplier", "pvp_respawn_base_amount",
        ]),
        CardSpec("PvP offline", [
            "prevent_pvp_offline", "prevent_pvp_offline_interval",
            "prevent_pvp_offline_invincible_interval",
            "enable_cryo_sickness_pvp",
        ]),
        CardSpec("PvE auto timer", [
            "auto_pve_timer", "auto_pve_use_system_time",
            "auto_pve_start_time", "auto_pve_stop_time",
        ]),
        CardSpec("Doenças / gamma", [
            "enable_diseases", "non_permanent_diseases", "allow_pvp_gamma", "allow_pve_gamma",
        ], bool_grid=True),
        CardSpec("Receitas / stasis", [
            "allow_custom_recipes", "custom_recipe_effectiveness_multiplier",
            "custom_recipe_skill_multiplier", "override_npc_stasis_range_scale",
            "npc_stasis_range_scale_start", "npc_stasis_range_scale_end",
            "npc_stasis_range_scale_percent_end",
        ]),
        CardSpec("Miscelânea", [
            "oxygen_swim_speed_stat_multiplier", "supply_crate_loot_quality_multiplier",
            "fishing_loot_quality_multiplier", "use_corpse_life_span_multiplier",
            "global_powered_battery_durability_decrease", "random_supply_crate_points",
            "use_corpse_locator", "prevent_spawn_animations", "allow_unlimited_respecs",
        ]),
    ]
    help_items = [
        ("PvP / PvE", "Modo principal — PvP permite atacar outros jogadores."),
        ("Modo hardcore", "Ao morrer, o personagem volta ao nível 1."),
        ("Dificuldade oficial", "Nível máx. dos dinos selvagens. 5.0 ≈ nível 150."),
        ("Offset de dificuldade", "Modificador adicional (0.0–1.0)."),
        ("Máx. membros na tribo", "0 = sem limite."),
        ("PvP offline", "Protege bases quando a tribo está offline."),
        ("Timer automático PvE", "Alterna PvP/PvE nos horários (segundos desde meia-noite)."),
        ("Marcador de cadáver", "Mostra no mapa onde você morreu."),
        ("Respecs ilimitados", "Mindwipe Tonic sem limite de uso."),
    ]

    def _after_cards(row: int) -> None:
        add_collapsible_help(sf, help_items, row)
        if on_done:
            on_done()

    build_cards_layout_chunked(
        sf, ctx, cards,
        on_complete=_after_cards,
        is_cancelled=is_cancelled,
        on_progress=on_progress,
        on_error=on_error,
        on_cancelled=on_cancelled,
        chunk_size=1,
    )


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 6 — Transferências / Tributo
# ════════════════════════════════════════════════════════════════════════════ #

def _build_transfers(sf, srv, vars_ref, bg, accent):
    from ..ui.server_field_widgets import CardSpec, add_collapsible_help, begin_tek_section, build_cards_layout

    ctx = begin_tek_section(sf, srv, vars_ref, accent, "Transferências / Tributo", "Transferências e tributo")
    row = build_cards_layout(sf, ctx, [
        CardSpec("Tributo geral", ["enable_tribute_downloads"], bool_grid=True),
        CardSpec("Bloquear download", [
            "prevent_download_survivors", "prevent_download_items", "prevent_download_dinos",
        ], bool_grid=True),
        CardSpec("Bloquear upload", [
            "prevent_upload_survivors", "prevent_upload_items", "prevent_upload_dinos",
        ], bool_grid=True),
        CardSpec("Cluster", ["cross_ark_allow_foreign_dino_downloads"], bool_grid=True),
        CardSpec("Expiração — personagens", ["save_tribute_char_expiration", "tribute_char_expiration_seconds"]),
        CardSpec("Expiração — items", ["save_tribute_item_expiration", "tribute_item_expiration_seconds"]),
        CardSpec("Expiração — dinos", ["save_tribute_dino_expiration", "tribute_dino_expiration_seconds"]),
        CardSpec("Re-upload de dinos", ["save_min_dino_reupload_interval", "min_dino_reupload_interval"]),
        CardSpec("Acesso exclusivo", ["exclusive_join"], bool_grid=True),
    ])
    add_collapsible_help(sf, [
        ("Downloads de tributo", "Interruptor geral do terminal/obelisco. Desmarque para bloquear toda viagem."),
        ("Download / upload", "Controle fino por tipo: personagem, itens ou dinos."),
        ("Dinos estrangeiros", "Permite baixar dinos de servidores fora do cluster configurado."),
        ("Expiração de tributo", "Remove automaticamente após o tempo configurado."),
        ("Re-upload de dino", "Tempo mínimo entre uploads do mesmo dino."),
        ("Acesso exclusivo", "Somente SteamIDs na whitelist podem entrar."),
        ("Cross-ARK", "Cluster ID e pasta compartilhada: menu Clusters."),
    ], row)


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 7 — Bate-papo e Notificações
# ════════════════════════════════════════════════════════════════════════════ #

def _build_chat(sf, srv, vars_ref, bg, accent):
    from ..ui.server_field_widgets import CardSpec, add_collapsible_help, begin_tek_section, build_cards_layout

    ctx = begin_tek_section(sf, srv, vars_ref, accent, "Bate-papo e Notificações", "Bate-papo e notificações")
    row = build_cards_layout(sf, ctx, [
        CardSpec("Chat e notificações", [
            "global_voice_chat", "proximity_chat",
            "player_joined_notifications", "player_leave_notifications",
        ], bool_grid=True),
    ])
    add_collapsible_help(sf, [
        ("Chat de voz global", "Todos os jogadores ouvem a voz, independente da distância."),
        ("Chat por proximidade", "Somente jogadores próximos ouvem mensagens e voz."),
        ("Notificar entrada/saída", "Mensagem no chat quando um jogador entra ou sai."),
    ], row)


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 8 — HUD e Visuais
# ════════════════════════════════════════════════════════════════════════════ #

def _build_hud(sf, srv, vars_ref, bg, accent):
    from ..ui.server_field_widgets import CardSpec, add_collapsible_help, begin_tek_section, build_cards_layout

    ctx = begin_tek_section(sf, srv, vars_ref, accent, "HUD e Visuais", "HUD e visuais")
    row = build_cards_layout(sf, ctx, [
        CardSpec("HUD / visual", [
            "allow_crosshair", "allow_hud", "allow_third_person_view",
            "show_map_player_location", "show_floating_damage_text", "allow_hit_markers",
        ], bool_grid=True),
    ])
    add_collapsible_help(sf, [
        ("Mira", "Exibe a mira na tela dos jogadores."),
        ("HUD habilitado", "Barras de vida, stamina, comida e indicadores."),
        ("Terceira pessoa", "Permite câmera em terceira pessoa."),
        ("Posição no mapa", "Mostra a localização do jogador no mapa."),
        ("Texto flutuante de dano", "Números de dano flutuando sobre os alvos."),
        ("Marcadores de acerto", "Indicador visual quando um acerto é registrado."),
    ], row)


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

def _build_players(sf, srv, vars_ref, bg, accent, *, on_done=None, is_cancelled=None, on_progress=None, on_error=None, on_cancelled=None):
    from ..ui.server_field_widgets import (
        add_bool_field, add_card_header, add_collapsible_help, add_float_field,
        add_int_field, build_per_level_accordion, init_panel_context,
        make_card, run_ui_tasks_chunked, section_title, setup_dual_column_parent,
    )

    setup_dual_column_parent(sf)
    ctx = init_panel_context(
        sf, srv, vars_ref, accent, "Configurações do Jogador",
        vars_ref.get("_panel_root"),
    )
    section_title(sf, "Configurações do Jogador", accent, 0)

    def _card_mult() -> None:
        card = make_card(sf, 1, 0, ctx.theme)
        add_card_header(card, "Multiplicadores", accent)
        for i, fld in enumerate([
            "xp_multiplier", "player_damage_multiplier", "player_resistance_multiplier",
            "player_water_drain_multiplier", "player_food_drain_multiplier",
            "player_stamina_drain_multiplier", "player_health_recovery_multiplier",
            "player_harvesting_damage_multiplier", "crafting_skill_bonus_multiplier",
        ], start=1):
            add_float_field(ctx, card, fld, i)

    def _card_xp() -> None:
        card = make_card(sf, 1, 1, ctx.theme)
        add_card_header(card, "XP por tipo", accent)
        for i, fld in enumerate([
            "craft_xp_multiplier", "generic_xp_multiplier", "harvest_xp_multiplier",
            "kill_xp_multiplier", "special_xp_multiplier",
        ], start=1):
            add_float_field(ctx, card, fld, i)

    def _card_lim() -> None:
        from ..ui.player_level_panel import build_tek_player_level_section

        card = make_card(sf, 2, 0, ctx.theme)
        card.grid(columnspan=2, sticky="nsew")
        add_card_header(card, "Nível máximo do jogador", accent)
        next_row = build_tek_player_level_section(ctx, card, start_row=1)
        add_bool_field(ctx, card, "enable_flyer_carry", next_row)

    def _accordion() -> None:
        build_per_level_accordion(
            ctx, sf, 3,
            [("Pts/nível", "per_level_player")],
            "Quanto cada atributo cresce por ponto aplicado pelo jogador (1.0 = padrão).",
        )

    def _help() -> None:
        add_collapsible_help(sf, [
            ("Multiplicadores (1,0 = vanilla)", "Valores acima de 1,0 aumentam o atributo; abaixo diminuem."),
            ("Multiplicador de XP", "Multiplicador geral de XP. Outros tipos são aplicados adicionalmente."),
            ("Nível base / total", "Nível base sem bônus; o total inclui ascensões γ/β/α (+5 cada) e extras."),
            ("Pontos por nível", "Crescimento por ponto investido. 1,0 = vanilla."),
            ("Carregar com voador (PvE)", "Voadores podem carregar outros dinos em PvE."),
        ], 4)

    run_ui_tasks_chunked(
        sf,
        [_card_mult, _card_xp, _card_lim, _accordion, _help],
        on_done=on_done,
        is_cancelled=is_cancelled,
        on_progress=on_progress,
        on_error=on_error,
        on_cancelled=on_cancelled,
        chunk_size=1,
    )


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 10 — Configurações do Dino
# ════════════════════════════════════════════════════════════════════════════ #

def _build_dinos(sf, srv, vars_ref, bg, accent, *, on_done=None, is_cancelled=None, on_progress=None, on_error=None, on_cancelled=None):
    from ..ui.server_field_widgets import (
        add_bool_field, add_card_header, add_collapsible_help, add_float_field,
        add_int_field, build_per_level_accordion, init_panel_context,
        make_card, run_ui_tasks_chunked, section_title, setup_dual_column_parent,
    )

    setup_dual_column_parent(sf)
    ctx = init_panel_context(
        sf, srv, vars_ref, accent, "Configurações do Dino",
        vars_ref.get("_panel_root"),
    )
    section_title(sf, "Configurações do Dino", accent, 0)

    def _card_dmg() -> None:
        card = make_card(sf, 1, 0, ctx.theme)
        add_card_header(card, "Dano e resistência", accent)
        for i, fld in enumerate([
            "dino_damage_multiplier", "tamed_dino_damage_multiplier",
            "dino_resistance_multiplier", "tamed_dino_resistance_multiplier",
            "dino_turret_damage_multiplier", "dino_harvesting_damage_multiplier",
        ], start=1):
            add_float_field(ctx, card, fld, i)

    def _card_surv() -> None:
        card = make_card(sf, 1, 1, ctx.theme)
        add_card_header(card, "Sobrevivência", accent)
        for i, fld in enumerate([
            "dino_char_food_drain_multiplier", "dino_char_stamina_drain_multiplier",
            "dino_char_health_recovery_multiplier", "wild_dino_char_food_drain_multiplier",
            "tamed_dino_char_food_drain_multiplier", "wild_dino_torpor_drain_multiplier",
            "tamed_dino_torpor_drain_multiplier",
        ], start=1):
            add_float_field(ctx, card, fld, i)

    def _card_mgmt() -> None:
        card = make_card(sf, 2, 0, ctx.theme)
        add_card_header(card, "Gestão de dinos", accent)
        add_int_field(ctx, card, "max_tamed_dinos", 1)
        for i, fld in enumerate([
            "dino_count_multiplier", "taming_speed_multiplier",
            "passive_tame_interval_multiplier", "max_personal_tamed_dinos",
            "pve_dino_decay_period_multiplier", "raid_dino_food_drain_multiplier",
        ], start=2):
            add_float_field(ctx, card, fld, i)
        add_int_field(ctx, card, "personal_tamed_dinos_saddle_structure_cost", 8)
        add_int_field(ctx, card, "override_max_xp_dino", 9)

    def _card_opts() -> None:
        card = make_card(sf, 2, 1, ctx.theme)
        add_card_header(card, "Opções", accent)
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=1)
        bool_fields = [
            "allow_raid_dino_feeding", "allow_flying_stamina_recovery", "prevent_mate_boost",
            "allow_flyer_speed_leveling",
            "disable_dino_decay_pve", "pvp_dino_decay", "auto_destroy_decayed_dinos",
            "allow_multiple_attached_c4", "disable_dino_riding", "disable_dino_taming",
            "use_tame_limit_for_structures_only", "disable_imprint_buff", "allow_anyone_baby_imprint",
        ]
        for i, fld in enumerate(bool_fields):
            add_bool_field(ctx, card, fld, row=1 + i // 2, col=i % 2)

    def _accordion() -> None:
        build_per_level_accordion(
            ctx, sf, 3,
            [
                ("Wild", "per_level_dino_wild"),
                ("Dom.", "per_level_dino_tamed"),
                ("+Add", "per_level_dino_tamed_add"),
                ("+Afi", "per_level_dino_tamed_affinity"),
            ],
            "Wild = selvagem • Dom. = domesticado • +Add = bônus fixo • +Afi = afinidade.",
        )

    def _help() -> None:
        add_collapsible_help(sf, [
            ("Dano / resistência", "Afeta todos os dinos. 1,5 = 50% a mais."),
            ("Máx. dinos domesticados", "Limite global. Recomendado: 300–500 para evitar lag."),
            ("Velocidade de tame", "Maior que 1,0 = mais rápido; menor = mais lento."),
            ("Bônus de imprint", "Multiplicador do buff de imprint — 100% para efeito máximo."),
            ("Selvagem / domado / extra / afinidade", "Multiplicadores de atributo por nível."),
        ], 4)

    run_ui_tasks_chunked(
        sf,
        [_card_dmg, _card_surv, _card_mgmt, _card_opts, _accordion, _help],
        on_done=on_done,
        is_cancelled=is_cancelled,
        on_progress=on_progress,
        on_error=on_error,
        on_cancelled=on_cancelled,
        chunk_size=1,
    )


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 11 — Reprodução
# ════════════════════════════════════════════════════════════════════════════ #

def _build_breeding(sf, srv, vars_ref, bg, accent):
    from ..ui.server_field_widgets import (
        add_card_header, add_collapsible_help, add_float_field,
        init_panel_context, make_card, section_title, setup_dual_column_parent,
    )

    setup_dual_column_parent(sf)
    ctx = init_panel_context(
        sf, srv, vars_ref, accent, "Reprodução",
        vars_ref.get("_panel_root"),
    )
    section_title(sf, "Reprodução e imprinting", accent, 0)

    card_main = make_card(sf, 1, 0, ctx.theme)
    add_card_header(card_main, "Ciclo de reprodução", accent)
    for i, fld in enumerate([
        "mating_interval_multiplier", "egg_hatch_speed_multiplier",
        "baby_mature_speed_multiplier", "baby_food_consumption_multiplier",
    ], start=1):
        add_float_field(ctx, card_main, fld, i)

    card_imp = make_card(sf, 1, 1, ctx.theme)
    add_card_header(card_imp, "Imprinting", accent)
    for i, fld in enumerate([
        "baby_cuddle_interval_multiplier", "baby_cuddle_grace_period_multiplier",
        "baby_cuddle_lose_imprint_quality_speed_multiplier", "baby_imprinting_stat_scale",
    ], start=1):
        add_float_field(ctx, card_imp, fld, i)

    calc_f = ctk.CTkFrame(sf, fg_color="transparent")
    calc_f.grid(row=2, column=0, columnspan=2, padx=8, pady=(4, 8), sticky="w")

    def _open_calc():
        from ..breeding_calculator import open_breeding_calculator
        widgets = {f"gs_{k}": v for k, v in vars_ref.items() if not k.startswith("_")}
        def on_apply():
            for attr in ("baby_mature_speed_multiplier", "egg_hatch_speed_multiplier",
                         "mating_interval_multiplier", "baby_cuddle_interval_multiplier"):
                sv = vars_ref.get(attr)
                if sv is not None:
                    sv.set(str(getattr(srv, attr, 1.0)))
        open_breeding_calculator(sf, srv, widgets, on_apply)

    ctk.CTkButton(
        calc_f, text="🧠  Calculadora de Breeding",
        width=240, height=36,
        fg_color=ctx.theme.get("card_bg", "#1e293b"), hover_color="#0f172a",
        text_color=accent, border_width=1, border_color=accent,
        corner_radius=8, font=ctk.CTkFont(size=12, weight="bold"),
        command=_open_calc,
    ).pack(side="left")

    add_collapsible_help(sf, [
        ("Intervalo de acasalamento", "Menor que 1,0 = acasalamento mais frequente."),
        ("Velocidade de eclosão", "Maior que 1,0 = ovos eclodem mais rápido."),
        ("Velocidade de maturação", "Maior que 1,0 = filhotes crescem mais rápido."),
        ("Intervalo de carinho", "Menor que 1,0 = carinhos mais frequentes (imprint mais fácil)."),
        ("Escala de stats de imprint", "Multiplica o bônus de atributo do imprinting."),
        ("Calculadora de breeding", "Calcula multiplicadores ideais automaticamente."),
    ], 3)


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 12 — Meio Ambiente
# ════════════════════════════════════════════════════════════════════════════ #

def _build_environment(sf, srv, vars_ref, bg, accent, *, on_done=None, is_cancelled=None, on_progress=None, on_error=None, on_cancelled=None):
    from ..ui.server_field_widgets import CardSpec, add_collapsible_help, begin_tek_section, build_cards_layout_chunked

    ctx = begin_tek_section(sf, srv, vars_ref, accent, "Meio Ambiente", "Meio ambiente")
    cards = [
        CardSpec("Coleta e recursos", [
            "harvest_amount_multiplier", "harvest_health_multiplier", "resources_respawn_multiplier",
            "resource_no_replenish_radius_players", "resource_no_replenish_radius_structures",
        ]),
        CardSpec("Opções de coleta", ["use_optimized_harvesting_health", "clamp_resource_harvest_damage"], bool_grid=True),
        CardSpec("Tempo / clima", [
            "day_cycle_speed_scale", "day_time_speed_scale", "night_time_speed_scale",
            "base_temperature_multiplier", "disable_weather_fog",
        ]),
        CardSpec("Decomposição / spoiling", [
            "global_spoiling_time_multiplier", "global_item_decomposition_multiplier",
            "global_corpse_decomposition_multiplier", "clamp_item_spoiling_times",
        ]),
        CardSpec("Agricultura / criaturas", [
            "crop_decay_speed_multiplier", "crop_growth_speed_multiplier",
            "lay_egg_interval_multiplier", "poop_interval_multiplier", "hair_growth_speed_multiplier",
        ]),
    ]
    help_items = [
        ("Quantidade coletada", "Recursos por golpe. 2.0 = coleta dupla."),
        ("Respawn de recursos", "Velocidade de reaparecimento. Valores menores = mais rápido."),
        ("Ciclo dia/noite", "Valores maiores = dias e noites mais curtos."),
        ("Tempo de spoil global", "Valores maiores = itens estragam mais devagar."),
        ("Decomposição de cadáveres", "Tempo até o corpo desaparecer."),
        ("Plantações", "Crescimento e deterioração das plantações."),
    ]

    def _after_cards(row: int) -> None:
        add_collapsible_help(sf, help_items, row)
        if on_done:
            on_done()

    build_cards_layout_chunked(
        sf, ctx, cards,
        on_complete=_after_cards,
        is_cancelled=is_cancelled,
        on_progress=on_progress,
        on_error=on_error,
        on_cancelled=on_cancelled,
        chunk_size=1,
    )


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 13 — Estruturas
# ════════════════════════════════════════════════════════════════════════════ #

def _build_structures(sf, srv, vars_ref, bg, accent, *, on_done=None, is_cancelled=None, on_progress=None, on_error=None, on_cancelled=None):
    from ..ui.server_field_widgets import CardSpec, add_collapsible_help, begin_tek_section, build_cards_layout_chunked

    ctx = begin_tek_section(sf, srv, vars_ref, accent, "Estruturas", "Estruturas")
    cards = [
        CardSpec("Platform saddle / Tek Strider", [
            "override_structure_platform_prevention",
            "per_platform_max_structures_multiplier",
            "max_platform_saddle_structures",
            "platform_saddle_build_area_bounds_multiplier",
            "allow_platform_saddle_multi_floors",
            "flyer_platform_allow_unaligned_dino_basing",
        ]),
        CardSpec("Dano e resistência", [
            "structure_resistance_multiplier", "structure_damage_multiplier",
            "structure_damage_repair_cooldown", "pvp_structure_decay",
            "pvp_zone_structure_damage_multiplier",
        ]),
        CardSpec("Limites", [
            "max_structures_in_range",
        ]),
        CardSpec("Decay PvE", [
            "enable_structure_decay_pve", "pve_structure_decay_period_multiplier",
            "pve_structure_decay_destruction_period", "auto_destroy_old_structures_multiplier",
            "pve_allow_structures_at_supply_drops",
        ]),
        CardSpec("Opções gerais", [
            "always_allow_structure_pickup", "force_all_structure_locking",
            "disable_structure_placement_collision",
            "only_auto_destroy_core_structures", "only_decay_unsnapped_core_structures",
            "fast_decay_unsnapped_core_structures", "destroy_unconnected_water_pipes",
            "passive_defenses_damage_riderless_dinos", "enable_fast_decay_interval",
            "fast_decay_interval",
        ]),
        CardSpec("Torretas", [
            "limit_turrets_in_range", "limit_turrets_range", "limit_turrets_num",
            "hard_limit_turrets_in_range",
        ]),
    ]
    help_items = [
        ("Torretas no Stryder", "Ative «Permitir torretas em platform saddle» — sem isso Auto/Tek Turret não colocam no Tek Strider."),
        ("Resistência e dano", "Dano recebido/causado por estruturas. 1.0 = vanilla."),
        ("Máx. estruturas por raio", "Limite por área — reduz lag em bases grandes."),
        ("Decay em PvE", "Remove bases abandonadas automaticamente."),
        ("Limite de torretas", "Teto de torretas por raio — recomendado em cercos."),
        ("Trancar ao construir", "Estruturas ficam trancadas ao serem colocadas."),
    ]

    def _after_cards(row: int) -> None:
        add_collapsible_help(sf, help_items, row)
        if on_done:
            on_done()

    build_cards_layout_chunked(
        sf, ctx, cards,
        on_complete=_after_cards,
        is_cancelled=is_cancelled,
        on_progress=on_progress,
        on_error=on_error,
        on_cancelled=on_cancelled,
        chunk_size=1,
    )


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 14 — Engramas
# ════════════════════════════════════════════════════════════════════════════ #

def _build_engrams(sf, srv, vars_ref, bg, accent, *, on_done=None, is_cancelled=None, on_progress=None, on_error=None, on_cancelled=None):
    from ..ui.server_field_widgets import (
        CardSpec, add_collapsible_help, begin_tek_section, build_cards_layout_chunked,
        make_card, add_card_header, run_ui_tasks_chunked,
    )

    ctx = begin_tek_section(sf, srv, vars_ref, accent, "Engramas", "Engramas")
    final_row = [2]

    def _help() -> None:
        add_collapsible_help(sf, [
            ("Só engramas listados", "Apenas engramas configurados ficam disponíveis."),
            ("Desbloquear todos os engramas", "Libera todos os engramas ao subir de nível."),
            ("Substituição de engramas", "Formato Game.ini: OverrideNamedEngramEntries=..."),
            ("Editor visual", "Gera entradas automaticamente."),
        ], final_row[0])
        if on_done:
            on_done()

    def _extras() -> None:
        row = final_row[0]
        app = vars_ref.get("_app")
        if app:
            btn_f = ctk.CTkFrame(sf, fg_color="transparent")
            btn_f.grid(row=row, column=0, columnspan=2, padx=8, pady=4, sticky="w")
            ctk.CTkButton(
                btn_f, text="🎓  Abrir Editor Visual de Engramas", height=32,
                fg_color=ctx.theme["accent_muted_bg"], hover_color="#052e16",
                border_width=1, border_color=accent, text_color=accent,
                font=ctk.CTkFont(size=11),
                command=lambda: app._asm_open_engram_editor(srv),
            ).pack(side="left")
            row += 1
        raw_card = make_card(sf, row, 0, ctx.theme)
        raw_card.grid(columnspan=2, sticky="ew")
        add_card_header(raw_card, "Override de Engramas (Game.ini)", accent)
        ctk.CTkLabel(raw_card, text="OverrideNamedEngramEntries=(...) — um por linha",
                     font=ctk.CTkFont(size=10), text_color=ctx.theme["text_muted"]).grid(
            row=1, column=0, padx=12, pady=(0, 4), sticky="w")
        box = ctk.CTkTextbox(raw_card, height=300, font=ctk.CTkFont(family="Consolas", size=10))
        box.grid(row=2, column=0, padx=12, pady=(0, 10), sticky="ew")
        box.insert("1.0", srv.engram_entries_raw)
        vars_ref["_raw_engram_entries_raw"] = box
        final_row[0] = row + 1
        _help()

    def _after_cards(row: int) -> None:
        final_row[0] = row
        run_ui_tasks_chunked(
            sf, [_extras], is_cancelled=is_cancelled,
            on_error=on_error, on_cancelled=on_cancelled,
        )

    build_cards_layout_chunked(
        sf, ctx,
        [CardSpec("Opções", ["only_allow_specified_engrams", "auto_unlock_all_engrams"], bool_grid=True)],
        on_complete=_after_cards,
        is_cancelled=is_cancelled,
        on_progress=on_progress,
        on_error=on_error,
        on_cancelled=on_cancelled,
    )


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 15 — Arquivos do Servidor
# ════════════════════════════════════════════════════════════════════════════ #

def _build_server_files(sf, srv, vars_ref, bg, accent):
    sf.grid_columnconfigure(0, weight=1)

    _LISTS = [
        {
            "title": "Administradores",
            "icon": "🛡",
            "sub": "SteamID64 de cada admin, um por linha.",
            "hint": "Gravado em ShooterGame/Saved/AllowedCheaterSteamIDs.txt ao salvar ou iniciar o servidor.",
            "key": "_admin_ids_text",
            "items": srv.admin_ids,
        },
        {
            "title": "Whitelist",
            "icon": "✅",
            "sub": "SteamID64 permitidos. Ative 'Exclusive Join' na seção Transferências.",
            "hint": "Quando Exclusive Join está ativo, apenas SteamIDs desta lista podem entrar.",
            "key": "_whitelist_ids_text",
            "items": srv.whitelist_ids,
        },
        {
            "title": "Exclusive Join",
            "icon": "🔑",
            "sub": "SteamID64 com acesso garantido mesmo com server cheio ou restrito.",
            "hint": "Complementa a whitelist. Separe por linha. Deixe vazio se não usa Exclusive Join.",
            "key": "_exclusive_ids_text",
            "items": srv.exclusive_join_ids,
        },
    ]

    for r, cfg in enumerate(_LISTS):
        card = ctk.CTkFrame(sf, fg_color="#0d1b2a", corner_radius=10,
                            border_width=1, border_color="#1e293b")
        card.grid(row=r, column=0, padx=8, pady=6, sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        # ── Cabeçalho do card ────────────────────────────────────────────────
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=12, pady=(10, 0), sticky="ew")
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr, text=f"{cfg['icon']} {cfg['title']}",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=accent).grid(row=0, column=0, sticky="w")

        count_lbl = ctk.CTkLabel(hdr, text="", font=ctk.CTkFont(size=10),
                                 text_color="#64748b")
        count_lbl.grid(row=0, column=1, padx=(8, 0), sticky="w")

        ctk.CTkLabel(card, text=cfg["sub"], font=ctk.CTkFont(size=10),
                     text_color="#64748b", anchor="w").grid(
            row=1, column=0, padx=12, pady=(2, 4), sticky="ew")

        # ── Textbox ──────────────────────────────────────────────────────────
        box = ctk.CTkTextbox(card, height=88,
                             font=ctk.CTkFont(family="Consolas", size=11),
                             fg_color="#07101c")
        box.grid(row=2, column=0, padx=12, pady=(0, 4), sticky="ew")
        box.insert("1.0", "\n".join(cfg["items"]))
        vars_ref[cfg["key"]] = box

        # ── Contador dinâmico ────────────────────────────────────────────────
        def _update_count(b=box, lbl=count_lbl):
            ids = [ln.strip() for ln in b.get("1.0", "end").splitlines() if ln.strip()]
            lbl.configure(text=f"({len(ids)} IDs)" if ids else "(vazio)")

        _update_count()
        box.bind("<KeyRelease>", lambda _e, fn=_update_count: fn())

        # ── Botão "Colar SteamID" ─────────────────────────────────────────────
        act_row = ctk.CTkFrame(card, fg_color="transparent")
        act_row.grid(row=3, column=0, padx=12, pady=(0, 10), sticky="w")

        def _paste_id(b=box, fn=_update_count):
            try:
                clip = b.clipboard_get().strip()
            except Exception:
                clip = ""
            if not clip:
                return
            ids_existing = {ln.strip() for ln in b.get("1.0", "end").splitlines() if ln.strip()}
            new_ids = [p.strip() for p in clip.replace(",", "\n").splitlines()
                       if p.strip() and p.strip() not in ids_existing]
            if new_ids:
                cur = b.get("1.0", "end").rstrip("\n")
                if cur:
                    b.insert("end", "\n" + "\n".join(new_ids))
                else:
                    b.delete("1.0", "end")
                    b.insert("1.0", "\n".join(new_ids))
                fn()

        def _clear(b=box, fn=_update_count):
            b.delete("1.0", "end")
            fn()

        ctk.CTkButton(act_row, text="📋 Colar ID(s)", width=110, height=26,
                      fg_color="#1e293b", hover_color="#334155",
                      text_color="#94a3b8", font=ctk.CTkFont(size=11),
                      command=_paste_id).pack(side="left", padx=(0, 6))

        ctk.CTkButton(act_row, text="✕ Limpar", width=80, height=26,
                      fg_color="#2d1212", hover_color="#3d1818",
                      text_color="#f87171", font=ctk.CTkFont(size=11),
                      command=_clear).pack(side="left")

    _add_help(sf, [
        ("IDs de Admin", "SteamIDs dos administradores do servidor. Acesso total a comandos admin sem senha."),
        ("Whitelist", "SteamIDs permitidos. Ative «Acesso exclusivo» na seção Transferências para restringir."),
        ("Acesso exclusivo", "SteamIDs com entrada garantida mesmo com servidor cheio ou restrito."),
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

    # ── Presets de tabelas populares ──────────────────────────────────────────
    preset_f = ctk.CTkFrame(gen_card, fg_color="transparent")
    preset_f.grid(row=1, column=0, columnspan=8, padx=12, pady=(0, 4), sticky="w")

    _PRESETS = {
        "Official (70 lvls)":   {"max": 70,  "base": 5,   "mult": 1.20, "engrams": 8},
        "Hard (150 lvls)":      {"max": 150, "base": 10,  "mult": 1.18, "engrams": 8},
        "Custom (100 lvls)":    {"max": 100, "base": 8,   "mult": 1.15, "engrams": 10},
        "Extreme (200 lvls)":   {"max": 200, "base": 15,  "mult": 1.14, "engrams": 12},
    }

    def _apply_preset(name: str):
        p = _PRESETS.get(name)
        if not p:
            return
        _vars_p[0].set(str(p["max"]))
        _vars_p[1].set(str(p["base"]))
        _vars_p[2].set(str(p["mult"]))
        _vars_p[3].set(str(p["engrams"]))
        _preview_player_gen()

    ctk.CTkLabel(preset_f, text="Presets:", font=ctk.CTkFont(size=10),
                 text_color="#8899aa").pack(side="left", padx=(0, 6))
    for pname in _PRESETS:
        ctk.CTkButton(preset_f, text=pname, width=100, height=24,
                      fg_color="#1e293b", hover_color="#334155",
                      text_color="#94a3b8", font=ctk.CTkFont(size=10),
                      command=lambda n=pname: _apply_preset(n)).pack(side="left", padx=(0, 4))

    # ── Campos do gerador ─────────────────────────────────────────────────────
    _fields_p = [
        ("Nível máx.", "100"), ("XP base (lv0)", "70"),
        ("Multiplicador XP", "1.15"), ("Engrams/nível", "8"),
    ]
    _vars_p: list[tk.StringVar] = []
    for col, (lbl, default) in enumerate(_fields_p):
        ctk.CTkLabel(gen_card, text=lbl, font=ctk.CTkFont(size=10),
                     text_color="#8899aa").grid(row=2, column=col * 2, padx=(12, 2), pady=(0, 4), sticky="e")
        v = tk.StringVar(value=default)
        _vars_p.append(v)
        ctk.CTkEntry(gen_card, textvariable=v, width=80, height=28).grid(
            row=2, column=col * 2 + 1, padx=(0, 8), pady=(0, 4), sticky="w")

    # ── Modo fórmula custom ───────────────────────────────────────────────────
    custom_f = ctk.CTkFrame(gen_card, fg_color="transparent")
    custom_f.grid(row=3, column=0, columnspan=8, padx=12, pady=(0, 4), sticky="w")

    ctk.CTkLabel(custom_f, text="Fórmula custom (Python):",
                 font=ctk.CTkFont(size=10), text_color="#8899aa").pack(side="left", padx=(0, 6))
    custom_formula_var = tk.StringVar(value="base * (mult ** i)")
    ctk.CTkEntry(custom_f, textvariable=custom_formula_var, width=260, height=26,
                 font=ctk.CTkFont(family="Consolas", size=10)).pack(side="left", padx=(0, 6))

    def _preview_player_gen():
        try:
            max_lvl = max(1, min(int(_vars_p[0].get()), 500))
            xp_base = max(1, int(_vars_p[1].get()))
            xp_mult = max(1.0, float(_vars_p[2].get()))
            engrams = max(0, int(_vars_p[3].get()))
        except ValueError:
            return

        # Usa fórmula custom se diferente do padrão
        formula = custom_formula_var.get().strip()
        xp_vals = []
        try:
            for i in range(max_lvl):
                base, mult = xp_base, xp_mult
                xp = int(eval(formula, {"__builtins__": {}}, {"i": i, "base": base, "mult": mult}))
                xp_vals.append(xp)
        except Exception:
            xp_vals = [int(xp_base * (xp_mult ** i)) for i in range(max_lvl)]

        text_lines = [f"LevelExperienceRampOverrides=(ExperiencePointsForLevel[{i}]={xp_vals[i]})" for i in range(max_lvl)]
        text_lines += [f"OverridePlayerLevelEngramPoints={engrams}" for _ in range(max_lvl)]
        text = "\n".join(text_lines)

        # Atualiza preview
        if len(text_lines) > 12:
            shown = text_lines[:6] + ["  ..."] + text_lines[-3:]
        else:
            shown = text_lines
        preview_box.configure(state="normal")
        preview_box.delete("1.0", "end")
        preview_box.insert("1.0", "\n".join(shown))
        preview_box.configure(state="disabled")

        # Atualiza gráfico
        _draw_xp_curve(xp_vals, canvas_xp)

    def _apply_player_gen():
        try:
            max_lvl = max(1, min(int(_vars_p[0].get()), 500))
            xp_base = max(1, int(_vars_p[1].get()))
            xp_mult = max(1.0, float(_vars_p[2].get()))
            engrams = max(0, int(_vars_p[3].get()))
        except ValueError:
            return

        formula = custom_formula_var.get().strip()
        xp_vals = []
        try:
            for i in range(max_lvl):
                base, mult = xp_base, xp_mult
                xp = int(eval(formula, {"__builtins__": {}}, {"i": i, "base": base, "mult": mult}))
                xp_vals.append(xp)
        except Exception:
            xp_vals = [int(xp_base * (xp_mult ** i)) for i in range(max_lvl)]

        text_lines = [f"LevelExperienceRampOverrides=(ExperiencePointsForLevel[{i}]={xp_vals[i]})" for i in range(max_lvl)]
        text_lines += [f"OverridePlayerLevelEngramPoints={engrams}" for _ in range(max_lvl)]
        text = "\n".join(text_lines)

        box_p.configure(state="normal")
        box_p.delete("1.0", "end")
        box_p.insert("1.0", text)
        _preview_player_gen()

    ctk.CTkButton(gen_card, text="👁  Preview",
                  height=28, fg_color="#1e293b", hover_color="#334155",
                  font=ctk.CTkFont(size=11),
                  command=_preview_player_gen).grid(
        row=4, column=0, padx=12, pady=(0, 8), sticky="w")
    ctk.CTkButton(gen_card, text="Gerar e aplicar",
                  height=28, fg_color="#0e4a6e", hover_color="#0a3550",
                  font=ctk.CTkFont(size=11),
                  command=_apply_player_gen).grid(
        row=4, column=1, padx=(0, 12), pady=(0, 8), sticky="w")

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
        ("Tabela de XP do jogador", "Define quanto XP é necessário para cada nível do jogador. Uma linha por nível."),
        ("Pontos de engrama por nível", "Quantidade de pontos de engrama ganhos em cada nível. Uma linha por nível."),
        ("Tabela de XP do dino", "Define a progressão de XP dos dinos. Uma linha por nível."),
        ("Gerador rápido", "Calcula automaticamente os valores com base em nível máximo, XP base e multiplicador."),
    ])


# ════════════════════════════════════════════════════════════════════════════ #
#  Extensões SM (Fase 5)
# ════════════════════════════════════════════════════════════════════════════ #

def _build_sm_extensions(sf, srv, vars_ref, bg, accent):
    from ..ui.tek_sm_extensions_section import build_sm_extensions_section
    build_sm_extensions_section(sf, srv, vars_ref, accent)


# ════════════════════════════════════════════════════════════════════════════ #
#  Ferramentas (Fase 7 — launchers que abrem janelas dedicadas)
# ════════════════════════════════════════════════════════════════════════════ #

def _build_tool_spawn_exact(sf, srv, vars_ref, bg, accent):
    """Painel-lançador do Gerador SpawnExact."""
    _build_tool_launcher(
        sf=sf,
        vars_ref=vars_ref,
        srv=srv,
        icon="🦕",
        title="Gerador SpawnExact",
        description=(
            "Gera o comando admin cheat SpawnExactDino com controle total de\n"
            "stats selvagens, níveis domados, cores por região e imprint.\n\n"
            "• Busca espécies do manifesto ArkUtils (cache local)\n"
            "• Blueprints favoritos salvos localmente\n"
            "• Envio direto via RCON quando configurado\n"
            "• Presets e histórico de comandos gerados"
        ),
        btn_label="Abrir Gerador SpawnExact",
        action=lambda app=vars_ref.get("_app"), s=srv: app._asm_open_spawn_exact(s),
        accent=accent,
        bg=bg,
    )


def _build_tool_rcon(sf, srv, vars_ref, bg, accent):
    """Painel-lançador do Console RCON."""
    rcon_ok = bool(getattr(srv, "rcon_enabled", False) and getattr(srv, "admin_password", ""))
    _build_tool_launcher(
        sf=sf,
        vars_ref=vars_ref,
        srv=srv,
        icon="⚡",
        title="Console RCON",
        description=(
            "Terminal interativo de comandos admin via protocolo Source RCON.\n\n"
            "• Atalhos rápidos: ListPlayers, SaveWorld, DestroyWildDinos…\n"
            "• Histórico de comandos navegável (↑ ↓)\n"
            "• Ping de keep-alive automático\n"
            "• Reconexão automática em caso de queda"
            + ("" if rcon_ok else
               "\n\n⚠  RCON não configurado — ative-o na seção Administração\n"
               "   e defina a Senha Admin.")
        ),
        btn_label="Abrir Console RCON",
        action=lambda app=vars_ref.get("_app"), s=srv: app._asm_open_rcon(s),
        accent=accent,
        bg=bg,
        btn_disabled=not rcon_ok,
    )


def _build_tool_players(sf, srv, vars_ref, bg, accent):
    """Painel-lançador da lista de Jogadores Online."""
    rcon_ok = bool(getattr(srv, "rcon_enabled", False) and getattr(srv, "admin_password", ""))
    _build_tool_launcher(
        sf=sf,
        vars_ref=vars_ref,
        srv=srv,
        icon="👥",
        title="Jogadores Online",
        description=(
            "Visualize e gerencie os jogadores conectados ao servidor.\n\n"
            "• Lista de jogadores com nome e SteamID\n"
            "• Ações: Kick, Ban, Mensagem direta\n"
            "• Atualização automática configurável"
            + ("" if rcon_ok else
               "\n\n⚠  RCON não configurado — ative-o na seção Administração\n"
               "   e defina a Senha Admin.")
        ),
        btn_label="Abrir Lista de Jogadores",
        action=lambda app=vars_ref.get("_app"), s=srv: app._asm_open_player_list(s),
        accent=accent,
        bg=bg,
        btn_disabled=not rcon_ok,
    )


def _build_tool_launcher(
    sf, vars_ref: dict, srv, icon: str, title: str, description: str,
    btn_label: str, action, accent: str, bg: str, btn_disabled: bool = False,
) -> None:
    """Widget genérico de lançador para seções de Ferramentas."""
    import customtkinter as ctk
    from ..ui_constants import get_theme

    th  = get_theme("tek")
    card_bg = th["card_bg"]
    sep     = th.get("separator", "#1e293b")
    t1      = th["text_primary"]
    t2      = th["text_secondary"]
    t3      = th.get("text_muted", "#475569")
    acc_mb  = th.get("accent_muted_bg", "#083344")

    sf.grid_columnconfigure(0, weight=1)

    # ── Card central ───────────────────────────────────────────────────────
    card = ctk.CTkFrame(sf, fg_color=card_bg, corner_radius=12,
                        border_width=1, border_color=sep)
    card.grid(row=0, column=0, padx=24, pady=32, sticky="ew")
    card.grid_columnconfigure(0, weight=1)

    # Ícone + título
    hdr = ctk.CTkFrame(card, fg_color=acc_mb, corner_radius=10, height=72)
    hdr.grid(row=0, column=0, sticky="ew", padx=1, pady=(1, 0))
    hdr.grid_columnconfigure(1, weight=1)
    hdr.grid_propagate(False)

    ctk.CTkLabel(hdr, text=icon,
                 font=ctk.CTkFont(size=32)).grid(row=0, column=0, padx=(20, 12), pady=16)
    ctk.CTkLabel(hdr, text=title,
                 font=ctk.CTkFont(size=17, weight="bold"),
                 text_color=accent, anchor="w").grid(row=0, column=1, sticky="w", pady=16)

    # Descrição
    ctk.CTkLabel(card, text=description,
                 font=ctk.CTkFont(size=12), text_color=t2,
                 justify="left", anchor="w", wraplength=480,
                 ).grid(row=1, column=0, padx=20, pady=(16, 8), sticky="w")

    ctk.CTkFrame(card, fg_color=sep, height=1).grid(
        row=2, column=0, sticky="ew", padx=12, pady=(4, 12))

    # Botão de ação
    ctk.CTkButton(
        card, text=btn_label, height=40, width=240,
        fg_color=accent if not btn_disabled else sep,
        hover_color=th["accent_hover"] if not btn_disabled else sep,
        text_color="#000" if not btn_disabled else t3,
        font=ctk.CTkFont(size=13, weight="bold"),
        state="normal" if not btn_disabled else "disabled",
        command=action,
    ).grid(row=3, column=0, padx=20, pady=(0, 20))

    # Atalho de teclado info
    ctk.CTkLabel(card, text="Dica: o painel abre em janela flutuante separada.",
                 font=ctk.CTkFont(size=10), text_color=t3).grid(
        row=4, column=0, padx=20, pady=(0, 14), sticky="w")


# ════════════════════════════════════════════════════════════════════════════ #
#  Seções Agregadas (Fase 4)
# ════════════════════════════════════════════════════════════════════════════ #

def _build_harvest_aggregated(sf, srv, vars_ref, bg, accent, *, on_done=None, is_cancelled=None, on_progress=None, on_error=None, on_cancelled=None):
    from ..ui.server_field_widgets import run_ui_tasks_chunked
    from ..ui.tek_aggregated_sections import build_harvest_resource_section

    def _help() -> None:
        _add_help(sf, [
            ("Formato", "HarvestResourceItemAmountClassMultipliers=(ClassName=\"PrimalItemResource_Stone_C\",Multiplier=2.0)"),
            ("Empilhamento", "Multiplica junto com o multiplicador global de coleta em Meio Ambiente."),
        ])

    def _after_main() -> None:
        run_ui_tasks_chunked(
            sf, [_help], on_done=on_done, is_cancelled=is_cancelled, on_progress=on_progress,
            on_error=on_error, on_cancelled=on_cancelled,
        )

    build_harvest_resource_section(
        sf, srv, vars_ref, accent,
        on_done=_after_main, is_cancelled=is_cancelled, on_progress=on_progress,
        on_error=on_error, on_cancelled=on_cancelled,
    )


def _build_dino_class_aggregated(sf, srv, vars_ref, bg, accent, *, on_done=None, is_cancelled=None, on_progress=None, on_error=None, on_cancelled=None):
    from ..ui.server_field_widgets import run_ui_tasks_chunked
    from ..ui.tek_aggregated_sections import build_dino_class_multipliers_section

    def _help() -> None:
        _add_help(sf, [
            ("Classe", "Use o nome curto com sufixo _C, ex.: Rex_Character_BP_C."),
            ("Multiplicador", "1,0 = padrão; valores maiores aumentam o efeito (dano ou resistência)."),
        ])

    def _after_main() -> None:
        run_ui_tasks_chunked(
            sf, [_help], on_done=on_done, is_cancelled=is_cancelled, on_progress=on_progress,
            on_error=on_error, on_cancelled=on_cancelled,
        )

    build_dino_class_multipliers_section(
        sf, srv, vars_ref, accent,
        on_done=_after_main, is_cancelled=is_cancelled, on_progress=on_progress,
        on_error=on_error, on_cancelled=on_cancelled,
    )


def _build_spawn_tame_aggregated(sf, srv, vars_ref, bg, accent, *, on_done=None, is_cancelled=None, on_progress=None, on_error=None, on_cancelled=None):
    from ..ui.server_field_widgets import run_ui_tasks_chunked
    from ..ui.tek_aggregated_sections import build_spawn_tame_section

    def _help() -> None:
        _add_help(sf, [
            ("Peso de spawn", "SpawnWeightMultiplier controla a frequência relativa no pool de spawn."),
            ("Bloquear tame", "PreventDinoTameClassNames impede a domesticação da classe informada."),
        ])

    def _after_main() -> None:
        run_ui_tasks_chunked(
            sf, [_help], on_done=on_done, is_cancelled=is_cancelled, on_progress=on_progress,
            on_error=on_error, on_cancelled=on_cancelled,
        )

    build_spawn_tame_section(
        sf, srv, vars_ref, accent,
        on_done=_after_main, is_cancelled=is_cancelled, on_progress=on_progress,
        on_error=on_error, on_cancelled=on_cancelled,
    )


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
        ("Tipo exato de recurso", "Verdadeiro = exige exatamente a classe informada; falso = aceita subclasses (ex.: qualquer madeira)."),
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
        ("Ignorar multiplicador global", "Verdadeiro = usa a quantidade absoluta, ignorando o multiplicador global de pilha."),
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
        ("Adicionar spawn", "Adiciona dinos a um container de spawn existente sem remover os originais."),
        ("Remover spawn", "Remove entradas específicas de um container de spawn."),
        ("Substituir spawn", "Substitui completamente um container de spawn."),
        ("Peso da entrada", "Peso relativo do spawn. Valores maiores = mais comum. Use entre 0,001 e 1,0."),
        ("Percentual máximo", "Percentual máximo do total de spawns permitido para essa criatura."),
        ("Editor visual", "Use o botão acima para uma interface gráfica que facilita a criação de spawners."),
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
        ("Substituir loot de crate", "Substitui o conteúdo de uma caixa de loot (bea/drop/mar). Formato complexo — use o gerador rápido."),
        ("Classe da crate", "Classe do container alvo (ex.: SupplyCrate_Level03_C)."),
        ("Conjuntos mín./máx.", "Quantos conjuntos de itens aparecem no drop (mínimo e máximo)."),
        ("Peso do conjunto", "Conjuntos com peso maior aparecem com mais frequência."),
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
    """Parse blocos [Seção] + chave=valor (compatível com colar do ASM)."""
    sections: dict = {}
    current: "str | None" = None
    text = raw.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(";") or stripped.startswith("#"):
            continue
        if stripped.startswith("["):
            end = stripped.find("]")
            if end > 1:
                current = stripped[1:end].strip()
                sections.setdefault(current, [])
            continue
        if "=" in stripped:
            k, _, v = stripped.partition("=")
            k, v = k.strip(), v.strip()
            if not k:
                continue
            if current is None:
                current = "Imported"
                sections.setdefault(current, [])
            sections[current].append((k, v))
    return sections


class _IniPasteDialog(ctk.CTkToplevel):
    """Diálogo estilo ASM — colar seções INI personalizadas e processar."""

    def __init__(self, parent: tk.Misc, on_apply: Callable[[str], bool], accent: str) -> None:
        super().__init__(parent)
        self.title("Dados de configuração personalizados")
        self.resizable(True, True)
        self.minsize(480, 320)
        self.configure(fg_color="#0f172a")
        self.grab_set()
        self.focus_set()
        self._on_apply = on_apply

        ctk.CTkLabel(
            self, text="Cole as seções INI abaixo ([Seção] e chave=valor)",
            font=ctk.CTkFont(size=12), text_color=accent,
        ).pack(padx=16, pady=(14, 8), anchor="w")

        self._box = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=11))
        self._box.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        try:
            clip = parent.clipboard_get()
            if clip and clip.strip():
                self._box.insert("1.0", clip)
        except tk.TclError:
            pass

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkButton(
            btns, text="Processa", width=110, fg_color=accent,
            hover_color="#16a34a", command=self._process,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            btns, text="Cancela", width=110,
            fg_color="#1e293b", hover_color="#334155", command=self.destroy,
        ).pack(side="right")

    def _process(self) -> None:
        text = self._box.get("1.0", "end").strip()
        if not text:
            from tkinter import messagebox
            messagebox.showwarning("Sem conteúdo", "Cole ao menos uma seção INI.", parent=self)
            return
        if self._on_apply(text):
            self.destroy()
        else:
            from tkinter import messagebox
            messagebox.showerror(
                "Formato inválido",
                "Não foi possível interpretar o texto.\n\n"
                "Use o formato:\n[ServerSettings]\nChave=Valor",
                parent=self,
            )


def _serialize_ini_sections(sections: "dict[str, list[tuple[str,str]]]") -> str:
    parts = []
    for sec, items in sections.items():
        parts.append(f"[{sec}]")
        for k, v in items:
            parts.append(f"{k}={v}")
        parts.append("")
    return "\n".join(parts).strip()


def _build_ini_editor(
    sf, title: str, raw_text: str, raw_key: str, vars_ref: dict, accent: str,
    *, on_ready=None, on_progress=None,
) -> None:
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
    lt = ctk.CTkFrame(lp, fg_color=_HDR_BG, corner_radius=0)
    lt.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
    lt.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(lt, text="Seções Personalizadas",
                 font=ctk.CTkFont(size=11, weight="bold"),
                 text_color=_TXT_HDR).grid(row=0, column=0, padx=10, pady=(6, 2), sticky="w")

    tb_l = ctk.CTkFrame(lt, fg_color="transparent")
    tb_l.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))

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
    rt = ctk.CTkFrame(rp, fg_color=_HDR_BG, corner_radius=0)
    rt.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
    rt.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(rt, text="Itens Personalizados",
                 font=ctk.CTkFont(size=11, weight="bold"),
                 text_color=_TXT_HDR).grid(row=0, column=0, padx=10, pady=(6, 2), sticky="w")

    tb_r = ctk.CTkFrame(rt, fg_color="transparent")
    tb_r.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))

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

    _items_render_gen: list[int] = [0]
    _ITEM_CHUNK = 12

    def _render_items(*, on_done=None):
        for w in item_scroll.winfo_children():
            w.destroy()
        sec = sel_section[0]
        if sec is None or sec not in sections:
            if on_done:
                on_done()
            return
        items = sections[sec]
        gen = _items_render_gen[0] + 1
        _items_render_gen[0] = gen

        def _render_chunk(start: int = 0) -> None:
            if gen != _items_render_gen[0]:
                return
            end = min(start + _ITEM_CHUNK, len(items))
            for idx in range(start, end):
                k, v = items[idx]
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

            if end < len(items):
                if on_progress:
                    on_progress(end, len(items))
                sf.after(0, lambda s=end: _render_chunk(s))
            elif on_done:
                if on_progress:
                    on_progress(len(items), len(items))
                on_done()

        if not items:
            if on_progress:
                on_progress(1, 1)
            if on_done:
                on_done()
            return
        _render_chunk(0)

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

    def _merge_parsed_ini(text: str) -> bool:
        parsed = _parse_ini_sections(text)
        if not parsed:
            return False
        for sec, items in parsed.items():
            if sec not in sections:
                sections[sec] = []
            sections[sec].extend(items)
        if not sel_section[0] and sections:
            sel_section[0] = next(iter(sections))
        _flush()
        _render_sections()
        _render_items()
        return True

    def _import_from_clipboard():
        try:
            text = sf.winfo_toplevel().clipboard_get()
        except tk.TclError:
            from tkinter import messagebox
            messagebox.showwarning(
                "Área de transferência vazia",
                "Não há texto na área de transferência.",
                parent=sf.winfo_toplevel(),
            )
            return
        if not _merge_parsed_ini(text):
            from tkinter import messagebox
            messagebox.showerror(
                "Formato inválido",
                "Não foi possível interpretar o conteúdo colado.",
                parent=sf.winfo_toplevel(),
            )

    def _open_paste_dialog():
        _IniPasteDialog(sf.winfo_toplevel(), _merge_parsed_ini, accent)

    def _copy_all_sections():
        sf.winfo_toplevel().clipboard_clear()
        sf.winfo_toplevel().clipboard_append(_serialize_ini_sections(sections))

    def _paste_items():
        sec = sel_section[0]
        if sec is None:
            from tkinter import messagebox
            messagebox.showinfo(
                "Selecione uma seção",
                "Selecione uma seção à esquerda antes de colar itens.",
                parent=sf.winfo_toplevel(),
            )
            return
        try:
            text = sf.winfo_toplevel().clipboard_get()
        except tk.TclError:
            from tkinter import messagebox
            messagebox.showwarning(
                "Área de transferência vazia",
                "Não há texto na área de transferência.",
                parent=sf.winfo_toplevel(),
            )
            return
        added = 0
        for line in text.replace("\r\n", "\n").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith(("[", ";", "#")):
                k, _, v = line.partition("=")
                sections[sec].append((k.strip(), v.strip()))
                added += 1
        if not added:
            from tkinter import messagebox
            messagebox.showerror(
                "Formato inválido",
                "Nenhuma linha chave=valor encontrada no texto colado.",
                parent=sf.winfo_toplevel(),
            )
            return
        _flush()
        _render_items()

    # ── Botões toolbar (rótulos PT — evita confusão com só ícones) ────────────
    _BTN_ADD_G  = "#15803d"
    _BTN_ADD_GH = "#14532d"
    _BTN_IMP    = "#0e4a6e"
    _BTN_IMP_H  = "#0a3550"
    _BTN_FONT   = ctk.CTkFont(family="Segoe UI", size=10)

    def _ini_btn(parent, label: str, cmd, fg: str, hv: str) -> None:
        ctk.CTkButton(
            parent, text=label, height=26, corner_radius=6,
            fg_color=fg, hover_color=hv, command=cmd,
            font=_BTN_FONT,
        ).pack(side="left", padx=2, pady=2)

    for label, cmd, fg, hv in [
        ("Recarregar", _refresh_sections, _BTN_NEU, _BTN_NEU_H),
        ("Nova seção", _add_section, _BTN_ADD_G, _BTN_ADD_GH),
        ("Colar seções…", _open_paste_dialog, _BTN_IMP, _BTN_IMP_H),
        ("Copiar tudo", _copy_all_sections, _BTN_NEU, _BTN_NEU_H),
        ("Excluir seção", lambda: _del_section(sel_section[0]) if sel_section[0] else None,
         _BTN_DEL, _BTN_DEL_H),
    ]:
        _ini_btn(tb_l, label, cmd, fg, hv)

    for label, cmd, fg, hv in [
        ("Novo item", _add_item, _BTN_ADD_G, _BTN_ADD_GH),
        ("Colar itens", _paste_items, _BTN_IMP, _BTN_IMP_H),
        ("Limpar itens", _clear_items, _BTN_DEL, _BTN_DEL_H),
    ]:
        _ini_btn(tb_r, label, cmd, fg, hv)

    # ── Render inicial ────────────────────────────────────────────────────────
    if sections:
        sel_section[0] = next(iter(sections))
    _render_sections()
    _render_items(on_done=on_ready)


# ════════════════════════════════════════════════════════════════════════════ #
#  Seção 22 — Custom GameUserSettings.ini
# ════════════════════════════════════════════════════════════════════════════ #

def _build_custom_gus(sf, srv, vars_ref, bg, accent, *, on_done=None, is_cancelled=None, on_progress=None, on_error=None, on_cancelled=None):
    from ..ui.server_field_widgets import run_ui_tasks_chunked

    def _help() -> None:
        _add_help(sf, [
            ("Para que serve", "Conteúdo extra adicionado ao final do GameUserSettings.ini gerado pelo app."),
            ("Secções comuns", "[ServerSettings], [SessionSettings], [/Script/Engine.GameSession]"),
            ("Dica", "Use este campo para configurações avancadas que não possuem campo dedicado no painel."),
        ])

    def _after_ini() -> None:
        run_ui_tasks_chunked(
            sf, [_help], on_done=on_done, is_cancelled=is_cancelled, on_progress=on_progress,
            on_error=on_error, on_cancelled=on_cancelled,
        )

    _build_ini_editor(
        sf, "Conteúdo extra — GameUserSettings.ini",
        srv.custom_gus_ini_raw, "_raw_custom_gus_ini_raw",
        vars_ref, accent, on_ready=_after_ini, on_progress=on_progress,
    )


def _build_custom_game(sf, srv, vars_ref, bg, accent, *, on_done=None, is_cancelled=None, on_progress=None, on_error=None, on_cancelled=None):
    from ..ui.server_field_widgets import run_ui_tasks_chunked

    def _help() -> None:
        _add_help(sf, [
            ("Para que serve", "Conteúdo extra adicionado ao final do Game.ini gerado pelo app."),
            ("Seções comuns", "[/script/shootergame.shootergamemode], [DinoSettings_Extra]"),
            ("Dica", "Use para overrides avançados como configurações de dinos específicos e regras de jogo custom."),
        ])

    def _after_ini() -> None:
        run_ui_tasks_chunked(
            sf, [_help], on_done=on_done, is_cancelled=is_cancelled, on_progress=on_progress,
            on_error=on_error, on_cancelled=on_cancelled,
        )

    _build_ini_editor(
        sf, "Conteúdo extra — Game.ini",
        srv.custom_game_ini_raw, "_raw_custom_game_ini_raw",
        vars_ref, accent, on_ready=_after_ini, on_progress=on_progress,
    )



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
    from ..ui_constants import _ARK_EVENT_LABEL_TO_ID
    field_types = {f.name: f.type for f in _fields(AsmServerConfig)}

    for field_name, var in vars_ref.items():
        if field_name.startswith("_"):
            continue
        ftype = field_types.get(field_name)
        try:
            raw = var.get()
            if field_name == "active_event":
                from ..ui_constants import _ARK_EVENT_LABEL_TO_ID, normalize_active_event
                setattr(
                    srv,
                    field_name,
                    normalize_active_event(_ARK_EVENT_LABEL_TO_ID.get(str(raw), str(raw).strip())),
                )
                continue
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

    # Nível máximo do jogador (base + ascensões → XP)
    if vars_ref.get("player_base_level") is not None:
        from ..ui.player_level_panel import sync_player_level_vars
        sync_player_level_vars(vars_ref)
        try:
            srv.player_base_level = int(float(vars_ref["player_base_level"].get()))
        except (ValueError, TypeError, tk.TclError):
            pass
        asc_var = vars_ref.get("player_ascension_state")
        if asc_var is not None:
            srv.player_ascension_state = str(asc_var.get())
        xp_var = vars_ref.get("override_max_xp_player")
        if xp_var is not None:
            try:
                srv.override_max_xp_player = int(float(xp_var.get()))
            except (ValueError, TypeError, tk.TclError):
                pass

    mult_var = vars_ref.get("player_engram_points_multiplier")
    if mult_var is not None and hasattr(srv, "player_engram_points_multiplier"):
        try:
            srv.player_engram_points_multiplier = float(
                str(mult_var.get()).replace(",", ".")
            )
        except (ValueError, TypeError, tk.TclError):
            pass

    # CPU affinity (lista de inteiros)
    cpu_var = vars_ref.get("_cpu_affinity_csv")
    if cpu_var:
        raw = cpu_var.get().strip()
        if raw:
            cores: list[int] = []
            for part in raw.replace(";", ",").split(","):
                part = part.strip()
                if not part:
                    continue
                try:
                    cores.append(int(part))
                except ValueError:
                    continue
            srv.cpu_affinity_cores = cores
        else:
            srv.cpu_affinity_cores = []

    day_vars = vars_ref.get("_auto_restart_day_vars")
    if day_vars:
        srv.auto_restart_days = sorted(
            idx for idx, var in day_vars.items() if var.get()
        )

    # Per-level stat multipliers
    pls = vars_ref.get("_pls")
    if pls:
        for attr, svars in pls.items():
            try:
                setattr(srv, attr, [float(sv.get()) for sv in svars])
            except Exception:
                pass

    # Editores agregados (Fase 4)
    from ..ui.tek_list_editor import (
        collect_class_multiplier_list,
        collect_class_name_list,
        collect_spawn_weight_list,
    )
    _agg_map = (
        ("harvest_resource_multipliers", "_list_harvest", collect_class_multiplier_list),
        ("dino_class_resistance_multipliers", "_list_dino_res", collect_class_multiplier_list),
        ("dino_class_damage_multipliers", "_list_dino_dmg", collect_class_multiplier_list),
        ("tamed_dino_class_resistance_multipliers", "_list_tamed_dino_res", collect_class_multiplier_list),
        ("tamed_dino_class_damage_multipliers", "_list_tamed_dino_dmg", collect_class_multiplier_list),
        ("dino_spawn_weight_multipliers", "_list_spawn_weight", collect_spawn_weight_list),
        ("prevent_dino_tame_class_names", "_list_prevent_tame", collect_class_name_list),
    )
    for attr, key, collector in _agg_map:
        rows = vars_ref.get(key)
        if rows is not None:
            setattr(srv, attr, collector(rows))


def _save(app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
    inst = app.asm_server_manager.get_instance(srv.id)
    status = inst.status if inst else "stopped"
    if not is_config_editable(status):
        import tkinter.messagebox as _mb
        _mb.showwarning(
            "Servidor em execução",
            "Pare o servidor antes de salvar.\n\n"
            "Alterações no INI e perfil só entram em vigor após reiniciar o processo.",
            parent=app,
        )
        return

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

    # 4. Escreve os INIs e arquivos de Steam ID (se install_dir existir)
    import os as _os
    if srv.install_dir and _os.path.isdir(srv.install_dir):
        try:
            from ..asm_engine.asm_ini_manager import write_ini
            write_ini(srv)
        except Exception:
            pass  # INIs serão escritos no próximo start

        from ..ark_server_files import write_allowed_cheater_steam_ids_safe

        def _warn(msg: str) -> None:
            log_fn = getattr(app, "_global_log", None)
            if log_fn:
                log_fn(msg, "warning")

        write_allowed_cheater_steam_ids_safe(
            srv.install_dir,
            list(srv.admin_ids or []),
            server_name=srv.name,
            on_warning=_warn,
        )

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
    from ..asm_engine.asm_preset_manager import AsmPresetManager, format_preset_categories
    from ..asm_engine.asm_config_categories import iter_preset_categories
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
    dlg.geometry("680x620")
    dlg.minsize(560, 480)
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
            ctk.CTkLabel(pf, text=f"Categorias: {format_preset_categories(p['categories'])}  •  {p['created_at'][:10]}",
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
    save_f.grid_rowconfigure(3, weight=1)

    ctk.CTkLabel(save_f, text="Nome do preset:", font=ctk.CTkFont(size=11),
                 text_color=t_sec, anchor="w").grid(row=0, column=0, padx=12, pady=(12, 2), sticky="w")
    name_entry = ctk.CTkEntry(save_f, placeholder_text="Meu Preset PvE")
    name_entry.grid(row=1, column=0, padx=12, pady=(0, 4), sticky="ew")

    cat_header = ctk.CTkFrame(save_f, fg_color="transparent")
    cat_header.grid(row=2, column=0, padx=12, pady=(8, 2), sticky="ew")
    cat_header.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(cat_header, text="Categorias a incluir:", font=ctk.CTkFont(size=11),
                 text_color=t_sec, anchor="w").grid(row=0, column=0, sticky="w")

    cat_vars: dict[str, tk.BooleanVar] = {}
    sel_all_var = tk.BooleanVar(value=True)

    def _toggle_all_cats() -> None:
        val = sel_all_var.get()
        for var in cat_vars.values():
            var.set(val)

    ctk.CTkCheckBox(
        cat_header, text="Selecionar tudo", variable=sel_all_var,
        font=ctk.CTkFont(size=10, weight="bold"), text_color=t_sec,
        border_color=accent, checkmark_color=accent,
        command=_toggle_all_cats,
    ).grid(row=0, column=1, sticky="e")

    cats_scroll = ctk.CTkScrollableFrame(save_f, fg_color=bg, corner_radius=8, height=220)
    cats_scroll.grid(row=3, column=0, padx=12, pady=(0, 8), sticky="nsew")
    cats_scroll.grid_columnconfigure((0, 1), weight=1)

    preset_cats = list(iter_preset_categories())
    for i, (slug, label) in enumerate(preset_cats):
        v = tk.BooleanVar(value=True)
        cat_vars[slug] = v
        ctk.CTkCheckBox(
            cats_scroll, text=label, variable=v,
            font=ctk.CTkFont(size=10), text_color=t_sec,
            border_color=accent, checkmark_color=accent,
        ).grid(row=i // 2, column=i % 2, padx=6, pady=2, sticky="w")

    ctk.CTkLabel(save_f, text="Descrição (opcional):", font=ctk.CTkFont(size=11),
                 text_color=t_sec, anchor="w").grid(row=4, column=0, padx=12, pady=(4, 2), sticky="w")
    desc_entry = ctk.CTkEntry(save_f, placeholder_text="Balanceamento para PvE casual")
    desc_entry.grid(row=5, column=0, padx=12, pady=(0, 8), sticky="ew")

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
                  command=_save_preset).grid(row=6, column=0, padx=12, pady=(0, 12), sticky="ew")
