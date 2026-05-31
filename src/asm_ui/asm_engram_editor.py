"""
S4.3 — Editor Visual de Engramas.
Tabela interativa com filtro em tempo real.
Gera OverrideNamedEngramEntries para Game.ini.
"""
from __future__ import annotations

import tkinter as tk
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import get_theme
from ..asm_engine.asm_server_config import AsmServerConfig

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

# ── Dataset de engramas conhecidos ────────────────────────────────────────────
# (entry_class, display_name, default_cost, default_level, is_blueprint)
_KNOWN_ENGRAMS: List[tuple] = [
    ("EngramEntry_WeaponPrimitiveSpear_C", "Lança Primitiva", 3, 2, False),
    ("EngramEntry_TorchDefault_C", "Tocha", 3, 2, False),
    ("EngramEntry_Pick_Stone_C", "Picareta de Pedra", 6, 2, False),
    ("EngramEntry_Hatchet_Stone_C", "Machado de Pedra", 6, 2, False),
    ("EngramEntry_CampfireSmall_C", "Fogueira", 3, 2, False),
    ("EngramEntry_MapNote_C", "Nota de Mapa", 3, 2, False),
    ("EngramEntry_FoundationWood_C", "Fundação de Madeira", 12, 5, False),
    ("EngramEntry_WallWood_C", "Parede de Madeira", 3, 5, False),
    ("EngramEntry_CeilingWood_C", "Teto de Madeira", 6, 7, False),
    ("EngramEntry_DoorWood_C", "Porta de Madeira", 6, 10, False),
    ("EngramEntry_FoundationStone_C", "Fundação de Pedra", 15, 15, False),
    ("EngramEntry_WallStone_C", "Parede de Pedra", 6, 20, False),
    ("EngramEntry_MetalIngot_C", "Metal Fundido", 0, 20, True),
    ("EngramEntry_WeaponGun_C", "Pistola", 30, 40, False),
    ("EngramEntry_WeaponRifle_C", "Rifle", 34, 55, False),
    ("EngramEntry_WeaponShotgun_C", "Espingarda", 20, 35, False),
    ("EngramEntry_WeaponSniper_C", "Rifle de Precisão", 34, 62, False),
    ("EngramEntry_WeaponRocketLauncher_C", "Lança-Foguetes", 65, 87, False),
    ("EngramEntry_WeaponMachinedShotgun_C", "Espingarda Fabricada", 24, 70, False),
    ("EngramEntry_SaddleProcoptodon_C", "Sela de Procoptodon", 25, 54, False),
    ("EngramEntry_SaddleRex_C", "Sela de Rex", 40, 74, False),
    ("EngramEntry_SaddleGiga_C", "Sela de Giganotossauro", 90, 97, False),
    ("EngramEntry_SaddleWyvern_C", "Sela de Wyvern", 50, 72, False),
    ("EngramEntry_TekReplicator_C", "Replicador TEK", 0, 100, True),
    ("EngramEntry_TekTransporter_C", "Transportador TEK", 0, 100, True),
    ("EngramEntry_TekGenerator_C", "Gerador TEK", 0, 100, True),
    ("EngramEntry_TekRifle_C", "Rifle TEK", 0, 100, True),
    ("EngramEntry_TekPistol_C", "Pistola TEK", 0, 100, True),
    ("EngramEntry_TekGrenade_C", "Granada TEK", 0, 100, True),
]


class _EngramRow:
    """Representa uma linha editável no editor de engramas."""
    __slots__ = ("entry_class", "display_name", "cost", "level", "hidden", "forced")

    def __init__(self, entry_class: str, display_name: str,
                 cost: int = 0, level: int = 1,
                 hidden: bool = False, forced: bool = False):
        self.entry_class  = entry_class
        self.display_name = display_name
        self.cost         = cost
        self.level        = level
        self.hidden       = hidden
        self.forced       = forced

    def to_ini_line(self) -> str:
        hidden_str = "True" if self.hidden else "False"
        forced_str = "True" if self.forced else "False"
        return (
            f'OverrideNamedEngramEntries=(EngramClassName="{self.entry_class}",'
            f'EngramHidden={hidden_str},'
            f'EngramPointsCost={self.cost},'
            f'EngramLevelRequirement={self.level},'
            f'RemoveEngramPreReq={forced_str})'
        )


