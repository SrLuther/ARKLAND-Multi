"""Bot Discord oBobonic embutido no ARKLAND Server Manager.

Capacidades (portadas dos cogs do projeto oBobonicClean):
  * administração  (``admin.py``)        — !reload / !load / !unload / !restart / !shutdown
  * moderação      (``moderation.py``)   — !faxina / !limpar / !limpezageral + filtros
  * salas de voz   (``voice_manager.py``) — salas temporárias a partir de um lobby

O pacote NÃO importa ``discord`` no topo: ``settings``, ``logic``, ``storage`` e
``legacy_import`` são puros (testáveis sem discord.py). ``runner`` só importa
``discord`` dentro da thread do bot, quando o usuário inicia o bot.
"""

__all__ = [
    "settings",
    "logic",
    "storage",
    "legacy_import",
    "runner",
]
