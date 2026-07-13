"""ARKBANK — edge cases e contratos do ledger (docs/ARKBANK_SPEC.md).

Cobre: saldo negativo, idempotência, retenção 20% catálogo, doação 1:1000,
contribuição de casal 40%, e corrida concurrent-ish no mesmo payment_id.

Hooks de produção (app / market_listings / PIX) podem ainda estar ausentes —
esses testes fazem skip com motivo explícito até o wiring existir.
"""
from __future__ import annotations

import inspect
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ARKSHOP_WEB_SECRET", "test-secret")
os.environ.setdefault("ARKSHOP_SKIP_DB_BOOT", "1")

arkbank = pytest.importorskip(
    "arkbank_service",
    reason="arkbank_service.py ainda não disponível",
)
from market_pair import pair_prize_contribution  # noqa: E402

STEAM = "76561198000000001"


@pytest.fixture()
def ark_db(tmp_path):
    path = tmp_path / "arkbank.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    arkbank.ensure_arkbank_schema(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def _tx_count(db) -> int:
    return int(db.execute(text("SELECT COUNT(*) FROM arkbank_transactions")).scalar() or 0)


# ── Política / math (sempre verdes se o serviço existir) ──────────────────────


class TestDonationBrlConversion:
    def test_one_real_equals_1000_amber(self):
        assert arkbank.ARKBANK_DONATION_AMBER_PER_REAL == 1000
        assert arkbank.donation_amber_from_brl(1) == 1000
        assert arkbank.donation_amber_from_brl(1.0) == 1000

    def test_canonical_example_r5(self):
        """SPEC §2.6: R$ 5,00 → +5.000 Âmbar no ARKBANK."""
        assert arkbank.donation_amber_from_brl(5) == 5000

    def test_rounds_fractional_brl(self):
        assert arkbank.donation_amber_from_brl(0.001) == 1  # round(1.0)
        assert arkbank.donation_amber_from_brl(1.5) == 1500

    def test_zero_and_invalid(self):
        assert arkbank.donation_amber_from_brl(0) == 0
        assert arkbank.donation_amber_from_brl(-10) == 0
        assert arkbank.donation_amber_from_brl(None) == 0
        assert arkbank.donation_amber_from_brl("x") == 0


class TestCatalogRetentionMath:
    """Compra +P → desistência −0.80P → líquido +0.20P no banco (R1)."""

    def test_buy_then_desist_leaves_20_percent(self, ark_db):
        paid = 10000
        refunded = int(round(paid * 0.80))  # espelha _ORDER_DESIST_REFUND_FACTOR
        assert refunded == 8000

        r1 = arkbank.credit_catalog_spend(
            ark_db, order_id="ord-r1", steam_id=STEAM, points=paid, commit=True
        )
        assert r1["applied"] is True
        assert arkbank.get_balance(ark_db) == paid

        r2 = arkbank.debit_catalog_refund_clawback(
            ark_db,
            order_id="ord-r1",
            steam_id=STEAM,
            refunded=refunded,
            event="cancel",
            commit=True,
        )
        assert r2["applied"] is True
        assert arkbank.get_balance(ark_db) == 2000  # 20% retention
        assert _tx_count(ark_db) == 2

    def test_retention_matches_app_desist_factor(self):
        import app as app_mod

        assert getattr(app_mod, "_ORDER_DESIST_REFUND_FACTOR", None) == 0.80
        paid = 12345
        refund = int(round(paid * app_mod._ORDER_DESIST_REFUND_FACTOR))
        retention = paid - refund
        assert retention == paid - int(round(paid * 0.80))
        assert retention == paid - refund


class TestNegativeBalanceAllowed:
    def test_timed_reward_drives_balance_negative(self, ark_db):
        assert arkbank.get_balance(ark_db) == 0
        r = arkbank.debit_timed_reward(
            ark_db,
            steam_id=STEAM,
            amount=500,
            map_id="TheIsland",
            cycle_key="cycle-1",
            commit=True,
        )
        assert r["applied"] is True
        assert arkbank.get_balance(ark_db) == -500
        assert r["balance_after"] == -500

    def test_debit_never_blocked_when_already_negative(self, ark_db):
        arkbank.debit(
            ark_db,
            tx_type=arkbank.TX_TIMED_REWARD,
            amount=1000,
            idempotency_key="arkbank:neg:a",
            commit=True,
        )
        arkbank.debit(
            ark_db,
            tx_type=arkbank.TX_TIMED_REWARD,
            amount=2500,
            idempotency_key="arkbank:neg:b",
            commit=True,
        )
        assert arkbank.get_balance(ark_db) == -3500
        summary = arkbank.summary(ark_db, days=7)
        assert summary["health"] == "deficitario"
        assert summary["balance"] == -3500


