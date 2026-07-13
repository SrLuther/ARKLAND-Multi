"""
Catálogo PT + EN + hints para campos de AsmServerConfig.
Fontes: asm_ini_manager.INI_MAP, asm_server_panel.py, ASM ServerProfile.cs.
"""
from __future__ import annotations

import re
from dataclasses import MISSING, dataclass, fields as dc_fields
from typing import Literal, Optional

from ..asm_engine.asm_server_config import AsmServerConfig
from ..asm_engine.asm_ini_manager import INI_MAP

try:
    from .legacy_pt_labels import LEGACY_PT_LABELS
except ImportError:
    LEGACY_PT_LABELS: dict[str, str] = {}

from .tek_section_fields import SECTION_FIELDS as _SECTION_FIELDS

FieldType = Literal["str", "int", "float", "bool", "list", "raw"]


@dataclass(frozen=True)
class FieldMeta:
    key: str
    pt: str
    en: str
    hint: str = ""
    field_type: FieldType = "str"
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    section: str = ""
    ini_key: str = ""
    search_text: str = ""


# ── Traduções PT manuais (prioridade sobre humanização) ───────────────────────
_PT_OVERRIDES: dict[str, str] = {
    # Administração
    "name": "Nome no gerenciador",
    "install_dir": "Pasta de instalação",
    "user_config_folder": "Pasta custom de INI (ASE)",
    "enable_cryo_sickness_pvp": "Cryo Sickness em PvP",
    "server_exe": "Executável do servidor",
    "session_name": "Nome da sessão (browser)",
    "server_password": "Senha do servidor",
    "admin_password": "Senha de admin",
    "spectator_password": "Senha de espectador",
    "server_ip": "IP (MultiHome)",
    "server_port": "Porta do servidor",
    "query_port": "Porta de consulta",
    "rcon_enabled": "RCON ativo",
    "rcon_port": "Porta RCON",
    "rcon_log_buffer": "Buffer de log RCON",
    "admin_logging": "Log de admin",
    "max_players": "Máximo de jogadores",
    "active_mods": "Mods ativos",
    "server_map": "Mapa",
    "auto_save_period": "Intervalo de autosave (min)",
    "additional_args": "Args CLI adicionais",
    # CLI / linha de comando
    "use_battleye": "BattlEye ativo",
    "force_respawn_dinos": "Forçar respawn de dinos (-ForceRespawnDinos)",
    "use_allcores": "Usar todos os núcleos CPU",
    "active_event": "Evento sazonal ARK (Páscoa, Halloween…)",
    "crossplay": "Crossplay Epic + Steam",
    "epic_only": "Somente Epic Game Store",
    "use_vivox": "Vivox (chat de voz Steam)",
    "use_item_dupe_check": "Proteção anti-dupe de itens",
    "use_raw_sockets": "Sockets UDP raw (bRawSockets)",
    "no_net_threading": "Sem net threading (-nonetthreading)",
    "force_net_threading": "Forçar net threading (-forcenetthreading)",
    "public_ip_for_epic": "IP público para Epic (NAT/VPS)",
    "no_transfer_from_filtering": "Bloquear transferência por filtro (cluster)",
    "disable_vac": "Desativar VAC (-insecure)",
    "disable_anti_speed_hack": "Desativar anti-speedhack",
    "speed_hack_bias": "Bias do speedhack",
    "disable_player_move_physics_opt": "Desativar otimização de física do jogador",
    "use_cache": "Usar cache de assets (-usecache)",
    "use_old_save_format": "Formato de save antigo",
    "use_no_memory_bias": "Sem bias de memória (-nomemorybias)",
    "stasis_keep_controllers": "Manter controllers em stasis",
    "use_no_hang_detection": "Sem detecção de hang",
    "server_allow_ansel": "Permitir NVIDIA Ansel",
    "no_dinos": "Sem dinos selvagens (-NoDinos)",
    "force_dx10": "Forçar DirectX 10 (-d3d10)",
    "force_shader_model4": "Forçar Shader Model 4 (-sm4)",
    "force_low_memory": "Modo baixa memória (-lowmemory)",
    "enable_auto_destroy_structures": "Auto-destruir estruturas (-AutoDestroyStructures)",
    "enable_no_fish_loot": "Sem loot de peixe (-nofishloot)",
    "enable_web_alarm": "Web alarm ativo (-webalarm)",
    "web_alarm_key": "Chave do web alarm",
    "web_alarm_url": "URL do web alarm",
    "enable_server_admin_logs": "Log de admin no console (-servergamelog)",
    "server_admin_logs_include_tribe_logs": "Incluir logs de tribo no log admin",
    "server_rcon_output_tribe_logs": "Logs de tribo via RCON",
    "notify_admin_commands_in_chat": "Notificar comandos admin no chat",
    # Extensões SM (Fase 5)
    "item_stack_size_multiplier": "Multiplicador global de pilhas",
    "spoiling_time_multiplier": "Multiplicador de spoil (legado GUS)",
    "item_decomposition_time_multiplier": "Decomposição de itens no chão (GUS)",
    "platform_saddle_build_area_bounds_multiplier": "Área de construção na platform saddle",
    "max_tribute_dinos": "Máx. dinos no terminal",
    "max_tribute_items": "Máx. itens no terminal",
    "baby_imprint_amount_multiplier": "Multiplicador de % por imprint",
    "enable_creative_mode": "Modo criativo (ESC)",
    "motd": "Mensagem do dia",
    "motd_duration": "Duração da MOTD (s)",
    # Jogador
    "xp_multiplier": "Multiplicador de XP",
    "player_damage_multiplier": "Dano do jogador",
    "player_resistance_multiplier": "Resistência do jogador",
    "player_water_drain_multiplier": "Consumo de água",
    "player_food_drain_multiplier": "Consumo de comida",
    "player_stamina_drain_multiplier": "Consumo de stamina",
    "player_health_recovery_multiplier": "Recuperação de vida",
    "player_harvesting_damage_multiplier": "Dano de coleta",
    "crafting_skill_bonus_multiplier": "Bônus de skill de crafting",
    "enable_flyer_carry": "Permitir carregar com voador (PvE)",
    "override_max_xp_player": "XP máximo do jogador (Game.ini; 0=padrão)",
    "player_engram_points_multiplier": "Multiplicador de pontos de engrama/nível",
    "craft_xp_multiplier": "XP de crafting",
    "generic_xp_multiplier": "XP genérico",
    "harvest_xp_multiplier": "XP de coleta",
    "kill_xp_multiplier": "XP de abate",
    "special_xp_multiplier": "XP especial",
    # Dino
    "dino_damage_multiplier": "Dano dos dinos",
    "tamed_dino_damage_multiplier": "Dano dos dinos domesticados",
    "dino_resistance_multiplier": "Resistência dos dinos",
    "tamed_dino_resistance_multiplier": "Resistência dos dinos domesticados",
    "dino_turret_damage_multiplier": "Dano de torreta em dino",
    "dino_harvesting_damage_multiplier": "Dano de coleta (dino)",
    "dino_char_food_drain_multiplier": "Consumo de comida (dino)",
    "dino_char_stamina_drain_multiplier": "Consumo de stamina (dino)",
    "dino_char_health_recovery_multiplier": "Recuperação de vida (dino)",
    "wild_dino_char_food_drain_multiplier": "Comida — dino selvagem",
    "tamed_dino_char_food_drain_multiplier": "Comida — dino domesticado",
    "wild_dino_torpor_drain_multiplier": "Torpor — dino selvagem",
    "tamed_dino_torpor_drain_multiplier": "Torpor — dino domesticado",
    "max_tamed_dinos": "Máximo de dinos domesticados",
    "dino_count_multiplier": "Multiplicador de contagem de dinos",
    "taming_speed_multiplier": "Velocidade de domesticação",
    "passive_tame_interval_multiplier": "Intervalo de tame passivo",
    "max_personal_tamed_dinos": "Máx. dinos pessoais",
    "personal_tamed_dinos_saddle_structure_cost": "Custo de estrutura de sela pessoal",
    "override_max_xp_dino": "XP máximo do dino (0=padrão)",
    "pve_dino_decay_period_multiplier": "Período de decay PvE",
    "raid_dino_food_drain_multiplier": "Consumo de comida (raid dino)",
    "allow_raid_dino_feeding": "Permitir alimentar dino de raid",
    "allow_flying_stamina_recovery": "Recuperação de stamina em voo",
    "allow_flyer_speed_leveling": "Upar velocidade em voadores",
    "prevent_mate_boost": "Impedir mate boost",
    "disable_dino_decay_pve": "Desativar decay de dino PvE",
    "pvp_dino_decay": "Decay de dino PvP",
    "auto_destroy_decayed_dinos": "Destruir dinos decayed automaticamente",
    "allow_multiple_attached_c4": "Permitir múltiplos C4",
    "disable_dino_riding": "Desativar montaria em dinos",
    "disable_dino_taming": "Desativar domesticação",
    "use_tame_limit_for_structures_only": "Limite de tame só para estruturas",
    "disable_imprint_buff": "Desativar buff de imprint",
    "allow_anyone_baby_imprint": "Qualquer um pode imprintar filhote",
    # Reprodução
    "mating_interval_multiplier": "Intervalo de acasalamento",
    "egg_hatch_speed_multiplier": "Velocidade de eclosão",
    "baby_mature_speed_multiplier": "Velocidade de maturação",
    "baby_food_consumption_multiplier": "Consumo de comida (filhote)",
    "baby_cuddle_interval_multiplier": "Intervalo de carinho",
    "baby_cuddle_grace_period_multiplier": "Período de graça do carinho",
    "baby_cuddle_lose_imprint_quality_speed_multiplier": "Perda de qualidade de imprint",
    "baby_imprinting_stat_scale": "Escala de stats de imprint",
    # ── Gameplay — campos adicionais ────────────────────────────────────────
    "allow_cave_flyers": "Permitir voadores em cavernas (PvE)",
    "disable_loot_crates_extra": "Desativar loot crates extras (PvE)",
    "extinction_event_utc": "Hora do evento de extinção (UTC)",
    # ── Administração / servidor ────────────────────────────────────────────
    "cpu_affinity_cores": "Afinidade de CPU (núcleos separados por vírgula)",
    "process_priority": "Prioridade do processo do servidor",
    "customshop_config_path": "Caminho do config.json da loja",
    "shop_server_id": "ID do servidor na loja CustomShop",
    "cross_chat_label": "Nome exibido no chat cluster (ServerId)",
    "tags": "Tags do servidor",
    "notes": "Notas e observações internas",
    "exclusive_join_ids": "SteamIDs com acesso exclusivo (whitelist)",
    "whitelist_ids": "Whitelist de SteamIDs",
    # ── Campos internos ─────────────────────────────────────────────────────
    "id": "ID interno do servidor",
    "folder": "Pasta de perfil do servidor",
    "admin_ids": "SteamIDs de administradores",
    "custom_ini_sections": "Seções INI customizadas (mapa de seção→conteúdo)",
    "pgm_terrain_string": "String de terreno ARK Procedural (PGM)",
    # ── Editores raw (nomes descritivos para busca) ─────────────────────────
    "crafting_overrides_raw": "Substituições de Crafting (Game.ini bruto)",
    "stack_size_overrides_raw": "Substituições de Stack/Pilha (Game.ini bruto)",
    "npc_spawn_overrides_raw": "Substituições de Spawn NPC (Game.ini bruto)",
    "supply_crate_overrides_raw": "Substituições de Supply Crate (Game.ini bruto)",
    "prevent_transfer_raw": "Impedir Transferências por classe (Game.ini bruto)",
    "engram_entries_raw": "Entradas de Engrama (Game.ini bruto)",
    "player_level_stats_raw": "Stats por nível — Jogador (Game.ini bruto)",
    "dino_level_stats_raw": "Stats por nível — Dinos (Game.ini bruto)",
    "custom_gus_ini_raw": "Conteúdo extra — GameUserSettings.ini",
    "custom_game_ini_raw": "Conteúdo extra — Game.ini",
    "custom_engine_ini_raw": "Conteúdo extra — Engine.ini",
    # ── Editores agregados (nomes descritivos) ──────────────────────────────
    "harvest_resource_multipliers": "Multiplicadores de coleta por recurso",
    "dino_class_damage_multipliers": "Multiplicadores de dano por classe de dino",
    "dino_class_resistance_multipliers": "Multiplicadores de resistência por classe de dino",
    "tamed_dino_class_damage_multipliers": "Multiplicadores de dano (dinos domados) por classe",
    "tamed_dino_class_resistance_multipliers": "Multiplicadores de resistência (dinos domados) por classe",
    "dino_spawn_weight_multipliers": "Pesos de spawn por espécie",
    "prevent_dino_tame_class_names": "Classes de dinos impedidas de domesticar",
    # ── Campos per-level ────────────────────────────────────────────────────
    "per_level_player": "Stats por nível — Jogador",
    "per_level_dino_wild": "Stats por nível — Dino selvagem",
    "per_level_dino_tamed": "Stats por nível — Dino domado",
    "per_level_dino_tamed_add": "Stats por nível — Dino domado (pontos extras)",
    "per_level_dino_tamed_affinity": "Stats por nível — Dino (bônus de domesticação)",
}

