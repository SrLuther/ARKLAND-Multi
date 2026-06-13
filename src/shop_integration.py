"""Integração loja central ↔ apps cliente ↔ plugins CustomShop (multi-servidor / LAN)."""
from __future__ import annotations

import json
import re
import shutil
import socket
import sys
import urllib.error
import urllib.request
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .asm_engine.asm_config_manager import AsmConfigManager
    from .config_manager import ConfigManager, ShopGlobalConfig
    from .server_config import ServerConfig

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CATALOG = _PROJECT_ROOT / "plugin" / "CustomShop" / "configs" / "config.json"
_PLUGIN_INFO = _PROJECT_ROOT / "plugin" / "CustomShop" / "configs" / "PluginInfo.json"
_DEV_BIN_DIR = _PROJECT_ROOT / "plugin" / "CustomShop" / "bin"
_ARKSHOP_WEB_DIR = _PROJECT_ROOT / "plugin" / "arkshop_web"
_SETTINGS_FILE = _ARKSHOP_WEB_DIR / "settings.json"
_SERVERS_FILE = _ARKSHOP_WEB_DIR / "servers.json"
_CUSTOMSHOP_DLLS = ("CustomShop.dll", "libmariadb.dll", "z.dll")


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


def customshop_plugin_dir(install_dir: str) -> Path:
    return (
        Path(install_dir)
        / "ShooterGame"
        / "Binaries"
        / "Win64"
        / "ArkApi"
        / "Plugins"
        / "CustomShop"
    )


def default_customshop_path(install_dir: str) -> str:
    if not install_dir or not install_dir.strip():
        return ""
    return str(customshop_plugin_dir(install_dir) / "config.json")


def bundled_customshop_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "plugins"  # type: ignore[attr-defined]
    return _DEV_BIN_DIR


def bundled_customshop_files() -> Dict[str, Path]:
    root = bundled_customshop_root()
    found: Dict[str, Path] = {}
    for name in _CUSTOMSHOP_DLLS:
        p = root / name
        if p.is_file():
            found[name] = p
    return found


def is_customshop_installed(install_dir: str) -> bool:
    if not install_dir or not install_dir.strip():
        return False
    return (customshop_plugin_dir(install_dir) / "CustomShop.dll").is_file()


def _default_config_template() -> Path:
    if _DEFAULT_CATALOG.is_file():
        return _DEFAULT_CATALOG
    fallback = _DEV_BIN_DIR / "config.json"
    return fallback if fallback.is_file() else _DEFAULT_CATALOG


def install_customshop_to_server(
    install_dir: str,
    *,
    overwrite_dlls: bool = True,
) -> Tuple[List[str], List[str]]:
    """Copia DLLs embutidas + PluginInfo/config padrão. Retorna (copiados, avisos/erros)."""
    ok: List[str] = []
    notes: List[str] = []

    if not install_dir or not install_dir.strip():
        return ok, ["install_dir vazio"]

    root = Path(install_dir)
    if not root.is_dir():
        return ok, [f"pasta não encontrada: {install_dir}"]

    bundled = bundled_customshop_files()
    if "CustomShop.dll" not in bundled:
        return ok, ["CustomShop.dll não encontrado no bundle do app — reinstale o ARKLAND Multi"]

    dest = customshop_plugin_dir(install_dir)
    dest.mkdir(parents=True, exist_ok=True)

    for name, src in bundled.items():
        target = dest / name
        if target.is_file() and not overwrite_dlls:
            ok.append(f"{name} (já existia)")
            continue
        shutil.copy2(src, target)
        ok.append(name)

    for optional in ("libmariadb.dll", "z.dll"):
        if optional not in bundled:
            notes.append(f"{optional} ausente no bundle — MySQL pode falhar até copiar manualmente")

    if _PLUGIN_INFO.is_file():
        info_dest = dest / "PluginInfo.json"
        if not info_dest.is_file() or overwrite_dlls:
            shutil.copy2(_PLUGIN_INFO, info_dest)
            ok.append("PluginInfo.json")

    cfg_dest = dest / "config.json"
    if not cfg_dest.is_file():
        template = _default_config_template()
        if template.is_file():
            shutil.copy2(template, cfg_dest)
            ok.append("config.json (padrão)")
        else:
            notes.append("config.json padrão não encontrado no app")

    return ok, notes


