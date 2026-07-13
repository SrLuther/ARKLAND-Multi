"""Parser do TribeLog.log (formato ARK SE) — compartilhado entre poller e ingestão.

Formato típico:
  Day 123, 14:30:15: JogadorX was added to the Tribe by JogadorY!
"""
from __future__ import annotations

import re
from typing import Any

_LINE_RE = re.compile(
    r"^Day\s+(?P<day>\d+),\s+(?P<time>[\d:]+):\s+(?P<body>.+)$",
    re.IGNORECASE,
)

# Ordem importa: primeiro match ganha.
_EVENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("killed", re.compile(r"\bkilled\b|\bdestroyed\b", re.I)),
    ("structure", re.compile(r"\bstructure\b|\bbuilt\b|\bplaced\b", re.I)),
    ("tamed", re.compile(r"\btamed\b|\btaming\b", re.I)),
    ("admin", re.compile(r"\bAdmin Command\b|\badminchat\b", re.I)),
    ("player", re.compile(
        r"\bjoined\b|\bleft\b|\bdied\b|\badded to the Tribe\b|\bremoved from the Tribe\b",
        re.I,
    )),
]

EVENT_TYPES = ("killed", "structure", "tamed", "admin", "player", "other")

EVENT_COLORS = {
    "killed": "#ef4444",
    "structure": "#f59e0b",
    "tamed": "#22c55e",
    "admin": "#a855f7",
    "player": "#38bdf8",
    "other": "#94a3b8",
}


def classify_event(text: str) -> str:
    """Classifica o tipo de evento a partir do corpo ou da linha completa."""
    for etype, pattern in _EVENT_PATTERNS:
        if pattern.search(text or ""):
            return etype
    return "other"


def parse_tribe_log_line(raw: str, *, file_offset: int = 0) -> dict[str, Any] | None:
    """Parseia uma linha do TribeLog.log.

    Retorna dict com day_number, event_time, event_type, raw_line, body, file_offset
    ou None se a linha estiver vazia.
    """
    line = (raw or "").rstrip("\r\n")
    if not line.strip():
        return None

    m = _LINE_RE.match(line)
    if m:
        body = m.group("body")
        etype = classify_event(body)
        return {
            "day_number": int(m.group("day")),
            "event_time": m.group("time"),
            "event_type": etype,
            "body": body,
            "raw_line": line,
            "file_offset": int(file_offset or 0),
        }

    etype = classify_event(line)
    return {
        "day_number": None,
        "event_time": None,
        "event_type": etype,
        "body": line,
        "raw_line": line,
        "file_offset": int(file_offset or 0),
    }


def parse_tribe_log_chunk(
    text: str,
    *,
    base_offset: int = 0,
) -> list[dict[str, Any]]:
    """Parseia um bloco de texto (várias linhas) com offsets cumulativos."""
    if not text:
        return []
    out: list[dict[str, Any]] = []
    pos = int(base_offset or 0)
    # Normaliza newlines sem perder contagem de bytes (approx UTF-8 = 1 byte ASCII logs)
    parts = text.splitlines(keepends=True)
    for part in parts:
        raw = part.rstrip("\r\n")
        parsed = parse_tribe_log_line(raw, file_offset=pos)
        pos += len(part.encode("utf-8", errors="replace"))
        if parsed:
            out.append(parsed)
    return out
