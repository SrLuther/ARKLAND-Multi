"""Painel TEK de gerenciamento do bot Discord oBobonicClean."""
from __future__ import annotations

import os
import threading
import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..obobonic_bot import (
    COG_CATALOG,
    DEFAULT_PROJECT_PATH,
    ENV_SECTIONS,
    ArkMapEntry,
    MapHealthResult,
    ObobonicBotProcess,
    apply_env_section_updates,
    backup_env_file,
    collect_bot_log_text,
    discord_developer_url,
    discord_invite_url,
    health_check_maps,
    list_env_backups,
    mask_secret,
    parse_ark_maps_from_env,
    parse_bot_status_from_log,
    read_config_cogs,
    read_env_value,
    read_log_tail,
    restore_env_backup,
    sync_asm_servers_to_env,
    validate_discord_token,
    write_ark_maps_to_env,
    write_config_cogs,
)
from ..server_visibility import resolve_machine_public_ip
from ..ui_constants import (
    _BG,
    _CARD_BG,
    _GREEN,
    _GREEN_DARK,
    _GREEN_HOVER,
    _RED_DARK,
    _RED_HOVER,
    get_theme,
)

if TYPE_CHECKING:
    from ..app_tek import ARKTEKApp

_SEC_BG = "#0d0d1e"
_HEAD_BG = "#141428"
_INNER = "#16162a"
_BDR = "#2a2a45"
_FIELD_BG = "#111128"
_AMBER = "#e0af68"
_OFFLINE = "#f7768e"


def _head(parent: tk.Widget, text: str, bg: str = _INNER) -> None:
    tk.Label(parent, text=text, bg=bg, fg="#c8c8e8",
             font=ctk.CTkFont(size=12, weight="bold"),
             anchor="w").pack(fill="x", padx=10, pady=(8, 2))
    tk.Frame(parent, bg=_GREEN, height=1).pack(fill="x", padx=10, pady=(0, 6))


def _toast(app: "ARKTEKApp", msg: str, kind: str = "info") -> None:
    try:
        app._toast(msg, kind=kind)
    except Exception:
        if kind == "error":
            messagebox.showerror("oBobonic", msg)
        elif kind == "warning":
            messagebox.showwarning("oBobonic", msg)
        else:
            messagebox.showinfo("oBobonic", msg)


