"""Transporte do Chat Arkland usando exclusivamente o Gateway central do Lumo."""
from __future__ import annotations

import asyncio
from collections import deque
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


def discord_chat_line(value):
    """Uma linha visível e segura, limitada também em unidades UTF-16."""
    text = " ".join(str(value).split()).replace("`", "ˋ")
    output, units = [], 0
    for char in text:
        size = 2 if ord(char) > 0xFFFF else 1
        if units + size > 1979:
            return "".join(output) + "…"
        output.append(char)
        units += size
    return text


def chat_code_block(lines):
    return "```text\n" + "\n".join(lines) + "\n```"


class ChatDiscordTransport:
    def __init__(self, load_settings, relay_handler=None):
        self.load_settings = load_settings
        self.owner = str(uuid.uuid4())
        self.relay_handler = relay_handler
        self._group_message = None
        self._group_lines = []
        self._relay_ids = deque(maxlen=128)
        self._relay_id_set = set()

    def is_relay_message(self, message):
        return bool(re.fullmatch(r"ca:[0-9]+", str(getattr(message, "nonce", "") or ""))
                    or str(getattr(message, "id", "")) in self._relay_id_set)

    def _remember_relay(self, message_id):
        value = str(message_id)
        if value not in self._relay_id_set:
            if len(self._relay_ids) == self._relay_ids.maxlen:
                self._relay_id_set.discard(self._relay_ids[0])
            self._relay_ids.append(value)
            self._relay_id_set.add(value)

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
        if own and self.is_relay_message(message):
            # O publicador entrega o evento original ao Lumo; seu eco não é
            # outra conversa. Edits de blocos não dependem do nonce inicial.
            return None
        self._group_message, self._group_lines = None, []
        body = str(getattr(message, "content", "") or "").strip()
        if not body:
            return None
        try:
            await asyncio.to_thread(service.ingest_discord, str(message.id), str(author.id),
                str(getattr(author, "display_name", "Sobrevivente")), body, lumo=own)
        except Exception as failure:
            log.warning("Mensagem Discord não encaminhada (%s)", type(failure).__name__)
        return None

    async def _publish(self, channel, pending):
        import discord
        line = discord_chat_line(pending["payload"].get("discord_plain") or pending["payload"]["plain"])
        group = self._group_message
        candidate = self._group_lines + [line]
        last_id = getattr(channel, "last_message_id", None)
        can_append = (group is not None and str(getattr(group.channel, "id", "")) == str(channel.id)
            and (last_id is None or str(last_id) == str(group.id)) and len(candidate) <= 40
            and len(chat_code_block(candidate).encode("utf-16-le")) // 2 <= 2000)
        try:
            if can_append:
                try:
                    sent = await group.edit(content=chat_code_block(candidate), allowed_mentions=discord.AllowedMentions.none())
                except discord.NotFound:
                    # 404 confirma que o bloco foi removido; criar outro apenas
                    # com a linha atual não republica o histórico anterior.
                    can_append = False
            if not can_append:
                candidate = [line]
                sent = await channel.send(chat_code_block(candidate), allowed_mentions=discord.AllowedMentions.none(),
                                          nonce="ca:" + str(pending["seq"]))
            self._group_message, self._group_lines = sent, candidate
            self._remember_relay(sent.id)
            return str(sent.id)
        except BaseException:
            self._group_message, self._group_lines = None, []
            raise

    async def _relay_callbacks(self, client, queue):
        while True:
            channel, context = await queue.get()
            try:
                await self.relay_handler(client, channel, context)
            except asyncio.CancelledError:
                raise
            except Exception as failure:
                log.warning("Reação do Lumo ao relay indisponível (%s)", type(failure).__name__)
            finally:
                queue.task_done()

    async def run(self, client):
        from chat_arkland_routes import get_chat_service
        self._group_message, self._group_lines = None, []
        callbacks = asyncio.Queue(maxsize=64)
        callback_task = asyncio.create_task(self._relay_callbacks(client, callbacks)) if self.relay_handler else None
        try:
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
                                    message_id = await self._publish(channel, pending)
                                except Exception as failure:
                                    # Resultado de envio desconhecido não é reenviado às cegas.
                                    log.warning("Envio Discord não confirmado (%s)", type(failure).__name__)
                                await asyncio.to_thread(service.confirm_discord, pending["seq"], self.owner, message_id)
                                if message_id and self.relay_handler:
                                    context = {"event_id": pending["event_id"], "steam_id": pending["sender_steam"], "body": pending["payload"]["body"]}
                                    try:
                                        callbacks.put_nowait((channel, context))
                                    except asyncio.QueueFull:
                                        log.warning("Fila de reações do Lumo cheia; relay publicado sem reação automática.")
                except asyncio.CancelledError:
                    raise
                except Exception as failure:
                    log.warning("Transporte Discord indisponível (%s)", type(failure).__name__)
                await asyncio.sleep(max(0.1, min(30, delay)))
        finally:
            if callback_task:
                callback_task.cancel()
                await asyncio.gather(callback_task, return_exceptions=True)