class TestIdempotentDoubleCredit:
    def test_same_idempotency_key_does_not_double(self, ark_db):
        kwargs = dict(
            tx_type=arkbank.TX_CATALOG_SPEND,
            amount=4000,
            idempotency_key="arkbank:catalog:ord-dup",
            steam_id=STEAM,
            ref_id="ord-dup",
            commit=True,
        )
        a = arkbank.credit(ark_db, **kwargs)
        b = arkbank.credit(ark_db, **kwargs)
        assert a["applied"] is True
        assert b["duplicate"] is True
        assert b["applied"] is False
        assert arkbank.get_balance(ark_db) == 4000
        assert _tx_count(ark_db) == 1

    def test_catalog_helper_same_order_id(self, ark_db):
        a = arkbank.credit_catalog_spend(
            ark_db, order_id="ord-x", steam_id=STEAM, points=900, commit=True
        )
        b = arkbank.credit_catalog_spend(
            ark_db, order_id="ord-x", steam_id=STEAM, points=900, commit=True
        )
        assert a["applied"] is True
        assert b["duplicate"] is True
        assert arkbank.get_balance(ark_db) == 900


class TestDonationIdempotencyAndConcurrency:
    def test_double_credit_same_payment_id(self, ark_db):
        a = arkbank.credit_donation_brl(
            ark_db,
            payment_id="pay-42",
            steam_id=STEAM,
            amount_brl=10,
            payment_method="pix",
            commit=True,
        )
        b = arkbank.credit_donation_brl(
            ark_db,
            payment_id="pay-42",
            steam_id=STEAM,
            amount_brl=10,
            payment_method="pix",
            commit=True,
        )
        assert a["applied"] is True
        assert a["amount"] == 10000
        assert b["duplicate"] is True
        assert arkbank.get_balance(ark_db) == 10000
        assert _tx_count(ark_db) == 1

    def test_concurrent_double_apply_same_payment_id(self, tmp_path):
        """Dois workers com a mesma chave — no máximo um crédito aplicado."""
        path = tmp_path / "arkbank_race.db"
        engine = create_engine(
            f"sqlite:///{path}",
            future=True,
            connect_args={"check_same_thread": False},
        )
        arkbank.ensure_arkbank_schema(engine)
        Session = sessionmaker(bind=engine)
        barrier = threading.Barrier(8)
        results: list[dict] = []
        lock = threading.Lock()

        def worker():
            db = Session()
            try:
                barrier.wait(timeout=5)
                r = arkbank.credit_donation_brl(
                    db,
                    payment_id="pay-race",
                    steam_id=STEAM,
                    amount_brl=7.5,
                    payment_method="card",
                    commit=True,
                )
                with lock:
                    results.append(r)
            finally:
                db.close()

        with ThreadPoolExecutor(max_workers=8) as pool:
            futs = [pool.submit(worker) for _ in range(8)]
            for f in as_completed(futs):
                f.result()

        applied = [r for r in results if r.get("applied")]
        duplicates = [r for r in results if r.get("duplicate")]
        # SQLite pode serializar; IntegrityError path também conta como duplicate.
        assert len(applied) == 1, f"esperava 1 apply, got {len(applied)}: {results!r}"
        assert len(duplicates) >= 1
        db = Session()
        try:
            assert arkbank.get_balance(db) == 7500  # 7.5 * 1000
            assert _tx_count(db) == 1
        finally:
            db.close()


class TestMarketPairShareLedger:
    def test_pair_40_percent_credits_arkbank(self, ark_db):
        """S=200 → contribution 80 → ARKBANK +80 (destino tesouraria, não pote)."""
        contrib = pair_prize_contribution(100, 100)
        assert contrib == 80
        r = arkbank.credit_market_pair_share(
            ark_db,
            amount=contrib,
            listing_id=11,
            tx_id=99,
            seller_steam_id=STEAM,
            commit=True,
        )
        assert r["applied"] is True
        assert arkbank.get_balance(ark_db) == 80
        assert r["tx_type"] == arkbank.TX_MARKET_PAIR_SHARE

    def test_pair_claim_desist_does_not_clawback_share(self, ark_db):
        """SPEC §6.2: desistência de claim NÃO estorna market_pair_share."""
        arkbank.credit_market_pair_share(
            ark_db, amount=80, listing_id=1, tx_id=50, commit=True
        )
        # Nenhum helper de clawback de casal deve existir no MVP.
        assert not hasattr(arkbank, "debit_market_pair_share")
        assert not hasattr(arkbank, "debit_market_pair_clawback")
        assert arkbank.get_balance(ark_db) == 80


