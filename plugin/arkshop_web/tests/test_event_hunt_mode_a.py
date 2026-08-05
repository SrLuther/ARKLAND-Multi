"""Tests críticos Mode A — claim/lock (ArkEventHunt)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import event_hunt_service as ehs
import team_service as ts

USER_A = "76561198000000001"
USER_B = "76561198000000002"
USER_C = "76561198000000003"


@pytest.fixture()
def engine(tmp_path):
    path = tmp_path / "event_hunt_test.db"
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
    ehs.ensure_event_hunt_schema(eng)
    return eng


@pytest.fixture()
def db(engine, monkeypatch):
    Session = sessionmaker(bind=engine)
    s = Session()

    def _settings():
        return {"teams_enabled": True, "event_hunt_enabled": True}

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
    ehs.configure_event_hunt_service(settings_fn=_settings)
    monkeypatch.setattr(ehs, "event_hunt_enabled", lambda settings=None: True)
    yield s
    s.close()


def _team_with_two(db):
    ts.create_team(db, steam_id=USER_A, name="Caçadores")
    tid = ts.get_active_membership(db, USER_A)["team_id"]
    ts.set_recruitment_open(db, team_id=tid, actor_steam_id=USER_A, open_=True)
    ts.invite_member(db, team_id=tid, actor_steam_id=USER_A, target_steam_id=USER_B)
    ts.accept_invite(db, steam_id=USER_B, team_id=tid)
    return tid


def _challenge(db, **kw):
    payload = {
        "display_name": "Rex Shotgun",
        "blueprint": "Blueprint'/Game/PrimalEarth/Dinos/Rex/Rex_Character_BP.Rex_Character_BP'",
        "level": 150,
        "points": 500,
        "amber_reward": 0,
        "allowed_weapons": ["tag:shotgun"],
        "enabled": True,
    }
    payload.update(kw)
    return ehs.admin_create_challenge(db, payload)


def test_one_active_claim_per_steam_id(db):
    _team_with_two(db)
    c1 = _challenge(db, display_name="Rex")
    c2 = _challenge(db, display_name="Giga", blueprint="BP_Giga")
    r1 = ehs.select_challenge(db, steam_id=USER_A, challenge_id=c1["challenge_id"])
    assert r1["claim"]["status"] == "CLAIMED"
    assert r1["claim"]["event_code"].startswith("E")
    with pytest.raises(ValueError, match="desafio activo"):
        ehs.select_challenge(db, steam_id=USER_A, challenge_id=c2["challenge_id"])
    # Other member can select in parallel (even same challenge)
    r2 = ehs.select_challenge(db, steam_id=USER_B, challenge_id=c1["challenge_id"])
    assert r2["claim"]["owner_steam_id"] == USER_B
    assert r2["claim"]["event_code"] != r1["claim"]["event_code"]


def test_steam_challenge_uniqueness_after_complete(db):
    _team_with_two(db)
    ch = _challenge(db)
    cid = ch["challenge_id"]
    claim = ehs.select_challenge(db, steam_id=USER_A, challenge_id=cid)["claim"]
    ehs.plugin_mark_spawned(db, claim["claim_id"], steam_id=USER_A, dino_id1=1, dino_id2=2)
    done = ehs.plugin_complete(
        db,
        claim["claim_id"],
        killer_steam_id=USER_A,
        killer_team_id=claim["team_id"],
        idempotency_key="complete-1",
    )
    assert done["claim"]["status"] == "COMPLETED"
    assert done["points"] == 500
    assert ehs.member_has_lock(db, USER_A, cid)
    with pytest.raises(ValueError, match="Já usaste"):
        ehs.select_challenge(db, steam_id=USER_A, challenge_id=cid)
    # Teammate still can
    ehs.select_challenge(db, steam_id=USER_B, challenge_id=cid)


def test_fail_consumes_attempt(db):
    _team_with_two(db)
    ch = _challenge(db)
    cid = ch["challenge_id"]
    claim = ehs.select_challenge(db, steam_id=USER_A, challenge_id=cid)["claim"]
    ehs.plugin_mark_spawned(db, claim["claim_id"], steam_id=USER_A)
    failed = ehs.plugin_fail(db, claim["claim_id"], reason="weapon", actor_steam_id=USER_A)
    assert failed["consumed"] is True
    assert failed["claim"]["status"] == "FAILED"
    assert ehs.member_has_lock(db, USER_A, cid)
    lock = ehs.get_member_lock(db, USER_A, cid)
    assert lock["outcome"] == "FAIL"
    with pytest.raises(ValueError, match="Já usaste"):
        ehs.select_challenge(db, steam_id=USER_A, challenge_id=cid)


def test_cancel_claimed_does_not_consume(db):
    _team_with_two(db)
    ch = _challenge(db)
    cid = ch["challenge_id"]
    claim = ehs.select_challenge(db, steam_id=USER_A, challenge_id=cid)["claim"]
    out = ehs.cancel_claim(db, steam_id=USER_A, claim_id=claim["claim_id"])
    assert out["consumed"] is False
    assert out["claim"]["status"] == "CANCELLED"
    assert not ehs.member_has_lock(db, USER_A, cid)
    # Can select again same challenge
    again = ehs.select_challenge(db, steam_id=USER_A, challenge_id=cid)
    assert again["claim"]["status"] == "CLAIMED"


def test_cancel_spawned_rejected(db):
    _team_with_two(db)
    ch = _challenge(db)
    claim = ehs.select_challenge(db, steam_id=USER_A, challenge_id=ch["challenge_id"])["claim"]
    ehs.plugin_mark_spawned(db, claim["claim_id"], steam_id=USER_A)
    with pytest.raises(ValueError, match="CLAIMED"):
        ehs.cancel_claim(db, steam_id=USER_A, claim_id=claim["claim_id"])


def test_only_owner_spawns(db):
    _team_with_two(db)
    ch = _challenge(db)
    claim = ehs.select_challenge(db, steam_id=USER_A, challenge_id=ch["challenge_id"])["claim"]
    with pytest.raises(PermissionError):
        ehs.plugin_mark_spawned(db, claim["claim_id"], steam_id=USER_B)


def test_stolen_kill_fails_and_consumes(db):
    _team_with_two(db)
    # Second team
    ts.create_team(db, steam_id=USER_C, name="Rival")
    tid_c = ts.get_active_membership(db, USER_C)["team_id"]
    ch = _challenge(db)
    claim = ehs.select_challenge(db, steam_id=USER_A, challenge_id=ch["challenge_id"])["claim"]
    ehs.plugin_mark_spawned(db, claim["claim_id"], steam_id=USER_A)
    out = ehs.plugin_complete(
        db,
        claim["claim_id"],
        killer_steam_id=USER_C,
        killer_team_id=tid_c,
        idempotency_key="stolen-1",
    )
    assert out["claim"]["status"] == "FAILED"
    assert out["claim"]["fail_reason"] == "stolen"
    assert ehs.member_has_lock(db, USER_A, ch["challenge_id"])


def test_me_summary_lock_and_scores(db):
    tid = _team_with_two(db)
    ch = _challenge(db, points=300)
    claim = ehs.select_challenge(db, steam_id=USER_A, challenge_id=ch["challenge_id"])["claim"]
    ehs.plugin_mark_spawned(db, claim["claim_id"], steam_id=USER_A)
    ehs.plugin_complete(
        db,
        claim["claim_id"],
        killer_steam_id=USER_B,
        killer_team_id=tid,
        idempotency_key="ok-1",
    )
    summary = ehs.me_summary(db, USER_A)
    assert summary["lock"]["can_select"] is True
    assert summary["my_completed_count"] == 1
    assert summary["scores_team"]["hunt_points_total"] == 300
    assert summary["scores_team"]["completed_count_team"] == 1
    assert len(summary["my_consumed"]) == 1


def test_weapon_presets_seed_and_challenge_grant_defaults(db):
    presets = ehs.list_weapon_presets(db)
    assert len(presets) >= 1
    assert presets[0]["blueprint"]
    created = ehs.admin_create_weapon_preset(
        db,
        {
            "name": "Test Pike",
            "blueprint": "Blueprint'/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponPike.PrimalItem_WeaponPike'",
            "tag": "melee",
        },
    )
    assert created["preset_id"] > 0
    _team_with_two(db)
    ch = _challenge(
        db,
        allowed_weapons=[created["blueprint"]],
        min_allowed_weapon_damage_ratio=0.9,
        forbid_torpor=True,
        official_weapons_only=True,
        grant_weapon_on_start=True,
        grant_weapon_blueprint=created["blueprint"],
        grant_weapon_qty=2,
    )
    assert ch["min_allowed_weapon_damage_ratio"] == 0.9
    assert ch["forbid_torpor"] is True
    assert ch["official_weapons_only"] is True
    assert ch["grant_weapon_on_start"] is True
    assert ch["grant_weapon_blueprint"] == created["blueprint"]
    assert ch["grant_weapon_qty"] == 2
    claim = ehs.select_challenge(db, steam_id=USER_A, challenge_id=ch["challenge_id"])["claim"]
    payload = ehs.plugin_claim_by_code(db, claim["event_code"])
    assert payload["grant_weapon_on_start"] is True
    assert payload["grant_weapon_blueprint"] == created["blueprint"]
    assert payload["min_allowed_weapon_damage_ratio"] == 0.9
