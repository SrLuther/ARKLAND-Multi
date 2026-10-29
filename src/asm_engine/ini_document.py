"""Lossless, ordered representation for ARK INI files.

This module deliberately does not use ``configparser`` as its storage model:
ARK INIs may contain repeated keys, repeated sections, comments and raw lines
whose position must survive a read/write cycle.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*(?:[;#].*)?$")
_KEY_RE = re.compile(r"^(\s*)([^=]+?)(\s*=\s*)(.*?)(\r\n|\n|\r)?$")


@dataclass
class IniLine:
    """One source line with its original spelling and section occurrence."""

    raw: str
    kind: str
    section: str | None = None
    section_occurrence: int | None = None
    key: str | None = None
    value: str | None = None


@dataclass(frozen=True)
class _TextEncoding:
    codec: str
    bom: bytes


def _decode(data: bytes) -> tuple[str, _TextEncoding]:
    if data.startswith(b"\xff\xfe"):
        return data[2:].decode("utf-16-le"), _TextEncoding("utf-16-le", b"\xff\xfe")
    if data.startswith(b"\xfe\xff"):
        return data[2:].decode("utf-16-be"), _TextEncoding("utf-16-be", b"\xfe\xff")
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8"), _TextEncoding("utf-8", b"\xef\xbb\xbf")
    try:
        return data.decode("utf-8"), _TextEncoding("utf-8", b"")
    except UnicodeDecodeError:
        # Existing ARK installations may contain ANSI INIs. Preserve those
        # bytes by decoding/encoding with the same reversible single-byte map.
            try:
                return data.decode("cp1252"), _TextEncoding("cp1252", b"")
            except UnicodeDecodeError:
                return data.decode("latin-1"), _TextEncoding("latin-1", b"")


def _split_lines(text: str) -> list[str]:
    if not text:
        return []
    return text.splitlines(keepends=True)


def _newline_of(lines: Iterable[IniLine]) -> str:
    for line in lines:
        if line.raw.endswith("\r\n"):
            return "\r\n"
        if line.raw.endswith("\n"):
            return "\n"
        if line.raw.endswith("\r"):
            return "\r"
    return "\r\n"


class IniDocument:
    """Ordered INI document that preserves untouched source text exactly."""

    def __init__(self, lines: list[IniLine], encoding: _TextEncoding) -> None:
        self.lines = lines
        self._encoding = encoding
        self._original_lines = tuple(line.raw for line in lines)

    @classmethod
    def parse(cls, data: bytes | str) -> "IniDocument":
        if isinstance(data, bytes):
            text, encoding = _decode(data)
            original_bytes = data
        else:
            text, encoding = data.lstrip("\ufeff"), _TextEncoding("utf-8", b"")
            original_bytes = None

        lines: list[IniLine] = []
        current_section: str | None = None
        occurrence: int | None = None
        occurrences: dict[str, int] = {}
        for raw in _split_lines(text):
            content = raw.rstrip("\r\n")
            stripped = content.strip()
            if not stripped:
                lines.append(IniLine(raw, "blank", current_section, occurrence))
                continue
            if stripped.startswith((";", "#")):
                lines.append(IniLine(raw, "comment", current_section, occurrence))
                continue

            section_match = _SECTION_RE.match(content)
            if section_match:
                current_section = section_match.group(1).strip()
                folded = current_section.casefold()
                occurrence = occurrences.get(folded, 0)
                occurrences[folded] = occurrence + 1
                lines.append(IniLine(raw, "section", current_section, occurrence))
                continue

            key_match = _KEY_RE.match(raw)
            if key_match and "=" in content:
                key = key_match.group(2).strip()
                value = key_match.group(4)
                lines.append(IniLine(raw, "key", current_section, occurrence, key, value))
                continue

            lines.append(IniLine(raw, "raw", current_section, occurrence))
        document = cls(lines, encoding)
        if original_bytes is not None:
            document._original_bytes = original_bytes
        return document

    @classmethod
    def from_file(cls, path: str) -> "IniDocument":
        from pathlib import Path

        return cls.parse(Path(path).read_bytes())

    def to_text(self) -> str:
        return "".join(line.raw for line in self.lines)

    def to_config_text(self) -> str:
        """Serialize ARK configuration only, stripping comments and raw text.

        Valid key/value lines are kept, including repeated keys. Repeated
        instances of a section are folded into its first position so the
        output contains one well-formed section header per section name.
        """
        newline = _newline_of(self.lines)
        sections: list[tuple[str, list[str]]] = []
        by_name: dict[str, list[str]] = {}
        current: list[str] | None = None
        for line in self.lines:
            if line.kind == "section" and line.section:
                folded = line.section.casefold()
                current = by_name.get(folded)
                if current is None:
                    current = []
                    by_name[folded] = current
                    sections.append((line.section, current))
            elif line.kind == "key" and current is not None:
                content = line.raw.rstrip("\r\n")
                if line.key and "=" in content:
                    current.append(content + newline)
        output: list[str] = []
        for section, entries in sections:
            output.append(f"[{section}]{newline}")
            output.extend(entries)
        return "".join(output)

    def to_config_bytes(self) -> bytes:
        """Encode only valid INI structure and key/value configuration lines."""
        text = self.to_config_text()
        if tuple(line.raw for line in self.lines) == self._original_lines:
            original_text = self.to_text()
            if text == original_text:
                return self._original_bytes
        return self._encoding.bom + text.encode(self._encoding.codec)
    def to_bytes(self) -> bytes:
        if tuple(line.raw for line in self.lines) == self._original_lines:
            # No-op round-trip is byte exact, including unusual encodings.
            return self._original_bytes
        return self._encoding.bom + self.to_text().encode(self._encoding.codec)

    @property
    def _original_bytes(self) -> bytes:
        # Stored lazily for backwards-compatible construction; parse() sets
        # the byte snapshot after decoding.
        return getattr(self, "__original_bytes", self._encoding.bom + self.to_text().encode(self._encoding.codec))

    @_original_bytes.setter
    def _original_bytes(self, value: bytes) -> None:
        self.__original_bytes = value

    def find_values(
        self,
        section: str,
        key: str,
        *,
        section_occurrence: int | None = None,
        case_sensitive: bool = False,
    ) -> list[str]:
        """Return all values in document order, without collapsing duplicates."""
        norm = (lambda value: value) if case_sensitive else (lambda value: value.casefold())
        return [
            line.value or ""
            for line in self.lines
            if line.kind == "key"
            and line.section is not None
            and norm(line.section) == norm(section)
            and norm(line.key or "") == norm(key)
            and (section_occurrence is None or line.section_occurrence == section_occurrence)
        ]

    def set_value(
        self,
        section: str,
        key: str,
        value: str,
        *,
        occurrence: int = 0,
        section_occurrence: int | None = None,
        case_sensitive: bool = False,
    ) -> None:
        """Replace one matching key occurrence, or append it to the section."""
        if occurrence < 0:
            raise ValueError("occurrence must be non-negative")
        norm = (lambda item: item) if case_sensitive else (lambda item: item.casefold())
        target_section = norm(section)
        target_key = norm(key)
        matches = [
            i for i, line in enumerate(self.lines)
            if line.kind == "key"
            and line.section is not None
            and norm(line.section) == target_section
            and norm(line.key or "") == target_key
            and (section_occurrence is None or line.section_occurrence == section_occurrence)
        ]
        if occurrence < len(matches):
            index = matches[occurrence]
            line = self.lines[index]
            match = _KEY_RE.match(line.raw)
            if match is None:
                raise ValueError("cannot safely replace malformed INI key line")
            old_value = match.group(4)
            trailing_space = old_value[len(old_value.rstrip(" \t")):]
            line.raw = f"{match.group(1)}{match.group(2)}{match.group(3)}{value}{trailing_space}{match.group(5) or ''}"
            line.value = value
            return
        self._append_key(section, key, value, section_occurrence)

    def _append_key(
        self,
        section: str,
        key: str,
        value: str,
        section_occurrence: int | None,
    ) -> None:
        newline = _newline_of(self.lines)
        section_indices = [
            i for i, line in enumerate(self.lines)
            if line.kind == "section" and (line.section or "").casefold() == section.casefold()
            and (section_occurrence is None or line.section_occurrence == section_occurrence)
        ]
        if section_indices:
            header = section_indices[-1]
            end = next(
                (i for i in range(header + 1, len(self.lines)) if self.lines[i].kind == "section"),
                len(self.lines),
            )
            # If a specific earlier section occurrence was requested, stop at
            # its next section rather than appending to the final occurrence.
            if section_occurrence is not None:
                end = header + 1
                while end < len(self.lines) and self.lines[end].kind != "section":
                    end += 1
            insert_at = end
            while insert_at > header + 1 and self.lines[insert_at - 1].kind == "blank":
                insert_at -= 1
            if insert_at > 0 and not self.lines[insert_at - 1].raw.endswith(("\n", "\r")):
                self.lines[insert_at - 1].raw += newline
            self.lines.insert(insert_at, IniLine(f"{key}={value}{newline}", "key", section, self.lines[header].section_occurrence, key, value))
            return

        if self.lines and not self.lines[-1].raw.endswith(("\n", "\r")):
            self.lines[-1].raw += newline
        if self.lines and self.lines[-1].kind != "blank":
            self.lines.append(IniLine(newline, "blank"))
        occurrence = sum(1 for line in self.lines if line.kind == "section" and (line.section or "").casefold() == section.casefold())
        self.lines.extend((
            IniLine(f"[{section}]{newline}", "section", section, occurrence),
            IniLine(f"{key}={value}{newline}", "key", section, occurrence, key, value),
        ))

    def ensure_section(self, section: str) -> None:
        """Append an empty section only when no case-insensitive match exists."""
        if any(
            line.kind == "section" and (line.section or "").casefold() == section.casefold()
            for line in self.lines
        ):
            return
        newline = _newline_of(self.lines)
        if self.lines and not self.lines[-1].raw.endswith(("\n", "\r")):
            self.lines[-1].raw += newline
        if self.lines and self.lines[-1].kind != "blank":
            self.lines.append(IniLine(newline, "blank"))
        self.lines.append(IniLine(f"[{section}]{newline}", "section", section, 0))
    def remove_values(
        self,
        section: str,
        key: str,
        *,
        section_occurrence: int | None = None,
        occurrence: int | None = None,
        case_sensitive: bool = False,
    ) -> int:
        """Remove matching key lines; optionally remove just one occurrence."""
        norm = (lambda item: item) if case_sensitive else (lambda item: item.casefold())
        indices = [
            i for i, line in enumerate(self.lines)
            if line.kind == "key" and line.section is not None
            and norm(line.section) == norm(section) and norm(line.key or "") == norm(key)
            and (section_occurrence is None or line.section_occurrence == section_occurrence)
        ]
        if occurrence is not None:
            if occurrence < 0:
                raise ValueError("occurrence must be non-negative")
            indices = indices[occurrence:occurrence + 1]
        for index in reversed(indices):
            del self.lines[index]
        return len(indices)

    def remove_keys(
        self,
        section: str,
        keys: Iterable[str],
        *,
        case_sensitive: bool = False,
    ) -> int:
        """Remove all occurrences of several keys from one section."""
        key_set = {key if case_sensitive else key.casefold() for key in keys}
        before = len(self.lines)
        self.lines[:] = [
            line for line in self.lines
            if not (
                line.kind == "key"
                and line.section is not None
                and (line.section if case_sensitive else line.section.casefold())
                == (section if case_sensitive else section.casefold())
                and (line.key if case_sensitive else (line.key or "").casefold()) in key_set
            )
        ]
        return before - len(self.lines)


def sanitize_ini_bytes(data: bytes) -> bytes:
    """Keep only valid section headers and key/value configuration lines."""
    return IniDocument.parse(data).to_config_bytes()
