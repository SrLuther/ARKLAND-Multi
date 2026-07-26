"""Convites /tribe.CODE, confirmação de membros, Principal/Fob e leave-revoke.

Extensão da Área da Tribo (decisões Jul/2026) — ver docs/PROJETO_AREA_TRIBO.md §20 / §20.8.
"""
from __future__ import annotations

import logging
import re
import secrets
import string
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from tribe_service import (
    _naive,
    _utcnow,
    create_cluster_group,
    get_map_links,
    get_or_create_owner,
    get_owner,
    get_registered_owner_for_tribe,
    resolve_viewer_tribe_context,
    upsert_map_link,
)

log = logging.getLogger("arkshop_web.tribe_invite")

INVITE_CODE_MAX_DAYS = 30
INVITE_CODE_LEN = 8
PRINCIPAL_SWAP_COOLDOWN_HOURS = 24
JOIN_STATUSES = frozenset({"PENDING", "ACCEPTED", "DENIED"})
CONFIRMED_VIA = frozenset({"code", "sync"})

_CODE_ALPHABET = string.ascii_uppercase + string.digits
_REMOVED_RE = re.compile(
    r"(?P<name>.+?)\s+was\s+removed\s+from\s+the\s+Tribe",
    re.IGNORECASE,
)
_LEFT_RE = re.compile(
    r"(?P<name>.+?)\s+(?:has\s+)?left\s+the\s+Tribe",
    re.IGNORECASE,
)


def ensure_invite_schema(engine: Any) -> None:
    """DDL idempotente para convites / group members / limites / alertas."""
    from tribe_service import _add_col_if_missing

    is_sqlite = "sqlite" in str(engine.url).lower()
    _pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "BIGINT AUTO_INCREMENT PRIMARY KEY"
    _now_col = "DATETIME" if is_sqlite else "DATETIME(6)"
    _tinyint = "INTEGER" if is_sqlite else "TINYINT(1)"

    ddls = [
        f"""
        CREATE TABLE IF NOT EXISTS tribe_invite_codes (
          id                  {_pk},
          cluster_group_id    INTEGER NOT NULL,
          code                VARCHAR(16) NOT NULL,
          created_by_steam_id VARCHAR(32) NOT NULL,
          created_at          {_now_col} NOT NULL,
          expires_at          {_now_col} NOT NULL,
          revoked_at          {_now_col},
          is_active           {_tinyint} NOT NULL DEFAULT 1,
          UNIQUE {"" if is_sqlite else "KEY uq_invite_code"} (code)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS tribe_join_requests (
          id                    {_pk},
          cluster_group_id      INTEGER NOT NULL,
          invite_code_id        INTEGER,
          steam_id              VARCHAR(32) NOT NULL,
          character_name        VARCHAR(128),
          server_id             VARCHAR(64) NOT NULL,
          tribe_id              INTEGER NOT NULL,
          status                VARCHAR(16) NOT NULL DEFAULT 'PENDING',
          created_at            {_now_col} NOT NULL,
          resolved_at           {_now_col},
          resolved_by_steam_id  VARCHAR(32)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS tribe_group_members (
          id                    {_pk},
          cluster_group_id      INTEGER NOT NULL,
          steam_id              VARCHAR(32) NOT NULL,
          confirmed_via         VARCHAR(16) NOT NULL,
          confirmed_at          {_now_col} NOT NULL,
          confirmed_by_steam_id VARCHAR(32),
          UNIQUE {"" if is_sqlite else "KEY uq_group_member"} (cluster_group_id, steam_id)
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS tribe_construction_limits (
          id                  {_pk},
          cluster_group_id    INTEGER,
          principal_max       INTEGER NOT NULL DEFAULT 0,
          fob_max             INTEGER NOT NULL DEFAULT 0,
          notes               TEXT,
          updated_at          {_now_col} NOT NULL,
          updated_by_steam_id VARCHAR(32) NOT NULL DEFAULT ''
        )
        """,
        f"""
        CREATE TABLE IF NOT EXISTS tribe_admin_alerts (
          id           {_pk},
          alert_type   VARCHAR(64) NOT NULL,
          severity     VARCHAR(16) NOT NULL DEFAULT 'info',
          message      TEXT NOT NULL,
          payload_json TEXT,
          steam_id     VARCHAR(32),
          server_id    VARCHAR(64),
          tribe_id     INTEGER,
          is_resolved  {_tinyint} NOT NULL DEFAULT 0,
          created_at   {_now_col} NOT NULL,
          resolved_at  {_now_col}
        )
        """,
    ]
    with engine.connect() as conn:
        for ddl in ddls:
            try:
                conn.execute(text(ddl))
            except Exception as exc:
                log.warning("tribe_invite_schema DDL parcial: %s", exc)
        _add_col_if_missing(
            conn, is_sqlite, "tribe_cluster_groups",
            "principal_changed_at", _now_col,
        )
        _add_col_if_missing(
            conn, is_sqlite, "tribe_cluster_groups",
            "owner_steam_id", "VARCHAR(32)",
        )
        _add_col_if_missing(
            conn, is_sqlite, "tribe_members",
            "confirmed_via", "VARCHAR(16)",
        )
        _add_col_if_missing(
            conn, is_sqlite, "tribe_map_links",
            "awaiting_owner_login", _tinyint + " DEFAULT 0",
        )
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_tribe_join_req_group_status "
                "ON tribe_join_requests (cluster_group_id, status)"
            ))
        except Exception as exc:
            log.debug("invite index: %s", exc)
        conn.commit()
    log.info("tribe_invite_schema: tabelas verificadas/criadas")


