"""Configuração do bot embutido (sem dependência de discord.py).

Os valores vêm de ``AppConfig.obobonic`` (config.json do app). O token é guardado
no mesmo ``config.json`` onde o app já guarda os demais segredos (``discord_bot.token``,
``remote_agent_token``, ``smtp.password`` …) e NUNCA deve ser escrito em logs.
"""
from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple
from urllib import error as urllib_error
from urllib import request as urllib_request

DEFAULT_PREFIX = "!"

# Bits de permissão do Discord usados pelos três cogs (ver Permissions do discord.py).
PERMISSION_BITS = {
    "add_reactions": 1 << 6,        # !restart / !shutdown pedem confirmação por reação
    "manage_channels": 1 << 4,      # criar/excluir salas de voz temporárias
    "view_channel": 1 << 10,
    "send_messages": 1 << 11,
    "manage_messages": 1 << 13,     # !faxina / !limpar / filtros
    "embed_links": 1 << 14,         # embeds de log/admin
    "read_message_history": 1 << 16,
    "connect": 1 << 20,
    "mute_members": 1 << 22,        # overwrite concedido ao dono da sala de voz
    "deafen_members": 1 << 23,
    "move_members": 1 << 24,        # mover membro para a sala nova
    "manage_roles": 1 << 28,        # quarentena (!limpezageral)
}

_TOKEN_PLACEHOLDERS = frozenset({
    "",
    "token_falso_para_dev",
    "seu_token_aqui",
    "discord_token",
    "xxx",
})


def compute_invite_permissions() -> int:
    """Soma das permissões que os três cogs realmente precisam."""
    total = 0
    for bit in PERMISSION_BITS.values():
        total |= bit
    return total


def mask_secret(value: str, visible: int = 4) -> str:
    """Mascara valor sensível para exibição na UI."""
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) <= visible * 2:
        return "*" * len(v)
    return v[:visible] + "…" + v[-visible:]


def redact(text: str, *secrets: str) -> str:
    """Remove segredos de uma linha de log."""
    out = text
    for secret in secrets:
        s = (secret or "").strip()
        if len(s) >= 8:
            out = out.replace(s, "***")
    return out


def validate_token_value(token: str) -> Tuple[bool, str]:
    """Valida o formato do token do bot (sem contactar o Discord)."""
    tok = (token or "").strip()
    if not tok:
        return False, "Token do bot ausente."
    if tok.lower() in _TOKEN_PLACEHOLDERS or len(tok) < 20:
        return False, "Token inválido ou placeholder."
    if tok.count(".") < 2:
        return False, "Token parece malformado (formato Discord esperado)."
    return True, "Token Discord OK"


def discord_app_id_from_token(token: str) -> Optional[str]:
    """Extrai o Application/Client ID do token (primeiro segmento em base64)."""
    try:
        part = (token or "").strip().split(".")[0]
        padded = part + "=" * (-len(part) % 4)
        raw = base64.b64decode(padded)
        return str(int(raw.decode("utf-8")))
    except (ValueError, OSError, UnicodeDecodeError):
        return None


def resolve_client_id(token: str, client_id: str = "") -> Optional[str]:
    """Client ID explícito (se numérico) ou derivado do token."""
    cid = (client_id or "").strip()
    if cid.isdigit():
        return cid
    return discord_app_id_from_token(token)


def discord_developer_url(token: str, client_id: str = "") -> str:
    cid = resolve_client_id(token, client_id)
    if cid:
        return f"https://discord.com/developers/applications/{cid}/bot"
    return "https://discord.com/developers/applications"


def discord_invite_url(
    token: str,
    client_id: str = "",
    permissions: Optional[int] = None,
) -> Optional[str]:
    """Link de convite com as permissões dos três cogs (scope ``bot``)."""
    cid = resolve_client_id(token, client_id)
    if not cid:
        return None
    perms = compute_invite_permissions() if permissions is None else int(permissions)
    return (
        "https://discord.com/oauth2/authorize"
        f"?client_id={cid}&permissions={perms}&scope=bot"
    )


def parse_discord_id(value: Any) -> int:
    """ID numérico tolerante (aceita espaços, vazio, lixo → 0)."""
    if value is None:
        return 0
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value if value > 0 else 0
    text = str(value).strip()
    return int(text) if text.isdigit() else 0


def default_data_dir() -> Path:
    """Pasta de dados do bot, dentro do próprio app."""
    return Path(os.environ.get("APPDATA", Path.home())) / "ARKLAND-ServerManager" / "obobonic"


