"""Column layout for the proportional, centered ASE notification.

Uses the baked Roboto51 HUD asset (Sansation Bold), including its negative
kerning before non-whitespace characters. TrueType/Slate metrics are different.
No font file or Pillow dependency is needed at runtime.
"""
from __future__ import annotations

import unicodedata

from chat_arkland_config import display_name
from chat_arkland_online_metrics import ADVANCES, KERNING

_WHITESPACE = frozenset('\t\n\v\f\r \x85\xa0')


def width(text: str) -> float:
    text = unicodedata.normalize('NFC', text)
    # FString is UTF-16; the non-remapped font uses the null glyph for unknowns.
    codes = text.encode('utf-16-le', errors='replace')
    chars = [chr(int.from_bytes(codes[i:i + 2], 'little')) for i in range(0, len(codes), 2)]
    return sum(ADVANCES.get(ord(char), ADVANCES[127]) +
        (KERNING if index + 1 < len(chars) and chars[index + 1] not in _WHITESPACE else 0)
        for index, char in enumerate(chars))


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
    columns = [("NOME", "name", 324), ("ID", "id", None)]
    if policy["ShowTribes"]:
        columns.append(("TRIBO", "tribe", 396))
    if show_map:
        columns.append(("MAPA", "map", 324))
    if policy["ShowOnlineTime"]:
        columns.append(("TEMPO", "time", None))
    rows = [[label for label, _, _ in columns]]
    for player in players:
        seconds = max(0, int((now - player["connected_at"]).total_seconds())) if player["connected_at"] else 0
        values = {"name": _cell(player["name"]), "id": str(player["public_id"]),
                  "tribe": _cell(player["tribe_name"]), "map": _cell(player["map"]),
                  "time": f"{seconds // 3600}h{seconds // 60 % 60:02d}m"}
        rows.append([_clip(values[key], maximum) if maximum else values[key] for _, key, maximum in columns])
    widths = [max(width(row[index]) for row in rows) for index in range(len(columns))]
    space, bar = ADVANCES[32], ADVANCES[ord('|')]
    base_widths = [width('  | '.join(row) + '  |') for row in rows]
    total = sum(widths) + len(columns) * (3 * space + 2 * KERNING + bar) - space - KERNING
    total += len(columns) * space  # Room for quantization without squeezing cells.
    layouts = []
    # Centering changes every column when the last field's width changes. Pick
    # whole-row widths first, then optimize the actual centered column stops.
    for total_phase in range(space):
        target_width = total + total_phase
        row_widths = [base + max(0, (target_width - base + space - 1) // space) * space for base in base_widths]
        lines = [''] * len(rows)
        spans = [(max(row_widths) - min(row_widths)) / 2]
        stop = 0
        valid = True
        for index, cell_width in enumerate(widths):
            prefixes = [line + row[index] for line, row in zip(lines, rows)]
            bases = [width(prefix) + KERNING for prefix in prefixes]
            stop += cell_width + 2 * space
            if index == len(columns) - 1:
                pads = [(size - base - bar) // space for size, base in zip(row_widths, bases)]
                if any(pad < 2 for pad in pads):
                    valid = False
                    break
            else:
                candidates = []
                for phase in range(space):
                    target = stop + phase - target_width / 2
                    pads = [max(2, round((target - base + size / 2) / space)) for base, size in zip(bases, row_widths)]
                    positions = [base + pad * space - size / 2 for base, pad, size in zip(bases, pads, row_widths)]
                    candidates.append((max(positions) - min(positions), phase, pads))
                span, phase, pads = min(candidates)
                spans.append(span)
                stop += phase
            lines = [prefix + ' ' * pad + '| ' for prefix, pad in zip(prefixes, pads)]
            stop += bar + space + KERNING
        if valid:
            layouts.append(((max(spans), sum(spans), max(row_widths)), [line.rstrip() for line in lines]))
    result = min(layouts, key=lambda entry: entry[0])[1]
    # Use ASCII: box-drawing Unicode is absent from the baked ASE HUD font.
    target = (min(map(width, result)) + max(map(width, result))) / 2
    dash_advance = ADVANCES[ord('-')] + KERNING
    rule = '-' * max(1, round((target + KERNING) / dash_advance))
    return [result[0], rule, *result[1:]]
