#!/usr/bin/env python3
"""Parse Itens Alfa.xlsx 'Cheats por Classe', diff vs config, create
kit_itensalfa_armas_* and kit_itensalfa_ferramentas_* per tier.

Uses same Permissions pattern as kit_itensalfa_{tier} (N + N+1 + Admins).
Prices: sum of individual item prices × (1 - discount) from kits_por_tier
(armas/ferramentas columns), with PRICE_MARKUP 1.15 like apply_itensalfa_licenses.
"""
from __future__ import annotations

import json
import re
import shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XLSX = Path(r"C:\Users\Ciano\Downloads\Itens Alfa.xlsx")
CONFIG = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"
BIN_CONFIG = ROOT / "plugin" / "CustomShop" / "bin" / "config.json"
BP_INDEX = ROOT / "tools" / "itensalfa_blueprints.json"

# Cluster ban: Criofreezer + Alfa Fabric never enter kits from the sheet.
# DENYLIST = path/class-name substrings (case-insensitive).
DENYLIST: frozenset[str] = frozenset(
    {
        # Alfa Fabric / Fabricator (ItensAlfa)
        "alfafabric",
        "alfa_fabric",
        "alfa fabric",
        "alfafabricator",
        "alfa_fabricator",
        # Criofreezer / Cryofreezer
        "criofreezer",
        "cryofreezer",
        "alfacriofreezer",
        "alfa_criofreezer",
        "alfa_cryofreezer",
    }
)
BP_DENYLIST_FRAGMENTS = DENYLIST  # alias

# Match apply_itensalfa_licenses
PRICE_MARKUP = 1.15
TIER_LADDER = [
    {"id": "delta", "group": "Delta", "label": "Delta", "sheet": "Delta"},
    {"id": "gamma", "group": "Gamma", "label": "Gamma", "sheet": "Gama"},
    {"id": "beta", "group": "Beta", "label": "Beta", "sheet": "Beta"},
    {"id": "alfa", "group": "Alfa", "label": "Alfa", "sheet": "Alfa"},
    {"id": "omega", "group": "Omega", "label": "Omega", "sheet": "Omega"},
    {"id": "transcendente", "group": "Transcendente", "label": "Transcendente", "sheet": "Transcendente"},
    {"id": "etereo", "group": "Etereo", "label": "Etéreo", "sheet": "Etereo"},
    {"id": "universal", "group": "Universal", "label": "Universal", "sheet": "Universal"},
    {"id": "onipotente", "group": "Onipotente", "label": "Onipotente", "sheet": "Onipotente"},
    {"id": "surreal", "group": "Surreal", "label": "Surreal", "sheet": "Surreal"},
    {"id": "imaterial", "group": "Imaterial", "label": "Imaterial", "sheet": "Imaterial"},
    {"id": "exotico", "group": "Exotico", "label": "Exótico", "sheet": "Exotico"},
]
# From itensalfa_kits_por_tier.csv (pre-markup sums)
KIT_PART_SUMS = {
    "delta": {"armas": 4200, "ferramentas": 1800, "discount": 0.20},
    "gamma": {"armas": 7000, "ferramentas": 3600, "discount": 0.20},
    "beta": {"armas": 11200, "ferramentas": 6300, "discount": 0.20},
    "alfa": {"armas": 18200, "ferramentas": 9000, "discount": 0.20},
    "omega": {"armas": 25200, "ferramentas": 12600, "discount": 0.20},
    "transcendente": {"armas": 36400, "ferramentas": 18000, "discount": 0.15},
    "etereo": {"armas": 50400, "ferramentas": 26100, "discount": 0.15},
    "universal": {"armas": 67200, "ferramentas": 34200, "discount": 0.15},
    "onipotente": {"armas": 88200, "ferramentas": 45000, "discount": 0.15},
    "surreal": {"armas": 113400, "ferramentas": 58500, "discount": 0.15},
    "imaterial": {"armas": 142800, "ferramentas": 73800, "discount": 0.15},
    "exotico": {"armas": 180600, "ferramentas": 92700, "discount": 0.15},
}

