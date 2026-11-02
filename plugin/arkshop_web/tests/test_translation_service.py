"""Tests for Azure Translator adapter and usage limits."""
from __future__ import annotations

import json
import os
import socket

import pytest
from sqlalchemy import create_engine

import translation_service as service
from translation_usage import TranslationUsage


class FakeResponse:
    def __init__(self, status=200, payload=None, headers=None):
        self.status = status
        self._payload = payload if isinstance(payload, bytes) else json.dumps(payload or []).encode()
        self._headers = list((headers or {}).items())

    def getheaders(self):
        return self._headers

    def read(self, _limit):
        return self._payload


class FakeConnection:
    responses = []
    requests = []

    def __init__(self, host, port, timeout):
        self.host, self.port, self.timeout = host, port, timeout
        self.sock = type("Socket", (), {"settimeout": lambda *_: None})()
        self.response = self.responses.pop(0)

    def request(self, method, path, body, headers):
        self.requests.append((method, path, body, headers))

    def getresponse(self):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def close(self):
        pass


@pytest.fixture(autouse=True)
def azure_config(monkeypatch):
    monkeypatch.setenv("AZURE_TRANSLATOR_KEY", "test-secret-key")
    monkeypatch.delenv("AZURE_TRANSLATOR_REGION", raising=False)
    monkeypatch.delenv("AZURE_TRANSLATOR_ENDPOINT", raising=False)
    monkeypatch.setenv("AZURE_TRANSLATOR_API_VERSION", "3.0")
    monkeypatch.setenv("AZURE_TRANSLATOR_MAX_RETRIES", "0")
    FakeConnection.responses = []
    FakeConnection.requests = []
    monkeypatch.setattr(service.http.client, "HTTPSConnection", FakeConnection)


def success_payload(text="Hola"):
    return [{"translations": [{"text": text}], "detectedLanguage": {"language": "en", "score": 0.99}}]


def test_translates_autodetected_text_and_keeps_key_in_backend_only():
    FakeConnection.responses = [FakeResponse(payload=success_payload(), headers={"X-RequestId": "req-123", "X-metered-usage": "5"})]
    result = service.translate("Hello", "es")
    assert result.translated_text == "Hola"
    assert result.source_language == "en"
    assert result.target_language == "es"
    assert result.request_id == "req-123"
    assert result.metered_characters == 5
    method, path, body, headers = FakeConnection.requests[0]
    assert method == "POST" and "api-version=3.0" in path and "to=es" in path
    assert json.loads(body) == [{"Text": "Hello"}]
    assert headers["Ocp-Apim-Subscription-Key"] == "test-secret-key"
    assert "test-secret-key" not in repr(service.translator_status())


def test_admin_config_override_is_used_and_never_returned():
    FakeConnection.responses = [FakeResponse(payload=success_payload())]
    result = service.translate("Hello", "pt", "en", config_override={
        "key": "panel-secret-key", "region": "brazilsouth",
        "endpoint": "https://api.cognitive.microsofttranslator.com",
    })
    assert result.translated_text == "Hola"
    headers = FakeConnection.requests[0][3]
    assert headers["Ocp-Apim-Subscription-Key"] == "panel-secret-key"
    assert headers["Ocp-Apim-Subscription-Region"] == "brazilsouth"
    status = service.translator_status(config_override={
        "key": "panel-secret-key", "region": "brazilsouth",
        "endpoint": "https://api.cognitive.microsofttranslator.com",
    })
    assert status["key_configured"] is True
    assert status["region"] == "brazilsouth"
    assert "panel-secret-key" not in repr(status)


@pytest.mark.parametrize(("source", "target"), [("en", "pt"), ("pt", "en"), ("en", "es"), ("es", "en"), ("es", "pt"), ("pt", "es")])
def test_supported_language_directions(source, target):
    FakeConnection.responses = [FakeResponse(payload=[{"translations": [{"text": "translated"}]}]) ]
    result = service.translate("A complete sentence for support.", target, source)
    assert result.translated_text == "translated"
    assert result.source_language == source
    assert result.target_language == target


def test_autodetection_accepts_other_source_languages():
    payload = [{"translations": [{"text": "Ol?"}], "detectedLanguage": {"language": "fr", "score": 0.98}}]
    FakeConnection.responses = [FakeResponse(payload=payload)]
    result = service.translate("Bonjour, j'ai besoin d'aide.", "pt")
    assert result.source_language == "fr"
    assert result.translated_text == "Ol?"


def test_invalid_json_response_is_a_safe_structured_error():
    FakeConnection.responses = [FakeResponse(payload=b"not-json")]
    with pytest.raises(service.TranslationServiceError) as error:
        service.translate("Hello", "pt", "en")
    assert error.value.code == "AZURE_TRANSLATOR_INVALID_RESPONSE"
    assert error.value.stage == "response"


