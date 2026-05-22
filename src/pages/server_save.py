from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING
import pathlib

from pathlib import Path
import time
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def save_server_config(app: "ARKServerManagerApp", server_id: str, silent: bool = False, force: bool = False) -> None:

    """Lê todos os widgets do servidor, salva no config e escreve os .ini."""
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return

    # Bloqueia salvamento se o servidor não estiver parado (a menos que force=True)
    if not force:
        inst = app.server_manager.get_instance(server_id)
        if inst and inst.status != SERVER_STATUS_STOPPED:
            if not silent:
                messagebox.showwarning(
                    "Servidor em execução",
                    "Pare o servidor antes de salvar as configurações.",
                    parent=app,
                )
            return

    w = app._server_widgets.get(server_id, {})

    # Snapshot antes das alterações (para o log)
    _snap_before = snapshot_server(srv)

    # ── Geral ──────────────────────────────────────────────────────────
    if "name" in w:
        # Valida portas antes de qualquer alteração
        try:
            _new_sp = int(w["server_port"].get())
            _new_qp = int(w["query_port"].get())
            _new_rp = int(w["rcon_port"].get())
            _port_errs = app._validate_server_ports(server_id, _new_sp, _new_qp, _new_rp)
            if _port_errs:
                if not silent:
                    messagebox.showerror(
                        "Conflito de Portas",
                        "Corrija os conflitos antes de salvar:\n\n"
                        + "\n".join(f"• {e}" for e in _port_errs),
                        parent=app,
                    )
                return
        except (ValueError, KeyError):
            pass

        srv.name           = w["name"].get().strip() or srv.name
        srv.install_dir    = w["install_dir"].get().strip()
        srv.server_name    = w["server_name"].get().strip()
        map_raw = w["map"].get()
        if "(" in map_raw and map_raw.endswith(")"):
            srv.map = map_raw.split("(")[-1].rstrip(")")
        else:
            srv.map = map_raw
        srv.server_password  = w["server_password"].get()
        srv.admin_password   = w["admin_password"].get()
        srv.rcon_password    = w["rcon_password"].get()
        try:
            srv.max_players  = int(w["max_players"].get())
            srv.server_port  = int(w["server_port"].get())
            srv.query_port   = int(w["query_port"].get())
            srv.rcon_port    = int(w["rcon_port"].get())
        except (ValueError, KeyError):
            pass
        srv.public_ip             = w.get("public_ip", tk.StringVar()).get().strip()
        srv.battlemetrics_id      = w.get("battlemetrics_id", tk.StringVar()).get().strip()
        # Rede avançada
        srv.server_ip            = w.get("server_ip",           tk.StringVar()).get().strip()
        srv.public_ip_for_epic   = w.get("public_ip_for_epic",   tk.StringVar()).get().strip()
        srv.use_raw_sockets      = bool(w.get("use_raw_sockets",     tk.BooleanVar()).get())
        srv.no_net_threading     = bool(w.get("no_net_threading",    tk.BooleanVar()).get())
        srv.force_net_threading  = bool(w.get("force_net_threading", tk.BooleanVar()).get())
        # Acesso especial
        srv.spectator_password   = w.get("spectator_password",   tk.StringVar()).get()
        srv.enable_ban_list_url  = bool(w.get("enable_ban_list_url", tk.BooleanVar()).get())
        srv.ban_list_url         = w.get("ban_list_url",          tk.StringVar()).get().strip()
        # RCON avançado
        try:
            srv.rcon_server_game_log_buffer = int(w.get("rcon_server_game_log_buffer", tk.StringVar(value="600")).get())
        except (ValueError, TypeError):
            pass
        srv.admin_logging = bool(w.get("admin_logging", tk.BooleanVar()).get())
        # Extinction
        srv.enable_extinction_event = bool(w.get("enable_extinction_event", tk.BooleanVar()).get())
        try:
            srv.extinction_event_time_interval = int(w.get("extinction_event_time_interval", tk.StringVar(value="2592000")).get())
        except (ValueError, TypeError):
            pass
        # Flags de processo
        srv.disable_vac                     = bool(w.get("disable_vac",                     tk.BooleanVar()).get())
        srv.disable_anti_speed_hack         = bool(w.get("disable_anti_speed_hack",         tk.BooleanVar()).get())
        try:
            srv.speed_hack_bias             = float(w.get("speed_hack_bias", tk.StringVar(value="1.0")).get())
        except (ValueError, TypeError):
            pass
        srv.disable_player_move_physics_opt = bool(w.get("disable_player_move_physics_opt", tk.BooleanVar()).get())
        srv.use_cache                       = bool(w.get("use_cache",                       tk.BooleanVar()).get())
        srv.use_old_save_format             = bool(w.get("use_old_save_format",             tk.BooleanVar()).get())
        srv.use_no_memory_bias              = bool(w.get("use_no_memory_bias",              tk.BooleanVar()).get())
        srv.stasis_keep_controllers         = bool(w.get("stasis_keep_controllers",         tk.BooleanVar()).get())
        srv.use_no_hang_detection           = bool(w.get("use_no_hang_detection",           tk.BooleanVar()).get())
        srv.server_allow_ansel              = bool(w.get("server_allow_ansel",              tk.BooleanVar()).get())
        srv.no_dinos                        = bool(w.get("no_dinos",                        tk.BooleanVar()).get())
        srv.force_dx10                      = bool(w.get("force_dx10",                      tk.BooleanVar()).get())
        srv.force_shader_model4             = bool(w.get("force_shader_model4",             tk.BooleanVar()).get())
        srv.force_low_memory                = bool(w.get("force_low_memory",                tk.BooleanVar()).get())
        srv.enable_allow_cave_flyers        = bool(w.get("enable_allow_cave_flyers",        tk.BooleanVar()).get())
        srv.enable_auto_destroy_structures  = bool(w.get("enable_auto_destroy_structures",  tk.BooleanVar()).get())
        srv.enable_no_fish_loot             = bool(w.get("enable_no_fish_loot",             tk.BooleanVar()).get())
        srv.enable_web_alarm                = bool(w.get("enable_web_alarm",                tk.BooleanVar()).get())
        srv.web_alarm_key                   = w.get("web_alarm_key",                        tk.StringVar()).get().strip()
        srv.web_alarm_url                   = w.get("web_alarm_url",                        tk.StringVar()).get().strip()
        # Logs de admin
        srv.enable_server_admin_logs             = bool(w.get("enable_server_admin_logs",             tk.BooleanVar()).get())
        srv.server_admin_logs_include_tribe_logs = bool(w.get("server_admin_logs_include_tribe_logs", tk.BooleanVar()).get())
        srv.server_rcon_output_tribe_logs        = bool(w.get("server_rcon_output_tribe_logs",        tk.BooleanVar()).get())
        srv.notify_admin_commands_in_chat        = bool(w.get("notify_admin_commands_in_chat",        tk.BooleanVar()).get())
        srv.allow_hide_damage_source_from_logs   = bool(w.get("allow_hide_damage_source_from_logs",   tk.BooleanVar()).get())
        try:
            srv.max_tribe_logs = int(w.get("max_tribe_logs", tk.StringVar(value="100")).get())
        except (ValueError, TypeError):
            pass
        srv.tribe_log_destroyed_enemy_structures = bool(w.get("tribe_log_destroyed_enemy_structures", tk.BooleanVar()).get())
        # Auto-respawn
        srv.enable_auto_force_respawn_wild_dinos_interval = bool(w.get("enable_auto_force_respawn_wild_dinos_interval", tk.BooleanVar()).get())
        try:
            srv.server_auto_force_respawn_wild_dinos_interval = int(w.get("server_auto_force_respawn_wild_dinos_interval", tk.StringVar(value="86400")).get())
        except (ValueError, TypeError):
            pass
        # Tributos
        try:
            srv.tribute_character_expiration_seconds = int(w.get("tribute_character_expiration_seconds", tk.StringVar(value="0")).get())
            srv.tribute_item_expiration_seconds      = int(w.get("tribute_item_expiration_seconds",      tk.StringVar(value="0")).get())
            srv.tribute_dino_expiration_seconds      = int(w.get("tribute_dino_expiration_seconds",      tk.StringVar(value="0")).get())
            srv.minimum_dino_reupload_interval       = int(w.get("minimum_dino_reupload_interval",       tk.StringVar(value="0")).get())
        except (ValueError, TypeError):
            pass
        srv.cross_ark_allow_foreign_dino_downloads = bool(w.get("cross_ark_allow_foreign_dino_downloads", tk.BooleanVar()).get())
        # SteamCMD Branch
        srv.branch_name     = w.get("branch_name",     tk.StringVar()).get().strip()
        srv.branch_password = w.get("branch_password", tk.StringVar()).get()
        srv.extra_args            = w.get("extra_args",    tk.StringVar()).get().strip()
        _evt_raw = w.get("active_event", tk.StringVar()).get().strip()
        srv.active_event          = _ARK_EVENT_LABEL_TO_ID.get(_evt_raw, _evt_raw)
        try:
            srv.auto_save_period  = float(w.get("auto_save", tk.StringVar(value="15")).get())
        except ValueError:
            pass
        # MOTD
        motd_box = w.get("motd")
        if motd_box:
            srv.motd = motd_box.get("1.0", "end").rstrip("\n")
        try:
            srv.motd_duration = int(w.get("motd_duration", tk.StringVar(value="60")).get())
        except ValueError:
            pass
        srv.rcon_enabled          = w.get("rcon_enabled",       tk.BooleanVar(value=True)).get()
        srv.use_battleye          = w.get("use_battleye",        tk.BooleanVar()).get()
        srv.use_allcores          = w.get("use_allcores",        tk.BooleanVar()).get()
        srv.force_respawn_dinos   = w.get("force_respawn",       tk.BooleanVar()).get()
        srv.whitelist_only        = w.get("whitelist_only",      tk.BooleanVar()).get()
        srv.auto_restart_on_crash = w.get("auto_restart_crash",  tk.BooleanVar()).get()
        srv.auto_update_on_start  = w.get("auto_update_start",   tk.BooleanVar()).get()
        _cpu_sel = w.get("cpu_core_count", tk.StringVar(value="Padrão (ARK decide)")).get()
        if _cpu_sel.startswith("Todos"):
            srv.cpu_core_count = -1
            srv.use_allcores   = True
        elif _cpu_sel[0].isdigit():
            srv.cpu_core_count = int(_cpu_sel.split()[0])
            srv.use_allcores   = False
        else:
            srv.cpu_core_count = 0
            srv.use_allcores   = False

        # Agendamentos
        _sched_rows = w.get("sched_task_rows", [])
        _al_inv = {"Reiniciar": "restart", "Desligar": "stop", "Atualizar + Reiniciar": "update_restart"}
        _new_tasks = []
        for rd in _sched_rows:
            try:
                _new_tasks.append({
                    "enabled": rd["enabled"].get(),
                    "time": rd["time"].get().strip() or "03:00",
                    "days": [d for d, bv in enumerate(rd["days"]) if bv.get()],
                    "action": _al_inv.get(rd["action"].get(), rd["action"].get()),
                    "warn_minutes": int(rd["warn"].get() or "0"),
                })
            except Exception:
                pass
        srv.scheduled_tasks = _new_tasks

    # Preserva as configurações de backup (gerenciadas pela aba Backup)
    # — não sobrescreve campos backup ao salvar outras abas

    # ── GameSettings ──────────────────────────────────────────────────
    gs = srv.game_settings
    float_gs = [
        "difficulty_offset", "override_official_difficulty",
        "xp_multiplier", "kill_xp_multiplier", "harvest_xp_multiplier",
        "craft_xp_multiplier", "generic_xp_multiplier", "special_xp_multiplier",
        "taming_speed_multiplier", "harvest_amount_multiplier",
        "resource_respawn_period_multiplier", "harvest_health_multiplier",
        "dino_count_multiplier", "player_damage_multiplier",
        "player_resistance_multiplier", "player_character_water_drain_multiplier",
        "player_character_food_drain_multiplier",
        "player_character_health_recovery_multiplier",
        "player_character_stamina_drain_multiplier",
        "dino_damage_multiplier", "dino_resistance_multiplier",
        "dino_character_health_recovery_multiplier",
        "dino_character_food_drain_multiplier",
        "baby_mature_speed_multiplier", "baby_hatch_speed_multiplier",
        "baby_food_consumption_speed_multiplier", "baby_cuddle_interval_multiplier",
        "mating_interval_multiplier", "egg_hatch_speed_multiplier",
        "lay_egg_interval_multiplier", "baby_imprinting_stat_scale_multiplier",
        "baby_cuddle_grace_period_multiplier", "structure_damage_multiplier",
        "structure_resistance_multiplier", "pve_structure_decay_period_multiplier",
        "crop_growth_speed_multiplier", "crop_decay_speed_multiplier",
        "item_stack_size_multiplier", "spoiling_time_multiplier",
        "item_decomposition_time_multiplier", "fishing_loot_quality_multiplier",
        "per_platform_max_structures_multiplier",
        "platform_saddle_build_area_bounds_multiplier",
        "kick_idle_players_period", "tribe_name_change_cooldown",
        "tamed_dino_damage_multiplier", "tamed_dino_resistance_multiplier",
        "dino_character_stamina_drain_multiplier", "dino_turret_damage_multiplier",
        "max_personal_tamed_dinos",
        "day_cycle_speed_scale", "day_time_speed_scale", "night_time_speed_scale",
        "pve_dino_decay_period_multiplier", "auto_destroy_old_structures_multiplier",
        "npc_network_stasis_range_scale_percent_end",
    ]
    int_gs = [
        "max_tamed_dinos", "structure_damage_repair_cooldown",
        "player_level_cap", "dino_level_cap", "max_tribe_size",
        "personal_tamed_dinos_saddle_structure_cost", "max_structures_visible",
        "max_platform_saddle_structure_limit",
        "npc_network_stasis_range_scale_player_count_start",
        "npc_network_stasis_range_scale_player_count_end",
    ]
    bool_gs = [
        "allow_flyer_carry_pve", "disable_structure_decay_pve", "disable_dino_decay_pve",
        "prevent_offline_pvp", "show_map_player_location", "allow_third_person_player",
        "always_notify_player_joined", "always_notify_player_left",
        "server_hardcore", "server_pvp", "no_tribute_downloads",
        "disable_weather_fog", "allow_pvp_gamma", "allow_pve_gamma", "allow_hit_markers",
        "disable_imprint_dino_buff", "allow_anyone_baby_imprint_cuddle",
        "allow_flying_stamina_recovery", "prevent_mate_boost", "allow_multiple_attached_c4",
        "auto_destroy_decayed_dinos", "disable_dino_decay_pvp",
        "pvp_structure_decay", "override_structure_platform_prevention",
        "only_auto_destroy_core_structures", "only_decay_unsnapped_core_structures",
        "fast_decay_unsnapped_core_structures", "destroy_unconnected_water_pipes",
        "allow_cave_building_pve", "pve_allow_structures_at_supply_drops",
        "enable_extra_structure_prevention_volumes", "clamp_resource_harvest_damage",
        "enable_diseases", "non_permanent_diseases", "allow_tribe_alliances",
        "override_npc_network_stasis_range_scale",
    ]
    for f in float_gs:
        key = f"gs_{f}"
        if key in w:
            try:
                setattr(gs, f, float(w[key].get()))
            except (ValueError, TypeError, AttributeError):
                pass
    for f in int_gs:
        key = f"gs_{f}"
        if key in w:
            try:
                setattr(gs, f, int(float(w[key].get())))
            except (ValueError, TypeError, AttributeError):
                pass
    for f in bool_gs:
        key = f"gs_{f}"
        if key in w:
            try:
                setattr(gs, f, bool(w[key].get()))
            except (Exception):
                pass

    # ── PerLevelStatsMultiplier ────────────────────────────────────────────
    for group, attr in [
        ("tamed",          "per_level_stats_mult_dino_tamed"),
        ("tamed_add",      "per_level_stats_mult_dino_tamed_add"),
        ("tamed_affinity", "per_level_stats_mult_dino_tamed_affinity"),
        ("wild",           "per_level_stats_mult_dino_wild"),
        ("player",         "per_level_stats_mult_player"),
    ]:
        vals = list(getattr(gs, attr))
        for i in range(12):
            key = f"gs_plsm_{group}_{i}"
            if key in w:
                try:
                    vals[i] = max(0.0, float(w[key].get()))
                except (ValueError, TypeError):
                    pass
        setattr(gs, attr, vals)

    # ── AdvancedSettings ──────────────────────────────────────────────
    adv = srv.advanced_settings
    adv_bool = [
        "prevent_download_survivors", "prevent_download_items", "prevent_download_dinos",
        "prevent_upload_survivors", "prevent_upload_items", "prevent_upload_dinos",
        "no_transfer_from_filtering", "enable_cryopod_nerf",
        "allow_crateSpawns_on_top_of_structures", "use_optimized_harvesting_health",
        "b_passive_defenses_damage_riderless_dinos", "global_voice_chat",
        "proximity_chat", "allow_raid_dino_feeding", "b_auto_pve_timer",
        "b_auto_pve_use_system_time", "force_all_structure_locking",
        "force_flyer_explosives",
        # v1.3.21
        "use_tame_limit_for_structures_only", "disable_dino_riding", "disable_dino_taming",
        "disable_friendly_fire_pvp", "disable_friendly_fire_pve", "disable_loot_crates",
        "increase_pvp_respawn_interval", "allow_tribe_war_pve", "allow_tribe_war_cancel_pve",
        "allow_custom_recipes", "use_corpse_locator", "allow_unlimited_respecs",
        "allow_platform_saddle_multi_floors", "random_supply_crate_points",
        "disable_structure_placement_collision", "flyer_platform_allow_unaligned_dino_basing",
        "enable_fast_decay_interval", "limit_turrets_in_range", "hard_limit_turrets_in_range",
    ]
    adv_float = [
        "cryopod_nerf_duration", "cryopod_nerf_damage_mult",
        "raid_dino_character_food_drain_multiplier",
        "oxygen_swim_speed_stat_multiplier", "dino_harvesting_damage_multiplier",
        "player_harvesting_damage_multiplier", "custom_recipe_skill_multiplier",
        "custom_recipe_effectiveness_multiplier",
        "auto_pve_start_time_seconds", "auto_pve_stop_time_seconds",
        # v1.3.21
        "passive_tame_interval_multiplier",
        "wild_dino_character_food_drain_multiplier", "tamed_dino_character_food_drain_multiplier",
        "wild_dino_torpor_drain_multiplier", "tamed_dino_torpor_drain_multiplier",
        "baby_cuddle_lose_imprint_quality_speed_multiplier", "base_temperature_multiplier",
        "increase_pvp_respawn_interval_check_period",
        "increase_pvp_respawn_interval_multiplier", "increase_pvp_respawn_interval_base_amount",
        "prevent_offline_pvp_connection_invincible_interval",
        "max_alliances_per_tribe", "max_tribes_per_alliance",
        "supply_crate_loot_quality_multiplier", "use_corpse_life_span_multiplier",
        "global_powered_battery_durability_decrease_per_second",
        "global_corpse_decomposition_time_multiplier", "poop_interval_multiplier",
        "hair_growth_speed_multiplier",
        "resource_no_replenish_radius_players", "resource_no_replenish_radius_structures",
        "crafting_skill_bonus_multiplier", "pvp_zone_structure_damage_multiplier",
        "fast_decay_interval", "limit_turrets_range", "limit_turrets_num",
    ]
    for f in adv_bool:
        if f"adv_{f}" in w:
            try:
                setattr(adv, f, bool(w[f"adv_{f}"].get()))
            except Exception:
                pass
    for f in adv_float:
        if f"adv_{f}" in w:
            try:
                setattr(adv, f, float(w[f"adv_{f}"].get()))
            except (ValueError, TypeError):
                pass

    # ── Spawn de Dinos (aba Spawns) ───────────────────────────────────
    def _collect_spawn_list(store_key: str, is_override: bool) -> list:
        result = []
        for cd in w.get(store_key, []):
            container_var = cd.get("container_var")
            if container_var is None:
                continue
            container_class = container_var.get().strip()
            if not container_class:
                continue
            entries = []
            for ed in cd.get("entries", []):
                name   = ed.get("name_var", tk.StringVar()).get().strip()
                try:
                    weight = float(ed.get("weight_var", tk.StringVar(value="1.0")).get())
                except (ValueError, TypeError):
                    weight = 1.0
                bp_box = ed.get("bp_box")
                if bp_box:
                    bps_raw = bp_box.get("1.0", "end").strip()
                else:
                    bps_raw = ""
                blueprints = [b.strip() for b in bps_raw.splitlines() if b.strip()]
                if name or blueprints:
                    entries.append({"name": name, "weight": weight, "blueprints": blueprints})
            mult = 1.0
            if is_override:
                try:
                    mult = float(cd.get("max_mult_var", tk.StringVar(value="1.0")).get())
                except (ValueError, TypeError):
                    mult = 1.0
            result.append({
                "container": container_class,
                "max_enemies_multiplier": mult,
                "entries": entries,
            })
        return result

    adv.npc_spawn_entries_add      = _collect_spawn_list("spawn_add_list",      is_override=False)
    adv.npc_spawn_entries_override = _collect_spawn_list("spawn_override_list", is_override=True)

    # ── Multiplicadores por Classe de Dino ────────────────────────────────
    def _collect_dino_mult(store_key: str) -> list:
        result = []
        for rd in w.get(store_key, []):
            class_name = rd.get("class_name_var", tk.StringVar()).get().strip()
            if not class_name:
                continue
            try:
                mult = float(rd.get("mult_var", tk.StringVar(value="1.0")).get())
            except ValueError:
                mult = 1.0
            result.append({"class_name": class_name, "multiplier": mult})
        return result

    adv.dino_class_resistance_multipliers       = _collect_dino_mult("dino_res_mult_list")
    adv.dino_class_damage_multipliers           = _collect_dino_mult("dino_dmg_mult_list")
    adv.tamed_dino_class_resistance_multipliers = _collect_dino_mult("tamed_dino_res_mult_list")
    adv.tamed_dino_class_damage_multipliers     = _collect_dino_mult("tamed_dino_dmg_mult_list")

    # ── Supply Crate Overrides ────────────────────────────────────────────
    def _collect_loot_crates() -> list:
        result = []
        for cd in w.get("loot_crate_list", []):
            crate_class = cd.get("crate_class_var", tk.StringVar()).get().strip()
            if not crate_class:
                continue
            try:
                min_sets = int(cd.get("min_sets_var", tk.StringVar(value="1")).get())
            except ValueError:
                min_sets = 1
            try:
                max_sets = int(cd.get("max_sets_var", tk.StringVar(value="1")).get())
            except ValueError:
                max_sets = 1
            try:
                num_sets_pow = float(cd.get("num_sets_power_var", tk.StringVar(value="1.0")).get())
            except ValueError:
                num_sets_pow = 1.0
            sets_no_repl = cd.get("sets_no_repl_var", tk.BooleanVar(value=True)).get()

            item_sets = []
            for isd in cd.get("item_sets", []):
                try:
                    sw = float(isd.get("set_weight_var", tk.StringVar(value="1.0")).get())
                except ValueError:
                    sw = 1.0
                try:
                    mi = int(isd.get("min_items_var", tk.StringVar(value="1")).get())
                except ValueError:
                    mi = 1
                try:
                    mx = int(isd.get("max_items_var", tk.StringVar(value="2")).get())
                except ValueError:
                    mx = 2
                try:
                    pow_ = float(isd.get("num_items_power_var", tk.StringVar(value="1.0")).get())
                except ValueError:
                    pow_ = 1.0
                items_no_repl = isd.get("items_no_repl_var", tk.BooleanVar(value=True)).get()

                entries = []
                for ed in isd.get("entries", []):
                    try:
                        ew = float(ed.get("weight_var", tk.StringVar(value="1.0")).get())
                    except ValueError:
                        ew = 1.0
                    ib = ed.get("items_box")
                    items_raw = ib.get("1.0", "end").strip() if ib else ""
                    items_list = [x.strip() for x in items_raw.splitlines() if x.strip()]
                    if not items_list:
                        continue
                    try:
                        min_q = float(ed.get("min_qty_var", tk.StringVar(value="1.0")).get())
                    except ValueError:
                        min_q = 1.0
                    try:
                        max_q = float(ed.get("max_qty_var", tk.StringVar(value="1.0")).get())
                    except ValueError:
                        max_q = 1.0
                    try:
                        min_ql = float(ed.get("min_ql_var", tk.StringVar(value="1.0")).get())
                    except ValueError:
                        min_ql = 1.0
                    try:
                        max_ql = float(ed.get("max_ql_var", tk.StringVar(value="1.0")).get())
                    except ValueError:
                        max_ql = 1.0
                    fbp = ed.get("force_bp_var", tk.BooleanVar(value=False)).get()
                    try:
                        bpc = float(ed.get("bp_chance_var", tk.StringVar(value="0.0")).get())
                    except ValueError:
                        bpc = 0.0
                    entries.append({
                        "weight": ew, "items": items_list,
                        "min_qty": min_q, "max_qty": max_q,
                        "min_quality": min_ql, "max_quality": max_ql,
                        "force_blueprint": fbp, "blueprint_chance": bpc,
                    })

                item_sets.append({
                    "min_items": mi, "max_items": mx,
                    "num_items_power": pow_, "set_weight": sw,
                    "items_no_replacement": items_no_repl, "entries": entries,
                })

            result.append({
                "crate_class": crate_class,
                "min_sets": min_sets, "max_sets": max_sets,
                "num_sets_power": num_sets_pow,
                "sets_no_replacement": sets_no_repl,
                "item_sets": item_sets,
            })
        return result

    adv.supply_crate_overrides = _collect_loot_crates()

    # ── Cluster ───────────────────────────────────────────────────────
    cl = srv.cluster
    if "cl_enabled" in w:
        cl.enabled              = bool(w["cl_enabled"].get())
        cl.cluster_id           = w.get("cl_cluster_id",  tk.StringVar()).get().strip()
        cl.cluster_dir_override = w.get("cl_cluster_dir", tk.StringVar()).get().strip()
        srv.alt_save_directory_name = w.get("cl_alt_save_dir", tk.StringVar()).get().strip()
    # Perfil de cluster vinculado
    if "cl_profile_id_var" in w:
        srv.cluster_profile_id = w["cl_profile_id_var"].get()

    # ── Config Dinâmica ───────────────────────────────────────────────
    if "dynamic_config_enabled" in w:
        srv.dynamic_config_enabled = bool(w["dynamic_config_enabled"].get())
    if srv.dynamic_config_enabled:
        app._push_dynamic_config(srv.id)
    else:
        app._dynamic_config_server.remove(srv.id)
        url_var = w.get("_dyn_url_var")
        if url_var:
            url_var.set("—")

    # Atualiza título do painel
    if "_name_title_var" in w:
        w["_name_title_var"].set(srv.name)

    # Persiste
    app.config_manager.update_server(srv)
    app.server_manager.update_server_config(srv)

    # Registra alterações no histórico
    try:
        _snap_after = snapshot_server(srv)
        _chg_logger = app._get_change_logger(server_id)
        diff_snapshots(_chg_logger, _snap_before, _snap_after)
    except Exception:
        pass

    # Escreve .ini se o diretório existir
    if srv.install_dir and os.path.isdir(srv.install_dir):
        try:
            ini_mgr = ArkIniManager(srv.install_dir)
            ini_mgr.save_all(srv)
        except Exception as exc:
            app._global_log(f"Erro ao salvar .ini para {srv.name}: {exc}", "error")

        # Grava AllowedCheaterSteamIDs.txt
        # Localização correta: ShooterGame/Saved/
        try:
            import pathlib
            allowed_path = (
                pathlib.Path(srv.install_dir)
                / "ShooterGame" / "Saved"
                / "AllowedCheaterSteamIDs.txt"
            )
            allowed_path.parent.mkdir(parents=True, exist_ok=True)
            allowed_path.write_text("\n".join(srv.admin_ids), encoding="utf-8")
        except Exception as exc:
            app._global_log(
                f"[{srv.name}] Aviso: não foi possível gravar AllowedCheaterSteamIDs.txt: {exc}",
                "warning",
            )

    app._rebuild_server_sidebar()
    app._refresh_dashboard()

    if not silent:
        messagebox.showinfo("Salvo", f"Configurações de '{srv.name}' salvas!", parent=app)

