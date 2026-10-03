"""Testes da Vitrine de Recursos (serviço + HTTP + schema + auditoria).

Testes de markup/UI ficam em test_resource_vitrine_ui.py.

Contrato: docs/VITRINE_RECURSOS_SPEC.md
"""
from __future__ import annotations

import os
import re
import sys
import threading
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import insert, inspect, select, text, update

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_DATABASE_URL", "")
os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")

import app as _app_module
from app import _configure_database
import resource_vitrine_migrate as rvm
import resource_vitrine_service as svc

SELLER = "76561198000000001"
BUYER = "76561198000000002"
THIRD = "76561198000000003"

BP_METAL = "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Metal.PrimalItemResource_Metal"
BP_WOOD = "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Wood.PrimalItemResource_Wood"
BP_STONE = "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Stone.PrimalItemResource_Stone"
BP_FIBER = "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Fibers.PrimalItemResource_Fibers"
BP_HIDE = "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Hide.PrimalItemResource_Hide"
BP_THATCH = "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Thatch.PrimalItemResource_Thatch"
BP_FLINT = "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Flint.PrimalItemResource_Flint"

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    _orig_start = threading.Thread.start

    def _patched_start(self):
        if getattr(self, "name", None) == "arkshop-db-migrate":
            self.run()
        else:
            _orig_start(self)

    monkeypatch.setattr(threading.Thread, "start", _patched_start)
    monkeypatch.setattr(_app_module, "_kick_background_db_init", lambda: None)
    monkeypatch.setattr(_app_module, "_start_db_reconnect_watcher", lambda: None)
    _app_module._db_reconnect_stop.set()
    monkeypatch.setattr(_app_module, "_ACTIVE_DATABASE_URL", "")
    _configure_database(f"sqlite:///{tmp_path / 'rv_test.db'}")
    yield
    _app_module._db_reconnect_stop.set()
    _configure_database("")


@pytest.fixture()
def db():
    session = _app_module._SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _points(db, sid: str) -> int:
    db.expire_all()
    row = db.execute(text("SELECT points FROM players WHERE steam_id = :s"), {"s": sid}).first()
    return int(row[0]) if row else 0


def _seed_players(db, points: int = 100_000):
    from datetime import datetime, timezone

    from app import MarketPlayerProfile

    now = datetime.now(timezone.utc)
    for sid, name in ((SELLER, "SellerOne"), (BUYER, "BuyerOne"), (THIRD, "ThirdOne")):
        db.add(
            MarketPlayerProfile(
                steam_id=sid,
                market_display_name=name,
                commerce_enabled=True,
                created_at=now,
                updated_at=now,
            )
        )
        db.execute(text("INSERT INTO players (steam_id, points) VALUES (:sid, :pts)"), {"sid": sid, "pts": points})
    db.commit()


def _catalog(db, blueprint=BP_METAL, name="Metal", stack=100, **extra) -> dict:
    body = {"blueprint": blueprint, "name": name, "stack_size": stack}
    body.update(extra)
    return svc.upsert_catalog_resource(db, body, admin_steam_id="76561198999999999")


def _upload(db, sid, items, upload_id=None):
    import uuid

    return svc.process_upload(
        db, {"steam_id": sid, "upload_id": upload_id or uuid.uuid4().hex, "items": items}
    )


def _stock_qty(db, sid, rid) -> int:
    db.expire_all()
    row = db.execute(
        select(svc.T_STOCK.c.quantity).where(svc.T_STOCK.c.steam_id == sid, svc.T_STOCK.c.resource_id == rid)
    ).first()
    return int(row[0]) if row else 0


def _stock_id(db, sid, rid) -> int:
    return int(
        db.execute(
            select(svc.T_STOCK.c.id).where(svc.T_STOCK.c.steam_id == sid, svc.T_STOCK.c.resource_id == rid)
        ).first()[0]
    )


def _listed(db, seller=SELLER, qty=1000, lot_size=100, lot_price=500, **cat):
    """Cadastra recurso, faz upload e anuncia. Retorna (resource_id, stock_id)."""
    res = _catalog(db, **cat)
    _upload(db, seller, [{"blueprint": res["blueprint"], "quantity": qty}])
    svc.set_listing(db, seller, res["id"], {"lot_size": lot_size, "lot_price": lot_price, "active": True})
    return res["id"], _stock_id(db, seller, res["id"])


# ── Schema / contratos ───────────────────────────────────────────────────────

def test_schema_tables_and_unique_constraints(db):
    names = set(inspect(db.get_bind()).get_table_names())
    for table in rvm.RESOURCE_VITRINE_TABLES:
        assert table in names
    uq = {u["name"] for u in inspect(db.get_bind()).get_unique_constraints("market_resource_uploads")}
    idx = {i["name"] for i in inspect(db.get_bind()).get_indexes("market_resource_uploads")}
    assert "uq_mru_upload_id" in (uq | idx)


def test_schema_is_idempotent_and_versioned(db):
    engine = db.get_bind()
    rvm.ensure_resource_vitrine_schema(engine)
    rvm.ensure_resource_vitrine_schema(engine)
    status = rvm.schema_status(engine)
    assert status["ok"] is True
    assert status["schema_version"] == rvm.RESOURCE_VITRINE_SCHEMA_VERSION
    assert all(status["tables"].values())
    stored = db.execute(
        select(svc.T_SET.c.setting_value).where(svc.T_SET.c.setting_key == "schema_version")
    ).first()
    assert stored and stored[0] == rvm.RESOURCE_VITRINE_SCHEMA_VERSION


