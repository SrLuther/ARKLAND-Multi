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
            "teams_max_members": 5,
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
    assert view["team"]["max_members"] == 5
    assert len(view["members"]) == 1
    with pytest.raises(ValueError, match="já pertence|Já pertence"):
        ts.create_team(db, steam_id=USER_A, name="Outra")


def test_default_max_members_is_five(db):
    assert ts.DEFAULT_MAX_MEMBERS == 5
    assert ts.default_max_members({"teams_max_members": 5}) == 5
    assert ts.default_max_members({}) == 5
    view = ts.create_team(db, steam_id=USER_A, name="Cap5")
    assert view["team"]["max_members"] == 5
    assert view["accepting_members"] is False  # recruitment closed by default
    assert view["recruiting_open"] is False


def test_teams_enabled_defaults_on_when_absent(monkeypatch):
    """Sem fixture db — não monkeypatcha teams_enabled para True."""
    monkeypatch.setattr(ts, "_load_settings", lambda: {})
    assert ts.teams_enabled() is True
    assert ts.teams_enabled({}) is True
    assert ts.teams_enabled({"teams_enabled": False}) is False
    assert ts.teams_enabled({"teams_enabled": True}) is True


def test_list_public_teams_and_recruiting_gate(db):
    ts.create_team(db, steam_id=USER_A, name="Aberta")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ts.update_mural(db, team_id=tid, actor_steam_id=USER_A, mural_text="Sem griefing.")
    ts.set_recruitment_open(db, team_id=tid, actor_steam_id=USER_A, open_=True)
    listing = ts.list_public_teams(db, q="Aber")
    assert listing["total"] >= 1
    row = next(x for x in listing["items"] if x["id"] == tid)
    assert row["name"] == "Aberta"
    assert row["owner_steam_id"] == USER_A
    assert row["mural_text"] == "Sem griefing."
    assert row["member_count"] == 1
    assert row["max_members"] == 5
    assert row["recruitment_open"] is True
    assert row["accepting_members"] is True
    assert row["recruiting_open"] is True
    # Full team is not accepting even if flag open (staff floor is max_members>=2)
    ts.staff_set_team_max_members(db, team_id=tid, max_members=2)
    ts.invite_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    ts.accept_invite(db, steam_id=USER_B, team_id=tid)
    listing2 = ts.list_public_teams(db)
    row2 = next(x for x in listing2["items"] if x["id"] == tid)
    assert row2["member_count"] == 2
    assert row2["max_members"] == 2
    assert row2["accepting_members"] is False
    with pytest.raises(ValueError, match="cheia"):
        ts.request_join(db, team_id=tid, steam_id=USER_C)
    # Kick B, raise cap, close recruitment — join blocked by flag
    ts.kick_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    ts.staff_set_team_max_members(db, team_id=tid, max_members=5)
    ts.set_recruitment_open(db, team_id=tid, actor_steam_id=USER_A, open_=False)
    with pytest.raises(ValueError, match="aberta"):
        ts.request_join(db, team_id=tid, steam_id=USER_C)
    ts.set_recruitment_open(db, team_id=tid, actor_steam_id=USER_A, open_=True)
    pending = ts.request_join(db, team_id=tid, steam_id=USER_C)
    assert pending["status"] == "PENDING"
    mine = ts.my_team_or_invites(db, USER_A)
    assert any(j["steam_id"] == USER_C for j in mine.get("join_requests") or [])


def test_milestone_raises_max_members(db):
    ts.create_team(db, steam_id=USER_A, name="UnlockCap")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    assert ts.get_team(db, tid)["max_members"] == 5
    ts.upsert_milestone(
        db,
        milestone_index=1,
        title="M1",
        amber_required=0,
        xp_required=0,
        resources=[],
        max_members_unlock=8,
        status="ACTIVE",
    )
    out = ts.try_complete_milestone(db, team_id=tid, actor_steam_id=USER_A)
    assert out["completed"] is True
    assert ts.get_team(db, tid)["max_members"] == 8


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


def _points(db, steam_id: str) -> int:
    return int(db.execute(
        text("SELECT points FROM players WHERE steam_id = :s"),
        {"s": steam_id},
    ).fetchone()[0])


