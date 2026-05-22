from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import _SIDEBAR_BG
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_config_search_bar(app: "ARKServerManagerApp", parent: "ctk.CTkFrame", server_id: str) -> None:
    """Barra de busca flutuante que filtra todas as configurações por rótulo/dica/aba."""
    bar = ctk.CTkFrame(parent, fg_color=_SIDEBAR_BG, corner_radius=0, height=40)
    bar.grid(row=1, column=0, sticky="ew")
    bar.grid_propagate(False)
    bar.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(bar, text="🔍", font=ctk.CTkFont(size=13), width=28,
                 text_color="gray50").grid(row=0, column=0, padx=(10, 0), pady=8)

    search_var = tk.StringVar()
    entry = ctk.CTkEntry(
        bar, textvariable=search_var, height=26, corner_radius=6,
        placeholder_text="Buscar configuração...",
        fg_color="#16162a", border_color="#2a2a4a", border_width=1,
        font=ctk.CTkFont(size=11),
    )
    entry.grid(row=0, column=1, padx=(4, 12), pady=7, sticky="ew")

    popup: list = [None]

    def _hide() -> None:
        if popup[0]:
            try:
                popup[0].destroy()
            except Exception:
                pass
            popup[0] = None

    def _on_change(*_) -> None:
        query = search_var.get().strip().lower()
        w = app._server_widgets.get(server_id, {})
        tabs: Any = w.get("_tabs")
        _hide()
        if len(query) < 2 or not tabs:
            return
        index = app._config_search_index.get(server_id, [])
        matches = [
            (lbl, hint, tab) for lbl, hint, tab in index
            if query in lbl.lower() or query in hint.lower() or query in tab.lower()
        ]
        if not matches:
            return
        n = min(len(matches), 7)
        row_h = 56
        outer = ctk.CTkFrame(
            parent, fg_color="#1a1a2e", corner_radius=8,
            border_color="#3a3a5a", border_width=1,
            height=n * row_h + (22 if len(matches) > 7 else 6),
        )
        outer.grid_propagate(False)
        inner = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        inner.pack(fill="both", expand=True)
        inner.grid_columnconfigure(0, weight=1)
        parent.update_idletasks()
        by = bar.winfo_y() + bar.winfo_height()
        outer.place(x=8, y=by + 2, relwidth=1.0, width=-16)
        outer.lift()
        popup[0] = outer

        def _make_cb(tab_name: str) -> Any:
            def _go() -> None:
                try:
                    tabs.set(tab_name)
                    # CTkTabview.set() pode não disparar o command; força build da aba
                    on_tc = app._server_widgets.get(server_id, {}).get("_on_tab_change")
                    if callable(on_tc):
                        on_tc()
                except Exception:
                    pass
                search_var.set("")
                _hide()
            return _go

        for i, (lbl, hint, tab) in enumerate(matches[:7]):
            row_fr = ctk.CTkFrame(inner, fg_color="transparent", cursor="hand2", height=row_h)
            row_fr.grid(row=i, column=0, sticky="ew", padx=4, pady=1)
            row_fr.grid_columnconfigure(1, weight=1)
            row_fr.grid_propagate(False)

            badge = ctk.CTkLabel(
                row_fr, text=tab, width=70, height=20,
                font=ctk.CTkFont(size=9, weight="bold"),
                text_color="#5a9ad5", fg_color="#161630", corner_radius=4,
            )
            badge.grid(row=0, column=0, rowspan=2, padx=(6, 8), pady=(8, 4), sticky="nw")

            name_lbl = ctk.CTkLabel(
                row_fr, text=lbl,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="gray85", anchor="w",
            )
            name_lbl.grid(row=0, column=1, padx=(0, 8), pady=(8, 0), sticky="w")

            hint_lbl = ctk.CTkLabel(
                row_fr,
                text=(hint[:70] + "…") if len(hint) > 70 else hint,
                font=ctk.CTkFont(size=9), text_color="gray50", anchor="w",
            )
            hint_lbl.grid(row=1, column=1, padx=(0, 8), pady=(0, 6), sticky="w")

            cb = _make_cb(tab)
            for widget in (row_fr, badge, name_lbl, hint_lbl):
                widget.bind("<Button-1>", lambda _e, c=cb: c())
                widget.bind("<Enter>",    lambda _e, f=row_fr: f.configure(fg_color="#252550"))
                widget.bind("<Leave>",    lambda _e, f=row_fr: f.configure(fg_color="transparent"))

        if len(matches) > 7:
            ctk.CTkLabel(
                inner,
                text=f"  … e mais {len(matches) - 7} resultado(s)",
                font=ctk.CTkFont(size=9), text_color="gray45",
            ).grid(row=7, column=0, padx=8, pady=(2, 6), sticky="w")

    search_var.trace_add("write", _on_change)
    entry.bind("<Escape>", lambda _e: (search_var.set(""), _hide()))
    entry.bind("<FocusOut>", lambda _e: app.after(200, _hide))
    app._server_widgets[server_id]["_config_search_var"] = search_var