def iter_shop_servers(
    cm: "ConfigManager",
    asm_cm: Optional["AsmConfigManager"] = None,
) -> List[Tuple[str, Any]]:
    """Lista (kind, server) — kind é 'classic' ou 'tek'."""
    out: List[Tuple[str, Any]] = []
    for srv in cm.servers:
        out.append(("classic", srv))
    if asm_cm is not None:
        for srv in asm_cm.servers:
            out.append(("tek", srv))
    return out


def _server_rcon_entry(srv: Any, shop: "ShopGlobalConfig") -> Dict[str, Any]:
    sid = (getattr(srv, "shop_server_id", "") or "").strip() or slugify_server_id(
        getattr(srv, "name", ""), getattr(srv, "id", ""),
    )
    host = (
        getattr(srv, "server_ip", "") or getattr(srv, "public_ip", "") or "127.0.0.1"
    )
    rcon_pass = (
        getattr(srv, "rcon_password", "") or getattr(srv, "admin_password", "") or ""
    )
    return {
        "server_id": sid,
        "label": getattr(srv, "name", "") or sid,
        "rcon_host": host,
        "rcon_port": int(getattr(srv, "rcon_port", None) or 27020),
        "rcon_password": rcon_pass,
        "delivery_mode": shop.delivery_mode or "plugin",
        "machine_label": shop.machine_label or "",
    }


def install_customshop_all(
    cm: "ConfigManager",
    asm_cm: Optional["AsmConfigManager"] = None,
    *,
    overwrite_dlls: bool = True,
) -> Tuple[List[str], List[str]]:
    """Instala CustomShop em todos os servidores. Retorna (sucessos, erros)."""
    ok: List[str] = []
    errors: List[str] = []
    classic_dirty = False
    tek_dirty = False

    for kind, srv in iter_shop_servers(cm, asm_cm):
        name = getattr(srv, "name", "") or getattr(srv, "id", "")
        if not getattr(srv, "install_dir", ""):
            errors.append(f"{name}: sem install_dir")
            continue
        copied, notes = install_customshop_to_server(
            srv.install_dir, overwrite_dlls=overwrite_dlls,
        )
        if not copied and notes:
            errors.append(f"{name}: {'; '.join(notes)}")
            continue
        path_str = default_customshop_path(srv.install_dir)
        if not getattr(srv, "customshop_config_path", ""):
            srv.customshop_config_path = path_str
            if kind == "tek":
                tek_dirty = True
            else:
                classic_dirty = True
        if not getattr(srv, "shop_server_id", ""):
            srv.shop_server_id = slugify_server_id(name, getattr(srv, "id", ""))
            if kind == "tek":
                tek_dirty = True
            else:
                classic_dirty = True
        detail = ", ".join(copied[:4])
        if len(copied) > 4:
            detail += f" (+{len(copied) - 4})"
        warn = f" — {'; '.join(notes)}" if notes else ""
        ok.append(f"{name}: {detail}{warn}")

    if classic_dirty:
        cm.save_servers()
    if tek_dirty and asm_cm is not None:
        asm_cm.save()
    return ok, errors


def resolve_central_url(shop: "ShopGlobalConfig") -> str:
    override = (shop.central_url or "").strip().rstrip("/")
    if shop.mode == "client":
        return override
    if override:
        return override
    host = (shop.host_ip or "").strip() or get_local_ip()
    port = max(1, int(shop.port or 5177))
    return f"http://{host}:{port}"


