"""Hub transacional do Chat Arkland; somente a Web Store acessa o banco."""
from __future__ import annotations

import hashlib
import calendar
import json
import math
import re
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable
from weakref import WeakSet

from sqlalchemy import (BigInteger, Boolean, Column, DateTime, Index, Integer, MetaData,
                        String, Table, Text, UniqueConstraint, and_, delete, func, insert, or_, select, text, update)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.exc import IntegrityError

from chat_arkland_config import DEFAULTS, MESSAGES, censor, clean_text, display_name, format_global, select_style, validate_config
from player_monitoring_routes import _ensure_schema as ensure_monitor_schema, ingest_session_event

META = MetaData()
JSON_TEXT = Text().with_variant(LONGTEXT(), "mysql")
SEQUENCE = BigInteger().with_variant(Integer(), "sqlite")
CONFIG = Table("chat_arkland_config", META, Column("id", Integer, primary_key=True),
    Column("revision", Integer, nullable=False), Column("config_json", JSON_TEXT, nullable=False),
    Column("changed_at", DateTime, nullable=False), Column("actor", String(40), nullable=False))
REVISIONS = Table("chat_arkland_revisions", META, Column("revision", Integer, primary_key=True),
    Column("config_json", JSON_TEXT, nullable=False), Column("changed_at", DateTime, nullable=False), Column("actor", String(40), nullable=False))
PLAYERS = Table("chat_arkland_players", META, Column("public_id", SEQUENCE, primary_key=True, autoincrement=True),
    Column("steam_id", String(32), nullable=False, unique=True), Column("notifications", Boolean, nullable=False, default=True),
    Column("reply_to", String(32)), Column("last_global_at", DateTime), sqlite_autoincrement=True)
INSTANCES = Table("chat_arkland_instances", META, Column("server_key", String(100), primary_key=True),
    Column("boot_id", String(8), nullable=False), Column("last_seen_at", DateTime, nullable=False),
    Column("last_monitor_at", DateTime), Column("revision", Integer, nullable=False),
    Column("plugin_version", String(32), nullable=False), Column("observer", Boolean, nullable=False),
    Column("last_error", String(256), nullable=False), Column("player_count", Integer, nullable=False))
EVENTS = Table("chat_arkland_events", META, Column("event_id", String(64), primary_key=True), Column("expires_at", DateTime, nullable=False))
MESSAGES_TABLE = Table("chat_arkland_messages", META, Column("seq", SEQUENCE, primary_key=True, autoincrement=True),
    Column("event_id", String(64), nullable=False, unique=True), Column("kind", String(16), nullable=False),
    Column("origin", String(16), nullable=False), Column("server_key", String(100), nullable=False),
    Column("sender_steam", String(32)), Column("payload_json", JSON_TEXT, nullable=False),
    Column("created_at", DateTime, nullable=False), Column("expires_at", DateTime, nullable=False),
    Column("discord_state", String(16), nullable=False), Column("discord_id", String(32)), Column("discord_owner", String(40)),
    Column("claimed_at", DateTime), sqlite_autoincrement=True)
DELIVERIES = Table("chat_arkland_deliveries", META, Column("delivery_id", String(64), primary_key=True),
    Column("event_id", String(64), nullable=False), Column("recipient", String(32), nullable=False),
    Column("lease_owner", String(100)), Column("lease_until", DateTime), Column("acked_at", DateTime),
    Column("expires_at", DateTime, nullable=False), UniqueConstraint("event_id", "recipient"))
LEADER = Table("chat_arkland_discord_lease", META, Column("id", Integer, primary_key=True),
    Column("owner", String(40)), Column("until_at", DateTime))
SCHEMA = Table("chat_arkland_schema", META, Column("version", Integer, primary_key=True), Column("applied_at", DateTime, nullable=False))
Index("ix_ca_messages_cursor", MESSAGES_TABLE.c.seq, MESSAGES_TABLE.c.expires_at)
Index("ix_ca_private_recipient", DELIVERIES.c.recipient, DELIVERIES.c.acked_at, DELIVERIES.c.expires_at)
Index("ix_ca_messages_discord", MESSAGES_TABLE.c.discord_state, MESSAGES_TABLE.c.seq)

_STEAM = re.compile(r"^[0-9]{17}$")
_BOOT = re.compile(r"^[0-9a-f]{8}$")
_SESSION = re.compile(r"^ca-[0-9a-f]{8}-[0-9a-f]{32}$")
_READY = WeakSet()
_SCHEMA_LOCK = threading.RLock()


