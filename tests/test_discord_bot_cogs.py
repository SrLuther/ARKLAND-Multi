"""Cogs portados (admin/moderação/voz) testados com mocks — sem conectar ao Discord."""
from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

discord = pytest.importorskip("discord")
from discord.ext import commands  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.discord_bot import storage  # noqa: E402
from src.discord_bot.bot import ObobonicBot, enabled_cog_modules, load_cogs  # noqa: E402
from src.discord_bot.moderation import Moderation  # noqa: E402
from src.discord_bot.settings import BotSettings  # noqa: E402
from src.discord_bot.voice_manager import VoiceManager  # noqa: E402

FAKE_TOKEN = "fake.discord.token-for-tests"


def _settings(tmp_path, **kw) -> BotSettings:
    base = dict(token=FAKE_TOKEN, data_dir=tmp_path, lobby_channel_id=100, logs_channel_id=200,
                quarantine_role_id=300)
    base.update(kw)
    return BotSettings(**base)


def _fake_bot(settings: BotSettings) -> SimpleNamespace:
    storage.ensure_data_dir(settings.data_dir)
    return SimpleNamespace(
        settings=settings, channel_cache=None, role_cache=None,
        get_channel=lambda _id: None,
    )


def run(coro):
    return asyncio.run(coro)


# ── Carregamento / comandos ──────────────────────────────────────────────────
class TestBotLoadsOnlyThreeCogs:
    def test_enabled_modules(self, tmp_path):
        mods = enabled_cog_modules(_settings(tmp_path))
        assert [m.rsplit(".", 1)[1] for m in mods] == ["admin", "voice_manager", "moderation"]
        only_admin = enabled_cog_modules(_settings(tmp_path, enable_voice=False, enable_moderation=False))
        assert [m.rsplit(".", 1)[1] for m in only_admin] == ["admin"]

    def test_load_extensions_registers_commands_and_aliases(self, tmp_path):
        async def scenario():
            bot = ObobonicBot(_settings(tmp_path))
            async with bot:
                assert await load_cogs(bot) is True
                names = {c.name for c in bot.commands}
                assert names == {"faxina", "limpar", "limpezageral", "reload", "load", "unload", "restart", "shutdown"}
                aliases = {a for c in bot.commands for a in c.aliases}
                assert {"purgeall", "clear", "limparall", "recarregar", "carregar", "descarregar",
                        "reboot", "reiniciar", "desligar"} <= aliases
                assert set(bot.cogs) == {"Admin", "VoiceManager", "Moderation"}
            return True

        assert run(scenario())

    def test_intents_match_original(self, tmp_path):
        bot = ObobonicBot(_settings(tmp_path))
        assert bot.intents.members and bot.intents.message_content and bot.intents.voice_states
        assert bot.command_prefix == "!"
        run(bot.close())

    def test_custom_prefix(self, tmp_path):
        bot = ObobonicBot(_settings(tmp_path, command_prefix="?"))
        assert bot.command_prefix == "?"
        run(bot.close())


# ── Moderação ────────────────────────────────────────────────────────────────
def _message(content: str, *, bot=False, guild=True):
    msg = MagicMock()
    msg.author = MagicMock(bot=bot, mention="<@1>")
    msg.guild = MagicMock() if guild else None
    msg.content = content
    msg.delete = AsyncMock()
    msg.channel.send = AsyncMock()
    return msg


