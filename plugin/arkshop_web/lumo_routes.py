"""Central de comunicação Lumo: rotas administrativas e publicação via webhook."""
from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from flask import jsonify, request


WEBHOOK_RE = re.compile(r"^/api/webhooks/(\d{17,22})/([A-Za-z0-9._-]{20,200})$")
MAX_TITLE = 256
MAX_DESCRIPTION = 4096
MAX_EMBED_TOTAL = 6000
FOOTER = "Lumo • Assistente oficial da ARKLAND"
AVATAR_URL = "https://arkland.com.br/lumo-avatar.png"
COLOR = 65535


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Webhooks não seguem redirecionamentos, evitando SSRF/redirecionamento de token."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def validate_webhook_url(value: str) -> str:
    """Aceita somente URL HTTPS de webhook no host oficial discord.com."""
    raw = str(value or "").strip()
    if not raw or len(raw) > 512:
        raise ValueError("Informe a URL completa do webhook do Discord.")
    try:
        parsed = urllib.parse.urlsplit(raw)
        match = WEBHOOK_RE.fullmatch(parsed.path)
        valid_port = parsed.port in (None, 443)
    except ValueError as exc:
        raise ValueError("A URL do webhook é inválida.") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname != "discord.com"
        or parsed.username
        or parsed.password
        or not valid_port
        or parsed.query
        or parsed.fragment
        or not match
    ):
        raise ValueError("Use uma URL HTTPS válida de webhook em discord.com.")
    return urllib.parse.urlunsplit(("https", "discord.com", parsed.path, "", ""))


def validate_https_media_url(value: Any, field: str) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    if len(raw) > 2048:
        raise ValueError(f"A URL de {field} excede 2.048 caracteres.")
    try:
        parsed = urllib.parse.urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"A URL de {field} é inválida.") from exc
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or port not in (None, 443):
        raise ValueError(f"A URL de {field} deve usar HTTPS e não pode conter credenciais.")
    return raw


def validate_embed(title: str, description: str, title_url: str = "", image_url: str = "", thumbnail_url: str = "") -> dict[str, Any]:
    title = str(title or "").strip()
    description = str(description or "")
    if not description.strip():
        raise ValueError("Escreva o conteúdo principal antes de publicar.")
    if len(title) > MAX_TITLE:
        raise ValueError(f"O título excede o limite de {MAX_TITLE} caracteres.")
    if len(description) > MAX_DESCRIPTION:
        raise ValueError(f"A descrição excede o limite de 4.096 caracteres.")
    if len(title) + len(description) + len(FOOTER) > MAX_EMBED_TOTAL:
        raise ValueError(f"A mensagem excede o limite total de {MAX_EMBED_TOTAL} caracteres do embed.")
    embed: dict[str, Any] = {
        "description": description,
        "color": COLOR,
        "footer": {"text": FOOTER},
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }
    if title:
        embed["title"] = title
    if title_url:
        embed["url"] = validate_https_media_url(title_url, "título")
        if not title:
            raise ValueError("Preencha o título para associar um link a ele.")
    image = validate_https_media_url(image_url, "imagem")
    thumbnail = validate_https_media_url(thumbnail_url, "miniatura")
    if image:
        embed["image"] = {"url": image}
    if thumbnail:
        embed["thumbnail"] = {"url": thumbnail}
    return embed


def _masked_webhook(url: str) -> str:
    try:
        path = urllib.parse.urlsplit(url).path
        parts = path.split("/")
        if len(parts) >= 5:
            token = parts[4]
            return f"discord.com/api/webhooks/{parts[3]}/••••••{token[-4:]}"
    except Exception:
        pass
    return "Webhook configurado"


