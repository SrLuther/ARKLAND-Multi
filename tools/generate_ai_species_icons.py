#!/usr/bin/env python3
"""Pipeline de ícones AI para espécies vanilla ARK — ARKLAND Web Store.

Gera retratos 1:1 com moldura canônica carno (metálica escura + logo ARK + nome + badge tier),
comprime para WebP 256×256 e mantém manifest em generated/manifest.json.

Uso:
  python tools/generate_ai_species_icons.py --list-only
  python tools/generate_ai_species_icons.py --compress-only
  python tools/generate_ai_species_icons.py --export-frame-template
  python tools/generate_ai_species_icons.py --prompt rex
  python tools/generate_ai_species_icons.py --species carno --reference refs/species_icons/carno.png
  python tools/generate_ai_species_icons.py --species rex --reference refs/species_icons/rex.png --frame-reference refs/species_icons/_frame_template_carno.png
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(WEB))

from ark_species_registry import VANILLA_CURATED  # noqa: E402

DEFAULTS_PATH = WEB / "data" / "market_species_defaults.json"
OVERLAY_PATH = WEB / "data" / "ark_species_registry.json"
OFFICIAL_LIST_PATH = WEB / "data" / "official_vanilla_species.json"
GENERATED_DIR = WEB / "static" / "species" / "icons" / "generated"
RAW_DIR = GENERATED_DIR / "raw"
MANIFEST_PATH = GENERATED_DIR / "manifest.json"
AI_MANIFEST_PATH = WEB / "data" / "species_ai_icons_manifest.json"
DEMO_DIR = WEB / "static" / "species" / "icons" / "demo"
FRAME_SPEC_PATH = WEB / "data" / "species_icon_frame_spec.json"
FRAME_TEMPLATE_REFS = ROOT / "refs" / "species_icons" / "_frame_template_carno.png"
FRAME_TEMPLATE_DEMO = DEMO_DIR / "frame_standard_carno.png"
DEFAULT_FRAME_REFERENCE = GENERATED_DIR / "raw" / "carno.png"
TRAITS_PATH = WEB / "data" / "species_icon_visual_traits.json"
FRAME_ASSETS_DIR = GENERATED_DIR / "_assets"
ARK_LOGO_CROP = FRAME_ASSETS_DIR / "ark_logo_crop.png"
ICON_CANVAS_SIZE = 1024

# Retrato (inset) — proporções derivadas do carno raw 1024×1024
PORTRAIT_INSET = (102, 118, 922, 820)  # left, top, right, bottom
NAMEPLATE_Y = 848

TIER_ORDER = {"S+": 0, "S": 1, "A": 2, "B": 3, "C": 4}
TIER_BADGE_FILL = "#2a1f14"
TIER_BADGE_BORDER = "#e8912d"
TIER_BADGE_LETTER = "#f0a030"
PORTRAIT_BACKGROUND = "#1a1a2e"

# Habitat inferido por role/nome quando não há entrada explícita em species_icon_visual_traits.json
_HABITAT_BY_ROLE: dict[str, str] = {
    "transport": "fly",
    "farm": "land",
    "utility": "land",
    "pvp": "land",
    "boss": "land",
}
_WATER_KEYWORDS = ("mosa", "megalodon", "plesio", "basilo", "tuso", "dunkle", "sarco", "megachelon", "archelon")
_FLY_KEYWORDS = ("wyvern", "quetz", "ptera", "tapejara", "pelagornis", "griffin", "owl", "argent", "tropeo", "desmodus", "pelagornis", "sinomacrops")

# Chaves duplicadas no registro que devem compartilhar o mesmo ícone canônico após regeneração.
CANONICAL_ICON_ALIASES: dict[str, str] = {
    "beaver": "castoroides",
    "doed": "doedicurus",
    "deinonychus_femea": "deinonychus",
    "tekstrider_femea": "tekstrider",
    "gigant": "giga",
    "giganotosaurus": "giga",
    "megalosaurus_femea": "megalosaurus",
    "megalosaurus_aberrant_femea": "megalosaurus",
    "xenomorph": "reaper",
    "xenomorph_femea": "reaper",
    "xenomorphgen2_femea": "reaper",
}

# Prompt para gerar SOMENTE o busto da criatura (composição PIL aplica a moldura depois).
CREATURE_BUST_PROMPT_TEMPLATE = """Square 1:1 creature portrait for ARK Survival Evolved icon compositing.
species_key: {species_key}
Creature: {english_name}
Habitat: {habitat}

MANDATORY distinctive anatomy:
{distinctive_features}

DO NOT include: {avoid_features}

