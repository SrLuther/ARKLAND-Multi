"""Fachada do bot Discord oBobonic EMBUTIDO (administração, moderação e salas de voz).

Antes o app supervisionava um projeto externo (pasta com bot.py/.env/Python). Agora o bot
roda dentro do próprio app — veja ``src/discord_bot/`` — e este módulo só liga a config
do app (``AppConfig.obobonic``) ao ``EmbeddedBotRunner``.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from .discord_bot.runner import (  # noqa: F401  (re-export para UI/testes)
    STATE_ERROR,
    STATE_ONLINE,
    STATE_RESTARTING,
    STATE_STARTING,
    STATE_STOPPED,
    STATE_STOPPING,
    EmbeddedBotRunner,
    RunnerStatus,
)
from .discord_bot.settings import (  # noqa: F401  (re-export para UI/testes)
    BotSettings,
    compute_invite_permissions,
    default_data_dir,
    discord_app_id_from_token,
    discord_developer_url,
    discord_invite_url,
    is_valid_discord_id,
    mask_secret,
    validate_token_value,
)

_log = logging.getLogger(__name__)

_RUNNER_ATTR = "_obobonic_runner"

# Campos de texto editáveis no painel (ordem de exibição).
TEXT_FIELDS: Tuple[str, ...] = (
    "token", "client_id", "guild_id", "command_prefix",
    "lobby_channel_id", "logs_channel_id", "quarantine_role_id",
)
_ID_FIELDS = ("client_id", "guild_id", "lobby_channel_id", "logs_channel_id", "quarantine_role_id")
_FIELD_LABELS = {
    "token": "Token do bot",
    "client_id": "Client ID",
    "guild_id": "ID do servidor",
    "command_prefix": "Prefixo",
    "lobby_channel_id": "Lobby de voz",
    "logs_channel_id": "Canal de logs",
    "quarantine_role_id": "Cargo de quarentena",
}


# ── Runner (singleton por app) ───────────────────────────────────────────────
def get_runner(app: Any) -> EmbeddedBotRunner:
    """Runner único por app (sobrevive a reconstruções do painel)."""
    runner = getattr(app, _RUNNER_ATTR, None)
    if runner is None:
        runner = EmbeddedBotRunner()
        setattr(app, _RUNNER_ATTR, runner)
    return runner


def live_config(app: Any) -> Any:
    """Config ATUAL do bot (sempre relida de ``app.config_manager.config``).

    Nunca guardar esta referência em closures de longa duração: se o ConfigManager
    recarregar o config, uma referência antiga ficaria "solta" e as opções marcadas
    no painel deixariam de ser persistidas.
    """
    return app.config_manager.config.obobonic


# ── Persistência das opções do painel ────────────────────────────────────────
def save_panel_options(config_manager: Any, *, auto_start: bool, auto_restart_on_crash: bool) -> None:
    """Grava as caixas do painel (estado marcado E desmarcado). Propaga erro de I/O."""
    cfg = config_manager.config.obobonic
    previous = (cfg.auto_start, cfg.auto_restart_on_crash)
    cfg.auto_start = bool(auto_start)
    cfg.auto_restart_on_crash = bool(auto_restart_on_crash)
    try:
        config_manager.save()
    except Exception:
        # memória deve refletir o que está no disco, para a UI poder reverter
        cfg.auto_start, cfg.auto_restart_on_crash = previous
        raise


def validate_bot_fields(values: Dict[str, str]) -> List[str]:
    """Erros (pt-BR) dos campos de texto do painel. Lista vazia = válido."""
    errors: List[str] = []
    token = (values.get("token") or "").strip()
    if token:
        ok, msg = validate_token_value(token)
        if not ok:
            errors.append(f"{_FIELD_LABELS['token']}: {msg}")
    for key in _ID_FIELDS:
        if not is_valid_discord_id(values.get(key, "")):
            errors.append(f"{_FIELD_LABELS[key]}: use somente números (ID do Discord).")
    prefix = (values.get("command_prefix") or "").strip()
    if values.get("command_prefix") is not None and (not prefix or len(prefix) > 5 or " " in prefix):
        errors.append(f"{_FIELD_LABELS['command_prefix']}: 1 a 5 caracteres, sem espaços.")
    return errors


def save_bot_fields(
    config_manager: Any,
    values: Dict[str, str],
    *,
    enable_voice: Optional[bool] = None,
    enable_moderation: Optional[bool] = None,
) -> List[str]:
    """Valida e grava os campos do bot. Retorna os erros (nada é gravado se houver)."""
    errors = validate_bot_fields(values)
    if errors:
        return errors
    cfg = config_manager.config.obobonic
    for key in TEXT_FIELDS:
        if key in values:
            setattr(cfg, key, (values[key] or "").strip())
    if enable_voice is not None:
        cfg.enable_voice = bool(enable_voice)
    if enable_moderation is not None:
        cfg.enable_moderation = bool(enable_moderation)
    config_manager.save()
    return []


# ── Ciclo de vida ────────────────────────────────────────────────────────────
def start_embedded_bot(app: Any) -> Tuple[bool, str]:
    """Inicia o bot embutido com a config atual do app."""
    cfg = live_config(app)
    settings = BotSettings.from_config(cfg)
    runner = get_runner(app)
    return runner.start(settings, auto_restart=cfg.auto_restart_on_crash)


def restart_embedded_bot(app: Any) -> Tuple[bool, str]:
    cfg = live_config(app)
    settings = BotSettings.from_config(cfg)
    return get_runner(app).restart(settings, auto_restart=cfg.auto_restart_on_crash)


def shutdown_obobonic_for_app(app: Any) -> None:
    """Para o bot embutido ao fechar o app (sem processos externos para limpar)."""
    runner = getattr(app, _RUNNER_ATTR, None)
    if runner is None:
        return
    try:
        runner.shutdown()
    except Exception:
        _log.debug("shutdown_obobonic_for_app falhou", exc_info=True)
