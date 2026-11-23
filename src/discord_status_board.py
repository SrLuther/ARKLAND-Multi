"""
Painel fixo Discord â€” status dos servidores TEK.

Uma Ãºnica mensagem (embed) Ã© criada apÃ³s limpar o canal no arranque do app
e depois sÃ³ Ã© editada (PATCH) enquanto o processo corre.
ONLINE sÃ³ quando listado na Steam (STEAM_AVAILABLE).
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
from .server_visibility import (
    STEAM_LAN,
    STEAM_NEED_PUBLIC_IP,
    STEAM_UNAVAILABLE,
    STEAM_WAITING,
)

_logger = logging.getLogger(__name__)

STATUS_PARADO = "PARADO"
STATUS_INICIANDO = "INICIANDO"
STATUS_ATUALIZANDO = "ATUALIZANDO"
STATUS_ONLINE = "ONLINE"
STATUS_ONLINE_UNLISTED = "ONLINE_SEM_LISTAGEM"
STATUS_ONLINE_LAN = "ONLINE_LAN"
STATUS_QUERY_PENDING = "QUERY_PENDENTE"
STATUS_INDISPONIVEL = "INDISPONIVEL"

_STATUS_META: dict[str, tuple[str, int]] = {
    STATUS_PARADO: ("ðŸ”´", 0x95A5A6),
    STATUS_INICIANDO: ("ðŸŸ¡", 0xF1C40F),
    STATUS_ATUALIZANDO: ("ðŸ”„", 0x3498DB),
    STATUS_ONLINE: ("ðŸŸ¢", 0x2ECC71),
    STATUS_ONLINE_UNLISTED: ("ðŸŸ¡", 0xF1C40F),
    STATUS_ONLINE_LAN: ("ðŸ”µ", 0x3498DB),
    STATUS_QUERY_PENDING: ("ðŸŸ ", 0xE67E22),
    STATUS_INDISPONIVEL: ("âšª", 0x64748B),
}

_STATUS_SECTIONS: tuple[tuple[str, str], ...] = (
    (STATUS_ONLINE, "ðŸŸ¢ ONLINE"),
    (STATUS_ONLINE_UNLISTED, "ðŸŸ¡ AGUARDANDO STEAM"),
    (STATUS_QUERY_PENDING, "ðŸŸ  AGUARDANDO QUERY"),
    (STATUS_PARADO, "ðŸ”´ OFFLINE"),
    (STATUS_INDISPONIVEL, "âšª INDISPONÃVEL"),
    (STATUS_ONLINE_LAN, "ðŸ”µ ONLINE NA REDE LOCAL"),
    (STATUS_INICIANDO, "ðŸŸ¡ INICIANDO"),
    (STATUS_ATUALIZANDO, "ðŸ”„ ATUALIZANDO"),
)

_FOOTER = "ARKLAND Â· painel de status"
_OFFICIAL_SITE_URL = "https://arkland.com.br/"
_DEBOUNCE_S = 8.0
_API = "https://discord.com/api/v10"
_TZ_BRASILIA = timezone(timedelta(hours=-3), name="BRT")
_status_change_lock = threading.Lock()
_status_change_by_server: dict[str, tuple[str, str, float]] = {}


def _now_brasilia_label() -> str:
    """Data/hora de BrasÃ­lia (UTCâˆ’3) para o rodapÃ© do painel."""
    return datetime.now(_TZ_BRASILIA).strftime("%d/%m/%Y %H:%M:%S")


def _status_changed_at(server_id: str, status: str, label: str, unix_time: float) -> tuple[str, float]:
    """MantÃ©m o instante da Ãºltima transiÃ§Ã£o de estado de cada servidor."""
    key = (server_id or "?").strip() or "?"
    with _status_change_lock:
        previous = _status_change_by_server.get(key)
        if previous and previous[0] == status:
            return previous[1], previous[2]
        _status_change_by_server[key] = (status, label, unix_time)
        return label, unix_time


def connected_label(status: str, players: Optional[int]) -> str:
    """Texto de pessoas conectadas no card.

    Usa a contagem A2S jÃ¡ guardada no servidor. Servidor parado ou em
    atualizaÃ§Ã£o nÃ£o tem query ao vivo â€” traÃ§o, sem reaproveitar cache antigo.
    Query ausente (None) tambÃ©m vira traÃ§o. NÃ£o inventa um nÃºmero.
    """
    if status in (STATUS_PARADO, STATUS_INICIANDO, STATUS_ATUALIZANDO, STATUS_QUERY_PENDING):
        return "â€”"
    if players is None:
        return "â€”"
    return f"{players} jogadores"


def build_embed(rows: list) -> dict:
    updated_at = _now_brasilia_label()
    counted: list[str] = []
    grouped: dict[str, list[tuple[str, str, float]]] = {
        status: [] for status, _ in _STATUS_SECTIONS
    }
    for row in rows or []:
        try:
            name = str(row[0])
            status = str(row[1]) if len(row) > 1 else STATUS_INDISPONIVEL
            if status not in grouped:
                status = STATUS_INDISPONIVEL
            changed_label = str(row[2]) if len(row) > 2 and isinstance(row[2], str) else updated_at
            changed_unix = float(row[3]) if len(row) > 3 and row[3] is not None else 0.0
            grouped[status].append((name, changed_label or updated_at, changed_unix))
            counted.append(status)
        except Exception:
            _logger.debug("Linha do painel Discord ignorada", exc_info=True)

    lines: list[str] = []
    if not counted:
        lines.append("_Nenhum servidor configurado._")
    for status, title in _STATUS_SECTIONS:
        members = grouped[status]
        if not members:
            continue
        latest = max(members, key=lambda item: item[2])
        lines.append(f"**{title} - {latest[1]}**")
        lines.extend(
            f"â€¢ {name}"
            for name, _timestamp, _unix in sorted(members, key=lambda item: item[0].casefold())
        )

    online_n = sum(1 for s in counted if s in (STATUS_ONLINE, STATUS_ONLINE_LAN))
    waiting_n = sum(1 for s in counted if s in (STATUS_ONLINE_UNLISTED, STATUS_QUERY_PENDING, STATUS_INICIANDO, STATUS_ATUALIZANDO))
    offline_n = sum(1 for s in counted if s == STATUS_PARADO)
    unavailable_n = sum(1 for s in counted if s == STATUS_INDISPONIVEL)
    total_n = len(counted)
    counts = (
        f"{online_n} online Â· {waiting_n} aguardando Â· {offline_n} offline Â· "
        f"{unavailable_n} indisponÃ­vel Â· {total_n} total"
    )
    warning = (
        "âš ï¸ O painel Ã© atualizado periodicamente e pode ter atraso. "
        "Consulte tambÃ©m o site oficial e adicione os servidores aos favoritos da Steam."
    )
    lines.extend(("", warning))
    color = 0x2ECC71 if online_n and not waiting_n and not offline_n else 0x3498DB

    return {
        "title": "ðŸ“Š STATUS DOS SERVIDORES",
        "description": "\n".join(lines)[:4000],
        "color": color,
        "footer": {
            "text": (
                f"{_FOOTER} Â· {counts} Â· Dados consultados em "
                f"{updated_at} (horÃ¡rio de BrasÃ­lia)"
            )[:2048],
        },
    }

_lock = threading.Lock()
_io_lock = threading.Lock()
_last_push = 0.0
_pending_timer: Optional[threading.Timer] = None
_boot_done = False
_suppress_updates = False
_last_push_warn = 0.0
_PUSH_WARN_INTERVAL_S = 120.0


def _warn_push(msg: str, *args: Any) -> None:
    global _last_push_warn
    now = time.monotonic()
    if now - _last_push_warn < _PUSH_WARN_INTERVAL_S:
        _logger.debug(msg, *args)
        return
    _last_push_warn = now
    _logger.warning(msg, *args)


def map_public_status(process_status: str, steam_status: str) -> str:
    """Mapeia processo + listagem Steam â†’ estado pÃºblico do painel."""
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
        if ss == STEAM_LAN:
            return STATUS_ONLINE_LAN
        if ss in (STEAM_WAITING, STEAM_NEED_PUBLIC_IP):
            # Waiting is emitted only after the local A2S query responds. The
            # process is online, but public Steam listing is not confirmed.
            return STATUS_ONLINE_UNLISTED
        if ss == STEAM_UNAVAILABLE or not ss:
            # The process is alive but the query endpoint is not confirmed;
            # never leave it labeled as starting indefinitely.
            return STATUS_QUERY_PENDING
        return STATUS_QUERY_PENDING
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


def _normalize_bot_token(bot_token: str) -> str:
    tok = (bot_token or "").strip()
    if tok.lower().startswith("bot "):
        tok = tok[4:].strip()
    return tok


def purge_channel_messages(bot_token: str, channel_id: str) -> tuple[int, str]:
    """Apaga mensagens do canal. Retorna (apagadas, aviso_ou_vazio)."""
    token = _normalize_bot_token(bot_token)
    cid = (channel_id or "").strip()
    if not token or not cid:
        return 0, "Token do bot ou ID do canal em falta."
    deleted = 0
    headers = {"Authorization": f"Bot {token}"}
    for _ in range(8):
        code, body = _http_json(
            "GET",
            f"{_API}/channels/{cid}/messages?limit=100",
            headers=headers,
        )
        if code in (401, 403):
            return deleted, (
                f"Bot sem permissÃ£o no canal ({code}). "
                "Precisa Manage Messages + Read Message History."
            )
        if code != 200:
            return deleted, f"Falha ao listar mensagens do canal (HTTP {code})."
        if not isinstance(body, list) or not body:
            break
        ids = [str(m.get("id")) for m in body if isinstance(m, dict) and m.get("id")]
        if not ids:
            break
        if len(ids) >= 2:
            bcode, bbody = _http_json(
                "POST",
                f"{_API}/channels/{cid}/messages/bulk-delete",
                payload={"messages": ids[:100]},
                headers=headers,
            )
            if bcode in (200, 204):
                deleted += len(ids[:100])
                time.sleep(0.4)
                continue
            _logger.warning("bulk-delete falhou (%s): %s â€” a apagar 1 a 1", bcode, bbody)
        for mid in ids:
            dcode, _ = _http_json(
                "DELETE",
                f"{_API}/channels/{cid}/messages/{mid}",
                headers=headers,
            )
            if dcode in (200, 204):
                deleted += 1
            time.sleep(0.35)
    return deleted, ""


def _webhook_delete(url: str, message_id: str) -> bool:
    wid, token = _parse_webhook_url(url)
    if not wid or not token or not message_id:
        return False
    code, _ = _http_json(
        "DELETE",
        f"{_API}/webhooks/{wid}/{token}/messages/{message_id}",
    )
    return code in (200, 204)


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


def _status_components() -> list[dict[str, Any]]:
    return [{
        "type": 1,
        "components": [{"type": 2, "style": 5, "label": "SITE OFICIAL", "url": _OFFICIAL_SITE_URL}],
    }]


def _webhook_create(url: str, username: str, embed: dict) -> str:
    """POST ?wait=true â†’ devolve message id."""
    base = url.split("?")[0].rstrip("/")
    code, body = _http_json(
        "POST",
        f"{base}?wait=true",
        payload={"username": username or "ARKLAND", "embeds": [embed], "components": _status_components()},
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
        payload={"username": username or "ARKLAND", "embeds": [embed], "components": _status_components()},
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
        _logger.warning("NÃ£o gravou status_board_message_id: %s", exc)


def _webhook_url(cfg: Any) -> str:
    """Webhook dedicado do painel (nÃ£o o de eventos)."""
    return (getattr(cfg, "status_board_webhook_url", "") or "").strip()


def _sender_name(cfg: Any) -> str:
    return (getattr(cfg, "sender_name", "") or "").strip() or "ARKLAND"


def _channel_id(cfg: Any) -> str:
    return (getattr(cfg, "status_board_channel_id", "") or "").strip()


def _cancel_pending_timer() -> None:
    global _pending_timer
    with _lock:
        if _pending_timer is not None:
            _pending_timer.cancel()
            _pending_timer = None


def _opt_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def collect_status_payload(app: Any) -> list[dict[str, Any]]:
    """Lista de status para Discord + push Web Store."""
    from .asm_engine.asm_ini_manager import effective_session_name

    rows_out: list[dict[str, Any]] = []
    try:
        servers = list(app.asm_config_manager.servers or [])
    except Exception:
        servers = []
    mgr = getattr(app, "asm_server_manager", None)
    updated_at = _now_brasilia_label()
    now_unix = time.time()
    for srv in servers:
        try:
            try:
                display = (effective_session_name(srv) or "").strip()
            except Exception:
                display = ""
            if not display:
                display = (getattr(srv, "session_name", None) or getattr(srv, "name", None)
                           or getattr(srv, "id", "?") or "?").strip()
            asm_id = (getattr(srv, "id", None) or "").strip()
            shop_id = (getattr(srv, "shop_server_id", None) or "").strip()
            if not shop_id:
                # Keep the TEK heartbeat aligned with Shop/RCON integrations
                # when a profile has not had its shop_server_id initialized yet.
                from .shop_integration import slugify_server_id

                shop_id = slugify_server_id(
                    getattr(srv, "name", "") or display,
                    asm_id,
                )
            sid = shop_id or asm_id
            process = ASM_STATUS_STOPPED
            steam = ""
            inst = None
            players: Optional[int] = None
            max_players: Optional[int] = None
            if mgr is not None and asm_id:
                try:
                    inst = mgr.get_instance(asm_id)
                except Exception:
                    inst = None
                    _logger.debug("get_instance falhou para %s", asm_id, exc_info=True)
                if inst is not None:
                    process = getattr(inst, "status", ASM_STATUS_STOPPED) or ASM_STATUS_STOPPED
                    steam = getattr(inst, "steam_status", "") or ""
                    # Contagem jÃ¡ preenchida pelo poller A2S (mesma fonte do card Â«pessoasÂ»).
                    # None = query falhou ou ainda nÃ£o correu â€” o card mostra traÃ§o.
                    players = _opt_int(getattr(inst, "a2s_players", None))
                    max_players = _opt_int(getattr(inst, "a2s_max_players", None))
            if max_players is None:
                max_players = _opt_int(getattr(srv, "max_players", None))
            status = map_public_status(process, steam)
            discord_status = STATUS_INDISPONIVEL if mgr is None or inst is None else status
            status_changed_at, status_changed_at_unix = _status_changed_at(
                sid, discord_status, updated_at, now_unix
            )
            item = {
                "server_id": sid,
                "status": status,
                "discord_status": discord_status,
                "listing_status": str(steam or "").strip().lower(),
                "status_detail": str(
                    getattr(inst, "steam_status_detail", "") if inst is not None else ""
                ).strip(),
                "display_name": display,
                "steam_listing_name": str(
                    getattr(inst, "steam_listing_name", "") if inst is not None else ""
                ).strip(),
                "updated_at": updated_at,
                "updated_at_unix": now_unix,
                "status_changed_at": status_changed_at,
                "status_changed_at_unix": status_changed_at_unix,
                "players": players,
                "max_players": max_players,
            }
            rows_out.append(item)
            # Alias pelo id ASM se diferente do shop_id â€” home pode usar qualquer um.
            if shop_id and asm_id and shop_id != asm_id:
                rows_out.append({**item, "server_id": asm_id})
        except Exception:
            _logger.debug("Servidor omitido do payload de status", exc_info=True)
            name = (getattr(srv, "name", None) or getattr(srv, "id", "?") or "?")
            rows_out.append({
                "server_id": getattr(srv, "id", "") or "?",
                "status": STATUS_PARADO,
                "discord_status": STATUS_INDISPONIVEL,
                "display_name": str(name),
                "steam_listing_name": "",
                "updated_at": updated_at,
                "updated_at_unix": now_unix,
                "status_changed_at": updated_at,
                "status_changed_at_unix": now_unix,
                "players": None,
                "max_players": None,
            })
    return rows_out


def push_status_to_webstore(app: Any, items: Optional[list[dict[str, Any]]] = None) -> None:
    """Envia status runtime Ã  Web Store (best-effort, thread-safe no caller)."""
    try:
        from .shop_integration import resolve_plugin_api_url
    except Exception:
        return
    try:
        cm = app.config_manager
        shop = cm.config.shop
        api_key = (getattr(shop, "api_key", "") or "").strip()
        if not api_key:
            _warn_push(
                "runtime-status push ignorado: shop.api_key vazio "
                "(home fica em Â«Aguardando status do TEKâ€¦Â»)."
            )
            return
        api_url = resolve_plugin_api_url(shop).rstrip("/")
        if not api_url:
            _warn_push("runtime-status push ignorado: URL da Web Store vazia.")
            return
        payload_items = items if items is not None else collect_status_payload(app)
        if not payload_items:
            return
        body = json.dumps({"servers": payload_items}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{api_url}/api/servers/runtime-status",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "X-API-Key": api_key,
                "User-Agent": "ARKLAND-Multi/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            if int(resp.status) not in (200, 201, 204):
                _warn_push("runtime-status push HTTP %s", resp.status)
            else:
                from .diagnostics.events import CAT_WEBSTORE, diag_event
                diag_event(CAT_WEBSTORE, "runtime-status push ok", _level=10,
                           servers=len(payload_items), url=api_url)
    except Exception as exc:
        # Auth/URL/rede â€” sem isto a home fica eternamente Â«Aguardando status do TEKâ€¦Â».
        _warn_push("runtime-status push falhou: %s", exc)


def boot_webstore_status_push(app: Any) -> None:
    """No arranque: envia status Ã  Web Store mesmo sem painel Discord activo."""

    def _worker() -> None:
        try:
            # Pequeno atraso para reconnect/Steam poller terem estado Ãºtil.
            time.sleep(3.0)
            push_status_to_webstore(app)
        except Exception as exc:
            _logger.warning("boot_webstore_status_push falhou: %s", exc)

    threading.Thread(
        target=_worker, daemon=True, name="webstore-status-boot"
    ).start()


def _rows_for_embed(payload: list[dict[str, Any]]) -> list[tuple[str, str, str, float]]:
    """Uma linha por servidor: nome exibido, estado e instante da transiÃ§Ã£o."""
    seen: set[str] = set()
    rows: list[tuple[str, str, str, float]] = []
    for item in payload:
        try:
            status = str(item.get("discord_status") or item.get("status") or STATUS_PARADO)
            listed_name = str(item.get("steam_listing_name") or "").strip()
            name = listed_name if status == STATUS_ONLINE and listed_name else str(
                item.get("display_name") or item.get("server_id") or "?"
            )
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            changed_at = str(item.get("status_changed_at") or item.get("updated_at") or "")
            changed_unix = _opt_int(item.get("status_changed_at_unix")) or 0
            rows.append((name, status, changed_at, float(changed_unix)))
        except Exception:
            _logger.debug("Item de status ignorado no card", exc_info=True)
    rows.sort(key=lambda r: r[0].lower())
    return rows


def _collect_rows(app: Any) -> list[tuple[str, str, str, float]]:
    """Lista (nome, estado, instante da transiÃ§Ã£o) ordenada por nome."""
    return _rows_for_embed(collect_status_payload(app))


def _push_now(app: Any) -> None:
    """Edita a mensagem existente; sÃ³ cria se ainda nÃ£o houver ID (com lock)."""
    global _suppress_updates
    if _suppress_updates:
        return
    cfg = _status_cfg(app)
    if cfg is None or not getattr(cfg, "status_board_enabled", False):
        return
    url = _webhook_url(cfg)
    if not url:
        return
    username = _sender_name(cfg)
    payload = collect_status_payload(app)
    embed = build_embed(_rows_for_embed(payload))

    with _io_lock:
        if _suppress_updates:
            return
        mid = (getattr(cfg, "status_board_message_id", "") or "").strip()
        if mid and _webhook_edit(url, mid, username, embed):
            push_status_to_webstore(app, payload)
            return
        mid2 = (getattr(cfg, "status_board_message_id", "") or "").strip()
        if mid2 and mid2 != mid and _webhook_edit(url, mid2, username, embed):
            push_status_to_webstore(app, payload)
            return
        new_id = _webhook_create(url, username, embed)
        if new_id:
            _persist_message_id(app, new_id)
        push_status_to_webstore(app, payload)


def _recreate_sync(app: Any) -> dict[str, Any]:
    """Limpa canal + publica um painel. Corre sob _io_lock (chamador)."""
    cfg = _status_cfg(app)
    result: dict[str, Any] = {
        "ok": False,
        "purged": 0,
        "message_id": "",
        "warnings": [],
    }
    if cfg is None or not getattr(cfg, "status_board_enabled", False):
        result["warnings"].append("Painel de status desativado.")
        return result
    url = _webhook_url(cfg)
    if not url:
        result["warnings"].append("Webhook do painel vazio.")
        return result

    # 1) Apaga a mensagem conhecida via webhook (nÃ£o precisa de bot).
    old_mid = (getattr(cfg, "status_board_message_id", "") or "").strip()
    if old_mid:
        if _webhook_delete(url, old_mid):
            _logger.info("Painel Discord: mensagem antiga %s apagada via webhook", old_mid)
        cfg.status_board_message_id = ""

    # 2) Limpa o canal com o bot.
    channel_id = _channel_id(cfg) or fetch_webhook_channel_id(url)
    token = _bot_token(app)
    if token and channel_id:
        purged, warn = purge_channel_messages(token, channel_id)
        result["purged"] = purged
        if warn:
            result["warnings"].append(warn)
        else:
            _logger.info("Painel Discord: canal %s limpo (%s msgs)", channel_id, purged)
    elif not channel_id:
        result["warnings"].append(
            "ID do canal em falta â€” nÃ£o limpei a sala (sÃ³ tentei apagar a msg conhecida)."
        )
    else:
        result["warnings"].append(
            "Token do Discord Bot em falta â€” nÃ£o limpei a sala. "
            "Mensagens antigas ficam; configure o token em Â«Discord BotÂ»."
        )

    # 3) Uma Ãºnica mensagem nova.
    payload = collect_status_payload(app)
    new_id = _webhook_create(url, _sender_name(cfg), build_embed(_rows_for_embed(payload)))
    if new_id:
        _persist_message_id(app, new_id)
        result["message_id"] = new_id
        result["ok"] = True
        _logger.info("Painel Discord: nova mensagem %s", new_id)
    else:
        result["warnings"].append("Falha ao publicar o painel novo.")
    push_status_to_webstore(app, payload)
    return result


def boot_status_board(app: Any) -> None:
    """No arranque: limpa o canal e publica painel novo (webhook dedicado)."""
    global _boot_done, _suppress_updates
    # Home pÃºblica NÃƒO depende do painel Discord â€” sempre faz push runtime.
    boot_webstore_status_push(app)

    cfg = _status_cfg(app)
    if cfg is None or not getattr(cfg, "status_board_enabled", False):
        return
    if not _webhook_url(cfg):
        _logger.warning(
            "Painel Discord: webhook do painel vazio â€” configure o webhook "
            "dedicado do canal de status."
        )
        return

    def _worker() -> None:
        global _boot_done, _suppress_updates
        _cancel_pending_timer()
        _suppress_updates = True
        try:
            with _io_lock:
                _recreate_sync(app)
        except Exception as exc:
            _logger.warning("boot_status_board falhou: %s", exc)
        finally:
            _suppress_updates = False
            _boot_done = True

    threading.Thread(target=_worker, daemon=True, name="discord-status-boot").start()


def schedule_status_board_update(app: Any, *, force_new: bool = False) -> None:
    """Agenda atualizaÃ§Ã£o com debounce (edita a mesma mensagem + push Web Store)."""
    global _last_push, _pending_timer
    if force_new:
        recreate_status_board(app)
        return
    if _suppress_updates:
        # Durante recreate Discord, a home nÃ£o pode ficar sem heartbeat.
        try:
            push_status_to_webstore(app)
        except Exception:
            pass
        return

    def _run() -> None:
        global _last_push, _pending_timer
        with _lock:
            _pending_timer = None
            _last_push = time.monotonic()
        try:
            # Home sempre atualiza; Discord sÃ³ se o painel estiver ativo.
            cfg = _status_cfg(app)
            if cfg is not None and getattr(cfg, "status_board_enabled", False) and _webhook_url(cfg):
                _push_now(app)
            else:
                push_status_to_webstore(app)
        except Exception as exc:
            _logger.warning("AtualizaÃ§Ã£o painel Discord falhou: %s", exc)

    with _lock:
        now = time.monotonic()
        wait = max(0.0, _DEBOUNCE_S - (now - _last_push))
        if _pending_timer is not None:
            _pending_timer.cancel()
        _pending_timer = threading.Timer(wait, _run)
        _pending_timer.daemon = True
        _pending_timer.start()


def recreate_status_board(app: Any, *, sync: bool = False) -> dict[str, Any]:
    """Limpa canal + publica painel novo. sync=True bloqueia e devolve resultado."""
    global _suppress_updates

    def _worker() -> dict[str, Any]:
        global _suppress_updates
        _cancel_pending_timer()
        _suppress_updates = True
        try:
            with _io_lock:
                return _recreate_sync(app)
        except Exception as exc:
            _logger.warning("recreate_status_board falhou: %s", exc)
            return {
                "ok": False,
                "purged": 0,
                "message_id": "",
                "warnings": [str(exc)],
            }
        finally:
            _suppress_updates = False

    if sync:
        return _worker()

    result_box: dict[str, Any] = {"ok": False, "purged": 0, "message_id": "", "warnings": []}

    def _bg() -> None:
        result_box.update(_worker())

    t = threading.Thread(target=_bg, daemon=True, name="discord-status-recreate")
    t.start()
    return result_box


def recreate_status_board_blocking(app: Any) -> dict[str, Any]:
    """VersÃ£o sÃ­ncrona para o botÃ£o da UI (mostra resultado real)."""
    return recreate_status_board(app, sync=True)
