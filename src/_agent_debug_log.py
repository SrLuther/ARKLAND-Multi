"""Debug-mode NDJSON logger (session 24417c). Remove after verified fix."""
from __future__ import annotations

import json
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
    # Dev machine (optional)
    paths.append(r"c:\Users\Ciano\Documents\arkland-multi\debug-24417c.log")
    return paths


def agent_dbg(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> None:
    payload = {
        "sessionId": "24417c",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    line = json.dumps(payload, ensure_ascii=False) + "\n"
    for path in _log_paths():
        try:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line)
        except Exception:
            pass
