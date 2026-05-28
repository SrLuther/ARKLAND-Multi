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
    cross_ark_cluster_id:       str  = ""
    cluster_dir_override:       str  = ""

    # Args extras CLI
    additional_args: str = ""

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

    # ── Engrams (override de custo/disponibilidade) ───────────────────────────
    # Cada item: {"class_name": str, "hidden": bool, "force_unlock": bool, "cost": int, "reqs": int}
    engram_overrides: List[dict] = field(default_factory=list)

    # ── Levels (tabelas de XP / Engram Points) ────────────────────────────────
    # Cada item: {"xp": int, "engram_points": int} — jogador e dino separados
    player_level_xp_overrides:   List[dict] = field(default_factory=list)
    dino_level_xp_overrides:     List[dict] = field(default_factory=list)

    # ── Custom INI livre (editor avançado) ────────────────────────────────────
    # Seções extras a injetar direto no GUS ou Game.ini
    # {"file": "GameUserSettings.ini"|"Game.ini", "section": str, "entries": [{"key":str,"value":str}]}
    custom_ini_sections: List[dict] = field(default_factory=list)

    # ── Metadados internos ────────────────────────────────────────────────────
    notes: str = ""

    # ─────────────────────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AsmServerConfig":
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid})


# Constantes de status (espelham as do PRIMITIVE para compatibilidade de UI)
ASM_STATUS_STOPPED  = "stopped"
ASM_STATUS_STARTING = "starting"
ASM_STATUS_RUNNING  = "running"
ASM_STATUS_STOPPING = "stopping"
ASM_STATUS_CRASHED  = "crashed"
ASM_STATUS_UPDATING = "updating"
