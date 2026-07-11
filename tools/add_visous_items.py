"""Deprecado: VisousMod removido. Use apply_itensalfa_licenses.py."""
from __future__ import annotations

import sys


def main() -> int:
    print(
        "add_visous_items.py está obsoleto — VisousMod foi removido do catálogo.\n"
        "Use: python tools/apply_itensalfa_licenses.py\n"
        "BPs: tools/itensalfa_blueprints.json (fonte: Itens Alfa.xlsx)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
