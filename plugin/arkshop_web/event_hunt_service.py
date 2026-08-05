"""ArkEventHunt — Mode A (desafios por membro) + Mode B (evento público) / audit.

Schema + regras locked (PROJETO_ARK_EVENT_HUNT.md):
- Mode A: 1 claim activo por owner_steam_id; lock (steam_id, challenge_id)
- Mode B: sessão + catálogo + inscrição team; só inscritas pontuam; Team+MVP
- Score agrega na Team (event_hunt_scores); grant manual A/B
"""
from __future__ import annotations

import json
import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

log = logging.getLogger("arkshop_web.event_hunt")

_load_settings: Callable[[], dict[str, Any]] | None = None
_add_points_tx: Callable[..., Any] | None = None
_audit_event: Callable[..., Any] | None = None


class EventHuntReject(ValueError):
    """Rejeição de negócio com código estável para plugin/UI (HTTP 400/409)."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str,
        http_status: int = 400,
    ) -> None:
        super().__init__(message)
        self.error_code = str(error_code)
        self.http_status = int(http_status)

ACTIVE_CLAIM_STATUSES = ("CLAIMED", "SPAWNED")
TERMINAL_STATUSES = ("COMPLETED", "FAILED", "CANCELLED", "VOIDED")
CODE_ALPHABET = string.ascii_uppercase + string.digits
DEFAULT_CLAIM_TTL_SEC = 3600
DEFAULT_SPAWN_TTL_SEC = 900
DEFAULT_MIN_ALLOWED_WEAPON_DAMAGE_RATIO = 0.80
DEFAULT_FORBID_TORPOR = True
DEFAULT_OFFICIAL_WEAPONS_ONLY = True
DEFAULT_GRANT_WEAPON_ON_START = True
DEFAULT_GRANT_WEAPON_QTY = 1
MAX_LOOT_ROWS = 32
MAX_LOOT_QTY = 100

# Exemplos vanilla (selas / armadura / arma) — NÃO inclui ItensAlfa / Tek Alfa.
# Referência docs/UI; desafios novos começam com loot vazio.
EXAMPLE_LOOT_VANILLA: list[dict[str, Any]] = [
    {
        "blueprint": (
            "Blueprint'/Game/PrimalEarth/CoreBlueprints/Items/Armor/Saddles/"
            "PrimalItemArmor_RexSaddle.PrimalItemArmor_RexSaddle'"
        ),
        "qty": 1,
    },
    {
        "blueprint": (
            "Blueprint'/Game/PrimalEarth/CoreBlueprints/Items/Armor/Metal/"
            "PrimalItemArmor_MetalHelmet.PrimalItemArmor_MetalHelmet'"
        ),
        "qty": 1,
    },
    {
        "blueprint": (
            "Blueprint'/Game/PrimalEarth/CoreBlueprints/Weapons/"
            "PrimalItem_WeaponSword.PrimalItem_WeaponSword'"
        ),
        "qty": 1,
    },
]

# Starter library — official ASE item BPs (admin can edit/extend).
DEFAULT_WEAPON_PRESETS: list[dict[str, str]] = [
    {"name": "Arco", "blueprint": "Blueprint'/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponBow.PrimalItem_WeaponBow'", "tag": "bow"},
    {"name": "Besta", "blueprint": "Blueprint'/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponCrossbow.PrimalItem_WeaponCrossbow'", "tag": "bow"},
    {"name": "Pike", "blueprint": "Blueprint'/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponPike.PrimalItem_WeaponPike'", "tag": "melee"},
    {"name": "Lança", "blueprint": "Blueprint'/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponSpear.PrimalItem_WeaponSpear'", "tag": "melee"},
    {"name": "Espada", "blueprint": "Blueprint'/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponSword.PrimalItem_WeaponSword'", "tag": "melee"},
    {"name": "Pistola simples", "blueprint": "Blueprint'/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponSimplePistol.PrimalItem_WeaponSimplePistol'", "tag": "firearm"},
    {"name": "Espingarda", "blueprint": "Blueprint'/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponShotgun.PrimalItem_WeaponShotgun'", "tag": "firearm"},
    {"name": "Shotgun fabricada", "blueprint": "Blueprint'/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponMachinedShotgun.PrimalItem_WeaponMachinedShotgun'", "tag": "firearm"},
    {"name": "Rifle fabricado", "blueprint": "Blueprint'/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponMachinedRifle.PrimalItem_WeaponMachinedRifle'", "tag": "firearm"},
    {"name": "Sniper fabricada", "blueprint": "Blueprint'/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponMachinedSniper.PrimalItem_WeaponMachinedSniper'", "tag": "firearm"},
    {"name": "Arco composto", "blueprint": "Blueprint'/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponCompoundBow.PrimalItem_WeaponCompoundBow'", "tag": "bow"},
]


def configure_event_hunt_service(
    *,
    settings_fn: Callable[[], dict[str, Any]] | None = None,
    add_points_tx: Callable[..., Any] | None = None,
    audit_event: Callable[..., Any] | None = None,
) -> None:
    global _load_settings, _add_points_tx, _audit_event
    if settings_fn is not None:
        _load_settings = settings_fn
    if add_points_tx is not None:
        _add_points_tx = add_points_tx
    if audit_event is not None:
        _audit_event = audit_event


def _settings() -> dict[str, Any]:
    if _load_settings:
        try:
            return dict(_load_settings() or {})
        except Exception:
            return {}
    return {}


def event_hunt_enabled(settings: dict[str, Any] | None = None) -> bool:
    s = settings if settings is not None else _settings()
    if "event_hunt_enabled" not in s:
        return True
    return bool(s.get("event_hunt_enabled"))


def _require_enabled() -> None:
    if not event_hunt_enabled():
        raise PermissionError("event_hunt_enabled=false")


def _naive() -> datetime:
    return datetime.utcnow()


def _is_sqlite(db: Session) -> bool:
    try:
        return "sqlite" in str(db.get_bind().url).lower()
    except Exception:
        return False


def _last_id(db: Session) -> int:
    sql = "SELECT last_insert_rowid()" if _is_sqlite(db) else "SELECT LAST_INSERT_ID()"
    row = db.execute(text(sql)).fetchone()
    return int(row[0]) if row else 0


def _json_dumps(val: Any) -> str:
    return json.dumps(val if val is not None else [], ensure_ascii=False)


def _json_loads(raw: Any, default: Any = None) -> Any:
    if default is None:
        default = []
    if raw is None or raw == "":
        return default
    if isinstance(raw, (list, dict)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return default


# ── Schema ───────────────────────────────────────────────────────────────────


def ensure_event_hunt_schema(engine: Engine) -> None:
    """Idempotent CREATE TABLE for Event Hunt (SQLite + MySQL)."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "BIGINT AUTO_INCREMENT PRIMARY KEY"
    now_col = "DATETIME" if is_sqlite else "DATETIME(6)"
    tiny = "INTEGER" if is_sqlite else "TINYINT(1)"
    eng = "" if is_sqlite else " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"

    ddls = [
        f"""
        CREATE TABLE IF NOT EXISTS event_hunt_challenges (
          challenge_id      {pk},
          species_key       VARCHAR(64) NOT NULL DEFAULT '',
          blueprint         VARCHAR(512) NOT NULL,
          display_name      VARCHAR(128) NOT NULL,
          level             INTEGER NOT NULL DEFAULT 150,
          stats_mode        VARCHAR(16) NOT NULL DEFAULT 'RANDOM',
          allowed_weapons   TEXT NOT NULL,
          forbidden_weapons TEXT,
          points            INTEGER NOT NULL DEFAULT 0,
          amber_reward      INTEGER NOT NULL DEFAULT 0,
          claim_ttl_sec     INTEGER NOT NULL DEFAULT {DEFAULT_CLAIM_TTL_SEC},
          spawn_ttl_sec     INTEGER NOT NULL DEFAULT {DEFAULT_SPAWN_TTL_SEC},
          min_allowed_weapon_damage_ratio REAL NOT NULL DEFAULT {DEFAULT_MIN_ALLOWED_WEAPON_DAMAGE_RATIO},
          forbid_torpor     {tiny} NOT NULL DEFAULT 1,
          official_weapons_only {tiny} NOT NULL DEFAULT 1,
          grant_weapon_on_start {tiny} NOT NULL DEFAULT 1,
          grant_weapon_blueprint VARCHAR(512) NOT NULL DEFAULT '',
          grant_weapon_qty  INTEGER NOT NULL DEFAULT {DEFAULT_GRANT_WEAPON_QTY},
          loot_on_complete  TEXT,
          enabled           {tiny} NOT NULL DEFAULT 1,
          created_at        {now_col} NOT NULL,
          updated_at        {now_col} NOT NULL
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS event_hunt_weapon_presets (
          preset_id     {pk},
          name          VARCHAR(128) NOT NULL,
          blueprint     VARCHAR(512) NOT NULL,
          tag           VARCHAR(64) NOT NULL DEFAULT '',
          created_at    {now_col} NOT NULL
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS event_hunt_claims (
          claim_id              {pk},
          challenge_id          INTEGER NOT NULL,
          team_id               INTEGER NOT NULL,
          owner_steam_id        VARCHAR(32) NOT NULL,
          event_code            VARCHAR(32) NOT NULL,
          status                VARCHAR(16) NOT NULL DEFAULT 'CLAIMED',
          selected_by_steam_id  VARCHAR(32) NOT NULL,
          spawned_by_steam_id   VARCHAR(32),
          dino_id1              BIGINT,
          dino_id2              BIGINT,
          server_id             VARCHAR(64),
          map_name              VARCHAR(64),
          fail_reason           VARCHAR(64),
          points_awarded        INTEGER NOT NULL DEFAULT 0,
          amber_awarded         INTEGER NOT NULL DEFAULT 0,
          reward_status         VARCHAR(16) NOT NULL DEFAULT 'NONE',
          claim_expires_at      {now_col},
          completed_at          {now_col},
          failed_at             {now_col},
          idempotency_key       VARCHAR(128),
          created_at            {now_col} NOT NULL,
          updated_at            {now_col} NOT NULL,
          UNIQUE {"(event_code)" if is_sqlite else "KEY uq_eh_claim_code (event_code)"},
          UNIQUE {"(idempotency_key)" if is_sqlite else "KEY uq_eh_claim_idem (idempotency_key)"}
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS event_hunt_member_challenge_locks (
          steam_id      VARCHAR(32) NOT NULL,
          challenge_id  INTEGER NOT NULL,
          team_id       INTEGER NOT NULL,
          claim_id      INTEGER NOT NULL,
          outcome       VARCHAR(16) NOT NULL,
          fail_reason   VARCHAR(64),
          consumed_at   {now_col} NOT NULL,
          PRIMARY KEY (steam_id, challenge_id)
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS event_hunt_scores (
          score_id          {pk},
          mode              VARCHAR(8) NOT NULL DEFAULT 'A',
          event_session_id  INTEGER,
          team_id           INTEGER NOT NULL,
          steam_id          VARCHAR(32) NOT NULL DEFAULT '',
          points            INTEGER NOT NULL DEFAULT 0,
          amber             INTEGER NOT NULL DEFAULT 0,
          reason            VARCHAR(64) NOT NULL DEFAULT '',
          claim_id          INTEGER,
          instance_id       INTEGER,
          idempotency_key   VARCHAR(128),
          created_at        {now_col} NOT NULL,
          UNIQUE {"(idempotency_key)" if is_sqlite else "KEY uq_eh_score_idem (idempotency_key)"}
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS event_hunt_audit_events (
          audit_id          {pk},
          occurred_at       {now_col} NOT NULL,
          mode              VARCHAR(8) NOT NULL DEFAULT 'A',
          event_type        VARCHAR(32) NOT NULL,
          status            VARCHAR(16) NOT NULL DEFAULT '',
          team_id           INTEGER,
          member_steam_id   VARCHAR(32) NOT NULL DEFAULT '',
          challenge_id      INTEGER,
          public_dino_id    INTEGER,
          source_kind       VARCHAR(16) NOT NULL DEFAULT 'claim',
          source_id         INTEGER,
          points_awarded    INTEGER NOT NULL DEFAULT 0,
          amber_awarded     INTEGER NOT NULL DEFAULT 0,
          reward_status     VARCHAR(16) NOT NULL DEFAULT 'NONE',
          fail_reason       VARCHAR(64),
          note              VARCHAR(512) NOT NULL DEFAULT '',
          actor_steam_id    VARCHAR(32),
          server_id         VARCHAR(64),
          event_code        VARCHAR(32)
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS event_hunt_manual_grants (
          grant_id              {pk},
          source_kind           VARCHAR(16) NOT NULL,
          source_id             INTEGER NOT NULL,
          audit_id              INTEGER,
          team_id               INTEGER NOT NULL,
          beneficiary_steam_id  VARCHAR(32) NOT NULL DEFAULT '',
          points_granted        INTEGER NOT NULL DEFAULT 0,
          amber_granted         INTEGER NOT NULL DEFAULT 0,
          reason                VARCHAR(512) NOT NULL,
          admin_steam_id        VARCHAR(32) NOT NULL,
          created_at            {now_col} NOT NULL,
          idempotency_key       VARCHAR(128) NOT NULL,
          override_double_pay   {tiny} NOT NULL DEFAULT 0,
          UNIQUE {"(idempotency_key)" if is_sqlite else "KEY uq_eh_grant_idem (idempotency_key)"}
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS event_hunt_sessions (
          event_session_id      {pk},
          name                  VARCHAR(128) NOT NULL,
          status                VARCHAR(24) NOT NULL DEFAULT 'DRAFT',
          map_scope             VARCHAR(256) NOT NULL DEFAULT '*',
          starts_at             {now_col},
          ends_at               {now_col},
          inscription_required  {tiny} NOT NULL DEFAULT 1,
          created_at            {now_col} NOT NULL,
          updated_at            {now_col} NOT NULL
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS event_hunt_public_dinos (
          public_dino_id        {pk},
          event_session_id      INTEGER NOT NULL,
          event_code            VARCHAR(32) NOT NULL,
          display_name          VARCHAR(128) NOT NULL,
          blueprint             VARCHAR(512) NOT NULL,
          level                 INTEGER NOT NULL DEFAULT 150,
          allowed_weapons       TEXT NOT NULL,
          forbid_torpor         {tiny} NOT NULL DEFAULT 1,
          allow_personal_tames  {tiny} NOT NULL DEFAULT 0,
          min_allowed_weapon_damage_ratio REAL NOT NULL DEFAULT {DEFAULT_MIN_ALLOWED_WEAPON_DAMAGE_RATIO},
          official_weapons_only {tiny} NOT NULL DEFAULT 1,
          points_team           INTEGER NOT NULL DEFAULT 0,
          points_mvp            INTEGER NOT NULL DEFAULT 0,
          amber_team            INTEGER NOT NULL DEFAULT 0,
          amber_mvp             INTEGER NOT NULL DEFAULT 0,
          rank_rewards_json     TEXT,
          loot_on_complete      TEXT,
          ttl_sec               INTEGER NOT NULL DEFAULT 0,
          sort_order            INTEGER NOT NULL DEFAULT 0,
          enabled               {tiny} NOT NULL DEFAULT 1,
          created_at            {now_col} NOT NULL,
          updated_at            {now_col} NOT NULL,
          UNIQUE {"(event_code)" if is_sqlite else "KEY uq_eh_pd_code (event_code)"}
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS event_hunt_inscriptions (
          inscription_id        {pk},
          event_session_id      INTEGER NOT NULL,
          team_id               INTEGER NOT NULL,
          inscribed_by_steam_id VARCHAR(32) NOT NULL DEFAULT '',
          inscribed_at          {now_col} NOT NULL,
          status                VARCHAR(16) NOT NULL DEFAULT 'ACTIVE',
          UNIQUE {"(event_session_id, team_id)" if is_sqlite else "KEY uq_eh_insc (event_session_id, team_id)"}
        ){eng}
        """,
        f"""
        CREATE TABLE IF NOT EXISTS event_hunt_instances (
          instance_id           {pk},
          event_session_id      INTEGER NOT NULL,
          public_dino_id        INTEGER NOT NULL,
          event_code            VARCHAR(32) NOT NULL,
          status                VARCHAR(16) NOT NULL DEFAULT 'ALIVE',
          dino_id1              BIGINT,
          dino_id2              BIGINT,
          spawned_by_admin      VARCHAR(32),
          server_id             VARCHAR(64),
          map_name              VARCHAR(64),
          expires_at            {now_col},
          warned_1min           {tiny} NOT NULL DEFAULT 0,
          killer_steam_id       VARCHAR(32),
          killer_team_id        INTEGER,
          fail_reason           VARCHAR(64),
          points_awarded        INTEGER NOT NULL DEFAULT 0,
          amber_awarded         INTEGER NOT NULL DEFAULT 0,
          reward_status         VARCHAR(16) NOT NULL DEFAULT 'NONE',
          idempotency_key       VARCHAR(128),
          spawned_at            {now_col},
          killed_at             {now_col},
          expired_at            {now_col},
          created_at            {now_col} NOT NULL,
          updated_at            {now_col} NOT NULL,
          UNIQUE {"(idempotency_key)" if is_sqlite else "KEY uq_eh_inst_idem (idempotency_key)"}
        ){eng}
        """,
    ]

    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_eh_claims_owner_status ON event_hunt_claims (owner_steam_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_eh_claims_team ON event_hunt_claims (team_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_eh_claims_challenge ON event_hunt_claims (challenge_id)",
        "CREATE INDEX IF NOT EXISTS ix_eh_scores_team ON event_hunt_scores (team_id, mode)",
        "CREATE INDEX IF NOT EXISTS ix_eh_audit_occurred ON event_hunt_audit_events (occurred_at)",
        "CREATE INDEX IF NOT EXISTS ix_eh_audit_team ON event_hunt_audit_events (team_id)",
        "CREATE INDEX IF NOT EXISTS ix_eh_challenges_enabled ON event_hunt_challenges (enabled)",
        "CREATE INDEX IF NOT EXISTS ix_eh_sessions_status ON event_hunt_sessions (status)",
        "CREATE INDEX IF NOT EXISTS ix_eh_pd_session ON event_hunt_public_dinos (event_session_id)",
        "CREATE INDEX IF NOT EXISTS ix_eh_insc_session ON event_hunt_inscriptions (event_session_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_eh_inst_session ON event_hunt_instances (event_session_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_eh_inst_code ON event_hunt_instances (event_code)",
        "CREATE INDEX IF NOT EXISTS ix_eh_scores_session ON event_hunt_scores (event_session_id, mode)",
    ]

    with engine.begin() as conn:
        for ddl in ddls:
            conn.execute(text(ddl))
        for ix in indexes:
            try:
                conn.execute(text(ix))
            except Exception as exc:
                log.debug("event_hunt index skip: %s (%s)", ix, exc)
        _migrate_challenge_weapon_rules(conn, is_sqlite, tiny)
        _migrate_public_dino_loot(conn, is_sqlite)
        _migrate_scores_session_col(conn, is_sqlite)
        _seed_weapon_presets_if_empty(conn)


def _add_column_if_missing(
    conn: Any, *, table: str, col: str, col_type: str, is_sqlite: bool
) -> None:
    try:
        if is_sqlite:
            existing = [
                r[1]
                for r in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            ]
            if col not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
        else:
            row = conn.execute(
                text(f"SHOW COLUMNS FROM `{table}` LIKE '{col}'")
            ).fetchone()
            if row is None:
                conn.execute(
                    text(f"ALTER TABLE `{table}` ADD COLUMN `{col}` {col_type}")
                )
    except Exception as exc:
        log.debug("event_hunt migrate %s.%s: %s", table, col, exc)


def _migrate_challenge_weapon_rules(conn: Any, is_sqlite: bool, tiny: str) -> None:
    """Add damage-ratio / torpor / official-only / grant / loot columns on existing DBs."""
    cols = [
        (
            "min_allowed_weapon_damage_ratio",
            f"REAL NOT NULL DEFAULT {DEFAULT_MIN_ALLOWED_WEAPON_DAMAGE_RATIO}",
        ),
        ("forbid_torpor", f"{tiny} NOT NULL DEFAULT 1"),
        ("official_weapons_only", f"{tiny} NOT NULL DEFAULT 1"),
        ("grant_weapon_on_start", f"{tiny} NOT NULL DEFAULT 1"),
        ("grant_weapon_blueprint", "VARCHAR(512) NOT NULL DEFAULT ''"),
        (
            "grant_weapon_qty",
            f"INTEGER NOT NULL DEFAULT {DEFAULT_GRANT_WEAPON_QTY}",
        ),
        ("loot_on_complete", "TEXT"),
    ]
    for col, col_type in cols:
        _add_column_if_missing(
            conn, table="event_hunt_challenges", col=col, col_type=col_type, is_sqlite=is_sqlite
        )


def _migrate_public_dino_loot(conn: Any, is_sqlite: bool) -> None:
    """Add loot_on_complete on Mode B public dinos."""
    _add_column_if_missing(
        conn,
        table="event_hunt_public_dinos",
        col="loot_on_complete",
        col_type="TEXT",
        is_sqlite=is_sqlite,
    )


def _migrate_scores_session_col(conn: Any, is_sqlite: bool) -> None:
    """Add event_session_id on event_hunt_scores for Mode B leaderboards."""
    try:
        if is_sqlite:
            existing = [
                r[1]
                for r in conn.execute(text("PRAGMA table_info(event_hunt_scores)")).fetchall()
            ]
            if "event_session_id" not in existing:
                conn.execute(
                    text("ALTER TABLE event_hunt_scores ADD COLUMN event_session_id INTEGER")
                )
        else:
            row = conn.execute(
                text("SHOW COLUMNS FROM `event_hunt_scores` LIKE 'event_session_id'")
            ).fetchone()
            if row is None:
                conn.execute(
                    text(
                        "ALTER TABLE `event_hunt_scores` ADD COLUMN `event_session_id` INTEGER NULL"
                    )
                )
    except Exception as exc:
        log.debug("event_hunt migrate scores.session: %s", exc)


def _seed_weapon_presets_if_empty(conn: Any) -> None:
    try:
        row = conn.execute(
            text("SELECT COUNT(1) FROM event_hunt_weapon_presets")
        ).fetchone()
        if row and int(row[0] or 0) > 0:
            return
        now = datetime.utcnow()
        for p in DEFAULT_WEAPON_PRESETS:
            conn.execute(
                text("""
                    INSERT INTO event_hunt_weapon_presets (name, blueprint, tag, created_at)
                    VALUES (:n, :bp, :tag, :now)
                """),
                {
                    "n": p["name"][:128],
                    "bp": p["blueprint"][:512],
                    "tag": (p.get("tag") or "")[:64],
                    "now": now,
                },
            )
        log.info(
            "event_hunt: seeded %s weapon presets", len(DEFAULT_WEAPON_PRESETS)
        )
    except Exception as exc:
        log.debug("event_hunt seed presets: %s", exc)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _clamp_ratio(value: Any, default: float = DEFAULT_MIN_ALLOWED_WEAPON_DAMAGE_RATIO) -> float:
    try:
        r = float(value)
    except (TypeError, ValueError):
        r = float(default)
    if r < 0.0:
        return 0.0
    if r > 1.0:
        return 1.0
    return r


def _looks_like_alpha_loot(blueprint: str) -> bool:
    """Heuristic: ItensAlfa / Tek Alfa / shop alpha kits — never in seeds/examples."""
    s = (blueprint or "").lower()
    needles = (
        "itensalfa",
        "itens_alfa",
        "itemsalfa",
        "tekalfa",
        "tek_alfa",
        "alphaarmor",
        "alpha_armor",
        "primalitemarmor_alpha",
        "primalitem_weaponalpha",
        "/alfa/",
        "_alfa",
        "alfa'",
    )
    return any(n in s for n in needles)


def _normalize_loot_on_complete(raw: Any, *, strip_alpha: bool = False) -> list[dict[str, Any]]:
    """Normalize `[{blueprint, qty}, ...]` for challenges / public dinos."""
    if raw is None or raw == "":
        return []
    if isinstance(raw, str):
        raw = _json_loads(raw, [])
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            bp = item.strip()
            qty = 1
        elif isinstance(item, dict):
            bp = str(item.get("blueprint") or item.get("bp") or "").strip()
            try:
                qty = int(item.get("qty") if item.get("qty") is not None else item.get("quantity") or 1)
            except (TypeError, ValueError):
                qty = 1
        else:
            continue
        if not bp:
            continue
        if strip_alpha and _looks_like_alpha_loot(bp):
            continue
        qty = max(1, min(MAX_LOOT_QTY, qty))
        out.append({"blueprint": bp[:512], "qty": qty})
        if len(out) >= MAX_LOOT_ROWS:
            break
    return out


def _row_challenge(row: Any) -> dict[str, Any]:
    """Map SELECT `_CHALLENGE_COLS` → dict."""
    n = len(row) if row is not None else 0

    def _at(i: int, default: Any = None) -> Any:
        return row[i] if n > i else default

    return {
        "challenge_id": int(row[0]),
        "species_key": row[1] or "",
        "blueprint": row[2] or "",
        "display_name": row[3] or "",
        "level": int(row[4] or 150),
        "stats_mode": row[5] or "RANDOM",
        "allowed_weapons": _json_loads(row[6], []),
        "forbidden_weapons": _json_loads(row[7], []),
        "points": int(row[8] or 0),
        "amber_reward": int(row[9] or 0),
        "claim_ttl_sec": int(row[10] or DEFAULT_CLAIM_TTL_SEC),
        "spawn_ttl_sec": int(row[11] or DEFAULT_SPAWN_TTL_SEC),
        "min_allowed_weapon_damage_ratio": _clamp_ratio(
            _at(12, DEFAULT_MIN_ALLOWED_WEAPON_DAMAGE_RATIO)
        ),
        "forbid_torpor": bool(_at(13, DEFAULT_FORBID_TORPOR)),
        "official_weapons_only": bool(_at(14, DEFAULT_OFFICIAL_WEAPONS_ONLY)),
        "grant_weapon_on_start": bool(_at(15, DEFAULT_GRANT_WEAPON_ON_START)),
        "grant_weapon_blueprint": str(_at(16, "") or ""),
        "grant_weapon_qty": int(_at(17, DEFAULT_GRANT_WEAPON_QTY) or DEFAULT_GRANT_WEAPON_QTY),
        "loot_on_complete": _normalize_loot_on_complete(_at(18, [])),
        "enabled": bool(_at(19, True)),
        "created_at": str(_at(20)) if _at(20) else None,
        "updated_at": str(_at(21)) if _at(21) else None,
    }


_CHALLENGE_COLS = """
  challenge_id, species_key, blueprint, display_name, level, stats_mode,
  allowed_weapons, forbidden_weapons, points, amber_reward,
  claim_ttl_sec, spawn_ttl_sec,
  min_allowed_weapon_damage_ratio, forbid_torpor, official_weapons_only,
  grant_weapon_on_start, grant_weapon_blueprint, grant_weapon_qty,
  loot_on_complete, enabled, created_at, updated_at
"""


def get_challenge(db: Session, challenge_id: int) -> dict[str, Any] | None:
    row = db.execute(
        text(f"SELECT {_CHALLENGE_COLS} FROM event_hunt_challenges WHERE challenge_id = :id"),
        {"id": int(challenge_id)},
    ).fetchone()
    return _row_challenge(row) if row else None


def _row_claim(row: Any) -> dict[str, Any]:
    return {
        "claim_id": int(row[0]),
        "challenge_id": int(row[1]),
        "team_id": int(row[2]),
        "owner_steam_id": str(row[3] or ""),
        "event_code": str(row[4] or ""),
        "status": str(row[5] or ""),
        "selected_by_steam_id": str(row[6] or ""),
        "spawned_by_steam_id": str(row[7] or "") if row[7] else None,
        "dino_id1": int(row[8]) if row[8] is not None else None,
        "dino_id2": int(row[9]) if row[9] is not None else None,
        "server_id": row[10],
        "map_name": row[11],
        "fail_reason": row[12],
        "points_awarded": int(row[13] or 0),
        "amber_awarded": int(row[14] or 0),
        "reward_status": str(row[15] or "NONE"),
        "claim_expires_at": str(row[16]) if row[16] else None,
        "completed_at": str(row[17]) if row[17] else None,
        "failed_at": str(row[18]) if row[18] else None,
        "idempotency_key": row[19],
        "created_at": str(row[20]) if row[20] else None,
        "updated_at": str(row[21]) if row[21] else None,
    }


_CLAIM_COLS = """
  claim_id, challenge_id, team_id, owner_steam_id, event_code, status,
  selected_by_steam_id, spawned_by_steam_id, dino_id1, dino_id2,
  server_id, map_name, fail_reason, points_awarded, amber_awarded, reward_status,
  claim_expires_at, completed_at, failed_at, idempotency_key, created_at, updated_at
"""


def get_claim(db: Session, claim_id: int) -> dict[str, Any] | None:
    row = db.execute(
        text(f"SELECT {_CLAIM_COLS} FROM event_hunt_claims WHERE claim_id = :id"),
        {"id": int(claim_id)},
    ).fetchone()
    return _row_claim(row) if row else None


def get_claim_by_code(db: Session, event_code: str) -> dict[str, Any] | None:
    code = str(event_code or "").strip().upper()
    if not code:
        return None
    row = db.execute(
        text(f"SELECT {_CLAIM_COLS} FROM event_hunt_claims WHERE event_code = :c"),
        {"c": code},
    ).fetchone()
    return _row_claim(row) if row else None


def _active_claim_for_member(db: Session, steam_id: str) -> dict[str, Any] | None:
    row = db.execute(
        text(f"""
            SELECT {_CLAIM_COLS} FROM event_hunt_claims
            WHERE owner_steam_id = :s AND status IN ('CLAIMED', 'SPAWNED')
            ORDER BY claim_id DESC LIMIT 1
        """),
        {"s": str(steam_id)},
    ).fetchone()
    return _row_claim(row) if row else None


def member_has_lock(db: Session, steam_id: str, challenge_id: int) -> bool:
    row = db.execute(
        text("""
            SELECT 1 FROM event_hunt_member_challenge_locks
            WHERE steam_id = :s AND challenge_id = :c LIMIT 1
        """),
        {"s": str(steam_id), "c": int(challenge_id)},
    ).fetchone()
    return row is not None


def get_member_lock(db: Session, steam_id: str, challenge_id: int) -> dict[str, Any] | None:
    row = db.execute(
        text("""
            SELECT steam_id, challenge_id, team_id, claim_id, outcome, fail_reason, consumed_at
            FROM event_hunt_member_challenge_locks
            WHERE steam_id = :s AND challenge_id = :c LIMIT 1
        """),
        {"s": str(steam_id), "c": int(challenge_id)},
    ).fetchone()
    if not row:
        return None
    return {
        "steam_id": row[0],
        "challenge_id": int(row[1]),
        "team_id": int(row[2]),
        "claim_id": int(row[3]),
        "outcome": row[4],
        "fail_reason": row[5],
        "consumed_at": str(row[6]) if row[6] else None,
    }


def _require_active_membership(db: Session, steam_id: str) -> dict[str, Any]:
    from team_service import get_active_membership

    mem = get_active_membership(db, str(steam_id))
    if not mem:
        raise PermissionError("Precisas de uma equipe ACTIVE.")
    return mem


def _reserve_event_code(db: Session) -> str:
    for _ in range(40):
        body = "".join(secrets.choice(CODE_ALPHABET) for _ in range(5))
        code = f"E{body}"
        exists_a = db.execute(
            text("SELECT 1 FROM event_hunt_claims WHERE event_code = :c LIMIT 1"),
            {"c": code},
        ).fetchone()
        exists_b = db.execute(
            text("SELECT 1 FROM event_hunt_public_dinos WHERE event_code = :c LIMIT 1"),
            {"c": code},
        ).fetchone()
        if not exists_a and not exists_b:
            return code
    raise RuntimeError("Não foi possível reservar event_code.")


def _append_audit(
    db: Session,
    *,
    event_type: str,
    status: str = "",
    mode: str = "A",
    team_id: int | None = None,
    member_steam_id: str = "",
    challenge_id: int | None = None,
    public_dino_id: int | None = None,
    source_kind: str = "claim",
    source_id: int | None = None,
    points_awarded: int = 0,
    amber_awarded: int = 0,
    reward_status: str = "NONE",
    fail_reason: str | None = None,
    note: str = "",
    actor_steam_id: str | None = None,
    server_id: str | None = None,
    event_code: str | None = None,
) -> int:
    now = _naive()
    db.execute(
        text("""
            INSERT INTO event_hunt_audit_events (
              occurred_at, mode, event_type, status, team_id, member_steam_id,
              challenge_id, public_dino_id, source_kind, source_id,
              points_awarded, amber_awarded, reward_status, fail_reason, note,
              actor_steam_id, server_id, event_code
            ) VALUES (
              :now, :mode, :etype, :status, :tid, :member,
              :cid, :pdid, :skind, :sid,
              :pts, :amb, :rstat, :fail, :note,
              :actor, :server, :ecode
            )
        """),
        {
            "now": now,
            "mode": mode,
            "etype": event_type,
            "status": status,
            "tid": team_id,
            "member": member_steam_id or "",
            "cid": challenge_id,
            "pdid": public_dino_id,
            "skind": source_kind,
            "sid": source_id,
            "pts": int(points_awarded or 0),
            "amb": int(amber_awarded or 0),
            "rstat": reward_status or "NONE",
            "fail": fail_reason,
            "note": (note or "")[:512],
            "actor": actor_steam_id,
            "server": server_id,
            "ecode": event_code,
        },
    )
    return _last_id(db)


def _insert_lock(
    db: Session,
    *,
    steam_id: str,
    challenge_id: int,
    team_id: int,
    claim_id: int,
    outcome: str,
    fail_reason: str | None = None,
) -> None:
    db.execute(
        text("""
            INSERT INTO event_hunt_member_challenge_locks
              (steam_id, challenge_id, team_id, claim_id, outcome, fail_reason, consumed_at)
            VALUES
              (:s, :c, :tid, :cid, :out, :fail, :now)
        """),
        {
            "s": str(steam_id),
            "c": int(challenge_id),
            "tid": int(team_id),
            "cid": int(claim_id),
            "out": outcome,
            "fail": fail_reason,
            "now": _naive(),
        },
    )


def _credit_team_amber(
    db: Session,
    *,
    team_id: int,
    amount: int,
    actor_steam_id: str,
    idempotency_key: str,
    note: str,
) -> None:
    if amount <= 0:
        return
    prev = db.execute(
        text("SELECT id FROM team_bank_ledger WHERE idempotency_key = :k LIMIT 1"),
        {"k": idempotency_key[:128]},
    ).fetchone()
    if prev:
        return
    # Ensure bank row
    bank = db.execute(
        text("SELECT amber_balance FROM team_bank WHERE team_id = :tid"),
        {"tid": int(team_id)},
    ).fetchone()
    if not bank:
        db.execute(
            text("""
                INSERT INTO team_bank (team_id, amber_balance, resources_json, committed_json, updated_at)
                VALUES (:tid, 0, '{}', '{}', :now)
            """),
            {"tid": int(team_id), "now": _naive()},
        )
        bal = 0
    else:
        bal = int(bank[0] or 0)
    new_bal = bal + int(amount)
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
              (:tid, 'HUNT_AMBER', 'amber', 'amber', :amt, :bal,
               :actor, :idem, :note, :now)
        """),
        {
            "tid": int(team_id),
            "amt": int(amount),
            "bal": new_bal,
            "actor": str(actor_steam_id),
            "idem": idempotency_key[:128],
            "note": (note or "Event Hunt")[:255],
            "now": now,
        },
    )


def _record_score(
    db: Session,
    *,
    team_id: int,
    steam_id: str,
    points: int,
    amber: int,
    reason: str,
    claim_id: int | None = None,
    instance_id: int | None = None,
    event_session_id: int | None = None,
    idempotency_key: str,
    mode: str = "A",
) -> None:
    prev = db.execute(
        text("SELECT score_id FROM event_hunt_scores WHERE idempotency_key = :k LIMIT 1"),
        {"k": idempotency_key[:128]},
    ).fetchone()
    if prev:
        return
    db.execute(
        text("""
            INSERT INTO event_hunt_scores
              (mode, event_session_id, team_id, steam_id, points, amber, reason,
               claim_id, instance_id, idempotency_key, created_at)
            VALUES
              (:mode, :esid, :tid, :sid, :pts, :amb, :reason,
               :cid, :iid, :idem, :now)
        """),
        {
            "mode": mode,
            "esid": int(event_session_id) if event_session_id is not None else None,
            "tid": int(team_id),
            "sid": str(steam_id),
            "pts": int(points),
            "amb": int(amber),
            "reason": reason[:64],
            "cid": int(claim_id) if claim_id is not None else None,
            "iid": int(instance_id) if instance_id is not None else None,
            "idem": idempotency_key[:128],
            "now": _naive(),
        },
    )


def team_hunt_score_totals(db: Session, team_id: int, mode: str = "A") -> dict[str, Any]:
    row = db.execute(
        text("""
            SELECT COALESCE(SUM(points),0), COALESCE(SUM(amber),0)
            FROM event_hunt_scores WHERE team_id = :tid AND mode = :mode
        """),
        {"tid": int(team_id), "mode": mode},
    ).fetchone()
    completed = db.execute(
        text("""
            SELECT COUNT(*) FROM event_hunt_claims
            WHERE team_id = :tid AND status = 'COMPLETED'
        """),
        {"tid": int(team_id)},
    ).fetchone()
    failed = db.execute(
        text("""
            SELECT COUNT(*) FROM event_hunt_claims
            WHERE team_id = :tid AND status = 'FAILED'
        """),
        {"tid": int(team_id)},
    ).fetchone()
    return {
        "hunt_points_total": int(row[0] or 0) if row else 0,
        "amber_total": int(row[1] or 0) if row else 0,
        "completed_count_team": int(completed[0] or 0) if completed else 0,
        "failed_count_team": int(failed[0] or 0) if failed else 0,
    }


# ── Catalog A ────────────────────────────────────────────────────────────────


def list_challenges(
    db: Session,
    *,
    enabled_only: bool = False,
    steam_id: str | None = None,
    available_for_me: bool = False,
) -> list[dict[str, Any]]:
    sql = f"SELECT {_CHALLENGE_COLS} FROM event_hunt_challenges"
    params: dict[str, Any] = {}
    if enabled_only or available_for_me:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY challenge_id ASC"
    rows = db.execute(text(sql), params).fetchall()
    items = [_row_challenge(r) for r in rows]

    locks: set[int] = set()
    active = None
    if steam_id:
        lock_rows = db.execute(
            text("SELECT challenge_id FROM event_hunt_member_challenge_locks WHERE steam_id = :s"),
            {"s": str(steam_id)},
        ).fetchall()
        locks = {int(r[0]) for r in lock_rows}
        active = _active_claim_for_member(db, steam_id)

    out: list[dict[str, Any]] = []
    for ch in items:
        cid = ch["challenge_id"]
        state = "available"
        if not ch["enabled"]:
            state = "disabled"
        elif cid in locks:
            state = "consumed"
        elif active and active["status"] in ACTIVE_CLAIM_STATUSES:
            state = "locked_active"
        ch = dict(ch)
        ch["availability"] = state
        ch["consumed_by_me"] = cid in locks
        if available_for_me and state != "available":
            continue
        out.append(ch)
    return out


def admin_create_challenge(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    _require_enabled()
    blueprint = str(payload.get("blueprint") or "").strip()
    display_name = str(payload.get("display_name") or "").strip()
    if not blueprint:
        raise ValueError("blueprint é obrigatório.")
    if not display_name:
        raise ValueError("display_name é obrigatório.")
    now = _naive()
    ratio = _clamp_ratio(
        payload.get(
            "min_allowed_weapon_damage_ratio",
            DEFAULT_MIN_ALLOWED_WEAPON_DAMAGE_RATIO,
        )
    )
    forbid = (
        DEFAULT_FORBID_TORPOR
        if "forbid_torpor" not in payload
        else bool(payload.get("forbid_torpor"))
    )
    official = (
        DEFAULT_OFFICIAL_WEAPONS_ONLY
        if "official_weapons_only" not in payload
        else bool(payload.get("official_weapons_only"))
    )
    grant_on = (
        DEFAULT_GRANT_WEAPON_ON_START
        if "grant_weapon_on_start" not in payload
        else bool(payload.get("grant_weapon_on_start"))
    )
    grant_bp = str(payload.get("grant_weapon_blueprint") or "").strip()[:512]
    grant_qty = max(1, int(payload.get("grant_weapon_qty") or DEFAULT_GRANT_WEAPON_QTY))
    loot = _normalize_loot_on_complete(payload.get("loot_on_complete"))
    db.execute(
        text("""
            INSERT INTO event_hunt_challenges (
              species_key, blueprint, display_name, level, stats_mode,
              allowed_weapons, forbidden_weapons, points, amber_reward,
              claim_ttl_sec, spawn_ttl_sec,
              min_allowed_weapon_damage_ratio, forbid_torpor, official_weapons_only,
              grant_weapon_on_start, grant_weapon_blueprint, grant_weapon_qty,
              loot_on_complete, enabled, created_at, updated_at
            ) VALUES (
              :sk, :bp, :dn, :lvl, :sm,
              :aw, :fw, :pts, :amb,
              :cttl, :sttl,
              :ratio, :forbid, :official,
              :grant_on, :grant_bp, :grant_qty,
              :loot, :en, :now, :now
            )
        """),
        {
            "sk": str(payload.get("species_key") or "")[:64],
            "bp": blueprint[:512],
            "dn": display_name[:128],
            "lvl": int(payload.get("level") or 150),
            "sm": str(payload.get("stats_mode") or "RANDOM")[:16],
            "aw": _json_dumps(payload.get("allowed_weapons") or []),
            "fw": _json_dumps(payload.get("forbidden_weapons") or []),
            "pts": int(payload.get("points") or 0),
            "amb": int(payload.get("amber_reward") or 0),
            "cttl": int(payload.get("claim_ttl_sec") or DEFAULT_CLAIM_TTL_SEC),
            "sttl": int(payload.get("spawn_ttl_sec") or DEFAULT_SPAWN_TTL_SEC),
            "ratio": ratio,
            "forbid": 1 if forbid else 0,
            "official": 1 if official else 0,
            "grant_on": 1 if grant_on else 0,
            "grant_bp": grant_bp,
            "grant_qty": grant_qty,
            "loot": _json_dumps(loot),
            "en": 1 if payload.get("enabled", True) else 0,
            "now": now,
        },
    )
    cid = _last_id(db)
    db.commit()
    return get_challenge(db, cid)  # type: ignore[return-value]


def admin_update_challenge(db: Session, challenge_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    _require_enabled()
    ch = get_challenge(db, challenge_id)
    if not ch:
        raise LookupError("Desafio não encontrado.")
    fields = {
        "species_key": str(payload.get("species_key", ch["species_key"]))[:64],
        "blueprint": str(payload.get("blueprint", ch["blueprint"]))[:512],
        "display_name": str(payload.get("display_name", ch["display_name"]))[:128],
        "level": int(payload.get("level", ch["level"])),
        "stats_mode": str(payload.get("stats_mode", ch["stats_mode"]))[:16],
        "allowed_weapons": _json_dumps(payload["allowed_weapons"] if "allowed_weapons" in payload else ch["allowed_weapons"]),
        "forbidden_weapons": _json_dumps(payload["forbidden_weapons"] if "forbidden_weapons" in payload else ch["forbidden_weapons"]),
        "points": int(payload.get("points", ch["points"])),
        "amber_reward": int(payload.get("amber_reward", ch["amber_reward"])),
        "claim_ttl_sec": int(payload.get("claim_ttl_sec", ch["claim_ttl_sec"])),
        "spawn_ttl_sec": int(payload.get("spawn_ttl_sec", ch["spawn_ttl_sec"])),
        "min_allowed_weapon_damage_ratio": _clamp_ratio(
            payload.get(
                "min_allowed_weapon_damage_ratio",
                ch.get(
                    "min_allowed_weapon_damage_ratio",
                    DEFAULT_MIN_ALLOWED_WEAPON_DAMAGE_RATIO,
                ),
            )
        ),
        "forbid_torpor": 1 if bool(
            payload["forbid_torpor"]
            if "forbid_torpor" in payload
            else ch.get("forbid_torpor", DEFAULT_FORBID_TORPOR)
        ) else 0,
        "official_weapons_only": 1 if bool(
            payload["official_weapons_only"]
            if "official_weapons_only" in payload
            else ch.get("official_weapons_only", DEFAULT_OFFICIAL_WEAPONS_ONLY)
        ) else 0,
        "grant_weapon_on_start": 1 if bool(
            payload["grant_weapon_on_start"]
            if "grant_weapon_on_start" in payload
            else ch.get("grant_weapon_on_start", DEFAULT_GRANT_WEAPON_ON_START)
        ) else 0,
        "grant_weapon_blueprint": str(
            payload["grant_weapon_blueprint"]
            if "grant_weapon_blueprint" in payload
            else ch.get("grant_weapon_blueprint") or ""
        ).strip()[:512],
        "grant_weapon_qty": max(
            1,
            int(
                payload["grant_weapon_qty"]
                if "grant_weapon_qty" in payload
                else ch.get("grant_weapon_qty", DEFAULT_GRANT_WEAPON_QTY)
            ),
        ),
        "loot_on_complete": _json_dumps(
            _normalize_loot_on_complete(
                payload["loot_on_complete"]
                if "loot_on_complete" in payload
                else ch.get("loot_on_complete") or []
            )
        ),
        "enabled": 1 if payload.get("enabled", ch["enabled"]) else 0,
        "now": _naive(),
        "id": int(challenge_id),
    }
    if not fields["blueprint"]:
        raise ValueError("blueprint é obrigatório.")
    if not fields["display_name"]:
        raise ValueError("display_name é obrigatório.")
    db.execute(
        text("""
            UPDATE event_hunt_challenges SET
              species_key=:species_key, blueprint=:blueprint, display_name=:display_name,
              level=:level, stats_mode=:stats_mode,
              allowed_weapons=:allowed_weapons, forbidden_weapons=:forbidden_weapons,
              points=:points, amber_reward=:amber_reward,
              claim_ttl_sec=:claim_ttl_sec, spawn_ttl_sec=:spawn_ttl_sec,
              min_allowed_weapon_damage_ratio=:min_allowed_weapon_damage_ratio,
              forbid_torpor=:forbid_torpor,
              official_weapons_only=:official_weapons_only,
              grant_weapon_on_start=:grant_weapon_on_start,
              grant_weapon_blueprint=:grant_weapon_blueprint,
              grant_weapon_qty=:grant_weapon_qty,
              loot_on_complete=:loot_on_complete,
              enabled=:enabled, updated_at=:now
            WHERE challenge_id=:id
        """),
        fields,
    )
    db.commit()
    return get_challenge(db, challenge_id)  # type: ignore[return-value]


def admin_disable_challenge(db: Session, challenge_id: int) -> dict[str, Any]:
    return admin_update_challenge(db, challenge_id, {"enabled": False})


# ── Weapon presets (admin library) ───────────────────────────────────────────


def _row_weapon_preset(row: Any) -> dict[str, Any]:
    return {
        "preset_id": int(row[0]),
        "name": str(row[1] or ""),
        "blueprint": str(row[2] or ""),
        "tag": str(row[3] or ""),
        "created_at": str(row[4]) if row[4] else None,
    }


def list_weapon_presets(db: Session) -> list[dict[str, Any]]:
    _require_enabled()
    rows = db.execute(
        text("""
            SELECT preset_id, name, blueprint, tag, created_at
            FROM event_hunt_weapon_presets
            ORDER BY tag ASC, name ASC, preset_id ASC
        """)
    ).fetchall()
    return [_row_weapon_preset(r) for r in rows]


def admin_create_weapon_preset(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    _require_enabled()
    name = str(payload.get("name") or "").strip()
    blueprint = str(payload.get("blueprint") or "").strip()
    if not name:
        raise ValueError("name é obrigatório.")
    if not blueprint:
        raise ValueError("blueprint é obrigatório.")
    tag = str(payload.get("tag") or "").strip()[:64]
    now = _naive()
    db.execute(
        text("""
            INSERT INTO event_hunt_weapon_presets (name, blueprint, tag, created_at)
            VALUES (:n, :bp, :tag, :now)
        """),
        {"n": name[:128], "bp": blueprint[:512], "tag": tag, "now": now},
    )
    pid = _last_id(db)
    db.commit()
    row = db.execute(
        text("""
            SELECT preset_id, name, blueprint, tag, created_at
            FROM event_hunt_weapon_presets WHERE preset_id = :id
        """),
        {"id": pid},
    ).fetchone()
    return _row_weapon_preset(row)


def admin_update_weapon_preset(
    db: Session, preset_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    _require_enabled()
    row = db.execute(
        text("""
            SELECT preset_id, name, blueprint, tag, created_at
            FROM event_hunt_weapon_presets WHERE preset_id = :id
        """),
        {"id": int(preset_id)},
    ).fetchone()
    if not row:
        raise LookupError("Preset não encontrado.")
    cur = _row_weapon_preset(row)
    name = str(payload.get("name", cur["name"])).strip()[:128]
    blueprint = str(payload.get("blueprint", cur["blueprint"])).strip()[:512]
    tag = str(payload.get("tag", cur["tag"])).strip()[:64]
    if not name:
        raise ValueError("name é obrigatório.")
    if not blueprint:
        raise ValueError("blueprint é obrigatório.")
    db.execute(
        text("""
            UPDATE event_hunt_weapon_presets
            SET name=:n, blueprint=:bp, tag=:tag
            WHERE preset_id=:id
        """),
        {"n": name, "bp": blueprint, "tag": tag, "id": int(preset_id)},
    )
    db.commit()
    row2 = db.execute(
        text("""
            SELECT preset_id, name, blueprint, tag, created_at
            FROM event_hunt_weapon_presets WHERE preset_id = :id
        """),
        {"id": int(preset_id)},
    ).fetchone()
    return _row_weapon_preset(row2)


def admin_delete_weapon_preset(db: Session, preset_id: int) -> dict[str, Any]:
    _require_enabled()
    row = db.execute(
        text("""
            SELECT preset_id, name, blueprint, tag, created_at
            FROM event_hunt_weapon_presets WHERE preset_id = :id
        """),
        {"id": int(preset_id)},
    ).fetchone()
    if not row:
        raise LookupError("Preset não encontrado.")
    db.execute(
        text("DELETE FROM event_hunt_weapon_presets WHERE preset_id = :id"),
        {"id": int(preset_id)},
    )
    db.commit()
    return {"deleted": True, "preset": _row_weapon_preset(row)}


# ── Player claims ────────────────────────────────────────────────────────────


def select_challenge(db: Session, *, steam_id: str, challenge_id: int) -> dict[str, Any]:
    """Member ACTIVE selects a challenge for themselves → CLAIMED + event_code."""
    _require_enabled()
    sid = str(steam_id).strip()
    mem = _require_active_membership(db, sid)
    team_id = int(mem["team_id"])
    ch = get_challenge(db, challenge_id)
    if not ch or not ch["enabled"]:
        raise ValueError("Desafio indisponível.")
    if member_has_lock(db, sid, int(challenge_id)):
        raise ValueError("Já usaste este desafio (conclusão ou falha).")
    active = _active_claim_for_member(db, sid)
    if active:
        raise ValueError("Já tens um desafio activo — conclui ou cancela antes.")

    code = _reserve_event_code(db)
    now = _naive()
    expires = now + timedelta(seconds=max(60, int(ch["claim_ttl_sec"])))
    db.execute(
        text("""
            INSERT INTO event_hunt_claims (
              challenge_id, team_id, owner_steam_id, event_code, status,
              selected_by_steam_id, points_awarded, amber_awarded, reward_status,
              claim_expires_at, created_at, updated_at
            ) VALUES (
              :cid, :tid, :owner, :code, 'CLAIMED',
              :owner, 0, 0, 'NONE',
              :exp, :now, :now
            )
        """),
        {
            "cid": int(challenge_id),
            "tid": team_id,
            "owner": sid,
            "code": code,
            "exp": expires,
            "now": now,
        },
    )
    claim_id = _last_id(db)
    _append_audit(
        db,
        event_type="CLAIM_SELECT",
        status="CLAIMED",
        team_id=team_id,
        member_steam_id=sid,
        challenge_id=int(challenge_id),
        source_id=claim_id,
        actor_steam_id=sid,
        event_code=code,
    )
    db.commit()
    claim = get_claim(db, claim_id)
    return {"claim": claim, "challenge": ch}


def cancel_claim(db: Session, *, steam_id: str, claim_id: int) -> dict[str, Any]:
    """Cancel CLAIMED (no spawn) — does NOT consume member attempt."""
    _require_enabled()
    sid = str(steam_id).strip()
    claim = get_claim(db, claim_id)
    if not claim:
        raise LookupError("Claim não encontrado.")
    if claim["owner_steam_id"] != sid:
        raise PermissionError("Só o dono pode cancelar este claim.")
    if claim["status"] != "CLAIMED":
        raise ValueError("Só podes cancelar um claim ainda CLAIMED (sem spawn).")
    now = _naive()
    db.execute(
        text("""
            UPDATE event_hunt_claims
            SET status='CANCELLED', updated_at=:now, fail_reason='cancelled'
            WHERE claim_id=:id AND status='CLAIMED'
        """),
        {"now": now, "id": int(claim_id)},
    )
    _append_audit(
        db,
        event_type="CANCEL",
        status="CANCELLED",
        team_id=int(claim["team_id"]),
        member_steam_id=sid,
        challenge_id=int(claim["challenge_id"]),
        source_id=int(claim_id),
        actor_steam_id=sid,
        event_code=claim["event_code"],
        note="cancel_claimed_no_consume",
    )
    db.commit()
    # Explicit: no lock insert
    assert not member_has_lock(db, sid, int(claim["challenge_id"]))
    return {"claim": get_claim(db, claim_id), "consumed": False}


def me_summary(db: Session, steam_id: str) -> dict[str, Any]:
    _require_enabled()
    sid = str(steam_id).strip()
    mem = _require_active_membership(db, sid)
    team_id = int(mem["team_id"])
    active = _active_claim_for_member(db, sid)
    my_active = None
    if active:
        ch = get_challenge(db, int(active["challenge_id"]))
        my_active = {
            **active,
            "display_name": (ch or {}).get("display_name"),
            "level": (ch or {}).get("level"),
            "points": (ch or {}).get("points"),
            "allowed_weapons": (ch or {}).get("allowed_weapons") or [],
            "amber_reward": (ch or {}).get("amber_reward") or 0,
        }
    lock_rows = db.execute(
        text("""
            SELECT l.challenge_id, l.outcome, l.fail_reason, l.consumed_at, l.claim_id,
                   c.display_name, c.points
            FROM event_hunt_member_challenge_locks l
            LEFT JOIN event_hunt_challenges c ON c.challenge_id = l.challenge_id
            WHERE l.steam_id = :s
            ORDER BY l.consumed_at DESC
        """),
        {"s": sid},
    ).fetchall()
    my_consumed = [
        {
            "challenge_id": int(r[0]),
            "outcome": r[1],
            "fail_reason": r[2],
            "consumed_at": str(r[3]) if r[3] else None,
            "claim_id": int(r[4]),
            "display_name": r[5] or f"#{r[0]}",
            "points": int(r[6] or 0) if r[1] == "COMPLETED" else 0,
        }
        for r in lock_rows
    ]
    my_completed = sum(1 for x in my_consumed if x["outcome"] == "COMPLETED")
    my_failed = sum(1 for x in my_consumed if x["outcome"] in ("FAIL", "FAILED", "EXPIRED"))
    can_select = active is None
    reason = None if can_select else "active_claim"
    scores = team_hunt_score_totals(db, team_id)
    return {
        "steam_id": sid,
        "team_id": team_id,
        "my_active_claim": my_active,
        "lock": {
            "one_active_per_member": True,
            "can_select": can_select,
            "reason": reason,
        },
        "my_consumed": my_consumed,
        "my_completed_count": my_completed,
        "my_failed_count": my_failed,
        "scores_team": scores,
    }


def team_summary(db: Session, steam_id: str) -> dict[str, Any]:
    _require_enabled()
    sid = str(steam_id).strip()
    mem = _require_active_membership(db, sid)
    team_id = int(mem["team_id"])
    scores = team_hunt_score_totals(db, team_id)
    rows = db.execute(
        text(f"""
            SELECT {_CLAIM_COLS} FROM event_hunt_claims
            WHERE team_id = :tid AND status IN ('CLAIMED', 'SPAWNED')
            ORDER BY claim_id DESC
        """),
        {"tid": team_id},
    ).fetchall()
    active_claims = []
    for r in rows:
        c = _row_claim(r)
        ch = get_challenge(db, int(c["challenge_id"]))
        # Codes only for owner — strip for others in API response helper
        item = {
            "claim_id": c["claim_id"],
            "challenge_id": c["challenge_id"],
            "owner_steam_id": c["owner_steam_id"],
            "status": c["status"],
            "display_name": (ch or {}).get("display_name"),
            "is_mine": c["owner_steam_id"] == sid,
        }
        if c["owner_steam_id"] == sid:
            item["event_code"] = c["event_code"]
        active_claims.append(item)
    recent = db.execute(
        text("""
            SELECT cl.owner_steam_id, cl.status, cl.fail_reason, cl.points_awarded,
                   cl.completed_at, cl.failed_at, c.display_name, cl.challenge_id
            FROM event_hunt_claims cl
            LEFT JOIN event_hunt_challenges c ON c.challenge_id = cl.challenge_id
            WHERE cl.team_id = :tid AND cl.status IN ('COMPLETED', 'FAILED')
            ORDER BY COALESCE(cl.completed_at, cl.failed_at) DESC
            LIMIT 20
        """),
        {"tid": team_id},
    ).fetchall()
    recent_items = [
        {
            "owner_steam_id": r[0],
            "status": r[1],
            "fail_reason": r[2],
            "points_awarded": int(r[3] or 0),
            "at": str(r[4] or r[5] or ""),
            "display_name": r[6] or f"#{r[7]}",
            "challenge_id": int(r[7]),
        }
        for r in recent
    ]
    return {
        "team_id": team_id,
        "scores": scores,
        "active_claims_by_members": active_claims,
        "recent_completions": recent_items,
    }


def list_team_claims(
    db: Session,
    steam_id: str,
    *,
    page: int = 1,
    page_size: int = 50,
    mine_only: bool = False,
) -> dict[str, Any]:
    _require_enabled()
    sid = str(steam_id).strip()
    mem = _require_active_membership(db, sid)
    team_id = int(mem["team_id"])
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))
    offset = (page - 1) * page_size
    where = "team_id = :tid"
    params: dict[str, Any] = {"tid": team_id, "lim": page_size, "off": offset}
    if mine_only:
        where += " AND owner_steam_id = :sid"
        params["sid"] = sid
    total = db.execute(
        text(f"SELECT COUNT(*) FROM event_hunt_claims WHERE {where}"),
        params,
    ).fetchone()
    rows = db.execute(
        text(f"""
            SELECT {_CLAIM_COLS} FROM event_hunt_claims
            WHERE {where}
            ORDER BY claim_id DESC LIMIT :lim OFFSET :off
        """),
        params,
    ).fetchall()
    items = []
    for r in rows:
        c = _row_claim(r)
        if c["owner_steam_id"] != sid:
            c = dict(c)
            c.pop("event_code", None)
            c["event_code_hidden"] = True
        ch = get_challenge(db, int(c["challenge_id"]))
        c["display_name"] = (ch or {}).get("display_name")
        items.append(c)
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": int(total[0] or 0) if total else 0,
    }


# ── Plugin bridge ────────────────────────────────────────────────────────────


def plugin_claim_by_code(db: Session, event_code: str) -> dict[str, Any]:
    _require_enabled()
    claim = get_claim_by_code(db, event_code)
    if not claim:
        raise LookupError("Código inválido.")
    if claim["status"] not in ("CLAIMED", "SPAWNED"):
        raise ValueError(f"Claim não está activo ({claim['status']}).")
    ch = get_challenge(db, int(claim["challenge_id"]))
    if not ch:
        raise LookupError("Desafio em falta.")
    return {
        "ok": True,
        "mode": "A",
        "event_code": claim["event_code"],
        "claim_id": claim["claim_id"],
        "challenge_id": claim["challenge_id"],
        "team_id": claim["team_id"],
        "owner_steam_id": claim["owner_steam_id"],
        "status": claim["status"],
        "blueprint": ch["blueprint"],
        "level": ch["level"],
        "allowed_weapons": ch["allowed_weapons"],
        "forbidden_weapons": ch["forbidden_weapons"],
        "min_allowed_weapon_damage_ratio": ch.get(
            "min_allowed_weapon_damage_ratio",
            DEFAULT_MIN_ALLOWED_WEAPON_DAMAGE_RATIO,
        ),
        "forbid_torpor": bool(ch.get("forbid_torpor", DEFAULT_FORBID_TORPOR)),
        "official_weapons_only": bool(
            ch.get("official_weapons_only", DEFAULT_OFFICIAL_WEAPONS_ONLY)
        ),
        "grant_weapon_on_start": bool(
            ch.get("grant_weapon_on_start", DEFAULT_GRANT_WEAPON_ON_START)
        ),
        "grant_weapon_blueprint": str(ch.get("grant_weapon_blueprint") or ""),
        "grant_weapon_qty": int(
            ch.get("grant_weapon_qty") or DEFAULT_GRANT_WEAPON_QTY
        ),
        "loot_on_complete": _normalize_loot_on_complete(
            ch.get("loot_on_complete") or []
        ),
        "allow_personal_tames": False,
        "dino_ttl_sec": ch["spawn_ttl_sec"],
        "points": ch["points"],
        "amber_reward": ch["amber_reward"],
        "display_name": ch["display_name"],
    }


def plugin_mark_spawned(
    db: Session,
    claim_id: int,
    *,
    steam_id: str,
    dino_id1: int | None = None,
    dino_id2: int | None = None,
    server_id: str | None = None,
    map_name: str | None = None,
) -> dict[str, Any]:
    _require_enabled()
    claim = get_claim(db, claim_id)
    if not claim:
        raise LookupError("Claim não encontrado.")
    if claim["status"] != "CLAIMED":
        if claim["status"] == "SPAWNED":
            return {"claim": claim, "duplicate": True}
        raise ValueError(f"Claim não está CLAIMED ({claim['status']}).")
    if str(steam_id) != claim["owner_steam_id"]:
        raise PermissionError("Só o dono do claim pode spawnar (/eve).")
    now = _naive()
    db.execute(
        text("""
            UPDATE event_hunt_claims SET
              status='SPAWNED', spawned_by_steam_id=:sid,
              dino_id1=:d1, dino_id2=:d2, server_id=:srv, map_name=:map,
              updated_at=:now
            WHERE claim_id=:id AND status='CLAIMED'
        """),
        {
            "sid": str(steam_id),
            "d1": dino_id1,
            "d2": dino_id2,
            "srv": (server_id or "")[:64] or None,
            "map": (map_name or "")[:64] or None,
            "now": now,
            "id": int(claim_id),
        },
    )
    _append_audit(
        db,
        event_type="SPAWN",
        status="SPAWNED",
        team_id=int(claim["team_id"]),
        member_steam_id=claim["owner_steam_id"],
        challenge_id=int(claim["challenge_id"]),
        source_id=int(claim_id),
        actor_steam_id=str(steam_id),
        server_id=server_id,
        event_code=claim["event_code"],
    )
    db.commit()
    return {"claim": get_claim(db, claim_id), "duplicate": False}


def plugin_complete(
    db: Session,
    claim_id: int,
    *,
    killer_steam_id: str,
    killer_team_id: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    _require_enabled()
    claim = get_claim(db, claim_id)
    if not claim:
        raise LookupError("Claim não encontrado.")
    idem = (idempotency_key or f"complete:{claim_id}")[:128]
    if claim["status"] == "COMPLETED":
        return {"claim": claim, "duplicate": True}
    if claim["status"] not in ("SPAWNED", "CLAIMED"):
        raise ValueError(f"Claim não pode completar ({claim['status']}).")

    # Killer must be same team
    owner_team = int(claim["team_id"])
    if killer_team_id is not None and int(killer_team_id) != owner_team:
        return plugin_fail(
            db,
            claim_id,
            reason="stolen",
            actor_steam_id=str(killer_steam_id),
            idempotency_key=f"fail-stolen:{claim_id}:{idem}",
        )

    ch = get_challenge(db, int(claim["challenge_id"]))
    if not ch:
        raise LookupError("Desafio em falta.")
    points = int(ch["points"] or 0)
    amber = int(ch["amber_reward"] or 0)
    now = _naive()
    reward_status = "PAID" if (points > 0 or amber > 0) else "NONE"

    if member_has_lock(db, claim["owner_steam_id"], int(claim["challenge_id"])):
        # Already consumed somehow — treat as duplicate terminal
        return {"claim": claim, "duplicate": True}

    db.execute(
        text("""
            UPDATE event_hunt_claims SET
              status='COMPLETED', points_awarded=:pts, amber_awarded=:amb,
              reward_status=:rs, completed_at=:now, updated_at=:now,
              idempotency_key=COALESCE(idempotency_key, :idem)
            WHERE claim_id=:id AND status IN ('CLAIMED','SPAWNED')
        """),
        {
            "pts": points,
            "amb": amber,
            "rs": reward_status,
            "now": now,
            "idem": idem,
            "id": int(claim_id),
        },
    )
    _insert_lock(
        db,
        steam_id=claim["owner_steam_id"],
        challenge_id=int(claim["challenge_id"]),
        team_id=owner_team,
        claim_id=int(claim_id),
        outcome="COMPLETED",
    )
    _record_score(
        db,
        team_id=owner_team,
        steam_id=claim["owner_steam_id"],
        points=points,
        amber=amber,
        reason="COMPLETED",
        claim_id=int(claim_id),
        idempotency_key=f"score:{idem}",
    )
    if amber > 0:
        try:
            _credit_team_amber(
                db,
                team_id=owner_team,
                amount=amber,
                actor_steam_id=claim["owner_steam_id"],
                idempotency_key=f"hunt-amber:{idem}",
                note=f"Event Hunt A claim #{claim_id}",
            )
        except Exception as exc:
            log.warning("event_hunt amber credit failed claim=%s: %s", claim_id, exc)
            reward_status = "PARTIAL" if points > 0 else "UNPAID"
            db.execute(
                text("UPDATE event_hunt_claims SET reward_status=:rs WHERE claim_id=:id"),
                {"rs": reward_status, "id": int(claim_id)},
            )
    _append_audit(
        db,
        event_type="COMPLETE",
        status="COMPLETED",
        team_id=owner_team,
        member_steam_id=claim["owner_steam_id"],
        challenge_id=int(claim["challenge_id"]),
        source_id=int(claim_id),
        points_awarded=points,
        amber_awarded=amber,
        reward_status=reward_status,
        actor_steam_id=str(killer_steam_id),
        event_code=claim["event_code"],
    )
    if points > 0 or amber > 0:
        _append_audit(
            db,
            event_type="SCORE",
            status="COMPLETED",
            team_id=owner_team,
            member_steam_id=claim["owner_steam_id"],
            challenge_id=int(claim["challenge_id"]),
            source_id=int(claim_id),
            points_awarded=points,
            amber_awarded=amber,
            reward_status=reward_status,
            actor_steam_id=str(killer_steam_id),
            event_code=claim["event_code"],
        )
    db.commit()
    return {"claim": get_claim(db, claim_id), "duplicate": False, "points": points, "amber": amber}


def plugin_fail(
    db: Session,
    claim_id: int,
    *,
    reason: str,
    actor_steam_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    _require_enabled()
    claim = get_claim(db, claim_id)
    if not claim:
        raise LookupError("Claim não encontrado.")
    if claim["status"] == "FAILED":
        return {"claim": claim, "duplicate": True, "consumed": True}
    if claim["status"] not in ("CLAIMED", "SPAWNED"):
        raise ValueError(f"Claim não pode falhar ({claim['status']}).")

    reason_n = str(reason or "unknown")[:64]
    outcome = "EXPIRED" if reason_n == "expired" else "FAIL"
    now = _naive()
    idem = (idempotency_key or f"fail:{claim_id}:{reason_n}")[:128]

    if member_has_lock(db, claim["owner_steam_id"], int(claim["challenge_id"])):
        return {"claim": claim, "duplicate": True, "consumed": True}

    db.execute(
        text("""
            UPDATE event_hunt_claims SET
              status='FAILED', fail_reason=:fr, points_awarded=0, amber_awarded=0,
              reward_status='NONE', failed_at=:now, updated_at=:now,
              idempotency_key=COALESCE(idempotency_key, :idem)
            WHERE claim_id=:id AND status IN ('CLAIMED','SPAWNED')
        """),
        {"fr": reason_n, "now": now, "idem": idem, "id": int(claim_id)},
    )
    _insert_lock(
        db,
        steam_id=claim["owner_steam_id"],
        challenge_id=int(claim["challenge_id"]),
        team_id=int(claim["team_id"]),
        claim_id=int(claim_id),
        outcome=outcome,
        fail_reason=reason_n,
    )
    _append_audit(
        db,
        event_type="FAIL",
        status="FAILED",
        team_id=int(claim["team_id"]),
        member_steam_id=claim["owner_steam_id"],
        challenge_id=int(claim["challenge_id"]),
        source_id=int(claim_id),
        fail_reason=reason_n,
        actor_steam_id=actor_steam_id,
        event_code=claim["event_code"],
    )
    db.commit()
    return {"claim": get_claim(db, claim_id), "duplicate": False, "consumed": True}


def admin_void_claim(
    db: Session,
    claim_id: int,
    *,
    admin_steam_id: str,
    note: str = "",
) -> dict[str, Any]:
    """Void active claim → FAIL admin_void (consumes attempt)."""
    return plugin_fail(
        db,
        claim_id,
        reason="admin_void",
        actor_steam_id=str(admin_steam_id),
        idempotency_key=f"void:{claim_id}",
    )


def admin_list_claims(
    db: Session,
    *,
    team_id: int | None = None,
    steam_id: str | None = None,
    status: str | None = None,
    event_code: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))
    offset = (page - 1) * page_size
    where = ["1=1"]
    params: dict[str, Any] = {"lim": page_size, "off": offset}
    if team_id is not None:
        where.append("team_id = :tid")
        params["tid"] = int(team_id)
    if steam_id:
        where.append("owner_steam_id = :sid")
        params["sid"] = str(steam_id)
    if status:
        where.append("status = :st")
        params["st"] = str(status)
    if event_code:
        where.append("event_code = :ec")
        params["ec"] = str(event_code).strip().upper()
    wh = " AND ".join(where)
    total = db.execute(text(f"SELECT COUNT(*) FROM event_hunt_claims WHERE {wh}"), params).fetchone()
    rows = db.execute(
        text(f"""
            SELECT {_CLAIM_COLS} FROM event_hunt_claims
            WHERE {wh} ORDER BY claim_id DESC LIMIT :lim OFFSET :off
        """),
        params,
    ).fetchall()
    items = []
    for r in rows:
        c = _row_claim(r)
        ch = get_challenge(db, int(c["challenge_id"]))
        c["display_name"] = (ch or {}).get("display_name")
        items.append(c)
    return {"items": items, "page": page, "page_size": page_size, "total": int(total[0] or 0) if total else 0}


def admin_list_audit(
    db: Session,
    *,
    team_id: int | None = None,
    member_steam_id: str | None = None,
    challenge_id: int | None = None,
    public_dino_id: int | None = None,
    mode: str | None = None,
    event_type: str | None = None,
    status: str | None = None,
    reward_status: str | None = None,
    from_ts: str | None = None,
    to_ts: str | None = None,
    points_awarded_min: int | None = None,
    points_awarded_max: int | None = None,
    amber_awarded_min: int | None = None,
    amber_awarded_max: int | None = None,
    unpaid_only: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))
    offset = (page - 1) * page_size
    where = ["1=1"]
    params: dict[str, Any] = {"lim": page_size, "off": offset}
    if team_id is not None:
        where.append("team_id = :tid")
        params["tid"] = int(team_id)
    if member_steam_id:
        where.append("member_steam_id = :ms")
        params["ms"] = str(member_steam_id)
    if challenge_id is not None:
        where.append("challenge_id = :cid")
        params["cid"] = int(challenge_id)
    if public_dino_id is not None:
        where.append("public_dino_id = :pdid")
        params["pdid"] = int(public_dino_id)
    if mode:
        where.append("mode = :mode")
        params["mode"] = str(mode)
    if event_type:
        where.append("event_type = :et")
        params["et"] = str(event_type)
    if status:
        where.append("status = :st")
        params["st"] = str(status)
    if reward_status:
        where.append("reward_status = :rs")
        params["rs"] = str(reward_status)
    if from_ts:
        where.append("occurred_at >= :from_ts")
        params["from_ts"] = str(from_ts)
    if to_ts:
        where.append("occurred_at <= :to_ts")
        params["to_ts"] = str(to_ts)
    if points_awarded_min is not None:
        where.append("points_awarded >= :pmin")
        params["pmin"] = int(points_awarded_min)
    if points_awarded_max is not None:
        where.append("points_awarded <= :pmax")
        params["pmax"] = int(points_awarded_max)
    if amber_awarded_min is not None:
        where.append("amber_awarded >= :amin")
        params["amin"] = int(amber_awarded_min)
    if amber_awarded_max is not None:
        where.append("amber_awarded <= :amax")
        params["amax"] = int(amber_awarded_max)
    if unpaid_only:
        where.append("(points_awarded = 0 OR amber_awarded = 0 OR reward_status IN ('UNPAID','PARTIAL','NONE'))")
        where.append("event_type IN ('COMPLETE','FAIL','SCORE','KILL')")
    wh = " AND ".join(where)
    total = db.execute(
        text(f"SELECT COUNT(*) FROM event_hunt_audit_events WHERE {wh}"), params
    ).fetchone()
    rows = db.execute(
        text(f"""
            SELECT audit_id, occurred_at, mode, event_type, status, team_id, member_steam_id,
                   challenge_id, public_dino_id, source_kind, source_id,
                   points_awarded, amber_awarded, reward_status, fail_reason, note,
                   actor_steam_id, server_id, event_code
            FROM event_hunt_audit_events
            WHERE {wh}
            ORDER BY audit_id DESC LIMIT :lim OFFSET :off
        """),
        params,
    ).fetchall()
    items = [
        {
            "audit_id": int(r[0]),
            "occurred_at": str(r[1]) if r[1] else None,
            "mode": r[2],
            "event_type": r[3],
            "status": r[4],
            "team_id": r[5],
            "member_steam_id": r[6],
            "challenge_id": r[7],
            "public_dino_id": r[8],
            "source_kind": r[9],
            "source_id": r[10],
            "points_awarded": int(r[11] or 0),
            "amber_awarded": int(r[12] or 0),
            "reward_status": r[13],
            "fail_reason": r[14],
            "note": r[15],
            "actor_steam_id": r[16],
            "server_id": r[17],
            "event_code": r[18],
        }
        for r in rows
    ]
    return {"items": items, "page": page, "page_size": page_size, "total": int(total[0] or 0) if total else 0}


def admin_grant_reward(
    db: Session,
    *,
    claim_id: int,
    admin_steam_id: str,
    reason: str,
    grant_points: bool = True,
    grant_amber: bool = True,
    points_amount: int | None = None,
    amber_amount: int | None = None,
    override_double_pay: bool = False,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    reason_s = str(reason or "").strip()
    if len(reason_s) < 10:
        raise ValueError("Motivo obrigatório (mín. 10 caracteres).")
    claim = get_claim(db, claim_id)
    if not claim:
        raise LookupError("Claim não encontrado.")
    ch = get_challenge(db, int(claim["challenge_id"]))
    if not ch:
        raise LookupError("Desafio em falta.")
    if not grant_points and not grant_amber:
        raise ValueError("Selecciona pontos e/ou Âmbar.")

    pts = int(points_amount if points_amount is not None else ch["points"]) if grant_points else 0
    amb = int(amber_amount if amber_amount is not None else ch["amber_reward"]) if grant_amber else 0
    if pts < 0 or amb < 0:
        raise ValueError("Montantes inválidos.")

    base_key = idempotency_key or f"manual_grant:claim:{claim_id}"
    if override_double_pay:
        n = db.execute(
            text("SELECT COUNT(*) FROM event_hunt_manual_grants WHERE source_kind='claim' AND source_id=:id"),
            {"id": int(claim_id)},
        ).fetchone()
        base_key = f"manual_grant:claim:{claim_id}:override:{int(n[0] or 0) + 1}"

    existing = db.execute(
        text("SELECT grant_id FROM event_hunt_manual_grants WHERE idempotency_key = :k LIMIT 1"),
        {"k": base_key[:128]},
    ).fetchone()
    if existing and not override_double_pay:
        raise ValueError("Já existe entrega para este registo (usa override).")

    if not override_double_pay and claim["reward_status"] in ("PAID", "MANUAL_PAID") and (
        int(claim["points_awarded"] or 0) > 0 or int(claim["amber_awarded"] or 0) > 0
    ):
        raise ValueError("Já pago — usa override_double_pay se necessário.")

    now = _naive()
    db.execute(
        text("""
            INSERT INTO event_hunt_manual_grants (
              source_kind, source_id, audit_id, team_id, beneficiary_steam_id,
              points_granted, amber_granted, reason, admin_steam_id, created_at,
              idempotency_key, override_double_pay
            ) VALUES (
              'claim', :sid, NULL, :tid, :ben,
              :pts, :amb, :reason, :admin, :now,
              :idem, :ovr
            )
        """),
        {
            "sid": int(claim_id),
            "tid": int(claim["team_id"]),
            "ben": claim["owner_steam_id"],
            "pts": pts,
            "amb": amb,
            "reason": reason_s[:512],
            "admin": str(admin_steam_id),
            "now": now,
            "idem": base_key[:128],
            "ovr": 1 if override_double_pay else 0,
        },
    )
    grant_id = _last_id(db)

    new_pts = int(claim["points_awarded"] or 0) + pts
    new_amb = int(claim["amber_awarded"] or 0) + amb
    db.execute(
        text("""
            UPDATE event_hunt_claims SET
              points_awarded=:pts, amber_awarded=:amb, reward_status='MANUAL_PAID', updated_at=:now
            WHERE claim_id=:id
        """),
        {"pts": new_pts, "amb": new_amb, "now": now, "id": int(claim_id)},
    )
    if pts > 0 or amb > 0:
        _record_score(
            db,
            team_id=int(claim["team_id"]),
            steam_id=claim["owner_steam_id"],
            points=pts,
            amber=amb,
            reason="MANUAL_GRANT",
            claim_id=int(claim_id),
            idempotency_key=f"score:{base_key}",
        )
    if amb > 0:
        _credit_team_amber(
            db,
            team_id=int(claim["team_id"]),
            amount=amb,
            actor_steam_id=str(admin_steam_id),
            idempotency_key=f"hunt-amber:{base_key}",
            note=f"Manual grant claim #{claim_id}",
        )
    audit_id = _append_audit(
        db,
        event_type="MANUAL_GRANT",
        status="MANUAL_PAID",
        team_id=int(claim["team_id"]),
        member_steam_id=claim["owner_steam_id"],
        challenge_id=int(claim["challenge_id"]),
        source_kind="grant",
        source_id=grant_id,
        points_awarded=pts,
        amber_awarded=amb,
        reward_status="MANUAL_PAID",
        note=reason_s,
        actor_steam_id=str(admin_steam_id),
        event_code=claim["event_code"],
    )
    db.execute(
        text("UPDATE event_hunt_manual_grants SET audit_id=:a WHERE grant_id=:g"),
        {"a": audit_id, "g": grant_id},
    )
    db.commit()
    return {
        "ok": True,
        "grant_id": grant_id,
        "points_granted": pts,
        "amber_granted": amb,
        "reward_status": "MANUAL_PAID",
        "audit_id": audit_id,
    }


# ── Mode B — sessão pública / catálogo / inscrição / plugin ───────────────────

SESSION_STATUSES = ("DRAFT", "OPEN_INSCRIPTION", "ACTIVE", "CLOSING", "CLOSED")
SESSION_TRANSITIONS = {
    "OPEN_INSCRIPTION": ("DRAFT",),
    "ACTIVE": ("OPEN_INSCRIPTION",),
    "CLOSING": ("ACTIVE",),
    "CLOSED": ("ACTIVE", "CLOSING"),
}
VISIBLE_SESSION_STATUSES = ("OPEN_INSCRIPTION", "ACTIVE", "CLOSING", "CLOSED")

_PUBLIC_DINO_COLS = """
  public_dino_id, event_session_id, event_code, display_name, blueprint, level,
  allowed_weapons, forbid_torpor, allow_personal_tames,
  min_allowed_weapon_damage_ratio, official_weapons_only,
  points_team, points_mvp, amber_team, amber_mvp, rank_rewards_json,
  loot_on_complete, ttl_sec, sort_order, enabled, created_at, updated_at
"""

_INSTANCE_COLS = """
  instance_id, event_session_id, public_dino_id, event_code, status,
  dino_id1, dino_id2, spawned_by_admin, server_id, map_name,
  expires_at, warned_1min, killer_steam_id, killer_team_id, fail_reason,
  points_awarded, amber_awarded, reward_status, idempotency_key,
  spawned_at, killed_at, expired_at, created_at, updated_at
"""

_SESSION_COLS = """
  event_session_id, name, status, map_scope, starts_at, ends_at,
  inscription_required, created_at, updated_at
"""


def _row_session(row: Any) -> dict[str, Any]:
    return {
        "event_session_id": int(row[0]),
        "name": row[1] or "",
        "status": row[2] or "DRAFT",
        "map_scope": row[3] or "*",
        "starts_at": str(row[4]) if row[4] else None,
        "ends_at": str(row[5]) if row[5] else None,
        "inscription_required": bool(row[6]),
        "created_at": str(row[7]) if row[7] else None,
        "updated_at": str(row[8]) if row[8] else None,
    }


def _row_public_dino(row: Any) -> dict[str, Any]:
    return {
        "public_dino_id": int(row[0]),
        "event_session_id": int(row[1]),
        "event_code": str(row[2] or ""),
        "display_name": row[3] or "",
        "blueprint": row[4] or "",
        "level": int(row[5] or 150),
        "allowed_weapons": _json_loads(row[6], []),
        "forbid_torpor": bool(row[7]),
        "allow_personal_tames": bool(row[8]),
        "min_allowed_weapon_damage_ratio": _clamp_ratio(row[9]),
        "official_weapons_only": bool(row[10]),
        "points_team": int(row[11] or 0),
        "points_mvp": int(row[12] or 0),
        "amber_team": int(row[13] or 0),
        "amber_mvp": int(row[14] or 0),
        "rank_rewards_json": _json_loads(row[15], {}),
        "loot_on_complete": _normalize_loot_on_complete(row[16] if len(row) > 16 else []),
        "ttl_sec": int(row[17] or 0),
        "sort_order": int(row[18] or 0),
        "enabled": bool(row[19]),
        "created_at": str(row[20]) if row[20] else None,
        "updated_at": str(row[21]) if row[21] else None,
    }


def _row_instance(row: Any) -> dict[str, Any]:
    return {
        "instance_id": int(row[0]),
        "event_session_id": int(row[1]),
        "public_dino_id": int(row[2]),
        "event_code": str(row[3] or ""),
        "status": str(row[4] or ""),
        "dino_id1": int(row[5]) if row[5] is not None else None,
        "dino_id2": int(row[6]) if row[6] is not None else None,
        "spawned_by_admin": row[7],
        "server_id": row[8],
        "map_name": row[9],
        "expires_at": str(row[10]) if row[10] else None,
        "warned_1min": bool(row[11]),
        "killer_steam_id": row[12],
        "killer_team_id": int(row[13]) if row[13] is not None else None,
        "fail_reason": row[14],
        "points_awarded": int(row[15] or 0),
        "amber_awarded": int(row[16] or 0),
        "reward_status": str(row[17] or "NONE"),
        "idempotency_key": row[18],
        "spawned_at": str(row[19]) if row[19] else None,
        "killed_at": str(row[20]) if row[20] else None,
        "expired_at": str(row[21]) if row[21] else None,
        "created_at": str(row[22]) if row[22] else None,
        "updated_at": str(row[23]) if row[23] else None,
    }


def get_session(db: Session, event_session_id: int) -> dict[str, Any] | None:
    row = db.execute(
        text(f"SELECT {_SESSION_COLS} FROM event_hunt_sessions WHERE event_session_id = :id"),
        {"id": int(event_session_id)},
    ).fetchone()
    return _row_session(row) if row else None


def get_public_dino(db: Session, public_dino_id: int) -> dict[str, Any] | None:
    row = db.execute(
        text(f"SELECT {_PUBLIC_DINO_COLS} FROM event_hunt_public_dinos WHERE public_dino_id = :id"),
        {"id": int(public_dino_id)},
    ).fetchone()
    return _row_public_dino(row) if row else None


def get_public_dino_by_code(db: Session, event_code: str) -> dict[str, Any] | None:
    code = str(event_code or "").strip().upper()
    if not code:
        return None
    row = db.execute(
        text(f"SELECT {_PUBLIC_DINO_COLS} FROM event_hunt_public_dinos WHERE event_code = :c"),
        {"c": code},
    ).fetchone()
    return _row_public_dino(row) if row else None


def get_instance(db: Session, instance_id: int) -> dict[str, Any] | None:
    row = db.execute(
        text(f"SELECT {_INSTANCE_COLS} FROM event_hunt_instances WHERE instance_id = :id"),
        {"id": int(instance_id)},
    ).fetchone()
    return _row_instance(row) if row else None


def _team_inscribed(db: Session, event_session_id: int, team_id: int) -> bool:
    row = db.execute(
        text("""
            SELECT 1 FROM event_hunt_inscriptions
            WHERE event_session_id = :sid AND team_id = :tid AND status = 'ACTIVE'
            LIMIT 1
        """),
        {"sid": int(event_session_id), "tid": int(team_id)},
    ).fetchone()
    return row is not None


def _get_inscription(db: Session, event_session_id: int, team_id: int) -> dict[str, Any] | None:
    row = db.execute(
        text("""
            SELECT inscription_id, event_session_id, team_id, inscribed_by_steam_id,
                   inscribed_at, status
            FROM event_hunt_inscriptions
            WHERE event_session_id = :sid AND team_id = :tid
            LIMIT 1
        """),
        {"sid": int(event_session_id), "tid": int(team_id)},
    ).fetchone()
    if not row:
        return None
    return {
        "inscription_id": int(row[0]),
        "event_session_id": int(row[1]),
        "team_id": int(row[2]),
        "inscribed_by_steam_id": row[3] or "",
        "inscribed_at": str(row[4]) if row[4] else None,
        "status": row[5] or "ACTIVE",
    }


def _current_visible_session(db: Session) -> dict[str, Any] | None:
    """Prefer ACTIVE / OPEN_INSCRIPTION; else latest CLOSING/CLOSED for boards."""
    for st in ("ACTIVE", "OPEN_INSCRIPTION", "CLOSING", "CLOSED"):
        row = db.execute(
            text(f"""
                SELECT {_SESSION_COLS} FROM event_hunt_sessions
                WHERE status = :st ORDER BY event_session_id DESC LIMIT 1
            """),
            {"st": st},
        ).fetchone()
        if row:
            return _row_session(row)
    return None


def mode_b_current_session(db: Session, steam_id: str | None = None) -> dict[str, Any]:
    _require_enabled()
    session = _current_visible_session(db)
    if not session:
        return {
            "session": None,
            "inscription": None,
            "leaderboard": {"team": [], "mvp": []},
            "message": "Não há evento público aberto.",
        }
    inscription = None
    my_team_points = 0
    my_rank = None
    is_mvp_highlight = False
    if steam_id:
        try:
            mem = _require_active_membership(db, steam_id)
            inscription = _get_inscription(db, int(session["event_session_id"]), int(mem["team_id"]))
            if inscription and inscription["status"] != "ACTIVE":
                inscription = {**inscription, "active": False}
            elif inscription:
                inscription = {**inscription, "active": True}
        except PermissionError:
            inscription = None
    board = mode_b_leaderboard(db, int(session["event_session_id"]), limit=10)
    if steam_id and inscription and inscription.get("active"):
        tid = int(inscription["team_id"])
        for i, row in enumerate(board["team"], start=1):
            if int(row["team_id"]) == tid:
                my_team_points = int(row["points"])
                my_rank = i
                break
        if board["mvp"] and board["mvp"][0].get("steam_id") == str(steam_id):
            is_mvp_highlight = True
    # Player never sees admin codes
    return {
        "session": {
            "event_session_id": session["event_session_id"],
            "name": session["name"],
            "status": session["status"],
            "map_scope": session["map_scope"],
            "starts_at": session["starts_at"],
            "ends_at": session["ends_at"],
        },
        "inscription": inscription,
        "my_team_points": my_team_points,
        "my_team_rank": my_rank,
        "is_mvp_highlight": is_mvp_highlight,
        "leaderboard": board,
        "message": None,
    }


# back-compat alias used by older routes
mode_b_current_session_stub = mode_b_current_session


def mode_b_leaderboard(db: Session, event_session_id: int, *, limit: int = 20) -> dict[str, Any]:
    lim = min(100, max(1, int(limit)))
    team_rows = db.execute(
        text("""
            SELECT team_id, COALESCE(SUM(points),0) AS pts, COALESCE(SUM(amber),0) AS amb
            FROM event_hunt_scores
            WHERE mode = 'B' AND event_session_id = :sid AND points > 0
            GROUP BY team_id
            ORDER BY pts DESC, team_id ASC
            LIMIT :lim
        """),
        {"sid": int(event_session_id), "lim": lim},
    ).fetchall()
    team_items = []
    for r in team_rows:
        tid = int(r[0])
        name = ""
        try:
            from team_service import get_team
            t = get_team(db, tid)
            name = (t or {}).get("name") or ""
        except Exception:
            name = ""
        team_items.append({
            "team_id": tid,
            "team_name": name,
            "points": int(r[1] or 0),
            "amber": int(r[2] or 0),
        })
    mvp_rows = db.execute(
        text("""
            SELECT steam_id, team_id, COALESCE(SUM(points),0) AS pts
            FROM event_hunt_scores
            WHERE mode = 'B' AND event_session_id = :sid
              AND steam_id != '' AND reason IN ('KILL_MVP', 'MANUAL_GRANT_MVP')
            GROUP BY steam_id, team_id
            ORDER BY pts DESC, steam_id ASC
            LIMIT :lim
        """),
        {"sid": int(event_session_id), "lim": lim},
    ).fetchall()
    # Fallback: also count KILL points attributed to steam if no MVP rows
    if not mvp_rows:
        mvp_rows = db.execute(
            text("""
                SELECT steam_id, team_id, COALESCE(SUM(points),0) AS pts
                FROM event_hunt_scores
                WHERE mode = 'B' AND event_session_id = :sid
                  AND steam_id != '' AND reason LIKE 'KILL%'
                GROUP BY steam_id, team_id
                ORDER BY pts DESC, steam_id ASC
                LIMIT :lim
            """),
            {"sid": int(event_session_id), "lim": lim},
        ).fetchall()
    mvp_items = [
        {
            "steam_id": str(r[0]),
            "team_id": int(r[1]) if r[1] is not None else None,
            "points": int(r[2] or 0),
        }
        for r in mvp_rows
    ]
    return {"team": team_items, "mvp": mvp_items}


def mode_b_team_summary(db: Session, steam_id: str) -> dict[str, Any]:
    _require_enabled()
    mem = _require_active_membership(db, steam_id)
    session = _current_visible_session(db)
    if not session:
        return {"session": None, "message": "Não há evento público aberto."}
    sid = int(session["event_session_id"])
    tid = int(mem["team_id"])
    insc = _get_inscription(db, sid, tid)
    board = mode_b_leaderboard(db, sid, limit=50)
    rank = None
    pts = 0
    for i, row in enumerate(board["team"], start=1):
        if int(row["team_id"]) == tid:
            rank = i
            pts = int(row["points"])
            break
    best_mvp = None
    for row in board["mvp"]:
        if row.get("team_id") is not None and int(row["team_id"]) == tid:
            best_mvp = row
            break
    return {
        "session": {
            "event_session_id": sid,
            "name": session["name"],
            "status": session["status"],
        },
        "inscription": insc,
        "points": pts,
        "rank": rank,
        "best_mvp": best_mvp,
    }


def mode_b_inscribe(db: Session, steam_id: str, event_session_id: int) -> dict[str, Any]:
    _require_enabled()
    mem = _require_active_membership(db, steam_id)
    session = get_session(db, event_session_id)
    if not session:
        raise LookupError("Sessão não encontrada.")
    if session["status"] != "OPEN_INSCRIPTION":
        raise ValueError("Inscrições só durante OPEN_INSCRIPTION.")
    tid = int(mem["team_id"])
    existing = _get_inscription(db, event_session_id, tid)
    now = _naive()
    if existing and existing["status"] == "ACTIVE":
        return {"inscription": existing, "duplicate": True}
    if existing:
        db.execute(
            text("""
                UPDATE event_hunt_inscriptions SET status='ACTIVE',
                  inscribed_by_steam_id=:s, inscribed_at=:now
                WHERE inscription_id=:id
            """),
            {"s": str(steam_id), "now": now, "id": int(existing["inscription_id"])},
        )
        insc_id = int(existing["inscription_id"])
    else:
        db.execute(
            text("""
                INSERT INTO event_hunt_inscriptions
                  (event_session_id, team_id, inscribed_by_steam_id, inscribed_at, status)
                VALUES (:sid, :tid, :s, :now, 'ACTIVE')
            """),
            {"sid": int(event_session_id), "tid": tid, "s": str(steam_id), "now": now},
        )
        insc_id = _last_id(db)
    _append_audit(
        db,
        mode="B",
        event_type="INSCRIBE",
        status="ACTIVE",
        team_id=tid,
        member_steam_id=str(steam_id),
        source_kind="inscription",
        source_id=insc_id,
        actor_steam_id=str(steam_id),
        note=f"session:{event_session_id}",
    )
    db.commit()
    return {"inscription": _get_inscription(db, event_session_id, tid), "duplicate": False}


def mode_b_withdraw(db: Session, steam_id: str, event_session_id: int) -> dict[str, Any]:
    _require_enabled()
    mem = _require_active_membership(db, steam_id)
    session = get_session(db, event_session_id)
    if not session:
        raise LookupError("Sessão não encontrada.")
    if session["status"] != "OPEN_INSCRIPTION":
        raise ValueError("Desinscrição só durante OPEN_INSCRIPTION.")
    tid = int(mem["team_id"])
    existing = _get_inscription(db, event_session_id, tid)
    if not existing or existing["status"] != "ACTIVE":
        raise ValueError("Equipa não está inscrita.")
    db.execute(
        text("UPDATE event_hunt_inscriptions SET status='WITHDRAWN' WHERE inscription_id=:id"),
        {"id": int(existing["inscription_id"])},
    )
    _append_audit(
        db,
        mode="B",
        event_type="WITHDRAW",
        status="WITHDRAWN",
        team_id=tid,
        member_steam_id=str(steam_id),
        source_kind="inscription",
        source_id=int(existing["inscription_id"]),
        actor_steam_id=str(steam_id),
    )
    db.commit()
    return {"ok": True, "inscription": _get_inscription(db, event_session_id, tid)}


# ── Mode B admin ──────────────────────────────────────────────────────────────


def admin_list_sessions(db: Session) -> list[dict[str, Any]]:
    rows = db.execute(
        text(f"SELECT {_SESSION_COLS} FROM event_hunt_sessions ORDER BY event_session_id DESC")
    ).fetchall()
    return [_row_session(r) for r in rows]


def admin_create_session(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("Nome da sessão obrigatório.")
    now = _naive()
    db.execute(
        text("""
            INSERT INTO event_hunt_sessions
              (name, status, map_scope, starts_at, ends_at, inscription_required, created_at, updated_at)
            VALUES (:n, 'DRAFT', :ms, :sa, :ea, :ir, :now, :now)
        """),
        {
            "n": name[:128],
            "ms": str(payload.get("map_scope") or "*")[:256],
            "sa": payload.get("starts_at") or None,
            "ea": payload.get("ends_at") or None,
            "ir": 1 if payload.get("inscription_required", True) else 0,
            "now": now,
        },
    )
    sid = _last_id(db)
    db.commit()
    return get_session(db, sid) or {}


def admin_update_session(
    db: Session, event_session_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    session = get_session(db, event_session_id)
    if not session:
        raise LookupError("Sessão não encontrada.")
    name = payload.get("name", session["name"])
    map_scope = payload.get("map_scope", session["map_scope"])
    starts_at = payload.get("starts_at", session["starts_at"])
    ends_at = payload.get("ends_at", session["ends_at"])
    ir = payload.get("inscription_required", session["inscription_required"])
    db.execute(
        text("""
            UPDATE event_hunt_sessions SET
              name=:n, map_scope=:ms, starts_at=:sa, ends_at=:ea,
              inscription_required=:ir, updated_at=:now
            WHERE event_session_id=:id
        """),
        {
            "n": str(name)[:128],
            "ms": str(map_scope or "*")[:256],
            "sa": starts_at,
            "ea": ends_at,
            "ir": 1 if ir else 0,
            "now": _naive(),
            "id": int(event_session_id),
        },
    )
    db.commit()
    return get_session(db, event_session_id) or {}


def admin_transition_session(
    db: Session,
    event_session_id: int,
    *,
    target_status: str,
    admin_steam_id: str = "",
) -> dict[str, Any]:
    session = get_session(db, event_session_id)
    if not session:
        raise LookupError("Sessão não encontrada.")
    target = str(target_status or "").strip().upper()
    if target not in SESSION_TRANSITIONS:
        raise ValueError(f"Transição inválida: {target}")
    allowed_from = SESSION_TRANSITIONS[target]
    if session["status"] not in allowed_from:
        raise ValueError(
            f"Não é possível {session['status']} → {target} "
            f"(esperado de {', '.join(allowed_from)})."
        )
    now = _naive()
    db.execute(
        text("""
            UPDATE event_hunt_sessions SET status=:st, updated_at=:now
            WHERE event_session_id=:id
        """),
        {"st": target, "now": now, "id": int(event_session_id)},
    )
    if target in ("CLOSING", "CLOSED"):
        db.execute(
            text("""
                UPDATE event_hunt_instances SET status='ORPHAN_ALIVE', updated_at=:now
                WHERE event_session_id=:sid AND status='ALIVE'
            """),
            {"now": now, "sid": int(event_session_id)},
        )
    _append_audit(
        db,
        mode="B",
        event_type="SESSION_TRANSITION",
        status=target,
        source_kind="session",
        source_id=int(event_session_id),
        actor_steam_id=str(admin_steam_id or ""),
        note=f"{session['status']}→{target}",
    )
    db.commit()
    return get_session(db, event_session_id) or {}


def admin_list_public_dinos(db: Session, event_session_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text(f"""
            SELECT {_PUBLIC_DINO_COLS} FROM event_hunt_public_dinos
            WHERE event_session_id = :sid
            ORDER BY sort_order ASC, public_dino_id ASC
        """),
        {"sid": int(event_session_id)},
    ).fetchall()
    return [_row_public_dino(r) for r in rows]


def admin_create_public_dino(
    db: Session, event_session_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    session = get_session(db, event_session_id)
    if not session:
        raise LookupError("Sessão não encontrada.")
    display_name = str(payload.get("display_name") or "").strip()
    blueprint = str(payload.get("blueprint") or "").strip()
    if not display_name or not blueprint:
        raise ValueError("display_name e blueprint obrigatórios.")
    code = str(payload.get("event_code") or "").strip().upper() or _reserve_event_code(db)
    # ensure unique across A+B
    if get_public_dino_by_code(db, code) or get_claim_by_code(db, code):
        raise ValueError(f"event_code já em uso: {code}")
    now = _naive()
    weapons = payload.get("allowed_weapons") or []
    if isinstance(weapons, str):
        weapons = [w.strip() for w in weapons.split(",") if w.strip()]
    loot = _normalize_loot_on_complete(payload.get("loot_on_complete"))
    db.execute(
        text("""
            INSERT INTO event_hunt_public_dinos (
              event_session_id, event_code, display_name, blueprint, level,
              allowed_weapons, forbid_torpor, allow_personal_tames,
              min_allowed_weapon_damage_ratio, official_weapons_only,
              points_team, points_mvp, amber_team, amber_mvp, rank_rewards_json,
              loot_on_complete, ttl_sec, sort_order, enabled, created_at, updated_at
            ) VALUES (
              :sid, :code, :dn, :bp, :lvl,
              :aw, :ft, :apt,
              :ratio, :owo,
              :pt, :pm, :at, :am, :rr,
              :loot, :ttl, :so, :en, :now, :now
            )
        """),
        {
            "sid": int(event_session_id),
            "code": code[:32],
            "dn": display_name[:128],
            "bp": blueprint[:512],
            "lvl": int(payload.get("level") or 150),
            "aw": _json_dumps(weapons),
            "ft": 1 if payload.get("forbid_torpor", True) else 0,
            "apt": 1 if payload.get("allow_personal_tames", False) else 0,
            "ratio": _clamp_ratio(
                payload.get(
                    "min_allowed_weapon_damage_ratio",
                    DEFAULT_MIN_ALLOWED_WEAPON_DAMAGE_RATIO,
                )
            ),
            "owo": 1 if payload.get("official_weapons_only", True) else 0,
            "pt": int(payload.get("points_team") or 0),
            "pm": int(payload.get("points_mvp") or 0),
            "at": int(payload.get("amber_team") or 0),
            "am": int(payload.get("amber_mvp") or 0),
            "rr": _json_dumps(payload.get("rank_rewards_json") or {}),
            "loot": _json_dumps(loot),
            "ttl": int(payload.get("ttl_sec") or 0),
            "so": int(payload.get("sort_order") or 0),
            "en": 1 if payload.get("enabled", True) else 0,
            "now": now,
        },
    )
    pdid = _last_id(db)
    _append_audit(
        db,
        mode="B",
        event_type="CATALOG_CREATE",
        status="REGISTERED",
        public_dino_id=pdid,
        source_kind="public_dino",
        source_id=pdid,
        event_code=code,
        note=display_name,
    )
    db.commit()
    return get_public_dino(db, pdid) or {}


def admin_update_public_dino(
    db: Session, public_dino_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    dino = get_public_dino(db, public_dino_id)
    if not dino:
        raise LookupError("Dino B não encontrado.")
    weapons = payload.get("allowed_weapons", dino["allowed_weapons"])
    if isinstance(weapons, str):
        weapons = [w.strip() for w in weapons.split(",") if w.strip()]
    loot = _normalize_loot_on_complete(
        payload["loot_on_complete"]
        if "loot_on_complete" in payload
        else dino.get("loot_on_complete") or []
    )
    db.execute(
        text("""
            UPDATE event_hunt_public_dinos SET
              display_name=:dn, blueprint=:bp, level=:lvl,
              allowed_weapons=:aw, forbid_torpor=:ft, allow_personal_tames=:apt,
              min_allowed_weapon_damage_ratio=:ratio, official_weapons_only=:owo,
              points_team=:pt, points_mvp=:pm, amber_team=:at, amber_mvp=:am,
              rank_rewards_json=:rr, loot_on_complete=:loot,
              ttl_sec=:ttl, sort_order=:so, enabled=:en,
              updated_at=:now
            WHERE public_dino_id=:id
        """),
        {
            "dn": str(payload.get("display_name", dino["display_name"]))[:128],
            "bp": str(payload.get("blueprint", dino["blueprint"]))[:512],
            "lvl": int(payload.get("level", dino["level"])),
            "aw": _json_dumps(weapons),
            "ft": 1 if payload.get("forbid_torpor", dino["forbid_torpor"]) else 0,
            "apt": 1 if payload.get("allow_personal_tames", dino["allow_personal_tames"]) else 0,
            "ratio": _clamp_ratio(
                payload.get(
                    "min_allowed_weapon_damage_ratio",
                    dino["min_allowed_weapon_damage_ratio"],
                )
            ),
            "owo": 1 if payload.get("official_weapons_only", dino["official_weapons_only"]) else 0,
            "pt": int(payload.get("points_team", dino["points_team"])),
            "pm": int(payload.get("points_mvp", dino["points_mvp"])),
            "at": int(payload.get("amber_team", dino["amber_team"])),
            "am": int(payload.get("amber_mvp", dino["amber_mvp"])),
            "rr": _json_dumps(payload.get("rank_rewards_json", dino["rank_rewards_json"])),
            "loot": _json_dumps(loot),
            "ttl": int(payload.get("ttl_sec", dino["ttl_sec"])),
            "so": int(payload.get("sort_order", dino["sort_order"])),
            "en": 1 if payload.get("enabled", dino["enabled"]) else 0,
            "now": _naive(),
            "id": int(public_dino_id),
        },
    )
    db.commit()
    return get_public_dino(db, public_dino_id) or {}


def admin_list_inscriptions(db: Session, event_session_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT i.inscription_id, i.event_session_id, i.team_id, i.inscribed_by_steam_id,
                   i.inscribed_at, i.status,
                   COALESCE((
                     SELECT SUM(s.points) FROM event_hunt_scores s
                     WHERE s.mode='B' AND s.event_session_id=i.event_session_id
                       AND s.team_id=i.team_id
                   ), 0) AS pts
            FROM event_hunt_inscriptions i
            WHERE i.event_session_id = :sid
            ORDER BY i.inscribed_at ASC
        """),
        {"sid": int(event_session_id)},
    ).fetchall()
    items = []
    for r in rows:
        tid = int(r[2])
        tname = ""
        try:
            from team_service import get_team
            t = get_team(db, tid)
            tname = (t or {}).get("name") or ""
        except Exception:
            pass
        items.append({
            "inscription_id": int(r[0]),
            "event_session_id": int(r[1]),
            "team_id": tid,
            "team_name": tname,
            "inscribed_by_steam_id": r[3] or "",
            "inscribed_at": str(r[4]) if r[4] else None,
            "status": r[5],
            "points": int(r[6] or 0),
        })
    return items


