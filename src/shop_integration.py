"""Integração loja central ↔ apps cliente ↔ plugins CustomShop (multi-servidor / LAN)."""
from __future__ import annotations

import json
import re
import shutil
import socket
import subprocess
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


def webstore_data_dir() -> Path:
    """Diretório gravável da Web Store (dev: plugin/; instalado: APPDATA)."""
    import os

    if getattr(sys, "frozen", False):
        p = Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager" / "arkshop_web"
    else:
        p = _ARKSHOP_WEB_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def resolve_webstore_executable() -> Optional[Path]:
    if not getattr(sys, "frozen", False):
        return None
    exe = Path(sys.executable).resolve().parent / "ARKLAND-WebStore.exe"
    return exe if exe.is_file() else None


def build_webstore_launch(shop: "ShopGlobalConfig") -> Tuple[List[str], str, Path]:
    """Retorna (comando, cwd, caminho do log)."""
    data = webstore_data_dir()
    log_path = data / "webstore.log"
    ws_exe = resolve_webstore_executable()
    if ws_exe is not None:
        return [str(ws_exe)], str(ws_exe.parent), log_path
    app_py = _ARKSHOP_WEB_DIR / "app.py"
    return [sys.executable, str(app_py)], str(_ARKSHOP_WEB_DIR), log_path


def read_webstore_log_tail(max_lines: int = 6) -> str:
    log_path = webstore_data_dir() / "webstore.log"
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-max_lines:]).strip()
    except Exception:
        return ""


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def fetch_public_ip(timeout: int = 6) -> Tuple[bool, str]:
    """Consulta IP público via api.ipify.org. Retorna (ok, ip_ou_erro)."""
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ARKLAND/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ip = resp.read().decode().strip()
                if ip and not ip.startswith("{"):
                    return True, ip
        except Exception:
            continue
    return False, "Não foi possível detectar o IP público."


def resolve_central_url(shop: "ShopGlobalConfig") -> str:
    override = (shop.central_url or "").strip().rstrip("/")
    if shop.mode == "client":
        return override
    if override:
        return override
    host = (shop.host_ip or "").strip() or get_local_ip()
    port = max(1, int(shop.port or 5177))
    return f"http://{host}:{port}"


def resolve_public_shop_url(shop: "ShopGlobalConfig") -> str:
    """URL da loja para acesso pela internet (IP público + porta)."""
    pub = (shop.public_ip or "").strip()
    if not pub:
        return ""
    port = max(1, int(shop.port or 5177))
    return f"http://{pub}:{port}"


def shop_access_urls(shop: "ShopGlobalConfig") -> dict[str, str]:
    """Retorna URLs de acesso LAN e internet para exibição na UI."""
    port = max(1, int(shop.port or 5177))
    lan_ip = (shop.host_ip or "").strip() or get_local_ip()
    pub_ip = (shop.public_ip or "").strip()
    return {
        "lan_ip": lan_ip,
        "public_ip": pub_ip,
        "lan_url": f"http://{lan_ip}:{port}",
        "public_url": f"http://{pub_ip}:{port}" if pub_ip else "",
        "central": resolve_central_url(shop),
    }


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


def server_win64_dir(install_dir: str) -> Path:
    return Path(install_dir) / "ShooterGame" / "Binaries" / "Win64"


_WIN64_RUNTIME_DLLS = ("libmariadb.dll", "z.dll")


def default_customshop_path(install_dir: str) -> str:
    if not install_dir or not install_dir.strip():
        return ""
    return str(customshop_plugin_dir(install_dir) / "config.json")


def bundled_customshop_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "plugins"  # type: ignore[attr-defined]
    return _DEV_BIN_DIR


def bundled_customshop_files() -> Dict[str, Path]:
    """Localiza DLLs do CustomShop no bundle PyInstaller, bin/ do projeto ou MariaDB portable."""
    candidates: list[Path] = [bundled_customshop_root(), _DEV_BIN_DIR]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "plugins")

    found: Dict[str, Path] = {}
    for name in _CUSTOMSHOP_DLLS:
        for root in candidates:
            p = root / name
            if p.is_file():
                found[name] = p
                break

    if "libmariadb.dll" not in found:
        try:
            from .pages.db_local_server import DbLocalServer

            mariadb_bin = DbLocalServer().mysqld_exe.parent
            lm = mariadb_bin / "libmariadb.dll"
            if lm.is_file():
                found["libmariadb.dll"] = lm
        except Exception:
            pass

    return found


