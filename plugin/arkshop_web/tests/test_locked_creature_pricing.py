"""Precificação travada: catálogo, P2P, encomenda e aplicar Price numa cópia."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import market_economy as me

_HTML = Path(__file__).resolve().parents[1] / "static" / "index.html"
_ROUTES = Path(__file__).resolve().parents[1] / "market_routes.py"
_REX_BP = "/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP"
_GIGA_BP = "/Game/PrimalEarth/Dinos/Giganotosaurus/Gigant_Character_BP.Gigant_Character_BP"
_MEGA_BP = "/Game/PrimalEarth/Dinos/Megalosaurus/Megalosaurus_Character_BP.Megalosaurus_Character_BP"
_BEE_BP = "/Game/PrimalEarth/Dinos/Bee/Bee_Character_BP.Bee_Character_BP"
_STRIDER_BP = "/Game/Genesis2/Dinos/TekStrider/TekStrider_Character_BP.TekStrider_Character_BP"


def _dino(name: str, price: int, blueprint: str, level: int = 200) -> dict:
    return {
        "Type": "dino",
        "Name": name,
        "Price": price,
        "Quantity": 7,
        "Description": "nao-mexer",
        "Dinos": [{"Blueprint": blueprint, "Level": level, "Gender": 1}],
    }


def _catalog() -> dict:
    return {
        "ShopName": "Arkland",
        "Items": {
            "rex_femea": _dino("Rex", 1, _REX_BP, 200),
            "rex_macho": _dino("Rex", 2, _REX_BP, 1),
            "pf_alpha_rex": _dino("Rex Alpha", 3, _REX_BP),
            "pf_toxic_rex": _dino("Rex Toxic", 4, _REX_BP),
            "pf_noxious_rex": _dino("Rex Noxious", 5, _REX_BP),
            "giga_femea": _dino("Giga", 6, _GIGA_BP),
            "pf_alpha_giga": _dino("Giga Alpha", 7, _GIGA_BP),
            "pf_alpha_giant_bee": _dino("Abelha Alpha", 8, _BEE_BP),
            "pf_fey_megalosaurus": _dino("Megalossauro Fey", 9, _MEGA_BP),
            "pf_celestial_megalosaurus": _dino("Megalossauro Celestial", 10, _MEGA_BP),
            "tekstrider_femea": _dino("Tek Strider", 11, _STRIDER_BP),
            "pf_elder_rex": _dino("Rex Elder", 12, _REX_BP),
            "zzz_sem_familia": _dino("Criatura Solta", 13, "/Game/Mods/Nada/Nada_Character_BP.Nada_Character_BP"),
            "pfb_mini_boss": _dino("Mini Boss", 14, "/Game/Mods/Primal_Fear_Bosses/Boss_Character_BP.Boss_Character_BP"),
            "metal": {"Type": "item", "Name": "Metal", "Price": 10, "Quantity": 99, "Description": "item"},
        },
        "Kits": {"starter": {"Price": 50, "Description": "kit", "Items": [{"Item": "metal", "Amount": 3}]}},
    }


def _row(catalog: dict, item_id: str) -> dict:
    rows = {row["catalog_item_id"]: row for row in me.list_locked_catalog_pricing(catalog)}
    return rows[item_id]


def test_conference_numbers_use_stored_roots_and_half_up():
    species = me.load_default_species_map()
    assert int(species["rex"]["root_value"]) == 18_000
    assert int(species["giga"]["root_value"]) == 22_500
    assert int(species["megalosaurus"]["root_value"]) == 9_000
    assert int(species["megalosaurus"]["premium_budget"]) == 66_000
    assert int(species["giant_bee"]["root_value"]) == 800

    examples = me.locked_pricing_examples()
    assert examples["rex_vanilla"] == 7_500
    assert examples["rex_alpha"] == 37_500
    assert examples["giga_vanilla"] == 9_375
    assert examples["giga_alpha"] == 46_875
    assert examples["utility_root_800_alpha"] == 1_667
    assert examples["megalosaurus_fey_catalog"] == 103_125
    assert examples["megalosaurus_fey_p2p"] == 169_125
    assert examples["megalosaurus_fey_encomenda"] == 266_805
    assert examples["noxious_index"] == examples["toxic_index"] == "2.25"
    assert examples["fey_index"] == examples["celestial_index"] == examples["demonic_index"] == "20.625"
    assert examples["megalosaurus_fey_encomenda"] > examples["megalosaurus_fey_p2p"]

    full = {key: 254 for key in ("health", "melee", "weight", "stamina")}
    assert me.locked_attack_quality(full) == Decimal(1)
    assert me.locked_catalog_price(800, Decimal("3.75")) == 1_667
    raw = (Decimal(10_000) * Decimal(800) * Decimal("3.75")) / Decimal(18_000)
    assert raw != raw.to_integral_value()
    assert me.locked_round_half_up(raw) == 1_667


def test_catalog_rows_match_the_locked_indexes():
    catalog = _catalog()
    rex_200 = _row(catalog, "rex_femea")
    rex_1 = _row(catalog, "rex_macho")
    assert rex_200["level"] == 200 and rex_1["level"] == 1
    assert rex_200["calculated_price"] == rex_1["calculated_price"] == 7_500
    assert rex_200["family_key"] == "rex"
    assert rex_200["coefficient_label"] == "1"
    assert rex_200["tier_label"] == "Vanilla"
    assert rex_200["index_label"] == "0,75"

    assert _row(catalog, "pf_alpha_rex")["calculated_price"] == 37_500
    assert _row(catalog, "giga_femea")["calculated_price"] == 9_375
    assert _row(catalog, "giga_femea")["coefficient_label"] == "1,25"
    assert _row(catalog, "pf_alpha_giga")["calculated_price"] == 46_875

    bee = _row(catalog, "pf_alpha_giant_bee")
    assert bee["family_key"] == "giant_bee"
    assert bee["family_root"] == 800
    assert bee["calculated_price"] == 1_667

    toxic = _row(catalog, "pf_toxic_rex")
    noxious = _row(catalog, "pf_noxious_rex")
    assert toxic["calculated_price"] == noxious["calculated_price"] == 22_500
    assert toxic["index_label"] == noxious["index_label"] == "2,25"

    fey = _row(catalog, "pf_fey_megalosaurus")
    celestial = _row(catalog, "pf_celestial_megalosaurus")
    assert fey["family_key"] == celestial["family_key"] == "megalosaurus"
    assert fey["family_root"] == 9_000
    assert fey["coefficient_label"] == "0,5"
    assert fey["calculated_price"] == celestial["calculated_price"] == 103_125
    assert fey["index_label"] == celestial["index_label"] == "20,625"
    assert fey["level"] == 200


def test_rock_elemental_keeps_the_vanilla_index():
    species = me.load_default_species_map()
    root = int(species["rock_elemental"]["root_value"])
    assert root == 2_500
    catalog = {
        "Items": {
            "rock_elemental": _dino(
                "Rock Elemental",
                1,
                "/Game/ScorchedEarth/Dinos/RockGolem/RockGolem_Character_BP.RockGolem_Character_BP",
            ),
            "pf_elemental_fire_rex": _dino("Rex Elemental Fogo", 1, _REX_BP),
        }
    }
    rock = _row(catalog, "rock_elemental")
    assert rock["family_key"] == "rock_elemental"
    assert rock["tier_label"] == "Vanilla"
    assert rock["calculated_price"] == me.locked_catalog_price(root, Decimal("0.75")) == 1_042
    elemental = _row(catalog, "pf_elemental_fire_rex")
    assert elemental["family_key"] == "rex"
    assert elemental["tier_label"] == "Elemental Basic"
    assert elemental["calculated_price"] == 56_250


def test_tek_strider_and_rows_without_index_or_family_have_no_automatic_price():
    catalog = _catalog()
    strider = _row(catalog, "tekstrider_femea")
    elder = _row(catalog, "pf_elder_rex")
    missing = _row(catalog, "zzz_sem_familia")
    boss = _row(catalog, "pfb_mini_boss")
    for row in (strider, elder, missing, boss):
        assert row["calculated_price"] is None
        assert row["can_apply_calculated"] is False
        assert row["block_reason"]
    assert "Tek Strider" in strider["block_reason"]
    assert "Elder" in elder["block_reason"]
    assert "família" in missing["block_reason"]
    assert "Chefe" in boss["block_reason"]
    assert len(me.list_locked_catalog_pricing(catalog)) == 14


def test_apply_one_and_bulk_change_only_price_on_a_temp_copy(tmp_path: Path):
    source = _catalog()
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(source, indent=2), encoding="utf-8")
    untouched = tmp_path / "outro" / "catalog.json"
    untouched.parent.mkdir()
    untouched.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    protected = {
        "catalog.json.bak-antes-itens-pf": "pf-antigo",
        "catalog.json.bak-antes-ajuste-precos": "precos-antigo",
    }
    for name, text in protected.items():
        (tmp_path / name).write_text(text, encoding="utf-8")

    one = me.apply_locked_prices_at_path(path, mode="one", catalog_item_id="rex_femea")
    assert one["written"] is True
    assert one["backup"] is None
    assert one["changed"] == [{
        "catalog_item_id": "rex_femea",
        "old_price": 1,
        "new_price": 7_500,
        "source": "calculado",
    }]
    after_one = json.loads(path.read_text(encoding="utf-8"))
    assert after_one["Items"]["rex_femea"]["Price"] == 7_500
    assert after_one["Items"]["rex_femea"]["Quantity"] == 7
    assert after_one["Items"]["pf_alpha_rex"]["Price"] == 3
    assert list(tmp_path.glob("catalog.json.bak-precificacao-*")) == []

    manual = me.apply_locked_prices_at_path(
        path,
        mode="one",
        catalog_item_id="tekstrider_femea",
        manuals={"tekstrider_femea": 4242},
    )
    assert manual["written"] is True
    assert json.loads(path.read_text(encoding="utf-8"))["Items"]["tekstrider_femea"]["Price"] == 4242

    blocked = me.apply_locked_prices_at_path(path, mode="one", catalog_item_id="pf_elder_rex")
    assert blocked["written"] is False
    assert json.loads(path.read_text(encoding="utf-8"))["Items"]["pf_elder_rex"]["Price"] == 12

    bulk = me.apply_locked_prices_at_path(
        path,
        mode="bulk",
        manuals={"pf_elder_rex": 888, "zzz_sem_familia": ""},
    )
    assert bulk["written"] is True
    assert bulk["backup"]
    backup_path = Path(bulk["backup"])
    assert backup_path.is_file()
    assert backup_path.parent == path.parent
    assert backup_path.name not in protected
    saved_before = json.loads(backup_path.read_text(encoding="utf-8"))
    assert saved_before["Items"]["pf_alpha_rex"]["Price"] == 3
    assert saved_before["Items"]["tekstrider_femea"]["Price"] == 4242

    final = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "rex_femea": 7_500,
        "rex_macho": 7_500,
        "pf_alpha_rex": 37_500,
        "pf_toxic_rex": 22_500,
        "pf_noxious_rex": 22_500,
        "giga_femea": 9_375,
        "pf_alpha_giga": 46_875,
        "pf_alpha_giant_bee": 1_667,
        "pf_fey_megalosaurus": 103_125,
        "pf_celestial_megalosaurus": 103_125,
        "tekstrider_femea": 4242,
        "pf_elder_rex": 888,
        "zzz_sem_familia": 13,
        "pfb_mini_boss": 14,
    }
    for item_id, price in expected.items():
        assert final["Items"][item_id]["Price"] == price
        assert final["Items"][item_id]["Quantity"] == source["Items"][item_id]["Quantity"]
        assert final["Items"][item_id]["Description"] == source["Items"][item_id]["Description"]
    assert final["Items"]["metal"] == source["Items"]["metal"]
    assert final["Kits"] == source["Kits"]
    assert final["ShopName"] == "Arkland"
    assert json.loads(untouched.read_text(encoding="utf-8"))["Items"]["rex_femea"]["Price"] == 1
    for name, text in protected.items():
        assert (tmp_path / name).read_text(encoding="utf-8") == text
    assert not (tmp_path / "catalog.json.bak-antes-itens-pf").samefile(backup_path)


def test_origin_correction_and_new_family_price_without_touching_catalog_fields(tmp_path: Path):
    loose = "/Game/Mods/Nada/Nada_Character_BP.Nada_Character_BP"
    catalog = {
        "ShopName": "Arkland",
        "Items": {
            "zzz_sem_familia": _dino("Criatura Solta", 13, loose),
            "outra_solta": _dino("Outra Solta", 21, loose),
            "pf_elder_solta": _dino("Solta Elder", 5, loose),
            "tekstrider_femea": _dino("Tek Strider", 11, _STRIDER_BP),
            "metal": {"Type": "item", "Name": "Metal", "Price": 10, "Quantity": 99, "Description": "item"},
        },
        "Kits": {"starter": {"Price": 50, "Description": "kit", "Items": [{"Item": "metal", "Amount": 3}]}},
    }
    bare = _row(catalog, "zzz_sem_familia")
    assert bare["calculated_price"] is None
    assert bare["can_apply_calculated"] is False
    assert bare["block_reason"] == "Sem família vanilla com raiz gravada. Sem preço automático."
    assert bare["origin_fields"] is True
    assert _row(catalog, "tekstrider_femea")["calculated_price"] is None

    defaults_path = me._defaults_file_path()
    repo_defaults = Path(__file__).resolve().parents[1] / "data" / "market_species_defaults.json"
    assert defaults_path.resolve() != repo_defaults.resolve()
    before = json.loads(defaults_path.read_text(encoding="utf-8"))

    refused = me.set_catalog_pricing_origin("zzz_sem_familia", family_key="familia_inventada")
    assert refused["ok"] is False
    assert _row(catalog, "zzz_sem_familia")["calculated_price"] is None

    rex_root = int(me.load_default_species_map()["rex"]["root_value"])
    assert rex_root == 18_000
    pointed = me.set_catalog_pricing_origin("zzz_sem_familia", family_key="rex")
    assert pointed["ok"] is True
    rex_row = _row(catalog, "zzz_sem_familia")
    assert rex_row["calculated_price"] == me.locked_catalog_price(rex_root, Decimal("0.75"))
    assert rex_row["calculated_price"] == 7_500
    assert rex_row["index_label"] == "0,75"
    assert rex_row["missing_family_message"] == bare["block_reason"]

    manual = me.set_catalog_pricing_origin("zzz_sem_familia", family_key="", manual_root=12_000)
    assert manual["ok"] is True
    manual_row = _row(catalog, "zzz_sem_familia")
    assert manual_row["calculated_price"] == me.locked_catalog_price(12_000, Decimal("0.75"))
    assert manual_row["calculated_price"] == 5_000
    assert manual_row["coefficient_source"] == "manual_root"

    cleared = me.set_catalog_pricing_origin("zzz_sem_familia", family_key="", manual_root=None)
    assert cleared["ok"] is True
    assert _row(catalog, "zzz_sem_familia")["calculated_price"] is None

    no_root = me.create_catalog_pricing_family("fantasma_solta", "Fantasma", None)
    assert no_root["ok"] is False
    assert "fantasma" not in {row["species_key"] for row in me.list_locked_pricing_families()}

    created = me.create_catalog_pricing_family("zzz_sem_familia", "Basilisk", 12_000)
    assert created["ok"] is True
    assert created["species_key"] == "basilisk"
    assert created["root_value"] == 12_000
    basil = _row(catalog, "zzz_sem_familia")
    assert basil["family_key"] == "basilisk"
    assert basil["family_root"] == 12_000
    assert basil["calculated_price"] == 5_000
    assert basil["calculated_price"] == me.locked_catalog_price(12_000, Decimal("0.75"))
    assert basil["missing_family_message"] == "Sem família vanilla com raiz gravada. Sem preço automático."
    assert basil["can_apply_calculated"] is True

    families = {row["species_key"]: row for row in me.list_locked_pricing_families()}
    assert families["basilisk"]["source"] == "criada"
    assert families["basilisk"]["root_value"] == 12_000
    assert families["rex"]["source"] == "gravada"

    other = me.set_catalog_pricing_origin("outra_solta", family_key="basilisk")
    assert other["ok"] is True
    assert _row(catalog, "outra_solta")["calculated_price"] == 5_000

    me.set_catalog_pricing_origin("pf_elder_solta", family_key="basilisk")
    elder = _row(catalog, "pf_elder_solta")
    assert elder["calculated_price"] is None
    assert "Elder" in elder["block_reason"]

    assert _row(catalog, "tekstrider_femea")["calculated_price"] is None
    me.set_catalog_pricing_origin("tekstrider_femea", manual_root=18_000)
    assert _row(catalog, "tekstrider_femea")["calculated_price"] == 7_500

    after = json.loads(defaults_path.read_text(encoding="utf-8"))
    assert after["species"] == before["species"]
    recorded = next(row for row in after["species"] if row.get("species_key") == "basilisk")
    assert recorded["root_value"] == 3_500
    assert after["_catalog_pricing_origins"]["families"]["basilisk"] == {
        "display_name": "Basilisk",
        "root_value": 12_000,
    }
    real = {
        "Items": {
            "basilisk": _dino(
                "Basilisk",
                1,
                "/Game/Aberration/Dinos/Basilisk/Basilisk_Character_BP.Basilisk_Character_BP",
            ),
        }
    }
    automatic = _row(real, "basilisk")
    assert automatic["origin_fields"] is False
    assert automatic["family_root"] == 3_500
    assert automatic["calculated_price"] == me.locked_catalog_price(3_500, Decimal("0.75"))

    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    original = catalog["Items"]["zzz_sem_familia"]
    one = me.apply_locked_prices_at_path(path, mode="one", catalog_item_id="zzz_sem_familia")
    assert one["written"] is True
    assert one["changed"] == [{
        "catalog_item_id": "zzz_sem_familia",
        "old_price": 13,
        "new_price": 5_000,
        "source": "calculado",
    }]
    saved = json.loads(path.read_text(encoding="utf-8"))
    item = saved["Items"]["zzz_sem_familia"]
    assert item["Price"] == 5_000
    assert set(item) == set(original)
    for key, value in original.items():
        if key != "Price":
            assert item[key] == value
    assert "_catalog_pricing_origins" not in saved
    assert saved["Items"]["metal"] == catalog["Items"]["metal"]
    assert saved["Kits"] == catalog["Kits"]
    assert saved["Items"]["outra_solta"]["Price"] == 21

    me.set_catalog_pricing_origin("zzz_sem_familia", family_key="", manual_root=None)
    clean = {
        "Items": {
            "zzz_sem_familia": _dino("Criatura Solta", 13, loose),
            "rex_femea": _dino("Rex", 1, _REX_BP),
        }
    }
    clean_path = tmp_path / "limpo" / "catalog.json"
    clean_path.parent.mkdir()
    clean_path.write_text(json.dumps(clean), encoding="utf-8")
    bulk = me.apply_locked_prices_at_path(clean_path, mode="bulk")
    assert bulk["written"] is True
    assert "zzz_sem_familia" not in {row["catalog_item_id"] for row in bulk["changed"]}
    assert "zzz_sem_familia" in {row["catalog_item_id"] for row in bulk["skipped"]}
    final = json.loads(clean_path.read_text(encoding="utf-8"))
    assert final["Items"]["zzz_sem_familia"]["Price"] == 13
    assert final["Items"]["rex_femea"]["Price"] == 7_500
    assert set(final["Items"]["zzz_sem_familia"]) == set(clean["Items"]["zzz_sem_familia"])


def test_page_shows_the_three_formulas_and_apply_buttons():
    html = _HTML.read_text(encoding="utf-8")
    start = html.find('id="locked-pricing-formulas"')
    end = html.find('id="market-economy-panel-precos"')
    formulas = html[start:end]
    assert "10.000 × coeficiente × índice" in formulas
    assert "7.500" in formulas
    assert "103.125" in formulas
    assert "169.125" in formulas
    assert "266.805" in formulas
    assert "Noxious acompanha Toxic" in formulas
    assert "Fey acompanha" in formulas
    assert "sempre acima do P2P" in formulas
    assert "275.000" in formulas
    assert "Sem teto fixo de 275.000" in formulas or "Não há teto fixo de 275.000" in formulas
    assert 'id="locked-pricing-apply-bulk"' in html
    assert "Aplicar em massa" in html
    assert "locked-pricing-manual" in html
    assert "Aplicar ajuste" in html
    assert "Família existente" in html
    assert "Família nova" in html
    assert "Criar família" in html
    assert "Raiz manual" in html
    assert "locked-pricing-origin-family" in html
    assert "locked-pricing-origin-root" in html
    assert "locked-pricing-create-family" in html
    routes = _ROUTES.read_text(encoding="utf-8")
    origin_start = routes.find("def market_admin_economy_pricing_origins")
    origin_end = routes.find("@app.route", origin_start)
    origin = routes[origin_start:origin_end]
    assert "create_catalog_pricing_family" in origin
    assert "set_catalog_pricing_origins" in origin
    assert "_resolve_shop_catalog" not in origin
    assert "apply_locked_prices_at_path" not in origin
    assert 'data-market-economy-tab="precos"' in html
    fn_start = routes.find("def market_admin_economy_apply_prices")
    fn_end = routes.find("@app.route", fn_start)
    fn = routes[fn_start:fn_end]
    assert "_resolve_shop_catalog" in fn
    assert "apply_locked_prices_at_path" in fn
    assert "_persist_shop_catalog" not in fn
    assert "_write_config_all_targets" not in fn
    assert "resolve_persistent_catalog_path" not in fn
