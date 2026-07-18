"""ARKLAND Modo Equipe — business logic (web-first teams).

Feature flag: settings.teams_enabled.
Q1: when teams_enabled, market split uses Equipe only (tribe split ignored).
Q2: max 1 ACTIVE team membership per player.
Q3: team XP is lifetime/cumulative; marco thresholds sum incremental xp_required.
Q4: manual kick immediate; optional Owner auto-kick by inactivity.
Q5: first foundation free; subsequent creates cost FOUNDING_FEE_AMBER (default 2500).
Q6: Owner can transfer ownership without staff.
Q7: team amber bonus % is ADDITIVE with TimedPoints license AND unlocked via milestones
    (staff sets amber_bonus_pp per marco; soft-capped by teams_amber_bonus_cap).
Q9: kick/leave after lottery confirm — team numbers STAY with the team.
Q10: prize division remainder → team bank (amber).
Q11: individual + team numbers allowed in same campaign.
Q12: shortfall refund teams_lottery_shortfall_refund (default 5000) Â per missing number.
Q13: max MAX_SPECIAL_ROLES (2) special roles per member (OWNER excluded from cap).
Q14: lottery confirm + split config = Owner only (Guardian cannot).
Q16: milestone trail cursor per team (milestone_index).

Tables: teams, team_members, team_roles, team_bank, team_bank_ledger,
team_milestones, team_milestone_progress, team_xp_events, player_xp_lifetime,
team_splits, team_split_members, team_lottery_confirmations.
"""
from __future__ import annotations

import json
import logging
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

log = logging.getLogger("arkshop_web.team")

# ── Constants ────────────────────────────────────────────────
TEAM_NAME_MIN = 3
TEAM_NAME_MAX = 32
TEAM_TAG_MAX = 5
DEFAULT_MAX_MEMBERS = 5  # base product cap; marcos podem subir via max_members_unlock
DEFAULT_AMBER_BONUS_PP = 2  # default amber_bonus_pp when marco field empty
DEFAULT_AMBER_BONUS_CAP = 20
# Q5: first foundation free; every subsequent create (after prior founder history) costs this
FOUNDING_FEE_AMBER = 2500
# Q12: Â refunded to team bank per lottery number that could not be allocated
LOTTERY_SHORTFALL_REFUND_AMBER = 5000
LOTTERY_NUMBERS_PER_MEMBER = 2
# Q13: special flavor roles (not OWNER) — max 2 per member (incl. owner)
MAX_SPECIAL_ROLES = 2
SPLIT_MIN_SALE_AMBER = 1_000
SPLIT_GAP_MIN_PP = 10
SPLIT_DEFAULT_SENDER_PCT = 60
SPLIT_DEFAULT_POOL_PCT = 40
INVITE_CODE_LEN = 8
RENAME_COOLDOWN_DAYS = 7
DEFAULT_AUTO_KICK_INACTIVE = False
DEFAULT_AUTO_KICK_HOURS = 168  # 7 days
AUTO_KICK_HOURS_MIN = 24
AUTO_KICK_HOURS_MAX = 720  # 30 days

TEAM_STATUSES = frozenset({"ACTIVE", "DISBANDED", "SUSPENDED"})
MEMBER_STATUSES = frozenset({
    "ACTIVE", "INVITED", "PENDING", "KICKED", "LEFT", "DECLINED", "REJECTED",
})
MILESTONE_STATUSES = frozenset({"DRAFT", "ACTIVE", "COMPLETED", "RETIRED"})

# Flavor role keys (Q15). OWNER is unique (permission); special roles max 2 (Q13).
ROLE_OWNER = "OWNER"
ROLE_GUARDIAN = "GUARDIAN"          # Guardião
ROLE_HERALD = "HERALD"              # Arauto
ROLE_TREASURER = "TREASURER"        # Guardião do Cofre
ROLE_ENGINEER = "ENGINEER"          # Engenheiro de Marcos
ROLE_AMBASSADOR = "AMBASSADOR"      # Embaixador
ROLE_ARCHIVIST = "ARCHIVIST"        # Arquivista

ASSIGNABLE_ROLES = frozenset({
    ROLE_GUARDIAN, ROLE_HERALD, ROLE_TREASURER,
    ROLE_ENGINEER, ROLE_AMBASSADOR, ROLE_ARCHIVIST,
})

ROLE_LABELS_PT = {
    ROLE_OWNER: "Proprietário",
    ROLE_GUARDIAN: "Guardião",
    ROLE_HERALD: "Arauto",
    ROLE_TREASURER: "Guardião do Cofre",
    ROLE_ENGINEER: "Engenheiro de Marcos",
    ROLE_AMBASSADOR: "Embaixador",
    ROLE_ARCHIVIST: "Arquivista",
}

# Curated warehouse catalog (~10 rares). shop_key aligns with CustomShop rec_* when present.
# /marco (CustomShop) accepts ALL of these into the team warehouse.
TEAM_WAREHOUSE_RESOURCES: tuple[dict[str, Any], ...] = (
    {
        "key": "element_ore",
        "label_pt": "Minério de Elemento",
        "shop_key": "rec_elementore",
        "blueprint": "/Game/Aberration/CoreBlueprints/Resources/PrimalItemResource_ElementOre.PrimalItemResource_ElementOre",
        "default_qty": 500,
    },
    {
        "key": "black_pearl",
        "label_pt": "Pérola Negra",
        "shop_key": "rec_pnegra",
        "blueprint": "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_BlackPearl.PrimalItemResource_BlackPearl",
        "default_qty": 200,
    },
    {
        "key": "hard_polymer",
        "label_pt": "Polímero Duro",
        "shop_key": "rec_polymer",
        "blueprint": "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Polymer.PrimalItemResource_Polymer",
        "default_qty": 300,
    },
    {
        "key": "sand",
        "label_pt": "Areia",
        "shop_key": "rec_sand",
        "blueprint": "/Game/ScorchedEarth/CoreBlueprints/Resources/PrimalItemResource_Sand.PrimalItemResource_Sand",
        "default_qty": 1000,
    },
    {
        "key": "substrate_absorbent",
        "label_pt": "Substrato Absorvente",
        "shop_key": "",
        "blueprint": "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_SubstrateAbsorbent.PrimalItemResource_SubstrateAbsorbent",
        "default_qty": 150,
    },
    {
        "key": "silica_pearls",
        "label_pt": "Pérolas de Sílica",
        "shop_key": "rec_silicon",
        "blueprint": "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Silicon.PrimalItemResource_Silicon",
        "default_qty": 400,
    },
    {
        "key": "deathworm_horn",
        "label_pt": "Chifre de Deathworm",
        "shop_key": "",
        "blueprint": "/Game/ScorchedEarth/Dinos/Deathworm/PrimalItemResource_KeratinSpike.PrimalItemResource_KeratinSpike",
        "default_qty": 50,
    },
    {
        "key": "organic_polymer",
        "label_pt": "Polímero Orgânico",
        "shop_key": "rec_organicpolymer",
        "blueprint": "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Polymer_Organic.PrimalItemResource_Polymer_Organic",
        "default_qty": 250,
    },
    {
        "key": "ammonite_bile",
        "label_pt": "Bílis de Amonite",
        "shop_key": "",
        "blueprint": "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_AmmoniteBlood.PrimalItemResource_AmmoniteBlood",
        "default_qty": 100,
    },
    {
        "key": "element_dust",
        "label_pt": "Pó de Elemento",
        "shop_key": "",
        "blueprint": "/Game/Extinction/CoreBlueprints/Resources/PrimalItemResource_ElementDust.PrimalItemResource_ElementDust",
        "default_qty": 500,
    },
)

TEAM_WAREHOUSE_KEYS = frozenset(r["key"] for r in TEAM_WAREHOUSE_RESOURCES)
_WAREHOUSE_BY_KEY = {r["key"]: r for r in TEAM_WAREHOUSE_RESOURCES}
# Accept shop aliases (rec_*) and legacy freeform → canonical catalog key
_WAREHOUSE_ALIASES: dict[str, str] = {}
for _r in TEAM_WAREHOUSE_RESOURCES:
    _WAREHOUSE_ALIASES[_r["key"]] = _r["key"]
    if _r.get("shop_key"):
        _WAREHOUSE_ALIASES[str(_r["shop_key"])] = _r["key"]
# Legacy catalog key (replaced by substrate_absorbent)
_WAREHOUSE_ALIASES["absorbent_polymer"] = "substrate_absorbent"
_WAREHOUSE_ALIASES["polimero_absorvente"] = "substrate_absorbent"

# Permissions: Q14 — Guardian can approve/kick/invite; sorteio+split = Owner only
_PERMS = {
    "rename": {ROLE_OWNER},
    "transfer_ownership": {ROLE_OWNER},
    "kick": {ROLE_OWNER, ROLE_GUARDIAN},
    "invite": {ROLE_OWNER, ROLE_GUARDIAN, ROLE_HERALD},
    "approve_join": {ROLE_OWNER, ROLE_GUARDIAN, ROLE_HERALD},
    "assign_roles": {ROLE_OWNER, ROLE_GUARDIAN},
    "split_config": {ROLE_OWNER},
    "lottery_confirm": {ROLE_OWNER},
    "bank_ledger": {ROLE_OWNER, ROLE_GUARDIAN, ROLE_TREASURER, ROLE_ENGINEER},
    "milestone_commit": {ROLE_OWNER, ROLE_TREASURER},
    "recruitment_toggle": {ROLE_OWNER, ROLE_GUARDIAN, ROLE_AMBASSADOR},
    "mural": {ROLE_OWNER, ROLE_AMBASSADOR, ROLE_ARCHIVIST},
    "team_settings": {ROLE_OWNER},
}


def warehouse_catalog() -> list[dict[str, Any]]:
    """Public/admin view of the fixed rare-resource catalog."""
    return [dict(r) for r in TEAM_WAREHOUSE_RESOURCES]


def normalize_warehouse_key(resource_key: str) -> str:
    """Map catalog key or shop alias → canonical key. Raises ValueError if unknown."""
    raw = str(resource_key or "").strip()
    if not raw:
        raise ValueError("resource_key obrigatório.")
    key = _WAREHOUSE_ALIASES.get(raw) or _WAREHOUSE_ALIASES.get(raw.lower())
    if not key:
        raise ValueError(
            f"Recurso fora do catálogo do armazém: {raw}. "
            f"Permitidos: {', '.join(sorted(TEAM_WAREHOUSE_KEYS))}."
        )
    return key


def _migrate_warehouse_resource_map(resources: dict[str, Any] | None) -> dict[str, int]:
    """Normalize legacy keys in stored bank/committed maps (e.g. absorbent_polymer)."""
    out: dict[str, int] = {}
    for raw_key, raw_qty in (resources or {}).items():
        try:
            key = normalize_warehouse_key(str(raw_key))
        except ValueError:
            continue
        qty = int(raw_qty or 0)
        if qty <= 0:
            continue
        out[key] = int(out.get(key) or 0) + qty
    return out


