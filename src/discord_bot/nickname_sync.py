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
    """Build ``[Tribe] | Character`` and fit Discord's nickname limit."""
    tribe = " ".join(str(tribe_name or "").split())
    character = " ".join(str(character_name or "").split())
    missing_tribe = not tribe
    if not tribe:
        tribe = "Tribo"
    if not character or limit < 7 or (missing_tribe and limit < len(tribe) + 6):
        return ""
    tribe_limit = max(1, min(len(tribe), limit - 6))
    tribe = tribe[:tribe_limit].rstrip()
    prefix = f"[{tribe}] | "
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

    @tasks.loop(minutes=1)
    async def _sync_nicknames(self) -> None:
        await self._sync_once()

    async def _sync_once(self) -> None:
        """Run a single cycle separately so the Discord update path is testable."""
        settings: Any = self.bot.settings
        if not str(getattr(settings, "arkshop_web_url", "") or "").strip() or not str(
            getattr(settings, "arkshop_api_key", "") or ""
        ).strip():
            reason = "URL ou chave da API da Web Store não configurada"
            if reason != self._last_error:
                log.warning("Nickname sync não executado: %s", reason)
                self._last_error = reason
            return
        guild_id = int(getattr(settings, "guild_id", 0) or 0)
        guild = self.bot.get_guild(guild_id) if guild_id else None
        if guild is None:
            reason = "guild_id ausente" if not guild_id else f"servidor Discord {guild_id} não está no cache do bot"
            if reason != self._last_error:
                log.warning("Nickname sync não executado: %s", reason)
                self._last_error = reason
            return
        bot_member = getattr(guild, "me", None)
        if bot_member is not None and not bot_member.guild_permissions.manage_nicknames:
            reason = "bot sem a permissão Gerenciar apelidos nesta guilda"
            if reason != self._last_error:
                log.warning("Nickname sync bloqueado: %s", reason)
                self._last_error = reason
            return
        try:
            snapshot = await asyncio.to_thread(self._get_snapshot)
            if not snapshot.get("ok"):
                reason = "API de identidades vinculadas retornou resposta inválida"
                if reason != self._last_error:
                    log.warning("Nickname sync não executado: %s", reason)
                    self._last_error = reason
                return
            users = snapshot.get("users") or []
            if not isinstance(users, list):
                raise RuntimeError("WebStore nickname snapshot has invalid users list")
            diagnostics = snapshot.get("diagnostics") or {}
            active_error = str(diagnostics.get("active_error") or "").strip()
            if active_error:
                reason = f"sessões ativas indisponíveis; usando último registro: {active_error}"
                if reason != self._last_error:
                    log.error("Nickname sync em fallback: %s", reason)
                self._last_error = reason
            changed = unchanged = skipped = forbidden = failed = 0
            for item in users:
                if not isinstance(item, dict):
                    skipped += 1
                    continue
                raw_id = str(item.get("discord_user_id") or "").strip()
                if not raw_id.isdigit():
                    skipped += 1
                    continue
                nickname = format_game_nickname(item.get("tribe_name", ""), item.get("character_name", ""))
                if not nickname:
                    skipped += 1
                    continue
                if item.get("identity_source") == "last_known":
                    log.info(
                        "Nickname sync usando última identidade conhecida; última atualização: %s",
                        str(item.get("identity_last_seen_at") or "data não informada"),
                    )
                member = guild.get_member(int(raw_id))
                if member is None:
                    try:
                        member = await guild.fetch_member(int(raw_id))
                    except discord.NotFound:
                        skipped += 1
                        log.info("Nickname sync ignorou membro Discord ausente (id=%s)", raw_id)
                        continue
                    except discord.Forbidden:
                        forbidden += 1
                        log.warning("Nickname sync sem acesso para consultar membro Discord (id=%s)", raw_id)
                        continue
                if member.bot:
                    skipped += 1
                    continue
                if member.nick == nickname:
                    unchanged += 1
                    continue
                if bot_member is not None and member.top_role >= bot_member.top_role:
                    forbidden += 1
                    log.warning(
                        "Nickname sync bloqueado: cargo do bot está abaixo do cargo do membro no Discord."
                    )
                    continue
                try:
                    await member.edit(nick=nickname, reason="Sincronização da identidade ARKLAND vinculada")
                    changed += 1
                except discord.Forbidden:
                    forbidden += 1
                    log.warning("Nickname sync sem permissão para editar membro %s", raw_id)
                except discord.HTTPException as exc:
                    failed += 1
                    log.warning("Nickname sync falhou para membro %s (HTTP %s)", raw_id, exc.status)
            log.info(
                "Nickname sync concluído: %s identidade(s), %s atualizada(s), "
                "%s já correta(s), %s ignorada(s), %s sem permissão, %s falha(s).",
                len(users), changed, unchanged, skipped, forbidden, failed,
            )
            if not active_error:
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
