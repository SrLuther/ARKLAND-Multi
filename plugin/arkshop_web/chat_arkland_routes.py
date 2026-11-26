"""API administrativa e de instâncias do Chat Arkland."""
from __future__ import annotations

import logging
import json
from string import Formatter

from flask import jsonify, request, make_response
from chat_arkland_config import MESSAGES, format_global, select_style, validate_config
from chat_arkland_service import ChatArklandService

log = logging.getLogger("arkshop.chat_arkland")
_SERVICE: ChatArklandService | None = None


def get_chat_service():
    return _SERVICE


def register_chat_arkland_routes(app, *, db_ready, session_factory, engine_getter, load_servers,
                               admin_required, api_key_required, actor_getter, license_provider,
                               license_catalog, discord_identity, load_settings, limiter=None,
                               bootstrap_key=lambda: "", public_url=lambda: "https://arkland.com.br"):
    global _SERVICE
    service = ChatArklandService(session_factory, engine_getter, load_servers,
        license_provider=license_provider, license_catalog=license_catalog, discord_identity=discord_identity)
    _SERVICE = service
    limit = limiter.limit if limiter else (lambda *a, **kw: lambda fn: fn)

    def instance_rate_key():
        if request.content_length and request.content_length > 1024 * 1024:
            return "chat:oversize:" + str(request.remote_addr)
        payload = request.get_json(silent=True)
        return "chat:" + str(payload.get("server_key", ""))[:100] if isinstance(payload, dict) else "chat:invalid"

    def failed(failure, status=400):
        return jsonify({"ok": False, "error": str(failure)}), status

    def reconfigure():
        def run():
            try:
                from lumo_gateway import get_lumo_runtime
                runtime = get_lumo_runtime()
                if runtime:
                    from chat_arkland_discord import transport_enabled
                    settings = load_settings()
                    wanted = bool(settings.get("lumo_assistant_enabled") or settings.get("lumo_game_chat_enabled") or transport_enabled())
                    if wanted and runtime.snapshot()["state"] not in {"online", "starting", "reconnecting"}:
                        runtime.reconfigure()
                    elif not wanted:
                        runtime.stop()
            except Exception as failure:
                log.warning("Reconfiguração do transporte Discord pendente (%s)", type(failure).__name__)
        from background_tasks import submit
        submit(run, dedupe_key="chat-arkland-reconfigure", name="chat-arkland-config")

    @app.get("/api/admin/chat-arkland")
    @admin_required
    def chat_arkland_admin():
        if not db_ready():
            return failed("Banco central temporariamente indisponível.", 503)
        try:
            settings = load_settings()
            return jsonify({"ok": True, **service.admin_snapshot(),
                "message_variables": {key: sorted({field for _, field, _, _ in Formatter().parse(value) if field}) for key, value in MESSAGES.items()}, "discord": {
                "guild_id": str(settings.get("lumo_guild_id") or ""),
                "channel_id": str(settings.get("lumo_game_chat_channel_id") or ""),
                "token_configured": bool(settings.get("lumo_bot_token")),
                "source": "Configuração compartilhada do Lumo"}})
        except Exception as failure:
            log.warning("Consulta administrativa do Chat Arkland falhou (%s)", type(failure).__name__)
            return failed("Não foi possível consultar o Chat Arkland.", 503)

    @app.get("/api/admin/chat-arkland/bootstrap/<server_key>")
    @admin_required
    def chat_arkland_bootstrap(server_key):
        if server_key not in service.catalog():
            return failed("Instância não cadastrada.", 404)
        key = bootstrap_key()
        if not key:
            return failed("A chave interna do serviço ainda não está configurada.", 503)
        shared = service.load_config()
        payload = {"Local": {"ServerKey": server_key, "ApiUrl": public_url().rstrip("/"), "ApiKey": key, "ObserveOnly": True},
                   "Shared": {"revision": shared["revision"], "config": shared["config"]}, "Runtime": {}}
        response = make_response(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        response.headers.update({"Content-Type": "application/json; charset=utf-8", "Content-Disposition": 'attachment; filename="config.json"',
                                 "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
        return response

    @app.put("/api/admin/chat-arkland/config")
    @admin_required
    @limit("30 per minute")
    def chat_arkland_publish():
        body = request.get_json(silent=True) or {}
        try:
            result = service.publish_config(body.get("config"), int(body.get("expected_revision")), actor_getter() or "admin")
            reconfigure()
            return jsonify({"ok": True, **result})
        except (ValueError, TypeError) as failure:
            return failed(failure)
        except Exception as failure:
            log.warning("Publicação do Chat Arkland falhou (%s)", type(failure).__name__)
            return failed("Não foi possível publicar a configuração; a revisão anterior foi preservada.", 503)

    @app.post("/api/admin/chat-arkland/preview")
    @admin_required
    def chat_arkland_preview():
        body = request.get_json(silent=True) or {}
        try:
            config = validate_config(body.get("config", {}))
            sample = body.get("sample") or {}
            actor = {"steam_id": "", "name": "Sobrevivente", "tribe_name": "Tribo de exemplo",
                     "groups": sample.get("groups", []), "tribe_id": "0"}
            tag, colors = select_style(config, actor, set(sample.get("licenses", [])))
            rendered = format_global(config, actor, "125", "Valguero [OMEGA]", "Olá, comunidade ARKLAND!", tag=tag, colors=colors)
            return jsonify({"ok": True, **rendered, "notice": "Exemplo visual. O ID 125 é ilustrativo; nenhuma mensagem foi enviada."})
        except (ValueError, TypeError, KeyError) as failure:
            return failed(failure)

    @app.get("/api/admin/chat-arkland/tag-candidates")
    @admin_required
    def chat_arkland_discovery():
        return jsonify({"ok": True, "candidates": service.discover_tags(), "notice": "Nenhuma tag descoberta é ativada sem confirmação administrativa."})

    @app.post("/api/admin/chat-arkland/rollback")
    @admin_required
    def chat_arkland_rollback():
        body = request.get_json(silent=True) or {}
        try:
            result = service.rollback_config(int(body.get("revision")), int(body.get("expected_revision")), actor_getter() or "admin")
            reconfigure()
            return jsonify({"ok": True, **result})
        except (TypeError, ValueError) as failure:
            return failed(failure)

    @app.post("/api/chat-arkland/plugin/exchange")
    @api_key_required(allow_admin_session=False)
    @limit("900 per minute", key_func=instance_rate_key)
    def chat_arkland_exchange():
        if not db_ready():
            return failed("Banco central temporariamente indisponível.", 503)
        if request.content_length and request.content_length > 1024 * 1024:
            return failed("O lote excede 1 MiB.", 413)
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return failed("Lote de comunicação inválido.")
        try:
            return jsonify(service.exchange(body))
        except (ValueError, TypeError, KeyError) as failure:
            return failed(failure)
        except Exception as failure:
            # Nunca incluir payloads, mensagens privadas, URLs com senhas ou tokens.
            log.warning("Intercâmbio do Chat Arkland indisponível (%s)", type(failure).__name__)
            return failed("Transporte temporariamente indisponível; preserve o chat nativo.", 503)
