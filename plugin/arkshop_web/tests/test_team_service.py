"""Focused tests for Modo Equipe (team_service)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import team_service as ts

USER_A = "76561198000000001"
USER_B = "76561198000000002"
USER_C = "76561198000000003"


@pytest.fixture()
def engine(tmp_path):
    path = tmp_path / "team_test.db"
    eng = create_engine(f"sqlite:///{path}", future=True)
    with eng.connect() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS players "
            "(steam_id TEXT PRIMARY KEY, points INTEGER DEFAULT 0, kits TEXT DEFAULT '{}')"
        ))
        conn.execute(text(
            "INSERT INTO players (steam_id, points) VALUES "
            f"('{USER_A}', 10000), ('{USER_B}', 5000), ('{USER_C}', 1000)"
        ))
        conn.commit()
    ts.ensure_team_schema(eng)
    return eng


@pytest.fixture()
def db(engine, monkeypatch):
    Session = sessionmaker(bind=engine)
    s = Session()

    def _settings():
        return {
            "teams_enabled": True,
            "teams_max_members": 10,
            "teams_amber_bonus_pp": 2,
            "teams_amber_bonus_cap": 20,
        }

    def _subtract(db_sess, steam_id, amount):
        row = db_sess.execute(
            text("SELECT points FROM players WHERE steam_id = :s"),
            {"s": steam_id},
        ).fetchone()
        if not row or int(row[0]) < amount:
            raise ValueError("insufficient_balance")
        new = int(row[0]) - amount
        db_sess.execute(
            text("UPDATE players SET points = :p WHERE steam_id = :s"),
            {"p": new, "s": steam_id},
        )
        return new

    ts.configure_team_service(settings_fn=_settings, subtract_points_tx=_subtract)
    monkeypatch.setattr(ts, "teams_enabled", lambda settings=None: True)
    yield s
    s.close()


def test_create_team_and_one_per_player(db):
    view = ts.create_team(db, steam_id=USER_A, name="Lobos do Norte", tag="LOB")
    assert view["team"]["name"] == "Lobos do Norte"
    assert view["team"]["owner_steam_id"] == USER_A
    assert len(view["members"]) == 1
    with pytest.raises(ValueError, match="já pertence|Já pertence"):
        ts.create_team(db, steam_id=USER_A, name="Outra")


def test_invite_accept_kick(db):
    ts.create_team(db, steam_id=USER_A, name="Equipe Alpha")
    team = ts.get_active_membership(db, USER_A)
    tid = team["team_id"]
    inv = ts.invite_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    assert inv["invite_code"]
    ts.accept_invite(db, steam_id=USER_B, invite_code=inv["invite_code"])
    assert ts.count_active_members(db, tid) == 2
    ts.kick_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    assert ts.count_active_members(db, tid) == 1


def test_roles_guardian_can_invite(db):
    ts.create_team(db, steam_id=USER_A, name="Papéis")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ts.invite_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    ts.accept_invite(db, steam_id=USER_B, team_id=tid)
    ts.assign_role(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B, role_key="GUARDIAN")
    assert "GUARDIAN" in ts._member_roles(db, tid, USER_B)
    inv = ts.invite_member(db, team_id=tid, actor_steam_id=USER_B, target_steam_id=USER_C)
    assert inv["invite_code"]


def test_transfer_ownership(db):
    ts.create_team(db, steam_id=USER_A, name="Bastão")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ts.invite_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    ts.accept_invite(db, steam_id=USER_B, team_id=tid)
    ts.transfer_ownership(db, team_id=tid, actor_steam_id=USER_A, new_owner_steam_id=USER_B)
    team = ts.get_team(db, tid)
    assert team["owner_steam_id"] == USER_B


def test_donate_amber_and_ledger(db):
    ts.create_team(db, steam_id=USER_A, name="Cofre")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    res = ts.donate_amber(db, team_id=tid, steam_id=USER_A, amount=500, idempotency_key="d1")
    assert res["donated"] == 500
    assert res["bank"]["amber_balance"] == 500
    dup = ts.donate_amber(db, team_id=tid, steam_id=USER_A, amount=500, idempotency_key="d1")
    assert dup.get("duplicate")
    ledger = ts.get_bank_ledger(db, tid)
    assert any(e["entry_type"] == "DONATE_AMBER" for e in ledger)


def test_warehouse_catalog_has_ten(db):
    cat = ts.warehouse_catalog()
    assert len(cat) == 10
    keys = {r["key"] for r in cat}
    assert "element_ore" in keys and "black_pearl" in keys and "sand" in keys
    assert ts.normalize_warehouse_key("rec_pnegra") == "black_pearl"
    assert ts.normalize_warehouse_key("hard_polymer") == "hard_polymer"
    with pytest.raises(ValueError, match="catálogo"):
        ts.normalize_warehouse_key("Paste")
    with pytest.raises(ValueError, match="catálogo"):
        ts.normalize_warehouse_key("unknown_item")


def test_deposit_catalog_and_reject_unknown(db):
    ts.create_team(db, steam_id=USER_A, name="Armazém")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ok = ts.deposit_resource(
        db, team_id=tid, steam_id=USER_A, resource_key="rec_elementore", amount=100, idempotency_key="dep1",
    )
    assert ok["resource_key"] == "element_ore"
    assert ok["bank"]["resources"]["element_ore"] == 100
    # Alias shop key also works
    ts.deposit_resource(
        db, team_id=tid, steam_id=USER_A, resource_key="black_pearl", amount=5, idempotency_key="dep2",
    )
    bank = ts.get_bank(db, tid)
    assert bank["resources"]["black_pearl"] == 5
    with pytest.raises(ValueError, match="catálogo"):
        ts.deposit_resource(
            db, team_id=tid, steam_id=USER_A, resource_key="CementingPaste", amount=10,
        )


def test_commit_to_milestone_and_insufficient_warehouse(db):
    ts.create_team(db, steam_id=USER_A, name="Commit")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ts.upsert_milestone(
        db,
        milestone_index=1,
        title="Marco 1",
        amber_required=50,
        xp_required=10,
        resources=[
            {"key": "element_ore", "quantity": 100},
            {"key": "black_pearl", "quantity": 20},
        ],
        status="ACTIVE",
    )
    ts.deposit_resource(
        db, team_id=tid, steam_id=USER_A, resource_key="element_ore", amount=40, idempotency_key="c1",
    )
    with pytest.raises(ValueError, match="insuficiente"):
        ts.commit_warehouse_to_milestone(
            db, team_id=tid, actor_steam_id=USER_A, resource_key="element_ore", amount=100,
        )
    ts.commit_warehouse_to_milestone(
        db, team_id=tid, actor_steam_id=USER_A, resource_key="element_ore", amount=40,
    )
    bank = ts.get_bank(db, tid)
    assert bank["resources"].get("element_ore", 0) == 0
    assert bank["committed"]["element_ore"] == 40
    # Not a requirement of current milestone
    ts.deposit_resource(
        db, team_id=tid, steam_id=USER_A, resource_key="sand", amount=50, idempotency_key="c2",
    )
    with pytest.raises(ValueError, match="não é requisito"):
        ts.commit_warehouse_to_milestone(
            db, team_id=tid, actor_steam_id=USER_A, resource_key="sand", amount=10,
        )


def test_milestone_complete_uses_committed(db):
    ts.create_team(db, steam_id=USER_A, name="Marcos")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ts.upsert_milestone(
        db,
        milestone_index=1,
        title="Marco 1",
        amber_required=100,
        xp_required=50,
        resources=[{"key": "hard_polymer", "quantity": 10}],
        status="ACTIVE",
    )
    ts.donate_amber(db, team_id=tid, steam_id=USER_A, amount=200)
    ts.deposit_resource(
        db, team_id=tid, steam_id=USER_A, resource_key="hard_polymer", amount=15, idempotency_key="r1",
    )
    # Warehouse alone does NOT complete
    team = ts.get_team(db, tid)
    ms = ts.get_current_milestone_for_team(db, team)
    view = ts.milestone_progress_view(db, team, ms)
    assert view["can_complete"] is False
    assert view["resources"][0]["warehouse"] == 15
    assert view["resources"][0]["committed"] == 0

    ts.commit_warehouse_to_milestone(
        db, team_id=tid, actor_steam_id=USER_A, resource_key="hard_polymer", amount=10,
    )
    ts.add_team_timed_xp(db, steam_id=USER_A, amount=50, map_id="island", cycle_key="c1", commit=True)
    out = ts.try_complete_milestone(db, team_id=tid, actor_steam_id=USER_A)
    assert out["completed"] is True
    team = ts.get_team(db, tid)
    assert team["milestone_index"] == 1
    # Q3: lifetime XP is NOT reset on marco complete
    assert team["team_xp"] == 50
    assert team["team_xp_lifetime"] == 50
    assert team["team_honor"] == 50
    bank = ts.get_bank(db, tid)
    assert bank["amber_balance"] == 100  # 200 - 100
    # Excess warehouse (15-10) remains; committed cleared
    assert bank["resources"].get("hard_polymer") == 5
    assert bank.get("committed") == {}


def test_cumulative_xp_threshold_and_no_reset(db):
    """Q3: xp_required is incremental; threshold = sum(1..N); complete keeps lifetime."""
    ts.create_team(db, steam_id=USER_A, name="LifetimeXP")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ts.upsert_milestone(
        db, milestone_index=1, title="M1", amber_required=0, xp_required=100,
        resources=[], status="ACTIVE",
    )
    ts.upsert_milestone(
        db, milestone_index=2, title="M2", amber_required=0, xp_required=200,
        resources=[], status="ACTIVE",
    )
    assert ts.cumulative_xp_threshold(db, 1) == 100
    assert ts.cumulative_xp_threshold(db, 2) == 300

    ts.add_team_timed_xp(db, steam_id=USER_A, amount=100, map_id="m", cycle_key="a", commit=True)
    team = ts.get_team(db, tid)
    ms1 = ts.get_current_milestone_for_team(db, team)
    view1 = ts.milestone_progress_view(db, team, ms1)
    assert view1["xp_threshold_cumulative"] == 100
    assert view1["xp_ok"] is True
    assert view1["can_complete"] is True
    out = ts.try_complete_milestone(db, team_id=tid, actor_steam_id=USER_A)
    assert out["completed"] is True
    team = ts.get_team(db, tid)
    assert team["milestone_index"] == 1
    assert team["team_xp_lifetime"] == 100  # not zeroed

    # Marco 2 needs lifetime >= 300
    ms2 = ts.get_current_milestone_for_team(db, team)
    view2 = ts.milestone_progress_view(db, team, ms2)
    assert view2["xp_threshold_cumulative"] == 300
    assert view2["xp_ok"] is False
    ts.add_team_timed_xp(db, steam_id=USER_A, amount=200, map_id="m", cycle_key="b", commit=True)
    team = ts.get_team(db, tid)
    view2b = ts.milestone_progress_view(db, team, ms2)
    assert view2b["team_xp_lifetime"] == 300
    assert view2b["xp_ok"] is True
    out2 = ts.try_complete_milestone(db, team_id=tid, actor_steam_id=USER_A)
    assert out2["completed"] is True
    team = ts.get_team(db, tid)
    assert team["milestone_index"] == 2
    assert team["team_xp_lifetime"] == 300
    assert team["team_honor"] == 300


def test_auto_kick_settings_validation(db):
    ts.create_team(db, steam_id=USER_A, name="KickCfg")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    with pytest.raises(ValueError, match="auto_kick_inactive_hours"):
        ts.validate_auto_kick_settings(auto_kick_inactive=True, auto_kick_inactive_hours=1)
    with pytest.raises(ValueError, match="auto_kick_inactive_hours"):
        ts.validate_auto_kick_settings(auto_kick_inactive=True, auto_kick_inactive_hours=9999)
    enabled, hours = ts.validate_auto_kick_settings(
        auto_kick_inactive=False, auto_kick_inactive_hours=5,
    )
    assert enabled is False
    assert hours == ts.AUTO_KICK_HOURS_MIN  # clamped when off
    updated = ts.update_team_settings(
        db, team_id=tid, actor_steam_id=USER_A,
        auto_kick_inactive=True, auto_kick_inactive_hours=48,
    )
    assert updated["auto_kick_inactive"] is True
    assert updated["auto_kick_inactive_hours"] == 48


def test_process_inactive_kicks_respects_hours_and_owner(db):
    from datetime import datetime, timedelta

    ts.create_team(db, steam_id=USER_A, name="IdleKick")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ts.invite_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    ts.accept_invite(db, steam_id=USER_B, team_id=tid)
    ts.update_team_settings(
        db, team_id=tid, actor_steam_id=USER_A,
        auto_kick_inactive=True, auto_kick_inactive_hours=24,
    )
    now = datetime(2026, 7, 18, 12, 0, 0)
    stale = now - timedelta(hours=48)
    # Owner stays recent; B is stale
    ts.touch_member_activity(db, team_id=tid, steam_id=USER_A, at=now, commit=True)
    ts.touch_member_activity(db, team_id=tid, steam_id=USER_B, at=stale, commit=True)
    result = ts.process_team_inactive_kicks(db, now=now)
    assert result["processed"] == 1
    assert result["kicked"][0]["steam_id"] == USER_B
    assert ts.count_active_members(db, tid) == 1
    # Owner never auto-kicked even if stale
    ts.invite_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_C)
    ts.accept_invite(db, steam_id=USER_C, team_id=tid)
    ts.touch_member_activity(db, team_id=tid, steam_id=USER_A, at=stale, commit=True)
    ts.touch_member_activity(db, team_id=tid, steam_id=USER_C, at=now, commit=True)
    result2 = ts.process_team_inactive_kicks(db, now=now)
    assert result2["processed"] == 0
    assert ts.get_team(db, tid)["owner_steam_id"] == USER_A
    assert ts.count_active_members(db, tid) == 2


def test_upsert_milestone_rejects_unknown_resource(db):
    with pytest.raises(ValueError, match="catálogo"):
        ts.upsert_milestone(
            db,
            milestone_index=1,
            title="Bad",
            resources=[{"key": "Paste", "quantity": 10}],
            status="DRAFT",
        )


def test_treasurer_can_commit(db):
    ts.create_team(db, steam_id=USER_A, name="Tesouro")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ts.invite_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    ts.accept_invite(db, steam_id=USER_B, team_id=tid)
    ts.assign_role(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B, role_key="TREASURER")
    ts.upsert_milestone(
        db,
        milestone_index=1,
        title="M1",
        amber_required=0,
        xp_required=0,
        resources=[{"key": "sand", "quantity": 5}],
        status="ACTIVE",
    )
    ts.deposit_resource(db, team_id=tid, steam_id=USER_A, resource_key="sand", amount=5)
    ts.commit_warehouse_to_milestone(
        db, team_id=tid, actor_steam_id=USER_B, resource_key="sand", amount=5,
    )
    assert ts.get_bank(db, tid)["committed"]["sand"] == 5


def test_player_xp_lifetime_without_team(db):
    r = ts.add_team_timed_xp(
        db, steam_id=USER_C, amount=25, map_id="rag", cycle_key="k1", commit=True,
    )
    assert r["applied"]
    rank = ts.my_player_rank(db, USER_C)
    assert rank["xp"] == 25


def test_xp_idempotent(db):
    ts.create_team(db, steam_id=USER_A, name="Idem")
    a = ts.add_team_timed_xp(db, steam_id=USER_A, amount=10, map_id="m", cycle_key="k", commit=True)
    b = ts.add_team_timed_xp(db, steam_id=USER_A, amount=10, map_id="m", cycle_key="k", commit=True)
    assert a["applied"]
    assert b.get("duplicate")


def test_ranking_teams(db):
    ts.create_team(db, steam_id=USER_A, name="RankA")
    ts.create_team(db, steam_id=USER_B, name="RankB")
    rows = ts.ranking_teams(db, limit=10)
    assert len(rows) >= 2
    assert rows[0]["rank"] == 1


def test_team_split_snapshot(db):
    ts.create_team(db, steam_id=USER_A, name="SplitTeam")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ts.invite_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    ts.accept_invite(db, steam_id=USER_B, team_id=tid)
    ts.create_or_update_team_split(db, team_id=tid, actor_steam_id=USER_A, sender_pct=60)
    snap = ts.get_team_split_snapshot_for_listing(db, seller_steam_id=USER_A, price=2000)
    assert snap is not None
    assert snap["kind"] == "team"
    assert sum(m["percentage"] for m in snap["members"]) == 100


def test_name_unique(db):
    ts.create_team(db, steam_id=USER_A, name="Único")
    with pytest.raises(ValueError, match="nome"):
        ts.create_team(db, steam_id=USER_B, name="único")
