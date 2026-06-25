"""Configuração e helpers do painel Broadcasts TEK."""
from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp

from ..config_manager import BroadcastTekConfig
from .broadcast_profile_io import get_library


def get_settings(app: "ARKServerManagerApp") -> BroadcastTekConfig:
    cfg = getattr(app.config_manager.config, "broadcast_tek", None)
    if not isinstance(cfg, BroadcastTekConfig):
        return BroadcastTekConfig()
    return cfg


def save_settings(app: "ARKServerManagerApp", settings: BroadcastTekConfig) -> None:
    app.config_manager.config.broadcast_tek = settings
    app.config_manager.save()


def all_server_ids(app: "ARKServerManagerApp") -> list[str]:
    return [s.id for s in app.asm_config_manager.servers]


def resolve_target_server_ids(app: "ARKServerManagerApp") -> list[str]:
    """IDs de servidores marcados para envio (vazio na config = todos)."""
    settings = get_settings(app)
    all_ids = all_server_ids(app)
    if not all_ids:
        return []
    if not settings.target_server_ids:
        return all_ids
    allowed = set(settings.target_server_ids)
    return [sid for sid in all_ids if sid in allowed]


def resolve_rotation_messages(app: "ARKServerManagerApp") -> list[dict[str, Any]]:
    """Mensagens da biblioteca incluídas no ciclo automático."""
    lib = get_library(app)
    if not lib:
        return []
    settings = get_settings(app)
    if not settings.enabled_message_ids:
        return lib
    allowed = set(settings.enabled_message_ids)
    return [e for e in lib if str(e.get("id")) in allowed]


def pick_next_message(app: "ARKServerManagerApp") -> tuple[dict[str, Any] | None, int]:
    """Escolhe próxima mensagem e novo índice de rotação."""
    pool = resolve_rotation_messages(app)
    if not pool:
        return None, 0

    settings = get_settings(app)
    if settings.random_order:
        return random.choice(pool), settings.rotation_index

    idx = settings.rotation_index % len(pool)
    next_index = (idx + 1) % len(pool)
    return pool[idx], next_index


def seconds_until_next(settings: BroadcastTekConfig, *, active: bool | None = None) -> int:
    if active is None:
        active = settings.scheduler_enabled
    if not active:
        return 0
    interval = max(1, int(settings.interval_minutes)) * 60
    elapsed = time.time() - float(settings.last_sent_at or 0)
    remaining = int(interval - elapsed)
    return max(0, remaining)


def format_countdown(seconds: int) -> str:
    if seconds <= 0:
        return "agora"
    mins, secs = divmod(seconds, 60)
    if mins >= 60:
        hrs, mins = divmod(mins, 60)
        return f"{hrs}h {mins:02d}m"
    if mins:
        return f"{mins}m {secs:02d}s"
    return f"{secs}s"
