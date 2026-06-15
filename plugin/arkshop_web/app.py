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
import socket
import struct
import sys
import threading
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from dotenv import load_dotenv

from cryptography.fernet import Fernet
from flask import Flask, jsonify, redirect, request, send_from_directory, session
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, scoped_session, sessionmaker

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


def _log(event: str, **kw: Any) -> None:
    parts = " ".join(f'{k}={json.dumps(v)}' for k, v in kw.items())
    log.info('"%s" %s', event, parts)


def _log_error(event: str, **kw: Any) -> None:
    parts = " ".join(f'{k}={json.dumps(v)}' for k, v in kw.items())
    log.error('"%s" %s', event, parts)


# ── Paths (dev vs PyInstaller) ────────────────────────────────────────────────

def _bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def _data_dir() -> Path:
    override = os.environ.get("ARKSHOP_DATA_DIR", "").strip()
    if override:
        p = Path(override)
    elif getattr(sys, "frozen", False):
        p = Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager" / "arkshop_web"
    else:
        p = Path(__file__).resolve().parent
    p.mkdir(parents=True, exist_ok=True)
    return p


_BUNDLE_DIR = _bundle_dir()
_DATA_DIR = _data_dir()

# ── Load environment variables ────────────────────────────────────────────────

# Resolve .env na raiz do projeto (um nível acima de plugin/arkshop_web/)
_PROJECT_ROOT = _BUNDLE_DIR.parent.parent if not getattr(sys, "frozen", False) else _BUNDLE_DIR
_ENV_PATH = (_PROJECT_ROOT / ".env") if not getattr(sys, "frozen", False) else Path()
load_dotenv(dotenv_path=_ENV_PATH if _ENV_PATH.exists() else None)


# ── App setup ─────────────────────────────────────────────────────────────────

app = Flask(__name__, static_folder=str(_BUNDLE_DIR / "static"), static_url_path="")
CORS(app)
app.secret_key = os.environ.get("ARKSHOP_WEB_SECRET", "arkshop-web-dev-secret-change-me")

_DEFAULT_CONFIG_PATH = os.environ.get("ARKSHOP_CONFIG_PATH", "").strip()
if not _DEFAULT_CONFIG_PATH:
    _cfg_candidates = [
        _BUNDLE_DIR / "CustomShop" / "configs" / "config.json",
        _BUNDLE_DIR.parent / "CustomShop" / "configs" / "config.json",
    ]
    _DEFAULT_CONFIG_PATH = str(next((p for p in _cfg_candidates if p.is_file()), _cfg_candidates[0]))
_STATE_FILE = _DATA_DIR / "settings.json"
_PLAYERS_FILE = _DATA_DIR / "players.json"
_ADMIN_FILE = _DATA_DIR / "admin_steamids.json"
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

# Secret key MUST come from environment in production
_secret_from_env = os.environ.get("ARKSHOP_WEB_SECRET", "").strip()
if _secret_from_env:
    app.secret_key = _secret_from_env
else:
    # Use a development secret if not set in env
    app.secret_key = "arkshop-web-dev-secret-change-me-in-prod"
    log.warning("ARKSHOP_WEB_SECRET não definida! "
                "Usando secret de desenvolvimento. "
                "Defina a variável de ambiente ARKSHOP_WEB_SECRET em produção.")

# API Key for CustomShop ↔ arkshop_web internal communication
# Must be set via environment variable ARKSHOP_API_KEY
_ARKSHOP_API_KEY = os.environ.get("ARKSHOP_API_KEY", "").strip()
_ENCRYPTED_PREFIX = "ENC:"
_SENSITIVE_SETTINGS_KEYS = ("rcon_password", "db_password")

# Rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

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


# ── DB setup ──────────────────────────────────────────────────────────────────

_ENGINE: Any = None
_SessionLocal: Any = None  # set by _configure_database(); None only before first DB config


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


