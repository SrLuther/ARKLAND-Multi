from __future__ import annotations

import queue
import threading
import uuid
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog
from typing import Callable

import customtkinter as ctk
import paramiko

from ..ssh_access.credential_vault import WindowsCredentialVault
from ..ssh_access.diagnostics import run_local_diagnostics, run_remote_diagnostics
from ..ssh_access.host_keys import HostKeyStore
from ..ssh_access.models import SSHProfile
from ..ssh_access.openssh_config import register_codex_alias, unregister_codex_alias
from ..ssh_access.profile_store import SSHProfileStore
from ..ssh_access.service import ChangedHostKeyError, SSHService, UnknownHostKeyError
from ..ssh_access.terminal_view import TerminalView
from ..ui_constants import get_theme


def _worker(app, work_queue: queue.Queue, label: str, fn: Callable, *args, **kwargs) -> None:
    def run() -> None:
        try:
            work_queue.put((label, fn(*args, **kwargs), None))
        except BaseException as exc:  # noqa: BLE001
            work_queue.put((label, None, exc))
    threading.Thread(target=run, name=f"arkland-ssh-{label}", daemon=True).start()


def _format_results(results) -> str:
    lines = []
    for item in results:
        lines.append(f"[{item.status}] {item.name} — {item.detail}\n    Responsável: {item.owner}")
    return "\n\n".join(lines)


