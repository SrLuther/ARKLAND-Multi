"""Logging central do ARKLAND Server Manager + captura de exceções não tratadas.

Uso (o mais cedo possível no boot — ``main.py``/``app.py``/``app_tek.py``)::

    from src.diagnostics.logging_setup import setup_logging
    setup_logging(mode="tek")

Depois que a janela raiz existir::

    from src.diagnostics.logging_setup import install_tk_exception_hook, register_ui_notifier
    install_tk_exception_hook(root)
    register_ui_notifier(lambda msg: root.after(0, lambda: toast(root, msg, "warning")))

O arquivo ``%APPDATA%\\ARKLAND-ServerManager\\logs\\arkland.log`` roda (2 MB x 5) e
todas as linhas — inclusive tracebacks — passam pelo mascaramento de segredos.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import threading
import time
import traceback
import warnings
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from . import paths
from .redact import redact_text

LOG_MAX_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 5
LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | v%(app_version)s/%(app_mode)s | "
    "%(threadName)s | %(name)s:%(module)s:%(lineno)d | %(message)s"
)
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"

VALID_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")

# Bibliotecas ruidosas: nunca abaixo de WARNING.
_NOISY_LOGGERS = ("PIL", "urllib3", "asyncio", "matplotlib", "charset_normalizer",
                  "discord.gateway", "discord.http", "comtypes")

# Rate-limit do aviso na UI e deduplicação de tracebacks repetidos.
UI_NOTICE_MIN_INTERVAL_S = 30.0
DUP_FULL_TRACE_INTERVAL_S = 60.0

_UI_NOTICE_TEXT = (
    "Um erro inesperado foi registrado. Veja Diagnóstico › «Gerar diagnóstico» "
    "se o problema persistir."
)


def _app_version() -> str:
    try:
        from ..version import APP_VERSION
        return str(APP_VERSION)
    except Exception:  # noqa: BLE001
        return "?"


# ─────────────────────────────────────────────────────────────────────────────
# Handler / Formatter / Filters
# ─────────────────────────────────────────────────────────────────────────────

class RedactingFormatter(logging.Formatter):
    """Formata e mascara segredos na linha final (inclui traceback)."""

    def format(self, record: logging.LogRecord) -> str:
        return redact_text(super().format(record))


class RedactingFilter(logging.Filter):
    """Filtro que mascara ``record.msg`` (use em handlers que não usam o Formatter acima)."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact_text(record.getMessage())
            record.args = ()
        except Exception:  # noqa: BLE001
            pass
        return True


class AppContextFilter(logging.Filter):
    """Injeta ``app_version`` e ``app_mode`` em cada registro."""

    def __init__(self, mode: str = "?") -> None:
        super().__init__()
        self.mode = mode
        self.version = _app_version()

    def filter(self, record: logging.LogRecord) -> bool:
        record.app_version = self.version
        record.app_mode = self.mode
        return True


class SafeRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler que tolera falha de rotação no Windows (arquivo em uso)."""

    _ROLLOVER_BACKOFF_S = 60.0

    def __init__(self, *a: Any, **kw: Any) -> None:
        super().__init__(*a, **kw)
        self._next_rollover_try = 0.0

    def shouldRollover(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        if time.monotonic() < self._next_rollover_try:
            return False
        return bool(super().shouldRollover(record))

    def doRollover(self) -> None:
        try:
            super().doRollover()
        except OSError:
            self._next_rollover_try = time.monotonic() + self._ROLLOVER_BACKOFF_S
            try:
                if self.stream is None:
                    self.stream = self._open()
            except OSError:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# Estado global do módulo
# ─────────────────────────────────────────────────────────────────────────────

class _State:
    configured = False
    mode = "?"
    log_path: Optional[Path] = None
    file_handler: Optional[logging.Handler] = None
    console_handler: Optional[logging.Handler] = None
    context_filter: Optional[AppContextFilter] = None
    hooks_installed = False
    prev_excepthook: Any = None
    prev_threading_hook: Any = None
    prev_unraisable: Any = None
    asyncio_patched = False
    ui_notifier: Optional[Callable[[str], None]] = None
    last_ui_notice = 0.0
    seen: Dict[Tuple[str, str, str], Dict[str, float]] = {}
    lock = threading.RLock()


_S = _State


def normalize_level(level: Any) -> int:
    """Aceita 'DEBUG'/'info'/10… e devolve o número de nível do ``logging``."""
    if isinstance(level, int):
        return level
    name = str(level or "INFO").strip().upper()
    if name == "WARN":
        name = "WARNING"
    value = logging.getLevelName(name)
    return value if isinstance(value, int) else logging.INFO


def current_level_name() -> str:
    return logging.getLevelName(logging.getLogger().level)


def log_file() -> Optional[Path]:
    """Caminho do arquivo de log ativo (``None`` se o logging ainda não foi iniciado)."""
    return _S.log_path


def set_log_level(level: Any, *, persist: bool = True) -> str:
    """Muda o nível em tempo de execução (e grava em ``diagnostics.json``)."""
    num = normalize_level(level)
    name = logging.getLevelName(num)
    logging.getLogger().setLevel(num)
    if persist:
        try:
            paths.save_prefs(log_level=name)
        except Exception:  # noqa: BLE001
            logging.getLogger("arkland").warning("Não foi possível gravar o nível de log", exc_info=True)
    logging.getLogger("arkland").info("Nível de log alterado para %s", name)
    return name


def _has_console() -> bool:
    err = sys.stderr
    if err is None:
        return False
    try:
        return bool(err.isatty())
    except Exception:  # noqa: BLE001
        return False


def setup_logging(mode: str = "tek", *, level: Any = None, log_dir: Optional[Path] = None,
                  console: Optional[bool] = None, install_hooks: bool = True) -> Path:
    """Configura o logging central. Idempotente — chamar de novo só atualiza modo/nível.

    Devolve o caminho do ``arkland.log``.
    """
    with _S.lock:
        target_dir = Path(log_dir) if log_dir else paths.logs_dir()
        target = target_dir / paths.LOG_FILE_NAME
        if _S.configured and _S.log_path == target:
            _S.mode = mode
            if _S.context_filter is not None:
                _S.context_filter.mode = mode
            if level is not None:
                logging.getLogger().setLevel(normalize_level(level))
            return target
        if _S.configured:
            shutdown_logging(keep_hooks=True)

        if level is None:
            level = os.environ.get("ARKLAND_LOG_LEVEL") or paths.load_prefs().get("log_level") or "INFO"
        num = normalize_level(level)

        root = logging.getLogger()
        ctx = AppContextFilter(mode)
        fmt = RedactingFormatter(LOG_FORMAT, LOG_DATEFMT)

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            fh: Optional[logging.Handler] = SafeRotatingFileHandler(
                str(target), maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
        except OSError:
            fh = None  # pasta sem permissão: segue sem arquivo (não derruba o boot)
        if fh is not None:
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(fmt)
            fh.addFilter(ctx)
            root.addHandler(fh)
        want_console = _has_console() if console is None else bool(console)
        ch: Optional[logging.Handler] = None
        if want_console:
            ch = logging.StreamHandler(sys.stderr)
            ch.setLevel(logging.DEBUG)
            ch.setFormatter(fmt)
            ch.addFilter(ctx)
            root.addHandler(ch)

        root.setLevel(num)
        for noisy in _NOISY_LOGGERS:
            logging.getLogger(noisy).setLevel(max(logging.WARNING, num))

        _S.configured = True
        _S.mode = mode
        _S.log_path = target
        _S.file_handler = fh
        _S.console_handler = ch
        _S.context_filter = ctx

        if install_hooks:
            install_exception_hooks()
        logging.getLogger("arkland").info(
            "Logging iniciado: arquivo=%s nivel=%s modo=%s console=%s",
            target if fh is not None else "<indisponível>", logging.getLevelName(num), mode, bool(ch),
        )
        return target


def shutdown_logging(*, keep_hooks: bool = False) -> None:
    """Remove os handlers (usado em testes e em troca de pasta de logs)."""
    with _S.lock:
        root = logging.getLogger()
        for h in (_S.file_handler, _S.console_handler):
            if h is not None:
                try:
                    root.removeHandler(h)
                    h.close()
                except Exception:  # noqa: BLE001
                    pass
        _S.file_handler = None
        _S.console_handler = None
        _S.configured = False
        _S.log_path = None
        _S.context_filter = None
        if not keep_hooks:
            uninstall_exception_hooks()


def flush_logs() -> None:
    for h in (_S.file_handler, _S.console_handler):
        try:
            if h is not None:
                h.flush()
        except Exception:  # noqa: BLE001
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Captura de exceções não tratadas
# ─────────────────────────────────────────────────────────────────────────────

def register_ui_notifier(fn: Optional[Callable[[str], None]]) -> None:
    """Registra o callback que mostra o aviso discreto na UI (thread-safe a cargo do callback)."""
    _S.ui_notifier = fn


def _signature(exc_type: Any, exc: Any, tb: Any) -> Tuple[str, str, str]:
    where = ""
    try:
        frames = traceback.extract_tb(tb)
        if frames:
            last = frames[-1]
            where = f"{os.path.basename(last.filename)}:{last.lineno}"
    except Exception:  # noqa: BLE001
        pass
    name = getattr(exc_type, "__name__", str(exc_type))
    return (name, str(exc)[:200], where)


def handle_unhandled_exception(source: str, exc_type: Any, exc: Any, tb: Any) -> None:
    """Grava o traceback completo e avisa a UI (com rate-limit). Nunca lança."""
    try:
        sig = _signature(exc_type, exc, tb)
        now = time.monotonic()
        full = True
        with _S.lock:
            info = _S.seen.get(sig)
            if info is None:
                if len(_S.seen) > 200:
                    _S.seen.clear()
                _S.seen[sig] = {"last_full": now, "suppressed": 0.0}
            elif now - info["last_full"] < DUP_FULL_TRACE_INTERVAL_S:
                info["suppressed"] += 1
                full = False
            else:
                suppressed = int(info["suppressed"])
                info["last_full"] = now
                info["suppressed"] = 0.0
                if suppressed:
                    logging.getLogger("arkland").error(
                        "Exceção repetida %d vez(es) desde o último registro completo: %s: %s",
                        suppressed, sig[0], sig[1])
        logger = logging.getLogger("arkland.crash")
        if full:
            logger.critical("Exceção não tratada [%s]", source, exc_info=(exc_type, exc, tb))
        else:
            logger.error("Exceção repetida [%s] %s: %s (traceback omitido; já registrado)",
                         source, sig[0], sig[1])
        flush_logs()
        _maybe_notify_ui()
    except Exception:  # noqa: BLE001
        try:
            sys.__stderr__ and traceback.print_exception(exc_type, exc, tb, file=sys.__stderr__)
        except Exception:  # noqa: BLE001
            pass


def _maybe_notify_ui() -> None:
    notifier = _S.ui_notifier
    if notifier is None:
        return
    now = time.monotonic()
    with _S.lock:
        if _S.last_ui_notice and now - _S.last_ui_notice < UI_NOTICE_MIN_INTERVAL_S:
            return
        _S.last_ui_notice = now
    try:
        notifier(_UI_NOTICE_TEXT)
    except Exception:  # noqa: BLE001
        logging.getLogger("arkland").debug("Falha ao exibir aviso de erro na UI", exc_info=True)


def _sys_excepthook(exc_type: Any, exc: Any, tb: Any) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        prev = _S.prev_excepthook or sys.__excepthook__
        prev(exc_type, exc, tb)
        return
    handle_unhandled_exception("sys.excepthook", exc_type, exc, tb)


def _threading_excepthook(args: Any) -> None:
    if args.exc_type is SystemExit:
        return
    name = getattr(args.thread, "name", "?")
    handle_unhandled_exception(f"thread:{name}", args.exc_type, args.exc_value, args.exc_traceback)


def _unraisable_hook(unraisable: Any) -> None:
    if unraisable.exc_type is None:
        return
    handle_unhandled_exception(
        f"unraisable:{unraisable.err_msg or ''}".strip(":"),
        unraisable.exc_type, unraisable.exc_value, unraisable.exc_traceback)


def asyncio_exception_handler(loop: Any, context: Dict[str, Any]) -> None:
    """Handler para ``loop.set_exception_handler`` — grava traceback + contexto."""
    exc = context.get("exception")
    if exc is not None:
        handle_unhandled_exception("asyncio", type(exc), exc, exc.__traceback__)
    else:
        logging.getLogger("arkland.crash").error(
            "Erro asyncio sem exceção: %s", context.get("message", context))
        _maybe_notify_ui()


def install_asyncio_exception_handler(loop: Any) -> None:
    """Instala o handler em um loop específico."""
    try:
        loop.set_exception_handler(asyncio_exception_handler)
    except Exception:  # noqa: BLE001
        logging.getLogger("arkland").debug("Falha ao instalar handler asyncio", exc_info=True)


def _patch_asyncio_policy() -> None:
    """Todo loop criado depois (ex.: bot Discord embutido) nasce com o handler instalado."""
    if _S.asyncio_patched:
        return
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            policy = asyncio.get_event_loop_policy()
        cls = type(policy)
        original = cls.new_event_loop
        if getattr(original, "_arkland_patched", False):
            _S.asyncio_patched = True
            return

        def new_event_loop(self: Any) -> Any:  # noqa: ANN001
            loop = original(self)
            install_asyncio_exception_handler(loop)
            return loop

        new_event_loop._arkland_patched = True  # type: ignore[attr-defined]
        new_event_loop._arkland_original = original  # type: ignore[attr-defined]
        cls.new_event_loop = new_event_loop  # type: ignore[assignment]
        _S.asyncio_patched = True
    except Exception:  # noqa: BLE001
        logging.getLogger("arkland").debug("Não foi possível instrumentar o asyncio", exc_info=True)


def _unpatch_asyncio_policy() -> None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            cls = type(asyncio.get_event_loop_policy())
        cur = cls.new_event_loop
        orig = getattr(cur, "_arkland_original", None)
        if orig is not None:
            cls.new_event_loop = orig  # type: ignore[assignment]
    except Exception:  # noqa: BLE001
        pass
    _S.asyncio_patched = False


def install_exception_hooks() -> None:
    """Instala ``sys.excepthook``, ``threading.excepthook``, ``sys.unraisablehook`` e asyncio."""
    with _S.lock:
        if _S.hooks_installed:
            return
        _S.prev_excepthook = sys.excepthook
        _S.prev_threading_hook = getattr(threading, "excepthook", None)
        _S.prev_unraisable = getattr(sys, "unraisablehook", None)
        sys.excepthook = _sys_excepthook
        if hasattr(threading, "excepthook"):
            threading.excepthook = _threading_excepthook  # type: ignore[assignment]
        if hasattr(sys, "unraisablehook"):
            sys.unraisablehook = _unraisable_hook
        _patch_asyncio_policy()
        _S.hooks_installed = True


def uninstall_exception_hooks() -> None:
    with _S.lock:
        if not _S.hooks_installed:
            return
        if sys.excepthook is _sys_excepthook:
            sys.excepthook = _S.prev_excepthook or sys.__excepthook__
        if getattr(threading, "excepthook", None) is _threading_excepthook and _S.prev_threading_hook:
            threading.excepthook = _S.prev_threading_hook  # type: ignore[assignment]
        if getattr(sys, "unraisablehook", None) is _unraisable_hook and _S.prev_unraisable:
            sys.unraisablehook = _S.prev_unraisable
        _unpatch_asyncio_policy()
        _S.hooks_installed = False


def install_tk_exception_hook(root: Any) -> None:
    """Substitui ``report_callback_exception`` na janela raiz do Tk/CTk.

    O Tk chama ``root.report_callback_exception(exc, val, tb)`` quando um callback
    (botão, ``after``, bind…) falha; o padrão só imprime no stderr (invisível no .exe).
    """

    def report_callback_exception(exc: Any, val: Any, tb: Any) -> None:
        handle_unhandled_exception("tk", exc, val, tb)

    try:
        root.report_callback_exception = report_callback_exception
    except Exception:  # noqa: BLE001
        logging.getLogger("arkland").warning("Não foi possível instalar o hook do Tk", exc_info=True)


def make_toast_notifier(app: Any) -> Callable[[str], None]:
    """Notificador padrão: toast discreto via ``app.after`` (seguro entre threads)."""

    def _notify(message: str) -> None:
        def _show() -> None:
            try:
                from ..pages.toast import toast
                toast(app, message, "warning")
            except Exception:  # noqa: BLE001
                logging.getLogger("arkland").debug("toast indisponível", exc_info=True)

        try:
            app.after(0, _show)
        except Exception:  # noqa: BLE001
            pass

    return _notify


def attach_to_app(app: Any, mode: str) -> None:
    """Gancho único para os dois modos de UI: Tk hook + aviso na UI + evento de boot."""
    setup_logging(mode)
    install_tk_exception_hook(app)
    register_ui_notifier(make_toast_notifier(app))
    try:
        from .boot import log_boot_event
        log_boot_event(mode)
    except Exception:  # noqa: BLE001
        logging.getLogger("arkland").debug("log_boot_event falhou", exc_info=True)
