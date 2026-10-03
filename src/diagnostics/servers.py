"""Visão neutra dos servidores (clássico ``servers.json`` + TEK ``asm_servers.json``).

O doctor e o coletor trabalham sobre ``ServerView`` — nunca guardam senhas
(só se ``admin_password`` está preenchida ou não).
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOG = logging.getLogger("arkland")

STATUS_UNKNOWN = "desconhecido"


def read_json_file(path: Path) -> Any:
    """Lê JSON tolerante (utf-8/utf-8-sig). Devolve ``None`` se ausente/ilegível."""
    try:
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("JSON ilegível %s: %s", path, exc)
        return None


def read_text_any(path: Path, max_bytes: Optional[int] = None) -> str:
    """Lê texto tentando as codificações usadas pelo ARK (UTF-16 com BOM, UTF-8, latin-1).

    ``max_bytes`` limita a leitura (arquivos enormes); levanta ``OSError`` se ilegível.
    """
    with open(path, "rb") as fh:
        raw = fh.read(max_bytes) if max_bytes else fh.read()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        # corte em número ímpar de bytes quebraria o decode UTF-16
        if len(raw) % 2:
            raw = raw[:-1]
        return raw.decode("utf-16", errors="replace")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        if max_bytes and len(raw) >= max_bytes:   # provável corte no meio de um caractere
            return raw.decode("utf-8", errors="replace")
        return raw.decode("latin-1", errors="replace")


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass
class ServerView:
    mode: str                     # "tek" | "classic"
    id: str
    name: str
    install_dir: str
    map: str = ""
    server_port: int = 0
    query_port: int = 0
    rcon_port: int = 0
    use_raw_sockets: bool = False
    admin_password_set: bool = False
    progressions_enabled: Optional[bool] = None   # só TEK
    ramp_entry_count: int = 0                     # só TEK
    user_config_folder: str = ""
    status: str = STATUS_UNKNOWN
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def win64_dir(self) -> Path:
        return Path(self.install_dir) / "ShooterGame" / "Binaries" / "Win64"

    @property
    def ini_dir(self) -> Path:
        return Path(self.install_dir) / "ShooterGame" / "Saved" / "Config" / "WindowsServer"

    @property
    def safe_label(self) -> str:
        base = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.name or "servidor").strip("_") or "servidor"
        return f"{base}-{(self.id or '')[:8]}"

    def all_ports(self) -> Dict[str, int]:
        ports = {"server_port": self.server_port, "query_port": self.query_port,
                 "rcon_port": self.rcon_port}
        if self.use_raw_sockets and self.server_port:
            ports["raw_udp_port"] = self.server_port + 1
        return {k: v for k, v in ports.items() if v}


def _from_tek(item: Dict[str, Any]) -> ServerView:
    return ServerView(
        mode="tek",
        id=str(item.get("id", "")),
        name=str(item.get("name") or item.get("session_name") or ""),
        install_dir=str(item.get("install_dir") or ""),
        map=str(item.get("server_map") or ""),
        server_port=_to_int(item.get("server_port")),
        query_port=_to_int(item.get("query_port")),
        rcon_port=_to_int(item.get("rcon_port")),
        use_raw_sockets=bool(item.get("use_raw_sockets", False)),
        admin_password_set=bool(str(item.get("admin_password") or "").strip()),
        progressions_enabled=(
            bool(item["player_level_progressions_enabled"])
            if "player_level_progressions_enabled" in item else None
        ),
        ramp_entry_count=_to_int(item.get("player_ramp_entry_count")),
        user_config_folder=str(item.get("user_config_folder") or ""),
    )


def _from_classic(item: Dict[str, Any]) -> ServerView:
    return ServerView(
        mode="classic",
        id=str(item.get("id", "")),
        name=str(item.get("name") or ""),
        install_dir=str(item.get("install_dir") or ""),
        map=str(item.get("map") or ""),
        server_port=_to_int(item.get("server_port")),
        query_port=_to_int(item.get("query_port")),
        rcon_port=_to_int(item.get("rcon_port")),
        use_raw_sockets=bool(item.get("use_raw_sockets", False)),
        admin_password_set=bool(str(item.get("admin_password") or "").strip()),
    )


def load_server_views(config_dir: Path, app: Any = None) -> List[ServerView]:
    """Lê servidores TEK + clássicos do disco; se ``app`` for dado, anexa o status em execução."""
    views: List[ServerView] = []
    for fname, builder in (("asm_servers.json", _from_tek), ("servers.json", _from_classic)):
        data = read_json_file(Path(config_dir) / fname)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    try:
                        views.append(builder(item))
                    except Exception:  # noqa: BLE001
                        _LOG.warning("Servidor inválido em %s", fname, exc_info=True)
    if app is not None:
        _attach_runtime_status(views, app)
    return views


def _attach_runtime_status(views: List[ServerView], app: Any) -> None:
    for v in views:
        try:
            mgr = getattr(app, "asm_server_manager", None) if v.mode == "tek" else getattr(app, "server_manager", None)
            inst = mgr.get_instance(v.id) if mgr is not None else None
            if inst is not None:
                v.status = str(getattr(inst, "status", STATUS_UNKNOWN))
        except Exception:  # noqa: BLE001
            _LOG.debug("status de servidor indisponível", exc_info=True)
