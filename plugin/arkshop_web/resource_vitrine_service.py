"""Vitrine de Recursos — serviço (mercado P2P de recursos, somente Âmbar).

Contrato: docs/VITRINE_RECURSOS_SPEC.md. Todas as operações monetárias/estoque são transacionais e
idempotentes (guardas atômicas ``UPDATE ... WHERE`` com ``rowcount``; ``FOR UPDATE`` extra no MySQL).
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, delete, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from market_fee import compute_market_fee
from resource_vitrine_migrate import (
    resource_catalog as T_CAT,
    resource_claims as T_CLAIM,
    resource_settings as T_SET,
    resource_stock as T_STOCK,
    resource_transactions as T_TX,
    resource_uploads as T_UP,
)

log = logging.getLogger("arkshop.resource_vitrine")

# ── Constantes de negócio ────────────────────────────────────────────────────
DEFAULT_MAX_TYPES = 5
MIN_MAX_TYPES = 1
MAX_MAX_TYPES = 50
MAX_UPLOAD_LINES = 64
MAX_UPLOAD_QTY_PER_LINE = 1_000_000
MAX_STOCK_PER_RESOURCE = 100_000_000
MAX_LOT_SIZE = 1_000_000
MAX_LOT_PRICE = 100_000_000
MAX_LOTS_PER_PURCHASE = 1000
MAX_TOTAL_PRICE = 2_000_000_000
MAX_STACK_SIZE = 1_000_000
CLAIM_RESERVATION_HOURS = 24
CLAIMED_EXPIRY_GRACE_MINUTES = 15

CLAIM_PENDING = "PENDENTE"
CLAIM_CLAIMED = "CLAIMED"
CLAIM_DELIVERED = "DELIVERED"
CLAIM_REFUNDED = "REEMBOLSADO"
CLAIM_EXPIRED = "EXPIRADO"

KIND_BUY = "BUY"
KIND_WITHDRAW = "WITHDRAW"

TX_COMPLETED = "COMPLETED"
TX_REFUNDED = "REFUNDED"

UPLOAD_APPLIED = "APPLIED"
UPLOAD_CANCELLED = "CANCELLED"

SETTING_MAX_TYPES = "max_types_per_player"

_STEAM_RE = re.compile(r"^\d{17}$")
_UPLOAD_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{8,64}$")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_\-:.]{1,64}$")
_BP_RE = re.compile(r"(/(?:Game|Script|Engine)/[A-Za-z0-9_./\-]+)")
_NAME_BAD_RE = re.compile(r"[\x00-\x1f\x7f<>]")


class RVError(Exception):
    """Erro de negócio da Vitrine de Recursos (vira ``{ok:false, error, code}``)."""

    def __init__(self, message: str, code: str = "invalid_input", status: int = 400, **extra: Any) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status
        self.extra = extra


# ── Utilidades ───────────────────────────────────────────────────────────────

def _now() -> datetime:
    """UTC ingênuo (as colunas ``DateTime`` desta feature são naive-UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=None).isoformat() + "Z"


def _hours_remaining(expires_at: datetime | None, now: datetime | None = None) -> float | None:
    if expires_at is None:
        return None
    delta = (expires_at - (now or _now())).total_seconds() / 3600.0
    return round(max(0.0, delta), 2)


def clean_steam_id(value: Any) -> str:
    sid = str(value or "").strip()
    if not _STEAM_RE.match(sid):
        raise RVError("SteamID64 inválido", "invalid_input")
    return sid


def clean_request_id(value: Any) -> str | None:
    if value is None or value == "":
        return None
    rid = str(value).strip()
    if not _REQUEST_ID_RE.match(rid):
        raise RVError("request_id inválido", "invalid_input")
    return rid


def as_int(value: Any, field: str, *, minimum: int | None = None, maximum: int | None = None) -> int:
    if isinstance(value, bool) or value is None:
        raise RVError(f"{field} inválido", "invalid_input")
    if isinstance(value, float):
        if not value.is_integer():
            raise RVError(f"{field} inválido", "invalid_input")
        value = int(value)
    try:
        number = int(str(value).strip()) if not isinstance(value, int) else int(value)
    except (TypeError, ValueError):
        raise RVError(f"{field} inválido", "invalid_input")
    if minimum is not None and number < minimum:
        raise RVError(f"{field} deve ser ≥ {minimum}", "invalid_input")
    if maximum is not None and number > maximum:
        raise RVError(f"{field} deve ser ≤ {maximum}", "invalid_input")
    return number


def _strip_class_suffix(name: str) -> str:
    """Remove o sufixo de classe ``_C`` / ``_c`` (só no nome do objeto, não no asset)."""
    if len(name) > 2 and name[-2] == "_" and name[-1] in "Cc":
        return name[:-2]
    return name


def normalize_blueprint(raw: Any) -> tuple[str, str] | None:
    """Retorna ``(blueprint_canonico, chave_minuscula)`` ou None.

    Aceita o que o admin cola e o que o ARK reporta para o mesmo item:
    ``Blueprint'/Game/.../X.X'``, ``/Game/.../X.X``, ``/Game/.../X.X_C`` (ou ``_c``),
    ``BlueprintGeneratedClass /Game/.../X.X_C`` e o nome do CDO
    ``.../X.Default__X_C`` (``GetFullName`` do default object). Canônico: ``/Game/.../X.X``.
    """
    text_in = str(raw or "").strip()
    if not text_in or len(text_in) > 400:
        return None
    match = _BP_RE.search(text_in)
    if not match:
        return None
    path = match.group(1).rstrip("/.")
    slash = path.rfind("/")
    dot = path.rfind(".")
    if dot != -1 and dot > slash:
        obj = path[dot + 1 :]
        if obj.startswith("Default__") and len(obj) > 9:
            obj = obj[9:]
        obj = _strip_class_suffix(obj)
        if not obj:
            return None
        path = path[: dot + 1] + obj
    else:
        path = _strip_class_suffix(path)
        last = path.rsplit("/", 1)[-1]
        if not last:
            return None
        if "." not in last:
            path = f"{path}.{last}"
    if len(path) > 255 or ".." in path:
        return None
    return path, path.lower()


def ascii_fold(value: str) -> str:
    """Nome seguro para o chat do jogo (ASCII)."""
    folded = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    folded = re.sub(r"[^\x20-\x7e]", "", folded).strip()
    return folded or "Recurso"


def _dialect_is_sqlite(db: Session) -> bool:
    bind = getattr(db, "bind", None)
    return "sqlite" in str(getattr(bind, "url", "")).lower()


def _seller_name(db: Session, steam_id: str) -> str:
    try:
        from market_listings import _profile_display_name

        name = _profile_display_name(db, steam_id)
        if name:
            return name
    except Exception:
        pass
    return f"Jogador …{steam_id[-4:]}"


def _audit(db: Session, event_type: str, **kwargs: Any) -> None:
    """Auditoria best-effort (nunca derruba a operação principal)."""
    try:
        from market_audit import market_audit_event

        kwargs.setdefault("commit", True)
        market_audit_event(db, event_type, **kwargs)
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        log.warning("auditoria %s falhou: %s", event_type, exc)


def _ledger(db: Session, **kwargs: Any) -> None:
    try:
        from amber_ledger import record_movement

        record_movement(db, commit=True, **kwargs)
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        log.warning("amber_ledger (vitrine recursos) falhou: %s", exc)