def _migrate_schema(engine: Any) -> None:
    """Detecta schema antigo (orders sem order_id) e recria as tabelas."""
    is_mysql = "mysql" in str(engine.url).lower()
    if not is_mysql:
        Base.metadata.create_all(bind=engine)
        return
    with engine.connect() as conn:
        tbl_row = conn.execute(text("SHOW TABLES LIKE 'orders'")).fetchone()
        if tbl_row is not None:
            col_row = conn.execute(text("SHOW COLUMNS FROM `orders` LIKE 'order_id'")).fetchone()
            if col_row is None:
                log.warning("Schema antigo detectado (orders sem order_id) — recriando tabelas")
                conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
                for tbl in ("order_attempts", "rebuys", "disputes", "orders"):
                    conn.execute(text(f"DROP TABLE IF EXISTS `{tbl}`"))
                conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
                conn.commit()
    Base.metadata.create_all(bind=engine)


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
    global _ENGINE, _SessionLocal, _ACTIVE_DATABASE_URL

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

    if not normalized:
        return

    engine = create_engine(normalized, future=True)
    session_local = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True))

    # Registra o DB como "configurado" ANTES de create_all.
    # Assim _db_ready() retorna True mesmo se o MariaDB estiver offline no boot;
    # as queries falharão com erro de conexão (não "Banco não configurado").
    _ENGINE = engine
    _SessionLocal = session_local
    _ACTIVE_DATABASE_URL = normalized
    _log("db_configured", url=normalized[:40] + "...")

    schema_ok = False
    try:
        _migrate_schema(engine)
        schema_ok = True
    except Exception as exc:
        log.warning("DB schema setup falhou (%s): %s — background thread tentará reconectar", normalized[:40], exc)

    if not schema_ok:
        _start_db_reconnect_watcher()


_DB_INIT_LOCK = threading.Lock()
_DB_INITIALIZED = False


def _initialize_database_if_needed() -> None:
    global _DB_INITIALIZED
    if _DB_INITIALIZED:
        return
    with _DB_INIT_LOCK:
        if _DB_INITIALIZED:
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


def _get_db_session():
    """Get a database session, or None if not ready."""
    if _SessionLocal is not None:
        return _SessionLocal()
    return None


def _require_db():
    if not _db_ready():
        return jsonify({
            "ok": False,
            "error": "Banco não configurado. Configure as credenciais em Configurações → DB.",
            "db_offline": True,
        }), 503
    return None


def _ensure_runtime_initialized_before_request() -> None:
    _initialize_database_if_needed()
    _initialize_scheduler_if_needed()


app.before_request(_ensure_runtime_initialized_before_request)


def _load_settings() -> Dict[str, Any]:
    if _STATE_FILE.exists():
        try:
            data = json.loads(_STATE_FILE.read_text(encoding="utf-8"))
            # Decrypt sensitive fields
            for key in _SENSITIVE_SETTINGS_KEYS:
                if key in data and isinstance(data[key], str):
                    data[key] = _decrypt_value(data[key])
            return data
        except Exception:
            pass
    return {
        "config_path": _DEFAULT_CONFIG_PATH,
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
    }


def _save_settings(data: Dict[str, Any]) -> None:
    safe_data = data.copy()
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


def _load_admin_steamids() -> set[str]:
    if _db_ready():
        db = _SessionLocal()
        try:
            rows = db.query(ShopAdmin).all()
            if rows:
                return {r.steam_id for r in rows}
        except Exception:
            pass
        finally:
            db.close()

    if not _ADMIN_FILE.exists():
        return set()
    try:
        data = json.loads(_ADMIN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return set()

    values = data if isinstance(data, list) else data.get("steam_ids", []) if isinstance(data, dict) else []
    return {str(v).strip() for v in values if isinstance(v, (str, int)) and _is_valid_steamid64(str(v))}


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
        return int(row[0]) if row else None
    except Exception:
        return None
    finally:
        db.close()


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
        if not _steam_id_from_session():
            return jsonify({"ok": False, "error": "Não autenticado", "message": _STEAM_SESSION_REQUIRED_MESSAGE}), 401
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


# ── RCON ──────────────────────────────────────────────────────────────────────

def _rcon_command(host: str, port: int, password: str, command: str, timeout: float = 5.0) -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((host, port))

    def _pack(pkt_id: int, pkt_type: int, body: str) -> bytes:
        encoded = body.encode("utf-8") + b"\x00\x00"
        size = 4 + 4 + len(encoded)
        return struct.pack("<iii", size, pkt_id, pkt_type) + encoded

    def _recv() -> tuple[int, int, str]:
        raw_size = sock.recv(4)
        size = struct.unpack("<i", raw_size)[0]
        data = b""
        while len(data) < size:
            chunk = sock.recv(size - len(data))
            if not chunk:
                break
            data += chunk
        pkt_id, pkt_type = struct.unpack("<ii", data[:8])
        body = data[8:].rstrip(b"\x00").decode("utf-8", errors="replace")
        return pkt_id, pkt_type, body

    try:
        sock.send(_pack(1, 3, password))
        _recv()
        sock.send(_pack(2, 2, command))
        _, _, response = _recv()
        return response
    finally:
        sock.close()


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

def _create_order(steam_id: str, item_type: str, item_id: str, amount: int, original_order_id: str | None = None) -> tuple[Order | None, str | None]:
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
            Order.status == "PENDENTE"
        ).all()
        items = [{
            "order_id": o.order_id,
            "item_id": o.item_id,
            "amount": o.amount,
            "item_type": o.item_type,
        } for o in orders]
        return jsonify({"ok": True, "items": items, "orders": items})
    except Exception as exc:
        _log_error("get_pending_deliveries", steam_id=steam_id, error=str(exc))
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
            order.status = "ENTREGUE"
            order.last_error = None
            order.updated_at = _now()
            delivered.append(order_id)
        db.commit()
        _log("orders_marked_delivered", steam_id=steam_id, count=len(delivered))
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
    return send_from_directory("static", "index.html")


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
    _log("auth_login", steam_id=steam_id, is_admin=_is_admin_steamid(steam_id))
    return redirect("/")


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    steam_id = _steam_id_from_session()
    session.pop("steam_id", None)
    _log("auth_logout", steam_id=steam_id)
    return jsonify({"ok": True})


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    steam_id = _steam_id_from_session()
    if not steam_id:
        return jsonify({"authenticated": False, "is_admin": False, "steam_id": None})
    return jsonify({"authenticated": True, "is_admin": _is_admin_steamid(steam_id), "steam_id": steam_id})