def test_founding_first_free_second_charges_2500(db):
    """Q5: 1ª fundação grátis; após leave/disband, 2ª custa 2500 Â."""
    assert ts.FOUNDING_FEE_AMBER == 2500
    before = _points(db, USER_A)
    view = ts.create_team(db, steam_id=USER_A, name="Primeira")
    assert view.get("founding_fee_charged") == 0
    assert _points(db, USER_A) == before
    assert ts.count_teams_founded(db, USER_A) == 1

    ts.leave_team(db, steam_id=USER_A)
    assert ts.get_active_membership(db, USER_A) is None

    view2 = ts.create_team(db, steam_id=USER_A, name="Segunda")
    assert view2.get("founding_fee_charged") == 2500
    assert _points(db, USER_A) == before - 2500
    assert ts.count_teams_founded(db, USER_A) == 2


def test_founding_second_insufficient_balance(db):
    """Q5: 2ª fundação falha se saldo < 2500."""
    ts.create_team(db, steam_id=USER_C, name="Barata")
    ts.leave_team(db, steam_id=USER_C)
    assert _points(db, USER_C) == 1000
    with pytest.raises(ValueError, match="2500|insuficiente|Saldo"):
        ts.create_team(db, steam_id=USER_C, name="CaraDemais")
    assert _points(db, USER_C) == 1000
    assert ts.get_active_membership(db, USER_C) is None


def test_max_two_special_roles(db):
    """Q13: máx. 2 papéis especiais; 3º rejeitado. OWNER não conta no limite."""
    ts.create_team(db, steam_id=USER_A, name="RolesCap")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ts.invite_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    ts.accept_invite(db, steam_id=USER_B, team_id=tid)

    ts.assign_role(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B, role_key="GUARDIAN")
    ts.assign_role(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B, role_key="HERALD")
    roles = ts._member_roles(db, tid, USER_B)
    assert "GUARDIAN" in roles and "HERALD" in roles

    with pytest.raises(ValueError, match="Máximo de 2|2 papéis"):
        ts.assign_role(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B, role_key="TREASURER")

    # Owner may also hold up to 2 special roles (OWNER excluded from cap)
    ts.assign_role(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_A, role_key="TREASURER")
    ts.assign_role(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_A, role_key="ARCHIVIST")
    owner_roles = ts._member_roles(db, tid, USER_A)
    assert "OWNER" in owner_roles
    assert "TREASURER" in owner_roles and "ARCHIVIST" in owner_roles
    with pytest.raises(ValueError, match="Máximo de 2|2 papéis"):
        ts.assign_role(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_A, role_key="AMBASSADOR")


def test_guardian_cannot_confirm_lottery_or_split(db, monkeypatch):
    """Q14: sorteio e split = Owner only."""
    ts.create_team(db, steam_id=USER_A, name="GuardPerms")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ts.invite_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    ts.accept_invite(db, steam_id=USER_B, team_id=tid)
    ts.assign_role(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B, role_key="GUARDIAN")

    with pytest.raises(PermissionError):
        ts.create_or_update_team_split(db, team_id=tid, actor_steam_id=USER_B, sender_pct=60)
    with pytest.raises(PermissionError):
        ts.confirm_team_lottery(db, team_id=tid, actor_steam_id=USER_B, campaign_id=1)
    # Owner OK for split
    ts.create_or_update_team_split(db, team_id=tid, actor_steam_id=USER_A, sender_pct=60)


def test_amber_bonus_via_milestones_q7(db):
    """Q7: bonus is additive AND unlocked via marco amber_bonus_pp (not a free-floating %)."""
    assert ts.team_amber_bonus_pct(0) == 0
    assert ts.team_amber_bonus_pct(1) == 2  # flat fallback without db milestones
    assert ts.team_amber_bonus_pct(10) == 20
    assert ts.team_amber_bonus_pct(15) == 20  # soft cap
    assert ts.FOUNDING_FEE_AMBER == 2500
    assert ts.MAX_SPECIAL_ROLES == 2
    assert ts.LOTTERY_SHORTFALL_REFUND_AMBER == 5000

    ts.upsert_milestone(
        db, milestone_index=1, title="M1", amber_required=0, xp_required=10,
        resources=[], amber_bonus_pp=2, status="ACTIVE",
    )
    ts.upsert_milestone(
        db, milestone_index=2, title="M2", amber_required=0, xp_required=10,
        resources=[], amber_bonus_pp=5, status="ACTIVE",
    )
    assert ts.sum_milestone_amber_bonus_pp(db, 0) == 0
    assert ts.sum_milestone_amber_bonus_pp(db, 1) == 2
    assert ts.sum_milestone_amber_bonus_pp(db, 2) == 7
    assert ts.team_amber_bonus_pct(2, db=db) == 7
    # Cap applies
    ts.upsert_milestone(
        db, milestone_index=3, title="M3", amber_required=0, xp_required=10,
        resources=[], amber_bonus_pp=50, status="ACTIVE",
    )
    assert ts.team_amber_bonus_pct(3, db=db) == 20


