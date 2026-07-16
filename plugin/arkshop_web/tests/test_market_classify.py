"""Testes do fluxo admin de classificação de listings."""
from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from app import _configure_database

SELLER = "76561198000000003"
TRACE = "classifytest000000000000000001"


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'market_classify.db'}"
    monkeypatch.setattr(_app_module, "_DATABASE_URL", db_url)
    monkeypatch.setattr(_app_module, "_build_database_url_from_settings", lambda _s=None: None)
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    monkeypatch.setattr(threading.Thread, "start", lambda self: self.run())
    monkeypatch.setattr(_app_module, "_start_db_reconnect_watcher", lambda: None)

    _orig_configure = _app_module._configure_database

    def _sqlite_only_configure(url: str) -> None:
        normalized = (url or "").strip()
        if normalized and "mysql" in normalized.lower():
            return
        _orig_configure(url)

    monkeypatch.setattr(_app_module, "_configure_database", _sqlite_only_configure)
    _sqlite_only_configure(db_url)
    yield
    _sqlite_only_configure("")


def _session():
    url = _app_module._ACTIVE_DATABASE_URL
    if url and "sqlite" in str(url):
        _app_module._configure_database(url)
    return _app_module._SessionLocal()


def _seed_profile(db):
    from app import MarketPlayerProfile

    db.add(
        MarketPlayerProfile(
            steam_id=SELLER,
            market_display_name="AnkyTrader",
            commerce_enabled=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


def _ankylo_upload_body():
    return {
        "steam_id": SELLER,
        "inventory_removed": True,
        "inventory_verified_empty": True,
        "item_blob_hex": "0a0b0c",
        "upload_id": TRACE,
        "market_trace_id": TRACE,
        "metadata": {
            "species_blueprint": "/Game/PrimalEarth/Dinos/Ankylo/Ankylo_Character_BP.Ankylo_Character_BP",
            "imprint_pct": 1.0,
            "name_map": "Ankylo_Character_BP_C_257",
            "stats_max": {"melee": {"points": 40}},
            "dino_level": 224,
            "dino_identity": {
                "dino_id1": 0x55556666,
                "dino_id2": 0x77778888,
                "ancestors": [],
            },
        },
    }


def test_admin_classify_promotes_to_draft():
    from market_listings import admin_classify_listing, listing_to_public, process_plugin_upload

    db = _session()
    try:
        _seed_profile(db)
        result = process_plugin_upload(db, _ankylo_upload_body())
        assert result["status"] == "PENDING_CLASSIFICATION"
        listing_id = result["listing_id"]

        from app import MarketListing

        row = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
        meta = json.loads(row.metadata_json)
        sug = meta.get("classification_suggestion")
        assert sug is not None
        assert sug.get("display_name") == "Anquilossauro"

        pub_pending = listing_to_public(row, include_breakdown=True)
        assert "Character_BP" not in pub_pending["display_title"]
        assert pub_pending["suggested_base_value"] >= 800

        out = admin_classify_listing(
            db,
            listing_id,
            species_key="ankylo",
            display_name="Anquilossauro",
            tier="B",
            root_value=2000,
            approve=True,
        )
        assert out["listing_status"] == "DRAFT"
        assert out["species_status"] == "ACTIVE"

        from app import MarketSpecies

        listing = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
        species = db.query(MarketSpecies).filter(
            MarketSpecies.species_key == listing.species_key
        ).first()
        assert species is not None
        assert species.status == "ACTIVE"
        assert listing.status == "DRAFT"
        assert listing.computed_base_value >= 2000

        pub = listing_to_public(listing, species_row=species, include_breakdown=True)
        assert pub["display_title"] == "Anquilossauro"
        assert pub["awaiting_classification"] is False
    finally:
        db.close()


def test_admin_classify_accepts_draft_without_approval():
    """Reproduz cenário DRAFT na fila admin (reconcile/ativação espécie sem classify)."""
    import json

    from app import MarketListing
    from market_listings import admin_classify_listing, listing_to_public, process_plugin_upload

    db = _session()
    try:
        _seed_profile(db)
        result = process_plugin_upload(db, _ankylo_upload_body())
        listing_id = result["listing_id"]

        from app import MarketListing

        listing = db.query(MarketListing).filter(MarketListing.id == listing_id).first()
        meta = json.loads(listing.metadata_json)
        meta.pop("admin_classification_approved", None)
        listing.metadata_json = json.dumps(meta)
        listing.status = "DRAFT"
        listing.computed_base_value = 0
        db.commit()

        pub = listing_to_public(listing, include_breakdown=True)
        assert pub["status"] == "DRAFT"
        assert pub["awaiting_classification"] is True

        out = admin_classify_listing(
            db,
            listing_id,
            species_key="ankylo",
            display_name="Anquilossauro",
            tier="B",
            root_value=2000,
            approve=True,
        )
        assert out["listing_status"] == "DRAFT"
        assert out["computed_base_value"] >= 2000

        db.refresh(listing)
        meta_after = json.loads(listing.metadata_json)
        assert meta_after.get("admin_classification_approved") is True
        assert listing.computed_base_value >= 2000
    finally:
        db.close()