def build_ssh_panel(app, parent) -> None:  # noqa: C901
    theme = get_theme("tek")
    work_queue: queue.Queue = queue.Queue()
    store = SSHProfileStore()
    host_keys = HostKeyStore()
    vault = WindowsCredentialVault()
    service = SSHService(host_keys=host_keys, vault=vault)

    app._ssh_service = service
    app._ssh_profiles = store
    app._ssh_connection = None
    app._ssh_worker_queue = work_queue

    parent.grid_rowconfigure(1, weight=1)
    parent.grid_columnconfigure(0, weight=1)
    header = ctk.CTkFrame(parent, fg_color="transparent")
    header.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 10))
    ctk.CTkLabel(header, text="Acesso SSH", font=ctk.CTkFont(size=22, weight="bold"),
                 text_color=theme["text_primary"]).pack(anchor="w")
    ctk.CTkLabel(
        header,
        text="Conecte-se a uma máquina autorizada. A página Remoto continua usando o protocolo próprio do ARKLAND.",
        font=ctk.CTkFont(size=12), text_color=theme["text_muted"],
    ).pack(anchor="w", pady=(3, 0))

    body = ctk.CTkFrame(parent, fg_color="transparent")
    body.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
    body.grid_columnconfigure(0, weight=0, minsize=310)
    body.grid_columnconfigure(1, weight=1)
    body.grid_rowconfigure(0, weight=1)

    left = ctk.CTkFrame(body, fg_color=theme["panel_bg"], corner_radius=12)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    left.grid_columnconfigure(0, weight=1)
    left.grid_rowconfigure(1, weight=1)
    ctk.CTkLabel(left, text="Perfis de conexão", font=ctk.CTkFont(size=15, weight="bold"),
                 text_color=theme["text_primary"]).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 8))
    profile_list = ctk.CTkScrollableFrame(left, fg_color="transparent", height=170)
    profile_list.grid(row=1, column=0, sticky="nsew", padx=8)
    selected: dict[str, SSHProfile | None] = {"profile": None}
    profile_buttons: list[Any] = []

    details = ctk.CTkLabel(left, text="Selecione ou cadastre uma conexão.", justify="left", wraplength=270,
                           text_color=theme["text_muted"])
    details.grid(row=2, column=0, sticky="ew", padx=14, pady=8)
    actions = ctk.CTkFrame(left, fg_color="transparent")
    actions.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
    actions.grid_columnconfigure((0, 1), weight=1)

    diagnostics_frame = ctk.CTkFrame(left, fg_color=theme["surface_bg"], corner_radius=10)
    diagnostics_frame.grid(row=4, column=0, sticky="ew", padx=10, pady=(0, 12))
    diagnostics_frame.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(diagnostics_frame, text="Diagnóstico SSH", font=ctk.CTkFont(size=14, weight="bold"),
                 text_color=theme["text_primary"]).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))
    local_btn = ctk.CTkButton(diagnostics_frame, text="Verificar ambiente local", height=31)
    local_btn.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
    remote_btn = ctk.CTkButton(diagnostics_frame, text="Testar conexão remota", height=31)
    remote_btn.grid(row=2, column=0, sticky="ew", padx=10, pady=4)
    trust_btn = ctk.CTkButton(diagnostics_frame, text="Revisar e confiar fingerprint…", height=31,
                              fg_color="#8a5a00", hover_color="#704900")
    trust_btn.grid(row=3, column=0, sticky="ew", padx=10, pady=4)
    trust_btn.configure(state="disabled")
    local_note = ctk.CTkLabel(
        diagnostics_frame,
        text="O teste do Codex é separado: o agente pode ter outro PATH, rede ou sandbox.",
        font=ctk.CTkFont(size=10), text_color=theme["text_muted"], wraplength=270, justify="left",
    )
    local_note.grid(row=4, column=0, sticky="w", padx=10, pady=(4, 10))

    right = ctk.CTkFrame(body, fg_color=theme["panel_bg"], corner_radius=12)
    right.grid(row=0, column=1, sticky="nsew")
    right.grid_columnconfigure(0, weight=1)
    right.grid_rowconfigure(2, weight=1)
    connection_bar = ctk.CTkFrame(right, fg_color="transparent")
    connection_bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
    connection_bar.grid_columnconfigure(5, weight=1)
    status_var = ctk.StringVar(value="Desconectado")
    ctk.CTkLabel(connection_bar, textvariable=status_var, text_color=theme["text_muted"]).grid(row=0, column=0, sticky="w", padx=(2, 12))
    test_btn = ctk.CTkButton(connection_bar, text="Testar", width=74, height=30)
    test_btn.grid(row=0, column=1, padx=3)
    connect_btn = ctk.CTkButton(connection_bar, text="Conectar", width=92, height=30)
    connect_btn.grid(row=0, column=2, padx=3)
    disconnect_btn = ctk.CTkButton(connection_bar, text="Desconectar", width=104, height=30,
                                   fg_color="#773c48", hover_color="#61313a")
    disconnect_btn.grid(row=0, column=3, padx=3)
    codex_btn = ctk.CTkButton(connection_bar, text="Habilitar alias para Codex", height=30)
    codex_btn.grid(row=0, column=4, padx=3)

    results_box = ctk.CTkTextbox(right, height=150, wrap="word", font=ctk.CTkFont(size=11),
                                 fg_color=theme["surface_bg"], text_color=theme["text_primary"])
    results_box.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
    results_box.insert("end", "Execute o diagnóstico local ou selecione um perfil para testar a máquina remota.\n")
    results_box.configure(state="disabled")

    terminal_frame = ctk.CTkFrame(right, fg_color="transparent")
    terminal_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(4, 12))
    terminal_frame.grid_rowconfigure(0, weight=1)
    terminal_frame.grid_columnconfigure(0, weight=1)
    terminal = TerminalView(terminal_frame, fg_color=theme["surface_bg"], corner_radius=8,
                            on_resize=lambda w, h: app._ssh_connection.resize(w, h) if app._ssh_connection else None)
    terminal.grid(row=0, column=0, sticky="nsew")
    app._ssh_terminal = terminal

    def show_results(title: str, text: str) -> None:
        results_box.configure(state="normal")
        results_box.delete("1.0", "end")
        results_box.insert("end", f"{title}\n\n{text}\n")
        results_box.configure(state="disabled")

    def add_profile_button(profile: SSHProfile) -> None:
        button = ctk.CTkButton(profile_list, text=f"{profile.name}\n{profile.username}@{profile.host}:{profile.port}",
                               anchor="w", height=52, fg_color="transparent", text_color=theme["text_primary"],
                               hover_color=theme["accent_hover"], command=lambda p=profile: select_profile(p))
        button.pack(fill="x", padx=4, pady=3)
        profile_buttons.append(button)

    def refresh_profiles() -> None:
        for button in profile_buttons:
            button.destroy()
        profile_buttons.clear()
        try:
            profiles = store.load()
        except Exception as exc:  # noqa: BLE001
            show_results("Perfis SSH", f"Falha ao carregar perfis: {exc}")
            return
        for profile in profiles:
            add_profile_button(profile)
        if selected["profile"]:
            current = next((p for p in profiles if p.id == selected["profile"].id), None)
            selected["profile"] = current
            if current:
                select_profile(current)

    def select_profile(profile: SSHProfile) -> None:
        selected["profile"] = profile
        details.configure(text=(
            f"{profile.name}\n{profile.username}@{profile.host}:{profile.port}\n"
            f"Autenticação: {'Chave SSH' if profile.auth_method == 'key' else 'Senha'}\n"
            f"Alias Codex: {profile.alias or 'não configurado'}\n"
            f"Host key: {host_keys.get(profile.host, profile.port) is not None and 'conhecida' or 'a confirmar'}"
        ))
        trust_btn.configure(state="normal")

    def edit_profile(existing: SSHProfile | None = None) -> None:
        dialog = ctk.CTkToplevel(app)
        dialog.title("Perfil SSH" if existing is None else "Editar perfil SSH")
        dialog.geometry("500x570")
        dialog.transient(app)
        dialog.grab_set()
        dialog.grid_columnconfigure(1, weight=1)
        values = {
            "name": ctk.StringVar(value=existing.name if existing else ""),
            "host": ctk.StringVar(value=existing.host if existing else ""),
            "port": ctk.StringVar(value=str(existing.port if existing else 22)),
            "username": ctk.StringVar(value=existing.username if existing else ""),
            "alias": ctk.StringVar(value=existing.alias if existing else ""),
            "auth": ctk.StringVar(value=existing.auth_method if existing else "key"),
            "identity": ctk.StringVar(value=existing.identity_file if existing else ""),
            "server": ctk.StringVar(value=existing.server_id if existing else ""),
            "secret": ctk.StringVar(value=""),
            "save_secret": ctk.BooleanVar(value=False),
        }
        fields = [("Nome", "name"), ("Hostname ou IP", "host"), ("Porta", "port"),
                  ("Usuário", "username"), ("Alias para Codex", "alias")]
        for row, (label, key) in enumerate(fields):
            ctk.CTkLabel(dialog, text=label).grid(row=row, column=0, sticky="w", padx=16, pady=7)
            ctk.CTkEntry(dialog, textvariable=values[key]).grid(row=row, column=1, sticky="ew", padx=16, pady=7)
        row = len(fields)
        ctk.CTkLabel(dialog, text="Autenticação").grid(row=row, column=0, sticky="w", padx=16, pady=7)
        auth_menu = ctk.CTkOptionMenu(dialog, variable=values["auth"], values=["key", "password"])
        auth_menu.grid(row=row, column=1, sticky="w", padx=16, pady=7)
        row += 1
        identity_row = ctk.CTkFrame(dialog, fg_color="transparent")
        identity_row.grid(row=row, column=0, columnspan=2, sticky="ew", padx=16, pady=5)
        identity_row.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(identity_row, textvariable=values["identity"], placeholder_text="Caminho da chave privada").grid(row=0, column=0, sticky="ew", padx=(0, 6))
        def browse_key() -> None:
            path = filedialog.askopenfilename(parent=dialog, title="Selecionar chave SSH", filetypes=[("Chaves privadas", "*"), ("Todos os arquivos", "*.*")])
            if path:
                values["identity"].set(path)
        ctk.CTkButton(identity_row, text="Procurar…", width=88, command=browse_key).grid(row=0, column=1)
        row += 1
        ctk.CTkLabel(dialog, text="Senha / frase secreta (opcional)").grid(row=row, column=0, sticky="w", padx=16, pady=7)
        ctk.CTkEntry(dialog, textvariable=values["secret"], show="*").grid(row=row, column=1, sticky="ew", padx=16, pady=7)
        row += 1
        ctk.CTkCheckBox(dialog, text="Salvar no Gerenciador de Credenciais do Windows", variable=values["save_secret"]).grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=5)
        row += 1
        servers = list(getattr(getattr(app, "asm_config_manager", None), "servers", []) or [])
        server_map = {"(sem associação)": ""}
        server_map.update({f"{srv.name} ({srv.id[:8]})": srv.id for srv in servers})
        display_by_id = {value: label for label, value in server_map.items()}
        ctk.CTkLabel(dialog, text="Servidor TEK associado").grid(row=row, column=0, sticky="w", padx=16, pady=7)
        server_menu = ctk.CTkOptionMenu(dialog, values=list(server_map), command=lambda label: values["server"].set(server_map[label]))
        server_menu.set(display_by_id.get(values["server"].get(), "(sem associação)"))
        server_menu.grid(row=row, column=1, sticky="w", padx=16, pady=7)
        row += 1
        ctk.CTkLabel(dialog, text="Codex usa o OpenSSH e a identidade do usuário do Windows. Senhas não são exportadas.",
                     wraplength=450, justify="left", text_color=theme["text_muted"]).grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=8)
        row += 1

        def save_profile() -> None:
            try:
                profile = SSHProfile(
                    id=existing.id if existing else str(uuid.uuid4()),
                    name=values["name"].get().strip(), host=values["host"].get().strip(),
                    username=values["username"].get().strip(), port=int(values["port"].get()),
                    alias=values["alias"].get().strip(), auth_method=values["auth"].get(),
                    identity_file=values["identity"].get().strip(), server_id=values["server"].get(),
                )
                profile.validate()
                profiles = store.load()
                if any(p.alias.casefold() == profile.alias.casefold() and p.id != profile.id for p in profiles if profile.alias):
                    raise ValueError("Esse alias já está associado a outro perfil SSH do ARKLAND.")
                profiles = [p for p in profiles if p.id != profile.id]
                profiles.append(profile)
                store.save(profiles)
                secret = values["secret"].get()
                if secret and values["save_secret"].get():
                    vault.set_secret(profile.id, "password" if profile.auth_method == "password" else "key-passphrase", secret)
                selected["profile"] = profile
                refresh_profiles()
                select_profile(profile)
                dialog.destroy()
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Perfil SSH", str(exc), parent=dialog)

        button_row = ctk.CTkFrame(dialog, fg_color="transparent")
        button_row.grid(row=row, column=0, columnspan=2, sticky="e", padx=16, pady=14)
        ctk.CTkButton(button_row, text="Cancelar", fg_color="transparent", command=dialog.destroy).pack(side="left", padx=5)
        ctk.CTkButton(button_row, text="Salvar perfil", command=save_profile).pack(side="left", padx=5)

    def get_ephemeral_secret(profile: SSHProfile) -> tuple[str | None, str | None]:
        purpose = "password" if profile.auth_method == "password" else "key-passphrase"
        saved = vault.get_secret(profile.id, purpose)
        if saved:
            return (saved if profile.auth_method == "password" else None,
                    saved if profile.auth_method == "key" else None)
        prompt = "Senha SSH" if profile.auth_method == "password" else "Frase secreta da chave (deixe vazio se a chave não tiver frase secreta)"
        secret = simpledialog.askstring("Credencial SSH", prompt, show="*", parent=app)
        if secret is None:
            raise PermissionError("Operação cancelada pelo usuário.")
        if secret and messagebox.askyesno("Credencial SSH", "Salvar esta credencial no Gerenciador de Credenciais do Windows?", parent=app):
            vault.set_secret(profile.id, purpose, secret)
        return (secret if profile.auth_method == "password" else None,
                secret if profile.auth_method == "key" else None)

    def trust_selected_host() -> None:
        profile = selected["profile"]
        if profile is None:
            messagebox.showinfo("SSH", "Selecione um perfil primeiro.", parent=app)
            return
        trust_btn.configure(state="disabled")
        status_var.set("Consultando identidade…")
        def done(label, result, error):
            if label != "host-inspection":
                return
            if error:
                status_var.set("Falha ao consultar o host")
                show_results("Identidade SSH", str(error))
                trust_btn.configure(state="normal")
                return
            inspection = result
            if inspection.trusted:
                status_var.set("Identidade já confiável")
                show_results("Identidade SSH", f"Fingerprint já registrada:\n{inspection.fingerprint}")
                trust_btn.configure(state="normal")
                return
            accepted = messagebox.askyesno(
                "Confiar neste servidor SSH?",
                f"Fingerprint apresentada pelo host:\n\n{inspection.fingerprint}\n\nCompare com um canal independente (por exemplo, console/administrador do servidor). Confiar somente se corresponder.",
                parent=app,
            )
            if not accepted:
                status_var.set("Host não confiado")
                trust_btn.configure(state="normal")
                return
            try:
                service.trust_host(profile, inspection.key)
                status_var.set("Fingerprint registrada")
                show_results("Identidade SSH", f"Fingerprint confiada:\n{inspection.fingerprint}\n\nA autenticação agora pode ser testada.")
                select_profile(profile)
            except Exception as exc:  # noqa: BLE001
                status_var.set("Não foi possível confiar no host")
                show_results("Identidade SSH", str(exc))
            trust_btn.configure(state="normal")
        _worker(app, work_queue, "host-inspection", service.inspect_host, profile)

    def test_remote() -> None:
        profile = selected["profile"]
        if profile is None:
            messagebox.showinfo("SSH", "Selecione um perfil primeiro.", parent=app)
            return
        try:
            password, key_passphrase = get_ephemeral_secret(profile)
        except Exception as exc:  # noqa: BLE001
            show_results("Diagnóstico remoto", str(exc))
            return
        remote_btn.configure(state="disabled")
        test_btn.configure(state="disabled")
        status_var.set("Testando DNS, porta, identidade e autenticação…")
        def perform():
            return run_remote_diagnostics(profile, service, password=password, key_passphrase=key_passphrase)
        _worker(app, work_queue, "remote-diagnostic", perform)

    def test_connection() -> None:
        test_remote()

    def connect_shell() -> None:
        profile = selected["profile"]
        if profile is None:
            messagebox.showinfo("SSH", "Selecione um perfil primeiro.", parent=app)
            return
        try:
            password, key_passphrase = get_ephemeral_secret(profile)
        except Exception as exc:  # noqa: BLE001
            show_results("Conexão SSH", str(exc))
            return
        connect_btn.configure(state="disabled")
        status_var.set("Verificando identidade do servidor…")
        def inspect_then_connect():
            inspection = service.inspect_host(profile)
            return inspection, password, key_passphrase
        def finish_connect(payload):
            inspection, pass_value, phrase_value = payload
            if not inspection.trusted:
                accepted = messagebox.askyesno(
                    "Confiar neste servidor SSH?",
                    f"Fingerprint apresentada:\n\n{inspection.fingerprint}\n\nCompare-a por um canal independente antes de confiar.",
                    parent=app,
                )
                if not accepted:
                    status_var.set("Host não confiado")
                    connect_btn.configure(state="normal")
                    return
                try:
                    service.trust_host(profile, inspection.key)
                except Exception as exc:  # noqa: BLE001
                    show_results("Conexão SSH", str(exc))
                    connect_btn.configure(state="normal")
                    return
            status_var.set("Autenticando e abrindo terminal…")
            def open_shell():
                return service.open_shell(profile, password=pass_value, key_passphrase=phrase_value)
            _worker(app, work_queue, "ssh-shell", open_shell)

        # Keep modal dialogs and all Tk operations on the UI thread.
        def on_inspected(_label, result, error):
            if error:
                show_results("Conexão SSH", str(error))
                status_var.set("Conexão não iniciada")
                connect_btn.configure(state="normal")
            else:
                finish_connect(result)
        _worker(app, work_queue, "shell-inspection", inspect_then_connect)
        app._ssh_pending_inspection_callback = on_inspected

    def disconnect() -> None:
        terminal.disconnect()
        app._ssh_connection = None
        status_var.set("Desconectado")

    def configure_codex_alias() -> None:
        profile = selected["profile"]
        if profile is None:
            messagebox.showinfo("SSH / Codex", "Selecione um perfil primeiro.", parent=app)
            return
        if profile.auth_method != "key":
            messagebox.showwarning("SSH / Codex", "O alias para o Codex requer autenticação por chave SSH. Senhas não serão exportadas.", parent=app)
            return
        if not profile.alias:
            profile.alias = simpledialog.askstring("Alias SSH", "Nome curto para usar no terminal do Codex (ex.: arkland-producao):", parent=app) or ""
            try:
                profile.validate()
                profiles = store.load()
                profiles = [p for p in profiles if p.id != profile.id] + [profile]
                store.save(profiles)
                refresh_profiles()
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Alias SSH", str(exc), parent=app)
                return
        accepted = messagebox.askyesno(
            "Configurar alias SSH para Codex",
            "O ARKLAND adicionará um bloco marcado ao arquivo ~/.ssh/config e criará um backup antes da alteração.\n\n"
            "O bloco será validado por ssh -G. Nenhuma senha será copiada. A configuração só estará disponível para o Codex se ele executar como este mesmo usuário do Windows e tiver acesso à rede/chave.\n\nContinuar?",
            parent=app,
        )
        if not accepted:
            return
        try:
            path = register_codex_alias(profile)
            show_results("Integração Codex", f"Alias '{profile.alias}' configurado e validado.\nArquivo gerenciado: {path}\n\nTeste no terminal do agente Codex com:\nssh {profile.alias}")
            status_var.set("Alias Codex configurado")
            select_profile(profile)
        except Exception as exc:  # noqa: BLE001
            show_results("Integração Codex", str(exc))
            status_var.set("Falha ao configurar alias")

    def delete_profile() -> None:
        profile = selected["profile"]
        if profile is None:
            return
        if not messagebox.askyesno("Excluir perfil SSH", f"Excluir o perfil '{profile.name}' e as credenciais associadas no Windows? A chave privada externa não será apagada.", parent=app):
            return
        try:
            unregister_codex_alias(profile)
        except OSError as exc:
            messagebox.showerror("Excluir perfil SSH", f"Não foi possível arquivar/remover o alias gerenciado. O perfil foi mantido.\n\n{exc}", parent=app)
            return
        profiles = [p for p in store.load() if p.id != profile.id]
        store.save(profiles)
        vault.delete_profile_secrets(profile.id)
        selected["profile"] = None
        details.configure(text="Selecione ou cadastre uma conexão.")
        refresh_profiles()

    ctk.CTkButton(actions, text="Adicionar", command=lambda: edit_profile()).grid(row=0, column=0, sticky="ew", padx=3, pady=3)
    ctk.CTkButton(actions, text="Editar", command=lambda: edit_profile(selected["profile"]) if selected["profile"] else None).grid(row=0, column=1, sticky="ew", padx=3, pady=3)
    ctk.CTkButton(actions, text="Excluir", command=delete_profile, fg_color="#773c48", hover_color="#61313a").grid(row=1, column=0, columnspan=2, sticky="ew", padx=3, pady=3)

    def on_local_diagnostics():
        local_btn.configure(state="disabled")
        show_results("Diagnóstico local", "Verificando ambiente do ARKLAND…")
        _worker(app, work_queue, "local-diagnostic", run_local_diagnostics)

    local_btn.configure(command=on_local_diagnostics)
    remote_btn.configure(command=test_remote)
    trust_btn.configure(command=trust_selected_host)
    test_btn.configure(command=test_connection)
    connect_btn.configure(command=connect_shell)
    disconnect_btn.configure(command=disconnect)
    codex_btn.configure(command=configure_codex_alias)

    def process_results() -> None:
        try:
            while True:
                label, result, error = work_queue.get_nowait()
                if label == "local-diagnostic":
                    local_btn.configure(state="normal")
                    show_results("Diagnóstico local", _format_results(result) if not error else str(error))
                    status_var.set("Diagnóstico local concluído")
                elif label == "remote-diagnostic":
                    remote_btn.configure(state="normal")
                    test_btn.configure(state="normal")
                    show_results("Diagnóstico da conexão remota", _format_results(result) if not error else str(error))
                    status_var.set("Diagnóstico remoto concluído" if not error else "Falha no diagnóstico")
                elif label == "host-inspection":
                    trust_btn.configure(state="normal")
                    if error:
                        status_var.set("Falha ao consultar identidade")
                        show_results("Identidade SSH", str(error))
                    elif result.trusted:
                        status_var.set("Identidade já confiável")
                        show_results("Identidade SSH", f"Fingerprint: {result.fingerprint}\nJá confiável.")
                    else:
                        accepted = messagebox.askyesno("Confiar fingerprint?", f"Fingerprint: {result.fingerprint}\n\nCompare por um canal independente antes de aceitar.", parent=app)
                        if accepted:
                            service.trust_host(selected["profile"], result.key)
                            show_results("Identidade SSH", "Fingerprint registrada. Execute novamente o teste remoto para autenticar.")
                            select_profile(selected["profile"])
                        else:
                            show_results("Identidade SSH", "Host permanece não confiável; autenticação bloqueada.")
                elif label == "shell-inspection":
                    connect_btn.configure(state="normal")
                    if error:
                        status_var.set("Conexão não iniciada")
                        show_results("Conexão SSH", str(error))
                        continue
                    inspection, password, phrase = result
                    if not inspection.trusted:
                        accepted = messagebox.askyesno("Confiar neste servidor SSH?", f"Fingerprint:\n{inspection.fingerprint}\n\nCompare por um canal independente antes de confiar.", parent=app)
                        if not accepted:
                            status_var.set("Host não confiado")
                            continue
                        try:
                            service.trust_host(selected["profile"], inspection.key)
                        except Exception as exc:  # noqa: BLE001
                            show_results("Identidade SSH", str(exc))
                            continue
                    connect_btn.configure(state="disabled")
                    status_var.set("Abrindo sessão SSH…")
                    _worker(app, work_queue, "ssh-shell", lambda: service.open_shell(selected["profile"], password=password, key_passphrase=phrase))
                elif label == "ssh-shell":
                    connect_btn.configure(state="normal")
                    if error:
                        status_var.set("Falha na autenticação/sessão")
                        show_results("Sessão SSH", f"Não foi possível abrir o terminal: {error}")
                    else:
                        app._ssh_connection = result
                        terminal.attach(result)
                        status_var.set(f"Conectado: {selected['profile'].host}")
                        show_results("Sessão SSH", f"Conectado como {selected['profile'].username}@{selected['profile'].host}:{selected['profile'].port}. A sessão é interativa; comandos são enviados somente após digitação.")
        except queue.Empty:
            pass
        if parent.winfo_exists():
            parent.after(80, process_results)

    refresh_profiles()
    process_results()

