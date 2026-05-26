from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING

import customtkinter as ctk  # type: ignore[reportMissingImports]

import uuid
from ..remote_agent import local_ip, parse_identity_code, RemoteClient
from ..ui_constants import (
    _GREEN, _GREEN_DARK, _GREEN_HOVER, _RED_DARK, _RED_HOVER, _CARD_BG,
    _hostname,
)

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def build_remote_panel(app: "ARKServerManagerApp", parent) -> None:  # noqa: C901
    parent.grid_columnconfigure(0, weight=1)
    cfg = app.config_manager.config

    ctk.CTkLabel(parent, text="🖥️  Acesso Remoto",
                 font=ctk.CTkFont(size=24, weight="bold")).grid(
        row=0, column=0, padx=24, pady=(24, 2), sticky="w")
    ctk.CTkLabel(
        parent,
        text="Controle qualquer instância ARKLAND remotamente pela internet.",
        text_color="gray60",
    ).grid(row=1, column=0, padx=24, pady=(0, 18), sticky="w")

    # ── Seção: Este Agente ────────────────────────────────────────────────
    app._section_lbl(parent, 2, "📡  Este Agente")
    agent_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    agent_card.grid(row=3, column=0, padx=20, pady=(0, 14), sticky="ew")
    agent_card.grid_columnconfigure(1, weight=1)

    # Status
    app._remote_status_var = tk.StringVar(value="● Agente parado")
    status_lbl = ctk.CTkLabel(
        agent_card, textvariable=app._remote_status_var,
        font=ctk.CTkFont(size=12, weight="bold"), text_color="#ff6666",
    )
    status_lbl.grid(row=0, column=0, columnspan=3, padx=16, pady=(14, 4), sticky="w")
    app._remote_status_lbl = status_lbl

    def _update_agent_status_lbl() -> None:
        if app._remote_agent and app._remote_agent.is_running:
            app._remote_status_var.set(
                f"● Agente ativo — porta {app.config_manager.config.remote_agent_port}")
            app._remote_status_lbl.configure(text_color=_GREEN)
            app._remote_toggle_btn.configure(
                text="⏹  Parar Agente", fg_color=_RED_DARK, hover_color=_RED_HOVER)
        else:
            app._remote_status_var.set("● Agente parado")
            app._remote_status_lbl.configure(text_color="#ff6666")
            app._remote_toggle_btn.configure(
                text="▶  Ativar Agente", fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER)
        app._refresh_identity_code()

    # Nome da instância
    ctk.CTkLabel(agent_card, text="Nome desta máquina:", width=190, anchor="w",
                 text_color="gray60").grid(row=1, column=0, padx=16, pady=(8, 4), sticky="w")
    app._remote_name_var = tk.StringVar(value=cfg.remote_agent_name or _hostname())
    ctk.CTkEntry(agent_card, textvariable=app._remote_name_var, height=32,
                 placeholder_text="Ex: Servidor Principal").grid(
        row=1, column=1, padx=(0, 16), pady=(8, 4), sticky="ew")

    # Porta
    ctk.CTkLabel(agent_card, text="Porta do agente:", width=190, anchor="w",
                 text_color="gray60").grid(row=2, column=0, padx=16, pady=4, sticky="w")
    app._remote_port_var = tk.StringVar(value=str(cfg.remote_agent_port))
    ctk.CTkEntry(agent_card, textvariable=app._remote_port_var, height=32,
                 width=110).grid(row=2, column=1, padx=(0, 16), pady=4, sticky="w")
    ctk.CTkLabel(agent_card,
                 text="Libere esta porta no firewall/roteador para acesso externo.",
                 text_color="gray45", font=ctk.CTkFont(size=10)).grid(
        row=3, column=0, columnspan=2, padx=16, pady=(0, 6), sticky="w")

    # Código de identidade
    ctk.CTkLabel(agent_card, text="Código de identidade:", width=190, anchor="w",
                 text_color="gray60").grid(row=4, column=0, padx=16, pady=(8, 0), sticky="w")
    code_fr = ctk.CTkFrame(agent_card, fg_color="transparent")
    code_fr.grid(row=4, column=1, padx=(0, 16), pady=(8, 0), sticky="ew")
    code_fr.grid_columnconfigure(0, weight=1)
    app._remote_code_var = tk.StringVar(value="—")
    ctk.CTkEntry(code_fr, textvariable=app._remote_code_var, height=32,
                 state="readonly", font=ctk.CTkFont(family="Consolas", size=10)).grid(
        row=0, column=0, sticky="ew", padx=(0, 6))

    def _copy_code() -> None:
        code = app._remote_code_var.get()
        if code and code != "—":
            app.clipboard_clear()
            app.clipboard_append(code)
            app._toast("Código copiado para a área de transferência!")

    ctk.CTkButton(code_fr, text="📋", width=34, height=32,
                  command=_copy_code).grid(row=0, column=1)
    ctk.CTkLabel(agent_card,
                 text="Compartilhe este código com quem vai gerenciar esta máquina remotamente.",
                 text_color="gray45", font=ctk.CTkFont(size=10)).grid(
        row=5, column=0, columnspan=2, padx=16, pady=(2, 4), sticky="w")

    app._remote_ip_var = tk.StringVar(value=f"IP local detectado: {local_ip()}")
    ctk.CTkLabel(agent_card, textvariable=app._remote_ip_var,
                 text_color="gray50", font=ctk.CTkFont(size=10)).grid(
        row=6, column=0, columnspan=2, padx=16, pady=(0, 6), sticky="w")

    # Botões de controle
    btn_row = ctk.CTkFrame(agent_card, fg_color="transparent")
    btn_row.grid(row=7, column=0, columnspan=2, padx=12, pady=(4, 16), sticky="w")

    def _toggle_agent() -> None:
        _save_agent_cfg()
        if app._remote_agent and app._remote_agent.is_running:
            app._remote_agent.stop()
            app._remote_agent = None
        else:
            app._start_remote_agent()
        _update_agent_status_lbl()

    app._remote_toggle_btn = ctk.CTkButton(
        btn_row, text="▶  Ativar Agente", height=34,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=_toggle_agent,
    )
    app._remote_toggle_btn.pack(side="left", padx=(0, 8))

    def _test_agent() -> None:
        """Testa alcance do agente em 127.0.0.1 E no IP LAN local."""
        if not (app._remote_agent and app._remote_agent.is_running):
            messagebox.showinfo("Testar Agente", "O agente não está ativo.", parent=app)
            return
        port = app.config_manager.config.remote_agent_port

        def _do() -> None:
            lo_ok  = RemoteClient("127.0.0.1", port, token="", timeout=3.0).ping()
            lan_ip = local_ip()
            lan_ok = RemoteClient(lan_ip,      port, token="", timeout=3.0).ping()

            if lo_ok and lan_ok:
                msg = (
                    f"✅  Agente acessível em 127.0.0.1 e {lan_ip}.\n\n"
                    "Se outra máquina ainda não conseguir conectar, o problema\n"
                    "é no roteador/firewall externo ou na rede entre as máquinas."
                )
                app.after(0, lambda: messagebox.showinfo("Testar Agente", msg, parent=app))

            elif lo_ok and not lan_ok:
                msg = (
                    f"⚠️  Agente responde em 127.0.0.1 mas NÃO em {lan_ip}:{port}.\n\n"
                    "Causa provável: Windows Defender Firewall bloqueando a porta\n"
                    "no perfil de rede (Privado/Público).\n\n"
                    "Solução rápida: clique em '🔒 Firewall' para criar a regra\n"
                    "automaticamente (requer confirmação UAC)."
                )
                app.after(0, lambda: messagebox.showwarning("Testar Agente", msg, parent=app))

            else:
                msg = (
                    f"❌  Agente não respondeu nem em 127.0.0.1:{port}.\n\n"
                    "Verifique se o agente está realmente ativo."
                )
                app.after(0, lambda: messagebox.showerror("Testar Agente", msg, parent=app))
        threading.Thread(target=_do, daemon=True).start()

    ctk.CTkButton(
        btn_row, text="🔍  Testar", height=34,
        fg_color="#2a3050", hover_color="#3a4060",
        command=_test_agent,
    ).pack(side="left", padx=(0, 8))

    def _fix_firewall() -> None:
        """Cria regra no Windows Firewall via UAC (sem precisar de admin prévio)."""
        port = app.config_manager.config.remote_agent_port
        if not messagebox.askyesno(
            "Criar Regra no Firewall",
            f"Isso vai criar uma regra de entrada no Windows Defender Firewall\n"
            f"para liberar TCP porta {port} em todos os perfis de rede\n"
            f"(Domínio, Privado e Público).\n\n"
            f"Uma janela de UAC (controle de conta) será exibida pedindo permissão.\n\n"
            "Continuar?",
            parent=app,
        ):
            return
        import ctypes, subprocess, sys
        rule_name = f"ARKLAND Remote Agent {port}"
        # Remove regra antiga se existir, depois cria nova com Profile=Any
        ps_cmd = (
            f"netsh advfirewall firewall delete rule name=\"{rule_name}\" 2>nul & "
            f"netsh advfirewall firewall add rule name=\"{rule_name}\" "
            f"protocol=TCP dir=in localport={port} action=allow profile=any && "
            f"echo SUCESSO"
        )
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", "cmd.exe",
            f'/c {ps_cmd} & pause',
            None, 1,
        )
        if ret > 32:
            app.after(3500, lambda: messagebox.showinfo(
                "Regra criada",
                f"✅  Regra '{rule_name}' aplicada.\n\n"
                f"Clique em '🔍 Testar' para verificar se a conexão LAN funciona agora.",
                parent=app,
            ))
        else:
            messagebox.showerror(
                "Erro",
                "Não foi possível abrir o prompt elevado. "
                "Execute o ARKLAND como Administrador e tente novamente.",
                parent=app,
            )

    ctk.CTkButton(
        btn_row, text="🔒  Firewall", height=34,
        fg_color="#3a2a10", hover_color="#5a3a18",
        command=_fix_firewall,
    ).pack(side="left", padx=(0, 8))

    def _regen_token() -> None:
        if messagebox.askyesno(
            "Regenerar Token",
            "Regenerar o token invalidará todos os códigos de identidade existentes.\n"
            "Qualquer app remoto conectado precisará de um novo código.\n\nContinuar?",
            parent=app,
        ):
            app.config_manager.config.remote_agent_token = str(uuid.uuid4())
            app.config_manager.save()
            if app._remote_agent and app._remote_agent.is_running:
                app._remote_agent.stop()
                app._remote_agent = None
                app._start_remote_agent()
            _update_agent_status_lbl()

    ctk.CTkButton(
        btn_row, text="🔑  Regenerar Token", height=34,
        fg_color="#3a3a50", hover_color="#4a4a60",
        command=_regen_token,
    ).pack(side="left")

    def _save_agent_cfg() -> None:
        cfg = app.config_manager.config
        cfg.remote_agent_name = app._remote_name_var.get().strip() or _hostname()
        try:
            cfg.remote_agent_port = int(app._remote_port_var.get())
        except ValueError:
            pass
        app.config_manager.save()

    ctk.CTkButton(
        btn_row, text="💾  Salvar", height=34,
        fg_color="#2a3a2a", hover_color="#3a4a3a",
        command=lambda: (_save_agent_cfg(), app._refresh_identity_code(),
                         app._toast("Configurações do agente salvas!")),
    ).pack(side="left", padx=(8, 0))

    # Inicializa label de status imediatamente
    _update_agent_status_lbl()

    # ── Seção: Descoberta na Rede Local (LAN) ─────────────────────────────
    app._section_lbl(parent, 4, "📡  Descoberta na Rede (LAN)")

    lan_card = ctk.CTkFrame(parent, corner_radius=12, fg_color=_CARD_BG)
    lan_card.grid(row=5, column=0, padx=20, pady=(0, 14), sticky="ew")
    lan_card.grid_columnconfigure(0, weight=1)

    lan_header = ctk.CTkFrame(lan_card, fg_color="transparent")
    lan_header.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
    lan_header.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(
        lan_header,
        text="Instâncias ARKLAND detectadas automaticamente na mesma rede.",
        text_color="gray50", font=ctk.CTkFont(size=11),
    ).grid(row=0, column=0, sticky="w")

    def _refresh_lan() -> None:
        """Atualiza a lista de instâncias LAN descobertas via UDP."""
        for w in app._lan_peers_frame.winfo_children():
            w.destroy()

        disc = getattr(app, "_udp_discovery", None)
        peers = disc.peers if disc else []

        if not peers:
            ctk.CTkLabel(
                app._lan_peers_frame,
                text="Nenhuma instância detectada. Certifique-se de que o agente"
                     " remoto está ativo em ambas as máquinas.",
                text_color="gray45", font=ctk.CTkFont(size=11),
            ).pack(anchor="w", padx=8, pady=6)
        else:
            for peer in peers:
                row_f = ctk.CTkFrame(app._lan_peers_frame,
                                     fg_color="#1a1a2e", corner_radius=8)
                row_f.pack(fill="x", pady=3, padx=4)
                row_f.grid_columnconfigure(1, weight=1)

                ctk.CTkLabel(
                    row_f,
                    text=f"🖥  {peer['name']}",
                    font=ctk.CTkFont(size=12, weight="bold"),
                ).grid(row=0, column=0, padx=(10, 6), pady=(6, 2), sticky="w")
                ctk.CTkLabel(
                    row_f,
                    text=f"{peer['host']}:{peer['port']}",
                    text_color="gray50", font=ctk.CTkFont(size=11),
                ).grid(row=1, column=0, padx=(10, 6), pady=(0, 6), sticky="w")

                def _connect(p=peer) -> None:
                    _open_connect_dialog(p)

                # Verifica se já está salvo
                already = any(
                    i.get("host") == peer["host"] and i.get("port") == peer["port"]
                    for i in (app.config_manager.config.remote_instances or [])
                )
                if already:
                    ctk.CTkLabel(
                        row_f, text="✔ Salvo", text_color="#66bb66",
                        font=ctk.CTkFont(size=11),
                    ).grid(row=0, column=2, rowspan=2, padx=(0, 12), pady=6)
                else:
                    ctk.CTkButton(
                        row_f, text="Conectar", height=28, width=90,
                        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                        command=_connect,
                    ).grid(row=0, column=2, rowspan=2, padx=(0, 10), pady=6)

    def _open_connect_dialog(peer: dict) -> None:
        """Abre diálogo pedindo apenas o token para conectar à instância descoberta."""
        dlg = ctk.CTkToplevel(app)
        dlg.title("Conectar à Instância LAN")
        dlg.geometry("440x200")
        dlg.grab_set()
        dlg.resizable(False, False)

        ctk.CTkLabel(
            dlg,
            text=f"Conectar a  {peer['name']}  ({peer['host']}:{peer['port']})",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(padx=20, pady=(16, 4), anchor="w")
        ctk.CTkLabel(
            dlg,
            text="Cole o token do agente remoto (aba Acesso Remoto na outra máquina):",
            text_color="gray60", font=ctk.CTkFont(size=11),
        ).pack(padx=20, anchor="w")

        token_var = tk.StringVar()
        ctk.CTkEntry(dlg, textvariable=token_var, height=32, width=400,
                     font=ctk.CTkFont(family="Consolas", size=11),
                     placeholder_text="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx").pack(
            padx=20, pady=(6, 0))

        err_var = tk.StringVar()
        ctk.CTkLabel(dlg, textvariable=err_var, text_color="#ff6666",
                     font=ctk.CTkFont(size=11)).pack(padx=20, pady=(2, 0), anchor="w")

        def _confirm() -> None:
            token = token_var.get().strip()
            if not token:
                err_var.set("O token não pode ser vazio.")
                return
            inst = {
                "name":     peer["name"],
                "host":     peer["host"],
                "port":     peer["port"],
                "token":    token,
                "favorite": False,
            }
            app.config_manager.config.remote_instances.append(inst)
            app.config_manager.save()
            dlg.destroy()
            _refresh_lan()
            app._refresh_remote_instances_list()

        ctk.CTkButton(dlg, text="✔  Conectar", height=34,
                      fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                      command=_confirm).pack(pady=12)

    btn_lan = ctk.CTkFrame(lan_header, fg_color="transparent")
    btn_lan.grid(row=0, column=1, sticky="e")
    ctk.CTkButton(
        btn_lan, text="🔄  Atualizar", height=28, width=110,
        fg_color="#2a2a40", hover_color="#363656",
        command=_refresh_lan,
    ).pack()

    app._lan_peers_frame = ctk.CTkFrame(lan_card, fg_color="transparent")
    app._lan_peers_frame.grid(row=1, column=0, padx=8, pady=(0, 10), sticky="ew")
    app._lan_peers_frame.grid_columnconfigure(0, weight=1)
    _refresh_lan()

    # Polling automático a cada 6 s
    def _lan_poll() -> None:
        if parent.winfo_exists():
            _refresh_lan()
            parent.after(6000, _lan_poll)
    parent.after(6000, _lan_poll)

    # ── Seção: Máquinas Remotas ────────────────────────────────────────────
    app._section_lbl(parent, 6, "🌐  Máquinas Remotas")

    # Botão Adicionar
    add_row = ctk.CTkFrame(parent, fg_color="transparent")
    add_row.grid(row=7, column=0, padx=20, pady=(0, 6), sticky="w")

    def _add_remote() -> None:
        dlg = tk.Toplevel(app)
        dlg.title("Adicionar Conexão Remota")
        dlg.geometry("520x230")
        dlg.configure(bg="#111118")
        dlg.grab_set()
        dlg.resizable(False, False)

        ctk.CTkLabel(dlg, text="Cole o código de identidade fornecido pela máquina remota:",
                     text_color="gray70").pack(padx=20, pady=(20, 6), anchor="w")
        code_sv = tk.StringVar()
        ctk.CTkEntry(dlg, textvariable=code_sv, height=34, width=480,
                     font=ctk.CTkFont(family="Consolas", size=10),
                     placeholder_text="eyJuIjoi...").pack(padx=20)
        err_var = tk.StringVar()
        ctk.CTkLabel(dlg, textvariable=err_var, text_color="#ff6666",
                     font=ctk.CTkFont(size=11)).pack(padx=20, pady=(4, 0), anchor="w")

        def _confirm() -> None:
            try:
                data = parse_identity_code(code_sv.get())
            except ValueError as exc:
                err_var.set(str(exc))
                return
            inst = {
                "name":     data["n"],
                "host":     data["h"],
                "port":     data["p"],
                "token":    data["t"],   # salvo até ser desmarcado como favorito
                "favorite": False,
            }
            app.config_manager.config.remote_instances.append(inst)
            app.config_manager.save()
            dlg.destroy()
            app._refresh_remote_instances_list()

        ctk.CTkButton(dlg, text="✔  Adicionar", height=36,
                      fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
                      command=_confirm).pack(pady=16)

    ctk.CTkButton(
        add_row, text="＋  Adicionar Conexão via Código", height=36,
        fg_color=_GREEN_DARK, hover_color=_GREEN_HOVER,
        command=_add_remote,
    ).pack(side="left")

    # Container das conexões
    app._remote_instances_frame = ctk.CTkFrame(parent, fg_color="transparent")
    app._remote_instances_frame.grid(row=8, column=0, padx=20, pady=(0, 24), sticky="ew")
    app._remote_instances_frame.grid_columnconfigure(0, weight=1)
    app._refresh_remote_instances_list()

