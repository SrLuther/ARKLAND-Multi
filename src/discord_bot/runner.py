"""Execução do bot embutido: thread com event loop asyncio dedicado, dentro do app.

Por que thread e não subprocesso?
  O app é empacotado com PyInstaller (``--onefile``): ``sys.executable`` aponta para o
  próprio ``ARKLAND-ServerManager.exe``, então ``python -m src.discord_bot`` não existe
  no EXE. Uma thread com loop próprio funciona igual em dev e empacotado, não exige
  Python externo e é encerrada junto com o app.

``discord`` só é importado dentro da thread (em ``bot.py``), quando o usuário inicia o bot.
"""
from __future__ import annotations

import asyncio
import importlib.util
import logging
import math
import os
import queue
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Tuple

from .settings import BotSettings, redact

log = logging.getLogger("arkland.obobonic")

STATE_STOPPED = "stopped"
STATE_STARTING = "starting"
STATE_ONLINE = "online"
STATE_STOPPING = "stopping"
STATE_RESTARTING = "restarting"
STATE_ERROR = "error"

MAX_AUTO_RESTARTS = 5
_STABLE_RUN_SECONDS = 60.0


def describe_error(exc: BaseException) -> Tuple[str, bool]:
    """Mensagem amigável (pt-BR) e se o erro é FATAL (não adianta tentar de novo)."""
    names = {c.__name__ for c in type(exc).__mro__}
    if "PrivilegedIntentsRequired" in names:
        return (
            "Intents privilegiadas não habilitadas. No Dev Portal → Bot, ative "
            "«Server Members Intent» e «Message Content Intent».",
            True,
        )
    if "LoginFailure" in names:
        return ("Token do bot rejeitado pelo Discord (inválido ou redefinido).", True)
    if "ModuleNotFoundError" in names or "ImportError" in names:
        return (f"Dependência ausente: {exc}", True)
    text = str(exc).strip() or type(exc).__name__
    return (f"{type(exc).__name__}: {text}", False)


@dataclass
class RunnerStatus:
    state: str = STATE_STOPPED
    bot_user: str = ""
    bot_id: str = ""
    guild_name: str = ""
    guild_count: int = 0
    latency_ms: Optional[float] = None
    last_error: str = ""
    started_at: Optional[float] = None
    restarts: int = 0

    @property
    def running(self) -> bool:
        return self.state in (STATE_STARTING, STATE_ONLINE, STATE_RESTARTING, STATE_STOPPING)

    @property
    def summary(self) -> str:
        if self.state == STATE_ONLINE:
            parts = []
            if self.bot_user:
                parts.append(f"Logado como {self.bot_user}")
            if self.bot_id:
                parts.append(f"ID {self.bot_id}")
            if self.guild_name:
                parts.append(f"Servidor «{self.guild_name}»")
            elif self.guild_count:
                parts.append(f"{self.guild_count} servidor(es)")
            if self.latency_ms is not None:
                parts.append(f"{self.latency_ms:.0f} ms")
            return " · ".join(parts) or "Online"
        if self.state == STATE_STARTING:
            return "Conectando ao Discord…"
        if self.state == STATE_RESTARTING:
            return "Reiniciando…"
        if self.state == STATE_STOPPING:
            return "Encerrando…"
        if self.last_error:
            return f"Erro: {self.last_error[:160]}"
        return "Parado"


class _QueueLogHandler(logging.Handler):
    """Envia logs do bot/discord.py para o painel (com o token redigido)."""

    def __init__(self, sink: "EmbeddedBotRunner", token: str) -> None:
        super().__init__(level=logging.INFO)
        self._sink = sink
        self._token = token

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            if record.exc_info and record.levelno >= logging.ERROR and record.exc_info[1] is not None:
                msg += f" ({type(record.exc_info[1]).__name__}: {record.exc_info[1]})"
            stamp = time.strftime("%H:%M:%S", time.localtime(record.created))
            prefix = "" if record.name.startswith("arkland") else f"[{record.name}] "
            level = f"{record.levelname}: " if record.levelno >= logging.WARNING else ""
            self._sink._push_log(redact(f"{stamp} {level}{prefix}{msg}", self._token))
        except Exception:
            pass


