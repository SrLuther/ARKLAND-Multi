#!/usr/bin/env python3
# Anatomy reference only — artwork © Dan Leveille (DodoDex). Internal use for AI generation.
# NOT for redistribution. Downloaded PNGs stay in refs/species_icons/ as anatomy guides.
"""Baixa imagens de anatomia do DodoDex para refs/species_icons/{species_key}.png."""
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
WEB = ROOT / "plugin" / "arkshop_web"
OFFICIAL_PATH = WEB / "data" / "official_vanilla_species.json"
MAPPING_PATH = WEB / "data" / "dododex_species_slugs.json"
REFS_DIR = ROOT / "refs" / "species_icons"

DODO_URL = "https://www.dododex.com/media/creature/{slug}.png"
SITEMAP_URL = "https://www.dododex.com/sitemap.xml"

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

# species_key → dododex_slug (quando difere do nome ARKLAND)
MANUAL_SLUG_OVERRIDES: dict[str, str] = {
    "giga": "giganotosaurus",
    "gigant": "giganotosaurus",
    "bionicgigant": "giganotosaurus",
    "quetz": "quetzal",
    "yuty": "yutyrannus",
    "ankylo": "ankylosaurus",
    "rhynio": "rhyniognatha",
    "tekstrider": "stryder",
    "tekstrider_femea": "stryder",
    "lionfishlion": "shadowmane",
    "lionfish_femea": "shadowmane",
    "beaver": "castoroides",
    "doed": "doedicurus",
    "xenomorph": "reaper",
    "xenomorph_femea": "reaper",
    "xenomorphgen2_femea": "reaper",
    "bronto": "brontosaurus",
    "ptera": "pteranodon",
    "trike": "triceratops",
    "allo": "allosaurus",
    "carno": "carnotaurus",
    "spino": "spinosaur",
    "theriz": "therizinosaurus",
    "owl": "snowowl",
    "bionicrex": "rex",
    "volcanorex": "rex",
    "carcha_femea": "carcharodontosaurus",
    "deinonychus_femea": "deinonychus",
    "megalosaurus_femea": "megalosaurus",
    "megalosaurus_aberrant_femea": "megalosaurus",
    "dunkle": "dunkleosteus",
    "tuso": "tusoteuthis",
    "para": "parasaur",
    "thyla": "thylacoleo",
    "stego": "stegosaurus",
    "dimorph": "dimorphodon",
    "argent": "argentavis",
    "titanboa": "titanoboa",
}


def load_official_species_keys() -> list[str]:
    data = json.loads(OFFICIAL_PATH.read_text(encoding="utf-8"))
    return [s["species_key"] for s in data["species"]]


def fetch_dododex_sitemap_slugs(session: requests.Session) -> set[str]:
    """Todos os slugs /taming/{slug} indexados no sitemap DodoDex."""
    try:
        resp = session.get(SITEMAP_URL, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"WARN: sitemap indisponível ({exc}); usando só overrides manuais.")
        return set()
    return set(re.findall(r"/taming/([a-z0-9_-]+)", resp.text))


def resolve_slug(species_key: str, sitemap_slugs: set[str]) -> str:
    sk = species_key.lower().strip()
    if sk in MANUAL_SLUG_OVERRIDES:
        return MANUAL_SLUG_OVERRIDES[sk]
    if sitemap_slugs and sk in sitemap_slugs:
        return sk
    return sk