@dataclass(frozen=True)
class BotSettings:
    """Snapshot imutável das configurações usadas numa execução do bot."""

    token: str
    data_dir: Path
    guild_id: int = 0
    lobby_channel_id: int = 0
    logs_channel_id: int = 0
    quarantine_role_id: int = 0
    validation_channel_id: int = 0
    validation_role_id: int = 0
    command_prefix: str = DEFAULT_PREFIX
    enable_voice: bool = True
    enable_moderation: bool = True

    @classmethod
    def from_config(cls, cfg: Any, data_dir: Optional[Path] = None) -> "BotSettings":
        prefix = (getattr(cfg, "command_prefix", "") or "").strip() or DEFAULT_PREFIX
        return cls(
            token=(getattr(cfg, "token", "") or "").strip(),
            data_dir=Path(data_dir) if data_dir else default_data_dir(),
            guild_id=parse_discord_id(getattr(cfg, "guild_id", "")),
            lobby_channel_id=parse_discord_id(getattr(cfg, "lobby_channel_id", "")),
            logs_channel_id=parse_discord_id(getattr(cfg, "logs_channel_id", "")),
            quarantine_role_id=parse_discord_id(getattr(cfg, "quarantine_role_id", "")),
            validation_channel_id=parse_discord_id(getattr(cfg, "validation_channel_id", "")),
            validation_role_id=parse_discord_id(getattr(cfg, "validation_role_id", "")),
            command_prefix=prefix,
            enable_voice=bool(getattr(cfg, "enable_voice", True)),
            enable_moderation=bool(getattr(cfg, "enable_moderation", True)),
        )
    def problems(self) -> List[str]:
        """Pendências bloqueantes (impedem iniciar)."""
        out: List[str] = []
        ok, msg = validate_token_value(self.token)
        if not ok:
            out.append(msg)
        return out

    def warnings(self) -> List[str]:
        """Avisos não bloqueantes."""
        out: List[str] = []
        if self.enable_voice and not self.lobby_channel_id:
            out.append("Lobby de voz não configurado — salas temporárias desativadas.")
        if self.enable_moderation and not self.logs_channel_id:
            out.append("Canal de logs não configurado — moderação não registrará logs.")
        if self.enable_moderation and not self.quarantine_role_id:
            out.append("Cargo de quarentena não configurado — !limpezageral não isola o usuário.")
        return out
@dataclass(frozen=True)
class DiscordLinkValidationResult:
    ok: bool
    status_code: int
    message: str
    steam_id: str = ""
    discord_user_id: str = ""
    first_link_bonus: int = 0


class DiscordLinkValidatorClient:
    """Cliente HTTP simples para confirmar código de vínculo no backend da loja."""

    def __init__(self, *, base_url: str, api_key: str, timeout_seconds: float = 8.0) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = (api_key or "").strip()
        self.timeout_seconds = max(1.0, float(timeout_seconds or 8.0))

    @classmethod
    def from_env(cls) -> "DiscordLinkValidatorClient":
        base_url = (
            os.environ.get("ARKSHOP_WEB_URL", "")
            or os.environ.get("ARKSHOP_WEBSTORE_URL", "")
            or os.environ.get("ARKLAND_WEB_URL", "")
            or "http://127.0.0.1:27199"
        )
        api_key = os.environ.get("ARKSHOP_API_KEY", "")
        return cls(base_url=base_url, api_key=api_key)

    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def confirm_code(
        self,
        *,
        code: str,
        discord_user_id: str,
        discord_username: str,
    ) -> DiscordLinkValidationResult:
        if not self.configured():
            return DiscordLinkValidationResult(
                ok=False,
                status_code=0,
                message="Integração não configurada (ARKSHOP_WEB_URL/ARKSHOP_API_KEY).",
            )

        endpoint = f"{self.base_url}/api/internal/tickets/discord-link/confirm"
        payload = {
            "code": (code or "").strip(),
            "discord_user_id": (discord_user_id or "").strip(),
            "discord_username": (discord_username or "").strip(),
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib_request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": self.api_key,
            },
        )

        try:
            with urllib_request.urlopen(req, timeout=self.timeout_seconds) as resp:
                status_code = int(getattr(resp, "status", 200) or 200)
                raw = resp.read().decode("utf-8", errors="replace")
                data = json.loads(raw or "{}") if raw else {}
                ok = bool(data.get("ok"))
                return DiscordLinkValidationResult(
                    ok=ok,
                    status_code=status_code,
                    message=str(data.get("error") or data.get("message") or ("OK" if ok else "Falha")),
                    steam_id=str(data.get("steam_id") or ""),
                    discord_user_id=str(data.get("discord_user_id") or payload["discord_user_id"]),
                    first_link_bonus=int(data.get("first_link_bonus") or 0),
                )
        except urllib_error.HTTPError as exc:
            status_code = int(exc.code or 0)
            try:
                raw = exc.read().decode("utf-8", errors="replace")
                data = json.loads(raw or "{}") if raw else {}
                message = str(data.get("error") or data.get("message") or "Falha na validação")
            except Exception:
                message = f"Falha na validação (HTTP {status_code})."
            return DiscordLinkValidationResult(
                ok=False,
                status_code=status_code,
                message=message,
            )
        except Exception as exc:
            return DiscordLinkValidationResult(
                ok=False,
                status_code=0,
                message=f"Falha de comunicação com web store: {exc}",
            )

_ID_RE = re.compile(r"^\d{5,25}$")

def is_valid_discord_id(value: str) -> bool:
    """True para vazio (opcional) ou um snowflake plausível."""
    v = (value or "").strip()
    return not v or bool(_ID_RE.match(v))