from .field_i18n_extra import EXTRA_HINTS, EXTRA_PT_OVERRIDES, EXTRA_SEARCH_KEYWORDS

_PT_OVERRIDES.update(EXTRA_PT_OVERRIDES)

# ── Hints (tooltips) ──────────────────────────────────────────────────────────
_HINTS: dict[str, str] = {
    "xp_multiplier": "Multiplicador geral de XP. Outros tipos de XP são aplicados adicionalmente.",
    "player_damage_multiplier": "Valores acima de 1.0 aumentam o atributo; abaixo diminuem.",
    "override_max_xp_player": "Cap de XP em Game.ini (OverrideMaxExperiencePointsPlayer). Com progressões ON e base >105 precisa da rampa no mesmo arquivo.",
    "player_engram_points_multiplier": "Multiplica os 8 pontos vanilla por nível (5.0 = 40 pts — permite aprender todos os engramas).",
    "enable_flyer_carry": "Permite que pterodatos e outros voadores carreguem outros dinos em PvE.",
    "dino_damage_multiplier": "Afeta todos os dinos (selvagens e domesticados). 1.5 = 50% mais dano.",
    "max_tamed_dinos": "Limite global de dinos domesticados. Recomendado: 300–500 para evitar lag.",
    "taming_speed_multiplier": ">1.0 = domesticação mais rápida; <1.0 = mais lenta.",
    "disable_imprint_buff": "Multiplica o bônus de imprinting. Apenas 100% de imprint tem efeito máximo.",
    "mating_interval_multiplier": "Menor valor = acasalamento mais frequente.",
    "egg_hatch_speed_multiplier": "Maior valor = ovos eclodem mais rápido.",
    "baby_mature_speed_multiplier": "Maior valor = filhotes amadurecem mais rápido.",
    "baby_cuddle_interval_multiplier": "Menor valor = carinhos mais frequentes (imprint mais fácil).",
    # CLI
    "use_battleye": "Desmarcado adiciona -NoBattlEye na linha de comando.",
    "force_respawn_dinos": "Força respawn imediato de todos os dinos ao iniciar.",
    "use_allcores": "Adiciona -useallavailablecores para usar todos os núcleos da CPU.",
    "crossplay": "Permite jogadores Epic e Steam no mesmo servidor (-crossplay).",
    "use_raw_sockets": "Ativa ?bRawSockets; combine com flags de net threading se necessário.",
    "disable_vac": "Desativa VAC da Steam. Use apenas para testes ou mods incompatíveis.",
    "speed_hack_bias": "Fator de tolerância anti-speedhack. Padrão: 1.0.",
    "enable_web_alarm": "Notificação de morte via webhook (-webalarm).",
    "additional_args": "Flags extras em texto livre; evite duplicar opções já configuradas acima.",
    "item_stack_size_multiplier": "Multiplica todas as pilhas padrão. 2.0 = dobro de stack.",
    "baby_imprint_amount_multiplier": "Afeta o % de imprint por carinho em todas as espécies.",
    "max_tribute_dinos": "Padrão ARK: 20. Valores muito altos podem corromper o cluster.",
    "enable_creative_mode": "Equivalente a bShowCreativeMode no Game.ini.",
}

