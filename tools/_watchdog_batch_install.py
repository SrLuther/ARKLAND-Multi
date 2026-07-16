#!/usr/bin/env python3
"""Install any assets/*_bust.png that match still-missing species keys."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
ASSETS = Path(r"C:\Users\Ciano\.cursor\projects\c-Users-Ciano-Documents-arkland-multi\assets")

spec = importlib.util.spec_from_file_location("install", ROOT / "tools" / "_watchdog_install_icon.py")
inst = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inst)

# refresh gaps
import subprocess

subprocess.check_call([sys.executable, str(ROOT / "tools" / "_watchdog_gaps.py")], cwd=str(ROOT))
gaps = json.loads((ROOT / "tools" / "_watchdog_gaps.json").read_text(encoding="utf-8"))
missing = gaps.get("truly_missing") or {}

installed = []
for bust in sorted(ASSETS.glob("*_bust.png")):
    sk = bust.stem[: -len("_bust")]
    dest = ROOT / "plugin" / "arkshop_web" / "static" / "species" / "icons" / "generated" / f"{sk}.webp"
    if dest.is_file():
        continue
    if sk not in missing:
        # still install if file was generated for a known key
        pass
    meta = missing.get(sk) or {}
    dn = meta.get("display") or sk
    for junk in (
        " Fêmea Nível 1",
        " Femea Nivel 1",
        " Nível 1",
        " Nivel 1",
        " (SmallBosses)",
        " (Brighamia Creatures)",
        " (BigAL's Collection)",
    ):
        if junk in str(dn):
            dn = str(dn).split(junk)[0]
    tier = meta.get("tier") or "B"
    inst.install(sk, bust, display_name=dn, tier=tier)
    installed.append(sk)

print(f"BATCH_INSTALLED {len(installed)} {installed}")
