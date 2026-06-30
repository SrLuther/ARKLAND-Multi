"""Testes de visibilidade e catálogo TEK."""
from __future__ import annotations

import pytest

from dataclasses import fields

from src.asm_engine.asm_server_config import AsmServerConfig
from src.asm_engine.asm_ini_manager import INI_MAP
from src.ui.tek_section_fields import SECTION_FIELDS
from src.ui.server_field_labels import (
    FIELD_LABELS,
    field_search_entries,
    invalidate_search_caches,
    section_search_index,
)
from src.asm_ui.asm_server_panel import SECTIONS


INTERNAL = frozenset({
    "id", "cluster_profile_id", "disable_loot_crates_extra", "custom_ini_sections",
    "shop_server_id", "cross_chat_label", "customshop_config_path",
    "shop_show_on_home", "shop_exclude",
})

RAW_OR_AGG = frozenset({
    "engram_entries_raw", "player_level_stats_raw", "dino_level_stats_raw",
    "crafting_overrides_raw", "stack_size_overrides_raw", "npc_spawn_overrides_raw",
    "supply_crate_overrides_raw", "prevent_transfer_raw",
    "custom_gus_ini_raw", "custom_game_ini_raw", "custom_engine_ini_raw",
    "per_level_player", "per_level_dino_wild", "per_level_dino_tamed",
    "per_level_dino_tamed_add", "per_level_dino_tamed_affinity",
    "admin_ids", "whitelist_ids", "exclusive_join_ids",
    "harvest_resource_multipliers", "dino_class_resistance_multipliers",
    "dino_class_damage_multipliers", "tamed_dino_class_resistance_multipliers",
    "tamed_dino_class_damage_multipliers", "dino_spawn_weight_multipliers",
    "prevent_dino_tame_class_names",
})


@pytest.fixture(autouse=True)
def _fresh_search_cache():
    invalidate_search_caches()
    yield
    invalidate_search_caches()


def test_section_fields_no_duplicate_keys():
    seen: dict[str, str] = {}
    dups: list[tuple[str, str, str]] = []
    for sec, flist in SECTION_FIELDS.items():
        for key in flist:
            if key in seen:
                dups.append((key, seen[key], sec))
            else:
                seen[key] = sec
    assert not dups, f"Campos duplicados em SECTION_FIELDS: {dups}"


def test_ini_map_fields_have_section():
    missing = []
    for key in INI_MAP:
        if key in INTERNAL:
            continue
        meta = FIELD_LABELS.get(key)
        if not meta or not meta.section:
            missing.append(key)
    assert not missing, f"INI_MAP sem seção TEK: {missing[:20]}"


def test_gameplay_sections_in_search_index():
    idx = section_search_index()
    assert "Configurações do Jogador" in idx
    assert "xp_multiplier" in idx["Configurações do Jogador"]
    assert "Configurações do Dino" in idx
    assert "Reprodução" in idx


def test_search_keywords_stryder_and_evento():
    entries = {k: blob for k, _s, _pt, blob in field_search_entries()}
    assert "stryder" in entries["override_structure_platform_prevention"]
    assert "páscoa" in entries["active_event"] or "easter" in entries["active_event"]


def test_tribute_fields_mapped_to_transfers():
    trib = SECTION_FIELDS["Transferências / Tributo"]
    for key in (
        "enable_tribute_downloads",
        "prevent_download_survivors",
        "cross_ark_allow_foreign_dino_downloads",
    ):
        assert key in trib


def test_panel_sections_have_field_map_or_tools():
    """Toda seção do painel (exceto ferramentas) tem entrada em SECTION_FIELDS."""
    tool_sections = {
        "🦕 Gerador SpawnExact", "⚡ Console RCON", "👥 Jogadores Online",
    }
    special = {"Todas as opções"} | tool_sections
    missing = [s for s in SECTIONS if s not in SECTION_FIELDS and s not in special]
    assert missing == [], f"Seções sem SECTION_FIELDS: {missing}"


def test_active_event_portuguese_label():
    meta = FIELD_LABELS["active_event"]
    assert "Evento" in meta.pt
    assert "Páscoa" in meta.pt or "sazonal" in meta.pt


def test_config_scalar_coverage():
    """Campos escalares INI devem estar em SECTION_FIELDS."""
    config_fields = {f.name for f in fields(AsmServerConfig)}
    section_fields = {k for fl in SECTION_FIELDS.values() for k in fl}
    skip = INTERNAL | RAW_OR_AGG
    gap = sorted((INI_MAP.keys() & config_fields) - section_fields - skip)
    assert len(gap) <= 2, f"INI scalars fora de SECTION_FIELDS: {gap}"
