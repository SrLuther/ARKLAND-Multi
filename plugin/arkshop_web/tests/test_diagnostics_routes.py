"""Testes do endpoint de recepção de diagnósticos (POST /api/diagnostics)."""
from __future__ import annotations

import io
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest
from flask import Flask, jsonify, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import diagnostics_routes as dr  # noqa: E402

KEY = "k-test"


def _make_zip(entries=None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in (entries or {"app_info.json": "{}"}).items():
            zf.writestr(name, data)
    return buf.getvalue()


def _build_app(tmp_path: Path, *, limit: bool = False):
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.secret_key = "x"
    limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri="memory://")

    def api_key_required(allow_admin_session=False):
        def deco(fn):
            def wrapper(*a, **kw):
                from flask import request
                if request.headers.get("X-API-Key", "") != KEY:
                    return jsonify({"ok": False, "error": "Unauthorized"}), 401
                return fn(*a, **kw)
            wrapper.__name__ = fn.__name__
            return wrapper
        return deco

    def admin_required(fn):
        def wrapper(*a, **kw):
            if not session.get("admin"):
                return jsonify({"ok": False, "error": "Acesso negado"}), 403
            return fn(*a, **kw)
        wrapper.__name__ = fn.__name__
        return wrapper

    dr.register_diagnostics_routes(
        app, api_key_required=api_key_required, admin_required=admin_required,
        limiter=limiter, data_dir=tmp_path,
    )

    @app.route("/_login")
    def _login():
        session["admin"] = True
        return "ok"

    return app


def _post(client, data: bytes, *, key=KEY, fields=None, filename="x.zip"):
    form = {"file": (io.BytesIO(data), filename)}
    form.update(fields or {})
    headers = {"X-API-Key": key} if key else {}
    return client.post("/api/diagnostics", data=form, headers=headers,
                       content_type="multipart/form-data")


@pytest.fixture()
def client(tmp_path):
    return _build_app(tmp_path).test_client()


def test_exige_api_key(client, tmp_path):
    assert _post(client, _make_zip(), key="").status_code == 401
    assert _post(client, _make_zip(), key="errada").status_code == 401
    assert not (tmp_path / "diagnostics").exists()


def test_upload_valido_grava_zip_e_metadados(client, tmp_path):
    r = _post(client, _make_zip(), fields={
        "app_version": "1.2.3", "ui_mode": "tek", "machine": "PC-Teste",
        "note": "olá\x00 mundo", "doctor_summary": json.dumps({"ok": 3, "aviso": 1, "erro": 0}),
    })
    assert r.status_code == 201
    body = r.get_json()
    assert body["ok"] is True and dr._ID_RE.match(body["id"])
    z = tmp_path / "diagnostics" / f"{body['id']}.zip"
    assert z.is_file() and zipfile.is_zipfile(z)
    meta = json.loads(z.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["app_version"] == "1.2.3" and meta["machine"] == "PC-Teste"
    assert "\x00" not in meta["note"]
    assert meta["doctor_summary"] == {"ok": 3, "aviso": 1, "erro": 0}
    assert len(meta["sha256"]) == 64


def test_nome_do_cliente_e_ignorado_sem_path_traversal(client, tmp_path):
    r = _post(client, _make_zip(), filename="../../../evil.zip")
    assert r.status_code == 201
    store = tmp_path / "diagnostics"
    assert {p.suffix for p in store.iterdir()} == {".zip", ".json"}
    assert not (tmp_path.parent / "evil.zip").exists()


def test_rejeita_nao_zip(client, tmp_path):
    r = _post(client, b"isto nao e um zip")
    assert r.status_code == 400
    assert not list((tmp_path / "diagnostics").glob("*.zip"))
    assert not list((tmp_path / "diagnostics").glob(".*.part"))


def test_rejeita_zip_corrompido(client):
    bad = _make_zip()[:-30]
    assert _post(client, b"PK\x03\x04" + bad[4:]).status_code == 400


def test_rejeita_zip_com_caminho_perigoso(client):
    assert _post(client, _make_zip({"../escape.txt": "x"})).status_code == 400
    assert _post(client, _make_zip({"/abs.txt": "x"})).status_code == 400


def test_rejeita_sem_campo_file(client):
    r = client.post("/api/diagnostics", data={"note": "x"}, headers={"X-API-Key": KEY},
                    content_type="multipart/form-data")
    assert r.status_code == 400


def test_limite_de_tamanho(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_DIAGNOSTICS_MAX_MB", "1")
    monkeypatch.setattr(dr, "_OVERHEAD", 1024)
    client = _build_app(tmp_path).test_client()
    big = _make_zip({"a.bin": os.urandom(2 * 1024 * 1024)})
    assert _post(client, big).status_code == 413
    store = tmp_path / "diagnostics"
    assert not store.exists() or not list(store.glob("*.zip"))


def test_rate_limit(tmp_path):
    client = _build_app(tmp_path).test_client()
    codes = [_post(client, _make_zip()).status_code for _ in range(7)]
    assert codes[:6] == [201] * 6
    assert codes[6] == 429


def test_retencao_remove_antigos(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSHOP_DIAGNOSTICS_KEEP", "5")
    store = tmp_path / "diagnostics"
    store.mkdir()
    for i in range(8):
        stem = f"20200101-00000{i}-{i:08x}"
        (store / f"{stem}.zip").write_bytes(_make_zip())
        (store / f"{stem}.json").write_text("{}")
    dr._prune(store, dr._keep())
    left = sorted(p.stem for p in store.glob("*.zip"))
    assert len(left) == 5 and left[0].startswith("20200101-000003")
    assert len(list(store.glob("*.json"))) == 5


def test_admin_lista_e_baixa(tmp_path):
    client = _build_app(tmp_path).test_client()
    diag_id = _post(client, _make_zip(), fields={"machine": "M1"}).get_json()["id"]

    assert client.get("/api/admin/diagnostics").status_code == 403
    assert client.get(f"/api/admin/diagnostics/{diag_id}/download").status_code == 403

    client.get("/_login")
    lst = client.get("/api/admin/diagnostics").get_json()
    assert lst["data"]["count"] == 1 and lst["data"]["items"][0]["machine"] == "M1"
    dl = client.get(f"/api/admin/diagnostics/{diag_id}/download")
    assert dl.status_code == 200 and zipfile.ZipFile(io.BytesIO(dl.data)).namelist()
    dl.close()


def test_admin_download_valida_id(tmp_path):
    client = _build_app(tmp_path).test_client()
    client.get("/_login")
    for bad in ("..%2F..%2Fsecret", "abc", "20200101-000000-ZZZZZZZZ", "20200101-000000-00000000"):
        assert client.get(f"/api/admin/diagnostics/{bad}/download").status_code in (400, 404)


def test_clean_text():
    assert dr.clean_text("a\x00b\x1b[31m<script>", 50) == "ab[31mscript"
    assert len(dr.clean_text("x" * 1000, 20)) == 20


def test_rota_registrada_no_app_real_e_exige_chave():
    import app as app_module

    rules = {r.rule for r in app_module.app.url_map.iter_rules()}
    assert "/api/diagnostics" in rules
    assert "/api/admin/diagnostics" in rules
    c = app_module.app.test_client()
    r = c.post("/api/diagnostics", data={"file": (io.BytesIO(_make_zip()), "a.zip")},
               content_type="multipart/form-data")
    assert r.status_code == 401
