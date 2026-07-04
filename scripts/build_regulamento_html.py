"""Gera plugin/arkshop_web/static/regulamento_v{version}.html a partir do markdown."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "plugin" / "arkshop_web"
sys.path.insert(0, str(WEB))

from regulamento_config import REGULAMENTO_SOURCE_DOC, REGULAMENTO_VERSION  # noqa: E402
from regulamento_service import _markdown_to_html  # noqa: E402


def _content_start(md: str) -> int:
    for marker in ("## Sumário", "## 1."):
        pos = md.find(marker)
        if pos >= 0:
            return pos
    return 0


def build(*, version: str | None = None) -> Path:
    ver = (version or REGULAMENTO_VERSION).strip()
    md_path = ROOT / REGULAMENTO_SOURCE_DOC
    if not md_path.is_file():
        raise SystemExit(f"Markdown não encontrado: {md_path}")

    md = md_path.read_text(encoding="utf-8")
    html_body = _markdown_to_html(md[_content_start(md):])
    out = WEB / "static" / f"regulamento_v{ver.replace('.', '_')}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_body, encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)} ({len(html_body)} bytes)")
    return out


if __name__ == "__main__":
    build()
