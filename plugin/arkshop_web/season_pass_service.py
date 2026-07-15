"""Season Pass — motor: calendário, XP, Premium, claims/grants."""
from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

import season_pass_config as spcfg

log = logging.getLogger("arkshop_web.season_pass")

MAX_XP = 4875
_STATUSES = ("inactive", "active", "claim_window", "ended")

_TIER_RANK = {
    "Delta": 1,
    "Gamma": 2,
    "Beta": 3,
    "Alfa": 4,
    "Omega": 5,
    "Transcendente": 6,
    "Etereo": 7,
    "Universal": 8,
    "Onipotente": 9,
    "Surreal": 10,
    "Imaterial": 11,
    "Exotico": 12,
}
_PAID_LICENSE_GROUPS = frozenset(_TIER_RANK.keys())
MAX_ACTIVE_PAID_LICENSE_TIERS = 2

_cbs: dict[str, Any] = {}


def configure_engine(**kwargs: Any) -> None:
    """Injeta callbacks da app (pontos, pedidos, entitlements, ARKBANK)."""
    _cbs.update(kwargs)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _naive_utc(dt: datetime | str | None = None) -> datetime:
    if dt is None:
        dt = _utcnow()
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return _naive_utc(_utcnow())
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _parse_iso(raw: Any) -> datetime | None:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return _naive_utc(raw)
    try:
        return _naive_utc(str(raw))
    except Exception:
        return None


