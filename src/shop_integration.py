"""Integração loja central ↔ apps cliente ↔ plugins CustomShop (multi-servidor / LAN)."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from urllib.parse import urlparse

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
logger = logging.getLogger(__name__)

_INSTALLED_CATALOG_REL = Path("plugin") / "CustomShop" / "configs" / "config.json"


def is_ephemeral_pyinstaller_path(path: str | Path) -> bool:
    """True se o caminho aponta para extração temporária do PyInstaller (_MEIPASS)."""
    if not path:
        return False
    norm = str(path).replace("/", "\\")
    upper = norm.upper()
    return "_MEI" in upper or "\\TEMP\\_MEI" in upper


def catalog_entry_counts(data: Dict[str, Any]) -> Tuple[int, int]:
    """Retorna (n_items, n_kits) do config CustomShop."""
    items = data.get("Items") or data.get("ShopItems") or {}
    kits = data.get("Kits") or {}
    ni = len(items) if isinstance(items, dict) else 0
    nk = len(kits) if isinstance(kits, dict) else 0
    return ni, nk


def catalog_entry_total(data: Dict[str, Any]) -> int:
    ni, nk = catalog_entry_counts(data)
    return ni + nk


# Chaves de Settings definidas pelo TEK na sincronização (por mapa / cluster).
TEK_MANAGED_SETTINGS_KEYS = frozenset({"WebsiteUrl", "WebApiUrl", "WebApiKey"})

# Seções compartilhadas que devem propagar entre mestre TEK, WEBSTORE e plugins.
SHARED_SYNC_TOP_LEVEL_KEYS = (
    "Items",
    "ShopItems",
    "Kits",
    "TimedPointsReward",
    "CrossChat",
    "Messages",
    "Downloads",
    "PointPackages",
    "FeaturedMaps",
)


def _stable_json_blob(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


def shared_config_fingerprint(data: Dict[str, Any]) -> str:
    """Hash das seções compartilhadas (Settings sem URLs TEK + TimedPointsReward, etc.)."""
    parts: Dict[str, Any] = {}
    for key in SHARED_SYNC_TOP_LEVEL_KEYS:
        if key in data:
            parts[key] = data[key]
    settings = data.get("Settings") or {}
    if settings:
        parts["Settings"] = {
            k: v for k, v in settings.items() if k not in TEK_MANAGED_SETTINGS_KEYS
        }
    return hashlib.sha256(_stable_json_blob(parts).encode("utf-8")).hexdigest()


def merge_settings_from_catalog(
    merged: Dict[str, Any],
    catalog: Dict[str, Any],
    existing: Dict[str, Any],
    *,
    website_url: str = "",
    api_url: str = "",
    api_key: str = "",
) -> None:
    """Settings do catálogo mestre vencem; preserva chaves extras locais do mapa."""
    cat_settings = catalog.get("Settings") or {}
    ex_settings = existing.get("Settings") or {}
    out = merged.setdefault("Settings", {})
    for k, v in cat_settings.items():
        if k not in TEK_MANAGED_SETTINGS_KEYS:
            out[k] = deepcopy(v)
    for k, v in ex_settings.items():
        if k not in TEK_MANAGED_SETTINGS_KEYS and k not in cat_settings:
            out.setdefault(k, deepcopy(v))
    if website_url:
        out["WebsiteUrl"] = website_url
    if api_url:
        out["WebApiUrl"] = api_url
    if api_key:
        out["WebApiKey"] = api_key


def apply_shared_sections_to_plugin(
    merged: Dict[str, Any],
    catalog: Dict[str, Any],
    existing: Dict[str, Any],
) -> None:
    """Copia seções compartilhadas do mestre; preserva ServerId local do CrossChat."""
    for key in SHARED_SYNC_TOP_LEVEL_KEYS:
        if key not in catalog:
            continue
        if key == "CrossChat":
            cat_cc = deepcopy(catalog["CrossChat"])
            ex_sid = (existing.get("CrossChat") or {}).get("ServerId")
            if ex_sid:
                cat_cc["ServerId"] = ex_sid
            merged["CrossChat"] = cat_cc
        else:
            merged[key] = deepcopy(catalog[key])
    merge_settings_from_catalog(merged, catalog, existing)


def merge_catalog_into_plugin_config(
    catalog: Dict[str, Any],
    existing: Dict[str, Any],
) -> Dict[str, Any]:
    """Mescla catálogo mestre no config de um mapa (admin web / sync)."""
    merged = deepcopy(catalog)
    apply_shared_sections_to_plugin(merged, catalog, existing)
    if not merged.get("Database") and existing.get("Database"):
        merged["Database"] = deepcopy(existing["Database"])
    merged_db = merged.get("Database") or {}
    existing_db = existing.get("Database") or {}
    merged_pw = str(merged_db.get("Password") or "")
    existing_pw = str(existing_db.get("Password") or "")
    if _is_placeholder_db_password(merged_pw) and existing_pw and not _is_placeholder_db_password(existing_pw):
        merged_db["Password"] = existing_pw
        merged["Database"] = merged_db
    return merged


def installed_catalog_candidates() -> List[Path]:
    """Caminhos persistentes possíveis para o catálogo mestre config.json.

    Não inclui WEBSTORE/config.json — essa cópia é só runtime da Web Store;
    usá-la como mestre (v1.9.128) truncava o catálogo para poucos itens.
    """
    candidates: List[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / _INSTALLED_CATALOG_REL)
    pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    candidates.append(pf / "ARKLAND-ServerManager" / _INSTALLED_CATALOG_REL)
    candidates.append(
        Path(os.environ.get("APPDATA", Path.home()))
        / "ARKLAND-ServerManager"
        / "CustomShop"
        / "configs"
        / "config.json"
    )
    candidates.append(_DEFAULT_CATALOG)
    return _dedupe_paths(candidates)


def _dedupe_paths(paths: List[Path]) -> List[Path]:
    seen: set[str] = set()
    out: List[Path] = []
    for p in paths:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _webstore_catalog_file() -> Optional[Path]:
    from .arkland_environment import try_load_environment_paths

    if not try_load_environment_paths():
        return None
    return webstore_data_dir() / "config.json"


def is_webstore_catalog_path(path: str | Path) -> bool:
    """True se o caminho é a cópia WEBSTORE/config.json (não o mestre de sync)."""
    ws = _webstore_catalog_file()
    if ws is None:
        return False
    try:
        return Path(path).resolve() == ws.resolve()
    except OSError:
        return False


def _map_plugin_config_paths() -> List[Path]:
    """Configs CustomShop nos mapas do ambiente ARKLAND (fonte de recuperação)."""
    from .arkland_environment import try_load_environment_paths

    paths = try_load_environment_paths()
    if not paths:
        return []
    maps_root = getattr(paths, "maps", None)
    if not maps_root or not Path(maps_root).is_dir():
        return []
    maps_root = Path(maps_root)
    return sorted(
        maps_root.glob(
            "*/ShooterGame/Binaries/Win64/ArkApi/Plugins/CustomShop/config.json"
        )
    )


def _collect_catalog_search_paths() -> List[Path]:
    return _dedupe_paths(installed_catalog_candidates() + _map_plugin_config_paths())


def _pick_richest_catalog_path(candidates: List[Path]) -> Optional[Path]:
    best: Optional[Path] = None
    best_score = -1
    for p in candidates:
        if not p.is_file():
            continue
        try:
            score = catalog_entry_total(load_plugin_config(p))
        except Exception:
            continue
        if score > best_score:
            best_score = score
            best = p
    return best


def _is_truncated_vs_alternatives(path: Path, alternatives: List[Path]) -> bool:
    """Detecta cópia WEBSTORE (ou mestre) muito menor que configs nos mapas."""
    if not path.is_file():
        return False
    own = catalog_entry_total(load_plugin_config(path))
    best_other = 0
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    for alt in alternatives:
        if not alt.is_file():
            continue
        try:
            if alt.resolve() == resolved:
                continue
        except OSError:
            if alt == path:
                continue
        best_other = max(best_other, catalog_entry_total(load_plugin_config(alt)))
    return best_other >= 20 and own < max(10, int(best_other * 0.25))


def resolve_persistent_catalog_path(
    configured: str | Path = "",
    *,
    shop: Optional["ShopGlobalConfig"] = None,
) -> Path:
    """Resolve caminho gravável do catálogo mestre — nunca _MEIPASS nem stub WEBSTORE."""
    search_paths = _collect_catalog_search_paths()
    preferred: List[Path] = []
    for raw in (
        str(configured or "").strip(),
        (getattr(shop, "catalog_config_path", "") or "").strip() if shop else "",
    ):
        if raw and not is_ephemeral_pyinstaller_path(raw):
            preferred.append(Path(raw))

    for p in preferred:
        if not p.is_file():
            continue
        if _is_truncated_vs_alternatives(p, search_paths):
            logger.warning(
                "Catálogo configurado parece truncado (%s itens+kits) — "
                "ignorando em favor de fonte mais completa",
                catalog_entry_total(load_plugin_config(p)),
            )
            continue
        return p

    richest = _pick_richest_catalog_path(search_paths)
    if richest is not None:
        return richest

    for p in installed_catalog_candidates():
        if p.is_file():
            return p
    for p in installed_catalog_candidates():
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            return p
        except OSError:
            continue
    return installed_catalog_candidates()[-1]


def webstore_data_dir() -> Path:
    """Diretório gravável da Web Store (dev: plugin/; instalado: APPDATA ou ambiente)."""
    import os

    from .arkland_environment import default_webstore_dir, try_load_environment_paths

    override = os.environ.get("ARKSHOP_DATA_DIR", "").strip()
    if override:
        p = Path(override)
    elif try_load_environment_paths():
        p = default_webstore_dir()
    elif getattr(sys, "frozen", False):
        p = Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager" / "arkshop_web"
    else:
        p = _ARKSHOP_WEB_DIR
    p.mkdir(parents=True, exist_ok=True)
    return p


def resolve_web_secret() -> str:
    """Secret Flask da Web Store — env, arquivo persistente ou geração automática."""
    import os
    import secrets

    env_val = os.environ.get("ARKSHOP_WEB_SECRET", "").strip()
    if env_val:
        return env_val

    secret_file = webstore_data_dir() / "web_secret.txt"
    if secret_file.is_file():
        try:
            stored = secret_file.read_text(encoding="utf-8").strip()
            if stored:
                return stored
        except OSError:
            pass

    generated = secrets.token_urlsafe(32)
    try:
        secret_file.write_text(generated, encoding="utf-8")
        logger.info("ARKSHOP_WEB_SECRET gerada em %s", secret_file)
    except OSError as exc:
        logger.warning("Não foi possível gravar web_secret.txt: %s", exc)
    return generated


def _path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def merge_catalog_content_from_source(
    base: Dict[str, Any],
    source: Dict[str, Any],
) -> Dict[str, Any]:
    """Copia seções editáveis do catálogo (Items/Kits/Settings/etc.) preservando URLs TEK do base."""
    out = deepcopy(base)
    for key in SHARED_SYNC_TOP_LEVEL_KEYS:
        if key in source:
            out[key] = deepcopy(source[key])
    ws_settings = source.get("Settings") or {}
    if ws_settings:
        out_settings = out.setdefault("Settings", {})
        for k, v in ws_settings.items():
            if k not in TEK_MANAGED_SETTINGS_KEYS:
                out_settings[k] = deepcopy(v)
    return out


def reconcile_catalog_before_sync(
    catalog_path: Path | str,
    catalog: Dict[str, Any],
) -> Tuple[Path, Dict[str, Any]]:
    """Antes do Sync TEK: incorpora edições da Web Store e do disco (evita memória stale).

    Prioridade: WEBSTORE/config.json mais recente ou mais completo que o mestre TEK;
    senão recarrega o mestre do disco se tiver pelo menos tantas entradas quanto a memória.
    """
    master = Path(catalog_path)
    merged = deepcopy(catalog)

    if master.is_file():
        disk_master = load_plugin_config(master)
        if catalog_entry_total(disk_master) >= catalog_entry_total(merged):
            merged = disk_master

    ws_path = _webstore_catalog_file()
    if ws_path is None or not ws_path.is_file():
        return master, merged

    try:
        same_file = ws_path.resolve() == master.resolve()
    except OSError:
        same_file = ws_path == master
    if same_file:
        return master, merged

    ws_data = load_plugin_config(ws_path)
    ws_total = catalog_entry_total(ws_data)
    merged_total = catalog_entry_total(merged)
    ws_mtime = _path_mtime(ws_path)
    master_mtime = _path_mtime(master)
    ws_fp = shared_config_fingerprint(ws_data)
    merged_fp = shared_config_fingerprint(merged)

    if (
        ws_mtime > master_mtime + 0.001
        or ws_total > merged_total
        or (ws_fp != merged_fp and ws_mtime + 0.001 >= master_mtime)
    ):
        merged = merge_catalog_content_from_source(merged, ws_data)
        if ws_mtime > master_mtime + 0.001:
            reason = "mtime"
        elif ws_total > merged_total:
            reason = "conteúdo"
        else:
            reason = "Settings/TimedPointsReward"
        logger.info(
            "Sync: catálogo da Web Store incorporado (%s, %d entradas) — mestre TEK desatualizado",
            reason,
            ws_total,
        )

    return master, merged


def ensure_webstore_catalog_config(source: Path | str) -> Path:
    """Copia catálogo mestre para WEBSTORE/config.json (runtime da Web Store).

    Atualiza a cópia quando ausente ou quando o mestre tem muito mais itens
    (evita servir stub truncado após migração v1.9.128).
    Nunca sobrescreve WEBSTORE mais recente que o mestre (edições do admin web).
    """
    from .arkland_environment import try_load_environment_paths

    src = Path(source)
    if not try_load_environment_paths():
        return src
    dest = webstore_data_dir() / "config.json"
    if not src.is_file():
        return dest if dest.is_file() else src

    src_total = catalog_entry_total(load_plugin_config(src))
    should_copy = not dest.is_file()
    if dest.is_file() and not should_copy:
        dest_mtime = _path_mtime(dest)
        src_mtime = _path_mtime(src)
        if dest_mtime > src_mtime + 0.001:
            return dest
        dest_total = catalog_entry_total(load_plugin_config(dest))
        if src_total > dest_total + 5:
            should_copy = True
            logger.info(
                "WEBSTORE config desatualizado (%d vs mestre %d) — recopiando de %s",
                dest_total, src_total, src,
            )

    if should_copy:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
    return dest if dest.is_file() else src


def push_catalog_to_webstore(source: Path | str) -> Optional[Path]:
    """Grava catálogo mestre em WEBSTORE/config.json (força convergência após save/sync TEK)."""
    from .arkland_environment import try_load_environment_paths

    if not try_load_environment_paths():
        return None
    src = Path(source)
    if not src.is_file():
        return None
    dest = webstore_data_dir() / "config.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    logger.info("WEBSTORE config atualizado a partir do mestre → %s", dest)
    return dest


def _richest_map_catalog_total(
    cm: "ConfigManager",
    asm_cm: Optional["AsmConfigManager"] = None,
) -> int:
    best = 0
    for kind, srv in iter_shop_servers(cm, asm_cm):
        path_str = (getattr(srv, "customshop_config_path", "") or "").strip()
        if not path_str:
            path_str = default_customshop_path(getattr(srv, "install_dir", ""))
        if not path_str:
            continue
        p = Path(path_str)
        if p.is_file():
            best = max(best, catalog_entry_total(load_plugin_config(p)))
    return best


def check_catalog_shrink_guard(
    catalog: Dict[str, Any],
    cm: "ConfigManager",
    asm_cm: Optional["AsmConfigManager"] = None,
) -> Optional[str]:
    """Bloqueia sync que apagaria catálogo nos mapas (mestre muito menor que plugins)."""
    master_total = catalog_entry_total(catalog)
    richest_map = _richest_map_catalog_total(cm, asm_cm)
    if richest_map >= 50 and master_total < max(10, int(richest_map * 0.25)):
        ni, nk = catalog_entry_counts(catalog)
        return (
            f"Sync abortado: catálogo mestre tem apenas {ni} itens e {nk} kits "
            f"(total {master_total}), mas um mapa tem {richest_map} entradas. "
            "Recarregue o catálogo do mapa ou backup antes de sincronizar."
        )
    return None


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


def _is_ipv4_literal(host: str) -> bool:
    parts = (host or "").strip().split(".")
    if len(parts) != 4:
        return False
    try:
        return all(p.isdigit() and 0 <= int(p) <= 255 for p in parts)
    except ValueError:
        return False


def is_stale_ip_website_url(url: str) -> bool:
    """True quando WebsiteUrl aponta para IP (ex.: http://179.x.x.x:27199)."""
    raw = (url or "").strip()
    if not raw:
        return False
    try:
        parsed = urlparse(raw if "://" in raw else f"http://{raw}")
        host = (parsed.hostname or "").strip()
        return bool(host and _is_ipv4_literal(host))
    except Exception:
        return False


def needs_website_url_fix(current: str, desired: str) -> bool:
    """Decide se WebsiteUrl no disco deve ser sobrescrito pelo domínio público."""
    cur = (current or "").strip()
    des = (desired or "").strip()
    if not des:
        return False
    if not cur:
        return True
    if is_stale_ip_website_url(cur):
        return cur != des
    return False


def resolve_plugin_website_url(shop: "ShopGlobalConfig") -> str:
    """URL gravada em WebsiteUrl do plugin (/shop, mensagens Nuvem no chat).

    Sempre o domínio público efetivo — nunca IP:porta. WebApiUrl continua em LAN no host.
    """
    return effective_shop_public_url(shop)


def resolve_plugin_api_url(shop: "ShopGlobalConfig") -> str:
    """URL HTTP que o CustomShop.dll usa para a API da web store.

    Modo Host: plugins na LAN usam IP:porta da loja — entrega não depende do
    domínio público (ex.: Cloudflare Tunnel). Modo Cliente: aponta para a loja remota.
    """
    if (shop.mode or "client") == "client":
        domain = effective_shop_public_url(shop)
        if domain:
            return domain
        client = normalize_shop_url((shop.central_url or "").strip())
        if client:
            return client
        return resolve_central_url(shop)

    host = (shop.host_ip or "").strip()
    port = max(1, int(shop.port or DEFAULT_SHOP_PORT))
    if host:
        return f"http://{host}:{port}"
    return f"http://127.0.0.1:{port}"


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
        "plugin_website": resolve_plugin_website_url(shop),
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
    port = 3306
    user = "arkland"

    if shop is not None:
        port = int(shop.orders_db_port or port)
        user = (shop.orders_db_user or "").strip() or user

    prefs = _db_manager_prefs()
    host = normalize_orders_db_host(shop)
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


def _is_local_machine_host(host: str) -> bool:
    """True se o host aponta para esta máquina (localhost ou IP LAN local)."""
    h = (host or "").strip().lower()
    if not h or h in ("127.0.0.1", "localhost", "::1"):
        return True
    try:
        if h == get_local_ip().lower():
            return True
    except Exception:
        pass
    return False


def normalize_orders_db_host(
    shop: Optional["ShopGlobalConfig"] = None,
    *,
    raw_host: str = "",
) -> str:
    """Host MySQL efetivo para plugins — prefere 127.0.0.1 quando bind MariaDB é só localhost."""
    from .pages.db_local_server import DbLocalServer

    host = (raw_host or "").strip()
    if shop is not None and not host:
        host = (shop.orders_db_host or "").strip()

    if not host:
        prefs = _db_manager_prefs()
        host = (prefs.get("host") or "").strip() or "127.0.0.1"

    if not DbLocalServer.get_bind_lan() and _is_local_machine_host(host):
        return "127.0.0.1"

    return host


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
    host     = normalize_orders_db_host(shop)
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
    env["ARKSHOP_WEB_SECRET"] = resolve_web_secret()
    if shop.api_key:
        env["ARKSHOP_API_KEY"] = shop.api_key
    db_url = build_orders_database_url(shop)
    if db_url:
        env["ARKSHOP_DATABASE_URL"] = db_url
    catalog = resolve_persistent_catalog_path(shop.catalog_config_path, shop=shop)
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


def probe_public_https(hostname: str) -> Tuple[bool, str]:
    """Testa HTTPS no domínio público (Cloudflare Tunnel, proxy externo, etc.)."""
    host = re.sub(r"^https?://", "", (hostname or "").strip().lower()).split("/")[0].strip()
    if not host:
        return False, "domínio vazio"
    return test_shop_connection(f"https://{host}")


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


def resolve_dns_ipv4(hostname: str) -> Tuple[bool, str]:
    """Resolve o primeiro IPv4 de um hostname (domínio da loja)."""
    host = (hostname or "").strip().lower()
    host = re.sub(r"^https?://", "", host).split("/")[0].strip()
    if not host:
        return False, ""
    try:
        for info in socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM):
            return True, info[4][0]
    except OSError as exc:
        return False, str(exc)
    return False, "sem IPv4"


