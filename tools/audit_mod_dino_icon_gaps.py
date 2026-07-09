#!/usr/bin/env python3
"""Audita dinos de MOD no catálogo e gera docs/MOD_DINO_ICON_GAPS.md."""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
DOCS = ROOT / "docs" / "MOD_DINO_ICON_GAPS.md"
sys.path.insert(0, str(WEB))
sys.path.insert(0, str(ROOT / "tools"))

spec = importlib.util.spec_from_file_location("gen", ROOT / "tools" / "generate_ai_species_icons.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

from market_economy import build_catalog_economy_map, load_default_species_map  # noqa: E402
from ark_species_registry import VANILLA_CURATED, registry_entry_is_commerce_dino  # noqa: E402

ICONS_DIR = WEB / "static" / "species" / "icons"
GEN_DIR = ICONS_DIR / "generated"
REFS_DIR = ROOT / "refs" / "species_icons"
CONFIG = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"
ALIASES = gen.CANONICAL_ICON_ALIASES

KNOWN_MOD_KEYS = {
    "acro",
    "indominus",
    "indoraptor",
    "ancient_wyvern",
    "armaedron",
    "archelon",
    "brachio",
    "concavenator",
    "cryolophosaurus",
    "deinosuchus",
    "diru_ya_ku",
    "dread_wyvern",
    "kutsu_ya_ku",
    "puretotokage",
    "shimosaur",
    "xiphactinus",
}

_CATALOG_SUFFIX_RE = __import__("re").compile(r"(_200|_femea|_pack\d+)$")


def catalog_species_key(item_id: str, defn: dict | None = None) -> str:
    if defn and defn.get("species_key"):
        return str(defn["species_key"])
    return _CATALOG_SUFFIX_RE.sub("", item_id)


def is_mod_catalog_item(item_id: str, entry: dict, defn: dict | None, official_keys: set[str]) -> bool:
    sk = catalog_species_key(item_id, defn)
    ov = None
    if sk in official_keys:
        return False
    for vsk, *_ in VANILLA_CURATED:
        if vsk == sk:
            return False
    bp = str(((entry.get("Dinos") or [{}])[0]).get("Blueprint") or "")
    if "/Mods/" in bp:
        return True
    if item_id.startswith(("sb_", "abyss_")) or sk.startswith(("sb_", "abyss_")):
        return True
    ms = (defn or {}).get("mod_source", "")
    if ms and ms != "vanilla":
        return True
    if sk in KNOWN_MOD_KEYS or canonical(sk) in KNOWN_MOD_KEYS:
        return True
    return False


def canonical(sk: str) -> str:
    return ALIASES.get(sk.lower(), sk.lower())


def has_webp(sk: str) -> str | None:
    c = canonical(sk)
    if (GEN_DIR / f"{c}.webp").is_file():
        return c
    if (GEN_DIR / f"{sk.lower()}.webp").is_file():
        return sk.lower()
    return None


def has_svg(sk: str) -> str | None:
    c = canonical(sk)
    for key in (c, sk.lower()):
        if (ICONS_DIR / f"{key}.svg").is_file():
            return key
    return None


def infer_mod_pack(sk: str, defn: dict | None = None, overlay_entry: dict | None = None) -> str:
    sk = sk.lower()
    ms = (defn or {}).get("mod_source", "") or ""
    mod = (overlay_entry or {}).get("mod", "") or ""
    if sk.startswith("sb_"):
        return "SmallBosses"
    if sk.startswith("abyss_"):
        return "Abyss"
    if ms == "ark_additions":
        return "ARK Additions"
    if ms == "grand_hunt":
        return "Grand Hunt"
    if ms == "brighamia":
        return "Brighamia"
    if ms == "indominus_rex":
        return "Indominus Rex"
    if mod.lower() == "abyss":
        return "Abyss"
    if "indominus" in sk or "indoraptor" in sk:
        return "Indominus Rex"
    if "acro" in sk:
        return "ARK Additions"
    return ms or mod or "Outros mods"


def is_mod_dino(
    sk: str,
    defn: dict | None = None,
    overlay_entry: dict | None = None,
    official_keys: set[str] | None = None,
) -> bool:
    sk = sk.lower()
    if official_keys and sk in official_keys:
        return False
    for vsk, *_ in VANILLA_CURATED:
        if vsk == sk:
            return False
    role = (overlay_entry or {}).get("role", "")
    if role in ("resource", "seed", "vehicle", "structure"):
        return False
    if overlay_entry and not registry_entry_is_commerce_dino(overlay_entry):
        if not (defn and defn.get("species_key") == sk):
            return False
    ms = (defn or {}).get("mod_source", "")
    if ms and ms != "vanilla":
        return True
    if sk.startswith(("sb_", "abyss_")):
        return True
    if overlay_entry and overlay_entry.get("mod"):
        return True
    if sk in KNOWN_MOD_KEYS or canonical(sk) in KNOWN_MOD_KEYS:
        return True
    return False


def main() -> None:
    official = json.loads((WEB / "data" / "official_vanilla_species.json").read_text(encoding="utf-8"))
    official_keys = {s["species_key"] for s in official["species"]}
    overlay = json.loads((WEB / "data" / "ark_species_registry.json").read_text(encoding="utf-8"))
    ai_manifest = json.loads((GEN_DIR / "manifest.json").read_text(encoding="utf-8"))
    defaults = load_default_species_map()
    econ_map = build_catalog_economy_map()
    catalog = json.loads(CONFIG.read_text(encoding="utf-8"))
    items = catalog.get("Items") or catalog.get("ShopItems") or {}

    regen = {r["species_key"]: r for r in ai_manifest.get("regen_queue", [])}
    ai_icons = ai_manifest.get("icons", {})

    def status_for(sk: str) -> tuple[str, str | None, str | None]:
        c = canonical(sk)
        webp = has_webp(sk)
        svg = has_svg(sk)
        ai_entry = ai_icons.get(c) or ai_icons.get(sk)
        in_regen = sk in regen or c in regen or (ai_entry and ai_entry.get("status") == "needs_regeneration")
        if in_regen:
            return "NEEDS_REGEN", webp, svg
        if webp:
            return "HAS_AI_WEBP", webp, svg
        if svg:
            return "SVG_ONLY", webp, svg
        return "NO_ICON", webp, svg

    saved_refs: dict[str, str] = {}
    if REFS_DIR.is_dir():
        for path in REFS_DIR.iterdir():
            if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                saved_refs[path.stem.lower()] = path.name

    overlay_by_key = {e["species_key"]: e for e in overlay.get("species", []) if e.get("species_key")}

    catalog_mod_dinos: dict[str, dict] = {}
    for item_id, entry in items.items():
        if str(entry.get("Type", "")).lower() != "dino":
            continue
        defn = econ_map.get(item_id)
        if not is_mod_catalog_item(item_id, entry, defn, official_keys):
            continue
        sk = catalog_species_key(item_id, defn)
        ov = overlay_by_key.get(sk)
        display_name = (
            (defn or {}).get("display_name")
            or (ov or {}).get("display_name")
            or str(entry.get("Name") or sk).split(" Nível")[0].strip()
        )
        if sk not in catalog_mod_dinos:
            catalog_mod_dinos[sk] = {
                "species_key": sk,
                "display_name": display_name,
                "mod_pack": infer_mod_pack(sk, defn, ov),
                "catalog_item_ids": [],
                "tier": (defn or {}).get("tier") or (ov or {}).get("tier", ""),
                "mod_source": (defn or {}).get("mod_source", ""),
                "mapped_in_defaults": bool(defn),
            }
        catalog_mod_dinos[sk]["catalog_item_ids"].append(item_id)

    registry_mod_dinos: dict[str, dict] = {}
    for e in overlay.get("species", []):
        sk = e.get("species_key", "")
        if not sk or not registry_entry_is_commerce_dino(e):
            continue
        if not is_mod_dino(sk, defaults.get(sk), e, official_keys):
            continue
        registry_mod_dinos[sk] = e

    all_mod_keys = set(catalog_mod_dinos) | set(registry_mod_dinos)
    rows: list[dict] = []
    for sk in sorted(all_mod_keys):
        defn = defaults.get(sk, {})
        ov = overlay_by_key.get(sk, {})
        cat = catalog_mod_dinos.get(sk, {})
        st, webp, svg = status_for(sk)
        c = canonical(sk)
        has_ref = c in saved_refs or sk in saved_refs
        in_catalog = sk in catalog_mod_dinos
        rows.append(
            {
                "species_key": sk,
                "display_name": cat.get("display_name") or defn.get("display_name") or ov.get("display_name", sk),
                "mod_pack": cat.get("mod_pack") or infer_mod_pack(sk, defn, ov),
                "catalog_item_id": ", ".join(cat.get("catalog_item_ids", [])) or ov.get("catalog_item_id", "—"),
                "in_catalog": in_catalog,
                "mapped_in_defaults": cat.get("mapped_in_defaults", bool(defn)),
                "status": st,
                "webp": webp or "—",
                "svg": svg or "—",
                "has_ref": has_ref,
                "ref_path": f"refs/species_icons/{c}.png",
                "tier": cat.get("tier") or defn.get("tier") or ov.get("tier", ""),
            }
        )

    status_counts = Counter(r["status"] for r in rows)
    catalog_rows = [r for r in rows if r["in_catalog"]]
    cat_status = Counter(r["status"] for r in catalog_rows)
    by_pack: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_pack[r["mod_pack"]].append(r)

    gaps = [r for r in catalog_rows if r["status"] in ("NO_ICON", "SVG_ONLY", "NEEDS_REGEN")]
    gaps.sort(key=lambda x: (0 if x["status"] == "NO_ICON" else 1 if x["status"] == "SVG_ONLY" else 2, x["mod_pack"], x["display_name"].lower()))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    webp_count = len(list(GEN_DIR.glob("*.webp")))
    ref_count = len(saved_refs)

    out: list[str] = []
    out.append("# Lacunas de ícones — dinos de MOD")
    out.append("")
    out.append(
        f"> Gerado em **{now}** por `tools/audit_mod_dino_icon_gaps.py`. "
        "Auditoria apenas — não gera ícones."
    )
    out.append("")
    out.append("## Resumo")
    out.append("")
    out.append("| Métrica | Valor |")
    out.append("|---------|-------|")
    out.append(f"| Dinos de mod rastreados (catálogo + registro) | **{len(rows)}** |")
    out.append(f"| Dinos de mod no catálogo (`config.json` Type=dino) | **{len(catalog_rows)}** |")
    out.append(f"| Espécies mod só no registro (fora do catálogo) | **{len(rows) - len(catalog_rows)}** |")
    out.append(f"| Sem mapeamento em `market_species_defaults` | **{sum(1 for r in catalog_rows if not r.get('mapped_in_defaults'))}** |")
    out.append(f"| Com WebP AI (`generated/*.webp`) | **{status_counts['HAS_AI_WEBP']}** |")
    out.append(f"| Só SVG procedural (badge) | **{status_counts['SVG_ONLY']}** |")
    out.append(f"| Na fila de regeneração | **{status_counts['NEEDS_REGEN']}** |")
    out.append(f"| Sem ícone (fallback de tier) | **{status_counts['NO_ICON']}** |")
    out.append(f"| WebP totais no disco | **{webp_count}** |")
    out.append(f"| Referências em `refs/species_icons/` | **{ref_count}** |")
    out.append("")
    out.append("### Status no catálogo (loja)")
    out.append("")
    for st in ("HAS_AI_WEBP", "SVG_ONLY", "NEEDS_REGEN", "NO_ICON"):
        if cat_status.get(st):
            out.append(f"- **{st}**: {cat_status[st]}")
    out.append("")
    out.append("### Por pacote de mod")
    out.append("")
    out.append("| Pacote | Total | WebP | SVG only | Regen | Sem ícone |")
    out.append("|--------|-------|------|----------|-------|-----------|")
    for pack in sorted(by_pack.keys()):
        pack_rows = by_pack[pack]
        pc = Counter(r["status"] for r in pack_rows)
        out.append(
            f"| {pack} | {len(pack_rows)} | {pc['HAS_AI_WEBP']} | {pc['SVG_ONLY']} | "
            f"{pc['NEEDS_REGEN']} | {pc['NO_ICON']} |"
        )
    out.append("")
    out.append("---")
    out.append("")
    out.append("## Prioridade — catálogo sem ícone adequado")
    out.append("")
    out.append(
        "Ordem: **NO_ICON** (pior) → **SVG_ONLY** (badge genérico) → **NEEDS_REGEN** (WebP existente mas reprovado)."
    )
    out.append("")
    out.append("| # | species_key | display_name | mod | catalog_item_id | status | ref salva? | ref sugerida |")
    out.append("|---|-------------|--------------|-----|-------------------|--------|------------|--------------|")
    for i, r in enumerate(gaps, 1):
        ref_saved = "sim" if r["has_ref"] else "não"
        out.append(
            f"| {i} | `{r['species_key']}` | {r['display_name']} | {r['mod_pack']} | "
            f"`{r['catalog_item_id']}` | {r['status']} | {ref_saved} | `{r['ref_path']}` |"
        )
    out.append("")
    out.append("---")
    out.append("")
    out.append("## Tabela completa (todos os dinos de mod)")
    out.append("")
    out.append(
        "| species_key | display_name | mod/source | catalog_item_id | in_catalog? | status | webp | svg | ref? | ref sugerida |"
    )
    out.append(
        "|-------------|--------------|------------|-----------------|-------------|--------|------|-----|------|--------------|"
    )
    for r in rows:
        in_cat = "sim" if r["in_catalog"] else "não"
        ref_saved = "sim" if r["has_ref"] else "não"
        out.append(
            f"| `{r['species_key']}` | {r['display_name']} | {r['mod_pack']} | `{r['catalog_item_id']}` | "
            f"{in_cat} | {r['status']} | `{r['webp']}` | `{r['svg']}` | {ref_saved} | `{r['ref_path']}` |"
        )
    out.append("")
    out.append("---")
    out.append("")
    for pack in sorted(by_pack.keys()):
        pack_rows = sorted(by_pack[pack], key=lambda x: x["display_name"].lower())
        out.append(f"## {pack}")
        out.append("")
        out.append("| species_key | display_name | status | catalog_item_id | ref? |")
        out.append("|-------------|--------------|--------|-----------------|------|")
        for r in pack_rows:
            ref_saved = "sim" if r["has_ref"] else "não"
            out.append(
                f"| `{r['species_key']}` | {r['display_name']} | {r['status']} | `{r['catalog_item_id']}` | {ref_saved} |"
            )
        out.append("")

    out.append("---")
    out.append("")
    out.append("## Site ao vivo (arkland.com.br)")
    out.append("")
    out.append(
        "O portal público em [arkland.com.br](https://arkland.com.br) carrega o catálogo de doações "
        "(abas Itens / Dinos / Kits) e o Comércio P2P (Tabela Oficial, Mercado, Encomenda). "
        "A página inicial é acessível sem login; mercado/encomenda exigem Steam."
    )
    out.append("")
    out.append(
        "Com base no HTML público, na API `/api/catalog` (88 itens Type=dino de mod, alinhados ao `config.json` local) "
        "e no pipeline de ícones do repositório: todos os dinos de mod listados acima aparecem na loja com "
        "**badge SVG procedural** ou **silhueta de tier** — nenhum mod do catálogo possui WebP AI dedicado."
    )
    out.append("")
    out.append("### Lacunas visíveis no catálogo (prioridade alta)")
    out.append("")
    out.append("| Prioridade | Espécies | Impacto |")
    out.append("|------------|----------|---------|")
    out.append("| **P0** | `indoraptor` | Único mod no catálogo sem SVG — cai direto no fallback de tier S+ |")
    out.append("| **P1** | 20× SmallBosses (`sb_*`) | 40 itens na loja, zero ícone (nem SVG) |")
    out.append("| **P2** | 28× Abyss dinos | SVG badge apenas; sem WebP AI |")
    out.append("| **P3** | ARK Additions, Grand Hunt, Brighamia, Indominus | SVG badge; sem WebP AI nem ref salva |")
    out.append("")
    out.append("## Fontes auditadas")
    out.append("")
    out.append("- `plugin/CustomShop/configs/config.json` (Items Type=dino)")
    out.append("- `plugin/arkshop_web/data/market_species_defaults.json`")
    out.append("- `plugin/arkshop_web/data/ark_species_registry.json`")
    out.append("- `plugin/arkshop_web/data/species_icons_manifest.json`")
    out.append("- `plugin/arkshop_web/static/species/icons/*.svg`")
    out.append("- `plugin/arkshop_web/static/species/icons/generated/*.webp`")
    out.append("- `plugin/arkshop_web/static/species/icons/generated/manifest.json`")
    out.append("- `refs/species_icons/`")
    out.append("- Resolução: `resolve_species_image` em `ark_species_registry.py`")
    out.append("")
    out.append("## Critérios")
    out.append("")
    out.append("- **mod**: não está em `official_vanilla_species.json` (99 oficiais) nem em `VANILLA_CURATED`")
    out.append("- **dino**: `Type=dino` no catálogo ou `registry_entry_is_commerce_dino` no overlay")
    out.append("- Exclui recursos/sementes Abyss (`role`: resource, seed, etc.)")
    out.append("- **HAS_AI_WEBP**: `generated/{canonical}.webp` existe e não está na fila regen")
    out.append("- **SVG_ONLY**: só badge procedural em `icons/*.svg`")
    out.append("- **NO_ICON**: cai em silhueta de tier (`tier-s.svg`, etc.)")

    DOCS.parent.mkdir(parents=True, exist_ok=True)
    DOCS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Wrote {DOCS}")
    print(f"Mod dinos: {len(rows)} | catalog: {len(catalog_rows)} | gaps: {len(gaps)}")
    print(f"Status: {dict(status_counts)}")


if __name__ == "__main__":
    main()
