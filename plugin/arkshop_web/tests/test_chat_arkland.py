from __future__ import annotations

import copy
from datetime import datetime, timedelta
from pathlib import Path
import sys
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat_arkland_config import DEFAULTS, censor, format_global, select_style, validate_config
from chat_arkland_service import ChatArklandService, DELIVERIES, MESSAGES_TABLE, PLAYERS

A, B, C = "76561198000000001", "76561198000000002", "76561198000000003"


@pytest.fixture
def hub(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'chat.sqlite'}")
    sessions = sessionmaker(engine)
    now = [datetime(2026, 11, 26, 12)]
    service = ChatArklandService(sessions, lambda: engine,
        lambda: [{"server_id": "map-a", "arkland_ref": "tek:aaa", "label": "Mapa A"},
                 {"server_id": "map-b", "arkland_ref": "tek:bbb", "label": "Mapa B"}], clock=lambda: now[0])
    config = copy.deepcopy(DEFAULTS)
    config["Maps"] = {"tek:aaa": {"Enabled": True, "Label": "Mapa A"}, "tek:bbb": {"Enabled": True, "Label": "Mapa B"}}
    service.publish_config(config, 1, "admin")
    return service, sessions, now


def player(steam, boot, *, name="Mesmo nome", session=None, groups=None):
    return {"steam_id": steam, "name": name, "character_id": "123", "tribe_id": "456", "tribe_name": "Tribo",
            "groups": groups or ["Default"], "session_id": "ca-" + boot + "-" + (session or uuid.uuid4().hex)}


def exchange(service, key, boot, players, events=(), **extra):
    return service.exchange({"server_key": key, "boot_id": boot, "players": players, "events": list(events), "acks": [],
        "revision": 0, "cursor": 0, "resume": True, "observer": False, **extra})


def event(steam, kind, body):
    return {"event_id": str(uuid.uuid4()), "steam_id": steam, "kind": kind, "body": body}


def test_defaults_validation_censorship_and_required_public_id():
    config = validate_config({})
    assert config["PollRate"] == 1.0
    assert config["PrivateMessages"]["Enabled"] is True
    assert config["BadWords"]["Enabled"] is False
    config["BadWords"].update(Enabled=True, Words=["palavra"])
    for body in ("Essa PALAVRA é proibida", "Essa p.a.l.a.v.r.a é proibida", "Essa p4l4vr4 é proibida"):
        filtered = censor(body, config)
        assert "palavra" not in filtered.casefold()
        assert "*" in filtered
    assert censor("palavração e antepalavra são outras palavras", config) == "palavração e antepalavra são outras palavras"
    for patch in ({"PollRate": 0}, {"PollRate": True}, {"PollRate": float("nan")}, {"Token": "não permitido"},
                  {"Messages": {"Global": "{mensagem}"}}, {"Messages": {"NoPermission": "{__class__}"}}):
        with pytest.raises(ValueError):
            validate_config(patch)
    actor = {"name": "João", "tribe_name": "", "groups": []}
    rendered = format_global(config, actor, "125", "Valguero [OMEGA]", "Olá, ç! <tag>")
    assert "João (125):" in rendered["plain"]
    assert "Olá, ç!" in rendered["plain"]
    assert "&lt;tag&gt;" in rendered["rich"]
    assert "AM" not in rendered["plain"] and "PM" not in rendered["plain"]


def test_tag_priority_confirmation_and_expired_license():
    config = copy.deepcopy(DEFAULTS)
    config["Tags"] = [
        {"Key": "spirit", "Label": "SPIRIT", "Kind": "license", "Priority": 0, "Enabled": True, "Approved": True, "LicenseGroups": ["spirit"]},
        {"Key": "mod", "Label": "Moderador", "Kind": "admin", "Priority": 1, "Enabled": True, "Approved": True, "PermissionGroups": ["Mod"]},
        {"Key": "staff", "Label": "STAFF", "Kind": "admin", "Priority": 0, "Enabled": True, "Approved": True, "PermissionGroups": ["STAFF"]},
    ]
    config = validate_config(config)
    assert select_style(config, {"groups": ["l_spirit"]}, set())[0] is None
    assert select_style(config, {"groups": []}, {"spirit"})[0]["Label"] == "SPIRIT"
    assert select_style(config, {"groups": ["Mod"]}, {"spirit"})[0]["Label"] == "Moderador"
    assert select_style(config, {"groups": ["Mod", "STAFF"]}, {"spirit"})[0]["Label"] == "STAFF"
    config["Tags"][2]["Approved"] = False
    assert select_style(config, {"groups": ["Mod", "STAFF"]}, {"spirit"})[0]["Label"] == "Moderador"


