"""Report eligible Discord text activity without storing message contents."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib import request as urllib_request

import discord
from discord.ext import commands, tasks

log = logging.getLogger("arkland.obobonic")


class ActivityRewards(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.channel_ids: set[int] = set()
        self.guild_id = 0

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        settings: Any = self.bot.settings
        base_url = str(getattr(settings, "arkshop_web_url", "") or "").rstrip("/")
        api_key = str(getattr(settings, "arkshop_api_key", "") or "").strip()
        if not base_url or not api_key:
            return {}
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8") if payload is not None else None
        req = urllib_request.Request(
            base_url + path,
            data=data,
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            method="POST" if data is not None else "GET",
        )
        try:
            with urllib_request.urlopen(req, timeout=8) as response:
                body = json.loads(response.read().decode("utf-8"))
                return body if isinstance(body, dict) else {}
        except Exception as exc:
            log.warning("Integração de atividade Discord falhou: %s", exc)
            return {}

    @tasks.loop(seconds=60)
    async def _refresh_config(self) -> None:
        settings: Any = self.bot.settings
        if not settings.arkshop_web_url or not settings.arkshop_api_key:
            self.channel_ids.clear()
            return
        cfg = await asyncio.to_thread(self._request, "/api/internal/discord-engagement/config")
        if not cfg.get("ok"):
            return
        self.channel_ids = {
            int(value) for value in cfg.get("text_channel_ids", []) if str(value).isdigit()
        }
        raw_guild_id = str(cfg.get("guild_id") or "")
        self.guild_id = int(raw_guild_id) if raw_guild_id.isdigit() else 0

    @_refresh_config.before_loop
    async def _before_refresh(self) -> None:
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if not self._refresh_config.is_running():
            self._refresh_config.start()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return
        if message.channel.id not in self.channel_ids:
            return
        if self.guild_id and message.guild.id != self.guild_id:
            return
        settings: Any = self.bot.settings
        content = (message.content or "").strip()
        prefix = str(getattr(settings, "command_prefix", "!") or "!")
        payload = {
            "guild_id": str(message.guild.id),
            "discord_user_id": str(message.author.id),
            "channel_id": str(message.channel.id),
            "message_id": str(message.id),
            "content_length": len(content),
            "attachment_count": len(message.attachments),
            "is_command": content.startswith((prefix, "/")),
        }
        await asyncio.to_thread(
            self._request,
            "/api/internal/discord-engagement/text-event",
            payload,
        )

    def cog_unload(self) -> None:
        if self._refresh_config.is_running():
            self._refresh_config.cancel()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ActivityRewards(bot))
