#!/usr/bin/env python3
# Internal reference only — images © Studio Wildcard via ark.wiki.gg (CC BY-NC-SA).
# NOT for redistribution in shop. See plugin/arkshop_web/static/species/ATTRIBUTION.md
"""Baixa ícones de recursos/itens Aquatica/Abyss de ark.wiki.gg para refs/resource_icons/."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("Instale requests: pip install requests", file=sys.stderr)
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parents[1]
REFS_DIR = ROOT / "refs" / "resource_icons"
CONFIG_PATH = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"
MAPPING_PATH = ROOT / "plugin" / "arkshop_web" / "data" / "wiki_resource_refs.json"

API = "https://ark.wiki.gg/api.php"
HEADERS = {"User-Agent": "arkland-multi/1.0 (internal wiki ref fetch)"}

# catalog_key → (wiki File: name, local ref filename)
# Itens Abyss/Aquatica vendidos na loja — mapeamento explícito quando o nome wiki difere.
WIKI_ITEM_MAP: dict[str, tuple[str, str]] = {
    # Resources (wiki #Resources)
    "abyss_aqualyrium": ("Aqualyrium.png", "rec_aqualyrium.png"),
    "abyss_barnacle": ("Barnacle.png", "rec_barnacle.png"),
    "abyss_crystallized_wood": ("Crystallized_Wood.png", "rec_crystallizedWood.png"),
    "abyss_fish_scale": ("Fish_Scale.png", "rec_fishScale.png"),
    "abyss_hardened_steel": ("Hardened_Steel_Ingot.png", "rec_HardenedSteelIngot.png"),
    "abyss_manganese": ("Manganese.png", "rec_manganese.png"),
    "abyss_seaweed": ("Seaweed.png", "rec_seaweed.png"),
    # Seeds
    "abyss_seed_cucumis": ("Cucumis_Seed.png", "abyss_seed_cucumis.png"),
    "abyss_seed_rice": ("Oryraise_Seed.png", "abyss_seed_rice.png"),
    "abyss_seed_plantspeciesw": ("Plant_Species_W_Seed.png", "abyss_seed_plantspeciesw.png"),
    # Consumíveis Aquatica no catálogo
    "daco_sushi": ("Daco_Sushi.png", "daco_sushi.png"),
    # Veículos Abyss (Type=item, vendidos na loja)
    "abyss_hover_sail": ("Tek_Thalassian_Hoversail.png", "abyss_hover_sail.png"),
    "abyss_hover_skiff": (
        "Unassembled_TEK_Thalassian_Hover_Skiff.png",
        "abyss_hover_skiff.png",
    ),
}

# Não sobrescrever refs fornecidas pelo usuário
SKIP_IF_EXISTS: set[str] = {"rec_HardenedSteelIngot.png", "rec_manganese.png"}


def load_catalog() -> dict[str, dict]:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return data.get("Items") or {}


def is_abyss_sellable(key: str, entry: dict) -> bool:
    """Itens Abyss/Aquatica vendidos que precisam de ref wiki."""
    if not key.startswith("abyss_") and key != "daco_sushi":
        return False
    if entry.get("Type") != "item":
        return False
    bp = entry.get("Blueprint") or ""
    if entry.get("Items"):
        rows = entry.get("Items") or []
        if rows and isinstance(rows[0], dict):
            bp = rows[0].get("Blueprint") or bp
    if "/Game/Abyss/" not in bp:
        return False
    # Recursos, sementes, consumíveis catalogados, veículos
    if key in WIKI_ITEM_MAP:
        return True
    if "PrimalItemResource_" in bp:
        return True
    if "PrimalItemConsumable_Seed_" in bp:
        return True
    if entry.get("Category") == "Recursos":
        return True
    return key in ("abyss_hover_sail", "abyss_hover_skiff")


def discover_items(catalog: dict[str, dict]) -> dict[str, tuple[str, str]]:
    """Retorna catalog_key → (wiki_file, local_name) para todos os itens Abyss vendidos."""
    discovered: dict[str, tuple[str, str]] = dict(WIKI_ITEM_MAP)
    for key, entry in catalog.items():
        if not is_abyss_sellable(key, entry):
            continue
        if key in discovered:
            continue
        desc = entry.get("Description") or entry.get("Name") or key
        # fallback: derivar do blueprint
        bp = entry.get("Blueprint") or ""
        m = re.search(r"PrimalItem(?:Resource|Consumable)_(?:Seed_)?(\w+)", bp)
        if m:
            wiki_base = re.sub(r"([a-z])([A-Z])", r"\1 \2", m.group(1))
            wiki_file = wiki_base.replace(" ", "_") + ".png"
            local = f"{key}.png"
            discovered[key] = (wiki_file, local)
    return discovered


def fetch_image_url(session: requests.Session, filename: str) -> str | None:
    """Resolve File: URL — wiki titles use spaces, storage uses underscores."""
    candidates = [
        filename,
        filename.replace("_", " "),
    ]
    for candidate in dict.fromkeys(candidates):
        resp = session.get(
            API,
            params={
                "action": "query",
                "titles": f"File:{candidate}",
                "prop": "imageinfo",
                "iiprop": "url",
                "format": "json",
            },
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        for page in resp.json()["query"]["pages"].values():
            if page.get("missing"):
                continue
            info = (page.get("imageinfo") or [{}])[0]
            if info.get("url"):
                return info["url"]
    return None


def download(session: requests.Session, url: str, dest: Path) -> bool:
    resp = session.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return True


def main() -> int:
    REFS_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    catalog = load_catalog()
    all_items = discover_items(catalog)

    mapping_entries: dict[str, dict] = {}
    downloaded: list[str] = []
    skipped: list[str] = []
    already: list[str] = []
    failed: list[str] = []

    for catalog_key, (wiki_file, local_name) in sorted(all_items.items()):
        dest = REFS_DIR / local_name
        wiki_url = fetch_image_url(session, wiki_file)
        wiki_page = wiki_file.replace(".png", "").replace("_", " ")
        entry = {
            "catalog_key": catalog_key,
            "wiki_page": wiki_page,
            "wiki_file": wiki_file,
            "wiki_url": wiki_url,
            "reference_path": f"refs/resource_icons/{local_name}",
            "image_source": "wiki_reference_internal",
            "source": "ark.wiki.gg",
            "attribution": "© Studio Wildcard — internal AI reference only, not for shop redistribution",
        }

        if local_name in SKIP_IF_EXISTS and dest.exists():
            entry["status"] = "skipped_user_provided"
            skipped.append(f"{catalog_key} -> {local_name} (usuario)")
            mapping_entries[catalog_key] = entry
            continue

        if dest.exists() and local_name not in SKIP_IF_EXISTS:
            entry["status"] = "already_exists"
            already.append(f"{catalog_key} -> {local_name}")
            mapping_entries[catalog_key] = entry
            continue

        if not wiki_url:
            entry["status"] = "failed_no_url"
            failed.append(f"{catalog_key}: URL não encontrada para {wiki_file}")
            mapping_entries[catalog_key] = entry
            continue

        try:
            download(session, wiki_url, dest)
            entry["status"] = "downloaded"
            downloaded.append(f"{catalog_key} -> {dest.name}")
        except requests.RequestException as exc:
            entry["status"] = "failed_download"
            entry["error"] = str(exc)
            failed.append(f"{catalog_key}: {exc}")

        mapping_entries[catalog_key] = entry

    payload = {
        "_comment": "Referências visuais internas de ark.wiki.gg para recursos/itens Aquatica/Abyss vendidos na loja. NÃO redistribuir.",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "ark.wiki.gg",
        "image_source": "wiki_reference_internal",
        "fetch_tool": "tools/fetch_wiki_aquatica_resource_refs.py",
        "attribution_note": "Imagens © Studio Wildcard via wiki comunitária. Uso interno para geração AI — ver ATTRIBUTION.md",
        "catalog_abyss_item_count": len(all_items),
        "mapping": mapping_entries,
    }
    MAPPING_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"=== Itens Abyss/Aquatica no escopo: {len(all_items)} ===")
    print("=== Baixados nesta execução ===")
    for line in downloaded:
        print(f"  OK {line}")
    print("=== Já existiam ===")
    for line in already:
        print(f"  EXISTS {line}")
    print("=== Ignorados (usuario) ===")
    for line in skipped:
        print(f"  SKIP {line}")
    print("=== Falhas ===")
    for line in failed:
        print(f"  FAIL {line}")
    print(f"\nMapping: {MAPPING_PATH}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
