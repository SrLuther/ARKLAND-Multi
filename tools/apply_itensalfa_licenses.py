#!/usr/bin/env python3
"""Aplica licenças ItensAlfa (Delta→Exótico) no config CustomShop.

Idempotente: reexecutar atualiza preços/descrições/gates sem duplicar IDs.
BPs: tools/itensalfa_blueprints.json + tools/itensalfa_creatures.json
     (extraídos de Itens Alfa.xlsx — nunca inventa).
Fontes preços: docs/LICENCAS_PRECOS_PROPOSTA.md, tools/itensalfa_kits_por_tier.csv,
               tools/itensalfa_precos_proposta.csv

Preços de itens/kits/criaturas ItensAlfa: base da proposta × PRICE_MARKUP (15%).
Licenças (licenca_*) NÃO recebem markup.

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

# Acréscimo loja ItensAlfa (itens, kits, criaturas). Não aplicar a licenças.
PRICE_MARKUP = 1.15


def _shop_price(base: int | float) -> int:
    """Preço final na loja = base proposta × 15%, arredondado ao inteiro."""
    return int(round(float(base) * PRICE_MARKUP))

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
    # Selas TEK: tools/itensalfa_precos_proposta.csv / kits_por_tier (só Delta→Omega).
    "delta": {"armor_piece": 400, "weapon": 300, "tool": 200, "saddle": 400, "armor_set": 2000},
    "gamma": {"armor_piece": 700, "weapon": 500, "tool": 400, "saddle": 600, "armor_set": 3500},
    "beta": {"armor_piece": 1100, "weapon": 800, "tool": 700, "saddle": 1000, "armor_set": 5500},
    "alfa": {"armor_piece": 1700, "weapon": 1300, "tool": 1000, "saddle": 1500, "armor_set": 8500},
    "omega": {"armor_piece": 2400, "weapon": 1800, "tool": 1400, "saddle": 2100, "armor_set": 12000},
    "transcendente": {"armor_piece": 3400, "weapon": 2600, "tool": 2000, "saddle": 0, "armor_set": 17000},
    "etereo": {"armor_piece": 4800, "weapon": 3600, "tool": 2900, "saddle": 0, "armor_set": 24000},
    "universal": {"armor_piece": 6400, "weapon": 4800, "tool": 3800, "saddle": 0, "armor_set": 32000},
    "onipotente": {"armor_piece": 8400, "weapon": 6300, "tool": 5000, "saddle": 0, "armor_set": 42000},
    "surreal": {"armor_piece": 10800, "weapon": 8100, "tool": 6500, "saddle": 0, "armor_set": 54000},
    "imaterial": {"armor_piece": 13600, "weapon": 10200, "tool": 8200, "saddle": 0, "armor_set": 68000},
    "exotico": {"armor_piece": 17200, "weapon": 12900, "tool": 10300, "saddle": 0, "armor_set": 86000},
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
# Completo face à planilha ASE Armas / ASE - Ferramentas (só entra se houver BP no índice).
ITEM_MAP = [
    # Armas (14 famílias; Club/Grenade/Cruise só Alfa na planilha)
    ("escudo_tek", "TekShiledArmor", "Escudo TEK ItensAlfa", "Armas", "weapon"),
    ("canhao_ombro", "ShoulderCannon", "Canhão de Ombro ItensAlfa", "Armas", "weapon"),
    ("arco_tek", "TekBow", "Arco Tek ItensAlfa", "Armas", "weapon"),
    ("pistola_tek", "TekPistol", "Pistola TEK ItensAlfa", "Armas", "weapon"),
    ("electropod", "EletricPod", "ElectroPod ItensAlfa", "Armas", "weapon"),
    ("espada_tek", "TekSword", "Espada TEK ItensAlfa", "Armas", "weapon"),
    ("garras_tek", "TekClaws", "Garras TEK ItensAlfa", "Armas", "weapon"),
    ("rifle_tek", "TekRifle", "Rifle TEK ItensAlfa", "Armas", "weapon"),
    ("sniper", "Sniper", "Sniper ItensAlfa", "Armas", "weapon"),
    ("pike", "Pike", "Pike ItensAlfa", "Armas", "weapon"),
    ("escopeta", "PumpAction", "Escopeta ItensAlfa", "Armas", "weapon"),
    ("clava", "StoneClub", "Clava ItensAlfa", "Armas", "weapon"),
    ("lanca_granadas", "GrenadeLauncher", "Lança-Granadas TEK ItensAlfa", "Armas", "weapon"),
    ("cruise_missile", "TekCruiseMissile", "Cruise Missile TEK ItensAlfa", "Armas", "weapon"),
    # Ferramentas (9; FishingRod Delta→Alfa; Torch/Whip/Lanterna só Alfa)
    ("motosserra", "Chainsaw", "Motosserra ItensAlfa", "Ferramentas", "tool"),
    ("machado", "Hatched", "Machado ItensAlfa", "Ferramentas", "tool"),
    ("mining_drill", "MiningDrill", "Mining Drill ItensAlfa", "Ferramentas", "tool"),
    ("picareta", "Pick", "Picareta ItensAlfa", "Ferramentas", "tool"),
    ("foice", "Sickle", "Foice ItensAlfa", "Ferramentas", "tool"),
    ("vara_pesca", "FishingRod", "Vara de Pesca ItensAlfa", "Ferramentas", "tool"),
    ("tocha", "Torch", "Tocha ItensAlfa", "Ferramentas", "tool"),
    ("chicote", "Whip", "Chicote ItensAlfa", "Ferramentas", "tool"),
    ("lanterna", "LanternCharge", "Lanterna de Carga ItensAlfa", "Ferramentas", "tool"),
    # Selas TEK (7; apenas Delta→Omega na planilha — BPs ausentes = skip)
    ("itensalfa_sela_megalodon", "Megalodon", "Sela TEK Megalodon ItensAlfa", "ItensAlfa — Selas", "saddle"),
    ("itensalfa_sela_mosassauro", "Mosa", "Sela TEK Mosassauro ItensAlfa", "ItensAlfa — Selas", "saddle"),
    ("itensalfa_sela_rex", "Rex", "Sela TEK Rex ItensAlfa", "ItensAlfa — Selas", "saddle"),
    ("itensalfa_sela_rockdrake", "RockDrake", "Sela TEK Rock Drake ItensAlfa", "ItensAlfa — Selas", "saddle"),
    ("itensalfa_sela_astrodelph", "SpaceDolphin", "Sela TEK Astrodelph ItensAlfa", "ItensAlfa — Selas", "saddle"),
    ("itensalfa_sela_astrocetus", "SpaceWhale", "Sela TEK Astrocetus ItensAlfa", "ItensAlfa — Selas", "saddle"),
    ("itensalfa_sela_tapejara", "Tapejara", "Sela TEK Tapejara ItensAlfa", "ItensAlfa — Selas", "saddle"),
]

ARMOR_FAMILIES = ("TekHelmet", "TekShirtNew", "TekGloves", "TekPants", "TekBoots")

# Stats de combate por tier (planilha Status dos itens → itensalfa_kit_descriptions.json).
TIER_STATUS: dict[str, dict[str, int]] = {
    "Delta": {"armor": 180, "weapon": 120, "saddle": 40},
    "Gama": {"armor": 500, "weapon": 250, "saddle": 100},
    "Beta": {"armor": 1000, "weapon": 450, "saddle": 350},
    "Alfa": {"armor": 1900, "weapon": 750, "saddle": 600},
    "Omega": {"armor": 3200, "weapon": 1300, "saddle": 790},
    "Transcendente": {"armor": 4900, "weapon": 1850, "saddle": 0},
    "Etereo": {"armor": 7000, "weapon": 2500, "saddle": 0},
    "Universal": {"armor": 9500, "weapon": 3250, "saddle": 0},
    "Onipotente": {"armor": 12400, "weapon": 4100, "saddle": 0},
    "Surreal": {"armor": 15700, "weapon": 4950, "saddle": 0},
    "Imaterial": {"armor": 19400, "weapon": 5800, "saddle": 0},
    "Exotico": {"armor": 23500, "weapon": 6650, "saddle": 0},
}

# Preço Â âncora (proposta §5.6 / CSV) no tier de referência da família.
# HoverSail / Mek / Exo-Mek / MiniMegaMek removidos do catálogo (crash no servidor).
CREATURE_BLOCKED_FAMILIES: frozenset[str] = frozenset({"HOVERSAIL", "EXO-MEK", "MEK"})
CREATURE_PRICE_ANCHOR: dict[str, tuple[int, str]] = {
    "HOVERSKIFF": (15000, "alfa"),
    "ENFORCER": (8000, "alfa"),
    "DEFENDER": (8000, "alfa"),
    "STRYDER": (25000, "alfa"),
    "SUBMARINE": (18000, "alfa"),
}

# Labels de planilha → id da escada (Comum/Minimega/Perfect* não são grupos Permissions).
# PerfectPVE/PerfectPVP: âncora Alfa para preço; gate real = qualquer licença excepto Nuvem.
CREATURE_TIER_ALIAS: dict[str, str] = {
    "Gama": "gamma",
    "Comum": "delta",
    "Minimega": "omega",
    "PerfectPVE": "alfa",
    "PerfectPVP": "alfa",
}

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
    # Base arredondada à centena; markup 15% aplicado em _creature_item.
    return max(100, int(round(raw / 100.0) * 100))


def _creature_shop_key(family: str, sheet_tier: str) -> str:
    fam = family.lower().replace("-", "").replace(" ", "")
    tier = sheet_tier.lower().replace(" ", "")
    return f"itensalfa_{fam}_{tier}"


def _creature_display_name(family: str, sheet_tier: str, tier_id: str) -> str:
    fam_names = {
        "HOVERSKIFF": "HoverSkiff",
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
) -> dict:
    name = _creature_display_name(family, sheet_tier, tier_id)
    # Stryder PerfectPVE/PerfectPVP: preço âncora fixo (proposta); restantes escalam por tier.
    if family == "STRYDER" and sheet_tier in ("PerfectPVE", "PerfectPVP"):
        price = _shop_price(CREATURE_PRICE_ANCHOR["STRYDER"][0])
    else:
        price = _shop_price(_creature_price(family, tier_id))
    desc = (
        f"{name} — resgatável com qualquer licença Delta→Exótico "
        "(Nuvem/keyvault não conta)."
    )
    return {
        "Category": "ItensAlfa — Criaturas",
        "Description": desc,
        "ForceBlueprint": False,
        "Items": [_bp_entry(bp)],
        "Name": name,
        "Permissions": _perms_all_license_tiers(),
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
    base = int(prices.get(price_key) or 0)
    name = f"{label} {tier['label']} (1x)"
    entry = {
        "Category": category,
        "Description": name,
        "ForceBlueprint": False,
        "Items": [_bp_entry(bp)],
        "Name": name,
        "Permissions": _perms_for_tier_index(idx),
        "Price": _shop_price(base),
        "Quality": 0,
        "Type": "item",
    }
    if price_key == "saddle":
        st = TIER_STATUS.get(tier["sheet"]) or {}
        saddle_armor = int(st.get("saddle") or 0)
        if saddle_armor:
            entry["Description"] = (
                f"{name} — armadura da sela {saddle_armor}. "
                f"Licença: próprio ou um acima."
            )
    return entry


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
        "Price": _shop_price(prices["armor_set"]),
        "Quality": 0,
        "Type": "item",
    }


def _classify_kit_bps(item_bps: list[str]) -> dict[str, int]:
    counts = {"armor": 0, "weapon": 0, "tool": 0, "saddle": 0, "other": 0}
    for bp in item_bps:
        low = (bp or "").lower()
        if "saddle" in low or "/selas/" in low:
            counts["saddle"] += 1
        elif "tool" in low or "/ferramentas/" in low:
            counts["tool"] += 1
        elif "weapon" in low or "/armas/" in low or "shiled" in low or "shield" in low:
            # Escudo TEK (TekShiledArmor) conta como arma na planilha Status
            counts["weapon"] += 1
        elif "armor" in low or "/armadura/" in low:
            counts["armor"] += 1
        else:
            counts["other"] += 1
    return counts


def _kit_detail_blurb(tier: dict, item_bps: list[str]) -> str:
    """Texto estruturado do kit (stats + contagens) — fonte: TIER_STATUS / BPs."""
    counts = _classify_kit_bps(item_bps)
    st = TIER_STATUS.get(tier["sheet"]) or {}
    parts: list[str] = []
    if counts["armor"]:
        arm = st.get("armor")
        parts.append(
            f"{counts['armor']} armaduras TEK"
            + (f" (armadura {arm})" if arm else "")
        )
    if counts["weapon"]:
        dmg = st.get("weapon")
        parts.append(
            f"{counts['weapon']} armas"
            + (f" (dano {dmg})" if dmg else "")
        )
    if counts["tool"]:
        parts.append(f"{counts['tool']} ferramentas")
    if counts["saddle"]:
        sad = st.get("saddle")
        parts.append(
            f"{counts['saddle']} selas TEK"
            + (f" (armadura da sela {sad})" if sad else "")
        )
    elif tier["id"] in ("delta", "gamma", "beta", "alfa", "omega"):
        parts.append("sem selas neste pacote")
    else:
        parts.append("sem selas (selas só até Omega)")
    if counts["other"]:
        parts.append(f"{counts['other']} outros")
    body = "; ".join(parts) if parts else "conteúdo do tier"
    return (
        f"Inclui {len(item_bps)} blueprints ItensAlfa {tier['label']}: {body}. "
        f"Licença: próprio ou um acima."
    )


def _kit_itensalfa(tier: dict, idx: int, item_bps: list[str]) -> dict:
    n = len(item_bps)
    blurb = _kit_detail_blurb(tier, item_bps)
    return {
        "DefaultAmount": 1,
        "Description": blurb,
        "KitDescription": blurb,
        "Items": [_bp_entry(bp) for bp in item_bps],
        "Name": f"Kit ItensAlfa {tier['label']}",
        "Permissions": _perms_for_tier_index(idx),
        "Price": _shop_price(KIT_IA_PRICES[tier["id"]]),
        "Type": "kit",
        "ItemCountHint": n,
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
    """Upsert todas as criaturas/veículos ItensAlfa da planilha (gate any-license excepto Nuvem)."""
    for row in _load_creatures():
        family = str(row.get("family") or "").strip().upper()
        sheet_tier = str(row.get("tier") or "").strip()
        bp = str(row.get("blueprint") or "").strip()
        if not family or not sheet_tier or not bp:
            stats["creatures_skipped"] += 1
            continue
        if family in CREATURE_BLOCKED_FAMILIES:
            stats["creatures_skipped"] += 1
            print(f"  SKIP creature (bloqueada — crash): {family} {sheet_tier}")
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

        key = _creature_shop_key(family, sheet_tier)
        items[key] = _creature_item(
            family=family,
            sheet_tier=sheet_tier,
            bp=bp,
            tier_id=tier_id,
        )
        stats["creatures_upserted"] += 1


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