def _dump(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _insert_once(db, table, values, conflict_keys):
    if db.get_bind().dialect.name == "mysql":
        from sqlalchemy.dialects.mysql import insert as mysql_insert
        query = mysql_insert(table).values(**values)
        # INSERT IGNORE is intentionally restricted to known idempotency tables.
        query = query.prefix_with("IGNORE")
    else:
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        query = sqlite_insert(table).values(**values).on_conflict_do_nothing(index_elements=conflict_keys)
    return db.execute(query).rowcount == 1


def ensure_chat_schema(engine):
    with _SCHEMA_LOCK:
        if engine in _READY:
            return
        ensure_monitor_schema(engine)
        META.create_all(engine)
        with engine.begin() as conn:
            if conn.execute(select(CONFIG.c.id).where(CONFIG.c.id == 1)).first() is None:
                defaults = validate_config({})
                conn.execute(insert(CONFIG).values(id=1, revision=1, config_json=_dump(defaults), changed_at=datetime.utcnow(), actor="system"))
                conn.execute(insert(REVISIONS).values(revision=1, config_json=_dump(defaults), changed_at=datetime.utcnow(), actor="system"))
            if conn.execute(select(LEADER.c.id).where(LEADER.c.id == 1)).first() is None:
                conn.execute(insert(LEADER).values(id=1))
            if conn.execute(select(SCHEMA.c.version).where(SCHEMA.c.version == 1)).first() is None:
                conn.execute(insert(SCHEMA).values(version=1, applied_at=datetime.utcnow()))
        _READY.add(engine)


class ChatArklandService:
    def __init__(self, session_factory, engine_getter, servers, *, license_provider=None,
                 license_catalog=None, discord_identity=None, clock=None):
        self.session_factory = session_factory
        self.engine_getter = engine_getter
        self.servers = servers
        self.license_provider = license_provider or (lambda db, ids: {})
        self.license_catalog = license_catalog or (lambda: [])
        self.discord_identity = discord_identity or (lambda db, user_id: None)
        self.clock = clock or datetime.utcnow
        self._config_cache = None
        self._config_time = 0.0
        self._lock = threading.RLock()
        self._cleanup_at = 0.0

    def database(self):
        engine = self.engine_getter()
        if engine is None:
            raise RuntimeError("Banco central temporariamente indisponível.")
        ensure_chat_schema(engine)
        return self.session_factory()

    def load_config(self, db=None, *, force=False):
        with self._lock:
            if not force and self._config_cache and time.monotonic() - self._config_time < 2:
                return self._config_cache
        owned = db is None
        db = db or self.database()
        try:
            row = db.execute(select(CONFIG).where(CONFIG.c.id == 1)).mappings().one()
            value = {"revision": row["revision"], "config": validate_config(json.loads(row["config_json"])),
                     "changed_at": row["changed_at"].isoformat() + "Z", "actor": row["actor"]}
            with self._lock:
                self._config_cache, self._config_time = value, time.monotonic()
            return value
        finally:
            if owned:
                db.close()

    def publish_config(self, raw, expected_revision, actor):
        config = validate_config(raw)
        if len(_dump(config).encode("utf-8")) > 128 * 1024:
            raise ValueError("A configuração excede 128 KiB.")
        db = self.database()
        try:
            revision = int(expected_revision) + 1
            result = db.execute(update(CONFIG).where(CONFIG.c.id == 1, CONFIG.c.revision == expected_revision).values(
                revision=revision, config_json=_dump(config), changed_at=self.clock(), actor=actor))
            if result.rowcount != 1:
                raise ValueError("A configuração foi alterada por outra pessoa. Atualize a página antes de publicar.")
            db.execute(insert(REVISIONS).values(revision=revision, config_json=_dump(config), changed_at=self.clock(), actor=actor))
            db.commit()
            with self._lock:
                self._config_cache = None
            return self.load_config(force=True)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def catalog(self):
        from map_members_service import server_identity_catalog
        result = {}
        for server in server_identity_catalog(list(self.servers() or [])):
            # Um slug de exibição não substitui a identidade permanente.
            key = str(server.get("arkland_ref") or "")
            if key:
                result[key] = server
        return result

    def _id(self, db, steam):
        if not _STEAM.fullmatch(steam):
            raise ValueError("Identidade de jogador inválida.")
        existing = db.execute(select(PLAYERS).where(PLAYERS.c.steam_id == steam)).mappings().first()
        if existing:
            return existing
        _insert_once(db, PLAYERS, {"steam_id": steam, "notifications": True}, ["steam_id"])
        return db.execute(select(PLAYERS).where(PLAYERS.c.steam_id == steam)).mappings().one()

    def _ids(self, db, steam_ids):
        steam_ids = list(set(steam_ids))
        if not steam_ids:
            return {}
        result = {row["steam_id"]: row for row in db.execute(select(PLAYERS).where(PLAYERS.c.steam_id.in_(steam_ids))).mappings()}
        for steam in steam_ids:
            if steam not in result:
                result[steam] = self._id(db, steam)
        return result

    def _event(self, db, event_id):
        return _insert_once(db, EVENTS, {"event_id": event_id, "expires_at": self.clock() + timedelta(days=1)}, ["event_id"])

    def _message(self, db, event_id, kind, origin, server_key, sender, payload, config, recipients=()):
        expires = self.clock() + timedelta(seconds=config["MessageTtlSeconds"])
        result = db.execute(insert(MESSAGES_TABLE).values(event_id=event_id, kind=kind, origin=origin,
            server_key=server_key, sender_steam=sender, payload_json=_dump(payload), created_at=self.clock(), expires_at=expires,
            discord_state="pending" if kind == "global" and origin == "game" and config["Discord"]["Enabled"] else "skip"))
        for recipient in set(recipients):
            db.execute(insert(DELIVERIES).values(delivery_id=hashlib.sha256(f"{event_id}:{recipient}".encode()).hexdigest(),
                event_id=event_id, recipient=recipient, expires_at=expires))
        return result.inserted_primary_key[0]

    def _notice(self, db, event_id, recipient, message, config, **variables):
        variables.setdefault("comando", config["PrivateMessages"]["ReplyCommand"] if message == "ReplyUsage" else config["PrivateMessages"]["Command"])
        variables.setdefault("resposta", config["PrivateMessages"]["ReplyCommand"])
        body = config["Messages"].get(message, message).format_map(variables)
        self._message(db, event_id, "notice", "system", "", None,
                      {"text": body, "recipients": [recipient]}, config, [recipient])

    def _online(self, db, config):
        from player_monitoring_routes import _as_datetime
        catalog = self.catalog()
        aliases = {alias: key for key, server in catalog.items() for alias in server.get("identity_server_ids", [server["server_id"]])}
        rows = db.execute(text("SELECT s.steam_id,s.server_id,s.connected_at,s.last_seen_at,g.player_name,g.character_id,g.tribe_id,g.tribe_name "
            "FROM game_player_sessions s LEFT JOIN game_players g ON g.steam_id=s.steam_id "
            "WHERE s.disconnected_at IS NULL AND s.last_seen_at>=:since ORDER BY s.last_seen_at DESC,s.session_id"),
            {"since": self.clock() - timedelta(seconds=config["PresenceTtlSeconds"])}).mappings().all()
        rows = [row for row in rows if _STEAM.fullmatch(str(row["steam_id"] or ""))]
        identities = self._ids(db, [str(row["steam_id"]) for row in rows])
        result = {}
        for row in rows:
            steam = str(row["steam_id"])
            key = aliases.get(row["server_id"])
            if steam in result or not key or not config["Maps"].get(key, {}).get("Enabled", False):
                continue
            identity = identities[steam]
            result[steam] = {"steam_id": steam, "public_id": str(identity["public_id"]), "server_key": key,
                "name": row["player_name"] or steam, "tribe_name": row["tribe_name"] or "",
                "tribe_id": row["tribe_id"] or "", "connected_at": _as_datetime(row["connected_at"]),
                "map": config["Maps"].get(key, {}).get("Label") or catalog[key].get("label") or key}
        return result

    def _actor_style(self, db, config, actor):
        licenses = actor.get("active_licenses")
        if licenses is None:
            licenses = self.license_provider(db, [actor["steam_id"]]).get(actor["steam_id"], [])
        tag, colors = select_style(config, actor, {entry["group"] for entry in licenses})
        return tag, colors

    def _process(self, db, event, actor, server_key, server, config):
        event_id = str(uuid.UUID(str(event.get("event_id"))))
        if not self._event(db, event_id):
            return
        if config["DisableChat"]:
            return self._notice(db, event_id, actor["steam_id"], "Disabled", config)
        kind = str(event.get("kind", ""))
        try:
            body = clean_text(event.get("body"), config["MaxMessageLength"])
        except ValueError:
            return self._notice(db, event_id, actor["steam_id"], "TooLong", config)
        steam = actor["steam_id"]
        identity = self._id(db, steam)
        if not body and kind not in {"online", "joinleave"}:
            return self._notice(db, event_id, steam, "PrivateUsage" if kind == "pm" else "ReplyUsage" if kind == "reply" else "EmptyMessage", config)
        if kind == "joinleave":
            if not config["CrossMapNotifications"]["Enabled"]:
                return self._notice(db, event_id, steam, "Disabled", config)
            enabled = not identity["notifications"]
            db.execute(update(PLAYERS).where(PLAYERS.c.steam_id == steam).values(notifications=enabled))
            return self._notice(db, event_id, steam, "NotificationsOn" if enabled else "NotificationsOff", config)
        if kind == "online":
            policy = config["OnlinePlayersCommand"]
            if not policy["Enabled"]:
                return self._notice(db, event_id, steam, "Disabled", config)
            groups = set(actor["groups"]) | {"Default"}
            if policy["RestrictCommandToPermissions"] and not groups.intersection(policy["RestrictCommandToPermissions"]):
                return self._notice(db, event_id, steam, "NoPermission", config)
            players = list(self._online(db, config).values())
            players.sort(key=lambda player: int(player["public_id"]))
            pages = max(1, math.ceil(len(players) / policy["AmountPerPage"]))
            try:
                page = max(1, min(pages, int(body or "1")))
            except ValueError:
                page = 1
            lines = [config["ClusterName"] + " · " + config["Messages"]["OnlineHeader"].format(total=len(players), pagina=page, total_paginas=pages)]
            for player in players[(page - 1) * policy["AmountPerPage"]:page * policy["AmountPerPage"]]:
                seconds = max(0, int((self.clock() - player["connected_at"]).total_seconds())) if player["connected_at"] else 0
                lines.append(config["Messages"]["OnlinePlayer"].format(jogador=display_name(player["name"]), id=player["public_id"],
                    tribo=f" [{display_name(player['tribe_name'])}]" if policy["ShowTribes"] and player["tribe_name"] else "",
                    mapa=f" · {display_name(player['map'])}" if groups.intersection(policy["OnlyShowMapToGroups"]) else "",
                    tempo=f" · conectado há {seconds // 3600}h{seconds // 60 % 60:02d}" if policy["ShowOnlineTime"] else ""))
            return self._message(db, event_id, "online", "system", server_key, steam,
                {"text": "\n".join(lines), "scale": policy["DisplayScale"], "duration": policy["DisplayTime"]}, config, [steam])
        if kind in {"pm", "reply"}:
            if not config["PrivateMessages"]["Enabled"]:
                return self._notice(db, event_id, steam, "Disabled", config)
            target = None
            if kind == "pm":
                number, separator, body = body.partition(" ")
                if not separator:
                    return self._notice(db, event_id, steam, "PrivateUsage", config)
                if re.fullmatch(r"[1-9][0-9]{0,11}", number):
                    target = db.execute(select(PLAYERS).where(PLAYERS.c.public_id == int(number))).mappings().first()
            elif identity["reply_to"]:
                target = self._id(db, identity["reply_to"])
            else:
                return self._notice(db, event_id, steam, "NoConversation", config)
            if not target:
                return self._notice(db, event_id, steam, "InvalidId", config)
            if target["steam_id"] == steam:
                return self._notice(db, event_id, steam, "SelfMessage", config)
            online = self._online(db, config)
            recipient = online.get(target["steam_id"])
            if not recipient:
                return self._notice(db, event_id, steam, "Offline", config)
            if config["DisableCrossServerChat"] and recipient["server_key"] != server_key:
                return self._notice(db, event_id, steam, "Disabled", config)
            body = censor(body, config)
            if not body.strip():
                return self._notice(db, event_id, steam, "EmptyMessage", config)
            for participant in sorted({steam, target["steam_id"]}):
                db.execute(select(PLAYERS.c.public_id).where(PLAYERS.c.steam_id == participant).with_for_update()).first()
            db.execute(update(PLAYERS).where(PLAYERS.c.steam_id == steam).values(reply_to=target["steam_id"]))
            return self._message(db, event_id, "pm", "game", server_key, steam,
                {"sender": steam, "target": target["steam_id"], "from_text": config["Messages"]["PrivateFrom"].format(
                    jogador=display_name(actor["name"]), id=identity["public_id"], mensagem=body),
                 "to_text": config["Messages"]["PrivateTo"].format(destinatario=display_name(recipient["name"]), id=target["public_id"], mensagem=body)},
                config, [steam, target["steam_id"]])
        if kind != "global":
            raise ValueError("Tipo de mensagem inválido.")
        if not config["UseCrossChat"]:
            return self._notice(db, event_id, steam, "Disabled", config)
        immune = config["AdminImmuneToMuteAndSpamDelay"] and set(actor["groups"]).intersection(config["AdminGroups"])
        # Lock da identidade serializa o intervalo de spam entre mapas/processos.
        row = db.execute(select(PLAYERS).where(PLAYERS.c.steam_id == steam).with_for_update()).mappings().one()
        remaining = config["GlobalChatSpamDelaySec"] - (self.clock() - row["last_global_at"]).total_seconds() if row["last_global_at"] else 0
        if remaining > 0 and not immune:
            return self._notice(db, event_id, steam, "Spam", config, segundos=max(1, math.ceil(remaining)))
        db.execute(update(PLAYERS).where(PLAYERS.c.steam_id == steam).values(last_global_at=self.clock()))
        tag, colors = self._actor_style(db, config, actor)
        label = config["Maps"].get(server_key, {}).get("Label") or server.get("label") or server_key
        colors = {**colors, "Map": config["Maps"].get(server_key, {}).get("Color", colors["Map"])}
        rendered = format_global(config, actor, str(identity["public_id"]), label, body, tag=tag, colors=colors)
        rendered["discord_plain"] = format_global({**config, "ShowMapName": config["Discord"]["ShowMap"]}, actor,
            str(identity["public_id"]), label, rendered["body"], tag=tag, colors=colors)["plain"]
        rendered["local_rich"] = format_global({**config, "ShowMapName": False}, actor, str(identity["public_id"]), label,
            rendered["body"], tag=tag, colors=colors)["rich"] if config["HideServerTagOnLocal"] else rendered["rich"]
        own_colors = colors if colors["OverrideGraySelfNameColor"] else {**colors, "Name": "#999999FF"}
        rendered["own_rich"] = format_global(config, actor, str(identity["public_id"]), label, rendered["body"], tag=tag, colors=own_colors)["rich"]
        rendered["own_local_rich"] = format_global({**config, "ShowMapName": False}, actor, str(identity["public_id"]), label,
            rendered["body"], tag=tag, colors=own_colors)["rich"] if config["HideServerTagOnLocal"] else rendered["own_rich"]
        rendered.update({"source_server_key": server_key, "sender_steam": steam})
        return self._message(db, event_id, "global", "game", server_key, steam, rendered, config)

    def _sync_players(self, db, server_key, server, boot, players, config, previous):
        now = self.clock()
        prefix = "ca-" + boot + "-"
        existing = db.execute(text("SELECT s.session_id,s.steam_id,s.connected_at,g.player_name FROM game_player_sessions s LEFT JOIN game_players g ON g.steam_id=s.steam_id WHERE s.server_id=:server AND s.session_id LIKE :prefix AND s.disconnected_at IS NULL"),
                              {"server": server["server_id"], "prefix": prefix + "%"}).mappings().all()
        current = {player["session_id"] for player in players.values()}
        for row in existing:
            if row["session_id"] not in current:
                identity = self._id(db, row["steam_id"])
                ingest_session_event(db, {"steam_id": row["steam_id"], "server_id": server["server_id"], "session_id": row["session_id"],
                    "player_name": "", "character_id": "", "tribe_id": "", "tribe_name": ""}, "disconnect", now=now, update_profile=False)
                self._notification(db, f"leave:{row['session_id']}", "Leave", server_key, server, str(identity["public_id"]), row["player_name"] or row["steam_id"], config)
        last_monitor = previous["last_monitor_at"] if previous else None
        existing_ids = {row["session_id"] for row in existing}
        for steam, player in players.items():
            fresh = player["session_id"] not in existing_ids
            if not fresh and last_monitor and (now - last_monitor).total_seconds() < 10:
                continue
            result, code = ingest_session_event(db, {"steam_id": steam, "server_id": server["server_id"], "session_id": player["session_id"],
                "player_name": player["name"], "character_id": str(player.get("character_id", "")),
                "tribe_id": str(player.get("tribe_id", "")), "tribe_name": player.get("tribe_name", "")}, "connect" if fresh else "heartbeat", now=now, authoritative_profile=True)
            if code >= 400:
                raise ValueError("Snapshot de sessão inválido.")
            if fresh:
                identity = self._id(db, steam)
                self._notification(db, f"join:{player['session_id']}", "Join", server_key, server, str(identity["public_id"]), player["name"], config)

    def _notification(self, db, event_id, kind, server_key, server, public_id, name, config):
        if not config["CrossMapNotifications"]["Enabled"] or not self._event(db, event_id):
            return
        label = config["Maps"].get(server_key, {}).get("Label") or server.get("label") or server_key
        self._message(db, event_id, "notification", "system", server_key, None,
            {"event": kind.lower(), "source_server_key": server_key, "text": config["Messages"][kind].format(
                jogador=display_name(name), id=public_id, mapa=display_name(label))}, config)

    def _deliver(self, db, key, local_players, cursor, config, identities):
        now = self.clock()
        rows = db.execute(select(MESSAGES_TABLE).where(MESSAGES_TABLE.c.seq > cursor, MESSAGES_TABLE.c.expires_at > now)
                          .order_by(MESSAGES_TABLE.c.seq).limit(200)).mappings().all()
        result = []
        for row in rows:
            cursor = max(cursor, row["seq"])
            if row["kind"] not in {"global", "notification"}:
                continue
            if config["DisableCrossServerChat"] and row["origin"] in {"game", "system"} and row["server_key"] != key:
                continue
            data = json.loads(row["payload_json"])
            if row["kind"] == "notification":
                recipients = [steam for steam in local_players if identities[steam]["notifications"]]
                if not recipients:
                    continue
                data["recipients"] = recipients
            result.append({"event_id": row["event_id"], "seq": row["seq"], "kind": row["kind"], **data})
        online = self._online(db, config)
        local = [steam for steam in local_players if online.get(steam, {}).get("server_key") == key]
        if local:
            private = db.execute(select(DELIVERIES, MESSAGES_TABLE.c.kind, MESSAGES_TABLE.c.payload_json).join(
                MESSAGES_TABLE, DELIVERIES.c.event_id == MESSAGES_TABLE.c.event_id).where(
                DELIVERIES.c.recipient.in_(local), DELIVERIES.c.acked_at.is_(None), DELIVERIES.c.expires_at > now,
                or_(DELIVERIES.c.lease_until.is_(None), DELIVERIES.c.lease_until <= now, DELIVERIES.c.lease_owner == key))
                .limit(100)).mappings().all()
            for row in private:
                claimed = db.execute(update(DELIVERIES).where(DELIVERIES.c.delivery_id == row["delivery_id"],
                    or_(DELIVERIES.c.lease_until.is_(None), DELIVERIES.c.lease_until <= now, DELIVERIES.c.lease_owner == key)).values(
                        lease_owner=key, lease_until=now + timedelta(seconds=3)))
                if not claimed.rowcount:
                    continue
                payload = json.loads(row["payload_json"])
                body = payload.get("text", "")
                if row["kind"] == "pm":
                    body = payload["to_text"] if row["recipient"] == payload["sender"] else payload["from_text"]
                result.append({"event_id": row["event_id"], "delivery_id": row["delivery_id"], "kind": row["kind"],
                               "recipients": [row["recipient"]], "text": body,
                               "scale": payload.get("scale", 0.5), "duration": payload.get("duration", 10)})
        return result, cursor

    def exchange(self, body):
        key, boot = str(body.get("server_key", "")), str(body.get("boot_id", ""))
        catalog = self.catalog()
        if key not in catalog or not _BOOT.fullmatch(boot):
            raise ValueError("Instância não cadastrada ou identificador de inicialização inválido.")
        if not isinstance(body.get("players", []), list) or len(body.get("players", [])) > 500:
            raise ValueError("Snapshot de jogadores inválido.")
        players = {}
        for raw in body.get("players", []):
            steam, session = str(raw.get("steam_id", "")), str(raw.get("session_id", ""))
            if not _STEAM.fullmatch(steam) or not _SESSION.fullmatch(session) or not session.startswith("ca-" + boot + "-"):
                raise ValueError("Identidade ou sessão inválida no snapshot.")
            groups = raw.get("groups", [])
            if not isinstance(groups, list) or len(groups) > 100 or any(not isinstance(x, str) or len(x) > 80 for x in groups):
                raise ValueError("Grupos inválidos no snapshot.")
            players[steam] = {"steam_id": steam, "session_id": session, "name": clean_text(raw.get("name"), 128),
                "steam_name": clean_text(raw.get("steam_name"), 128), "tribe_name": clean_text(raw.get("tribe_name"), 128),
                "tribe_id": str(raw.get("tribe_id") or ""), "character_id": str(raw.get("character_id") or ""), "groups": groups}
        events, acks = body.get("events", []), body.get("acks", [])
        if not isinstance(events, list) or len(events) > 50 or not isinstance(acks, list) or len(acks) > 200:
            raise ValueError("Lote fora dos limites permitidos.")
        db = self.database()
        try:
            shared = self.load_config(db)
            config, server = shared["config"], catalog[key]
            observer = bool(body.get("observer", True)) or not config["Maps"].get(key, {}).get("Enabled", False) or config["DisableChat"]
            previous = db.execute(select(INSTANCES).where(INSTANCES.c.server_key == key).with_for_update()).mappings().first()
            if previous and previous["boot_id"] != boot and previous["last_seen_at"] > self.clock() - timedelta(seconds=config["PresenceTtlSeconds"]):
                raise ValueError("Outra instância com a mesma ServerKey ainda está ativa.")
            if not observer:
                self._sync_players(db, key, server, boot, players, config, previous)
            identities = self._ids(db, players)
            licenses = self.license_provider(db, list(players)) if players else {}
            for steam, actor in players.items():
                actor["active_licenses"] = licenses.get(steam, [])
            accepted, rejected = [], []
            if not observer:
                # Confirmações precedem comandos: /r enviado junto ao ACK da
                # mensagem recém-exibida deve responder ao interlocutor correto.
                for ack in acks:
                    recipient = str(ack.get("recipient", ""))
                    if recipient not in players:
                        continue
                    acknowledged = db.execute(update(DELIVERIES).where(DELIVERIES.c.delivery_id == str(ack.get("delivery_id", "")),
                        DELIVERIES.c.recipient == recipient, DELIVERIES.c.lease_owner == key,
                        DELIVERIES.c.acked_at.is_(None), DELIVERIES.c.expires_at > self.clock()).values(acked_at=self.clock()))
                    if acknowledged.rowcount:
                        message = db.execute(select(MESSAGES_TABLE.c.sender_steam, MESSAGES_TABLE.c.payload_json).join(
                            DELIVERIES, DELIVERIES.c.event_id == MESSAGES_TABLE.c.event_id).where(
                            DELIVERIES.c.delivery_id == str(ack.get("delivery_id", "")), MESSAGES_TABLE.c.kind == "pm")).first()
                        if message and json.loads(message[1]).get("target") == recipient:
                            db.execute(update(PLAYERS).where(PLAYERS.c.steam_id == recipient).values(reply_to=message[0]))
                for event in events:
                    actor = players.get(str(event.get("steam_id", "")))
                    try:
                        if actor is None:
                            raise ValueError("O remetente não pertence ao snapshot desta instância.")
                        self._process(db, event, actor, key, server, config)
                        accepted.append(str(event["event_id"]))
                    except (ValueError, TypeError, KeyError) as failure:
                        rejected.append({"event_id": str(event.get("event_id", ""))[:64], "reason": str(failure)[:200]})
            cursor = max(0, int(body.get("cursor", 0)))
            if previous is None and not body.get("resume", False):
                cursor = int(db.execute(select(func.max(MESSAGES_TABLE.c.seq))).scalar() or 0)
            identities = self._ids(db, players)
            deliveries, cursor = self._deliver(db, key, players, cursor, config, identities) if not observer else ([], cursor)
            values = {"boot_id": boot, "last_seen_at": self.clock() - timedelta(seconds=config["PresenceTtlSeconds"] + 1) if body.get("stopping") else self.clock(), "revision": max(0, int(body.get("revision", 0))),
                      "plugin_version": str(body.get("plugin_version", ""))[:32], "observer": observer,
                      "last_error": "" if not rejected else "Há eventos inválidos no último lote.", "player_count": len(players),
                      "last_monitor_at": self.clock() if not previous or not previous["last_monitor_at"] or (self.clock() - previous["last_monitor_at"]).total_seconds() >= 10 else previous["last_monitor_at"]}
            if previous:
                db.execute(update(INSTANCES).where(INSTANCES.c.server_key == key).values(**values))
            else:
                db.execute(insert(INSTANCES).values(server_key=key, **values))
            def license_cache(steam):
                result = []
                for entry in licenses.get(steam, []):
                    expiry = entry.get("expires_at")
                    if expiry:
                        parsed = datetime.fromisoformat(str(expiry).replace("Z", "+00:00"))
                        expiry = calendar.timegm(parsed.utctimetuple())
                    result.append({"group": entry["group"], "expires_epoch": expiry})
                return result
            response = {"ok": True, "revision": shared["revision"], "observer": observer, "cursor": cursor,
                "config": config if shared["revision"] != body.get("revision") else None, "accepted": accepted, "rejected": rejected,
                "players": {steam: {"public_id": str(identity["public_id"]), "notifications": identity["notifications"],
                            "licenses": license_cache(steam)} for steam, identity in identities.items()}, "deliveries": deliveries}
            self._cleanup(db, config)
            db.commit()
            return response
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _cleanup(self, db, config):
        if time.monotonic() - self._cleanup_at < 10:
            return
        now = self.clock()
        expired = db.execute(select(DELIVERIES.c.event_id, DELIVERIES.c.recipient, MESSAGES_TABLE.c.sender_steam).join(
            MESSAGES_TABLE, DELIVERIES.c.event_id == MESSAGES_TABLE.c.event_id).where(DELIVERIES.c.acked_at.is_(None),
            DELIVERIES.c.expires_at <= now, MESSAGES_TABLE.c.kind == "pm")).all()
        for event_id, recipient, sender in expired:
            if recipient != sender:
                failure_id = "fail:" + event_id
                if self._event(db, failure_id):
                    self._notice(db, failure_id, sender, "DeliveryFailed", config)
        db.execute(delete(DELIVERIES).where(DELIVERIES.c.expires_at <= now))
        db.execute(delete(MESSAGES_TABLE).where(MESSAGES_TABLE.c.expires_at <= now))
        db.execute(delete(EVENTS).where(EVENTS.c.expires_at <= now))
        db.execute(update(MESSAGES_TABLE).where(MESSAGES_TABLE.c.discord_state == "sending",
            MESSAGES_TABLE.c.claimed_at < now - timedelta(seconds=30)).values(discord_state="uncertain"))
        self._cleanup_at = time.monotonic()

    def ingest_discord(self, message_id, author_id, author_name, body, *, lumo=False):
        db = self.database()
        try:
            config = self.load_config(db)["config"]
            if config["DisableChat"] or not config["UseCrossChat"] or not config["Discord"]["Enabled"] or not config["Discord"]["AllowDiscordToIngame"]:
                return False
            event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "arkland-discord:" + str(message_id)))
            if not self._event(db, event_id):
                db.commit()
                return False
            actor = {"name": "Lumo" if lumo else clean_text(author_name, 128), "tribe_name": "", "groups": []}
            public_id, tag, colors = None, None, config["Colors"]
            if not lumo:
                linked = self.discord_identity(db, str(author_id))
                if linked:
                    actor.update(linked)
                    public_id = str(self._id(db, actor["steam_id"])["public_id"])
                    tag, colors = self._actor_style(db, config, actor)
            # Texto vindo do Discord nunca é interpretado como /pm, RCON ou comando.
            rendered = format_global(config, actor, public_id, "Discord", body, origin="lumo" if lumo else "discord", tag=tag, colors=colors)
            self._message(db, event_id, "global", "lumo" if lumo else "discord", "discord", actor.get("steam_id"), rendered, config)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def claim_discord(self, owner):
        db = self.database()
        try:
            config = self.load_config(db)["config"]
            if config["DisableChat"] or not config["Discord"]["Enabled"] or not any(m.get("Enabled") for m in config["Maps"].values()):
                return None
            now = self.clock()
            claimed = db.execute(update(LEADER).where(LEADER.c.id == 1, or_(LEADER.c.until_at.is_(None),
                LEADER.c.until_at <= now, LEADER.c.owner == owner)).values(owner=owner, until_at=now + timedelta(seconds=10)))
            if not claimed.rowcount:
                db.rollback()
                return None
            row = db.execute(select(MESSAGES_TABLE).where(MESSAGES_TABLE.c.kind == "global", MESSAGES_TABLE.c.origin == "game",
                MESSAGES_TABLE.c.discord_state == "pending", MESSAGES_TABLE.c.expires_at > now).order_by(MESSAGES_TABLE.c.seq).limit(1).with_for_update()).mappings().first()
            if row:
                db.execute(update(MESSAGES_TABLE).where(MESSAGES_TABLE.c.seq == row["seq"], MESSAGES_TABLE.c.discord_state == "pending").values(
                    discord_state="sending", discord_owner=owner, claimed_at=now))
            db.commit()
            return {**row, "payload": json.loads(row["payload_json"])} if row else None
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def confirm_discord(self, seq, owner, message_id=None):
        db = self.database()
        try:
            db.execute(update(MESSAGES_TABLE).where(MESSAGES_TABLE.c.seq == seq, MESSAGES_TABLE.c.discord_owner == owner,
                MESSAGES_TABLE.c.discord_state == "sending").values(discord_state="sent" if message_id else "uncertain", discord_id=str(message_id) if message_id else None))
            db.commit()
        finally:
            db.close()

    def relay_context(self, seq):
        db = self.database()
        try:
            row = db.execute(select(MESSAGES_TABLE).where(MESSAGES_TABLE.c.seq == seq, MESSAGES_TABLE.c.origin == "game",
                MESSAGES_TABLE.c.kind == "global", MESSAGES_TABLE.c.discord_state.in_(["sending", "sent"]),
                MESSAGES_TABLE.c.expires_at > self.clock())).mappings().first()
            return {"event_id": row["event_id"], "steam_id": row["sender_steam"], **json.loads(row["payload_json"])} if row else None
        finally:
            db.close()

    def admin_snapshot(self):
        db = self.database()
        try:
            shared = self.load_config(db, force=True)
            instances = {row["server_key"]: dict(row) for row in db.execute(select(INSTANCES)).mappings()}
            maps = []
            for key, server in self.catalog().items():
                instance = instances.get(key)
                connected = bool(instance and instance["last_seen_at"] > self.clock() - timedelta(seconds=shared["config"]["PresenceTtlSeconds"]))
                maps.append({"server_key": key, "label": server.get("label") or key, "connected": connected,
                    "instance": {k: v.isoformat() + "Z" if isinstance(v, datetime) else v for k, v in instance.items()} if instance else None,
                    "status": "Observação" if connected and instance["observer"] else "Sincronizado" if connected and instance["revision"] == shared["revision"] else "Configuração pendente" if connected else "Sem comunicação recente"})
            revisions = db.execute(select(REVISIONS.c.revision, REVISIONS.c.changed_at, REVISIONS.c.actor).order_by(REVISIONS.c.revision.desc()).limit(30)).mappings().all()
            delivery_states = dict(db.execute(select(MESSAGES_TABLE.c.discord_state, func.count()).group_by(MESSAGES_TABLE.c.discord_state)).all())
            return {**shared, "maps": maps, "revisions": [{**row, "changed_at": row["changed_at"].isoformat() + "Z"} for row in revisions],
                    "discord_deliveries": delivery_states,
                    "validation": "Em desenvolvimento; testes automatizados não substituem a homologação em jogo."}
        finally:
            db.close()

    def discover_tags(self):
        candidates = [{"Key": "staff", "Label": "STAFF", "Kind": "admin", "Priority": 0, "PermissionGroups": ["STAFF"], "Color": "#FF6060FF", "Approved": False, "Enabled": False},
                      {"Key": "moderador", "Label": "Moderador", "Kind": "admin", "Priority": 1, "PermissionGroups": ["Mod"], "Color": "#60CFFFFF", "Approved": False, "Enabled": False}]
        reference = ["spirit", "chaos", "fey", "demonic", "celestial", "corrupted", "elder", "buffoon", "primal_tek", "omega", "fabled", "apex", "elemental", "alpha", "toxic"]
        for item in self.license_catalog():
            group = str(item["group"])
            folded = group.lower().removeprefix("l_").removeprefix("licenca_")
            candidates.append({"Key": "license:" + group, "Label": folded.upper()[:40], "Kind": "license",
                "Priority": 10 + reference.index(folded) if folded in reference else 1000 + len(candidates),
                "LicenseGroups": [group], "PermissionGroups": [], "Color": "#FFD700FF", "Approved": False, "Enabled": False})
        return candidates

    def rollback_config(self, revision, expected_revision, actor):
        db = self.database()
        try:
            value = db.execute(select(REVISIONS.c.config_json).where(REVISIONS.c.revision == revision)).scalar()
            if value is None:
                raise ValueError("Revisão não encontrada.")
        finally:
            db.close()
        return self.publish_config(json.loads(value), expected_revision, actor)
