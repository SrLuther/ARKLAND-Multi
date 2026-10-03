"""Debug-mode logger (session 24417c) — compatível com os chamadores existentes.

``agent_dbg`` agora encaminha cada ponto de instrumentação para o log central
(``arkland.log``, categoria ``debug``) via ``diag_event`` — já mascarado e com rotação.

O arquivo NDJSON avulso (``debug-24417c.log``) só é escrito se a variável de ambiente
``ARKLAND_AGENT_DEBUG_FILE=1`` estiver definida, e apenas em ``%TEMP%`` / ``%APPDATA%``
(sem caminhos fixos da máquina do desenvolvedor).
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any


def _log_paths() -> list[str]:
    paths: list[str] = []
    tmp = os.environ.get("TEMP") or os.environ.get("TMP")
    if tmp:
        paths.append(os.path.join(tmp, "debug-24417c.log"))
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths.append(str(Path(appdata) / "ARKLAND-ServerManager" / "debug-24417c.log"))
    return paths


def _file_enabled() -> bool:
    return os.environ.get("ARKLAND_AGENT_DEBUG_FILE", "").strip().lower() in ("1", "true", "yes", "on")


def agent_dbg(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> None:
    # 1) Log central (sempre) — nunca levanta exceção.
    try:
        from .diagnostics.events import diag_event
        diag_event("debug", message, _level=logging.DEBUG, hypothesis=hypothesis_id,
                   location=location, data=data or {})
    except Exception:  # noqa: BLE001
        pass

    # 2) Arquivo NDJSON legado (opt-in).
    if not _file_enabled():
        return
    payload = {
        "sessionId": "24417c",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    line = json.dumps(payload, ensure_ascii=False, default=str) + "\n"
    for path in _log_paths():
        try:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            logging.getLogger("arkland").debug("agent_dbg: falha ao gravar %s", path, exc_info=True)