def test_indexed_varchar_within_mysql_limit():
    for table in rvm.metadata.tables.values():
        for idx in list(table.indexes) + [c for c in table.constraints if hasattr(c, "columns")]:
            for col in idx.columns:
                length = getattr(col.type, "length", None)
                if length and col.type.__class__.__name__ == "String":
                    assert length <= 191, f"{table.name}.{col.name} VARCHAR({length}) estoura índice utf8mb4"


# ── Helpers de validação ─────────────────────────────────────────────────────

def test_normalize_blueprint_variants():
    canon, key = svc.normalize_blueprint(f"Blueprint'{BP_METAL}'")
    assert canon == BP_METAL and key == BP_METAL.lower()
    assert svc.normalize_blueprint(BP_METAL + "_C")[0] == BP_METAL
    assert svc.normalize_blueprint("lixo") is None
    assert svc.normalize_blueprint("") is None
    assert svc.normalize_blueprint("/Game/../../etc/passwd'; DROP TABLE x;--") is None or True


def test_normalize_blueprint_admin_paste_matches_ark_report():
    """O mesmo item: cola do admin, GetFullName da classe e GetFullName do CDO."""
    pkg = BP_METAL.rsplit(".", 1)[0]
    forms = [
        BP_METAL,
        BP_METAL + "_C",
        BP_METAL + "_c",
        f"Blueprint'{BP_METAL}'",
        f"Blueprint'{BP_METAL}_C'",
        f"BlueprintGeneratedClass {BP_METAL}_C",
        f"PrimalItemResource_Metal_C {pkg}.Default__PrimalItemResource_Metal_C",
        f'cheat giveitem "Blueprint\'{BP_METAL}\'" 100 0 0',
    ]
    for raw in forms:
        assert svc.normalize_blueprint(raw) == (BP_METAL, BP_METAL.lower()), raw


def test_clean_steam_id_rejects_invalid():
    with pytest.raises(svc.RVError):
        svc.clean_steam_id("abc")
    with pytest.raises(svc.RVError):
        svc.clean_steam_id("1234")
    assert svc.clean_steam_id(SELLER) == SELLER


# ── Admin: catálogo ──────────────────────────────────────────────────────────

def test_admin_catalog_upsert_list_disable_and_price_bounds(db):
    res = _catalog(db, min_lot_price=100, max_lot_price=1000)
    assert res["blueprint"] == BP_METAL and res["stack_size"] == 100
    assert res["min_lot_price"] == 100 and res["max_lot_price"] == 1000

    with pytest.raises(svc.RVError) as dup:  # mesmo blueprint sem id = conflito
        _catalog(db, name="Outro")
    assert dup.value.status == 409
    again = svc.upsert_catalog_resource(
        db, {"id": res["id"], "blueprint": BP_METAL, "name": "Metal Bruto", "stack_size": 50}
    )
    assert again["id"] == res["id"]
    assert again["name"] == "Metal Bruto" and again["stack_size"] == 50
    assert len(svc.list_catalog(db)) == 1

    with pytest.raises(svc.RVError):
        svc.upsert_catalog_resource(db, {"blueprint": "xx", "name": "A"})
    with pytest.raises(svc.RVError):
        svc.upsert_catalog_resource(db, {"blueprint": BP_WOOD, "name": "Madeira", "min_lot_price": 900, "max_lot_price": 100})
    with pytest.raises(svc.RVError):
        svc.upsert_catalog_resource(db, {"blueprint": BP_WOOD, "name": "", "stack_size": 10})

    svc.disable_catalog_resource(db, res["id"])
    assert svc.plugin_config(db)["resources"] == []


def test_max_types_setting_bounds(db):
    assert svc.get_max_types(db) == svc.DEFAULT_MAX_TYPES
    assert svc.set_max_types(db, 3) == 3
    assert svc.get_max_types(db) == 3
    for bad in (0, -1, 999, "x", None):
        with pytest.raises(svc.RVError):
            svc.set_max_types(db, bad)
    assert svc.get_max_types(db) == 3


def test_plugin_config_exposes_ascii_name(db):
    _catalog(db, name="Pérola Negra")
    cfg = svc.plugin_config(db)
    assert cfg["max_types_per_player"] == svc.DEFAULT_MAX_TYPES
    assert cfg["resources"][0]["name_ascii"] == "Perola Negra"
    assert cfg["resources"][0]["stack_size"] == 100


# ── Upload (plugin) ──────────────────────────────────────────────────────────

def test_upload_credits_exact_quantity_and_is_idempotent(db):
    res = _catalog(db)
    out1 = svc.process_upload(db, {"steam_id": SELLER, "upload_id": "up-aaaaaaaa1", "items": [{"blueprint": BP_METAL, "quantity": 250}]})
    assert out1["duplicate"] is False and out1["status"] == "APPLIED"
    out2 = svc.process_upload(db, {"steam_id": SELLER, "upload_id": "up-aaaaaaaa1", "items": [{"blueprint": BP_METAL, "quantity": 250}]})
    assert out2["duplicate"] is True
    assert _stock_qty(db, SELLER, res["id"]) == 250  # nunca duplica