def test_global_ids_are_persistent_deduplicated_and_spam_is_enforced(hub):
    service, sessions, now = hub
    pa, pb = player(A, "aaaaaaaa"), player(B, "bbbbbbbb")
    first = exchange(service, "tek:aaa", "aaaaaaaa", [pa])
    aid = first["players"][A]["public_id"]
    exchange(service, "tek:bbb", "bbbbbbbb", [pb])
    message = event(A, "global", "Olá, cluster!")
    sent = exchange(service, "tek:aaa", "aaaaaaaa", [pa], [message])
    retry = exchange(service, "tek:aaa", "aaaaaaaa", [pa], [message])
    incoming = exchange(service, "tek:bbb", "bbbbbbbb", [pb])
    globals = [item for item in incoming["deliveries"] if item["kind"] == "global"]
    assert len(globals) == 1 and f"({aid})" in globals[0]["plain"]
    assert globals[0]["body"] == "Olá, cluster!"
    assert sent["accepted"] == retry["accepted"] == [message["event_id"]]
    blocked = exchange(service, "tek:aaa", "aaaaaaaa", [pa], [event(A, "global", "Outro")])
    assert any("Aguarde" in item.get("text", "") for item in blocked["deliveries"])
    assert exchange(service, "tek:aaa", "aaaaaaaa", [pa])["players"][A]["public_id"] == aid
    with sessions() as db:
        assert db.execute(select(PLAYERS.c.public_id).where(PLAYERS.c.steam_id == A)).scalar() == int(aid)


def test_private_messages_follow_id_across_maps_do_not_leak_or_retarget_reply(hub):
    service, sessions, now = hub
    pa, pb, pc = player(A, "aaaaaaaa"), player(B, "bbbbbbbb"), player(C, "aaaaaaaa")
    exchange(service, "tek:aaa", "aaaaaaaa", [pa, pc])
    target = exchange(service, "tek:bbb", "bbbbbbbb", [pb])["players"][B]["public_id"]
    message = event(A, "pm", target + " Segredo privado")
    sent = exchange(service, "tek:aaa", "aaaaaaaa", [pa, pc], [message])
    incoming = exchange(service, "tek:bbb", "bbbbbbbb", [pb])
    private = [item for item in incoming["deliveries"] if item["kind"] == "pm"]
    assert len(private) == 1 and private[0]["recipients"] == [B]
    assert "Segredo privado" in private[0]["text"]
    assert not any(item["kind"] == "pm" and C in item["recipients"] for item in sent["deliveries"])
    exchange(service, "tek:aaa", "aaaaaaaa", [pa, pc], [event(A, "global", "Público")])
    reply = exchange(service, "tek:bbb", "bbbbbbbb", [pb], [event(B, "reply", "Resposta privada")],
        acks=[{"delivery_id": private[0]["delivery_id"], "recipient": B}])
    assert any(item["kind"] == "pm" and "Resposta privada" in item["text"] for item in reply["deliveries"])
    with sessions() as db:
        assert all(state == "skip" for state in db.execute(select(MESSAGES_TABLE.c.discord_state).where(MESSAGES_TABLE.c.kind == "pm")).scalars())
    assert service.claim_discord("publisher")["payload"]["body"] == "Público"


def test_individual_notifications_and_observation_mode(hub):
    service, sessions, now = hub
    pa = player(A, "aaaaaaaa")
    observed = exchange(service, "tek:aaa", "aaaaaaaa", [pa], [event(A, "global", "não encaminhar")], observer=True)
    assert observed["observer"] is True and observed["deliveries"] == []
    with sessions() as db:
        assert db.execute(text("SELECT COUNT(*) FROM game_players")).scalar() == 0
    active = exchange(service, "tek:aaa", "aaaaaaaa", [pa], [event(A, "joinleave", "")])
    assert any("desativadas" in item.get("text", "") for item in active["deliveries"])
    latest = exchange(service, "tek:aaa", "aaaaaaaa", [pa])
    assert latest["players"][A]["notifications"] is False


