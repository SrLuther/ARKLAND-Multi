from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _CARD_BG

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_global_config(app: "ARKServerManagerApp", parent) -> None:
    parent.grid_columnconfigure(0, weight=1)
    cfg = app.config_manager.config

    ctk.CTkLabel(parent, text="⚙️  Configurações Globais",
                 font=ctk.CTkFont(size=24, weight="bold")).grid(
        row=0, column=0, padx=24, pady=(24, 2), sticky="w")
    ctk.CTkLabel(parent, text="Configurações globais do ARKLAND - Server Manager.",
                 text_color="gray60").grid(row=1, column=0, padx=24, pady=(0, 18), sticky="w")

    app._section_lbl(parent, 2, "🎮  SteamCMD")
    sc_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    sc_card.grid(row=3, column=0, padx=20, pady=(0, 14), sticky="ew")
    sc_card.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(sc_card, text="Caminho do SteamCMD:", width=200, anchor="w",
                 text_color="gray60").grid(row=0, column=0, padx=16, pady=14)
    app._steamcmd_var = tk.StringVar(value=cfg.steamcmd_path)
    fr = ctk.CTkFrame(sc_card, fg_color="transparent")
    fr.grid(row=0, column=1, padx=(0, 16), pady=14, sticky="ew")
    fr.grid_columnconfigure(0, weight=1)
    ctk.CTkEntry(fr, textvariable=app._steamcmd_var, height=34,
                 placeholder_text=r"Ex: C:\SteamCMD\steamcmd.exe").grid(
        row=0, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkButton(fr, text="📁", width=34, height=34,
                  command=lambda: app._browse_file(app._steamcmd_var, "steamcmd.exe")).grid(
        row=0, column=1)
    app._steamcmd_dl_btn = ctk.CTkButton(
        sc_card, text="⬇  Baixar SteamCMD", height=34,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=app._download_steamcmd,
    )
    app._steamcmd_dl_btn.grid(row=0, column=2, padx=(0, 16), pady=14)
    app._steamcmd_status_lbl = ctk.CTkLabel(
        sc_card,
        text="O SteamCMD é necessário para instalar/atualizar servidores e baixar mods via Steam Workshop.",
        text_color="gray50", font=ctk.CTkFont(size=11),
    )
    app._steamcmd_status_lbl.grid(row=1, column=0, columnspan=3, padx=16, pady=(0, 10), sticky="w")

    from .environment_section import build_environment_section
    _next_row = build_environment_section(app, parent, 4)

    app._section_lbl(parent, _next_row, "📂  Diretório Padrão de Instalação")
    dir_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    dir_card.grid(row=_next_row + 1, column=0, padx=20, pady=(0, 14), sticky="ew")
    dir_card.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(dir_card, text="Diretório Padrão:", width=200, anchor="w",
                 text_color="gray60").grid(row=0, column=0, padx=16, pady=(14, 2))
    app._default_dir_var = tk.StringVar(value=cfg.default_install_dir)
    fr2 = ctk.CTkFrame(dir_card, fg_color="transparent")
    fr2.grid(row=0, column=1, padx=(0, 16), pady=(14, 2), sticky="ew")
    fr2.grid_columnconfigure(0, weight=1)
    ctk.CTkEntry(fr2, textvariable=app._default_dir_var, height=34).grid(
        row=0, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkButton(fr2, text="📁", width=34, height=34,
                  command=lambda: app._browse_dir(app._default_dir_var)).grid(row=0, column=1)
    ctk.CTkLabel(dir_card,
                 text="Pasta sugerida ao criar um novo servidor. Pode ser sobrescrita individualmente.",
                 text_color="gray45", font=ctk.CTkFont(size=10)).grid(
        row=1, column=0, columnspan=2, padx=16, pady=(0, 12), sticky="w")

    app._section_lbl(parent, _next_row + 2, "🔧  Opções")
    opt_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    opt_card.grid(row=_next_row + 3, column=0, padx=20, pady=(0, 14), sticky="ew")

    app._cfg_startup_var   = tk.BooleanVar(value=cfg.startup_with_windows)
    app._cfg_minimize_tray_var = tk.BooleanVar(value=cfg.minimize_to_tray)
    app._cfg_log_debug_var = tk.BooleanVar(value=cfg.log_debug)

    ctk.CTkCheckBox(opt_card, text="Iniciar o ARKLAND - Server Manager com o Windows",
                    variable=app._cfg_startup_var,
                    checkmark_color="white", fg_color=_GREEN_DARK,
                    hover_color=_GREEN_HOVER).grid(
        row=0, column=0, padx=16, pady=(16, 2), sticky="w")
    ctk.CTkLabel(opt_card,
                 text="Inicia o app automaticamente quando o Windows ligar. "
                      "Marque «Iniciar ao abrir o app» em cada servidor (Gerenciamento Automático) "
                      "para subir os mapas junto com o ARKLAND.",
                 text_color="gray45", font=ctk.CTkFont(size=10)).grid(
        row=1, column=0, padx=(42, 16), pady=(0, 8), sticky="w")

    ctk.CTkCheckBox(opt_card, text="Minimizar para a bandeja do sistema ao fechar",
                    variable=app._cfg_minimize_tray_var,
                    checkmark_color="white", fg_color=_GREEN_DARK,
                    hover_color=_GREEN_HOVER).grid(
        row=2, column=0, padx=16, pady=(0, 2), sticky="w")
    ctk.CTkLabel(opt_card,
                 text="Mantém o app ativo na bandeja (systray) em vez de fechar. Clique no ícone para restaurar.",
                 text_color="gray45", font=ctk.CTkFont(size=10)).grid(
        row=3, column=0, padx=(42, 16), pady=(0, 8), sticky="w")

    ctk.CTkCheckBox(opt_card, text="Modo de log verbose (debug)",
                    variable=app._cfg_log_debug_var,
                    checkmark_color="white", fg_color=_GREEN_DARK,
                    hover_color=_GREEN_HOVER).grid(
        row=4, column=0, padx=16, pady=(0, 2), sticky="w")
    ctk.CTkLabel(opt_card,
                 text="Registra mensagens detalhadas no log. Útil para diagnosticar problemas.",
                 text_color="gray45", font=ctk.CTkFont(size=10)).grid(
        row=5, column=0, padx=(42, 16), pady=(0, 8), sticky="w")

    # ForceDay desativado: SetDay via RCON crasha ASE 361.7 (produção 1.10.47).
    app._cfg_force_day_enabled_var = tk.BooleanVar(value=False)
    try:
        _force_day_default = int(getattr(cfg, "force_day_on_start", 20) or 20)
    except (TypeError, ValueError):
        _force_day_default = 20
    app._cfg_force_day_var = tk.StringVar(value=str(max(0, _force_day_default)))

    ctk.CTkCheckBox(
        opt_card,
        text="Forçar dia do mapa no start/restart — DESATIVADO (crash ASE)",
        variable=app._cfg_force_day_enabled_var,
        checkmark_color="white", fg_color=_GREEN_DARK,
        hover_color=_GREEN_HOVER,
        state="disabled",
    ).grid(row=6, column=0, padx=16, pady=(0, 2), sticky="w")

    _day_row = ctk.CTkFrame(opt_card, fg_color="transparent")
    _day_row.grid(row=7, column=0, padx=(42, 16), pady=(0, 2), sticky="w")
    ctk.CTkLabel(
        _day_row, text="Dia desejado (DayNumber):",
        text_color="gray60", width=180, anchor="w",
    ).pack(side="left")
    ctk.CTkEntry(
        _day_row, textvariable=app._cfg_force_day_var,
        width=80, height=28, placeholder_text="20",
        state="disabled",
    ).pack(side="left", padx=(8, 0))

    def _apply_force_day_now() -> None:
        from tkinter import messagebox
        messagebox.showerror(
            "ForceDay — desativado",
            "SetDay via RCON crasha servidores ASE 361.7 "
            "(UShooterCheatManager::SetDay / RCON tick).\n\n"
            "Não é seguro aplicar o dia por RCON (nem «cheat SetDay»).\n"
            "Reinicie os mapas SEM ForceDay. Alinhar DayNumber "
            "exige outro método (ainda não disponível).",
            parent=app,
        )

    ctk.CTkButton(
        _day_row,
        text="Aplicar agora (indisponível)",
        width=220,
        height=28,
        fg_color="gray40",
        hover_color="gray35",
        command=_apply_force_day_now,
    ).pack(side="left", padx=(12, 0))

    ctk.CTkLabel(
        opt_card,
        text=(
            "CRÍTICO: na 1.10.47, SetDay via RCON derrubou todos os mapas online. "
            "O envio está bloqueado no código. Não use ForceDay até haver "
            "alternativa segura (plugin / edição offline do save)."
        ),
        text_color="#b33a3a", font=ctk.CTkFont(size=10),
        wraplength=620, justify="left",
    ).grid(row=8, column=0, padx=(42, 16), pady=(0, 16), sticky="w")

    # ── Seção Steam Web API ─────────────────────────────────────────────────
    app._section_lbl(parent, _next_row + 4, "🔑  Steam Web API")
    api_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    api_card.grid(row=_next_row + 5, column=0, padx=20, pady=(0, 14), sticky="ew")
    api_card.grid_columnconfigure(1, weight=1)

    app._steam_api_key_var = tk.StringVar(value=cfg.steam_api_key)
    ctk.CTkLabel(api_card, text="Chave da API Steam:", width=200, anchor="w",
                 text_color="gray60").grid(row=0, column=0, padx=16, pady=(14, 2), sticky="w")
    ctk.CTkEntry(api_card, textvariable=app._steam_api_key_var, height=34,
                 placeholder_text="Opcional — ex: XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                 show="*").grid(row=0, column=1, padx=(0, 16), pady=(14, 2), sticky="ew")
    ctk.CTkLabel(
        api_card,
        text="Usada para verificar atualizações de mods sem depender da cota pública compartilhada. "
             "Obtenha a sua em: steamcommunity.com/dev/apikey",
        text_color="gray45", font=ctk.CTkFont(size=10), wraplength=560, justify="left",
    ).grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 12), sticky="w")

    # ── Seção Discord ───────────────────────────────────────────
    app._section_lbl(parent, _next_row + 6, "🔔  Notificações Discord")
    disc_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    disc_card.grid(row=_next_row + 7, column=0, padx=20, pady=(0, 14), sticky="ew")
    disc_card.grid_columnconfigure(1, weight=1)

    dc = cfg.discord_notify
    app._discord_enabled_var         = tk.BooleanVar(value=dc.enabled)
    app._discord_url_var             = tk.StringVar(value=dc.webhook_url)
    app._discord_sender_var          = tk.StringVar(value=dc.sender_name)
    app._discord_notify_start        = tk.BooleanVar(value=dc.notify_start)
    app._discord_notify_stop         = tk.BooleanVar(value=dc.notify_stop)
    app._discord_notify_crash        = tk.BooleanVar(value=dc.notify_crash)
    app._discord_notify_update       = tk.BooleanVar(value=dc.notify_update)
    app._discord_notify_backup       = tk.BooleanVar(value=dc.notify_backup)
    app._discord_mod_changelog_hook  = tk.StringVar(value=dc.mod_changelog_webhook)

    ctk.CTkCheckBox(
        disc_card, text="Ativar notificações Discord",
        variable=app._discord_enabled_var,
        checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
    ).grid(row=0, column=0, columnspan=2, padx=16, pady=(16, 4), sticky="w")
    ctk.CTkLabel(disc_card,
                 text="Envia mensagens para um canal Discord quando eventos de servidor ocorrem.",
                 text_color="gray45", font=ctk.CTkFont(size=10)).grid(
        row=1, column=0, columnspan=2, padx=(42, 16), pady=(0, 10), sticky="w")

    ctk.CTkLabel(disc_card, text="URL do Webhook:", width=160, anchor="w",
                 text_color="gray60").grid(row=2, column=0, padx=16, pady=(4, 0), sticky="w")
    ctk.CTkEntry(disc_card, textvariable=app._discord_url_var, height=32,
                 placeholder_text="https://discord.com/api/webhooks/...").grid(
        row=2, column=1, padx=(0, 16), pady=(4, 0), sticky="ew")
    ctk.CTkLabel(disc_card,
                 text="Obtenha em: Canal Discord → Editar Canal → Integrações → Webhooks → Novo Webhook → Copiar URL",
                 text_color="gray45", font=ctk.CTkFont(size=10)).grid(
        row=3, column=0, columnspan=2, padx=(16, 16), pady=(0, 6), sticky="w")

    ctk.CTkLabel(disc_card, text="Nome do remetente:", width=160, anchor="w",
                 text_color="gray60").grid(row=4, column=0, padx=16, pady=4, sticky="w")
    ctk.CTkEntry(disc_card, textvariable=app._discord_sender_var, height=32,
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
    evt_fr.grid(row=7, column=0, columnspan=2, padx=12, pady=(0, 6), sticky="w")
    for ci, (txt, var) in enumerate([
        ("🟡 Iniciando / Online",  app._discord_notify_start),
        ("🔴 Parado / Encerrando", app._discord_notify_stop),
        ("💥 Crash",               app._discord_notify_crash),
        ("🔄 Atualização de mods", app._discord_notify_update),
        ("💾 Backup concluído",   app._discord_notify_backup),
    ]):
        ctk.CTkCheckBox(
            evt_fr, text=txt, variable=var, width=200,
            checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
            font=ctk.CTkFont(size=11),
        ).grid(row=ci // 3, column=ci % 3, padx=8, pady=3, sticky="w")

    # ── Webhook separado para notas de atualização de mods ────────────────
    ctk.CTkLabel(disc_card, text="Webhook de mods (opcional):", width=160, anchor="w",
                 text_color="gray60").grid(row=8, column=0, padx=16, pady=(10, 0), sticky="w")
    ctk.CTkEntry(disc_card, textvariable=app._discord_mod_changelog_hook, height=32,
                 placeholder_text="https://discord.com/api/webhooks/... (vazio = usar webhook principal)").grid(
        row=8, column=1, padx=(0, 16), pady=(10, 0), sticky="ew")
    ctk.CTkLabel(disc_card,
                 text="Quando um mod for atualizado, as notas de atualização serão enviadas para este canal.\n"
                      "Deixe em branco para usar o mesmo webhook principal configurado acima.",
                 text_color="gray45", font=ctk.CTkFont(size=10), justify="left").grid(
        row=9, column=0, columnspan=2, padx=(16, 16), pady=(2, 14), sticky="w")

    # ── Seção Backup ────────────────────────────────────────────────────────
    app._section_lbl(parent, _next_row + 8, "💾  Backup Automático")
    bk_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    bk_card.grid(row=_next_row + 9, column=0, padx=20, pady=(0, 14), sticky="ew")
    bk_card.grid_columnconfigure(1, weight=1)

    bk = cfg.backup
    app._bk_dir_var             = tk.StringVar(value=bk.backup_dir)
    app._bk_include_saves_var   = tk.BooleanVar(value=bk.include_savegames)
    app._bk_include_config_var  = tk.BooleanVar(value=getattr(bk, "include_config", True))
    app._bk_exclude_redundant_var = tk.BooleanVar(
        value=getattr(bk, "backup_exclude_redundant", True)
    )
    app._bk_limit_count_var     = tk.BooleanVar(value=getattr(bk, "limit_backup_count", bk.exclude_old_backups))
    app._bk_max_count_var       = tk.StringVar(value=str(getattr(bk, "max_backup_count", 10)))
    app._bk_rcon_mode_var       = tk.StringVar(value=bk.rcon_broadcast_mode)
    app._bk_save_msg_var        = tk.StringVar(value=bk.save_message)
    app._bk_auto_var            = tk.BooleanVar(value=bk.auto_backup)
    app._bk_interval_var        = tk.StringVar(value=bk.backup_interval)

    ctk.CTkLabel(bk_card, text="Diretório de backup:", width=200, anchor="w",
                 text_color="gray60").grid(row=0, column=0, padx=16, pady=(14, 2), sticky="w")
    fr_bk = ctk.CTkFrame(bk_card, fg_color="transparent")
    fr_bk.grid(row=0, column=1, padx=(0, 16), pady=(14, 2), sticky="ew")
    fr_bk.grid_columnconfigure(0, weight=1)
    ctk.CTkEntry(
        fr_bk,
        textvariable=app._bk_dir_var,
        height=32,
        placeholder_text=r"Padrão: D:\Backups\servers",
    ).grid(
        row=0, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkButton(fr_bk, text="📁", width=32, height=32,
                  command=lambda: app._browse_dir(app._bk_dir_var)).grid(row=0, column=1)
    ctk.CTkButton(fr_bk, text="Limpar", width=60, height=32,
                  fg_color="#5c1a1a", hover_color="#7c2020",
                  command=lambda: app._bk_dir_var.set("")).grid(row=0, column=2, padx=(4, 0))

    ctk.CTkCheckBox(bk_card, text="Incluir saves do mundo (.ark, perfis, tribos) — recomendado",
                    variable=app._bk_include_saves_var,
                    checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    ).grid(row=1, column=0, columnspan=2, padx=16, pady=(10, 2), sticky="w")
    ctk.CTkCheckBox(bk_card, text="Incluir arquivos .ini (Game.ini / GameUserSettings.ini) — opcional",
                    variable=app._bk_include_config_var,
                    checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    ).grid(row=2, column=0, columnspan=2, padx=16, pady=(2, 2), sticky="w")
    ctk.CTkCheckBox(
        bk_card,
        text="Excluir cópias redundantes do ARK (.bak / backups datados)",
        variable=app._bk_exclude_redundant_var,
        checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
    ).grid(row=3, column=0, columnspan=2, padx=16, pady=(2, 2), sticky="w")
    ctk.CTkLabel(bk_card,
                 text="Os saves ficam em ShooterGame/Saved/{AltSaveDirectoryName}/ (ex.: savegame). "
                      "As configs são gerenciadas pelo ARKLAND e podem ser recriadas — o progresso do mundo não. "
                      "Cópias redundantes: *_AntiCorruptionBackup.bak, *_NewLaunchBackup.bak e "
                      "Map_DD.MM.YYYY_HH.MM.SS.ark (backups internos do ARK). O .ark ativo e perfis/tribos "
                      "sempre entram. Desmarque só se precisar de um snapshot completo da pasta.",
                 text_color="gray45", font=ctk.CTkFont(size=10), justify="left",
                 ).grid(row=4, column=0, columnspan=2, padx=16, pady=(2, 6), sticky="w")

    fr_keep = ctk.CTkFrame(bk_card, fg_color="transparent")
    fr_keep.grid(row=5, column=0, columnspan=2, padx=16, pady=(2, 8), sticky="w")
    ctk.CTkCheckBox(fr_keep, text="Manter apenas os",
                    variable=app._bk_limit_count_var,
                    checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    ).pack(side="left")
    ctk.CTkEntry(fr_keep, textvariable=app._bk_max_count_var, width=50, height=28).pack(side="left", padx=6)
    ctk.CTkLabel(fr_keep, text="backups mais recentes por servidor", text_color="gray60").pack(side="left")

    fr_rcon = ctk.CTkFrame(bk_card, fg_color="transparent")
    fr_rcon.grid(row=6, column=0, columnspan=2, padx=16, pady=(4, 2), sticky="w")
    ctk.CTkLabel(fr_rcon, text="Modo RCON Broadcast:", text_color="gray60", width=180, anchor="w").pack(side="left")
    ctk.CTkComboBox(fr_rcon, variable=app._bk_rcon_mode_var, width=160, height=28,
                    values=["Broadcast", "ServerChat", "SendRcon"]).pack(side="left", padx=6)

    ctk.CTkLabel(bk_card, text="Mensagem do Save:", width=200, anchor="w",
                 text_color="gray60").grid(row=7, column=0, padx=16, pady=(8, 2), sticky="w")
    ctk.CTkEntry(bk_card, textvariable=app._bk_save_msg_var, height=30).grid(
        row=7, column=1, padx=(0, 16), pady=(8, 2), sticky="ew")

    ctk.CTkCheckBox(bk_card, text="Ativar backup automático de todos os servidores",
                    variable=app._bk_auto_var,
                    checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    ).grid(row=8, column=0, columnspan=2, padx=16, pady=(10, 2), sticky="w")
    fr_bk_int = ctk.CTkFrame(bk_card, fg_color="transparent")
    fr_bk_int.grid(row=9, column=0, columnspan=2, padx=16, pady=(2, 8), sticky="w")
    ctk.CTkLabel(fr_bk_int, text="Intervalo entre backups (HH:MM):", text_color="gray60").pack(side="left")
    ctk.CTkEntry(fr_bk_int, textvariable=app._bk_interval_var, width=80, height=28,
                 placeholder_text="06:00").pack(side="left", padx=6)

    def _run_global_backup_now() -> None:
        if hasattr(app, "_run_global_backup"):
            app._run_global_backup()

    ctk.CTkButton(
        bk_card, text="▶ Executar backup agora", height=32,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=_run_global_backup_now,
    ).grid(row=10, column=0, columnspan=2, padx=16, pady=(0, 14), sticky="w")

    # ── Seção Auto-Atualização ───────────────────────────────────────────────
    app._section_lbl(parent, _next_row + 10, "🔄  Atualização Automática")
    upd_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    upd_card.grid(row=_next_row + 11, column=0, padx=20, pady=(0, 14), sticky="ew")
    upd_card.grid_columnconfigure(1, weight=1)

    au = cfg.auto_update
    app._au_cache_dir_var      = tk.StringVar(value=au.cache_dir)
    app._au_interval_var       = tk.StringVar(value=au.update_interval)
    app._au_smart_cache_var    = tk.BooleanVar(value=au.smart_cache_copy)
    app._au_validate_var       = tk.BooleanVar(value=au.validate_server_files)
    app._au_parallel_var       = tk.BooleanVar(value=au.update_in_parallel)
    app._au_delay_var          = tk.IntVar(value=au.update_delay_seconds)
    app._au_show_reason_var    = tk.BooleanVar(value=au.show_update_reason)
    app._au_reason_prefix_var  = tk.StringVar(value=au.update_reason_prefix)
    app._au_replace_restart_var = tk.BooleanVar(value=au.replace_restart_after_update)

    ctk.CTkCheckBox(upd_card, text="Ativar atualização automática",
                    variable=app._au_auto_var if hasattr(app, "_au_auto_var") else tk.BooleanVar(value=True),
                    checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    ).grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 4), sticky="w")

    ctk.CTkLabel(upd_card, text="Diretório de Cache:", width=200, anchor="w",
                 text_color="gray60").grid(row=1, column=0, padx=16, pady=(4, 2), sticky="w")
    fr_cache = ctk.CTkFrame(upd_card, fg_color="transparent")
    fr_cache.grid(row=1, column=1, padx=(0, 16), pady=(4, 2), sticky="ew")
    fr_cache.grid_columnconfigure(0, weight=1)
    ctk.CTkEntry(fr_cache, textvariable=app._au_cache_dir_var, height=30).grid(
        row=0, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkButton(fr_cache, text="📁", width=30, height=30,
                  command=lambda: app._browse_dir(app._au_cache_dir_var)).grid(row=0, column=1)

    fr_upd_int = ctk.CTkFrame(upd_card, fg_color="transparent")
    fr_upd_int.grid(row=2, column=0, columnspan=2, padx=16, pady=(6, 2), sticky="w")
    ctk.CTkLabel(fr_upd_int, text="Intervalo de atualização:", text_color="gray60").pack(side="left")
    ctk.CTkEntry(fr_upd_int, textvariable=app._au_interval_var, width=80, height=28,
                 placeholder_text="01:00").pack(side="left", padx=6)

    chk_fr = ctk.CTkFrame(upd_card, fg_color="transparent")
    chk_fr.grid(row=3, column=0, columnspan=2, padx=12, pady=(6, 0), sticky="w")
    for ci, (txt, var) in enumerate([
        ("Use cópia de cache inteligente",               app._au_smart_cache_var),
        ("Validar Arquivos do Servidor",                 app._au_validate_var),
        ("Atualize os servidores em paralelo",           app._au_parallel_var),
        ("Substituir a reinicialização após atualização automática", app._au_replace_restart_var),
    ]):
        ctk.CTkCheckBox(chk_fr, text=txt, variable=var, width=320,
                        checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                        ).grid(row=ci // 2, column=ci % 2, padx=8, pady=3, sticky="w")

    fr_delay = ctk.CTkFrame(upd_card, fg_color="transparent")
    fr_delay.grid(row=4, column=0, columnspan=2, padx=16, pady=(6, 2), sticky="w")
    ctk.CTkLabel(fr_delay, text="Atraso entre cada atualização do servidor:", text_color="gray60").pack(side="left")
    ctk.CTkEntry(fr_delay, textvariable=app._au_delay_var, width=60, height=28).pack(side="left", padx=6)
    ctk.CTkLabel(fr_delay, text="segundos", text_color="gray60").pack(side="left")

    ctk.CTkCheckBox(upd_card, text="Mostrar o motivo da atualização nas mensagens de desligamento",
                    variable=app._au_show_reason_var,
                    checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    ).grid(row=5, column=0, columnspan=2, padx=16, pady=(6, 2), sticky="w")
    ctk.CTkLabel(upd_card, text="Motivo da Atualização:", width=200, anchor="w",
                 text_color="gray60").grid(row=6, column=0, padx=16, pady=(4, 14), sticky="w")
    ctk.CTkEntry(upd_card, textvariable=app._au_reason_prefix_var, height=28).grid(
        row=6, column=1, padx=(0, 16), pady=(4, 14), sticky="ew")

    # ── Seção Desligamento ──────────────────────────────────────────────────
    app._section_lbl(parent, _next_row + 12, "⏹️  Opções de Desligamento")
    sd_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    sd_card.grid(row=_next_row + 13, column=0, padx=20, pady=(0, 14), sticky="ew")
    sd_card.grid_columnconfigure(1, weight=1)

    sd = cfg.shutdown
    app._sd_check_online_var  = tk.BooleanVar(value=sd.check_online_players)
    app._sd_send_msgs_var     = tk.BooleanVar(value=sd.send_msgs_to_client)
    app._sd_grace_var         = tk.IntVar(value=sd.grace_period_minutes)
    app._sd_msg1_var          = tk.StringVar(value=sd.msg1)
    app._sd_msg2_var          = tk.StringVar(value=sd.msg2)
    app._sd_msg3_var          = tk.StringVar(value=sd.msg3)
    app._sd_save_msg_var      = tk.StringVar(value=sd.save_message)
    app._sd_cancel_msg_var    = tk.StringVar(value=sd.cancel_message)
    app._sd_show_reason_var   = tk.BooleanVar(value=sd.show_reason_all_msgs)

    ctk.CTkLabel(sd_card, text="Essas mensagens serão transmitidas apenas se o RCON estiver ativado.",
                 text_color="#c0824a", font=ctk.CTkFont(size=10), wraplength=560).grid(
        row=0, column=0, columnspan=2, padx=16, pady=(10, 4), sticky="w")

    fr_sd_top = ctk.CTkFrame(sd_card, fg_color="transparent")
    fr_sd_top.grid(row=1, column=0, columnspan=2, padx=12, pady=(4, 0), sticky="w")
    ctk.CTkCheckBox(fr_sd_top, text="Executar verificação de jogador online",
                    variable=app._sd_check_online_var,
                    checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    ).pack(side="left", padx=8)
    ctk.CTkCheckBox(fr_sd_top, text="Enviar mensagens de desligamento para o Game Client",
                    variable=app._sd_send_msgs_var,
                    checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    ).pack(side="left", padx=8)

    fr_grace = ctk.CTkFrame(sd_card, fg_color="transparent")
    fr_grace.grid(row=2, column=0, columnspan=2, padx=16, pady=(8, 4), sticky="w")
    ctk.CTkLabel(fr_grace, text="Período de carência:", text_color="gray60").pack(side="left")
    ctk.CTkEntry(fr_grace, textvariable=app._sd_grace_var, width=60, height=28).pack(side="left", padx=6)
    ctk.CTkLabel(fr_grace, text="minutos", text_color="gray60").pack(side="left")

    for r, (lbl, var) in enumerate([
        ("Mensagem 1:",        app._sd_msg1_var),
        ("Mensagem 2:",        app._sd_msg2_var),
        ("Mensagem 3:",        app._sd_msg3_var),
        ("Mensagem do Save:",  app._sd_save_msg_var),
        ("Cancelar mensagem:", app._sd_cancel_msg_var),
    ], start=3):
        ctk.CTkLabel(sd_card, text=lbl, width=160, anchor="w",
                     text_color="gray60").grid(row=r, column=0, padx=16, pady=3, sticky="w")
        ctk.CTkEntry(sd_card, textvariable=var, height=28).grid(
            row=r, column=1, padx=(0, 16), pady=3, sticky="ew")

    ctk.CTkCheckBox(sd_card, text="Mostrar o motivo de desligamento com TODAS as mensagens de desligamento",
                    variable=app._sd_show_reason_var,
                    checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    ).grid(row=8, column=0, columnspan=2, padx=16, pady=(8, 14), sticky="w")

    # ── Seção Mensagens de Alerta ───────────────────────────────────────────
    app._section_lbl(parent, _next_row + 14, "🔔  Opções de Alerta")
    al_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    al_card.grid(row=_next_row + 15, column=0, padx=20, pady=(0, 14), sticky="ew")
    al_card.grid_columnconfigure(1, weight=1)

    am = cfg.alert_messages
    app._al_stopped_var        = tk.StringVar(value=am.server_stopped)
    app._al_shutting_var       = tk.StringVar(value=am.server_shutting_down)
    app._al_started_var        = tk.StringVar(value=am.server_started)
    app._al_incl_ip_var        = tk.BooleanVar(value=am.include_ip_port)
    app._al_ip_fmt_var         = tk.StringVar(value=am.ip_port_format)
    app._al_bk_err_var         = tk.StringVar(value=am.backup_error)
    app._al_sd_err_var         = tk.StringVar(value=am.shutdown_error)
    app._al_rst_err_var        = tk.StringVar(value=am.restart_error)
    app._al_upd_err_var        = tk.StringVar(value=am.update_error)
    app._al_upd_res_var        = tk.StringVar(value=am.update_result)
    app._al_srv_upd_var        = tk.StringVar(value=am.server_update_msg)
    app._al_srv_stat_var       = tk.StringVar(value=am.server_status)
    app._al_mod_upd_var        = tk.StringVar(value=am.mod_update_detected)
    app._al_players_var        = tk.StringVar(value=am.players_changed)
    app._al_dino_var           = tk.StringVar(value=am.dino_respawn)

    for r, (lbl, var) in enumerate([
        ("Mensagem de Parada do Servidor:",            app._al_stopped_var),
        ("Mensagem de desligamento do servidor:",      app._al_shutting_var),
        ("Mensagem iniciada pelo servidor:",           app._al_started_var),
        ("Erro no processo de backup:",                app._al_bk_err_var),
        ("Erro no processo de desligamento:",          app._al_sd_err_var),
        ("Erro no processo de reiniciar:",             app._al_rst_err_var),
        ("Erro no processo de atualizar:",             app._al_upd_err_var),
        ("Resultado da atualização:",                  app._al_upd_res_var),
        ("Mensagem de atualização do servidor:",       app._al_srv_upd_var),
        ("Status do servidor:",                        app._al_srv_stat_var),
        ("Atualização de mods detectada:",             app._al_mod_upd_var),
        ("Alteração na contagem de jogadores online:", app._al_players_var),
        ("Força Respawn de Dinos:",                    app._al_dino_var),
    ]):
        ctk.CTkLabel(al_card, text=lbl, width=280, anchor="w",
                     text_color="gray60").grid(row=r, column=0, padx=16, pady=3, sticky="w")
        ctk.CTkEntry(al_card, textvariable=var, height=28).grid(
            row=r, column=1, padx=(0, 16), pady=3, sticky="ew")

    fr_ip = ctk.CTkFrame(al_card, fg_color="transparent")
    fr_ip.grid(row=13, column=0, columnspan=2, padx=12, pady=(6, 14), sticky="w")
    ctk.CTkCheckBox(fr_ip, text="Incluir IP Público e Porta na Mensagem Inicial",
                    variable=app._al_incl_ip_var,
                    checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    ).pack(side="left", padx=8)
    ctk.CTkEntry(fr_ip, textvariable=app._al_ip_fmt_var, width=180, height=28,
                 placeholder_text="{ipaddress}:{port}").pack(side="left", padx=6)

    # ── Seção Discord Bot ───────────────────────────────────────────────────
    app._section_lbl(parent, _next_row + 16, "🤖  Discord Bot")
    bot_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    bot_card.grid(row=_next_row + 17, column=0, padx=20, pady=(0, 14), sticky="ew")
    bot_card.grid_columnconfigure(1, weight=1)

    db = cfg.discord_bot
    app._db_enabled_var       = tk.BooleanVar(value=db.enabled)
    app._db_token_var         = tk.StringVar(value=db.token)
    app._db_server_id_var     = tk.StringVar(value=db.server_id)
    app._db_prefix_var        = tk.StringVar(value=db.prefix)
    app._db_log_level_var     = tk.StringVar(value=db.log_level)
    app._db_alias_var         = tk.StringVar(value=db.alias_all_profiles)
    app._db_allow_backup_var  = tk.BooleanVar(value=db.allow_backup)
    app._db_allow_update_var  = tk.BooleanVar(value=db.allow_update)
    app._db_allow_restart_var = tk.BooleanVar(value=db.allow_restart)
    app._db_allow_shutdown_var = tk.BooleanVar(value=db.allow_shutdown)
    app._db_allow_start_var   = tk.BooleanVar(value=db.allow_start)
    app._db_allow_stop_var    = tk.BooleanVar(value=db.allow_stop)
    app._db_all_bots_var      = tk.BooleanVar(value=db.allow_all_bots)

    ctk.CTkCheckBox(bot_card, text="Habilitar Discord Bot",
                    variable=app._db_enabled_var,
                    checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    ).grid(row=0, column=0, columnspan=2, padx=16, pady=(16, 4), sticky="w")
    ctk.CTkLabel(bot_card, text="Você precisará reiniciar o server manager se alterar alguma configuração do Discord Bot.",
                 text_color="#c0824a", font=ctk.CTkFont(size=10), wraplength=560).grid(
        row=1, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="w")

    fr_tok = ctk.CTkFrame(bot_card, fg_color="transparent")
    fr_tok.grid(row=2, column=0, columnspan=2, padx=12, pady=(4, 0), sticky="ew")
    fr_tok.grid_columnconfigure(1, weight=1)
    ctk.CTkLabel(fr_tok, text="Token:", width=80, anchor="w", text_color="gray60").grid(
        row=0, column=0, padx=4)
    ctk.CTkEntry(fr_tok, textvariable=app._db_token_var, height=30, show="*").grid(
        row=0, column=1, sticky="ew", padx=4)

    fr_bot_row = ctk.CTkFrame(bot_card, fg_color="transparent")
    fr_bot_row.grid(row=3, column=0, columnspan=2, padx=12, pady=(6, 0), sticky="ew")
    for lbl, var, w in [
        ("Server ID:", app._db_server_id_var, 200),
        ("Prefix:",    app._db_prefix_var,    80),
        ("Alias all:", app._db_alias_var,     80),
    ]:
        ctk.CTkLabel(fr_bot_row, text=lbl, text_color="gray60").pack(side="left", padx=(8, 2))
        ctk.CTkEntry(fr_bot_row, textvariable=var, width=w, height=28).pack(side="left", padx=(0, 8))
    ctk.CTkLabel(fr_bot_row, text="Nível de registro:", text_color="gray60").pack(side="left", padx=(8, 2))
    ctk.CTkComboBox(fr_bot_row, variable=app._db_log_level_var, width=140, height=28,
                    values=["Informações", "Depuração", "Aviso", "Erro"]).pack(side="left", padx=(0, 8))

    perm_fr = ctk.CTkFrame(bot_card, fg_color="transparent")
    perm_fr.grid(row=4, column=0, columnspan=2, padx=12, pady=(10, 4), sticky="w")
    for ci, (txt, var) in enumerate([
        ("Permitir backup",       app._db_allow_backup_var),
        ("Permitir atualização",  app._db_allow_update_var),
        ("Permitir Reinício",     app._db_allow_restart_var),
        ("Permitir desligamento", app._db_allow_shutdown_var),
        ("Permitir iniciar",      app._db_allow_start_var),
        ("Permitir parar",        app._db_allow_stop_var),
    ]):
        ctk.CTkCheckBox(perm_fr, text=txt, variable=var, width=200,
                        checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                        ).grid(row=ci // 3, column=ci % 3, padx=8, pady=3, sticky="w")

    ctk.CTkCheckBox(bot_card, text="Permitir todos os bots",
                    variable=app._db_all_bots_var,
                    checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    ).grid(row=5, column=0, columnspan=2, padx=16, pady=(6, 14), sticky="w")

    # ── Seção SMTP ───────────────────────────────────────────────────────────
    app._section_lbl(parent, _next_row + 18, "✉️  Configurações de Email SMTP")
    smtp_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    smtp_card.grid(row=_next_row + 19, column=0, padx=20, pady=(0, 14), sticky="ew")
    smtp_card.grid_columnconfigure(1, weight=1)
    smtp_card.grid_columnconfigure(3, weight=1)

    sm = cfg.smtp
    app._smtp_host_var    = tk.StringVar(value=sm.host)
    app._smtp_port_var    = tk.IntVar(value=sm.port)
    app._smtp_ssl_var     = tk.BooleanVar(value=sm.use_ssl)
    app._smtp_defcred_var = tk.BooleanVar(value=sm.use_default_credentials)
    app._smtp_user_var    = tk.StringVar(value=sm.username)
    app._smtp_pass_var    = tk.StringVar(value=sm.password)
    app._smtp_from_var    = tk.StringVar(value=sm.from_address)
    app._smtp_to_var      = tk.StringVar(value=sm.to_address)
    app._smtp_n_backup_var  = tk.BooleanVar(value=sm.notify_auto_backup)
    app._smtp_n_update_var  = tk.BooleanVar(value=sm.notify_auto_update)
    app._smtp_n_shutdown_var = tk.BooleanVar(value=sm.notify_auto_shutdown)
    app._smtp_n_restart_var  = tk.BooleanVar(value=sm.notify_shutdown_restart)

    fr_smtp1 = ctk.CTkFrame(smtp_card, fg_color="transparent")
    fr_smtp1.grid(row=0, column=0, columnspan=4, padx=12, pady=(14, 4), sticky="ew")
    for lbl, var, w, show in [
        ("Host:",   app._smtp_host_var, 220, ""),
        ("Porta:",  app._smtp_port_var,  60, ""),
        ("Senha:",  app._smtp_pass_var, 140, "*"),
    ]:
        ctk.CTkLabel(fr_smtp1, text=lbl, text_color="gray60").pack(side="left", padx=(8, 2))
        ctk.CTkEntry(fr_smtp1, textvariable=var, width=w, height=28, show=show).pack(side="left", padx=(0, 8))
    ctk.CTkCheckBox(fr_smtp1, text="Use SSL",
                    variable=app._smtp_ssl_var,
                    checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    ).pack(side="left", padx=8)

    fr_smtp2 = ctk.CTkFrame(smtp_card, fg_color="transparent")
    fr_smtp2.grid(row=1, column=0, columnspan=4, padx=12, pady=(4, 4), sticky="ew")
    ctk.CTkCheckBox(fr_smtp2, text="Use credenciais padrão",
                    variable=app._smtp_defcred_var,
                    checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    ).pack(side="left", padx=8)
    ctk.CTkLabel(fr_smtp2, text="Nome de usuário:", text_color="gray60").pack(side="left", padx=(16, 2))
    ctk.CTkEntry(fr_smtp2, textvariable=app._smtp_user_var, width=160, height=28).pack(side="left", padx=(0, 8))

    fr_smtp3 = ctk.CTkFrame(smtp_card, fg_color="transparent")
    fr_smtp3.grid(row=2, column=0, columnspan=4, padx=12, pady=(4, 6), sticky="ew")
    ctk.CTkLabel(fr_smtp3, text="De:", text_color="gray60").pack(side="left", padx=(8, 2))
    ctk.CTkEntry(fr_smtp3, textvariable=app._smtp_from_var, width=200, height=28).pack(side="left", padx=(0, 8))
    ctk.CTkLabel(fr_smtp3, text="Para:", text_color="gray60").pack(side="left", padx=(8, 2))
    ctk.CTkEntry(fr_smtp3, textvariable=app._smtp_to_var, width=200, height=28).pack(side="left", padx=(0, 8))
    ctk.CTkButton(fr_smtp3, text="Enviar email de teste", width=160, height=28,
                  fg_color="#0e4a6e", hover_color="#0a3550",
                  command=lambda: None).pack(side="left", padx=8)

    ctk.CTkLabel(smtp_card, text="Configurações de notificação por email:",
                 text_color="gray55", font=ctk.CTkFont(size=11, weight="bold")).grid(
        row=3, column=0, columnspan=4, padx=16, pady=(8, 2), sticky="w")
    notif_fr = ctk.CTkFrame(smtp_card, fg_color="transparent")
    notif_fr.grid(row=4, column=0, columnspan=4, padx=12, pady=(0, 14), sticky="w")
    for ci, (txt, var) in enumerate([
        ("Backup automático",      app._smtp_n_backup_var),
        ("Atualização automática", app._smtp_n_update_var),
        ("Desligamento automático", app._smtp_n_shutdown_var),
        ("Desligamento / Reinício", app._smtp_n_restart_var),
    ]):
        ctk.CTkCheckBox(notif_fr, text=txt, variable=var, width=220,
                        checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                        ).grid(row=0, column=ci, padx=8, pady=3, sticky="w")

    # ── Servidores legados (modo primitivo) ───────────────────────────────
    _legacy = list(app.config_manager.servers)
    if _legacy:
        app._section_lbl(parent, _next_row + 21, "📦  Servidores legados (modo primitivo)")
        leg_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
        leg_card.grid(row=_next_row + 22, column=0, padx=20, pady=(0, 14), sticky="ew")
        leg_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            leg_card,
            text="Estes servidores foram criados no modo primitivo. "
                 "Remova-os aqui se não tiver mais acesso àquele modo.",
            text_color="gray50",
            font=ctk.CTkFont(size=11),
            wraplength=700,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, padx=16, pady=(14, 8), sticky="w")

        for ri, srv in enumerate(_legacy):
            ctk.CTkLabel(
                leg_card, text=srv.name, anchor="w",
                font=ctk.CTkFont(size=12, weight="bold"),
            ).grid(row=ri + 1, column=0, padx=16, pady=6, sticky="w")
            ctk.CTkLabel(
                leg_card,
                text=(srv.install_dir or "(sem pasta)")[:72],
                text_color="gray55",
                font=ctk.CTkFont(size=10),
                anchor="w",
            ).grid(row=ri + 1, column=1, padx=8, pady=6, sticky="ew")
            ctk.CTkButton(
                leg_card, text="Remover", width=90, height=28,
                fg_color="#7f1d1d", hover_color="#991b1b",
                command=lambda sid=srv.id: (
                    app._confirm_remove_primitive_server(sid)
                    if hasattr(app, "_confirm_remove_primitive_server")
                    else app._confirm_remove_server(sid)
                ),
            ).grid(row=ri + 1, column=2, padx=(0, 16), pady=6)

    ctk.CTkButton(
        parent, text="💾  Salvar Configurações Globais",
        height=44, font=ctk.CTkFont(size=14, weight="bold"),
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=app._save_global_config,
    ).grid(row=_next_row + 24, column=0, padx=20, pady=(0, 24), sticky="ew")

