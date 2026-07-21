"""
AsmServerConfig — dataclass com todos os ~300 campos do ARK Server Manager (ASM).
Fiel ao ServerProfile.cs do ASM original.
Dados salvos em %APPDATA%\\ARKLAND-ServerManager\\asm_servers.json
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, fields, asdict
from typing import List, Optional


@dataclass
class AsmServerConfig:
    """Configuração completa de um servidor TEK (fiel ao ASM ServerProfile.cs)."""

    # ── Identificação ────────────────────────────────────────────────────────
    id:   str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "ARK Server TEK"   # Nome interno no gerenciador (não vai ao INI)

    # ── Localização ──────────────────────────────────────────────────────────
    install_dir:  str = ""
    user_config_folder: str = ""   # Pasta ASE custom de INI (sync → WindowsServer no start)
    server_exe:   str = "ShooterGameServer.exe"

    # ── Administration ───────────────────────────────────────────────────────
    session_name:        str  = "My ARK Server"
    server_password:     str  = ""
    admin_password:      str  = ""
    spectator_password:  str  = ""
    server_ip:           str  = ""                # MultiHome (só inclui se preenchido)
    server_port:         int  = 7777
    query_port:          int  = 27015
    rcon_enabled:        bool = True
    rcon_port:           int  = 27020
    rcon_log_buffer:     int  = 600               # RCONServerGameLogBuffer
    admin_logging:       bool = False
    max_players:         int  = 70

    # Mods (lista de IDs Steam Workshop)
    active_mods:         List[str] = field(default_factory=list)

    # Sessão / save
    server_map:                 str   = "TheIsland"
    total_conversion_mod_id:    str   = ""
    alt_save_directory_name:    str   = "savegame"
    auto_save_period:           float = 15.0
    kick_idle_players:          float = 3600.0
    enable_ban_list_url:        bool  = False
    ban_list_url:               str   = "http://arkdedicated.com/banlist.txt"
    motd:                       str   = ""
    motd_duration:              int   = 20

    # Branch SteamCMD
    branch_name:     str = ""            # ex: "experimental"
    branch_password: str = ""

    # Cluster cross-ARK
    cluster_profile_id:         str  = ""
    cross_ark_cluster_id:       str  = ""
    cluster_dir_override:       str  = ""

    # Args extras CLI
    additional_args: str = ""

    # ── CLI / Linha de comando (paridade server_config.py) ───────────────────
    use_battleye: bool = False
    force_respawn_dinos: bool = False
    use_allcores: bool = False
    active_event: str = ""
    crossplay: bool = False
    epic_only: bool = False
    use_vivox: bool = False
    use_item_dupe_check: bool = False
    use_raw_sockets: bool = False
    no_net_threading: bool = False
    force_net_threading: bool = False
    public_ip_for_epic: str = ""
    no_transfer_from_filtering: bool = False
    disable_vac: bool = False
    disable_anti_speed_hack: bool = False
    speed_hack_bias: float = 1.0
    disable_player_move_physics_opt: bool = False
    use_cache: bool = False
    use_old_save_format: bool = False
    use_no_memory_bias: bool = False
    stasis_keep_controllers: bool = False
    use_no_hang_detection: bool = False
    server_allow_ansel: bool = False
    no_dinos: bool = False
    force_dx10: bool = False
    force_shader_model4: bool = False
    force_low_memory: bool = False
    enable_auto_destroy_structures: bool = False
    enable_no_fish_loot: bool = False
    enable_web_alarm: bool = False
    web_alarm_key: str = ""
    web_alarm_url: str = ""
    enable_server_admin_logs: bool = False
    server_admin_logs_include_tribe_logs: bool = False
    server_rcon_output_tribe_logs: bool = False
    notify_admin_commands_in_chat: bool = False

    def __post_init__(self) -> None:
        if not self.alt_save_directory_name or not self.alt_save_directory_name.strip():
            self.alt_save_directory_name = "savegame"

    # ── Rules ─────────────────────────────────────────────────────────────────
    enable_hardcore:                 bool  = False
    enable_pvp:                      bool  = True    # ServerPVE = not enable_pvp
    allow_cave_building_pve:         bool  = False
    disable_friendly_fire_pvp:       bool  = False   # bDisableFriendlyFire
    disable_friendly_fire_pve:       bool  = False   # bPvEDisableFriendlyFire
    disable_loot_crates:             bool  = False
    enable_difficulty_override:      bool  = False
    override_official_difficulty:    float = 5.0
    difficulty_offset:               float = 0.2
    max_tribe_size:                  int   = 0
    enable_tribute_downloads:        bool  = True    # NoTributeDownloads = not enable_tribute_downloads
    prevent_download_survivors:      bool  = False
    prevent_download_items:          bool  = False
    prevent_download_dinos:          bool  = False
    prevent_upload_survivors:        bool  = False
    prevent_upload_items:            bool  = False
    prevent_upload_dinos:            bool  = False
    allow_pvp_gamma:                 bool  = False
    allow_tribe_alliances:           bool  = True    # PreventTribeAlliances = not allow_tribe_alliances
    allow_custom_recipes:            bool  = True
    enable_diseases:                 bool  = True    # PreventDiseases = not enable_diseases
    prevent_pvp_offline:             bool  = False
    enable_cryo_sickness_pvp:        bool  = False
    auto_pve_timer:                  bool  = False

    # ── ChatAndNotifications ──────────────────────────────────────────────────
    global_voice_chat:              bool = False
    proximity_chat:                 bool = False
    player_leave_notifications:     bool = True
    player_joined_notifications:    bool = True

    # ── HudAndVisuals ─────────────────────────────────────────────────────────
    allow_crosshair:            bool = True
    allow_hud:                  bool = True    # ServerForceNoHud = not allow_hud
    allow_third_person_view:    bool = True
    show_map_player_location:   bool = True
    show_floating_damage_text:  bool = False
    allow_hit_markers:          bool = True

    # ── Players ───────────────────────────────────────────────────────────────
    xp_multiplier:                       float = 1.0
    player_damage_multiplier:            float = 1.0
    player_resistance_multiplier:        float = 1.0
    player_water_drain_multiplier:       float = 1.0
    player_food_drain_multiplier:        float = 1.0
    player_stamina_drain_multiplier:     float = 1.0
    player_health_recovery_multiplier:   float = 1.0
    player_harvesting_damage_multiplier: float = 1.0
    crafting_skill_bonus_multiplier:     float = 1.0
    enable_flyer_carry:                  bool  = False
    override_max_xp_player:             int   = 0
    player_base_level:                  int   = 0   # 0 = vanilla 105; nível sem ascensões/bônus
    player_ascension_state:             str   = ""  # JSON: bosses {id:tier 0-3}, extras {id:bool}
    player_engram_points_multiplier:    float = 1.0  # Multiplica os 8 pts vanilla por nível (5.0 = 40/nível)
    # Curva de XP / rampa (unificação nível máximo — ver PLAYER_MAX_LEVEL_SPEC.md)
    player_xp_curve_mode:               str   = "vanilla"  # vanilla | custom
    player_xp_curve_base:               int   = 70
    player_xp_curve_mult:               float = 1.05  # ≤1.08; 1.15 torna pós-100 impraticável
    player_xp_curve_formula:            str   = "base * (mult ** i)"
    player_ramp_entry_count:            int   = 0   # lido do Game.ini ou derivado no save
    player_ramp_max_index:              int   = -1
    # False = modo simples ASM (EnableLevelProgressions=false): só cap GUS, sem rampa/engrams no Game.ini
    player_level_progressions_enabled:  bool  = False

    # ── Dinos ─────────────────────────────────────────────────────────────────
    dino_damage_multiplier:              float = 1.0
    tamed_dino_damage_multiplier:        float = 1.0
    dino_resistance_multiplier:          float = 1.0
    tamed_dino_resistance_multiplier:    float = 1.0
    max_tamed_dinos:                     int   = 5000
    dino_count_multiplier:               float = 1.0
    taming_speed_multiplier:             float = 1.0
    mating_interval_multiplier:          float = 1.0
    egg_hatch_speed_multiplier:          float = 1.0
    baby_mature_speed_multiplier:        float = 1.0
    baby_food_consumption_multiplier:    float = 1.0
    baby_cuddle_interval_multiplier:     float = 1.0
    baby_imprinting_stat_scale:          float = 1.0
    disable_imprint_buff:                bool  = False
    allow_anyone_baby_imprint:           bool  = False
    disable_dino_riding:                 bool  = False
    disable_dino_taming:                 bool  = False
    allow_flyer_speed_leveling:          bool  = False   # bAllowFlyerSpeedLeveling (Game.ini)
    passive_tame_interval_multiplier:    float = 1.0
    dino_harvesting_damage_multiplier:   float = 3.2
    allow_cave_flyers:                   bool  = False   # CLI flag -ForceAllowCaveFlyers
    disable_dino_decay_pve:              bool  = False
    pvp_dino_decay:                      bool  = False   # PvPDinoDecay= (inverted)

    # ── Environment ───────────────────────────────────────────────────────────
    harvest_amount_multiplier:                float = 1.0
    harvest_health_multiplier:                float = 1.0
    resources_respawn_multiplier:             float = 1.0
    day_cycle_speed_scale:                    float = 1.0
    day_time_speed_scale:                     float = 1.0
    night_time_speed_scale:                   float = 1.0
    global_spoiling_time_multiplier:          float = 1.0
    global_item_decomposition_multiplier:     float = 1.0
    global_corpse_decomposition_multiplier:   float = 1.0
    crop_decay_speed_multiplier:              float = 1.0
    crop_growth_speed_multiplier:             float = 1.0
    hair_growth_speed_multiplier:             float = 1.0
    base_temperature_multiplier:              float = 1.0
    disable_weather_fog:                      bool  = False

    # ── Structures ────────────────────────────────────────────────────────────
    structure_resistance_multiplier:             float = 1.0
    structure_damage_multiplier:                 float = 1.0
    max_structures_in_range:                     int   = 10500
    per_platform_max_structures_multiplier:      float = 1.0
    max_platform_saddle_structures:              int   = 130
    enable_structure_decay_pve:                  bool  = False  # DisableStructureDecayPVE (inverted)
    pve_structure_decay_period_multiplier:       float = 1.0
    pve_structure_decay_destruction_period:      float = 1.0
    auto_destroy_old_structures_multiplier:      float = 0.0
    force_all_structure_locking:                 bool  = False
    disable_structure_placement_collision:       bool  = False
    limit_turrets_in_range:                      bool  = False
    limit_turrets_range:                         int   = 10000
    limit_turrets_num:                           int   = 100

    # ── Administration extras ────────────────────────────────────────────────
    max_tribe_logs:                          int   = 100
    tribe_log_destroyed_enemy_structures:    bool  = False
    allow_hide_damage_source:                bool  = False
    enable_extinction_event:                 bool  = False
    extinction_event_interval:               int   = 0
    extinction_event_utc:                    int   = 0
    enable_auto_respawn_wild_dinos:          bool  = False
    auto_respawn_wild_dinos_interval:        int   = 0
    enable_kick_idle_players:                bool  = False

    # ── Rules extras ─────────────────────────────────────────────────────────
    disable_loot_crates_extra:               bool  = False  # alias removido — mantido para compatibilidade de JSON antigo
    enable_extra_structure_prevention_volumes: bool = False
    allow_pve_gamma:                         bool  = False   # AllowPvEGamma / DisablePvEGamma inverted
    oxygen_swim_speed_stat_multiplier:       float = 1.0
    supply_crate_loot_quality_multiplier:    float = 1.0
    fishing_loot_quality_multiplier:         float = 1.0
    use_corpse_life_span_multiplier:         float = 1.0
    global_powered_battery_durability_decrease: float = 0.0
    tribe_name_change_cooldown:              int   = 0
    random_supply_crate_points:              bool  = False
    increase_pvp_respawn_interval:           bool  = False
    pvp_respawn_check_period:                int   = 300
    pvp_respawn_multiplier:                  float = 2.0
    pvp_respawn_base_amount:                 int   = 0
    prevent_pvp_offline_interval:            int   = 0
    prevent_pvp_offline_invincible_interval: int   = 5
    auto_pve_use_system_time:                bool  = False
    auto_pve_start_time:                     int   = 0
    auto_pve_stop_time:                      int   = 0
    allow_tribe_war_pve:                     bool  = False
    allow_tribe_war_cancel_pve:              bool  = False
    custom_recipe_effectiveness_multiplier:  float = 1.0
    custom_recipe_skill_multiplier:          float = 1.0
    non_permanent_diseases:                  bool  = False
    override_npc_stasis_range_scale:         bool  = False
    npc_stasis_range_scale_start:            int   = 0
    npc_stasis_range_scale_end:              int   = 0
    npc_stasis_range_scale_percent_end:      float = 0.5
    use_corpse_locator:                      bool  = False
    prevent_spawn_animations:               bool  = False
    allow_unlimited_respecs:                 bool  = False
    allow_platform_saddle_multi_floors:      bool  = False
    max_alliances_per_tribe:                 int   = 10
    max_tribes_per_alliance:                 int   = 10
    save_tribute_char_expiration:            bool  = False
    tribute_char_expiration_seconds:         int   = 86400
    save_tribute_item_expiration:            bool  = False
    tribute_item_expiration_seconds:         int   = 86400
    save_tribute_dino_expiration:            bool  = False
    tribute_dino_expiration_seconds:         int   = 86400
    save_min_dino_reupload_interval:         bool  = False
    min_dino_reupload_interval:              int   = 0
    cross_ark_allow_foreign_dino_downloads:  bool  = False

    # ── Dinos extras ─────────────────────────────────────────────────────────
    dino_char_food_drain_multiplier:                  float = 1.0
    dino_char_stamina_drain_multiplier:               float = 1.0
    dino_char_health_recovery_multiplier:             float = 1.0
    allow_raid_dino_feeding:                          bool  = False
    raid_dino_food_drain_multiplier:                  float = 1.0
    allow_flying_stamina_recovery:                    bool  = False
    prevent_mate_boost:                               bool  = False
    auto_destroy_decayed_dinos:                       bool  = False
    pve_dino_decay_period_multiplier:                 float = 1.0
    allow_multiple_attached_c4:                       bool  = False
    max_personal_tamed_dinos:                         float = 0.0
    personal_tamed_dinos_saddle_structure_cost:       int   = 19
    use_tame_limit_for_structures_only:               bool  = False
    wild_dino_char_food_drain_multiplier:             float = 1.0
    tamed_dino_char_food_drain_multiplier:            float = 1.0
    wild_dino_torpor_drain_multiplier:                float = 1.0
    tamed_dino_torpor_drain_multiplier:               float = 1.0
    override_max_xp_dino:                             int   = 0
    baby_cuddle_grace_period_multiplier:              float = 1.0
    baby_cuddle_lose_imprint_quality_speed_multiplier: float = 1.0
    dino_turret_damage_multiplier:                    float = 1.0

    # ── Environment extras ───────────────────────────────────────────────────
    craft_xp_multiplier:                     float = 1.0
    generic_xp_multiplier:                   float = 1.0
    harvest_xp_multiplier:                   float = 1.0
    kill_xp_multiplier:                      float = 1.0
    special_xp_multiplier:                   float = 1.0
    lay_egg_interval_multiplier:             float = 1.0
    poop_interval_multiplier:                float = 1.0
    resource_no_replenish_radius_players:    float = 1.0
    resource_no_replenish_radius_structures: float = 1.0
    use_optimized_harvesting_health:         bool  = False
    clamp_resource_harvest_damage:           bool  = False
    clamp_item_spoiling_times:               bool  = False

    # ── Structures extras ────────────────────────────────────────────────────
    pvp_structure_decay:                         bool  = False
    pvp_zone_structure_damage_multiplier:        float = 6.0
    structure_damage_repair_cooldown:            int   = 180
    override_structure_platform_prevention:      bool  = False
    flyer_platform_allow_unaligned_dino_basing:  bool  = False
    always_allow_structure_pickup:               bool  = False   # AlwaysAllowStructurePickup (GUS)
    pve_allow_structures_at_supply_drops:        bool  = False
    only_auto_destroy_core_structures:           bool  = False
    only_decay_unsnapped_core_structures:        bool  = False
    fast_decay_unsnapped_core_structures:        bool  = False
    destroy_unconnected_water_pipes:             bool  = False
    enable_fast_decay_interval:                  bool  = False
    fast_decay_interval:                         int   = 43200
    hard_limit_turrets_in_range:                 bool  = False
    passive_defenses_damage_riderless_dinos:     bool  = False

    # ── Engrams ───────────────────────────────────────────────────────────────
    only_allow_specified_engrams:    bool = False
    auto_unlock_all_engrams:         bool = False
    engram_entries_raw:              str  = ""  # raw Game.ini lines OverrideNamedEngramEntries=...

    # ── Levels (tabelas de XP / Engram Points) ────────────────────────────────
    player_level_stats_raw:  str = ""  # raw Game.ini LevelExperienceRampOverrides / OverridePlayerLevelEngramPoints
    dino_level_stats_raw:    str = ""  # raw Game.ini OverrideMaxExperiencePointsDino / LevelExperienceRampOverrides

    # ── Multiplicadores por nível (PerLevelStatsMultiplier) ───────────────────
    # Índices 0-11: Health, Stamina, Torpidity, Oxygen, Food, Water, Temperature,
    #              Weight, MeleeDamage, MovementSpeed, Fortitude, CraftingSkill
    per_level_player:            List[float] = field(default_factory=lambda: [1.0] * 12)
    per_level_dino_wild:         List[float] = field(default_factory=lambda: [1.0] * 12)
    per_level_dino_tamed:        List[float] = field(default_factory=lambda: [1.0] * 12)
    per_level_dino_tamed_add:    List[float] = field(default_factory=lambda: [0.14] * 12)
    per_level_dino_tamed_affinity: List[float] = field(default_factory=lambda: [0.44] * 12)

    # ── Extensões SM (Fase 5 — campos do painel clássico sem ASM original) ───
    item_stack_size_multiplier:                  float = 1.0
    spoiling_time_multiplier:                    float = 1.0
    item_decomposition_time_multiplier:          float = 1.0
    platform_saddle_build_area_bounds_multiplier: float = 1.0
    max_tribute_dinos:                           int   = 20
    max_tribute_items:                           int   = 50
    baby_imprint_amount_multiplier:              float = 1.0
    enable_creative_mode:                        bool  = False

    # ── Editores agregados (Game.ini — chaves repetidas, Fase 4) ─────────────
    harvest_resource_multipliers:            List[dict] = field(default_factory=list)
    dino_class_resistance_multipliers:       List[dict] = field(default_factory=list)
    dino_class_damage_multipliers:           List[dict] = field(default_factory=list)
    tamed_dino_class_resistance_multipliers: List[dict] = field(default_factory=list)
    tamed_dino_class_damage_multipliers:     List[dict] = field(default_factory=list)
    dino_spawn_weight_multipliers:           List[dict] = field(default_factory=list)
    prevent_dino_tame_class_names:           List[str] = field(default_factory=list)

    # ── Substituições avançadas (texto livre no formato INI do ARK) ──────────
    crafting_overrides_raw:    str = ""  # ConfigOverrideItemCraftingCosts=...
    stack_size_overrides_raw:  str = ""  # ConfigOverrideItemMaxQuantity=...
    npc_spawn_overrides_raw:   str = ""  # ConfigAddNPCSpawnEntriesContainer / ConfigSubtract / ConfigOverride
    supply_crate_overrides_raw: str = "" # ConfigOverrideSupplyCrateItems=...
    prevent_transfer_raw:      str = ""  # PreventTransferForClassNames=... (GUS)

    # ── Arquivos do Servidor ──────────────────────────────────────────────────
    admin_ids:              List[str] = field(default_factory=list)
    whitelist_ids:          List[str] = field(default_factory=list)
    exclusive_join_ids:     List[str] = field(default_factory=list)
    exclusive_join:         bool      = False   # CLI flag -exclusivejoin

    # ── Gerenciamento Automático ──────────────────────────────────────────────
    auto_start_on_launch:           bool  = False   # Iniciar ao abrir o app
    enable_auto_restart:            bool  = False
    auto_restart_time:              str   = "03:00"
    auto_restart_days:              List[int] = field(default_factory=lambda: list(range(7)))  # 0=Seg … 6=Dom
    restart_countdown_minutes:      int   = 15
    enable_auto_update_check:       bool  = False
    auto_update_check_minutes:      int   = 60
    notify_discord_on_events:       bool  = False

    # ── Desempenho do Processo ────────────────────────────────────────────────
    cpu_affinity_cores:     List[int] = field(default_factory=list)  # [] = todos os cores
    process_priority:       str       = "normal"  # normal|above_normal|high|realtime

    # ── Discord Bot ───────────────────────────────────────────────────────────
    discord_webhook_url:            str   = ""
    discord_notify_server_start:    bool  = False
    discord_notify_server_stop:     bool  = False
    discord_notify_player_join:     bool  = False
    discord_notify_player_leave:    bool  = False

    # ── ARK Procedural (PGM) ─────────────────────────────────────────────────
    pgm_enabled:            bool = False
    pgm_name:               str  = ""
    pgm_terrain_string:     str  = ""  # PGTerrainPropertiesString raw

    # ── Custom INI livre (editor avançado) ────────────────────────────────────
    custom_gus_ini_raw:     str  = ""  # texto livre → GameUserSettings.ini
    custom_game_ini_raw:    str  = ""  # texto livre → Game.ini
    custom_engine_ini_raw:  str  = ""  # texto livre → Engine.ini
    # legado — mantido para compatibilidade de dados antigos
    custom_ini_sections: List[dict] = field(default_factory=list)

    # ── Loja CustomShop ───────────────────────────────────────────────────────
    shop_server_id: str = ""
    cross_chat_label: str = ""
    customshop_config_path: str = ""
    shop_show_on_home: bool = True
    shop_exclude: bool = False

    # ── Metadados internos ────────────────────────────────────────────────────
    notes:  str = ""
    color:  str = ""           # cor customizada do card (ex: "#22c55e"). Vazio = padrão
    tags:   List[str] = field(default_factory=list)  # etiquetas livres
    folder: str = ""           # grupo/pasta no dashboard (ex: "Cluster #1")

    # ─────────────────────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AsmServerConfig":
        from ..player_level_ramp import infer_player_level_progressions_enabled, migrate_player_level_dict

        data = dict(data)
        pl = data.pop("player_level", None)
        if isinstance(pl, dict):
            migrate_player_level_dict(data, pl)
        if "player_level_progressions_enabled" not in data:
            data["player_level_progressions_enabled"] = infer_player_level_progressions_enabled(data)

        field_map = {f.name: f for f in fields(cls)}
        defaults = cls()
        kwargs: dict = {}
        for key, raw in data.items():
            if key not in field_map:
                continue
            kwargs[key] = _coerce_config_field(field_map[key], raw, defaults)
        from ..ui_constants import normalize_active_event
        if "active_event" in kwargs:
            kwargs["active_event"] = normalize_active_event(kwargs.get("active_event", ""))
        return cls(**kwargs)


def _coerce_config_field(field_def, value, defaults: "AsmServerConfig"):
    """Normaliza valores vindos de JSON/preset para o tipo do dataclass."""
    if value is None:
        return getattr(defaults, field_def.name)

    ftype = field_def.type
    ftype_str = str(ftype)

    if ftype is bool or ftype_str == "bool":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("true", "1", "yes")

    if ftype is int or ftype_str == "int":
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return getattr(defaults, field_def.name)

    if ftype is float or ftype_str == "float":
        try:
            return float(value)
        except (TypeError, ValueError):
            return getattr(defaults, field_def.name)

    if "List" in ftype_str or ftype is list:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [x.strip() for x in value.split(",") if x.strip()]
        return getattr(defaults, field_def.name)

    return value


# Constantes de status (espelham as do PRIMITIVE para compatibilidade de UI)
ASM_STATUS_STOPPED  = "stopped"
ASM_STATUS_STARTING = "starting"
ASM_STATUS_RUNNING  = "running"
ASM_STATUS_STOPPING = "stopping"
ASM_STATUS_CRASHED  = "crashed"
ASM_STATUS_UPDATING = "updating"


def is_config_editable(status: str) -> bool:
    """True quando o perfil pode ser gravado com segurança (servidor parado)."""
    return status in (ASM_STATUS_STOPPED, ASM_STATUS_CRASHED)
