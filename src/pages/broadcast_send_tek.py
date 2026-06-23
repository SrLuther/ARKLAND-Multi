"""Envio de broadcast RCON para todos os servidores TEK gerenciados."""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp

_MAX_MSG_LEN = 900


def _rcon_command(mode: str, message: str) -> str:
    safe = message.replace('"', "'").strip()[:_MAX_MSG_LEN]
    cmd = (mode or "Broadcast").strip()
    if cmd == "ServerChat":
        return f"ServerChat {safe}"
    if cmd == "SendRcon":
        return f"SendRcon {safe}"
    return f"Broadcast {safe}"


def _send_one_server(
    srv: Any,
    message: str,
    mode: str,
) -> tuple[bool, str]:
    from ..rcon_client import RconClient

    name = getattr(srv, "name", None) or getattr(srv, "id", "?")
    if not getattr(srv, "rcon_enabled", False):
        return False, f"{name} (RCON desabilitado)"
    pwd = (getattr(srv, "admin_password", None) or "").strip()
    if not pwd:
        return False, f"{name} (sem senha admin)"

    host = (getattr(srv, "server_ip", None) or "").strip() or "127.0.0.1"
    port = int(getattr(srv, "rcon_port", 0) or 0)
    if port <= 0:
        return False, f"{name} (porta RCON inválida)"

    cmd = _rcon_command(mode, message)
    client: RconClient | None = None
    try:
        client = RconClient(host, port, pwd)
        client.connect()
        ok, resp = client.send_command_with_retry(cmd, retries=3)
        if ok:
            return True, name
        detail = (resp or "falha RCON").strip()[:80]
        return False, f"{name} ({detail})"
    except Exception as exc:
        return False, f"{name} ({exc})"
    finally:
        if client is not None:
            try:
                client.disconnect()
            except Exception:
                pass


def broadcast_send_tek(
    app: "ARKServerManagerApp",
    message: str,
    *,
    server_ids: list[str] | None = None,
) -> None:
    """Envia mensagem a todos os servidores gerenciados (ou subconjunto)."""
    if not message or not message.strip():
        app._toast("Digite uma mensagem para enviar.", kind="warning")
        return

    servers = list(app.asm_config_manager.servers)
    if server_ids is not None:
        ids = set(server_ids)
        servers = [s for s in servers if s.id in ids]

    if not servers:
        app._toast("Nenhum servidor TEK configurado.", kind="warning")
        return

    mode = getattr(app.config_manager.config.backup, "rcon_broadcast_mode", "Broadcast")
    text = message.strip()

    def _worker() -> None:
        ok_count = 0
        failures: list[str] = []
        for srv in servers:
            ok, info = _send_one_server(srv, text, mode)
            if ok:
                ok_count += 1
            else:
                failures.append(info)

        total = len(servers)
        if failures:
            fail_preview = ", ".join(failures[:4])
            if len(failures) > 4:
                fail_preview += f" (+{len(failures) - 4})"
            summary = f"Enviado: {ok_count}/{total} — falhas: {fail_preview}"
            kind = "warning" if ok_count else "error"
        else:
            summary = f"Broadcast enviado a {ok_count} servidor(es)."
            kind = "info"

        def _done() -> None:
            app._toast(summary, kind=kind)
            app._global_log(f"[Broadcast] {summary}", "warning" if failures else "info")

        app.after(0, _done)

    threading.Thread(target=_worker, daemon=True).start()