@dataclass
class ShopConnectivityReport:
    """Diagnóstico honesto — não confundir localhost com domínio público."""

    local_ok: bool = False
    local_msg: str = ""
    lan_ok: bool = False
    lan_msg: str = ""
    public_ok: bool = False
    public_msg: str = ""
    www_ok: bool = False
    www_msg: str = ""
    public_url: str = ""
    public_ip: str = ""
    dns_ip: str = ""
    dns_ok: bool = False
    lines: List[str] = field(default_factory=list)

    @property
    def process_up(self) -> bool:
        return self.local_ok

    @property
    def players_ok(self) -> bool:
        return self.public_ok and self.www_ok

    def status_label(self) -> str:
        if not self.process_up:
            return "Offline"
        if self.players_ok:
            return "Online · jogadores"
        if self.lan_ok:
            return "Online · LAN"
        if self.public_ok:
            return "Online · domínio parcial"
        return "Online · só local"

    def status_color(self) -> str:
        if not self.process_up:
            return "#ef4444"
        if self.players_ok:
            return "#22c55e"
        return "#f59e0b"


def diagnose_shop_connectivity(shop: "ShopGlobalConfig") -> ShopConnectivityReport:
    """Testa local, LAN, domínio HTTPS público e coerência DNS."""
    report = ShopConnectivityReport()
    port = max(1, int(shop.port or DEFAULT_SHOP_PORT))
    host = (shop.host_ip or "").strip() or get_local_ip()
    public_url = effective_shop_public_url(shop)
    report.public_url = public_url

    ok_ip, pub_ip = fetch_public_ip(timeout=4)
    report.public_ip = pub_ip if ok_ip else ""

    parsed = urlparse(public_url if "://" in public_url else f"https://{public_url}")
    domain = (parsed.hostname or "").strip().lower()
    if domain:
        ok_dns, dns_ip = resolve_dns_ipv4(domain)
        report.dns_ip = dns_ip if ok_dns else ""
        if ok_dns and report.public_ip:
            report.dns_ok = report.dns_ip == report.public_ip
        elif ok_dns and (shop.public_ip or "").strip():
            report.dns_ok = report.dns_ip == (shop.public_ip or "").strip()

    if shop.mode == "client":
        report.public_ok, report.public_msg = test_shop_connection(public_url)
        report.local_ok = report.public_ok
        report.local_msg = report.public_msg
        report.www_ok = report.public_ok
        report.www_msg = report.public_msg
        report.lines = [
            f"Domínio ({public_url}): {'OK' if report.public_ok else 'FALHOU'} — {report.public_msg}",
        ]
        return report

    local_url = f"http://127.0.0.1:{port}"
    lan_url = f"http://{host}:{port}" if host else ""
    report.local_ok, report.local_msg = test_shop_connection(local_url)
    if lan_url:
        report.lan_ok, report.lan_msg = test_shop_connection(lan_url)
    else:
        report.lan_ok = False
        report.lan_msg = "IP LAN não configurado"

    if domain:
        report.public_ok, report.public_msg = probe_public_https(domain)
        www_host = f"www.{domain}" if not domain.startswith("www.") else domain
        if www_host != domain:
            report.www_ok, report.www_msg = probe_public_https(www_host)
        else:
            report.www_ok, report.www_msg = report.public_ok, report.public_msg
    else:
        report.public_ok = False
        report.public_msg = "domínio não configurado"
        report.www_ok = False
        report.www_msg = report.public_msg

    report.lines.insert(
        0,
        f"Local ({local_url}): {'OK' if report.local_ok else 'FALHOU'} — {report.local_msg}",
    )
    if lan_url:
        fw = "sim" if check_webstore_firewall_rule(port) else "não"
        report.lines.insert(
            1,
            f"LAN ({lan_url}): {'OK' if report.lan_ok else 'FALHOU'} — {report.lan_msg}"
            + ("" if report.lan_ok else f" (firewall {fw})"),
        )
    if domain:
        report.lines.append(
            f"HTTPS ({domain}): {'OK' if report.public_ok else 'FALHOU'} — {report.public_msg}"
        )
        www_host = f"www.{domain}" if not domain.startswith("www.") else domain
        if www_host != domain:
            report.lines.append(
                f"HTTPS (www): {'OK' if report.www_ok else 'FALHOU'} — {report.www_msg}"
            )
    if report.public_ip:
        report.lines.append(f"IP público detectado: {report.public_ip}")
    if report.dns_ip:
        dns_state = "OK" if report.dns_ok else "fora do IP local (túnel/proxy?)"
        report.lines.append(f"DNS {domain} → {report.dns_ip} ({dns_state})")
    if report.local_ok and domain and not report.public_ok:
        report.lines.append(
            "Loja local OK, mas o domínio HTTPS não responde — confira Cloudflare Tunnel / DNS"
        )
    return report


