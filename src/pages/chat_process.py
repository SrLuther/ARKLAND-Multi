from __future__ import annotations
from typing import TYPE_CHECKING
import datetime
import re
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def chat_process(app: "ARKServerManagerApp", server_id: str, raw: str) -> None:
    import re
    from datetime import datetime
    ts = datetime.now().strftime("%H:%M:%S")
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line or line.lower() == "no chat":
            continue
        # SERVER: message
        m = re.match(r"^SERVER:\s*(.+)$", line, re.IGNORECASE)
        if m:
            app._chat_append(server_id, f"[{ts}] ", "ts")
            app._chat_append(server_id, "[SERVIDOR]", "server")
            app._chat_append(server_id, f": {m.group(1)}\n", "message")
            continue
        # PlayerName (SteamID64): message  or  PlayerName: message
        m = re.match(r"^(.+?)(?:\s+\(\d{17}\))?:\s*(.+)$", line)
        if m:
            app._chat_append(server_id, f"[{ts}] ", "ts")
            app._chat_append(server_id, m.group(1).strip(), "player")
            app._chat_append(server_id, f": {m.group(2).strip()}\n", "message")
        else:
            app._chat_append(server_id, f"[{ts}] {line}\n", "message")

