"""Sincroniza player_entitlements (arkland_shop) ↔ ark_permission.players (MySQL)."""
from __future__ import annotations

import logging
import re
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

log = logging.getLogger(__name__)

PERM_DB_NAME = "ark_permission"
SHOP_DB_NAME = "arkland_shop"
PAID_LICENSE_GROUPS = frozenset({
    "Delta",
    "Gamma",
    "Beta",
    "Alfa",
    "Omega",
    "Transcendente",
    "Etereo",
    "Universal",
    "Onipotente",
    "Surreal",
    "Imaterial",
    "Exotico",
})
TIMED_LICENSE_GROUPS = PAID_LICENSE_GROUPS | frozenset({"keyvault"})
STAFF_PERM_GROUPS = frozenset({"Moderacao", "Mod", "MOD", "STAFF", "Admins", "Admin"})
_MANAGED_SYNC_GROUPS = TIMED_LICENSE_GROUPS | STAFF_PERM_GROUPS
_STEAM_ID_RE = re.compile(r"^7656119\d{10}$")
_STAFF_ALIASES: dict[str, frozenset[str]] = {
    "Moderacao": frozenset({"Moderacao", "Mod", "MOD"}),
    "Mod": frozenset({"Moderacao", "Mod", "MOD"}),
    "MOD": frozenset({"Moderacao", "Mod", "MOD"}),
    "Admin": frozenset({"Admin", "Admins"}),
    "Admins": frozenset({"Admin", "Admins"}),
}
_RECONCILE_LOCK = threading.Lock()
_EXPIRY_TOLERANCE_SEC = 300


def _is_valid_steam_id(steam_id: str) -> bool:
    return bool(_STEAM_ID_RE.match(str(steam_id or "").strip()))


def _parse_shop_db_url(shop_url: str, perm_db: str = PERM_DB_NAME) -> str:
    raw = (shop_url or "").strip()
    if not raw:
        return ""
    normalized = raw.replace("mysql+pymysql://", "mysql://")
    parsed = urllib.parse.urlparse(normalized)
    if not parsed.hostname or not parsed.username:
        return ""
    user = urllib.parse.quote_plus(urllib.parse.unquote(parsed.username))
    password = urllib.parse.quote_plus(urllib.parse.unquote(parsed.password or ""))
    host = parsed.hostname
    port = parsed.port or 3306
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{perm_db}?charset=utf8mb4"


def _normalize_shop_db_url(shop_url: str) -> str:
    raw = (shop_url or "").strip()
    if not raw:
        return ""
    if "?" not in raw:
        return raw + "?charset=utf8mb4"
    return raw


def _perm_engine(shop_db_url: str) -> Engine | None:
    url = _parse_shop_db_url(shop_db_url)
    if not url:
        return None
    return create_engine(
        url,
        future=True,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5, "read_timeout": 12, "write_timeout": 12},
    )


def _shop_engine(shop_db_url: str) -> Engine | None:
    url = _normalize_shop_db_url(shop_db_url)
    if not url or "sqlite" in url.lower():
        return None
    normalized = url.replace("mysql+pymysql://", "mysql://")
    parsed = urllib.parse.urlparse(normalized)
    if not parsed.hostname or not parsed.username:
        return None
    return create_engine(
        url,
        future=True,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5, "read_timeout": 12, "write_timeout": 12},
    )


def _split_csv_groups(raw: str) -> list[str]:
    out: list[str] = []
    for part in str(raw or "").split(","):
        g = part.strip()
        if g and g not in out:
            out.append(g)
    return out


def _format_permission_groups(groups: list[str]) -> str:
    cleaned = [g for g in groups if g]
    if "Default" not in cleaned:
        cleaned.insert(0, "Default")
    return ",".join(cleaned) + "," if cleaned else "Default,"