def _gen_code(length: int = INVITE_CODE_LEN) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def _group_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row[0],
        "group_name": row[1] or "",
        "anchor_server_id": row[2],
        "anchor_tribe_id": int(row[3]),
        "created_by_steam_id": row[4],
        "created_at": str(row[5]) if row[5] else None,
        "owner_steam_id": (row[6] if len(row) > 6 else None) or row[4],
        "principal_changed_at": str(row[7]) if len(row) > 7 and row[7] else None,
    }


def get_cluster_group(db: Session, group_id: int) -> dict[str, Any] | None:
    row = db.execute(
        text("""
            SELECT id, group_name, anchor_server_id, anchor_tribe_id,
                   created_by_steam_id, created_at, owner_steam_id, principal_changed_at
            FROM tribe_cluster_groups WHERE id = :id
        """),
        {"id": int(group_id)},
    ).fetchone()
    return _group_row_to_dict(row) if row else None


def get_group_for_owner(db: Session, owner_steam_id: str) -> dict[str, Any] | None:
    row = db.execute(
        text("""
            SELECT id, group_name, anchor_server_id, anchor_tribe_id,
                   created_by_steam_id, created_at, owner_steam_id, principal_changed_at
            FROM tribe_cluster_groups
            WHERE created_by_steam_id = :sid OR owner_steam_id = :sid
            ORDER BY id DESC LIMIT 1
        """),
        {"sid": owner_steam_id},
    ).fetchone()
    return _group_row_to_dict(row) if row else None


def ensure_cluster_group_for_owner(db: Session, owner_steam_id: str) -> dict[str, Any]:
    """Garante um cluster group com âncora no mapa Principal do painel."""
    existing = get_group_for_owner(db, owner_steam_id)
    if existing:
        return existing

    owner = get_or_create_owner(db, owner_steam_id)
    links = get_map_links(db, owner["id"])
    principal = next(
        (L for L in links if (L.get("tribe_type") or "principal") == "principal" and L.get("is_active")),
        None,
    )
    if not principal and links:
        principal = links[0]
    if not principal:
        raise ValueError(
            "Ative o painel e vincule ao menos um mapa (login como Proprietário) "
            "antes de gerar o código de convite."
        )

    group = create_cluster_group(
        db,
        group_name=principal.get("tribe_name_local") or f"Tribo {principal['tribe_id']}",
        anchor_server_id=principal["server_id"],
        anchor_tribe_id=int(principal["tribe_id"]),
        created_by_steam_id=owner_steam_id,
    )
    now = _naive(_utcnow())
    db.execute(
        text("""
            UPDATE tribe_cluster_groups
            SET owner_steam_id = :sid, updated_at = :now
            WHERE id = :id
        """),
        {"sid": owner_steam_id, "now": now, "id": group["id"]},
    )
    db.execute(
        text("""
            UPDATE tribe_map_links
            SET cluster_group_id = :gid, tribe_type = 'principal'
            WHERE tribe_owner_id = :oid AND server_id = :sid AND tribe_id = :tid
        """),
        {
            "gid": group["id"], "oid": owner["id"],
            "sid": principal["server_id"], "tid": principal["tribe_id"],
        },
    )
    # Owner confirmado via sync
    confirm_group_member(
        db,
        cluster_group_id=group["id"],
        steam_id=owner_steam_id,
        confirmed_via="sync",
        confirmed_by_steam_id=owner_steam_id,
        commit=False,
    )
    db.commit()
    return get_cluster_group(db, group["id"]) or group


