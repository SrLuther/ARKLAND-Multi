"""Cog de administração (porta de cogs/admin.py).

Comandos (somente administradores): ``!reload`` ``!load`` ``!unload`` ``!restart`` ``!shutdown``.

Adaptações ao bot embutido:
  * os nomes de cog aceitos são os três módulos embutidos
    (``voicemanager``, ``moderation``, ``admin``);
  * ``!restart`` reinicia o bot DENTRO do app (o original encerrava o processo com
    ``sys.exit(24)``, o que fecharia o ARKLAND Server Manager);
  * ``!shutdown`` encerra só o bot embutido (o app continua aberto).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

import discord
from discord.ext import commands
from discord.ext.commands import MissingPermissions, NotOwner

from .logic import AVAILABLE_COGS, reaction_confirmed, resolve_extension_module

log = logging.getLogger("arkland.obobonic")

_PACKAGE = __name__.rsplit(".", 1)[0]
_ADMIN_COMMANDS = ['reload', 'load', 'unload', 'shutdown', 'restart']


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._settings: Any = getattr(bot, "settings")

    def _log_channel(self) -> Optional[Any]:
        logs_id = self._settings.logs_channel_id
        return self.bot.get_channel(logs_id) if logs_id else None

    async def _module_or_reply(self, ctx: commands.Context[Any], cog_name: str) -> Optional[str]:
        module_name = resolve_extension_module(cog_name, _PACKAGE)
        if module_name is None:
            await ctx.send(
                f"❌ Cog `{cog_name}` não existe. Disponíveis: "
                + ", ".join(f"`{c}`" for c in AVAILABLE_COGS) + ".",
                delete_after=10,
            )
        return module_name

    @commands.command(aliases=['recarregar'])
    @commands.has_permissions(administrator=True)
    async def reload(self, ctx: commands.Context[Any], cog_name: str) -> None:
        module_name = await self._module_or_reply(ctx, cog_name)
        if module_name is None:
            return
        try:
            await self.bot.reload_extension(module_name)
            await ctx.send(f"♻️ Cog `{cog_name}` recarregado com sucesso!", delete_after=10)

            canal_logs = self._log_channel()
            if canal_logs:
                embed = discord.Embed(
                    title="🔄 Cog Recarregado",
                    description=f"A extensão **`{cog_name}`** foi recarregada manualmente por segurança.",
                    color=discord.Color.gold()
                )
                embed.set_footer(text=f"Ação executada por: {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
                embed.timestamp = datetime.now()
                await canal_logs.send(embed=embed)

        except commands.ExtensionNotLoaded:
            await ctx.send(f"❌ Cog `{cog_name}` não está carregado. Use `{self._settings.command_prefix}load {cog_name}`.", delete_after=10)
        except Exception as e:
            await ctx.send(f"❌ Falha ao recarregar `{cog_name}`: ```{e}```", delete_after=20)

    @commands.command(aliases=['carregar'])
    @commands.has_permissions(administrator=True)
    async def load(self, ctx: commands.Context[Any], cog_name: str) -> None:
        module_name = await self._module_or_reply(ctx, cog_name)
        if module_name is None:
            return
        try:
            await self.bot.load_extension(module_name)
            await ctx.send(f"✅ Cog `{cog_name}` carregado com sucesso!", delete_after=10)
        except commands.ExtensionAlreadyLoaded:
            await ctx.send(f"⚠️ Cog `{cog_name}` já está carregado.", delete_after=10)
        except Exception as e:
            await ctx.send(f"❌ Falha ao carregar `{cog_name}`: ```{e}```", delete_after=20)

    @commands.command(aliases=['descarregar'])
    @commands.has_permissions(administrator=True)
    async def unload(self, ctx: commands.Context[Any], cog_name: str) -> None:
        module_name = await self._module_or_reply(ctx, cog_name)
        if module_name is None:
            return
        try:
            if resolve_extension_module("admin", _PACKAGE) == module_name:
                await ctx.send("🛑 Não é possível descarregar o próprio cog de administração.", delete_after=10)
                return

            await self.bot.unload_extension(module_name)
            await ctx.send(f"💤 Cog `{cog_name}` descarregado com sucesso!", delete_after=10)
        except commands.ExtensionNotLoaded:
            await ctx.send(f"⚠️ Cog `{cog_name}` não está carregado/ativo para ser descarregado.", delete_after=10)
        except Exception as e:
            await ctx.send(f"❌ Falha ao descarregar `{cog_name}`: ```{e}```", delete_after=20)

    @commands.command(aliases=['reboot', 'reiniciar'])
    @commands.has_permissions(administrator=True)
    async def restart(self, ctx: commands.Context[Any]) -> None:
        embed = discord.Embed(
            title="⚠️ Confirmação Necessária",
            description="Você está prestes a **reiniciar** o bot.\n\nReaja com ✅ para confirmar ou ❌ para cancelar.",
            color=discord.Color.orange()
        )
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

        def check(reaction: discord.Reaction, user: discord.abc.User) -> bool:
            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == msg.id

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)

            if not reaction_confirmed(str(reaction.emoji)):
                await ctx.send("❌ Reinicialização cancelada.", delete_after=8)
                return

            await ctx.send("🟠 Reiniciando o Bobonic... Voltarei em um instante.", delete_after=10)

            canal_logs = self._log_channel()
            if canal_logs:
                embed = discord.Embed(
                    title="🟠 Reiniciando o Bot",
                    description=f"Bot reiniciado manualmente por {ctx.author.mention}.",
                    color=discord.Color.orange()
                )
                embed.timestamp = datetime.now()
                await canal_logs.send(embed=embed)

            await getattr(self.bot, "restart_embedded")()

        except asyncio.TimeoutError:
            await ctx.send("⏰ Tempo esgotado! Reinicialização cancelada.", delete_after=8)
        except Exception as e:
            await ctx.send(f"❌ Erro ao tentar reiniciar: {e}")

    @commands.command(aliases=['desligar'])
    @commands.has_permissions(administrator=True)
    async def shutdown(self, ctx: commands.Context[Any]) -> None:
        embed = discord.Embed(
            title="⚠️ Confirmação Necessária",
            description="Você está prestes a **desligar** o bot permanentemente.\n\nReaja com ✅ para confirmar ou ❌ para cancelar.",
            color=discord.Color.red()
        )
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

        def check(reaction: discord.Reaction, user: discord.abc.User) -> bool:
            return user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == msg.id

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)

            if not reaction_confirmed(str(reaction.emoji)):
                await ctx.send("❌ Desligamento cancelado.", delete_after=8)
                return

            await ctx.send("🔴 Desligando o Bobonic... Adeus.", delete_after=10)

            canal_logs = self._log_channel()
            if canal_logs:
                embed = discord.Embed(
                    title="🔴 Bot Desligado",
                    description=f"Bot desligado manualmente por {ctx.author.mention}.",
                    color=discord.Color.red()
                )
                embed.set_footer(text="Processo encerrado.")
                embed.timestamp = datetime.now()
                await canal_logs.send(embed=embed)

            await getattr(self.bot, "shutdown_embedded")()

        except asyncio.TimeoutError:
            await ctx.send("⏰ Tempo esgotado! Desligamento cancelado.", delete_after=8)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context[Any], error: commands.CommandError) -> None:
        if ctx.cog != self or ctx.command is None or ctx.command.name not in _ADMIN_COMMANDS:
            return

        if isinstance(error, MissingPermissions):
            await ctx.send("❌ **Acesso Negado:** Você não tem a permissão de **Administrador** para usar este comando.", delete_after=10)
        elif isinstance(error, NotOwner):
            await ctx.send("❌ **Acesso Negado:** Somente o Proprietário do Bot pode executar este comando.", delete_after=10)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"⚠️ **Argumento Faltando:** Você deve especificar o nome do cog. Exemplo: `{self._settings.command_prefix}{ctx.command.name} voicemanager`", delete_after=10)
        else:
            log.error("Erro inesperado no comando %s por %s: %s", ctx.command.name, ctx.author, error)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
