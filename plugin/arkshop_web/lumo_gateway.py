"""Gateway runtime do Lumo, isolado do ciclo das páginas administrativas."""
from __future__ import annotations

import asyncio
import hashlib
from collections import deque
import logging
import random
import re
import threading
import time
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from lumo_assistant import (
    GAME_CHAT_REPLIES,
    GREETING_REPLIES,
    TriggerMatch,
    build_response,
    make_embed_payload,
    pick_greeting,
    recognize_game_topic,
    recognize_trigger,
)

log = logging.getLogger("arkshop_web.lumo.gateway")
_UTC = timezone.utc
_AUTO_TYPES = ("betland", "polls")


def _utc_iso(value: datetime | None = None) -> str:
    return (value or datetime.now(_UTC)).astimezone(_UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_utc(raw: Any) -> datetime | None:
    try:
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return value.replace(tzinfo=_UTC) if value.tzinfo is None else value.astimezone(_UTC)
    except (TypeError, ValueError):
        return None


class LumoGatewayRunner:
    """Singleton lifecycle for the one-process Waitress Web Store deployment."""

    def __init__(
        self,
        load_settings: Callable[[], dict[str, Any]],
        save_settings: Callable[[dict[str, Any]], None],
        source_provider: Callable[[str], dict[str, Any]],
        audit_event: Callable[..., Any],
    ) -> None:
        self._load_settings = load_settings
        self._save_settings = save_settings
        self._source_provider = source_provider
        self._audit_event = audit_event
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._client: Any = None
        self._state = "stopped"
        self._last_error = ""
        self._started_at: float | None = None
        self._last_interaction = ""
        self._last_announcement = ""
        self._responses = 0
        self._announcements = 0
        self._last_greeting: dict[str, str] = {}
        self._user_last: dict[str, float] = {}
        self._trigger_last: dict[str, float] = {}
        self._global_last = 0.0
        self._global_hour: deque[float] = deque()
        self._seen_messages: deque[str] = deque(maxlen=5000)
        self._seen_message_ids: set[str] = set()
        self._grouped_content_by_id: dict[str, str] = {}
        self._grouped_content_order: deque[str] = deque(maxlen=2000)
        self._game_topic_last: dict[str, float] = {}
        self._game_user_topic_last: dict[str, float] = {}
        self._game_greeting_last = 0.0
        self._game_global_last = 0.0
        self._source_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._scheduler_task: asyncio.Task[Any] | None = None
        self._chat_task: asyncio.Task[Any] | None = None
        from chat_arkland_discord import ChatDiscordTransport
        self._chat_transport = ChatDiscordTransport(lambda: self._load_settings(), relay_handler=self._on_verified_game_relay)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            alive = bool(self._thread and self._thread.is_alive())
            state = self._state if alive else ("error" if self._last_error else "stopped")
            return {
                "state": state,
                "connected": state == "online",
                "last_error": self._last_error,
                "started_at": _utc_iso(datetime.fromtimestamp(self._started_at, _UTC)) if self._started_at else "",
                "uptime_seconds": max(0, int(time.time() - self._started_at)) if self._started_at else 0,
                "last_interaction_at": self._last_interaction,
                "last_announcement_at": self._last_announcement,
                "responses": self._responses,
                "announcements": self._announcements,
                "scheduler_running": bool(self._scheduler_task and not self._scheduler_task.done()),
            }

    def reconfigure(self) -> tuple[bool, str]:
        settings = self._load_settings()
        from chat_arkland_discord import transport_enabled
        chat_enabled = transport_enabled()
        enabled = bool(settings.get("lumo_assistant_enabled") or settings.get("lumo_game_chat_enabled") or chat_enabled)
        token = str(settings.get("lumo_bot_token") or "").strip()
        guild_id = str(settings.get("lumo_guild_id") or "").strip()
        channel_id = str(settings.get("lumo_interaction_channel_id") or "").strip()
        if not enabled:
            self.stop()
            return True, "Assistente interativo desativado."
        game_channel_id = str(settings.get("lumo_game_chat_channel_id") or "").strip()
        if (not token or not guild_id.isdigit()
                or (settings.get("lumo_assistant_enabled") and not channel_id.isdigit())
                or ((settings.get("lumo_game_chat_enabled") or chat_enabled) and not game_channel_id.isdigit())):
            self.stop()
            return False, "Configure token, servidor e os IDs dos canais habilitados antes de ativar."
        with self._lock:
            old_thread = self._thread if self._thread and self._thread.is_alive() else None
            client, loop = self._client, self._loop
            if old_thread and client is not None and loop is not None and not loop.is_closed():
                asyncio.run_coroutine_threadsafe(client.close(), loop)
        if old_thread:
            old_thread.join(10.0)
            if old_thread.is_alive():
                return False, "O Gateway atual ainda está encerrando; tente aplicar a configuração novamente em alguns segundos."
        with self._lock:
            self._last_error = ""
            self._state = "starting"
            self._thread = threading.Thread(target=self._run, args=(token,), name="LumoDiscordGateway", daemon=True)
            self._thread.start()
        return True, "Conectando o Lumo ao Discord Gateway."

    def stop(self, timeout: float = 10.0) -> None:
        with self._lock:
            thread, client, loop = self._thread, self._client, self._loop
            if not thread or not thread.is_alive():
                self._state = "stopped"
                return
            if client is not None and loop is not None and not loop.is_closed():
                try:
                    asyncio.run_coroutine_threadsafe(client.close(), loop)
                except Exception:
                    log.exception("Não foi possível solicitar o encerramento do Gateway Lumo")
        if thread is not threading.current_thread():
            thread.join(timeout)

    def _run(self, token: str) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            import discord

            intents = discord.Intents.none()
            intents.guilds = True
            intents.messages = True
            intents.message_content = True

            class LumoClient(discord.Client):
                async def on_ready(inner_self) -> None:
                    with self._lock:
                        self._state = "online"
                        self._last_error = ""
                        self._started_at = self._started_at or time.time()
                    log.info("Lumo Gateway conectado (bot_id=%s)", getattr(inner_self.user, "id", ""))
                    try:
                        settings = self._load_settings()
                        bot_id = str(getattr(inner_self.user, "id", "") or "")
                        if bot_id and settings.get("lumo_bot_user_id") != bot_id:
                            settings["lumo_bot_user_id"] = bot_id
                            self._save_settings(settings)
                    except Exception:
                        log.debug("Não foi possível persistir o ID do usuário Lumo", exc_info=True)
                    if self._scheduler_task is None or self._scheduler_task.done():
                        self._scheduler_task = asyncio.create_task(self._scheduler(inner_self))
                    if self._chat_task is None or self._chat_task.done():
                        self._chat_task = asyncio.create_task(self._chat_transport.run(inner_self))

                async def on_disconnect(inner_self) -> None:
                    with self._lock:
                        if self._state != "stopped":
                            self._state = "reconnecting"

                async def on_resumed(inner_self) -> None:
                    with self._lock:
                        self._state = "online"

                async def on_message(inner_self, message: Any) -> None:
                    await self._on_message(inner_self, message)

                async def on_message_edit(inner_self, before: Any, after: Any) -> None:
                    await self._on_message_edit(inner_self, before, after)

            client = LumoClient(intents=intents)
            with self._lock:
                self._client = client
            loop.run_until_complete(client.start(token, reconnect=True))
        except Exception as exc:
            detail = str(exc).replace(token, "[REDACTED]") if token else str(exc)
            safe = f"{type(exc).__name__}: {detail[:240]}"
            with self._lock:
                self._last_error = safe
                self._state = "error"
            log.error("Falha no Gateway do Lumo: %s", safe)
        finally:
            pending = [task for task in (self._scheduler_task, self._chat_task) if task is not None and not task.done()]
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self._scheduler_task = self._chat_task = None
            with self._lock:
                self._client = None
                self._loop = None
                if self._state not in {"error"}:
                    self._state = "stopped"
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()

    async def _get_data(self, source: str) -> dict[str, Any]:
        cached = self._source_cache.get(source)
        if cached and time.monotonic() - cached[0] < 30:
            return dict(cached[1])
        try:
            result = await asyncio.to_thread(self._source_provider, source)
            result = result if isinstance(result, dict) else {"ok": False}
            self._source_cache[source] = (time.monotonic(), dict(result))
            return result
        except Exception as exc:
            log.warning("Consulta da fonte Lumo %s falhou: %s", source, type(exc).__name__)
            return {"ok": False}

    async def preview(self, text: str) -> dict[str, Any]:
        config = self._load_settings()
        licenses = await self._get_data("licenses")
        match = recognize_trigger(
            text, licenses.get("licenses", []),
            aliases=config.get("lumo_trigger_aliases"),
            enabled=config.get("lumo_trigger_enabled"),
        )
        if match is None:
            return {"recognized": False, "reason": "Nenhum dos quatro gatilhos autorizados foi identificado.", "embed": None}
        source = {"STATUS": "status", "BETLAND": "betland", "LICENCAS": "licenses", "VOTACAO": "polls"}[match.key]
        data = licenses if source == "licenses" else await self._get_data(source)
        try:
            title, description = build_response(match, data, config)
            embed = make_embed_payload(title, description)
            return {"recognized": True, "trigger": match.key, "rule": match.rule, "source": source, "embed": embed, "reason": ""}
        except Exception as exc:
            return {"recognized": True, "trigger": match.key, "rule": match.rule, "source": source, "embed": None, "reason": str(exc)}

    async def preview_game_chat(self, text: str) -> dict[str, Any]:
        config = self._load_settings()
        topic = recognize_game_topic(text, config.get("lumo_game_chat_trigger_aliases"), config.get("lumo_game_chat_topic_enabled"))
        if not topic:
            return {"recognized": False, "reason": "Nenhum gatilho do Chat do Jogo foi identificado."}
        if topic == "BETLAND":
            data = await self._get_data("betland")
            if not data.get("ok"):
                return {"recognized": True, "trigger": topic, "message": "", "reason": "Fonte BetLand indisponível; nenhuma resposta seria enviada."}
            campaign = data.get("campaign") or {}
            if data.get("enabled") and str(campaign.get("status") or "").upper() == "ACTIVE" and campaign.get("prize_amber_total") is not None and campaign.get("seconds_remaining") is not None:
                hours, minutes = divmod(max(0, int(campaign["seconds_remaining"])) // 60, 60)
                message = f"A BetLand está com {int(campaign['prize_amber_total']):,} Âmbares e faltam {hours}h{minutes:02d} para o sorteio. arkland.com.br".replace(",", ".")
            else:
                message = "No momento não há sorteio aberto na BetLand. Confira as novidades em arkland.com.br."
        elif topic == "VOTACAO":
            data = await self._get_data("polls")
            if not data.get("ok"):
                return {"recognized": True, "trigger": topic, "message": "", "reason": "Fonte de votações indisponível; nenhuma resposta seria enviada."}
            polls = [item for item in data.get("polls", []) if isinstance(item, dict) and item.get("is_open")]
            message = f"Há {len(polls)} votação(ões) aberta(s) no site. Participe em arkland.com.br." if polls else "No momento não há votações abertas. Acompanhe em arkland.com.br."
        elif topic == "SEASON":
            data = await self._get_data("season")
            if not data.get("ok"):
                return {"recognized": True, "trigger": topic, "message": "", "reason": "Fonte SeasonLand indisponível; nenhuma resposta seria enviada."}
            season = data.get("season") or {}
            if str(season.get("status") or "").lower() == "active":
                remaining = season.get("days_remaining")
                message = f"A {season.get('name') or 'SeasonLand'} está ativa" + (f" por mais {int(remaining)} dia(s)" if remaining is not None else "") + ". Confira em arkland.com.br."
            else:
                message = "No momento não há temporada ativa na SeasonLand. Acompanhe as novidades em arkland.com.br."
        else:
            message = GAME_CHAT_REPLIES[topic]
        maximum = max(80, min(250, int(config.get("lumo_game_chat_max_chars", 250))))
        if len(message) > maximum:
            return {"recognized": True, "trigger": topic, "message": "", "reason": f"A resposta excede o limite atual de {maximum} caracteres e seria omitida."}
        return {"recognized": True, "trigger": topic, "message": message, "reason": "Simulação local; nada foi enviado."}

    def send_game_message(self, text: str, timeout: float = 12.0) -> str:
        config = self._load_settings()
        if not config.get("lumo_game_chat_enabled") or not config.get("lumo_game_chat_channel_id"):
            raise RuntimeError("Chat do Jogo desativado ou canal não configurado.")
        with self._lock:
            client, loop = self._client, self._loop
        if client is None or loop is None or loop.is_closed():
            raise RuntimeError("O Gateway do Lumo não está conectado.")
        future = asyncio.run_coroutine_threadsafe(self._send_manual_game_message(client, text, config), loop)
        return future.result(timeout=timeout)

    async def _send_manual_game_message(self, client: Any, text: str, config: dict[str, Any]) -> str:
        channel = client.get_channel(int(config["lumo_game_chat_channel_id"]))
        if channel is None:
            raise RuntimeError("O Gateway não encontrou o canal do Chat do Jogo.")
        maximum = max(80, min(250, int(config.get("lumo_game_chat_max_chars", 250))))
        text = " ".join(str(text).split())
        if not text or len(text) > maximum:
            raise ValueError(f"A mensagem deve conter entre 1 e {maximum} caracteres.")
        sent = await channel.send(text, allowed_mentions=__import__("discord").AllowedMentions.none())
        self._audit("lumo_game_manual_message", status="success", channel_id=str(channel.id), discord_message_id=str(getattr(sent, "id", "")))
        return str(getattr(sent, "id", ""))

    async def _on_message(self, client: Any, message: Any) -> None:
        # Validar canal/servidor antes de processar texto, menção ou qualquer consulta.
        config = self._load_settings()
        await self._chat_transport.incoming(client, message)
        if not (config.get("lumo_assistant_enabled") or config.get("lumo_game_chat_enabled")):
            return
        if getattr(message, "guild", None) is None:
            return
        bot_id = str(getattr(client.user, "id", "") or "")
        is_webhook = bool(getattr(message, "webhook_id", None))
        if ((getattr(message.author, "bot", False) and not is_webhook)
                or str(getattr(message.author, "id", "")) == bot_id
                or str(getattr(message.author, "id", "")) == str(config.get("lumo_bot_user_id") or "")):
            return
        if str(message.guild.id) != str(config.get("lumo_guild_id") or ""):
            return
        channel_id = str(message.channel.id)
        global_channel = str(config.get("lumo_interaction_channel_id") or "")
        game_channel = str(config.get("lumo_game_chat_channel_id") or "")
        is_game_channel = bool(config.get("lumo_game_chat_enabled")) and bool(game_channel) and channel_id == game_channel
        is_global_channel = bool(global_channel) and channel_id == global_channel
        if not is_game_channel and not (config.get("lumo_assistant_enabled") and is_global_channel and not is_webhook):
            return
        if is_game_channel:
            if is_webhook and not config.get("lumo_game_chat_webhooks_enabled"):
                return
            await self._on_game_chat_message(client, message, config, is_webhook)
            return
        message_id = str(getattr(message, "id", "") or "")
        if message_id and message_id in self._seen_message_ids:
            return
        if message_id:
            if len(self._seen_messages) == self._seen_messages.maxlen:
                expired = self._seen_messages[0]
                self._seen_message_ids.discard(expired)
            self._seen_messages.append(message_id)
            self._seen_message_ids.add(message_id)

        now_mono = time.monotonic()
        user_key = str(message.author.id)
        try:
            user_cooldown = max(0, min(3600, int(config.get("lumo_user_cooldown_seconds", 15))))
            trigger_cooldown = max(0, min(3600, int(config.get("lumo_trigger_cooldown_seconds", 20))))
            global_cooldown = max(0, min(120, int(config.get("lumo_global_cooldown_seconds", 3))))
            hourly_limit = max(1, min(500, int(config.get("lumo_global_hourly_limit", 40))))
        except (TypeError, ValueError):
            log.warning("Configuração inválida de limites do Gateway Lumo; mensagem ignorada")
            return
        if now_mono - self._user_last.get(user_key, 0) < user_cooldown:
            return
        content = str(getattr(message, "content", "") or "")[:4000]
        license_data = await self._get_data("licenses")
        match = recognize_trigger(
            content, license_data.get("licenses", []),
            aliases=config.get("lumo_trigger_aliases"),
            enabled=config.get("lumo_trigger_enabled"),
        )
        mentioned = any(getattr(user, "id", None) == getattr(client.user, "id", None) for user in getattr(message, "mentions", []))
        if not match and not mentioned:
            return

        trigger_key = match.key if match else "MENTION"
        if now_mono - self._trigger_last.get(trigger_key, 0) < trigger_cooldown:
            return
        if now_mono - self._global_last < global_cooldown:
            return
        while self._global_hour and now_mono - self._global_hour[0] >= 3600:
            self._global_hour.popleft()
        if len(self._global_hour) >= hourly_limit:
            return

        source_map = {"STATUS": "status", "BETLAND": "betland", "LICENCAS": "licenses", "VOTACAO": "polls"}
        try:
            if match:
                source = source_map[match.key]
                data = license_data if source == "licenses" else await self._get_data(source)
                title, description = build_response(match, data, config)
            else:
                previous = self._last_greeting.get(user_key, "")
                title = ""
                configured_replies = config.get("lumo_greeting_replies")
                replies = [str(x).strip() for x in configured_replies if str(x).strip()] if isinstance(configured_replies, list) else []
                if replies:
                    choices = [reply for reply in replies if reply != previous] or replies
                    description = random.choice(choices)
                else:
                    description = pick_greeting(previous)
                display_name = str(getattr(message.author, "display_name", "Sobrevivente") or "Sobrevivente")[:80].replace("@", "@\u200b")
                description = description.replace("{jogador}", display_name).replace("{nome}", display_name)
                self._last_greeting[user_key] = description
            embed_data = make_embed_payload(title, description)
            embed = __import__("discord").Embed.from_dict(embed_data)
            embed.set_author(name="Lumo • Assistente oficial da ARKLAND", icon_url="https://arkland.com.br/lumo-avatar.png")
            sent = await message.channel.send(embed=embed, allowed_mentions=__import__("discord").AllowedMentions.none())
            self._user_last[user_key] = now_mono
            self._trigger_last[trigger_key] = now_mono
            self._global_last = now_mono
            self._global_hour.append(now_mono)
            self._last_interaction = _utc_iso()
            self._responses += 1
            self._audit("lumo_interaction", status="success", trigger=trigger_key, channel_id=str(message.channel.id), user_id=user_key, discord_message_id=str(getattr(sent, "id", "")))
        except Exception as exc:
            safe = f"{type(exc).__name__}: {str(exc)[:180]}"
            self._audit("lumo_interaction", status="failed", trigger=trigger_key, channel_id=str(message.channel.id), user_id=user_key, reason=safe)
            log.warning("Resposta do Lumo não enviada (%s)", type(exc).__name__)

    async def _on_verified_game_relay(self, client: Any, channel: Any, context: dict[str, Any]) -> None:
        """Evento original autenticado do hub; não reinterpreta o bloco do bot."""
        config = self._load_settings()
        if (not config.get("lumo_game_chat_enabled") or str(getattr(getattr(channel, "guild", None), "id", "")) != str(config.get("lumo_guild_id") or "")
                or str(channel.id) != str(config.get("lumo_game_chat_channel_id") or "")):
            return
        verified = SimpleNamespace(id="ca:" + context["event_id"], guild=channel.guild,
            channel=channel, author=SimpleNamespace(id=context["steam_id"], bot=False),
            content=context["body"], webhook_id=None, mentions=[], verified_chat_event=True)
        await self._on_game_chat_message(client, verified, config, False)

    async def _on_game_chat_message(self, client: Any, message: Any, config: dict[str, Any], is_webhook: bool) -> None:
        """Responde somente com o texto que deve vir depois do ':' no chat do jogo."""
        if not config.get("lumo_game_chat_keywords_enabled"):
            return
        author = getattr(message, "author", None)
        if ((getattr(author, "bot", False) and not is_webhook)
                or str(getattr(author, "id", "")) == str(getattr(client.user, "id", "") or "")
                or str(getattr(author, "id", "")) == str(config.get("lumo_bot_user_id") or "")):
            return
        message_id = str(getattr(message, "id", "") or "")
        if message_id and not message_id.startswith("grouped:") and message_id not in self._grouped_content_by_id:
            if len(self._grouped_content_order) == self._grouped_content_order.maxlen:
                self._grouped_content_by_id.pop(self._grouped_content_order[0], None)
            self._grouped_content_order.append(message_id)
        if message_id and not message_id.startswith("grouped:"):
            self._grouped_content_by_id[message_id] = str(getattr(message, "content", "") or "")
        if message_id and message_id in self._seen_message_ids:
            return
        if message_id:
            if len(self._seen_messages) == self._seen_messages.maxlen:
                self._seen_message_ids.discard(self._seen_messages[0])
            self._seen_messages.append(message_id)
            self._seen_message_ids.add(message_id)

        content = str(getattr(message, "content", "") or "").strip()
        player_key = str(getattr(getattr(message, "author", None), "id", "") or "")
        # O plugin de ponte adiciona horário/origem/licença/nickname/tribo. Esses
        # campos servem só para retirar o envelope; nunca são identidade/autorização.
        bridge = None if getattr(message, "verified_chat_event", False) else re.match(
            r"^\[\d{1,2}:\d{2}\]\[(?:Discord|.+?)\]\s*(?:<[^>]{1,80}>\s*)?(.+?):\s*(.*)$",
            content, re.I | re.S,
        )
        if bridge:
            label, content = bridge.group(1).strip(), bridge.group(2).strip()
            if re.sub(r"[^a-z]", "", label.casefold()) == "lumo":
                self._audit("lumo_game_message_ignored", status="own_message", channel_id=str(message.channel.id), webhook=is_webhook)
                return
            player_key = f"bridge:{getattr(message, 'webhook_id', '')}:{label.casefold()[:80]}"
        if not content:
            return
        topic = recognize_game_topic(content, config.get("lumo_game_chat_trigger_aliases"), config.get("lumo_game_chat_topic_enabled"))
        if not topic:
            return

        now_mono = time.monotonic()
        try:
            topic_cooldown = max(0, min(3600, int(config.get("lumo_game_chat_topic_cooldown_seconds", 120))))
            user_cooldown = max(0, min(3600, int(config.get("lumo_game_chat_user_topic_cooldown_seconds", 300))))
            greeting_cooldown = max(600, min(86400, int(config.get("lumo_game_chat_greeting_cooldown_seconds", 600))))
            global_cooldown = max(0, min(120, int(config.get("lumo_game_chat_global_cooldown_seconds", 5))))
            max_chars = max(80, min(250, int(config.get("lumo_game_chat_max_chars", 250))))
        except (TypeError, ValueError):
            log.warning("Configuração inválida do Chat do Jogo; mensagem ignorada")
            return
        if topic == "LUMO" and now_mono - self._game_greeting_last < greeting_cooldown:
            self._audit("lumo_game_response", status="cooldown", trigger=topic, channel_id=str(message.channel.id))
            return
        user_topic = f"{player_key}:{topic}"
        if (now_mono - self._game_topic_last.get(topic, 0) < topic_cooldown
                or now_mono - self._game_user_topic_last.get(user_topic, 0) < user_cooldown
                or now_mono - self._game_global_last < global_cooldown):
            self._audit("lumo_game_response", status="cooldown", trigger=topic, channel_id=str(message.channel.id))
            return

        if topic == "BETLAND":
            data = await self._get_data("betland")
            campaign = data.get("campaign") or {}
            if not data.get("ok"):
                self._audit("lumo_game_response", status="source_unavailable", trigger=topic, channel_id=str(message.channel.id))
                return
            if data.get("enabled") and str(campaign.get("status") or "").upper() == "ACTIVE":
                prize = campaign.get("prize_amber_total")
                remaining = campaign.get("seconds_remaining")
                if prize is None or remaining is None:
                    return
                hours, minutes = divmod(max(0, int(remaining)) // 60, 60)
                reply = f"A BetLand está com {int(prize):,} Âmbares e faltam {hours}h{minutes:02d} para o sorteio. arkland.com.br".replace(",", ".")
            else:
                reply = "No momento não há sorteio aberto na BetLand. Confira as novidades em arkland.com.br."
        elif topic == "VOTACAO":
            data = await self._get_data("polls")
            if not data.get("ok"):
                self._audit("lumo_game_response", status="source_unavailable", trigger=topic, channel_id=str(message.channel.id))
                return
            polls = [item for item in data.get("polls", []) if isinstance(item, dict) and item.get("is_open")]
            if polls:
                first = polls[0]
                reward = first.get("reward_amber")
                reply = f"Há {len(polls)} votação(ões) aberta(s) no site. Participe em arkland.com.br" + (f"; recompensa atual: {int(reward):,} Âmbares.".replace(",", ".") if reward is not None else ".")
            else:
                reply = "No momento não há votações abertas. Acompanhe em arkland.com.br."
        elif topic == "SEASON":
            data = await self._get_data("season")
            if not data.get("ok"):
                self._audit("lumo_game_response", status="source_unavailable", trigger=topic, channel_id=str(message.channel.id))
                return
            season = data.get("season") or {}
            if str(season.get("status") or "").lower() == "active":
                remaining = season.get("days_remaining")
                reply = f"A {season.get('name') or 'SeasonLand'} está ativa" + (f" por mais {int(remaining)} dia(s)" if remaining is not None else "") + ". Confira em arkland.com.br."
            else:
                reply = "No momento não há temporada ativa na SeasonLand. Acompanhe as novidades em arkland.com.br."
        else:
            reply = GAME_CHAT_REPLIES[topic]
        reply = " ".join(str(reply).split())
        if len(reply) > max_chars:
            # Não truncar detalhes que possam mudar o sentido da resposta.
            self._audit("lumo_game_response", status="message_too_long", trigger=topic, channel_id=str(message.channel.id))
            return
        try:
            sent = await message.channel.send(reply, allowed_mentions=__import__("discord").AllowedMentions.none())
            self._game_topic_last[topic] = now_mono
            self._game_user_topic_last[user_topic] = now_mono
            self._game_global_last = now_mono
            if topic == "LUMO":
                self._game_greeting_last = now_mono
            self._last_interaction = _utc_iso()
            self._responses += 1
            self._audit("lumo_game_response", status="success", trigger=topic, channel_id=str(message.channel.id), discord_message_id=str(getattr(sent, "id", "")), webhook=is_webhook)
        except Exception as exc:
            self._audit("lumo_game_response", status="failed", trigger=topic, channel_id=str(message.channel.id), reason=type(exc).__name__)
            log.warning("Resposta de chat do Lumo não enviada (%s)", type(exc).__name__)

    async def _on_message_edit(self, client: Any, before: Any, after: Any) -> None:
        """Extrai apenas linhas novas quando a ponte agrega o chat editando uma mensagem."""
        if str(getattr(getattr(after, "author", None), "id", "")) == str(getattr(getattr(client, "user", None), "id", "")) and self._chat_transport.is_relay_message(after):
            return
        config = self._load_settings()
        if not config.get("lumo_game_chat_enabled") or str(getattr(getattr(after, "guild", None), "id", "")) != str(config.get("lumo_guild_id") or ""):
            return
        if str(getattr(getattr(after, "channel", None), "id", "")) != str(config.get("lumo_game_chat_channel_id") or ""):
            return
        is_webhook = bool(getattr(after, "webhook_id", None))
        if is_webhook and not config.get("lumo_game_chat_webhooks_enabled"):
            return
        message_id = str(getattr(after, "id", "") or "")
        previous = self._grouped_content_by_id.get(message_id, str(getattr(before, "content", "") or ""))
        current = str(getattr(after, "content", "") or "")
        if current.startswith(previous):
            additions = current[len(previous):].splitlines()
        else:
            remaining: dict[str, int] = {}
            for line in previous.splitlines():
                remaining[line] = remaining.get(line, 0) + 1
            additions = []
            for line in current.splitlines():
                if remaining.get(line, 0):
                    remaining[line] -= 1
                else:
                    additions.append(line)
        self._grouped_content_by_id[message_id] = current
        for index, line in enumerate(item.strip() for item in additions if item.strip()):
            fingerprint = hashlib.sha256(f"{message_id}:{current}:{index}:{line}".encode("utf-8")).hexdigest()
            grouped = SimpleNamespace(
                id="grouped:" + fingerprint,
                guild=after.guild,
                channel=after.channel,
                author=after.author,
                webhook_id=getattr(after, "webhook_id", None),
                content=line,
                mentions=getattr(after, "mentions", []),
            )
            await self._on_game_chat_message(client, grouped, config, is_webhook)

    def _audit(self, event: str, **details: Any) -> None:
        try:
            self._audit_event(
                event, source="lumo_gateway", actor_type="player", severity="info" if details.get("status") == "success" else "warning",
                message="Interação informativa do Lumo", status_after=str(details.get("status") or "unknown"), **details,
            )
        except Exception:
            log.debug("Auditoria da interação Lumo indisponível", exc_info=True)

    async def _scheduler(self, client: Any) -> None:
        while not client.is_closed():
            try:
                await self._scheduler_tick(client)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("Agendador do Lumo: falha em ciclo (%s)", type(exc).__name__)
            await asyncio.sleep(15)

    async def _scheduler_tick(self, client: Any) -> None:
        config = self._load_settings()
        if not (config.get("lumo_assistant_enabled") or config.get("lumo_game_chat_enabled")):
            return
        await self._game_scheduler_tick(client, config)
        channel = client.get_channel(int(config.get("lumo_interaction_channel_id") or 0))
        if channel is None:
            return
        now = datetime.now(_UTC)
        for category in _AUTO_TYPES:
            enabled = bool(config.get(f"lumo_auto_{category}_enabled"))
            state_key = f"lumo_auto_{category}_next_at"
            if not enabled:
                if config.get(state_key):
                    config[state_key] = ""
                    self._save_settings(config)
                continue
            data = await self._get_data(category)
            active = (bool(data.get("enabled")) and bool(data.get("campaign")) and str((data.get("campaign") or {}).get("status") or "").upper() == "ACTIVE") if category == "betland" else bool(data.get("polls"))
            if not data.get("ok") or not active:
                if config.get(state_key):
                    config[state_key] = ""
                    self._save_settings(config)
                continue
            due = _parse_utc(config.get(state_key))
            if due is None:
                # A new activity begins a fresh persistent randomized interval.
                config[state_key] = _utc_iso(now + timedelta(minutes=random.randint(180, 240)))
                self._save_settings(config)
                continue
            if due > now:
                continue
            last_auto = _parse_utc(config.get("lumo_last_auto_announcement_at"))
            if last_auto and now - last_auto < timedelta(minutes=15):
                config[state_key] = _utc_iso(last_auto + timedelta(minutes=random.randint(15, 20)))
                self._save_settings(config)
                continue
            match = TriggerMatch("BETLAND", "automatic_announcement") if category == "betland" else TriggerMatch("VOTACAO", "automatic_announcement")
            try:
                title, description = build_response(match, data, config)
                import discord
                embed = discord.Embed.from_dict(make_embed_payload(title, description))
                embed.set_author(name="Lumo • Assistente oficial da ARKLAND", icon_url="https://arkland.com.br/lumo-avatar.png")
                sent = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                published = _utc_iso(now)
                config[f"lumo_auto_{category}_last_at"] = published
                config[f"lumo_auto_{category}_last_result"] = "success"
                config[state_key] = _utc_iso(now + timedelta(minutes=random.randint(180, 240)))
                config["lumo_last_auto_announcement_at"] = published
                self._save_settings(config)
                self._last_announcement = published
                self._announcements += 1
                self._audit("lumo_automatic_announcement", status="success", trigger=category, channel_id=str(channel.id), discord_message_id=str(getattr(sent, "id", "")))
            except Exception as exc:
                config[f"lumo_auto_{category}_last_result"] = "failed"
                config[f"lumo_auto_{category}_last_error"] = type(exc).__name__
                config[state_key] = _utc_iso(now + timedelta(minutes=15))
                self._save_settings(config)
                self._audit("lumo_automatic_announcement", status="failed", trigger=category, channel_id=str(channel.id), reason=type(exc).__name__)

    async def _game_scheduler_tick(self, client: Any, config: dict[str, Any]) -> None:
        if not config.get("lumo_game_chat_enabled") or not config.get("lumo_game_chat_announcements_enabled"):
            return
        channel_id = str(config.get("lumo_game_chat_channel_id") or "")
        if not channel_id.isdigit():
            return
        channel = client.get_channel(int(channel_id))
        if channel is None:
            return
        now = datetime.now(_UTC)
        last_auto = _parse_utc(config.get("lumo_game_last_auto_announcement_at"))
        not_before = _parse_utc(config.get("lumo_game_announcements_not_before"))
        if last_auto and (not_before is None or not_before < last_auto + timedelta(minutes=15)):
            not_before = last_auto + timedelta(minutes=random.randint(15, 20))
            config["lumo_game_announcements_not_before"] = _utc_iso(not_before)
            self._save_settings(config)
        if not_before and not_before > now:
            return
        pending = []
        for category, enabled_key, due_key in (("general", "lumo_game_general_announcements_enabled", "lumo_game_general_next_at"),
                ("betland", "lumo_game_auto_betland_enabled", "lumo_game_auto_betland_next_at"),
                ("polls", "lumo_game_auto_polls_enabled", "lumo_game_auto_polls_next_at")):
            due = _parse_utc(config.get(due_key))
            if config.get(enabled_key) and due is not None and due <= now:
                pending.append((due, category))
        oldest = min(pending)[1] if pending else None
        # Anúncios gerais: fila simples de assuntos estáticos, intervalo 30–60 min.
        if config.get("lumo_game_general_announcements_enabled"):
            state_key = "lumo_game_general_next_at"
            due = _parse_utc(config.get(state_key))
            if due is None:
                config[state_key] = _utc_iso(now + timedelta(minutes=random.randint(30, 60)))
                self._save_settings(config)
            elif due <= now and oldest == "general":
                available_topics = ("SITE", "LINK", "CATALOG", "STARTER", "SUPPORT", "STATUS", "SEASON", "LIMIT")
                enabled_topics = config.get("lumo_game_chat_topic_enabled") or {}
                topics = tuple(topic for topic in available_topics if enabled_topics.get(topic, True))
                if not topics:
                    config[state_key] = ""
                    self._save_settings(config)
                    return
                previous = str(config.get("lumo_game_general_last_topic") or "")
                choices = [topic for topic in topics if topic != previous]
                topic = random.choice(choices or list(topics))
                if topic == "SEASON":
                    season_data = await self._get_data("season")
                    season = season_data.get("season") or {}
                    if not season_data.get("ok") or str(season.get("status") or "").lower() != "active":
                        config[state_key] = _utc_iso(now + timedelta(minutes=random.randint(30, 60)))
                        self._save_settings(config)
                        return
                    remaining = season.get("days_remaining")
                    text = f"A {season.get('name') or 'SeasonLand'} está ativa" + (f" por mais {int(remaining)} dia(s)" if remaining is not None else "") + ". Confira em arkland.com.br."
                    sent_general = await self._send_game_text(channel, text, "AUTO_SEASON", config)
                else:
                    sent_general = await self._send_game_announcement(channel, topic, now, config, next_minutes=random.randint(30, 60))
                config["lumo_game_general_last_topic"] = topic
                config[state_key] = _utc_iso(now + timedelta(minutes=random.randint(30, 60)))
                if sent_general:
                    self._mark_game_announcement(config, now)
                else:
                    config["lumo_game_announcements_not_before"] = _utc_iso(now + timedelta(minutes=15))
                self._save_settings(config)
                return
        # BetLand e votações mantêm relógios independentes e só anunciam dados atuais.
        for category, source in (("betland", "betland"), ("polls", "polls")):
            if not config.get(f"lumo_game_auto_{category}_enabled"):
                continue
            state_key = f"lumo_game_auto_{category}_next_at"
            due = _parse_utc(config.get(state_key))
            if due is None:
                config[state_key] = _utc_iso(now + timedelta(minutes=random.randint(180, 240)))
                self._save_settings(config)
                continue
            if due > now:
                continue
            if oldest is not None and oldest != category:
                continue
            data = await self._get_data(source)
            if not data.get("ok"):
                config[state_key] = _utc_iso(now + timedelta(minutes=15))
                config[f"lumo_game_auto_{category}_last_result"] = "source_unavailable"
                self._save_settings(config)
                self._audit("lumo_game_announcement", status="source_unavailable", trigger=category, channel_id=channel_id)
                continue
            if category == "betland":
                campaign = data.get("campaign") or {}
                if not data.get("enabled") or str(campaign.get("status") or "").upper() != "ACTIVE":
                    config[state_key] = ""
                    config[f"lumo_game_auto_{category}_last_result"] = "no_active_campaign"
                    self._save_settings(config)
                    continue
                prize, remaining = campaign.get("prize_amber_total"), campaign.get("seconds_remaining")
                if prize is None or remaining is None:
                    config[state_key] = _utc_iso(now + timedelta(minutes=15))
                    self._save_settings(config)
                    continue
                hours, minutes = divmod(max(0, int(remaining)) // 60, 60)
                message = f"BetLand: prêmio atual de {int(prize):,} Âmbares; faltam {hours}h{minutes:02d} para o sorteio. arkland.com.br".replace(",", ".")
            else:
                polls = [p for p in data.get("polls", []) if isinstance(p, dict) and p.get("is_open")]
                if not polls:
                    config[state_key] = ""
                    config[f"lumo_game_auto_{category}_last_result"] = "no_open_polls"
                    self._save_settings(config)
                    continue
                message = f"Há {len(polls)} votação(ões) aberta(s) no site. Participe em arkland.com.br."
            sent = await self._send_game_text(channel, message, category.upper(), config)
            config[state_key] = _utc_iso(now + timedelta(minutes=random.randint(180, 240) if sent else 15))
            config[f"lumo_game_auto_{category}_last_result"] = "success" if sent else "failed"
            if sent:
                config[f"lumo_game_auto_{category}_last_at"] = _utc_iso(now)
                self._mark_game_announcement(config, now)
            else:
                config["lumo_game_announcements_not_before"] = _utc_iso(now + timedelta(minutes=15))
            self._save_settings(config)
            return  # Uma tentativa por ciclo; resultado ambíguo também reserva pausa.

    @staticmethod
    def _mark_game_announcement(config: dict[str, Any], now: datetime) -> None:
        config["lumo_game_last_auto_announcement_at"] = _utc_iso(now)
        config["lumo_game_announcements_not_before"] = _utc_iso(now + timedelta(minutes=random.randint(15, 20)))

    async def _send_game_announcement(self, channel: Any, topic: str, now: datetime, config: dict[str, Any], *, next_minutes: int) -> bool:
        return await self._send_game_text(channel, GAME_CHAT_REPLIES[topic], f"AUTO_{topic}", config)

    async def _send_game_text(self, channel: Any, message: str, topic: str, config: dict[str, Any]) -> bool:
        message = " ".join(str(message).split())
        maximum = max(80, min(250, int(config.get("lumo_game_chat_max_chars", 250))))
        if len(message) > maximum:
            self._audit("lumo_game_announcement", status="message_too_long", trigger=topic, channel_id=str(channel.id))
            return False
        try:
            sent = await channel.send(message, allowed_mentions=__import__("discord").AllowedMentions.none())
            self._last_announcement = _utc_iso()
            self._announcements += 1
            self._audit("lumo_game_announcement", status="success", trigger=topic, channel_id=str(channel.id), discord_message_id=str(getattr(sent, "id", "")))
            return True
        except Exception as exc:
            self._audit("lumo_game_announcement", status="failed", trigger=topic, channel_id=str(channel.id), reason=type(exc).__name__)
            log.warning("Anúncio do Chat do Jogo não enviado (%s)", type(exc).__name__)
            return False


_RUNTIME: LumoGatewayRunner | None = None
_RUNTIME_LOCK = threading.Lock()


def configure_lumo_runtime(
    load_settings: Callable[[], dict[str, Any]],
    save_settings: Callable[[dict[str, Any]], None],
    source_provider: Callable[[str], dict[str, Any]],
    audit_event: Callable[..., Any],
) -> LumoGatewayRunner:
    global _RUNTIME
    with _RUNTIME_LOCK:
        if _RUNTIME is None:
            _RUNTIME = LumoGatewayRunner(load_settings, save_settings, source_provider, audit_event)
        elif not (_RUNTIME._thread and _RUNTIME._thread.is_alive()):
            # Permite registrar apps Flask isolados em testes sem deixar callbacks
            # presos à primeira instância criada; em produção há um único app.
            _RUNTIME._load_settings = load_settings
            _RUNTIME._save_settings = save_settings
            _RUNTIME._source_provider = source_provider
            _RUNTIME._audit_event = audit_event
        return _RUNTIME


def get_lumo_runtime() -> LumoGatewayRunner | None:
    return _RUNTIME
