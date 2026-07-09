#!/usr/bin/env python3
# Anatomy reference only — artwork © Dan Leveille (DodoDex). Internal use for AI generation.
# NOT for redistribution. Downloaded PNGs stay in refs/resource_icons/ as visual guides.
"""Baixa imagens de referência do DodoDex para refs/resource_icons/{rec_key}.png."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("Instale requests: pip install requests", file=sys.stderr)
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"
MAPPING_PATH = ROOT / "plugin" / "arkshop_web" / "data" / "dododex_resource_slugs.json"
REFS_DIR = ROOT / "refs" / "resource_icons"

SITEMAP_URL = "https://www.dododex.com/sitemap.xml"
ITEM_PAGE_URL = "https://www.dododex.com/item/{item_id}/{slug}"
ITEM_IMAGE_URL = "https://www.dododex.com/media/item/{image_name}.png"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.dododex.com/",
}

# rec_key → slug DodoDex (/item/{id}/{slug}) quando difere de rec_{nome}
MANUAL_SLUG_OVERRIDES: dict[str, str | None] = {
    "rec_HardenedSteelIngot": None,  # mod Abyss — ausente no DodoDex
    "rec_bolo": "sweet-vegetable-cake",
    "rec_cement": "cementing-paste",
    "rec_cookedmeat": "cooked-meat",
    "rec_elementore": "element-ore",
    "rec_gemblue": "blue-gem",
    "rec_gemgreen": "green-gem",
    "rec_gemred": "red-gem",
    "rec_honey": "giant-bee-honey",
    "rec_medicalbrew": "medical-brew",
    "rec_metalingot": "metal-ingot",
    "rec_manganese": None,  # mod Abyss — ausente no DodoDex
    "rec_organicpolymer": "organic-polymer",
    "rec_pnegra": "black-pearl",
    "rec_rareflower": "rare-flower",
    "rec_raremushroom": "rare-mushroom",
    "rec_silicon": "silicon",
    "rec_wyvernmilk": "wyvern-milk",
}

# rec_key → nome do arquivo em /media/item/{name}.png (quando slug→nome falha)
MANUAL_IMAGE_OVERRIDES: dict[str, str] = {}


def load_rec_catalog() -> dict[str, dict]:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    items = data.get("Items") or {}
    catalog: dict[str, dict] = {}
    for key, entry in items.items():
        if not key.startswith("rec_"):
            continue
        blueprint = ""
        item_rows = entry.get("Items") or []
        if item_rows and isinstance(item_rows[0], dict):
            blueprint = item_rows[0].get("Blueprint") or ""
        catalog[key] = {
            "description": entry.get("Description") or entry.get("Name") or "",
            "blueprint": blueprint,
            "type": entry.get("Type") or "item",
        }
    return catalog


def fetch_sitemap_items(session: requests.Session) -> dict[str, tuple[str, str]]:
    """slug → (item_id, slug) a partir de /item/{id}/{slug} no sitemap."""
    try:
        resp = session.get(SITEMAP_URL, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"WARN: sitemap indisponível ({exc}); mapeamento parcial.")
        return {}
    pairs = re.findall(
        r"<loc>https://www\.dododex\.com/item/(\d+)/([a-z0-9_-]+)</loc>",
        resp.text,
    )
    by_slug: dict[str, tuple[str, str]] = {}
    for item_id, slug in pairs:
        by_slug[slug] = (item_id, slug)
    return by_slug


def slug_to_image_name(slug: str) -> str:
    """metal-ingot → Metal_Ingot, stone → Stone."""
    parts = [p for p in slug.split("-") if p]
    return "_".join(p[:1].upper() + p[1:] for p in parts)


def resolve_slug(rec_key: str, sitemap_items: dict[str, tuple[str, str]]) -> str | None:
    rk = rec_key.strip()
    if rk in MANUAL_SLUG_OVERRIDES:
        return MANUAL_SLUG_OVERRIDES[rk]  # None = explicitamente indisponível
    candidate = rk[4:].lower() if rk.lower().startswith("rec_") else rk.lower()
    if candidate in sitemap_items:
        return candidate
    return candidate


def resolve_image_name(
    rec_key: str,
    slug: str | None,
    session: requests.Session,
    sitemap_items: dict[str, tuple[str, str]],
) -> tuple[str | None, str | None]:
    """Retorna (image_name, source) onde source = override|slug|og_image."""
    if rec_key in MANUAL_IMAGE_OVERRIDES:
        return MANUAL_IMAGE_OVERRIDES[rec_key], "override"

    if slug:
        derived = slug_to_image_name(slug)
        url = ITEM_IMAGE_URL.format(image_name=derived)
        try:
            resp = session.head(url, timeout=20, allow_redirects=True)
            if resp.status_code == 200:
                return derived, "slug"
        except requests.RequestException:
            pass

        if slug in sitemap_items:
            item_id, _ = sitemap_items[slug]
            page_url = ITEM_PAGE_URL.format(item_id=item_id, slug=slug)
            try:
                page = session.get(page_url, timeout=30)
                if page.status_code == 200:
                    og = re.findall(
                        r'property="og:image" content="([^"]+)"',
                        page.text,
                    )
                    if og:
                        name = og[0].rstrip("/").rsplit("/", 1)[-1]
                        if name.lower().endswith(".png"):
                            name = name[:-4]
                        return name, "og_image"
            except requests.RequestException:
                pass

    return None, None


def build_mapping(
    catalog: dict[str, dict],
    sitemap_items: dict[str, tuple[str, str]],
    session: requests.Session,
) -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    for rec_key in sorted(catalog):
        slug = resolve_slug(rec_key, sitemap_items)
        item_id = sitemap_items[slug][0] if slug and slug in sitemap_items else None
        image_name, image_source = resolve_image_name(
            rec_key, slug, session, sitemap_items
        )
        entry: dict = {
            "slug": slug,
            "item_id": item_id,
            "image_name": image_name,
            "image_url": (
                ITEM_IMAGE_URL.format(image_name=image_name) if image_name else None
            ),
            "image_source": image_source,
            "blueprint": catalog[rec_key]["blueprint"],
            "description": catalog[rec_key]["description"],
        }
        if slug and item_id:
            entry["page_url"] = ITEM_PAGE_URL.format(item_id=item_id, slug=slug)
        mapping[rec_key] = entry
    return mapping


def save_mapping(
    mapping: dict[str, dict],
    *,
    sitemap_count: int,
    catalog_count: int,
) -> None:
    mapped_with_image = sum(1 for m in mapping.values() if m.get("image_name"))
    payload = {
        "_comment": (
            "rec_key ARKLAND → slug/nome DodoDex para /media/item/{ImageName}.png. "
            "Páginas: /item/{id}/{slug}. Anatomy reference only — © Dan Leveille, "
            "internal AI generation use."
        ),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "tools/fetch_dododex_resource_references.py",
        "dododex_url_patterns": {
            "item_page": "https://www.dododex.com/item/{item_id}/{slug}",
            "item_image": "https://www.dododex.com/media/item/{image_name}.png",
            "notes": (
                "Itens usam /media/item/{PascalCase_With_Underscores}.png — diferente "
                "de criaturas (/media/creature/{slug}.png). Slugs vêm do sitemap "
                "(/item/{id}/{slug}); o nome do PNG nem sempre coincide com o slug "
                "em minúsculas (ex.: giant-bee-honey → Giant_Bee_Honey.png)."
            ),
        },
        "dododex_sitemap_item_count": sitemap_count,
        "catalog_rec_count": catalog_count,
        "mapped_with_image_count": mapped_with_image,
        "mapping": mapping,
    }
    MAPPING_PATH.parent.mkdir(parents=True, exist_ok=True)
    MAPPING_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Mapping salvo: {MAPPING_PATH.relative_to(ROOT)} "
        f"({len(mapping)} rec_*, {mapped_with_image} com imagem)"
    )


def download_one(
    session: requests.Session,
    rec_key: str,
    meta: dict,
    *,
    dry_run: bool,
    skip_existing: bool,
    delay: float,
) -> str:
    image_name = meta.get("image_name")
    if not image_name:
        reason = "sem slug/imagem" if meta.get("slug") is None else "imagem não resolvida"
        print(f"  SKIP  {rec_key}: {reason}")
        return "unavailable"

    out_path = REFS_DIR / f"{rec_key}.png"
    url = meta.get("image_url") or ITEM_IMAGE_URL.format(image_name=image_name)

    if skip_existing and out_path.is_file():
        print(f"  SKIP  {rec_key} -> {image_name} (ja existe, --skip-existing)")
        return "skipped"

    if dry_run:
        existed = out_path.is_file()
        action = "REPLACE" if existed else "DOWNLOAD"
        print(f"  DRY   {action} {rec_key} -> {image_name} ({url})")
        return "replaced" if existed else "downloaded"

    existed = out_path.is_file()
    try:
        resp = session.get(url, timeout=30)
    except requests.RequestException as exc:
        print(f"  ERROR {rec_key} -> {image_name}: {exc}")
        return "error"

    if resp.status_code == 404:
        print(f"  404   {rec_key} -> {image_name}")
        return "not_found"
    if resp.status_code == 403:
        print(f"  403   {rec_key} -> {image_name}")
        return "forbidden"
    if resp.status_code != 200:
        print(f"  HTTP  {rec_key} -> {image_name}: {resp.status_code}")
        return "error"

    content_type = (resp.headers.get("Content-Type") or "").lower()
    if "image" not in content_type and len(resp.content) < 1000:
        print(
            f"  ERROR {rec_key} -> {image_name}: "
            f"resposta nao parece imagem ({content_type})"
        )
        return "error"

    REFS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(resp.content)
    action = "REPLACED" if existed else "OK"
    print(f"  {action:7} {rec_key} -> {image_name} ({len(resp.content):,} bytes)")
    time.sleep(delay)
    return "replaced" if existed else "downloaded"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Baixa referências visuais DodoDex para refs/resource_icons/."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Só mostra o que seria baixado, sem gravar arquivos.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Não sobrescrever PNGs já presentes.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Segundos entre downloads (padrão: 1.5).",
    )
    parser.add_argument(
        "--resources",
        nargs="*",
        help="Baixar só estas rec_key (padrão: todas do catálogo).",
    )
    args = parser.parse_args()

    if not CONFIG_PATH.is_file():
        print(f"ERRO: {CONFIG_PATH} não encontrado.", file=sys.stderr)
        return 1

    catalog = load_rec_catalog()
    if not catalog:
        print("ERRO: nenhum rec_* encontrado no catálogo.", file=sys.stderr)
        return 1

    rec_keys = sorted(catalog)
    if args.resources:
        wanted = {r if r.startswith("rec_") else f"rec_{r}" for r in args.resources}
        rec_keys = [k for k in rec_keys if k in wanted]
        missing = wanted - set(rec_keys)
        if missing:
            print(f"WARN: rec_key desconhecidas: {', '.join(sorted(missing))}")

    session = requests.Session()
    session.headers.update(HEADERS)

    print("Consultando sitemap DodoDex (itens)…")
    sitemap_items = fetch_sitemap_items(session)
    if sitemap_items:
        print(f"  {len(sitemap_items)} itens no sitemap.")

    print("Resolvendo slugs e nomes de imagem…")
    mapping = build_mapping(catalog, sitemap_items, session)
    if not args.dry_run:
        save_mapping(
            mapping,
            sitemap_count=len(sitemap_items),
            catalog_count=len(catalog),
        )

    mode = "dry-run" if args.dry_run else ("skip-existing" if args.skip_existing else "overwrite")
    print(f"\nBaixando {len(rec_keys)} referências ({mode})…\n")

    stats: dict[str, int] = {}
    failed: list[str] = []
    unavailable: list[str] = []

    for rk in rec_keys:
        result = download_one(
            session,
            rk,
            mapping[rk],
            dry_run=args.dry_run,
            skip_existing=args.skip_existing,
            delay=0 if args.dry_run else args.delay,
        )
        stats[result] = stats.get(result, 0) + 1
        if result in ("not_found", "forbidden", "error"):
            failed.append(rk)
        if result == "unavailable":
            unavailable.append(rk)

    png_count = len(list(REFS_DIR.glob("*.png"))) if REFS_DIR.is_dir() else 0

    print("\n--- Resumo ---")
    print(f"  rec_* no catálogo:    {len(catalog)}")
    print(f"  Mapeados c/ imagem:   {sum(1 for m in mapping.values() if m.get('image_name'))}")
    print(f"  Baixados (novos):     {stats.get('downloaded', 0)}")
    print(f"  Substituídos:         {stats.get('replaced', 0)}")
    print(f"  Ignorados (existente):{stats.get('skipped', 0)}")
    print(f"  Indisponíveis:        {stats.get('unavailable', 0)}")
    print(f"  404:                  {stats.get('not_found', 0)}")
    print(f"  403:                  {stats.get('forbidden', 0)}")
    print(f"  Erros:                {stats.get('error', 0)}")
    print(f"  PNGs em refs/:        {png_count}")
    if unavailable:
        print(f"  Sem DodoDex:          {', '.join(sorted(unavailable))}")
    if failed:
        print(f"  Falhas download:      {', '.join(sorted(failed))}")

    return 1 if failed and not args.dry_run else 0


if __name__ == "__main__":
    raise SystemExit(main())
