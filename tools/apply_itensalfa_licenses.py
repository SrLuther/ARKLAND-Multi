#!/usr/bin/env python3
"""Aplica licenças ItensAlfa (Delta→Exótico) no config CustomShop.

Idempotente: reexecutar atualiza preços/descrições/gates sem duplicar IDs.
BPs: tools/itensalfa_blueprints.json + tools/itensalfa_creatures.json
     (extraídos de Itens Alfa.xlsx — nunca inventa).
Fontes preços: docs/LICENCAS_PRECOS_PROPOSTA.md, tools/itensalfa_kits_por_tier.csv,
               tools/itensalfa_precos_proposta.csv

Uso:
  python tools/apply_itensalfa_licenses.py
  python tools/apply_itensalfa_licenses.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"
BIN_CONFIG = ROOT / "plugin" / "CustomShop" / "bin" / "config.json"
BP_INDEX = ROOT / "tools" / "itensalfa_blueprints.json"
CREATURES_INDEX = ROOT / "tools" / "itensalfa_creatures.json"

# Ordem da escada (grupo Permissions). Gama → Gamma (legado produção).
TIER_LADDER: list[dict] = [
    {"id": "delta", "group": "Delta", "label": "Delta", "sheet": "Delta", "price": 6000, "bonus": 5, "access": "apenas tier Delta"},
    {"id": "gamma", "group": "Gamma", "label": "Gamma", "sheet": "Gama", "price": 50000, "bonus": 25, "access": "Gama + Delta"},
    {"id": "beta", "group": "Beta", "label": "Beta", "sheet": "Beta", "price": 75000, "bonus": 50, "access": "Beta + Gama"},
    {"id": "alfa", "group": "Alfa", "label": "Alfa", "sheet": "Alfa", "price": 100000, "bonus": 75, "access": "Alfa + Beta"},
    {"id": "omega", "group": "Omega", "label": "Omega", "sheet": "Omega", "price": 115000, "bonus": 90, "access": "Omega + Alfa"},
    {"id": "transcendente", "group": "Transcendente", "label": "Transcendente", "sheet": "Transcendente", "price": 130000, "bonus": 105, "access": "Transcendente + Omega"},
    {"id": "etereo", "group": "Etereo", "label": "Etéreo", "sheet": "Etereo", "price": 150000, "bonus": 120, "access": "Etéreo + Transcendente"},
    {"id": "universal", "group": "Universal", "label": "Universal", "sheet": "Universal", "price": 165000, "bonus": 135, "access": "Universal + Etéreo"},
    {"id": "onipotente", "group": "Onipotente", "label": "Onipotente", "sheet": "Onipotente", "price": 180000, "bonus": 150, "access": "Onipotente + Universal"},
    {"id": "surreal", "group": "Surreal", "label": "Surreal", "sheet": "Surreal", "price": 195000, "bonus": 165, "access": "Surreal + Onipotente"},
    {"id": "imaterial", "group": "Imaterial", "label": "Imaterial", "sheet": "Imaterial", "price": 215000, "bonus": 180, "access": "Imaterial + Surreal"},
    {"id": "exotico", "group": "Exotico", "label": "Exótico", "sheet": "Exotico", "price": 230000, "bonus": 200, "access": "Exótico + Imaterial"},
]

ITEM_PRICES: dict[str, dict[str, int]] = {
    "delta": {"armor_piece": 400, "weapon": 300, "tool": 200, "armor_set": 2000},
    "gamma": {"armor_piece": 700, "weapon": 500, "tool": 400, "armor_set": 3500},
    "beta": {"armor_piece": 1100, "weapon": 800, "tool": 700, "armor_set": 5500},
    "alfa": {"armor_piece": 1700, "weapon": 1300, "tool": 1000, "armor_set": 8500},
    "omega": {"armor_piece": 2400, "weapon": 1800, "tool": 1400, "armor_set": 12000},
    "transcendente": {"armor_piece": 3400, "weapon": 2600, "tool": 2000, "armor_set": 17000},
    "etereo": {"armor_piece": 4800, "weapon": 3600, "tool": 2900, "armor_set": 24000},
    "universal": {"armor_piece": 6400, "weapon": 4800, "tool": 3800, "armor_set": 32000},
    "onipotente": {"armor_piece": 8400, "weapon": 6300, "tool": 5000, "armor_set": 42000},
    "surreal": {"armor_piece": 10800, "weapon": 8100, "tool": 6500, "armor_set": 54000},
    "imaterial": {"armor_piece": 13600, "weapon": 10200, "tool": 8200, "armor_set": 68000},
    "exotico": {"armor_piece": 17200, "weapon": 12900, "tool": 10300, "armor_set": 86000},
}

KIT_IA_PRICES: dict[str, int] = {
    "delta": 8600,
    "gamma": 14600,
    "beta": 24000,
    "alfa": 37000,
    "omega": 51600,
    "transcendente": 60700,
    "etereo": 85400,
    "universal": 113400,
    "onipotente": 149000,
    "surreal": 192000,
    "imaterial": 242000,
    "exotico": 305400,
}

# prefix shop → (família BP index, label, category, price_key)
ITEM_MAP = [
    ("arco_tek", "TekBow", "Arco Tek ItensAlfa", "Armas", "weapon"),
    ("escopeta", "PumpAction", "Escopeta ItensAlfa", "Armas", "weapon"),
    ("foice", "Sickle", "Foice ItensAlfa", "Ferramentas", "tool"),
    ("machado", "Hatched", "Machado ItensAlfa", "Ferramentas", "tool"),
    ("motosserra", "Chainsaw", "Motosserra ItensAlfa", "Ferramentas", "tool"),
    ("picareta", "Pick", "Picareta ItensAlfa", "Ferramentas", "tool"),
]

ARMOR_FAMILIES = ("TekHelmet", "TekShirtNew", "TekGloves", "TekPants", "TekBoots")

# Preço Â âncora (proposta §5.6 / CSV) no tier de referência da família.
# Mek ausente na proposta — âncora por craft vs Exo-Mek (1.5× Alfa).
CREATURE_PRICE_ANCHOR: dict[str, tuple[int, str]] = {
    "HOVERSKIFF": (15000, "alfa"),
    "HOVERSAIL": (12000, "alfa"),
    "EXO-MEK": (20000, "alfa"),
    "MEK": (30000, "alfa"),
    "ENFORCER": (8000, "alfa"),
    "DEFENDER": (8000, "alfa"),
    "STRYDER": (25000, "alfa"),
    "SUBMARINE": (18000, "alfa"),
}

# Labels de planilha → id da escada (Comum/Minimega não são grupos Permissions).
CREATURE_TIER_ALIAS: dict[str, str] = {
    "Gama": "gamma",
    "Comum": "delta",
    "Minimega": "omega",
}

# Stryder: só PerfectPVE; Alfa/Universal/PerfectPVP ficam de fora do catálogo.
STRYDER_SHOP_TIER = "PerfectPVE"


def _load_bp_index() -> dict[str, dict[str, str]]:
    raw = json.loads(BP_INDEX.read_text(encoding="utf-8"))
    return raw.get("families") or raw


def _load_creatures() -> list[dict]:
    if not CREATURES_INDEX.is_file():
        return []
    raw = json.loads(CREATURES_INDEX.read_text(encoding="utf-8"))
    return list(raw.get("creatures") or [])


def _tier_index_by_id(tier_id: str) -> int:
    for i, t in enumerate(TIER_LADDER):
        if t["id"] == tier_id:
            return i
    raise KeyError(tier_id)


def _resolve_creature_tier_id(sheet_tier: str) -> str | None:
    if sheet_tier in CREATURE_TIER_ALIAS:
        return CREATURE_TIER_ALIAS[sheet_tier]
    for t in TIER_LADDER:
        if t["sheet"] == sheet_tier or t["label"] == sheet_tier or t["group"] == sheet_tier:
            return t["id"]
        if t["id"] == sheet_tier.lower():
            return t["id"]
    return None


def _perms_for_tier_index(idx: int) -> str:
    groups = ["Admins", TIER_LADDER[idx]["group"]]
    if idx + 1 < len(TIER_LADDER):
        groups.append(TIER_LADDER[idx + 1]["group"])
    return ",".join(groups)


def _perms_all_license_tiers() -> str:
    """Delta→Exótico + Admins. Sem keyvault/Nuvem."""
    return "Admins," + ",".join(t["group"] for t in TIER_LADDER)


def _creature_price(family: str, tier_id: str) -> int:
    anchor_price, anchor_tier = CREATURE_PRICE_ANCHOR[family]
    ref = ITEM_PRICES[anchor_tier]["armor_set"]
    scale = ITEM_PRICES[tier_id]["armor_set"] / ref
    raw = anchor_price * scale
    return max(100, int(round(raw / 100.0) * 100))


def _creature_shop_key(family: str, sheet_tier: str) -> str:
    fam = family.lower().replace("-", "").replace(" ", "")
    tier = sheet_tier.lower().replace(" ", "")
    return f"itensalfa_{fam}_{tier}"


def _creature_display_name(family: str, sheet_tier: str, tier_id: str) -> str:
    fam_names = {
        "HOVERSKIFF": "HoverSkiff",
        "HOVERSAIL": "HoverSail",
        "EXO-MEK": "Exo-Mek",
        "MEK": "Mek",
        "ENFORCER": "Enforcer",
        "DEFENDER": "Defender",
        "SUBMARINE": "Submarine",
        "STRYDER": "Stryder",
    }
    fam = fam_names.get(family, family.title())
    if sheet_tier in ("Comum", "Minimega", "PerfectPVE", "PerfectPVP"):
        display = sheet_tier
    elif sheet_tier == "Gama":
        display = "Gamma"
    else:
        display = next(t["label"] for t in TIER_LADDER if t["id"] == tier_id)
    return f"{fam} {display} ItensAlfa (1x)"


def _creature_item(
    *,
    family: str,
    sheet_tier: str,
    bp: str,
    tier_id: str,
    idx: int,
    special_stryder: bool,
) -> dict:
    if special_stryder:
        name = "Stryder PerfectPVE ItensAlfa (1x)"
        desc = (
            "Stryder PerfectPVE (ItensAlfa) — resgatável com qualquer licença "
            "Delta→Exótico (Nuvem/keyvault não conta)."
        )
        perms = _perms_all_license_tiers()
        price = int(CREATURE_PRICE_ANCHOR["STRYDER"][0])
    else:
        name = _creature_display_name(family, sheet_tier, tier_id)
        desc = (
            f"{name} — gate N+N−1 (próprio tier + um acima). "
            "Licença Nuvem/keyvault não desbloqueia."
        )
        perms = _perms_for_tier_index(idx)
        price = _creature_price(family, tier_id)

    return {
        "Category": "ItensAlfa — Criaturas",
        "Description": desc,
        "ForceBlueprint": False,
        "Items": [_bp_entry(bp)],
        "Name": name,
        "Permissions": perms,
        "Price": price,
        "Quality": 0,
        "Type": "item",
    }


def _license_entry(tier: dict, *, renewal: bool = False) -> dict:
    price = int(tier["price"])
    if renewal:
        price = int(round(price * 0.80))
    total = 25 + int(tier["bonus"])
    if renewal:
        name = (
            f"Renovação Licença {tier['label']} (30 dias) — −20% "
            f"(requer {tier['label']} ativa) — {total} Âmbar / 30 min"
        )
        desc = (
            f"Renovação antecipada Licença {tier['label']} (30 dias) — 20% de desconto. "
            f"Requer licença {tier['label']} ainda ativa. Acesso: {tier['access']}."
        )
    else:
        warn = ""
        if tier["id"] == "delta":
            warn = " ATENÇÃO: desbloqueia APENAS o tier Delta (sem tier abaixo)."
        name = (
            f"Licença {tier['label']} (30 dias) — {total} Âmbar a cada 30 min online"
        )
        desc = (
            f"Licença {tier['label']} (30 dias) — Acesso: {tier['access']}.{warn} "
            f"Bônus +{tier['bonus']} Âmbar / 30 min (total {total} com Default)."
        )
    entry: dict = {
        "Category": "Licenças",
        "Description": desc,
        "ForceBlueprint": False,
        "LicenseGrant": {
            "Days": 30,
            "Group": tier["group"],
            "Redeemable": True,
        },
        "Name": name,
        "Price": price,
        "Quality": 0,
        "TimedPointsBonus": int(tier["bonus"]),
        "Type": "license",
    }
    if renewal:
        entry["Permissions"] = f"Admins,{tier['group']}"
    return entry


def _bp_entry(bp: str) -> dict:
    return {"Blueprint": bp, "Quantity": 1, "Quality": 0, "ForceBlueprint": False}


def _weapon_item(label: str, category: str, price_key: str, bp: str, tier: dict, idx: int) -> dict:
    prices = ITEM_PRICES[tier["id"]]
    name = f"{label} {tier['label']} (1x)"
    return {
        "Category": category,
        "Description": name,
        "ForceBlueprint": False,
        "Items": [_bp_entry(bp)],
        "Name": name,
        "Permissions": _perms_for_tier_index(idx),
        "Price": int(prices[price_key]),
        "Quality": 0,
        "Type": "item",
    }


def _armor_item(bps: list[str], tier: dict, idx: int) -> dict:
    prices = ITEM_PRICES[tier["id"]]
    name = f"Armadura TEK ItensAlfa {tier['label']} (5 peças)"
    return {
        "Category": "ItensAlfa — Armaduras",
        "Description": name,
        "ForceBlueprint": False,
        "Items": [_bp_entry(bp) for bp in bps],
        "Name": name,
        "Permissions": _perms_for_tier_index(idx),
        "Price": int(prices["armor_set"]),
        "Quality": 0,
        "Type": "item",
    }


def _kit_itensalfa(tier: dict, idx: int, item_bps: list[str]) -> dict:
    n = len(item_bps)
    return {
        "DefaultAmount": 1,
        "Description": (
            f"Kit ItensAlfa {tier['label']} — {n} blueprints ItensAlfa do tier "
            f"(armadura TEK + armas/ferramentas mapeadas). Licença: próprio ou um acima."
        ),
        "Items": [_bp_entry(bp) for bp in item_bps],
        "Name": f"Kit ItensAlfa {tier['label']}",
        "Permissions": _perms_for_tier_index(idx),
        "Price": int(KIT_IA_PRICES[tier["id"]]),
        "Type": "kit",
    }


def _armor_bps(index: dict, sheet: str) -> list[str] | None:
    bps = []
    for fam in ARMOR_FAMILIES:
        bp = (index.get(fam) or {}).get(sheet)
        if not bp:
            return None
        bps.append(bp)
    return bps


def _collect_tier_bps(index: dict, tier: dict) -> list[str]:
    sheet = tier["sheet"]
    bps: list[str] = []
    for _prefix, fam, _label, _cat, _pk in ITEM_MAP:
        bp = (index.get(fam) or {}).get(sheet)
        if bp:
            bps.append(bp)
    armor = _armor_bps(index, sheet)
    if armor:
        bps.extend(armor)
    return bps


def _apply_creatures(items: dict, stats: dict[str, int]) -> None:
    """Upsert criaturas/veículos ItensAlfa; Stryder só PerfectPVE."""
    wanted_keys: set[str] = set()
    for row in _load_creatures():
        family = str(row.get("family") or "").strip().upper()
        sheet_tier = str(row.get("tier") or "").strip()
        bp = str(row.get("blueprint") or "").strip()
        if not family or not sheet_tier or not bp:
            stats["creatures_skipped"] += 1
            continue

        if family == "STRYDER":
            if sheet_tier != STRYDER_SHOP_TIER:
                stats["stryder_variants_excluded"] += 1
                continue
            key = _creature_shop_key(family, sheet_tier)
            # PerfectPVE: perms Delta→Exótico; tier_id só para preço âncora
            items[key] = _creature_item(
                family=family,
                sheet_tier=sheet_tier,
                bp=bp,
                tier_id="alfa",
                idx=0,
                special_stryder=True,
            )
            wanted_keys.add(key)
            stats["creatures_upserted"] += 1
            continue

        tier_id = _resolve_creature_tier_id(sheet_tier)
        if tier_id is None:
            stats["creatures_skipped"] += 1
            print(f"  SKIP creature (tier desconhecido): {family} {sheet_tier}")
            continue
        if family not in CREATURE_PRICE_ANCHOR:
            stats["creatures_skipped"] += 1
            print(f"  SKIP creature (sem preço âncora): {family} {sheet_tier}")
            continue

        idx = _tier_index_by_id(tier_id)
        key = _creature_shop_key(family, sheet_tier)
        items[key] = _creature_item(
            family=family,
            sheet_tier=sheet_tier,
            bp=bp,
            tier_id=tier_id,
            idx=idx,
            special_stryder=False,
        )
        wanted_keys.add(key)
        stats["creatures_upserted"] += 1

    # Remover variantes Stryder ItensAlfa que não sejam PerfectPVE
    for key in list(items.keys()):
        if not key.startswith("itensalfa_stryder_"):
            continue
        if key not in wanted_keys:
            del items[key]
            stats["stryder_variants_removed"] += 1


def apply_config(data: dict, index: dict) -> dict[str, int]:
    stats = {
        "licenses": 0,
        "renewals": 0,
        "items_upserted": 0,
        "items_skipped_no_bp": 0,
        "kits_upserted": 0,
        "timed_groups": 0,
        "legacy_kit_gates": 0,
        "visous_keys_removed": 0,
        "creatures_upserted": 0,
        "creatures_skipped": 0,
        "stryder_variants_excluded": 0,
        "stryder_variants_removed": 0,
    }
    items = data.setdefault("Items", {})
    kits = data.setdefault("Kits", {})

    # Remover quaisquer chaves Visous residuais
    for key in list(items.keys()):
        if key.startswith("visous_") or "VISOUSMod" in json.dumps(items[key], ensure_ascii=False):
            del items[key]
            stats["visous_keys_removed"] += 1

    tpr = data.setdefault("TimedPointsReward", {})
    groups = tpr.setdefault("Groups", {})
    for tier in TIER_LADDER:
        groups[tier["group"]] = {"Amount": int(tier["bonus"])}
        stats["timed_groups"] += 1
    groups.setdefault("Default", {"Amount": 25})
    groups.setdefault("Moderacao", {"Amount": 500})
    groups.setdefault("STAFF", {"Amount": 1000})

    for tier in TIER_LADDER:
        lid = f"licenca_{tier['id']}"
        rid = f"licenca_{tier['id']}_renovacao"
        items[lid] = _license_entry(tier, renewal=False)
        items[rid] = _license_entry(tier, renewal=True)
        stats["licenses"] += 1
        stats["renewals"] += 1

    for idx, tier in enumerate(TIER_LADDER):
        sheet = tier["sheet"]
        for prefix, fam, label, category, price_key in ITEM_MAP:
            key = f"{prefix}_{tier['id']}"
            bp = (index.get(fam) or {}).get(sheet)
            if not bp:
                # Ex.: armas Exótico ausentes na planilha — não inventar; remover se existir
                if key in items:
                    del items[key]
                stats["items_skipped_no_bp"] += 1
                continue
            items[key] = _weapon_item(label, category, price_key, bp, tier, idx)
            stats["items_upserted"] += 1

        armor = _armor_bps(index, sheet)
        if armor:
            items[f"itensalfa_tek_{tier['id']}"] = _armor_item(armor, tier, idx)
            stats["items_upserted"] += 1
        else:
            stats["items_skipped_no_bp"] += 1

        kit_key = f"kit_itensalfa_{tier['id']}"
        kits[kit_key] = _kit_itensalfa(tier, idx, _collect_tier_bps(index, tier))
        stats["kits_upserted"] += 1

    legacy_map = {"kit_gamma": 1, "kit_beta": 2, "kit_alfa": 3}
    for kit_id, idx in legacy_map.items():
        if kit_id in kits and isinstance(kits[kit_id], dict):
            kits[kit_id]["Permissions"] = _perms_for_tier_index(idx)
            stats["legacy_kit_gates"] += 1

    # Alias legado gamma
    for idx, tier in enumerate(TIER_LADDER):
        if tier["id"] != "gamma":
            continue
        sheet = tier["sheet"]
        for prefix, fam, label, category, price_key in ITEM_MAP:
            bp = (index.get(fam) or {}).get(sheet)
            if not bp:
                continue
            items[f"{prefix}_gamma"] = _weapon_item(label, category, price_key, bp, tier, idx)

    _apply_creatures(items, stats)
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    index = _load_bp_index()
    raw = CONFIG.read_text(encoding="utf-8")
    data = json.loads(raw)
    before_items = len(data.get("Items", {}))
    before_kits = len(data.get("Kits", {}))
    stats = apply_config(data, index)
    after_items = len(data.get("Items", {}))
    after_kits = len(data.get("Kits", {}))

    print("=== apply_itensalfa_licenses ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"  Items: {before_items} -> {after_items}")
    print(f"  Kits:  {before_kits} -> {after_kits}")

    if args.dry_run:
        print("Dry-run: nenhuma escrita.")
        return 0

    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    CONFIG.write_text(text, encoding="utf-8")
    print(f"Escrito: {CONFIG}")
    if BIN_CONFIG.is_file():
        shutil.copy2(CONFIG, BIN_CONFIG)
        print(f"Espelho: {BIN_CONFIG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
