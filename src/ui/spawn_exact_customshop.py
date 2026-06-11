"""
Fase 6.5 — Integração SpawnExact ↔ CustomShop.

Permite exportar um comando SpawnExactDino gerado diretamente para
a lista de Comandos RCON de um kit no config.json da CustomShop.

Fluxo:
  1. Usuário gera o comando no painel SpawnExact
  2. Clica "Adicionar ao Kit"
  3. Diálogo exibe kits existentes ou cria novo
  4. Comando é inserido em Kit > Commands > [...]
  5. config.json é salvo
"""
from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from typing import Any, Dict, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import get_theme

_PROJECT_ROOT       = Path(__file__).resolve().parent.parent.parent
_DEFAULT_SHOP_CFG   = _PROJECT_ROOT / "plugin" / "CustomShop" / "configs" / "config.json"

_GREEN_DARK  = "#15803d"
_GREEN_HOVER = "#14532d"
_BG          = "#020617"
_INNER       = "#16162a"
_BDR         = "#2a2a45"


# ── Helpers de arquivo ────────────────────────────────────────────────────────

def _load_shop_cfg(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"Settings": {}, "Items": {}, "Kits": {}}


def _save_shop_cfg(path: Path, data: Dict[str, Any]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return True
    except Exception as exc:
        from tkinter import messagebox
        messagebox.showerror("Erro ao Salvar", str(exc))
        return False


def _resolve_cfg_path(srv_cfg_path: Optional[str]) -> Path:
    """Resolve o caminho do config.json: prioritiza o do servidor, senão o padrão."""
    if srv_cfg_path and Path(srv_cfg_path).exists():
        return Path(srv_cfg_path)
    return _DEFAULT_SHOP_CFG


# ── Diálogo principal ─────────────────────────────────────────────────────────

def open_add_to_kit_dialog(
    parent: ctk.CTkToplevel,
    command: str,
    shop_cfg_path: Optional[str] = None,
) -> None:
    """Abre o diálogo para adicionar *command* à lista RCON de um kit CustomShop."""
    if not command.strip():
        from tkinter import messagebox
        messagebox.showwarning("Sem Comando", "Gere o comando SpawnExact antes de exportar.")
        return

    cfg_path = _resolve_cfg_path(shop_cfg_path)
    data = _load_shop_cfg(cfg_path)
    _AddToKitDialog(parent, command, cfg_path, data)


class _AddToKitDialog(ctk.CTkToplevel):
    """Diálogo de exportação SpawnExact → kit CustomShop."""

    def __init__(
        self,
        parent: ctk.CTkToplevel,
        command: str,
        cfg_path: Path,
        data: Dict[str, Any],
    ) -> None:
        super().__init__(parent)
        self._command  = command
        self._cfg_path = cfg_path
        self._data     = data

        th = get_theme("tek")
        self._acc  = th["accent"]
        self._bg   = th["bg"]
        self._card = th["card_bg"]
        self._sep  = th.get("separator", "#1e293b")
        self._t1   = th["text_primary"]
        self._t2   = th["text_secondary"]
        self._t3   = th.get("text_muted", "#475569")

        self.title("Adicionar ao Kit — CustomShop")
        self.geometry("560x500")
        self.configure(fg_color=self._bg)
        self.grab_set()

        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ── Cabeçalho ─────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=self._card, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(hdr, text="📦  Exportar para Kit CustomShop",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=self._acc).pack(padx=16, pady=12, anchor="w")

        # ── Preview do comando ─────────────────────────────────────────────
        prev_fr = ctk.CTkFrame(self, fg_color=self._card, corner_radius=8,
                                border_width=1, border_color=self._sep)
        prev_fr.grid(row=1, column=0, padx=12, pady=(8, 4), sticky="ew")
        ctk.CTkLabel(prev_fr, text="Comando a exportar:",
                     font=ctk.CTkFont(size=11), text_color=self._t3).pack(padx=10, pady=(6, 2), anchor="w")
        box = ctk.CTkTextbox(prev_fr, height=56, fg_color=self._bg,
                              text_color=self._acc,
                              font=ctk.CTkFont(family="Consolas", size=10),
                              wrap="word", state="normal")
        box.pack(fill="x", padx=8, pady=(0, 8))
        box.insert("1.0", self._command)
        box.configure(state="disabled")

        # ── Seleção de kit ─────────────────────────────────────────────────
        sel_fr = ctk.CTkFrame(self, fg_color=self._card, corner_radius=8,
                               border_width=1, border_color=self._sep)
        sel_fr.grid(row=2, column=0, padx=12, pady=4, sticky="nsew")
        sel_fr.grid_columnconfigure(0, weight=1)
        sel_fr.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(sel_fr, text="Selecione ou crie um kit:",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=self._t1).grid(row=0, column=0, padx=10, pady=(8, 4), sticky="w")

        list_wrap = ctk.CTkFrame(sel_fr, fg_color="#0d1220", corner_radius=6)
        list_wrap.grid(row=1, column=0, padx=8, pady=4, sticky="nsew")
        list_wrap.grid_columnconfigure(0, weight=1)
        list_wrap.grid_rowconfigure(0, weight=1)

        self._kit_listbox = tk.Listbox(
            list_wrap,
            bg="#0d1220", fg=self._t1, selectbackground=self._acc,
            selectforeground="#000", activestyle="none",
            relief="flat", borderwidth=0, highlightthickness=0,
            font=("Consolas", 11), exportselection=False,
        )
        self._kit_listbox.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        sb = ctk.CTkScrollbar(list_wrap, command=self._kit_listbox.yview,
                               fg_color=self._card, button_color=self._sep)
        sb.grid(row=0, column=1, sticky="ns")
        self._kit_listbox.configure(yscrollcommand=sb.set)

        kits = self._data.get("Kits", {})
        for kit_id in sorted(kits.keys()):
            self._kit_listbox.insert("end", kit_id)

        # Campo novo kit
        new_fr = ctk.CTkFrame(sel_fr, fg_color="transparent")
        new_fr.grid(row=2, column=0, padx=8, pady=(2, 8), sticky="ew")
        new_fr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(new_fr, text="Ou crie um novo kit com ID:",
                     text_color=self._t3, font=ctk.CTkFont(size=11)).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))
        self._new_kit_var = tk.StringVar()
        ctk.CTkEntry(new_fr, textvariable=self._new_kit_var,
                     placeholder_text="ex: spawn_rex_padrão",
                     fg_color=self._bg, text_color=self._t1,
                     border_color=self._sep).grid(row=1, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(new_fr, text="Criar e Selecionar", width=140, height=28,
                       fg_color=self._sep, hover_color="#2a2a45",
                       text_color=self._t2, font=ctk.CTkFont(size=11),
                       command=self._create_kit).grid(row=1, column=1)

        # ── Config path info ───────────────────────────────────────────────
        path_lbl = str(self._cfg_path)
        if len(path_lbl) > 60:
            path_lbl = "…" + path_lbl[-57:]
        ctk.CTkLabel(self, text=f"Config: {path_lbl}",
                     font=ctk.CTkFont(size=9), text_color=self._t3).grid(
            row=3, column=0, padx=12, pady=(2, 0), sticky="w")

        # ── Botões ─────────────────────────────────────────────────────────
        btn_fr = ctk.CTkFrame(self, fg_color="transparent")
        btn_fr.grid(row=4, column=0, pady=10)

        ctk.CTkButton(btn_fr, text="✔ Adicionar ao Kit", width=160, height=36,
                       fg_color=self._acc, hover_color=th["accent_hover"] if (th := get_theme("tek")) else "#0e7490",
                       text_color="#000", font=ctk.CTkFont(size=13, weight="bold"),
                       command=self._add_to_kit).pack(side="left", padx=8)
        ctk.CTkButton(btn_fr, text="Cancelar", width=90, height=36,
                       fg_color=self._sep, hover_color="#2a2a45",
                       text_color=self._t2, font=ctk.CTkFont(size=12),
                       command=self.destroy).pack(side="left", padx=8)

        self._status_lbl = ctk.CTkLabel(self, text="",
                                         font=ctk.CTkFont(size=11), text_color="#4ade80")
        self._status_lbl.grid(row=5, column=0, pady=(0, 8))

    def _create_kit(self) -> None:
        kit_id = self._new_kit_var.get().strip()
        if not kit_id:
            self._status_lbl.configure(text="Digite um ID para o novo kit.", text_color="#ef4444")
            return
        kits = self._data.setdefault("Kits", {})
        if kit_id not in kits:
            kits[kit_id] = {
                "Price": 0,
                "Description": kit_id,
                "DefaultAmount": 1,
                "Items": [],
                "Commands": [],
            }
        # Selecionar na listbox
        all_ids = sorted(kits.keys())
        self._kit_listbox.delete(0, "end")
        for k in all_ids:
            self._kit_listbox.insert("end", k)
        idx = all_ids.index(kit_id) if kit_id in all_ids else 0
        self._kit_listbox.selection_set(idx)
        self._kit_listbox.see(idx)
        self._new_kit_var.set("")
        self._status_lbl.configure(
            text=f'Kit "{kit_id}" criado e selecionado.',
            text_color="#4ade80",
        )

    def _add_to_kit(self) -> None:
        sel = self._kit_listbox.curselection()
        if not sel:
            self._status_lbl.configure(
                text="Selecione ou crie um kit primeiro.",
                text_color="#ef4444",
            )
            return

        all_ids = sorted(self._data.get("Kits", {}).keys())
        kit_id  = all_ids[sel[0]]
        kit     = self._data["Kits"][kit_id]

        cmds: list = kit.setdefault("Commands", [])
        if self._command not in cmds:
            cmds.append(self._command)

        if _save_shop_cfg(self._cfg_path, self._data):
            self._status_lbl.configure(
                text=f'Comando adicionado ao kit "{kit_id}" e salvo.',
                text_color="#4ade80",
            )
            self.after(2000, self.destroy)
