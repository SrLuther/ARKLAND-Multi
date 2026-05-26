"""
Componentes de UI reutilizáveis — sem overhead de CTkScrollableFrame.

FastScrollFrame: substitui CTkScrollableFrame em todos os containers de página.
  - 1 canvas por página (em vez de O(n) por widget)
  - scroll region calculada uma única vez ao final do build
  - mouse wheel apenas quando o cursor está sobre o frame (evita conflitos entre páginas)

ServerTabBar: barra de tabs de servidor sempre visível.
  - troca de servidor = grid_remove/grid (0ms, sem rebuild)
  - suporte a status dot colorido por servidor
  - botão [+] para adicionar novo servidor
"""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Callable, Dict, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

if TYPE_CHECKING:
    from .app import ARKServerManagerApp


# ══════════════════════════════════════════════════════════════════════════════
# FastScrollFrame
# ══════════════════════════════════════════════════════════════════════════════

class FastScrollFrame(tk.Frame):
    """Container scrollável leve baseado em tk.Canvas nativo.

    Diferença crítica vs CTkScrollableFrame:
        CTkScrollableFrame  → cada widget filho dispara <Configure> no canvas → O(n²)
        FastScrollFrame     → 1 evento <Configure> no inner frame ao final → O(1)

    Uso:
        sf = FastScrollFrame(parent, bg="#111118")
        sf.grid(row=0, column=0, sticky="nsew")
        # adicionar widgets em sf.inner  (tk.Frame nativo)
        label = tk.Label(sf.inner, text="Olá", bg="#111118", fg="white")
        label.grid(row=0, column=0)
    """

    def __init__(self, parent, bg: str = "#111118", **kw):
        super().__init__(parent, bg=bg, **kw)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._bg = bg
        self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self._vsb = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self.inner = tk.Frame(self._canvas, bg=bg)

        self._win_id = self._canvas.create_window(0, 0, anchor="nw", window=self.inner)
        self._canvas.configure(yscrollcommand=self._vsb.set)

        self._canvas.grid(row=0, column=0, sticky="nsew")
        self._vsb.grid(row=0, column=1, sticky="ns")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<Enter>", self._bind_wheel)
        self._canvas.bind("<Leave>", self._unbind_wheel)
        self.inner.bind("<Enter>", self._bind_wheel)
        self.inner.bind("<Leave>", self._unbind_wheel)

    # ── handlers ─────────────────────────────────────────────────────────────

    def _on_inner_configure(self, _event) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        self._canvas.itemconfig(self._win_id, width=event.width)

    def _bind_wheel(self, _event) -> None:
        self._canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self, _event) -> None:
        self._canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event) -> None:
        self._canvas.yview_scroll(int(-1 * event.delta / 120), "units")

    # ── utilitário ────────────────────────────────────────────────────────────

    def scroll_to_top(self) -> None:
        self._canvas.yview_moveto(0)


# ══════════════════════════════════════════════════════════════════════════════
# ServerTabBar
# ══════════════════════════════════════════════════════════════════════════════

_TAB_H = 38          # altura de cada tab
_TAB_MIN_W = 130     # largura mínima por tab
_TAB_MAX_W = 200     # largura máxima por tab