def _db_manager_prefs() -> dict:
    """Lê as credenciais salvas pelo DB Manager como fallback."""
    try:
        import os, json as _json
        appdata = os.environ.get("APPDATA", "")
        prefs_file = Path(appdata) / "ARKLAND-ServerManager" / "db_server_prefs.json"
        if prefs_file.exists():
            raw = _json.loads(prefs_file.read_text(encoding="utf-8"))
            return raw.get("shop_db") or raw.get("last_connection", {})
    except Exception:
        pass
    return {}


def build_orders_database_url(shop: "ShopGlobalConfig") -> str:
    explicit = (shop.orders_db_url or "").strip()
    if explicit:
        return explicit
    host     = (shop.orders_db_host or "").strip()
    port     = int(shop.orders_db_port or 3306)
    name     = (shop.orders_db_name or "").strip()
    user     = (shop.orders_db_user or "").strip()
    password = (shop.orders_db_password or "").strip()

    # Fallback: usa credenciais do DB Manager se os campos da loja estiverem vazios
    if not user:
        prefs = _db_manager_prefs()
        host     = host     or prefs.get("host", "127.0.0.1")
        port     = port     or int(prefs.get("port", 3306))
        name     = name     or prefs.get("database", "arkland_shop")
        user     = prefs.get("user", "")
        password = password or prefs.get("password", "")

    name = name or "arkland_shop"
    if user:
        import urllib.parse
        u = urllib.parse.quote_plus(user)
        p = urllib.parse.quote_plus(password)
        return f"mysql+pymysql://{u}:{p}@{host}:{port}/{name}?charset=utf8mb4"
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


def register_arkshop_servers(
    cm: "ConfigManager",
    shop: "ShopGlobalConfig",
    asm_cm: Optional["AsmConfigManager"] = None,
) -> int:
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
    for _kind, srv in iter_shop_servers(cm, asm_cm):
        entry = _server_rcon_entry(srv, shop)
        by_id[entry["server_id"]] = entry
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
    asm_cm: Optional["AsmConfigManager"] = None,
) -> Tuple[List[str], List[str]]:
    """Retorna (sucessos, erros)."""
    central = resolve_central_url(shop)
    api_key = shop.api_key or ""
    db_settings = catalog.get("Database", {})
    ok: List[str] = []
    errors: List[str] = []
    classic_dirty = False
    tek_dirty = False

    for kind, srv in iter_shop_servers(cm, asm_cm):
        path_str = (getattr(srv, "customshop_config_path", "") or "").strip()
        if not path_str:
            path_str = default_customshop_path(getattr(srv, "install_dir", ""))
        if not path_str:
            errors.append(f"{getattr(srv, 'name', '')}: sem install_dir / caminho do plugin")
            continue
        plugin_path = Path(path_str)
        try:
            sync_plugin_at_path(catalog, plugin_path, central, api_key, db_settings)
            sid = (getattr(srv, "shop_server_id", "") or "").strip() or slugify_server_id(
                getattr(srv, "name", ""), getattr(srv, "id", ""),
            )
            if not getattr(srv, "shop_server_id", ""):
                srv.shop_server_id = sid
                if kind == "tek":
                    tek_dirty = True
                else:
                    classic_dirty = True
            if not getattr(srv, "customshop_config_path", ""):
                srv.customshop_config_path = path_str
                if kind == "tek":
                    tek_dirty = True
                else:
                    classic_dirty = True
            ok.append(f"{getattr(srv, 'name', '')} → {plugin_path}")
        except Exception as exc:
            errors.append(f"{getattr(srv, 'name', '')}: {exc}")

    if classic_dirty:
        cm.save_servers()
    if tek_dirty and asm_cm is not None:
        asm_cm.save()
    sync_arkshop_web_settings(shop, catalog_path, central)
    register_arkshop_servers(cm, shop, asm_cm=asm_cm)
    return ok, errors


def default_catalog_path(shop: "ShopGlobalConfig") -> Path:
    raw = (shop.catalog_config_path or "").strip()
    if raw:
        return Path(raw)
    return _DEFAULT_CATALOG