def test_milestone_cursor_per_team(db):
    """Q16: each team has its own milestone_index cursor on the shared trail."""
    ts.upsert_milestone(
        db, milestone_index=1, title="M1", amber_required=0, xp_required=10,
        resources=[], status="ACTIVE",
    )
    ts.upsert_milestone(
        db, milestone_index=2, title="M2", amber_required=0, xp_required=10,
        resources=[], status="ACTIVE",
    )

    ts.create_team(db, steam_id=USER_A, name="CursorA")
    ts.create_team(db, steam_id=USER_B, name="CursorB")
    tid_a = ts.get_active_membership(db, USER_A)["team_id"]
    tid_b = ts.get_active_membership(db, USER_B)["team_id"]

    team_a = ts.get_team(db, tid_a)
    ms_a = ts.get_current_milestone_for_team(db, team_a)
    assert ms_a and ms_a["milestone_index"] == 1

    # Advance A only
    db.execute(
        text("UPDATE teams SET milestone_index = 1 WHERE id = :id"),
        {"id": tid_a},
    )
    db.commit()
    team_a = ts.get_team(db, tid_a)
    team_b = ts.get_team(db, tid_b)
    assert ts.get_current_milestone_for_team(db, team_a)["milestone_index"] == 2
    assert ts.get_current_milestone_for_team(db, team_b)["milestone_index"] == 1


# ── Team lottery (Q9–Q12) ────────────────────────────────────

@pytest.fixture()
def lottery_ready(db, engine, monkeypatch, tmp_path):
    """Wire lottery schema + enable flag into the team test DB."""
    import json
    import lottery_service as ls
    import app as _app_module

    ls.ensure_lottery_schema(engine)
    settings_file = tmp_path / "lot_settings.json"
    settings_file.write_text(json.dumps({"lottery_enabled": True, "teams_enabled": True}), encoding="utf-8")
    monkeypatch.setattr(_app_module, "_STATE_FILE", settings_file)

    def _credit(db_sess, steam_id, amount):
        row = db_sess.execute(
            text("SELECT points FROM players WHERE steam_id = :s"),
            {"s": steam_id},
        ).fetchone()
        cur = int(row[0]) if row else 0
        db_sess.execute(
            text(
                "INSERT INTO players (steam_id, points) VALUES (:s, :p) "
                "ON CONFLICT(steam_id) DO UPDATE SET points = :p"
            ),
            {"s": steam_id, "p": cur + int(amount)},
        )

    def _debit(db_sess, steam_id, amount):
        row = db_sess.execute(
            text("SELECT points FROM players WHERE steam_id = :s"),
            {"s": steam_id},
        ).fetchone()
        if not row or int(row[0]) < amount:
            raise ValueError("insufficient_balance")
        db_sess.execute(
            text("UPDATE players SET points = :p WHERE steam_id = :s"),
            {"p": int(row[0]) - amount, "s": steam_id},
        )

    ls.configure_lottery(
        credit_fn=_credit,
        debit_fn=_debit,
        settings_fn=lambda: {"lottery_enabled": True},
    )
    monkeypatch.setattr(ls, "_is_enabled", lambda: True)
    return ls


