from __future__ import annotations
from datetime import datetime
from ..ui_constants import now_brasilia


def format_countdown(target: "datetime") -> str:
    """Formata o tempo restante até `target` como Xd Xh Xm Xs."""
    delta = target - now_brasilia()
    total = int(delta.total_seconds())
    if total <= 0:
        return "00s"
    d, rem = divmod(total, 86400)
    h, rem = divmod(rem, 3600)
    m, s   = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h or d:
        parts.append(f"{h:02d}h")
    if m or h or d:
        parts.append(f"{m:02d}m")
    parts.append(f"{s:02d}s")
    return " ".join(parts)