# ── Configuração (catálogo + settings) ───────────────────────────────────────

def get_max_types(db: Session) -> int:
    row = db.execute(select(T_SET.c.setting_value).where(T_SET.c.setting_key == SETTING_MAX_TYPES)).first()
    if not row:
        return DEFAULT_MAX_TYPES
    try:
        value = int(row[0])
    except (TypeError, ValueError):
        return DEFAULT_MAX_TYPES
    return max(MIN_MAX_TYPES, min(MAX_MAX_TYPES, value))


def set_max_types(db: Session, value: Any) -> int:
    number = as_int(value, "max_types_per_player", minimum=MIN_MAX_TYPES, maximum=MAX_MAX_TYPES)
    now = _now()
    existing = db.execute(select(T_SET.c.setting_key).where(T_SET.c.setting_key == SETTING_MAX_TYPES)).first()
    if existing:
        db.execute(
            update(T_SET).where(T_SET.c.setting_key == SETTING_MAX_TYPES).values(setting_value=str(number), updated_at=now)
        )
    else:
        db.execute(insert(T_SET).values(setting_key=SETTING_MAX_TYPES, setting_value=str(number), updated_at=now))
    db.commit()
    return number


def _catalog_row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(row.id),
        "blueprint": row.blueprint,
        "key": row.blueprint_key,
        "name": row.name,
        "name_ascii": ascii_fold(row.name),
        "stack_size": int(row.stack_size or 1),
        "min_lot_price": int(row.min_lot_price) if row.min_lot_price is not None else None,
        "max_lot_price": int(row.max_lot_price) if row.max_lot_price is not None else None,
        "enabled": bool(row.enabled),
    }


def list_catalog(db: Session, *, include_disabled: bool = False) -> list[dict[str, Any]]:
    q = select(T_CAT).order_by(T_CAT.c.name.asc(), T_CAT.c.id.asc())
    if not include_disabled:
        q = q.where(T_CAT.c.enabled == 1)
    return [_catalog_row_to_dict(r) for r in db.execute(q).all()]


def _catalog_by_key(db: Session) -> dict[str, Any]:
    rows = db.execute(select(T_CAT)).all()
    return {r.blueprint_key: r for r in rows}


def plugin_config(db: Session) -> dict[str, Any]:
    return {
        "max_types_per_player": get_max_types(db),
        "resources": [
            {
                "id": r["id"],
                "blueprint": r["blueprint"],
                "key": r["key"],
                "name": r["name"],
                "name_ascii": r["name_ascii"],
                "stack_size": r["stack_size"],
            }
            for r in list_catalog(db)
        ],
    }


def admin_overview(db: Session) -> dict[str, Any]:
    resources = list_catalog(db, include_disabled=True)
    stock_rows = db.execute(
        select(T_STOCK.c.resource_id, func.count(T_STOCK.c.id), func.coalesce(func.sum(T_STOCK.c.quantity), 0))
        .where(T_STOCK.c.quantity > 0)
        .group_by(T_STOCK.c.resource_id)
    ).all()
    stats = {int(r[0]): {"owners": int(r[1]), "quantity": int(r[2])} for r in stock_rows}
    for res in resources:
        res.update(stats.get(res["id"], {"owners": 0, "quantity": 0}))
    return {
        "resources": resources,
        "max_types_per_player": get_max_types(db),
        "limits": {
            "default_max_types": DEFAULT_MAX_TYPES,
            "min_max_types": MIN_MAX_TYPES,
            "max_max_types": MAX_MAX_TYPES,
            "max_lot_price": MAX_LOT_PRICE,
            "max_lot_size": MAX_LOT_SIZE,
            "max_stack_size": MAX_STACK_SIZE,
        },
    }


def _resource_has_dependents(db: Session, resource_id: int) -> bool:
    stock = db.execute(
        select(func.count(T_STOCK.c.id)).where(T_STOCK.c.resource_id == resource_id, T_STOCK.c.quantity > 0)
    ).scalar()
    claims = db.execute(
        select(func.count(T_CLAIM.c.id)).where(
            T_CLAIM.c.resource_id == resource_id, T_CLAIM.c.status.in_([CLAIM_PENDING, CLAIM_CLAIMED])
        )
    ).scalar()
    return bool(stock or claims)


def upsert_catalog_resource(db: Session, body: dict[str, Any], *, admin_steam_id: str | None = None) -> dict[str, Any]:
    normalized = normalize_blueprint(body.get("blueprint"))
    if not normalized:
        raise RVError("Blueprint inválido (use o caminho /Game/.../Nome.Nome)", "invalid_input")
    blueprint, key = normalized
    name = str(body.get("name") or "").strip()
    if not name or len(name) > 80 or _NAME_BAD_RE.search(name):
        raise RVError("Nome inválido (1–80 caracteres, sem símbolos de controle)", "invalid_input")
    stack_size = as_int(body.get("stack_size", 100), "stack_size", minimum=1, maximum=MAX_STACK_SIZE)

    min_price = body.get("min_lot_price")
    max_price = body.get("max_lot_price")
    min_val = None if min_price in (None, "") else as_int(min_price, "min_lot_price", minimum=1, maximum=MAX_LOT_PRICE)
    max_val = None if max_price in (None, "") else as_int(max_price, "max_lot_price", minimum=1, maximum=MAX_LOT_PRICE)
    if min_val is not None and max_val is not None and min_val > max_val:
        raise RVError("Preço mínimo não pode ser maior que o máximo", "invalid_input")
    enabled = 1 if bool(body.get("enabled", True)) else 0

    now = _now()
    rid_raw = body.get("id")
    current = None
    if rid_raw not in (None, ""):
        rid = as_int(rid_raw, "id", minimum=1)
        current = db.execute(select(T_CAT).where(T_CAT.c.id == rid)).first()
        if current is None:
            raise RVError("Recurso não encontrado", "not_found", 404)

    clash = db.execute(select(T_CAT.c.id).where(T_CAT.c.blueprint_key == key)).first()
    if clash and (current is None or int(clash[0]) != int(current.id)):
        raise RVError("Já existe um recurso com este blueprint", "invalid_input", 409)

    if current is not None:
        if current.blueprint_key != key and _resource_has_dependents(db, int(current.id)):
            raise RVError(
                "Não é possível trocar o blueprint de um recurso com estoque ou resgates pendentes", "invalid_input"
            )
        db.execute(
            update(T_CAT)
            .where(T_CAT.c.id == current.id)
            .values(
                blueprint_key=key,
                blueprint=blueprint,
                name=name,
                stack_size=stack_size,
                min_lot_price=min_val,
                max_lot_price=max_val,
                enabled=enabled,
                updated_at=now,
            )
        )
        resource_id = int(current.id)
    else:
        try:
            result = db.execute(
                insert(T_CAT).values(
                    blueprint_key=key,
                    blueprint=blueprint,
                    name=name,
                    stack_size=stack_size,
                    min_lot_price=min_val,
                    max_lot_price=max_val,
                    enabled=enabled,
                    created_at=now,
                    updated_at=now,
                )
            )
        except IntegrityError:
            db.rollback()
            raise RVError("Já existe um recurso com este blueprint", "invalid_input", 409)
        resource_id = int(result.inserted_primary_key[0])
    db.commit()
    row = db.execute(select(T_CAT).where(T_CAT.c.id == resource_id)).first()
    _audit(
        db,
        "MARKET_RESOURCE_ADMIN_CATALOG",
        source="web",
        steam_id=admin_steam_id,
        metadata={"resource_id": resource_id, "blueprint": blueprint, "name": name, "enabled": bool(enabled)},
    )
    return _catalog_row_to_dict(row)


