"""Notificações de tickets no Discord (canal staff)."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Callable

from ticket_service import TICKET_PRIORITY_LABELS, TICKET_STATUS_LABELS

log = logging.getLogger(__name__)

_EVENT_LABELS: dict[str, str] = {
    "created": "Novo ticket",
    "reply_admin": "Resposta do suporte",
    "reply_player": "Resposta do jogador",
    "status_changed": "Status alterado",
    "attended": "Ticket em atendimento",
    "closed": "Ticket encerrado",
    "close_requested": "Encerramento solicitado",
    "priority_changed": "Prioridade alterada",
    "attachment_added": "Anexo adicionado",
    "order_linked": "Pedido vinculado",
}


def load_ticket_discord_config(load_settings: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Lê config de notificações de ticket no Discord (settings.json + env)."""
    import os

    s = load_settings()
    enabled = bool(s.get("ticket_discord_enabled", False))
    channel_id = str(s.get("ticket_discord_channel_id", "")).strip()
    token = str(s.get("ticket_discord_token", "")).strip()

    env_enabled = os.environ.get("ARKSHOP_TICKET_DISCORD_ENABLED", "").strip().lower()
    if env_enabled in ("1", "true", "yes", "on"):
        enabled = True
    elif env_enabled in ("0", "false", "no", "off"):
        enabled = False

    if not channel_id:
        channel_id = os.environ.get("ARKSHOP_TICKET_DISCORD_CHANNEL_ID", "").strip()
    if not token:
        token = os.environ.get("ARKSHOP_TICKET_DISCORD_TOKEN", "").strip()

    try:
        ch_id = int(channel_id) if channel_id else 0
    except ValueError:
        ch_id = 0

    token_source = "ticket" if token else "none"

    return {
        "enabled": enabled and bool(token) and ch_id > 0,
        "requested_enabled": enabled,
        "token_set": bool(token),
        "token_source": token_source,
        "channel_id": ch_id,
        "_token": token,
    }


def ticket_discord_status(load_settings: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    cfg = load_ticket_discord_config(load_settings)
    s = load_settings()
    missing: list[str] = []
    if not s.get("ticket_discord_enabled"):
        missing.append("enabled")
    if not cfg.get("token_set"):
        missing.append("token")
    if not cfg.get("channel_id"):
        missing.append("channel_id")

    if not cfg.get("requested_enabled"):
        status_message = "Desativado"
    elif missing:
        labels = {"enabled": "ativação", "token": "token do bot", "channel_id": "ID do canal"}
        status_message = "Config incompleta: falta " + ", ".join(labels.get(m, m) for m in missing)
    elif cfg["enabled"]:
        status_message = f"Pronto — canal {cfg['channel_id']} (token dedicado)"
    else:
        status_message = "Desativado"

    return {
        "enabled": cfg["enabled"],
        "requested_enabled": cfg.get("requested_enabled", False),
        "status_message": status_message,
        "channel_id": cfg.get("channel_id") or 0,
        "token_set": cfg.get("token_set", False),
        "token_source": cfg.get("token_source", "none"),
        "missing": missing,
    }


def _status_label(code: str | None) -> str:
    if not code:
        return ""
    return TICKET_STATUS_LABELS.get(code, code)


def format_ticket_discord_message(
    ticket: dict[str, Any],
    event: str,
    *,
    actor_name: str = "",
    note: str = "",
    old_value: str | None = None,
    new_value: str | None = None,
) -> str:
    tid = ticket.get("id", "?")
    subject = (ticket.get("subject") or "")[:120]
    player = ticket.get("player_name") or ticket.get("steam_id") or "?"
    cat = ticket.get("category_label") or ticket.get("category") or ""
    pri = ticket.get("priority_label") or ticket.get("priority") or ""
    status = ticket.get("status_label") or _status_label(ticket.get("status"))
    label = _EVENT_LABELS.get(event, event)

    lines = [
        f"**[{label}]** Ticket **#{tid}** — {subject}",
        f"Jogador: **{player}** · {cat} · {pri} · {status}",
    ]
    if actor_name:
        lines.append(f"Por: {actor_name}")
    if old_value and new_value:
        lines.append(f"Alteração: `{old_value}` → `{new_value}`")
    elif new_value:
        lines.append(f"Novo valor: `{new_value}`")
    if note:
        lines.append(f"> {(note or '')[:400]}")
    return "\n".join(lines)[:1900]


def send_discord_channel_message(token: str, channel_id: int, content: str) -> bool:
    if not token or channel_id <= 0 or not content.strip():
        return False
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    payload = json.dumps({"content": content[:2000]}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
            "User-Agent": "arkshop_web/ticket-notify",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as exc:
        log.warning("Ticket Discord: HTTP %s — %s", exc.code, exc.read()[:200])
        return False
    except Exception as exc:
        log.warning("Ticket Discord: envio falhou: %s", exc)
        return False


def notify_ticket_discord(
    load_settings: Callable[[], dict[str, Any]],
    ticket: dict[str, Any],
    event: str,
    *,
    actor_name: str = "",
    note: str = "",
    old_value: str | None = None,
    new_value: str | None = None,
) -> bool:
    cfg = load_ticket_discord_config(load_settings)
    if not cfg["enabled"]:
        return False
    msg = format_ticket_discord_message(
        ticket,
        event,
        actor_name=actor_name,
        note=note,
        old_value=old_value,
        new_value=new_value,
    )
    return send_discord_channel_message(
        str(cfg.get("_token") or ""),
        int(cfg.get("channel_id") or 0),
        msg,
    )
