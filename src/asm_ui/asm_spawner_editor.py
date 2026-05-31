"""
S4.5 — Editor Visual de Spawner.
Árvore de containers de spawn com adição/remoção de entradas,
multiplicadores e geração de NPCSeedCreatureOverrides para Game.ini.
"""
from __future__ import annotations

import re
import tkinter as tk
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import get_theme
from ..asm_engine.asm_server_config import AsmServerConfig

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


# ── Containers de spawn conhecidos ────────────────────────────────────────────
_KNOWN_CONTAINERS = [
    "DinoSpawnEntriesBeach_C",
    "DinoSpawnEntriesSnow_C",
    "DinoSpawnEntriesJungle_C",
    "DinoSpawnEntriesRedwoods_C",
    "DinoSpawnEntriesDesert_C",
    "DinoSpawnEntriesSwamp_C",
    "DinoSpawnEntriesVolcano_C",
    "DinoSpawnEntriesOcean_C",
    "DinoSpawnEntriesDeepOcean_C",
    "DinoSpawnEntriesCave_C",
    "DinoSpawnEntriesAberration_C",
    "DinoSpawnEntriesExtinction_C",
    "DinoSpawnEntriesGenesis_C",
]


class _SpawnEntry:
    __slots__ = ("npc_class", "weight", "max_pct")

    def __init__(self, npc_class: str, weight: float = 1.0, max_pct: float = 0.1):
        self.npc_class = npc_class
        self.weight    = weight
        self.max_pct   = max_pct


class _SpawnContainer:
    def __init__(self, container_class: str):
        self.container_class = container_class
        self.entries: List[_SpawnEntry] = []
        self.limit_multiplier = 1.0

    def to_ini_lines(self) -> List[str]:
        if not self.entries:
            return []
        lines = []
        entries_str = ",".join(
            f'(AnEntryName="CustomEntry",EntryWeight={e.weight:.2f},'
            f'NPCsToSpawnStrings=("{e.npc_class}"),'
            f'MaxPercentageOfDesiredNumToAllow={e.max_pct:.2f})'
            for e in self.entries
        )
        lines.append(
            f'NPCReplacements=(FromClassName="{self.container_class}",'
            f'ToClassName="")'
        )
        lines.append(
            f'ConfigAddNPCSpawnEntriesContainer=(NPCSpawnEntriesContainerClassString='
            f'"{self.container_class}",'
            f'NPCSpawnEntries=({entries_str}),'
            f'NPCSpawnLimits=())'
        )
        return lines