def diagnose_webstore_access(shop: "ShopGlobalConfig") -> Tuple[bool, str, bool]:
    """Compat: retorna (ok, mensagem, local_ok). Em host, ok = jogadores alcançam o domínio."""
    report = diagnose_shop_connectivity(shop)
    if shop.mode == "client":
        return report.public_ok, report.lines[0] if report.lines else report.public_msg, False
    if report.players_ok:
        return True, report.lines[-2] if len(report.lines) > 1 else "Domínio respondendo", report.local_ok
    if report.lan_ok:
        return False, " · ".join(report.lines), report.local_ok
    if report.local_ok:
        return False, " · ".join(report.lines), True
    return False, report.local_msg or "Sem resposta", False


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
    host = normalize_orders_db_host(shop)
    port = int(shop.orders_db_port or 3306)
    name = (shop.orders_db_name or "").strip() or "arkland_shop"
    user = _shop_target_user(shop)
    password = resolve_shop_db_password(shop)

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


def warn_cluster_db_bind_mismatch(shop: "ShopGlobalConfig") -> Optional[str]:
    """Avisa quando mapas remotos precisam de MySQL na LAN mas o bind é só localhost."""
    from .pages.db_local_server import DbLocalServer

    host = (shop.orders_db_host or "").strip() or DEFAULT_REMOTE_SHOP_HOST
    if host in ("127.0.0.1", "localhost", "::1"):
        return None
    if DbLocalServer.get_bind_lan():
        return None
    return (
        f"MariaDB escuta só em 127.0.0.1, mas mapas usam Host={host}. "
        "Servidores de mapa em outras máquinas não conectam — CustomShop aborta "
        "e /shop fica off. No DB Manager: «Abrir porta 3306» → escolha LAN, "
        "reinicie o MariaDB e sincronize os plugins."
    )


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
            "Chat entre mapas do cluster (captura automatica do chat global). "
            "ServerId definido automaticamente ao sincronizar."
        ),
        "Enabled": enabled,
        "ServerId": _cross_chat_server_label(srv),
        "AutoCapture": bool(merged.get("AutoCapture", True)),
        "IgnoreCommands": bool(merged.get("IgnoreCommands", True)),
        "GlobalChatOnly": bool(merged.get("GlobalChatOnly", True)),
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


