"""Transporte do Chat Arkland usando exclusivamente o Gateway central do Lumo."""
from __future__ import annotations

import asyncio
from collections import deque
import logging
import re
import uuid
import hashlib

log = logging.getLogger("arkshop.chat_arkland.discord")

_MIRROR_ERRORS = {"missing_view_or_send", "missing_manage_messages", "missing_history", "missing_attach_files",
    "source_author_mismatch", "source_attachment_changed", "source_sticker_changed",
    "attachment_exceeds_bot_limit", "interactive_original_preserved", "invalid_copy_receipt", "bot_identity_changed", "source_scope_mismatch"}


def mirror_failure(failure):
    return str(failure) if str(failure) in _MIRROR_ERRORS else type(failure).__name__


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


def source_text(message):
    """Captura texto visível; anexos são copiados como arquivos, não como URL efêmera."""
    pieces = [str(getattr(message, "content", "") or "")]
    for embed in getattr(message, "embeds", ()):
        data = embed.to_dict()
        for key in ("title", "description", "url"):
            if data.get(key):
                pieces.append(str(data[key]))
        for field in data.get("fields", ()):
            pieces.extend(str(field.get(key) or "") for key in ("name", "value"))
        for key in ("author", "footer"):
            detail = data.get(key) or {}
            pieces.extend(str(detail.get(part) or "") for part in ("name", "text", "url"))
        for key in ("image", "thumbnail"):
            if (data.get(key) or {}).get("url"):
                pieces.append(str(data[key]["url"]))
    for attachment in getattr(message, "attachments", ()):
        pieces.append("[arquivo: " + str(attachment.filename) + "]")
    for sticker in getattr(message, "stickers", ()):
        pieces.append("[figurinha: " + str(sticker.name) + "]")
    for component in getattr(message, "components", ()):
        for child in getattr(component, "children", ()):
            if getattr(child, "url", None):
                pieces.append(str(getattr(child, "label", "Link")) + ": " + str(child.url))
    return " ".join(part for part in pieces if part)


def source_parts(value, author=""):
    """Divide sem truncar conteúdo, respeitando o limite em UTF-16 do Discord."""
    remaining = " ".join(str(value).split()).replace("`", "ˋ")
    parts = []
    while remaining:
        prefix = ("[continuação: " + discord_chat_line(author)[:80] + "] ") if parts else ""
        capacity, units, end = 1979 - len(prefix.encode("utf-16-le")) // 2, 0, 0
        for char in remaining:
            size = 2 if ord(char) > 0xFFFF else 1
            if units + size > capacity:
                break
            units += size
            end += 1
        parts.append(prefix + remaining[:end])
        remaining = remaining[end:]
    return parts