def customshop_install_diagnostics(install_dir: str) -> list[str]:
    """Lista problemas que causam Error 126 ao carregar CustomShop.dll."""
    issues: list[str] = []
    if not install_dir or not install_dir.strip():
        return ["install_dir vazio"]

    plugin = customshop_plugin_dir(install_dir)
    win64 = server_win64_dir(install_dir)

    if not (plugin / "CustomShop.dll").is_file():
        issues.append("CustomShop.dll ausente em ArkApi/Plugins/CustomShop/")

    for dll in _WIN64_RUNTIME_DLLS:
        in_plugin = (plugin / dll).is_file()
        in_win64 = (win64 / dll).is_file()
        if not in_plugin and not in_win64:
            issues.append(
                f"{dll} ausente — copie para Plugins/CustomShop/ e Win64/ (causa Error 126)"
            )
        elif not in_win64:
            issues.append(
                f"{dll} não está em Win64/ — o ARK pode falhar ao carregar o plugin (Error 126)"
            )
    return issues


def is_customshop_installed(install_dir: str) -> bool:
    if not install_dir or not install_dir.strip():
        return False
    plugin = customshop_plugin_dir(install_dir)
    if not (plugin / "CustomShop.dll").is_file():
        return False
    return not customshop_install_diagnostics(install_dir)


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
    win64 = server_win64_dir(install_dir)
    win64.mkdir(parents=True, exist_ok=True)

    for name, src in bundled.items():
        target = dest / name
        if target.is_file() and not overwrite_dlls:
            ok.append(f"{name} (já existia)")
        else:
            shutil.copy2(src, target)
            ok.append(f"{name} → Plugins/CustomShop/")
        if name in _WIN64_RUNTIME_DLLS:
            w64_target = win64 / name
            if overwrite_dlls or not w64_target.is_file():
                shutil.copy2(src, w64_target)
                ok.append(f"{name} → Win64/")

    for required in _WIN64_RUNTIME_DLLS:
        if required not in bundled:
            notes.append(
                f"{required} ausente no bundle — reinstale o ARKLAND ou copie manualmente "
                f"para Plugins/CustomShop/ e Win64/ (Error 126)"
            )

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
    return f"sqlite:///{webstore_data_dir() / 'orders.db'}"


def get_shop_subprocess_env(shop: "ShopGlobalConfig") -> Dict[str, str]:
    import os

    env = dict(os.environ)
    env["PORT"] = str(max(1, int(shop.port or 5177)))
    env["ARKSHOP_DATA_DIR"] = str(webstore_data_dir())
    if shop.api_key:
        env["ARKSHOP_API_KEY"] = shop.api_key
    db_url = build_orders_database_url(shop)
    if db_url:
        env["ARKSHOP_DATABASE_URL"] = db_url
    catalog = default_catalog_path(shop)
    if catalog.is_file():
        env["ARKSHOP_CONFIG_PATH"] = str(catalog)
    return env


def test_shop_connection(url: str, api_key: str = "") -> Tuple[bool, str]:
    base = url.strip().rstrip("/")
    if not base:
        return False, "URL vazia"
    if not base.startswith(("http://", "https://")):
        base = f"http://{base}"
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


_WEBSTORE_FW_PREFIX = "ARKLAND-WebStore-"


def check_webstore_firewall_rule(port: int) -> bool:
    try:
        rule = f"{_WEBSTORE_FW_PREFIX}{port}"
        cmd = f'netsh advfirewall firewall show rule name="{rule}"'
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=6,
        )
        return result.returncode == 0
    except Exception:
        return False