def ensure_season_pass_schema(engine: Engine) -> None:
    is_sqlite = "sqlite" in str(engine.url).lower()
    if is_sqlite:
        progress_ddl = """
        CREATE TABLE IF NOT EXISTS season_pass_progress (
          steam_id VARCHAR(32) NOT NULL,
          season_id VARCHAR(64) NOT NULL,
          xp INTEGER NOT NULL DEFAULT 0,
          premium INTEGER NOT NULL DEFAULT 0,
          claimed_json TEXT NOT NULL DEFAULT '[]',
          updated_at DATETIME NOT NULL,
          PRIMARY KEY (steam_id, season_id)
        )
        """
        xp_ddl = """
        CREATE TABLE IF NOT EXISTS season_pass_xp_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at DATETIME NOT NULL,
          steam_id VARCHAR(32) NOT NULL,
          season_id VARCHAR(64) NOT NULL,
          amount INTEGER NOT NULL,
          map_id VARCHAR(64) NOT NULL,
          cycle_key VARCHAR(64) NOT NULL,
          UNIQUE (steam_id, season_id, map_id, cycle_key, amount)
        )
        """
    else:
        progress_ddl = """
        CREATE TABLE IF NOT EXISTS season_pass_progress (
          steam_id VARCHAR(32) NOT NULL,
          season_id VARCHAR(64) NOT NULL,
          xp INT NOT NULL DEFAULT 0,
          premium TINYINT(1) NOT NULL DEFAULT 0,
          claimed_json TEXT NOT NULL,
          updated_at DATETIME(3) NOT NULL,
          PRIMARY KEY (steam_id, season_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        xp_ddl = """
        CREATE TABLE IF NOT EXISTS season_pass_xp_events (
          id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
          created_at DATETIME(3) NOT NULL,
          steam_id VARCHAR(32) NOT NULL,
          season_id VARCHAR(64) NOT NULL,
          amount INT NOT NULL,
          map_id VARCHAR(64) NOT NULL,
          cycle_key VARCHAR(64) NOT NULL,
          UNIQUE KEY uq_sp_xp (steam_id, season_id, map_id, cycle_key, amount)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    with engine.begin() as conn:
        conn.execute(text(progress_ddl))
        conn.execute(text(xp_ddl))


def compute_status(cfg: dict[str, Any], *, now: datetime | None = None) -> str:
    starts = _parse_iso(cfg.get("starts_at"))
    ends = _parse_iso(cfg.get("ends_at"))
    if not starts or not ends or not cfg.get("season_id"):
        return "inactive"
    n = _naive_utc(now)
    if n <= ends:
        return "active"
    return "claim_window"


def days_remaining(cfg: dict[str, Any], *, now: datetime | None = None) -> int | None:
    ends = _parse_iso(cfg.get("ends_at"))
    if not ends:
        return None
    n = _naive_utc(now)
    secs = (ends - n).total_seconds()
    if secs <= 0:
        return 0
    return max(1, int(math.ceil(secs / 86400.0)))


def status_label(status: str) -> str:
    return {
        "inactive": "Não iniciada",
        "active": "Ativa",
        "claim_window": "Janela de resgate",
        "ended": "Encerrada",
    }.get(status, status)


def refresh_calendar_fields(cfg: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Devolve cfg com status/days_remaining computados (não grava)."""
    out = dict(cfg)
    st = compute_status(out, now=now)
    out["status"] = st
    out["days_remaining"] = days_remaining(out, now=now)
    return out


def season_public(cfg: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    c = refresh_calendar_fields(cfg, now=now)
    tier = str(c.get("current_tier") or "Delta")
    dur = int(c.get("duration_days") or 30)
    st = str(c.get("status") or "inactive")
    price = spcfg.premium_price(c, tier)
    left = c.get("days_remaining")
    note_parts = []
    if st == "inactive":
        note_parts.append(
            "Season ainda não foi iniciada pela administração. "
            "XP, Premium e resgates ficam indisponíveis até ao start."
        )
    elif st == "active":
        note_parts.append(
            f"Season Pass — {tier}: {dur} dias fixos; fim automático. "
            "Próxima season só quando admin iniciar."
        )
    elif st == "claim_window":
        note_parts.append(
            "Season encerrada (relógio). Ainda podes resgatar recompensas "
            "até a administração iniciar a próxima season."
        )
    return {
        "id": str(c.get("season_id") or ""),
        "tier": tier,
        "name": f"Season Pass — {tier}",
        "title": f"Season Pass — {tier}",
        "status": st,
        "status_label": status_label(st),
        "duration_days": dur,
        "days_remaining": left,
        "starts_at": c.get("starts_at"),
        "ends_at": c.get("ends_at"),
        "tier_sequence": list(c.get("tier_sequence") or []),
        "premium_price_amber": price,
        "note": " ".join(note_parts),
    }


def _latch_meta_reached(cfg: dict[str, Any], *, progress: int, now: datetime | None = None) -> dict[str, Any]:
    """Se progresso >= target e ainda não latched, grava meta_reached na config."""
    target = int(cfg.get("meta_target_amber") or 0)
    if target <= 0 or progress < target:
        return cfg
    if bool(cfg.get("meta_reached")) and cfg.get("meta_reached_at"):
        return cfg
    n = now or _utcnow()
    patched = {
        **cfg,
        "meta_reached": True,
        "meta_reached_at": spcfg._iso(n if n.tzinfo else n.replace(tzinfo=timezone.utc)),
    }
    try:
        return spcfg.save_config(patched, preserve_calendar=True)
    except Exception as exc:
        log.warning("meta_reached latch failed: %s", exc)
        return patched


def collective_meta_public(
    cfg: dict[str, Any],
    db: Session | None = None,
    *,
    now: datetime | None = None,
    latch: bool = True,
) -> dict[str, Any]:
    """Meta colectiva do cofre — progresso ≠ Pass XP e ≠ saldo ARKBANK.

    Progresso = Σ INFLOW_TYPES desde ``starts_at`` da season (SPEC §15.8).
    ``admin_adjust`` e outflows (TimedPoints) não contam.
    Ao atingir o target: flag ``meta_reached``; evento é agenda admin (não auto-fire).
    """
    c = refresh_calendar_fields(cfg, now=now)
    target = int(c.get("meta_target_amber") or 0)
    starts = _parse_iso(c.get("starts_at"))
    st = str(c.get("status") or "inactive")
    enabled = target > 0
    progress = 0
    by_type: dict[str, Any] = {}
    balance: int | None = None
    inflow_meta: dict[str, Any] = {}

    if enabled and starts is not None and db is not None:
        try:
            from arkbank_service import get_balance, season_meta_inflow

            inflow_meta = season_meta_inflow(db, since=starts, until=None)
            progress = int(inflow_meta.get("progress") or 0)
            by_type = dict(inflow_meta.get("by_type") or {})
            balance = int(get_balance(db))
        except Exception as exc:
            log.warning("collective_meta inflow query failed: %s", exc)

    pct = 0
    if enabled and target > 0:
        pct = max(0, min(100, int(round(100.0 * progress / target))))

    reached = bool(c.get("meta_reached"))
    if enabled and progress >= target:
        reached = True
        if latch and not bool(c.get("meta_reached")):
            c = _latch_meta_reached(c, progress=progress, now=now)
            reached = True

    event_at = c.get("meta_event_at")
    event_notes = str(c.get("meta_event_notes") or "")
    reached_at = c.get("meta_reached_at")

    status_meta = "disabled"
    if not enabled:
        status_meta = "disabled"
    elif st == "inactive":
        status_meta = "awaiting_season"
    elif reached:
        status_meta = "event_scheduled" if event_at else "reached_pending_schedule"
    else:
        status_meta = "in_progress"

    return {
        "enabled": enabled,
        "target_amber": target,
        "progress_amber": progress,
        "percent": pct,
        "meta_reached": reached,
        "meta_reached_at": reached_at,
        "event_at": event_at,
        "event_notes": event_notes,
        "event_auto_fire": False,
        "status": status_meta,
        "definition": {
            "metric": "arkbank_season_inflow",
            "vs_vault_balance": (
                "Progresso = Σ inflows (catálogo, market, dino order, doação BRL, Premium) "
                "desde o início da season. Não é o saldo actual do cofre (esse inclui "
                "outflows TimedPoints e pode ser negativo)."
            ),
            "vs_pass_xp": "Meta colectiva ≠ XP individual do Season Pass.",
            "included_types": list(inflow_meta.get("included_types") or []),
            "excludes": ["admin_adjust", "timed_reward", "clawbacks"],
            "on_reach": (
                "Quando atingida: flag meta_reached. Admin agenda a data do evento — "
                "não dispara automaticamente. Relógio da season continua 30 dias."
            ),
        },
        "by_type": by_type,
        "vault_balance": balance,
        "label": "Cofre da temporada",
        "season_starts_at": c.get("starts_at"),
    }


def _next_tier(cfg: dict[str, Any]) -> str:
    seq = list(cfg.get("tier_sequence") or spcfg._SEASON_TIERS)
    cur = str(cfg.get("current_tier") or "Delta")
    try:
        idx = seq.index(cur)
        if idx + 1 < len(seq):
            return seq[idx + 1]
    except ValueError:
        pass
    return seq[0] if seq else "Delta"


def start_season(
    *,
    advance_tier: bool = False,
    updated_by_steam_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Inicia season (primeira) ou próxima (fecha claims da anterior)."""
    with spcfg._lock:
        cfg = spcfg.load_config()
        st = compute_status(cfg, now=now)
        n = _naive_utc(now)
        if advance_tier:
            if st == "inactive" and not cfg.get("season_id"):
                raise ValueError(
                    "Nenhuma season anterior — use «Iniciar season» primeiro."
                )
            tier = _next_tier(cfg)
        else:
            if st == "active":
                raise ValueError("Já existe uma season activa.")
            if st == "claim_window":
                raise ValueError(
                    "Season em janela de resgate — use «Iniciar próxima season»."
                )
            tier = str(cfg.get("current_tier") or "Delta")

        dur = int(cfg.get("duration_days") or 30)
        ends = n + timedelta(days=dur)
        season_id = f"season-{tier.lower()}-{n.strftime('%Y%m%d%H%M%S')}"
        # Nova season: reset latch/agenda da meta (target pode ficar; admin ajusta se quiser)
        raw = {
            **cfg,
            "current_tier": tier,
            "season_id": season_id,
            "starts_at": spcfg._iso(n.replace(tzinfo=timezone.utc)),
            "ends_at": spcfg._iso(ends.replace(tzinfo=timezone.utc)),
            "meta_reached": False,
            "meta_reached_at": None,
            "meta_event_at": None,
            "meta_event_notes": "",
        }
        saved = spcfg.save_config(raw, updated_by_steam_id=updated_by_steam_id)
        return refresh_calendar_fields(saved, now=n)


def claimed_key(track: str, level: int) -> str:
    return f"{track}:{int(level)}"


def _parse_claimed(raw: Any) -> set[str]:
    if isinstance(raw, list):
        return {str(x) for x in raw}
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return {str(x) for x in data}
        except json.JSONDecodeError:
            pass
    return set()


def get_progress(db: Session, steam_id: str, season_id: str) -> dict[str, Any]:
    if not season_id:
        return {"steam_id": steam_id, "season_id": "", "xp": 0, "premium": False, "claimed": set()}
    ensure_season_pass_schema(db.get_bind())
    row = db.execute(
        text(
            "SELECT xp, premium, claimed_json FROM season_pass_progress "
            "WHERE steam_id = :sid AND season_id = :seid"
        ),
        {"sid": str(steam_id), "seid": str(season_id)},
    ).fetchone()
    if not row:
        return {
            "steam_id": steam_id,
            "season_id": season_id,
            "xp": 0,
            "premium": False,
            "claimed": set(),
        }
    return {
        "steam_id": steam_id,
        "season_id": season_id,
        "xp": int(row[0] or 0),
        "premium": bool(int(row[1] or 0)),
        "claimed": _parse_claimed(row[2]),
    }


def _upsert_progress(
    db: Session,
    *,
    steam_id: str,
    season_id: str,
    xp: int,
    premium: bool,
    claimed: set[str],
) -> None:
    now = _naive_utc()
    claimed_json = json.dumps(sorted(claimed), ensure_ascii=False)
    is_sqlite = "sqlite" in str(db.get_bind().url).lower()
    params = {
        "sid": str(steam_id),
        "seid": str(season_id),
        "xp": int(xp),
        "prem": 1 if premium else 0,
        "cj": claimed_json,
        "now": now,
    }
    if is_sqlite:
        db.execute(
            text(
                "INSERT INTO season_pass_progress "
                "(steam_id, season_id, xp, premium, claimed_json, updated_at) "
                "VALUES (:sid, :seid, :xp, :prem, :cj, :now) "
                "ON CONFLICT(steam_id, season_id) DO UPDATE SET "
                "xp = excluded.xp, premium = excluded.premium, "
                "claimed_json = excluded.claimed_json, updated_at = excluded.updated_at"
            ),
            params,
        )
    else:
        db.execute(
            text(
                "INSERT INTO season_pass_progress "
                "(steam_id, season_id, xp, premium, claimed_json, updated_at) "
                "VALUES (:sid, :seid, :xp, :prem, :cj, :now) "
                "ON DUPLICATE KEY UPDATE "
                "xp = VALUES(xp), premium = VALUES(premium), "
                "claimed_json = VALUES(claimed_json), updated_at = VALUES(updated_at)"
            ),
            params,
        )


def add_timed_xp(
    db: Session,
    *,
    steam_id: str,
    amount: int,
    map_id: str,
    cycle_key: str,
    commit: bool = False,
) -> dict[str, Any]:
    """Credita Pass XP (= Â do tick) se season activa e abaixo do cap. Idempotente."""
    amount = int(amount)
    if amount <= 0:
        return {"applied": False, "reason": "zero"}
    cfg = spcfg.load_config()
    st = compute_status(cfg)
    if st != "active":
        return {"applied": False, "reason": f"season_{st}"}
    season_id = str(cfg.get("season_id") or "")
    if not season_id:
        return {"applied": False, "reason": "no_season"}

    ensure_season_pass_schema(db.get_bind())
    now = _naive_utc()
    mid = str(map_id or "unknown")[:64]
    ck = str(cycle_key)[:64]
    exists = db.execute(
        text(
            "SELECT 1 FROM season_pass_xp_events "
            "WHERE steam_id = :sid AND season_id = :seid AND map_id = :mid "
            "AND cycle_key = :ck AND amount = :amt LIMIT 1"
        ),
        {"sid": str(steam_id), "seid": season_id, "mid": mid, "ck": ck, "amt": amount},
    ).fetchone()
    if exists:
        return {"applied": False, "duplicate": True}

    db.execute(
        text(
            "INSERT INTO season_pass_xp_events "
            "(created_at, steam_id, season_id, amount, map_id, cycle_key) "
            "VALUES (:now, :sid, :seid, :amt, :mid, :ck)"
        ),
        {
            "now": now,
            "sid": str(steam_id),
            "seid": season_id,
            "amt": amount,
            "mid": mid,
            "ck": ck,
        },
    )

    prog = get_progress(db, steam_id, season_id)
    before = int(prog["xp"])
    if before >= MAX_XP:
        if commit:
            db.commit()
        return {
            "applied": False,
            "reason": "xp_cap",
            "xp": before,
            "xp_added": 0,
            "frozen": True,
        }
    added = min(amount, MAX_XP - before)
    after = before + added
    _upsert_progress(
        db,
        steam_id=steam_id,
        season_id=season_id,
        xp=after,
        premium=bool(prog["premium"]),
        claimed=set(prog["claimed"]),
    )
    if commit:
        db.commit()
    return {
        "applied": True,
        "xp_before": before,
        "xp_after": after,
        "xp_added": added,
        "frozen": after >= MAX_XP,
        "season_id": season_id,
    }


def buy_premium(db: Session, steam_id: str) -> dict[str, Any]:
    """Debita Âmbar do jogador, credita 100% no ARKBANK, marca premium."""
    cfg = spcfg.load_config()
    st = compute_status(cfg)
    if st != "active":
        raise ValueError(
            "Compra Premium só durante a season activa."
            if st != "inactive"
            else "Season ainda não foi iniciada."
        )
    season_id = str(cfg.get("season_id") or "")
    if not season_id:
        raise ValueError("Season ainda não foi iniciada.")
    price = spcfg.premium_price(cfg)
    if price <= 0:
        raise ValueError("Preço Premium inválido.")

    ensure_season_pass_schema(db.get_bind())
    prog = get_progress(db, steam_id, season_id)
    if prog["premium"]:
        return {
            "ok": True,
            "already_owned": True,
            "premium": True,
            "price_amber": price,
            "season_id": season_id,
        }

    subtract_fn: Callable = _cbs.get("subtract_points_tx")
    credit_ark_fn: Callable = _cbs.get("credit_arkbank_premium")
    if not subtract_fn or not credit_ark_fn:
        raise RuntimeError("season_pass_engine_not_wired")

    try:
        new_bal = subtract_fn(db, str(steam_id), int(price))
    except ValueError as exc:
        if "insufficient" in str(exc).lower():
            raise ValueError(f"Saldo insuficiente ({price:,} Â necessários).".replace(",", ".")) from exc
        raise

    ark = credit_ark_fn(
        db,
        steam_id=str(steam_id),
        amount=int(price),
        season_id=season_id,
        commit=False,
    )
    _upsert_progress(
        db,
        steam_id=steam_id,
        season_id=season_id,
        xp=int(prog["xp"]),
        premium=True,
        claimed=set(prog["claimed"]),
    )
    progress = spcfg.level_from_xp(int(prog["xp"]), list(cfg.get("xp_thresholds") or []))
    catchup_to = int(progress["level"])
    db.commit()
    return {
        "ok": True,
        "already_owned": False,
        "premium": True,
        "price_amber": price,
        "points_after": new_bal,
        "season_id": season_id,
        "catchup_to_level": catchup_to,
        "catchup_note": (
            f"Catch-up activo: podes resgatar Premium 1…{catchup_to} "
            "(e Free ×4 já desbloqueadas ainda não claimadas)."
            if catchup_to >= 1
            else "Premium activo — resgata à medida que sobes de nível."
        ),
        "arkbank": {
            "balance_after": ark.get("balance_after"),
            "duplicate": ark.get("duplicate"),
        },
    }


def tier_rank(group: str) -> int:
    return int(_TIER_RANK.get(str(group), 0))


def player_has_higher_license(entitlements: list[dict[str, Any]], grant_group: str) -> bool:
    """True se QUALQUER licença activa do jogador for de tier superior ao grant."""
    g_rank = tier_rank(grant_group)
    if g_rank <= 0:
        return False
    for ent in entitlements or []:
        eg = str(ent.get("group") or ent.get("group_name") or "")
        if tier_rank(eg) > g_rank:
            return True
    return False


def active_paid_license_groups(entitlements: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for ent in entitlements or []:
        eg = str(ent.get("group") or ent.get("group_name") or "").strip()
        if eg in _PAID_LICENSE_GROUPS:
            out.add(eg)
    return out


def player_can_accept_license(
    entitlements: list[dict[str, Any]], grant_group: str,
) -> bool:
    """Mesmo tier → renovação/stack OK; tier novo só com < 2 slots activos."""
    group = str(grant_group or "").strip()
    if group not in _PAID_LICENSE_GROUPS:
        return True
    active = active_paid_license_groups(entitlements)
    if group in active:
        return True
    return len(active) < MAX_ACTIVE_PAID_LICENSE_TIERS


def license_catalog_amber(group: str) -> int:
    fallback = {
        "Delta": 5000,
        "Gamma": 10000,
        "Beta": 15000,
        "Alfa": 25000,
        "Omega": 40000,
        "Transcendente": 60000,
    }
    fn: Callable | None = _cbs.get("license_catalog_price")
    if fn:
        try:
            price = int(fn(str(group)))
            if price > 0:
                return price
        except Exception as exc:
            log.warning("license_catalog_price failed for %s: %s", group, exc)
    return int(fallback.get(str(group), 5000))


def claim_eligibility(
    *,
    status: str,
    track: str,
    level: int,
    player_level: int,
    premium: bool,
    claimed: set[str],
    free_levels: list[int] | None = None,
) -> tuple[bool, str | None]:
    """Elegibilidade de claim.

    Janela: durante `active` e após `ends_at` (`claim_window`).
    Quando o admin inicia a season seguinte o calendário muda de season_id —
    claims da anterior ficam inacessíveis (perdidos).
    """
    if status not in ("active", "claim_window"):
        return False, "Season não permite claims (não iniciada ou já encerrada pela seguinte)."
    if track == "free":
        fl = free_levels or list(spcfg._FREE_LEVELS)
        if level not in fl:
            return False, f"Nível Free {level} não existe (só ×4)."
    elif track == "premium":
        if level < 1 or level > 30:
            return False, "Nível Premium inválido."
        if not premium:
            return False, "Track Premium bloqueada — compra o Premium nesta season."
    else:
        return False, "track deve ser free|premium"
    if player_level < level:
        return False, f"Nível {level} ainda não atingido (nível actual={player_level})."
    key = claimed_key(track, level)
    if key in claimed:
        return False, "Já resgatado."
    return True, None


def _fmt_amber(n: int) -> str:
    return f"{int(n):,}".replace(",", ".")


def _assert_grants_deliverable(
    annotated: list[dict[str, Any]],
    *,
    track: str,
    level: int,
) -> None:
    """Falha antes de qualquer entrega se ainda houver sku_pending."""
    if not annotated:
        raise ValueError("Sem rewards na config para este nó — edita no painel admin.")
    pending = [g for g in annotated if not g.get("grant_ready")]
    if not pending:
        return
    bits = []
    for g in pending:
        gtype = str(g.get("type") or "?")
        label = str(g.get("label") or "").strip()
        bits.append(f"{gtype}" + (f" ({label})" if label else ""))
    raise ValueError(
        f"sku_pending: {track} L{level} ainda sem ID de catálogo "
        f"({', '.join(bits)}). Resgate bloqueado até preencherem os SKUs."
    )


def _claim_message(delivery: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for d in delivery:
        dtype = str(d.get("type") or "")
        if dtype == "amber":
            parts.append(f"{_fmt_amber(int(d.get('qty') or 0))} Â creditados")
        elif dtype == "license" and d.get("choice") == "amber":
            parts.append(
                f"{_fmt_amber(int(d.get('amber') or 0))} Â "
                f"(alternativa à licença {d.get('id')})"
            )
        elif dtype == "license":
            parts.append(
                f"Licença {d.get('id')} ({int(d.get('days') or 0)} dias) activada"
            )
        elif d.get("pending_order"):
            parts.append(
                f"{dtype} «{d.get('id')}» na fila da loja — entra online e usa /shop"
            )
        elif d.get("delivered"):
            parts.append(f"{dtype} entregue")
    return " · ".join(parts) if parts else "Recompensa resgatada."


def license_choice_needed(
    entitlements: list[dict[str, Any]],
    grants: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Se algum grant license exige escolha licença↔Â, devolve detalhes.

    Motivos: já tem tier superior, ou já tem 2 tiers distintos e o grant
    seria um 3.º (máx. 2 licenças pagas activas).
    """
    for g in spcfg.annotate_grants(grants):
        if str(g.get("type") or "") != "license" or not g.get("grant_ready"):
            continue
        group = str(g.get("id") or "").strip()
        if not group:
            continue
        higher = player_has_higher_license(entitlements, group)
        slots_ok = player_can_accept_license(entitlements, group)
        if higher or not slots_ok:
            reason = "higher_tier" if higher else "slots_full"
            return {
                "group": group,
                "days": int(g.get("days") or 0),
                "amber_alternative": license_catalog_amber(group),
                "reason": reason,
            }
    return None


def _deliver_grants(
    db: Session,
    *,
    steam_id: str,
    season_id: str,
    track: str,
    level: int,
    grants: list[dict[str, Any]],
    license_choice: str | None,
    entitlements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    add_pts: Callable = _cbs.get("add_points_tx")
    queue_order: Callable = _cbs.get("queue_catalog_order")
    grant_lic: Callable = _cbs.get("grant_license")
    if not add_pts or not queue_order or not grant_lic:
        raise RuntimeError("season_pass_engine_not_wired")

    annotated = spcfg.annotate_grants(grants)
    _assert_grants_deliverable(annotated, track=track, level=level)

    # Exigir escolha L29-style ANTES de qualquer side-effect.
    choice_info = license_choice_needed(entitlements, annotated)
    if choice_info:
        choice = (license_choice or "").strip().lower()
        if choice not in ("license", "amber"):
            amt = int(choice_info["amber_alternative"])
            reason = str(choice_info.get("reason") or "")
            if reason == "slots_full":
                raise ValueError(
                    "Já tens 2 licenças de tier distintas activas. Escolhe "
                    f"license_choice='amber' (valor de catálogo: {_fmt_amber(amt)} Â) "
                    "ou 'license' só se fores renovar o mesmo tier."
                )
            raise ValueError(
                "Já tens licença de tier superior. Escolhe license_choice="
                f"'license' ou 'amber' (valor de catálogo: {_fmt_amber(amt)} Â)."
            )

    results: list[dict[str, Any]] = []
    for g in annotated:
        gtype = str(g.get("type") or "")
        if gtype == "amber":
            qty = int(g.get("qty") or 0)
            if qty <= 0:
                raise ValueError(f"Grant Â inválido em {track} L{level}")
            bal = add_pts(db, steam_id, qty)
            results.append({"type": "amber", "qty": qty, "delivered": True, "points_after": bal})
            continue

        if gtype == "license":
            group = str(g.get("id") or "").strip()
            days = int(g.get("days") or 0)
            needs_choice = bool(choice_info and choice_info.get("group") == group)
            choice = (
                (license_choice or "").strip().lower()
                if needs_choice
                else "license"
            )
            if needs_choice and choice == "amber":
                amt = license_catalog_amber(group)
                bal = add_pts(db, steam_id, amt)
                results.append({
                    "type": "license",
                    "id": group,
                    "choice": "amber",
                    "amber": amt,
                    "delivered": True,
                    "points_after": bal,
                })
            else:
                if not player_can_accept_license(entitlements, group):
                    raise ValueError(
                        "Já tens 2 licenças de tier distintas activas — "
                        "não é possível activar um terceiro tier. "
                        "Escolhe license_choice='amber'."
                    )
                grant_lic(db, steam_id, group, days, source=f"sp:{season_id}:{track}:{level}")
                results.append({
                    "type": "license",
                    "id": group,
                    "days": days,
                    "choice": "license",
                    "delivered": True,
                })
            continue

        if gtype in ("kit", "item", "dino"):
            gid = str(g.get("id") or "").strip()
            qty = max(1, int(g.get("qty") or 1))
            item_type = "kit" if gtype == "kit" else "shop"
            order_id = queue_order(
                db,
                steam_id=steam_id,
                item_type=item_type,
                item_id=gid,
                amount=qty,
                original_order_id=f"sp:{season_id}:{track}:{level}:{gtype}:{gid}",
            )
            results.append({
                "type": gtype,
                "id": gid,
                "qty": qty,
                "delivered": True,
                "pending_order": True,
                "order_id": order_id,
            })
            continue

        raise ValueError(f"Tipo de grant não suportado: {gtype}")
    return results


def claim_reward(
    db: Session,
    *,
    steam_id: str,
    track: str,
    level: int,
    license_choice: str | None = None,
) -> dict[str, Any]:
    cfg = spcfg.load_config()
    st = compute_status(cfg)
    season_id = str(cfg.get("season_id") or "")
    if not season_id:
        raise ValueError("Season ainda não foi iniciada.")

    ensure_season_pass_schema(db.get_bind())
    prog = get_progress(db, steam_id, season_id)
    progress = spcfg.level_from_xp(int(prog["xp"]), list(cfg.get("xp_thresholds") or []))
    player_level = int(progress["level"])
    ok, err = claim_eligibility(
        status=st,
        track=track,
        level=level,
        player_level=player_level,
        premium=bool(prog["premium"]),
        claimed=set(prog["claimed"]),
        free_levels=list(cfg.get("free_levels") or []),
    )
    if not ok:
        raise ValueError(err or "Claim não permitido")

    grants = spcfg.rewards_for(cfg, track, level)
    if not grants:
        raise ValueError("Sem rewards na config para este nó — edita no painel admin.")

    get_ents: Callable | None = _cbs.get("get_entitlements")
    ents = list(get_ents(steam_id, db) if get_ents else [])

    delivery = _deliver_grants(
        db,
        steam_id=steam_id,
        season_id=season_id,
        track=track,
        level=level,
        grants=grants,
        license_choice=license_choice,
        entitlements=ents,
    )

    claimed = set(prog["claimed"])
    claimed.add(claimed_key(track, level))
    _upsert_progress(
        db,
        steam_id=steam_id,
        season_id=season_id,
        xp=int(prog["xp"]),
        premium=bool(prog["premium"]),
        claimed=claimed,
    )

    # Audit mirror na claim queue JSON (histórico)
    try:
        spcfg.enqueue_claim(
            steam_id=steam_id,
            season_id=season_id,
            tier=str(cfg.get("current_tier") or "Delta"),
            track=track,
            level=level,
            grants=grants,
        )
        data = spcfg.load_claims()
        row = spcfg.find_claim(
            data, steam_id=steam_id, season_id=season_id, track=track, level=level
        )
        if row:
            row["status"] = "delivered"
            row["in_game_delivered"] = True
            row["delivery_result"] = delivery
            with spcfg._lock:
                spcfg._save_claims_unlocked(data)
    except Exception as exc:
        log.warning("season_pass claim audit queue: %s", exc)

    db.commit()
    msg = _claim_message(delivery)
    return {
        "ok": True,
        "track": track,
        "level": level,
        "season_id": season_id,
        "in_game_delivered": True,
        "delivery": delivery,
        "message": msg,
    }


def player_claimed_pairs(prog: dict[str, Any]) -> set[tuple[str, int]]:
    out: set[tuple[str, int]] = set()
    for key in prog.get("claimed") or set():
        parts = str(key).split(":")
        if len(parts) != 2:
            continue
        try:
            out.add((parts[0], int(parts[1])))
        except ValueError:
            continue
    return out


def new_order_id() -> str:
    return str(uuid.uuid4())