def test_config_cas_and_discord_one_publisher_and_no_echo(hub):
    service, sessions, now = hub
    with pytest.raises(ValueError, match="outra pessoa"):
        service.publish_config({}, 1, "stale-admin")
    pa = player(A, "aaaaaaaa")
    exchange(service, "tek:aaa", "aaaaaaaa", [pa], [event(A, "global", "Mensagem")])
    claimed = service.claim_discord("one")
    assert claimed and service.claim_discord("two") is None
    context = service.relay_context(claimed["seq"])
    assert context["body"] == "Mensagem"
    service.confirm_discord(claimed["seq"], "one", None)
    assert service.claim_discord("one") is None
    assert service.ingest_discord("123", "456", "Bot não jogador", "Texto do Lumo", lumo=True)
    assert not service.ingest_discord("123", "456", "Lumo", "Duplicado", lumo=True)
    received = exchange(service, "tek:aaa", "aaaaaaaa", [pa])
    lumo = [item for item in received["deliveries"] if item.get("sender_name") == "Lumo"]
    assert len(lumo) == 1 and lumo[0]["public_id"] is None
    assert service.claim_discord("one") is None


def test_same_poll_preference_refresh_and_invalid_or_offline_private_id(hub):
    service, sessions, now = hub
    pa = player(A, "aaaaaaaa")
    result = exchange(service, "tek:aaa", "aaaaaaaa", [pa], [event(A, "joinleave", "")])
    assert result["players"][A]["notifications"] is False
    assert not any(item['kind'] == 'notification' for item in result['deliveries'])
    for target in ('999999', result['players'][A]['public_id']):
        response = exchange(service, "tek:aaa", "aaaaaaaa", [pa], [event(A, 'pm', target + ' segredo')])
        assert not any(item['kind'] == 'pm' for item in response['deliveries'])
        assert any(item['kind'] == 'notice' for item in response['deliveries'])


def test_private_transfer_releases_lease_and_reply_requires_received_ack(hub):
    service, sessions, now = hub
    pa, pb = player(A, 'aaaaaaaa'), player(B, 'bbbbbbbb')
    exchange(service, 'tek:aaa', 'aaaaaaaa', [pa])
    bid = exchange(service, 'tek:bbb', 'bbbbbbbb', [pb])['players'][B]['public_id']
    response = exchange(service, 'tek:aaa', 'aaaaaaaa', [pa], [event(A, 'pm', bid + ' transferência')])
    incoming = exchange(service, 'tek:bbb', 'bbbbbbbb', [pb])
    private = next(item for item in incoming['deliveries'] if item['kind'] == 'pm')
    # O destino ainda não confirmou que exibiu a mensagem.
    with sessions() as db:
        assert db.execute(select(PLAYERS.c.reply_to).where(PLAYERS.c.steam_id == B)).scalar() is None
    exchange(service, 'tek:bbb', 'bbbbbbbb', [])
    now[0] += timedelta(seconds=4)
    moved = player(B, 'aaaaaaaa')
    delivered = exchange(service, 'tek:aaa', 'aaaaaaaa', [pa, moved])
    received = next(item for item in delivered['deliveries'] if item.get('delivery_id') == private['delivery_id'])
    assert received['recipients'] == [B]
    exchange(service, 'tek:aaa', 'aaaaaaaa', [pa, moved], acks=[{'delivery_id': received['delivery_id'], 'recipient': B}])
    with sessions() as db:
        assert db.execute(select(PLAYERS.c.reply_to).where(PLAYERS.c.steam_id == B)).scalar() == A
    assert not any(item.get('delivery_id') == private['delivery_id'] for item in exchange(service, 'tek:aaa', 'aaaaaaaa', [pa, moved])['deliveries'])


