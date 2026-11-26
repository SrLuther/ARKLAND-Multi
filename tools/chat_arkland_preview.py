"""Prévia local de desenvolvimento do Chat Arkland. Não serve para produção."""
from __future__ import annotations
import argparse
from functools import wraps
import os
from pathlib import Path
import secrets
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin" / "arkshop_web"))
from flask import Flask, jsonify, request, send_from_directory
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from chat_arkland_routes import register_chat_arkland_routes


def build_app(database_url):
    app = Flask("ChatArkland-LocalPreview")
    engine = create_engine(database_url)
    sessions = sessionmaker(engine)
    # Somente uma fixture em loopback, sem token real nem cliente Discord.
    def admin(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if request.remote_addr not in {"127.0.0.1", "::1"}:
                return jsonify(ok=False, error="Prévia disponível somente em loopback."), 403
            return fn(*args, **kwargs)
        return wrapped
    api_key = os.environ.get("CHAT_PREVIEW_API_KEY") or secrets.token_urlsafe(32)
    def internal(**_options):
        def decorate(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                if request.headers.get("X-API-Key") != api_key:
                    return jsonify(ok=False, error="Acesso interno não autorizado."), 401
                return fn(*args, **kwargs)
            return wrapped
        return decorate
    register_chat_arkland_routes(app, db_ready=lambda: True, session_factory=sessions, engine_getter=lambda: engine,
        load_servers=lambda: [{"server_id": "preview-a", "arkland_ref": "preview:map-a", "label": "Mapa de demonstração A"},
                              {"server_id": "preview-b", "arkland_ref": "preview:map-b", "label": "Mapa de demonstração B"}],
        admin_required=admin, api_key_required=internal, actor_getter=lambda: "preview-local", license_provider=lambda db, ids: {},
        license_catalog=lambda: [{"group": "licenca_exemplo", "label": "Licença fictícia da prévia"}],
        discord_identity=lambda db, author: None, load_settings=lambda: {}, bootstrap_key=lambda: api_key,
        public_url=lambda: "http://127.0.0.1:5188")
    @app.get("/")
    def index():
        return '''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Chat Arkland — prévia local</title>
<style>:root{--bg:#080e15;--surface:#101b27;--border:#304454;--amber:#70d9cd;--text:#e5edf2;--text2:#9babb8}*{box-sizing:border-box}body{background:var(--bg);color:var(--text);margin:0;font:15px 'Segoe UI',sans-serif}.btn{font:inherit;cursor:pointer;color:var(--text);background:transparent;border:1px solid var(--border);border-radius:7px;padding:8px 13px}.btn-primary{background:#20565a}.btn-sm{font-size:13px}.preview-label{padding:12px 24px;background:#583e16;color:#fff2ca}</style>
<link rel="stylesheet" href="/chat-arkland.css"><div class="preview-label">PRÉVIA LOCAL · dados fictícios · nenhuma mensagem será enviada ao Discord ou aos servidores.</div><main id="chat-arkland-root"></main>
<script>let _auth={authenticated:true,is_admin:true};function goToPage(){alert('A configuração compartilhada do Lumo é acessada no portal real; esta é uma prévia isolada.');}</script>
<script src="/chat-arkland.js"></script><script>loadChatArkland();</script></html>'''
    @app.get("/<path:filename>")
    def static_asset(filename):
        if filename not in {"chat-arkland.css", "chat-arkland.js"}:
            return "Não encontrado", 404
        return send_from_directory(ROOT / "plugin" / "arkshop_web" / "static", filename)
    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5188)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="arkland-chat-preview-") as folder:
        app = build_app(os.environ.get("CHAT_PREVIEW_DATABASE_URL") or f"sqlite:///{Path(folder)/'preview.sqlite'}")
        app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)
