"""
Fase 6.3 / 6.4 / 6.6 — Painel Gerador SpawnExactDino.

Funcionalidades:
  • Busca de espécies (oficial + mods) via ObeliskClient
  • Configuração completa de stats selvagens e domados
  • Seis campos de cor por região
  • Imprint (nome, ID, qualidade)
  • Sela e nome personalizado
  • Botões: Copiar, Enviar RCON (6.4)
  • Presets locais + histórico recente (6.6)

Uso:
    from src.asm_ui.spawn_exact_panel import open_spawn_exact_panel
    open_spawn_exact_panel(app, srv)
"""
from __future__ import annotations

import json
import threading
import tkinter as tk
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..spawn_exact import (
    STAT_NAMES, COLOR_COUNT, SpawnExactParams,
    validate_and_build,
)
from ..obelisk_client import get_client, Species
from ..rcon_client import RconClient, RconError
from ..asm_engine.asm_server_config import AsmServerConfig
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp

_CACHE_DIR         = Path(__file__).resolve().parent.parent.parent / ".cache"
_PRESETS_FILE      = _CACHE_DIR / "spawnexact_presets.json"
_HISTORY_FILE      = _CACHE_DIR / "spawnexact_history.json"
_BLUEPRINTS_FILE   = _CACHE_DIR / "spawnexact_blueprints.json"
_HISTORY_MAX       = 20


# ─── Ponto de entrada ────────────────────────────────────────────────────────


def open_spawn_exact_panel(
    app: "ARKServerManagerApp",
    srv: Optional[AsmServerConfig] = None,
) -> None:
    """Abre (ou foca) o painel SpawnExact."""
    attr = "_spawn_exact_win"
    existing: Optional[ctk.CTkToplevel] = getattr(app, attr, None)
    if existing and existing.winfo_exists():
        existing.lift()
        existing.focus_force()
        return
    win = _SpawnExactWindow(app, srv)
    setattr(app, attr, win)
    win.protocol("WM_DELETE_WINDOW", lambda: _on_close(app, attr, win))
    win.after(100, win.lift)
    win.after(150, win.focus_force)


def _on_close(app: "ARKServerManagerApp", attr: str, win: ctk.CTkToplevel) -> None:
    setattr(app, attr, None)
    win.destroy()


# ─── Janela principal ─────────────────────────────────────────────────────────


