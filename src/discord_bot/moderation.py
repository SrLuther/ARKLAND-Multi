"""Cog de moderação (porta de cogs/moderation.py).

Comandos: ``!faxina`` (purgeall), ``!limpar`` (clear), ``!limpezageral`` (limparall).
Filtros automáticos: convites do Discord e palavrões.

Mudanças em relação ao original (apenas adaptação ao bot embutido):
  * IDs de canal de logs / cargo de quarentena vêm da config do app;
  * a lista de palavrões vive em ``<dados>/palavroes.txt`` (e não em ``.bancos/``);
  * mensagens privadas (DM) são ignoradas pelos filtros.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List, Optional, cast

import discord
from discord.ext import commands

from . import storage
from .logic import (
    INVITE_REGEX,
    VIOLATION_BADWORD,
    VIOLATION_INVITE,
    classify_message,
    compile_badwords,
    limpezageral_limit_ok,
)

log = logging.getLogger("arkland.obobonic")


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self._settings: Any = getattr(bot, "settings")
        self._compile_badwords()
        # Regex pré-compilada para convites (melhor performance)
        self.invite_regex = INVITE_REGEX

    def _compile_badwords(self) -> None:
        """Carrega e compila lista de palavrões em regex otimizada."""
        try:
            words = storage.load_badwords(self._settings.data_dir)
            self.badwords_regex = compile_badwords(words)
            self.badwords_count = len(words) if self.badwords_regex else 0
            log.info("✅ Filtro de palavrões carregado: %s palavras.", self.badwords_count)
        except FileNotFoundError:
            log.warning("⚠️ Arquivo palavroes.txt não encontrado. Filtro de palavrões desativado.")
            self.badwords_regex = None
            self.badwords_count = 0

    def get_log_channel(self, guild: Optional[discord.Guild]) -> Optional[discord.TextChannel]:
        """Obtém canal de logs com cache."""
        logs_id = self._settings.logs_channel_id
        if not logs_id:
            return None
        cache = getattr(self.bot, "channel_cache", None)
        if cache:
            channel = cache.get(self.bot, logs_id)
            return cast(Optional[discord.TextChannel], channel) if isinstance(channel, discord.TextChannel) else None
        channel = self.bot.get_channel(logs_id)
        return cast(Optional[discord.TextChannel], channel)

    @staticmethod
    async def _safe_delete(message: discord.Message) -> None:
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

    @commands.command(name="faxina", aliases=['purgeall'])
    @commands.has_permissions(manage_messages=True)
    async def faxina(self, ctx: commands.Context[Any]) -> None:
        try:
            if ctx.guild is None or not isinstance(ctx.channel, discord.TextChannel):
                await ctx.send("❌ Este comando só pode ser usado em canais de texto do servidor.", delete_after=8)
                return
            await self._safe_delete(ctx.message)
            deleted: List[discord.Message] = await ctx.channel.purge()
            log_channel: Optional[discord.TextChannel] = self.get_log_channel(ctx.guild)
            if log_channel:
                embed = discord.Embed(
                    title="🧹 Faxina Completa (Purge)",
                    description=f"Todas as mensagens foram apagadas em {ctx.channel.mention}.",
                    color=discord.Color.blue()
                )
                embed.add_field(name="Mensagens Deletadas", value=len(deleted), inline=True)
                embed.add_field(name="Executado Por", value=ctx.author.mention, inline=True)
                embed.timestamp = datetime.now()
                await log_channel.send(embed=embed)

            await ctx.send(f"🧹 Faxina feita! {len(deleted)} mensagens deletadas.", delete_after=5)

        except discord.Forbidden:
            await ctx.send("❌ Não tenho permissão para deletar mensagens neste canal.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Ocorreu um erro ao tentar deletar as mensagens: {e}")

    @commands.command(name="limpar", aliases=['clear'])
    @commands.has_permissions(manage_messages=True)
    async def limpar(self, ctx: commands.Context[Any], quantidade: int) -> None:
        if ctx.guild is None or not isinstance(ctx.channel, discord.TextChannel):
            await ctx.send("❌ Este comando só pode ser usado em canais de texto do servidor.", delete_after=8)
            return
        await self._safe_delete(ctx.message)
        if quantidade <= 0:
            await ctx.send("❌ A quantidade de caracteres precisa ser maior que 0.", delete_after=5)
            return

        contador: int = 0
        mensagens: List[discord.Message] = []

        async for msg in ctx.channel.history(limit=None):
            contador += len(msg.content)
            mensagens.append(msg)
            if contador >= quantidade:
                break

        if mensagens:
            try:
                await ctx.channel.delete_messages(mensagens)
                log_channel: Optional[discord.TextChannel] = self.get_log_channel(ctx.guild)
                if log_channel:
                    embed = discord.Embed(
                        title="🧹 Limpeza por Caracteres",
                        description=f"Mensagens deletadas em {ctx.channel.mention} até atingir o limite de caracteres.",
                        color=discord.Color.dark_blue()
                    )
                    embed.add_field(name="Caracteres Alvo", value=quantidade, inline=True)
                    embed.add_field(name="Mensagens Deletadas", value=len(mensagens), inline=True)
                    embed.add_field(name="Executado Por", value=ctx.author.mention, inline=False)
                    embed.timestamp = datetime.now()
                    await log_channel.send(embed=embed)

                await ctx.send(f"🧹 Mensagens deletadas até atingir {quantidade} caracteres.", delete_after=5)
            except discord.Forbidden:
                await ctx.send("❌ Não tenho permissão para deletar mensagens neste canal.")
            except discord.HTTPException as e:
                await ctx.send(f"❌ Ocorreu um erro ao tentar deletar as mensagens: {e}")
        else:
            await ctx.send("⚠️ Não foram encontradas mensagens para deletar.", delete_after=5)

    @commands.command(aliases=['limparall'])
    @commands.has_permissions(administrator=True)
    async def limpezageral(self, ctx: commands.Context[Any], usuario: discord.Member, limite: int = 200) -> None:
        if not limpezageral_limit_ok(limite):
            await ctx.send("O limite deve ser entre 1 e 1000.")
            return

        if ctx.guild is None:
            await ctx.send("❌ Este comando só pode ser usado dentro de um servidor.", delete_after=8)
            return
        await self._safe_delete(ctx.message)

        log_channel: Optional[discord.TextChannel] = self.get_log_channel(ctx.guild)
        mensagens_apagadas: int = 0

        guild: discord.Guild = ctx.guild
        role_cache = getattr(self.bot, "role_cache", None)
        quarantine_id = self._settings.quarantine_role_id
        quarantine_role: Optional[discord.Role] = (
            (role_cache.get(guild, quarantine_id) if role_cache else guild.get_role(quarantine_id))
            if quarantine_id else None
        )
        if quarantine_role:
            try:
                await usuario.edit(roles=[quarantine_role], reason="Conta comprometida/Raid - Quarentena.")
                await ctx.send(f"🛡️ **QUARENTENA APLICADA:** {usuario.mention} foi isolado e o sistema Anti-Raid está em ação.", delete_after=10)
            except discord.Forbidden:
                await ctx.send("❌ Não tenho permissão para modificar cargos do usuário (verifique a hierarquia).", delete_after=15)
            except Exception as e:
                log.error("Erro ao aplicar quarentena: %s", e)

        for channel in guild.text_channels:
            try:
                def is_target(message: discord.Message) -> bool:
                    return message.author == usuario

                deleted: List[discord.Message] = await channel.purge(limit=limite, check=is_target)

                if deleted:
                    mensagens_apagadas += len(deleted)
                    await channel.send(
                        f"🛡️ **SISTEMA DE AUTODEFESA ACIONADO** 🛡️\n"
                        f"O membro {usuario.mention} está em **QUARENTENA** por suspeita de RAID. "
                        f"Suas últimas **{len(deleted)}** mensagens neste canal foram removidas.",
                        delete_after=120
                    )

            except discord.Forbidden:
                continue
            except Exception as e:
                log.error("Erro ao limpar mensagens em %s: %s", channel.name, e)
                continue

        if log_channel:
            embed = discord.Embed(
                title="🚨 AÇÃO ANTI-RAID: Limpeza Global & Quarentena",
                description="Conta comprometida detectada e isolada. Limpeza de mensagens concluída.",
                color=discord.Color.red()
            )
            embed.add_field(name="Usuário Alvo", value=usuario.mention, inline=True)
            embed.add_field(name="Total Apagado", value=f"{mensagens_apagadas} mensagens", inline=True)
            embed.add_field(name="Quarentena Aplicada", value="Sim" if quarantine_role else "Não (Cargo não configurado)", inline=False)
            embed.add_field(name="Executado Por", value=ctx.author.mention, inline=False)
            embed.timestamp = datetime.now()
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.guild is None:
            return

        violation = classify_message(message.content, self.badwords_regex, self.invite_regex)
        if violation is None:
            return

        log_channel: Optional[discord.TextChannel] = self.get_log_channel(message.guild)
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        if violation == VIOLATION_INVITE:
            await self._safe_delete(message)
            if log_channel:
                await log_channel.send(f"🚫 Convite bloqueado ({now}) de {message.author.mention}:\n`{message.content}`")
            await message.channel.send(f"{message.author.mention}, enviar convites é proibido.", delete_after=5)
            return

        if violation == VIOLATION_BADWORD:
            await self._safe_delete(message)
            if log_channel:
                await log_channel.send(f"⚠ Palavrão detectado ({now}) de {message.author.mention}:\n`{message.content}`")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Moderation(bot))
