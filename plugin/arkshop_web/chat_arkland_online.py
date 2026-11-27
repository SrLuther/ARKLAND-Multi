"""Column layout for the proportional, centered ASE notification.

Advances are measured from the server's Engine/Content/Slate/Fonts/Roboto-Bold.ttf.
They approximate the stock client font; client/mod font changes require visual QA.
No font file or Pillow dependency is needed at runtime.
"""
from __future__ import annotations

import unicodedata

from chat_arkland_config import display_name
from chat_arkland_online_metrics import ADVANCES


def width(text: str) -> float:
    result = 0.0
    for char in text:
        if unicodedata.combining(char):
            continue
        result += ADVANCES.get(ord(char), 1000 if unicodedata.east_asian_width(char) in {"F", "W"} else 600)
    return result


def _cell(value) -> str:
    # Keep separators unambiguous; native Notice() still escapes all markup.
    return display_name(str(value or "")).replace("|", "/") or "--"


def _clip(text: str, maximum: float) -> str:
    if width(text) <= maximum:
        return text
    while text and width(text + "...") > maximum:
        text = text[:-1]
    return text.rstrip() + "..."


def online_table(players: list[dict], policy: dict, show_map: bool, now) -> list[str]:
    """Return equal-width rows; absolute stops avoid accumulating padding errors.

    Closing bars preserve the last column's padding when the client centers each
    line. Ordinary ljust()/tabs would align characters, not rendered glyphs.
    """
    columns = [("NOME", "name", 9000), ("ID", "id", None)]
    if policy["ShowTribes"]:
        columns.append(("TRIBO", "tribe", 11000))
    if show_map:
        columns.append(("MAPA", "map", 9000))
    if policy["ShowOnlineTime"]:
        columns.append(("TEMPO", "time", None))
    rows = [[label for label, _, _ in columns]]
    for player in players:
        seconds = max(0, int((now - player["connected_at"]).total_seconds())) if player["connected_at"] else 0
        values = {"name": _cell(player["name"]), "id": str(player["public_id"]),
                  "tribe": _cell(player["tribe_name"]), "map": _cell(player["map"]),
                  "time": f"{seconds // 3600}h{seconds // 60 % 60:02d}m"}
        rows.append([_clip(values[key], maximum) if maximum else values[key] for _, key, maximum in columns])
    widths = [max(width(row[index]) for row in rows) + ADVANCES[32] for index in range(len(columns))]
    result = []
    separator = " | "
    for row in rows:
        line, stop = "", 0.0
        for index, value in enumerate(row):
            line += value
            stop += widths[index]
            # Measure the entire prefix so rounding errors don't compound.
            line += " " * max(0, round((stop - width(line)) / ADVANCES[32]))
            line += separator
            stop += width(separator)
        result.append(line.rstrip())
    return result
