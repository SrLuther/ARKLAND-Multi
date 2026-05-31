"""
S5.3 — Monitor Avançado de Servidor.
CPU%, RAM%, players em tempo real + histórico 24h + alertas configuráveis.
"""
from __future__ import annotations

import threading
import time
import tkinter as tk
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Tuple, TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import get_theme
from ..asm_engine.asm_server_config import AsmServerConfig, ASM_STATUS_RUNNING

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

# Comprimento máximo do histórico (~24h com coleta a cada 30s = 2880 pontos)
_MAX_HISTORY = 2880
_POLL_INTERVAL_S = 30


def _get_process_stats(pid: int) -> Tuple[float, float]:
    """Retorna (cpu_pct, rss_mb) para o PID dado. Requer psutil."""
    try:
        import psutil  # type: ignore[reportMissingModuleSource]
        p = psutil.Process(pid)
        cpu = p.cpu_percent(interval=1)
        rss = p.memory_info().rss / (1024 * 1024)
        return cpu, rss
    except Exception:
        return 0.0, 0.0


def _get_player_count(srv: AsmServerConfig) -> int:
    """Faz query RCON para obter número de players. Retorna -1 se falhar."""
    if not srv.rcon_enabled or not srv.admin_password:
        return -1
    try:
        from ..rcon_client import RconClient
        rc = RconClient(srv.rcon_host or "127.0.0.1", srv.rcon_port, srv.admin_password)
        rc.connect()
        ok, resp = rc.send_command_safe("ListPlayers")
        rc.disconnect()
        if not ok:
            return -1
        # ListPlayers retorna "1. Nome, SteamID" ou "No Players Connected"
        if "no players" in resp.lower():
            return 0
        return sum(1 for line in resp.splitlines() if line.strip() and line[0].isdigit())
    except Exception:
        return -1


class _MonitorData:
    """Buffer de histórico de métricas."""

    def __init__(self):
        self.cpu:     Deque[float] = deque(maxlen=_MAX_HISTORY)
        self.ram:     Deque[float] = deque(maxlen=_MAX_HISTORY)
        self.players: Deque[int]   = deque(maxlen=_MAX_HISTORY)
        self.times:   Deque[str]   = deque(maxlen=_MAX_HISTORY)
        self.lock = threading.Lock()

    def push(self, cpu: float, ram: float, players: int):
        ts = datetime.now().strftime("%H:%M")
        with self.lock:
            self.cpu.append(cpu)
            self.ram.append(ram)
            self.players.append(players)
            self.times.append(ts)

    def snapshot(self):
        with self.lock:
            return (
                list(self.cpu), list(self.ram),
                list(self.players), list(self.times),
            )


