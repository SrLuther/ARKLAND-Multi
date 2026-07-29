#!/usr/bin/env python3
"""Gera ícone genérico ARKLAND a partir de static/logo.png."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "plugin" / "arkshop_web" / "static" / "logo.png"
OUT_DIR = ROOT / "plugin" / "arkshop_web" / "static" / "catalog"
SPECIES_DIR = ROOT / "plugin" / "arkshop_web" / "static" / "species"
CROP_ASSET = (
    ROOT
    / "plugin"
    / "arkshop_web"
    / "static"
    / "species"
    / "icons"
    / "generated"
    / "_assets"
    / "ark_logo_crop.png"
)


def _load_crop() -> Image.Image:
    logo = Image.open(LOGO).convert("RGBA")
    w, h = logo.size
    return logo.crop((int(w * 0.12), int(h * 0.02), int(w * 0.88), int(h * 0.72)))


def make_icon(crop: Image.Image, size: int = 256, badge: str | None = None) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (13, 16, 22, 255))
    draw = ImageDraw.Draw(canvas)
    for i in range(size // 2, 0, -2):
        draw.ellipse(
            [size // 2 - i, size // 2 - i, size // 2 + i, size // 2 + i],
            fill=(26, 22, 18, 255),
        )
    inset = int(size * 0.10)
    box_w = size - 2 * inset
    portrait = crop.copy()
    portrait.thumbnail((box_w, box_w), Image.Resampling.LANCZOS)
    px = inset + (box_w - portrait.width) // 2
    py = inset + (box_w - portrait.height) // 2 - int(size * 0.02)
    canvas.paste(portrait, (px, py), portrait)

    m = int(size * 0.04)
    frames = [
        ((30, 34, 40), max(2, size // 40)),
        ((74, 80, 88), max(1, size // 64)),
        ((232, 120, 32), max(1, size // 80)),
    ]
    for i, (col, width) in enumerate(frames):
        draw.rounded_rectangle(
            [m + i * 2, m + i * 2, size - m - i * 2, size - m - i * 2],
            radius=max(8, int(size * 0.12) - i),
            outline=col,
            width=width,
        )

    if badge:
        bw = int(size * 0.22)
        bx1, by1 = int(size * 0.06), int(size * 0.06)
        draw.rounded_rectangle(
            [bx1, by1, bx1 + bw, by1 + bw],
            radius=int(bw * 0.2),
            fill=(20, 28, 36, 230),
            outline=(232, 120, 32),
            width=max(1, size // 100),
        )
        try:
            font = ImageFont.truetype("arialbd.ttf", max(10, bw // 3))
        except OSError:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), badge, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            (bx1 + (bw - tw) // 2, by1 + (bw - th) // 2 - bbox[1]),
            badge,
            fill=(240, 230, 200),
            font=font,
        )
    return canvas


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SPECIES_DIR.mkdir(parents=True, exist_ok=True)
    crop = _load_crop()

    icon = make_icon(crop, 256)
    webp = OUT_DIR / "arkland-generic.webp"
    png = OUT_DIR / "arkland-generic.png"
    icon.save(webp, "WEBP", quality=90, method=6)
    icon.save(png, "PNG")
    print(f"wrote {webp} ({webp.stat().st_size} B)")

    for tier, label in (
        ("s-plus", "S+"),
        ("s", "S"),
        ("a", "A"),
        ("b", "B"),
        ("c", "C"),
    ):
        dest = SPECIES_DIR / f"tier-{tier}.webp"
        make_icon(crop, 256, badge=label).save(dest, "WEBP", quality=90, method=6)
        print(f"wrote {dest.name}")

    CROP_ASSET.parent.mkdir(parents=True, exist_ok=True)
    crop.resize((186, 157), Image.Resampling.LANCZOS).save(CROP_ASSET, "PNG")
    print(f"updated {CROP_ASSET}")


if __name__ == "__main__":
    main()
