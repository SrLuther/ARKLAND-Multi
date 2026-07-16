"""Revert mistaken Permissions on license-kit dinos/pack10; keep ItensAlfa locks."""
from __future__ import annotations

import json
from pathlib import Path

WRONG_DINOS = {
    "armaedron_femea",
    "bionicgigant_femea",
    "bionicrex_femea",
    "carcha_femea",
    "desmodus_femea",
    "lionfish_femea",
    "therizinosaur",
    "carcha_femea_l200",
    "lionfish_femea_l200",
    "armaedron_femea_l200",
    "bionicgigant_femea_l200",
    "bionicrex_femea_l200",
    "desmodus_femea_l200",
    "therizinosaur_l200",
}
WRONG_KITS = {
    "armaedron_pack10",
    "bionicgigant_pack10",
    "bionicrex_pack10",
    "carcha_pack10",
    "desmodus_pack10",
    "lionfish_pack10",
    "therizinosaur_pack10",
}


def strip(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    removed: list[str] = []
    for section_name, keys in (("Items", WRONG_DINOS), ("Kits", WRONG_KITS)):
        section = data.get(section_name) or {}
        for key in keys:
            entry = section.get(key)
            if isinstance(entry, dict) and "Permissions" in entry:
                removed.append(f"{section_name}.{key}={entry.get('Permissions')}")
                del entry["Permissions"]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return removed


def main() -> None:
    for rel in (
        "plugin/CustomShop/configs/config.json",
        "plugin/CustomShop/bin/config.json",
    ):
        path = Path(rel)
        if not path.exists():
            print("missing", rel)
            continue
        removed = strip(path)
        print(rel, "removed", len(removed))
        for row in removed:
            print(" ", row)

    data = json.loads(Path("plugin/CustomShop/configs/config.json").read_text(encoding="utf-8"))
    items = data["Items"]
    kits = data["Kits"]
    dinos_locked = sum(
        1
        for _k, v in items.items()
        if isinstance(v, dict)
        and str(v.get("Type", "")).lower() == "dino"
        and str(v.get("Permissions") or "").strip()
    )
    itensalfa = sum(
        1
        for k, v in items.items()
        if isinstance(v, dict)
        and k.lower().startswith("itensalfa")
        and str(v.get("Permissions") or "").strip()
    )
    wrong_kits = sum(
        1 for k in WRONG_KITS if str((kits.get(k) or {}).get("Permissions") or "").strip()
    )
    print("dinos_locked", dinos_locked)
    print("itensalfa_with_perms", itensalfa)
    print("wrong_pack10_still_locked", wrong_kits)


if __name__ == "__main__":
    main()
