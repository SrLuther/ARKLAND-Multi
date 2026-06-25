"""Painel TEK de gerenciamento do bot Discord oBobonicClean."""
from __future__ import annotations

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..obobonic_bot import (
    DEFAULT_PROJECT_PATH,
    ArkMapEntry,
    ObobonicBotProcess,
    parse_ark_maps_from_env,
    read_log_tail,
    write_ark_maps_to_env,
)
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


def _head(parent: tk.Widget, text: str, bg: str = _INNER) -> None:
    tk.Label(parent, text=text, bg=bg, fg="#c8c8e8",
             font=ctk.CTkFont(size=12, weight="bold"),
             anchor="w").pack(fill="x", padx=10, pady=(8, 2))
    tk.Frame(parent, bg=_GREEN, height=1).pack(fill="x", padx=10, pady=(0, 6))


def build_obobonic_panel(app: "ARKTEKApp", parent: tk.Widget) -> None:
    theme = get_theme("tek")
    accent = theme["accent"]
    cfg = app.config_manager.config.obobonic

    parent.grid_rowconfigure(1, weight=1)
    parent.grid_columnconfigure(0, weight=1)

    bot_holder: Dict[str, Any] = {"proc": None}
    state: Dict[str, Any] = {
        "maps": [],
        "follow_logs": True,
        "poll_job": None,
    }

    def _project_dir() -> Path:
        raw = (path_var.get() or "").strip() or DEFAULT_PROJECT_PATH
        return Path(raw)

    def _ensure_bot() -> ObobonicBotProcess:
        pdir = _project_dir()
        proc = bot_holder.get("proc")
        if proc is None or proc.project_dir != pdir:
            proc = ObobonicBotProcess(pdir)
            bot_holder["proc"] = proc
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

    status_dot = ctk.CTkLabel(header, text="●", font=ctk.CTkFont(size=18), text_color="#f7768e")
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

    ctk.CTkLabel(path_card, text="Pasta do bot", text_color="gray60",
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
            messagebox.showwarning("Pasta", "Pasta do bot não encontrada.")

    ctk.CTkButton(path_card, text="📁", width=36, height=30,
                  fg_color=theme["accent_muted_bg"], hover_color=theme["accent_hover"],
                  command=_browse_path).grid(row=1, column=2, padx=(0, 12), pady=(0, 10))

    val_lbl = ctk.CTkLabel(path_card, text="", text_color="gray55", anchor="w",
                           font=ctk.CTkFont(size=10))
    val_lbl.grid(row=2, column=0, columnspan=3, padx=12, pady=(0, 10), sticky="ew")

    # Controles
    ctrl_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    ctrl_card.pack(fill="x", padx=16, pady=8)

    btn_row = ctk.CTkFrame(ctrl_card, fg_color="transparent")
    btn_row.pack(fill="x", padx=12, pady=12)

    hidden_var = tk.BooleanVar(value=cfg.start_hidden)

    def _set_status(running: bool, pid: Optional[int] = None) -> None:
        if running:
            status_var.set("Rodando")
            status_dot.configure(text_color=_GREEN)
            pid_var.set(f"PID {pid}" if pid else "PID —")
        else:
            status_var.set("Parado")
            status_dot.configure(text_color="#f7768e")
            pid_var.set("PID —")

    def _append_panel_log(msg: str) -> None:
        log_box.configure(state=tk.NORMAL)
        log_box.insert(tk.END, msg + "\n")
        if state["follow_logs"]:
            log_box.see(tk.END)
        log_box.configure(state=tk.DISABLED)

    def _start() -> None:
        _persist_path()
        bot = _ensure_bot()

        def _worker() -> None:
            ok, msg = bot.start(hidden=hidden_var.get())
            app.after(0, lambda: _on_action(ok, msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _stop() -> None:
        bot = _ensure_bot()

        def _worker() -> None:
            ok, msg = bot.stop()
            app.after(0, lambda: _on_action(ok, msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _restart() -> None:
        _persist_path()
        bot = _ensure_bot()

        def _worker() -> None:
            ok, msg = bot.restart(hidden=hidden_var.get())
            app.after(0, lambda: _on_action(ok, msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_action(ok: bool, msg: str) -> None:
        prefix = "✅ " if ok else "⚠ "
        _append_panel_log(prefix + msg)
        _refresh_status()

    ctk.CTkButton(btn_row, text="▶  Iniciar", width=110, height=34,
                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=_start).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkButton(btn_row, text="⏹  Parar", width=100, height=34,
                  fg_color=_RED_DARK, hover_color=_RED_HOVER,
                  command=_stop).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkButton(btn_row, text="🔄  Reiniciar", width=120, height=34,
                  fg_color=theme["accent_muted_bg"], hover_color=theme["accent_hover"],
                  command=_restart).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkCheckBox(btn_row, text="Modo oculto (sem janela)",
                    variable=hidden_var,
                    command=lambda: setattr(cfg, "start_hidden", hidden_var.get()) or app.config_manager.save(),
                    fg_color=theme["accent_dark"], hover_color=theme["accent_hover"]).pack(
        side=tk.LEFT, padx=(12, 0))

    aux_row = ctk.CTkFrame(ctrl_card, fg_color="transparent")
    aux_row.pack(fill="x", padx=12, pady=(0, 12))

    def _install_deps() -> None:
        bot = _ensure_bot()
        _append_panel_log("📦 Instalando dependências...")

        def _worker() -> None:
            def on_line(line: str) -> None:
                if line.strip():
                    app.after(0, lambda l=line: _append_panel_log(l))

            ok, msg = bot.install_dependencies(on_line=on_line)
            app.after(0, lambda: _on_action(ok, msg))

        threading.Thread(target=_worker, daemon=True).start()

    ctk.CTkButton(aux_row, text="📦 Instalar deps", width=130, height=30,
                  fg_color=_SEC_BG, hover_color=theme["accent_hover"],
                  command=_install_deps).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkButton(aux_row, text="📂 Abrir pasta", width=120, height=30,
                  fg_color=_SEC_BG, hover_color=theme["accent_hover"],
                  command=_open_folder).pack(side=tk.LEFT)

    # ── Salas / Mapas ARK ─────────────────────────────────────────────────
    maps_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    maps_card.pack(fill="x", padx=16, pady=8)
    maps_inner = tk.Frame(maps_card, bg=_INNER)
    maps_inner.pack(fill="both", expand=True, padx=2, pady=2)
    _head(maps_inner, "Configuração de salas (mapas ARK no .env)")

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
        fr.grid_columnconfigure(1, weight=1)
        fr.grid_columnconfigure(3, weight=1)

        name_var = tk.StringVar(value=entry.name if entry else "")
        port_var = tk.StringVar(value=entry.port if entry else "")
        svc_var = tk.StringVar(value=entry.service if entry else "")
        max_var = tk.StringVar(value=entry.max_players if entry else "50")

        ctk.CTkLabel(fr, text=f"#{idx}", width=28, text_color="gray55").grid(
            row=0, column=0, rowspan=2, padx=(8, 4), pady=8)
        ctk.CTkLabel(fr, text="Nome", text_color="gray60", font=ctk.CTkFont(size=10)).grid(
            row=0, column=1, sticky="w", padx=4)
        ctk.CTkEntry(fr, textvariable=name_var, height=28, placeholder_text="Ex: Ragnarok").grid(
            row=1, column=1, sticky="ew", padx=4, pady=(0, 8))
        ctk.CTkLabel(fr, text="Porta RCON", text_color="gray60", font=ctk.CTkFont(size=10)).grid(
            row=0, column=2, sticky="w", padx=4)
        ctk.CTkEntry(fr, textvariable=port_var, width=90, height=28).grid(
            row=1, column=2, padx=4, pady=(0, 8))
        ctk.CTkLabel(fr, text="Serviço", text_color="gray60", font=ctk.CTkFont(size=10)).grid(
            row=0, column=3, sticky="w", padx=4)
        ctk.CTkEntry(fr, textvariable=svc_var, height=28,
                     placeholder_text="ark-ragnarok.service").grid(
            row=1, column=3, sticky="ew", padx=4, pady=(0, 8))
        ctk.CTkLabel(fr, text="Max", text_color="gray60", font=ctk.CTkFont(size=10)).grid(
            row=0, column=4, sticky="w", padx=4)
        ctk.CTkEntry(fr, textvariable=max_var, width=50, height=28).grid(
            row=1, column=4, padx=4, pady=(0, 8))

        def _remove() -> None:
            fr.destroy()
            map_rows[:] = [r for r in map_rows if r["frame"] is not fr]

        ctk.CTkButton(fr, text="✕", width=32, height=28,
                      fg_color=_RED_DARK, hover_color=_RED_HOVER,
                      command=_remove).grid(row=0, column=5, rowspan=2, padx=8, pady=8)

        map_rows.append({
            "frame": fr,
            "index": idx,
            "name": name_var,
            "port": port_var,
            "service": svc_var,
            "max": max_var,
        })

    def _load_maps() -> None:
        _clear_map_rows()
        env_path = _project_dir() / ".env"
        if not env_path.is_file():
            state["maps"] = []
            return
        try:
            text = env_path.read_text(encoding="utf-8")
            state["maps"] = parse_ark_maps_from_env(text)
            for m in state["maps"]:
                _add_map_row(m)
        except OSError as exc:
            _append_panel_log(f"❌ Erro ao ler .env: {exc}")

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
                service=row["service"].get().strip(),
                max_players=row["max"].get().strip() or "50",
            ))
        return entries

    def _save_maps() -> None:
        env_path = _project_dir() / ".env"
        if not env_path.is_file():
            messagebox.showerror("Salvar salas", "Arquivo .env não encontrado na pasta do bot.")
            return
        try:
            text = env_path.read_text(encoding="utf-8")
            maps = _collect_maps()
            new_text = write_ark_maps_to_env(text, maps)
            env_path.write_text(new_text, encoding="utf-8")
            state["maps"] = maps
            _append_panel_log(f"✅ Salas salvas no .env ({len(maps)} mapa(s)). Reinicie o bot para aplicar.")
            messagebox.showinfo(
                "Salvo",
                "Configuração de salas salva no .env.\nReinicie o bot para aplicar as alterações.",
            )
        except OSError as exc:
            messagebox.showerror("Erro", str(exc))

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

    # ── Cogs ativos ───────────────────────────────────────────────────────
    cogs_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    cogs_card.pack(fill="x", padx=16, pady=8)
    cogs_inner = tk.Frame(cogs_card, bg=_INNER)
    cogs_inner.pack(fill="x", padx=2, pady=2)
    _head(cogs_inner, "Módulos (cogs) carregados pelo bot")
    cogs_lbl = ctk.CTkLabel(cogs_inner, text="—", anchor="w", justify="left",
                            text_color="gray65", wraplength=700,
                            font=ctk.CTkFont(size=10))
    cogs_lbl.pack(fill="x", padx=10, pady=(0, 10))

    def _load_cogs() -> None:
        bot = _ensure_bot()
        cogs = bot.list_cogs()
        if cogs:
            cogs_lbl.configure(text=", ".join(cogs))
        else:
            cogs_lbl.configure(text="Não foi possível ler config.py — verifique a pasta do bot.")

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
        ok, msg = bot.validate()
        if ok:
            val_lbl.configure(text="✅ Ambiente OK — bot.py, .env e Python encontrados.", text_color=_GREEN)
        else:
            val_lbl.configure(text=f"⚠ {msg.replace(chr(10), ' — ')}", text_color="#e0af68")

    def _refresh_status() -> None:
        bot = _ensure_bot()
        _set_status(bot.is_running, bot.pid)
        _refresh_validation()

    def _poll_tick() -> None:
        _refresh_logs()
        _refresh_status()
        state["poll_job"] = app.after(500, _poll_tick)

    def _on_destroy(_event=None) -> None:
        job = state.get("poll_job")
        if job:
            try:
                app.after_cancel(job)
            except Exception:
                pass

    parent.bind("<Destroy>", _on_destroy, add="+")
    path_entry.bind("<FocusOut>", lambda _e: _persist_path())

    _refresh_validation()
    _load_maps()
    _load_cogs()
    _refresh_logs()
    _poll_tick()

    app._obobonic_panel_state = state
    app._obobonic_bot_holder = bot_holder
