"""Área de Tribo ARKLAND — lógica de negócio.

Implementa:
  - Esquema DB (tribe_owners, tribe_map_links, tribe_cluster_groups,
    tribe_members, tribe_presences, tribe_regulations,
    tribe_splits, tribe_split_members, tribe_split_audit)
  - Gestão de membros, presença, regulamento e cluster (principal + fobs)
  - Regras de split (R1–R14) — integração com market_listings via tribe_split_service

Padrão de integração (igual lottery_service):
  - ensure_tribe_schema(engine) — chamado em _migrate_schema do app.py
  - register_tribe_schema(engine) — idempotente
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

log = logging.getLogger("arkshop_web.tribe")

# ────────────────────────────────────────────────────────────
# Constantes de regras (spec §18)
# ────────────────────────────────────────────────────────────
SPLIT_MIN_SALE_AMBER = 1_000       # R8 — venda mínima para split
SPLIT_MAX_MEMBERS = 10             # R11
SPLIT_GAP_MIN_PP = 10              # R1 — gap mínimo vendedor vs próximo (p.p.)
SPLIT_COOLDOWN_HOURS = 48          # R3
SPLIT_REENTRY_HOURS = 45           # R4 — tempo mínimo pós opt-out
REGULAMENTO_MAX_CHARS = 5_000      # §19.4
REGULAMENTO_ADDENDUM_MAX_CHARS = 2_000

SPLIT_STATUSES = frozenset({
    "DRAFT", "PENDING_COOLDOWN", "ACTIVE", "PAUSED", "FROZEN", "DISABLED", "ORPHANED"
})
TRIBE_TYPES = frozenset({"principal", "fob"})
REG_ACTIONS = frozenset({
    "CREATED", "UPDATED", "VISIBILITY_CHANGED", "SUPPRESSED", "HIDDEN", "RESTORED"
})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _as_bool(value: Any) -> bool:
    """Normaliza flags vindas do plugin (bool/int/str)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {
            "1", "true", "yes", "y", "owner", "proprietario", "proprietário",
        }
    return bool(value)


