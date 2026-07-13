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
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from dotenv import load_dotenv

from cryptography.fernet import Fernet

from pix_payments import (
    CARD_PAYER_FORM,
    PIX_PAYER_FORM,
    PayerValidationError,
    PixPaymentError,
    create_card_checkout_preference,
    create_pix_payment,
    extract_checkout_url,
    extract_pix_data,
    fetch_payment,
    map_mp_status,
    normalize_card_payer_input,
    normalize_pix_payer_input,
    parse_mp_error_message,
)
from exchange_rates import estimate_foreign, get_exchange_rates
from flask import Flask, has_request_context, jsonify, make_response, redirect, request, send_from_directory, session
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from sqlalchemy import Boolean, DateTime, Float, Integer, LargeBinary, String, Text, UniqueConstraint, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, scoped_session, sessionmaker

from rcon_bridge import rcon_command as _rcon_send, rcon_test_connection as _rcon_test_connection
from server_connect import diagnose_server_connect, public_server_connect_view

from kit_limits import (
    get_kit_remaining,
    kit_default_amount,
    kit_has_limit,
    kit_limit_status,
    parse_kit_stash,
    reset_kit_limit,
    reset_kit_limits_for_license,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from src.rcon_util import CUSTOMSHOP_RELOAD_COMMANDS, sanitize_rcon_password  # noqa: E402
from src.shop_integration import (  # noqa: E402
    apply_machine_server_registry,
    _collect_catalog_search_paths,
    _merge_arkland_server_entry,
    _resolve_game_host,
    canonical_master_catalog_path,
    default_customshop_path,
    is_ephemeral_pyinstaller_path,
    is_webstore_catalog_path,
    load_plugin_config,
    slugify_server_id,
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
        _release_db_session(db)


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

# Resolve .env: raiz do projeto (dev), pasta do exe (PyInstaller) e dados persistentes (TEK)
_PROJECT_ROOT = _BUNDLE_DIR.parent.parent if not getattr(sys, "frozen", False) else _BUNDLE_DIR
_ENV_CANDIDATES: list[Path] = []
if not getattr(sys, "frozen", False):
    _ENV_CANDIDATES.append(_PROJECT_ROOT / ".env")
else:
    _ENV_CANDIDATES.append(Path(sys.executable).resolve().parent / ".env")
_ENV_CANDIDATES.append(_DATA_DIR / ".env")
for _env_candidate in _ENV_CANDIDATES:
    if _env_candidate.is_file():
        load_dotenv(dotenv_path=_env_candidate, override=False)


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
_SUPPORT_FILE = _DATA_DIR / "support_steamids.json"
_SUPPORT_EXAMPLE = _BUNDLE_DIR / "support_steamids.example.json"
_SERVERS_FILE = _DATA_DIR / "servers.json"
_TICKET_UPLOADS_DIR = _DATA_DIR / "ticket_uploads"
_ENCOMENDA_SHOWCASE_FILE = _DATA_DIR / "dino_order_color_showcases.json"
_ENCOMENDA_SHOWCASE_UPLOADS_DIR = _DATA_DIR / "encomenda_showcase_uploads"
_ENCOMENDA_VITRINE_FILE = _DATA_DIR / "dino_order_vitrine.json"
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
_session_days = max(1, int(os.environ.get("ARKSHOP_SESSION_DAYS", "30") or "30"))
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

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = _is_production or _is_frozen
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=_session_days)


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


def _ensure_support_steamids_file() -> None:
    """Garante support_steamids.json no diretório de dados (não no repositório)."""
    if _SUPPORT_FILE.exists():
        return
    _SUPPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    legacy = _BUNDLE_DIR / "support_steamids.json"
    if legacy.is_file() and legacy.resolve() != _SUPPORT_FILE.resolve():
        try:
            _SUPPORT_FILE.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
            log.info("support_steamids migrado de %s para %s", legacy, _SUPPORT_FILE)
            return
        except Exception as exc:
            log.warning("Falha ao migrar support_steamids legado: %s", exc)
    if _SUPPORT_EXAMPLE.is_file():
        _SUPPORT_FILE.write_text(_SUPPORT_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        _SUPPORT_FILE.write_text("[]\n", encoding="utf-8")
    log.info("support_steamids criado em %s — cadastre SteamIDs da equipe de suporte", _SUPPORT_FILE)


_ensure_support_steamids_file()

# API Key for CustomShop ↔ arkshop_web internal communication
# Must be set via environment variable ARKSHOP_API_KEY
_ARKSHOP_API_KEY = os.environ.get("ARKSHOP_API_KEY", "").strip()
_ENCRYPTED_PREFIX = "ENC:"
_SENSITIVE_SETTINGS_KEYS = ("rcon_password", "db_password", "mp_access_token", "steam_api_key", "cross_chat_discord_token", "ticket_discord_token")

_DEFAULT_POINT_PACKAGES: list[dict[str, Any]] = [
    {"id": "p10000", "label": "10.000 Âmbares", "points": 10000, "price_brl": 5.0, "note": "Primeiro passo — ideal para conhecer a loja"},
    {"id": "p20500", "label": "20.500 Âmbares", "points": 20500, "price_brl": 10.0, "note": "+2,5% bônus vs pacote inicial"},
    {"id": "p42000", "label": "42.000 Âmbares", "points": 42000, "price_brl": 20.0, "note": "+5% bônus — dobro com vantagem"},
    {"id": "p75000", "label": "75.000 Âmbares", "points": 75000, "price_brl": 35.0, "note": "Melhor custo-benefício entre R$ 20 e R$ 50"},
    {"id": "p110000", "label": "110.000 Âmbares", "points": 110000, "price_brl": 50.0, "note": "Pacote popular — equilíbrio ideal"},
    {"id": "p170000", "label": "170.000 Âmbares", "points": 170000, "price_brl": 75.0, "note": "+13% bônus vs pacote de R$ 50"},
    {"id": "p230000", "label": "230.000 Âmbares", "points": 230000, "price_brl": 100.0, "note": "Impulsione seu progresso no cluster"},
    {"id": "p625000", "label": "625.000 Âmbares", "points": 625000, "price_brl": 250.0, "note": "+25% bônus — apoio premium ao servidor"},
    {"id": "p1300000", "label": "1.300.000 Âmbares", "points": 1300000, "price_brl": 500.0, "note": "Melhor valor por Âmbar acima de R$ 250"},
    {"id": "p2700000", "label": "2.700.000 Âmbares", "points": 2700000, "price_brl": 1000.0, "note": "+35% bônus — máximo incentivo ARKLAND"},
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
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class ShopSupport(Base):
    """Equipe de suporte — acesso à fila de tickets sem permissões de admin."""

    __tablename__ = "shop_support"

    steam_id: Mapped[str] = mapped_column(String(32), primary_key=True)


class StoreUser(Base):
    """Conta web — criada no primeiro login Steam; base do painel admin de jogadores."""

    __tablename__ = "store_users"

    steam_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    steam_persona: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    site_access_blocked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    ban_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    regulamento_accepted_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    regulamento_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fixed_lottery_number: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)


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
    tribe_split_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    split_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Casal M+F (§8.7.3): vínculo bidirecional; primário = menor listing_id
    pair_mate_listing_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    pair_group_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)


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


class SupportTicket(Base):
    """Ticket de suporte — jogador ↔ admin (MVP 1.9.149)."""

    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    steam_id: Mapped[str] = mapped_column(String(32), index=True)
    player_name: Mapped[str] = mapped_column(String(128), default="")
    discord_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    discord_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    subject: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(64), default="geral", index=True)
    priority: Mapped[str] = mapped_column(String(16), default="normal", index=True)
    status: Mapped[str] = mapped_column(String(32), default="AGUARDANDO_SUPORTE", index=True)
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    listing_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    claim_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    market_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    assigned_admin_steam_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SupportTicketMessage(Base):
    __tablename__ = "support_ticket_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(Integer, index=True)
    author_type: Mapped[str] = mapped_column(String(16), default="player")
    author_steam_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    author_name: Mapped[str] = mapped_column(String(128), default="")
    body: Mapped[str] = mapped_column(Text)
    links_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class SupportTicketAttachment(Base):
    __tablename__ = "support_ticket_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(Integer, index=True)
    message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    storage_path: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class SupportTicketHistory(Base):
    """Histórico / trilha de auditoria de um ticket."""

    __tablename__ = "support_ticket_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(Integer, index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    actor_steam_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(128), default="")
    field_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    old_value: Mapped[str | None] = mapped_column(String(256), nullable=True)
    new_value: Mapped[str | None] = mapped_column(String(256), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


class SupportTicketDiscordLink(Base):
    __tablename__ = "support_ticket_discord_links"

    steam_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    discord_user_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    discord_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    link_method: Mapped[str] = mapped_column(String(16), default="manual")
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class UserNotification(Base):
    """Notificação in-app para jogadores."""

    __tablename__ = "user_notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    steam_id: Mapped[str] = mapped_column(String(32), index=True)
    type: Mapped[str] = mapped_column(String(64), default="general", index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    link_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    link_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


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
    ("shop_support", "steam_id"),
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
    ("support_tickets", "steam_id"),
    ("support_tickets", "assigned_admin_steam_id"),
    ("support_ticket_messages", "author_steam_id"),
    ("support_ticket_discord_links", "steam_id"),
)


def _steam_id_on_sql(left: str, right: str, *, mysql: bool = True) -> str:
    """Comparação steam_id segura quando collations divergem (general_ci vs unicode_ci)."""
    if not mysql:
        return f"{left} = {right}"
    coll = _STEAM_ID_COLLATION
    return f"{left} COLLATE {coll} = {right} COLLATE {coll}"


def _column_is_primary_key(conn: Any, table: str, column: str) -> bool:
    """True se a coluna faz parte da PRIMARY KEY da tabela (information_schema)."""
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :tbl "
            "AND COLUMN_NAME = :col AND CONSTRAINT_NAME = 'PRIMARY' LIMIT 1"
        ),
        {"tbl": table, "col": column},
    ).fetchone()
    return row is not None


def _is_multiple_primary_key_error(exc: BaseException) -> bool:
    orig = getattr(exc, "orig", None)
    if orig is not None and getattr(orig, "args", None):
        if orig.args[0] == 1068:
            return True
    msg = str(exc).lower()
    return "1068" in msg or "multiple primary key" in msg


