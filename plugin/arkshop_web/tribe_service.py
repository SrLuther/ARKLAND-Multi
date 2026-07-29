"""Área de Tribo ARKLAND — lógica de negócio.

Implementa:
  - Esquema DB (tribe_owners, tribe_map_links, tribe_cluster_groups,
    tribe_members, tribe_presences, tribe_regulations,
    tribe_splits, tribe_split_members, tribe_split_audit,
    tribe_sync_requests, tribe_logs)
  - Gestão de membros, presença, regulamento e cluster (principal + fobs)
  - Fila pull de sync (Verificar de novo → plugin poll, sem depender de RCON)
  - Espelho do TribeLog por mapa (ingest + consulta com permissões)
  - Regras de split (R1–R14) — integração com market_listings via tribe_split_service

Padrão de integração (igual lottery_service):
  - ensure_tribe_schema(engine) — chamado em _migrate_schema do app.py
  - register_tribe_schema(engine) — idempotente
"""
from __future__ import annotations

import json
import hashlib
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
SPLIT_DEFAULT_SENDER_PCT = 60      # Default: quem envia
SPLIT_DEFAULT_POOL_PCT = 40        # Default: demais do pool (dividido por igual)
REGULAMENTO_MAX_CHARS = 5_000      # §19.4
REGULAMENTO_ADDENDUM_MAX_CHARS = 2_000
# Pedido «Verificar de novo»: plugin faz pull; RCON é só acelerador opcional.
TRIBE_SYNC_REQUEST_TTL_MINUTES = 15
TRIBE_SYNC_REQUEST_STATUSES = frozenset({
    "pending", "claimed", "done", "expired",
})

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
    if rank_implies_admin(member_rank):
        return False
    if _as_bool(is_owner):
        return True
    return rank_implies_owner(member_rank)


def resolve_member_is_owner(
    *,
    is_owner: Any = None,
    member_rank: str | None = None,
) -> bool:
    """Proprietário in-game para um membro da lista — Admin nunca é dono."""
    return resolve_is_owner(is_owner=is_owner, member_rank=member_rank)


def member_steam_key(*, steam_id: str | None = None, player_data_id: Any = None) -> str:
    """Chave estável para tribe_members — offline usa pdid:<id>."""
    sid = str(steam_id or "").strip()
    if sid:
        return sid
    pdid = player_data_id
    if pdid is not None and str(pdid).strip().isdigit() and int(pdid) > 0:
        return f"pdid:{int(pdid)}"
    return ""