def rank_implies_owner(rank: str | None) -> bool:
    """True se o nome do rank indica Proprietário/Owner (não Admin/Leader genérico)."""
    if not rank:
        return False
    r = str(rank).strip().lower()
    if not r:
        return False
    # Acentos comuns no cliente PT
    for a, b in (("á", "a"), ("ã", "a"), ("â", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        r = r.replace(a, b)
    if r in ("owner", "proprietario", "founder"):
        return True
    if "propriet" in r or "owner" in r:
        return True
    return False


def resolve_is_owner(*, is_owner: Any = None, member_rank: str | None = None) -> bool:
    """Combina flag explícita + rank (Owner/Proprietário)."""
    if _as_bool(is_owner):
        return True
    return rank_implies_owner(member_rank)


# ────────────────────────────────────────────────────────────
# Schema DDL
# ────────────────────────────────────────────────────────────

def ensure_tribe_schema(engine: Engine) -> None:
    """Cria todas as tabelas de tribo (idempotente — SQLite e MySQL)."""
    is_sqlite = "sqlite" in str(engine.url).lower()
    _pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if is_sqlite else "BIGINT AUTO_INCREMENT PRIMARY KEY"
    _now_col = "DATETIME" if is_sqlite else "DATETIME(6)"
    _tinyint = "INTEGER" if is_sqlite else "TINYINT(1)"

    ddls = [
        # ── Proprietário registrado no site
        f"""
        CREATE TABLE IF NOT EXISTS tribe_owners (
          id            {_pk},
          steam_id      VARCHAR(32) NOT NULL,
          display_name  VARCHAR(128) NOT NULL DEFAULT '',
          description   TEXT,
          log_visibility VARCHAR(16) NOT NULL DEFAULT 'members',
          created_at    {_now_col} NOT NULL,
          updated_at    {_now_col} NOT NULL,
          UNIQUE {"" if is_sqlite else "KEY uq_owner"} (steam_id)
        )
        """,
        # ── Presença/snapshot por mapa (enviado pelo plugin C++)
        f"""
        CREATE TABLE IF NOT EXISTS tribe_presences (
          id            {_pk},
          steam_id      VARCHAR(32) NOT NULL,
          server_id     VARCHAR(64) NOT NULL,
          map_name      VARCHAR(64) NOT NULL DEFAULT '',
          tribe_id      INTEGER,
          tribe_name    VARCHAR(128),
          is_owner      {_tinyint} NOT NULL DEFAULT 0,
          member_rank   VARCHAR(64),
          captured_at   {_now_col} NOT NULL,
          source        VARCHAR(16) NOT NULL DEFAULT 'login_hook'
        )
        """,
        # ── Membership atual por mapa
        f"""
        CREATE TABLE IF NOT EXISTS tribe_members (
          id            {_pk},
          server_id     VARCHAR(64) NOT NULL,
          tribe_id      INTEGER NOT NULL,
          tribe_name    VARCHAR(128) NOT NULL DEFAULT '',
          steam_id      VARCHAR(32) NOT NULL,
          character_name VARCHAR(128),
          is_owner      {_tinyint} NOT NULL DEFAULT 0,
          rank_name     VARCHAR(64),
          joined_at     {_now_col},
          last_seen_at  {_now_col},
          updated_at    {_now_col} NOT NULL,
          UNIQUE {"" if is_sqlite else "KEY uq_member_server"} (server_id, tribe_id, steam_id)
        )
        """,
        # ── Grupo cluster (principal + fobs)
        f"""
        CREATE TABLE IF NOT EXISTS tribe_cluster_groups (
          id                  {_pk},
          group_name          VARCHAR(128) NOT NULL DEFAULT '',
          anchor_server_id    VARCHAR(64) NOT NULL,
          anchor_tribe_id     INTEGER NOT NULL,
          created_by_steam_id VARCHAR(32) NOT NULL,
          created_at          {_now_col} NOT NULL,
          updated_at          {_now_col} NOT NULL
        )
        """,
        # ── Link mapa → tribo do dono (principal ou fob)
        f"""
        CREATE TABLE IF NOT EXISTS tribe_map_links (
          id                 {_pk},
          tribe_owner_id     INTEGER NOT NULL,
          server_id          VARCHAR(64) NOT NULL,
          tribe_id           INTEGER NOT NULL,
          tribe_name_local   VARCHAR(128) NOT NULL DEFAULT '',
          tribe_type         VARCHAR(16) NOT NULL DEFAULT 'principal',
          cluster_group_id   INTEGER,
          fob_owner_steam_id VARCHAR(32),
          is_active          {_tinyint} NOT NULL DEFAULT 1,
          confirmed_at       {_now_col} NOT NULL,
          UNIQUE {"" if is_sqlite else "KEY uq_link"} (tribe_owner_id, server_id)
        )
        """,
        # ── Regulamento da tribo
        f"""
        CREATE TABLE IF NOT EXISTS tribe_regulations (
          id             {_pk},
          tribe_owner_id INTEGER NOT NULL,
          version        INTEGER NOT NULL DEFAULT 1,
          content_text   TEXT NOT NULL DEFAULT '',
          checklist_json TEXT,
          visibility     VARCHAR(16) NOT NULL DEFAULT 'private',
          is_hidden      {_tinyint} NOT NULL DEFAULT 0,
          hidden_reason  TEXT,
          char_count     INTEGER NOT NULL DEFAULT 0,
          created_at     {_now_col} NOT NULL,
          updated_at     {_now_col} NOT NULL,
          updated_by     VARCHAR(32) NOT NULL DEFAULT ''
        )
        """,
        # ── Histórico de versões do regulamento
        f"""
        CREATE TABLE IF NOT EXISTS tribe_regulation_history (
          id                {_pk},
          regulation_id     INTEGER,
          version           INTEGER NOT NULL,
          action            VARCHAR(32) NOT NULL,
          actor_steam_id    VARCHAR(32) NOT NULL,
          old_content_text  TEXT,
          new_content_text  TEXT,
          created_at        {_now_col} NOT NULL
        )
        """,
        # ── Configuração de split por tribo
        f"""
        CREATE TABLE IF NOT EXISTS tribe_splits (
          id             {_pk},
          tribe_owner_id INTEGER NOT NULL,
          tribe_id       INTEGER NOT NULL,
          server_id      VARCHAR(64) NOT NULL,
          tribe_name     VARCHAR(128),
          status         VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
          cooldown_hours INTEGER NOT NULL DEFAULT 48,
          valid_from     {_now_col},
          created_at     {_now_col} NOT NULL,
          updated_at     {_now_col} NOT NULL,
          updated_by     VARCHAR(32)
        )
        """,
        # ── Membros do split
        f"""
        CREATE TABLE IF NOT EXISTS tribe_split_members (
          id           {_pk},
          split_id     INTEGER NOT NULL,
          steam_id     VARCHAR(32) NOT NULL,
          display_name VARCHAR(128),
          percentage   INTEGER NOT NULL DEFAULT 0,
          is_seller    {_tinyint} NOT NULL DEFAULT 0,
          opted_out    {_tinyint} NOT NULL DEFAULT 0,
          opted_out_at {_now_col},
          added_at     {_now_col} NOT NULL,
          UNIQUE {"" if is_sqlite else "KEY uq_member"} (split_id, steam_id)
        )
        """,
        # ── Audit log do split
        f"""
        CREATE TABLE IF NOT EXISTS tribe_split_audit (
          id               {_pk},
          split_id         INTEGER NOT NULL,
          action           VARCHAR(32) NOT NULL,
          actor_steam_id   VARCHAR(32) NOT NULL,
          target_steam_id  VARCHAR(32),
          old_value_json   TEXT,
          new_value_json   TEXT,
          created_at       {_now_col} NOT NULL,
          ip_address       VARCHAR(45)
        )
        """,
    ]

    with engine.connect() as conn:
        for ddl in ddls:
            try:
                conn.execute(text(ddl))
            except Exception as exc:
                log.warning("tribe_schema DDL parcial: %s", exc)
        # Adiciona colunas de split em market_listings se não existirem
        _add_col_if_missing(conn, is_sqlite, "market_listings", "tribe_split_id", "INTEGER")
        _add_col_if_missing(conn, is_sqlite, "market_listings", "split_snapshot", "TEXT")
        conn.commit()
    log.info("tribe_schema: tabelas verificadas/criadas")


def _add_col_if_missing(conn: Any, is_sqlite: bool, table: str, col: str, col_type: str) -> None:
    """Adiciona coluna idempotente (SQLite e MySQL)."""
    try:
        if is_sqlite:
            existing = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            cols = [r[1] for r in existing]
            if col not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
        else:
            row = conn.execute(text(
                f"SHOW COLUMNS FROM `{table}` LIKE '{col}'"
            )).fetchone()
            if row is None:
                conn.execute(text(
                    f"ALTER TABLE `{table}` ADD COLUMN `{col}` {col_type}"
                ))
    except Exception as exc:
        log.debug("tribe_schema alter col %s.%s: %s", table, col, exc)


# ────────────────────────────────────────────────────────────
# Funções de tribe_owner
# ────────────────────────────────────────────────────────────

def get_or_create_owner(db: Session, steam_id: str, display_name: str = "") -> dict[str, Any]:
    """Retorna ou cria tribe_owner para este steam_id."""
    row = db.execute(
        text("SELECT id, steam_id, display_name, description, log_visibility, created_at FROM tribe_owners WHERE steam_id = :sid"),
        {"sid": steam_id},
    ).fetchone()
    if row:
        return _owner_row_to_dict(row)
    now = _naive(_utcnow())
    db.execute(
        text("""
            INSERT INTO tribe_owners (steam_id, display_name, description, log_visibility, created_at, updated_at)
            VALUES (:sid, :dn, '', 'members', :now, :now)
        """),
        {"sid": steam_id, "dn": display_name or steam_id, "now": now},
    )
    db.commit()
    return get_or_create_owner(db, steam_id, display_name)


def _is_usable_server_id(server_id: str | None) -> bool:
    sid = str(server_id or "").strip().lower()
    return bool(sid) and sid not in ("unknown", "server")


def backfill_owner_links_from_presence(db: Session, steam_id: str) -> int:
    """Cria tribe_map_links a partir de tribe_presences onde o jogador foi líder.

    Útil quando o jogador logou no servidor *antes* de ativar o painel no site.
    Aceita is_owner=1 ou rank Proprietário/Owner (presenças antigas mal marcadas).
    Retorna quantos links novos foram criados.
    """
    owner = get_owner(db, steam_id)
    if not owner:
        return 0
    rows = db.execute(
        text("""
            SELECT server_id, tribe_id, tribe_name, is_owner, member_rank, captured_at
            FROM tribe_presences
            WHERE steam_id = :sid AND tribe_id IS NOT NULL
            ORDER BY captured_at DESC
        """),
        {"sid": steam_id},
    ).fetchall()
    created = 0
    seen_servers: set[str] = set()
    now = _naive(_utcnow())
    for r in rows:
        server_id = str(r[0] or "")
        if not _is_usable_server_id(server_id) or server_id in seen_servers:
            continue
        if not resolve_is_owner(is_owner=r[3], member_rank=r[4]):
            continue
        seen_servers.add(server_id)
        tribe_id = int(r[1])
        tribe_name = str(r[2] or "") or f"Tribo {tribe_id}"
        before = db.execute(
            text("SELECT id FROM tribe_map_links WHERE tribe_owner_id = :oid AND server_id = :sid"),
            {"oid": owner["id"], "sid": server_id},
        ).fetchone()
        _auto_link_owner(
            db, owner=owner, server_id=server_id,
            tribe_id=tribe_id, tribe_name=tribe_name, now=now,
        )
        after = db.execute(
            text("SELECT id FROM tribe_map_links WHERE tribe_owner_id = :oid AND server_id = :sid"),
            {"oid": owner["id"], "sid": server_id},
        ).fetchone()
        if after and not before:
            created += 1
    if created:
        db.commit()
    return created


def get_owner(db: Session, steam_id: str) -> dict[str, Any] | None:
    row = db.execute(
        text("SELECT id, steam_id, display_name, description, log_visibility, created_at FROM tribe_owners WHERE steam_id = :sid"),
        {"sid": steam_id},
    ).fetchone()
    return _owner_row_to_dict(row) if row else None


def _owner_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row[0],
        "steam_id": row[1],
        "display_name": row[2] or "",
        "description": row[3] or "",
        "log_visibility": row[4] or "members",
        "created_at": str(row[5]) if row[5] else None,
    }


def update_owner_profile(db: Session, steam_id: str, *, display_name: str | None = None,
                          description: str | None = None, log_visibility: str | None = None) -> dict[str, Any]:
    owner = get_or_create_owner(db, steam_id)
    sets: list[str] = []
    params: dict[str, Any] = {"sid": steam_id, "now": _naive(_utcnow())}
    if display_name is not None:
        sets.append("display_name = :dn")
        params["dn"] = display_name[:128]
    if description is not None:
        sets.append("description = :desc")
        params["desc"] = description[:1000]
    if log_visibility in ("owner", "members", "public"):
        sets.append("log_visibility = :lv")
        params["lv"] = log_visibility
    if sets:
        db.execute(text(
            f"UPDATE tribe_owners SET {', '.join(sets)}, updated_at = :now WHERE steam_id = :sid"
        ), params)
        db.commit()
    return get_owner(db, steam_id) or {}


# ────────────────────────────────────────────────────────────
# tribe_map_links (vínculo owner ↔ tribo por mapa)
# ────────────────────────────────────────────────────────────

def get_map_links(db: Session, tribe_owner_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT id, tribe_owner_id, server_id, tribe_id, tribe_name_local,
                   tribe_type, cluster_group_id, fob_owner_steam_id, is_active, confirmed_at
            FROM tribe_map_links WHERE tribe_owner_id = :oid ORDER BY tribe_type, server_id
        """),
        {"oid": tribe_owner_id},
    ).fetchall()
    return [_link_row_to_dict(r) for r in rows]


def _link_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row[0],
        "tribe_owner_id": row[1],
        "server_id": row[2],
        "tribe_id": row[3],
        "tribe_name_local": row[4] or "",
        "tribe_type": row[5] or "principal",
        "cluster_group_id": row[6],
        "fob_owner_steam_id": row[7],
        "is_active": bool(row[8]),
        "confirmed_at": str(row[9]) if row[9] else None,
    }


def upsert_map_link(
    db: Session,
    *,
    tribe_owner_id: int,
    server_id: str,
    tribe_id: int,
    tribe_name_local: str,
    tribe_type: str = "principal",
    fob_owner_steam_id: str | None = None,
    cluster_group_id: int | None = None,
) -> dict[str, Any]:
    """Cria ou atualiza vínculo. Se tribe_type='fob', requer cluster_group_id."""
    if tribe_type not in TRIBE_TYPES:
        raise ValueError(f"tribe_type inválido: {tribe_type}")

    now = _naive(_utcnow())
    existing = db.execute(
        text("SELECT id FROM tribe_map_links WHERE tribe_owner_id = :oid AND server_id = :sid"),
        {"oid": tribe_owner_id, "sid": server_id},
    ).fetchone()

    if existing:
        db.execute(text("""
            UPDATE tribe_map_links
            SET tribe_id = :tid, tribe_name_local = :tn, tribe_type = :tt,
                cluster_group_id = :cgid, fob_owner_steam_id = :fob, is_active = 1,
                confirmed_at = :now
            WHERE tribe_owner_id = :oid AND server_id = :sid
        """), {
            "tid": tribe_id, "tn": tribe_name_local[:128], "tt": tribe_type,
            "cgid": cluster_group_id, "fob": fob_owner_steam_id, "now": now,
            "oid": tribe_owner_id, "sid": server_id,
        })
    else:
        db.execute(text("""
            INSERT INTO tribe_map_links
              (tribe_owner_id, server_id, tribe_id, tribe_name_local, tribe_type,
               cluster_group_id, fob_owner_steam_id, is_active, confirmed_at)
            VALUES (:oid, :sid, :tid, :tn, :tt, :cgid, :fob, 1, :now)
        """), {
            "oid": tribe_owner_id, "sid": server_id, "tid": tribe_id,
            "tn": tribe_name_local[:128], "tt": tribe_type,
            "cgid": cluster_group_id, "fob": fob_owner_steam_id, "now": now,
        })
    db.commit()
    row = db.execute(
        text("SELECT id, tribe_owner_id, server_id, tribe_id, tribe_name_local, tribe_type, cluster_group_id, fob_owner_steam_id, is_active, confirmed_at FROM tribe_map_links WHERE tribe_owner_id = :oid AND server_id = :sid"),
        {"oid": tribe_owner_id, "sid": server_id},
    ).fetchone()
    return _link_row_to_dict(row)


# ────────────────────────────────────────────────────────────
# tribe_presences (snapshot do plugin C++)
# ────────────────────────────────────────────────────────────

def record_presence(
    db: Session,
    *,
    steam_id: str,
    server_id: str,
    map_name: str,
    tribe_id: int | None,
    tribe_name: str | None,
    is_owner: bool | Any = False,
    member_rank: str | None = None,
    source: str = "login_hook",
    members: list[dict[str, Any]] | None = None,
) -> None:
    """Grava snapshot de presença e atualiza tribe_members."""
    steam_id = str(steam_id or "").strip()
    server_id = str(server_id or "").strip()
    tribe_name_s = str(tribe_name or "").strip()
    member_rank_s = str(member_rank or "").strip() or None
    owner_flag = resolve_is_owner(is_owner=is_owner, member_rank=member_rank_s)

    # Normaliza membros: is_owner via flag ou rank_name
    normalized_members: list[dict[str, Any]] | None = None
    if members:
        normalized_members = []
        for m in members:
            mm = dict(m)
            mm["is_owner"] = resolve_is_owner(
                is_owner=mm.get("is_owner"),
                member_rank=mm.get("rank_name") or mm.get("member_rank"),
            )
            sid = str(mm.get("steam_id") or "").strip()
            if sid:
                mm["steam_id"] = sid
                normalized_members.append(mm)

    now = _naive(_utcnow())
    db.execute(text("""
        INSERT INTO tribe_presences
          (steam_id, server_id, map_name, tribe_id, tribe_name, is_owner, member_rank, captured_at, source)
        VALUES (:sid, :svid, :mn, :tid, :tn, :iso, :mr, :now, :src)
    """), {
        "sid": steam_id, "svid": server_id, "mn": map_name or server_id,
        "tid": tribe_id, "tn": tribe_name_s or None,
        "iso": 1 if owner_flag else 0,
        "mr": member_rank_s, "now": now, "src": source,
    })

    # Se enviou lista de membros, upsert em tribe_members
    if normalized_members and tribe_id:
        _upsert_members(
            db, server_id=server_id, tribe_id=int(tribe_id),
            tribe_name=tribe_name_s, members=normalized_members, now=now,
        )

    # Auto-vincula owner ao tribe_map_links (tribe_name opcional — nome vazio não bloqueia)
    if owner_flag and tribe_id and _is_usable_server_id(server_id):
        owner = get_owner(db, steam_id)
        if owner:
            _auto_link_owner(
                db, owner=owner, server_id=server_id,
                tribe_id=int(tribe_id),
                tribe_name=tribe_name_s or f"Tribo {tribe_id}",
                now=now,
            )

    db.commit()


def _upsert_members(
    db: Session, *, server_id: str, tribe_id: int,
    tribe_name: str, members: list[dict[str, Any]], now: datetime
) -> None:
    for m in members:
        sid = str(m.get("steam_id") or "")
        if not sid:
            continue
        existing = db.execute(
            text("SELECT id FROM tribe_members WHERE server_id = :svid AND tribe_id = :tid AND steam_id = :sid"),
            {"svid": server_id, "tid": tribe_id, "sid": sid},
        ).fetchone()
        if existing:
            db.execute(text("""
                UPDATE tribe_members
                SET character_name = :cn, is_owner = :iso, rank_name = :rn,
                    last_seen_at = :now, updated_at = :now, tribe_name = :tn
                WHERE server_id = :svid AND tribe_id = :tid AND steam_id = :sid
            """), {
                "cn": m.get("character_name"), "iso": 1 if m.get("is_owner") else 0,
                "rn": m.get("rank_name"), "now": now, "tn": tribe_name,
                "svid": server_id, "tid": tribe_id, "sid": sid,
            })
        else:
            db.execute(text("""
                INSERT INTO tribe_members
                  (server_id, tribe_id, tribe_name, steam_id, character_name, is_owner, rank_name, joined_at, last_seen_at, updated_at)
                VALUES (:svid, :tid, :tn, :sid, :cn, :iso, :rn, :now, :now, :now)
            """), {
                "svid": server_id, "tid": tribe_id, "tn": tribe_name, "sid": sid,
                "cn": m.get("character_name"), "iso": 1 if m.get("is_owner") else 0,
                "rn": m.get("rank_name"), "now": now,
            })


def _auto_link_owner(
    db: Session, *, owner: dict[str, Any], server_id: str,
    tribe_id: int, tribe_name: str, now: datetime
) -> None:
    """Vincula automaticamente owner à tribo detectada no login (se ainda não vinculado)."""
    existing = db.execute(
        text("SELECT id, tribe_id FROM tribe_map_links WHERE tribe_owner_id = :oid AND server_id = :sid"),
        {"oid": owner["id"], "sid": server_id},
    ).fetchone()
    if existing is None:
        # Primeira detecção — cria link como principal (pode ser alterado depois)
        db.execute(text("""
            INSERT INTO tribe_map_links
              (tribe_owner_id, server_id, tribe_id, tribe_name_local, tribe_type, is_active, confirmed_at)
            VALUES (:oid, :sid, :tid, :tn, 'principal', 1, :now)
        """), {"oid": owner["id"], "sid": server_id, "tid": tribe_id, "tn": tribe_name, "now": now})
    elif existing[1] != tribe_id:
        # TribeID mudou (pós-wipe) — atualiza e marca para re-vínculo
        db.execute(text("""
            UPDATE tribe_map_links
            SET tribe_id = :tid, tribe_name_local = :tn, confirmed_at = :now
            WHERE tribe_owner_id = :oid AND server_id = :sid
        """), {"tid": tribe_id, "tn": tribe_name, "now": now, "oid": owner["id"], "sid": server_id})


# ────────────────────────────────────────────────────────────
# Consulta "Minha Tribo"
# ────────────────────────────────────────────────────────────

def get_presence_summary(db: Session, steam_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
    """Últimas presenças do jogador (diagnóstico / sync forçado)."""
    rows = db.execute(
        text("""
            SELECT server_id, tribe_id, tribe_name, is_owner, member_rank, captured_at, source
            FROM tribe_presences
            WHERE steam_id = :sid
            ORDER BY captured_at DESC
            LIMIT :lim
        """),
        {"sid": steam_id, "lim": int(limit)},
    ).fetchall()
    return [
        {
            "server_id": r[0],
            "tribe_id": r[1],
            "tribe_name": r[2] or "",
            "is_owner": bool(r[3]),
            "member_rank": r[4] or "",
            "captured_at": str(r[5]) if r[5] else None,
            "source": r[6] or "",
        }
        for r in rows
    ]


def sync_owner_maps(db: Session, steam_id: str) -> dict[str, Any]:
    """Reaplica backfill a partir de tribe_presences e devolve diagnóstico.

    Usado pelo botão «Verificar de novo» — não contacta o servidor ARK;
    depende de snapshots já enviados pelo plugin no login.
    """
    steam_id = str(steam_id or "").strip()
    owner = get_owner(db, steam_id)
    if not owner:
        return {
            "panel_activated": False,
            "maps_linked": 0,
            "maps": [],
            "presences": get_presence_summary(db, steam_id),
            "hint": "Ative o painel de tribo primeiro.",
        }

    linked = backfill_owner_links_from_presence(db, steam_id)
    tribes = get_my_tribes(db, steam_id, _skip_backfill=True)
    presences = get_presence_summary(db, steam_id)
    owner_presences = [p for p in presences if p.get("is_owner")]
    usable_owner = [
        p for p in owner_presences if _is_usable_server_id(p.get("server_id"))
    ]
    hint = None
    if not tribes.get("maps"):
        if not presences:
            hint = (
                "Nenhuma presença in-game registada. Relogue no servidor ARKLAND "
                "como Proprietário da tribo (após o plugin CustomShop com TribeSync) "
                "e depois clique em Verificar de novo. Se já relogou: confirme no log "
                "do mapa a linha «TribeSync: presence OK» e CrossChat.ServerId no config."
            )
        elif not owner_presences:
            hint = (
                "Há presença no mapa, mas o sistema não marcou ownership "
                "(OwnerPlayerDataID / rank Proprietário). Confirme que é o "
                "Proprietário da tribo in-game (não só Admin) e relogue."
            )
        elif not usable_owner:
            hint = (
                "Presença de líder chegou com ServerId inválido (unknown). "
                "No TEK, sincronize o CustomShop do mapa para gravar "
                "CrossChat.ServerId (ex.: BRIGHAMIA), faça Shop.Reload ou reinicie "
                "o mapa e relogue."
            )
        else:
            hint = "Presença de líder encontrada, mas o vínculo falhou — tente novamente."
    return {
        "panel_activated": True,
        "is_owner": True,
        "maps_linked": linked,
        "maps": tribes.get("maps") or [],
        "owner": tribes.get("owner"),
        "presences": presences,
        "hint": hint,
        "_regulation": tribes.get("_regulation"),
        "_split": tribes.get("_split"),
    }


def get_my_tribes(db: Session, steam_id: str, *, _skip_backfill: bool = False) -> dict[str, Any]:
    """Retorna visão agregada das tribos do jogador por mapa."""
    owner = get_owner(db, steam_id)
    if owner and not _skip_backfill:
        # Presença pode ter chegado depois de ativar o painel — vincula oportunisticamente
        try:
            backfill_owner_links_from_presence(db, steam_id)
        except Exception as exc:
            log.debug("get_my_tribes backfill: %s", exc)

    if not owner:
        # Membro (não dono do painel): mapas onde aparece em tribe_members / presence
        member_rows = db.execute(
            text("""
                SELECT server_id, tribe_id, tribe_name
                FROM tribe_members WHERE steam_id = :sid
                ORDER BY last_seen_at DESC
            """),
            {"sid": steam_id},
        ).fetchall()
        if not member_rows:
            member_rows = db.execute(
                text("""
                    SELECT server_id, tribe_id, tribe_name
                    FROM tribe_presences WHERE steam_id = :sid AND tribe_id IS NOT NULL
                    ORDER BY captured_at DESC
                """),
                {"sid": steam_id},
            ).fetchall()

        maps_data: list[dict[str, Any]] = []
        seen: set[tuple[str, int]] = set()
        for r in member_rows:
            key = (str(r[0]), int(r[1] or 0))
            if key in seen or not key[1]:
                continue
            seen.add(key)
            members = get_members_by_map(db, server_id=key[0], tribe_id=key[1])
            maps_data.append({
                "server_id": key[0],
                "tribe_id": key[1],
                "tribe_name": r[2] or "",
                "tribe_name_local": r[2] or "",
                "tribe_type": "principal",
                "members": members,
                "member_count": len(members),
            })
        return {
            "is_owner": False,
            "owner": None,
            "maps": maps_data,
            "panel_activated": False,
            "_regulation": None,
            "_split": None,
        }

    links = get_map_links(db, owner["id"])
    maps_data = []
    for link in links:
        members = get_members_by_map(db, server_id=link["server_id"], tribe_id=link["tribe_id"])
        maps_data.append({
            **link,
            "members": members,
            "member_count": len(members),
        })

    return {
        "is_owner": True,
        "owner": owner,
        "maps": maps_data,
        "panel_activated": True,
        "_regulation": get_regulation(db, owner["id"]),
        "_split": get_active_split(db, owner["id"]),
    }


def manual_add_member(
    db: Session,
    *,
    owner_steam_id: str,
    server_id: str,
    tribe_id: int,
    member_steam_id: str,
    character_name: str = "",
) -> dict[str, Any]:
    """Owner registra manualmente um membro (SteamID64) na tribo do mapa.

    Complementa a detecção automática via login — útil quando o plugin ainda
    não reportou presença ou o membro ainda não entrou no servidor.
    """
    member_steam_id = (member_steam_id or "").strip()
    if not member_steam_id.isdigit() or len(member_steam_id) < 15:
        raise ValueError("SteamID64 inválido")
    if not server_id or not tribe_id:
        raise ValueError("server_id e tribe_id obrigatórios")

    owner = get_owner(db, owner_steam_id)
    if not owner:
        raise ValueError("Painel de tribo não ativado. Use /api/tribe/register primeiro.")

    link = db.execute(
        text("""
            SELECT id, tribe_name_local FROM tribe_map_links
            WHERE tribe_owner_id = :oid AND server_id = :sid AND tribe_id = :tid AND is_active = 1
        """),
        {"oid": owner["id"], "sid": server_id, "tid": tribe_id},
    ).fetchone()
    if not link:
        raise ValueError("Mapa/tribo não vinculado ao seu painel")

    now = _naive(_utcnow())
    tribe_name = link[1] or ""
    _upsert_members(
        db,
        server_id=server_id,
        tribe_id=tribe_id,
        tribe_name=tribe_name,
        members=[{
            "steam_id": member_steam_id,
            "character_name": (character_name or member_steam_id)[:128],
            "is_owner": False,
            "rank_name": "Membro",
        }],
        now=now,
    )
    db.commit()
    return {
        "steam_id": member_steam_id,
        "character_name": character_name or member_steam_id,
        "server_id": server_id,
        "tribe_id": tribe_id,
    }


def get_members_by_map(
    db: Session, *, server_id: str, tribe_id: int
) -> list[dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT steam_id, character_name, is_owner, rank_name, last_seen_at
            FROM tribe_members WHERE server_id = :svid AND tribe_id = :tid
            ORDER BY is_owner DESC, last_seen_at DESC
        """),
        {"svid": server_id, "tid": tribe_id},
    ).fetchall()
    return [
        {
            "steam_id": r[0],
            "character_name": r[1] or "",
            "is_owner": bool(r[2]),
            "rank_name": r[3] or "",
            "last_seen_at": str(r[4]) if r[4] else None,
        }
        for r in rows
    ]


