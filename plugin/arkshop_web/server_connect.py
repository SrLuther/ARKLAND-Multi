"""Helpers para conexão Steam direta aos servidores ARK (home pública)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

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


def diagnose_server_connect(srv: dict, settings: dict) -> Dict[str, Any]:
    """Diagnóstico admin: por que um servidor pode ou não exibir botões de conexão."""
    host = resolve_join_host(srv, settings)
    port = int(srv.get("game_port") or srv.get("server_port") or 7777)
    blockers: List[str] = []

    if not str(srv.get("server_id") or "").strip():
        blockers.append("server_id ausente")
    if srv.get("show_on_home", True) is False:
        blockers.append("show_on_home=false (oculto na home)")
    if not host:
        blockers.append(
            "sem host público — preencha join_host no servidor, game_host/public_ip, "
            "ou join_host/public_ip global nas Configurações; rcon_host só vale se não for localhost"
        )
    if port <= 0:
        blockers.append("game_port inválida ou ausente")

    view = public_server_connect_view(srv, settings)
    return {
        "server_id": str(srv.get("server_id") or ""),
        "label": str(srv.get("label") or srv.get("server_id") or ""),
        "show_on_home": srv.get("show_on_home", True) is not False,
        "can_connect": view["can_connect"],
        "resolved_host": host or "",
        "resolved_port": port,
        "connect_url": view.get("connect_url", ""),
        "join_address": view.get("join_address", ""),
        "blockers": blockers,
        "fields": {
            "join_host": str(srv.get("join_host") or ""),
            "game_host": str(srv.get("game_host") or ""),
            "public_ip": str(srv.get("public_ip") or ""),
            "game_port": port,
            "rcon_host": str(srv.get("rcon_host") or ""),
        },
        "settings_fallback": {
            "join_host": str(settings.get("join_host") or ""),
            "public_ip": str(settings.get("public_ip") or ""),
        },
    }