def create_webstore_firewall_rule(port: int) -> Tuple[bool, str]:
    """Cria regra de entrada TCP para a Web Store (perfil Any)."""
    from .pages.db_local_server import DbLocalServer

    port = max(1, int(port or 5177))
    rule = f"{_WEBSTORE_FW_PREFIX}{port}"
    if check_webstore_firewall_rule(port):
        return True, f"Regra já existe para porta {port}."

    netsh_cmd = (
        f'netsh advfirewall firewall delete rule name="{rule}" & '
        f'netsh advfirewall firewall add rule name="{rule}" '
        f"protocol=TCP dir=in localport={port} action=allow profile=any "
        f'description="ARKLAND Web Store HTTP"'
    )

    if DbLocalServer.is_admin():
        try:
            result = subprocess.run(
                netsh_cmd, shell=True, capture_output=True, text=True, timeout=10,
            )
            if check_webstore_firewall_rule(port):
                return True, f"Porta {port} liberada no firewall."
            out = (result.stdout + result.stderr).strip()
            return False, out or f"Código {result.returncode}"
        except Exception as exc:
            return False, str(exc)

    try:
        import ctypes
        import tempfile
        import time as _time

        bat = tempfile.NamedTemporaryFile(
            suffix=".bat", mode="w", delete=False, encoding="utf-8",
        )
        bat.write(f"@echo off\n{netsh_cmd}\n")
        bat.close()
        try:
            ret = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", "cmd.exe", f'/c "{bat.name}"', None, 0,
            )
            if ret <= 32:
                return False, "UAC cancelado ou acesso negado."
            for _ in range(16):
                _time.sleep(0.5)
                if check_webstore_firewall_rule(port):
                    return True, f"Porta {port} liberada no firewall."
            return False, "Timeout aguardando criação da regra."
        finally:
            try:
                import os as _os
                _os.unlink(bat.name)
            except Exception:
                pass
    except Exception as exc:
        return False, str(exc)


def diagnose_webstore_access(shop: "ShopGlobalConfig") -> Tuple[bool, str, bool]:
    """Testa localhost e IP LAN. Retorna (ok_lan, mensagem, ok_local)."""
    port = max(1, int(shop.port or 5177))
    host = (shop.host_ip or "").strip() or get_local_ip()
    ok_local, msg_local = test_shop_connection(f"http://127.0.0.1:{port}")
    ok_lan, msg_lan = test_shop_connection(f"http://{host}:{port}")
    if ok_lan:
        return True, "Loja respondendo (LAN)", ok_local
    if ok_local:
        fw = "sim" if check_webstore_firewall_rule(port) else "não"
        return False, (
            f"Loja OK em localhost, mas {host}:{port} não responde na LAN "
            f"(firewall Windows: regra {fw})"
        ), ok_local
    return False, msg_lan or msg_local or "Sem resposta", ok_local


def load_plugin_config(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_plugin_config(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def build_plugin_database_settings(shop: "ShopGlobalConfig") -> Dict[str, Any]:
    """Monta bloco Database do config.json do plugin a partir da loja / DB Manager."""
    host = (shop.orders_db_host or "").strip() or "127.0.0.1"
    port = int(shop.orders_db_port or 3306)
    name = (shop.orders_db_name or "").strip() or "arkland_shop"
    user = (shop.orders_db_user or "").strip()
    password = (shop.orders_db_password or "").strip()

    if not user:
        prefs = _db_manager_prefs()
        host = host or prefs.get("host", "127.0.0.1")
        port = port or int(prefs.get("port", 3306))
        name = name or prefs.get("database", "arkland_shop")
        user = prefs.get("user", "arkland")
        password = password or prefs.get("password", "")

    return {
        "Host": host,
        "Port": port,
        "User": user,
        "Password": password,
        "Database": name,
        "Ssl": False,
    }


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
    settings_path = webstore_data_dir() / "settings.json"
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
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

    settings_path = webstore_data_dir() / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def register_arkshop_servers(
    cm: "ConfigManager",
    shop: "ShopGlobalConfig",
    asm_cm: Optional["AsmConfigManager"] = None,
) -> int:
    servers_path = webstore_data_dir() / "servers.json"
    servers = []
    if servers_path.exists():
        try:
            raw = json.loads(servers_path.read_text(encoding="utf-8"))
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

    servers_path = webstore_data_dir() / "servers.json"
    servers_path.parent.mkdir(parents=True, exist_ok=True)
    servers_path.write_text(
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
    db_settings = build_plugin_database_settings(shop)
    catalog_db = catalog.get("Database", {})
    if catalog_db:
        db_settings = {**catalog_db, **db_settings}
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