def is_tribe_member(db: Session, steam_id: str, server_id: str, tribe_id: int) -> bool:
    row = db.execute(
        text("SELECT 1 FROM tribe_members WHERE steam_id = :sid AND server_id = :svid AND tribe_id = :tid"),
        {"sid": steam_id, "svid": server_id, "tid": tribe_id},
    ).fetchone()
    return row is not None


# ────────────────────────────────────────────────────────────
# Regulamento interno (§19)
# ────────────────────────────────────────────────────────────

def get_regulation(db: Session, tribe_owner_id: int) -> dict[str, Any] | None:
    row = db.execute(
        text("""
            SELECT id, tribe_owner_id, version, content_text, checklist_json,
                   visibility, is_hidden, char_count, created_at, updated_at, updated_by
            FROM tribe_regulations WHERE tribe_owner_id = :oid
            ORDER BY id DESC LIMIT 1
        """),
        {"oid": tribe_owner_id},
    ).fetchone()
    return _reg_row_to_dict(row) if row else None


def _reg_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row[0],
        "tribe_owner_id": row[1],
        "version": row[2],
        "content_text": row[3] or "",
        "checklist_json": json.loads(row[4]) if row[4] else None,
        "visibility": row[5] or "private",
        "is_hidden": bool(row[6]),
        "char_count": row[7],
        "created_at": str(row[8]) if row[8] else None,
        "updated_at": str(row[9]) if row[9] else None,
        "updated_by": row[10] or "",
    }