class _MonitorWindow(ctk.CTkToplevel):
    def __init__(self, parent, srv: AsmServerConfig, app: "ARKServerManagerApp"):
        super().__init__(parent)
        th = get_theme("tek")
        self._bg    = th["bg"]
        self._cg    = th["card_bg"]
        self._sep   = th["separator"]
        self._acc   = th["accent"]
        self._t_sec = th["text_secondary"]
        self._t_mut = th["text_muted"]

        self.title(f"Monitor — {srv.name}")
        self.geometry("820x560")
        self.configure(fg_color=self._bg)
        self.resizable(True, True)
        self.after(100, self.lift)
        self.after(150, self.focus_force)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._srv = srv
        self._app = app
        self._data = _MonitorData()
        self._running = True

        # Alertas configuráveis (cpu_limit, ram_limit, players_limit)
        self._alert_cpu_var     = tk.StringVar(value="90")
        self._alert_ram_var     = tk.StringVar(value="85")
        self._alert_players_var = tk.StringVar(value="65")
        self._alert_discord_var = tk.BooleanVar(value=False)
        self._alert_restart_var = tk.BooleanVar(value=False)

        self._build_ui()
        self._start_poller()
        self._tick_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Toolbar / stats instantâneos
        tb = ctk.CTkFrame(self, fg_color=self._cg, corner_radius=0)
        tb.grid(row=0, column=0, sticky="ew")
        tb.grid_columnconfigure((1, 3, 5), weight=1)

        self._stat_labels: Dict[str, ctk.CTkLabel] = {}
        for i, (key, label, color) in enumerate([
            ("cpu",     "CPU",      "#a78bfa"),
            ("ram",     "RAM",      "#f472b6"),
            ("players", "Players",  "#22c55e"),
            ("status",  "Status",   "#60a5fa"),
        ]):
            col = i * 2
            ctk.CTkLabel(tb, text=label,
                         font=ctk.CTkFont(size=9), text_color=self._t_mut,
                         ).grid(row=0, column=col, padx=(16 if col == 0 else 8, 2), pady=(8, 0), sticky="sw")
            lbl = ctk.CTkLabel(tb, text="—",
                               font=ctk.CTkFont(size=20, weight="bold"),
                               text_color=color)
            lbl.grid(row=1, column=col, padx=(16 if col == 0 else 8, 2), pady=(0, 8), sticky="nw")
            self._stat_labels[key] = lbl

        # Linha separadora entre stat blocks
        for sep_col in (1, 3, 5):
            ctk.CTkFrame(tb, width=1, fg_color=self._sep).grid(
                row=0, column=sep_col, rowspan=2, sticky="ns", padx=0, pady=8)

        # Botão de configurar alertas
        ctk.CTkButton(
            tb, text="🔔 Alertas", width=90, height=28,
            fg_color=self._sep, hover_color="#263347",
            font=ctk.CTkFont(size=10), text_color=self._t_sec,
            command=self._open_alert_config,
        ).grid(row=0, column=8, rowspan=2, padx=(0, 12), pady=8)

        # Linha separadora
        ctk.CTkFrame(self, height=1, fg_color=self._sep).grid(row=0, column=0, sticky="ews")

        # Painel de gráficos (tabview com CPU / RAM / Players)
        self._tabview = ctk.CTkTabview(self, fg_color=self._bg, corner_radius=0)
        self._tabview.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        for tab_name in ("CPU%", "RAM (MB)", "Players"):
            self._tabview.add(tab_name)
            self._tabview.tab(tab_name).grid_columnconfigure(0, weight=1)
            self._tabview.tab(tab_name).grid_rowconfigure(0, weight=1)

        # Canvas de gráfico para cada aba
        self._canvases: Dict[str, tk.Canvas] = {}
        for i, tab_name in enumerate(("CPU%", "RAM (MB)", "Players")):
            c = tk.Canvas(self._tabview.tab(tab_name),
                          bg="#060d14", highlightthickness=0)
            c.grid(row=0, column=0, sticky="nsew")
            self._canvases[tab_name] = c

    def _tick_ui(self):
        """Atualiza os stat labels e redesenha os gráficos a cada 2s."""
        if not self._running or not self.winfo_exists():
            return
        cpus, rams, players, times = self._data.snapshot()
        if cpus:
            self._stat_labels["cpu"].configure(text=f"{cpus[-1]:.0f}%")
            self._stat_labels["ram"].configure(text=f"{rams[-1]:.0f} MB")
            last_pl = players[-1]
            self._stat_labels["players"].configure(
                text=str(last_pl) if last_pl >= 0 else "N/D")
        # Status
        inst = self._app.asm_server_manager.get_instance(self._srv.id)
        status_text = "ONLINE" if (inst and inst.status == ASM_STATUS_RUNNING) else "OFFLINE"
        status_color = "#22c55e" if status_text == "ONLINE" else "#64748b"
        self._stat_labels["status"].configure(text=status_text, text_color=status_color)

        # Redesenha gráficos
        self._draw_chart("CPU%",     cpus,    "#a78bfa", 0, 100)
        self._draw_chart("RAM (MB)", rams,    "#f472b6")
        pl_clean = [p for p in players if p >= 0]
        self._draw_chart("Players",  pl_clean, "#22c55e", 0)

        self.after(2000, self._tick_ui)

    def _draw_chart(self, tab: str, values: List[float], color: str,
                    y_min: float = None, y_max: float = None):
        c = self._canvases.get(tab)
        if not c:
            return
        c.delete("all")
        if len(values) < 2:
            c.create_text(10, 10, anchor="nw", text="Coletando dados...",
                          fill="#475569", font=("Consolas", 10))
            return

        w = c.winfo_width()  or 600
        h = c.winfo_height() or 300
        pad_l, pad_r, pad_t, pad_b = 48, 12, 12, 28

        y0 = y_min if y_min is not None else min(values)
        y1 = y_max if y_max is not None else max(values)
        if y1 == y0:
            y1 = y0 + 1

        # Grid horizontal
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = pad_t + (h - pad_t - pad_b) * (1 - frac)
            val = y0 + (y1 - y0) * frac
            c.create_line(pad_l, y, w - pad_r, y, fill="#1e293b", dash=(2, 4))
            c.create_text(pad_l - 4, y, anchor="e", text=f"{val:.0f}",
                          fill="#475569", font=("Consolas", 8))

        # Linha do gráfico
        pts = []
        n = len(values)
        for i, v in enumerate(values):
            x = pad_l + (w - pad_l - pad_r) * i / (n - 1)
            y = pad_t + (h - pad_t - pad_b) * (1 - (v - y0) / (y1 - y0))
            pts.append((x, y))

        flat = [c_ for p in pts for c_ in p]
        if len(flat) >= 4:
            c.create_line(*flat, fill=color, width=1.5, smooth=True)

        # Área preenchida
        area_pts = [(pad_l, h - pad_b)] + pts + [(pts[-1][0], h - pad_b)]
        flat_area = [c_ for p in area_pts for c_ in p]
        if len(flat_area) >= 6:
            c.create_polygon(*flat_area, fill=color, stipple="gray25", outline="")

    # ── Alertas ───────────────────────────────────────────────────────────────

    def _open_alert_config(self):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Configurar Alertas")
        dlg.geometry("340x280")
        dlg.configure(fg_color=self._cg)
        dlg.after(100, dlg.lift)

        ctk.CTkLabel(dlg, text="Limites de alerta",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=self._acc).pack(pady=(16, 8))

        for label, var in [
            ("CPU > (%)", self._alert_cpu_var),
            ("RAM > (%)", self._alert_ram_var),
            ("Players >", self._alert_players_var),
        ]:
            row = ctk.CTkFrame(dlg, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=3)
            ctk.CTkLabel(row, text=label, width=100, anchor="w",
                         font=ctk.CTkFont(size=11), text_color=self._t_sec,
                         ).pack(side="left")
            ctk.CTkEntry(row, textvariable=var, width=80, height=26).pack(side="left")

        ctk.CTkCheckBox(dlg, text="Notificar Discord",
                        variable=self._alert_discord_var,
                        text_color=self._t_sec, border_color=self._acc,
                        checkmark_color=self._acc).pack(anchor="w", padx=20, pady=4)
        ctk.CTkCheckBox(dlg, text="Reiniciar automaticamente ao ultrapassar limite",
                        variable=self._alert_restart_var,
                        text_color=self._t_sec, border_color=self._acc,
                        checkmark_color=self._acc).pack(anchor="w", padx=20, pady=4)
        ctk.CTkButton(dlg, text="Fechar", width=100, height=28,
                      command=dlg.destroy).pack(pady=12)

    # ── Poller ────────────────────────────────────────────────────────────────

    def _start_poller(self):
        def _worker():
            while self._running:
                inst = self._app.asm_server_manager.get_instance(self._srv.id)
                pid  = getattr(inst, "pid", None) if inst else None

                cpu, ram = (0.0, 0.0) if pid is None else _get_process_stats(pid)
                players  = _get_player_count(self._srv) if inst else -1
                self._data.push(cpu, ram, players)
                self._check_alerts(cpu, ram, players)

                for _ in range(_POLL_INTERVAL_S * 2):
                    if not self._running:
                        return
                    time.sleep(0.5)

        threading.Thread(target=_worker, daemon=True).start()

    def _check_alerts(self, cpu: float, ram: float, players: int):
        try:
            cpu_lim = float(self._alert_cpu_var.get())
            ram_lim = float(self._alert_ram_var.get())
            pl_lim  = int(self._alert_players_var.get())
        except (ValueError, TypeError):
            return

        triggered = []
        if cpu > cpu_lim:
            triggered.append(f"CPU: {cpu:.0f}% > {cpu_lim:.0f}%")
        if ram > 0 and ram > ram_lim:
            triggered.append(f"RAM: {ram:.0f}MB > {ram_lim:.0f}%")
        if players >= 0 and players > pl_lim:
            triggered.append(f"Players: {players} > {pl_lim}")

        if not triggered:
            return

        msg = f"[{self._srv.name}] Alerta: {', '.join(triggered)}"
        if self._alert_discord_var.get():
            self._notify_discord(msg)
        if self._alert_restart_var.get():
            self.after(0, lambda: self._app._asm_restart_server(self._srv))

    def _notify_discord(self, msg: str):
        wh = getattr(self._srv, "discord_webhook_url", "") or ""
        if not wh:
            return
        try:
            import urllib.request
            body = json.dumps({"content": msg}).encode()
            req = urllib.request.Request(wh, data=body,
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)  # noqa: S310
        except Exception:
            pass

    def _on_close(self):
        self._running = False
        self.destroy()


def open_asm_monitor(app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
    """Abre janela de monitor avançado (singleton por servidor)."""
    key = f"_asm_monitor_{srv.id}"
    existing = getattr(app, key, None)
    if existing and existing.winfo_exists():
        existing.lift()
        existing.focus_force()
        return
    win = _MonitorWindow(app, srv, app)
    setattr(app, key, win)


# ── Fix missing import in _notify_discord ────────────────────────────────────
import json  # noqa: E402 (needed for _notify_discord)
