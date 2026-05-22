from __future__ import annotations
import tkinter as tk
from typing import TYPE_CHECKING
from ..ui_constants import _GREEN, _STATUS_COLOR, _STATUS_LABEL
import datetime
from tkinter import messagebox
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def run_server_install(app: "ARKServerManagerApp", server_id: str, validate: bool = False) -> None:
    """Instala ou valida o servidor ARK via SteamCMD."""
    if not app.mod_manager.is_steamcmd_available():
        messagebox.showwarning(
            "SteamCMD não encontrado",
            "Configure o caminho do SteamCMD nas Configurações Globais antes de instalar.",
            parent=app)
        return

    w = app._server_widgets.get(server_id, {})
    install_dir = w.get("install_dir", tk.StringVar()).get().strip()
    if not install_dir:
        messagebox.showwarning(
            "Diretório não definido",
            "Preencha o 'Diretório de Instalação' na aba Geral e salve antes de instalar.",
            parent=app)
        return

    inst_log: Any = w.get("_inst_log")
    inst_status: Any = w.get("_inst_status")
    inst_btn: Any = w.get("_inst_btn")
    val_btn: Any = w.get("_val_btn")
    _prog_var: Any  = w.get("_install_progress_var")
    _stat_var: Any  = w.get("_status_var")
    _stat_lbl: Any  = w.get("_status_lbl")

    import re as _re
    _PROGRESS_RE = _re.compile(r'progress:\s*([\d.]+)')

    def _set_progress(txt: str) -> None:
        def _do():
            if _prog_var:
                _prog_var.set(txt)
        app.after(0, _do)

    def _set_header_status(txt: str, color: str) -> None:
        def _do():
            if _stat_var:
                _stat_var.set(txt)
            if _stat_lbl:
                _stat_lbl.configure(text_color=color)
        app.after(0, _do)

    def _log(msg: str, level: str = "info") -> None:
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        m = _PROGRESS_RE.search(msg)
        if m:
            pct = float(m.group(1))
            icon = "🔍" if validate else "⬇️"
            _set_progress(f"{icon}  {pct:.1f}%")
        def _do():
            if inst_log:
                inst_log.configure(state="normal")
                inst_log.insert("end", line)
                inst_log.see("end")
                inst_log.configure(state="disabled")
        app.after(0, _do)

    def _set_status(txt: str, color: str = "gray60") -> None:
        def _do():
            if inst_status:
                inst_status.configure(text=txt, text_color=color)
        app.after(0, _do)

    def _set_btns(state: str) -> None:
        def _do():
            if inst_btn:
                inst_btn.configure(state=state)
            if val_btn:
                val_btn.configure(state=state)
        app.after(0, _do)

    def _on_done(ok: bool) -> None:
        if ok:
            _set_status("✅  Instalação concluída com sucesso!", _GREEN)
        else:
            _set_status("❌  Falha na instalação. Veja o log acima.", "#f87171")
        _set_progress("")
        inst_obj = app.server_manager.get_instance(server_id)
        real_st = inst_obj.status if inst_obj else SERVER_STATUS_STOPPED
        _set_header_status(
            _STATUS_LABEL.get(real_st, "PARADO"),
            _STATUS_COLOR.get(real_st, "#ff6666"),
        )
        _set_btns("normal")

    _set_btns("disabled")
    action = "Validando" if validate else "Instalando/Atualizando"
    _set_status(f"⏳  {action}... Aguarde.", "#fbbf24")
    _hdr_txt   = "VALIDANDO" if validate else "ATUALIZANDO"
    _set_header_status(_hdr_txt, "#fbbf24")
    icon = "🔍" if validate else "⬇️"
    _set_progress(f"{icon}  0.0%")

    # Redireciona o log do mod_manager para o log local
    orig_log = app.mod_manager._on_log
    app.mod_manager._on_log = _log
    def _wrapped_done(ok: bool) -> None:
        app.mod_manager._on_log = orig_log
        _on_done(ok)

    srv_cfg = app.config_manager.get_server(server_id)
    _branch = srv_cfg.branch_name if srv_cfg else ""
    _branch_pw = srv_cfg.branch_password if srv_cfg else ""
    app.mod_manager.install_server(
        install_dir, validate=validate, on_done=_wrapped_done,
        branch_name=_branch, branch_password=_branch_pw,
    )

