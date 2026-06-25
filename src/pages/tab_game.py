from __future__ import annotations

import os
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _GREEN, _GREEN_DARK, _GREEN_HOVER, _CARD_BG
from ..breeding_calculator import open_breeding_calculator
from ..server_config import SERVER_STATUS_STOPPED

import platform
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def build_tab_game(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:  # noqa: C901
    scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
    scroll.pack(fill="both", expand=True, padx=4, pady=4)

    # Referência mutável para o body frame da seção corrente.
    # Atualizado em _dispatch_task quando uma nova seção ("s") é criada.
    _cur_body:    list = [None]  # tk.Frame atual alvo dos widgets
    _sec_start_r: list = [0]    # valor de r da última seção criada + 1

    # Auto-carrega Game.ini do disco antes de popular os widgets,
    # garantindo que PerLevelStatsMultiplier e campos de breeding
    # reflitam o arquivo real caso o JSON tenha apenas defaults.
    if srv.install_dir:
        try:
            from .ark_ini import ArkIniManager as _AIM, get_ini_path as _gip
            _game_ini_path = _gip(srv.install_dir, "Game.ini")
            if _game_ini_path.exists():
                _AIM(srv.install_dir).load_game_ini(srv)
        except Exception:
            pass

    w  = app._server_widgets[srv.id]
    gs = srv.game_settings
    adv = srv.advanced_settings

    def frow(label: str, hint: str, field: str, val: float, row_n: int,
             frm: float = 0.0, to: float = 10.0) -> None:
        app._register_config_item(srv.id, label, hint, "Jogo")
        var = tk.DoubleVar(value=val)
        w[f"gs_{field}"] = var

        _body = _cur_body[0]
        lbl_fr = ctk.CTkFrame(_body, fg_color="transparent")
        lbl_fr.grid(row=row_n, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
        ctk.CTkLabel(lbl_fr, text=label, width=290, anchor="w",
                     text_color="gray65",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        if hint:
            ctk.CTkLabel(lbl_fr, text=hint, width=290, anchor="w",
                         text_color="gray40",
                         font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))

        entry_var = tk.StringVar(value=f"{val:.2f}")
        entry = ctk.CTkEntry(_body, textvariable=entry_var, width=72, height=28,
                             justify="right", text_color=_GREEN,
                             font=ctk.CTkFont(size=12, weight="bold"))
        entry.grid(row=row_n, column=2, padx=(4, 14), pady=4)

        slider = ctk.CTkSlider(
            _body, from_=frm, to=to, variable=var,  # type: ignore[arg-type]
            command=lambda v, ev=entry_var: ev.set(f"{float(v):.2f}"),
        )
        slider.grid(row=row_n, column=1, padx=4, pady=4, sticky="ew")

        def _sync_entry(*_, _v=var, _ev=entry_var):
            _ev.set(f"{_v.get():.2f}")
        var.trace_add("write", _sync_entry)

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
        app._register_config_item(srv.id, label, hint, "Jogo")
        _body = _cur_body[0]
        w[f"gs_{field}"] = tk.StringVar(value=str(val))
        lbl_fr = ctk.CTkFrame(_body, fg_color="transparent")
        lbl_fr.grid(row=row_n, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
        ctk.CTkLabel(lbl_fr, text=label, width=290, anchor="w",
                     text_color="gray65",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        if hint:
            ctk.CTkLabel(lbl_fr, text=hint, width=290, anchor="w",
                         text_color="gray40",
                         font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))
        ctk.CTkEntry(_body, textvariable=w[f"gs_{field}"], width=120, height=28).grid(
            row=row_n, column=1, padx=4, pady=4, sticky="w")

    def brow(label: str, field: str, val: bool, row_n: int) -> None:
        app._register_config_item(srv.id, label, "", "Jogo")
        w[f"gs_{field}"] = tk.BooleanVar(value=val)
        ctk.CTkCheckBox(_cur_body[0], text=label, variable=w[f"gs_{field}"],
                        checkmark_color="white", fg_color=_GREEN_DARK,
                        hover_color=_GREEN_HOVER).grid(
            row=row_n, column=0, columnspan=3, padx=16, pady=4, sticky="w")

    def adv_frow(label: str, hint: str, field: str, val: float, row_n: int,
                 frm: float = 0.0, to: float = 10.0) -> None:
        """Como frow mas registra em w[f'adv_{field}'] (ServerAdvancedSettings)."""
        app._register_config_item(srv.id, label, hint, "Jogo")
        var = tk.DoubleVar(value=val)
        w[f"adv_{field}"] = var
        _body = _cur_body[0]
        lbl_fr = ctk.CTkFrame(_body, fg_color="transparent")
        lbl_fr.grid(row=row_n, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
        ctk.CTkLabel(lbl_fr, text=label, width=290, anchor="w",
                     text_color="gray65",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        if hint:
            ctk.CTkLabel(lbl_fr, text=hint, width=290, anchor="w",
                         text_color="gray40",
                         font=ctk.CTkFont(size=10)).pack(anchor="w", pady=(0, 2))
        entry_var = tk.StringVar(value=f"{val:.2f}")
        entry = ctk.CTkEntry(_body, textvariable=entry_var, width=72, height=28,
                             justify="right", text_color=_GREEN,
                             font=ctk.CTkFont(size=12, weight="bold"))
        entry.grid(row=row_n, column=2, padx=(4, 14), pady=4)
        slider = ctk.CTkSlider(
            _body, from_=frm, to=to, variable=var,
            command=lambda v, ev=entry_var: ev.set(f"{float(v):.2f}"),
        )
        slider.grid(row=row_n, column=1, padx=4, pady=4, sticky="ew")
        def _sync_adv(*_, _v=var, _ev=entry_var):
            _ev.set(f"{_v.get():.2f}")
        var.trace_add("write", _sync_adv)
        def _commit_adv(event=None, _var=var, _ev=entry_var, _frm=frm, _to=to):
            try:
                v = float(_ev.get().replace(",", "."))
                v = max(_frm, min(_to, v))
                _var.set(v)
                _ev.set(f"{v:.2f}")
            except ValueError:
                _ev.set(f"{_var.get():.2f}")
        entry.bind("<Return>", _commit_adv)
        entry.bind("<FocusOut>", _commit_adv)

    def adv_brow(label: str, field: str, val: bool, row_n: int) -> None:
        """Como brow mas registra em w[f'adv_{field}'] (ServerAdvancedSettings)."""
        app._register_config_item(srv.id, label, "", "Jogo")
        w[f"adv_{field}"] = tk.BooleanVar(value=val)
        ctk.CTkCheckBox(_cur_body[0], text=label, variable=w[f"adv_{field}"],
                        checkmark_color="white", fg_color=_GREEN_DARK,
                        hover_color=_GREEN_HOVER).grid(
            row=row_n, column=0, columnspan=3, padx=16, pady=4, sticky="w")

    def _level_cap_row(label: str, hint: str, field: str, val: int, row_n: int) -> None:
        from ..ark_ini import _level_to_xp as _l2xp
        _body = _cur_body[0]
        app._register_config_item(srv.id, label, hint, "Jogo")
        w[f"gs_{field}"] = tk.StringVar(value=str(val))
        lbl_fr = ctk.CTkFrame(_body, fg_color="transparent")
        lbl_fr.grid(row=row_n, column=0, padx=(16, 6), pady=(4, 0), sticky="w")
        ctk.CTkLabel(lbl_fr, text=label, width=290, anchor="w",
                     text_color="gray65",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(lbl_fr, text=hint, width=290, anchor="w",
                     text_color="gray40",
                     font=ctk.CTkFont(size=10), justify="left",
                     wraplength=270).pack(anchor="w", pady=(0, 2))
        right_fr = ctk.CTkFrame(_body, fg_color="transparent")
        right_fr.grid(row=row_n, column=1, padx=4, pady=4, sticky="w")
        ctk.CTkEntry(right_fr, textvariable=w[f"gs_{field}"],
                     width=80, height=28).pack(side="left")
        xp_lbl = ctk.CTkLabel(right_fr, text="", text_color="gray45",
                              font=ctk.CTkFont(size=10))
        xp_lbl.pack(side="left", padx=(6, 0))

        def _update_xp_preview(*_):
            try:
                lvl = int(w[f"gs_{field}"].get())
                xp_lbl.configure(text="(padrão ARK)" if lvl <= 0 else f"→ {_l2xp(lvl):,} XP")
            except (ValueError, TypeError):
                xp_lbl.configure(text="")

        w[f"gs_{field}"].trace_add("write", _update_xp_preview)
        _update_xp_preview()

    # ── Coleta de tasks com row pré-calculado ─────────────────────────────
    # Em vez de criar todos os ~350 widgets de uma vez (freeze de ~500ms),
    # as tasks são despachadas em lotes de 6 via after(0), cedendo o
    # controle ao event loop entre cada lote.
    _tasks: list = []
    r = 0

    def _s(text: str) -> None:
        nonlocal r
        _tasks.append(("s", r, text))
        r += 1

    def _f(label, hint, field, val, frm=0.0, to=10.0) -> None:
        nonlocal r
        _tasks.append(("f", r, label, hint, field, val, frm, to))
        r += 1

    def _i(label, hint, field, val) -> None:
        nonlocal r
        _tasks.append(("i", r, label, hint, field, val))
        r += 1

    def _b(label, field, val) -> None:
        nonlocal r
        _tasks.append(("b", r, label, field, val))
        r += 1

    def _af(label, hint, field, val, frm=0.0, to=10.0) -> None:
        nonlocal r
        _tasks.append(("adv_f", r, label, hint, field, val, frm, to))
        r += 1

    def _ab(label, field, val) -> None:
        nonlocal r
        _tasks.append(("adv_b", r, label, field, val))
        r += 1

    def _calc() -> None:
        nonlocal r
        _tasks.append(("calc", r))
        r += 1

    def _lcap(label, hint, field, val) -> None:
        nonlocal r
        _tasks.append(("lcap", r, label, hint, field, val))
        r += 1

    def _ascend_calc() -> None:
        nonlocal r
        _tasks.append(("ascend_calc", r))
        r += 1

    def _save() -> None:
        _tasks.append(("save", r + 1))

    def _plsm() -> None:
        nonlocal r
        _tasks.append(("plsm", r))
        r += 1

    # ── Definição das rows ────────────────────────────────────────────────
    _s("⚙️  Dificuldade")
    _f("Nível de Dificuldade",
       "Padrão: 0.20 — Aumentar eleva o nível máximo dos dinos selvagens.",
       "difficulty_offset", gs.difficulty_offset, 0, 1)
    _f("Dificuldade Máxima (Override)",
       "Ex: 5.0 = dinos até nível 150. Aumente para dinos mais difíceis.",
       "override_official_difficulty", gs.override_official_difficulty, 1, 10)

    _s("📈  XP")
    _f("Multiplicador de XP Geral",
       "Multiplica todo o XP ganho. Aumente para progredir mais rápido.",
       "xp_multiplier", gs.xp_multiplier)
    _f("XP por Abate",
       "Multiplica o XP ganho ao matar criaturas.",
       "kill_xp_multiplier", gs.kill_xp_multiplier)
    _f("XP por Coleta",
       "Multiplica o XP ganho ao coletar recursos.",
       "harvest_xp_multiplier", gs.harvest_xp_multiplier)
    _f("XP por Craft",
       "Multiplica o XP ganho ao fabricar itens.",
       "craft_xp_multiplier", gs.craft_xp_multiplier)
    _f("XP Genérico",
       "Multiplica o XP de fontes diversas.",
       "generic_xp_multiplier", gs.generic_xp_multiplier)
    _f("XP Especial",
       "Multiplica o XP de eventos e fontes especiais.",
       "special_xp_multiplier", gs.special_xp_multiplier)

    _s("👤  Jogador")
    _f("Dano do Jogador",
       "Aumenta o dano causado pelo jogador. Ex: 2.0 = dano dobrado.",
       "player_damage_multiplier", gs.player_damage_multiplier)
    _f("Resistência do Jogador",
       "Reduz o dano recebido. Menor = mais resistente ao dano.",
       "player_resistance_multiplier", gs.player_resistance_multiplier)
    _f("Consumo de Água",
       "Taxa de consumo de água. Menor = seca mais devagar.",
       "player_character_water_drain_multiplier",
       gs.player_character_water_drain_multiplier)
    _f("Consumo de Comida",
       "Taxa de consumo de comida. Menor = fica com fome mais devagar.",
       "player_character_food_drain_multiplier",
       gs.player_character_food_drain_multiplier)
    _f("Regeneração de Vida",
       "Velocidade de recuperação de HP. Maior = recupera mais rápido.",
       "player_character_health_recovery_multiplier",
       gs.player_character_health_recovery_multiplier)
    _f("Consumo de Stamina",
       "Taxa de consumo de stamina. Menor = cansa mais devagar.",
       "player_character_stamina_drain_multiplier",
       gs.player_character_stamina_drain_multiplier)

    _s("🦖  Dinos")
    _f("Dano dos Dinos",
       "Aumenta o dano causado pelos dinos selvagens.",
       "dino_damage_multiplier", gs.dino_damage_multiplier)
    _f("Resistência dos Dinos",
       "Reduz o dano recebido pelos dinos. Menor = dinos mais resistentes.",
       "dino_resistance_multiplier", gs.dino_resistance_multiplier)
    _f("Regeneração dos Dinos",
       "Velocidade de recuperação de HP dos dinos.",
       "dino_character_health_recovery_multiplier",
       gs.dino_character_health_recovery_multiplier)
    _f("Consumo de Comida dos Dinos (GUS)",
       "Taxa de consumo de comida dos dinos (GameUserSettings). Menor = comem mais devagar.",
       "dino_character_food_drain_multiplier",
       gs.dino_character_food_drain_multiplier)
    _f("Consumo de Stamina dos Dinos",
       "Taxa de consumo de stamina dos dinos. Menor = cansam mais devagar.",
       "dino_character_stamina_drain_multiplier",
       gs.dino_character_stamina_drain_multiplier)
    _f("Dano dos Dinos Domesticados",
       "Multiplica o dano causado pelos dinos domesticados.",
       "tamed_dino_damage_multiplier", gs.tamed_dino_damage_multiplier)
    _f("Resistência dos Dinos Domesticados",
       "Reduz o dano recebido pelos dinos domesticados. Menor = mais resistentes.",
       "tamed_dino_resistance_multiplier", gs.tamed_dino_resistance_multiplier)
    _f("Dano de Torretas Montadas em Dino",
       "Multiplica o dano das torretas fixadas em dinos.",
       "dino_turret_damage_multiplier", gs.dino_turret_damage_multiplier)
    _f("Quantidade de Dinos no Mapa",
       "Multiplica a quantidade de dinos. Ex: 2.0 = dobro de dinos selvagens.",
       "dino_count_multiplier", gs.dino_count_multiplier)
    _i("Máx. Dinos Domesticados (Global)",
       "Limite total de dinos domesticados no servidor.",
       "max_tamed_dinos", gs.max_tamed_dinos)
    _f("Máx. Dinos Domesticados por Jogador",
       "Limite individual de dinos por jogador (0 = ilimitado pelo slot de sela).",
       "max_personal_tamed_dinos", gs.max_personal_tamed_dinos, 0, 500)
    _i("Custo em Estruturas por Sela de Plataforma",
       "Penalidade de limite de tame por cada sela de plataforma colocada no mapa.",
       "personal_tamed_dinos_saddle_structure_cost",
       gs.personal_tamed_dinos_saddle_structure_cost)

    _s("📊  Stats por Nível")
    _plsm()

    _s("🥚  Criação / Imprinting")
    _calc()
    _f("Velocidade de Domesticação",
       "Maior = domestica mais rápido. Ex: 3.0 = 3× mais rápido.",
       "taming_speed_multiplier", gs.taming_speed_multiplier)
    _f("Intervalo de Acasalamento",
       "Menor = pode acasalar com mais frequência.",
       "mating_interval_multiplier", gs.mating_interval_multiplier)
    _f("Velocidade de Chocagem",
       "Maior = ovos chocam mais rápido.",
       "egg_hatch_speed_multiplier", gs.egg_hatch_speed_multiplier)
    _f("Intervalo de Postura de Ovos",
       "Menor = dinos põem ovos com mais frequência.",
       "lay_egg_interval_multiplier", gs.lay_egg_interval_multiplier)
    _f("Velocidade de Crescimento do Filhote",
       "Maior = filhotes crescem mais rápido.",
       "baby_mature_speed_multiplier", gs.baby_mature_speed_multiplier, 0, 100)
    _f("Velocidade de Nascimento do Filhote",
       "Maior = filhotes vivíparos nascem mais rápido.",
       "baby_hatch_speed_multiplier", gs.baby_hatch_speed_multiplier, 0, 100)
    _f("Consumo de Comida do Filhote",
       "Menor = filhotes comem menos (mais fácil de criar).",
       "baby_food_consumption_speed_multiplier",
       gs.baby_food_consumption_speed_multiplier)
    _f("Intervalo de Carinho (Imprint)",
       "Menor = menos tempo entre os pedidos de carinho do filhote.",
       "baby_cuddle_interval_multiplier", gs.baby_cuddle_interval_multiplier)
    _f("Tolerância de Atraso do Imprint",
       "Maior = mais tempo para responder ao pedido de carinho sem perder %.",
       "baby_cuddle_grace_period_multiplier",
       gs.baby_cuddle_grace_period_multiplier)
    _f("Bônus de Stats por Imprint",
       "Maior = mais bônus de stats ao completar 100% de imprint.",
       "baby_imprinting_stat_scale_multiplier",
       gs.baby_imprinting_stat_scale_multiplier)
    _af("Velocidade de Perda do Imprint",
        "Maior = o imprint perde qualidade mais rápido quando o pedido é ignorado.",
        "baby_cuddle_lose_imprint_quality_speed_multiplier",
        adv.baby_cuddle_lose_imprint_quality_speed_multiplier)
    _b("Desativar Bônus de Stats do Imprint",
       "disable_imprint_dino_buff", gs.disable_imprint_dino_buff)
    _b("Qualquer Jogador Pode Fazer Imprint",
       "allow_anyone_baby_imprint_cuddle", gs.allow_anyone_baby_imprint_cuddle)
    _b("Desativar Mate Boost (+33% stats ao lado do par)",
       "prevent_mate_boost", gs.prevent_mate_boost)
    _b("Voadores Recuperam Stamina em Voo",
       "allow_flying_stamina_recovery", gs.allow_flying_stamina_recovery)
    _ab("Upar Velocidade em Voadores (Game.ini)",
        "allow_flyer_speed_leveling", adv.allow_flyer_speed_leveling)
    _af("Intervalo de Domesticação Passiva",
        "Multiplicador do intervalo de domesticação passiva (comedouros). Menor = domestica mais rápido.",
        "passive_tame_interval_multiplier",
        adv.passive_tame_interval_multiplier)
    _af("Consumo de Comida — Dino Selvagem [Game.ini]",
        "Taxa de consumo de comida de dinos selvagens (Game.ini). Menor = esvaziam mais devagar.",
        "wild_dino_character_food_drain_multiplier",
        adv.wild_dino_character_food_drain_multiplier)
    _af("Consumo de Comida — Dino Domesticado [Game.ini]",
        "Taxa de consumo de comida de dinos domesticados (Game.ini). Complementa o campo GUS.",
        "tamed_dino_character_food_drain_multiplier",
        adv.tamed_dino_character_food_drain_multiplier)
    _af("Recuperação de Torpor — Selvagem",
        "Velocidade de recuperação de torpor de dinos selvagens. Menor = ficam dopados por mais tempo.",
        "wild_dino_torpor_drain_multiplier",
        adv.wild_dino_torpor_drain_multiplier)
    _af("Recuperação de Torpor — Domesticado",
        "Velocidade de recuperação de torpor de dinos domesticados.",
        "tamed_dino_torpor_drain_multiplier",
        adv.tamed_dino_torpor_drain_multiplier)

    _s("🌾  Coleta / Recursos")
    _f("Quantidade de Coleta",
       "Mais recursos por coleta. Ex: 3.0 = 3× mais recursos.",
       "harvest_amount_multiplier", gs.harvest_amount_multiplier)
    _f("Durabilidade dos Recursos",
       "Maior = rochas/árvores duram mais antes de destruir.",
       "harvest_health_multiplier", gs.harvest_health_multiplier)
    _f("Reaparecimento de Recursos",
       "Menor = recursos reaparecem mais rápido no mapa.",
       "resource_respawn_period_multiplier",
       gs.resource_respawn_period_multiplier)
    _f("Velocidade de Crescimento das Plantas",
       "Maior = plantas nas estufas crescem mais rápido.",
       "crop_growth_speed_multiplier", gs.crop_growth_speed_multiplier)
    _f("Apodrecimento das Plantas",
       "Menor = plantas demoram mais para apodrecer.",
       "crop_decay_speed_multiplier", gs.crop_decay_speed_multiplier)
    _f("Tamanho de Stack",
       "Multiplica o limite de empilhamento. Ex: 2.0 = stacks dobrados.",
       "item_stack_size_multiplier", gs.item_stack_size_multiplier)
    _f("Tempo de Estragamento",
       "Maior = comida demora mais para estragar.",
       "spoiling_time_multiplier", gs.spoiling_time_multiplier)
    _f("Tempo de Decomposição de Itens",
       "Maior = itens largados no chão demoram mais para sumir.",
       "item_decomposition_time_multiplier",
       gs.item_decomposition_time_multiplier)
    _f("Qualidade de Loot de Pesca",
       "Maior = itens de melhor qualidade ao pescar.",
       "fishing_loot_quality_multiplier", gs.fishing_loot_quality_multiplier)

    _s("🏗️  Estruturas")
    _f("Dano às Estruturas",
       "Aumenta o dano causado às estruturas por jogadores/dinos.",
       "structure_damage_multiplier", gs.structure_damage_multiplier)
    _f("Resistência das Estruturas",
       "Menor = estruturas mais resistentes (recebem menos dano).",
       "structure_resistance_multiplier", gs.structure_resistance_multiplier)
    _i("Cooldown de Reparo (s)",
       "Segundos de espera para reparar após receber dano.",
       "structure_damage_repair_cooldown",
       gs.structure_damage_repair_cooldown)
    _f("Decaimento de Estruturas (PvE)",
       "Maior = estruturas sem dono demoram mais para decair.",
       "pve_structure_decay_period_multiplier",
       gs.pve_structure_decay_period_multiplier)
    _f("Estruturas em Plataformas",
       "Multiplica o limite de estruturas em platform saddles.",
       "per_platform_max_structures_multiplier",
       gs.per_platform_max_structures_multiplier)
    _f("Área de Build em Saddles",
       "Multiplica a área construível ao redor de platform saddles.",
       "platform_saddle_build_area_bounds_multiplier",
       gs.platform_saddle_build_area_bounds_multiplier)

    _s("🏆  Tribal / Misc")
    _i("Tamanho Máximo da Tribo",
       "Número máximo de membros por tribo.",
       "max_tribe_size", gs.max_tribe_size)
    _f("Tempo para Expulsar AFK (s)",
       "Segundos até expulsar jogadores inativos. 0 = desativado.",
       "kick_idle_players_period", gs.kick_idle_players_period, 0, 7200)
    _f("Cooldown para Renomear Tribo (s)",
       "Segundos que uma tribo deve esperar antes de poder renomear novamente. 0 = sem cooldown.",
       "tribe_name_change_cooldown", gs.tribe_name_change_cooldown, 0, 86400)
    _b("Permitir Alianças entre Tribos",
       "allow_tribe_alliances", gs.allow_tribe_alliances)

    _s("🔢  Teto de Níveis")
    _i("XP Máximo do Jogador (Override)",
       "Substitui o valor de XP máximo acumulável pelo jogador. 0 = padrão ARK.",
       "override_max_experience_points_player", gs.override_max_experience_points_player)
    _i("XP Máximo do Dino (Override)",
       "Substitui o valor de XP máximo acumulável por dinos domesticados. 0 = padrão ARK.",
       "override_max_experience_points_dino", gs.override_max_experience_points_dino)
    _lcap("Nível Máximo do Jogador",
          "Nível final do jogador, incluindo os desbloqueados por ascensões."
          " 0 = padrão ARK (105 base + ascensões).",
          "player_level_cap", gs.player_level_cap)
    _lcap("Nível Máximo do Dino",
          "Nível máximo que dinos podem atingir ao acumular XP."
          " 0 = padrão ARK.",
          "dino_level_cap", gs.dino_level_cap)
    _ascend_calc()

    _s("🎮  Opções do Servidor")
    _b("PvP Ativado",                              "server_pvp",                  gs.server_pvp)
    _b("Modo Hardcore (morte permanente)",         "server_hardcore",             gs.server_hardcore)
    _b("Dinos Voadores Carregam Jogadores (PvE)",  "allow_flyer_carry_pve",       gs.allow_flyer_carry_pve)
    _b("Terceira Pessoa Permitida",                "allow_third_person_player",   gs.allow_third_person_player)
    _b("Mostrar Localização no Mapa",              "show_map_player_location",    gs.show_map_player_location)
    _b("Desativar Decaimento de Estruturas (PvE)", "disable_structure_decay_pve", gs.disable_structure_decay_pve)
    _b("Desativar Decaimento de Dinos (PvE)",      "disable_dino_decay_pve",      gs.disable_dino_decay_pve)
    _b("Desativar Decaimento de Dinos (PvP)",      "disable_dino_decay_pvp",      gs.disable_dino_decay_pvp)
    _b("Auto-destruir Dinos Decaídos",             "auto_destroy_decayed_dinos",  gs.auto_destroy_decayed_dinos)
    _f("Multiplicador de Decaimento de Dinos (PvE)",
       "Multiplica o tempo para dinos sem dono decaírem em PvE.",
       "pve_dino_decay_period_multiplier", gs.pve_dino_decay_period_multiplier)
    _b("Proteção Offline (ORP)",                         "prevent_offline_pvp",                   gs.prevent_offline_pvp)
    _f("Intervalo da Proteção Offline (s)",
       "Tempo em segundos que o jogador fica invulnerável após desconectar com ORP ativo. 0 = imediato.",
       "prevent_offline_pvp_interval", gs.prevent_offline_pvp_interval, 0, 3600)
    _b("Bloquear Downloads de Tributos",                 "no_tribute_downloads",                  gs.no_tribute_downloads)
    _b("Notificar quando Jogador Entrar",                "always_notify_player_joined",           gs.always_notify_player_joined)
    _b("Notificar quando Jogador Sair",                  "always_notify_player_left",             gs.always_notify_player_left)
    _b("Suprimir Notif. de Entrada (duplicado)",         "dont_always_notify_player_joined",      gs.dont_always_notify_player_joined)
    _b("PvP — Desativar Canto (Gamma)",                  "allow_pvp_gamma",                       gs.allow_pvp_gamma)
    _b("PvE — Desativar Canto (Gamma)",                  "allow_pve_gamma",                       gs.allow_pve_gamma)
    _b("Mostrar Marcadores de Dano (Hit Markers)",       "allow_hit_markers",                     gs.allow_hit_markers)
    _b("Permitir Múltiplos C4 por Dino",                 "allow_multiple_attached_c4",            gs.allow_multiple_attached_c4)
    _b("Construção em Cavernas (PvE)",                   "allow_cave_building_pve",               gs.allow_cave_building_pve)
    _b("Estruturas sobre Supply Drops (PvE)",            "pve_allow_structures_at_supply_drops",  gs.pve_allow_structures_at_supply_drops)
    _b("Volume Extra de Prevenção de Estruturas",        "enable_extra_structure_prevention_volumes", gs.enable_extra_structure_prevention_volumes)
    _b("Limitar Dano de Coleta de Recursos",             "clamp_resource_harvest_damage",         gs.clamp_resource_harvest_damage)
    _b("Decaimento de Estruturas (PvP)",                 "pvp_structure_decay",                   gs.pvp_structure_decay)
    _b("Ignorar Prevenção de Plataforma (Override)",     "override_structure_platform_prevention",gs.override_structure_platform_prevention)
    _b("Doenças Habilitadas",                            "enable_diseases",                       gs.enable_diseases)
    _b("Doenças Não Permanentes",                        "non_permanent_diseases",                gs.non_permanent_diseases)
    _b("Clima — Desativar Névoa",                        "disable_weather_fog",                   gs.disable_weather_fog)

    _s("🏗️  Estruturas")
    _b("Permitir Recolher Estruturas",
       "always_allow_structure_pickup", gs.always_allow_structure_pickup)
    _i("Máx. Estruturas Visíveis",
       "Número máximo de estruturas dentro do raio de renderização. Padrão ARK: 10500.",
       "max_structures_visible", gs.max_structures_visible)
    _i("Máx. Estruturas em Selas de Plataforma",
       "Limite global de estruturas em todas as selas de plataforma do servidor. Padrão: 130.",
       "max_platform_saddle_structure_limit", gs.max_platform_saddle_structure_limit)
    _f("Multiplicador de Auto-destruição de Estruturas",
       "Multiplica a velocidade de auto-destruição de estruturas antigas. 0 = desativado.",
       "auto_destroy_old_structures_multiplier", gs.auto_destroy_old_structures_multiplier, 0, 10)
    _f("Período de Destruição de Decay (PvE)",
       "Multiplicador do período que estruturas decaídas ficam antes de serem destruídas (PvE).",
       "pve_structure_decay_destruction_period", gs.pve_structure_decay_destruction_period, 0, 10)
    _b("Destruir Estruturas Núcleo Desconectadas Rapidamente",
       "fast_decay_unsnapped_core_structures", gs.fast_decay_unsnapped_core_structures)
    _b("Auto-destruição Somente em Estruturas Núcleo",
       "only_auto_destroy_core_structures", gs.only_auto_destroy_core_structures)
    _b("Decay Somente em Estruturas Núcleo Desconectadas",
       "only_decay_unsnapped_core_structures", gs.only_decay_unsnapped_core_structures)
    _b("Destruir Canos d'Água Desconectados",
       "destroy_unconnected_water_pipes", gs.destroy_unconnected_water_pipes)

    _s("🌅  Ciclo Dia / Noite")
    _f("Velocidade do Ciclo Dia/Noite",
       "Multiplica a velocidade completa do ciclo. 1.0 = padrão. 2.0 = dia/noite duas vezes mais rápidos.",
       "day_cycle_speed_scale", gs.day_cycle_speed_scale, 0.1, 5.0)
    _f("Velocidade do Período Diurno",
       "Multiplica exclusivamente a duração do dia. 1.0 = padrão.",
       "day_time_speed_scale", gs.day_time_speed_scale, 0.1, 5.0)
    _f("Velocidade do Período Noturno",
       "Multiplica exclusivamente a duração da noite. 1.0 = padrão.",
       "night_time_speed_scale", gs.night_time_speed_scale, 0.1, 5.0)

    _s("📡  NPC Network Stasis")
    _b("Ativar Escala de Stasis Dinâmica (NPC)",
       "override_npc_network_stasis_range_scale", gs.override_npc_network_stasis_range_scale)
    _i("Contagem de Jogadores — Início da Escala",
       "Número de jogadores online a partir do qual a escala de stasis começa a ser aplicada.",
       "npc_network_stasis_range_scale_player_count_start",
       gs.npc_network_stasis_range_scale_player_count_start)
    _i("Contagem de Jogadores — Fim da Escala",
       "Número de jogadores online em que a escala de stasis atinge o valor mínimo definido.",
       "npc_network_stasis_range_scale_player_count_end",
       gs.npc_network_stasis_range_scale_player_count_end)
    _f("Percentual Mínimo do Raio de Stasis",
       "Fração do raio original de stasis aplicada quando o servidor está cheio. Ex: 0.5 = 50%.",
       "npc_network_stasis_range_scale_percent_end",
       gs.npc_network_stasis_range_scale_percent_end, 0.01, 1.0)
    _save()

    # ── Despacho em chunks via after(0) ───────────────────────────────────
    # Lotes de 6 tasks — cada after(0) cede o controle ao event loop antes
    # do próximo lote, eliminando o freeze de ~500ms que 44 CTkSliders causavam.
    _CHUNK = 6

    def _build_ascension_panel(row_n: int) -> None:
        """Painel informativo de níveis base e calculadora de ascensões."""
        _BG_PANEL = "#12122a"
        _BDR      = "#2a2a55"
        panel = tk.Frame(_cur_body[0], bg=_BG_PANEL, highlightthickness=1,
                         highlightbackground=_BDR)
        panel.grid(row=row_n, column=0, columnspan=3,
                   padx=16, pady=(2, 10), sticky="ew")
        panel.columnconfigure(0, weight=1)

        # Cabeçalho
        tk.Label(panel, text="📊  Referência de Níveis Vanilla (ARK oficial)",
                 bg=_BG_PANEL, fg="#c8c8e8",
                 font=ctk.CTkFont(size=12, weight="bold"),
                 anchor="w").grid(row=0, column=0, padx=12, pady=(8, 2), sticky="w")
        tk.Frame(panel, bg=_GREEN, height=1).grid(
            row=1, column=0, padx=12, sticky="ew")

        # Info estática
        info = tk.Frame(panel, bg=_BG_PANEL)
        info.grid(row=2, column=0, padx=12, pady=(6, 4), sticky="w")
        _HINT = "gray50"
        tk.Label(info, text="Nível base do jogador (sem ascensões):",
                 bg=_BG_PANEL, fg=_HINT,
                 font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w", padx=(0, 8))
        tk.Label(info, text="105", bg=_BG_PANEL, fg=_GREEN,
                 font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=1, sticky="w")
        tk.Label(info, text="Nível máximo de dino selvagem (Dificuldade 5.0):",
                 bg=_BG_PANEL, fg=_HINT,
                 font=ctk.CTkFont(size=11)).grid(row=1, column=0, sticky="w", padx=(0, 8))
        tk.Label(info, text="150", bg=_BG_PANEL, fg=_GREEN,
                 font=ctk.CTkFont(size=11, weight="bold")).grid(row=1, column=1, sticky="w")

        # Divisor
        tk.Frame(panel, bg="#1e1e3a", height=1).grid(
            row=3, column=0, padx=12, sticky="ew", pady=(4, 2))

        # Título calculadora
        tk.Label(panel, text="🧮  Calculadora de Ascensões do Jogador",
                 bg=_BG_PANEL, fg="#c8c8e8",
                 font=ctk.CTkFont(size=11, weight="bold"),
                 anchor="w").grid(row=4, column=0, padx=12, pady=(4, 2), sticky="w")
        tk.Label(panel,
                 text="Selecione as ascensões completadas para ver o nível máximo final:",
                 bg=_BG_PANEL, fg=_HINT,
                 font=ctk.CTkFont(size=10)).grid(row=5, column=0, padx=12,
                                                  pady=(0, 6), sticky="w")

        # Ascensões disponíveis:  (nome, níveis concedidos por tier)
        # Tier α/β/γ — usa o maior tier selecionado (são mutuamente exclusivos por mapa)
        # Mapas com tiers γ/β/α — cada um concede +5/+10/+15 níveis (cumulativo: usa o maior)
        _TIERED = [
            # (nome,               γ,  β,  α,  hint)
            ("The Island",         5, 10, 15, "Overseer — The Island (cavernas γ/β/α)"),
            ("Scorched Earth",     5, 10, 15, "Manticore — Scorched Earth (γ/β/α)"),
            ("Aberration",         5, 10, 15, "Rockwell — Aberration (γ/β/α)"),
            ("Extinction",         5, 10, 15, "King Titan — Extinction (γ/β/α)"),
            ("Genesis: Part 1",    5, 10, 15, "Corrupted Master Controller (γ/β/α)"),
            ("Genesis: Part 2",    5, 10, 15, "Rockwell Prime — Genesis Part 2 (γ/β/α)"),
        ]
        # DLCs com tier único (sem γ/β — somente α)
        _SINGLE = [
            ("Aquatica (α)", 5, "DLC — Mapa Aquatica (conta na soma oficial)"),
        ]
        _EXTRA = [
            ("Chibis",             5, "Coletar chibis dourados no Fear Evolved / Winter Wonderland"),
            ("Notas de Explorador (todas)", 10, "Completar todas as notas de explorador (todas as Story ARKs)"),
            ("Runas de Hjemskr",   5, "Runas de Fjordur"),
        ]

        chk_vars: list[tk.BooleanVar] = []

        chk_fr = tk.Frame(panel, bg=_BG_PANEL)
        chk_fr.grid(row=6, column=0, padx=12, pady=(0, 4), sticky="ew")
        chk_fr.columnconfigure((0, 1, 2), weight=1)

        tier_vars: dict[str, list[tk.BooleanVar]] = {}  # name → [γ, β, α]

        _col = 0
        _row_chk = 0

        def _add_chk(parent_fr, label: str, hint: str, var: tk.BooleanVar,
                     result_var: tk.IntVar, levels: int, c: int, rw: int) -> None:
            fr = tk.Frame(parent_fr, bg=_BG_PANEL)
            fr.grid(row=rw, column=c, padx=4, pady=2, sticky="w")
            ctk.CTkCheckBox(fr, text=label, variable=var, width=20,
                            checkmark_color="white", fg_color=_GREEN_DARK,
                            hover_color=_GREEN_HOVER,
                            command=lambda: _recalc(result_var)).pack(side="left")
            tk.Label(fr, text=f"+{levels}", bg=_BG_PANEL, fg=_GREEN,
                     font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=(4, 0))
            if hint:
                tk.Label(fr, text=f"  {hint}", bg=_BG_PANEL, fg=_HINT,
                         font=ctk.CTkFont(size=9)).pack(side="left")

        result_var = tk.IntVar(value=105)

        def _recalc(rv: tk.IntVar) -> None:
            total = 105
            # single checkboxes
            for sv, lvls in zip(chk_vars, [t[1] for t in _SINGLE]):
                if sv.get():
                    total += lvls
            # tiered: pick highest tier selected per map
            for name, tv_list in tier_vars.items():
                best = 0
                for tier_idx, (tv, bonus) in enumerate(zip(tv_list, [5, 10, 15])):
                    if tv.get():
                        best = max(best, bonus)
                total += best
            # extras
            for sv, lvls in zip(extra_vars, [e[1] for e in _EXTRA]):
                if sv.get():
                    total += lvls
            rv.set(total)

        extra_vars: list[tk.BooleanVar] = []

        # Seção: mapas com tier
        tier_sec = tk.LabelFrame(chk_fr, text="  Mapas com Tiers γ/β/α (boss caves)  ",
                                  bg=_BG_PANEL, fg="gray60",
                                  font=ctk.CTkFont(size=10))
        tier_sec.grid(row=0, column=0, columnspan=3, padx=2, pady=(0, 6), sticky="ew")
        for col_idx in range(4):
            tier_sec.columnconfigure(col_idx, weight=1)

        for t_idx, (tname, g_b, b_b, a_b, t_hint) in enumerate(_TIERED):
            tier_row = tk.Frame(tier_sec, bg=_BG_PANEL)
            tier_row.grid(row=t_idx, column=0, columnspan=4,
                          padx=4, pady=1, sticky="w")
            tk.Label(tier_row, text=tname, width=16, anchor="w",
                     bg=_BG_PANEL, fg="gray70",
                     font=ctk.CTkFont(size=10)).pack(side="left", padx=(2, 8))
            tvs = []
            for tier_lbl, tier_bonus in [("γ", g_b), ("β", b_b), ("α", a_b)]:
                tv = tk.BooleanVar(value=False)
                tvs.append(tv)
                ctk.CTkCheckBox(tier_row, text=f"{tier_lbl} +{tier_bonus}", variable=tv,
                                width=20, fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                                checkmark_color="white",
                                command=lambda: _recalc(result_var)).pack(
                    side="left", padx=6)
            tier_vars[tname] = tvs

        # Seção: mapas de expansão (single tier)
        exp_sec = tk.LabelFrame(chk_fr, text="  DLCs (+5 cada)  ",
                                 bg=_BG_PANEL, fg="gray60",
                                 font=ctk.CTkFont(size=10))
        exp_sec.grid(row=1, column=0, columnspan=3, padx=2, pady=(0, 6), sticky="ew")
        for ci in range(3):
            exp_sec.columnconfigure(ci, weight=1)

        for s_idx, (s_name, s_lvls, s_hint) in enumerate(_SINGLE):
            sv = tk.BooleanVar(value=False)
            chk_vars.append(sv)
            fr = tk.Frame(exp_sec, bg=_BG_PANEL)
            fr.grid(row=s_idx // 3, column=s_idx % 3, padx=4, pady=2, sticky="w")
            ctk.CTkCheckBox(fr, text=s_name, variable=sv, width=20,
                            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                            checkmark_color="white",
                            command=lambda: _recalc(result_var)).pack(side="left")
            tk.Label(fr, text=f"+{s_lvls}", bg=_BG_PANEL, fg=_GREEN,
                     font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=(4, 0))

        # Seção: extras
        ext_sec = tk.LabelFrame(chk_fr, text="  Extras (Chibis, Notas, Runas)  ",
                                 bg=_BG_PANEL, fg="gray60",
                                 font=ctk.CTkFont(size=10))
        ext_sec.grid(row=2, column=0, columnspan=3, padx=2, pady=(0, 8), sticky="ew")
        for ci in range(3):
            ext_sec.columnconfigure(ci, weight=1)

        for e_idx, (e_name, e_lvls, e_hint) in enumerate(_EXTRA):
            ev = tk.BooleanVar(value=False)
            extra_vars.append(ev)
            fr = tk.Frame(ext_sec, bg=_BG_PANEL)
            fr.grid(row=e_idx // 3, column=e_idx % 3, padx=4, pady=2, sticky="w")
            ctk.CTkCheckBox(fr, text=e_name, variable=ev, width=20,
                            fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                            checkmark_color="white",
                            command=lambda: _recalc(result_var)).pack(side="left")
            tk.Label(fr, text=f"+{e_lvls}", bg=_BG_PANEL, fg=_GREEN,
                     font=ctk.CTkFont(size=10, weight="bold")).pack(side="left", padx=(4, 0))
            if e_hint:
                tk.Label(fr, text=f"  {e_hint}", bg=_BG_PANEL, fg=_HINT,
                         font=ctk.CTkFont(size=9)).pack(side="left")

        # Resultado
        res_fr = tk.Frame(panel, bg="#0d1a1f",
                          highlightthickness=1, highlightbackground=_GREEN_DARK)
        res_fr.grid(row=7, column=0, padx=12, pady=(0, 10), sticky="ew")
        tk.Label(res_fr, text="Nível máximo calculado do jogador:",
                 bg="#0d1a1f", fg="gray60",
                 font=ctk.CTkFont(size=11)).pack(side="left", padx=(12, 6), pady=8)
        ctk.CTkLabel(res_fr, textvariable=result_var,  # type: ignore[arg-type]
                     text_color=_GREEN,
                     font=ctk.CTkFont(size=18, weight="bold")).pack(
            side="left", pady=8)
        tk.Label(res_fr,
                 text="  ← inclui todas as ascensões selecionadas (Aquatica contabilizada)",
                 bg="#0d1a1f", fg="gray45",
                 font=ctk.CTkFont(size=9)).pack(side="left", padx=(4, 12), pady=8)

    # ── Nomes e descrições dos stats (índices 0-11) ───────────────────────
    _PLSM_STATS = [
        (0,  "❤️",  "Vida",               "HP máx. por ponto. Padrão ARK ≈ +10 HP base por nível."),
        (1,  "⚡",  "Stamina",            "Stamina por ponto. Padrão ≈ +10 stamina por nível."),
        (2,  "💤",  "Torpor",             "Resistência ao torpor. Principalmente relevante para dinos selvagens."),
        (3,  "🫧",  "Oxigênio",           "Oxigênio por ponto. Relevante para dinos aquáticos."),
        (4,  "🍖",  "Comida",             "Capacidade de comida por ponto."),
        (5,  "💧",  "Água",               "Capacidade de água. Relevante principalmente para jogadores."),
        (6,  "🌡️", "Temperatura",        "Resistência à temperatura (raramente ajustado)."),
        (7,  "⚖️", "Peso",               "Carga por ponto. Padrão ≈ +10 por nível."),
        (8,  "⚔️", "Dano Corpo a Corpo", "Dano melee por ponto. Padrão ≈ +2% por nível."),
        (9,  "🏃",  "Velocidade",         "Velocidade de movimento por ponto. Padrão ≈ +1% por nível."),
        (10, "🛡️", "Fortitude",          "Resistência ao frio/calor. Relevante para jogadores."),
        (11, "🔨",  "Craft Skill",        "Habilidade de fabricação. Melhora receitas customizadas."),
    ]

    def _build_plsm_table(rn: int) -> None:
        """Constrói a tabela PerLevelStatsMultiplier (Dino Domado / Selvagem / Jogador)."""
        outer = ctk.CTkFrame(_cur_body[0], fg_color=_CARD_BG, corner_radius=10)
        outer.grid(row=rn, column=0, columnspan=4, padx=12, pady=(0, 8), sticky="ew")
        outer.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            outer,
            text="Multiplica o ganho de cada stat a cada ponto investido ao subir nível."
                 "  1.0 = padrão ARK  •  2.0 = dobro do ganho  •  0.0 = desativa o stat.",
            text_color="gray50", font=ctk.CTkFont(size=10), justify="left",
        ).grid(row=0, column=0, padx=14, pady=(10, 4), sticky="w")

        tbl = ctk.CTkFrame(outer, fg_color="transparent")
        tbl.grid(row=1, column=0, padx=10, pady=(0, 12), sticky="ew")
        tbl.grid_columnconfigure(0, weight=1)
        tbl.grid_columnconfigure(1, minsize=82)
        tbl.grid_columnconfigure(2, minsize=82)
        tbl.grid_columnconfigure(3, minsize=82)
        tbl.grid_columnconfigure(4, minsize=82)
        tbl.grid_columnconfigure(5, minsize=82)

        # Cabeçalho
        ctk.CTkLabel(tbl, text="Stat", anchor="w",
                     text_color="gray55",
                     font=ctk.CTkFont(size=10, weight="bold")).grid(
            row=0, column=0, padx=(8, 4), pady=(0, 2), sticky="w")
        for col_i, (col_txt, col_color) in enumerate([
            ("Domado (IdM)",       "#4fc3f7"),
            ("Dom. Bônus (TaM)",  "#ce93d8"),
            ("Dom. Afinid. (TmM)", "#f48fb1"),
            ("Selvagem (IwM)",     "#a5d6a7"),
            ("Jogador",            "#ffcc80"),
        ], start=1):
            ctk.CTkLabel(tbl, text=col_txt, anchor="center",
                         text_color=col_color,
                         font=ctk.CTkFont(size=10, weight="bold")).grid(
                row=0, column=col_i, padx=4, pady=(0, 2))

        ctk.CTkFrame(tbl, height=1, fg_color="gray30").grid(
            row=1, column=0, columnspan=6, sticky="ew", padx=4, pady=(0, 2))

        # Linhas de stat
        for i, (stat_idx, emoji, stat_name, stat_hint) in enumerate(_PLSM_STATS):
            tr = stat_idx + 2
            app._register_config_item(
                srv.id, f"{stat_name} — Stats/Nível", stat_hint, "Jogo")

            stripe = "#1c1c2e" if i % 2 == 0 else "#13131c"
            row_fr = ctk.CTkFrame(tbl, fg_color=stripe, corner_radius=4)
            row_fr.grid(row=tr, column=0, columnspan=6, sticky="ew", padx=2, pady=1)
            row_fr.grid_columnconfigure(0, weight=1)
            row_fr.grid_columnconfigure(1, minsize=82)
            row_fr.grid_columnconfigure(2, minsize=82)
            row_fr.grid_columnconfigure(3, minsize=82)
            row_fr.grid_columnconfigure(4, minsize=82)
            row_fr.grid_columnconfigure(5, minsize=82)

            ctk.CTkLabel(
                row_fr,
                text=f"{emoji}  {stat_name}",
                text_color="gray65",
                font=ctk.CTkFont(size=11),
                anchor="w", width=188,
            ).grid(row=0, column=0, padx=(8, 4), pady=3, sticky="w")

            for col_i, (group, grp_attr) in enumerate([
                ("tamed",          "per_level_stats_mult_dino_tamed"),
                ("tamed_add",      "per_level_stats_mult_dino_tamed_add"),
                ("tamed_affinity", "per_level_stats_mult_dino_tamed_affinity"),
                ("wild",           "per_level_stats_mult_dino_wild"),
                ("player",         "per_level_stats_mult_player"),
            ], start=1):
                val = getattr(gs, grp_attr)[stat_idx]
                var = tk.StringVar(value=f"{val:.4g}")
                w[f"gs_plsm_{group}_{stat_idx}"] = var
                ent = ctk.CTkEntry(
                    row_fr, textvariable=var,
                    width=82, height=26,
                    justify="center",
                    font=ctk.CTkFont(size=11),
                    fg_color="#0a0a14",
                )
                ent.grid(row=0, column=col_i, padx=4, pady=3)

                def _make_commit(v=var):
                    def _commit(e=None):
                        try:
                            fv = max(0.0, float(v.get().replace(",", ".")))
                            v.set(f"{fv:.4g}")
                        except ValueError:
                            v.set("1")
                    return _commit
                _cb = _make_commit()
                ent.bind("<FocusOut>", _cb)
                ent.bind("<Return>",   _cb)

    def _make_section(text: str) -> tk.Frame:
        """Cria uma seção colapsável (accordion) e retorna seu body frame."""
        _SEC_BG  = "#0d0d1e"
        _HEAD_BG = "#141428"
        _BDR     = "#2a2a45"
        sec = tk.Frame(scroll, bg=_SEC_BG, highlightthickness=1,
                       highlightbackground=_BDR)
        sec.pack(fill="x", padx=6, pady=(8, 0))

        expanded = [True]

        header = tk.Frame(sec, bg=_HEAD_BG, cursor="hand2")
        header.pack(fill="x")

        arrow = tk.Label(header, text="▼", bg=_HEAD_BG, fg=_GREEN,
                         font=ctk.CTkFont(size=11))
        arrow.pack(side="left", padx=(10, 6), pady=7)

        tk.Label(header, text=text, bg=_HEAD_BG, fg="#c8c8e8",
                 font=ctk.CTkFont(size=12, weight="bold"),
                 anchor="w").pack(side="left", pady=7, fill="x", expand=True)

        body = tk.Frame(sec, bg=_SEC_BG)
        body.pack(fill="x", padx=4, pady=(2, 6))
        body.columnconfigure(1, weight=1)
        body.columnconfigure(3, weight=1)

        def _toggle(event=None):
            expanded[0] = not expanded[0]
            if expanded[0]:
                body.pack(fill="x", padx=4, pady=(2, 6))
                arrow.configure(text="▼")
            else:
                body.pack_forget()
                arrow.configure(text="▶")

        header.bind("<Button-1>", _toggle)
        for child in header.winfo_children():
            child.bind("<Button-1>", _toggle)

        return body

    def _dispatch_task(task: tuple) -> None:
        kind = task[0]
        if kind == "s":
            _, rn, text = task
            _sec_start_r[0] = rn + 1
            _cur_body[0]    = _make_section(text)
        elif kind == "f":
            _, rn, lbl, hint, field, val, frm, to = task
            lr = rn - _sec_start_r[0]
            frow(lbl, hint, field, val, lr, frm, to)
        elif kind == "i":
            _, rn, lbl, hint, field, val = task
            lr = rn - _sec_start_r[0]
            irow(lbl, hint, field, val, lr)
        elif kind == "b":
            _, rn, lbl, field, val = task
            lr = rn - _sec_start_r[0]
            brow(lbl, field, val, lr)
        elif kind == "adv_f":
            _, rn, lbl, hint, field, val, frm, to = task
            lr = rn - _sec_start_r[0]
            adv_frow(lbl, hint, field, val, lr, frm, to)
        elif kind == "adv_b":
            _, rn, lbl, field, val = task
            lr = rn - _sec_start_r[0]
            adv_brow(lbl, field, val, lr)
        elif kind == "ascend_calc":
            _, rn = task
            lr = rn - _sec_start_r[0]
            _build_ascension_panel(lr)
        elif kind == "lcap":
            _, rn, lbl, hint, field, val = task
            lr = rn - _sec_start_r[0]
            _level_cap_row(lbl, hint, field, val, lr)
        elif kind == "calc":
            _, rn = task
            lr = rn - _sec_start_r[0]
            ctk.CTkButton(
                _cur_body[0],
                text="🧮  Calculadora de Breeding",
                width=230,
                fg_color="#2d4a6f",
                hover_color="#1b2d45",
                command=lambda _gs=gs: open_breeding_calculator(
                    app,  # type: ignore[arg-type]
                    _gs,
                    app._server_widgets.get(srv.id, {}),
                    lambda: app._save_server_config(srv.id, silent=True, force=True),
                ),
            ).grid(row=lr, column=0, columnspan=3, sticky="e", padx=16, pady=(2, 8))
        elif kind == "plsm":
            _, rn = task
            lr = rn - _sec_start_r[0]
            _build_plsm_table(lr)
        elif kind == "save":
            save_fr = ctk.CTkFrame(scroll, fg_color="transparent")
            save_fr.pack(fill="x", pady=(10, 4))
            app._save_btn_row(save_fr, 0, srv.id)

    def _exec_chunk(idx: int) -> None:
        for task in _tasks[idx: idx + _CHUNK]:
            _dispatch_task(task)
        nxt = idx + _CHUNK
        if nxt < len(_tasks):
            app.after(0, lambda i=nxt: _exec_chunk(i))
        else:
            # Último lote concluído — aplica lock se servidor estiver rodando
            inst_chk = app.server_manager.get_instance(srv.id)
            if inst_chk and inst_chk.status != SERVER_STATUS_STOPPED:
                app._set_config_editable(srv.id, False)

    app.after(0, lambda: _exec_chunk(0))

