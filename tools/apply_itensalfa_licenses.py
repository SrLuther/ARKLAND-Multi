#!/usr/bin/env python3
"""Aplica licenças ItensAlfa (Delta→Exótico) no config CustomShop.

Idempotente: reexecutar atualiza preços/descrições/gates sem duplicar IDs.
Fontes: docs/LICENCAS_PRECOS_PROPOSTA.md, tools/itensalfa_kits_por_tier.csv

Uso:
  python tools/apply_itensalfa_licenses.py
  python tools/apply_itensalfa_licenses.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import shutil
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"
BIN_CONFIG = ROOT / "plugin" / "CustomShop" / "bin" / "config.json"

# Ordem da escada (grupo Permissions). Gama → Gamma (legado produção).
TIER_LADDER: list[dict] = [
    {"id": "delta", "group": "Delta", "label": "Delta", "path": "Delta", "price": 6000, "bonus": 5, "access": "apenas tier Delta"},
    {"id": "gamma", "group": "Gamma", "label": "Gamma", "path": "Gama", "price": 50000, "bonus": 25, "access": "Gama + Delta"},
    {"id": "beta", "group": "Beta", "label": "Beta", "path": "Beta", "price": 75000, "bonus": 50, "access": "Beta + Gama"},
    {"id": "alfa", "group": "Alfa", "label": "Alfa", "path": "Alfa", "price": 100000, "bonus": 75, "access": "Alfa + Beta"},
    {"id": "omega", "group": "Omega", "label": "Omega", "path": "Omega", "price": 115000, "bonus": 90, "access": "Omega + Alfa"},
    {"id": "transcendente", "group": "Transcendente", "label": "Transcendente", "path": "Transcendente", "price": 130000, "bonus": 105, "access": "Transcendente + Omega"},
    {"id": "etereo", "group": "Etereo", "label": "Etéreo", "path": "Etereo", "price": 150000, "bonus": 120, "access": "Etéreo + Transcendente"},
    {"id": "universal", "group": "Universal", "label": "Universal", "path": "Universal", "price": 165000, "bonus": 135, "access": "Universal + Etéreo"},
    {"id": "onipotente", "group": "Onipotente", "label": "Onipotente", "path": "Onipotente", "price": 180000, "bonus": 150, "access": "Onipotente + Universal"},
    {"id": "surreal", "group": "Surreal", "label": "Surreal", "path": "Surreal", "price": 195000, "bonus": 165, "access": "Surreal + Onipotente"},
    {"id": "imaterial", "group": "Imaterial", "label": "Imaterial", "path": "Imaterial", "price": 215000, "bonus": 180, "access": "Imaterial + Surreal"},
    {"id": "exotico", "group": "Exotico", "label": "Exótico", "path": "Exotico", "price": 230000, "bonus": 200, "access": "Exótico + Imaterial"},
]

# Preços CSV (armadura/peça, arma, ferramenta) — tools/itensalfa_precos_proposta.csv
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

# Kits ItensAlfa (tools/itensalfa_kits_por_tier.csv) — preço bundle
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

ARMOR_PIECES = ["Helmet", "Shirt", "Gloves", "Pants", "Boots"]

# Templates VISOUS já usados em Gama/Beta/Alfa — só troca o tier no path/nome.
WEAPON_TEMPLATES = [
    ("arco_tek", "Arco Tek", "Armas", "weapon",
     "/Game/Mods/VISOUSMod/ArcoTek/{path}/PrimalItem_Weapon_ArcoTek_{path}.PrimalItem_Weapon_ArcoTek_{path}"),
    ("escopeta", "Escopeta", "Armas", "weapon",
     "/Game/Mods/VISOUSMod/Escopeta/{path}/PrimalItem_Escopeta_{path}.PrimalItem_Escopeta_{path}"),
    ("foice", "Foice", "Ferramentas", "tool",
     "/Game/Mods/VISOUSMod/Foice/{path}/PrimalItem_Foice_{path}.PrimalItem_Foice_{path}"),
    ("machado", "Machado", "Ferramentas", "tool",
     "/Game/Mods/VISOUSMod/Machado/{path}/PrimalItem_Machado_{path}.PrimalItem_Machado_{path}"),
    ("motosserra", "Motoserra", "Ferramentas", "tool",
     "/Game/Mods/VISOUSMod/Motoserra/{path}/PrimalItem_Motosserra_{path}.PrimalItem_Motosserra_{path}"),
    ("picareta", "Picareta", "Ferramentas", "tool",
     "/Game/Mods/VISOUSMod/Picareta/{path}/PrimalItem_Picareta_{path}.PrimalItem_Picareta_{path}"),
]

ARMOR_TEMPLATES = [
    ("visous_blindado", "Armadura Blindada VISOUS",
     "/Game/Mods/VISOUSMod/Blindado/{path}/PrimalItemArmor_Metal{piece}_{path}.PrimalItemArmor_Metal{piece}_{path}"),
    ("visous_tek_padrao", "Armadura Tek VISOUS",
     "/Game/Mods/VISOUSMod/Roupa_Tek/Padrao/{path}/PrimalItemArmor_Tek{piece}_{path}.PrimalItemArmor_Tek{piece}_{path}"),
    ("visous_tek_gen2", "Armadura Tek Gen2 VISOUS",
     "/Game/Mods/VISOUSMod/Roupa_Tek/Gen2/{path}/PrimalItemArmor_Tek{piece}_Gen2_{path}.PrimalItemArmor_Tek{piece}_Gen2_{path}"),
]


def _perms_for_tier_index(idx: int) -> str:
    """Próprio tier + licença imediatamente acima (matriz N + N-1 invertida no gate)."""
    groups = ["Admins", TIER_LADDER[idx]["group"]]
    if idx + 1 < len(TIER_LADDER):
        groups.append(TIER_LADDER[idx + 1]["group"])
    return ",".join(groups)


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
        # Só quem já tem o grupo vê/compra a renovação −20%.
        entry["Permissions"] = f"Admins,{tier['group']}"
    return entry


def _weapon_item(prefix: str, label: str, category: str, price_key: str, bp: str, tier: dict, idx: int) -> dict:
    prices = ITEM_PRICES[tier["id"]]
    return {
        "Category": category,
        "Description": f"{label} {tier['label']} (1x)",
        "ForceBlueprint": False,
        "Items": [{"Blueprint": bp, "Quantity": 1, "Quality": 0, "ForceBlueprint": False}],
        "Name": f"{label} {tier['label']} (1x)",
        "Permissions": _perms_for_tier_index(idx),
        "Price": int(prices[price_key]),
        "Quality": 0,
        "Type": "item",
    }


def _armor_item(label: str, bps: list[str], tier: dict, idx: int) -> dict:
    prices = ITEM_PRICES[tier["id"]]
    return {
        "Category": "Armaduras",
        "Description": f"{label} {tier['label']} (5 peças)",
        "ForceBlueprint": False,
        "Items": [
            {"Blueprint": bp, "Quantity": 1, "Quality": 0, "ForceBlueprint": False}
            for bp in bps
        ],
        "Name": f"{label} {tier['label']} (5 peças)",
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
            f"Kit ItensAlfa {tier['label']} — {n} blueprints VISOUS do tier "
            f"(armaduras/armas/ferramentas conhecidos). Licença: próprio ou um acima. "
            f"Preço bundle CSV (−15/−20%). Gap: armas/selas extras do CSV sem BP verificado."
        ),
        "Items": [
            {"Blueprint": bp, "Quantity": 1, "Quality": 0, "ForceBlueprint": False}
            for bp in item_bps
        ],
        "Name": f"Kit ItensAlfa {tier['label']}",
        "Permissions": _perms_for_tier_index(idx),
        "Price": int(KIT_IA_PRICES[tier["id"]]),
        "Type": "kit",
    }


def _collect_tier_bps(tier: dict) -> list[str]:
    path = tier["path"]
    bps: list[str] = []
    for _prefix, _label, _cat, _pk, tmpl in WEAPON_TEMPLATES:
        bps.append(tmpl.format(path=path))
    for _prefix, _label, tmpl in ARMOR_TEMPLATES:
        for piece in ARMOR_PIECES:
            bps.append(tmpl.format(path=path, piece=piece))
    return bps


def apply_config(data: dict) -> dict[str, int]:
    stats = {
        "licenses": 0,
        "renewals": 0,
        "items_upserted": 0,
        "kits_upserted": 0,
        "timed_groups": 0,
        "legacy_kit_gates": 0,
    }
    items = data.setdefault("Items", {})
    kits = data.setdefault("Kits", {})

    # TimedPoints
    tpr = data.setdefault("TimedPointsReward", {})
    groups = tpr.setdefault("Groups", {})
    for tier in TIER_LADDER:
        groups[tier["group"]] = {"Amount": int(tier["bonus"])}
        stats["timed_groups"] += 1
    groups.setdefault("Default", {"Amount": 25})
    groups.setdefault("Moderacao", {"Amount": 500})
    groups.setdefault("STAFF", {"Amount": 1000})

    # Licenças + renovação −20%
    for tier in TIER_LADDER:
        lid = f"licenca_{tier['id']}"
        rid = f"licenca_{tier['id']}_renovacao"
        items[lid] = _license_entry(tier, renewal=False)
        items[rid] = _license_entry(tier, renewal=True)
        stats["licenses"] += 1
        stats["renewals"] += 1

    # Itens VISOUS por tier (padrão de path existente)
    for idx, tier in enumerate(TIER_LADDER):
        path = tier["path"]
        for prefix, label, category, price_key, tmpl in WEAPON_TEMPLATES:
            key = f"{prefix}_{tier['id']}"
            bp = tmpl.format(path=path)
            items[key] = _weapon_item(prefix, label, category, price_key, bp, tier, idx)
            stats["items_upserted"] += 1
        for prefix, label, tmpl in ARMOR_TEMPLATES:
            key = f"{prefix}_{tier['id']}"
            bps = [tmpl.format(path=path, piece=p) for p in ARMOR_PIECES]
            items[key] = _armor_item(label, bps, tier, idx)
            stats["items_upserted"] += 1

        # Kit ItensAlfa (não sobrescreve kit_gamma/beta/alfa VIP existentes)
        kit_key = f"kit_itensalfa_{tier['id']}"
        kits[kit_key] = _kit_itensalfa(tier, idx, _collect_tier_bps(tier))
        stats["kits_upserted"] += 1

    # Atualiza gates dos kits VIP legados (matriz N + N-1)
    legacy_map = {
        "kit_gamma": 1,  # Gamma index
        "kit_beta": 2,
        "kit_alfa": 3,
    }
    for kit_id, idx in legacy_map.items():
        if kit_id in kits and isinstance(kits[kit_id], dict):
            kits[kit_id]["Permissions"] = _perms_for_tier_index(idx)
            stats["legacy_kit_gates"] += 1

    # Aliases legados gamma nos itens (arco_tek_gamma etc.) — manter e alinhar preço/gate
    for idx, tier in enumerate(TIER_LADDER):
        if tier["id"] != "gamma":
            continue
        for prefix, label, category, price_key, tmpl in WEAPON_TEMPLATES:
            legacy_key = f"{prefix}_gamma"
            path = tier["path"]
            items[legacy_key] = _weapon_item(prefix, label, category, price_key, tmpl.format(path=path), tier, idx)
        for prefix, label, tmpl in ARMOR_TEMPLATES:
            legacy_key = f"{prefix}_gamma"
            path = tier["path"]
            bps = [tmpl.format(path=path, piece=p) for p in ARMOR_PIECES]
            items[legacy_key] = _armor_item(label, bps, tier, idx)

    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    raw = CONFIG.read_text(encoding="utf-8")
    data = json.loads(raw)
    before_items = len(data.get("Items", {}))
    before_kits = len(data.get("Kits", {}))
    stats = apply_config(data)
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