# ── Settings routes ───────────────────────────────────────────────────────────

@app.route("/api/settings", methods=["GET"])
@admin_required
def get_settings():
    s = _load_settings()
    safe = {k: v for k, v in s.items() if k not in ("rcon_password", "db_password")}
    safe["rcon_password_set"] = bool(s.get("rcon_password"))
    safe["db_password_set"] = bool(s.get("db_password"))
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
    ):
        if key in body:
            s[key] = body[key]
    if "rcon_password" in body and body["rcon_password"] != "":
        s["rcon_password"] = body["rcon_password"]
    if "db_password" in body and body["db_password"] != "":
        s["db_password"] = body["db_password"]
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
        "rcon_host": str(body.get("rcon_host", "127.0.0.1")).strip(),
        "rcon_port": int(body.get("rcon_port", 27020)),
        "delivery_command_template": str(body.get("delivery_command_template", "Shop.Deliver {steam_id} {item_id} {amount}")).strip(),
        "retry_max_attempts": int(body.get("retry_max_attempts", 10)),
    }
    if "rcon_password" in body and body["rcon_password"] != "":
        entry["rcon_password"] = body["rcon_password"]
    else:
        for existing in servers:
            if existing.get("server_id") == server_id:
                entry["rcon_password"] = existing.get("rcon_password", "")
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
    return data


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
    path = Path(s["config_path"])
    body = request.get_json(force=True)
    # Normaliza ShopItems -> Items ao salvar (formato CustomShop)
    body = _normalize_config_to_file(body)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
        _log("config_saved", path=str(path), admin=_steam_id_from_session())
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


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
        return jsonify({"ok": True, "info": f"Banco conectado ({_ACTIVE_DATABASE_URL[:30]}...)"})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 200


# ── Catalog (público, sem autenticação) ───────────────────────────────────────

@app.route("/api/catalog", methods=["GET"])
def get_catalog():
    """Retorna os itens da loja sem autenticação — visível a todos os jogadores."""
    s = _load_settings()
    path = Path(s["config_path"])
    if not path.exists():
        return jsonify({"items": {}})
    try:
        text_body = path.read_text(encoding="utf-8-sig")
        try:
            data = json.loads(text_body)
        except json.JSONDecodeError:
            cleaned = re.sub(r"//[^\n]*", "", text_body)
            data = json.loads(cleaned)
        # Expõe somente os itens (sem configurações sensíveis)
        items = data.get("Items") or data.get("ShopItems") or {}
        shop_name = data.get("ShopName") or data.get("shop_name") or "ARKLAND Shop"
        return jsonify({"items": items, "shop_name": shop_name})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


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
    """Retorna a lista de links de download do config.json + artefatos do projeto."""
    # Artefatos automáticos do projeto (lidos do version.json)
    release = _get_project_release()
    auto = []
    if release.get("download_url"):
        ver = release.get("version", "latest")
        auto.append({
            "id":          "arkland_installer",
            "label":       f"ARKLAND Server Manager v{ver}",
            "description": "Instalador completo — inclui app desktop, web store integrada e plugin CustomShop.",
            "url":         release["download_url"],
            "icon":        "download",
            "category":    "ARKLAND",
            "_auto":       True,
        })
        # Link direto para a página de releases no GitHub
        releases_page = release["download_url"].split("/download/")[0].replace("/releases", "") + "/releases"
        auto.append({
            "id":          "arkland_releases",
            "label":       "Todas as Versões (GitHub Releases)",
            "description": "Histórico completo de releases, changelogs e versões anteriores.",
            "url":         releases_page,
            "icon":        "github",
            "category":    "ARKLAND",
            "_auto":       True,
        })

    # Links configurados manualmente no config.json
    s = _load_settings()
    path = Path(s["config_path"])
    manual = []
    if path.exists():
        try:
            text = path.read_text(encoding="utf-8-sig")
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                cleaned = re.sub(r"//[^\n]*", "", text)
                data = json.loads(cleaned)
            manual = [d for d in (data.get("Downloads") or []) if not d.get("_auto")]
        except Exception:
            pass

    return auto + manual


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