def admin_list_instances(
    db: Session,
    *,
    event_session_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))
    offset = (page - 1) * page_size
    where = ["1=1"]
    params: dict[str, Any] = {"lim": page_size, "off": offset}
    if event_session_id is not None:
        where.append("event_session_id = :sid")
        params["sid"] = int(event_session_id)
    if status:
        where.append("status = :st")
        params["st"] = str(status)
    wh = " AND ".join(where)
    total = db.execute(
        text(f"SELECT COUNT(*) FROM event_hunt_instances WHERE {wh}"), params
    ).fetchone()
    rows = db.execute(
        text(f"""
            SELECT {_INSTANCE_COLS} FROM event_hunt_instances
            WHERE {wh} ORDER BY instance_id DESC LIMIT :lim OFFSET :off
        """),
        params,
    ).fetchall()
    items = []
    for r in rows:
        inst = _row_instance(r)
        pd = get_public_dino(db, int(inst["public_dino_id"]))
        inst["display_name"] = (pd or {}).get("display_name")
        items.append(inst)
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": int(total[0] or 0) if total else 0,
    }


def admin_void_instance(
    db: Session,
    instance_id: int,
    *,
    admin_steam_id: str,
    note: str = "",
) -> dict[str, Any]:
    inst = get_instance(db, instance_id)
    if not inst:
        raise LookupError("Instância não encontrada.")
    if inst["status"] in ("VOIDED", "EXPIRED"):
        return {"instance": inst, "duplicate": True}
    now = _naive()
    db.execute(
        text("""
            UPDATE event_hunt_instances SET
              status='VOIDED', fail_reason='admin_void', updated_at=:now
            WHERE instance_id=:id
        """),
        {"now": now, "id": int(instance_id)},
    )
    _append_audit(
        db,
        mode="B",
        event_type="VOID",
        status="VOIDED",
        team_id=inst.get("killer_team_id"),
        member_steam_id=inst.get("killer_steam_id") or "",
        public_dino_id=int(inst["public_dino_id"]),
        source_kind="instance",
        source_id=int(instance_id),
        actor_steam_id=str(admin_steam_id),
        event_code=inst["event_code"],
        note=note or "admin void",
    )
    db.commit()
    return {"instance": get_instance(db, instance_id), "duplicate": False}


