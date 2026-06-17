from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def init_discord_notifier(app: "ARKServerManagerApp") -> None:
    """Inicializa o notificador global de webhooks Discord."""
    from ..discord_notifier import DiscordNotifier

    app._discord_notifier = DiscordNotifier(app.config_manager.config.discord_notify)
