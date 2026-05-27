from __future__ import annotations
import threading
from datetime import datetime
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..rcon_client import RconClient

_MAX_MSG_LEN = 900   # ARK trunca mensagens mais longas que ~1000 chars


def broadcast_rcon(app: "ARKServerManagerApp", server_id: str, message: str) -> None:
    """Envia um Broadcast RCON para todos os jogadores online com retry (3x).

    Prioriza a sessão RCON já aberta; cria conexão temporária se necessário.
    Registra o broadcast na aba de Chat.
    """
    if not message or not message.strip():
        return

    safe = message.replace('"', "'").strip()[:_MAX_MSG_LEN]

    ts = datetime.now().strftime("%H:%M:%S")
    app._chat_append(server_id, f"[{ts}] ", "ts")
    app._chat_append(server_id, "[BROADCAST]", "server")
    app._chat_append(server_id, f": {message}\n", "message")

    existing = app._rcon_clients.get(server_id)
    if existing and existing.is_connected:
        # ── Usa sessão aberta com retry ────────────────────────────────────
        def _do_existing() -> None:
            ok, resp = existing.send_command_with_retry(f"Broadcast {safe}", retries=3)
            if not ok:
                app.after(
                    0,
                    lambda r=resp: app._global_log(
                        f"[RCON] Broadcast falhou no servidor {server_id}: {r}", "warning"
                    ),
                )
        threading.Thread(target=_do_existing, daemon=True).start()
        return

    # ── Conexão temporária ────────────────────────────────────────────────
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return
    if not srv.rcon_enabled or not (srv.rcon_password or srv.admin_password):
        messagebox.showwarning(
            "RCON não configurado",
            "Habilite o RCON e defina a senha nas configurações do servidor"
            " antes de enviar broadcasts.",
            parent=app,
        )
        return

    rcon_port = srv.rcon_port
    rcon_pass = (srv.rcon_password or srv.admin_password).strip()

    def _do_temp() -> None:
        tmp: RconClient | None = None
        try:
            tmp = RconClient("127.0.0.1", rcon_port, rcon_pass)
            tmp.connect()
            ok, resp = tmp.send_command_with_retry(f"Broadcast {safe}", retries=3)
            if not ok:
                app.after(
                    0,
                    lambda r=resp: app._global_log(
                        f"[RCON] Broadcast falhou (temp): {r}", "warning"
                    ),
                )
        except Exception as exc:
            app.after(
                0,
                lambda e=str(exc): app._global_log(
                    f"[RCON] Broadcast falhou (temp): {e}", "warning"
                ),
            )
        finally:
            if tmp is not None:
                try:
                    tmp.disconnect()
                except Exception:
                    pass

    threading.Thread(target=_do_temp, daemon=True).start()

