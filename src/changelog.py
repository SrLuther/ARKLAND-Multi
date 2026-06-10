"""Histórico de versões do ARKLAND.

Reexporta CHANGELOG de src/version.py (fonte única de verdade).
changelog_recent.py e changelog_legacy.py estão obsoletos.
"""
from .version import CHANGELOG

__all__ = ["CHANGELOG"]
