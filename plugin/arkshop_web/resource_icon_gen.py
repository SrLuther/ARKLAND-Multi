"""Composição determinística de ícones ARKLAND para recursos do catálogo."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

WEB = Path(__file__).resolve().parent
ROOT = WEB.parents[1]
CONFIG_PATH = ROOT / "plugin" / "CustomShop" / "configs" / "config.json"
REFS_DIR = ROOT / "refs" / "resource_icons"
OUTPUT_DIR = WEB / "static" / "catalog" / "resources"
MANIFEST_PATH = WEB / "data" / "resource_icons_manifest.json"

ARK_LOGO_CROP = WEB / "static" / "species" / "icons" / "generated" / "_assets" / "ark_logo_crop.png"
FRAME_TEMPLATE_REFS = ROOT / "refs" / "species_icons" / "_frame_template_carno.png"

ICON_CANVAS_SIZE = 1024
PORTRAIT_INSET = (102, 118, 922, 820)
PORTRAIT_BACKGROUND = "#1a1a2e"

REC_BADGE_FILL = "#14202a"
REC_BADGE_BORDER = "#2d8fd4"
REC_BADGE_LETTER = "#5ec8ff"

ABYSS_REF_MAP: dict[str, str] = {
    "abyss_aqualyrium": "rec_aqualyrium.png",
    "abyss_barnacle": "rec_barnacle.png",
    "abyss_crystallized_wood": "rec_crystallizedWood.png",
    "abyss_fish_scale": "rec_fishScale.png",
    "abyss_hardened_steel": "rec_HardenedSteelIngot.png",
    "abyss_manganese": "rec_manganese.png",
    "abyss_seaweed": "rec_seaweed.png",
    "abyss_seed_cucumis": "abyss_seed_cucumis.png",
    "abyss_seed_rice": "abyss_seed_rice.png",
    "abyss_seed_plantspeciesw": "abyss_seed_plantspeciesw.png",
    "abyss_hover_sail": "abyss_hover_sail.png",
    "abyss_hover_skiff": "abyss_hover_skiff.png",
    "daco_sushi": "daco_sushi.png",
}

_QTY_SUFFIX_RE = re.compile(r"\s*\(\d+x\)\s*$", re.I)


def expected_ref_filename(catalog_key: str) -> str:
    if catalog_key in ABYSS_REF_MAP:
        return ABYSS_REF_MAP[catalog_key]
    if catalog_key.startswith("rec_"):
        return f"{catalog_key}.png"
    return f"{catalog_key}.png"


def expected_ref_path(catalog_key: str) -> Path:
    return REFS_DIR / expected_ref_filename(catalog_key)


def clean_display_name(name: str, *, fallback: str = "") -> str:
    text = _QTY_SUFFIX_RE.sub("", (name or "").strip())
    if not text:
        text = fallback
    if len(text) > 28:
        text = text[:26].rstrip() + "…"
    return text


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
    raise FileNotFoundError("ARK logo crop not found for resource icon compositing")


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


def _draw_rec_badge(canvas) -> None:
    from PIL import Image, ImageDraw, ImageFont

    w, _ = canvas.size
    badge_size = int(w * 0.14)
    pad = int(w * 0.035)
    x1, y1 = pad, pad
    x2, y2 = x1 + badge_size, y1 + badge_size
    radius = int(badge_size * 0.18)

    badge = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(badge)
    fill = _hex_to_rgb(REC_BADGE_FILL) + (255,)
    border = _hex_to_rgb(REC_BADGE_BORDER)
    letter_col = _hex_to_rgb(REC_BADGE_LETTER)
    draw.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=fill, outline=border, width=max(2, w // 256))
    label = "REC"
    font_size = int(badge_size * 0.34)
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


def _paste_item(canvas, item) -> None:
    from PIL import Image

    left, top, right, bottom = PORTRAIT_INSET
    box_w, box_h = right - left, bottom - top
    item = item.convert("RGBA")
    cw, ch = item.size
    scale = min(box_w / cw, box_h / ch) * 0.88
    nw, nh = max(1, int(cw * scale)), max(1, int(ch * scale))
    item = item.resize((nw, nh), Image.Resampling.LANCZOS)
    px = left + (box_w - nw) // 2
    py = top + (box_h - nh) // 2
    canvas.paste(item, (px, py), item)


def composite_resource_icon(item_image, *, display_name: str, size: int = ICON_CANVAS_SIZE):
    """Compõe ícone final: moldura metálica + logo ARK + badge REC + nome."""
    from PIL import Image, ImageDraw

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 255))
    if item_image.size != (size, size):
        item_image = item_image.resize((size, size), Image.Resampling.LANCZOS)

    inset_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(inset_layer)
    bg = _hex_to_rgb(PORTRAIT_BACKGROUND)
    draw.rounded_rectangle(PORTRAIT_INSET, radius=16, fill=bg)
    _draw_hex_grid(draw, PORTRAIT_INSET, bg)
    canvas = Image.alpha_composite(canvas, inset_layer)

    _paste_item(canvas, item_image)
    _draw_metal_frame(canvas)
    _draw_rec_badge(canvas)
    _draw_nameplate(canvas, display_name)

    logo = _load_ark_logo()
    logo_scale = int(size * 0.16)
    logo = logo.resize((logo_scale, int(logo_scale * logo.height / logo.width)), Image.Resampling.LANCZOS)
    lx = size - logo.width - int(size * 0.035)
    ly = int(size * 0.035)
    canvas.paste(logo, (lx, ly), logo)
    return canvas.convert("RGB")


def compress_to_webp(src, dest: Path, *, size: int = 256, quality: int = 82) -> dict[str, Any]:
    from PIL import Image

    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = im.convert("RGBA")
        im = im.resize((size, size), Image.Resampling.LANCZOS)
        im.save(dest, format="WEBP", quality=quality, method=6)
    return {
        "webp_kb": round(dest.stat().st_size / 1024, 1),
        "size": f"{size}x{size}",
    }


def extract_blueprint_token(blueprint: str) -> str:
    bp = (blueprint or "").strip()
    if not bp:
        return ""
    token = bp.rsplit("/", 1)[-1]
    if "." in token:
        token = token.rsplit(".", 1)[-1]
    return token


def collect_catalog_resource_keys() -> list[str]:
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    items = data.get("Items") or {}
    rec_keys = {k for k in items if k.startswith("rec_")}
    abyss_recursos = {
        k for k, v in items.items() if k.startswith("abyss_") and v.get("Category") == "Recursos"
    }
    other_recursos = {
        k
        for k, v in items.items()
        if v.get("Category") == "Recursos" and not k.startswith(("rec_", "abyss_"))
    }
    abyss_type_item = {k for k, v in items.items() if k.startswith("abyss_") and v.get("Type") == "item"}
    return sorted(rec_keys | abyss_recursos | other_recursos | abyss_type_item)


def catalog_entry_display_name(key: str, entry: dict[str, Any]) -> str:
    raw = str(entry.get("Name") or entry.get("Description") or key).strip()
    return clean_display_name(raw, fallback=key.replace("rec_", "").replace("abyss_", "").replace("_", " "))


def catalog_entry_blueprint(entry: dict[str, Any]) -> str:
    rows = entry.get("Items") or []
    if rows and isinstance(rows[0], dict):
        return str(rows[0].get("Blueprint") or "").strip()
    for field in ("Blueprint", "blueprint", "ItemBlueprint"):
        val = entry.get(field)
        if val:
            return str(val).strip()
    return ""
