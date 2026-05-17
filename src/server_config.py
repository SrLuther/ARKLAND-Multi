"""
Configurações de servidor ARK: Survival Evolved.
Inclui todas as opções de GameUserSettings.ini, Game.ini e parâmetros de linha de comando.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


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
    "Aquatica",
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
    "Aquatica": "Aquatica",
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
    player_level_cap: int = 0   # Nível-teto do jogador (0 = sem override). INI calculado pelo app.
    dino_level_cap: int = 0     # Nível-teto do dino   (0 = sem override). INI calculado pelo app.

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

    # Multiplicadores de stats por nível — Game.ini PerLevelStatsMultiplier_*
    # Índices: 0=Vida, 1=Stamina, 2=Torpor, 3=Oxigênio, 4=Comida, 5=Água,
    #          6=Temperatura, 7=Peso, 8=Dano, 9=Velocidade, 10=Fortitude, 11=Craft
    per_level_stats_mult_dino_tamed:          List[float] = field(default_factory=lambda: [1.0] * 12)
    per_level_stats_mult_dino_tamed_add:      List[float] = field(default_factory=lambda: [1.0] * 12)  # TaM — bônus aditivo pós-tame
    per_level_stats_mult_dino_tamed_affinity: List[float] = field(default_factory=lambda: [1.0] * 12)  # TmM — bônus multiplicativo via TE
    per_level_stats_mult_dino_wild:           List[float] = field(default_factory=lambda: [1.0] * 12)
    per_level_stats_mult_player:              List[float] = field(default_factory=lambda: [1.0] * 12)


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

    # Spawn de Dinos Customizados (Game.ini)
    # Cada item é um dict com chaves:
    #   "container": str  — ex: "DinoSpawnEntriesBeach_C"
    #   "max_enemies_multiplier": float  — somente override; padrão 1.0
    #   "entries": List[dict]  — cada entry: {"name": str, "weight": float, "blueprints": List[str]}
    npc_spawn_entries_add: List[dict] = field(default_factory=list)
    npc_spawn_entries_override: List[dict] = field(default_factory=list)

    # Multiplicadores de dano e resistência por classe de dino (Game.ini)
    # Cada item: {"class_name": str, "multiplier": float}
    dino_class_resistance_multipliers: List[dict] = field(default_factory=list)
    dino_class_damage_multipliers: List[dict] = field(default_factory=list)
    tamed_dino_class_resistance_multipliers: List[dict] = field(default_factory=list)
    tamed_dino_class_damage_multipliers: List[dict] = field(default_factory=list)

    # Substituição de itens de supply crates — ConfigOverrideSupplyCrateItems (Game.ini)
    supply_crate_overrides: List[dict] = field(default_factory=list)


@dataclass
class ClusterConfig:
    """Configurações de Cross-ARK (Cluster) — configuração manual por servidor (legado)."""
    enabled: bool = False
    cluster_id: str = ""
    cluster_dir_override: str = ""
    prevent_download_survivors: bool = False
    prevent_download_items: bool = False
    prevent_download_dinos: bool = False
    no_transfer_from_filtering: bool = False


@dataclass
class ClusterProfile:
    """Perfil de cluster cross-ARK compartilhado entre múltiplos servidores.

    Modes:
      "local"   — servidores na mesma máquina gerenciados pelo mesmo app;
                  cluster_dir aponta para uma pasta local acessível por todos.
      "network" — servidores em máquinas diferentes na mesma rede;
                  cluster_dir deve ser um caminho UNC (\\\\servidor\\pasta)
                  ou uma unidade de rede mapeada acessível em todas as máquinas.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Novo Cluster"
    mode: str = "local"           # "local" | "network"
    cluster_id: str = field(default_factory=lambda: str(uuid.uuid4()).replace("-", "")[:20])
    cluster_dir: str = ""         # Pasta local ou UNC/mapeada
    prevent_download_survivors: bool = False
    prevent_download_items: bool = False
    prevent_download_dinos: bool = False
    no_transfer_from_filtering: bool = False
    # Sincronização automática de dados de viagem (local ↔ rede)
    sync_enabled: bool = False       # Ativa sync automático local_cluster_dir ↔ cluster_dir
    local_cluster_dir: str = ""      # Pasta local onde o ARK grava os dados de viagem
    sync_interval: int = 30          # Intervalo em segundos entre ciclos de sync

    def to_dict(self) -> dict:
        from dataclasses import asdict as _asdict
        return _asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ClusterProfile":
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid})


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
    public_ip: str = ""          # IP/hostname público para conexão de outros jogadores
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

    # Seções INI personalizadas (não provenientes de nenhum mod)
    # {"gus": [{"section": str, "entries": [{"key": str, "value": str}]}],
    #  "game": [...]}
    custom_ini_sections: Dict[str, list] = field(default_factory=dict)

    # Biblioteca de broadcasts: mensagens salvas para envio rápido via RCON
    # [{"label": str, "message": str}]
    broadcasts: List[dict] = field(default_factory=list)

    # Opções de linha de comando adicionais
    extra_args: str = ""
    use_battleye: bool = False
    force_respawn_dinos: bool = False
    use_allcores: bool = False
    cpu_core_count: int = 0   # 0=padrão, -1=todos (flag), N>0=afinidade de N núcleos
    auto_save_period: float = 15.0
    active_event: str = ""

    # Rede / plataformas / jogadores
    crossplay: bool = False                # -crossplay (Epic + Steam no mesmo servidor)
    epic_only: bool = False                # -epiconly (somente Epic Game Store)
    use_vivox: bool = False                # -UseVivox (chat de voz no Steam)
    use_item_dupe_check: bool = False      # -UseItemDupeCheck (proteção anti-dupe)
    prevent_spawn_animations: bool = False # ?PreventSpawnAnimations=True (sem animação de spawn)
    show_floating_damage_text: bool = False # ?ShowFloatingDamageText=True (dano flutuante RPG)

    # Mensagem do Dia (MOTD)
    motd: str = ""
    motd_duration: int = 60

    # Configurações do jogo
    game_settings: ServerGameSettings = field(default_factory=ServerGameSettings)
    advanced_settings: ServerAdvancedSettings = field(default_factory=ServerAdvancedSettings)
    cluster: ClusterConfig = field(default_factory=ClusterConfig)
    # ID do perfil de cluster global (ClusterProfile); "" = usar config manual (cluster acima)
    cluster_profile_id: str = ""
    # Nome único da pasta de saves deste servidor (evita conflito ao rodar múltiplos servidores na mesma máquina)
    # Corresponde a ?AltSaveDirectoryName=<valor> na linha de comando
    alt_save_directory_name: str = ""

    # Config Dinâmica (DynamicConfigURL)
    dynamic_config_enabled: bool = False  # Serve config via HTTP local p/ aplicar mudanças sem reiniciar

    # Controle interno
    auto_restart_on_crash: bool = False
    auto_update_on_start: bool = False

    # Backup automático
    backup_enabled: bool = False
    backup_interval_hours: int = 6
    backup_keep_count: int = 10
    backup_include_saves: bool = True
    backup_include_config: bool = True
    backup_dir: str = ""  # "" = padrão (%APPDATA%/ARKLAND-ServerManager/backups/servers/{id})

    # Steam IDs com permissão de admin (gravados em AllowedCheaterSteamIDs.txt)
    admin_ids: List[str] = field(default_factory=list)
    # Cache de nomes Steam resolvidos: {steam_id: display_name}
    admin_names: Dict[str, str] = field(default_factory=dict)

    # Agendamentos automáticos
    scheduled_tasks: List[dict] = field(default_factory=list)
    # Cada item: {"enabled": bool, "time": "HH:MM", "days": [0..6], "action": str, "warn_minutes": int}
    # action: "restart" | "stop" | "update_restart"

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

    def build_launch_args(
        self,
        cluster_profile: Optional["ClusterProfile"] = None,
        dynamic_config_url: str = "",
    ) -> str:
        """Monta a linha de comando completa para iniciar o servidor.

        Args:
            cluster_profile: Perfil de cluster global a usar; sobrepõe a config
                             manual (self.cluster) quando fornecido.
            dynamic_config_url: URL para o parâmetro -DynamicConfigURL. Quando
                                fornecida, injeta o flag no startup do ARK.
        """
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

        # Cluster — perfil global tem prioridade sobre configuração manual por servidor
        _cl_id  = ""
        _cl_dir = ""
        _cl_no_transfer = False
        if cluster_profile and cluster_profile.cluster_id:
            _cl_id  = cluster_profile.cluster_id
            _cl_dir = cluster_profile.cluster_dir
            _cl_no_transfer = cluster_profile.no_transfer_from_filtering
        elif self.cluster.enabled and self.cluster.cluster_id:
            _cl_id  = self.cluster.cluster_id
            _cl_dir = self.cluster.cluster_dir_override
            _cl_no_transfer = self.cluster.no_transfer_from_filtering

        if _cl_id:
            params.append(f"?ClusterID={_cl_id}")
            if self.alt_save_directory_name:
                params.append(f"?AltSaveDirectoryName={self.alt_save_directory_name}")

        if self.prevent_spawn_animations:
            params.append("?PreventSpawnAnimations=True")
        if self.show_floating_damage_text:
            params.append("?ShowFloatingDamageText=True")

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
        if self.use_allcores or self.cpu_core_count == -1:
            flags.append("-useallavailablecores")
        if self.force_respawn_dinos:
            flags.append("-ForceRespawnDinos")
        if self.crossplay:
            flags.append("-crossplay")
        if self.epic_only:
            flags.append("-epiconly")
        if self.use_vivox:
            flags.append("-UseVivox")
        if self.use_item_dupe_check:
            flags.append("-UseItemDupeCheck")

        if _cl_id:
            if _cl_no_transfer:
                flags.append("-NoTransferFromFiltering")
            if _cl_dir:
                flags.append(f'-ClusterDirOverride="{_cl_dir}"')

        if dynamic_config_url:
            # ?customdynamicconfigurl= é query param; -UseDynamicConfig é a flag habilitadora (patch 307.2)
            params.append(f'?customdynamicconfigurl="{dynamic_config_url}"')
            flags.append("-UseDynamicConfig")

        if self.extra_args:
            flags.append(self.extra_args)

        args_str = "".join(params)
        flags_str = " ".join(flags)
        return f'"{exe_path}" {map_arg}{args_str} {flags_str}'
