"""Construtor da aba Geral no modo primitivo (servidor sem TEK mode ativo)."""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, List, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..server_config import ServerConfig, ARK_MAPS, ARK_MAP_NAMES
from ..ui_constants import (
    _ARK_EVENT_ID_TO_LABEL, _ARK_EVENT_LABEL_TO_ID, _ARK_OFFICIAL_EVENTS,
    _GREEN_DARK, _GREEN_HOVER, _BLUE, _BLUE_HOVER, _CARD_BG,
)

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_tab_general_primitive(app: "ARKServerManagerApp", parent, srv: ServerConfig) -> None:
    scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
    scroll.pack(fill="both", expand=True, padx=4, pady=4)
    scroll.grid_columnconfigure(1, weight=1)

    w = app._server_widgets[srv.id]

    def row(label: str, hint: str, var, row_n: int, is_pass: bool = False,
            browse: bool = False, combo: Optional[List] = None) -> None:
        lbl_fr = ctk.CTkFrame(scroll, fg_color="transparent")
        lbl_fr.grid(row=row_n, column=0, padx=(16, 8), pady=(4, 0), sticky="w")
        ctk.CTkLabel(lbl_fr, text=label, width=200, anchor="w",
                     text_color="gray65",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        if hint:
            ctk.CTkLabel(lbl_fr, text=hint, width=200, anchor="w",
                         text_color="gray40",
                         font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))
        if combo:
            ent = ctk.CTkComboBox(scroll, variable=var, values=combo, width=340, height=34)
            ent.grid(row=row_n, column=1, padx=(0, 16), pady=4, sticky="w")
        elif browse:
            fr = ctk.CTkFrame(scroll, fg_color="transparent")
            fr.grid(row=row_n, column=1, padx=(0, 16), pady=4, sticky="ew")
            fr.grid_columnconfigure(0, weight=1)
            ctk.CTkEntry(fr, textvariable=var, height=34).grid(
                row=0, column=0, sticky="ew", padx=(0, 6))
            ctk.CTkButton(fr, text="📁", width=34, height=34,
                          command=lambda v=var: app._browse_dir(v)).grid(row=0, column=1)
        else:
            ctk.CTkEntry(scroll, textvariable=var, height=34,
                         show="*" if is_pass else "").grid(
                row=row_n, column=1, padx=(0, 16), pady=4, sticky="ew")

    w["name"]            = tk.StringVar(value=srv.name)
    w["install_dir"]     = tk.StringVar(value=srv.install_dir)
    w["server_name"]     = tk.StringVar(value=srv.server_name)
    w["map"]             = tk.StringVar(value=srv.map)
    w["server_password"] = tk.StringVar(value=srv.server_password)
    w["admin_password"]  = tk.StringVar(value=srv.admin_password)
    w["rcon_password"]   = tk.StringVar(value=srv.rcon_password)
    w["max_players"]     = tk.StringVar(value=str(srv.max_players))
    w["server_port"]     = tk.StringVar(value=str(srv.server_port))
    w["query_port"]      = tk.StringVar(value=str(srv.query_port))
    w["rcon_port"]       = tk.StringVar(value=str(srv.rcon_port))
    w["extra_args"]      = tk.StringVar(value=srv.extra_args)
    w["active_event"]    = tk.StringVar(
        value=_ARK_EVENT_ID_TO_LABEL.get(srv.active_event, srv.active_event) or "(nenhum evento)")
    w["auto_save"]       = tk.StringVar(value=str(srv.auto_save_period))

    app._section_lbl(scroll, 0, "🖥️  Identificação")
    row("Nome interno:",
        "Label exibido na barra lateral do app.",
        w["name"], 1)
    row("Diretório de Instalação:",
        "Pasta onde o ARK Server será instalado/atualizado.",
        w["install_dir"], 2, browse=True)
    row("Nome do Servidor:",
        "Nome visível na lista de servidores do jogo (Session Name).",
        w["server_name"], 3)

    app._section_lbl(scroll, 4, "🗺️  Mapa")
    row("Mapa:",
        "Selecione o mapa que o servidor irá rodar.",
        w["map"], 5, combo=[
            f"{ARK_MAP_NAMES.get(m, m)} ({m})" for m in ARK_MAPS
        ])

    app._section_lbl(scroll, 6, "🔌  Rede e Portas")
    row("Porta do Servidor:",
        "Porta principal UDP. Padrão: 7777. Liberar no roteador (UDP).",
        w["server_port"], 7)
    row("Porta de Query:",
        "Porta de consulta Steam. Padrão: 27015. Liberar no roteador (UDP).",
        w["query_port"], 8)
    row("Porta RCON:",
        "Porta do console remoto. Padrão: 27020. Só abrir se usar RCON externo.",
        w["rcon_port"], 9)

    app._section_lbl(scroll, 10, "🔒  Acesso")
    row("Senha do Servidor:",
        "Senha para entrar. Deixe vazio para servidor público.",
        w["server_password"], 11, is_pass=True)
    row("Senha de Admin:",
        "Usada para ativar cheats in-game (enablecheats). Mantenha secreta.",
        w["admin_password"], 12, is_pass=True)
    row("Senha RCON:",
        "Senha para conexão via console RCON. Geralmente igual à de admin.",
        w["rcon_password"], 13, is_pass=True)
    row("Máx. Jogadores:",
        "Limite de jogadores simultâneos no servidor.",
        w["max_players"], 14)

    app._section_lbl(scroll, 15, "⚙️  Opções de Inicialização")
    row("Evento Ativo:",
        "Selecione o evento oficial do ARK ou deixe em «(nenhum evento)».",
        w["active_event"], 16,
        combo=[label for _, label in _ARK_OFFICIAL_EVENTS])
    row("Auto-Save (min):",
        "Intervalo de salvamento automático em minutos. Padrão: 15.",
        w["auto_save"], 17)
    row("Argumentos Extras:",
        "Parâmetros adicionais de linha de comando. Ex: -ForceAllowCaveFlyers.",
        w["extra_args"], 18)

    w["rcon_enabled"]       = tk.BooleanVar(value=srv.rcon_enabled)
    w["use_battleye"]       = tk.BooleanVar(value=srv.use_battleye)
    w["use_allcores"]       = tk.BooleanVar(value=srv.use_allcores)
    w["force_respawn"]      = tk.BooleanVar(value=srv.force_respawn_dinos)
    w["whitelist_only"]     = tk.BooleanVar(value=srv.whitelist_only)
    w["auto_restart_crash"] = tk.BooleanVar(value=srv.auto_restart_on_crash)
    w["auto_update_start"]  = tk.BooleanVar(value=srv.auto_update_on_start)

    app._section_lbl(scroll, 19, "🔧  Flags")
    checkboxes = [
        ("Habilitar RCON",
         "Ativa o console remoto. Necessário para usar a aba Console RCON.",
         w["rcon_enabled"]),
        ("Usar BattlEye (anti-cheat)",
         "Proteção anti-cheat oficial. Desative para servidores com mods incompatíveis.",
         w["use_battleye"]),
        ("Usar todos os núcleos de CPU",
         "Permite que o servidor use todos os núcleos disponíveis na máquina.",
         w["use_allcores"]),
        ("Forçar respawn de dinos",
         "Reseta todos os dinos selvagens ao iniciar o servidor.",
         w["force_respawn"]),
        ("Apenas whitelist",
         "Somente jogadores na whitelist podem entrar no servidor.",
         w["whitelist_only"]),
        ("Auto-restart ao travar",
         "Reinicia o servidor automaticamente caso ocorra um crash.",
         w["auto_restart_crash"]),
        ("Atualizar servidor ao iniciar",
         "Verifica e aplica atualizações via SteamCMD antes de iniciar.",
         w["auto_update_start"]),
    ]
    for ci, (txt, hint_txt, var) in enumerate(checkboxes):
        cb_fr = ctk.CTkFrame(scroll, fg_color="transparent")
        cb_fr.grid(row=20 + ci, column=0, columnspan=2, padx=16, pady=(4, 0), sticky="w")
        ctk.CTkCheckBox(cb_fr, text=txt, variable=var,
                        checkmark_color="white", fg_color=_GREEN_DARK,
                        hover_color=_GREEN_HOVER).pack(anchor="w")
        ctk.CTkLabel(cb_fr, text=hint_txt, text_color="gray40",
                     font=ctk.CTkFont(size=10), anchor="w").pack(
            anchor="w", padx=(26, 0), pady=(0, 2))

    app._save_btn_row(scroll, 27, srv.id)

    # ── Seção Instalação ─────────────────────────────────────────────────
    app._section_lbl(scroll, 28, "⬇️  Instalação / Atualização do Servidor")
    inst_card = ctk.CTkFrame(scroll, corner_radius=12, fg_color=_CARD_BG)
    inst_card.grid(row=29, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="ew")
    inst_card.grid_columnconfigure(0, weight=1)

    btn_row = ctk.CTkFrame(inst_card, fg_color="transparent")
    btn_row.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="w")

    inst_btn = ctk.CTkButton(
        btn_row, text="⬇  Instalar / Atualizar Servidor",
        height=38, width=230,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=lambda sid=srv.id: app._run_server_install(sid, validate=False))
    inst_btn.grid(row=0, column=0, padx=(0, 10))

    val_btn = ctk.CTkButton(
        btn_row, text="✅  Verificar Arquivos (validate)",
        height=38, width=230,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=lambda sid=srv.id: app._run_server_install(sid, validate=True))
    val_btn.grid(row=0, column=1)

    ctk.CTkLabel(inst_card,
                 text="Usa o SteamCMD para baixar/atualizar os arquivos do servidor ARK: Survival Evolved (App 376030).\n"
                      "O 'Diretório de Instalação' acima deve estar preenchido. Salve antes de instalar.",
                 text_color="gray45", font=ctk.CTkFont(size=10), justify="left").grid(
        row=1, column=0, padx=16, pady=(0, 6), sticky="w")

    inst_status = ctk.CTkLabel(inst_card, text="", text_color="gray60",
                               font=ctk.CTkFont(size=11))
    inst_status.grid(row=2, column=0, padx=16, pady=(0, 4), sticky="w")

    inst_log = ctk.CTkTextbox(
        inst_card, height=160, state="disabled",
        font=ctk.CTkFont(family="Consolas", size=10),
        fg_color="#0d0d18", text_color="#c8c8d8", corner_radius=6)
    inst_log.grid(row=3, column=0, padx=16, pady=(0, 14), sticky="ew")

    app._server_widgets[srv.id]["_inst_status"] = inst_status
    app._server_widgets[srv.id]["_inst_log"]    = inst_log
    app._server_widgets[srv.id]["_inst_btn"]    = inst_btn
    app._server_widgets[srv.id]["_val_btn"]     = val_btn
