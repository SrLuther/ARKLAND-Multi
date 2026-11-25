"""Central de comunicação Lumo: rotas administrativas e publicação via webhook."""
from __future__ import annotations

import json
import re
import ssl
import asyncio
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from flask import jsonify, request, send_file
from lumo_assets import MAX_IMAGE_BYTES, cleanup_assets, resolve_asset, validate_and_store
from lumo_assistant import GREETING_REPLIES
from lumo_gateway import configure_lumo_runtime


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


def _discord_request(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None,
                     files: list[tuple[str, str, str, bytes]] | None = None) -> tuple[int, dict[str, Any], dict[str, str]]:
    headers = {"Accept": "application/json", "User-Agent": "ARKLAND-Lumo/1.0"}
    if files:
        boundary = "----ARKLANDLumo" + uuid.uuid4().hex
        chunks = [f"--{boundary}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\nContent-Type: application/json\r\n\r\n".encode(),
                  json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), b"\r\n"]
        for index, (field_name, filename, mime, content) in enumerate(files):
            safe_filename = Path(filename).name.replace('"', "")
            chunks.extend([f"--{boundary}\r\nContent-Disposition: form-data; name=\"files[{index}]\"; filename=\"{safe_filename}\"\r\nContent-Type: {mime}\r\n\r\n".encode(), content, b"\r\n"])
        chunks.append(f"--{boundary}--\r\n".encode())
        body = b"".join(chunks)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    else:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8") if payload is not None else None
        if body is not None:
            headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers=headers,
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