def catalog_permission_diff(
    existing: Dict[str, Any],
    catalog: Dict[str, Any],
) -> List[Tuple[str, str, str, str]]:
    """Compara Permissions de Kits/Items entre servidor e catálogo TEK."""
    changes: List[Tuple[str, str, str, str]] = []
    for section in ("Kits", "Items"):
        cat_sec = catalog.get(section) or {}
        ex_sec = existing.get(section) or {}
        for entry_id in sorted(cat_sec):
            old_p = str((ex_sec.get(entry_id) or {}).get("Permissions") or "")
            new_p = str((cat_sec.get(entry_id) or {}).get("Permissions") or "")
            if old_p != new_p:
                changes.append((section, entry_id, old_p, new_p))
    return changes


def format_permission_sync_note(
    section: str,
    entry_id: str,
    old_perms: str,
    new_perms: str,
) -> str:
    old_label = old_perms if old_perms else "(vazio)"
    new_label = new_perms if new_perms else "(vazio)"
    return f"{section}/{entry_id} Permissions: {old_label} → {new_label}"


def fix_website_url_in_config_file(
    plugin_path: Path,
    desired: str,
    *,
    server_name: str = "",
) -> Tuple[bool, str]:
    """Corrige WebsiteUrl legado (IP) em um config.json. Retorna (alterou, mensagem)."""
    if not plugin_path.is_file():
        return False, ""
    cfg = load_plugin_config(plugin_path)
    settings = cfg.setdefault("Settings", {})
    current = str(settings.get("WebsiteUrl") or "").strip()
    if not needs_website_url_fix(current, desired):
        return False, ""
    settings["WebsiteUrl"] = desired
    save_plugin_config(plugin_path, cfg)
    label = server_name or plugin_path.parent.name or str(plugin_path)
    msg = f"{label}: WebsiteUrl {current or '(vazio)'} → {desired}"
    logger.info("CustomShop migrate WebsiteUrl: %s (%s)", msg, plugin_path)
    return True, msg


