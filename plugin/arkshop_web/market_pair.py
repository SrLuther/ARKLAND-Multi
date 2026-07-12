"""Venda em casal (M+F) — pricing e validação (§8.7.3–8.7.4).

Checkout: Y = round((P1 + P2) × 0.60)
Pote sorteio: round((P1 + P2) × 0.40)  — crédito de sistema, sem débito extra ao vendedor.
Desistência / claim expirado: reembolso ao comprador = round(0.60 × Y); pote sem estorno.
Repartição de tribo (se ativa): aplica-se sobre Y (crédito do vendedor), não sobre S.
"""
from __future__ import annotations

from typing import Any

PAIR_BUYER_FACTOR = 0.60
PAIR_PRIZE_FACTOR = 0.40
PAIR_CLAIM_REFUND_FACTOR = 0.60


def pair_sum_asking(price_a: int, price_b: int) -> int:
    return max(0, int(price_a)) + max(0, int(price_b))


def pair_checkout_price(price_a: int, price_b: int) -> int:
    """Y = (P1 + P2) × 0,60 — valor pago pelo comprador e recebido pelo vendedor."""
    return int(round(pair_sum_asking(price_a, price_b) * PAIR_BUYER_FACTOR))


def pair_prize_contribution(price_a: int, price_b: int) -> int:
    """Crédito de sistema ao pote: 0,40 × S."""
    return int(round(pair_sum_asking(price_a, price_b) * PAIR_PRIZE_FACTOR))


def pair_claim_refund(price_paid: int) -> int:
    """Reembolso ao comprador em desistência/expiração de casal: 60% do valor pago (Y)."""
    return int(round(max(0, int(price_paid)) * PAIR_CLAIM_REFUND_FACTOR))


def pair_pricing_breakdown(price_a: int, price_b: int) -> dict[str, int]:
    s = pair_sum_asking(price_a, price_b)
    y = pair_checkout_price(price_a, price_b)
    pot = pair_prize_contribution(price_a, price_b)
    return {
        "asking_a": int(price_a),
        "asking_b": int(price_b),
        "sum_asking": s,
        "checkout_price": y,
        "prize_contribution": pot,
    }


def validate_pair_eligibility(listing_a: Any, listing_b: Any) -> None:
    """Valida mesma espécie, sexos opostos, mesmo vendedor e status editável."""
    if listing_a is None or listing_b is None:
        raise ValueError("Anúncios do casal não encontrados")
    if int(listing_a.id) == int(listing_b.id):
        raise ValueError("Não é possível formar casal com o mesmo anúncio")
    if str(listing_a.seller_steam_id) != str(listing_b.seller_steam_id):
        raise ValueError("Os dois dinos devem ser do mesmo vendedor")
    sk_a = (listing_a.species_key or "").strip()
    sk_b = (listing_b.species_key or "").strip()
    if not sk_a or not sk_b or sk_a != sk_b:
        raise ValueError("Casal exige a mesma espécie")
    if bool(listing_a.is_female) == bool(listing_b.is_female):
        raise ValueError("Casal exige um macho e uma fêmea")
    editable = ("DRAFT", "PAUSED", "PENDING_CLASSIFICATION", "ACTIVE")
    for row, label in ((listing_a, "A"), (listing_b, "B")):
        if row.status not in editable:
            raise ValueError(f"Anúncio {label} não permite vínculo de casal (status={row.status})")
        mate_id = getattr(row, "pair_mate_listing_id", None)
        if mate_id and int(mate_id) not in (int(listing_a.id), int(listing_b.id)):
            raise ValueError(f"Anúncio {label} já está vinculado a outro casal")


def is_pair_listing(row: Any) -> bool:
    mate = getattr(row, "pair_mate_listing_id", None)
    return mate is not None and int(mate) > 0


def is_pair_primary(row: Any) -> bool:
    """Card público / checkout: o anúncio de menor id do par é o primário."""
    if not is_pair_listing(row):
        return False
    mate_id = int(row.pair_mate_listing_id)
    return int(row.id) < mate_id
