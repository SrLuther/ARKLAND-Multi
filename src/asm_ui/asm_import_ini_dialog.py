"""
TEK — Diálogo de Importação e Sincronização de INI

Permite carregar GameUserSettings.ini / Game.ini de qualquer diretório
e aplicar as configurações ao servidor atual ou sincronizar com outros.

Campos NUNCA importados: nome do servidor, portas, diretório de instalação,
mapa, save dir, cluster, branch e args extras.
"""
from __future__ import annotations

import copy
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig
from ..asm_engine.asm_ini_manager import read_ini_from_paths
from ..asm_engine.asm_config_categories import ASM_EXCLUDED_FIELDS, iter_import_categories
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


# ── Campos que NUNCA são importados ───────────────────────────────────────────
_EXCLUDED_FIELDS = ASM_EXCLUDED_FIELDS


# Categorias: ver asm_engine.asm_config_categories (fonte única com presets)
def _categories() -> list[tuple[str, list[str]]]:
    return list(iter_import_categories())


# ── Diálogo ────────────────────────────────────────────────────────────────────

class _ImportIniDialog(ctk.CTkToplevel):
    """Modal de importação e sincronização de configurações INI."""

    def __init__(self, parent: ctk.CTk, app: "ARKServerManagerApp", srv: AsmServerConfig):
        super().__init__(parent)
        self._app  = app
        self._srv  = srv
        self._tmp_cfg: AsmServerConfig | None = None
        self._theme = get_theme("tek")

        self.title("Importar / Sincronizar INI")
        self.geometry("880x680")
        self.minsize(700, 500)
        self.resizable(True, True)
        self.transient(parent)
        self.configure(fg_color=self._theme["bg"])

        # Variáveis de caminhos de arquivo
        self._gus_var  = tk.StringVar()
        self._game_var = tk.StringVar()

        # Pré-preenche com o diretório de instalação do servidor, se disponível
        if srv.install_dir:
            base = (
                Path(srv.install_dir)
                / "ShooterGame" / "Saved" / "Config" / "WindowsServer"
            )
            gus  = base / "GameUserSettings.ini"
            game = base / "Game.ini"
            if gus.exists():
                self._gus_var.set(str(gus))
            if game.exists():
                self._game_var.set(str(game))

        self._status_var = tk.StringVar(value="Aguardando arquivos…")
        self._cat_vars:  dict[str, tk.BooleanVar] = {}
        self._srv_vars:  dict[str, tk.BooleanVar] = {}
        self._sel_all_var = tk.BooleanVar(value=True)

        self._build_ui()

        self.after(100, self.lift)
        self.after(150, self.focus_force)

        # Auto-carrega se os arquivos já existem
        if self._gus_var.get() or self._game_var.get():
            self.after(300, self._load_files)

    # ── Construção da UI ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        th = self._theme
        sep = th["separator"]

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Barra de título
        self._build_titlebar()

        # Separador
        ctk.CTkFrame(self, height=1, fg_color=sep).grid(
            row=0, column=0, sticky="ews")

        # Área de conteúdo rolável
        scroll = ctk.CTkScrollableFrame(
            self, fg_color=th["bg"], corner_radius=0,
            scrollbar_button_color=sep,
        )
        scroll.grid(row=1, column=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)

        r = 0
        r = self._build_file_section(scroll, r)
        r = self._build_categories_section(scroll, r)
        r = self._build_apply_section(scroll, r)
        r = self._build_sync_section(scroll, r)
        ctk.CTkFrame(scroll, height=24, fg_color="transparent").grid(
            row=r, column=0, sticky="ew")

    def _build_titlebar(self) -> None:
        th = self._theme
        tb = ctk.CTkFrame(self, fg_color=th["card_bg"], corner_radius=0, height=54)
        tb.grid(row=0, column=0, sticky="ew")
        tb.grid_propagate(False)
        tb.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            tb, text="📥  Importar / Sincronizar INI",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=th["accent"],
        ).grid(row=0, column=0, padx=16, pady=14, sticky="w")

        ctk.CTkLabel(
            tb, text=f"Servidor: {self._srv.name}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=th["text_secondary"],
        ).grid(row=0, column=1, padx=0, pady=0, sticky="w")

        ctk.CTkButton(
            tb, text="✕", width=36, height=36, corner_radius=6,
            fg_color="transparent", hover_color=th["accent_muted_bg"],
            text_color=th["text_secondary"],
            command=self.destroy,
        ).grid(row=0, column=2, padx=12, pady=0, sticky="e")

    def _section_header(self, parent: ctk.CTkScrollableFrame,
                        row: int, text: str) -> int:
        th = self._theme
        f = ctk.CTkFrame(parent, fg_color=th["card_bg"], corner_radius=8)
        f.grid(row=row, column=0, sticky="ew", padx=16, pady=(12, 4))
        ctk.CTkLabel(
            f, text=text,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=th["accent"],
        ).grid(row=0, column=0, padx=12, pady=8, sticky="w")
        return row + 1

    # ── Seção: Arquivos INI ───────────────────────────────────────────────────

    def _build_file_section(self, parent: ctk.CTkScrollableFrame, row: int) -> int:
        th = self._theme
        row = self._section_header(parent, row, "📁  Arquivos INI")

        card = ctk.CTkFrame(parent, fg_color=th["card_bg"], corner_radius=8)
        card.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 4))
        card.grid_columnconfigure(1, weight=1)
        row += 1

        font_lbl  = ctk.CTkFont(family="Segoe UI", size=11)
        font_mono = ctk.CTkFont(family="Consolas", size=10)

        for i, (lbl_text, path_var) in enumerate([
            ("GameUserSettings.ini", self._gus_var),
            ("Game.ini",             self._game_var),
        ]):
            ctk.CTkLabel(
                card, text=lbl_text, width=175, anchor="e",
                font=font_lbl, text_color=th["text_secondary"],
            ).grid(row=i, column=0, padx=(12, 6), pady=(8, 4), sticky="e")

            ctk.CTkEntry(
                card, textvariable=path_var,
                font=font_mono, height=30,
                fg_color=th["bg"],
                border_color=th["separator"],
                text_color=th["text_primary"],
            ).grid(row=i, column=1, padx=(0, 4), pady=(8, 4), sticky="ew")

            _var = path_var
            ctk.CTkButton(
                card, text="📂", width=34, height=30,
                fg_color=th["accent_muted_bg"], hover_color=th["accent_dark"],
                text_color=th["accent"], corner_radius=6,
                command=lambda v=_var, t=lbl_text: self._browse(v, t),
            ).grid(row=i, column=2, padx=(0, 12), pady=(8, 4))

        # Linha de botão + status
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.grid(row=2, column=0, columnspan=3, sticky="ew", padx=12, pady=(4, 10))
        btn_row.grid_columnconfigure(0, weight=1)

        self._status_lbl = ctk.CTkLabel(
            btn_row, textvariable=self._status_var,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=th["text_secondary"],
        )
        self._status_lbl.grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            btn_row, text="📂  Carregar", width=130, height=32,
            fg_color=th["accent_muted_bg"], hover_color=th["accent_dark"],
            text_color=th["accent"], corner_radius=6,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._load_files,
        ).grid(row=0, column=1, sticky="e")

        return row

    # ── Seção: Categorias ─────────────────────────────────────────────────────

    def _build_categories_section(self, parent: ctk.CTkScrollableFrame,
                                   row: int) -> int:
        th = self._theme
        row = self._section_header(parent, row, "⚙️  Categorias a Importar / Sincronizar")

        card = ctk.CTkFrame(parent, fg_color=th["card_bg"], corner_radius=8)
        card.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 4))
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=1)
        row += 1

        font_check = ctk.CTkFont(family="Segoe UI", size=11)

        # Linha "Selecionar Tudo" + contador
        sel_row = ctk.CTkFrame(card, fg_color="transparent")
        sel_row.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 4))

        ctk.CTkCheckBox(
            sel_row, text="Selecionar Tudo",
            variable=self._sel_all_var,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=th["text_primary"],
            fg_color=th["accent"], hover_color=th["accent_hover"],
            border_color=th["separator"],
            command=self._on_select_all,
        ).pack(side="left")

        self._field_count_lbl = ctk.CTkLabel(
            sel_row, text="",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=th["text_muted"],
        )
        self._field_count_lbl.pack(side="right", padx=8)

        # Checkboxes em 2 colunas
        for i, (cat_label, _) in enumerate(_categories()):
            var = tk.BooleanVar(value=True)
            self._cat_vars[cat_label] = var

            col = i % 2
            r   = (i // 2) + 1

            ctk.CTkCheckBox(
                card, text=cat_label, variable=var,
                font=font_check,
                text_color=th["text_primary"],
                fg_color=th["accent"], hover_color=th["accent_hover"],
                border_color=th["separator"],
                command=self._on_cat_changed,
            ).grid(row=r, column=col, sticky="w", padx=(16, 8), pady=2)

        # Padding inferior
        ctk.CTkFrame(card, height=8, fg_color="transparent").grid(
            row=(len(_categories()) // 2) + 2, column=0, columnspan=2, sticky="ew")

        return row

    # ── Seção: Aplicar ao servidor atual ──────────────────────────────────────

    def _build_apply_section(self, parent: ctk.CTkScrollableFrame,
                              row: int) -> int:
        th = self._theme
        row = self._section_header(parent, row, "✅  Aplicar neste servidor")

        card = ctk.CTkFrame(parent, fg_color=th["card_bg"], corner_radius=8)
        card.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 4))
        card.grid_columnconfigure(0, weight=1)
        row += 1

        ctk.CTkLabel(
            card,
            text=(
                f"Aplica as categorias selecionadas ao servidor \"{self._srv.name}\". "
                "Nome, portas, mapa e diretório de instalação são sempre preservados."
            ),
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=th["text_secondary"],
            wraplength=700, justify="left",
        ).grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")

        self._apply_btn = ctk.CTkButton(
            card, text="✅  Aplicar neste servidor",
            width=210, height=36,
            fg_color=th["accent_muted_bg"], hover_color=th["accent_dark"],
            text_color=th["accent"],
            border_width=1, border_color=th["accent_dark"],
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            state="disabled",
            command=self._apply_to_current,
        )
        self._apply_btn.grid(row=1, column=0, padx=12, pady=(4, 12), sticky="e")

        return row

    # ── Seção: Sincronizar para outros servidores ──────────────────────────────

    def _build_sync_section(self, parent: ctk.CTkScrollableFrame,
                             row: int) -> int:
        th = self._theme
        row = self._section_header(parent, row, "🔄  Sincronizar para outros servidores")

        card = ctk.CTkFrame(parent, fg_color=th["card_bg"], corner_radius=8)
        card.grid(row=row, column=0, sticky="ew", padx=16, pady=(0, 4))
        card.grid_columnconfigure(0, weight=1)
        row += 1

        other_servers = [
            s for s in self._app.asm_config_manager.servers
            if s.id != self._srv.id
        ]

        if not other_servers:
            ctk.CTkLabel(
                card,
                text="Nenhum outro servidor gerenciado. Adicione servidores no Dashboard.",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=th["text_muted"],
            ).grid(row=0, column=0, padx=12, pady=12, sticky="w")
        else:
            ctk.CTkLabel(
                card,
                text=(
                    "Selecione os servidores destino. "
                    "As categorias marcadas acima sobrescreverão os campos correspondentes."
                ),
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=th["text_secondary"],
                wraplength=700, justify="left",
            ).grid(row=0, column=0, padx=12, pady=(10, 4), sticky="w")

            srv_grid = ctk.CTkFrame(card, fg_color="transparent")
            srv_grid.grid(row=1, column=0, sticky="ew", padx=12, pady=4)
            for i, s in enumerate(other_servers):
                var = tk.BooleanVar(value=False)
                self._srv_vars[s.id] = var
                col = i % 3
                r   = i // 3
                ctk.CTkCheckBox(
                    srv_grid, text=s.name, variable=var,
                    font=ctk.CTkFont(family="Segoe UI", size=11),
                    text_color=th["text_primary"],
                    fg_color=th["accent"], hover_color=th["accent_hover"],
                    border_color=th["separator"],
                ).grid(row=r, column=col, sticky="w", padx=(0, 24), pady=2)

        self._sync_btn = ctk.CTkButton(
            card, text="🔄  Sincronizar selecionados",
            width=230, height=36,
            fg_color=th["accent_muted_bg"], hover_color=th["accent_dark"],
            text_color=th["accent"],
            border_width=1, border_color=th["accent_dark"],
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            state="disabled",
            command=self._sync_to_destinations,
        )
        self._sync_btn.grid(row=99, column=0, padx=12, pady=(4, 12), sticky="e")

        return row

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _browse(self, var: tk.StringVar, title: str) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title=f"Selecionar {title}",
            filetypes=[("INI files", "*.ini"), ("All files", "*.*")],
        )
        if path:
            var.set(path)

    def _load_files(self) -> None:
        gus  = self._gus_var.get().strip()
        game = self._game_var.get().strip()

        if not gus and not game:
            self._status_var.set("⚠  Selecione pelo menos um arquivo .ini")
            self._status_lbl.configure(text_color="#f59e0b")
            return

        # Cria config temporária como cópia do servidor atual
        tmp = copy.deepcopy(self._srv)

        try:
            read_ini_from_paths(
                tmp,
                gus_path=gus  or None,
                game_path=game or None,
            )
            self._tmp_cfg = tmp

            count = self._count_importable_fields()
            self._status_var.set(f"✅  Arquivos carregados — {count} campos disponíveis")
            self._status_lbl.configure(text_color=self._theme["accent"])
            self._field_count_lbl.configure(text=f"{count} campos")

            # Habilita botões de ação
            self._apply_btn.configure(state="normal")
            self._sync_btn.configure(state="normal")

        except Exception as exc:
            self._status_var.set(f"❌  Erro: {exc}")
            self._status_lbl.configure(text_color="#ef4444")

    def _count_importable_fields(self) -> int:
        """Conta campos importáveis (todos os campos das categorias, excluindo excluídos)."""
        seen: set[str] = set()
        for _, fields in _categories():
            for f in fields:
                if f not in _EXCLUDED_FIELDS:
                    seen.add(f)
        return len(seen)

    def _on_select_all(self) -> None:
        val = self._sel_all_var.get()
        for var in self._cat_vars.values():
            var.set(val)

    def _on_cat_changed(self) -> None:
        all_checked = all(v.get() for v in self._cat_vars.values())
        self._sel_all_var.set(all_checked)

    def _get_selected_categories(self) -> list[str]:
        return [cat for cat, var in self._cat_vars.items() if var.get()]

    def _apply_categories_to(
        self,
        source: AsmServerConfig,
        target: AsmServerConfig,
        selected_cats: list[str],
    ) -> int:
        """Copia campos das categorias selecionadas de source para target.
        Retorna a contagem de campos copiados.
        """
        count = 0
        for cat_label, fields in _categories():
            if cat_label not in selected_cats:
                continue
            for field_name in fields:
                if field_name in _EXCLUDED_FIELDS:
                    continue
                if not hasattr(source, field_name) or not hasattr(target, field_name):
                    continue
                val = getattr(source, field_name)
                if isinstance(val, list):
                    val = copy.deepcopy(val)
                setattr(target, field_name, val)
                count += 1
        return count

    def _apply_to_current(self) -> None:
        if self._tmp_cfg is None:
            return
        selected = self._get_selected_categories()
        if not selected:
            messagebox.showwarning(
                "Aviso", "Selecione pelo menos uma categoria.", parent=self)
            return

        count = self._apply_categories_to(self._tmp_cfg, self._srv, selected)
        self._app.asm_config_manager.update_server(self._srv)
        self.destroy()
        self._app._asm_open_server_panel(self._srv.id)
        messagebox.showinfo(
            "Importação concluída",
            f"✅  {count} campos aplicados ao servidor \"{self._srv.name}\".\n\n"
            "O painel foi atualizado com as novas configurações.\n"
            "Verifique e salve para gravar nos arquivos .ini do servidor.",
            parent=self._app,
        )

    def _sync_to_destinations(self) -> None:
        if self._tmp_cfg is None:
            return
        selected_cats = self._get_selected_categories()
        if not selected_cats:
            messagebox.showwarning(
                "Aviso", "Selecione pelo menos uma categoria.", parent=self)
            return

        dest_ids = [sid for sid, var in self._srv_vars.items() if var.get()]
        if not dest_ids:
            messagebox.showwarning(
                "Aviso", "Selecione pelo menos um servidor destino.", parent=self)
            return

        srv_map = {s.id: s for s in self._app.asm_config_manager.servers}
        total   = 0
        synced: list[str] = []

        for sid in dest_ids:
            target = srv_map.get(sid)
            if target:
                n = self._apply_categories_to(self._tmp_cfg, target, selected_cats)
                total  += n
                synced.append(target.name)
                self._app.asm_config_manager.update_server(target)

        if synced:
            self.destroy()
            messagebox.showinfo(
                "Sincronização concluída",
                f"✅  {total} campos sincronizados para {len(synced)} servidor(es):\n\n"
                + "\n".join(f"  • {n}" for n in synced)
                + "\n\nAcesse cada servidor e salve para gravar nos arquivos .ini.",
                parent=self._app,
            )


# ── Ponto de entrada (singleton por servidor) ──────────────────────────────────

def open_asm_import_ini_dialog(
    app: "ARKServerManagerApp",
    srv: AsmServerConfig,
) -> None:
    """Abre o diálogo de importação/sincronização de INI (singleton por servidor)."""
    key = f"_asm_import_ini_{srv.id}"
    win: _ImportIniDialog | None = getattr(app, key, None)
    if win and win.winfo_exists():
        win.lift()
        win.focus_force()
        return

    win = _ImportIniDialog(app, app, srv)
    setattr(app, key, win)
    win.protocol("WM_DELETE_WINDOW", lambda: (win.destroy(), setattr(app, key, None)))