# ── RCON routes ───────────────────────────────────────────────────────────────

@app.route("/api/rcon/reload", methods=["POST"])
@admin_required
@limiter.limit("10 per hour")
def rcon_reload():
    s = _load_settings()
    try:
        resp = _rcon_command(s.get("rcon_host", "127.0.0.1"), int(s.get("rcon_port", 27020)), s.get("rcon_password", ""), "Shop.Reload")
        _log("rcon_reload", admin=_steam_id_from_session(), response=resp[:100])
        return jsonify({"ok": True, "response": resp})
    except Exception as exc:
        _log_error("rcon_reload", admin=_steam_id_from_session(), error=str(exc))
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/rcon/points", methods=["POST"])
@admin_required
@limiter.limit("20 per hour")
def rcon_points():
    s = _load_settings()
    body = request.get_json(force=True)
    action = body.get("action", "get")
    player = body.get("player", "")
    amount = body.get("amount", 0)
    cmd = f"Shop.GetPoints {player}" if action == "get" else f"Shop.AddPoints {player} {amount}" if action == "add" else f"Shop.SetPoints {player} {amount}"
    try:
        resp = _rcon_command(s.get("rcon_host", "127.0.0.1"), int(s.get("rcon_port", 27020)), s.get("rcon_password", ""), cmd)
        return jsonify({"ok": True, "response": resp})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/rcon/command", methods=["POST"])
@admin_required
@limiter.limit("20 per hour")
def rcon_custom():
    s = _load_settings()
    body = request.get_json(force=True)
    cmd = body.get("command", "")
    if not cmd:
        return jsonify({"error": "Comando vazio"}), 400
    try:
        resp = _rcon_command(s.get("rcon_host", "127.0.0.1"), int(s.get("rcon_port", 27020)), s.get("rcon_password", ""), cmd)
        return jsonify({"ok": True, "response": resp})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/rcon/purchase", methods=["POST"])
@admin_required
def rcon_purchase_admin():
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

@app.route("/api/player/purchase", methods=["POST"])
@login_required
@limiter.limit("10 per minute; 50 per hour")
def player_purchase():
    body = request.get_json(force=True)
    steam_id = _steam_id_from_session()
    item_id = str(body.get("item_id", "")).strip()
    item_type = str(body.get("item_type", "shop")).strip() or "shop"
    amount = int(body.get("amount", 1))

    if (err := _require_db()) is not None:
        return err

    # Idempotency check — client must supply a unique key per purchase attempt
    idempotency_key = str(body.get("idempotency_key", "")).strip()
    if idempotency_key:
        if not _check_idempotency(idempotency_key):
            # Duplicate request — find and return the existing order
            _log("purchase_duplicate_idempotency", steam_id=str(steam_id),
                 idempotency_key=idempotency_key)
            return jsonify({"ok": False, "error": "Pedido duplicado — esta compra já foi processada",
                           "idempotency_key": idempotency_key}), 409

    price = int(body.get("price", 0))
    if price > 0:
        balance = _get_player_points(str(steam_id))
        if balance is not None and balance < price:
            # Refund idempotency key — insufficient funds is not a successful op
            if idempotency_key:
                _used_idempotency_keys.pop(idempotency_key, None)
            return jsonify({"ok": False, "error": f"Saldo insuficiente ({balance} pts, necessário {price} pts)"}), 402

    order, error = _create_order(str(steam_id), item_type, item_id, amount)
    if error:
        if idempotency_key:
            _used_idempotency_keys.pop(idempotency_key, None)
        return jsonify({"ok": False, "error": error}), 400
    assert order is not None

    # Deduz pontos do jogador após pedido criado com sucesso
    if price > 0:
        try:
            db = _SessionLocal()
            db.execute(
                text("UPDATE players SET points = GREATEST(0, points - :price) WHERE steam_id = :sid"),
                {"price": price, "sid": str(steam_id)},
            )
            db.commit()
            db.close()
        except Exception as _pts_err:
            _log_error("debit_points", steam_id=str(steam_id), price=price, error=str(_pts_err))

    result = _process_order_delivery(order.order_id)
    result["order_id"] = order.order_id
    result["new_balance"] = _get_player_points(str(steam_id))
    _log("purchase_ok", steam_id=str(steam_id), item_id=item_id,
         order_id=order.order_id, idempotency_key=idempotency_key or "none")
    return jsonify(result), 200 if result.get("ok") else 500