Composition: creature bust/portrait close-up, three-quarter view, centered, species instantly recognizable.
Background: solid flat dark navy {portrait_bg} ONLY — no frame, no border, no text, no logo, no badge, no UI elements.
Cinematic rim lighting from upper right on creature, high-detail textures.
Fill ~75% of canvas with creature head and shoulders."""
FRAME_PROMPT_BLOCK = """MANDATORY STANDARD FRAME (identical layout for every species — only badge letter and name change):
- Square 1:1 ARK Survival Evolved store icon with thick dark weathered metallic rounded-square frame (carno style).
- Frame: gunmetal / brushed steel, beveled edges, silver highlights upper-left, subtle scratches, diagonal corner notches.
- Portrait inset inside frame: solid dark navy background {portrait_bg} ONLY — no scenery, no gradients in background.
- TOP-RIGHT on frame band: small ARK Survival Evolved logo (official-style, legible at thumbnail).
- TOP-LEFT on frame band: tier badge — rounded square, fill {badge_fill}, {badge_border} orange/amber border, letter "{tier}" in {badge_letter} bold centered.
- Tier {tier} = {tier_label}.
- BOTTOM-CENTER on frame band: creature display name text "{display_name}" in bold condensed sans-serif, light cream #{name_color}.
- Creature bust/portrait close-up in portrait inset, three-quarter view, species instantly recognizable at thumbnail size.
- Cinematic rim lighting from upper right on creature only, high-detail textures."""

PROMPT_TEMPLATE = """Square 1:1 ARK Survival Evolved game UI icon.
species_key: {species_key}
Creature: {english_name} ({display_name})
Habitat: {habitat}
Tier: {tier}

MANDATORY distinctive anatomy:
{distinctive_features}

DO NOT include: {avoid_features}

{frame_block}

