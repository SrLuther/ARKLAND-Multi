"""Compat: reexporta de src.permission_entitlements_sync."""
from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from src.permission_entitlements_sync import *  # noqa: F403, F401
