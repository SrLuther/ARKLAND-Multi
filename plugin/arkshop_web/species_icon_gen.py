"""Gera ícones SVG originais ARKLAND por espécie (silhuetas procedurais, sem IP de terceiros)."""
from __future__ import annotations

import hashlib
import re
from typing import Any

TIER_PALETTE: dict[str, tuple[str, str, str]] = {
    "S+": ("#1a0f00", "#ff6d00", "#ffab40"),
    "S": ("#1a1208", "#ff5722", "#ffccbc"),
    "A": ("#1a1608", "#ffc107", "#ffe082"),
    "B": ("#0d1a10", "#4caf50", "#a5d6a7"),
    "C": ("#12161a", "#78909c", "#b0bec5"),
}

ARCHETYPE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"wyvern|drake|griffin|ptera|quetz|argent|tapejara|pelagornis|owl|desmodus|hawk|tropeo|astrocetus|fjordhawk|sinomacrops", re.I), "flyer"),
    (re.compile(r"rex|giga|carno|allo|yuty|theriz|spino|carcha|acro|indominus|concavenator|deinosuchus|armaedron|lionfish|bionic|volcano", re.I), "predator_large"),
    (re.compile(r"raptor|deinonychus|direwolf|sabertooth|thyla|purlovia|kapro|sarco|megalosaurus|cryolophosaurus|shimosaur", re.I), "predator_medium"),
    (re.compile(r"ankylo|doed|stego|turtle|carbonemys|paracer|achatina", re.I), "armored"),
    (re.compile(r"bronto|diplo|brachio|amarga|sauropod", re.I), "sauropod"),
    (re.compile(r"mosa|megalodon|basil|plesio|tuso|dunkle|xiphactinus|archelon|basilosaurus|dakosaurus|megachelon", re.I), "aquatic"),
    (re.compile(r"mantis|scorpion|spider|bloodstalker|reaper|xenomorph|rhynio", re.I), "alien"),
    (re.compile(r"beaver|mammoth|megatherium|daeodon|gasbags|maewing|procoptodon|equus|galli|phiomia", re.I), "mammal"),
    (re.compile(r"tek|strider|ferox|velonasaur|gacha|managarmr|magmasaur", re.I), "fantasy"),
    (re.compile(r"seaweed|manganese|barnacle|fish_scale|resource|ingot|wood|seed", re.I), "resource"),
)

ROLE_ARCHETYPE: dict[str, str] = {
    "farm": "armored",
    "transport": "flyer",
    "pvp": "predator_large",
    "boss": "predator_large",
    "utility": "mammal",
    "resource": "resource",
}


def _hash_seed(species_key: str) -> int:
    return int(hashlib.sha256(species_key.encode()).hexdigest()[:8], 16)


def _pick_archetype(species_key: str, role: str = "") -> str:
    sk = species_key.lower()
    for pattern, archetype in ARCHETYPE_PATTERNS:
        if pattern.search(sk):
            return archetype
    return ROLE_ARCHETYPE.get((role or "").lower(), "mammal")


def _horn_paths(seed: int, count: int, accent: str) -> str:
    parts: list[str] = []
    for i in range(count):
        angle = (seed % 7 + i * 3) % 5
        x = 28 + i * 8 + (seed % 4)
        h = 8 + (seed >> (i * 2)) % 6
        parts.append(
            f'<path fill="{accent}" opacity="0.45" d="M{x} 18 L{x + angle} {18 - h} L{x + 4} 22 Z"/>'
        )
    return "".join(parts)


