"""Gerenciamento do reverse proxy Caddy (HTTPS → Web Store) no modo Host."""
from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, Tuple
from urllib.parse import urlparse

if TYPE_CHECKING:
    from .config_manager import ShopGlobalConfig

DEFAULT_CADDY_DIR = Path(r"C:\caddy")
SCHEDULED_TASK_NAME = "ARKLAND-Caddy-HTTPS"
_GITHUB_RELEASE_API = "https://api.github.com/repos/caddyserver/caddy/releases/latest"


def _port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def resolve_caddy_dir(shop: "ShopGlobalConfig") -> Path:
    raw = (getattr(shop, "caddy_dir", "") or "").strip()
    return Path(raw) if raw else DEFAULT_CADDY_DIR


def domain_from_shop(shop: "ShopGlobalConfig") -> str:
    from .shop_integration import effective_shop_public_url

    url = effective_shop_public_url(shop)
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or url).strip().lower()
    host = re.sub(r"^https?://", "", host).split("/")[0].strip()
    return host or "arkland.com.br"


def caddy_exe(shop: "ShopGlobalConfig") -> Path:
    return resolve_caddy_dir(shop) / "caddy.exe"


def caddyfile_path(shop: "ShopGlobalConfig") -> Path:
    return resolve_caddy_dir(shop) / "Caddyfile"


def is_caddy_installed(shop: "ShopGlobalConfig") -> bool:
    return caddy_exe(shop).is_file()


def is_caddy_running() -> bool:
    """Proxy ativo se 443 ou admin API 2019 respondem em localhost."""
    return _port_open(443) or _port_open(2019)


def write_caddyfile(shop: "ShopGlobalConfig") -> Path:
    install_dir = resolve_caddy_dir(shop)
    install_dir.mkdir(parents=True, exist_ok=True)
    domain = domain_from_shop(shop)
    port = max(1, int(getattr(shop, "port", None) or 27199))
    www = f"www.{domain}" if not domain.startswith("www.") else domain
    sites = domain if domain.startswith("www.") else f"{domain}, {www}"
    content = (
        f"{sites} {{\n"
        f"    reverse_proxy 127.0.0.1:{port}\n"
        f"}}\n"
    )
    path = caddyfile_path(shop)
    path.write_text(content, encoding="utf-8")
    return path


