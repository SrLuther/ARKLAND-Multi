from __future__ import annotations

import os
import platform
import tkinter as tk
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import (
    _GREEN, _GREEN_DARK, _GREEN_HOVER,
    _BLUE, _BLUE_HOVER,
    _CARD_BG, _BG,
    _FORM_FONT_BOLD, _FORM_FONT_HINT, _FORM_LABEL_FG, _FORM_HINT_FG,
)

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
    from ..server_config import ServerConfig


def build_tab_advanced(app: "ARKServerManagerApp", parent, srv: "ServerConfig") -> None:  # noqa: C901
    # ── Barra de salvar fixada no topo ────────────────────────────────────
    save_bar = tk.Frame(parent, bg=_BG, height=52)
    save_bar.pack(side="top", fill="x")
    save_bar.pack_propagate(False)
    ctk.CTkButton(
        save_bar, text="💾  Salvar & Aplicar Configurações",
        height=36, font=ctk.CTkFont(size=13, weight="bold"),
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=lambda: app._save_server_config(srv.id),
    ).pack(side="left", padx=(16, 0), pady=8)
    ctk.CTkButton(
        save_bar, text="⬆️  Importar INI do Disco",
        height=36, width=190, fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=lambda: app._import_ini_from_disk(srv.id),
    ).pack(side="left", padx=(10, 0), pady=8)
    ctk.CTkButton(
        save_bar, text="🔄  Sincronizar INI",
        height=36, width=160, fg_color="#6a3aaa", hover_color="#7a4abb",
        command=lambda: app._open_sync_ini_dialog(srv.id),
    ).pack(side="left", padx=(10, 0), pady=8)
    ctk.CTkButton(
        save_bar, text="📋  Clonar Configurações",
        height=36, width=190, fg_color="#3a5a2a", hover_color="#4a6a3a",
        command=lambda: app._open_clone_config_dialog(srv.id),
    ).pack(side="left", padx=(10, 0), pady=8)

    # ── Scroll 2 colunas ──────────────────────────────────────────────────
    scroll = ctk.CTkScrollableFrame(parent, fg_color=_CARD_BG)
    scroll.pack(fill="both", expand=True, padx=4, pady=4)
    scroll.grid_columnconfigure(0, weight=1, uniform="gcol")
    scroll.grid_columnconfigure(1, weight=1, uniform="gcol")
    # Suspende o recálculo de scrollregion durante o build (elimina O(n²))
    scroll.unbind("<Configure>")

    w   = app._server_widgets[srv.id]
    adv = srv.advanced_settings
    cl  = srv.cluster
    _INNER = "#16162a"

    def _make_card(col: int, grow: int, colspan: int = 1) -> tk.Frame:
        c = tk.Frame(scroll, bg=_INNER,
                     highlightthickness=1, highlightbackground="#2a2a45")
        c.grid(row=grow, column=col, columnspan=colspan,
               padx=8, pady=6, sticky="new")
        c.columnconfigure(0, weight=1)
        return c

    def _head(cnt: tk.Frame, text: str) -> None:
        tk.Label(cnt, text=text, bg=_INNER, fg="#c8c8e8",
                 font=ctk.CTkFont(size=12, weight="bold"),
                 anchor="w").pack(fill="x", padx=10, pady=(8, 2))
        tk.Frame(cnt, bg=_GREEN, height=1).pack(fill="x", padx=10, pady=(0, 6))

    def _fld(cnt: tk.Frame, label: str, hint: str, var,
             is_pass: bool = False, browse: bool = False,
             combo: Optional[List] = None, state: str = "normal") -> None:
        app._register_config_item(srv.id, label.rstrip(": "), hint, "Avançado")
        fr = tk.Frame(cnt, bg=_INNER)
        fr.pack(fill="x", padx=10, pady=(0, 4))
        fr.columnconfigure(0, weight=1)
        tk.Label(fr, text=label, anchor="w", bg=_INNER,
                 fg=_FORM_LABEL_FG, font=_FORM_FONT_BOLD).grid(row=0, column=0, sticky="w")
        if browse:
            bf = tk.Frame(fr, bg=_INNER)
            bf.grid(row=1, column=0, sticky="ew", pady=(2, 0))
            bf.columnconfigure(0, weight=1)
            ent = ctk.CTkEntry(bf, textvariable=var, height=34, state=state)
            ent.grid(row=0, column=0, sticky="ew", padx=(0, 6))
            btn = ctk.CTkButton(bf, text="📁", width=34, height=34, state=state,
                                command=lambda v=var: app._browse_dir(v))
            btn.grid(row=0, column=1)
            # store references for enable/disable
            if hasattr(var, "_browse_widgets"):
                var._browse_widgets = (ent, btn)
        else:
            ctk.CTkEntry(fr, textvariable=var, height=34,
                         show="*" if is_pass else "",
                         state=state).grid(
                row=1, column=0, sticky="ew", pady=(2, 0))
        if hint:
            tk.Label(fr, text=hint, anchor="w", bg=_INNER, fg=_FORM_HINT_FG,
                     font=_FORM_FONT_HINT, justify="left").grid(
                row=2, column=0, sticky="w", pady=(1, 2))

    def _chk(cnt: tk.Frame, label: str, hint: str, var,
             key: str | None = None) -> None:
        app._register_config_item(srv.id, label, hint, "Avançado")
        fr = tk.Frame(cnt, bg=_INNER)
        fr.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkCheckBox(fr, text=label, variable=var,
                        checkmark_color="white", fg_color=_GREEN_DARK,
                        hover_color=_GREEN_HOVER).pack(anchor="w")
        if hint:
            tk.Label(fr, text=hint, bg=_INNER, fg=_FORM_HINT_FG,
                     font=_FORM_FONT_HINT, anchor="w").pack(
                anchor="w", padx=(26, 0), pady=(0, 2))

    # ── helpers de campo c/ prefixo adv_ ─────────────────────────────────
    def _b(cnt: tk.Frame, label: str, hint: str, field: str, val: bool) -> None:
        w[f"adv_{field}"] = tk.BooleanVar(value=val)
        _chk(cnt, label, hint, w[f"adv_{field}"])

    def _f(cnt: tk.Frame, label: str, hint: str, field: str, val: float) -> None:
        w[f"adv_{field}"] = tk.StringVar(value=str(val))
        _fld(cnt, label, hint, w[f"adv_{field}"])

    # ══════════════════════════════════════════════════════════════════════
    # Linha 0 — Cross-ARK (largura total)
    # ══════════════════════════════════════════════════════════════════════
    c_cl = _make_card(0, 0, colspan=2)
    _head(c_cl, "🌐  Cross-ARK (Cluster)")

    # ── Seletor de Perfil de Cluster ──────────────────────────────────────
    profiles      = app.config_manager.clusters
    profile_names = [""] + [p.name for p in profiles]
    profile_ids   = [""] + [p.id for p in profiles]
    current_pid   = srv.cluster_profile_id
    current_idx   = profile_ids.index(current_pid) if current_pid in profile_ids else 0

    w["cl_profile_id_var"] = tk.StringVar(value=profile_ids[current_idx])
    _manual_locked = bool(current_pid)

    def _on_profile_select(choice: str) -> None:
        idx = profile_names.index(choice) if choice in profile_names else 0
        pid = profile_ids[idx]
        w["cl_profile_id_var"].set(pid)
        state = "disabled" if pid else "normal"
        for widget_key in ("_cl_id_entry", "_cl_dir_entry", "_cl_dir_btn"):
            wgt = w.get(widget_key)
            if wgt:
                try:
                    wgt.configure(state=state)
                except Exception:
                    pass
        if pid:
            prof = app.config_manager.get_cluster(pid)
            if prof:
                w.get("cl_cluster_id",  tk.StringVar()).set(prof.cluster_id)
                w.get("cl_cluster_dir", tk.StringVar()).set(prof.cluster_dir)
        cl_en_cb = w.get("_cl_enabled_cb")
        if cl_en_cb:
            try:
                cl_en_cb.configure(state="disabled" if pid else "normal")
            except Exception:
                pass

    # ── Perfil ────────────────────────────────────────────────────────────
    prof_fr = tk.Frame(c_cl, bg=_INNER)
    prof_fr.pack(fill="x", padx=10, pady=(0, 6))
    prof_fr.columnconfigure(1, weight=1)
    tk.Label(prof_fr, text="Perfil de Cluster:", bg=_INNER,
             fg=_FORM_LABEL_FG, font=_FORM_FONT_BOLD, anchor="w").grid(
        row=0, column=0, sticky="w", padx=(0, 8))
    tk.Label(prof_fr,
             text="Selecione um perfil global ou configure manualmente abaixo.",
             bg=_INNER, fg=_FORM_HINT_FG, font=_FORM_FONT_HINT, anchor="w").grid(
        row=1, column=0, columnspan=2, sticky="w")
    ctk.CTkOptionMenu(
        prof_fr, values=profile_names, width=260, height=32,
        fg_color=_CARD_BG, button_color=_BLUE, button_hover_color=_BLUE_HOVER,
        command=_on_profile_select,
        variable=tk.StringVar(value=profile_names[current_idx]),
    ).grid(row=0, column=1, sticky="ew")

    # ── Habilitado ────────────────────────────────────────────────────────
    w["cl_enabled"] = tk.BooleanVar(value=cl.enabled)
    en_fr = tk.Frame(c_cl, bg=_INNER)
    en_fr.pack(fill="x", padx=10, pady=(0, 4))
    _cl_en_cb = ctk.CTkCheckBox(
        en_fr, text="Habilitar Cluster (Cross-ARK)",
        variable=w["cl_enabled"],
        checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        state="disabled" if _manual_locked else "normal",
    )
    _cl_en_cb.pack(anchor="w")
    tk.Label(en_fr,
             text="Permite que múltiplos servidores compartilhem tribos, dinos e itens entre si.",
             bg=_INNER, fg=_FORM_HINT_FG, font=_FORM_FONT_HINT, anchor="w").pack(
        anchor="w", padx=(26, 0))
    w["_cl_enabled_cb"] = _cl_en_cb

    # ── Cluster ID ────────────────────────────────────────────────────────
    w["cl_cluster_id"]  = tk.StringVar(value=cl.cluster_id)
    w["cl_cluster_dir"] = tk.StringVar(value=cl.cluster_dir_override)
    w["cl_alt_save_dir"] = tk.StringVar(value=srv.alt_save_directory_name)

    cid_fr2 = tk.Frame(c_cl, bg=_INNER)
    cid_fr2.pack(fill="x", padx=10, pady=(0, 4))
    cid_fr2.columnconfigure(0, weight=1)
    tk.Label(cid_fr2, text="ID do Cluster:", bg=_INNER,
             fg=_FORM_LABEL_FG, font=_FORM_FONT_BOLD, anchor="w").grid(row=0, column=0, sticky="w")
    tk.Label(cid_fr2,
             text="Identificador único do cluster. Todos os servidores do mesmo cluster devem usar o mesmo ID.",
             bg=_INNER, fg=_FORM_HINT_FG, font=_FORM_FONT_HINT, anchor="w").grid(row=1, column=0, sticky="w")
    _cl_id_entry = ctk.CTkEntry(cid_fr2, textvariable=w["cl_cluster_id"], height=32,
                                placeholder_text="Ex: MeuCluster123",
                                state="disabled" if _manual_locked else "normal")
    _cl_id_entry.grid(row=2, column=0, sticky="ew", pady=(2, 0))
    w["_cl_id_entry"] = _cl_id_entry

    # ── Pasta do Cluster ──────────────────────────────────────────────────
    cdir_fr2 = tk.Frame(c_cl, bg=_INNER)
    cdir_fr2.pack(fill="x", padx=10, pady=(0, 4))
    cdir_fr2.columnconfigure(0, weight=1)
    tk.Label(cdir_fr2, text="Pasta do Cluster:", bg=_INNER,
             fg=_FORM_LABEL_FG, font=_FORM_FONT_BOLD, anchor="w").grid(row=0, column=0, columnspan=2, sticky="w")
    tk.Label(cdir_fr2, text="Pasta compartilhada para transferência de dados entre servidores. Opcional.",
             bg=_INNER, fg=_FORM_HINT_FG, font=_FORM_FONT_HINT, anchor="w").grid(row=1, column=0, columnspan=2, sticky="w")
    _cl_dir_entry = ctk.CTkEntry(cdir_fr2, textvariable=w["cl_cluster_dir"], height=32,
                                 state="disabled" if _manual_locked else "normal")
    _cl_dir_entry.grid(row=2, column=0, sticky="ew", padx=(0, 6), pady=(2, 0))
    _cl_dir_btn = ctk.CTkButton(cdir_fr2, text="📁", width=34, height=32,
                                state="disabled" if _manual_locked else "normal",
                                command=lambda: app._browse_dir(w["cl_cluster_dir"]))
    _cl_dir_btn.grid(row=2, column=1, pady=(2, 0))
    w["_cl_dir_entry"] = _cl_dir_entry
    w["_cl_dir_btn"]   = _cl_dir_btn

    # ── Pasta de Saves ────────────────────────────────────────────────────
    asdir_fr2 = tk.Frame(c_cl, bg=_INNER)
    asdir_fr2.pack(fill="x", padx=10, pady=(0, 4))
    asdir_fr2.columnconfigure(0, weight=1)
    tk.Label(asdir_fr2, text="Nome da Pasta de Saves:", bg=_INNER,
             fg=_FORM_LABEL_FG, font=_FORM_FONT_BOLD, anchor="w").grid(row=0, column=0, sticky="w")
    tk.Label(asdir_fr2,
             text="Pasta única de saves para este servidor (?AltSaveDirectoryName). "
                  "Obrigatório ao rodar múltiplos servidores na mesma máquina.",
             bg=_INNER, fg=_FORM_HINT_FG, font=_FORM_FONT_HINT, anchor="w").grid(row=1, column=0, sticky="w")
    _cl_asdir_entry = ctk.CTkEntry(asdir_fr2, textvariable=w["cl_alt_save_dir"], height=32,
                                   placeholder_text="Ex: Save1",
                                   state="disabled" if _manual_locked else "normal")
    _cl_asdir_entry.grid(row=2, column=0, sticky="ew", pady=(2, 0))
    w["_cl_asdir_entry"] = _cl_asdir_entry

    # ── Restrições de Transferência ───────────────────────────────────────
    _b(c_cl, "Bloquear Download de Sobreviventes",
       "Impede jogadores de importar personagens de outros servidores do cluster.",
       "prevent_download_survivors", adv.prevent_download_survivors)
    _b(c_cl, "Bloquear Download de Itens",
       "Impede jogadores de trazer itens de outros servidores do cluster.",
       "prevent_download_items", adv.prevent_download_items)
    _b(c_cl, "Bloquear Download de Dinos",
       "Impede jogadores de trazer dinos domesticados de outros servidores.",
       "prevent_download_dinos", adv.prevent_download_dinos)
    _b(c_cl, "Bloquear Upload de Sobreviventes",
       "Impede jogadores de enviar seus personagens para o cluster.",
       "prevent_upload_survivors", adv.prevent_upload_survivors)
    _b(c_cl, "Bloquear Upload de Itens",
       "Impede jogadores de enviar itens ao cluster.",
       "prevent_upload_items", adv.prevent_upload_items)
    _b(c_cl, "Bloquear Upload de Dinos",
       "Impede jogadores de enviar dinos ao cluster.",
       "prevent_upload_dinos", adv.prevent_upload_dinos)
    _b(c_cl, "Bloquear Transferência por Filtro",
       "Impede transferências bloqueadas por restrições de filtro de mapa.",
       "no_transfer_from_filtering", adv.no_transfer_from_filtering)

    # ── Diagnóstico ───────────────────────────────────────────────────────
    diag_fr = tk.Frame(c_cl, bg=_INNER)
    diag_fr.pack(fill="x", padx=10, pady=(2, 10))
    ctk.CTkButton(
        diag_fr, text="🔍  Diagnosticar Cluster", height=32, width=220,
        fg_color="#2a4a6a", hover_color="#3a5a7a",
        command=lambda sid=srv.id: app._show_cluster_health_dialog(sid),
    ).pack(anchor="w")

    # ══════════════════════════════════════════════════════════════════════
    # Linha 1 — Game.ini Avançado (col 0) | Dinos Comportamentos (col 1)
    # ══════════════════════════════════════════════════════════════════════
    c_game = _make_card(0, 1)
    _head(c_game, "⚙️  Game.ini Avançado")
    _b(c_game, "Nerf de Criôpod Ativado",
       "Aplica penalidade de dano em dinos recém-lançados do criôpod. Útil para PvP.",
       "enable_cryopod_nerf", adv.enable_cryopod_nerf)
    _f(c_game, "Duração do Nerf de Criôpod (s)",
       "Quantos segundos dura a penalidade após sair do criôpod.",
       "cryopod_nerf_duration", adv.cryopod_nerf_duration)
    _f(c_game, "Mult. de Dano do Nerf",
       "Fator de dano enquanto o nerf está ativo. Ex: 0.01 = apenas 1% do dano normal.",
       "cryopod_nerf_damage_mult", adv.cryopod_nerf_damage_mult)
    _b(c_game, "Spawnar Supply Crates em Estruturas",
       "Permite que supply crates apareçam sobre estruturas construídas.",
       "allow_crateSpawns_on_top_of_structures", adv.allow_crateSpawns_on_top_of_structures)
    _b(c_game, "Otimizar HP de Coleta",
       "Melhora a performance ao calcular HP de recursos coletáveis.",
       "use_optimized_harvesting_health", adv.use_optimized_harvesting_health)
    _b(c_game, "Defesas Passivas Atacam Dinos sem Cavaleiro",
       "Torretas e armadilhas atacam dinos selvagens e sem piloto.",
       "b_passive_defenses_damage_riderless_dinos", adv.b_passive_defenses_damage_riderless_dinos)
    _b(c_game, "Chat de Voz Global",
       "Todos os jogadores se ouvem independente da distância.",
       "global_voice_chat", adv.global_voice_chat)
    _b(c_game, "Chat de Voz por Proximidade",
       "Somente jogadores próximos se ouvem. Tem prioridade sobre o Chat Global.",
       "proximity_chat", adv.proximity_chat)
    _b(c_game, "Alimentar Dino de Raid",
       "Permite que o Titanossauro (raid dino) seja alimentado.",
       "allow_raid_dino_feeding", adv.allow_raid_dino_feeding)
    _f(c_game, "Consumo de Comida do Dino de Raid",
       "Taxa de consumo de comida do Titanossauro. Menor = come mais devagar.",
       "raid_dino_character_food_drain_multiplier", adv.raid_dino_character_food_drain_multiplier)
    _f(c_game, "Mult. Velocidade de Nado (Oxigênio)",
       "Multiplica a velocidade de nado baseada no stat de oxigênio.",
       "oxygen_swim_speed_stat_multiplier", adv.oxygen_swim_speed_stat_multiplier)
    _f(c_game, "Dano de Coleta dos Dinos",
       "Multiplica o dano que dinos causam ao coletar recursos.",
       "dino_harvesting_damage_multiplier", adv.dino_harvesting_damage_multiplier)
    _f(c_game, "Dano de Coleta dos Jogadores",
       "Multiplica o dano que jogadores causam ao coletar recursos.",
       "player_harvesting_damage_multiplier", adv.player_harvesting_damage_multiplier)
    _f(c_game, "Habilidade em Receitas Customizadas",
       "Influencia as stats da receita baseado na habilidade do personagem.",
       "custom_recipe_skill_multiplier", adv.custom_recipe_skill_multiplier)
    _f(c_game, "Efetividade de Receitas Customizadas",
       "Multiplica os bônus de stats obtidos em receitas customizadas.",
       "custom_recipe_effectiveness_multiplier", adv.custom_recipe_effectiveness_multiplier)
    _b(c_game, "PvE Automático com Timer",
       "Alterna automaticamente entre PvP e PvE conforme o horário definido.",
       "b_auto_pve_timer", adv.b_auto_pve_timer)
    _b(c_game, "PvE Automático usa Hora do Sistema",
       "Usa o horário do servidor (SO) para calcular o timer de PvE automático.",
       "b_auto_pve_use_system_time", adv.b_auto_pve_use_system_time)
    _f(c_game, "Início do PvE Automático (s do dia)",
       "Segundo do dia (0–86400) em que o PvE começa. Ex: 0 = meia-noite.",
       "auto_pve_start_time_seconds", adv.auto_pve_start_time_seconds)
    _f(c_game, "Fim do PvE Automático (s do dia)",
       "Segundo do dia (0–86400) em que o PvE termina.",
       "auto_pve_stop_time_seconds", adv.auto_pve_stop_time_seconds)
    _b(c_game, "Forçar Bloqueio em Estruturas",
       "Todas as estruturas são criadas bloqueadas por padrão.",
       "force_all_structure_locking", adv.force_all_structure_locking)
    _b(c_game, "Forçar Explosivos em Voadores",
       "Dinos voadores podem transportar C4 e explosivos em PvP.",
       "force_flyer_explosives", adv.force_flyer_explosives)

    # ── Dinos Comportamentos (col 1) ──────────────────────────────────────
    c_dino = _make_card(1, 1)
    _head(c_dino, "🦖  Dinos — Comportamentos Extras")
    _f(c_dino, "Intervalo de Domesticação Passiva",
       "Multiplica o intervalo entre interações de tame passivo.",
       "passive_tame_interval_multiplier", adv.passive_tame_interval_multiplier)
    _f(c_dino, "Consumo de Comida — Dino Selvagem",
       "Taxa de consumo de comida de dinos selvagens.",
       "wild_dino_character_food_drain_multiplier", adv.wild_dino_character_food_drain_multiplier)
    _f(c_dino, "Consumo de Comida — Dino Domado",
       "Taxa de consumo de comida de dinos domados.",
       "tamed_dino_character_food_drain_multiplier", adv.tamed_dino_character_food_drain_multiplier)
    _f(c_dino, "Dreno de Torpor — Dino Selvagem",
       "Velocidade de redução de torpor em dinos selvagens.",
       "wild_dino_torpor_drain_multiplier", adv.wild_dino_torpor_drain_multiplier)
    _f(c_dino, "Dreno de Torpor — Dino Domado",
       "Velocidade de redução de torpor em dinos domados.",
       "tamed_dino_torpor_drain_multiplier", adv.tamed_dino_torpor_drain_multiplier)
    _f(c_dino, "Velocidade de Perda de Qualidade de Imprint",
       "Multiplica a velocidade de perda de qualidade de imprint durante o carinho.",
       "baby_cuddle_lose_imprint_quality_speed_multiplier",
       adv.baby_cuddle_lose_imprint_quality_speed_multiplier)
    _f(c_dino, "Multiplicador de Temperatura Base",
       "Escala a temperatura ambiente do mapa (BaseTemperatureMultiplier).",
       "base_temperature_multiplier", adv.base_temperature_multiplier)
    _b(c_dino, "Usar Limite de Tame Apenas para Estruturas",
       "bUseTameLimitForStructuresOnly — conta apenas estruturas no limite de dinos domados.",
       "use_tame_limit_for_structures_only", adv.use_tame_limit_for_structures_only)
    _b(c_dino, "Desativar Montaria em Dinos",
       "Nenhum jogador pode montar dinos no servidor (bDisableDinoRiding).",
       "disable_dino_riding", adv.disable_dino_riding)
    _b(c_dino, "Desativar Domesticação de Dinos",
       "Nenhum jogador pode domesticar dinos (bDisableDinoTaming).",
       "disable_dino_taming", adv.disable_dino_taming)

    # ══════════════════════════════════════════════════════════════════════
    # Linha 2 — PvP/PvE Extras (col 0) | Gameplay / Itens (col 1)
    # ══════════════════════════════════════════════════════════════════════
    c_pvp = _make_card(0, 2)
    _head(c_pvp, "⚔️  PvP/PvE — Extras")
    _b(c_pvp, "Desativar Fogo Amigo (PvP)",
       "Danos entre aliados são desativados em servidores PvP (bDisableFriendlyFire).",
       "disable_friendly_fire_pvp", adv.disable_friendly_fire_pvp)
    _b(c_pvp, "Desativar Fogo Amigo (PvE)",
       "Danos entre aliados são desativados em servidores PvE (bPvEDisableFriendlyFire).",
       "disable_friendly_fire_pve", adv.disable_friendly_fire_pve)
    _b(c_pvp, "Desativar Supply Crates (Loots)",
       "Impede que beacons/supply drops apareçam no mapa (bDisableLootCrates).",
       "disable_loot_crates", adv.disable_loot_crates)
    _b(c_pvp, "Aumentar Intervalo de Respawn em PvP",
       "Aumenta progressivamente o tempo de respawn de jogadores que morrem em PvP.",
       "increase_pvp_respawn_interval", adv.increase_pvp_respawn_interval)
    _f(c_pvp, "Período de Verificação do Respawn PvP (s)",
       "Janela de tempo para contar mortes em PvP.",
       "increase_pvp_respawn_interval_check_period",
       adv.increase_pvp_respawn_interval_check_period)
    _f(c_pvp, "Multiplicador do Intervalo de Respawn PvP",
       "Quanto aumenta o tempo de respawn por morte recente.",
       "increase_pvp_respawn_interval_multiplier",
       adv.increase_pvp_respawn_interval_multiplier)
    _f(c_pvp, "Valor Base do Aumento de Respawn PvP (s)",
       "Segundos base adicionados ao respawn PvP antes de aplicar o multiplicador.",
       "increase_pvp_respawn_interval_base_amount",
       adv.increase_pvp_respawn_interval_base_amount)
    _f(c_pvp, "Invencibilidade ao Conectar após ORP (s)",
       "Segundos de invencibilidade ao entrar no servidor quando ORP estava ativo.",
       "prevent_offline_pvp_connection_invincible_interval",
       adv.prevent_offline_pvp_connection_invincible_interval)
    _b(c_pvp, "Permitir Guerra de Tribos (PvE)",
       "Tribos PvE podem declarar guerra entre si (bPvEAllowTribeWar).",
       "allow_tribe_war_pve", adv.allow_tribe_war_pve)
    _b(c_pvp, "Permitir Cancelar Guerra de Tribos (PvE)",
       "Tribos podem cancelar guerras em andamento (bPvEAllowTribeWarCancel).",
       "allow_tribe_war_cancel_pve", adv.allow_tribe_war_cancel_pve)
    _f(c_pvp, "Máx. Alianças por Tribo",
       "Número máximo de alianças que uma tribo pode ter.",
       "max_alliances_per_tribe", adv.max_alliances_per_tribe)
    _f(c_pvp, "Máx. Tribos por Aliança",
       "Número máximo de tribos que podem participar de uma aliança.",
       "max_tribes_per_alliance", adv.max_tribes_per_alliance)

    # ── Gameplay / Itens (col 1) ──────────────────────────────────────────
    c_gplay = _make_card(1, 2)
    _head(c_gplay, "🧪  Gameplay / Itens")
    _b(c_gplay, "Permitir Receitas Customizadas",
       "Jogadores podem criar receitas personalizadas (bAllowCustomRecipes).",
       "allow_custom_recipes", adv.allow_custom_recipes)
    _b(c_gplay, "Localizador de Cadáver",
       "Exibe onde o jogador morreu no mapa (bUseCorpseLocator).",
       "use_corpse_locator", adv.use_corpse_locator)
    _b(c_gplay, "Respecs Ilimitados",
       "Jogadores podem redistribuir atributos sem limite (bAllowUnlimitedRespecs).",
       "allow_unlimited_respecs", adv.allow_unlimited_respecs)
    _b(c_gplay, "Múltiplos Andares em Platform Saddle",
       "Permite construir múltiplos andares em platform saddles (bAllowPlatformSaddleMultiFloors).",
       "allow_platform_saddle_multi_floors", adv.allow_platform_saddle_multi_floors)
    _b(c_gplay, "Supply Crates em Pontos Aleatórios",
       "Spawna supply drops em locais aleatórios.",
       "random_supply_crate_points", adv.random_supply_crate_points)
    _f(c_gplay, "Qualidade de Loot de Supply Crate",
       "Multiplica a qualidade dos itens em supply drops.",
       "supply_crate_loot_quality_multiplier", adv.supply_crate_loot_quality_multiplier)
    _f(c_gplay, "Multiplicador de Vida Útil do Cadáver",
       "Quanto tempo cadáveres permanecem no chão.",
       "use_corpse_life_span_multiplier", adv.use_corpse_life_span_multiplier)
    _f(c_gplay, "Dreno de Durabilidade de Bateria/s",
       "Velocidade de desgaste de baterias ativas.",
       "global_powered_battery_durability_decrease_per_second",
       adv.global_powered_battery_durability_decrease_per_second)
    _f(c_gplay, "Mult. Tempo de Decomposição de Cadáver",
       "Multiplica o tempo que cadáveres levam para desaparecer.",
       "global_corpse_decomposition_time_multiplier",
       adv.global_corpse_decomposition_time_multiplier)
    _f(c_gplay, "Intervalo de Fazer Cocô",
       "Multiplica o intervalo entre defecações de criaturas.",
       "poop_interval_multiplier", adv.poop_interval_multiplier)
    _f(c_gplay, "Velocidade de Crescimento de Cabelo",
       "Multiplica a velocidade do crescimento de cabelo/pelo dos personagens.",
       "hair_growth_speed_multiplier", adv.hair_growth_speed_multiplier)
    _f(c_gplay, "Raio de Supressão de Recursos — Jogadores",
       "Raio ao redor de jogadores onde recursos não reaparecem.",
       "resource_no_replenish_radius_players", adv.resource_no_replenish_radius_players)
    _f(c_gplay, "Raio de Supressão de Recursos — Estruturas",
       "Raio ao redor de estruturas onde recursos não reaparecem.",
       "resource_no_replenish_radius_structures", adv.resource_no_replenish_radius_structures)
    _f(c_gplay, "Bônus de Crafting Skill",
       "Multiplica os bônus de stat obtidos via Craft Skill.",
       "crafting_skill_bonus_multiplier", adv.crafting_skill_bonus_multiplier)

    # ══════════════════════════════════════════════════════════════════════
    # Linha 3 — Estruturas Extras (col 0) + col 1 livre
    # ══════════════════════════════════════════════════════════════════════
    c_struct = _make_card(0, 3)
    _head(c_struct, "🏗️  Estruturas — Extras")
    _b(c_struct, "Desativar Colisão no Posicionamento",
       "Permite sobrepor estruturas ao construir (bDisableStructurePlacementCollision).",
       "disable_structure_placement_collision", adv.disable_structure_placement_collision)
    _f(c_struct, "Dano de Estrutura em Zona PvP",
       "Multiplica o dano sofrido por estruturas em zonas PvP.",
       "pvp_zone_structure_damage_multiplier", adv.pvp_zone_structure_damage_multiplier)
    _b(c_struct, "Dinos Não-Alinhados em Platform Saddle",
       "Permite que dinos montem em platform saddles sem alinhar direção.",
       "flyer_platform_allow_unaligned_dino_basing",
       adv.flyer_platform_allow_unaligned_dino_basing)
    _b(c_struct, "Habilitar Decaimento Rápido por Intervalo",
       "Ativa o modo de decaimento acelerado baseado em intervalo.",
       "enable_fast_decay_interval", adv.enable_fast_decay_interval)
    _f(c_struct, "Intervalo de Decaimento Rápido (s)",
       "Intervalo em segundos para o ciclo de decaimento rápido. Padrão: 43200 (12h).",
       "fast_decay_interval", adv.fast_decay_interval)
    _b(c_struct, "Limitar Torretas em Área",
       "Ativa o limite de torretas dentro de um raio (bLimitTurretsInRange).",
       "limit_turrets_in_range", adv.limit_turrets_in_range)
    _f(c_struct, "Raio do Limite de Torretas (unidades)",
       "Raio (em unidades de jogo) para contar o limite de torretas.",
       "limit_turrets_range", adv.limit_turrets_range)
    _f(c_struct, "Máx. Torretas no Raio",
       "Número máximo de torretas permitido dentro do raio.",
       "limit_turrets_num", adv.limit_turrets_num)
    _b(c_struct, "Limite Rígido de Torretas",
       "Bloqueia completamente a colocação quando o limite é atingido (bHardLimitTurretsInRange).",
       "hard_limit_turrets_in_range", adv.hard_limit_turrets_in_range)

    # ══════════════════════════════════════════════════════════════════════
    # Linha 4 — Config Dinâmica (largura total)
    # ══════════════════════════════════════════════════════════════════════
    c_dyn = _make_card(0, 4, colspan=2)
    _head(c_dyn, "⚡  Config Dinâmica (sem reinício)")

    tk.Label(
        c_dyn,
        text="O ARK suporta -DynamicConfigURL: o servidor busca um arquivo INI periodicamente (~2 min)\n"
             "e aplica multiplicadores de rate, breeding etc. sem reiniciar. Funciona apenas com\n"
             "servidores iniciados pelo app após ativar esta opção.",
        bg=_INNER, fg=_FORM_HINT_FG, font=_FORM_FONT_HINT, justify="left", anchor="w",
    ).pack(fill="x", padx=10, pady=(0, 6))

    app._register_config_item(srv.id,
        "Config Dinâmica", "Aplica mudanças de rate sem reiniciar via DynamicConfigURL.", "Avançado")
    w["dynamic_config_enabled"] = tk.BooleanVar(value=srv.dynamic_config_enabled)

    dyn_cb_fr = tk.Frame(c_dyn, bg=_INNER)
    dyn_cb_fr.pack(fill="x", padx=10, pady=(0, 4))
    ctk.CTkCheckBox(
        dyn_cb_fr, text="Ativar Config Dinâmica",
        variable=w["dynamic_config_enabled"],
        checkmark_color="white", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
    ).pack(side="left")

    dyn_url_var = tk.StringVar(value=(
        app._dynamic_config_server.get_url(srv.id)
        if srv.dynamic_config_enabled else "—"
    ))
    w["_dyn_url_var"] = dyn_url_var
    tk.Label(dyn_cb_fr, textvariable=dyn_url_var, bg=_INNER,
             fg=_FORM_HINT_FG, font=_FORM_FONT_HINT).pack(side="left", padx=(14, 0))

    dyn_btn_row = tk.Frame(c_dyn, bg=_INNER)
    dyn_btn_row.pack(fill="x", padx=10, pady=(4, 10))
    ctk.CTkButton(
        dyn_btn_row,
        text="⚡  Aplicar Sem Reiniciar",
        height=34, width=200,
        fg_color="#2a6a9a", hover_color="#3a7aaa",
        command=lambda sid=srv.id: app._push_dynamic_config(sid),
    ).pack(side="left", padx=(0, 10))
    tk.Label(
        dyn_btn_row,
        text="Atualiza o conteúdo servido — ARK aplicará na próxima poll.",
        bg=_INNER, fg=_FORM_HINT_FG, font=_FORM_FONT_HINT,
    ).pack(side="left")
    # Restaura o binding de scrollregion e força um único recálculo
    scroll.bind("<Configure>",
                lambda _e, _c=scroll._parent_canvas: _c.configure(scrollregion=_c.bbox("all")))
    scroll._parent_canvas.configure(scrollregion=scroll._parent_canvas.bbox("all"))

