"""
Configurações de servidor ARK: Survival Evolved.
Inclui todas as opções de GameUserSettings.ini, Game.ini e parâmetros de linha de comando.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List


# ── Mapas disponíveis ──────────────────────────────────────────────────────────
ARK_MAPS = [
    "TheIsland",
    "TheCenter",
    "ScorchedEarth_P",
    "Ragnarok",
    "Aberration_P",
    "Extinction",
    "Valguero_P",
    "Genesis",
    "CrystalIsles",
    "Gen2",
    "LostIsland",
    "Fjordur",
]

# Nomes amigáveis dos mapas
ARK_MAP_NAMES = {
    "TheIsland": "The Island",
    "TheCenter": "The Center",
    "ScorchedEarth_P": "Scorched Earth",
    "Ragnarok": "Ragnarok",
    "Aberration_P": "Aberration",
    "Extinction": "Extinction",
    "Valguero_P": "Valguero",
    "Genesis": "Genesis Part 1",
    "CrystalIsles": "Crystal Isles",
    "Gen2": "Genesis Part 2",
    "LostIsland": "Lost Island",
    "Fjordur": "Fjordur",
}

# ── Status do servidor ─────────────────────────────────────────────────────────
SERVER_STATUS_STOPPED   = "stopped"
SERVER_STATUS_STARTING  = "starting"
SERVER_STATUS_RUNNING   = "running"
SERVER_STATUS_STOPPING  = "stopping"
SERVER_STATUS_CRASHED   = "crashed"
SERVER_STATUS_UPDATING  = "updating"


@dataclass
class ServerGameSettings:
    """Configurações do [ServerSettings] / GameUserSettings.ini"""
    # Dificuldade
    difficulty_offset: float = 0.2
    override_official_difficulty: float = 5.0

    # Multiplicadores gerais
    xp_multiplier: float = 1.0
    taming_speed_multiplier: float = 1.0
    harvest_amount_multiplier: float = 1.0
    resource_respawn_period_multiplier: float = 1.0
    harvest_health_multiplier: float = 1.0
    dino_count_multiplier: float = 1.0
    max_tamed_dinos: int = 5000

    # Jogador
    player_damage_multiplier: float = 1.0
    player_resistance_multiplier: float = 1.0
    player_character_water_drain_multiplier: float = 1.0
    player_character_food_drain_multiplier: float = 1.0
    player_character_health_recovery_multiplier: float = 1.0
    player_character_stamina_drain_multiplier: float = 1.0

    # Dino
    dino_damage_multiplier: float = 1.0
    dino_resistance_multiplier: float = 1.0
    dino_character_health_recovery_multiplier: float = 1.0
    dino_character_food_drain_multiplier: float = 1.0

    # Criação/maturação
    baby_mature_speed_multiplier: float = 1.0
    baby_hatch_speed_multiplier: float = 1.0
    baby_food_consumption_speed_multiplier: float = 1.0
    baby_cuddle_interval_multiplier: float = 1.0
    mating_interval_multiplier: float = 1.0
    egg_hatch_speed_multiplier: float = 1.0
    lay_egg_interval_multiplier: float = 1.0

    # Imprinting
    baby_imprinting_stat_scale_multiplier: float = 1.0
    baby_cuddle_grace_period_multiplier: float = 1.0

    # Estruturas
    structure_damage_multiplier: float = 1.0
    structure_resistance_multiplier: float = 1.0
    structure_damage_repair_cooldown: int = 180
    pve_structure_decay_period_multiplier: float = 1.0
    pve_structure_decay_destruction_period: float = 1.0

    # Plantio
    crop_growth_speed_multiplier: float = 1.0
    crop_decay_speed_multiplier: float = 1.0

    # Opções PvP/PvE
    allow_flyer_carry_pve: bool = True
    disable_structure_decay_pve: bool = False
    disable_dino_decay_pve: bool = False
    prevent_offline_pvp: bool = False
    prevent_offline_pvp_interval: float = 0.0

    # Opções do servidor
    show_map_player_location: bool = True
    allow_third_person_player: bool = True
    always_notify_player_joined: bool = True
    always_notify_player_left: bool = True
    dont_always_notify_player_joined: bool = False
    server_hardcore: bool = False
    server_pvp: bool = True
    no_tribute_downloads: bool = False

    # Custom levels
    override_max_experience_points_player: int = 0
    override_max_experience_points_dino: int = 0

    # Stack
    item_stack_size_multiplier: float = 1.0

    # Spoiling
    spoiling_time_multiplier: float = 1.0
    item_decomposition_time_multiplier: float = 1.0

    # Platform saddle
    platform_saddle_build_area_bounds_multiplier: float = 1.0
    per_platform_max_structures_multiplier: float = 1.0

    # Automático
    kick_idle_players_period: float = 3600.0
    kill_xp_multiplier: float = 1.0
    harvest_xp_multiplier: float = 1.0
    craft_xp_multiplier: float = 1.0
    generic_xp_multiplier: float = 1.0
    special_xp_multiplier: float = 1.0

    # Customização tribal
    max_tribe_size: int = 0
    tribe_name_change_cooldown: float = 0.0

    # Fishing
    fishing_loot_quality_multiplier: float = 1.0


@dataclass
class ServerAdvancedSettings:
    """Configurações avançadas do [/Script/ShooterGame.ShooterGameMode] / Game.ini"""
    # Downloads/Uploads Cross-ARK
    prevent_download_survivors: bool = False
    prevent_download_items: bool = False
    prevent_download_dinos: bool = False
    prevent_upload_survivors: bool = False
    prevent_upload_items: bool = False
    prevent_upload_dinos: bool = False

    # Triforce
    no_transfer_from_filtering: bool = False

    # Engrams
    override_player_level_engram_points: List[int] = field(default_factory=list)

    # Cryopod
    enable_cryopod_nerf: bool = False
    cryopod_nerf_duration: float = 10.0
    cryopod_nerf_damage_mult: float = 0.01

    # Misc game
    allow_crateSpawns_on_top_of_structures: bool = False
    use_optimized_harvesting_health: bool = False
    b_passive_defenses_damage_riderless_dinos: bool = False
    global_voice_chat: bool = False
    proximity_chat: bool = False
    allow_raid_dino_feeding: bool = False
    raid_dino_character_food_drain_multiplier: float = 1.0
    oxygen_swim_speed_stat_multiplier: float = 1.0
    dino_harvesting_damage_multiplier: float = 3.2
    player_harvesting_damage_multiplier: float = 1.0
    custom_recipe_effectiveness_multiplier: float = 1.0
    custom_recipe_skill_multiplier: float = 1.0

    # Booleans de gameplay
    b_auto_pve_timer: bool = False
    b_auto_pve_use_system_time: bool = False
    auto_pve_start_time_seconds: float = 0.0
    auto_pve_stop_time_seconds: float = 0.0
    force_all_structure_locking: bool = False
    force_flyer_explosives: bool = False


@dataclass
class ClusterConfig:
    """Configurações de Cross-ARK (Cluster)."""
    enabled: bool = False
    cluster_id: str = ""
    cluster_dir_override: str = ""
    prevent_download_survivors: bool = False
    prevent_download_items: bool = False
    prevent_download_dinos: bool = False
    no_transfer_from_filtering: bool = False


@dataclass
class ServerConfig:
    """Configuração completa de uma instância de servidor ARK."""
    # Identificação
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "ARK Server"

    # Localização
    install_dir: str = ""
    server_exe: str = "ShooterGameServer.exe"

    # Rede
    map: str = "TheIsland"
    server_port: int = 7777
    query_port: int = 27015
    rcon_port: int = 27020
    rcon_enabled: bool = True
    rcon_password: str = ""

    # Acesso
    server_name: str = "My ARK Server"
    server_password: str = ""
    admin_password: str = ""
    max_players: int = 70
    whitelist_only: bool = False

    # Mods (IDs do Steam Workshop)
    mods: List[str] = field(default_factory=list)

    # Nomes dos mods {"mod_id": "Nome do Mod"}
    mod_names: Dict[str, str] = field(default_factory=dict)

    # Configurações INI por mod  {"mod_id": {"game_ini": "...", "gus_ini": "..."}}
    mod_ini_configs: Dict[str, dict] = field(default_factory=dict)

    # Opções de linha de comando adicionais
    extra_args: str = ""
    use_battleye: bool = False
    force_respawn_dinos: bool = False
    use_allcores: bool = False
    auto_save_period: float = 15.0
    active_event: str = ""

    # Configurações do jogo
    game_settings: ServerGameSettings = field(default_factory=ServerGameSettings)
    advanced_settings: ServerAdvancedSettings = field(default_factory=ServerAdvancedSettings)
    cluster: ClusterConfig = field(default_factory=ClusterConfig)

    # Controle interno
    auto_restart_on_crash: bool = False
    auto_update_on_start: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "ServerConfig":
        game = ServerGameSettings(**{
            k: v for k, v in data.get("game_settings", {}).items()
            if k in ServerGameSettings.__dataclass_fields__
        })
        adv = ServerAdvancedSettings(**{
            k: v for k, v in data.get("advanced_settings", {}).items()
            if k in ServerAdvancedSettings.__dataclass_fields__
        })
        cluster = ClusterConfig(**{
            k: v for k, v in data.get("cluster", {}).items()
            if k in ClusterConfig.__dataclass_fields__
        })
        top_fields = {
            k: v for k, v in data.items()
            if k in cls.__dataclass_fields__
            and k not in ("game_settings", "advanced_settings", "cluster")
        }
        return cls(**top_fields, game_settings=game, advanced_settings=adv, cluster=cluster)

    def build_launch_args(self) -> str:
        """Monta a linha de comando completa para iniciar o servidor."""
        exe_path = self.server_exe
        map_arg = self.map

        params = [
            "?listen",
            f"?SessionName=\"{self.server_name}\"",
            f"?MaxPlayers={self.max_players}",
            f"?Port={self.server_port}",
            f"?QueryPort={self.query_port}",
        ]

        if self.server_password:
            params.append(f"?ServerPassword={self.server_password}")
        if self.admin_password:
            params.append(f"?ServerAdminPassword={self.admin_password}")
        if self.rcon_enabled:
            params.append("?RCONEnabled=True")
            params.append(f"?RCONPort={self.rcon_port}")
        if self.whitelist_only:
            params.append("?ExclusiveJoin")
        if self.active_event:
            params.append(f"?ActiveEvent={self.active_event}")
        if self.auto_save_period != 15.0:
            params.append(f"?AutoSavePeriodMinutes={self.auto_save_period}")

        # Cluster
        if self.cluster.enabled and self.cluster.cluster_id:
            params.append(f"?ClusterID={self.cluster.cluster_id}")
            if self.cluster.cluster_dir_override:
                params.append(f"?ClusterDirOverride=\"{self.cluster.cluster_dir_override}\"")

        # Mods
        if self.mods:
            params.append(f"?GameModIds={','.join(self.mods)}")

        flags = [
            "-server",
            "-log",
            "-nosteamclient",
            "-game",
            f"-port={self.server_port}",
            f"-queryport={self.query_port}",
        ]

        if not self.use_battleye:
            flags.append("-NoBattlEye")
        if self.use_allcores:
            flags.append("-useallavailablecores")
        if self.force_respawn_dinos:
            flags.append("-ForceRespawnDinos")

        if self.cluster.enabled:
            if self.cluster.prevent_download_survivors:
                flags.append("-NoTransferFromFiltering")
            if self.cluster.cluster_dir_override:
                flags.append(f'-clusterdir="{self.cluster.cluster_dir_override}"')

        if self.extra_args:
            flags.append(self.extra_args)

        args_str = "".join(params)
        flags_str = " ".join(flags)
        return f'"{exe_path}" {map_arg}{args_str} {flags_str}'