BP_RE = re.compile(
    r"Blueprint['\"](/Game/Mods/ItensAlfa/[^'\"]+)['\"]",
    re.IGNORECASE,
)
SEC_RE = re.compile(
    r"^(ARMADURA|ARMADURAS|ARMAS|FERRAMENTAS|SELAS)\s+(.+)$",
    re.IGNORECASE,
)

SHEET_TO_ID = {t["sheet"].lower(): t["id"] for t in TIER_LADDER}
SHEET_TO_ID.update({t["label"].lower(): t["id"] for t in TIER_LADDER})
SHEET_TO_ID.update({t["id"]: t["id"] for t in TIER_LADDER})
# Sheet aliases (accents stripped in _tier_id → keys below must be unaccented)
SHEET_TO_ID["eterea"] = "etereo"
SHEET_TO_ID["etérea"] = "etereo"
SHEET_TO_ID["etéreo"] = "etereo"
SHEET_TO_ID["eter"] = "etereo"
SHEET_TO_ID["exótico"] = "exotico"
# Planilha usa ONIPRESENTE (ferramentas) em vez de ONIPOTENTE
SHEET_TO_ID["onipresente"] = "onipotente"


def _norm_bp(raw: str) -> str:
    bp = raw.strip().replace("\\", "/")
    if bp.startswith("Game/"):
        bp = "/" + bp
    # strip class suffix duplication quirks
    return bp


def _is_denied_bp(bp: str) -> bool:
    """True if BP is Criofreezer / Alfa Fabric (banned from cluster kits)."""
    low = bp.lower().replace("\\", "/")
    return any(frag in low for frag in DENYLIST)


def _parse_sheet() -> dict[str, dict[str, list[str]]]:
    import openpyxl

    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb["Cheats por Classe"]
    data: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    section = None
    tier = None
    for row in ws.iter_rows(values_only=True):
        cell = row[0]
        if not cell or not isinstance(cell, str):
            continue
        cell = cell.strip()
        m = SEC_RE.match(cell)
        if m:
            kind = m.group(1).upper()
            if kind.startswith("ARMADURA"):
                kind = "ARMADURA"
            section = kind
            tier = m.group(2).strip()
            continue
        if not (cell.lower().startswith("cheat") and section and tier):
            continue
        # Blueprint'/path' or Blueprint"/path"
        bm = BP_RE.search(cell.replace("\\'", "'"))
        if not bm:
            bm2 = re.search(
                r"Blueprint'/Game/Mods/ItensAlfa/[^']+'",
                cell.replace("\\", ""),
            )
            if not bm2:
                continue
            bp = bm2.group(0)[len("Blueprint'") : -1]
        else:
            bp = bm.group(1)
        bp = _norm_bp(bp)
        if _is_denied_bp(bp):
            continue
        data[section][tier].append(bp)
    return data


def _tier_id(sheet_tier: str) -> str | None:
    key = sheet_tier.strip().lower()
    # strip accents roughly
    key = (
        key.replace("é", "e")
        .replace("ê", "e")
        .replace("ó", "o")
        .replace("á", "a")
    )
    return SHEET_TO_ID.get(key) or SHEET_TO_ID.get(sheet_tier.strip())


def _perms(tier_id: str) -> str:
    idx = next(i for i, t in enumerate(TIER_LADDER) if t["id"] == tier_id)
    groups = ["Admins", TIER_LADDER[idx]["group"]]
    if idx + 1 < len(TIER_LADDER):
        groups.append(TIER_LADDER[idx + 1]["group"])
    return ",".join(groups)


def _shop_price(base: int) -> int:
    return int(round(base * PRICE_MARKUP))


