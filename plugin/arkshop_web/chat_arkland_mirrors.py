"""Fila durável de cópia e remoção dos originais do canal público de chat."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, Column, DateTime, Index, String, Table, delete, func, or_, select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


def define_mirrors(meta, json_type):
    table = Table("chat_arkland_discord_sources", meta,
        Column("source_id", String(32), primary_key=True),
        Column("guild_id", String(32), nullable=False), Column("channel_id", String(32), nullable=False),
        Column("author_id", String(32), nullable=False), Column("lumo", Boolean, nullable=False),
        Column("snapshot_json", json_type, nullable=False), Column("state", String(16), nullable=False),
        Column("copy_ids_json", json_type, nullable=False), Column("owner", String(40)),
        Column("created_at", DateTime, nullable=False), Column("updated_at", DateTime, nullable=False),
        Column("claimed_at", DateTime), Column("retry_at", DateTime),
        Column("last_error", String(80), nullable=False))
    Index("ix_ca_sources_work", table.c.state, table.c.retry_at, table.c.created_at)
    return table


class DiscordMirrorStore:
    def __init__(self, hub, table, leader):
        self.hub, self.table, self.leader = hub, table, leader

    @staticmethod
    def _row(row):
        return {**row, "snapshot": json.loads(row["snapshot_json"]),
                "copy_ids": json.loads(row["copy_ids_json"])} if row else None

    def capture(self, source_id, guild_id, channel_id, author_id, author_name, body, *,
                lumo=False, attachments=(), stickers=(), occurred_at=None, history=False):
        for value in (source_id, guild_id, channel_id, author_id):
            if not re.fullmatch(r"[0-9]{1,32}", str(value)):
                raise ValueError("Identidade Discord inválida.")
        db = self.hub.database()
        try:
            existing = db.execute(select(self.table).where(self.table.c.source_id == str(source_id))).mappings().first()
            if existing:
                return self._row(existing)  # A primeira versão capturada é imutável.
            config = self.hub.load_config(db)["config"]
            if config["DisableChat"] or not config["Discord"]["Enabled"]:
                return None
            if len(str(body)) > 32000 or len(attachments) > 10 or len(stickers) > 3:
                raise ValueError("Conteúdo não pode ser copiado integralmente.")
            when = None
            if occurred_at:
                when = datetime.fromisoformat(str(occurred_at).replace("Z", "+00:00"))
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
            rendered = self.hub.render_discord(db, config, author_id, author_name, body,
                lumo=lumo, limit=32000, when=when, immutable_identity=True)
            snapshot = {"author_name": str(author_name), "display_name": rendered["_identity_name"], "body": rendered["body"],
                "discord_plain": rendered["plain"], "attachments": list(attachments),
                "stickers": list(stickers), "history": bool(history),
                "game_allowed": bool(config["UseCrossChat"] and config["Discord"]["AllowDiscordToIngame"])}
            chunks, remaining = [], rendered["body"]
            maximum = config["MaxMessageLength"]
            while remaining:
                cut = min(maximum, len(remaining))
                if cut < len(remaining):
                    space = remaining.rfind(" ", 0, cut)
                    if space > cut // 2:
                        cut = space
                chunks.append(remaining[:cut])
                remaining = remaining[cut:].lstrip()
            snapshot["game_chunks"] = chunks
            now = self.hub.clock()
            values = dict(source_id=str(source_id), guild_id=str(guild_id), channel_id=str(channel_id),
                author_id=str(author_id), lumo=bool(lumo), snapshot_json=json.dumps(snapshot, ensure_ascii=False),
                state="pending", copy_ids_json="[]", created_at=now, updated_at=now, last_error="")
            query = mysql_insert(self.table).values(**values).prefix_with("IGNORE") if db.get_bind().dialect.name == "mysql" else sqlite_insert(self.table).values(**values).on_conflict_do_nothing(index_elements=["source_id"])
            db.execute(query)
            db.commit()
            return self._row(db.execute(select(self.table).where(self.table.c.source_id == str(source_id))).mappings().one())
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def forward_live(self, row):
        snapshot = row["snapshot"]
        if snapshot.get("history") or not snapshot.get("game_allowed", True):
            return
        config = self.hub.load_config()["config"]
        if row["created_at"] + timedelta(seconds=config["MessageTtlSeconds"]) < self.hub.clock():
            return  # Não reproduzir falas antigas no jogo depois de indisponibilidade.
        for index, part in enumerate(snapshot.get("game_chunks", [snapshot["body"]])):
            identity = row["source_id"] if index == 0 else row["source_id"] + ":part:" + str(index)
            self.hub.ingest_discord(identity, row["author_id"], snapshot["author_name"], part, lumo=row["lumo"])

    def claim(self, owner, guild_id, channel_id):
        db = self.hub.database()
        try:
            now = self.hub.clock()
            leader = db.execute(select(self.leader.c.owner).where(self.leader.c.id == 1,
                self.leader.c.owner == owner, self.leader.c.until_at > now)).first()
            if not leader:
                return None
            db.execute(update(self.table).where(self.table.c.state == "sending",
                self.table.c.claimed_at < now - timedelta(minutes=10)).values(state="uncertain", last_error="interrupted_copy", updated_at=now))
            db.execute(delete(self.table).where(self.table.c.state.in_(["deleted", "source_gone"]), self.table.c.updated_at < now - timedelta(days=1)))
            row = db.execute(select(self.table).where(self.table.c.guild_id == str(guild_id),
                self.table.c.channel_id == str(channel_id), self.table.c.state == "pending",
                or_(self.table.c.retry_at.is_(None), self.table.c.retry_at <= now))
                .order_by(self.table.c.created_at, self.table.c.source_id).limit(1).with_for_update()).mappings().first()
            if row:
                claimed = db.execute(update(self.table).where(self.table.c.source_id == row["source_id"],
                    self.table.c.state == "pending").values(state="sending", owner=owner, claimed_at=now, updated_at=now))
                if claimed.rowcount != 1:
                    row = None
            db.commit()
            return self._row(row)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def finish(self, source_id, owner, copy_ids, *, attempted=False, error=""):
        db = self.hub.database()
        try:
            copied = bool(copy_ids) and not error
            state = "copied" if copied else "uncertain" if attempted else "pending"
            now = self.hub.clock()
            result = db.execute(update(self.table).where(self.table.c.source_id == str(source_id),
                self.table.c.owner == owner, self.table.c.state == "sending").values(state=state,
                copy_ids_json=json.dumps(list(copy_ids)), last_error=str(error)[:80], updated_at=now,
                retry_at=None if copied else now + timedelta(seconds=30)))
            db.commit()
            return result.rowcount == 1
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def pending_deletion(self, guild_id, channel_id):
        db = self.hub.database()
        try:
            now = self.hub.clock()
            row = db.execute(select(self.table).where(self.table.c.state == "copied",
                self.table.c.guild_id == str(guild_id), self.table.c.channel_id == str(channel_id),
                or_(self.table.c.retry_at.is_(None), self.table.c.retry_at <= now))
                .order_by(self.table.c.created_at).limit(1)).mappings().first()
            return self._row(row)
        finally:
            db.close()

    def deleted(self, source_id, *, error=""):
        db = self.hub.database()
        try:
            now = self.hub.clock()
            db.execute(update(self.table).where(self.table.c.source_id == str(source_id), self.table.c.state == "copied")
                .values(state="copied" if error else "deleted", updated_at=now, last_error=str(error)[:80],
                        retry_at=now + timedelta(seconds=30) if error else None))
            db.commit()
        finally:
            db.close()

    def source_gone(self, source_id, owner):
        db = self.hub.database()
        try:
            db.execute(update(self.table).where(self.table.c.source_id == str(source_id),
                self.table.c.owner == owner, self.table.c.state == "sending")
                .values(state="source_gone", updated_at=self.hub.clock(), last_error=""))
            db.commit()
        finally:
            db.close()

    def stats(self, db):
        counts = dict(db.execute(select(self.table.c.state, func.count()).group_by(self.table.c.state)).all())
        issues = db.execute(select(self.table.c.source_id, self.table.c.guild_id, self.table.c.channel_id,
            self.table.c.state, self.table.c.last_error).where(self.table.c.last_error != "")
            .order_by(self.table.c.updated_at.desc()).limit(5)).mappings().all()
        return {"counts": counts, "errors": list(dict.fromkeys(row["last_error"] for row in issues)),
            "issues": [{"source_id": row["source_id"], "state": row["state"],
                "url": f"https://discord.com/channels/{row['guild_id']}/{row['channel_id']}/{row['source_id']}"} for row in issues]}
