"""Testes: convite /tribe.CODE, accept/deny, leave-revoke, principal cooldown."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tribe_service import (
    ensure_tribe_schema,
    get_members_by_map,
    get_or_create_owner,
    record_presence,
    upsert_map_link,
)
from tribe_invite_service import (
    PRINCIPAL_SWAP_COOLDOWN_HOURS,
    count_principals_for_owner,
    create_join_request,
    generate_invite_code,
    get_active_invite_code,
    resolve_join_request,
    revoke_membership_on_map,
    set_principal_map,
    is_confirmed_member,
    list_join_requests,
)

USER_A = "76561198000000001"
USER_B = "76561198000000002"
USER_C = "76561198000000003"
SERVER_ISLAND = "the_island"
SERVER_RAG = "ragnarok"


@pytest.fixture()
def engine(tmp_path):
    path = tmp_path / "tribe_invite_test.db"
    eng = create_engine(f"sqlite:///{path}", future=True)
    with eng.connect() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS players "
            "(steam_id TEXT PRIMARY KEY, points INTEGER DEFAULT 0, kits TEXT DEFAULT '{}')"
        ))
        conn.commit()
    ensure_tribe_schema(eng)
    return eng


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _setup_owner_tribe(db, steam_id=USER_A, server_id=SERVER_ISLAND, tribe_id=10001):
    owner = get_or_create_owner(db, steam_id, "Owner A")
    record_presence(
        db,
        steam_id=steam_id,
        server_id=server_id,
        map_name=server_id,
        tribe_id=tribe_id,
        tribe_name="ARKLAND BR",
        is_owner=True,
        members=[
            {"steam_id": steam_id, "character_name": "OwnerA", "is_owner": True, "rank_name": "Proprietário"},
            {"steam_id": USER_B, "character_name": "MemberB", "is_owner": False, "rank_name": "Member"},
        ],
    )
    return owner


def test_invite_generate_and_join_pending(db):
    _setup_owner_tribe(db)
    inv = generate_invite_code(db, owner_steam_id=USER_A, regenerate=False)
    assert inv["code"]
    assert inv["chat_command"].startswith("/tribe.")
    assert get_active_invite_code(db, inv["cluster_group"]["id"])["code"] == inv["code"]

    # Membro B usa código no mesmo mapa
    req = create_join_request(
        db,
        code=inv["code"],
        steam_id=USER_B,
        server_id=SERVER_ISLAND,
        tribe_id=10001,
        character_name="MemberB",
    )
    assert req["status"] == "PENDING"
    pending = list_join_requests(db, owner_steam_id=USER_A, status="PENDING")
    assert len(pending) == 1
    assert pending[0]["steam_id"] == USER_B


def test_invite_accept_confirms_member(db):
    _setup_owner_tribe(db)
    inv = generate_invite_code(db, owner_steam_id=USER_A)
    req = create_join_request(
        db, code=inv["code"], steam_id=USER_B,
        server_id=SERVER_ISLAND, tribe_id=10001, character_name="MemberB",
    )
    out = resolve_join_request(
        db, owner_steam_id=USER_A, request_id=req["id"], action="accept",
    )
    assert out["status"] == "ACCEPTED"
    assert is_confirmed_member(db, inv["cluster_group"]["id"], USER_B)
    assert out.get("confirmed_via") == "code"


def test_invite_deny_may_regenerate(db):
    _setup_owner_tribe(db)
    inv = generate_invite_code(db, owner_steam_id=USER_A)
    old_code = inv["code"]
    req = create_join_request(
        db, code=old_code, steam_id=USER_B,
        server_id=SERVER_ISLAND, tribe_id=10001,
    )
    out = resolve_join_request(
        db, owner_steam_id=USER_A, request_id=req["id"],
        action="deny", regenerate_code_on_deny=True,
    )
    assert out["status"] == "DENIED"
    assert out.get("code_regenerated") is True
    new_inv = get_active_invite_code(db, inv["cluster_group"]["id"])
    assert new_inv["code"] != old_code
    # Código antigo inválido
    with pytest.raises(ValueError, match="inválido|expirado|revogado"):
        create_join_request(
            db, code=old_code, steam_id=USER_C,
            server_id=SERVER_ISLAND, tribe_id=10001,
        )


def test_leave_revokes_one_map_only(db):
    _setup_owner_tribe(db, server_id=SERVER_ISLAND, tribe_id=10001)
    record_presence(
        db,
        steam_id=USER_B,
        server_id=SERVER_RAG,
        map_name=SERVER_RAG,
        tribe_id=20002,
        tribe_name="FOB RAG",
        is_owner=False,
        members=[
            {"steam_id": USER_A, "character_name": "OwnerA", "is_owner": True},
            {"steam_id": USER_B, "character_name": "MemberB", "is_owner": False},
        ],
    )
    # B em Island e Rag
    record_presence(
        db,
        steam_id=USER_B,
        server_id=SERVER_ISLAND,
        map_name=SERVER_ISLAND,
        tribe_id=10001,
        tribe_name="ARKLAND BR",
        is_owner=False,
        members=[
            {"steam_id": USER_A, "character_name": "OwnerA", "is_owner": True},
            {"steam_id": USER_B, "character_name": "MemberB", "is_owner": False},
        ],
    )
    members_island = get_members_by_map(db, server_id=SERVER_ISLAND, tribe_id=10001)
    members_rag = get_members_by_map(db, server_id=SERVER_RAG, tribe_id=20002)
    assert any(m["steam_id"] == USER_B for m in members_island)
    assert any(m["steam_id"] == USER_B for m in members_rag)

    revoke_membership_on_map(
        db, steam_id=USER_B, server_id=SERVER_RAG, tribe_id=20002, reason="test",
    )
    members_island2 = get_members_by_map(db, server_id=SERVER_ISLAND, tribe_id=10001)
    members_rag2 = get_members_by_map(db, server_id=SERVER_RAG, tribe_id=20002)
    assert any(m["steam_id"] == USER_B for m in members_island2)
    assert not any(m["steam_id"] == USER_B for m in members_rag2)


def test_presence_tribe_id_zero_revokes_map(db):
    _setup_owner_tribe(db)
    record_presence(
        db,
        steam_id=USER_B,
        server_id=SERVER_ISLAND,
        map_name=SERVER_ISLAND,
        tribe_id=10001,
        tribe_name="ARKLAND BR",
        is_owner=False,
        members=[
            {"steam_id": USER_A, "character_name": "A", "is_owner": True},
            {"steam_id": USER_B, "character_name": "B", "is_owner": False},
        ],
    )
    assert any(
        m["steam_id"] == USER_B
        for m in get_members_by_map(db, server_id=SERVER_ISLAND, tribe_id=10001)
    )
    record_presence(
        db,
        steam_id=USER_B,
        server_id=SERVER_ISLAND,
        map_name=SERVER_ISLAND,
        tribe_id=0,
        tribe_name="",
        is_owner=False,
        source="plugin_leave",
    )
    assert not any(
        m["steam_id"] == USER_B
        for m in get_members_by_map(db, server_id=SERVER_ISLAND, tribe_id=10001)
    )


def test_one_principal_per_owner_and_cooldown(db):
    owner = _setup_owner_tribe(db, server_id=SERVER_ISLAND, tribe_id=10001)
    upsert_map_link(
        db,
        tribe_owner_id=owner["id"],
        server_id=SERVER_RAG,
        tribe_id=20002,
        tribe_name_local="FOB RAG",
        tribe_type="fob",
    )
    inv = generate_invite_code(db, owner_steam_id=USER_A)
    assert inv["cluster_group"]

    # Já é principal no Island — set_principal no Rag
    out = set_principal_map(db, owner_steam_id=USER_A, server_id=SERVER_RAG)
    assert out["principal_server_id"] == SERVER_RAG
    assert count_principals_for_owner(db, USER_A) == 1

    # Cooldown 24h
    with pytest.raises(ValueError, match="Cooldownoldown"):
        set_principal_map(db, owner_steam_id=USER_A, server_id=SERVER_ISLAND)

    # Simula passagem do cooldown
    past = datetime.utcnow() - timedelta(hours=PRINCIPAL_SWAP_COOLDOWN_HOURS + 1)
    db.execute(
        text("UPDATE tribe_cluster_groups SET principal_changed_at = :p"),
        {"p": past},
    )
    db.commit()
    out2 = set_principal_map(db, owner_steam_id=USER_A, server_id=SERVER_ISLAND)
    assert out2["principal_server_id"] == SERVER_ISLAND
    assert count_principals_for_owner(db, USER_A) == 1
