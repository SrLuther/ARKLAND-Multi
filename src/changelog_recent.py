"""OBSOLETO — use src/version.py (CHANGELOG) como fonte única.

Mantido apenas para evitar ImportError em código legado.
"""
from .version import CHANGELOG as CHANGELOG_RECENT

__all__ = ["CHANGELOG_RECENT"]
