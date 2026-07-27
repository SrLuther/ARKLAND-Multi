"""Notificações Discord para servidores TEK (webhook por servidor + global)."""
from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Any, Optional

from .asm_server_config import (
    ASM_STATUS_CRASHED,
    ASM_STATUS_RUNNING,
    ASM_STATUS_STARTING,
    ASM_STATUS_STOPPED,
    ASM_STATUS_STOPPING,
    AsmServerConfig,
)

if TYPE_CHECKING:
    pass

_TEK_TO_LEGACY_STATUS = {
    ASM_STATUS_STARTING: "starting",
    ASM_STATUS_RUNNING: "running",
    ASM_STATUS_STOPPING: "stopping",
    ASM_STATUS_STOPPED: "stopped",
    ASM_STATUS_CRASHED: "crashed",
}

_PER_SERVER_META: dict[str, tuple[str, str, int, str]] = {
    "starting": ("🟡", "Servidor iniciando", 0xF1C40F, "discord_notify_server_start"),
    "running":  ("🟢", "Servidor online",    0x2ECC71, "discord_notify_server_start"),
    "stopping": ("⏹️", "Servidor encerrando", 0xE67E22, "discord_notify_server_stop"),
    "stopped":  ("🔴", "Servidor parado",    0x95A5A6, "discord_notify_server_stop"),
    "crashed":  ("💥", "Crash detectado",    0xE74C3C, "discord_notify_server_stop"),
}


def _parse_players(raw: str) -> list[dict[str, str]]:
    players: list[dict[str, str]] = []
    for line in (raw or "").splitlines():
        m = re.match(r"^(\d+)\.\s+(.+),\s*(\d{15,17})$", line.strip())
        if m:
            players.append({"name": m.group(2).strip(), "steam_id": m.group(3).strip()})
    return players


def _build_status_detail(app: Any, srv: AsmServerConfig, status: str) -> str:
    parts: list[str] = []
    if status in ("starting", "running"):
        if srv.server_map:
            parts.append(f"map={srv.server_map}")
        if srv.server_port:
            parts.append(f"port={srv.server_port}")
    elif status == "stopped":
        inst = app.asm_server_manager.get_instance(srv.id)
        if inst and getattr(inst, "uptime_start", None):
            elapsed = int(time.time() - inst.uptime_start)
            hrs, rem = divmod(elapsed, 3600)
            mins, _ = divmod(rem, 60)
            uptime = f"{hrs}h {mins:02d}m" if hrs else f"{mins}m"
            parts.append(f"uptime={uptime}")
    return "\n".join(parts)


def notify_tek_server_status(app: Any, server_id: str, new_status: str) -> None:
    """Dispara webhooks globais e por-servidor quando o status TEK muda."""
    srv = app.asm_config_manager.get_server(server_id)
    if srv is None:
        return

    legacy = _TEK_TO_LEGACY_STATUS.get(new_status)
    if legacy:
        notifier = getattr(app, "_discord_notifier", None)
        if notifier is not None:
            notifier.notify_status(
                srv.name or server_id,
                legacy,
                detail=_build_status_detail(app, srv, legacy),
            )
        _notify_per_server_webhook(app, srv, legacy)

    try:
        from ..discord_status_board import schedule_status_board_update
        schedule_status_board_update(app)
    except Exception:
        pass


def _notify_per_server_webhook(app: Any, srv: AsmServerConfig, status: str) -> None:
    if not getattr(srv, "notify_discord_on_events", False):
        return
    url = (getattr(srv, "discord_webhook_url", "") or "").strip()
    if not url:
        return

    meta = _PER_SERVER_META.get(status)
    if not meta:
        return
    emoji, label, color, flag_name = meta
    if not getattr(srv, flag_name, False):
        return

    from ..discord_notifier import post_discord_embed_url

    fields: list[dict] = []
    if srv.server_map:
        fields.append({"name": "🗺️  Mapa", "value": srv.server_map, "inline": True})
    if srv.server_port:
        fields.append({"name": "🔌  Porta", "value": str(srv.server_port), "inline": True})

    post_discord_embed_url(
        url,
        username=srv.name or "ARKLAND",
        title=f"{emoji}  {label} — {srv.name}",
        description=f"Evento do servidor **{srv.name}**.",
        color=color,
        fields=fields or None,
    )


def poll_tek_player_discord(
    app: Any, srv: AsmServerConfig, *, players_resp: Optional[str] = None,
) -> None:
    """Detecta join/leave via ListPlayers e notifica webhook do servidor."""
    if not getattr(srv, "notify_discord_on_events", False):
        return
    url = (getattr(srv, "discord_webhook_url", "") or "").strip()
    if not url:
        return
    if not (
        getattr(srv, "discord_notify_player_join", False)
        or getattr(srv, "discord_notify_player_leave", False)
    ):
        return

    cache_key = f"_asm_discord_players_{srv.id}"
    current: dict[str, str]

    if players_resp is not None:
        current = {p["steam_id"]: p["name"] for p in _parse_players(players_resp)}
    else:
        if not (srv.rcon_enabled and srv.admin_password):
            return
        try:
            from ..rcon_client import RconClient
            host = srv.server_ip or "127.0.0.1"
            rc = RconClient(host, srv.rcon_port, srv.admin_password)
            rc.connect()
            ok, resp = rc.send_command_safe("ListPlayers")
            rc.disconnect()
            if not ok:
                return
            current = {p["steam_id"]: p["name"] for p in _parse_players(resp)}
        except Exception:
            return

    prev: dict[str, str] = getattr(app, cache_key, {})
    if not prev and current:
        setattr(app, cache_key, current)
        return

    from ..discord_notifier import post_discord_embed_url

    for sid, name in current.items():
        if sid not in prev and getattr(srv, "discord_notify_player_join", False):
            post_discord_embed_url(
                url,
                username=srv.name or "ARKLAND",
                title=f"🟢  Jogador entrou — {srv.name}",
                description=f"**{name}** conectou ao servidor.",
                color=0x2ECC71,
            )

    for sid, name in prev.items():
        if sid not in current and getattr(srv, "discord_notify_player_leave", False):
            post_discord_embed_url(
                url,
                username=srv.name or "ARKLAND",
                title=f"🔴  Jogador saiu — {srv.name}",
                description=f"**{name}** desconectou do servidor.",
                color=0x95A5A6,
            )

    setattr(app, cache_key, current)


def clear_tek_player_cache(app: Any, server_id: str) -> None:
    cache_key = f"_asm_discord_players_{server_id}"
    if hasattr(app, cache_key):
        delattr(app, cache_key)
