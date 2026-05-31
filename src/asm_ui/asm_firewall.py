"""
asm_firewall.py — Verificador de Regras de Firewall TEK.

Verifica e cria regras de firewall Windows para as portas do servidor ARK
usando o comando `netsh advfirewall`.

Uso:
    from src.asm_engine.asm_firewall import check_firewall_rules, create_firewall_rules
    rules = check_firewall_rules(srv)
    create_firewall_rules(srv)

Ou via janela:
    from src.asm_engine.asm_firewall import open_asm_firewall_dialog
    open_asm_firewall_dialog(app, srv)
"""
from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..asm_engine.asm_server_config import AsmServerConfig
from ..ui_constants import get_theme

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp


# ─────────────────────────────────────────────────────────────────────────────
# Lógica de verificação (sem UI)
# ─────────────────────────────────────────────────────────────────────────────


def _netsh_show_rules() -> str:
    """Retorna a saída de 'netsh advfirewall firewall show rule name=all'."""
    try:
        result = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
            capture_output=True, text=True, timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
        )
        return result.stdout
    except Exception:
        return ""


def _port_in_rules(output: str, port: int, protocol: str) -> bool:
    """Verifica se a porta/protocolo aparece nas regras listadas."""
    port_str = str(port)
    proto_lower = protocol.lower()
    lines = output.splitlines()
    for i, line in enumerate(lines):
        if proto_lower in line.lower() and port_str in line:
            return True
        # Formato: "LocalPort: 7777"
        if "localport" in line.lower() and port_str in line:
            # Verifica se protocolo está próximo
            context = "\n".join(lines[max(0, i - 5):i + 5]).lower()
            if proto_lower in context:
                return True
    return False


def check_firewall_rules(srv: AsmServerConfig) -> list[dict]:
    """Verifica regras de firewall para as portas do servidor.

    Retorna lista de dicts:
        {"port": int, "protocol": str, "desc": str, "status": "open"|"missing"}
    """
    output = _netsh_show_rules()
    ports = [
        (srv.server_port,  "UDP", "Conexão de Jogadores"),
        (srv.query_port,   "UDP", "Steam Query"),
        (srv.rcon_port,    "TCP", "RCON"),
    ]
    results = []
    for port, proto, desc in ports:
        found = _port_in_rules(output, port, proto)
        results.append({
            "port":     port,
            "protocol": proto,
            "desc":     desc,
            "status":   "open" if found else "missing",
        })
    return results


def create_firewall_rules(srv: AsmServerConfig) -> list[str]:
    """Cria regras de firewall para as portas do servidor (requer privilégios admin).

    Retorna lista de mensagens de resultado por regra.
    """
    ports = [
        (srv.server_port,  "UDP", "Jogadores"),
        (srv.query_port,   "UDP", "SteamQuery"),
        (srv.rcon_port,    "TCP", "RCON"),
    ]
    messages = []
    for port, proto, label in ports:
        rule_name = f"ARKLAND - {srv.name} - {label} {proto} {port}"
        cmd = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={rule_name}",
            f"protocol={proto}",
            f"localport={port}",
            "action=allow",
            "dir=in",
            "enable=yes",
            "profile=any",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
            )
            if result.returncode == 0:
                messages.append(f"✔ {rule_name}")
            else:
                messages.append(f"✘ {rule_name}: {result.stderr.strip() or result.stdout.strip()}")
        except Exception as exc:
            messages.append(f"✘ {label} {port}/{proto}: {exc}")
    return messages


# ─────────────────────────────────────────────────────────────────────────────
# Janela de UI
# ─────────────────────────────────────────────────────────────────────────────


def open_asm_firewall_dialog(
    app: "ARKServerManagerApp", srv: AsmServerConfig
) -> None:
    """Abre dialog de verificação/criação de regras de firewall."""
    _FirewallDialog(app, srv)


