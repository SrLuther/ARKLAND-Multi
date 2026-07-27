"""
S5.2 — Assistente IA contextual.
Chat que recebe a config atual do servidor como contexto e sugere ajustes.
Suporta NVIDIA NIM, OpenAI ou modo offline (heurísticas locais).
"""
from __future__ import annotations

import json
import threading
import tkinter as tk
from dataclasses import asdict
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import customtkinter as ctk  # type: ignore[reportMissingImports]

from ..ui_constants import get_theme
from ..asm_engine.asm_server_config import AsmServerConfig

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

# Provedores disponíveis
_PROVIDERS = {
    "nvidia": {
        "label":    "NVIDIA NIM — Grátis",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model":    "meta/llama-3.3-70b-instruct",
        "key_hint": "nvapi-...",
        "key_prefix": "nvapi-",
    },
    "openai": {
        "label":    "OpenAI GPT-4o Mini",
        "base_url": "https://api.openai.com/v1",
        "model":    "gpt-4o-mini",
        "key_hint": "sk-...",
        "key_prefix": "sk-",
    },
}
_CREDS_KEYS = {
    "nvidia": "nvidia_api_key",
    "openai": "openai_api_key",
}

# Modelos NVIDIA disponíveis (mesmos do ARKLAND SM)
_NVIDIA_MODELS = [
    ("meta/llama-3.3-70b-instruct",               "Llama 3.3 70B — Rápido & Poderoso ✅"),
    ("openai/gpt-oss-120b",                        "GPT OSS 120B — Raciocínio Avançado"),
    ("deepseek-ai/deepseek-r1",                    "DeepSeek R1 — Forte em Lógica"),
    ("nvidia/llama-3.1-nemotron-ultra-253b-v1",    "Nemotron Ultra 253B — Enterprise ⚠"),
]

# ── Sugestões offline (heurísticas) ──────────────────────────────────────────

def _offline_advice(config_snapshot: Dict[str, Any], user_msg: str) -> str:
    """
    Gera sugestões simples sem chamada de API.
    Analisa multiplicadores e flags mais comuns do servidor.
    """
    msg = user_msg.lower()
    lines: List[str] = []

    tm = config_snapshot.get("taming_speed_multiplier", 1.0)
    xp = config_snapshot.get("xp_multiplier", 1.0)
    harvest = config_snapshot.get("harvest_amount_multiplier", 1.0)
    breeding = config_snapshot.get("baby_mature_speed_multiplier", 1.0)
    max_players = config_snapshot.get("max_players", 70)
    rcon = config_snapshot.get("rcon_enabled", False)
    pvp = config_snapshot.get("enable_pvp", True)

    if "taming" in msg or "tame" in msg or "domesticação" in msg:
        if tm < 3.0:
            lines.append(f"⚡ **Taming lento** — atual {tm:.1f}x. Para servidores casuais, 5x–10x é bem recebido.")
        else:
            lines.append(f"✅ **Taming speed** de {tm:.1f}x parece adequado para a maioria dos jogadores.")

    if "xp" in msg or "experiência" in msg or "level" in msg:
        if xp < 2.0:
            lines.append(f"⚠ **XP baixo** — atual {xp:.1f}x. Muitos jogadores casuais preferem 2x–5x para evitar grindar.")
        elif xp > 20.0:
            lines.append(f"⚠ **XP muito alto** ({xp:.1f}x) pode tornar o jogo trivial. Considere reduzir para 10x.")
        else:
            lines.append(f"✅ XP de {xp:.1f}x parece equilibrado.")

    if "harvest" in msg or "coleta" in msg or "recurso" in msg:
        if harvest < 2.0:
            lines.append(f"⚡ **Harvest lento** — atual {harvest:.1f}x. Valor 3x–5x é mais agradável em servidores não-oficiais.")
        else:
            lines.append(f"✅ Harvest de {harvest:.1f}x ok.")

    if "breed" in msg or "criação" in msg or "dino baby" in msg:
        if breeding < 10.0:
            lines.append(f"🐣 **Criação lenta** — atual {breeding:.1f}x. Para servidores PvE, 20x–50x costuma ser bem-vindo.")

    if "pvp" in msg or "pvp" in msg:
        if pvp:
            lines.append("⚔ **PvP ativado.** Certifique-se que offline protection está configurado se necessário.")
        else:
            lines.append("🌿 **PvE mode** — ideal para servidores familiares ou roleplay.")

    if "rcon" in msg:
        if not rcon:
            lines.append("🔒 **RCON desativado.** Ative para poder gerenciar o servidor remotamente sem teclado no host.")

    if "player" in msg or "jogador" in msg:
        if max_players > 100:
            lines.append(f"⚠ **{max_players} jogadores** é muito. Servidores ARK com mais de 70 costumam ter lag.")
        else:
            lines.append(f"👥 Limite de {max_players} jogadores parece razoável.")

    if not lines:
        lines.append(
            "🤖 **Dica geral:** Revise os multiplicadores de XP, coleta e taming antes de lançar o servidor. "
            "Use RCON habilitado para administração remota. "
            "Backups diários automáticos são altamente recomendados."
        )

    return "\n\n".join(lines)


