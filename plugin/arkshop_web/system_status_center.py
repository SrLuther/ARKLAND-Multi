"""Central oficial de maturidade, disponibilidade e saúde operacional ARKLAND."""
from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from flask import jsonify, request
from sqlalchemy import text

log = logging.getLogger("arkshop.system_status")

MATURITY = {"PLANEJADO", "EM_DESENVOLVIMENTO", "ALPHA", "BETA", "EM_HOMOLOGACAO", "FINALIZADO", "EM_REFORMULACAO", "DESCONTINUADO", "NAO_AVALIADO"}
OPERATIONS = {"OPERACIONAL", "PARCIALMENTE_OPERACIONAL", "INSTAVEL", "EM_MANUTENCAO", "INDISPONIVEL", "NAO_DISPONIBILIZADO", "NAO_MONITORADO", "STATUS_DESCONHECIDO"}
AVAILABILITY = {"AVAILABLE", "EXPERIMENTAL", "RESTRICTED", "SUSPENDED", "NOT_RELEASED"}
INCIDENT_STATES = {"IDENTIFICADO", "EM_INVESTIGACAO", "EM_CORRECAO", "EM_MONITORAMENTO", "RESOLVIDO"}
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,79}$")

# Registry based on source modules and documentation. These are deliberately
# unclassified until administrators validate actual release and production state.
SEED_SYSTEMS = (
    ("webstore", "Web Store ARKLAND", "Plataforma web, autenticação e áreas públicas e administrativas", "Plataforma web"),
    ("economy", "Economia e Âmbares", "Carteira, bônus, pagamentos e movimentações de Âmbares", "Economia e recompensas"),
    ("catalog-delivery", "Catálogo e entregas", "Catálogo, compras, pedidos e entrega integrada aos servidores", "Catálogo e entregas"),
    ("licenses", "Licenças e benefícios", "Licenças de jogador, benefícios e sincronização com plugins", "Licenças e benefícios"),
    ("dino-market", "Comércio de criaturas", "Anúncios e negociações entre jogadores", "Economia e recompensas"),
    ("dino-lab", "Dino Lab", "Encomenda e entrega de criaturas personalizadas", "Catálogo e entregas"),
    ("resource-farm", "Fazenda de Recursos", "Produção, saldo e resgate de recursos configurados", "Plugins dos servidores"),
    ("teams", "Equipes e tribos", "Equipes do site, rankings e recursos de tribo", "Equipes e tribos"),
    ("seasonland", "SeasonLand", "Progressão sazonal e recompensas Free/Premium", "Eventos e competições"),
    ("betland", "BetLand", "Campanhas de sorteio, participação e apuração", "Eventos e competições"),
    ("polls", "Votações", "Enquetes públicas e administração de votações", "Eventos e competições"),
    ("support", "Suporte e tickets", "Atendimento, mensagens, anexos e acompanhamento de tickets", "Suporte e atendimento"),
    ("lumo", "Lumo", "Assistente da comunidade e central de comunicação", "Inteligência artificial e assistentes"),
    ("ark-cluster", "Servidores ARK", "Instâncias ASE e status de processo/listagem por mapa", "Servidores e plugins"),
    ("customshop", "Plugin CustomShop", "Economia in-game, comandos e entregas de compras", "Plugins dos servidores"),
    ("customdino-deliver", "Plugin CustomDinoDeliver", "Entrega de criaturas personalizadas no servidor", "Plugins dos servidores"),
    ("arkplayer", "Plugin ArkPlayer", "Comandos e utilidades para jogadores", "Plugins dos servidores"),
    ("arkeventhunt", "Plugin ArkEventHunt", "Eventos de caça e desafios no servidor", "Plugins dos servidores"),
    ("engramlevel", "Plugin EngramLevel", "Desbloqueio de engramas associado à progressão", "Plugins dos servidores"),
    ("structure-limits", "Plugin StructureLimits", "Limites compartilhados de estruturas por tribo e mapa", "Limites e gerenciamento"),
    ("permissions", "Permissions", "Permissões e grupos usados pelos plugins ArkApi", "Integrações e automações"),
    ("discord", "Integração com Discord", "Bot, notificações e painéis de status da comunidade", "Integrações e automações"),
    ("payments", "Pagamentos", "Integração de checkout e confirmação de pagamentos", "Integrações e automações"),
)


