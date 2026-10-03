"""Mascaramento de segredos para logs e pacotes de diagnóstico.

Tudo que sai do app (linha de log, config, INI, JSON de plugin) passa por aqui.

Para estender:

* novas palavras de chave sensível  → :func:`add_sensitive_keyword`
* novo padrão de texto livre        → :func:`add_rule`
* regras opcionais (IP, SteamID)    → :func:`enable_optional_rule` (desligadas por padrão)

A lista central é ``REDACTION_RULES`` (regras de texto, aplicadas em ordem) +
``SENSITIVE_KEYWORDS`` (nomes de chave que denunciam segredo em JSON/INI/``k=v``).
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Pattern, Union

REDACTED = "***REDACTED***"

# ── Palavras que, dentro do NOME de uma chave, indicam segredo ───────────────
# (regex; casadas sem diferenciar maiúsculas)
SENSITIVE_KEYWORDS: List[str] = [
    r"token",
    r"passw(?:or)?d",
    r"passwd",
    r"pwd",
    r"senha",
    r"secret",
    r"api[_\-]?key",
    r"apikey",
    r"webhook",
    r"authori[sz]ation",
    r"cookie",
    r"credential",
    r"private[_\-]?key",
    r"hash",
    r"signature",
    r"bearer",
]

Replacement = Union[str, Callable[[re.Match], str]]


@dataclass(frozen=True)
class RedactionRule:
    """Regra de texto livre: ``pattern`` → ``repl`` (padrão ``re.sub``)."""

    name: str
    pattern: Pattern[str]
    repl: Replacement


def _rule(name: str, pattern: str, repl: Replacement, flags: int = 0) -> RedactionRule:
    return RedactionRule(name, re.compile(pattern, flags), repl)


# ── Regras estáticas (independem de palavras-chave) ──────────────────────────
REDACTION_RULES: List[RedactionRule] = [
    # Webhook do Discord: a URL inteira é a credencial.
    _rule(
        "discord_webhook_url",
        r"https?://(?:(?:ptb|canary)\.)?discord(?:app)?\.com/api/(?:v\d+/)?webhooks/\d+/[\w\-]+",
        "https://discord.com/api/webhooks/" + REDACTED,
        re.IGNORECASE,
    ),
    # Token de bot do Discord (3 blocos base64url separados por ponto).
    _rule(
        "discord_bot_token",
        r"\b[MNO][A-Za-z0-9_\-]{23,27}\.[A-Za-z0-9_\-]{6}\.[A-Za-z0-9_\-]{27,}\b",
        REDACTED,
    ),
    # JWT.
    _rule(
        "jwt",
        r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\b",
        REDACTED,
    ),
    # Tokens de provedores conhecidos (GitHub, Slack).
    _rule(
        "provider_tokens",
        r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-[A-Za-z0-9\-]{10,})\b",
        REDACTED,
    ),
    # "Bearer <token>"
    _rule(
        "bearer",
        r"(\bbearer\s+)(?!\*\*\*REDACTED)[A-Za-z0-9\-._~+/]+=*",
        lambda m: m.group(1) + REDACTED,
        re.IGNORECASE,
    ),
    # Cabeçalhos HTTP sensíveis (linha inteira).
    _rule(
        "http_auth_headers",
        r"^([ \t]*(?:authorization|proxy-authorization|cookie|set-cookie|x-api-key)[ \t]*:[ \t]*)(?!\*\*\*REDACTED).+$",
        lambda m: m.group(1) + REDACTED,
        re.IGNORECASE | re.MULTILINE,
    ),
    # Credenciais embutidas em URL: scheme://user:senha@host
    _rule(
        "url_userinfo",
        r"(\b[a-z][a-z0-9+.\-]*://[^\s:/@\"']+:)(?!\*\*\*REDACTED)[^\s@/\"']+(@)",
        lambda m: m.group(1) + REDACTED + m.group(2),
        re.IGNORECASE,
    ),
]

# Regras opcionais — desligadas (decisão do usuário: IP/SteamID não são anonimizados
# nesta versão). Ative com enable_optional_rule("ipv4") etc.
OPTIONAL_RULES: dict[str, RedactionRule] = {
    "ipv4": _rule(
        "ipv4",
        r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b",
        "x.x.x.x",
    ),
    "steamid64": _rule("steamid64", r"\b7656119\d{10}\b", "7656119XXXXXXXXXX"),
}

_enabled_optional: List[str] = []
_lock = threading.RLock()
_compiled_cache: Optional[List[RedactionRule]] = None
_key_re_cache: Optional[Pattern[str]] = None


def _invalidate() -> None:
    global _compiled_cache, _key_re_cache
    _compiled_cache = None
    _key_re_cache = None


def add_sensitive_keyword(pattern: str) -> None:
    """Adiciona uma palavra (regex) que marca nomes de chave como sensíveis."""
    with _lock:
        if pattern not in SENSITIVE_KEYWORDS:
            SENSITIVE_KEYWORDS.append(pattern)
            _invalidate()


def add_rule(name: str, pattern: str, repl: Replacement = REDACTED,
             flags: int = 0, *, first: bool = False) -> None:
    """Registra uma regra de texto livre (``first=True`` → antes das existentes)."""
    rule = _rule(name, pattern, repl, flags)
    with _lock:
        if first:
            REDACTION_RULES.insert(0, rule)
        else:
            REDACTION_RULES.append(rule)
        _invalidate()


def enable_optional_rule(name: str) -> None:
    with _lock:
        if name not in OPTIONAL_RULES:
            raise KeyError(f"Regra opcional desconhecida: {name}")
        if name not in _enabled_optional:
            _enabled_optional.append(name)
            _invalidate()


def disable_optional_rule(name: str) -> None:
    with _lock:
        if name in _enabled_optional:
            _enabled_optional.remove(name)
            _invalidate()


def _keywords_alt() -> str:
    return "|".join(f"(?:{k})" for k in SENSITIVE_KEYWORDS)


def _key_regex() -> Pattern[str]:
    global _key_re_cache
    with _lock:
        if _key_re_cache is None:
            _key_re_cache = re.compile(_keywords_alt(), re.IGNORECASE)
        return _key_re_cache


def _keyword_rules() -> List[RedactionRule]:
    """Regras que dependem de ``SENSITIVE_KEYWORDS`` (JSON, dict-repr, INI/env, k=v)."""
    kw = _keywords_alt()
    return [
        # JSON:  "api_key": "valor"   (mantém aspas → continua JSON válido)
        _rule(
            "json_pair",
            r'("[^"\n]*(?:' + kw + r')[^"\n]*"[ \t]*:[ \t]*)(?!"")(?!"?\*\*\*REDACTED)'
            r'("(?:[^"\\\n]|\\.)*"|[^\s,}\]{\["]+)',
            lambda m: m.group(1) + (
                '"' + REDACTED + '"'
                if m.group(2).lower() not in ("true", "false", "null") else m.group(2)
            ),
            re.IGNORECASE,
        ),
        # dict-repr do Python:  'api_key': 'valor'
        _rule(
            "pydict_pair",
            r"('[^'\n]*(?:" + kw + r")[^'\n]*'[ \t]*:[ \t]*)(?!'')(?!'?\*\*\*REDACTED)"
            r"('(?:[^'\\\n]|\\.)*'|[^\s,}\]{\['\"]+)",
            lambda m: m.group(1) + (
                "'" + REDACTED + "'"
                if m.group(2).lower() not in ("true", "false", "none") else m.group(2)
            ),
            re.IGNORECASE,
        ),
        # Linha INI/env/yaml:  ServerAdminPassword=abc   |   discord_token: abc
        _rule(
            "line_key_value",
            r'^([ \t]*["\']?[\w.\-\[\]]*(?:' + kw + r')[\w.\-\[\]]*["\']?[ \t]*[=:])'
            r'(?![ \t]*(?:[ \t\r]*$|["\']?\*\*\*REDACTED|["\']{2}[ \t,;\r]*$'
            r'|(?:true|false|null|none)[ \t,;\r]*$))'
            r'([ \t]*)(.+?)([ \t,;\r]*)$',
            lambda m: m.group(1) + m.group(2) + REDACTED + m.group(4),
            re.IGNORECASE | re.MULTILINE,
        ),
        # Inline  chave=valor  (linhas de comando ?ServerPassword=x, query string, logs)
        _rule(
            "inline_key_value",
            r'\b([\w.\-]*(?:' + kw + r')[\w.\-]*)([ \t]*=[ \t]*)(?!\*\*\*REDACTED)'
            r'("[^"]*"|\'[^\']*\'|[^\s?&"\';,]+)',
            lambda m: m.group(1) + m.group(2) + REDACTED,
            re.IGNORECASE,
        ),
        # Inline  password: valor  (mensagens livres)
        _rule(
            "inline_colon",
            r"\b(passw(?:or)?d|passwd|senha|secret|token|api[_\-\s]?key)([ \t]*:[ \t]+)"
            r"(?!\*\*\*REDACTED)(?!(?:true|false|null|none|vazi[oa]|empty)\b)(\S+)",
            lambda m: m.group(1) + m.group(2) + REDACTED,
            re.IGNORECASE,
        ),
    ]


def _all_rules() -> List[RedactionRule]:
    global _compiled_cache
    with _lock:
        if _compiled_cache is None:
            rules = list(REDACTION_RULES) + _keyword_rules()
            rules += [OPTIONAL_RULES[n] for n in _enabled_optional]
            _compiled_cache = rules
        return _compiled_cache


# ─────────────────────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────────────────────

def is_sensitive_key(key: Any) -> bool:
    """True se o NOME da chave denuncia um segredo (``rcon_password``, ``ApiKey``…)."""
    if not isinstance(key, str) or not key:
        return False
    return _key_regex().search(key) is not None


def redact_text(text: Any) -> str:
    """Mascara segredos em texto livre (logs, INI, JSON em texto, linhas de comando)."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    if not text:
        return text
    for rule in _all_rules():
        try:
            text = rule.pattern.sub(rule.repl, text)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001 — regra defeituosa nunca derruba o log
            continue
    return text


def _mask_scalar(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str) and not value.strip():
        return value  # vazio continua vazio (diagnóstico: «senha em branco»)
    return REDACTED


def _mask_all(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _mask_all(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_mask_all(v) for v in value]
    return _mask_scalar(value)


def redact_obj(obj: Any) -> Any:
    """Devolve cópia de ``obj`` (dict/list/str…) com segredos mascarados.

    * valores de chaves sensíveis viram ``***REDACTED***`` (vazios e booleanos ficam);
    * demais strings passam por :func:`redact_text` (URLs com senha, tokens soltos…).
    """
    if isinstance(obj, dict):
        out: dict = {}
        for k, v in obj.items():
            if is_sensitive_key(k):
                out[k] = _mask_all(v)
            else:
                out[k] = redact_obj(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [redact_obj(v) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj)
    return obj


def redact_ini_text(text: str) -> str:
    """Alias semântico para INI (``ServerPassword=…``, ``RCONPassword=…``)."""
    return redact_text(text)
