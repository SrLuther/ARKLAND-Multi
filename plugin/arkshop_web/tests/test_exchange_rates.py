"""Testes para cotações BRL → USD/EUR."""
from __future__ import annotations


from exchange_rates import FALLBACK_RATES, estimate_foreign, get_exchange_rates


def test_estimate_foreign_uses_rates():
    est = estimate_foreign(100.0, {"USD": 0.2, "EUR": 0.18})
    assert est == {"USD": 20.0, "EUR": 18.0}


def test_get_exchange_rates_fallback_on_api_error(monkeypatch):
    def fail_fetch():
        raise OSError("network down")

    monkeypatch.setattr("exchange_rates._fetch_frankfurter", fail_fetch)
    payload = get_exchange_rates(force_refresh=True)
    assert payload["rates"] == FALLBACK_RATES
    assert payload["source"] == "fallback"
    assert payload["base"] == "BRL"


def test_get_exchange_rates_from_api(monkeypatch):
    def ok_fetch():
        return {"USD": 0.19, "EUR": 0.16}

    monkeypatch.setattr("exchange_rates._fetch_frankfurter", ok_fetch)
    payload = get_exchange_rates(force_refresh=True)
    assert payload["rates"]["USD"] == 0.19
    assert payload["source"] == "frankfurter"