class _SpawnExactWindow(ctk.CTkToplevel):
    """Gerador de SpawnExactDino."""

    def __init__(
        self,
        app: "ARKServerManagerApp",
        srv: Optional[AsmServerConfig],
    ) -> None:
        super().__init__(app)
        self._app = app
        self._srv = srv
        self._species_list: list[Species] = []
        self._selected_species: Optional[Species] = None
        self._history: list[str] = []
        self._presets: dict[str, dict] = {}
        self._blueprints: dict[str, str] = {}   # nome → blueprint path
        self._rcon_client: Optional[RconClient] = None

        th = get_theme("tek")
        self._th   = th
        self._bg   = th["bg"]
        self._card = th["card_bg"]
        self._acc  = th["accent"]
        self._sep  = th.get("separator", "#1e293b")
        self._t1   = th["text_primary"]
        self._t2   = th["text_secondary"]
        self._t3   = th.get("text_muted", "#475569")

        title = f"SpawnExact — {srv.name}" if srv else "SpawnExact Generator"
        self.title(title)
        self.geometry("1060x740")
        self.minsize(900, 600)
        self.configure(fg_color=self._bg)

        self._build_layout()
        self._load_presets()
        self._load_history()
        self._load_blueprints()
        self._start_species_load()

    # ── Layout principal ──────────────────────────────────────────────────────

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=2, minsize=300)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        # Painel esquerdo — espécies + histórico + presets
        left = ctk.CTkFrame(self, fg_color=self._card, corner_radius=0)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(1, weight=1)

        self._build_left(left)

        # Painel direito — configuração + geração
        right = ctk.CTkScrollableFrame(self, fg_color=self._bg, corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew", padx=0)
        right.grid_columnconfigure(0, weight=1)
        self._build_right(right)

    # ── Painel esquerdo ───────────────────────────────────────────────────────

    def _build_left(self, parent: ctk.CTkFrame) -> None:
        # Linha 0 = cabeçalho fixo; Linha 1 = lista expansível; Linha 2 = abas fixas
        parent.grid_rowconfigure(0, weight=0)
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_rowconfigure(2, weight=0)

        # ── Cabeçalho ────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(parent, fg_color=self._card, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text="🦕 SpawnExact",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=self._acc).grid(row=0, column=0, padx=12, pady=(10, 2), sticky="w")

        ctk.CTkLabel(hdr, text="Selecione uma espécie ou cole o blueprint à direita",
                     font=ctk.CTkFont(size=10), text_color=self._t3).grid(
            row=1, column=0, padx=12, pady=(0, 4), sticky="w")

        # Busca
        search_fr = ctk.CTkFrame(hdr, fg_color=self._sep, corner_radius=6)
        search_fr.grid(row=2, column=0, padx=8, pady=(2, 4), sticky="ew")
        search_fr.grid_columnconfigure(0, weight=1)

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search_change())
        ctk.CTkEntry(
            search_fr, textvariable=self._search_var,
            placeholder_text="🔍  Buscar espécie...",
            fg_color=self._bg, border_width=0,
            text_color=self._t1, height=28,
        ).grid(row=0, column=0, sticky="ew", padx=4, pady=3)

        self._status_lbl = ctk.CTkLabel(hdr, text="Carregando manifesto ArkUtils...",
                                        font=ctk.CTkFont(size=10), text_color=self._t3)
        self._status_lbl.grid(row=3, column=0, padx=12, pady=(0, 4), sticky="w")

        ctk.CTkFrame(hdr, fg_color=self._sep, height=1).grid(
            row=4, column=0, sticky="ew", padx=0)

        # ── Lista de espécies (expandível) ────────────────────────────────────
        list_fr = ctk.CTkFrame(parent, fg_color="#090f1a", corner_radius=0)
        list_fr.grid(row=1, column=0, sticky="nsew")
        list_fr.grid_columnconfigure(0, weight=1)
        list_fr.grid_rowconfigure(0, weight=1)

        self._species_listbox = tk.Listbox(
            list_fr,
            bg="#090f1a", fg=self._t1, selectbackground=self._acc,
            selectforeground="#000000", activestyle="none",
            relief="flat", borderwidth=0, highlightthickness=0,
            font=("Segoe UI", 11), exportselection=False,
        )
        self._species_listbox.grid(row=0, column=0, sticky="nsew")
        sb = ctk.CTkScrollbar(list_fr, command=self._species_listbox.yview,
                               fg_color="#090f1a", button_color=self._sep)
        sb.grid(row=0, column=1, sticky="ns")
        self._species_listbox.configure(yscrollcommand=sb.set)
        self._species_listbox.bind("<<ListboxSelect>>", self._on_species_select)

        # ── Abas: Blueprints / Histórico / Presets (altura fixa) ─────────────
        tabs = ctk.CTkTabview(parent, fg_color=self._card,
                               segmented_button_fg_color=self._sep,
                               segmented_button_selected_color=self._acc,
                               segmented_button_selected_hover_color=self._acc,
                               height=190)
        tabs.grid(row=2, column=0, sticky="ew")
        tabs.add("Blueprints")
        tabs.add("Histórico")
        tabs.add("Presets")

        # ── Aba Blueprints salvos ─────────────────────────────────────────
        bp_fr = tabs.tab("Blueprints")
        bp_fr.grid_columnconfigure(0, weight=1)
        bp_fr.grid_rowconfigure(0, weight=1)

        self._bp_listbox = tk.Listbox(
            bp_fr, bg="#0d1220", fg=self._t1, selectbackground=self._acc,
            selectforeground="#000000", activestyle="none",
            relief="flat", borderwidth=0, highlightthickness=0,
            font=("Consolas", 10), exportselection=False, height=6,
        )
        self._bp_listbox.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._bp_listbox.bind("<Double-Button-1>", self._on_blueprint_load)
        self._bp_listbox.bind("<<ListboxSelect>>", self._on_blueprint_select)

        self._bp_tooltip = ctk.CTkLabel(
            bp_fr, text="", font=ctk.CTkFont(family="Consolas", size=9),
            text_color=self._t3, wraplength=260, justify="left",
        )
        self._bp_tooltip.grid(row=1, column=0, padx=6, pady=(0, 2), sticky="w")

        bp_btn_row = ctk.CTkFrame(bp_fr, fg_color="transparent")
        bp_btn_row.grid(row=2, column=0, pady=(0, 4))
        ctk.CTkButton(bp_btn_row, text="Carregar", height=24, width=72,
                       fg_color=self._acc, hover_color=self._th["accent_hover"],
                       text_color="#000", font=ctk.CTkFont(size=11, weight="bold"),
                       command=self._load_selected_blueprint).pack(side="left", padx=3)
        ctk.CTkButton(bp_btn_row, text="Remover", height=24, width=72,
                       fg_color=self._sep, hover_color="#2a2a45",
                       text_color=self._t2, font=ctk.CTkFont(size=11),
                       command=self._remove_blueprint).pack(side="left", padx=3)

        # ── Aba Histórico ─────────────────────────────────────────────────
        hist_fr = tabs.tab("Histórico")
        hist_fr.grid_columnconfigure(0, weight=1)
        hist_fr.grid_rowconfigure(0, weight=1)
        self._hist_listbox = tk.Listbox(
            hist_fr, bg="#0d1220", fg=self._t2, selectbackground=self._acc,
            selectforeground="#000000", activestyle="none",
            relief="flat", borderwidth=0, highlightthickness=0,
            font=("Consolas", 10), exportselection=False, height=6,
        )
        self._hist_listbox.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._hist_listbox.bind("<Double-Button-1>", self._on_history_load)
        ctk.CTkButton(hist_fr, text="Limpar histórico", height=24,
                       fg_color=self._sep, hover_color="#2a2a45",
                       text_color=self._t2, font=ctk.CTkFont(size=11),
                       command=self._clear_history).grid(row=1, column=0, pady=(0, 4))

        # ── Aba Presets ───────────────────────────────────────────────────
        pre_fr = tabs.tab("Presets")
        pre_fr.grid_columnconfigure(0, weight=1)
        pre_fr.grid_rowconfigure(0, weight=1)
        self._preset_listbox = tk.Listbox(
            pre_fr, bg="#0d1220", fg=self._t2, selectbackground=self._acc,
            selectforeground="#000000", activestyle="none",
            relief="flat", borderwidth=0, highlightthickness=0,
            font=("Consolas", 10), exportselection=False, height=5,
        )
        self._preset_listbox.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        self._preset_listbox.bind("<Double-Button-1>", self._on_preset_load)

        btn_row = ctk.CTkFrame(pre_fr, fg_color="transparent")
        btn_row.grid(row=1, column=0, pady=(0, 4))
        ctk.CTkButton(btn_row, text="Salvar", height=24, width=70,
                       fg_color=self._acc, hover_color=self._th["accent_hover"],
                       text_color="#000", font=ctk.CTkFont(size=11, weight="bold"),
                       command=self._save_preset).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="Remover", height=24, width=70,
                       fg_color=self._sep, hover_color="#2a2a45",
                       text_color=self._t2, font=ctk.CTkFont(size=11),
                       command=self._remove_preset).pack(side="left", padx=4)

    # ── Painel direito ────────────────────────────────────────────────────────

    def _build_right(self, parent: ctk.CTkScrollableFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_columnconfigure(1, weight=1)
        row = 0

        def _sec_lbl(text: str) -> None:
            nonlocal row
            ctk.CTkLabel(parent, text=text,
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=self._acc).grid(
                row=row, column=0, columnspan=2, padx=16, pady=(14, 4), sticky="w")
            row += 1

        def _sep() -> None:
            nonlocal row
            ctk.CTkFrame(parent, fg_color=self._sep, height=1).grid(
                row=row, column=0, columnspan=2, sticky="ew", padx=12, pady=2)
            row += 1

        # ── Blueprint da criatura ──────────────────────────────────────────
        bp_card = ctk.CTkFrame(parent, fg_color=self._card, corner_radius=8,
                               border_width=1, border_color=self._acc)
        bp_card.grid(row=row, column=0, columnspan=2, padx=10, pady=(12, 6), sticky="ew")
        bp_card.grid_columnconfigure(1, weight=1)
        row += 1

        ctk.CTkLabel(bp_card, text="Blueprint da Criatura",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=self._acc).grid(row=0, column=0, columnspan=3,
                                                padx=12, pady=(8, 2), sticky="w")
        ctk.CTkLabel(bp_card,
                     text="Selecione na lista ao lado  ou  cole o caminho abaixo:",
                     font=ctk.CTkFont(size=10), text_color=self._t3).grid(
            row=1, column=0, columnspan=3, padx=12, pady=(0, 4), sticky="w")

        self._blueprint_var = tk.StringVar()
        bp_entry = ctk.CTkEntry(
            bp_card, textvariable=self._blueprint_var,
            placeholder_text="Blueprint'/Game/.../NomeDino_Character_BP.NomeDino_Character_BP'",
            fg_color=self._bg, border_color=self._sep,
            text_color=self._t1, height=32,
            font=ctk.CTkFont(family="Consolas", size=10),
        )
        bp_entry.grid(row=2, column=0, columnspan=2, padx=(12, 4), pady=(0, 8), sticky="ew")

        ctk.CTkButton(bp_card, text="✕", width=28, height=28,
                      fg_color=self._sep, hover_color="#2a2a45",
                      text_color=self._t2, font=ctk.CTkFont(size=11),
                      command=lambda: self._blueprint_var.set("")).grid(
            row=2, column=2, padx=(0, 10), pady=(0, 8))

        self._bp_name_lbl = ctk.CTkLabel(bp_card, text="",
                                          font=ctk.CTkFont(size=10, weight="bold"),
                                          text_color=self._acc)
        self._bp_name_lbl.grid(row=3, column=0, columnspan=3, padx=12, pady=(0, 8), sticky="w")

        _sep()

        # ── Stats selvagens (wild) ─────────────────────────────────────────
        _sec_lbl("Stats Selvagens (Wild)")
        self._wild_vars: list[tk.IntVar] = []
        for i, name in enumerate(STAT_NAMES):
            v = tk.IntVar(value=0)
            self._wild_vars.append(v)
            col = i % 2
            r   = row + i // 2
            fr = ctk.CTkFrame(parent, fg_color=self._card, corner_radius=6)
            fr.grid(row=r, column=col, padx=6, pady=3, sticky="ew")
            ctk.CTkLabel(fr, text=name, text_color=self._t2,
                         font=ctk.CTkFont(size=11), width=90, anchor="w").pack(side="left", padx=8)
            ctk.CTkEntry(fr, textvariable=v, width=60, fg_color=self._bg,
                         text_color=self._t1, border_color=self._sep).pack(side="right", padx=6, pady=4)
        row += (len(STAT_NAMES) + 1) // 2
        _sep()

        # ── Stats domados (tamed) ──────────────────────────────────────────
        _sec_lbl("Stats Domados (Tamed Additions)")
        self._tamed_vars: list[tk.IntVar] = []
        for i, name in enumerate(STAT_NAMES):
            v = tk.IntVar(value=0)
            self._tamed_vars.append(v)
            col = i % 2
            r   = row + i // 2
            fr = ctk.CTkFrame(parent, fg_color=self._card, corner_radius=6)
            fr.grid(row=r, column=col, padx=6, pady=3, sticky="ew")
            ctk.CTkLabel(fr, text=name, text_color=self._t2,
                         font=ctk.CTkFont(size=11), width=90, anchor="w").pack(side="left", padx=8)
            ctk.CTkEntry(fr, textvariable=v, width=60, fg_color=self._bg,
                         text_color=self._t1, border_color=self._sep).pack(side="right", padx=6, pady=4)
        row += (len(STAT_NAMES) + 1) // 2
        _sep()

        # ── Cores (6 regiões) ──────────────────────────────────────────────
        _sec_lbl("Cores por Região (0 = padrão)")
        self._color_vars: list[tk.IntVar] = []
        for i in range(COLOR_COUNT):
            v = tk.IntVar(value=0)
            self._color_vars.append(v)
            col = i % 2
            r   = row + i // 2
            fr = ctk.CTkFrame(parent, fg_color=self._card, corner_radius=6)
            fr.grid(row=r, column=col, padx=6, pady=3, sticky="ew")
            ctk.CTkLabel(fr, text=f"Região {i}", text_color=self._t2,
                         font=ctk.CTkFont(size=11), width=90, anchor="w").pack(side="left", padx=8)
            ctk.CTkEntry(fr, textvariable=v, width=60, fg_color=self._bg,
                         text_color=self._t1, border_color=self._sep).pack(side="right", padx=6, pady=4)
        row += (COLOR_COUNT + 1) // 2
        _sep()

        # ── Imprint ────────────────────────────────────────────────────────
        _sec_lbl("Imprint")
        self._imp_name_var = tk.StringVar()
        self._imp_id_var   = tk.StringVar(value="0")
        self._imp_qual_var = tk.DoubleVar(value=0.0)

        for label, var, ph in [
            ("Nome do Imprinter", self._imp_name_var, "Nome do jogador"),
            ("ID do Imprinter",   self._imp_id_var,   "0"),
        ]:
            fr = ctk.CTkFrame(parent, fg_color=self._card, corner_radius=6)
            fr.grid(row=row, column=0, columnspan=2, padx=6, pady=3, sticky="ew")
            ctk.CTkLabel(fr, text=label, text_color=self._t2,
                         font=ctk.CTkFont(size=11), width=140, anchor="w").pack(side="left", padx=8)
            ctk.CTkEntry(fr, textvariable=var, placeholder_text=ph,
                         fg_color=self._bg, text_color=self._t1, border_color=self._sep
                         ).pack(side="right", fill="x", expand=True, padx=6, pady=4)
            row += 1

        imp_sl_fr = ctk.CTkFrame(parent, fg_color=self._card, corner_radius=6)
        imp_sl_fr.grid(row=row, column=0, columnspan=2, padx=6, pady=3, sticky="ew")
        imp_sl_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(imp_sl_fr, text="Imprint %", text_color=self._t2,
                     font=ctk.CTkFont(size=11), width=140, anchor="w").grid(row=0, column=0, padx=8)
        self._imp_val_lbl = ctk.CTkLabel(imp_sl_fr, text="0 %", text_color=self._acc,
                                          font=ctk.CTkFont(size=11), width=40)
        self._imp_val_lbl.grid(row=0, column=2, padx=8)
        ctk.CTkSlider(
            imp_sl_fr, from_=0, to=100, number_of_steps=100,
            variable=self._imp_qual_var,
            fg_color=self._sep, button_color=self._acc,
            progress_color=self._acc,
            command=lambda v: self._imp_val_lbl.configure(text=f"{int(v)} %"),
        ).grid(row=0, column=1, sticky="ew", padx=8, pady=6)
        row += 1
        _sep()

        # ── Nome + Sela ────────────────────────────────────────────────────
        _sec_lbl("Identificação & Sela")
        self._dino_name_var   = tk.StringVar()
        self._saddle_bp_var   = tk.StringVar()
        self._saddle_qual_var = tk.DoubleVar(value=0.0)
        self._neutered_var    = tk.BooleanVar(value=False)

        for label, var, ph in [
            ("Nome do Dino",  self._dino_name_var, "Deixe vazio para sem nome"),
            ("Saddle BP",     self._saddle_bp_var, 'Blueprint\'/.../SaddleBP\' ou ""'),
        ]:
            fr = ctk.CTkFrame(parent, fg_color=self._card, corner_radius=6)
            fr.grid(row=row, column=0, columnspan=2, padx=6, pady=3, sticky="ew")
            ctk.CTkLabel(fr, text=label, text_color=self._t2,
                         font=ctk.CTkFont(size=11), width=140, anchor="w").pack(side="left", padx=8)
            ctk.CTkEntry(fr, textvariable=var, placeholder_text=ph,
                         fg_color=self._bg, text_color=self._t1, border_color=self._sep
                         ).pack(side="right", fill="x", expand=True, padx=6, pady=4)
            row += 1

        sq_fr = ctk.CTkFrame(parent, fg_color=self._card, corner_radius=6)
        sq_fr.grid(row=row, column=0, columnspan=2, padx=6, pady=3, sticky="ew")
        sq_fr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(sq_fr, text="Qualidade da Sela", text_color=self._t2,
                     font=ctk.CTkFont(size=11), width=140, anchor="w").grid(row=0, column=0, padx=8)
        self._sq_lbl = ctk.CTkLabel(sq_fr, text="0", text_color=self._acc,
                                     font=ctk.CTkFont(size=11), width=30)
        self._sq_lbl.grid(row=0, column=2, padx=8)
        ctk.CTkSlider(
            sq_fr, from_=0, to=100, number_of_steps=100,
            variable=self._saddle_qual_var,
            fg_color=self._sep, button_color=self._acc,
            progress_color=self._acc,
            command=lambda v: self._sq_lbl.configure(text=str(int(v))),
        ).grid(row=0, column=1, sticky="ew", padx=8, pady=6)
        row += 1

        neu_fr = ctk.CTkFrame(parent, fg_color=self._card, corner_radius=6)
        neu_fr.grid(row=row, column=0, columnspan=2, padx=6, pady=3, sticky="ew")
        ctk.CTkLabel(neu_fr, text="Castrado", text_color=self._t2,
                     font=ctk.CTkFont(size=11), width=140, anchor="w").pack(side="left", padx=8)
        ctk.CTkSwitch(neu_fr, text="", variable=self._neutered_var,
                       onvalue=True, offvalue=False,
                       progress_color=self._acc, button_color=self._t2,
                       ).pack(side="right", padx=8, pady=6)
        row += 1
        _sep()

        # ── Posição ────────────────────────────────────────────────────────
        _sec_lbl("Posição de Spawn")
        self._spawn_dist_var = tk.IntVar(value=200)
        self._spawn_y_var    = tk.IntVar(value=0)
        self._spawn_z_var    = tk.IntVar(value=0)
        for label, var in [("Dist. Frente", self._spawn_dist_var),
                            ("Offset Y",    self._spawn_y_var),
                            ("Offset Z",    self._spawn_z_var)]:
            col = [("Dist. Frente", 0), ("Offset Y", 0), ("Offset Z", 1)][
                [("Dist. Frente", self._spawn_dist_var),
                 ("Offset Y", self._spawn_y_var),
                 ("Offset Z", self._spawn_z_var)].index((label, var))
            ][1]
            fr = ctk.CTkFrame(parent, fg_color=self._card, corner_radius=6)
            fr.grid(row=row, column=col, padx=6, pady=3, sticky="ew")
            ctk.CTkLabel(fr, text=label, text_color=self._t2,
                         font=ctk.CTkFont(size=11), width=90, anchor="w").pack(side="left", padx=8)
            ctk.CTkEntry(fr, textvariable=var, width=70, fg_color=self._bg,
                         text_color=self._t1, border_color=self._sep).pack(side="right", padx=6, pady=4)
        row += 1
        _sep()

        # ── Área de resultado ──────────────────────────────────────────────
        _sec_lbl("Comando Gerado")
        self._cmd_box = ctk.CTkTextbox(
            parent, height=80, fg_color=self._card, border_color=self._sep,
            border_width=1, text_color=self._acc, font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word", state="normal",
        )
        self._cmd_box.grid(row=row, column=0, columnspan=2, padx=6, pady=4, sticky="ew")
        row += 1

        # ── Botões ─────────────────────────────────────────────────────────
        btn_fr = ctk.CTkFrame(parent, fg_color="transparent")
        btn_fr.grid(row=row, column=0, columnspan=2, padx=6, pady=8)

        ctk.CTkButton(
            btn_fr, text="⟳ Gerar", width=120, height=36,
            fg_color=self._acc, hover_color=self._th["accent_hover"],
            text_color="#000", font=ctk.CTkFont(size=13, weight="bold"),
            command=self._generate,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_fr, text="📋 Copiar", width=100, height=36,
            fg_color=self._sep, hover_color="#2a2a45", text_color=self._t1,
            font=ctk.CTkFont(size=12),
            command=self._copy,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_fr, text="⭐ Salvar BP", width=110, height=36,
            fg_color="#1c2a10", hover_color="#2a3d18",
            text_color="#86efac", font=ctk.CTkFont(size=12),
            command=self._save_blueprint_entry,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_fr, text="📦 Adicionar ao Kit", width=150, height=36,
            fg_color="#1a2a0a", hover_color="#253810",
            text_color="#bbf7d0", font=ctk.CTkFont(size=12),
            command=self._export_to_customshop,
        ).pack(side="left", padx=6)

        self._rcon_btn = ctk.CTkButton(
            btn_fr, text="⚡ Enviar RCON", width=130, height=36,
            fg_color=self._th.get("accent_dark", "#0e7490"),
            hover_color=self._th["accent_hover"],
            text_color=self._t1, font=ctk.CTkFont(size=12),
            command=self._send_rcon,
        )
        self._rcon_btn.pack(side="left", padx=6)
        if not self._srv or not getattr(self._srv, "rcon_enabled", False):
            self._rcon_btn.configure(state="disabled", text="⚡ RCON (desativado)")

        self._err_lbl = ctk.CTkLabel(parent, text="", text_color="#ef4444",
                                      font=ctk.CTkFont(size=11), wraplength=500)
        self._err_lbl.grid(row=row + 1, column=0, columnspan=2, padx=12, pady=4, sticky="w")

    # ── Lógica de espécies ─────────────────────────────────────────────────────

    def _start_species_load(self) -> None:
        get_client().load(on_done=self._on_species_loaded)

    def _on_species_loaded(self, ok: bool, msg: str) -> None:
        def _ui() -> None:
            self._status_lbl.configure(text=msg if ok else f"Erro: {msg}")
            if ok:
                self._update_species_list()
        self.after(0, _ui)

    def _update_species_list(self) -> None:
        q = self._search_var.get().strip()
        mods = _srv_mod_ids(self._srv)
        client = get_client()
        species = client.search(q, mods) if client.loaded else []
        self._species_list = species
        self._species_listbox.delete(0, "end")
        for sp in species:
            self._species_listbox.insert("end", sp.display_name())
        total = len(get_client().all_species(mods))
        self._status_lbl.configure(text=f"{len(species)} / {total} espécies")

    def _on_search_change(self) -> None:
        if get_client().loaded:
            self._update_species_list()

    def _on_species_select(self, _event: tk.Event) -> None:
        sel = self._species_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._species_list):
            self._selected_species = self._species_list[idx]
            self._blueprint_var.set(self._selected_species.blueprint)
            self._bp_name_lbl.configure(
                text=f"✔  {self._selected_species.name}"
                     + (f"  [mod {self._selected_species.mod_id}]"
                        if self._selected_species.mod_id else "")
            )

    # ── Gerar / copiar / RCON ─────────────────────────────────────────────────

    def _build_params(self) -> SpawnExactParams:
        bp = self._blueprint_var.get().strip()
        return SpawnExactParams(
            blueprint=bp,
            saddle_bp=self._saddle_bp_var.get().strip(),
            saddle_quality=float(self._saddle_qual_var.get()),
            base_stats=[_safe_int(v.get()) for v in self._wild_vars],
            added_stats=[_safe_int(v.get()) for v in self._tamed_vars],
            name=self._dino_name_var.get(),
            neutered=self._neutered_var.get(),
            imprinter_name=self._imp_name_var.get(),
            imprinter_id=_safe_int(self._imp_id_var.get()),
            imprint_quality=float(self._imp_qual_var.get()) / 100.0,
            colors=[_safe_int(v.get()) for v in self._color_vars],
            spawn_dist=float(self._spawn_dist_var.get()),
            spawn_y=float(self._spawn_y_var.get()),
            spawn_z=float(self._spawn_z_var.get()),
        )

    def _generate(self) -> None:
        p = self._build_params()
        ok, result = validate_and_build(p)
        self._cmd_box.configure(state="normal")
        self._cmd_box.delete("1.0", "end")
        if ok:
            self._cmd_box.insert("1.0", result)
            self._err_lbl.configure(text="")
            self._push_history(result)
        else:
            self._cmd_box.insert("1.0", "")
            self._err_lbl.configure(text=result)
        self._cmd_box.configure(state="disabled")

    def _copy(self) -> None:
        cmd = self._cmd_box.get("1.0", "end").strip()
        if cmd:
            self.clipboard_clear()
            self.clipboard_append(cmd)
            self._err_lbl.configure(text="Copiado!", text_color="#4ade80")
            self.after(2000, lambda: self._err_lbl.configure(text="", text_color="#ef4444"))

    def _send_rcon(self) -> None:
        cmd = self._cmd_box.get("1.0", "end").strip()
        if not cmd:
            self._generate()
            cmd = self._cmd_box.get("1.0", "end").strip()
        if not cmd or not self._srv:
            return
        srv = self._srv
        threading.Thread(target=self._rcon_worker, args=(srv, cmd), daemon=True).start()

    def _rcon_worker(self, srv: AsmServerConfig, cmd: str) -> None:
        try:
            host = srv.server_ip or "127.0.0.1"
            c = RconClient(host, srv.rcon_port, srv.admin_password)
            c.connect()
            ok, resp = c.send_command_safe(cmd)
            c.disconnect()
            msg  = resp.strip() if resp else "(sem resposta)"
            color = "#4ade80" if ok else "#ef4444"
            self.after(0, lambda: self._err_lbl.configure(
                text=f"RCON: {msg}", text_color=color))
        except RconError as exc:
            self.after(0, lambda: self._err_lbl.configure(
                text=f"Erro RCON: {exc}", text_color="#ef4444"))

    def _export_to_customshop(self) -> None:
        """Exporta o comando atual para um kit da CustomShop (Fase 6.5)."""
        cmd = self._cmd_box.get("1.0", "end").strip()
        if not cmd:
            self._generate()
            cmd = self._cmd_box.get("1.0", "end").strip()
        if not cmd:
            return

        shop_cfg_path: Optional[str] = None
        if self._srv:
            shop_cfg_path = getattr(self._srv, "customshop_config_path", None)

        from ..ui.spawn_exact_customshop import open_add_to_kit_dialog
        open_add_to_kit_dialog(self, cmd, shop_cfg_path)

    # ── Histórico ─────────────────────────────────────────────────────────────

    def _push_history(self, cmd: str) -> None:
        if cmd in self._history:
            self._history.remove(cmd)
        self._history.insert(0, cmd)
        self._history = self._history[:_HISTORY_MAX]
        self._refresh_hist_listbox()
        self._save_history()

    def _refresh_hist_listbox(self) -> None:
        self._hist_listbox.delete(0, "end")
        for h in self._history:
            display = h[:80] + "..." if len(h) > 80 else h
            self._hist_listbox.insert("end", display)

    def _on_history_load(self, _event: tk.Event) -> None:
        sel = self._hist_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._history):
            cmd = self._history[idx]
            self._cmd_box.configure(state="normal")
            self._cmd_box.delete("1.0", "end")
            self._cmd_box.insert("1.0", cmd)
            self._cmd_box.configure(state="disabled")

    def _clear_history(self) -> None:
        self._history.clear()
        self._refresh_hist_listbox()
        self._save_history()

    def _load_history(self) -> None:
        try:
            data = _load_json(_HISTORY_FILE)
            self._history = data.get("history", [])[:_HISTORY_MAX]
        except Exception:
            self._history = []
        self._refresh_hist_listbox()

    def _save_history(self) -> None:
        _save_json(_HISTORY_FILE, {"history": self._history})

    # ── Presets ───────────────────────────────────────────────────────────────

    def _load_presets(self) -> None:
        try:
            self._presets = _load_json(_PRESETS_FILE)
        except Exception:
            self._presets = {}
        self._refresh_preset_listbox()

    def _refresh_preset_listbox(self) -> None:
        self._preset_listbox.delete(0, "end")
        for name in self._presets:
            self._preset_listbox.insert("end", name)

    def _save_preset(self) -> None:
        def _do_save(name: str) -> None:
            if not name.strip():
                return
            p = self._build_params()
            self._presets[name.strip()] = _params_to_dict(p)
            _save_json(_PRESETS_FILE, self._presets)
            self._refresh_preset_listbox()

        _ask_string(self, "Salvar Preset", "Nome do preset:", _do_save)

    def _remove_preset(self) -> None:
        sel = self._preset_listbox.curselection()
        if not sel:
            return
        name = list(self._presets.keys())[sel[0]]
        del self._presets[name]
        _save_json(_PRESETS_FILE, self._presets)
        self._refresh_preset_listbox()

    def _on_preset_load(self, _event: tk.Event) -> None:
        sel = self._preset_listbox.curselection()
        if not sel:
            return
        name = list(self._presets.keys())[sel[0]]
        data = self._presets[name]
        _apply_dict_to_panel(data, self)

    # ── Blueprints salvos ─────────────────────────────────────────────────────

    def _load_blueprints(self) -> None:
        """Carrega blueprints salvos do arquivo JSON."""
        try:
            self._blueprints = _load_json(_BLUEPRINTS_FILE)
        except Exception:
            self._blueprints = {}
        self._refresh_bp_listbox()

    def _save_blueprints_file(self) -> None:
        _save_json(_BLUEPRINTS_FILE, self._blueprints)

    def _refresh_bp_listbox(self) -> None:
        self._bp_listbox.delete(0, "end")
        for name in self._blueprints:
            self._bp_listbox.insert("end", name)

    def _save_blueprint_entry(self) -> None:
        """Salva o blueprint da espécie atualmente selecionada."""
        if not self._selected_species:
            self._err_lbl.configure(
                text="Selecione uma espécie primeiro.",
                text_color="#ef4444",
            )
            return

        sp = self._selected_species

        def _do_save(name: str) -> None:
            name = name.strip()
            if not name:
                return
            self._blueprints[name] = {
                "blueprint":  sp.blueprint,
                "species_name": sp.name,
                "mod_id":     sp.mod_id,
            }
            self._save_blueprints_file()
            self._refresh_bp_listbox()
            self._err_lbl.configure(
                text=f'Blueprint "{name}" salvo.',
                text_color="#4ade80",
            )
            self.after(2500, lambda: self._err_lbl.configure(text="", text_color="#ef4444"))

        default_name = sp.name
        _ask_string(self, "Salvar Blueprint", "Nome para este blueprint:", _do_save,
                    default=default_name)

    def _on_blueprint_select(self, _event: tk.Event) -> None:
        """Exibe o caminho do blueprint selecionado no tooltip abaixo da lista."""
        sel = self._bp_listbox.curselection()
        if not sel:
            self._bp_tooltip.configure(text="")
            return
        name = list(self._blueprints.keys())[sel[0]]
        entry = self._blueprints[name]
        bp = entry.get("blueprint", "") if isinstance(entry, dict) else str(entry)
        short = bp[:70] + "..." if len(bp) > 70 else bp
        self._bp_tooltip.configure(text=short)

    def _load_selected_blueprint(self) -> None:
        """Aplica o blueprint selecionado ao campo de espécie."""
        sel = self._bp_listbox.curselection()
        if not sel:
            return
        name = list(self._blueprints.keys())[sel[0]]
        self._apply_blueprint(name)

    def _on_blueprint_load(self, _event: tk.Event) -> None:
        """Duplo clique — aplica blueprint imediatamente."""
        self._load_selected_blueprint()

    def _apply_blueprint(self, name: str) -> None:
        """Aplica um blueprint salvo ao painel."""
        entry = self._blueprints.get(name)
        if not entry:
            return
        bp = entry.get("blueprint", "") if isinstance(entry, dict) else str(entry)
        species_name = entry.get("species_name", name) if isinstance(entry, dict) else name

        self._blueprint_var.set(bp)
        self._bp_name_lbl.configure(text=f"✔  {species_name}")

        sp = get_client().by_blueprint(bp)
        if sp:
            self._selected_species = sp
        else:
            from ..obelisk_client import Species as _Sp
            self._selected_species = _Sp(
                name=species_name, blueprint=bp,
                mod_id=entry.get("mod_id") if isinstance(entry, dict) else None,
                dino_name_tag="", no_spawner=False, variants=[],
            )

        self._err_lbl.configure(
            text=f'Blueprint "{name}" carregado.',
            text_color="#4ade80",
        )
        self.after(2000, lambda: self._err_lbl.configure(text="", text_color="#ef4444"))

    def _remove_blueprint(self) -> None:
        sel = self._bp_listbox.curselection()
        if not sel:
            return
        name = list(self._blueprints.keys())[sel[0]]
        del self._blueprints[name]
        self._save_blueprints_file()
        self._refresh_bp_listbox()
        self._bp_tooltip.configure(text="")


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _safe_int(val: object) -> int:
    try:
        return int(str(val))
    except (ValueError, TypeError):
        return 0