def migrate_stale_plugin_website_urls(
    cm: "ConfigManager",
    shop: "ShopGlobalConfig",
    asm_cm: Optional["AsmConfigManager"] = None,
) -> Tuple[List[str], List[str]]:
    """Varre todos os servidores e corrige WebsiteUrl com IP legado."""
    desired = resolve_plugin_website_url(shop)
    fixed: List[str] = []
    errors: List[str] = []
    for kind, srv in iter_shop_servers(cm, asm_cm):
        path_str = (getattr(srv, "customshop_config_path", "") or "").strip()
        if not path_str:
            path_str = default_customshop_path(getattr(srv, "install_dir", ""))
        if not path_str:
            continue
        plugin_path = Path(path_str)
        try:
            changed, msg = fix_website_url_in_config_file(
                plugin_path, desired, server_name=getattr(srv, "name", "") or "",
            )
            if changed and msg:
                fixed.append(msg)
        except Exception as exc:
            errors.append(f"{getattr(srv, 'name', '')}: {exc}")
    catalog_raw = (shop.catalog_config_path or "").strip()
    if catalog_raw:
        catalog_raw = str(resolve_persistent_catalog_path(catalog_raw, shop=shop))
    if catalog_raw:
        try:
            changed, msg = fix_website_url_in_config_file(
                Path(catalog_raw), desired, server_name="catálogo mestre",
            )
            if changed and msg:
                fixed.append(msg)
        except Exception as exc:
            errors.append(f"catálogo mestre: {exc}")
    if fixed:
        logger.info(
            "CustomShop migrate: %d config(s) corrigido(s) → WebsiteUrl=%s",
            len(fixed), desired,
        )
    return fixed, errors


