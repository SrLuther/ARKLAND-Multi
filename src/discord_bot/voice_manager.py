"""Cog de salas de voz temporárias (porta de cogs/voicemanager.py).

Comportamento preservado: ao entrar no canal *lobby* o membro ganha uma sala própria
("Sala de 🗣️ <nome>", limite 10, com permissões de gerenciar/mover/mutar/ensurdecer),
e a sala é excluída quando fica vazia.

Extra do bot embutido: as salas rastreadas são salvas em disco para serem limpas
caso o bot reinicie com o app (o original perdia o rastreio no restart).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, Union

import discord
from discord.ext import commands

from . import storage
from .logic import (
    VOICE_USER_LIMIT,
    is_lobby_join,
    should_delete_temp_channel,
    temp_channel_name,
)

log = logging.getLogger("arkland.obobonic")


class VoiceManager(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        settings: Any = getattr(bot, "settings")
        self.lobby_id: int = settings.lobby_channel_id
        self._data_dir = settings.data_dir
        self.temp_channels: Dict[int, int] = storage.load_temp_channels(self._data_dir)

        if self.lobby_id == 0:
            log.warning("⚠️ [VoiceManager] LOBBY_CHANNEL_ID não configurado. O Cog não funcionará.")

    def _persist(self) -> None:
        storage.save_temp_channels(self._data_dir, self.temp_channels)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Limpa salas temporárias que ficaram vazias/inexistentes durante o reinício."""
        changed = False
        for channel_id in list(self.temp_channels):
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                del self.temp_channels[channel_id]
                changed = True
            elif isinstance(channel, discord.VoiceChannel) and not channel.members:
                try:
                    await channel.delete(reason="Canal temporário vazio.")
                    log.info("🗑️ [VoiceManager] Canal temporário '%s' deletado (limpeza no boot).", channel.name)
                except Exception as e:
                    log.error("❌ [VoiceManager] Erro ao deletar canal: %s", e)
                    continue
                del self.temp_channels[channel_id]
                changed = True
        if changed:
            self._persist()

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        # CRIAÇÃO
        if is_lobby_join(after.channel.id if after.channel else None, self.lobby_id):
            assert after.channel is not None
            category = after.channel.category
            if not category:
                log.error("❌ [VoiceManager] O canal Lobby (ID: %s) precisa estar em uma categoria.", self.lobby_id)
                try:
                    await member.move_to(None)
                except Exception:
                    pass
                return

            channel_name = temp_channel_name(member.display_name)

            overwrites: Mapping[Union[discord.Role, discord.Member, discord.Object], discord.PermissionOverwrite] = {
                member: discord.PermissionOverwrite(
                    manage_channels=True,
                    move_members=True,
                    mute_members=True,
                    deafen_members=True,
                )
            }
            try:
                new_channel = await category.create_voice_channel(
                    name=channel_name,
                    user_limit=VOICE_USER_LIMIT,
                    overwrites=overwrites,
                    reason=f"Canal temporário criado por {member.display_name}",
                )
            except discord.HTTPException as e:
                log.error("❌ [VoiceManager] Erro ao criar canal temporário: %s", e)
                return

            try:
                await member.move_to(new_channel)
                self.temp_channels[new_channel.id] = member.id
                self._persist()
                log.info("✅ [VoiceManager] Canal temporário '%s' criado e membro movido.", channel_name)
            except Exception as e:
                log.error("❌ [VoiceManager] Erro ao mover membro ou criar canal: %s", e)

        # EXCLUSÃO
        if before.channel and before.channel.id != self.lobby_id:
            old_channel = before.channel
            if should_delete_temp_channel(
                old_channel.id, self.lobby_id, self.temp_channels, len(old_channel.members),
            ):
                try:
                    await old_channel.delete(reason="Canal temporário vazio.")
                    del self.temp_channels[old_channel.id]
                    self._persist()
                    log.info("🗑️ [VoiceManager] Canal temporário '%s' deletado.", old_channel.name)
                except Exception as e:
                    log.error("❌ [VoiceManager] Erro ao deletar canal: %s", e)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(VoiceManager(bot))
