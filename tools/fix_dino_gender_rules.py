"""Normaliza genero/neutered dos dinos no catalogo mestre."""
from __future__ import annotations

import json
from pathlib import Path

CONFIG = Path("docs/config.json")


def is_neutered_species(blueprint: str) -> bool:
    b = blueprint.lower()
    return "xenomorph" in b or "tekstrider" in b


def normalize_dino(dino: dict) -> None:
    if not isinstance(dino, dict) or not dino.get("Blueprint"):
        return
    level = int(dino.get("Level", 150))
    bp = str(dino["Blueprint"])
    if level == 1:
        if is_neutered_species(bp):
            dino["Neutered"] = True
            dino.pop("Gender", None)
        else:
            dino["Gender"] = "female"
            dino["Neutered"] = False
    else:
        dino.pop("Gender", None)
        dino["Neutered"] = False


def dedupe_non_lvl1_pairs(dinos: list) -> list:
    """Um dino por blueprint quando nivel != 1 (remove casal M/F)."""
    out: list = []
    seen: set[str] = set()
    for d in dinos:
        if not isinstance(d, dict):
            out.append(d)
            continue
        level = int(d.get("Level", 1))
        bp = str(d.get("Blueprint") or "")
        if level != 1 and bp:
            if bp in seen:
                continue
            seen.add(bp)
        out.append(d)
    return out


def walk_dinos(obj) -> int:
    changed = 0
    if isinstance(obj, dict):
        if "Dinos" in obj and isinstance(obj["Dinos"], list):
            before = len(obj["Dinos"])
            for d in obj["Dinos"]:
                if isinstance(d, dict):
                    normalize_dino(d)
                    changed += 1
            obj["Dinos"] = dedupe_non_lvl1_pairs(obj["Dinos"])
            if len(obj["Dinos"]) != before:
                changed += before - len(obj["Dinos"])
        for v in obj.values():
            changed += walk_dinos(v)
    elif isinstance(obj, list):
        for v in obj:
            changed += walk_dinos(v)
    return changed


def main() -> None:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    n = walk_dinos(data)
    CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Normalizados: {n} entradas Dinos (incl. dedup casais)")


if __name__ == "__main__":
    main()