def sync_plugin_at_path(
    catalog: Dict[str, Any],
    plugin_path: Path,
    website_url: str,
    api_url: str,
    api_key: str,
    db_settings: Dict[str, Any],
    *,
    server_name: str = "",
) -> List[str]:
    """Sincroniza config do plugin; retorna notas de Permissions alteradas."""
    existing = load_plugin_config(plugin_path) if plugin_path.exists() else {}
    perm_notes: List[str] = []
    label = server_name or plugin_path.parent.parent.name or str(plugin_path)
    for section, entry_id, old_p, new_p in catalog_permission_diff(existing, catalog):
        note = format_permission_sync_note(section, entry_id, old_p, new_p)
        perm_notes.append(f"{label}: {note}")
        logger.info("CustomShop sync Permissions [%s] %s", label, note)

    old_url = str((existing.get("Settings") or {}).get("WebsiteUrl") or "").strip()
    merged = merge_plugin_config(catalog, website_url, api_url, api_key, db_settings)
    # Não sobrescrever senha válida já no plugin com placeholder do app.
    merged_db = merged.get("Database") or {}
    existing_db = existing.get("Database") or {}
    merged_pw = str(merged_db.get("Password") or "")
    existing_pw = str(existing_db.get("Password") or "")
    if _is_placeholder_db_password(merged_pw) and existing_pw and not _is_placeholder_db_password(existing_pw):
        merged_db["Password"] = existing_pw
        merged["Database"] = merged_db
    apply_shared_sections_to_plugin(merged, catalog, existing)
    merge_settings_from_catalog(
        merged, catalog, existing,
        website_url=website_url, api_url=api_url, api_key=api_key,
    )
    tp = merged.get("TimedPointsReward") or {}
    tp_groups = tp.get("Groups") or {}
    logger.info(
        "CustomShop sync TimedPointsReward [%s]: enabled=%s interval=%s groups=%s",
        label,
        tp.get("Enabled"),
        tp.get("Interval", 30),
        ",".join(sorted(str(k) for k in tp_groups.keys())) or "(none)",
    )
    new_url = str((merged.get("Settings") or {}).get("WebsiteUrl") or "").strip()
    if old_url != new_url:
        logger.info(
            "CustomShop sync WebsiteUrl: %s → %s (%s)",
            old_url or "(vazio)", new_url, plugin_path,
        )
    save_plugin_config(plugin_path, merged)
    return perm_notes


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

    catalog_path = resolve_persistent_catalog_path(catalog_path, shop=shop)
    if shop and is_ephemeral_pyinstaller_path(shop.catalog_config_path or ""):
        shop.catalog_config_path = str(catalog_path)
    webstore_config = ensure_webstore_catalog_config(catalog_path)

    data["port"] = int(shop.port or DEFAULT_SHOP_PORT)
    data["delivery_mode"] = shop.delivery_mode or "plugin"
    data["config_path"] = str(webstore_config)
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
    from .catalog_vip_pricing import apply_vip_pricing_to_catalog, catalog_has_placeholder_kit_prices

    catalog_path = resolve_persistent_catalog_path(catalog_path, shop=shop)
    shop_dirty = False
    if shop and is_ephemeral_pyinstaller_path(shop.catalog_config_path or ""):
        shop.catalog_config_path = str(catalog_path)
        shop_dirty = True
    if is_webstore_catalog_path(shop.catalog_config_path or ""):
        shop.catalog_config_path = str(catalog_path)
        shop_dirty = True

    catalog_path, catalog = reconcile_catalog_before_sync(catalog_path, catalog)

    shrink_err = check_catalog_shrink_guard(catalog, cm, asm_cm=asm_cm)
    if shrink_err:
        return [], [shrink_err]

    bind_warn = warn_cluster_db_bind_mismatch(shop)
    if bind_warn:
        logger.warning("CustomShop sync: %s", bind_warn)

    website = resolve_plugin_website_url(shop)
    api = resolve_plugin_api_url(shop)
    api_key = shop.api_key or ""
    logger.info("CustomShop sync: WebsiteUrl=%s WebApiUrl=%s", website, api)
    db_settings = build_plugin_database_settings(shop)
    db_ok, db_msg = validate_plugin_database_settings(db_settings)
    if not db_ok:
        errors: List[str] = [f"CustomShop DB: {db_msg}"]
        return [], errors

    ok: List[str] = []
    errors: List[str] = []
    if bind_warn:
        errors.append(f"AVISO: {bind_warn}")

    had_placeholders = catalog_has_placeholder_kit_prices(catalog)
    cleared, kit_updates = apply_vip_pricing_to_catalog(catalog)
    try:
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        save_plugin_config(catalog_path, catalog)
        ok.append(f"Catálogo mestre gravado → {catalog_path}")
        ws_copy = push_catalog_to_webstore(catalog_path) or ensure_webstore_catalog_config(catalog_path)
        if ws_copy.is_file() and ws_copy != catalog_path:
            ok.append(f"Web Store atualizada → {ws_copy}")
        if had_placeholders or cleared:
            ok.append(f"Placeholders removidos: {', '.join(cleared[:12]) or '(recalculados)'}")
        if kit_updates and (had_placeholders or cleared):
            ok.append(f"Preços VIP/Tek: {', '.join(kit_updates[:12])}")
    except Exception as exc:
        errors.append(f"catálogo mestre ({catalog_path}): {exc}")

    catalog_db = catalog.get("Database", {})
    if catalog_db:
        # Senha nunca vem do catálogo (template pode ter SUA_SENHA_AQUI).
        catalog_db = {k: v for k, v in catalog_db.items() if k != "Password"}
        db_settings = {**catalog_db, **db_settings}
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
            perm_notes = sync_plugin_at_path(
                catalog, plugin_path, website, api, api_key, db_settings,
                server_name=getattr(srv, "name", "") or "",
            )
            for note in perm_notes:
                ok.append(note)
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
    if shop_dirty:
        cm.save()
    sync_arkshop_web_settings(shop, catalog_path, website_url=website, api_url=api)
    reg_n = register_arkshop_servers(cm, shop, asm_cm=asm_cm, errors=errors)
    if reg_n:
        ok.append(f"Servidores registrados na loja: {reg_n}")
    return ok, errors


def default_catalog_path(shop: "ShopGlobalConfig") -> Path:
    return resolve_persistent_catalog_path(shop.catalog_config_path, shop=shop)
