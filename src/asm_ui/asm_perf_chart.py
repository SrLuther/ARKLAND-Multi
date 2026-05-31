"""
asm_perf_chart.py — Gráfico de Performance em Tempo Real TEK.

Widget de gráfico de linha (Canvas tkinter) com histórico de 60 pontos
para CPU%, RAM% e jogadores online. Atualizado a cada 5s.

Uso:
    from src.asm_ui.asm_perf_chart import AsmPerfChart
    chart = AsmPerfChart(parent, srv, app)
    chart.pack(fill="both", expand=True)
    chart.start()
"""
from __future__ import annotations

import tkinter as tk
from collections import deque
from typing import TYPE_CHECKING, Callable, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp


_HISTORY_LEN  = 60   # pontos no gráfico (~5 min a 5s/tick)
_TICK_MS      = 5_000


def _try_psutil() -> bool:
    try:
        import psutil  # noqa: F401
        return True
    except ImportError:
        return False


class AsmPerfChart(ctk.CTkFrame):
    """Mini-gráfico de performance para um servidor ARK.

    Parâmetros
    ----------
    parent   : widget pai
    srv      : AsmServerConfig — usado para identificar o processo
    app      : ARKServerManagerApp — para chamar asm_server_manager
    on_players_fn : callable opcional → retorna int com jogadores online
    """

    _COLORS = {
        "cpu":     "#f59e0b",   # amarelo
        "ram":     "#38bdf8",   # azul
        "players": "#4ade80",   # verde
    }

    def __init__(
        self,
        parent: tk.Widget,
        srv: AsmServerConfig,
        app: "ARKServerManagerApp",
        on_players_fn: Optional[Callable[[], int]] = None,
    ) -> None:
        th = get_theme("tek")
        super().__init__(parent, fg_color=th["card_bg"], corner_radius=8)

        self._srv          = srv
        self._app          = app
        self._on_players   = on_players_fn
        self._after_id: Optional[str] = None
        self._running      = False
        self._has_psutil   = _try_psutil()

        self._hist_cpu:     deque[float] = deque([0.0] * _HISTORY_LEN, maxlen=_HISTORY_LEN)
        self._hist_ram:     deque[float] = deque([0.0] * _HISTORY_LEN, maxlen=_HISTORY_LEN)
        self._hist_players: deque[float] = deque([0.0] * _HISTORY_LEN, maxlen=_HISTORY_LEN)

        sep    = th.get("separator", "#1e293b")
        t_sec  = th.get("text_secondary", "#94a3b8")
        t_mut  = th.get("text_muted", "#475569")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Legenda / valores atuais ──────────────────────────────────────────
        legend = ctk.CTkFrame(self, fg_color="transparent")
        legend.grid(row=0, column=0, sticky="ew", padx=8, pady=(6, 2))

        self._cpu_lbl = ctk.CTkLabel(
            legend, text="CPU  0%",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=self._COLORS["cpu"],
        )
        self._cpu_lbl.pack(side="left", padx=(0, 14))

        self._ram_lbl = ctk.CTkLabel(
            legend, text="RAM  0%",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=self._COLORS["ram"],
        )
        self._ram_lbl.pack(side="left", padx=(0, 14))

        self._players_lbl = ctk.CTkLabel(
            legend, text="Players  0",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=self._COLORS["players"],
        )
        self._players_lbl.pack(side="left")

        if not self._has_psutil:
            ctk.CTkLabel(
                legend, text="(psutil não instalado)",
                font=ctk.CTkFont(size=10), text_color=t_mut,
            ).pack(side="right")

        # ── Canvas do gráfico ─────────────────────────────────────────────────
        self._canvas = tk.Canvas(
            self, bg="#04090f", highlightthickness=0, height=90,
        )
        self._canvas.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))

    # ── Ciclo de atualização ──────────────────────────────────────────────────

    def start(self) -> None:
        """Inicia o loop de atualização."""
        if self._running:
            return
        self._running = True
        self._tick()

    def stop(self) -> None:
        """Para o loop de atualização."""
        self._running = False
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _tick(self) -> None:
        if not self._running or not self.winfo_exists():
            return
        self._collect()
        self._draw_chart()
        self._after_id = self.after(_TICK_MS, self._tick)

    def _collect(self) -> None:
        """Coleta métricas de CPU, RAM e jogadores."""
        cpu_pct = 0.0
        ram_pct = 0.0
        players = 0

        if self._has_psutil:
            try:
                import psutil  # type: ignore[reportMissingImports]
                inst = self._app.asm_server_manager.get_instance(self._srv.id)
                if inst and inst.pid:
                    try:
                        proc = psutil.Process(inst.pid)
                        cpu_pct = proc.cpu_percent(interval=None)
                    except Exception:
                        pass
                ram_pct = psutil.virtual_memory().percent
            except Exception:
                pass

        if self._on_players:
            try:
                players = self._on_players()
            except Exception:
                pass

        self._hist_cpu.append(cpu_pct)
        self._hist_ram.append(ram_pct)
        self._hist_players.append(float(players))

        self._cpu_lbl.configure(text=f"CPU  {cpu_pct:.0f}%")
        self._ram_lbl.configure(text=f"RAM  {ram_pct:.0f}%")
        self._players_lbl.configure(text=f"Players  {players}")

    # ── Desenho do gráfico ────────────────────────────────────────────────────

    def _draw_chart(self) -> None:
        c = self._canvas
        if not c.winfo_exists():
            return
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w <= 1 or h <= 1:
            return

        n = _HISTORY_LEN
        step = w / (n - 1)
        pad  = 4

        def _polyline(series: deque, max_val: float, color: str) -> None:
            if max_val <= 0:
                return
            pts = []
            for i, v in enumerate(series):
                x = i * step
                y = h - pad - (v / max_val) * (h - pad * 2)
                pts.extend([x, y])
            if len(pts) >= 4:
                c.create_line(pts, fill=color, width=1, smooth=True)

        # Linhas de grade horizontais (25%, 50%, 75%, 100%)
        for pct in (0.25, 0.5, 0.75, 1.0):
            y = h - pad - pct * (h - pad * 2)
            c.create_line(0, y, w, y, fill="#1e293b", width=1, dash=(2, 4))

        max_players = max(max(self._hist_players), 1.0)
        _polyline(self._hist_cpu,     100.0,       self._COLORS["cpu"])
        _polyline(self._hist_ram,     100.0,       self._COLORS["ram"])
        _polyline(self._hist_players, max_players, self._COLORS["players"])


# ─────────────────────────────────────────────────────────────────────────────
# Janela autônoma de performance
# ─────────────────────────────────────────────────────────────────────────────


def open_asm_perf_window(app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
    """Abre janela flutuante com gráfico de performance para *srv*."""
    win_attr = f"_asm_perf_win_{srv.id}"
    existing: Optional[ctk.CTkToplevel] = getattr(app, win_attr, None)
    if existing and existing.winfo_exists():
        existing.lift()
        existing.focus_force()
        return

    th = get_theme("tek")
    win = ctk.CTkToplevel(app)
    win.title(f"Performance — {srv.name}")
    win.geometry("500x180")
    win.configure(fg_color=th["bg"])
    win.grid_columnconfigure(0, weight=1)
    win.grid_rowconfigure(0, weight=1)

    chart = AsmPerfChart(win, srv, app)
    chart.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
    chart.start()

    def _on_close() -> None:
        chart.stop()
        setattr(app, win_attr, None)
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", _on_close)
    setattr(app, win_attr, win)
    win.after(100, win.lift)
    win.after(150, win.focus_force)
