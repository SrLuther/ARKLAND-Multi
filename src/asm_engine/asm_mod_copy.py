"""
Cópia de mods — paridade ModUtils.CopyMod / UE4ChunkUnzip do ARK Server Manager.

O SteamCMD baixa assets comprimidos (.uasset.z). O ARK Dedicated só monta
PrimalGameData e mapas mod após descompressão para .uasset/.umap.
"""
from __future__ import annotations

import shutil
import struct
import zlib
from pathlib import Path
from typing import Callable, Dict, List, Optional

ARK_WORKSHOP_APP_ID = "346110"
LAST_UPDATED_TIME_FILE = "LastUpdatedASM.txt"
PACKAGE_FILE_TAG = 2653586369
CHUNK_SIZE = 131072


def _read_i64(data: bytes, offset: int) -> tuple[int, int]:
    val = struct.unpack_from("<q", data, offset)[0]
    return val, offset + 8


def ue4_chunk_unzip(source: Path, destination: Path) -> None:
    """Descomprime arquivo .z do Unreal Engine (formato ASM/Ionic.Zlib)."""
    raw = source.read_bytes()
    offset = 0

    _, offset = _read_i64(raw, offset)
    chunk_size, offset = _read_i64(raw, offset)
    _, offset = _read_i64(raw, offset)
    total_size, offset = _read_i64(raw, offset)

    if chunk_size == PACKAGE_FILE_TAG:
        chunk_size = CHUNK_SIZE

    num_chunks = (total_size + chunk_size - 1) // chunk_size if chunk_size else 0
    compressed_sizes: list[int] = []
    for _ in range(num_chunks):
        cs, offset = _read_i64(raw, offset)
        _, offset = _read_i64(raw, offset)
        compressed_sizes.append(cs)

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as out:
        for cs in compressed_sizes:
            chunk = raw[offset: offset + cs]
            offset += cs
            out.write(zlib.decompress(chunk))


def _read_ue4_string(data: bytes, offset: int) -> tuple[str, int]:
    if offset + 4 > len(data):
        return "", offset
    count = struct.unpack_from("<i", data, offset)[0]
    offset += 4
    if count < 0:
        count = -count
    if count <= 0:
        return "", offset
    if offset + count > len(data):
        return "", offset
    text = data[offset: offset + count - 1].decode("utf-8", errors="replace")
    return text, offset + count


def parse_mod_info_map_names(mod_info_path: Path) -> list[str]:
    """Lê nomes de mapa do mod.info (ParseBaseInformation do ASM)."""
    if not mod_info_path.is_file():
        return []
    try:
        raw = mod_info_path.read_bytes()
        offset = 0
        _, offset = _read_ue4_string(raw, offset)
        if offset + 4 > len(raw):
            return []
        num_maps = struct.unpack_from("<I", raw, offset)[0]
        offset += 4
        names: list[str] = []
        for _ in range(num_maps):
            name, offset = _read_ue4_string(raw, offset)
            if name:
                names.append(name)
        return names
    except Exception:
        return []


def parse_modmeta(modmeta_path: Path) -> dict[str, str]:
    """Lê modmeta.info (ParseMetaInformation do ASM)."""
    meta: dict[str, str] = {}
    if not modmeta_path.is_file():
        return meta
    try:
        raw = modmeta_path.read_bytes()
        offset = 0
        if offset + 4 > len(raw):
            return meta
        count = struct.unpack_from("<I", raw, offset)[0]
        offset += 4
        for _ in range(count):
            key, offset = _read_ue4_string(raw, offset)
            val, offset = _read_ue4_string(raw, offset)
            if key:
                meta[key] = val
    except Exception:
        pass
    return meta


def _write_ue4_string(writer, text: str) -> None:
    data = text.encode("utf-8") + b"\x00"
    writer.write(struct.pack("<I", len(data)))
    writer.write(data)


