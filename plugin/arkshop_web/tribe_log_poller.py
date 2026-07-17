"""Worker de polling do TribeLog.log → tribe_logs (Opção B / PROJETO_AREA_TRIBO).

Fontes (por mapa / server_id):
  1. Ficheiro local: {install_dir}/ShooterGame/Saved/Logs/TribeLog.log
     (descoberto via asm_servers.json / servers.json do ARKLAND Manager)
  2. remote_agent: GET /server/{id}/tribelog?offset=N (quando configurado)

Env:
  ARKSHOP_TRIBE_LOG_POLL_SECONDS — intervalo (default 30; 0 = desligado)
  ARKSHOP_TRIBE_LOG_REMOTE_URL   — base URL do remote_agent (opcional)
  ARKSHOP_TRIBE_LOG_REMOTE_TOKEN — Bearer token do remote_agent (opcional)
"""
from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("arkshop_web.tribe_log_poller")

_scheduler_thread: threading.Thread | None = None
_scheduler_stop = threading.Event()
_last_status: dict[str, Any] = {"runs": 0, "last_error": None, "servers": {}}

_TRIBELOG_REL = Path("ShooterGame") / "Saved" / "Logs" / "TribeLog.log"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _poll_interval_seconds() -> int:
    return max(0, _env_int("ARKSHOP_TRIBE_LOG_POLL_SECONDS", 30))


def find_tribe_log_path(install_dir: str) -> Path | None:
    if not install_dir:
        return None
    p = Path(install_dir) / _TRIBELOG_REL
    return p if p.is_file() else None


def discover_local_tribe_log_targets() -> list[dict[str, str]]:
    """Lista {server_id, install_dir} a partir do Manager local."""
    cfg_dir = Path(os.environ.get("APPDATA", "")) / "ARKLAND-ServerManager"
    if not cfg_dir.is_dir():
        return []

    out: list[dict[str, str]] = []
    seen: set[str] = set()

    def _add(item: dict[str, Any]) -> None:
        if not isinstance(item, dict):
            return
        install = str(item.get("install_dir") or "").strip()
        if not install:
            return
        sid = (
            str(item.get("shop_server_id") or "").strip()
            or str(item.get("name") or "").strip()
            or str(item.get("id") or "").strip()
        )
        if not sid or sid in seen:
            return
        if not find_tribe_log_path(install):
            return
        seen.add(sid)
        out.append({"server_id": sid, "install_dir": install})

    for fname in ("asm_servers.json", "servers.json"):
        path = cfg_dir / fname
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            items = raw if isinstance(raw, list) else []
            for item in items:
                _add(item)
        except Exception as exc:
            log.debug("discover %s: %s", path, exc)

    return out


def read_tribe_log_since(
    log_path: Path,
    *,
    since_offset: int = 0,
    max_bytes: int = 512_000,
) -> tuple[list[dict[str, Any]], int]:
    """Lê bytes novos do TribeLog.log a partir de since_offset.

    Retorna (linhas parseadas com file_offset, novo offset EOF).
    Se o ficheiro encolheu (rotação/wipe), reinicia do início.
    Na primeira leitura (offset 0) limita-se aos últimos max_bytes.
    """
    from tribe_log_parser import parse_tribe_log_chunk

    size = log_path.stat().st_size
    offset = max(0, int(since_offset or 0))
    if offset > size:
        offset = 0
    if offset == 0 and size > max_bytes:
        offset = max(0, size - max_bytes)

    with log_path.open("rb") as fh:
        fh.seek(offset)
        chunk = fh.read(max_bytes)
        new_offset = fh.tell()

    if not chunk:
        return [], new_offset

    text = chunk.decode("utf-8", errors="replace")
    # Se começamos a meio de uma linha, descarta o fragmento inicial
    if offset > 0 and chunk and chunk[0:1] not in (b"\n", b"\r"):
        nl = text.find("\n")
        if nl >= 0:
            skip = nl + 1
            text = text[skip:]
            base = offset + skip
            lines = parse_tribe_log_chunk(text, base_offset=base)
            return lines, new_offset

    lines = parse_tribe_log_chunk(text, base_offset=offset)
    return lines, new_offset


