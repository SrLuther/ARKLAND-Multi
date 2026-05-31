"""
S4.1 — Tribe Log Viewer.
Visualiza e filtra o TribeLog.log do servidor em tempo real (tail a cada 5s).
"""
from __future__ import annotations

import re
import threading
import tkinter as tk
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import get_theme
from ..asm_engine.asm_server_config import AsmServerConfig

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

# Regex para parsear linhas do TribeLog
_LINE_RE = re.compile(
    r"^Day\s+(?P<day>\d+),\s+(?P<time>[\d:]+):\s+(?P<body>.+)$"
)

# Classificação de eventos
_EVENT_TYPES = {
    "killed":     (r"\bkilled\b|\bdestroyed\b",          "#ef4444"),  # vermelho
    "structure":  (r"\bstructure\b|\bbuilt\b|\bplaced\b", "#f59e0b"),  # amarelo
    "tamed":      (r"\btamed\b|\btaming\b",               "#22c55e"),  # verde
    "admin":      (r"\bAdmin Command\b|\badminchat\b",    "#a855f7"),  # roxo
    "player":     (r"\bjoined\b|\bleft\b|\bdied\b",       "#38bdf8"),  # azul
}


def _classify(line: str) -> tuple[str, str]:
    """Retorna (tipo, cor) para a linha."""
    for etype, (pattern, color) in _EVENT_TYPES.items():
        if re.search(pattern, line, re.IGNORECASE):
            return etype, color
    return "other", "#94a3b8"


def _find_tribe_log(install_dir: str) -> Optional[Path]:
    """Localiza o arquivo TribeLog.log no diretório de instalação."""
    p = Path(install_dir) / "ShooterGame" / "Saved" / "Logs" / "TribeLog.log"
    return p if p.exists() else None


