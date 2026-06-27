"""Ponte Discord ↔ chat cluster ARK (bidirecional, sem eco)."""
from __future__ import annotations

import asyncio
import logging
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

log = logging.getLogger(__name__)

DISCORD_SOURCE = "Discord"
_DISCORD_STEAM_RE = re.compile(r"^discord:\d{5,}$")
_POLL_INTERVAL = 2.0
_RATE_SECONDS = 2

_bridge_lock = threading.Lock()
_bridge_thread: threading.Thread | None = None
_bridge_stop = threading.Event()
_bridge_client: Any | None = None
_last_forward_id = 0
_rate_limit: dict[str, datetime] = {}

# Estado exposto ao painel admin
_bridge_phase = "idle"  # idle | waiting_db | starting | connected | error | stopped
_bridge_error: str | None = None
_client_ready = False
_channel_resolved = False
_discord_py_available: bool | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _set_phase(phase: str, error: str | None = None) -> None:
    global _bridge_phase, _bridge_error
    _bridge_phase = phase
    if error is not None:
        _bridge_error = error
    elif phase in ("connected", "idle", "stopped", "waiting_db", "starting"):
        _bridge_error = None


def _check_discord_py() -> bool:
    global _discord_py_available
    try:
        import discord  # noqa: F401
    except ImportError:
        _discord_py_available = False
        return False
    _discord_py_available = True
    return True


def is_discord_steam_id(steam_id: str) -> bool:
    return bool(_DISCORD_STEAM_RE.match((steam_id or "").strip()))


def format_discord_outbound(source_server: str, player_name: str, message: str) -> str:
    """Rotula mensagem do jogo para o Discord: [Mapa] Jogador: texto."""
    src = (source_server or "Servidor").strip()
    name = (player_name or "Jogador").strip()
    text = (message or "").strip()
    return f"[{src}] {name}: {text}"