def save_regulation(
    db: Session,
    *,
    tribe_owner_id: int,
    content_text: str,
    actor_steam_id: str,
    visibility: str = "private",
    checklist_json: dict | None = None,
) -> dict[str, Any]:
    """Salva ou atualiza regulamento (cria nova versão)."""
    if len(content_text) > REGULAMENTO_MAX_CHARS:
        raise ValueError(f"Regulamento excede {REGULAMENTO_MAX_CHARS} caracteres")
    if visibility not in ("private", "public"):
        visibility = "private"

    now = _naive(_utcnow())
    existing = get_regulation(db, tribe_owner_id)
    checklist_str = json.dumps(checklist_json, ensure_ascii=False) if checklist_json else None

    if existing:
        new_version = existing["version"] + 1
        old_text = existing["content_text"]
        action = "UPDATED" if old_text != content_text else "VISIBILITY_CHANGED"

        db.execute(text("""
            UPDATE tribe_regulations
            SET version = :ver, content_text = :ct, checklist_json = :cj,
                visibility = :vis, char_count = :cc, updated_at = :now, updated_by = :by
            WHERE id = :rid
        """), {
            "ver": new_version, "ct": content_text, "cj": checklist_str,
            "vis": visibility, "cc": len(content_text), "now": now,
            "by": actor_steam_id, "rid": existing["id"],
        })

        # Registra histórico
        db.execute(text("""
            INSERT INTO tribe_regulation_history
              (regulation_id, version, action, actor_steam_id, old_content_text, new_content_text, created_at)
            VALUES (:rid, :ver, :act, :actor, :old, :new, :now)
        """), {
            "rid": existing["id"], "ver": new_version, "act": action,
            "actor": actor_steam_id, "old": old_text, "new": content_text, "now": now,
        })
    else:
        db.execute(text("""
            INSERT INTO tribe_regulations
              (tribe_owner_id, version, content_text, checklist_json, visibility,
               is_hidden, char_count, created_at, updated_at, updated_by)
            VALUES (:oid, 1, :ct, :cj, :vis, 0, :cc, :now, :now, :by)
        """), {
            "oid": tribe_owner_id, "ct": content_text, "cj": checklist_str,
            "vis": visibility, "cc": len(content_text), "now": now,
            "by": actor_steam_id,
        })
        reg_id = db.execute(
            text("SELECT id FROM tribe_regulations WHERE tribe_owner_id = :oid ORDER BY id DESC LIMIT 1"),
            {"oid": tribe_owner_id},
        ).fetchone()[0]
        db.execute(text("""
            INSERT INTO tribe_regulation_history
              (regulation_id, version, action, actor_steam_id, old_content_text, new_content_text, created_at)
            VALUES (:rid, 1, 'CREATED', :actor, NULL, :new, :now)
        """), {"rid": reg_id, "actor": actor_steam_id, "new": content_text, "now": now})

    db.commit()
    return get_regulation(db, tribe_owner_id) or {}


