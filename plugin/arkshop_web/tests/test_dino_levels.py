"""Dinos unificados: nível livre (1..teto), gênero, migração, filtros e endpoints."""
from __future__ import annotations

import copy
import json

import pytest

import app as _app_module
from app import app, _configure_database
from catalog_enrich import enrich_kit, enrich_shop_item
from dino_levels import (
    DEFAULT_DINO_LEVEL_MAX,
    base_item_id,
    collect_level_options,
    dino_card_meta,
    dino_level_max,
    entry_dino_gender,
    entry_dino_level,
    infer_gender_from_text,
    infer_level_from_text,
    interpolate_level_price,
    legacy_tab_redirect,
    level_variant_id,
    migrate_catalog_dinos,
    normalize_gender,
    parse_dino_level,
    retitle_for_level,
    validate_catalog_dino_levels,
)

REX_BP = "/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP"
ADMIN = "76561198000000001"


def _dino(desc="Rex", level=None, gender=None, **extra):
    d = {"Blueprint": REX_BP}
    if level is not None:
        d["Level"] = level
    if gender is not None:
        d["Gender"] = gender
    e = {"Type": "dino", "Price": 1000, "Description": desc, "Dinos": [d]}
    e.update(extra)
    return e


# ── parse / teto ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,expected", [
    (1, 1), (50, 50), ("100", 100), (150, 150), (200, 200), (225, 225), (500, 500),
    (200.0, 200), (" 75 ", 75),
])
def test_parse_accepts_any_valid_integer(raw, expected):
    assert parse_dino_level(raw, max_level=500) == expected


@pytest.mark.parametrize("raw", [0, -1, -200, "abc", "", None, 1.5, True, False, "12x", 501, 10_000])
def test_parse_rejects_invalid(raw):
    assert parse_dino_level(raw, max_level=500) is None


def test_level_max_precedence(monkeypatch):
    monkeypatch.delenv("ARKSHOP_DINO_LEVEL_MAX", raising=False)
    assert dino_level_max() == DEFAULT_DINO_LEVEL_MAX == 500
    monkeypatch.setenv("ARKSHOP_DINO_LEVEL_MAX", "300")
    assert dino_level_max() == 300
    assert dino_level_max({"shop_dino_level_max": 450}) == 450


# ── inferência ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("text,expected", [
    ("Rex LVL 200", 200), ("Rex Nível 150", 150), ("rex_femea_l225", 225), ("Rex L50", 50),
])
def test_infer_level_from_text(text, expected):
    assert infer_level_from_text(text) == expected


def test_level_precedence_dinos_field_beats_hints():
    e = _dino("Rex LVL 200", level=50, Category="Dinos 200")
    assert entry_dino_level(e, "rex_l200") == 50


@pytest.mark.parametrize("key,desc,cat,expected", [
    ("rex_l200", "Rex", None, 200),
    ("rex", "Rex LVL 200", None, 200),
    ("rex", "Rex", "Dinos 200", 200),
    ("rex_200", "Rex", None, 200),
    ("rex", "Rex", None, 1),
])
def test_legacy_catalog_level_inferred(key, desc, cat, expected):
    e = {"Type": "dino", "Description": desc, "Price": 1,
         "Dinos": [{"Blueprint": REX_BP}]}
    if cat:
        e["Category"] = cat
    assert entry_dino_level(e, key) == expected


@pytest.mark.parametrize("text,expected", [
    ("Rex FEMEA", "female"), ("Rex Fêmea", "female"), ("rex_fem", "female"),
    ("Rex MACHO", "male"), ("Rex MALE", "male"), ("Rex FEMALE", "female"),
    ("Casal de Rex", "pair"), ("Rex", None),
])
def test_gender_inference(text, expected):
    assert infer_gender_from_text(text) == expected


def test_gender_explicit_wins_and_normalizes():
    assert normalize_gender("Female") == "female"
    assert normalize_gender("Macho") == "male"
    e = _dino("Rex MACHO", gender="Female")
    assert entry_dino_gender(e, "rex_macho") == "female"


def test_dino_card_meta_marks_inferred_gender():
    meta = dino_card_meta(_dino("Rex FEMEA Nível 200"), "rex_femea_l200")
    assert meta["dino_level"] == 200
    assert meta["dino_gender"] == "female"
    assert meta["dino_gender_source"] == "inferred"
    meta2 = dino_card_meta(_dino(level=100, gender="male"), "rex")
    assert meta2["dino_gender_source"] == "explicit" and meta2["dino_level"] == 100


