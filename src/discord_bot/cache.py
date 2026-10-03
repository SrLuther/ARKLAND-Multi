"""Caches de canais/cargos do Discord (portado de utils/cache.py do projeto original).

Diferença: as instâncias são POR bot (``bot.channel_cache`` / ``bot.role_cache``), para
que um reinício do bot embutido não reaproveite objetos de uma conexão anterior.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple


class ChannelCache:
    """Cache para canais do Discord."""

    def __init__(self, ttl: float = 300.0) -> None:  # 5 minutos
        self._cache: Dict[int, Tuple[Any, float]] = {}
        self.ttl = ttl

    def get(self, bot: Any, channel_id: int) -> Optional[Any]:
        now = time.time()
        if channel_id in self._cache:
            obj, timestamp = self._cache[channel_id]
            if now - timestamp < self.ttl:
                return obj
            del self._cache[channel_id]
        channel = bot.get_channel(channel_id)
        if channel:
            self._cache[channel_id] = (channel, now)
        return channel

    def invalidate(self, channel_id: int) -> None:
        self._cache.pop(channel_id, None)

    def clear(self) -> None:
        self._cache.clear()


class RoleCache:
    """Cache para cargos do Discord (por guild)."""

    def __init__(self, ttl: float = 600.0) -> None:  # 10 minutos
        self._cache: Dict[int, Dict[int, Tuple[Any, float]]] = {}
        self.ttl = ttl

    def get(self, guild: Any, role_id: int) -> Optional[Any]:
        if not guild:
            return None
        guild_cache = self._cache.setdefault(guild.id, {})
        now = time.time()
        if role_id in guild_cache:
            obj, timestamp = guild_cache[role_id]
            if now - timestamp < self.ttl:
                return obj
            del guild_cache[role_id]
        role = guild.get_role(role_id)
        if role:
            guild_cache[role_id] = (role, now)
        return role

    def invalidate_guild(self, guild_id: int) -> None:
        self._cache.pop(guild_id, None)

    def clear(self) -> None:
        self._cache.clear()
