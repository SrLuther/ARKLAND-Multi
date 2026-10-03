"""Lógica pura dos cogs (sem discord.py) — testável sem conectar ao Discord."""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Pattern, Sequence

# ── Moderação ────────────────────────────────────────────────────────────────

# Lista inicial de palavrões (mesma do palavroes.txt do projeto original).
# Gravada em <dados>/palavroes.txt na primeira execução; o admin pode editar o arquivo.
DEFAULT_BADWORDS: Sequence[str] = (
    "merda", "caralho", "puta", "foda", "bosta", "cu", "idiota", "burro",
    "cabrão", "viado", "otário", "babaca", "fodido", "gostosa", "chifrudo",
    "vagabundo", "desgraçado", "imbecil", "safado", "palhaço", "arrombado",
    "pnc", "tnc", "fudido",
)

# Convites do Discord (regex pré-compilada, igual ao cog original).
INVITE_REGEX: Pattern[str] = re.compile(r"(discord\.gg/|discord\.com/invite/)", re.IGNORECASE)

VIOLATION_INVITE = "invite"
VIOLATION_BADWORD = "badword"


def parse_badwords(text: str) -> List[str]:
    """Uma palavra por linha → minúsculas, sem vazios, sem duplicadas (ordem preservada)."""
    seen: set[str] = set()
    words: List[str] = []
    for raw in (text or "").splitlines():
        w = raw.strip().lower()
        if w and w not in seen:
            seen.add(w)
            words.append(w)
    return words


def compile_badwords(words: Iterable[str]) -> Optional[Pattern[str]]:
    """Regex com word boundaries (``\\b(...)\\b``) ou ``None`` se não houver palavras."""
    cleaned = [w.strip().lower() for w in words if w and w.strip()]
    if not cleaned:
        return None
    pattern = "|".join(re.escape(w) for w in cleaned)
    return re.compile(r"\b(" + pattern + r")\b", re.IGNORECASE)


def classify_message(
    content: str,
    badwords_regex: Optional[Pattern[str]],
    invite_regex: Pattern[str] = INVITE_REGEX,
) -> Optional[str]:
    """Convite tem prioridade sobre palavrão (ordem do cog original)."""
    text = content or ""
    if invite_regex.search(text):
        return VIOLATION_INVITE
    if badwords_regex is not None and badwords_regex.search(text):
        return VIOLATION_BADWORD
    return None


def limpezageral_limit_ok(limite: int) -> bool:
    return 1 <= limite <= 1000


# ── Salas de voz ─────────────────────────────────────────────────────────────

VOICE_USER_LIMIT = 10


def temp_channel_name(display_name: str) -> str:
    return f"Sala de 🗣️ {display_name}"


def should_delete_temp_channel(
    channel_id: int,
    lobby_id: int,
    tracked: Dict[int, int],
    member_count: int,
) -> bool:
    """Canal temporário rastreado, que não é o lobby e ficou vazio."""
    return channel_id != lobby_id and channel_id in tracked and member_count == 0


def is_lobby_join(after_channel_id: Optional[int], lobby_id: int) -> bool:
    return bool(lobby_id) and after_channel_id is not None and after_channel_id == lobby_id


# ── Administração ────────────────────────────────────────────────────────────

# Nome digitado no Discord → módulo dentro de ``src.discord_bot``.
EXTENSION_ALIASES: Dict[str, str] = {
    "voicemanager": "voice_manager",
    "voice_manager": "voice_manager",
    "voz": "voice_manager",
    "moderation": "moderation",
    "moderacao": "moderation",
    "admin": "admin",
}
AVAILABLE_COGS = ("voicemanager", "moderation", "admin")


def resolve_extension_module(cog_name: str, package: str) -> Optional[str]:
    """Módulo completo da extensão ou ``None`` se o nome não for um dos 3 cogs."""
    key = (cog_name or "").strip().lower().removesuffix(".py")
    module = EXTENSION_ALIASES.get(key)
    return f"{package}.{module}" if module else None


def reaction_confirmed(emoji: str) -> bool:
    return str(emoji) == "✅"