class TestModerationCog:
    def _cog(self, tmp_path, words=None):
        s = _settings(tmp_path)
        bot = _fake_bot(s)
        if words is not None:
            (tmp_path / storage.BADWORDS_FILENAME).write_text("\n".join(words) + "\n", encoding="utf-8")
        return Moderation(bot), bot  # type: ignore[arg-type]

    def test_loads_badwords_from_app_data_dir(self, tmp_path):
        cog, _ = self._cog(tmp_path, ["idiota", "burro"])
        assert cog.badwords_count == 2

    def test_missing_badword_file_disables_filter(self, tmp_path):
        s = _settings(tmp_path)
        bot = SimpleNamespace(settings=s, channel_cache=None, role_cache=None, get_channel=lambda _i: None)
        cog = Moderation(bot)  # type: ignore[arg-type]
        assert cog.badwords_regex is None and cog.badwords_count == 0

    def test_invite_is_deleted_and_user_warned(self, tmp_path):
        cog, _ = self._cog(tmp_path, ["idiota"])
        msg = _message("venha: discord.gg/abcd")
        run(cog.on_message(msg))
        msg.delete.assert_awaited_once()
        msg.channel.send.assert_awaited_once()
        assert "convites é proibido" in msg.channel.send.await_args.args[0]

    def test_badword_is_deleted_silently(self, tmp_path):
        cog, _ = self._cog(tmp_path, ["idiota"])
        msg = _message("seu idiota")
        run(cog.on_message(msg))
        msg.delete.assert_awaited_once()
        msg.channel.send.assert_not_called()

    def test_clean_bot_and_dm_messages_are_ignored(self, tmp_path):
        cog, _ = self._cog(tmp_path, ["idiota"])
        for msg in (_message("bom dia"), _message("idiota", bot=True), _message("discord.gg/x", guild=False)):
            run(cog.on_message(msg))
            msg.delete.assert_not_called()

    def test_delete_failure_is_swallowed(self, tmp_path):
        cog, _ = self._cog(tmp_path, ["idiota"])
        msg = _message("idiota")
        msg.delete.side_effect = discord.NotFound(MagicMock(status=404, reason="x"), "gone")
        run(cog.on_message(msg))  # não levanta

    def test_log_channel_unconfigured_returns_none(self, tmp_path):
        s = _settings(tmp_path, logs_channel_id=0)
        bot = _fake_bot(s)
        storage.ensure_data_dir(tmp_path)
        assert Moderation(bot).get_log_channel(None) is None  # type: ignore[arg-type]


# ── Salas de voz ─────────────────────────────────────────────────────────────
def _voice_state(channel):
    return SimpleNamespace(channel=channel)


class TestVoiceManagerCog:
    def _lobby(self, category=object()):
        lobby = MagicMock()
        lobby.id = 100
        lobby.category = category
        return lobby

    def test_join_lobby_creates_temp_channel_and_moves_member(self, tmp_path):
        s = _settings(tmp_path)
        cog = VoiceManager(_fake_bot(s))  # type: ignore[arg-type]
        new_channel = MagicMock(id=555)
        category = MagicMock()
        category.create_voice_channel = AsyncMock(return_value=new_channel)
        member = MagicMock(id=7, display_name="Ana")
        member.move_to = AsyncMock()

        run(cog.on_voice_state_update(member, _voice_state(None), _voice_state(self._lobby(category))))

        kwargs = category.create_voice_channel.await_args.kwargs
        assert kwargs["name"] == "Sala de 🗣️ Ana"
        assert kwargs["user_limit"] == 10
        ow = kwargs["overwrites"][member]
        assert ow.manage_channels and ow.move_members and ow.mute_members and ow.deafen_members
        member.move_to.assert_awaited_once_with(new_channel)
        assert cog.temp_channels == {555: 7}
        assert storage.load_temp_channels(tmp_path) == {555: 7}  # persistido

    def test_lobby_without_category_disconnects_member(self, tmp_path):
        cog = VoiceManager(_fake_bot(_settings(tmp_path)))  # type: ignore[arg-type]
        member = MagicMock(display_name="Ana")
        member.move_to = AsyncMock()
        run(cog.on_voice_state_update(member, _voice_state(None), _voice_state(self._lobby(None))))
        member.move_to.assert_awaited_once_with(None)
        assert cog.temp_channels == {}

    def test_empty_temp_channel_is_deleted(self, tmp_path):
        cog = VoiceManager(_fake_bot(_settings(tmp_path)))  # type: ignore[arg-type]
        cog.temp_channels[555] = 7
        old = MagicMock(id=555, members=[])
        old.delete = AsyncMock()
        run(cog.on_voice_state_update(MagicMock(), _voice_state(old), _voice_state(None)))
        old.delete.assert_awaited_once()
        assert cog.temp_channels == {}

    def test_occupied_or_untracked_channels_are_kept(self, tmp_path):
        cog = VoiceManager(_fake_bot(_settings(tmp_path)))  # type: ignore[arg-type]
        cog.temp_channels[555] = 7
        busy = MagicMock(id=555, members=[object()])
        busy.delete = AsyncMock()
        other = MagicMock(id=999, members=[])
        other.delete = AsyncMock()
        run(cog.on_voice_state_update(MagicMock(), _voice_state(busy), _voice_state(None)))
        run(cog.on_voice_state_update(MagicMock(), _voice_state(other), _voice_state(None)))
        busy.delete.assert_not_called()
        other.delete.assert_not_called()
        assert 555 in cog.temp_channels

    def test_no_lobby_configured_does_nothing(self, tmp_path):
        cog = VoiceManager(_fake_bot(_settings(tmp_path, lobby_channel_id=0)))  # type: ignore[arg-type]
        category = MagicMock()
        category.create_voice_channel = AsyncMock()
        run(cog.on_voice_state_update(MagicMock(), _voice_state(None), _voice_state(self._lobby(category))))
        category.create_voice_channel.assert_not_called()

    def test_tracked_channels_are_restored_and_cleaned_on_ready(self, tmp_path):
        storage.save_temp_channels(tmp_path, {1: 10, 2: 20})
        s = _settings(tmp_path)
        empty = MagicMock(spec=discord.VoiceChannel)
        empty.members = []
        empty.delete = AsyncMock()
        empty.name = "x"
        bot = _fake_bot(s)
        bot.get_channel = lambda cid: empty if cid == 1 else None  # 2 não existe mais
        cog = VoiceManager(bot)  # type: ignore[arg-type]
        assert cog.temp_channels == {1: 10, 2: 20}
        run(cog.on_ready())
        empty.delete.assert_awaited_once()
        assert cog.temp_channels == {}
        assert storage.load_temp_channels(tmp_path) == {}