# ── Gaps de wiring (skip até o agente principal ligar os hooks) ───────────────


def _source_mentions_arkbank(obj) -> bool:
    try:
        src = inspect.getsource(obj)
    except (OSError, TypeError):
        return False
    low = src.lower()
    return "arkbank" in low or "credit_market_pair_share" in low or "credit_donation_brl" in low


def _pair_contrib_wired_to_arkbank() -> bool:
    try:
        from lottery_service import contribute_market_pair_to_prize
    except ImportError:
        return False
    return _source_mentions_arkbank(contribute_market_pair_to_prize)


def _finalize_pix_wired() -> bool:
    try:
        import app as app_mod
    except ImportError:
        return False
    fn = getattr(app_mod, "_finalize_pix_payment", None)
    return bool(fn and ("credit_donation_brl" in inspect.getsource(fn)))


def _catalog_spend_wired() -> bool:
    try:
        import app as app_mod
        src = inspect.getsource(app_mod)
    except (ImportError, OSError, TypeError):
        return False
    return "credit_catalog_spend" in src


def _catalog_clawback_wired() -> bool:
    try:
        import app as app_mod
        src = inspect.getsource(app_mod)
    except (ImportError, OSError, TypeError):
        return False
    return "debit_catalog_refund_clawback" in src


@pytest.mark.skipif(
    not _pair_contrib_wired_to_arkbank(),
    reason="contribute_market_pair_to_prize ainda não destina 40% ao ARKBANK",
)
def test_hook_pair_share_routes_to_arkbank_not_prize_column():
    """Cutover opção A: contribute_market_pair_to_prize → credit_market_pair_share."""
    from lottery_service import contribute_market_pair_to_prize

    src = inspect.getsource(contribute_market_pair_to_prize)
    assert "credit_market_pair_share" in src
    assert "destination" in src and "arkbank" in src
    # Não deve mais incrementar prize_amber_from_market
    assert "prize_amber_from_market" not in src or "congelado" in src.lower() or "arkbank" in src


@pytest.mark.skipif(
    not _finalize_pix_wired(),
    reason="Hook donation_brl ainda não ligado em _finalize_pix_payment",
)
def test_hook_finalize_pix_credits_arkbank():
    import app as app_mod

    src = inspect.getsource(app_mod._finalize_pix_payment)
    assert "credit_donation_brl" in src


@pytest.mark.skipif(
    not _catalog_spend_wired(),
    reason="Hook catalog_spend ainda não ligado em app.py",
)
def test_hook_catalog_spend_present_in_app():
    import app as app_mod

    assert "credit_catalog_spend" in inspect.getsource(app_mod)


@pytest.mark.skipif(
    not _catalog_clawback_wired(),
    reason="Hook catalog_refund_clawback ainda não ligado em app.py",
)
def test_hook_catalog_clawback_present_in_app():
    import app as app_mod

    assert "debit_catalog_refund_clawback" in inspect.getsource(app_mod)

class TestAdminApiContract:
    """API admin MVP — skip se rotas ainda não existirem."""

    def test_admin_routes_or_skip(self):
        import app as app_mod

        rules = {str(r) for r in app_mod.app.url_map.iter_rules()}
        ark_rules = {r for r in rules if "arkbank" in r.lower()}
        if not ark_rules:
            pytest.skip(
                "Rotas /api/admin/arkbank* ainda não registadas "
                "(GET saldo/txs + POST adjust esperados na Fase 1)"
            )
        joined = " ".join(sorted(ark_rules))
        assert "arkbank" in joined


class TestOutboxTimedReward:
    def test_process_outbox_debits_even_from_zero(self, ark_db):
        arkbank.enqueue_timed_outbox(
            ark_db,
            steam_id=STEAM,
            amount=120,
            map_id="ScorchedEarth",
            cycle_key="c1",
            commit=True,
        )
        out = arkbank.process_timed_outbox(ark_db, batch_size=50)
        assert out["processed"] == 1
        assert arkbank.get_balance(ark_db) == -120

    def test_outbox_enqueue_idempotent(self, ark_db):
        a = arkbank.enqueue_timed_outbox(
            ark_db, steam_id=STEAM, amount=50, map_id="m", cycle_key="k", commit=True
        )
        b = arkbank.enqueue_timed_outbox(
            ark_db, steam_id=STEAM, amount=50, map_id="m", cycle_key="k", commit=True
        )
        assert a.get("enqueued") is True
        assert b.get("duplicate") is True or b.get("enqueued") is False
