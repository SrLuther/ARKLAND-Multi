"""Runner do bot embutido: ciclo de vida, auto-restart e classificação de erros (sem rede)."""
from __future__ import annotations

import asyncio
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.discord_bot import runner as runner_mod  # noqa: E402
from src.discord_bot.runner import (  # noqa: E402
    STATE_ERROR,
    STATE_STOPPED,
    EmbeddedBotRunner,
    RunnerStatus,
    describe_error,
)
from src.discord_bot.settings import BotSettings  # noqa: E402

FAKE_TOKEN = "fake.discord.token-for-tests"


def _settings(tmp_path, token=FAKE_TOKEN) -> BotSettings:
    return BotSettings(token=token, data_dir=tmp_path)


@pytest.fixture(autouse=True)
def _fake_discord_available(monkeypatch):
    """Permite testar sem discord.py instalado: start() só checa find_spec."""
    real = runner_mod.importlib.util.find_spec
    monkeypatch.setattr(
        runner_mod.importlib.util, "find_spec",
        lambda name, *a, **k: object() if name == "discord" else real(name, *a, **k),
    )


def _wait(pred, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


class LoginFailure(Exception):
    pass


class PrivilegedIntentsRequired(Exception):
    pass


class TestDescribeError:
    def test_fatal_errors(self):
        msg, fatal = describe_error(LoginFailure("Improper token"))
        assert fatal and "Token" in msg
        msg, fatal = describe_error(PrivilegedIntentsRequired())
        assert fatal and "Message Content Intent" in msg

    def test_transient_error(self):
        msg, fatal = describe_error(ConnectionError("rede caiu"))
        assert not fatal and "rede caiu" in msg

    def test_missing_dependency_is_fatal(self):
        assert describe_error(ModuleNotFoundError("No module named 'discord'"))[1] is True


class TestStartValidation:
    def test_requires_valid_token(self, tmp_path):
        r = EmbeddedBotRunner()
        ok, msg = r.start(_settings(tmp_path, token=""))
        assert not ok and "Token" in msg
        assert not r.is_running

    def test_requires_discord_library(self, tmp_path, monkeypatch):
        monkeypatch.setattr(runner_mod.importlib.util, "find_spec", lambda *a, **k: None)
        ok, msg = EmbeddedBotRunner().start(_settings(tmp_path))
        assert not ok and "discord.py" in msg

    def test_stop_when_not_running(self):
        ok, _ = EmbeddedBotRunner().stop()
        assert ok is False


class TestSupervisor:
    def test_start_stop_cycle(self, tmp_path, monkeypatch):
        started = {"n": 0}

        async def fake_run_once(self, settings):
            started["n"] += 1
            while not self._stop_requested.is_set():
                await asyncio.sleep(0.02)

        monkeypatch.setattr(EmbeddedBotRunner, "_run_once", fake_run_once)
        r = EmbeddedBotRunner()
        ok, _ = r.start(_settings(tmp_path))
        assert ok and _wait(lambda: started["n"] == 1)
        assert r.is_running and r.snapshot().running
        assert r.start(_settings(tmp_path))[0] is False  # já rodando
        ok, msg = r.stop(timeout=5)
        assert ok, msg
        assert not r.is_running
        assert r.snapshot().state == STATE_STOPPED

    def test_fatal_error_does_not_retry_even_with_auto_restart(self, tmp_path, monkeypatch):
        calls = {"n": 0}

        async def fake_run_once(self, settings):
            calls["n"] += 1
            raise LoginFailure("Improper token")

        monkeypatch.setattr(EmbeddedBotRunner, "_run_once", fake_run_once)
        r = EmbeddedBotRunner()
        r.start(_settings(tmp_path), auto_restart=True)
        assert _wait(lambda: not r.is_running)
        assert calls["n"] == 1
        st = r.snapshot()
        assert st.state == STATE_ERROR and "Token" in st.last_error

    def test_no_auto_restart_stops_after_crash(self, tmp_path, monkeypatch):
        calls = {"n": 0}

        async def fake_run_once(self, settings):
            calls["n"] += 1
            raise ConnectionError("caiu")

        monkeypatch.setattr(EmbeddedBotRunner, "_run_once", fake_run_once)
        r = EmbeddedBotRunner()
        r.start(_settings(tmp_path), auto_restart=False)
        assert _wait(lambda: not r.is_running)
        assert calls["n"] == 1

    def test_auto_restart_retries_then_stop(self, tmp_path, monkeypatch):
        calls = {"n": 0}

        async def fake_run_once(self, settings):
            calls["n"] += 1
            if calls["n"] < 3:
                raise ConnectionError("caiu")
            while not self._stop_requested.is_set():
                await asyncio.sleep(0.02)

        async def fast_sleep(self, seconds):
            await asyncio.sleep(0)

        monkeypatch.setattr(EmbeddedBotRunner, "_run_once", fake_run_once)
        monkeypatch.setattr(EmbeddedBotRunner, "_sleep_interruptible", fast_sleep)
        r = EmbeddedBotRunner()
        r.start(_settings(tmp_path), auto_restart=True)
        assert _wait(lambda: calls["n"] == 3)
        assert r.stop(timeout=5)[0]
        assert r.snapshot().restarts >= 2

    def test_auto_restart_gives_up_after_limit(self, tmp_path, monkeypatch):
        calls = {"n": 0}

        async def fake_run_once(self, settings):
            calls["n"] += 1
            raise ConnectionError("caiu")

        async def fast_sleep(self, seconds):
            await asyncio.sleep(0)

        monkeypatch.setattr(EmbeddedBotRunner, "_run_once", fake_run_once)
        monkeypatch.setattr(EmbeddedBotRunner, "_sleep_interruptible", fast_sleep)
        r = EmbeddedBotRunner()
        r.start(_settings(tmp_path), auto_restart=True)
        assert _wait(lambda: not r.is_running)
        assert calls["n"] == runner_mod.MAX_AUTO_RESTARTS + 1
        assert r.snapshot().state == STATE_ERROR

    def test_restart_flag_from_discord_command_restarts_without_auto_restart(self, tmp_path, monkeypatch):
        calls = {"n": 0}

        async def fake_run_once(self, settings):
            calls["n"] += 1
            if calls["n"] == 1:
                self._request_restart_flag()  # como o !restart do cog admin
                return
            while not self._stop_requested.is_set():
                await asyncio.sleep(0.02)

        async def fast_sleep(self, seconds):
            await asyncio.sleep(0)

        monkeypatch.setattr(EmbeddedBotRunner, "_run_once", fake_run_once)
        monkeypatch.setattr(EmbeddedBotRunner, "_sleep_interruptible", fast_sleep)
        r = EmbeddedBotRunner()
        r.start(_settings(tmp_path), auto_restart=False)
        assert _wait(lambda: calls["n"] == 2)
        r.stop(timeout=5)

    def test_shutdown_command_stops_without_restart(self, tmp_path, monkeypatch):
        calls = {"n": 0}

        async def fake_run_once(self, settings):
            calls["n"] += 1
            self._request_shutdown_flag()  # como o !shutdown
            return

        monkeypatch.setattr(EmbeddedBotRunner, "_run_once", fake_run_once)
        r = EmbeddedBotRunner()
        r.start(_settings(tmp_path), auto_restart=True)
        assert _wait(lambda: not r.is_running)
        assert calls["n"] == 1


class TestLogsAndStatus:
    def test_token_is_redacted_in_logs(self, tmp_path, monkeypatch):
        async def fake_run_once(self, settings):
            runner_mod.log.info("login com %s", FAKE_TOKEN)
            while not self._stop_requested.is_set():
                await asyncio.sleep(0.02)

        monkeypatch.setattr(EmbeddedBotRunner, "_run_once", fake_run_once)
        r = EmbeddedBotRunner()
        r.start(_settings(tmp_path))
        assert _wait(lambda: any("login com" in line for line in r.history()))
        r.stop(timeout=5)
        joined = "\n".join(r.history() + r.drain_logs())
        assert FAKE_TOKEN not in joined
        assert "***" in joined

    def test_status_summary(self):
        assert RunnerStatus().summary == "Parado"
        online = RunnerStatus(state="online", bot_user="Bobo#1", bot_id="9", guild_name="ARK", latency_ms=42.0)
        assert "Bobo#1" in online.summary and "42 ms" in online.summary
        assert "Erro" in RunnerStatus(state="error", last_error="falhou").summary
