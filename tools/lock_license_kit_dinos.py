#!/usr/bin/env python3
"""DEPRECATED — do NOT run.

Wrong approach used in v1.10.44: locked dinos/pack10 that share BPs with
kit_gamma/beta/alfa. Product intent is only ItensAlfa shop items (already
have Permissions). Revert via tools/revert_wrong_dino_permissions.py.
"""
from __future__ import annotations

import sys


def main() -> int:
    print(
        "DEPRECATED: this script wrongly locked kit dinos/pack10.\n"
        "ItensAlfa items already have Permissions; do not re-run.\n"
        "Use tools/revert_wrong_dino_permissions.py if locks reappear.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
