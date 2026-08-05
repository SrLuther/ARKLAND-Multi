"""Mode B plugin_b_by_code — rejeições enabled / sessão / ALIVE."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import event_hunt_service as ehs

ADMIN = "76561198000000999"


@pytest.fixture()
def engine(tmp_path):
    path = tmp_path / "event_hunt_b.db"
    eng = create_engine(f"sqlite:///{path}", future=True)
    ehs.ensure_event_hunt_schema(eng)
    return eng


@pytest.fixture()
def db(engine, monkeypatch):
    Session = sessionmaker(bind=engine)
    s = Session()

    def _settings():
        return {"event_hunt_enabled": True}

    ehs.configure_event_hunt_service(settings_fn=_settings)
    monkeypatch.setattr(ehs, "event_hunt_enabled", lambda settings=None: True)
    yield s
    s.close()


def _active_session_with_dino(db, *, enabled=True, code="EUSUA4"):
    sess = ehs.admin_create_session(db, {"name": "Megalossauro 500", "map_scope": "*"})
    sid = int(sess["event_session_id"])
    ehs.admin_transition_session(db, sid, target_status="OPEN_INSCRIPTION")
    ehs.admin_transition_session(db, sid, target_status="ACTIVE")
    dino = ehs.admin_create_public_dino(
        db,
        sid,
        {
            "display_name": "Megalossauro 500",
            "blueprint": "Blueprint'/Game/PrimalEarth/Dinos/Mega/Mega.Mega'",
            "level": 150,
            "points_team": 500,
            "event_code": code,
            "enabled": enabled,
        },
    )
    return sess, dino


def test_plugin_b_by_code_ok_when_enabled_active(db):
    _sess, dino = _active_session_with_dino(db, enabled=True, code="EUSUA4")
    payload = ehs.plugin_b_by_code(db, "eusua4")
    assert payload["ok"] is True
    assert payload["event_code"] == "EUSUA4"
    assert payload["public_dino_id"] == dino["public_dino_id"]


def test_plugin_b_by_code_rejects_disabled(db):
    _sess, dino = _active_session_with_dino(db, enabled=True, code="EUSUA4")
    ehs.admin_update_public_dino(db, dino["public_dino_id"], {"enabled": False})
    with pytest.raises(ehs.EventHuntReject) as ei:
        ehs.plugin_b_by_code(db, "EUSUA4")
    assert ei.value.error_code == "dino_disabled"
    assert ei.value.http_status == 400
    assert "desactivado" in str(ei.value).lower() or "Desactivado" in str(ei.value)


def test_plugin_b_by_code_rejects_alive_with_void_hint(db):
    _sess, dino = _active_session_with_dino(db, enabled=True, code="EALIVE1")
    spawned = ehs.plugin_b_mark_spawned(
        db,
        public_dino_id=dino["public_dino_id"],
        admin_steam_id=ADMIN,
        dino_id1=1,
        dino_id2=2,
    )
    iid = int(spawned["instance"]["instance_id"])
    with pytest.raises(ehs.EventHuntReject) as ei:
        ehs.plugin_b_by_code(db, "EALIVE1")
    assert ei.value.error_code == "instance_alive"
    assert ei.value.http_status == 409
    assert f"/instances/{iid}/void" in str(ei.value)
    # Void clears ALIVE → by-code OK again
    ehs.admin_void_instance(db, iid, admin_steam_id=ADMIN, note="re-summon")
    payload = ehs.plugin_b_by_code(db, "EALIVE1")
    assert payload["ok"] is True
