from __future__ import annotations
import os
from typing import TYPE_CHECKING
from tkinter import messagebox
from ..ark_ini import ArkIniManager, sections_to_ini_text
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def ini_save(app: "ARKServerManagerApp", server_id: str) -> None:
    """Serializa o conteúdo estruturado de volta para mod_ini_configs e custom_ini_sections."""
    # Flush da seção visível em ambos os file_keys
    for fk in ("gus", "game"):
        app._ini_flush_current(server_id, fk)

    srv = app.config_manager.get_server(server_id)
    if not srv:
        return
    w = app._server_widgets.get(server_id, {})

    for file_key in ("gus", "game"):
        data_key = f"_ini_{file_key}_data"
        # A file whose editor has not been loaded is not an empty declaration.
        # Leave its persisted sections alone rather than interpreting absence
        # of widgets as a user request to delete everything.
        if data_key not in w:
            continue
        data = w[data_key]
        ini_key = f"{file_key}_ini"
        mod_buckets: dict = {}     # mod_id → list of section dicts
        custom_secs: list = []

        for sec in data:
            # Lê de StringVars se presentes
            plain_entries = []
            for entry in sec.get("entries", []):
                kv = entry.get("_key_var")
                vv = entry.get("_val_var")
                key = kv.get().strip() if kv else entry.get("key", "").strip()
                val = vv.get().strip() if vv else entry.get("value", "").strip()
                if key:
                    plain_entries.append({"key": key, "value": val})
            plain_sec = {"section": sec["section"], "entries": plain_entries}
            mid = sec.get("mod_id")
            if mid is None:
                custom_secs.append(plain_sec)
            else:
                mod_buckets.setdefault(mid, []).append(plain_sec)

        # A lista visível é a fonte de verdade para este arquivo. Remova do
        # perfil buckets que desapareceram; mantenha o outro INI do mesmo mod.
        for mod_id in list(srv.mod_ini_configs):
            cfg = srv.mod_ini_configs[mod_id]
            if mod_id not in mod_buckets:
                cfg.pop(ini_key, None)
            if not any(str(value or "").strip() for value in cfg.values()):
                srv.mod_ini_configs.pop(mod_id, None)

        # Atualiza mod_ini_configs
        for mod_id, secs in mod_buckets.items():
            cfg = srv.mod_ini_configs.setdefault(mod_id, {})
            cfg[ini_key] = sections_to_ini_text(secs)
            if not any(str(value or "").strip() for value in cfg.values()):
                srv.mod_ini_configs.pop(mod_id, None)

        # Atualiza custom_ini_sections
        srv.custom_ini_sections[file_key] = custom_secs

    app.config_manager.update_server(srv)

    # Aplica nos arquivos .ini se o diretório existir
    applied = False
    apply_error: Exception | None = None
    if srv.install_dir and os.path.isdir(srv.install_dir):
        try:
            combined = dict(srv.mod_ini_configs)
            custom_gus = sections_to_ini_text(srv.custom_ini_sections.get("gus", []))
            custom_game = sections_to_ini_text(srv.custom_ini_sections.get("game", []))
            if custom_gus or custom_game:
                combined["_custom_"] = {"gus_ini": custom_gus, "game_ini": custom_game}
            ArkIniManager(srv.install_dir).apply_mod_ini_configs(combined)
            applied = True
        except Exception as exc:
            apply_error = exc
            app._global_log(f"Erro ao aplicar INI de mods: {exc}", "error")

    msg = "Seções INI salvas com sucesso!"
    if applied:
        msg += "\n\nAplicadas nos arquivos .ini do servidor."
    elif apply_error is not None:
        msg = ("As seções foram salvas no perfil, mas não foi possível aplicá-las "
               f"aos arquivos INI: {apply_error}\n\nCorrija o acesso aos arquivos e tente novamente.")
        messagebox.showwarning("Perfil salvo; INI pendente", msg, parent=app)
        return
    else:
        msg += ("\n\nAs seções serão aplicadas nos arquivos .ini\n"
                "na próxima vez que o servidor for iniciado\n"
                "ou quando você clicar em 'Salvar e Aplicar' no diálogo de mod.")
    messagebox.showinfo("INI Salvo", msg, parent=app)