def _download_caddy_zip(dest_dir: Path) -> Tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Caddy integrado só no Windows (modo Host)."
    try:
        req = urllib.request.Request(
            _GITHUB_RELEASE_API,
            headers={"User-Agent": "ARKLAND-ServerManager"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        asset = next(
            (a for a in data.get("assets", [])
             if re.match(r"^caddy_.*_windows_amd64\.zip$", a.get("name", ""))),
            None,
        )
        if not asset:
            return False, "Pacote Windows amd64 do Caddy não encontrado no GitHub."
        dest_dir.mkdir(parents=True, exist_ok=True)
        zip_path = dest_dir / "_caddy_download.zip"
        with urllib.request.urlopen(asset["browser_download_url"], timeout=300) as resp:
            zip_path.write_bytes(resp.read())
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(dest_dir)
        zip_path.unlink(missing_ok=True)
        if not (dest_dir / "caddy.exe").is_file():
            return False, "caddy.exe ausente após extração."
        return True, f"Caddy instalado em {dest_dir}"
    except Exception as exc:
        return False, str(exc)


def _run_caddy(shop: "ShopGlobalConfig", *args: str, timeout: int = 20) -> Tuple[int, str]:
    exe = caddy_exe(shop)
    cwd = resolve_caddy_dir(shop)
    if not exe.is_file():
        return 127, "caddy.exe não encontrado"
    try:
        proc = subprocess.run(
            [str(exe), *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out.strip()
    except subprocess.TimeoutExpired:
        return 124, "Timeout"
    except Exception as exc:
        return 127, str(exc)


def _firewall_rule_exists(name: str) -> bool:
    try:
        r = subprocess.run(
            f'netsh advfirewall firewall show rule name="{name}"',
            shell=True, capture_output=True, text=True, timeout=8,
        )
        return r.returncode == 0
    except Exception:
        return False


def ensure_caddy_firewall() -> Tuple[bool, str]:
    """Libera TCP 80 e 443 (requer admin ou UAC)."""
    from .pages.db_local_server import DbLocalServer

    ports = (80, 443)
    missing = [p for p in ports if not _firewall_rule_exists(f"ARKLAND Caddy {p}")]
    if not missing:
        return True, "Portas 80 e 443 já liberadas."

    parts = []
    for p in missing:
        parts.append(
            f'netsh advfirewall firewall add rule name="ARKLAND Caddy {p}" '
            f"protocol=TCP dir=in localport={p} action=allow profile=any "
            f'description="ARKLAND Caddy HTTPS proxy"'
        )
    netsh_cmd = " & ".join(parts)

    if DbLocalServer.is_admin():
        try:
            subprocess.run(netsh_cmd, shell=True, capture_output=True, text=True, timeout=15)
            if all(_firewall_rule_exists(f"ARKLAND Caddy {p}") for p in ports):
                return True, "Portas 80 e 443 liberadas."
            return False, "Falha ao criar regras de firewall."
        except Exception as exc:
            return False, str(exc)

    try:
        import ctypes

        bat = tempfile.NamedTemporaryFile(suffix=".bat", mode="w", delete=False, encoding="utf-8")
        bat.write(f"@echo off\n{netsh_cmd}\n")
        bat.close()
        try:
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", f'/c "{bat.name}"', None, 0)
            if ret <= 32:
                return False, "UAC cancelado."
            for _ in range(20):
                time.sleep(0.5)
                if all(_firewall_rule_exists(f"ARKLAND Caddy {p}") for p in ports):
                    return True, "Portas 80 e 443 liberadas."
            return False, "Timeout aguardando firewall."
        finally:
            try:
                Path(bat.name).unlink(missing_ok=True)
            except Exception:
                pass
    except Exception as exc:
        return False, str(exc)


def install_caddy(shop: "ShopGlobalConfig", *, open_firewall: bool = True) -> Tuple[bool, str]:
    dest = resolve_caddy_dir(shop)
    if not is_caddy_installed(shop):
        ok, msg = _download_caddy_zip(dest)
        if not ok:
            return False, msg
    write_caddyfile(shop)
    code, out = _run_caddy(shop, "validate", "--config", str(caddyfile_path(shop)))
    if code != 0:
        return False, out or "Caddyfile inválido"
    msgs = ["Caddy pronto", str(dest)]
    if open_firewall:
        fw_ok, fw_msg = ensure_caddy_firewall()
        msgs.append(fw_msg if fw_ok else f"Firewall: {fw_msg}")
    return True, " — ".join(msgs)


def start_caddy(shop: "ShopGlobalConfig") -> Tuple[bool, str]:
    if not is_caddy_installed(shop):
        ok, msg = install_caddy(shop, open_firewall=False)
        if not ok:
            return False, msg
    write_caddyfile(shop)
    if is_caddy_running():
        return True, "Caddy já está rodando"
    code, out = _run_caddy(shop, "start")
    time.sleep(1.5)
    if is_caddy_running():
        return True, "Caddy iniciado (HTTPS → loja local)"
    if code == 0 and "Successfully started" in out:
        return True, "Caddy iniciado"
    return False, out or f"exit {code}"


def stop_caddy(shop: "ShopGlobalConfig") -> Tuple[bool, str]:
    if not is_caddy_installed(shop):
        return True, "Caddy não instalado"
    _run_caddy(shop, "stop")
    time.sleep(0.8)
    if is_caddy_running():
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "caddy.exe"],
                capture_output=True, timeout=10,
            )
            time.sleep(0.5)
        except Exception:
            pass
    if is_caddy_running():
        return False, "Não foi possível parar o Caddy"
    return True, "Caddy parado"


def restart_caddy(shop: "ShopGlobalConfig") -> Tuple[bool, str]:
    stop_caddy(shop)
    time.sleep(0.5)
    return start_caddy(shop)


def register_caddy_autostart(shop: "ShopGlobalConfig") -> Tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Somente Windows"
    if not is_caddy_installed(shop):
        ok, msg = install_caddy(shop)
        if not ok:
            return False, msg
    write_caddyfile(shop)
    exe = str(caddy_exe(shop))
    cfg = str(caddyfile_path(shop))
    cwd = str(resolve_caddy_dir(shop))
    tr_cmd = (
        f'schtasks /Create /F /TN "{SCHEDULED_TASK_NAME}" /SC ONSTART /RL HIGHEST '
        f'/TR "\\"{exe}\\" run --config \\"{cfg}\\"" /RU SYSTEM'
    )
    try:
        r = subprocess.run(tr_cmd, shell=True, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            out = (r.stdout + r.stderr).strip()
            return False, out or "schtasks falhou"
        return True, f"Tarefa «{SCHEDULED_TASK_NAME}» criada (inicia com o Windows)"
    except Exception as exc:
        return False, str(exc)


def caddy_status(shop: "ShopGlobalConfig") -> dict:
    installed = is_caddy_installed(shop)
    running = is_caddy_running()
    domain = domain_from_shop(shop)
    port = max(1, int(getattr(shop, "port", None) or 27199))
    if not installed:
        msg = "Não instalado — use «Instalar Caddy»"
    elif running:
        msg = f"HTTPS ativo → http://127.0.0.1:{port}"
    else:
        msg = "Instalado, parado"
    return {
        "installed": installed,
        "running": running,
        "domain": domain,
        "port": port,
        "dir": str(resolve_caddy_dir(shop)),
        "message": msg,
    }


def auto_start_caddy(shop: "ShopGlobalConfig", on_log: Optional[Callable[[str, str], None]] = None) -> None:
    """Inicia Caddy no boot do app (modo Host)."""
    if (shop.mode or "client") != "host":
        return
    if not getattr(shop, "caddy_auto_start", True):
        return
    if is_caddy_running():
        return
    if not is_caddy_installed(shop):
        return

    def _worker() -> None:
        ok, msg = start_caddy(shop)
        if on_log:
            on_log(msg, "info" if ok else "warning")

    import threading
    threading.Thread(target=_worker, daemon=True, name="CaddyLauncher").start()