# ────────────────────────────────────────────────────────────
# Cluster group (principal + fobs) — Opção A
# ────────────────────────────────────────────────────────────

def create_cluster_group(
    db: Session,
    *,
    group_name: str,
    anchor_server_id: str,
    anchor_tribe_id: int,
    created_by_steam_id: str,
) -> dict[str, Any]:
    now = _naive(_utcnow())
    db.execute(text("""
        INSERT INTO tribe_cluster_groups
          (group_name, anchor_server_id, anchor_tribe_id, created_by_steam_id, created_at, updated_at)
        VALUES (:gn, :asid, :atid, :by, :now, :now)
    """), {
        "gn": group_name[:128], "asid": anchor_server_id, "atid": anchor_tribe_id,
        "by": created_by_steam_id, "now": now,
    })
    db.commit()
    row = db.execute(
        text("SELECT id, group_name, anchor_server_id, anchor_tribe_id, created_by_steam_id, created_at FROM tribe_cluster_groups ORDER BY id DESC LIMIT 1"),
        {},
    ).fetchone()
    return {
        "id": row[0], "group_name": row[1],
        "anchor_server_id": row[2], "anchor_tribe_id": row[3],
        "created_by_steam_id": row[4], "created_at": str(row[5]),
    }


def link_fob(
    db: Session,
    *,
    cluster_group_id: int,
    tribe_owner_id: int,
    server_id: str,
    tribe_id: int,
    tribe_name: str,
    fob_owner_steam_id: str,
) -> dict[str, Any]:
    """Vincula uma fob ao cluster group. Apenas owner principal pode fazer isso."""
    now = _naive(_utcnow())
    upsert_map_link(
        db,
        tribe_owner_id=tribe_owner_id,
        server_id=server_id,
        tribe_id=tribe_id,
        tribe_name_local=tribe_name,
        tribe_type="fob",
        fob_owner_steam_id=fob_owner_steam_id,
        cluster_group_id=cluster_group_id,
    )
    # Atualiza timestamp do grupo
    db.execute(
        text("UPDATE tribe_cluster_groups SET updated_at = :now WHERE id = :gid"),
        {"now": now, "gid": cluster_group_id},
    )
    db.commit()
    return {"ok": True, "server_id": server_id, "tribe_id": tribe_id, "tribe_type": "fob"}


