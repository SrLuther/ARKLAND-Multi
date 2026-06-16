"""Testes para validação de pagador PIX."""
from __future__ import annotations

import pytest

from pix_payments import (
    PayerValidationError,
    normalize_payer_input,
    parse_mp_error_message,
)


def test_normalize_payer_ok():
    payer = normalize_payer_input({
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


def test_normalize_payer_rejects_invalid_email():
    with pytest.raises(PayerValidationError) as exc:
        normalize_payer_input({"email": "invalid", "full_name": "A B", "cpf": "52998224725"})
    assert exc.value.field == "email"


def test_normalize_payer_rejects_invalid_cpf():
    with pytest.raises(PayerValidationError) as exc:
        normalize_payer_input({
            "email": "a@b.com",
            "full_name": "A B",
            "cpf": "111.111.111-11",
        })
    assert exc.value.field == "cpf"


def test_normalize_payer_requires_surname():
    with pytest.raises(PayerValidationError) as exc:
        normalize_payer_input({
            "email": "a@b.com",
            "full_name": "Joao",
            "cpf": "52998224725",
        })
    assert exc.value.field == "full_name"


def test_parse_mp_error_message_json():
    raw = '{"message":"bad","cause":[{"description":"payer.email must be valid"}]}'
    assert "payer.email" in parse_mp_error_message(raw)
