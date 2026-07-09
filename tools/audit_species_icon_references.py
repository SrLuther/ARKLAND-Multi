#!/usr/bin/env python3
"""Audita ícones de espécies e gera docs/SPECIES_ICON_REFERENCE_CHECKLIST.md."""
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
DOCS = ROOT / "docs" / "SPECIES_ICON_REFERENCE_CHECKLIST.md"
sys.path.insert(0, str(WEB))
sys.path.insert(0, str(ROOT / "tools"))

spec = importlib.util.spec_from_file_location("gen", ROOT / "tools" / "generate_ai_species_icons.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

from market_economy import build_catalog_economy_map, load_default_species_map  # noqa: E402
from ark_species_registry import VANILLA_CURATED  # noqa: E402

ICONS_DIR = WEB / "static" / "species" / "icons"
GEN_DIR = ICONS_DIR / "generated"
REFS_DIR = ROOT / "refs" / "species_icons"
CONFIG = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"

ALIASES = gen.CANONICAL_ICON_ALIASES
DONE_QUEUE_KEYS = {"megalosaurus", "tekstrider", "reaper"}


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


def infer_origin(sk: str, mod_source: str | None = None, mod: str | None = None, official_keys: set[str] | None = None) -> str:
    sk = sk.lower()
    if sk.startswith("abyss_"):
        return "abyss"
    ms = (mod_source or "").lower()
    if ms == "vanilla":
        return "vanilla"
    if official_keys and sk in official_keys:
        return "vanilla"
    if mod == "abyss":
        return "abyss"
    if "sb_" in sk or ms == "sb":
        return "sb"
    return "mod"


def main() -> None:
    icons_manifest = json.loads((WEB / "data" / "species_icons_manifest.json").read_text(encoding="utf-8"))
    ai_manifest = json.loads((GEN_DIR / "manifest.json").read_text(encoding="utf-8"))
    defaults = load_default_species_map()
    overlay = json.loads((WEB / "data" / "ark_species_registry.json").read_text(encoding="utf-8"))
    official = json.loads((WEB / "data" / "official_vanilla_species.json").read_text(encoding="utf-8"))
    official_keys = {s["species_key"] for s in official["species"]}

    all_species: dict[str, dict] = {}

    def add(
        sk: str,
        display_name: str = "",
        origin: str | None = None,
        tier: str = "",
        in_catalog: bool = False,
        sources: list[str] | None = None,
        mod_source: str | None = None,
        mod: str | None = None,
    ) -> None:
        sk = sk.lower().strip()
        if not sk:
            return
        o = origin or infer_origin(sk, mod_source, mod, official_keys)
        if sk not in all_species:
            all_species[sk] = {
                "species_key": sk,
                "display_name": display_name or sk,
                "origin": o,
                "tier": tier,
                "in_catalog": in_catalog,
                "sources": set(sources or []),
            }
        else:
            entry = all_species[sk]
            if display_name and entry["display_name"] in ("", sk):
                entry["display_name"] = display_name
            if o and entry["origin"] == "mod" and o != "mod":
                entry["origin"] = o
            if tier:
                entry["tier"] = tier
            if in_catalog:
                entry["in_catalog"] = True
            entry["sources"].update(sources or [])

    for sk, defn in defaults.items():
        add(
            sk,
            defn.get("display_name", ""),
            in_catalog=True,
            tier=defn.get("tier", ""),
            sources=["market_defaults"],
            mod_source=defn.get("mod_source"),
        )

    for entry in overlay.get("species", []):
        sk = entry.get("species_key", "")
        add(
            sk,
            entry.get("display_name", ""),
            tier=entry.get("tier", ""),
            in_catalog=sk in defaults,
            sources=["registry_overlay"],
            mod=entry.get("mod"),
        )

    for sk, dn, _token, tier, _role, _rv in VANILLA_CURATED:
        add(sk, dn, origin="vanilla", tier=tier, in_catalog=sk in defaults, sources=["vanilla_curated"])

    for sk, meta in icons_manifest.get("icons", {}).items():
        add(
            sk,
            meta.get("display_name", ""),
            tier=meta.get("tier", ""),
            in_catalog=sk in defaults,
            sources=["icons_manifest"],
        )

    for svg_file in ICONS_DIR.glob("*.svg"):
        add(svg_file.stem, in_catalog=svg_file.stem in defaults, sources=["svg_file"])

    for s in official["species"]:
        add(
            s["species_key"],
            s.get("display_name", ""),
            origin="vanilla",
            tier=s.get("tier", ""),
            in_catalog=s["species_key"] in defaults,
            sources=["official_vanilla"],
        )

    catalog = json.loads(CONFIG.read_text(encoding="utf-8"))
    econ_map = build_catalog_economy_map()
    items = catalog.get("Items") or catalog.get("ShopItems") or {}
    for item_id, entry in items.items():
        if str(entry.get("Type", "")).lower() != "dino":
            continue
        defn = econ_map.get(item_id)
        if defn:
            sk = defn["species_key"]
            add(
                sk,
                defn.get("display_name", ""),
                in_catalog=True,
                tier=defn.get("tier", ""),
                sources=["config_catalog"],
                mod_source=defn.get("mod_source"),
            )

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

    rows: list[dict] = []
    for sk, entry in all_species.items():
        st, webp, svg = status_for(sk)
        rows.append({
            **entry,
            "status": st,
            "webp": webp,
            "svg": svg,
            "canonical": canonical(sk),
            "regen_note": (regen.get(sk) or regen.get(canonical(sk)) or {}).get("note", ""),
        })

    prio_a = [r for r in rows if r["in_catalog"] and r["status"] == "NO_ICON"]
    prio_b = [r for r in rows if r["in_catalog"] and r["status"] == "SVG_ONLY"]
    prio_c = [
        r for r in rows
        if r["species_key"] in official_keys and r["status"] in ("NO_ICON", "SVG_ONLY", "NEEDS_REGEN")
    ]
    prio_d = [r for r in rows if r["svg"] and not r["webp"]]

    saved_refs: dict[str, str] = {}
    if REFS_DIR.is_dir():
        for path in REFS_DIR.iterdir():
            if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                saved_refs[path.stem.lower()] = path.name

    done_rows = [r for r in rows if r["species_key"] in DONE_QUEUE_KEYS or r["canonical"] in DONE_QUEUE_KEYS]

    status_counts = Counter(r["status"] for r in rows)
    catalog_rows = [r for r in rows if r["in_catalog"]]
    catalog_status = Counter(r["status"] for r in catalog_rows)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    webp_files = sorted(p.stem for p in GEN_DIR.glob("*.webp"))
    svg_files = sorted(p.stem for p in ICONS_DIR.glob("*.svg"))

    def table_md(items: list[dict], title: str) -> str:
        lines = [
            f"## {title}",
            "",
            f"**Total: {len(items)}**",
            "",
            "| species_key | display_name | origin | current_status | in_catalog? | ref sugerida |",
            "|-------------|--------------|--------|----------------|-------------|--------------|",
        ]
        for row in sorted(items, key=lambda x: (x["origin"], x["display_name"].lower())):
            ref = f"`refs/species_icons/{row['canonical']}.png`"
            in_cat = "sim" if row["in_catalog"] else "não"
            lines.append(
                f"| `{row['species_key']}` | {row['display_name']} | {row['origin']} | {row['status']} | {in_cat} | {ref} |"
            )
        lines.append("")
        return "\n".join(lines)

    out: list[str] = []
    out.append("# Checklist — referências de ícones de espécies")
    out.append("")
    out.append(
        f"> Gerado em **{now}** por `tools/audit_species_icon_references.py`. "
        "Não gera ícones — só lista o que falta para você caçar referências."
    )
    out.append("")
    out.append("## Resumo")
    out.append("")
    out.append("| Métrica | Valor |")
    out.append("|---------|-------|")
    out.append(f"| Espécies rastreadas (todas as fontes) | **{len(rows)}** |")
    out.append(f"| No catálogo atual (`market_species_defaults` + `config.json` dino) | **{len(catalog_rows)}** |")
    out.append(f"| Oficial vanilla (`official_vanilla_species.json`) | **{official['count']}** |")
    out.append(f"| WebP AI em `generated/` | **{len(webp_files)}** |")
    out.append(f"| SVG procedural em `icons/` | **{len(svg_files)}** |")
    out.append(f"| Referências salvas em `refs/species_icons/` | **{len(saved_refs)}** |")
    out.append("")
    out.append("### Status global")
    out.append("")
    out.append("| Status | Qtd | Significado |")
    out.append("|--------|-----|-------------|")
    out.append(f"| HAS_AI_WEBP | {status_counts['HAS_AI_WEBP']} | WebP gerado (ou alias resolve) |")
    out.append(f"| SVG_ONLY | {status_counts['SVG_ONLY']} | SVG procedural, sem WebP AI |")
    out.append(f"| NEEDS_REGEN | {status_counts['NEEDS_REGEN']} | WebP existe mas na fila de regeneração |")
    out.append(f"| NO_ICON | {status_counts['NO_ICON']} | Sem SVG nem WebP (fallback de tier) |")
    out.append("")
    out.append("### Catálogo atual")
    out.append("")
    for st, count in sorted(catalog_status.items()):
        out.append(f"- **{st}**: {count}")
    out.append("")
    out.append("### Prioridades para caçar referências")
    out.append("")
    out.append(f"- **Prioridade A** (catálogo sem ícone): **{len(prio_a)}**")
    out.append(f"- **Prioridade B** (catálogo só SVG): **{len(prio_b)}**")
    out.append(f"- **Prioridade C** (vanilla oficial sem WebP OK / regen): **{len(prio_c)}**")
    out.append(f"- **Prioridade D** (SVG no disco sem WebP): **{len(prio_d)}**")
    out.append("")
    out.append("---")
    out.append("")
    out.append(table_md(prio_a, "Prioridade A — Catálogo sem nenhum ícone"))
    out.append(table_md(prio_b, "Prioridade B — Catálogo com SVG apenas (upgrade AI)"))
    out.append("## Prioridade C — Vanilla oficial (99) sem WebP aprovado ou na fila regen")
    out.append("")
    out.append(f"**Total: {len(prio_c)}**")
    out.append("")
    out.append("| species_key | display_name | origin | current_status | in_catalog? | nota regen | ref sugerida |")
    out.append("|-------------|--------------|--------|----------------|-------------|------------|--------------|")
    for row in sorted(prio_c, key=lambda x: x["display_name"].lower()):
        note = row["regen_note"] or "—"
        in_cat = "sim" if row["in_catalog"] else "não"
        out.append(
            f"| `{row['species_key']}` | {row['display_name']} | {row['origin']} | {row['status']} | {in_cat} | {note} | "
            f"`refs/species_icons/{row['canonical']}.png` |"
        )
    out.append("")
    out.append(table_md(prio_d, "Prioridade D — SVG no disco sem WebP correspondente"))
    out.append("## SVG sem WebP (candidatos diretos)")
    out.append("")
    out.append("Arquivos `icons/*.svg` cujo `generated/{canonical}.webp` **não existe**:")
    out.append("")
    for stem in sorted({r["svg"] for r in prio_d if r["svg"]}):
        c = canonical(stem)
        out.append(f"- `{stem}.svg` → falta `generated/{c}.webp`")
    out.append("")
    out.append("---")
    out.append("")
    out.append("## Já tem referência salva")
    out.append("")
    if saved_refs:
        out.append("| arquivo | espécie provável | já tem WebP? |")
        out.append("|---------|------------------|--------------|")
        for stem, fname in sorted(saved_refs.items()):
            webp = has_webp(stem)
            out.append(f"| `{fname}` | `{stem}` | {'sim' if webp else 'não'} |")
    else:
        out.append("_Pasta `refs/species_icons/` não encontrada ou vazia._")
    out.append("")
    out.append("## Já aprovados / done na fila")
    out.append("")
    out.append("Espécies marcadas como concluídas em `docs/SPECIES_ICON_REGEN_QUEUE.md`:")
    out.append("")
    out.append("| species_key | display_name | status atual | WebP |")
    out.append("|-------------|--------------|--------------|------|")
    for row in sorted(done_rows, key=lambda x: x["species_key"]):
        webp_name = f"`{row['webp']}.webp`" if row["webp"] else "—"
        out.append(f"| `{row['species_key']}` | {row['display_name']} | {row['status']} | {webp_name} |")
    out.append("")
    out.append("## Fila regen pendente (`generated/manifest.json`)")
    out.append("")
    out.append("| # | species_key | nota | ref sugerida | já tem ref salva? |")
    out.append("|---|-------------|------|--------------|-------------------|")
    for i, item in enumerate(ai_manifest.get("regen_queue", []), 1):
        sk = item["species_key"]
        c = canonical(sk)
        has_ref = "sim" if c in saved_refs or sk in saved_refs else "não"
        out.append(
            f"| {i} | `{sk}` | {item.get('note', '')} | `refs/species_icons/{c}.png` | {has_ref} |"
        )
    out.append("")
    out.append("---")
    out.append("")
    out.append("## Fontes auditadas")
    out.append("")
    out.append("- `plugin/arkshop_web/static/species/icons/*.svg`")
    out.append("- `plugin/arkshop_web/static/species/icons/generated/*.webp`")
    out.append("- `plugin/arkshop_web/data/species_icons_manifest.json`")
    out.append("- `plugin/arkshop_web/static/species/icons/generated/manifest.json`")
    out.append("- `plugin/arkshop_web/data/market_species_defaults.json`")
    out.append("- `plugin/arkshop_web/data/ark_species_registry.json`")
    out.append("- `plugin/arkshop_web/data/official_vanilla_species.json`")
    out.append("- `plugin/CustomShop/configs/config.json` (Items Type:dino)")
    out.append("- `refs/species_icons/` (referências do usuário)")
    out.append("")
    out.append("## Aliases canônicos (1 WebP para várias chaves)")
    out.append("")
    for alias, canon in sorted(ALIASES.items()):
        out.append(f"- `{alias}` → `{canon}`")

    DOCS.parent.mkdir(parents=True, exist_ok=True)
    DOCS.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Wrote {DOCS}")
    print(f"Prioridade A: {len(prio_a)} | B: {len(prio_b)} | C: {len(prio_c)} | D: {len(prio_d)}")


if __name__ == "__main__":
    main()
