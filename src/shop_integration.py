"""Integração loja central ↔ apps cliente ↔ plugins CustomShop (multi-servidor / LAN)."""
from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .config_manager import ConfigManager, ShopGlobalConfig
    from .server_config import ServerConfig

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CATALOG = _PROJECT_ROOT / "plugin" / "CustomShop" / "configs" / "config.json"
_ARKSHOP_WEB_DIR = _PROJECT_ROOT / "plugin" / "arkshop_web"
_SETTINGS_FILE = _ARKSHOP_WEB_DIR / "settings.json"
_SERVERS_FILE = _ARKSHOP_WEB_DIR / "servers.json"


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def slugify_server_id(name: str, srv_id: str) -> str:
    base = (name or srv_id or "server").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", base).strip("_")
    return slug[:48] or srv_id[:8]


def default_customshop_path(install_dir: str) -> str:
    if not install_dir or not install_dir.strip():
        return ""
    p = (
        Path(install_dir)
        / "ShooterGame"
        / "Binaries"
        / "Win64"
        / "ArkApi"
        / "Plugins"
        / "CustomShop"
        / "config.json"
    )
    return str(p)


def resolve_central_url(shop: "ShopGlobalConfig") -> str:
    override = (shop.central_url or "").strip().rstrip("/")
    if shop.mode == "client":
        return override
    if override:
        return override
    host = (shop.host_ip or "").strip() or get_local_ip()
    port = max(1, int(shop.port or 5177))
    return f"http://{host}:{port}"


def build_orders_database_url(shop: "ShopGlobalConfig") -> str:
    explicit = (shop.orders_db_url or "").strip()
    if explicit:
        return explicit
    host = (shop.orders_db_host or "127.0.0.1").strip()
    port = int(shop.orders_db_port or 3306)
    name = (shop.orders_db_name or "arkshop").strip()
    user = (shop.orders_db_user or "").strip()
    password = (shop.orders_db_password or "").strip()
    if user:
        auth = f"{user}:{password}@" if password else f"{user}@"
        return f"mysql+pymysql://{auth}{host}:{port}/{name}"
    return f"sqlite:///{_ARKSHOP_WEB_DIR / 'orders.db'}"


def get_shop_subprocess_env(shop: "ShopGlobalConfig") -> Dict[str, str]:
    import os

    env = dict(os.environ)
    env["PORT"] = str(max(1, int(shop.port or 5177)))
    if shop.api_key:
        env["ARKSHOP_API_KEY"] = shop.api_key
    db_url = build_orders_database_url(shop)
    if db_url:
        env["ARKSHOP_DATABASE_URL"] = db_url
    return env


def test_shop_connection(url: str, api_key: str = "") -> Tuple[bool, str]:
    base = url.strip().rstrip("/")
    if not base:
        return False, "URL vazia"
    try:
        req = urllib.request.Request(f"{base}/api/auth/me", method="GET")
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                return True, "Loja respondendo"
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403, 404, 405):
            return True, f"Loja online (HTTP {exc.code})"
        return False, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)
    return False, "Sem resposta"


