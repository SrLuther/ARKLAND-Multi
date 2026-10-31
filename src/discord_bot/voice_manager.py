"""Cog de salas de voz temporárias (porta de cogs/voicemanager.py).

Comportamento preservado: ao entrar no canal *lobby* o membro ganha uma sala própria
("Sala de 🗣️ <nome>", limite 10, com permissões de gerenciar/mover/mutar/ensurdecer),
e a sala é excluída quando fica vazia.

Extra do bot embutido: as salas rastreadas são salvas em disco para serem limpas
caso o bot reinicie com o app (o original perdia o rastreio no restart).
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Mapping, Union
from urllib import request as urllib_request

import discord
from discord.ext import commands, tasks

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
        self._engagement_guild_id = 0

        if self.lobby_id == 0:
            log.warning("⚠️ [VoiceManager] LOBBY_CHANNEL_ID não configurado. O Cog não funcionará.")

    def _persist(self) -> None:
        storage.save_temp_channels(self._data_dir, self.temp_channels)

    def _post_webstore(self, path: str, payload: dict[str, Any]) -> None:
        settings: Any = self.bot.settings
        base_url = str(getattr(settings, "arkshop_web_url", "") or "").rstrip("/")
        api_key = str(getattr(settings, "arkshop_api_key", "") or "").strip()
        if not base_url or not api_key:
            return
        req = urllib_request.Request(
            base_url + path,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-API-Key": api_key},
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=8) as response:
                if response.status >= 300:
                    log.warning("Integração de atividade Discord respondeu HTTP %s", response.status)
        except Exception as exc:
            log.warning("Envio de atividade Discord para Web Store falhou: %s", exc)

    def _get_webstore(self, path: str) -> dict[str, Any]:
        settings: Any = self.bot.settings
        base_url = str(getattr(settings, "arkshop_web_url", "") or "").rstrip("/")
        api_key = str(getattr(settings, "arkshop_api_key", "") or "").strip()
        if not base_url or not api_key:
            return {}
        req = urllib_request.Request(base_url + path, headers={"X-API-Key": api_key}, method="GET")
        try:
            with urllib_request.urlopen(req, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload if isinstance(payload, dict) else {}
        except Exception as exc:
            log.warning("Leitura da configuração de atividade falhou: %s", exc)
            return {}

    @tasks.loop(seconds=60)
    async def _publish_voice_presence(self) -> None:
        settings: Any = self.bot.settings
        if not settings.arkshop_web_url or not settings.arkshop_api_key:
            return
        activity_cfg = await asyncio.to_thread(
            self._get_webstore, "/api/internal/discord-engagement/config"
        )
        if activity_cfg.get("ok"):
            raw_guild_id = str(activity_cfg.get("guild_id") or "")
            self._engagement_guild_id = int(raw_guild_id) if raw_guild_id.isdigit() else 0
        guilds = [self.bot.get_guild(settings.guild_id)] if settings.guild_id else list(self.bot.guilds)
        for guild in filter(None, guilds):
            if self._engagement_guild_id and guild.id != self._engagement_guild_id:
                continue
            members: list[dict[str, Any]] = []
            for raw_channel_id in list(self.temp_channels):
                channel = guild.get_channel(int(raw_channel_id))
                if not isinstance(channel, discord.VoiceChannel) or channel == guild.afk_channel:
                    continue
                humans = [member for member in channel.members if not member.bot]
                room_eligible = len(humans) >= 2
                for member in humans:
                    members.append({
                        "discord_user_id": str(member.id),
                        "username": member.display_name,
                        "channel_id": str(channel.id),
                        "channel_name": channel.name,
                        "eligible": room_eligible,
                    })
            await asyncio.to_thread(
                self._post_webstore,
                "/api/internal/discord-engagement/voice-snapshot",
                {"guild_id": str(guild.id), "members": members},
            )

    @_publish_voice_presence.before_loop
    async def _before_presence_publish(self) -> None:
        await self.bot.wait_until_ready()

    def cog_unload(self) -> None:
        if self._publish_voice_presence.is_running():
            self._publish_voice_presence.cancel()

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
        if not self._publish_voice_presence.is_running():
            self._publish_voice_presence.start()

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
