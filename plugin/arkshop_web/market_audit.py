"""Auditoria dedicada do Mercado de Dinos (market_audit_events)."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable

log = logging.getLogger("arkshop.market_audit")

WEB_VERSION = "1.0.0"

# Labels PT-BR para auditoria admin (superset da vitrine vendedor)
MARKET_ADMIN_AUDIT_LABELS: dict[str, str] = {
    "MARKET_DISPLAY_NAME_CHANGED": "Nome da vitrine alterado",
    "MARKET_UPLOAD_CONFIRMED": "Upload cryopod confirmado",
    "MARKET_SPECIES_PENDING": "Espécie pendente de classificação",
    "MARKET_LISTING_ACTIVATED": "Anúncio ativado",
    "MARKET_LISTING_PRICE_SET": "Preço definido",
    "MARKET_PURCHASE_COMPLETED": "Compra concluída",
    "MARKET_CLAIM_DELIVERED": "Claim entregue",
    "MARKET_CLAIM_EXPIRED": "Claim expirado",
    "MARKET_CLAIM_REFUNDED": "Claim reembolsado",
    "MARKET_LISTING_PAUSED": "Anúncio pausado",
    "MARKET_LISTING_WITHDRAW_REQUESTED": "Resgate solicitado (vendedor)",
    "MARKET_LISTING_ADMIN_REMOVED": "Moderação: removido",
    "MARKET_LISTING_ADMIN_PRICE": "Moderação: preço ajustado",
    "MARKET_LISTING_ADMIN_FLAGGED": "Moderação: sinalizado",
    "MARKET_LISTING_CLASSIFIED": "Espécie classificada",
    "MARKET_LISTING_PROMOTED": "Anúncio promovido",
    "MARKET_LISTING_RECOMPUTED": "Economia recalculada",
    "MARKET_SELLER_LISTING_SOLD": "Venda (vitrine)",
    "MARKET_SELLER_BUYER_CLAIMED": "Comprador resgatou (vitrine)",
    "MARKET_SELLER_LISTING_ADMIN_FLAGGED": "Sinalizado (vitrine)",
    "MARKET_SELLER_LISTING_ADMIN_REMOVED": "Removido (vitrine)",
    "MARKET_SELLER_RECLAIM_DELIVERED": "Devolução após remoção admin",
    "MARKET_LISTING_BULK_ADMIN_ACTION": "Ação em lote (moderação)",
    "MARKET_TICKET_LINKED": "Ticket vinculado",
}


def market_audit_label(event_type: str) -> str:
    return MARKET_ADMIN_AUDIT_LABELS.get(event_type or "", event_type or "—")


def market_audit_event(
    db: Any,
    event_type: str,
    *,
    severity: str = "INFO",
    source: str = "web",
    steam_id: str | None = None,
    counterparty_steam_id: str | None = None,
    market_display_name: str | None = None,
    listing_id: int | None = None,
    vault_id: int | None = None,
    claim_id: int | None = None,
    blob_hash: str | None = None,
    computed_base_value: int | None = None,
    effective_price: int | None = None,
    points_delta: int | None = None,
    points_before: int | None = None,
    points_after: int | None = None,
    market_trace_id: str | None = None,
    parser_version: str | None = None,
    plugin_version: str | None = None,
    metadata: dict[str, Any] | None = None,
    commit: bool = True,
) -> None:
    from app import MarketAuditEvent

    meta_str: str | None = None
    if metadata:
        try:
            meta_str = json.dumps(metadata, ensure_ascii=False, default=str)
            if len(meta_str) > 65536:
                meta_str = meta_str[:65536]
        except Exception:
            meta_str = str(metadata)[:65536]

    row = MarketAuditEvent(
        market_trace_id=market_trace_id,
        event_type=event_type,
        severity=severity.upper(),
        steam_id=steam_id,
        counterparty_steam_id=counterparty_steam_id,
        market_display_name=market_display_name,
        listing_id=listing_id,
        vault_id=vault_id,
        claim_id=claim_id,
        blob_hash=blob_hash,
        computed_base_value=computed_base_value,
        effective_price=effective_price,
        points_delta=points_delta,
        points_before=points_before,
        points_after=points_after,
        parser_version=parser_version,
        plugin_version=plugin_version,
        web_version=WEB_VERSION,
        source=source,
        metadata_json=meta_str,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    if commit:
        db.commit()

    log.info(
        "market_audit %s trace=%s listing=%s steam=%s",
        event_type,
        market_trace_id,
        listing_id,
        steam_id,
    )


def mirror_critical_to_shop_audit(
    shop_audit_fn: Callable[..., None],
    event_type: str,
    *,
    severity: str = "CRITICAL",
    **kwargs: Any,
) -> None:
    """Espelha eventos CRITICAL no audit_events geral (§9.8)."""
    if severity.upper() != "CRITICAL":
        return
    shop_audit_fn(
        event_type,
        severity=severity.lower(),
        source=kwargs.get("source", "web"),
        message=kwargs.get("message") or event_type,
        **{k: v for k, v in kwargs.items() if k not in ("source", "message")},
    )
