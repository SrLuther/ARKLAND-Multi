"""Guards de I/O externo (Steam/RCON/MP/Discord/câmbio) fora dos hot paths HTTP.

Auditoria pós-1.10.52: nenhum request de jogador pode esperar RCON de mapas
offline, HTTP do Mercado Pago sem throttle, refresh síncrono de câmbio ou
Discord de tickets inline.
"""
from __future__ import annotations

import threading
import time

import pytest

import app as _app_module
import exchange_rates as _fx
import rcon_bridge as _bridge

USER_STEAM = "76561198000000002"


# ── RCON fan-out de licenças ──────────────────────────────────────────────────

def test_sync_license_permissions_rcon_async_does_not_call_rcon_inline(monkeypatch):
    """rcon_async=True: MySQL síncrono, fan-out RCON delegado ao background."""
    background_calls: list[tuple[str, str]] = []
    inline_calls: list[str] = []

    monkeypatch.setattr(
        _app_module,
        "_sync_player_entitlements_to_permission_db",
        lambda sid, ents: [{"server_id": "mysql", "label": "ark_permission (MySQL)", "ok": True}],
    )
    monkeypatch.setattr(
        _app_module,
        "_get_player_entitlements",
        lambda sid: [{"group": "Alfa", "expires_at": "2099-01-01T00:00:00+00:00"}],
    )
    monkeypatch.setattr(
        _app_module,
        "_rcon_permission_fanout_background",
        lambda cmd, context="": background_calls.append((cmd, context)),
    )
    monkeypatch.setattr(
        _app_module,
        "_rcon_permission_fanout",
        lambda cmd, **k: inline_calls.append(cmd) or [],
    )

    results = _app_module._sync_license_permissions_all_servers(
        USER_STEAM, "Alfa", grant=True, days=30, rcon_async=True,
    )

    assert inline_calls == []
    assert len(background_calls) == 1
    assert background_calls[0][0].startswith("Permissions.AddTimed")
    queued = [r for r in results if r.get("queued")]
    assert queued and queued[0]["ok"] is True


def test_sync_license_permissions_sync_uses_parallel_fanout(monkeypatch):
    """Sem rcon_async: fan-out inline (paralelo) — admin vê resultado por mapa."""
    fanout_cmds: list[str] = []

    monkeypatch.setattr(
        _app_module,
        "_get_player_entitlements",
        lambda sid: [],
    )
    monkeypatch.setattr(
        "permission_db_sync.grant_group_in_permission_db",
        lambda url, sid, grp, days=0: {"ok": True},
    )
    monkeypatch.setattr(
        _app_module,
        "_rcon_permission_fanout",
        lambda cmd, **k: fanout_cmds.append(cmd)
        or [{"server_id": "map1", "label": "Mapa 1", "ok": True}],
    )

    results = _app_module._sync_license_permissions_all_servers(
        USER_STEAM, "Alfa", grant=True, days=30,
    )
    assert fanout_cmds and fanout_cmds[0].startswith("Permissions.AddTimed")
    assert any(r.get("server_id") == "map1" for r in results)


def test_rcon_permission_fanout_runs_servers_in_parallel(monkeypatch):
    """6 mapas lentos (0.2s cada) devem completar em ~1×, não 6× (sequencial)."""
    servers = [
        {"server_id": f"map{i}", "label": f"Mapa {i}", "rcon_host": "127.0.0.1",
         "rcon_port": 27020 + i, "rcon_password": "pw"}
        for i in range(6)
    ]
    monkeypatch.setattr(_app_module, "_load_settings", lambda: {})
    monkeypatch.setattr(
        _app_module,
        "_resolve_rcon_target",
        lambda sid, settings: ("127.0.0.1", 27020, "pw", str(sid)),
    )

    def slow_rcon(host, port, password, cmd, **k):
        time.sleep(0.2)
        return "ok"

    monkeypatch.setattr(_app_module, "_rcon_command", slow_rcon)
    t0 = time.perf_counter()
    results = _app_module._rcon_permission_fanout(
        "Permissions.Add 1 Alfa", settings={}, servers=servers,
    )
    elapsed = time.perf_counter() - t0
    assert len(results) == 6
    assert all(r["ok"] for r in results)
    assert elapsed < 0.8, f"fan-out não paralelo: {elapsed:.2f}s"


# ── rcon_bridge: deadline mata retries zombie ────────────────────────────────

