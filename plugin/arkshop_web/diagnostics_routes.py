"""Recepção de pacotes de diagnóstico enviados pelo ARKLAND Server Manager (opt-in).

  POST /api/diagnostics                      — API key (X-API-Key), multipart: file=<zip>
  GET  /api/admin/diagnostics                — admin: lista os pacotes recebidos
  GET  /api/admin/diagnostics/<id>/download  — admin: baixa um pacote

Segurança:
  * autenticação por API key (mesma ``ARKSHOP_API_KEY`` das demais rotas internas);
  * rate-limit agressivo (6/hora, 20/dia por IP);
  * tamanho máximo do upload (``ARKSHOP_DIAGNOSTICS_MAX_MB``, padrão 25 MB), checado
    pelo ``Content-Length`` ANTES de ler o corpo e de novo ao gravar;
  * o nome do arquivo do cliente é IGNORADO — o id é gerado no servidor
    (``AAAAMMDD-HHMMSS-<8 hex>``); ``<id>`` nas rotas admin é validado por regex
    (sem path traversal);
  * o zip é só validado (assinatura, listagem, sem ``..``/caminhos absolutos, limite de
    entradas e de tamanho descompactado) — nunca é extraído no servidor;
  * retenção: no máximo ``ARKSHOP_DIAGNOSTICS_KEEP`` pacotes (padrão 100).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from flask import Flask, jsonify, request, send_file

log = logging.getLogger("arkshop_web.diagnostics_routes")

_ID_RE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{8}$")
_SAFE_TEXT_RE = re.compile(r"[^\w .,@:+\-/()\[\]áéíóúâêôãõçÁÉÍÓÚÂÊÔÃÕÇ]")
_MAX_ENTRIES = 3000
_MAX_UNCOMPRESSED = 400 * 1024 * 1024
_MAX_MB_DEFAULT = 25
_KEEP_DEFAULT = 100
_OVERHEAD = 256 * 1024     # campos multipart + cabeçalhos além do arquivo


def _max_bytes() -> int:
    try:
        mb = float(os.environ.get("ARKSHOP_DIAGNOSTICS_MAX_MB", _MAX_MB_DEFAULT))
    except ValueError:
        mb = _MAX_MB_DEFAULT
    return int(max(1.0, min(mb, 200.0)) * 1024 * 1024)


def _keep() -> int:
    try:
        return max(5, int(os.environ.get("ARKSHOP_DIAGNOSTICS_KEEP", _KEEP_DEFAULT)))
    except ValueError:
        return _KEEP_DEFAULT


def clean_text(value: Any, limit: int) -> str:
    """Texto curto e seguro para metadados (sem caracteres de controle, tamanho limitado)."""
    text = str(value or "")
    text = "".join(ch for ch in text if ch.isprintable())
    return _SAFE_TEXT_RE.sub("", text).strip()[:limit]


def validate_zip(path: Path) -> Optional[str]:
    """Devolve mensagem de erro, ou ``None`` se o zip é aceitável."""
    try:
        with open(path, "rb") as fh:
            if fh.read(4) != b"PK\x03\x04":
                return "arquivo não é um zip"
        with zipfile.ZipFile(path) as zf:
            infos = zf.infolist()
            if not infos:
                return "zip vazio"
            if len(infos) > _MAX_ENTRIES:
                return "zip com entradas demais"
            total = 0
            for info in infos:
                name = info.filename.replace("\\", "/")
                if name.startswith("/") or re.match(r"^[A-Za-z]:", name) or ".." in name.split("/"):
                    return "zip com caminho inválido"
                total += info.file_size
                if total > _MAX_UNCOMPRESSED:
                    return "zip descompactado grande demais"
    except zipfile.BadZipFile:
        return "zip corrompido"
    except OSError:
        return "falha ao ler o zip"
    return None


def _prune(directory: Path, keep: int) -> None:
    """Mantém só os ``keep`` pacotes mais recentes (o id começa pela data → ordem lexical)."""
    try:
        zips = sorted(p for p in directory.glob("*.zip") if _ID_RE.match(p.stem))
        for old in zips[:-keep] if len(zips) > keep else []:
            for victim in (old, old.with_suffix(".json")):
                try:
                    victim.unlink()
                except OSError:
                    pass
    except OSError:
        log.warning("diagnostics: falha ao aplicar retenção", exc_info=True)


def _read_meta(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def register_diagnostics_routes(
    app: Flask,
    *,
    api_key_required: Callable,
    admin_required: Callable,
    limiter: Any,
    data_dir: Path,
) -> None:
    store = Path(data_dir) / "diagnostics"

    def _fail(msg: str, code: int = 400):
        return jsonify({"ok": False, "error": msg}), code

    @app.route("/api/diagnostics", methods=["POST"])
    @limiter.limit("6 per hour; 20 per day", override_defaults=True)   # antes da auth: freia força bruta
    @api_key_required(allow_admin_session=False)
    def diagnostics_ingest():
        limit = _max_bytes()
        length = request.content_length
        if length is None:
            return _fail("Content-Length obrigatório", 411)
        if length > limit + _OVERHEAD:
            return _fail("pacote grande demais", 413)
        try:
            request.max_content_length = limit + _OVERHEAD   # Flask ≥ 3.1: limite por request
        except Exception:  # noqa: BLE001
            pass
        upload = request.files.get("file")
        if upload is None:
            return _fail("campo 'file' (zip) obrigatório")

        try:
            store.mkdir(parents=True, exist_ok=True)
        except OSError:
            log.exception("diagnostics: pasta de destino indisponível")
            return _fail("armazenamento indisponível", 500)

        diag_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(4)}"
        tmp = store / f".{diag_id}.part"
        final = store / f"{diag_id}.zip"
        digest = hashlib.sha256()
        size = 0
        try:
            with open(tmp, "wb") as out:
                while True:
                    chunk = upload.stream.read(64 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > limit:
                        raise ValueError("size")
                    digest.update(chunk)
                    out.write(chunk)
        except ValueError:
            tmp.unlink(missing_ok=True)
            return _fail("pacote grande demais", 413)
        except OSError:
            tmp.unlink(missing_ok=True)
            log.exception("diagnostics: falha ao gravar upload")
            return _fail("falha ao gravar o pacote", 500)

        problem = validate_zip(tmp)
        if problem:
            tmp.unlink(missing_ok=True)
            return _fail(f"pacote inválido: {problem}", 400)

        os.replace(tmp, final)
        summary: Dict[str, Any] = {}
        try:
            raw = json.loads(request.form.get("doctor_summary") or "{}")
            if isinstance(raw, dict):
                summary = {clean_text(k, 12): int(v) for k, v in list(raw.items())[:6]
                           if isinstance(v, (int, float))}
        except (ValueError, TypeError):
            summary = {}
        meta = {
            "id": diag_id,
            "size": size,
            "sha256": digest.hexdigest(),
            "received_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "remote_addr": clean_text(request.remote_addr, 45),
            "app_version": clean_text(request.form.get("app_version"), 40),
            "ui_mode": clean_text(request.form.get("ui_mode"), 16),
            "machine": clean_text(request.form.get("machine"), 64),
            "note": clean_text(request.form.get("note"), 500),
            "doctor_summary": summary,
        }
        try:
            final.with_suffix(".json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            log.warning("diagnostics: metadados não gravados para %s", diag_id, exc_info=True)
        _prune(store, _keep())
        log.info("diagnostics: recebido %s (%d bytes) de %s", diag_id, size, meta["machine"] or "?")
        return jsonify({"ok": True, "id": diag_id, "size": size, "data": {"id": diag_id}}), 201

    @app.route("/api/admin/diagnostics", methods=["GET"])
    @admin_required
    def admin_diagnostics_list():
        items: List[Dict[str, Any]] = []
        if store.is_dir():
            for z in sorted((p for p in store.glob("*.zip") if _ID_RE.match(p.stem)), reverse=True)[:200]:
                meta = _read_meta(z.with_suffix(".json")) or {"id": z.stem, "size": z.stat().st_size}
                items.append(meta)
        return jsonify({"ok": True, "data": {"items": items, "count": len(items)}})

    @app.route("/api/admin/diagnostics/<diag_id>/download", methods=["GET"])
    @admin_required
    def admin_diagnostics_download(diag_id: str):
        if not _ID_RE.match(diag_id or ""):
            return _fail("id inválido", 400)
        path = store / f"{diag_id}.zip"
        if not path.is_file():
            return _fail("não encontrado", 404)
        return send_file(path, mimetype="application/zip", as_attachment=True,
                         download_name=f"arkland-diagnostico-{diag_id}.zip")
