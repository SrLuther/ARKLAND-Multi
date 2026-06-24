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
_PERM_CONFIG_TEMPLATE = _PROJECT_ROOT / "plugin" / "Permissions" / "configs" / "config.json"
_PERM_DB_NAME = "ark_permission"
_PERM_PASSWORD_PLACEHOLDER = "SUA_SENHA_AQUI"
_DEV_BIN_DIR = _PROJECT_ROOT / "plugin" / "CustomShop" / "bin"
DEFAULT_SHOP_PUBLIC_URL = "https://arkland.com.br"
DEFAULT_SHOP_PORT = 27199
DEFAULT_REMOTE_SHOP_HOST = "192.168.15.51"
DEFAULT_REMOTE_SHOP_PUBLIC_IP = "179.185.19.88"
_ARKSHOP_WEB_DIR = _PROJECT_ROOT / "plugin" / "arkshop_web"
_SETTINGS_FILE = _ARKSHOP_WEB_DIR / "settings.json"
_SERVERS_FILE = _ARKSHOP_WEB_DIR / "servers.json"
_CUSTOMSHOP_DLLS = ("CustomShop.dll", "libmariadb.dll", "z.dll")


def webstore_data_dir() -> Path:
    """Diretório gravável da Web Store (dev: plugin/; instalado: APPDATA ou ambiente)."""
    import os

    from .arkland_environment import default_webstore_dir, try_load_environment_paths

    if try_load_environment_paths():
        p = default_webstore_dir()
    elif getattr(sys, "frozen", False):
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


def normalize_shop_url(url: str) -> str:
    """Normaliza URL da loja (domínio ou endereço completo)."""
    u = (url or "").strip()
    if not u:
        return ""
    if not re.match(r"^https?://", u, re.I):
        u = f"https://{u}"
    return u.rstrip("/")


def effective_shop_public_url(shop: "ShopGlobalConfig") -> str:
    """Domínio público efetivo da loja (configurado ou padrão arkland.com.br)."""
    return normalize_shop_url(getattr(shop, "public_url", "") or "") or DEFAULT_SHOP_PUBLIC_URL


def resolve_central_url(shop: "ShopGlobalConfig") -> str:
    """URL da loja para sync — domínio remoto; não usa IP desta máquina."""
    override = normalize_shop_url((shop.central_url or "").strip())
    if not override and (shop.central_url or "").strip():
        override = (shop.central_url or "").strip().rstrip("/")
    if shop.mode == "client":
        return override or effective_shop_public_url(shop)
    if override:
        return override
    domain = effective_shop_public_url(shop)
    if domain:
        return domain
    host = (shop.host_ip or "").strip()
    if host:
        port = max(1, int(shop.port or DEFAULT_SHOP_PORT))
        return f"http://{host}:{port}"
    return DEFAULT_SHOP_PUBLIC_URL


def resolve_public_shop_url(shop: "ShopGlobalConfig") -> str:
    """URL pública da loja para jogadores (domínio preferido sobre IP)."""
    domain = normalize_shop_url(getattr(shop, "public_url", "") or "")
    if domain:
        return domain
    pub_ip = (shop.public_ip or "").strip()
    if pub_ip:
        port = max(1, int(shop.port or DEFAULT_SHOP_PORT))
        if port == 80:
            return f"http://{pub_ip}"
        if port == 443:
            return f"https://{pub_ip}"
        return f"http://{pub_ip}:{port}"
    return DEFAULT_SHOP_PUBLIC_URL


def resolve_website_url(shop: "ShopGlobalConfig") -> str:
    """URL exibida ao jogador (/shop, Discord, etc.)."""
    pub = resolve_public_shop_url(shop)
    if pub:
        return pub
    if shop.mode == "client":
        client = normalize_shop_url(shop.central_url or "")
        if client:
            return client
    return resolve_central_url(shop)


def resolve_plugin_api_url(shop: "ShopGlobalConfig") -> str:
    """URL HTTP que o CustomShop.dll usa para a API da web store."""
    domain = effective_shop_public_url(shop)
    if domain:
        return domain
    if shop.mode == "client":
        client = (shop.central_url or "").strip().rstrip("/")
        if client:
            return client
    return resolve_central_url(shop)


