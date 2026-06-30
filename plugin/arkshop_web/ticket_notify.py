"""Coordena notificações in-app e Discord para eventos de ticket."""
from __future__ import annotations

import logging
from typing import Any, Callable

from notification_service import create_notification
from ticket_discord import notify_ticket_discord
from ticket_service import TICKET_PRIORITY_LABELS, TICKET_STATUS_LABELS, _ticket_row_to_dict

log = logging.getLogger(__name__)

_load_settings: Callable[[], dict[str, Any]] | None = None


def configure_ticket_notify(*, load_settings: Callable[[], dict[str, Any]]) -> None:
    global _load_settings
    _load_settings = load_settings


def _settings_loader() -> Callable[[], dict[str, Any]]:
    if _load_settings is not None:
        return _load_settings
    from app import _load_settings as app_load

    return app_load


def _player_notification(
    db: Any,
    ticket: dict[str, Any],
    event: str,
    *,
    actor_name: str = "",
    note: str = "",
    old_value: str | None = None,
    new_value: str | None = None,
) -> None:
    steam_id = ticket.get("steam_id")
    if not steam_id:
        return
    tid = ticket.get("id", "?")
    subject = (ticket.get("subject") or "")[:80]
    link_id = str(tid)

    if event == "reply_admin":
        title = f"Nova resposta no ticket #{tid}"
        body = f"{actor_name or 'Suporte'} respondeu: {(note or '')[:300]}"
        ntype = "ticket_reply"
    elif event == "status_changed":
        old_l = TICKET_STATUS_LABELS.get(old_value or "", old_value or "")
        new_l = TICKET_STATUS_LABELS.get(new_value or "", new_value or "")
        title = f"Status do ticket #{tid} atualizado"
        body = f"{subject} — {old_l} → {new_l}"
        ntype = "ticket_status"
    elif event == "attended":
        title = f"Ticket #{tid} em atendimento"
        body = f"{subject} — a equipe está analisando seu pedido."
        ntype = "ticket_attended"
    elif event == "closed":
        title = f"Ticket #{tid} encerrado"
        body = subject
        if note:
            body += f" — {note[:200]}"
        ntype = "ticket_closed"
    elif event == "priority_changed":
        old_l = TICKET_PRIORITY_LABELS.get(old_value or "", old_value or "")
        new_l = TICKET_PRIORITY_LABELS.get(new_value or "", new_value or "")
        title = f"Prioridade do ticket #{tid} alterada"
        body = f"{subject} — {old_l} → {new_l}"
        ntype = "ticket_priority"
    else:
        return

    create_notification(
        db,
        steam_id=steam_id,
        type=ntype,
        title=title,
        body=body,
        link_type="ticket",
        link_id=link_id,
    )


def notify_ticket_update(
    db: Any,
    ticket_id: int,
    event: str,
    *,
    actor_steam_id: str | None = None,
    actor_name: str = "",
    note: str = "",
    old_value: str | None = None,
    new_value: str | None = None,
) -> None:
    from app import SupportTicket

    ticket_row = db.get(SupportTicket, ticket_id)
    if not ticket_row:
        return
    ticket = _ticket_row_to_dict(ticket_row)

    player_events = {
        "reply_admin",
        "status_changed",
        "attended",
        "closed",
        "priority_changed",
    }
    if event in player_events:
        try:
            _player_notification(
                db,
                ticket,
                event,
                actor_name=actor_name,
                note=note,
                old_value=old_value,
                new_value=new_value,
            )
            db.commit()
        except Exception as exc:
            log.warning("Notificação in-app ticket #%s: %s", ticket_id, exc)
            try:
                db.rollback()
            except Exception:
                pass

    try:
        notify_ticket_discord(
            _settings_loader(),
            ticket,
            event,
            actor_name=actor_name,
            note=note,
            old_value=old_value,
            new_value=new_value,
        )
    except Exception as exc:
        log.warning("Discord ticket #%s: %s", ticket_id, exc)