class EmbeddedBotRunner:
    """Controla o ciclo de vida do bot embutido (iniciar / parar / reiniciar)."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._bot = None  # type: ignore[var-annotated]
        self._settings: Optional[BotSettings] = None
        self._auto_restart = False
        self._stop_requested = threading.Event()
        self._restart_flag = False
        self._state = STATE_STOPPED
        self._bot_user = ""
        self._bot_id = ""
        self._guild_name = ""
        self._last_error = ""
        self._started_at: Optional[float] = None
        self._restarts = 0
        self._log_queue: "queue.Queue[str]" = queue.Queue()
        self._history: Deque[str] = deque(maxlen=800)

    # ── estado / logs ──────────────────────────────────────────────────────
    def _push_log(self, line: str) -> None:
        self._history.append(line)
        self._log_queue.put(line)

    def drain_logs(self) -> List[str]:
        lines: List[str] = []
        while True:
            try:
                lines.append(self._log_queue.get_nowait())
            except queue.Empty:
                break
        return lines

    def history(self) -> List[str]:
        return list(self._history)

    def _set_state(self, state: str) -> None:
        with self._lock:
            self._state = state

    @property
    def is_running(self) -> bool:
        t = self._thread
        return t is not None and t.is_alive()

    @property
    def auto_restart(self) -> bool:
        return self._auto_restart

    def set_auto_restart(self, enabled: bool) -> None:
        self._auto_restart = bool(enabled)

    def snapshot(self) -> RunnerStatus:
        with self._lock:
            state = self._state
            if state in (STATE_STARTING, STATE_ONLINE, STATE_RESTARTING, STATE_STOPPING) and not self.is_running:
                state = STATE_STOPPED if not self._last_error else STATE_ERROR
            st = RunnerStatus(
                state=state,
                bot_user=self._bot_user,
                bot_id=self._bot_id,
                guild_name=self._guild_name,
                last_error=self._last_error,
                started_at=self._started_at,
                restarts=self._restarts,
            )
        bot = self._bot
        if bot is not None and state == STATE_ONLINE:
            try:
                lat = float(bot.latency)
                if math.isfinite(lat):
                    st.latency_ms = lat * 1000.0
                st.guild_count = len(bot.guilds)
            except Exception:
                pass
        return st

    # ── API pública ────────────────────────────────────────────────────────
    def start(self, settings: BotSettings, *, auto_restart: bool = False) -> Tuple[bool, str]:
        """Inicia o bot (retorna logo; a conexão acontece na thread)."""
        with self._lock:
            if self.is_running:
                return False, "O bot já está em execução."
            problems = settings.problems()
            if problems:
                return False, problems[0]
            if importlib.util.find_spec("discord") is None:
                return False, (
                    "A biblioteca discord.py não está disponível nesta instalação. "
                    "Reinstale o app (ou rode: pip install discord.py)."
                )
            self._settings = settings
            self._auto_restart = bool(auto_restart)
            self._stop_requested.clear()
            self._restart_flag = False
            self._last_error = ""
            self._bot_user = self._bot_id = self._guild_name = ""
            self._started_at = None
            self._state = STATE_STARTING
            self._thread = threading.Thread(
                target=self._thread_main, name="ObobonicBot", daemon=True,
            )
            self._thread.start()
        return True, "Bot iniciando…"

    def stop(self, timeout: float = 12.0) -> Tuple[bool, str]:
        thread = self._thread
        if thread is None or not thread.is_alive():
            self._set_state(STATE_STOPPED)
            return False, "O bot não está em execução."
        self._stop_requested.set()
        self._set_state(STATE_STOPPING)
        self._close_bot_threadsafe()
        thread.join(timeout)
        if thread.is_alive():
            return False, "O bot não encerrou a tempo (ainda finalizando em segundo plano)."
        return True, "Bot parado."

    def restart(
        self, settings: BotSettings, *, auto_restart: bool = False, timeout: float = 12.0,
    ) -> Tuple[bool, str]:
        if self.is_running:
            ok, msg = self.stop(timeout=timeout)
            if not ok and self.is_running:
                return False, msg
        return self.start(settings, auto_restart=auto_restart)

    def shutdown(self) -> None:
        """Ao fechar o app: desliga o auto-restart e encerra o bot."""
        self._auto_restart = False
        if self.is_running:
            self.stop(timeout=6.0)

    # ── internos ───────────────────────────────────────────────────────────
    def _close_bot_threadsafe(self) -> None:
        loop, bot = self._loop, self._bot
        if loop is not None and bot is not None and not loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(bot.close(), loop)
            except Exception:
                pass

    def _request_restart_flag(self) -> None:
        self._restart_flag = True

    def _request_shutdown_flag(self) -> None:
        self._stop_requested.set()

    def _on_bot_ready(self, bot) -> None:  # type: ignore[no-untyped-def]
        user = getattr(bot, "user", None)
        with self._lock:
            self._bot_user = str(user) if user else ""
            self._bot_id = str(getattr(user, "id", "")) if user else ""
            guild = bot.get_guild(bot.settings.guild_id) if bot.settings.guild_id else None
            self._guild_name = guild.name if guild else ""
            self._started_at = time.time()
            self._state = STATE_ONLINE

    def _thread_main(self) -> None:
        settings = self._settings
        assert settings is not None
        handler = _QueueLogHandler(self, settings.token)
        watched = [logging.getLogger("arkland.obobonic"), logging.getLogger("discord")]
        for lg in watched:
            lg.addHandler(handler)
            if lg.level == logging.NOTSET or lg.level > logging.INFO:
                lg.setLevel(logging.INFO)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            try:
                import certifi  # type: ignore[import-not-found]
                os.environ.setdefault("SSL_CERT_FILE", certifi.where())
            except Exception:
                pass
            loop.run_until_complete(self._supervise(settings))
        except Exception as exc:
            msg, _fatal = describe_error(exc)
            with self._lock:
                self._last_error = msg
                self._state = STATE_ERROR
            log.error("Falha inesperada no bot embutido: %s", msg)
        finally:
            try:
                pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
                for t in pending:
                    t.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()
            self._loop = None
            self._bot = None
            with self._lock:
                if self._state != STATE_ERROR:
                    self._state = STATE_STOPPED
            log.info("Bot embutido encerrado.")
            for lg in watched:
                lg.removeHandler(handler)

    async def _sleep_interruptible(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end and not self._stop_requested.is_set():
            await asyncio.sleep(0.25)

    async def _supervise(self, settings: BotSettings) -> None:
        failures = 0
        while not self._stop_requested.is_set():
            self._restart_flag = False
            started = time.monotonic()
            fatal = False
            with self._lock:
                if self._state not in (STATE_STARTING, STATE_RESTARTING):
                    self._state = STATE_STARTING
            try:
                await self._run_once(settings)
            except Exception as exc:
                msg, fatal = describe_error(exc)
                with self._lock:
                    self._last_error = msg
                log.error("❌ %s", msg)

            if self._stop_requested.is_set():
                break
            if self._restart_flag:
                self._restarts += 1
                failures = 0
                self._set_state(STATE_RESTARTING)
                log.info("🔄 Reiniciando o bot…")
                await self._sleep_interruptible(1.0)
                continue
            if fatal:
                self._set_state(STATE_ERROR)
                break
            if not self._auto_restart:
                self._set_state(STATE_ERROR if self._last_error else STATE_STOPPED)
                break
            failures = 0 if (time.monotonic() - started) > _STABLE_RUN_SECONDS else failures + 1
            if failures > MAX_AUTO_RESTARTS:
                with self._lock:
                    self._last_error = (
                        self._last_error or "Bot encerrou repetidamente."
                    ) + " (reinício automático desistiu)"
                self._set_state(STATE_ERROR)
                log.error("⚠ Muitas falhas seguidas — reinício automático desativado.")
                break
            delay = min(3.0 * max(failures, 1), 30.0)
            self._restarts += 1
            self._set_state(STATE_RESTARTING)
            log.warning("⚠ Bot encerrou. Reinício automático em %.0fs…", delay)
            await self._sleep_interruptible(delay)

    async def _run_once(self, settings: BotSettings) -> None:
        from .bot import ObobonicBot  # importa discord.py só aqui

        bot = ObobonicBot(
            settings,
            on_ready_cb=self._on_bot_ready,
            on_restart=self._request_restart_flag,
            on_shutdown=self._request_shutdown_flag,
        )
        self._bot = bot
        try:
            if self._stop_requested.is_set():
                return
            async with bot:
                await bot.start(settings.token)
        finally:
            self._bot = None
