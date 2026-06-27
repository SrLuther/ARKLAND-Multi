"""ArkShop Web Manager — backend com auth Steam, autorização admin e pedidos no DB."""
from __future__ import annotations

import base64
import functools
import hashlib
import json
import logging
import logging.config
import os
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from dotenv import load_dotenv

from cryptography.fernet import Fernet

from pix_payments import (
    PIX_PAYER_FORM,
    PayerValidationError,
    PixPaymentError,
    create_card_checkout_preference,
    create_pix_payment,
    extract_checkout_url,
    extract_pix_data,
    fetch_payment,
    map_mp_status,
    normalize_payer_input,
    parse_mp_error_message,
)
from flask import Flask, jsonify, make_response, redirect, request, send_from_directory, session
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from sqlalchemy import Boolean, DateTime, Float, Integer, LargeBinary, String, Text, UniqueConstraint, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, scoped_session, sessionmaker

from rcon_bridge import rcon_command as _rcon_send, rcon_test_connection as _rcon_test_connection

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from src.rcon_util import sanitize_rcon_password  # noqa: E402
from src.shop_integration import (  # noqa: E402
    apply_machine_server_registry,
    _collect_catalog_search_paths,
    _merge_arkland_server_entry,
    canonical_master_catalog_path,
    is_ephemeral_pyinstaller_path,
    is_webstore_catalog_path,
    load_plugin_config,
    merge_catalog_into_plugin_config,
    resolve_persistent_catalog_path,
    webstore_data_dir,
)

# ── Logging estruturado ───────────────────────────────────────────────────────

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "logging.Formatter",
            "fmt": '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}',
            "datefmt": "%Y-%m-%dT%H:%M:%SZ",
        },
        "plain": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%dT%H:%M:%SZ",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
        },
    },
    "root": {"level": "INFO", "handlers": ["console"]},
})

log = logging.getLogger("arkshop")

DEFAULT_SHOP_PUBLIC_URL = "https://arkland.com.br"


def _log(event: str, **kw: Any) -> None:
    parts = " ".join(f'{k}={json.dumps(v)}' for k, v in kw.items())
    log.info('"%s" %s', event, parts)


def _log_error(event: str, **kw: Any) -> None:
    parts = " ".join(f'{k}={json.dumps(v)}' for k, v in kw.items())
    log.error('"%s" %s', event, parts)


def _request_meta() -> tuple[str | None, str | None]:
    try:
        ip = get_remote_address()
        ua = (request.headers.get("User-Agent") or "")[:512]
        return ip, ua
    except Exception:
        return None, None


def _audit_event(
    event_type: str,
    *,
    severity: str = "info",
    source: str = "web",
    actor_type: str = "system",
    actor_steam_id: str | None = None,
    target_steam_id: str | None = None,
    order_id: str | None = None,
    server_id: str | None = None,
    item_type: str | None = None,
    item_id: str | None = None,
    amount: int | None = None,
    status_before: str | None = None,
    status_after: str | None = None,
    message: str | None = None,
    persist: bool = True,
    **payload: Any,
) -> None:
    """Grava evento estruturado no banco (se disponível) e no log de arquivo."""
    ip, ua = _request_meta()
    payload_clean = {k: v for k, v in payload.items() if v is not None}
    payload_str: str | None = None
    if payload_clean:
        try:
            raw = json.dumps(payload_clean, ensure_ascii=False, default=str)
            if len(raw) > 16384:
                payload_clean["truncated"] = True
                raw = json.dumps(payload_clean, ensure_ascii=False, default=str)[:16384]
            payload_str = raw
        except Exception:
            payload_str = str(payload_clean)[:16384]

    log_fn = _log_error if severity == "error" else _log
    log_fn(
        event_type,
        severity=severity,
        source=source,
        actor_type=actor_type,
        actor_steam_id=actor_steam_id,
        target_steam_id=target_steam_id,
        order_id=order_id,
        message=message,
        **payload_clean,
    )

    if not persist or not _db_ready() or _SessionLocal is None:
        return
    db = _SessionLocal()
    try:
        row = AuditEvent(
            event_type=event_type,
            severity=severity,
            source=source,
            actor_type=actor_type,
            actor_steam_id=actor_steam_id,
            target_steam_id=target_steam_id,
            order_id=order_id,
            server_id=server_id,
            item_type=item_type,
            item_id=item_id,
            amount=amount,
            status_before=status_before,
            status_after=status_after,
            message=message,
            payload_json=payload_str,
            ip_address=ip,
            user_agent=ua,
            created_at=_now(),
        )
        db.add(row)
        db.commit()
    except Exception as exc:
        db.rollback()
        _log_error("audit_persist_failed", event_type=event_type, error=str(exc))
    finally:
        db.close()


def _audit_row_dict(row: AuditEvent) -> dict[str, Any]:
    payload: Any = None
    if row.payload_json:
        try:
            payload = json.loads(row.payload_json)
        except Exception:
            payload = row.payload_json
    return {
        "id": row.id,
        "event_type": row.event_type,
        "severity": row.severity,
        "source": row.source,
        "actor_type": row.actor_type,
        "actor_steam_id": row.actor_steam_id,
        "target_steam_id": row.target_steam_id,
        "order_id": row.order_id,
        "server_id": row.server_id,
        "item_type": row.item_type,
        "item_id": row.item_id,
        "amount": row.amount,
        "status_before": row.status_before,
        "status_after": row.status_after,
        "message": row.message,
        "payload": payload,
        "ip_address": row.ip_address,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


# ── Paths (dev vs PyInstaller) ────────────────────────────────────────────────

def _bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def _data_dir() -> Path:
    return webstore_data_dir()


_BUNDLE_DIR = _bundle_dir()
_DATA_DIR = _data_dir()

# ── Load environment variables ────────────────────────────────────────────────

# Resolve .env na raiz do projeto (um nível acima de plugin/arkshop_web/)
_PROJECT_ROOT = _BUNDLE_DIR.parent.parent if not getattr(sys, "frozen", False) else _BUNDLE_DIR
_ENV_PATH = (_PROJECT_ROOT / ".env") if not getattr(sys, "frozen", False) else Path()
load_dotenv(dotenv_path=_ENV_PATH if _ENV_PATH.exists() else None)


# ── App setup ─────────────────────────────────────────────────────────────────

_CORS_ORIGINS = [
    "https://arkland.com.br",
    "https://www.arkland.com.br",
    r"http://localhost:\d+",
    r"http://127.0.0.1:\d+",
]

app = Flask(__name__, static_folder=str(_BUNDLE_DIR / "static"), static_url_path="")
CORS(app, origins=_CORS_ORIGINS, supports_credentials=True)

_DEFAULT_CONFIG_PATH = str(
    resolve_persistent_catalog_path(os.environ.get("ARKSHOP_CONFIG_PATH", "").strip())
)
_STATE_FILE = _DATA_DIR / "settings.json"
_PLAYERS_FILE = _DATA_DIR / "players.json"
_ADMIN_FILE = _DATA_DIR / "admin_steamids.json"
_ADMIN_EXAMPLE = _BUNDLE_DIR / "admin_steamids.example.json"
_SERVERS_FILE = _DATA_DIR / "servers.json"
_STEAMID64_RE = re.compile(r"^7656119\d{10}$")
_STEAM_OPENID_URL = "https://steamcommunity.com/openid/login"
_STEAM_CLAIMED_ID_RE = re.compile(r"^https?://steamcommunity\.com/openid/id/(\d+)$")

_DATABASE_URL = os.environ.get("ARKSHOP_DATABASE_URL", "").strip()
_STEAM_SESSION_REQUIRED_MESSAGE = "Faça login com Steam para continuar"
_ACTIVE_DATABASE_URL = ""

_RETRY_INTERVAL_SECONDS = int(os.environ.get("ARKSHOP_RETRY_INTERVAL", "60"))
_RETRY_BATCH_SIZE = int(os.environ.get("ARKSHOP_RETRY_BATCH", "20"))

# ── Security ─────────────────────────────────────────────────────────────────

# Secret key MUST come from environment in production / frozen exe
_is_production = os.environ.get("ARKSHOP_ENV", "").strip().lower() == "production"
_is_frozen = getattr(sys, "frozen", False)
_secret_from_env = os.environ.get("ARKSHOP_WEB_SECRET", "").strip()
if _secret_from_env:
    app.secret_key = _secret_from_env
elif _is_production or _is_frozen:
    log.error(
        "ARKSHOP_WEB_SECRET não definida — obrigatória em produção (ARKSHOP_ENV=production) "
        "ou ao executar o .exe empacotado."
    )
    sys.exit(1)
else:
    app.secret_key = "arkshop-web-dev-secret-change-me-in-prod"
    log.warning(
        "ARKSHOP_WEB_SECRET não definida! Usando secret de desenvolvimento. "
        "Defina a variável de ambiente ARKSHOP_WEB_SECRET em produção."
    )


def _ensure_admin_steamids_file() -> None:
    """Garante admin_steamids.json no diretório de dados (não no repositório)."""
    if _ADMIN_FILE.exists():
        return
    _ADMIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    legacy = _BUNDLE_DIR / "admin_steamids.json"
    if legacy.is_file() and legacy.resolve() != _ADMIN_FILE.resolve():
        try:
            _ADMIN_FILE.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
            log.info("admin_steamids migrado de %s para %s", legacy, _ADMIN_FILE)
            return
        except Exception as exc:
            log.warning("Falha ao migrar admin_steamids legado: %s", exc)
    if _ADMIN_EXAMPLE.is_file():
        _ADMIN_FILE.write_text(_ADMIN_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        _ADMIN_FILE.write_text("[]\n", encoding="utf-8")
    log.info("admin_steamids criado em %s — adicione seu SteamID64", _ADMIN_FILE)


_ensure_admin_steamids_file()

# API Key for CustomShop ↔ arkshop_web internal communication
# Must be set via environment variable ARKSHOP_API_KEY
_ARKSHOP_API_KEY = os.environ.get("ARKSHOP_API_KEY", "").strip()
_ENCRYPTED_PREFIX = "ENC:"
_SENSITIVE_SETTINGS_KEYS = ("rcon_password", "db_password", "mp_access_token", "cross_chat_discord_token")

_DEFAULT_POINT_PACKAGES: list[dict[str, Any]] = [
    {"id": "p500", "label": "500 Âmbares", "points": 500, "price_brl": 5.0},
    {"id": "p1200", "label": "1.200 Âmbares", "points": 1200, "price_brl": 10.0},
    {"id": "p3000", "label": "3.000 Âmbares", "points": 3000, "price_brl": 20.0},
    {"id": "p8000", "label": "8.000 Âmbares", "points": 8000, "price_brl": 45.0},
    {
        "id": "p8250",
        "label": "8.250 Âmbares — Kit VIP Ouro",
        "points": 8250,
        "price_brl": 75.0,
        "note": "Suficiente para Licença VIP Ouro (7.500) + Kit Ouro/alfa (750). Apenas Âmbar — VIP Diamante não incluído.",
    },
]

_AMBER_SINGULAR = "Âmbar"
_AMBER_PLURAL = "Âmbares"
_AMBER_ICON_URL = "/ambar.png"
_DEFAULT_PUBLIC_BRAND = "ARKLAND DONATIONS"

# Rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)


def _is_api_request() -> bool:
    return (request.path or "").startswith("/api/")


@app.errorhandler(HTTPException)
def _api_http_exception_handler(exc: HTTPException):
    """Rotas /api/* sempre respondem JSON — evita HTML do Werkzeug/limiter no fetch()."""
    if not _is_api_request():
        return exc
    msg = exc.description or exc.name or "Erro HTTP"
    if exc.code == 429:
        msg = "Muitas tentativas. Aguarde um momento e tente novamente."
    elif exc.code == 404:
        msg = "Endpoint não encontrado. Atualize a loja web se o erro persistir."
    return jsonify({"ok": False, "error": str(msg)}), exc.code


# Encryption key for sensitive settings (RCON passwords etc.)
# Derived from app.secret_key — same key = same encryption
def _get_fernet() -> Optional[Fernet]:
    """Create a Fernet instance from app.secret_key.
    Returns None if secret_key is too short or unset."""
    sk = app.secret_key
    if not sk or len(sk) < 32:
        return None
    # Derive a 32-byte key using SHA-256
    # app.secret_key can be str or bytes; normalise to bytes for sha256
    sk_bytes = sk.encode("utf-8") if isinstance(sk, str) else sk
    key_bytes = hashlib.sha256(sk_bytes).digest()
    key_b64 = base64.urlsafe_b64encode(key_bytes)
    return Fernet(key_b64)


def _encrypt_value(plaintext: str) -> str:
    """Encrypt a value using Fernet. Returns plaintext if encryption is unavailable."""
    if not plaintext:
        return ""
    f = _get_fernet()
    if not f:
        return plaintext
    try:
        return _ENCRYPTED_PREFIX + f.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    except Exception:
        return plaintext


def _decrypt_value(ciphertext: str) -> str:
    """Decrypt a value using Fernet. Returns original value on failure."""
    if not ciphertext:
        return ""
    if not ciphertext.startswith(_ENCRYPTED_PREFIX):
        return ciphertext
    f = _get_fernet()
    if not f:
        return ciphertext
    try:
        token = ciphertext[len(_ENCRYPTED_PREFIX):]
        return f.decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:
        return ciphertext


# ── Idempotency ─────────────────────────────────────────────────────────────

_used_idempotency_keys: dict[str, datetime] = {}
_IDEMPOTENCY_EXPIRE_SECONDS = 3600


def _check_idempotency(key: str) -> bool:
    """Returns True if this is the FIRST time this key is seen (not a duplicate).
    Returns False if the key was already used within the last hour."""
    if not key:
        return True  # no key provided — allow (no idempotency protection)
    now = _now()
    # Clean expired keys
    expired = [k for k, ts in _used_idempotency_keys.items()
               if (now - ts).total_seconds() > _IDEMPOTENCY_EXPIRE_SECONDS]
    for k in expired:
        _used_idempotency_keys.pop(k, None)
    if key in _used_idempotency_keys:
        return False
    _used_idempotency_keys[key] = now
    return True


# ── API Key auth ────────────────────────────────────────────────────────────

def api_key_required(allow_admin_session: bool = False) -> Callable[..., Any]:
    """Validates X-API-Key header for CustomShop ↔ arkshop_web communication.
    
    Args:
        allow_admin_session: If True, also allow admin steam_id in session (for browser tests).
                            If False, ONLY API key auth is accepted (production).
    """
    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            api_key = request.headers.get("X-API-Key", "").strip()
            
            # Check API key first (strict)
            if api_key and _ARKSHOP_API_KEY and api_key == _ARKSHOP_API_KEY:
                return f(*args, **kwargs)
            
            # Optionally allow admin via session (for development/testing)
            if allow_admin_session:
                steam_id = _steam_id_from_session()
                if steam_id and _is_admin_steamid(steam_id):
                    return f(*args, **kwargs)
            
            # Reject
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        return decorated_function
    return decorator


# ── ORM ───────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    steam_id: Mapped[str] = mapped_column(String(32), index=True)
    server_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    item_type: Mapped[str] = mapped_column(String(32), default="shop")
    item_id: Mapped[str] = mapped_column(String(128), index=True)
    amount: Mapped[int] = mapped_column(Integer, default=1)
    points_spent: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="PENDENTE", index=True)
    original_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    contested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class OrderAttempt(Base):
    __tablename__ = "order_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    command: Mapped[str] = mapped_column(Text)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


class Dispute(Base):
    __tablename__ = "disputes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    steam_id: Mapped[str] = mapped_column(String(32), index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="ABERTO", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Rebuy(Base):
    __tablename__ = "rebuys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    steam_id: Mapped[str] = mapped_column(String(32), index=True)
    original_order_id: Mapped[str] = mapped_column(String(64), index=True)
    new_order_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ShopAdmin(Base):
    __tablename__ = "shop_admins"

    steam_id: Mapped[str] = mapped_column(String(32), primary_key=True)


class StoreUser(Base):
    """Conta web — criada no primeiro login Steam; base do painel admin de jogadores."""

    __tablename__ = "store_users"

    steam_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    site_access_blocked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    ban_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PointPayment(Base):
    __tablename__ = "point_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payment_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    mp_payment_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    steam_id: Mapped[str] = mapped_column(String(32), index=True)
    package_id: Mapped[str] = mapped_column(String(64))
    amount_brl: Mapped[float] = mapped_column(Float, default=0.0)
    points: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="PENDENTE", index=True)
    pix_qr_base64: Mapped[str | None] = mapped_column(Text, nullable=True)
    pix_copy_paste: Mapped[str | None] = mapped_column(Text, nullable=True)
    payer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_method: Mapped[str] = mapped_column(String(16), default="pix", index=True)
    credited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="info")
    source: Mapped[str] = mapped_column(String(32), default="web")
    actor_type: Mapped[str] = mapped_column(String(16), default="system")
    actor_steam_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    target_steam_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    server_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    item_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    item_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    amount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status_before: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status_after: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


