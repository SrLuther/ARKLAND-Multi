"""Transporte do Chat Arkland usando exclusivamente o Gateway central do Lumo."""
from __future__ import annotations

import asyncio
import logging
import re
import uuid

log = logging.getLogger("arkshop.chat_arkland.discord")


def transport_enabled():
    try:
        from chat_arkland_routes import get_chat_service
        service = get_chat_service()
        if service is None:
            return False
        config = service.load_config()["config"]
        return not config["DisableChat"] and config["Discord"]["Enabled"] and any(item.get("Enabled") for item in config["Maps"].values())
    except Exception:
        return False


class ChatDiscordTransport:
    def __init__(self, load_settings):
        self.load_settings = load_settings
        self.owner = str(uuid.uuid4())

    async def incoming(self, client, message):
        """Retorna contexto de jogador somente para um relay próprio autenticado."""
        from chat_arkland_routes import get_chat_service
        service = get_chat_service()
        if service is None:
            return None
        settings = self.load_settings()
        guild, channel = getattr(message, "guild", None), getattr(message, "channel", None)
        if (guild is None or channel is None or str(guild.id) != str(settings.get("lumo_guild_id") or "")
                or str(channel.id) != str(settings.get("lumo_game_chat_channel_id") or "")):
            return None
        author = getattr(message, "author", None)
        if author is None or getattr(message, "webhook_id", None):
            return None
        own = str(author.id) == str(getattr(getattr(client, "user", None), "id", ""))
        if getattr(author, "bot", False) and not own:
            return None  # Apenas o usuário real do Lumo é autorizado, nunca o apelido.
        if not await asyncio.to_thread(transport_enabled):
            return None
        nonce = str(getattr(message, "nonce", "") or "")
        if own and re.fullmatch(r"ca:[0-9]+", nonce):
            return await asyncio.to_thread(service.relay_context, int(nonce[3:]))
        body = str(getattr(message, "content", "") or "").strip()
        if not body:
            return None
        try:
            await asyncio.to_thread(service.ingest_discord, str(message.id), str(author.id),
                str(getattr(author, "display_name", "Sobrevivente")), body, lumo=own)
        except Exception as failure:
            log.warning("Mensagem Discord não encaminhada (%s)", type(failure).__name__)
        return None

    async def run(self, client):
        import discord
        from chat_arkland_routes import get_chat_service
        while not client.is_closed():
            delay = 1.0
            try:
                service = get_chat_service()
                settings = self.load_settings()
                channel_id = str(settings.get("lumo_game_chat_channel_id") or "")
                guild_id = str(settings.get("lumo_guild_id") or "")
                if service and channel_id.isdigit() and guild_id.isdigit():
                    channel = client.get_channel(int(channel_id))
                    if channel and str(getattr(getattr(channel, "guild", None), "id", "")) == guild_id:
                        config = await asyncio.to_thread(service.load_config)
                        delay = config["config"]["PollRate"]
                        pending = await asyncio.to_thread(service.claim_discord, self.owner)
                        if pending:
                            message_id = None
                            try:
                                payload = pending["payload"]
                                sent = await channel.send(discord.utils.escape_markdown(payload.get("discord_plain") or payload["plain"]),
                                    allowed_mentions=discord.AllowedMentions.none(), nonce="ca:" + str(pending["seq"]))
                                message_id = str(sent.id)
                            except Exception as failure:
                                # Resultado de envio desconhecido não é reenviado às cegas.
                                log.warning("Envio Discord não confirmado (%s)", type(failure).__name__)
                            await asyncio.to_thread(service.confirm_discord, pending["seq"], self.owner, message_id)
            except asyncio.CancelledError:
                raise
            except Exception as failure:
                log.warning("Transporte Discord indisponível (%s)", type(failure).__name__)
            await asyncio.sleep(max(0.1, min(30, delay)))