def build_obobonic_panel(app: "ARKTEKApp", parent: tk.Widget) -> None:
    theme = get_theme("tek")
    accent = theme["accent"]
    cfg = app.config_manager.config.obobonic

    parent.grid_rowconfigure(0, weight=0)
    parent.grid_rowconfigure(1, weight=1)
    parent.grid_columnconfigure(0, weight=1)

    bot_holder: Dict[str, Any] = {"proc": None}
    state: Dict[str, Any] = {
        "maps": [],
        "follow_logs": True,
        "poll_job": None,
        "health": {},  # name -> MapHealthResult
    }

    def _project_dir() -> Path:
        raw = (path_var.get() or "").strip() or DEFAULT_PROJECT_PATH
        return Path(raw)

    def _env_path() -> Path:
        return _project_dir() / ".env"

    def _read_env_text() -> str:
        p = _env_path()
        if not p.is_file():
            return ""
        return p.read_text(encoding="utf-8")

    def _ensure_bot() -> ObobonicBotProcess:
        pdir = _project_dir()
        proc = bot_holder.get("proc")
        if proc is None or proc.project_dir != pdir:
            proc = ObobonicBotProcess(pdir)
            bot_holder["proc"] = proc
        proc.set_auto_restart(auto_restart_var.get())
        return proc

    def _persist_path() -> None:
        cfg.project_path = str(_project_dir())
        app.config_manager.save()

    # ── Header ────────────────────────────────────────────────────────────
    header = ctk.CTkFrame(parent, fg_color=_HEAD_BG, corner_radius=0, height=72)
    header.grid(row=0, column=0, sticky="ew")
    header.grid_propagate(False)
    header.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        header, text="🎩  oBobonic — Bot Discord",
        font=ctk.CTkFont(size=20, weight="bold"),
        text_color=accent,
    ).grid(row=0, column=0, rowspan=2, padx=20, pady=14, sticky="w")

    status_dot = ctk.CTkLabel(header, text="●", font=ctk.CTkFont(size=18), text_color=_OFFLINE)
    status_dot.grid(row=0, column=1, padx=(0, 6), sticky="e")
    status_var = tk.StringVar(value="Parado")
    pid_var = tk.StringVar(value="PID —")
    ctk.CTkLabel(header, textvariable=status_var, font=ctk.CTkFont(size=12, weight="bold")).grid(
        row=0, column=2, sticky="w")
    ctk.CTkLabel(header, textvariable=pid_var, text_color="gray55",
                 font=ctk.CTkFont(size=10)).grid(row=1, column=2, sticky="w")

    # ── Corpo scrollável ──────────────────────────────────────────────────
    body = ctk.CTkScrollableFrame(parent, fg_color=_BG, corner_radius=0)
    body.grid(row=1, column=0, sticky="nsew")
    body.grid_columnconfigure(0, weight=1)

    # Caminho do projeto
    path_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    path_card.pack(fill="x", padx=16, pady=(16, 8))
    path_card.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(path_card, text="Pasta do bot (oBobonicClean)", text_color="gray60",
                 font=ctk.CTkFont(size=11, weight="bold")).grid(
        row=0, column=0, columnspan=3, padx=12, pady=(10, 4), sticky="w")

    path_var = tk.StringVar(value=cfg.project_path or DEFAULT_PROJECT_PATH)
    path_entry = ctk.CTkEntry(path_card, textvariable=path_var, height=30)
    path_entry.grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 10), sticky="ew")

    def _browse_path() -> None:
        chosen = filedialog.askdirectory(
            title="Selecionar pasta do oBobonicClean",
            initialdir=str(_project_dir()) if _project_dir().is_dir() else str(Path.home()),
        )
        if chosen:
            path_var.set(chosen)
            _persist_path()
            _refresh_validation()
            _load_maps()
            _refresh_logs()

    def _open_folder() -> None:
        p = _project_dir()
        if p.is_dir():
            os.startfile(str(p))  # type: ignore[attr-defined]
        else:
            _toast(app, "Pasta do bot não encontrada.", "warning")

    ctk.CTkButton(path_card, text="📁", width=36, height=30,
                  fg_color=theme["accent_muted_bg"], hover_color=theme["accent_hover"],
                  command=_browse_path).grid(row=1, column=2, padx=(0, 12), pady=(0, 10))

    val_lbl = ctk.CTkLabel(path_card, text="", text_color="gray55", anchor="w",
                           font=ctk.CTkFont(size=10), wraplength=720, justify="left")
    val_lbl.grid(row=2, column=0, columnspan=3, padx=12, pady=(0, 10), sticky="ew")

    # Controles
    ctrl_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    ctrl_card.pack(fill="x", padx=16, pady=8)

    btn_row = ctk.CTkFrame(ctrl_card, fg_color="transparent")
    btn_row.pack(fill="x", padx=12, pady=12)

    hidden_var = tk.BooleanVar(value=cfg.start_hidden)
    auto_restart_var = tk.BooleanVar(value=cfg.auto_restart_on_crash)
    health_before_start_var = tk.BooleanVar(value=cfg.health_check_before_start)

    def _set_status(running: bool, pid: Optional[int] = None) -> None:
        if running:
            status_var.set("Rodando")
            status_dot.configure(text_color=_GREEN)
            pid_var.set(f"PID {pid}" if pid else "PID —")
        else:
            status_var.set("Parado")
            status_dot.configure(text_color=_OFFLINE)
            pid_var.set("PID —")

    def _append_panel_log(msg: str) -> None:
        log_box.configure(state=tk.NORMAL)
        log_box.insert(tk.END, msg + "\n")
        if state["follow_logs"]:
            log_box.see(tk.END)
        log_box.configure(state=tk.DISABLED)

    def _on_action(ok: bool, msg: str) -> None:
        prefix = "✅ " if ok else "⚠ "
        _append_panel_log(prefix + msg)
        _refresh_status()
        _toast(app, msg, "info" if ok else "warning")

    def _start() -> None:
        _persist_path()
        bot = _ensure_bot()
        bot.set_auto_restart(auto_restart_var.get())

        def _worker() -> None:
            health: Optional[List[MapHealthResult]] = None
            if health_before_start_var.get():
                try:
                    env_text = _read_env_text()
                    maps = _collect_maps() or parse_ark_maps_from_env(env_text)
                    if maps:
                        health = health_check_maps(maps, env_text)
                        state["health"] = {h.name: h for h in health}
                        app.after(0, _refresh_health_ui)
                except Exception as exc:
                    app.after(0, lambda: _on_action(False, f"Health check falhou: {exc}"))
                    return
            ok, msg = bot.start(
                hidden=hidden_var.get(),
                skip_health=not health_before_start_var.get(),
                health_results=health,
            )
            app.after(0, lambda: _on_action(ok, msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _stop() -> None:
        bot = _ensure_bot()
        bot.set_auto_restart(False)

        def _worker() -> None:
            ok, msg = bot.stop()
            app.after(0, lambda: _on_action(ok, msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _restart() -> None:
        _persist_path()
        bot = _ensure_bot()
        bot.set_auto_restart(auto_restart_var.get())

        def _worker() -> None:
            health: Optional[List[MapHealthResult]] = None
            if health_before_start_var.get():
                env_text = _read_env_text()
                maps = _collect_maps() or parse_ark_maps_from_env(env_text)
                if maps:
                    health = health_check_maps(maps, env_text)
            ok, msg = bot.restart(
                hidden=hidden_var.get(),
                skip_health=not health_before_start_var.get(),
                health_results=health,
            )
            app.after(0, lambda: _on_action(ok, msg))

        threading.Thread(target=_worker, daemon=True).start()

    ctk.CTkButton(btn_row, text="▶  Iniciar", width=110, height=34,
                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=_start).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkButton(btn_row, text="⏹  Parar", width=100, height=34,
                  fg_color=_RED_DARK, hover_color=_RED_HOVER,
                  command=_stop).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkButton(btn_row, text="🔄  Reiniciar", width=120, height=34,
                  fg_color=theme["accent_muted_bg"], hover_color=theme["accent_hover"],
                  command=_restart).pack(side=tk.LEFT, padx=(0, 8))

    opt_row = ctk.CTkFrame(ctrl_card, fg_color="transparent")
    opt_row.pack(fill="x", padx=12, pady=(0, 12))

    def _save_opt() -> None:
        cfg.start_hidden = hidden_var.get()
        cfg.auto_restart_on_crash = auto_restart_var.get()
        cfg.health_check_before_start = health_before_start_var.get()
        app.config_manager.save()
        _ensure_bot().set_auto_restart(auto_restart_var.get())

    ctk.CTkCheckBox(opt_row, text="Modo oculto (sem janela)",
                    variable=hidden_var, command=_save_opt,
                    fg_color=theme["accent_dark"], hover_color=theme["accent_hover"]).pack(
        side=tk.LEFT, padx=(0, 12))
    ctk.CTkCheckBox(opt_row, text="Reiniciar ao crash",
                    variable=auto_restart_var, command=_save_opt,
                    fg_color=theme["accent_dark"], hover_color=theme["accent_hover"]).pack(
        side=tk.LEFT, padx=(0, 12))
    ctk.CTkCheckBox(opt_row, text="Verificar RCON antes de iniciar",
                    variable=health_before_start_var, command=_save_opt,
                    fg_color=theme["accent_dark"], hover_color=theme["accent_hover"]).pack(
        side=tk.LEFT)

    aux_row = ctk.CTkFrame(ctrl_card, fg_color="transparent")
    aux_row.pack(fill="x", padx=12, pady=(0, 12))

    def _install_deps() -> None:
        bot = _ensure_bot()
        _append_panel_log("📦 Criando .venv (se necessário) e instalando dependências...")

        def _worker() -> None:
            def on_line(line: str) -> None:
                if line.strip():
                    app.after(0, lambda l=line: _append_panel_log(l))

            ok, msg = bot.install_dependencies(on_line=on_line, create_venv=True)
            app.after(0, lambda: _on_action(ok, msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _sync_asm() -> None:
        asm_servers = app.asm_config_manager.servers
        if not asm_servers:
            _toast(app, "Nenhum servidor TEK cadastrado para sincronizar.", "warning")
            return
        env_path = _env_path()
        if not env_path.is_file():
            _toast(app, "Arquivo .env não encontrado na pasta do bot.", "error")
            return

        def _worker() -> None:
            try:
                env_text = env_path.read_text(encoding="utf-8")
                pub_ip = resolve_machine_public_ip(app.config_manager.config)
                default_host = pub_ip or read_env_value(env_text, "ARK_HOST") or "127.0.0.1"
                new_text, maps, logs = sync_asm_servers_to_env(
                    env_text, asm_servers, default_host=default_host,
                )
                if not maps:
                    app.after(0, lambda: _toast(app, logs[0] if logs else "Nada a sincronizar.", "warning"))
                    return
                env_path.write_text(new_text, encoding="utf-8")
                state["maps"] = maps

                def _done() -> None:
                    _load_maps()
                    for line in logs:
                        _append_panel_log("↻ " + line)
                    _toast(
                        app,
                        f"Sincronizado: {len(maps)} mapa(s) TEK → .env (RCON, query, senha).",
                        "info",
                    )
                    _run_health_check(quiet=True)

                app.after(0, _done)
            except OSError as exc:
                app.after(0, lambda: _toast(app, str(exc), "error"))

        _append_panel_log("↻ Sincronizando servidores TEK → .env do bot...")
        threading.Thread(target=_worker, daemon=True).start()

    ctk.CTkButton(aux_row, text="📦 Instalar deps", width=130, height=30,
                  fg_color=_SEC_BG, hover_color=theme["accent_hover"],
                  command=_install_deps).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkButton(aux_row, text="↻ Sync TEK → .env", width=140, height=30,
                  fg_color=theme["accent_muted_bg"], hover_color=theme["accent_hover"],
                  command=_sync_asm).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkButton(aux_row, text="📂 Abrir pasta", width=120, height=30,
                  fg_color=_SEC_BG, hover_color=theme["accent_hover"],
                  command=_open_folder).pack(side=tk.LEFT)

    # ── Status Discord (via logs) ─────────────────────────────────────────
    discord_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    discord_card.pack(fill="x", padx=16, pady=8)
    discord_inner = tk.Frame(discord_card, bg=_INNER)
    discord_inner.pack(fill="x", padx=2, pady=2)
    _head(discord_inner, "Status Discord (inferido dos logs)")

    discord_status_lbl = ctk.CTkLabel(
        discord_inner, text="—", anchor="w", justify="left",
        text_color="gray65", wraplength=700, font=ctk.CTkFont(size=10),
    )
    discord_status_lbl.pack(fill="x", padx=10, pady=(0, 6))

    discord_note = ctk.CTkLabel(
        discord_inner,
        text="Latência e contagem de guilds exigem API Discord — não disponível sem alterar o bot.",
        text_color="gray50", font=ctk.CTkFont(size=9), anchor="w", wraplength=700, justify="left",
    )
    discord_note.pack(fill="x", padx=10, pady=(0, 8))

    link_row = ctk.CTkFrame(discord_inner, fg_color="transparent")
    link_row.pack(fill="x", padx=10, pady=(0, 10))

    def _open_discord_dev() -> None:
        try:
            env_text = _read_env_text()
            token = read_env_value(env_text, "DISCORD_TOKEN")
            url = discord_developer_url(token)
            if url:
                webbrowser.open(url)
            else:
                webbrowser.open("https://discord.com/developers/applications")
        except Exception as exc:
            _toast(app, str(exc), "error")

    def _open_discord_invite() -> None:
        try:
            env_text = _read_env_text()
            token = read_env_value(env_text, "DISCORD_TOKEN")
            url = discord_invite_url(token)
            if url:
                webbrowser.open(url)
            else:
                _toast(app, "Token inválido — não foi possível gerar link de convite.", "warning")
        except Exception as exc:
            _toast(app, str(exc), "error")

    def _open_bancos() -> None:
        p = _project_dir() / ".bancos"
        if p.is_dir():
            os.startfile(str(p))  # type: ignore[attr-defined]
        else:
            _toast(app, "Pasta .bancos não encontrada.", "warning")

    def _open_data() -> None:
        p = _project_dir() / "data"
        if p.is_dir():
            os.startfile(str(p))  # type: ignore[attr-defined]
        else:
            _toast(app, "Pasta data não encontrada.", "warning")

    ctk.CTkButton(link_row, text="🔗 Dev Portal", width=110, height=28,
                  fg_color=theme["accent_muted_bg"], hover_color=theme["accent_hover"],
                  command=_open_discord_dev).pack(side=tk.LEFT, padx=(0, 6))
    ctk.CTkButton(link_row, text="➕ Convidar bot", width=110, height=28,
                  fg_color=theme["accent_muted_bg"], hover_color=theme["accent_hover"],
                  command=_open_discord_invite).pack(side=tk.LEFT, padx=(0, 6))
    ctk.CTkButton(link_row, text="🗄 .bancos", width=90, height=28,
                  fg_color=_SEC_BG, hover_color=theme["accent_hover"],
                  command=_open_bancos).pack(side=tk.LEFT, padx=(0, 6))
    ctk.CTkButton(link_row, text="📁 data/", width=80, height=28,
                  fg_color=_SEC_BG, hover_color=theme["accent_hover"],
                  command=_open_data).pack(side=tk.LEFT)

    def _refresh_discord_status() -> None:
        bot = _ensure_bot()
        log_text = collect_bot_log_text(
            _project_dir(),
            proc_log_lines=[],
            hidden_log_path=bot.hidden_log_path if bot else None,
        )
        if bot.is_running and not bot.hidden_mode:
            recent = []
            log_box.configure(state=tk.NORMAL)
            recent = log_box.get("1.0", tk.END).splitlines()[-400:]
            log_box.configure(state=tk.DISABLED)
            log_text = collect_bot_log_text(
                _project_dir(), proc_log_lines=recent, hidden_log_path=bot.hidden_log_path,
            )
        st = parse_bot_status_from_log(log_text)
        if bot.is_running and st.online:
            discord_status_lbl.configure(text=f"🟢 {st.summary}", text_color=_GREEN)
        elif bot.is_running:
            discord_status_lbl.configure(text=f"🟡 Iniciando… {st.summary}", text_color=_AMBER)
        else:
            discord_status_lbl.configure(text=f"⚫ Parado — {st.summary}", text_color="gray55")

    # ── Configuração .env (seções) ────────────────────────────────────────
    env_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    env_card.pack(fill="x", padx=16, pady=8)
    env_inner = tk.Frame(env_card, bg=_INNER)
    env_inner.pack(fill="x", padx=2, pady=2)
    _head(env_inner, "Configuração .env (chaves críticas)")

    env_section_var = tk.StringVar(value=ENV_SECTIONS[0]["id"] if ENV_SECTIONS else "")
    env_fields_fr = ctk.CTkFrame(env_inner, fg_color="transparent")
    env_fields_fr.pack(fill="x", padx=10, pady=(0, 8))
    env_field_vars: Dict[str, tk.StringVar] = {}

    def _rebuild_env_fields(*_args: Any) -> None:
        for w in env_fields_fr.winfo_children():
            w.destroy()
        env_field_vars.clear()
        sid = env_section_var.get()
        section = next((s for s in ENV_SECTIONS if s["id"] == sid), None)
        if not section:
            return
        env_text = _read_env_text()
        for row_i, (key, label, secret) in enumerate(section["keys"]):
            ctk.CTkLabel(env_fields_fr, text=label, text_color="gray60",
                         font=ctk.CTkFont(size=10)).grid(row=row_i, column=0, sticky="w", padx=(0, 8), pady=3)
            raw = read_env_value(env_text, key)
            display = mask_secret(raw) if secret and raw else raw
            var = tk.StringVar(value=display)
            env_field_vars[key] = var
            show = "*" if secret else ""
            ent = ctk.CTkEntry(env_fields_fr, textvariable=var, height=28, show=show)
            ent.grid(row=row_i, column=1, sticky="ew", pady=3)
            ctk.CTkLabel(env_fields_fr, text=key, text_color="gray45",
                         font=ctk.CTkFont(size=9)).grid(row=row_i, column=2, sticky="w", padx=(8, 0))
        env_fields_fr.grid_columnconfigure(1, weight=1)

    env_sel_row = ctk.CTkFrame(env_inner, fg_color="transparent")
    env_sel_row.pack(fill="x", padx=10, pady=(0, 6))
    ctk.CTkLabel(env_sel_row, text="Seção:", text_color="gray60").pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkOptionMenu(
        env_sel_row,
        variable=env_section_var,
        values=[s["id"] for s in ENV_SECTIONS],
        command=lambda _v: _rebuild_env_fields(),
        width=160, height=28,
        fg_color=_SEC_BG,
    ).pack(side=tk.LEFT)
    _rebuild_env_fields()

    def _save_env_section() -> None:
        env_path = _env_path()
        if not env_path.is_file():
            _toast(app, ".env não encontrado.", "error")
            return
        sid = env_section_var.get()
        section = next((s for s in ENV_SECTIONS if s["id"] == sid), None)
        if not section:
            return
        updates = {key: var.get().strip() for key, var in env_field_vars.items()}
        secret_keys = {key for key, _l, sec in section["keys"] if sec}
        for key in secret_keys:
            if updates.get(key) == mask_secret(read_env_value(_read_env_text(), key)):
                updates[key] = read_env_value(_read_env_text(), key)
        try:
            text = env_path.read_text(encoding="utf-8")
            new_text = apply_env_section_updates(text, updates)
            env_path.write_text(new_text, encoding="utf-8")
            _append_panel_log(f"✅ Seção «{sid}» salva no .env. Reinicie o bot para aplicar.")
            _toast(app, f"Seção {sid} salva.", "info")
            _refresh_validation()
            _rebuild_env_fields()
        except OSError as exc:
            _toast(app, str(exc), "error")

    def _backup_env() -> None:
        env_path = _env_path()
        if not env_path.is_file():
            _toast(app, ".env não encontrado.", "error")
            return
        try:
            backup = backup_env_file(env_path)
            _append_panel_log(f"💾 Backup: {backup.name}")
            _toast(app, f"Backup criado: {backup.name}", "info")
        except OSError as exc:
            _toast(app, str(exc), "error")

    def _restore_env() -> None:
        backups = list_env_backups(_project_dir())
        if not backups:
            _toast(app, "Nenhum backup .env encontrado.", "warning")
            return
        latest = backups[0]
        if not messagebox.askyesno(
            "Restaurar .env",
            f"Restaurar backup mais recente?\n\n{latest.name}\n\nO .env atual será sobrescrito.",
        ):
            return
        try:
            restore_env_backup(latest, _env_path())
            _append_panel_log(f"↩ .env restaurado de {latest.name}")
            _toast(app, "Backup restaurado. Reinicie o bot.", "info")
            _refresh_validation()
            _rebuild_env_fields()
            _load_maps()
        except OSError as exc:
            _toast(app, str(exc), "error")

    env_btn_row = ctk.CTkFrame(env_inner, fg_color="transparent")
    env_btn_row.pack(fill="x", padx=10, pady=(0, 10))
    ctk.CTkButton(env_btn_row, text="💾 Salvar seção", width=120, height=30,
                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=_save_env_section).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkButton(env_btn_row, text="💾 Backup .env", width=120, height=30,
                  fg_color=_SEC_BG, hover_color=theme["accent_hover"],
                  command=_backup_env).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkButton(env_btn_row, text="↩ Restaurar", width=100, height=30,
                  fg_color=_SEC_BG, hover_color=theme["accent_hover"],
                  command=_restore_env).pack(side=tk.LEFT)
    ctk.CTkLabel(
        env_btn_row,
        text="Mapas ARK: use «Salas» acima. Cogs: edite abaixo. Dados JSON: pastas .bancos/ e data/.",
        text_color="gray50", font=ctk.CTkFont(size=9),
    ).pack(side=tk.LEFT, padx=(12, 0))

    # ── Status dos mapas (health) ─────────────────────────────────────────
    health_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    health_card.pack(fill="x", padx=16, pady=8)
    health_inner = tk.Frame(health_card, bg=_INNER)
    health_inner.pack(fill="both", expand=True, padx=2, pady=2)
    _head(health_inner, "Status dos mapas (RCON / query)")

    health_list_fr = ctk.CTkFrame(health_inner, fg_color="transparent")
    health_list_fr.pack(fill="x", padx=10, pady=(0, 8))
    health_rows: Dict[str, ctk.CTkLabel] = {}

    def _refresh_health_ui() -> None:
        for w in health_list_fr.winfo_children():
            w.destroy()
        health_rows.clear()
        health_map: Dict[str, MapHealthResult] = state.get("health") or {}
        if not health_map:
            ctk.CTkLabel(
                health_list_fr, text="Clique em «Testar RCON» ou sincronize com os servidores TEK.",
                text_color="gray55", font=ctk.CTkFont(size=10), anchor="w",
            ).pack(fill="x", pady=4)
            return
        for name, h in sorted(health_map.items(), key=lambda x: x[0].lower()):
            row = ctk.CTkFrame(health_list_fr, fg_color=_SEC_BG, corner_radius=6)
            row.pack(fill="x", pady=2)
            dot = "🟢" if h.online else "🔴"
            detail = h.status_label
            if not h.rcon_ok and h.rcon_detail:
                detail += f" — {h.rcon_detail[:60]}"
            lbl = ctk.CTkLabel(
                row, text=f"{dot}  {name}: {detail}",
                anchor="w", font=ctk.CTkFont(size=10),
                text_color=_GREEN if h.online else "gray60",
            )
            lbl.pack(fill="x", padx=10, pady=6)
            health_rows[name] = lbl

    def _run_health_check(quiet: bool = False) -> None:
        env_path = _env_path()
        if not env_path.is_file():
            if not quiet:
                _toast(app, ".env não encontrado.", "error")
            return

        def _worker() -> None:
            try:
                env_text = env_path.read_text(encoding="utf-8")
                maps = _collect_maps() or parse_ark_maps_from_env(env_text)
                if not maps:
                    app.after(0, lambda: _toast(app, "Nenhum mapa configurado no .env.", "warning"))
                    return
                results = health_check_maps(maps, env_text)
                state["health"] = {h.name: h for h in results}

                def _done() -> None:
                    _refresh_health_ui()
                    ok_n = sum(1 for h in results if h.rcon_ok)
                    if not quiet:
                        _toast(
                            app,
                            f"Health check: {ok_n}/{len(results)} mapa(s) com RCON OK.",
                            "info" if ok_n == len(results) else "warning",
                        )

                app.after(0, _done)
            except Exception as exc:
                app.after(0, lambda: _toast(app, str(exc), "error"))

        if not quiet:
            _append_panel_log("🔍 Testando RCON/query de cada mapa...")
        threading.Thread(target=_worker, daemon=True).start()

    health_btns = ctk.CTkFrame(health_inner, fg_color="transparent")
    health_btns.pack(fill="x", padx=10, pady=(0, 10))
    ctk.CTkButton(health_btns, text="🔍 Testar RCON", width=130, height=30,
                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=lambda: _run_health_check(quiet=False)).pack(side=tk.LEFT)

    # ── Salas / Mapas ARK ─────────────────────────────────────────────────
    maps_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    maps_card.pack(fill="x", padx=16, pady=8)
    maps_inner = tk.Frame(maps_card, bg=_INNER)
    maps_inner.pack(fill="both", expand=True, padx=2, pady=2)
    _head(maps_inner, "Salas ARK no .env (RCON, query, serviço)")

    maps_list_fr = ctk.CTkFrame(maps_inner, fg_color="transparent")
    maps_list_fr.pack(fill="x", padx=10, pady=(0, 8))

    map_rows: List[Dict[str, Any]] = []

    def _clear_map_rows() -> None:
        for row in map_rows:
            row["frame"].destroy()
        map_rows.clear()

    def _add_map_row(entry: Optional[ArkMapEntry] = None) -> None:
        idx = entry.index if entry else (max((m.index for m in state["maps"]), default=0) + 1)
        fr = ctk.CTkFrame(maps_list_fr, fg_color=_SEC_BG, corner_radius=8)
        fr.pack(fill="x", pady=4)
        for c, w in enumerate((28, 1, 90, 90, 1, 50, 32)):
            fr.grid_columnconfigure(c, weight=w if w == 1 else 0)

        name_var = tk.StringVar(value=entry.name if entry else "")
        port_var = tk.StringVar(value=entry.port if entry else "")
        query_var = tk.StringVar(value=entry.query_port if entry else "")
        svc_var = tk.StringVar(value=entry.service if entry else "")
        max_var = tk.StringVar(value=entry.max_players if entry else "50")

        ctk.CTkLabel(fr, text=f"#{idx}", width=28, text_color="gray55").grid(
            row=0, column=0, rowspan=2, padx=(8, 4), pady=8)
        ctk.CTkLabel(fr, text="Nome", text_color="gray60", font=ctk.CTkFont(size=10)).grid(
            row=0, column=1, sticky="w", padx=4)
        ctk.CTkEntry(fr, textvariable=name_var, height=28,
                     placeholder_text="Ex: Brighamia").grid(
            row=1, column=1, sticky="ew", padx=4, pady=(0, 8))
        ctk.CTkLabel(fr, text="RCON", text_color="gray60", font=ctk.CTkFont(size=10)).grid(
            row=0, column=2, sticky="w", padx=4)
        ctk.CTkEntry(fr, textvariable=port_var, width=80, height=28).grid(
            row=1, column=2, padx=4, pady=(0, 8))
        ctk.CTkLabel(fr, text="Query", text_color="gray60", font=ctk.CTkFont(size=10)).grid(
            row=0, column=3, sticky="w", padx=4)
        ctk.CTkEntry(fr, textvariable=query_var, width=80, height=28).grid(
            row=1, column=3, padx=4, pady=(0, 8))
        ctk.CTkLabel(fr, text="Serviço", text_color="gray60", font=ctk.CTkFont(size=10)).grid(
            row=0, column=4, sticky="w", padx=4)
        ctk.CTkEntry(fr, textvariable=svc_var, height=28,
                     placeholder_text="ark-brighamia.service").grid(
            row=1, column=4, sticky="ew", padx=4, pady=(0, 8))
        ctk.CTkLabel(fr, text="Max", text_color="gray60", font=ctk.CTkFont(size=10)).grid(
            row=0, column=5, sticky="w", padx=4)
        ctk.CTkEntry(fr, textvariable=max_var, width=44, height=28).grid(
            row=1, column=5, padx=4, pady=(0, 8))

        def _remove() -> None:
            fr.destroy()
            map_rows[:] = [r for r in map_rows if r["frame"] is not fr]

        ctk.CTkButton(fr, text="✕", width=32, height=28,
                      fg_color=_RED_DARK, hover_color=_RED_HOVER,
                      command=_remove).grid(row=0, column=6, rowspan=2, padx=8, pady=8)

        map_rows.append({
            "frame": fr,
            "index": idx,
            "name": name_var,
            "port": port_var,
            "query": query_var,
            "service": svc_var,
            "max": max_var,
        })

    def _load_maps() -> None:
        _clear_map_rows()
        env_path = _env_path()
        if not env_path.is_file():
            state["maps"] = []
            return
        try:
            text = env_path.read_text(encoding="utf-8")
            state["maps"] = parse_ark_maps_from_env(text)
            for m in state["maps"]:
                _add_map_row(m)
        except OSError as exc:
            _toast(app, f"Erro ao ler .env: {exc}", "error")

    def _collect_maps() -> List[ArkMapEntry]:
        entries: List[ArkMapEntry] = []
        for i, row in enumerate(map_rows, start=1):
            name = row["name"].get().strip()
            port = row["port"].get().strip()
            if not name or not port:
                continue
            entries.append(ArkMapEntry(
                index=i,
                name=name,
                port=port,
                query_port=row["query"].get().strip(),
                service=row["service"].get().strip(),
                max_players=row["max"].get().strip() or "50",
            ))
        return entries

    def _save_maps() -> None:
        env_path = _env_path()
        if not env_path.is_file():
            _toast(app, "Arquivo .env não encontrado na pasta do bot.", "error")
            return
        try:
            text = env_path.read_text(encoding="utf-8")
            maps = _collect_maps()
            new_text = write_ark_maps_to_env(text, maps)
            env_path.write_text(new_text, encoding="utf-8")
            state["maps"] = maps
            _append_panel_log(f"✅ Salas salvas no .env ({len(maps)} mapa(s)). Reinicie o bot para aplicar.")
            _toast(app, f"{len(maps)} sala(s) salva(s) no .env.", "info")
        except OSError as exc:
            _toast(app, str(exc), "error")

    maps_btns = ctk.CTkFrame(maps_inner, fg_color="transparent")
    maps_btns.pack(fill="x", padx=10, pady=(0, 10))
    ctk.CTkButton(maps_btns, text="＋ Adicionar sala", width=140, height=30,
                  fg_color=theme["accent_muted_bg"], hover_color=theme["accent_hover"],
                  command=lambda: _add_map_row()).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkButton(maps_btns, text="💾 Salvar salas", width=120, height=30,
                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=_save_maps).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkButton(maps_btns, text="↻ Recarregar", width=110, height=30,
                  fg_color=_SEC_BG, hover_color=theme["accent_hover"],
                  command=_load_maps).pack(side=tk.LEFT)

    # ── Gerenciador de cogs ───────────────────────────────────────────────
    cogs_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    cogs_card.pack(fill="x", padx=16, pady=8)
    cogs_inner = tk.Frame(cogs_card, bg=_INNER)
    cogs_inner.pack(fill="x", padx=2, pady=2)
    _head(cogs_inner, "Módulos (cogs) — habilitar/desabilitar em config.py")

    cogs_grid = ctk.CTkFrame(cogs_inner, fg_color="transparent")
    cogs_grid.pack(fill="x", padx=10, pady=(0, 6))
    cog_vars: Dict[str, tk.BooleanVar] = {}

    def _load_cogs() -> None:
        for w in cogs_grid.winfo_children():
            w.destroy()
        cog_vars.clear()
        enabled, available = read_config_cogs(_project_dir())
        if not available:
            ctk.CTkLabel(cogs_grid, text="config.py ou pasta cogs/ não encontrados.",
                         text_color="gray55", font=ctk.CTkFont(size=10)).pack(anchor="w")
            return
        cols = 2
        for i, name in enumerate(available):
            meta = COG_CATALOG.get(name, {})
            label = meta.get("label", name)
            env_hint = meta.get("env", [])
            hint = f" ({', '.join(env_hint[:2])})" if env_hint else ""
            var = tk.BooleanVar(value=name in enabled)
            cog_vars[name] = var
            txt = f"{label}{hint}"
            cb = ctk.CTkCheckBox(
                cogs_grid, text=txt, variable=var,
                font=ctk.CTkFont(size=10),
                fg_color=theme["accent_dark"], hover_color=theme["accent_hover"],
            )
            cb.grid(row=i // cols, column=i % cols, sticky="w", padx=4, pady=2)

    def _save_cogs() -> None:
        enabled = [name for name, var in cog_vars.items() if var.get()]
        if not enabled:
            _toast(app, "Selecione ao menos um cog.", "warning")
            return
        if "admin" not in enabled:
            _toast(app, "O cog «admin» não pode ser desabilitado.", "warning")
            return
        try:
            write_config_cogs(_project_dir(), enabled)
            _append_panel_log(f"✅ Cogs salvos em config.py ({len(enabled)} ativos). Reinicie o bot.")
            _toast(app, f"{len(enabled)} cog(s) ativos — reinicie o bot.", "info")
            _load_cogs()
        except OSError as exc:
            _toast(app, str(exc), "error")

    cogs_btn_row = ctk.CTkFrame(cogs_inner, fg_color="transparent")
    cogs_btn_row.pack(fill="x", padx=10, pady=(0, 10))
    ctk.CTkButton(cogs_btn_row, text="💾 Salvar cogs", width=120, height=30,
                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=_save_cogs).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkButton(cogs_btn_row, text="↻ Recarregar", width=110, height=30,
                  fg_color=_SEC_BG, hover_color=theme["accent_hover"],
                  command=_load_cogs).pack(side=tk.LEFT)
    ctk.CTkLabel(
        cogs_btn_row,
        text="Alterações exigem reinício. Comandos !load/!reload continuam no Discord.",
        text_color="gray50", font=ctk.CTkFont(size=9),
    ).pack(side=tk.LEFT, padx=(12, 0))

    # ── Logs ──────────────────────────────────────────────────────────────
    log_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    log_card.pack(fill="both", expand=True, padx=16, pady=(8, 16))
    log_card.grid_rowconfigure(1, weight=1)
    log_card.grid_columnconfigure(0, weight=1)

    log_hdr = ctk.CTkFrame(log_card, fg_color="transparent")
    log_hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
    ctk.CTkLabel(log_hdr, text="Logs", font=ctk.CTkFont(size=13, weight="bold"),
                 text_color=accent).pack(side=tk.LEFT)

    follow_var = tk.BooleanVar(value=True)
    state["follow_logs"] = True

    log_host = tk.Frame(log_card, bg=_FIELD_BG, highlightthickness=1,
                        highlightbackground=_BDR)
    log_host.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
    log_host.grid_rowconfigure(0, weight=1)
    log_host.grid_columnconfigure(0, weight=1)

    log_box = tk.Text(log_host, bg="#0a0a14", fg="#9ece6a",
                      insertbackground="#c8c8e8", font=("Consolas", 10),
                      relief=tk.FLAT, wrap=tk.WORD, state=tk.DISABLED)
    log_sb = tk.Scrollbar(log_host, command=log_box.yview,
                          bg=_BDR, troughcolor=_BG, width=10)
    log_box.configure(yscrollcommand=log_sb.set)
    log_box.grid(row=0, column=0, sticky="nsew")
    log_sb.grid(row=0, column=1, sticky="ns")

    def _refresh_logs() -> None:
        bot = _ensure_bot()
        for line in bot.drain_logs():
            log_box.configure(state=tk.NORMAL)
            log_box.insert(tk.END, line + "\n")
            log_box.configure(state=tk.DISABLED)
        if bot.hidden_mode and bot.is_running:
            tail = read_log_tail(bot.hidden_log_path, max_lines=400)
            if tail:
                log_box.configure(state=tk.NORMAL)
                log_box.delete("1.0", tk.END)
                log_box.insert("1.0", tail)
                log_box.configure(state=tk.DISABLED)
        elif not bot.is_running:
            tail = read_log_tail(bot.hidden_log_path, max_lines=200)
            if tail and log_box.index(tk.END) == "1.0":
                log_box.configure(state=tk.NORMAL)
                log_box.insert("1.0", tail)
                log_box.configure(state=tk.DISABLED)
        if follow_var.get():
            log_box.see(tk.END)

    def _clear_logs() -> None:
        log_box.configure(state=tk.NORMAL)
        log_box.delete("1.0", tk.END)
        log_box.configure(state=tk.DISABLED)

    def _toggle_follow() -> None:
        state["follow_logs"] = follow_var.get()

    log_btns = ctk.CTkFrame(log_hdr, fg_color="transparent")
    log_btns.pack(side=tk.RIGHT)
    ctk.CTkCheckBox(log_btns, text="Seguir", variable=follow_var,
                    command=_toggle_follow, width=70,
                    fg_color=theme["accent_dark"]).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkButton(log_btns, text="↻ Atualizar", width=90, height=28,
                  fg_color=_SEC_BG, hover_color=theme["accent_hover"],
                  command=_refresh_logs).pack(side=tk.LEFT, padx=(0, 6))
    ctk.CTkButton(log_btns, text="Limpar", width=70, height=28,
                  fg_color=_SEC_BG, hover_color=theme["accent_hover"],
                  command=_clear_logs).pack(side=tk.LEFT)

    def _refresh_validation() -> None:
        bot = _ensure_bot()
        ok, msg = bot.validate(check_token=False)
        parts: List[str] = []
        if ok:
            parts.append("✅ bot.py, .env e Python OK")
        else:
            parts.append(f"⚠ {msg.replace(chr(10), ' — ')}")
        env_path = _env_path()
        if env_path.is_file():
            try:
                env_text = env_path.read_text(encoding="utf-8")
                tok_ok, tok_msg = validate_discord_token(env_text)
                if tok_ok:
                    parts.append("✅ DISCORD_TOKEN válido")
                    val_lbl.configure(text="  ·  ".join(parts), text_color=_GREEN)
                else:
                    parts.append(f"⚠ {tok_msg}")
                    val_lbl.configure(text="  ·  ".join(parts), text_color=_AMBER)
            except OSError:
                val_lbl.configure(text="  ·  ".join(parts), text_color=_AMBER)
        else:
            val_lbl.configure(text="  ·  ".join(parts), text_color=_AMBER)

    def _refresh_status() -> None:
        bot = _ensure_bot()
        _set_status(bot.is_running, bot.pid)
        _refresh_validation()

    _health_poll_counter = {"n": 0}

    def _poll_tick() -> None:
        _refresh_logs()
        _refresh_status()
        _refresh_discord_status()
        _health_poll_counter["n"] += 1
        if _health_poll_counter["n"] % 30 == 0 and map_rows:
            _run_health_check(quiet=True)
        state["poll_job"] = app.after(500, _poll_tick)

    def _on_destroy(_event=None) -> None:
        job = state.get("poll_job")
        if job:
            try:
                app.after_cancel(job)
            except Exception:
                pass
        proc = bot_holder.get("proc")
        if proc:
            proc.shutdown()

    parent.bind("<Destroy>", _on_destroy, add="+")
    path_entry.bind("<FocusOut>", lambda _e: _persist_path())

    _refresh_validation()
    _load_maps()
    _load_cogs()
    _refresh_health_ui()
    _refresh_logs()
    _poll_tick()

    app._obobonic_panel_state = state
    app._obobonic_bot_holder = bot_holder
