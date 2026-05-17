"""
Cliente BattleMetrics — consulta periódica à API pública para confirmar
se um servidor ARK está realmente online e quantos jogadores estão conectados.

API pública, sem autenticação: https://api.battlemetrics.com/servers/{id}
"""
from __future__ import annotations

import json
import threading
import time
from typing import Callable, Dict, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


_BM_API_URL = "https://api.battlemetrics.com/servers/{server_id}"
_POLL_INTERVAL = 60   # segundos entre consultas
_TIMEOUT = 10         # timeout por requisição


class BattleMetricsData:
    """Dados retornados pela API para um servidor."""
    __slots__ = ("online", "players", "max_players", "name", "updated_at")

    def __init__(
        self,
        online: bool,
        players: int,
        max_players: int,
        name: str,
        updated_at: str = "",
    ) -> None:
        self.online = online
        self.players = players
        self.max_players = max_players
        self.name = name
        self.updated_at = updated_at


def _fetch_server(bm_id: str) -> Optional[BattleMetricsData]:
    """Consulta a API BattleMetrics e retorna os dados, ou None em caso de erro."""
    url = _BM_API_URL.format(server_id=bm_id.strip())
    req = Request(url, headers={"User-Agent": "ARKLAND-ServerManager/1.0"})
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read()
        data = json.loads(raw)
        attrs = data["data"]["attributes"]
        return BattleMetricsData(
            online=attrs.get("status", "") == "online",
            players=int(attrs.get("players", 0)),
            max_players=int(attrs.get("maxPlayers", 0)),
            name=attrs.get("name", ""),
            updated_at=attrs.get("updatedAt", ""),
        )
    except (HTTPError, URLError, KeyError, ValueError, OSError):
        return None


class BattleMetricsPoller:
    """
    Poller periódico que consulta a API BattleMetrics para múltiplos servidores.

    Uso:
        poller = BattleMetricsPoller(on_update=my_callback)
        poller.set_servers({"server_uuid": "bm_id_1", "server_uuid2": "bm_id_2"})
        poller.start()
        ...
        poller.stop()

    on_update(server_id: str, data: Optional[BattleMetricsData]) -> None
        Chamado após cada consulta com os dados mais recentes (ou None se falhou).
    """

    def __init__(
        self,
        on_update: Optional[Callable[[str, Optional[BattleMetricsData]], None]] = None,
    ) -> None:
        self._on_update = on_update or (lambda sid, d: None)
        self._servers: Dict[str, str] = {}   # {server_id: bm_id}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # Cache dos dados mais recentes: {server_id: BattleMetricsData | None}
        self._cache: Dict[str, Optional[BattleMetricsData]] = {}

    def set_servers(self, mapping: Dict[str, str]) -> None:
        """Atualiza o mapeamento {server_id_interno -> bm_id}.
        Passa mapping vazio para limpar. Remove entradas com bm_id vazio.
        """
        with self._lock:
            self._servers = {k: v for k, v in mapping.items() if v and v.strip()}
            # Remove cache de IDs que saíram do mapeamento
            for sid in list(self._cache):
                if sid not in self._servers:
                    del self._cache[sid]

    def get(self, server_id: str) -> Optional[BattleMetricsData]:
        """Retorna os dados em cache para um servidor, ou None."""
        return self._cache.get(server_id)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="BattleMetricsPoller"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _loop(self) -> None:
        # Primeira consulta imediata; depois a cada _POLL_INTERVAL segundos
        self._poll_all()
        while not self._stop_event.wait(_POLL_INTERVAL):
            self._poll_all()

    def _poll_all(self) -> None:
        with self._lock:
            items = list(self._servers.items())

        for server_id, bm_id in items:
            if self._stop_event.is_set():
                break
            data = _fetch_server(bm_id)
            self._cache[server_id] = data
            try:
                self._on_update(server_id, data)
            except Exception:
                pass
            # Pequena pausa entre requisições para não bombardear a API
            time.sleep(1)