class _TribeLogWindow(ctk.CTkToplevel):
    def __init__(self, parent, srv: AsmServerConfig, app: "ARKServerManagerApp"):
        super().__init__(parent)
        th = get_theme("tek")
        bg = th["bg"]
        card_bg = th["card_bg"]
        sep = th["separator"]
        accent = th["accent"]
        t_sec = th["text_secondary"]
        t_mut = th["text_muted"]

        self.title(f"Tribe Log — {srv.name}")
        self.geometry("900x580")
        self.configure(fg_color=bg)
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self.lift)
        self.after(150, self.focus_force)

        self._srv = srv
        self._app = app
        self._log_path = _find_tribe_log(srv.install_dir) if srv.install_dir else None
        self._all_lines: List[dict] = []
        self._filter_type = tk.StringVar(value="Todos")
        self._filter_text = tk.StringVar()
        self._running = True
        self._last_pos = 0

        self._build_ui(bg, card_bg, sep, accent, t_sec, t_mut)
        self._start_tail()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self, bg, card_bg, sep, accent, t_sec, t_mut):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Toolbar
        tb = ctk.CTkFrame(self, fg_color=card_bg, corner_radius=0)
        tb.grid(row=0, column=0, sticky="ew")
        tb.grid_columnconfigure(5, weight=1)

        ctk.CTkLabel(tb, text="🔍", font=ctk.CTkFont(size=14)).grid(
            row=0, column=0, padx=(12, 4), pady=8)
        ctk.CTkEntry(tb, textvariable=self._filter_text,
                     placeholder_text="Filtrar texto...",
                     width=200, height=28).grid(row=0, column=1, padx=(0, 8), pady=8, sticky="w")
        self._filter_text.trace_add("write", lambda *_: self._apply_filter())

        # Chips de tipo
        types = ["Todos"] + list(_EVENT_TYPES.keys()) + ["other"]
        for i, t in enumerate(types):
            def _set_t(tv=t):
                self._filter_type.set(tv)
                self._apply_filter()
                self._refresh_chips()

            btn = ctk.CTkButton(
                tb, text=t.capitalize(), width=72, height=26,
                fg_color=accent if t == "Todos" else card_bg,
                hover_color="#1e3a5f", text_color="white" if t == "Todos" else t_sec,
                corner_radius=5, font=ctk.CTkFont(size=10),
                command=_set_t,
            )
            btn.grid(row=0, column=2 + i, padx=2, pady=8)
            setattr(self, f"_chip_{t}", btn)

        # Botões de ação
        ctk.CTkButton(
            tb, text="📋 Copiar", width=72, height=26,
            fg_color="#1e293b", hover_color="#263347",
            font=ctk.CTkFont(size=10), text_color=t_sec,
            command=self._copy_visible,
        ).grid(row=0, column=2 + len(types), padx=(8, 4), pady=8)

        ctk.CTkButton(
            tb, text="💾 Exportar", width=80, height=26,
            fg_color="#1e293b", hover_color="#263347",
            font=ctk.CTkFont(size=10), text_color=t_sec,
            command=self._export,
        ).grid(row=0, column=3 + len(types), padx=(0, 12), pady=8)

        # Linha log
        log_frame = ctk.CTkFrame(self, fg_color=bg, corner_radius=0)
        log_frame.grid(row=1, column=0, sticky="nsew")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)

        self._log_box = ctk.CTkTextbox(
            log_frame, fg_color="#060d14",
            text_color="#94a3b8",
            font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled",
        )
        self._log_box.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        # Tags de cor para os tipos
        for etype, (_, color) in _EVENT_TYPES.items():
            self._log_box._textbox.tag_configure(etype, foreground=color)
        self._log_box._textbox.tag_configure("other", foreground="#94a3b8")
        self._log_box._textbox.tag_configure("time", foreground="#475569")

        # Status bar
        self._status_lbl = ctk.CTkLabel(
            self, text="Aguardando log...", font=ctk.CTkFont(size=9),
            text_color=t_mut, anchor="w")
        self._status_lbl.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 4))

    def _refresh_chips(self):
        active = self._filter_type.get()
        th = get_theme("tek")
        for t in ["Todos"] + list(_EVENT_TYPES.keys()) + ["other"]:
            btn = getattr(self, f"_chip_{t}", None)
            if btn:
                is_active = (t == active)
                btn.configure(
                    fg_color=th["accent"] if is_active else th["card_bg"],
                    text_color="white" if is_active else th["text_secondary"],
                )

    # ── Tail ─────────────────────────────────────────────────────────────────

    def _start_tail(self):
        def _worker():
            if self._log_path and self._log_path.exists():
                with open(self._log_path, "r", encoding="utf-8", errors="replace") as fh:
                    fh.seek(0, 2)  # vai para o final do arquivo
                    self._last_pos = fh.tell()
                    # carrega as últimas 200 linhas
                    fh.seek(0)
                    lines = fh.readlines()[-200:]
                    for line in lines:
                        parsed = self._parse_line(line.rstrip())
                        if parsed:
                            self._all_lines.append(parsed)
                self.after(0, self._apply_filter)
                self._status_lbl.configure(text=str(self._log_path))

            while self._running:
                threading.Event().wait(5)
                if not self._running:
                    break
                self._tail_step()

        threading.Thread(target=_worker, daemon=True).start()

    def _tail_step(self):
        if not self._log_path or not self._log_path.exists():
            return
        try:
            with open(self._log_path, "r", encoding="utf-8", errors="replace") as fh:
                fh.seek(self._last_pos)
                new = fh.read()
                self._last_pos = fh.tell()
            if new.strip():
                for line in new.splitlines():
                    parsed = self._parse_line(line)
                    if parsed:
                        self._all_lines.append(parsed)
                self.after(0, self._apply_filter)
        except Exception:
            pass

    def _parse_line(self, raw: str) -> Optional[dict]:
        if not raw.strip():
            return None
        m = _LINE_RE.match(raw)
        if m:
            body = m.group("body")
            etype, color = _classify(body)
            return {"day": m.group("day"), "time": m.group("time"),
                    "body": body, "raw": raw, "type": etype, "color": color}
        etype, color = _classify(raw)
        return {"day": "", "time": "", "body": raw, "raw": raw,
                "type": etype, "color": color}

    # ── Filtro / Render ───────────────────────────────────────────────────────

    def _apply_filter(self, *_):
        ft = self._filter_type.get()
        txt = self._filter_text.get().strip().lower()

        filtered = [
            e for e in self._all_lines
            if (ft == "Todos" or e["type"] == ft)
            and (not txt or txt in e["raw"].lower())
        ]

        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        tb = self._log_box._textbox

        for entry in filtered[-500:]:  # máximo 500 linhas visíveis
            if entry["day"]:
                tb.insert("end", f"[Day {entry['day']} {entry['time']}] ", "time")
            tb.insert("end", entry["body"] + "\n", entry["type"])

        self._log_box.configure(state="disabled")
        self._log_box.see("end")

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _copy_visible(self):
        lines = [
            (f"[Day {e['day']} {e['time']}] " if e["day"] else "") + e["body"]
            for e in self._all_lines
        ]
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines[-500:]))

    def _export(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("CSV", "*.csv")],
            initialfile=f"tribelog_{self._srv.name}.txt",
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            for e in self._all_lines:
                prefix = f"[Day {e['day']} {e['time']}] " if e["day"] else ""
                fh.write(prefix + e["body"] + "\n")

    def _on_close(self):
        self._running = False
        self.destroy()


def open_asm_tribe_log(app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
    """Abre janela de Tribe Log (singleton por servidor)."""
    key = f"_asm_tribe_log_{srv.id}"
    existing = getattr(app, key, None)
    if existing and existing.winfo_exists():
        existing.lift()
        existing.focus_force()
        return
    win = _TribeLogWindow(app, srv, app)
    setattr(app, key, win)