def load_discord_config(load_settings: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Lê config da ponte Discord (settings.json + env)."""
    import os

    s = load_settings()
    enabled = bool(s.get("cross_chat_discord_enabled", False))
    token = str(s.get("cross_chat_discord_token", "")).strip()
    channel_id = str(s.get("cross_chat_discord_channel_id", "")).strip()

    env_enabled = os.environ.get("ARKSHOP_CROSS_CHAT_DISCORD_ENABLED", "").strip().lower()
    if env_enabled in ("1", "true", "yes", "on"):
        enabled = True
    elif env_enabled in ("0", "false", "no", "off"):
        enabled = False

    if not token:
        token = os.environ.get("ARKSHOP_CROSS_CHAT_DISCORD_TOKEN", "").strip()
    if not channel_id:
        channel_id = os.environ.get("ARKSHOP_CROSS_CHAT_DISCORD_CHANNEL_ID", "").strip()

    try:
        ch_id = int(channel_id) if channel_id else 0
    except ValueError:
        ch_id = 0

    global _last_forward_id
    try:
        _last_forward_id = max(0, int(s.get("cross_chat_discord_last_id") or 0))
    except (TypeError, ValueError):
        _last_forward_id = 0

    return {
        "enabled": enabled and bool(token) and ch_id > 0,
        "requested_enabled": enabled,
        "token_set": bool(token),
        "channel_id": ch_id,
        "_token": token,
    }


def _discord_token(load_settings: Callable[[], dict[str, Any]]) -> str:
    cfg = load_discord_config(load_settings)
    return str(cfg.get("_token") or "")


def _save_forward_cursor(
    load_settings: Callable[[], dict[str, Any]],
    save_settings: Callable[[dict[str, Any]], None],
    last_id: int,
) -> None:
    s = load_settings()
    s["cross_chat_discord_last_id"] = int(last_id)
    save_settings(s)


def _rate_limited(key: str) -> bool:
    now = _utcnow()
    prev = _rate_limit.get(key)
    if prev and (now - prev).total_seconds() < _RATE_SECONDS:
        return True
    _rate_limit[key] = now
    return False


def _fetch_game_messages(session_factory: Callable[[], Any]) -> list[tuple[int, str, str, str]]:
    from sqlalchemy import text

    global _last_forward_id
    db = session_factory()
    try:
        rows = db.execute(
            text(
                "SELECT id, source_server, player_name, message "
                "FROM cross_server_chat "
                "WHERE id > :since AND channel = 'cluster' "
                "ORDER BY id ASC LIMIT 50"
            ),
            {"since": _last_forward_id},
        ).fetchall()
        return [(int(r[0]), str(r[1]), str(r[2]), str(r[3])) for r in rows]
    finally:
        db.close()


def _advance_forward_cursor(
    load_settings: Callable[[], dict[str, Any]],
    save_settings: Callable[[dict[str, Any]], None],
    max_id: int,
) -> None:
    global _last_forward_id
    if max_id > _last_forward_id:
        _last_forward_id = max_id
        _save_forward_cursor(load_settings, save_settings, _last_forward_id)


def _publish_discord_message(
    session_factory: Callable[[], Any],
    author_name: str,
    content: str,
    discord_user_id: int,
) -> None:
    from cross_chat_service import publish_message

    steam_id = f"discord:{discord_user_id}"
    db = session_factory()
    try:
        result = publish_message(
            db,
            source_server=DISCORD_SOURCE,
            steam_id=steam_id,
            player_name=author_name,
            message=content,
            channel="discord",
        )
        if not result.get("ok"):
            log.debug("CrossChat Discord: publish recusado: %s", result.get("error"))
    finally:
        db.close()


def _close_bridge_client(timeout: float = 6.0) -> None:
    global _bridge_client
    client = _bridge_client
    if client is None:
        return
    loop = getattr(client, "loop", None)
    if loop is not None and loop.is_running():
        try:
            fut = asyncio.run_coroutine_threadsafe(client.close(), loop)
            fut.result(timeout=timeout)
        except Exception as exc:
            log.debug("CrossChat Discord: close client: %s", exc)
    _bridge_client = None


def _run_bridge(
    session_factory: Callable[[], Any],
    load_settings: Callable[[], dict[str, Any]],
    save_settings: Callable[[dict[str, Any]], None],
) -> None:
    global _bridge_client, _client_ready, _channel_resolved

    if not _check_discord_py():
        msg = "discord.py nao instalado — pip install discord.py (ou rebuild do Web Store)"
        log.error("CrossChat Discord: %s", msg)
        _set_phase("error", msg)
        return

    import discord

    cfg = load_discord_config(load_settings)
    if not cfg["enabled"]:
        log.info("CrossChat Discord: desativado ou incompleto (token/canal).")
        _set_phase("idle")
        return

    channel_id: int = cfg["channel_id"]
    stop = _bridge_stop
    _set_phase("starting")
    _client_ready = False
    _channel_resolved = False

    class BridgeClient(discord.Client):
        def __init__(self) -> None:
            intents = discord.Intents.default()
            intents.message_content = True
            super().__init__(intents=intents)
            self._out_channel: discord.abc.Messageable | None = None

        async def _resolve_channel(self) -> discord.abc.Messageable | None:
            ch = self.get_channel(channel_id)
            if ch is not None:
                return ch
            try:
                fetched = await self.fetch_channel(channel_id)
                if isinstance(fetched, discord.abc.Messageable):
                    return fetched
            except discord.Forbidden:
                _set_phase(
                    "error",
                    f"Bot sem permissao no canal {channel_id} — convide o bot e conceda Enviar Mensagens",
                )
            except discord.NotFound:
                _set_phase(
                    "error",
                    f"Canal {channel_id} nao encontrado — verifique o ID e se o bot esta no servidor",
                )
            except Exception as exc:
                log.warning("CrossChat Discord: fetch canal falhou: %s", exc)
            return None

        async def setup_hook(self) -> None:
            self.loop.create_task(self._poll_outbound())

        async def on_ready(self) -> None:
            global _client_ready, _channel_resolved
            _client_ready = True
            self._out_channel = await self._resolve_channel()
            _channel_resolved = self._out_channel is not None
            if self._out_channel is None and _bridge_error is None:
                _set_phase(
                    "error",
                    f"Canal {channel_id} indisponivel — confira ID, convite do bot e permissoes",
                )
            else:
                _set_phase("connected")
            log.info(
                "CrossChat Discord: conectado como %s (canal %s, resolvido=%s)",
                self.user,
                channel_id,
                _channel_resolved,
            )

        async def on_message(self, message: discord.Message) -> None:
            if message.author.bot or message.channel.id != channel_id:
                return
            text = (message.content or "").strip()
            if not text or text.startswith("/"):
                return
            if text.startswith("[") and "]" in text[:48]:
                return
            key = f"discord:{message.author.id}"
            if _rate_limited(key):
                return
            author = (message.author.display_name or message.author.name or "Discord").strip()
            try:
                await asyncio.to_thread(
                    _publish_discord_message,
                    session_factory,
                    author,
                    text,
                    int(message.author.id),
                )
            except Exception as exc:
                log.warning("CrossChat Discord: inbound falhou: %s", exc)

        async def _poll_outbound(self) -> None:
            while not stop.is_set():
                try:
                    rows = await asyncio.to_thread(_fetch_game_messages, session_factory)
                    if rows:
                        ch = self._out_channel or await self._resolve_channel()
                        if ch is not None:
                            self._out_channel = ch
                            _channel_resolved = True
                            if _bridge_phase != "connected":
                                _set_phase("connected")
                        if ch is None:
                            log.warning(
                                "CrossChat Discord: canal %s indisponivel — mensagens retidas",
                                channel_id,
                            )
                        else:
                            max_id = _last_forward_id
                            sent_up_to = _last_forward_id
                            for msg_id, src, name, body in rows:
                                if msg_id <= _last_forward_id:
                                    continue
                                line = format_discord_outbound(src, name, body)
                                await ch.send(line[:1900])
                                if msg_id > max_id:
                                    max_id = msg_id
                                sent_up_to = msg_id
                            if sent_up_to > _last_forward_id:
                                await asyncio.to_thread(
                                    _advance_forward_cursor,
                                    load_settings,
                                    save_settings,
                                    sent_up_to,
                                )
                except discord.Forbidden as exc:
                    _set_phase("error", f"Sem permissao para enviar no canal: {exc}")
                    log.warning("CrossChat Discord: envio negado: %s", exc)
                except Exception as exc:
                    log.debug("CrossChat Discord: poll outbound falhou: %s", exc)
                await asyncio.sleep(_POLL_INTERVAL)

    async def _main() -> None:
        global _bridge_client
        client = BridgeClient()
        _bridge_client = client
        try:
            await client.start(_discord_token(load_settings))
        finally:
            await client.close()
            _bridge_client = None

    try:
        asyncio.run(_main())
    except discord.LoginFailure as exc:
        msg = f"Token Discord invalido ou expirado: {exc}"
        log.error("CrossChat Discord: %s", msg)
        _set_phase("error", msg)
    except Exception as exc:
        if not stop.is_set():
            msg = str(exc).strip() or exc.__class__.__name__
            log.error("CrossChat Discord: bridge encerrado: %s", exc)
            _set_phase("error", msg)
    finally:
        _client_ready = False
        _channel_resolved = False
        if stop.is_set():
            _set_phase("stopped")
        elif _bridge_phase == "connected":
            _set_phase("error", _bridge_error or "Conexao Discord encerrada")


def start_discord_bridge(
    *,
    session_factory: Callable[[], Any],
    load_settings: Callable[[], dict[str, Any]],
    save_settings: Callable[[dict[str, Any]], None],
    db_ready: Callable[[], bool],
) -> None:
    """Inicia thread daemon da ponte Discord (idempotente)."""
    global _bridge_thread

    with _bridge_lock:
        if _bridge_thread is not None and _bridge_thread.is_alive():
            return

        def _boot() -> None:
            _set_phase("waiting_db")
            for _ in range(120):
                if _bridge_stop.is_set():
                    _set_phase("stopped")
                    return
                if db_ready():
                    break
                time.sleep(1)
            if _bridge_stop.is_set():
                _set_phase("stopped")
                return
            if not db_ready():
                _set_phase("error", "Banco de dados indisponivel apos 120s — configure MySQL e reinicie")
                return
            cfg = load_discord_config(load_settings)
            if not cfg["enabled"]:
                _set_phase("idle")
                return
            _run_bridge(session_factory, load_settings, save_settings)

        _bridge_stop.clear()
        _bridge_thread = threading.Thread(
            target=_boot, name="cross-chat-discord", daemon=True
        )
        _bridge_thread.start()


def stop_discord_bridge() -> None:
    """Para a ponte Discord e aguarda encerramento da thread."""
    global _bridge_thread

    with _bridge_lock:
        _bridge_stop.set()
        _set_phase("stopped")
        thread = _bridge_thread
        _bridge_thread = None

    _close_bridge_client()
    if thread is not None and thread.is_alive():
        thread.join(timeout=10.0)
        if thread.is_alive():
            log.warning("CrossChat Discord: thread nao encerrou a tempo apos stop")


def _build_status_message(
    *,
    cfg: dict[str, Any],
    missing: list[str],
    db_ready: bool,
    alive: bool,
) -> str:
    if not cfg.get("requested_enabled"):
        return "Desativado"
    if missing:
        labels = {
            "enabled": "ativacao",
            "token": "token do bot",
            "channel_id": "ID do canal",
        }
        parts = [labels.get(m, m) for m in missing]
        return "Config incompleta: falta " + ", ".join(parts)
    if _discord_py_available is False:
        return "discord.py ausente — pip install discord.py ou rebuild ARKLAND-WebStore.exe"
    if not db_ready:
        return "Aguardando banco MySQL"
    if _bridge_error:
        return f"Erro: {_bridge_error}"
    if _bridge_phase == "connected" and _client_ready:
        if not _channel_resolved:
            return f"Conectado, mas canal {cfg.get('channel_id')} nao resolvido — confira ID e permissoes"
        return "Conectado e encaminhando mensagens"
    if _bridge_phase == "waiting_db":
        return "Aguardando banco MySQL..."
    if _bridge_phase == "starting":
        return "Conectando ao Discord..."
    if _bridge_phase == "stopped":
        return "Parado — salve a config ou reinicie o Web Store"
    if cfg["enabled"] and not alive:
        return "Bridge encerrado — salve novamente ou reinicie o ARKLAND-WebStore"
    if cfg["enabled"]:
        return "Aguardando conexao Discord..."
    return "Desativado"


def discord_bridge_status(
    load_settings: Callable[[], dict[str, Any]],
    db_ready: Callable[[], bool],
) -> dict[str, Any]:
    cfg = load_discord_config(load_settings)
    ready = db_ready()
    alive = _bridge_thread is not None and _bridge_thread.is_alive()
    s = load_settings()
    missing: list[str] = []
    if not s.get("cross_chat_discord_enabled"):
        missing.append("enabled")
    if not cfg.get("token_set"):
        missing.append("token")
    if not cfg.get("channel_id"):
        missing.append("channel_id")

    if _discord_py_available is None:
        _check_discord_py()

    connected = (
        cfg["enabled"]
        and alive
        and _bridge_phase == "connected"
        and _client_ready
        and _channel_resolved
        and not _bridge_error
    )
    status_message = _build_status_message(
        cfg=cfg, missing=missing, db_ready=ready, alive=alive
    )

    return {
        "enabled": cfg["enabled"],
        "requested_enabled": cfg.get("requested_enabled", False),
        "connected": connected,
        "phase": _bridge_phase,
        "status_message": status_message,
        "error": _bridge_error,
        "discord_py_available": bool(_discord_py_available),
        "client_ready": _client_ready,
        "channel_resolved": _channel_resolved,
        "thread_alive": alive,
        "channel_id": cfg["channel_id"] if cfg.get("channel_id") else 0,
        "token_set": cfg.get("token_set", False),
        "last_forward_id": _last_forward_id,
        "db_ready": ready,
        "missing": missing,
    }