def _parse_timed_groups(raw: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for part in str(raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        pieces = part.split(";")
        if len(pieces) < 3:
            continue
        try:
            expiry = int(pieces[1])
        except (TypeError, ValueError):
            continue
        group = pieces[2].strip()
        if group:
            out[group] = expiry
    return out


def _format_timed_groups(groups: dict[str, int]) -> str:
    if not groups:
        return ""
    parts = [f"0;{int(exp)};{grp}" for grp, exp in sorted(groups.items(), key=lambda x: x[0].lower())]
    return ",".join(parts) + ","


def _is_permanent_group(group: str, days: int) -> bool:
    g = str(group or "").strip()
    if g in STAFF_PERM_GROUPS:
        return True
    return int(days or 0) <= 0 and g not in TIMED_LICENSE_GROUPS


def _expiry_unix_from_days(days: int) -> int:
    d = max(1, int(days or 1))
    return int(time.time()) + d * 86400


def _expiry_unix_from_dt(value: Any) -> int:
    if value is None:
        return int(time.time()) + 3650 * 86400
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())
    except Exception:
        return int(time.time()) + 30 * 86400


def _staff_equivalent(a: str, b: str) -> bool:
    if a == b:
        return True
    variants = _STAFF_ALIASES.get(a)
    if variants and b in variants:
        return True
    variants = _STAFF_ALIASES.get(b)
    return bool(variants and a in variants)


def _staff_present(group: str, actual_groups: list[str]) -> bool:
    return any(_staff_equivalent(group, g) for g in actual_groups)


def _preserved_manual_groups(existing_perm: list[str]) -> list[str]:
    return [
        g for g in existing_perm
        if g != "Default" and g not in _MANAGED_SYNC_GROUPS
    ]


def _dedupe_groups(groups: list[str]) -> list[str]:
    out: list[str] = []
    for g in groups:
        if g and g not in out:
            out.append(g)
    return out


def _entitlement_row_to_dict(row: Any) -> dict[str, Any]:
    grp = str(row[1] if len(row) > 1 else row.get("group_name", ""))
    exp_raw = row[2] if len(row) > 2 else row.get("expires")
    permanent = exp_raw is None
    if exp_raw is not None and hasattr(exp_raw, "isoformat"):
        exp_iso = exp_raw.isoformat()
    elif exp_raw is not None:
        exp_iso = str(exp_raw)
    else:
        exp_iso = None
    return {
        "group": grp,
        "group_name": grp,
        "expires_at": exp_iso,
        "expires": exp_raw,
        "permanent": permanent,
    }


def _build_target_from_entitlements(entitlements: list[dict[str, Any]]) -> tuple[list[str], dict[str, int]]:
    perm_groups = ["Default"]
    timed_groups: dict[str, int] = {}

    for ent in entitlements or []:
        group = str(ent.get("group") or ent.get("group_name") or "").strip()
        if not group or group == "Default":
            continue
        permanent = bool(ent.get("permanent")) or ent.get("expires_at") is None and ent.get("expires") is None
        if group in STAFF_PERM_GROUPS or (permanent and group not in TIMED_LICENSE_GROUPS):
            if group not in perm_groups:
                perm_groups.append(group)
            timed_groups.pop(group, None)
            continue
        expiry_raw = ent.get("expires_at") or ent.get("expires")
        timed_groups[group] = _expiry_unix_from_dt(expiry_raw)

    for g in list(timed_groups):
        if g in PAID_LICENSE_GROUPS:
            for old in PAID_LICENSE_GROUPS:
                if old != g:
                    timed_groups.pop(old, None)

    return perm_groups, timed_groups


def _is_player_perm_irregular(
    entitlements: list[dict[str, Any]],
    perm_groups_raw: str,
    timed_groups_raw: str,
) -> bool:
    expected_perm, expected_timed = _build_target_from_entitlements(entitlements)
    actual_perm = _split_csv_groups(perm_groups_raw)
    actual_timed = _parse_timed_groups(timed_groups_raw)

    for g in expected_perm:
        if g == "Default":
            continue
        if g in STAFF_PERM_GROUPS:
            if not _staff_present(g, actual_perm):
                return True
        elif g not in actual_perm:
            return True

    for g, exp_unix in expected_timed.items():
        if g not in actual_timed:
            return True
        if abs(int(actual_timed[g]) - int(exp_unix)) > _EXPIRY_TOLERANCE_SEC:
            return True

    for g in actual_timed:
        if g in TIMED_LICENSE_GROUPS and g not in expected_timed:
            return True

    for g in actual_perm:
        if g in STAFF_PERM_GROUPS:
            if not any(
                _staff_equivalent(g, eg)
                for eg in expected_perm
                if eg != "Default"
            ):
                return True

    if entitlements:
        has_managed = any(
            str(e.get("group") or e.get("group_name") or "").strip() in _MANAGED_SYNC_GROUPS
            for e in entitlements
        )
        if has_managed and not actual_timed and all(g in ("Default",) for g in actual_perm):
            if expected_timed or any(g != "Default" for g in expected_perm):
                return True

    return False


def _ensure_player_row(conn: Any, steam_id: str) -> None:
    row = conn.execute(
        text("SELECT Id FROM players WHERE SteamId = :sid LIMIT 1"),
        {"sid": int(steam_id)},
    ).fetchone()
    if row:
        return
    conn.execute(
        text(
            "INSERT INTO players (SteamId, PermissionGroups, TimedPermissionGroups) "
            "VALUES (:sid, 'Default,', '')"
        ),
        {"sid": int(steam_id)},
    )


def _load_player_perm_fields(conn: Any, steam_id: str) -> tuple[str, str]:
    row = conn.execute(
        text(
            "SELECT PermissionGroups, TimedPermissionGroups FROM players "
            "WHERE SteamId = :sid LIMIT 1"
        ),
        {"sid": int(steam_id)},
    ).fetchone()
    if not row:
        return "Default,", ""
    return str(row[0] or "Default,"), str(row[1] or "")


def grant_group_in_permission_db(
    shop_db_url: str,
    steam_id: str,
    group: str,
    *,
    days: int = 30,
) -> dict[str, Any]:
    steam_id = str(steam_id or "").strip()
    group = str(group or "").strip()
    if not _is_valid_steam_id(steam_id):
        return {"ok": False, "error": "SteamID64 inválido"}
    if not group:
        return {"ok": False, "error": "Grupo vazio"}

    engine = _perm_engine(shop_db_url)
    if engine is None:
        return {"ok": False, "error": "URL do banco da loja indisponível"}

    try:
        with engine.begin() as conn:
            _ensure_player_row(conn, steam_id)
            perm_groups_raw, timed_raw = _load_player_perm_fields(conn, steam_id)
            perm_groups = _split_csv_groups(perm_groups_raw)
            timed_groups = _parse_timed_groups(timed_raw)

            if group in PAID_LICENSE_GROUPS:
                for old in PAID_LICENSE_GROUPS:
                    if old != group:
                        timed_groups.pop(old, None)
                        if old in perm_groups:
                            perm_groups.remove(old)

            if _is_permanent_group(group, days):
                if group not in perm_groups:
                    perm_groups.append(group)
            else:
                timed_groups[group] = _expiry_unix_from_days(days)
                if group in perm_groups and group != "Default":
                    perm_groups.remove(group)

            conn.execute(
                text(
                    "UPDATE players SET PermissionGroups = :pg, TimedPermissionGroups = :tpg "
                    "WHERE SteamId = :sid"
                ),
                {
                    "sid": int(steam_id),
                    "pg": _format_permission_groups(perm_groups),
                    "tpg": _format_timed_groups(timed_groups),
                },
            )
        return {"ok": True, "steam_id": steam_id, "group": group, "days": int(days)}
    except Exception as exc:
        log.warning("grant_group_in_permission_db %s %s: %s", steam_id, group, exc)
        return {"ok": False, "error": str(exc)}
    finally:
        engine.dispose()


def revoke_group_in_permission_db(
    shop_db_url: str,
    steam_id: str,
    group: str,
) -> dict[str, Any]:
    steam_id = str(steam_id or "").strip()
    group = str(group or "").strip()
    if not _is_valid_steam_id(steam_id):
        return {"ok": False, "error": "SteamID64 inválido"}
    if not group:
        return {"ok": False, "error": "Grupo vazio"}

    engine = _perm_engine(shop_db_url)
    if engine is None:
        return {"ok": False, "error": "URL do banco da loja indisponível"}

    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT PermissionGroups, TimedPermissionGroups FROM players "
                    "WHERE SteamId = :sid LIMIT 1"
                ),
                {"sid": int(steam_id)},
            ).fetchone()
            if not row:
                return {"ok": True, "steam_id": steam_id, "group": group, "note": "jogador ausente"}
            perm_groups = _split_csv_groups(str(row[0] or ""))
            timed_groups = _parse_timed_groups(str(row[1] or ""))
            if group in perm_groups and group != "Default":
                perm_groups.remove(group)
            timed_groups.pop(group, None)
            for g in list(perm_groups):
                if g in STAFF_PERM_GROUPS and _staff_equivalent(g, group):
                    perm_groups.remove(g)
            for g in list(timed_groups):
                if _staff_equivalent(g, group):
                    timed_groups.pop(g, None)
            conn.execute(
                text(
                    "UPDATE players SET PermissionGroups = :pg, TimedPermissionGroups = :tpg "
                    "WHERE SteamId = :sid"
                ),
                {
                    "sid": int(steam_id),
                    "pg": _format_permission_groups(perm_groups),
                    "tpg": _format_timed_groups(timed_groups),
                },
            )
        return {"ok": True, "steam_id": steam_id, "group": group}
    except Exception as exc:
        log.warning("revoke_group_in_permission_db %s %s: %s", steam_id, group, exc)
        return {"ok": False, "error": str(exc)}
    finally:
        engine.dispose()


