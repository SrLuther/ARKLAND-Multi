import asyncio
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lumo_gateway as gateway
from lumo_audience import game_audience_snapshot, query_game_server


@pytest.mark.parametrize('results,expected', [
    ([], (True, False)),
    ([{'status':'online','players':[]}], (True, False)),
    ([{'status':'online','players':[]},{'status':'unavailable','players':[]}], (False, False)),
    ([{'status':'online','players':[True]},{'status':'unavailable','players':[]}], (True, True)),
    ([{'status':'online','players':None}], (False, False)),
])
def test_snapshot_requires_fresh_positive_or_known_empty(results, expected):
    value = game_audience_snapshot(results, lambda item: item)
    assert (value['ok'], value['has_players']) == expected
    assert set(value) == {'ok','has_players','confirmed_players'}


@pytest.mark.parametrize('reply,status,count', [
    ('No Players Connected', 'online', 0), ('\x00No Players Connected.\x00', 'online', 0),
    ('0. Jogador, 76561198000000001', 'online', 1), ('', 'unavailable', 0),
    ('Permission denied', 'unavailable', 0), ('1 player', 'unavailable', 0),
])
def test_rcon_only_accepts_recognized_listplayers(reply, status, count):
    calls=[]
    def execute(*args, **kwargs): calls.append(args[3]); return reply
    value=query_game_server({'server_id':'map'}, settings=lambda _: {'rcon_password':'private'},
        hosts=lambda *_:['127.0.0.1'], sanitize=lambda x:x, execute=execute,
        parse=lambda raw: [True] if raw.startswith('0. Jogador, 7656119') else [])
    assert value['status']==status and len(value['players'])==count and calls==['ListPlayers']


@pytest.mark.parametrize('category', ['general','season','betland','polls'])
@pytest.mark.parametrize('audience', [
    {'ok':True,'has_players':False,'confirmed_players':0}, {'ok':False},
    {'ok':True,'has_players':True,'confirmed_players':0},
])
def test_all_game_announcements_defer_without_confirmed_audience(monkeypatch, category, audience):
    now=datetime(2026,11,27,8,tzinfo=timezone.utc)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return now
    monkeypatch.setattr(gateway,'datetime',Clock)
    general=category in {'general','season'}
    key='lumo_game_general_next_at' if general else f'lumo_game_auto_{category}_next_at'
    settings={'lumo_game_chat_enabled':True,'lumo_game_chat_announcements_enabled':True,'lumo_game_chat_channel_id':'20',
              'lumo_game_general_announcements_enabled':general,'lumo_game_auto_betland_enabled':category=='betland',
              'lumo_game_auto_polls_enabled':category=='polls',key:now.isoformat(),
              'lumo_game_chat_topic_enabled':{t:t==('SEASON' if category=='season' else 'SITE') for t in ('SITE','LINK','CATALOG','STARTER','SUPPORT','STATUS','SEASON','LIMIT')}}
    baseline=copy.deepcopy(settings); sent=[]; calls=[]
    def source(kind):
        calls.append(kind)
        if kind=='game_audience':return audience
        return {'ok':True,'enabled':True,'campaign':{'status':'ACTIVE','prize_amber_total':100,'seconds_remaining':3600},
                'polls':[{'is_open':True}],'season':{'status':'active','name':'Gamma','days_remaining':5}}
    def save(value):settings.update(copy.deepcopy(value))
    async def send(*args,**kwargs):sent.append(args);return NS(id=1)
    runner=gateway.LumoGatewayRunner(lambda:copy.deepcopy(settings),save,source,lambda *args,**kwargs:None)
    # A cached positive must never authorize a later announcement.
    runner._source_cache['game_audience']=(gateway.time.monotonic(),{'ok':True,'has_players':True,'confirmed_players':2})
    asyncio.run(runner._game_scheduler_tick(NS(get_channel=lambda _:NS(id=20,send=send)),copy.deepcopy(settings)))
    assert not sent and calls.count('game_audience')==1
    assert settings[key]==baseline[key]
    assert 'lumo_game_general_last_topic' not in settings and 'lumo_game_last_auto_announcement_at' not in settings
    assert runner._announcements==0
    assert gateway._parse_utc(settings['lumo_game_announcements_not_before'])==now+timedelta(seconds=60)


def test_retry_survives_restart_and_sends_only_after_fresh_positive(monkeypatch):
    current=[datetime(2026,11,27,8,tzinfo=timezone.utc)]; readers=[0]; sent=[]; checks=[]
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return current[0]
    monkeypatch.setattr(gateway,'datetime',Clock)
    settings={'lumo_game_chat_enabled':True,'lumo_game_chat_announcements_enabled':True,'lumo_game_chat_channel_id':'20',
              'lumo_game_auto_polls_enabled':True,'lumo_game_auto_polls_next_at':current[0].isoformat()}
    def source(kind):
        if kind=='game_audience':checks.append(current[0]);return {'ok':True,'has_players':bool(readers[0]),'confirmed_players':readers[0]}
        return {'ok':True,'polls':[{'is_open':True}]}
    def save(value):settings.update(copy.deepcopy(value))
    async def send(*args,**kwargs):sent.append(args);return NS(id=1)
    def runner():return gateway.LumoGatewayRunner(lambda:copy.deepcopy(settings),save,source,lambda *args,**kwargs:None)
    async def scenario():
        await runner()._game_scheduler_tick(NS(get_channel=lambda _:NS(id=20,send=send)),copy.deepcopy(settings))
        current[0]+=timedelta(seconds=59);readers[0]=1
        restarted=runner()
        await restarted._game_scheduler_tick(NS(get_channel=lambda _:NS(id=20,send=send)),copy.deepcopy(settings))
        assert not sent and len(checks)==1
        current[0]+=timedelta(seconds=1)
        await restarted._game_scheduler_tick(NS(get_channel=lambda _:NS(id=20,send=send)),copy.deepcopy(settings))
        assert len(sent)==1 and len(checks)==2
        pause=gateway._parse_utc(settings['lumo_game_announcements_not_before'])-current[0]
        assert timedelta(minutes=15)<=pause<=timedelta(minutes=20)
    asyncio.run(scenario())


@pytest.mark.parametrize('channel_id,should_send', [('20',False),('30',True)])
def test_interaction_auto_only_uses_game_gate_when_channel_is_shared(monkeypatch, channel_id, should_send):
    now=datetime(2026,11,27,8,tzinfo=timezone.utc)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return now
    monkeypatch.setattr(gateway,'datetime',Clock)
    monkeypatch.setattr(gateway,'build_response',lambda *args:('Aviso','Texto do aviso'))
    settings={'lumo_assistant_enabled':True,'lumo_game_chat_channel_id':'20','lumo_interaction_channel_id':channel_id,
              'lumo_auto_betland_enabled':True,'lumo_auto_betland_next_at':now.isoformat()}
    sent=[]
    async def send(*args,**kwargs):sent.append(kwargs);return NS(id=1)
    def source(kind):return {'ok':True,'has_players':False,'confirmed_players':0} if kind=='game_audience' else {'ok':True,'enabled':True,'campaign':{'status':'ACTIVE','prize_amber_total':100,'seconds_remaining':3600}}
    runner=gateway.LumoGatewayRunner(lambda:copy.deepcopy(settings),lambda value:settings.update(value),source,lambda *args,**kwargs:None)
    asyncio.run(runner._scheduler_tick(NS(get_channel=lambda _:NS(id=int(channel_id),send=send))))
    assert bool(sent)==should_send