class AdminReissue(Base):
    __tablename__ = "admin_reissues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_steam_id: Mapped[str] = mapped_column(String(32), index=True)
    player_steam_id: Mapped[str] = mapped_column(String(32), index=True)
    original_order_id: Mapped[str] = mapped_column(String(64), index=True)
    new_order_id: Mapped[str] = mapped_column(String(64), index=True)
    reason: Mapped[str] = mapped_column(Text)
    force_reset: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class MarketSpecies(Base):
    __tablename__ = "market_species"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    species_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    catalog_item_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    blueprint_path: Mapped[str] = mapped_column(String(512), default="")
    reference_level: Mapped[int] = mapped_column(Integer, default=1)
    root_value: Mapped[int] = mapped_column(Integer, default=0)
    tier: Mapped[str] = mapped_column(String(8), default="B")
    breeding_difficulty: Mapped[str | None] = mapped_column(String(32), nullable=True)
    breeding_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="PRE_REGISTERED", index=True)
    shop_price_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class MarketSpeciesStatMultiplier(Base):
    __tablename__ = "market_species_stat_multipliers"
    __table_args__ = (
        UniqueConstraint("species_id", "stat_key", name="uq_market_species_stat"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    species_id: Mapped[int] = mapped_column(Integer, index=True)
    stat_key: Mapped[str] = mapped_column(String(32))
    multiplier: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class MarketSpeciesAlias(Base):
    """Variantes de loja/blueprint que compartilham a mesma economia (ex.: Rex Tek → rex)."""
    __tablename__ = "market_species_aliases"
    __table_args__ = (
        UniqueConstraint("catalog_item_id", name="uq_market_species_alias_catalog"),
        UniqueConstraint("blueprint_norm", name="uq_market_species_alias_bp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    species_id: Mapped[int] = mapped_column(Integer, index=True)
    catalog_item_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    blueprint_path: Mapped[str] = mapped_column(String(512), default="")
    blueprint_norm: Mapped[str] = mapped_column(String(512), default="", index=True)
    variant_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class MarketPlayerProfile(Base):
    __tablename__ = "market_player_profile"

    steam_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    market_display_name: Mapped[str] = mapped_column(String(32))
    name_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    commerce_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class MarketCryopodVault(Base):
    __tablename__ = "market_cryopod_vault"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_steam_id: Mapped[str] = mapped_column(String(32), index=True)
    item_blob: Mapped[bytes] = mapped_column(LargeBinary)
    blob_hash: Mapped[str] = mapped_column(String(64), index=True)
    metadata_json: Mapped[str] = mapped_column(Text)
    species_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    market_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class MarketListing(Base):
    __tablename__ = "market_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vault_id: Mapped[int] = mapped_column(Integer)
    seller_steam_id: Mapped[str] = mapped_column(String(32), index=True)
    species_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    price_mode: Mapped[str] = mapped_column(String(16), default="ABSOLUTE")
    price_absolute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_offset_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    computed_base_value: Mapped[int] = mapped_column(Integer, default=0)
    effective_price: Mapped[int] = mapped_column(Integer, default=0)
    buyer_steam_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    market_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dino_display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    custom_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    category: Mapped[str | None] = mapped_column(String(16), nullable=True)
    custom_description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    stat_health: Mapped[int] = mapped_column(Integer, default=0)
    stat_melee: Mapped[int] = mapped_column(Integer, default=0)
    stat_weight: Mapped[int] = mapped_column(Integer, default=0)
    stat_stamina: Mapped[int] = mapped_column(Integer, default=0)
    stat_oxygen: Mapped[int] = mapped_column(Integer, default=0)
    stat_food: Mapped[int] = mapped_column(Integer, default=0)
    stat_speed: Mapped[int] = mapped_column(Integer, default=0)
    mutations_male: Mapped[int] = mapped_column(Integer, default=0)
    mutations_female: Mapped[int] = mapped_column(Integer, default=0)
    dino_level: Mapped[int] = mapped_column(Integer, default=0)
    imprint_pct: Mapped[float] = mapped_column(Float, default=0.0)
    is_female: Mapped[bool] = mapped_column(Boolean, default=False)
    is_neutered: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MarketTransaction(Base):
    __tablename__ = "market_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(Integer, index=True)
    buyer_steam_id: Mapped[str] = mapped_column(String(32), index=True)
    seller_steam_id: Mapped[str] = mapped_column(String(32))
    price_paid: Mapped[int] = mapped_column(Integer, default=0)
    base_value_at_sale: Mapped[int] = mapped_column(Integer, default=0)
    fee_amount: Mapped[int] = mapped_column(Integer, default=0)
    buyer_points_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    buyer_points_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seller_points_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seller_points_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class MarketClaim(Base):
    __tablename__ = "market_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listing_id: Mapped[int] = mapped_column(Integer, index=True)
    recipient_steam_id: Mapped[str] = mapped_column(String(32), index=True)
    claim_type: Mapped[str] = mapped_column(String(32), default="BUYER")
    status: Mapped[str] = mapped_column(String(32), default="PENDENTE", index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claim_reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    claim_status: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)


class MarketAuditEvent(Base):
    __tablename__ = "market_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="INFO")
    steam_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    counterparty_steam_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    market_display_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    listing_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    vault_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    claim_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blob_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    computed_base_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    effective_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points_before: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parser_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    plugin_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    web_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="web")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


# ── DB setup ──────────────────────────────────────────────────────────────────

_ENGINE: Any = None
_SessionLocal: Any = None  # set by _configure_database(); None only before first DB config


def _safe_db_log_fields(url: str) -> dict[str, Any]:
    """Extrai host/database para log sem expor credenciais."""
    s = (url or "").strip()
    if not s:
        return {}
    try:
        after_at = s.split("@", 1)[1] if "@" in s else s
        host_part, _, path_part = after_at.partition("/")
        host_port = host_part.split("?")[0]
        if ":" in host_port:
            host, _, port_s = host_port.rpartition(":")
            port = int(port_s) if port_s.isdigit() else None
        else:
            host, port = host_port, None
        db_name = path_part.split("?")[0] if path_part else None
        out: dict[str, Any] = {}
        if host:
            out["host"] = host
        if port:
            out["port"] = port
        if db_name:
            out["database"] = db_name
        return out
    except Exception:
        return {"configured": True}


def _build_database_url_from_settings(settings: dict[str, Any]) -> str:
    explicit_url = str(settings.get("database_url", "")).strip()
    if explicit_url:
        return explicit_url

    host = str(settings.get("db_host", "")).strip()
    name = str(settings.get("db_name", "")).strip()
    user = str(settings.get("db_user", "")).strip()
    password = str(settings.get("db_password", "")).strip()
    port = int(settings.get("db_port", 3306) or 3306)
    if not host or not name or not user:
        return ""

    user_q = urllib.parse.quote_plus(user)
    pass_q = urllib.parse.quote_plus(password)
    return f"mysql+pymysql://{user_q}:{pass_q}@{host}:{port}/{name}?charset=utf8mb4"


def _load_state_settings_snapshot() -> dict[str, Any]:
    if not _STATE_FILE.exists():
        return {}
    try:
        raw = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _resolve_database_url(settings: dict[str, Any] | None = None) -> str:
    # Se settings foram explicitamente fornecidas, tenta construir a URL a partir delas primeiro.
    # Isso garante que 'save_settings' use as novas credenciais salvas, não a env var antiga.
    if settings is not None:
        url_from_settings = _build_database_url_from_settings(settings)
        if url_from_settings:
            return url_from_settings
    # Fallback: env var de ambiente (definida no início do processo)
    if _DATABASE_URL:
        return _DATABASE_URL
    # Último fallback: lê settings do disco
    if settings is None:
        settings = _load_state_settings_snapshot()
    return _build_database_url_from_settings(settings)


def _db_table_exists(engine: Any, table_name: str) -> bool:
    try:
        from sqlalchemy import inspect

        return table_name in set(inspect(engine).get_table_names())
    except Exception:
        return False


_STEAM_ID_COLLATION = "utf8mb4_unicode_ci"

# Colunas steam_id usadas em JOINs/comparações entre tabelas (legado vs SQLAlchemy).
_STEAM_ID_VARCHAR_COLUMNS: tuple[tuple[str, str], ...] = (
    ("store_users", "steam_id"),
    ("players", "steam_id"),
    ("market_player_profile", "steam_id"),
    ("orders", "steam_id"),
    ("point_payments", "steam_id"),
    ("player_entitlements", "steam_id"),
    ("shop_admins", "steam_id"),
    ("rebuys", "steam_id"),
    ("disputes", "steam_id"),
    ("market_cryopod_vault", "seller_steam_id"),
    ("market_listings", "seller_steam_id"),
    ("market_listings", "buyer_steam_id"),
    ("market_transactions", "buyer_steam_id"),
    ("market_transactions", "seller_steam_id"),
    ("market_claims", "recipient_steam_id"),
    ("market_audit_events", "steam_id"),
    ("market_audit_events", "counterparty_steam_id"),
)


def _steam_id_on_sql(left: str, right: str, *, mysql: bool = True) -> str:
    """Comparação steam_id segura quando collations divergem (general_ci vs unicode_ci)."""
    if not mysql:
        return f"{left} = {right}"
    coll = _STEAM_ID_COLLATION
    return f"{left} COLLATE {coll} = {right} COLLATE {coll}"


def _ensure_steam_id_collation(engine: Any) -> None:
    """Normaliza collation de colunas steam_id para evitar erro 1267 em JOINs MySQL."""
    if "mysql" not in str(engine.url).lower():
        return
    changed = 0
    with engine.connect() as conn:
        for table, column in _STEAM_ID_VARCHAR_COLUMNS:
            if not _db_table_exists(engine, table):
                continue
            row = conn.execute(
                text(f"SHOW FULL COLUMNS FROM `{table}` LIKE :col"),
                {"col": column},
            ).fetchone()
            if row is None:
                continue
            col_type = str(row[1] or "")
            collation = str(row[2] or "")
            null_flag = str(row[3] or "")
            key_flag = str(row[4] or "")
            if not col_type.lower().startswith("varchar") or collation == _STEAM_ID_COLLATION:
                continue
            null_sql = "NULL" if null_flag == "YES" else "NOT NULL"
            key_sql = " PRIMARY KEY" if key_flag == "PRI" else ""
            conn.execute(
                text(
                    f"ALTER TABLE `{table}` MODIFY `{column}` {col_type} "
                    f"CHARACTER SET utf8mb4 COLLATE {_STEAM_ID_COLLATION} "
                    f"{null_sql}{key_sql}"
                )
            )
            changed += 1
        if changed:
            conn.commit()
            log.info(
                "steam_id: %s coluna(s) normalizadas para %s",
                changed,
                _STEAM_ID_COLLATION,
            )


def _ensure_store_users_schema(engine: Any) -> None:
    """Garante store_users e colunas usadas pelo painel admin de jogadores."""
    is_mysql = "mysql" in str(engine.url).lower()
    if not _db_table_exists(engine, "store_users"):
        Base.metadata.create_all(bind=engine, tables=[StoreUser.__table__])
        return
    if not is_mysql:
        return
    with engine.connect() as conn:
        cols = {
            str(row[0])
            for row in conn.execute(text("SHOW COLUMNS FROM `store_users`")).fetchall()
        }
        alters: list[str] = []
        if "site_access_blocked" not in cols:
            alters.append(
                "ADD COLUMN `site_access_blocked` TINYINT(1) NOT NULL DEFAULT 0"
            )
        if "ban_reason" not in cols:
            alters.append("ADD COLUMN `ban_reason` TEXT NULL")
        if "last_login_at" not in cols:
            alters.append("ADD COLUMN `last_login_at` DATETIME NULL")
        if "display_name" not in cols:
            alters.append("ADD COLUMN `display_name` VARCHAR(128) NULL")
        if "created_at" not in cols:
            alters.append(
                "ADD COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
            )
        for fragment in alters:
            conn.execute(text(f"ALTER TABLE `store_users` {fragment}"))
        if alters:
            conn.commit()
            log.info("store_users: colunas do painel admin adicionadas (%s)", len(alters))


def _migrate_schema(engine: Any) -> None:
    """Alinha schema MySQL com os modelos SQLAlchemy (incl. setup_db.sql legado)."""
    global _ENTITLEMENTS_SCHEMA_READY
    is_mysql = "mysql" in str(engine.url).lower()
    if not is_mysql:
        Base.metadata.create_all(bind=engine)
        with engine.connect() as conn:
            conn.execute(text(
                "CREATE TABLE IF NOT EXISTS players ("
                "  steam_id VARCHAR(20) PRIMARY KEY NOT NULL,"
                "  points INTEGER NOT NULL DEFAULT 0,"
                "  kits TEXT DEFAULT '{}'"
                ")"
            ))
            conn.commit()
        try:
            from market_migrate import ensure_market_schema

            ensure_market_schema(engine, bootstrap=False)
        except Exception as exc:
            log.warning("Mercado (sqlite dev): migrate falhou: %s", exc)
        with engine.connect() as conn:
            conn.execute(text(_entitlements_ddl_sqlite()))
            conn.commit()
        _ENTITLEMENTS_SCHEMA_READY = True
        _ensure_store_users_schema(engine)
        _ensure_steam_id_collation(engine)
        _backfill_store_users(engine)
        return
    with engine.connect() as conn:
        tbl_row = conn.execute(text("SHOW TABLES LIKE 'orders'")).fetchone()
        if tbl_row is not None:
            order_id_row = conn.execute(text("SHOW COLUMNS FROM `orders` LIKE 'order_id'")).fetchone()
            id_row = conn.execute(text("SHOW COLUMNS FROM `orders` LIKE 'id'")).fetchone()
            if order_id_row is None:
                log.warning("Schema antigo detectado (orders sem order_id) — recriando tabelas")
                conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
                for tbl in ("order_attempts", "rebuys", "disputes", "point_payments", "orders"):
                    conn.execute(text(f"DROP TABLE IF EXISTS `{tbl}`"))
                conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
                conn.commit()
            elif id_row is None:
                log.warning("Schema legado (orders.order_id como PK, sem id) — migrando")
                conn.execute(text("ALTER TABLE `orders` DROP PRIMARY KEY"))
                conn.execute(text(
                    "ALTER TABLE `orders` ADD COLUMN `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST"
                ))
                idx_rows = conn.execute(text(
                    "SHOW INDEX FROM `orders` WHERE Column_name = 'order_id' AND Non_unique = 0"
                )).fetchall()
                if not idx_rows:
                    conn.execute(text(
                        "ALTER TABLE `orders` ADD UNIQUE INDEX `ix_orders_order_id` (`order_id`)"
                    ))
                conn.commit()
        pp_row = conn.execute(text("SHOW TABLES LIKE 'point_payments'")).fetchone()
        if pp_row is not None:
            payer_col = conn.execute(text(
                "SHOW COLUMNS FROM `point_payments` LIKE 'payer_email'"
            )).fetchone()
            if payer_col is None:
                log.warning("Migrando point_payments — adicionando payer_email")
                conn.execute(text(
                    "ALTER TABLE `point_payments` ADD COLUMN `payer_email` VARCHAR(255) NULL"
                ))
                conn.commit()
            pm_col = conn.execute(text(
                "SHOW COLUMNS FROM `point_payments` LIKE 'payment_method'"
            )).fetchone()
            if pm_col is None:
                log.warning("Migrando point_payments — adicionando payment_method")
                conn.execute(text(
                    "ALTER TABLE `point_payments` ADD COLUMN `payment_method` VARCHAR(16) NOT NULL DEFAULT 'pix'"
                ))
                conn.execute(text(
                    "UPDATE `point_payments` SET `payment_method` = 'card' "
                    "WHERE `pix_copy_paste` IS NULL AND `pix_qr_base64` IS NULL"
                ))
                conn.commit()
        orders_row = conn.execute(text("SHOW TABLES LIKE 'orders'")).fetchone()
        if orders_row is not None:
            pts_col = conn.execute(text(
                "SHOW COLUMNS FROM `orders` LIKE 'points_spent'"
            )).fetchone()
            if pts_col is None:
                log.warning("Migrando orders — adicionando points_spent")
                conn.execute(text(
                    "ALTER TABLE `orders` ADD COLUMN `points_spent` INT NOT NULL DEFAULT 0"
                ))
                conn.commit()
        conn.execute(text(_entitlements_ddl_mysql()))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    _ENTITLEMENTS_SCHEMA_READY = True
    _ensure_store_users_schema(engine)
    _ensure_steam_id_collation(engine)
    _backfill_store_users(engine)
    try:
        from market_migrate import ensure_market_schema

        ensure_market_schema(engine, bootstrap=True)
        _ensure_steam_id_collation(engine)
    except Exception as exc:
        log.warning("Mercado: migrate falhou (será retentado pelo watcher): %s", exc)
    try:
        from cross_chat_service import ensure_cross_chat_schema

        ensure_cross_chat_schema(engine)
    except Exception as exc:
        log.warning("CrossChat: migrate falhou: %s", exc)


_db_reconnect_thread: threading.Thread | None = None
_db_reconnect_stop   = threading.Event()


def _start_db_reconnect_watcher() -> None:
    """Inicia um thread que fica tentando migrate_schema a cada 5 s até ter sucesso."""
    global _db_reconnect_thread

    if _db_reconnect_thread is not None and _db_reconnect_thread.is_alive():
        return  # já existe um watcher ativo

    _db_reconnect_stop.clear()

    def _watcher() -> None:
        log.info("DB reconnect watcher iniciado — tentando a cada 5 s…")
        while not _db_reconnect_stop.wait(5):
            engine = _ENGINE
            if engine is None:
                continue
            try:
                _migrate_schema(engine)
                log.info("DB reconnect watcher: schema OK — encerrando")
                break
            except Exception as exc:
                log.debug("DB reconnect watcher: ainda sem conexão (%s)", exc)

    _db_reconnect_thread = threading.Thread(
        target=_watcher, name="arkshop-db-reconnect", daemon=True
    )
    _db_reconnect_thread.start()


def _configure_database(url: str) -> None:
    global _ENGINE, _SessionLocal, _ACTIVE_DATABASE_URL, _ENTITLEMENTS_SCHEMA_READY

    normalized = (url or "").strip()
    if normalized == _ACTIVE_DATABASE_URL:
        return

    # Para o watcher de reconexão da URL anterior (se houver)
    _db_reconnect_stop.set()

    if _SessionLocal is not None:
        _SessionLocal.remove()
    if _ENGINE is not None:
        _ENGINE.dispose()

    _ENGINE = None
    _SessionLocal = None
    _ACTIVE_DATABASE_URL = ""
    _ENTITLEMENTS_SCHEMA_READY = False

    if not normalized:
        return

    connect_args: dict[str, Any] = {}
    if "mysql" in normalized.lower():
        connect_args = {"connect_timeout": 5, "read_timeout": 8, "write_timeout": 8}

    engine = create_engine(
        normalized,
        future=True,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
        pool_timeout=8,
        connect_args=connect_args,
    )
    session_local = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True))

    # Registra o DB como "configurado" ANTES de create_all.
    # Assim _db_ready() retorna True mesmo se o MariaDB estiver offline no boot;
    # as queries falharão com erro de conexão (não "Banco não configurado").
    _ENGINE = engine
    _SessionLocal = session_local
    _ACTIVE_DATABASE_URL = normalized
    _log("db_configured", **_safe_db_log_fields(normalized))

    if os.environ.get("ARKSHOP_SYNC_DB_MIGRATE") == "1":
        try:
            _migrate_schema(engine)
            log.info("DB schema migrate concluído (sync)")
        except Exception as exc:
            log.warning(
                "DB schema setup falhou (%s): %s",
                _safe_db_log_fields(normalized),
                exc,
            )
        return

    def _migrate_async() -> None:
        try:
            _migrate_schema(engine)
            log.info("DB schema migrate concluído")
        except Exception as exc:
            log.warning(
                "DB schema setup falhou (%s): %s — background thread tentará reconectar",
                _safe_db_log_fields(normalized),
                exc,
            )
            _start_db_reconnect_watcher()

    threading.Thread(target=_migrate_async, daemon=True, name="arkshop-db-migrate").start()


_DB_INIT_LOCK = threading.Lock()
_DB_INITIALIZED = False
_DB_BOOT_THREAD: threading.Thread | None = None
_ENTITLEMENTS_SCHEMA_LOCK = threading.Lock()
_ENTITLEMENTS_SCHEMA_READY = False

_HEALTH_DB_CACHE: dict[str, Any] = {
    "reachable": None,
    "checked_at": 0.0,
    "ping_inflight": False,
}
_HEALTH_DB_CACHE_TTL = 5.0
_HEALTH_DB_PING_TIMEOUT = 2.0
_ADMIN_DB_QUERY_TIMEOUT = 2.0


def _kick_background_db_init() -> None:
    """Inicia configuração do DB em thread — nunca bloqueia respostas HTTP."""
    global _DB_BOOT_THREAD
    if _DB_INITIALIZED:
        return
    if _DB_BOOT_THREAD is not None and _DB_BOOT_THREAD.is_alive():
        return

    def _boot() -> None:
        try:
            _initialize_database_if_needed()
        except Exception as exc:
            log.warning("DB background boot failed: %s", exc)

    _DB_BOOT_THREAD = threading.Thread(target=_boot, name="arkshop-db-boot", daemon=True)
    _DB_BOOT_THREAD.start()


def _initialize_database_if_needed() -> None:
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return
    if _db_ready() and (_ACTIVE_DATABASE_URL or _DATABASE_URL):
        _DB_INITIALIZED = True
        return
    with _DB_INIT_LOCK:
        if _DB_INITIALIZED:
            return
        if _db_ready() and (_ACTIVE_DATABASE_URL or _DATABASE_URL):
            _DB_INITIALIZED = True
            return
        try:
            startup_settings = _load_state_settings_snapshot()
            for key in _SENSITIVE_SETTINGS_KEYS:
                if key in startup_settings and startup_settings[key]:
                    try:
                        startup_settings[key] = _decrypt_value(startup_settings[key])
                    except Exception:
                        pass
            startup_url = (
                _build_database_url_from_settings(startup_settings)
                or _DATABASE_URL
                or f"sqlite:///{_DATA_DIR / 'orders.db'}"
            )
            _configure_database(startup_url)
            _DB_INITIALIZED = True
        except Exception as exc:
            log.warning("DB lazy initialization failed: %s", exc)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _db_ready() -> bool:
    return _SessionLocal is not None


def _db_session_factory():
    """Sessão SQLAlchemy atual — usado por market_routes (não capturar _SessionLocal na importação)."""
    return _SessionLocal()


def _get_db_session():
    """Get a database session, or None if not ready."""
    if _SessionLocal is not None:
        return _SessionLocal()
    return None


def _require_db():
    if not _db_ready():
        _kick_background_db_init()
        _initialize_database_if_needed()
    if not _db_ready():
        return jsonify({
            "ok": False,
            "error": "Banco não configurado. Configure as credenciais em Configurações → DB.",
            "db_offline": True,
        }), 503
    return None


_BOOT_SKIP_EXACT = frozenset({"/", "/favicon.ico"})
_BOOT_SKIP_PREFIXES = ("/api/health", "/api/auth/me", "/static/", "/logo")


def _ensure_runtime_initialized_before_request() -> None:
    """Nunca bloqueia em migrate/conexão MySQL — DB sobe em background."""
    path = request.path or ""
    if path in _BOOT_SKIP_EXACT or any(path.startswith(p) for p in _BOOT_SKIP_PREFIXES):
        return
    _initialize_scheduler_if_needed()
    _kick_background_db_init()


app.before_request(_ensure_runtime_initialized_before_request)


@app.teardown_appcontext
def _teardown_db_session(_exc: BaseException | None = None) -> None:
    """Libera scoped_session por request — evita vazamento de conexões entre threads Flask."""
    if _SessionLocal is not None:
        _SessionLocal.remove()


def _resolve_settings_catalog_path(configured: str = "") -> str:
    """Mestre canônico único — migra WEBSTORE/_MEIPASS legados."""
    raw = (configured or os.environ.get("ARKSHOP_CONFIG_PATH", "") or "").strip()
    if is_ephemeral_pyinstaller_path(raw) or is_webstore_catalog_path(raw):
        raw = ""
    return str(resolve_persistent_catalog_path(raw or canonical_master_catalog_path()))


def _load_settings() -> Dict[str, Any]:
    if _STATE_FILE.exists():
        try:
            data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            # Decrypt sensitive fields
            for key in _SENSITIVE_SETTINGS_KEYS:
                if key in data and isinstance(data[key], str):
                    data[key] = _decrypt_value(data[key])
            cp = str(data.get("config_path") or "").strip()
            canonical = _resolve_settings_catalog_path(cp)
            if cp != canonical:
                data["config_path"] = canonical
                _save_settings(data)
            return data
        except Exception:
            pass
    return {
        "config_path": _resolve_settings_catalog_path(_DEFAULT_CONFIG_PATH),
        "rcon_host": "127.0.0.1",
        "rcon_port": 27020,
        "rcon_password": "",
        "delivery_command_template": "Shop.Deliver {steam_id} {item_id} {amount}",
        "delivery_mode": "plugin",
        "server_id": "default",
        "retry_max_attempts": 10,
        "database_url": "",
        "db_host": "",
        "db_port": 3306,
        "db_name": "arkland_shop",
        "db_user": "",
        "db_password": "",
        "point_packages": _DEFAULT_POINT_PACKAGES,
        "mp_access_token": "",
        "mp_sandbox": False,
    }


def _save_settings(data: Dict[str, Any]) -> None:
    safe_data = data.copy()
    cp = str(safe_data.get("config_path") or "").strip()
    safe_data["config_path"] = _resolve_settings_catalog_path(cp)
    # Encrypt sensitive fields
    for key in _SENSITIVE_SETTINGS_KEYS:
        if key in safe_data:
            safe_data[key] = _encrypt_value(str(safe_data[key]))
    _STATE_FILE.write_text(json.dumps(safe_data, indent=2, ensure_ascii=False), encoding="utf-8")


def _is_valid_steamid64(value: str) -> bool:
    return bool(_STEAMID64_RE.match(value.strip()))


def _load_players() -> list[Dict[str, str]]:
    if not _PLAYERS_FILE.exists():
        return []
    try:
        data = json.loads(_PLAYERS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [p for p in data if isinstance(p, dict)]
    except Exception:
        pass
    return []


def _save_players(players: list[Dict[str, str]]) -> None:
    players_sorted = sorted(players, key=lambda p: ((p.get("name") or "").lower(), p.get("steam_id") or ""))
    _PLAYERS_FILE.write_text(json.dumps(players_sorted, indent=2, ensure_ascii=False), encoding="utf-8")


def _resolve_player_display_name(
    steam_id: str,
    *,
    store_name: str | None = None,
    market_name: str | None = None,
) -> str:
    for candidate in (store_name, market_name):
        if candidate and str(candidate).strip():
            return str(candidate).strip()[:128]
    for p in _load_players():
        if str(p.get("steam_id", "")).strip() == steam_id:
            nm = str(p.get("name") or "").strip()
            if nm:
                return nm[:128]
    return steam_id


def _touch_store_user_login(steam_id: str) -> None:
    """Registra ou atualiza conta web no login Steam."""
    if not _db_ready() or not _is_valid_steamid64(steam_id):
        return
    db = _SessionLocal()
    try:
        now = _now()
        row = db.get(StoreUser, steam_id)
        market_name: str | None = None
        try:
            prof = _safe_market_profile(db, steam_id)
            if prof and (prof.market_display_name or "").strip():
                market_name = str(prof.market_display_name).strip()
        except Exception:
            market_name = None
        if row is None:
            row = StoreUser(
                steam_id=steam_id,
                display_name=_resolve_player_display_name(steam_id, market_name=market_name),
                last_login_at=now,
            )
            db.add(row)
        else:
            row.last_login_at = now
            if market_name and not (row.display_name or "").strip():
                row.display_name = market_name
        db.commit()
    except Exception as exc:
        db.rollback()
        _log_error("touch_store_user_login", steam_id=steam_id, error=str(exc))
    finally:
        db.close()


def _backfill_store_users(engine: Any) -> None:
    """Popula store_users a partir de perfis, saldos e pedidos existentes (uma vez)."""
    try:
        with engine.connect() as conn:
            existing = conn.execute(text("SELECT COUNT(*) FROM store_users")).scalar() or 0
            if int(existing) > 0:
                return
    except Exception:
        return

    db = _SessionLocal()
    try:
        now = _now()
        steam_ids: set[str] = set()
        for row in db.execute(text("SELECT steam_id FROM players")).fetchall():
            sid = str(row[0] or "").strip()
            if _is_valid_steamid64(sid):
                steam_ids.add(sid)
        try:
            for row in db.query(MarketPlayerProfile.steam_id).all():
                sid = str(row[0] or "").strip()
                if _is_valid_steamid64(sid):
                    steam_ids.add(sid)
        except Exception:
            pass
        for row in db.query(Order.steam_id).distinct().all():
            sid = str(row[0] or "").strip()
            if _is_valid_steamid64(sid):
                steam_ids.add(sid)
        for row in db.query(PointPayment.steam_id).distinct().all():
            sid = str(row[0] or "").strip()
            if _is_valid_steamid64(sid):
                steam_ids.add(sid)
        for sid in steam_ids:
            if db.get(StoreUser, sid) is not None:
                continue
            market_name: str | None = None
            try:
                prof = _safe_market_profile(db, sid)
                if prof and (prof.market_display_name or "").strip():
                    market_name = str(prof.market_display_name).strip()
            except Exception:
                pass
            db.add(StoreUser(
                steam_id=sid,
                display_name=_resolve_player_display_name(sid, market_name=market_name),
                created_at=now,
            ))
        db.commit()
        if steam_ids:
            _log("store_users_backfill", count=len(steam_ids))
    except Exception as exc:
        db.rollback()
        log.warning("store_users backfill falhou: %s", exc)
    finally:
        db.close()


def _is_player_site_blocked(steam_id: str) -> bool:
    if not _db_ready() or _is_admin_steamid(steam_id):
        return False
    db = _SessionLocal()
    try:
        row = db.get(StoreUser, str(steam_id))
        return bool(row and row.site_access_blocked)
    except Exception:
        return False
    finally:
        db.close()


def _store_user_blocked_fields(steam_id: str) -> dict[str, Any]:
    if not _db_ready():
        return {"site_access_blocked": False, "ban_reason": None}
    db = _SessionLocal()
    try:
        row = db.get(StoreUser, str(steam_id))
        if not row:
            return {"site_access_blocked": False, "ban_reason": None}
        return {
            "site_access_blocked": bool(row.site_access_blocked),
            "ban_reason": row.ban_reason,
        }
    finally:
        db.close()


def _dt_iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _list_admin_players(
    *,
    q: str = "",
    sort: str = "last_login",
    order: str = "desc",
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    if not _db_ready():
        return {"ok": False, "error": "Banco não configurado"}
    limit = max(1, min(200, int(limit)))
    offset = max(0, int(offset))
    q = (q or "").strip()
    sort_key = sort if sort in ("last_login", "display_name", "points", "created_at") else "last_login"
    sort_dir = "ASC" if str(order).lower() == "asc" else "DESC"
    db = _SessionLocal()
    try:
        bind = db.get_bind()
        _ensure_store_users_schema(bind)
        is_mysql = _is_mysql_engine(bind)
        has_market_profile = _db_table_exists(bind, "market_player_profile")
        has_players = _db_table_exists(bind, "players")
        params: dict[str, Any] = {"lim": limit, "off": offset}
        where = "WHERE 1=1"
        if q:
            params["q"] = f"%{q}%"
            params["qexact"] = q
            search_bits = [
                "su.steam_id LIKE :q",
                "su.display_name LIKE :q",
                "su.steam_id = :qexact",
            ]
            if has_market_profile:
                search_bits.append("mp.market_display_name LIKE :q")
            where += f" AND ({' OR '.join(search_bits)})"
        market_join = (
            f"LEFT JOIN market_player_profile mp ON {_steam_id_on_sql('mp.steam_id', 'su.steam_id', mysql=is_mysql)} "
            if has_market_profile
            else ""
        )
        players_join = (
            f"LEFT JOIN players p ON {_steam_id_on_sql('p.steam_id', 'su.steam_id', mysql=is_mysql)} "
            if has_players
            else ""
        )
        points_expr = "COALESCE(p.points, 0)" if has_players else "0"
        sort_col = {
            "last_login": "su.last_login_at",
            "display_name": (
                "COALESCE(su.display_name, mp.market_display_name, su.steam_id)"
                if has_market_profile
                else "COALESCE(su.display_name, su.steam_id)"
            ),
            "points": points_expr,
            "created_at": "su.created_at",
        }[sort_key]
        count_sql = (
            "SELECT COUNT(*) FROM store_users su "
            f"{market_join}"
            f"{players_join}"
            f"{where}"
        )
        total = int(db.execute(text(count_sql), params).scalar() or 0)
        select_cols = (
            "su.steam_id, su.display_name, "
            + ("mp.market_display_name, " if has_market_profile else "NULL AS market_display_name, ")
            + f"{points_expr}, su.site_access_blocked, su.ban_reason, "
            "su.created_at, su.last_login_at "
        )
        rows = db.execute(
            text(
                f"SELECT {select_cols}"
                "FROM store_users su "
                f"{market_join}"
                f"{players_join}"
                f"{where} "
                f"ORDER BY {sort_col} {sort_dir}, su.steam_id ASC "
                "LIMIT :lim OFFSET :off"
            ),
            params,
        ).fetchall()
        items: list[dict[str, Any]] = []
        for r in rows:
            sid = str(r[0])
            market_name = str(r[2]).strip() if r[2] else None
            if not market_name and has_market_profile:
                try:
                    prof = _safe_market_profile(db, sid)
                    if prof and (prof.market_display_name or "").strip():
                        market_name = str(prof.market_display_name).strip()
                except Exception:
                    pass
            ents = _get_player_entitlements(sid)
            items.append({
                "steam_id": sid,
                "display_name": _resolve_player_display_name(
                    sid, store_name=r[1], market_name=market_name,
                ),
                "points": int(r[3] or 0),
                "site_access_blocked": bool(r[4]),
                "ban_reason": r[5],
                "created_at": _dt_iso(r[6]),
                "last_login_at": _dt_iso(r[7]),
                "licenses": [e["group"] for e in ents],
            })
        return {"ok": True, "items": items, "total": total, "offset": offset, "limit": limit}
    except Exception as exc:
        _log_error("list_admin_players", error=str(exc))
        return {"ok": False, "error": str(exc)}
    finally:
        db.close()


def _get_admin_player_detail(steam_id: str) -> dict[str, Any]:
    if not _db_ready():
        return {"ok": False, "error": "Banco não configurado"}
    steam_id = str(steam_id or "").strip()
    if not _is_valid_steamid64(steam_id):
        return {"ok": False, "error": "SteamID64 inválido"}
    db = _SessionLocal()
    try:
        su = db.get(StoreUser, steam_id)
        prof = _safe_market_profile(db, steam_id)
        points = _get_player_points(steam_id) or 0
        entitlements = _get_player_entitlements(steam_id)
        orders = (
            db.query(Order)
            .filter(Order.steam_id == steam_id)
            .order_by(Order.created_at.desc())
            .limit(20)
            .all()
        )
        donations = (
            db.query(PointPayment)
            .filter(PointPayment.steam_id == steam_id)
            .order_by(PointPayment.created_at.desc())
            .limit(10)
            .all()
        )
        listings_count = 0
        try:
            listings_count = (
                db.query(MarketListing)
                .filter(MarketListing.seller_steam_id == steam_id)
                .count()
            )
        except Exception:
            pass
        kit_stash: dict[str, Any] = {}
        try:
            row = db.execute(
                text("SELECT kits FROM players WHERE steam_id = :sid"),
                {"sid": steam_id},
            ).fetchone()
            if row and row[0]:
                kit_stash = json.loads(row[0]) if isinstance(row[0], str) else {}
        except Exception:
            kit_stash = {}
        display_name = _resolve_player_display_name(
            steam_id,
            store_name=(su.display_name if su else None),
            market_name=(prof.market_display_name if prof else None),
        )
        return {
            "ok": True,
            "player": {
                "steam_id": steam_id,
                "display_name": display_name,
                "points": points,
                "site_access_blocked": bool(su and su.site_access_blocked),
                "ban_reason": su.ban_reason if su else None,
                "created_at": _dt_iso(su.created_at) if su else None,
                "last_login_at": _dt_iso(su.last_login_at) if su else None,
                "market_display_name": (prof.market_display_name if prof else None),
                "commerce_enabled": bool(prof.commerce_enabled) if prof else False,
                "entitlements": entitlements,
                "kit_stash": kit_stash,
                "listings_count": listings_count,
            },
            "recent_orders": [
                {
                    "order_id": o.order_id,
                    "item_type": o.item_type,
                    "item_id": o.item_id,
                    "amount": o.amount,
                    "status": o.status,
                    "points_spent": o.points_spent,
                    "created_at": _dt_iso(o.created_at),
                }
                for o in orders
            ],
            "recent_donations": [
                {
                    "payment_id": p.payment_id,
                    "package_id": p.package_id,
                    "points": p.points,
                    "status": p.status,
                    "credited": p.credited,
                    "created_at": _dt_iso(p.created_at),
                }
                for p in donations
            ],
            "license_catalog": _catalog_license_options(),
            "kit_catalog": _catalog_kit_options(),
        }
    except Exception as exc:
        _log_error("get_admin_player_detail", steam_id=steam_id, error=str(exc))
        return {"ok": False, "error": str(exc)}
    finally:
        db.close()


_LICENSE_GROUP_SKIP = frozenset({"Admins", "Staff", "Default", "VIPDoacao", ""})
_LICENSE_ID_GROUP_FALLBACK: dict[str, str] = {
    "gamma": "Gamma",
    "gama": "Gamma",
    "beta": "Beta",
    "alfa": "Alfa",
    "nuvem": "keyvault",
    "vip_bronze": "VIPBronze",
    "vip_prata": "VIPPrata",
    "vip_ouro": "VIPOuro",
    "vip_diamante": "VIPDiamante",
}


def _is_catalog_license_item(entry: dict[str, Any], item_id: str = "") -> bool:
    """Item concedível como licença — alinhado ao editor/catálogo público."""
    from catalog_enrich import _is_license_entry

    return _is_license_entry(entry, item_id or "item")


def _catalog_license_group(entry: dict[str, Any], item_id: str) -> str:
    lic = _get_license_grant(entry)
    if lic and str(lic.get("Group") or "").strip():
        return str(lic["Group"]).strip()
    for perm in _parse_permissions_field(entry):
        if perm not in _LICENSE_GROUP_SKIP:
            return perm
    key = str(item_id or "").strip().lower()
    if key.startswith("licenca_"):
        suffix = key[8:]
        if suffix in _LICENSE_ID_GROUP_FALLBACK:
            return _LICENSE_ID_GROUP_FALLBACK[suffix]
        parts = suffix.split("_")
        if len(parts) == 2 and parts[0] == "vip":
            tier = parts[1]
            return "VIP" + (tier[:1].upper() + tier[1:] if tier else "")
    return str(item_id or "").strip()


def _catalog_license_days(entry: dict[str, Any]) -> int:
    lic = _get_license_grant(entry)
    if lic and lic.get("Days") is not None:
        return int(lic.get("Days", 30) or 30)
    return 30


def _count_catalog_license_items(data: dict[str, Any]) -> int:
    items = _catalog_item_map(data)
    return sum(
        1
        for key, entry in items.items()
        if isinstance(entry, dict) and _is_catalog_license_item(entry, key)
    )


def _read_richest_license_catalog_config() -> dict[str, Any]:
    """Prefer config com mais licenças — evita dropdown truncado (stub só VIP)."""
    best = _read_shop_config()
    best_count = _count_catalog_license_items(best)
    for path in _collect_catalog_search_paths():
        if not path.is_file():
            continue
        try:
            candidate = load_plugin_config(path)
        except Exception:
            continue
        count = _count_catalog_license_items(candidate)
        if count > best_count:
            best = candidate
            best_count = count
    return best


def _catalog_license_options() -> list[dict[str, Any]]:
    data = _read_richest_license_catalog_config()
    items = _catalog_item_map(data)
    out: list[dict[str, Any]] = []
    seen_groups: set[str] = set()
    for key, entry in items.items():
        if not isinstance(entry, dict) or not _is_catalog_license_item(entry, key):
            continue
        group = _catalog_license_group(entry, key)
        if not group or group in seen_groups:
            continue
        days = _catalog_license_days(entry)
        seen_groups.add(group)
        label = str(
            entry.get("Description")
            or entry.get("Name")
            or key
        ).strip()
        out.append({
            "item_id": key,
            "group": group,
            "label": label,
            "days": days,
            "permanent": days <= 0,
        })
    out.sort(key=lambda x: (x["label"].lower(), x["group"].lower()))
    return out


def _catalog_kit_options() -> list[dict[str, Any]]:
    kits = _read_shop_config().get("Kits") or {}
    out: list[dict[str, Any]] = []
    if isinstance(kits, dict):
        for key, entry in kits.items():
            if not isinstance(entry, dict):
                continue
            out.append({
                "kit_id": key,
                "label": str(entry.get("Description") or key),
                "price": int(entry.get("Price", 0) or 0),
            })
    out.sort(key=lambda x: x["label"].lower())
    return out


def _subtract_player_points_tx(db: Any, steam_id: str, amount: int) -> int:
    if amount <= 0:
        raise ValueError("amount must be positive")
    row = db.execute(
        text("SELECT points FROM players WHERE steam_id = :sid"),
        {"sid": steam_id},
    ).fetchone()
    current = int(row[0]) if row else 0
    new_balance = max(0, current - amount)
    return _set_player_points_tx(db, steam_id, new_balance)


def _admin_player_points_adjust(
    steam_id: str,
    *,
    mode: str,
    amount: int,
    reason: str = "",
) -> dict[str, Any]:
    steam_id = str(steam_id or "").strip()
    if not _is_valid_steamid64(steam_id):
        return {"ok": False, "error": "SteamID64 inválido"}
    if not _db_ready():
        return {"ok": False, "error": "Banco não configurado"}
    mode = str(mode or "add").strip().lower()
    amount = int(amount or 0)
    db = _SessionLocal()
    try:
        before = _get_player_points(steam_id) or 0
        if mode == "add":
            if amount <= 0:
                return {"ok": False, "error": "Quantidade deve ser maior que zero"}
            after = _add_player_points_tx(db, steam_id, amount)
            event_type = "admin_player_points_add"
        elif mode == "subtract":
            if amount <= 0:
                return {"ok": False, "error": "Quantidade deve ser maior que zero"}
            after = _subtract_player_points_tx(db, steam_id, amount)
            event_type = "admin_player_points_subtract"
        elif mode == "set":
            if amount < 0:
                return {"ok": False, "error": "Saldo não pode ser negativo"}
            after = _set_player_points_tx(db, steam_id, amount)
            event_type = "admin_player_points_set"
        else:
            return {"ok": False, "error": f"Modo inválido: {mode}"}
        db.commit()
        _audit_event(
            event_type,
            actor_type="admin",
            actor_steam_id=str(_steam_id_from_session() or ""),
            target_steam_id=steam_id,
            amount=after,
            status_before=str(before),
            status_after=str(after),
            message=reason or f"Saldo: {before} → {after}",
            mode=mode,
            delta=after - before,
        )
        return {"ok": True, "steam_id": steam_id, "points": after, "before": before, "after": after}
    except Exception as exc:
        db.rollback()
        return {"ok": False, "error": str(exc)}
    finally:
        db.close()


def _admin_player_ban(steam_id: str, *, blocked: bool, reason: str = "") -> dict[str, Any]:
    steam_id = str(steam_id or "").strip()
    if not _is_valid_steamid64(steam_id):
        return {"ok": False, "error": "SteamID64 inválido"}
    if _is_admin_steamid(steam_id):
        return {"ok": False, "error": "Não é possível bloquear um administrador"}
    if not _db_ready():
        return {"ok": False, "error": "Banco não configurado"}
    db = _SessionLocal()
    try:
        row = db.get(StoreUser, steam_id)
        if row is None:
            row = StoreUser(steam_id=steam_id, display_name=steam_id)
            db.add(row)
        before = bool(row.site_access_blocked)
        row.site_access_blocked = bool(blocked)
        ban_reason_val = (reason or "").strip()[:2000] if blocked else None
        row.ban_reason = ban_reason_val
        db.commit()
        _audit_event(
            "admin_player_unban" if not blocked else "admin_player_ban",
            actor_type="admin",
            actor_steam_id=str(_steam_id_from_session() or ""),
            target_steam_id=steam_id,
            status_before="blocked" if before else "active",
            status_after="blocked" if blocked else "active",
            message=reason or ("Acesso liberado" if not blocked else "Acesso bloqueado"),
        )
        return {
            "ok": True,
            "steam_id": steam_id,
            "site_access_blocked": bool(blocked),
            "ban_reason": ban_reason_val,
        }
    except Exception as exc:
        db.rollback()
        return {"ok": False, "error": str(exc)}
    finally:
        db.close()


def _revoke_player_entitlement_by_group(steam_id: str, group: str) -> None:
    db = _SessionLocal()
    try:
        _ensure_entitlements_schema(db)
        db.execute(
            text("DELETE FROM player_entitlements WHERE steam_id = :sid AND group_name = :grp"),
            {"sid": str(steam_id), "grp": str(group)},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _admin_player_license(
    steam_id: str,
    *,
    action: str,
    group: str = "",
    days: int = 30,
    reason: str = "",
) -> dict[str, Any]:
    steam_id = str(steam_id or "").strip()
    group = str(group or "").strip()
    if not _is_valid_steamid64(steam_id):
        return {"ok": False, "error": "SteamID64 inválido"}
    if not group:
        return {"ok": False, "error": "Grupo de licença obrigatório"}
    action = str(action or "grant").strip().lower()
    if not _db_ready():
        return {"ok": False, "error": "Banco não configurado"}
    admin_sid = str(_steam_id_from_session() or "")
    try:
        if action == "grant":
            _grant_player_entitlement(
                steam_id,
                group,
                int(days),
                source=f"admin:{admin_sid}",
                notes=reason or "grant_admin",
            )
            _audit_event(
                "admin_player_license_grant",
                actor_type="admin",
                actor_steam_id=admin_sid,
                target_steam_id=steam_id,
                item_id=group,
                amount=int(days),
                message=reason or f"Licença {group} concedida",
            )
        elif action == "revoke":
            _revoke_player_entitlement_by_group(steam_id, group)
            _audit_event(
                "admin_player_license_revoke",
                actor_type="admin",
                actor_steam_id=admin_sid,
                target_steam_id=steam_id,
                item_id=group,
                message=reason or f"Licença {group} revogada",
            )
        else:
            return {"ok": False, "error": f"Ação inválida: {action}"}
        return {
            "ok": True,
            "steam_id": steam_id,
            "group": group,
            "action": action,
            "entitlements": _get_player_entitlements(steam_id),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _admin_player_kit(
    steam_id: str,
    *,
    mode: str,
    kit_id: str,
    amount: int = 1,
    reason: str = "",
) -> dict[str, Any]:
    steam_id = str(steam_id or "").strip()
    kit_id = str(kit_id or "").strip()
    amount = max(1, int(amount or 1))
    mode = str(mode or "deliver").strip().lower()
    if not _is_valid_steamid64(steam_id):
        return {"ok": False, "error": "SteamID64 inválido"}
    if not kit_id:
        return {"ok": False, "error": "kit_id obrigatório"}
    entry = _catalog_entry("kit", kit_id)
    if not entry:
        return {"ok": False, "error": f"Kit «{kit_id}» não encontrado no catálogo"}
    admin_sid = str(_steam_id_from_session() or "")
    if mode == "stash":
        if not _db_ready():
            return {"ok": False, "error": "Banco não configurado"}
        db = _SessionLocal()
        try:
            row = db.execute(
                text("SELECT kits FROM players WHERE steam_id = :sid"),
                {"sid": steam_id},
            ).fetchone()
            stash: dict[str, Any] = {}
            if row and row[0]:
                try:
                    stash = json.loads(row[0]) if isinstance(row[0], str) else {}
                except Exception:
                    stash = {}
            resolved = _resolve_catalog_item_id("kit", kit_id)
            cur = int((stash.get(resolved) or {}).get("Amount", 0) or 0)
            stash[resolved] = {"Amount": cur + amount}
            kits_json = json.dumps(stash, ensure_ascii=False)
            if _is_mysql_engine(db):
                db.execute(
                    text(
                        "INSERT INTO players (steam_id, points, kits) VALUES (:sid, 0, :kits) "
                        "ON DUPLICATE KEY UPDATE kits = :kits"
                    ),
                    {"sid": steam_id, "kits": kits_json},
                )
            else:
                db.execute(
                    text(
                        "INSERT INTO players (steam_id, points, kits) VALUES (:sid, 0, :kits) "
                        "ON CONFLICT(steam_id) DO UPDATE SET kits = :kits"
                    ),
                    {"sid": steam_id, "kits": kits_json},
                )
            db.commit()
            _audit_event(
                "admin_player_kit_stash",
                actor_type="admin",
                actor_steam_id=admin_sid,
                target_steam_id=steam_id,
                item_type="kit",
                item_id=resolved,
                amount=amount,
                message=reason or f"Kit {resolved} +{amount} no stash",
            )
            return {"ok": True, "mode": "stash", "kit_id": resolved, "stash": stash}
        except Exception as exc:
            db.rollback()
            return {"ok": False, "error": str(exc)}
        finally:
            db.close()
    if mode == "deliver":
        order, error = _create_order(steam_id, "kit", kit_id, amount)
        if error:
            return {"ok": False, "error": error}
        assert order is not None
        result = _process_order_delivery(order.order_id)
        _audit_event(
            "admin_player_kit_deliver",
            actor_type="admin",
            actor_steam_id=admin_sid,
            target_steam_id=steam_id,
            order_id=order.order_id,
            item_type="kit",
            item_id=order.item_id,
            amount=amount,
            message=reason or f"Entrega admin kit {order.item_id}",
            delivery_ok=bool(result.get("ok")),
        )
        result["order_id"] = order.order_id
        return result
    return {"ok": False, "error": f"Modo inválido: {mode}"}


_ADMIN_STEAMIDS_CACHE: dict[str, Any] = {
    "ids": None,
    "expires": 0.0,
    "db_skip_until": 0.0,
}
_ADMIN_STEAMIDS_CACHE_TTL = 30.0
_ADMIN_STEAMIDS_DB_BACKOFF = 60.0


def _load_admin_steamids_from_file() -> set[str]:
    if not _ADMIN_FILE.exists():
        return set()
    try:
        data = json.loads(_ADMIN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return set()

    values = data if isinstance(data, list) else data.get("steam_ids", []) if isinstance(data, dict) else []
    return {str(v).strip() for v in values if isinstance(v, (str, int)) and _is_valid_steamid64(str(v))}


def _merge_admin_steamids_from_db(ids: set[str], *, timeout: float) -> set[str]:
    """Mescla admins do MySQL com timeout — nunca bloqueia a thread HTTP por mais que timeout."""
    if not _db_ready() or _SessionLocal is None:
        return ids
    now = time.monotonic()
    if now < float(_ADMIN_STEAMIDS_CACHE.get("db_skip_until") or 0):
        return ids

    merged = set(ids)
    done = threading.Event()
    err: list[Exception | None] = [None]

    def _worker() -> None:
        db = _SessionLocal()
        try:
            rows = db.query(ShopAdmin).all()
            for row in rows:
                sid = str(getattr(row, "steam_id", "") or "").strip()
                if _is_valid_steamid64(sid):
                    merged.add(sid)
        except Exception as exc:
            err[0] = exc
        finally:
            db.close()
            done.set()

    threading.Thread(target=_worker, name="arkshop-admin-db", daemon=True).start()
    if not done.wait(timeout):
        _ADMIN_STEAMIDS_CACHE["db_skip_until"] = now + _ADMIN_STEAMIDS_DB_BACKOFF
        log.warning(
            "ShopAdmin timeout (%ss) — usando admins do arquivo por %ss",
            timeout,
            int(_ADMIN_STEAMIDS_DB_BACKOFF),
        )
        return ids
    if err[0] is not None:
        _ADMIN_STEAMIDS_CACHE["db_skip_until"] = now + _ADMIN_STEAMIDS_DB_BACKOFF
        log.warning(
            "ShopAdmin indisponível — usando admins do arquivo por %ss",
            int(_ADMIN_STEAMIDS_DB_BACKOFF),
        )
        return ids
    return merged


def _load_admin_steamids(*, db_timeout: float = _ADMIN_DB_QUERY_TIMEOUT) -> set[str]:
    """Lista admins — arquivo primeiro; DB opcional com cache, backoff e timeout."""
    now = time.monotonic()
    cached = _ADMIN_STEAMIDS_CACHE.get("ids")
    if isinstance(cached, set) and now < float(_ADMIN_STEAMIDS_CACHE.get("expires") or 0):
        return cached

    ids = _load_admin_steamids_from_file()
    if _db_ready():
        ids = _merge_admin_steamids_from_db(ids, timeout=db_timeout)

    _ADMIN_STEAMIDS_CACHE["ids"] = ids
    _ADMIN_STEAMIDS_CACHE["expires"] = now + _ADMIN_STEAMIDS_CACHE_TTL
    return ids


def _is_admin_steamid(steam_id: str) -> bool:
    return steam_id in _load_admin_steamids()


def _get_player_points(steam_id: str) -> int | None:
    """Returns points balance from the shared MySQL players table, or None if unavailable."""
    if not _db_ready():
        return None
    db = _SessionLocal()
    try:
        row = db.execute(
            text("SELECT points FROM players WHERE steam_id = :sid"),
            {"sid": steam_id},
        ).fetchone()
        return int(row[0]) if row else 0
    except Exception as exc:
        _log_error("get_player_points", steam_id=steam_id, error=str(exc))
        return None
    finally:
        db.close()


def _add_player_points(steam_id: str, amount: int) -> int | None:
    """Credita pontos ao jogador. Retorna novo saldo ou None."""
    if not _db_ready() or amount <= 0:
        return None
    db = _SessionLocal()
    try:
        new_balance = _add_player_points_tx(db, steam_id, amount)
        db.commit()
        return new_balance
    except Exception as exc:
        db.rollback()
        _log_error("add_player_points", steam_id=steam_id, amount=amount, error=str(exc))
        return None
    finally:
        db.close()


def _is_mysql_engine(db: Any | None = None) -> bool:
    url = str(getattr(db, "bind", None).url if db is not None and getattr(db, "bind", None) else (_ACTIVE_DATABASE_URL or ""))
    return "mysql" in url.lower()


def _add_player_points_tx(db: Any, steam_id: str, amount: int) -> int:
    """Credita pontos na sessão atual (sem commit)."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    if _is_mysql_engine(db):
        db.execute(
            text(
                "INSERT INTO players (steam_id, points) VALUES (:sid, :pts) "
                "ON DUPLICATE KEY UPDATE points = points + :pts"
            ),
            {"sid": steam_id, "pts": amount},
        )
    else:
        db.execute(
            text(
                "INSERT INTO players (steam_id, points) VALUES (:sid, :pts) "
                "ON CONFLICT(steam_id) DO UPDATE SET points = points + :pts"
            ),
            {"sid": steam_id, "pts": amount},
        )
    row = db.execute(
        text("SELECT points FROM players WHERE steam_id = :sid"),
        {"sid": steam_id},
    ).fetchone()
    if not row:
        raise RuntimeError("player row missing after credit")
    return int(row[0])


def _set_player_points_tx(db: Any, steam_id: str, amount: int) -> int:
    """Define saldo absoluto na sessão atual (sem commit)."""
    amount = max(0, int(amount))
    if _is_mysql_engine(db):
        db.execute(
            text(
                "INSERT INTO players (steam_id, points) VALUES (:sid, :pts) "
                "ON DUPLICATE KEY UPDATE points = :pts"
            ),
            {"sid": steam_id, "pts": amount},
        )
    else:
        db.execute(
            text(
                "INSERT INTO players (steam_id, points) VALUES (:sid, :pts) "
                "ON CONFLICT(steam_id) DO UPDATE SET points = :pts"
            ),
            {"sid": steam_id, "pts": amount},
        )
    row = db.execute(
        text("SELECT points FROM players WHERE steam_id = :sid"),
        {"sid": steam_id},
    ).fetchone()
    if not row:
        raise RuntimeError("player row missing after set")
    return int(row[0])


def _admin_points_action(action: str, steam_id: str, amount: int = 0) -> dict[str, Any]:
    """Consulta, credita ou define pontos diretamente no banco central."""
    steam_id = str(steam_id or "").strip()
    if not steam_id:
        return {"ok": False, "error": "SteamID64 é obrigatório"}
    if not _db_ready():
        return {"ok": False, "error": "Banco não configurado. Configure as credenciais em Configurações → DB."}

    db = _SessionLocal()
    try:
        if action == "get":
            balance = _get_player_points(steam_id)
            return {
                "ok": True,
                "steam_id": steam_id,
                "points": balance if balance is not None else 0,
                "response": f"Saldo: {balance if balance is not None else 0:,}".replace(",", "."),
            }
        if action == "add":
            if amount <= 0:
                return {"ok": False, "error": "Quantidade deve ser maior que zero"}
            new_balance = _add_player_points_tx(db, steam_id, amount)
            db.commit()
            _audit_event(
                "admin_points_add",
                actor_type="admin",
                actor_steam_id=str(_steam_id_from_session() or ""),
                target_steam_id=steam_id,
                amount=amount,
                message=f"Saldo após crédito: {new_balance}",
            )
            return {
                "ok": True,
                "steam_id": steam_id,
                "points": new_balance,
                "response": f"+{amount:,} → saldo {new_balance:,}".replace(",", "."),
            }
        if action == "set":
            if amount < 0:
                return {"ok": False, "error": "Saldo não pode ser negativo"}
            new_balance = _set_player_points_tx(db, steam_id, amount)
            db.commit()
            _audit_event(
                "admin_points_set",
                actor_type="admin",
                actor_steam_id=str(_steam_id_from_session() or ""),
                target_steam_id=steam_id,
                amount=new_balance,
                message=f"Saldo definido: {new_balance}",
            )
            return {
                "ok": True,
                "steam_id": steam_id,
                "points": new_balance,
                "response": f"Saldo definido: {new_balance:,}".replace(",", "."),
            }
        return {"ok": False, "error": f"Ação inválida: {action}"}
    except Exception as exc:
        db.rollback()
        _log_error("admin_points", action=action, steam_id=steam_id, amount=amount, error=str(exc))
        return {"ok": False, "error": str(exc)}
    finally:
        db.close()


_CONFIG_CACHE: dict[str, Any] = {"path": "", "mtime": 0.0, "data": {}}


def _invalidate_shop_config_cache() -> None:
    _CONFIG_CACHE.update({"path": "", "mtime": 0.0, "data": {}})


def _read_shop_config() -> dict[str, Any]:
    s = _load_settings()
    path = Path(s.get("config_path", _DEFAULT_CONFIG_PATH))
    if not path.exists():
        return {}
    try:
        mtime = path.stat().st_mtime
        path_key = str(path.resolve())
        if (
            _CONFIG_CACHE.get("path") == path_key
            and _CONFIG_CACHE.get("mtime") == mtime
            and isinstance(_CONFIG_CACHE.get("data"), dict)
        ):
            return _CONFIG_CACHE["data"]
        text_body = path.read_text(encoding="utf-8-sig")
        try:
            data = json.loads(text_body)
        except json.JSONDecodeError:
            cleaned = re.sub(r"//[^\n]*", "", text_body)
            data = json.loads(cleaned)
        _CONFIG_CACHE.update({"path": path_key, "mtime": mtime, "data": data})
        return data
    except Exception:
        return {}


PAID_LICENSE_GROUPS = frozenset({"Gamma", "Beta", "Alfa"})
LICENSE_TIMED_BONUS = {
    "Default": 25,
    "Gamma": 25,
    "Beta": 50,
    "Alfa": 75,
    "Moderacao": 500,
    "STAFF": 1000,
}


def _parse_permissions_field(entry: dict[str, Any]) -> list[str]:
    raw = entry.get("Permissions") or entry.get("RequiredPermissions") or ""
    if isinstance(raw, list):
        return [str(g).strip() for g in raw if str(g).strip()]
    if not raw:
        return []
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def _get_license_grant(entry: dict[str, Any]) -> dict[str, Any] | None:
    lic = entry.get("LicenseGrant")
    if isinstance(lic, dict) and lic.get("Group"):
        return lic
    return None


def _catalog_item_map(data: dict[str, Any]) -> dict[str, Any]:
    raw = data.get("Items") or data.get("ShopItems") or {}
    return raw if isinstance(raw, dict) else {}


def _resolve_catalog_item_id(item_type: str, item_id: str) -> str:
    """Resolve aliases (ex.: Gamma → licenca_gamma) para o ID canônico no config."""
    item_id = str(item_id or "").strip()
    if not item_id:
        return item_id
    data = _read_shop_config()
    if item_type == "kit":
        kits = data.get("Kits") or {}
        if item_id in kits:
            return item_id
        lower = item_id.lower()
        if lower in kits:
            return lower
        return item_id

    items = _catalog_item_map(data)
    if item_id in items:
        return item_id
    lower = item_id.lower()
    if lower in items:
        return lower
    lic_key = f"licenca_{lower}"
    if lic_key in items:
        return lic_key
    return item_id


def _catalog_entry(item_type: str, item_id: str) -> dict[str, Any]:
    data = _read_shop_config()
    resolved = _resolve_catalog_item_id(item_type, item_id)
    if item_type == "kit":
        return (data.get("Kits") or {}).get(resolved) or {}
    return _catalog_item_map(data).get(resolved) or {}


def _catalog_price(entry: dict[str, Any], amount: int = 1) -> int:
    return max(0, int(entry.get("Price", 0) or 0)) * max(1, amount)


def _entitlements_ddl_mysql() -> str:
    return (
        "CREATE TABLE IF NOT EXISTS player_entitlements ("
        "  id INT AUTO_INCREMENT PRIMARY KEY,"
        "  steam_id VARCHAR(20) NOT NULL,"
        "  group_name VARCHAR(32) NOT NULL,"
        "  expires DATETIME DEFAULT NULL,"
        "  source VARCHAR(64) DEFAULT NULL,"
        "  notes VARCHAR(255) DEFAULT NULL,"
        "  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
        "  UNIQUE KEY uq_steam_group (steam_id, group_name),"
        "  INDEX idx_steam_expires (steam_id, expires)"
        ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
    )


def _entitlements_ddl_sqlite() -> str:
    return (
        "CREATE TABLE IF NOT EXISTS player_entitlements ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  steam_id VARCHAR(20) NOT NULL,"
        "  group_name VARCHAR(32) NOT NULL,"
        "  expires DATETIME DEFAULT NULL,"
        "  source VARCHAR(64) DEFAULT NULL,"
        "  notes VARCHAR(255) DEFAULT NULL,"
        "  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
        "  UNIQUE (steam_id, group_name)"
        ")"
    )


def _ensure_entitlements_schema(conn: Any) -> None:
    """Cria player_entitlements uma única vez — DDL repetido bloqueava o MySQL para todos."""
    global _ENTITLEMENTS_SCHEMA_READY
    if _ENTITLEMENTS_SCHEMA_READY:
        return
    with _ENTITLEMENTS_SCHEMA_LOCK:
        if _ENTITLEMENTS_SCHEMA_READY:
            return
        ddl = _entitlements_ddl_mysql() if _is_mysql_engine(conn) else _entitlements_ddl_sqlite()
        conn.execute(text(ddl))
        if not _is_mysql_engine(conn):
            conn.commit()
        _ENTITLEMENTS_SCHEMA_READY = True


def _apply_entitlement_grant_tx(
    db: Any,
    steam_id: str,
    group: str,
    days: int,
    *,
    source: str = "",
    notes: str = "",
) -> None:
    _ensure_entitlements_schema(db)
    if group in PAID_LICENSE_GROUPS:
        db.execute(
            text(
                "DELETE FROM player_entitlements "
                "WHERE steam_id = :sid AND group_name IN ('Gamma','Beta','Alfa') "
                "AND group_name != :grp"
            ),
            {"sid": str(steam_id), "grp": group},
        )
    params = {
        "sid": str(steam_id),
        "grp": group,
        "days": days,
        "src": source,
        "notes": notes,
        "src_up": source,
        "notes_up": notes,
    }
    if days <= 0:
        if _is_mysql_engine(db):
            db.execute(
                text(
                    "INSERT INTO player_entitlements (steam_id, group_name, expires, source, notes) "
                    "VALUES (:sid, :grp, NULL, :src, :notes) "
                    "ON DUPLICATE KEY UPDATE expires = NULL, source = :src_up, notes = :notes_up"
                ),
                params,
            )
        else:
            db.execute(
                text(
                    "INSERT INTO player_entitlements (steam_id, group_name, expires, source, notes) "
                    "VALUES (:sid, :grp, NULL, :src, :notes) "
                    "ON CONFLICT(steam_id, group_name) DO UPDATE SET "
                    "expires = NULL, source = excluded.source, notes = excluded.notes"
                ),
                params,
            )
    elif _is_mysql_engine(db):
        db.execute(
            text(
                "INSERT INTO player_entitlements (steam_id, group_name, expires, source, notes) "
                "VALUES (:sid, :grp, DATE_ADD(NOW(), INTERVAL :days DAY), :src, :notes) "
                "ON DUPLICATE KEY UPDATE "
                "expires = DATE_ADD(GREATEST(COALESCE(expires, NOW()), NOW()), INTERVAL :days DAY), "
                "source = :src_up, notes = :notes_up"
            ),
            params,
        )
    else:
        db.execute(
            text(
                "INSERT INTO player_entitlements (steam_id, group_name, expires, source, notes) "
                "VALUES (:sid, :grp, datetime('now', '+' || :days || ' days'), :src, :notes) "
                "ON CONFLICT(steam_id, group_name) DO UPDATE SET "
                "expires = datetime('now', '+' || :days || ' days'), "
                "source = excluded.source, notes = excluded.notes"
            ),
            params,
        )


def _get_player_entitlements(steam_id: str) -> list[dict[str, Any]]:
    if not _db_ready():
        return []
    db = _SessionLocal()
    try:
        _ensure_entitlements_schema(db)
        expires_clause = (
            "(expires IS NULL OR expires > NOW())"
            if _is_mysql_engine(db)
            else "(expires IS NULL OR expires > datetime('now'))"
        )
        rows = db.execute(
            text(
                f"SELECT group_name, expires, source, notes, created_at "
                f"FROM player_entitlements "
                f"WHERE steam_id = :sid AND {expires_clause} "
                f"ORDER BY expires IS NULL DESC, expires ASC"
            ),
            {"sid": str(steam_id)},
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            grp = str(row[0])
            bonus = LICENSE_TIMED_BONUS.get(grp, 0)
            exp_raw = row[1]
            if exp_raw is not None and hasattr(exp_raw, "isoformat"):
                exp_iso = exp_raw.isoformat()
            elif exp_raw is not None:
                exp_iso = str(exp_raw)
            else:
                exp_iso = None
            out.append({
                "group": grp,
                "expires_at": exp_iso,
                "permanent": row[1] is None,
                "source": row[2],
                "notes": row[3],
                "timed_points_bonus": bonus,
            })
        return out
    except Exception as exc:
        _log_error("get_player_entitlements", steam_id=steam_id, error=str(exc))
        return []
    finally:
        db.close()


def _compute_timed_points_total(groups: list[str]) -> int:
    total = LICENSE_TIMED_BONUS.get("Default", 25)
    for g in groups:
        if g == "Default":
            continue
        total += LICENSE_TIMED_BONUS.get(g, 0)
    return total


def _player_has_license(steam_id: str, group: str) -> bool:
    if group == "Default":
        return True
    for ent in _get_player_entitlements(steam_id):
        if ent["group"] == group:
            return True
    return False


def _check_entry_permissions(steam_id: str, entry: dict[str, Any]) -> tuple[bool, list[str]]:
    groups = _parse_permissions_field(entry)
    if not groups:
        return True, []
    mode = str(entry.get("PermissionsMode", "any")).strip().lower()
    active = [g for g in groups if _player_has_license(steam_id, g)]
    if mode == "all":
        ok = len(active) == len(groups)
    else:
        ok = len(active) > 0
    missing = [g for g in groups if g not in active]
    return ok, missing


def _ensure_license_entitlement_for_order(order: Order, *, reason: str = "") -> bool:
    """Garante player_entitlements para pedidos de licença (reparo pós-entrega)."""
    item_type = str(order.item_type or "shop")
    item_id = str(order.item_id or "")
    entry = _catalog_entry(
        "kit" if item_type == "kit" else "shop",
        item_id,
    )
    lic = _get_license_grant(entry)
    if not lic or lic.get("Redeemable") is False:
        return False
    group = str(lic.get("Group") or "").strip()
    if not group:
        return False
    if _player_has_license(str(order.steam_id), group):
        return True
    note = reason or f"repair:{item_id}"
    try:
        _grant_player_entitlement(
            str(order.steam_id),
            group,
            int(lic.get("Days", 30)),
            source=str(order.order_id),
            notes=note,
        )
        _log(
            "license_entitlement_repaired",
            order_id=order.order_id,
            steam_id=str(order.steam_id),
            group=group,
            item_id=item_id,
            reason=reason or "missing_after_delivery",
        )
        return True
    except Exception as exc:
        _log_error(
            "license_entitlement_repair_failed",
            order_id=order.order_id,
            steam_id=str(order.steam_id),
            group=group,
            error=str(exc),
        )
        return False


def _grant_player_entitlement(
    steam_id: str,
    group: str,
    days: int,
    *,
    source: str = "",
    notes: str = "",
) -> None:
    db = _SessionLocal()
    try:
        _apply_entitlement_grant_tx(
            db, steam_id, group, days, source=source, notes=notes,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _revoke_entitlement_for_order(steam_id: str, order_id: str, db: Any | None = None) -> None:
    """Remove entitlement vinculado ao pedido. Se `db` for passado, usa a sessão atual."""
    sql = text(
        "DELETE FROM player_entitlements "
        "WHERE steam_id = :sid AND source = :oid"
    )
    params = {"sid": str(steam_id), "oid": order_id}
    if db is not None:
        db.execute(sql, params)
        return
    sess = _SessionLocal()
    try:
        sess.execute(sql, params)
        sess.commit()
    finally:
        sess.close()


def _load_point_packages() -> list[dict[str, Any]]:
    cfg = _read_shop_config()
    packages = cfg.get("PointPackages")
    if isinstance(packages, list) and packages:
        return packages
    s = _load_settings()
    stored = s.get("point_packages")
    if isinstance(stored, list) and stored:
        return stored
    return _DEFAULT_POINT_PACKAGES


def _package_label(package_id: str) -> str:
    pid = str(package_id or "").strip()
    if not pid:
        return "Doação PIX"
    for pkg in _load_point_packages():
        if str(pkg.get("id", "")).strip() == pid:
            return str(pkg.get("label") or pkg.get("name") or pid)
    return pid


def _get_mp_access_token() -> str:
    env_token = os.environ.get("MP_ACCESS_TOKEN", "").strip()
    if env_token:
        return env_token
    return str(_load_settings().get("mp_access_token", "")).strip()


def _pix_enabled() -> bool:
    return bool(_get_mp_access_token())


def _mp_sandbox() -> bool:
    return bool(_load_settings().get("mp_sandbox"))


def _payments_enabled() -> bool:
    return _pix_enabled()


def _steam_id_from_session() -> str | None:
    value = session.get("steam_id")
    if isinstance(value, str) and _is_valid_steamid64(value):
        return value
    return None


def _build_base_url() -> str:
    if request.headers.get("X-Forwarded-Proto") and request.headers.get("X-Forwarded-Host"):
        return f"{request.headers['X-Forwarded-Proto']}://{request.headers['X-Forwarded-Host']}"
    return request.url_root.rstrip("/")


# ── Servers registry ──────────────────────────────────────────────────────────

def _load_servers() -> list[Dict[str, Any]]:
    if not _SERVERS_FILE.exists():
        return []
    try:
        data = json.loads(_SERVERS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "rcon_password" in item and isinstance(item["rcon_password"], str):
                    item["rcon_password"] = _decrypt_value(item["rcon_password"])
            return data
    except Exception:
        pass
    return []


def _save_servers(servers: list[Dict[str, Any]]) -> None:
    safe_servers = []
    for s in servers:
        safe = s.copy()
        if "rcon_password" in safe:
            safe["rcon_password"] = _encrypt_value(str(safe["rcon_password"]))
        safe_servers.append(safe)
    _SERVERS_FILE.write_text(json.dumps(safe_servers, indent=2, ensure_ascii=False), encoding="utf-8")


def _get_server_settings(server_id: str) -> Dict[str, Any]:
    """Returns settings for a server_id, merged over global defaults."""
    base = _load_settings()
    servers = _load_servers()
    for s in servers:
        if str(s.get("server_id", "")).strip() == server_id:
            return {**base, **s}
    return base


# ── Steam OpenID ──────────────────────────────────────────────────────────────

def _verify_steam_openid(query_params: dict[str, str]) -> bool:
    payload = {k: v for k, v in query_params.items() if k.startswith("openid.")}
    payload["openid.mode"] = "check_authentication"
    encoded = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(_STEAM_OPENID_URL, data=encoded, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as response:
        text_body = response.read().decode("utf-8", errors="replace")
    return "is_valid:true" in text_body


def _extract_steam_id_from_claimed_id(claimed_id: str) -> str | None:
    m = _STEAM_CLAIMED_ID_RE.match(claimed_id.strip())
    if not m:
        return None
    candidate = m.group(1)
    return candidate if _is_valid_steamid64(candidate) else None


# ── Auth decorators ───────────────────────────────────────────────────────────

def login_required(fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    def _wrapper(*args: Any, **kwargs: Any):
        steam_id = _steam_id_from_session()
        if not steam_id:
            return jsonify({"ok": False, "error": "Não autenticado", "message": _STEAM_SESSION_REQUIRED_MESSAGE}), 401
        if _is_player_site_blocked(steam_id):
            return jsonify({
                "ok": False,
                "error": "Seu acesso ao site foi bloqueado. Contate a administração.",
                "site_access_blocked": True,
            }), 403
        return fn(*args, **kwargs)

    return _wrapper


def admin_required(fn: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(fn)
    def _wrapper(*args: Any, **kwargs: Any):
        steam_id = _steam_id_from_session()
        if not steam_id:
            return jsonify({"ok": False, "error": "Não autenticado", "message": _STEAM_SESSION_REQUIRED_MESSAGE}), 401
        if not _is_admin_steamid(steam_id):
            return jsonify({"ok": False, "error": "Acesso negado"}), 403
        return fn(*args, **kwargs)

    return _wrapper


def _safe_market_profile(db: Any, steam_id: str) -> Any | None:
    """Perfil de comércio ou None se tabela/DB indisponível."""
    from market_listings import get_profile
    from sqlalchemy.exc import OperationalError

    try:
        return get_profile(db, steam_id)
    except OperationalError:
        return None


def _auth_display_name_fields(steam_id: str, is_admin: bool) -> dict[str, Any]:
    """Campos de perfil de exibição para /api/auth/me (jogadores; admins isentos)."""
    if is_admin or not _db_ready():
        return {"market_display_name": None, "needs_display_name": False}

    db = _SessionLocal()
    try:
        prof = _safe_market_profile(db, steam_id)
        name = ((prof.market_display_name if prof else None) or "").strip()
        return {
            "market_display_name": name or None,
            "needs_display_name": not bool(name),
        }
    finally:
        db.close()


def _guard_player_display_name(steam_id: str) -> Any:
    """Bloqueia ações de jogador sem nome de exibição; admins isentos."""
    if _is_admin_steamid(steam_id) or not _db_ready():
        return None

    db = _SessionLocal()
    try:
        prof = _safe_market_profile(db, str(steam_id))
        if not prof or not (prof.market_display_name or "").strip():
            return jsonify({
                "ok": False,
                "error": "Defina seu nome de exibição antes de continuar.",
                "needs_display_name": True,
            }), 403
    finally:
        db.close()
    return None


# ── RCON ──────────────────────────────────────────────────────────────────────

def _rcon_command(
    host: str,
    port: int,
    password: str,
    command: str,
    timeout: float = 18.0,
    *,
    connect_retries: int = 1,
) -> str:
    """Envia comando RCON via RconClient compartilhado (thread pool, ASE)."""
    return _rcon_send(
        host,
        port,
        password,
        command,
        timeout=max(timeout, 12.0),
        connect_retries=connect_retries,
    )


# Comandos que o painel web / banco central já cobrem — não devem ir via RCON.
_RCON_BLOCKED_COMMANDS = frozenset({
    "shop.addpoints",
    "shop.setpoints",
    "shop.getpoints",
    "shop.deliver",
    "arkshopdeliver",
})


def _rcon_command_blocked_reason(command: str) -> str | None:
    token = (command.strip().split() or [""])[0].lower()
    if token in _RCON_BLOCKED_COMMANDS:
        return (
            "Este comando é gerenciado fora do jogo (banco central / painel web). "
            "Use Jogadores & Entregas para pontos e entregas."
        )
    return None


def _resolve_rcon_target(
    server_id: str | None,
    settings: dict[str, Any],
) -> tuple[str, int, str, str]:
    """Resolve host, porta, senha e label para RCON (servidor específico ou fallback global)."""
    if server_id:
        for srv in _load_servers():
            if str(srv.get("server_id", "")).strip() == str(server_id).strip():
                return (
                    str(srv.get("rcon_host") or settings.get("rcon_host") or "127.0.0.1"),
                    int(srv.get("rcon_port") or settings.get("rcon_port") or 27020),
                    sanitize_rcon_password(
                        str(srv.get("rcon_password") or settings.get("rcon_password") or "")
                    ),
                    str(srv.get("label") or server_id),
                )
    return (
        str(settings.get("rcon_host") or "127.0.0.1"),
        int(settings.get("rcon_port") or 27020),
        sanitize_rcon_password(str(settings.get("rcon_password") or "")),
        "padrão",
    )


def _build_delivery_command(template: str, steam_id: str, item_type: str, item_id: str, amount: int) -> str:
    return template.format(steam_id=steam_id, item_type=item_type, item_id=item_id, amount=amount)


def _delivery_mode(settings: dict[str, Any] | None = None) -> str:
    """plugin = CustomShop entrega via fila pending; rcon = legado via Shop.Deliver."""
    s = settings if settings is not None else _load_settings()
    return str(s.get("delivery_mode", "plugin")).strip().lower()


def _attempt_delivery(order: Order, settings: dict[str, Any]) -> tuple[bool, str | None, str | None, str]:
    host = settings.get("rcon_host", "127.0.0.1")
    port = int(settings.get("rcon_port", 27020))
    password = settings.get("rcon_password", "")
    template = str(settings.get("delivery_command_template", "")).strip()
    command = _build_delivery_command(template, order.steam_id, order.item_type, order.item_id, order.amount)
    try:
        response = _rcon_command(host, port, password, command)
        _log("delivery_attempt", order_id=order.order_id, server_id=order.server_id, steam_id=order.steam_id, success=True)
        return True, response, None, command
    except Exception as exc:
        _log_error("delivery_attempt", order_id=order.order_id, server_id=order.server_id, steam_id=order.steam_id, success=False, error=str(exc))
        return False, None, str(exc), command


# ── Order core ────────────────────────────────────────────────────────────────

def _create_order(steam_id: str, item_type: str, item_id: str, amount: int,
                  original_order_id: str | None = None,
                  points_spent: int = 0) -> tuple[Order | None, str | None]:
    if not _db_ready():
        return None, "Banco não configurado. Defina ARKSHOP_DATABASE_URL ou configure DB em Settings"

    if not _is_valid_steamid64(steam_id):
        return None, "SteamID64 inválido"
    if not item_id:
        return None, "item_id é obrigatório"
    if amount <= 0:
        return None, "amount deve ser maior que zero"

    s = _load_settings()
    order = Order(
        order_id=str(uuid.uuid4()),
        steam_id=steam_id,
        server_id=str(s.get("server_id", "default")),
        item_type=item_type or "shop",
        item_id=item_id,
        amount=amount,
        points_spent=max(0, int(points_spent)),
        status="PENDENTE",
        original_order_id=original_order_id,
        created_at=_now(),
        updated_at=_now(),
    )

    db = _SessionLocal()
    try:
        db.add(order)
        db.commit()
        db.refresh(order)
        _log("order_created", order_id=order.order_id, steam_id=steam_id, item_id=item_id, amount=amount, server_id=order.server_id)
        return order, None
    finally:
        db.close()


def _process_order_delivery(order_id: str, *, force_rcon: bool = False) -> dict[str, Any]:
    if not _db_ready():
        return {"ok": False, "error": "Banco não configurado. Defina ARKSHOP_DATABASE_URL ou configure DB em Settings"}

    db = _SessionLocal()
    try:
        order = db.query(Order).filter(Order.order_id == order_id).with_for_update().first()
        if not order:
            return {"ok": False, "error": "Pedido não encontrado"}

        if order.status == "ENTREGUE":
            return {"ok": True, "order_id": order.order_id, "status": order.status, "skipped": True}

        server_settings = _get_server_settings(order.server_id)
        if not force_rcon and _delivery_mode(server_settings) != "rcon":
            _log(
                "order_queued_for_plugin",
                order_id=order.order_id,
                steam_id=order.steam_id,
                server_id=order.server_id,
            )
            return {
                "ok": True,
                "order_id": order.order_id,
                "status": "PENDENTE",
                "queued": True,
                "delivery_mode": "plugin",
            }

        success, response, error, command = _attempt_delivery(order, server_settings)
        attempt = OrderAttempt(
            order_id=order.order_id,
            success=success,
            command=command,
            response=response,
            error=error,
            attempted_at=_now(),
        )
        db.add(attempt)

        if success:
            order.status = "ENTREGUE"
            order.last_error = None
        else:
            order.retry_count += 1
            max_attempts = int(server_settings.get("retry_max_attempts", 10))
            order.status = "ERRO" if order.retry_count >= max_attempts else "PENDENTE"
            order.last_error = error
        order.updated_at = _now()
        db.commit()

        _log("order_processed", order_id=order.order_id, status=order.status, retry_count=order.retry_count, success=success)
        return {
            "ok": success,
            "order_id": order.order_id,
            "status": order.status,
            "command": command,
            "response": response,
            "error": error,
            "retry_count": order.retry_count,
        }
    finally:
        db.close()


# ── Background retry scheduler ────────────────────────────────────────────────

_scheduler_thread: threading.Thread | None = None
_scheduler_stop = threading.Event()


def _retry_worker() -> None:
    _log("scheduler_started", interval_seconds=_RETRY_INTERVAL_SECONDS, batch_size=_RETRY_BATCH_SIZE)
    while not _scheduler_stop.wait(_RETRY_INTERVAL_SECONDS):
        if not _db_ready():
            continue

        try:
            from market_listings import expire_stale_claims

            mdb = _SessionLocal()
            try:
                result = expire_stale_claims(mdb)
                if result.get("processed"):
                    _log("market_claims_expired", **result)
            finally:
                mdb.close()
        except Exception as exc:
            _log_error("market_claims_expire_worker", error=str(exc))

        if _delivery_mode() != "rcon":
            continue
        db = _SessionLocal()
        try:
            pending = (
                db.query(Order)
                .filter(Order.status == "PENDENTE")
                .order_by(Order.created_at.asc())
                .limit(_RETRY_BATCH_SIZE)
                .all()
            )
            order_ids = [o.order_id for o in pending]
        finally:
            db.close()

        if order_ids:
            _log("scheduler_retry_batch", count=len(order_ids))
            for oid in order_ids:
                if _scheduler_stop.is_set():
                    break
                _process_order_delivery(oid)


_SCHEDULER_INIT_LOCK = threading.Lock()
_SCHEDULER_INITIALIZED = False


def _start_scheduler() -> None:
    global _scheduler_thread
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(target=_retry_worker, name="arkshop-retry", daemon=True)
    _scheduler_thread.start()


def _initialize_scheduler_if_needed() -> None:
    global _SCHEDULER_INITIALIZED
    if _SCHEDULER_INITIALIZED:
        return
    with _SCHEDULER_INIT_LOCK:
        if _SCHEDULER_INITIALIZED:
            return
        _start_scheduler()
        _SCHEDULER_INITIALIZED = True


# ── CustomShop internal API (requires X-API-Key header) ─────────────────────────

@app.route("/api/pending/<steam_id>", methods=["GET"])
@api_key_required(allow_admin_session=False)
@limiter.limit("60 per minute")
def get_pending_deliveries(steam_id: str):
    """Fetch pending orders for a player (called by CustomShop plugin)."""
    if (err := _require_db()) is not None:
        return err
    db = _get_db_session()
    if db is None:
        return jsonify({"ok": False, "error": "Database not available"}), 500
    try:
        orders = db.query(Order).filter(
            Order.steam_id == steam_id,
            Order.status.in_(("PENDENTE", "ENTREGANDO"))
        ).all()
        items = [{
            "order_id": o.order_id,
            "item_id": _resolve_catalog_item_id(o.item_type or "shop", o.item_id),
            "catalog_item_id": o.item_id,
            "amount": o.amount,
            "item_type": o.item_type,
        } for o in orders]
        _audit_event(
            "pending_polled",
            source="plugin",
            actor_type="plugin",
            target_steam_id=steam_id,
            message=f"Plugin consultou {len(items)} pedido(s) pendente(s)",
            persist=True,
            pending_count=len(items),
            order_ids=[i["order_id"] for i in items],
        )
        return jsonify({"ok": True, "items": items, "orders": items})
    except Exception as exc:
        _log_error("get_pending_deliveries", steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/pending/claim", methods=["POST"])
@api_key_required(allow_admin_session=False)
@limiter.limit("60 per minute")
def claim_pending_orders():
    """Reserva pedidos PENDENTE para entrega atômica (evita duplicar AddTimed)."""
    if (err := _require_db()) is not None:
        return err
    body = request.get_json(force=True, silent=True) or {}
    steam_id = str(body.get("steam_id", "")).strip()
    raw_ids = body.get("order_ids") or []
    if not steam_id or not _is_valid_steamid64(steam_id):
        return jsonify({"ok": False, "error": "steam_id inválido"}), 400

    db = _get_db_session()
    if db is None:
        return jsonify({"ok": False, "error": "Database not available"}), 500
    claimed: list[dict[str, Any]] = []
    try:
        targets = (
            [str(x).strip() for x in raw_ids if str(x).strip()]
            if isinstance(raw_ids, list) and raw_ids
            else None
        )
        q = db.query(Order).filter(
            Order.steam_id == steam_id,
            Order.status == "PENDENTE",
        )
        if targets:
            q = q.filter(Order.order_id.in_(targets))
        pending = q.order_by(Order.created_at.asc()).all()

        now = _now()
        for order in pending:
            updated = db.execute(
                text(
                    "UPDATE orders SET status = 'ENTREGANDO', updated_at = :now "
                    "WHERE order_id = :oid AND steam_id = :sid AND status = 'PENDENTE'"
                ),
                {"now": now, "oid": order.order_id, "sid": steam_id},
            )
            if int(getattr(updated, "rowcount", 0) or 0) <= 0:
                continue
            item_type = str(order.item_type or "shop")
            resolved_id = _resolve_catalog_item_id(item_type, str(order.item_id or ""))
            claimed.append({
                "order_id": order.order_id,
                "item_id": resolved_id,
                "catalog_item_id": order.item_id,
                "amount": order.amount,
                "item_type": item_type,
            })
        db.commit()
        return jsonify({"ok": True, "items": claimed, "orders": claimed})
    except Exception as exc:
        db.rollback()
        _log_error("claim_pending_orders", steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/pending/release", methods=["POST"])
@api_key_required(allow_admin_session=False)
@limiter.limit("60 per minute")
def release_pending_orders():
    """Reabre pedidos ENTREGANDO após falha na entrega pelo plugin."""
    if (err := _require_db()) is not None:
        return err
    body = request.get_json(force=True, silent=True) or {}
    steam_id = str(body.get("steam_id", "")).strip()
    raw_ids = body.get("order_ids") or []
    if not steam_id or not isinstance(raw_ids, list) or not raw_ids:
        return jsonify({"ok": False, "error": "steam_id e order_ids são obrigatórios"}), 400

    db = _get_db_session()
    if db is None:
        return jsonify({"ok": False, "error": "Database not available"}), 500
    released: list[str] = []
    try:
        now = _now()
        for raw_id in raw_ids:
            order_id = str(raw_id).strip()
            if not order_id:
                continue
            updated = db.execute(
                text(
                    "UPDATE orders SET status = 'PENDENTE', updated_at = :now "
                    "WHERE order_id = :oid AND steam_id = :sid AND status = 'ENTREGANDO'"
                ),
                {"now": now, "oid": order_id, "sid": steam_id},
            )
            if int(getattr(updated, "rowcount", 0) or 0) > 0:
                released.append(order_id)
        db.commit()
        return jsonify({"ok": True, "released": released})
    except Exception as exc:
        db.rollback()
        _log_error("release_pending_orders", steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/pending/delivered", methods=["POST"])
@api_key_required(allow_admin_session=False)
@limiter.limit("30 per minute")
def mark_pending_delivered_batch():
    """Marca vários pedidos como entregues (CustomShop plugin)."""
    if (err := _require_db()) is not None:
        return err
    body = request.get_json(force=True, silent=True) or {}
    steam_id = str(body.get("steam_id", "")).strip()
    order_ids = body.get("order_ids") or []
    deliveries = body.get("deliveries") or []
    if not steam_id or not _is_valid_steamid64(steam_id):
        return jsonify({"ok": False, "error": "steam_id inválido"}), 400
    if not isinstance(order_ids, list) or not order_ids:
        return jsonify({"ok": False, "error": "order_ids é obrigatório"}), 400

    db = _get_db_session()
    if db is None:
        return jsonify({"ok": False, "error": "Database not available"}), 500
    delivered: list[str] = []
    try:
        for raw_id in order_ids:
            order_id = str(raw_id).strip()
            if not order_id:
                continue
            order = db.query(Order).filter(
                Order.steam_id == steam_id,
                Order.order_id == order_id,
            ).first()
            if not order:
                continue
            if order.status not in ("PENDENTE", "ENTREGANDO"):
                continue
            before = order.status
            order.status = "ENTREGUE"
            order.last_error = None
            order.updated_at = _now()
            delivered.append(order_id)
            _ensure_license_entitlement_for_order(order, reason="post_delivery_repair")
            delivery_detail = next(
                (d for d in deliveries if isinstance(d, dict) and str(d.get("order_id", "")) == order_id),
                None,
            )
            _audit_event(
                "delivery_confirmed",
                source="plugin",
                actor_type="plugin",
                target_steam_id=steam_id,
                order_id=order_id,
                server_id=order.server_id,
                item_type=order.item_type,
                item_id=order.item_id,
                amount=order.amount,
                status_before=before,
                status_after="ENTREGUE",
                message=f"Plugin confirmou entrega de {order.item_id}",
                delivery=delivery_detail,
            )
        db.commit()
        _audit_event(
            "orders_marked_delivered",
            source="plugin",
            actor_type="plugin",
            target_steam_id=steam_id,
            message=f"{len(delivered)} pedido(s) marcado(s) ENTREGUE",
            count=len(delivered),
            order_ids=delivered,
        )
        return jsonify({"ok": True, "delivered": delivered})
    except Exception as exc:
        db.rollback()
        _log_error("mark_pending_delivered_batch", steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/pending/<steam_id>/<order_id>", methods=["POST"])
@api_key_required(allow_admin_session=False)
@limiter.limit("30 per minute")
def mark_pending_delivered(steam_id: str, order_id: str):
    """Mark a pending order as delivered (called by CustomShop plugin)."""
    if (err := _require_db()) is not None:
        return err
    db = _get_db_session()
    if db is None:
        return jsonify({"ok": False, "error": "Database not available"}), 500
    try:
        order = db.query(Order).filter(
            Order.steam_id == steam_id,
            Order.order_id == order_id
        ).first()
        if not order:
            return jsonify({"ok": False, "error": "Order not found"}), 404
        order.status = "ENTREGUE"
        order.updated_at = _now()
        db.commit()
        _log("order_marked_delivered", order_id=order_id, steam_id=steam_id)
        return jsonify({"ok": True})
    except Exception as exc:
        _log_error("mark_pending_delivered", order_id=order_id, steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        db.close()


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    resp = make_response(send_from_directory("static", "index.html"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/api/auth/login", methods=["GET"])
def auth_login():
    base = _build_base_url()
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.return_to": f"{base}/api/auth/callback",
        "openid.realm": base,
    }
    return redirect(f"{_STEAM_OPENID_URL}?{urllib.parse.urlencode(params)}")


@app.route("/api/auth/callback", methods=["GET"])
def auth_callback():
    qp = {k: v for k, v in request.args.items()}
    if qp.get("openid.mode", "") != "id_res":
        return redirect("/")

    steam_id = _extract_steam_id_from_claimed_id(qp.get("openid.claimed_id", ""))
    if not steam_id:
        return redirect("/")

    try:
        valid = _verify_steam_openid(qp)
    except Exception:
        valid = False
    if not valid:
        return redirect("/")

    session["steam_id"] = steam_id
    _touch_store_user_login(steam_id)
    _log("auth_login", steam_id=steam_id, is_admin=_is_admin_steamid(steam_id))
    return redirect("/")


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    steam_id = _steam_id_from_session()
    session.pop("steam_id", None)
    _log("auth_logout", steam_id=steam_id)
    return jsonify({"ok": True})


def _kick_db_health_ping_if_stale() -> None:
    """Dispara ping SELECT 1 em background — resposta de /api/health nunca espera."""
    if not _db_ready() or _SessionLocal is None:
        _HEALTH_DB_CACHE["reachable"] = False
        _HEALTH_DB_CACHE["checked_at"] = time.monotonic()
        return
    now = time.monotonic()
    if now - float(_HEALTH_DB_CACHE.get("checked_at") or 0) < _HEALTH_DB_CACHE_TTL:
        return
    if _HEALTH_DB_CACHE.get("ping_inflight"):
        return
    _HEALTH_DB_CACHE["ping_inflight"] = True

    def _worker() -> None:
        reachable = False
        done = threading.Event()

        def _ping() -> None:
            nonlocal reachable
            try:
                db = _SessionLocal()
                try:
                    db.execute(text("SELECT 1")).fetchone()
                    reachable = True
                finally:
                    db.close()
            except Exception:
                reachable = False
            finally:
                done.set()

        threading.Thread(target=_ping, name="arkshop-db-ping", daemon=True).start()
        if not done.wait(_HEALTH_DB_PING_TIMEOUT):
            log.debug("DB health ping timeout (%ss)", _HEALTH_DB_PING_TIMEOUT)
        _HEALTH_DB_CACHE["reachable"] = reachable
        _HEALTH_DB_CACHE["checked_at"] = time.monotonic()
        _HEALTH_DB_CACHE["ping_inflight"] = False

    threading.Thread(target=_worker, name="arkshop-db-health", daemon=True).start()


@app.route("/api/health", methods=["GET"])
def health_check():
    """Ping leve — zero I/O bloqueante; db_reachable vem de cache em background."""
    if _db_ready():
        _kick_db_health_ping_if_stale()
    return jsonify({
        "ok": True,
        "db_configured": _db_ready(),
        "db_reachable": _HEALTH_DB_CACHE.get("reachable") if _db_ready() else None,
        "version": _get_project_release().get("version", ""),
    })


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    steam_id = _steam_id_from_session()
    if not steam_id:
        return jsonify({
            "authenticated": False,
            "is_admin": False,
            "steam_id": None,
            "needs_display_name": False,
            "market_display_name": None,
        })
    file_admins = _load_admin_steamids_from_file()
    is_admin = steam_id in file_admins
    if not is_admin and _db_ready():
        is_admin = steam_id in _load_admin_steamids(db_timeout=1.5)
    payload: dict[str, Any] = {
        "authenticated": True,
        "is_admin": is_admin,
        "steam_id": steam_id,
    }
    payload.update(_auth_display_name_fields(steam_id, is_admin))
    if not is_admin:
        payload.update(_store_user_blocked_fields(steam_id))
    return jsonify(payload)


# ── Settings routes ───────────────────────────────────────────────────────────

@app.route("/api/settings", methods=["GET"])
@admin_required
def get_settings():
    s = _load_settings()
    safe = {k: v for k, v in s.items() if k not in ("rcon_password", "db_password", "mp_access_token", "cross_chat_discord_token")}
    safe["rcon_password_set"] = bool(s.get("rcon_password"))
    safe["db_password_set"] = bool(s.get("db_password"))
    safe["mp_access_token_set"] = bool(_get_mp_access_token())
    safe["cross_chat_discord_token_set"] = bool(s.get("cross_chat_discord_token"))
    safe["pix_enabled"] = _pix_enabled()
    safe["card_enabled"] = _payments_enabled()
    safe["mp_sandbox"] = _mp_sandbox()
    safe["point_packages"] = _load_point_packages()
    safe["db_configured"] = _db_ready()
    safe["db_from_env"] = bool(_DATABASE_URL)
    return jsonify(safe)


@app.route("/api/settings", methods=["POST"])
@admin_required
def save_settings():
    body = request.get_json(force=True)
    s = _load_settings()
    for key in (
        "config_path",
        "rcon_host",
        "rcon_port",
        "delivery_command_template",
        "delivery_mode",
        "server_id",
        "retry_max_attempts",
        "database_url",
        "db_host",
        "db_port",
        "db_name",
        "db_user",
        "point_packages",
        "mp_sandbox",
    ):
        if key in body:
            s[key] = body[key]
    if "rcon_password" in body and body["rcon_password"] != "":
        s["rcon_password"] = body["rcon_password"]
    if "db_password" in body and body["db_password"] != "":
        s["db_password"] = body["db_password"]
    if "mp_access_token" in body and body["mp_access_token"] != "":
        s["mp_access_token"] = body["mp_access_token"]
    _save_settings(s)

    reconnect_error = None
    try:
        _configure_database(_resolve_database_url(s))
    except Exception as exc:
        reconnect_error = str(exc)

    _log("settings_saved", admin=_steam_id_from_session(), db_ok=_db_ready())
    return jsonify({
        "ok": reconnect_error is None,
        "db_configured": _db_ready(),
        "db_from_env": bool(_DATABASE_URL),
        "error": reconnect_error,
    }), 200 if reconnect_error is None else 500


# ── Servers routes ────────────────────────────────────────────────────────────

@app.route("/api/servers", methods=["GET"])
@admin_required
def get_servers():
    servers = _load_servers()
    safe = []
    for s in servers:
        entry = {k: v for k, v in s.items() if k not in ("rcon_password",)}
        entry["rcon_password_set"] = bool(s.get("rcon_password"))
        safe.append(entry)
    return jsonify({"ok": True, "items": safe})


@app.route("/api/servers", methods=["POST"])
@admin_required
def upsert_server():
    body = request.get_json(force=True)
    server_id = str(body.get("server_id", "")).strip()
    if not server_id:
        return jsonify({"ok": False, "error": "server_id é obrigatório"}), 400

    servers = _load_servers()
    entry: Dict[str, Any] = {
        "server_id": server_id,
        "label": str(body.get("label", server_id)).strip(),
        "plugin_config_path": str(body.get("plugin_config_path") or "").strip(),
        "retry_max_attempts": int(body.get("retry_max_attempts", 10)),
        "show_on_home": body.get("show_on_home", True) is not False,
    }
    for key in (
        "rcon_host",
        "rcon_port",
        "rcon_password",
        "delivery_command_template",
        "delivery_mode",
    ):
        if key in body and body[key] not in (None, ""):
            entry[key] = body[key]

    for existing in servers:
        if existing.get("server_id") == server_id:
            if not entry["plugin_config_path"]:
                entry["plugin_config_path"] = str(existing.get("plugin_config_path") or "").strip()
            for key in (
                "rcon_host",
                "rcon_port",
                "rcon_password",
                "delivery_command_template",
                "delivery_mode",
                "arkland_ref",
                "managed_by",
            ):
                if key not in entry and existing.get(key) not in (None, ""):
                    entry[key] = existing[key]
            break

    replaced = False
    for idx, s in enumerate(servers):
        if s.get("server_id") == server_id:
            servers[idx] = entry
            replaced = True
            break
    if not replaced:
        servers.append(entry)

    _save_servers(servers)
    _log("server_upserted", server_id=server_id, admin=_steam_id_from_session())
    return jsonify({"ok": True, "updated": replaced})


@app.route("/api/servers/<server_id>", methods=["DELETE"])
@admin_required
def delete_server(server_id: str):
    server_id = server_id.strip()
    servers = _load_servers()
    kept = [s for s in servers if s.get("server_id") != server_id]
    _save_servers(kept)
    _log("server_deleted", server_id=server_id, admin=_steam_id_from_session())
    return jsonify({"ok": True, "removed": len(servers) - len(kept)})


@app.route("/api/servers/sync", methods=["POST"])
@api_key_required(allow_admin_session=False)
def sync_servers_from_client():
    """Recebe cadastro de servidores de uma máquina cliente (modo cross / multi-host)."""
    body = request.get_json(force=True, silent=True) or {}
    machine_label = str(body.get("machine_label") or "").strip()
    if not machine_label:
        return jsonify({"ok": False, "error": "machine_label é obrigatório"}), 400

    raw_servers = body.get("servers") or []
    if not isinstance(raw_servers, list):
        return jsonify({"ok": False, "error": "servers deve ser uma lista"}), 400

    active_refs = {
        str(r).strip()
        for r in (body.get("active_refs") or [])
        if str(r).strip()
    }

    servers = _load_servers()
    by_id: Dict[str, Any] = {}
    for s in servers:
        if not isinstance(s, dict):
            continue
        sid = str(s.get("server_id", "")).strip()
        if sid:
            by_id[sid] = s

    incoming: List[Dict[str, Any]] = []
    for raw in raw_servers:
        if not isinstance(raw, dict):
            continue
        sid = str(raw.get("server_id", "")).strip()
        if not sid:
            continue
        entry = {
            k: v
            for k, v in raw.items()
            if k in (
                "server_id", "label", "rcon_host", "rcon_port", "rcon_password",
                "delivery_mode", "machine_label", "plugin_config_path",
                "arkland_ref", "show_on_home", "retry_max_attempts",
                "delivery_command_template",
            ) and v not in (None, "")
        }
        entry["server_id"] = sid
        entry["machine_label"] = machine_label
        entry.setdefault("show_on_home", True)
        if raw.get("arkland_ref"):
            entry["arkland_ref"] = str(raw.get("arkland_ref"))
        existing = by_id.get(sid)
        srv_stub = type("Srv", (), {"shop_show_on_home": entry.get("show_on_home", True)})()
        incoming.append(_merge_arkland_server_entry(existing, entry, srv_stub))

    registered = apply_machine_server_registry(
        by_id, machine_label, incoming, active_refs,
    )
    _save_servers(list(by_id.values()))
    _log(
        "servers_synced",
        machine_label=machine_label,
        registered=registered,
        active_refs=len(active_refs),
    )
    return jsonify({"ok": True, "registered": registered, "total": len(by_id)})


# ── Players routes ────────────────────────────────────────────────────────────

@app.route("/api/players", methods=["GET"])
@admin_required
def get_players():
    return jsonify(_load_players())


@app.route("/api/players", methods=["POST"])
@admin_required
def upsert_player():
    body = request.get_json(force=True)
    steam_id = str(body.get("steam_id", "")).strip()
    if not _is_valid_steamid64(steam_id):
        return jsonify({"ok": False, "error": "SteamID64 inválido"}), 400

    new_player = {
        "steam_id": steam_id,
        "name": str(body.get("name", "")).strip(),
        "tribe": str(body.get("tribe", "")).strip(),
        "note": str(body.get("note", "")).strip(),
    }
    players = _load_players()
    replaced = False
    for idx, player in enumerate(players):
        if str(player.get("steam_id", "")).strip() == steam_id:
            players[idx] = new_player
            replaced = True
            break
    if not replaced:
        players.append(new_player)
    _save_players(players)
    return jsonify({"ok": True, "updated": replaced})


@app.route("/api/players/<steam_id>", methods=["DELETE"])
@admin_required
def delete_player(steam_id: str):
    steam_id = steam_id.strip()
    if not _is_valid_steamid64(steam_id):
        return jsonify({"ok": False, "error": "SteamID64 inválido"}), 400
    players = _load_players()
    kept = [p for p in players if str(p.get("steam_id", "")).strip() != steam_id]
    _save_players(kept)
    return jsonify({"ok": True, "removed": len(players) - len(kept)})


# ── Config routes ─────────────────────────────────────────────────────────────

def _normalize_config_to_web(data: dict) -> dict:
    """Normaliza config.json (CustomShop: 'Items') para o formato web (ShopItems).
    Aceita ambos os formatos — não destrói dados já no formato correto.
    """
    if "Items" in data and "ShopItems" not in data:
        data = dict(data)
        data["ShopItems"] = data.pop("Items")
    if "Kits" in data and not isinstance(data.get("Kits"), dict):
        pass  # mantém como está
    return data


def _normalize_config_to_file(data: dict) -> dict:
    """Normaliza de volta para CustomShop ('ShopItems' -> 'Items') ao salvar."""
    if "ShopItems" in data and "Items" not in data:
        data = dict(data)
        data["Items"] = data.pop("ShopItems")
    try:
        from src.shop_catalog_import import sanitize_catalog_blueprints

        sanitize_catalog_blueprints(data)
    except Exception:
        pass
    return data


def _read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        text_body = path.read_text(encoding="utf-8-sig")
        try:
            return json.loads(text_body)
        except json.JSONDecodeError:
            cleaned = re.sub(r"//[^\n]*", "", text_body)
            return json.loads(cleaned)
    except Exception:
        return {}


def _merge_catalog_into_plugin(existing: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    """Mescla catálogo mestre no config de um servidor, preservando ServerId e senha DB locais."""
    return merge_catalog_into_plugin_config(catalog, existing)


def _plugin_sync_targets(settings: dict[str, Any]) -> list[dict[str, str]]:
    """Destinos onde o config.json do CustomShop deve ser gravado (sem duplicatas)."""
    targets: list[dict[str, str]] = []
    seen: set[str] = set()

    master = _resolve_settings_catalog_path(str(settings.get("config_path") or _DEFAULT_CONFIG_PATH))
    if master:
        targets.append({"label": "Catálogo mestre", "path": master, "kind": "master"})
        seen.add(master.lower())

    for srv in _load_servers():
        path = str(
            srv.get("plugin_config_path")
            or srv.get("customshop_config_path")
            or ""
        ).strip()
        if not path:
            continue
        key = path.lower()
        if key in seen:
            continue
        seen.add(key)
        label = str(srv.get("label") or srv.get("server_id") or path).strip()
        targets.append({"label": label, "path": path, "kind": "server"})

    return targets


def _write_config_all_targets(body: dict[str, Any], settings: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Grava catálogo em todos os destinos. Retorna (written, errors)."""
    written: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    file_body = _normalize_config_to_file(body)

    for target in _plugin_sync_targets(settings):
        path = Path(target["path"])
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            existing = _read_json_file(path)
            merged = _merge_catalog_into_plugin(existing, file_body) if existing else file_body
            path.write_text(json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8")
            written.append({"label": target["label"], "path": str(path)})
        except Exception as exc:
            errors.append({"label": target["label"], "path": str(path), "error": str(exc)})

    return written, errors


def _reload_all_plugins(settings: dict[str, Any]) -> list[dict[str, Any]]:
    """Shop.Reload via RCON em todos os servidores registrados (+ fallback global)."""
    results: list[dict[str, Any]] = []
    servers = _load_servers()

    if servers:
        for srv in servers:
            sid = str(srv.get("server_id") or "server")
            label = str(srv.get("label") or sid)
            host, port, password, _ = _resolve_rcon_target(sid, settings)
            try:
                resp = _rcon_command(
                    host, port, password, "Shop.Reload", connect_retries=5,
                )
                results.append({"server_id": sid, "label": label, "ok": True, "response": resp[:200]})
            except Exception as exc:
                results.append({"server_id": sid, "label": label, "ok": False, "error": str(exc)})
        return results

    host, port, password, label = _resolve_rcon_target(None, settings)
    try:
        resp = _rcon_command(host, port, password, "Shop.Reload", connect_retries=5)
        results.append({"server_id": "default", "label": label, "ok": True, "response": resp[:200]})
    except Exception as exc:
        results.append({"server_id": "default", "label": label, "ok": False, "error": str(exc)})
    return results


@app.route("/api/config", methods=["GET"])
@admin_required
def get_config():
    s = _load_settings()
    path = Path(s["config_path"])
    if not path.exists():
        # Retorna estrutura vazia para o frontend inicializar corretamente
        return jsonify({"ShopItems": {}, "Kits": {}, "_config_path_missing": str(path)})
    try:
        text_body = path.read_text(encoding="utf-8-sig")
        try:
            data = json.loads(text_body)
        except json.JSONDecodeError:
            cleaned = re.sub(r"//[^\n]*", "", text_body)
            data = json.loads(cleaned)
        # Normaliza Items -> ShopItems para o frontend web
        data = _normalize_config_to_web(data)
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/config", methods=["POST"])
@admin_required
def save_config():
    s = _load_settings()
    body = request.get_json(force=True)
    settings = body.get("Settings")
    if isinstance(settings, dict) and settings.get("ShopName"):
        settings["ShopName"] = _public_brand_name(str(settings["ShopName"]))
    written, write_errors = _write_config_all_targets(body, s)
    if not written and write_errors:
        return jsonify({"ok": False, "error": write_errors[0]["error"], "written": [], "errors": write_errors}), 500
    _log(
        "config_saved",
        paths=[w["path"] for w in written],
        admin=_steam_id_from_session(),
        errors=len(write_errors),
    )
    _invalidate_shop_config_cache()
    master_path = next((w["path"] for w in written if "mestre" in w.get("label", "").lower()), "")
    if master_path:
        try:
            from src.shop_integration import push_catalog_to_webstore

            push_catalog_to_webstore(master_path)
        except Exception:
            pass
    return jsonify({
        "ok": True,
        "written": written,
        "errors": write_errors,
        "sync_count": len(written),
    })


# ── DB test ───────────────────────────────────────────────────────────────────

@app.route("/api/db/test", methods=["POST"])
@admin_required
def test_db_connection():
    """Testa a conectividade com o banco de dados atual."""
    if not _db_ready():
        return jsonify({"ok": False, "error": "Banco não configurado. Preencha as credenciais em Configurações."}), 200
    try:
        session = _get_db_session()
        if session is None:
            return jsonify({"ok": False, "error": "SessionLocal não inicializado."}), 200
        session.execute(text("SELECT 1")).fetchone()
        session.close()
        db_info = _safe_db_log_fields(_ACTIVE_DATABASE_URL)
        label = db_info.get("database") or db_info.get("host") or "ok"
        return jsonify({"ok": True, "info": f"Banco conectado ({label})"})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 200


# ── Público (home + catálogo sem login) ───────────────────────────────────────

def _catalog_public_stats(data: dict[str, Any]) -> dict[str, int]:
    """Contagens públicas do catálogo para a home."""
    items_map = data.get("Items") or data.get("ShopItems") or {}
    items_n = dinos_n = 0
    for entry in items_map.values():
        if not isinstance(entry, dict):
            continue
        if str(entry.get("Type") or "item").lower() == "dino":
            dinos_n += 1
        else:
            items_n += 1
    kits_n = len(data.get("Kits") or {})
    return {"items": items_n, "dinos": dinos_n, "kits": kits_n}


def _public_currency() -> dict[str, str]:
    return {
        "singular": _AMBER_SINGULAR,
        "plural": _AMBER_PLURAL,
        "image_url": _AMBER_ICON_URL,
    }


def _public_brand_name(raw: str) -> str:
    """Nome público do portal — nunca exibe 'Shop' (evita conotação de loja comercial)."""
    name = str(raw or "").strip()
    if not name:
        return _DEFAULT_PUBLIC_BRAND
    if re.search(r"\bshop\b", name, re.IGNORECASE):
        base = re.sub(r"\s*\bshop\b", "", name, flags=re.IGNORECASE).strip()
        if not base or re.fullmatch(r"arkland", base, re.IGNORECASE):
            return _DEFAULT_PUBLIC_BRAND
        if re.search(r"\bdonations?\b", base, re.IGNORECASE):
            return base.upper() if base.upper().startswith("ARKLAND") else base
        return _DEFAULT_PUBLIC_BRAND if re.fullmatch(r"arkland", base, re.IGNORECASE) else base
    if re.fullmatch(r"arkland", name, re.IGNORECASE):
        return _DEFAULT_PUBLIC_BRAND
    return name


def _default_amber_lore() -> dict[str, Any]:
    return {
        "title": "A Lenda do Âmbar de Arkland",
        "sections": [
            {
                "paragraphs": [
                    "Antes dos sobreviventes erguerem muralhas, antes das tribos dominarem os céus "
                    "com Wyverns e os mares com Mosassauros, existia apenas o silêncio.",
                    "Dizem que, quando os primeiros Obeliscos surgiram sobre Arkland, uma chuva dourada "
                    "caiu dos céus durante sete dias e sete noites. Não era fogo, nem cristal. Eram "
                    "fragmentos de uma substância desconhecida que brilhava como o sol ao amanhecer.",
                    "Os sobreviventes que encontraram esses fragmentos perceberam algo estranho. "
                    "Dentro deles havia memórias.",
                    "Alguns continham folhas de árvores extintas. Outros guardavam insetos ancestrais. "
                    "Os mais raros aprisionavam fragmentos da essência das criaturas primordiais.",
                    "Um caçador encontrou um pedaço tão puro que dentro dele podia ser visto o crânio "
                    "de um Rex ancestral.",
                    "Quando o fragmento foi levado até o Grande Obelisco, o cristal reagiu. "
                    "A luz dos Obeliscos reconhecia aquela substância.",
                    "Naquele momento nasceu o nome que atravessaria gerações: Âmbar.",
                    "Os sábios de Arkland descobriram que cada pedaço de Âmbar continha energia "
                    "ancestral condensada durante milhares de anos. Não era apenas uma pedra. "
                    "Era tempo solidificado. Era a memória viva do mundo primitivo.",
                    "Por isso nenhuma tribo ousava destruí-lo. Nenhum comerciante recusava recebê-lo. "
                    "Nenhum governante conseguia ignorar seu valor.",
                    "Com o passar dos anos, o Âmbar tornou-se a moeda oficial de Arkland. "
                    "Não porque alguém decretou. Mas porque todos concordaram que nada era mais valioso "
                    "do que a própria história do mundo.",
                ],
            },
            {
                "heading": "Valor Cultural",
                "paragraphs": [
                    "Para os habitantes de Arkland:",
                    "Ouro representa riqueza.",
                    "Cristais representam tecnologia.",
                    "Elemento representa poder.",
                    "Mas o Âmbar representa algo maior: Legado.",
                    "Cada moeda é considerada um fragmento preservado da Era Primitiva.",
                    "Ao trocar Âmbares, os sobreviventes acreditam estar transferindo parte da "
                    "história de Arkland para outra pessoa.",
                ],
            },
            {
                "heading": "A Coroa de Âmbar",
                "paragraphs": [
                    "Entre todas as moedas já cunhadas, existe uma categoria lendária. "
                    "As Coroas de Âmbar.",
                    "Produzidas apenas pelos Guardiões dos Obeliscos, elas utilizam os fragmentos "
                    "mais puros já encontrados.",
                    "Acredita-se que cada Coroa de Âmbar contenha a essência de um Alfa ancestral.",
                    "Possuir uma delas não significa apenas riqueza. Significa prestígio. "
                    "Significa que o próprio Ark reconheceu seu valor.",
                ],
                "blockquote": (
                    "O ouro compra ferramentas.\n"
                    "O cristal compra poder.\n"
                    "Mas o Âmbar compra o respeito do tempo."
                ),
                "blockquote_attribution": "Uma antiga inscrição encontrada em uma ruína",
            },
        ],
        "quote": {
            "label": "Frase oficial da moeda",
            "title": "Âmbar",
            "text": (
                "Quando os dinossauros desaparecerem, quando as tribos ruírem e quando os obeliscos "
                "se apagarem, o Âmbar ainda contará a história de quem viveu aqui."
            ),
        },
    }


def _amber_lore_block(settings_block: dict[str, Any]) -> dict[str, Any]:
    """Lore do Âmbar — editável via Settings.AmberLore / AmberLoreTitle no config da loja."""
    default = _default_amber_lore()
    title = str(settings_block.get("AmberLoreTitle") or default["title"]).strip()
    raw = str(settings_block.get("AmberLore") or "").strip()
    if raw:
        return {
            "title": title,
            "paragraphs": [p.strip() for p in raw.split("\n\n") if p.strip()],
            "sections": [],
            "quote": default.get("quote"),
            "image_url": _AMBER_ICON_URL,
        }
    return {
        "title": title,
        "sections": default["sections"],
        "paragraphs": [],
        "quote": default.get("quote"),
        "image_url": _AMBER_ICON_URL,
    }


@app.route("/api/public/home", methods=["GET"])
def public_home():
    """Dados públicos para a página inicial (sem autenticação)."""
    data = _read_shop_config()
    settings_block = data.get("Settings") or {}
    shop_name = _public_brand_name(
        settings_block.get("ShopName")
        or data.get("ShopName")
        or data.get("shop_name")
        or _DEFAULT_PUBLIC_BRAND
    )
    s = _load_settings()
    public_url = str(s.get("public_url") or "").strip() or DEFAULT_SHOP_PUBLIC_URL
    website_url = str(settings_block.get("WebsiteUrl") or settings_block.get("WebApiUrl") or public_url).strip()
    discord_url = str(settings_block.get("DiscordUrl") or "").strip()
    servers = [
        {
            "server_id": srv.get("server_id", ""),
            "label": srv.get("label") or srv.get("server_id", ""),
            "machine_label": str(srv.get("machine_label") or "").strip(),
        }
        for srv in _load_servers()
        if srv.get("server_id") and srv.get("show_on_home", True) is not False
    ]
    utilities = _load_downloads()
    packages = _load_point_packages()
    stats = _catalog_public_stats(data)
    stats["kits"] = stats.get("kits", 0)
    stats["packages"] = len(packages)
    stats["utilities"] = len(utilities)
    stats["servers"] = len(servers)

    messages = data.get("Messages") or {}
    welcome = str(
        messages.get("Welcome")
        or messages.get("HomeWelcome")
        or messages.get("MOTD")
        or ""
    ).strip()

    default_description = (
        "O ARKLAND é um ecossistema de servidores ARK: Survival Evolved pensado para "
        "comunidades que jogam em cluster, com loja integrada, entrega automática in-game "
        "e suporte a doações voluntárias via PIX. Aqui você apoia o servidor e resgata "
        "recompensas simbólicas em Âmbares — itens, dinos e kits entregues quando você conecta."
    )

    return jsonify({
        "ok": True,
        "shop_name": shop_name,
        "public_url": public_url,
        "website_url": website_url,
        "discord_url": discord_url,
        "currency": _public_currency(),
        "amber_lore": _amber_lore_block(settings_block),
        "pix_enabled": _pix_enabled(),
        "card_enabled": _payments_enabled(),
        "starting_points": int(settings_block.get("StartingPoints") or 0),
        "servers": servers,
        "stats": stats,
        "tagline": (
            "Doações voluntárias · Âmbar simbólico · Entrega automática no ARK"
        ),
        "description": str(settings_block.get("HomeDescription") or "").strip() or welcome or default_description,
        "welcome_message": welcome,
        "donation_packages": [
            {
                "id": p.get("id", ""),
                "label": p.get("label", ""),
                "points": int(p.get("points", 0) or 0),
                "price_brl": float(p.get("price_brl", 0) or 0),
            }
            for p in packages[:6]
        ],
        "utilities_preview": [
            {
                "id": u.get("id", ""),
                "label": u.get("label", ""),
                "description": u.get("description", ""),
                "icon": u.get("icon", "link"),
                "category": u.get("category", "Geral"),
                "url": u.get("url", ""),
            }
            for u in utilities[:8]
        ],
        "seasonal_events": {
            "title": "Eventos Sazonais",
            "description": (
                "Utilizamos um sistema de Eventos Sazonais semelhante ao dos servidores oficiais da Wildcard. "
                "Em cada ciclo, um evento sazonal é definido para o cluster — Fear Evolved, Winter Wonderland, "
                "Summer Bash e outros — e todos os mapas passam a operar com rates e regras específicas "
                "ajustadas periodicamente de acordo com o evento ativo."
            ),
            "highlights": [
                "Rates de XP, reprodução, consumo e coleta calibrados por evento, em todos os mapas do cluster.",
                "Rotação periódica — a experiência muda ao longo da temporada, como nos servidores oficiais.",
                "Anúncios no Discord e neste portal quando um novo evento entra em vigor.",
            ],
        },
        "featured_maps": _load_featured_maps_public(),
        "featured_maps_section": _featured_maps_section_meta(),
    })


# ── Catalog (público, sem autenticação) ───────────────────────────────────────

@app.route("/api/catalog", methods=["GET"])
def get_catalog():
    """Retorna catálogo público (itens, kits, pacotes de doação)."""
    from ark_species_registry import TIER_ICON_URLS
    from catalog_enrich import CATEGORY_ICONS, enrich_catalog_payload

    s = _load_settings()
    config_path = Path(s.get("config_path", _DEFAULT_CONFIG_PATH))
    data = _read_shop_config()
    items = data.get("Items") or data.get("ShopItems") or {}
    kits = data.get("Kits") or {}
    items, kits = enrich_catalog_payload(items, kits)
    settings_block = data.get("Settings") or {}
    shop_name = _public_brand_name(
        settings_block.get("ShopName")
        or data.get("ShopName")
        or data.get("shop_name")
        or _DEFAULT_PUBLIC_BRAND
    )
    packages = _load_point_packages()
    public_url = str(s.get("public_url") or "").strip() or DEFAULT_SHOP_PUBLIC_URL

    def _kit_price(kit_id: str) -> int | None:
        raw = (kits.get(kit_id) or data.get("Kits", {}).get(kit_id) or {})
        if not isinstance(raw, dict):
            return None
        price = raw.get("Price")
        return int(price) if price is not None else None

    def _kit_perms(kit_id: str) -> str:
        raw = (kits.get(kit_id) or data.get("Kits", {}).get(kit_id) or {})
        if not isinstance(raw, dict):
            return ""
        return str(raw.get("Permissions") or "")

    placeholder_kits_detected = False
    try:
        from src.catalog_vip_pricing import catalog_has_placeholder_kit_prices

        placeholder_kits_detected = catalog_has_placeholder_kit_prices(data)
    except Exception:
        pass

    catalog_meta = {
        "config_path": str(config_path.resolve()) if config_path.exists() else str(config_path),
        "config_exists": config_path.is_file(),
        "items_count": len(items) if isinstance(items, dict) else 0,
        "kits_count": len(kits) if isinstance(kits, dict) else 0,
        "placeholder_kits_detected": placeholder_kits_detected,
        "vip_sample": {
            "vip_bronze": {"price": _kit_price("vip_bronze"), "permissions": _kit_perms("vip_bronze")},
            "ouro": {"price": _kit_price("ouro"), "permissions": _kit_perms("ouro")},
            "diamante": {"price": _kit_price("diamante"), "permissions": _kit_perms("diamante")},
            "kit_tek_padrao_alfa": {"price": _kit_price("kit_tek_padrao_alfa")},
        },
    }

    return jsonify({
        "items": items,
        "kits": kits,
        "shop_name": shop_name,
        "point_packages": packages,
        "currency": _public_currency(),
        "pix_enabled": _pix_enabled(),
        "card_enabled": _payments_enabled(),
        "mp_sandbox": _mp_sandbox(),
        "public_url": public_url,
        "shop_url": public_url,
        "tier_icon_urls": TIER_ICON_URLS,
        "category_icons": CATEGORY_ICONS,
        "catalog_meta": catalog_meta,
    })


# ── Downloads (público + admin CRUD) ─────────────────────────────────────────

_VERSION_JSON = _BUNDLE_DIR / "version.json"
if not _VERSION_JSON.is_file() and not getattr(sys, "frozen", False):
    _VERSION_JSON = Path(__file__).resolve().parent.parent.parent / "version.json"


def _get_project_release() -> dict:
    """Lê version.json e retorna os dados da versão atual do projeto."""
    try:
        if _VERSION_JSON.exists():
            return json.loads(_VERSION_JSON.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _load_downloads() -> list:
    """Retorna links de utilidades cadastrados manualmente no config.json."""
    s = _load_settings()
    path = Path(s["config_path"])
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8-sig")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            cleaned = re.sub(r"//[^\n]*", "", text)
            data = json.loads(cleaned)
        return [d for d in (data.get("Downloads") or []) if not d.get("_auto")]
    except Exception:
        return []


def _save_downloads(downloads: list) -> None:
    """Persiste a lista de downloads no config.json."""
    s = _load_settings()
    path = Path(s["config_path"])
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8-sig")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            cleaned = re.sub(r"//[^\n]*", "", text)
            data = json.loads(cleaned)
        data["Downloads"] = downloads
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        log.error("Erro ao salvar downloads: %s", exc)


_DEFAULT_FEATURED_MAPS_INTRO = (
    "O ARKLAND não é só mais um cluster — somos um ecossistema construído em torno de mapas MOD "
    "de alta qualidade. A maioria dos nossos servidores roda cenários customizados, curados à mão "
    "para PvE/PvP, performance em dedicado e integração total com eventos sazonais."
)


def _default_featured_maps() -> list[dict[str, Any]]:
    return [
        {
            "id": "brighamia",
            "name": "Brighamia",
            "mod_map": True,
            "description": (
                "Mapa mod de alta qualidade — paisagens únicas, exploração recompensadora e "
                "ótimo desempenho em servidor dedicado. Uma das joias do nosso cluster."
            ),
            "sort_order": 0,
            "enabled": True,
        },
        {
            "id": "alps",
            "name": "Alps",
            "mod_map": True,
            "description": (
                "Mapa mod alpino com biomas dramáticos, rotas de voo desafiadoras e bases "
                "espetaculares. Excelente para tribos que buscam cenário épico e variedade."
            ),
            "sort_order": 1,
            "enabled": True,
        },
        {
            "id": "the_volcano",
            "name": "The Volcano",
            "mod_map": True,
            "description": (
                "Mapa mod vulcânico com biomas extremos, recursos únicos e desafio constante — "
                "ideal para tribos que buscam risco e recompensa."
            ),
            "sort_order": 2,
            "enabled": True,
        },
        {
            "id": "amissa",
            "name": "Amissa",
            "mod_map": True,
            "description": (
                "Mapa mod com paisagens variadas e exploração profunda, integrado ao cluster "
                "com rates e eventos sazonais do ARKLAND."
            ),
            "sort_order": 3,
            "enabled": True,
        },
        {
            "id": "crystal_isles",
            "name": "Crystal Isles",
            "mod_map": False,
            "description": (
                "Mapa oficial com ilhas flutuantes, biomas cristalinos e criaturas exclusivas. "
                "Um dos cenários vanilla mais impressionantes — integrado ao cluster com rates ARKLAND."
            ),
            "sort_order": 4,
            "enabled": True,
        },
        {
            "id": "genesis_2",
            "name": "Genesis 2",
            "mod_map": False,
            "description": (
                "Mapa oficial de endgame com bioma espacial, missões e conteúdo Tek avançado. "
                "Complementa o cluster com a progressão completa da expansão Genesis Part 2."
            ),
            "sort_order": 5,
            "enabled": True,
        },
    ]


def _read_catalog_data() -> dict[str, Any]:
    s = _load_settings()
    path = Path(s.get("config_path") or "")
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8-sig")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            cleaned = re.sub(r"//[^\n]*", "", text)
            return json.loads(cleaned)
    except Exception:
        return {}


def _write_catalog_data(data: dict[str, Any]) -> bool:
    s = _load_settings()
    path = Path(s.get("config_path") or "")
    if not path.is_file():
        return False
    try:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        _invalidate_shop_config_cache()
        return True
    except Exception as exc:
        log.error("Erro ao salvar config catálogo: %s", exc)
        return False


def _load_featured_maps_raw() -> list[dict[str, Any]]:
    data = _read_catalog_data()
    raw = data.get("FeaturedMaps")
    if not isinstance(raw, list) or not raw:
        return deepcopy(_default_featured_maps())
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        out.append({
            "id": str(item.get("id") or name.lower().replace(" ", "_"))[:48],
            "name": name,
            "mod_map": bool(item.get("mod_map", False)),
            "description": str(item.get("description") or "").strip(),
            "sort_order": int(item.get("sort_order", 0) or 0),
            "enabled": item.get("enabled", True) is not False,
        })
    out.sort(key=lambda m: (int(m.get("sort_order", 0) or 0), m.get("name", "")))
    defaults = _default_featured_maps()
    known_ids = {m["id"] for m in out}
    for default_map in defaults:
        if default_map["id"] not in known_ids:
            out.append(deepcopy(default_map))
    out.sort(key=lambda m: (int(m.get("sort_order", 0) or 0), m.get("name", "")))
    return out or deepcopy(_default_featured_maps())


def _save_featured_maps(maps: list[dict[str, Any]]) -> bool:
    data = _read_catalog_data()
    if not data:
        return False
    data["FeaturedMaps"] = maps
    return _write_catalog_data(data)


def _featured_maps_section_meta() -> dict[str, str]:
    data = _read_catalog_data()
    settings = data.get("Settings") or {}
    return {
        "title": str(settings.get("HomeMapsTitle") or "Mapas do cluster").strip(),
        "intro": str(settings.get("HomeMapsIntro") or _DEFAULT_FEATURED_MAPS_INTRO).strip(),
    }


def _load_featured_maps_public() -> list[dict[str, Any]]:
    return [
        {
            "name": m.get("name", ""),
            "mod_map": bool(m.get("mod_map", False)),
            "description": m.get("description", ""),
        }
        for m in _load_featured_maps_raw()
        if m.get("enabled", True) is not False
    ]


@app.route("/api/featured-maps", methods=["GET"])
def get_featured_maps():
    return jsonify({"ok": True, "maps": _load_featured_maps_public()})


@app.route("/api/featured-maps/admin", methods=["GET"])
@admin_required
def get_featured_maps_admin():
    section = _featured_maps_section_meta()
    return jsonify({
        "ok": True,
        "maps": _load_featured_maps_raw(),
        "section": section,
    })


@app.route("/api/featured-maps/settings", methods=["PUT"])
@admin_required
def save_featured_maps_settings():
    body = request.get_json(force=True, silent=True) or {}
    data = _read_catalog_data()
    if not data:
        return jsonify({"ok": False, "error": "config.json não encontrado"}), 400
    settings = data.setdefault("Settings", {})
    if "title" in body:
        settings["HomeMapsTitle"] = str(body.get("title") or "").strip()
    if "intro" in body:
        settings["HomeMapsIntro"] = str(body.get("intro") or "").strip()
    if not _write_catalog_data(data):
        return jsonify({"ok": False, "error": "Falha ao salvar config"}), 500
    return jsonify({"ok": True, "section": _featured_maps_section_meta()})


@app.route("/api/featured-maps", methods=["POST"])
@admin_required
def create_featured_map():
    body = request.get_json(force=True, silent=True) or {}
    name = str(body.get("name", "")).strip()
    if not name:
        return jsonify({"ok": False, "error": "name é obrigatório"}), 400
    import uuid as _uuid
    maps = _load_featured_maps_raw()
    entry = {
        "id": str(body.get("id") or _uuid.uuid4().hex[:8]),
        "name": name,
        "mod_map": body.get("mod_map", True) is not False,
        "description": str(body.get("description", "")).strip(),
        "sort_order": int(body.get("sort_order", len(maps)) or 0),
        "enabled": body.get("enabled", True) is not False,
    }
    existing_ids = {m.get("id") for m in maps}
    while entry["id"] in existing_ids:
        entry["id"] = _uuid.uuid4().hex[:8]
    maps.append(entry)
    if not _save_featured_maps(maps):
        return jsonify({"ok": False, "error": "Falha ao salvar"}), 500
    _log("featured_map_created", id=entry["id"], name=name, admin=_steam_id_from_session())
    return jsonify({"ok": True, "map": entry})


@app.route("/api/featured-maps/<map_id>", methods=["PUT"])
@admin_required
def update_featured_map(map_id: str):
    body = request.get_json(force=True, silent=True) or {}
    maps = _load_featured_maps_raw()
    for i, m in enumerate(maps):
        if m.get("id") == map_id:
            maps[i] = {
                "id": map_id,
                "name": str(body.get("name", m.get("name", ""))).strip(),
                "mod_map": body.get("mod_map", m.get("mod_map", True)) is not False,
                "description": str(body.get("description", m.get("description", ""))).strip(),
                "sort_order": int(body.get("sort_order", m.get("sort_order", 0)) or 0),
                "enabled": body.get("enabled", m.get("enabled", True)) is not False,
            }
            if not _save_featured_maps(maps):
                return jsonify({"ok": False, "error": "Falha ao salvar"}), 500
            _log("featured_map_updated", id=map_id, admin=_steam_id_from_session())
            return jsonify({"ok": True, "map": maps[i]})
    return jsonify({"ok": False, "error": "Mapa não encontrado"}), 404


@app.route("/api/featured-maps/<map_id>", methods=["DELETE"])
@admin_required
def delete_featured_map(map_id: str):
    maps = _load_featured_maps_raw()
    new_list = [m for m in maps if m.get("id") != map_id]
    if len(new_list) == len(maps):
        return jsonify({"ok": False, "error": "Mapa não encontrado"}), 404
    if not _save_featured_maps(new_list):
        return jsonify({"ok": False, "error": "Falha ao salvar"}), 500
    _log("featured_map_deleted", id=map_id, admin=_steam_id_from_session())
    return jsonify({"ok": True, "removed": 1})


@app.route("/api/downloads", methods=["GET"])
def get_downloads():
    """Retorna links de download (público)."""
    return jsonify({"ok": True, "downloads": _load_downloads()})


@app.route("/api/downloads", methods=["POST"])
@admin_required
def create_download():
    """Cria um novo link de download."""
    body = request.get_json(force=True, silent=True) or {}
    label = str(body.get("label", "")).strip()
    url   = str(body.get("url",   "")).strip()
    if not label or not url:
        return jsonify({"ok": False, "error": "label e url são obrigatórios"}), 400
    import uuid as _uuid
    entry = {
        "id":          body.get("id") or _uuid.uuid4().hex[:8],
        "label":       label,
        "description": str(body.get("description", "")).strip(),
        "url":         url,
        "icon":        str(body.get("icon", "link")).strip() or "link",
        "category":    str(body.get("category", "Geral")).strip() or "Geral",
    }
    downloads = _load_downloads()
    # Garante que o id é único
    existing_ids = {d.get("id") for d in downloads}
    while entry["id"] in existing_ids:
        entry["id"] = _uuid.uuid4().hex[:8]
    downloads.append(entry)
    _save_downloads(downloads)
    _log("download_created", id=entry["id"], label=label, admin=_steam_id_from_session())
    return jsonify({"ok": True, "download": entry})


@app.route("/api/downloads/<dl_id>", methods=["PUT"])
@admin_required
def update_download(dl_id: str):
    """Atualiza um link de download existente."""
    body = request.get_json(force=True, silent=True) or {}
    downloads = _load_downloads()
    for i, d in enumerate(downloads):
        if d.get("id") == dl_id:
            downloads[i] = {
                "id":          dl_id,
                "label":       str(body.get("label", d.get("label", ""))).strip(),
                "description": str(body.get("description", d.get("description", ""))).strip(),
                "url":         str(body.get("url", d.get("url", ""))).strip(),
                "icon":        str(body.get("icon", d.get("icon", "link"))).strip() or "link",
                "category":    str(body.get("category", d.get("category", "Geral"))).strip() or "Geral",
            }
            _save_downloads(downloads)
            _log("download_updated", id=dl_id, admin=_steam_id_from_session())
            return jsonify({"ok": True, "download": downloads[i]})
    return jsonify({"ok": False, "error": "Download não encontrado"}), 404


@app.route("/api/downloads/<dl_id>", methods=["DELETE"])
@admin_required
def delete_download(dl_id: str):
    """Remove um link de download."""
    downloads = _load_downloads()
    new_list = [d for d in downloads if d.get("id") != dl_id]
    if len(new_list) == len(downloads):
        return jsonify({"ok": False, "error": "Download não encontrado"}), 404
    _save_downloads(new_list)
    _log("download_deleted", id=dl_id, admin=_steam_id_from_session())
    return jsonify({"ok": True})


# ── Versão / release info (público) ──────────────────────────────────────────

@app.route("/api/version", methods=["GET"])
def get_version():
    """Retorna a versão atual do projeto e o link de download do instalador."""
    return jsonify(_get_project_release())


# ── Admin: pontos e entregas (banco + fila plugin) ────────────────────────────

@app.route("/api/admin/points", methods=["POST"])
@admin_required
@limiter.limit("60 per hour")
def admin_points():
    body = request.get_json(force=True)
    action = str(body.get("action", "get")).strip().lower()
    steam_id = str(body.get("steam_id") or body.get("player") or "").strip()
    amount = int(body.get("amount", 0) or 0)
    result = _admin_points_action(action, steam_id, amount)
    status = 200 if result.get("ok") else 400 if "inválida" in str(result.get("error", "")).lower() else 500
    return jsonify(result), status


@app.route("/api/admin/deliver", methods=["POST"])
@admin_required
def admin_deliver():
    return _admin_deliver_order()


@app.route("/api/rcon/status", methods=["GET"])
@admin_required
@limiter.limit("60 per minute")
def rcon_status():
    s = _load_settings()
    server_id = str(request.args.get("server_id") or "").strip() or None
    host, port, password, label = _resolve_rcon_target(server_id, s)
    ok, message = _rcon_test_connection(host, port, password)
    return jsonify({
        "ok": ok,
        "connected": ok,
        "server": label,
        "host": host,
        "port": port,
        "message": message,
    }), 200 if ok else 503


@app.route("/api/rcon/reload", methods=["POST"])
@admin_required
@limiter.limit("30 per hour")
def rcon_reload():
    s = _load_settings()
    body = request.get_json(silent=True) or {}
    server_id = str(body.get("server_id") or "").strip() or None
    if server_id:
        host, port, password, label = _resolve_rcon_target(server_id, s)
        try:
            resp = _rcon_command(host, port, password, "Shop.Reload", connect_retries=5)
            results = [{"server_id": server_id, "label": label, "ok": True, "response": resp[:200]}]
        except Exception as exc:
            results = [{"server_id": server_id, "label": label, "ok": False, "error": str(exc)}]
    else:
        results = _reload_all_plugins(s)
    ok_count = sum(1 for r in results if r.get("ok"))
    all_ok = ok_count == len(results) and bool(results)
    _log("rcon_reload", admin=_steam_id_from_session(), ok=ok_count, total=len(results))
    return jsonify({
        "ok": all_ok or ok_count > 0,
        "results": results,
        "reload_count": ok_count,
        "reload_total": len(results),
    }), 200 if all_ok or ok_count > 0 else 500


@app.route("/api/rcon/points", methods=["POST"])
@admin_required
@limiter.limit("60 per hour")
def rcon_points():
    body = request.get_json(force=True)
    result = _admin_points_action(
        str(body.get("action", "get")).strip().lower(),
        str(body.get("player") or body.get("steam_id") or "").strip(),
        int(body.get("amount", 0) or 0),
    )
    status = 200 if result.get("ok") else 400 if "inválida" in str(result.get("error", "")).lower() else 500
    return jsonify(result), status


@app.route("/api/rcon/command", methods=["POST"])
@admin_required
@limiter.limit("60 per minute; 300 per hour")
def rcon_custom():
    s = _load_settings()
    body = request.get_json(force=True)
    cmd = str(body.get("command", "")).strip()
    server_id = str(body.get("server_id") or "").strip() or None
    if not cmd:
        return jsonify({"ok": False, "error": "Comando vazio"}), 400
    blocked = _rcon_command_blocked_reason(cmd)
    if blocked:
        return jsonify({"ok": False, "error": blocked}), 400
    host, port, password, label = _resolve_rcon_target(server_id, s)
    try:
        resp = _rcon_command(host, port, password, cmd)
        return jsonify({"ok": True, "response": resp, "server": label})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc), "server": label}), 500


@app.route("/api/rcon/purchase", methods=["POST"])
@admin_required
def rcon_purchase_admin():
    return _admin_deliver_order()


def _admin_deliver_order():
    body = request.get_json(force=True)
    steam_id = str(body.get("steam_id", "")).strip()
    item_id = str(body.get("item_id", "")).strip()
    item_type = str(body.get("item_type", "shop")).strip() or "shop"
    amount = int(body.get("amount", 1))

    if (err := _require_db()) is not None:
        return err

    order, error = _create_order(steam_id, item_type, item_id, amount)
    if error:
        return jsonify({"ok": False, "error": error}), 400
    assert order is not None
    result = _process_order_delivery(order.order_id)
    result["order_id"] = order.order_id
    return jsonify(result), 200 if result.get("ok") else 500


# ── Player routes ─────────────────────────────────────────────────────────────

def _purchase_user_message(
    result: dict[str, Any],
    *,
    item_type: str,
    item_id: str,
    price: int,
) -> str:
    """Mensagem amigável em PT-BR para o jogador após tentativa de resgate."""
    if result.get("ok"):
        if result.get("queued"):
            kind = "kit" if item_type == "kit" else "item"
            return (
                f"Resgate de {kind} «{item_id}» registrado! Entre no servidor ARKLAND — "
                "os itens serão entregues automaticamente na Nuvem (/shop)."
            )
        if result.get("skipped"):
            return "Este pedido já foi entregue anteriormente."
        return f"Resgate concluído: {item_id}."
    err = str(result.get("error") or "").strip()
    low = err.lower()
    if "saldo" in low or "insufficient" in low or "afford" in low:
        return err or "Saldo de Âmbares insuficiente para este resgate."
    if "licen" in low or "permission" in low:
        return err or "Você não possui a licença necessária para este item ou kit."
    if "não encontrado" in low or "not found" in low or "unknown" in low:
        label = "Kit" if item_type == "kit" else "Item"
        return err or f"{label} «{item_id}» não encontrado no catálogo da loja."
    if "duplicad" in low or "idempotency" in low:
        return "Este resgate já foi processado — verifique Minha Área."
    if "rcon" in low or "connection" in low or "timeout" in low:
        return (
            "Servidor indisponível no momento. Seu pedido ficou pendente — "
            "entre no jogo ou tente novamente em alguns minutos."
        )
    if "invent" in low or "weight" in low or "encumber" in low:
        return "Inventário cheio ou sobrecarregado — libere espaço e entre no servidor."
    if err:
        return err
    if price > 0:
        return f"Não foi possível concluir o resgate de «{item_id}». Verifique Minha Área ou contate um admin."
    return f"Falha ao resgatar «{item_id}». Tente novamente ou contate um admin."


@app.route("/api/player/purchase", methods=["POST"])
@login_required
@limiter.limit("10 per minute; 50 per hour")
def player_purchase():
    body = request.get_json(force=True)
    steam_id = _steam_id_from_session()
    if (dn_err := _guard_player_display_name(str(steam_id))) is not None:
        return dn_err
    item_id = str(body.get("item_id", "")).strip()
    item_type = str(body.get("item_type", "shop")).strip() or "shop"
    amount = int(body.get("amount", 1))

    if (err := _require_db()) is not None:
        return err

    idempotency_key = str(body.get("idempotency_key", "")).strip()
    if idempotency_key:
        if not _check_idempotency(idempotency_key):
            _log("purchase_duplicate_idempotency", steam_id=str(steam_id),
                 idempotency_key=idempotency_key)
            return jsonify({"ok": False, "error": "Pedido duplicado — este resgate já foi processado",
                           "idempotency_key": idempotency_key}), 409

    entry = _catalog_entry("kit" if item_type == "kit" else "shop", item_id)
    if not entry:
        if idempotency_key:
            _used_idempotency_keys.pop(idempotency_key, None)
        resolved = _resolve_catalog_item_id(item_type, item_id)
        hint = f" (tentou também '{resolved}')" if resolved != item_id else ""
        return jsonify({"ok": False, "error": f"Item não encontrado no catálogo{hint}"}), 404

    lic = _get_license_grant(entry)
    if str(entry.get("Type", "")).strip().lower() == "license" and not lic:
        if idempotency_key:
            _used_idempotency_keys.pop(idempotency_key, None)
        return jsonify({
            "ok": False,
            "error": "Item de licença mal configurado (sem LicenseGrant no catálogo). Contate um admin.",
        }), 500

    if lic and (lic.get("AdminOnly") or lic.get("Redeemable") is False):
        if idempotency_key:
            _used_idempotency_keys.pop(idempotency_key, None)
        return jsonify({"ok": False, "error": "Esta licença não pode ser resgatada na loja"}), 403

    can_buy, missing = _check_entry_permissions(str(steam_id), entry)
    if not can_buy:
        if idempotency_key:
            _used_idempotency_keys.pop(idempotency_key, None)
        need = ", ".join(missing)
        return jsonify({
            "ok": False,
            "error": f"Licença necessária: {need}",
            "missing_licenses": missing,
        }), 403

    price = _catalog_price(entry, amount)
    if price > 0:
        balance = _get_player_points(str(steam_id))
        if balance is not None and balance < price:
            if idempotency_key:
                _used_idempotency_keys.pop(idempotency_key, None)
            return jsonify({
                "ok": False,
                "error": f"Saldo insuficiente ({balance} pts, necessário {price} pts)",
            }), 402

    order, error = _create_order(str(steam_id), item_type, item_id, amount, points_spent=price)
    if error:
        if idempotency_key:
            _used_idempotency_keys.pop(idempotency_key, None)
        return jsonify({"ok": False, "error": error}), 400
    assert order is not None

    db = _SessionLocal()
    purchase_db_error: str | None = None
    try:
        if price > 0:
            if _is_mysql_engine(db):
                debit_sql = (
                    "UPDATE players SET points = GREATEST(0, points - :price) "
                    "WHERE steam_id = :sid AND points >= :price"
                )
            else:
                debit_sql = (
                    "UPDATE players SET points = MAX(points - :price, 0) "
                    "WHERE steam_id = :sid AND points >= :price"
                )
            updated = db.execute(
                text(debit_sql),
                {"price": price, "sid": str(steam_id)},
            )
            if int(getattr(updated, "rowcount", 0) or 0) <= 0:
                row = db.execute(
                    text("SELECT points FROM players WHERE steam_id = :sid"),
                    {"sid": str(steam_id)},
                ).fetchone()
                balance_now = int(row[0]) if row else 0
                db.rollback()
                if idempotency_key:
                    _used_idempotency_keys.pop(idempotency_key, None)
                return jsonify({
                    "ok": False,
                    "error": f"Saldo insuficiente ({balance_now} pts, necessário {price} pts)",
                }), 402

        if lic and lic.get("Redeemable", True):
            _apply_entitlement_grant_tx(
                db,
                str(steam_id),
                str(lic["Group"]),
                int(lic.get("Days", 30)),
                source=order.order_id,
                notes=f"web:{item_id}",
            )
        db.commit()
    except Exception as exc:
        db.rollback()
        purchase_db_error = str(exc)
        _log_error(
            "purchase_db_tx",
            steam_id=str(steam_id),
            item_id=item_id,
            order_id=order.order_id,
            error=purchase_db_error,
        )
    finally:
        db.close()

    if purchase_db_error:
        if idempotency_key:
            _used_idempotency_keys.pop(idempotency_key, None)
        return jsonify({
            "ok": False,
            "error": (
                "Não foi possível concluir o resgate da licença. "
                "Seu saldo não foi alterado — tente novamente em instantes."
            ),
            "detail": purchase_db_error,
        }), 500

    result = _process_order_delivery(order.order_id)
    result["order_id"] = order.order_id
    result["new_balance"] = _get_player_points(str(steam_id))
    result["points_spent"] = price
    result["user_message"] = _purchase_user_message(
        result, item_type=item_type, item_id=item_id, price=price,
    )
    if not result.get("error") and not result.get("ok"):
        result["error"] = result["user_message"]
    new_balance = result.get("new_balance")
    purchase_ok = bool(result.get("ok"))
    _audit_event(
        "purchase_created" if purchase_ok else "purchase_failed",
        severity="info" if purchase_ok else "error",
        actor_type="player",
        actor_steam_id=str(steam_id),
        target_steam_id=str(steam_id),
        order_id=order.order_id,
        server_id=order.server_id,
        item_type=item_type,
        item_id=item_id,
        amount=amount,
        status_after=order.status,
        message=result.get("user_message") or f"Resgate: {item_id}",
        price=price,
        idempotency_key=idempotency_key or None,
        points_after=new_balance,
        delivery_mode=result.get("delivery_mode"),
        queued=result.get("queued"),
        error=result.get("error") if not result.get("ok") else None,
    )
    return jsonify(result), 200 if result.get("ok") else 500


@app.route("/api/player/orders/<order_id>/cancel", methods=["POST"])
@login_required
@limiter.limit("20 per minute")
def player_cancel_order(order_id: str):
    """Desistência — cancela pedido PENDENTE e reembolsa Âmbar."""
    if (err := _require_db()) is not None:
        return err
    steam_id = str(_steam_id_from_session())
    if (dn_err := _guard_player_display_name(steam_id)) is not None:
        return dn_err
    db = _SessionLocal()
    try:
        order = (
            db.query(Order)
            .filter(Order.order_id == order_id, Order.steam_id == steam_id)
            .with_for_update()
            .first()
        )
        if not order:
            return jsonify({"ok": False, "error": "Pedido não encontrado"}), 404
        if order.status != "PENDENTE":
            return jsonify({
                "ok": False,
                "error": "Só é possível desistir de resgates ainda pendentes (aguardando entrada no servidor)",
            }), 409

        item_type = str(order.item_type or "shop")
        item_id = str(order.item_id or "")
        order_amount = int(order.amount or 1)

        refund = int(order.points_spent or 0)
        if refund <= 0:
            entry = _catalog_entry(
                "kit" if item_type == "kit" else "shop",
                item_id,
            )
            refund = _catalog_price(entry, order_amount)

        new_balance: int | None = None
        if refund > 0:
            new_balance = _add_player_points_tx(db, steam_id, refund)
        else:
            row = db.execute(
                text("SELECT points FROM players WHERE steam_id = :sid"),
                {"sid": steam_id},
            ).fetchone()
            new_balance = int(row[0]) if row else 0

        order.status = "CANCELADO"
        order.updated_at = _now()
        _revoke_entitlement_for_order(steam_id, order_id, db=db)
        db.commit()
    except Exception as exc:
        db.rollback()
        _log_error("player_cancel_order", order_id=order_id, steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        db.close()

    if new_balance is None:
        new_balance = _get_player_points(steam_id)

    _audit_event(
        "order_cancelled",
        actor_type="player",
        actor_steam_id=steam_id,
        target_steam_id=steam_id,
        order_id=order_id,
        item_type=item_type,
        item_id=item_id,
        status_before="PENDENTE",
        status_after="CANCELADO",
        message=f"Desistência — reembolso de {refund} Âmbar",
        price=refund,
        points_after=new_balance,
    )
    return jsonify({
        "ok": True,
        "order_id": order_id,
        "status": "CANCELADO",
        "refunded": refund,
        "new_balance": new_balance,
    })


@app.route("/api/player/entitlements", methods=["GET"])
@login_required
def player_entitlements():
    steam_id = str(_steam_id_from_session())
    ents = _get_player_entitlements(steam_id)
    groups = [e["group"] for e in ents]
    return jsonify({
        "ok": True,
        "entitlements": ents,
        "timed_points_total": _compute_timed_points_total(groups),
        "timed_points_interval_min": 30,
    })


@app.route("/api/player/points", methods=["GET"])
@login_required
def player_points():
    steam_id = str(_steam_id_from_session())
    if not _db_ready():
        return jsonify({
            "ok": False,
            "error": "Banco temporariamente indisponível. Recarregue em alguns segundos.",
            "db_offline": True,
        }), 503
    try:
        balance = _get_player_points(steam_id)
    except Exception as exc:
        _log_error("player_points", steam_id=steam_id, error=str(exc))
        return jsonify({
            "ok": False,
            "error": "Não foi possível consultar seu saldo. Tente novamente.",
            "db_offline": True,
        }), 503
    if balance is None:
        return jsonify({
            "ok": False,
            "error": "Saldo indisponível no momento. Tente novamente.",
            "db_offline": True,
        }), 503
    return jsonify({"ok": True, "steam_id": steam_id, "points": balance})


def _describe_catalog_entry(item_type: str, item_id: str) -> dict[str, Any]:
    data = _read_shop_config()
    if item_type == "kit":
        entry = (data.get("Kits") or {}).get(item_id) or {}
    else:
        entry = (data.get("Items") or data.get("ShopItems") or {}).get(item_id) or {}
    return {
        "name": entry.get("Description") or item_id,
        "description": entry.get("Description") or "",
        "price": int(entry.get("Price", 0) or 0),
        "type": entry.get("Type") or ("kit" if item_type == "kit" else "item"),
    }


def _resolve_payment_method(row: PointPayment) -> str:
    """Retorna 'pix' ou 'card' — usa coluna persistida ou infere por dados legados."""
    pm = str(row.payment_method or "").strip().lower()
    if pm in ("pix", "card"):
        return pm
    if row.pix_copy_paste or row.pix_qr_base64:
        return "pix"
    return "card"


def _finalize_pix_payment(db: Any, payment: PointPayment, mp_status: str, *, source: str = "web") -> None:
    mapped = map_mp_status(mp_status)
    locked = (
        db.query(PointPayment)
        .filter(PointPayment.payment_id == payment.payment_id)
        .with_for_update()
        .first()
    )
    if not locked:
        return
    payment = locked
    payment_id = payment.payment_id
    old_status = payment.status
    if payment.status == "ABANDONADO" and mapped == "PENDENTE":
        return
    payment.status = mapped
    payment.updated_at = _now()
    if old_status != mapped:
        _audit_event(
            "pix_status_updated",
            actor_steam_id=payment.steam_id,
            order_id=payment.payment_id,
            item_id=payment.package_id,
            amount=payment.points,
            status_before=old_status,
            status_after=mapped,
            message=f"Doação {old_status} → {mapped}",
            source=source,
            mp_payment_id=payment.mp_payment_id,
            mp_status_raw=mp_status,
            amount_brl=payment.amount_brl,
            package_label=_package_label(payment.package_id),
            credited=payment.credited,
            payment_method=_resolve_payment_method(payment),
            persist=False,
        )
        payment = (
            db.query(PointPayment)
            .filter(PointPayment.payment_id == payment_id)
            .with_for_update()
            .first()
        )
        if not payment:
            return
    if mapped == "APROVADO" and not payment.credited:
        try:
            new_balance = _add_player_points_tx(db, payment.steam_id, payment.points)
            payment.credited = True
            pm = _resolve_payment_method(payment)
            _audit_event(
                "pix_credited",
                actor_steam_id=payment.steam_id,
                order_id=payment.payment_id,
                item_id=payment.package_id,
                amount=payment.points,
                status_after="APROVADO",
                message=f"Doação creditada ({pm}) — {_package_label(payment.package_id)}",
                source=source,
                mp_payment_id=payment.mp_payment_id,
                amount_brl=payment.amount_brl,
                new_balance=new_balance,
                package_label=_package_label(payment.package_id),
                payment_method=pm,
                persist=False,
            )
            _log(
                "pix_credited",
                payment_id=payment.payment_id,
                steam_id=payment.steam_id,
                points=payment.points,
                new_balance=new_balance,
            )
        except Exception as exc:
            _audit_event(
                "pix_credit_failed",
                severity="error",
                actor_steam_id=payment.steam_id,
                order_id=payment.payment_id,
                item_id=payment.package_id,
                amount=payment.points,
                status_after=mapped,
                message=f"Falha ao creditar Âmbares: {exc}",
                source=source,
                mp_payment_id=payment.mp_payment_id,
                amount_brl=payment.amount_brl,
                error=str(exc),
                persist=False,
            )
            _log_error(
                "pix_credit_failed",
                payment_id=payment.payment_id,
                steam_id=payment.steam_id,
                points=payment.points,
                error=str(exc),
            )
            raise


@app.route("/api/player/available", methods=["GET"])
@login_required
def player_available():
    """Itens/kits pendentes de resgate e ofertas gratuitas."""
    if (err := _require_db()) is not None:
        return err
    steam_id = str(_steam_id_from_session())
    db = _SessionLocal()
    try:
        pending_rows = (
            db.query(Order)
            .filter(Order.steam_id == steam_id, Order.status == "PENDENTE")
            .order_by(Order.created_at.desc())
            .limit(100)
            .all()
        )
        pending = []
        for row in pending_rows:
            meta = _describe_catalog_entry(row.item_type, row.item_id)
            pending.append({
                "order_id": row.order_id,
                "item_type": row.item_type,
                "item_id": row.item_id,
                "amount": row.amount,
                "status": row.status,
                "points_spent": int(row.points_spent or 0),
                "can_cancel": row.status == "PENDENTE",
                "name": meta["name"],
                "description": meta["description"],
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })

        redeemable: list[dict[str, Any]] = []
        cfg = _read_shop_config()
        for key, itm in (cfg.get("Items") or cfg.get("ShopItems") or {}).items():
            if not isinstance(itm, dict):
                continue
            price = int(itm.get("Price", 0) or 0)
            if price == 0:
                redeemable.append({
                    "key": key,
                    "catalog_kind": "item",
                    "purchase_type": "shop",
                    "name": itm.get("Description") or key,
                    "description": itm.get("Description") or "",
                    "price": 0,
                    "type": itm.get("Type") or "item",
                })
        for key, kit in (cfg.get("Kits") or {}).items():
            if not isinstance(kit, dict):
                continue
            price = int(kit.get("Price", 0) or 0)
            if price == 0:
                redeemable.append({
                    "key": key,
                    "catalog_kind": "kit",
                    "purchase_type": "kit",
                    "name": kit.get("Description") or key,
                    "description": kit.get("Description") or "",
                    "price": 0,
                    "type": "kit",
                })

        return jsonify({"ok": True, "pending": pending, "redeemable": redeemable})
    except Exception as exc:
        _log_error("player_available", steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/player/pix/payer-form", methods=["GET"])
@login_required
def player_pix_payer_form():
    """Campos exigidos ao jogador antes de gerar PIX (Mercado Pago / Brasil)."""
    return jsonify({"ok": True, "fields": PIX_PAYER_FORM})


@app.route("/api/player/pix/checkout", methods=["POST"])
@login_required
@limiter.limit("5 per minute; 20 per hour")
def player_pix_checkout():
    if (err := _require_db()) is not None:
        return err
    steam_id = str(_steam_id_from_session())
    if (dn_err := _guard_player_display_name(steam_id)) is not None:
        return dn_err
    if not _pix_enabled():
        return jsonify({"ok": False, "error": "Doação PIX não configurada (indisponível)"}), 503

    body = request.get_json(force=True, silent=True) or {}
    package_id = str(body.get("package_id", "")).strip()
    packages = _load_point_packages()
    package = next((p for p in packages if str(p.get("id")) == package_id), None)
    if not package:
        return jsonify({"ok": False, "error": "Pacote de pontos inválido"}), 400

    try:
        payer = normalize_payer_input(body.get("payer"))
    except PayerValidationError as exc:
        return jsonify({"ok": False, "error": str(exc), "field": exc.field}), 400

    points = int(package.get("points", 0) or 0)
    price_brl = float(package.get("price_brl", 0) or 0)
    if points <= 0 or price_brl <= 0:
        return jsonify({"ok": False, "error": "Pacote mal configurado"}), 400

    steam_id = str(_steam_id_from_session())
    payment_id = str(uuid.uuid4())
    label = str(package.get("label") or f"{points:,}".replace(",", ".") + f" {_AMBER_SINGULAR if points == 1 else _AMBER_PLURAL}")
    description = f"Doação ARKLAND — {label} ({steam_id})"

    try:
        mp_resp = create_pix_payment(
            _get_mp_access_token(),
            amount_brl=price_brl,
            description=description,
            external_reference=payment_id,
            idempotency_key=payment_id,
            payer=payer,
        )
    except PixPaymentError as exc:
        _audit_event(
            "pix_checkout_failed",
            severity="error",
            actor_steam_id=steam_id,
            item_id=package_id,
            amount=points,
            message=f"Mercado Pago recusou checkout: {exc}",
            amount_brl=price_brl,
            package_label=label,
            error=str(exc),
        )
        return jsonify({"ok": False, "error": f"Mercado Pago: {exc}"}), 502

    mp_id, qr_b64, copy_paste = extract_pix_data(mp_resp)
    if not mp_id:
        return jsonify({"ok": False, "error": "Resposta PIX inválida do Mercado Pago"}), 502

    db = _SessionLocal()
    try:
        row = PointPayment(
            payment_id=payment_id,
            mp_payment_id=mp_id,
            steam_id=steam_id,
            package_id=package_id,
            amount_brl=price_brl,
            points=points,
            status=map_mp_status(str(mp_resp.get("status", "pending"))),
            pix_qr_base64=qr_b64,
            pix_copy_paste=copy_paste,
            payer_email=payer.get("email"),
            payment_method="pix",
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(row)
        db.commit()
        _audit_event(
            "pix_checkout_created",
            actor_steam_id=steam_id,
            order_id=payment_id,
            item_id=package_id,
            amount=points,
            status_after=row.status,
            message=f"Tentativa PIX — {label} — R$ {price_brl:.2f}",
            amount_brl=price_brl,
            mp_payment_id=mp_id,
            payer_email=payer.get("email"),
            package_label=label,
            payment_method="pix",
        )
        _log("pix_checkout", payment_id=payment_id, steam_id=steam_id, package_id=package_id, mp_id=mp_id)
        return jsonify({
            "ok": True,
            "payment_id": payment_id,
            "mp_payment_id": mp_id,
            "status": row.status,
            "points": points,
            "amount_brl": price_brl,
            "label": label,
            "pix_qr_base64": qr_b64,
            "pix_copy_paste": copy_paste,
        })
    except Exception as exc:
        db.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        db.close()


def _resolve_point_package(package_id: str) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve pacote pelo id — preço e pontos sempre do servidor."""
    pid = str(package_id or "").strip()
    if not pid:
        return None, "Pacote de pontos inválido"
    package = next((p for p in _load_point_packages() if str(p.get("id")) == pid), None)
    if not package:
        return None, "Pacote de pontos inválido"
    points = int(package.get("points", 0) or 0)
    price_brl = float(package.get("price_brl", 0) or 0)
    if points <= 0 or price_brl <= 0:
        return None, "Pacote mal configurado"
    return package, None


@app.route("/api/player/card/checkout", methods=["POST"])
@login_required
@limiter.limit("5 per minute; 20 per hour")
def player_card_checkout():
    if (err := _require_db()) is not None:
        return err
    steam_id = str(_steam_id_from_session())
    if (dn_err := _guard_player_display_name(steam_id)) is not None:
        return dn_err
    if not _payments_enabled():
        return jsonify({"ok": False, "error": "Doação por cartão não configurada (indisponível)"}), 503

    body = request.get_json(force=True, silent=True) or {}
    package_id = str(body.get("package_id", "")).strip()
    package, pkg_err = _resolve_point_package(package_id)
    if pkg_err:
        return jsonify({"ok": False, "error": pkg_err}), 400

    try:
        payer = normalize_payer_input(body.get("payer"))
    except PayerValidationError as exc:
        return jsonify({"ok": False, "error": str(exc), "field": exc.field}), 400

    points = int(package.get("points", 0) or 0)
    price_brl = float(package.get("price_brl", 0) or 0)
    payment_id = str(uuid.uuid4())
    label = str(package.get("label") or f"{points:,}".replace(",", ".") + f" {_AMBER_SINGULAR if points == 1 else _AMBER_PLURAL}")
    description = f"Doação ARKLAND — {label} ({steam_id})"
    base = _build_base_url()
    back_urls = {
        "success": f"{base}/?mp_card_return=success",
        "failure": f"{base}/?mp_card_return=failure",
        "pending": f"{base}/?mp_card_return=pending",
    }

    try:
        mp_resp = create_card_checkout_preference(
            _get_mp_access_token(),
            amount_brl=price_brl,
            description=description,
            external_reference=payment_id,
            payer=payer,
            back_urls=back_urls,
        )
    except PixPaymentError as exc:
        _audit_event(
            "card_checkout_failed",
            severity="error",
            actor_steam_id=steam_id,
            item_id=package_id,
            amount=points,
            message=f"Mercado Pago recusou checkout cartão: {exc}",
            amount_brl=price_brl,
            package_label=label,
            error=str(exc),
        )
        return jsonify({"ok": False, "error": f"Mercado Pago: {exc}"}), 502

    checkout_url = extract_checkout_url(mp_resp, sandbox=_mp_sandbox())
    if not checkout_url:
        return jsonify({"ok": False, "error": "Resposta de checkout inválida do Mercado Pago"}), 502

    db = _SessionLocal()
    try:
        row = PointPayment(
            payment_id=payment_id,
            mp_payment_id=None,
            steam_id=steam_id,
            package_id=package_id,
            amount_brl=price_brl,
            points=points,
            status="PENDENTE",
            payer_email=payer.get("email"),
            payment_method="card",
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(row)
        db.commit()
        _audit_event(
            "card_checkout_created",
            actor_steam_id=steam_id,
            order_id=payment_id,
            item_id=package_id,
            amount=points,
            status_after=row.status,
            message=f"Tentativa cartão — {label} — R$ {price_brl:.2f}",
            amount_brl=price_brl,
            payer_email=payer.get("email"),
            package_label=label,
            payment_method="card",
        )
        _log("card_checkout", payment_id=payment_id, steam_id=steam_id, package_id=package_id)
        return jsonify({
            "ok": True,
            "payment_id": payment_id,
            "status": "PENDENTE",
            "points": points,
            "amount_brl": price_brl,
            "label": label,
            "checkout_url": checkout_url,
            "sandbox": bool(_mp_sandbox()),
        })
    except Exception as exc:
        db.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/player/pix/<payment_id>/status", methods=["GET"])
@login_required
@limiter.limit("20 per minute; 300 per hour", override_defaults=True)
def player_pix_status(payment_id: str):
    if (err := _require_db()) is not None:
        return err
    steam_id = str(_steam_id_from_session())
    db = _SessionLocal()
    try:
        payment = db.query(PointPayment).filter(
            PointPayment.payment_id == payment_id,
            PointPayment.steam_id == steam_id,
        ).first()
        if not payment:
            return jsonify({"ok": False, "error": "Doação não encontrada"}), 404

        mp_id_hint = str(request.args.get("mp_id", "")).strip()
        if mp_id_hint and not payment.mp_payment_id:
            payment.mp_payment_id = mp_id_hint
            payment.updated_at = _now()
            db.commit()

        poll_error = None
        mp_status_raw = None
        if payment.credited:
            pass
        elif payment.status == "APROVADO":
            try:
                _finalize_pix_payment(db, payment, "approved")
                db.commit()
            except Exception as exc:
                db.rollback()
                poll_error = str(exc)
                _log_error("pix_status_retry_credit", payment_id=payment_id, error=poll_error)
        elif payment.status not in ("RECUSADO", "EXPIRADO", "ESTORNADO", "ABANDONADO") and payment.mp_payment_id:
            token = _get_mp_access_token()
            if not token:
                poll_error = "Access Token do Mercado Pago não configurado"
            else:
                try:
                    mp_resp = fetch_payment(token, payment.mp_payment_id)
                    mp_status_raw = str(mp_resp.get("status", "") or "")
                    _finalize_pix_payment(db, payment, mp_status_raw)
                    db.commit()
                except PixPaymentError as exc:
                    poll_error = str(exc)
                    _log_error("pix_status_poll", payment_id=payment_id, error=poll_error)

        new_balance = _get_player_points(steam_id) if payment.credited else None
        return jsonify({
            "ok": True,
            "payment_id": payment.payment_id,
            "status": payment.status,
            "credited": payment.credited,
            "points": payment.points,
            "new_balance": new_balance,
            "mp_status": mp_status_raw,
            "poll_error": poll_error,
        })
    finally:
        db.close()


@app.route("/api/player/pix/<payment_id>/abandon", methods=["POST"])
@login_required
@limiter.limit("30 per hour")
def player_pix_abandon(payment_id: str):
    """Jogador fechou o modal PIX sem concluir a doação — rastreio para suporte."""
    if (err := _require_db()) is not None:
        return err
    steam_id = str(_steam_id_from_session())
    db = _SessionLocal()
    try:
        payment = db.query(PointPayment).filter(
            PointPayment.payment_id == payment_id,
            PointPayment.steam_id == steam_id,
        ).first()
        if not payment:
            return jsonify({"ok": False, "error": "Doação PIX não encontrada"}), 404
        if payment.credited or payment.status == "APROVADO":
            return jsonify({"ok": True, "ignored": True, "status": payment.status})
        if payment.status == "ABANDONADO":
            return jsonify({"ok": True, "status": payment.status})
        if payment.status not in ("PENDENTE",):
            return jsonify({"ok": True, "ignored": True, "status": payment.status})

        old_status = payment.status
        payment.status = "ABANDONADO"
        payment.updated_at = _now()
        db.commit()
        _audit_event(
            "pix_abandoned",
            severity="warn",
            actor_steam_id=steam_id,
            order_id=payment.payment_id,
            item_id=payment.package_id,
            amount=payment.points,
            status_before=old_status,
            status_after="ABANDONADO",
            message=f"Doação PIX abandonada pelo jogador — {_package_label(payment.package_id)}",
            amount_brl=payment.amount_brl,
            mp_payment_id=payment.mp_payment_id,
            package_label=_package_label(payment.package_id),
            payer_email=payment.payer_email,
        )
        return jsonify({"ok": True, "status": "ABANDONADO"})
    except Exception as exc:
        db.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/payments/webhook", methods=["GET", "POST"])
@limiter.limit("120 per hour")
def payments_webhook():
    """Webhook Mercado Pago — confirma PIX/cartão e credita pontos."""
    if request.method == "GET":
        # Validação de URL no painel MP ou IPN legado (?topic=payment&id=)
        return jsonify({"ok": True}), 200
    if (err := _require_db()) is not None:
        return err
    body = request.get_json(force=True, silent=True) or {}
    mp_id = str(body.get("data", {}).get("id") or body.get("id") or "").strip()
    if not mp_id:
        mp_id = str(request.args.get("data.id") or request.args.get("id") or "").strip()
    if not mp_id:
        return jsonify({"ok": True, "ignored": True})

    token = _get_mp_access_token()
    if not token:
        return jsonify({"ok": False, "error": "Pagamentos não configurados"}), 503

    try:
        mp_resp = fetch_payment(token, mp_id)
    except PixPaymentError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502

    external_ref = str(mp_resp.get("external_reference") or "").strip()
    db = _SessionLocal()
    try:
        payment = None
        if external_ref:
            payment = db.query(PointPayment).filter(PointPayment.payment_id == external_ref).first()
        if not payment:
            payment = db.query(PointPayment).filter(PointPayment.mp_payment_id == mp_id).first()
        if not payment:
            return jsonify({"ok": True, "ignored": True})

        payment_id_out = payment.payment_id
        needs_mp = not payment.mp_payment_id
        db.expunge(payment)
        if needs_mp:
            db.query(PointPayment).filter(PointPayment.payment_id == payment_id_out).update(
                {PointPayment.mp_payment_id: mp_id, PointPayment.updated_at: _now()},
                synchronize_session=False,
            )
        pay_row = db.query(PointPayment).filter(PointPayment.payment_id == payment_id_out).first()
        if not pay_row:
            return jsonify({"ok": True, "ignored": True})
        _finalize_pix_payment(db, pay_row, str(mp_resp.get("status", "")), source="webhook")
        db.commit()
        row = db.query(PointPayment).filter(PointPayment.payment_id == payment_id_out).first()
        return jsonify({
            "ok": True,
            "payment_id": payment_id_out,
            "status": row.status if row else "PENDENTE",
        })
    except Exception as exc:
        db.rollback()
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/player/summary", methods=["GET"])
@login_required
def player_summary():
    if (err := _require_db()) is not None:
        return err
    steam_id = str(_steam_id_from_session())
    db = _SessionLocal()
    try:
        total = db.query(Order).filter(Order.steam_id == steam_id).count()
        delivered = db.query(Order).filter(Order.steam_id == steam_id, Order.status == "ENTREGUE").count()
        pending = db.query(Order).filter(Order.steam_id == steam_id, Order.status == "PENDENTE").count()
        contested = db.query(Order).filter(Order.steam_id == steam_id, Order.contested.is_(True)).count()
        donations_total = db.query(PointPayment).filter(PointPayment.steam_id == steam_id).count()
        donations_credited = db.query(PointPayment).filter(
            PointPayment.steam_id == steam_id,
            PointPayment.credited.is_(True),
        ).count()
        balance = _get_player_points(steam_id)
        return jsonify({
            "ok": True,
            "steam_id": steam_id,
            "points": balance if balance is not None else 0,
            "stats": {
                "total_orders": total,
                "delivered": delivered,
                "pending": pending,
                "contested": contested,
                "donations_total": donations_total,
                "donations_credited": donations_credited,
            },
        })
    except Exception as exc:
        _log_error("player_summary", steam_id=steam_id, error=str(exc))
        err_str = str(exc)
        if "10061" in err_str or "Can't connect" in err_str or "Connection refused" in err_str:
            msg = "Banco de dados temporariamente offline. Aguarde alguns segundos e recarregue a página."
        else:
            msg = f"Erro ao consultar banco: {exc}"
        return jsonify({"ok": False, "error": msg, "db_offline": "10061" in err_str}), 503
    finally:
        db.close()


@app.route("/api/player/history", methods=["GET"])
@login_required
def player_history():
    if (err := _require_db()) is not None:
        return err
    steam_id = str(_steam_id_from_session())
    limit = max(1, min(100, int(request.args.get("limit", 20))))
    offset = max(0, int(request.args.get("offset", 0)))
    status_filter = str(request.args.get("status", "")).strip().upper()
    db = _SessionLocal()
    try:
        q = db.query(Order).filter(Order.steam_id == steam_id)
        if status_filter:
            q = q.filter(Order.status == status_filter)
        total = q.count()
        rows = q.order_by(Order.created_at.desc()).offset(offset).limit(limit).all()
        return jsonify(
            {
                "ok": True,
                "total": total,
                "items": [
                    {
                        "order_id": r.order_id,
                        "steam_id": r.steam_id,
                        "server_id": r.server_id,
                        "item_type": r.item_type,
                        "item_id": r.item_id,
                        "amount": r.amount,
                        "status": r.status,
                        "retry_count": r.retry_count,
                        "last_error": r.last_error,
                        "contested": r.contested,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                    }
                    for r in rows
                ],
            }
        )
    except Exception as exc:
        _log_error("player_history", steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": f"Erro ao consultar histórico: {exc}"}), 500
    finally:
        db.close()


@app.route("/api/player/donations", methods=["GET"])
@login_required
def player_donations():
    """Histórico de doações do jogador (PIX ou cartão — recompensa em pontos)."""
    if (err := _require_db()) is not None:
        return err
    steam_id = str(_steam_id_from_session())
    limit = max(1, min(100, int(request.args.get("limit", 20))))
    offset = max(0, int(request.args.get("offset", 0)))
    db = _SessionLocal()
    try:
        q = db.query(PointPayment).filter(PointPayment.steam_id == steam_id)
        total = q.count()
        rows = q.order_by(PointPayment.created_at.desc()).offset(offset).limit(limit).all()
        return jsonify({
            "ok": True,
            "total": total,
            "items": [
                {
                    "payment_id": r.payment_id,
                    "package_id": r.package_id,
                    "package_label": _package_label(r.package_id),
                    "amount_brl": r.amount_brl,
                    "points": r.points,
                    "status": r.status,
                    "credited": r.credited,
                    "payment_method": _resolve_payment_method(r),
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "credited_at": r.updated_at.isoformat() if r.credited and r.updated_at else None,
                }
                for r in rows
            ],
        })
    except Exception as exc:
        _log_error("player_donations", steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": f"Erro ao consultar doações: {exc}"}), 500
    finally:
        db.close()


@app.route("/api/player/orders/<order_id>", methods=["GET"])
@login_required
def player_order_detail(order_id: str):
    if (err := _require_db()) is not None:
        return err
    steam_id = str(_steam_id_from_session())
    db = _SessionLocal()
    try:
        order = db.query(Order).filter(Order.order_id == order_id, Order.steam_id == steam_id).first()
        if not order:
            return jsonify({"ok": False, "error": "Pedido não encontrado"}), 404

        attempts = (
            db.query(OrderAttempt)
            .filter(OrderAttempt.order_id == order_id)
            .order_by(OrderAttempt.attempted_at.desc())
            .limit(20)
            .all()
        )
        disputes = (
            db.query(Dispute)
            .filter(Dispute.order_id == order_id)
            .order_by(Dispute.created_at.desc())
            .all()
        )
        return jsonify(
            {
                "ok": True,
                "order": {
                    "order_id": order.order_id,
                    "server_id": order.server_id,
                    "item_type": order.item_type,
                    "item_id": order.item_id,
                    "amount": order.amount,
                    "status": order.status,
                    "retry_count": order.retry_count,
                    "contested": order.contested,
                    "last_error": order.last_error,
                    "original_order_id": order.original_order_id,
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                    "updated_at": order.updated_at.isoformat() if order.updated_at else None,
                },
                "attempts": [
                    {
                        "attempted_at": a.attempted_at.isoformat() if a.attempted_at else None,
                        "success": a.success,
                        "command": a.command,
                        "response": a.response,
                        "error": a.error,
                    }
                    for a in attempts
                ],
                "disputes": [
                    {
                        "reason": d.reason,
                        "status": d.status,
                        "created_at": d.created_at.isoformat() if d.created_at else None,
                    }
                    for d in disputes
                ],
            }
        )
    except Exception as exc:
        _log_error("player_order_detail", order_id=order_id, error=str(exc))
        return jsonify({"ok": False, "error": f"Erro ao carregar pedido: {exc}"}), 500
    finally:
        db.close()


@app.route("/api/player/orders/<order_id>/contest", methods=["POST"])
@login_required
def player_contest(order_id: str):
    if (err := _require_db()) is not None:
        return err
    steam_id = str(_steam_id_from_session())
    if (dn_err := _guard_player_display_name(steam_id)) is not None:
        return dn_err
    body = request.get_json(force=True)
    reason = str(body.get("reason", "")).strip()
    if not reason:
        return jsonify({"ok": False, "error": "Motivo é obrigatório"}), 400

    db = _SessionLocal()
    try:
        order = db.query(Order).filter(Order.order_id == order_id, Order.steam_id == steam_id).first()
        if not order:
            return jsonify({"ok": False, "error": "Pedido não encontrado"}), 404

        status_before = order.status
        order.contested = True
        order.status = "CONTESTADO"
        order.updated_at = _now()
        db.add(Dispute(order_id=order.order_id, steam_id=steam_id, reason=reason, status="ABERTO", created_at=_now()))
        db.commit()
        final_status = order.status
        _audit_event(
            "order_contested",
            actor_type="player",
            actor_steam_id=steam_id,
            target_steam_id=steam_id,
            order_id=order_id,
            item_type=order.item_type,
            item_id=order.item_id,
            status_before=status_before,
            status_after="CONTESTADO",
            message=f"Jogador contestou pedido {order_id[:8]}…",
            reason=reason,
        )
        return jsonify({"ok": True, "status": final_status})
    except Exception as exc:
        _log_error("player_contest", order_id=order_id, steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": f"Erro ao contestar pedido: {exc}"}), 500
    finally:
        db.close()


@app.route("/api/player/orders/<order_id>/rebuy", methods=["POST"])
@login_required
def player_rebuy(order_id: str):
    """Desativado — reemissão apenas por admin."""
    return jsonify({
        "ok": False,
        "error": "Reemissão disponível apenas para administradores. Use Contestação (⚠️) ou contate um admin.",
    }), 403


# ── Admin order routes ────────────────────────────────────────────────────────

_ADMIN_TERMINAL_STATUSES = frozenset({"CANCELADO", "REEMBOLSADO"})


def _order_refund_amount(order: Order) -> int:
    """Valor em Âmbar a devolver para o pedido (points_spent ou preço do catálogo)."""
    refund = int(order.points_spent or 0)
    if refund > 0:
        return refund
    entry = _catalog_entry(
        "kit" if str(order.item_type or "") == "kit" else "shop",
        str(order.item_id or ""),
    )
    return _catalog_price(entry, int(order.amount or 1))


def _close_order_disputes(db: Any, order_id: str) -> int:
    """Encerra disputas abertas do pedido."""
    rows = (
        db.query(Dispute)
        .filter(Dispute.order_id == order_id, Dispute.status == "ABERTO")
        .all()
    )
    for row in rows:
        row.status = "ENCERRADO"
    return len(rows)


def _build_admin_order_details(db: Any, order: Order) -> dict[str, Any]:
    order_id = order.order_id
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.order_id == order_id)
        .order_by(AuditEvent.created_at.asc())
        .all()
    )
    attempts = (
        db.query(OrderAttempt)
        .filter(OrderAttempt.order_id == order_id)
        .order_by(OrderAttempt.attempted_at.asc())
        .all()
    )
    disputes = db.query(Dispute).filter(Dispute.order_id == order_id).all()
    reissues = db.query(AdminReissue).filter(
        (AdminReissue.original_order_id == order_id) | (AdminReissue.new_order_id == order_id)
    ).all()
    return {
        "order": {
            "order_id": order.order_id,
            "steam_id": order.steam_id,
            "server_id": order.server_id,
            "item_type": order.item_type,
            "item_id": order.item_id,
            "amount": order.amount,
            "points_spent": int(order.points_spent or 0),
            "status": order.status,
            "contested": bool(order.contested),
            "retry_count": order.retry_count,
            "last_error": order.last_error,
            "original_order_id": order.original_order_id,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        },
        "audit_events": [_audit_row_dict(e) for e in events],
        "attempts": [
            {
                "attempted_at": a.attempted_at.isoformat() if a.attempted_at else None,
                "success": a.success,
                "command": a.command,
                "response": a.response,
                "error": a.error,
            }
            for a in attempts
        ],
        "disputes": [
            {
                "reason": d.reason,
                "status": d.status,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in disputes
        ],
        "reissues": [
            {
                "admin_steam_id": r.admin_steam_id,
                "player_steam_id": r.player_steam_id,
                "original_order_id": r.original_order_id,
                "new_order_id": r.new_order_id,
                "reason": r.reason,
                "force_reset": r.force_reset,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reissues
        ],
    }


@app.route("/api/admin/orders/retry", methods=["POST"])
@admin_required
def admin_retry_pending():
    if (err := _require_db()) is not None:
        return err
    body = request.get_json(force=True, silent=True) or {}
    limit = max(1, min(100, int(body.get("limit", 20))))

    db = _SessionLocal()
    try:
        pending = (
            db.query(Order)
            .filter(Order.status == "PENDENTE")
            .order_by(Order.created_at.asc())
            .limit(limit)
            .all()
        )
        order_ids = [o.order_id for o in pending]
    except Exception as exc:
        _log_error("admin_retry_pending", error=str(exc))
        return jsonify({"ok": False, "error": f"Erro ao buscar pedidos pendentes: {exc}"}), 500
    finally:
        db.close()

    _log("admin_retry", count=len(order_ids), admin=_steam_id_from_session())
    processed = [_process_order_delivery(order_id) for order_id in order_ids]
    return jsonify({"ok": True, "count": len(processed), "items": processed})


@app.route("/api/admin/orders", methods=["GET"])
@admin_required
def admin_list_orders():
    if (err := _require_db()) is not None:
        return err
    status = str(request.args.get("status", "")).strip().upper()
    limit = max(1, min(200, int(request.args.get("limit", 50))))
    db = _SessionLocal()
    try:
        q = db.query(Order)
        if status:
            q = q.filter(Order.status == status)
        rows = q.order_by(Order.created_at.desc()).limit(limit).all()
        return jsonify(
            {
                "ok": True,
                "items": [
                    {
                        "order_id": o.order_id,
                        "steam_id": o.steam_id,
                        "server_id": o.server_id,
                        "item_type": o.item_type,
                        "item_id": o.item_id,
                        "amount": o.amount,
                        "status": o.status,
                        "points_spent": int(o.points_spent or 0),
                        "contested": bool(o.contested),
                        "retry_count": o.retry_count,
                        "last_error": o.last_error,
                        "created_at": o.created_at.isoformat() if o.created_at else None,
                        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
                    }
                    for o in rows
                ],
            }
        )
    except Exception as exc:
        _log_error("admin_list_orders", error=str(exc))
        return jsonify({"ok": False, "error": f"Erro ao listar pedidos: {exc}"}), 500
    finally:
        db.close()


@app.route("/api/admin/orders/<order_id>/refund", methods=["POST"])
@admin_required
def admin_refund_order(order_id: str):
    """Reembolsa Âmbar ao jogador quando o resgate não foi entregue (ou contestado)."""
    if (err := _require_db()) is not None:
        return err
    admin_id = str(_steam_id_from_session())
    body = request.get_json(force=True, silent=True) or {}
    reason = str(body.get("reason", "")).strip() or None

    db = _SessionLocal()
    try:
        order = (
            db.query(Order)
            .filter(Order.order_id == order_id)
            .with_for_update()
            .first()
        )
        if not order:
            return jsonify({"ok": False, "error": "Pedido não encontrado"}), 404
        if order.status in _ADMIN_TERMINAL_STATUSES:
            return jsonify({
                "ok": False,
                "error": f"Pedido já está {order.status} — não é possível reembolsar novamente",
            }), 409

        status_before = order.status
        steam_id = str(order.steam_id)
        item_type = order.item_type
        item_id = order.item_id
        refund = _order_refund_amount(order)
        new_balance: int | None = None
        if refund > 0:
            new_balance = _add_player_points_tx(db, steam_id, refund)
        else:
            row = db.execute(
                text("SELECT points FROM players WHERE steam_id = :sid"),
                {"sid": steam_id},
            ).fetchone()
            new_balance = int(row[0]) if row else 0

        _revoke_entitlement_for_order(steam_id, order_id, db=db)
        closed = _close_order_disputes(db, order_id)
        order.contested = False
        order.status = "REEMBOLSADO"
        order.updated_at = _now()
        db.commit()
    except Exception as exc:
        db.rollback()
        _log_error("admin_refund_order", order_id=order_id, admin=admin_id, error=str(exc))
        return jsonify({"ok": False, "error": f"Erro ao reembolsar: {exc}"}), 500
    finally:
        db.close()

    _audit_event(
        "admin_refund",
        actor_type="admin",
        actor_steam_id=admin_id,
        target_steam_id=steam_id,
        order_id=order_id,
        item_type=item_type,
        item_id=item_id,
        status_before=status_before,
        status_after="REEMBOLSADO",
        message=f"Admin reembolsou {refund} Âmbar — pedido {order_id[:8]}…",
        reason=reason,
        refunded=refund,
        disputes_closed=closed,
        points_after=new_balance,
    )
    return jsonify({
        "ok": True,
        "order_id": order_id,
        "status": "REEMBOLSADO",
        "refunded": refund,
        "new_balance": new_balance,
    })


@app.route("/api/admin/orders/<order_id>/resend", methods=["POST"])
@admin_required
def admin_resend_order(order_id: str):
    """Reabre o pedido como PENDENTE para resgate via /shop in-game (sem novo débito)."""
    if (err := _require_db()) is not None:
        return err
    admin_id = str(_steam_id_from_session())
    body = request.get_json(force=True, silent=True) or {}
    reason = str(body.get("reason", "")).strip() or None

    db = _SessionLocal()
    try:
        order = (
            db.query(Order)
            .filter(Order.order_id == order_id)
            .with_for_update()
            .first()
        )
        if not order:
            return jsonify({"ok": False, "error": "Pedido não encontrado"}), 404
        if order.status == "PENDENTE":
            return jsonify({
                "ok": False,
                "error": "Pedido já está pendente — aguardando resgate no jogo",
            }), 409
        if order.status == "REEMBOLSADO":
            return jsonify({
                "ok": False,
                "error": "Pedido reembolsado — use um novo resgate ou reembolso reverso manual",
            }), 409
        if order.status == "REEMITIDO":
            reissue = (
                db.query(AdminReissue)
                .filter(AdminReissue.original_order_id == order_id)
                .order_by(AdminReissue.created_at.desc())
                .first()
            )
            hint = ""
            if reissue:
                hint = f" Use o pedido substituto {reissue.new_order_id[:8]}…"
            return jsonify({
                "ok": False,
                "error": f"Pedido substituído por reemissão anterior.{hint}",
            }), 409

        status_before = order.status
        player_steam = str(order.steam_id)
        resend_server_id = order.server_id
        item_type = order.item_type
        item_id = order.item_id
        resend_amount = order.amount
        _close_order_disputes(db, order_id)
        order.status = "PENDENTE"
        order.contested = False
        order.last_error = None
        order.retry_count = 0
        order.updated_at = _now()
        db.commit()
    except Exception as exc:
        db.rollback()
        _log_error("admin_resend_order", order_id=order_id, admin=admin_id, error=str(exc))
        return jsonify({"ok": False, "error": f"Erro ao reenviar: {exc}"}), 500
    finally:
        db.close()

    _audit_event(
        "admin_resend",
        actor_type="admin",
        actor_steam_id=admin_id,
        target_steam_id=player_steam,
        order_id=order_id,
        server_id=resend_server_id,
        item_type=item_type,
        item_id=item_id,
        amount=resend_amount,
        status_before=status_before,
        status_after="PENDENTE",
        message=f"Admin reenviou pedido {order_id[:8]}… para fila /shop",
        reason=reason,
    )
    return jsonify({
        "ok": True,
        "order_id": order_id,
        "status": "PENDENTE",
        "queued": True,
        "delivery_mode": "plugin",
    })


@app.route("/api/admin/orders/<order_id>/cancel", methods=["POST"])
@admin_required
def admin_cancel_order(order_id: str):
    """Marca pedido como cancelado sem reembolsar Âmbar."""
    if (err := _require_db()) is not None:
        return err
    admin_id = str(_steam_id_from_session())
    body = request.get_json(force=True, silent=True) or {}
    reason = str(body.get("reason", "")).strip() or None

    db = _SessionLocal()
    try:
        order = (
            db.query(Order)
            .filter(Order.order_id == order_id)
            .with_for_update()
            .first()
        )
        if not order:
            return jsonify({"ok": False, "error": "Pedido não encontrado"}), 404
        if order.status in _ADMIN_TERMINAL_STATUSES:
            return jsonify({
                "ok": False,
                "error": f"Pedido já está {order.status}",
            }), 409

        status_before = order.status
        steam_id = str(order.steam_id)
        item_type = order.item_type
        item_id = order.item_id
        _revoke_entitlement_for_order(steam_id, order_id, db=db)
        closed = _close_order_disputes(db, order_id)
        order.contested = False
        order.status = "CANCELADO"
        order.updated_at = _now()
        db.commit()
    except Exception as exc:
        db.rollback()
        _log_error("admin_cancel_order", order_id=order_id, admin=admin_id, error=str(exc))
        return jsonify({"ok": False, "error": f"Erro ao cancelar: {exc}"}), 500
    finally:
        db.close()

    _audit_event(
        "admin_cancel",
        actor_type="admin",
        actor_steam_id=admin_id,
        target_steam_id=steam_id,
        order_id=order_id,
        item_type=item_type,
        item_id=item_id,
        status_before=status_before,
        status_after="CANCELADO",
        message=f"Admin cancelou pedido {order_id[:8]}… (sem reembolso)",
        reason=reason,
        disputes_closed=closed,
    )
    return jsonify({
        "ok": True,
        "order_id": order_id,
        "status": "CANCELADO",
        "refunded": 0,
    })


@app.route("/api/admin/orders/<order_id>/details", methods=["GET"])
@admin_required
def admin_order_details(order_id: str):
    """Detalhes completos do pedido — timeline, tentativas, disputas e reemissões."""
    if (err := _require_db()) is not None:
        return err
    db = _SessionLocal()
    try:
        order = db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            return jsonify({"ok": False, "error": "Pedido não encontrado"}), 404
        payload = _build_admin_order_details(db, order)
        return jsonify({"ok": True, **payload})
    except Exception as exc:
        _log_error("admin_order_details", order_id=order_id, error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/admin/orders/<order_id>/repair-license", methods=["POST"])
@admin_required
def admin_repair_order_license(order_id: str):
    """Recria player_entitlements para pedido de licença já entregue sem grant no banco."""
    if (err := _require_db()) is not None:
        return err
    admin_id = str(_steam_id_from_session())
    db = _SessionLocal()
    try:
        order = db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            return jsonify({"ok": False, "error": "Pedido não encontrado"}), 404
        repaired = _ensure_license_entitlement_for_order(order, reason="admin_repair")
        entitlements = _get_player_entitlements(str(order.steam_id))
        _audit_event(
            "admin_repair_license",
            actor_type="admin",
            actor_steam_id=admin_id,
            target_steam_id=str(order.steam_id),
            order_id=order_id,
            item_type=order.item_type,
            item_id=order.item_id,
            message="Licença reparada no banco" if repaired else "Nada a reparar ou item sem LicenseGrant",
            repaired=repaired,
        )
        return jsonify({
            "ok": True,
            "repaired": repaired,
            "entitlements": entitlements,
            "timed_points_total": _compute_timed_points_total([e["group"] for e in entitlements]),
        })
    finally:
        db.close()


@app.route("/api/admin/orders/<order_id>/reprocess", methods=["POST"])
@admin_required
def admin_reprocess_order(order_id: str):
    if (err := _require_db()) is not None:
        return err
    force_rcon = request.args.get("force_rcon", "").lower() in ("1", "true", "yes")
    force_reset = request.args.get("force_reset", "").lower() in ("1", "true", "yes")
    admin_id = str(_steam_id_from_session())
    db = _SessionLocal()
    status_before = ""
    player_steam = ""
    try:
        order = db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            return jsonify({"ok": False, "error": "Pedido não encontrado"}), 404
        status_before = order.status
        player_steam = order.steam_id
        if order.status == "ENTREGUE" and not force_reset:
            return jsonify({"ok": False, "error": "Pedido já entregue — use force_reset=1 para reabrir"}), 400
        order.status = "PENDENTE"
        order.last_error = None
        order.updated_at = _now()
        db.commit()
    finally:
        db.close()

    _audit_event(
        "admin_reprocess",
        actor_type="admin",
        actor_steam_id=admin_id,
        target_steam_id=player_steam or None,
        order_id=order_id,
        status_before=status_before,
        status_after="PENDENTE",
        message=f"Admin reprocessou pedido {order_id[:8]}…",
        force_rcon=force_rcon,
        force_reset=force_reset,
    )
    result = _process_order_delivery(order_id, force_rcon=force_rcon)
    return jsonify(result), 200 if result.get("ok") else 500


@app.route("/api/admin/orders/<order_id>/reissue", methods=["POST"])
@admin_required
def admin_reissue_order(order_id: str):
    """Reemissão admin — cria novo pedido PENDENTE sem debitar pontos."""
    if (err := _require_db()) is not None:
        return err
    admin_id = str(_steam_id_from_session())
    body = request.get_json(force=True, silent=True) or {}
    reason = str(body.get("reason", "")).strip()
    force_reset = bool(body.get("force_reset", True))
    if not reason:
        return jsonify({"ok": False, "error": "Motivo da reemissão é obrigatório"}), 400

    db = _SessionLocal()
    new_order_id: str | None = None
    try:
        original = db.query(Order).filter(Order.order_id == order_id).first()
        if not original:
            return jsonify({"ok": False, "error": "Pedido não encontrado"}), 404

        before = original.status
        new_order = Order(
            order_id=str(uuid.uuid4()),
            steam_id=original.steam_id,
            server_id=original.server_id,
            item_type=original.item_type,
            item_id=original.item_id,
            amount=original.amount,
            status="PENDENTE",
            original_order_id=original.order_id,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(new_order)
        db.add(AdminReissue(
            admin_steam_id=admin_id,
            player_steam_id=original.steam_id,
            original_order_id=original.order_id,
            new_order_id=new_order.order_id,
            reason=reason,
            force_reset=force_reset,
            created_at=_now(),
        ))
        if before != "REEMITIDO":
            original.status = "REEMITIDO"
            original.updated_at = _now()
        db.commit()
        db.refresh(new_order)
        new_order_id = new_order.order_id

        _audit_event(
            "admin_reissue",
            actor_type="admin",
            actor_steam_id=admin_id,
            target_steam_id=original.steam_id,
            order_id=original.order_id,
            server_id=original.server_id,
            item_type=original.item_type,
            item_id=original.item_id,
            amount=original.amount,
            status_before=before,
            status_after="REEMITIDO",
            message=f"Admin reemitiu {original.item_id} para {original.steam_id}",
            reason=reason,
            new_order_id=new_order_id,
            force_reset=force_reset,
        )
    except Exception as exc:
        db.rollback()
        _log_error("admin_reissue", order_id=order_id, admin=admin_id, error=str(exc))
        return jsonify({"ok": False, "error": f"Erro ao reemitir: {exc}"}), 500
    finally:
        db.close()

    if not new_order_id:
        return jsonify({"ok": False, "error": "Falha ao reemitir"}), 500

    result = _process_order_delivery(new_order_id)
    result["order_id"] = new_order_id
    result["new_order_id"] = new_order_id
    return jsonify(result), 200 if result.get("ok") else 500


# ── Admin audit routes ────────────────────────────────────────────────────────

def _pix_payment_row_dict(row: PointPayment) -> dict[str, Any]:
    return {
        "payment_id": row.payment_id,
        "mp_payment_id": row.mp_payment_id,
        "steam_id": row.steam_id,
        "package_id": row.package_id,
        "package_label": _package_label(row.package_id),
        "amount_brl": float(row.amount_brl or 0),
        "points": int(row.points or 0),
        "status": row.status,
        "credited": bool(row.credited),
        "payer_email": row.payer_email,
        "payment_method": _resolve_payment_method(row),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@app.route("/api/admin/pix/audit", methods=["GET"])
@admin_required
def admin_pix_audit():
    """Log completo de doações (PIX e cartão) para suporte — tentativas, concluídas e canceladas."""
    if (err := _require_db()) is not None:
        return err
    status = str(request.args.get("status", "")).strip().upper()
    steam_id = str(request.args.get("steam_id", "")).strip()
    payment_id = str(request.args.get("payment_id", "")).strip()
    q = str(request.args.get("q", "")).strip().lower()
    limit = max(1, min(200, int(request.args.get("limit", 50))))
    offset = max(0, int(request.args.get("offset", 0)))

    db = _SessionLocal()
    try:
        query = db.query(PointPayment)
        if status:
            if status == "CONCLUIDA":
                query = query.filter(PointPayment.credited.is_(True))
            elif status == "CANCELADA":
                query = query.filter(PointPayment.status.in_((
                    "RECUSADO", "EXPIRADO", "ESTORNADO", "ABANDONADO",
                )))
            elif status == "TENTATIVA":
                query = query.filter(
                    PointPayment.credited.is_(False),
                    PointPayment.status.in_(("PENDENTE", "ABANDONADO")),
                )
            else:
                query = query.filter(PointPayment.status == status)
        if steam_id:
            query = query.filter(PointPayment.steam_id == steam_id)
        if payment_id:
            query = query.filter(
                (PointPayment.payment_id == payment_id)
                | (PointPayment.mp_payment_id == payment_id)
            )
        if q:
            query = query.filter(
                (PointPayment.steam_id.ilike(f"%{q}%"))
                | (PointPayment.payment_id.ilike(f"%{q}%"))
                | (PointPayment.mp_payment_id.ilike(f"%{q}%"))
                | (PointPayment.package_id.ilike(f"%{q}%"))
                | (PointPayment.payer_email.ilike(f"%{q}%"))
            )

        total = query.count()
        rows = query.order_by(PointPayment.created_at.desc()).offset(offset).limit(limit).all()

        base = db.query(PointPayment)
        stats = {
            "total": base.count(),
            "concluidas": base.filter(PointPayment.credited.is_(True)).count(),
            "pendentes": base.filter(
                PointPayment.status == "PENDENTE",
                PointPayment.credited.is_(False),
            ).count(),
            "abandonadas": base.filter(PointPayment.status == "ABANDONADO").count(),
            "recusadas": base.filter(PointPayment.status == "RECUSADO").count(),
            "expiradas": base.filter(PointPayment.status == "EXPIRADO").count(),
            "estornadas": base.filter(PointPayment.status == "ESTORNADO").count(),
            "aprovadas_sem_credito": base.filter(
                PointPayment.status == "APROVADO",
                PointPayment.credited.is_(False),
            ).count(),
        }

        return jsonify({
            "ok": True,
            "total": total,
            "stats": stats,
            "items": [_pix_payment_row_dict(r) for r in rows],
        })
    except Exception as exc:
        _log_error("admin_pix_audit", error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/admin/audit", methods=["GET"])
@admin_required
def admin_list_audit():
    if (err := _require_db()) is not None:
        return err
    event_type = str(request.args.get("event_type", "")).strip()
    severity = str(request.args.get("severity", "")).strip()
    steam_id = str(request.args.get("steam_id", "")).strip()
    order_id = str(request.args.get("order_id", "")).strip()
    admin_steam_id = str(request.args.get("admin_steam_id", "")).strip()
    q = str(request.args.get("q", "")).strip().lower()
    limit = max(1, min(200, int(request.args.get("limit", 50))))
    offset = max(0, int(request.args.get("offset", 0)))

    db = _SessionLocal()
    try:
        query = db.query(AuditEvent)
        if event_type:
            if event_type == "pix":
                query = query.filter(AuditEvent.event_type.like("pix_%"))
            else:
                query = query.filter(AuditEvent.event_type == event_type)
        if severity:
            query = query.filter(AuditEvent.severity == severity)
        if steam_id:
            query = query.filter(
                (AuditEvent.target_steam_id == steam_id) | (AuditEvent.actor_steam_id == steam_id)
            )
        if order_id:
            query = query.filter(AuditEvent.order_id == order_id)
        if admin_steam_id:
            query = query.filter(AuditEvent.actor_steam_id == admin_steam_id)
        if q:
            query = query.filter(
                (AuditEvent.message.ilike(f"%{q}%"))
                | (AuditEvent.event_type.ilike(f"%{q}%"))
                | (AuditEvent.item_id.ilike(f"%{q}%"))
                | (AuditEvent.order_id.ilike(f"%{q}%"))
            )
        total = query.count()
        rows = query.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit).all()
        return jsonify({
            "ok": True,
            "total": total,
            "items": [_audit_row_dict(r) for r in rows],
        })
    except Exception as exc:
        _log_error("admin_list_audit", error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        db.close()


@app.route("/api/admin/audit/<int:event_id>", methods=["GET"])
@admin_required
def admin_audit_detail(event_id: int):
    if (err := _require_db()) is not None:
        return err
    db = _SessionLocal()
    try:
        row = db.query(AuditEvent).filter(AuditEvent.id == event_id).first()
        if not row:
            return jsonify({"ok": False, "error": "Evento não encontrado"}), 404
        return jsonify({"ok": True, "event": _audit_row_dict(row)})
    finally:
        db.close()


@app.route("/api/admin/orders/<order_id>/timeline", methods=["GET"])
@admin_required
def admin_order_timeline(order_id: str):
    """Alias legado — mesmos dados de /details."""
    if (err := _require_db()) is not None:
        return err
    db = _SessionLocal()
    try:
        order = db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            return jsonify({"ok": False, "error": "Pedido não encontrado"}), 404
        return jsonify({"ok": True, **_build_admin_order_details(db, order)})
    except Exception as exc:
        _log_error("admin_order_timeline", order_id=order_id, error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        db.close()


# ── Admin: gestão de jogadores ────────────────────────────────────────────────

@app.route("/api/admin/license-catalog", methods=["GET"])
@admin_required
def admin_license_catalog():
    return jsonify({"ok": True, "items": _catalog_license_options()})


@app.route("/api/admin/players", methods=["GET"])
@admin_required
def admin_players_list():
    q = str(request.args.get("q") or request.args.get("search") or "").strip()
    sort = str(request.args.get("sort") or "last_login").strip()
    order = str(request.args.get("order") or "desc").strip()
    try:
        offset = int(request.args.get("offset", 0) or 0)
        limit = int(request.args.get("limit", 50) or 50)
    except (TypeError, ValueError):
        offset, limit = 0, 50
    result = _list_admin_players(q=q, sort=sort, order=order, offset=offset, limit=limit)
    status = 200 if result.get("ok") else 500
    return jsonify(result), status


@app.route("/api/admin/players/<steam_id>", methods=["GET"])
@admin_required
def admin_player_detail(steam_id: str):
    result = _get_admin_player_detail(steam_id.strip())
    if not result.get("ok"):
        code = 404 if "inválido" in str(result.get("error", "")).lower() else 500
        return jsonify(result), code
    return jsonify(result)


@app.route("/api/admin/players/<steam_id>/points", methods=["POST"])
@admin_required
@limiter.limit("120 per hour")
def admin_player_points(steam_id: str):
    body = request.get_json(force=True, silent=True) or {}
    result = _admin_player_points_adjust(
        steam_id.strip(),
        mode=str(body.get("mode") or body.get("action") or "add"),
        amount=int(body.get("amount", 0) or 0),
        reason=str(body.get("reason") or "").strip(),
    )
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.route("/api/admin/players/<steam_id>/ban", methods=["POST"])
@admin_required
@limiter.limit("60 per hour")
def admin_player_ban(steam_id: str):
    body = request.get_json(force=True, silent=True) or {}
    blocked = body.get("blocked")
    if blocked is None:
        blocked = body.get("site_access_blocked", True)
    result = _admin_player_ban(
        steam_id.strip(),
        blocked=bool(blocked),
        reason=str(body.get("reason") or body.get("ban_reason") or "").strip(),
    )
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.route("/api/admin/players/<steam_id>/licenses", methods=["POST"])
@admin_required
@limiter.limit("120 per hour")
def admin_player_licenses(steam_id: str):
    body = request.get_json(force=True, silent=True) or {}
    group = str(body.get("group") or body.get("license_group") or "").strip()
    if not group and body.get("item_id"):
        entry = _catalog_entry("shop", str(body.get("item_id")))
        lic = _get_license_grant(entry) if entry else None
        if lic:
            group = str(lic.get("Group") or "")
    days = int(body.get("days", 30) or 30)
    result = _admin_player_license(
        steam_id.strip(),
        action=str(body.get("action") or "grant"),
        group=group,
        days=days,
        reason=str(body.get("reason") or "").strip(),
    )
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.route("/api/admin/players/<steam_id>/kits", methods=["POST"])
@admin_required
@limiter.limit("120 per hour")
def admin_player_kits(steam_id: str):
    body = request.get_json(force=True, silent=True) or {}
    result = _admin_player_kit(
        steam_id.strip(),
        mode=str(body.get("mode") or "deliver"),
        kit_id=str(body.get("kit_id") or body.get("item_id") or ""),
        amount=int(body.get("amount", 1) or 1),
        reason=str(body.get("reason") or "").strip(),
    )
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


# ── Admin admins routes ───────────────────────────────────────────────────────

@app.route("/api/admin/admins", methods=["GET"])
@admin_required
def admin_list_admins():
    admins = sorted(_load_admin_steamids())
    return jsonify({"ok": True, "items": admins})


@app.route("/api/admin/admins", methods=["POST"])
@admin_required
def admin_add_admin():
    body = request.get_json(force=True)
    steam_id = str(body.get("steam_id", "")).strip()
    if not _is_valid_steamid64(steam_id):
        return jsonify({"ok": False, "error": "SteamID64 inválido"}), 400

    if _db_ready():
        db = _SessionLocal()
        try:
            db.merge(ShopAdmin(steam_id=steam_id))
            db.commit()
        finally:
            db.close()
    else:
        ids = _load_admin_steamids()
        ids.add(steam_id)
        _ADMIN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _ADMIN_FILE.write_text(json.dumps(sorted(ids), indent=2, ensure_ascii=False), encoding="utf-8")

    _log("admin_added", steam_id=steam_id, by=_steam_id_from_session())
    return jsonify({"ok": True})


@app.route("/api/admin/admins/<steam_id>", methods=["DELETE"])
@admin_required
def admin_remove_admin(steam_id: str):
    steam_id = steam_id.strip()
    if not _is_valid_steamid64(steam_id):
        return jsonify({"ok": False, "error": "SteamID64 inválido"}), 400

    if _db_ready():
        db = _SessionLocal()
        try:
            db.query(ShopAdmin).filter(ShopAdmin.steam_id == steam_id).delete()
            db.commit()
        finally:
            db.close()
    else:
        ids = _load_admin_steamids()
        ids.discard(steam_id)
        _ADMIN_FILE.write_text(json.dumps(sorted(ids), indent=2, ensure_ascii=False), encoding="utf-8")

    _log("admin_removed", steam_id=steam_id, by=_steam_id_from_session())
    return jsonify({"ok": True})


from market_routes import register_market_routes

register_market_routes(
    app,
    db_ready=_db_ready,
    session_factory=_db_session_factory,
    read_shop_config=_read_shop_config,
    admin_required=admin_required,
    login_required=login_required,
    api_key_required=api_key_required,
    steam_id_from_session=_steam_id_from_session,
    audit_event=_audit_event,
    limiter=limiter,
)

from cross_chat_routes import register_cross_chat_routes

register_cross_chat_routes(
    app,
    db_ready=_db_ready,
    session_factory=_db_session_factory,
    api_key_required=api_key_required,
    admin_required=admin_required,
    limiter=limiter,
    load_settings=_load_settings,
    save_settings=_save_settings,
)

from cross_chat_discord import start_discord_bridge

start_discord_bridge(
    session_factory=_db_session_factory,
    load_settings=_load_settings,
    save_settings=_save_settings,
    db_ready=_db_ready,
)

if os.environ.get("ARKSHOP_SKIP_DB_BOOT") != "1":
    _kick_background_db_init()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5177))
    log.info("ArkShop Web Manager rodando em http://127.0.0.1:%d", port)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