# ── lista dinâmica / redirect ────────────────────────────────────────────────
def test_collect_level_options_dynamic_sorted():
    entries = [{"dino_level": 200}, {"dino_level": 50}, {"dino_level": 200}, {"dino_level": 1}]
    assert collect_level_options(entries) == [
        {"level": 1, "count": 1}, {"level": 50, "count": 1}, {"level": 200, "count": 2}]


@pytest.mark.parametrize("tab", ["dinos200", "Dinos 200", "dinos-200", "dinos_200"])
def test_legacy_tab_redirect(tab):
    assert legacy_tab_redirect(tab) == ("dinos", 200)


def test_non_legacy_tab_untouched():
    assert legacy_tab_redirect("kits") == ("kits", None)


# ── validação / migração ─────────────────────────────────────────────────────
def test_validate_rejects_invalid_levels_only_when_informed():
    cat = {"Items": {
        "ok": _dino(level=225), "none": _dino(), "zero": _dino(level=0),
        "neg": _dino(level=-5), "txt": _dino(level="abc"), "big": _dino(level=9999),
    }}
    bad = {e["item_id"] for e in validate_catalog_dino_levels(cat, max_level=500)}
    assert bad == {"zero", "neg", "txt", "big"}


def test_migrate_is_idempotent_and_backward_compatible():
    cat = {"Items": {
        "rex_femea_l200": _dino("Rex FEMEA LVL 200", Category="Dinos 200"),
        "rex_femea": _dino("Rex FEMEA"),
        "rex_100": _dino("Rex", level=100),
    }}
    r1 = migrate_catalog_dinos(cat)
    items = cat["Items"]
    assert items["rex_femea_l200"]["Dinos"][0]["Level"] == 200
    assert items["rex_femea_l200"]["Category"] == "Dinos"
    assert items["rex_100"]["Dinos"][0]["Level"] == 100  # nunca sobrescreve
    assert "Gender" not in items["rex_femea_l200"]["Dinos"][0]  # opt-in
    assert r1["changed_items"] >= 1
    snapshot = copy.deepcopy(cat)
    r2 = migrate_catalog_dinos(cat)
    assert cat == snapshot and r2["changed_items"] == 0


def test_migrate_writes_gender_only_when_requested():
    cat = {"Items": {"rex_macho": _dino("Rex MACHO")}}
    migrate_catalog_dinos(cat, write_inferred_gender=True)
    assert cat["Items"]["rex_macho"]["Dinos"][0]["Gender"] == "male"


# ── geração de variantes ─────────────────────────────────────────────────────
def test_level_variant_helpers():
    assert base_item_id("rex_femea_l200") == "rex_femea"
    assert level_variant_id("rex_femea", 1) == "rex_femea"
    assert level_variant_id("rex_femea_l200", 225) == "rex_femea_l225"
    with pytest.raises(ValueError):
        level_variant_id("rex", 0)
    assert retitle_for_level("Rex Nível 1", 150) == "Rex Nível 150"
    assert retitle_for_level("Rex", 150) == "Rex Nível 150"


def test_interpolate_price_monotonic():
    prices = [interpolate_level_price(1000, 3000, lv) for lv in (1, 50, 100, 150, 200, 225)]
    assert prices == sorted(prices) and prices[0] == 1000
    assert interpolate_level_price(1000, 3000, 200) == 3000


