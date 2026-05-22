from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def on_sync_stats(app: "ARKServerManagerApp", stats: dict) -> None:
    def _do():
        if app._sync_stats_lbl:
            app._sync_stats_lbl.configure(
                text=(f"Ciclos: {stats.get('cycles', 0)}  |  "
                      f"Arquivos: {stats.get('total_synced', 0)}  |  "
                      f"Erros: {stats.get('errors', 0)}  |  "
                      f"Último: {stats.get('last_sync', '—')}"))
    app.after(0, _do)

