"""
Análise automática de crashes com a IA integrada (NVIDIA NIM / OpenAI).

Quando um crash é detectado:
  1. Heurística local (crash_parser) preenche diagnosis imediata
  2. Este módulo, em background, chama a API (se houver key) com
     call stack + cauda do ShooterGame.log e actualiza o CrashStore

Sem API key: melhora o texto heurístico com contexto extra do log
(em vez de ficar só em «Causa não identificada»).
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("arkland.crash_ai")

_ANALYZING = "🤖 IA a analisar o crash… aguarde alguns segundos."
_GENERIC = "Causa não identificada. Consulte o call stack e o ShooterGame.log para mais detalhes."
_LOCK = threading.Lock()
_IN_FLIGHT: set[str] = set()


def _creds_path() -> Path:
    return (
        Path(os.environ.get("APPDATA", Path.home()))
        / "ARKLAND-ServerManager"
        / "cloud_credentials.json"
    )


def load_ai_credentials() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Devolve (provider_id, api_key, model) ou (None, None, None)."""
    try:
        path = _creds_path()
        if not path.exists():
            return None, None, None
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None, None, None

    nvidia = str(data.get("nvidia_api_key") or "").strip()
    openai = str(data.get("openai_api_key") or "").strip()
    if nvidia.startswith("nvapi-"):
        return (
            "nvidia",
            nvidia,
            str(data.get("nvidia_crash_model") or "meta/llama-3.3-70b-instruct"),
        )
    if openai.startswith("sk-"):
        return "openai", openai, "gpt-4o-mini"
    return None, None, None


def _provider_endpoint(provider: str) -> str:
    if provider == "openai":
        return "https://api.openai.com/v1"
    return "https://integrate.api.nvidia.com/v1"


def read_shootergame_context(install_dir: str, *, max_chars: int = 6000) -> str:
    """Lê a cauda do ShooterGame.log centrada no último Fatal error!."""
    candidates = [
        Path(install_dir) / "ShooterGame" / "Saved" / "Logs" / "ShooterGame.log",
        Path(install_dir) / "Saved" / "Logs" / "ShooterGame.log",
    ]
    log_file = next((p for p in candidates if p.exists()), None)
    if not log_file:
        return ""
    try:
        size = log_file.stat().st_size
        # Até ~256 KB de cauda — Fatal error + erros anteriores.
        with open(log_file, "rb") as fh:
            fh.seek(max(0, size - 262_144))
            text = fh.read().decode("utf-8", errors="replace")
    except Exception as exc:
        log.debug("read_shootergame_context failed: %s", exc)
        return ""

    idx = text.rfind("Fatal error!")
    if idx < 0:
        return text[-max_chars:]
    start = max(0, idx - 3500)
    end = min(len(text), idx + 4500)
    return text[start:end][-max_chars:]