def test_only_stable_registry_keys_and_graceful_restart(hub):
    service, sessions, now = hub
    original = service.servers
    service.servers = lambda: [*original(), {'server_id': 'mutable-name', 'label': 'Sem identidade'}]
    assert 'mutable-name' not in service.catalog()
    pa = player(A, 'aaaaaaaa')
    public_id = exchange(service, 'tek:aaa', 'aaaaaaaa', [pa])['players'][A]['public_id']
    with pytest.raises(ValueError, match='mesma ServerKey'):
        exchange(service, 'tek:aaa', 'cccccccc', [player(A, 'cccccccc')])
    exchange(service, 'tek:aaa', 'aaaaaaaa', [], stopping=True)
    restarted = exchange(service, 'tek:aaa', 'cccccccc', [player(A, 'cccccccc')])
    assert restarted['players'][A]['public_id'] == public_id


@pytest.mark.parametrize('kind,body,expected', [('reply','Olá','Inicie uma conversa'),('pm','0 Olá','inválido'),
    ('pm','abc Olá','inválido'),('pm','999999 Olá','inválido'),('pm','1','Use'),('global','','Digite uma mensagem')])
def test_private_and_text_errors_are_only_notices(hub, kind, body, expected):
    service, sessions, now = hub
    response=exchange(service,'tek:aaa','aaaaaaaa',[player(A,'aaaaaaaa')],[event(A,kind,body)])
    notices=[item for item in response['deliveries'] if item['kind']=='notice']
    assert any(expected in item['text'] for item in notices)
    assert all(item['recipients']==[A] for item in notices)
    assert not any(item['kind'] in {'pm','global'} for item in response['deliveries'])


def test_online_pagination_identity_and_disconnect_name(hub):
    service, sessions, now=hub
    config=copy.deepcopy(service.load_config()['config'])
    config['OnlinePlayersCommand']['AmountPerPage']=1
    service.publish_config(config,2,'admin')
    pa,pb=player(A,'aaaaaaaa',name='João'),player(B,'bbbbbbbb',name='Maria')
    aid=exchange(service,'tek:aaa','aaaaaaaa',[pa])['players'][A]['public_id']
    exchange(service,'tek:bbb','bbbbbbbb',[pb])
    response=exchange(service,'tek:aaa','aaaaaaaa',[pa],[event(A,'online','1')])
    listing=next(item for item in response['deliveries'] if item['kind']=='online')
    assert 'página 1/2' in listing['text'] and f'João ({aid})' in listing['text']
    assert 'Mapa A' not in listing['text']  # Default não revela localização.
    cursor=response['cursor']
    exchange(service,'tek:aaa','aaaaaaaa',[])
    remaining=exchange(service,'tek:bbb','bbbbbbbb',[pb],cursor=cursor)
    assert any('João' in item.get('text','') and 'saiu' in item.get('text','') for item in remaining['deliveries'])


def test_cross_disabled_keeps_local_and_offline_private_target_is_not_delivered(hub):
    service,sessions,now=hub
    pa,pb=player(A,'aaaaaaaa'),player(B,'bbbbbbbb')
    exchange(service,'tek:aaa','aaaaaaaa',[pa])
    bid=exchange(service,'tek:bbb','bbbbbbbb',[pb])['players'][B]['public_id']
    exchange(service,'tek:bbb','bbbbbbbb',[])
    result=exchange(service,'tek:aaa','aaaaaaaa',[pa],[event(A,'pm',bid+' segredo')])
    assert any('desconectado' in item.get('text','') for item in result['deliveries'])
    config=copy.deepcopy(service.load_config()['config']);config['DisableCrossServerChat']=True
    service.publish_config(config,2,'admin')
    local=exchange(service,'tek:aaa','aaaaaaaa',[pa],[event(A,'global','Somente local')])
    remote=exchange(service,'tek:bbb','bbbbbbbb',[pb])
    assert any(item['kind']=='global' for item in local['deliveries'])
    assert not any(item['kind']=='global' for item in remote['deliveries'])


def test_status_reports_transport_without_claiming_game_validation(hub):
    from system_status_center import chat_instances_snapshot,ensure_system_status_schema
    service,sessions,now=hub
    exchange(service,'tek:aaa','aaaaaaaa',[player(A,'aaaaaaaa')],observer=True)
    engine=service.engine_getter();ensure_system_status_schema(engine)
    status=chat_instances_snapshot(engine,service.servers())
    assert len(status)==2 and status[1]['operational']=='NAO_MONITORADO'
    assert status[0]['operational']!='OPERACIONAL'