def _head_path(archetype: str, seed: int) -> str:
    v = seed % 5
    if archetype == "flyer":
        return (
            f"M14 38c4-10 12-16 22-18 6-8 16-10 24-4 4 8 0 16-8 20 "
            f"{2+v}-6 {6+v}-10 {10+v}-12-6 2-12 6-16 10-8 2-16 0-22-4z"
        )
    if archetype == "predator_large":
        return (
            f"M10 40c2-12 10-20 22-22 6-8 18-10 28-2 4 10-2 18-10 22 "
            f"4 6 2 14-6 16-10 4-22 0-28-8-6-4-8-10-6-16z"
        )
    if archetype == "predator_medium":
        return (
            f"M16 42c2-8 8-14 16-16 4-6 12-8 18-2 2 6-2 12-8 14 "
            f"2 4 0 10-6 12-8 2-16 0-20-8z"
        )
    if archetype == "armored":
        return (
            f"M12 44c0-12 8-22 20-24 8-2 16 2 20 10 2 8-2 16-10 20 "
            f"-6 4-14 4-20 0-6-4-10-10-10-6z"
        )
    if archetype == "sauropod":
        return (
            f"M8 46c4-14 16-24 30-26 10-2 18 4 22 14 0 8-6 14-14 16 "
            f"-8 2-18 0-26-4-8-4-12-10-12-16z"
        )
    if archetype == "aquatic":
        return (
            f"M10 36c6-6 14-10 24-10 10 0 18 4 24 12 2 8-4 16-14 18 "
            f"-8 2-18 0-26-6-6-4-10-10-8-14z"
        )
    if archetype == "alien":
        return (
            f"M14 34c6-12 16-18 28-16 8 2 14 10 14 20 0 8-8 14-18 14 "
            f"-10 0-18-6-22-14-4-8-4-16-2-4z"
        )
    if archetype == "fantasy":
        return (
            f"M12 38c4-10 12-18 22-20 8-2 16 2 22 10 4 8 2 16-6 20 "
            f"-6 4-14 6-22 4-8-2-14-8-16-14z"
        )
    if archetype == "resource":
        return (
            f"M20 44c0-10 6-18 14-20 6-2 12 2 16 8 2 6 0 12-6 16 "
            f"-6 4-14 4-20 0-4-4-6-8-4-4z"
        )
    # mammal / default
    return (
        f"M14 42c2-8 10-14 18-16 6-4 14-4 20 2 4 6 2 12-4 16 "
        f"-4 4-12 6-18 4-8-2-14-8-16-6z"
    )


def _eye_positions(archetype: str, seed: int) -> tuple[tuple[float, float], tuple[float, float] | None]:
    if archetype == "resource":
        return ((32, 30), None)
    if archetype in ("flyer", "aquatic"):
        return ((38, 28), (44, 30))
    if archetype == "sauropod":
        return ((22, 26), None)
    x = 36 + (seed % 4)
    y = 26 + (seed % 3)
    return ((x, y), (x + 8, y + 1) if archetype in ("predator_large", "alien") else None)


def render_species_icon_svg(
    *,
    species_key: str,
    display_name: str,
    tier: str = "B",
    role: str = "",
) -> str:
    """Retorna SVG 64×64 — silhueta de cabeça original ARKLAND."""
    tier_key = tier.strip().upper() if tier.strip().upper() in TIER_PALETTE else "B"
    if tier_key == "S":
        tier_key = "S"
    bg, primary, accent = TIER_PALETTE.get(tier_key, TIER_PALETTE["B"])
    seed = _hash_seed(species_key)
    archetype = _pick_archetype(species_key, role)
    head = _head_path(archetype, seed)
    eye1, eye2 = _eye_positions(archetype, seed)
    horns = ""
    if archetype in ("flyer", "fantasy", "alien", "predator_large"):
        horns = _horn_paths(seed, 1 + seed % 2, accent)

    label = (display_name or species_key)[:24].replace('"', "'")
    eye_dots = f'<circle cx="{eye1[0]}" cy="{eye1[1]}" r="2.2" fill="{accent}"/>'
    if eye2:
        eye_dots += f'<circle cx="{eye2[0]}" cy="{eye2[1]}" r="1.8" fill="{accent}" opacity="0.85"/>'

    jaw = ""
    if archetype in ("predator_large", "predator_medium"):
        jaw = f'<path fill="{primary}" opacity="0.55" d="M18 44c4 4 10 6 16 4 4-2 6-6 4-10-6 2-12 2-20 6z"/>'

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="{label}">
  <rect width="64" height="64" rx="12" fill="{bg}"/>
  {horns}
  <path fill="{primary}" d="{head}"/>
  {jaw}
  {eye_dots}
  <circle cx="{eye1[0]+1}" cy="{eye1[1]-0.5}" r="0.8" fill="{bg}" opacity="0.6"/>
</svg>
'''


def collect_registry_species() -> list[dict[str, Any]]:
    """Lista espécies do registro mesclado (sem cache)."""
    from ark_species_registry import _merged_species_list

    return _merged_species_list()
