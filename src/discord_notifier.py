"""
src/discord_notifier.py
Envio de notificações Discord via webhook.

Usa apenas stdlib (urllib) — sem dependências externas.
Fire-and-forget: cada envio ocorre em thread separada, nunca bloqueia a UI.
"""
from __future__ import annotations

import json
import logging
import threading
import urllib.request
import urllib.error
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config_manager import DiscordNotifyConfig

_logger = logging.getLogger(__name__)

# ── Mapeamento visual por evento ───────────────────────────────────────────────
_EVENT_META: dict[str, tuple[str, str, int]] = {
    # status: (emoji, label_pt,  cor_embed)
    "starting": ("🟡", "Iniciando",         0xF1C40F),
    "running":  ("🟢", "Online",            0x2ECC71),
    "stopped":  ("🔴", "Parado",            0x95A5A6),
    "crashed":  ("💥", "Crash detectado",   0xE74C3C),
    "stopping": ("⏹️", "Encerrando",        0xE67E22),
    "update":   ("🔄", "Atualização",       0x3498DB),
    "backup":   ("💾", "Backup concluído",  0x9B59B6),
}


def _post_webhook(url: str, payload: dict) -> None:
    """Envia POST JSON ao webhook Discord. Executa em thread separada."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "ARKLAND-Multi/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 204):
                _logger.warning("Discord webhook retornou status %s", resp.status)
    except urllib.error.HTTPError as exc:
        _logger.warning("Discord webhook HTTP %s: %s", exc.code, exc.reason)
    except Exception as exc:
        _logger.debug("Falha ao enviar notificação Discord: %s", exc)


class DiscordNotifier:
    """
    Envia notificações de eventos de servidor para um webhook Discord.
    Recebe referência direta ao DiscordNotifyConfig — qualquer mudança de
    configuração salva pelo usuário é refletida automaticamente sem reiniciar.
    """

    def __init__(self, config: "DiscordNotifyConfig") -> None:
        # Mantém referência (não cópia) para refletir mudanças em tempo real
        self.config = config

    # ── API pública ────────────────────────────────────────────────────────────

    def notify_status(self, server_name: str, status: str, detail: str = "") -> None:
        """
        status: 'starting' | 'running' | 'stopped' | 'crashed' | 'stopping'
        """
        cfg = self.config
        if not cfg.enabled or not cfg.webhook_url:
            return

        # Filtra por tipo de evento habilitado
        should_send = {
            "starting": cfg.notify_start,
            "running":  cfg.notify_start,
            "stopped":  cfg.notify_stop,
            "crashed":  cfg.notify_crash,
            "stopping": cfg.notify_stop,
        }.get(status, False)

        if not should_send:
            return

        meta = _EVENT_META.get(status)
        if not meta:
            return

        emoji, label, color = meta
        self._send_embed(
            sender=cfg.sender_name or "ARKLAND",
            title=f"{emoji}  {label}",
            description=f"**{server_name}**" + (f"\n{detail}" if detail else ""),
            color=color,
        )

    def notify_update(self, server_name: str, detail: str = "") -> None:
        cfg = self.config
        if not cfg.enabled or not cfg.webhook_url or not cfg.notify_update:
            return
        emoji, label, color = _EVENT_META["update"]
        self._send_embed(
            sender=cfg.sender_name or "ARKLAND",
            title=f"{emoji}  {label}",
            description=f"**{server_name}**" + (f"\n{detail}" if detail else ""),
            color=color,
        )

    def notify_backup(self, server_name: str, detail: str = "") -> None:
        cfg = self.config
        if not cfg.enabled or not cfg.webhook_url or not cfg.notify_backup:
            return
        emoji, label, color = _EVENT_META["backup"]
        self._send_embed(
            sender=cfg.sender_name or "ARKLAND",
            title=f"{emoji}  {label}",
            description=f"**{server_name}**" + (f"\n{detail}" if detail else ""),
            color=color,
        )

    # ── Internos ───────────────────────────────────────────────────────────────

    def _send_embed(self, sender: str, title: str, description: str, color: int) -> None:
        payload = {
            "username": sender,
            "embeds": [{
                "title": title,
                "description": description,
                "color": color,
            }],
        }
        url = self.config.webhook_url
        threading.Thread(
            target=_post_webhook,
            args=(url, payload),
            daemon=True,
            name="discord-webhook",
        ).start()
