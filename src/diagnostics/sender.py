"""Envio OPT-IN do pacote de diagnóstico (Discord webhook / API da Web Store).

Nada aqui é chamado automaticamente: só pelos botões da tela «Diagnóstico», depois de
confirmação do usuário. Falhas nunca lançam exceção — voltam como ``SendResult(ok=False)``
com mensagem em português (sem expor a URL do webhook nem a API key).
"""
from __future__ import annotations

import json
import logging
import mimetypes
import re
import socket
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .collector import DISCORD_MAX_ZIP_BYTES
from .doctor import SEV_ERR, SEV_WARN, CheckResult, summarize
from .events import CAT_DIAG, CAT_WEBSTORE, diag_event
from .redact import redact_text

_LOG = logging.getLogger("arkland")

WEBSTORE_MAX_ZIP_BYTES = 25 * 1024 * 1024
DISCORD_CONTENT_LIMIT = 1900

_WEBHOOK_RE = re.compile(
    r"^https://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api/(?:v\d+/)?webhooks/\d+/[\w\-]+/?$",
    re.IGNORECASE,
)


@dataclass
class SendResult:
    ok: bool
    message: str
    partial: bool = False                 # True = só o resumo foi enviado (zip grande demais)
    remote_id: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)


def is_valid_discord_webhook(url: str) -> bool:
    return bool(_WEBHOOK_RE.match((url or "").strip()))


