"""Gera ícones SVG minimalistas ARKLAND por espécie (círculo + tier + sigla)."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

TIER_PALETTE: dict[str, tuple[str, str, str]] = {
    "S+": ("#1a0f00", "#ff6d00", "#ffab40"),
    "S": ("#1a1208", "#ff5722", "#ffccbc"),
    "A": ("#1a1608", "#ffc107", "#ffe082"),
    "B": ("#0d1a10", "#4caf50", "#a5d6a7"),
    "C": ("#12161a", "#78909c", "#b0bec5"),
}

ARCHETYPE_GLYPH: dict[str, str] = {
    "flyer": "M32 46 L22 36 L32 30 L42 36 Z",
    "predator": "M24 44 L32 28 L40 44 L36 40 L28 40 Z",
    "herbivore": "M26 42 Q32 30 38 42 Q32 38 26 42",
    "aquatic": "M20 38 Q32 28 44 38 Q32 48 20 38",
    "resource": "M28 38 L32 30 L36 38 L34 42 L30 42 Z",
    "vehicle": "M22 40 L26 34 L38 34 L42 40 L38 44 L26 44 Z",
}

ARCHETYPE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"hover|skiff|sail|vehicle", re.I), "vehicle"),
    (re.compile(r"wyvern|drake|griffin|ptera|quetz|argent|tapejara|owl|desmodus|hawk|tropeo|astrocetus|fjordhawk|sinomacrops", re.I), "flyer"),
    (re.compile(r"rex|giga|carno|allo|yuty|theriz|spino|carcha|acro|indominus|raptor|deinonychus|sarco|megalosaurus|reaper|xenomorph", re.I), "predator"),
    (re.compile(r"mosa|megalodon|basil|plesio|tuso|dunkle|xiphactinus|archelon|basilosaurus|dakosaurus|megachelon|tridacna|seahorse|wyvern", re.I), "aquatic"),
    (re.compile(r"seaweed|manganese|barnacle|fish_scale|resource|ingot|wood|seed|aqualyrium|steel", re.I), "resource"),
    (re.compile(r"ankylo|doed|stego|bronto|diplo|brachio|paracer|achatina|moschops", re.I), "herbivore"),
)

ROLE_ARCHETYPE: dict[str, str] = {
    "farm": "herbivore",
    "transport": "flyer",
    "pvp": "predator",
    "boss": "predator",
    "utility": "herbivore",
    "resource": "resource",
}

_SKIP_WORDS = frozenset({"de", "da", "do", "das", "dos", "the", "a", "an", "abyssal", "abyss", "variant"})


def _norm_ascii(text: str) -> str:
    return (
        unicodedata.normalize("NFD", text or "")
        .encode("ascii", "ignore")
        .decode()
        .strip()
    )


def _pick_archetype(species_key: str, role: str = "") -> str:
    sk = species_key.lower()
    for pattern, archetype in ARCHETYPE_PATTERNS:
        if pattern.search(sk):
            return archetype
    return ROLE_ARCHETYPE.get((role or "").lower(), "herbivore")


def species_abbrev(species_key: str, display_name: str) -> str:
    """Sigla de 2 letras legível (ex.: Rex → RX, Water Wyvern → WW)."""
    name = _norm_ascii(display_name or species_key)
    words = [w for w in re.split(r"[\s_\-]+", name) if w and w.lower() not in _SKIP_WORDS]
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    if len(words) == 1:
        w = words[0]
        if len(w) >= 2:
            return w[:2].upper()
        return (w + w).upper()[:2]
    key = re.sub(r"^abyss_", "", species_key.lower())
    parts = [p for p in key.split("_") if p and p not in _SKIP_WORDS]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    if parts:
        p = parts[0]
        return (p[:2] if len(p) >= 2 else p + "X").upper()
    return "AR"


def render_species_icon_svg(
    *,
    species_key: str,
    display_name: str,
    tier: str = "B",
    role: str = "",
) -> str:
    """Retorna SVG 64×64 — círculo com anel de tier, badge e sigla de 2 letras."""
    tier_key = tier.strip().upper() if tier.strip().upper() in TIER_PALETTE else "B"
    bg, primary, accent = TIER_PALETTE.get(tier_key, TIER_PALETTE["B"])
    code = species_abbrev(species_key, display_name)
    archetype = _pick_archetype(species_key, role)
    glyph = ARCHETYPE_GLYPH.get(archetype, ARCHETYPE_GLYPH["herbivore"])
    label = (display_name or species_key)[:24].replace('"', "'")
    badge_w = 18 if len(tier_key) > 1 else 14

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="{label}">
  <rect width="64" height="64" rx="12" fill="{bg}"/>
  <circle cx="32" cy="34" r="22" fill="none" stroke="{primary}" stroke-width="3" opacity="0.95"/>
  <circle cx="32" cy="34" r="18" fill="{bg}" stroke="{accent}" stroke-width="1" opacity="0.35"/>
  <path fill="{accent}" opacity="0.55" d="{glyph}"/>
  <text x="32" y="38" text-anchor="middle" font-family="Rajdhani,Segoe UI,sans-serif" font-size="16" font-weight="700" fill="{primary}" letter-spacing="0.5">{code}</text>
  <rect x="{64 - badge_w - 6}" y="6" width="{badge_w}" height="14" rx="4" fill="{primary}"/>
  <text x="{64 - badge_w / 2 - 6}" y="16" text-anchor="middle" font-family="Rajdhani,Segoe UI,sans-serif" font-size="9" font-weight="700" fill="{bg}">{tier_key}</text>
</svg>
'''


def collect_registry_species() -> list[dict[str, Any]]:
    """Lista espécies do registro mesclado (sem cache)."""
    from ark_species_registry import _merged_species_list

    return _merged_species_list()