_HINTS.update(EXTRA_HINTS)

# Termos de jogo/tecnologia aceitos em rótulos PT (não marcar como "fraco")
_PT_TERM_WHITELIST = frozenset({
    "ark", "battleye", "cli", "cryo", "epic", "hud", "ini", "mods", "pvp", "pve",
    "rcon", "sickness", "steam", "steamcmd", "vac", "vivox", "xp",
})

_EN_LABEL_RE = re.compile(
    r"\b(?:Enable|Disable|Allow|Prevent|Override|Multiplier|Interval|Structure|"
    r"Harvest|Decay|Fast|Hard|Auto|Destroy|Clamp|Crop|Day|Night|Flyer|Platform|"
    r"Saddle|Supply|Crate|Turret|Water|Pipe|Exclusive|Difficulty|Effectiveness|"
    r"Skill|Fishing|Loot|Quality|Temperature|Weather|Fog|Spoiling|Decomposition|"
    r"Additional|Args|Branch|Password|Cluster|Directory|Save|Logging|Tribe|Logs|"
    r"Marker|Crosshair|Respec|Hardcore|Download|Upload|Tribute|Gamma)\b",
    re.IGNORECASE,
)

_PT_LABEL_PREFIX = re.compile(
    r"^(?:Ativar|Desativar|Permitir|Bloquear|Usar|Forçar|Sem |Modo |Máx\.?|Máximo|"
    r"Intervalo|Velocidade|Qualidade|Multiplicador|Bônus|Ocultar|Auto-|Pasta |"
    r"Senha |Nome |Porta |Log |Tempo |Duração |Quantidade |Raio |Teto )",
    re.IGNORECASE,
)