# ── Chamada de API (OpenAI-compatible) ───────────────────────────────────────

def _api_chat(api_key: str, base_url: str, model: str,
              messages: List[Dict[str, str]]) -> str:
    """Chama qualquer endpoint compatível com a API OpenAI chat/completions."""
    import urllib.request
    import urllib.error

    body = json.dumps({
        "model":      model,
        "messages":   messages,
        "max_tokens": 600,
    }).encode()

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=body,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as exc:
        # Lê o corpo do erro para mostrar a mensagem real da API
        try:
            err_body = json.loads(exc.read())
            api_msg = (
                err_body.get("message")
                or err_body.get("error", {}).get("message")
                or str(err_body)
            )
        except Exception:
            api_msg = str(exc)
        return (
            f"[Erro {exc.code} da API: {api_msg}]\n\n"
            f"💡 Modelo: `{model}`\n"
            "Se o erro for 404, tente outro modelo (ex: Llama 3.3 70B). "
            "Alguns modelos exigem acesso especial ou plano pago."
        )
    except Exception as exc:
        return f"[Erro ao contatar a API: {exc}]"


# ── Janela do assistente ──────────────────────────────────────────────────────

class _AIAssistantWindow(ctk.CTkToplevel):
    def __init__(self, parent, srv: AsmServerConfig, app: "ARKServerManagerApp"):
        super().__init__(parent)
        th = get_theme("tek")
        self._bg    = th["bg"]
        self._cg    = th["card_bg"]
        self._sep   = th["separator"]
        self._acc   = th["accent"]
        self._t_sec = th["text_secondary"]
        self._t_mut = th["text_muted"]
        self._acc_mb = th["accent_muted_bg"]

        self.title(f"Assistente IA — {srv.name}")
        self.geometry("760x580")
        self.configure(fg_color=self._bg)
        self.resizable(True, True)
        self.transient(parent)           # sempre acima da janela principal
        self.after(100, self.lift)
        self.after(150, self.focus_force)

        self._srv = srv
        self._app = app
        self._history: List[Dict[str, str]] = []

        # Provider selecionado, modelo e chaves
        self._provider_var = tk.StringVar(value="nvidia")
        self._nvidia_model_var = tk.StringVar(value=_NVIDIA_MODELS[0][0])
        self._keys: Dict[str, str] = self._load_all_keys()

        self._build_ui()
        self._send_welcome()

    def _load_all_keys(self) -> Dict[str, str]:
        try:
            from ..crash_ai import load_ai_keys_dict
            return load_ai_keys_dict()
        except Exception:
            return {k: "" for k in _CREDS_KEYS}

    def _current_key(self) -> str:
        return self._keys.get(self._provider_var.get(), "")

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Toolbar
        tb = ctk.CTkFrame(self, fg_color=self._cg, corner_radius=0)
        tb.grid(row=0, column=0, sticky="ew")
        tb.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(tb, text="🤖 Assistente IA — " + self._srv.name,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=self._acc).grid(row=0, column=0, padx=12, pady=8, sticky="w")

        # Seletor de provedor
        prov_frame = ctk.CTkFrame(tb, fg_color="transparent")
        prov_frame.grid(row=0, column=1, padx=4, pady=4, sticky="w")

        ctk.CTkLabel(prov_frame, text="Provedor:",
                     font=ctk.CTkFont(size=9), text_color=self._t_mut,
                     ).pack(side="left", padx=(0, 4))

        self._prov_combo = ctk.CTkComboBox(
            prov_frame,
            values=[p["label"] for p in _PROVIDERS.values()],
            width=180, height=26,
            font=ctk.CTkFont(size=10),
            command=self._on_provider_change,
        )
        # Seleciona NVIDIA por padrão (ou openai se tiver chave)
        default_prov = "nvidia" if self._keys.get("nvidia") else ("openai" if self._keys.get("openai") else "nvidia")
        self._provider_var.set(default_prov)
        self._prov_combo.set(_PROVIDERS[default_prov]["label"])
        self._prov_combo.pack(side="left", padx=(0, 6))

        # Seletor de modelo NVIDIA
        self._model_combo = ctk.CTkComboBox(
            prov_frame,
            values=[label for _, label in _NVIDIA_MODELS],
            width=230, height=26,
            font=ctk.CTkFont(size=10),
            command=self._on_model_change,
        )
        self._model_combo.set(_NVIDIA_MODELS[0][1])
        self._model_combo.pack(side="left")
        self._model_combo.configure(state="normal" if default_prov == "nvidia" else "disabled")

        # Frame com os botões de ação (coluna 2)
        action_frame = ctk.CTkFrame(tb, fg_color="transparent")
        action_frame.grid(row=0, column=2, padx=(0, 8), pady=4)

        ctk.CTkButton(
            action_frame, text="🔑 Keys (global)", width=120, height=26,
            fg_color=self._sep, hover_color="#263347",
            font=ctk.CTkFont(size=10), text_color=self._t_sec,
            command=self._set_api_key,
        ).pack(side="left", padx=(0, 4))

        ctk.CTkButton(
            action_frame, text="?", width=28, height=26,
            fg_color=self._sep, hover_color="#1e40af",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#60a5fa",
            command=self._open_help,
        ).pack(side="left")

        # Status bar — fica na segunda linha da toolbar (abaixo dos controles)
        self._status_lbl = ctk.CTkLabel(
            tb, text=self._mode_text(),
            font=ctk.CTkFont(size=9), text_color=self._t_mut,
        )
        self._status_lbl.grid(row=1, column=0, columnspan=3, padx=12, pady=(0, 6), sticky="w")

        # Chat
        self._chat_box = ctk.CTkTextbox(
            self, state="disabled",
            fg_color="#060d14", text_color="#94a3b8",
            font=ctk.CTkFont(family="Segoe UI", size=11),
        )
        self._chat_box.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._chat_box._textbox.tag_configure("user",   foreground="#7dd3fc", font=("Segoe UI", 11, "bold"))
        self._chat_box._textbox.tag_configure("ai",     foreground="#94a3b8")
        self._chat_box._textbox.tag_configure("system", foreground="#475569", font=("Segoe UI", 9))

        # Barra de entrada
        input_bar = ctk.CTkFrame(self, fg_color=self._cg, corner_radius=0)
        input_bar.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        input_bar.grid_columnconfigure(0, weight=1)

        self._input_var = tk.StringVar()
        self._entry = ctk.CTkEntry(
            input_bar, textvariable=self._input_var,
            placeholder_text="Pergunte algo sobre a configuração do servidor...",
            height=34, font=ctk.CTkFont(size=11),
        )
        self._entry.grid(row=0, column=0, padx=(8, 4), pady=8, sticky="ew")
        self._entry.bind("<Return>", lambda _: self._on_send())

        ctk.CTkButton(
            input_bar, text="Enviar", width=80, height=34,
            fg_color=self._acc_mb, hover_color="#052e16",
            border_width=1, border_color=self._acc, text_color=self._acc,
            font=ctk.CTkFont(size=11),
            command=self._on_send,
        ).grid(row=0, column=1, padx=(0, 8), pady=8)

    def _mode_text(self) -> str:
        prov = self._provider_var.get()
        if self._current_key():
            return f"{_PROVIDERS[prov]['label']} · key global"
        return "Modo offline — configure a API Key em Configurações Globais → Assistente IA"

    def _open_help(self):
        """Abre janela de ajuda com tutorial de obtenção das API Keys (singleton)."""
        # Singleton — se já existe, traz para frente e retorna
        existing = getattr(self, "_help_win", None)
        if existing is not None and existing.winfo_exists():
            existing.lift()
            existing.focus_force()
            return

        win = ctk.CTkToplevel(self)
        self._help_win = win
        win.title("Ajuda — Como obter a API Key")
        win.geometry("700x620")
        win.configure(fg_color=self._bg)
        win.resizable(True, True)
        win.transient(self)   # mantém sempre acima da janela do assistente
        win.after(100, win.lift)
        win.after(150, win.focus_force)

        # Cabeçalho
        hdr = ctk.CTkFrame(win, fg_color=self._cg, corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(
            hdr, text="❓ Como obter sua API Key de IA",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=self._acc,
        ).pack(padx=16, pady=10, anchor="w")

        # Área de rolagem
        scroll = ctk.CTkScrollableFrame(win, fg_color=self._bg)
        scroll.pack(fill="both", expand=True, padx=8, pady=8)

        def _section(title: str, color: str = "#e2e8f0"):
            ctk.CTkLabel(
                scroll, text=title,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=color, anchor="w",
            ).pack(fill="x", pady=(12, 2), padx=4)

        def _text(content: str, color: str = "#94a3b8"):
            ctk.CTkLabel(
                scroll, text=content,
                font=ctk.CTkFont(size=11),
                text_color=color, anchor="w",
                justify="left", wraplength=640,
            ).pack(fill="x", pady=1, padx=8)

        def _step(num: str, content: str):
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(
                row, text=num, width=26,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=self._acc, anchor="w",
            ).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(
                row, text=content,
                font=ctk.CTkFont(size=11),
                text_color="#cbd5e1", anchor="w",
                justify="left", wraplength=600,
            ).pack(side="left", fill="x")

        def _link_btn(label: str, url: str):
            import webbrowser
            ctk.CTkButton(
                scroll, text=f"🔗  {label}", anchor="w",
                height=28, font=ctk.CTkFont(size=11),
                fg_color="#0f172a", hover_color="#1e293b",
                border_width=1, border_color=self._sep,
                text_color="#60a5fa",
                command=lambda u=url: webbrowser.open(u),
            ).pack(fill="x", padx=8, pady=3)

        def _divider():
            ctk.CTkFrame(scroll, height=1, fg_color=self._sep).pack(
                fill="x", padx=8, pady=8)

        # ── NVIDIA NIM (RECOMENDADO) ──────────────────────────────────────────
        _section("⭐  NVIDIA NIM  (Recomendado — Gratuito)", "#22c55e")
        _text(
            "A NVIDIA NIM oferece acesso gratuito a modelos avançados como Llama 3.3 70B, "
            "DeepSeek R1 e Nemotron Ultra 253B. É o mesmo provedor usado no ARKLAND SM. "
            "A chave começa com nvapi-..."
        )
        _divider()
        _section("Passo a passo — NVIDIA NIM:", "#e2e8f0")
        _step("1.", "Acesse o site abaixo e crie uma conta NVIDIA (ou entre com Google/GitHub):")
        _link_btn("build.nvidia.com — Criar conta gratuita", "https://build.nvidia.com")
        _step("2.", "Após o login, clique no seu perfil (canto superior direito) → \"API Keys\".")
        _step("3.", "Clique em \"Generate Key\" ou \"+ New Key\". Dê um nome como \"ARKLAND\".")
        _step("4.", "A chave gerada começa com nvapi-...  Copie-a agora — ela só é exibida uma vez.")
        _step("5.", "Em ARKLAND: Configurações Globais → Assistente IA (global) → cole a chave e Salvar.")
        _divider()
        _section("Qual modelo escolher?", "#e2e8f0")
        rows = [
            ("Llama 3.3 70B",        "✅ Padrão recomendado. Rápido, bom equilíbrio entre velocidade e qualidade."),
            ("GPT OSS 120B",         "🧠 Melhor raciocínio. Ideal para análises detalhadas de configuração."),
            ("DeepSeek R1",          "🔬 Excelente em lógica e matemática. Ótimo para cálculos de multipliers."),
            ("Nemotron Ultra 253B",  "🏆 Mais poderoso. Respostas longas e precisas. Mais lento."),
        ]
        for model, desc in rows:
            row = ctk.CTkFrame(scroll, fg_color="#0d1b2a", corner_radius=6)
            row.pack(fill="x", padx=8, pady=2)
            ctk.CTkLabel(
                row, text=model, width=180,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#7dd3fc", anchor="w",
            ).pack(side="left", padx=(10, 6), pady=6)
            ctk.CTkLabel(
                row, text=desc,
                font=ctk.CTkFont(size=11),
                text_color="#94a3b8", anchor="w", wraplength=430,
            ).pack(side="left", fill="x", padx=(0, 10), pady=6)

        _divider()
        # ── OPENAI ────────────────────────────────────────────────────────────
        _section("OpenAI GPT-4o Mini  (Pago)", "#f59e0b")
        _text(
            "A OpenAI cobra por uso (tokens). GPT-4o Mini é o modelo mais barato deles. "
            "A chave começa com sk-..."
        )
        _step("1.", "Acesse a plataforma OpenAI:")
        _link_btn("platform.openai.com — Dashboard OpenAI", "https://platform.openai.com")
        _step("2.", "Faça login → clique no seu perfil → \"API Keys\" → \"+ Create new secret key\".")
        _step("3.", "Copie a chave (começa com sk-...) — não será exibida novamente.")
        _step("4.", "Adicione créditos em \"Billing\" (mínimo US$ 5). Sem créditos, a key não funciona.")
        _step("5.", "Em ARKLAND: Configurações Globais → Assistente IA (global) → cole a key OpenAI e Salvar.")    
        _divider()
        _section("💡  Dica de segurança", "#f87171")
        _text(
            "Nunca compartilhe sua API Key. Ela é salva localmente em:\n"
            "%APPDATA%\\ARKLAND-ServerManager\\cloud_credentials.json"
        )

        # Botão fechar
        ctk.CTkButton(
            win, text="Fechar", height=32,
            fg_color=self._sep, hover_color="#263347",
            font=ctk.CTkFont(size=11), text_color=self._t_sec,
            command=win.destroy,
        ).pack(pady=(0, 10), padx=16, fill="x")

    def _on_provider_change(self, choice: str):
        for k, p in _PROVIDERS.items():
            if p["label"] == choice:
                self._provider_var.set(k)
                break
        self._history.clear()
        # Ativa/desativa seletor de modelo NVIDIA
        is_nvidia = self._provider_var.get() == "nvidia"
        if hasattr(self, "_model_combo") and self._model_combo.winfo_exists():
            self._model_combo.configure(state="normal" if is_nvidia else "disabled")
        if hasattr(self, "_status_lbl") and self._status_lbl.winfo_exists():
            self._status_lbl.configure(text=self._mode_text())

    def _on_model_change(self, label: str):
        for model_id, model_label in _NVIDIA_MODELS:
            if model_label == label:
                self._nvidia_model_var.set(model_id)
                break
        self._history.clear()

    def _append_msg(self, role: str, text: str):
        self._chat_box.configure(state="normal")
        prefix = {"user": "Você: ", "ai": "🤖 IA: ", "system": ""}[role]
        if prefix:
            self._chat_box._textbox.insert("end", prefix, role)
        self._chat_box._textbox.insert("end", text + "\n\n", role)
        self._chat_box.configure(state="disabled")
        self._chat_box.see("end")

    def _send_welcome(self):
        cfg = self._srv
        self._append_msg("system",
            f"Servidor: {cfg.name} | Mapa: {cfg.server_map} | "
            f"PvP: {'Sim' if cfg.enable_pvp else 'Não'} | "
            f"Max players: {cfg.max_players} | "
            f"XP: {cfg.xp_multiplier}x | Taming: {cfg.taming_speed_multiplier}x"
        )
        prov_name = _PROVIDERS.get(self._provider_var.get(), {}).get("label", "IA")
        key_status = f"usando **{prov_name}**" if self._current_key() else "no **modo offline** (sem API Key)"
        self._append_msg("ai",
            f"Olá! Sou o assistente de configuração ARKLAND TEK, {key_status}. "
            "Posso analisar as configurações do seu servidor e sugerir ajustes. "
            "Sobre o que quer conversar? (ex: 'otimize o taming', 'revise o XP')"
        )

    def _on_send(self):
        msg = self._input_var.get().strip()
        if not msg:
            return
        self._input_var.set("")
        self._append_msg("user", msg)
        self._entry.configure(state="disabled")
        threading.Thread(target=self._worker, args=(msg,), daemon=True).start()

    def _worker(self, user_msg: str):
        try:
            cfg_snapshot = {
                k: v for k, v in asdict(self._srv).items()
                if isinstance(v, (int, float, bool, str)) and not k.endswith("_raw")
            }

            key = self._current_key()
            if key:
                prov = _PROVIDERS[self._provider_var.get()]
                # Para NVIDIA usa o modelo selecionado; OpenAI usa o padrão do provider
                model = (
                    self._nvidia_model_var.get()
                    if self._provider_var.get() == "nvidia"
                    else prov["model"]
                )
                system_prompt = (
                    "Você é um especialista em servidores ARK: Survival Evolved. "
                    "Analise as configurações do servidor abaixo e responda em português. "
                    "Seja conciso e direto.\n\n"
                    "IMPORTANTE: Todos os campos abaixo ESTÃO configurados. "
                    "Valor 1.0 significa taxa padrão vanilla (Wildcard oficial). "
                    "Valor 0.0 em multiplicadores como taming_speed_multiplier significa que a taxa está DESATIVADA — não confunda com 'não configurado'. "
                    "Quando o usuário perguntar sobre taxas, sempre liste os valores reais dos campos relevantes, mesmo que sejam 1.0.\n\n"
                    f"Config atual do servidor '{self._srv.name}':\n"
                    f"{json.dumps(cfg_snapshot, ensure_ascii=False)[:3000]}"
                )
                if not self._history:
                    self._history.append({"role": "system", "content": system_prompt})
                self._history.append({"role": "user", "content": user_msg})
                reply = _api_chat(key, prov["base_url"], model, self._history[-10:])
                self._history.append({"role": "assistant", "content": reply})
            else:
                reply = _offline_advice(cfg_snapshot, user_msg)

            self.after(0, lambda: self._append_msg("ai", reply))
        except Exception as exc:
            self.after(0, lambda: self._append_msg("system", f"[Erro: {exc}]"))
        finally:
            self.after(0, lambda: self._entry.configure(state="normal"))

    def _set_api_key(self):
        """Atalho: grava a key global (mesmo ficheiro das Configurações Globais)."""
        from ..crash_ai import load_ai_keys_dict, save_ai_keys

        prov_id  = self._provider_var.get()
        prov     = _PROVIDERS[prov_id]
        hint     = prov["key_hint"]
        prefix   = prov["key_prefix"]

        dlg = ctk.CTkInputDialog(
            text=(
                f"Cole a {prov['label']} API Key ({hint}).\n"
                "É uma configuração GLOBAL (Configurações Globais → Assistente IA)."
            ),
            title=f"API Key global — {prov['label']}",
        )
        key = dlg.get_input()
        if not key:
            return
        key = key.strip()
        if not key.startswith(prefix):
            self._append_msg("system", f"[Chave inválida — deve começar com '{prefix}']")
            return

        try:
            cur = load_ai_keys_dict()
            if prov_id == "nvidia":
                save_ai_keys(nvidia_api_key=key, openai_api_key=cur.get("openai", ""))
            else:
                save_ai_keys(nvidia_api_key=cur.get("nvidia", ""), openai_api_key=key)
            self._keys = load_ai_keys_dict()
            self._status_lbl.configure(text=self._mode_text())
            self._append_msg(
                "system",
                f"✅ Key global salva ({prov['label']}). Também editável em "
                "Configurações Globais → Assistente IA.",
            )
        except Exception as exc:
            self._append_msg("system", f"[Erro ao salvar Key: {exc}]")


def open_asm_ai_assistant(app: "ARKServerManagerApp", srv: AsmServerConfig) -> None:
    """Abre janela do assistente IA (singleton por servidor)."""
    key = f"_asm_ai_{srv.id}"
    existing = getattr(app, key, None)
    if existing and existing.winfo_exists():
        existing.lift()
        existing.focus_force()
        return
    win = _AIAssistantWindow(app, srv, app)
    setattr(app, key, win)
