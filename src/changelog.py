"""Histórico de versões do ARKLAND.

Importa e combina entradas recentes e legadas.
"""
from .changelog_recent import CHANGELOG_RECENT
from .changelog_legacy import CHANGELOG_LEGACY

CHANGELOG = CHANGELOG_RECENT + CHANGELOG_LEGACY

__all__ = ["CHANGELOG"]