def test_run_rcon_sync_respects_deadline(monkeypatch):
    """Deadline expirado corta retries — task órfã não segura worker do pool."""
    attempts: list[int] = []

    class _FailClient:
        def __init__(self, *a, **k):
            pass

        def connect(self):
            attempts.append(1)
            raise _bridge.RconError("connection refused")

        def disconnect(self):
            pass

    monkeypatch.setattr(_bridge, "RconClient", _FailClient)
    t0 = time.perf_counter()
    with pytest.raises(RuntimeError):
        _bridge._run_rcon_sync(
            "127.0.0.1", 27020, "pw", "Shop.Reload",
            connect_retries=5,
            retry_delay=2.0,
            deadline=time.monotonic() - 0.01,  # caller já desistiu (future timeout)
        )
    elapsed = time.perf_counter() - t0
    # Sem deadline seriam sleeps 2+4+6+8=20s; com deadline expirado aborta após a 1ª.
    assert elapsed < 2.0, f"retries ignoraram deadline: {elapsed:.2f}s"
    assert len(attempts) == 1


# ── Mercado Pago: throttle + timeout curto no poll de status ────────────────

def test_pix_mp_poll_throttle_allows_first_then_blocks(monkeypatch):
    _app_module._PIX_MP_POLL_LAST.clear()
    assert _app_module._pix_mp_poll_allowed("pay-1") is True
    assert _app_module._pix_mp_poll_allowed("pay-1") is False
    # Pagamento diferente não é afetado.
    assert _app_module._pix_mp_poll_allowed("pay-2") is True


def test_pix_mp_poll_throttle_releases_after_interval(monkeypatch):
    _app_module._PIX_MP_POLL_LAST.clear()
    assert _app_module._pix_mp_poll_allowed("pay-3") is True
    _app_module._PIX_MP_POLL_LAST["pay-3"] = (
        time.monotonic() - _app_module._PIX_MP_POLL_MIN_INTERVAL - 1.0
    )
    assert _app_module._pix_mp_poll_allowed("pay-3") is True


def test_fetch_payment_accepts_short_timeout(monkeypatch):
    """fetch_payment propaga timeout ao urllib — poll usa 8s, não 30s."""
    import pix_payments as _pp

    seen: dict[str, float] = {}

    def fake_mp_request(token, method, path, payload=None, *, idempotency_key=None, timeout=30.0):
        seen["timeout"] = timeout
        return {"status": "pending"}

    monkeypatch.setattr(_pp, "_mp_request", fake_mp_request)
    _pp.fetch_payment("tok", "mp-1", timeout=8.0)
    assert seen["timeout"] == 8.0


# ── Câmbio: stale-while-revalidate (sem bloquear /api/catalog) ───────────────

def test_exchange_rates_expired_cache_returns_stale_without_blocking(monkeypatch):
    fetch_started = threading.Event()
    fetch_release = threading.Event()

    def slow_fetch():
        fetch_started.set()
        fetch_release.wait(timeout=5)
        return {"USD": 0.25, "EUR": 0.22}

    monkeypatch.setattr(_fx, "_fetch_frankfurter", slow_fetch)
    with _fx._cache_lock:
        _fx._cache["rates"] = {"USD": 0.11, "EUR": 0.10}
        _fx._cache["source"] = "frankfurter"
        _fx._cache["expires_at"] = 0.0
        _fx._cache["refresh_inflight"] = False

    t0 = time.perf_counter()
    payload = _fx.get_exchange_rates()
    elapsed = time.perf_counter() - t0

    assert elapsed < 1.0, f"request bloqueou no refresh de câmbio: {elapsed:.2f}s"
    assert payload["rates"]["USD"] == 0.11  # stale servido imediatamente

    assert fetch_started.wait(timeout=5)
    fetch_release.set()
    for _ in range(100):
        with _fx._cache_lock:
            if _fx._cache["rates"].get("USD") == 0.25:
                break
        time.sleep(0.05)
    with _fx._cache_lock:
        assert _fx._cache["rates"]["USD"] == 0.25
        assert _fx._cache["refresh_inflight"] is False


def test_exchange_rates_single_flight_refresh(monkeypatch):
    calls: list[int] = []
    release = threading.Event()

    def counted_fetch():
        calls.append(1)
        release.wait(timeout=5)
        return {"USD": 0.3, "EUR": 0.28}

    monkeypatch.setattr(_fx, "_fetch_frankfurter", counted_fetch)
    with _fx._cache_lock:
        _fx._cache["expires_at"] = 0.0
        _fx._cache["refresh_inflight"] = False

    _fx.get_exchange_rates()
    _fx.get_exchange_rates()
    _fx.get_exchange_rates()
    time.sleep(0.1)
    assert len(calls) == 1  # single-flight: só um refresh em voo
    release.set()
    for _ in range(100):
        with _fx._cache_lock:
            if not _fx._cache["refresh_inflight"]:
                break
        time.sleep(0.05)