class _SpawnerEditorWindow(ctk.CTkToplevel):
    def __init__(self, parent, srv: AsmServerConfig, app: "ARKServerManagerApp"):
        super().__init__(parent)
        th = get_theme("tek")
        self._bg    = th["bg"]
        self._cg    = th["card_bg"]
        self._sep   = th["separator"]
        self._acc   = th["accent"]
        self._t_sec = th["text_secondary"]
        self._t_mut = th["text_muted"]
        self._acc_mb = th["accent_muted_bg"]

        self.title(f"Editor de Spawner — {srv.name}")
        self.geometry("1100x660")
        self.configure(fg_color=self._bg)
        self.resizable(True, True)
        self.after(100, self.lift)
        self.after(150, self.focus_force)

        self._srv = srv
        self._app = app
        self._containers: List[_SpawnContainer] = []
        self._selected_container: Optional[_SpawnContainer] = None
        self._filter_var = tk.StringVar()

        self._load_initial()
        self._build_ui()
        self._refresh_container_list()

    # ── Dados ─────────────────────────────────────────────────────────────────

    def _load_initial(self):
        raw = getattr(self._srv, "spawner_overrides_raw", "") or ""
        pat = re.compile(
            r'ConfigAddNPCSpawnEntriesContainer=\(NPCSpawnEntriesContainerClassString="([^"]+)"',
            re.IGNORECASE,
        )
        seen = set()
        for m in pat.finditer(raw):
            cc = m.group(1)
            if cc not in seen:
                self._containers.append(_SpawnContainer(cc))
                seen.add(cc)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Painel esquerdo: lista de containers ──────────────────────────────
        left = ctk.CTkFrame(self, fg_color=self._cg, corner_radius=0, width=260)
        left.grid(row=0, column=0, sticky="nsew")
        left.grid_propagate(False)
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Containers de Spawn",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=self._acc).grid(row=0, column=0, padx=10, pady=(12, 4), sticky="w")

        # Filtro
        self._filter_var = tk.StringVar()
        ctk.CTkEntry(left, textvariable=self._filter_var,
                     placeholder_text="Filtrar...", height=26,
                     ).grid(row=1, column=0, padx=8, pady=(0, 4), sticky="ew")
        self._filter_var.trace_add("write", lambda *_: self._refresh_container_list())

        self._container_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent", corner_radius=0)
        self._container_scroll.grid(row=2, column=0, sticky="nsew")
        self._container_scroll.grid_columnconfigure(0, weight=1)

        # Botão adicionar container
        add_bar = ctk.CTkFrame(left, fg_color="transparent")
        add_bar.grid(row=3, column=0, sticky="ew", padx=8, pady=8)
        add_bar.grid_columnconfigure(0, weight=1)

        self._new_container_var = tk.StringVar()
        ctk.CTkComboBox(add_bar, variable=self._new_container_var,
                        values=_KNOWN_CONTAINERS,
                        height=26, font=ctk.CTkFont(size=10),
                        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(add_bar, text="+", width=28, height=26,
                      fg_color=self._acc_mb, hover_color="#052e16",
                      text_color=self._acc, corner_radius=4,
                      command=self._add_container,
                      ).grid(row=0, column=1)

        # ── Painel direito: entradas do container selecionado ─────────────────
        self._right = ctk.CTkFrame(self, fg_color=self._bg, corner_radius=0)
        self._right.grid(row=0, column=1, sticky="nsew")
        self._right.grid_columnconfigure(0, weight=1)
        self._right.grid_rowconfigure(1, weight=1)

        # Toolbar do lado direito
        self._right_toolbar = ctk.CTkFrame(self._right, fg_color=self._cg, corner_radius=0)
        self._right_toolbar.grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(
            self._right_toolbar, text="✅ Aplicar ao Servidor", width=160, height=28,
            fg_color=self._acc_mb, hover_color="#052e16",
            border_width=1, border_color=self._acc, text_color=self._acc,
            font=ctk.CTkFont(size=10),
            command=self._apply,
        ).pack(side="right", padx=8, pady=8)

        self._right_title = ctk.CTkLabel(
            self._right_toolbar, text="Selecione um container →",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=self._t_sec,
        )
        self._right_title.pack(side="left", padx=12, pady=8)

        # Scroll de entradas
        self._entries_scroll = ctk.CTkScrollableFrame(self._right, fg_color=self._bg, corner_radius=0)
        self._entries_scroll.grid(row=1, column=0, sticky="nsew")
        self._entries_scroll.grid_columnconfigure((0, 1, 2), weight=1)

    # ── Lista de containers ───────────────────────────────────────────────────

    def _refresh_container_list(self, *_):
        for w in self._container_scroll.winfo_children():
            w.destroy()
        flt = self._filter_var.get().strip().lower()
        for c in self._containers:
            if flt and flt not in c.container_class.lower():
                continue
            is_sel = (c is self._selected_container)
            btn = ctk.CTkButton(
                self._container_scroll,
                text=c.container_class.replace("DinoSpawnEntries", "").replace("_C", ""),
                height=32, anchor="w",
                fg_color=self._acc_mb if is_sel else "transparent",
                hover_color="#1e293b",
                text_color=self._acc if is_sel else self._t_sec,
                font=ctk.CTkFont(size=10),
                command=lambda cc=c: self._select_container(cc),
            )
            btn.pack(fill="x", padx=4, pady=1)

    def _select_container(self, c: _SpawnContainer):
        self._selected_container = c
        self._refresh_container_list()
        self._refresh_entries()
        self._right_title.configure(text=c.container_class)

    def _add_container(self):
        cc = self._new_container_var.get().strip()
        if not cc:
            return
        if any(c.container_class == cc for c in self._containers):
            return
        new_c = _SpawnContainer(cc)
        self._containers.append(new_c)
        self._refresh_container_list()
        self._select_container(new_c)

    # ── Entradas do container ─────────────────────────────────────────────────

    def _refresh_entries(self):
        for w in self._entries_scroll.winfo_children():
            w.destroy()

        if not self._selected_container:
            return

        c = self._selected_container
        th = get_theme("tek")

        # Cabeçalho
        hdr = ctk.CTkFrame(self._entries_scroll, fg_color="#0a111c", corner_radius=0)
        hdr.pack(fill="x", pady=(0, 4))
        for i, (txt, w) in enumerate([("Classe NPC", 350), ("Peso", 80), ("Max %", 80)]):
            ctk.CTkLabel(hdr, text=txt,
                         font=ctk.CTkFont(size=10, weight="bold"),
                         text_color=th["text_secondary"], width=w, anchor="w",
                         ).grid(row=0, column=i, padx=(12 if i == 0 else 4, 0), pady=6, sticky="w")

        for idx, entry in enumerate(c.entries):
            row_bg = self._bg if idx % 2 == 0 else "#080e18"
            rf = ctk.CTkFrame(self._entries_scroll, fg_color=row_bg, corner_radius=0, height=34)
            rf.pack(fill="x")
            rf.pack_propagate(False)

            ctk.CTkLabel(rf, text=entry.npc_class[:48],
                         font=ctk.CTkFont(family="Consolas", size=9),
                         text_color=th["text_secondary"],
                         ).place(x=12, rely=0.5, anchor="w")

            wt_var = tk.StringVar(value=f"{entry.weight:.2f}")
            ctk.CTkEntry(rf, textvariable=wt_var, width=70, height=24,
                         font=ctk.CTkFont(size=10)).place(x=362, rely=0.5, anchor="w")
            wt_var.trace_add("write", lambda *_, e=entry, v=wt_var: _safe_float(e, "weight", v))

            mp_var = tk.StringVar(value=f"{entry.max_pct:.2f}")
            ctk.CTkEntry(rf, textvariable=mp_var, width=70, height=24,
                         font=ctk.CTkFont(size=10)).place(x=442, rely=0.5, anchor="w")
            mp_var.trace_add("write", lambda *_, e=entry, v=mp_var: _safe_float(e, "max_pct", v))

            ctk.CTkButton(rf, text="✕", width=22, height=22,
                          fg_color="#7f1d1d", hover_color="#991b1b",
                          text_color="#fca5a5", corner_radius=4, font=ctk.CTkFont(size=9),
                          command=lambda e=entry: self._remove_entry(e),
                          ).place(x=524, rely=0.5, anchor="w")

        # Formulário de adição
        add_f = ctk.CTkFrame(self._entries_scroll, fg_color="#0a111c", corner_radius=6)
        add_f.pack(fill="x", padx=4, pady=8)
        add_f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(add_f, text="Classe NPC:", font=ctk.CTkFont(size=10),
                     text_color=th["text_muted"]).grid(row=0, column=0, padx=(10, 4), pady=8, sticky="w")
        new_npc_var = tk.StringVar()
        ctk.CTkEntry(add_f, textvariable=new_npc_var,
                     placeholder_text="ex: Dino_Character_BP_Raptor_C",
                     height=26,
                     ).grid(row=0, column=1, padx=(0, 4), pady=8, sticky="ew")
        ctk.CTkButton(add_f, text="Adicionar", width=90, height=26,
                      fg_color=self._acc_mb, hover_color="#052e16",
                      border_width=1, border_color=self._acc, text_color=self._acc,
                      font=ctk.CTkFont(size=10),
                      command=lambda: self._add_entry(new_npc_var.get()),
                      ).grid(row=0, column=2, padx=(0, 10), pady=8)

    def _add_entry(self, npc_class: str):
        if not npc_class.strip() or not self._selected_container:
            return
        self._selected_container.entries.append(_SpawnEntry(npc_class.strip()))
        self._refresh_entries()

    def _remove_entry(self, entry: _SpawnEntry):
        if self._selected_container:
            self._selected_container.entries = [
                e for e in self._selected_container.entries if e is not entry
            ]
            self._refresh_entries()

    # ── Aplicar ───────────────────────────────────────────────────────────────

    def _apply(self):
        lines = []
        for c in self._containers:
            lines.extend(c.to_ini_lines())
        self._srv.spawner_overrides_raw = "\n".join(lines)
        self._app.asm_config_manager.update_server(self._srv)
        self.destroy()


def _safe_float(obj, attr: str, var: tk.StringVar):
    try:
        setattr(obj, attr, float(var.get()))
    except (ValueError, TypeError):
        pass


def open_asm_spawner_editor(app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
    """Abre editor visual de spawner (singleton por servidor)."""
    key = f"_asm_spawner_{srv.id}"
    existing = getattr(app, key, None)
    if existing and existing.winfo_exists():
        existing.lift()
        existing.focus_force()
        return
    win = _SpawnerEditorWindow(app, srv, app)
    setattr(app, key, win)
