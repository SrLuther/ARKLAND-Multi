"""Mascaramento de segredos (src/diagnostics/redact.py)."""
from __future__ import annotations

import json

import pytest

from src.diagnostics import redact
from src.diagnostics.redact import REDACTED, is_sensitive_key, redact_obj, redact_text


def test_ini_passwords_masked_empty_kept():
    ini = (
        "[ServerSettings]\r\n"
        "ServerPassword=hunter2abc\r\n"
        "ServerAdminPassword=SuperAdmin!99\r\n"
        "SpectatorPassword=\r\n"
        "RCONPassword=rconsecret1\r\n"
        "RCONPort=27020\r\n"
        "MaxPlayers=70\r\n"
    )
    out = redact_text(ini)
    assert "hunter2abc" not in out
    assert "SuperAdmin!99" not in out
    assert "rconsecret1" not in out
    assert "RCONPort=27020" in out and "MaxPlayers=70" in out
    assert "SpectatorPassword=\r\n" in out          # vazio continua vazio
    assert out.count("\r\n") == ini.count("\r\n")   # CRLF preservado


def test_json_text_keeps_valid_json():
    raw = json.dumps({"api_key": "abc123SECRET", "name": "Loja", "token": "tok_ABCDEFGHIJ", "empty_password": ""}, indent=2)
    out = redact_text(raw)
    data = json.loads(out)                       # continua JSON válido
    assert data["api_key"] == REDACTED and data["token"] == REDACTED
    assert data["name"] == "Loja"
    assert data["empty_password"] == ""


def test_discord_webhook_url_and_bot_token():
    url = "https://discord.com/api/webhooks/123456789012345678/fixture-webhook"
    out = redact_text(f"enviando para {url} agora")
    assert "fixture-webhook" not in out and "123456789012345678" not in out
    assert "enviando para" in out
    phrase = "token: synthetic-secret-for-redact-test"
    assert "synthetic-secret-for-redact-test" not in redact_text(phrase)


def test_bearer_authorization_cookie_headers():
    text = "Authorization: Bearer abc.def.ghi123\nCookie: session=xyz; other=1\nX-Api-Key: k3y\nAccept: */*"
    out = redact_text(text)
    assert "abc.def.ghi123" not in out and "session=xyz" not in out and "k3y" not in out
    assert "Accept: */*" in out
    assert "Bearer " + REDACTED in redact_text("header Bearer abcdefghijkl123")


def test_inline_key_value_and_command_line():
    cmd = "ShooterGameServer.exe TheIsland?listen?ServerPassword=pw12345?ServerAdminPassword=adm!n?Port=7777 -log"
    out = redact_text(cmd)
    assert "pw12345" not in out and "adm!n" not in out
    assert "Port=7777" in out
    assert "token=" in redact_text("GET /x?token=abcdef&page=2") and "abcdef" not in redact_text("GET /x?token=abcdef&page=2")
    assert "page=2" in redact_text("GET /x?token=abcdef&page=2")
    assert "secretvalue" not in redact_text("login failed password: secretvalue")


def test_url_userinfo_and_jwt():
    out = redact_text("mysql://root:p4ssw0rd@10.0.0.5:3306/arkshop")
    assert "p4ssw0rd" not in out and "root:" in out and "@10.0.0.5" in out
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop"
    assert jwt not in redact_text(f"jwt={jwt}")


def test_pydict_repr_masked():
    out = redact_text("{'api_key': 'abc123secret', 'user': 'bob', 'enabled': True}")
    assert "abc123secret" not in out and "'user': 'bob'" in out


def test_redact_obj_nested_and_non_sensitive_untouched():
    obj = {
        "shop": {"api_key": "KEY-12345678", "central_url": "https://loja.exemplo.com", "orders_db_password": "dbpass99"},
        "discord_notify": {"webhook_url": "https://discord.com/api/webhooks/1/abc", "enabled": True},
        "servers": [{"name": "Ilha", "admin_password": "adm1234", "ports": [7777, 27015]}],
        "remote_agent_token": "uuid-uuid-uuid",
        "bool_pw": False,
        "none_token": None,
        "blank_password": "",
        "url": "mysql://u:secretpw@host/db",
    }
    out = redact_obj(obj)
    flat = json.dumps(out)
    for leaked in ("KEY-12345678", "dbpass99", "adm1234", "uuid-uuid-uuid", "secretpw", "discord.com/api/webhooks/1/abc"):
        assert leaked not in flat, leaked
    assert out["shop"]["central_url"] == "https://loja.exemplo.com"
    assert out["servers"][0]["name"] == "Ilha" and out["servers"][0]["ports"] == [7777, 27015]
    assert out["discord_notify"]["enabled"] is True
    assert out["bool_pw"] is False and out["none_token"] is None and out["blank_password"] == ""
    assert obj["shop"]["api_key"] == "KEY-12345678"      # original intacto


def test_redact_is_idempotent():
    once = redact_text("ServerPassword=abc12345\napi_key: k-123456")
    assert redact_text(once) == once


@pytest.mark.parametrize("key,expected", [
    ("ServerAdminPassword", True), ("rcon_password", True), ("steam_api_key", True), ("webhook_url", True),
    ("Authorization", True), ("Cookie", True), ("remote_agent_token", True), ("password_hash", True),
    ("name", False), ("install_dir", False), ("passive_mode", False), ("bypass_check", False),
])
def test_is_sensitive_key(key, expected):
    assert is_sensitive_key(key) is expected


def test_extension_points():
    redact.add_sensitive_keyword(r"licenca")
    try:
        assert is_sensitive_key("minha_licenca")
        assert "XYZ" not in redact_text("minha_licenca=XYZ123")
        redact.add_rule("meu_padrao", r"ARK-\d{6}", "ARK-******", first=True)
        assert redact_text("codigo ARK-123456") == "codigo ARK-******"
    finally:
        redact.SENSITIVE_KEYWORDS.remove(r"licenca")
        redact.REDACTION_RULES[:] = [r for r in redact.REDACTION_RULES if r.name != "meu_padrao"]
        redact._invalidate()


def test_optional_rules_off_by_default_and_toggle():
    assert redact_text("ip 192.168.1.10 steam 76561198000000001") == "ip 192.168.1.10 steam 76561198000000001"
    redact.enable_optional_rule("ipv4")
    try:
        assert "192.168.1.10" not in redact_text("ip 192.168.1.10")
    finally:
        redact.disable_optional_rule("ipv4")
    assert "192.168.1.10" in redact_text("ip 192.168.1.10")


def test_game_ini_ramp_lines_not_touched():
    line = "LevelExperienceRampOverrides=(ExperiencePointsForLevel[0]=100,ExperiencePointsForLevel[1]=250)"
    assert redact_text(line) == line


def test_large_text_performance():
    import time
    chunk = "2026-10-02 10:00:00 | INFO | v1/tek | MainThread | arkland:x:1 | Servidor iniciado porta=7777 ok\n" * 40000
    t0 = time.perf_counter()
    redact_text(chunk)
    assert time.perf_counter() - t0 < 12.0