@app.route("/api/player/points", methods=["GET"])
@login_required
def player_points():
    steam_id = str(_steam_id_from_session())
    balance = _get_player_points(steam_id)
    return jsonify({"ok": True, "steam_id": steam_id, "points": balance})


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
        balance = _get_player_points(steam_id)
        return jsonify({
            "ok": True,
            "steam_id": steam_id,
            "points": balance,
            "stats": {
                "total_orders": total,
                "delivered": delivered,
                "pending": pending,
                "contested": contested,
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
    body = request.get_json(force=True)
    reason = str(body.get("reason", "")).strip()
    if not reason:
        return jsonify({"ok": False, "error": "Motivo é obrigatório"}), 400

    db = _SessionLocal()
    try:
        order = db.query(Order).filter(Order.order_id == order_id, Order.steam_id == steam_id).first()
        if not order:
            return jsonify({"ok": False, "error": "Pedido não encontrado"}), 404

        order.contested = True
        order.status = "CONTESTADO"
        order.updated_at = _now()
        db.add(Dispute(order_id=order.order_id, steam_id=steam_id, reason=reason, status="ABERTO", created_at=_now()))
        db.commit()
        _log("order_contested", order_id=order_id, steam_id=steam_id)
        return jsonify({"ok": True, "status": order.status})
    except Exception as exc:
        _log_error("player_contest", order_id=order_id, steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": f"Erro ao contestar pedido: {exc}"}), 500
    finally:
        db.close()


@app.route("/api/player/orders/<order_id>/rebuy", methods=["POST"])
@login_required
def player_rebuy(order_id: str):
    if (err := _require_db()) is not None:
        return err
    steam_id = str(_steam_id_from_session())
    db = _SessionLocal()
    new_order_id: str | None = None
    try:
        original = db.query(Order).filter(Order.order_id == order_id, Order.steam_id == steam_id).first()
        if not original:
            return jsonify({"ok": False, "error": "Pedido original não encontrado"}), 404

        new_order = Order(
            order_id=str(uuid.uuid4()),
            steam_id=steam_id,
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
        db.add(Rebuy(steam_id=steam_id, original_order_id=original.order_id, new_order_id=new_order.order_id, created_at=_now()))

        original.status = "REEMITIDO"
        original.updated_at = _now()

        db.commit()
        db.refresh(new_order)
        new_order_id = new_order.order_id
        _log("order_rebuy", original_order_id=order_id, new_order_id=new_order_id, steam_id=steam_id)
    except Exception as exc:
        _log_error("player_rebuy", order_id=order_id, steam_id=steam_id, error=str(exc))
        return jsonify({"ok": False, "error": f"Erro ao recomprar pedido: {exc}"}), 500
    finally:
        db.close()

    if not new_order_id:
        return jsonify({"ok": False, "error": "Falha ao criar recompra"}), 500

    result = _process_order_delivery(new_order_id)
    result["order_id"] = new_order_id
    return jsonify(result), 200 if result.get("ok") else 500


# ── Admin order routes ────────────────────────────────────────────────────────

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


@app.route("/api/admin/orders/<order_id>/reprocess", methods=["POST"])
@admin_required
def admin_reprocess_order(order_id: str):
    if (err := _require_db()) is not None:
        return err
    force_rcon = request.args.get("force_rcon", "").lower() in ("1", "true", "yes")
    db = _SessionLocal()
    try:
        order = db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            return jsonify({"ok": False, "error": "Pedido não encontrado"}), 404
        if order.status == "ENTREGUE":
            return jsonify({"ok": False, "error": "Pedido já entregue"}), 400
        order.status = "PENDENTE"
        order.updated_at = _now()
        db.commit()
    finally:
        db.close()

    _log("admin_reprocess", order_id=order_id, admin=_steam_id_from_session(), force_rcon=force_rcon)
    result = _process_order_delivery(order_id, force_rcon=force_rcon)
    return jsonify(result), 200 if result.get("ok") else 500


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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5177))
    log.info("ArkShop Web Manager rodando em http://127.0.0.1:%d", port)
    app.run(host="0.0.0.0", port=port, debug=False)