# ── Seção TEK por campo (para busca na nav) ─────────────────────────────────
_SECTION_BY_FIELD: dict[str, str] = {
    # Jogador
    "xp_multiplier": "Configurações do Jogador",
    "player_damage_multiplier": "Configurações do Jogador",
    "player_resistance_multiplier": "Configurações do Jogador",
    "player_water_drain_multiplier": "Configurações do Jogador",
    "player_food_drain_multiplier": "Configurações do Jogador",
    "player_stamina_drain_multiplier": "Configurações do Jogador",
    "player_health_recovery_multiplier": "Configurações do Jogador",
    "player_harvesting_damage_multiplier": "Configurações do Jogador",
    "crafting_skill_bonus_multiplier": "Configurações do Jogador",
    "enable_flyer_carry": "Configurações do Jogador",
    "override_max_xp_player": "Configurações do Jogador",
    "player_engram_points_multiplier": "Configurações do Jogador",
    "craft_xp_multiplier": "Configurações do Jogador",
    "generic_xp_multiplier": "Configurações do Jogador",
    "harvest_xp_multiplier": "Configurações do Jogador",
    "kill_xp_multiplier": "Configurações do Jogador",
    "special_xp_multiplier": "Configurações do Jogador",
    "per_level_player": "Configurações do Jogador",
    # Dino
    "dino_damage_multiplier": "Configurações do Dino",
    "tamed_dino_damage_multiplier": "Configurações do Dino",
    "dino_resistance_multiplier": "Configurações do Dino",
    "tamed_dino_resistance_multiplier": "Configurações do Dino",
    "dino_turret_damage_multiplier": "Configurações do Dino",
    "dino_harvesting_damage_multiplier": "Configurações do Dino",
    "dino_char_food_drain_multiplier": "Configurações do Dino",
    "dino_char_stamina_drain_multiplier": "Configurações do Dino",
    "dino_char_health_recovery_multiplier": "Configurações do Dino",
    "wild_dino_char_food_drain_multiplier": "Configurações do Dino",
    "tamed_dino_char_food_drain_multiplier": "Configurações do Dino",
    "wild_dino_torpor_drain_multiplier": "Configurações do Dino",
    "tamed_dino_torpor_drain_multiplier": "Configurações do Dino",
    "max_tamed_dinos": "Configurações do Dino",
    "dino_count_multiplier": "Configurações do Dino",
    "taming_speed_multiplier": "Configurações do Dino",
    "passive_tame_interval_multiplier": "Configurações do Dino",
    "max_personal_tamed_dinos": "Configurações do Dino",
    "personal_tamed_dinos_saddle_structure_cost": "Configurações do Dino",
    "override_max_xp_dino": "Configurações do Dino",
    "pve_dino_decay_period_multiplier": "Configurações do Dino",
    "raid_dino_food_drain_multiplier": "Configurações do Dino",
    "allow_raid_dino_feeding": "Configurações do Dino",
    "allow_flying_stamina_recovery": "Configurações do Dino",
    "allow_flyer_speed_leveling": "Configurações do Dino",
    "prevent_mate_boost": "Configurações do Dino",
    "disable_dino_decay_pve": "Configurações do Dino",
    "pvp_dino_decay": "Configurações do Dino",
    "auto_destroy_decayed_dinos": "Configurações do Dino",
    "allow_multiple_attached_c4": "Configurações do Dino",
    "disable_dino_riding": "Configurações do Dino",
    "disable_dino_taming": "Configurações do Dino",
    "use_tame_limit_for_structures_only": "Configurações do Dino",
    "disable_imprint_buff": "Configurações do Dino",
    "allow_anyone_baby_imprint": "Configurações do Dino",
    "per_level_dino_wild": "Configurações do Dino",
    "per_level_dino_tamed": "Configurações do Dino",
    "per_level_dino_tamed_add": "Configurações do Dino",
    "per_level_dino_tamed_affinity": "Configurações do Dino",
    # Reprodução
    "mating_interval_multiplier": "Reprodução",
    "egg_hatch_speed_multiplier": "Reprodução",
    "baby_mature_speed_multiplier": "Reprodução",
    "baby_food_consumption_multiplier": "Reprodução",
    "baby_cuddle_interval_multiplier": "Reprodução",
    "baby_cuddle_grace_period_multiplier": "Reprodução",
    "baby_cuddle_lose_imprint_quality_speed_multiplier": "Reprodução",
    "baby_imprinting_stat_scale": "Reprodução",
}

