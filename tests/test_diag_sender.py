"""Envio opt-in (src/diagnostics/sender.py): Discord (webhook) e Web Store (API)."""
from __future__ import annotations

import io
import json
import socket
import urllib.error
import zipfile
from pathlib import Path

import pytest

from src.diagnostics import sender as sd
from src.diagnostics.doctor import CheckResult

WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/AbCdEf_ghIJkl-MNop0123456789"
KEY = "shop-key-123456"


class FakeResp:
    def __init__(self, status=200, body=b"{}"):
        self.status, self._body = status, body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Recorder:
    def __init__(self, resp=None, exc=None):
        self.resp, self.exc, self.requests = resp or FakeResp(), exc, []

    def __call__(self, req, timeout=None):
        self.requests.append(req)
        if self.exc:
            raise self.exc
        return self.resp


@pytest.fixture()
def zip_file(tmp_path) -> Path:
    p = tmp_path / "arkland-diagnostico-x.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("app_info.json", "{}")
    return p


def _http_error(code):
    return urllib.error.HTTPError("https://x.test/api/diagnostics", code, "msg", {}, None)


# ── utilidades ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url,valid", [
    (WEBHOOK, True),
    ("https://discordapp.com/api/webhooks/1/abc_DEF-1", True),
    ("https://ptb.discord.com/api/v10/webhooks/1/abc", True),
    ("http://discord.com/api/webhooks/1/abc", False),
    ("https://evil.test/api/webhooks/1/abc", False),
    ("https://discord.com.evil.test/api/webhooks/1/abc", False),
    ("https://discord.com/api/webhooks/abc/abc", False),
    ("", False),
])
def test_validacao_do_webhook(url, valid):
    assert sd.is_valid_discord_webhook(url) is valid


def test_multipart_bem_formado():
    body, ctype = sd.build_multipart({"a": "1", "nota": "olá"}, [("file", "x.zip", b"PK\x03\x04bin", "application/zip")])
    boundary = ctype.split("boundary=")[1]
    assert body.startswith(f"--{boundary}\r\n".encode()) and body.endswith(f"--{boundary}--\r\n".encode())
    assert b'name="a"\r\n\r\n1\r\n' in body and "olá".encode() in body
    assert b'name="file"; filename="x.zip"' in body and b"PK\x03\x04bin" in body


def test_resumo_mascara_e_limita():
    res = [CheckResult("a", "Falha", "ERRO", f"password=hunter2hunter2 {WEBHOOK}"),
           CheckResult("b", "Ok", "OK", "x")] + [CheckResult(f"w{i}", f"Aviso {i}", "AVISO", "d" * 300) for i in range(30)]
    text = sd.build_summary(res, "1.2.3", "tek")
    assert "1 erro(s)" in text and "30 aviso(s)" in text and "v1.2.3" in text
    assert "hunter2hunter2" not in text and "AbCdEf_ghIJkl" not in text
    assert len(text) <= sd.DISCORD_CONTENT_LIMIT


# ── Discord ──────────────────────────────────────────────────────────────────

def test_discord_url_invalida_nao_faz_requisicao(zip_file):
    rec = Recorder()
    r = sd.send_to_discord("https://evil.test/x", zip_file, "resumo", urlopen=rec)
    assert not r.ok and "inválida" in r.message and rec.requests == []


def test_discord_envia_zip_multipart(zip_file):
    rec = Recorder(FakeResp(200))
    r = sd.send_to_discord(WEBHOOK, zip_file, "resumo teste", urlopen=rec)
    assert r.ok and not r.partial
    req = rec.requests[0]
    assert req.full_url.startswith(WEBHOOK) and req.get_method() == "POST"
    assert req.get_header("Content-type").startswith("multipart/form-data; boundary=")
    assert b"resumo teste" in req.data and b'filename="arkland-diagnostico-x.zip"' in req.data
    assert b"PK\x03\x04" in req.data


def test_discord_zip_grande_envia_so_resumo(zip_file):
    rec = Recorder(FakeResp(204))
    r = sd.send_to_discord(WEBHOOK, zip_file, "resumo", max_bytes=10, urlopen=rec)
    assert r.ok and r.partial
    req = rec.requests[0]
    assert req.get_header("Content-type") == "application/json"
    payload = json.loads(req.data)
    assert "resumo" in payload["content"] and "apenas o resumo" in payload["content"]
    assert b"PK\x03\x04" not in req.data


@pytest.mark.parametrize("exc,fragment", [
    (_http_error(429), "429"), (_http_error(404), "404"), (_http_error(500), "500"),
    (urllib.error.URLError(socket.gaierror("x")), "conectar"), (socket.timeout(), "tempo esgotado"),
    (RuntimeError("boom"), "inesperada"),
])
def test_discord_falhas_viram_mensagem_sem_levantar(zip_file, exc, fragment):
    r = sd.send_to_discord(WEBHOOK, zip_file, "r", urlopen=Recorder(exc=exc))
    assert not r.ok and fragment in r.message
    assert "AbCdEf" not in r.message and "discord.com" not in r.message     # não expõe o webhook


def test_discord_zip_inexistente(tmp_path):
    r = sd.send_to_discord(WEBHOOK, tmp_path / "nao.zip", "r", urlopen=Recorder())
    assert not r.ok and "não encontrado" in r.message


# ── Web Store ────────────────────────────────────────────────────────────────

def test_webstore_requer_url_e_chave(zip_file):
    rec = Recorder()
    assert "URL" in sd.send_to_webstore("", KEY, zip_file, urlopen=rec).message
    assert "API key" in sd.send_to_webstore("https://loja.test", "", zip_file, urlopen=rec).message
    assert rec.requests == []