def disable_catalog_resource(db: Session, resource_id: int, *, admin_steam_id: str | None = None) -> dict[str, Any]:
    row = db.execute(select(T_CAT).where(T_CAT.c.id == resource_id)).first()
    if row is None:
        raise RVError("Recurso não encontrado", "not_found", 404)
    db.execute(update(T_CAT).where(T_CAT.c.id == resource_id).values(enabled=0, updated_at=_now()))
    db.commit()
    _audit(
        db,
        "MARKET_RESOURCE_ADMIN_CATALOG",
        source="web",
        steam_id=admin_steam_id,
        metadata={"resource_id": resource_id, "blueprint": row.blueprint, "enabled": False, "action": "disable"},
    )
    return {"id": resource_id, "enabled": False, "has_dependents": _resource_has_dependents(db, resource_id)}


# ── Estoque: helpers ─────────────────────────────────────────────────────────

def _insert_ignore(db: Session, table: Any, **values: Any) -> int:
    """INSERT que ignora violação de UNIQUE (sem SAVEPOINT). Retorna linhas inseridas (0/1)."""
    prefix = "OR IGNORE" if _dialect_is_sqlite(db) else "IGNORE"
    result = db.execute(insert(table).prefix_with(prefix).values(**values))
    return int(getattr(result, "rowcount", 0) or 0)


def _stock_row(db: Session, steam_id: str, resource_id: int, *, lock: bool = False) -> Any | None:
    q = select(T_STOCK).where(T_STOCK.c.steam_id == steam_id, T_STOCK.c.resource_id == resource_id)
    if lock:
        q = q.with_for_update()
    return db.execute(q).first()


def _add_stock(db: Session, steam_id: str, resource_id: int, quantity: int, *, cap: bool = True) -> int:
    """Soma ``quantity`` ao estoque (cria linha se preciso). Retorna a quantidade resultante."""
    now = _now()
    row = _stock_row(db, steam_id, resource_id, lock=True)
    if row is None:
        _insert_ignore(
            db,
            T_STOCK,
            steam_id=steam_id,
            resource_id=resource_id,
            quantity=0,
            lot_size=None,
            lot_price=None,
            active=0,
            created_at=now,
            updated_at=now,
        )
        row = _stock_row(db, steam_id, resource_id, lock=True)
    if row is None:  # pragma: no cover - defensivo
        raise RVError("Falha ao criar estoque", "internal", 500)
    new_qty = int(row.quantity or 0) + int(quantity)
    if cap and new_qty > MAX_STOCK_PER_RESOURCE:
        raise RVError(
            f"Estoque máximo por recurso é {MAX_STOCK_PER_RESOURCE:,}".replace(",", "."),
            "stock_cap",
        )
    db.execute(
        update(T_STOCK)
        .where(T_STOCK.c.id == row.id)
        .values(quantity=T_STOCK.c.quantity + int(quantity), updated_at=now)
    )
    return new_qty


def _count_types(db: Session, steam_id: str) -> int:
    return int(
        db.execute(
            select(func.count(T_STOCK.c.id)).where(T_STOCK.c.steam_id == steam_id, T_STOCK.c.quantity > 0)
        ).scalar()
        or 0
    )


def plugin_stock_summary(db: Session, steam_id: str) -> dict[str, Any]:
    steam_id = clean_steam_id(steam_id)
    rows = db.execute(
        select(T_STOCK.c.resource_id).where(T_STOCK.c.steam_id == steam_id, T_STOCK.c.quantity > 0)
    ).all()
    types = sorted(int(r[0]) for r in rows)
    return {"max_types": get_max_types(db), "type_count": len(types), "types": types}


# ── Upload (plugin) ──────────────────────────────────────────────────────────

