#!/usr/bin/env python3
"""Gera CHANGELOG.md a partir de src/version.py (fonte única de verdade)."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_PY = ROOT / "src" / "version.py"
OUTPUT = ROOT / "CHANGELOG.md"

_SECTION_MAP = (
    (re.compile(r"^(Novo|Feat|Feature)\b", re.I), "Feature"),
    (re.compile(r"^Melhoria\b", re.I), "Improvement"),
    (re.compile(r"^Fix\b", re.I), "Fix"),
    (re.compile(r"^Refactor\b", re.I), "Refactor"),
)


def _load_changelog() -> list[dict]:
    src = VERSION_PY.read_text(encoding="utf-8-sig")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        value = None
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "CHANGELOG":
                    value = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "CHANGELOG":
                value = node.value
        if value is not None:
            return ast.literal_eval(value)
    raise RuntimeError("CHANGELOG não encontrado em src/version.py")


def _clean(text: str) -> str:
    """Remove surrogates inválidos herdados de entradas antigas."""
    return text.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="replace")


def _bucket(change: str) -> str:
    for pattern, section in _SECTION_MAP:
        if pattern.search(change.strip()):
            return section
    return "Other"


def _render(entries: list[dict]) -> str:
    lines = [
        "# Changelog",
        "",
        "<!-- Gerado por scripts/sync_changelog_md.py — não edite manualmente. -->",
        "<!-- Fonte: src/version.py -->",
        "",
        "<!-- markdownlint-disable MD024 -->",
        "",
    ]
    for entry in entries:
        version = entry["version"]
        date = entry.get("date", "")
        lines.append(f"## [{version}] - {date}")
        lines.append("")
        buckets: dict[str, list[str]] = {}
        for change in entry.get("changes", []):
            clean = _clean(str(change))
            buckets.setdefault(_bucket(clean), []).append(clean)
        for section in ("Feature", "Improvement", "Fix", "Refactor", "Other"):
            items = buckets.get(section)
            if not items:
                continue
            lines.append(f"### {section}")
            lines.append("")
            for item in items:
                lines.append(f"- {item}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    entries = _load_changelog()
    OUTPUT.write_text(_render(entries), encoding="utf-8", newline="\n")
    print(f"OK: {OUTPUT} ({len(entries)} versoes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