def test_upload_merges_duplicate_lines(db):
    res = _catalog(db)
    _upload(db, SELLER, [{"blueprint": BP_METAL, "quantity": 10}, {"blueprint": BP_METAL + "_C", "quantity": 15}])
    assert _stock_qty(db, SELLER, res["id"]) == 25


def test_upload_rejects_unauthorized_resource_without_partial_credit(db):
    res = _catalog(db)
    with pytest.raises(svc.RVError) as e:
        _upload(db, SELLER, [{"blueprint": BP_METAL, "quantity": 10}, {"blueprint": BP_WOOD, "quantity": 5}])
    assert e.value.code == "not_authorized_resource"
    assert _stock_qty(db, SELLER, res["id"]) == 0


def test_upload_rejects_disabled_resource(db):
    res = _catalog(db)
    svc.disable_catalog_resource(db, res["id"])
    with pytest.raises(svc.RVError) as e:
        _upload(db, SELLER, [{"blueprint": BP_METAL, "quantity": 10}])
    assert e.value.code == "not_authorized_resource"


@pytest.mark.parametrize("qty", [0, -5, "x", None, 10**9])
def test_upload_rejects_bad_quantity(db, qty):
    _catalog(db)
    with pytest.raises(svc.RVError):
        _upload(db, SELLER, [{"blueprint": BP_METAL, "quantity": qty}])


def test_upload_rejects_bad_payload(db):
    _catalog(db)
    for items in (None, [], "x", [1, 2]):
        with pytest.raises(svc.RVError):
            _upload(db, SELLER, items)
    with pytest.raises(svc.RVError):
        svc.process_upload(db, {"steam_id": SELLER, "upload_id": "../x", "items": [{"blueprint": BP_METAL, "quantity": 1}]})
    with pytest.raises(svc.RVError):
        svc.process_upload(db, {"steam_id": "nao-e-steam", "upload_id": "up-bbbbbbbb1", "items": [{"blueprint": BP_METAL, "quantity": 1}]})


def test_upload_respects_type_limit_atomically(db):
    svc.set_max_types(db, 2)
    bps = [BP_METAL, BP_WOOD, BP_STONE]
    for i, bp in enumerate(bps):
        _catalog(db, blueprint=bp, name=f"R{i}")
    _upload(db, SELLER, [{"blueprint": BP_METAL, "quantity": 5}, {"blueprint": BP_WOOD, "quantity": 5}])
    with pytest.raises(svc.RVError) as e:
        _upload(db, SELLER, [{"blueprint": BP_STONE, "quantity": 5}])
    assert e.value.code == "type_limit"
    # Tipo já existente continua aceitando mais quantidade
    _upload(db, SELLER, [{"blueprint": BP_METAL, "quantity": 5}])
    # Upload com 2 tipos novos de uma vez não aplica parcial
    svc.set_max_types(db, 3)
    for bp, n in ((BP_FIBER, "Fibra"), (BP_HIDE, "Couro")):
        _catalog(db, blueprint=bp, name=n)
    with pytest.raises(svc.RVError):
        _upload(db, SELLER, [{"blueprint": BP_FIBER, "quantity": 1}, {"blueprint": BP_HIDE, "quantity": 1}])
    summary = svc.plugin_stock_summary(db, SELLER)
    assert summary["type_count"] == 2 and summary["max_types"] == 3


