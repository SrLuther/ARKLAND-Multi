from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from copy import deepcopy
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import _BLUE, _BLUE_HOVER
import shutil

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def import_ini_from_disk(app: "ARKServerManagerApp", server_id: str) -> None:

    """Abre dialog para escolher a pasta de origem e importa GameUserSettings.ini e Game.ini."""
    srv = app.config_manager.get_server(server_id)
    if not srv:
        return

    # ── Dialog de seleção de origem ───────────────────────────────────────
    dlg = ctk.CTkToplevel(app)
    dlg.title("Importar INI do Disco")
    dlg.geometry("620x280")
    dlg.resizable(False, False)
    dlg.grab_set()
    dlg.grid_columnconfigure(0, weight=1)

    ctk.CTkLabel(
        dlg, text="📂  Importar arquivos INI",
        font=ctk.CTkFont(size=15, weight="bold"),
    ).grid(row=0, column=0, padx=20, pady=(16, 4), sticky="w")

    ctk.CTkLabel(
        dlg,
        text="Selecione a pasta que contém os arquivos INI.\n"
             "Pode ser a pasta do servidor ou um diretório de backup qualquer.\n"
             "Serão procurados: GameUserSettings.ini e Game.ini",
        text_color="gray55", font=ctk.CTkFont(size=11), justify="left",
    ).grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")

    path_fr = ctk.CTkFrame(dlg, fg_color="transparent")
    path_fr.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")
    path_fr.grid_columnconfigure(0, weight=1)

    # Valor padrão: pasta WindowsServer do servidor, se existir
    from ..ark_ini import get_ini_path as _get_ini_path2
    default_dir = str(_get_ini_path2(srv.install_dir, "Game.ini").parent) if srv.install_dir else ""
    path_var = tk.StringVar(value=default_dir)

    path_entry = ctk.CTkEntry(path_fr, textvariable=path_var, height=34,
                              placeholder_text="Caminho da pasta com os arquivos INI")
    path_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

    def _browse():
        folder = filedialog.askdirectory(
            title="Selecionar pasta com arquivos INI",
            initialdir=path_var.get() or os.path.expanduser("~"),
            parent=dlg,
        )
        if folder:
            path_var.set(folder)

    ctk.CTkButton(path_fr, text="📁", width=40, height=34,
                  fg_color="gray30", hover_color="gray40",
                  command=_browse).grid(row=0, column=1)

    btn_fr = ctk.CTkFrame(dlg, fg_color="transparent")
    btn_fr.grid(row=3, column=0, padx=20, pady=(0, 16), sticky="e")

    def _do_import():
        folder = path_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning(
                "Pasta inválida",
                "Selecione uma pasta válida para importar os INIs.",
                parent=dlg,
            )
            return

        from pathlib import Path
        gus_path  = Path(folder) / "GameUserSettings.ini"
        game_path = Path(folder) / "Game.ini"

        if not gus_path.exists() and not game_path.exists():
            messagebox.showwarning(
                "Arquivos não encontrados",
                f"Nenhum arquivo INI (GameUserSettings.ini / Game.ini) encontrado em:\n{folder}",
                parent=dlg,
            )
            return

        try:
            from ..ini_write_safety import find_install_conflicts, load_tek_profiles_read_only
            profiles = list(app.config_manager.servers) + load_tek_profiles_read_only()
            if app.server_manager.is_server_running(server_id):
                raise RuntimeError("Pare o servidor pela interface antes de importar os INIs.")
            conflicts = find_install_conflicts(
                srv.id, srv.install_dir, profiles, target_profile=srv
            )
            if conflicts:
                names = ", ".join(str(getattr(item, "name", getattr(item, "id", "perfil"))) for item in conflicts)
                raise RuntimeError(f"Outro perfil aponta para esta instalação ({names}); resolva o conflito antes de importar.")
            from ..ark_ini import get_ini_path
            replacements = []
            for source in (gus_path, game_path):
                if not source.exists():
                    continue
                target = get_ini_path(srv.install_dir, source.name)
                if target.resolve() != source.resolve() and target.exists():
                    replacements.append(target)
            if replacements and not messagebox.askyesno(
                "Confirmar substituição",
                "A importação substituirá estes arquivos. Será criado backup byte a byte antes de gravar:\n\n"
                + "\n".join(str(path) for path in replacements)
                + "\n\nConfigurações de mods presentes somente no destino também serão substituídas. Continuar?",
                parent=dlg,
            ):
                return
        except Exception as exc:
            messagebox.showerror("Importação bloqueada", str(exc), parent=dlg)
            return

        # Usa ArkIniManager apontando para a pasta escolhida,
        # mas lê diretamente os arquivos lá presentes
        def _load_from_folder(target_srv, src_folder: str) -> None:
            from ..ark_ini import (
                populate_config_from_gus,
                populate_custom_gus_from_file,
                populate_config_from_game_ini,
                populate_custom_game_ini_from_file,
                read_ini_with_fallback,
                find_startup_bat,
                parse_cmdline_args,
                apply_cmdline_args_to_config,
                get_ini_path,
            )
            from ..ini_write_safety import find_install_conflicts, load_tek_profiles_read_only
            profiles = list(app.config_manager.servers) + load_tek_profiles_read_only()
            if app.server_manager.is_server_running(server_id):
                raise RuntimeError("O servidor foi iniciado durante a importação; nenhuma gravação foi feita.")
            conflicts = find_install_conflicts(
                target_srv.id, target_srv.install_dir, profiles, target_profile=srv
            )
            if conflicts:
                raise RuntimeError("Foi detectado perfil concorrente para a instalação; nenhuma gravação foi feita.")
            p_gus = Path(src_folder) / "GameUserSettings.ini"
            if p_gus.exists():
                parser = read_ini_with_fallback(p_gus, strict=False)
                populate_config_from_gus(parser, target_srv)
                populate_custom_gus_from_file(p_gus, target_srv)

            p_game = Path(src_folder) / "Game.ini"
            if p_game.exists():
                parser2 = read_ini_with_fallback(p_game, strict=False)
                populate_config_from_game_ini(parser2, target_srv)
                populate_custom_game_ini_from_file(p_game, target_srv)

            # Complementa com args de linha de comando do .bat de startup,
            # que têm precedência sobre o INI no ARK (ex: breed multipliers)
            bat = find_startup_bat(Path(src_folder))
            if bat:
                try:
                    bat_text = bat.read_text(encoding="utf-8", errors="replace")
                    cmdline_args = parse_cmdline_args(bat_text)
                    apply_cmdline_args_to_config(cmdline_args, target_srv)
                except OSError:
                    pass

            # A importação mantém os bytes do arquivo de origem (encoding,
            # comentários e seções de mods) e troca os dois destinos em lote.
            if target_srv.install_dir:
                dst_gus  = get_ini_path(target_srv.install_dir, "GameUserSettings.ini")
                dst_game = get_ini_path(target_srv.install_dir, "Game.ini")
                sources = {}
                if p_gus.exists() and dst_gus.resolve() != p_gus.resolve():
                    sources[dst_gus] = p_gus
                if p_game.exists() and dst_game.resolve() != p_game.resolve():
                    sources[dst_game] = p_game
                if sources:
                    from ..ini_sync import import_ini_targets

                    def validate_target(destination: Path) -> None:
                        if not Path(target_srv.install_dir).resolve() in destination.resolve().parents:
                            raise RuntimeError("Destino de importação fora da instalação selecionada.")
                        if app.server_manager.is_server_running(server_id):
                            raise RuntimeError("O servidor foi iniciado durante a importação; gravação cancelada.")
                        latest = list(app.config_manager.servers) + load_tek_profiles_read_only()
                        if find_install_conflicts(
                            target_srv.id, target_srv.install_dir, latest, target_profile=srv
                        ):
                            raise RuntimeError("Foi detectado perfil concorrente para a instalação; gravação cancelada.")

                    import_ini_targets(sources, validate_target=validate_target)

        # Desabilita o botão de importar e mostra feedback visual
        import_btn.configure(state="disabled", text="⏳  Importando...")
        btn_cancel.configure(state="disabled")

        import threading

        def _worker():
            imported_srv = deepcopy(srv)
            try:
                _load_from_folder(imported_srv, folder)
                err = None
            except Exception as exc:
                err = exc

            def _on_done():
                if err is not None:
                    import_btn.configure(state="normal", text="⬆️  Importar")
                    btn_cancel.configure(state="normal")
                    messagebox.showerror("Erro ao importar", str(err), parent=dlg)
                    return
                app.config_manager.update_server(imported_srv)
                dlg.destroy()
                app._rebuild_server_panel(server_id)
                found = []
                if gus_path.exists():
                    found.append("GameUserSettings.ini")
                if game_path.exists():
                    found.append("Game.ini")
                messagebox.showinfo(
                    "INI importado",
                    "Configurações importadas com sucesso!\n\nArquivos lidos:\n  " + "\n  ".join(found) + f"\n\nDe: {folder}"
                    "\n\n⚠️  Confira as portas (Servidor, Query e RCON) na aba Geral — "
                    "cada servidor precisa usar portas únicas para evitar conflitos.",
                    parent=app,
                )

            app.after(0, _on_done)

        threading.Thread(target=_worker, daemon=True).start()

    btn_cancel = ctk.CTkButton(
        btn_fr, text="Cancelar", width=100, height=36,
        fg_color="gray30", hover_color="gray40",
        command=dlg.destroy,
    )
    btn_cancel.pack(side="left", padx=(0, 8))
    import_btn = ctk.CTkButton(
        btn_fr, text="⬆️  Importar", width=130, height=36,
        fg_color=_BLUE, hover_color=_BLUE_HOVER,
        command=_do_import,
    )
    import_btn.pack(side="left")