def sync_entitlements_to_permission_db(
    shop_db_url: str,
    steam_id: str,
    entitlements: list[dict[str, Any]],
) -> dict[str, Any]:
    """Espelha entitlements em ark_permission, preservando grupos manuais não gerenciados pela web."""
    steam_id = str(steam_id or "").strip()
    if not _is_valid_steam_id(steam_id):
        return {"ok": False, "error": "SteamID64 inválido"}

    engine = _perm_engine(shop_db_url)
    if engine is None:
        return {"ok": False, "error": "URL do banco da loja indisponível"}

    target_perm, target_timed = _build_target_from_entitlements(entitlements)

    try:
        with engine.begin() as conn:
            _ensure_player_row(conn, steam_id)
            existing_pg, _existing_tpg = _load_player_perm_fields(conn, steam_id)
            preserved = _preserved_manual_groups(_split_csv_groups(existing_pg))
            final_perm = _dedupe_groups(
                ["Default"] + preserved + [g for g in target_perm if g != "Default"]
            )
            conn.execute(
                text(
                    "UPDATE players SET PermissionGroups = :pg, TimedPermissionGroups = :tpg "
                    "WHERE SteamId = :sid"
                ),
                {
                    "sid": int(steam_id),
                    "pg": _format_permission_groups(final_perm),
                    "tpg": _format_timed_groups(target_timed),
                },
            )
        return {
            "ok": True,
            "steam_id": steam_id,
            "permission_groups": final_perm,
            "timed_groups": list(target_timed.keys()),
            "preserved_manual": preserved,
        }
    except Exception as exc:
        log.warning("sync_entitlements_to_permission_db %s: %s", steam_id, exc)
        return {"ok": False, "error": str(exc)}
    finally:
        engine.dispose()


