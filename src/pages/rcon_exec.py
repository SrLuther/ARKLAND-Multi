from __future__ import annotations
import threading
from datetime import datetime
from typing import TYPE_CHECKING
from ..ui_constants import _RED_DARK, _RED_HOVER
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def rcon_exec(app: "ARKServerManagerApp", server_id: str, command: str) -> None:
    """Executa um comando RCON com retry automático (3 tentativas) e feedback na UI."""
    client = app._rcon_clients.get(server_id)
    ts = datetime.now().strftime("%H:%M:%S")
    app._rcon_append(server_id, f"[{ts}] ", "ts")
    app._rcon_append(server_id, f"> {command}\n", "cmd")

    if not client:
        app._rcon_append(
            server_id,
            "Não conectado. Clique em 'Conectar' primeiro.\n",
            "err",
        )
        return

    was_connected_before = client.is_connected

    def _do() -> None:
        ok, result = client.send_command_with_retry(command, retries=3)

        def _update() -> None:
            # Reconexão silenciosa — atualiza indicadores de status na UI
            if not was_connected_before and ok:
                w   = app._server_widgets.get(server_id, {})
                sv  = w.get("rcon_status_var")
                btn = w.get("rcon_connect_btn")
                host, port = client._host, client._port
                if sv:
                    sv.set(f"🟢 {host}:{port}")
                if btn:
                    btn.configure(
                        text="🔌 Desconectar",
                        fg_color=_RED_DARK,
                        hover_color=_RED_HOVER,
                    )
                app._rcon_append(server_id, f"[Auto-reconectado a {host}:{port}]\n", "sys")

            if ok:
                display = result if result.strip() else "(ok — sem resposta textual)"
                app._rcon_append(server_id, display + "\n", "resp")
            else:
                app._rcon_append(
                    server_id,
                    f"❌ Falha: {result or 'sem resposta'}\n",
                    "err",
                )

        app.after(0, _update)

    threading.Thread(target=_do, daemon=True).start()

