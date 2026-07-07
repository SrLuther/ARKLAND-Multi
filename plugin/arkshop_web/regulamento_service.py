"""Aceite e entrega do Regulamento ARKLAND na Web Store."""
from __future__ import annotations

import html
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from flask import jsonify, request
from sqlalchemy import text

from regulamento_config import (
    REGULAMENTO_SOURCE_DOC,
    REGULAMENTO_TITLE,
    REGULAMENTO_UPDATED_AT,
    REGULAMENTO_VERSION,
)


def _bundle_dir() -> Path:
    """Dev: plugin/arkshop_web — PyInstaller onefile: sys._MEIPASS."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def _repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return _bundle_dir()
    return Path(__file__).resolve().parent.parent.parent


_REGULAMENTO_MD_PATH = _repo_root() / REGULAMENTO_SOURCE_DOC
_STATIC_HTML_PATH = (
    _bundle_dir() / "static" / f"regulamento_v{REGULAMENTO_VERSION.replace('.', '_')}.html"
)
_SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_H2_SECTION_RE = re.compile(r'<h2\s+id="([^"]+)"[^>]*>([^<]+)</h2>')


def _section_titles_from_markdown(md: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    for m in _SECTION_RE.finditer(md):
        title = m.group(1).strip()
        anchor = re.sub(r"[^\w\-]+", "-", title.lower()).strip("-")
        sections.append({"title": title, "anchor": anchor})
    return sections


def _section_titles_from_html(html_text: str) -> list[dict[str, str]]:
    return [
        {"title": title.strip(), "anchor": anchor.strip()}
        for anchor, title in _H2_SECTION_RE.findall(html_text)
    ]


def _version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in str(version or "").strip().split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            break
    return tuple(parts)


def needs_regulamento_accept(accepted_version: str | None) -> bool:
    if not (accepted_version or "").strip():
        return True
    return _version_tuple(accepted_version) < _version_tuple(REGULAMENTO_VERSION)


def regulamento_meta() -> dict[str, Any]:
    sections: list[dict[str, str]] = []
    if _REGULAMENTO_MD_PATH.is_file():
        md = _REGULAMENTO_MD_PATH.read_text(encoding="utf-8")
        sections = _section_titles_from_markdown(md)
    elif _STATIC_HTML_PATH.is_file():
        sections = _section_titles_from_html(_STATIC_HTML_PATH.read_text(encoding="utf-8"))
    return {
        "version": REGULAMENTO_VERSION,
        "updated_at": REGULAMENTO_UPDATED_AT,
        "title": REGULAMENTO_TITLE,
        "sections": sections,
    }


def _inline_markdown(text: str) -> str:
    """Escape HTML e converte negrito/links inline do markdown."""
    body = html.escape(text.strip())
    body = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2" target="_blank" rel="noopener">\1</a>',
        body,
    )
    body = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", body)
    return body


def _markdown_to_html(md: str) -> str:
    """Conversão leve markdown→HTML para o regulamento (MVP)."""
    lines = md.splitlines()
    out: list[str] = []
    in_ul = False
    in_table = False

    def close_ul() -> None:
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    def close_table() -> None:
        nonlocal in_table
        if in_table:
            out.append("</tbody></table>")
            in_table = False

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            close_ul()
            close_table()
            out.append("")
            continue
        if line.startswith("# "):
            close_ul()
            close_table()
            out.append(f"<h1>{html.escape(line[2:].strip())}</h1>")
            continue
        if line.startswith("## "):
            close_ul()
            close_table()
            title = line[3:].strip()
            anchor = re.sub(r"[^\w\-]+", "-", title.lower()).strip("-")
            out.append(f'<h2 id="{html.escape(anchor)}">{html.escape(title)}</h2>')
            continue
        if line.startswith("### "):
            close_ul()
            close_table()
            out.append(f"<h3>{html.escape(line[4:].strip())}</h3>")
            continue
        if line.startswith("|") and "|" in line[1:]:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= {"-", ":"} for c in cells):
                continue
            close_ul()
            if not in_table:
                out.append('<table class="regulamento-table"><tbody>')
                in_table = True
            row = "".join(f"<td>{_inline_markdown(c)}</td>" for c in cells)
            out.append(f"<tr>{row}</tr>")
            continue
        if line.startswith("- "):
            close_table()
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{_inline_markdown(line[2:])}</li>")
            continue
        close_ul()
        close_table()
        out.append(f"<p>{_inline_markdown(line)}</p>")

    close_ul()
    close_table()
    return "\n".join(out)


def regulamento_content_html() -> str:
    if _STATIC_HTML_PATH.is_file():
        return _STATIC_HTML_PATH.read_text(encoding="utf-8")
    if _REGULAMENTO_MD_PATH.is_file():
        md = _REGULAMENTO_MD_PATH.read_text(encoding="utf-8")
        # Remove cabeçalho de metadados markdown (tabela inicial)
        start = md.find("## Sumário")
        if start < 0:
            start = md.find("## 1.")
        if start < 0:
            start = 0
        return _markdown_to_html(md[start:])
    return "<p>Regulamento indisponível no momento.</p>"


def auth_regulamento_fields(
    steam_id: str,
    *,
    db_get_store_user: Callable[[str], Any],
) -> dict[str, Any]:
    row = db_get_store_user(steam_id)
    accepted = (row.regulamento_accepted_version if row else None) or None
    accepted_at = row.regulamento_accepted_at if row else None
    pending = needs_regulamento_accept(accepted)
    return {
        "needs_regulamento_accept": pending,
        "regulamento_version_current": REGULAMENTO_VERSION,
        "regulamento_version_accepted": accepted,
        "regulamento_accepted_at": (
            accepted_at.isoformat() if hasattr(accepted_at, "isoformat") else None
        ),
    }


def guard_regulamento_accepted(
    steam_id: str,
    *,
    db_get_store_user: Callable[[str], Any],
) -> Any:
    row = db_get_store_user(steam_id)
    accepted = (row.regulamento_accepted_version if row else None) or None
    if not needs_regulamento_accept(accepted):
        return None
    return jsonify({
        "ok": False,
        "error": "Aceite o Regulamento do Servidor ARKLAND para continuar.",
        "needs_regulamento_accept": True,
        "regulamento_version_current": REGULAMENTO_VERSION,
    }), 403


def accept_regulamento(
    *,
    steam_id: str,
    version: str,
    db_session: Any,
    store_user_model: Any,
    audit_fn: Callable[..., None] | None = None,
    now_fn: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    ver = str(version or "").strip()
    if ver != REGULAMENTO_VERSION:
        return {
            "ok": False,
            "error": f"Versão inválida — vigente: {REGULAMENTO_VERSION}",
        }
    now = (now_fn or (lambda: datetime.now(timezone.utc)))()
    row = db_session.get(store_user_model, steam_id)
    if row is None:
        row = store_user_model(steam_id=steam_id, display_name=steam_id)
        db_session.add(row)
    row.regulamento_accepted_version = ver
    row.regulamento_accepted_at = now
    db_session.commit()
    if audit_fn:
        audit_fn(
            event_type="regulamento_accepted",
            actor_steam_id=steam_id,
            actor_type="player",
            message=f"Regulamento v{ver}",
            version=ver,
        )
    return {
        "ok": True,
        "regulamento_version_accepted": ver,
        "regulamento_accepted_at": now.isoformat(),
        "needs_regulamento_accept": False,
    }


def ensure_regulamento_columns(engine: Any, *, table_exists: Callable[[Any, str], bool]) -> None:
    """Adiciona colunas de aceite em store_users (MySQL incremental)."""
    if not table_exists(engine, "store_users"):
        return
    is_mysql = "mysql" in str(engine.url).lower()
    if not is_mysql:
        return
    with engine.connect() as conn:
        cols = {
            str(row[0])
            for row in conn.execute(text("SHOW COLUMNS FROM `store_users`")).fetchall()
        }
        alters: list[str] = []
        if "regulamento_accepted_version" not in cols:
            alters.append("ADD COLUMN `regulamento_accepted_version` VARCHAR(16) NULL")
        if "regulamento_accepted_at" not in cols:
            alters.append("ADD COLUMN `regulamento_accepted_at` DATETIME NULL")
        for fragment in alters:
            conn.execute(text(f"ALTER TABLE `store_users` {fragment}"))
        if alters:
            conn.commit()


def register_regulamento_routes(
    app: Any,
    *,
    login_required: Callable,
    db_ready: Callable[[], bool],
    session_factory: Callable[[], Any],
    steam_id_from_session: Callable[[], str | None],
    store_user_model: Any,
    audit_fn: Callable[..., None] | None = None,
) -> None:
    @app.route("/api/regulamento/meta", methods=["GET"])
    def regulamento_meta_route():
        return jsonify({"ok": True, **regulamento_meta()})

    @app.route("/api/regulamento/content", methods=["GET"])
    def regulamento_content_route():
        return jsonify({
            "ok": True,
            "version": REGULAMENTO_VERSION,
            "html": regulamento_content_html(),
        })

    @app.route("/api/regulamento/status", methods=["GET"])
    @login_required
    def regulamento_status_route():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        steam_id = str(steam_id_from_session())
        db = session_factory()
        try:
            fields = auth_regulamento_fields(
                steam_id, db_get_store_user=lambda sid: db.get(store_user_model, sid)
            )
            return jsonify({"ok": True, **fields})
        finally:
            db.close()

    @app.route("/api/regulamento/accept", methods=["POST"])
    @login_required
    def regulamento_accept_route():
        if not db_ready():
            return jsonify({"ok": False, "error": "Banco não configurado"}), 503
        body = request.get_json(force=True, silent=True) or {}
        steam_id = str(steam_id_from_session())
        db = session_factory()
        try:
            result = accept_regulamento(
                steam_id=steam_id,
                version=str(body.get("version") or ""),
                db_session=db,
                store_user_model=store_user_model,
                audit_fn=audit_fn,
            )
            status = 200 if result.get("ok") else 400
            return jsonify(result), status
        finally:
            db.close()
