#!/usr/bin/env python3
"""Compose bust PNGs into generated/*.webp for all still-missing species."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "plugin" / "arkshop_web"))

spec = importlib.util.spec_from_file_location("compose", ROOT / "tools" / "_compose_dino_icon.py")
compose_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compose_mod)

STAGING = ROOT / "tools" / "_watchdog_staging"
RAW = ROOT / "plugin" / "arkshop_web" / "static" / "species" / "icons" / "generated" / "raw"
GEN = ROOT / "plugin" / "arkshop_web" / "static" / "species" / "icons" / "generated"
NEED = ROOT / "_inventory_need_create.json"
LOG = ROOT / "debug-24417c.log"
CURSOR_ASSETS = Path(r"C:\Users\Ciano\.cursor\projects\c-Users-Ciano-Documents-arkland-multi\assets")


def log(msg: str, data: dict) -> None:
    line = {
        "sessionId": "24417c",
        "hypothesisId": "WATCHDOG",
        "location": "tools/_watchdog_batch_compose.py",
        "message": msg,
        "data": data,
        "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
    }
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def find_bust(sk: str) -> Path | None:
    for d in (STAGING, RAW, CURSOR_ASSETS, ROOT / "assets"):
        for name in (f"{sk}_bust.png", f"{sk}.png"):
            p = d / name
            if p.is_file():
                return p
    return None


def main() -> int:
    if not NEED.is_file():
        print("missing _inventory_need_create.json — run _inventory_need_create.py first")
        return 1
    payload = json.loads(NEED.read_text(encoding="utf-8"))
    missing = payload.get("missing") or []
    installed = []
    skipped = []
    failed = []

    for entry in missing:
        sk = str(entry["species_key"]).lower()
        dest = GEN / f"{sk}.webp"
        if dest.is_file():
            skipped.append(sk)
            continue
        bust = find_bust(sk)
        if not bust:
            failed.append(sk)
            continue
        dn = str(entry.get("display_name") or sk)
        for junk in (
            " Fêmea Nível 1",
            " Femea Nivel 1",
            " Nível 1",
            " Nivel 1",
            " (SmallBosses)",
            " (Brighamia Creatures)",
            " (BigAL's Collection)",
        ):
            if junk in dn:
                dn = dn.split(junk)[0]
        try:
            compose_mod.process(sk, bust, display_name=dn)
            installed.append(sk)
            print(f"OK {sk}")
        except Exception as exc:
            failed.append(f"{sk}:{exc}")
            print(f"FAIL {sk}: {exc}")

    log(
        "batch compose",
        {"installed": installed, "skipped": len(skipped), "failed": failed, "installed_count": len(installed)},
    )
    print(f"INSTALLED {len(installed)} SKIPPED {len(skipped)} FAILED {len(failed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