class ChatDiscordTransport:
    def __init__(self, load_settings, relay_handler=None):
        self.load_settings = load_settings
        self.owner = str(uuid.uuid4())
        self.relay_handler = relay_handler
        self._group_message = None
        self._group_lines = []
        self._relay_ids = deque(maxlen=128)
        self._relay_id_set = set()
        self._source_ids = deque(maxlen=2048)
        self._source_id_set = set()
        self._publish_lock = asyncio.Lock()
        self._mirror_status = {"enabled": False, "ready": False, "permissions": {}, "last_error": ""}
        self._capture_errors = deque(maxlen=5)

    def mirror_snapshot(self):
        status = self._mirror_status
        return {**status, "permissions": dict(status["permissions"]), "capture_errors": list(self._capture_errors)}

    def normalizes(self, client, message):
        settings = self.load_settings()
        author = getattr(message, "author", None)
        own_id = str(getattr(getattr(client, "user", None), "id", ""))
        return bool(author and getattr(message, "guild", None) and getattr(message, "channel", None)
            and settings.get("lumo_guild_id") and settings.get("lumo_game_chat_channel_id")
            and not getattr(message, "webhook_id", None)
            and (not getattr(author, "bot", False) or str(author.id) == own_id)
            and str(getattr(getattr(message, "guild", None), "id", "")) == str(settings.get("lumo_guild_id") or "")
            and str(getattr(getattr(message, "channel", None), "id", "")) == str(settings.get("lumo_game_chat_channel_id") or ""))

    def is_relay_message(self, message):
        return bool(re.fullmatch(r"ca:[0-9a-f]{1,20}", str(getattr(message, "nonce", "") or ""))
                    or str(getattr(message, "id", "")) in self._relay_id_set)

    def _remember_source(self, message_id):
        value = str(message_id)
        if value not in self._source_id_set:
            if len(self._source_ids) == self._source_ids.maxlen:
                self._source_id_set.discard(self._source_ids[0])
            self._source_ids.append(value)
            self._source_id_set.add(value)

    def _forget_source(self, message_id):
        value = str(message_id)
        self._source_id_set.discard(value)
        try:
            self._source_ids.remove(value)
        except ValueError:
            pass

    def _remember_relay(self, message_id):
        value = str(message_id)
        if value not in self._relay_id_set:
            if len(self._relay_ids) == self._relay_ids.maxlen:
                self._relay_id_set.discard(self._relay_ids[0])
            self._relay_ids.append(value)
            self._relay_id_set.add(value)

    async def incoming(self, client, message):
        """Captura a primeira versão; ecos dos blocos próprios não são mensagens novas."""
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
        if own and self.is_relay_message(message):
            # O publicador entrega o evento original ao Lumo; seu eco não é
            # outra conversa. Edits de blocos não dependem do nonce inicial.
            return None
        body = source_text(message).strip()
        if not body:
            return None
        self._remember_source(message.id)
        if not await asyncio.to_thread(transport_enabled):
            self._forget_source(message.id)
            return None
        captured = False
        try:
            mirrors = getattr(service, "mirrors", None)
            if mirrors is None:
                self._forget_source(message.id)
                self._group_message, self._group_lines = None, []
                await asyncio.to_thread(service.ingest_discord, str(message.id), str(author.id),
                    str(getattr(author, "display_name", "Sobrevivente")), body, lumo=own)
                return None
            when = getattr(message, "created_at", None)
            row = await asyncio.to_thread(mirrors.capture, str(message.id), str(guild.id), str(channel.id),
                str(author.id), str(getattr(author, "display_name", "Sobrevivente")), body, lumo=own,
                attachments=[{"id": str(a.id), "filename": str(a.filename), "size": int(a.size)} for a in getattr(message, "attachments", ())],
                stickers=[{"id": str(s.id), "name": str(s.name)} for s in getattr(message, "stickers", ())],
                occurred_at=when.isoformat() if when else None)
            if row:
                captured = True
                await asyncio.to_thread(mirrors.forward_live, row)
            else:
                self._forget_source(message.id)
        except Exception as failure:
            if not captured:
                self._forget_source(message.id)
                self._group_message, self._group_lines = None, []
                self._capture_errors.append(mirror_failure(failure))
            log.warning("Mensagem Discord não encaminhada (%s)", type(failure).__name__)
        return None

    async def _publish(self, channel, pending):
        async with self._publish_lock:
            return await self._publish_line(channel,
                discord_chat_line(pending["payload"].get("discord_plain") or pending["payload"]["plain"]),
                "ca:" + str(pending["seq"]))

    async def _publish_line(self, channel, line, nonce, *, files=None, stickers=None):
        import discord
        group = self._group_message
        candidate = self._group_lines + [line]
        last_id = getattr(channel, "last_message_id", None)
        can_append = (group is not None and str(getattr(group.channel, "id", "")) == str(channel.id)
            and not files and not stickers
            and (last_id is None or str(last_id) == str(group.id) or str(last_id) in self._source_id_set) and len(candidate) <= 40
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
                extras = {}
                if files:
                    extras["files"] = files
                if stickers:
                    extras["stickers"] = stickers
                sent = await channel.send(chat_code_block(candidate), allowed_mentions=discord.AllowedMentions.none(),
                                          nonce=nonce, **extras)
            self._group_message, self._group_lines = sent, candidate
            self._remember_relay(sent.id)
            return str(sent.id)
        except BaseException:
            self._group_message, self._group_lines = None, []
            raise

    @staticmethod
    def _source_permissions(channel, own):
        member = getattr(channel.guild, "me", None)
        permissions = channel.permissions_for(member) if member else None
        if permissions is None or not permissions.view_channel or not permissions.send_messages:
            raise PermissionError("missing_view_or_send")
        if not permissions.read_message_history:
            raise PermissionError("missing_history")
        if not own and not permissions.manage_messages:
            raise PermissionError("missing_manage_messages")
        return permissions

    async def _copy_source(self, client, channel, store, row):
        import discord
        files, copies, attempted = [], [], False
        try:
            if row["guild_id"] != str(channel.guild.id) or row["channel_id"] != str(channel.id):
                raise ValueError("source_scope_mismatch")
            if row["lumo"] and row["author_id"] != str(client.user.id):
                raise ValueError("bot_identity_changed")
            own = row["lumo"] and row["author_id"] == str(client.user.id)
            permissions = self._source_permissions(channel, own)
            snapshot = row["snapshot"]
            original = None
            try:
                original = await channel.fetch_message(int(row["source_id"]))
            except discord.NotFound:
                await asyncio.to_thread(store.source_gone, row["source_id"], self.owner)
                return  # Não recriar mensagem removida antes da consolidação.
            if original and (str(original.author.id) != row["author_id"] or getattr(original, "webhook_id", None)):
                raise ValueError("source_author_mismatch")
            if original and (getattr(original, "poll", None) or any(getattr(child, "custom_id", None)
                    for component in getattr(original, "components", ()) for child in getattr(component, "children", ()))):
                raise ValueError("interactive_original_preserved")
            actual = {str(a.id): a for a in getattr(original, "attachments", ())} if original else {}
            if snapshot.get("attachments") and not permissions.attach_files:
                raise PermissionError("missing_attach_files")
            for metadata in snapshot.get("attachments", ()):
                attachment = actual.get(metadata["id"])
                if attachment is None or attachment.size != metadata["size"]:
                    raise ValueError("source_attachment_changed")
                if attachment.size > channel.guild.filesize_limit:
                    raise ValueError("attachment_exceeds_bot_limit")
                files.append(await asyncio.wait_for(attachment.to_file(use_cached=True, spoiler=attachment.is_spoiler()), timeout=30))
            actual_stickers = {str(s.id): s for s in getattr(original, "stickers", ())} if original else {}
            stickers = [actual_stickers.get(s["id"]) for s in snapshot.get("stickers", ())]
            if any(sticker is None for sticker in stickers):
                raise ValueError("source_sticker_changed")
            await asyncio.to_thread(store.forward_live, row)
            self._remember_source(row["source_id"])
            for index, part in enumerate(source_parts(snapshot["discord_plain"], snapshot.get("display_name", snapshot["author_name"]))):
                async with self._publish_lock:
                    attempted = True
                    nonce = "ca:" + hashlib.sha256((row["source_id"] + ":" + str(index)).encode()).hexdigest()[:20]
                    identifier = await asyncio.wait_for(self._publish_line(channel, part, nonce,
                        files=files if index == 0 else None, stickers=stickers if index == 0 else None), timeout=45)
                    if identifier not in copies:
                        copies.append(identifier)
            await asyncio.to_thread(store.finish, row["source_id"], self.owner, copies)
        except asyncio.CancelledError:
            await asyncio.shield(asyncio.to_thread(store.finish, row["source_id"], self.owner, copies,
                attempted=attempted, error="interrupted_copy"))
            raise
        except Exception as failure:
            reason = mirror_failure(failure)
            await asyncio.to_thread(store.finish, row["source_id"], self.owner, copies,
                attempted=attempted, error=reason)
            log.warning("Original Discord preservado; cópia não confirmada (%s)", reason)
        finally:
            for file in files:
                file.close()

    async def _delete_source(self, client, channel, store, row):
        import discord
        try:
            if row["guild_id"] != str(channel.guild.id) or row["channel_id"] != str(channel.id):
                raise ValueError("source_scope_mismatch")
            if not row["copy_ids"] or row["source_id"] in row["copy_ids"]:
                raise ValueError("invalid_copy_receipt")
            own = row["lumo"] and row["author_id"] == str(client.user.id)
            self._source_permissions(channel, own)
            try:
                original = await channel.fetch_message(int(row["source_id"]))
                if str(original.author.id) != row["author_id"] or getattr(original, "webhook_id", None):
                    raise ValueError("source_author_mismatch")
                await original.delete()
            except discord.NotFound:
                pass
            await asyncio.to_thread(store.deleted, row["source_id"])
        except asyncio.CancelledError:
            raise
        except Exception as failure:
            reason = mirror_failure(failure)
            await asyncio.to_thread(store.deleted, row["source_id"], error=reason)
            log.warning("Remoção do original Discord pendente (%s)", reason)

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

    async def _mirror_sources(self, client):
        from chat_arkland_routes import get_chat_service
        while not client.is_closed():
            try:
                service, settings = get_chat_service(), self.load_settings()
                guild, channel_id = str(settings.get("lumo_guild_id") or ""), str(settings.get("lumo_game_chat_channel_id") or "")
                store = getattr(service, "mirrors", None)
                enabled = bool(store and await asyncio.to_thread(transport_enabled))
                self._mirror_status = {"enabled": enabled, "ready": False, "permissions": {}, "last_error": ""}
                if enabled and guild.isdigit() and channel_id.isdigit():
                    channel = client.get_channel(int(channel_id))
                    if channel and str(getattr(getattr(channel, "guild", None), "id", "")) == guild:
                        member = getattr(channel.guild, "me", None)
                        permissions = channel.permissions_for(member) if member else None
                        flags = {key: bool(getattr(permissions, key, False)) for key in
                            ("view_channel", "send_messages", "read_message_history", "manage_messages", "attach_files")}
                        ready = all(flags[key] for key in ("view_channel", "send_messages", "read_message_history", "manage_messages"))
                        self._mirror_status = {"enabled": True, "ready": ready, "permissions": flags,
                            "last_error": "" if ready else "missing_channel_permissions"}
                        row = await asyncio.to_thread(store.claim, self.owner, guild, channel_id)
                        if row:
                            await self._copy_source(client, channel, store, row)
                        copied = await asyncio.to_thread(store.pending_deletion, guild, channel_id)
                        if copied:
                            await self._delete_source(client, channel, store, copied)
            except asyncio.CancelledError:
                raise
            except Exception as failure:
                self._mirror_status = {"enabled": True, "ready": False, "permissions": {}, "last_error": type(failure).__name__}
                log.warning("Consolidação Discord indisponível (%s)", type(failure).__name__)
            await asyncio.sleep(0.5)

    async def run(self, client):
        from chat_arkland_routes import get_chat_service
        self._group_message, self._group_lines = None, []
        callbacks = asyncio.Queue(maxsize=64)
        callback_task = asyncio.create_task(self._relay_callbacks(client, callbacks)) if self.relay_handler else None
        mirror_task = asyncio.create_task(self._mirror_sources(client))
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
            mirror_task.cancel()
            await asyncio.gather(mirror_task, return_exceptions=True)
            if callback_task:
                callback_task.cancel()
                await asyncio.gather(callback_task, return_exceptions=True)