def _normalize_rank_text(rank: str | None) -> str:
    if not rank:
        return ""
    r = str(rank).strip().lower()
    for a, b in (("á", "a"), ("ã", "a"), ("â", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        r = r.replace(a, b)
    return r


def rank_implies_admin(rank: str | None) -> bool:
    """True se o rank in-game é Admin (não Proprietário)."""
    r = _normalize_rank_text(rank)
    if not r:
        return False
    if rank_implies_owner(rank):
        return False
    return r == "admin" or r.startswith("admin ") or r.endswith(" admin")


def get_viewer_membership_snapshot(db: Session, steam_id: str) -> dict[str, Any]:
    """Última filiação conhecida do jogador (tribe_members → tribe_presences)."""
    steam_id = str(steam_id or "").strip()
    row = db.execute(
        text("""
            SELECT is_owner, rank_name, server_id, tribe_id, tribe_name, last_seen_at
            FROM tribe_members
            WHERE steam_id = :sid
            ORDER BY last_seen_at DESC
            LIMIT 1
        """),
        {"sid": steam_id},
    ).fetchone()
    if row:
        return {
            "is_game_owner": bool(row[0]),
            "rank_name": row[1] or "",
            "server_id": row[2],
            "tribe_id": row[3],
            "tribe_name": row[4] or "",
            "seen_at": str(row[5]) if row[5] else None,
            "source": "members",
        }
    row = db.execute(
        text("""
            SELECT is_owner, member_rank, server_id, tribe_id, tribe_name, captured_at
            FROM tribe_presences
            WHERE steam_id = :sid AND tribe_id IS NOT NULL
            ORDER BY captured_at DESC
            LIMIT 1
        """),
        {"sid": steam_id},
    ).fetchone()
    if row:
        return {
            "is_game_owner": resolve_is_owner(is_owner=row[0], member_rank=row[1]),
            "rank_name": row[1] or "",
            "server_id": row[2],
            "tribe_id": row[3],
            "tribe_name": row[4] or "",
            "seen_at": str(row[5]) if row[5] else None,
            "source": "presence",
        }
    return {
        "is_game_owner": False,
        "rank_name": "",
        "server_id": None,
        "tribe_id": None,
        "tribe_name": "",
        "seen_at": None,
        "source": None,
    }


def resolve_viewer_role(*, is_game_owner: bool, rank_name: str | None) -> str:
    """Papel do jogador na tribo: owner | admin | member."""
    if is_game_owner:
        return "owner"
    if rank_implies_admin(rank_name):
        return "admin"
    return "member"


def resolve_viewer_tribe_context(db: Session, steam_id: str, *, panel_activated: bool) -> dict[str, Any]:
    """Contexto de papel do visitante — separa painel web de proprietário in-game."""
    snap = get_viewer_membership_snapshot(db, steam_id)
    is_game_owner = bool(snap.get("is_game_owner"))
    member_rank = str(snap.get("rank_name") or "")
    viewer_role = resolve_viewer_role(is_game_owner=is_game_owner, rank_name=member_rank)

    can_manage = False
    if panel_activated:
        if is_game_owner:
            can_manage = True
        elif snap.get("source") is None:
            # Painel com mapas vinculados antes de haver snapshot de membro (backfill antigo).
            owner = get_owner(db, steam_id)
            if owner and get_map_links(db, owner["id"]):
                can_manage = True
                is_game_owner = True
                viewer_role = "owner"
        # Presença explícita como Admin bloqueia gestão mesmo com painel ativo.
        if rank_implies_admin(member_rank) and snap.get("source"):
            can_manage = False
            is_game_owner = False
            viewer_role = "admin"

    return {
        "is_game_owner": is_game_owner,
        "viewer_role": viewer_role,
        "member_rank": member_rank,
        "can_manage": can_manage,
        "membership": snap,
    }


def get_game_owner_member(
    db: Session, *, server_id: str, tribe_id: int
) -> dict[str, Any] | None:
    """Membro marcado como proprietário in-game num mapa/tribo."""
    row = db.execute(
        text("""
            SELECT steam_id, character_name, rank_name
            FROM tribe_members
            WHERE server_id = :svid AND tribe_id = :tid AND is_owner = 1
            ORDER BY last_seen_at DESC
            LIMIT 1
        """),
        {"svid": server_id, "tid": int(tribe_id)},
    ).fetchone()
    if row:
        return {
            "steam_id": row[0],
            "display_name": row[1] or row[0],
            "rank_name": row[2] or "",
        }
    row = db.execute(
        text("""
            SELECT steam_id, character_name, rank_name
            FROM tribe_members
            WHERE server_id = :svid AND tribe_id = :tid
              AND (
                LOWER(rank_name) LIKE '%propriet%'
                OR LOWER(rank_name) = 'owner'
              )
            ORDER BY last_seen_at DESC
            LIMIT 1
        """),
        {"svid": server_id, "tid": int(tribe_id)},
    ).fetchone()
    if not row:
        return None
    return {
        "steam_id": row[0],
        "display_name": row[1] or row[0],
        "rank_name": row[2] or "",
    }


def _collect_member_maps(db: Session, steam_id: str) -> list[dict[str, Any]]:
    """Mapas onde o jogador aparece como membro (sem painel de proprietário)."""
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
        game_owner = get_game_owner_member(db, server_id=key[0], tribe_id=key[1])
        maps_data.append({
            "server_id": key[0],
            "tribe_id": key[1],
            "tribe_name": r[2] or "",
            "tribe_name_local": r[2] or "",
            "tribe_type": "principal",
            "members": members,
            "member_count": len(members),
            "game_owner": game_owner,
        })
    return maps_data


def _game_owner_from_maps(maps_data: list[dict[str, Any]]) -> dict[str, Any] | None:
    for m in maps_data:
        go = m.get("game_owner")
        if go:
            return go
    return None


def _my_tribes_payload(
    db: Session,
    steam_id: str,
    *,
    panel_owner: dict[str, Any] | None,
    maps_data: list[dict[str, Any]],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    panel_activated = panel_owner is not None
    game_owner_info = _game_owner_from_maps(maps_data)
    payload: dict[str, Any] = {
        "is_owner": ctx["is_game_owner"],
        "can_manage": ctx["can_manage"],
        "panel_activated": panel_activated,
        "viewer_role": ctx["viewer_role"],
        "member_rank": ctx["member_rank"],
        "owner": panel_owner if ctx["is_game_owner"] else None,
        "game_owner": game_owner_info,
        "maps": maps_data,
        "_regulation": get_regulation(db, panel_owner["id"]) if panel_owner and ctx["can_manage"] else None,
        "_split": get_active_split(db, panel_owner["id"]) if panel_owner and ctx["can_manage"] else None,
    }
    return payload


def get_registered_owner_for_tribe(
    db: Session, *, server_id: str, tribe_id: int
) -> dict[str, Any] | None:
    """Proprietário já vinculado na web a este (server_id, tribe_id).

    Se existir, syncs posteriores de outros jogadores (mesmo como owner in-game)
    são tratados como membro — não sobrescrevem o dono.
    """
    server_id = str(server_id or "").strip()
    if not server_id or tribe_id is None:
        return None
    row = db.execute(
        text("""
            SELECT o.id, o.steam_id, o.display_name, l.id
            FROM tribe_map_links l
            JOIN tribe_owners o ON o.id = l.tribe_owner_id
            WHERE l.server_id = :sid AND l.tribe_id = :tid AND l.is_active = 1
            ORDER BY l.confirmed_at ASC
            LIMIT 1
        """),
        {"sid": server_id, "tid": int(tribe_id)},
    ).fetchone()
    if not row:
        return None
    return {
        "tribe_owner_id": int(row[0]),
        "steam_id": str(row[1]),
        "display_name": row[2] or "",
        "map_link_id": int(row[3]),
    }


def build_default_split_percentages(
    pool: list[dict[str, Any]],
    *,
    sender_steam_id: str,
    sender_pct: int = SPLIT_DEFAULT_SENDER_PCT,
) -> list[dict[str, Any]]:
    """Default 60/40: quem envia leva sender_pct; o resto divide por igual.

    ``pool`` = participantes do ganho partilhado (opt-in). Remainder de
    arredondamento vai ao remetente.
    """
    sender_steam_id = str(sender_steam_id or "").strip()
    if not sender_steam_id:
        raise ValueError("sender_steam_id obrigatório")
    if sender_pct < 1 or sender_pct > 99:
        raise ValueError("sender_pct deve estar entre 1 e 99")

    by_sid: dict[str, dict[str, Any]] = {}
    for m in pool:
        sid = str(m.get("steam_id") or "").strip()
        if sid:
            by_sid[sid] = m
    if sender_steam_id not in by_sid:
        raise ValueError("Remetente não está no pool de partilha.")

    others = [sid for sid in by_sid if sid != sender_steam_id]
    if not others:
        sender = by_sid[sender_steam_id]
        return [{
            "steam_id": sender_steam_id,
            "display_name": sender.get("display_name") or sender_steam_id,
            "percentage": 100,
            "is_seller": True,
            "opted_out": False,
        }]

    remainder = 100 - sender_pct
    each = remainder // len(others)
    rem = remainder - each * len(others)
    out: list[dict[str, Any]] = [{
        "steam_id": sender_steam_id,
        "display_name": by_sid[sender_steam_id].get("display_name") or sender_steam_id,
        "percentage": sender_pct + rem,
        "is_seller": True,
        "opted_out": False,
    }]
    for sid in others:
        out.append({
            "steam_id": sid,
            "display_name": by_sid[sid].get("display_name") or sid,
            "percentage": each,
            "is_seller": False,
            "opted_out": False,
        })
    return out


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
          player_data_id BIGINT,
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
        # ── Pedidos de sync (web → plugin pull; RCON opcional)
        f"""
        CREATE TABLE IF NOT EXISTS tribe_sync_requests (
          id                    {_pk},
          steam_id              VARCHAR(32) NOT NULL,
          status                VARCHAR(16) NOT NULL DEFAULT 'pending',
          requested_at          {_now_col} NOT NULL,
          expires_at            {_now_col} NOT NULL,
          claimed_at            {_now_col},
          claimed_by_server_id  VARCHAR(64),
          completed_at          {_now_col},
          last_error            TEXT
        )
        """,
        # ── Tribe Log espelhado por mapa (TribeLog.log / ingest plugin)
        f"""
        CREATE TABLE IF NOT EXISTS tribe_logs (
          id            {_pk},
          server_id     VARCHAR(64) NOT NULL,
          tribe_id      INTEGER,
          tribe_name    VARCHAR(128),
          steam_id      VARCHAR(32),
          day_number    INTEGER,
          event_time    VARCHAR(16),
          event_type    VARCHAR(32) NOT NULL DEFAULT 'other',
          raw_line      TEXT NOT NULL,
          file_offset   BIGINT NOT NULL DEFAULT 0,
          captured_at   {_now_col} NOT NULL,
          UNIQUE {"" if is_sqlite else "KEY uq_server_offset"} (server_id, file_offset)
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
        _add_col_if_missing(conn, is_sqlite, "tribe_members", "player_data_id", "BIGINT")
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_tribe_sync_req_steam_status "
                "ON tribe_sync_requests (steam_id, status)"
            ))
        except Exception as exc:
            log.debug("tribe_schema index tribe_sync_requests: %s", exc)
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_tribe_logs_server_captured "
                "ON tribe_logs (server_id, captured_at DESC)"
            ))
        except Exception as exc:
            log.debug("tribe_schema index tribe_logs: %s", exc)
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_tribe_logs_server_tribe "
                "ON tribe_logs (server_id, tribe_id)"
            ))
        except Exception as exc:
            log.debug("tribe_schema index tribe_logs tribe: %s", exc)
        conn.commit()
    log.info("tribe_schema: tabelas verificadas/criadas")
    try:
        from tribe_invite_service import ensure_invite_schema
        ensure_invite_schema(engine)
    except Exception as exc:
        log.warning("tribe_invite_schema: %s", exc)


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
    """Grava snapshot de presença e atualiza tribe_members.

    tribe_id <= 0 (saída de tribo neste mapa) → revoga membership web só neste mapa.
    """
    steam_id = str(steam_id or "").strip()
    server_id = str(server_id or "").strip()
    tribe_name_s = str(tribe_name or "").strip()
    member_rank_s = str(member_rank or "").strip() or None

    tid_int: int | None
    try:
        tid_int = int(tribe_id) if tribe_id is not None else None
    except (TypeError, ValueError):
        tid_int = None

    # Saída de tribo neste mapa — revoga só este server_id (outros mapas intactos).
    if tid_int is None or tid_int <= 0:
        try:
            from tribe_invite_service import revoke_membership_on_map
            revoke_membership_on_map(
                db,
                steam_id=steam_id,
                server_id=server_id,
                tribe_id=None,
                reason=str(source or "presence_leave"),
            )
        except Exception as exc:
            log.warning("tribe leave-revoke falhou: %s", exc)
        return

    owner_flag = resolve_is_owner(is_owner=is_owner, member_rank=member_rank_s)

    # Se a web já tem proprietário para esta tribo/mapa, não deixar outro jogador
    # reivindicar ownership (nem via map_link). Continua membro.
    registered = None
    if _is_usable_server_id(server_id):
        registered = get_registered_owner_for_tribe(
            db, server_id=server_id, tribe_id=tid_int,
        )
    claim_owner_link = owner_flag
    if registered and registered["steam_id"] != steam_id:
        claim_owner_link = False
        # Transferência: sync do novo Proprietário in-game (OwnerPlayerDataID)
        if owner_flag:
            try:
                from tribe_invite_service import handle_ownership_transfer
                handle_ownership_transfer(
                    db,
                    server_id=server_id,
                    tribe_id=tid_int,
                    new_owner_steam_id=steam_id,
                    old_owner_steam_id=registered["steam_id"],
                    tribe_name=tribe_name_s,
                )
            except Exception as exc:
                log.warning("tribe ownership transfer: %s", exc)
        owner_flag = False

    # Normaliza membros: is_owner via flag/rank in-game (não sobrescreve com dono web).
    normalized_members: list[dict[str, Any]] | None = None
    if members:
        normalized_members = []
        for m in members:
            mm = dict(m)
            mm["is_owner"] = resolve_member_is_owner(
                is_owner=mm.get("is_owner"),
                member_rank=mm.get("rank_name") or mm.get("member_rank"),
            )
            sid = member_steam_key(
                steam_id=mm.get("steam_id"),
                player_data_id=mm.get("player_data_id"),
            )
            if not sid:
                continue
            mm["steam_id"] = sid
            normalized_members.append(mm)

    now = _naive(_utcnow())
    db.execute(text("""
        INSERT INTO tribe_presences
          (steam_id, server_id, map_name, tribe_id, tribe_name, is_owner, member_rank, captured_at, source)
        VALUES (:sid, :svid, :mn, :tid, :tn, :iso, :mr, :now, :src)
    """), {
        "sid": steam_id, "svid": server_id, "mn": map_name or server_id,
        "tid": tid_int, "tn": tribe_name_s or None,
        "iso": 1 if owner_flag else 0,
        "mr": member_rank_s, "now": now, "src": source,
    })

    # Se enviou lista de membros, upsert em tribe_members
    if normalized_members and tid_int:
        _upsert_members(
            db, server_id=server_id, tribe_id=tid_int,
            tribe_name=tribe_name_s, members=normalized_members, now=now,
        )

    # Auto-vincula owner ao tribe_map_links (tribe_name opcional — nome vazio não bloqueia)
    if claim_owner_link and tid_int and _is_usable_server_id(server_id):
        owner = get_owner(db, steam_id)
        if owner:
            _auto_link_owner(
                db, owner=owner, server_id=server_id,
                tribe_id=tid_int,
                tribe_name=tribe_name_s or f"Tribo {tid_int}",
                now=now,
            )

    db.commit()


def _upsert_members(
    db: Session, *, server_id: str, tribe_id: int,
    tribe_name: str, members: list[dict[str, Any]], now: datetime
) -> None:
    """Upsert membros; garante um único is_owner=1 por tribo/mapa no snapshot."""
    owner_key: str | None = None
    for m in members:
        if m.get("is_owner"):
            owner_key = member_steam_key(
                steam_id=m.get("steam_id"),
                player_data_id=m.get("player_data_id"),
            ) or str(m.get("steam_id") or "").strip()
            if owner_key:
                break
    if owner_key:
        db.execute(
            text("""
                UPDATE tribe_members
                SET is_owner = 0, updated_at = :now
                WHERE server_id = :svid AND tribe_id = :tid AND steam_id != :owner_key
            """),
            {"svid": server_id, "tid": tribe_id, "owner_key": owner_key, "now": now},
        )

    for m in members:
        sid = member_steam_key(
            steam_id=m.get("steam_id"),
            player_data_id=m.get("player_data_id"),
        )
        if not sid:
            continue
        char_name = str(m.get("character_name") or "").strip()
        pdid = m.get("player_data_id")
        try:
            pdid_int = int(pdid) if pdid not in (None, "", 0, "0") else None
        except (TypeError, ValueError):
            pdid_int = None
        if pdid_int and not str(sid).startswith("pdid:"):
            pdid_key = member_steam_key(player_data_id=pdid_int)
            if pdid_key and pdid_key != sid:
                db.execute(
                    text("""
                        UPDATE tribe_members
                        SET steam_id = :sid, character_name = :cn, is_owner = :iso,
                            rank_name = :rn, last_seen_at = :now, updated_at = :now,
                            tribe_name = :tn, player_data_id = :pdid
                        WHERE server_id = :svid AND tribe_id = :tid AND steam_id = :pdid_key
                    """),
                    {
                        "sid": sid, "cn": char_name or None,
                        "iso": 1 if m.get("is_owner") else 0,
                        "rn": m.get("rank_name"), "now": now, "tn": tribe_name,
                        "pdid": pdid_int,
                        "svid": server_id, "tid": tribe_id, "pdid_key": pdid_key,
                    },
                )
        existing = db.execute(
            text("SELECT id FROM tribe_members WHERE server_id = :svid AND tribe_id = :tid AND steam_id = :sid"),
            {"svid": server_id, "tid": tribe_id, "sid": sid},
        ).fetchone()
        if existing:
            db.execute(text("""
                UPDATE tribe_members
                SET character_name = :cn, is_owner = :iso, rank_name = :rn,
                    last_seen_at = :now, updated_at = :now, tribe_name = :tn,
                    player_data_id = COALESCE(:pdid, player_data_id)
                WHERE server_id = :svid AND tribe_id = :tid AND steam_id = :sid
            """), {
                "cn": char_name or None, "iso": 1 if m.get("is_owner") else 0,
                "rn": m.get("rank_name"), "now": now, "tn": tribe_name,
                "pdid": pdid_int,
                "svid": server_id, "tid": tribe_id, "sid": sid,
            })
        else:
            db.execute(text("""
                INSERT INTO tribe_members
                  (server_id, tribe_id, tribe_name, steam_id, character_name, is_owner,
                   rank_name, player_data_id, joined_at, last_seen_at, updated_at)
                VALUES (:svid, :tid, :tn, :sid, :cn, :iso, :rn, :pdid, :now, :now, :now)
            """), {
                "svid": server_id, "tid": tribe_id, "tn": tribe_name, "sid": sid,
                "cn": char_name or None, "iso": 1 if m.get("is_owner") else 0,
                "rn": m.get("rank_name"), "pdid": pdid_int, "now": now,
            })


def _auto_link_owner(
    db: Session, *, owner: dict[str, Any], server_id: str,
    tribe_id: int, tribe_name: str, now: datetime
) -> None:
    """Vincula automaticamente owner à tribo detectada no login (se ainda não vinculado).

    Não sobrescreve se outro tribe_owner já tiver esta (server_id, tribe_id).
    """
    registered = get_registered_owner_for_tribe(db, server_id=server_id, tribe_id=tribe_id)
    if registered and registered["steam_id"] != owner["steam_id"]:
        log.info(
            "tribe auto-link skip: tribo %s@%s já tem dono web %s (sync=%s)",
            tribe_id, server_id, registered["steam_id"], owner["steam_id"],
        )
        return

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

# ────────────────────────────────────────────────────────────
# Fila pull de sync (Verificar de novo → plugin)
# ────────────────────────────────────────────────────────────

def _sync_request_row_to_dict(row: Any) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "id": int(row[0]),
        "steam_id": row[1],
        "status": row[2],
        "requested_at": str(row[3]) if row[3] else None,
        "expires_at": str(row[4]) if row[4] else None,
        "claimed_at": str(row[5]) if row[5] else None,
        "claimed_by_server_id": row[6] or None,
        "completed_at": str(row[7]) if row[7] else None,
        "last_error": row[8] or None,
    }


def expire_stale_tribe_sync_requests(db: Session) -> int:
    """Marca pedidos pending/claimed expirados."""
    now = _naive(_utcnow())
    result = db.execute(
        text("""
            UPDATE tribe_sync_requests
            SET status = 'expired'
            WHERE status IN ('pending', 'claimed') AND expires_at < :now
        """),
        {"now": now},
    )
    db.commit()
    return int(result.rowcount or 0)


def request_tribe_sync(db: Session, steam_id: str) -> dict[str, Any]:
    """Cria/renova pedido de sync para o jogador (pull pelo plugin).

    Idempotente: se já houver pending/claimed activo, renova expires_at.
    """
    steam_id = str(steam_id or "").strip()
    if not steam_id:
        raise ValueError("steam_id obrigatório")

    expire_stale_tribe_sync_requests(db)
    now = _naive(_utcnow())
    expires = now + timedelta(minutes=TRIBE_SYNC_REQUEST_TTL_MINUTES)

    existing = db.execute(
        text("""
            SELECT id, steam_id, status, requested_at, expires_at,
                   claimed_at, claimed_by_server_id, completed_at, last_error
            FROM tribe_sync_requests
            WHERE steam_id = :sid AND status IN ('pending', 'claimed')
            ORDER BY requested_at DESC
            LIMIT 1
        """),
        {"sid": steam_id},
    ).fetchone()

    if existing:
        db.execute(
            text("""
                UPDATE tribe_sync_requests
                SET status = 'pending',
                    requested_at = :now,
                    expires_at = :exp,
                    claimed_at = NULL,
                    claimed_by_server_id = NULL,
                    completed_at = NULL,
                    last_error = NULL
                WHERE id = :id
            """),
            {"now": now, "exp": expires, "id": int(existing[0])},
        )
        db.commit()
        row = db.execute(
            text("""
                SELECT id, steam_id, status, requested_at, expires_at,
                       claimed_at, claimed_by_server_id, completed_at, last_error
                FROM tribe_sync_requests WHERE id = :id
            """),
            {"id": int(existing[0])},
        ).fetchone()
        data = _sync_request_row_to_dict(row) or {}
        data["renewed"] = True
        return data

    db.execute(
        text("""
            INSERT INTO tribe_sync_requests
              (steam_id, status, requested_at, expires_at)
            VALUES (:sid, 'pending', :now, :exp)
        """),
        {"sid": steam_id, "now": now, "exp": expires},
    )
    db.commit()
    row = db.execute(
        text("""
            SELECT id, steam_id, status, requested_at, expires_at,
                   claimed_at, claimed_by_server_id, completed_at, last_error
            FROM tribe_sync_requests
            WHERE steam_id = :sid
            ORDER BY id DESC LIMIT 1
        """),
        {"sid": steam_id},
    ).fetchone()
    data = _sync_request_row_to_dict(row) or {}
    data["renewed"] = False
    return data


def claim_tribe_sync_requests(
    db: Session,
    steam_ids: list[str],
    *,
    server_id: str,
) -> list[dict[str, Any]]:
    """Plugin reclama pedidos pending para jogadores online neste mapa."""
    server_id = str(server_id or "").strip()
    ids = sorted({str(s or "").strip() for s in steam_ids if str(s or "").strip()})
    if not ids or not server_id:
        return []

    expire_stale_tribe_sync_requests(db)
    now = _naive(_utcnow())
    claimed: list[dict[str, Any]] = []

    for sid in ids:
        row = db.execute(
            text("""
                SELECT id, steam_id, status, requested_at, expires_at,
                       claimed_at, claimed_by_server_id, completed_at, last_error
                FROM tribe_sync_requests
                WHERE steam_id = :sid AND status = 'pending' AND expires_at >= :now
                ORDER BY requested_at ASC
                LIMIT 1
            """),
            {"sid": sid, "now": now},
        ).fetchone()
        if not row:
            continue
        req_id = int(row[0])
        db.execute(
            text("""
                UPDATE tribe_sync_requests
                SET status = 'claimed',
                    claimed_at = :now,
                    claimed_by_server_id = :srv
                WHERE id = :id AND status = 'pending'
            """),
            {"now": now, "srv": server_id[:64], "id": req_id},
        )
        claimed.append({
            "request_id": req_id,
            "steam_id": sid,
        })

    if claimed:
        db.commit()
    return claimed


def complete_tribe_sync_request(
    db: Session,
    request_id: int,
    *,
    ok: bool = True,
    error: str | None = None,
) -> dict[str, Any] | None:
    """Marca pedido como done (ou reabre pending se falhou e ainda não expirou)."""
    request_id = int(request_id)
    now = _naive(_utcnow())
    row = db.execute(
        text("""
            SELECT id, steam_id, status, requested_at, expires_at,
                   claimed_at, claimed_by_server_id, completed_at, last_error
            FROM tribe_sync_requests WHERE id = :id
        """),
        {"id": request_id},
    ).fetchone()
    if not row:
        return None

    if ok:
        db.execute(
            text("""
                UPDATE tribe_sync_requests
                SET status = 'done', completed_at = :now, last_error = NULL
                WHERE id = :id
            """),
            {"now": now, "id": request_id},
        )
    else:
        err = (error or "sync_failed")[:500]
        # Reabre para outro mapa / próximo poll se ainda válido.
        expires = row[4]
        still_valid = expires is not None and expires >= now
        if still_valid:
            db.execute(
                text("""
                    UPDATE tribe_sync_requests
                    SET status = 'pending',
                        claimed_at = NULL,
                        claimed_by_server_id = NULL,
                        last_error = :err
                    WHERE id = :id
                """),
                {"err": err, "id": request_id},
            )
        else:
            db.execute(
                text("""
                    UPDATE tribe_sync_requests
                    SET status = 'expired', last_error = :err
                    WHERE id = :id
                """),
                {"err": err, "id": request_id},
            )
    db.commit()
    refreshed = db.execute(
        text("""
            SELECT id, steam_id, status, requested_at, expires_at,
                   claimed_at, claimed_by_server_id, completed_at, last_error
            FROM tribe_sync_requests WHERE id = :id
        """),
        {"id": request_id},
    ).fetchone()
    return _sync_request_row_to_dict(refreshed)


def get_active_tribe_sync_request(db: Session, steam_id: str) -> dict[str, Any] | None:
    """Pedido pending/claimed activo (para UI / diagnóstico)."""
    steam_id = str(steam_id or "").strip()
    if not steam_id:
        return None
    expire_stale_tribe_sync_requests(db)
    now = _naive(_utcnow())
    row = db.execute(
        text("""
            SELECT id, steam_id, status, requested_at, expires_at,
                   claimed_at, claimed_by_server_id, completed_at, last_error
            FROM tribe_sync_requests
            WHERE steam_id = :sid AND status IN ('pending', 'claimed')
              AND expires_at >= :now
            ORDER BY requested_at DESC
            LIMIT 1
        """),
        {"sid": steam_id, "now": now},
    ).fetchone()
    return _sync_request_row_to_dict(row)


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

    Usado pelo botão «Verificar de novo» — não exige RCON;
    depende de snapshots enviados pelo plugin (poll pull / login / RCON opcional).
    """
    steam_id = str(steam_id or "").strip()
    owner = get_owner(db, steam_id)
    sync_req = get_active_tribe_sync_request(db, steam_id)
    if not owner:
        return {
            "panel_activated": False,
            "maps_linked": 0,
            "maps": [],
            "presences": get_presence_summary(db, steam_id),
            "sync_request": sync_req,
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
            if sync_req:
                hint = (
                    "Pedido de sync registado. O CustomShop (≥1.10.12) no mapa "
                    "puxa o pedido em ~15s e envia presença — sem depender de RCON. "
                    "Esteja online como Proprietário e clique de novo em alguns segundos."
                )
            else:
                hint = (
                    "Nenhuma presença in-game registada. Com o CustomShop ≥1.10.12 online, "
                    "clique em «Verificar de novo» estando logado como Proprietário — "
                    "cria um pedido que o plugin puxa sozinho. Confirme no log "
                    "«TribeSync: presence OK» e Settings/CrossChat.ServerId."
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
    ctx = resolve_viewer_tribe_context(db, steam_id, panel_activated=True)
    return {
        "panel_activated": True,
        "is_owner": ctx["is_game_owner"],
        "can_manage": ctx["can_manage"],
        "viewer_role": ctx["viewer_role"],
        "member_rank": ctx["member_rank"],
        "maps_linked": linked,
        "maps": tribes.get("maps") or [],
        "owner": tribes.get("owner"),
        "game_owner": tribes.get("game_owner"),
        "presences": presences,
        "sync_request": sync_req,
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

    ctx = resolve_viewer_tribe_context(db, steam_id, panel_activated=owner is not None)

    if not owner:
        maps_data = _collect_member_maps(db, steam_id)
        return _my_tribes_payload(db, steam_id, panel_owner=None, maps_data=maps_data, ctx=ctx)

    links = get_map_links(db, owner["id"])
    maps_data: list[dict[str, Any]] = []
    for link in links:
        members = get_members_by_map(db, server_id=link["server_id"], tribe_id=link["tribe_id"])
        game_owner = get_game_owner_member(
            db, server_id=link["server_id"], tribe_id=link["tribe_id"],
        )
        maps_data.append({
            **link,
            "members": members,
            "member_count": len(members),
            "game_owner": game_owner,
        })

    # Painel ativado por Admin (não proprietário) sem mapas vinculados — mostra visão de membro.
    if not maps_data and not ctx["is_game_owner"]:
        maps_data = _collect_member_maps(db, steam_id)

    return _my_tribes_payload(db, steam_id, panel_owner=owner, maps_data=maps_data, ctx=ctx)


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
    ctx = resolve_viewer_tribe_context(db, owner_steam_id, panel_activated=True)
    if not ctx["can_manage"]:
        raise ValueError(
            "Apenas o Proprietário in-game pode gerir membros (rank Admin não basta)."
        )

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
    try:
        from tribe_invite_service import confirm_group_member, get_group_for_owner
        group = get_group_for_owner(db, owner_steam_id)
        if group:
            confirm_group_member(
                db,
                cluster_group_id=group["id"],
                steam_id=member_steam_id,
                confirmed_via="sync",
                confirmed_by_steam_id=owner_steam_id,
                commit=False,
            )
    except Exception as exc:
        log.debug("manual_add confirm: %s", exc)
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
    Valida R1 (gap ≥ 10 p.p.) e R2 (soma = 100%) na tabela de taxas.
    Opt-in/opt-out individual não entra aqui — a tabela define o template.
    """
    if len(members) < 2:
        raise ValueError("Split exige ao menos 2 participantes na configuração.")
    if len(members) > SPLIT_MAX_MEMBERS:
        raise ValueError(f"Split permite no máximo {SPLIT_MAX_MEMBERS} membros.")

    total = sum(int(m["percentage"]) for m in members)
    if total != 100:
        raise ValueError(f"Soma dos percentuais deve ser exatamente 100% (atual: {total}%).")

    seller = next((m for m in members if m.get("is_seller")), None)
    if not seller:
        raise ValueError("Configuração deve ter um vendedor/lister marcado (parcela de quem envia).")

    pct_seller = int(seller["percentage"])
    others_pct = [int(m["percentage"]) for m in members if not m.get("is_seller")]
    max_other = max(others_pct) if others_pct else 0

    if pct_seller <= max_other:
        raise ValueError(
            "Quem envia deve ter percentual estritamente maior que qualquer outro membro."
        )
    gap = pct_seller - max_other
    if gap < SPLIT_GAP_MIN_PP:
        raise ValueError(
            f"Gap mínimo entre quem envia e o próximo membro é {SPLIT_GAP_MIN_PP} p.p. "
            f"(atual: {gap} p.p., remetente: {pct_seller}%, próximo: {max_other}%)."
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

    try:
        from tribe_invite_service import filter_confirmed_for_split
        members = filter_confirmed_for_split(
            db, tribe_owner_id=tribe_owner_id, members=members,
        )
    except Exception as exc:
        log.debug("split confirmed filter: %s", exc)

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
        # Preserva opt-in dos membros existentes ao regravar taxas
        prev_opt: dict[str, tuple[bool, Any]] = {
            m["steam_id"]: (bool(m.get("opted_out")), m.get("opted_out_at"))
            for m in existing.get("members") or []
        }
        db.execute(text("DELETE FROM tribe_split_members WHERE split_id = :sid"), {"sid": split_id})
    else:
        prev_opt = {}
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

    # Insere membros — novos começam fora do pool (opted_out=1) até aceitarem.
    # Membros que já tinham opt-in mantêm o estado.
    for m in members:
        sid = m["steam_id"]
        if sid in prev_opt:
            was_out, out_at = prev_opt[sid]
            opted_out = 1 if was_out else 0
            opted_out_at = out_at if was_out else None
        else:
            opted_out = 1
            opted_out_at = None
        db.execute(text("""
            INSERT INTO tribe_split_members
              (split_id, steam_id, display_name, percentage, is_seller, opted_out, opted_out_at, added_at)
            VALUES (:sid, :steam, :dn, :pct, :isl, :oo, :ooat, :now)
        """), {
            "sid": split_id, "steam": sid, "dn": m.get("display_name") or sid,
            "pct": int(m["percentage"]), "isl": 1 if m.get("is_seller") else 0,
            "oo": opted_out, "ooat": opted_out_at, "now": now,
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
    """Opt-out imediato: sai do pool — vendas próprias voltam a 100% (sem split).

    As taxas-template do owner mantêm-se; só a participação no pool muda.
    """
    members = _get_split_members(db, split_id)
    target = next((m for m in members if m["steam_id"] == steam_id), None)
    if not target:
        raise ValueError("Membro não encontrado no split.")
    if target.get("opted_out"):
        raise ValueError("Já está fora do ganho partilhado.")

    now = _naive(_utcnow())
    db.execute(text("""
        UPDATE tribe_split_members SET opted_out = 1, opted_out_at = :now
        WHERE split_id = :sid AND steam_id = :steam
    """), {"now": now, "sid": split_id, "steam": steam_id})

    _audit_split(db, split_id=split_id, action="OPTED_OUT", actor=actor_steam_id,
                 target=steam_id, old_json=None, new_json=json.dumps({"opted_out": steam_id}),
                 ip_address=ip_address, now=now)
    db.commit()
    return _get_split_members(db, split_id)  # type: ignore[return-value]


def member_optin(
    db: Session,
    *,
    split_id: int,
    steam_id: str,
    actor_steam_id: str,
    owner_approved: bool = False,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Aceita participar do ganho partilhado (opt-in por jogador).

    Reentrada após opt-out: exige 45h + aprovação do owner (D3/R4), salvo
    primeira adesão (nunca teve opted_out_at).
    """
    members = _get_split_members(db, split_id)
    target = next((m for m in members if m["steam_id"] == steam_id), None)
    if not target:
        raise ValueError("Membro não encontrado na configuração de divisão.")
    if not target.get("opted_out"):
        raise ValueError("Já participa do ganho partilhado.")

    now = _naive(_utcnow())
    # Reentrada: teve opted_out_at → carência 45h + aprovação owner
    if target.get("opted_out_at"):
        try:
            left_at = datetime.fromisoformat(str(target["opted_out_at"]).replace("Z", ""))
            if left_at.tzinfo is not None:
                left_at = _naive(left_at)
        except Exception:
            left_at = now
        elapsed = now - left_at
        if elapsed < timedelta(hours=SPLIT_REENTRY_HOURS):
            remaining = SPLIT_REENTRY_HOURS - int(elapsed.total_seconds() // 3600)
            raise ValueError(
                f"Reentrada só após {SPLIT_REENTRY_HOURS}h do opt-out "
                f"(faltam ~{max(remaining, 1)}h)."
            )
        if not owner_approved and actor_steam_id == steam_id:
            raise ValueError(
                "Reentrada requer aprovação explícita do proprietário da tribo."
            )

    db.execute(text("""
        UPDATE tribe_split_members SET opted_out = 0, opted_out_at = NULL
        WHERE split_id = :sid AND steam_id = :steam
    """), {"sid": split_id, "steam": steam_id})

    _audit_split(db, split_id=split_id, action="OPTED_IN", actor=actor_steam_id,
                 target=steam_id, old_json=None, new_json=json.dumps({"opted_in": steam_id}),
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
    db: Session,
    tribe_owner_id: int,
    price: int,
    *,
    seller_steam_id: str | None = None,
) -> dict[str, Any] | None:
    """
    Snapshot de split para um anúncio — opt-in por jogador.

    Só aplica se:
      - preço ≥ R8 (1000 Âmbares)
      - split ACTIVE
      - vendedor está no pool (não opted_out)
      - há pelo menos outro participante no pool

    Quem envia recebe a parcela de remetente (template is_seller / default 60%);
    os demais do pool partilham o resto (pesos do template ou iguais).
    """
    if price < SPLIT_MIN_SALE_AMBER:
        return None
    split = get_active_split(db, tribe_owner_id)
    if not split or split["status"] != "ACTIVE":
        return None

    seller_steam_id = str(seller_steam_id or "").strip()
    pool = [m for m in split["members"] if not m.get("opted_out")]
    if seller_steam_id:
        seller_in = next((m for m in pool if m["steam_id"] == seller_steam_id), None)
        if not seller_in:
            # Vendedor não aceitou partilha → 100% (sem snapshot)
            return None
        snapshot_members = _build_runtime_shares(pool, seller_steam_id=seller_steam_id)
    else:
        if len(pool) < 2:
            return None
        snapshot_members = pool

    if len([m for m in snapshot_members if not m.get("opted_out")]) < 2:
        return None
    return {
        "split_id": split["id"],
        "members": snapshot_members,
        "seller_steam_id": seller_steam_id or None,
        "rule": "sender_largest_share",
    }


def _build_runtime_shares(
    pool: list[dict[str, Any]], *, seller_steam_id: str
) -> list[dict[str, Any]]:
    """Monta % no momento da listagem: remetente = maior fatia; demais do pool."""
    template_sender = next((m for m in pool if m.get("is_seller")), None)
    sender_pct = (
        int(template_sender["percentage"])
        if template_sender
        else SPLIT_DEFAULT_SENDER_PCT
    )
    others = [m for m in pool if m["steam_id"] != seller_steam_id]
    if not others:
        return build_default_split_percentages(
            pool, sender_steam_id=seller_steam_id, sender_pct=sender_pct,
        )

    # Pesos customizados dos não-remetentes no template (exclui slot is_seller)
    weight_src = [m for m in pool if not m.get("is_seller") and m["steam_id"] != seller_steam_id]
    if not weight_src:
        # Remetente real era um "membro" no template — divide resto por igual
        return build_default_split_percentages(
            pool, sender_steam_id=seller_steam_id, sender_pct=sender_pct,
        )

    # Se todos os outros têm o mesmo peso (ou 1 membro), equal/default
    weights = [max(int(m["percentage"]), 1) for m in weight_src]
    if len(set(weights)) <= 1 and len(others) == len(weight_src):
        return build_default_split_percentages(
            pool, sender_steam_id=seller_steam_id, sender_pct=sender_pct,
        )

    # Escala pesos dos outros para somar (100 - sender_pct)
    remainder = 100 - sender_pct
    # Mapear peso por steam; quem não tinha peso no template fica peso médio
    weight_by_sid = {m["steam_id"]: max(int(m["percentage"]), 1) for m in weight_src}
    avg_w = max(sum(weights) // len(weights), 1)
    ordered_weights = [weight_by_sid.get(m["steam_id"], avg_w) for m in others]
    wsum = sum(ordered_weights) or 1
    out: list[dict[str, Any]] = []
    distributed = 0
    for i, m in enumerate(others):
        if i < len(others) - 1:
            pct = int(round(remainder * ordered_weights[i] / wsum))
            distributed += pct
        else:
            pct = remainder - distributed
        out.append({
            "steam_id": m["steam_id"],
            "display_name": m.get("display_name") or m["steam_id"],
            "percentage": pct,
            "is_seller": False,
            "opted_out": False,
        })
    seller = next(m for m in pool if m["steam_id"] == seller_steam_id)
    out.insert(0, {
        "steam_id": seller_steam_id,
        "display_name": seller.get("display_name") or seller_steam_id,
        "percentage": sender_pct,
        "is_seller": True,
        "opted_out": False,
    })
    # Corrige soma por arredondamento — remainder ao remetente
    total = sum(int(x["percentage"]) for x in out)
    if total != 100:
        out[0]["percentage"] = int(out[0]["percentage"]) + (100 - total)
    return out


def find_tribe_owner_id_for_seller(db: Session, seller_steam_id: str) -> int | None:
    """Resolve tribe_owner_id do split aplicável ao vendedor (membro de mapa com split)."""
    seller_steam_id = str(seller_steam_id or "").strip()
    if not seller_steam_id:
        return None
    # 1) Vendedor é o tribe_owner
    owner = get_owner(db, seller_steam_id)
    if owner:
        split = get_active_split(db, owner["id"])
        if split and split["status"] in ("ACTIVE", "PENDING_COOLDOWN"):
            return int(owner["id"])
    # 2) Vendedor é membro de tribo cujo dono tem split
    row = db.execute(
        text("""
            SELECT l.tribe_owner_id
            FROM tribe_members m
            JOIN tribe_map_links l
              ON l.server_id = m.server_id AND l.tribe_id = m.tribe_id AND l.is_active = 1
            JOIN tribe_splits s ON s.tribe_owner_id = l.tribe_owner_id
            WHERE m.steam_id = :sid
              AND s.status NOT IN ('DISABLED', 'ORPHANED')
            ORDER BY CASE s.status WHEN 'ACTIVE' THEN 0 ELSE 1 END, s.id DESC
            LIMIT 1
        """),
        {"sid": seller_steam_id},
    ).fetchone()
    return int(row[0]) if row else None


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
# Tribe Log espelhado por mapa
# ────────────────────────────────────────────────────────────

def _player_maps_for_log(db: Session, steam_id: str) -> list[dict[str, Any]]:
    """Mapas onde o jogador tem presença (owner links ou membership)."""
    data = get_my_tribes(db, steam_id, _skip_backfill=True)
    return list(data.get("maps") or [])


def resolve_log_access(
    db: Session,
    steam_id: str,
    server_id: str,
    *,
    is_admin: bool = False,
) -> dict[str, Any]:
    """Verifica se o jogador pode ver o log do mapa e devolve contexto.

    Raises PermissionError se não tiver acesso.
    """
    server_id = str(server_id or "").strip()
    if not server_id:
        raise ValueError("server_id obrigatório")

    if is_admin:
        return {
            "allowed": True,
            "role": "admin",
            "server_id": server_id,
            "tribe_id": None,
            "tribe_name": None,
            "log_visibility": "admin",
        }

    maps = _player_maps_for_log(db, steam_id)
    match = next((m for m in maps if str(m.get("server_id")) == server_id), None)
    if not match:
        raise PermissionError("Sem acesso ao log deste mapa")

    owner = get_owner(db, steam_id)
    # Owner do painel: vê todos os mapas vinculados
    if owner and any(
        str(m.get("server_id")) == server_id for m in get_map_links(db, owner["id"])
    ):
        return {
            "allowed": True,
            "role": "owner",
            "server_id": server_id,
            "tribe_id": match.get("tribe_id"),
            "tribe_name": match.get("tribe_name_local") or match.get("tribe_name"),
            "log_visibility": owner.get("log_visibility") or "members",
        }

    # Membro: respeita log_visibility do owner daquele mapa (se existir)
    tribe_id = int(match.get("tribe_id") or 0)
    link_owner_row = db.execute(
        text("""
            SELECT o.steam_id, o.log_visibility
            FROM tribe_map_links l
            JOIN tribe_owners o ON o.id = l.tribe_owner_id
            WHERE l.server_id = :sid AND l.tribe_id = :tid AND l.is_active = 1
            ORDER BY l.confirmed_at ASC LIMIT 1
        """),
        {"sid": server_id, "tid": tribe_id},
    ).fetchone()
    visibility = (link_owner_row[1] if link_owner_row else None) or "members"
    if visibility == "owner":
        raise PermissionError("Log visível apenas ao proprietário da tribo")
    if visibility == "public" or visibility == "members":
        return {
            "allowed": True,
            "role": "member",
            "server_id": server_id,
            "tribe_id": tribe_id or None,
            "tribe_name": match.get("tribe_name_local") or match.get("tribe_name"),
            "log_visibility": visibility,
        }
    raise PermissionError("Sem permissão para ver o log")


def ingest_tribe_log_lines(
    db: Session,
    *,
    server_id: str,
    lines: list[dict[str, Any]] | list[str],
    tribe_id: int | None = None,
    tribe_name: str | None = None,
    steam_id: str | None = None,
    source: str = "ingest",
) -> dict[str, Any]:
    """Insere linhas do TribeLog (dedup por server_id + file_offset).

    Aceita lista de strings ou dicts já parseados
    ({raw_line, file_offset, event_type, day_number, event_time, ...}).
    """
    from tribe_log_parser import parse_tribe_log_line

    server_id = str(server_id or "").strip()
    if not server_id:
        raise ValueError("server_id obrigatório")
    if not isinstance(lines, list) or not lines:
        return {"inserted": 0, "skipped": 0, "server_id": server_id, "source": source}

    now = _naive(_utcnow())
    inserted = 0
    skipped = 0
    tid = int(tribe_id) if tribe_id not in (None, "", 0, "0") else None
    tname = (tribe_name or "").strip() or None
    sid = (steam_id or "").strip() or None

    is_sqlite = False
    try:
        bind = db.get_bind()
        is_sqlite = bool(bind and bind.dialect and bind.dialect.name == "sqlite")
    except Exception:
        is_sqlite = False

    insert_sql = text(
        """
        INSERT OR IGNORE INTO tribe_logs
          (server_id, tribe_id, tribe_name, steam_id, day_number,
           event_time, event_type, raw_line, file_offset, captured_at)
        VALUES
          (:server_id, :tribe_id, :tribe_name, :steam_id, :day_number,
           :event_time, :event_type, :raw_line, :file_offset, :captured_at)
        """
        if is_sqlite
        else """
        INSERT IGNORE INTO tribe_logs
          (server_id, tribe_id, tribe_name, steam_id, day_number,
           event_time, event_type, raw_line, file_offset, captured_at)
        VALUES
          (:server_id, :tribe_id, :tribe_name, :steam_id, :day_number,
           :event_time, :event_type, :raw_line, :file_offset, :captured_at)
        """
    )

    for idx, item in enumerate(lines):
        tid_line = tid
        tname_line = tname
        sid_line = sid

        if isinstance(item, str):
            parsed = parse_tribe_log_line(item, file_offset=0)
            if not parsed:
                skipped += 1
                continue
            payload = parsed
        elif isinstance(item, dict):
            raw = str(item.get("raw_line") or item.get("line") or item.get("body") or "").strip()
            if not raw:
                skipped += 1
                continue
            if item.get("event_type") and (
                "day_number" in item or "event_time" in item or item.get("file_offset")
            ):
                payload = {
                    "day_number": item.get("day_number"),
                    "event_time": item.get("event_time"),
                    "event_type": str(item.get("event_type") or "other")[:32],
                    "raw_line": raw,
                    "file_offset": int(item.get("file_offset") or 0),
                }
            else:
                parsed = parse_tribe_log_line(
                    raw, file_offset=int(item.get("file_offset") or 0),
                )
                if not parsed:
                    skipped += 1
                    continue
                payload = parsed
            if item.get("tribe_id") not in (None, "", 0, "0"):
                try:
                    tid_line = int(item["tribe_id"])
                except (TypeError, ValueError):
                    tid_line = tid
            tname_line = (item.get("tribe_name") or tname or None)
            sid_line = (item.get("steam_id") or sid or None)
        else:
            skipped += 1
            continue

        offset = int(payload.get("file_offset") or 0)
        if offset <= 0:
            digest = hashlib.md5(
                f"{server_id}:{payload['raw_line']}".encode("utf-8", errors="replace")
            ).hexdigest()
            offset = -int(digest[:12], 16)
            if offset == 0:
                offset = -(idx + 1)

        result = db.execute(
            insert_sql,
            {
                "server_id": server_id,
                "tribe_id": tid_line,
                "tribe_name": tname_line,
                "steam_id": sid_line,
                "day_number": payload.get("day_number"),
                "event_time": (str(payload.get("event_time") or "")[:16] or None),
                "event_type": str(payload.get("event_type") or "other")[:32],
                "raw_line": payload["raw_line"],
                "file_offset": offset,
                "captured_at": now,
            },
        )
        if int(result.rowcount or 0) > 0:
            inserted += 1
            # Leave / removed → revoga membership web só neste mapa
            raw_line = str(payload.get("raw_line") or "")
            if payload.get("event_type") == "player" and (
                "removed from the Tribe" in raw_line
                or "left the Tribe" in raw_line
                or "Left the Tribe" in raw_line
            ):
                try:
                    from tribe_invite_service import (
                        parse_leave_character_name,
                        revoke_by_character_name,
                    )
                    cname = parse_leave_character_name(
                        str(payload.get("body") or raw_line),
                    )
                    if cname:
                        revoke_by_character_name(
                            db,
                            server_id=server_id,
                            character_name=cname,
                            tribe_id=tid_line,
                            reason="tribelog_removed",
                        )
                except Exception as exc:
                    log.debug("tribe log leave-revoke: %s", exc)
        else:
            skipped += 1

    db.commit()
    return {
        "inserted": inserted,
        "skipped": skipped,
        "server_id": server_id,
        "source": source,
        "tribe_id": tid,
    }


def get_max_file_offset(db: Session, server_id: str) -> int:
    """Maior file_offset positivo já ingerido para o mapa (para resume do tail)."""
    row = db.execute(
        text("""
            SELECT MAX(file_offset) FROM tribe_logs
            WHERE server_id = :sid AND file_offset > 0
        """),
        {"sid": server_id},
    ).fetchone()
    if not row or row[0] is None:
        return 0
    return int(row[0])


def get_tribe_log(
    db: Session,
    *,
    steam_id: str,
    server_id: str,
    limit: int = 200,
    event_type: str | None = None,
    tribe_id: int | None = None,
    is_admin: bool = False,
) -> dict[str, Any]:
    """Consulta log espelhado de um mapa com verificação de permissão."""
    access = resolve_log_access(db, steam_id, server_id, is_admin=is_admin)
    limit = max(1, min(int(limit or 200), 500))
    etype = (event_type or "").strip().lower() or None
    if etype in ("all", "todos", "*"):
        etype = None

    preferred_tid = tribe_id if tribe_id not in (None, "", 0, "0") else access.get("tribe_id")
    try:
        preferred_tid = int(preferred_tid) if preferred_tid not in (None, "") else None
    except (TypeError, ValueError):
        preferred_tid = None

    params: dict[str, Any] = {"sid": server_id, "lim": limit}
    where = ["server_id = :sid"]
    # Prefere linhas da tribo do jogador; inclui linhas sem tribe_id (arquivo global do mapa)
    if preferred_tid:
        where.append("(tribe_id IS NULL OR tribe_id = :tid)")
        params["tid"] = preferred_tid
    if etype:
        where.append("event_type = :etype")
        params["etype"] = etype

    sql = f"""
        SELECT id, server_id, tribe_id, tribe_name, steam_id,
               day_number, event_time, event_type, raw_line, file_offset, captured_at
        FROM tribe_logs
        WHERE {' AND '.join(where)}
        ORDER BY captured_at DESC, id DESC
        LIMIT :lim
    """
    rows = db.execute(text(sql), params).fetchall()
    lines = []
    for r in rows:
        lines.append({
            "id": r[0],
            "server_id": r[1],
            "tribe_id": r[2],
            "tribe_name": r[3],
            "steam_id": r[4],
            "day_number": r[5],
            "event_time": r[6],
            "event_type": r[7],
            "raw_line": r[8],
            "file_offset": r[9],
            "captured_at": str(r[10]) if r[10] else None,
        })
    # Cronológico crescente na UI
    lines.reverse()

    return {
        "server_id": server_id,
        "status": "ok",
        "access": {
            "role": access.get("role"),
            "log_visibility": access.get("log_visibility"),
            "tribe_id": access.get("tribe_id"),
            "tribe_name": access.get("tribe_name"),
        },
        "count": len(lines),
        "lines": lines,
        "filters": {"event_type": etype, "tribe_id": preferred_tid, "limit": limit},
    }


# Compat: nome antigo do stub
def get_tribe_log_stub(server_id: str, limit: int = 200) -> dict[str, Any]:
    """Deprecated — use get_tribe_log com sessão DB."""
    return {
        "server_id": server_id,
        "status": "stub",
        "message": "Use get_tribe_log(db, steam_id=..., server_id=...).",
        "lines": [],
        "limit": limit,
    }
