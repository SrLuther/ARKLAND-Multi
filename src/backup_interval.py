"""Utilitários para intervalos de backup (formato HH:MM)."""
from __future__ import annotations


def parse_interval_seconds(value: str, *, default: int = 3600) -> int:
    """Converte 'HH:MM' ou horas inteiras em segundos."""
    raw = (value or "").strip()
    if not raw:
        return default
    if ":" in raw:
        parts = raw.split(":", 1)
        try:
            hours = int(parts[0].strip())
            minutes = int(parts[1].strip())
            return max(60, hours * 3600 + minutes * 60)
        except ValueError:
            return default
    try:
        return max(60, int(raw) * 3600)
    except ValueError:
        return default
