"""Transactional helpers for comparing and synchronizing ARK INI files."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
import re
from typing import Callable, Mapping

from .asm_engine.ini_document import IniDocument, IniLine, sanitize_ini_bytes
from .ini_write_safety import atomic_replace


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
    source_doc = IniDocument.parse(source)
    # Files created by sync follow the ARK default; existing targets retain
    # their own encoding/BOM because the destination document controls output.
    destination_doc = IniDocument.parse(destination if destination is not None else b"\xff\xfe")
    if not selected:
        return destination_doc.to_bytes()

    def sections(document: IniDocument) -> tuple[list[IniLine], list[tuple[str, list[IniLine]]]]:
        prefix: list[IniLine] = []
        result: list[tuple[str, list[IniLine]]] = []
        current_name: str | None = None
        current_lines: list[IniLine] | None = None
        for line in document.lines:
            if line.kind == "section" and line.section:
                current_name = line.section
                current_lines = [line]
                result.append((current_name, current_lines))
            elif current_name is not None and current_lines is not None:
                current_lines.append(line)
            else:
                prefix.append(line)
        return prefix, result

    source_prefix, source_all = sections(source_doc)
    destination_prefix, destination_all = sections(destination_doc)
    del source_prefix  # A section sync does not import global preamble text.
    source_sections = [item for item in source_all if item[0].casefold() in selected]
    source_by_name: dict[str, list[tuple[str, list[IniLine]]]] = {}
    for item in source_sections:
        source_by_name.setdefault(item[0].casefold(), []).append(item)

    newline = "\r\n"
    for line in destination_doc.lines:
        if line.raw.endswith(("\r\n", "\n", "\r")):
            newline = "\r\n" if line.raw.endswith("\r\n") else line.raw[-1]
            break

    def with_target_newline(lines: list[IniLine]) -> list[IniLine]:
        normalized: list[IniLine] = []
        for line in lines:
            raw = re.sub(r"\r\n|\r|\n", newline, line.raw)
            normalized.append(IniLine(raw, line.kind, line.section, line.section_occurrence, line.key, line.value))
        return normalized

    emitted_source_names: set[str] = set()
    merged_lines = list(destination_prefix)
    for name, lines in destination_all:
        folded = name.casefold()
        if folded not in selected:
            merged_lines.extend(lines)
        elif folded in source_by_name and folded not in emitted_source_names:
            for _source_name, source_lines in source_by_name[folded]:
                merged_lines.extend(with_target_newline(source_lines))
            emitted_source_names.add(folded)
        # A selected destination section missing from the source is deliberately removed.
    for name, lines in source_sections:
        folded = name.casefold()
        if folded not in emitted_source_names:
            merged_lines.extend(with_target_newline(lines))
            emitted_source_names.add(folded)
    destination_doc.lines = merged_lines
    return destination_doc.to_bytes()


def _atomic_write(path: Path, data: bytes) -> None:
    atomic_replace(path, data)


def import_ini_targets(
    sources: Mapping[Path, Path],
    *,
    validate_target: Callable[[Path], None] | None = None,
) -> list[Path]:
    """Copy selected source INI bytes as a backed-up, atomic target batch."""
    payload: dict[Path, bytes] = {}
    for target, source in sources.items():
        if target.resolve() == source.resolve():
            continue
        payload[target] = source.read_bytes()
    return sync_ini_targets(payload, validate_target=validate_target)


def sync_ini_targets(
    files: Mapping[Path, bytes],
    *,
    backup_dir: Path | None = None,
    timestamp: str | None = None,
    validate_target: Callable[[Path], None] | None = None,
) -> list[Path]:
    """Back up all existing targets, then atomically replace them as one batch.

    If any replacement fails, every already replaced target is restored from its
    in-memory original (or removed if it did not exist before the batch).
    Persistent backups remain available for operator recovery after success.
    """
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    normalized = {path.resolve(): data for path, data in files.items()}
    if validate_target:
        for path in normalized:
            validate_target(path)
    originals = {path: path.read_bytes() if path.exists() else None for path in normalized}
    backups: list[Path] = []

    for index, (path, original) in enumerate(originals.items()):
        if original is None:
            continue
        target_backup_dir = backup_dir or (path.parent / "ArklandIniBackups")
        target_backup_dir.mkdir(parents=True, exist_ok=True)
        backup = target_backup_dir / f"{path.stem}_{stamp}_{index}.bak"
        if backup.exists():
            raise FileExistsError(f"Backup já existe: {backup}")
        _atomic_write(backup, original)
        backups.append(backup)

    applied: list[Path] = []
    try:
        for path, data in normalized.items():
            if validate_target:
                validate_target(path)
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