# ── Administração ────────────────────────────────────────────────────────────
class TestAdminCog:
    def _setup(self, tmp_path):
        from src.discord_bot.admin import Admin

        bot = MagicMock()
        bot.settings = _settings(tmp_path, logs_channel_id=0)
        bot.restart_embedded = AsyncMock()
        bot.shutdown_embedded = AsyncMock()
        bot.reload_extension = AsyncMock()
        bot.load_extension = AsyncMock()
        bot.unload_extension = AsyncMock()
        ctx = MagicMock()
        ctx.send = AsyncMock(return_value=MagicMock(add_reaction=AsyncMock(), id=1))
        return Admin(bot), bot, ctx  # type: ignore[arg-type]

    def test_reload_maps_name_to_internal_module(self, tmp_path):
        cog, bot, ctx = self._setup(tmp_path)
        run(cog.reload.callback(cog, ctx, "voicemanager"))
        bot.reload_extension.assert_awaited_once_with("src.discord_bot.voice_manager")

    def test_unknown_cog_is_rejected_without_importing(self, tmp_path):
        cog, bot, ctx = self._setup(tmp_path)
        for cmd in (cog.reload, cog.load, cog.unload):
            run(cmd.callback(cog, ctx, "tickets"))
        bot.reload_extension.assert_not_called()
        bot.load_extension.assert_not_called()
        bot.unload_extension.assert_not_called()
        assert "não existe" in ctx.send.await_args.args[0]

    def test_cannot_unload_admin(self, tmp_path):
        cog, bot, ctx = self._setup(tmp_path)
        run(cog.unload.callback(cog, ctx, "admin"))
        bot.unload_extension.assert_not_called()
        assert "próprio cog de administração" in ctx.send.await_args.args[0]

    def test_restart_confirmed_restarts_embedded_bot_not_process(self, tmp_path):
        cog, bot, ctx = self._setup(tmp_path)
        bot.wait_for = AsyncMock(return_value=(SimpleNamespace(emoji="✅"), ctx.author))
        run(cog.restart.callback(cog, ctx))
        bot.restart_embedded.assert_awaited_once()  # nada de sys.exit(24)

    def test_restart_cancelled(self, tmp_path):
        cog, bot, ctx = self._setup(tmp_path)
        bot.wait_for = AsyncMock(return_value=(SimpleNamespace(emoji="❌"), ctx.author))
        run(cog.restart.callback(cog, ctx))
        bot.restart_embedded.assert_not_called()

    def test_restart_timeout(self, tmp_path):
        cog, bot, ctx = self._setup(tmp_path)
        bot.wait_for = AsyncMock(side_effect=asyncio.TimeoutError())
        run(cog.restart.callback(cog, ctx))
        bot.restart_embedded.assert_not_called()
        assert "Tempo esgotado" in ctx.send.await_args.args[0]

    def test_shutdown_confirmed(self, tmp_path):
        cog, bot, ctx = self._setup(tmp_path)
        bot.wait_for = AsyncMock(return_value=(SimpleNamespace(emoji="✅"), ctx.author))
        run(cog.shutdown.callback(cog, ctx))
        bot.shutdown_embedded.assert_awaited_once()