def _assistant_view(settings: dict[str, Any], runtime: Any) -> dict[str, Any]:
    """Configuração operacional sem retornar o token do bot ou o webhook."""
    return {
        "enabled": bool(settings.get("lumo_assistant_enabled", False)),
        "token_configured": bool(settings.get("lumo_bot_token")),
        "guild_id": str(settings.get("lumo_guild_id") or ""),
        "interaction_channel_id": str(settings.get("lumo_interaction_channel_id") or ""),
        "game_chat_enabled": bool(settings.get("lumo_game_chat_enabled", False)),
        "game_chat_channel_id": str(settings.get("lumo_game_chat_channel_id") or ""),
        "game_chat_webhooks_enabled": bool(settings.get("lumo_game_chat_webhooks_enabled", False)),
        "game_chat_keywords_enabled": bool(settings.get("lumo_game_chat_keywords_enabled", False)),
        "game_chat_announcements_enabled": bool(settings.get("lumo_game_chat_announcements_enabled", False)),
        "game_general_announcements_enabled": bool(settings.get("lumo_game_general_announcements_enabled", False)),
        "game_auto_betland_enabled": bool(settings.get("lumo_game_auto_betland_enabled", False)),
        "game_auto_polls_enabled": bool(settings.get("lumo_game_auto_polls_enabled", False)),
        "game_general_next_at": str(settings.get("lumo_game_general_next_at") or ""),
        "game_auto_betland_next_at": str(settings.get("lumo_game_auto_betland_next_at") or ""),
        "game_auto_polls_next_at": str(settings.get("lumo_game_auto_polls_next_at") or ""),
        "game_chat_max_chars": int(settings.get("lumo_game_chat_max_chars", 250) or 250),
        "game_chat_trigger_aliases": dict(settings.get("lumo_game_chat_trigger_aliases") or {}),
        "game_chat_topic_enabled": dict(settings.get("lumo_game_chat_topic_enabled") or {}),
        "game_chat_greeting_cooldown_seconds": int(settings.get("lumo_game_chat_greeting_cooldown_seconds", 600) or 0),
        "game_chat_topic_cooldown_seconds": int(settings.get("lumo_game_chat_topic_cooldown_seconds", 120) or 0),
        "game_chat_user_topic_cooldown_seconds": int(settings.get("lumo_game_chat_user_topic_cooldown_seconds", 300) or 0),
        "game_chat_global_cooldown_seconds": int(settings.get("lumo_game_chat_global_cooldown_seconds", 5) or 0),
        "bot_user_id": str(settings.get("lumo_bot_user_id") or ""),
        "status_channel_id": str(settings.get("lumo_status_channel_id") or ""),
        "trigger_enabled": dict(settings.get("lumo_trigger_enabled") or {"STATUS": True, "BETLAND": True, "LICENCAS": True, "VOTACAO": True}),
        "trigger_aliases": dict(settings.get("lumo_trigger_aliases") or {}),
        "auto_betland_enabled": bool(settings.get("lumo_auto_betland_enabled", False)),
        "auto_polls_enabled": bool(settings.get("lumo_auto_polls_enabled", False)),
        "user_cooldown_seconds": int(settings.get("lumo_user_cooldown_seconds", 15) or 0),
        "trigger_cooldown_seconds": int(settings.get("lumo_trigger_cooldown_seconds", 20) or 0),
        "global_cooldown_seconds": int(settings.get("lumo_global_cooldown_seconds", 3) or 0),
        "global_hourly_limit": int(settings.get("lumo_global_hourly_limit", 40) or 0),
        "auto_betland_last_at": str(settings.get("lumo_auto_betland_last_at") or ""),
        "auto_betland_next_at": str(settings.get("lumo_auto_betland_next_at") or ""),
        "auto_betland_last_result": str(settings.get("lumo_auto_betland_last_result") or ""),
        "auto_polls_last_at": str(settings.get("lumo_auto_polls_last_at") or ""),
        "auto_polls_next_at": str(settings.get("lumo_auto_polls_next_at") or ""),
        "auto_polls_last_result": str(settings.get("lumo_auto_polls_last_result") or ""),
        "runtime": runtime.snapshot(),
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
    source_provider: Callable[[str], dict[str, Any]] | None = None,
    uploads_dir: Path | str | None = None,
) -> None:
    runtime = configure_lumo_runtime(load_settings, save_settings, source_provider or (lambda _source: {"ok": False}), audit_event)
    asset_dir = Path(uploads_dir or (Path(app.instance_path) / "lumo_uploads")).resolve()

    def expire_assets(settings: dict[str, Any]) -> dict[str, Any]:
        now_utc = datetime.now(UTC)
        last = str(settings.get("lumo_asset_cleanup_at") or "")
        try:
            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        except ValueError:
            last_dt = None
        if last_dt and (now_utc - last_dt).total_seconds() < 86400:
            return settings
        records = settings.get("lumo_media_assets")
        records = records if isinstance(records, list) else []
        updated, removed = cleanup_assets(asset_dir, records, retention_days=int(settings.get("lumo_asset_retention_days", 30) or 30), now=now_utc)
        settings["lumo_media_assets"] = updated
        settings["lumo_asset_cleanup_at"] = now_utc.isoformat(timespec="seconds")
        if removed:
            audit_event("lumo_asset_cleanup", source="lumo_assets", actor_type="system", severity="info", message="Limpeza diária de imagens Lumo", status_after="success", count=len(removed), asset_ids=removed)
        save_settings(settings)
        return settings
    @app.get("/admin/lumo")
    @admin_required
    def lumo_admin_page():
        return index_view()

    @app.get("/api/admin/lumo/config")
    @admin_required
    @limiter.limit("60 per minute")
    def lumo_get_config():
        settings = load_settings()
        return jsonify({"ok": True, "integration": _integration_view(settings), "assistant": _assistant_view(settings, runtime)})

    @app.get("/api/admin/lumo/assistant/config")
    @admin_required
    @limiter.limit("60 per minute")
    def lumo_get_assistant_config():
        settings = expire_assets(load_settings())
        return jsonify({"ok": True, "assistant": _assistant_view(settings, runtime), "greeting_replies": list(settings.get("lumo_greeting_replies") or GREETING_REPLIES)})

    @app.post("/api/admin/lumo/assistant/config")
    @admin_required
    @limiter.limit("20 per hour", override_defaults=True)
    def lumo_save_assistant_config():
        if not _same_origin_request():
            return jsonify({"ok": False, "error": "Origem da solicitação inválida."}), 403
        body = request.get_json(silent=True) or {}
        settings = load_settings()
        guild_id = str(body.get("guild_id", settings.get("lumo_guild_id", "")) or "").strip()
        channel_id = str(body.get("interaction_channel_id", settings.get("lumo_interaction_channel_id", "")) or "").strip()
        status_id = str(body.get("status_channel_id", settings.get("lumo_status_channel_id", "")) or "").strip()
        game_channel_id = str(body.get("game_chat_channel_id", settings.get("lumo_game_chat_channel_id", "")) or "").strip()
        bot_user_id = str(body.get("bot_user_id", settings.get("lumo_bot_user_id", "")) or "").strip()
        if guild_id and not re.fullmatch(r"\d{17,22}", guild_id):
            return jsonify({"ok": False, "error": "O ID do servidor Discord deve conter entre 17 e 22 dígitos."}), 400
        if channel_id and not re.fullmatch(r"\d{17,22}", channel_id):
            return jsonify({"ok": False, "error": "O ID do canal autorizado deve conter entre 17 e 22 dígitos."}), 400
        if status_id and not re.fullmatch(r"\d{17,22}", status_id):
            return jsonify({"ok": False, "error": "O ID do canal de status deve conter entre 17 e 22 dígitos."}), 400
        if game_channel_id and not re.fullmatch(r"\d{17,22}", game_channel_id):
            return jsonify({"ok": False, "error": "O ID do canal de chat do jogo deve conter entre 17 e 22 dígitos."}), 400
        if bot_user_id and not re.fullmatch(r"\d{17,22}", bot_user_id):
            return jsonify({"ok": False, "error": "O ID do usuário Lumo deve conter entre 17 e 22 dígitos."}), 400
        enabled_raw = body.get("enabled", settings.get("lumo_assistant_enabled", False))
        if not isinstance(enabled_raw, bool):
            return jsonify({"ok": False, "error": "A ativação precisa ser true/false."}), 400
        enabled = enabled_raw
        game_enabled = body.get("game_chat_enabled", settings.get("lumo_game_chat_enabled", False))
        if not isinstance(game_enabled, bool):
            return jsonify({"ok": False, "error": "A ativação do Chat do Jogo precisa ser true/false."}), 400
        if game_enabled and not game_channel_id:
            return jsonify({"ok": False, "error": "Informe o ID do canal integrado ao chat do jogo antes de ativá-lo."}), 400
        if game_enabled and enabled and game_channel_id == channel_id:
            return jsonify({"ok": False, "error": "Use canais diferentes para o Chat Global e o Chat do Jogo."}), 400
        token = str(body.get("bot_token") or "").strip()
        if token and (len(token) > 256 or any(ch.isspace() for ch in token)):
            return jsonify({"ok": False, "error": "O token do bot tem formato inválido."}), 400
        if token:
            if get_fernet() is None:
                return jsonify({"ok": False, "error": "A chave segura do site não está disponível; o token não foi salvo."}), 503
            encrypted = str(encrypt_value(token))
            if not encrypted.startswith("ENC:"):
                return jsonify({"ok": False, "error": "Não foi possível criptografar o token; ele não foi salvo."}), 503
            settings["lumo_bot_token"] = token
        elif body.get("clear_bot_token"):
            settings["lumo_bot_token"] = ""
        if (enabled or game_enabled) and not (settings.get("lumo_bot_token") and guild_id):
            return jsonify({"ok": False, "error": "Para ativar o Gateway, informe o token do bot e o ID do servidor."}), 400
        if enabled and not channel_id:
            return jsonify({"ok": False, "error": "Informe o canal global autorizado para ativar as respostas do Lumo no Discord."}), 400

        bool_keys = ("auto_betland_enabled", "auto_polls_enabled")
        settings.update({
            "lumo_assistant_enabled": enabled,
            "lumo_guild_id": guild_id,
            "lumo_interaction_channel_id": channel_id,
            "lumo_status_channel_id": status_id,
            "lumo_game_chat_channel_id": game_channel_id,
            "lumo_game_chat_enabled": game_enabled,
            "lumo_bot_user_id": bot_user_id,
        })
        for key in ("game_chat_webhooks_enabled", "game_chat_keywords_enabled", "game_chat_announcements_enabled", "game_general_announcements_enabled", "game_auto_betland_enabled", "game_auto_polls_enabled"):
            if key in body:
                if not isinstance(body[key], bool):
                    return jsonify({"ok": False, "error": f"{key} precisa ser true/false."}), 400
                settings[f"lumo_{key}"] = body[key]
        for key, default, maximum in (
            ("game_chat_greeting_cooldown_seconds", 600, 86400),
            ("game_chat_topic_cooldown_seconds", 120, 3600),
            ("game_chat_user_topic_cooldown_seconds", 300, 3600),
            ("game_chat_global_cooldown_seconds", 5, 120),
        ):
            if key in body:
                try:
                    settings[f"lumo_{key}"] = max(default if key.endswith("greeting_cooldown_seconds") else 0, min(maximum, int(body[key])))
                except (TypeError, ValueError):
                    return jsonify({"ok": False, "error": f"Valor inválido para {key}."}), 400
        if "game_chat_max_chars" in body:
            try:
                settings["lumo_game_chat_max_chars"] = max(80, min(250, int(body["game_chat_max_chars"])))
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": "Limite de tamanho inválido."}), 400
        if "game_chat_trigger_aliases" in body:
            aliases = body["game_chat_trigger_aliases"]
            allowed = {"BETLAND", "VOTACAO", "SEASON", "SUPPORT", "SITE", "LINK", "STARTER", "CATALOG", "STATUS", "LIMIT", "LUMO"}
            if not isinstance(aliases, dict) or set(aliases) - allowed:
                return jsonify({"ok": False, "error": "Aliases do Chat do Jogo inválidos."}), 400
            clean_aliases = {}
            for topic, values in aliases.items():
                if not isinstance(values, list) or len(values) > 30:
                    return jsonify({"ok": False, "error": f"Informe até 30 aliases para {topic}."}), 400
                clean = [str(value).strip()[:60] for value in values if str(value).strip()]
                if any(len(value) < 2 for value in clean):
                    return jsonify({"ok": False, "error": "Cada alias precisa ter ao menos 2 caracteres."}), 400
                clean_aliases[topic] = clean
            settings["lumo_game_chat_trigger_aliases"] = clean_aliases
        if "game_chat_topic_enabled" in body:
            topic_enabled = body["game_chat_topic_enabled"]
            allowed_topics = {"BETLAND", "VOTACAO", "SEASON", "SUPPORT", "SITE", "LINK", "STARTER", "CATALOG", "STATUS", "LIMIT", "LUMO"}
            if not isinstance(topic_enabled, dict) or set(topic_enabled) - allowed_topics or any(not isinstance(value, bool) for value in topic_enabled.values()):
                return jsonify({"ok": False, "error": "Ativações de assuntos inválidas."}), 400
            settings["lumo_game_chat_topic_enabled"] = {key: topic_enabled.get(key, True) for key in allowed_topics}
        for key in bool_keys:
            if key in body:
                if not isinstance(body[key], bool):
                    return jsonify({"ok": False, "error": f"{key} precisa ser true/false."}), 400
                settings[f"lumo_{key}"] = body[key]
        for key, default, maximum in (
            ("user_cooldown_seconds", 15, 3600),
            ("trigger_cooldown_seconds", 20, 3600),
            ("global_cooldown_seconds", 3, 120),
            ("global_hourly_limit", 40, 500),
        ):
            if key in body:
                try:
                    settings[f"lumo_{key}"] = max(0, min(maximum, int(body[key])))
                except (TypeError, ValueError):
                    return jsonify({"ok": False, "error": f"Valor inválido para {key}."}), 400

        if "trigger_enabled" in body:
            trigger_enabled = body.get("trigger_enabled")
            if not isinstance(trigger_enabled, dict) or any(k not in {"STATUS", "BETLAND", "LICENCAS", "VOTACAO"} for k in trigger_enabled) or any(not isinstance(v, bool) for v in trigger_enabled.values()):
                return jsonify({"ok": False, "error": "Configuração de gatilhos inválida."}), 400
            settings["lumo_trigger_enabled"] = {k: trigger_enabled.get(k, True) for k in ("STATUS", "BETLAND", "LICENCAS", "VOTACAO")}
        if "trigger_aliases" in body:
            aliases = body.get("trigger_aliases")
            if not isinstance(aliases, dict) or any(k not in {"STATUS", "BETLAND", "LICENCAS", "VOTACAO"} for k in aliases):
                return jsonify({"ok": False, "error": "Aliases de gatilho inválidos."}), 400
            normalized_aliases: dict[str, list[str]] = {}
            for key, values in aliases.items():
                if not isinstance(values, list) or len(values) > 40:
                    return jsonify({"ok": False, "error": f"Informe até 40 aliases para {key}."}), 400
                clean = [str(value).strip()[:60] for value in values if str(value).strip()]
                if any(len(value) < 2 for value in clean):
                    return jsonify({"ok": False, "error": "Cada alias precisa ter pelo menos 2 caracteres."}), 400
                normalized_aliases[key] = clean
            settings["lumo_trigger_aliases"] = normalized_aliases
        save_settings(settings)
        ok, message = runtime.reconfigure()
        audit_event("lumo_assistant_configured", source="admin", actor_type="admin", actor_steam_id=str(get_admin_id() or ""), severity="info", message="Configuração operacional do Lumo atualizada", status_after="enabled" if enabled else "disabled")
        updated = load_settings()
        return jsonify({"ok": ok, "message": message, "assistant": _assistant_view(updated, runtime)}), 200 if ok else 409

    @app.post("/api/admin/lumo/assistant/preview")
    @admin_required
    @limiter.limit("60 per minute", override_defaults=True)
    def lumo_assistant_preview():
        if not _same_origin_request():
            return jsonify({"ok": False, "error": "Origem da solicitação inválida."}), 403
        body = request.get_json(silent=True) or {}
        text = str(body.get("text") or "").strip()
        if not text or len(text) > 1000:
            return jsonify({"ok": False, "error": "Escreva uma mensagem de teste com até 1.000 caracteres."}), 400
        try:
            result = asyncio.run(runtime.preview(text))
            return jsonify({"ok": True, **result})
        except Exception:
            return jsonify({"ok": False, "error": "O modo de teste não conseguiu consultar as fontes agora."}), 503

    @app.post("/api/admin/lumo/assistant/game-preview")
    @admin_required
    @limiter.limit("60 per minute", override_defaults=True)
    def lumo_game_preview():
        if not _same_origin_request():
            return jsonify({"ok": False, "error": "Origem da solicitação inválida."}), 403
        body = request.get_json(silent=True) or {}
        text = str(body.get("text") or "").strip()
        if not text or len(text) > 1000:
            return jsonify({"ok": False, "error": "Informe uma mensagem de até 1.000 caracteres."}), 400
        try:
            return jsonify({"ok": True, **asyncio.run(runtime.preview_game_chat(text))})
        except Exception:
            return jsonify({"ok": False, "error": "A simulação do Chat do Jogo falhou ao consultar as fontes."}), 503

    @app.post("/api/admin/lumo/game-chat/send")
    @admin_required
    @limiter.limit("5 per minute", override_defaults=True)
    def lumo_game_manual_send():
        if not _same_origin_request():
            return jsonify({"ok": False, "error": "Origem da solicitação inválida."}), 403
        body = request.get_json(silent=True) or {}
        text = " ".join(str(body.get("text") or "").split())
        if not text or len(text) > 250:
            return jsonify({"ok": False, "error": "A mensagem deve conter de 1 a 250 caracteres."}), 400
        try:
            message_id = runtime.send_game_message(text)
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc) or "O envio pelo Chat do Jogo falhou."}), 503
        audit_event("lumo_game_manual_message", source="admin", actor_type="admin", actor_steam_id=str(get_admin_id() or ""), severity="info", message="Mensagem administrativa enviada pelo Chat do Jogo", status_after="success", channel_id=str(load_settings().get("lumo_game_chat_channel_id") or ""), discord_message_id=message_id)
        return jsonify({"ok": True, "message": "Mensagem enviada uma vez ao canal compartilhado do Chat do Jogo."})

    @app.put("/api/admin/lumo/assistant/greetings")
    @admin_required
    @limiter.limit("30 per hour", override_defaults=True)
    def lumo_save_greetings():
        if not _same_origin_request():
            return jsonify({"ok": False, "error": "Origem da solicitação inválida."}), 403
        body = request.get_json(silent=True) or {}
        replies = body.get("replies")
        if not isinstance(replies, list) or not 1 <= len(replies) <= 100:
            return jsonify({"ok": False, "error": "Mantenha entre 1 e 100 respostas de saudação."}), 400
        clean = [str(item).strip() for item in replies if str(item).strip()]
        if len(clean) != len(replies) or any(len(item) > 1000 for item in clean):
            return jsonify({"ok": False, "error": "Cada resposta deve ser texto não vazio com até 1.000 caracteres."}), 400
        if any(re.search(r"\{(?!jogador\}|nome\})[^{}]{1,30}\}", item, flags=re.I) for item in clean):
            return jsonify({"ok": False, "error": "Variáveis disponíveis: {jogador} e {nome}."}), 400
        settings = load_settings()
        settings["lumo_greeting_replies"] = clean
        save_settings(settings)
        return jsonify({"ok": True, "replies": clean})

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
        settings = load_settings()
        records = settings.get("lumo_media_assets") if isinstance(settings.get("lumo_media_assets"), list) else []
        records_by_id = {str(row.get("id")): row for row in records if isinstance(row, dict)}
        selected_assets: list[dict[str, Any]] = []
        try:
            embed = validate_embed(body.get("title"), body.get("content"), body.get("title_url"), body.get("image_url"), body.get("thumbnail_url"))
            for body_key, embed_key in (("image_asset_id", "image"), ("thumbnail_asset_id", "thumbnail")):
                asset_id = str(body.get(body_key) or "").strip()
                if not asset_id:
                    continue
                if body.get("image_url" if embed_key == "image" else "thumbnail_url"):
                    raise ValueError("Escolha URL externa ou upload para cada campo de imagem, não ambos.")
                record = records_by_id.get(asset_id)
                if not record:
                    raise ValueError("A imagem selecionada não existe mais. Atualize a lista de imagens.")
                path = resolve_asset(asset_dir, record)
                embed[embed_key] = {"url": "attachment://" + str(record["filename"])}
                selected_assets.append({"record": record, "path": path})
            url = validate_webhook_url(str(settings.get("lumo_webhook_url") or ""))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception:
            return jsonify({"ok": False, "error": "Configure e verifique o webhook antes de publicar."}), 400
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
        payload["attachments"] = [{"id": index, "filename": item["record"]["filename"]} for index, item in enumerate(selected_assets)]
        upload_files = [(str(index), item["record"]["filename"], item["record"]["mime_type"], item["path"].read_bytes()) for index, item in enumerate(selected_assets)]
        endpoint = url + "?wait=true"
        try:
            code, data, headers = _discord_request(endpoint, method="POST", payload=payload, files=upload_files or None)
            if code in (200, 201) and data.get("id"):
                published_at = now().astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
                for selected in selected_assets:
                    selected["record"]["last_used_at"] = published_at
                    selected["record"]["last_used_by"] = admin_id[:64]
                    selected["record"]["references"] = []
                if selected_assets:
                    save_settings(settings)
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

    @app.get("/api/admin/lumo/assets")
    @admin_required
    @limiter.limit("60 per minute")
    def lumo_asset_list():
        settings = expire_assets(load_settings())
        records = settings.get("lumo_media_assets") if isinstance(settings.get("lumo_media_assets"), list) else []
        return jsonify({"ok": True, "assets": [{k: row.get(k) for k in ("id", "original_name", "mime_type", "size", "width", "height", "uploaded_at", "last_used_at", "uploaded_by", "references", "status")} for row in records if isinstance(row, dict)], "retention_days": int(settings.get("lumo_asset_retention_days", 30) or 30)})

    @app.post("/api/admin/lumo/assets")
    @admin_required
    @limiter.limit("20 per hour", override_defaults=True)
    def lumo_asset_upload():
        if not _same_origin_request():
            return jsonify({"ok": False, "error": "Origem da solicitação inválida."}), 403
        uploaded = request.files.get("file")
        if uploaded is None:
            return jsonify({"ok": False, "error": "Selecione um arquivo de imagem."}), 400
        if request.content_length and request.content_length > MAX_IMAGE_BYTES + 128 * 1024:
            return jsonify({"ok": False, "error": "O arquivo excede o limite de 8 MB."}), 413
        try:
            record = validate_and_store(asset_dir, uploaded.stream, uploaded.filename or "imagem", str(get_admin_id() or ""))
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        settings = load_settings()
        records = settings.get("lumo_media_assets") if isinstance(settings.get("lumo_media_assets"), list) else []
        records.append(record)
        settings["lumo_media_assets"] = records
        save_settings(settings)
        audit_event("lumo_asset_upload", source="admin", actor_type="admin", actor_steam_id=str(get_admin_id() or ""), severity="info", message="Imagem enviada para a Comunicação Lumo", status_after="success", asset_id=record["id"], size=record["size"], mime_type=record["mime_type"])
        return jsonify({"ok": True, "asset": {**record, "preview_url": f"/api/admin/lumo/assets/{record['id']}/preview"}}), 201

    @app.get("/api/admin/lumo/assets/<asset_id>/preview")
    @admin_required
    @limiter.limit("120 per minute")
    def lumo_asset_preview(asset_id: str):
        if not re.fullmatch(r"[a-f0-9]{32}", asset_id):
            return jsonify({"ok": False, "error": "Imagem não encontrada."}), 404
        records = load_settings().get("lumo_media_assets") or []
        record = next((row for row in records if isinstance(row, dict) and row.get("id") == asset_id), None)
        if not record:
            return jsonify({"ok": False, "error": "Imagem não encontrada."}), 404
        try:
            path = resolve_asset(asset_dir, record)
        except ValueError:
            return jsonify({"ok": False, "error": "Imagem não encontrada."}), 404
        response = send_file(path, mimetype=record["mime_type"], conditional=True, max_age=0)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.delete("/api/admin/lumo/assets/<asset_id>")
    @admin_required
    @limiter.limit("30 per hour", override_defaults=True)
    def lumo_asset_delete(asset_id: str):
        if not _same_origin_request():
            return jsonify({"ok": False, "error": "Origem da solicitação inválida."}), 403
        settings = load_settings()
        records = settings.get("lumo_media_assets") if isinstance(settings.get("lumo_media_assets"), list) else []
        record = next((row for row in records if isinstance(row, dict) and row.get("id") == asset_id), None)
        if not record:
            return jsonify({"ok": False, "error": "Imagem não encontrada."}), 404
        if record.get("references"):
            return jsonify({"ok": False, "error": "Esta imagem está vinculada a uma comunicação e não pode ser removida."}), 409
        try:
            resolve_asset(asset_dir, record).unlink(missing_ok=True)
        except ValueError:
            pass
        settings["lumo_media_assets"] = [row for row in records if row is not record]
        save_settings(settings)
        audit_event("lumo_asset_delete", source="admin", actor_type="admin", actor_steam_id=str(get_admin_id() or ""), severity="info", message="Imagem removida da Comunicação Lumo", status_after="success", asset_id=asset_id)
        return jsonify({"ok": True})

    @app.post("/api/admin/lumo/assets/retention")
    @admin_required
    @limiter.limit("20 per hour", override_defaults=True)
    def lumo_asset_retention():
        if not _same_origin_request():
            return jsonify({"ok": False, "error": "Origem da solicitação inválida."}), 403
        body = request.get_json(silent=True) or {}
        try:
            days = int(body.get("days"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Informe um prazo em dias."}), 400
        if not 1 <= days <= 3650:
            return jsonify({"ok": False, "error": "O prazo deve estar entre 1 e 3.650 dias."}), 400
        settings = load_settings()
        settings["lumo_asset_retention_days"] = days
        save_settings(settings)
        return jsonify({"ok": True, "retention_days": days})

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
            query = db.query(audit_model).filter(audit_model.event_type.in_((
                "lumo_publish", "lumo_interaction", "lumo_automatic_announcement",
            )))
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
                items.append({
                    "id": row.id,
                    "type": row.event_type,
                    "trigger": payload.get("trigger", ""),
                    "player_id": payload.get("user_id", ""),
                    "message_id": payload.get("discord_message_id", ""),
                    "channel_id": payload.get("channel_id", ""),
                    "guild_id": payload.get("guild_id", ""),
                    "title": payload.get("title", ""),
                    "content": payload.get("description", ""),
                    "embed": payload.get("embed", {}),
                    "created_at": row.created_at.isoformat() if row.created_at else "",
                    "admin_steam_id": row.actor_steam_id or "",
                    "status": row.status_after or "unknown",
                    "error": row.message or "",
                })
            return jsonify({"ok": True, "items": items, "has_more": has_more, "limit": limit, "offset": offset})
        finally:
            db.close()