def _offline_enriched_diagnosis(
    *,
    culprit: str,
    log_tail: List[str],
    log_context: str,
) -> str:
    """Heurística mais útil quando não há API key ou a IA falha."""
    blob = "\n".join(log_tail) + "\n" + (log_context or "")
    low = blob.lower()
    tips: List[str] = []

    if culprit:
        tips.append(f"Módulo suspeito no stack: **{culprit}**.")
    if "out of memory" in low or "llmalloc" in low or "ran out of memory" in low:
        tips.append("Indícios de falta de RAM — reduza mods/players ou aumente memória.")
    if "access violation" in low or "0xc0000005" in low:
        tips.append("Access violation — tipicamente plugin/mod incompatível com a build do servidor.")
    if "libmariadb" in low or "libmysql" in low or "mysql" in low:
        tips.append("Falha relacionada a MariaDB/MySQL — verifique DLL e ligação à base.")
    if "customshop" in low:
        tips.append("CustomShop aparece no contexto — confirme versão do plugin vs ArkApi.")
    if "assertion" in low or "ensure(" in low:
        tips.append("Assertion/Ensure do Unreal — dados/save ou mod a violar invariantes do engine.")
    if re.search(r"mod[_\s-]?id|steamworkshop|content/mods", low):
        tips.append("Há referências a mods — teste arranque sem o último mod adicionado.")

    # Linhas Error/Warning imediatamente antes do Fatal
    pre_errors = []
    for ln in (log_context or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        if re.search(r"\berror\b|\bwarning\b|\bfatal\b|\bexception\b", s, re.I):
            if "fatal error!" in s.lower() and len(s) < 20:
                continue
            pre_errors.append(s[:180])
    pre_errors = pre_errors[-4:]

    if not tips and not pre_errors and (not log_tail or all(
        ln.strip().lower() in ("fatal error!", "fatal error") for ln in log_tail
    )):
        return (
            "Crash fatal sem call stack útil no registo. "
            "Isto costuma acontecer quando o processo morre antes do UE4 gravar o stack "
            "(kill externo, OOM do SO, antivírus, ou crash no arranque). "
            "Abra ShooterGame.log e procure Error/Warning nos segundos antes do Fatal error!; "
            "confirme RAM livre, integridade dos ficheiros Steam e o último plugin/mod alterado."
        )

    parts = ["Análise local (sem API key de IA ou IA indisponível):"]
    parts.extend(f"• {t}" for t in tips)
    if pre_errors:
        parts.append("Trechos relevantes do log:")
        parts.extend(f"  – {e}" for e in pre_errors)
    if not tips:
        parts.append(
            "• Sem padrão conhecido no extracto — priorize ShooterGame.log completo e "
            "a pasta Saved/Crashes (se existir .dmp/.crashstack)."
        )
    return "\n".join(parts)


def _build_prompt(
    *,
    server_name: str,
    kind: str,
    culprit: str,
    heuristic: str,
    log_tail: List[str],
    log_context: str,
) -> List[Dict[str, str]]:
    stack = "\n".join(log_tail[:40]) if log_tail else "(vazio)"
    ctx = log_context or "(ShooterGame.log indisponível)"
    user = (
        f"Servidor ARK ASE: {server_name}\n"
        f"Tipo: {kind}\n"
        f"Culprit heurístico: {culprit or '(nenhum)'}\n"
        f"Diagnóstico heurístico prévio: {heuristic or '(nenhum)'}\n\n"
        f"Call stack / extracto curto:\n{stack}\n\n"
        f"Contexto ShooterGame.log (à volta do Fatal error!):\n{ctx}\n\n"
        "Explica a causa mais provável em português (Brasil/Portugal), 5–10 linhas, "
        "com passos práticos de mitigação. Se o stack for só 'Fatal error!', "
        "usa o contexto do log e diz o que falta para confirmar."
    )
    system = (
        "És especialista em crashes de servidores ARK: Survival Evolved (ASE) "
        "com ArkApi/plugins. Responde em português, objectivo e técnico. "
        "Não inventes DLLs que não apareçam no texto. "
        "Se a evidência for fraca, declara incerteza e lista hipóteses ordenadas."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _call_llm(provider: str, api_key: str, model: str, messages: List[Dict[str, str]]) -> str:
    from .asm_ui.asm_ai_assistant import _api_chat

    reply = _api_chat(api_key, _provider_endpoint(provider), model, messages)
    if not reply or reply.startswith("[Erro"):
        raise RuntimeError(reply or "resposta vazia")
    return reply.strip()


def needs_ai_upgrade(diagnosis: str) -> bool:
    """True se o texto actual ainda é genérico / placeholder."""
    d = (diagnosis or "").strip()
    if not d:
        return True
    if d.startswith("🤖 IA a analisar"):
        return True
    if d.startswith(_GENERIC) or d == _GENERIC:
        return True
    if "Causa não identificada" in d and "🤖 IA:" not in d:
        return True
    return False


def schedule_crash_ai_analysis(
    event_id: str,
    *,
    server_name: str,
    install_dir: str,
    kind: str,
    culprit: str,
    log_tail: List[str],
    heuristic_diagnosis: str,
) -> None:
    """Agenda análise em background; actualiza CrashStore.diagnosis."""
    with _LOCK:
        if event_id in _IN_FLIGHT:
            return
        _IN_FLIGHT.add(event_id)

    def _run() -> None:
        try:
            from .crash_store import CrashStore

            store = CrashStore.instance()
            # Placeholder imediato se ainda for genérico
            if needs_ai_upgrade(heuristic_diagnosis):
                store.update_diagnosis(event_id, _ANALYZING)

            ctx = read_shootergame_context(install_dir)
            provider, key, model = load_ai_credentials()
            if provider and key and model:
                try:
                    messages = _build_prompt(
                        server_name=server_name,
                        kind=kind,
                        culprit=culprit,
                        heuristic=heuristic_diagnosis,
                        log_tail=list(log_tail or []),
                        log_context=ctx,
                    )
                    reply = _call_llm(provider, key, model, messages)
                    store.update_diagnosis(event_id, f"🤖 IA ({provider}):\n{reply}")
                    return
                except Exception as exc:
                    log.warning("crash AI LLM failed: %s", exc)

            enriched = _offline_enriched_diagnosis(
                culprit=culprit,
                log_tail=list(log_tail or []),
                log_context=ctx,
            )
            store.update_diagnosis(event_id, enriched)
        except Exception as exc:
            log.warning("schedule_crash_ai_analysis failed: %s", exc)
            try:
                from .crash_store import CrashStore

                CrashStore.instance().update_diagnosis(
                    event_id,
                    heuristic_diagnosis or _GENERIC,
                )
            except Exception:
                pass
        finally:
            with _LOCK:
                _IN_FLIGHT.discard(event_id)

    threading.Thread(target=_run, name=f"crash-ai-{event_id[:8]}", daemon=True).start()
