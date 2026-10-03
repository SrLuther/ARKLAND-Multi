"""Bot discord.py interno (equivalente ao bot.py do projeto original, reduzido aos 3 cogs).

Importa ``discord`` — só deve ser importado pela thread do bot (``runner``) ou em testes
com ``pytest.importorskip("discord")``.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, List, Optional

import discord
from discord.ext import commands

from .cache import ChannelCache, RoleCache
from .settings import BotSettings
from .storage import ensure_data_dir

log = logging.getLogger("arkland.obobonic")

_PACKAGE = __name__.rsplit(".", 1)[0]

# (módulo, nome amigável, flag em BotSettings ou None = sempre)
COG_MODULES = (
    ("admin", "admin", None),
    ("voice_manager", "voicemanager", "enable_voice"),
    ("moderation", "moderation", "enable_moderation"),
)


def build_intents() -> discord.Intents:
    """Intents idênticas às do bot original (members + message_content são privilegiadas)."""
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    return intents


def enabled_cog_modules(settings: BotSettings) -> List[str]:
    """Módulos completos dos cogs habilitados (admin sempre)."""
    out: List[str] = []
    for module, _label, flag in COG_MODULES:
        if flag is None or getattr(settings, flag, True):
            out.append(f"{_PACKAGE}.{module}")
    return out


class ObobonicBot(commands.Bot):
    """Bot com os cogs de administração, moderação e salas de voz."""

    def __init__(
        self,
        settings: BotSettings,
        *,
        on_ready_cb: Optional[Callable[["ObobonicBot"], None]] = None,
        on_restart: Optional[Callable[[], None]] = None,
        on_shutdown: Optional[Callable[[], None]] = None,
    ) -> None:
        # O bot gerencia canais de voz, mas nunca fala: o aviso do PyNaCl é só ruído.
        discord.VoiceClient.warn_nacl = False
        super().__init__(
            command_prefix=settings.command_prefix,
            intents=build_intents(),
            help_command=None,
        )
        self.settings = settings
        self.channel_cache = ChannelCache()
        self.role_cache = RoleCache()
        self._on_ready_cb = on_ready_cb
        self._on_restart = on_restart
        self._on_shutdown = on_shutdown
        ensure_data_dir(settings.data_dir)

    async def setup_hook(self) -> None:
        """Executado UMA vez antes de conectar ao gateway."""
        await load_cogs(self)

    async def on_ready(self) -> None:
        user = self.user
        log.info("🚀 Bot Logado como %s (ID: %s)", user, user.id if user else "desconhecido")
        if self.settings.guild_id and self.get_guild(self.settings.guild_id) is None:
            log.warning(
                "⚠️ O bot não está no servidor configurado (ID %s). Use «Convidar bot» no painel.",
                self.settings.guild_id,
            )
        log.info("✅ Bot pronto e rodando!")
        if self._on_ready_cb:
            try:
                self._on_ready_cb(self)
            except Exception:  # callback de UI nunca derruba o bot
                log.debug("on_ready_cb falhou", exc_info=True)

    async def restart_embedded(self) -> None:
        """!restart — fecha a conexão e pede ao runner para subir o bot de novo."""
        if self._on_restart:
            self._on_restart()
        await self.close()

    async def shutdown_embedded(self) -> None:
        """!shutdown — fecha a conexão sem reiniciar (o app continua aberto)."""
        if self._on_shutdown:
            self._on_shutdown()
        await self.close()

    async def on_command_error(self, ctx: commands.Context[Any], error: commands.CommandError) -> None:  # type: ignore[override]
        # Ignora erros já tratados por handlers locais dos cogs
        if hasattr(ctx.command, 'on_error'):
            return
        if ctx.cog and commands.Cog._get_overridden_method(ctx.cog.cog_command_error) is not None:
            return

        if isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "❌ **Acesso Negado:** Você não tem a permissão de **Administrador** para usar este comando.",
                delete_after=8
            )
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"⚠️ **Argumento faltando:** `{error.param.name}`.",
                delete_after=8
            )
        elif isinstance(error, commands.CommandNotFound):
            pass  # Ignora comandos inexistentes silenciosamente
        else:
            log.error("[ERRO] Comando `%s` por %s: %s", ctx.command, ctx.author, error)


async def load_cogs(bot: ObobonicBot) -> bool:
    """Carrega os cogs habilitados. Retorna True se todos carregaram."""
    log.info("--- Iniciando Carregamento de Cogs ---")
    all_loaded = True
    for module in enabled_cog_modules(bot.settings):
        short = module.rsplit(".", 1)[1]
        try:
            await bot.load_extension(module)
            log.info("[COG] Carregado: %s.py", short)
        except commands.ExtensionAlreadyLoaded:
            log.info("[COG] Já carregado: %s.py", short)
        except Exception as e:
            all_loaded = False
            log.error("[ERRO] Falha ao carregar %s.py: Erro: %s: %s", short, type(e).__name__, e)
    log.info("Status Final: %s", "SUCESSO" if all_loaded else "FALHA")
    return all_loaded