def _merge_upload_lines(db: Session, items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list) or not items:
        raise RVError("Nenhum item informado", "invalid_input")
    if len(items) > MAX_UPLOAD_LINES:
        raise RVError(f"Itens demais (máx. {MAX_UPLOAD_LINES})", "invalid_input")
    catalog = _catalog_by_key(db)
    merged: dict[int, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            raise RVError("Item inválido", "invalid_input")
        normalized = normalize_blueprint(item.get("blueprint"))
        if not normalized:
            raise RVError("Blueprint inválido", "not_authorized_resource")
        res = catalog.get(normalized[1])
        if res is None or not res.enabled:
            raise RVError(
                f"Recurso não autorizado na vitrine: {normalized[0].rsplit('/', 1)[-1]}",
                "not_authorized_resource",
            )
        qty = as_int(item.get("quantity"), "quantity", minimum=1, maximum=MAX_UPLOAD_QTY_PER_LINE)
        slot = merged.setdefault(int(res.id), {"resource_id": int(res.id), "name": res.name, "blueprint": res.blueprint, "quantity": 0})
        slot["quantity"] += qty
        if slot["quantity"] > MAX_UPLOAD_QTY_PER_LINE:
            raise RVError(f"Quantidade acima do limite por envio ({MAX_UPLOAD_QTY_PER_LINE})", "invalid_input")
    return list(merged.values())


def _upload_result(row: Any, *, duplicate: bool) -> dict[str, Any]:
    lines: list[dict[str, Any]] = []
    try:
        lines = json.loads(row.lines_json or "[]")
    except Exception:
        lines = []
    return {
        "status": row.status,
        "upload_id": row.upload_id,
        "duplicate": duplicate,
        "credited": lines,
        "total_quantity": int(row.total_quantity or 0),
    }


def _get_upload(db: Session, upload_id: str) -> Any | None:
    return db.execute(select(T_UP).where(T_UP.c.upload_id == upload_id)).first()


def process_upload(db: Session, body: dict[str, Any]) -> dict[str, Any]:
    steam_id = clean_steam_id(body.get("steam_id"))
    upload_id = str(body.get("upload_id") or "").strip()
    if not _UPLOAD_ID_RE.match(upload_id):
        raise RVError("upload_id inválido", "invalid_input")

    existing = _get_upload(db, upload_id)
    if existing is not None:
        return _resolve_existing_upload(existing, steam_id)

    lines = _merge_upload_lines(db, body.get("items"))
    now = _now()
    try:
        # Trava as linhas de estoque do jogador (MySQL) e apura o limite de tipos.
        held = {
            int(r.resource_id): int(r.quantity or 0)
            for r in db.execute(select(T_STOCK).where(T_STOCK.c.steam_id == steam_id).with_for_update()).all()
        }
        current_types = sum(1 for q in held.values() if q > 0)
        max_types = get_max_types(db)
        new_types = [ln for ln in lines if held.get(ln["resource_id"], 0) <= 0]
        if new_types and current_types + len(new_types) > max_types:
            allowed = max(0, max_types - current_types)
            rejected = [ln["name"] for ln in new_types[allowed:]]
            raise RVError(
                f"Limite de {max_types} tipos de recurso na vitrine. Não cabem: {', '.join(rejected)}",
                "type_limit",
                max_types=max_types,
                type_count=current_types,
                rejected=rejected,
            )

        total = sum(ln["quantity"] for ln in lines)
        inserted = _insert_ignore(
            db,
            T_UP,
            upload_id=upload_id,
            steam_id=steam_id,
            status=UPLOAD_APPLIED,
            lines_json=json.dumps(lines, ensure_ascii=False),
            total_quantity=total,
            created_at=now,
            updated_at=now,
        )
        if inserted != 1:
            # Corrida com o mesmo upload_id: outro request já gravou — devolve o resultado original.
            db.rollback()
            row = _get_upload(db, upload_id)
            if row is None:
                raise RVError("Falha ao registrar upload", "internal", 500)
            return _resolve_existing_upload(row, steam_id)

        credited = []
        for ln in lines:
            new_qty = _add_stock(db, steam_id, ln["resource_id"], ln["quantity"])
            credited.append({**ln, "stock_quantity": new_qty})
        db.execute(
            update(T_UP).where(T_UP.c.upload_id == upload_id).values(lines_json=json.dumps(credited, ensure_ascii=False))
        )
        db.commit()
    except RVError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    _audit(
        db,
        "MARKET_RESOURCE_UPLOAD",
        source="plugin",
        steam_id=steam_id,
        market_trace_id=upload_id[:64],
        metadata={"upload_id": upload_id, "lines": [{"resource_id": c["resource_id"], "quantity": c["quantity"]} for c in credited]},
    )
    return {
        "status": UPLOAD_APPLIED,
        "upload_id": upload_id,
        "duplicate": False,
        "credited": credited,
        "total_quantity": total,
    }


def _resolve_existing_upload(row: Any, steam_id: str) -> dict[str, Any]:
    if row.steam_id != steam_id:
        raise RVError("upload_id já usado por outro jogador", "invalid_input", 409)
    if row.status == UPLOAD_CANCELLED:
        raise RVError("Este envio foi cancelado e não pode ser reaplicado", "upload_cancelled", 409)
    return _upload_result(row, duplicate=True)


def get_upload_status(db: Session, upload_id: str) -> dict[str, Any]:
    upload_id = str(upload_id or "").strip()
    if not _UPLOAD_ID_RE.match(upload_id):
        raise RVError("upload_id inválido", "invalid_input")
    row = _get_upload(db, upload_id)
    if row is None:
        return {"status": "UNKNOWN", "upload_id": upload_id}
    return {"status": row.status, "upload_id": upload_id}


def cancel_upload(db: Session, body: dict[str, Any]) -> dict[str, Any]:
    steam_id = clean_steam_id(body.get("steam_id"))
    upload_id = str(body.get("upload_id") or "").strip()
    if not _UPLOAD_ID_RE.match(upload_id):
        raise RVError("upload_id inválido", "invalid_input")
    now = _now()
    row = _get_upload(db, upload_id)
    if row is None:
        _insert_ignore(
            db,
            T_UP,
            upload_id=upload_id,
            steam_id=steam_id,
            status=UPLOAD_CANCELLED,
            lines_json="[]",
            total_quantity=0,
            created_at=now,
            updated_at=now,
        )
        db.commit()
        row = _get_upload(db, upload_id)
        if row is not None and row.status == UPLOAD_CANCELLED and row.steam_id == steam_id:
            _audit(
                db,
                "MARKET_RESOURCE_UPLOAD_CANCELLED",
                source="plugin",
                steam_id=steam_id,
                market_trace_id=upload_id[:64],
                metadata={"upload_id": upload_id},
            )
    if row is None:
        raise RVError("Falha ao cancelar upload", "internal", 500)
    if row.steam_id != steam_id:
        raise RVError("upload_id pertence a outro jogador", "invalid_input", 409)
    return {"status": row.status, "upload_id": upload_id}


# ── Anúncio (jogador, web) ───────────────────────────────────────────────────

def _listing_state(stock: Any, resource: Any) -> str:
    qty = int(stock.quantity or 0)
    lot = stock.lot_size
    price = stock.lot_price
    if not resource.enabled:
        return "resource_disabled"
    if not lot or not price:
        return "no_lot_defined"
    if not stock.active:
        return "paused"
    if qty < int(lot):
        return "no_full_lot"
    return "active"


def _stock_to_public(stock: Any, resource: Any) -> dict[str, Any]:
    qty = int(stock.quantity or 0)
    lot = int(stock.lot_size) if stock.lot_size else None
    price = int(stock.lot_price) if stock.lot_price else None
    return {
        "stock_id": int(stock.id),
        "resource_id": int(stock.resource_id),
        "resource": _catalog_row_to_dict(resource),
        "quantity": qty,
        "lot_size": lot,
        "lot_price": price,
        "active": bool(stock.active),
        "lots_available": (qty // lot) if lot else 0,
        "leftover": (qty % lot) if lot else qty,
        "state": _listing_state(stock, resource),
        "updated_at": _iso(stock.updated_at),
    }


def set_listing(
    db: Session, steam_id: str, resource_id: int, body: dict[str, Any]
) -> dict[str, Any]:
    steam_id = clean_steam_id(steam_id)
    resource = db.execute(select(T_CAT).where(T_CAT.c.id == resource_id)).first()
    if resource is None:
        raise RVError("Recurso não encontrado", "not_found", 404)
    stock = _stock_row(db, steam_id, resource_id, lock=True)
    if stock is None:
        raise RVError("Você não tem estoque deste recurso na vitrine", "not_found", 404)

    lot_size = body.get("lot_size", stock.lot_size)
    lot_price = body.get("lot_price", stock.lot_price)
    want_active = bool(body.get("active", stock.active))

    values: dict[str, Any] = {"updated_at": _now()}
    if lot_size in (None, "") and lot_price in (None, ""):
        if want_active:
            raise RVError("Defina tamanho do lote e preço para ativar", "invalid_input")
        lot_size = lot_price = None
    else:
        lot_size = as_int(lot_size, "lot_size", minimum=1, maximum=MAX_LOT_SIZE)
        lot_price = as_int(lot_price, "lot_price", minimum=1, maximum=MAX_LOT_PRICE)
        if resource.min_lot_price is not None and lot_price < int(resource.min_lot_price):
            raise RVError(
                f"Preço mínimo por lote para {resource.name}: {int(resource.min_lot_price)} Âmbares",
                "price_out_of_range",
            )
        if resource.max_lot_price is not None and lot_price > int(resource.max_lot_price):
            raise RVError(
                f"Preço máximo por lote para {resource.name}: {int(resource.max_lot_price)} Âmbares",
                "price_out_of_range",
            )
    if want_active and not resource.enabled:
        raise RVError("Este recurso foi desativado pela administração", "not_authorized_resource")
    values.update(lot_size=lot_size, lot_price=lot_price, active=1 if want_active else 0)
    db.execute(update(T_STOCK).where(T_STOCK.c.id == stock.id).values(**values))
    db.commit()
    refreshed = _stock_row(db, steam_id, resource_id)
    _audit(
        db,
        "MARKET_RESOURCE_LISTING_SET",
        source="web",
        steam_id=steam_id,
        listing_id=int(stock.id),
        effective_price=lot_price,
        metadata={"resource_id": resource_id, "lot_size": lot_size, "lot_price": lot_price, "active": want_active},
    )
    return _stock_to_public(refreshed, resource)


# ── Explorar (público) ───────────────────────────────────────────────────────

def list_public_listings(
    db: Session,
    *,
    seller_steam_id: str | None = None,
    resource_id: int | None = None,
    query: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> list[dict[str, Any]]:
    limit = max(1, min(100, int(limit)))
    offset = max(0, int(offset))
    q = (
        select(T_STOCK)
        .join(T_CAT, T_CAT.c.id == T_STOCK.c.resource_id)
        .where(
            T_STOCK.c.active == 1,
            T_CAT.c.enabled == 1,
            T_STOCK.c.lot_size.isnot(None),
            T_STOCK.c.lot_price.isnot(None),
            T_STOCK.c.quantity >= T_STOCK.c.lot_size,
        )
        .order_by(T_STOCK.c.updated_at.desc(), T_STOCK.c.id.desc())
    )
    if seller_steam_id:
        q = q.where(T_STOCK.c.steam_id == str(seller_steam_id).strip())
    if resource_id:
        q = q.where(T_STOCK.c.resource_id == int(resource_id))
    if query:
        like = "%" + re.sub(r"[%_\\]", "", str(query).strip().lower())[:60] + "%"
        q = q.where(func.lower(T_CAT.c.name).like(like))
    rows = db.execute(q.offset(offset).limit(limit)).all()
    catalog = {int(r.id): r for r in db.execute(select(T_CAT)).all()}
    out: list[dict[str, Any]] = []
    names: dict[str, str] = {}
    for row in rows:
        sid = row.steam_id
        res = catalog.get(int(row.resource_id))
        if res is None:
            continue
        if sid not in names:
            names[sid] = _seller_name(db, sid)
        lot = int(row.lot_size)
        out.append(
            {
                "stock_id": int(row.id),
                "seller_steam_id": sid,
                "seller_display_name": names[sid],
                "resource": _catalog_row_to_dict(res),
                "lot_size": lot,
                "lot_price": int(row.lot_price),
                "unit_price": round(int(row.lot_price) / lot, 4),
                "lots_available": int(row.quantity) // lot,
                "stock_quantity": int(row.quantity),
            }
        )
    return out


# ── Compra ───────────────────────────────────────────────────────────────────

def _new_claim_values(
    *,
    kind: str,
    recipient: str,
    seller: str | None,
    resource: Any,
    quantity: int,
    tx_id: int | None,
    request_id: str | None,
    now: datetime,
    blueprint: str | None = None,
    name: str | None = None,
    stack_size: int | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "recipient_steam_id": recipient,
        "seller_steam_id": seller,
        "resource_id": int(resource.id),
        "blueprint": blueprint or resource.blueprint,
        "resource_name": name or resource.name,
        "stack_size": int(stack_size or resource.stack_size or 1),
        "quantity": int(quantity),
        "tx_id": tx_id,
        "status": CLAIM_PENDING,
        "request_id": request_id,
        "claim_reserved_at": now,
        "claim_expires_at": now + timedelta(hours=CLAIM_RESERVATION_HOURS),
        "claimed_at": None,
        "delivered_at": None,
        "created_at": now,
        "updated_at": now,
    }


def _claim_public(row: Any, *, now: datetime | None = None) -> dict[str, Any]:
    return {
        "claim_id": int(row.id),
        "kind": row.kind,
        "resource_id": int(row.resource_id),
        "blueprint": row.blueprint,
        "name": row.resource_name,
        "name_ascii": ascii_fold(row.resource_name),
        "quantity": int(row.quantity),
        "stack_size": int(row.stack_size or 1),
        "status": row.status,
        "expires_at": _iso(row.claim_expires_at),
        "hours_remaining": _hours_remaining(row.claim_expires_at, now),
    }


def _purchase_result_from_existing(db: Session, tx: Any) -> dict[str, Any]:
    claim = db.execute(select(T_CLAIM).where(T_CLAIM.c.tx_id == tx.id, T_CLAIM.c.kind == KIND_BUY)).first()
    return {
        "duplicate": True,
        "tx_id": int(tx.id),
        "claim_id": int(claim.id) if claim else None,
        "stock_id": int(tx.stock_id),
        "lots": int(tx.lots),
        "quantity": int(tx.quantity),
        "price_paid": int(tx.price_paid),
        "buyer_balance": tx.buyer_points_after,
        "claim_expires_at": _iso(claim.claim_expires_at) if claim else None,
        "message": f"Compra já registrada. Resgate com /mercado em até {CLAIM_RESERVATION_HOURS}h.",
    }


def purchase_lots(
    db: Session,
    stock_id: int,
    buyer_steam_id: str,
    lots: Any,
    *,
    request_id: str | None = None,
    expected_price: Any = None,
) -> dict[str, Any]:
    from market_listings import _credit_points, _debit_points, _player_points

    buyer = clean_steam_id(buyer_steam_id)
    lots_n = as_int(lots, "lots", minimum=1, maximum=MAX_LOTS_PER_PURCHASE)
    request_id = clean_request_id(request_id)
    expected = None if expected_price in (None, "") else as_int(expected_price, "expected_price", minimum=0)

    if request_id:
        prev = db.execute(
            select(T_TX).where(T_TX.c.buyer_steam_id == buyer, T_TX.c.request_id == request_id)
        ).first()
        if prev is not None:
            return _purchase_result_from_existing(db, prev)

    try:
        stock = db.execute(select(T_STOCK).where(T_STOCK.c.id == stock_id).with_for_update()).first()
        if stock is None:
            raise RVError("Anúncio não encontrado", "not_found", 404)
        resource = db.execute(select(T_CAT).where(T_CAT.c.id == stock.resource_id)).first()
        if resource is None or not resource.enabled:
            raise RVError("Recurso indisponível", "not_found", 404)
        if stock.steam_id == buyer:
            raise RVError("Não é possível comprar da sua própria vitrine", "self_purchase")
        if not stock.active or not stock.lot_size or not stock.lot_price:
            raise RVError("Anúncio não disponível", "not_found", 404)
        lot_size = int(stock.lot_size)
        lot_price = int(stock.lot_price)
        available = int(stock.quantity or 0) // lot_size
        if lots_n > available:
            raise RVError(
                f"Estoque insuficiente: {available} lote(s) disponível(is)", "insufficient_stock", available=available
            )
        price = lots_n * lot_price
        if price > MAX_TOTAL_PRICE:
            raise RVError("Valor total acima do limite permitido", "invalid_input")
        if expected is not None and expected != price:
            raise RVError("O preço mudou — atualize a lista e tente de novo", "price_changed", price=price)
        quantity = lots_n * lot_size
        seller = stock.steam_id
        now = _now()

        # 1) Guarda atômica do estoque (vale mesmo sem FOR UPDATE).
        res = db.execute(
            update(T_STOCK)
            .where(
                T_STOCK.c.id == stock.id,
                T_STOCK.c.quantity >= quantity,
                T_STOCK.c.active == 1,
                T_STOCK.c.lot_size == lot_size,
                T_STOCK.c.lot_price == lot_price,
            )
            .values(quantity=T_STOCK.c.quantity - quantity, updated_at=now)
        )
        if getattr(res, "rowcount", 0) != 1:
            raise RVError("O anúncio mudou — atualize a lista e tente de novo", "price_changed")

        # 2) Âmbar: débito atômico condicional + crédito.
        buyer_before = _player_points(db, buyer)
        if buyer_before < price:
            raise RVError(f"Saldo insuficiente ({buyer_before} < {price})", "insufficient_balance")
        seller_before = _player_points(db, seller)
        try:
            buyer_after = _debit_points(db, buyer, price)
        except ValueError:
            raise RVError(f"Saldo insuficiente ({buyer_before} < {price})", "insufficient_balance")
        fee = compute_market_fee(price)
        seller_credit = price - fee
        seller_after = _credit_points(db, seller, seller_credit)

        trace = uuid.uuid4().hex
        tx_result = db.execute(
            insert(T_TX).values(
                request_id=request_id,
                stock_id=int(stock.id),
                resource_id=int(resource.id),
                seller_steam_id=seller,
                buyer_steam_id=buyer,
                blueprint=resource.blueprint,
                resource_name=resource.name,
                lots=lots_n,
                lot_size=lot_size,
                lot_price=lot_price,
                quantity=quantity,
                price_paid=price,
                fee_amount=fee,
                seller_credit=seller_credit,
                buyer_points_before=buyer_before,
                buyer_points_after=buyer_after,
                seller_points_before=seller_before,
                seller_points_after=seller_after,
                status=TX_COMPLETED,
                market_trace_id=trace,
                created_at=now,
            )
        )
        tx_id = int(tx_result.inserted_primary_key[0])
        claim_result = db.execute(
            insert(T_CLAIM).values(
                **_new_claim_values(
                    kind=KIND_BUY,
                    recipient=buyer,
                    seller=seller,
                    resource=resource,
                    quantity=quantity,
                    tx_id=tx_id,
                    request_id=request_id,
                    now=now,
                )
            )
        )
        claim_id = int(claim_result.inserted_primary_key[0])
        db.commit()
    except IntegrityError:
        # request_id duplicado em corrida: a transação inteira foi abortada — devolve o resultado original.
        db.rollback()
        if request_id:
            prev = db.execute(
                select(T_TX).where(T_TX.c.buyer_steam_id == buyer, T_TX.c.request_id == request_id)
            ).first()
            if prev is not None:
                return _purchase_result_from_existing(db, prev)
        raise
    except RVError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    _audit(
        db,
        "MARKET_RESOURCE_PURCHASE",
        source="web",
        steam_id=buyer,
        counterparty_steam_id=seller,
        listing_id=int(stock_id),
        claim_id=claim_id,
        effective_price=price,
        points_delta=-price,
        points_before=buyer_before,
        points_after=buyer_after,
        market_trace_id=trace,
        metadata={
            "tx_id": tx_id,
            "resource_id": int(resource.id),
            "resource": resource.name,
            "lots": lots_n,
            "lot_size": lot_size,
            "quantity": quantity,
            "fee_amount": fee,
        },
    )
    _ledger(
        db,
        channel="market",
        event_type="market_resource_purchase_buyer",
        signed_delta=-price,
        idempotency_key=f"market:restx:{tx_id}:buyer",
        steam_id=buyer,
        counterparty_id=seller,
        source_table="market_resource_transactions",
        source_id=str(tx_id),
        metadata={"stock_id": int(stock_id), "leg": "buyer"},
    )
    _ledger(
        db,
        channel="market",
        event_type="market_resource_purchase_seller",
        signed_delta=seller_credit,
        idempotency_key=f"market:restx:{tx_id}:seller",
        steam_id=seller,
        counterparty_id=buyer,
        source_table="market_resource_transactions",
        source_id=str(tx_id),
        metadata={"stock_id": int(stock_id), "leg": "seller"},
    )
    return {
        "duplicate": False,
        "tx_id": tx_id,
        "claim_id": claim_id,
        "stock_id": int(stock_id),
        "lots": lots_n,
        "quantity": quantity,
        "price_paid": price,
        "buyer_balance": buyer_after,
        "claim_expires_at": _iso(now + timedelta(hours=CLAIM_RESERVATION_HOURS)),
        "message": f"Compra concluída! Resgate com /mercado em até {CLAIM_RESERVATION_HOURS}h.",
    }


# ── Retirada ─────────────────────────────────────────────────────────────────

def withdraw_stock(
    db: Session,
    steam_id: str,
    *,
    resource_id: Any = None,
    quantity: Any = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    steam_id = clean_steam_id(steam_id)
    request_id = clean_request_id(request_id)
    rid = None if resource_id in (None, "") else as_int(resource_id, "resource_id", minimum=1)
    qty_req = None if quantity in (None, "") else as_int(quantity, "quantity", minimum=1, maximum=MAX_STOCK_PER_RESOURCE)
    if qty_req is not None and rid is None:
        raise RVError("Informe resource_id para retirar uma quantidade específica", "invalid_input")

    def _claim_req_id(resource: int) -> str | None:
        return f"{request_id}:{resource}"[:64] if request_id else None

    try:
        q = select(T_STOCK).where(T_STOCK.c.steam_id == steam_id, T_STOCK.c.quantity > 0).with_for_update()
        if rid is not None:
            q = q.where(T_STOCK.c.resource_id == rid)
        rows = db.execute(q).all()
        if not rows:
            # Reexecução idempotente (mesmo request_id): devolve os claims já criados.
            if request_id:
                prev = db.execute(
                    select(T_CLAIM).where(
                        T_CLAIM.c.recipient_steam_id == steam_id,
                        T_CLAIM.c.kind == KIND_WITHDRAW,
                        T_CLAIM.c.request_id.like(f"{request_id}:%"),
                    )
                ).all()
                if prev:
                    return {"duplicate": True, "claims": [_claim_public(c) for c in prev]}
            raise RVError("Sem estoque para retirar", "insufficient_stock")

        catalog = {int(r.id): r for r in db.execute(select(T_CAT)).all()}
        now = _now()
        created_ids: list[int] = []
        withdrawn: list[dict[str, Any]] = []
        for stock in rows:
            res = catalog.get(int(stock.resource_id))
            if res is None:
                continue
            take = int(stock.quantity)
            if qty_req is not None:
                if qty_req > take:
                    raise RVError(f"Estoque insuficiente ({take})", "insufficient_stock")
                take = qty_req
            claim_req = _claim_req_id(int(stock.resource_id))
            if claim_req:
                dup = db.execute(
                    select(T_CLAIM.c.id).where(
                        T_CLAIM.c.recipient_steam_id == steam_id, T_CLAIM.c.request_id == claim_req
                    )
                ).first()
                if dup:
                    continue
            guard = db.execute(
                update(T_STOCK)
                .where(T_STOCK.c.id == stock.id, T_STOCK.c.quantity >= take)
                .values(quantity=T_STOCK.c.quantity - take, updated_at=now)
            )
            if getattr(guard, "rowcount", 0) != 1:
                raise RVError("O estoque mudou — tente novamente", "insufficient_stock")
            inserted = db.execute(
                insert(T_CLAIM).values(
                    **_new_claim_values(
                        kind=KIND_WITHDRAW,
                        recipient=steam_id,
                        seller=steam_id,
                        resource=res,
                        quantity=take,
                        tx_id=None,
                        request_id=claim_req,
                        now=now,
                    )
                )
            )
            created_ids.append(int(inserted.inserted_primary_key[0]))
            withdrawn.append({"resource_id": int(res.id), "name": res.name, "quantity": take})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise RVError("Retirada já registrada", "invalid_input", 409)
    except RVError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    claims = db.execute(select(T_CLAIM).where(T_CLAIM.c.id.in_(created_ids))).all() if created_ids else []
    for c in claims:
        _audit(
            db,
            "MARKET_RESOURCE_WITHDRAW",
            source="web",
            steam_id=steam_id,
            claim_id=int(c.id),
            metadata={"resource_id": int(c.resource_id), "quantity": int(c.quantity)},
        )
    return {
        "duplicate": False,
        "claims": [_claim_public(c) for c in claims],
        "withdrawn": withdrawn,
        "message": f"Retirada solicitada. Resgate com /mercado em até {CLAIM_RESERVATION_HOURS}h.",
    }


# ── Minha vitrine (overview) ─────────────────────────────────────────────────

def _history(db: Session, steam_id: str, limit: int = 50) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in db.execute(
        select(T_UP).where(T_UP.c.steam_id == steam_id, T_UP.c.status == UPLOAD_APPLIED).order_by(T_UP.c.id.desc()).limit(limit)
    ).all():
        events.append(
            {"type": "upload", "at": row.created_at, "quantity": int(row.total_quantity or 0), "label": "Envio do jogo"}
        )
    for row in db.execute(
        select(T_TX)
        .where(or_(T_TX.c.seller_steam_id == steam_id, T_TX.c.buyer_steam_id == steam_id))
        .order_by(T_TX.c.id.desc())
        .limit(limit)
    ).all():
        as_seller = row.seller_steam_id == steam_id
        events.append(
            {
                "type": "sale" if as_seller else "purchase",
                "at": row.created_at,
                "resource": row.resource_name,
                "lots": int(row.lots),
                "quantity": int(row.quantity),
                "amount": int(row.seller_credit if as_seller else row.price_paid),
                "status": row.status,
                "counterparty": row.buyer_steam_id if as_seller else row.seller_steam_id,
            }
        )
        if row.status == TX_REFUNDED and row.refunded_at is not None:
            events.append(
                {
                    "type": "refund",
                    "at": row.refunded_at,
                    "resource": row.resource_name,
                    "quantity": int(row.quantity),
                    "amount": int(row.seller_reversal or 0) if as_seller else int(row.refund_amount or 0),
                    "label": "Resgate expirado — reembolso" if not as_seller else "Resgate expirado — recurso voltou ao estoque",
                }
            )
    for row in db.execute(
        select(T_CLAIM)
        .where(T_CLAIM.c.recipient_steam_id == steam_id, T_CLAIM.c.kind == KIND_WITHDRAW)
        .order_by(T_CLAIM.c.id.desc())
        .limit(limit)
    ).all():
        events.append(
            {
                "type": "withdraw",
                "at": row.created_at,
                "resource": row.resource_name,
                "quantity": int(row.quantity),
                "status": row.status,
            }
        )
    events.sort(key=lambda e: e["at"] or datetime.min, reverse=True)
    out = events[:limit]
    for e in out:
        e["at"] = _iso(e["at"])
    return out


def my_overview(db: Session, steam_id: str) -> dict[str, Any]:
    steam_id = clean_steam_id(steam_id)
    catalog = {int(r.id): r for r in db.execute(select(T_CAT)).all()}
    stock_rows = db.execute(
        select(T_STOCK).where(T_STOCK.c.steam_id == steam_id).order_by(T_STOCK.c.updated_at.desc())
    ).all()
    stock = [
        _stock_to_public(s, catalog[int(s.resource_id)])
        for s in stock_rows
        if int(s.resource_id) in catalog and (int(s.quantity or 0) > 0 or s.lot_size)
    ]
    now = _now()
    pending = db.execute(
        select(T_CLAIM)
        .where(T_CLAIM.c.recipient_steam_id == steam_id, T_CLAIM.c.status.in_([CLAIM_PENDING, CLAIM_CLAIMED]))
        .order_by(T_CLAIM.c.claim_expires_at.asc())
    ).all()
    return {
        "stock": stock,
        "type_count": sum(1 for s in stock if s["quantity"] > 0),
        "max_types": get_max_types(db),
        "pending_claims": [_claim_public(c, now=now) for c in pending],
        "history": _history(db, steam_id),
        "catalog": list_catalog(db),
    }


# ── Claims (plugin) ──────────────────────────────────────────────────────────

def get_pending_claims(db: Session, steam_id: str) -> list[dict[str, Any]]:
    steam_id = clean_steam_id(steam_id)
    now = _now()
    rows = db.execute(
        select(T_CLAIM)
        .where(
            T_CLAIM.c.recipient_steam_id == steam_id,
            T_CLAIM.c.status == CLAIM_PENDING,
            T_CLAIM.c.claim_expires_at > now,
        )
        .order_by(T_CLAIM.c.id.asc())
    ).all()
    return [_claim_public(r, now=now) for r in rows]


def _claim_ids(raw: Any) -> list[int]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise RVError("claim_ids inválido", "invalid_input")
    out: list[int] = []
    for x in raw[:200]:
        if isinstance(x, bool):
            continue
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def claim_deliveries(db: Session, steam_id: str, claim_ids: Any) -> list[dict[str, Any]]:
    steam_id = clean_steam_id(steam_id)
    ids = _claim_ids(claim_ids)
    now = _now()
    q = select(T_CLAIM).where(T_CLAIM.c.recipient_steam_id == steam_id, T_CLAIM.c.status == CLAIM_PENDING)
    if ids:
        q = q.where(T_CLAIM.c.id.in_(ids))
    rows = db.execute(q).all()
    claimed: list[dict[str, Any]] = []
    try:
        for row in rows:
            if row.claim_expires_at <= now:
                raise RVError(
                    "Resgate expirado — o prazo de 24h terminou. Reembolso/devolução em processamento.",
                    "claim_expired",
                )
            res = db.execute(
                update(T_CLAIM)
                .where(T_CLAIM.c.id == row.id, T_CLAIM.c.status == CLAIM_PENDING)
                .values(status=CLAIM_CLAIMED, claimed_at=now, updated_at=now)
            )
            if getattr(res, "rowcount", 0) == 1:
                claimed.append(_claim_public(row, now=now) | {"status": CLAIM_CLAIMED})
        db.commit()
    except RVError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    for c in claimed:
        _audit(db, "MARKET_RESOURCE_CLAIM_CLAIMED", source="plugin", steam_id=steam_id, claim_id=c["claim_id"])
    return claimed


def release_claims(db: Session, steam_id: str, claim_ids: Any) -> list[dict[str, Any]]:
    steam_id = clean_steam_id(steam_id)
    ids = _claim_ids(claim_ids)
    if not ids:
        return []
    now = _now()
    released: list[dict[str, Any]] = []
    rows = db.execute(
        select(T_CLAIM).where(
            T_CLAIM.c.recipient_steam_id == steam_id, T_CLAIM.c.id.in_(ids), T_CLAIM.c.status == CLAIM_CLAIMED
        )
    ).all()
    for row in rows:
        res = db.execute(
            update(T_CLAIM)
            .where(T_CLAIM.c.id == row.id, T_CLAIM.c.status == CLAIM_CLAIMED)
            .values(status=CLAIM_PENDING, claimed_at=None, updated_at=now)
        )
        if getattr(res, "rowcount", 0) == 1:
            released.append({"claim_id": int(row.id)})
    db.commit()
    for r in released:
        _audit(db, "MARKET_RESOURCE_CLAIM_RELEASED", source="plugin", steam_id=steam_id, claim_id=r["claim_id"])
    return released


def mark_claim_delivered(db: Session, claim_id: Any, steam_id: str) -> dict[str, Any]:
    steam_id = clean_steam_id(steam_id)
    cid = as_int(claim_id, "claim_id", minimum=1)
    row = db.execute(select(T_CLAIM).where(T_CLAIM.c.id == cid)).first()
    if row is None:
        raise RVError("Claim não encontrado", "not_found", 404)
    if row.recipient_steam_id != steam_id:
        raise RVError("SteamID não corresponde", "invalid_input", 403)
    if row.status == CLAIM_DELIVERED:
        return {"claim_id": cid, "status": CLAIM_DELIVERED, "duplicate": True}
    if row.status in (CLAIM_REFUNDED, CLAIM_EXPIRED):
        raise RVError(
            "Resgate expirado e já processado (reembolso/devolução). Contate o suporte.", "claim_expired", 409
        )
    now = _now()
    res = db.execute(
        update(T_CLAIM)
        .where(T_CLAIM.c.id == cid, T_CLAIM.c.status.in_([CLAIM_CLAIMED, CLAIM_PENDING]))
        .values(status=CLAIM_DELIVERED, delivered_at=now, updated_at=now)
    )
    if getattr(res, "rowcount", 0) != 1:
        db.rollback()
        raise RVError("Estado do claim mudou — contate o suporte", "claim_expired", 409)
    db.commit()
    _audit(
        db,
        "MARKET_RESOURCE_CLAIM_DELIVERED",
        source="plugin",
        steam_id=steam_id,
        claim_id=cid,
        metadata={"resource_id": int(row.resource_id), "quantity": int(row.quantity), "kind": row.kind},
    )
    return {"claim_id": cid, "status": CLAIM_DELIVERED, "duplicate": False}


# ── Expiração / reembolso ────────────────────────────────────────────────────

def _expire_one(db: Session, claim_id: int, *, now: datetime) -> dict[str, Any] | None:
    from market_listings import _credit_points, _debit_points, _player_points

    grace_cutoff = now - timedelta(minutes=CLAIMED_EXPIRY_GRACE_MINUTES)
    claim = db.execute(select(T_CLAIM).where(T_CLAIM.c.id == claim_id).with_for_update()).first()
    if claim is None:
        return None
    if claim.status not in (CLAIM_PENDING, CLAIM_CLAIMED) or claim.claim_expires_at > now:
        return None
    if claim.status == CLAIM_CLAIMED and (claim.claimed_at is None or claim.claimed_at > grace_cutoff):
        return None  # plugin pode estar entregando agora

    new_status = CLAIM_REFUNDED if claim.kind == KIND_BUY else CLAIM_EXPIRED
    guard = db.execute(
        update(T_CLAIM)
        .where(T_CLAIM.c.id == claim_id, T_CLAIM.c.status == claim.status)
        .values(status=new_status, updated_at=now)
    )
    if getattr(guard, "rowcount", 0) != 1:
        db.rollback()
        return None

    result: dict[str, Any] = {"claim_id": claim_id, "kind": claim.kind, "refund_amount": 0}
    resource_id = int(claim.resource_id)
    buyer = claim.recipient_steam_id
    owner = claim.seller_steam_id or claim.recipient_steam_id
    refund = 0
    seller_debited = 0
    buyer_before = buyer_after = seller_before = seller_after = None
    tx = None

    if claim.kind == KIND_BUY and claim.tx_id is not None:
        tx = db.execute(select(T_TX).where(T_TX.c.id == claim.tx_id).with_for_update()).first()
    if tx is not None and tx.status == TX_COMPLETED:
        refund = int(tx.price_paid or 0)
        buyer_before = _player_points(db, buyer)
        seller_before = _player_points(db, owner)
        buyer_after = _credit_points(db, buyer, refund)
        reversal = min(_player_points(db, owner), int(tx.seller_credit or 0))
        if reversal > 0:
            seller_after = _debit_points(db, owner, reversal)
            seller_debited = reversal
        else:
            seller_after = seller_before
        db.execute(
            update(T_TX)
            .where(T_TX.c.id == tx.id, T_TX.c.status == TX_COMPLETED)
            .values(status=TX_REFUNDED, refund_amount=refund, seller_reversal=seller_debited, refunded_at=now)
        )
        result["refund_amount"] = refund

    # Devolve o recurso ao estoque do dono (sem limite de tipos nem teto de estoque).
    _add_stock(db, owner, resource_id, int(claim.quantity), cap=False)
    db.commit()
    result["returned_quantity"] = int(claim.quantity)
    result["owner"] = owner

    if claim.kind == KIND_BUY:
        _audit(
            db,
            "MARKET_RESOURCE_CLAIM_EXPIRED_REFUND",
            severity="WARN",
            source="scheduler",
            steam_id=buyer,
            counterparty_steam_id=owner,
            claim_id=claim_id,
            effective_price=refund,
            points_delta=refund,
            points_before=buyer_before,
            points_after=buyer_after,
            metadata={
                "tx_id": int(claim.tx_id) if claim.tx_id is not None else None,
                "refund_amount": refund,
                "seller_debited": seller_debited,
                "returned_quantity": int(claim.quantity),
                "resource_id": resource_id,
            },
        )
        if refund > 0:
            _ledger(
                db,
                channel="market",
                event_type="market_resource_refund_buyer",
                signed_delta=refund,
                idempotency_key=f"market:rescl:{claim_id}:buyer_refund",
                steam_id=buyer,
                counterparty_id=owner,
                source_table="market_resource_claims",
                source_id=str(claim_id),
            )
        if seller_debited > 0:
            _ledger(
                db,
                channel="market",
                event_type="market_resource_refund_seller",
                signed_delta=-seller_debited,
                idempotency_key=f"market:rescl:{claim_id}:seller_debit",
                steam_id=owner,
                counterparty_id=buyer,
                source_table="market_resource_claims",
                source_id=str(claim_id),
            )
    else:
        _audit(
            db,
            "MARKET_RESOURCE_CLAIM_EXPIRED_RETURN",
            severity="WARN",
            source="scheduler",
            steam_id=owner,
            claim_id=claim_id,
            metadata={"resource_id": resource_id, "returned_quantity": int(claim.quantity)},
        )
    return result


def expire_resource_claims(db: Session, *, batch_size: int = 50) -> dict[str, Any]:
    """Processa claims de recursos expirados (idempotente; commit por claim)."""
    now = _now()
    ids = [
        int(r[0])
        for r in db.execute(
            select(T_CLAIM.c.id)
            .where(T_CLAIM.c.status.in_([CLAIM_PENDING, CLAIM_CLAIMED]), T_CLAIM.c.claim_expires_at <= now)
            .order_by(T_CLAIM.c.claim_expires_at.asc())
            .limit(max(1, min(500, int(batch_size))))
        ).all()
    ]
    done: list[dict[str, Any]] = []
    for cid in ids:
        try:
            result = _expire_one(db, cid, now=now)
            if result:
                done.append(result)
            else:
                db.rollback()
        except Exception as exc:
            db.rollback()
            log.error("expire_resource_claims claim=%s falhou: %s", cid, exc)
    return {
        "processed": len(done),
        "buyer_refunds": [d for d in done if d["kind"] == KIND_BUY],
        "returned_to_stock": [d for d in done if d["kind"] == KIND_WITHDRAW],
    }
