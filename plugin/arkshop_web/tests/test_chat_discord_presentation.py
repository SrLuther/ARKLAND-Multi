"""Apresentação Discord com mensagens simuladas; nenhuma chamada externa."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace as NS

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from chat_arkland_discord import ChatDiscordTransport,chat_code_block,discord_chat_line


class Channel:
    def __init__(self):
        self.id=20;self.guild=NS(id=10);self.last_message_id=None
        self.sent=[];self.edited=[];self.fail_edit=False
    async def send(self,content,**kwargs):
        message=Message(self,100+len(self.sent),content)
        self.sent.append((message,kwargs));self.last_message_id=message.id
        return message


class Message:
    def __init__(self,channel,identifier,content):
        self.channel=channel;self.id=identifier;self.content=content
    async def edit(self,**kwargs):
        if self.channel.fail_edit:
            raise TimeoutError('Resultado desconhecido')
        self.content=kwargs['content'];self.channel.edited.append(kwargs)
        return self


def pending(seq,text):
    return {'seq':seq,'event_id':f'uuid-{seq}','sender_steam':'76561198000000001',
            'payload':{'plain':text,'discord_plain':text,'body':text}}


def test_groups_lines_without_reposting_history_or_mentions():
    async def scenario():
        transport=ChatDiscordTransport(lambda:{})
        channel=Channel()
        first=await transport._publish(channel,pending(1,'[07:19][The Island] Ciano (1): Olá!'))
        second=await transport._publish(channel,pending(2,'[07:20][The Island] Ciano (1): ``` @everyone'))
        assert first==second and len(channel.sent)==1 and len(channel.edited)==1
        rendered=channel.sent[0][0].content
        assert rendered.startswith('```text\n') and rendered.endswith('\n```')
        assert rendered.count('```')==2 and 'ˋˋˋ @everyone' in rendered
        assert rendered.count('Ciano (1)')==2
        assert channel.sent[0][1]['allowed_mentions'].everyone is False
        assert channel.edited[0]['allowed_mentions'].everyone is False
        channel.last_message_id=999  # Outra conversa apareceu no canal.
        await transport._publish(channel,pending(3,'[07:21] Outra linha'))
        assert len(channel.sent)==2 and 'Ciano' not in channel.sent[1][0].content
    asyncio.run(scenario())


def test_discord_limit_unicode_and_rollover_preserve_previous_blocks():
    async def scenario():
        transport=ChatDiscordTransport(lambda:{})
        channel=Channel()
        await transport._publish(channel,pending(1,'A'*1100))
        await transport._publish(channel,pending(2,'B'*1100))
        assert len(channel.sent)==2 and channel.sent[0][0].content.count('A')==1100
        assert 'A' not in channel.sent[1][0].content
        line=discord_chat_line('🦖'*1500)
        assert len(chat_code_block([line]).encode('utf-16-le'))//2<=2000
        assert line.endswith('…')
    asyncio.run(scenario())


def test_ambiguous_edit_is_not_repeated_in_next_block():
    async def scenario():
        transport=ChatDiscordTransport(lambda:{})
        channel=Channel()
        await transport._publish(channel,pending(1,'primeira'))
        channel.fail_edit=True
        try:
            await transport._publish(channel,pending(2,'incerta'))
        except TimeoutError:
            pass
        else:
            raise AssertionError('Envio ambíguo deveria ter falhado')
        await transport._publish(channel,pending(3,'terceira'))
        assert len(channel.sent)==2 and 'incerta' not in channel.sent[1][0].content
    asyncio.run(scenario())


def test_group_publisher_delivers_each_original_event_once_to_lumo(monkeypatch):
    import chat_arkland_routes as routes
    async def scenario():
        channel=Channel();confirmed=[];reacted=[]
        class Service:
            def load_config(self):return {'config':{'PollRate':0.1}}
            def claim_discord(self,owner):return pending(len(confirmed)+1,f'original-{len(confirmed)+1}')
            def confirm_discord(self,seq,owner,message_id):confirmed.append((seq,message_id))
        class Client:
            def is_closed(self):return len(confirmed)>=2
            def get_channel(self,identifier):return channel
        async def react(client,target,context):reacted.append(context)
        monkeypatch.setattr(routes,'_SERVICE',Service())
        transport=ChatDiscordTransport(lambda:{'lumo_guild_id':'10','lumo_game_chat_channel_id':'20'},relay_handler=react)
        await transport.run(Client())
        assert len(channel.sent)==1 and len(channel.edited)==1
        assert [x['body'] for x in reacted]==['original-1','original-2']
        assert [x['event_id'] for x in reacted]==['uuid-1','uuid-2']
        assert confirmed[0][1]==confirmed[1][1]
    asyncio.run(scenario())


def test_own_group_edit_is_not_a_new_lumo_question():
    from lumo_gateway import LumoGatewayRunner
    runner=LumoGatewayRunner(lambda:{'lumo_game_chat_enabled':True,'lumo_guild_id':'10','lumo_game_chat_channel_id':'20'},lambda _:None,lambda _: {},lambda *args,**kwargs:None)
    captured=[]
    async def handler(*args,**kwargs):captured.append(args)
    runner._on_game_chat_message=handler
    before=NS(content='linha anterior')
    after=NS(id=100,nonce='ca:1',author=NS(id=99,bot=True),guild=NS(id=10),channel=NS(id=20),content='```text\nLumo, ajuda\n```')
    asyncio.run(runner._on_message_edit(NS(user=NS(id=99)),before,after))
    assert captured==[]