# ── Mode B plugin ─────────────────────────────────────────────────────────────


def plugin_b_by_code(db: Session, event_code: str) -> dict[str, Any]:
    """Claim-summon payload for /eveadm <code>.

    Pré-condições: dino `enabled`, sessão `ACTIVE`, sem instância ALIVE/ORPHAN_ALIVE.
    Se houver vivo órfão/stuck: admin void via
    ``POST /api/admin/event-hunt/b/instances/<id>/void``.
    """
    _require_enabled()
    code_norm = str(event_code or "").strip().upper()
    dino = get_public_dino_by_code(db, code_norm)
    if not dino:
        log.warning("plugin_b_by_code: código B desconhecido code=%s", code_norm)
        raise LookupError("Código B inválido.")
    if not dino["enabled"]:
        log.warning(
            "plugin_b_by_code: dino desactivado code=%s public_dino_id=%s session=%s",
            dino["event_code"],
            dino["public_dino_id"],
            dino["event_session_id"],
        )
        raise EventHuntReject(
            f"Dino B desactivado (código {dino['event_code']}). "
            "No Catálogo B usa «Activar» (estado deve mostrar ON) antes de /eveadm.",
            error_code="dino_disabled",
        )
    session = get_session(db, int(dino["event_session_id"]))
    if not session:
        raise LookupError("Sessão B em falta.")
    if session["status"] != "ACTIVE":
        log.warning(
            "plugin_b_by_code: sessão não ACTIVE code=%s session=%s status=%s",
            dino["event_code"],
            session["event_session_id"],
            session["status"],
        )
        raise EventHuntReject(
            f"Sessão não está ACTIVE ({session['status']}).",
            error_code="session_not_active",
        )
    alive = db.execute(
        text("""
            SELECT instance_id FROM event_hunt_instances
            WHERE public_dino_id = :pd AND status IN ('ALIVE', 'ORPHAN_ALIVE')
            LIMIT 1
        """),
        {"pd": int(dino["public_dino_id"])},
    ).fetchone()
    if alive:
        iid = int(alive[0])
        log.warning(
            "plugin_b_by_code: instância viva code=%s instance_id=%s "
            "(void: POST /api/admin/event-hunt/b/instances/%s/void)",
            dino["event_code"],
            iid,
            iid,
        )
        raise EventHuntReject(
            f"Já existe instância viva (#{iid}) deste dino — espera kill/expire "
            f"ou void admin POST /api/admin/event-hunt/b/instances/{iid}/void.",
            error_code="instance_alive",
            http_status=409,
        )
    return {
        "ok": True,
        "mode": "B",
        "event_code": dino["event_code"],
        "public_dino_id": dino["public_dino_id"],
        "event_session_id": dino["event_session_id"],
        "blueprint": dino["blueprint"],
        "level": dino["level"],
        "allowed_weapons": dino["allowed_weapons"],
        "forbid_torpor": dino["forbid_torpor"],
        "allow_personal_tames": dino["allow_personal_tames"],
        "min_allowed_weapon_damage_ratio": dino["min_allowed_weapon_damage_ratio"],
        "official_weapons_only": dino["official_weapons_only"],
        "dino_ttl_sec": dino["ttl_sec"],
        "points_team": dino["points_team"],
        "points_mvp": dino["points_mvp"],
        "amber_team": dino["amber_team"],
        "amber_mvp": dino["amber_mvp"],
        "loot_on_complete": _normalize_loot_on_complete(
            dino.get("loot_on_complete") or []
        ),
        "display_name": dino["display_name"],
        "session_name": session["name"],
    }


