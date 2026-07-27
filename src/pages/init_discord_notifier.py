from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def init_discord_notifier(app: "ARKServerManagerApp") -> None:
    """Inicializa o notificador global de webhooks Discord + painel de status."""
    from ..discord_notifier import DiscordNotifier
    from ..discord_status_board import boot_status_board

    app._discord_notifier = DiscordNotifier(app.config_manager.config.discord_notify)
    # Arranque: limpa o canal de status e publica painel novo.
    try:
        boot_status_board(app)
    except Exception:
        pass
