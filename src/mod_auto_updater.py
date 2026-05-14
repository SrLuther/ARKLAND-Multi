"""
Verificador automático de atualizações de mods do Steam Workshop.

Fluxo:
  1. A cada `check_interval_minutes` verifica o timestamp de atualização de cada
     mod configurado em todos os servidores via API pública do Steam.
  2. Quando detecta um mod atualizado:
     a. Inicia o download do mod imediatamente (servidores continuam rodando).
     b. Emite broadcast RCON informando o tempo restante (avisos em X min e 1 min).
     c. Quando o download conclui E o timer expira (o maior dos dois), para os servidores.
     d. Reinicia os servidores parados com o mod já atualizado.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.request
from datetime import datetime
from typing import Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .server_config import ServerConfig
    from .server_manager import ServerManager
    from .mod_manager import ModManager

_STEAM_API_URL = (
    "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"
)

# Segundos entre cada ciclo de verificação (padrão 15 min)
_DEFAULT_CHECK_INTERVAL = 15 * 60


class ModAutoUpdater:
    """
    Serviço que roda em background verificando atualizações de mods e
    reiniciando servidores conforme necessário.
    """

    def __init__(
        self,
        server_manager: "ServerManager",
        mod_manager: "ModManager",
        get_servers: Callable[[], List["ServerConfig"]],
        on_log: Optional[Callable[[str, str], None]] = None,
        check_interval_minutes: int = 15,
        warning_minutes: int = 5,
    ) -> None:
        self._server_manager      = server_manager
        self._mod_manager         = mod_manager
        self._get_servers         = get_servers
        self._on_log              = on_log or (lambda m, lvl: None)
        self._check_interval      = check_interval_minutes * 60
        self._warning_seconds     = warning_minutes * 60
        self._enabled             = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event          = threading.Event()
        # mod_id → last known time_updated (unix timestamp)
        self._known_timestamps: Dict[str, int] = {}
        # mod_id → nome amigável
        self._mod_names: Dict[str, str] = {}

    # ── Controle ──────────────────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_interval(self, minutes: int) -> None:
        self._check_interval = max(1, minutes) * 60

    def set_warning_minutes(self, minutes: int) -> None:
        self._warning_seconds = max(1, minutes) * 60

    def start(self) -> None:
        if self._enabled:
            return
        self._enabled = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="ModAutoUpdater"
        )
        self._thread.start()
        self._log("Verificador automático de mods iniciado.", "info")

    def stop(self) -> None:
        if not self._enabled:
            return
        self._enabled = False
        self._stop_event.set()
        self._log("Verificador automático de mods parado.", "info")

    # ── Loop principal ────────────────────────────────────────────────────────

    def _loop(self) -> None:
        # Primeira execução: popula timestamps sem disparar update
        self._seed_timestamps()
        # Verifica mods não instalados e baixa os que faltam
        self._install_missing_mods()
        while not self._stop_event.is_set():
            self._stop_event.wait(self._check_interval)
            if self._stop_event.is_set():
                break
            try:
                self._check_for_updates()
            except Exception as exc:
                self._log(f"Erro no ciclo de verificação de mods: {exc}", "error")

    def _install_missing_mods(self) -> None:
        """Verifica mods não instalados em cada servidor e força o download."""
        for srv in self._get_servers():
            if not srv.mods or not srv.install_dir:
                continue
            missing = [
                mid for mid in srv.mods
                if mid.strip().isdigit()
                and not self._mod_manager.check_mod_installed(srv.install_dir, mid.strip())
            ]
            if not missing:
                continue
            self._log(
                f"Servidor '{srv.name}': {len(missing)} mod(s) não instalado(s), "
                f"iniciando download: {', '.join(missing)}",
                "info",
            )
            done_event = __import__("threading").Event()

            def _on_done(ok: bool, _ev=done_event):
                _ev.set()

            self._mod_manager.download_mods(missing, srv.install_dir, on_done=_on_done)
            done_event.wait(timeout=600)  # até 10 min por servidor

    def _seed_timestamps(self) -> None:
        """Obtém timestamps atuais sem considerar como atualização."""
        all_mod_ids = self._collect_all_mod_ids()
        if not all_mod_ids:
            return
        data = self._fetch_mod_details(all_mod_ids)
        for item in data:
            mid = str(item.get("publishedfileid", ""))
            ts  = int(item.get("time_updated", 0))
            name = item.get("title", mid)
            if mid:
                self._known_timestamps[mid] = ts
                self._mod_names[mid] = name
        self._log(
            f"Timestamps iniciais obtidos para {len(data)} mods.", "info"
        )

    def _check_for_updates(self) -> None:
        all_mod_ids = self._collect_all_mod_ids()
        if not all_mod_ids:
            return

        self._log("Verificando atualizações de mods no Workshop…", "info")
        data = self._fetch_mod_details(all_mod_ids)
        updated_mods: List[str] = []

        for item in data:
            mid  = str(item.get("publishedfileid", ""))
            ts   = int(item.get("time_updated", 0))
            name = item.get("title", mid)
            if not mid:
                continue
            self._mod_names[mid] = name
            known = self._known_timestamps.get(mid, 0)
            if ts > known:
                self._log(
                    f"🔔 Mod atualizado no Workshop: [{mid}] {name} "
                    f"(publicado em {datetime.utcfromtimestamp(ts).strftime('%d/%m/%Y %H:%M')} UTC)",
                    "info",
                )
                updated_mods.append(mid)
                self._known_timestamps[mid] = ts

        if not updated_mods:
            self._log("Nenhuma atualização de mod encontrada.", "info")
            return

        # Agrupa: mod_id → lista de server_ids afetados
        affected: Dict[str, List[str]] = {}
        for srv in self._get_servers():
            for mid in srv.mods:
                if mid in updated_mods:
                    affected.setdefault(mid, []).append(srv.id)

        if not affected:
            return

        # Processa cada mod atualizado em thread separada para não bloquear o loop
        for mod_id, server_ids in affected.items():
            t = threading.Thread(
                target=self._handle_mod_update,
                args=(mod_id, server_ids),
                daemon=True,
                name=f"ModUpdate-{mod_id}",
            )
            t.start()

    # ── Atualização de um mod ─────────────────────────────────────────────────

    def _handle_mod_update(self, mod_id: str, server_ids: List[str]) -> None:
        mod_name = self._mod_names.get(mod_id, mod_id)
        warn_secs = self._warning_seconds

        # ── Fase 1: localizar install_dir ─────────────────────────────────────
        install_dir = ""
        for srv in self._get_servers():
            if mod_id in srv.mods:
                install_dir = srv.install_dir
                break

        if not install_dir:
            self._log(f"Diretório de instalação não encontrado para mod {mod_id}.", "error")
            return

        # ── Fase 2: iniciar download IMEDIATAMENTE (servidores continuam rodando) ──
        self._log(f"Baixando mod atualizado {mod_id} ({mod_name}) em segundo plano…", "info")
        done_event = threading.Event()
        success_box = [False]

        def _on_done(ok: bool) -> None:
            success_box[0] = ok
            done_event.set()

        self._mod_manager.download_mods([mod_id], install_dir, on_done=_on_done, copy_to_mods=False)

        # ── Fase 3: avisos RCON enquanto o download acontece ──────────────────
        running_servers = [
            sid for sid in server_ids
            if self._server_manager.get_instance(sid) is not None
            and self._server_manager.get_instance(sid).status == "running"  # type: ignore[union-attr]
        ]

        if running_servers:
            self._broadcast_all(
                running_servers,
                f"[ARKLAND] ⚠ Mod '{mod_name}' foi atualizado! Baixando em segundo plano… "
                f"O servidor reiniciará em até {warn_secs // 60} minuto(s).",
            )
            self._log(
                f"Broadcast enviado: mod {mod_id} ({mod_name}) será aplicado em até "
                f"{warn_secs // 60} min nos servidores: {', '.join(running_servers)}",
                "info",
            )

            # Aviso 1 minuto antes (se warn_secs > 90 s)
            if warn_secs > 90:
                self._stop_event.wait(warn_secs - 60)
                if self._stop_event.is_set():
                    return
                running_servers = [
                    sid for sid in server_ids
                    if self._server_manager.get_instance(sid) is not None
                    and self._server_manager.get_instance(sid).status == "running"  # type: ignore[union-attr]
                ]
                if running_servers:
                    self._broadcast_all(
                        running_servers,
                        f"[ARKLAND] ⚠ Reiniciando em 1 minuto para aplicar mod '{mod_name}'.",
                    )
                self._stop_event.wait(60)
                if self._stop_event.is_set():
                    return
            else:
                self._stop_event.wait(warn_secs)
                if self._stop_event.is_set():
                    return
        else:
            self._log(
                f"Nenhum servidor rodando usa o mod {mod_id}; aguardando download sem aviso.",
                "info",
            )

        # ── Fase 4: aguardar download concluir (se ainda não terminou) ────────
        if not done_event.is_set():
            self._log(f"Timer expirou; aguardando conclusão do download do mod {mod_id}…", "info")
            done_event.wait(timeout=600)

        if not success_box[0]:
            self._log(f"Falha ao baixar mod {mod_id}. Servidores NÃO serão reiniciados.", "error")
            return

        self._log(f"Mod {mod_id} ({mod_name}) baixado. Parando servidores para aplicar…", "info")

        # ── Fase 5: parar servidores ──────────────────────────────────────────
        running_now = [
            sid for sid in server_ids
            if self._server_manager.get_instance(sid) is not None
            and self._server_manager.get_instance(sid).status  # type: ignore[union-attr]
            in ("running", "starting")
        ]
        for sid in running_now:
            self._log(f"Parando servidor '{sid}' para aplicar mod {mod_id}…", "info")
            self._server_manager.stop_server(sid)

        # Aguarda todos pararem (máx 90 s)
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            all_stopped = all(
                self._server_manager.get_instance(sid) is None
                or self._server_manager.get_instance(sid).status == "stopped"  # type: ignore[union-attr]
                for sid in server_ids
            )
            if all_stopped:
                break
            time.sleep(2)

        # ── Fase 5b: copiar mod para Mods/ (agora que o servidor está parado) ──
        self._log(f"Copiando mod {mod_id} para ShooterGame/Content/Mods/…", "info")
        self._mod_manager.copy_downloaded_mods([mod_id], install_dir)

        # ── Fase 6: reiniciar servidores parados ──────────────────────────────
        for sid in running_now:
            inst = self._server_manager.get_instance(sid)
            if inst and inst.status == "stopped":
                self._log(f"Reiniciando servidor '{sid}'…", "info")
                self._server_manager.start_server(sid)
            time.sleep(3)  # pequeno intervalo entre starts

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _broadcast_all(self, server_ids: List[str], message: str) -> None:
        from .rcon_client import RconClient, RconError
        for sid in server_ids:
            inst = self._server_manager.get_instance(sid)
            if not inst:
                continue
            cfg = inst.config
            if not cfg.rcon_enabled or not cfg.rcon_password:
                continue
            try:
                rcon = RconClient(
                    host="127.0.0.1",
                    port=cfg.rcon_port,
                    password=cfg.rcon_password,
                )
                rcon.send_command(f"Broadcast {message[:900]}")
                rcon.disconnect()
            except RconError as exc:
                self._log(f"RCON broadcast falhou ({sid}): {exc}", "warning")

    def _collect_all_mod_ids(self) -> List[str]:
        seen: set[str] = set()
        for srv in self._get_servers():
            for mid in srv.mods:
                if mid.strip().isdigit():
                    seen.add(mid.strip())
        return list(seen)

    def _fetch_mod_details(self, mod_ids: List[str]) -> List[dict]:
        """
        Consulta a API do Steam para obter detalhes (incluindo time_updated)
        de uma lista de mods. Retorna lista de dicts.
        Divide em lotes de 100 (limite da API).
        """
        results: List[dict] = []
        batch_size = 100
        for i in range(0, len(mod_ids), batch_size):
            batch = mod_ids[i : i + batch_size]
            try:
                results.extend(self._fetch_batch(batch))
            except Exception as exc:
                self._log(f"Erro ao consultar Steam API (lote {i}): {exc}", "error")
        return results

    def _fetch_batch(self, mod_ids: List[str]) -> List[dict]:
        params: Dict[str, str] = {"itemcount": str(len(mod_ids))}
        for idx, mid in enumerate(mod_ids):
            params[f"publishedfileids[{idx}]"] = mid

        data_encoded = "&".join(f"{k}={v}" for k, v in params.items())
        data_bytes = data_encoded.encode("utf-8")

        req = urllib.request.Request(
            _STEAM_API_URL,
            data=data_bytes,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = json.loads(resp.read().decode("utf-8"))

        return raw.get("response", {}).get("publishedfiledetails", [])

    def _log(self, msg: str, level: str = "info") -> None:
        self._on_log(msg, level)
