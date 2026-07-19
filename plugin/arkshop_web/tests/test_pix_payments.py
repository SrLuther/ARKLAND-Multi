"""Testes para validação de pagador PIX."""
from __future__ import annotations

import pytest

from pix_payments import (
    PayerValidationError,
    normalize_card_payer_input,
    normalize_payer_input,
    normalize_pix_payer_input,
    parse_mp_error_message,
)


def test_normalize_payer_ok():
    payer = normalize_pix_payer_input({
        "email": "Joao@Example.com",
        "full_name": "João Silva",
        "cpf": "529.982.247-25",
        "phone": "(11) 98765-4321",
    })
    assert payer["email"] == "joao@example.com"
    assert payer["first_name"] == "João"
    assert payer["last_name"] == "Silva"
    assert payer["identification"] == {"type": "CPF", "number": "52998224725"}
    assert payer["phone"] == {"area_code": "11", "number": "987654321"}


def test_normalize_payer_alias_still_pix():
    payer = normalize_payer_input({
        "email": "a@b.com",
        "full_name": "A B",
        "cpf": "52998224725",
        "phone": "11987654321",
    })
    assert payer["identification"]["type"] == "CPF"


def test_normalize_pix_requires_phone():
    with pytest.raises(PayerValidationError) as exc:
        normalize_pix_payer_input({
            "email": "a@b.com",
            "full_name": "A B",
            "cpf": "52998224725",
        })
    assert exc.value.field == "phone"


def test_normalize_card_without_identification():
    payer = normalize_card_payer_input({
        "email": "international@example.com",
        "full_name": "John Smith",
    })
    assert payer["email"] == "international@example.com"
    assert payer["first_name"] == "John"
    assert payer["last_name"] == "Smith"
    assert "identification" not in payer


def test_normalize_card_with_passport():
    payer = normalize_card_payer_input({
        "email": "international@example.com",
        "full_name": "John Smith",
        "identification": "AB1234567",
    })
    assert payer["identification"] == {"type": "Otro", "number": "AB1234567"}


def test_normalize_card_with_cpf():
    payer = normalize_card_payer_input({
        "email": "br@example.com",
        "full_name": "João Silva",
        "identification": "529.982.247-25",
    })
    assert payer["identification"] == {"type": "CPF", "number": "52998224725"}


def test_normalize_payer_rejects_invalid_email():
    with pytest.raises(PayerValidationError) as exc:
        normalize_pix_payer_input({
            "email": "invalid",
            "full_name": "A B",
            "cpf": "52998224725",
            "phone": "11987654321",
        })
    assert exc.value.field == "email"


def test_normalize_payer_rejects_invalid_cpf():
    with pytest.raises(PayerValidationError) as exc:
        normalize_pix_payer_input({
            "email": "a@b.com",
            "full_name": "A B",
            "cpf": "111.111.111-11",
            "phone": "11987654321",
        })
    assert exc.value.field == "cpf"


def test_normalize_payer_requires_surname():
    with pytest.raises(PayerValidationError) as exc:
        normalize_pix_payer_input({
            "email": "a@b.com",
            "full_name": "Joao",
            "cpf": "52998224725",
            "phone": "11987654321",
        })
    assert exc.value.field == "full_name"


def test_parse_mp_error_message_json():
    raw = '{"message":"bad","cause":[{"description":"payer.email must be valid"}]}'
    assert "payer.email" in parse_mp_error_message(raw)


def test_create_card_checkout_preference_requires_success_url():
    from pix_payments import PixPaymentError, create_card_checkout_preference

    with pytest.raises(PixPaymentError, match="success"):
        create_card_checkout_preference(
            "token",
            amount_brl=5.0,
            description="test",
            external_reference="ref",
            payer={"email": "a@b.com", "first_name": "A", "last_name": "B"},
            back_urls={"success": "", "failure": "https://x/f", "pending": "https://x/p"},
        )


