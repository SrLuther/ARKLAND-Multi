"""Conflito de blueprint_norm em market_species_aliases (Incluir no Comércio).

Reproduz o UPDATE do alias do item da loja para um blueprint_norm que já
existe em outra linha (unique ux/uq em blueprint_norm).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from app import _configure_database

ALPHA_BP = (
    "/Game/Mods/Primal_Fear/Dinos/Alpha/Alpha_Baryonyx/"
    "AlphaBaryonyx_Character_BP.AlphaBaryonyx_Character_BP"
)
STALE_BP = "/Game/Mods/Primal_Fear/Dinos/Alpha/Alpha_Baryonyx/Legacy_BP.Legacy_BP"
GIGA_BP = "/Game/Dinos/GigaLivre/GigaLivre_Character_BP.GigaLivre_Character_BP"

SHOP_SAME = "pf_alpha_baryonyx_shop"
SHOP_OTHER = "pf_baryonyx_domestico"
SHOP_NEXT = "giga_lote_ok"


def _norm(bp: str) -> str:
    from market_economy import normalize_blueprint

    return normalize_blueprint(bp)


def _now():
    return datetime.now(timezone.utc)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'alias_bp_conflict.db'}"
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(db_url)
    session = _app_module._SessionLocal()
    try:
        yield session
    finally:
        session.close()
        try:
            _app_module._SessionLocal.remove()
        except Exception:
            pass
        _configure_database("")


def _species(db, species_key: str, *, blueprint: str = ""):
    from app import MarketSpecies

    row = MarketSpecies(
        species_key=species_key,
        display_name=species_key,
        blueprint_path=blueprint or None,
        root_value=1000,
        tier="B",
        status="PRE_REGISTERED",
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    db.flush()
    return row


def _alias(db, species_id: int, *, blueprint: str, catalog_item_id: str | None):
    from app import MarketSpeciesAlias

    row = MarketSpeciesAlias(
        species_id=species_id,
        catalog_item_id=catalog_item_id,
        blueprint_path=blueprint,
        blueprint_norm=_norm(blueprint),
        variant_label=catalog_item_id,
    )
    db.add(row)
    db.flush()
    return row


def _dino(item_id: str, blueprint: str, name: str) -> dict:
    return {
        "Type": "dino",
        "Name": name,
        "Price": 4200,
        "Dinos": [{"Blueprint": blueprint, "Level": 1}],
    }


def test_sync_same_species_does_not_rewrite_alias_onto_taken_blueprint(db):
    """Alias B (item da loja) não pode receber o blueprint_norm que já está em A."""
    from app import MarketSpeciesAlias
    from market_service import _sync_species_aliases

    species = _species(db, SHOP_SAME, blueprint=STALE_BP)
    alias_a = _alias(db, species.id, blueprint=ALPHA_BP, catalog_item_id=None)
    alias_b = _alias(db, species.id, blueprint=STALE_BP, catalog_item_id=SHOP_SAME)
    db.commit()
    id_a, id_b = alias_a.id, alias_b.id

    conflicts = _sync_species_aliases(
        db,
        species,
        [
            {
                "catalog_item_id": SHOP_SAME,
                "blueprint_path": ALPHA_BP,
                "blueprint_norm": _norm(ALPHA_BP),
                "variant_label": "Alpha Baryonyx",
            }
        ],
    )
    db.commit()

    assert conflicts == []
    owners = (
        db.query(MarketSpeciesAlias)
        .filter(MarketSpeciesAlias.blueprint_norm == _norm(ALPHA_BP))
        .all()
    )
    assert len(owners) == 1
    assert owners[0].id == id_a
    assert owners[0].species_id == species.id
    moved = db.get(MarketSpeciesAlias, id_b)
    assert moved is None or moved.blueprint_norm != _norm(ALPHA_BP)


def test_pre_register_same_species_treats_blueprint_as_already_registered(db):
    from app import MarketSpeciesAlias
    from market_service import pre_register_catalog_item

    species = _species(db, SHOP_SAME, blueprint=STALE_BP)
    _alias(db, species.id, blueprint=ALPHA_BP, catalog_item_id=None)
    _alias(db, species.id, blueprint=STALE_BP, catalog_item_id=SHOP_SAME)
    db.commit()

    catalog = {"ShopItems": {SHOP_SAME: _dino(SHOP_SAME, ALPHA_BP, "Alpha Baryonyx")}}
    result = pre_register_catalog_item(db, catalog, SHOP_SAME)

    assert result["status"] == "PRE_REGISTERED"
    assert result["species_key"] == SHOP_SAME
    owners = (
        db.query(MarketSpeciesAlias)
        .filter(MarketSpeciesAlias.blueprint_norm == _norm(ALPHA_BP))
        .all()
    )
    assert len(owners) == 1
    assert owners[0].species_id == species.id


def test_pre_register_other_species_skips_item_and_continues_batch(db):
    """Blueprint de outra espécie não é fundido; o item seguinte do lote segue."""
    from app import MarketSpecies, MarketSpeciesAlias
    from market_service import pre_register_catalog_item

    owner = _species(db, "pf_alpha_baryonyx", blueprint=ALPHA_BP)
    alias_a = _alias(db, owner.id, blueprint=ALPHA_BP, catalog_item_id=None)
    domestico = _species(db, SHOP_OTHER, blueprint=STALE_BP)
    alias_b = _alias(db, domestico.id, blueprint=STALE_BP, catalog_item_id=SHOP_OTHER)
    db.commit()
    id_a, id_b = alias_a.id, alias_b.id
    owner_id = owner.id

    catalog = {
        "ShopItems": {
            SHOP_OTHER: _dino(SHOP_OTHER, ALPHA_BP, "Baryonyx Doméstico"),
            SHOP_NEXT: _dino(SHOP_NEXT, GIGA_BP, "Giga livre"),
        }
    }

    with pytest.raises(ValueError, match="outra espécie"):
        pre_register_catalog_item(db, catalog, SHOP_OTHER)

    db.expire_all()
    kept = db.get(MarketSpeciesAlias, id_a)
    assert kept is not None
    assert kept.species_id == owner_id
    assert kept.blueprint_norm == _norm(ALPHA_BP)
    other = db.get(MarketSpeciesAlias, id_b)
    assert other is not None
    assert other.blueprint_norm == _norm(STALE_BP)
    assert other.species_id == domestico.id

    nxt = pre_register_catalog_item(db, catalog, SHOP_NEXT)
    assert nxt["status"] == "PRE_REGISTERED"
    assert nxt["species_key"] == SHOP_NEXT
    assert (
        db.query(MarketSpecies).filter(MarketSpecies.species_key == SHOP_NEXT).count()
        == 1
    )


def test_bulk_market_include_continues_after_blueprint_conflict(db):
    from app import MarketSpecies

    owner = _species(db, "pf_alpha_baryonyx", blueprint=ALPHA_BP)
    _alias(db, owner.id, blueprint=ALPHA_BP, catalog_item_id=None)
    domestico = _species(db, SHOP_OTHER, blueprint=STALE_BP)
    _alias(db, domestico.id, blueprint=STALE_BP, catalog_item_id=SHOP_OTHER)
    db.commit()
    try:
        _app_module._SessionLocal.remove()
    except Exception:
        pass

    catalog = {
        "ShopItems": {
            SHOP_OTHER: _dino(SHOP_OTHER, ALPHA_BP, "Baryonyx Doméstico"),
            SHOP_NEXT: _dino(SHOP_NEXT, GIGA_BP, "Giga livre"),
        }
    }
    extra = _app_module._shop_bulk_after_market_include([SHOP_OTHER, SHOP_NEXT], catalog)

    warning = extra[SHOP_OTHER].get("warning") or ""
    assert "IntegrityError" not in warning
    assert "outra espécie" in warning
    assert extra[SHOP_NEXT].get("market_status") == "PRE_REGISTERED"
    assert "warning" not in extra[SHOP_NEXT]

    check = _app_module._SessionLocal()
    try:
        assert (
            check.query(MarketSpecies)
            .filter(MarketSpecies.species_key == SHOP_NEXT)
            .count()
            == 1
        )
        owner_row = (
            check.query(MarketSpecies)
            .filter(MarketSpecies.species_key == "pf_alpha_baryonyx")
            .one()
        )
        assert owner_row.root_value == 1000
    finally:
        check.close()
