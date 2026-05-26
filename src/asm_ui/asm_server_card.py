"""
TEK — Card de servidor para o dashboard ASM.
Visual diferente do PRIMITIVE: borda teal, layout compacto.
"""
from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import (
    AsmServerConfig,
    ASM_STATUS_STOPPED, ASM_STATUS_STARTING, ASM_STATUS_RUNNING,
    ASM_STATUS_STOPPING, ASM_STATUS_CRASHED, ASM_STATUS_UPDATING,
)
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

_STATUS_COLOR = {
    ASM_STATUS_STOPPED:  "#ff6666",
    ASM_STATUS_STARTING: "#ffaa44",
    ASM_STATUS_RUNNING:  "#00BCD4",
    ASM_STATUS_STOPPING: "#ffaa44",
    ASM_STATUS_CRASHED:  "#ff3333",
    ASM_STATUS_UPDATING: "#ffaa44",
}
_STATUS_LABEL = {
    ASM_STATUS_STOPPED:  "⬛ PARADO",
    ASM_STATUS_STARTING: "🟡 INICIANDO",
    ASM_STATUS_RUNNING:  "🟢 RODANDO",
    ASM_STATUS_STOPPING: "🟡 PARANDO",
    ASM_STATUS_CRASHED:  "🔴 TRAVADO",
    ASM_STATUS_UPDATING: "🟡 ATUALIZANDO",
}

ARK_MAP_LABELS: dict[str, str] = {
    "TheIsland":    "The Island",
    "TheCenter":    "The Center",
    "ScorchedEarth_P": "Scorched Earth",
    "Ragnarok":     "Ragnarok",
    "Aberration_P": "Aberration",
    "Extinction":   "Extinction",
    "Valguero_P":   "Valguero",
    "Genesis":      "Genesis",
    "CrystalIsles": "Crystal Isles",
    "Gen2":         "Genesis 2",
    "Fjordur":      "Fjordur",
    "LostIsland":   "Lost Island",
}


def build_asm_server_card(app: "ARKServerManagerApp", parent: tk.Widget,
                          srv: AsmServerConfig, row: int, col: int) -> None:
    theme = get_theme("tek")
    accent  = theme["accent"]       # #00BCD4
    card_bg = theme["card_bg"]      # #162228

    inst   = app.asm_server_manager.get_instance(srv.id)
    status = inst.status if inst else ASM_STATUS_STOPPED
    color  = _STATUS_COLOR.get(status, "#ff6666")
    status_txt = _STATUS_LABEL.get(status, "PARADO")
    is_running = status == ASM_STATUS_RUNNING
    is_busy    = status in (ASM_STATUS_STARTING, ASM_STATUS_STOPPING, ASM_STATUS_UPDATING)

    card = ctk.CTkFrame(parent, corner_radius=12, fg_color=card_bg,
                        border_width=1, border_color="#094f5c")
    card.grid(row=row, column=col, padx=8, pady=8, sticky="ew")
    card.grid_columnconfigure(0, weight=1)

    # ── Header: nome + status ────────────────────────────────────────────────
    hdr = ctk.CTkFrame(card, fg_color="transparent")
    hdr.grid(row=0, column=0, padx=14, pady=(12, 0), sticky="ew")
    hdr.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(hdr, text=srv.name,
                 font=ctk.CTkFont(size=15, weight="bold"),
                 text_color="#e0f4f8").grid(row=0, column=0, sticky="w")
    ctk.CTkLabel(hdr, text=status_txt, text_color=color,
                 font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=1, sticky="e")

    # ── Info: mapa + portas ──────────────────────────────────────────────────
    map_label = ARK_MAP_LABELS.get(srv.server_map, srv.server_map)
    info_text = (
        f"🗺  {map_label}   "
        f"⚙  :{srv.server_port}   "
        f"🔍  Query: {srv.query_port}"
    )
    ctk.CTkLabel(card, text=info_text,
                 font=ctk.CTkFont(size=11), text_color="#7ab8c8",
                 justify="left").grid(row=1, column=0, padx=14, pady=(4, 2), sticky="w")

    # Mods count
    if srv.active_mods:
        ctk.CTkLabel(card, text=f"🔧  {len(srv.active_mods)} mod(s)",
                     font=ctk.CTkFont(size=10), text_color="#5a8fa0").grid(
            row=2, column=0, padx=14, pady=(0, 2), sticky="w")

    # ── Separador ────────────────────────────────────────────────────────────
    sep = tk.Frame(card, height=1, bg="#0a4450")
    sep.grid(row=3, column=0, sticky="ew", padx=14, pady=(4, 6))

    # ── Botões de ação ────────────────────────────────────────────────────────
    btn_row = ctk.CTkFrame(card, fg_color="transparent")
    btn_row.grid(row=4, column=0, padx=14, pady=(0, 12), sticky="ew")

    if is_running:
        ctk.CTkButton(
            btn_row, text="⏹ Parar", width=90, height=30,
            fg_color="#7a2d2d", hover_color="#5c1f1f",
            command=lambda sid=srv.id: app._asm_stop_server(sid),
        ).pack(side="left", padx=(0, 6))
    else:
        ctk.CTkButton(
            btn_row, text="▶ Iniciar", width=90, height=30,
            fg_color="#0d5f72", hover_color="#094d5c",
            state="disabled" if is_busy else "normal",
            command=lambda s=srv: app._asm_start_server(s),
        ).pack(side="left", padx=(0, 6))

    ctk.CTkButton(
        btn_row, text="🔄 Restart", width=90, height=30,
        fg_color="#1a3a4a", hover_color="#102530",
        state="disabled" if is_busy or not is_running else "normal",
        command=lambda s=srv: app._asm_restart_server(s),
    ).pack(side="left", padx=(0, 6))

    ctk.CTkButton(
        btn_row, text="⚙ Configurar", width=110, height=30,
        fg_color="#0b3944", hover_color="#094f5c",
        border_width=1, border_color=accent,
        command=lambda sid=srv.id: app._asm_open_server_panel(sid),
    ).pack(side="right")
