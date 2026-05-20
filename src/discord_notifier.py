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
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

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

_FOOTER_TEXT = "ARKLAND Server Manager"


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
        detail: string codificada pelo server_manager (key=value por linha)
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

        # ── Decodifica o detalhe estruturado (key=value por linha) ────────────
        detail_map: dict[str, str] = {}
        for line in detail.splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                detail_map[k.strip()] = v.strip()

        map_name    = detail_map.get("map", "")
        port        = detail_map.get("port", "")
        uptime_val  = detail_map.get("uptime", "")
        crash_info  = detail_map.get("crash", "")

        fields: List[dict] = []
        description = ""

        # ── Conteúdo por status ───────────────────────────────────────────────
        if status == "starting":
            description = "O servidor está inicializando. Isso pode levar alguns minutos."
            if map_name:
                fields.append({"name": "🗺️  Mapa",  "value": map_name, "inline": True})
            if port:
                fields.append({"name": "🔌  Porta", "value": port,     "inline": True})

        elif status == "running":
            description = "O servidor está **online** e pronto para receber conexões."
            if map_name:
                fields.append({"name": "🗺️  Mapa",  "value": map_name, "inline": True})
            if port:
                fields.append({"name": "🔌  Porta", "value": port,     "inline": True})

        elif status == "stopping":
            description = (
                "Salvando o mundo (`SaveWorld`) e encerrando o processo.\n"
                "Aguarde o encerramento gracioso para preservar os saves."
            )

        elif status == "stopped":
            description = "O servidor foi encerrado com sucesso."
            if uptime_val:
                fields.append({"name": "⏱️  Uptime", "value": uptime_val, "inline": True})

        elif status == "crashed":
            description = "⚠️  O processo do servidor encerrou inesperadamente."
            if crash_info:
                # Limita a 900 chars para não ultrapassar o limite de campo do Discord
                excerpt = crash_info[:900] + ("…" if len(crash_info) > 900 else "")
                fields.append({
                    "name": "🔍  Diagnóstico",
                    "value": f"```\n{excerpt}\n```",
                    "inline": False,
                })
            fields.append({
                "name": "📋  Mais detalhes",
                "value": "Consulte a aba **🔴 Crashes** no ARKLAND para o histórico completo e diagnóstico detalhado.",
                "inline": False,
            })

        self._send_embed(
            sender=cfg.sender_name or "ARKLAND",
            title=f"{emoji}  {label} — {server_name}",
            description=description,
            color=color,
            fields=fields,
        )

    def notify_update(self, server_name: str, detail: str = "") -> None:
        cfg = self.config
        if not cfg.enabled or not cfg.webhook_url or not cfg.notify_update:
            return
        emoji, label, color = _EVENT_META["update"]
        fields: List[dict] = []
        if detail:
            fields.append({"name": "�  Detalhes", "value": detail, "inline": False})
        self._send_embed(
            sender=cfg.sender_name or "ARKLAND",
            title=f"{emoji}  {label} — {server_name}",
            description="Atualização concluída. O servidor será reiniciado automaticamente.",
            color=color,
            fields=fields,
        )

    def notify_backup(self, server_name: str, detail: str = "") -> None:
        cfg = self.config
        if not cfg.enabled or not cfg.webhook_url or not cfg.notify_backup:
            return
        emoji, label, color = _EVENT_META["backup"]
        fields: List[dict] = []
        if detail:
            fields.append({"name": "💾  Snapshot", "value": detail, "inline": False})
        self._send_embed(
            sender=cfg.sender_name or "ARKLAND",
            title=f"{emoji}  {label} — {server_name}",
            description="Backup realizado com sucesso. Use a aba **Backup** no ARKLAND para restaurar quando necessário.",
            color=color,
            fields=fields,
        )

    # ── Internos ───────────────────────────────────────────────────────────────

    def _send_embed(
        self,
        sender: str,
        title: str,
        description: str,
        color: int,
        fields: Optional[List[dict]] = None,
    ) -> None:
        embed: dict = {
            "title": title,
            "color": color,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "footer": {"text": _FOOTER_TEXT},
        }
        if description:
            embed["description"] = description
        if fields:
            embed["fields"] = fields

        payload = {
            "username": sender,
            "embeds": [embed],
        }
        url = self.config.webhook_url
        threading.Thread(
            target=_post_webhook,
            args=(url, payload),
            daemon=True,
            name="discord-webhook",
        ).start()
