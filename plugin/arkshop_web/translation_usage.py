"""Database-backed monthly Azure Translator usage accounting and cap."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from threading import Lock
from sqlalchemy import text

_logger = logging.getLogger(__name__)
_schema_lock = Lock()
_ready_engines: set[str] = set()


class TranslationUsage:
    def __init__(self, engine):
        self.engine = engine
        self._ensure_schema()

    def _ensure_schema(self):
        key = str(self.engine.url)
        with _schema_lock:
            if key in _ready_engines:
                return
            if self.engine.dialect.name == "sqlite":
                ddl = """
                    CREATE TABLE IF NOT EXISTS azure_translation_usage (
                      period CHAR(7) PRIMARY KEY,
                      request_count INTEGER NOT NULL DEFAULT 0,
                      character_count BIGINT NOT NULL DEFAULT 0,
                      success_count INTEGER NOT NULL DEFAULT 0,
                      failure_count INTEGER NOT NULL DEFAULT 0,
                      last_error VARCHAR(64) NULL,
                      last_request_id VARCHAR(128) NULL,
                      last_source_language VARCHAR(12) NULL,
                      last_target_language VARCHAR(12) NULL,
                      last_duration_ms INTEGER NULL,
                      last_translation_at DATETIME NULL,
                      alert_level INTEGER NOT NULL DEFAULT 0,
                      updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """
            else:
                ddl = """
                    CREATE TABLE IF NOT EXISTS azure_translation_usage (
                      period CHAR(7) PRIMARY KEY,
                      request_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
                      character_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
                      success_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
                      failure_count BIGINT UNSIGNED NOT NULL DEFAULT 0,
                      last_error VARCHAR(64) NULL,
                      last_request_id VARCHAR(128) NULL,
                      last_source_language VARCHAR(12) NULL,
                      last_target_language VARCHAR(12) NULL,
                      last_duration_ms INT UNSIGNED NULL,
                      last_translation_at DATETIME(3) NULL,
                      alert_level SMALLINT UNSIGNED NOT NULL DEFAULT 0,
                      updated_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
                        ON UPDATE CURRENT_TIMESTAMP(3)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            with self.engine.begin() as conn:
                conn.execute(text(ddl))
            _ready_engines.add(key)

    @staticmethod
    def _period() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def _insert_period(self, conn, period: str):
        if self.engine.dialect.name == "sqlite":
            conn.execute(text("INSERT INTO azure_translation_usage (period) VALUES (:p) ON CONFLICT(period) DO NOTHING"), {"p": period})
        else:
            conn.execute(text("INSERT IGNORE INTO azure_translation_usage (period) VALUES (:p)"), {"p": period})

    def reserve(self, characters: int, limit: int, configured_thresholds=None) -> tuple[bool, list[int], int, str]:
        characters = max(0, int(characters))
        period = self._period()
        thresholds: list[int] = []
        with self.engine.begin() as conn:
            self._insert_period(conn, period)
            row = conn.execute(text(
                "SELECT character_count, alert_level FROM azure_translation_usage WHERE period=:p" +
                (" FOR UPDATE" if self.engine.dialect.name != "sqlite" else "")
            ), {"p": period}).mappings().first()
            if not row:
                raise RuntimeError("usage period row missing")
            current = int(row["character_count"] or 0)
            if limit > 0 and current + characters > limit:
                return False, [], current, period
            conn.execute(text("""
                UPDATE azure_translation_usage
                SET request_count=request_count+1, character_count=character_count+:n
                WHERE period=:p
            """), {"n": characters, "p": period})
            updated = current + characters
            previous_alert = int(row["alert_level"] or 0)
            if limit > 0:
                from translation_service import alert_thresholds
                thresholds = [v for v in alert_thresholds(configured_thresholds)
                              if v > previous_alert and updated * 100 >= limit * v]
                if thresholds:
                    conn.execute(text("UPDATE azure_translation_usage SET alert_level=:level WHERE period=:p"),
                                 {"level": max(thresholds), "p": period})
        for threshold in thresholds:
            _logger.warning("[Translation] provider=azure monthly_usage_alert=%d%% period=%s characters=%d limit=%d",
                            threshold, period, updated, limit)
        return True, thresholds, updated, period

    def finish(self, event: dict, period: str | None = None) -> None:
        period = period or self._period()
        reserved = max(0, int(event.get("reserved_characters") or 0))
        metered = event.get("metered_characters")
        actual = max(0, int(metered)) if metered is not None else reserved
        success = bool(event.get("success"))
        error = event.get("error_code")
        with self.engine.begin() as conn:
            self._insert_period(conn, period)
            conn.execute(text("""
                UPDATE azure_translation_usage SET
                  character_count=MAX(0, character_count + :delta),
                  success_count=success_count+:success,
                  failure_count=failure_count+:failure,
                  last_error=:error,
                  last_request_id=:request_id,
                  last_source_language=:source,
                  last_target_language=:target,
                  last_duration_ms=:duration,
                  last_translation_at=:now
                WHERE period=:p
            """ if self.engine.dialect.name == "sqlite" else """
                UPDATE azure_translation_usage SET
                  character_count=GREATEST(0, character_count + :delta),
                  success_count=success_count+:success,
                  failure_count=failure_count+:failure,
                  last_error=:error,
                  last_request_id=:request_id,
                  last_source_language=:source,
                  last_target_language=:target,
                  last_duration_ms=:duration,
                  last_translation_at=:now
                WHERE period=:p
            """), {
                "delta": actual - reserved, "success": int(success), "failure": int(not success),
                "error": error, "request_id": event.get("request_id"),
                "source": event.get("source_language"), "target": event.get("target_language"),
                "duration": int(event.get("duration_ms") or 0),
                "now": datetime.now(timezone.utc).replace(tzinfo=None), "p": period,
            })

    def snapshot(self, limit: int = 0) -> dict:
        period = self._period()
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM azure_translation_usage WHERE period=:p"), {"p": period}).mappings().first()
        row = dict(row) if row else {}
        characters = int(row.get("character_count") or 0)
        last_translation_at = row.get("last_translation_at")
        if hasattr(last_translation_at, "isoformat"):
            last_translation_at = last_translation_at.isoformat()
        elif last_translation_at is not None:
            last_translation_at = str(last_translation_at)
        return {
            "period": period,
            "requests": int(row.get("request_count") or 0),
            "characters": characters,
            "successful": int(row.get("success_count") or 0),
            "failed": int(row.get("failure_count") or 0),
            "limit": int(limit or 0),
            "limit_configured": int(limit or 0) > 0,
            "usage_percent": round((characters * 100.0 / limit), 2) if limit else None,
            "last_error": row.get("last_error"),
            "last_request_id": row.get("last_request_id"),
            "last_source_language": row.get("last_source_language"),
            "last_target_language": row.get("last_target_language"),
            "last_duration_ms": row.get("last_duration_ms"),
            "last_translation_at": last_translation_at,
        }