def build_multipart(fields: Dict[str, str],
                    files: Sequence[Tuple[str, str, bytes, str]]) -> Tuple[bytes, str]:
    """Monta ``multipart/form-data`` (stdlib). ``files``: (campo, nome, bytes, content-type)."""
    boundary = "----arkland" + uuid.uuid4().hex
    out: List[bytes] = []
    for name, value in fields.items():
        out.append(f"--{boundary}\r\n".encode())
        out.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        out.append(str(value).encode("utf-8") + b"\r\n")
    for fname, filename, data, ctype in files:
        out.append(f"--{boundary}\r\n".encode())
        out.append((f'Content-Disposition: form-data; name="{fname}"; filename="{filename}"\r\n'
                    f"Content-Type: {ctype}\r\n\r\n").encode())
        out.append(data + b"\r\n")
    out.append(f"--{boundary}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={boundary}"


def build_summary(results: Sequence[CheckResult], app_version: str = "?", mode: str = "?") -> str:
    """Texto curto (≤ ~1900 chars) para o Discord/Web Store."""
    summ = summarize(results)
    lines = [f"**Diagnóstico ARKLAND** v{app_version} ({mode}) — "
             f"{summ.get('OK', 0)} OK, {summ.get(SEV_WARN, 0)} aviso(s), {summ.get(SEV_ERR, 0)} erro(s)"]
    for sev, icon in ((SEV_ERR, "🔴"), (SEV_WARN, "🟡")):
        for r in [x for x in results if x.severity == sev][:8]:
            detail = (r.detail or "").replace("\n", " ")
            lines.append(f"{icon} {r.title}: {detail[:140]}")
    text = redact_text("\n".join(lines))
    return text[:DISCORD_CONTENT_LIMIT]


def _http_error_message(exc: BaseException, what: str) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        code = exc.code
        if code == 429:
            return f"{what}: limite de requisições atingido (HTTP 429). Aguarde um pouco e tente de novo."
        if code in (401, 403):
            return f"{what}: acesso negado (HTTP {code}). Verifique a API key/URL configurada."
        if code in (404, 405):
            return f"{what}: endpoint não encontrado (HTTP {code}). A Web Store pode estar desatualizada."
        if code == 413:
            return f"{what}: pacote grande demais para o servidor (HTTP 413)."
        return f"{what}: o servidor respondeu HTTP {code}."
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return f"{what}: tempo esgotado."
    if isinstance(exc, urllib.error.URLError):
        return f"{what}: não foi possível conectar ({type(exc.reason).__name__})."
    return f"{what}: falha inesperada ({type(exc).__name__})."


UrlOpen = Callable[..., Any]


def send_to_discord(webhook_url: str, zip_path: Path, summary: str, *,
                    max_bytes: int = DISCORD_MAX_ZIP_BYTES, timeout: float = 30.0,
                    urlopen: Optional[UrlOpen] = None) -> SendResult:
    """POST multipart do zip ao webhook. Se o zip passa de ``max_bytes`` envia só o resumo."""
    url = (webhook_url or "").strip()
    if not is_valid_discord_webhook(url):
        return SendResult(False, "URL do webhook do Discord inválida (esperado https://discord.com/api/webhooks/…).")
    opener = urlopen or urllib.request.urlopen
    zip_path = Path(zip_path)
    try:
        size = zip_path.stat().st_size
    except OSError as exc:
        return SendResult(False, f"Pacote não encontrado: {exc}")

    too_big = size > max_bytes
    content = summary
    if too_big:
        content += (f"\n⚠ Pacote ({size / 1024 / 1024:.1f} MB) excede o limite do Discord "
                    f"({max_bytes / 1024 / 1024:.1f} MB); enviado apenas o resumo. "
                    f"Arquivo mantido na máquina: {zip_path.name}")
    payload = {"content": content[:2000], "username": "ARKLAND Diagnóstico"}
    try:
        if too_big:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(url + "?wait=true", data=body, method="POST", headers={
                "Content-Type": "application/json", "User-Agent": "ARKLAND-Diagnostics/1.0"})
        else:
            body, ctype = build_multipart(
                {"payload_json": json.dumps(payload, ensure_ascii=False)},
                [("files[0]", zip_path.name, zip_path.read_bytes(), "application/zip")])
            req = urllib.request.Request(url + "?wait=true", data=body, method="POST", headers={
                "Content-Type": ctype, "User-Agent": "ARKLAND-Diagnostics/1.0"})
        with opener(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200))
        if status not in (200, 201, 204):
            return SendResult(False, f"Discord respondeu HTTP {status}.")
    except Exception as exc:  # noqa: BLE001
        msg = _http_error_message(exc, "Envio ao Discord")
        _LOG.warning("%s (%s)", msg, type(exc).__name__)
        diag_event(CAT_DIAG, "Envio ao Discord falhou", _level=logging.WARNING, error=type(exc).__name__)
        return SendResult(False, msg)
    diag_event(CAT_DIAG, "Diagnóstico enviado ao Discord", size_kb=size // 1024, partial=too_big)
    if too_big:
        return SendResult(True, "Resumo enviado ao Discord. O .zip excede ~8 MB e não foi anexado "
                                "(fica salvo localmente).", partial=True)
    return SendResult(True, "Diagnóstico enviado ao Discord.")


def resolve_webstore_target(app: Any) -> Tuple[str, str]:
    """(URL base, API key) da Web Store, reaproveitando a configuração de «Loja»."""
    shop = app.config_manager.config.shop
    api_key = (getattr(shop, "api_key", "") or "").strip()
    from ..shop_integration import resolve_plugin_api_url
    return resolve_plugin_api_url(shop).rstrip("/"), api_key


def send_to_webstore(base_url: str, api_key: str, zip_path: Path, *, app_version: str = "?",
                     mode: str = "?", note: str = "", machine: str = "",
                     doctor_summary: Optional[Dict[str, int]] = None,
                     max_bytes: int = WEBSTORE_MAX_ZIP_BYTES, timeout: float = 60.0,
                     urlopen: Optional[UrlOpen] = None) -> SendResult:
    """POST multipart em ``{base_url}/api/diagnostics`` (autenticado por API key)."""
    base = (base_url or "").strip().rstrip("/")
    key = (api_key or "").strip()
    if not base:
        return SendResult(False, "URL da Web Store não configurada (Configurações › Loja).")
    if not key:
        return SendResult(False, "API key da Web Store não configurada (Configurações › Loja).")
    zip_path = Path(zip_path)
    try:
        size = zip_path.stat().st_size
    except OSError as exc:
        return SendResult(False, f"Pacote não encontrado: {exc}")
    if size > max_bytes:
        return SendResult(False, f"Pacote ({size / 1024 / 1024:.1f} MB) acima do limite de envio "
                                 f"({max_bytes / 1024 / 1024:.0f} MB). Gere novamente ou envie manualmente.")
    opener = urlopen or urllib.request.urlopen
    try:
        body, ctype = build_multipart(
            {"app_version": app_version, "ui_mode": mode, "machine": machine, "note": note[:500],
             "doctor_summary": json.dumps(doctor_summary or {})},
            [("file", zip_path.name, zip_path.read_bytes(),
              mimetypes.guess_type(zip_path.name)[0] or "application/zip")])
        req = urllib.request.Request(f"{base}/api/diagnostics", data=body, method="POST", headers={
            "Content-Type": ctype, "X-API-Key": key, "Authorization": f"Bearer {key}",
            "User-Agent": "ARKLAND-Diagnostics/1.0"})
        with opener(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200))
            raw = resp.read() if hasattr(resp, "read") else b""
        data: Dict[str, Any] = {}
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except ValueError:
            data = {}
        if status not in (200, 201) or data.get("ok") is False:
            return SendResult(False, f"A Web Store recusou o pacote: {data.get('error') or f'HTTP {status}'}.")
        rid = str(data.get("id") or "")
        if not rid and isinstance(data.get("data"), dict):
            rid = str(data["data"].get("id") or "")
    except Exception as exc:  # noqa: BLE001
        msg = _http_error_message(exc, "Envio à Web Store")
        _LOG.warning("%s (%s)", msg, type(exc).__name__)
        diag_event(CAT_WEBSTORE, "Envio de diagnóstico à Web Store falhou", _level=logging.WARNING,
                   error=type(exc).__name__)
        return SendResult(False, msg)
    diag_event(CAT_WEBSTORE, "Diagnóstico enviado à Web Store", size_kb=size // 1024, remote_id=rid)
    return SendResult(True, f"Diagnóstico enviado à Web Store (id {rid or '?'}).", remote_id=rid)