def validate_milestone_resources(resources: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Normalize admin milestone resource list to [{key, quantity, label_pt}]."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for req in resources or []:
        if not isinstance(req, dict):
            raise ValueError("Cada requisito de recurso deve ser um objeto {key, quantity}.")
        raw_key = req.get("key") or req.get("blueprint_or_key") or req.get("resource_key") or ""
        key = normalize_warehouse_key(str(raw_key))
        if key in seen:
            raise ValueError(f"Recurso duplicado no marco: {key}")
        seen.add(key)
        qty = int(req.get("quantity") or 0)
        if qty < 0:
            raise ValueError("quantity deve ser >= 0")
        if qty == 0:
            continue
        meta = _WAREHOUSE_BY_KEY[key]
        out.append({"key": key, "quantity": qty, "label_pt": meta["label_pt"]})
    return out


def default_milestone_resource_suggestions() -> list[dict[str, Any]]:
    """Optional system defaults for admin milestone editor."""
    return [
        {"key": r["key"], "quantity": int(r["default_qty"]), "label_pt": r["label_pt"]}
        for r in TEAM_WAREHOUSE_RESOURCES
    ]

_settings_fn: Callable[[], dict[str, Any]] | None = None
_subtract_points_tx: Callable[[Session, str, int], int] | None = None


def configure_team_service(
    *,
    settings_fn: Callable[[], dict[str, Any]] | None = None,
    subtract_points_tx: Callable[[Session, str, int], int] | None = None,
) -> None:
    global _settings_fn, _subtract_points_tx
    if settings_fn is not None:
        _settings_fn = settings_fn
    if subtract_points_tx is not None:
        _subtract_points_tx = subtract_points_tx


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _naive(dt: datetime | None = None) -> datetime:
    d = dt or _utcnow()
    if d.tzinfo is None:
        return d
    return d.astimezone(timezone.utc).replace(tzinfo=None)


def _load_settings() -> dict[str, Any]:
    if _settings_fn:
        try:
            return dict(_settings_fn() or {})
        except Exception:
            return {}
    return {}


def teams_enabled(settings: dict[str, Any] | None = None) -> bool:
    """Product default: Equipes on when the key is absent (Tribos saíram da web)."""
    s = settings if settings is not None else _load_settings()
    if "teams_enabled" not in s:
        return True
    return bool(s.get("teams_enabled"))


def default_max_members(settings: dict[str, Any] | None = None) -> int:
    s = settings if settings is not None else _load_settings()
    try:
        raw = s.get("teams_max_members")
        if raw is None or raw == "":
            return DEFAULT_MAX_MEMBERS
        return max(2, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_MAX_MEMBERS


def team_accepting_members(team: dict[str, Any], member_count: int) -> bool:
    """Recruiting gate for directory / join: flag open AND seats available."""
    try:
        max_m = int(team.get("max_members") or DEFAULT_MAX_MEMBERS)
    except (TypeError, ValueError):
        max_m = DEFAULT_MAX_MEMBERS
    return bool(team.get("recruitment_open")) and int(member_count) < max_m


def amber_bonus_pp_per_milestone(settings: dict[str, Any] | None = None) -> int:
    """Default pp when a marco's amber_bonus_pp field is empty (Q7)."""
    s = settings if settings is not None else _load_settings()
    try:
        return max(0, int(s.get("teams_amber_bonus_pp") or DEFAULT_AMBER_BONUS_PP))
    except (TypeError, ValueError):
        return DEFAULT_AMBER_BONUS_PP


def amber_bonus_cap(settings: dict[str, Any] | None = None) -> int:
    s = settings if settings is not None else _load_settings()
    try:
        return max(0, int(s.get("teams_amber_bonus_cap") or DEFAULT_AMBER_BONUS_CAP))
    except (TypeError, ValueError):
        return DEFAULT_AMBER_BONUS_CAP


def lottery_shortfall_refund_amber(settings: dict[str, Any] | None = None) -> int:
    """Q12: Â per missing team lottery number reimbursed to team bank."""
    s = settings if settings is not None else _load_settings()
    try:
        raw = s.get("teams_lottery_shortfall_refund")
        if raw is None or raw == "":
            return LOTTERY_SHORTFALL_REFUND_AMBER
        return max(0, int(raw))
    except (TypeError, ValueError):
        return LOTTERY_SHORTFALL_REFUND_AMBER


def sum_milestone_amber_bonus_pp(
    db: Session,
    up_to_milestone_index: int,
    settings: dict[str, Any] | None = None,
) -> int:
    """Sum amber_bonus_pp for marcos 1..N (Q7 — bonus unlocked via milestone trail)."""
    idx = int(up_to_milestone_index)
    if idx <= 0:
        return 0
    default_pp = amber_bonus_pp_per_milestone(settings)
    try:
        rows = db.execute(
            text("""
                SELECT milestone_index, amber_bonus_pp FROM team_milestones
                WHERE milestone_index >= 1 AND milestone_index <= :i
                  AND status IN ('ACTIVE', 'COMPLETED', 'RETIRED')
                ORDER BY milestone_index
            """),
            {"i": idx},
        ).fetchall()
    except Exception:
        # Column may be missing on very old DBs mid-migrate — fall back to flat formula
        return idx * default_pp
    by_idx = {int(r[0]): r[1] for r in rows}
    total = 0
    for i in range(1, idx + 1):
        if i not in by_idx:
            # Missing definition for a completed cursor step — use default
            total += default_pp
            continue
        raw = by_idx[i]
        if raw is None:
            total += default_pp
        else:
            try:
                total += max(0, int(raw))
            except (TypeError, ValueError):
                total += default_pp
    return total


def team_amber_bonus_pct(
    milestone_index: int,
    settings: dict[str, Any] | None = None,
    *,
    db: Session | None = None,
) -> int:
    """Team amber bonus % (Q7): ADDITIVE with TimedPoints license; unlocked via marcos.

    With db: sum of each marco's amber_bonus_pp for 1..milestone_index (default pp if empty).
    Without db: legacy flat formula milestone_index * teams_amber_bonus_pp.
    Soft-capped via teams_amber_bonus_cap. C++ TimedPoints may apply later; web exposes %.
    """
    cap = amber_bonus_cap(settings)
    if db is not None:
        pp_sum = sum_milestone_amber_bonus_pp(db, int(milestone_index), settings)
        return min(cap, max(0, pp_sum))
    pp = amber_bonus_pp_per_milestone(settings)
    return min(cap, max(0, int(milestone_index)) * pp)


def founding_fee_amber(settings: dict[str, Any] | None = None) -> int:
    """Âmbares charged on create when player already founded before (Q5)."""
    s = settings if settings is not None else _load_settings()
    try:
        raw = s.get("teams_founding_fee")
        if raw is None or raw == "":
            return FOUNDING_FEE_AMBER
        return max(0, int(raw))
    except (TypeError, ValueError):
        return FOUNDING_FEE_AMBER


def count_teams_founded(db: Session, steam_id: str) -> int:
    """How many teams this steam_id has ever founded (any status)."""
    row = db.execute(
        text("SELECT COUNT(*) FROM teams WHERE founder_steam_id = :sid"),
        {"sid": str(steam_id).strip()},
    ).fetchone()
    return int(row[0] or 0) if row else 0


def founding_fee_for_player(db: Session, steam_id: str, settings: dict[str, Any] | None = None) -> int:
    """0 on first-ever create; FOUNDING_FEE (default 2500) if count_teams_founded >= 1."""
    if count_teams_founded(db, steam_id) >= 1:
        return founding_fee_amber(settings)
    return 0


# ── Schema ───────────────────────────────────────────────────

def ensure_team_schema(engine: Engine) -> None:
    """Idempotent CREATE TABLE for teams (SQLite + MySQL)."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "BIGINT AUTO_INCREMENT PRIMARY KEY"
    now_col = "DATETIME" if is_sqlite else "DATETIME(6)"
    tiny = "INTEGER" if is_sqlite else "TINYINT(1)"
    eng = "" if is_sqlite else " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"

    ddls = [
        f"""
        CREATE TABLE IF NOT EXISTS teams (
          id                {pk},
          name              VARCHAR(64) NOT NULL,
          name_norm         VARCHAR(64) NOT NULL,
          tag               VARCHAR(8) NOT NULL DEFAULT '',
          founder_steam_id  VARCHAR(32) NOT NULL,
          owner_steam_id    VARCHAR(32) NOT NULL,
          status            VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
          max_members       INTEGER NOT NULL DEFAULT {DEFAULT_MAX_MEMBERS},
          milestone_index   INTEGER NOT NULL DEFAULT 0,
          team_xp           INTEGER NOT NULL DEFAULT 0,
          team_xp_lifetime  INTEGER NOT NULL DEFAULT 0,
          bank_mode         VARCHAR(32) NOT NULL DEFAULT 'closed',
          recruitment_open  {tiny} NOT NULL DEFAULT 0,
          represents_tribe  {tiny} NOT NULL DEFAULT 0,
          auto_kick_inactive {tiny} NOT NULL DEFAULT 0,
          auto_kick_inactive_hours INTEGER NOT NULL DEFAULT {DEFAULT_AUTO_KICK_HOURS},
          mural_text        TEXT,
          renamed_at        {now_col},
          created_at        {now_col} NOT NULL,
          updated_at        {now_col} NOT NULL,
          UNIQUE {"(name_norm)" if is_sqlite else "KEY uq_team_name (name_norm)"}
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS team_members (
          id              {pk},
          team_id         INTEGER NOT NULL,
          steam_id        VARCHAR(32) NOT NULL,
          display_name    VARCHAR(128) NOT NULL DEFAULT '',
          status          VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
          invite_code     VARCHAR(32),
          joined_at       {now_col},
          left_at         {now_col},
          last_activity_at {now_col},
          created_at      {now_col} NOT NULL,
          updated_at      {now_col} NOT NULL,
          UNIQUE {"(team_id, steam_id)" if is_sqlite else "KEY uq_team_member (team_id, steam_id)"}
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS team_roles (
          id         {pk},
          team_id    INTEGER NOT NULL,
          steam_id   VARCHAR(32) NOT NULL,
          role_key   VARCHAR(32) NOT NULL,
          assigned_at {now_col} NOT NULL,
          assigned_by VARCHAR(32) NOT NULL DEFAULT '',
          UNIQUE {"(team_id, steam_id, role_key)" if is_sqlite else "KEY uq_team_role (team_id, steam_id, role_key)"}
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS team_bank (
          team_id         INTEGER NOT NULL PRIMARY KEY,
          amber_balance   INTEGER NOT NULL DEFAULT 0,
          resources_json  TEXT NOT NULL,
          committed_json  TEXT NOT NULL DEFAULT '{{}}',
          updated_at      {now_col} NOT NULL
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS team_bank_ledger (
          id              {pk},
          team_id         INTEGER NOT NULL,
          entry_type      VARCHAR(32) NOT NULL,
          asset_kind      VARCHAR(16) NOT NULL,
          asset_key       VARCHAR(128) NOT NULL DEFAULT 'amber',
          amount          INTEGER NOT NULL,
          balance_after   INTEGER NOT NULL DEFAULT 0,
          actor_steam_id  VARCHAR(32) NOT NULL DEFAULT '',
          idempotency_key VARCHAR(128),
          note            VARCHAR(255) NOT NULL DEFAULT '',
          meta_json       TEXT,
          created_at      {now_col} NOT NULL,
          UNIQUE {"(idempotency_key)" if is_sqlite else "KEY uq_team_ledger_idem (idempotency_key)"}
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS team_milestones (
          id              {pk},
          milestone_index INTEGER NOT NULL,
          title           VARCHAR(128) NOT NULL DEFAULT '',
          description     TEXT,
          amber_required  INTEGER NOT NULL DEFAULT 0,
          xp_required     INTEGER NOT NULL DEFAULT 0,
          resources_json  TEXT NOT NULL,
          max_members_unlock INTEGER,
          amber_bonus_pp  INTEGER,
          status          VARCHAR(16) NOT NULL DEFAULT 'DRAFT',
          created_at      {now_col} NOT NULL,
          updated_at      {now_col} NOT NULL,
          UNIQUE {"(milestone_index)" if is_sqlite else "KEY uq_milestone_idx (milestone_index)"}
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS team_milestone_progress (
          id              {pk},
          team_id         INTEGER NOT NULL,
          milestone_index INTEGER NOT NULL,
          status          VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
          completed_at    {now_col},
          meta_json       TEXT,
          created_at      {now_col} NOT NULL,
          updated_at      {now_col} NOT NULL,
          UNIQUE {"(team_id, milestone_index)" if is_sqlite else "KEY uq_team_ms (team_id, milestone_index)"}
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS team_xp_events (
          id          {pk},
          created_at  {now_col} NOT NULL,
          team_id     INTEGER NOT NULL,
          steam_id    VARCHAR(32) NOT NULL,
          amount      INTEGER NOT NULL,
          map_id      VARCHAR(64) NOT NULL,
          cycle_key   VARCHAR(64) NOT NULL,
          UNIQUE {"(team_id, steam_id, map_id, cycle_key, amount)" if is_sqlite else "KEY uq_team_xp (team_id, steam_id, map_id, cycle_key, amount)"}
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS player_xp_lifetime (
          steam_id    VARCHAR(32) NOT NULL PRIMARY KEY,
          xp          INTEGER NOT NULL DEFAULT 0,
          updated_at  {now_col} NOT NULL
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS team_splits (
          id             {pk},
          team_id        INTEGER NOT NULL,
          status         VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
          sender_pct     INTEGER NOT NULL DEFAULT {SPLIT_DEFAULT_SENDER_PCT},
          pool_pct       INTEGER NOT NULL DEFAULT {SPLIT_DEFAULT_POOL_PCT},
          created_at     {now_col} NOT NULL,
          updated_at     {now_col} NOT NULL,
          updated_by     VARCHAR(32)
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS team_split_members (
          id           {pk},
          split_id     INTEGER NOT NULL,
          steam_id     VARCHAR(32) NOT NULL,
          display_name VARCHAR(128),
          percentage   INTEGER NOT NULL DEFAULT 0,
          is_seller    {tiny} NOT NULL DEFAULT 0,
          opted_out    {tiny} NOT NULL DEFAULT 0,
          opted_out_at {now_col},
          added_at     {now_col} NOT NULL,
          UNIQUE {"(split_id, steam_id)" if is_sqlite else "KEY uq_team_split_m (split_id, steam_id)"}
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS team_lottery_confirmations (
          campaign_id INTEGER NOT NULL,
          team_id INTEGER NOT NULL,
          confirmed_by VARCHAR(32) NOT NULL,
          confirmed_at {now_col} NOT NULL,
          numbers_requested INTEGER NOT NULL DEFAULT 0,
          numbers_assigned INTEGER NOT NULL DEFAULT 0,
          shortfall_refunded INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY (campaign_id, team_id)
        ){eng}
        """,
    ]

    with engine.connect() as conn:
        for ddl in ddls:
            try:
                conn.execute(text(ddl))
            except Exception as exc:
                log.warning("team_schema DDL partial: %s", exc)
        for idx_sql in (
            "CREATE INDEX IF NOT EXISTS ix_team_members_steam ON team_members (steam_id)",
            "CREATE INDEX IF NOT EXISTS ix_team_members_status ON team_members (team_id, status)",
            "CREATE INDEX IF NOT EXISTS ix_team_bank_ledger_team ON team_bank_ledger (team_id, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_player_xp_lifetime_xp ON player_xp_lifetime (xp DESC)",
            "CREATE INDEX IF NOT EXISTS ix_teams_rank ON teams (milestone_index DESC, team_xp_lifetime DESC)",
        ):
            try:
                conn.execute(text(idx_sql))
            except Exception as exc:
                log.debug("team_schema index: %s", exc)
        # Reuse market_listings.split_snapshot for team splits (kind in JSON).
        _add_col_if_missing(conn, is_sqlite, "market_listings", "team_split_id", "INTEGER")
        _add_col_if_missing(conn, is_sqlite, "team_bank", "committed_json", "TEXT")
        _add_col_if_missing(conn, is_sqlite, "teams", "auto_kick_inactive", tiny)
        _add_col_if_missing(
            conn, is_sqlite, "teams", "auto_kick_inactive_hours",
            f"INTEGER NOT NULL DEFAULT {DEFAULT_AUTO_KICK_HOURS}",
        )
        _add_col_if_missing(conn, is_sqlite, "team_members", "last_activity_at", now_col)
        _add_col_if_missing(conn, is_sqlite, "team_milestones", "amber_bonus_pp", "INTEGER")
        conn.commit()
    log.info("team_schema: tables verified/created")


def _add_col_if_missing(conn: Any, is_sqlite: bool, table: str, col: str, col_type: str) -> None:
    try:
        if is_sqlite:
            cols = [r[1] for r in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()]
            if col not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
        else:
            row = conn.execute(text(f"SHOW COLUMNS FROM `{table}` LIKE '{col}'")).fetchone()
            if row is None:
                conn.execute(text(f"ALTER TABLE `{table}` ADD COLUMN `{col}` {col_type}"))
    except Exception as exc:
        log.debug("team_schema alter %s.%s: %s", table, col, exc)


# ── Helpers ──────────────────────────────────────────────────

def _norm_name(name: str) -> str:
    return " ".join(str(name or "").strip().lower().split())


def validate_team_name(name: str) -> str:
    name = " ".join(str(name or "").strip().split())
    if len(name) < TEAM_NAME_MIN or len(name) > TEAM_NAME_MAX:
        raise ValueError(f"Nome deve ter entre {TEAM_NAME_MIN} e {TEAM_NAME_MAX} caracteres.")
    return name


def _gen_invite_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(INVITE_CODE_LEN))


def _require_enabled() -> None:
    if not teams_enabled():
        raise PermissionError("Modo Equipe desativado (teams_enabled=false).")


def _usable_player_nick(name: str | None, steam_id: str) -> str | None:
    """Nick de jogador utilizável — rejeita vazio ou cópia do SteamID64."""
    nick = str(name or "").strip()
    sid = str(steam_id or "").strip()
    if not nick or not sid or nick == sid:
        return None
    return nick[:128]


def _nicks_from_store_users(db: Session, steam_ids: list[str]) -> dict[str, str]:
    """Resolve nicks via store_users (steam_persona → display_name), como mercado/admin."""
    unique = list(dict.fromkeys(str(s).strip() for s in steam_ids if str(s or "").strip()))
    if not unique:
        return {}
    out: dict[str, str] = {}
    try:
        ph = ", ".join(f":id{i}" for i in range(len(unique)))
        params = {f"id{i}": sid for i, sid in enumerate(unique)}
        rows = db.execute(
            text(
                f"SELECT steam_id, steam_persona, display_name "
                f"FROM store_users WHERE steam_id IN ({ph})"
            ),
            params,
        ).fetchall()
    except Exception:
        return {}
    for row in rows:
        sid = str(row[0])
        for col in (row[1], row[2]):
            nick = _usable_player_nick(col, sid)
            if nick:
                out[sid] = nick
                break
    return out


def resolve_member_display_name(
    db: Session,
    steam_id: str,
    stored: str = "",
    *,
    nick_cache: dict[str, str] | None = None,
) -> str:
    """Nome para UI: store_users nick, senão display_name gravado (se ≠ SteamID), senão SteamID."""
    sid = str(steam_id or "").strip()
    if not sid:
        return ""
    if nick_cache is not None and sid in nick_cache:
        return nick_cache[sid]
    nicks = nick_cache if nick_cache is not None else _nicks_from_store_users(db, [sid])
    resolved = nicks.get(sid) or _usable_player_nick(stored, sid) or sid
    if nick_cache is not None:
        nick_cache[sid] = resolved
    return resolved


def get_active_membership(db: Session, steam_id: str) -> dict[str, Any] | None:
    row = db.execute(
        text("""
            SELECT m.id, m.team_id, m.steam_id, m.display_name, m.status, m.joined_at,
                   t.name, t.owner_steam_id, t.status AS team_status
            FROM team_members m
            JOIN teams t ON t.id = m.team_id
            WHERE m.steam_id = :sid AND m.status = 'ACTIVE' AND t.status = 'ACTIVE'
            LIMIT 1
        """),
        {"sid": str(steam_id)},
    ).fetchone()
    if not row:
        return None
    sid = str(row[2])
    return {
        "member_id": row[0],
        "team_id": row[1],
        "steam_id": sid,
        "display_name": resolve_member_display_name(db, sid, str(row[3] or "")),
        "status": row[4],
        "joined_at": str(row[5]) if row[5] else None,
        "team_name": row[6],
        "owner_steam_id": row[7],
        "team_status": row[8],
    }


def _member_roles(db: Session, team_id: int, steam_id: str) -> list[str]:
    team = get_team(db, team_id)
    roles: list[str] = []
    if team and team["owner_steam_id"] == str(steam_id):
        roles.append(ROLE_OWNER)
    rows = db.execute(
        text("SELECT role_key FROM team_roles WHERE team_id = :tid AND steam_id = :sid"),
        {"tid": team_id, "sid": str(steam_id)},
    ).fetchall()
    for r in rows:
        rk = str(r[0])
        if rk not in roles:
            roles.append(rk)
    return roles


def member_can(db: Session, team_id: int, steam_id: str, action: str) -> bool:
    allowed = _PERMS.get(action)
    if not allowed:
        return False
    roles = set(_member_roles(db, team_id, steam_id))
    return bool(roles & allowed)


def _assert_can(db: Session, team_id: int, steam_id: str, action: str) -> None:
    if not member_can(db, team_id, steam_id, action):
        raise PermissionError("Sem permissão para esta ação.")


def count_active_members(db: Session, team_id: int) -> int:
    row = db.execute(
        text("SELECT COUNT(*) FROM team_members WHERE team_id = :tid AND status = 'ACTIVE'"),
        {"tid": team_id},
    ).fetchone()
    return int(row[0] or 0) if row else 0


_TEAM_COLS = """
            id, name, tag, founder_steam_id, owner_steam_id, status,
            max_members, milestone_index, team_xp, team_xp_lifetime,
            bank_mode, recruitment_open, represents_tribe, mural_text,
            renamed_at, created_at, updated_at,
            auto_kick_inactive, auto_kick_inactive_hours
"""


def get_team(db: Session, team_id: int) -> dict[str, Any] | None:
    row = db.execute(
        text(f"SELECT {_TEAM_COLS} FROM teams WHERE id = :id"),
        {"id": int(team_id)},
    ).fetchone()
    if not row:
        return None
    return _team_row(row, db=db)


def _team_row(row: Any, *, db: Session | None = None) -> dict[str, Any]:
    lifetime = int(row[9] or 0)
    auto_kick = bool(row[17]) if len(row) > 17 else False
    try:
        auto_hours = int(row[18]) if len(row) > 18 and row[18] is not None else DEFAULT_AUTO_KICK_HOURS
    except (TypeError, ValueError):
        auto_hours = DEFAULT_AUTO_KICK_HOURS
    mi = int(row[7] or 0)
    return {
        "id": int(row[0]),
        "name": row[1],
        "tag": row[2] or "",
        "founder_steam_id": row[3],
        "owner_steam_id": row[4],
        "status": row[5],
        "max_members": int(row[6] or DEFAULT_MAX_MEMBERS),
        "milestone_index": mi,
        "team_xp": int(row[8] or 0),
        "team_xp_lifetime": lifetime,
        "team_honor": lifetime,
        "bank_mode": row[10] or "closed",
        "recruitment_open": bool(row[11]),
        "represents_tribe": bool(row[12]),
        "mural_text": row[13] or "",
        "renamed_at": str(row[14]) if row[14] else None,
        "created_at": str(row[15]) if row[15] else None,
        "updated_at": str(row[16]) if row[16] else None,
        "auto_kick_inactive": auto_kick,
        "auto_kick_inactive_hours": max(AUTO_KICK_HOURS_MIN, min(AUTO_KICK_HOURS_MAX, auto_hours)),
        "amber_bonus_pct": team_amber_bonus_pct(mi, db=db),
    }


def list_members(db: Session, team_id: int, *, statuses: list[str] | None = None) -> list[dict[str, Any]]:
    if statuses:
        ph = ", ".join(f":s{i}" for i in range(len(statuses)))
        params: dict[str, Any] = {"tid": team_id}
        for i, st in enumerate(statuses):
            params[f"s{i}"] = st
        rows = db.execute(
            text(f"""
                SELECT id, steam_id, display_name, status, invite_code, joined_at, created_at,
                       last_activity_at
                FROM team_members WHERE team_id = :tid AND status IN ({ph})
                ORDER BY joined_at IS NULL, joined_at, id
            """),
            params,
        ).fetchall()
    else:
        rows = db.execute(
            text("""
                SELECT id, steam_id, display_name, status, invite_code, joined_at, created_at,
                       last_activity_at
                FROM team_members WHERE team_id = :tid
                ORDER BY CASE status WHEN 'ACTIVE' THEN 0 WHEN 'INVITED' THEN 1
                         WHEN 'PENDING' THEN 2 ELSE 3 END, joined_at, id
            """),
            {"tid": team_id},
        ).fetchall()
    steam_ids = [str(r[1]) for r in rows]
    nick_cache = _nicks_from_store_users(db, steam_ids)
    out = []
    for r in rows:
        sid = str(r[1])
        roles = _member_roles(db, team_id, sid) if r[3] == "ACTIVE" else []
        out.append({
            "id": int(r[0]),
            "steam_id": sid,
            "display_name": resolve_member_display_name(
                db, sid, str(r[2] or ""), nick_cache=nick_cache
            ),
            "status": r[3],
            "invite_code": r[4],
            "joined_at": str(r[5]) if r[5] else None,
            "created_at": str(r[6]) if r[6] else None,
            "last_activity_at": str(r[7]) if len(r) > 7 and r[7] else None,
            "roles": roles,
            "role_labels": [ROLE_LABELS_PT.get(x, x) for x in roles],
        })
    return out


def team_public_view(db: Session, team_id: int, *, viewer_steam_id: str | None = None) -> dict[str, Any]:
    team = get_team(db, team_id)
    if not team:
        raise ValueError("Equipe não encontrada.")
    members = list_members(db, team_id, statuses=["ACTIVE"])
    member_count = len(members)
    bank = get_bank(db, team_id)
    ms = get_current_milestone_for_team(db, team)
    progress = milestone_progress_view(db, team, ms) if ms else None
    viewer_roles: list[str] = []
    if viewer_steam_id:
        mem = get_active_membership(db, viewer_steam_id)
        if mem and mem["team_id"] == team_id:
            viewer_roles = _member_roles(db, team_id, viewer_steam_id)
    accepting = team_accepting_members(team, member_count)
    owner_row = next((m for m in members if m["steam_id"] == team["owner_steam_id"]), None)
    return {
        "team": team,
        "members": members,
        "member_count": member_count,
        "max_members": int(team["max_members"]),
        "recruitment_open": bool(team["recruitment_open"]),
        "accepting_members": accepting,
        "recruiting_open": accepting,  # alias for directory UI
        "owner_display_name": (owner_row or {}).get("display_name") or team["owner_steam_id"],
        "bank": {
            "amber_balance": bank["amber_balance"],
            "resources": bank["resources"],
            "committed": bank.get("committed") or {},
            "warehouse": bank["resources"],
        },
        "milestone": progress,
        "viewer_roles": viewer_roles,
        "split": get_active_team_split(db, team_id),
        "lottery": get_team_lottery_status(db, team_id),
    }


def list_public_teams(
    db: Session,
    *,
    q: str = "",
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Directory of ACTIVE founded teams for the global Equipes page."""
    limit = max(1, min(200, int(limit)))
    offset = max(0, int(offset))
    q = str(q or "").strip()
    params: dict[str, Any] = {"lim": limit, "off": offset}
    where = "status = 'ACTIVE'"
    if q:
        where += (
            " AND (name LIKE :q OR name_norm LIKE :qn OR tag LIKE :qt"
            " OR owner_steam_id LIKE :qs OR founder_steam_id LIKE :qs)"
        )
        params["q"] = f"%{q}%"
        params["qn"] = f"%{_norm_name(q)}%"
        params["qt"] = f"%{q.upper()}%"
        params["qs"] = f"%{q}%"
    total_row = db.execute(
        text(f"SELECT COUNT(*) FROM teams WHERE {where}"),
        {k: v for k, v in params.items() if k not in ("lim", "off")},
    ).fetchone()
    total = int(total_row[0] or 0) if total_row else 0
    rows = db.execute(
        text(f"""
            SELECT {_TEAM_COLS}
            FROM teams WHERE {where}
            ORDER BY name ASC
            LIMIT :lim OFFSET :off
        """),
        params,
    ).fetchall()
    owner_ids = [str(_team_row(r, db=db)["owner_steam_id"]) for r in rows]
    nick_cache = _nicks_from_store_users(db, owner_ids)
    items: list[dict[str, Any]] = []
    for r in rows:
        t = _team_row(r, db=db)
        mc = count_active_members(db, t["id"])
        owner_sid = str(t["owner_steam_id"])
        owner_dn = db.execute(
            text("""
                SELECT display_name FROM team_members
                WHERE team_id = :tid AND steam_id = :sid AND status = 'ACTIVE'
                LIMIT 1
            """),
            {"tid": t["id"], "sid": owner_sid},
        ).fetchone()
        stored_dn = str(owner_dn[0] or "") if owner_dn else ""
        accepting = team_accepting_members(t, mc)
        items.append({
            "id": t["id"],
            "name": t["name"],
            "tag": t["tag"],
            "owner_steam_id": owner_sid,
            "owner_display_name": resolve_member_display_name(
                db, owner_sid, stored_dn, nick_cache=nick_cache
            ),
            "mural_text": t["mural_text"] or "",
            "member_count": mc,
            "max_members": int(t["max_members"]),
            "recruitment_open": bool(t["recruitment_open"]),
            "accepting_members": accepting,
            "recruiting_open": accepting,
            "milestone_index": t["milestone_index"],
            "team_honor": t["team_honor"],
            "status": t["status"],
        })
    return {"items": items, "total": total, "limit": limit, "offset": offset}


# ── Create / rename / lifecycle ──────────────────────────────

def create_team(
    db: Session,
    *,
    steam_id: str,
    name: str,
    tag: str = "",
    display_name: str = "",
    represents_tribe: bool = False,
) -> dict[str, Any]:
    _require_enabled()
    steam_id = str(steam_id).strip()
    if get_active_membership(db, steam_id):
        raise ValueError("Já pertence a uma equipe ativa (máx. 1 por jogador).")
    name = validate_team_name(name)
    name_norm = _norm_name(name)
    tag = str(tag or "").strip().upper()[:TEAM_TAG_MAX]
    now = _naive()
    max_m = default_max_members()

    existing = db.execute(
        text("SELECT id FROM teams WHERE name_norm = :n LIMIT 1"),
        {"n": name_norm},
    ).fetchone()
    if existing:
        raise ValueError("Já existe uma equipe com este nome.")

    # Q5: first foundation free; subsequent creates cost FOUNDING_FEE_AMBER
    fee = founding_fee_for_player(db, steam_id)
    if fee > 0:
        if not _subtract_points_tx:
            raise RuntimeError("team_service subtract_points_tx not wired")
        try:
            _subtract_points_tx(db, steam_id, fee)
        except ValueError as exc:
            msg = str(exc)
            if "insufficient" in msg.lower() or "saldo" in msg.lower():
                raise ValueError(
                    f"Saldo insuficiente para fundar novamente "
                    f"(custo: {fee} Âmbares após a 1ª fundação)."
                ) from exc
            raise

    db.execute(
        text("""
            INSERT INTO teams
              (name, name_norm, tag, founder_steam_id, owner_steam_id, status,
               max_members, milestone_index, team_xp, team_xp_lifetime,
               bank_mode, recruitment_open, represents_tribe, mural_text,
               created_at, updated_at)
            VALUES
              (:name, :nn, :tag, :founder, :owner, 'ACTIVE',
               :maxm, 0, 0, 0, 'closed', 0, :rep, '', :now, :now)
        """),
        {
            "name": name, "nn": name_norm, "tag": tag,
            "founder": steam_id, "owner": steam_id,
            "maxm": max_m, "rep": 1 if represents_tribe else 0, "now": now,
        },
    )
    row = db.execute(
        text("SELECT id FROM teams WHERE name_norm = :n LIMIT 1"),
        {"n": name_norm},
    ).fetchone()
    team_id = int(row[0])
    db.execute(
        text("""
            INSERT INTO team_members
              (team_id, steam_id, display_name, status, joined_at, last_activity_at,
               created_at, updated_at)
            VALUES (:tid, :sid, :dn, 'ACTIVE', :now, :now, :now, :now)
        """),
        {
            "tid": team_id,
            "sid": steam_id,
            "dn": resolve_member_display_name(db, steam_id, display_name),
            "now": now,
        },
    )
    db.execute(
        text("""
            INSERT INTO team_roles (team_id, steam_id, role_key, assigned_at, assigned_by)
            VALUES (:tid, :sid, :rk, :now, :sid)
        """),
        {"tid": team_id, "sid": steam_id, "rk": ROLE_OWNER, "now": now},
    )
    db.execute(
        text("""
            INSERT INTO team_bank (team_id, amber_balance, resources_json, committed_json, updated_at)
            VALUES (:tid, 0, '{}', '{}', :now)
        """),
        {"tid": team_id, "now": now},
    )
    db.commit()
    view = team_public_view(db, team_id, viewer_steam_id=steam_id)
    view["founding_fee_charged"] = fee
    return view


def rename_team(db: Session, *, team_id: int, actor_steam_id: str, name: str) -> dict[str, Any]:
    _require_enabled()
    _assert_can(db, team_id, actor_steam_id, "rename")
    team = get_team(db, team_id)
    if not team or team["status"] != "ACTIVE":
        raise ValueError("Equipe indisponível.")
    name = validate_team_name(name)
    name_norm = _norm_name(name)
    clash = db.execute(
        text("SELECT id FROM teams WHERE name_norm = :n AND id != :id LIMIT 1"),
        {"n": name_norm, "id": team_id},
    ).fetchone()
    if clash:
        raise ValueError("Já existe uma equipe com este nome.")
    now = _naive()
    db.execute(
        text("""
            UPDATE teams SET name = :name, name_norm = :nn, renamed_at = :now, updated_at = :now
            WHERE id = :id
        """),
        {"name": name, "nn": name_norm, "now": now, "id": team_id},
    )
    db.commit()
    return get_team(db, team_id) or {}


def set_recruitment_open(db: Session, *, team_id: int, actor_steam_id: str, open_: bool) -> dict[str, Any]:
    _require_enabled()
    _assert_can(db, team_id, actor_steam_id, "recruitment_toggle")
    now = _naive()
    db.execute(
        text("UPDATE teams SET recruitment_open = :o, updated_at = :now WHERE id = :id"),
        {"o": 1 if open_ else 0, "now": now, "id": team_id},
    )
    db.commit()
    return get_team(db, team_id) or {}


def update_mural(
    db: Session,
    *,
    team_id: int,
    actor_steam_id: str,
    mural_text: str,
) -> dict[str, Any]:
    """Owner / Embaixador / Arquivista — regulamento / mural da equipe."""
    _require_enabled()
    _assert_can(db, team_id, actor_steam_id, "mural")
    team = get_team(db, team_id)
    if not team or team["status"] != "ACTIVE":
        raise ValueError("Equipe indisponível.")
    text_val = str(mural_text or "").strip()
    if len(text_val) > 8000:
        raise ValueError("Regulamento/mural demasiado longo (máx. 8000 caracteres).")
    now = _naive()
    db.execute(
        text("UPDATE teams SET mural_text = :m, updated_at = :now WHERE id = :id"),
        {"m": text_val, "now": now, "id": team_id},
    )
    db.commit()
    return get_team(db, team_id) or {}


def validate_auto_kick_settings(
    *,
    auto_kick_inactive: bool,
    auto_kick_inactive_hours: int | None,
) -> tuple[bool, int]:
    """Validate Owner auto-kick config. Hours only required/clamped when enabled."""
    enabled = bool(auto_kick_inactive)
    hours = int(auto_kick_inactive_hours) if auto_kick_inactive_hours is not None else DEFAULT_AUTO_KICK_HOURS
    if enabled and (hours < AUTO_KICK_HOURS_MIN or hours > AUTO_KICK_HOURS_MAX):
        raise ValueError(
            f"auto_kick_inactive_hours deve estar entre {AUTO_KICK_HOURS_MIN} e {AUTO_KICK_HOURS_MAX}."
        )
    hours = max(AUTO_KICK_HOURS_MIN, min(AUTO_KICK_HOURS_MAX, hours))
    return enabled, hours


def update_team_settings(
    db: Session,
    *,
    team_id: int,
    actor_steam_id: str,
    auto_kick_inactive: bool | None = None,
    auto_kick_inactive_hours: int | None = None,
) -> dict[str, Any]:
    """Owner-only team settings (Q4 auto-kick)."""
    _require_enabled()
    _assert_can(db, team_id, actor_steam_id, "team_settings")
    team = get_team(db, team_id)
    if not team or team["status"] != "ACTIVE":
        raise ValueError("Equipe indisponível.")
    enabled = team["auto_kick_inactive"] if auto_kick_inactive is None else bool(auto_kick_inactive)
    hours = (
        team["auto_kick_inactive_hours"]
        if auto_kick_inactive_hours is None
        else int(auto_kick_inactive_hours)
    )
    enabled, hours = validate_auto_kick_settings(
        auto_kick_inactive=enabled,
        auto_kick_inactive_hours=hours,
    )
    now = _naive()
    db.execute(
        text("""
            UPDATE teams SET auto_kick_inactive = :ak, auto_kick_inactive_hours = :h,
              updated_at = :now WHERE id = :id
        """),
        {"ak": 1 if enabled else 0, "h": hours, "now": now, "id": team_id},
    )
    db.commit()
    return get_team(db, team_id) or {}


def touch_member_activity(
    db: Session,
    *,
    team_id: int,
    steam_id: str,
    commit: bool = False,
    at: datetime | None = None,
) -> None:
    """Update last_activity_at for inactivity tracking (Q4)."""
    now = _naive(at) if at else _naive()
    db.execute(
        text("""
            UPDATE team_members SET last_activity_at = :now, updated_at = :now
            WHERE team_id = :tid AND steam_id = :sid AND status = 'ACTIVE'
        """),
        {"now": now, "tid": int(team_id), "sid": str(steam_id)},
    )
    if commit:
        db.commit()


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s[:26], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", ""))
    except ValueError:
        return None


def process_team_inactive_kicks(
    db: Session,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Periodic job: auto-kick inactive members when Owner enabled it. Never kicks Owner."""
    if not teams_enabled():
        return {"processed": 0, "kicked": [], "skipped": "teams_disabled"}
    now_dt = _naive(now) if now else _naive()
    teams = db.execute(
        text("""
            SELECT id, owner_steam_id, auto_kick_inactive_hours
            FROM teams
            WHERE status = 'ACTIVE' AND auto_kick_inactive = 1
        """),
    ).fetchall()
    kicked: list[dict[str, Any]] = []
    for trow in teams:
        team_id = int(trow[0])
        owner_sid = str(trow[1] or "")
        hours = int(trow[2] or DEFAULT_AUTO_KICK_HOURS)
        hours = max(AUTO_KICK_HOURS_MIN, min(AUTO_KICK_HOURS_MAX, hours))
        cutoff = now_dt - timedelta(hours=hours)
        members = db.execute(
            text("""
                SELECT steam_id, last_activity_at, joined_at, created_at
                FROM team_members
                WHERE team_id = :tid AND status = 'ACTIVE'
            """),
            {"tid": team_id},
        ).fetchall()
        for m in members:
            sid = str(m[0])
            if sid == owner_sid:
                continue
            last = _parse_dt(m[1]) or _parse_dt(m[2]) or _parse_dt(m[3])
            if last is None or last > cutoff:
                continue
            try:
                kick_member(
                    db,
                    team_id=team_id,
                    actor_steam_id=owner_sid or sid,
                    target_steam_id=sid,
                    staff=True,
                )
                kicked.append({"team_id": team_id, "steam_id": sid, "last_activity_at": str(last)})
            except Exception as exc:
                log.warning("auto_kick team=%s member=%s: %s", team_id, sid, exc)
    return {"processed": len(kicked), "kicked": kicked}


# ── Invite / join / leave / kick ─────────────────────────────

def invite_member(
    db: Session,
    *,
    team_id: int,
    actor_steam_id: str,
    target_steam_id: str,
    display_name: str = "",
) -> dict[str, Any]:
    _require_enabled()
    _assert_can(db, team_id, actor_steam_id, "invite")
    team = get_team(db, team_id)
    if not team or team["status"] != "ACTIVE":
        raise ValueError("Equipe indisponível.")
    if count_active_members(db, team_id) >= int(team["max_members"]):
        raise ValueError("Equipe cheia.")
    target_steam_id = str(target_steam_id).strip()
    if get_active_membership(db, target_steam_id):
        raise ValueError("Jogador já está em uma equipe.")
    now = _naive()
    code = _gen_invite_code()
    existing = db.execute(
        text("SELECT id, status FROM team_members WHERE team_id = :tid AND steam_id = :sid"),
        {"tid": team_id, "sid": target_steam_id},
    ).fetchone()
    if existing:
        if existing[1] == "ACTIVE":
            raise ValueError("Já é membro.")
        db.execute(
            text("""
                UPDATE team_members SET status = 'INVITED', invite_code = :c,
                  display_name = :dn, updated_at = :now, left_at = NULL
                WHERE id = :id
            """),
            {"c": code, "dn": resolve_member_display_name(db, target_steam_id, display_name), "now": now, "id": existing[0]},
        )
    else:
        db.execute(
            text("""
                INSERT INTO team_members
                  (team_id, steam_id, display_name, status, invite_code, created_at, updated_at)
                VALUES (:tid, :sid, :dn, 'INVITED', :c, :now, :now)
            """),
            {
                "tid": team_id, "sid": target_steam_id,
                "dn": resolve_member_display_name(db, target_steam_id, display_name), "c": code, "now": now,
            },
        )
    db.commit()
    return {"invite_code": code, "steam_id": target_steam_id, "team_id": team_id}


def accept_invite(db: Session, *, steam_id: str, invite_code: str | None = None, team_id: int | None = None) -> dict[str, Any]:
    _require_enabled()
    steam_id = str(steam_id).strip()
    if get_active_membership(db, steam_id):
        raise ValueError("Já pertence a uma equipe.")
    if invite_code:
        row = db.execute(
            text("""
                SELECT id, team_id FROM team_members
                WHERE steam_id = :sid AND status = 'INVITED' AND invite_code = :c
                LIMIT 1
            """),
            {"sid": steam_id, "c": str(invite_code).strip().upper()},
        ).fetchone()
    elif team_id is not None:
        row = db.execute(
            text("""
                SELECT id, team_id FROM team_members
                WHERE steam_id = :sid AND team_id = :tid AND status = 'INVITED'
                LIMIT 1
            """),
            {"sid": steam_id, "tid": int(team_id)},
        ).fetchone()
    else:
        raise ValueError("Informe invite_code ou team_id.")
    if not row:
        raise ValueError("Convite não encontrado.")
    team = get_team(db, int(row[1]))
    if not team or team["status"] != "ACTIVE":
        raise ValueError("Equipe indisponível.")
    if count_active_members(db, int(row[1])) >= int(team["max_members"]):
        raise ValueError("Equipe cheia.")
    now = _naive()
    db.execute(
        text("""
            UPDATE team_members SET status = 'ACTIVE', joined_at = :now, last_activity_at = :now,
              updated_at = :now, invite_code = NULL WHERE id = :id
        """),
        {"now": now, "id": row[0]},
    )
    # R3: +2 lottery numbers if team already confirmed for active campaign (Q12 refund if short)
    maybe_allocate_lottery_on_member_join(db, int(row[1]))
    db.commit()
    return team_public_view(db, int(row[1]), viewer_steam_id=steam_id)


def decline_invite(db: Session, *, steam_id: str, team_id: int) -> dict[str, Any]:
    _require_enabled()
    now = _naive()
    res = db.execute(
        text("""
            UPDATE team_members SET status = 'DECLINED', updated_at = :now, invite_code = NULL
            WHERE team_id = :tid AND steam_id = :sid AND status = 'INVITED'
        """),
        {"now": now, "tid": int(team_id), "sid": str(steam_id)},
    )
    db.commit()
    if not res.rowcount:
        raise ValueError("Convite não encontrado.")
    return {"ok": True}


def request_join(db: Session, *, team_id: int, steam_id: str, display_name: str = "") -> dict[str, Any]:
    _require_enabled()
    steam_id = str(steam_id).strip()
    if get_active_membership(db, steam_id):
        raise ValueError("Já pertence a uma equipe.")
    team = get_team(db, team_id)
    if not team or team["status"] != "ACTIVE":
        raise ValueError("Equipe indisponível.")
    if not team["recruitment_open"]:
        raise ValueError("Equipe não está aberta a pedidos.")
    if count_active_members(db, team_id) >= int(team["max_members"]):
        raise ValueError("Equipe cheia.")
    now = _naive()
    existing = db.execute(
        text("SELECT id, status FROM team_members WHERE team_id = :tid AND steam_id = :sid"),
        {"tid": team_id, "sid": steam_id},
    ).fetchone()
    if existing and existing[1] == "ACTIVE":
        raise ValueError("Já é membro.")
    if existing:
        db.execute(
            text("""
                UPDATE team_members SET status = 'PENDING', display_name = :dn, updated_at = :now
                WHERE id = :id
            """),
            {"dn": resolve_member_display_name(db, steam_id, display_name), "now": now, "id": existing[0]},
        )
    else:
        db.execute(
            text("""
                INSERT INTO team_members
                  (team_id, steam_id, display_name, status, created_at, updated_at)
                VALUES (:tid, :sid, :dn, 'PENDING', :now, :now)
            """),
            {"tid": team_id, "sid": steam_id, "dn": resolve_member_display_name(db, steam_id, display_name), "now": now},
        )
    db.commit()
    return {"team_id": team_id, "status": "PENDING"}


def approve_join(db: Session, *, team_id: int, actor_steam_id: str, target_steam_id: str) -> dict[str, Any]:
    _require_enabled()
    _assert_can(db, team_id, actor_steam_id, "approve_join")
    team = get_team(db, team_id)
    if not team or team["status"] != "ACTIVE":
        raise ValueError("Equipe indisponível.")
    if count_active_members(db, team_id) >= int(team["max_members"]):
        raise ValueError("Equipe cheia.")
    target_steam_id = str(target_steam_id).strip()
    if get_active_membership(db, target_steam_id):
        raise ValueError("Jogador já está em outra equipe.")
    now = _naive()
    res = db.execute(
        text("""
            UPDATE team_members SET status = 'ACTIVE', joined_at = :now, last_activity_at = :now,
              updated_at = :now
            WHERE team_id = :tid AND steam_id = :sid AND status = 'PENDING'
        """),
        {"now": now, "tid": team_id, "sid": target_steam_id},
    )
    if not res.rowcount:
        raise ValueError("Pedido não encontrado.")
    maybe_allocate_lottery_on_member_join(db, team_id)
    db.commit()
    return team_public_view(db, team_id, viewer_steam_id=actor_steam_id)


def reject_join(db: Session, *, team_id: int, actor_steam_id: str, target_steam_id: str) -> dict[str, Any]:
    _require_enabled()
    _assert_can(db, team_id, actor_steam_id, "approve_join")
    now = _naive()
    res = db.execute(
        text("""
            UPDATE team_members SET status = 'REJECTED', updated_at = :now
            WHERE team_id = :tid AND steam_id = :sid AND status = 'PENDING'
        """),
        {"now": now, "tid": team_id, "sid": str(target_steam_id)},
    )
    if not res.rowcount:
        raise ValueError("Pedido não encontrado.")
    db.commit()
    return {"ok": True}


def leave_team(db: Session, *, steam_id: str) -> dict[str, Any]:
    _require_enabled()
    mem = get_active_membership(db, steam_id)
    if not mem:
        raise ValueError("Não está em nenhuma equipe.")
    team_id = int(mem["team_id"])
    team = get_team(db, team_id)
    if team and team["owner_steam_id"] == str(steam_id):
        active = count_active_members(db, team_id)
        if active > 1:
            raise ValueError("Owner deve transferir a propriedade antes de sair.")
    now = _naive()
    db.execute(
        text("""
            UPDATE team_members SET status = 'LEFT', left_at = :now, updated_at = :now
            WHERE team_id = :tid AND steam_id = :sid AND status = 'ACTIVE'
        """),
        {"now": now, "tid": team_id, "sid": str(steam_id)},
    )
    db.execute(
        text("DELETE FROM team_roles WHERE team_id = :tid AND steam_id = :sid AND role_key != :own"),
        {"tid": team_id, "sid": str(steam_id), "own": ROLE_OWNER},
    )
    if team and team["owner_steam_id"] == str(steam_id):
        db.execute(
            text("UPDATE teams SET status = 'DISBANDED', updated_at = :now WHERE id = :id"),
            {"now": now, "id": team_id},
        )
    db.commit()
    return {"ok": True, "team_id": team_id}


def kick_member(
    db: Session,
    *,
    team_id: int,
    actor_steam_id: str,
    target_steam_id: str,
    staff: bool = False,
) -> dict[str, Any]:
    _require_enabled()
    target_steam_id = str(target_steam_id).strip()
    team = get_team(db, team_id)
    if not team:
        raise ValueError("Equipe não encontrada.")
    if not staff:
        _assert_can(db, team_id, actor_steam_id, "kick")
        if target_steam_id == team["owner_steam_id"]:
            raise PermissionError("Não é possível kickar o Owner.")
        if target_steam_id == str(actor_steam_id):
            raise ValueError("Use leave para sair.")
    now = _naive()
    res = db.execute(
        text("""
            UPDATE team_members SET status = 'KICKED', left_at = :now, updated_at = :now
            WHERE team_id = :tid AND steam_id = :sid AND status = 'ACTIVE'
        """),
        {"now": now, "tid": team_id, "sid": target_steam_id},
    )
    if not res.rowcount:
        raise ValueError("Membro ativo não encontrado.")
    db.execute(
        text("DELETE FROM team_roles WHERE team_id = :tid AND steam_id = :sid"),
        {"tid": team_id, "sid": target_steam_id},
    )
    # Q9: lottery numbers stay with team (no revoke on kick/leave)
    if staff and target_steam_id == team["owner_steam_id"]:
        # Staff kick of owner → leave ownership vacant until transfer (custody)
        db.execute(
            text("UPDATE teams SET owner_steam_id = '', updated_at = :now WHERE id = :id"),
            {"now": now, "id": team_id},
        )
        db.execute(
            text("DELETE FROM team_roles WHERE team_id = :tid AND role_key = :rk"),
            {"tid": team_id, "rk": ROLE_OWNER},
        )
    db.commit()
    return {"ok": True, "team_id": team_id, "kicked": target_steam_id}


def assign_role(
    db: Session,
    *,
    team_id: int,
    actor_steam_id: str,
    target_steam_id: str,
    role_key: str,
) -> dict[str, Any]:
    _require_enabled()
    _assert_can(db, team_id, actor_steam_id, "assign_roles")
    role_key = str(role_key).strip().upper()
    if role_key == ROLE_OWNER:
        raise ValueError("Use transferência de ownership para Owner.")
    if role_key not in ASSIGNABLE_ROLES:
        raise ValueError(f"Papel inválido: {role_key}")
    mem = db.execute(
        text("""
            SELECT 1 FROM team_members
            WHERE team_id = :tid AND steam_id = :sid AND status = 'ACTIVE'
        """),
        {"tid": team_id, "sid": str(target_steam_id)},
    ).fetchone()
    if not mem:
        raise ValueError("Alvo não é membro ativo.")
    # Guardian cannot assign Guardian (only Owner)
    actor_roles = set(_member_roles(db, team_id, actor_steam_id))
    if ROLE_OWNER not in actor_roles and role_key == ROLE_GUARDIAN:
        raise PermissionError("Só o Owner pode atribuir Guardião.")
    # Q13: max MAX_SPECIAL_ROLES special roles (OWNER does not count toward the cap)
    current_special = [r for r in _member_roles(db, team_id, target_steam_id) if r in ASSIGNABLE_ROLES]
    if role_key not in current_special and len(current_special) >= MAX_SPECIAL_ROLES:
        raise ValueError(
            f"Máximo de {MAX_SPECIAL_ROLES} papéis especiais por membro "
            f"(já tem: {', '.join(current_special)})."
        )
    now = _naive()
    exists = db.execute(
        text("""
            SELECT id FROM team_roles
            WHERE team_id = :tid AND steam_id = :sid AND role_key = :rk
        """),
        {"tid": team_id, "sid": str(target_steam_id), "rk": role_key},
    ).fetchone()
    if not exists:
        db.execute(
            text("""
                INSERT INTO team_roles (team_id, steam_id, role_key, assigned_at, assigned_by)
                VALUES (:tid, :sid, :rk, :now, :by)
            """),
            {
                "tid": team_id, "sid": str(target_steam_id), "rk": role_key,
                "now": now, "by": str(actor_steam_id),
            },
        )
    db.commit()
    return {"steam_id": target_steam_id, "roles": _member_roles(db, team_id, target_steam_id)}


def remove_role(
    db: Session,
    *,
    team_id: int,
    actor_steam_id: str,
    target_steam_id: str,
    role_key: str,
) -> dict[str, Any]:
    _require_enabled()
    _assert_can(db, team_id, actor_steam_id, "assign_roles")
    role_key = str(role_key).strip().upper()
    if role_key == ROLE_OWNER:
        raise ValueError("Não é possível remover Owner assim.")
    db.execute(
        text("""
            DELETE FROM team_roles
            WHERE team_id = :tid AND steam_id = :sid AND role_key = :rk
        """),
        {"tid": team_id, "sid": str(target_steam_id), "rk": role_key},
    )
    db.commit()
    return {"steam_id": target_steam_id, "roles": _member_roles(db, team_id, target_steam_id)}


def transfer_ownership(
    db: Session,
    *,
    team_id: int,
    actor_steam_id: str,
    new_owner_steam_id: str,
    staff: bool = False,
) -> dict[str, Any]:
    _require_enabled()
    team = get_team(db, team_id)
    if not team:
        raise ValueError("Equipe não encontrada.")
    new_owner_steam_id = str(new_owner_steam_id).strip()
    if not staff:
        if team["owner_steam_id"] != str(actor_steam_id):
            raise PermissionError("Só o Owner pode transferir.")
    mem = db.execute(
        text("""
            SELECT 1 FROM team_members
            WHERE team_id = :tid AND steam_id = :sid AND status = 'ACTIVE'
        """),
        {"tid": team_id, "sid": new_owner_steam_id},
    ).fetchone()
    if not mem:
        raise ValueError("Novo Owner deve ser membro ACTIVE.")
    now = _naive()
    old = team["owner_steam_id"]
    db.execute(
        text("UPDATE teams SET owner_steam_id = :o, updated_at = :now WHERE id = :id"),
        {"o": new_owner_steam_id, "now": now, "id": team_id},
    )
    db.execute(
        text("DELETE FROM team_roles WHERE team_id = :tid AND role_key = :rk"),
        {"tid": team_id, "rk": ROLE_OWNER},
    )
    db.execute(
        text("""
            INSERT INTO team_roles (team_id, steam_id, role_key, assigned_at, assigned_by)
            VALUES (:tid, :sid, :rk, :now, :by)
        """),
        {
            "tid": team_id, "sid": new_owner_steam_id, "rk": ROLE_OWNER,
            "now": now, "by": str(actor_steam_id),
        },
    )
    db.commit()
    return {
        "team_id": team_id,
        "old_owner": old,
        "new_owner": new_owner_steam_id,
    }


def suspend_team(db: Session, *, team_id: int, suspend: bool = True) -> dict[str, Any]:
    _require_enabled()
    team = get_team(db, team_id)
    if not team:
        raise ValueError("Equipe não encontrada.")
    now = _naive()
    status = "SUSPENDED" if suspend else "ACTIVE"
    db.execute(
        text("UPDATE teams SET status = :st, updated_at = :now WHERE id = :id"),
        {"st": status, "now": now, "id": team_id},
    )
    db.commit()
    return get_team(db, team_id) or {}


def staff_list_teams(db: Session, *, q: str = "", limit: int = 100) -> list[dict[str, Any]]:
    limit = max(1, min(500, int(limit)))
    q = str(q or "").strip()
    if q:
        rows = db.execute(
            text(f"""
                SELECT {_TEAM_COLS}
                FROM teams
                WHERE name LIKE :q OR owner_steam_id LIKE :q OR founder_steam_id LIKE :q
                ORDER BY id DESC LIMIT :lim
            """),
            {"q": f"%{q}%", "lim": limit},
        ).fetchall()
    else:
        rows = db.execute(
            text(f"""
                SELECT {_TEAM_COLS}
                FROM teams ORDER BY id DESC LIMIT :lim
            """),
            {"lim": limit},
        ).fetchall()
    out = []
    for r in rows:
        t = _team_row(r, db=db)
        t["member_count"] = count_active_members(db, t["id"])
        out.append(t)
    return out


# ── Bank ─────────────────────────────────────────────────────

def get_bank(db: Session, team_id: int) -> dict[str, Any]:
    row = db.execute(
        text(
            "SELECT amber_balance, resources_json, committed_json, updated_at "
            "FROM team_bank WHERE team_id = :tid"
        ),
        {"tid": team_id},
    ).fetchone()
    if not row:
        now = _naive()
        db.execute(
            text("""
                INSERT INTO team_bank (team_id, amber_balance, resources_json, committed_json, updated_at)
                VALUES (:tid, 0, '{}', '{}', :now)
            """),
            {"tid": team_id, "now": now},
        )
        db.commit()
        return {
            "team_id": team_id,
            "amber_balance": 0,
            "resources": {},
            "committed": {},
            "updated_at": str(now),
        }
    try:
        resources = json.loads(row[1] or "{}")
    except Exception:
        resources = {}
    try:
        committed = json.loads(row[2] or "{}") if row[2] is not None else {}
    except Exception:
        committed = {}
    resources = _migrate_warehouse_resource_map(
        resources if isinstance(resources, dict) else {}
    )
    committed = _migrate_warehouse_resource_map(
        committed if isinstance(committed, dict) else {}
    )
    return {
        "team_id": team_id,
        "amber_balance": int(row[0] or 0),
        "resources": resources,
        "committed": committed,
        "updated_at": str(row[3]) if row[3] else None,
    }


def get_bank_ledger(db: Session, team_id: int, *, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(200, int(limit)))
    rows = db.execute(
        text("""
            SELECT id, entry_type, asset_kind, asset_key, amount, balance_after,
                   actor_steam_id, note, created_at
            FROM team_bank_ledger WHERE team_id = :tid
            ORDER BY id DESC LIMIT :lim
        """),
        {"tid": team_id, "lim": limit},
    ).fetchall()
    return [
        {
            "id": int(r[0]),
            "entry_type": r[1],
            "asset_kind": r[2],
            "asset_key": r[3],
            "amount": int(r[4]),
            "balance_after": int(r[5] or 0),
            "actor_steam_id": r[6] or "",
            "note": r[7] or "",
            "created_at": str(r[8]) if r[8] else None,
        }
        for r in rows
    ]


def donate_amber(
    db: Session,
    *,
    team_id: int,
    steam_id: str,
    amount: int,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Debit player wallet → credit team bank."""
    _require_enabled()
    amount = int(amount)
    if amount <= 0:
        raise ValueError("Valor deve ser positivo.")
    mem = get_active_membership(db, steam_id)
    if not mem or mem["team_id"] != team_id:
        raise PermissionError("Só membros ACTIVE podem doar.")
    team = get_team(db, team_id)
    if not team or team["status"] != "ACTIVE":
        raise ValueError("Equipe indisponível.")

    if idempotency_key:
        prev = db.execute(
            text("SELECT id FROM team_bank_ledger WHERE idempotency_key = :k LIMIT 1"),
            {"k": str(idempotency_key)[:128]},
        ).fetchone()
        if prev:
            bank = get_bank(db, team_id)
            return {"duplicate": True, "bank": bank}

    if not _subtract_points_tx:
        raise RuntimeError("team_service subtract_points_tx not wired")
    _subtract_points_tx(db, str(steam_id), amount)

    bank = get_bank(db, team_id)
    new_bal = int(bank["amber_balance"]) + amount
    now = _naive()
    db.execute(
        text("""
            UPDATE team_bank SET amber_balance = :b, updated_at = :now WHERE team_id = :tid
        """),
        {"b": new_bal, "now": now, "tid": team_id},
    )
    db.execute(
        text("""
            INSERT INTO team_bank_ledger
              (team_id, entry_type, asset_kind, asset_key, amount, balance_after,
               actor_steam_id, idempotency_key, note, created_at)
            VALUES
              (:tid, 'DONATE_AMBER', 'amber', 'amber', :amt, :bal,
               :actor, :idem, 'Doação de Âmbares', :now)
        """),
        {
            "tid": team_id, "amt": amount, "bal": new_bal,
            "actor": str(steam_id),
            "idem": (str(idempotency_key)[:128] if idempotency_key else None),
            "now": now,
        },
    )
    touch_member_activity(db, team_id=team_id, steam_id=str(steam_id))
    db.commit()
    return {"donated": amount, "bank": get_bank(db, team_id)}


def deposit_resource(
    db: Session,
    *,
    team_id: int,
    steam_id: str,
    resource_key: str,
    amount: int,
    idempotency_key: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    """Plugin /marco bridge — credit catalog resource into team WAREHOUSE (not milestone)."""
    _require_enabled()
    amount = int(amount)
    if amount <= 0:
        raise ValueError("Quantidade deve ser positiva.")
    resource_key = normalize_warehouse_key(resource_key)
    label = _WAREHOUSE_BY_KEY[resource_key]["label_pt"]
    mem = get_active_membership(db, steam_id)
    if not mem or mem["team_id"] != team_id:
        raise PermissionError("Jogador não é membro ACTIVE desta equipe.")

    if idempotency_key:
        prev = db.execute(
            text("SELECT id FROM team_bank_ledger WHERE idempotency_key = :k LIMIT 1"),
            {"k": str(idempotency_key)[:128]},
        ).fetchone()
        if prev:
            return {"duplicate": True, "bank": get_bank(db, team_id)}

    bank = get_bank(db, team_id)
    resources = dict(bank["resources"])
    resources[resource_key] = int(resources.get(resource_key) or 0) + amount
    now = _naive()
    db.execute(
        text("UPDATE team_bank SET resources_json = :rj, updated_at = :now WHERE team_id = :tid"),
        {"rj": json.dumps(resources, ensure_ascii=False), "now": now, "tid": team_id},
    )
    db.execute(
        text("""
            INSERT INTO team_bank_ledger
              (team_id, entry_type, asset_kind, asset_key, amount, balance_after,
               actor_steam_id, idempotency_key, note, created_at)
            VALUES
              (:tid, 'DEPOSIT_RESOURCE', 'resource', :rk, :amt, :bal,
               :actor, :idem, :note, :now)
        """),
        {
            "tid": team_id, "rk": resource_key, "amt": amount,
            "bal": resources[resource_key], "actor": str(steam_id),
            "idem": (str(idempotency_key)[:128] if idempotency_key else None),
            "note": (note or f"/marco → armazém ({label})")[:255], "now": now,
        },
    )
    touch_member_activity(db, team_id=team_id, steam_id=str(steam_id))
    db.commit()
    return {
        "deposited": amount,
        "resource_key": resource_key,
        "label_pt": label,
        "bank": get_bank(db, team_id),
    }


def commit_warehouse_to_milestone(
    db: Session,
    *,
    team_id: int,
    actor_steam_id: str,
    resource_key: str,
    amount: int,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Owner/Treasurer: move qty from warehouse → committed progress for current milestone."""
    _require_enabled()
    _assert_can(db, team_id, actor_steam_id, "milestone_commit")
    amount = int(amount)
    if amount <= 0:
        raise ValueError("Quantidade deve ser positiva.")
    resource_key = normalize_warehouse_key(resource_key)
    label = _WAREHOUSE_BY_KEY[resource_key]["label_pt"]

    team = get_team(db, team_id)
    if not team or team["status"] != "ACTIVE":
        raise ValueError("Equipe indisponível.")
    ms = get_current_milestone_for_team(db, team)
    if not ms:
        raise ValueError("Nenhum marco ACTIVE disponível para aplicar recursos.")

    allowed_keys = {
        str(req.get("key") or "")
        for req in (ms.get("resources") or [])
        if int(req.get("quantity") or 0) > 0
    }
    if resource_key not in allowed_keys:
        raise ValueError(
            f"{label} não é requisito do marco atual. "
            f"Requisitos: {', '.join(sorted(allowed_keys)) or '(nenhum)'}."
        )

    if idempotency_key:
        prev = db.execute(
            text("SELECT id FROM team_bank_ledger WHERE idempotency_key = :k LIMIT 1"),
            {"k": str(idempotency_key)[:128]},
        ).fetchone()
        if prev:
            return {"duplicate": True, "bank": get_bank(db, team_id)}

    bank = get_bank(db, team_id)
    warehouse = dict(bank["resources"])
    committed = dict(bank.get("committed") or {})
    have = int(warehouse.get(resource_key) or 0)
    if have < amount:
        raise ValueError(
            f"Armazém insuficiente de {label}: tem {have}, pediu {amount}."
        )
    warehouse[resource_key] = have - amount
    if warehouse[resource_key] == 0:
        warehouse.pop(resource_key, None)
    committed[resource_key] = int(committed.get(resource_key) or 0) + amount
    now = _naive()
    db.execute(
        text("""
            UPDATE team_bank SET resources_json = :rj, committed_json = :cj, updated_at = :now
            WHERE team_id = :tid
        """),
        {
            "rj": json.dumps(warehouse, ensure_ascii=False),
            "cj": json.dumps(committed, ensure_ascii=False),
            "now": now,
            "tid": team_id,
        },
    )
    db.execute(
        text("""
            INSERT INTO team_bank_ledger
              (team_id, entry_type, asset_kind, asset_key, amount, balance_after,
               actor_steam_id, idempotency_key, note, created_at)
            VALUES
              (:tid, 'COMMIT_MILESTONE', 'resource', :rk, :amt, :bal,
               :actor, :idem, :note, :now)
        """),
        {
            "tid": team_id, "rk": resource_key, "amt": -amount,
            "bal": int(warehouse.get(resource_key) or 0),
            "actor": str(actor_steam_id),
            "idem": (str(idempotency_key)[:128] if idempotency_key else None),
            "note": f"Aplicar ao marco {ms['milestone_index']}: {amount}× {label}"[:255],
            "now": now,
        },
    )
    touch_member_activity(db, team_id=team_id, steam_id=str(actor_steam_id))
    db.commit()
    return {
        "committed": amount,
        "resource_key": resource_key,
        "label_pt": label,
        "bank": get_bank(db, team_id),
        "progress": milestone_progress_view(db, get_team(db, team_id) or team, ms),
    }


# ── Milestones ───────────────────────────────────────────────

def list_milestones(db: Session, *, include_draft: bool = False) -> list[dict[str, Any]]:
    if include_draft:
        rows = db.execute(
            text("""
                SELECT id, milestone_index, title, description, amber_required, xp_required,
                       resources_json, max_members_unlock, status, created_at, updated_at,
                       amber_bonus_pp
                FROM team_milestones ORDER BY milestone_index
            """)
        ).fetchall()
    else:
        rows = db.execute(
            text("""
                SELECT id, milestone_index, title, description, amber_required, xp_required,
                       resources_json, max_members_unlock, status, created_at, updated_at,
                       amber_bonus_pp
                FROM team_milestones
                WHERE status IN ('ACTIVE', 'COMPLETED')
                ORDER BY milestone_index
            """)
        ).fetchall()
    return [_ms_row(r) for r in rows]


def _ms_row(r: Any) -> dict[str, Any]:
    try:
        resources = json.loads(r[6] or "[]")
    except Exception:
        resources = []
    if not isinstance(resources, list):
        resources = []
    # Enrich labels for UI
    enriched = []
    for req in resources:
        if not isinstance(req, dict):
            continue
        key = str(req.get("key") or "")
        meta = _WAREHOUSE_BY_KEY.get(key)
        enriched.append({
            "key": key,
            "quantity": int(req.get("quantity") or 0),
            "label_pt": req.get("label_pt") or (meta["label_pt"] if meta else key),
        })
    amber_pp = None
    if len(r) > 11 and r[11] is not None:
        try:
            amber_pp = max(0, int(r[11]))
        except (TypeError, ValueError):
            amber_pp = None
    return {
        "id": int(r[0]),
        "milestone_index": int(r[1]),
        "title": r[2] or "",
        "description": r[3] or "",
        "amber_required": int(r[4] or 0),
        "xp_required": int(r[5] or 0),
        "resources": enriched,
        "max_members_unlock": int(r[7]) if r[7] is not None else None,
        "status": r[8],
        "created_at": str(r[9]) if r[9] else None,
        "updated_at": str(r[10]) if r[10] else None,
        "amber_bonus_pp": amber_pp if amber_pp is not None else amber_bonus_pp_per_milestone(),
        "amber_bonus_pp_explicit": amber_pp,
    }


def upsert_milestone(
    db: Session,
    *,
    milestone_index: int,
    title: str,
    description: str = "",
    amber_required: int = 0,
    xp_required: int = 0,
    resources: list[dict[str, Any]] | None = None,
    max_members_unlock: int | None = None,
    amber_bonus_pp: int | None = None,
    status: str = "DRAFT",
) -> dict[str, Any]:
    milestone_index = int(milestone_index)
    if milestone_index < 1:
        raise ValueError("milestone_index >= 1")
    status = str(status or "DRAFT").upper()
    if status not in MILESTONE_STATUSES:
        raise ValueError("status inválido")
    resources = validate_milestone_resources(resources)
    now = _naive()
    existing = db.execute(
        text("SELECT id FROM team_milestones WHERE milestone_index = :i"),
        {"i": milestone_index},
    ).fetchone()
    if amber_bonus_pp is None:
        pp_val = amber_bonus_pp_per_milestone()
    else:
        pp_val = max(0, int(amber_bonus_pp))
    params = {
        "i": milestone_index,
        "title": str(title or f"Marco {milestone_index}")[:128],
        "desc": str(description or ""),
        "amber": max(0, int(amber_required)),
        "xp": max(0, int(xp_required)),
        "rj": json.dumps(resources, ensure_ascii=False),
        "mmu": max_members_unlock,
        "abpp": pp_val,
        "st": status,
        "now": now,
    }
    if existing:
        db.execute(
            text("""
                UPDATE team_milestones SET title=:title, description=:desc,
                  amber_required=:amber, xp_required=:xp, resources_json=:rj,
                  max_members_unlock=:mmu, amber_bonus_pp=:abpp, status=:st, updated_at=:now
                WHERE milestone_index=:i
            """),
            params,
        )
    else:
        db.execute(
            text("""
                INSERT INTO team_milestones
                  (milestone_index, title, description, amber_required, xp_required,
                   resources_json, max_members_unlock, amber_bonus_pp, status, created_at, updated_at)
                VALUES (:i, :title, :desc, :amber, :xp, :rj, :mmu, :abpp, :st, :now, :now)
            """),
            params,
        )
    db.commit()
    row = db.execute(
        text("""
            SELECT id, milestone_index, title, description, amber_required, xp_required,
                   resources_json, max_members_unlock, status, created_at, updated_at,
                   amber_bonus_pp
            FROM team_milestones WHERE milestone_index = :i
        """),
        {"i": milestone_index},
    ).fetchone()
    return _ms_row(row)


def publish_milestone(db: Session, milestone_index: int) -> dict[str, Any]:
    return upsert_milestone(
        db,
        **{**_ms_as_kwargs(db, milestone_index), "status": "ACTIVE"},
    )


def _ms_as_kwargs(db: Session, milestone_index: int) -> dict[str, Any]:
    rows = list_milestones(db, include_draft=True)
    ms = next((m for m in rows if m["milestone_index"] == int(milestone_index)), None)
    if not ms:
        raise ValueError("Marco não encontrado.")
    return {
        "milestone_index": ms["milestone_index"],
        "title": ms["title"],
        "description": ms["description"],
        "amber_required": ms["amber_required"],
        "xp_required": ms["xp_required"],
        "resources": ms["resources"],
        "max_members_unlock": ms["max_members_unlock"],
        "amber_bonus_pp": ms.get("amber_bonus_pp_explicit", ms.get("amber_bonus_pp")),
        "status": ms["status"],
    }


def get_current_milestone_for_team(db: Session, team: dict[str, Any]) -> dict[str, Any] | None:
    """Cursor per team (Q16): next published milestone after milestone_index."""
    next_idx = int(team["milestone_index"]) + 1
    row = db.execute(
        text("""
            SELECT id, milestone_index, title, description, amber_required, xp_required,
                   resources_json, max_members_unlock, status, created_at, updated_at,
                   amber_bonus_pp
            FROM team_milestones
            WHERE milestone_index = :i AND status = 'ACTIVE'
            LIMIT 1
        """),
        {"i": next_idx},
    ).fetchone()
    return _ms_row(row) if row else None


def cumulative_xp_threshold(db: Session, up_to_milestone_index: int) -> int:
    """Sum of incremental xp_required for milestones 1..N (Q3 lifetime model).

    Admin field xp_required is incremental XP for that marco; progress checks
    team_xp_lifetime against the running sum.
    """
    idx = int(up_to_milestone_index)
    if idx <= 0:
        return 0
    row = db.execute(
        text("""
            SELECT COALESCE(SUM(xp_required), 0) FROM team_milestones
            WHERE milestone_index >= 1 AND milestone_index <= :i
              AND status IN ('ACTIVE', 'COMPLETED', 'RETIRED')
        """),
        {"i": idx},
    ).fetchone()
    return int(row[0] or 0) if row else 0


def milestone_progress_view(
    db: Session, team: dict[str, Any], ms: dict[str, Any]
) -> dict[str, Any]:
    bank = get_bank(db, int(team["id"]))
    res_req = ms.get("resources") or []
    warehouse = bank["resources"]
    committed = bank.get("committed") or {}
    resources_ok = True
    resource_bars = []
    for req in res_req:
        key = str(req.get("key") or req.get("blueprint_or_key") or "")
        need = int(req.get("quantity") or 0)
        have_committed = int(committed.get(key) or 0)
        have_warehouse = int(warehouse.get(key) or 0)
        label = req.get("label_pt") or (_WAREHOUSE_BY_KEY.get(key) or {}).get("label_pt") or key
        if have_committed < need:
            resources_ok = False
        resource_bars.append({
            "key": key,
            "label_pt": label,
            "required": need,
            "have": have_committed,
            "committed": have_committed,
            "warehouse": have_warehouse,
            "ok": have_committed >= need,
        })
    amber_ok = int(bank["amber_balance"]) >= int(ms["amber_required"])
    lifetime = int(team.get("team_xp_lifetime") or team.get("team_xp") or 0)
    mi = int(ms["milestone_index"])
    xp_threshold = cumulative_xp_threshold(db, mi)
    xp_prev = cumulative_xp_threshold(db, mi - 1)
    xp_incremental = int(ms.get("xp_required") or 0)
    xp_ok = lifetime >= xp_threshold
    complete = resources_ok and amber_ok and xp_ok
    return {
        "milestone": ms,
        "team_xp": lifetime,
        "team_xp_lifetime": lifetime,
        "team_honor": lifetime,
        "xp_required_incremental": xp_incremental,
        "xp_threshold_cumulative": xp_threshold,
        "xp_threshold_previous": xp_prev,
        "xp_into_marco": max(0, lifetime - xp_prev),
        "amber_balance": int(bank["amber_balance"]),
        "warehouse": warehouse,
        "committed": committed,
        "resources": resource_bars,
        "amber_ok": amber_ok,
        "xp_ok": xp_ok,
        "resources_ok": resources_ok,
        "can_complete": complete,
        "can_commit": True,
    }


def try_complete_milestone(db: Session, *, team_id: int, actor_steam_id: str | None = None) -> dict[str, Any]:
    """Complete current marco when committed+amber+lifetime XP met; keep lifetime XP (Q3)."""
    _require_enabled()
    team = get_team(db, team_id)
    if not team or team["status"] != "ACTIVE":
        raise ValueError("Equipe indisponível.")
    ms = get_current_milestone_for_team(db, team)
    if not ms:
        raise ValueError("Nenhum marco ACTIVE disponível para esta equipe.")
    view = milestone_progress_view(db, team, ms)
    if not view["can_complete"]:
        return {"completed": False, "progress": view}

    bank = get_bank(db, team_id)
    warehouse = dict(bank["resources"])
    committed = dict(bank.get("committed") or {})
    for req in ms.get("resources") or []:
        key = str(req.get("key") or req.get("blueprint_or_key") or "")
        need = int(req.get("quantity") or 0)
        have = int(committed.get(key) or 0)
        if have < need:
            raise ValueError("Progresso committed insuficiente.")
        remaining = have - need
        if remaining > 0:
            # Excess committed returns to warehouse
            warehouse[key] = int(warehouse.get(key) or 0) + remaining
            committed.pop(key, None)
        else:
            committed.pop(key, None)

    amber_cost = int(ms["amber_required"])
    new_amber = int(bank["amber_balance"]) - amber_cost
    if new_amber < 0:
        raise ValueError("Saldo de Âmbares insuficiente.")

    now = _naive()
    new_index = int(ms["milestone_index"])
    # Q3: keep lifetime XP (do not zero); sync team_xp mirror to lifetime
    lifetime = int(team["team_xp_lifetime"])
    db.execute(
        text("""
            UPDATE teams SET milestone_index = :mi, team_xp = :xp, updated_at = :now,
              max_members = CASE
                WHEN :mmu IS NOT NULL AND :mmu > max_members THEN :mmu
                ELSE max_members END
            WHERE id = :id
        """),
        {
            "mi": new_index,
            "xp": lifetime,
            "now": now,
            "mmu": ms.get("max_members_unlock"),
            "id": team_id,
        },
    )
    db.execute(
        text("""
            UPDATE team_bank SET amber_balance = :a, resources_json = :rj,
              committed_json = :cj, updated_at = :now
            WHERE team_id = :tid
        """),
        {
            "a": new_amber,
            "rj": json.dumps(warehouse, ensure_ascii=False),
            "cj": json.dumps(committed, ensure_ascii=False),
            "now": now,
            "tid": team_id,
        },
    )
    if amber_cost > 0:
        db.execute(
            text("""
                INSERT INTO team_bank_ledger
                  (team_id, entry_type, asset_kind, asset_key, amount, balance_after,
                   actor_steam_id, note, created_at)
                VALUES
                  (:tid, 'MILESTONE_SPEND', 'amber', 'amber', :amt, :bal, :actor, :note, :now)
            """),
            {
                "tid": team_id, "amt": -amber_cost, "bal": new_amber,
                "actor": str(actor_steam_id or ""),
                "note": f"Marco {new_index}", "now": now,
            },
        )
    for req in ms.get("resources") or []:
        key = str(req.get("key") or "")
        need = int(req.get("quantity") or 0)
        if need <= 0:
            continue
        db.execute(
            text("""
                INSERT INTO team_bank_ledger
                  (team_id, entry_type, asset_kind, asset_key, amount, balance_after,
                   actor_steam_id, note, created_at)
                VALUES
                  (:tid, 'MILESTONE_SPEND', 'resource', :rk, :amt, 0, :actor, :note, :now)
            """),
            {
                "tid": team_id, "rk": key, "amt": -need,
                "actor": str(actor_steam_id or ""),
                "note": f"Marco {new_index} consumiu committed", "now": now,
            },
        )
    db.execute(
        text("""
            INSERT INTO team_milestone_progress
              (team_id, milestone_index, status, completed_at, created_at, updated_at)
            VALUES (:tid, :mi, 'COMPLETED', :now, :now, :now)
        """),
        {"tid": team_id, "mi": new_index, "now": now},
    )
    db.commit()
    return {
        "completed": True,
        "milestone_index": new_index,
        "team": get_team(db, team_id),
        "bank": get_bank(db, team_id),
    }


# ── XP hooks (TimedPoints outbox) ────────────────────────────

def add_team_timed_xp(
    db: Session,
    *,
    steam_id: str,
    amount: int,
    map_id: str,
    cycle_key: str,
    commit: bool = False,
) -> dict[str, Any]:
    """Mirror season_pass add_timed_xp: 1 Â = 1 XP to player lifetime + team marco XP."""
    amount = int(amount)
    if amount <= 0:
        return {"applied": False, "reason": "zero"}
    steam_id = str(steam_id)
    mid = str(map_id or "unknown")[:64]
    ck = str(cycle_key)[:64]
    now = _naive()

    # Always credit player lifetime XP (even without team) — P5
    prev_p = db.execute(
        text("SELECT xp FROM player_xp_lifetime WHERE steam_id = :sid"),
        {"sid": steam_id},
    ).fetchone()
    # Dedup via team_xp_events when in team; for solo use negative team_id sentinel in events
    mem = get_active_membership(db, steam_id)
    team_id = int(mem["team_id"]) if mem else 0

    if team_id:
        exists = db.execute(
            text("""
                SELECT 1 FROM team_xp_events
                WHERE team_id = :tid AND steam_id = :sid AND map_id = :mid
                  AND cycle_key = :ck AND amount = :amt LIMIT 1
            """),
            {"tid": team_id, "sid": steam_id, "mid": mid, "ck": ck, "amt": amount},
        ).fetchone()
        if exists:
            return {"applied": False, "duplicate": True}

        db.execute(
            text("""
                INSERT INTO team_xp_events
                  (created_at, team_id, steam_id, amount, map_id, cycle_key)
                VALUES (:now, :tid, :sid, :amt, :mid, :ck)
            """),
            {"now": now, "tid": team_id, "sid": steam_id, "amt": amount, "mid": mid, "ck": ck},
        )
        db.execute(
            text("""
                UPDATE teams SET team_xp = team_xp + :a, team_xp_lifetime = team_xp_lifetime + :a,
                  updated_at = :now WHERE id = :id
            """),
            {"a": amount, "now": now, "id": team_id},
        )
        touch_member_activity(db, team_id=team_id, steam_id=steam_id)
    else:
        # Solo lifetime: idempotency via team_id=0 events
        exists = db.execute(
            text("""
                SELECT 1 FROM team_xp_events
                WHERE team_id = 0 AND steam_id = :sid AND map_id = :mid
                  AND cycle_key = :ck AND amount = :amt LIMIT 1
            """),
            {"sid": steam_id, "mid": mid, "ck": ck, "amt": amount},
        ).fetchone()
        if exists:
            return {"applied": False, "duplicate": True}
        db.execute(
            text("""
                INSERT INTO team_xp_events
                  (created_at, team_id, steam_id, amount, map_id, cycle_key)
                VALUES (:now, 0, :sid, :amt, :mid, :ck)
            """),
            {"now": now, "sid": steam_id, "amt": amount, "mid": mid, "ck": ck},
        )

    new_xp = int(prev_p[0] if prev_p else 0) + amount
    if prev_p:
        db.execute(
            text("UPDATE player_xp_lifetime SET xp = :xp, updated_at = :now WHERE steam_id = :sid"),
            {"xp": new_xp, "now": now, "sid": steam_id},
        )
    else:
        db.execute(
            text("""
                INSERT INTO player_xp_lifetime (steam_id, xp, updated_at)
                VALUES (:sid, :xp, :now)
            """),
            {"sid": steam_id, "xp": new_xp, "now": now},
        )

    if commit:
        db.commit()
    return {
        "applied": True,
        "team_id": team_id or None,
        "player_xp": new_xp,
        "xp_added": amount,
    }


# ── Rankings ─────────────────────────────────────────────────

def ranking_teams(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(200, int(limit)))
    rows = db.execute(
        text(f"""
            SELECT {_TEAM_COLS}
            FROM teams WHERE status = 'ACTIVE'
            ORDER BY milestone_index DESC, team_xp_lifetime DESC, created_at ASC
            LIMIT :lim
        """),
        {"lim": limit},
    ).fetchall()
    out = []
    for i, r in enumerate(rows, start=1):
        t = _team_row(r, db=db)
        t["rank"] = i
        t["member_count"] = count_active_members(db, t["id"])
        out.append(t)
    return out


def ranking_players(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    limit = max(1, min(200, int(limit)))
    rows = db.execute(
        text("""
            SELECT steam_id, xp, updated_at FROM player_xp_lifetime
            ORDER BY xp DESC, steam_id ASC LIMIT :lim
        """),
        {"lim": limit},
    ).fetchall()
    steam_ids = [str(r[0]) for r in rows]
    nick_cache = _nicks_from_store_users(db, steam_ids)
    out = []
    for i, r in enumerate(rows, start=1):
        sid = str(r[0])
        mem = get_active_membership(db, sid)
        out.append({
            "rank": i,
            "steam_id": sid,
            "display_name": resolve_member_display_name(db, sid, nick_cache=nick_cache),
            "xp": int(r[1] or 0),
            "updated_at": str(r[2]) if r[2] else None,
            "team_id": mem["team_id"] if mem else None,
            "team_name": mem["team_name"] if mem else None,
        })
    return out


def my_player_rank(db: Session, steam_id: str) -> dict[str, Any]:
    row = db.execute(
        text("SELECT xp FROM player_xp_lifetime WHERE steam_id = :sid"),
        {"sid": str(steam_id)},
    ).fetchone()
    xp = int(row[0] or 0) if row else 0
    above = db.execute(
        text("SELECT COUNT(*) FROM player_xp_lifetime WHERE xp > :xp"),
        {"xp": xp},
    ).fetchone()
    rank = int(above[0] or 0) + 1 if xp > 0 or row else None
    return {"steam_id": str(steam_id), "xp": xp, "rank": rank}


# ── Team market split (Q1: replaces tribe split when teams_enabled) ─

def get_active_team_split(db: Session, team_id: int) -> dict[str, Any] | None:
    row = db.execute(
        text("""
            SELECT id, team_id, status, sender_pct, pool_pct, created_at, updated_at, updated_by
            FROM team_splits WHERE team_id = :tid AND status = 'ACTIVE'
            ORDER BY id DESC LIMIT 1
        """),
        {"tid": team_id},
    ).fetchone()
    if not row:
        return None
    split = {
        "id": int(row[0]),
        "team_id": int(row[1]),
        "status": row[2],
        "sender_pct": int(row[3]),
        "pool_pct": int(row[4]),
        "created_at": str(row[5]) if row[5] else None,
        "updated_at": str(row[6]) if row[6] else None,
        "updated_by": row[7],
        "kind": "team",
    }
    members = db.execute(
        text("""
            SELECT id, steam_id, display_name, percentage, is_seller, opted_out
            FROM team_split_members WHERE split_id = :sid
        """),
        {"sid": split["id"]},
    ).fetchall()
    split["members"] = [
        {
            "id": int(m[0]),
            "steam_id": m[1],
            "display_name": m[2] or "",
            "percentage": int(m[3]),
            "is_seller": bool(m[4]),
            "opted_out": bool(m[5]),
        }
        for m in members
    ]
    return split


def create_or_update_team_split(
    db: Session,
    *,
    team_id: int,
    actor_steam_id: str,
    sender_pct: int = SPLIT_DEFAULT_SENDER_PCT,
) -> dict[str, Any]:
    _require_enabled()
    _assert_can(db, team_id, actor_steam_id, "split_config")
    sender_pct = int(sender_pct)
    pool_pct = 100 - sender_pct
    if sender_pct <= 0 or pool_pct <= 0:
        raise ValueError("Percentuais inválidos.")
    if sender_pct - (pool_pct if pool_pct < sender_pct else 0) < 0:
        pass
    # Gap vs equal pool share is validated at snapshot time; store template.
    actives = list_members(db, team_id, statuses=["ACTIVE"])
    if len(actives) < 2:
        raise ValueError("Split exige ao menos 2 membros ACTIVE.")
    now = _naive()
    existing = get_active_team_split(db, team_id)
    if existing:
        db.execute(
            text("""
                UPDATE team_splits SET sender_pct=:s, pool_pct=:p, updated_at=:now, updated_by=:by
                WHERE id=:id
            """),
            {"s": sender_pct, "p": pool_pct, "now": now, "by": actor_steam_id, "id": existing["id"]},
        )
        split_id = existing["id"]
        db.execute(text("DELETE FROM team_split_members WHERE split_id = :sid"), {"sid": split_id})
    else:
        db.execute(
            text("""
                INSERT INTO team_splits
                  (team_id, status, sender_pct, pool_pct, created_at, updated_at, updated_by)
                VALUES (:tid, 'ACTIVE', :s, :p, :now, :now, :by)
            """),
            {
                "tid": team_id, "s": sender_pct, "p": pool_pct,
                "now": now, "by": actor_steam_id,
            },
        )
        row = db.execute(
            text("SELECT id FROM team_splits WHERE team_id = :tid ORDER BY id DESC LIMIT 1"),
            {"tid": team_id},
        ).fetchone()
        split_id = int(row[0])

    # Opt-in roster; runtime snapshot assigns is_seller + equal pool shares.
    for m in actives:
        db.execute(
            text("""
                INSERT INTO team_split_members
                  (split_id, steam_id, display_name, percentage, is_seller, opted_out, added_at)
                VALUES (:sid, :steam, :dn, 0, 0, 0, :now)
            """),
            {
                "sid": split_id,
                "steam": m["steam_id"],
                "dn": m.get("display_name") or m["steam_id"],
                "now": now,
            },
        )
    db.commit()
    return get_active_team_split(db, team_id) or {}


def disable_team_split(db: Session, *, team_id: int, actor_steam_id: str) -> dict[str, Any]:
    _require_enabled()
    _assert_can(db, team_id, actor_steam_id, "split_config")
    now = _naive()
    db.execute(
        text("""
            UPDATE team_splits SET status = 'DISABLED', updated_at = :now, updated_by = :by
            WHERE team_id = :tid AND status = 'ACTIVE'
        """),
        {"now": now, "by": actor_steam_id, "tid": team_id},
    )
    db.commit()
    return {"ok": True}


def team_split_optin(db: Session, *, team_id: int, steam_id: str) -> dict[str, Any]:
    _require_enabled()
    mem = get_active_membership(db, steam_id)
    if not mem or mem["team_id"] != team_id:
        raise PermissionError("Não é membro ACTIVE.")
    split = get_active_team_split(db, team_id)
    if not split:
        raise ValueError("Sem split ACTIVE.")
    now = _naive()
    row = db.execute(
        text("SELECT id FROM team_split_members WHERE split_id = :sid AND steam_id = :steam"),
        {"sid": split["id"], "steam": str(steam_id)},
    ).fetchone()
    if row:
        db.execute(
            text("""
                UPDATE team_split_members SET opted_out = 0, opted_out_at = NULL
                WHERE id = :id
            """),
            {"id": row[0]},
        )
    else:
        db.execute(
            text("""
                INSERT INTO team_split_members
                  (split_id, steam_id, display_name, percentage, is_seller, opted_out, added_at)
                VALUES (:sid, :steam, :dn, 0, 0, 0, :now)
            """),
            {
                "sid": split["id"], "steam": str(steam_id),
                "dn": mem.get("display_name") or steam_id, "now": now,
            },
        )
    db.commit()
    return get_active_team_split(db, team_id) or {}


def team_split_optout(db: Session, *, team_id: int, steam_id: str) -> dict[str, Any]:
    _require_enabled()
    split = get_active_team_split(db, team_id)
    if not split:
        raise ValueError("Sem split ACTIVE.")
    now = _naive()
    db.execute(
        text("""
            UPDATE team_split_members SET opted_out = 1, opted_out_at = :now
            WHERE split_id = :sid AND steam_id = :steam
        """),
        {"now": now, "sid": split["id"], "steam": str(steam_id)},
    )
    db.commit()
    return get_active_team_split(db, team_id) or {}


def get_team_split_snapshot_for_listing(
    db: Session,
    *,
    seller_steam_id: str,
    price: int,
) -> dict[str, Any] | None:
    """If seller is ACTIVE on a team with ACTIVE split and opted in, build snapshot."""
    if not teams_enabled():
        return None
    if price < SPLIT_MIN_SALE_AMBER:
        return None
    mem = get_active_membership(db, seller_steam_id)
    if not mem:
        return None
    split = get_active_team_split(db, int(mem["team_id"]))
    if not split:
        return None
    pool = [m for m in split["members"] if not m.get("opted_out")]
    seller = next((m for m in pool if m["steam_id"] == str(seller_steam_id)), None)
    if not seller:
        return None
    others = [m for m in pool if m["steam_id"] != str(seller_steam_id)]
    if not others:
        return None
    sender_pct = int(split["sender_pct"])
    pool_pct = int(split["pool_pct"])
    if sender_pct + pool_pct != 100:
        pool_pct = 100 - sender_pct
    # Equal share of pool among others
    n = len(others)
    base = pool_pct // n
    rem = pool_pct - base * n
    snapshot_members = [{
        "steam_id": str(seller_steam_id),
        "display_name": seller.get("display_name") or seller_steam_id,
        "percentage": sender_pct,
        "is_seller": True,
        "opted_out": False,
    }]
    for i, m in enumerate(others):
        pct = base + (1 if i < rem else 0)
        snapshot_members.append({
            "steam_id": m["steam_id"],
            "display_name": m.get("display_name") or m["steam_id"],
            "percentage": pct,
            "is_seller": False,
            "opted_out": False,
        })
    return {
        "split_id": split["id"],
        "kind": "team",
        "team_id": split["team_id"],
        "members": snapshot_members,
    }


def credit_team_bank_amber(
    db: Session,
    *,
    team_id: int,
    amount: int,
    entry_type: str,
    note: str = "",
    actor_steam_id: str = "",
    idempotency_key: str | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    """Credit Âmbares to team bank (no player debit). Used for Q10 remainder / Q12 refund."""
    amount = int(amount)
    if amount <= 0:
        bank = get_bank(db, team_id)
        return {"credited": 0, "bank": bank}
    if idempotency_key:
        prev = db.execute(
            text("SELECT id FROM team_bank_ledger WHERE idempotency_key = :k LIMIT 1"),
            {"k": str(idempotency_key)[:128]},
        ).fetchone()
        if prev:
            return {"duplicate": True, "bank": get_bank(db, team_id)}
    bank = get_bank(db, team_id)
    new_bal = int(bank["amber_balance"]) + amount
    now = _naive()
    db.execute(
        text("UPDATE team_bank SET amber_balance = :b, updated_at = :now WHERE team_id = :tid"),
        {"b": new_bal, "now": now, "tid": int(team_id)},
    )
    db.execute(
        text("""
            INSERT INTO team_bank_ledger
              (team_id, entry_type, asset_kind, asset_key, amount, balance_after,
               actor_steam_id, idempotency_key, note, created_at)
            VALUES
              (:tid, :etype, 'amber', 'amber', :amt, :bal,
               :actor, :idem, :note, :now)
        """),
        {
            "tid": int(team_id),
            "etype": str(entry_type or "CREDIT_AMBER")[:64],
            "amt": amount,
            "bal": new_bal,
            "actor": str(actor_steam_id or ""),
            "idem": (str(idempotency_key)[:128] if idempotency_key else None),
            "note": (note or "")[:255],
            "now": now,
        },
    )
    if commit:
        db.commit()
    return {"credited": amount, "bank": get_bank(db, team_id)}


def get_team_lottery_status(db: Session, team_id: int) -> dict[str, Any]:
    """Status of team lottery participation for the active campaign (for UI)."""
    out: dict[str, Any] = {
        "enabled": False,
        "campaign": None,
        "confirmed": False,
        "numbers": [],
        "numbers_count": 0,
        "can_confirm": False,
        "confirmation_deadline_ok": False,
        "shortfall_refund_per_number": lottery_shortfall_refund_amber(),
        "last_refund_notice": None,
    }
    try:
        from lottery_service import (
            _confirmation_deadline_ok,
            _is_enabled,
            get_active_campaign,
            list_team_numbers,
            _campaign_public_dict,
        )
    except Exception:
        return out
    if not _is_enabled():
        return out
    out["enabled"] = True
    campaign = get_active_campaign(db)
    if not campaign or str(campaign.status) != "ACTIVE":
        return out
    cid = int(campaign.id)
    out["campaign"] = {
        "id": cid,
        "title": str(getattr(campaign, "title", "") or ""),
        "draw_at_display": (_campaign_public_dict(campaign, db=db) or {}).get("draw_at_display"),
    }
    deadline_ok = _confirmation_deadline_ok(campaign)
    out["confirmation_deadline_ok"] = deadline_ok
    conf = db.execute(
        text(
            "SELECT confirmed_at, numbers_requested, numbers_assigned, shortfall_refunded, confirmed_by "
            "FROM team_lottery_confirmations WHERE campaign_id = :cid AND team_id = :tid"
        ),
        {"cid": cid, "tid": int(team_id)},
    ).fetchone()
    if conf:
        out["confirmed"] = True
        out["numbers_requested"] = int(conf[1] or 0)
        out["numbers_assigned"] = int(conf[2] or 0)
        out["shortfall_refunded"] = int(conf[3] or 0)
        out["confirmed_by"] = str(conf[4] or "")
        if int(conf[3] or 0) > 0:
            out["last_refund_notice"] = (
                f"Reembolso de {int(conf[3])} Âmbares ao banco da equipe "
                f"(números em falta na grade)."
            )
    else:
        out["can_confirm"] = deadline_ok
    try:
        nums = list_team_numbers(db, campaign_id=cid, team_id=int(team_id))
    except Exception:
        nums = []
    out["numbers"] = nums
    out["numbers_count"] = len(nums)
    return out


def _refund_lottery_shortfall(
    db: Session,
    *,
    team_id: int,
    shortfall: int,
    campaign_id: int,
    actor_steam_id: str = "",
    reason: str = "confirm",
) -> int:
    """Q12: credit team bank for each number that could not be allocated."""
    shortfall = max(0, int(shortfall))
    if shortfall <= 0:
        return 0
    per = lottery_shortfall_refund_amber()
    total = shortfall * per
    if total <= 0:
        return 0
    credit_team_bank_amber(
        db,
        team_id=int(team_id),
        amount=total,
        entry_type="LOTTERY_SHORTFALL_REFUND",
        note=f"Q12 reembolso {shortfall} nº × {per} Â (campanha {campaign_id}, {reason})",
        actor_steam_id=actor_steam_id,
        idempotency_key=f"team_lot_shortfall:{campaign_id}:{team_id}:{reason}:{shortfall}",
        commit=False,
    )
    return total


def maybe_allocate_lottery_on_member_join(db: Session, team_id: int) -> dict[str, Any] | None:
    """R3: after team confirmed for active campaign, new member → +2 numbers (or Q12 refund)."""
    try:
        from lottery_service import (
            _is_enabled,
            allocate_team_numbers,
            get_active_campaign,
        )
    except Exception:
        return None
    if not teams_enabled() or not _is_enabled():
        return None
    campaign = get_active_campaign(db)
    if not campaign or str(campaign.status) != "ACTIVE":
        return None
    cid = int(campaign.id)
    conf = db.execute(
        text(
            "SELECT 1 FROM team_lottery_confirmations "
            "WHERE campaign_id = :cid AND team_id = :tid"
        ),
        {"cid": cid, "tid": int(team_id)},
    ).fetchone()
    if not conf:
        return None
    result = allocate_team_numbers(
        db, campaign_id=cid, team_id=int(team_id), count=LOTTERY_NUMBERS_PER_MEMBER,
    )
    refunded = _refund_lottery_shortfall(
        db,
        team_id=int(team_id),
        shortfall=int(result.get("shortfall") or 0),
        campaign_id=cid,
        reason=f"join:{len(result.get('numbers') or [])}",
    )
    if refunded:
        db.execute(
            text("""
                UPDATE team_lottery_confirmations
                SET numbers_assigned = numbers_assigned + :a,
                    shortfall_refunded = shortfall_refunded + :r
                WHERE campaign_id = :cid AND team_id = :tid
            """),
            {
                "a": len(result.get("numbers") or []),
                "r": refunded,
                "cid": cid,
                "tid": int(team_id),
            },
        )
    else:
        db.execute(
            text("""
                UPDATE team_lottery_confirmations
                SET numbers_assigned = numbers_assigned + :a
                WHERE campaign_id = :cid AND team_id = :tid
            """),
            {"a": len(result.get("numbers") or []), "cid": cid, "tid": int(team_id)},
        )
    return {**result, "shortfall_refunded": refunded, "campaign_id": cid}


def confirm_team_lottery(
    db: Session,
    *,
    team_id: int,
    actor_steam_id: str,
    campaign_id: int | None = None,
) -> dict[str, Any]:
    """Owner confirms team lottery participation once per campaign (R1–R2, Q12)."""
    _require_enabled()
    _assert_can(db, team_id, actor_steam_id, "lottery_confirm")
    from lottery_service import (
        _confirmation_deadline_ok,
        _is_enabled,
        allocate_team_numbers,
        get_active_campaign,
        list_team_numbers,
        _fetch_campaign_row,
    )

    if not _is_enabled():
        raise ValueError("Sorteio desabilitado.")
    if campaign_id:
        campaign = _fetch_campaign_row(db, int(campaign_id))
        if not campaign or str(campaign.status) != "ACTIVE":
            raise ValueError("Campanha de sorteio não está ACTIVE.")
    else:
        campaign = get_active_campaign(db)
        if not campaign or str(campaign.status) != "ACTIVE":
            raise ValueError("Nenhuma campanha de sorteio ACTIVE.")
    cid = int(campaign.id)
    if not _confirmation_deadline_ok(campaign):
        raise ValueError(
            "O prazo para confirmar participação encerrou (2 horas antes do sorteio)."
        )
    existing = db.execute(
        text(
            "SELECT 1 FROM team_lottery_confirmations "
            "WHERE campaign_id = :cid AND team_id = :tid"
        ),
        {"cid": cid, "tid": int(team_id)},
    ).fetchone()
    if existing:
        raise ValueError("Equipe já confirmada nesta campanha.")

    n_members = count_active_members(db, team_id)
    requested = n_members * LOTTERY_NUMBERS_PER_MEMBER
    alloc = allocate_team_numbers(
        db, campaign_id=cid, team_id=int(team_id), count=requested,
    )
    shortfall = int(alloc.get("shortfall") or 0)
    refunded = _refund_lottery_shortfall(
        db,
        team_id=int(team_id),
        shortfall=shortfall,
        campaign_id=cid,
        actor_steam_id=str(actor_steam_id),
        reason="confirm",
    )
    now = _naive()
    db.execute(
        text("""
            INSERT INTO team_lottery_confirmations
              (campaign_id, team_id, confirmed_by, confirmed_at,
               numbers_requested, numbers_assigned, shortfall_refunded)
            VALUES (:cid, :tid, :by, :now, :req, :asn, :ref)
        """),
        {
            "cid": cid,
            "tid": int(team_id),
            "by": str(actor_steam_id),
            "now": now,
            "req": requested,
            "asn": len(alloc.get("numbers") or []),
            "ref": refunded,
        },
    )
    db.commit()
    nums = list_team_numbers(db, campaign_id=cid, team_id=int(team_id))
    return {
        "ok": True,
        "team_id": int(team_id),
        "campaign_id": cid,
        "members": n_members,
        "numbers_requested": requested,
        "numbers_assigned": len(nums),
        "numbers": nums,
        "shortfall": shortfall,
        "shortfall_refunded": refunded,
        "shortfall_refund_per_number": lottery_shortfall_refund_amber(),
        "message": (
            f"Participação confirmada: {len(nums)}/{requested} números."
            + (
                f" Reembolso de {refunded} Âmbares ao banco (grade insuficiente)."
                if refunded
                else ""
            )
        ),
    }


# Keep alias so old imports don't break during transition
lottery_confirm_stub = confirm_team_lottery


def my_team_or_invites(db: Session, steam_id: str) -> dict[str, Any]:
    """Aggregate for Minha Equipe / Minha Área."""
    mem = get_active_membership(db, steam_id)
    invites = db.execute(
        text("""
            SELECT m.team_id, m.invite_code, m.status, t.name, t.tag
            FROM team_members m
            JOIN teams t ON t.id = m.team_id
            WHERE m.steam_id = :sid AND m.status IN ('INVITED', 'PENDING')
              AND t.status = 'ACTIVE'
        """),
        {"sid": str(steam_id)},
    ).fetchall()
    pending_in = [
        {
            "team_id": int(r[0]),
            "invite_code": r[1],
            "status": r[2],
            "team_name": r[3],
            "tag": r[4] or "",
        }
        for r in invites
    ]
    if mem:
        tid = int(mem["team_id"])
        touch_member_activity(db, team_id=tid, steam_id=steam_id, commit=True)
        view = team_public_view(db, tid, viewer_steam_id=steam_id)
        view["pending"] = pending_in
        view["player_xp"] = my_player_rank(db, steam_id)
        roles = view.get("viewer_roles") or []
        if any(r in roles for r in (ROLE_OWNER, ROLE_GUARDIAN, ROLE_HERALD)):
            view["join_requests"] = list_members(db, tid, statuses=["PENDING"])
        else:
            view["join_requests"] = []
        return view
    return {
        "team": None,
        "members": [],
        "pending": pending_in,
        "join_requests": [],
        "player_xp": my_player_rank(db, steam_id),
        "enabled": teams_enabled(),
    }


def staff_set_team_max_members(db: Session, *, team_id: int, max_members: int) -> dict[str, Any]:
    max_members = max(2, min(100, int(max_members)))
    now = _naive()
    db.execute(
        text("UPDATE teams SET max_members = :m, updated_at = :now WHERE id = :id"),
        {"m": max_members, "now": now, "id": team_id},
    )
    db.commit()
    return get_team(db, team_id) or {}


def delete_milestone(db: Session, milestone_index: int) -> dict[str, Any]:
    db.execute(
        text("DELETE FROM team_milestones WHERE milestone_index = :i AND status = 'DRAFT'"),
        {"i": int(milestone_index)},
    )
    db.commit()
    return {"ok": True, "deleted_index": int(milestone_index)}
