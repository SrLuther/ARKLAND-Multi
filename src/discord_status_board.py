"""
Painel fixo Discord — status dos servidores TEK.

Uma única mensagem (embed) é criada após limpar o canal no arranque do app
e depois só é editada (PATCH) enquanto o processo corre.
ONLINE só quando listado na Steam (STEAM_AVAILABLE).
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .asm_engine.asm_server_config import (
    ASM_STATUS_CRASHED,
    ASM_STATUS_RUNNING,
    ASM_STATUS_STARTING,
    ASM_STATUS_STOPPING,
    ASM_STATUS_STOPPED,
    ASM_STATUS_UPDATING,
)
from .server_visibility import STEAM_AVAILABLE

_logger = logging.getLogger(__name__)

STATUS_PARADO = "PARADO"
STATUS_INICIANDO = "INICIANDO"
STATUS_ATUALIZANDO = "ATUALIZANDO"
STATUS_ONLINE = "ONLINE"

_STATUS_META: dict[str, tuple[str, int]] = {
    STATUS_PARADO: ("🔴", 0x95A5A6),
    STATUS_INICIANDO: ("🟡", 0xF1C40F),
    STATUS_ATUALIZANDO: ("🔄", 0x3498DB),
    STATUS_ONLINE: ("🟢", 0x2ECC71),
}

_FOOTER = "ARKLAND · painel de status"
_DEBOUNCE_S = 8.0
_API = "https://discord.com/api/v10"
_TZ_BRASILIA = timezone(timedelta(hours=-3), name="BRT")


def _now_brasilia_label() -> str:
    """Data/hora de Brasília (UTC−3) para o rodapé do painel."""
    return datetime.now(_TZ_BRASILIA).strftime("%d/%m/%Y %H:%M:%S")


def build_embed(rows: list[tuple[str, str]]) -> dict:
    updated_at = _now_brasilia_label()
    if not rows:
        description = "_Nenhum servidor configurado._"
        color = 0x64748B
    else:
        lines: list[str] = []
        worst = STATUS_ONLINE
        order = [STATUS_PARADO, STATUS_ATUALIZANDO, STATUS_INICIANDO, STATUS_ONLINE]
        for name, status in rows:
            emoji, _ = _STATUS_META.get(status, ("⚪", 0x64748B))
            lines.append(f"{emoji} **{name}** — `{status}`")
            if order.index(status) < order.index(worst):
                worst = status
        description = "\n".join(lines)
        color = _STATUS_META.get(worst, ("", 0x64748B))[1]

    online_n = sum(1 for _, s in rows if s == STATUS_ONLINE)
    total_n = len(rows)
    return {
        "title": "🖥️  Status dos servidores",
        "description": description[:4000],
        "color": color,
        "footer": {
            "text": (
                f"{_FOOTER} · {online_n}/{total_n} online · "
                f"Atualizado {updated_at} (Brasília)"
            )[:2048],
        },
    }

_lock = threading.Lock()
_last_push = 0.0
_pending_timer: Optional[threading.Timer] = None
_boot_done = False


def map_public_status(process_status: str, steam_status: str) -> str:
    """Mapeia processo + listagem Steam → estado público do painel."""
    ps = (process_status or "").strip().lower()
    ss = (steam_status or "").strip().lower()

    if ps == ASM_STATUS_UPDATING:
        return STATUS_ATUALIZANDO
    if ps == ASM_STATUS_STARTING:
        return STATUS_INICIANDO
    if ps in (ASM_STATUS_STOPPED, ASM_STATUS_STOPPING, ASM_STATUS_CRASHED, ""):
        return STATUS_PARADO
    if ps == ASM_STATUS_RUNNING:
        if ss == STEAM_AVAILABLE:
            return STATUS_ONLINE
        return STATUS_INICIANDO
    return STATUS_PARADO


def _http_json(
    method: str,
    url: str,
    *,
    payload: Optional[dict] = None,
    headers: Optional[dict[str, str]] = None,
    timeout: float = 15.0,
) -> tuple[int, Any]:
    data = None
    hdrs = {
        "User-Agent": "ARKLAND-Multi/1.0",
        "Content-Type": "application/json",
    }
    if headers:
        hdrs.update(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            body: Any = None
            if raw:
                try:
                    body = json.loads(raw.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    body = raw.decode("utf-8", errors="replace")
            return int(resp.status), body
    except urllib.error.HTTPError as exc:
        raw = b""
        try:
            raw = exc.read()
        except Exception:
            pass
        body = None
        if raw:
            try:
                body = json.loads(raw.decode("utf-8", errors="replace"))
            except Exception:
                body = raw.decode("utf-8", errors="replace")[:400]
        return int(exc.code), body


def _parse_webhook_url(url: str) -> tuple[str, str]:
    """Retorna (webhook_id, webhook_token) a partir da URL."""
    parts = (url or "").strip().rstrip("/").split("/")
    if len(parts) < 2:
        return "", ""
    return parts[-2], parts[-1]


def fetch_webhook_channel_id(webhook_url: str) -> str:
    wid, token = _parse_webhook_url(webhook_url)
    if not wid or not token:
        return ""
    code, body = _http_json("GET", f"{_API}/webhooks/{wid}/{token}")
    if code != 200 or not isinstance(body, dict):
        _logger.warning("Webhook GET falhou (%s): %s", code, body)
        return ""
    return str(body.get("channel_id") or "")


def purge_channel_messages(bot_token: str, channel_id: str) -> int:
    """Apaga todas as mensagens recentes do canal (bot com Manage Messages)."""
    token = (bot_token or "").strip()
    cid = (channel_id or "").strip()
    if not token or not cid:
        return 0
    deleted = 0
    headers = {"Authorization": f"Bot {token}"}
    # Até ~500 mensagens (5 páginas × 100) — suficiente para canal de status.
    for _ in range(5):
        code, body = _http_json(
            "GET",
            f"{_API}/channels/{cid}/messages?limit=100",
            headers=headers,
        )
        if code != 200 or not isinstance(body, list) or not body:
            break
        ids = [str(m.get("id")) for m in body if isinstance(m, dict) and m.get("id")]
        if not ids:
            break
        # Bulk delete exige 2–100 msgs e <14 dias; fallback individual.
        if len(ids) >= 2:
            bcode, _ = _http_json(
                "POST",
                f"{_API}/channels/{cid}/messages/bulk-delete",
                payload={"messages": ids[:100]},
                headers=headers,
            )
            if bcode in (200, 204):
                deleted += len(ids[:100])
                time.sleep(0.35)
                continue
        for mid in ids:
            dcode, _ = _http_json(
                "DELETE",
                f"{_API}/channels/{cid}/messages/{mid}",
                headers=headers,
            )
            if dcode in (200, 204):
                deleted += 1
            time.sleep(0.35)
    return deleted


def _status_cfg(app: Any) -> Any:
    try:
        return app.config_manager.config.discord_notify
    except Exception:
        return None


def _bot_token(app: Any) -> str:
    try:
        return (app.config_manager.config.discord_bot.token or "").strip()
    except Exception:
        return ""


def _collect_rows(app: Any) -> list[tuple[str, str]]:
    """Lista (nome_exibição_Steam, status_público) ordenada por nome."""
    from .asm_engine.asm_ini_manager import effective_session_name

    rows: list[tuple[str, str]] = []
    try:
        servers = list(app.asm_config_manager.servers or [])
    except Exception:
        servers = []
    mgr = getattr(app, "asm_server_manager", None)
    for srv in servers:
        # Mesmo nome do browser / lista Steam (SessionName), não o nome interno TEK.
        try:
            name = (effective_session_name(srv) or "").strip()
        except Exception:
            name = ""
        if not name:
            name = (getattr(srv, "session_name", None) or getattr(srv, "name", None)
                    or getattr(srv, "id", "?") or "?").strip()
        sid = getattr(srv, "id", "")
        process = ASM_STATUS_STOPPED
        steam = ""
        if mgr is not None:
            inst = mgr.get_instance(sid)
            if inst is not None:
                process = getattr(inst, "status", ASM_STATUS_STOPPED) or ASM_STATUS_STOPPED
                steam = getattr(inst, "steam_status", "") or ""
        rows.append((name, map_public_status(process, steam)))
    rows.sort(key=lambda r: r[0].lower())
    return rows


def _webhook_create(url: str, username: str, embed: dict) -> str:
    """POST ?wait=true → devolve message id."""
    base = url.split("?")[0].rstrip("/")
    code, body = _http_json(
        "POST",
        f"{base}?wait=true",
        payload={"username": username or "ARKLAND", "embeds": [embed]},
    )
    if code not in (200, 201) or not isinstance(body, dict):
        _logger.warning("Falha a criar painel Discord (%s): %s", code, body)
        return ""
    return str(body.get("id") or "")


def _webhook_edit(url: str, message_id: str, username: str, embed: dict) -> bool:
    wid, token = _parse_webhook_url(url)
    if not wid or not token or not message_id:
        return False
    code, body = _http_json(
        "PATCH",
        f"{_API}/webhooks/{wid}/{token}/messages/{message_id}",
        payload={"username": username or "ARKLAND", "embeds": [embed]},
    )
    if code in (200, 201):
        return True
    _logger.warning("Falha a editar painel Discord (%s): %s", code, body)
    return False


def _persist_message_id(app: Any, message_id: str) -> None:
    cfg = _status_cfg(app)
    if cfg is None:
        return
    cfg.status_board_message_id = message_id or ""
    try:
        app.config_manager.save()
    except Exception as exc:
        _logger.warning("Não gravou status_board_message_id: %s", exc)


def _webhook_url(cfg: Any) -> str:
    return (getattr(cfg, "webhook_url", "") or "").strip()


def _sender_name(cfg: Any) -> str:
    return (getattr(cfg, "sender_name", "") or "").strip() or "ARKLAND"


def _channel_id(cfg: Any) -> str:
    return (getattr(cfg, "status_board_channel_id", "") or "").strip()


def _push_now(app: Any, *, force_new: bool = False) -> None:
    cfg = _status_cfg(app)
    if cfg is None or not getattr(cfg, "status_board_enabled", False):
        return
    url = _webhook_url(cfg)
    if not url:
        return
    username = _sender_name(cfg)
    embed = build_embed(_collect_rows(app))
    mid = "" if force_new else (getattr(cfg, "status_board_message_id", "") or "").strip()

    if mid and _webhook_edit(url, mid, username, embed):
        return
    new_id = _webhook_create(url, username, embed)
    if new_id:
        _persist_message_id(app, new_id)


def boot_status_board(app: Any) -> None:
    """No arranque: limpa o canal e publica um painel novo (reusa webhook global)."""
    global _boot_done
    cfg = _status_cfg(app)
    if cfg is None or not getattr(cfg, "status_board_enabled", False):
        return
    url = _webhook_url(cfg)
    if not url:
        _logger.warning("Painel Discord: webhook global vazio — painel não publicado.")
        return

    def _worker() -> None:
        global _boot_done
        try:
            channel_id = _channel_id(cfg)
            if not channel_id:
                # Fallback: canal do próprio webhook
                channel_id = fetch_webhook_channel_id(url)
            token = _bot_token(app)
            if token and channel_id:
                n = purge_channel_messages(token, channel_id)
                _logger.info(
                    "Painel Discord: canal %s limpo (%s msgs)", channel_id, n
                )
            elif not channel_id:
                _logger.warning(
                    "Painel Discord: defina o ID do canal — "
                    "não foi possível limpar a sala."
                )
            elif not token:
                _logger.warning(
                    "Painel Discord: sem token do Discord Bot — "
                    "não foi possível limpar o canal; só publica painel novo."
                )
            cfg.status_board_message_id = ""
            embed = build_embed(_collect_rows(app))
            new_id = _webhook_create(url, _sender_name(cfg), embed)
            if new_id:
                _persist_message_id(app, new_id)
                _logger.info("Painel Discord: nova mensagem %s", new_id)
        except Exception as exc:
            _logger.warning("boot_status_board falhou: %s", exc)
        finally:
            _boot_done = True

    threading.Thread(target=_worker, daemon=True, name="discord-status-boot").start()


def schedule_status_board_update(app: Any, *, force_new: bool = False) -> None:
    """Agenda atualização com debounce (edita a mesma mensagem)."""
    global _last_push, _pending_timer
    cfg = _status_cfg(app)
    if cfg is None or not getattr(cfg, "status_board_enabled", False):
        return
    if not _webhook_url(cfg):
        return

    def _run() -> None:
        global _last_push, _pending_timer
        with _lock:
            _pending_timer = None
            _last_push = time.monotonic()
        try:
            _push_now(app, force_new=force_new)
        except Exception as exc:
            _logger.warning("Atualização painel Discord falhou: %s", exc)

    with _lock:
        if force_new:
            if _pending_timer is not None:
                _pending_timer.cancel()
                _pending_timer = None
            threading.Thread(target=_run, daemon=True, name="discord-status-force").start()
            return
        now = time.monotonic()
        wait = max(0.0, _DEBOUNCE_S - (now - _last_push))
        if _pending_timer is not None:
            _pending_timer.cancel()
        _pending_timer = threading.Timer(wait, _run)
        _pending_timer.daemon = True
        _pending_timer.start()


def recreate_status_board(app: Any) -> None:
    """Limpa canal + publica painel novo (botão UI / restart manual)."""
    boot_status_board(app)