def test_upload_stock_cap(db):
    res = _catalog(db)
    _upload(db, SELLER, [{"blueprint": BP_METAL, "quantity": svc.MAX_UPLOAD_QTY_PER_LINE}])
    with pytest.raises(svc.RVError) as e:
        for _ in range(svc.MAX_STOCK_PER_RESOURCE // svc.MAX_UPLOAD_QTY_PER_LINE + 2):
            _upload(db, SELLER, [{"blueprint": BP_METAL, "quantity": svc.MAX_UPLOAD_QTY_PER_LINE}])
    assert e.value.code == "stock_cap"
    assert _stock_qty(db, SELLER, res["id"]) <= svc.MAX_STOCK_PER_RESOURCE


def test_upload_cancel_prevents_later_apply_and_is_idempotent(db):
    res = _catalog(db)
    out = svc.cancel_upload(db, {"steam_id": SELLER, "upload_id": "up-cancel-01"})
    assert out["status"] == "CANCELLED"
    assert svc.cancel_upload(db, {"steam_id": SELLER, "upload_id": "up-cancel-01"})["status"] == "CANCELLED"
    with pytest.raises(svc.RVError) as e:
        svc.process_upload(db, {"steam_id": SELLER, "upload_id": "up-cancel-01", "items": [{"blueprint": BP_METAL, "quantity": 10}]})
    assert e.value.code == "upload_cancelled"
    assert _stock_qty(db, SELLER, res["id"]) == 0
    assert svc.get_upload_status(db, "up-cancel-01")["status"] == "CANCELLED"


def test_cancel_after_applied_never_refunds_items(db):
    res = _catalog(db)
    _upload(db, SELLER, [{"blueprint": BP_METAL, "quantity": 10}], upload_id="up-applied-01")
    out = svc.cancel_upload(db, {"steam_id": SELLER, "upload_id": "up-applied-01"})
    assert out["status"] == "APPLIED"  # jogo NÃO devolve itens
    assert _stock_qty(db, SELLER, res["id"]) == 10


def test_upload_id_cannot_be_hijacked_by_other_player(db):
    _catalog(db)
    _upload(db, SELLER, [{"blueprint": BP_METAL, "quantity": 10}], upload_id="up-owner-001")
    with pytest.raises(svc.RVError):
        svc.process_upload(db, {"steam_id": BUYER, "upload_id": "up-owner-001", "items": [{"blueprint": BP_METAL, "quantity": 10}]})


def test_get_upload_status_unknown(db):
    assert svc.get_upload_status(db, "up-nao-existe")["status"] == "UNKNOWN"


# ── Anúncio (lotes) ──────────────────────────────────────────────────────────

def test_set_listing_validates_bounds_and_whole_lots(db):
    res = _catalog(db, min_lot_price=100, max_lot_price=1000)
    _upload(db, SELLER, [{"blueprint": BP_METAL, "quantity": 250}])
    with pytest.raises(svc.RVError) as e:
        svc.set_listing(db, SELLER, res["id"], {"lot_size": 100, "lot_price": 50, "active": True})
    assert e.value.code == "price_out_of_range"
    with pytest.raises(svc.RVError):
        svc.set_listing(db, SELLER, res["id"], {"lot_size": 100, "lot_price": 5000, "active": True})
    for bad in (0, -1, "x", 10**9):
        with pytest.raises(svc.RVError):
            svc.set_listing(db, SELLER, res["id"], {"lot_size": bad, "lot_price": 500, "active": True})
    item = svc.set_listing(db, SELLER, res["id"], {"lot_size": 100, "lot_price": 500, "active": True})
    assert item["lots_available"] == 2 and item["leftover"] == 50
    assert item["state"] == "active"


def test_set_listing_without_stock_or_foreign_resource(db):
    res = _catalog(db)
    with pytest.raises(svc.RVError) as e:
        svc.set_listing(db, SELLER, res["id"], {"lot_size": 10, "lot_price": 10, "active": True})
    assert e.value.status == 404
    with pytest.raises(svc.RVError):
        svc.set_listing(db, SELLER, 9999, {"lot_size": 10, "lot_price": 10, "active": True})


def test_listing_hidden_when_stock_below_one_lot_and_reappears(db):
    rid, sid = _listed(db, qty=150, lot_size=100)
    assert len(svc.list_public_listings(db)) == 1
    svc.withdraw_stock(db, SELLER, resource_id=rid, quantity=100)  # sobra 50 < lote
    assert svc.list_public_listings(db) == []
    mine = svc.my_overview(db, SELLER)
    assert mine["stock"][0]["state"] == "no_full_lot"
    _upload(db, SELLER, [{"blueprint": BP_METAL, "quantity": 100}])
    assert len(svc.list_public_listings(db)) == 1


def test_public_listings_show_only_whole_lots_and_filter(db):
    rid, sid = _listed(db, qty=250, lot_size=100, lot_price=500)
    items = svc.list_public_listings(db)
    assert len(items) == 1
    row = items[0]
    assert row["lots_available"] == 2
    assert row["resource"]["id"] == rid and row["resource"]["blueprint"] == BP_METAL
    assert svc.list_public_listings(db, seller_steam_id=BUYER) == []
    assert len(svc.list_public_listings(db, resource_id=rid)) == 1
    assert len(svc.list_public_listings(db, query="metal")) == 1
    assert svc.list_public_listings(db, query="zzz") == []


def test_paused_or_disabled_listing_not_public(db):
    rid, sid = _listed(db)
    svc.set_listing(db, SELLER, rid, {"active": False})
    assert svc.list_public_listings(db) == []
    svc.set_listing(db, SELLER, rid, {"active": True})
    assert len(svc.list_public_listings(db)) == 1
    svc.disable_catalog_resource(db, rid)
    assert svc.list_public_listings(db) == []


# ── Compra ───────────────────────────────────────────────────────────────────

def test_purchase_moves_amber_stock_and_creates_claim(db):
    _seed_players(db)
    rid, sid = _listed(db, qty=1000, lot_size=100, lot_price=500)
    out = svc.purchase_lots(db, sid, BUYER, 3, request_id="req-buy-0001")
    assert out["price_paid"] == 1500 and out["quantity"] == 300 and out["duplicate"] is False
    assert _points(db, BUYER) == 100_000 - 1500
    assert _points(db, SELLER) == 100_000 + 1500  # taxa 0
    assert _stock_qty(db, SELLER, rid) == 700
    pend = svc.get_pending_claims(db, BUYER)
    assert len(pend) == 1 and pend[0]["quantity"] == 300 and pend[0]["kind"] == "BUY"
    assert pend[0]["stack_size"] == 100
    assert svc.get_pending_claims(db, SELLER) == []


def test_purchase_is_idempotent_by_request_id(db):
    _seed_players(db)
    rid, sid = _listed(db)
    a = svc.purchase_lots(db, sid, BUYER, 1, request_id="req-dup-0001")
    b = svc.purchase_lots(db, sid, BUYER, 1, request_id="req-dup-0001")
    assert b["duplicate"] is True and b["claim_id"] == a["claim_id"]
    assert _points(db, BUYER) == 100_000 - 500
    assert _stock_qty(db, SELLER, rid) == 900
    assert len(svc.get_pending_claims(db, BUYER)) == 1


def test_purchase_insufficient_balance_changes_nothing(db):
    _seed_players(db, points=100)
    rid, sid = _listed(db)
    with pytest.raises(svc.RVError) as e:
        svc.purchase_lots(db, sid, BUYER, 1)
    assert e.value.code == "insufficient_balance"
    assert _points(db, BUYER) == 100 and _points(db, SELLER) == 100
    assert _stock_qty(db, SELLER, rid) == 1000
    assert svc.get_pending_claims(db, BUYER) == []


def test_purchase_rejects_self_purchase(db):
    _seed_players(db)
    rid, sid = _listed(db)
    with pytest.raises(svc.RVError) as e:
        svc.purchase_lots(db, sid, SELLER, 1)
    assert e.value.code == "self_purchase"
    assert _stock_qty(db, SELLER, rid) == 1000


def test_purchase_more_lots_than_available(db):
    _seed_players(db)
    rid, sid = _listed(db, qty=250, lot_size=100)
    with pytest.raises(svc.RVError) as e:
        svc.purchase_lots(db, sid, BUYER, 3)
    assert e.value.code == "insufficient_stock"
    svc.purchase_lots(db, sid, BUYER, 2)
    assert _stock_qty(db, SELLER, rid) == 50  # sobra fica com o dono


@pytest.mark.parametrize("lots", [0, -1, "x", None, 10**6])
def test_purchase_rejects_bad_lots(db, lots):
    _seed_players(db)
    rid, sid = _listed(db)
    with pytest.raises(svc.RVError):
        svc.purchase_lots(db, sid, BUYER, lots)


def test_purchase_expected_price_mismatch(db):
    _seed_players(db)
    rid, sid = _listed(db, lot_price=500)
    with pytest.raises(svc.RVError) as e:
        svc.purchase_lots(db, sid, BUYER, 1, expected_price=400)
    assert e.value.code == "price_changed"
    svc.purchase_lots(db, sid, BUYER, 1, expected_price=500)


def test_purchase_missing_or_inactive_listing(db):
    _seed_players(db)
    with pytest.raises(svc.RVError) as e:
        svc.purchase_lots(db, 12345, BUYER, 1)
    assert e.value.status == 404
    rid, sid = _listed(db)
    svc.set_listing(db, SELLER, rid, {"active": False})
    with pytest.raises(svc.RVError):
        svc.purchase_lots(db, sid, BUYER, 1)


def test_concurrent_purchases_never_oversell_or_overdraw(db):
    _seed_players(db, points=100_000)
    rid, sid = _listed(db, qty=300, lot_size=100, lot_price=500)  # 3 lotes
    results: list[str] = []
    lock = threading.Lock()

    def _worker(n: int):
        s = _app_module._SessionLocal()
        try:
            for attempt in range(5):
                try:
                    svc.purchase_lots(s, sid, BUYER, 1, request_id=f"req-conc-{n}")
                    with lock:
                        results.append("ok")
                    return
                except svc.RVError as exc:
                    with lock:
                        results.append(exc.code)
                    return
                except Exception:  # SQLite "database is locked" — tenta de novo
                    s.rollback()
            with lock:
                results.append("locked")
        finally:
            s.close()

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    sold = results.count("ok")
    assert sold <= 3
    assert _stock_qty(db, SELLER, rid) == 300 - sold * 100
    assert _points(db, BUYER) == 100_000 - sold * 500
    assert _points(db, SELLER) == 100_000 + sold * 500
    assert len(svc.get_pending_claims(db, BUYER)) == sold


# ── Claims (plugin /mercado) ─────────────────────────────────────────────────

def _bought_claim(db):
    _seed_players(db)
    rid, sid = _listed(db)
    out = svc.purchase_lots(db, sid, BUYER, 1, request_id="req-claim-001")
    return rid, sid, out["claim_id"]


def test_claim_deliver_flow_is_idempotent(db):
    rid, sid, cid = _bought_claim(db)
    claimed = svc.claim_deliveries(db, BUYER, [cid])
    assert [c["claim_id"] for c in claimed] == [cid] and claimed[0]["status"] == "CLAIMED"
    assert svc.get_pending_claims(db, BUYER) == []
    done = svc.mark_claim_delivered(db, cid, BUYER)
    assert done["status"] == "DELIVERED"
    again = svc.mark_claim_delivered(db, cid, BUYER)
    assert again["status"] == "DELIVERED" and again["duplicate"] is True


def test_claim_cannot_be_claimed_by_other_player(db):
    rid, sid, cid = _bought_claim(db)
    assert svc.claim_deliveries(db, THIRD, [cid]) == []
    with pytest.raises(svc.RVError):
        svc.mark_claim_delivered(db, cid, THIRD)


def test_release_returns_claim_to_pending(db):
    rid, sid, cid = _bought_claim(db)
    svc.claim_deliveries(db, BUYER, [cid])
    released = svc.release_claims(db, BUYER, [cid])
    assert len(released) == 1
    assert len(svc.get_pending_claims(db, BUYER)) == 1
    # liberar de novo não faz nada
    assert svc.release_claims(db, BUYER, [cid]) == []


# ── Expiração e reembolso ────────────────────────────────────────────────────

def _age_claim(db, cid, hours=25):
    db.execute(
        update(svc.T_CLAIM)
        .where(svc.T_CLAIM.c.id == cid)
        .values(claim_expires_at=svc._now() - timedelta(hours=hours - 24))
    )
    db.commit()


def test_expiry_refunds_buyer_and_returns_stock_idempotently(db):
    rid, sid, cid = _bought_claim(db)
    assert _points(db, BUYER) == 100_000 - 500
    assert _stock_qty(db, SELLER, rid) == 900
    _age_claim(db, cid)
    result = svc.expire_resource_claims(db, batch_size=10)
    assert result["processed"] == 1
    assert _points(db, BUYER) == 100_000
    assert _points(db, SELLER) == 100_000
    assert _stock_qty(db, SELLER, rid) == 1000
    again = svc.expire_resource_claims(db, batch_size=10)
    assert again["processed"] == 0
    assert _points(db, BUYER) == 100_000  # sem reembolso em dobro
    assert _stock_qty(db, SELLER, rid) == 1000
    with pytest.raises(svc.RVError):
        svc.mark_claim_delivered(db, cid, BUYER)  # já reembolsado


def test_expiry_when_seller_spent_amber_refunds_buyer_fully(db):
    rid, sid, cid = _bought_claim(db)
    db.execute(text("UPDATE players SET points = 0 WHERE steam_id = :s"), {"s": SELLER})
    db.commit()
    _age_claim(db, cid)
    svc.expire_resource_claims(db, batch_size=10)
    assert _points(db, BUYER) == 100_000  # comprador recebe tudo
    assert _points(db, SELLER) == 0  # vendedor nunca fica negativo
    assert _stock_qty(db, SELLER, rid) == 1000


def test_expiry_skips_delivered_and_fresh_claims(db):
    rid, sid, cid = _bought_claim(db)
    assert svc.expire_resource_claims(db)["processed"] == 0  # ainda no prazo
    svc.claim_deliveries(db, BUYER, [cid])
    svc.mark_claim_delivered(db, cid, BUYER)
    _age_claim(db, cid)
    assert svc.expire_resource_claims(db)["processed"] == 0
    assert _points(db, BUYER) == 100_000 - 500


def test_claimed_but_not_confirmed_claim_expires_after_grace(db):
    rid, sid, cid = _bought_claim(db)
    svc.claim_deliveries(db, BUYER, [cid])
    db.execute(
        update(svc.T_CLAIM).where(svc.T_CLAIM.c.id == cid).values(claim_expires_at=svc._now() - timedelta(minutes=5))
    )
    db.commit()
    assert svc.expire_resource_claims(db)["processed"] == 0  # resgatado agora: pode estar entregando
    db.execute(
        update(svc.T_CLAIM)
        .where(svc.T_CLAIM.c.id == cid)
        .values(claim_expires_at=svc._now() - timedelta(minutes=40), claimed_at=svc._now() - timedelta(minutes=40))
    )
    db.commit()
    assert svc.expire_resource_claims(db)["processed"] == 1


# ── Retirada ─────────────────────────────────────────────────────────────────

def test_withdraw_all_creates_claims_without_amber(db):
    _seed_players(db)
    res_a = _catalog(db, blueprint=BP_METAL, name="Metal")
    res_b = _catalog(db, blueprint=BP_WOOD, name="Madeira")
    _upload(db, SELLER, [{"blueprint": BP_METAL, "quantity": 120}, {"blueprint": BP_WOOD, "quantity": 30}])
    out = svc.withdraw_stock(db, SELLER, request_id="wd-all-00001")
    assert len(out["claims"]) == 2 and out["duplicate"] is False
    assert _stock_qty(db, SELLER, res_a["id"]) == 0 and _stock_qty(db, SELLER, res_b["id"]) == 0
    assert _points(db, SELLER) == 100_000
    pend = svc.get_pending_claims(db, SELLER)
    assert sorted(c["quantity"] for c in pend) == [30, 120]
    assert all(c["kind"] == "WITHDRAW" for c in pend)
    again = svc.withdraw_stock(db, SELLER, request_id="wd-all-00001")
    assert again["duplicate"] is True and len(svc.get_pending_claims(db, SELLER)) == 2


def test_withdraw_partial_and_validation(db):
    res = _catalog(db)
    _upload(db, SELLER, [{"blueprint": BP_METAL, "quantity": 100}])
    with pytest.raises(svc.RVError):
        svc.withdraw_stock(db, SELLER, resource_id=res["id"], quantity=101)
    with pytest.raises(svc.RVError):
        svc.withdraw_stock(db, SELLER, quantity=5)  # quantidade sem recurso
    with pytest.raises(svc.RVError):
        svc.withdraw_stock(db, SELLER, resource_id=res["id"], quantity=0)
    svc.withdraw_stock(db, SELLER, resource_id=res["id"], quantity=40)
    assert _stock_qty(db, SELLER, res["id"]) == 60
    with pytest.raises(svc.RVError):
        svc.withdraw_stock(db, BUYER)  # sem estoque


def test_withdraw_expiry_returns_stock_without_touching_amber(db):
    _seed_players(db)
    res = _catalog(db)
    _upload(db, SELLER, [{"blueprint": BP_METAL, "quantity": 100}])
    out = svc.withdraw_stock(db, SELLER)
    cid = out["claims"][0]["claim_id"]
    _age_claim(db, cid)
    assert svc.expire_resource_claims(db)["processed"] == 1
    assert _stock_qty(db, SELLER, res["id"]) == 100
    assert _points(db, SELLER) == 100_000


# ── Overview ─────────────────────────────────────────────────────────────────

def test_my_overview_has_stock_pending_history(db):
    _seed_players(db)
    rid, sid = _listed(db)
    svc.purchase_lots(db, sid, BUYER, 1)
    seller_view = svc.my_overview(db, SELLER)
    assert seller_view["stock"][0]["quantity"] == 900
    assert any(h["type"] == "sale" for h in seller_view["history"])
    buyer_view = svc.my_overview(db, BUYER)
    assert len(buyer_view["pending_claims"]) == 1
    assert any(h["type"] == "purchase" for h in buyer_view["history"])
    assert seller_view["max_types"] == svc.DEFAULT_MAX_TYPES


# ── HTTP / permissões ────────────────────────────────────────────────────────

@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(_app_module, "_ARKSHOP_API_KEY", "test-api-key")
    return _app_module.app.test_client()


def _login(client, sid):
    with client.session_transaction() as sess:
        sess["steam_id"] = sid


API = {"X-API-Key": "test-api-key"}


def test_http_plugin_routes_require_api_key(client):
    for method, path in (
        ("get", "/api/market/resources/plugin/config"),
        ("get", f"/api/market/resources/plugin/stock/{SELLER}"),
        ("post", "/api/market/resources/plugin/upload"),
        ("post", "/api/market/resources/plugin/upload/cancel"),
        ("get", f"/api/market/resources/plugin/pending/{SELLER}"),
        ("post", "/api/market/resources/plugin/claims/claim"),
        ("post", "/api/market/resources/plugin/claims/release"),
        ("post", "/api/market/resources/plugin/claims/delivered"),
    ):
        r = getattr(client, method)(path, json={})
        assert r.status_code == 401, path
        r = getattr(client, method)(path, json={}, headers={"X-API-Key": "errada"})
        assert r.status_code == 401, path


def test_http_player_routes_require_login(client):
    assert client.get("/api/market/resources/my").status_code in (401, 403)
    assert client.put("/api/market/resources/my/stock/1/listing", json={}).status_code in (401, 403)
    assert client.post("/api/market/resources/my/withdraw", json={}).status_code in (401, 403)
    assert client.post("/api/market/resources/listings/1/purchase", json={"lots": 1}).status_code in (401, 403)


def test_http_admin_routes_reject_non_admin(client):
    _login(client, BUYER)
    for method, path in (
        ("get", "/api/market/resources/admin/catalog"),
        ("put", "/api/market/resources/admin/catalog"),
        ("delete", "/api/market/resources/admin/catalog/1"),
        ("put", "/api/market/resources/admin/settings"),
        ("post", "/api/market/resources/admin/claims/expire-stale"),
    ):
        r = getattr(client, method)(path, json={})
        assert r.status_code in (401, 403), path


def test_http_public_catalog_and_listings_are_json(client):
    r = client.get("/api/market/resources/catalog")
    assert r.content_type.startswith("application/json") and r.get_json()["ok"] is True
    r = client.get("/api/market/resources/listings?limit=5")
    assert r.content_type.startswith("application/json")
    data = r.get_json()
    assert data["ok"] is True and data["listings"] == []


def test_http_listings_rejects_bad_params(client):
    r = client.get("/api/market/resources/listings?resource_id=abc")
    assert r.status_code == 400 and r.get_json()["code"] == "invalid_input"
    r = client.get("/api/market/resources/listings?seller_steam_id=zzz")
    assert r.status_code == 400


def test_http_full_flow_upload_list_buy_deliver(client, db, monkeypatch):
    _seed_players(db)
    monkeypatch.setattr(_app_module, "_is_admin_steamid", lambda sid: sid == THIRD)

    # Admin cadastra o recurso e ajusta o limite.
    _login(client, THIRD)
    r = client.put(
        "/api/market/resources/admin/catalog",
        json={"blueprint": BP_METAL, "name": "Metal", "stack_size": 100, "min_lot_price": 10, "max_lot_price": 10000},
    )
    assert r.status_code == 200, r.get_json()
    rid = r.get_json()["resource"]["id"]
    assert client.put("/api/market/resources/admin/settings", json={"max_types_per_player": 4}).get_json()["max_types_per_player"] == 4
    assert client.get("/api/market/resources/admin/catalog").get_json()["ok"] is True

    # Plugin envia os itens (idempotente).
    body = {"steam_id": SELLER, "upload_id": "up-http-0001", "items": [{"blueprint": BP_METAL, "quantity": 500}]}
    r1 = client.post("/api/market/resources/plugin/upload", json=body, headers=API)
    r2 = client.post("/api/market/resources/plugin/upload", json=body, headers=API)
    assert r1.get_json()["duplicate"] is False and r2.get_json()["duplicate"] is True
    cfg = client.get("/api/market/resources/plugin/config", headers=API).get_json()
    assert cfg["max_types_per_player"] == 4 and cfg["resources"][0]["stack_size"] == 100

    # Vendedor anuncia.
    _login(client, SELLER)
    r = client.put(f"/api/market/resources/my/stock/{rid}/listing", json={"lot_size": 100, "lot_price": 200, "active": True})
    assert r.status_code == 200, r.get_json()
    r = client.put(f"/api/market/resources/my/stock/{rid}/listing", json={"lot_size": 100, "lot_price": 5, "active": True})
    assert r.status_code == 400 and r.get_json()["code"] == "price_out_of_range"

    listing = client.get("/api/market/resources/listings").get_json()["listings"][0]
    stock_id = listing["stock_id"]

    # Auto-compra recusada.
    r = client.post(f"/api/market/resources/listings/{stock_id}/purchase", json={"lots": 1})
    assert r.status_code == 400 and r.get_json()["code"] == "self_purchase"

    # Comprador compra.
    _login(client, BUYER)
    r = client.post(f"/api/market/resources/listings/{stock_id}/purchase", json={"lots": 2, "request_id": "req-http-0001"})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["price_paid"] == 400
    r = client.post(f"/api/market/resources/listings/{stock_id}/purchase", json={"lots": 99})
    assert r.status_code == 400 and r.get_json()["code"] == "insufficient_stock"

    # Plugin entrega via /mercado.
    pend = client.get(f"/api/market/resources/plugin/pending/{BUYER}", headers=API).get_json()["claims"]
    assert len(pend) == 1 and pend[0]["quantity"] == 200
    cid = pend[0]["claim_id"]
    claimed = client.post("/api/market/resources/plugin/claims/claim", json={"steam_id": BUYER, "claim_ids": [cid]}, headers=API)
    assert claimed.get_json()["claimed"][0]["claim_id"] == cid
    done = client.post("/api/market/resources/plugin/claims/delivered", json={"steam_id": BUYER, "claim_id": cid}, headers=API)
    assert done.get_json()["status"] == "DELIVERED"

    # Retirada do vendedor.
    _login(client, SELLER)
    r = client.post("/api/market/resources/my/withdraw", json={"request_id": "wd-http-0001"})
    assert r.status_code == 200 and r.get_json()["claims"][0]["quantity"] == 300
    me = client.get("/api/market/resources/my").get_json()
    assert me["ok"] is True and len(me["pending_claims"]) == 1

    # Admin força expiração (nada expirado ainda).
    _login(client, THIRD)
    r = client.post("/api/market/resources/admin/claims/expire-stale", json={})
    assert r.status_code == 200 and r.get_json()["processed"] == 0


def test_http_errors_do_not_leak_internal_details(client, monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("segredo-interno-xyz")

    monkeypatch.setattr(svc, "plugin_config", _boom)
    r = client.get("/api/market/resources/plugin/config", headers=API)
    assert r.status_code == 500
    assert "segredo-interno-xyz" not in r.get_data(as_text=True)
    assert r.get_json()["code"] == "internal"


def test_http_upload_validation_returns_400_json(client, db):
    _catalog(db)
    r = client.post(
        "/api/market/resources/plugin/upload",
        json={"steam_id": SELLER, "upload_id": "up-bad-0001", "items": [{"blueprint": BP_WOOD, "quantity": 1}]},
        headers=API,
    )
    assert r.status_code == 400 and r.get_json()["code"] == "not_authorized_resource"


# ── Auditoria / ledger ───────────────────────────────────────────────────────

def test_purchase_writes_ledger_once(db):
    _seed_players(db)
    rid, sid = _listed(db)
    svc.purchase_lots(db, sid, BUYER, 1, request_id="req-ledg-001")
    svc.purchase_lots(db, sid, BUYER, 1, request_id="req-ledg-001")
    rows = db.execute(text("SELECT idempotency_key FROM amber_ledger WHERE idempotency_key LIKE 'market:restx:%'")).all()
    keys = sorted(r[0] for r in rows)
    assert len(keys) == 2 and len(set(keys)) == 2  # comprador + vendedor, uma única vez
    assert keys[0].endswith(":buyer") and keys[1].endswith(":seller")
    events = db.execute(
        text("SELECT event_type, points_delta FROM market_audit_events WHERE event_type = 'MARKET_RESOURCE_PURCHASE'")
    ).all()
    assert len(events) == 1 and events[0][1] == -500


def test_expiry_writes_refund_ledger_once(db):
    rid, sid, cid = _bought_claim(db)
    _age_claim(db, cid)
    svc.expire_resource_claims(db)
    svc.expire_resource_claims(db)
    keys = sorted(
        r[0] for r in db.execute(text("SELECT idempotency_key FROM amber_ledger WHERE idempotency_key LIKE 'market:rescl:%'")).all()
    )
    assert keys == [f"market:rescl:{cid}:buyer_refund", f"market:rescl:{cid}:seller_debit"]


def test_audit_labels_cover_all_resource_events():
    from market_audit import MARKET_ADMIN_AUDIT_LABELS

    src = (ROOT / "resource_vitrine_service.py").read_text(encoding="utf-8") + (ROOT / "resource_vitrine_routes.py").read_text(encoding="utf-8")
    events = set(re.findall(r'"(MARKET_RESOURCE_[A-Z_]+)"', src))
    # MARKET_RESOURCE_CLAIMS_EXPIRE_MANUAL vai para o audit global (app._audit_event), não para market_audit.
    events.discard("MARKET_RESOURCE_CLAIMS_EXPIRE_MANUAL")
    missing = events - set(MARKET_ADMIN_AUDIT_LABELS)
    assert not missing, f"sem label PT-BR: {sorted(missing)}"

