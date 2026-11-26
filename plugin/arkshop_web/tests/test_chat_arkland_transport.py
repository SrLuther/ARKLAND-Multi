"""Contratos HTTP e Discord usando fixtures; não envia mensagens reais."""
import asyncio
from functools import wraps
from pathlib import Path
import sys
from types import SimpleNamespace as NS

from flask import Flask, jsonify, request
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chat_arkland_routes as routes
from chat_arkland_discord import ChatDiscordTransport
from chat_arkland_service import PLAYERS


def test_http_admin_api_and_secret_boundaries(tmp_path, monkeypatch):
    app = Flask(__name__)
    engine = create_engine(f"sqlite:///{tmp_path / 'http.sqlite'}")
    def admin(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            return fn(*args, **kwargs) if request.headers.get('X-Admin') == 'yes' else (jsonify(ok=False), 403)
        return wrapped
    def api(**options):
        assert options == {'allow_admin_session': False}
        def decorate(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                return fn(*args, **kwargs) if request.headers.get('X-API-Key') == 'fixture-internal' else (jsonify(ok=False), 401)
            return wrapped
        return decorate
    monkeypatch.setattr('background_tasks.submit', lambda *args, **kwargs: None)
    routes.register_chat_arkland_routes(app, db_ready=lambda: True, session_factory=sessionmaker(engine),
        engine_getter=lambda: engine, load_servers=lambda: [{'server_id': 'map-a', 'arkland_ref': 'tek:aaa', 'label': 'A'}],
        admin_required=admin, api_key_required=api, actor_getter=lambda: 'fixture', license_provider=lambda db, ids: {},
        license_catalog=lambda: [], discord_identity=lambda db, author: None,
        load_settings=lambda: {'lumo_bot_token': 'fixture-discord-secret'}, bootstrap_key=lambda: 'fixture-internal')
    client = app.test_client()
    admin_headers = {'X-Admin': 'yes'}
    assert client.get('/api/admin/chat-arkland').status_code == 403
    assert client.get('/api/admin/chat-arkland/bootstrap/tek:aaa').status_code == 403
    assert client.post('/api/chat-arkland/plugin/exchange', json={}, headers=admin_headers).status_code == 401
    snapshot = client.get('/api/admin/chat-arkland', headers=admin_headers)
    assert snapshot.status_code == 200 and snapshot.json['discord']['token_configured']
    assert 'fixture-discord-secret' not in snapshot.text and 'fixture-internal' not in snapshot.text
    bootstrap = client.get('/api/admin/chat-arkland/bootstrap/tek:aaa', headers=admin_headers)
    assert bootstrap.status_code == 200 and bootstrap.json['Local']['ObserveOnly']
    assert bootstrap.json['Local']['ApiKey'] == 'fixture-internal'
    assert 'no-store' in bootstrap.headers['Cache-Control']
    assert 'fixture-discord-secret' not in bootstrap.text
    preview = client.post('/api/admin/chat-arkland/preview', headers=admin_headers, json={'config': {}})
    assert preview.status_code == 200 and '(125)' in preview.json['plain']
    with engine.connect() as db:
        assert db.execute(select(func.count()).select_from(PLAYERS)).scalar() == 0
    invalid = client.put('/api/admin/chat-arkland/config', headers=admin_headers,
        json={'expected_revision': 1, 'config': {'PollRate': 0}})
    assert invalid.status_code == 400
    assert client.get('/api/admin/chat-arkland', headers=admin_headers).json['revision'] == 1


def test_mysql_tables_do_not_inherit_legacy_latin1():
    from sqlalchemy.dialects import mysql
    from sqlalchemy.schema import CreateTable
    from chat_arkland_service import META
    for table in META.tables.values():
        ddl=str(CreateTable(table).compile(dialect=mysql.dialect()))
        assert 'utf8mb4' in ddl and 'InnoDB' in ddl


def test_discord_only_real_lumo_and_linked_humans_not_impersonators(monkeypatch):
    calls = []
    class Service:
        def load_config(self):
            return {'config': {'DisableChat': False, 'Discord': {'Enabled': True}, 'Maps': {'tek:aaa': {'Enabled': True}}}}
        def ingest_discord(self, *args, **kwargs):
            calls.append((args, kwargs))
        def relay_context(self, seq):
            return {'body': 'texto verificado', 'steam_id': '76561198000000001', 'seq': seq}
    monkeypatch.setattr(routes, '_SERVICE', Service())
    transport = ChatDiscordTransport(lambda: {'lumo_guild_id': '10', 'lumo_game_chat_channel_id': '20'})
    client = NS(user=NS(id=99))
    def message(author=99, bot=True, webhook=None, nonce=None, guild=10, channel=20, content='Olá'):
        return NS(id=123, guild=NS(id=guild), channel=NS(id=channel),
                  author=NS(id=author, bot=bot, display_name='Lumo'), webhook_id=webhook, nonce=nonce, content=content)
    async def scenario():
        for invalid in (message(author=98), message(webhook=1), message(guild=11), message(channel=21)):
            assert await transport.incoming(client, invalid) is None
        assert calls == []
        relay = await transport.incoming(client, message(nonce='ca:42'))
        assert relay['body'] == 'texto verificado' and relay['seq'] == 42 and calls == []
        await transport.incoming(client, message())
        assert calls[-1][1] == {'lumo': True}
        await transport.incoming(client, message(author=55, bot=False, nonce='ca:42', content='/pm 1 NÃO executar'))
        assert calls[-1][0][-1] == '/pm 1 NÃO executar' and calls[-1][1] == {'lumo': False}
    asyncio.run(scenario())


def test_lumo_uses_verified_original_body_without_bot_impersonation():
    from lumo_gateway import LumoGatewayRunner
    runner=LumoGatewayRunner(lambda:{'lumo_game_chat_enabled':True},lambda _:None,lambda _: {},lambda *args,**kwargs:None)
    captured=[]
    async def incoming(client,message):
        return {'event_id':'uuid-fixture','steam_id':'76561198000000001','body':'Lumo, ajuda'}
    async def handler(client,message,config,is_webhook):
        captured.append((message,is_webhook))
    runner._chat_transport.incoming=incoming
    runner._on_game_chat_message=handler
    message=NS(guild=NS(id=10),channel=NS(id=20),author=NS(id=99,bot=True),content='texto do relay')
    asyncio.run(runner._on_message(NS(user=NS(id=99)),message))
    assert len(captured)==1
    forwarded,is_webhook=captured[0]
    assert forwarded.content=='Lumo, ajuda' and forwarded.author.id=='76561198000000001'
    assert forwarded.id=='ca:uuid-fixture' and not is_webhook


def test_existing_permission_reader_respects_future_and_expired_groups(tmp_path,monkeypatch):
    sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
    from src import permission_entitlements_sync as permissions
    from sqlalchemy import text
    engine=create_engine(f"sqlite:///{tmp_path / 'permissions.sqlite'}")
    with engine.begin() as db:
        db.execute(text('CREATE TABLE players (SteamId TEXT,PermissionGroups TEXT,TimedPermissionGroups TEXT)'))
        db.execute(text("INSERT INTO players VALUES ('76561198000000001','Default,Admins','50;150;STAFF,101;200;Future,1;99;Expired,inválido')"))
    monkeypatch.setattr(permissions,'_perm_engine',lambda _:engine)
    monkeypatch.setattr(permissions.time,'time',lambda:100)
    groups=permissions.read_active_player_groups('fixture','76561198000000001')
    assert {'Default','Admins','STAFF'}<=set(groups)
    assert 'Future' not in groups and 'Expired' not in groups
    assert permissions.read_active_player_groups('fixture','invalid')==['Default']
