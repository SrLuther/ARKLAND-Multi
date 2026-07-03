"""Compare boss-unlocked tekgrams (wiki tables) vs user lists.

Fetches https://ark.wiki.gg/wiki/Table_of_Tekgrams (and optionally fandom cache),
parses rows unlocked by boss defeat, maps canonical blueprint paths, and writes
tools/tek_boss_unlock_missing.md.

Default: compare vs tools/tek_unlock_commands.txt (asset key match).
--vs-user-example: compare only vs the user's ~35-item chat shorthand list.
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USER_FILE = ROOT / "tools" / "tek_unlock_commands.txt"
OUT_FILE = ROOT / "tools" / "tek_boss_unlock_missing.md"
WIKI_CACHE = Path(__file__).resolve().parent / "_wiki_tekgrams.html"
FANDOM_CACHE = Path(__file__).resolve().parent / "_fandom_tekgrams.html"

WIKI_GG_URL = "https://ark.wiki.gg/wiki/Table_of_Tekgrams"
FANDOM_URL = "https://ark.fandom.com/wiki/Table_of_Tekgrams"

# Shorthand from user chat (~35 items) -> wiki table row names.
USER_EXAMPLE_NAMES: frozenset[str] = frozenset(
    {
        "Tek Replicator",
        "Tek Transmitter",
        "Tek Generator",
        "Cloning Chamber",
        "Tek Teleporter",
        "Tek Forcefield",  # TekShield (structure)
        "Tek Sensor",  # TekSensor / TekAlarm (wiki row; blueprint is TekAlarm)
        "Tek Sleeping Pod",  # Bed_Tek
        "Tek Trough",
        "Unassembled TEK Hover Skiff",
        "Unassembled Exo-Mek",
        "Tek Helmet",
        "Tek Chestpiece",  # TekShirt
        "Tek Gauntlets",
        "Tek Leggings",
        "Tek Boots",
        "Tek Rifle",
        "Tek Sword",
        "Tek Grenade",
        "Tek Claws",  # TekSniper is a different engram, not a boss tekgram
        "Tek Foundation",  # TekFloor
        "Tek Ceiling",
        "Tek Wall",
        "Tek Doorframe",
        "Tek Door",
        "Tek Window",
        "Tek Trapdoor",
        "Tek Hatchframe",  # TekCeilingWithTrapdoor
        "Tek Ramp",
        "Tek Staircase",  # TekStairs
        "Tek Dinosaur Gateway",  # TekGateframe
        "Tek Dinosaur Gate",  # TekGate
        "Tek Catwalk",
        "Tek Ladder",
        "Tek Pillar",
    }
)

# Typical blueprint paths from the user's chat commands (for ## Corrigidos only).
USER_EXAMPLE_PATHS: dict[str, str] = {
    "Tek Staircase": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekStairs.PrimalItemStructure_TekStairs",
}

# Canonical UnlockEngram paths (wiki.gg item pages + fandom Tek Tier spawn commands).
# Keys must match wiki table row names exactly.
BOSS_PATHS: dict[str, str] = {
    "Astrocetus Tek Saddle": "/Game/Genesis/Dinos/SpaceWhale/PrimalItemArmor_SpaceWhaleSaddle_Tek.PrimalItemArmor_SpaceWhaleSaddle_Tek",
    "Behemoth Tek Gate": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekGate_Large.PrimalItemStructure_TekGate_Large",
    "Behemoth Tek Gateway": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekGateFrame_Large.PrimalItemStructure_TekGateFrame_Large",
    "Cloning Chamber": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/BuildingBases/PrimalItemStructure_TekCloningChamber.PrimalItemStructure_TekCloningChamber",
    "Cruise Missile": "/Game/Genesis/Weapons/CruiseMissile/PrimalItem_WeaponTekCruiseMissile.PrimalItem_WeaponTekCruiseMissile",
    "Large Tek Wall": "/Game/PrimalEarth/StructuresPlus/Structures/Walls_L/Tek/PrimalItemStructure_LargeWall_Tek.PrimalItemStructure_LargeWall_Tek",
    "Megalodon Tek Saddle": "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Saddles/PrimalItemArmor_MegalodonSaddle_Tek.PrimalItemArmor_MegalodonSaddle_Tek",
    "Mosasaur Tek Saddle": "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Saddles/PrimalItemArmor_MosaSaddle_Tek.PrimalItemArmor_MosaSaddle_Tek",
    "Rex Tek Saddle": "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Saddles/PrimalItemArmor_RexSaddle_Tek.PrimalItemArmor_RexSaddle_Tek",
    "Rock Drake Tek Saddle": "/Game/Aberration/Dinos/RockDrake/PrimalItemArmor_RockDrakeSaddle_Tek.PrimalItemArmor_RockDrakeSaddle_Tek",
    "Sloped Tek Roof": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/tek/PrimalItemStructure_TekRoof.PrimalItemStructure_TekRoof",
    "Sloped Tek Wall Left": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/tek/PrimalItemStructure_TekWall_Sloped_Left.PrimalItemStructure_TekWall_Sloped_Left",
    "Sloped Tek Wall Right": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/tek/PrimalItemStructure_TekWall_Sloped_Right.PrimalItemStructure_TekWall_Sloped_Right",
    "Tapejara Tek Saddle": "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Saddles/PrimalItemArmor_Tapejara_Tek.PrimalItemArmor_Tapejara_Tek",
    "Tek Boots": "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Tek/PrimalItemArmor_TekBoots.PrimalItemArmor_TekBoots",
    "Tek Catwalk": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekCatwalk.PrimalItemStructure_TekCatwalk",
    "Tek Ceiling": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekCeiling.PrimalItemStructure_TekCeiling",
    "Tek Chestpiece": "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Tek/PrimalItemArmor_TekShirt.PrimalItemArmor_TekShirt",
    "Tek Claws": "/Game/Genesis/Weapons/TekHandBlades/PrimalItem_WeaponTekClaws.PrimalItem_WeaponTekClaws",
    "Tek Dedicated Storage": "/Game/PrimalEarth/StructuresPlus/Misc/DedicatedStorage/PrimalItemStructure_DedicatedStorage.PrimalItemStructure_DedicatedStorage",
    "Tek Dinosaur Gate": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekGate.PrimalItemStructure_TekGate",
    "Tek Dinosaur Gateway": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekGateFrame.PrimalItemStructure_TekGateFrame",
    "Tek Door": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekDoor.PrimalItemStructure_TekDoor",
    "Tek Doorframe": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekWallWithDoor.PrimalItemStructure_TekWallWithDoor",
    "Tek Double Door": "/Game/PrimalEarth/StructuresPlus/Doors/Doors_Double/Tek/PrimalItemStructure_DoubleDoor_Tek.PrimalItemStructure_DoubleDoor_Tek",
    "Tek Double Doorframe": "/Game/PrimalEarth/StructuresPlus/Structures/Doorframes_Double/Tek/PrimalItemStructure_DoubleDoorframe_Tek.PrimalItemStructure_DoubleDoorframe_Tek",
    "Tek Fence Foundation": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/tek/PrimalItemStructure_Tekfencefoundation.PrimalItemStructure_Tekfencefoundation",
    "Tek Fence Support": "/Game/PrimalEarth/StructuresPlus/Structures/FenceSupports/Tek/PrimalItemStructure_FenceSupport_Tek.PrimalItemStructure_FenceSupport_Tek",
    "Tek Forcefield": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Misc/PrimalItemStructure_TekShield.PrimalItemStructure_TekShield",
    "Tek Foundation": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekFloor.PrimalItemStructure_TekFloor",
    "Tek Gauntlets": "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Tek/PrimalItemArmor_TekGloves.PrimalItemArmor_TekGloves",
    "Tek Generator": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Misc/PrimalItemStructure_TekGenerator.PrimalItemStructure_TekGenerator",
    "Tek Grenade": "/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_TekGrenade.PrimalItem_TekGrenade",
    "Tek Grenade Launcher": "/Game/Extinction/CoreBlueprints/Items/PrimalItem_WeaponTekGrenadeLauncher.PrimalItem_WeaponTekGrenadeLauncher",
    "Tek Hatchframe": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekCeilingWithTrapdoor.PrimalItemStructure_TekCeilingWithTrapdoor",
    "Tek Helmet": "/Game/PrimalEarth/CoreBlueprints/Items/Armor/TEK/PrimalItemArmor_TekHelmet.PrimalItemArmor_TekHelmet",
    "Tek Ladder": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekLadder.PrimalItemStructure_TekLadder",
    "Tek Leggings": "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Tek/PrimalItemArmor_TekPants.PrimalItemArmor_TekPants",
    "Tek Light": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Misc/PrimalItemStructure_TekLight.PrimalItemStructure_TekLight",
    "Tek Pillar": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekPillar.PrimalItemStructure_TekPillar",
    "Tek Railing": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekRailing.PrimalItemStructure_TekRailing",
    "Tek Ramp": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekRamp.PrimalItemStructure_TekRamp",
    "Tek Replicator": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Misc/PrimalItemStructure_TekReplicator.PrimalItemStructure_TekReplicator",
    "Tek Rifle": "/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_TekRifle.PrimalItem_TekRifle",
    "Tek Railgun": "/Game/Extinction/CoreBlueprints/Items/PrimalItem_WeaponTekRailgun.PrimalItem_WeaponTekRailgun",
    "Tek Sensor": "/Game/Genesis/Structures/TekAlarm/PrimalItemStructure_TekAlarm.PrimalItemStructure_TekAlarm",
    "Tek Shield": "/Game/PrimalEarth/CoreBlueprints/Items/Armor/Shields/PrimalItemArmor_ShieldTek.PrimalItemArmor_ShieldTek",
    "Tek Shoulder Cannon": "/Game/Genesis2/Weapons/TekShoulderCannon/PrimalItem_WeaponTekShoulderCannon.PrimalItem_WeaponTekShoulderCannon",
    "Tek Sleeping Pod": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Misc/PrimalItemStructure_Bed_Tek.PrimalItemStructure_Bed_Tek",
    "Tek Staircase": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/tek/PrimalItemStructure_TekStairs.PrimalItemStructure_TekStairs",
    "Tek Stairs": "/Game/PrimalEarth/StructuresPlus/Structures/Ramps/Tek/PrimalItemStructure_Ramp_Tek.PrimalItemStructure_Ramp_Tek",
    "Tek Sword": "/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponTekSword.PrimalItem_WeaponTekSword",
    "Tek Teleporter": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Misc/PrimalItemStructure_TekTeleporter.PrimalItemStructure_TekTeleporter",
    "Tek Transmitter": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Misc/PrimalItemStructure_TekTransmitter.PrimalItemStructure_TekTransmitter",
    "Tek Trapdoor": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekTrapdoor.PrimalItemStructure_TekTrapdoor",
    "Tek Trough": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Misc/PrimalItemStructure_TekTrough.PrimalItemStructure_TekTrough",
    "Tek Triangle Ceiling": "/Game/PrimalEarth/StructuresPlus/Structures/Ceilings/Triangle/Tek/PrimalItemStructure_TriCeiling_Tek.PrimalItemStructure_TriCeiling_Tek",
    "Tek Triangle Foundation": "/Game/PrimalEarth/StructuresPlus/Structures/Foundations/Triangle/Tek/PrimalItemStructure_TriFoundation_Tek.PrimalItemStructure_TriFoundation_Tek",
    "Tek Triangle Roof": "/Game/PrimalEarth/StructuresPlus/Structures/Roofs_Tri/Tek/PrimalItemStructure_TriRoof_Tek.PrimalItemStructure_TriRoof_Tek",
    "Tek Turret": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Misc/PrimalItemStructure_TurretTek.PrimalItemStructure_TurretTek",
    "Tek Wall": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekWall.PrimalItemStructure_TekWall",
    "Tek Window": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekWindow.PrimalItemStructure_TekWindow",
    "Tek Windowframe": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/Tek/PrimalItemStructure_TekWallWithWindow.PrimalItemStructure_TekWallWithWindow",
    "Unassembled Exo-Mek": "/Game/Genesis2/Dinos/Mek/PrimalItem_Spawner_Exosuit.PrimalItem_Spawner_Exosuit",
    "Unassembled TEK Hover Skiff": "/Game/Genesis/CoreBlueprints/Items/PrimalItem_Spawner_HoverSkiff.PrimalItem_Spawner_HoverSkiff",
    "Vacuum Compartment": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/BuildingBases/PrimalItemStructure_UnderwaterBase.PrimalItemStructure_UnderwaterBase",
    "Vacuum Compartment Moonpool": "/Game/PrimalEarth/CoreBlueprints/Items/Structures/BuildingBases/PrimalItemStructure_UnderwaterBase_moonpool.PrimalItemStructure_UnderwaterBase_Moonpool",
}

# Rows that are metadata, not craftable tekgrams.
_SKIP_ROW_PREFIXES = ("Required Level", "Element", "Harder difficulties", "Ragnarok Arena", "ARK:")


class _TekgramTableParser(HTMLParser):
    """Extract wiki table rows: first cell = item name, rest = boss checkmarks."""

    def __init__(self) -> None:
        super().__init__()
        self._in_table = False
        self._in_row = False
        self._in_cell = False
        self._cell_idx = -1
        self._cell_text: list[str] = []
        self._row_cells: list[str] = []
        self.rows: list[tuple[str, bool]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._in_table = True
        elif self._in_table and tag == "tr":
            self._in_row = True
            self._row_cells = []
            self._cell_idx = -1
        elif self._in_row and tag in ("td", "th"):
            self._in_cell = True
            self._cell_idx += 1
            self._cell_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._in_cell:
            text = "".join(self._cell_text).strip()
            self._row_cells.append(text)
            self._in_cell = False
        elif tag == "tr" and self._in_row:
            if self._row_cells:
                name = self._row_cells[0].strip()
                boss_cells = self._row_cells[1:]
                has_boss = any("✓" in c or "check" in c.lower() for c in boss_cells)
                if name and not name.startswith(_SKIP_ROW_PREFIXES):
                    self.rows.append((name, has_boss))
            self._in_row = False
        elif tag == "table":
            self._in_table = False

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._cell_text.append(data)


def _fetch(url: str, cache: Path) -> str:
    headers = {"User-Agent": "arkland-multi-tekgram-compare/1.0"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        cache.write_text(html, encoding="utf-8")
        return html
    except Exception as exc:
        if cache.is_file():
            print(f"warn: fetch {url} failed ({exc}); using cache {cache.name}", file=sys.stderr)
            return cache.read_text(encoding="utf-8", errors="replace")
        raise


def _parse_boss_names(html: str) -> list[str]:
    parser = _TekgramTableParser()
    parser.feed(html)
    names = [name for name, has_boss in parser.rows if has_boss]
    # Fallback: markdown-style table from wiki.gg API render
    if not names:
        for line in html.splitlines():
            m = re.match(r"^\| ([^|]+?) \|", line)
            if not m:
                continue
            name = m.group(1).strip()
            if name in ("Tekgrams", "") or name.startswith(_SKIP_ROW_PREFIXES):
                continue
            if "✓" in line:
                names.append(name)
    return names


def _cmd(path: str) -> str:
    return f'cheat UnlockEngram "Blueprint\'{path}\'"'


def _asset_key(path: str) -> str:
    m = re.search(r"([^/]+)\.([^/]+)'?$", path)
    if not m:
        return path.lower()
    return m.group(1).lower()


def _parse_unlock_commands(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("cheat UnlockEngram"):
            continue
        m = re.search(r"Blueprint'([^']+)'", line)
        if m:
            path = m.group(1)
            out[_asset_key(path)] = path
    return out


def _merge_wiki_boss_names(wiki_gg: list[str], fandom: list[str]) -> list[str]:
    gg_set = set(wiki_gg)
    fd_set = set(fandom)
    merged = sorted(gg_set | fd_set)
    only_gg = gg_set - fd_set
    only_fd = fd_set - gg_set
    if only_gg:
        print(f"warn: only on wiki.gg ({len(only_gg)}): {', '.join(sorted(only_gg)[:5])}...", file=sys.stderr)
    if only_fd:
        print(f"warn: only on fandom ({len(only_fd)}): {', '.join(sorted(only_fd)[:5])}...", file=sys.stderr)
    return merged


def _covered_by_user_example(name: str, canon: str, extra_asset_keys: set[str]) -> bool:
    if name in USER_EXAMPLE_NAMES:
        return True
    key = _asset_key(canon)
    if key in extra_asset_keys:
        return True
    # Fuzzy: wiki name tokens vs example set (already name-mapped; asset fallback above).
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare wiki boss tekgrams vs user coverage")
    parser.add_argument(
        "--vs-user-example",
        action="store_true",
        help="Compare only vs USER_EXAMPLE_NAMES (chat ~35 items), not tek_unlock_commands.txt",
    )
    args = parser.parse_args()
    vs_user = args.vs_user_example

    html_gg = _fetch(WIKI_GG_URL, WIKI_CACHE)
    try:
        html_fd = _fetch(FANDOM_URL, FANDOM_CACHE)
    except Exception as exc:
        print(f"warn: fandom unavailable ({exc})", file=sys.stderr)
        html_fd = ""

    boss_names_gg = _parse_boss_names(html_gg)
    boss_names_fd = _parse_boss_names(html_fd) if html_fd else []
    boss_names = _merge_wiki_boss_names(boss_names_gg, boss_names_fd)

    if not boss_names:
        print("error: no boss tekgrams parsed from wiki; using BOSS_PATHS keys", file=sys.stderr)
        boss_names = sorted(BOSS_PATHS.keys())

    missing_paths: list[str] = []
    boss_canonical: dict[str, str] = {}
    for name in boss_names:
        path = BOSS_PATHS.get(name)
        if not path:
            missing_paths.append(name)
            continue
        boss_canonical[name] = path

    if missing_paths:
        print(f"error: no blueprint path for: {missing_paths}", file=sys.stderr)
        sys.exit(1)

    user_paths: dict[str, str] = {}
    if not vs_user:
        user_paths = _parse_unlock_commands(USER_FILE.read_text(encoding="utf-8-sig"))

    # Extra asset keys from user's typical paths (fuzzy asset match).
    example_asset_keys = {_asset_key(p) for p in USER_EXAMPLE_PATHS.values()}

    missing: list[tuple[str, str]] = []
    corrected: list[tuple[str, str, str]] = []

    covered_by_example = 0

    for name, canon in sorted(boss_canonical.items()):
        key = _asset_key(canon)
        in_example = _covered_by_user_example(name, canon, example_asset_keys)

        if in_example:
            covered_by_example += 1

        if vs_user:
            example_path = USER_EXAMPLE_PATHS.get(name)
            if in_example and example_path is not None and example_path != canon:
                corrected.append((name, example_path, canon))
            elif not in_example:
                missing.append((name, canon))
            continue

        user_path = user_paths.get(key)

        if user_path is not None and user_path != canon:
            corrected.append((name, user_path, canon))
            continue

        if user_path == canon:
            continue

        missing.append((name, canon))

    n_wiki = len(boss_canonical)
    n_example = len(USER_EXAMPLE_NAMES)
    n_missing = len(missing)

    if vs_user:
        lines = [
            "# Tek boss unlock — faltantes e correções",
            "",
            f"**{n_wiki} na wiki · {n_example} no seu exemplo · {n_missing} faltantes**",
            "",
            "Fonte: [wiki.gg](https://ark.wiki.gg/wiki/Table_of_Tekgrams) · "
            "comparação vs lista do chat (~35 itens), **não** vs `tek_unlock_commands.txt`",
            "",
        ]
        section_missing = "## Faltantes (vs seu exemplo)"
    else:
        lines = [
            "# Tek boss unlock — faltantes e correções",
            "",
            "Fonte: [wiki.gg](https://ark.wiki.gg/wiki/Table_of_Tekgrams) · "
            "[fandom](https://ark.fandom.com/wiki/Table_of_Tekgrams) · "
            f"ref: `tools/tek_unlock_commands.txt`",
            "",
            f"<!-- wiki boss tekgrams: {n_wiki} | "
            f"exemplo chat: {n_example} nomes | "
            f"tek_unlock_commands: {len(user_paths)} comandos | "
            f"faltantes: {n_missing} | corrigidos: {len(corrected)} -->",
            "",
        ]
        section_missing = "## Faltantes"

    if missing:
        lines.append(section_missing)
        lines.append("")
        for _name, path in missing:
            lines.append(_cmd(path))
        lines.append("")

    if corrected:
        lines.append("## Corrigidos")
        lines.append("")
        for name, wrong, right in corrected:
            lines.append(f"<!-- {name}: era `{wrong}` -->")
            lines.append(_cmd(right))
        lines.append("")

    if not missing and not corrected:
        lines.append("_Nenhuma diferença — cobertura completa com paths canônicos._")
        lines.append("")

    OUT_FILE.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print(f"Wrote {OUT_FILE}")
    print(f"mode={'vs-user-example' if vs_user else 'vs-tek_unlock_commands'}")
    print(f"wiki_boss_tekgrams={n_wiki}")
    print(f"user_example_names={n_example}")
    print(f"user_example_covers={covered_by_example} of {n_wiki} wiki rows")
    if not vs_user:
        print(f"tek_unlock_commands={len(user_paths)}")
    print(f"missing={n_missing} corrected={len(corrected)}")
    for name, _ in missing:
        print(f"  MISSING: {name}")
    for name, wrong, right in corrected:
        print(f"  FIX {name}:")
        print(f"    was: {wrong}")
        print(f"    now: {right}")


if __name__ == "__main__":
    main()