def build_mapping(species_keys: list[str], sitemap_slugs: set[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for sk in species_keys:
        mapping[sk] = resolve_slug(sk, sitemap_slugs)
    return mapping


def save_mapping(
    mapping: dict[str, str],
    *,
    sitemap_count: int,
    species_count: int,
) -> None:
    payload = {
        "_comment": (
            "species_key ARKLAND → slug DodoDex para /media/creature/{slug}.png. "
            "Anatomy reference only — © Dan Leveille, internal AI generation use."
        ),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "tools/fetch_dododex_references.py",
        "dododex_sitemap_creature_count": sitemap_count,
        "official_vanilla_count": species_count,
        "mapping": dict(sorted(mapping.items())),
    }
    MAPPING_PATH.parent.mkdir(parents=True, exist_ok=True)
    MAPPING_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Mapping salvo: {MAPPING_PATH.relative_to(ROOT)} ({len(mapping)} entradas)")


def download_one(
    session: requests.Session,
    species_key: str,
    slug: str,
    *,
    dry_run: bool,
    skip_existing: bool,
    delay: float,
) -> str:
    """Retorna: downloaded | replaced | skipped | not_found | forbidden | error."""
    out_path = REFS_DIR / f"{species_key}.png"
    url = DODO_URL.format(slug=slug)

    if skip_existing and out_path.is_file():
        print(f"  SKIP  {species_key} -> {slug} (ja existe, --skip-existing)")
        return "skipped"

    if dry_run:
        existed = out_path.is_file()
        action = "REPLACE" if existed else "DOWNLOAD"
        print(f"  DRY   {action} {species_key} -> {slug} ({url})")
        return "replaced" if existed else "downloaded"

    existed = out_path.is_file()
    try:
        resp = session.get(url, timeout=30)
    except requests.RequestException as exc:
        print(f"  ERROR {species_key} -> {slug}: {exc}")
        return "error"

    if resp.status_code == 404:
        print(f"  404   {species_key} -> {slug}")
        return "not_found"
    if resp.status_code == 403:
        print(f"  403   {species_key} -> {slug}")
        return "forbidden"
    if resp.status_code != 200:
        print(f"  HTTP  {species_key} -> {slug}: {resp.status_code}")
        return "error"

    content_type = (resp.headers.get("Content-Type") or "").lower()
    if "image" not in content_type and len(resp.content) < 1000:
        print(f"  ERROR {species_key} -> {slug}: resposta nao parece imagem ({content_type})")
        return "error"

    REFS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(resp.content)
    action = "REPLACED" if existed else "OK"
    print(f"  {action:7} {species_key} -> {slug} ({len(resp.content):,} bytes)")
    time.sleep(delay)
    return "replaced" if existed else "downloaded"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Baixa referências de anatomia DodoDex para refs/species_icons/."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Só mostra o que seria baixado, sem gravar arquivos.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Não sobrescrever PNGs já presentes (comportamento antigo).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Segundos entre downloads (padrão: 1.5).",
    )
    parser.add_argument(
        "--species",
        nargs="*",
        help="Baixar só estas species_key (padrão: todas as 99 oficiais).",
    )
    args = parser.parse_args()

    if not OFFICIAL_PATH.is_file():
        print(f"ERRO: {OFFICIAL_PATH} não encontrado.", file=sys.stderr)
        return 1

    species_keys = load_official_species_keys()
    if args.species:
        wanted = {s.lower() for s in args.species}
        species_keys = [sk for sk in species_keys if sk in wanted]
        missing = wanted - set(species_keys)
        if missing:
            print(f"WARN: species_key desconhecidas: {', '.join(sorted(missing))}")

    session = requests.Session()
    session.headers.update(HEADERS)

    print("Consultando sitemap DodoDex…")
    sitemap_slugs = fetch_dododex_sitemap_slugs(session)
    if sitemap_slugs:
        print(f"  {len(sitemap_slugs)} criaturas no sitemap.")

    mapping = build_mapping(species_keys, sitemap_slugs)
    if not args.dry_run:
        save_mapping(mapping, sitemap_count=len(sitemap_slugs), species_count=len(species_keys))

    mode = "dry-run" if args.dry_run else ("skip-existing" if args.skip_existing else "overwrite")
    print(f"\nBaixando {len(species_keys)} referências ({mode})…\n")

    stats = {
        "downloaded": 0,
        "replaced": 0,
        "skipped": 0,
        "not_found": 0,
        "forbidden": 0,
        "error": 0,
    }
    failed_keys: list[str] = []

    for sk in species_keys:
        slug = mapping[sk]
        result = download_one(
            session,
            sk,
            slug,
            dry_run=args.dry_run,
            skip_existing=args.skip_existing,
            delay=0 if args.dry_run else args.delay,
        )
        stats[result] = stats.get(result, 0) + 1
        if result in ("not_found", "forbidden", "error"):
            failed_keys.append(sk)

    png_count = len(list(REFS_DIR.glob("*.png"))) if REFS_DIR.is_dir() else 0

    print("\n--- Resumo ---")
    print(f"  Baixados (novos):     {stats.get('downloaded', 0)}")
    print(f"  Substituídos:         {stats.get('replaced', 0)}")
    print(f"  Ignorados (existente):{stats.get('skipped', 0)}")
    print(f"  404:                  {stats.get('not_found', 0)}")
    print(f"  403:                  {stats.get('forbidden', 0)}")
    print(f"  Erros:                {stats.get('error', 0)}")
    print(f"  PNGs em refs/:        {png_count}")
    if failed_keys:
        print(f"  Falhas:               {', '.join(sorted(failed_keys))}")

    return 1 if failed_keys and not args.dry_run else 0


if __name__ == "__main__":
    raise SystemExit(main())