def _make_active_campaign(db, ls, *, draw_hours=48, prize_base=9000, catalog=None):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    data = {
        "title": "Team Lot Test",
        "draw_at": (now + timedelta(hours=draw_hours)).isoformat(),
        "starts_at": (now - timedelta(hours=1)).isoformat(),
        "prize_amber_base": prize_base,
        "winning_numbers_count": 1,
        "auto_chain_enabled": False,
    }
    if catalog is not None:
        data["prize_catalog"] = catalog
    # Avoid resolve failures for fake catalog items in unit tests
    prev = ls._resolve_catalog_prize_fn
    if catalog:

        def _fake_resolve(kind, item_id):
            return {"kind": kind, "item_id": item_id, "label": item_id, "amber_price": 0}

        ls._resolve_catalog_prize_fn = _fake_resolve
    try:
        draft = ls.create_campaign_draft(db, data=data)
    finally:
        ls._resolve_catalog_prize_fn = prev
    cid = int(draft["id"])
    # Re-apply catalog with amber values (normalize may have zeroed via fake resolve)
    if catalog:
        import json as _json
        normalized = []
        for p in catalog:
            entry = {
                "kind": p.get("kind"),
                "item_id": p.get("item_id"),
                "amount": p.get("amount", 1),
                "label": p.get("label") or p.get("item_id"),
            }
            for k in ("amber_price", "amber_value", "price"):
                if p.get(k) is not None:
                    entry["amber_price"] = int(p[k])
                    break
            normalized.append(entry)
        db.execute(
            text("UPDATE lottery_campaigns SET prize_catalog_json = :j WHERE id = :id"),
            {"j": _json.dumps(normalized), "id": cid},
        )
    ls.publish_campaign(db, cid)
    db.commit()
    return cid


def test_team_lottery_confirm_allocates_two_per_member(db, lottery_ready):
    ls = lottery_ready
    cid = _make_active_campaign(db, ls)
    ts.create_team(db, steam_id=USER_A, name="LotTeam")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ts.invite_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    ts.accept_invite(db, steam_id=USER_B, team_id=tid)

    result = ts.confirm_team_lottery(db, team_id=tid, actor_steam_id=USER_A, campaign_id=cid)
    assert result["ok"] is True
    assert result["numbers_requested"] == 4
    assert result["numbers_assigned"] == 4
    assert len(result["numbers"]) == 4
    assert result["shortfall"] == 0

    # Q11: individual number can coexist
    holder = ls.team_holder_steam_id(tid)
    rows = db.execute(
        text(
            "SELECT source, steam_id FROM lottery_numbers "
            "WHERE campaign_id = :c AND status = 'ACTIVE' AND source = 'TEAM'"
        ),
        {"c": cid},
    ).fetchall()
    assert len(rows) == 4
    assert all(str(r[1]) == holder for r in rows)

    free = next(n for n in range(100, 999) if n not in result["numbers"])
    ls._insert_number(
        db, campaign_id=cid, steam_id=USER_A, number_value=free, source="AMBER_RANDOM",
    )
    db.commit()
    mine = db.execute(
        text(
            "SELECT COUNT(*) FROM lottery_numbers WHERE campaign_id = :c "
            "AND steam_id = :s AND source = 'AMBER_RANDOM'"
        ),
        {"c": cid, "s": USER_A},
    ).fetchone()
    assert int(mine[0]) == 1


def test_team_lottery_q9_numbers_stay_on_kick(db, lottery_ready):
    ls = lottery_ready
    cid = _make_active_campaign(db, ls)
    ts.create_team(db, steam_id=USER_A, name="KickLot")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ts.invite_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    ts.accept_invite(db, steam_id=USER_B, team_id=tid)
    before = ts.confirm_team_lottery(db, team_id=tid, actor_steam_id=USER_A, campaign_id=cid)
    nums_before = sorted(before["numbers"])

    ts.kick_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    after = ls.list_team_numbers(db, campaign_id=cid, team_id=tid)
    assert sorted(after) == nums_before


def test_team_lottery_join_after_confirm_allocates_two(db, lottery_ready):
    ls = lottery_ready
    cid = _make_active_campaign(db, ls)
    ts.create_team(db, steam_id=USER_A, name="JoinLot")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ts.confirm_team_lottery(db, team_id=tid, actor_steam_id=USER_A, campaign_id=cid)
    assert len(ls.list_team_numbers(db, campaign_id=cid, team_id=tid)) == 2

    ts.invite_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    ts.accept_invite(db, steam_id=USER_B, team_id=tid)
    assert len(ls.list_team_numbers(db, campaign_id=cid, team_id=tid)) == 4


