from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import (_GREEN_DARK, _GREEN_HOVER, _RED_DARK, _RED_HOVER,
                             _STATUS_COLOR, _STATUS_LABEL)
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp
from ..server_config import SERVER_STATUS_CRASHED, SERVER_STATUS_RUNNING, SERVER_STATUS_STARTING, SERVER_STATUS_STOPPED, SERVER_STATUS_STOPPING


def on_server_status_change(app: "ARKServerManagerApp", server_id: str, status: str) -> None:
    def _do():
        color = _STATUS_COLOR.get(status, "#ff6666")
        label = _STATUS_LABEL.get(status, status)

        w = app._server_widgets.get(server_id, {})
        sv: Optional[tk.StringVar]  = w.get("_status_var")
        sl: Optional[ctk.CTkLabel]  = w.get("_status_lbl")
        ss: Optional[ctk.CTkButton] = w.get("_start_stop_btn")
        if sv:
            sv.set(label)
        if sl:
            sl.configure(text_color=color)
        if ss:
            is_running = status == SERVER_STATUS_RUNNING
            is_busy    = status in (SERVER_STATUS_STARTING, SERVER_STATUS_STOPPING)
            is_crashed = status == SERVER_STATUS_CRASHED
            if is_busy:
                ss.configure(
                    text="⚡ Cancelar",
                    fg_color="#7a4a00", hover_color="#5c3600",
                    state="normal",
                )
            elif is_crashed:
                ss.configure(
                    text="💀 Forçar Enc.",
                    fg_color=_RED_DARK, hover_color=_RED_HOVER,
                    state="normal",
                )
            elif is_running:
                ss.configure(
                    text="⏹ Parar",
                    fg_color=_RED_DARK, hover_color=_RED_HOVER,
                    state="normal",
                )
            else:
                ss.configure(
                    text="▶ Iniciar",
                    fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                    state="normal",
                )

        # Bloquear/desbloquear configurações
        app._set_config_editable(server_id, status == SERVER_STATUS_STOPPED)

        # ── Auto-reconexão RCON ───────────────────────────────────────
        if status == SERVER_STATUS_RUNNING:
            # habilita auto-connect e agenda o primeiro loop
            app._rcon_auto_enabled[server_id] = True
            app._rcon_schedule_auto_connect(server_id, delay_ms=5000)
        elif status == SERVER_STATUS_STOPPED:
            # servidor parou: cancela loop e desconecta RCON
            app._rcon_auto_enabled[server_id] = False
            app._rcon_cancel_auto_job(server_id)
            client = app._rcon_clients.pop(server_id, None)
            if client:
                try:
                    client.disconnect()
                except Exception:
                    pass
            w2 = app._server_widgets.get(server_id, {})
            sv2 = w2.get("rcon_status_var")
            cb2 = w2.get("rcon_connect_btn")
            if sv2:
                sv2.set("⬛ Desconectado")
            if cb2:
                cb2.configure(text="🔌 Conectar",
                              fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER)

        btn = app._sidebar_server_btns.get(server_id)
        if btn:
            dot = getattr(btn, "_status_dot", None)
            if dot:
                dot.configure(text_color=color)

        app._refresh_dashboard()
    app.after(0, _do)

