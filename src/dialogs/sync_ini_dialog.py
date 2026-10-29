"""Dialog for previewing and synchronizing ARK INI files across servers."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _BLUE, _BLUE_HOVER, _GREEN_DARK, _GREEN_HOVER

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def open_sync_ini_dialog(app: "ARKServerManagerApp", source_server_id: str) -> None:
    """Show a diff preview and safely sync selected INIs to other servers."""
    src = app.config_manager.get_server(source_server_id)
    if not src:
        return
    if not src.install_dir or not os.path.isdir(src.install_dir):
        messagebox.showwarning(
            "Diretório indisponível",
            "Configure e salve o diretório de instalação antes de sincronizar.",
            parent=app,
        )
        return

    from ..ark_ini import get_ini_path

    source_files = {
        "GameUserSettings.ini": get_ini_path(src.install_dir, "GameUserSettings.ini"),
        "Game.ini": get_ini_path(src.install_dir, "Game.ini"),
    }
    if not any(path.exists() for path in source_files.values()):
        messagebox.showwarning(
            "Arquivos não encontrados",
            "Nenhum INI foi encontrado na pasta do servidor. Salve as configurações primeiro.",
            parent=app,
        )
        return

    other_servers = [server for server in app.config_manager.servers if server.id != source_server_id]
    if not other_servers:
        messagebox.showinfo("Sem outros servidores", "Não há outro servidor cadastrado.", parent=app)
        return

    dlg = ctk.CTkToplevel(app)
    dlg.title("Sincronizar INIs entre servidores")
    dlg.geometry("560x640")
    dlg.minsize(520, 560)
    dlg.resizable(False, False)
    dlg.transient(app)
    dlg.grab_set()

    ctk.CTkLabel(
        dlg,
        text=f"Origem: {src.name}",
        font=ctk.CTkFont(size=14, weight="bold"),
    ).pack(padx=22, pady=(18, 4), anchor="w")
    ctk.CTkLabel(
        dlg,
        text="Revise as diferenças antes de aplicar. Cada arquivo existente terá backup.",
        text_color="gray65",
        font=ctk.CTkFont(size=11),
        wraplength=470,
        justify="left",
    ).pack(padx=22, pady=(0, 12), anchor="w")

    server_vars: dict[str, tk.BooleanVar] = {}
    scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent", height=210)
    scroll.pack(fill="both", expand=True, padx=18, pady=4)
    for server in other_servers:
        usable = bool(server.install_dir and os.path.isdir(server.install_dir))
        variable = tk.BooleanVar(value=usable)
        server_vars[server.id] = variable
        ctk.CTkCheckBox(
            scroll,
            text=f"{server.name}  —  {server.install_dir or 'sem diretório configurado'}",
            variable=variable,
            state="normal" if usable else "disabled",
            checkmark_color="white",
            fg_color=_GREEN_DARK,
            hover_color=_GREEN_HOVER,
        ).pack(fill="x", padx=8, pady=3, anchor="w")

    file_frame = ctk.CTkFrame(dlg, fg_color="transparent")
    file_frame.pack(fill="x", padx=22, pady=(8, 4))
    gus_var = tk.BooleanVar(value=True)
    game_var = tk.BooleanVar(value=True)
    section_vars: dict[str, dict[str, tk.BooleanVar]] = {}

    ctk.CTkLabel(
        dlg,
        text="Seções para sincronizar (somente as marcadas serão substituídas)",
        text_color="gray75",
        anchor="w",
    ).pack(fill="x", padx=22, pady=(8, 2))
    section_scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent", height=150)
    section_scroll.pack(fill="both", expand=True, padx=18, pady=(0, 4))

    def refresh_sections() -> None:
        from ..asm_engine.ini_document import IniDocument

        previous = {
            filename: {name.casefold(): variable.get() for name, variable in variables.items()}
            for filename, variables in section_vars.items()
        }
        for child in section_scroll.winfo_children():
            child.destroy()
        section_vars.clear()
        for filename, path, enabled in (
            ("GameUserSettings.ini", source_files["GameUserSettings.ini"], gus_var),
            ("Game.ini", source_files["Game.ini"], game_var),
        ):
            if not enabled.get() or not path.exists():
                continue
            document = IniDocument.parse(path.read_bytes())
            names: list[str] = []
            seen: set[str] = set()
            for line in document.lines:
                if line.kind == "section" and line.section:
                    folded = line.section.casefold()
                    if folded not in seen:
                        names.append(line.section)
                        seen.add(folded)
            if not names:
                continue
            ctk.CTkLabel(section_scroll, text=filename, anchor="w", font=ctk.CTkFont(weight="bold")).pack(
                fill="x", padx=6, pady=(4, 0), anchor="w"
            )
            section_vars[filename] = {}
            for name in names:
                variable = tk.BooleanVar(value=previous.get(filename, {}).get(name.casefold(), True))
                section_vars[filename][name] = variable
                ctk.CTkCheckBox(section_scroll, text=name, variable=variable).pack(
                    fill="x", padx=14, pady=1, anchor="w"
                )

    ctk.CTkCheckBox(
        file_frame, text="GameUserSettings.ini", variable=gus_var, command=refresh_sections
    ).pack(side="left", padx=(0, 18))
    ctk.CTkCheckBox(file_frame, text="Game.ini", variable=game_var, command=refresh_sections).pack(side="left")
    refresh_sections()

    button_row = ctk.CTkFrame(dlg, fg_color="transparent")
    button_row.pack(pady=(12, 18))

    def preview_sync() -> None:
        targets = [server for server in other_servers if server_vars[server.id].get()]
        selected = [
            (name, path)
            for name, path, variable in (
                ("GameUserSettings.ini", source_files["GameUserSettings.ini"], gus_var),
                ("Game.ini", source_files["Game.ini"], game_var),
            )
            if variable.get() and path.exists()
        ]
        if not targets or not selected:
            messagebox.showwarning("Seleção incompleta", "Selecione ao menos um servidor e um INI existente.", parent=dlg)
            return

        from ..ini_sync import diff_ini_entries, merge_ini_sections, sync_ini_targets

        plans: list[tuple[str, str, object, bytes, list[str], list[str]]] = []
        errors: list[str] = []
        seen: set[str] = set()
        sections_by_file = {
            filename: {name for name, variable in variables.items() if variable.get()}
            for filename, variables in section_vars.items()
        }
        if any(not sections_by_file.get(filename) for filename, _path in selected):
            messagebox.showwarning("Seleção incompleta", "Marque ao menos uma seção em cada INI escolhido.", parent=dlg)
            return
        for server in targets:
            if not server.install_dir or not os.path.isdir(server.install_dir):
                errors.append(f"{server.name}: diretório indisponível")
                continue
            for filename, source_path in selected:
                destination = get_ini_path(server.install_dir, filename)
                key = os.path.normcase(os.path.abspath(str(destination)))
                if key == os.path.normcase(os.path.abspath(str(source_path))):
                    errors.append(f"{server.name}: destino é o próprio arquivo de origem")
                    continue
                if key in seen:
                    errors.append(f"{server.name}: destino duplicado; confira as pastas cadastradas")
                    continue
                seen.add(key)
                current = destination.read_bytes() if destination.exists() else None
                selected_sections = sections_by_file.get(filename, set())
                content = merge_ini_sections(source_path.read_bytes(), current, selected_sections)
                added, removed = diff_ini_entries(content, current)
                plans.append((server.name, filename, destination, content, added, removed))

        if not plans:
            messagebox.showerror("Sem destinos válidos", "\n".join(errors) or "Nada para sincronizar.", parent=dlg)
            return

        preview = ctk.CTkToplevel(dlg)
        preview.title("Revisar sincronização")
        preview.geometry("850x560")
        preview.minsize(680, 420)
        preview.transient(dlg)
        preview.grab_set()
        ctk.CTkLabel(
            preview,
            text="Confira a alteração por servidor. Os arquivos serão gravados sem comentários ou texto fora da configuração.",
            anchor="w",
            justify="left",
            wraplength=800,
        ).pack(fill="x", padx=16, pady=(16, 8))
        details = ctk.CTkTextbox(preview, wrap="word", font=ctk.CTkFont(family="Consolas", size=11))
        details.pack(fill="both", expand=True, padx=16, pady=8)
        for server_name, filename, destination, _content, added, removed in plans:
            details.insert(
                "end",
                f"{server_name} — {filename}\n  Destino: {destination}\n"
                f"  Adicionadas/alteradas: {len(added)} · removidas/substituídas: {len(removed)}\n",
            )
            preview_added, preview_removed = added[:30], removed[:30]
            if preview_added:
                details.insert("end", "  +\n" + "\n".join(f"    {line}" for line in preview_added) + "\n")
            if preview_removed:
                details.insert("end", "  -\n" + "\n".join(f"    {line}" for line in preview_removed) + "\n")
            if len(added) > len(preview_added) or len(removed) > len(preview_removed):
                details.insert("end", "  ... prévia limitada a 30 entradas por direção\n")
            details.insert("end", "\n")
        if errors:
            details.insert("end", "Ignorados:\n" + "\n".join(f"  • {error}" for error in errors))
        details.configure(state="disabled")

        def apply_sync() -> None:
            files = {destination: content for _server, _name, destination, content, _add, _remove in plans}
            try:
                backups = sync_ini_targets(files)  # type: ignore[arg-type]
            except Exception as exc:
                messagebox.showerror(
                    "Sincronização revertida",
                    f"A gravação falhou. Os arquivos já aplicados foram restaurados.\n\n{exc}",
                    parent=preview,
                )
                return
            preview.destroy()
            dlg.destroy()
            summary = f"{len(files)} arquivo(s) sincronizado(s) em {len({item[0] for item in plans})} servidor(es)."
            if backups:
                summary += "\n\nBackups:\n" + "\n".join(map(str, backups))
            if errors:
                summary += "\n\nAvisos:\n" + "\n".join(errors)
                messagebox.showwarning("Concluído com avisos", summary, parent=app)
            else:
                messagebox.showinfo("Sincronização concluída", summary, parent=app)

        controls = ctk.CTkFrame(preview, fg_color="transparent")
        controls.pack(fill="x", padx=16, pady=(4, 16))
        ctk.CTkButton(
            controls,
            text="Aplicar sincronização",
            width=170,
            fg_color=_GREEN_DARK,
            hover_color=_GREEN_HOVER,
            command=apply_sync,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            controls, text="Voltar", width=100, fg_color=_BLUE, hover_color=_BLUE_HOVER, command=preview.destroy
        ).pack(side="right")

    ctk.CTkButton(
        button_row,
        text="Pré-visualizar",
        width=150,
        height=38,
        fg_color="#6a3aaa",
        hover_color="#7a4abb",
        command=preview_sync,
    ).pack(side="left", padx=(0, 10))
    ctk.CTkButton(
        button_row, text="Cancelar", width=100, height=38, fg_color="#3a3a5a", hover_color="#252540", command=dlg.destroy
    ).pack(side="left")
