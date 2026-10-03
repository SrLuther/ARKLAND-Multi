"""Eventos de domínio de diagnóstico (``diag_event``) e decorator ``diag_call``.

Cada evento vira UMA linha no ``arkland.log`` (logger ``arkland.diag``) no formato::

    [categoria] mensagem | chave=valor chave2=valor2

Valores passam pelo mascaramento de segredos (chaves ``*password*``, ``*token*`` etc.).
Os últimos eventos também ficam num buffer em memória, incluído no pacote de diagnóstico.
Nunca lança exceção — diagnóstico não pode derrubar o app.
"""
from __future__ import annotations

import functools
import logging
import threading
import time
from collections import deque
from datetime import datetime
from typing import Any, Callable, Deque, Dict, List, Optional

from .redact import redact_obj, redact_text

DIAG_LOGGER_NAME = "arkland.diag"

# Categorias padronizadas (livres, mas estas são usadas pelos fluxos principais).
CAT_BOOT = "boot"
CAT_SAVE = "salvar"
CAT_INI = "ini"
CAT_SERVER = "servidor"
CAT_MODS = "mods"
CAT_PLUGINS = "plugins"
CAT_WEBSTORE = "webstore"
CAT_CONFIG = "config"
CAT_DIAG = "diagnostico"

_MAX_EVENTS = 400
_MAX_VALUE_LEN = 300
_events: Deque[Dict[str, Any]] = deque(maxlen=_MAX_EVENTS)
_events_lock = threading.Lock()


def _fmt_value(value: Any) -> str:
    try:
        if isinstance(value, str):
            text = value
        else:
            text = repr(value)
    except Exception:  # noqa: BLE001
        text = "<?>"
    text = text.replace("\n", "\\n").replace("\r", "")
    if len(text) > _MAX_VALUE_LEN:
        text = text[:_MAX_VALUE_LEN] + "…"
    if " " in text or not text:
        text = '"' + text.replace('"', "'") + '"'
    return text


def diag_event(category: str, message: str = "", *, _level: int = logging.INFO,
               **fields: Any) -> None:
    """Registra um evento de domínio no log e no buffer em memória."""
    try:
        safe_fields = redact_obj(fields)
        safe_msg = redact_text(message)
        entry = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "category": str(category),
            "message": safe_msg,
            "fields": safe_fields,
        }
        with _events_lock:
            _events.append(entry)
        tail = " ".join(f"{k}={_fmt_value(v)}" for k, v in safe_fields.items())
        line = f"[{category}] {safe_msg}" + (f" | {tail}" if tail else "")
        logging.getLogger(DIAG_LOGGER_NAME).log(_level, "%s", line)
    except Exception:  # noqa: BLE001
        pass


def recent_events(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Cópia dos últimos eventos (mais antigos primeiro)."""
    with _events_lock:
        items = list(_events)
    return items[-limit:] if limit else items


def clear_events() -> None:
    with _events_lock:
        _events.clear()


def wrap_done(category: str, label: str, on_done: Optional[Callable[[bool], None]],
              **fields: Any) -> Callable[[bool], None]:
    """Embrulha um callback ``on_done(success)``: registra início agora e o resultado depois.

    Usado em operações assíncronas (SteamCMD: mods/servidor) sem alterar o contrato original.
    """
    t0 = time.perf_counter()
    diag_event(category, f"{label} iniciado", **fields)

    def _done(success: bool) -> None:
        diag_event(category, f"{label} {'concluído' if success else 'FALHOU'}",
                   _level=logging.INFO if success else logging.WARNING,
                   elapsed_s=round(time.perf_counter() - t0, 1), **fields)
        if on_done is not None:
            on_done(success)

    return _done


def diag_call(category: str, label: str,
              summarize: Optional[Callable[[tuple, dict, Any], Dict[str, Any]]] = None
              ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator: registra início/fim/duração e, em falha, o traceback completo.

    A exceção é **re-lançada** (comportamento original preservado); o decorator apenas
    garante que ela fique no log com contexto.
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                try:
                    logging.getLogger(DIAG_LOGGER_NAME).exception(
                        "[%s] %s FALHOU após %.0f ms", category, label,
                        (time.perf_counter() - t0) * 1000.0,
                    )
                    diag_event(category, f"{label} FALHOU", _level=logging.ERROR,
                               error=f"{type(exc).__name__}: {exc}")
                except Exception:  # noqa: BLE001
                    pass
                raise
            try:
                extra: Dict[str, Any] = {}
                if summarize is not None:
                    try:
                        extra = dict(summarize(args, kwargs, result) or {})
                    except Exception as sexc:  # noqa: BLE001
                        extra = {"summary_error": f"{type(sexc).__name__}: {sexc}"}
                diag_event(category, f"{label} ok",
                           elapsed_ms=round((time.perf_counter() - t0) * 1000.0), **extra)
            except Exception:  # noqa: BLE001
                pass
            return result

        return wrapper

    return decorator