def write_mod_file(
    dest: Path,
    mod_id: str,
    meta: dict[str, str],
    map_names: list[str],
) -> None:
    """Gera {modId}.mod binário (WriteModFile do ASM)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    mod_id_int = int(mod_id)
    with dest.open("wb") as f:
        f.write(struct.pack("<Q", mod_id_int))
        _write_ue4_string(f, "ModName")
        _write_ue4_string(f, "")
        f.write(struct.pack("<I", len(map_names)))
        for name in map_names:
            _write_ue4_string(f, name)
        f.write(struct.pack("<I", 4280483635))
        f.write(struct.pack("<I", 2))
        f.write(struct.pack("<B", 1 if meta else 0))
        f.write(struct.pack("<I", len(meta)))
        for key, val in meta.items():
            _write_ue4_string(f, key)
            _write_ue4_string(f, val)


def _copy_one_file(source: Path, dest_dir: Path) -> bool:
    """Copia um arquivo; descomprime .z. Retorna True se PrimalGameData no nome."""
    ext = source.suffix.lower()
    if ext == ".uncompressed_size":
        return False

    if ext == ".z":
        out_name = source.name[:-2]
        dest = dest_dir / out_name
        ue4_chunk_unzip(source, dest)
    else:
        dest = dest_dir / source.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)

    return "PrimalGameData" in source.name


def copy_mod_tree(source: Path, destination: Path) -> bool:
    """Copia pasta do mod descomprimindo .z (ModUtils.Copy recursivo)."""
    has_primal = False
    if not source.is_dir():
        return False

    for src_file in source.rglob("*"):
        if not src_file.is_file():
            continue
        rel_parent = src_file.parent.relative_to(source)
        dest_dir = destination / rel_parent
        if _copy_one_file(src_file, dest_dir):
            has_primal = True
    return has_primal


def mod_needs_decompress_repair(mod_folder: Path) -> bool:
    """True se há PrimalGameData.uasset.z sem o .uasset descomprimido."""
    if not mod_folder.is_dir():
        return False
    for zf in mod_folder.rglob("*PrimalGameData*.uasset.z"):
        dest = Path(str(zf)[:-2])
        if not dest.is_file():
            return True
    return False


def find_workshop_mod_folder(
    mod_id: str,
    install_dir: str = "",
    steamcmd_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Localiza pasta workshop do mod (install_dir primeiro, depois steamcmd)."""
    candidates: list[Path] = []
    if install_dir:
        candidates.append(
            Path(install_dir) / "steamapps" / "workshop" / "content"
            / ARK_WORKSHOP_APP_ID / mod_id
        )
    if steamcmd_dir:
        candidates.append(
            steamcmd_dir / "steamapps" / "workshop" / "content"
            / ARK_WORKSHOP_APP_ID / mod_id
        )
    for path in candidates:
        if path.is_dir():
            return path
    return None


def install_mod_from_workshop(
    workshop_src: Path,
    install_dir: str,
    mod_id: str,
    on_log: Optional[Callable[[str], None]] = None,
) -> bool:
    """
    Instala mod no servidor: descomprime .z, grava .mod (paridade ASM CopyMod).
    """
    _log = on_log or (lambda _m: None)
    if not workshop_src.is_dir():
        _log(f"[AVISO] Pasta workshop ausente: {workshop_src}")
        return False

    mods_dir = Path(install_dir) / "ShooterGame" / "Content" / "Mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    dest_folder = mods_dir / mod_id
    dot_mod = mods_dir / f"{mod_id}.mod"

    map_names = parse_mod_info_map_names(workshop_src / "mod.info")
    meta = parse_modmeta(workshop_src / "modmeta.info")

    mod_source = workshop_src
    if (workshop_src / "modmeta.info").is_file():
        win = workshop_src / "WindowsNoEditor"
        if win.is_dir():
            mod_source = win

    if dest_folder.exists():
        shutil.rmtree(dest_folder)
    if dot_mod.exists():
        dot_mod.unlink()

    _log(f"Copiando mod {mod_id} (descomprimindo .z)…")
    has_primal = copy_mod_tree(mod_source, dest_folder)
    if not meta and has_primal:
        meta["ModType"] = "1"

    write_mod_file(dot_mod, mod_id, meta, map_names)

    ts_src = workshop_src / LAST_UPDATED_TIME_FILE
    if ts_src.is_file():
        shutil.copy2(ts_src, dest_folder / LAST_UPDATED_TIME_FILE)

    _log(f"[OK] Mod {mod_id} instalado em {dest_folder}")
    return True


def repair_mod_decompression(
    install_dir: str,
    mod_id: str,
    steamcmd_dir: Optional[Path] = None,
    on_log: Optional[Callable[[str], None]] = None,
) -> bool:
    """Reinstala mod do workshop se PrimalGameData ainda estiver comprimido (.z)."""
    mod_folder = Path(install_dir) / "ShooterGame" / "Content" / "Mods" / mod_id
    if not mod_needs_decompress_repair(mod_folder):
        return False
    workshop = find_workshop_mod_folder(mod_id, install_dir, steamcmd_dir)
    if not workshop:
        if on_log:
            on_log(
                f"Mod {mod_id}: PrimalGameData comprimido (.z) — "
                "re-baixe o mod na aba Mods."
            )
        return False
    if on_log:
        on_log(f"Mod {mod_id}: reinstalando com descompressão UE4…")
    return install_mod_from_workshop(workshop, install_dir, mod_id, on_log)
