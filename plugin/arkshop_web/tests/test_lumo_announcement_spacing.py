import asyncio
import copy
from datetime import datetime,timedelta,timezone
from pathlib import Path
import sys
from types import SimpleNamespace as NS

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import lumo_gateway as gateway


def test_simultaneous_announcements_wait_persisted_gap_after_restart(monkeypatch):
    current=[datetime(2026,11,26,12,tzinfo=timezone.utc)]
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return current[0]
    monkeypatch.setattr(gateway,'datetime',Clock)
    monkeypatch.setattr(gateway.random,'randint',lambda a,b:17 if (a,b)==(15,20) else a)
    settings={'lumo_game_chat_enabled':True,'lumo_game_chat_announcements_enabled':True,
        'lumo_game_chat_channel_id':'20','lumo_game_auto_betland_enabled':True,'lumo_game_auto_polls_enabled':True,
        'lumo_game_auto_betland_next_at':current[0].isoformat(),'lumo_game_auto_polls_next_at':current[0].isoformat()}
    sent=[]
    class Channel:
        id=20
        async def send(self,text,**kwargs):sent.append((current[0],text));return NS(id=len(sent))
    client=NS(get_channel=lambda _:Channel())
    def save(value):settings.update(copy.deepcopy(value))
    def source(category):
        return {'ok':True,'enabled':True,'campaign':{'status':'ACTIVE','prize_amber_total':100,'seconds_remaining':3600}} if category=='betland' else {'ok':True,'polls':[{'is_open':True}]}
    def runner():return gateway.LumoGatewayRunner(lambda:copy.deepcopy(settings),save,source,lambda *args,**kwargs:None)
    async def scenario():
        first=runner()
        await first._game_scheduler_tick(client,copy.deepcopy(settings))
        assert len(sent)==1 and sent[0][1].startswith('BetLand:')
        pause=gateway._parse_utc(settings['lumo_game_announcements_not_before'])
        assert pause-current[0]==timedelta(minutes=17)
        assert gateway._parse_utc(settings['lumo_game_auto_polls_next_at'])==current[0]
        current[0]+=timedelta(minutes=16,seconds=59)
        restarted=runner()
        await restarted._game_scheduler_tick(client,copy.deepcopy(settings))
        assert len(sent)==1
        # Geral também ficou pendente; a votação mais antiga tem precedência.
        settings.update(lumo_game_general_announcements_enabled=True,lumo_game_general_next_at=current[0].isoformat())
        current[0]+=timedelta(seconds=1)
        await restarted._game_scheduler_tick(client,copy.deepcopy(settings))
        assert len(sent)==2 and 'votação' in sent[1][1]
        assert sent[1][0]-sent[0][0]==timedelta(minutes=17)
        await restarted._game_scheduler_tick(client,copy.deepcopy(settings))
        assert len(sent)==2
    asyncio.run(scenario())


def test_existing_last_announcement_establishes_gap_once(monkeypatch):
    current=datetime(2026,11,26,12,tzinfo=timezone.utc)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return current
    monkeypatch.setattr(gateway,'datetime',Clock)
    monkeypatch.setattr(gateway.random,'randint',lambda a,b:20)
    config={'lumo_game_chat_enabled':True,'lumo_game_chat_announcements_enabled':True,'lumo_game_chat_channel_id':'20',
            'lumo_game_last_auto_announcement_at':(current-timedelta(minutes=3)).isoformat()}
    saved=[]
    runner=gateway.LumoGatewayRunner(lambda:config,lambda value:saved.append(copy.deepcopy(value)),lambda _: {},lambda *args,**kwargs:None)
    async def scenario():
        await runner._game_scheduler_tick(NS(get_channel=lambda _:NS(id=20)),config)
        assert len(saved)==1
        assert gateway._parse_utc(config['lumo_game_announcements_not_before'])==current+timedelta(minutes=17)
        await runner._game_scheduler_tick(NS(get_channel=lambda _:NS(id=20)),config)
        assert len(saved)==1
    asyncio.run(scenario())


def test_failed_attempt_is_not_marked_sent_and_does_not_try_next_notice(monkeypatch):
    now=datetime(2026,11,26,12,tzinfo=timezone.utc)
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return now
    monkeypatch.setattr(gateway,'datetime',Clock)
    config={'lumo_game_chat_enabled':True,'lumo_game_chat_announcements_enabled':True,'lumo_game_chat_channel_id':'20',
        'lumo_game_auto_betland_enabled':True,'lumo_game_auto_polls_enabled':True,
        'lumo_game_auto_betland_next_at':now.isoformat(),'lumo_game_auto_polls_next_at':now.isoformat()}
    attempts=[]
    async def fail_send(*args,**kwargs):attempts.append(args);raise TimeoutError('Envio desconhecido')
    source=lambda kind:{'ok':True,'enabled':True,'campaign':{'status':'ACTIVE','prize_amber_total':100,'seconds_remaining':3600},'polls':[{'is_open':True}]}
    runner=gateway.LumoGatewayRunner(lambda:config,lambda _:None,source,lambda *args,**kwargs:None)
    asyncio.run(runner._game_scheduler_tick(NS(get_channel=lambda _:NS(id=20,send=fail_send)),config))
    assert len(attempts)==1 and config['lumo_game_auto_betland_last_result']=='failed'
    assert 'lumo_game_auto_betland_last_at' not in config and 'lumo_game_last_auto_announcement_at' not in config
    assert gateway._parse_utc(config['lumo_game_announcements_not_before'])==now+timedelta(minutes=15)
