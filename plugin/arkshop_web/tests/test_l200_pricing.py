"""Testes da fórmula de preço L200 (loja CustomShop)."""
from __future__ import annotations

import json
from pathlib import Path

import market_economy as me

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"


def test_l200_indominus_formula():
    # R=28000, B=122000 → V254=150000 → P200=60000
    assert me.compute_v254(28_000, 122_000, 150_000) == 150_000
    assert me.compute_l200_price(28_000, 28_000, 122_000, market_absolute_max=150_000) == 60_000


def test_l200_formula_uncapped():
    # R=18000, B=50000 → V254=68000 → round(0.40×68000)=27200
    assert me.compute_l200_price(18_000, 18_000, 50_000, market_absolute_max=150_000) == 27_200


def test_l200_formula_hits_market_cap():
    # R+B acima do teto → V254=cap
    assert me.compute_v254(40_000, 200_000, 150_000) == 150_000
    assert me.compute_l200_price(40_000, 40_000, 200_000, market_absolute_max=150_000) == 60_000


def test_l200_formula_skip_when_p200_leq_p1():
    # V254=10000 → P200=4000 ≤ P1=10000 → skip
    assert me.compute_l200_price(10_000, 10_000, 0, market_absolute_max=150_000) is None


def test_l200_ratio_constant():
    assert me.L200_OF_V254_RATIO == 0.40
    assert me.L200_ID_SUFFIX == "_l200"
    assert me.l200_shop_id("rex_femea") == "rex_femea_l200"
    assert me.BREEDING_KIT_PAY_RATIO == 0.60


def test_apply_l200_idempotent(tmp_path, monkeypatch):
    import sys

    tools = ROOT / "tools"
    sys.path.insert(0, str(tools))
    from apply_shop_l200_prices import apply_l200_to_catalog  # noqa: WPS433

    defaults = {
        "_floor_quality": {"market_absolute_max": 150_000},
        "species": [
            {
                "species_key": "indominus",
                "display_name": "Indominus",
                "catalog_item_id": "indominus_femea",
                "catalog_item_ids": ["indominus_femea"],
                "root_value": 28_000,
                "premium_budget": 122_000,
                "blueprint_path": "/Game/Indominus",
            },
            {
                "species_key": "tight",
                "display_name": "Tight",
                "catalog_item_id": "tight_femea",
                "catalog_item_ids": ["tight_femea"],
                "root_value": 10_000,
                "premium_budget": 0,
                "blueprint_path": "/Game/Tight",
            },
        ]
    }
    defaults_path = tmp_path / "market_species_defaults.json"
    defaults_path.write_text(json.dumps(defaults), encoding="utf-8")
    monkeypatch.setattr(me, "_DEFAULTS_FILE", defaults_path)
    for fn_name in ("load_defaults_file", "load_default_species_map", "build_catalog_economy_map"):
        fn = getattr(me, fn_name, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()  # type: ignore[attr-defined]

    catalog = {
        "Items": {
            "indominus_femea": {
                "Type": "dino",
                "Price": 28_000,
                "Description": "Indominus Fêmea Nível 1",
                "Dinos": [
                    {
                        "Blueprint": "/Game/Indominus",
                        "ForceTame": True,
                        "Gender": "female",
                        "Level": 1,
                        "Neutered": False,
                    }
                ],
            },
            "tight_femea": {
                "Type": "dino",
                "Price": 10_000,
                "Description": "Tight Nível 1",
                "Dinos": [{"Blueprint": "/Game/Tight", "Level": 1, "ForceTame": True}],
            },
        }
    }

    s1 = apply_l200_to_catalog(catalog)
    assert s1["created_count"] == 1
    assert s1["skipped_count"] == 1
    assert "indominus_femea_l200" in catalog["Items"]
    assert catalog["Items"]["indominus_femea_l200"]["Price"] == 60_000
    assert catalog["Items"]["indominus_femea_l200"]["Dinos"][0]["Level"] == 200
    assert "Gender" not in catalog["Items"]["indominus_femea_l200"]["Dinos"][0]
    assert "Fêmea" not in catalog["Items"]["indominus_femea_l200"].get("Description", "")
    assert "tight_femea_l200" not in catalog["Items"]

    s2 = apply_l200_to_catalog(catalog)
    assert s2["created_count"] == 0
    assert s2["updated_count"] == 1
    assert catalog["Items"]["indominus_femea_l200"]["Price"] == 60_000
    assert "Gender" not in catalog["Items"]["indominus_femea_l200"]["Dinos"][0]


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
    market_cap = me.load_market_absolute_max()
    for item_id, entry in me.iter_catalog_dinos(catalog, level200_only=True):
        assert item_id.endswith(me.L200_ID_SUFFIX), item_id
        l1_id = item_id[: -len(me.L200_ID_SUFFIX)]
        l1 = (catalog.get("Items") or {}).get(l1_id)
        assert l1 is not None, f"L200 sem L1: {item_id}"
        p1 = int(l1.get("Price") or 0)
        root = me.resolve_species_root_value(l1_id, l1)
        budget = me.resolve_species_premium_budget(l1_id, l1)
        assert root is not None and budget is not None
        expected = me.compute_l200_price(
            p1, root, budget, market_absolute_max=market_cap
        )
        assert expected is not None
        assert int(entry.get("Price") or 0) == expected
        assert me.catalog_dino_level(entry) == 200
        d0 = (entry.get("Dinos") or [{}])[0]
        assert not (d0.get("Gender") or "").strip(), f"{item_id} deve ter sexo aleatório"
        for field in ("Name", "Description"):
            text = str(entry.get(field) or "")
            assert "Fêmea" not in text and "Femea" not in text, f"{item_id}.{field}"


def test_repo_indominus_option_a():
    if not CONFIG.is_file():
        return
    defaults = ROOT / "plugin" / "arkshop_web" / "data" / "market_species_defaults.json"
    me._DEFAULTS_FILE = defaults.resolve()
    for fn_name in ("load_defaults_file", "load_default_species_map", "build_catalog_economy_map"):
        fn = getattr(me, fn_name, None)
        if fn is not None and hasattr(fn, "cache_clear"):
            fn.cache_clear()  # type: ignore[attr-defined]

    catalog = json.loads(CONFIG.read_text(encoding="utf-8"))
    l1 = (catalog.get("Items") or {}).get("indominus_femea")
    l200 = (catalog.get("Items") or {}).get("indominus_femea_l200")
    if not l1:
        return
    assert int(l1.get("Price") or 0) == 28_000
    root = me.resolve_species_root_value("indominus_femea", l1)
    budget = me.resolve_species_premium_budget("indominus_femea", l1)
    assert root == 28_000
    assert budget == 122_000
    assert me.compute_v254(root, budget) == 150_000
    if l200:
        assert int(l200.get("Price") or 0) == 60_000
