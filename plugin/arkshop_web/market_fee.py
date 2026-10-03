"""Comissão do Mercado (fonte única).

Hoje o Mercado de Dinos grava ``fee_amount=0`` e a Vitrine de Recursos usa este módulo.
Se a comissão deixar de ser 0, altere ``MARKET_FEE_PERCENT`` aqui e passe a usar
``compute_market_fee`` também em ``market_listings.purchase_listing`` (mantendo as duas
vitrines sempre iguais).
"""
from __future__ import annotations

# Percentual inteiro (0–100) retido pelo sistema em cada venda P2P (hoje: taxa zero).
MARKET_FEE_PERCENT: int = 0


def compute_market_fee(price: int) -> int:
    """Valor (inteiro, em Âmbares) retido sobre ``price``."""
    amount = int(price or 0)
    if amount <= 0 or MARKET_FEE_PERCENT <= 0:
        return 0
    return min(amount, (amount * int(MARKET_FEE_PERCENT)) // 100)
