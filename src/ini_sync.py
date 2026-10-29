"""Transactional helpers for comparing and synchronizing ARK INI files."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import os
from pathlib import Path
import tempfile
from typing import Mapping

from .asm_engine.ini_document import IniDocument, IniLine, sanitize_ini_bytes


def _config_counter(data: bytes) -> Counter[tuple[str, str, str]]:
    document = IniDocument.parse(sanitize_ini_bytes(data))
    return Counter(
        ((line.section or "").casefold(), (line.key or "").casefold(), line.value or "")
        for line in document.lines
        if line.kind == "key" and line.key
    )


def diff_ini_bytes(source: bytes, destination: bytes | None) -> tuple[int, int]:
    """Return added and removed config occurrences from destination vs source."""
    src = _config_counter(source)
    dst = _config_counter(destination or b"")
    additions = sum((src - dst).values())
    removals = sum((dst - src).values())
    return additions, removals


def diff_ini_entries(source: bytes, destination: bytes | None) -> tuple[list[str], list[str]]:
    """Return ordered human-readable added and removed entries for a preview."""
    def entries(data: bytes | None) -> list[tuple[str, str, str]]:
        document = IniDocument.parse(sanitize_ini_bytes(data or b""))
        return [
            (line.section or "", line.key or "", line.value or "")
            for line in document.lines if line.kind == "key" and line.key
        ]

    src = entries(source)
    dst = entries(destination)

    def unmatched(left: list[tuple[str, str, str]], right: list[tuple[str, str, str]]) -> list[str]:
        available = Counter((section.casefold(), key.casefold(), value) for section, key, value in right)
        result: list[str] = []
        for section, key, value in left:
            item = (section.casefold(), key.casefold(), value)
            if available[item]:
                available[item] -= 1
                continue
            safe_value = "<oculto>" if any(
                token in key.casefold() for token in ("password", "passwd", "token", "secret", "apikey", "api_key")
            ) else value
            result.append(f"[{section}] {key}={safe_value}")
        return result

    return unmatched(src, dst), unmatched(dst, src)


def merge_ini_sections(
    source: bytes,
    destination: bytes | None,
    selected_sections: set[str] | frozenset[str],
) -> bytes:
    """Replace only selected section names, preserving other destination sections.

    Section matching is case-insensitive. Repeated section occurrences and
    repeated keys remain in document order. A selected section absent from the
    source is removed from the destination.
    """
    selected = {str(name).strip().casefold() for name in selected_sections if str(name).strip()}
    source_doc = IniDocument.parse(sanitize_ini_bytes(source))
    destination_doc = IniDocument.parse(destination or b"")
    if not selected:
        return destination_doc.to_config_bytes()

    def sections(document: IniDocument) -> list[tuple[str, list[IniLine]]]:
        result: list[tuple[str, list[IniLine]]] = []
        current_name: str | None = None
        current_lines: list[IniLine] | None = None
        for line in document.lines:
            if line.kind == "section" and line.section:
                current_name = line.section
                current_lines = []
                result.append((current_name, current_lines))
            elif line.kind == "key" and current_name is not None and current_lines is not None:
                current_lines.append(line)
        return result

    source_sections = [item for item in sections(source_doc) if item[0].casefold() in selected]
    source_names = {name.casefold() for name, _ in source_sections}
    ordered: list[tuple[str, list[IniLine]]] = []
    emitted_source_names: set[str] = set()
    for name, lines in sections(destination_doc):
        folded = name.casefold()
        if folded not in selected:
            ordered.append((name, lines))
        elif folded in source_names and folded not in emitted_source_names:
            ordered.extend(item for item in source_sections if item[0].casefold() == folded)
            emitted_source_names.add(folded)
    ordered.extend(
        item for item in source_sections if item[0].casefold() not in emitted_source_names
    )

    newline = "\r\n"
    for line in destination_doc.lines or source_doc.lines:
        if line.raw.endswith("\r\n"):
            newline = "\r\n"
            break
        if line.raw.endswith("\n"):
            newline = "\n"
            break
        if line.raw.endswith("\r"):
            newline = "\r"
            break

    merged: list[IniLine] = []
    occurrences: dict[str, int] = {}
    for section_name, key_lines in ordered:
        folded = section_name.casefold()
        occurrence = occurrences.get(folded, 0)
        occurrences[folded] = occurrence + 1
        merged.append(IniLine(f"[{section_name}]{newline}", "section", section_name, occurrence))
        for line in key_lines:
            raw = line.raw.rstrip("\r\n")
            merged.append(IniLine(raw + newline, "key", section_name, occurrence, line.key, line.value))
    destination_doc.lines = merged
    return destination_doc.to_config_bytes()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def sync_ini_targets(
    files: Mapping[Path, bytes],
    *,
    backup_dir: Path | None = None,
    timestamp: str | None = None,
) -> list[Path]:
    """Back up all existing targets, then atomically replace them as one batch.

    If any replacement fails, every already replaced target is restored from its
    in-memory original (or removed if it did not exist before the batch).
    Persistent backups remain available for operator recovery after success.
    """
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    normalized = {path.resolve(): sanitize_ini_bytes(data) for path, data in files.items()}
    originals = {path: path.read_bytes() if path.exists() else None for path in normalized}
    backups: list[Path] = []

    for index, (path, original) in enumerate(originals.items()):
        if original is None:
            continue
        target_backup_dir = backup_dir or (path.parent / "ArklandIniBackups")
        target_backup_dir.mkdir(parents=True, exist_ok=True)
        backup = target_backup_dir / f"{path.stem}_{stamp}_{index}.bak"
        _atomic_write(backup, original)
        backups.append(backup)

    applied: list[Path] = []
    try:
        for path, data in normalized.items():
            _atomic_write(path, data)
            applied.append(path)
    except Exception:
        rollback_errors: list[str] = []
        for path in reversed(applied):
            original = originals[path]
            try:
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    _atomic_write(path, original)
            except OSError as rollback_exc:
                rollback_errors.append(f"{path}: {rollback_exc}")
        if rollback_errors:
            raise RuntimeError(
                f"Sincronização falhou e o rollback teve erros: {'; '.join(rollback_errors)}"
            )
        raise
    return backups
