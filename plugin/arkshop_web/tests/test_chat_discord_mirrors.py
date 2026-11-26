"""Cópia/remoção com Discord simulado e SQLite; nenhuma mensagem externa."""
import asyncio
import copy
import io
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat_arkland_config import DEFAULTS
from chat_arkland_service import ChatArklandService, DISCORD_SOURCES, MESSAGES_TABLE
from chat_arkland_discord import ChatDiscordTransport, source_parts


@pytest.fixture
def hub(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mirror.sqlite'}")
    sessions = sessionmaker(engine)
    now = [datetime(2026, 11, 26, 16)]
    service = ChatArklandService(sessions, lambda: engine,
        lambda: [{"server_id": "a", "arkland_ref": "tek:aaa", "label": "Mapa A"}], clock=lambda: now[0],
        discord_identity=lambda db, user: {"steam_id": "76561198000000001", "name": "Ciano", "groups": []} if user == "55" else None)
    config = copy.deepcopy(DEFAULTS)
    config["Maps"] = {"tek:aaa": {"Enabled": True, "Label": "A"}}
    service.publish_config(config, 1, "fixture")
    return service, sessions, now


def source(service, identifier="101", body="teste", *, author="55", lumo=False, attachments=()):
    return service.mirrors.capture(identifier, "10", "20", author, "Lumo" if lumo else "Discord Ciano", body,
        lumo=lumo, attachments=attachments, occurred_at="2026-11-26T16:00:00Z")


def claim(service, owner):
    service.claim_discord(owner)  # Obtém o lease compartilhado do publicador.
    return service.mirrors.claim(owner, "10", "20")


class Message:
    def __init__(self, channel, identifier, content="teste", *, author=55, bot=False):
        self.channel = channel; self.guild = channel.guild; self.id = identifier
        self.author = NS(id=author, bot=bot, display_name="Ciano")
        self.content = content; self.webhook_id = None; self.nonce = None
        self.attachments = []; self.stickers = []; self.components = []; self.poll = None
        self.embeds = []; self.created_at = None
    async def edit(self, **kwargs):
        if self.channel.fail_edit:
            raise TimeoutError("resultado desconhecido")
        self.content = kwargs["content"]; self.channel.edits.append(kwargs); return self
    async def delete(self):
        if self.channel.fail_delete:
            import discord
            raise discord.Forbidden(NS(status=403, reason="Forbidden"), "fixture")
        self.channel.deleted.append(self.id); self.channel.originals.pop(self.id, None)


class Channel:
    def __init__(self):
        self.id = 20; self.guild = NS(id=10, me=NS(id=99), filesize_limit=1024 * 1024)
        self.last_message_id = None; self.sent = []; self.edits = []; self.deleted = []; self.uploaded = []
        self.originals = {}; self.fail_send = False; self.fail_edit = False; self.fail_delete = False
        self.permissions = NS(view_channel=True, send_messages=True, read_message_history=True, manage_messages=True, attach_files=True)
    def permissions_for(self, member): return self.permissions
    async def fetch_message(self, identifier):
        if identifier not in self.originals:
            import discord
            raise discord.NotFound(NS(status=404, reason="Not Found"), "fixture")
        return self.originals[identifier]
    async def send(self, content, **kwargs):
        if self.fail_send: raise TimeoutError("não confirmar")
        message = Message(self, 1000 + len(self.sent), content, author=99, bot=True)
        message.nonce = kwargs.get("nonce")
        self.uploaded.extend(file.fp.getvalue() for file in kwargs.get("files", ()))
        self.sent.append((message, kwargs)); self.last_message_id = message.id
        return message


def transport():
    return ChatDiscordTransport(lambda: {"lumo_guild_id": "10", "lumo_game_chat_channel_id": "20"})


def test_first_snapshot_is_immutable_and_game_forward_is_once(hub):
    service, sessions, now = hub
    first = source(service, body="primeira versão")
    edited = source(service, body="VERSÃO EDITADA")
    assert first["snapshot"] == edited["snapshot"]
    assert "primeira versão" in edited["snapshot"]["discord_plain"] and "EDITADA" not in edited["snapshot"]["discord_plain"]
    assert "Ciano (1)" in first["snapshot"]["discord_plain"]
    assert first["snapshot"]["discord_plain"].startswith("[13:00][Discord]")
    service.mirrors.forward_live(first); service.mirrors.forward_live(edited)
    with sessions() as db:
        assert db.execute(select(func.count()).select_from(MESSAGES_TABLE)).scalar() == 1


def test_unlinked_human_named_lumo_cannot_look_like_the_bot(hub):
    service, _, _ = hub
    human = service.mirrors.capture("101", "10", "20", "77", "Lumo", "humano")
    bot = source(service, "102", "assistente", author="99", lumo=True)
    assert "Lumo [Discord ID 77]" in human["snapshot"]["discord_plain"]
    assert "Lumo:" in bot["snapshot"]["discord_plain"]


def test_human_and_lumo_append_to_game_block_before_original_delete(hub):
    service, sessions, _ = hub
    async def scenario():
        t = transport(); channel = Channel(); client = NS(user=NS(id=99))
        game = {"seq": 1, "payload": {"plain": "[13:00][A] Ciano (1): jogo"}}
        await t._publish(channel, game)
        for identifier, lumo in ((101, False), (102, True)):
            row = source(service, str(identifier), "Lumo responde" if lumo else "teste", author="99" if lumo else "55", lumo=lumo)
            channel.originals[identifier] = Message(channel, identifier, author=99 if lumo else 55, bot=lumo)
            channel.last_message_id = identifier; t._remember_source(identifier)
            pending = claim(service, t.owner)
            await t._copy_source(client, channel, service.mirrors, pending)
            assert identifier not in channel.deleted
            copied = service.mirrors.pending_deletion("10", "20")
            assert copied and copied["source_id"] == str(identifier)
            await t._delete_source(client, channel, service.mirrors, copied)
        assert channel.deleted == [101, 102] and len(channel.sent) == 1
        assert "jogo" in channel.sent[0][0].content and "teste" in channel.sent[0][0].content and "Lumo responde" in channel.sent[0][0].content
        assert all(not item[1]["allowed_mentions"].everyone for item in channel.sent)
    asyncio.run(scenario())
    with sessions() as db:
        assert set(db.execute(select(DISCORD_SOURCES.c.state)).scalars()) == {"deleted"}


def test_ambiguous_copy_preserves_original_and_never_retries_blindly(hub):
    service, _, _ = hub
    async def scenario():
        t = transport(); channel = Channel(); channel.fail_send = True
        channel.originals[101] = Message(channel, 101); source(service)
        await t._copy_source(NS(user=NS(id=99)), channel, service.mirrors, claim(service, t.owner))
        assert channel.deleted == [] and channel.sent == []
        assert service.mirrors.pending_deletion("10", "20") is None
        assert claim(service, t.owner) is None
    asyncio.run(scenario())
    with service.database() as db:
        assert service.mirrors.stats(db)["counts"] == {"uncertain": 1}


def test_delete_failure_retries_only_delete_not_copy(hub):
    service, _, now = hub
    async def scenario():
        t = transport(); channel = Channel(); client = NS(user=NS(id=99))
        channel.originals[101] = Message(channel, 101); source(service)
        await t._copy_source(client, channel, service.mirrors, claim(service, t.owner))
        channel.fail_delete = True
        await t._delete_source(client, channel, service.mirrors, service.mirrors.pending_deletion("10", "20"))
        assert channel.deleted == [] and len(channel.sent) == 1
        now[0] += timedelta(seconds=31); channel.fail_delete = False
        await t._delete_source(client, channel, service.mirrors, service.mirrors.pending_deletion("10", "20"))
        assert channel.deleted == [101] and len(channel.sent) == 1
    asyncio.run(scenario())


def test_missing_permission_never_publishes_or_deletes(hub):
    service, _, _ = hub
    async def scenario():
        t = transport(); channel = Channel(); channel.permissions.manage_messages = False
        channel.originals[101] = Message(channel, 101); source(service)
        await t._copy_source(NS(user=NS(id=99)), channel, service.mirrors, claim(service, t.owner))
        assert channel.sent == [] and channel.deleted == []
    asyncio.run(scenario())
    with service.database() as db:
        assert service.mirrors.stats(db)["errors"] == ["missing_manage_messages"]


def test_attachment_bytes_are_copied_before_deletion(hub):
    service, _, _ = hub
    class Attachment:
        id = 77; filename = "imagem.png"; size = 4
        def is_spoiler(self): return False
        async def to_file(self, **kwargs):
            import discord
            return discord.File(io.BytesIO(b"DATA"), filename=self.filename)
    async def scenario():
        t = transport(); channel = Channel(); client = NS(user=NS(id=99))
        original = Message(channel, 101); original.attachments = [Attachment()]; channel.originals[101] = original
        source(service, attachments=[{"id": "77", "filename": "imagem.png", "size": 4}])
        await t._copy_source(client, channel, service.mirrors, claim(service, t.owner))
        assert channel.uploaded == [b"DATA"] and channel.deleted == []
        await t._delete_source(client, channel, service.mirrors, service.mirrors.pending_deletion("10", "20"))
        assert channel.deleted == [101]
    asyncio.run(scenario())


def test_long_unicode_is_split_without_truncation_or_fence_escape():
    text = "[13:00][Discord] Ciano: " + "🦖" * 3000 + " ``` fim"
    parts = source_parts(text, "Ciano (1)")
    assert len(parts) > 1 and sum(part.count("🦖") for part in parts) == 3000
    assert all(len(("```text\n" + part + "\n```").encode("utf-16-le")) // 2 <= 2000 for part in parts)
    assert "ˋˋˋ fim" in parts[-1]


def test_edits_are_ignored_for_managed_humans_and_lumo():
    from lumo_gateway import LumoGatewayRunner
    runner = LumoGatewayRunner(lambda: {"lumo_game_chat_enabled": True, "lumo_guild_id": "10", "lumo_game_chat_channel_id": "20"}, lambda _: None, lambda _: {}, lambda *args, **kwargs: None)
    calls = []
    async def react(*args): calls.append(args)
    runner._on_game_chat_message = react
    async def scenario():
        channel = Channel()
        for author, bot in ((55, False), (99, True)):
            after = Message(channel, 101, "texto editado Lumo", author=author, bot=bot)
            await runner._on_message_edit(NS(user=NS(id=99)), NS(content="primeiro"), after)
    asyncio.run(scenario())
    assert calls == []


def test_copy_queue_survives_a_new_service_instance(hub):
    service, sessions, now = hub
    captured = source(service, body="continua depois de reiniciar")
    reopened = ChatArklandService(sessions, service.engine_getter, service.servers, clock=lambda: now[0])
    row = claim(reopened, "new-worker")
    assert row["snapshot"] == captured["snapshot"]
    assert reopened.mirrors.pending_deletion("10", "20") is None


def test_original_removed_before_copy_is_not_recreated(hub):
    service, sessions, _ = hub
    async def scenario():
        t = transport(); channel = Channel(); source(service)
        await t._copy_source(NS(user=NS(id=99)), channel, service.mirrors, claim(service, t.owner))
        assert channel.sent == [] and channel.deleted == []
    asyncio.run(scenario())
    with sessions() as db:
        assert db.execute(select(DISCORD_SOURCES.c.state)).scalar() == "source_gone"


def test_incoming_copy_echo_is_not_ingested_as_lumo(monkeypatch, hub):
    import chat_arkland_routes as routes
    service, sessions, _ = hub
    monkeypatch.setattr(routes, "_SERVICE", service)
    async def scenario():
        t = transport(); channel = Channel(); client = NS(user=NS(id=99))
        original = Message(channel, 101); channel.originals[101] = original
        await t.incoming(client, original)
        await t._copy_source(client, channel, service.mirrors, claim(service, t.owner))
        copy_message = channel.sent[0][0]
        assert copy_message.nonce.startswith("ca:")
        # Inclusive antes de o evento de criação depender do cache de IDs.
        t._relay_id_set.clear()
        await t.incoming(client, copy_message)
    asyncio.run(scenario())
    with sessions() as db:
        assert db.execute(select(func.count()).select_from(DISCORD_SOURCES)).scalar() == 1
        assert db.execute(select(func.count()).select_from(MESSAGES_TABLE)).scalar() == 1


def test_copy_does_not_truncate_long_source_or_duplicate_game_parts(hub):
    service, sessions, _ = hub
    body = "palavra " * 500
    row = source(service, body=body)
    service.mirrors.forward_live(row); service.mirrors.forward_live(row)
    assert len(row["snapshot"]["body"]) > 500
    assert row["snapshot"]["body"].endswith("palavra")
    with sessions() as db:
        messages = db.execute(select(MESSAGES_TABLE)).mappings().all()
        import json
        parts = [json.loads(message["payload_json"])["body"] for message in messages]
        assert len(messages) == len(row["snapshot"]["game_chunks"])
        assert " ".join(parts) == row["snapshot"]["body"]


def test_wrong_channel_and_unconfirmed_receipt_never_delete(hub):
    service, _, _ = hub
    async def scenario():
        t = transport(); channel = Channel(); channel.originals[101] = Message(channel, 101)
        source(service); row = claim(service, t.owner)
        row["copy_ids"] = ["1000"]; row["channel_id"] = "21"
        await t._delete_source(NS(user=NS(id=99)), channel, service.mirrors, row)
        assert channel.deleted == []
        row["channel_id"] = "20"; row["copy_ids"] = []
        await t._delete_source(NS(user=NS(id=99)), channel, service.mirrors, row)
        assert channel.deleted == []
    asyncio.run(scenario())


def test_worker_copies_and_deletes_without_reacting_to_the_copy(monkeypatch, hub):
    import chat_arkland_routes as routes
    service, sessions, _ = hub
    monkeypatch.setattr(routes, "_SERVICE", service)
    async def scenario():
        t = transport(); channel = Channel(); channel.originals[101] = Message(channel, 101)
        reactions = []
        async def react(*args): reactions.append(args)
        t.relay_handler = react
        class Client:
            user = NS(id=99)
            def is_closed(self): return channel.deleted == [101]
            def get_channel(self, identifier): return channel
        await t.incoming(Client(), channel.originals[101])
        await asyncio.wait_for(t.run(Client()), timeout=8)
        assert channel.deleted == [101] and len(channel.sent) == 1
        assert reactions == []
        assert t.mirror_snapshot()["ready"]
    asyncio.run(scenario())