def _safe_json_response(response: Any) -> dict[str, Any]:
    try:
        data = json.loads(response.read().decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _discord_request(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any], dict[str, str]]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Accept": "application/json", "User-Agent": "ARKLAND-Lumo/1.0", **({"Content-Type": "application/json"} if body is not None else {})},
    )
    opener = urllib.request.build_opener(NoRedirect, urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    try:
        response = opener.open(req, timeout=12)
    except urllib.error.HTTPError as exc:
        return int(exc.code), _safe_json_response(exc), {str(k).lower(): str(v) for k, v in exc.headers.items()}
    with response:
        return int(response.status), _safe_json_response(response), {str(k).lower(): str(v) for k, v in response.headers.items()}


def _integration_view(settings: dict[str, Any]) -> dict[str, Any]:
    url = str(settings.get("lumo_webhook_url") or "")
    return {
        "configured": bool(url),
        "masked_url": _masked_webhook(url) if url else "",
        "status": str(settings.get("lumo_webhook_status") or ("unverified" if url else "not_configured")),
        "last_checked_at": str(settings.get("lumo_webhook_checked_at") or ""),
        "last_published_at": str(settings.get("lumo_last_published_at") or ""),
        "channel_id": str(settings.get("lumo_webhook_channel_id") or ""),
        "guild_id": str(settings.get("lumo_webhook_guild_id") or ""),
        "last_error": str(settings.get("lumo_webhook_error") or ""),
    }


def _same_origin_request() -> bool:
    """Defesa CSRF adicional às cookies SameSite e ao payload JSON."""
    site = (request.headers.get("Sec-Fetch-Site") or "").lower()
    if site and site not in {"same-origin", "same-site", "none"}:
        return False
    origin = (request.headers.get("Origin") or "").strip()
    if not origin:
        return True
    try:
        parsed = urllib.parse.urlsplit(origin)
        request_host = (request.host or "").lower().split(":", 1)[0]
        return parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() == request_host
    except Exception:
        return False


def register_lumo_routes(
    app: Any,
    *,
    admin_required: Callable[..., Any],
    limiter: Any,
    load_settings: Callable[[], dict[str, Any]],
    save_settings: Callable[[dict[str, Any]], None],
    get_fernet: Callable[[], Any],
    encrypt_value: Callable[[str], str],
    audit_event: Callable[..., None],
    session_factory: Callable[[], Any],
    audit_model: Any,
    idempotency_store: Any,
    now: Callable[[], datetime],
    get_admin_id: Callable[[], Any],
    index_view: Callable[[], Any],
    db_ready: Callable[[], bool],
) -> None:
    @app.get("/admin/lumo")
    @admin_required
    def lumo_admin_page():
        return index_view()

    @app.get("/api/admin/lumo/config")
    @admin_required
    @limiter.limit("60 per minute")
    def lumo_get_config():
        return jsonify({"ok": True, "integration": _integration_view(load_settings())})

    @app.post("/api/admin/lumo/config")
    @admin_required
    @limiter.limit("10 per hour", override_defaults=True)
    def lumo_save_config():
        if not _same_origin_request():
            return jsonify({"ok": False, "error": "Origem da solicitação inválida."}), 403
        body = request.get_json(silent=True) or {}
        url = str(body.get("webhook_url") or "").strip()
        try:
            normalized = validate_webhook_url(url) if url else ""
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        if normalized and get_fernet() is None:
            return jsonify({"ok": False, "error": "A chave segura do site não está disponível; o webhook não foi salvo."}), 503
        if normalized and not str(encrypt_value(normalized)).startswith("ENC:"):
            return jsonify({"ok": False, "error": "Não consegui criptografar a credencial; o webhook não foi salvo."}), 503
        settings = load_settings()
        settings["lumo_webhook_url"] = normalized
        settings["lumo_webhook_status"] = "unverified" if normalized else "not_configured"
        settings["lumo_webhook_checked_at"] = ""
        settings["lumo_webhook_channel_id"] = ""
        settings["lumo_webhook_guild_id"] = ""
        settings["lumo_webhook_error"] = ""
        save_settings(settings)
        admin_id = str(get_admin_id() or "")
        audit_event("lumo_webhook_configured" if normalized else "lumo_webhook_removed", source="admin", actor_type="admin", actor_steam_id=admin_id, message="Configuração do webhook Lumo alterada", persist=True)
        return jsonify({"ok": True, "integration": _integration_view(load_settings())})

    @app.post("/api/admin/lumo/verify")
    @admin_required
    @limiter.limit("5 per minute", override_defaults=True)
    def lumo_verify_webhook():
        if not _same_origin_request():
            return jsonify({"ok": False, "error": "Origem da solicitação inválida."}), 403
        settings = load_settings()
        raw_url = str(settings.get("lumo_webhook_url") or "")
        if not raw_url:
            return jsonify({"ok": False, "error": "Configure o webhook antes de verificar."}), 400
        checked = now().astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
        status = "failed"
        safe_error = "Não foi possível verificar o webhook. Confira a URL e tente novamente."
        channel_id = guild_id = ""
        try:
            url = validate_webhook_url(raw_url)
            code, data, headers = _discord_request(url)
            if code == 200 and data.get("id") and data.get("channel_id"):
                status = "verified"
                channel_id = str(data.get("channel_id") or "")
                guild_id = str(data.get("guild_id") or "")
                safe_error = ""
            elif code == 429:
                retry = data.get("retry_after") or headers.get("retry-after") or "alguns segundos"
                safe_error = f"O Discord limitou a verificação. Aguarde {retry} segundos e tente novamente."
            elif code in (401, 403, 404):
                safe_error = "O Discord não reconheceu este webhook ou ele não está mais disponível."
        except Exception:
            # Não registrar nem devolver exceções de transporte: algumas contêm a URL secreta.
            pass
        settings.update({
            "lumo_webhook_status": status,
            "lumo_webhook_checked_at": checked,
            "lumo_webhook_channel_id": channel_id,
            "lumo_webhook_guild_id": guild_id,
            "lumo_webhook_error": safe_error,
        })
        save_settings(settings)
        audit_event("lumo_webhook_verified" if status == "verified" else "lumo_webhook_verification_failed", source="admin", actor_type="admin", actor_steam_id=str(get_admin_id() or ""), severity="info" if status == "verified" else "warning", message="Verificação de metadados do webhook Lumo", status_after=status)
        return jsonify({"ok": status == "verified", "integration": _integration_view(settings), "message": "Webhook verificado. Nenhuma mensagem foi publicada." if status == "verified" else safe_error}), 200 if status == "verified" else 502

    @app.post("/api/admin/lumo/publish")
    @admin_required
    @limiter.limit("5 per minute", override_defaults=True)
    def lumo_publish():
        if not _same_origin_request():
            return jsonify({"ok": False, "error": "Origem da solicitação inválida."}), 403
        body = request.get_json(silent=True) or {}
        try:
            embed = validate_embed(body.get("title"), body.get("content"), body.get("title_url"), body.get("image_url"), body.get("thumbnail_url"))
            url = validate_webhook_url(str(load_settings().get("lumo_webhook_url") or ""))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception:
            return jsonify({"ok": False, "error": "Configure e verifique o webhook antes de publicar."}), 400
        settings = load_settings()
        if settings.get("lumo_webhook_status") != "verified":
            return jsonify({"ok": False, "error": "Verifique a integração com Discord antes de publicar."}), 409
        key = str(body.get("request_id") or "").strip()
        if not re.fullmatch(r"[A-Fa-f0-9-]{32,36}", key):
            return jsonify({"ok": False, "error": "Identificador de envio inválido. Atualize o editor e tente novamente."}), 400
        admin_id = str(get_admin_id() or "")
        idem_key = f"lumo-publish:{admin_id}:{key}"
        try:
            claimed = idempotency_store.claim(idem_key)
        except Exception:
            return jsonify({"ok": False, "error": "Não consegui reservar este envio com segurança. Tente novamente."}), 503
        if not claimed:
            return jsonify({"ok": False, "error": "Este envio já foi processado ou está em andamento. Confira o histórico antes de tentar novamente."}), 409
        payload = {
            "username": "Lumo",
            "avatar_url": AVATAR_URL,
            "embeds": [embed],
            "allowed_mentions": {"parse": []},
        }
        endpoint = url + "?wait=true"
        try:
            code, data, headers = _discord_request(endpoint, method="POST", payload=payload)
            if code in (200, 201) and data.get("id"):
                published_at = now().astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
                settings["lumo_last_published_at"] = published_at
                settings["lumo_webhook_channel_id"] = str(data.get("channel_id") or settings.get("lumo_webhook_channel_id") or "")
                settings["lumo_webhook_guild_id"] = str(data.get("guild_id") or settings.get("lumo_webhook_guild_id") or "")
                save_settings(settings)
                audit_event("lumo_publish", source="admin", actor_type="admin", actor_steam_id=admin_id, severity="info", message="Publicação Lumo concluída", status_after="success", title=embed.get("title", ""), description=embed["description"], embed=embed, discord_message_id=str(data.get("id") or ""), channel_id=str(data.get("channel_id") or ""), guild_id=str(data.get("guild_id") or ""), published_at=published_at)
                return jsonify({"ok": True, "message": "Sua mensagem foi publicada no Discord da ARKLAND.", "discord_message_id": str(data.get("id") or ""), "channel_id": str(data.get("channel_id") or ""), "guild_id": str(data.get("guild_id") or ""), "published_at": published_at})
            if code == 429:
                retry = data.get("retry_after") or headers.get("retry-after") or "alguns segundos"
                message, status_after = f"O Discord limitou o envio. Aguarde {retry} segundos antes de tentar novamente.", "rate_limited"
            elif code in (400, 401, 403, 404):
                message, status_after = "O Discord recusou a publicação. Verifique o webhook e os campos da mensagem.", "rejected"
            else:
                message, status_after = "O Discord não confirmou a publicação. Confira o histórico antes de tentar novamente.", "uncertain"
            if status_after in {"rate_limited", "rejected"}:
                idempotency_store.release(idem_key)
            if code in (401, 403, 404):
                settings["lumo_webhook_status"] = "failed"
                settings["lumo_webhook_error"] = "O Discord não reconheceu este webhook ou ele não está mais disponível."
                save_settings(settings)
            audit_event("lumo_publish", source="admin", actor_type="admin", actor_steam_id=admin_id, severity="warning", message=message, status_after=status_after, title=embed.get("title", ""), description=embed["description"], embed=embed, http_status=code)
            return jsonify({"ok": False, "error": message, "result": status_after}), 502 if status_after != "rate_limited" else 429
        except (TimeoutError, urllib.error.URLError, OSError):
            message = "A conexão com o Discord expirou ou foi interrompida. O resultado é incerto; confira o histórico antes de tentar novamente."
            audit_event("lumo_publish", source="admin", actor_type="admin", actor_steam_id=admin_id, severity="warning", message=message, status_after="uncertain", title=embed.get("title", ""), description=embed["description"], embed=embed)
            return jsonify({"ok": False, "error": message, "result": "uncertain"}), 504
        except Exception:
            message = "O resultado da publicação não pôde ser determinado. Confira o histórico antes de tentar novamente."
            audit_event("lumo_publish", source="admin", actor_type="admin", actor_steam_id=admin_id, severity="warning", message=message, status_after="uncertain", title=embed.get("title", ""), description=embed["description"], embed=embed)
            return jsonify({"ok": False, "error": message, "result": "uncertain"}), 502

    @app.get("/api/admin/lumo/history")
    @admin_required
    @limiter.limit("60 per minute")
    def lumo_history():
        if not db_ready():
            return jsonify({"ok": False, "error": "O histórico está indisponível enquanto a base de dados inicializa."}), 503
        try:
            limit = max(1, min(50, int(request.args.get("limit", 20))))
            offset = max(0, min(100000, int(request.args.get("offset", 0))))
        except ValueError:
            return jsonify({"ok": False, "error": "Paginação inválida."}), 400
        status_filter = str(request.args.get("status") or "").strip().lower()
        query_text = str(request.args.get("q") or "").strip()[:120].lower()
        admin_filter = str(request.args.get("admin") or "").strip()[:32]
        db = session_factory()
        try:
            query = db.query(audit_model).filter(audit_model.event_type == "lumo_publish")
            if status_filter:
                query = query.filter(audit_model.status_after == status_filter)
            if admin_filter:
                query = query.filter(audit_model.actor_steam_id == admin_filter)
            date_from = str(request.args.get("from") or "").strip()
            date_to = str(request.args.get("to") or "").strip()
            try:
                if date_from:
                    query = query.filter(audit_model.created_at >= datetime.fromisoformat(date_from).replace(tzinfo=UTC))
                if date_to:
                    end_date = datetime.fromisoformat(date_to).replace(tzinfo=UTC).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                    query = query.filter(audit_model.created_at < end_date)
            except ValueError:
                return jsonify({"ok": False, "error": "Período inválido."}), 400
            if query_text:
                query = query.filter(audit_model.message.ilike(f"%{query_text}%") | audit_model.payload_json.ilike(f"%{query_text}%"))
            rows = query.order_by(audit_model.created_at.desc(), audit_model.id.desc()).offset(offset).limit(limit + 1).all()
            has_more = len(rows) > limit
            items = []
            for row in rows[:limit]:
                try:
                    payload = json.loads(row.payload_json or "{}")
                except Exception:
                    payload = {}
                items.append({"id": row.id, "message_id": payload.get("discord_message_id", ""), "channel_id": payload.get("channel_id", ""), "guild_id": payload.get("guild_id", ""), "title": payload.get("title", ""), "content": payload.get("description", ""), "embed": payload.get("embed", {}), "created_at": row.created_at.isoformat() if row.created_at else "", "admin_steam_id": row.actor_steam_id or "", "status": row.status_after or "unknown", "error": row.message or ""})
            return jsonify({"ok": True, "items": items, "has_more": has_more, "limit": limit, "offset": offset})
        finally:
            db.close()

