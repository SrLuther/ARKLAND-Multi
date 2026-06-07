"""Construtor da aba Avançado/Cross-ARK no modo primitivo (servidor sem TEK mode)."""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..server_config import ServerConfig
from ..ui_constants import _GREEN_DARK, _GREEN_HOVER, _BLUE, _BLUE_HOVER, _CARD_BG

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_tab_advanced_primitive(app: "ARKServerManagerApp", parent, srv: ServerConfig) -> None:
    scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
    scroll.pack(fill="both", expand=True, padx=4, pady=4)
    scroll.grid_columnconfigure(1, weight=1)

    w   = app._server_widgets[srv.id]
    adv = srv.advanced_settings
    cl  = srv.cluster

    def brow(label: str, hint: str, field: str, val: bool, row_n: int, prefix: str = "adv_") -> None:
        w[f"{prefix}{field}"] = tk.BooleanVar(value=val)
        cb_fr = ctk.CTkFrame(scroll, fg_color="transparent")
        cb_fr.grid(row=row_n, column=0, columnspan=2, padx=16, pady=(4, 0), sticky="w")
        ctk.CTkCheckBox(cb_fr, text=label, variable=w[f"{prefix}{field}"],
                        checkmark_color="white", fg_color=_GREEN_DARK,
                        hover_color=_GREEN_HOVER).pack(anchor="w")
        if hint:
            ctk.CTkLabel(cb_fr, text=hint, text_color="gray40",
                         font=ctk.CTkFont(size=10), anchor="w").pack(
                anchor="w", padx=(26, 0), pady=(0, 2))

    def frow(label: str, hint: str, field: str, val: float, row_n: int, prefix: str = "adv_") -> None:
        w[f"{prefix}{field}"] = tk.StringVar(value=str(val))
        lbl_fr = ctk.CTkFrame(scroll, fg_color="transparent")
        lbl_fr.grid(row=row_n, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
        ctk.CTkLabel(lbl_fr, text=label, width=310, anchor="w",
                     text_color="gray65",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        if hint:
            ctk.CTkLabel(lbl_fr, text=hint, width=310, anchor="w",
                         text_color="gray40",
                         font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))
        ctk.CTkEntry(scroll, textvariable=w[f"{prefix}{field}"], width=120, height=28).grid(
            row=row_n, column=1, padx=4, pady=4, sticky="w")

    r = 0
    app._section_lbl(scroll, r, "🌐  Cross-ARK (Cluster)")
    r += 1
    brow("Habilitar Cluster (Cross-ARK)",
         "Permite que múltiplos servidores compartilhem tribos, dinos e itens entre si.",
         "enabled", cl.enabled, r, "cl_")
    r += 1

    w["cl_cluster_id"]  = tk.StringVar(value=cl.cluster_id)
    w["cl_cluster_dir"] = tk.StringVar(value=cl.cluster_dir_override)

    cid_fr = ctk.CTkFrame(scroll, fg_color="transparent")
    cid_fr.grid(row=r, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
    ctk.CTkLabel(cid_fr, text="ID do Cluster:", width=310, anchor="w",
                 text_color="gray65",
                 font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
    ctk.CTkLabel(cid_fr, text="Identificador único do cluster. Todos os servidores do mesmo cluster devem usar o mesmo ID.",
                 width=310, anchor="w", text_color="gray40",
                 font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))
    ctk.CTkEntry(scroll, textvariable=w["cl_cluster_id"], height=30,
                 placeholder_text="Ex: MeuCluster123").grid(
        row=r, column=1, padx=4, pady=4, sticky="ew")
    r += 1

    cdir_fr = ctk.CTkFrame(scroll, fg_color="transparent")
    cdir_fr.grid(row=r, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
    ctk.CTkLabel(cdir_fr, text="Pasta do Cluster:", width=310, anchor="w",
                 text_color="gray65",
                 font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
    ctk.CTkLabel(cdir_fr, text="Pasta compartilhada para transferência de dados entre servidores. Opcional.",
                 width=310, anchor="w", text_color="gray40",
                 font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))
    dir_fr = ctk.CTkFrame(scroll, fg_color="transparent")
    dir_fr.grid(row=r, column=1, padx=4, pady=4, sticky="ew")
    dir_fr.grid_columnconfigure(0, weight=1)
    ctk.CTkEntry(dir_fr, textvariable=w["cl_cluster_dir"], height=30).grid(
        row=0, column=0, sticky="ew", padx=(0, 6))
    ctk.CTkButton(dir_fr, text="📁", width=34, height=30,
                  command=lambda: app._browse_dir(w["cl_cluster_dir"])).grid(row=0, column=1)
    r += 1

    app._section_lbl(scroll, r, "🚫  Restrições de Transferência (Cross-ARK)")
    r += 1
    brow("Bloquear Download de Sobreviventes",
         "Impede jogadores de importar personagens de outros servidores do cluster.",
         "prevent_download_survivors", adv.prevent_download_survivors, r)
    r += 1
    brow("Bloquear Download de Itens",
         "Impede jogadores de trazer itens de outros servidores do cluster.",
         "prevent_download_items",     adv.prevent_download_items,     r)
    r += 1
    brow("Bloquear Download de Dinos",
         "Impede jogadores de trazer dinos domesticados de outros servidores.",
         "prevent_download_dinos",     adv.prevent_download_dinos,     r)
    r += 1
    brow("Bloquear Upload de Sobreviventes",
         "Impede jogadores de enviar seus personagens para o cluster.",
         "prevent_upload_survivors",   adv.prevent_upload_survivors,   r)
    r += 1
    brow("Bloquear Upload de Itens",
         "Impede jogadores de enviar itens ao cluster.",
         "prevent_upload_items",       adv.prevent_upload_items,       r)
    r += 1
    brow("Bloquear Upload de Dinos",
         "Impede jogadores de enviar dinos ao cluster.",
         "prevent_upload_dinos",       adv.prevent_upload_dinos,       r)
    r += 1
    brow("Bloquear Transferência por Filtro",
         "Impede transferências bloqueadas por restrições de filtro de mapa.",
         "no_transfer_from_filtering", adv.no_transfer_from_filtering, r)
    r += 1

    app._section_lbl(scroll, r, "⚙️  Game.ini Avançado")
    r += 1
    brow("Nerf de Criôpod Ativado",
         "Aplica penalidade de dano em dinos recém-lançados do criôpod. Útil para PvP.",
         "enable_cryopod_nerf",                       adv.enable_cryopod_nerf,                       r)
    r += 1
    frow("Duração do Nerf de Criôpod (s)",
         "Quantos segundos dura a penalidade após sair do criôpod.",
         "cryopod_nerf_duration",                     adv.cryopod_nerf_duration,                     r)
    r += 1
    frow("Mult. de Dano do Nerf",
         "Fator de dano enquanto o nerf está ativo. Ex: 0.01 = apenas 1% do dano normal.",
         "cryopod_nerf_damage_mult",                  adv.cryopod_nerf_damage_mult,                  r)
    r += 1
    brow("Spawnar Supply Crates em Estruturas",
         "Permite que supply crates apareçam sobre estruturas construídas.",
         "allow_crateSpawns_on_top_of_structures",    adv.allow_crateSpawns_on_top_of_structures,    r)
    r += 1
    brow("Otimizar HP de Coleta",
         "Melhora a performance ao calcular HP de recursos coletáveis.",
         "use_optimized_harvesting_health",           adv.use_optimized_harvesting_health,           r)
    r += 1
    brow("Defesas Passivas Atacam Dinos sem Cavaleiro",
         "Torretas e armadilhas atacam dinos selvagens e sem piloto.",
         "b_passive_defenses_damage_riderless_dinos", adv.b_passive_defenses_damage_riderless_dinos, r)
    r += 1
    brow("Chat de Voz Global",
         "Todos os jogadores se ouvem independente da distância.",
         "global_voice_chat",                         adv.global_voice_chat,                         r)
    r += 1
    brow("Chat de Voz por Proximidade",
         "Somente jogadores próximos se ouvem. Tem prioridade sobre o Chat Global.",
         "proximity_chat",                            adv.proximity_chat,                            r)
    r += 1
    brow("Alimentar Dino de Raid",
         "Permite que o Titanossauro (raid dino) seja alimentado.",
         "allow_raid_dino_feeding",                   adv.allow_raid_dino_feeding,                   r)
    r += 1
    frow("Consumo de Comida do Dino de Raid",
         "Taxa de consumo de comida do Titanossauro. Menor = come mais devagar.",
         "raid_dino_character_food_drain_multiplier", adv.raid_dino_character_food_drain_multiplier, r)
    r += 1
    frow("Mult. Velocidade de Nado (Oxigênio)",
         "Multiplica a velocidade de nado baseada no stat de oxigênio.",
         "oxygen_swim_speed_stat_multiplier",         adv.oxygen_swim_speed_stat_multiplier,         r)
    r += 1
    frow("Dano de Coleta dos Dinos",
         "Multiplica o dano que dinos causam ao coletar recursos.",
         "dino_harvesting_damage_multiplier",         adv.dino_harvesting_damage_multiplier,         r)
    r += 1
    frow("Dano de Coleta dos Jogadores",
         "Multiplica o dano que jogadores causam ao coletar recursos.",
         "player_harvesting_damage_multiplier",       adv.player_harvesting_damage_multiplier,       r)
    r += 1
    frow("Habilidade em Receitas Customizadas",
         "Influencia as stats da receita baseado na habilidade do personagem.",
         "custom_recipe_skill_multiplier",            adv.custom_recipe_skill_multiplier,            r)
    r += 1
    frow("Efetividade de Receitas Customizadas",
         "Multiplica os bônus de stats obtidos em receitas customizadas.",
         "custom_recipe_effectiveness_multiplier",    adv.custom_recipe_effectiveness_multiplier,    r)
    r += 1
    brow("PvE Automático com Timer",
         "Alterna automaticamente entre PvP e PvE conforme o horário definido.",
         "b_auto_pve_timer",                          adv.b_auto_pve_timer,                          r)
    r += 1
    brow("PvE Automático usa Hora do Sistema",
         "Usa o horário do servidor (SO) para calcular o timer de PvE automático.",
         "b_auto_pve_use_system_time",                adv.b_auto_pve_use_system_time,                r)
    r += 1
    frow("Início do PvE Automático (s do dia)",
         "Segundo do dia (0–86400) em que o PvE começa. Ex: 0 = meia-noite.",
         "auto_pve_start_time_seconds",               adv.auto_pve_start_time_seconds,               r)
    r += 1
    frow("Fim do PvE Automático (s do dia)",
         "Segundo do dia (0–86400) em que o PvE termina.",
         "auto_pve_stop_time_seconds",                adv.auto_pve_stop_time_seconds,                r)
    r += 1
    brow("Forçar Bloqueio em Estruturas",
         "Todas as estruturas são criadas bloqueadas por padrão.",
         "force_all_structure_locking",               adv.force_all_structure_locking,               r)
    r += 1
    brow("Forçar Explosivos em Voadores",
         "Dinos voadores podem transportar C4 e explosivos em PvP.",
         "force_flyer_explosives",                    adv.force_flyer_explosives,                    r)
    r += 1

    # ── Importar / Sincronizar INI ────────────────────────────────────────
    app._section_lbl(scroll, r + 1, "📂  GameUserSettings.ini / Game.ini")
    r += 2
    ini_card = ctk.CTkFrame(scroll, corner_radius=10, fg_color=_CARD_BG)
    ini_card.grid(row=r, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="ew")
    ini_card.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        ini_card,
        text="Importe as configurações diretamente dos arquivos INI do servidor, "
             "ou copie os INIs para outros servidores do cluster.",
        text_color="gray55", font=ctk.CTkFont(size=10), justify="left",
    ).grid(row=0, column=0, columnspan=2, padx=16, pady=(10, 6), sticky="w")

    btn_row_ini = ctk.CTkFrame(ini_card, fg_color="transparent")
    btn_row_ini.grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 12), sticky="w")

    ctk.CTkButton(
        btn_row_ini,
        text="⬆️  Importar INI do Disco",
        height=36, width=200,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=lambda sid=srv.id: app._import_ini_from_disk(sid),
    ).pack(side="left", padx=(0, 10))

    ctk.CTkButton(
        btn_row_ini,
        text="🔄  Sincronizar INI com Servidores",
        height=36, width=230,
        fg_color="#6a3aaa", hover_color="#7a4abb",
        command=lambda sid=srv.id: app._open_sync_ini_dialog(sid),
    ).pack(side="left")
    r += 1

    app._save_btn_row(scroll, r + 2, srv.id)