# Limites sugeridos para sliders numéricos
_SLIDER_RANGES: dict[str, tuple[float, float]] = {
    "xp_multiplier": (0.0, 10.0),
    "player_damage_multiplier": (0.0, 10.0),
    "player_resistance_multiplier": (0.0, 10.0),
    "dino_damage_multiplier": (0.0, 10.0),
    "taming_speed_multiplier": (0.1, 50.0),
    "mating_interval_multiplier": (0.01, 10.0),
    "egg_hatch_speed_multiplier": (0.1, 100.0),
    "baby_mature_speed_multiplier": (0.1, 100.0),
}


def _humanize_en(key: str) -> str:
    """Converte snake_case em rótulo legível (inglês)."""
    if key in INI_MAP:
        ini_key = INI_MAP[key][2]
        if ini_key.startswith("b") and len(ini_key) > 1 and ini_key[1].isupper():
            ini_key = ini_key[1:]
        return re.sub(r"([a-z])([A-Z])", r"\1 \2", ini_key)
    return key.replace("_", " ").title()


def _humanize_pt(key: str) -> str:
    if key in _PT_OVERRIDES:
        return _PT_OVERRIDES[key]
    if key in LEGACY_PT_LABELS:
        return LEGACY_PT_LABELS[key]
    return _humanize_en(key)