def _fetch_active_entitlements_by_steam(shop_engine: Engine) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    with shop_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT steam_id, group_name, expires FROM player_entitlements "
                "WHERE expires IS NULL OR expires > NOW()"
            ),
        ).fetchall()
    for row in rows:
        sid = str(row[0]).strip()
        if not _is_valid_steam_id(sid):
            continue
        out.setdefault(sid, []).append(_entitlement_row_to_dict(row))
    return out


def _fetch_permission_players(perm_engine: Engine) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    with perm_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT SteamId, PermissionGroups, TimedPermissionGroups FROM players"),
        ).fetchall()
    for row in rows:
        sid = str(row[0]).strip()
        if not _is_valid_steam_id(sid):
            continue
        out[sid] = (str(row[1] or "Default,"), str(row[2] or ""))
    return out


def _player_has_managed_permission_only(perm_pg: str, perm_tpg: str) -> bool:
    actual_perm = _split_csv_groups(perm_pg)
    actual_timed = _parse_timed_groups(perm_tpg)
    if any(g in TIMED_LICENSE_GROUPS for g in actual_timed):
        return True
    return any(g in STAFF_PERM_GROUPS for g in actual_perm)


def reconcile_entitlements_with_permission_db(
    shop_db_url: str,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Compara player_entitlements com ark_permission.players e corrige divergências."""
    shop_url = _normalize_shop_db_url(shop_db_url)
    if not shop_url or "sqlite" in shop_url.lower():
        return {"ok": False, "error": "Banco MySQL da loja não configurado"}

    shop_eng = _shop_engine(shop_url)
    perm_eng = _perm_engine(shop_url)
    if shop_eng is None or perm_eng is None:
        return {"ok": False, "error": "URL do banco indisponível"}

    with _RECONCILE_LOCK:
        try:
            ent_by_steam = _fetch_active_entitlements_by_steam(shop_eng)
            perm_by_steam = _fetch_permission_players(perm_eng)

            all_ids: set[str] = set(ent_by_steam) | set(perm_by_steam)
            irregular: list[str] = []
            synced: list[str] = []
            errors: list[dict[str, str]] = []

            for steam_id in sorted(all_ids):
                ents = ent_by_steam.get(steam_id, [])
                perm_row = perm_by_steam.get(steam_id)

                is_irregular = False
                if perm_row is None:
                    is_irregular = bool(ents)
                else:
                    is_irregular = _is_player_perm_irregular(ents, perm_row[0], perm_row[1])
                    if not ents and _player_has_managed_permission_only(perm_row[0], perm_row[1]):
                        is_irregular = True

                if not is_irregular:
                    continue

                irregular.append(steam_id)
                if dry_run:
                    continue

                res = sync_entitlements_to_permission_db(shop_url, steam_id, ents)
                if res.get("ok"):
                    synced.append(steam_id)
                else:
                    errors.append({"steam_id": steam_id, "error": str(res.get("error") or "falha")})

            return {
                "ok": True,
                "dry_run": dry_run,
                "checked": len(all_ids),
                "irregular": len(irregular),
                "synced": len(synced),
                "errors": errors,
                "steam_ids": irregular[:100],
            }
        except Exception as exc:
            log.warning("reconcile_entitlements_with_permission_db: %s", exc)
            return {"ok": False, "error": str(exc)}
        finally:
            shop_eng.dispose()
            perm_eng.dispose()
