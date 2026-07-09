#!/usr/bin/env python3
"""Marca espécies reportadas como needs_regeneration no manifest AI."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "plugin" / "arkshop_web" / "static" / "species" / "icons" / "generated" / "manifest.json"

QUEUE = [
    ("mosasaurus", "Muito magro; anatomia incorreta"),
    ("astrocetus", "Ícone ruim"),
    ("bloodstalker", "Ícone ruim"),
    ("castoroides", "Duas imagens (alias beaver consolidado)"),
    ("crystalwyvern", "Ícone ruim"),
    ("deinonychus", "Duas imagens (variante deinonychus_femea)"),
    ("doedicurus", "Duas imagens (alias doed consolidado)"),
    ("gacha", "Ícone ruim"),
    ("gasbags", "Ícone ruim"),
    ("giga", "Duas imagens giganotossauro (giga + gigant)"),
    ("megalosaurus", "Duas imagens (variantes _femea)"),
    ("phiomia", "Parece elefante"),
    ("rhynio", "Parece besouro de esterco (Rhinognatha)"),
    ("sinomacrops", "Ícone ruim"),
    ("tekstrider", "Ícone ruim (variante tekstrider_femea)"),
    ("xenomorph", "Duas imagens (variantes _femea)"),
]

VARIANT_NOTES = {
    "deinonychus_femea": "Sincronizar após deinonychus aprovado",
    "gigant": "Sincronizar após giga aprovado",
    "megalosaurus_femea": "Sincronizar após megalosaurus aprovado",
    "megalosaurus_aberrant_femea": "Sincronizar após megalosaurus aprovado",
    "tekstrider_femea": "Sincronizar após tekstrider aprovado",
    "xenomorph_femea": "Sincronizar após xenomorph aprovado",
    "xenomorphgen2_femea": "Sincronizar após xenomorph aprovado",
}


def main() -> int:
    now = datetime.now(timezone.utc).isoformat()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["regen_queue"] = [
        {"species_key": sk, "note": note, "status": "pending", "queued_at": now}
        for sk, note in QUEUE
    ]
    manifest["_reference_policy"] = (
        "User-provided reference per species via --reference; never cross-species anatomy copy"
    )

    for sk, note in QUEUE:
        entry = manifest.setdefault("icons", {}).get(sk) or {"species_key": sk}
        entry["status"] = "needs_regeneration"
        entry["regen_note"] = note
        entry["user_reported"] = True
        entry["marked_at"] = now
        manifest["icons"][sk] = entry

    for sk, note in VARIANT_NOTES.items():
        entry = manifest.setdefault("icons", {}).get(sk) or {"species_key": sk}
        entry["status"] = "needs_regeneration"
        entry["regen_note"] = note
        entry["sync_after_canonical"] = True
        entry["marked_at"] = now
        manifest["icons"][sk] = entry

    for alias, canonical in {"beaver": "castoroides", "doed": "doedicurus"}.items():
        if alias in manifest.get("icons", {}):
            manifest["icons"][alias]["status"] = "alias"
            manifest["icons"][alias]["canonical_species_key"] = canonical
            manifest["icons"][alias]["path"] = f"/species/icons/generated/{canonical}.webp"

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Marked {len(QUEUE)} canonical + {len(VARIANT_NOTES)} variants in {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