def test_exchange_rates_force_refresh_still_synchronous(monkeypatch):
    monkeypatch.setattr(_fx, "_fetch_frankfurter", lambda: {"USD": 0.5, "EUR": 0.4})
    payload = _fx.get_exchange_rates(force_refresh=True)
    assert payload["rates"]["USD"] == 0.5
    assert payload["source"] == "frankfurter"


# ── Discord de tickets: HTTP externo fora do request ─────────────────────────

def test_ticket_discord_notify_runs_off_request_thread(monkeypatch):
    import ticket_notify as _tn

    called_from: list[str] = []
    done = threading.Event()

    def capture_discord(load_settings, ticket, event, **kwargs):
        called_from.append(threading.current_thread().name)
        done.set()
        return True

    monkeypatch.setattr(_tn, "notify_ticket_discord", capture_discord)

    class _FakeDb:
        def get(self, model, tid):
            return object()

        def commit(self):
            pass

        def rollback(self):
            pass

    monkeypatch.setattr(
        "ticket_service._ticket_row_to_dict",
        lambda row: {"id": 1, "subject": "t", "steam_id": None, "status": "open"},
    )
    monkeypatch.setattr(_tn, "_ticket_row_to_dict", lambda row: {
        "id": 1, "subject": "t", "steam_id": None, "status": "open",
    })

    _tn.notify_ticket_update(_FakeDb(), 1, "created", actor_name="X")
    assert done.wait(timeout=5), "notify Discord não foi disparado"
    assert called_from and called_from[0] != threading.main_thread().name
    assert called_from[0].startswith("ticket-discord-notify")


# ── Steam login: persona fetch sem segurar sessão web ────────────────────────

def test_touch_store_user_login_releases_db_before_steam(monkeypatch):
    session_state = {"open": False}

    class _FakeDb:
        def get(self, *_a, **_k):
            return None

        def add(self, _row):
            pass

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            session_state["open"] = False

    def _session_factory():
        session_state["open"] = True
        return _FakeDb()

    closed_before_steam = {"ok": False}

    def _slow_steam_refresh(_db, ids, **kw):
        closed_before_steam["ok"] = not session_state["open"]
        time.sleep(0.05)
        return {USER_STEAM: "NickSteam"} if USER_STEAM in ids else {}

    monkeypatch.setattr(_app_module, "_db_ready", lambda: True)
    monkeypatch.setattr(_app_module, "_steam_api_key_configured", lambda: True)
    monkeypatch.setattr(_app_module, "_SessionLocal", _session_factory)
    monkeypatch.setattr(_app_module, "_refresh_steam_personas", _slow_steam_refresh)
    monkeypatch.setattr(_app_module, "_release_db_session", lambda db, force=False: db.close())
    monkeypatch.setattr(
        "lottery_service.ensure_fixed_lottery_number",
        lambda *_a, **_k: None,
    )

    _app_module._touch_store_user_login(USER_STEAM)
    assert closed_before_steam["ok"] is True


# ── Plugin claim: sync Permissions após libertar sessão ────────────────────

def test_claim_pending_deferred_perm_sync_runs_after_db_release(monkeypatch):
    session_state = {"open": False}
    sync_during_db: list[bool] = []

    class _FakeDb:
        def query(self, *_a, **_k):
            return self

        def options(self, *_a, **_k):
            # claim usa load_only(...).options(...).filter(...).order_by(...).all()
            return self

        def filter(self, *_a, **_k):
            return self

        def order_by(self, *_a, **_k):
            return self

        def all(self):
            return []

        def execute(self, *_a, **_k):
            return type("R", (), {"rowcount": 0})()

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            session_state["open"] = False

    def _session_factory():
        session_state["open"] = True
        return _FakeDb()

    def _capture_flush(specs):
        sync_during_db.append(session_state["open"])

    monkeypatch.setenv("ARKSHOP_API_KEY", "test-io-guard-key")
    monkeypatch.setattr(_app_module, "_ARKSHOP_API_KEY", "test-io-guard-key")
    monkeypatch.setattr(_app_module, "_get_db_session", _session_factory)
    monkeypatch.setattr(_app_module, "_require_db", lambda: None)
    monkeypatch.setattr(_app_module, "_flush_deferred_license_perm_syncs", _capture_flush)
    monkeypatch.setattr(_app_module, "_release_db_session", lambda db, force=False: db.close())
    monkeypatch.setattr(_app_module, "_pending_empty_cache_hit", lambda *_a, **_k: False)

    client = _app_module.app.test_client()
    resp = client.post(
        "/api/pending/claim",
        json={"steam_id": USER_STEAM, "order_ids": []},
        headers={"X-API-Key": "test-io-guard-key"},
    )
    assert resp.status_code == 200

    assert sync_during_db == [False]