def _infer_type(name: str, default) -> FieldType:
    if name.endswith("_raw") or name in (
        "crafting_overrides_raw", "stack_size_overrides_raw",
        "npc_spawn_overrides_raw", "supply_crate_overrides_raw",
        "prevent_transfer_raw", "custom_gus_ini_raw", "custom_game_ini_raw",
        "custom_engine_ini_raw", "engram_entries_raw",
        "player_level_stats_raw", "dino_level_stats_raw",
    ):
        return "raw"
    if isinstance(default, bool):
        return "bool"
    if isinstance(default, int) and not isinstance(default, bool):
        return "int"
    if isinstance(default, float):
        return "float"
    if isinstance(default, list):
        return "list"
    return "str"


def _all_section_by_field() -> dict[str, str]:
    merged = dict(_SECTION_BY_FIELD)
    for section, fields in _SECTION_FIELDS.items():
        for key in fields:
            merged[key] = section
    return merged


def _build_default_hint(key: str, pt: str, ftype: FieldType, section: str) -> str:
    """Tooltip PT gerado quando não há hint manual no catálogo."""
    if key.endswith("_raw") or ftype == "raw":
        return f"Editor de texto com entradas de {pt.lower()} no formato INI do ARK."
    if ftype == "bool":
        low = pt[0].lower() + pt[1:] if pt else pt
        if key.startswith(("enable_", "allow_")):
            return f"Ativo: {low}. Desativado: comportamento padrão do jogo."
        if key.startswith(("disable_", "prevent_")):
            return f"Ativo: {low}."
        return f"Opção sim/não — {low}."
    if ftype in ("int", "float"):
        if "multiplier" in key or "scale" in key:
            return f"{pt}. 1,0 = padrão vanilla; valores maiores intensificam o efeito."
        if "interval" in key or "period" in key or key.endswith("_seconds"):
            return f"{pt}. Valor em segundos."
        if "minutes" in key or key.endswith("_minutes"):
            return f"{pt}. Valor em minutos."
        if "port" in key:
            return f"{pt}. Libere a porta no firewall do servidor."
        if "password" in key:
            return f"{pt}. Deixe vazio para não exigir senha."
        if "time" in key and ftype == "int":
            return f"{pt}. Horário no formato HH:MM (24h) quando aplicável."
        return f"{pt}. Campo numérico — ajuste conforme a experiência desejada no servidor."
    if ftype == "list":
        return f"{pt}. Lista editável neste painel."
    if "url" in key or "webhook" in key:
        return f"{pt}. Informe a URL completa (https://...)."
    if any(x in key for x in ("path", "dir", "folder", "install")):
        return f"{pt}. Caminho no disco do servidor."
    if key in ("active_mods",):
        return "IDs numéricos dos mods da Steam Workshop, separados por vírgula."
    if key in ("admin_ids", "whitelist_ids", "exclusive_join_ids"):
        return "SteamIDs de 17 dígitos, um por linha ou separados por vírgula."
    if section:
        return f"{pt}. Configuração da seção «{section}»."
    return f"{pt}."


