"""Validação HMAC x-signature — webhook Mercado Pago."""
from __future__ import annotations

import hashlib
import hmac
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pix_payments import (  # noqa: E402
    WebhookSignatureError,
    build_mp_webhook_manifest,
    verify_mp_webhook_signature,
)


def _sign(secret: str, data_id: str, request_id: str, ts: str) -> str:
    manifest = build_mp_webhook_manifest(data_id, request_id, ts)
    v1 = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"


def test_verify_mp_webhook_signature_ok():
    secret = "test-webhook-secret"
    ts = str(int(time.time()))
    hdr = _sign(secret, "mp_123", "req-abc", ts)
    verify_mp_webhook_signature(hdr, "req-abc", "mp_123", secret)


def test_verify_mp_webhook_signature_rejects_bad_v1():
    secret = "test-webhook-secret"
    ts = str(int(time.time()))
    hdr = f"ts={ts},v1=deadbeef"
    with pytest.raises(WebhookSignatureError):
        verify_mp_webhook_signature(hdr, "req-abc", "mp_123", secret)


def test_verify_mp_webhook_signature_skips_when_no_secret():
    verify_mp_webhook_signature(None, None, None, "")


def test_build_mp_webhook_manifest_lowercases_data_id():
    assert build_mp_webhook_manifest("ORD01ABC", "r1", "99") == "id:ord01abc;request-id:r1;ts:99;"