def _collect_config_bps(cfg: dict) -> set[str]:
    found: set[str] = set()
    for section in ("Items", "Kits"):
        for entry in (cfg.get(section) or {}).values():
            if not isinstance(entry, dict):
                continue
            if "Blueprint" in entry:
                found.add(_norm_bp(str(entry["Blueprint"])))
            for it in entry.get("Items") or []:
                if isinstance(it, dict) and it.get("Blueprint"):
                    found.add(_norm_bp(str(it["Blueprint"])))
    return found


def _kit_entry(bps: list[str], *, description: str, price: int, perms: str) -> dict:
    # Quality 100 for ItensAlfa gear (match selas pattern from changelog)
    # Name = short shop card title only (UI: Name || Description). No Âmbar/license prose.
    items = [
        {
            "Blueprint": bp,
            "Quantity": 1,
            "Quality": 100,
            "ForceBlueprint": False,
        }
        for bp in bps
    ]
    return {
        "DefaultAmount": 1,
        "Name": description,
        "Description": description,
        "KitDescription": description,
        "Price": price,
        "MinLevel": 0,
        "Permissions": perms,
        "Items": items,
    }


def main() -> None:
    if not XLSX.is_file():
        raise SystemExit(f"Excel not found: {XLSX}")

    sheet = _parse_sheet()
    print("=== Cheats por Classe counts ===")
    for sec, tiers in sheet.items():
        print(sec, {t: len(v) for t, v in tiers.items()})

    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    present = _collect_config_bps(cfg)

    missing: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for sec in ("ARMAS", "FERRAMENTAS", "ARMADURA"):
        for sheet_tier, bps in sheet.get(sec, {}).items():
            tid = _tier_id(sheet_tier)
            for bp in bps:
                if bp not in present:
                    missing[sec].append((sheet_tier, bp))

    print("\n=== Missing from config (not in any Item/Kit BP) ===")
    for sec, rows in missing.items():
        print(sec, len(rows))
        for st, bp in rows[:15]:
            print(" ", st, bp)
        if len(rows) > 15:
            print("  ...", len(rows) - 15, "more")

    kits = cfg.setdefault("Kits", {})
    created = []
    for kind, sec, price_key, label_pt in (
        ("armas", "ARMAS", "armas", "Armas"),
        ("ferramentas", "FERRAMENTAS", "ferramentas", "Ferramentas"),
    ):
        for t in TIER_LADDER:
            # find sheet tier key
            sheet_key = None
            for k in sheet.get(sec, {}):
                if _tier_id(k) == t["id"]:
                    sheet_key = k
                    break
            if not sheet_key:
                print(f"SKIP no sheet section for {kind} {t['id']}")
                continue
            bps = list(dict.fromkeys(sheet[sec][sheet_key]))  # unique preserve order
            bps = [bp for bp in bps if not _is_denied_bp(bp)]
            if not bps:
                continue
            sums = KIT_PART_SUMS[t["id"]]
            base = int(round(sums[price_key] * (1.0 - sums["discount"])))
            price = _shop_price(base)
            perms = _perms(t["id"])
            kit_id = f"kit_itensalfa_{kind}_{t['id']}"
            # Short shop label only (no blueprint counts / license prose)
            desc = f"KIT {label_pt.upper()} {t['id'].upper()}"
            kits[kit_id] = _kit_entry(bps, description=desc, price=price, perms=perms)
            # also ensure Permissions on reference full kit if present
            full_id = f"kit_itensalfa_{t['id']}"
            if full_id in kits and isinstance(kits[full_id], dict):
                kits[full_id]["Permissions"] = perms
            created.append((kit_id, len(bps), price, perms))

    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(CONFIG, BIN_CONFIG)

    print("\n=== Kits created/updated ===")
    for row in created:
        print(" ", row)

    # report vs blueprints index families
    if BP_INDEX.is_file():
        idx = json.loads(BP_INDEX.read_text(encoding="utf-8")).get("families") or {}
        print("\n=== BP index families", len(idx), "===")


if __name__ == "__main__":
    main()