def test_generate_variants_idempotent():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "tools" / "generate_dino_level_variants.py"
    spec = importlib.util.spec_from_file_location("gen_dino_variants", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cat = {"Items": {"rex_femea": _dino("Rex FEMEA Nível 1", level=1)}}
    created = mod.generate(cat, [1, 50, 225])
    assert [k for k, _ in created] == ["rex_femea_l50", "rex_femea_l225"]
    assert created[1][1]["Dinos"][0]["Level"] == 225
    for k, e in created:
        cat["Items"][k] = e
    assert mod.generate(cat, [1, 50, 225]) == []


# ── enrich ───────────────────────────────────────────────────────────────────
def test_enrich_dino_item_exposes_level_gender_and_unifies_category():
    meta = enrich_shop_item(
        "rex_femea_l200", _dino("Rex FEMEA Nível 200", level=200, Category="Dinos 200"))
    assert meta["display_category"] == "Dinos"
    assert meta["dino_level"] == 200 and meta["dino_gender"] == "female"
    assert "nv 200" in meta["search_text"]


def test_enrich_kit_with_dinos():
    kit = {"Description": "Kit Rex", "Price": 10,
           "Dinos": [{"Blueprint": REX_BP, "Level": 150, "Gender": "male"}]}
    meta = enrich_kit("kit_rex", kit)
    assert meta["dino_level"] == 150 and meta["dino_gender"] == "male"


# ── endpoints ────────────────────────────────────────────────────────────────
@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_API_KEY", "test-key")
    monkeypatch.setattr(_app_module, "_ARKSHOP_API_KEY", "test-key")
    monkeypatch.setattr(_app_module, "_ADMIN_FILE", tmp_path / "admin_steamids.json")
    monkeypatch.setattr(_app_module, "_STATE_FILE", tmp_path / "settings.json")
    (tmp_path / "admin_steamids.json").write_text(json.dumps([ADMIN]))
    catalog = tmp_path / "config.json"
    data = {
        "Settings": {"ShopName": "ARKLAND DONATIONS"},
        "Items": {
            "rex_femea": _dino("Rex FEMEA Nível 1", level=1),
            "rex_femea_l50": _dino("Rex FEMEA Nível 50", level=50),
            "rex_macho_l225": _dino("Rex MACHO Nível 225", level=225),
            "rex_femea_l200": _dino("Rex FEMEA LVL 200", Category="Dinos 200"),
        },
        "Kits": {"starter": {"Description": "Starter", "Price": 0}},
        "PointPackages": [],
    }
    catalog.write_text(json.dumps(data), encoding="utf-8")
    (tmp_path / "settings.json").write_text(
        json.dumps({"config_path": str(catalog)}), encoding="utf-8")
    monkeypatch.setattr(
        _app_module, "_resolve_settings_catalog_path",
        lambda configured="", _c=str(catalog): str(configured or _c).strip() or _c)
    monkeypatch.setattr(
        _app_module, "_heal_empty_shop_config_path",
        lambda preferred: (preferred, json.loads(catalog.read_text(encoding="utf-8")), None))
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(f"sqlite:///{tmp_path / 'test.db'}")
    _app_module._invalidate_public_catalog_cache()
    _app_module._invalidate_shop_config_cache()
    yield
    _app_module._invalidate_public_catalog_cache()
    _configure_database("")


@pytest.fixture
def client(env):
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_api_catalog_exposes_dynamic_levels(client):
    body = client.get("/api/catalog").get_json()
    items = body["items"]
    assert items["rex_femea_l50"]["dino_level"] == 50
    assert items["rex_macho_l225"]["dino_level"] == 225
    assert items["rex_macho_l225"]["dino_gender"] == "male"
    assert items["rex_femea_l200"]["dino_level"] == 200  # inferido
    assert items["rex_femea_l200"]["display_category"] == "Dinos"
    levels = [o["level"] for o in body["catalog_meta"]["dino_levels"]]
    assert levels == [1, 50, 200, 225]
    assert body["catalog_meta"]["dino_level_max"] >= 225


def test_api_dino_levels_endpoint(client):
    d = client.get("/api/catalog/dino-levels").get_json()
    assert d["ok"] is True
    assert [o["level"] for o in d["levels"]] == [1, 50, 200, 225]


@pytest.mark.parametrize("path", ["/dinos200", "/dinos-200", "/dinos_200"])
def test_legacy_route_redirects_to_dinos_level_200(client, path):
    r = client.get(path)
    assert r.status_code == 301
    loc = r.headers["Location"]
    assert "tab=dinos" in loc and "nivel=200" in loc


@pytest.mark.parametrize("bad", [0, -3, "abc", 99999])
def test_save_config_rejects_invalid_level(client, bad):
    with client.session_transaction() as sess:
        sess["steam_id"] = ADMIN
    r = client.post("/api/config", json={
        "Items": {"x": _dino(level=bad)}, "Kits": {}, "reload": False})
    assert r.status_code == 400
    d = r.get_json()
    assert d["ok"] is False and d["level_errors"]
    assert d["dino_level_max"] >= 1


def test_public_audit_endpoint_rejects_invalid_level(client):
    for bad in ("0", "-1", "abc"):
        r = client.get(f"/api/public/catalog-dinos?level={bad}")
        assert r.status_code in (400, 503), (bad, r.status_code)
        if r.status_code == 400:
            assert r.get_json()["ok"] is False
