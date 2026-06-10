"""Helpers de UI para operações SteamCMD no modo TEK."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig
from ..asm_engine.asm_steamcmd import AsmSteamCmd

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


class SteamCmdLogWindow:
    """Janela de log reutilizável para uma operação SteamCMD."""

    def __init__(self, app: "ARKServerManagerApp", title: str, on_abort: Callable[[], None]) -> None:
        self._app = app
        self._title = title
        self._on_abort = on_abort
        self._win: Optional[ctk.CTkToplevel] = None
        self._box: Optional[ctk.CTkTextbox] = None

    def open(self) -> None:
        if self._win and self._win.winfo_exists():
            self._win.lift()
            return
        win = ctk.CTkToplevel(self._app)
        win.title(self._title)
        win.geometry("720x420")
        win.configure(fg_color="#0d1117")
        self._win = win
        box = ctk.CTkTextbox(
            win, state="disabled",
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0a0a0a", text_color="#86efac",
        )
        box.pack(fill="both", expand=True, padx=8, pady=8)
        self._box = box
        ctk.CTkButton(
            win, text="⏹  Cancelar", width=110, height=28,
            fg_color="#7f1d1d", hover_color="#991b1b",
            command=self._abort,
        ).pack(pady=(0, 8))
        win.protocol("WM_DELETE_WINDOW", self.close)

    def log(self, msg: str) -> None:
        if not self._box:
            return
        try:
            self._box.configure(state="normal")
            self._box.insert("end", msg + "\n")
            self._box.see("end")
            self._box.configure(state="disabled")
        except Exception:
            pass

    def close(self) -> None:
        if self._win and self._win.winfo_exists():
            self._win.destroy()
        self._win = None
        self._box = None

    def _abort(self) -> None:
        self._on_abort()
        self.close()


def _steamcmd_path(app: "ARKServerManagerApp") -> Optional[str]:
    cfg = getattr(getattr(app, "config_manager", None), "config", None)
    return getattr(cfg, "steamcmd_path", None) or None


def _make_client(app: "ARKServerManagerApp", log: SteamCmdLogWindow) -> AsmSteamCmd:
    def _on_log(msg: str) -> None:
        app.after(0, lambda m=msg: log.log(m))

    return AsmSteamCmd(_steamcmd_path(app), on_log=_on_log)


def _run_with_ui(
    app: "ARKServerManagerApp",
    srv: AsmServerConfig,
    action_label: str,
    starter: Callable[[AsmSteamCmd, Callable[[bool, str], None]], None],
) -> bool:
    """Abre log, feedback imediato e executa operação SteamCMD. Retorna False se indisponível."""
    import tkinter.messagebox as mb

    sc = AsmSteamCmd(_steamcmd_path(app))
    if not sc.is_available:
        mb.showwarning(
            "SteamCMD não encontrado",
            "steamcmd.exe não foi localizado.\n"
            "Configure o caminho em Configurações ou instale em C:\\steamcmd\\",
            parent=app,
        )
        return False

    log = SteamCmdLogWindow(app, f"SteamCMD — {srv.name}", on_abort=sc.abort)
    log.open()
    log.log(f"▶ {action_label}")
    log.log("⏳ Iniciando SteamCMD…")
    log.log("   (A auto-atualização do SteamCMD pode levar 1–2 min antes do download aparecer.)")
    log.log("   Uma janela do SteamCMD também será aberta com o progresso detalhado.")
    log.log("")

    client = _make_client(app, log)

    def _done(ok: bool, msg: str) -> None:
        tag = "OK" if ok else "ERRO"
        app.after(0, lambda: log.log(f"[{tag}] {msg}"))

    starter(client, _done)
    return True


def start_server_install(
    app: "ARKServerManagerApp",
    srv: AsmServerConfig,
    *,
    validate: bool = False,
) -> bool:
    def _start(sc: AsmSteamCmd, on_done: Callable[[bool, str], None]) -> None:
        sc.install_server(
            srv.install_dir,
            branch=srv.branch_name,
            branch_password=srv.branch_password,
            validate=validate,
            show_console=True,
            on_done=on_done,
        )

    return _run_with_ui(app, srv, "Instalar / Atualizar servidor", _start)


def start_mods_download(app: "ARKServerManagerApp", srv: AsmServerConfig) -> bool:
    if not srv.active_mods:
        import tkinter.messagebox as mb
        mb.showinfo("Sem mods", "Nenhum mod configurado na lista de Mods.", parent=app)
        return False

    def _start(sc: AsmSteamCmd, on_done: Callable[[bool, str], None]) -> None:
        sc.download_mods(srv.active_mods, srv.install_dir, show_console=True, on_done=on_done)

    return _run_with_ui(app, srv, f"Baixar {len(srv.active_mods)} mod(s)", _start)


def start_server_validate(app: "ARKServerManagerApp", srv: AsmServerConfig) -> bool:
    def _start(sc: AsmSteamCmd, on_done: Callable[[bool, str], None]) -> None:
        sc.validate_server(srv.install_dir, show_console=True, on_done=on_done)

    return _run_with_ui(app, srv, "Validar arquivos do servidor", _start)


def start_mods_redownload(app: "ARKServerManagerApp", srv: AsmServerConfig, mod_ids: List[str]) -> bool:
    if not mod_ids:
        return False

    def _start(sc: AsmSteamCmd, on_done: Callable[[bool, str], None]) -> None:
        sc.download_mods(mod_ids, srv.install_dir, show_console=True, on_done=on_done)

    return _run_with_ui(app, srv, f"Redownload de {len(mod_ids)} mod(s)", _start)


def offer_server_install_after_create(app: "ARKServerManagerApp", server_id: str) -> None:
    """Pergunta se o usuário quer instalar o servidor recém-criado."""
    from tkinter import messagebox

    from ..asm_engine.asm_steamcmd import AsmSteamCmd

    srv = app.asm_config_manager.get_server(server_id)
    if not srv or not (srv.install_dir or "").strip():
        return

    had_server = AsmSteamCmd.install_dir_has_server(srv.install_dir)
    extra = ""
    if had_server:
        bid = AsmSteamCmd.read_installed_build_id(srv.install_dir) or "desconhecido"
        extra = (
            f"\n\n⚠ Esta pasta JÁ contém um servidor ARK (build Steam {bid}).\n"
            "O SteamCMD pode manter a versão antiga se não forçar validate.\n"
            "A instalação inicial usará validate para garantir arquivos atualizados."
        )

    if not messagebox.askyesno(
        "Instalar servidor",
        f"Servidor '{srv.name}' criado.\n\n"
        f"Deseja baixar/atualizar os arquivos do servidor agora?\n\n"
        f"Pasta: {srv.install_dir}{extra}",
        parent=app,
    ):
        return
    # Primeira instalação: validate garante download completo e manifest correto
    start_server_install(app, srv, validate=True)
