"""Helpers para conexão Steam direta aos servidores ARK (home pública)."""
from __future__ import annotations

from typing import Any, Dict, Optional

_LOCALHOST = frozenset({"127.0.0.1", "localhost", "::1", "0.0.0.0"})


def _is_localhost(host: str) -> bool:
    return (host or "").strip().lower() in _LOCALHOST


def resolve_join_host(srv: dict, settings: dict) -> Optional[str]:
    """Resolve o host público para join Steam.

    Prioridade: join_host no servidor → game_host → public_ip no servidor →
    join_host/public_ip nas settings → rcon_host se não for localhost.
    """
    join = str(srv.get("join_host") or "").strip()
    if join:
        return join

    game_host = str(srv.get("game_host") or "").strip()
    if game_host and not _is_localhost(game_host):
        return game_host

    public_ip = str(srv.get("public_ip") or "").strip()
    if public_ip:
        return public_ip

    for key in ("join_host", "public_ip"):
        val = str(settings.get(key) or "").strip()
        if val:
            return val

    rcon_host = str(srv.get("rcon_host") or "").strip()
    if rcon_host and not _is_localhost(rcon_host):
        return rcon_host

    return None


def build_steam_connect_url(host: str, port: int) -> str:
    return f"steam://connect/{host}:{int(port)}"


def build_join_address(host: str, port: int) -> str:
    return f"{host}:{int(port)}"


def public_server_connect_view(srv: dict, settings: dict) -> Dict[str, Any]:
    """Campos públicos de conexão para a home (sem credenciais RCON)."""
    host = resolve_join_host(srv, settings)
    port = int(srv.get("game_port") or srv.get("server_port") or 7777)
    can_connect = bool(host and port > 0)

    out: Dict[str, Any] = {
        "connect_url": build_steam_connect_url(host, port) if can_connect else "",
        "join_address": build_join_address(host, port) if can_connect else "",
        "can_connect": can_connect,
        "game_port": port,
    }

    map_name = str(srv.get("server_map") or srv.get("map") or "").strip()
    if map_name:
        out["map"] = map_name

    return out