def confirm_group_member(
    db: Session,
    *,
    cluster_group_id: int,
    steam_id: str,
    confirmed_via: str,
    confirmed_by_steam_id: str | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    if confirmed_via not in CONFIRMED_VIA:
        raise ValueError("confirmed_via inválido (use code|sync)")
    steam_id = str(steam_id or "").strip()
    now = _naive(_utcnow())
    existing = db.execute(
        text("""
            SELECT id FROM tribe_group_members
            WHERE cluster_group_id = :gid AND steam_id = :sid
        """),
        {"gid": cluster_group_id, "sid": steam_id},
    ).fetchone()
    if existing:
        db.execute(
            text("""
                UPDATE tribe_group_members
                SET confirmed_via = :via, confirmed_at = :now,
                    confirmed_by_steam_id = :by
                WHERE id = :id
            """),
            {
                "via": confirmed_via, "now": now,
                "by": confirmed_by_steam_id, "id": existing[0],
            },
        )
    else:
        db.execute(
            text("""
                INSERT INTO tribe_group_members
                  (cluster_group_id, steam_id, confirmed_via, confirmed_at, confirmed_by_steam_id)
                VALUES (:gid, :sid, :via, :now, :by)
            """),
            {
                "gid": cluster_group_id, "sid": steam_id,
                "via": confirmed_via, "now": now, "by": confirmed_by_steam_id,
            },
        )
    # Espelha confirmed_via nas linhas tribe_members dos mapas do grupo
    links = db.execute(
        text("""
            SELECT server_id, tribe_id FROM tribe_map_links
            WHERE cluster_group_id = :gid AND is_active = 1
        """),
        {"gid": cluster_group_id},
    ).fetchall()
    for link in links:
        db.execute(
            text("""
                UPDATE tribe_members
                SET confirmed_via = :via, updated_at = :now
                WHERE steam_id = :sid AND server_id = :svid AND tribe_id = :tid
            """),
            {
                "via": confirmed_via, "now": now, "sid": steam_id,
                "svid": link[0], "tid": link[1],
            },
        )
    if commit:
        db.commit()
    return {
        "cluster_group_id": cluster_group_id,
        "steam_id": steam_id,
        "confirmed_via": confirmed_via,
        "confirmed_at": str(now),
    }


def is_confirmed_member(db: Session, cluster_group_id: int, steam_id: str) -> bool:
    row = db.execute(
        text("""
            SELECT 1 FROM tribe_group_members
            WHERE cluster_group_id = :gid AND steam_id = :sid LIMIT 1
        """),
        {"gid": cluster_group_id, "sid": steam_id},
    ).fetchone()
    return bool(row)


def list_confirmed_members(db: Session, cluster_group_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT steam_id, confirmed_via, confirmed_at, confirmed_by_steam_id
            FROM tribe_group_members
            WHERE cluster_group_id = :gid
            ORDER BY confirmed_at ASC
        """),
        {"gid": cluster_group_id},
    ).fetchall()
    return [
        {
            "steam_id": r[0],
            "confirmed_via": r[1],
            "confirmed_at": str(r[2]) if r[2] else None,
            "confirmed_by_steam_id": r[3],
        }
        for r in rows
    ]


def filter_confirmed_for_split(
    db: Session,
    *,
    tribe_owner_id: int,
    members: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Mantém apenas membros confirmados no cluster group (quando o grupo usa convites)."""
    owner = db.execute(
        text("SELECT steam_id FROM tribe_owners WHERE id = :id"),
        {"id": tribe_owner_id},
    ).fetchone()
    if not owner:
        return members
    group = get_group_for_owner(db, owner[0])
    if not group:
        return members
    confirmed_list = list_confirmed_members(db, group["id"])
    if not confirmed_list:
        return members
    confirmed = {r["steam_id"] for r in confirmed_list}
    filtered = [m for m in members if m.get("steam_id") in confirmed]
    return filtered if filtered else members


# ── Leave / revoke (um mapa) ─────────────────────────────────

def revoke_membership_on_map(
    db: Session,
    *,
    steam_id: str,
    server_id: str,
    tribe_id: int | None = None,
    reason: str = "leave",
    commit: bool = True,
) -> dict[str, Any]:
    """Remove membership web neste mapa apenas (outros mapas preservados)."""
    steam_id = str(steam_id or "").strip()
    server_id = str(server_id or "").strip()
    if not steam_id or not server_id:
        return {"revoked": 0, "reason": reason}

    now = _naive(_utcnow())
    params: dict[str, Any] = {"sid": steam_id, "svid": server_id}
    if tribe_id is not None and int(tribe_id) > 0:
        params["tid"] = int(tribe_id)
        result = db.execute(
            text("""
                DELETE FROM tribe_members
                WHERE steam_id = :sid AND server_id = :svid AND tribe_id = :tid
            """),
            params,
        )
    else:
        result = db.execute(
            text("""
                DELETE FROM tribe_members
                WHERE steam_id = :sid AND server_id = :svid
            """),
            params,
        )
    revoked = int(result.rowcount or 0)

    # Presença com tribe_id=0 (histórico)
    db.execute(
        text("""
            INSERT INTO tribe_presences
              (steam_id, server_id, map_name, tribe_id, tribe_name, is_owner,
               member_rank, captured_at, source)
            VALUES (:sid, :svid, :svid, 0, NULL, 0, NULL, :now, :src)
        """),
        {"sid": steam_id, "svid": server_id, "now": now, "src": f"leave_{reason}"},
    )
    if commit:
        db.commit()
    log.info(
        "tribe revoke map steam=%s server=%s tribe=%s revoked=%s reason=%s",
        steam_id, server_id, tribe_id, revoked, reason,
    )
    return {
        "revoked": revoked,
        "steam_id": steam_id,
        "server_id": server_id,
        "tribe_id": tribe_id,
        "reason": reason,
    }


def revoke_by_character_name(
    db: Session,
    *,
    server_id: str,
    character_name: str,
    tribe_id: int | None = None,
    reason: str = "tribelog_removed",
) -> dict[str, Any]:
    name = (character_name or "").strip()
    if not name or not server_id:
        return {"revoked": 0}
    params: dict[str, Any] = {"svid": server_id, "cn": name}
    sql = """
        SELECT steam_id, tribe_id FROM tribe_members
        WHERE server_id = :svid AND LOWER(character_name) = LOWER(:cn)
    """
    if tribe_id is not None and int(tribe_id) > 0:
        sql += " AND tribe_id = :tid"
        params["tid"] = int(tribe_id)
    rows = db.execute(text(sql), params).fetchall()
    total = 0
    for r in rows:
        out = revoke_membership_on_map(
            db,
            steam_id=r[0],
            server_id=server_id,
            tribe_id=int(r[1]) if r[1] else tribe_id,
            reason=reason,
            commit=False,
        )
        total += int(out.get("revoked") or 0)
    if rows:
        db.commit()
    return {"revoked": total, "matches": len(rows), "character_name": name}


def parse_leave_character_name(body: str) -> str | None:
    text_body = (body or "").strip()
    for pattern in (_REMOVED_RE, _LEFT_RE):
        m = pattern.search(text_body)
        if m:
            return (m.group("name") or "").strip() or None
    return None


# ── Invite codes ─────────────────────────────────────────────

def get_active_invite_code(db: Session, cluster_group_id: int) -> dict[str, Any] | None:
    now = _naive(_utcnow())
    row = db.execute(
        text("""
            SELECT id, cluster_group_id, code, created_by_steam_id,
                   created_at, expires_at, revoked_at, is_active
            FROM tribe_invite_codes
            WHERE cluster_group_id = :gid AND is_active = 1
              AND (revoked_at IS NULL)
              AND expires_at > :now
            ORDER BY id DESC LIMIT 1
        """),
        {"gid": cluster_group_id, "now": now},
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "cluster_group_id": row[1],
        "code": row[2],
        "created_by_steam_id": row[3],
        "created_at": str(row[4]) if row[4] else None,
        "expires_at": str(row[5]) if row[5] else None,
        "revoked_at": str(row[6]) if row[6] else None,
        "is_active": bool(row[7]),
        "chat_command": f"/tribe.{row[2]}",
        "max_validity_days": INVITE_CODE_MAX_DAYS,
    }


def generate_invite_code(
    db: Session,
    *,
    owner_steam_id: str,
    regenerate: bool = False,
) -> dict[str, Any]:
    owner = get_owner(db, owner_steam_id)
    if not owner:
        raise ValueError("Ative o painel de tribo primeiro.")
    ctx = resolve_viewer_tribe_context(db, owner_steam_id, panel_activated=True)
    if not ctx.get("is_game_owner") and not ctx.get("can_manage"):
        raise ValueError("Apenas o Proprietário in-game pode gerar o código.")

    group = ensure_cluster_group_for_owner(db, owner_steam_id)
    now = _naive(_utcnow())
    expires = now + timedelta(days=INVITE_CODE_MAX_DAYS)

    if regenerate or get_active_invite_code(db, group["id"]):
        db.execute(
            text("""
                UPDATE tribe_invite_codes
                SET is_active = 0, revoked_at = :now
                WHERE cluster_group_id = :gid AND is_active = 1
            """),
            {"now": now, "gid": group["id"]},
        )

    code = _gen_code()
    for _ in range(8):
        clash = db.execute(
            text("SELECT id FROM tribe_invite_codes WHERE code = :c"),
            {"c": code},
        ).fetchone()
        if not clash:
            break
        code = _gen_code()

    db.execute(
        text("""
            INSERT INTO tribe_invite_codes
              (cluster_group_id, code, created_by_steam_id, created_at, expires_at, is_active)
            VALUES (:gid, :code, :by, :now, :exp, 1)
        """),
        {
            "gid": group["id"], "code": code, "by": owner_steam_id,
            "now": now, "exp": expires,
        },
    )
    db.commit()
    active = get_active_invite_code(db, group["id"])
    assert active is not None
    return {**active, "cluster_group": group, "regenerated": bool(regenerate)}


def _as_naive_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _naive(value) if value.tzinfo else value
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return _naive(parsed) if parsed.tzinfo else parsed
    except Exception:
        return None


def lookup_invite_code(db: Session, code: str) -> dict[str, Any] | None:
    code = (code or "").strip().upper()
    if not code:
        return None
    now = _naive(_utcnow())
    row = db.execute(
        text("""
            SELECT id, cluster_group_id, code, created_by_steam_id,
                   created_at, expires_at, revoked_at, is_active
            FROM tribe_invite_codes WHERE code = :c
        """),
        {"c": code},
    ).fetchone()
    if not row:
        return None
    if not row[7] or row[6] is not None:
        return None
    exp_n = _as_naive_dt(row[5])
    if exp_n is not None and exp_n <= now:
        return None
    return {
        "id": row[0],
        "cluster_group_id": row[1],
        "code": row[2],
        "created_by_steam_id": row[3],
        "created_at": str(row[4]) if row[4] else None,
        "expires_at": str(row[5]) if row[5] else None,
        "is_active": True,
    }


def _map_links_for_group(db: Session, cluster_group_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT id, tribe_owner_id, server_id, tribe_id, tribe_name_local,
                   tribe_type, cluster_group_id, is_active
            FROM tribe_map_links
            WHERE cluster_group_id = :gid AND is_active = 1
        """),
        {"gid": cluster_group_id},
    ).fetchall()
    return [
        {
            "id": r[0], "tribe_owner_id": r[1], "server_id": r[2],
            "tribe_id": int(r[3]), "tribe_name_local": r[4] or "",
            "tribe_type": r[5] or "principal", "cluster_group_id": r[6],
            "is_active": bool(r[7]),
        }
        for r in rows
    ]


def create_join_request(
    db: Session,
    *,
    code: str,
    steam_id: str,
    server_id: str,
    tribe_id: int,
    character_name: str = "",
) -> dict[str, Any]:
    """Plugin /tribe.CODE — cria PENDING (não auto-aceita)."""
    steam_id = str(steam_id or "").strip()
    server_id = str(server_id or "").strip()
    tribe_id = int(tribe_id or 0)
    if not steam_id or not server_id or tribe_id <= 0:
        raise ValueError("steam_id, server_id e tribe_id obrigatórios")

    invite = lookup_invite_code(db, code)
    if not invite:
        raise ValueError("Código inválido, expirado ou revogado.")

    group = get_cluster_group(db, invite["cluster_group_id"])
    if not group:
        raise ValueError("Grupo de tribo não encontrado.")

    links = _map_links_for_group(db, group["id"])
    linked = next(
        (L for L in links if L["server_id"] == server_id and L["tribe_id"] == tribe_id),
        None,
    )
    # Se mapa ainda não vinculado: exige que o dono in-game web da tribo seja o owner do grupo
    if not linked:
        registered = get_registered_owner_for_tribe(
            db, server_id=server_id, tribe_id=tribe_id,
        )
        owner_sid = group.get("owner_steam_id") or group.get("created_by_steam_id")
        # Alternativa: presença do owner do grupo como is_owner nesta tribo/mapa
        owner_in_tribe = db.execute(
            text("""
                SELECT 1 FROM tribe_members
                WHERE server_id = :svid AND tribe_id = :tid
                  AND steam_id = :sid AND is_owner = 1
                LIMIT 1
            """),
            {"svid": server_id, "tid": tribe_id, "sid": owner_sid},
        ).fetchone()
        if not owner_in_tribe and (not registered or registered["steam_id"] != owner_sid):
            # Membro precisa estar na lista da tribo; validação mínima: steam na tribe_members
            in_members = db.execute(
                text("""
                    SELECT 1 FROM tribe_members
                    WHERE server_id = :svid AND tribe_id = :tid AND steam_id = :sid
                    LIMIT 1
                """),
                {"svid": server_id, "tid": tribe_id, "sid": steam_id},
            ).fetchone()
            if not in_members:
                raise ValueError(
                    "Você precisa estar na tribo in-game deste mapa para usar o código."
                )
            # Permite pedido; na aceitação o owner liga a fob se for o dono
        else:
            in_members = db.execute(
                text("""
                    SELECT 1 FROM tribe_members
                    WHERE server_id = :svid AND tribe_id = :tid AND steam_id = :sid
                    LIMIT 1
                """),
                {"svid": server_id, "tid": tribe_id, "sid": steam_id},
            ).fetchone()
            if not in_members and steam_id != owner_sid:
                raise ValueError(
                    "Você precisa estar na tribo in-game deste mapa para usar o código."
                )
    else:
        in_members = db.execute(
            text("""
                SELECT 1 FROM tribe_members
                WHERE server_id = :svid AND tribe_id = :tid AND steam_id = :sid
                LIMIT 1
            """),
            {"svid": server_id, "tid": tribe_id, "sid": steam_id},
        ).fetchone()
        if not in_members:
            raise ValueError(
                "Você precisa estar na tribo in-game deste mapa para usar o código."
            )

    if is_confirmed_member(db, group["id"], steam_id):
        return {
            "status": "ALREADY_CONFIRMED",
            "message": "Você já está confirmado neste grupo de tribo.",
            "cluster_group_id": group["id"],
        }

    pending = db.execute(
        text("""
            SELECT id FROM tribe_join_requests
            WHERE cluster_group_id = :gid AND steam_id = :sid AND status = 'PENDING'
            LIMIT 1
        """),
        {"gid": group["id"], "sid": steam_id},
    ).fetchone()
    if pending:
        return {
            "status": "PENDING",
            "id": pending[0],
            "message": "Pedido já pendente — aguarde o Proprietário no site.",
            "cluster_group_id": group["id"],
        }

    now = _naive(_utcnow())
    db.execute(
        text("""
            INSERT INTO tribe_join_requests
              (cluster_group_id, invite_code_id, steam_id, character_name,
               server_id, tribe_id, status, created_at)
            VALUES (:gid, :iid, :sid, :cn, :svid, :tid, 'PENDING', :now)
        """),
        {
            "gid": group["id"], "iid": invite["id"], "sid": steam_id,
            "cn": (character_name or "")[:128] or None,
            "svid": server_id, "tid": tribe_id, "now": now,
        },
    )
    db.commit()
    row = db.execute(
        text("""
            SELECT id FROM tribe_join_requests
            WHERE cluster_group_id = :gid AND steam_id = :sid AND status = 'PENDING'
            ORDER BY id DESC LIMIT 1
        """),
        {"gid": group["id"], "sid": steam_id},
    ).fetchone()
    return {
        "status": "PENDING",
        "id": row[0] if row else None,
        "message": "Pedido enviado. O Proprietário precisa aceitar no site (Minha Tribo).",
        "cluster_group_id": group["id"],
        "server_id": server_id,
        "tribe_id": tribe_id,
    }


def list_join_requests(
    db: Session,
    *,
    owner_steam_id: str,
    status: str = "PENDING",
) -> list[dict[str, Any]]:
    group = get_group_for_owner(db, owner_steam_id)
    if not group:
        return []
    status = (status or "PENDING").upper()
    rows = db.execute(
        text("""
            SELECT id, cluster_group_id, invite_code_id, steam_id, character_name,
                   server_id, tribe_id, status, created_at, resolved_at, resolved_by_steam_id
            FROM tribe_join_requests
            WHERE cluster_group_id = :gid
              AND (:st = 'ALL' OR status = :st)
            ORDER BY created_at DESC
            LIMIT 100
        """),
        {"gid": group["id"], "st": status},
    ).fetchall()
    return [
        {
            "id": r[0], "cluster_group_id": r[1], "invite_code_id": r[2],
            "steam_id": r[3], "character_name": r[4] or "",
            "server_id": r[5], "tribe_id": int(r[6]),
            "status": r[7], "created_at": str(r[8]) if r[8] else None,
            "resolved_at": str(r[9]) if r[9] else None,
            "resolved_by_steam_id": r[10],
        }
        for r in rows
    ]


def resolve_join_request(
    db: Session,
    *,
    owner_steam_id: str,
    request_id: int,
    action: str,
    regenerate_code_on_deny: bool = False,
) -> dict[str, Any]:
    action = (action or "").strip().lower()
    if action not in ("accept", "deny"):
        raise ValueError("action deve ser accept ou deny")

    group = get_group_for_owner(db, owner_steam_id)
    if not group:
        raise ValueError("Grupo de tribo não encontrado.")

    row = db.execute(
        text("""
            SELECT id, cluster_group_id, steam_id, character_name, server_id, tribe_id, status
            FROM tribe_join_requests WHERE id = :id
        """),
        {"id": int(request_id)},
    ).fetchone()
    if not row or int(row[1]) != int(group["id"]):
        raise ValueError("Pedido não encontrado.")
    if row[6] != "PENDING":
        raise ValueError(f"Pedido já resolvido ({row[6]}).")

    now = _naive(_utcnow())
    new_status = "ACCEPTED" if action == "accept" else "DENIED"
    db.execute(
        text("""
            UPDATE tribe_join_requests
            SET status = :st, resolved_at = :now, resolved_by_steam_id = :by
            WHERE id = :id
        """),
        {"st": new_status, "now": now, "by": owner_steam_id, "id": row[0]},
    )

    result: dict[str, Any] = {
        "id": row[0],
        "status": new_status,
        "steam_id": row[2],
        "server_id": row[4],
        "tribe_id": int(row[5]),
    }

    if action == "accept":
        confirm_group_member(
            db,
            cluster_group_id=group["id"],
            steam_id=row[2],
            confirmed_via="code",
            confirmed_by_steam_id=owner_steam_id,
            commit=False,
        )
        # Liga fob se mapa ainda não está no grupo e a tribo é do owner
        links = _map_links_for_group(db, group["id"])
        if not any(L["server_id"] == row[4] and L["tribe_id"] == int(row[5]) for L in links):
            owner = get_owner(db, owner_steam_id)
            if owner:
                # Demais mapas = fob; âncora permanece principal
                is_anchor = (
                    row[4] == group["anchor_server_id"]
                    and int(row[5]) == int(group["anchor_tribe_id"])
                )
                upsert_map_link(
                    db,
                    tribe_owner_id=owner["id"],
                    server_id=row[4],
                    tribe_id=int(row[5]),
                    tribe_name_local=row[3] or f"Tribo {row[5]}",
                    tribe_type="principal" if is_anchor else "fob",
                    cluster_group_id=group["id"],
                )
                db.execute(
                    text("""
                        UPDATE tribe_map_links
                        SET cluster_group_id = :gid
                        WHERE tribe_owner_id = :oid AND server_id = :sid
                    """),
                    {"gid": group["id"], "oid": owner["id"], "sid": row[4]},
                )
        result["confirmed_via"] = "code"
        db.commit()
    else:
        db.commit()
        if regenerate_code_on_deny:
            result["invite"] = generate_invite_code(
                db, owner_steam_id=owner_steam_id, regenerate=True,
            )
            result["code_regenerated"] = True

    return result


# ── Principal / Fob ──────────────────────────────────────────

def count_principals_for_owner(db: Session, owner_steam_id: str) -> int:
    owner = get_owner(db, owner_steam_id)
    if not owner:
        return 0
    row = db.execute(
        text("""
            SELECT COUNT(*) FROM tribe_map_links
            WHERE tribe_owner_id = :oid AND tribe_type = 'principal' AND is_active = 1
        """),
        {"oid": owner["id"]},
    ).fetchone()
    return int(row[0] or 0) if row else 0


def set_principal_map(
    db: Session,
    *,
    owner_steam_id: str,
    server_id: str,
) -> dict[str, Any]:
    """Define mapa Principal (demais → Fob). Cooldown 24h."""
    server_id = str(server_id or "").strip()
    if not server_id:
        raise ValueError("server_id obrigatório")
    owner = get_owner(db, owner_steam_id)
    if not owner:
        raise ValueError("Painel de tribo não ativado.")
    ctx = resolve_viewer_tribe_context(db, owner_steam_id, panel_activated=True)
    if not ctx.get("is_game_owner") and not ctx.get("can_manage"):
        raise ValueError("Apenas o Proprietário pode alterar Principal/Fob.")

    group = ensure_cluster_group_for_owner(db, owner_steam_id)
    now = _naive(_utcnow())
    changed = group.get("principal_changed_at")
    prev = _as_naive_dt(changed)
    if prev is not None:
        delta = now - prev
        if delta < timedelta(hours=PRINCIPAL_SWAP_COOLDOWN_HOURS):
            remaining = PRINCIPAL_SWAP_COOLDOWN_HOURS * 3600 - int(delta.total_seconds())
            raise ValueError(
                f"Cooldownoldown de {PRINCIPAL_SWAP_COOLDOWN_HOURS}h para trocar Principal. "
                f"Aguarde ~{max(remaining // 3600, 1)}h."
            )

    link = db.execute(
        text("""
            SELECT id, tribe_id, tribe_name_local FROM tribe_map_links
            WHERE tribe_owner_id = :oid AND server_id = :sid AND is_active = 1
        """),
        {"oid": owner["id"], "sid": server_id},
    ).fetchone()
    if not link:
        raise ValueError("Mapa não vinculado ao seu painel.")

    # Constraint: no máximo 1 principal por steam_id
    db.execute(
        text("""
            UPDATE tribe_map_links
            SET tribe_type = 'fob'
            WHERE tribe_owner_id = :oid AND is_active = 1 AND server_id != :sid
        """),
        {"oid": owner["id"], "sid": server_id},
    )
    db.execute(
        text("""
            UPDATE tribe_map_links
            SET tribe_type = 'principal', cluster_group_id = :gid
            WHERE id = :id
        """),
        {"gid": group["id"], "id": link[0]},
    )
    db.execute(
        text("""
            UPDATE tribe_cluster_groups
            SET anchor_server_id = :sid, anchor_tribe_id = :tid,
                principal_changed_at = :now, updated_at = :now,
                owner_steam_id = :owner
            WHERE id = :gid
        """),
        {
            "sid": server_id, "tid": int(link[1]), "now": now,
            "owner": owner_steam_id, "gid": group["id"],
        },
    )
    db.commit()

    n = count_principals_for_owner(db, owner_steam_id)
    if n > 1:
        log.warning("principal constraint violated steam=%s count=%s", owner_steam_id, n)

    return {
        "principal_server_id": server_id,
        "principal_tribe_id": int(link[1]),
        "cluster_group_id": group["id"],
        "principal_count": count_principals_for_owner(db, owner_steam_id),
        "cooldown_hours": PRINCIPAL_SWAP_COOLDOWN_HOURS,
    }


def handle_ownership_transfer(
    db: Session,
    *,
    server_id: str,
    tribe_id: int,
    new_owner_steam_id: str,
    old_owner_steam_id: str | None = None,
    tribe_name: str = "",
) -> dict[str, Any]:
    """Atualiza web após transferência in-game de ownership."""
    new_owner_steam_id = str(new_owner_steam_id or "").strip()
    server_id = str(server_id or "").strip()
    tribe_id = int(tribe_id or 0)
    if not new_owner_steam_id or not server_id or tribe_id <= 0:
        raise ValueError("dados de transferência inválidos")

    registered = get_registered_owner_for_tribe(
        db, server_id=server_id, tribe_id=tribe_id,
    )
    now = _naive(_utcnow())
    alerts: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "server_id": server_id,
        "tribe_id": tribe_id,
        "new_owner_steam_id": new_owner_steam_id,
    }

    # Atualiza is_owner em tribe_members
    db.execute(
        text("""
            UPDATE tribe_members SET is_owner = 0, updated_at = :now
            WHERE server_id = :svid AND tribe_id = :tid
        """),
        {"now": now, "svid": server_id, "tid": tribe_id},
    )
    existing = db.execute(
        text("""
            SELECT id FROM tribe_members
            WHERE server_id = :svid AND tribe_id = :tid AND steam_id = :sid
        """),
        {"svid": server_id, "tid": tribe_id, "sid": new_owner_steam_id},
    ).fetchone()
    if existing:
        db.execute(
            text("""
                UPDATE tribe_members
                SET is_owner = 1, rank_name = 'Proprietário', updated_at = :now
                WHERE id = :id
            """),
            {"now": now, "id": existing[0]},
        )
    else:
        db.execute(
            text("""
                INSERT INTO tribe_members
                  (server_id, tribe_id, tribe_name, steam_id, character_name,
                   is_owner, rank_name, joined_at, last_seen_at, updated_at)
                VALUES (:svid, :tid, :tn, :sid, :cn, 1, 'Proprietário', :now, :now, :now)
            """),
            {
                "svid": server_id, "tid": tribe_id,
                "tn": tribe_name or "", "sid": new_owner_steam_id,
                "cn": "", "now": now,
            },
        )

    new_web = get_owner(db, new_owner_steam_id)
    awaiting = 0 if new_web else 1

    if registered:
        # Reassocia link ao novo steam (mantém dados se já tem painel)
        if registered["steam_id"] != new_owner_steam_id:
            if new_web:
                # Novo dono já tem principal noutro mapa?
                other_principal = db.execute(
                    text("""
                        SELECT server_id, tribe_id FROM tribe_map_links
                        WHERE tribe_owner_id = :oid AND tribe_type = 'principal'
                          AND is_active = 1 AND NOT (server_id = :sid AND tribe_id = :tid)
                        LIMIT 1
                    """),
                    {"oid": new_web["id"], "sid": server_id, "tid": tribe_id},
                ).fetchone()
                tribe_type = "fob" if other_principal else "principal"
                upsert_map_link(
                    db,
                    tribe_owner_id=new_web["id"],
                    server_id=server_id,
                    tribe_id=tribe_id,
                    tribe_name_local=tribe_name or registered.get("display_name") or "",
                    tribe_type=tribe_type,
                )
                # Desativa link antigo
                old_owner = get_owner(db, registered["steam_id"])
                if old_owner:
                    db.execute(
                        text("""
                            UPDATE tribe_map_links SET is_active = 0
                            WHERE tribe_owner_id = :oid AND server_id = :sid AND tribe_id = :tid
                        """),
                        {"oid": old_owner["id"], "sid": server_id, "tid": tribe_id},
                    )
                if other_principal:
                    msg = (
                        f"Transferência de ownership: {new_owner_steam_id} já tem Principal em "
                        f"{other_principal[0]} — mapa {server_id} marcado como Fob."
                    )
                    alert = create_admin_alert(
                        db,
                        alert_type="ownership_principal_conflict",
                        severity="warning",
                        message=msg,
                        steam_id=new_owner_steam_id,
                        server_id=server_id,
                        tribe_id=tribe_id,
                        payload={
                            "other_principal_server": other_principal[0],
                            "other_principal_tribe": int(other_principal[1]),
                        },
                        commit=False,
                    )
                    alerts.append(alert)
                    result["tribe_type"] = "fob"
                    result["admin_alert"] = True
                else:
                    result["tribe_type"] = "principal"
            else:
                # Sem conta web: mantém dados, associa steam, aguarda login
                db.execute(
                    text("""
                        UPDATE tribe_owners SET steam_id = :new, updated_at = :now
                        WHERE id = :id
                    """),
                    {
                        "new": new_owner_steam_id,
                        "now": now,
                        "id": registered["tribe_owner_id"],
                    },
                )
                db.execute(
                    text("""
                        UPDATE tribe_map_links
                        SET awaiting_owner_login = 1
                        WHERE tribe_owner_id = :oid AND server_id = :sid
                    """),
                    {"oid": registered["tribe_owner_id"], "sid": server_id},
                )
                awaiting = 1
                result["awaiting_owner_login"] = True
                result["member_message"] = (
                    "Aguardando novo dono conectar ao site"
                )

    result["awaiting_owner_login"] = bool(awaiting)
    result["alerts"] = alerts
    db.commit()
    return result


def create_admin_alert(
    db: Session,
    *,
    alert_type: str,
    message: str,
    severity: str = "info",
    steam_id: str | None = None,
    server_id: str | None = None,
    tribe_id: int | None = None,
    payload: dict[str, Any] | None = None,
    commit: bool = True,
) -> dict[str, Any]:
    import json
    now = _naive(_utcnow())
    db.execute(
        text("""
            INSERT INTO tribe_admin_alerts
              (alert_type, severity, message, payload_json, steam_id,
               server_id, tribe_id, is_resolved, created_at)
            VALUES (:t, :sev, :msg, :pj, :sid, :svid, :tid, 0, :now)
        """),
        {
            "t": alert_type[:64], "sev": severity[:16], "msg": message,
            "pj": json.dumps(payload or {}, ensure_ascii=False),
            "sid": steam_id, "svid": server_id, "tid": tribe_id, "now": now,
        },
    )
    if commit:
        db.commit()
    return {
        "alert_type": alert_type,
        "severity": severity,
        "message": message,
        "steam_id": steam_id,
        "server_id": server_id,
        "tribe_id": tribe_id,
    }


def list_admin_tribes(db: Session, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT o.id, o.steam_id, o.display_name, o.created_at,
                   (SELECT COUNT(*) FROM tribe_map_links l
                    WHERE l.tribe_owner_id = o.id AND l.is_active = 1) AS maps,
                   (SELECT COUNT(*) FROM tribe_map_links l
                    WHERE l.tribe_owner_id = o.id AND l.tribe_type = 'principal'
                      AND l.is_active = 1) AS principals
            FROM tribe_owners o
            ORDER BY o.updated_at DESC
            LIMIT :lim
        """),
        {"lim": int(limit)},
    ).fetchall()
    return [
        {
            "tribe_owner_id": r[0],
            "steam_id": r[1],
            "display_name": r[2] or "",
            "created_at": str(r[3]) if r[3] else None,
            "map_count": int(r[4] or 0),
            "principal_count": int(r[5] or 0),
        }
        for r in rows
    ]


def list_admin_alerts(db: Session, *, unresolved_only: bool = True, limit: int = 50) -> list[dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT id, alert_type, severity, message, steam_id, server_id,
                   tribe_id, is_resolved, created_at
            FROM tribe_admin_alerts
            WHERE (:uo = 0 OR is_resolved = 0)
            ORDER BY created_at DESC
            LIMIT :lim
        """),
        {"uo": 1 if unresolved_only else 0, "lim": int(limit)},
    ).fetchall()
    return [
        {
            "id": r[0], "alert_type": r[1], "severity": r[2], "message": r[3],
            "steam_id": r[4], "server_id": r[5], "tribe_id": r[6],
            "is_resolved": bool(r[7]), "created_at": str(r[8]) if r[8] else None,
        }
        for r in rows
    ]