def _build_catalog() -> dict[str, FieldMeta]:
    section_map = _all_section_by_field()
    catalog: dict[str, FieldMeta] = {}
    for f in dc_fields(AsmServerConfig):
        key = f.name
        if f.default is not MISSING:
            default = f.default
        elif f.default_factory is not MISSING:
            default = f.default_factory()
        else:
            default = None
        ftype = _infer_type(key, default)
        ini_key = INI_MAP[key][2] if key in INI_MAP else ""
        en = _humanize_en(key)
        pt = _humanize_pt(key)
        hint = _HINTS.get(key) or _build_default_hint(key, pt, ftype, section_map.get(key, ""))
        section = section_map.get(key, "")
        mn, mx = _SLIDER_RANGES.get(key, (None, None))
        extra_kw = EXTRA_SEARCH_KEYWORDS.get(key, "")
        search = f"{key} {pt} {en} {ini_key} {hint} {extra_kw}".lower()
        catalog[key] = FieldMeta(
            key=key, pt=pt, en=en, hint=hint, field_type=ftype,
            min_val=mn, max_val=mx, section=section, ini_key=ini_key,
            search_text=search,
        )
    return catalog


FIELD_LABELS: dict[str, FieldMeta] = _build_catalog()


def get_field_meta(key: str) -> FieldMeta:
    if key in FIELD_LABELS:
        return FIELD_LABELS[key]
    return FieldMeta(key=key, pt=key, en=key)


