from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from system_status_center import (
    SEED_SYSTEMS,
    ensure_system_status_schema,
    lumo_status_snapshot,
    register_system_status_routes,
)


class _Limiter:
    def limit(self, *_args, **_kwargs):
        return lambda fn: fn


def _identity_decorator(fn):
    return fn


def test_catalog_seed_is_idempotent_and_does_not_claim_verified_status(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'status.sqlite'}")
    ensure_system_status_schema(engine)
    ensure_system_status_schema(engine)
    with engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM system_status_catalog")).scalar_one()
        row = conn.execute(text(
            "SELECT maturity,operational,availability FROM system_status_catalog WHERE system_key='structure-limits'"
        )).one()
    assert count == len(SEED_SYSTEMS)
    assert any(item[0] == "chat-arkland" for item in SEED_SYSTEMS)
    assert tuple(row) == ("NAO_AVALIADO", "NAO_MONITORADO", None)


def test_public_admin_incident_and_lumo_flows_are_persisted_and_audited(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'status.sqlite'}")
    ensure_system_status_schema(engine)
    app = Flask(__name__)
    app.config["TESTING"] = True
    register_system_status_routes(
        app,
        db_ready=lambda: True,
        engine_getter=lambda: engine,
        admin_required=_identity_decorator,
        api_key_required=lambda **_kwargs: _identity_decorator,
        actor_getter=lambda: "76561198000000000",
        load_servers=lambda: [{"server_id": "srv05", "label": "05 The Island Híbrido", "server_map": "TheIsland"}],
        runtime_statuses=lambda **_kwargs: {"srv05": {
            "display_name": "[BR][ARKLAND][HYBRIDO] The Island - (v361.7)",
            "status": "ONLINE", "updated_at": "2026-11-25T12:00:00Z", "status_detail": "Steam listing confirmed",
        }},
        limiter=_Limiter(),
    )
    client = app.test_client()

    public = client.get("/api/public/systems-status").get_json()
    assert public["ok"] is True
    cluster = next(item for item in public["systems"] if item["system_key"] == "ark-cluster")
    assert cluster["instances"][0]["display_name"] == "[BR][ARKLAND][HYBRIDO] The Island - (v361.7)"
    assert cluster["instances"][0]["operational"] == "ONLINE"

    changed = client.put("/api/admin/systems-status/structure-limits", json={
        "maturity": "ALPHA", "operational": "NAO_MONITORADO", "player_note": "Build observacional em teste.",
    })
    assert changed.status_code == 200
    assert changed.get_json()["system"]["maturity"] == "ALPHA"

    created = client.post("/api/admin/systems-status/structure-limits/incidents", json={
        "title": "Teste de validação", "description": "Incidente de teste", "state": "IDENTIFICADO",
    })
    assert created.status_code == 201
    incident_id = created.get_json()["incident_id"]
    assert client.patch(f"/api/admin/systems-status/incidents/{incident_id}", json={"state": "RESOLVIDO"}).status_code == 200

    with engine.connect() as conn:
        audit_count = conn.execute(text("SELECT COUNT(*) FROM system_status_audit")).scalar_one()
    assert audit_count == 3
    snapshot = lumo_status_snapshot(engine)
    assert snapshot["ok"] is True
    assert any(item["system_key"] == "structure-limits" for item in snapshot["systems"])
    assert snapshot["incidents"] == []
