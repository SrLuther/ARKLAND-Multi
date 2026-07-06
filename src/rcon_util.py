"""Utilitários RCON compartilhados (TEK + Web Store)."""
from __future__ import annotations

# Comandos de reload do CustomShop — ordem de tentativa (plugin registra Shop.Reload).
CUSTOMSHOP_RELOAD_COMMANDS: tuple[str, ...] = (
    "Shop.Reload",
)

# Comandos de reload do CustomDinoDeliver (plugin registra DinoDeliver.Reload).
CUSTOMDINO_RELOAD_COMMANDS: tuple[str, ...] = (
    "DinoDeliver.Reload",
)


def sanitize_rcon_password(password: str | None) -> str:
    """Remove sufixo corrompido ?ServerPassword= que o engine ARK pode gravar no INI."""
    raw = str(password or "").strip()
    if not raw:
        return ""
    idx = raw.find("?ServerPassword=")
    if idx >= 0:
        raw = raw[:idx].strip()
    return raw
