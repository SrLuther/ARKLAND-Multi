from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _GREEN
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def on_server_visibility_change(app: "ARKServerManagerApp", server_id: str, mode: str) -> None:
    """Callback chamado quando o online_mode de um servidor muda (—/LAN/WAN)."""
    def _do():
        w = app._server_widgets.get(server_id, {})
        vis_lbl: Optional[ctk.CTkLabel] = w.get("_visibility_lbl")
        if vis_lbl:
            if mode == "WAN":
                vis_lbl.configure(text="🌐 WAN", text_color=_GREEN)
            elif mode == "LAN":
                vis_lbl.configure(text="🏠 LAN", text_color="#ffaa44")
            else:
                vis_lbl.configure(text="", text_color="gray50")
        app._refresh_dashboard()
    app.after(0, _do)