def ensure_system_status_schema(engine: Any) -> None:
    """Create only this feature's tables; safe to call repeatedly on SQLite/MySQL."""
    mysql = "mysql" in str(engine.url).lower()
    incident_id = "BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY" if mysql else "INTEGER PRIMARY KEY AUTOINCREMENT"
    ddl = (
        "CREATE TABLE IF NOT EXISTS system_status_catalog ("
        "system_key VARCHAR(80) PRIMARY KEY, name VARCHAR(160) NOT NULL, description TEXT NOT NULL, "
        "category VARCHAR(100) NOT NULL, maturity VARCHAR(32) NOT NULL DEFAULT 'NAO_AVALIADO', "
        "operational VARCHAR(40) NOT NULL DEFAULT 'NAO_MONITORADO', availability VARCHAR(24) NULL, "
        "version VARCHAR(80) NULL, updated_at VARCHAR(40) NULL, verified_at VARCHAR(40) NULL, "
        "implemented_json TEXT NOT NULL, development_json TEXT NOT NULL, limitations_json TEXT NOT NULL, "
        "known_issues_json TEXT NOT NULL, player_note TEXT NOT NULL, public_url VARCHAR(500) NOT NULL, "
        "is_public INTEGER NOT NULL DEFAULT 1, is_archived INTEGER NOT NULL DEFAULT 0, "
        "override_until VARCHAR(40) NULL, updated_by VARCHAR(40) NULL, changed_at VARCHAR(40) NOT NULL)"
    )
    statements = [ddl,
        "CREATE TABLE IF NOT EXISTS system_status_instances ("
        "id VARCHAR(220) PRIMARY KEY, system_key VARCHAR(80) NOT NULL, instance_key VARCHAR(120) NOT NULL, "
        "display_name VARCHAR(180) NOT NULL, map_id VARCHAR(120) NOT NULL, map_name VARCHAR(180) NOT NULL, "
        "version VARCHAR(80) NULL, operational VARCHAR(40) NOT NULL, source VARCHAR(40) NOT NULL, "
        "checked_at VARCHAR(40) NOT NULL, last_success_at VARCHAR(40) NULL, details VARCHAR(300) NOT NULL, "
        "failure_streak INTEGER NOT NULL DEFAULT 0, UNIQUE(system_key, instance_key))",
        "CREATE TABLE IF NOT EXISTS system_status_incidents ("
        f"id {incident_id}, system_key VARCHAR(80) NOT NULL, title VARCHAR(200) NOT NULL, "
        "description TEXT NOT NULL, state VARCHAR(32) NOT NULL, affected_instances_json TEXT NOT NULL, "
        "identified_at VARCHAR(40) NOT NULL, updated_at VARCHAR(40) NOT NULL, resolved_at VARCHAR(40) NULL, "
        "is_public INTEGER NOT NULL DEFAULT 1, updated_by VARCHAR(40) NULL)",
        "CREATE TABLE IF NOT EXISTS system_status_audit ("
        f"id {incident_id}, system_key VARCHAR(80) NOT NULL, actor VARCHAR(40) NOT NULL, "
        "changed_at VARCHAR(40) NOT NULL, before_json TEXT NOT NULL, after_json TEXT NOT NULL)",
    ]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
        # Seed registry labels only. Operational, maturity and availability remain explicitly unvalidated.
        for key, name, description, category in SEED_SYSTEMS:
            conn.execute(text(
                "INSERT INTO system_status_catalog "
                "(system_key,name,description,category,maturity,operational,availability,implemented_json,development_json,limitations_json,known_issues_json,player_note,public_url,is_public,is_archived,changed_at) "
                "VALUES (:key,:name,:description,:category,'NAO_AVALIADO','NAO_MONITORADO',NULL,'[]','[]','[]','[]','Aguardando validação administrativa.','',1,0,:now) "
                "ON DUPLICATE KEY UPDATE system_key=VALUES(system_key)"
            ) if mysql else text(
                "INSERT OR IGNORE INTO system_status_catalog "
                "(system_key,name,description,category,maturity,operational,availability,implemented_json,development_json,limitations_json,known_issues_json,player_note,public_url,is_public,is_archived,changed_at) "
                "VALUES (:key,:name,:description,:category,'NAO_AVALIADO','NAO_MONITORADO',NULL,'[]','[]','[]','[]','Aguardando validação administrativa.','',1,0,:now)"
            ), {"key": key, "name": name, "description": description, "category": category, "now": _now()})