def load_plugin_config(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_plugin_config(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def merge_plugin_config(
    catalog: Dict[str, Any],
    central_url: str,
    api_key: str,
    db_settings: Dict[str, Any],
) -> Dict[str, Any]:
    out = deepcopy(catalog)
    settings = out.setdefault("Settings", {})
    settings["WebsiteUrl"] = central_url
    settings["WebApiUrl"] = central_url
    settings["WebApiKey"] = api_key
    if db_settings:
        out["Database"] = deepcopy(db_settings)
    return out


def sync_plugin_at_path(
    catalog: Dict[str, Any],
    plugin_path: Path,
    central_url: str,
    api_key: str,
    db_settings: Dict[str, Any],
) -> None:
    existing = load_plugin_config(plugin_path) if plugin_path.exists() else {}
    merged = merge_plugin_config(catalog, central_url, api_key, db_settings)
    if existing.get("Settings"):
        for k, v in existing["Settings"].items():
            if k not in ("WebsiteUrl", "WebApiUrl", "WebApiKey"):
                merged["Settings"].setdefault(k, v)
    save_plugin_config(plugin_path, merged)


def sync_arkshop_web_settings(
    shop: "ShopGlobalConfig",
    catalog_path: Path,
    central_url: str,
) -> None:
    data: Dict[str, Any] = {}
    if _SETTINGS_FILE.exists():
        try:
            data = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    data["port"] = int(shop.port or 5177)
    data["delivery_mode"] = shop.delivery_mode or "plugin"
    data["config_path"] = str(catalog_path)
    data["central_url"] = central_url
    data["shop_mode"] = shop.mode
    data["machine_label"] = shop.machine_label or ""
    if shop.api_key:
        data["api_key"] = shop.api_key

    db_url = build_orders_database_url(shop)
    if db_url.startswith("sqlite"):
        data["database_url"] = db_url
    else:
        data["database_url"] = db_url
        data["db_host"] = shop.orders_db_host
        data["db_port"] = int(shop.orders_db_port or 3306)
        data["db_name"] = shop.orders_db_name
        data["db_user"] = shop.orders_db_user
        if shop.orders_db_password:
            data["db_password"] = shop.orders_db_password

    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def register_arkshop_servers(cm: "ConfigManager", shop: "ShopGlobalConfig") -> int:
    servers = []
    if _SERVERS_FILE.exists():
        try:
            raw = json.loads(_SERVERS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                servers = raw
        except Exception:
            servers = []

    by_id = {str(s.get("server_id", "")): s for s in servers if isinstance(s, dict)}
    count = 0
    for srv in cm.servers:
        sid = (srv.shop_server_id or "").strip() or slugify_server_id(srv.name, srv.id)
        entry = {
            "server_id": sid,
            "label": srv.name or sid,
            "rcon_host": srv.server_ip or srv.public_ip or "127.0.0.1",
            "rcon_port": int(srv.rcon_port or 27020),
            "rcon_password": srv.rcon_password or "",
            "delivery_mode": shop.delivery_mode or "plugin",
            "machine_label": shop.machine_label or "",
        }
        by_id[sid] = entry
        count += 1

    _SERVERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SERVERS_FILE.write_text(
        json.dumps(list(by_id.values()), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return count


def sync_all_plugins(
    cm: "ConfigManager",
    shop: "ShopGlobalConfig",
    catalog: Dict[str, Any],
    catalog_path: Path,
) -> Tuple[List[str], List[str]]:
    """Retorna (sucessos, erros)."""
    central = resolve_central_url(shop)
    api_key = shop.api_key or ""
    db_settings = catalog.get("Database", {})
    ok: List[str] = []
    errors: List[str] = []

    for srv in cm.servers:
        path_str = (srv.customshop_config_path or "").strip()
        if not path_str:
            path_str = default_customshop_path(srv.install_dir)
        if not path_str:
            errors.append(f"{srv.name}: sem install_dir / caminho do plugin")
            continue
        plugin_path = Path(path_str)
        try:
            sync_plugin_at_path(catalog, plugin_path, central, api_key, db_settings)
            sid = (srv.shop_server_id or "").strip() or slugify_server_id(srv.name, srv.id)
            if not srv.shop_server_id:
                srv.shop_server_id = sid
            if not srv.customshop_config_path:
                srv.customshop_config_path = path_str
            ok.append(f"{srv.name} → {plugin_path}")
        except Exception as exc:
            errors.append(f"{srv.name}: {exc}")

    if ok:
        cm.save_servers()
    sync_arkshop_web_settings(shop, catalog_path, central)
    register_arkshop_servers(cm, shop)
    return ok, errors


def default_catalog_path(shop: "ShopGlobalConfig") -> Path:
    raw = (shop.catalog_config_path or "").strip()
    if raw:
        return Path(raw)
    return _DEFAULT_CATALOG
