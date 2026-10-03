"""Página «Diagnóstico» — Verificar saúde, gerar .zip, envio opt-in e controle de logs.

Compartilhada pelos dois modos de UI (clássico e TEK/ASM). Toda a lógica pesada está em
``src/diagnostics``; aqui só ficam widgets e threads de fundo (a UI nunca bloqueia).
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import messagebox
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..diagnostics import paths
from ..diagnostics.events import CAT_DIAG, diag_event
from ..ui_constants import get_theme

_LOG = logging.getLogger("arkland")

_SEV_COLOR = {"ERRO": "#f87171", "AVISO": "#fbbf24", "OK": "#4ade80"}
_SEV_ICON = {"ERRO": "✖", "AVISO": "▲", "OK": "✔"}
_SEV_RANK = {"ERRO": 0, "AVISO": 1, "OK": 2}
_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")

CONFIRM_SEND_TEXT = (
    "Serão enviados logs e configurações do app e dos servidores, com segredos "
    "(senhas, tokens, API keys, webhooks) mascarados automaticamente.\n\n"
    "IPs, nomes de servidor e SteamIDs NÃO são anonimizados.\n\n"
    "Deseja continuar?"
)


def open_in_explorer(path: Path) -> None:
    """Abre uma pasta (ou seleciona um arquivo) no Explorer; falha silenciosa e logada."""
    try:
        path = Path(path)
        if sys.platform == "win32":
            if path.is_file():
                subprocess.Popen(["explorer", "/select,", str(path)])
            else:
                os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path if path.is_dir() else path.parent)])
    except Exception:  # noqa: BLE001
        _LOG.warning("Não foi possível abrir %s", path, exc_info=True)


def _alive(widget: Any) -> bool:
    try:
        return bool(widget is not None and widget.winfo_exists())
    except Exception:  # noqa: BLE001
        return False


def _ui(app: Any, fn: Callable[[], None]) -> None:
    """Agenda ``fn`` na thread da UI (seguro a partir de threads de fundo)."""
    def _safe() -> None:
        try:
            fn()
        except Exception:  # noqa: BLE001
            _LOG.warning("Atualização da tela Diagnóstico falhou", exc_info=True)
    try:
        app.after(0, _safe)
    except Exception:  # noqa: BLE001
        pass


class _DiagnosticsPage:
    def __init__(self, app: Any, parent: Any) -> None:
        self.app = app
        self.parent = parent
        self.th = get_theme(getattr(app, "_active_mode", None) or "primitive")
        self.results: List[Any] = []
        self.busy = False
        self.mode = "tek" if getattr(app, "asm_config_manager", None) is not None else "classic"

    # ── construção ──────────────────────────────────────────────────────────
    def build(self) -> None:
        p, th = self.parent, self.th
        p.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(p, text="Diagnóstico", font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=th["text_primary"]).grid(row=0, column=0, padx=24, pady=(24, 2), sticky="w")
        ctk.CTkLabel(p, text="Verifique a saúde da instalação, gere um pacote de diagnóstico e envie "
                             "(opcional) quando precisar de ajuda.", text_color=th["text_secondary"],
                     wraplength=760, justify="left").grid(row=1, column=0, padx=24, pady=(0, 14), sticky="w")
        self._build_doctor_card(2)
        self._build_package_card(4)
        self._build_send_card(6)
        self._build_logs_card(8)

    def _section(self, row: int, text: str) -> None:
        ctk.CTkLabel(self.parent, text=text, font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=self.th.get("accent_label", self.th["accent"])).grid(
            row=row, column=0, padx=24, pady=(10, 2), sticky="w")

    def _card(self, row: int) -> Any:
        card = ctk.CTkFrame(self.parent, corner_radius=12, fg_color=self.th["card_bg"])
        card.grid(row=row, column=0, padx=20, pady=(0, 10), sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        return card

    def _btn(self, parent: Any, text: str, command: Callable[[], None], width: int = 200) -> Any:
        th = self.th
        return ctk.CTkButton(parent, text=text, width=width, height=36, corner_radius=8,
                             fg_color=th["accent_dark"], hover_color=th["accent_hover"],
                             text_color="#ffffff", command=command)

    # Verificar saúde ------------------------------------------------------------
    def _build_doctor_card(self, row: int) -> None:
        self._section(row, "🩺  Verificar saúde")
        card = self._card(row + 1)
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="ew")
        self.doctor_btn = self._btn(top, "🩺  Verificar saúde", self._on_doctor)
        self.doctor_btn.pack(side="left")
        self.doctor_status = ctk.CTkLabel(top, text="Ainda não executado.", text_color=self.th["text_secondary"])
        self.doctor_status.pack(side="left", padx=14)
        self.results_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.results_frame.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="ew")
        self.results_frame.grid_columnconfigure(1, weight=1)

    def _on_doctor(self) -> None:
        if self.busy:
            return
        self._set_busy(True)
        self.doctor_status.configure(text="Verificando… (as checagens rodam em segundo plano)",
                                     text_color=self.th["text_secondary"])
        from ..diagnostics.doctor import DoctorContext, run_doctor_async
        try:
            ctx = DoctorContext.from_config_dir(app=self.app)
        except Exception:  # noqa: BLE001
            _LOG.exception("Falha ao preparar o doctor")
            self._set_busy(False)
            self.doctor_status.configure(text="Falha ao preparar a verificação (veja o log).",
                                         text_color=_SEV_COLOR["ERRO"])
            return
        run_doctor_async(ctx, on_done=lambda res: _ui(self.app, lambda: self._show_results(res)))

    def _show_results(self, results: List[Any]) -> None:
        self._set_busy(False)
        self.results = list(results)
        if not _alive(self.results_frame):
            return
        for w in self.results_frame.winfo_children():
            w.destroy()
        from ..diagnostics.doctor import summarize
        s = summarize(results)
        worst = "ERRO" if s["ERRO"] else "AVISO" if s["AVISO"] else "OK"
        self.doctor_status.configure(
            text=f"{s['OK']} OK  •  {s['AVISO']} aviso(s)  •  {s['ERRO']} erro(s)",
            text_color=_SEV_COLOR[worst])
        th = self.th
        for i, r in enumerate(sorted(results, key=lambda x: (_SEV_RANK.get(x.severity, 3), x.id))):
            color = _SEV_COLOR.get(r.severity, th["text_secondary"])
            ctk.CTkLabel(self.results_frame, text=f"{_SEV_ICON.get(r.severity, '?')} {r.severity}",
                         text_color=color, width=82, anchor="w",
                         font=ctk.CTkFont(size=12, weight="bold")).grid(row=i * 2, column=0, sticky="nw", pady=(6, 0))
            ctk.CTkLabel(self.results_frame, text=r.title, anchor="w", justify="left", wraplength=640,
                         text_color=th["text_primary"],
                         font=ctk.CTkFont(size=12, weight="bold")).grid(row=i * 2, column=1, sticky="w", pady=(6, 0))
            body = r.detail + (f"\n💡 {r.hint}" if r.hint and r.severity != "OK" else "")
            if body:
                ctk.CTkLabel(self.results_frame, text=body, anchor="w", justify="left", wraplength=640,
                             text_color=th["text_secondary"], font=ctk.CTkFont(size=11)).grid(
                    row=i * 2 + 1, column=1, sticky="w")

    # Pacote .zip ------------------------------------------------------------------
    def _build_package_card(self, row: int) -> None:
        self._section(row, "📦  Pacote de diagnóstico")
        card = self._card(row + 1)
        ctk.CTkLabel(card, text="Gera um .zip com logs recentes, configs (segredos mascarados), INIs, plugins "
                                "ArkApi e o resultado da verificação de saúde.",
                     text_color=self.th["text_secondary"], wraplength=740, justify="left").grid(
            row=0, column=0, padx=16, pady=(14, 6), sticky="w")
        line = ctk.CTkFrame(card, fg_color="transparent")
        line.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="ew")
        self.zip_btn = self._btn(line, "📦  Gerar diagnóstico (.zip)", self._on_generate, width=240)
        self.zip_btn.pack(side="left")
        self.zip_status = ctk.CTkLabel(line, text=f"Pasta: {paths.diagnostics_dir()}",
                                       text_color=self.th["text_muted"], wraplength=480, justify="left")
        self.zip_status.pack(side="left", padx=14)

    def _on_generate(self) -> None:
        if self.busy:
            return
        self._set_busy(True)
        self.zip_status.configure(text="Gerando pacote…", text_color=self.th["text_secondary"])

        def _work() -> None:
            try:
                res = self._collect()
            except Exception as exc:  # noqa: BLE001
                _LOG.exception("Falha ao gerar diagnóstico")
                _ui(self.app, lambda e=exc: self._zip_done(None, e))   # `exc` some após o except
                return
            _ui(self.app, lambda: self._zip_done(res, None))

        threading.Thread(target=_work, name="diag-collect", daemon=True).start()

    def _collect(self, max_zip_bytes: Optional[int] = None) -> Any:
        from ..diagnostics.collector import DEFAULT_MAX_ZIP_BYTES, collect_diagnostics
        return collect_diagnostics(app=self.app, mode=self.mode,
                                   max_zip_bytes=max_zip_bytes or DEFAULT_MAX_ZIP_BYTES,
                                   doctor_results=self.results or None)

    def _zip_done(self, res: Any, exc: Optional[BaseException]) -> None:
        self._set_busy(False)
        if exc is not None or res is None:
            self.zip_status.configure(text=f"Falha ao gerar o pacote: {exc}", text_color=_SEV_COLOR["ERRO"])
            return
        extra = f"  ({len(res.warnings)} aviso(s) na coleta)" if res.warnings else ""
        self.zip_status.configure(text=f"Gerado: {res.path.name} ({res.size // 1024} KB){extra}",
                                  text_color=_SEV_COLOR["OK"])
        open_in_explorer(res.path)

    # Envio -----------------------------------------------------------------------
    def _build_send_card(self, row: int) -> None:
        self._section(row, "📤  Enviar (opcional)")
        card = self._card(row + 1)
        th = self.th
        ctk.CTkLabel(card, text="Nada é enviado automaticamente. Cada botão pede confirmação antes de enviar.",
                     text_color=th["text_secondary"], wraplength=740, justify="left").grid(
            row=0, column=0, padx=16, pady=(14, 8), sticky="w")
        # Discord
        ctk.CTkLabel(card, text="Webhook do Discord", text_color=th["text_secondary"]).grid(
            row=1, column=0, padx=16, sticky="w")
        wrow = ctk.CTkFrame(card, fg_color="transparent")
        wrow.grid(row=2, column=0, padx=16, pady=(2, 6), sticky="ew")
        wrow.grid_columnconfigure(0, weight=1)
        self.webhook_var = ctk.StringVar(value=str(paths.load_prefs().get("discord_webhook_url") or ""))
        self.webhook_entry = ctk.CTkEntry(wrow, textvariable=self.webhook_var, show="•",
                                          placeholder_text="https://discord.com/api/webhooks/…")
        self.webhook_entry.grid(row=0, column=0, sticky="ew")
        self.webhook_entry.bind("<FocusOut>", lambda _e: self._save_webhook())
        self._show_hook = False
        ctk.CTkButton(wrow, text="👁", width=36, fg_color=th["accent_muted_bg"], hover_color=th["accent_hover"],
                      text_color=th["accent"], command=self._toggle_webhook_visibility).grid(
            row=0, column=1, padx=(6, 0))
        ctk.CTkLabel(card, text="Salvo em diagnostics.json (APPDATA). Aparece mascarado dentro do .zip.",
                     text_color=th["text_muted"], font=ctk.CTkFont(size=10)).grid(
            row=3, column=0, padx=16, sticky="w")
        brow = ctk.CTkFrame(card, fg_color="transparent")
        brow.grid(row=4, column=0, padx=16, pady=(8, 4), sticky="w")
        self.discord_btn = self._btn(brow, "📨  Enviar para Discord", self._on_send_discord, width=220)
        self.discord_btn.pack(side="left")
        self.webstore_btn = self._btn(brow, "🛒  Enviar para a Web Store", self._on_send_webstore, width=240)
        self.webstore_btn.pack(side="left", padx=10)
        self.send_status = ctk.CTkLabel(card, text="", text_color=th["text_secondary"], wraplength=740,
                                        justify="left")
        self.send_status.grid(row=5, column=0, padx=16, pady=(2, 14), sticky="w")

    def _toggle_webhook_visibility(self) -> None:
        self._show_hook = not self._show_hook
        self.webhook_entry.configure(show="" if self._show_hook else "•")

    def _save_webhook(self) -> None:
        try:
            paths.save_prefs(discord_webhook_url=self.webhook_var.get().strip())
        except Exception:  # noqa: BLE001
            _LOG.warning("Não foi possível salvar o webhook de diagnóstico", exc_info=True)

    def _set_send_status(self, text: str, ok: Optional[bool] = None) -> None:
        if not _alive(self.send_status):
            return
        color = self.th["text_secondary"] if ok is None else _SEV_COLOR["OK" if ok else "ERRO"]
        self.send_status.configure(text=text, text_color=color)

    def _confirm(self, destination: str) -> bool:
        return bool(messagebox.askyesno(f"Enviar para {destination}", CONFIRM_SEND_TEXT, parent=self.app))

    def _on_send_discord(self) -> None:
        if self.busy:
            return
        from ..diagnostics.sender import is_valid_discord_webhook
        url = self.webhook_var.get().strip()
        self._save_webhook()
        if not is_valid_discord_webhook(url):
            self._set_send_status("Informe uma URL de webhook válida (https://discord.com/api/webhooks/…).", False)
            return
        if not self._confirm("o Discord"):
            return
        self._start_send("Gerando pacote e enviando ao Discord…", lambda: self._do_discord(url))

    def _do_discord(self, url: str) -> Any:
        from ..diagnostics.collector import DISCORD_MAX_ZIP_BYTES
        from ..diagnostics.sender import build_summary, send_to_discord
        from ..version import APP_VERSION
        res = self._collect(max_zip_bytes=DISCORD_MAX_ZIP_BYTES)
        summary = build_summary(self.results, APP_VERSION, self.mode) if self.results else (
            f"**Diagnóstico ARKLAND** v{APP_VERSION} ({self.mode})")
        sent = send_to_discord(url, res.path, summary)
        return sent, res

    def _on_send_webstore(self) -> None:
        if self.busy:
            return
        from ..diagnostics.sender import resolve_webstore_target
        try:
            base, key = resolve_webstore_target(self.app)
        except Exception:  # noqa: BLE001
            _LOG.warning("Web Store indisponível para envio", exc_info=True)
            self._set_send_status("Não foi possível ler a configuração da Web Store (Configurações › Loja).", False)
            return
        if not base or not key:
            self._set_send_status("Configure a URL e a API key da Web Store em Configurações › Loja.", False)
            return
        if not self._confirm("a Web Store"):
            return
        self._start_send("Gerando pacote e enviando à Web Store…", lambda: self._do_webstore(base, key))

    def _do_webstore(self, base: str, key: str) -> Any:
        import socket
        from ..diagnostics.sender import send_to_webstore
        from ..version import APP_VERSION
        res = self._collect()
        sent = send_to_webstore(base, key, res.path, app_version=APP_VERSION, mode=self.mode,
                                machine=socket.gethostname(), doctor_summary=res.doctor_summary)
        return sent, res

    def _start_send(self, status: str, job: Callable[[], Any]) -> None:
        self._set_busy(True)
        self._set_send_status(status)

        def _work() -> None:
            try:
                sent, res = job()
            except Exception as exc:  # noqa: BLE001 — nunca derruba o app
                _LOG.exception("Falha no envio do diagnóstico")
                _ui(self.app, lambda e=exc: self._send_done(None, None, e))   # `exc` some após o except
                return
            _ui(self.app, lambda: self._send_done(sent, res, None))

        threading.Thread(target=_work, name="diag-send", daemon=True).start()

    def _send_done(self, sent: Any, res: Any, exc: Optional[BaseException]) -> None:
        self._set_busy(False)
        if exc is not None or sent is None:
            self._set_send_status(f"Falha inesperada no envio: {exc}. O pacote local não foi afetado.", False)
            return
        where = f" Pacote salvo em: {res.path}" if res is not None else ""
        extra = ""
        if res is not None and res.over_limit:
            extra = " (aviso: pacote maior que o limite recomendado)"
        self._set_send_status(sent.message + extra + ("" if sent.ok and not sent.partial else where),
                              sent.ok and not sent.partial)
        diag_event(CAT_DIAG, "Envio de diagnóstico finalizado", ok=sent.ok, partial=sent.partial)

    # Logs ------------------------------------------------------------------------
    def _build_logs_card(self, row: int) -> None:
        self._section(row, "📜  Logs")
        card = self._card(row + 1)
        th = self.th
        line = ctk.CTkFrame(card, fg_color="transparent")
        line.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="w")
        ctk.CTkLabel(line, text="Nível de log:", text_color=th["text_secondary"]).pack(side="left")
        current = str(paths.load_prefs().get("log_level") or "INFO").upper()
        self.level_var = ctk.StringVar(value=current if current in _LEVELS else "INFO")
        ctk.CTkOptionMenu(line, values=list(_LEVELS), variable=self.level_var, width=130,
                          fg_color=th["accent_dark"], button_color=th["accent_dark"],
                          button_hover_color=th["accent_hover"],
                          command=self._on_level_change).pack(side="left", padx=10)
        self._btn(line, "📂  Abrir pasta de logs", self._on_open_logs, width=200).pack(side="left", padx=6)
        self.log_info = ctk.CTkLabel(card, text=f"Arquivo: {paths.log_file_path()}  (rotação 2 MB × 5)",
                                     text_color=th["text_muted"], wraplength=740, justify="left")
        self.log_info.grid(row=1, column=0, padx=16, pady=(0, 14), sticky="w")

    def _on_level_change(self, value: str) -> None:
        try:
            from ..diagnostics.logging_setup import set_log_level
            set_log_level(value)
        except Exception:  # noqa: BLE001
            _LOG.warning("Não foi possível alterar o nível de log", exc_info=True)

    def _on_open_logs(self) -> None:
        d = paths.logs_dir()
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        open_in_explorer(d)

    # Estado ----------------------------------------------------------------------
    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        for name in ("doctor_btn", "zip_btn", "discord_btn", "webstore_btn"):
            w = getattr(self, name, None)
            if _alive(w):
                try:
                    w.configure(state=state)
                except Exception:  # noqa: BLE001
                    pass


def build_diagnostics(app: Any, parent: Any) -> None:
    """Constrói a página «Diagnóstico» dentro de ``parent`` (frame rolável)."""
    page = _DiagnosticsPage(app, parent)
    app._diagnostics_page = page   # mantém referência (callbacks de threads)
    page.build()