# ────────────────────────────────────────────────────────────
# Split — configuração e validação (§18)
# ────────────────────────────────────────────────────────────

def get_active_split(db: Session, tribe_owner_id: int) -> dict[str, Any] | None:
    """Retorna split ACTIVE ou PENDING_COOLDOWN da tribo principal."""
    row = db.execute(
        text("""
            SELECT id, tribe_owner_id, tribe_id, server_id, tribe_name, status,
                   cooldown_hours, valid_from, created_at, updated_at, updated_by
            FROM tribe_splits
            WHERE tribe_owner_id = :oid AND status NOT IN ('DISABLED','ORPHANED')
            ORDER BY id DESC LIMIT 1
        """),
        {"oid": tribe_owner_id},
    ).fetchone()
    if not row:
        return None
    split = _split_row_to_dict(row)
    split["members"] = _get_split_members(db, split["id"])
    return split


def _split_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row[0],
        "tribe_owner_id": row[1],
        "tribe_id": row[2],
        "server_id": row[3],
        "tribe_name": row[4] or "",
        "status": row[5],
        "cooldown_hours": row[6],
        "valid_from": str(row[7]) if row[7] else None,
        "created_at": str(row[8]) if row[8] else None,
        "updated_at": str(row[9]) if row[9] else None,
        "updated_by": row[10] or "",
    }


def _get_split_members(db: Session, split_id: int) -> list[dict[str, Any]]:
    rows = db.execute(
        text("""
            SELECT id, split_id, steam_id, display_name, percentage, is_seller,
                   opted_out, opted_out_at, added_at
            FROM tribe_split_members WHERE split_id = :sid ORDER BY is_seller DESC, percentage DESC
        """),
        {"sid": split_id},
    ).fetchall()
    return [
        {
            "id": r[0], "split_id": r[1], "steam_id": r[2],
            "display_name": r[3] or r[2], "percentage": r[4],
            "is_seller": bool(r[5]), "opted_out": bool(r[6]),
            "opted_out_at": str(r[7]) if r[7] else None,
            "added_at": str(r[8]) if r[8] else None,
        }
        for r in rows
    ]