def fetch_remote_tribelog(
    *,
    base_url: str,
    token: str,
    server_id: str,
    offset: int = 0,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """GET /server/{id}/tribelog no remote_agent."""
    base = base_url.rstrip("/")
    qs = urllib.parse.urlencode({"offset": int(offset or 0)})
    url = f"{base}/server/{urllib.parse.quote(server_id)}/tribelog?{qs}"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def poll_once(
    *,
    session_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    """Uma passagem de polling: ficheiros locais + remote_agent opcional."""
    from tribe_service import get_max_file_offset, ingest_tribe_log_lines

    if session_factory is None:
        try:
            import app as app_module

            session_factory = app_module._SessionLocal
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    if session_factory is None:
        return {"ok": False, "error": "Banco não configurado"}

    summary: dict[str, Any] = {"ok": True, "servers": [], "inserted_total": 0}
    db = session_factory()
    try:
        for target in discover_local_tribe_log_targets():
            sid = target["server_id"]
            path = find_tribe_log_path(target["install_dir"])
            if not path:
                continue
            since = get_max_file_offset(db, sid)
            try:
                lines, new_off = read_tribe_log_since(path, since_offset=since)
                # Primeira ingestão: não carrega o ficheiro inteiro histórico
                if since == 0 and lines and len(lines) > 200:
                    lines = lines[-200:]
                result = {"inserted": 0, "skipped": 0}
                if lines:
                    result = ingest_tribe_log_lines(
                        db,
                        server_id=sid,
                        lines=lines,
                        source="local_file",
                    )
                entry = {
                    "server_id": sid,
                    "source": "local_file",
                    "path": str(path),
                    "since": since,
                    "new_offset": new_off,
                    "lines": len(lines),
                    **result,
                }
                summary["servers"].append(entry)
                summary["inserted_total"] += int(result.get("inserted") or 0)
                _last_status["servers"][sid] = entry
            except Exception as exc:
                log.warning("tribe_log poll local %s: %s", sid, exc)
                summary["servers"].append({"server_id": sid, "error": str(exc)})

        remote_url = os.environ.get("ARKSHOP_TRIBE_LOG_REMOTE_URL", "").strip()
        remote_token = os.environ.get("ARKSHOP_TRIBE_LOG_REMOTE_TOKEN", "").strip()
        if remote_url and remote_token:
            # Lista servidores conhecidos via remote /servers
            try:
                req = urllib.request.Request(
                    remote_url.rstrip("/") + "/servers",
                    headers={"Authorization": f"Bearer {remote_token}"},
                )
                with urllib.request.urlopen(req, timeout=8.0) as resp:
                    servers_payload = json.loads(resp.read().decode("utf-8"))
                remote_servers = servers_payload.get("servers") or []
            except Exception as exc:
                log.debug("remote /servers: %s", exc)
                remote_servers = []

            for srv in remote_servers:
                sid = str(
                    (srv.get("shop_server_id") if isinstance(srv, dict) else None)
                    or (srv.get("id") if isinstance(srv, dict) else None)
                    or (srv.get("name") if isinstance(srv, dict) else None)
                    or ""
                ).strip()
                if not sid:
                    continue
                since = get_max_file_offset(db, sid)
                try:
                    payload = fetch_remote_tribelog(
                        base_url=remote_url,
                        token=remote_token,
                        server_id=sid,
                        offset=since,
                    )
                    raw_lines = payload.get("lines") or []
                    new_off = int(payload.get("offset") or since)
                    result = {"inserted": 0, "skipped": 0}
                    if raw_lines:
                        result = ingest_tribe_log_lines(
                            db,
                            server_id=sid,
                            lines=raw_lines,
                            source="remote_agent",
                        )
                    entry = {
                        "server_id": sid,
                        "source": "remote_agent",
                        "since": since,
                        "new_offset": new_off,
                        "lines": len(raw_lines),
                        **result,
                    }
                    summary["servers"].append(entry)
                    summary["inserted_total"] += int(result.get("inserted") or 0)
                    _last_status["servers"][sid] = entry
                except Exception as exc:
                    log.warning("tribe_log poll remote %s: %s", sid, exc)
                    summary["servers"].append({"server_id": sid, "error": str(exc)})
    finally:
        try:
            db.close()
        except Exception:
            pass
        # scoped_session: remove() devolve a conexão ao pool nesta thread.
        try:
            if hasattr(session_factory, "remove"):
                session_factory.remove()
            else:
                import app as app_module

                if getattr(app_module, "_SessionLocal", None) is not None:
                    app_module._SessionLocal.remove()
        except Exception:
            pass

    _last_status["runs"] = int(_last_status.get("runs") or 0) + 1
    _last_status["last_error"] = None
    return summary


def get_tribe_log_poller_status() -> dict[str, Any]:
    return {
        "interval_seconds": _poll_interval_seconds(),
        "running": _scheduler_thread is not None and _scheduler_thread.is_alive(),
        **_last_status,
    }


def _scheduler_worker(interval: int) -> None:
    log.info("tribe_log_poller started (interval=%ss)", interval)
    # Primeira passagem após arranque curto
    if not _scheduler_stop.wait(5):
        try:
            poll_once()
        except Exception as exc:
            log.warning("tribe_log_poller first tick failed: %s", exc)
            _last_status["last_error"] = str(exc)
    while not _scheduler_stop.wait(interval):
        try:
            poll_once()
        except Exception as exc:
            log.warning("tribe_log_poller tick failed: %s", exc)
            _last_status["last_error"] = str(exc)


def start_tribe_log_poller_if_needed() -> None:
    """Inicia o worker se ARKSHOP_TRIBE_LOG_POLL_SECONDS > 0."""
    global _scheduler_thread
    interval = _poll_interval_seconds()
    if interval <= 0:
        return
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return
    _scheduler_stop.clear()
    _scheduler_thread = threading.Thread(
        target=_scheduler_worker,
        args=(interval,),
        name="arkshop-tribe-log-poller",
        daemon=True,
    )
    _scheduler_thread.start()