def test_team_lottery_q12_shortfall_refund(db, lottery_ready):
    ls = lottery_ready
    cid = _make_active_campaign(db, ls)
    # Fill almost entire grid so only 1 free number remains
    for n in range(100, 999):  # leave 999 free
        ls._insert_number(
            db, campaign_id=cid, steam_id=USER_C, number_value=n, source="DONATION",
        )
    db.commit()

    ts.create_team(db, steam_id=USER_A, name="ShortLot")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    bank0 = ts.get_bank(db, tid)["amber_balance"]
    result = ts.confirm_team_lottery(db, team_id=tid, actor_steam_id=USER_A, campaign_id=cid)
    # Owner alone → 2 requested, only 1 free → shortfall 1 → refund 5000
    assert result["numbers_assigned"] == 1
    assert result["shortfall"] == 1
    assert result["shortfall_refunded"] == 5000
    bank1 = ts.get_bank(db, tid)["amber_balance"]
    assert bank1 == bank0 + 5000


def test_team_lottery_q10_remainder_to_bank_on_draw(db, lottery_ready, monkeypatch):
    ls = lottery_ready
    cid = _make_active_campaign(
        db, ls, prize_base=10000,
        catalog=[{"kind": "kit", "item_id": "kit_test", "amount": 1, "amber_value": 500}],
    )
    ts.create_team(db, steam_id=USER_A, name="WinLot")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ts.invite_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    ts.accept_invite(db, steam_id=USER_B, team_id=tid)
    ts.invite_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_C)
    ts.accept_invite(db, steam_id=USER_C, team_id=tid)
    conf = ts.confirm_team_lottery(db, team_id=tid, actor_steam_id=USER_A, campaign_id=cid)
    win_num = conf["numbers"][0]

    from datetime import datetime, timezone

    def _fake_draw(w_count, **kwargs):
        return [win_num], {
            "algorithm_version": "test",
            "seed_hash": "abc",
            "entropy_snapshot": "00",
            "winning_numbers_count": 1,
            "drawn_at": datetime.now(timezone.utc).isoformat(),
            "method": "test",
        }

    monkeypatch.setattr(ls, "draw_winning_numbers", _fake_draw)
    pts0 = {
        u: int(db.execute(text("SELECT points FROM players WHERE steam_id=:s"), {"s": u}).fetchone()[0])
        for u in (USER_A, USER_B, USER_C)
    }
    out = ls.run_draw(db, cid, job_id="test-team-draw")
    db.commit()
    assert out["matched_count"] == 1
    assert out["team_payouts"]
    tp = out["team_payouts"][0]
    # share = ceil(10000/1)=10000 + catalog 500 = 10500; 10500/3 = 3500 each, rem 0
    assert tp["pool"] == 10500
    assert tp["per_member"] == 3500
    assert tp["remainder_to_bank"] == 0
    assert tp["catalog_amber"] == 500
    for u in (USER_A, USER_B, USER_C):
        pts = int(db.execute(text("SELECT points FROM players WHERE steam_id=:s"), {"s": u}).fetchone()[0])
        assert pts == pts0[u] + 3500


def test_team_lottery_q10_remainder_nonzero(db, lottery_ready, monkeypatch):
    ls = lottery_ready
    cid = _make_active_campaign(db, ls, prize_base=10001, catalog=[])
    ts.create_team(db, steam_id=USER_A, name="RemLot")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ts.invite_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    ts.accept_invite(db, steam_id=USER_B, team_id=tid)
    conf = ts.confirm_team_lottery(db, team_id=tid, actor_steam_id=USER_A, campaign_id=cid)
    win_num = conf["numbers"][0]

    from datetime import datetime, timezone

    def _fake_draw(w_count, **kwargs):
        return [win_num], {
            "algorithm_version": "test",
            "seed_hash": "abc",
            "entropy_snapshot": "00",
            "winning_numbers_count": 1,
            "drawn_at": datetime.now(timezone.utc).isoformat(),
            "method": "test",
        }

    monkeypatch.setattr(ls, "draw_winning_numbers", _fake_draw)
    bank0 = ts.get_bank(db, tid)["amber_balance"]
    out = ls.run_draw(db, cid, job_id="test-rem")
    db.commit()
    tp = out["team_payouts"][0]
    # 10001 / 2 = 5000 each, rem 1 → bank
    assert tp["per_member"] == 5000
    assert tp["remainder_to_bank"] == 1
    assert ts.get_bank(db, tid)["amber_balance"] == bank0 + 1
