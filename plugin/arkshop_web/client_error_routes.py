"""Ingest and admin-only viewer for browser-side errors and warnings."""
from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from flask import Flask, jsonify, request

_LOCK = threading.RLock()
_MAX_FILE_BYTES = 16 * 1024 * 1024
_MAX_EVENTS = 30
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_STEAM_RE = re.compile(r"\b7656119\d{10}\b")
_SECRET_RE = re.compile(r"(?i)(bearer\s+|token[\"']?\s*[:=]\s*[\"']?)[^\s,;\"']+")
_LONG_NUMBER_RE = re.compile(r"\b\d{8,}\b")
_URL_QUERY_RE = re.compile(r"(?i)((?:https?://|/)[^\s?#\"']+)[?#][^\s\"')]*")


def _clean(value: Any, limit: int = 3000) -> str:
    text = "".join(ch for ch in str(value or "") if ch.isprintable())
    text = _SECRET_RE.sub(r"\1[redacted]", text)
    text = _URL_QUERY_RE.sub(r"\1", text)
    text = _EMAIL_RE.sub("[email]", text)
    text = _STEAM_RE.sub("[steam-id]", text)
    text = _LONG_NUMBER_RE.sub("[number]", text)
    return text[:limit]


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    try:
        with _LOCK, path.open("r", encoding="utf-8") as stream:
            for line in stream:
                try:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        out.append(item)
                except (ValueError, TypeError):
                    continue
    except OSError:
        return []
    return out


def _prune_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    size = 0
    for event in reversed(events):
        line_size = len(json.dumps(event, ensure_ascii=False)) + 1
        if size + line_size > int(_MAX_FILE_BYTES * 0.75):
            break
        kept.append(event)
        size += line_size
    return list(reversed(kept))


def register_client_error_routes(
    app: Flask, *, admin_required: Callable, limiter: Any, data_dir: Path,
    get_plugin_versions: Callable[[], dict[str, Any]] | None = None,
) -> None:
    store = Path(data_dir) / "client-errors.jsonl"

    @app.post("/api/client-errors")
    @limiter.limit("30 per minute", override_defaults=True)
    def ingest_client_errors():
        if request.content_length is not None and request.content_length > 256 * 1024:
            return jsonify({"ok": False, "error": "payload_too_large"}), 413
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not isinstance(body.get("events"), list):
            return jsonify({"ok": False, "error": "invalid_payload"}), 400
        accepted = []
        try:
            plugin_versions = get_plugin_versions() if get_plugin_versions else {}
        except Exception:
            app.logger.debug("Could not enrich client error with plugin versions", exc_info=True)
            plugin_versions = {}
        if not isinstance(plugin_versions, dict):
            plugin_versions = {}
        for raw in body["events"][:_MAX_EVENTS]:
            if not isinstance(raw, dict):
                continue
            severity = str(raw.get("severity") or "error").lower()
            if severity not in {"error", "warning"}:
                continue
            message = _clean(raw.get("message"), 2000)
            if not message:
                continue
            try:
                occurrences = max(1, min(int(raw.get("occurrences", 1) or 1), 1000))
            except (TypeError, ValueError):
                occurrences = 1
            context = raw.get("context") if isinstance(raw.get("context"), dict) else {}
            safe_context = {
                _clean(key, 40): _clean(value, 300)
                for key, value in list(context.items())[:20]
                if isinstance(key, str) and isinstance(value, (str, int, float, bool))
            }
            path = _clean(raw.get("path"), 180).split("?", 1)[0].split("#", 1)[0]
            event = {
                "id": uuid.uuid4().hex,
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "severity": severity,
                "category": _clean(raw.get("category") or "client", 40),
                "message": message,
                "page": path or "/",
                "source": _clean(raw.get("source"), 400).split("?", 1)[0].split("#", 1)[0],
                "stack": _clean(raw.get("stack"), 5000),
                "user_agent": _clean(raw.get("user_agent"), 500),
                "context": safe_context,
                "plugin_versions": plugin_versions,
                "occurrences": occurrences,
            }
            event["fingerprint"] = hashlib.sha256(
                (event["category"] + "\0" + event["message"] + "\0" + event["source"]).encode("utf-8")
            ).hexdigest()[:20]
            accepted.append(event)
        if not accepted:
            return jsonify({"ok": True, "accepted": 0})
        try:
            store.parent.mkdir(parents=True, exist_ok=True)
            with _LOCK:
                if store.exists() and store.stat().st_size > _MAX_FILE_BYTES:
                    existing = _prune_events(_read_events(store))
                    store.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in existing), encoding="utf-8")
                with store.open("a", encoding="utf-8") as stream:
                    for event in accepted:
                        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError:
            app.logger.exception("Could not persist browser error events")
            return jsonify({"ok": False, "error": "storage_unavailable"}), 503
        return jsonify({"ok": True, "accepted": len(accepted)})

    @app.get("/api/admin/client-errors")
    @admin_required
    def list_client_errors():
        all_events = _read_events(store)
        events = sorted(all_events, key=lambda item: item.get("timestamp", ""), reverse=True)
        severity = request.args.get("severity", "").lower()
        query = _clean(request.args.get("q", ""), 100).lower()
        if severity in {"error", "warning"}:
            events = [event for event in events if event.get("severity") == severity]
        if query:
            events = [event for event in events if query in " ".join((event.get("message", ""), event.get("source", ""), event.get("page", ""), event.get("stack", ""))).lower()]
        total = len(events)
        try:
            limit = max(1, min(int(request.args.get("limit", "100")), 200))
            offset = max(0, int(request.args.get("offset", "0")))
        except ValueError:
            return jsonify({"ok": False, "error": "invalid_pagination"}), 400
        return jsonify({
            "ok": True,
            "events": events[offset:offset + limit],
            "total": total,
            "summary": {
                "errors": sum(int(event.get("occurrences", 1) or 1) for event in all_events if event.get("severity") == "error"),
                "warnings": sum(int(event.get("occurrences", 1) or 1) for event in all_events if event.get("severity") == "warning"),
            },
        })