def validate_split_config(members: list[dict[str, Any]]) -> None:
    """
    Valida R1 (gap ≥ 10 p.p.) e R2 (soma = 100%).
    Lança ValueError com mensagem clara se inválido.
    """
    active = [m for m in members if not m.get("opted_out")]
    if len(active) < 2:
        raise ValueError("Split exige ao menos 2 participantes ativos.")
    if len(active) > SPLIT_MAX_MEMBERS:
        raise ValueError(f"Split permite no máximo {SPLIT_MAX_MEMBERS} membros.")

    total = sum(int(m["percentage"]) for m in active)
    if total != 100:
        raise ValueError(f"Soma dos percentuais deve ser exatamente 100% (atual: {total}%).")

    seller = next((m for m in active if m.get("is_seller")), None)
    if not seller:
        raise ValueError("Configuração deve ter um vendedor/lister marcado.")

    pct_seller = int(seller["percentage"])
    others_pct = [int(m["percentage"]) for m in active if not m.get("is_seller")]
    max_other = max(others_pct) if others_pct else 0

    if pct_seller <= max_other:
        raise ValueError(
            "O vendedor deve ter percentual estritamente maior que qualquer outro membro."
        )
    gap = pct_seller - max_other
    if gap < SPLIT_GAP_MIN_PP:
        raise ValueError(
            f"Gap mínimo entre vendedor e próximo membro é {SPLIT_GAP_MIN_PP} p.p. "
            f"(atual: {gap} p.p., vendedor: {pct_seller}%, próximo: {max_other}%)."
        )


def recalc_proportional(
    members: list[dict[str, Any]], opted_out_steam_id: str
) -> list[dict[str, Any]]:
    """
    R4 — Recalcula percentuais proporcionalmente após opt-out de um membro.
    Retorna nova lista de membros ativos (sem o que saiu).
    O remainder de arredondamento vai ao vendedor.
    """
    import copy
    members = copy.deepcopy(members)

    # Encontra o membro que saiu
    leaving = next((m for m in members if m["steam_id"] == opted_out_steam_id), None)
    if not leaving:
        raise ValueError("Membro não encontrado no split.")
    if leaving.get("is_seller"):
        raise ValueError("O vendedor não pode fazer opt-out sem desativar o split.")

    freed_pct = int(leaving["percentage"])
    remaining = [m for m in members if m["steam_id"] != opted_out_steam_id and not m.get("opted_out")]
    if not remaining:
        raise ValueError("Sem membros restantes após opt-out.")

    soma_restante = sum(int(m["percentage"]) for m in remaining)
    if soma_restante <= 0:
        raise ValueError("Soma dos percentuais restantes é zero — impossível recalcular.")

    # Distribui proporcionalmente
    total_distributed = 0
    seller = next((m for m in remaining if m.get("is_seller")), remaining[0])

    for m in remaining:
        if m["steam_id"] == seller["steam_id"]:
            continue
        added = round(freed_pct * int(m["percentage"]) / soma_restante)
        m["percentage"] = int(m["percentage"]) + added
        total_distributed += added

    # Remainder ao vendedor
    seller["percentage"] = int(seller["percentage"]) + (freed_pct - total_distributed)

    return remaining