def plugin_b_mark_spawned(
    db: Session,
    *,
    public_dino_id: int | None = None,
    event_code: str | None = None,
    admin_steam_id: str,
    dino_id1: int | None = None,
    dino_id2: int | None = None,
    server_id: str | None = None,
    map_name: str | None = None,
) -> dict[str, Any]:
    _require_enabled()
    dino = None
    if public_dino_id:
        dino = get_public_dino(db, int(public_dino_id))
    elif event_code:
        dino = get_public_dino_by_code(db, event_code)
    if not dino:
        raise LookupError("Dino B não encontrado.")
    session = get_session(db, int(dino["event_session_id"]))
    if not session or session["status"] != "ACTIVE":
        raise ValueError("Sessão não ACTIVE — spawn bloqueado.")
    now = _naive()
    expires_at = None
    ttl = int(dino["ttl_sec"] or 0)
    if ttl > 0:
        expires_at = now + timedelta(seconds=ttl)
    db.execute(
        text("""
            INSERT INTO event_hunt_instances (
              event_session_id, public_dino_id, event_code, status,
              dino_id1, dino_id2, spawned_by_admin, server_id, map_name,
              expires_at, warned_1min, spawned_at, created_at, updated_at
            ) VALUES (
              :sid, :pd, :code, 'ALIVE',
              :d1, :d2, :admin, :srv, :map,
              :exp, 0, :now, :now, :now
            )
        """),
        {
            "sid": int(dino["event_session_id"]),
            "pd": int(dino["public_dino_id"]),
            "code": dino["event_code"],
            "d1": dino_id1,
            "d2": dino_id2,
            "admin": str(admin_steam_id)[:32],
            "srv": (server_id or "")[:64] or None,
            "map": (map_name or "")[:64] or None,
            "exp": expires_at,
            "now": now,
        },
    )
    iid = _last_id(db)
    _append_audit(
        db,
        mode="B",
        event_type="SUMMON",
        status="ALIVE",
        public_dino_id=int(dino["public_dino_id"]),
        source_kind="instance",
        source_id=iid,
        actor_steam_id=str(admin_steam_id),
        server_id=server_id,
        event_code=dino["event_code"],
    )
    db.commit()
    return {"instance": get_instance(db, iid), "public_dino": dino}