def test_custom_cognitive_endpoint_uses_translator_resource_path(monkeypatch):
    monkeypatch.setenv("AZURE_TRANSLATOR_ENDPOINT", "https://resource.cognitiveservices.azure.com")
    FakeConnection.responses = [FakeResponse(payload=success_payload())]
    service.translate("Hello", "pt", "en")
    assert FakeConnection.requests[0][1].startswith("/translator/text/v3.0/translate?")


def test_same_language_skips_external_request():
    result = service.translate("Ol?", "pt", "pt")
    assert result.skipped and result.translated_text == "Ol?"
    assert FakeConnection.requests == []


def test_invalid_language_and_oversize_rejected_before_network():
    with pytest.raises(service.TranslationServiceError) as invalid:
        service.translate("Hello", "fr")
    assert invalid.value.code == "TRANSLATION_BAD_REQUEST"
    with pytest.raises(service.TranslationServiceError) as large:
        service.translate("x" * 5001, "pt")
    assert large.value.stage == "validation"
    assert FakeConnection.requests == []


@pytest.mark.parametrize(("status", "code"), [(400, "AZURE_TRANSLATOR_BAD_REQUEST"), (401, "AZURE_TRANSLATOR_AUTH_FAILED"), (403, "AZURE_TRANSLATOR_FORBIDDEN"), (500, "AZURE_TRANSLATOR_UNAVAILABLE"), (503, "AZURE_TRANSLATOR_UNAVAILABLE")])
def test_http_errors_are_structured_and_do_not_leak_credentials(status, code):
    FakeConnection.responses = [FakeResponse(status=status, payload={"error": {"message": "secret-bearing response"}}, headers={"X-RequestId": "azure-req"})]
    with pytest.raises(service.TranslationServiceError) as error:
        service.translate("Hello", "pt", "en")
    assert error.value.code == code
    assert error.value.http_status == status
    assert error.value.request_id == "azure-req"
    assert "test-secret-key" not in str(error.value)
    assert "secret-bearing response" not in str(error.value)


@pytest.mark.parametrize("status", [429, 500, 503])
def test_retries_transient_http_errors_once_and_honors_retry_after(monkeypatch, status):
    monkeypatch.setenv("AZURE_TRANSLATOR_MAX_RETRIES", "1")
    monkeypatch.setattr(service.time, "sleep", lambda _seconds: None)
    events = []
    FakeConnection.responses = [
        FakeResponse(status=status, headers={"Retry-After": "0"}),
        FakeResponse(payload=success_payload()),
    ]
    result = service.translate("Hello", "pt", before_attempt=lambda _n: True, after_attempt=events.append)
    assert result.translated_text == "Hola"
    assert len(FakeConnection.requests) == 2
    assert [event["success"] for event in events] == [False, True]


def test_timeout_retries_are_bounded(monkeypatch):
    monkeypatch.setenv("AZURE_TRANSLATOR_MAX_RETRIES", "1")
    monkeypatch.setattr(service.time, "sleep", lambda _seconds: None)
    FakeConnection.responses = [socket.timeout("late"), socket.timeout("late")]
    with pytest.raises(service.TranslationServiceError) as error:
        service.translate("Hello", "pt", "en")
    assert error.value.code == "AZURE_TRANSLATOR_TIMEOUT"
    assert len(FakeConnection.requests) == 2


def test_monthly_usage_cap_counts_actual_metered_usage_and_blocks_next_call(tmp_path, monkeypatch):
    monkeypatch.setenv("AZURE_TRANSLATOR_ALERT_THRESHOLDS", "50,100")
    engine = create_engine(f"sqlite:///{tmp_path / 'usage.db'}", future=True)
    usage = TranslationUsage(engine)
    allowed, alerts, reserved, period = usage.reserve(8, 10)
    assert allowed and alerts == [50] and reserved == 8
    usage.finish({"reserved_characters": 8, "metered_characters": 6, "success": True, "duration_ms": 10}, period)
    snapshot = usage.snapshot(10)
    assert snapshot["characters"] == 6 and snapshot["successful"] == 1
    assert usage.reserve(5, 10)[0] is False
    engine.dispose()


@pytest.mark.azure_integration
def test_real_azure_translation_is_opt_in():
    if not (os.environ.get("AZURE_TRANSLATOR_KEY") or "").strip():
        pytest.skip("AZURE_TRANSLATOR_KEY is not configured")
    if os.environ.get("ARKLAND_RUN_AZURE_TRANSLATOR_INTEGRATION") != "1":
        pytest.skip("Set ARKLAND_RUN_AZURE_TRANSLATOR_INTEGRATION=1 to call Azure")
    result = service.translate("Hello, I need help with my server.", "pt", "en")
    assert result.http_status == 200
    assert result.translated_text.strip()
    assert result.target_language == "pt"