def test_webstore_envia_com_headers_e_campos(zip_file):
    rec = Recorder(FakeResp(201, json.dumps({"ok": True, "id": "20260101-000000-abcdef12"}).encode()))
    r = sd.send_to_webstore("https://loja.test/", KEY, zip_file, app_version="9.9", mode="tek",
                            note="n" * 900, machine="PC1", doctor_summary={"OK": 3, "ERRO": 1}, urlopen=rec)
    assert r.ok and r.remote_id == "20260101-000000-abcdef12" and "20260101-000000-abcdef12" in r.message
    req = rec.requests[0]
    assert req.full_url == "https://loja.test/api/diagnostics"
    assert req.get_header("X-api-key") == KEY and req.get_header("Authorization") == f"Bearer {KEY}"
    assert b'name="app_version"\r\n\r\n9.9' in req.data and b'name="machine"\r\n\r\nPC1' in req.data
    assert b'name="file"; filename="arkland-diagnostico-x.zip"' in req.data
    assert b"n" * 500 in req.data and b"n" * 501 not in req.data       # nota truncada em 500


def test_webstore_id_em_data(zip_file):
    rec = Recorder(FakeResp(200, json.dumps({"ok": True, "data": {"id": "zzz"}}).encode()))
    assert sd.send_to_webstore("https://loja.test", KEY, zip_file, urlopen=rec).remote_id == "zzz"


def test_webstore_pacote_acima_do_limite_nao_envia(zip_file):
    rec = Recorder()
    r = sd.send_to_webstore("https://loja.test", KEY, zip_file, max_bytes=5, urlopen=rec)
    assert not r.ok and "limite" in r.message and rec.requests == []


@pytest.mark.parametrize("exc,fragment", [
    (_http_error(401), "acesso negado"), (_http_error(403), "acesso negado"),
    (_http_error(404), "desatualizada"), (_http_error(413), "grande demais"), (_http_error(429), "429"),
    (urllib.error.URLError(ConnectionRefusedError()), "conectar"), (TimeoutError(), "tempo esgotado"),
])
def test_webstore_falhas_com_mensagens_claras_e_sem_vazar_chave(zip_file, exc, fragment):
    r = sd.send_to_webstore("https://loja.test", KEY, zip_file, urlopen=Recorder(exc=exc))
    assert not r.ok and fragment in r.message
    assert KEY not in r.message and "loja.test" not in r.message


def test_webstore_resposta_ok_false_e_recusa(zip_file):
    rec = Recorder(FakeResp(200, json.dumps({"ok": False, "error": "pacote inválido: zip vazio"}).encode()))
    r = sd.send_to_webstore("https://loja.test", KEY, zip_file, urlopen=rec)
    assert not r.ok and "zip vazio" in r.message


def test_webstore_corpo_nao_json_com_201_ainda_ok(zip_file):
    r = sd.send_to_webstore("https://loja.test", KEY, zip_file, urlopen=Recorder(FakeResp(201, b"<html>")))
    assert r.ok and r.remote_id == ""


def test_resolve_webstore_target_usa_config_da_loja():
    from types import SimpleNamespace
    shop = SimpleNamespace(mode="client", central_url="https://loja.test/", public_url="https://loja.test/",
                           host_ip="", port=27199, api_key=f"  {KEY} ")
    app = SimpleNamespace(config_manager=SimpleNamespace(config=SimpleNamespace(shop=shop)))
    url, key = sd.resolve_webstore_target(app)
    assert url.startswith("https://loja.test") and not url.endswith("/") and key == KEY


# ── ponta a ponta: cliente → endpoint real do arkshop_web (app Flask isolado) ─

def test_end_to_end_cliente_contra_endpoint(tmp_path, zip_file):
    import os
    import sys

    web_dir = Path(__file__).resolve().parents[1] / "plugin" / "arkshop_web"
    if str(web_dir) not in sys.path:
        sys.path.insert(0, str(web_dir))
    flask = pytest.importorskip("flask")
    pytest.importorskip("flask_limiter")
    import diagnostics_routes as dr
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    app = flask.Flask(__name__)
    limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri="memory://")

    def api_key_required(allow_admin_session=False):
        def deco(fn):
            def wrapper(*a, **kw):
                if flask.request.headers.get("X-API-Key") != KEY:
                    return flask.jsonify({"ok": False}), 401
                return fn(*a, **kw)
            wrapper.__name__ = fn.__name__
            return wrapper
        return deco

    dr.register_diagnostics_routes(app, api_key_required=api_key_required, admin_required=lambda f: f,
                                   limiter=limiter, data_dir=tmp_path / "data")
    client = app.test_client()

    def fake_urlopen(req, timeout=None):
        resp = client.post("/api/diagnostics", data=req.data,
                           headers={k: v for k, v in req.header_items()}, content_type=req.get_header("Content-type"))
        if resp.status_code >= 400:
            raise urllib.error.HTTPError(req.full_url, resp.status_code, "err", {}, None)
        return FakeResp(resp.status_code, resp.data)

    ok_res = sd.send_to_webstore("https://loja.test", KEY, zip_file, app_version="1.0", mode="tek",
                                 machine="PC", doctor_summary={"OK": 1}, urlopen=fake_urlopen)
    assert ok_res.ok and ok_res.remote_id
    saved = list((tmp_path / "data" / "diagnostics").glob("*.zip"))
    assert len(saved) == 1 and saved[0].stem == ok_res.remote_id
    assert zipfile.ZipFile(saved[0]).namelist() == ["app_info.json"]

    bad = sd.send_to_webstore("https://loja.test", "chave-errada", zip_file, urlopen=fake_urlopen)
    assert not bad.ok and "acesso negado" in bad.message