class _EngramEditorWindow(ctk.CTkToplevel):
    def __init__(self, parent, srv: AsmServerConfig, app: "ARKServerManagerApp"):
        super().__init__(parent)
        th = get_theme("tek")
        self._bg     = th["bg"]
        self._cg     = th["card_bg"]
        self._sep    = th["separator"]
        self._acc    = th["accent"]
        self._t_sec  = th["text_secondary"]
        self._t_mut  = th["text_muted"]
        self._acc_mb = th["accent_muted_bg"]

        self.title(f"Editor de Engramas — {srv.name}")
        self.geometry("1000x640")
        self.configure(fg_color=self._bg)
        self.resizable(True, True)
        self.after(100, self.lift)
        self.after(150, self.focus_force)

        self._srv = srv
        self._app = app
        self._rows: List[_EngramRow] = []
        self._filter_text = tk.StringVar()
        self._row_widgets: List[dict] = []

        self._load_initial()
        self._build_ui()
        self._refresh_table()

    # ── Dados ─────────────────────────────────────────────────────────────────

    def _load_initial(self):
        """Carrega engramas já configurados ou defaults conhecidos."""
        # Tenta parse das linhas salvas
        existing: Dict[str, _EngramRow] = {}
        raw = getattr(self._srv, "custom_game_ini", "") or ""
        import re
        pattern = re.compile(
            r'OverrideNamedEngramEntries=\(EngramClassName="([^"]+)"'
            r',EngramHidden=(\w+)'
            r',EngramPointsCost=(\d+)'
            r',EngramLevelRequirement=(\d+)'
            r',RemoveEngramPreReq=(\w+)\)',
            re.IGNORECASE,
        )
        for m in pattern.finditer(raw):
            ec = m.group(1)
            existing[ec] = _EngramRow(
                entry_class  = ec,
                display_name = ec,
                cost         = int(m.group(3)),
                level        = int(m.group(4)),
                hidden       = m.group(2).lower() == "true",
                forced       = m.group(5).lower() == "true",
            )

        # Popula com os conhecidos + existentes
        self._rows = []
        seen = set()
        for (ec, name, cost, level, _) in _KNOWN_ENGRAMS:
            if ec in existing:
                r = existing[ec]
                r.display_name = name
                self._rows.append(r)
            else:
                self._rows.append(_EngramRow(ec, name, cost, level))
            seen.add(ec)
        # Adiciona existentes que não estão nos conhecidos
        for ec, r in existing.items():
            if ec not in seen:
                self._rows.append(r)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Toolbar
        tb = ctk.CTkFrame(self, fg_color=self._cg, corner_radius=0)
        tb.grid(row=0, column=0, sticky="ew")
        tb.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(tb, text="🔍", font=ctk.CTkFont(size=14)).grid(
            row=0, column=0, padx=(12, 4), pady=8)
        ctk.CTkEntry(tb, textvariable=self._filter_text,
                     placeholder_text="Filtrar engrama...",
                     width=240, height=28).grid(row=0, column=1, padx=(0, 8), pady=8, sticky="w")
        self._filter_text.trace_add("write", lambda *_: self._refresh_table())

        ctk.CTkButton(
            tb, text="+ Adicionar Custom", width=130, height=28,
            fg_color=self._sep, hover_color="#263347",
            font=ctk.CTkFont(size=10), text_color=self._t_sec,
            command=self._add_custom,
        ).grid(row=0, column=2, padx=4, pady=8)
        ctk.CTkButton(
            tb, text="✅ Aplicar ao Servidor", width=150, height=28,
            fg_color=self._acc_mb, hover_color="#052e16",
            border_width=1, border_color=self._acc, text_color=self._acc,
            font=ctk.CTkFont(size=10),
            command=self._apply,
        ).grid(row=0, column=3, padx=(0, 12), pady=8)

        # Cabeçalho da tabela
        hdr = ctk.CTkFrame(self, fg_color="#0a111c", corner_radius=0)
        hdr.grid(row=1, column=0, sticky="ew")
        for col_i, (label, w) in enumerate([
            ("Engrama", 260), ("Classe", 260), ("Custo", 60), ("Nível", 60), ("Esconder", 70), ("Forçar Desbloqueio", 120),
        ]):
            ctk.CTkLabel(hdr, text=label,
                         font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                         text_color=self._t_sec, width=w, anchor="w",
                         ).grid(row=0, column=col_i, padx=(10 if col_i == 0 else 4, 0), pady=6, sticky="w")

        # Tabela (scroll)
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=self._bg, corner_radius=0)
        self._scroll.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)

    def _refresh_table(self, *_):
        for w in self._scroll.winfo_children():
            w.destroy()
        self._row_widgets = []

        txt = self._filter_text.get().strip().lower()
        visible = [
            r for r in self._rows
            if not txt or txt in r.display_name.lower() or txt in r.entry_class.lower()
        ]

        th = get_theme("tek")
        for i, eng in enumerate(visible):
            row_bg = self._bg if i % 2 == 0 else "#080e18"
            rf = ctk.CTkFrame(self._scroll, fg_color=row_bg, corner_radius=0, height=32)
            rf.pack(fill="x")
            rf.pack_propagate(False)

            # Nome
            ctk.CTkLabel(rf, text=eng.display_name[:32],
                         font=ctk.CTkFont(size=11), text_color=self._t_sec, width=260, anchor="w",
                         ).place(x=10, rely=0.5, anchor="w")
            # Classe (editável ao double-click)
            ctk.CTkLabel(rf, text=eng.entry_class[:34],
                         font=ctk.CTkFont(family="Consolas", size=9), text_color=self._t_mut, width=240, anchor="w",
                         ).place(x=280, rely=0.5, anchor="w")

            # Custo
            cost_var = tk.StringVar(value=str(eng.cost))
            ctk.CTkEntry(rf, textvariable=cost_var, width=50, height=22,
                         font=ctk.CTkFont(size=10),
                         ).place(x=530, rely=0.5, anchor="w")
            cost_var.trace_add("write", lambda *_, e=eng, v=cost_var: _safe_int(e, "cost", v))

            # Nível
            lvl_var = tk.StringVar(value=str(eng.level))
            ctk.CTkEntry(rf, textvariable=lvl_var, width=50, height=22,
                         font=ctk.CTkFont(size=10),
                         ).place(x=594, rely=0.5, anchor="w")
            lvl_var.trace_add("write", lambda *_, e=eng, v=lvl_var: _safe_int(e, "level", v))

            # Esconder
            hid_var = tk.BooleanVar(value=eng.hidden)
            ctk.CTkCheckBox(rf, text="", variable=hid_var, width=20, height=20,
                            checkmark_color=self._acc, border_color=self._sep,
                            command=lambda e=eng, v=hid_var: setattr(e, "hidden", v.get()),
                            ).place(x=660, rely=0.5, anchor="w")

            # Forçar
            frc_var = tk.BooleanVar(value=eng.forced)
            ctk.CTkCheckBox(rf, text="", variable=frc_var, width=20, height=20,
                            checkmark_color=self._acc, border_color=self._sep,
                            command=lambda e=eng, v=frc_var: setattr(e, "forced", v.get()),
                            ).place(x=740, rely=0.5, anchor="w")

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _add_custom(self):
        dlg = ctk.CTkInputDialog(
            text="Classe do engrama (ex: EngramEntry_XXX_C):",
            title="Adicionar Engrama Custom",
        )
        ec = dlg.get_input()
        if ec and ec.strip():
            self._rows.append(_EngramRow(ec.strip(), ec.strip()))
            self._refresh_table()

    def _apply(self):
        """Gera as linhas INI e as injeta em custom_game_ini do servidor."""
        import re
        # Remove entradas existentes de OverrideNamedEngramEntries
        raw = getattr(self._srv, "custom_game_ini", "") or ""
        raw = re.sub(r'OverrideNamedEngramEntries=\([^)]+\)\n?', '', raw)

        # Adiciona apenas as que têm custo != default ou hidden/forced
        new_lines = []
        for r in self._rows:
            if r.hidden or r.forced or r.cost != [x[2] for x in _KNOWN_ENGRAMS if x[0] == r.entry_class][0:1] or True:
                new_lines.append(r.to_ini_line())

        if new_lines:
            raw = raw.rstrip() + "\n" + "\n".join(new_lines) + "\n"

        self._srv.custom_game_ini = raw
        self._app.asm_config_manager.update_server(self._srv)
        self.destroy()


def _safe_int(obj, attr: str, var: tk.StringVar):
    try:
        setattr(obj, attr, int(var.get()))
    except (ValueError, TypeError):
        pass


def open_asm_engram_editor(app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
    """Abre o editor visual de engramas (singleton por servidor)."""
    key = f"_asm_engram_{srv.id}"
    existing = getattr(app, key, None)
    if existing and existing.winfo_exists():
        existing.lift()
        existing.focus_force()
        return
    win = _EngramEditorWindow(app, srv, app)
    setattr(app, key, win)