class _FirewallDialog(ctk.CTkToplevel):
    def __init__(self, app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
        super().__init__(app)
        th = get_theme("tek")
        bg      = th["bg"]
        card_bg = th["card_bg"]
        accent  = th["accent"]
        sep     = th.get("separator", "#1e293b")
        t_sec   = th.get("text_secondary", "#94a3b8")
        t_mut   = th.get("text_muted", "#475569")

        self._app = app
        self._srv = srv

        self.title(f"Firewall — {srv.name}")
        self.geometry("520x400")
        self.resizable(False, False)
        self.configure(fg_color=bg)
        self.grab_set()
        self.after(100, self.lift)
        self.after(150, self.focus_force)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Cabeçalho ─────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=card_bg, corner_radius=0, height=50)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            hdr,
            text="🔒  Verificador de Firewall Windows",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=accent,
        ).grid(row=0, column=0, padx=16, pady=14, sticky="w")

        # ── Lista de portas ────────────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=14, pady=10)
        body.grid_columnconfigure(0, weight=1)

        self._rows_frame = ctk.CTkFrame(body, fg_color="transparent")
        self._rows_frame.grid(row=0, column=0, sticky="ew")
        self._rows_frame.grid_columnconfigure(2, weight=1)

        # Log de operações
        self._log = ctk.CTkTextbox(
            body, state="disabled", height=120,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#04090f", text_color="#d1fae5",
            border_width=1, border_color=sep,
            corner_radius=6, wrap="word",
        )
        self._log.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        # Botões
        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="e", pady=(10, 0))

        ctk.CTkButton(
            btn_row, text="↺  Verificar", width=100, height=32,
            fg_color="#0f172a", hover_color="#1e293b",
            border_width=1, border_color=sep,
            text_color=t_sec,
            font=ctk.CTkFont(size=11),
            command=self._do_check,
        ).pack(side="left", padx=(0, 8))

        self._btn_create = ctk.CTkButton(
            btn_row, text="✚  Criar Regras", width=120, height=32,
            fg_color="#14532d", hover_color="#166534",
            text_color=accent,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._do_create,
        )
        self._btn_create.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="Fechar", width=80, height=32,
            fg_color="#0f172a", hover_color="#1e293b",
            border_width=1, border_color=sep,
            command=self.destroy,
        ).pack(side="left")

        self._do_check()

    def _do_check(self) -> None:
        import threading
        self._log_line("Verificando regras de firewall…")
        threading.Thread(target=self._check_worker, daemon=True).start()

    def _check_worker(self) -> None:
        rules = check_firewall_rules(self._srv)
        self.after(0, lambda r=rules: self._render_rules(r))

    def _render_rules(self, rules: list[dict]) -> None:
        th = get_theme("tek")
        t_sec = th.get("text_secondary", "#94a3b8")
        t_mut = th.get("text_muted", "#475569")

        for w in self._rows_frame.winfo_children():
            w.destroy()

        # Cabeçalho
        for col, (txt, w) in enumerate([("Porta", 60), ("Proto", 52), ("Descrição", 200), ("Status", 80)]):
            ctk.CTkLabel(
                self._rows_frame, text=txt, width=w, anchor="w",
                font=ctk.CTkFont(size=11, weight="bold"), text_color=t_sec,
            ).grid(row=0, column=col, padx=(6 if col == 0 else 2, 0), pady=(0, 4), sticky="w")

        for i, rule in enumerate(rules):
            is_open = rule["status"] == "open"
            row_bg = th["card_bg"] if i % 2 == 0 else "#0a1520"
            row = ctk.CTkFrame(self._rows_frame, fg_color=row_bg, corner_radius=4, height=34)
            row.grid(row=i + 1, column=0, columnspan=4, sticky="ew", pady=1)
            row.grid_propagate(False)

            ctk.CTkLabel(row, text=str(rule["port"]), width=60,
                         font=ctk.CTkFont(family="Consolas", size=11), text_color=t_sec).pack(side="left", padx=(8, 4))
            ctk.CTkLabel(row, text=rule["protocol"], width=52,
                         font=ctk.CTkFont(size=11), text_color=t_mut).pack(side="left", padx=(0, 4))
            ctk.CTkLabel(row, text=rule["desc"], width=200, anchor="w",
                         font=ctk.CTkFont(size=11), text_color=t_sec).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(
                row,
                text="✔ Aberta" if is_open else "✘ Faltando",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#4ade80" if is_open else "#f87171",
            ).pack(side="left")

        missing = sum(1 for r in rules if r["status"] == "missing")
        if missing == 0:
            self._log_line("✔ Todas as portas estão abertas no firewall.", color="#4ade80")
        else:
            self._log_line(f"⚠ {missing} porta(s) sem regra de firewall. Clique em 'Criar Regras'.", color="#fbbf24")

    def _do_create(self) -> None:
        import threading
        self._btn_create.configure(state="disabled")
        self._log_line("Criando regras de firewall (requer privilégios de admin)…")
        threading.Thread(target=self._create_worker, daemon=True).start()

    def _create_worker(self) -> None:
        messages = create_firewall_rules(self._srv)
        for msg in messages:
            self.after(0, lambda m=msg: self._log_line(m))
        self.after(500, self._do_check)
        self.after(0, lambda: self._btn_create.configure(state="normal"))

    def _log_line(self, text: str, color: str = "#d1fae5") -> None:
        if not self.winfo_exists():
            return
        import time
        self._log.configure(state="normal")
        ts = time.strftime("%H:%M:%S")
        self._log.insert("end", f"[{ts}] ", ("ts",))
        self._log.insert("end", text + "\n", ("msg",))
        self._log.tag_config("ts",  foreground="#475569")
        self._log.tag_config("msg", foreground=color)
        self._log.see("end")
        self._log.configure(state="disabled")
