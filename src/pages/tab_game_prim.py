"""Construtor da aba Jogo no modo primitivo (servidor sem TEK mode ativo)."""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..server_config import ServerConfig
from ..ui_constants import _GREEN, _GREEN_DARK, _GREEN_HOVER

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_tab_game_primitive(app: "ARKServerManagerApp", parent, srv: ServerConfig) -> None:
    scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
    scroll.pack(fill="both", expand=True, padx=4, pady=4)
    scroll.grid_columnconfigure(1, weight=1)

    w  = app._server_widgets[srv.id]
    gs = srv.game_settings

    def frow(label: str, hint: str, field: str, val: float, row_n: int,
             frm: float = 0.0, to: float = 10.0) -> None:
        var = tk.DoubleVar(value=val)
        w[f"gs_{field}"] = var

        lbl_fr = ctk.CTkFrame(scroll, fg_color="transparent")
        lbl_fr.grid(row=row_n, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
        ctk.CTkLabel(lbl_fr, text=label, width=290, anchor="w",
                     text_color="gray65",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        if hint:
            ctk.CTkLabel(lbl_fr, text=hint, width=290, anchor="w",
                         text_color="gray40",
                         font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))

        entry_var = tk.StringVar(value=f"{val:.2f}")
        entry = ctk.CTkEntry(scroll, textvariable=entry_var, width=72, height=28,
                             justify="right", text_color=_GREEN,
                             font=ctk.CTkFont(size=12, weight="bold"))
        entry.grid(row=row_n, column=2, padx=(4, 14), pady=4)

        slider = ctk.CTkSlider(
            scroll, from_=int(frm), to=int(to), variable=var,
            command=lambda v, ev=entry_var: ev.set(f"{float(v):.2f}"),
        )
        slider.grid(row=row_n, column=1, padx=4, pady=4, sticky="ew")

        def _commit(event=None, _var=var, _ev=entry_var, _frm=frm, _to=to):
            try:
                v = float(_ev.get().replace(",", "."))
                v = max(_frm, min(_to, v))
                _var.set(v)
                _ev.set(f"{v:.2f}")
            except ValueError:
                _ev.set(f"{_var.get():.2f}")

        entry.bind("<Return>", _commit)
        entry.bind("<FocusOut>", _commit)

    def irow(label: str, hint: str, field: str, val: int, row_n: int) -> None:
        w[f"gs_{field}"] = tk.StringVar(value=str(val))
        lbl_fr = ctk.CTkFrame(scroll, fg_color="transparent")
        lbl_fr.grid(row=row_n, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
        ctk.CTkLabel(lbl_fr, text=label, width=290, anchor="w",
                     text_color="gray65",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        if hint:
            ctk.CTkLabel(lbl_fr, text=hint, width=290, anchor="w",
                         text_color="gray40",
                         font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))
        ctk.CTkEntry(scroll, textvariable=w[f"gs_{field}"], width=120, height=28).grid(
            row=row_n, column=1, padx=4, pady=4, sticky="w")

    def brow(label: str, field: str, val: bool, row_n: int) -> None:
        w[f"gs_{field}"] = tk.BooleanVar(value=val)
        ctk.CTkCheckBox(scroll, text=label, variable=w[f"gs_{field}"],
                        checkmark_color="white", fg_color=_GREEN_DARK,
                        hover_color=_GREEN_HOVER).grid(
            row=row_n, column=0, columnspan=3, padx=16, pady=4, sticky="w")

    r = 0
    app._section_lbl(scroll, r, "⚙️  Dificuldade")
    r += 1
    frow("Nível de Dificuldade",
         "Padrão: 0.20 — Aumentar eleva o nível máximo dos dinos selvagens.",
         "difficulty_offset", gs.difficulty_offset, r, 0, 1)
    r += 1
    frow("Dificuldade Máxima (Override)",
         "Ex: 5.0 = dinos até nível 150. Aumente para dinos mais difíceis.",
         "override_official_difficulty", gs.override_official_difficulty, r, 1, 10)
    r += 1

    app._section_lbl(scroll, r, "📈  XP")
    r += 1
    frow("Multiplicador de XP Geral",
         "Multiplica todo o XP ganho. Aumente para progredir mais rápido.",
         "xp_multiplier", gs.xp_multiplier, r)
    r += 1
    frow("XP por Abate",
         "Multiplica o XP ganho ao matar criaturas.",
         "kill_xp_multiplier", gs.kill_xp_multiplier, r)
    r += 1
    frow("XP por Coleta",
         "Multiplica o XP ganho ao coletar recursos.",
         "harvest_xp_multiplier", gs.harvest_xp_multiplier, r)
    r += 1
    frow("XP por Craft",
         "Multiplica o XP ganho ao fabricar itens.",
         "craft_xp_multiplier", gs.craft_xp_multiplier, r)
    r += 1
    frow("XP Genérico",
         "Multiplica o XP de fontes diversas.",
         "generic_xp_multiplier", gs.generic_xp_multiplier, r)
    r += 1
    frow("XP Especial",
         "Multiplica o XP de eventos e fontes especiais.",
         "special_xp_multiplier", gs.special_xp_multiplier, r)
    r += 1

    app._section_lbl(scroll, r, "👤  Jogador")
    r += 1
    frow("Dano do Jogador",
         "Aumenta o dano causado pelo jogador. Ex: 2.0 = dano dobrado.",
         "player_damage_multiplier", gs.player_damage_multiplier, r)
    r += 1
    frow("Resistência do Jogador",
         "Reduz o dano recebido. Menor = mais resistente ao dano.",
         "player_resistance_multiplier", gs.player_resistance_multiplier, r)
    r += 1
    frow("Consumo de Água",
         "Taxa de consumo de água. Menor = seca mais devagar.",
         "player_character_water_drain_multiplier",
         gs.player_character_water_drain_multiplier, r)
    r += 1
    frow("Consumo de Comida",
         "Taxa de consumo de comida. Menor = fica com fome mais devagar.",
         "player_character_food_drain_multiplier",
         gs.player_character_food_drain_multiplier, r)
    r += 1
    frow("Regeneração de Vida",
         "Velocidade de recuperação de HP. Maior = recupera mais rápido.",
         "player_character_health_recovery_multiplier",
         gs.player_character_health_recovery_multiplier, r)
    r += 1
    frow("Consumo de Stamina",
         "Taxa de consumo de stamina. Menor = cansa mais devagar.",
         "player_character_stamina_drain_multiplier",
         gs.player_character_stamina_drain_multiplier, r)
    r += 1

    app._section_lbl(scroll, r, "🦖  Dinos")
    r += 1
    frow("Dano dos Dinos",
         "Aumenta o dano causado pelos dinos selvagens.",
         "dino_damage_multiplier", gs.dino_damage_multiplier, r)
    r += 1
    frow("Resistência dos Dinos",
         "Reduz o dano recebido pelos dinos. Menor = dinos mais resistentes.",
         "dino_resistance_multiplier", gs.dino_resistance_multiplier, r)
    r += 1
    frow("Regeneração dos Dinos",
         "Velocidade de recuperação de HP dos dinos.",
         "dino_character_health_recovery_multiplier",
         gs.dino_character_health_recovery_multiplier, r)
    r += 1
    frow("Consumo de Comida dos Dinos",
         "Taxa de consumo de comida dos dinos. Menor = comem mais devagar.",
         "dino_character_food_drain_multiplier",
         gs.dino_character_food_drain_multiplier, r)
    r += 1
    frow("Quantidade de Dinos no Mapa",
         "Multiplica a quantidade de dinos. Ex: 2.0 = dobro de dinos selvagens.",
         "dino_count_multiplier", gs.dino_count_multiplier, r)
    r += 1
    irow("Máx. Dinos Domesticados",
         "Limite total de dinos domesticados no servidor.",
         "max_tamed_dinos", gs.max_tamed_dinos, r)
    r += 1

    app._section_lbl(scroll, r, "🥚  Criação / Imprinting")
    r += 1
    frow("Velocidade de Domesticação",
         "Maior = domestica mais rápido. Ex: 3.0 = 3× mais rápido.",
         "taming_speed_multiplier", gs.taming_speed_multiplier, r)
    r += 1
    frow("Intervalo de Acasalamento",
         "Menor = pode acasalar com mais frequência.",
         "mating_interval_multiplier", gs.mating_interval_multiplier, r)
    r += 1
    frow("Velocidade de Chocagem",
         "Maior = ovos chocam mais rápido.",
         "egg_hatch_speed_multiplier", gs.egg_hatch_speed_multiplier, r)
    r += 1
    frow("Intervalo de Postura de Ovos",
         "Menor = dinos põem ovos com mais frequência.",
         "lay_egg_interval_multiplier", gs.lay_egg_interval_multiplier, r)
    r += 1
    frow("Velocidade de Crescimento do Filhote",
         "Maior = filhotes crescem mais rápido.",
         "baby_mature_speed_multiplier", gs.baby_mature_speed_multiplier, r, 0, 100)
    r += 1
    frow("Velocidade de Nascimento do Filhote",
         "Maior = filhotes vivíparos nascem mais rápido.",
         "baby_hatch_speed_multiplier", gs.baby_hatch_speed_multiplier, r, 0, 100)
    r += 1
    frow("Consumo de Comida do Filhote",
         "Menor = filhotes comem menos (mais fácil de criar).",
         "baby_food_consumption_speed_multiplier",
         gs.baby_food_consumption_speed_multiplier, r)
    r += 1
    frow("Intervalo de Carinho (Imprint)",
         "Menor = menos tempo entre os pedidos de carinho do filhote.",
         "baby_cuddle_interval_multiplier", gs.baby_cuddle_interval_multiplier, r)
    r += 1
    frow("Tolerância de Atraso do Imprint",
         "Maior = mais tempo para responder ao pedido de carinho sem perder %.",
         "baby_cuddle_grace_period_multiplier",
         gs.baby_cuddle_grace_period_multiplier, r)
    r += 1
    frow("Bônus de Stats por Imprint",
         "Maior = mais bônus de stats ao completar 100% de imprint.",
         "baby_imprinting_stat_scale_multiplier",
         gs.baby_imprinting_stat_scale_multiplier, r)
    r += 1

    app._section_lbl(scroll, r, "🌾  Coleta / Recursos")
    r += 1
    frow("Quantidade de Coleta",
         "Mais recursos por coleta. Ex: 3.0 = 3× mais recursos.",
         "harvest_amount_multiplier", gs.harvest_amount_multiplier, r)
    r += 1
    frow("Durabilidade dos Recursos",
         "Maior = rochas/árvores duram mais antes de destruir.",
         "harvest_health_multiplier", gs.harvest_health_multiplier, r)
    r += 1
    frow("Reaparecimento de Recursos",
         "Menor = recursos reaparecem mais rápido no mapa.",
         "resource_respawn_period_multiplier",
         gs.resource_respawn_period_multiplier, r)
    r += 1
    frow("Velocidade de Crescimento das Plantas",
         "Maior = plantas nas estufas crescem mais rápido.",
         "crop_growth_speed_multiplier", gs.crop_growth_speed_multiplier, r)
    r += 1
    frow("Apodrecimento das Plantas",
         "Menor = plantas demoram mais para apodrecer.",
         "crop_decay_speed_multiplier", gs.crop_decay_speed_multiplier, r)
    r += 1
    frow("Tamanho de Stack",
         "Multiplica o limite de empilhamento. Ex: 2.0 = stacks dobrados.",
         "item_stack_size_multiplier", gs.item_stack_size_multiplier, r)
    r += 1
    frow("Tempo de Estragamento",
         "Maior = comida demora mais para estragar.",
         "spoiling_time_multiplier", gs.spoiling_time_multiplier, r)
    r += 1
    frow("Tempo de Decomposição de Itens",
         "Maior = itens largados no chão demoram mais para sumir.",
         "item_decomposition_time_multiplier",
         gs.item_decomposition_time_multiplier, r)
    r += 1
    frow("Qualidade de Loot de Pesca",
         "Maior = itens de melhor qualidade ao pescar.",
         "fishing_loot_quality_multiplier", gs.fishing_loot_quality_multiplier, r)
    r += 1

    app._section_lbl(scroll, r, "🏗️  Estruturas")
    r += 1
    frow("Dano às Estruturas",
         "Aumenta o dano causado às estruturas por jogadores/dinos.",
         "structure_damage_multiplier", gs.structure_damage_multiplier, r)
    r += 1
    frow("Resistência das Estruturas",
         "Menor = estruturas mais resistentes (recebem menos dano).",
         "structure_resistance_multiplier", gs.structure_resistance_multiplier, r)
    r += 1
    irow("Cooldown de Reparo (s)",
         "Segundos de espera para reparar após receber dano.",
         "structure_damage_repair_cooldown",
         gs.structure_damage_repair_cooldown, r)
    r += 1
    frow("Decaimento de Estruturas (PvE)",
         "Maior = estruturas sem dono demoram mais para decair.",
         "pve_structure_decay_period_multiplier",
         gs.pve_structure_decay_period_multiplier, r)
    r += 1
    frow("Estruturas em Plataformas",
         "Multiplica o limite de estruturas em platform saddles.",
         "per_platform_max_structures_multiplier",
         gs.per_platform_max_structures_multiplier, r)
    r += 1
    frow("Área de Build em Saddles",
         "Multiplica a área construível ao redor de platform saddles.",
         "platform_saddle_build_area_bounds_multiplier",
         gs.platform_saddle_build_area_bounds_multiplier, r)
    r += 1

    app._section_lbl(scroll, r, "🏆  Tribal / Misc")
    r += 1
    irow("Tamanho Máximo da Tribo",
         "Número máximo de membros por tribo.",
         "max_tribe_size", gs.max_tribe_size, r)
    r += 1
    frow("Tempo para Expulsar AFK (s)",
         "Segundos até expulsar jogadores inativos. 0 = desativado.",
         "kick_idle_players_period", gs.kick_idle_players_period, r, 0, 7200)
    r += 1
    irow("XP Máximo do Jogador (Override)",
         "Substitui o limite padrão de XP dos jogadores.",
         "override_max_experience_points_player",
         gs.override_max_experience_points_player, r)
    r += 1
    irow("XP Máximo do Dino (Override)",
         "Substitui o limite padrão de XP dos dinos.",
         "override_max_experience_points_dino",
         gs.override_max_experience_points_dino, r)
    r += 1

    app._section_lbl(scroll, r, "🎮  Opções do Servidor")
    r += 1
    brow("PvP Ativado",                              "server_pvp",                  gs.server_pvp,                  r)
    r += 1
    brow("Modo Hardcore (morte permanente)",         "server_hardcore",             gs.server_hardcore,             r)
    r += 1
    brow("Dinos Voadores Carregam Jogadores (PvE)",  "allow_flyer_carry_pve",       gs.allow_flyer_carry_pve,       r)
    r += 1
    brow("Terceira Pessoa Permitida",                "allow_third_person_player",   gs.allow_third_person_player,   r)
    r += 1
    brow("Mostrar Localização no Mapa",              "show_map_player_location",    gs.show_map_player_location,    r)
    r += 1
    brow("Desativar Decaimento de Estruturas (PvE)", "disable_structure_decay_pve", gs.disable_structure_decay_pve, r)
    r += 1
    brow("Desativar Decaimento de Dinos (PvE)",      "disable_dino_decay_pve",      gs.disable_dino_decay_pve,      r)
    r += 1
    brow("Proteção Offline (ORP)",                   "prevent_offline_pvp",         gs.prevent_offline_pvp,         r)
    r += 1
    brow("Bloquear Downloads de Tributos",           "no_tribute_downloads",        gs.no_tribute_downloads,        r)
    r += 1
    brow("Notificar quando Jogador Entrar",          "always_notify_player_joined", gs.always_notify_player_joined, r)
    r += 1
    brow("Notificar quando Jogador Sair",            "always_notify_player_left",   gs.always_notify_player_left,   r)
    r += 1

    app._save_btn_row(scroll, r + 1, srv.id)
