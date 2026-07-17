"""Integração Mercado Pago (PIX e cartão) para doações de pontos."""
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


# Campos PIX — Brasil: CPF e telefone celular obrigatórios (Mercado Pago).
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
        "hint": "Obrigatório para PIX — DDD + número (Brasil)",
        "type": "phone",
        "required": True,
        "mp_key": "phone",
    },
]

# Cartão — internacional: e-mail e nome obrigatórios; documento opcional (CPF ou passaporte).
CARD_PAYER_FORM: list[dict[str, Any]] = [
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
        "id": "identification",
        "label": "CPF ou passaporte",
        "hint": "Opcional — brasileiros podem informar CPF; internacionais, passaporte ou documento",
        "type": "identification",
        "required": False,
        "mp_key": "identification",
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


def _parse_optional_identification(value: str) -> dict[str, str] | None:
    raw = (value or "").strip()
    if not raw:
        return None
    digits = _digits(raw)
    if len(digits) == 11:
        cpf = _validate_cpf(raw)
        return {"type": "CPF", "number": cpf}
    doc = re.sub(r"[^A-Za-z0-9]", "", raw)
    if len(doc) < 5 or len(doc) > 20:
        raise PayerValidationError(
            "Documento inválido — informe CPF (11 dígitos) ou passaporte (5–20 caracteres).",
            field="identification",
        )
    return {"type": "Otro", "number": doc.upper()}


def normalize_pix_payer_input(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Valida pagador PIX (Brasil): e-mail, nome, CPF e telefone celular."""
    data = raw if isinstance(raw, dict) else {}
    email = _validate_email(str(data.get("email", "")))
    first_name, last_name = _split_full_name(str(data.get("full_name", "")))
    cpf = _validate_cpf(str(data.get("cpf", "")))
    phone_raw = str(data.get("phone", "")).strip()
    if not phone_raw:
        raise PayerValidationError("Telefone celular é obrigatório para PIX.", field="phone")
    phone = _parse_phone(phone_raw)
    if not phone:
        raise PayerValidationError("Telefone celular é obrigatório para PIX.", field="phone")

    payer: dict[str, Any] = {
        "email": email,
        "first_name": first_name[:255],
        "last_name": last_name[:255],
        "identification": {"type": "CPF", "number": cpf},
        "phone": phone,
    }
    return payer


def normalize_card_payer_input(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Valida pagador cartão: e-mail e nome obrigatórios; documento opcional."""
    data = raw if isinstance(raw, dict) else {}
    email = _validate_email(str(data.get("email", "")))
    first_name, last_name = _split_full_name(str(data.get("full_name", "")))
    identification = _parse_optional_identification(str(data.get("identification", "")))

    payer: dict[str, Any] = {
        "email": email,
        "first_name": first_name[:255],
        "last_name": last_name[:255],
    }
    if identification:
        payer["identification"] = identification
    return payer


def normalize_payer_input(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Alias retrocompatível — validação PIX."""
    return normalize_pix_payer_input(raw)


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
    timeout: float = 30.0,
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
        with urllib.request.urlopen(req, timeout=max(2.0, float(timeout))) as resp:
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


def fetch_payment(
    access_token: str,
    mp_payment_id: str,
    *,
    timeout: float = 30.0,
) -> dict[str, Any]:
    return _mp_request(
        access_token, "GET", f"/v1/payments/{mp_payment_id}", timeout=timeout,
    )


def extract_pix_data(mp_response: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Retorna (mp_payment_id, qr_code_base64, copy_paste)."""
    mp_id = str(mp_response.get("id", "") or "")
    poi = mp_response.get("point_of_interaction") or {}
    tx = poi.get("transaction_data") or {}
    qr_raw = tx.get("qr_code_base64")
    copy_raw = tx.get("qr_code") or tx.get("ticket_url")
    qr_b64 = str(qr_raw).strip() if qr_raw is not None and str(qr_raw).strip() else None
    copy_paste = str(copy_raw).strip() if copy_raw is not None and str(copy_raw).strip() else None
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


def create_card_checkout_preference(
    access_token: str,
    *,
    amount_brl: float,
    description: str,
    external_reference: str,
    payer: dict[str, Any],
    back_urls: dict[str, str],
) -> dict[str, Any]:
    """Checkout Pro — cartão de crédito/débito (PIX excluído; fluxo PIX usa API direta)."""
    if not payer or not payer.get("email"):
        raise PayerValidationError("Dados do pagador são obrigatórios.", field="email")
    success_url = str(back_urls.get("success") or "").strip()[:512]
    failure_url = str(back_urls.get("failure") or "").strip()[:512]
    pending_url = str(back_urls.get("pending") or "").strip()[:512]
    if not success_url:
        raise PixPaymentError("URL de retorno (success) não configurada — defina public_url em settings")
    payload: dict[str, Any] = {
        "items": [
            {
                "title": description[:256],
                "quantity": 1,
                "unit_price": round(float(amount_brl), 2),
                "currency_id": "BRL",
            }
        ],
        "payer": {
            "email": payer.get("email"),
            "name": payer.get("first_name"),
            "surname": payer.get("last_name"),
        },
        "external_reference": external_reference[:256],
        "back_urls": {
            "success": success_url,
            "failure": failure_url,
            "pending": pending_url,
        },
        "statement_descriptor": "ARKLAND",
        "payment_methods": {
            "excluded_payment_types": [
                {"id": "ticket"},
                {"id": "bank_transfer"},
            ],
        },
    }
    if payer.get("identification"):
        payload["payer"]["identification"] = payer["identification"]
    if success_url.startswith("https://"):
        payload["auto_return"] = "approved"
    if payer.get("phone"):
        payload["payer"]["phone"] = payer["phone"]
    return _mp_request(access_token, "POST", "/checkout/preferences", payload)


def extract_checkout_url(mp_response: dict[str, Any], *, sandbox: bool = False) -> str | None:
    """URL de redirecionamento do Checkout Pro (produção ou sandbox)."""
    if sandbox:
        url = mp_response.get("sandbox_init_point") or mp_response.get("init_point")
    else:
        url = mp_response.get("init_point") or mp_response.get("sandbox_init_point")
    return str(url).strip() if url else None
