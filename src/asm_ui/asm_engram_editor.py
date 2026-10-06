"""
S4.3 — Editor Visual de Engramas.
Tabela interativa com filtro em tempo real.
Gera OverrideNamedEngramEntries para Game.ini.
"""
from __future__ import annotations

import tkinter as tk
from typing import List, TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import get_theme
from ..asm_engine.asm_engram_entries import (
    ENGRAM_CLASS_MAX_LEN,
    EngramOverride,
    clamp_engram_class,
    class_column_text,
    collect_engram_sources,
    delete_engram_row,
    edit_engram_class,
    load_engram_rows,
    name_column_text,
    persist_engram_rows,
)
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

# A soma cabe na janela. A coluna Classe (430px, Consolas 11) mostra 50
# caracteres — ``EngramEntry_BlueprintStation_Metal_C`` (36) fica inteira.
# Editar e Excluir ficam na área visível; o scroll só anda na vertical.
_TABLE_HEADERS = (
    ("Engrama", 190),
    ("Classe", 430),
    ("Custo", 52),
    ("Nível", 52),
    ("Esconder", 68),
    ("Forçar", 118),
    ("Editar", 74),
    ("Excluir", 74),
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
        self.geometry("1460x680")
        self.minsize(1280, 480)
        self.configure(fg_color=self._bg)
        self.resizable(True, True)
        self.after(100, self.lift)
        self.after(150, self.focus_force)

        self._srv = srv
        self._app = app
        self._rows: List[EngramOverride] = []
        self._filter_text = tk.StringVar()
        self._row_widgets: List[dict] = []
        self._row_menus: list[tk.Menu] = []

        self._load_initial()
        self._build_ui()
        self._refresh_table()

    # ── Dados ─────────────────────────────────────────────────────────────────

    def _load_initial(self):
        """Carrega engramas já configurados ou defaults conhecidos."""
        self._rows = load_engram_rows(
            collect_engram_sources(self._srv),
            _KNOWN_ENGRAMS,
        )

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
        for col_i, (label, width) in enumerate(_TABLE_HEADERS):
            hdr.grid_columnconfigure(col_i, weight=1 if col_i == 1 else 0, minsize=width)
            ctk.CTkLabel(
                hdr, text=label,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                text_color=self._t_sec, anchor="w",
            ).grid(row=0, column=col_i, padx=(10 if col_i == 0 else 4, 0), pady=6, sticky="w")

        # Tabela (scroll)
        self._scroll = ctk.CTkScrollableFrame(self, fg_color=self._bg, corner_radius=0)
        self._scroll.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)

    def _refresh_table(self, *_):
        for menu in self._row_menus:
            try:
                menu.destroy()
            except tk.TclError:
                pass
        self._row_menus = []
        for w in self._scroll.winfo_children():
            w.destroy()
        self._row_widgets = []

        txt = self._filter_text.get().strip().lower()
        visible = [
            r for r in self._rows
            if not txt or txt in r.display_name.lower() or txt in r.entry_class.lower()
        ]

        for i, eng in enumerate(visible):
            row_bg = self._bg if i % 2 == 0 else "#080e18"
            rf = ctk.CTkFrame(self._scroll, fg_color=row_bg, corner_radius=0)
            rf.pack(fill="x", pady=1)
            for col_i, (_label, width) in enumerate(_TABLE_HEADERS):
                rf.grid_columnconfigure(col_i, weight=1 if col_i == 1 else 0, minsize=width)

            name_lbl = ctk.CTkLabel(
                rf, text=name_column_text(eng.display_name),
                font=ctk.CTkFont(size=11), text_color=self._t_sec, anchor="w",
            )
            name_lbl.grid(row=0, column=0, padx=(10, 4), pady=6, sticky="w")

            class_var = tk.StringVar(value=class_column_text(eng.entry_class))
            class_entry = ctk.CTkEntry(
                rf, textvariable=class_var, height=26, width=420,
                font=ctk.CTkFont(family="Consolas", size=11),
            )
            class_entry.grid(row=0, column=1, padx=4, pady=4, sticky="ew")
            class_var.trace_add(
                "write",
                lambda *_, e=eng, v=class_var, lbl=name_lbl: self._on_class_edited(e, v, lbl),
            )

            cost_var = tk.StringVar(value=str(eng.cost))
            ctk.CTkEntry(
                rf, textvariable=cost_var, width=48, height=26,
                font=ctk.CTkFont(size=10),
            ).grid(row=0, column=2, padx=4, pady=4, sticky="w")
            cost_var.trace_add("write", lambda *_, e=eng, v=cost_var: _safe_int(e, "cost", v))

            lvl_var = tk.StringVar(value=str(eng.level))
            ctk.CTkEntry(
                rf, textvariable=lvl_var, width=48, height=26,
                font=ctk.CTkFont(size=10),
            ).grid(row=0, column=3, padx=4, pady=4, sticky="w")
            lvl_var.trace_add("write", lambda *_, e=eng, v=lvl_var: _safe_int(e, "level", v))

            hid_var = tk.BooleanVar(value=eng.hidden)
            ctk.CTkCheckBox(
                rf, text="", variable=hid_var, width=20, height=20,
                checkmark_color=self._acc, border_color=self._sep,
                command=lambda e=eng, v=hid_var: setattr(e, "hidden", v.get()),
            ).grid(row=0, column=4, padx=4, pady=4, sticky="w")

            frc_var = tk.BooleanVar(value=eng.forced)
            ctk.CTkCheckBox(
                rf, text="", variable=frc_var, width=20, height=20,
                checkmark_color=self._acc, border_color=self._sep,
                command=lambda e=eng, v=frc_var: setattr(e, "forced", v.get()),
            ).grid(row=0, column=5, padx=4, pady=4, sticky="w")

            ctk.CTkButton(
                rf, text="Editar", width=68, height=26,
                fg_color=self._sep, hover_color="#263347",
                font=ctk.CTkFont(size=10), text_color=self._t_sec,
                command=lambda e=eng: self._edit_row(e),
            ).grid(row=0, column=6, padx=4, pady=4, sticky="w")
            ctk.CTkButton(
                rf, text="Excluir", width=68, height=26,
                fg_color="#3f1d24", hover_color="#7f1d1d",
                font=ctk.CTkFont(size=10),
                command=lambda e=eng: self._delete_row(e),
            ).grid(row=0, column=7, padx=(4, 8), pady=4, sticky="w")

            self._bind_row_actions(eng, rf, name_lbl)

    def _bind_row_actions(self, eng: EngramOverride, row_frame, name_lbl) -> None:
        """Duplo clique e menu de contexto na linha. Os botões é que executam."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Editar", command=lambda e=eng: self._edit_row(e))
        menu.add_command(label="Excluir", command=lambda e=eng: self._delete_row(e))
        self._row_menus.append(menu)

        def popup(event, m=menu):
            try:
                m.tk_popup(event.x_root, event.y_root)
            finally:
                try:
                    m.grab_release()
                except tk.TclError:
                    pass

        def edit(_event=None, row=eng):
            self._edit_row(row)
            return "break"

        targets = [row_frame, name_lbl, *name_lbl.winfo_children()]
        for widget in targets:
            widget.bind("<Double-Button-1>", edit)
            widget.bind("<Button-3>", popup)

    def _on_class_edited(self, eng: EngramOverride, var: tk.StringVar, name_lbl) -> None:
        clamped = clamp_engram_class(var.get())
        if var.get() != clamped:
            var.set(clamped)
            return
        edit_engram_class(eng, clamped)
        name_lbl.configure(text=name_column_text(eng.display_name))

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _prompt_engram_class(self, title: str, initial: str = "") -> str | None:
        """Diálogo largo o bastante para a classe inteira, com ``_C`` visível."""
        result: dict[str, str | None] = {"value": None}
        dlg = ctk.CTkToplevel(self)
        dlg.title(title)
        dlg.geometry("720x168")
        dlg.resizable(False, False)
        dlg.configure(fg_color=self._bg)
        dlg.grab_set()
        dlg.after(50, dlg.lift)

        ctk.CTkLabel(
            dlg,
            text=f"Classe do engrama, até {ENGRAM_CLASS_MAX_LEN} caracteres (ex: EngramEntry_XXX_C):",
            text_color=self._t_sec,
        ).pack(padx=16, pady=(16, 6), anchor="w")
        var = tk.StringVar(value=clamp_engram_class(initial))

        def _keep_limit(*_args) -> None:
            clamped = clamp_engram_class(var.get())
            if var.get() != clamped:
                var.set(clamped)

        var.trace_add("write", _keep_limit)
        ent = ctk.CTkEntry(
            dlg, textvariable=var, width=680, height=32,
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        ent.pack(padx=16, pady=4, anchor="w")
        ent.focus_set()
        ent.icursor("end")

        def ok() -> None:
            result["value"] = clamp_engram_class(var.get())
            dlg.grab_release()
            dlg.destroy()

        def cancel() -> None:
            dlg.grab_release()
            dlg.destroy()

        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack(pady=12, anchor="e", padx=16)
        ctk.CTkButton(btns, text="Cancelar", width=100, height=28, command=cancel,
                      fg_color=self._sep, hover_color="#263347").pack(side="right", padx=(6, 0))
        ctk.CTkButton(btns, text="OK", width=100, height=28, command=ok,
                      fg_color=self._acc_mb, hover_color="#052e16",
                      text_color=self._acc).pack(side="right")
        ent.bind("<Return>", lambda _e: ok())
        dlg.protocol("WM_DELETE_WINDOW", cancel)
        self.wait_window(dlg)
        return result["value"]

    def _add_custom(self):
        ec = self._prompt_engram_class("Adicionar Engrama Custom")
        if ec and ec.strip():
            cleaned = clamp_engram_class(ec.strip())
            if cleaned:
                self._rows.append(EngramOverride(cleaned, cleaned))
                self._refresh_table()

    def _edit_row(self, eng: EngramOverride) -> None:
        """Abre a classe desta linha (até 50 caracteres), inclusive nome já cortado."""
        typed = self._prompt_engram_class(
            "Editar engrama",
            class_column_text(eng.entry_class),
        )
        if typed is None:
            return
        cleaned = clamp_engram_class(typed.strip())
        if not cleaned:
            return
        edit_engram_class(eng, cleaned)
        self._refresh_table()

    def _delete_row(self, eng: EngramOverride) -> None:
        """Remove só esta linha. A outra com o mesmo nome permanece."""
        self._rows = delete_engram_row(self._rows, eng)
        self._refresh_table()

    def _apply(self):
        """Gera as linhas INI e as grava em engram_entries_raw do servidor."""
        persist_engram_rows(self._srv, self._rows, _KNOWN_ENGRAMS)
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