def _srv_mod_ids(srv: Optional[AsmServerConfig]) -> Optional[list[str]]:
    if not srv:
        return None
    mods_str = getattr(srv, "active_mods", "") or ""
    ids = [m.strip() for m in mods_str.split(",") if m.strip()]
    return ids if ids else None


def _load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _params_to_dict(p: SpawnExactParams) -> dict:
    return {
        "blueprint":       p.blueprint,
        "saddle_bp":       p.saddle_bp,
        "saddle_quality":  p.saddle_quality,
        "base_stats":      p.base_stats,
        "added_stats":     p.added_stats,
        "name":            p.name,
        "neutered":        p.neutered,
        "imprinter_name":  p.imprinter_name,
        "imprinter_id":    p.imprinter_id,
        "imprint_quality": p.imprint_quality,
        "colors":          p.colors,
        "spawn_dist":      p.spawn_dist,
        "spawn_y":         p.spawn_y,
        "spawn_z":         p.spawn_z,
    }


def _apply_dict_to_panel(data: dict, w: "_SpawnExactWindow") -> None:
    bp = data.get("blueprint", "")
    if bp:
        w._blueprint_var.set(bp)
        sp = get_client().by_blueprint(bp)
        if sp:
            w._selected_species = sp
            w._bp_name_lbl.configure(text=f"✔  {sp.name}")

    for i, v in enumerate(data.get("base_stats", [])[:8]):
        w._wild_vars[i].set(_safe_int(v))
    for i, v in enumerate(data.get("added_stats", [])[:8]):
        w._tamed_vars[i].set(_safe_int(v))
    for i, v in enumerate(data.get("colors", [])[:6]):
        w._color_vars[i].set(_safe_int(v))

    w._dino_name_var.set(data.get("name", ""))
    w._saddle_bp_var.set(data.get("saddle_bp", ""))
    w._saddle_qual_var.set(data.get("saddle_quality", 0))
    w._neutered_var.set(bool(data.get("neutered", False)))
    w._imp_name_var.set(data.get("imprinter_name", ""))
    w._imp_id_var.set(str(data.get("imprinter_id", 0)))
    w._imp_qual_var.set(float(data.get("imprint_quality", 0.0)) * 100)
    w._spawn_dist_var.set(_safe_int(data.get("spawn_dist", 200)))
    w._spawn_y_var.set(_safe_int(data.get("spawn_y", 0)))
    w._spawn_z_var.set(_safe_int(data.get("spawn_z", 0)))


def _ask_string(
    parent: ctk.CTkToplevel,
    title: str,
    prompt: str,
    callback: "Callable[[str], None]",
    default: str = "",
) -> None:
    """Diálogo simples de input de texto com valor padrão opcional."""
    from typing import Callable
    dlg = ctk.CTkToplevel(parent)
    dlg.title(title)
    dlg.geometry("360x140")
    dlg.grab_set()
    th = get_theme("tek")
    dlg.configure(fg_color=th["bg"])

    ctk.CTkLabel(dlg, text=prompt, text_color=th["text_secondary"]).pack(pady=(16, 4))
    var = tk.StringVar(value=default)
    entry = ctk.CTkEntry(dlg, textvariable=var, fg_color=th["card_bg"],
                         text_color=th["text_primary"])
    entry.pack(fill="x", padx=20)
    entry.focus()
    entry.select_range(0, "end")

    def _ok() -> None:
        callback(var.get())
        dlg.destroy()

    entry.bind("<Return>", lambda _: _ok())
    ctk.CTkButton(dlg, text="OK", fg_color=th["accent"],
                   text_color="#000", command=_ok).pack(pady=10)