def _build_steam_id_collation_modify_sql(
    table: str,
    column: str,
    col_type: str,
    null_sql: str,
    *,
    key_flag: str,
    is_pk_column: bool,
) -> str:
    """ALTER MODIFY só para collation — não redeclara PK existente (MariaDB erro 1068)."""
    key_sql = ""
    if key_flag == "PRI" and not is_pk_column:
        key_sql = " PRIMARY KEY"
    return (
        f"ALTER TABLE `{table}` MODIFY `{column}` {col_type} "
        f"CHARACTER SET utf8mb4 COLLATE {_STEAM_ID_COLLATION} "
        f"{null_sql}{key_sql}"
    )


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
            is_pk = _column_is_primary_key(conn, table, column)
            alter_sql = _build_steam_id_collation_modify_sql(
                table,
                column,
                col_type,
                null_sql,
                key_flag=key_flag,
                is_pk_column=is_pk,
            )
            try:
                conn.execute(text(alter_sql))
            except Exception as exc:
                if _is_multiple_primary_key_error(exc):
                    log.warning(
                        "steam_id: %s.%s — retry MODIFY sem PRIMARY KEY (1068)",
                        table,
                        column,
                    )
                    conn.execute(
                        text(
                            _build_steam_id_collation_modify_sql(
                                table,
                                column,
                                col_type,
                                null_sql,
                                key_flag="",
                                is_pk_column=True,
                            )
                        )
                    )
                else:
                    raise
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
        with engine.connect() as conn:
            cols = {
                str(row[1])
                for row in conn.execute(text("PRAGMA table_info(store_users)")).fetchall()
            }
            if "steam_persona" not in cols:
                conn.execute(text("ALTER TABLE store_users ADD COLUMN steam_persona VARCHAR(128)"))
            if "fixed_lottery_number" not in cols:
                conn.execute(text("ALTER TABLE store_users ADD COLUMN fixed_lottery_number INTEGER"))
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_store_users_fixed_lottery_number "
                        "ON store_users (fixed_lottery_number) WHERE fixed_lottery_number IS NOT NULL"
                    )
                )
            conn.commit()
            if "steam_persona" not in cols or "fixed_lottery_number" not in cols:
                log.info("store_users: colunas sqlite adicionadas")
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
        if "steam_persona" not in cols:
            alters.append("ADD COLUMN `steam_persona` VARCHAR(128) NULL")
        if "created_at" not in cols:
            alters.append(
                "ADD COLUMN `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP"
            )
        if "regulamento_accepted_version" not in cols:
            alters.append("ADD COLUMN `regulamento_accepted_version` VARCHAR(16) NULL")
        if "regulamento_accepted_at" not in cols:
            alters.append("ADD COLUMN `regulamento_accepted_at` DATETIME NULL")
        if "fixed_lottery_number" not in cols:
            alters.append("ADD COLUMN `fixed_lottery_number` SMALLINT NULL")
        for fragment in alters:
            conn.execute(text(f"ALTER TABLE `store_users` {fragment}"))
        if alters:
            conn.commit()
            log.info("store_users: colunas do painel admin adicionadas (%s)", len(alters))
        if "fixed_lottery_number" not in cols:
            idx_row = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.statistics "
                    "WHERE table_schema = DATABASE() AND table_name = 'store_users' "
                    "AND index_name = 'uq_store_users_fixed_lottery_number' LIMIT 1"
                )
            ).fetchone()
            if idx_row is None:
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX uq_store_users_fixed_lottery_number "
                        "ON store_users (fixed_lottery_number)"
                    )
                )
                conn.commit()


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
        try:
            from amber_ledger import ensure_amber_schema

            ensure_amber_schema(engine)
        except Exception as exc:
            log.warning("Âmbarômetro (sqlite dev): migrate falhou: %s", exc)
        try:
            from lottery_service import ensure_lottery_schema

            ensure_lottery_schema(engine)
        except Exception as exc:
            log.warning("Sorteio (sqlite dev): migrate falhou: %s", exc)
        try:
            from custom_dino_service import ensure_custom_dino_schema

            ensure_custom_dino_schema(engine)
        except Exception as exc:
            log.warning("Dino Lab (sqlite dev): migrate falhou: %s", exc)
        try:
            from dino_lab_block_service import ensure_dino_lab_block_schema

            ensure_dino_lab_block_schema(engine)
        except Exception as exc:
            log.warning("Dino Lab block (sqlite dev): migrate falhou: %s", exc)
        try:
            from tribe_service import ensure_tribe_schema

            ensure_tribe_schema(engine)
        except Exception as exc:
            log.warning("Área de Tribo (sqlite dev): migrate falhou: %s", exc)
        try:
            from itensalfa_licenses_migrate import ensure_itensalfa_licenses_schema

            ensure_itensalfa_licenses_schema(engine)
        except Exception as exc:
            log.warning("ItensAlfa licenses (sqlite dev): migrate falhou: %s", exc)
        try:
            from home_notice_service import ensure_home_notice_schema

            ensure_home_notice_schema(engine)
        except Exception as exc:
            log.warning("Mural home (sqlite dev): migrate falhou: %s", exc)
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
            payload_col = conn.execute(text(
                "SHOW COLUMNS FROM `orders` LIKE 'payload_json'"
            )).fetchone()
            if payload_col is None:
                log.warning("Migrando orders — adicionando payload_json")
                conn.execute(text(
                    "ALTER TABLE `orders` ADD COLUMN `payload_json` TEXT NULL"
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
    try:
        from ticket_service import ensure_ticket_schema

        ensure_ticket_schema(engine)
    except Exception as exc:
        log.warning("Tickets: migrate falhou: %s", exc)
    try:
        from notification_service import ensure_notification_schema

        ensure_notification_schema(engine)
    except Exception as exc:
        log.warning("Notificações: migrate falhou: %s", exc)
    try:
        from poll_service import ensure_poll_schema

        ensure_poll_schema(engine)
    except Exception as exc:
        log.warning("Votações: migrate falhou: %s", exc)
    try:
        from suggestion_service import ensure_suggestion_schema

        ensure_suggestion_schema(engine)
    except Exception as exc:
        log.warning("Sugestões: migrate falhou: %s", exc)
    try:
        from media_service import ensure_media_schema

        ensure_media_schema(engine)
    except Exception as exc:
        log.warning("Mídias: migrate falhou: %s", exc)
    try:
        from amber_ledger import ensure_amber_schema

        ensure_amber_schema(engine)
    except Exception as exc:
        log.warning("Âmbarômetro: migrate falhou: %s", exc)
    try:
        from lottery_service import ensure_lottery_schema

        ensure_lottery_schema(engine)
    except Exception as exc:
        log.warning("Sorteio: migrate falhou: %s", exc)
    try:
        from custom_dino_service import ensure_custom_dino_schema

        ensure_custom_dino_schema(engine)
    except Exception as exc:
        log.warning("Dino Lab: migrate falhou: %s", exc)
    try:
        from dino_lab_block_service import ensure_dino_lab_block_schema

        ensure_dino_lab_block_schema(engine)
    except Exception as exc:
        log.warning("Dino Lab block: migrate falhou: %s", exc)
    try:
        from tribe_service import ensure_tribe_schema

        ensure_tribe_schema(engine)
    except Exception as exc:
        log.warning("Área de Tribo: migrate falhou: %s", exc)
    try:
        from itensalfa_licenses_migrate import ensure_itensalfa_licenses_schema

        ensure_itensalfa_licenses_schema(engine)
    except Exception as exc:
        log.warning("ItensAlfa licenses: migrate falhou: %s", exc)
    try:
        from home_notice_service import ensure_home_notice_schema

        ensure_home_notice_schema(engine)
    except Exception as exc:
        log.warning("Mural home: migrate falhou: %s", exc)


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
            _schedule_entitlements_reconcile()
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
_ENTITLEMENTS_RECONCILE_STARTED = False
_ENTITLEMENTS_RECONCILE_LOCK = threading.Lock()

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


def _release_db_session(db: Any | None = None) -> None:
    """Libera scoped_session fora de request Flask; no request o teardown chama remove()."""
    if db is None or _SessionLocal is None:
        return
    if has_request_context():
        return
    try:
        db.close()
    except Exception:
        pass
    try:
        _SessionLocal.remove()
    except Exception:
        pass


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
    try:
        from catalog_feed_service import start_catalog_feed_scheduler_if_needed

        start_catalog_feed_scheduler_if_needed()
    except Exception:
        pass
    try:
        from tribe_log_poller import start_tribe_log_poller_if_needed

        start_tribe_log_poller_if_needed()
    except Exception:
        pass
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
        "steam_api_key": "",
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


def _normalize_steam_id64(value: Any) -> str | None:
    """SteamID64 canônico (strip + rejeita inválidos)."""
    sid = str(value or "").strip()
    if sid.endswith(".0") and sid[:-2].isdigit():
        sid = sid[:-2]
    return sid if _STEAMID64_RE.match(sid) else None


def _is_valid_steamid64(value: str) -> bool:
    return _normalize_steam_id64(value) is not None


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


def _display_name_needs_steam_backfill(display_name: str | None, steam_id: str) -> bool:
    nm = (display_name or "").strip()
    return not nm or nm == steam_id


def _steam_persona_needs_backfill(steam_persona: str | None, steam_id: str) -> bool:
    nm = (steam_persona or "").strip()
    return not nm or nm == steam_id


def _admin_player_persona_label(
    steam_id: str,
    *,
    steam_persona: str | None = None,
) -> str:
    """Nome exibido no admin: apenas steam_persona (nick Steam real)."""
    if steam_persona and str(steam_persona).strip() and str(steam_persona).strip() != steam_id:
        return str(steam_persona).strip()[:128]
    for p in _load_players():
        if str(p.get("steam_id", "")).strip() == steam_id:
            nm = str(p.get("name") or "").strip()
            if nm and nm != steam_id:
                return nm[:128]
    return steam_id


def _resolve_player_display_name(
    steam_id: str,
    *,
    store_name: str | None = None,
) -> str:
    """Nome de sistema (store_users.display_name); nunca usa market_display_name."""
    if store_name and str(store_name).strip():
        name = str(store_name).strip()
        if name != steam_id:
            return name[:128]
    for p in _load_players():
        if str(p.get("steam_id", "")).strip() == steam_id:
            nm = str(p.get("name") or "").strip()
            if nm:
                return nm[:128]
    return steam_id


def _touch_store_user_login(steam_id: str) -> None:
    """Registra ou atualiza conta web no login Steam — sempre sobrescreve steam_persona."""
    if not _db_ready() or not _is_valid_steamid64(steam_id):
        return
    db = _SessionLocal()
    try:
        now = _now()
        _refresh_steam_persona(db, steam_id)
        row = db.get(StoreUser, steam_id)
        if row is None:
            row = StoreUser(steam_id=steam_id, last_login_at=now)
            db.add(row)
        row.last_login_at = now
        try:
            from lottery_service import ensure_fixed_lottery_number

            ensure_fixed_lottery_number(db, steam_id)
        except Exception as lot_exc:
            log.warning("fixed_lottery_number no login %s: %s", steam_id, lot_exc)
        db.commit()
    except Exception as exc:
        db.rollback()
        _log_error("touch_store_user_login", steam_id=steam_id, error=str(exc))
    finally:
        _release_db_session(db)


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
            db.add(StoreUser(
                steam_id=sid,
                display_name=_resolve_player_display_name(sid),
                created_at=now,
            ))
        db.commit()
        if steam_ids:
            _log("store_users_backfill", count=len(steam_ids))
    except Exception as exc:
        db.rollback()
        log.warning("store_users backfill falhou: %s", exc)
    finally:
        _release_db_session(db)


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
        _release_db_session(db)


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
        _release_db_session(db)


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
            "display_name": "COALESCE(su.display_name, su.steam_id)",
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
            "su.steam_id, su.display_name, su.steam_persona, "
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
        persona_map, persona_meta = _backfill_steam_personas(
            db, [(str(r[0]), r[2]) for r in rows], return_status=True,
        )
        items: list[dict[str, Any]] = []
        for r in rows:
            sid = _normalize_steam_id64(r[0]) or str(r[0]).strip()
            cached_persona = (str(r[2]).strip() if r[2] else "") or None
            if cached_persona == sid:
                cached_persona = None
            persona = persona_map.get(sid) or cached_persona
            label = _admin_player_persona_label(sid, steam_persona=persona)
            ents = _get_player_entitlements(sid, db=db)
            license_groups = [e["group"] for e in ents if not _is_staff_role_group(e["group"])]
            staff_roles = [e["group"] for e in ents if _is_staff_role_group(e["group"])]
            items.append({
                "steam_id": sid,
                "steam_persona": persona if persona and str(persona).strip() != sid else None,
                "display_name": label,
                "points": int(r[4] or 0),
                "site_access_blocked": bool(r[5]),
                "ban_reason": r[6],
                "created_at": _dt_iso(r[7]),
                "last_login_at": _dt_iso(r[8]),
                "licenses": license_groups,
                "staff_roles": staff_roles,
            })
        return {
            "ok": True,
            "items": items,
            "total": total,
            "offset": offset,
            "limit": limit,
            **persona_meta,
        }
    except Exception as exc:
        _log_error("list_admin_players", error=str(exc))
        return {"ok": False, "error": str(exc)}
    finally:
        _release_db_session(db)


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
            kit_stash = parse_kit_stash(row[0] if row else None)
        except Exception:
            kit_stash = {}
        kit_limits = _build_player_kit_limits(db, steam_id, kit_stash=kit_stash)
        persona = _refresh_steam_persona(db, steam_id) if su else None
        display_name = _admin_player_persona_label(steam_id, steam_persona=persona)
        reg_fields = _auth_regulamento_fields(steam_id, db=db)
        return {
            "ok": True,
            "player": {
                "steam_id": steam_id,
                "steam_persona": persona if persona and str(persona).strip() != steam_id else None,
                "display_name": display_name,
                "points": points,
                "site_access_blocked": bool(su and su.site_access_blocked),
                "ban_reason": su.ban_reason if su else None,
                "created_at": _dt_iso(su.created_at) if su else None,
                "last_login_at": _dt_iso(su.last_login_at) if su else None,
                "market_display_name": (prof.market_display_name if prof else None),
                "commerce_enabled": bool(prof.commerce_enabled) if prof else False,
                "entitlements": _filter_license_entitlements(entitlements),
                "staff_roles": _get_player_staff_roles_from_list(entitlements),
                "kit_stash": kit_stash,
                "kit_limits": kit_limits,
                "listings_count": listings_count,
                **reg_fields,
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
            "staff_role_catalog": _staff_role_catalog(),
            "kit_catalog": _catalog_kit_options(),
        }
    except Exception as exc:
        _log_error("get_admin_player_detail", steam_id=steam_id, error=str(exc))
        return {"ok": False, "error": str(exc)}
    finally:
        _release_db_session(db)


_LICENSE_GROUP_SKIP = frozenset({"Admins", "Staff", "Default", "VIPDoacao", ""})
_LICENSE_ID_GROUP_FALLBACK: dict[str, str] = {
    "delta": "Delta",
    "gamma": "Gamma",
    "gama": "Gamma",
    "beta": "Beta",
    "alfa": "Alfa",
    "omega": "Omega",
    "transcendente": "Transcendente",
    "etereo": "Etereo",
    "universal": "Universal",
    "onipotente": "Onipotente",
    "surreal": "Surreal",
    "imaterial": "Imaterial",
    "exotico": "Exotico",
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
    lic = _get_license_grant(entry, item_id)
    if lic and str(lic.get("Group") or "").strip():
        return str(lic["Group"]).strip()
    for perm in _parse_permissions_field(entry):
        if perm not in _LICENSE_GROUP_SKIP:
            return perm
    key = str(item_id or "").strip().lower()
    if key.startswith("licenca_"):
        suffix = key[8:]
        if suffix.endswith("_renovacao"):
            suffix = suffix[: -len("_renovacao")]
        if suffix in _LICENSE_ID_GROUP_FALLBACK:
            return _LICENSE_ID_GROUP_FALLBACK[suffix]
        parts = suffix.split("_")
        if len(parts) == 2 and parts[0] == "vip":
            tier = parts[1]
            return "VIP" + (tier[:1].upper() + tier[1:] if tier else "")
    return str(item_id or "").strip()


def _catalog_license_days(entry: dict[str, Any], item_id: str = "") -> int:
    lic = entry.get("LicenseGrant")
    if isinstance(lic, dict) and lic.get("Days") is not None:
        return int(lic.get("Days", 30) or 30)
    cmd_grant = _license_grant_from_commands(entry)
    if cmd_grant and cmd_grant.get("Days") is not None:
        return int(cmd_grant.get("Days", 30) or 30)
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
        days = _catalog_license_days(entry, key)
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
    current = _player_points_tx(db, steam_id)
    if current < amount:
        raise ValueError("insufficient_balance")
    return _set_player_points_tx(db, steam_id, current - amount)


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
        delta = after - before
        if delta != 0:
            try:
                from amber_ledger import record_admin_adjust

                record_admin_adjust(
                    db,
                    steam_id=steam_id,
                    delta=delta,
                    event_type=event_type,
                    idempotency_key=f"admin:player:{steam_id}:{int(_now().timestamp() * 1000000)}",
                    commit=True,
                )
            except Exception as amber_exc:
                log.warning("Âmbarômetro admin player hook: %s", amber_exc)
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
            delta=delta,
        )
        return {"ok": True, "steam_id": steam_id, "points": after, "before": before, "after": after}
    except Exception as exc:
        db.rollback()
        return {"ok": False, "error": str(exc)}
    finally:
        _release_db_session(db)


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
        _release_db_session(db)


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
    if _is_staff_role_group(group):
        return {
            "ok": False,
            "error": "MOD/STAFF são cargos da equipe — use a seção Cargos no painel do jogador.",
        }
    action = str(action or "grant").strip().lower()
    if not _db_ready():
        return {"ok": False, "error": "Banco não configurado"}
    admin_sid = str(_steam_id_from_session() or "")
    perm_sync: list[dict[str, Any]] = []
    try:
        if action == "grant":
            _grant_player_entitlement(
                steam_id,
                group,
                int(days),
                source=f"admin:{admin_sid}",
                notes=reason or "grant_admin",
            )
            perm_sync = _sync_license_permissions_all_servers(
                steam_id, group, grant=True, days=int(days),
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
            perm_sync = _sync_license_permissions_all_servers(
                steam_id, group, grant=False,
            )
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
            "entitlements": _filter_license_entitlements(_get_player_entitlements(steam_id)),
            "permissions_sync": perm_sync,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _is_staff_role_group(group: str) -> bool:
    return str(group or "").strip() in STAFF_ROLE_GROUPS


def _staff_role_catalog() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for group in sorted(STAFF_ROLE_GROUPS, key=lambda g: STAFF_ROLE_LABELS.get(g, g)):
        out.append({
            "group": group,
            "label": STAFF_ROLE_LABELS.get(group, group),
            "timed_bonus": LICENSE_TIMED_BONUS.get(group, 0),
            "permanent": True,
        })
    return out


def _filter_license_entitlements(entitlements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in entitlements if not _is_staff_role_group(str(e.get("group") or ""))]


def _get_player_staff_roles_from_list(entitlements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in entitlements if _is_staff_role_group(str(e.get("group") or ""))]


def _get_player_staff_roles(steam_id: str) -> list[dict[str, Any]]:
    return _get_player_staff_roles_from_list(_get_player_entitlements(steam_id))


def _sync_permissions_all_servers(
    steam_id: str,
    group: str,
    *,
    grant: bool,
) -> list[dict[str, Any]]:
    """Sincroniza grupo MOD/STAFF no plugin Permissions (MySQL + RCON)."""
    results: list[dict[str, Any]] = []
    shop_url = _ACTIVE_DATABASE_URL or _resolve_database_url()
    try:
        from permission_db_sync import grant_group_in_permission_db, revoke_group_in_permission_db

        if grant:
            db_res = grant_group_in_permission_db(shop_url, steam_id, group, days=0)
        else:
            db_res = revoke_group_in_permission_db(shop_url, steam_id, group)
        results.append({
            "server_id": "mysql",
            "label": "ark_permission (MySQL)",
            "ok": bool(db_res.get("ok")),
            "error": db_res.get("error"),
            "response": db_res.get("note") or "OK",
        })
    except Exception as exc:
        results.append({
            "server_id": "mysql",
            "label": "ark_permission (MySQL)",
            "ok": False,
            "error": str(exc),
        })

    settings = _load_settings()
    servers = _load_servers()
    cmd = (
        f"Permissions.Add {steam_id} {group}"
        if grant
        else f"Permissions.Remove {steam_id} {group}"
    )
    targets: list[dict[str, Any] | None] = list(servers) if servers else [None]
    for srv in targets:
        sid = str(srv.get("server_id") or "").strip() if srv else None
        label = str(srv.get("label") or sid or "padrão") if srv else "padrão"
        host, port, password, _ = _resolve_rcon_target(sid, settings)
        if not password:
            results.append({
                "server_id": sid or "default",
                "label": label,
                "ok": False,
                "error": "RCON sem senha configurada",
            })
            continue
        try:
            resp = _rcon_command(host, port, password, cmd, connect_retries=2)
            results.append({
                "server_id": sid or "default",
                "label": label,
                "ok": True,
                "response": resp[:120],
            })
        except Exception as exc:
            results.append({
                "server_id": sid or "default",
                "label": label,
                "ok": False,
                "error": str(exc),
            })
    return results


def _parse_entitlement_expires(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _entitlement_hours_remaining(
    steam_id: str,
    group: str,
    *,
    fallback_days: int = 30,
    entitlements: list[dict[str, Any]] | None = None,
) -> int:
    """Horas restantes da licença em player_entitlements (após renovação com soma)."""
    ents = entitlements if entitlements is not None else _get_player_entitlements(steam_id)
    for ent in ents:
        if str(ent.get("group") or "") != str(group):
            continue
        if ent.get("permanent"):
            return 0
        exp = _parse_entitlement_expires(ent.get("expires_at") or ent.get("expires"))
        if exp is None:
            return 0
        now = datetime.now(timezone.utc)
        secs = (exp - now).total_seconds()
        return max(1, int((secs + 3599) // 3600))  # ceil hours
    return max(1, int(fallback_days or 30) * 24)


def _sync_license_permissions_all_servers(
    steam_id: str,
    group: str,
    *,
    grant: bool,
    days: int = 0,
) -> list[dict[str, Any]]:
    """Sincroniza licença no Permissions (MySQL directo + RCON nos mapas).

    Em grant temporário usa horas restantes de player_entitlements (após renovação
    que soma dias) — não só days*24 a partir de agora.
    """
    results: list[dict[str, Any]] = []
    shop_url = _ACTIVE_DATABASE_URL or _resolve_database_url()
    hours_for_rcon = max(1, int(days or 0) * 24) if int(days or 0) > 0 else 0
    try:
        from permission_db_sync import grant_group_in_permission_db, revoke_group_in_permission_db

        if grant:
            # Espelha expires real (inclui residual + dias novos) em ark_permission.
            ents = _get_player_entitlements(steam_id)
            if any(
                str(e.get("group") or "") == str(group)
                for e in ents
            ):
                db_res_list = _sync_player_entitlements_to_permission_db(steam_id, ents)
                results.extend(db_res_list)
                hours_for_rcon = _entitlement_hours_remaining(
                    steam_id, group, fallback_days=int(days or 30), entitlements=ents,
                )
            else:
                db_res = grant_group_in_permission_db(
                    shop_url, steam_id, group, days=int(days or 0),
                )
                results.append({
                    "server_id": "mysql",
                    "label": "ark_permission (MySQL)",
                    "ok": bool(db_res.get("ok")),
                    "error": db_res.get("error"),
                    "response": "OK",
                })
        else:
            db_res = revoke_group_in_permission_db(shop_url, steam_id, group)
            results.append({
                "server_id": "mysql",
                "label": "ark_permission (MySQL)",
                "ok": bool(db_res.get("ok")),
                "error": db_res.get("error"),
                "response": "OK",
            })
    except Exception as exc:
        results.append({
            "server_id": "mysql",
            "label": "ark_permission (MySQL)",
            "ok": False,
            "error": str(exc),
        })

    settings = _load_settings()
    servers = _load_servers()
    if grant:
        cmd = (
            f"Permissions.Add {steam_id} {group}"
            if int(days) <= 0 and hours_for_rcon <= 0
            else f"Permissions.AddTimed {steam_id} {group} {int(hours_for_rcon)}"
        )
    else:
        cmd = f"Permissions.Remove {steam_id} {group}"
    targets: list[dict[str, Any] | None] = list(servers) if servers else [None]
    for srv in targets:
        sid = str(srv.get("server_id") or "").strip() if srv else None
        label = str(srv.get("label") or sid or "padrão") if srv else "padrão"
        host, port, password, _ = _resolve_rcon_target(sid, settings)
        if not password:
            results.append({
                "server_id": sid or "default",
                "label": label,
                "ok": False,
                "error": "RCON sem senha configurada",
            })
            continue
        try:
            resp = _rcon_command(host, port, password, cmd, connect_retries=2)
            results.append({
                "server_id": sid or "default",
                "label": label,
                "ok": True,
                "response": resp[:120],
            })
        except Exception as exc:
            results.append({
                "server_id": sid or "default",
                "label": label,
                "ok": False,
                "error": str(exc),
            })
    return results


def _admin_player_staff_role(
    steam_id: str,
    *,
    action: str,
    group: str = "",
    reason: str = "",
) -> dict[str, Any]:
    steam_id = str(steam_id or "").strip()
    group = str(group or "").strip()
    if not _is_valid_steamid64(steam_id):
        return {"ok": False, "error": "SteamID64 inválido"}
    if not group:
        return {"ok": False, "error": "Cargo obrigatório"}
    if not _is_staff_role_group(group):
        return {"ok": False, "error": f"Cargo inválido: {group}"}
    action = str(action or "grant").strip().lower()
    if not _db_ready():
        return {"ok": False, "error": "Banco não configurado"}
    admin_sid = str(_steam_id_from_session() or "")
    try:
        if action == "grant":
            _grant_player_entitlement(
                steam_id,
                group,
                0,
                source=f"staff_role:admin:{admin_sid}",
                notes=reason or "staff_grant",
            )
            _audit_event(
                "admin_player_staff_role_grant",
                actor_type="admin",
                actor_steam_id=admin_sid,
                target_steam_id=steam_id,
                item_id=group,
                message=reason or f"Cargo {group} concedido",
            )
            perm_sync = _sync_permissions_all_servers(steam_id, group, grant=True)
        elif action == "revoke":
            _revoke_player_entitlement_by_group(steam_id, group)
            _audit_event(
                "admin_player_staff_role_revoke",
                actor_type="admin",
                actor_steam_id=admin_sid,
                target_steam_id=steam_id,
                item_id=group,
                message=reason or f"Cargo {group} removido",
            )
            perm_sync = _sync_permissions_all_servers(steam_id, group, grant=False)
        else:
            return {"ok": False, "error": f"Ação inválida: {action}"}
        return {
            "ok": True,
            "steam_id": steam_id,
            "group": group,
            "action": action,
            "staff_roles": _get_player_staff_roles(steam_id),
            "permissions_sync": perm_sync,
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
            _release_db_session(db)
    if mode == "deliver":
        order, error = _create_order(
            steam_id, "kit", kit_id, amount, admin_skip_kit_limit=True,
        )
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
            _release_db_session(db)
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


def _admin_steamids_file_cache_key() -> str:
    try:
        path = _ADMIN_FILE.resolve()
        if path.is_file():
            return f"{path}:{path.stat().st_mtime_ns}"
    except OSError:
        pass
    return str(_ADMIN_FILE)


def _load_admin_steamids(*, db_timeout: float = _ADMIN_DB_QUERY_TIMEOUT) -> set[str]:
    """Lista admins — arquivo primeiro; DB opcional com cache, backoff e timeout."""
    now = time.monotonic()
    cached = _ADMIN_STEAMIDS_CACHE.get("ids")
    file_key = _admin_steamids_file_cache_key()
    if (
        isinstance(cached, set)
        and now < float(_ADMIN_STEAMIDS_CACHE.get("expires") or 0)
        and _ADMIN_STEAMIDS_CACHE.get("file_key") == file_key
    ):
        return cached

    ids = _load_admin_steamids_from_file()
    if _db_ready():
        ids = _merge_admin_steamids_from_db(ids, timeout=db_timeout)

    _ADMIN_STEAMIDS_CACHE["ids"] = ids
    _ADMIN_STEAMIDS_CACHE["file_key"] = file_key
    _ADMIN_STEAMIDS_CACHE["expires"] = now + _ADMIN_STEAMIDS_CACHE_TTL
    return ids


def _is_admin_steamid(steam_id: str) -> bool:
    return steam_id in _load_admin_steamids()


_SUPPORT_STEAMIDS_CACHE: dict[str, Any] = {
    "ids": None,
    "expires": 0.0,
    "db_skip_until": 0.0,
}
_SUPPORT_STEAMIDS_CACHE_TTL = 30.0
_SUPPORT_STEAMIDS_DB_BACKOFF = 60.0


def _load_support_steamids_from_file() -> set[str]:
    if not _SUPPORT_FILE.exists():
        return set()
    try:
        data = json.loads(_SUPPORT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return set()

    values = data if isinstance(data, list) else data.get("steam_ids", []) if isinstance(data, dict) else []
    return {str(v).strip() for v in values if isinstance(v, (str, int)) and _is_valid_steamid64(str(v))}


def _merge_support_steamids_from_db(ids: set[str], *, timeout: float) -> set[str]:
    if not _db_ready() or _SessionLocal is None:
        return ids
    now = time.monotonic()
    if now < float(_SUPPORT_STEAMIDS_CACHE.get("db_skip_until") or 0):
        return ids

    merged = set(ids)
    done = threading.Event()
    err: list[Exception | None] = [None]

    def _worker() -> None:
        db = _SessionLocal()
        try:
            rows = db.query(ShopSupport).all()
            for row in rows:
                sid = str(getattr(row, "steam_id", "") or "").strip()
                if _is_valid_steamid64(sid):
                    merged.add(sid)
        except Exception as exc:
            err[0] = exc
        finally:
            _release_db_session(db)
            done.set()

    threading.Thread(target=_worker, name="arkshop-support-db", daemon=True).start()
    if not done.wait(timeout):
        _SUPPORT_STEAMIDS_CACHE["db_skip_until"] = now + _SUPPORT_STEAMIDS_DB_BACKOFF
        log.warning(
            "ShopSupport timeout (%ss) — usando suporte do arquivo por %ss",
            timeout,
            int(_SUPPORT_STEAMIDS_DB_BACKOFF),
        )
        return ids
    if err[0] is not None:
        _SUPPORT_STEAMIDS_CACHE["db_skip_until"] = now + _SUPPORT_STEAMIDS_DB_BACKOFF
        log.warning(
            "ShopSupport indisponível — usando suporte do arquivo por %ss",
            int(_SUPPORT_STEAMIDS_DB_BACKOFF),
        )
        return ids
    return merged


def _load_support_steamids(*, db_timeout: float = _ADMIN_DB_QUERY_TIMEOUT) -> set[str]:
    now = time.monotonic()
    cached = _SUPPORT_STEAMIDS_CACHE.get("ids")
    if isinstance(cached, set) and now < float(_SUPPORT_STEAMIDS_CACHE.get("expires") or 0):
        return cached

    ids = _load_support_steamids_from_file()
    if _db_ready():
        ids = _merge_support_steamids_from_db(ids, timeout=db_timeout)

    _SUPPORT_STEAMIDS_CACHE["ids"] = ids
    _SUPPORT_STEAMIDS_CACHE["expires"] = now + _SUPPORT_STEAMIDS_CACHE_TTL
    return ids


def _invalidate_support_steamids_cache() -> None:
    _SUPPORT_STEAMIDS_CACHE["ids"] = None
    _SUPPORT_STEAMIDS_CACHE["expires"] = 0.0


def _is_support_steamid(steam_id: str) -> bool:
    if _is_admin_steamid(steam_id):
        return False
    return steam_id in _load_support_steamids()


def _can_manage_tickets(steam_id: str) -> bool:
    return _is_admin_steamid(steam_id) or steam_id in _load_support_steamids()


def _get_player_points(steam_id: str, db: Any | None = None) -> int | None:
    """Returns points balance from the shared MySQL players table, or None if unavailable."""
    if not _db_ready():
        return None
    owns_session = db is None
    if owns_session:
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
        if owns_session:
            _release_db_session(db)


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
        _release_db_session(db)


def _db_engine_url(db: Any | None = None) -> str:
    if db is not None:
        try:
            bind = db.get_bind()
            if bind is not None:
                return str(bind.url).lower()
        except Exception:
            pass
        legacy = getattr(db, "bind", None)
        if legacy is not None:
            return str(legacy.url).lower()
    return str(_ACTIVE_DATABASE_URL or "").lower()


def _is_mysql_engine(db: Any | None = None) -> bool:
    return "mysql" in _db_engine_url(db)


def _player_points_tx(db: Any, steam_id: str) -> int:
    row = db.execute(
        text("SELECT points FROM players WHERE steam_id = :sid"),
        {"sid": str(steam_id)},
    ).fetchone()
    return int(row[0]) if row else 0


def _add_player_points_tx(db: Any, steam_id: str, amount: int) -> int:
    """Credita pontos na sessão atual (sem commit)."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    if _is_mysql_engine(db):
        db.execute(
            text(
                "INSERT INTO players (steam_id, points, kits) VALUES (:sid, :pts, '{}') "
                "ON DUPLICATE KEY UPDATE points = points + :pts"
            ),
            {"sid": steam_id, "pts": amount},
        )
    else:
        db.execute(
            text(
                "INSERT INTO players (steam_id, points, kits) VALUES (:sid, :pts, '{}') "
                "ON CONFLICT(steam_id) DO UPDATE SET points = points + :pts"
            ),
            {"sid": steam_id, "pts": amount},
        )
    db.flush()
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
        before_balance = _get_player_points(steam_id) or 0
        if action == "get":
            return {
                "ok": True,
                "steam_id": steam_id,
                "points": before_balance,
                "response": f"Saldo: {before_balance:,}".replace(",", "."),
            }
        if action == "add":
            if amount <= 0:
                return {"ok": False, "error": "Quantidade deve ser maior que zero"}
            new_balance = _add_player_points_tx(db, steam_id, amount)
            db.commit()
            try:
                from amber_ledger import record_admin_adjust

                record_admin_adjust(
                    db,
                    steam_id=steam_id,
                    delta=amount,
                    event_type="admin_points_add",
                    idempotency_key=f"admin:api:add:{steam_id}:{int(_now().timestamp() * 1000000)}",
                    commit=True,
                )
            except Exception as amber_exc:
                log.warning("Âmbarômetro admin points add hook: %s", amber_exc)
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
            delta = new_balance - before_balance
            if delta != 0:
                try:
                    from amber_ledger import record_admin_adjust

                    record_admin_adjust(
                        db,
                        steam_id=steam_id,
                        delta=delta,
                        event_type="admin_points_set",
                        idempotency_key=f"admin:api:set:{steam_id}:{int(_now().timestamp() * 1000000)}",
                        commit=True,
                    )
                except Exception as amber_exc:
                    log.warning("Âmbarômetro admin points set hook: %s", amber_exc)
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
        _release_db_session(db)


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
LICENSE_TIMED_BONUS = {
    "Default": 25,
    "Delta": 5,
    "Gamma": 25,
    "Beta": 50,
    "Alfa": 75,
    "Omega": 90,
    "Transcendente": 105,
    "Etereo": 120,
    "Universal": 135,
    "Onipotente": 150,
    "Surreal": 165,
    "Imaterial": 180,
    "Exotico": 200,
    "Moderacao": 500,
    "STAFF": 1000,
}
# Renovação recente (−10%) até N dias após expirar; antecipada (−20%) via SKU *_renovacao.
LICENSE_RECENT_RENEWAL_DAYS = 7
LICENSE_RECENT_RENEWAL_FACTOR = 0.90
STAFF_ROLE_GROUPS = frozenset({"Moderacao", "Mod", "STAFF"})
STAFF_ROLE_LABELS: dict[str, str] = {
    "Moderacao": "MOD",
    "Mod": "MOD",
    "STAFF": "STAFF",
}


def _parse_permissions_field(entry: dict[str, Any]) -> list[str]:
    raw = entry.get("Permissions") or entry.get("RequiredPermissions") or ""
    if isinstance(raw, list):
        return [str(g).strip() for g in raw if str(g).strip()]
    if not raw:
        return []
    return [t.strip() for t in str(raw).split(",") if t.strip()]


def _license_grant_from_commands(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Fallback legado: licenças Type command com Permissions.AddTimed no catálogo."""
    commands = entry.get("Commands")
    if not isinstance(commands, list):
        return None
    for raw in commands:
        if isinstance(raw, dict):
            cmd = str(raw.get("Command") or raw.get("command") or "")
        else:
            cmd = str(raw or "")
        if "Permissions.AddTimed" not in cmd and "Permissions.Add " not in cmd:
            continue
        for group in (
            "keyvault",
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
            "VIPBronze",
            "VIPPrata",
            "VIPOuro",
            "VIPDiamante",
        ):
            if group in cmd:
                hours_m = re.search(r"Permissions\.AddTimed\s+\{?SteamID\}?\s+\S+\s+(\d+)", cmd, re.I)
                days = 30
                if hours_m:
                    try:
                        days = max(1, int(hours_m.group(1)) // 24)
                    except ValueError:
                        days = 30
                return {"Group": group, "Days": days, "Redeemable": True}
    return None


def _get_license_grant(entry: dict[str, Any], item_id: str = "") -> dict[str, Any] | None:
    lic = entry.get("LicenseGrant")
    if isinstance(lic, dict) and str(lic.get("Group") or "").strip():
        return lic
    from catalog_enrich import _is_license_entry

    key = str(item_id or "").strip().lower()
    if _is_license_entry(entry, key or "item"):
        if key.startswith("licenca_"):
            suffix = key[8:]
            if suffix.endswith("_renovacao"):
                suffix = suffix[: -len("_renovacao")]
            if suffix in _LICENSE_ID_GROUP_FALLBACK:
                return {
                    "Group": _LICENSE_ID_GROUP_FALLBACK[suffix],
                    "Days": _catalog_license_days(entry, key),
                    "Redeemable": True,
                }
        cmd_grant = _license_grant_from_commands(entry)
        if cmd_grant:
            return cmd_grant
    return None


def _catalog_item_map(data: dict[str, Any]) -> dict[str, Any]:
    raw = data.get("Items") or data.get("ShopItems") or {}
    return raw if isinstance(raw, dict) else {}


def _catalog_id_migration_aliases() -> dict[str, str]:
    """Aliases de IDs antigos da loja (migração L1 por blueprint)."""
    path = Path(__file__).resolve().parents[2] / "tools" / "catalog_id_migration.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get("aliases") or {}
        return {str(k): str(v) for k, v in raw.items() if k and v}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _resolve_catalog_item_id(item_type: str, item_id: str) -> str:
    """Resolve aliases (ex.: Gamma → licenca_gamma) para o ID canônico no config."""
    item_id = str(item_id or "").strip()
    if not item_id:
        return item_id
    migration = _catalog_id_migration_aliases()
    if item_id in migration:
        return migration[item_id]
    lower = item_id.lower()
    if lower in migration:
        return migration[lower]
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


def _player_kit_remaining(db, steam_id: str, kit_id: str, entry: dict[str, Any]) -> int:
    """Resgates restantes do kit (DefaultAmount na 1ª vez; depois players.kits)."""
    if not kit_has_limit(entry):
        return 999_999
    row = db.execute(
        text("SELECT kits FROM players WHERE steam_id = :sid"),
        {"sid": str(steam_id)},
    ).fetchone()
    stash = parse_kit_stash(row[0] if row else None)
    resolved = _resolve_catalog_item_id("kit", kit_id)
    return get_kit_remaining(stash, resolved, entry)


def _count_pending_kit_orders(db, steam_id: str, kit_id: str) -> int:
    """Pedidos de kit ainda não entregues — reservam slot de resgate."""
    resolved = _resolve_catalog_item_id("kit", kit_id)
    rows = db.execute(
        text(
            "SELECT item_id FROM orders "
            "WHERE steam_id = :sid AND item_type = 'kit' "
            "AND status IN ('PENDENTE', 'ENTREGANDO')"
        ),
        {"sid": str(steam_id)},
    ).fetchall()
    count = 0
    for row in rows:
        oid = _resolve_catalog_item_id("kit", str(row[0] or ""))
        if oid == resolved:
            count += 1
    return count


def _effective_kit_remaining(
    db,
    steam_id: str,
    kit_id: str,
    entry: dict[str, Any],
) -> int:
    if not kit_has_limit(entry):
        return 999_999
    remaining = _player_kit_remaining(db, steam_id, kit_id, entry)
    pending = _count_pending_kit_orders(db, steam_id, kit_id)
    return max(0, remaining - pending)


def _load_player_kit_stash(db, steam_id: str) -> dict[str, Any]:
    row = db.execute(
        text("SELECT kits FROM players WHERE steam_id = :sid"),
        {"sid": str(steam_id)},
    ).fetchone()
    return parse_kit_stash(row[0] if row else None)


def _save_player_kit_stash(db, steam_id: str, stash: dict[str, Any]) -> None:
    kits_json = json.dumps(stash, ensure_ascii=False)
    if _is_mysql_engine(db):
        db.execute(
            text(
                "INSERT INTO players (steam_id, points, kits) VALUES (:sid, 0, :kits) "
                "ON DUPLICATE KEY UPDATE kits = :kits"
            ),
            {"sid": str(steam_id), "kits": kits_json},
        )
    else:
        db.execute(
            text(
                "INSERT INTO players (steam_id, points, kits) VALUES (:sid, 0, :kits) "
                "ON CONFLICT(steam_id) DO UPDATE SET kits = :kits"
            ),
            {"sid": str(steam_id), "kits": kits_json},
        )


def _reset_dependent_kit_limits_tx(db: Any, steam_id: str, license_group: str) -> list[str]:
    """Na renovação de licença, restaura resgates dos kits que dependem dela."""
    data = _read_shop_config()
    kits = data.get("Kits") or {}
    if not isinstance(kits, dict) or not kits:
        return []
    stash = _load_player_kit_stash(db, steam_id)
    new_stash, reset_ids = reset_kit_limits_for_license(stash, kits, license_group)
    if reset_ids and new_stash != stash:
        _save_player_kit_stash(db, steam_id, new_stash)
    return reset_ids


def _build_player_kit_limits(
    db,
    steam_id: str,
    *,
    kit_stash: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Lista kits com DefaultAmount > 0 e contagem usada/limite."""
    data = _read_shop_config()
    kits = data.get("Kits") or {}
    stash = kit_stash if kit_stash is not None else _load_player_kit_stash(db, steam_id)
    out: list[dict[str, Any]] = []
    for kit_id, entry in kits.items():
        if not isinstance(entry, dict) or not kit_has_limit(entry):
            continue
        resolved = _resolve_catalog_item_id("kit", kit_id)
        status = kit_limit_status(
            stash,
            resolved,
            entry,
            pending_orders=_count_pending_kit_orders(db, steam_id, resolved),
        )
        out.append({
            "kit_id": resolved,
            "label": str(entry.get("Description") or entry.get("Name") or kit_id),
            **status,
        })
    return sorted(out, key=lambda row: row["kit_id"].lower())


def _admin_revoke_kit_limit(
    steam_id: str,
    kit_id: str,
    *,
    reason: str = "",
) -> dict[str, Any]:
    steam_id = str(steam_id or "").strip()
    kit_id = str(kit_id or "").strip()
    if not _is_valid_steamid64(steam_id):
        return {"ok": False, "error": "SteamID64 inválido"}
    if not kit_id:
        return {"ok": False, "error": "kit_id obrigatório"}
    entry = _catalog_entry("kit", kit_id)
    if not entry:
        return {"ok": False, "error": f"Kit «{kit_id}» não encontrado no catálogo"}
    if not kit_has_limit(entry):
        return {
            "ok": False,
            "error": "Este kit não possui limite de resgates (DefaultAmount=0).",
        }
    if not _db_ready():
        return {"ok": False, "error": "Banco não configurado"}
    resolved = _resolve_catalog_item_id("kit", kit_id)
    admin_sid = str(_steam_id_from_session() or "")
    db = _SessionLocal()
    try:
        stash = _load_player_kit_stash(db, steam_id)
        new_stash = reset_kit_limit(stash, resolved, entry)
        _save_player_kit_stash(db, steam_id, new_stash)
        db.commit()
        limit = kit_default_amount(entry)
        _audit_event(
            "admin_kit_limit_revoke",
            actor_type="admin",
            actor_steam_id=admin_sid,
            target_steam_id=steam_id,
            item_type="kit",
            item_id=resolved,
            message=reason or f"Limite de resgates resetado para {resolved} ({limit} usos)",
        )
        return {
            "ok": True,
            "kit_id": resolved,
            "limit": limit,
            "remaining": limit,
            "stash": new_stash,
            "kit_limits": _build_player_kit_limits(db, steam_id, kit_stash=new_stash),
        }
    except Exception as exc:
        db.rollback()
        return {"ok": False, "error": str(exc)}
    finally:
        _release_db_session(db)


def _catalog_price(entry: dict[str, Any], amount: int = 1) -> int:
    return max(0, int(entry.get("Price", 0) or 0)) * max(1, amount)


def _license_group_from_item_id(item_id: str) -> str:
    key = str(item_id or "").strip().lower()
    if not key.startswith("licenca_"):
        return ""
    suffix = key[8:]
    if suffix.endswith("_renovacao"):
        suffix = suffix[: -len("_renovacao")]
    return _LICENSE_ID_GROUP_FALLBACK.get(suffix, "")


def _days_since_license_expiry(steam_id: str, group: str) -> int | None:
    """Dias desde o vencimento da última entitlement do grupo; None se nunca teve / ainda ativa."""
    if not group or not _db_ready():
        return None
    db = _SessionLocal()
    try:
        _ensure_entitlements_schema(db)
        row = db.execute(
            text(
                "SELECT expires FROM player_entitlements "
                "WHERE steam_id = :sid AND group_name = :grp LIMIT 1"
            ),
            {"sid": str(steam_id), "grp": group},
        ).fetchone()
        if not row:
            return None
        expires = row[0]
        if expires is None:
            return None  # permanente
        if hasattr(expires, "timestamp"):
            exp_ts = float(expires.timestamp())
        else:
            try:
                from datetime import datetime as _dt

                exp_ts = _dt.fromisoformat(str(expires).replace("Z", "+00:00")).timestamp()
            except ValueError:
                return None
        now_ts = _now().timestamp() if hasattr(_now(), "timestamp") else float(__import__("time").time())
        if exp_ts > now_ts:
            return None  # ainda ativa — use SKU *_renovacao (−20%)
        return max(0, int((now_ts - exp_ts) // 86400))
    except Exception:
        return None
    finally:
        _release_db_session(db)


def _effective_license_price(
    steam_id: str,
    entry: dict[str, Any],
    item_id: str,
    amount: int = 1,
) -> int:
    """Preço de licença com renovação recente −10% (0–7 dias após expirar).

    Renovação antecipada −20% usa IDs `licenca_*_renovacao` no catálogo (já com preço).
    """
    base = _catalog_price(entry, amount)
    key = str(item_id or "").strip().lower()
    if key.endswith("_renovacao"):
        return base
    lic = _get_license_grant(entry, item_id)
    group = ""
    if isinstance(lic, dict):
        group = str(lic.get("Group") or "").strip()
    if not group:
        group = _license_group_from_item_id(item_id)
    if group not in PAID_LICENSE_GROUPS:
        return base
    days_gone = _days_since_license_expiry(str(steam_id), group)
    if days_gone is None:
        return base
    if 0 <= days_gone <= LICENSE_RECENT_RENEWAL_DAYS:
        return max(0, int(round(base * LICENSE_RECENT_RENEWAL_FACTOR)))
    return base


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
        paid_list = ", ".join(f"'{g}'" for g in sorted(PAID_LICENSE_GROUPS))
        db.execute(
            text(
                "DELETE FROM player_entitlements "
                f"WHERE steam_id = :sid AND group_name IN ({paid_list}) "
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
        # SQLite: soma dias a partir do maior entre agora e expires actual (paridade MySQL).
        db.execute(
            text(
                "INSERT INTO player_entitlements (steam_id, group_name, expires, source, notes) "
                "VALUES (:sid, :grp, datetime('now', '+' || :days || ' days'), :src, :notes) "
                "ON CONFLICT(steam_id, group_name) DO UPDATE SET "
                "expires = datetime("
                "  CASE WHEN expires IS NULL OR expires < datetime('now') "
                "       THEN datetime('now') ELSE expires END,"
                "  '+' || :days || ' days'"
                "), "
                "source = excluded.source, notes = excluded.notes"
            ),
            params,
        )
    _reset_dependent_kit_limits_tx(db, steam_id, group)


def _get_player_entitlements(steam_id: str, db: Any | None = None) -> list[dict[str, Any]]:
    if not _db_ready():
        return []
    owns_session = db is None
    if owns_session:
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
        if owns_session:
            _release_db_session(db)


def _compute_timed_points_total(groups: list[str]) -> int:
    total = LICENSE_TIMED_BONUS.get("Default", 25)
    for g in groups:
        if g == "Default":
            continue
        total += LICENSE_TIMED_BONUS.get(g, 0)
    return total


def _schedule_entitlements_reconcile() -> None:
    """Ao subir a web store, reconcilia entitlements ↔ ark_permission em background."""
    global _ENTITLEMENTS_RECONCILE_STARTED
    with _ENTITLEMENTS_RECONCILE_LOCK:
        if _ENTITLEMENTS_RECONCILE_STARTED:
            return
        _ENTITLEMENTS_RECONCILE_STARTED = True

    def _worker() -> None:
        if not _db_ready():
            return
        shop_url = _ACTIVE_DATABASE_URL or _resolve_database_url()
        if not shop_url or "sqlite" in shop_url.lower():
            return
        try:
            from permission_db_sync import reconcile_entitlements_with_permission_db

            res = reconcile_entitlements_with_permission_db(shop_url)
            if res.get("ok"):
                log.info(
                    "Reconciliação entitlements→ark_permission: verificados=%s irregulares=%s corrigidos=%s",
                    res.get("checked", 0),
                    res.get("irregular", 0),
                    res.get("synced", 0),
                )
            else:
                log.warning("Reconciliação entitlements falhou: %s", res.get("error"))
        except Exception as exc:
            log.warning("Reconciliação entitlements exceção: %s", exc)

    threading.Thread(
        target=_worker, daemon=True, name="entitlements-reconcile",
    ).start()


def _reconcile_all_entitlements_to_permission_db(*, dry_run: bool = False) -> dict[str, Any]:
    shop_url = _ACTIVE_DATABASE_URL or _resolve_database_url()
    if not shop_url or "sqlite" in shop_url.lower():
        return {"ok": False, "error": "Banco MySQL não configurado"}
    try:
        from permission_db_sync import reconcile_entitlements_with_permission_db

        return reconcile_entitlements_with_permission_db(shop_url, dry_run=dry_run)
    except Exception as exc:
        _log_error("reconcile_all_entitlements", error=str(exc))
        return {"ok": False, "error": str(exc)}


def _sync_player_entitlements_to_permission_db(
    steam_id: str,
    entitlements: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Espelha player_entitlements (arkland_shop) em ark_permission.players."""
    ents = entitlements if entitlements is not None else _get_player_entitlements(steam_id)
    shop_url = _ACTIVE_DATABASE_URL or _resolve_database_url()
    try:
        from permission_db_sync import sync_entitlements_to_permission_db

        res = sync_entitlements_to_permission_db(shop_url, str(steam_id), ents)
        return [{
            "server_id": "mysql",
            "label": "ark_permission (MySQL)",
            "ok": bool(res.get("ok")),
            "error": res.get("error"),
            "response": ",".join(res.get("timed_groups") or []) or "OK",
        }]
    except Exception as exc:
        _log_error("sync_entitlements_permission_db", steam_id=steam_id, error=str(exc))
        return [{
            "server_id": "mysql",
            "label": "ark_permission (MySQL)",
            "ok": False,
            "error": str(exc),
        }]


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


def _order_license_group(order: Order) -> str | None:
    item_type = str(order.item_type or "shop")
    item_id = str(order.item_id or "")
    resolved_id = _resolve_catalog_item_id(item_type, item_id)
    entry = _catalog_entry(
        "kit" if item_type == "kit" else "shop",
        item_id,
    )
    lic = _get_license_grant(entry, resolved_id)
    if not lic or lic.get("Redeemable") is False:
        return None
    group = str(lic.get("Group") or "").strip()
    return group or None


def _order_license_already_fulfilled(order: Order) -> bool:
    """True só se ESTE pedido já gravou o entitlement (source=order_id).

    Ter o grupo activo por residual antigo NÃO conta — renovação deve
    sincronizar Permissions / AddTimed com o novo expires.
    """
    group = _order_license_group(order)
    if not group:
        return False
    oid = str(order.order_id or "")
    for ent in _get_player_entitlements(str(order.steam_id)):
        if ent.get("group") == group and str(ent.get("source") or "") == oid:
            return True
    return False


def _finalize_license_order_if_fulfilled(db, order: Order, *, reason: str) -> bool:
    """Marca ENTREGUE quando o entitlement deste pedido já existe; re-sync Permissions."""
    if not _order_license_already_fulfilled(order):
        return False
    group = _order_license_group(order) or ""
    before = order.status
    order.status = "ENTREGUE"
    order.last_error = None
    order.updated_at = _now()
    _audit_event(
        "delivery_confirmed",
        source="web",
        actor_type="system",
        target_steam_id=str(order.steam_id),
        order_id=order.order_id,
        server_id=order.server_id,
        item_type=order.item_type,
        item_id=order.item_id,
        amount=order.amount,
        status_before=before,
        status_after="ENTREGUE",
        message=f"Licença já activa neste pedido; finalizado ({reason})",
        reason=reason,
    )
    if group:
        try:
            days_hint = 30
            entry = _catalog_entry(
                "kit" if str(order.item_type or "") == "kit" else "shop",
                str(order.item_id or ""),
            )
            if entry:
                lic = _get_license_grant(entry, str(order.item_id or ""))
                if lic:
                    days_hint = int(lic.get("Days", 30) or 30)
            _sync_license_permissions_all_servers(
                str(order.steam_id),
                group,
                grant=True,
                days=days_hint,
            )
        except Exception as exc:
            _log_error(
                "finalize_license_perm_resync",
                order_id=order.order_id,
                steam_id=str(order.steam_id),
                group=group,
                error=str(exc),
            )
    return True


def _ensure_license_entitlement_for_order(order: Order, *, reason: str = "") -> bool:
    """Garante player_entitlements para pedidos de licença (reparo pós-entrega)."""
    item_type = str(order.item_type or "shop")
    item_id = str(order.item_id or "")
    entry = _catalog_entry(
        "kit" if item_type == "kit" else "shop",
        item_id,
    )
    lic = _get_license_grant(entry, item_id)
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
    db: Any | None = None,
) -> None:
    owns_session = db is None
    if owns_session:
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
        if owns_session:
            _release_db_session(db)


def _revoke_player_entitlement_by_group(
    steam_id: str,
    group: str,
    db: Any | None = None,
) -> None:
    owns_session = db is None
    if owns_session:
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
        if owns_session:
            _release_db_session(db)


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
        _release_db_session(sess)


def _load_point_packages() -> list[dict[str, Any]]:
    cfg = _read_shop_config()
    packages = cfg.get("PointPackages")
    if isinstance(packages, list):
        return packages
    s = _load_settings()
    stored = s.get("point_packages")
    if isinstance(stored, list):
        return stored
    return _DEFAULT_POINT_PACKAGES


def _normalize_point_packages(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        pkg_id = str(entry.get("id") or "").strip()
        label = str(entry.get("label") or entry.get("name") or "").strip()
        try:
            points = int(entry.get("points") or 0)
            price_brl = float(entry.get("price_brl") or 0)
        except (TypeError, ValueError):
            continue
        if not pkg_id or not label or points <= 0 or price_brl <= 0:
            continue
        pkg: dict[str, Any] = {"id": pkg_id, "label": label, "points": points, "price_brl": price_brl}
        note = str(entry.get("note") or "").strip()
        if note:
            pkg["note"] = note
        out.append(pkg)
    return out


def _persist_point_packages_to_catalog(
    packages: list[dict[str, Any]],
    settings: dict[str, Any],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Grava PointPackages no catálogo mestre e destinos de sync do CustomShop."""
    master_path = _resolve_settings_catalog_path(
        str(settings.get("config_path") or _DEFAULT_CONFIG_PATH)
    )
    existing = _read_json_file(Path(master_path))
    if not existing:
        existing = _read_shop_config()
    body = dict(existing)
    body["PointPackages"] = packages
    written, errors = _write_config_all_targets(body, settings)
    _invalidate_shop_config_cache()
    if not errors:
        try:
            from src.shop_integration import push_catalog_to_webstore

            master_written = next(
                (w["path"] for w in written if "mestre" in w.get("label", "").lower()),
                master_path,
            )
            push_catalog_to_webstore(master_written)
        except Exception:
            pass
    return written, errors


def _package_label(package_id: str) -> str:
    pid = str(package_id or "").strip()
    if not pid:
        return "Doação PIX"
    for pkg in _load_point_packages():
        if str(pkg.get("id", "")).strip() == pid:
            return str(pkg.get("label") or pkg.get("name") or pid)
    return pid


def _get_mp_access_token() -> str:
    """Token MP: settings.json (admin UI) tem prioridade sobre env (evita env vazio/stale)."""
    settings_token = str(_load_settings().get("mp_access_token", "")).strip()
    env_token = os.environ.get("MP_ACCESS_TOKEN", "").strip()
    if settings_token:
        return settings_token
    return env_token


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


def _shop_public_base_url() -> str:
    """URL pública HTTPS da loja — usada em callbacks Mercado Pago (não localhost)."""
    s = _load_settings()
    configured = str(s.get("public_url") or "").strip().rstrip("/")
    if configured:
        if "://" not in configured:
            configured = f"https://{configured}"
        return configured.rstrip("/")
    return DEFAULT_SHOP_PUBLIC_URL.rstrip("/")


def _build_base_url() -> str:
    """URL base para redirects (Steam login, MP). Preferência: settings > proxy > fallback público."""
    public = _shop_public_base_url()
    proto = (request.headers.get("X-Forwarded-Proto") or request.scheme or "https").split(",")[0].strip()
    host = (
        request.headers.get("X-Forwarded-Host")
        or request.headers.get("Host")
        or request.host
        or ""
    ).split(",")[0].strip()
    if host.startswith("127.0.0.1") or host.startswith("localhost"):
        return public
    if proto and host:
        return f"{proto}://{host}".rstrip("/")
    root = (request.url_root or "").rstrip("/")
    if root and "127.0.0.1" not in root and "localhost" not in root:
        return root
    return public


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


def _get_steam_api_key() -> str:
    """Chave Steam Web API — settings.json (TEK/admin UI) > env STEAM_API_KEY."""
    settings_key = str(_load_settings().get("steam_api_key", "")).strip()
    if settings_key:
        return settings_key
    return (os.environ.get("STEAM_API_KEY") or "").strip()


def _steam_api_key_configured() -> bool:
    return bool(_get_steam_api_key())


_STEAM_PERSONA_BATCH_SIZE = 100
_STEAM_API_KEY_WARNED = False
_STEAM_PERSONA_ADMIN_WARNING = (
    "Nicknames Steam indisponíveis — configure a Chave Steam Web API no TEK "
    "(CustomShop → Web Store) ou em Configurações do admin web "
    "(https://steamcommunity.com/dev/apikey) e reinicie a Web Store. "
    "Verifique GET /api/health → steam_api_configured."
)
_STEAM_PERSONA_FETCH_WARNING = (
    "A Steam Web API não retornou nicknames para esta página — perfis privados, "
    "rede bloqueada ou chave inválida. Veja webstore.log."
)


def _warn_steam_api_key_missing(context: str = "") -> None:
    global _STEAM_API_KEY_WARNED
    if _steam_api_key_configured() or _STEAM_API_KEY_WARNED:
        return
    _STEAM_API_KEY_WARNED = True
    suffix = f" ({context})" if context else ""
    log.warning(
        "STEAM_API_KEY não configurada — nicknames Steam indisponíveis%s. "
        "Configure no TEK (CustomShop → Web Store) ou em https://steamcommunity.com/dev/apikey",
        suffix,
    )


def _admin_steam_persona_meta(
    requested_ids: list[str],
    fetched: dict[str, str],
) -> dict[str, Any]:
    configured = _steam_api_key_configured()
    meta: dict[str, Any] = {"steam_api_configured": configured, "steam_persona_warning": None}
    if not requested_ids:
        return meta
    if not configured:
        meta["steam_persona_warning"] = _STEAM_PERSONA_ADMIN_WARNING
        return meta
    if not fetched:
        meta["steam_persona_warning"] = _STEAM_PERSONA_FETCH_WARNING
        return meta
    missing = [sid for sid in requested_ids if sid not in fetched]
    if missing:
        meta["steam_persona_warning"] = (
            f"Nick Steam parcial: {len(fetched)}/{len(requested_ids)} obtidos via API. "
            "Perfis privados ou indisponíveis exibem …últimos dígitos do SteamID."
        )
    return meta


def _fetch_steam_persona_names_batch(steam_ids: list[str]) -> dict[str, str]:
    """Persona Steam em lote (até 100 por request); requer STEAM_API_KEY."""
    api_key = _get_steam_api_key()
    if not api_key:
        _warn_steam_api_key_missing("GetPlayerSummaries")
        return {}
    valid: list[str] = []
    seen: set[str] = set()
    for raw in steam_ids:
        sid = _normalize_steam_id64(raw)
        if sid and sid not in seen:
            seen.add(sid)
            valid.append(sid)
    if not valid:
        return {}
    result: dict[str, str] = {}
    for i in range(0, len(valid), _STEAM_PERSONA_BATCH_SIZE):
        chunk = valid[i : i + _STEAM_PERSONA_BATCH_SIZE]
        ids_param = ",".join(chunk)
        url = (
            "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
            f"?key={urllib.parse.quote(api_key, safe='')}"
            f"&steamids={ids_param}"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "arkshop-web"}, method="GET")
            with urllib.request.urlopen(req, timeout=12) as response:
                data = json.loads(response.read().decode("utf-8", errors="replace"))
            response_block = data.get("response") or {}
            api_error = response_block.get("error") or data.get("error")
            if api_error:
                log.warning(
                    "Steam GetPlayerSummaries erro API (%s ids): %s",
                    len(chunk),
                    api_error,
                )
                continue
            players = response_block.get("players") or []
            for player in players:
                sid = str(player.get("steamid") or "").strip()
                name = str(player.get("personaname") or "").strip()
                if sid and name:
                    result[sid] = name[:128]
            if chunk and not players:
                log.warning(
                    "Steam GetPlayerSummaries retornou 0 jogadores (%s ids solicitados)",
                    len(chunk),
                )
        except Exception as exc:
            log.warning(
                "Steam GetPlayerSummaries batch falhou (%s ids): %s",
                len(chunk),
                exc,
            )
    return result


def _persist_steam_personas(db: Any, persona_map: dict[str, str]) -> None:
    """Grava nick Steam em store_users.steam_persona (fonte única de exibição)."""
    if not persona_map:
        return
    for sid, persona in persona_map.items():
        norm_sid = _normalize_steam_id64(sid) or sid
        row = db.get(StoreUser, norm_sid)
        if row is None:
            row = db.get(StoreUser, sid)
        if row is None:
            row = StoreUser(steam_id=norm_sid, steam_persona=persona, display_name=persona)
            db.add(row)
        else:
            row.steam_persona = persona
            row.display_name = persona
    db.commit()


def _persist_steam_personas_isolated(persona_map: dict[str, str]) -> None:
    """Persiste personas em sessão própria — evita conflito com SELECT raw do admin."""
    if not persona_map or not _db_ready():
        return
    db = _SessionLocal()
    try:
        _persist_steam_personas(db, persona_map)
    except Exception as exc:
        db.rollback()
        log.warning("persist steam personas falhou: %s", exc)
    finally:
        _release_db_session(db)


def _refresh_steam_personas(
    db: Any,
    steam_ids: list[str],
    *,
    return_status: bool = False,
) -> dict[str, str] | tuple[dict[str, str], dict[str, Any]]:
    """Consulta Steam API e persiste — ignora cache DB (lista admin)."""
    valid_ids: list[str] = []
    seen: set[str] = set()
    for raw in steam_ids:
        sid = _normalize_steam_id64(raw)
        if sid and sid not in seen:
            seen.add(sid)
            valid_ids.append(sid)
    if not valid_ids:
        meta = _admin_steam_persona_meta([], {})
        return ({}, meta) if return_status else {}
    if not _steam_api_key_configured():
        _warn_steam_api_key_missing("refresh_steam_personas")
        meta = _admin_steam_persona_meta(valid_ids, {})
        return ({}, meta) if return_status else {}
    fetched = _fetch_steam_persona_names_batch(valid_ids)
    meta = _admin_steam_persona_meta(valid_ids, fetched)
    if fetched:
        _persist_steam_personas_isolated(fetched)
    return (fetched, meta) if return_status else fetched


def _refresh_steam_persona(db: Any, steam_id: str) -> str | None:
    """Atualiza steam_persona de um jogador via Steam API (login / auth/me)."""
    norm_sid = _normalize_steam_id64(steam_id)
    if not norm_sid:
        return None
    persona_map = _refresh_steam_personas(db, [norm_sid])
    if norm_sid in persona_map:
        return persona_map[norm_sid]
    row = db.get(StoreUser, norm_sid) or db.get(StoreUser, steam_id)
    if row and (row.steam_persona or "").strip():
        p = str(row.steam_persona).strip()
        return p if p != steam_id else None
    return None


def _backfill_steam_personas(
    db: Any,
    entries: list[tuple[str, str | None]],
    *,
    return_status: bool = False,
) -> dict[str, str] | tuple[dict[str, str], dict[str, Any]]:
    """Admin list: sempre busca nick Steam em lote e sobrescreve cache."""
    steam_ids: list[str] = []
    seen: set[str] = set()
    for raw, _ in entries:
        sid = _normalize_steam_id64(raw)
        if sid and sid not in seen:
            seen.add(sid)
            steam_ids.append(sid)
    return _refresh_steam_personas(db, steam_ids, return_status=return_status)


def _fetch_steam_persona_name(steam_id: str) -> str | None:
    """Persona Steam (personaname) via Web API; requer STEAM_API_KEY no ambiente."""
    if not _is_valid_steamid64(steam_id):
        return None
    return _fetch_steam_persona_names_batch([steam_id]).get(steam_id)


def _steam_persona_label(steam_id: str, persona: str | None) -> str | None:
    if persona and str(persona).strip() and str(persona).strip() != steam_id:
        return str(persona).strip()[:128]
    return None


def _resolve_auth_player_name(steam_id: str, *, enrich: bool = True) -> str | None:
    """Nick Steam para header — apenas steam_persona, nunca market_display_name."""
    if _db_ready():
        db = _SessionLocal()
        try:
            if enrich:
                persona = _refresh_steam_persona(db, steam_id)
            else:
                row = db.get(StoreUser, steam_id)
                persona = (row.steam_persona if row else None)
            label = _steam_persona_label(steam_id, persona)
            if label:
                return label
        finally:
            _release_db_session(db)

    if not enrich:
        return None

    persona = _fetch_steam_persona_name(steam_id)
    if not persona:
        return None
    if _db_ready():
        db = _SessionLocal()
        try:
            _persist_steam_personas(db, {steam_id: persona})
        except Exception:
            db.rollback()
        finally:
            _release_db_session(db)
    return persona[:128]


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


def ticket_staff_required(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Admin ou membro da equipe de suporte (fila de tickets)."""
    @functools.wraps(fn)
    def _wrapper(*args: Any, **kwargs: Any):
        steam_id = _steam_id_from_session()
        if not steam_id:
            return jsonify({"ok": False, "error": "Não autenticado", "message": _STEAM_SESSION_REQUIRED_MESSAGE}), 401
        if not _can_manage_tickets(steam_id):
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
    """Campos de /api/auth/me — nick Steam (steam_persona) como única fonte de exibição."""
    persona: str | None = None
    if _db_ready():
        db = _SessionLocal()
        try:
            persona = _steam_persona_label(steam_id, _refresh_steam_persona(db, steam_id))
        finally:
            _release_db_session(db)
    return {
        "steam_persona": persona,
        "display_name": persona,
        "market_display_name": None,
        "needs_display_name": False,
    }


def _guard_player_display_name(steam_id: str) -> Any:
    """Removido: nick Steam vem da API, não há nome editável separado."""
    return None


def _auth_regulamento_fields(steam_id: str, *, db: Any | None = None) -> dict[str, Any]:
    from regulamento_service import auth_regulamento_fields

    own_db = db is None
    if own_db:
        db = _SessionLocal()
    try:
        return auth_regulamento_fields(
            steam_id,
            db_get_store_user=lambda sid: db.get(StoreUser, sid),
        )
    finally:
        if own_db:
            _release_db_session(db)


def _auth_regulamento_fields_offline() -> dict[str, Any]:
    from regulamento_service import REGULAMENTO_VERSION

    return {
        "needs_regulamento_accept": True,
        "regulamento_version_current": REGULAMENTO_VERSION,
        "regulamento_version_accepted": None,
        "regulamento_accepted_at": None,
    }


def _guard_regulamento_accepted(steam_id: str) -> Any:
    """Bloqueia ações sem aceite do regulamento vigente."""
    if not _db_ready():
        return None
    from regulamento_service import guard_regulamento_accepted

    db = _SessionLocal()
    try:
        return guard_regulamento_accepted(
            steam_id,
            db_get_store_user=lambda sid: db.get(StoreUser, sid),
        )
    finally:
        _release_db_session(db)


def _guard_player_commerce(steam_id: str) -> Any:
    """Regulamento aceito + nome de exibição (mercado/resgates/doações)."""
    if (reg_err := _guard_regulamento_accepted(steam_id)) is not None:
        return reg_err
    return _guard_player_display_name(steam_id)


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


def _rcon_hosts_to_try(srv: dict[str, Any], settings: dict[str, Any]) -> list[str]:
    """127.0.0.1 primeiro (TEK local), depois host do servidor e fallback global."""
    hosts: list[str] = []
    for candidate in (
        "127.0.0.1",
        srv.get("rcon_host"),
        settings.get("rcon_host"),
        (srv.get("config_snapshot") or {}).get("server_ip") if isinstance(srv.get("config_snapshot"), dict) else None,
    ):
        h = str(candidate or "").strip()
        if not h or h in ("0.0.0.0",):
            continue
        if h.lower() == "localhost":
            h = "127.0.0.1"
        if h not in hosts:
            hosts.append(h)
    return hosts or ["127.0.0.1"]


def _load_manager_app_config() -> Any:
    """Lê config.json do Server Manager (machine_public_ip, shop.public_ip)."""
    cfg_path = Path(os.environ.get("APPDATA", "")) / "ARKLAND-ServerManager" / "config.json"
    if not cfg_path.is_file():
        return None
    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    shop_raw = raw.get("shop") if isinstance(raw.get("shop"), dict) else {}

    class _Cfg:
        machine_public_ip = str(raw.get("machine_public_ip") or "").strip()

        class _Shop:
            public_ip = str(shop_raw.get("public_ip") or "").strip()

        shop = _Shop()

    return _Cfg()


def _connect_fields_from_asm_raw(
    srv: dict[str, Any],
    settings: dict[str, Any],
) -> dict[str, Any]:
    app_cfg = _load_manager_app_config()
    game_host = _resolve_game_host(
        srv,
        app_config=app_cfg,
        settings=settings,
    )
    game_port = int(srv.get("server_port") or 7777)
    out: dict[str, Any] = {
        "game_host": game_host,
        "game_port": game_port,
    }
    server_public = str(srv.get("public_ip") or "").strip()
    if server_public:
        out["public_ip"] = server_public
    elif game_host and game_host not in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
        out["public_ip"] = game_host
    return out


def _server_dict_from_asm_raw(
    srv: dict[str, Any],
    settings: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if srv.get("shop_exclude"):
        return None
    if srv.get("rcon_enabled") is False:
        return None
    pwd = sanitize_rcon_password(
        str(srv.get("rcon_password") or srv.get("admin_password") or "")
    )
    if not pwd:
        return None
    sid = str(srv.get("shop_server_id") or "").strip() or slugify_server_id(
        str(srv.get("name") or ""), str(srv.get("id") or ""),
    )
    if not sid:
        return None
    install = str(srv.get("install_dir") or "")
    entry = {
        "server_id": sid,
        "label": str(srv.get("name") or sid),
        "rcon_host": str(srv.get("server_ip") or "127.0.0.1"),
        "rcon_port": int(srv.get("rcon_port") or 27020),
        "rcon_password": pwd,
        "plugin_config_path": str(
            srv.get("customshop_config_path") or default_customshop_path(install)
        ),
        "arkland_ref": f"tek:{srv.get('id')}",
    }
    entry.update(_connect_fields_from_asm_raw(srv, settings or {}))
    return entry


def _server_dict_from_classic_raw(
    srv: dict[str, Any],
    settings: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if srv.get("shop_exclude"):
        return None
    if srv.get("rcon_enabled") is False:
        return None
    pwd = sanitize_rcon_password(
        str(srv.get("rcon_password") or srv.get("admin_password") or "")
    )
    if not pwd:
        return None
    sid = str(srv.get("shop_server_id") or "").strip() or slugify_server_id(
        str(srv.get("name") or ""), str(srv.get("id") or ""),
    )
    if not sid:
        return None
    install = str(srv.get("install_dir") or "")
    entry = {
        "server_id": sid,
        "label": str(srv.get("name") or sid),
        "rcon_host": str(srv.get("server_ip") or srv.get("public_ip") or "127.0.0.1"),
        "rcon_port": int(srv.get("rcon_port") or 27020),
        "rcon_password": pwd,
        "plugin_config_path": str(
            srv.get("customshop_config_path") or default_customshop_path(install)
        ),
        "arkland_ref": f"classic:{srv.get('id')}",
    }
    entry.update(_connect_fields_from_asm_raw(srv, settings or {}))
    return entry


def _discover_local_rcon_servers() -> list[dict[str, Any]]:
    """Lê asm_servers.json e servers.json do Server Manager (host local)."""
    cfg_dir = Path(os.environ.get("APPDATA", "")) / "ARKLAND-ServerManager"
    if not cfg_dir.is_dir():
        return []

    settings = _load_settings()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    asm_path = cfg_dir / "asm_servers.json"
    if asm_path.exists():
        try:
            raw = json.loads(asm_path.read_text(encoding="utf-8"))
            items = raw if isinstance(raw, list) else []
            for item in items:
                if not isinstance(item, dict):
                    continue
                entry = _server_dict_from_asm_raw(item, settings)
                if entry and entry["server_id"] not in seen:
                    seen.add(entry["server_id"])
                    out.append(entry)
        except Exception:
            pass

    classic_path = cfg_dir / "servers.json"
    if classic_path.exists():
        try:
            raw = json.loads(classic_path.read_text(encoding="utf-8"))
            items = raw if isinstance(raw, list) else []
            for item in items:
                if not isinstance(item, dict):
                    continue
                entry = _server_dict_from_classic_raw(item, settings)
                if entry and entry["server_id"] not in seen:
                    seen.add(entry["server_id"])
                    out.append(entry)
        except Exception:
            pass

    return out


def _merge_rcon_server_entry(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if value in (None, ""):
            continue
        if key == "rcon_password" and merged.get("rcon_password"):
            continue
        if not merged.get(key):
            merged[key] = value
    return merged


def _resolve_rcon_reload_targets(settings: dict[str, Any]) -> list[dict[str, Any]]:
    """Servidores para Shop.Reload — servers.json da web + descoberta local ASM."""
    by_id: dict[str, dict[str, Any]] = {}
    for srv in _load_servers():
        if not isinstance(srv, dict):
            continue
        sid = str(srv.get("server_id") or "").strip()
        if sid:
            by_id[sid] = srv

    for discovered in _discover_local_rcon_servers():
        sid = str(discovered.get("server_id") or "").strip()
        if not sid:
            continue
        if sid in by_id:
            by_id[sid] = _merge_rcon_server_entry(by_id[sid], discovered)
        else:
            by_id[sid] = discovered

    targets = list(by_id.values())
    if targets:
        return targets

    # Fallback: destinos de config no disco (usa senha RCON global das settings)
    for target in _plugin_sync_targets(settings):
        if target.get("kind") != "server":
            continue
        sid = slugify_server_id(str(target.get("label") or ""), str(target.get("path") or ""))
        if sid and sid not in by_id:
            by_id[sid] = {
                "server_id": sid,
                "label": str(target.get("label") or sid),
                "plugin_config_path": str(target.get("path") or ""),
            }
    return list(by_id.values())


def _rcon_reload_one_server(srv: dict[str, Any], settings: dict[str, Any]) -> dict[str, Any]:
    sid = str(srv.get("server_id") or "server")
    label = str(srv.get("label") or sid)
    port = int(srv.get("rcon_port") or settings.get("rcon_port") or 27020)
    password = sanitize_rcon_password(
        str(srv.get("rcon_password") or settings.get("rcon_password") or "")
    )
    if not password:
        return {
            "server_id": sid,
            "label": label,
            "ok": False,
            "error": "senha RCON não configurada (cadastre em Servidores ou ASM)",
        }

    last_err = ""
    for host in _rcon_hosts_to_try(srv, settings):
        for cmd in CUSTOMSHOP_RELOAD_COMMANDS:
            try:
                resp = _rcon_command(host, port, password, cmd, connect_retries=5)
                return {
                    "server_id": sid,
                    "label": label,
                    "ok": True,
                    "host": host,
                    "command": cmd,
                    "response": (resp or "")[:200],
                }
            except Exception as exc:
                last_err = f"{host}:{port} {cmd}: {exc}"

    return {"server_id": sid, "label": label, "ok": False, "error": last_err or "falha RCON"}


def _trigger_tribe_sync_rcon_all() -> list[dict[str, Any]]:
    """Dispara Shop.TribeSync via RCON em todos os mapas (presença Minha Tribo)."""
    settings = _load_settings()
    targets = _resolve_rcon_reload_targets(settings)
    results: list[dict[str, Any]] = []
    for srv in targets:
        sid = str(srv.get("server_id") or "server")
        label = str(srv.get("label") or sid)
        port = int(srv.get("rcon_port") or settings.get("rcon_port") or 27020)
        password = sanitize_rcon_password(
            str(srv.get("rcon_password") or settings.get("rcon_password") or "")
        )
        if not password:
            results.append({
                "server_id": sid,
                "label": label,
                "ok": False,
                "error": "senha RCON não configurada",
            })
            continue
        last_err = ""
        sent = False
        for host in _rcon_hosts_to_try(srv, settings):
            try:
                resp = _rcon_command(
                    host, port, password, "Shop.TribeSync", connect_retries=2,
                )
                results.append({
                    "server_id": sid,
                    "label": label,
                    "ok": True,
                    "host": host,
                    "response": (resp or "")[:200],
                })
                sent = True
                break
            except Exception as exc:
                last_err = f"{host}:{port}: {exc}"
        if not sent:
            results.append({
                "server_id": sid,
                "label": label,
                "ok": False,
                "error": last_err or "falha RCON",
            })
    return results


def _reload_all_plugins(settings: dict[str, Any]) -> list[dict[str, Any]]:
    """Shop.Reload via RCON em todos os mapas (multi-host, alinhado ao Sync TEK)."""
    targets = _resolve_rcon_reload_targets(settings)
    if not targets:
        host, port, password, label = _resolve_rcon_target(None, settings)
        stub = {"server_id": "default", "label": label, "rcon_host": host, "rcon_port": port, "rcon_password": password}
        return [_rcon_reload_one_server(stub, settings)]

    results: list[dict[str, Any]] = []
    max_workers = min(8, max(1, len(targets)))
    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="shop-reload") as pool:
        futures = {
            pool.submit(_rcon_reload_one_server, srv, settings): srv
            for srv in targets
        }
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as exc:
                srv = futures[fut]
                results.append({
                    "server_id": str(srv.get("server_id") or "?"),
                    "label": str(srv.get("label") or "?"),
                    "ok": False,
                    "error": str(exc),
                })

    results.sort(key=lambda r: str(r.get("label") or r.get("server_id") or ""))
    return results


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
                  points_spent: int = 0,
                  *,
                  admin_skip_kit_limit: bool = False) -> tuple[Order | None, str | None]:
    if not _db_ready():
        return None, "Banco não configurado. Defina ARKSHOP_DATABASE_URL ou configure DB em Settings"

    if not _is_valid_steamid64(steam_id):
        return None, "SteamID64 inválido"
    if not item_id:
        return None, "item_id é obrigatório"
    if amount <= 0:
        return None, "amount deve ser maior que zero"

    s = _load_settings()
    if admin_skip_kit_limit and not original_order_id:
        original_order_id = "__admin_skip_kit_limit__"
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
        _release_db_session(db)


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
        _release_db_session(db)


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
                _release_db_session(mdb)
        except Exception as exc:
            _log_error("market_claims_expire_worker", error=str(exc))

        try:
            odb = _SessionLocal()
            try:
                result = expire_stale_pending_orders(odb)
                if result.get("processed"):
                    _log("shop_orders_auto_cancelled", **{
                        k: v for k, v in result.items() if k != "cancelled"
                    })
            finally:
                _release_db_session(odb)
        except Exception as exc:
            _log_error("shop_orders_auto_cancel_worker", error=str(exc))

        try:
            from lottery_service import process_due_draws

            ldb = _SessionLocal()
            try:
                n = process_due_draws(ldb)
                if n:
                    _log("lottery_draws_processed", count=n)
            finally:
                _release_db_session(ldb)
        except Exception as exc:
            _log_error("lottery_draw_worker", error=str(exc))

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
            _release_db_session(db)

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

def _pending_items_json(items: list[dict[str, Any]]) -> Any:
    """Resposta JSON padronizada para fila de entregas (nunca corpo vazio)."""
    return jsonify({"ok": True, "items": items, "orders": items})


@app.after_request
def _api_pending_never_empty_body(response: Any) -> Any:
    """Garante JSON válido nas rotas /api/pending/* (evita parse error no plugin)."""
    path = request.path or ""
    if not path.startswith("/api/pending/"):
        return response
    if response.status_code >= 400:
        return response
    body = (response.get_data(as_text=True) or "").strip()
    if body:
        return response
    return jsonify({"ok": True, "items": [], "orders": []})


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
            Order.status.in_(("PENDENTE", "ENTREGANDO")),
            Order.item_type != "custom_dino",
        ).all()
        items = [{
            "order_id": o.order_id,
            "item_id": _resolve_catalog_item_id(o.item_type or "shop", o.item_id),
            "catalog_item_id": o.item_id,
            "amount": o.amount,
            "item_type": o.item_type,
            "skip_kit_limit": str(o.original_order_id or "").startswith("__admin_skip_kit_limit__"),
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
        return _pending_items_json(items)
    except Exception as exc:
        _log_error("get_pending_deliveries", steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        _release_db_session(db)


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
            Order.item_type != "custom_dino",
        )
        if targets:
            q = q.filter(Order.order_id.in_(targets))
        pending = q.order_by(Order.created_at.asc()).all()

        now = _now()
        for order in pending:
            if _finalize_license_order_if_fulfilled(
                db, order, reason="claim_skip_already_licensed"
            ):
                continue
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
                "skip_kit_limit": str(order.original_order_id or "").startswith("__admin_skip_kit_limit__"),
            })
        db.commit()
        return _pending_items_json(claimed)
    except Exception as exc:
        db.rollback()
        _log_error("claim_pending_orders", steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        _release_db_session(db)


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
    fulfilled: list[str] = []
    try:
        now = _now()
        for raw_id in raw_ids:
            order_id = str(raw_id).strip()
            if not order_id:
                continue
            order = db.query(Order).filter(
                Order.steam_id == steam_id,
                Order.order_id == order_id,
                Order.status == "ENTREGANDO",
            ).first()
            if not order:
                continue
            if _finalize_license_order_if_fulfilled(
                db, order, reason="release_skip_already_licensed"
            ):
                fulfilled.append(order_id)
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
        return jsonify({"ok": True, "released": released, "fulfilled": fulfilled})
    except Exception as exc:
        db.rollback()
        _log_error("release_pending_orders", steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        _release_db_session(db)


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
        _release_db_session(db)


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
        _release_db_session(db)


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

    session.permanent = True
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
                    _release_db_session(db)
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
        "steam_api_configured": _steam_api_key_configured(),
        "version": _get_project_release().get("version", ""),
    })


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    steam_id = _steam_id_from_session()
    if not steam_id:
        return jsonify({
            "authenticated": False,
            "is_admin": False,
            "is_support": False,
            "can_manage_tickets": False,
            "steam_id": None,
            "steam_persona": None,
            "display_name": None,
            "needs_display_name": False,
            "market_display_name": None,
            "needs_regulamento_accept": False,
            "regulamento_version_current": None,
            "regulamento_version_accepted": None,
        })
    file_admins = _load_admin_steamids_from_file()
    is_admin = steam_id in file_admins
    if not is_admin and _db_ready():
        is_admin = steam_id in _load_admin_steamids(db_timeout=1.5)
    is_support = False if is_admin else steam_id in _load_support_steamids(db_timeout=1.5)
    can_manage_tickets = is_admin or is_support
    payload: dict[str, Any] = {
        "authenticated": True,
        "is_admin": is_admin,
        "is_support": is_support,
        "can_manage_tickets": can_manage_tickets,
        "steam_id": steam_id,
    }
    payload.update(_auth_display_name_fields(steam_id, is_admin))
    if _db_ready():
        db = _SessionLocal()
        try:
            payload.update(_auth_regulamento_fields(steam_id, db=db))
        finally:
            _release_db_session(db)
    else:
        payload.update(_auth_regulamento_fields_offline())
    if not is_admin:
        payload.update(_store_user_blocked_fields(steam_id))
    return jsonify(payload)


# ── Settings routes ───────────────────────────────────────────────────────────

@app.route("/api/settings", methods=["GET"])
@admin_required
def get_settings():
    s = _load_settings()
    safe = {k: v for k, v in s.items() if k not in ("rcon_password", "db_password", "mp_access_token", "steam_api_key", "cross_chat_discord_token", "ticket_discord_token")}
    safe["rcon_password_set"] = bool(s.get("rcon_password"))
    safe["db_password_set"] = bool(s.get("db_password"))
    safe["mp_access_token_set"] = bool(_get_mp_access_token())
    safe["steam_api_key_set"] = bool(_get_steam_api_key())
    safe["cross_chat_discord_token_set"] = bool(s.get("cross_chat_discord_token"))
    safe["ticket_discord_token_set"] = bool(s.get("ticket_discord_token"))
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
        "public_ip",
        "join_host",
        "lottery_enabled",
        "custom_dino_enabled",
        "custom_dino_require_ticket",
        "custom_dino_ground_fallback",
        "custom_dino_spawn_exact",
        "custom_dino_level_max",
        "dino_lab_block_debug",
        "dino_order_enabled",
        "dino_order_alpha",
        "dino_order_beta",
        "dino_order_delta_uniform",
        "dino_order_delta_base",
        "dino_order_delta_region",
        "dino_order_kappa",
        "dino_order_absolute_max",
        "dino_order_auto_approve_max",
    ):
        if key in body:
            s[key] = body[key]
    if "custom_dino_level_max" in body:
        try:
            s["custom_dino_level_max"] = max(0, int(body["custom_dino_level_max"]))
        except (TypeError, ValueError):
            s["custom_dino_level_max"] = 0
    if "rcon_password" in body and body["rcon_password"] != "":
        s["rcon_password"] = body["rcon_password"]
    if "db_password" in body and body["db_password"] != "":
        s["db_password"] = body["db_password"]
    if "mp_access_token" in body and body["mp_access_token"] != "":
        s["mp_access_token"] = body["mp_access_token"]
    if "steam_api_key" in body and body["steam_api_key"] != "":
        s["steam_api_key"] = body["steam_api_key"]
    point_packages_sync_errors: list[dict[str, str]] = []
    if "point_packages" in body:
        s["point_packages"] = _normalize_point_packages(body["point_packages"])
    _save_settings(s)

    if "point_packages" in body:
        _written, point_packages_sync_errors = _persist_point_packages_to_catalog(
            s["point_packages"],
            s,
        )
        if point_packages_sync_errors:
            _log_error(
                "point_packages_sync",
                admin=_steam_id_from_session(),
                errors=point_packages_sync_errors,
            )

    reconnect_error = None
    try:
        _configure_database(_resolve_database_url(s))
    except Exception as exc:
        reconnect_error = str(exc)

    _log("settings_saved", admin=_steam_id_from_session(), db_ok=_db_ready())
    ok = reconnect_error is None and not point_packages_sync_errors
    error = reconnect_error
    if not error and point_packages_sync_errors:
        error = point_packages_sync_errors[0].get("error") or "Falha ao gravar PointPackages no catálogo"
    return jsonify({
        "ok": ok,
        "db_configured": _db_ready(),
        "db_from_env": bool(_DATABASE_URL),
        "error": error,
        "point_packages_sync_errors": point_packages_sync_errors or None,
    }), 200 if ok else 500


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
        "join_host",
        "game_host",
        "game_port",
        "public_ip",
        "server_map",
        "query_port",
        "machine_label",
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
                "join_host",
                "game_host",
                "game_port",
                "public_ip",
                "server_map",
                "query_port",
                "machine_label",
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


@app.route("/api/servers/connect-status", methods=["GET"])
@admin_required
def servers_connect_status():
    """Diagnóstico admin: por que cada servidor pode ou não exibir botões Jogar/Copiar IP."""
    settings = _load_settings()
    items = [diagnose_server_connect(srv, settings) for srv in _load_servers()]
    visible = sum(1 for i in items if i.get("show_on_home"))
    connectable = sum(1 for i in items if i.get("can_connect"))
    return jsonify({
        "ok": True,
        "summary": {
            "total": len(items),
            "visible_on_home": visible,
            "connectable": connectable,
            "settings_join_host": str(settings.get("join_host") or ""),
            "settings_public_ip": str(settings.get("public_ip") or ""),
        },
        "items": items,
    })


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
                "delivery_command_template", "config_snapshot",
                "join_host", "game_host", "game_port", "public_ip",
                "server_map", "query_port",
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
    try:
        from src.catalog_sync import normalize_timed_points_reward_groups

        normalize_timed_points_reward_groups(file_body)
    except Exception:
        pass

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
    body = request.get_json(force=True) or {}
    do_reload = body.pop("reload", True)
    if not isinstance(do_reload, bool):
        do_reload = True
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
    catalog_feed_result = None
    try:
        from catalog_feed_service import maybe_feed_on_catalog_save

        catalog_feed_result = maybe_feed_on_catalog_save(body)
    except Exception as exc:
        log.debug("catalog_feed on save skipped: %s", exc)
    master_path = next((w["path"] for w in written if "mestre" in w.get("label", "").lower()), "")
    if master_path:
        try:
            from src.shop_integration import push_catalog_to_webstore

            push_catalog_to_webstore(master_path)
        except Exception:
            pass

    reload_results: list[dict[str, Any]] = []
    if do_reload:
        try:
            reload_results = _reload_all_plugins(s)
            ok_n = sum(1 for r in reload_results if r.get("ok"))
            _log(
                "config_reload_rcon",
                admin=_steam_id_from_session(),
                ok=ok_n,
                total=len(reload_results),
            )
        except Exception as exc:
            reload_results = [{"ok": False, "error": str(exc), "label": "reload"}]

    reload_ok = sum(1 for r in reload_results if r.get("ok"))
    return jsonify({
        "ok": True,
        "written": written,
        "errors": write_errors,
        "sync_count": len(written),
        "reload_results": reload_results,
        "reload_count": reload_ok,
        "reload_total": len(reload_results),
        "catalog_feed": catalog_feed_result,
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
        _release_db_session(session)
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
    servers = []
    for srv in _load_servers():
        if not srv.get("server_id") or srv.get("show_on_home", True) is False:
            continue
        entry = {
            "server_id": srv.get("server_id", ""),
            "label": srv.get("label") or srv.get("server_id", ""),
            "machine_label": str(srv.get("machine_label") or "").strip(),
        }
        entry.update(public_server_connect_view(srv, s))
        servers.append(entry)
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
                "estimate_usd": estimate_foreign(float(p.get("price_brl", 0) or 0))["USD"],
                "estimate_eur": estimate_foreign(float(p.get("price_brl", 0) or 0))["EUR"],
            }
            for p in packages[:6]
        ],
        "exchange_rates": get_exchange_rates(),
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
        "home_notice": _public_home_notice(),
    })


def _public_home_notice() -> dict[str, Any]:
    """Aviso do mural da home (degrada sem DB)."""
    empty = {
        "title": "",
        "body": "",
        "updated_at": None,
        "updated_by_steam_id": None,
        "has_content": False,
    }
    if not _db_ready():
        return empty
    db = _SessionLocal()
    try:
        from home_notice_service import get_home_notice

        return get_home_notice(db)
    except Exception as exc:
        _log_error("public_home_notice", error=str(exc))
        return empty
    finally:
        _release_db_session(db)


@app.route("/api/public/amber-stats", methods=["GET"])
@limiter.limit("120 per minute; 2000 per hour", override_defaults=True)
def public_amber_stats():
    """Totais públicos do Âmbarômetro (sem PII)."""
    from amber_ledger import degraded_public_stats, get_public_stats

    _kick_background_db_init()
    _initialize_database_if_needed()
    if not _db_ready():
        payload = degraded_public_stats(
            message="Banco ainda inicializando",
            currency=_public_currency(),
        )
        resp = make_response(jsonify(payload))
        resp.headers["Cache-Control"] = "no-cache"
        return resp
    db = _SessionLocal()
    try:
        payload = get_public_stats(db, currency=_public_currency)
    except Exception as exc:
        _log_error("public_amber_stats", error=str(exc))
        try:
            db.rollback()
            from amber_ledger import _ensure_schema_ready

            _ensure_schema_ready(db)
            payload = get_public_stats(db, currency=_public_currency, force_refresh=True)
        except Exception as retry_exc:
            _log_error("public_amber_stats_retry", error=str(retry_exc))
            payload = degraded_public_stats(
                message="Erro ao carregar estatísticas",
                currency=_public_currency(),
            )
    finally:
        _release_db_session(db)
    resp = make_response(jsonify(payload))
    resp.headers["Cache-Control"] = "no-cache" if payload.get("degraded") else "public, max-age=60"
    return resp


@app.route("/api/public/exchange-rates", methods=["GET"])
@limiter.limit("120 per minute; 2000 per hour", override_defaults=True)
def public_exchange_rates():
    """Cotações BRL → USD/EUR para estimativas na UI (cache 1h no servidor)."""
    payload = get_exchange_rates()
    resp = make_response(jsonify({"ok": True, **payload}))
    resp.headers["Cache-Control"] = "public, max-age=300"
    return resp


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
    fx = get_exchange_rates()
    enriched_packages = []
    for p in packages:
        entry = dict(p)
        est = estimate_foreign(float(p.get("price_brl", 0) or 0), fx["rates"])
        entry["estimate_usd"] = est["USD"]
        entry["estimate_eur"] = est["EUR"]
        enriched_packages.append(entry)
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
        from src.catalog_sync import catalog_has_placeholder_kit_prices

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
        "point_packages": enriched_packages,
        "currency": _public_currency(),
        "pix_enabled": _pix_enabled(),
        "card_enabled": _payments_enabled(),
        "mp_sandbox": _mp_sandbox(),
        "public_url": public_url,
        "shop_url": public_url,
        "exchange_rates": fx,
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

# Mapas oficiais vanilla — demais nomes são tratados como MOD na home.
_OFFICIAL_ARK_MAP_SLUGS = frozenset({
    "the_island", "the_center", "scorched_earth", "ragnarok", "aberration",
    "extinction", "valguero", "genesis", "genesis_1", "genesis_2", "genesis2",
    "crystal_isles", "lost_island", "fjordur", "aquatica",
})


def _guess_mod_map(server_map: str, display_name: str = "") -> bool:
    from src.server_config_snapshot import norm_slug

    for raw in (server_map, display_name):
        slug = norm_slug(str(raw or ""))
        if slug and slug in _OFFICIAL_ARK_MAP_SLUGS:
            return False
    return True


def _featured_map_overrides_index(
    manual_maps: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Índice de overrides opcionais (texto/badge) por server_id ou slug do nome."""
    from src.server_config_snapshot import norm_slug

    by_id: dict[str, dict[str, Any]] = {}
    by_slug: dict[str, dict[str, Any]] = {}
    for m in manual_maps:
        if m.get("enabled", True) is False:
            continue
        sid = str(m.get("server_id") or "").strip()
        if sid:
            by_id[sid] = m
        for key in (m.get("name"), m.get("id")):
            slug = norm_slug(str(key or ""))
            if slug:
                by_slug[slug] = m
    return by_id, by_slug


def _lookup_featured_override(
    srv: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    by_slug: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    from src.server_config_snapshot import norm_slug

    sid = str(srv.get("server_id") or "").strip()
    if sid and sid in by_id:
        return by_id[sid]
    label = str(srv.get("label") or "").strip()
    server_map = str(srv.get("server_map") or "").strip()
    for raw in (label, server_map, sid):
        slug = norm_slug(raw)
        if slug and slug in by_slug:
            return by_slug[slug]
    return None


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
            "server_id": str(item.get("server_id") or "").strip(),
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
    from src.server_config_snapshot import (
        build_snapshot_indexes,
        match_snapshot_for_map,
        snapshot_public_view,
    )

    servers = _load_servers()
    home_servers = [
        s for s in servers
        if isinstance(s, dict)
        and str(s.get("server_id") or "").strip()
        and s.get("show_on_home", True) is not False
    ]
    manual_maps = _load_featured_maps_raw()
    by_id_ov, by_slug_ov = _featured_map_overrides_index(manual_maps)

    if home_servers:
        out: list[dict[str, Any]] = []
        for srv in sorted(
            home_servers,
            key=lambda s: str(s.get("label") or s.get("server_id") or "").lower(),
        ):
            sid = str(srv.get("server_id") or "").strip()
            label = str(srv.get("label") or sid).strip()
            server_map = str(srv.get("server_map") or "").strip()
            display_name = label or server_map or sid
            ov = _lookup_featured_override(srv, by_id_ov, by_slug_ov)

            snap = srv.get("config_snapshot")
            stats = snapshot_public_view(snap) if isinstance(snap, dict) else None
            if not stats:
                pseudo = {"server_id": sid, "name": display_name, "id": sid}
                stats = match_snapshot_for_map(
                    pseudo, *build_snapshot_indexes(servers),
                )

            if ov and ov.get("name"):
                display_name = str(ov["name"]).strip()

            entry: dict[str, Any] = {
                "name": display_name,
                "mod_map": (
                    bool(ov.get("mod_map"))
                    if ov and "mod_map" in ov
                    else _guess_mod_map(server_map, display_name)
                ),
                "description": str(ov.get("description") or "").strip() if ov else "",
            }
            if stats:
                entry["stats"] = stats
            out.append(entry)
        return out

    by_id, by_slug = build_snapshot_indexes(servers)
    out = []
    for m in manual_maps:
        if m.get("enabled", True) is False:
            continue
        entry = {
            "name": m.get("name", ""),
            "mod_map": bool(m.get("mod_map", False)),
            "description": m.get("description", ""),
        }
        stats = match_snapshot_for_map(m, by_id, by_slug)
        if stats:
            entry["stats"] = stats
        out.append(entry)
    return out


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
        "server_id": str(body.get("server_id") or "").strip(),
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
                "server_id": str(body.get("server_id", m.get("server_id", "")) or "").strip(),
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
    if "limite" in low or "sem_usos" in low or "kit_limit" in low:
        return err or "Você já usou todos os resgates disponíveis deste kit."
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
    if (dn_err := _guard_player_commerce(str(steam_id))) is not None:
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

    lic = _get_license_grant(entry, item_id)
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

    if item_type == "kit" and kit_has_limit(entry):
        resolved_kit = _resolve_catalog_item_id("kit", item_id)
        db_limit = _SessionLocal()
        try:
            remaining = _effective_kit_remaining(db_limit, str(steam_id), resolved_kit, entry)
        finally:
            _release_db_session(db_limit)
        if remaining <= 0:
            if idempotency_key:
                _used_idempotency_keys.pop(idempotency_key, None)
            return jsonify({
                "ok": False,
                "error": (
                    f"Você já usou todos os resgates disponíveis do kit «{resolved_kit}». "
                    "Contate um admin se precisar de ajuda."
                ),
                "kit_limit_reached": True,
            }), 403

    price = _catalog_price(entry, amount)
    if lic or str(entry.get("Type", "")).strip().lower() == "license":
        price = _effective_license_price(str(steam_id), entry, item_id, amount)
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
                cancel_db = _SessionLocal()
                try:
                    orphan = (
                        cancel_db.query(Order)
                        .filter(Order.order_id == order.order_id)
                        .first()
                    )
                    if orphan and orphan.status == "PENDENTE":
                        orphan.status = "CANCELADO"
                        orphan.updated_at = _now()
                        cancel_db.commit()
                finally:
                    _release_db_session(cancel_db)
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
        if price > 0:
            try:
                from amber_ledger import record_shop_debit

                record_shop_debit(
                    db,
                    order_id=order.order_id,
                    steam_id=str(steam_id),
                    points=price,
                    commit=True,
                )
            except Exception as amber_exc:
                log.warning("Âmbarômetro shop debit hook: %s", amber_exc)
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
        _release_db_session(db)

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

    if lic and lic.get("Redeemable", True):
        try:
            _sync_license_permissions_all_servers(
                str(steam_id),
                str(lic["Group"]),
                grant=True,
                days=int(lic.get("Days", 30)),
            )
        except Exception as exc:
            _log_error(
                "purchase_license_perm_sync",
                steam_id=str(steam_id),
                item_id=item_id,
                order_id=order.order_id,
                group=str(lic.get("Group") or ""),
                error=str(exc),
            )

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
    if (dn_err := _guard_player_commerce(steam_id)) is not None:
        return dn_err
    db = _SessionLocal()
    refund = 0
    paid_amount = 0
    new_balance = None
    item_type = "shop"
    item_id = ""
    try:
        order = (
            db.query(Order)
            .filter(Order.order_id == order_id, Order.steam_id == steam_id)
            .with_for_update()
            .first()
        )
        if not order:
            return jsonify({"ok": False, "error": "Pedido não encontrado"}), 404

        policy = _order_cancel_policy(order)
        if not policy["can_cancel"]:
            code = policy.get("cancel_blocked_code") or "cancel_blocked"
            status = 409 if code == "not_pending" else 403
            return jsonify({
                "ok": False,
                "error": policy.get("cancel_blocked_reason") or "Não é possível desistir deste pedido",
                "code": code,
                "cancel_available_at": policy.get("cancel_available_at"),
                "is_license": bool(policy.get("is_license")),
            }), status

        item_type = str(order.item_type or "shop")
        item_id = str(order.item_id or "")
        order_amount = int(order.amount or 1)

        refund = max(0, _order_desist_refund_amount(order, db))
        paid_amount = max(0, _order_refund_amount(order, db))
        new_balance = _credit_order_refund_tx(db, steam_id, refund)

        order.status = "CANCELADO"
        order.updated_at = _now()
        _revoke_entitlement_for_order(steam_id, order_id, db=db)
        db.commit()
        if refund > 0:
            try:
                from amber_ledger import record_shop_refund

                record_shop_refund(
                    db,
                    order_id=order_id,
                    steam_id=steam_id,
                    refund=refund,
                    event_type="order_cancelled",
                    commit=True,
                )
            except Exception as amber_exc:
                log.warning("Âmbarômetro order_cancel hook: %s", amber_exc)
    except Exception as exc:
        db.rollback()
        _log_error("player_cancel_order", order_id=order_id, steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        _release_db_session(db)

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
        message=(
            f"Desistência — reembolso de {refund} Âmbar "
            f"(90% de {paid_amount}; retenção 10%)"
            if refund > 0
            else "Desistência — cancelado sem reembolso"
        ),
        price=refund,
        points_after=new_balance,
        paid_amount=paid_amount,
        refund_factor=_ORDER_DESIST_REFUND_FACTOR,
    )
    return jsonify({
        "ok": True,
        "order_id": order_id,
        "status": "CANCELADO",
        "refunded": refund,
        "paid_amount": paid_amount,
        "refund_factor": _ORDER_DESIST_REFUND_FACTOR,
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
    try:
        if getattr(row, 'pix_copy_paste', None) or getattr(row, 'pix_qr_base64', None):
            return "pix"
    except Exception:
        pass
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
            try:
                from amber_ledger import record_donation

                record_donation(
                    db,
                    payment_id=payment.payment_id,
                    steam_id=payment.steam_id,
                    points=int(payment.points),
                )
            except Exception as amber_exc:
                log.warning("Âmbarômetro donation hook: %s", amber_exc)
            try:
                from lottery_service import on_donation_credited

                on_donation_credited(
                    db,
                    payment_id=payment.payment_id,
                    steam_id=payment.steam_id,
                    amount_brl=float(payment.amount_brl or 0),
                )
            except Exception as lottery_exc:
                log.warning("Sorteio donation hook: %s", lottery_exc)
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
    if mapped == "ESTORNADO":
        try:
            from lottery_service import revoke_lottery_numbers_for_payment

            revoke_lottery_numbers_for_payment(db, payment_id=payment_id)
        except Exception as lottery_revoke_exc:
            log.warning("Sorteio revoke hook: %s", lottery_revoke_exc)


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
            policy = _order_cancel_policy(row)
            pending.append({
                "order_id": row.order_id,
                "item_type": row.item_type,
                "item_id": row.item_id,
                "amount": row.amount,
                "status": row.status,
                "points_spent": int(row.points_spent or 0),
                "can_cancel": bool(policy["can_cancel"]),
                "is_license": bool(policy["is_license"]),
                "cancel_blocked_code": policy.get("cancel_blocked_code"),
                "cancel_blocked_reason": policy.get("cancel_blocked_reason"),
                "cancel_available_at": policy.get("cancel_available_at"),
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

        return jsonify({
            "ok": True,
            "pending": pending,
            "redeemable": redeemable,
            "cancel_policy": {
                "cooldown_hours": _ORDER_CANCEL_COOLDOWN_HOURS,
                "auto_cancel_hours": _ORDER_AUTO_EXPIRE_HOURS,
                "desist_refund_factor": _ORDER_DESIST_REFUND_FACTOR,
                "licenses_irrevocable": True,
                "full_refund_requires_contest_ticket": True,
            },
        })
    except Exception as exc:
        _log_error("player_available", steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        _release_db_session(db)


@app.route("/api/player/pix/payer-form", methods=["GET"])
@login_required
def player_pix_payer_form():
    """Campos exigidos ao jogador antes de gerar PIX (Mercado Pago / Brasil)."""
    return jsonify({"ok": True, "fields": PIX_PAYER_FORM})


@app.route("/api/player/card/payer-form", methods=["GET"])
@login_required
def player_card_payer_form():
    """Campos para checkout com cartão (internacional — documento opcional)."""
    return jsonify({"ok": True, "fields": CARD_PAYER_FORM})


@app.route("/api/player/pix/checkout", methods=["POST"])
@login_required
@limiter.limit("5 per minute; 20 per hour")
def player_pix_checkout():
    if (err := _require_db()) is not None:
        return err
    steam_id = str(_steam_id_from_session())
    if (dn_err := _guard_player_commerce(steam_id)) is not None:
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
        payer = normalize_pix_payer_input(body.get("payer"))
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

    payment_status = map_mp_status(str(mp_resp.get("status", "pending")))
    db = _SessionLocal()
    try:
        row = PointPayment(
            payment_id=payment_id,
            mp_payment_id=mp_id,
            steam_id=steam_id,
            package_id=package_id,
            amount_brl=price_brl,
            points=points,
            status=payment_status,
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
            status_after=payment_status,
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
            "status": payment_status,
            "points": points,
            "amount_brl": price_brl,
            "label": label,
            "pix_qr_base64": str(qr_b64) if qr_b64 is not None else None,
            "pix_copy_paste": str(copy_paste) if copy_paste is not None else None,
        })
    except Exception as exc:
        db.rollback()
        _log_error("pix_checkout_db", payment_id=payment_id, error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500
    finally:
        _release_db_session(db)


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
    if (dn_err := _guard_player_commerce(steam_id)) is not None:
        return dn_err
    if not _payments_enabled():
        return jsonify({"ok": False, "error": "Doação por cartão não configurada (indisponível)"}), 503

    body = request.get_json(force=True, silent=True) or {}
    package_id = str(body.get("package_id", "")).strip()
    package, pkg_err = _resolve_point_package(package_id)
    if pkg_err:
        return jsonify({"ok": False, "error": pkg_err}), 400

    try:
        payer = normalize_card_payer_input(body.get("payer"))
    except PayerValidationError as exc:
        return jsonify({"ok": False, "error": str(exc), "field": exc.field}), 400

    points = int(package.get("points", 0) or 0)
    price_brl = float(package.get("price_brl", 0) or 0)
    payment_id = str(uuid.uuid4())
    label = str(package.get("label") or f"{points:,}".replace(",", ".") + f" {_AMBER_SINGULAR if points == 1 else _AMBER_PLURAL}")
    description = f"Doação ARKLAND — {label} ({steam_id})"
    base = _shop_public_base_url()
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
        _release_db_session(db)


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

        resp_status = payment.status
        resp_credited = payment.credited
        resp_points = payment.points
        new_balance = _get_player_points(steam_id) if resp_credited else None
        return jsonify({
            "ok": True,
            "payment_id": payment.payment_id,
            "status": resp_status,
            "credited": resp_credited,
            "points": resp_points,
            "new_balance": new_balance,
            "mp_status": mp_status_raw,
            "poll_error": poll_error,
        })
    finally:
        _release_db_session(db)


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
        _release_db_session(db)


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
        _release_db_session(db)


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
        _release_db_session(db)


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
        _release_db_session(db)


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
        _release_db_session(db)


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
        _release_db_session(db)


@app.route("/api/player/orders/<order_id>/contest", methods=["POST"])
@login_required
def player_contest(order_id: str):
    """Contesta pedido: motivo obrigatório + abre ticket vinculado (caminho para reembolso 100%)."""
    if (err := _require_db()) is not None:
        return err
    steam_id = str(_steam_id_from_session())
    if (dn_err := _guard_player_commerce(steam_id)) is not None:
        return dn_err
    body = request.get_json(force=True)
    reason = str(body.get("reason", "")).strip()
    if not reason:
        return jsonify({
            "ok": False,
            "error": "Motivo é obrigatório — explique o problema no ticket de contestação",
            "code": "reason_required",
        }), 400
    if len(reason) < _CONTEST_REASON_MIN_LEN:
        return jsonify({
            "ok": False,
            "error": (
                f"Explique o motivo com pelo menos {_CONTEST_REASON_MIN_LEN} caracteres. "
                "A contestação abre um ticket de suporte obrigatório."
            ),
            "code": "reason_too_short",
            "min_length": _CONTEST_REASON_MIN_LEN,
        }), 400

    db = _SessionLocal()
    try:
        order = db.query(Order).filter(Order.order_id == order_id, Order.steam_id == steam_id).first()
        if not order:
            return jsonify({"ok": False, "error": "Pedido não encontrado"}), 404

        status_before = order.status
        order.contested = True
        order.status = "CONTESTADO"
        order.updated_at = _now()
        db.add(Dispute(
            order_id=order.order_id,
            steam_id=steam_id,
            reason=reason,
            status="ABERTO",
            created_at=_now(),
        ))

        from ticket_service import create_ticket

        player_name = _resolve_player_display_name(steam_id) or steam_id
        short = order_id[:8]
        ticket_result = create_ticket(
            db,
            steam_id=steam_id,
            player_name=str(player_name),
            subject=f"Contestação do pedido {short}…",
            body=reason,
            category="resgate",
            priority="urgente",
            order_id=order_id,
        )
        if not ticket_result.get("ok"):
            db.rollback()
            return jsonify({
                "ok": False,
                "error": ticket_result.get("error") or "Falha ao abrir ticket de contestação",
                "code": "ticket_required",
            }), 400

        # create_ticket já fez commit (pedido contestado + ticket)
        final_status = "CONTESTADO"
        ticket_id = (ticket_result.get("ticket") or {}).get("id")
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
            message=f"Jogador contestou pedido {short}… (ticket #{ticket_id})",
            reason=reason,
            ticket_id=ticket_id,
        )
        return jsonify({
            "ok": True,
            "status": final_status,
            "ticket_id": ticket_id,
            "message": (
                "Contestação registrada. Foi aberto um ticket de suporte — "
                "acompanhe em Tickets. Reembolso integral só após análise da equipe."
            ),
        })
    except Exception as exc:
        db.rollback()
        _log_error("player_contest", order_id=order_id, steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": f"Erro ao contestar pedido: {exc}"}), 500
    finally:
        _release_db_session(db)


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

# Desistência do jogador: licenças irrevogáveis; demais itens só após 24h.
# Pedidos PENDENTE (não licença) sem resgate ≥48h → cancelamento + reembolso automático (90%).
# Reembolso integral (100%) do catálogo: apenas via contestação + ticket + decisão admin.
_ORDER_CANCEL_COOLDOWN_HOURS = 24
_ORDER_AUTO_EXPIRE_HOURS = 48
_ORDER_DESIST_REFUND_FACTOR = 0.90
_CONTEST_REASON_MIN_LEN = 20


def _datetime_as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _is_order_license(order: Order) -> bool:
    """True para Type license / licenca_* / entrada de catálogo de licença."""
    item_id = str(order.item_id or "").strip()
    item_type = str(order.item_type or "shop")
    key = item_id.lower()
    if key.startswith("licenca_"):
        return True
    entry = _catalog_entry("kit" if item_type == "kit" else "shop", item_id)
    if isinstance(entry, dict) and entry and _is_catalog_license_item(entry, item_id):
        return True
    return False


def _format_duration_short(delta: timedelta) -> str:
    secs = max(0, int(delta.total_seconds()))
    hours, rem = divmod(secs, 3600)
    minutes = rem // 60
    if hours > 0:
        return f"{hours}h{minutes:02d}m" if minutes else f"{hours}h"
    if minutes > 0:
        return f"{minutes} min"
    return "menos de 1 min"


def _order_cancel_policy(order: Order, *, now: datetime | None = None) -> dict[str, Any]:
    """Regras de desistência/cancelamento para UI e API do jogador."""
    now_utc = _datetime_as_utc(now) or _now()
    created = _datetime_as_utc(order.created_at) or now_utc
    age = now_utc - created
    is_license = _is_order_license(order)
    cooldown = timedelta(hours=_ORDER_CANCEL_COOLDOWN_HOURS)
    cancel_available_at = created + cooldown

    can_cancel = False
    reason_code: str | None = None
    reason: str | None = None

    if str(order.status or "") != "PENDENTE":
        reason_code = "not_pending"
        reason = (
            "Só é possível desistir de resgates ainda pendentes "
            "(aguardando entrada no servidor)"
        )
    elif is_license:
        reason_code = "license_irrevocable"
        reason = (
            "Licenças não podem ser canceladas nem reembolsadas — "
            "a activação é irrevogável."
        )
    elif age < cooldown:
        reason_code = "cooldown_24h"
        remaining = cooldown - age
        reason = (
            f"Só é possível desistir após {_ORDER_CANCEL_COOLDOWN_HOURS}h da compra. "
            f"Aguarde mais {_format_duration_short(remaining)}."
        )
    else:
        can_cancel = True

    return {
        "is_license": is_license,
        "can_cancel": can_cancel,
        "cancel_blocked_code": reason_code,
        "cancel_blocked_reason": reason,
        "cancel_available_at": cancel_available_at.isoformat() if not is_license else None,
        "cancel_cooldown_hours": _ORDER_CANCEL_COOLDOWN_HOURS,
        "auto_cancel_hours": _ORDER_AUTO_EXPIRE_HOURS,
        "desist_refund_factor": _ORDER_DESIST_REFUND_FACTOR,
        "order_age_seconds": max(0, int(age.total_seconds())),
    }


def _license_cancel_blocked_response():
    return jsonify({
        "ok": False,
        "error": (
            "Licenças não podem ser canceladas nem reembolsadas — "
            "a activação é irrevogável."
        ),
        "code": "license_irrevocable",
    }), 403


def expire_stale_pending_orders(db: Any, *, batch_size: int = 50) -> dict[str, Any]:
    """Cancela + reembolsa pedidos PENDENTE (não licença) com idade ≥ 48h. Idempotente."""
    now = _now()
    cutoff = now - timedelta(hours=_ORDER_AUTO_EXPIRE_HOURS)
    candidates = (
        db.query(Order)
        .filter(Order.status == "PENDENTE", Order.created_at <= cutoff)
        .order_by(Order.created_at.asc())
        .limit(max(1, min(200, int(batch_size))))
        .all()
    )

    cancelled: list[dict[str, Any]] = []
    skipped_license = 0

    for order in candidates:
        if _is_order_license(order):
            skipped_license += 1
            continue
        locked = (
            db.query(Order)
            .filter(Order.order_id == order.order_id, Order.status == "PENDENTE")
            .with_for_update()
            .first()
        )
        if not locked:
            continue
        if _is_order_license(locked):
            skipped_license += 1
            continue
        created = _datetime_as_utc(locked.created_at)
        if created is not None and created > cutoff:
            continue

        steam_id = str(locked.steam_id)
        order_id = str(locked.order_id)
        item_type = str(locked.item_type or "shop")
        item_id = str(locked.item_id or "")
        refund = max(0, _order_desist_refund_amount(locked, db))
        paid_amount = max(0, _order_refund_amount(locked, db))
        try:
            new_balance = _credit_order_refund_tx(db, steam_id, refund)
            locked.status = "CANCELADO"
            locked.updated_at = now
            _revoke_entitlement_for_order(steam_id, order_id, db=db)
            db.commit()
        except Exception:
            db.rollback()
            raise

        if refund > 0:
            try:
                from amber_ledger import record_shop_refund

                record_shop_refund(
                    db,
                    order_id=order_id,
                    steam_id=steam_id,
                    refund=refund,
                    event_type="order_auto_cancelled",
                    commit=True,
                )
            except Exception as amber_exc:
                log.warning("Âmbarômetro order_auto_cancel hook: %s", amber_exc)

        _audit_event(
            "order_auto_cancelled",
            actor_type="system",
            target_steam_id=steam_id,
            order_id=order_id,
            item_type=item_type,
            item_id=item_id,
            status_before="PENDENTE",
            status_after="CANCELADO",
            message=(
                f"Auto-cancelamento após {_ORDER_AUTO_EXPIRE_HOURS}h sem resgate — "
                f"reembolso de {refund} Âmbar (90% de {paid_amount}; retenção 10%)"
                if refund > 0
                else f"Auto-cancelamento após {_ORDER_AUTO_EXPIRE_HOURS}h sem resgate"
            ),
            price=refund,
            points_after=new_balance,
            auto_expire_hours=_ORDER_AUTO_EXPIRE_HOURS,
            paid_amount=paid_amount,
            refund_factor=_ORDER_DESIST_REFUND_FACTOR,
        )
        cancelled.append({
            "order_id": order_id,
            "steam_id": steam_id,
            "item_id": item_id,
            "refunded": refund,
            "paid_amount": paid_amount,
        })
        _log(
            "order_auto_cancelled",
            order_id=order_id,
            steam_id=steam_id,
            item_id=item_id,
            refunded=refund,
        )

    return {
        "processed": len(cancelled),
        "skipped_license": skipped_license,
        "cancelled": cancelled,
    }


def _order_refund_amount(order: Order, db: Any | None = None) -> int:
    """Valor pago em Âmbar (points_spent → catálogo → auditoria). Usado em reembolso admin 100%."""
    refund = int(order.points_spent or 0)
    if refund > 0:
        return refund
    item_type = str(order.item_type or "shop")
    entry = _catalog_entry(
        "kit" if item_type == "kit" else "shop",
        str(order.item_id or ""),
    )
    refund = _catalog_price(entry, int(order.amount or 1))
    if refund > 0:
        return refund
    if db is None:
        return 0
    rows = (
        db.query(AuditEvent)
        .filter(
            AuditEvent.order_id == order.order_id,
            AuditEvent.event_type.in_(("purchase_created", "purchase")),
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(5)
        .all()
    )
    for row in rows:
        try:
            payload = json.loads(row.payload_json or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {}
        price = int(payload.get("price") or 0)
        if price > 0:
            return price
    return 0


def _order_desist_refund_amount(order: Order, db: Any | None = None) -> int:
    """Reembolso de desistência/auto-cancel do catálogo: 90% do valor pago (retenção 10%)."""
    paid = max(0, _order_refund_amount(order, db))
    return int(round(paid * _ORDER_DESIST_REFUND_FACTOR))


def _credit_order_refund_tx(db: Any, steam_id: str, refund: int) -> int:
    """Credita reembolso e confirma que o saldo subiu na mesma transação."""
    if refund <= 0:
        return _player_points_tx(db, steam_id)
    before = _player_points_tx(db, steam_id)
    after = _add_player_points_tx(db, steam_id, refund)
    if after < before + refund:
        raise RuntimeError(
            f"Reembolso não creditado (saldo {before} → {after}, esperado +{refund})"
        )
    return after


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
        _release_db_session(db)

    _log("admin_retry", count=len(order_ids), admin=_steam_id_from_session())
    processed = [_process_order_delivery(order_id) for order_id in order_ids]
    return jsonify({"ok": True, "count": len(processed), "items": processed})


@app.route("/api/admin/orders", methods=["GET"])
@admin_required
def admin_list_orders():
    if (err := _require_db()) is not None:
        return err
    status = str(request.args.get("status", "")).strip().upper()
    q_text = str(request.args.get("q", "")).strip()
    sort = str(request.args.get("sort", "created_at")).strip().lower()
    order_dir = str(request.args.get("order", "desc")).strip().lower()
    date_from = str(request.args.get("date_from", "")).strip()
    date_to = str(request.args.get("date_to", "")).strip()
    limit = max(1, min(200, int(request.args.get("limit", 50))))
    offset = max(0, int(request.args.get("offset", 0)))
    db = _SessionLocal()
    try:
        query = db.query(Order)
        if status:
            query = query.filter(Order.status == status)
        if q_text:
            if q_text.isdigit() and len(q_text) >= 10:
                query = query.filter(Order.steam_id.like(f"{q_text}%"))
            elif len(q_text) >= 8:
                query = query.filter(
                    (Order.order_id.like(f"%{q_text}%")) | (Order.steam_id.like(f"{q_text}%"))
                )
            else:
                query = query.filter(Order.steam_id.like(f"{q_text}%"))
        if date_from:
            try:
                dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
                if dt_from.tzinfo is not None:
                    dt_from = dt_from.replace(tzinfo=None)
                query = query.filter(Order.created_at >= dt_from)
            except ValueError:
                pass
        if date_to:
            try:
                dt_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
                if dt_to.tzinfo is not None:
                    dt_to = dt_to.replace(tzinfo=None)
                if len(date_to) <= 10:
                    dt_to = dt_to.replace(hour=23, minute=59, second=59, microsecond=999999)
                query = query.filter(Order.created_at <= dt_to)
            except ValueError:
                pass
        sort_col = Order.created_at if sort == "created_at" else Order.created_at
        order_by = sort_col.asc() if order_dir == "asc" else sort_col.desc()
        total = query.count()
        rows = query.order_by(order_by).offset(offset).limit(limit).all()
        return jsonify(
            {
                "ok": True,
                "total": total,
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
                        "is_license": _is_order_license(o),
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
        _release_db_session(db)


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
        if _is_order_license(order):
            return _license_cancel_blocked_response()
        if order.status in _ADMIN_TERMINAL_STATUSES:
            return jsonify({
                "ok": False,
                "error": f"Pedido já está {order.status} — não é possível reembolsar novamente",
            }), 409

        status_before = order.status
        steam_id = str(order.steam_id)
        item_type = order.item_type
        item_id = order.item_id
        refund = _order_refund_amount(order, db)
        if refund <= 0:
            return jsonify({
                "ok": False,
                "error": (
                    "Valor do reembolso é zero — o pedido não tem Âmbares registrados. "
                    "Use «Ajustar saldo» no jogador se precisar devolver manualmente."
                ),
            }), 400

        new_balance = _credit_order_refund_tx(db, steam_id, refund)

        _revoke_entitlement_for_order(steam_id, order_id, db=db)
        closed = _close_order_disputes(db, order_id)
        order.contested = False
        order.status = "REEMBOLSADO"
        order.updated_at = _now()
        db.commit()
        try:
            from amber_ledger import record_shop_refund

            record_shop_refund(
                db,
                order_id=order_id,
                steam_id=steam_id,
                refund=refund,
                event_type="admin_refund",
                commit=True,
            )
        except Exception as amber_exc:
            log.warning("Âmbarômetro admin_refund hook: %s", amber_exc)
    except Exception as exc:
        db.rollback()
        _log_error("admin_refund_order", order_id=order_id, admin=admin_id, error=str(exc))
        return jsonify({"ok": False, "error": f"Erro ao reembolsar: {exc}"}), 500
    finally:
        _release_db_session(db)

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
        _release_db_session(db)

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
        if _is_order_license(order):
            return _license_cancel_blocked_response()
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
        _release_db_session(db)

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
        _release_db_session(db)


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
        perm_sync = _sync_player_entitlements_to_permission_db(
            str(order.steam_id), entitlements,
        )
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
            "permissions_sync": perm_sync,
            "timed_points_total": _compute_timed_points_total([e["group"] for e in entitlements]),
        })
    finally:
        _release_db_session(db)


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
        _release_db_session(db)

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
        _release_db_session(db)

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
        _release_db_session(db)


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
        _release_db_session(db)


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
        _release_db_session(db)


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
        _release_db_session(db)


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


@app.route("/api/admin/staff-roles", methods=["GET"])
@admin_required
def admin_staff_roles_catalog():
    return jsonify({"ok": True, "items": _staff_role_catalog()})


@app.route("/api/admin/players/<steam_id>/staff-roles", methods=["POST"])
@admin_required
@limiter.limit("120 per hour")
def admin_player_staff_roles(steam_id: str):
    body = request.get_json(force=True, silent=True) or {}
    result = _admin_player_staff_role(
        steam_id.strip(),
        action=str(body.get("action") or "grant"),
        group=str(body.get("group") or body.get("role") or "").strip(),
        reason=str(body.get("reason") or "").strip(),
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
        lic = _get_license_grant(entry, str(order.item_id or "")) if entry else None
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


@app.route("/api/admin/sync-all-permissions", methods=["POST"])
@admin_required
@limiter.limit("12 per hour")
def admin_sync_all_permissions():
    """Reconcilia player_entitlements ↔ ark_permission para todos os jogadores irregulares."""
    if (err := _require_db()) is not None:
        return err
    body = request.get_json(force=True, silent=True) or {}
    dry_run = bool(body.get("dry_run"))
    result = _reconcile_all_entitlements_to_permission_db(dry_run=dry_run)
    status = 200 if result.get("ok") else 500
    return jsonify(result), status


@app.route("/api/admin/players/<steam_id>/sync-permissions", methods=["POST"])
@admin_required
@limiter.limit("60 per hour")
def admin_player_sync_permissions(steam_id: str):
    """Reconstrói ark_permission.players a partir de player_entitlements (reparo)."""
    if (err := _require_db()) is not None:
        return err
    sid = str(steam_id or "").strip()
    if not _is_valid_steamid64(sid):
        return jsonify({"ok": False, "error": "SteamID64 inválido"}), 400
    entitlements = _get_player_entitlements(sid)
    perm_sync = _sync_player_entitlements_to_permission_db(sid, entitlements)
    mysql_ok = bool(perm_sync and perm_sync[0].get("ok"))
    return jsonify({
        "ok": mysql_ok,
        "steam_id": sid,
        "entitlements": entitlements,
        "permissions_sync": perm_sync,
        "timed_points_total": _compute_timed_points_total([e["group"] for e in entitlements]),
    }), 200 if mysql_ok else 500


@app.route("/api/admin/players/<steam_id>/kit-limits/<kit_id>/revoke", methods=["POST"])
@admin_required
@limiter.limit("120 per hour")
def admin_revoke_kit_limit(steam_id: str, kit_id: str):
    body = request.get_json(force=True, silent=True) or {}
    result = _admin_revoke_kit_limit(
        steam_id.strip(),
        kit_id.strip(),
        reason=str(body.get("reason") or "").strip(),
    )
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.route("/api/player/kit-limits", methods=["GET"])
@login_required
@limiter.limit("60 per minute")
def player_kit_limits():
    if (err := _require_db()) is not None:
        return err
    steam_id = str(_steam_id_from_session())
    db = _SessionLocal()
    try:
        limits = _build_player_kit_limits(db, steam_id)
    finally:
        _release_db_session(db)
    return jsonify({"ok": True, "kits": limits})


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
            _release_db_session(db)
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
            _release_db_session(db)
    else:
        ids = _load_admin_steamids()
        ids.discard(steam_id)
        _ADMIN_FILE.write_text(json.dumps(sorted(ids), indent=2, ensure_ascii=False), encoding="utf-8")

    _log("admin_removed", steam_id=steam_id, by=_steam_id_from_session())
    return jsonify({"ok": True})


# ── Admin support staff routes ────────────────────────────────────────────────

@app.route("/api/admin/support-staff", methods=["GET"])
@admin_required
def admin_list_support_staff():
    items = sorted(_load_support_steamids())
    return jsonify({"ok": True, "items": items})


@app.route("/api/admin/support-staff", methods=["POST"])
@admin_required
def admin_add_support_staff():
    body = request.get_json(force=True)
    steam_id = str(body.get("steam_id", "")).strip()
    if not _is_valid_steamid64(steam_id):
        return jsonify({"ok": False, "error": "SteamID64 inválido"}), 400
    if _is_admin_steamid(steam_id):
        return jsonify({
            "ok": False,
            "error": "Este SteamID já é administrador — não precisa ser cadastrado como suporte.",
        }), 400

    if _db_ready():
        db = _SessionLocal()
        try:
            db.merge(ShopSupport(steam_id=steam_id))
            db.commit()
        finally:
            _release_db_session(db)
    else:
        ids = _load_support_steamids()
        ids.add(steam_id)
        _SUPPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SUPPORT_FILE.write_text(json.dumps(sorted(ids), indent=2, ensure_ascii=False), encoding="utf-8")

    _invalidate_support_steamids_cache()
    _log("support_staff_added", steam_id=steam_id, by=_steam_id_from_session())
    return jsonify({"ok": True})


@app.route("/api/admin/support-staff/<steam_id>", methods=["DELETE"])
@admin_required
def admin_remove_support_staff(steam_id: str):
    steam_id = steam_id.strip()
    if not _is_valid_steamid64(steam_id):
        return jsonify({"ok": False, "error": "SteamID64 inválido"}), 400

    if _db_ready():
        db = _SessionLocal()
        try:
            db.query(ShopSupport).filter(ShopSupport.steam_id == steam_id).delete()
            db.commit()
        finally:
            _release_db_session(db)
    else:
        ids = _load_support_steamids()
        ids.discard(steam_id)
        _SUPPORT_FILE.write_text(json.dumps(sorted(ids), indent=2, ensure_ascii=False), encoding="utf-8")

    _invalidate_support_steamids_cache()
    _log("support_staff_removed", steam_id=steam_id, by=_steam_id_from_session())
    return jsonify({"ok": True})


from market_routes import register_market_routes

register_market_routes(
    app,
    db_ready=_db_ready,
    session_factory=_db_session_factory,
    read_shop_config=_read_shop_config,
    load_settings=_load_settings,
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
    steam_id_from_session=_steam_id_from_session,
)

from cross_chat_discord import start_discord_bridge

start_discord_bridge(
    session_factory=_db_session_factory,
    load_settings=_load_settings,
    save_settings=_save_settings,
    db_ready=_db_ready,
)

from ticket_routes import register_ticket_routes

_TICKET_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
register_ticket_routes(
    app,
    db_ready=_db_ready,
    session_factory=_db_session_factory,
    login_required=login_required,
    admin_required=admin_required,
    ticket_staff_required=ticket_staff_required,
    steam_id_from_session=_steam_id_from_session,
    is_admin_steamid=_is_admin_steamid,
    can_manage_tickets=_can_manage_tickets,
    resolve_display_name=lambda sid: _resolve_player_display_name(sid),
    regulamento_guard=_guard_regulamento_accepted,
    uploads_dir=_TICKET_UPLOADS_DIR,
    limiter=limiter,
    load_settings=_load_settings,
    save_settings=_save_settings,
)

from regulamento_service import register_regulamento_routes

register_regulamento_routes(
    app,
    login_required=login_required,
    db_ready=_db_ready,
    session_factory=_db_session_factory,
    steam_id_from_session=_steam_id_from_session,
    store_user_model=StoreUser,
    audit_fn=_audit_event,
)

from notification_routes import register_notification_routes

register_notification_routes(
    app,
    db_ready=_db_ready,
    session_factory=_db_session_factory,
    login_required=login_required,
    steam_id_from_session=_steam_id_from_session,
    limiter=limiter,
)

from poll_routes import register_poll_routes
from notification_service import create_notification as _create_user_notification

register_poll_routes(
    app,
    db_ready=_db_ready,
    session_factory=_db_session_factory,
    login_required=login_required,
    admin_required=admin_required,
    steam_id_from_session=_steam_id_from_session,
    limiter=limiter,
    create_notification=_create_user_notification,
)

from suggestion_routes import register_suggestion_routes

register_suggestion_routes(
    app,
    db_ready=_db_ready,
    session_factory=_db_session_factory,
    login_required=login_required,
    admin_required=admin_required,
    steam_id_from_session=_steam_id_from_session,
    regulamento_guard=_guard_regulamento_accepted,
    limiter=limiter,
)

from media_routes import register_media_routes

register_media_routes(
    app,
    db_ready=_db_ready,
    session_factory=_db_session_factory,
    admin_required=admin_required,
    steam_id_from_session=_steam_id_from_session,
    limiter=limiter,
)

from home_notice_routes import register_home_notice_routes

register_home_notice_routes(
    app,
    db_ready=_db_ready,
    session_factory=_db_session_factory,
    admin_required=admin_required,
    steam_id_from_session=_steam_id_from_session,
    limiter=limiter,
)

from lottery_routes import register_lottery_routes
from lottery_service import configure_lottery


def _lottery_resolve_catalog_prize(kind: str, item_id: str) -> dict[str, Any] | None:
    kind = str(kind or "").strip().lower()
    item_id = str(item_id or "").strip()
    if not item_id:
        return None
    if kind == "kit":
        resolved = _resolve_catalog_item_id("kit", item_id)
        entry = _catalog_entry("kit", resolved)
        if not entry:
            return None
        return {
            "kind": "kit",
            "item_id": resolved,
            "label": str(entry.get("Description") or entry.get("Name") or resolved),
        }
    if kind == "license":
        resolved = _resolve_catalog_item_id("shop", item_id)
        entry = _catalog_entry("shop", resolved)
        if not entry or not _is_catalog_license_item(entry, resolved):
            return None
        lic = _get_license_grant(entry, resolved)
        if not lic:
            return None
        return {
            "kind": "license",
            "item_id": resolved,
            "label": str(entry.get("Description") or entry.get("Name") or resolved),
            "group": str(lic.get("Group") or ""),
            "days": int(lic.get("Days", 30) or 30),
        }
    return None


def _lottery_prize_options() -> dict[str, Any]:
    """Lista kits e licenças do catálogo CustomShop para o admin do sorteio."""
    kits: list[dict[str, Any]] = []
    licenses: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        kits = [
            {"item_id": k["kit_id"], "label": k["label"], "kind": "kit"}
            for k in _catalog_kit_options()
        ]
    except Exception as exc:
        _log("lottery_prize_options_kits_failed", error=str(exc))
        errors.append(f"kits:{exc}")
    try:
        licenses = [
            {
                "item_id": x["item_id"],
                "label": x["label"],
                "kind": "license",
                "group": x.get("group"),
                "days": x.get("days"),
            }
            for x in _catalog_license_options()
        ]
    except Exception as exc:
        _log("lottery_prize_options_licenses_failed", error=str(exc))
        errors.append(f"licenses:{exc}")
    out: dict[str, Any] = {"kits": kits, "licenses": licenses}
    if errors:
        out["errors"] = errors
    return out


def _lottery_deliver_catalog_prize(
    db: Any,
    steam_id: str,
    prize: dict[str, Any],
    *,
    campaign_id: int,
    winning_number: int,
) -> dict[str, Any]:
    """Cria pedido PENDENTE (fila da loja) e activa entitlement de licença se aplicável."""
    kind = str(prize.get("kind") or "").strip().lower()
    item_id = str(prize.get("item_id") or "").strip()
    amount = max(1, int(prize.get("amount") or 1))
    if kind not in ("kit", "license") or not item_id:
        raise ValueError("invalid_catalog_prize")
    item_type = "kit" if kind == "kit" else "shop"
    resolved = _resolve_catalog_item_id(item_type, item_id)
    idem = f"lottery:catalog:{int(campaign_id)}:{int(winning_number)}:{resolved}"
    order_id = str(uuid.uuid4())
    now = _now()
    server_id = str(_load_settings().get("server_id", "default"))
    # Kits de prémio ignoram DefaultAmount (mesmo padrão que entrega admin)
    original = idem if kind == "license" else f"__admin_skip_kit_limit__|{idem}"
    existing = db.execute(
        text(
            "SELECT order_id FROM orders "
            "WHERE original_order_id = :a OR original_order_id = :b LIMIT 1"
        ),
        {"a": idem, "b": f"__admin_skip_kit_limit__|{idem}"},
    ).fetchone()
    if existing:
        return {
            "order_id": str(existing[0]),
            "item_id": resolved,
            "kind": kind,
            "skipped": True,
        }
    order = Order(
        order_id=order_id,
        steam_id=str(steam_id),
        server_id=server_id,
        item_type=item_type,
        item_id=resolved,
        amount=amount,
        points_spent=0,
        status="PENDENTE",
        original_order_id=original,
        created_at=now,
        updated_at=now,
    )
    db.add(order)
    db.flush()
    result: dict[str, Any] = {
        "order_id": order_id,
        "item_id": resolved,
        "kind": kind,
        "amount": amount,
    }
    if kind == "license":
        entry = _catalog_entry("shop", resolved)
        lic = _get_license_grant(entry, resolved) if entry else None
        if not lic:
            raise ValueError(f"license_grant_missing:{resolved}")
        days = int(lic.get("Days", 30) or 30)
        group = str(lic["Group"])
        _apply_entitlement_grant_tx(
            db,
            str(steam_id),
            group,
            days,
            source=order_id,
            notes=f"lottery:{resolved}",
        )
        result["license_group"] = group
        result["license_days"] = days
    _log(
        "lottery_catalog_prize_queued",
        order_id=order_id,
        steam_id=str(steam_id),
        item_id=resolved,
        kind=kind,
        campaign_id=int(campaign_id),
        winning_number=int(winning_number),
    )
    return result


def _lottery_sync_license_permissions(steam_id: str, group: str, days: int) -> Any:
    return _sync_license_permissions_all_servers(
        str(steam_id), str(group), grant=True, days=int(days),
    )


configure_lottery(
    credit_fn=_add_player_points_tx,
    debit_fn=_subtract_player_points_tx,
    settings_fn=_load_settings,
    save_settings_fn=_save_settings,
    resolve_catalog_prize_fn=_lottery_resolve_catalog_prize,
    deliver_catalog_prize_fn=_lottery_deliver_catalog_prize,
    prize_options_fn=_lottery_prize_options,
    sync_license_permissions_fn=_lottery_sync_license_permissions,
)
register_lottery_routes(
    app,
    db_ready=_db_ready,
    session_factory=_db_session_factory,
    login_required=login_required,
    admin_required=admin_required,
    steam_id_from_session=_steam_id_from_session,
    limiter=limiter,
)

from custom_dino_routes import register_custom_dino_routes
from custom_dino_service import configure_custom_dino

configure_custom_dino(settings_fn=_load_settings)
register_custom_dino_routes(
    app,
    db_ready=_db_ready,
    session_factory=_db_session_factory,
    admin_required=admin_required,
    login_required=login_required,
    api_key_required=api_key_required,
    steam_id_from_session=_steam_id_from_session,
    load_settings=_load_settings,
    is_valid_steamid64=_is_valid_steamid64,
    audit_event=_audit_event,
    get_server_id=lambda: str(_load_settings().get("server_id", "default")),
    limiter=limiter,
)

from dino_order_routes import register_dino_order_routes
from dino_order_service import configure_dino_order
from dino_order_showcase_service import configure_dino_order_showcase
from dino_order_vitrine_service import configure_dino_order_vitrine

configure_dino_order_showcase(
    showcases_file=_ENCOMENDA_SHOWCASE_FILE,
    uploads_dir=_ENCOMENDA_SHOWCASE_UPLOADS_DIR,
)
configure_dino_order_vitrine(vitrine_file=_ENCOMENDA_VITRINE_FILE)
configure_dino_order(
    settings_fn=_load_settings,
    debit_fn=_subtract_player_points_tx,
    credit_fn=_add_player_points_tx,
    get_player_points_fn=_get_player_points,
)
register_dino_order_routes(
    app,
    db_ready=_db_ready,
    session_factory=_db_session_factory,
    login_required=login_required,
    admin_required=admin_required,
    steam_id_from_session=_steam_id_from_session,
    guard_player_commerce=_guard_player_commerce,
    audit_event=_audit_event,
    get_server_id=lambda: str(_load_settings().get("server_id", "default")),
    limiter=limiter,
)

from ticket_notify import configure_ticket_notify

configure_ticket_notify(load_settings=_load_settings)

# ── Área de Tribo ──────────────────────────────────────────
from tribe_routes import register_tribe_routes

register_tribe_routes(
    app,
    db_ready=_db_ready,
    session_factory=_db_session_factory,
    login_required=login_required,
    admin_required=admin_required,
    api_key_required=api_key_required,
    steam_id_from_session=_steam_id_from_session,
    is_admin_steamid=_is_admin_steamid,
    limiter=limiter,
    trigger_tribe_sync_rcon=_trigger_tribe_sync_rcon_all,
)

from plugin_debug_routes import register_plugin_debug_routes

register_plugin_debug_routes(
    app,
    db_ready=_db_ready,
    session_factory=_db_session_factory,
    admin_required=admin_required,
    api_key_required=api_key_required,
)

if os.environ.get("ARKSHOP_SKIP_DB_BOOT") != "1":
    _kick_background_db_init()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5177))
    log.info("ArkShop Web Manager rodando em http://127.0.0.1:%d", port)
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
