from __future__ import annotations
import threading
from typing import TYPE_CHECKING
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def broadcast_test(app: "ARKServerManagerApp", server_id: str) -> None:
    """Envia uma mensagem de teste para verificar se o RCON/broadcast está funcionando."""
    srv = app.config_manager.get_server(server_id)
    if not srv or not srv.rcon_enabled or not srv.rcon_password:
        messagebox.showwarning(
            "RCON não configurado",
            "Habilite o RCON e defina a senha nas configurações do servidor antes de testar.",
            parent=app,
        )
        return

    safe = "[ARKLAND] \u2705 Teste de broadcast \u2014 RCON funcionando corretamente!"
    existing = app._rcon_clients.get(server_id)
    rcon_port = srv.rcon_port
    rcon_pass = srv.rcon_password

    def _do() -> None:
        try:
            if existing and existing.is_connected:
                ok, resp = existing.send_command_safe(f"Broadcast {safe}")
            else:
                tmp = RconClient("127.0.0.1", rcon_port, rcon_pass)
                ok, resp = tmp.send_command_safe(f"Broadcast {safe}")
                tmp.disconnect()
            if ok:
                app.after(0, lambda: messagebox.showinfo(
                    "Broadcast de teste",
                    "\u2705 Mensagem de teste enviada com sucesso!\n"
                    "Se o servidor estiver online, a mensagem aparecerá para todos os jogadores.",
                    parent=app,
                ))
            else:
                app.after(0, lambda r=resp: messagebox.showerror(
                    "Falha no broadcast",
                    f"\u274c RCON retornou erro:\n{r}\n\n"
                    "Verifique se o servidor está online e a senha RCON está correta.",
                    parent=app,
                ))
        except Exception as exc:
            app.after(0, lambda e=str(exc): messagebox.showerror(
                "Falha no broadcast",
                f"\u274c Não foi possível conectar ao RCON:\n{e}\n\n"
                "Verifique se o servidor está online e a porta RCON está correta.",
                parent=app,
            ))

    threading.Thread(target=_do, daemon=True).start()

