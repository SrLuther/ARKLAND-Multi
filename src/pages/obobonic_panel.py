"""Painel TEK do bot Discord oBobonic EMBUTIDO (administração, moderação e salas de voz)."""
from __future__ import annotations

import logging
import os
import webbrowser
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Any, Dict, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..discord_bot.legacy_import import (
    apply_legacy_to_config,
    collect_legacy_values,
    import_badwords,
    should_offer_legacy_import,
)
from ..discord_bot.settings import BotSettings, default_data_dir
from ..discord_bot.storage import BADWORDS_FILENAME, ensure_data_dir
from ..obobonic_bot import (
    STATE_ERROR,
    STATE_ONLINE,
    TEXT_FIELDS,
    discord_developer_url,
    discord_invite_url,
    get_runner,
    live_config,
    restart_embedded_bot,
    save_bot_fields,
    save_panel_options,
    start_embedded_bot,
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

_log = logging.getLogger(__name__)

_SEC_BG = "#0d0d1e"
_HEAD_BG = "#141428"
_INNER = "#16162a"
_BDR = "#2a2a45"
_FIELD_BG = "#111128"
_AMBER = "#e0af68"
_OFFLINE = "#f7768e"

# (campo da config, rótulo, secreto?, dica)
_FIELD_ROWS = (
    ("token", "Token do bot", True, "Dev Portal → Bot → Reset Token"),
    ("client_id", "Client ID (opcional)", False, "vazio = derivado do token"),
    ("guild_id", "ID do servidor Discord", False, "Servidor onde o bot atua"),
    ("command_prefix", "Prefixo dos comandos", False, "padrão: !"),
    ("lobby_channel_id", "Lobby de voz", False, "entrar cria uma sala própria"),
    ("logs_channel_id", "Canal de logs", False, "moderação / admin"),
    ("quarantine_role_id", "Cargo de quarentena", False, "usado por !limpezageral"),
)


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


def _save_config(app: "ARKTEKApp") -> Optional[str]:
    """Salva o config; devolve a mensagem de erro (ou None)."""
    try:
        app.config_manager.save()
        return None
    except OSError as exc:
        return str(exc)


def import_legacy_folder(app: "ARKTEKApp", folder: Path, *, overwrite: bool = False) -> str:
    """Importa token/IDs/palavrões da pasta antiga (uma vez, a pedido). Devolve resumo SEM segredos."""
    cfg = live_config(app)
    data = collect_legacy_values(folder)
    if not data.has_anything:
        cfg.legacy_import_done = True
        _save_config(app)
        return "Nada para importar nessa pasta."
    changed = apply_legacy_to_config(cfg, data, overwrite=overwrite)
    badwords = import_badwords(data, default_data_dir())
    cfg.legacy_import_done = True
    cfg.legacy_project_path = ""
    err = _save_config(app)
    if err:
        raise OSError(err)
    parts = list(changed)
    if badwords:
        parts.append("palavroes.txt")
    return "Importado: " + (", ".join(parts) if parts else "nenhum campo novo (já configurado)")


def offer_legacy_import(app: "ARKTEKApp", after_import: Any = None) -> bool:
    """Pergunta UMA vez se deve importar a config do bot antigo. Retorna True se importou."""
    cfg = live_config(app)
    if not should_offer_legacy_import(cfg):
        return False
    folder = Path(cfg.legacy_project_path)
    try:
        answer = messagebox.askyesno(
            "oBobonic — importar dados do bot antigo",
            "O oBobonic agora roda DENTRO do app (sem pasta externa).\n\n"
            f"Encontrei token e IDs do bot antigo em:\n{folder}\n\n"
            "Importar essas configurações uma única vez? "
            "(o caminho antigo não será mais usado)",
        )
    except Exception:
        return False
    imported = False
    try:
        if answer:
            summary = import_legacy_folder(app, folder)
            _toast(app, summary, "info")
            imported = True
        else:
            cfg.legacy_import_done = True
            cfg.legacy_project_path = ""
            _save_config(app)
    except Exception as exc:
        _toast(app, f"Falha ao importar: {exc}", "error")
    if imported and after_import:
        after_import()
    return imported


def build_obobonic_panel(app: "ARKTEKApp", parent: tk.Widget) -> None:
    theme = get_theme("tek")
    accent = theme["accent"]
    runner = get_runner(app)

    parent.grid_rowconfigure(0, weight=0)
    parent.grid_rowconfigure(1, weight=1)
    parent.grid_columnconfigure(0, weight=1)

    state: Dict[str, Any] = {"follow_logs": True, "poll_job": None}

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
    detail_var = tk.StringVar(value="Embutido no app")
    ctk.CTkLabel(header, textvariable=status_var, font=ctk.CTkFont(size=12, weight="bold")).grid(
        row=0, column=2, sticky="w")
    ctk.CTkLabel(header, textvariable=detail_var, text_color="gray55",
                 font=ctk.CTkFont(size=10)).grid(row=1, column=2, sticky="w")

    # ── Corpo scrollável ──────────────────────────────────────────────────
    body = ctk.CTkScrollableFrame(parent, fg_color=_BG, corner_radius=0)
    body.grid(row=1, column=0, sticky="nsew")
    body.grid_columnconfigure(0, weight=1)

    # Controles
    ctrl_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    ctrl_card.pack(fill="x", padx=16, pady=(16, 8))

    val_lbl = ctk.CTkLabel(ctrl_card, text="", text_color="gray55", anchor="w",
                           font=ctk.CTkFont(size=10), wraplength=720, justify="left")
    val_lbl.pack(fill="x", padx=12, pady=(10, 0))

    btn_row = ctk.CTkFrame(ctrl_card, fg_color="transparent")
    btn_row.pack(fill="x", padx=12, pady=12)

    cfg0 = live_config(app)
    auto_start_var = tk.BooleanVar(value=bool(cfg0.auto_start))
    auto_restart_var = tk.BooleanVar(value=bool(cfg0.auto_restart_on_crash))

    def _append_panel_log(msg: str) -> None:
        log_box.configure(state=tk.NORMAL)
        log_box.insert(tk.END, msg + "\n")
        if state["follow_logs"]:
            log_box.see(tk.END)
        log_box.configure(state=tk.DISABLED)

    def _on_action(ok: bool, msg: str) -> None:
        _append_panel_log(("✅ " if ok else "⚠ ") + msg)
        _refresh_status()
        _toast(app, msg, "info" if ok else "warning")

    def _start() -> None:
        _on_action(*start_embedded_bot(app))

    def _stop() -> None:
        import threading

        def _worker() -> None:
            ok, msg = runner.stop()
            app.after(0, lambda: _on_action(ok, msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _restart() -> None:
        import threading

        def _worker() -> None:
            ok, msg = restart_embedded_bot(app)
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
        """Persiste as caixas (marcadas OU desmarcadas) na config ATUAL do app."""
        wanted = (auto_start_var.get(), auto_restart_var.get())
        try:
            save_panel_options(
                app.config_manager,
                auto_start=wanted[0],
                auto_restart_on_crash=wanted[1],
            )
        except OSError as exc:
            # Não deixa a UI mentir: volta ao que está de fato gravado e avisa.
            cur = live_config(app)
            auto_start_var.set(bool(cur.auto_start))
            auto_restart_var.set(bool(cur.auto_restart_on_crash))
            _toast(app, f"Não foi possível salvar as opções: {exc}", "error")
            return
        runner.set_auto_restart(wanted[1])

    ctk.CTkCheckBox(opt_row, text="Iniciar com o app",
                    variable=auto_start_var, command=_save_opt,
                    fg_color=theme["accent_dark"], hover_color=theme["accent_hover"]).pack(
        side=tk.LEFT, padx=(0, 12))
    ctk.CTkCheckBox(opt_row, text="Reiniciar ao crash",
                    variable=auto_restart_var, command=_save_opt,
                    fg_color=theme["accent_dark"], hover_color=theme["accent_hover"]).pack(
        side=tk.LEFT, padx=(0, 12))

    # ── Status Discord (ao vivo) ──────────────────────────────────────────
    discord_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    discord_card.pack(fill="x", padx=16, pady=8)
    discord_inner = tk.Frame(discord_card, bg=_INNER)
    discord_inner.pack(fill="x", padx=2, pady=2)
    _head(discord_inner, "Status Discord")

    discord_status_lbl = ctk.CTkLabel(
        discord_inner, text="—", anchor="w", justify="left",
        text_color="gray65", wraplength=700, font=ctk.CTkFont(size=11),
    )
    discord_status_lbl.pack(fill="x", padx=10, pady=(0, 4))
    ctk.CTkLabel(
        discord_inner,
        text="Capacidades: administração (!reload/!load/!unload/!restart/!shutdown), "
             "moderação (!faxina/!limpar/!limpezageral + filtros) e salas de voz temporárias.",
        text_color="gray50", font=ctk.CTkFont(size=9), anchor="w", wraplength=700, justify="left",
    ).pack(fill="x", padx=10, pady=(0, 8))

    link_row = ctk.CTkFrame(discord_inner, fg_color="transparent")
    link_row.pack(fill="x", padx=10, pady=(0, 10))

    def _current_token_client() -> tuple:
        cfg = live_config(app)
        tok = (field_vars["token"].get() if "token" in field_vars else cfg.token).strip()
        cid = (field_vars["client_id"].get() if "client_id" in field_vars else cfg.client_id).strip()
        return tok, cid

    def _open_discord_dev() -> None:
        try:
            tok, cid = _current_token_client()
            webbrowser.open(discord_developer_url(tok, cid))
        except Exception as exc:
            _toast(app, str(exc), "error")

    def _invite_url() -> Optional[str]:
        tok, cid = _current_token_client()
        return discord_invite_url(tok, cid)

    def _open_discord_invite() -> None:
        url = _invite_url()
        if url:
            webbrowser.open(url)
        else:
            _toast(app, "Informe um token ou Client ID válido para gerar o link de convite.", "warning")

    def _copy_invite() -> None:
        url = _invite_url()
        if not url:
            _toast(app, "Informe um token ou Client ID válido para gerar o link de convite.", "warning")
            return
        try:
            app.clipboard_clear()
            app.clipboard_append(url)
            _toast(app, "Link de convite copiado.", "info")
        except Exception as exc:
            _toast(app, str(exc), "error")

    def _open_data_dir() -> None:
        p = ensure_data_dir(default_data_dir())
        try:
            os.startfile(str(p))  # type: ignore[attr-defined]
        except Exception as exc:
            _toast(app, f"Não foi possível abrir a pasta: {exc}", "warning")

    def _edit_badwords() -> None:
        ensure_data_dir(default_data_dir())
        path = default_data_dir() / BADWORDS_FILENAME
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
            _toast(app, "Salve o arquivo e reinicie o bot para aplicar a nova lista.", "info")
        except Exception as exc:
            _toast(app, f"Não foi possível abrir o arquivo: {exc}", "warning")

    ctk.CTkButton(link_row, text="🔗 Dev Portal", width=110, height=28,
                  fg_color=theme["accent_muted_bg"], hover_color=theme["accent_hover"],
                  command=_open_discord_dev).pack(side=tk.LEFT, padx=(0, 6))
    ctk.CTkButton(link_row, text="➕ Convidar bot", width=110, height=28,
                  fg_color=theme["accent_muted_bg"], hover_color=theme["accent_hover"],
                  command=_open_discord_invite).pack(side=tk.LEFT, padx=(0, 6))
    ctk.CTkButton(link_row, text="📋 Copiar convite", width=120, height=28,
                  fg_color=_SEC_BG, hover_color=theme["accent_hover"],
                  command=_copy_invite).pack(side=tk.LEFT, padx=(0, 6))
    ctk.CTkButton(link_row, text="🗄 Pasta de dados", width=120, height=28,
                  fg_color=_SEC_BG, hover_color=theme["accent_hover"],
                  command=_open_data_dir).pack(side=tk.LEFT)

    # ── Configuração do bot ───────────────────────────────────────────────
    cfg_card = ctk.CTkFrame(body, fg_color=_CARD_BG, corner_radius=10)
    cfg_card.pack(fill="x", padx=16, pady=8)
    cfg_inner = tk.Frame(cfg_card, bg=_INNER)
    cfg_inner.pack(fill="x", padx=2, pady=2)
    _head(cfg_inner, "Configuração do bot")

    fields_fr = ctk.CTkFrame(cfg_inner, fg_color="transparent")
    fields_fr.pack(fill="x", padx=10, pady=(0, 8))
    fields_fr.grid_columnconfigure(1, weight=1)
    field_vars: Dict[str, tk.StringVar] = {}
    token_entry: Dict[str, Any] = {}

    for row_i, (key, label, secret, hint) in enumerate(_FIELD_ROWS):
        ctk.CTkLabel(fields_fr, text=label, text_color="gray60",
                     font=ctk.CTkFont(size=10)).grid(row=row_i, column=0, sticky="w", padx=(0, 8), pady=3)
        var = tk.StringVar(value=str(getattr(cfg0, key, "") or ""))
        field_vars[key] = var
        ent = ctk.CTkEntry(fields_fr, textvariable=var, height=28, show="•" if secret else "")
        ent.grid(row=row_i, column=1, sticky="ew", pady=3)
        if secret:
            token_entry["w"] = ent
        ctk.CTkLabel(fields_fr, text=hint, text_color="gray45",
                     font=ctk.CTkFont(size=9)).grid(row=row_i, column=2, sticky="w", padx=(8, 0))

    show_token_var = tk.BooleanVar(value=False)

    def _toggle_token() -> None:
        token_entry["w"].configure(show="" if show_token_var.get() else "•")

    ctk.CTkCheckBox(cfg_inner, text="Mostrar token", variable=show_token_var,
                    command=_toggle_token, width=120,
                    fg_color=theme["accent_dark"]).pack(anchor="w", padx=10, pady=(0, 6))

    cogs_row = ctk.CTkFrame(cfg_inner, fg_color="transparent")
    cogs_row.pack(fill="x", padx=10, pady=(0, 6))
    voice_var = tk.BooleanVar(value=bool(cfg0.enable_voice))
    moderation_var = tk.BooleanVar(value=bool(cfg0.enable_moderation))
    ctk.CTkCheckBox(cogs_row, text="Salas de voz temporárias", variable=voice_var,
                    fg_color=theme["accent_dark"], hover_color=theme["accent_hover"]).pack(
        side=tk.LEFT, padx=(0, 12))
    ctk.CTkCheckBox(cogs_row, text="Moderação (filtros + comandos)", variable=moderation_var,
                    fg_color=theme["accent_dark"], hover_color=theme["accent_hover"]).pack(
        side=tk.LEFT, padx=(0, 12))
    ctk.CTkLabel(cogs_row, text="Administração está sempre ativa.", text_color="gray50",
                 font=ctk.CTkFont(size=9)).pack(side=tk.LEFT)

    def _save_fields() -> None:
        values = {k: v.get() for k, v in field_vars.items()}
        try:
            errors = save_bot_fields(
                app.config_manager, values,
                enable_voice=voice_var.get(), enable_moderation=moderation_var.get(),
            )
        except OSError as exc:
            _toast(app, f"Não foi possível salvar: {exc}", "error")
            return
        if errors:
            _toast(app, "\n".join(errors), "warning")
            return
        _append_panel_log("✅ Configuração salva. Reinicie o bot para aplicar.")
        _toast(app, "Configuração salva. Reinicie o bot para aplicar.", "info")
        _refresh_validation()

    def _reload_fields() -> None:
        cfg = live_config(app)
        for key in TEXT_FIELDS:
            if key in field_vars:
                field_vars[key].set(str(getattr(cfg, key, "") or ""))
        voice_var.set(bool(cfg.enable_voice))
        moderation_var.set(bool(cfg.enable_moderation))
        _refresh_validation()

    def _import_legacy() -> None:
        chosen = filedialog.askdirectory(
            title="Pasta do oBobonicClean antigo (leitura única)",
            initialdir=str(Path.home()),
        )
        if not chosen:
            return
        folder = Path(chosen)
        data = collect_legacy_values(folder)
        if not data.has_anything:
            _toast(app, "Nenhum token, ID ou palavroes.txt encontrado nessa pasta.", "warning")
            return
        found = ", ".join(sorted(data.values)) + (", palavroes.txt" if data.badwords_path else "")
        if not messagebox.askyesno(
            "Importar dados do bot antigo",
            f"Encontrado: {found}\n\nImportar para o app? Campos já preenchidos serão mantidos "
            "(use «Sim» apenas se quiser aproveitar o que falta).",
        ):
            return
        try:
            summary = import_legacy_folder(app, folder)
        except Exception as exc:
            _toast(app, f"Falha ao importar: {exc}", "error")
            return
        _reload_fields()
        _append_panel_log("📥 " + summary)
        _toast(app, summary, "info")

    env_btn_row = ctk.CTkFrame(cfg_inner, fg_color="transparent")
    env_btn_row.pack(fill="x", padx=10, pady=(0, 10))
    ctk.CTkButton(env_btn_row, text="💾 Salvar configuração", width=160, height=30,
                  fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                  command=_save_fields).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkButton(env_btn_row, text="📥 Importar dados do bot antigo", width=210, height=30,
                  fg_color=_SEC_BG, hover_color=theme["accent_hover"],
                  command=_import_legacy).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkButton(env_btn_row, text="✏ Editar palavrões", width=150, height=30,
                  fg_color=_SEC_BG, hover_color=theme["accent_hover"],
                  command=_edit_badwords).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkLabel(
        cfg_inner,
        text="Intents: ative «Server Members Intent» e «Message Content Intent» no Dev Portal → Bot. "
             "Alterações exigem reiniciar o bot.",
        text_color="gray50", font=ctk.CTkFont(size=9), anchor="w", wraplength=700, justify="left",
    ).pack(fill="x", padx=10, pady=(0, 10))

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

    log_host = tk.Frame(log_card, bg=_FIELD_BG, highlightthickness=1,
                        highlightbackground=_BDR)
    log_host.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
    log_host.grid_rowconfigure(0, weight=1)
    log_host.grid_columnconfigure(0, weight=1)

    log_box = tk.Text(log_host, bg="#0a0a14", fg="#9ece6a", height=14,
                      insertbackground="#c8c8e8", font=("Consolas", 10),
                      relief=tk.FLAT, wrap=tk.WORD, state=tk.DISABLED)
    log_sb = tk.Scrollbar(log_host, command=log_box.yview,
                          bg=_BDR, troughcolor=_BG, width=10)
    log_box.configure(yscrollcommand=log_sb.set)
    log_box.grid(row=0, column=0, sticky="nsew")
    log_sb.grid(row=0, column=1, sticky="ns")

    def _refresh_logs() -> None:
        lines = runner.drain_logs()
        if not lines:
            return
        log_box.configure(state=tk.NORMAL)
        for line in lines:
            log_box.insert(tk.END, line + "\n")
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

    # ── Status / validação ────────────────────────────────────────────────
    def _refresh_validation() -> None:
        settings = BotSettings.from_config(live_config(app))
        problems = settings.problems()
        parts = []
        if problems:
            parts.append("⚠ " + problems[0])
            val_lbl.configure(text="  ·  ".join(parts), text_color=_AMBER)
            return
        parts.append("✅ Bot embutido no app · token válido")
        for w in settings.warnings():
            parts.append("⚠ " + w)
        val_lbl.configure(text="  ·  ".join(parts), text_color=_GREEN if len(parts) == 1 else _AMBER)

    def _refresh_status() -> None:
        st = runner.snapshot()
        if st.state == STATE_ONLINE:
            status_var.set("Online")
            status_dot.configure(text_color=_GREEN)
            discord_status_lbl.configure(text=f"🟢 {st.summary}", text_color=_GREEN)
        elif st.running:
            status_var.set("Iniciando…" if st.state != "stopping" else "Encerrando…")
            status_dot.configure(text_color=_AMBER)
            discord_status_lbl.configure(text=f"🟡 {st.summary}", text_color=_AMBER)
        else:
            status_var.set("Erro" if st.state == STATE_ERROR else "Parado")
            status_dot.configure(text_color=_OFFLINE)
            discord_status_lbl.configure(
                text=f"⚫ {st.summary}",
                text_color=_OFFLINE if st.state == STATE_ERROR else "gray55",
            )
        detail_var.set(
            f"Embutido no app · {st.latency_ms:.0f} ms" if st.latency_ms is not None
            else "Embutido no app"
        )

    def _poll_tick() -> None:
        _refresh_logs()
        _refresh_status()
        state["poll_job"] = app.after(500, _poll_tick)

    def _on_destroy(event: Any = None) -> None:
        # Só reage à destruição do próprio painel (o bot continua rodando no app).
        if event is not None and getattr(event, "widget", None) is not parent:
            return
        job = state.get("poll_job")
        if job:
            try:
                app.after_cancel(job)
            except Exception:
                pass

    parent.bind("<Destroy>", _on_destroy, add="+")

    # Repovoa o log com o histórico da sessão (o painel é reconstruído ao navegar).
    hist = runner.history()
    runner.drain_logs()
    if hist:
        log_box.configure(state=tk.NORMAL)
        log_box.insert("1.0", "\n".join(hist[-300:]) + "\n")
        log_box.configure(state=tk.DISABLED)
        log_box.see(tk.END)
    boot_result = getattr(app, "_obobonic_autostart_msg", None)
    if isinstance(boot_result, tuple) and len(boot_result) == 2:
        ok, msg = boot_result
        _append_panel_log(("✅ " if ok else "⚠ ") + msg)

    _refresh_validation()
    _refresh_status()
    _poll_tick()

    # Config antiga com pasta externa: oferece importar uma única vez.
    app.after(400, lambda: offer_legacy_import(app, after_import=_reload_fields))


def auto_start_obobonic(app: "ARKTEKApp") -> None:
    """Inicia o bot embutido no boot do TEK se ``obobonic.auto_start`` estiver ativo."""
    if getattr(app, "_obobonic_autostart_started", False):
        return
    app._obobonic_autostart_started = True

    cfg = live_config(app)

    def _autostart() -> None:
        live = live_config(app)
        if not live.auto_start:
            return
        if not BotSettings.from_config(live).token:
            msg = "Token não configurado — configure no painel oBobonic para iniciar o bot."
            app._obobonic_autostart_msg = (False, msg)
            _log.info("auto_start_obobonic: %s", msg)
            return
        ok, msg = start_embedded_bot(app)
        app._obobonic_autostart_msg = (ok, msg)
        _log.log(logging.INFO if ok else logging.WARNING, "auto_start_obobonic: %s", msg)
        try:
            app._global_log(f"[oBobonic] {msg}", "info" if ok else "warning")
        except Exception:
            pass

    # Config antiga (pasta externa): oferece importar uma vez e, se importou, inicia.
    try:
        if should_offer_legacy_import(cfg):
            offer_legacy_import(app, after_import=_autostart)
            return
    except Exception:
        _log.warning("auto_start_obobonic: oferta de importação falhou", exc_info=True)

    _autostart()
