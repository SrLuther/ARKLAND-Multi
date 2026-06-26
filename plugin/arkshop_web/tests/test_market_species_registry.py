"""Testes do registro de espécies e normalização de blueprint."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ark_species_registry import (
    extract_class_token,
    is_raw_blueprint_label,
    load_registry,
    lookup_species,
    normalize_blueprint_extended,
    registry_stats,
    resolve_species_image,
    tier_icon_url,
    _bundled_species_icon_urls,
    _indexes,
)


@pytest.fixture(autouse=True)
def _clear_registry_cache():
    load_registry.cache_clear()
    _indexes.cache_clear()
    _bundled_species_icon_urls.cache_clear()
    yield
    load_registry.cache_clear()
    _indexes.cache_clear()
    _bundled_species_icon_urls.cache_clear()


def test_extract_class_token_from_raw_name_map():
    assert extract_class_token("Ankylo_Character_BP_C_257") == "ankylo"
    assert extract_class_token("Ankylo_Character_BP_C_257 ♂") == "ankylo"


def test_extract_class_token_from_full_blueprint():
    bp = "/Game/PrimalEarth/Dinos/Ankylo/Ankylo_Character_BP.Ankylo_Character_BP"
    assert extract_class_token(bp) == "ankylo"
    assert "ankylo" in normalize_blueprint_extended(bp)


def test_is_raw_blueprint_label():
    assert is_raw_blueprint_label("Ankylo_Character_BP_C_257")
    assert not is_raw_blueprint_label("Meu Rex TOP")


def test_lookup_ankylo_by_blueprint():
    bp = "/Game/PrimalEarth/Dinos/Ankylo/Ankylo_Character_BP.Ankylo_Character_BP"
    hit = lookup_species(blueprint=bp)
    assert hit is not None
    assert hit["display_name"] == "Anquilossauro"
    assert hit["tier"] == "B"
    assert hit["confidence"] in ("high", "medium")


def test_lookup_ankylo_by_name_hint():
    hit = lookup_species(name_hint="Ankylo_Character_BP_C_257 ♂")
    assert hit is not None
    assert hit["species_key"] in ("ankylo", "ankylosaurus")


def test_lookup_rex_defaults():
    hit = lookup_species(species_key="rex")
    assert hit is not None
    assert hit["tier"] == "A"


def test_registry_stats_has_species():
    stats = registry_stats()
    assert stats["species_count"] >= 120


def test_lookup_abyss_rex_abyssal_by_blueprint():
    bp = "/Game/Abyss/Dinos/Rex/Rex_Character_BP_Abyssal.Rex_Character_BP_Abyssal"
    hit = lookup_species(blueprint=bp)
    assert hit is not None
    assert hit["species_key"] == "abyss_rex_abyssal"
    assert hit["display_name"] == "Rex Abissal"
    assert hit["tier"] == "S+"
    assert hit["root_value"] == 13000
    assert hit["confidence"] == "high"


def test_lookup_abyss_ankylo_abyssal_by_name_hint():
    hit = lookup_species(name_hint="Ankylo_Character_BP_Abyssal")
    assert hit is not None
    assert hit["species_key"] == "abyss_ankylo_abyssal"
    assert hit["tier"] == "B"
    assert hit["role"] == "farm"


def test_lookup_abyss_water_wyvern():
    hit = lookup_species(blueprint="Wyvern_Character_BP_Water")
    assert hit is not None
    assert hit["species_key"] == "abyss_water_wyvern"
    assert hit["tier"] == "S+"
    assert hit["root_value"] == 12000


def test_lookup_abyss_dakosaurus():
    bp = "/Game/Abyss/Dinos/Dakosaurus/Dakosaurus_Character_BP.Dakosaurus_Character_BP"
    hit = lookup_species(blueprint=bp)
    assert hit is not None
    assert hit["species_key"] == "abyss_dakosaurus"
    assert hit["tier"] == "S"
    assert hit["root_value"] == 9000


def test_lookup_abyss_resource_seaweed():
    bp = "/Game/Abyss/CoreBlueprints/Resources/PrimalItemResource_Seaweed.PrimalItemResource_Seaweed"
    hit = lookup_species(blueprint=bp)
    assert hit is not None
    assert hit["species_key"] == "abyss_seaweed"
    assert hit["tier"] == "C"
    assert hit["role"] == "resource"


def test_lookup_abyss_reaper_male_abyssal():
    hit = lookup_species(name_hint="Reaper_Character_BP_Male_Abyssal")
    assert hit is not None
    assert hit["species_key"] == "abyss_reaper_abyssal"
    assert hit["tier"] == "S+"


def test_tier_icon_url_fallback():
    assert tier_icon_url("S+").endswith("tier-s-plus.svg")
    assert tier_icon_url("A").endswith("tier-a.svg")
    assert tier_icon_url(None).endswith("tier-b.svg")


def test_resolve_species_image_custom_and_fallback():
    entry = {"species_key": "rex", "tier": "A", "icon_path": "rex.png"}
    assert resolve_species_image(entry) == "/species/rex.png"
    assert resolve_species_image({"image_url": "https://cdn.example/rex.webp"}) == "https://cdn.example/rex.webp"
    assert resolve_species_image(None, tier="C").endswith("tier-c.svg")


def test_lookup_includes_image_url():
    hit = lookup_species(species_key="ankylo")
    assert hit is not None
    assert hit["image_url"] == "/species/icons/ankylo.svg"


def test_lookup_shop_rex_uses_species_icon():
    bp = "/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP"
    hit = lookup_species(blueprint=bp, name_hint="Rex Fêmea")
    assert hit is not None
    assert hit["image_url"].endswith("/rex.svg")


def test_bundled_icons_from_meipass_layout(tmp_path, monkeypatch):
    """PyInstaller empacota static/ e data/ na raiz de _MEIPASS, não em plugin/arkshop_web/."""
    meipass = tmp_path / "mei"
    icons = meipass / "static" / "species" / "icons"
    icons.mkdir(parents=True)
    (icons / "rex.svg").write_text("<svg/>", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    _bundled_species_icon_urls.cache_clear()
    urls = _bundled_species_icon_urls()
    assert urls.get("rex") == "/species/icons/rex.svg"
