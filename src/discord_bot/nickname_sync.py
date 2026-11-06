"""Synchronize linked Discord members' nicknames with their latest ARK identity."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib import request as urllib_request

import discord
from discord.ext import commands, tasks

log = logging.getLogger("arkland.obobonic")


def format_game_nickname(tribe_name: str, character_name: str, limit: int = 32) -> str:
    """Build ``[Tribe] Character`` and fit Discord's nickname limit."""
    tribe = " ".join(str(tribe_name or "").split())
    character = " ".join(str(character_name or "").split())
    if not tribe or not character or limit < 5:
        return ""
    tribe_limit = max(1, min(len(tribe), limit - 5))
    tribe = tribe[:tribe_limit].rstrip()
    prefix = f"[{tribe}] "
    character = character[:max(1, limit - len(prefix))].rstrip()
    return (prefix + character)[:limit].rstrip()


class NicknameSync(commands.Cog):
    """Periodically apply the latest linked in-game character and tribe names."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._last_error: str | None = None

    def _get_snapshot(self) -> dict[str, Any]:
        settings: Any = self.bot.settings
        base_url = str(getattr(settings, "arkshop_web_url", "") or "").rstrip("/")
        api_key = str(getattr(settings, "arkshop_api_key", "") or "").strip()
        if not base_url or not api_key:
            return {}
        req = urllib_request.Request(
            base_url + "/api/internal/discord/nickname-sync",
            headers={"X-API-Key": api_key},
            method="GET",
        )
        try:
            with urllib_request.urlopen(req, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload if isinstance(payload, dict) else {}
        except Exception as exc:
            raise RuntimeError(f"WebStore nickname snapshot unavailable ({type(exc).__name__})") from exc

    @tasks.loop(minutes=5)
    async def _sync_nicknames(self) -> None:
        settings: Any = self.bot.settings
        guild_id = int(getattr(settings, "guild_id", 0) or 0)
        guild = self.bot.get_guild(guild_id) if guild_id else None
        if guild is None:
            return
        try:
            snapshot = await asyncio.to_thread(self._get_snapshot)
            if not snapshot.get("ok"):
                return
            changed = 0
            for item in snapshot.get("users") or []:
                if not isinstance(item, dict):
                    continue
                raw_id = str(item.get("discord_user_id") or "").strip()
                if not raw_id.isdigit():
                    continue
                nickname = format_game_nickname(item.get("tribe_name", ""), item.get("character_name", ""))
                if not nickname:
                    continue
                member = guild.get_member(int(raw_id))
                if member is None:
                    try:
                        member = await guild.fetch_member(int(raw_id))
                    except (discord.NotFound, discord.Forbidden):
                        continue
                if member.bot or member.nick == nickname:
                    continue
                try:
                    await member.edit(nick=nickname, reason="Sincronização da identidade ARKLAND vinculada")
                    changed += 1
                except discord.Forbidden:
                    log.warning("Nickname sync sem permissão para editar membro %s", raw_id)
                except discord.HTTPException as exc:
                    log.warning("Nickname sync falhou para membro %s (HTTP %s)", raw_id, exc.status)
            if changed:
                log.info("Nickname sync atualizou %s membro(s) Discord.", changed)
            self._last_error = None
        except Exception as exc:
            message = str(exc)
            if message != self._last_error:
                log.warning("Nickname sync indisponível: %s", message)
                self._last_error = message

    @_sync_nicknames.before_loop
    async def _before_sync_nicknames(self) -> None:
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if not self._sync_nicknames.is_running():
            self._sync_nicknames.start()

    def cog_unload(self) -> None:
        if self._sync_nicknames.is_running():
            self._sync_nicknames.cancel()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NicknameSync(bot))
