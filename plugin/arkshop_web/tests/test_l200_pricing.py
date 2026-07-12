"""Testes da fórmula de preço L200 (loja CustomShop)."""
from __future__ import annotations

import json
from pathlib import Path

import market_economy as me

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"


def test_l200_formula_example_markup():
    # P1=18000, M=40000 → round(clamp(25200, 18001, 30000)) = 25200
    assert me.compute_l200_price(18_000, 40_000) == 25_200


def test_l200_formula_hits_cap():
    # P1=20000, M=30000 → raw=28000, cap=22500 → 22500
    assert me.compute_l200_price(20_000, 30_000) == 22_500


def test_l200_formula_floor_p1_plus_one():
    # k baixo artificial: raw < P1+1 → sobe para P1+1
    assert me.compute_l200_price(10_000, 50_000, k=1.00001) == 10_001


def test_l200_formula_skip_when_cap_leq_p1():
    # P1 == M → 0.75M < P1 → skip
    assert me.compute_l200_price(18_000, 18_000) is None
    # P1 >= 0.75M
    assert me.compute_l200_price(23_000, 30_000) is None  # cap=22500


def test_l200_markup_k_constant():
    assert me.L200_MARKUP_K == 1.40
    assert me.L200_CAP_RATIO == 0.75
    assert me.L200_ID_SUFFIX == "_l200"
    assert me.l200_shop_id("rex_femea") == "rex_femea_l200"


def test_apply_l200_idempotent(tmp_path, monkeypatch):
    import sys

    tools = ROOT / "tools"
    sys.path.insert(0, str(tools))
    from apply_shop_l200_prices import apply_l200_to_catalog  # noqa: WPS433

    defaults = {
        "species": [
            {
                "species_key": "rex",
                "display_name": "Rex",
                "catalog_item_id": "rex_femea",
                "catalog_item_ids": ["rex_femea"],
                "root_value": 40_000,
                "blueprint_path": "/Game/Rex",
            },
            {
                "species_key": "tight",
                "display_name": "Tight",
                "catalog_item_id": "tight_femea",
                "catalog_item_ids": ["tight_femea"],
                "root_value": 10_000,
                "blueprint_path": "/Game/Tight",
            },
        ]
    }
    defaults_path = tmp_path / "market_species_defaults.json"
    defaults_path.write_text(json.dumps(defaults), encoding="utf-8")
    monkeypatch.setattr(me, "_DEFAULTS_FILE", defaults_path)

    catalog = {
        "Items": {
            "rex_femea": {
                "Type": "dino",
                "Price": 18_000,
                "Description": "Rex Fêmea Nível 1",
                "Dinos": [
                    {
                        "Blueprint": "/Game/Rex",
                        "ForceTame": True,
                        "Gender": "female",
                        "Level": 1,
                        "Neutered": False,
                    }
                ],
            },
            "tight_femea": {
                "Type": "dino",
                "Price": 9_000,
                "Description": "Tight Nível 1",
                "Dinos": [{"Blueprint": "/Game/Tight", "Level": 1, "ForceTame": True}],
            },
        }
    }

    s1 = apply_l200_to_catalog(catalog)
    assert s1["created_count"] == 1
    assert s1["skipped_count"] == 1
    assert "rex_femea_l200" in catalog["Items"]
    assert catalog["Items"]["rex_femea_l200"]["Price"] == 25_200
    assert catalog["Items"]["rex_femea_l200"]["Dinos"][0]["Level"] == 200
    assert "tight_femea_l200" not in catalog["Items"]

    s2 = apply_l200_to_catalog(catalog)
    assert s2["created_count"] == 0
    assert s2["updated_count"] == 1
    assert catalog["Items"]["rex_femea_l200"]["Price"] == 25_200


def test_repo_l200_entries_match_formula_when_present():
    if not CONFIG.is_file():
        return
    # Forçar defaults do repo (não o WEBSTORE Desktop antigo via webstore_data_dir).
    defaults = ROOT / "plugin" / "arkshop_web" / "data" / "market_species_defaults.json"
    me._DEFAULTS_FILE = defaults.resolve()
    for fn_name in ("load_defaults_file", "load_default_species_map", "build_catalog_economy_map"):
        fn = getattr(me, fn_name, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()  # type: ignore[attr-defined]

    catalog = json.loads(CONFIG.read_text(encoding="utf-8"))
    for item_id, entry in me.iter_catalog_dinos(catalog, level200_only=True):
        assert item_id.endswith(me.L200_ID_SUFFIX), item_id
        l1_id = item_id[: -len(me.L200_ID_SUFFIX)]
        l1 = (catalog.get("Items") or {}).get(l1_id)
        assert l1 is not None, f"L200 sem L1: {item_id}"
        p1 = int(l1.get("Price") or 0)
        m = me.resolve_species_root_value(l1_id, l1)
        assert m is not None
        expected = me.compute_l200_price(p1, m)
        assert expected is not None
        assert int(entry.get("Price") or 0) == expected
        assert me.catalog_dino_level(entry) == 200
