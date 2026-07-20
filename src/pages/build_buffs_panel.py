from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]
from ..ui_constants import (
    _GREEN_DARK, _GREEN_HOVER, _BLUE, _BLUE_HOVER,
    _CARD_BG, _BG, _SIDEBAR_BG,
)
from ..buff_server_bridge import list_buff_servers
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


_TAB_RATES = "Rates temporários"
_TAB_ARK = "Evento ARK oficial"


def build_buffs_panel(app: "ARKServerManagerApp", parent: "ctk.CTkFrame") -> None:
    """Painel Eventos Globais: rates (buff) e ActiveEvent em abas distintas.

    Antes, ActiveEvent ficava empilhado acima dos rates e ocupava o viewport
    inteiro — a secção de XP/Doma/Farm deixava de aparecer. Abas garantem
    coexistência sem esconder nenhum dos dois.
    """
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)

    # ── Cabeçalho (row 0) ───────────────────────────────────────────────
    hdr = ctk.CTkFrame(parent, fg_color="transparent")
    hdr.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 6))
    hdr.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        hdr, text="⚡  Eventos Globais",
        font=ctk.CTkFont(size=24, weight="bold"),
    ).grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(
        hdr,
        text="Rates temporários (XP, Doma, Farm…) e eventos oficiais ARK (Páscoa, Halloween…).",
        text_color="gray60",
    ).grid(row=1, column=0, sticky="w", pady=(0, 4))

    btn_bar = ctk.CTkFrame(hdr, fg_color="transparent")
    btn_bar.grid(row=0, column=2, rowspan=2, sticky="e", padx=(0, 0))
    ctk.CTkButton(
        btn_bar, text="⚡  Novo rate temporário", height=38, width=180,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        font=ctk.CTkFont(size=13, weight="bold"),
        command=app._open_create_buff_dialog,
    ).pack(side="left", padx=(0, 8))
    ctk.CTkButton(
        btn_bar, text="📋  Presets", height=38, width=120,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=app._open_presets_manager,
    ).pack(side="left")

    # ── Abas: Rates | ActiveEvent (row 1) ────────────────────────────────
    tabs = ctk.CTkTabview(
        parent,
        fg_color=_BG,
        segmented_button_fg_color=_SIDEBAR_BG,
        segmented_button_selected_color=_GREEN_DARK,
        segmented_button_selected_hover_color=_GREEN_HOVER,
        segmented_button_unselected_color=_SIDEBAR_BG,
        segmented_button_unselected_hover_color=_CARD_BG,
    )
    tabs.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
    tabs.add(_TAB_RATES)
    tabs.add(_TAB_ARK)
    app._buffs_tabview = tabs

    _build_rates_tab(app, tabs.tab(_TAB_RATES))
    _build_ark_event_tab(app, tabs.tab(_TAB_ARK))

    # Rates primeiro — era o conteúdo original e sumiu sob o card ActiveEvent
    tabs.set(_TAB_RATES)


def _build_rates_tab(app: "ARKServerManagerApp", parent) -> None:
    """Lista ativa/agendada/presets/histórico de rates por servidor."""
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(1, weight=1)

    sel_bar = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=10)
    sel_bar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
    sel_bar.grid_columnconfigure(1, weight=1)

    ctk.CTkLabel(
        sel_bar, text="Servidor:", text_color="gray60",
        font=ctk.CTkFont(size=12),
    ).grid(row=0, column=0, padx=(16, 8), pady=10, sticky="w")

    app._buffs_server_var = tk.StringVar()
    entries = list_buff_servers(app)
    labels = [e.label for e in entries]
    srv_combo = ctk.CTkComboBox(
        sel_bar,
        variable=app._buffs_server_var,
        values=labels if labels else ["(nenhum servidor)"],
        state="readonly",
        width=300,
        command=lambda _: app._refresh_buffs_ui(),
    )
    if labels:
        app._buffs_server_var.set(labels[0])
    srv_combo.grid(row=0, column=1, padx=(0, 16), pady=10, sticky="w")

    ctk.CTkLabel(
        sel_bar,
        text="XP · Taming · Harvest · Breeding — agende ou aplique como antes",
        text_color="gray50",
        font=ctk.CTkFont(size=11),
    ).grid(row=0, column=2, padx=(0, 16), pady=10, sticky="e")

    body = ctk.CTkScrollableFrame(parent, fg_color=_BG)
    body.grid(row=1, column=0, sticky="nsew", padx=0, pady=(4, 0))
    body.grid_columnconfigure(0, weight=1)
    app._buffs_body_frame = body


def _build_ark_event_tab(app: "ARKServerManagerApp", parent) -> None:
    """ActiveEvent (-ActiveEvent=) — aplicação/agendamento global."""
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=1)

    scroll = ctk.CTkScrollableFrame(parent, fg_color=_BG)
    scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
    scroll.grid_columnconfigure(0, weight=1)

    from .global_active_event import build_global_active_event_section

    build_global_active_event_section(app, scroll)