def create_or_update_split(
    db: Session,
    *,
    tribe_owner_id: int,
    tribe_id: int,
    server_id: str,
    tribe_name: str,
    members: list[dict[str, Any]],
    actor_steam_id: str,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """
    Cria ou atualiza configuração de split.
    Valida R1+R2 antes de salvar. Aplica cooldown R3.
    """
    # Verifica se mapa é fob — fobs não têm split (R13)
    link = db.execute(
        text("SELECT tribe_type FROM tribe_map_links WHERE tribe_owner_id = :oid AND server_id = :sid"),
        {"oid": tribe_owner_id, "sid": server_id},
    ).fetchone()
    if link and link[0] == "fob":
        raise ValueError("Fobs não possuem configuração de split (R13). Split é exclusivo da tribo principal.")

    validate_split_config(members)

    now = _naive(_utcnow())
    valid_from = now + timedelta(hours=SPLIT_COOLDOWN_HOURS)

    existing = get_active_split(db, tribe_owner_id)
    old_json = json.dumps(existing, default=str) if existing else None

    if existing:
        # Atualiza
        db.execute(text("""
            UPDATE tribe_splits
            SET tribe_id = :tid, server_id = :sid, tribe_name = :tn,
                status = 'PENDING_COOLDOWN', valid_from = :vf,
                updated_at = :now, updated_by = :by
            WHERE id = :spid
        """), {
            "tid": tribe_id, "sid": server_id, "tn": tribe_name,
            "vf": valid_from, "now": now, "by": actor_steam_id,
            "spid": existing["id"],
        })
        split_id = existing["id"]
        # Limpa membros antigos
        db.execute(text("DELETE FROM tribe_split_members WHERE split_id = :sid"), {"sid": split_id})
    else:
        db.execute(text("""
            INSERT INTO tribe_splits
              (tribe_owner_id, tribe_id, server_id, tribe_name, status,
               cooldown_hours, valid_from, created_at, updated_at, updated_by)
            VALUES (:oid, :tid, :sid, :tn, 'PENDING_COOLDOWN', :ch, :vf, :now, :now, :by)
        """), {
            "oid": tribe_owner_id, "tid": tribe_id, "sid": server_id, "tn": tribe_name,
            "ch": SPLIT_COOLDOWN_HOURS, "vf": valid_from, "now": now, "by": actor_steam_id,
        })
        row = db.execute(
            text("SELECT id FROM tribe_splits WHERE tribe_owner_id = :oid ORDER BY id DESC LIMIT 1"),
            {"oid": tribe_owner_id},
        ).fetchone()
        split_id = row[0]

    # Insere membros
    for m in members:
        db.execute(text("""
            INSERT INTO tribe_split_members
              (split_id, steam_id, display_name, percentage, is_seller, opted_out, added_at)
            VALUES (:sid, :steam, :dn, :pct, :isl, 0, :now)
        """), {
            "sid": split_id, "steam": m["steam_id"], "dn": m.get("display_name") or m["steam_id"],
            "pct": int(m["percentage"]), "isl": 1 if m.get("is_seller") else 0, "now": now,
        })

    new_json = json.dumps({"members": members}, default=str)
    _audit_split(db, split_id=split_id, action="CREATED" if not existing else "UPDATED",
                 actor=actor_steam_id, old_json=old_json, new_json=new_json,
                 ip_address=ip_address, now=now)
    db.commit()
    return get_active_split(db, tribe_owner_id) or {}


def member_optout(
    db: Session,
    *,
    split_id: int,
    steam_id: str,
    actor_steam_id: str,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Opt-out imediato de membro (R4). Recalcula percentuais proporcionalmente."""
    members = _get_split_members(db, split_id)
    target = next((m for m in members if m["steam_id"] == steam_id), None)
    if not target:
        raise ValueError("Membro não encontrado no split.")
    if target.get("is_seller"):
        raise ValueError("Vendedor não pode fazer opt-out sem desativar o split (use 'desativar').")
    if target.get("opted_out"):
        raise ValueError("Membro já realizou opt-out.")

    active_members = [m for m in members if not m.get("opted_out")]
    new_members = recalc_proportional(active_members, steam_id)

    now = _naive(_utcnow())
    # Marca opt-out
    db.execute(text("""
        UPDATE tribe_split_members SET opted_out = 1, opted_out_at = :now
        WHERE split_id = :sid AND steam_id = :steam
    """), {"now": now, "sid": split_id, "steam": steam_id})

    # Atualiza percentuais dos restantes
    for m in new_members:
        db.execute(text("""
            UPDATE tribe_split_members SET percentage = :pct
            WHERE split_id = :sid AND steam_id = :steam
        """), {"pct": m["percentage"], "sid": split_id, "steam": m["steam_id"]})

    _audit_split(db, split_id=split_id, action="OPTED_OUT", actor=actor_steam_id,
                 target=steam_id, old_json=None, new_json=json.dumps(new_members, default=str),
                 ip_address=ip_address, now=now)
    db.commit()
    return _get_split_members(db, split_id)  # type: ignore[return-value]


def disable_split(
    db: Session, *, tribe_owner_id: int, actor_steam_id: str, ip_address: str | None = None
) -> None:
    """Desativa o split imediatamente (R5). Sem cooldown."""
    now = _naive(_utcnow())
    db.execute(text("""
        UPDATE tribe_splits SET status = 'DISABLED', updated_at = :now, updated_by = :by
        WHERE tribe_owner_id = :oid AND status NOT IN ('DISABLED', 'ORPHANED')
    """), {"now": now, "by": actor_steam_id, "oid": tribe_owner_id})
    split = get_active_split(db, tribe_owner_id)
    if split:
        _audit_split(db, split_id=split["id"], action="DISABLED", actor=actor_steam_id,
                     old_json=None, new_json=None, ip_address=ip_address, now=now)
    db.commit()


def activate_pending_splits(db: Session) -> int:
    """Ativa splits que completaram o cooldown de 48h. Chamado periodicamente."""
    now = _naive(_utcnow())
    result = db.execute(text("""
        UPDATE tribe_splits SET status = 'ACTIVE', updated_at = :now
        WHERE status = 'PENDING_COOLDOWN' AND valid_from <= :now
    """), {"now": now})
    count = getattr(result, "rowcount", 0)
    if count:
        db.commit()
    return count


def _audit_split(
    db: Session, *, split_id: int, action: str, actor: str,
    target: str | None = None, old_json: str | None = None,
    new_json: str | None = None, ip_address: str | None = None, now: datetime
) -> None:
    db.execute(text("""
        INSERT INTO tribe_split_audit
          (split_id, action, actor_steam_id, target_steam_id, old_value_json, new_value_json, created_at, ip_address)
        VALUES (:sid, :act, :actor, :tgt, :old, :new, :now, :ip)
    """), {
        "sid": split_id, "act": action, "actor": actor, "tgt": target,
        "old": old_json, "new": new_json, "now": now, "ip": ip_address,
    })


# ────────────────────────────────────────────────────────────
# Payout do split na compra (integração com market_listings)
# ────────────────────────────────────────────────────────────

def get_split_snapshot_for_listing(
    db: Session, tribe_owner_id: int, price: int
) -> dict[str, Any] | None:
    """
    Retorna snapshot de split para um anúncio (opt-in por listagem).
    Verifica R8 (mínimo 1000 Âmbares) e se split está ACTIVE.
    Retorna None se split não aplicável.
    """
    if price < SPLIT_MIN_SALE_AMBER:
        return None
    split = get_active_split(db, tribe_owner_id)
    if not split or split["status"] != "ACTIVE":
        return None
    active_members = [m for m in split["members"] if not m.get("opted_out")]
    if len(active_members) < 2:
        return None
    return {
        "split_id": split["id"],
        "members": active_members,
    }


def apply_split_payout(
    db: Session,
    *,
    split_snapshot_json: str,
    price: int,
    seller_steam_id: str,
    listing_id: int,
    credit_fn: Any,  # Callable[[Session, str, int], int]
) -> list[dict[str, Any]]:
    """
    Distribui o preço de venda entre membros do split.
    Retorna lista de payouts realizados.
    Deve ser chamado DENTRO de purchase_listing, substituindo o _credit_points simples.
    """
    snapshot = json.loads(split_snapshot_json)
    members = snapshot.get("members", [])
    split_id = snapshot.get("split_id")

    active = [m for m in members if not m.get("opted_out")]
    if not active:
        # Fallback: 100% ao vendedor
        credit_fn(db, seller_steam_id, price)
        return [{"steam_id": seller_steam_id, "amount": price, "pct": 100, "leg": "seller_fallback"}]

    payouts: list[dict[str, Any]] = []
    total_paid = 0

    seller_member = next((m for m in active if m.get("is_seller")), None)
    non_sellers = [m for m in active if not m.get("is_seller")]

    for m in non_sellers:
        pct = int(m["percentage"])
        amount = math.floor(price * pct / 100)
        if amount > 0:
            credit_fn(db, m["steam_id"], amount)
            total_paid += amount
            payouts.append({
                "steam_id": m["steam_id"],
                "amount": amount,
                "pct": pct,
                "leg": "member",
                "split_id": split_id,
                "listing_id": listing_id,
            })

    # Vendedor recebe o restante (inclui remainder de arredondamento — R14 edge case 14)
    seller_amount = price - total_paid
    if seller_amount > 0 and seller_member:
        credit_fn(db, seller_member["steam_id"], seller_amount)
        payouts.append({
            "steam_id": seller_member["steam_id"],
            "amount": seller_amount,
            "pct": seller_member["percentage"],
            "leg": "seller",
            "split_id": split_id,
            "listing_id": listing_id,
        })

    return payouts


# ────────────────────────────────────────────────────────────
# Stub de log — TODO: integrar com asm_tribe_log.py / remote_agent
# ────────────────────────────────────────────────────────────

def get_tribe_log_stub(server_id: str, limit: int = 200) -> dict[str, Any]:
    """
    TODO: Integrar com remote_agent.py endpoint /server/{id}/tribelog
    e com src/asm_ui/asm_tribe_log.py para polling real.
    Por ora retorna stub com instruções para implementação futura.
    """
    return {
        "server_id": server_id,
        "status": "stub",
        "message": (
            "Log de tribo não disponível no MVP. "
            "Implementar remote_agent endpoint /server/{id}/tribelog "
            "e tribe_log_poller.py conforme PROJETO_AREA_TRIBO.md §5 Opção B."
        ),
        "lines": [],
    }
