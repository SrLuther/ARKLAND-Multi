"""Gateway runtime do Lumo, isolado do ciclo das páginas administrativas."""
from __future__ import annotations

import asyncio
from collections import deque
import logging
import random
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from lumo_assistant import (
    GREETING_REPLIES,
    TriggerMatch,
    build_response,
    make_embed_payload,
    pick_greeting,
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
        self._source_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._scheduler_task: asyncio.Task[Any] | None = None

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
        enabled = bool(settings.get("lumo_assistant_enabled"))
        token = str(settings.get("lumo_bot_token") or "").strip()
        guild_id = str(settings.get("lumo_guild_id") or "").strip()
        channel_id = str(settings.get("lumo_interaction_channel_id") or "").strip()
        if not enabled:
            self.stop()
            return True, "Assistente interativo desativado."
        if not token or not guild_id.isdigit() or not channel_id.isdigit():
            self.stop()
            return False, "Configure o token e os IDs do servidor e do único canal autorizado antes de ativar."
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
                    if self._scheduler_task is None or self._scheduler_task.done():
                        self._scheduler_task = asyncio.create_task(self._scheduler(inner_self))

                async def on_disconnect(inner_self) -> None:
                    with self._lock:
                        if self._state != "stopped":
                            self._state = "reconnecting"

                async def on_resumed(inner_self) -> None:
                    with self._lock:
                        self._state = "online"

                async def on_message(inner_self, message: Any) -> None:
                    await self._on_message(inner_self, message)

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

    async def _on_message(self, client: Any, message: Any) -> None:
        # Validar canal/servidor antes de processar texto, menção ou qualquer consulta.
        config = self._load_settings()
        if not config.get("lumo_assistant_enabled"):
            return
        if getattr(message, "guild", None) is None or getattr(message, "webhook_id", None):
            return
        if getattr(message.author, "bot", False) or message.author.id == getattr(client.user, "id", None):
            return
        if str(message.guild.id) != str(config.get("lumo_guild_id") or ""):
            return
        if str(message.channel.id) != str(config.get("lumo_interaction_channel_id") or ""):
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
        if not config.get("lumo_assistant_enabled"):
            return
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
                config[state_key] = _utc_iso(last_auto + timedelta(minutes=15))
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