def lumo_status_snapshot(engine: Any, *, servers: list[dict[str, Any]] | None = None,
                         runtime_statuses: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Return a short, explicitly qualified snapshot for Lumo; never infer unknown states."""
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT system_key,name,maturity,operational,availability,version,verified_at,player_note "
            "FROM system_status_catalog WHERE is_public=1 AND is_archived=0 ORDER BY category,name"
        )).fetchall()
        incidents = conn.execute(text(
            "SELECT title,state,identified_at FROM system_status_incidents "
            "WHERE is_public=1 AND state<>'RESOLVIDO' ORDER BY identified_at DESC LIMIT 5"
        )).fetchall()
    systems = [dict(row._mapping) for row in rows]
    cluster = next((item for item in systems if item["system_key"] == "ark-cluster"), None)
    if cluster is not None:
        configs = {str(item.get("server_id") or ""): item for item in (servers or []) if isinstance(item, dict)}
        cluster["instances"] = [
            {"instance_key": server_id,
             "display_name": str(status.get("display_name") or configs.get(server_id, {}).get("label") or server_id),
             "map_name": str(configs.get(server_id, {}).get("server_map") or ""),
             "operational": str(status.get("status") or "STATUS_DESCONHECIDO"),
             "checked_at": status.get("updated_at") or "", "details": str(status.get("status_detail") or "")}
            for server_id, status in sorted((runtime_statuses or {}).items())
        ]
    return {
        "ok": True,
        "systems": systems,
        "incidents": [dict(row._mapping) for row in incidents],
        "updated_at": _now(),
    }


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _json_list(raw: Any, *, limit: int = 20) -> list[str]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = []
    if not isinstance(raw, list):
        return []
    return [str(item).strip()[:300] for item in raw[:limit] if str(item).strip()]


def _row(row: Any) -> dict[str, Any]:
    item = dict(row._mapping)
    for field in ("implemented_json", "development_json", "limitations_json", "known_issues_json"):
        key = field.removesuffix("_json")
        try:
            item[key] = json.loads(item.pop(field) or "[]")
        except Exception:
            item[key] = []
    item["availability"] = item.get("availability") or None
    item["is_public"] = bool(item.get("is_public"))
    item["is_archived"] = bool(item.get("is_archived"))
    item["override_active"] = bool(item.get("override_until") and str(item["override_until"]) > _now())
    item.pop("override_until", None)
    return item


def _incident(row: Any) -> dict[str, Any]:
    item = dict(row._mapping)
    try:
        item["affected_instances"] = json.loads(item.pop("affected_instances_json") or "[]")
    except Exception:
        item["affected_instances"] = []
    item["is_public"] = bool(item.get("is_public"))
    return item


def _audit(conn: Any, key: str, actor: str, before: dict[str, Any], after: dict[str, Any]) -> None:
    now = _now()
    mysql = "mysql" in str(conn.engine.url).lower()
    sql = ("INSERT INTO system_status_audit (system_key,actor,changed_at,before_json,after_json) VALUES (:key,:actor,:now,:before,:after)" if mysql else
           "INSERT INTO system_status_audit (system_key,actor,changed_at,before_json,after_json) VALUES (:key,:actor,:now,:before,:after)")
    conn.execute(text(sql), {"key": key, "actor": actor[:40], "now": now,
        "before": json.dumps(before, ensure_ascii=False, default=str), "after": json.dumps(after, ensure_ascii=False, default=str)})


def register_system_status_routes(app: Any, *, db_ready: Callable[[], bool], engine_getter: Callable[[], Any],
    admin_required: Callable[[Callable[..., Any]], Callable[..., Any]], api_key_required: Callable[..., Any],
    actor_getter: Callable[[], Any], load_servers: Callable[[], list[dict[str, Any]]],
    runtime_statuses: Callable[..., dict[str, dict[str, Any]]], limiter: Any) -> None:
    def ready():
        if not db_ready() or engine_getter() is None:
            return jsonify({"ok": False, "error": "database_unavailable"}), 503
        return None

    def fetch_catalog(public: bool = False) -> list[dict[str, Any]]:
        where = "WHERE is_public=1 AND is_archived=0" if public else "WHERE is_archived=0"
        with engine_getter().connect() as conn:
            rows = conn.execute(text(f"SELECT * FROM system_status_catalog {where} ORDER BY category,name")).fetchall()
            return [_row(row) for row in rows]

    @app.get("/api/public/systems-status")
    @limiter.limit("60 per minute")
    def public_systems_status():
        if (err := ready()) is not None:
            return err
        systems = fetch_catalog(public=True)
        with engine_getter().connect() as conn:
            incidents = [_incident(row) for row in conn.execute(text(
                "SELECT * FROM system_status_incidents WHERE is_public=1 ORDER BY identified_at DESC LIMIT 100"
            )).fetchall()]
            instances = [dict(row._mapping) for row in conn.execute(text(
                "SELECT i.* FROM system_status_instances i JOIN system_status_catalog c ON c.system_key=i.system_key "
                "WHERE c.is_public=1 AND c.is_archived=0 ORDER BY c.category,c.name,i.display_name"
            )).fetchall()]
        # Existing manager feed is the authoritative server-process/listing source.
        try:
            runtime = runtime_statuses(max_age_s=600)
            configs = {str(s.get("server_id") or ""): s for s in load_servers() if isinstance(s, dict)}
            cluster = next((s for s in systems if s["system_key"] == "ark-cluster"), None)
            if cluster is not None:
                cluster["instances"] = []
                for server_id, status in sorted(runtime.items()):
                    config = configs.get(server_id, {})
                    cluster["instances"].append({"instance_key": server_id,
                        "display_name": str(status.get("display_name") or config.get("label") or server_id),
                        "map_id": server_id, "map_name": str(config.get("server_map") or ""),
                        "version": None, "operational": str(status.get("status") or "STATUS_DESCONHECIDO"),
                        "source": "server_manager", "checked_at": status.get("updated_at"),
                        "details": str(status.get("status_detail") or "")})
        except Exception:
            log.warning("Não foi possível agregar status dos mapas à central", exc_info=True)
        grouped = {}
        for item in instances:
            grouped.setdefault(item["system_key"], []).append(item)
        for system in systems:
            if system.get("system_key") != "ark-cluster":
                system["instances"] = grouped.get(system["system_key"], [])
        counts = {"total": len(systems), "operational": sum(s["operational"] == "OPERACIONAL" for s in systems),
            "in_development": sum(s["maturity"] in {"PLANEJADO", "EM_DESENVOLVIMENTO", "ALPHA", "BETA", "EM_HOMOLOGACAO", "EM_REFORMULACAO"} for s in systems),
            "with_issues": sum(s["operational"] in {"PARCIALMENTE_OPERACIONAL", "INSTAVEL", "EM_MANUTENCAO", "INDISPONIVEL"} for s in systems)}
        response = jsonify({"ok": True, "updated_at": _now(), "summary": counts, "systems": systems, "incidents": incidents})
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    @app.get("/api/admin/systems-status")
    @admin_required
    def admin_systems_status():
        if (err := ready()) is not None:
            return err
        return jsonify({"ok": True, "systems": fetch_catalog(), "incidents": public_incidents(include_private=True)})

    def public_incidents(include_private: bool = False) -> list[dict[str, Any]]:
        with engine_getter().connect() as conn:
            suffix = "" if include_private else " AND is_public=1"
            return [_incident(row) for row in conn.execute(text(
                "SELECT * FROM system_status_incidents WHERE 1=1" + suffix + " ORDER BY identified_at DESC LIMIT 200"
            )).fetchall()]

    @app.put("/api/admin/systems-status/<system_key>")
    @admin_required
    def update_system(system_key: str):
        if (err := ready()) is not None:
            return err
        if not KEY_RE.fullmatch(system_key):
            return jsonify({"ok": False, "error": "invalid_system_key"}), 400
        body = request.get_json(silent=True) or {}
        allowed = {"name", "description", "category", "maturity", "operational", "availability", "version", "updated_at", "verified_at", "implemented", "development", "limitations", "known_issues", "player_note", "public_url", "is_public", "is_archived", "override_until"}
        if set(body) - allowed:
            return jsonify({"ok": False, "error": "unknown_fields", "fields": sorted(set(body)-allowed)}), 400
        if "maturity" in body and body["maturity"] not in MATURITY:
            return jsonify({"ok": False, "error": "invalid_maturity"}), 400
        if "operational" in body and body["operational"] not in OPERATIONS:
            return jsonify({"ok": False, "error": "invalid_operational_state"}), 400
        if body.get("availability") not in (None, "", *AVAILABILITY):
            return jsonify({"ok": False, "error": "invalid_availability"}), 400
        if body.get("public_url") and not str(body["public_url"]).startswith("https://"):
            return jsonify({"ok": False, "error": "public_url_must_be_https"}), 400
        max_lengths = {"name": 160, "description": 2000, "category": 100, "version": 80,
                       "updated_at": 40, "verified_at": 40, "player_note": 2000,
                       "public_url": 500, "override_until": 40}
        for field, max_length in max_lengths.items():
            if field in body and body[field] is not None and len(str(body[field])) > max_length:
                return jsonify({"ok": False, "error": "field_too_long", "field": field, "max_length": max_length}), 400
        list_fields = {field: json.dumps(_json_list(body.get(field)), ensure_ascii=False) for field in ("implemented", "development", "limitations", "known_issues") if field in body}
        columns = {"name", "description", "category", "maturity", "operational", "availability", "version", "updated_at", "verified_at", "player_note", "public_url", "is_public", "is_archived", "override_until"}
        values: dict[str, Any] = {k: body[k] for k in columns if k in body}
        values.update(list_fields)
        if "availability" in values and values["availability"] == "": values["availability"] = None
        for key in ("is_public", "is_archived"):
            if key in values: values[key] = int(bool(values[key]))
        if "override_until" in values and values["override_until"]:
            try:
                expiry = datetime.fromisoformat(str(values["override_until"]).replace("Z", "+00:00"))
                if expiry.tzinfo is None: raise ValueError
                if expiry <= datetime.now(UTC) or expiry > datetime.now(UTC) + timedelta(days=14): raise ValueError
            except Exception:
                return jsonify({"ok": False, "error": "override_must_expire_within_14_days"}), 400
        values["changed_at"] = _now()
        values.setdefault("updated_at", values["changed_at"])
        values.setdefault("verified_at", values["changed_at"])
        values["updated_by"] = str(actor_getter() or "")[:40]
        actor = values["updated_by"]
        with engine_getter().begin() as conn:
            old_row = conn.execute(text("SELECT * FROM system_status_catalog WHERE system_key=:key"), {"key": system_key}).fetchone()
            before = _row(old_row) if old_row else {}
            if not old_row and ("name" not in values or "description" not in values or "category" not in values):
                return jsonify({"ok": False, "error": "name_description_category_required_for_new_system"}), 400
            if not old_row:
                defaults = {"name": system_key, "description": "", "category": "Outros", "maturity": "NAO_AVALIADO", "operational": "NAO_MONITORADO", "availability": None, "implemented": "[]", "development": "[]", "limitations": "[]", "known_issues": "[]", "player_note": "", "public_url": "", "is_public": 1, "is_archived": 0}
                values = {**defaults, **values}
            sets = []
            params = {"key": system_key}
            for col, value in values.items():
                db_col = col + "_json" if col in {"implemented", "development", "limitations", "known_issues"} else col
                sets.append(f"{db_col}=:{col}")
                params[col] = value
            if old_row:
                conn.execute(text("UPDATE system_status_catalog SET " + ",".join(sets) + " WHERE system_key=:key"), params)
            else:
                conn.execute(text("INSERT INTO system_status_catalog (system_key," + ",".join(s.split("=")[0] for s in sets) + ") VALUES (:key," + ",".join(":"+k for k in values) + ")"), params)
            after_row = conn.execute(text("SELECT * FROM system_status_catalog WHERE system_key=:key"), {"key": system_key}).fetchone()
            _audit(conn, system_key, actor, before, _row(after_row))
        return jsonify({"ok": True, "system": fetch_system(system_key)})

    def fetch_system(system_key: str) -> dict[str, Any] | None:
        with engine_getter().connect() as conn:
            row = conn.execute(text("SELECT * FROM system_status_catalog WHERE system_key=:key"), {"key": system_key}).fetchone()
            return _row(row) if row else None

    @app.get("/api/admin/systems-status/<system_key>/audit")
    @admin_required
    def system_audit(system_key: str):
        if (err := ready()) is not None:
            return err
        with engine_getter().connect() as conn:
            rows = conn.execute(text(
                "SELECT id,actor,changed_at,before_json,after_json FROM system_status_audit "
                "WHERE system_key=:key ORDER BY id DESC LIMIT 100"
            ), {"key": system_key}).fetchall()
        entries = []
        for row in rows:
            item = dict(row._mapping)
            for field in ("before_json", "after_json"):
                try:
                    item[field.removesuffix("_json")] = json.loads(item.pop(field) or "{}")
                except Exception:
                    item[field.removesuffix("_json")] = {}
            entries.append(item)
        return jsonify({"ok": True, "system_key": system_key, "entries": entries})

    @app.post("/api/admin/systems-status/<system_key>/incidents")
    @admin_required
    def create_incident(system_key: str):
        if (err := ready()) is not None: return err
        body = request.get_json(silent=True) or {}
        title = str(body.get("title") or "").strip()[:200]
        description = str(body.get("description") or "").strip()
        state = str(body.get("state") or "IDENTIFICADO")
        if not fetch_system(system_key): return jsonify({"ok": False, "error": "system_not_found"}), 404
        if not title or not description or state not in INCIDENT_STATES:
            return jsonify({"ok": False, "error": "title_description_and_valid_state_required"}), 400
        now, actor = _now(), str(actor_getter() or "")[:40]
        public = int(bool(body.get("is_public", True)))
        affected = json.dumps(_json_list(body.get("affected_instances")), ensure_ascii=False)
        mysql = "mysql" in str(engine_getter().url).lower()
        stmt = ("INSERT INTO system_status_incidents (system_key,title,description,state,affected_instances_json,identified_at,updated_at,resolved_at,is_public,updated_by) VALUES (:key,:title,:description,:state,:affected,:now,:now,:resolved,:public,:actor)" if mysql else
                "INSERT INTO system_status_incidents (system_key,title,description,state,affected_instances_json,identified_at,updated_at,resolved_at,is_public,updated_by) VALUES (:key,:title,:description,:state,:affected,:now,:now,:resolved,:public,:actor)")
        resolved = now if state == "RESOLVIDO" else None
        with engine_getter().begin() as conn:
            result = conn.execute(text(stmt), {"key": system_key,"title":title,"description":description,"state":state,"affected":affected,"now":now,"resolved":resolved,"public":public,"actor":actor})
            incident_id = result.lastrowid
            _audit(conn, system_key, actor, {}, {"incident_id": incident_id, "title": title, "state": state})
        return jsonify({"ok": True, "incident_id": incident_id}), 201

    @app.patch("/api/admin/systems-status/incidents/<int:incident_id>")
    @admin_required
    def update_incident(incident_id: int):
        if (err := ready()) is not None: return err
        body = request.get_json(silent=True) or {}
        state = str(body.get("state") or "")
        if state not in INCIDENT_STATES: return jsonify({"ok": False, "error": "invalid_incident_state"}), 400
        now, actor = _now(), str(actor_getter() or "")[:40]
        with engine_getter().begin() as conn:
            row = conn.execute(text("SELECT * FROM system_status_incidents WHERE id=:id"), {"id": incident_id}).fetchone()
            if not row: return jsonify({"ok": False, "error": "incident_not_found"}), 404
            before = _incident(row)
            resolved = now if state == "RESOLVIDO" else None
            conn.execute(text("UPDATE system_status_incidents SET state=:state,updated_at=:now,resolved_at=:resolved,updated_by=:actor WHERE id=:id"), {"state":state,"now":now,"resolved":resolved,"actor":actor,"id":incident_id})
            after = {**before, "state": state, "updated_at": now, "resolved_at": resolved}
            _audit(conn, str(before["system_key"]), actor, before, after)
        return jsonify({"ok": True})

    @app.post("/api/plugin/systems-status/heartbeat")
    @api_key_required(allow_admin_session=False)
    @limiter.limit("120 per minute")
    def plugin_heartbeat():
        if (err := ready()) is not None: return err
        body = request.get_json(silent=True) or {}
        key = str(body.get("system_key") or "")
        map_id = str(body.get("map_id") or "")
        status = str(body.get("operational") or "STATUS_DESCONHECIDO")
        version = str(body.get("version") or "")[:80]
        if not KEY_RE.fullmatch(key) or status not in OPERATIONS or not map_id:
            return jsonify({"ok": False, "error": "invalid_heartbeat"}), 400
        if not fetch_system(key):
            return jsonify({"ok": False, "error": "unknown_system"}), 404
        configured = {str(s.get("server_id") or ""): s for s in load_servers() if isinstance(s, dict)}
        server = configured.get(map_id)
        if server is None: return jsonify({"ok": False, "error": "unknown_map"}), 403
        now = _now()
        instance_key = f"{map_id}"
        row_id = f"{key}:{instance_key}"
        values = {"id":row_id,"key":key,"instance":instance_key,"display":str(server.get("label") or map_id)[:180],"map_id":map_id,"map_name":str(server.get("server_map") or "")[:180],"version":version or None,"status":status,"source":"plugin_heartbeat","checked":now,"success":now if status == "OPERACIONAL" else None,"details":str(body.get("details") or "")[:300]}
        mysql = "mysql" in str(engine_getter().url).lower()
        sql = ("INSERT INTO system_status_instances (id,system_key,instance_key,display_name,map_id,map_name,version,operational,source,checked_at,last_success_at,details) VALUES (:id,:key,:instance,:display,:map_id,:map_name,:version,:status,:source,:checked,:success,:details) ON DUPLICATE KEY UPDATE display_name=VALUES(display_name),map_id=VALUES(map_id),map_name=VALUES(map_name),version=VALUES(version),operational=VALUES(operational),source=VALUES(source),checked_at=VALUES(checked_at),last_success_at=COALESCE(VALUES(last_success_at),last_success_at),details=VALUES(details)" if mysql else
              "INSERT INTO system_status_instances (id,system_key,instance_key,display_name,map_id,map_name,version,operational,source,checked_at,last_success_at,details) VALUES (:id,:key,:instance,:display,:map_id,:map_name,:version,:status,:source,:checked,:success,:details) ON CONFLICT(system_key,instance_key) DO UPDATE SET display_name=excluded.display_name,map_id=excluded.map_id,map_name=excluded.map_name,version=excluded.version,operational=excluded.operational,source=excluded.source,checked_at=excluded.checked_at,last_success_at=COALESCE(excluded.last_success_at,system_status_instances.last_success_at),details=excluded.details")
        with engine_getter().begin() as conn:
            conn.execute(text(sql), values)
        return jsonify({"ok": True, "checked_at": now})

