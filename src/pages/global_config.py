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

    app._section_lbl(parent, 4, "📂  Diretório Padrão de Instalação")
    dir_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    dir_card.grid(row=5, column=0, padx=20, pady=(0, 14), sticky="ew")
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

    app._section_lbl(parent, 6, "🔧  Opções")
    opt_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    opt_card.grid(row=7, column=0, padx=20, pady=(0, 14), sticky="ew")

    app._cfg_startup_var   = tk.BooleanVar(value=cfg.startup_with_windows)
    app._cfg_minimize_tray_var = tk.BooleanVar(value=cfg.minimize_to_tray)
    app._cfg_log_debug_var = tk.BooleanVar(value=cfg.log_debug)

    ctk.CTkCheckBox(opt_card, text="Iniciar o ARKLAND - Server Manager com o Windows",
                    variable=app._cfg_startup_var,
                    checkmark_color="white", fg_color=_GREEN_DARK,
                    hover_color=_GREEN_HOVER).grid(
        row=0, column=0, padx=16, pady=(16, 2), sticky="w")
    ctk.CTkLabel(opt_card,
                 text="Inicia o app automaticamente quando o Windows ligar.",
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
        row=5, column=0, padx=(42, 16), pady=(0, 16), sticky="w")

    # ── Seção Discord ───────────────────────────────────────────
    app._section_lbl(parent, 8, "🔔  Notificações Discord")
    disc_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    disc_card.grid(row=9, column=0, padx=20, pady=(0, 14), sticky="ew")
    disc_card.grid_columnconfigure(1, weight=1)

    dc = cfg.discord_notify
    app._discord_enabled_var    = tk.BooleanVar(value=dc.enabled)
    app._discord_url_var        = tk.StringVar(value=dc.webhook_url)
    app._discord_sender_var     = tk.StringVar(value=dc.sender_name)
    app._discord_notify_start   = tk.BooleanVar(value=dc.notify_start)
    app._discord_notify_stop    = tk.BooleanVar(value=dc.notify_stop)
    app._discord_notify_crash   = tk.BooleanVar(value=dc.notify_crash)
    app._discord_notify_update  = tk.BooleanVar(value=dc.notify_update)
    app._discord_notify_backup  = tk.BooleanVar(value=dc.notify_backup)

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
    evt_fr.grid(row=7, column=0, columnspan=2, padx=12, pady=(0, 14), sticky="w")
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

    ctk.CTkButton(
        parent, text="💾  Salvar Configurações Globais",
        height=44, font=ctk.CTkFont(size=14, weight="bold"),
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=app._save_global_config,
    ).grid(row=10, column=0, padx=20, pady=(0, 24), sticky="ew")

