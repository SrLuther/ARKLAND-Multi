"""Notificações in-app e auditoria da vitrine para vendedores do Comércio."""
from __future__ import annotations

import logging
from typing import Any

from market_audit import market_audit_event
from notification_service import create_notification

log = logging.getLogger("arkshop.market_notify")

SELLER_VITRINE_EVENT_TYPES = frozenset({
    "MARKET_SELLER_LISTING_SOLD",
    "MARKET_SELLER_BUYER_CLAIMED",
    "MARKET_SELLER_LISTING_ADMIN_FLAGGED",
    "MARKET_SELLER_LISTING_ADMIN_REMOVED",
})


def seller_vitrine_audit_event(
    db: Any,
    event_type: str,
    *,
    seller_steam_id: str,
    listing_id: int,
    admin_steam_id: str | None = None,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
    market_trace_id: str | None = None,
    effective_price: int | None = None,
    claim_id: int | None = None,
) -> None:
    """Registra evento na auditoria da vitrine (visível ao vendedor)."""
    meta: dict[str, Any] = dict(metadata or {})
    if reason:
        meta["reason"] = reason[:280]
    market_audit_event(
        db,
        event_type,
        steam_id=seller_steam_id,
        counterparty_steam_id=admin_steam_id,
        listing_id=listing_id,
        claim_id=claim_id,
        effective_price=effective_price,
        market_trace_id=market_trace_id,
        metadata=meta or None,
        commit=True,
    )


def notify_seller_listing_sold(
    db: Any,
    *,
    seller_steam_id: str,
    listing_id: int,
    listing_title: str,
    price: int,
    buyer_display_name: str | None = None,
    market_trace_id: str | None = None,
) -> None:
    buyer = (buyer_display_name or "um jogador").strip()
    title = f"Anúncio vendido — {listing_title[:60]}"
    body = (
        f"{buyer} comprou seu anúncio #{listing_id} por "
        f"{int(price):,} Âmbar. Aguarde o resgate do comprador."
    ).replace(",", ".")
    create_notification(
        db,
        steam_id=seller_steam_id,
        type="market_sale",
        title=title,
        body=body,
        link_type="market",
        link_id=str(listing_id),
    )
    db.commit()
    seller_vitrine_audit_event(
        db,
        "MARKET_SELLER_LISTING_SOLD",
        seller_steam_id=seller_steam_id,
        listing_id=listing_id,
        effective_price=price,
        market_trace_id=market_trace_id,
        metadata={"buyer_display_name": buyer_display_name, "price": price},
    )


def notify_seller_buyer_claimed(
    db: Any,
    *,
    seller_steam_id: str,
    listing_id: int,
    listing_title: str,
    buyer_display_name: str | None = None,
    market_trace_id: str | None = None,
    claim_id: int | None = None,
) -> None:
    buyer = (buyer_display_name or "O comprador").strip()
    title = f"Resgate concluído — {listing_title[:60]}"
    body = f"{buyer} resgatou o dino do anúncio #{listing_id} in-game."
    create_notification(
        db,
        steam_id=seller_steam_id,
        type="market_buyer_claimed",
        title=title,
        body=body,
        link_type="market",
        link_id=str(listing_id),
    )
    db.commit()
    seller_vitrine_audit_event(
        db,
        "MARKET_SELLER_BUYER_CLAIMED",
        seller_steam_id=seller_steam_id,
        listing_id=listing_id,
        claim_id=claim_id,
        market_trace_id=market_trace_id,
        metadata={"buyer_display_name": buyer_display_name},
    )


def notify_seller_listing_flagged(
    db: Any,
    *,
    seller_steam_id: str,
    listing_id: int,
    listing_title: str,
    admin_steam_id: str,
    reason: str = "",
    paused: bool = False,
    market_trace_id: str | None = None,
) -> None:
    title = f"Anúncio sinalizado pela moderação — {listing_title[:50]}"
    parts = [f"Seu anúncio #{listing_id} foi marcado como abusivo pela equipe."]
    if paused:
        parts.append("O anúncio foi pausado até revisão.")
    if reason.strip():
        parts.append(f"Motivo: {reason.strip()[:200]}")
    body = " ".join(parts)
    create_notification(
        db,
        steam_id=seller_steam_id,
        type="market_admin_flag",
        title=title,
        body=body,
        link_type="market",
        link_id=str(listing_id),
    )
    db.commit()
    seller_vitrine_audit_event(
        db,
        "MARKET_SELLER_LISTING_ADMIN_FLAGGED",
        seller_steam_id=seller_steam_id,
        listing_id=listing_id,
        admin_steam_id=admin_steam_id,
        reason=reason,
        market_trace_id=market_trace_id,
        metadata={"paused": paused},
    )


def notify_seller_listing_removed(
    db: Any,
    *,
    seller_steam_id: str,
    listing_id: int,
    listing_title: str,
    admin_steam_id: str,
    reason: str = "",
    claim_id: int | None = None,
    market_trace_id: str | None = None,
) -> None:
    title = f"Anúncio removido pela moderação — {listing_title[:50]}"
    parts = [
        f"Seu anúncio #{listing_id} foi removido pela equipe.",
        "Use /mercado in-game em até 24h para recuperar a cryopod.",
    ]
    if reason.strip():
        parts.append(f"Motivo: {reason.strip()[:200]}")
    body = " ".join(parts)
    create_notification(
        db,
        steam_id=seller_steam_id,
        type="market_admin_remove",
        title=title,
        body=body,
        link_type="market",
        link_id=str(listing_id),
    )
    db.commit()
    seller_vitrine_audit_event(
        db,
        "MARKET_SELLER_LISTING_ADMIN_REMOVED",
        seller_steam_id=seller_steam_id,
        listing_id=listing_id,
        admin_steam_id=admin_steam_id,
        reason=reason,
        claim_id=claim_id,
        market_trace_id=market_trace_id,
    )


def notify_staff_market_alert(
    db: Any,
    *,
    title: str,
    body: str,
    listing_id: int | None = None,
    severity: str = "WARN",
) -> None:
    """Notifica admins e equipe de suporte sobre eventos críticos do mercado."""
    try:
        from app import _load_admin_steamids, _load_support_steamids

        recipients = set(_load_admin_steamids()) | set(_load_support_steamids())
    except Exception as exc:
        log.warning("notify_staff_market_alert: falha ao carregar staff: %s", exc)
        return
    if not recipients:
        return
    ntype = "market_staff_critical" if severity.upper() == "CRITICAL" else "market_staff_alert"
    link_id = str(listing_id) if listing_id else None
    for steam_id in recipients:
        try:
            create_notification(
                db,
                steam_id=steam_id,
                type=ntype,
                title=title[:200],
                body=body[:2000],
                link_type="market_admin" if listing_id else None,
                link_id=link_id,
            )
        except Exception as exc:
            log.warning("notify_staff_market_alert steam=%s: %s", steam_id, exc)
    try:
        db.commit()
    except Exception:
        pass