def plugin_b_report_kill(
    db: Session,
    instance_id: int,
    *,
    killer_steam_id: str,
    killer_team_id: int | None = None,
    valid: bool = True,
    fail_reason: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Credit Team + MVP only if killer's team is inscribed."""
    _require_enabled()
    inst = get_instance(db, instance_id)
    if not inst:
        raise LookupError("Instância não encontrada.")
    idem = (idempotency_key or f"kill:{instance_id}")[:128]
    if inst["status"] in ("SCORED", "KILLED") and inst.get("idempotency_key") == idem:
        return {"instance": inst, "duplicate": True, "credited": False}
    if inst["status"] in ("SCORED",):
        return {"instance": inst, "duplicate": True, "credited": int(inst["points_awarded"] or 0) > 0}
    if inst["status"] not in ("ALIVE", "ORPHAN_ALIVE", "KILLED"):
        raise ValueError(f"Instância não pode receber kill ({inst['status']}).")

    dino = get_public_dino(db, int(inst["public_dino_id"]))
    if not dino:
        raise LookupError("Dino B em falta.")

    # Resolve team from membership if not provided
    team_id = killer_team_id
    if team_id is None:
        try:
            from team_service import get_active_membership
            mem = get_active_membership(db, str(killer_steam_id))
            if mem:
                team_id = int(mem["team_id"])
        except Exception:
            team_id = None

    inscribed = bool(team_id and _team_inscribed(db, int(inst["event_session_id"]), int(team_id)))
    now = _naive()
    pts_team = 0
    pts_mvp = 0
    amb_team = 0
    amb_mvp = 0
    credited = False
    note = ""
    reward_status = "NONE"

    if not valid or fail_reason:
        note = fail_reason or "invalid_kill"
        reward_status = "NONE"
    elif not inscribed:
        note = "not_inscribed"
        reward_status = "NONE"
    else:
        pts_team = int(dino["points_team"] or 0)
        pts_mvp = int(dino["points_mvp"] or 0)
        amb_team = int(dino["amber_team"] or 0)
        amb_mvp = int(dino["amber_mvp"] or 0)
        credited = (pts_team + pts_mvp + amb_team + amb_mvp) > 0
        reward_status = "PAID" if credited else "NONE"

    total_pts = pts_team + pts_mvp
    total_amb = amb_team + amb_mvp

    db.execute(
        text("""
            UPDATE event_hunt_instances SET
              status='SCORED', killer_steam_id=:ks, killer_team_id=:kt,
              fail_reason=:fr, points_awarded=:pts, amber_awarded=:amb,
              reward_status=:rs, idempotency_key=COALESCE(idempotency_key, :idem),
              killed_at=:now, updated_at=:now
            WHERE instance_id=:id AND status IN ('ALIVE','ORPHAN_ALIVE','KILLED')
        """),
        {
            "ks": str(killer_steam_id)[:32],
            "kt": int(team_id) if team_id is not None else None,
            "fr": (fail_reason or note or None),
            "pts": total_pts,
            "amb": total_amb,
            "rs": reward_status,
            "idem": idem,
            "now": now,
            "id": int(instance_id),
        },
    )

    if credited and team_id is not None:
        if pts_team > 0 or amb_team > 0:
            _record_score(
                db,
                mode="B",
                event_session_id=int(inst["event_session_id"]),
                team_id=int(team_id),
                steam_id="",
                points=pts_team,
                amber=amb_team,
                reason="KILL_TEAM",
                instance_id=int(instance_id),
                idempotency_key=f"score:team:{idem}",
            )
        if pts_mvp > 0 or amb_mvp > 0:
            _record_score(
                db,
                mode="B",
                event_session_id=int(inst["event_session_id"]),
                team_id=int(team_id),
                steam_id=str(killer_steam_id),
                points=pts_mvp,
                amber=amb_mvp,
                reason="KILL_MVP",
                instance_id=int(instance_id),
                idempotency_key=f"score:mvp:{idem}",
            )
        if amb_team > 0:
            _credit_team_amber(
                db,
                team_id=int(team_id),
                amount=amb_team,
                actor_steam_id=str(killer_steam_id),
                idempotency_key=f"hunt-amber:team:{idem}",
                note=f"Mode B kill team instance #{instance_id}",
            )
        if amb_mvp > 0:
            _credit_team_amber(
                db,
                team_id=int(team_id),
                amount=amb_mvp,
                actor_steam_id=str(killer_steam_id),
                idempotency_key=f"hunt-amber:mvp:{idem}",
                note=f"Mode B kill MVP instance #{instance_id}",
            )

    _append_audit(
        db,
        mode="B",
        event_type="KILL",
        status="SCORED",
        team_id=int(team_id) if team_id is not None else None,
        member_steam_id=str(killer_steam_id),
        public_dino_id=int(inst["public_dino_id"]),
        source_kind="instance",
        source_id=int(instance_id),
        points_awarded=total_pts,
        amber_awarded=total_amb,
        reward_status=reward_status,
        fail_reason=fail_reason or (note if note else None),
        note=note,
        actor_steam_id=str(killer_steam_id),
        event_code=inst["event_code"],
    )
    db.commit()
    return {
        "instance": get_instance(db, instance_id),
        "credited": credited,
        "inscribed": inscribed,
        "points_team": pts_team,
        "points_mvp": pts_mvp,
        "amber_team": amb_team,
        "amber_mvp": amb_mvp,
        "duplicate": False,
    }


def plugin_b_expire(
    db: Session,
    instance_id: int,
    *,
    warned_1min: bool | None = None,
    actor_steam_id: str | None = None,
) -> dict[str, Any]:
    _require_enabled()
    inst = get_instance(db, instance_id)
    if not inst:
        raise LookupError("Instância não encontrada.")
    if inst["status"] == "EXPIRED":
        return {"instance": inst, "duplicate": True}
    if warned_1min and inst["status"] in ("ALIVE", "ORPHAN_ALIVE") and not inst["warned_1min"]:
        db.execute(
            text("UPDATE event_hunt_instances SET warned_1min=1, updated_at=:now WHERE instance_id=:id"),
            {"now": _naive(), "id": int(instance_id)},
        )
        _append_audit(
            db,
            mode="B",
            event_type="EXPIRE_WARN",
            status=inst["status"],
            public_dino_id=int(inst["public_dino_id"]),
            source_kind="instance",
            source_id=int(instance_id),
            actor_steam_id=actor_steam_id,
            event_code=inst["event_code"],
            note="T-60s",
        )
        db.commit()
        return {"instance": get_instance(db, instance_id), "warned": True, "expired": False}

    if inst["status"] not in ("ALIVE", "ORPHAN_ALIVE"):
        raise ValueError(f"Instância não pode expirar ({inst['status']}).")
    now = _naive()
    db.execute(
        text("""
            UPDATE event_hunt_instances SET
              status='EXPIRED', expired_at=:now, updated_at=:now
            WHERE instance_id=:id
        """),
        {"now": now, "id": int(instance_id)},
    )
    _append_audit(
        db,
        mode="B",
        event_type="EXPIRE",
        status="EXPIRED",
        public_dino_id=int(inst["public_dino_id"]),
        source_kind="instance",
        source_id=int(instance_id),
        actor_steam_id=actor_steam_id,
        event_code=inst["event_code"],
    )
    db.commit()
    return {"instance": get_instance(db, instance_id), "warned": False, "expired": True}


def admin_grant_reward_instance(
    db: Session,
    *,
    instance_id: int,
    admin_steam_id: str,
    reason: str,
    grant_points: bool = True,
    grant_amber: bool = True,
    points_amount: int | None = None,
    amber_amount: int | None = None,
    override_double_pay: bool = False,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    reason_s = str(reason or "").strip()
    if len(reason_s) < 10:
        raise ValueError("Motivo obrigatório (mín. 10 caracteres).")
    inst = get_instance(db, instance_id)
    if not inst:
        raise LookupError("Instância não encontrada.")
    dino = get_public_dino(db, int(inst["public_dino_id"]))
    if not dino:
        raise LookupError("Dino B em falta.")
    if not grant_points and not grant_amber:
        raise ValueError("Selecciona pontos e/ou Âmbar.")

    team_id = inst.get("killer_team_id")
    if team_id is None:
        raise ValueError("Instância sem killer_team_id — não dá para entregar.")

    default_pts = int(dino["points_team"] or 0) + int(dino["points_mvp"] or 0)
    default_amb = int(dino["amber_team"] or 0) + int(dino["amber_mvp"] or 0)
    pts = int(points_amount if points_amount is not None else default_pts) if grant_points else 0
    amb = int(amber_amount if amber_amount is not None else default_amb) if grant_amber else 0
    if pts < 0 or amb < 0:
        raise ValueError("Montantes inválidos.")

    base_key = idempotency_key or f"manual_grant:instance:{instance_id}"
    if override_double_pay:
        n = db.execute(
            text(
                "SELECT COUNT(*) FROM event_hunt_manual_grants "
                "WHERE source_kind='instance' AND source_id=:id"
            ),
            {"id": int(instance_id)},
        ).fetchone()
        base_key = f"manual_grant:instance:{instance_id}:override:{int(n[0] or 0) + 1}"

    existing = db.execute(
        text("SELECT grant_id FROM event_hunt_manual_grants WHERE idempotency_key = :k LIMIT 1"),
        {"k": base_key[:128]},
    ).fetchone()
    if existing and not override_double_pay:
        raise ValueError("Já existe entrega para este registo (usa override).")

    if not override_double_pay and inst["reward_status"] in ("PAID", "MANUAL_PAID") and (
        int(inst["points_awarded"] or 0) > 0 or int(inst["amber_awarded"] or 0) > 0
    ):
        raise ValueError("Já pago — usa override_double_pay se necessário.")

    now = _naive()
    beneficiary = inst.get("killer_steam_id") or ""
    db.execute(
        text("""
            INSERT INTO event_hunt_manual_grants (
              source_kind, source_id, audit_id, team_id, beneficiary_steam_id,
              points_granted, amber_granted, reason, admin_steam_id, created_at,
              idempotency_key, override_double_pay
            ) VALUES (
              'instance', :sid, NULL, :tid, :ben,
              :pts, :amb, :reason, :admin, :now,
              :idem, :ovr
            )
        """),
        {
            "sid": int(instance_id),
            "tid": int(team_id),
            "ben": beneficiary,
            "pts": pts,
            "amb": amb,
            "reason": reason_s[:512],
            "admin": str(admin_steam_id),
            "now": now,
            "idem": base_key[:128],
            "ovr": 1 if override_double_pay else 0,
        },
    )
    grant_id = _last_id(db)
    new_pts = int(inst["points_awarded"] or 0) + pts
    new_amb = int(inst["amber_awarded"] or 0) + amb
    db.execute(
        text("""
            UPDATE event_hunt_instances SET
              points_awarded=:pts, amber_awarded=:amb, reward_status='MANUAL_PAID',
              updated_at=:now
            WHERE instance_id=:id
        """),
        {"pts": new_pts, "amb": new_amb, "now": now, "id": int(instance_id)},
    )
    if pts > 0 or amb > 0:
        _record_score(
            db,
            mode="B",
            event_session_id=int(inst["event_session_id"]),
            team_id=int(team_id),
            steam_id=beneficiary,
            points=pts,
            amber=amb,
            reason="MANUAL_GRANT",
            instance_id=int(instance_id),
            idempotency_key=f"score:{base_key}",
        )
    if amb > 0:
        _credit_team_amber(
            db,
            team_id=int(team_id),
            amount=amb,
            actor_steam_id=str(admin_steam_id),
            idempotency_key=f"hunt-amber:{base_key}",
            note=f"Manual grant instance #{instance_id}",
        )
    audit_id = _append_audit(
        db,
        mode="B",
        event_type="MANUAL_GRANT",
        status="MANUAL_PAID",
        team_id=int(team_id),
        member_steam_id=beneficiary,
        public_dino_id=int(inst["public_dino_id"]),
        source_kind="grant",
        source_id=grant_id,
        points_awarded=pts,
        amber_awarded=amb,
        reward_status="MANUAL_PAID",
        note=reason_s,
        actor_steam_id=str(admin_steam_id),
        event_code=inst["event_code"],
    )
    db.execute(
        text("UPDATE event_hunt_manual_grants SET audit_id=:a WHERE grant_id=:g"),
        {"a": audit_id, "g": grant_id},
    )
    db.commit()
    return {
        "ok": True,
        "grant_id": grant_id,
        "points_granted": pts,
        "amber_granted": amb,
        "reward_status": "MANUAL_PAID",
        "audit_id": audit_id,
    }