def shop_access_urls(shop: "ShopGlobalConfig") -> dict[str, str]:
    """Retorna URLs de acesso para exibição na UI."""
    port = max(1, int(shop.port or DEFAULT_SHOP_PORT))
    lan_ip = (shop.host_ip or "").strip()
    pub_ip = (shop.public_ip or "").strip()
    domain = effective_shop_public_url(shop)
    shop_url = resolve_website_url(shop)
    lan_url = f"http://{lan_ip}:{port}" if lan_ip else ""
    if pub_ip:
        if port in (80, 443):
            remote_public_url = f"{'https' if port == 443 else 'http'}://{pub_ip}"
        else:
            remote_public_url = f"http://{pub_ip}:{port}"
    else:
        remote_public_url = ""
    return {
        "lan_ip": lan_ip,
        "public_ip": pub_ip,
        "lan_url": lan_url,
        "remote_public_url": remote_public_url,
        "public_url": domain,
        "shop_url": shop_url,
        "central": resolve_central_url(shop),
        "plugin_api": resolve_plugin_api_url(shop),
        "remote": shop.mode == "client",
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


def permissions_plugin_dir(install_dir: str) -> Path:
    return (
        Path(install_dir)
        / "ShooterGame"
        / "Binaries"
        / "Win64"
        / "ArkApi"
        / "Plugins"
        / "Permissions"
    )


def default_permissions_config_path(install_dir: str) -> str:
    if not install_dir or not install_dir.strip():
        return ""
    return str(permissions_plugin_dir(install_dir) / "config.json")


def permissions_dll_installed(install_dir: str) -> bool:
    if not install_dir or not install_dir.strip():
        return False
    return (permissions_plugin_dir(install_dir) / "Permissions.dll").is_file()


def _default_permissions_template() -> Path:
    if getattr(sys, "frozen", False):
        bundled = Path(sys._MEIPASS) / "Permissions" / "configs" / "config.json"  # type: ignore[attr-defined]
        if bundled.is_file():
            return bundled
    return _PERM_CONFIG_TEMPLATE if _PERM_CONFIG_TEMPLATE.is_file() else _PERM_CONFIG_TEMPLATE


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
    shop: Optional["ShopGlobalConfig"] = None,
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

    perm_notes = _ensure_permissions_config_on_server(install_dir, shop=shop)
    ok.extend(perm_notes[0])
    notes.extend(perm_notes[1])

    return ok, notes


def build_permissions_config_settings(shop: Optional["ShopGlobalConfig"] = None) -> Dict[str, Any]:
    """Monta credenciais MySQL para Permissions/config.json (sempre ark_permission)."""
    host = "127.0.0.1"
    port = 3306
    user = "arkland"
    password = ""

    if shop is not None:
        host = (shop.orders_db_host or "").strip() or host
        port = int(shop.orders_db_port or port)
        user = (shop.orders_db_user or "").strip() or user

    prefs = _db_manager_prefs()
    host = host or prefs.get("host", "127.0.0.1")
    port = port or int(prefs.get("port", 3306))
    user = user or prefs.get("user", "arkland")
    password = resolve_shop_db_password(shop)

    return {
        "UseMysql": True,
        "MysqlHost": host,
        "MysqlUser": user,
        "MysqlPass": password,
        "MysqlDB": _PERM_DB_NAME,
        "MysqlPort": port,
    }


def merge_permissions_config(
    existing: Dict[str, Any],
    settings: Dict[str, Any],
) -> Dict[str, Any]:
    out = deepcopy(existing) if existing else {}
    for key in ("UseMysql", "MysqlHost", "MysqlUser", "MysqlPass", "MysqlDB", "MysqlPort"):
        if key in settings and settings[key] not in (None, ""):
            out[key] = settings[key]
    out["UseMysql"] = True
    out["MysqlDB"] = _PERM_DB_NAME
    return out


def sync_permissions_at_path(plugin_path: Path, settings: Dict[str, Any]) -> None:
    existing: Dict[str, Any] = {}
    if plugin_path.exists():
        existing = load_plugin_config(plugin_path)
    elif _default_permissions_template().is_file():
        existing = load_plugin_config(_default_permissions_template())
    merged = merge_permissions_config(existing, settings)
    save_plugin_config(plugin_path, merged)


def _ensure_permissions_config_on_server(
    install_dir: str,
    shop: Optional["ShopGlobalConfig"] = None,
) -> Tuple[List[str], List[str]]:
    """Garante Permissions/config.json no servidor. Retorna (ok, notes)."""
    ok: List[str] = []
    notes: List[str] = []
    if not install_dir or not install_dir.strip():
        return ok, ["install_dir vazio (Permissions)"]

    dest = permissions_plugin_dir(install_dir)
    dest.mkdir(parents=True, exist_ok=True)
    cfg_path = dest / "config.json"
    try:
        sync_permissions_at_path(cfg_path, build_permissions_config_settings(shop))
        ok.append(f"Permissions/config.json → {cfg_path}")
    except Exception as exc:
        notes.append(f"Permissions config: {exc}")
    return ok, notes


def collect_groups_from_catalog(catalog: Dict[str, Any]) -> List[str]:
    """Extrai nomes de grupos únicos do catálogo CustomShop."""
    found: set[str] = set()
    for kit in catalog.get("Kits", {}).values():
        if not isinstance(kit, dict):
            continue
        perms = kit.get("Permissions", "")
        if isinstance(perms, list):
            for g in perms:
                g = str(g).strip()
                if g:
                    found.add(g)
        elif perms:
            for token in str(perms).split(","):
                g = token.strip()
                if g:
                    found.add(g)

    for item in (catalog.get("Items") or catalog.get("ShopItems") or {}).values():
        if not isinstance(item, dict):
            continue
        perms = item.get("Permissions", "")
        if isinstance(perms, list):
            for g in perms:
                g = str(g).strip()
                if g:
                    found.add(g)
        elif perms:
            for token in str(perms).split(","):
                g = token.strip()
                if g:
                    found.add(g)

    for lic in ("Gamma", "Beta", "Alfa", "Moderacao", "STAFF"):
        found.add(lic)

    timed = catalog.get("TimedPointsReward", {})
    if isinstance(timed, dict):
        groups = timed.get("Groups", {})
        if isinstance(groups, dict):
            for name in groups:
                g = str(name).strip()
                if g:
                    found.add(g)
    return sorted(found)


def provision_permission_groups_for_servers(
    servers: List[Tuple[str, Any]],
    catalog: Dict[str, Any],
    *,
    server_manager: Any = None,
) -> Tuple[List[str], List[str], List[str]]:
    """Cria grupos via RCON (Permissions.AddGroup). Retorna (ok, erros, ignorados)."""
    from .rcon_client import RconClient

    groups = collect_groups_from_catalog(catalog)
    if not groups:
        return [], [], ["Nenhum grupo definido no catálogo"]

    ok: List[str] = []
    failed: List[str] = []
    skipped: List[str] = []

    for _kind, srv in servers:
        name = getattr(srv, "name", "") or getattr(srv, "id", "") or "Servidor"
        if not getattr(srv, "rcon_enabled", False):
            skipped.append(f"{name}: RCON desativado")
            continue
        rcon_pass = (
            getattr(srv, "rcon_password", "") or getattr(srv, "admin_password", "") or ""
        ).strip()
        if not rcon_pass:
            skipped.append(f"{name}: senha RCON/admin não definida")
            continue

        host = (getattr(srv, "server_ip", "") or "127.0.0.1").strip() or "127.0.0.1"
        port = int(getattr(srv, "rcon_port", None) or 27020)

        if server_manager is not None:
            inst = server_manager.get_instance(getattr(srv, "id", ""))
            if inst is not None and getattr(inst, "status", "") != "running":
                skipped.append(f"{name}: servidor não está em execução")
                continue

        client = RconClient(host, port, rcon_pass)
        try:
            client.connect()
            for group in groups:
                cmd = f"Permissions.AddGroup {group}"
                cmd_ok, result = client.send_command_with_retry(cmd, retries=2)
                if cmd_ok:
                    ok.append(f"{name}: {group}")
                else:
                    failed.append(f"{name}/{group}: {result or 'falha'}")
        except Exception as exc:
            failed.append(f"{name}: {exc}")
        finally:
            try:
                client.disconnect()
            except Exception:
                pass

    return ok, failed, skipped


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


def _arkland_ref(kind: str, srv: Any) -> str:
    return f"{kind}:{getattr(srv, 'id', '')}"


def _resolve_machine_label(shop: "ShopGlobalConfig") -> str:
    raw = (getattr(shop, "machine_label", "") or "").strip()
    if raw:
        return raw[:64]
    try:
        return socket.gethostname()[:64] or "arkland-node"
    except Exception:
        return "arkland-node"


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
        "machine_label": _resolve_machine_label(shop),
        "plugin_config_path": (
            getattr(srv, "customshop_config_path", "") or default_customshop_path(getattr(srv, "install_dir", ""))
        ),
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

    shop = cm.config.shop
    for kind, srv in iter_shop_servers(cm, asm_cm):
        name = getattr(srv, "name", "") or getattr(srv, "id", "")
        if not getattr(srv, "install_dir", ""):
            errors.append(f"{name}: sem install_dir")
            continue
        copied, notes = install_customshop_to_server(
            srv.install_dir, overwrite_dlls=overwrite_dlls, shop=shop,
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


def _read_db_prefs_file() -> dict:
    try:
        import os, json as _json
        appdata = os.environ.get("APPDATA", "")
        prefs_file = Path(appdata) / "ARKLAND-ServerManager" / "db_server_prefs.json"
        if prefs_file.exists():
            return _json.loads(prefs_file.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _db_manager_prefs() -> dict:
    """Credenciais do DB Manager — shop_db tem prioridade; não mistura root com arkland."""
    raw = _read_db_prefs_file()
    shop_db = raw.get("shop_db") or {}
    if (shop_db.get("user") or "").strip() and (shop_db.get("password") or "").strip():
        return shop_db
    last = raw.get("last_connection") or {}
    last_user = (last.get("user") or "").strip().lower()
    if last_user and last_user != "root":
        return last
    return shop_db


_PLACEHOLDER_DB_PASSWORDS = frozenset(
    {"", "SUA_SENHA_AQUI", "changeme", "password", "senha"}
)


def _is_placeholder_db_password(value: str) -> bool:
    return (value or "").strip() in _PLACEHOLDER_DB_PASSWORDS


def _shop_target_user(shop: Optional["ShopGlobalConfig"] = None) -> str:
    if shop is not None:
        user = (shop.orders_db_user or "").strip()
        if user:
            return user
    prefs = _db_manager_prefs()
    return (prefs.get("user") or "").strip() or "arkland"


def resolve_shop_db_password(shop: Optional["ShopGlobalConfig"] = None) -> str:
    """Senha efetiva: loja → shop_db (mesmo usuário). Nunca usa senha do root."""
    target_user = _shop_target_user(shop)
    if shop is not None:
        pwd = (shop.orders_db_password or "").strip()
        if pwd and not _is_placeholder_db_password(pwd):
            return pwd

    prefs = _db_manager_prefs()
    pref_user = (prefs.get("user") or "").strip()
    pref_pass = (prefs.get("password") or "").strip()
    if pref_user == target_user and pref_pass and not _is_placeholder_db_password(pref_pass):
        return pref_pass
    return ""


def build_orders_database_url(shop: "ShopGlobalConfig") -> str:
    explicit = (shop.orders_db_url or "").strip()
    if explicit:
        return explicit
    host     = (shop.orders_db_host or "").strip()
    port     = int(shop.orders_db_port or 3306)
    name     = (shop.orders_db_name or "").strip()
    user     = (shop.orders_db_user or "").strip()
    password = resolve_shop_db_password(shop)

    # Fallback: usa credenciais do DB Manager se os campos da loja estiverem vazios
    prefs = _db_manager_prefs()
    if not user:
        host = host or prefs.get("host", "127.0.0.1")
        port = port or int(prefs.get("port", 3306))
        name = name or prefs.get("database", "arkland_shop")
        user = prefs.get("user", "")

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
    env["PORT"] = str(max(1, int(shop.port or DEFAULT_SHOP_PORT)))
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

    port = max(1, int(port or DEFAULT_SHOP_PORT))
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
    """Testa conectividade com a loja. Em modo client, testa o domínio remoto."""
    if shop.mode == "client":
        url = effective_shop_public_url(shop)
        ok, msg = test_shop_connection(url)
        return ok, f"Loja remota ({url}): {msg}", False

    port = max(1, int(shop.port or DEFAULT_SHOP_PORT))
    host = (shop.host_ip or "").strip()
    ok_local, msg_local = test_shop_connection(f"http://127.0.0.1:{port}")
    if host:
        ok_lan, msg_lan = test_shop_connection(f"http://{host}:{port}")
    else:
        ok_lan, msg_lan = False, "IP LAN do host não configurado"
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
    from .db_setup_resources import probe_mysql_host

    prefs = _db_manager_prefs()
    host = (shop.orders_db_host or "").strip() or DEFAULT_REMOTE_SHOP_HOST
    port = int(shop.orders_db_port or 3306)
    name = (shop.orders_db_name or "").strip() or "arkland_shop"
    user = _shop_target_user(shop)
    password = resolve_shop_db_password(shop)

    host = host or prefs.get("host", "127.0.0.1")
    port = port or int(prefs.get("port", 3306))
    name = name or prefs.get("database", "arkland_shop")

    if password:
        working_host, probe_msg = probe_mysql_host(
            port=port,
            user=user,
            password=password,
            database=name,
            preferred_host=host,
        )
        if "Conectado" in probe_msg:
            host = working_host

    return {
        "Host": host,
        "Port": port,
        "User": user,
        "Password": password,
        "Database": name,
        "Ssl": False,
    }


def validate_plugin_database_settings(db_settings: Dict[str, Any]) -> Tuple[bool, str]:
    """Valida credenciais antes de gravar no plugin CustomShop."""
    from .db_setup_resources import probe_mysql_host

    user = (db_settings.get("User") or "").strip()
    password = (db_settings.get("Password") or "").strip()
    name = (db_settings.get("Database") or "").strip() or "arkland_shop"
    port = int(db_settings.get("Port") or 3306)
    host = (db_settings.get("Host") or "127.0.0.1").strip()

    if not user:
        return False, "Usuário MySQL não configurado (Banco de Pedidos / DB Manager)."
    if not password or _is_placeholder_db_password(password):
        return False, (
            f"Senha do usuário '{user}' não configurada. "
            "Preencha em CustomShop → Web Store → Banco de Pedidos e salve."
        )

    working_host, probe_msg = probe_mysql_host(
        port=port,
        user=user,
        password=password,
        database=name,
        preferred_host=host,
    )
    if "Conectado" in probe_msg:
        if working_host != host:
            db_settings["Host"] = working_host
        return True, f"MySQL OK ({user}@{working_host})"

    return False, (
        f"MySQL recusou '{user}' em 127.0.0.1 e localhost: {probe_msg}. "
        "No DB Manager, reconecte como arkland ou use «Criar usuário» para "
        "localhost + % com a mesma senha."
    )


def _cross_chat_server_label(srv: Any) -> str:
    """Nome exibido no chat cluster — único por mapa."""
    raw = (
        (getattr(srv, "name", "") or "").strip()
        or (getattr(srv, "shop_server_id", "") or "").strip()
    )
    if not raw:
        raw = slugify_server_id("", getattr(srv, "id", ""))
    ascii_parts = re.findall(r"[\x20-\x7e]+", raw)
    label = " ".join("".join(ascii_parts).split())
    return (label or slugify_server_id(raw, getattr(srv, "id", "")))[:64]


def build_cross_chat_settings(
    shop: "ShopGlobalConfig",
    srv: Any,
    catalog_cc: Optional[Dict[str, Any]] = None,
    existing_cc: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Monta bloco CrossChat do plugin — ServerId único por servidor."""
    catalog_cc = catalog_cc or {}
    existing_cc = existing_cc or {}
    merged = {**catalog_cc, **existing_cc}
    enabled = bool(getattr(shop, "cross_chat_enabled", True))
    if "Enabled" in catalog_cc:
        enabled = enabled and bool(catalog_cc.get("Enabled", True))
    return {
        "_comment": (
            "Chat entre mapas do cluster (comando /c). "
            "ServerId definido automaticamente ao sincronizar."
        ),
        "Enabled": enabled,
        "ServerId": _cross_chat_server_label(srv),
        "Command": str(merged.get("Command") or "/c"),
        "PollIntervalSeconds": max(1, int(merged.get("PollIntervalSeconds") or 2)),
        "MaxMessageLength": max(1, min(500, int(merged.get("MaxMessageLength") or 200))),
        "RateLimitSeconds": max(0, int(merged.get("RateLimitSeconds") or 2)),
        "UseWebApi": bool(merged.get("UseWebApi", False)),
    }


def merge_plugin_config(
    catalog: Dict[str, Any],
    website_url: str,
    api_url: str,
    api_key: str,
    db_settings: Dict[str, Any],
) -> Dict[str, Any]:
    out = deepcopy(catalog)
    settings = out.setdefault("Settings", {})
    settings["WebsiteUrl"] = website_url
    settings["WebApiUrl"] = api_url
    settings["WebApiKey"] = api_key
    if db_settings:
        out["Database"] = deepcopy(db_settings)
    return out


def sync_plugin_at_path(
    catalog: Dict[str, Any],
    plugin_path: Path,
    website_url: str,
    api_url: str,
    api_key: str,
    db_settings: Dict[str, Any],
) -> None:
    existing = load_plugin_config(plugin_path) if plugin_path.exists() else {}
    merged = merge_plugin_config(catalog, website_url, api_url, api_key, db_settings)
    # Não sobrescrever senha válida já no plugin com placeholder do app.
    merged_db = merged.get("Database") or {}
    existing_db = existing.get("Database") or {}
    merged_pw = str(merged_db.get("Password") or "")
    existing_pw = str(existing_db.get("Password") or "")
    if _is_placeholder_db_password(merged_pw) and existing_pw and not _is_placeholder_db_password(existing_pw):
        merged_db["Password"] = existing_pw
        merged["Database"] = merged_db
    if existing.get("Settings"):
        for k, v in existing["Settings"].items():
            if k not in ("WebsiteUrl", "WebApiUrl", "WebApiKey"):
                merged["Settings"].setdefault(k, v)
    save_plugin_config(plugin_path, merged)


def sync_arkshop_web_settings(
    shop: "ShopGlobalConfig",
    catalog_path: Path,
    *,
    website_url: str = "",
    api_url: str = "",
) -> None:
    data: Dict[str, Any] = {}
    settings_path = webstore_data_dir() / "settings.json"
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}

    data["port"] = int(shop.port or DEFAULT_SHOP_PORT)
    data["delivery_mode"] = shop.delivery_mode or "plugin"
    data["config_path"] = str(catalog_path)
    data["central_url"] = resolve_central_url(shop)
    data["public_url"] = effective_shop_public_url(shop)
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


def _merge_arkland_server_entry(
    existing: Optional[Dict[str, Any]],
    entry: Dict[str, Any],
    srv: Any,
) -> Dict[str, Any]:
    """Preserva label customizado e show_on_home do admin web quando aplicável."""
    out = dict(entry)
    out["arkland_ref"] = entry.get("arkland_ref", "")
    out["managed_by"] = "arkland"
    show_home = getattr(srv, "shop_show_on_home", True)
    if existing and "show_on_home" in existing and existing.get("arkland_ref") == out["arkland_ref"]:
        out["show_on_home"] = bool(existing.get("show_on_home", show_home))
    else:
        out["show_on_home"] = bool(show_home)
    auto_label = entry.get("label", "")
    if existing:
        prev_label = str(existing.get("label") or "").strip()
        prev_auto = str(existing.get("_auto_label") or auto_label).strip()
        if prev_label and prev_label != prev_auto:
            out["label"] = prev_label
    out["_auto_label"] = auto_label
    return out


def apply_machine_server_registry(
    by_id: Dict[str, Dict[str, Any]],
    machine_label: str,
    incoming: List[Dict[str, Any]],
    active_refs: set[str],
) -> int:
    """Mescla servidores de uma máquina e remove órfãos só deste machine_label."""

    def _owned(entry: Dict[str, Any]) -> bool:
        ml = str(entry.get("machine_label") or "").strip()
        if not ml:
            return True
        return ml == machine_label

    incoming_by_ref = {
        str(e.get("arkland_ref", "")): e
        for e in incoming
        if e.get("arkland_ref")
    }

    for old_sid, old_entry in list(by_id.items()):
        if not _owned(old_entry):
            continue
        ref = str(old_entry.get("arkland_ref") or "")
        if ref and ref in incoming_by_ref:
            new_sid = str(incoming_by_ref[ref].get("server_id", "")).strip()
            if new_sid and old_sid != new_sid:
                del by_id[old_sid]

    count = 0
    for entry in incoming:
        sid = str(entry.get("server_id", "")).strip()
        if not sid:
            continue
        clean = dict(entry)
        clean.pop("_auto_label", None)
        by_id[sid] = clean
        count += 1

    for sid, e in list(by_id.items()):
        if not _owned(e):
            continue
        ref = str(e.get("arkland_ref") or "")
        if ref and ref not in active_refs:
            del by_id[sid]

    return count


def _collect_server_registry(
    cm: "ConfigManager",
    shop: "ShopGlobalConfig",
    asm_cm: Optional["AsmConfigManager"],
    by_id: Dict[str, Dict[str, Any]],
) -> Tuple[str, List[Dict[str, Any]], set[str]]:
    machine_label = _resolve_machine_label(shop)
    incoming: List[Dict[str, Any]] = []
    active_refs: set[str] = set()

    for kind, srv in iter_shop_servers(cm, asm_cm):
        ref = _arkland_ref(kind, srv)
        if getattr(srv, "shop_exclude", False):
            continue
        active_refs.add(ref)
        entry = _server_rcon_entry(srv, shop)
        entry["arkland_ref"] = ref
        entry["machine_label"] = machine_label
        sid = entry["server_id"]
        existing = by_id.get(sid)
        incoming.append(_merge_arkland_server_entry(existing, entry, srv))

    return machine_label, incoming, active_refs


def _register_arkshop_servers_local(
    cm: "ConfigManager",
    shop: "ShopGlobalConfig",
    asm_cm: Optional["AsmConfigManager"] = None,
) -> int:
    servers_path = webstore_data_dir() / "servers.json"
    servers: List[Dict[str, Any]] = []
    if servers_path.exists():
        try:
            raw = json.loads(servers_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                servers = [s for s in raw if isinstance(s, dict)]
        except Exception:
            servers = []

    by_id: Dict[str, Dict[str, Any]] = {}
    for s in servers:
        sid = str(s.get("server_id", "")).strip()
        if sid:
            by_id[sid] = s

    machine_label, incoming, active_refs = _collect_server_registry(
        cm, shop, asm_cm, by_id,
    )
    count = apply_machine_server_registry(by_id, machine_label, incoming, active_refs)

    servers_path.parent.mkdir(parents=True, exist_ok=True)
    servers_path.write_text(
        json.dumps(list(by_id.values()), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return count


def _register_arkshop_servers_remote(
    cm: "ConfigManager",
    shop: "ShopGlobalConfig",
    asm_cm: Optional["AsmConfigManager"] = None,
    errors: Optional[List[str]] = None,
) -> int:
    """Envia cadastro de servidores desta máquina para a loja central (modo client)."""
    api_key = (shop.api_key or "").strip()
    if not api_key:
        msg = (
            "Loja remota: defina a API Key na aba Loja para registrar servidores no site central."
        )
        if errors is not None:
            errors.append(msg)
        return 0

    machine_label, incoming, active_refs = _collect_server_registry(
        cm, shop, asm_cm, {},
    )
    payload_entries: List[Dict[str, Any]] = []
    for entry in incoming:
        clean = dict(entry)
        clean.pop("_auto_label", None)
        payload_entries.append(clean)

    api_url = resolve_plugin_api_url(shop).rstrip("/")
    body = json.dumps({
        "machine_label": machine_label,
        "servers": payload_entries,
        "active_refs": sorted(active_refs),
    }, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        f"{api_url}/api/servers/sync",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": api_key,
            "User-Agent": "ARKLAND-ServerManager",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not data.get("ok"):
            msg = str(data.get("error") or "Falha ao registrar servidores na loja central")
            if errors is not None:
                errors.append(msg)
            return 0
        return int(data.get("registered", 0) or len(payload_entries))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        msg = f"Loja remota HTTP {exc.code}: {detail or exc.reason}"
        if errors is not None:
            errors.append(msg)
        return 0
    except Exception as exc:
        msg = f"Loja remota: não foi possível registrar servidores ({exc})"
        if errors is not None:
            errors.append(msg)
        return 0


def register_arkshop_servers(
    cm: "ConfigManager",
    shop: "ShopGlobalConfig",
    asm_cm: Optional["AsmConfigManager"] = None,
    errors: Optional[List[str]] = None,
) -> int:
    if (shop.mode or "client") == "client":
        return _register_arkshop_servers_remote(cm, shop, asm_cm=asm_cm, errors=errors)
    return _register_arkshop_servers_local(cm, shop, asm_cm=asm_cm)


def sync_all_plugins(
    cm: "ConfigManager",
    shop: "ShopGlobalConfig",
    catalog: Dict[str, Any],
    catalog_path: Path,
    asm_cm: Optional["AsmConfigManager"] = None,
) -> Tuple[List[str], List[str]]:
    """Retorna (sucessos, erros)."""
    website = resolve_website_url(shop)
    api = resolve_plugin_api_url(shop)
    api_key = shop.api_key or ""
    db_settings = build_plugin_database_settings(shop)
    db_ok, db_msg = validate_plugin_database_settings(db_settings)
    if not db_ok:
        errors: List[str] = [f"CustomShop DB: {db_msg}"]
        return [], errors

    catalog_db = catalog.get("Database", {})
    if catalog_db:
        # Senha nunca vem do catálogo (template pode ter SUA_SENHA_AQUI).
        catalog_db = {k: v for k, v in catalog_db.items() if k != "Password"}
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
            sync_plugin_at_path(catalog, plugin_path, website, api, api_key, db_settings)
            cfg_after = load_plugin_config(plugin_path)
            cfg_after["CrossChat"] = build_cross_chat_settings(
                shop,
                srv,
                catalog_cc=catalog.get("CrossChat") or {},
                existing_cc=cfg_after.get("CrossChat") or {},
            )
            save_plugin_config(plugin_path, cfg_after)
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
            ok.append(f"{getattr(srv, 'name', '')} → CustomShop {plugin_path}")

            install_dir = getattr(srv, "install_dir", "") or ""
            if install_dir:
                perm_ok, perm_notes = _ensure_permissions_config_on_server(
                    install_dir, shop=shop,
                )
                for line in perm_ok:
                    ok.append(f"{getattr(srv, 'name', '')} → {line}")
                for line in perm_notes:
                    errors.append(f"{getattr(srv, 'name', '')}: {line}")
        except Exception as exc:
            errors.append(f"{getattr(srv, 'name', '')}: {exc}")

    if classic_dirty:
        cm.save_servers()
    if tek_dirty and asm_cm is not None:
        asm_cm.save()
    sync_arkshop_web_settings(shop, catalog_path, website_url=website, api_url=api)
    reg_n = register_arkshop_servers(cm, shop, asm_cm=asm_cm, errors=errors)
    if reg_n:
        ok.append(f"Servidores registrados na loja: {reg_n}")
    return ok, errors


def default_catalog_path(shop: "ShopGlobalConfig") -> Path:
    raw = (shop.catalog_config_path or "").strip()
    if raw:
        return Path(raw)
    return _DEFAULT_CATALOG