class ServerTabBar(tk.Frame):
    """Barra de tabs de servidor — troca instantânea, sem rebuild.

    Cada tab mostra: [● dot status]  [nome]  [× fechar]
    """

    def __init__(
        self,
        parent,
        on_select: Callable[[str], None],
        on_add: Callable[[], None],
        on_close: Callable[[str], None],
        accent: str = "#4CAF50",
        bg: str = "#161622",
        **kw,
    ):
        super().__init__(parent, bg=bg, height=_TAB_H, **kw)
        self.pack_propagate(False)

        self._on_select = on_select
        self._on_add = on_add
        self._on_close = on_close
        self._accent = accent
        self._bg = bg
        self._active_id: Optional[str] = None
        self._tabs: Dict[str, Dict] = {}   # server_id → {frame, dot, label}

        # Botão [+] — lado direito (pack antes do _inner para não ser empurrado)
        self._add_btn = tk.Label(
            self,
            text="  ＋  ",
            bg=bg, fg="#88d4a0",
            font=("Segoe UI", 13),
            cursor="hand2",
        )
        self._add_btn.pack(side="right", padx=(0, 6))
        self._add_btn.bind("<Button-1>", lambda _: self._on_add())

        # Container interno de tabs
        self._inner = tk.Frame(self, bg=bg)
        self._inner.pack(side="left", fill="both", expand=True)

    # ── API pública ───────────────────────────────────────────────────────────

    def add_tab(self, server_id: str, name: str, status_color: str = "#ff6666") -> None:
        """Adiciona ou atualiza uma tab para o servidor."""
        if server_id in self._tabs:
            self.update_tab(server_id, name, status_color)
            return

        tab_frame = tk.Frame(
            self._inner, bg=self._bg,
            cursor="hand2",
        )
        tab_frame.pack(side="left", fill="y", padx=(0, 1))

        dot = tk.Label(tab_frame, text="●", fg=status_color, bg=self._bg,
                       font=("Segoe UI", 8))
        dot.pack(side="left", padx=(10, 4), pady=0)

        lbl = tk.Label(tab_frame, text=name, bg=self._bg, fg="#d8d8e8",
                       font=("Segoe UI", 11), anchor="w")
        lbl.pack(side="left", fill="x", expand=True, pady=0)

        close_btn = tk.Label(tab_frame, text=" × ", bg=self._bg, fg="#666680",
                             font=("Segoe UI", 11), cursor="hand2")
        close_btn.pack(side="left", padx=(4, 6))

        # bindings
        for widget in (tab_frame, dot, lbl):
            widget.bind("<Button-1>", lambda _, sid=server_id: self._select(sid))
        close_btn.bind("<Button-1>", lambda _, sid=server_id: self._close(sid))
        close_btn.bind("<Enter>", lambda _, w=close_btn: w.configure(fg="#ff6666"))
        close_btn.bind("<Leave>", lambda _, w=close_btn: w.configure(fg="#666680"))

        self._tabs[server_id] = {
            "frame": tab_frame, "dot": dot, "label": lbl, "close": close_btn,
        }

    def remove_tab(self, server_id: str) -> None:
        """Remove a tab do servidor."""
        tab = self._tabs.pop(server_id, None)
        if tab:
            tab["frame"].destroy()
        if self._active_id == server_id:
            self._active_id = None

    def update_tab(self, server_id: str, name: str, status_color: str) -> None:
        """Atualiza nome e cor do dot sem recriar a tab."""
        tab = self._tabs.get(server_id)
        if not tab:
            return
        tab["label"].configure(text=name)
        tab["dot"].configure(fg=status_color)

    def set_active(self, server_id: Optional[str]) -> None:
        """Marca a tab como ativa (highlight de cor)."""
        # Desativa a anterior
        if self._active_id and self._active_id in self._tabs:
            prev = self._tabs[self._active_id]
            prev["frame"].configure(bg=self._bg)
            prev["dot"].configure(bg=self._bg)
            prev["label"].configure(bg=self._bg, fg="#d8d8e8")
            prev["close"].configure(bg=self._bg)

        self._active_id = server_id

        if server_id and server_id in self._tabs:
            cur = self._tabs[server_id]
            active_bg = "#1e1e30"
            cur["frame"].configure(bg=active_bg)
            cur["dot"].configure(bg=active_bg)
            cur["label"].configure(bg=active_bg, fg="#ffffff",
                                   font=("Segoe UI", 11, "bold"))
            cur["close"].configure(bg=active_bg)

    def set_accent(self, accent: str) -> None:
        """Atualiza a cor de acento (ao trocar de modo PRIMITIVE/TEK)."""
        self._accent = accent

    def clear(self) -> None:
        """Remove todas as tabs."""
        for sid in list(self._tabs.keys()):
            self.remove_tab(sid)

    @property
    def active_id(self) -> Optional[str]:
        return self._active_id

    # ── handlers internos ─────────────────────────────────────────────────────

    def _select(self, server_id: str) -> None:
        self._on_select(server_id)

    def _close(self, server_id: str) -> None:
        self._on_close(server_id)
