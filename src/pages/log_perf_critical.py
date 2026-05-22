from __future__ import annotations
from typing import TYPE_CHECKING
import datetime
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def log_perf_critical(app: "ARKServerManagerApp", metric: str, pct: float, state: str) -> None:
    """Registra um ponto crítico no histórico do painel de Desempenho."""
    import datetime
    ts    = datetime.datetime.now().strftime("%d/%m %H:%M:%S")
    label = {"cpu": "CPU", "ram": "RAM", "gpu": "GPU"}.get(metric, metric.upper())
    if state == "ok":
        icon, nivel = "🟢", "recuperado"
    elif state == "warn":
        icon, nivel = "🟡", "AVISO"
    else:
        icon, nivel = "🔴", "CRÍTICO"
    line = f"[{ts}]  {icon}  {label}: {pct:.0f}%  →  {nivel}\n"

    def _do():
        box = app._perf_critical_log
        if box:
            box.configure(state="normal")
            box.insert("end", line)
            box.see("end")
            box.configure(state="disabled")
    try:
        app.after(0, _do)
    except Exception:
        pass

