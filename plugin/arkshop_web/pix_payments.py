"""Integração Mercado Pago (PIX) para doações de pontos."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any


class PixPaymentError(Exception):
    pass


class PayerValidationError(Exception):
    """Dados do pagador inválidos ou incompletos."""

    def __init__(self, message: str, *, field: str | None = None):
        super().__init__(message)
        self.field = field


# Campos solicitados ao jogador — exigidos pelo Mercado Pago para validar a doação PIX (Brasil).
PIX_PAYER_FORM: list[dict[str, Any]] = [
    {
        "id": "email",
        "label": "E-mail",
        "hint": "Exigido pelo Mercado Pago — comprovante da doação",
        "type": "email",
        "required": True,
        "mp_key": "email",
    },
    {
        "id": "full_name",
        "label": "Nome completo",
        "hint": "Exigido pelo Mercado Pago — validação da doação",
        "type": "text",
        "required": True,
        "mp_key": "name",
    },
    {
        "id": "cpf",
        "label": "CPF",
        "hint": "Exigido pelo Mercado Pago para PIX no Brasil",
        "type": "cpf",
        "required": True,
        "mp_key": "identification",
    },
    {
        "id": "phone",
        "label": "Telefone (celular)",
        "hint": "Opcional — repassado ao MP somente se informado",
        "type": "phone",
        "required": False,
        "mp_key": "phone",
    },
]


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _validate_email(value: str) -> str:
    email = (value or "").strip().lower()
    if not email or "@" not in email or email.endswith(".local"):
        raise PayerValidationError("Informe um e-mail válido.", field="email")
    local, _, domain = email.partition("@")
    if not local or not domain or "." not in domain:
        raise PayerValidationError("Informe um e-mail válido.", field="email")
    return email


def _validate_cpf(value: str) -> str:
    cpf = _digits(value)
    if len(cpf) != 11:
        raise PayerValidationError("CPF deve ter 11 dígitos.", field="cpf")
    if cpf == cpf[0] * 11:
        raise PayerValidationError("CPF inválido.", field="cpf")
    nums = [int(c) for c in cpf]
    for pos in (9, 10):
        total = sum(n * w for n, w in zip(nums[:pos], range(pos + 1, 1, -1)))
        digit = (total * 10) % 11 % 10
        if digit != nums[pos]:
            raise PayerValidationError("CPF inválido.", field="cpf")
    return cpf


def _split_full_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in re.split(r"\s+", (full_name or "").strip()) if p]
    if len(parts) < 2:
        raise PayerValidationError("Informe nome e sobrenome.", field="full_name")
    return parts[0], " ".join(parts[1:])


def _parse_phone(value: str) -> dict[str, str] | None:
    raw = (value or "").strip()
    if not raw:
        return None
    digits = _digits(raw)
    if len(digits) < 10:
        raise PayerValidationError("Telefone inválido — use DDD + número.", field="phone")
    if len(digits) == 10:
        return {"area_code": digits[:2], "number": digits[2:]}
    if len(digits) == 11:
        return {"area_code": digits[:2], "number": digits[2:]}
    raise PayerValidationError("Telefone inválido — use DDD + número.", field="phone")


def normalize_payer_input(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Valida dados informados pelo jogador e monta objeto payer para a API MP."""
    data = raw if isinstance(raw, dict) else {}
    email = _validate_email(str(data.get("email", "")))
    first_name, last_name = _split_full_name(str(data.get("full_name", "")))
    cpf = _validate_cpf(str(data.get("cpf", "")))
    phone = _parse_phone(str(data.get("phone", "")))

    payer: dict[str, Any] = {
        "email": email,
        "first_name": first_name[:255],
        "last_name": last_name[:255],
        "identification": {"type": "CPF", "number": cpf},
    }
    if phone:
        payer["phone"] = phone
    return payer


def parse_mp_error_message(raw: str) -> str:
    """Extrai mensagem legível de erro JSON do Mercado Pago."""
    text = (raw or "").strip()
    if not text:
        return "Erro desconhecido do Mercado Pago"
    try:
        data = json.loads(text)
    except Exception:
        return text[:500]
    if isinstance(data, dict):
        causes = data.get("cause") or []
        if isinstance(causes, list) and causes:
            parts: list[str] = []
            for c in causes:
                if not isinstance(c, dict):
                    continue
                desc = c.get("description") or c.get("code") or ""
                if desc:
                    parts.append(str(desc))
            if parts:
                return "; ".join(parts)
        msg = data.get("message") or data.get("error")
        if msg:
            return str(msg)
    return text[:500]


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
        raise PixPaymentError(parse_mp_error_message(detail) or str(exc)) from exc
    except Exception as exc:
        raise PixPaymentError(str(exc)) from exc


def create_pix_payment(
    access_token: str,
    *,
    amount_brl: float,
    description: str,
    external_reference: str,
    idempotency_key: str,
    payer: dict[str, Any],
) -> dict[str, Any]:
    if not payer or not payer.get("email"):
        raise PayerValidationError("Dados do pagador são obrigatórios.", field="email")
    payload = {
        "transaction_amount": round(float(amount_brl), 2),
        "description": description[:256],
        "payment_method_id": "pix",
        "external_reference": external_reference[:256],
        "payer": payer,
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
    if s in ("approved", "accredited", "authorized"):
        return "APROVADO"
    if s in ("rejected", "cancelled"):
        return "RECUSADO"
    if s in ("refunded", "charged_back"):
        return "ESTORNADO"
    if s in ("expired",):
        return "EXPIRADO"
    return "PENDENTE"
