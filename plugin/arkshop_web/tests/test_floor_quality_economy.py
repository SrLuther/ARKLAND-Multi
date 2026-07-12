"""Testes do modelo floor_quality e migração catálogo L1 por blueprint."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import market_economy

from market_economy import (
    SpeciesEconomy,
    apply_economy_meta,
    build_blueprint_economy_map,
    calculate_encomenda_value,
    calculate_quality_index,
    calculate_suggested_value,
    load_defaults_file,
    load_market_absolute_max,
    load_species_root_ladder,
    normalize_blueprint,
    resolve_species_by_blueprint,
)

ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"
MATRIX_PATH = ROOT / "tools" / "blueprint_catalog_matrix.csv"
LADDER_PATH = ROOT / "plugin" / "arkshop_web" / "data" / "species_root_ladder.json"

# Caminho canônico do defaults bundled no repo — garante que estes testes usem o
# arquivo atualizado pelo recalibrate, mesmo que app.py tenha inserido o root do
# projeto em sys.path e webstore_data_dir() retorne um caminho diferente.
_REPO_DEFAULTS = ROOT / "plugin" / "arkshop_web" / "data" / "market_species_defaults.json"


@pytest.fixture(autouse=True)
def _pin_market_defaults():
    """Fixa market_economy._DEFAULTS_FILE para o arquivo do repo durante estes testes."""
    original = market_economy._DEFAULTS_FILE
    market_economy._DEFAULTS_FILE = _REPO_DEFAULTS
    yield
    market_economy._DEFAULTS_FILE = original


def _all_stat_points(value: int) -> dict[str, int]:
    return {sk: value for sk in ("health", "melee", "weight", "stamina", "speed", "food")}


def test_ladder_file_exists():
    assert LADDER_PATH.is_file()
    ladder = load_species_root_ladder()
    assert ladder.get("market_absolute_max") == 150_000
    assert "blueprint_overrides" in ladder


def test_catalog_l1_and_optional_l200():
    """Catálogo: 189 L1 (piso) + pares opcionais *_l200 (Level 200) quando a fórmula cabe no teto.
    Contagem L1: 189 (98 originais + 91 vanilla/DLC Jul/2026).
    """
    if not CONFIG_PATH.is_file():
        pytest.skip("config.json ausente")
    catalog = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    items = catalog.get("Items") or {}
    l1 = []
    l200 = []
    for item_id, entry in items.items():
        if str(entry.get("Type") or "").lower() != "dino":
            continue
        level = int((entry.get("Dinos") or [{}])[0].get("Level") or 0)
        if level == 1:
            l1.append(item_id)
        elif level == 200:
            assert str(item_id).endswith("_l200"), f"L200 sem sufixo: {item_id}"
            l200.append(item_id)
        else:
            raise AssertionError(f"Nível inesperado {level} em {item_id}")
    assert len(l1) == 189, f"Esperado 189 dinos L1, encontrado {len(l1)}"
    for l200_id in l200:
        l1_id = l200_id[: -len("_l200")]
        assert l1_id in items, f"L200 órfão: {l200_id}"


def test_matrix_has_79_rows():
    if not MATRIX_PATH.is_file():
        pytest.skip("matrix csv ausente")
    lines = MATRIX_PATH.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 171  # header + 170 (79 originais + 91 vanilla/DLC Jul/2026)


def test_apex_hierarchy_r_values():
    data = load_defaults_file()
    by_key = {s["species_key"]: s for s in data.get("species", [])}
    arma = by_key.get("armaedron")
    indo = by_key.get("indominus")
    carcha = by_key.get("carcha")
    assert arma and indo and carcha
    assert int(arma["root_value"]) > int(indo["root_value"]) > int(carcha["root_value"])


def test_carcha_full_254_capped_at_150k():
    species = SpeciesEconomy(
        species_key="carcha",
        display_name="Carcha",
        root_value=25_000,
        premium_budget=125_000,
        dino_role="raid",
        pricing_mode="floor_quality",
    )
    apply_economy_meta(species)
    species.premium_budget = 125_000
    species.pricing_mode = "floor_quality"
    total, _ = calculate_suggested_value(species, _all_stat_points(254))
    assert total == load_market_absolute_max()


def test_market_at_zero_equals_root():
    species = SpeciesEconomy(
        species_key="rex",
        display_name="Rex",
        root_value=18_000,
        premium_budget=90_000,
        dino_role="ataque",
        pricing_mode="floor_quality",
    )
    total, breakdown = calculate_suggested_value(species, _all_stat_points(0))
    assert total == 18_000
    assert breakdown[0]["kind"] == "root"


def test_encomenda_greater_than_market():
    species = SpeciesEconomy(
        species_key="rex",
        display_name="Rex",
        root_value=18_000,
        premium_budget=90_000,
        dino_role="ataque",
        pricing_mode="floor_quality",
    )
    market, _ = calculate_suggested_value(species, _all_stat_points(100))
    encomenda = calculate_encomenda_value(species, market)
    assert encomenda > market


def test_tekstrider_in_defaults_as_catalog_or_market():
    """Tek Strider está no catálogo L1 — deve existir nos defaults (Dino Lab / sync)."""
    keys = {s["species_key"] for s in load_defaults_file().get("species", [])}
    assert "tekstrider" in keys
    entry = next(s for s in load_defaults_file()["species"] if s["species_key"] == "tekstrider")
    assert entry.get("catalog_item_id") == "tekstrider_femea"
    assert "TekStrider" in str(entry.get("blueprint_path") or "")


def test_resolve_species_by_blueprint_carcha():
    data = load_defaults_file()
    carcha = next(s for s in data["species"] if s["species_key"] == "carcha")
    bp = carcha["blueprint_path"]
    resolved = resolve_species_by_blueprint(bp)
    assert resolved is not None
    assert resolved["species_key"] == "carcha"


def test_build_blueprint_economy_map_unique():
    bmap = build_blueprint_economy_map()
    assert len(bmap) >= 78
    for nb, defn in bmap.items():
        assert normalize_blueprint(defn.get("blueprint_path")) == nb or nb


def test_quality_index_bounded():
    q, _ = calculate_quality_index(_all_stat_points(254), dino_role="raid")
    assert 0.99 <= q <= 1.0
    q0, _ = calculate_quality_index(_all_stat_points(0), dino_role="raid")
    assert q0 == 0.0


def test_catalog_price_matches_root_for_rex(tmp_path, monkeypatch):
    if not CONFIG_PATH.is_file():
        pytest.skip("config.json ausente")
    catalog = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    rex_item = (catalog.get("Items") or {}).get("rex")
    if not rex_item:
        pytest.skip("rex ausente no catálogo")
    data = load_defaults_file()
    rex_def = next(s for s in data["species"] if s["species_key"] == "rex")
    assert int(rex_item["Price"]) == int(rex_def["root_value"])
