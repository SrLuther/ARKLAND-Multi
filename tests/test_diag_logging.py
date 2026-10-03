"""Logging central + captura de exceções (src/diagnostics/logging_setup.py)."""
from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time

import pytest

from src.diagnostics import events, logging_setup as ls
from src.diagnostics.redact import REDACTED


@pytest.fixture()
def log_env(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.delenv("ARKLAND_LOG_LEVEL", raising=False)
    root = logging.getLogger()
    prev_level = root.level
    prev_hook = sys.excepthook
    prev_thread_hook = threading.excepthook
    ls.shutdown_logging()
    ls._S.seen.clear()
    ls._S.last_ui_notice = 0.0
    ls.register_ui_notifier(None)
    events.clear_events()
    yield tmp_path / "logs"
    ls.shutdown_logging()
    ls.register_ui_notifier(None)
    root.setLevel(prev_level)
    sys.excepthook = prev_hook
    threading.excepthook = prev_thread_hook


def _text(path):
    for h in logging.getLogger().handlers:
        h.flush()
    return path.read_text(encoding="utf-8")


def test_setup_creates_file_with_rotation_and_format(log_env):
    path = ls.setup_logging("tek", log_dir=log_env, console=False)
    assert path == log_env / "arkland.log" and path.exists()
    handler = ls._S.file_handler
    assert isinstance(handler, ls.SafeRotatingFileHandler)
    assert handler.maxBytes == 2 * 1024 * 1024 and handler.backupCount == 5
    logging.getLogger("arkland.teste").warning("olá mundo")
    text = _text(path)
    assert "| WARNING  |" in text and "/tek" in text and "olá mundo" in text
    assert threading.current_thread().name in text


def test_setup_is_idempotent(log_env):
    ls.setup_logging("tek", log_dir=log_env, console=False)
    n = len(logging.getLogger().handlers)
    ls.setup_logging("classic", log_dir=log_env, console=False)
    assert len(logging.getLogger().handlers) == n
    assert ls._S.mode == "classic"


def test_secrets_masked_in_log_lines_and_tracebacks(log_env):
    path = ls.setup_logging("tek", log_dir=log_env, console=False)
    log = logging.getLogger("arkland.secret")
    log.info("conectando com ServerAdminPassword=MinhaSenha123 e token=abcdef123456")
    log.info("webhook https://discord.com/api/webhooks/1234567890/ABCdef-ghi_JKL")
    try:
        raise RuntimeError("falha api_key=SUPERSECRETKEY")
    except RuntimeError:
        log.exception("erro")
    text = _text(path)
    for leaked in ("MinhaSenha123", "abcdef123456", "ABCdef-ghi_JKL", "SUPERSECRETKEY"):
        assert leaked not in text, leaked
    assert REDACTED in text and "Traceback" in text


def test_level_from_prefs_env_and_runtime_change(log_env, monkeypatch):
    from src.diagnostics import paths
    paths.save_prefs(log_level="DEBUG")
    ls.setup_logging("tek", log_dir=log_env, console=False)
    assert logging.getLogger().level == logging.DEBUG
    assert ls.set_log_level("warning") == "WARNING"
    assert paths.load_prefs()["log_level"] == "WARNING"
    logging.getLogger("arkland.t").info("não deve aparecer")
    logging.getLogger("arkland.t").warning("deve aparecer")
    text = _text(log_env / "arkland.log")
    assert "não deve aparecer" not in text and "deve aparecer" in text


def test_console_handler_only_when_requested(log_env):
    ls.setup_logging("tek", log_dir=log_env, console=False)
    assert ls._S.console_handler is None
    ls.shutdown_logging()
    ls.setup_logging("tek", log_dir=log_env, console=True)
    assert ls._S.console_handler is not None


def test_hooks_installed_and_restored(log_env):
    before = sys.excepthook
    ls.setup_logging("tek", log_dir=log_env, console=False)
    assert sys.excepthook is ls._sys_excepthook and threading.excepthook is ls._threading_excepthook
    ls.shutdown_logging()
    assert sys.excepthook is before


def test_sys_excepthook_logs_full_traceback(log_env):
    path = ls.setup_logging("tek", log_dir=log_env, console=False)
    try:
        raise ValueError("boom principal")
    except ValueError:
        sys.excepthook(*sys.exc_info())
    text = _text(path)
    assert "Exceção não tratada [sys.excepthook]" in text
    assert "ValueError: boom principal" in text and "Traceback" in text


def test_thread_exception_is_captured(log_env):
    path = ls.setup_logging("tek", log_dir=log_env, console=False)

    def worker():
        raise KeyError("falha-na-thread")

    t = threading.Thread(target=worker, name="worker-diag")
    t.start()
    t.join()
    text = _text(path)
    assert "[thread:worker-diag]" in text and "KeyError" in text and "falha-na-thread" in text


def test_tk_callback_hook_and_ui_notice_rate_limit(log_env):
    path = ls.setup_logging("tek", log_dir=log_env, console=False)
    notices = []
    ls.register_ui_notifier(notices.append)

    class FakeRoot:
        pass

    root = FakeRoot()
    ls.install_tk_exception_hook(root)
    for i in range(3):
        try:
            raise RuntimeError(f"erro tk {i}")
        except RuntimeError:
            root.report_callback_exception(*sys.exc_info())
    assert len(notices) == 1                     # rate-limit: 1 aviso, sem popup em loop
    text = _text(path)
    assert text.count("Exceção não tratada [tk]") == 3
    # depois do intervalo, avisa de novo
    ls._S.last_ui_notice -= ls.UI_NOTICE_MIN_INTERVAL_S + 1
    try:
        raise RuntimeError("outro")
    except RuntimeError:
        root.report_callback_exception(*sys.exc_info())
    assert len(notices) == 2


def test_repeated_identical_exception_traceback_deduped(log_env):
    path = ls.setup_logging("tek", log_dir=log_env, console=False)

    def boom():
        raise RuntimeError("mesma falha")

    for _ in range(5):
        try:
            boom()
        except RuntimeError:
            ls.handle_unhandled_exception("tk", *sys.exc_info())
    text = _text(path)
    assert text.count("Exceção não tratada [tk]") == 1
    assert text.count("Exceção repetida [tk]") == 4


def test_asyncio_handler_installed_on_new_loops(log_env):
    path = ls.setup_logging("tek", log_dir=log_env, console=False)
    loop = asyncio.new_event_loop()
    try:
        assert loop.get_exception_handler() is ls.asyncio_exception_handler
        loop.call_soon(lambda: (_ for _ in ()).throw(ZeroDivisionError("async-boom")))
        loop.call_soon(loop.stop)
        loop.run_forever()
    finally:
        loop.close()
    text = _text(path)
    assert "[asyncio]" in text and "async-boom" in text


def test_diag_event_logged_masked_and_buffered(log_env):
    path = ls.setup_logging("tek", log_dir=log_env, console=False)
    events.diag_event("salvar", "Perfil salvo", server="Ilha", admin_password="TopSecret99", ramp_lines=120)
    text = _text(path)
    assert "[salvar] Perfil salvo" in text and "ramp_lines=120" in text and "server=Ilha" in text
    assert "TopSecret99" not in text
    last = events.recent_events()[-1]
    assert last["category"] == "salvar" and last["fields"]["admin_password"] == REDACTED


def test_diag_call_logs_success_and_reraises_failure(log_env):
    path = ls.setup_logging("tek", log_dir=log_env, console=False)

    @events.diag_call("ini", "write_ini", summarize=lambda a, k, r: {"n": r})
    def ok_fn():
        return 7

    @events.diag_call("ini", "write_ini")
    def bad_fn():
        raise OSError("disco cheio")

    assert ok_fn() == 7
    with pytest.raises(OSError):
        bad_fn()
    text = _text(path)
    assert "write_ini ok" in text and "n=7" in text
    assert "write_ini FALHOU" in text and "disco cheio" in text and "Traceback" in text


def test_rollover_failure_does_not_break_logging(log_env, monkeypatch):
    path = ls.setup_logging("tek", log_dir=log_env, console=False)
    handler = ls._S.file_handler
    handler.maxBytes = 200
    import logging.handlers as lh

    def fail(self):
        raise PermissionError("arquivo em uso")

    monkeypatch.setattr(lh.RotatingFileHandler, "doRollover", fail)
    for i in range(10):
        logging.getLogger("arkland.rot").warning("linha longa %d %s", i, "x" * 100)
    assert "linha longa 9" in _text(path)
