"""Integração Mercado Pago (PIX) para recarga de pontos."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class PixPaymentError(Exception):
    pass


def _mp_request(
    access_token: str,
    method: str,
    path: str,
    payload: dict | None = None,
    *,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["X-Idempotency-Key"] = idempotency_key
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        f"https://api.mercadopago.com{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise PixPaymentError(detail or str(exc)) from exc
    except Exception as exc:
        raise PixPaymentError(str(exc)) from exc


def create_pix_payment(
    access_token: str,
    *,
    amount_brl: float,
    description: str,
    external_reference: str,
    idempotency_key: str,
) -> dict[str, Any]:
    payload = {
        "transaction_amount": round(float(amount_brl), 2),
        "description": description[:256],
        "payment_method_id": "pix",
        "external_reference": external_reference[:256],
        "payer": {"email": "pagamentos@arkland.local"},
    }
    return _mp_request(
        access_token,
        "POST",
        "/v1/payments",
        payload,
        idempotency_key=idempotency_key,
    )


def fetch_payment(access_token: str, mp_payment_id: str) -> dict[str, Any]:
    return _mp_request(access_token, "GET", f"/v1/payments/{mp_payment_id}")


def extract_pix_data(mp_response: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Retorna (mp_payment_id, qr_code_base64, copy_paste)."""
    mp_id = str(mp_response.get("id", "") or "")
    poi = mp_response.get("point_of_interaction") or {}
    tx = poi.get("transaction_data") or {}
    qr_b64 = tx.get("qr_code_base64")
    copy_paste = tx.get("qr_code") or tx.get("ticket_url")
    return mp_id or None, qr_b64, copy_paste


def map_mp_status(status: str) -> str:
    s = (status or "").lower()
    if s in ("approved",):
        return "APROVADO"
    if s in ("rejected", "cancelled"):
        return "RECUSADO"
    if s in ("refunded", "charged_back"):
        return "ESTORNADO"
    if s in ("expired",):
        return "EXPIRADO"
    return "PENDENTE"