def fields_for_section(section_name: str) -> list[str]:
    return [k for k, m in FIELD_LABELS.items() if m.section == section_name]


def section_search_index() -> dict[str, str]:
    """Texto agregado por seção TEK para filtro de busca (cache singleton)."""
    global _SECTION_SEARCH_INDEX_CACHE
    if _SECTION_SEARCH_INDEX_CACHE is not None:
        return _SECTION_SEARCH_INDEX_CACHE
    index: dict[str, str] = {}
    for key, meta in FIELD_LABELS.items():
        if not meta.section:
            continue
        index.setdefault(meta.section, "")
        index[meta.section] += " " + meta.search_text
    _SECTION_SEARCH_INDEX_CACHE = index
    return index


_SECTION_SEARCH_INDEX_CACHE: dict[str, str] | None = None
_FIELD_SEARCH_ENTRIES_CACHE: list[tuple[str, str, str, str]] | None = None


def invalidate_search_caches() -> None:
    """Limpa caches de busca (útil após alterar SECTION_FIELDS)."""
    global _SECTION_SEARCH_INDEX_CACHE, _FIELD_SEARCH_ENTRIES_CACHE
    _SECTION_SEARCH_INDEX_CACHE = None
    _FIELD_SEARCH_ENTRIES_CACHE = None


def field_search_entries() -> list[tuple[str, str, str, str]]:
    """(field_key, section, pt_label, search_blob) — busca global TEK."""
    global _FIELD_SEARCH_ENTRIES_CACHE
    if _FIELD_SEARCH_ENTRIES_CACHE is not None:
        return _FIELD_SEARCH_ENTRIES_CACHE
    entries: list[tuple[str, str, str, str]] = []
    for key, meta in FIELD_LABELS.items():
        if not meta.section:
            continue
        if key.startswith("_") or key in ("id", "cluster_profile_id", "custom_ini_sections"):
            continue
        entries.append((key, meta.section, meta.pt, meta.search_text))
    _FIELD_SEARCH_ENTRIES_CACHE = entries
    return entries


def _looks_english_pt(text: str) -> bool:
    """Heurística: rótulo ainda parece inglês de config ARK."""
    if not text or not text.strip():
        return False
    if _PT_LABEL_PREFIX.match(text.strip()):
        return False
    words = [w for w in re.split(r"[\s/()—–-]+", text) if w.isalpha()]
    pt_particles = {"de", "do", "da", "dos", "das", "em", "no", "na", "por", "para", "com", "sem", "ao", "aos", "ou"}
    if words:
        lower = {w.lower() for w in words}
        if lower & pt_particles:
            return False
    low = text.lower()
    if any(term in low for term in _PT_TERM_WHITELIST):
        # Ainda pode ser inglês puro — checa marcadores fortes
        if not _EN_LABEL_RE.search(text):
            return False
    if _EN_LABEL_RE.search(text):
        return True
    if len(words) < 2:
        return False
    lower = {w.lower() for w in words}
    if lower & pt_particles:
        return False
    titled = sum(1 for w in words if w[0].isupper())
    return titled >= len(words) * 0.6


def missing_pt_translations() -> list[str]:
    """Campos cujo PT é igual ao EN humanizado (sem override nem legado)."""
    missing = []
    for key, meta in FIELD_LABELS.items():
        if key in _PT_OVERRIDES or key in LEGACY_PT_LABELS:
            continue
        if meta.pt == meta.en:
            missing.append(key)
    return sorted(missing)


def weak_pt_labels() -> list[str]:
    """Campos com PT no catálogo mas rótulo ainda parecendo inglês."""
    weak = []
    for key, meta in FIELD_LABELS.items():
        if meta.pt == meta.en:
            weak.append(key)
            continue
        if _looks_english_pt(meta.pt):
            weak.append(key)
    return sorted(weak)


def missing_hints() -> list[str]:
    """Campos sem tooltip manual (os automáticos não entram nesta lista)."""
    return sorted(k for k in FIELD_LABELS if k not in _HINTS and k not in EXTRA_HINTS)