CRITICAL: Frame structure, logo placement, name band, and tier badge position must match the canonical carno frame template exactly.
Only the tier letter, display name text, and creature portrait change per species."""

# Anexado quando o usuário fornece imagem de referência da espécie correta.
REFERENCE_PROMPT_SUFFIX = """
REFERENCE IMAGE (user-provided anatomy guide: {reference_name}):
Match ONLY the silhouette, head shape, body proportions, and distinctive anatomy shown in the reference.
Reproduce that creature's identity at thumbnail size — do NOT copy frame, background, colors, or lighting from the reference.
Do NOT borrow anatomy from any other ARK creature (no rex jaws on mosa, no elephant trunk on phiomia, etc.).
The reference confirms this is {english_name} ({species_key}) — stay faithful to that species.
Apply the creature inside the standard ARKLAND frame — reference is anatomy-only."""

# Anexado com --frame-reference: copiar layout da moldura, não a criatura.
FRAME_REFERENCE_SUFFIX = """
FRAME REFERENCE IMAGE ({frame_reference_name}):
Copy ONLY the outer frame geometry, metallic texture, corner notches, ARK logo placement, name band position, and tier badge placement from this reference.
Do NOT copy the creature portrait from the frame reference — use the species anatomy reference (or prompt) for the portrait inset.
Replace tier badge letter with "{tier}" and bottom name text with "{display_name}"."""

# Demos existentes → species_key do registro
DEMO_SPECIES_KEYS: dict[str, str] = {
    "rex": "rex",
    "giganotosaurus": "giga",
    "wyvern": "wyvern",
    "quetzalcoatlus": "quetz",
    "argentavis": "argent",
    "yutyrannus": "yuty",
    "therizinosaurus": "theriz",
    "shadowmane": "lionfishlion",
    "mosasaurus": "mosasaurus",
    "ankylosaurus": "ankylo",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_official_species_list() -> list[dict]:
    """Espécies vanilla/oficiais — exclui mods (mod_source, overlay mod, abyss_*)."""
    defaults = _load_json(DEFAULTS_PATH)
    overlay = _load_json(OVERLAY_PATH) if OVERLAY_PATH.is_file() else {"species": []}

    mod_keys = {e["species_key"] for e in overlay.get("species", []) if e.get("mod")}
    mod_from_defaults = {
        d["species_key"]
        for d in defaults.get("species", [])
        if d.get("species_key") and d.get("mod_source", "vanilla") != "vanilla"
    }

    official: dict[str, dict] = {}
    for d in defaults.get("species", []):
        sk = str(d.get("species_key") or "").strip()
        if not sk or sk in mod_keys or sk in mod_from_defaults or sk.startswith("abyss_"):
            continue
        official[sk] = {
            "species_key": sk,
            "display_name": d.get("display_name") or sk,
            "tier": d.get("tier") or "B",
            "source": "market_defaults",
        }

    for sk, dn, _token, tier, role, _rv in VANILLA_CURATED:
        if sk in mod_keys:
            continue
        if sk not in official:
            official[sk] = {
                "species_key": sk,
                "display_name": dn,
                "tier": tier,
                "source": "vanilla_curated",
                "role": role,
            }
        else:
            official[sk]["source"] = "both"

    items = sorted(
        official.values(),
        key=lambda x: (TIER_ORDER.get(x["tier"], 9), x["display_name"].lower()),
    )
    return items


def save_official_list(species: list[dict]) -> None:
    tier_counts = {t: sum(1 for s in species if s["tier"] == t) for t in TIER_ORDER}
    payload = {
        "_comment": "Espécies vanilla/oficiais ARK (sem mods). Gerado por tools/generate_ai_species_icons.py",
        "count": len(species),
        "tier_counts": tier_counts,
        "species": species,
    }
    OFFICIAL_LIST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@lru_cache(maxsize=1)
def _load_frame_spec() -> dict:
    if FRAME_SPEC_PATH.is_file():
        return json.loads(FRAME_SPEC_PATH.read_text(encoding="utf-8"))
    return {}


@lru_cache(maxsize=1)
def _tier_by_species_key() -> dict[str, str]:
    return {s["species_key"]: s.get("tier") or "B" for s in build_official_species_list()}


def resolve_tier(species_key: str, *, explicit: str | None = None) -> str:
    if explicit:
        return explicit.upper() if explicit.upper() != "S" else explicit
    tier = _tier_by_species_key().get(species_key.lower())
    if tier:
        return tier
    spec = _load_frame_spec()
    return str(spec.get("tier_resolution", {}).get("default") or "B")


def tier_label(tier: str) -> str:
    legend = _load_frame_spec().get("tier_legend", {})
    entry = legend.get(tier) or legend.get(tier.upper())
    if entry:
        return str(entry.get("label") or tier)
    return tier


def build_frame_prompt(*, tier: str, display_name: str) -> str:
    return FRAME_PROMPT_BLOCK.format(
        portrait_bg=PORTRAIT_BACKGROUND,
        display_name=display_name.strip(),
        name_color="e8e4dc",
        badge_fill=TIER_BADGE_FILL,
        badge_border=TIER_BADGE_BORDER,
        badge_letter=TIER_BADGE_LETTER,
        tier=tier,
        tier_label=tier_label(tier),
    )


def creature_bust_prompt(
    display_name: str,
    *,
    species_key: str | None = None,
    role: str = "",
    reference_path: Path | None = None,
) -> str:
    """Prompt para IA gerar apenas o busto — moldura aplicada via composite_standard_icon()."""
    sk = (species_key or display_name).strip().lower()
    meta = _traits_for(sk, display_name, role)
    prompt = CREATURE_BUST_PROMPT_TEMPLATE.format(
        species_key=meta["species_key"],
        english_name=meta["english_name"],
        habitat=meta["habitat"],
        distinctive_features="\n".join(f"- {f}" for f in meta["distinctive_features"]),
        avoid_features=", ".join(meta["avoid_features"]),
        portrait_bg=PORTRAIT_BACKGROUND,
    )
    if reference_path is not None:
        prompt += REFERENCE_PROMPT_SUFFIX.format(
            reference_name=reference_path.name,
            english_name=meta["english_name"],
            species_key=meta["species_key"],
        )
    return prompt


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    c = color.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _load_ark_logo():
    from PIL import Image

    if ARK_LOGO_CROP.is_file():
        with Image.open(ARK_LOGO_CROP) as im:
            return im.convert("RGBA")
    if FRAME_TEMPLATE_REFS.is_file():
        with Image.open(FRAME_TEMPLATE_REFS) as im:
            return im.crop((820, 18, 1006, 175)).convert("RGBA")
    raise FileNotFoundError("ARK logo crop not found — expected generated/_assets/ark_logo_crop.png")


def _draw_hex_grid(draw, box: tuple[int, int, int, int], color: tuple[int, int, int]) -> None:
    left, top, right, bottom = box
    step = 28
    r, g, b = color
    line = (min(r + 12, 255), min(g + 12, 255), min(b + 18, 255), 40)
    for y in range(top, bottom, step):
        offset = step // 2 if ((y - top) // step) % 2 else 0
        for x in range(left + offset, right, step):
            draw.polygon(
                [
                    (x, y + step // 4),
                    (x + step // 2, y),
                    (x + step, y + step // 4),
                    (x + step, y + 3 * step // 4),
                    (x + step // 2, y + step),
                    (x, y + 3 * step // 4),
                ],
                outline=line,
            )


def _draw_metal_frame(canvas) -> None:
    from PIL import ImageDraw

    draw = ImageDraw.Draw(canvas)
    w, h = canvas.size
    margin = int(w * 0.04)
    radius = int(w * 0.12)
    outer = (margin, margin, w - margin, h - margin)
    for i, (col, width) in enumerate(
        [
            (_hex_to_rgb("#1e2228"), 14),
            (_hex_to_rgb("#4a5058"), 8),
            (_hex_to_rgb("#6a7078"), 4),
            (_hex_to_rgb("#2a2e34"), 6),
        ]
    ):
        inset = i * 3
        draw.rounded_rectangle(
            (outer[0] + inset, outer[1] + inset, outer[2] - inset, outer[3] - inset),
            radius=max(4, radius - inset),
            outline=col,
            width=width,
        )
    notch = int(w * 0.06)
    highlight = _hex_to_rgb("#9aa0a8")
    for cx, cy, dx, dy in (
        (outer[0] + notch, outer[1] + notch, 1, 1),
        (outer[2] - notch, outer[1] + notch, -1, 1),
        (outer[0] + notch, outer[3] - notch, 1, -1),
        (outer[2] - notch, outer[3] - notch, -1, -1),
    ):
        draw.line([(cx, cy), (cx + dx * notch, cy)], fill=highlight, width=3)
        draw.line([(cx, cy), (cx, cy + dy * notch)], fill=highlight, width=3)


def _draw_tier_badge(canvas, tier: str) -> None:
    from PIL import Image, ImageDraw, ImageFont

    w, _ = canvas.size
    badge_size = int(w * 0.14)
    pad = int(w * 0.035)
    x1, y1 = pad, pad
    x2, y2 = x1 + badge_size, y1 + badge_size
    radius = int(badge_size * 0.18)

    badge = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(badge)
    fill = _hex_to_rgb(TIER_BADGE_FILL) + (255,)
    border = _hex_to_rgb(TIER_BADGE_BORDER)
    letter_col = _hex_to_rgb(TIER_BADGE_LETTER)
    draw.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=fill, outline=border, width=max(2, w // 256))
    label = tier
    font_size = int(badge_size * 0.42) if label == "S+" else int(badge_size * 0.55)
    try:
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = x1 + (badge_size - tw) // 2
    ty = y1 + (badge_size - th) // 2 - bbox[1]
    draw.text((tx, ty), label, fill=letter_col, font=font)
    canvas.alpha_composite(badge)


def _draw_nameplate(canvas, display_name: str) -> None:
    from PIL import Image, ImageDraw, ImageFont

    w, h = canvas.size
    plate_h = int(h * 0.11)
    y1 = h - int(h * 0.04) - plate_h
    y2 = y1 + plate_h
    plate = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(plate)
    metal = _hex_to_rgb("#3a3f47")
    draw.rounded_rectangle((int(w * 0.08), y1, int(w * 0.92), y2), radius=8, fill=metal + (230,))
    draw.rectangle((int(w * 0.08), y1, int(w * 0.92), y1 + 3), fill=_hex_to_rgb("#8a9098"))
    text = display_name.strip().upper()
    font_size = int(w * 0.065)
    try:
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    tx = (w - tw) // 2
    ty = y1 + (plate_h - (bbox[3] - bbox[1])) // 2 - bbox[1]
    draw.text((tx + 1, ty + 1), text, fill=(0, 0, 0, 160), font=font)
    draw.text((tx, ty), text, fill=_hex_to_rgb("#e8e4dc"), font=font)
    canvas.alpha_composite(plate)


def _paste_creature(canvas, creature) -> None:
    from PIL import Image

    left, top, right, bottom = PORTRAIT_INSET
    box_w, box_h = right - left, bottom - top
    creature = creature.convert("RGBA")
    cw, ch = creature.size
    scale = min(box_w / cw, box_h / ch) * 0.95
    nw, nh = max(1, int(cw * scale)), max(1, int(ch * scale))
    creature = creature.resize((nw, nh), Image.Resampling.LANCZOS)
    px = left + (box_w - nw) // 2
    py = top + (box_h - nh) // 2
    canvas.paste(creature, (px, py), creature)


def composite_standard_icon(creature, *, tier: str, display_name: str, size: int = ICON_CANVAS_SIZE):
    """Compõe ícone final: moldura carno + logo ARK + badge tier + nome (PIL determinístico)."""
    from PIL import Image, ImageDraw

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    if creature.size != (size, size):
        creature = creature.resize((size, size), Image.Resampling.LANCZOS)

    inset_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(inset_layer)
    bg = _hex_to_rgb(PORTRAIT_BACKGROUND)
    draw.rounded_rectangle(PORTRAIT_INSET, radius=16, fill=bg)
    _draw_hex_grid(draw, PORTRAIT_INSET, bg)
    canvas = Image.alpha_composite(canvas, inset_layer)

    _paste_creature(canvas, creature)
    _draw_metal_frame(canvas)
    _draw_tier_badge(canvas, tier)
    _draw_nameplate(canvas, display_name)

    logo = _load_ark_logo()
    logo_scale = int(size * 0.16)
    logo = logo.resize((logo_scale, int(logo_scale * logo.height / logo.width)), Image.Resampling.LANCZOS)
    lx = size - logo.width - int(size * 0.035)
    ly = int(size * 0.035)
    canvas.paste(logo, (lx, ly), logo)
    return canvas.convert("RGB")


def composite_species_icon(
    species_key: str,
    creature_path: Path,
    *,
    output_path: Path | None = None,
    display_name: str | None = None,
    tier: str | None = None,
) -> Path:
    """Compõe ícone canônico para uma espécie a partir de PNG de busto."""
    from PIL import Image

    sk = species_key.lower()
    by_key = {s["species_key"]: s for s in build_official_species_list()}
    entry = by_key.get(sk, {})
    dn = display_name or entry.get("display_name") or sk
    t = resolve_tier(sk, explicit=tier or entry.get("tier"))

    with Image.open(creature_path) as im:
        composed = composite_standard_icon(im, tier=t, display_name=dn)

    dest = output_path or (RAW_DIR / f"{sk}.png")
    dest.parent.mkdir(parents=True, exist_ok=True)
    composed.save(dest, format="PNG")
    register_raw(sk, dest.name, display_name=dn, tier=t, status="framed")
    return dest


def export_frame_template(*, source: Path | None = None) -> Path | None:
    """Copia carno.webp (ou source) para refs + demo como template de moldura."""
    src = source or DEFAULT_FRAME_REFERENCE
    if not src.is_file():
        src = FRAME_TEMPLATE_DEMO if FRAME_TEMPLATE_DEMO.is_file() else None
    if src is None or not src.is_file():
        return None

    from PIL import Image

    FRAME_TEMPLATE_REFS.parent.mkdir(parents=True, exist_ok=True)
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = im.convert("RGBA")
        for dest in (FRAME_TEMPLATE_REFS, FRAME_TEMPLATE_DEMO):
            im.save(dest, format="PNG")
    return FRAME_TEMPLATE_REFS


@lru_cache(maxsize=1)
def _load_visual_traits() -> dict:
    if TRAITS_PATH.is_file():
        return json.loads(TRAITS_PATH.read_text(encoding="utf-8"))
    return {"species": {}, "_habitat_fallbacks": {}, "frame_style": ""}


def _infer_habitat(species_key: str, role: str = "") -> str:
    traits = _load_visual_traits().get("species", {}).get(species_key, {})
    if traits.get("habitat"):
        return str(traits["habitat"])
    sk = species_key.lower()
    if any(k in sk for k in _WATER_KEYWORDS):
        return "water"
    if any(k in sk for k in _FLY_KEYWORDS):
        return "fly"
    return _HABITAT_BY_ROLE.get((role or "").lower(), "land")


def _traits_for(species_key: str, display_name: str, role: str = "") -> dict:
    data = _load_visual_traits()
    sk = CANONICAL_ICON_ALIASES.get(species_key.lower(), species_key.lower())
    entry = dict(data.get("species", {}).get(sk) or {})
    habitat = _infer_habitat(species_key, role)
    fallbacks = data.get("_habitat_fallbacks", {}).get(habitat, {})

    english = entry.get("english_name") or display_name.strip()
    if species_key == "lionfishlion":
        english = "Shadowmane (Lionfish Lion)"

    distinctive = list(entry.get("distinctive_features") or fallbacks.get("distinctive_features") or [])
    avoid = list(entry.get("avoid_features") or fallbacks.get("avoid_features") or [])

    if not distinctive:
        distinctive = [f"clearly recognizable {english} from ARK", f"{habitat} creature"]
    if not avoid:
        avoid = ["wrong species", "generic dinosaur"]

    return {
        "species_key": species_key,
        "english_name": english,
        "display_name": display_name.strip(),
        "habitat": habitat,
        "distinctive_features": distinctive,
        "avoid_features": avoid,
        "frame_style": data.get("frame_style", ""),
    }


def creature_prompt(
    display_name: str,
    *,
    species_key: str | None = None,
    role: str = "",
    tier: str | None = None,
    reference_path: Path | None = None,
    frame_reference_path: Path | None = None,
) -> str:
    sk = (species_key or display_name).strip().lower()
    meta = _traits_for(sk, display_name, role)
    resolved_tier = resolve_tier(sk, explicit=tier)
    prompt = PROMPT_TEMPLATE.format(
        species_key=meta["species_key"],
        english_name=meta["english_name"],
        display_name=meta["display_name"],
        habitat=meta["habitat"],
        tier=resolved_tier,
        distinctive_features="\n".join(f"- {f}" for f in meta["distinctive_features"]),
        avoid_features=", ".join(meta["avoid_features"]),
        frame_block=build_frame_prompt(tier=resolved_tier, display_name=meta["display_name"]),
    )
    if reference_path is not None:
        prompt += REFERENCE_PROMPT_SUFFIX.format(
            reference_name=reference_path.name,
            english_name=meta["english_name"],
            species_key=meta["species_key"],
        )
    if frame_reference_path is not None:
        prompt += FRAME_REFERENCE_SUFFIX.format(
            frame_reference_name=frame_reference_path.name,
            tier=resolved_tier,
            display_name=meta["display_name"],
        )
    return prompt


def mark_needs_regeneration(
    species_key: str,
    *,
    note: str = "",
    user_reported: bool = True,
) -> None:
    """Marca espécie no manifest como needs_regeneration com nota do usuário."""
    manifest = load_manifest()
    sk = species_key.lower()
    entry = manifest.setdefault("icons", {}).get(sk) or {"species_key": sk}
    entry["status"] = "needs_regeneration"
    entry["regen_note"] = note
    entry["user_reported"] = user_reported
    entry["marked_at"] = datetime.now(timezone.utc).isoformat()
    manifest["icons"][sk] = entry
    queue = manifest.setdefault("regen_queue", [])
    if not any(q.get("species_key") == sk for q in queue):
        queue.append({"species_key": sk, "note": note, "status": "pending"})
    save_manifest(manifest)


def load_manifest() -> dict:
    if MANIFEST_PATH.is_file():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "_comment": "Ícones AI originais ARKLAND — moldura metálica padronizada",
        "_frame_style": "carno_canonical_v1 — dark metallic rounded-square + ARK logo + name + tier badge",
        "_frame_spec": "data/species_icon_frame_spec.json",
        "_frame_template": "refs/species_icons/_frame_template_carno.png",
        "_background": "#1a1a2e",
        "_output_size": "256x256 webp",
        "_prompt_source": "data/species_icon_visual_traits.json",
        "_reference_policy": "NEVER use another creature image as reference — causes rex/mosa confusion",
        "generated_at": None,
        "icons": {},
        "failures": [],
    }


def save_manifest(manifest: dict) -> None:
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    manifest["count"] = len(manifest.get("icons") or {})
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def compress_image(src: Path, dest: Path, *, size: int = 256, quality: int = 82) -> dict:
    from PIL import Image

    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = im.convert("RGBA")
        im = im.resize((size, size), Image.Resampling.LANCZOS)
        im.save(dest, format="WEBP", quality=quality, method=6)
    raw_kb = src.stat().st_size / 1024
    out_kb = dest.stat().st_size / 1024
    return {"raw_kb": round(raw_kb, 1), "webp_kb": round(out_kb, 1), "size": f"{size}x{size}"}


def compress_all_raw(*, force: bool = False) -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    done = 0
    for raw in sorted(RAW_DIR.glob("*.*")):
        if raw.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        sk = raw.stem.lower()
        dest = GENERATED_DIR / f"{sk}.webp"
        if dest.is_file() and not force:
            continue
        meta = compress_image(raw, dest)
        entry = manifest.setdefault("icons", {}).get(sk, {})
        entry.update(
            {
                "species_key": sk,
                "path": f"/species/icons/generated/{sk}.webp",
                "raw_path": f"raw/{raw.name}",
                **meta,
                "status": "compressed",
            }
        )
        manifest["icons"][sk] = entry
        done += 1
        print(f"  compressed {sk}.webp ({meta['webp_kb']} KB)")
    save_manifest(manifest)
    sync_ai_manifest(manifest)
    return done


def sync_ai_manifest(manifest: dict) -> None:
    """Manifesto separado para integração futura (não substitui SVG bundle)."""
    icons = manifest.get("icons") or {}
    by_key = {s["species_key"]: s for s in build_official_species_list()}
    payload_icons: dict[str, dict] = {
        sk: {
            "path": meta.get("path"),
            "display_name": meta.get("display_name"),
            "tier": meta.get("tier"),
            "webp_kb": meta.get("webp_kb"),
        }
        for sk, meta in icons.items()
        if meta.get("path")
    }
    for alias, canon in CANONICAL_ICON_ALIASES.items():
        canon_meta = icons.get(canon)
        if not canon_meta or not canon_meta.get("path"):
            continue
        alias_species = by_key.get(alias, {})
        payload_icons[alias] = {
            "path": canon_meta["path"],
            "display_name": alias_species.get("display_name") or alias,
            "tier": alias_species.get("tier") or canon_meta.get("tier"),
            "webp_kb": canon_meta.get("webp_kb"),
            "canonical_species_key": canon,
        }
    payload = {
        "_comment": "Ícones AI raster — integração opcional via icon_path no registro",
        "_license": "© ARKLAND — arte original gerada por IA; não são assets do jogo Studio Wildcard",
        "_frame_style": manifest.get("_frame_style"),
        "count": len(payload_icons),
        "icons": payload_icons,
    }
    AI_MANIFEST_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def register_raw(
    species_key: str,
    raw_filename: str,
    *,
    display_name: str | None = None,
    tier: str | None = None,
    status: str = "raw",
) -> None:
    manifest = load_manifest()
    sk = species_key.lower()
    manifest.setdefault("icons", {})[sk] = {
        "species_key": sk,
        "display_name": display_name,
        "tier": tier,
        "raw_path": f"raw/{raw_filename}",
        "status": status,
    }
    save_manifest(manifest)


def mark_failure(species_key: str, error: str) -> None:
    manifest = load_manifest()
    manifest.setdefault("failures", []).append(
        {"species_key": species_key, "error": error, "at": datetime.now(timezone.utc).isoformat()}
    )
    save_manifest(manifest)


def filter_species(
    species: list[dict],
    *,
    tiers: list[str] | None = None,
    keys: list[str] | None = None,
    demos_only: bool = False,
    skip_existing: bool = True,
) -> list[dict]:
    by_key = {s["species_key"]: s for s in species}
    if demos_only:
        demo_keys = set(DEMO_SPECIES_KEYS.values())
        filtered = [by_key[k] for k in DEMO_SPECIES_KEYS.values() if k in by_key]
        return filtered

    result = species
    if tiers:
        tier_set = {t.upper() for t in tiers}
        if "S" in tier_set:
            tier_set.add("S+")
        result = [s for s in result if s["tier"] in tier_set or (s["tier"] == "S+" and "S+" in tier_set)]
    if keys:
        want = {k.lower() for k in keys}
        result = [s for s in result if s["species_key"] in want]

    if skip_existing:
        existing = set()
        if MANIFEST_PATH.is_file():
            m = load_manifest()
            for sk, meta in (m.get("icons") or {}).items():
                webp = GENERATED_DIR / f"{sk}.webp"
                if webp.is_file() and meta.get("status") == "compressed":
                    existing.add(sk)
        result = [s for s in result if s["species_key"] not in existing]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline de ícones AI vanilla ARK.")
    parser.add_argument("--list-only", action="store_true", help="Gera official_vanilla_species.json e sai.")
    parser.add_argument("--prompt", nargs="*", metavar="KEY", help="Imprime prompt(s) para species_key.")
    parser.add_argument("--compress-only", action="store_true", help="Comprime raw/ → generated/*.webp")
    parser.add_argument("--force-compress", action="store_true", help="Recomprime mesmo se webp existir.")
    parser.add_argument("--tier", nargs="*", help="Filtra por tier (S+, S, A, B, C).")
    parser.add_argument("--species", nargs="*", metavar="KEY", help="Subset de species_key (1 com --reference).")
    parser.add_argument(
        "--reference",
        metavar="PATH",
        help="Imagem de referência do usuário para anatomia correta (usar com --species KEY).",
    )
    parser.add_argument(
        "--frame-reference",
        metavar="PATH",
        help="Imagem de referência da moldura canônica (default: carno.webp ou _frame_template_carno.png).",
    )
    parser.add_argument(
        "--export-frame-template",
        action="store_true",
        help="Exporta carno raw → refs/_frame_template_carno.png e demo/frame_standard_carno.png",
    )
    parser.add_argument(
        "--composite-proof",
        metavar="KEY",
        help="Compõe ícone de prova com moldura padrão (ex: rex). Usar com --creature PATH.",
    )
    parser.add_argument(
        "--creature",
        metavar="PATH",
        help="PNG do busto da criatura (sem moldura) para --composite-proof.",
    )
    parser.add_argument("--demos", action="store_true", help="Só os 10 demos padronizados.")
    args = parser.parse_args()

    species = build_official_species_list()
    save_official_list(species)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if args.list_only:
        print(f"Official vanilla species: {len(species)} -> {OFFICIAL_LIST_PATH}")
        return 0

    if args.export_frame_template:
        dest = export_frame_template()
        if dest:
            print(f"Frame template exported -> {dest}")
            print(f"                 demo copy -> {FRAME_TEMPLATE_DEMO}")
        else:
            print("Frame template source not found (expected generated/raw/carno.png).", file=sys.stderr)
            return 2
        return 0

    if args.composite_proof:
        key = args.composite_proof.lower()
        by_key = {s["species_key"]: s for s in species}
        entry = by_key.get(key, {"species_key": key, "display_name": key, "tier": "B"})
        creature_path = Path(args.creature) if args.creature else (DEMO_DIR / f"{key}.png")
        if not creature_path.is_file():
            creature_path = DEMO_DIR / "rex.png" if key == "rex" else creature_path
        if not creature_path.is_file():
            print(f"Creature image not found: {creature_path}", file=sys.stderr)
            return 2
        proof_raw = RAW_DIR / f"{key}_framed_proof.png"
        proof_webp = GENERATED_DIR / f"{key}_framed_proof.webp"
        out = composite_species_icon(
            key,
            creature_path,
            output_path=proof_raw,
            display_name=entry.get("display_name"),
            tier=entry.get("tier"),
        )
        meta = compress_image(out, proof_webp)
        print(f"Proof composed: tier={resolve_tier(key, explicit=entry.get('tier'))} name={entry.get('display_name')}")
        print(f"  raw:  {out}")
        print(f"  webp: {proof_webp} ({meta['webp_kb']} KB)")
        return 0

    frame_ref: Path | None = None
    if args.frame_reference:
        frame_ref = Path(args.frame_reference)
        if not frame_ref.is_file():
            print(f"Frame reference not found: {frame_ref}", file=sys.stderr)
            return 2
    else:
        for candidate in (FRAME_TEMPLATE_REFS, FRAME_TEMPLATE_DEMO, DEFAULT_FRAME_REFERENCE):
            if candidate.is_file():
                frame_ref = candidate
                break

    if args.prompt:
        by_key = {s["species_key"]: s for s in species}
        for key in args.prompt:
            entry = by_key.get(key.lower())
            if not entry:
                print(f"Unknown species_key: {key}", file=sys.stderr)
                continue
            print(f"--- {entry['species_key']} ({entry['display_name']}) tier={entry['tier']} ---")
            print(creature_prompt(
                entry["display_name"],
                species_key=entry["species_key"],
                role=str(entry.get("role") or ""),
                tier=entry.get("tier"),
                frame_reference_path=frame_ref.resolve() if frame_ref else None,
            ))
            if frame_ref:
                print(f"frame_reference: {frame_ref.resolve()}")
            print()
        return 0

    if args.reference:
        if not args.species or len(args.species) != 1:
            print("Use exatamente um --species KEY com --reference PATH.", file=sys.stderr)
            return 2
        ref = Path(args.reference)
        if not ref.is_file():
            print(f"Reference image not found: {ref}", file=sys.stderr)
            return 2
        by_key = {s["species_key"]: s for s in species}
        key = args.species[0].lower()
        entry = by_key.get(key)
        if not entry:
            print(f"Unknown species_key: {key}", file=sys.stderr)
            return 2
        ref_resolved = ref.resolve()
        print(f"--- REGEN: {entry['species_key']} ({entry['display_name']}) tier={entry['tier']} ---")
        print(f"reference_image: {ref_resolved}")
        if frame_ref:
            print(f"frame_reference: {frame_ref.resolve()}")
        print()
        print(creature_prompt(
            entry["display_name"],
            species_key=entry["species_key"],
            role=str(entry.get("role") or ""),
            tier=entry.get("tier"),
            reference_path=ref_resolved,
            frame_reference_path=frame_ref.resolve() if frame_ref else None,
        ))
        print()
        aliases = [alias for alias, canon in CANONICAL_ICON_ALIASES.items() if canon == key]
        if aliases:
            print(f"Aliases to sync after regen: {', '.join(aliases)}")
        print(f"\nNext: generate raw/{key}.png -> python {Path(__file__).name} --compress-only --force-compress")
        return 0

    if args.compress_only:
        n = compress_all_raw(force=args.force_compress)
        print(f"Compressed {n} icon(s) -> {GENERATED_DIR}")
        return 0

    # Default: list pending for external image gen
    pending = filter_species(
        species,
        tiers=args.tier,
        keys=args.species,
        demos_only=args.demos,
    )
    print(f"Pending generation: {len(pending)} species")
    for s in pending[:20]:
        print(f"  {s['tier']:>2}  {s['species_key']:24}  {s['display_name']}")
    if len(pending) > 20:
        print(f"  ... +{len(pending) - 20} more")
    print(f"\nFrame spec: {FRAME_SPEC_PATH}")
    print(f"Frame template: {FRAME_TEMPLATE_REFS}")
    if frame_ref:
        print(f"Frame reference (default): {frame_ref}")
    print(f"Output: {GENERATED_DIR}/{{species_key}}.webp")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