def test_create_card_checkout_preference_auto_return_only_for_https(monkeypatch):
    from pix_payments import create_card_checkout_preference

    captured: dict = {}

    def fake_mp(access_token, method, path, payload=None, *, idempotency_key=None):
        captured["payload"] = payload
        return {"init_point": "https://mp.test/checkout"}

    monkeypatch.setattr("pix_payments._mp_request", fake_mp)
    create_card_checkout_preference(
        "token",
        amount_brl=5.0,
        description="test",
        external_reference="ref",
        payer={
            "email": "a@b.com",
            "first_name": "A",
            "last_name": "B",
            "identification": {"type": "CPF", "number": "52998224725"},
        },
        back_urls={
            "success": "https://arkland.com.br/?mp_card_return=success",
            "failure": "https://arkland.com.br/?mp_card_return=failure",
            "pending": "https://arkland.com.br/?mp_card_return=pending",
        },
    )
    assert captured["payload"]["auto_return"] == "approved"
    assert captured["payload"]["back_urls"]["success"].startswith("https://arkland.com.br")
    assert captured["payload"]["payer"]["identification"]["type"] == "CPF"


def test_create_card_checkout_preference_omits_identification_when_absent(monkeypatch):
    from pix_payments import create_card_checkout_preference

    captured: dict = {}

    def fake_mp(access_token, method, path, payload=None, *, idempotency_key=None):
        captured["payload"] = payload
        return {"init_point": "https://mp.test/checkout"}

    monkeypatch.setattr("pix_payments._mp_request", fake_mp)
    create_card_checkout_preference(
        "token",
        amount_brl=5.0,
        description="test",
        external_reference="ref",
        payer={
            "email": "a@b.com",
            "first_name": "A",
            "last_name": "B",
        },
        back_urls={
            "success": "https://arkland.com.br/?mp_card_return=success",
            "failure": "https://arkland.com.br/?mp_card_return=failure",
            "pending": "https://arkland.com.br/?mp_card_return=pending",
        },
    )
    assert "identification" not in captured["payload"]["payer"]


def test_create_boleto_checkout_preference_excludes_non_ticket(monkeypatch):
    from pix_payments import create_boleto_checkout_preference

    captured: dict = {}

    def fake_mp(access_token, method, path, payload=None, *, idempotency_key=None):
        captured["payload"] = payload
        return {"init_point": "https://mp.test/boleto"}

    monkeypatch.setattr("pix_payments._mp_request", fake_mp)
    create_boleto_checkout_preference(
        "token",
        amount_brl=10.0,
        description="Doação boleto",
        external_reference="ref-boleto",
        payer={
            "email": "a@b.com",
            "first_name": "A",
            "last_name": "B",
            "identification": {"type": "CPF", "number": "52998224725"},
            "phone": {"area_code": "11", "number": "987654321"},
        },
        back_urls={
            "success": "https://arkland.com.br/?mp_boleto_return=success",
            "failure": "https://arkland.com.br/?mp_boleto_return=failure",
            "pending": "https://arkland.com.br/?mp_boleto_return=pending",
        },
    )
    excluded = {e["id"] for e in captured["payload"]["payment_methods"]["excluded_payment_types"]}
    assert "ticket" not in excluded
    assert "credit_card" in excluded
    assert "debit_card" in excluded
    assert "bank_transfer" in excluded
    assert captured["payload"]["payment_methods"]["default_payment_method_id"] == "bolbradesco"
    assert captured["payload"]["auto_return"] == "approved"
    assert captured["payload"]["payer"]["identification"]["type"] == "CPF"


def test_create_boleto_checkout_preference_requires_identification():
    from pix_payments import PayerValidationError, create_boleto_checkout_preference

    with pytest.raises(PayerValidationError) as exc:
        create_boleto_checkout_preference(
            "token",
            amount_brl=5.0,
            description="test",
            external_reference="ref",
            payer={"email": "a@b.com", "first_name": "A", "last_name": "B"},
            back_urls={
                "success": "https://arkland.com.br/?mp_boleto_return=success",
                "failure": "https://arkland.com.br/?mp_boleto_return=failure",
                "pending": "https://arkland.com.br/?mp_boleto_return=pending",
            },
        )
    assert exc.value.field == "identification"
