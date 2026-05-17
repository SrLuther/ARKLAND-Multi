"""
Sistema de log de alterações do ARKLAND - Server Manager.
Registra cada mudança de configuração com timestamp, campo e valores anterior/novo.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List

_TZ_BR = timezone(timedelta(hours=-3))


def _now_br() -> str:
    return datetime.now(tz=_TZ_BR).strftime("%d/%m/%Y %H:%M")


class ChangeLogger:
    """Grava e lê o histórico de alterações de um servidor em um arquivo JSONL."""

    def __init__(self, log_dir: Path, server_id: str) -> None:
        self._path = log_dir / f"{server_id}_changes.jsonl"

    # ── escrita ───────────────────────────────────────────────────────────────

    def log(self, tab: str, label: str, old_val, new_val) -> None:
        """Registra uma alteração se old_val != new_val (como string)."""
        old_s = str(old_val) if old_val is not None else ""
        new_s = str(new_val) if new_val is not None else ""
        if old_s == new_s:
            return
        entry = {
            "ts": _now_br(),
            "tab": tab,
            "label": label,
            "old": old_s,
            "new": new_s,
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def log_batch(self, changes: List[tuple]) -> None:
        """Registra múltiplas alterações de uma vez.

        Cada item em ``changes`` deve ser ``(tab, label, old_val, new_val)``.
        """
        for tab, label, old_val, new_val in changes:
            self.log(tab, label, old_val, new_val)

    # ── leitura ───────────────────────────────────────────────────────────────

    def read_all(self) -> List[dict]:
        """Retorna todas as entradas em ordem decrescente (mais recente primeiro)."""
        if not self._path.exists():
            return []
        entries: List[dict] = []
        try:
            with open(self._path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except OSError:
            pass
        return list(reversed(entries))

    def clear(self) -> None:
        """Remove o arquivo de log."""
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            pass

    # ── utilitário ────────────────────────────────────────────────────────────

    @property
    def log_path(self) -> Path:
        return self._path


def snapshot_server(srv) -> dict:
    """
    Tira um snapshot dos campos principais de ``ServerConfig`` para comparação.
    Retorna um dict plano com (field_path → valor).
    """
    gs = srv.game_settings
    return {
        # Geral
        ("Geral", "Nome interno"):          srv.name,
        ("Geral", "Nome do servidor"):      srv.server_name,
        ("Geral", "Mapa"):                  srv.map,
        ("Geral", "Porta do servidor"):     srv.server_port,
        ("Geral", "Porta de Query"):        srv.query_port,
        ("Geral", "Porta RCON"):            srv.rcon_port,
        ("Geral", "Max. jogadores"):        srv.max_players,
        ("Geral", "Evento ativo"):          srv.active_event,
        ("Geral", "Salvamento automático"): srv.auto_save_period,
        ("Geral", "RCON habilitado"):       srv.rcon_enabled,
        ("Geral", "BattlEye"):             srv.use_battleye,
        ("Geral", "Reiniciar em crash"):   srv.auto_restart_on_crash,
        ("Geral", "Atualizar ao iniciar"): srv.auto_update_on_start,
        ("Geral", "Whitelist ativa"):      srv.whitelist_only,
        # Jogo
        ("Jogo", "Dificuldade (offset)"):          gs.difficulty_offset,
        ("Jogo", "Dificuldade máxima"):            gs.override_official_difficulty,
        ("Jogo", "Multiplicador de XP"):           gs.xp_multiplier,
        ("Jogo", "XP de abate"):                   gs.kill_xp_multiplier,
        ("Jogo", "XP de coleta"):                  gs.harvest_xp_multiplier,
        ("Jogo", "XP de craft"):                   gs.craft_xp_multiplier,
        ("Jogo", "Velocidade de domesticação"):    gs.taming_speed_multiplier,
        ("Jogo", "Quantidade de coleta"):          gs.harvest_amount_multiplier,
        ("Jogo", "Qtd de dinos"):                  gs.dino_count_multiplier,
        ("Jogo", "Max. dinos domados"):            gs.max_tamed_dinos,
        ("Jogo", "Dano do jogador"):               gs.player_damage_multiplier,
        ("Jogo", "Resistência do jogador"):        gs.player_resistance_multiplier,
        ("Jogo", "Dano dos dinos"):                gs.dino_damage_multiplier,
        ("Jogo", "Resistência dos dinos"):         gs.dino_resistance_multiplier,
        ("Jogo", "Velocidade de maturação"):       gs.baby_mature_speed_multiplier,
        ("Jogo", "Intervalo de acasalamento"):     gs.mating_interval_multiplier,
        ("Jogo", "Tamanho de pilha de itens"):     gs.item_stack_size_multiplier,
        ("Jogo", "Tempo de deterioração"):         gs.spoiling_time_multiplier,
        ("Jogo", "Dano a estruturas"):             gs.structure_damage_multiplier,
        ("Jogo", "Modo PvP"):                      gs.server_pvp,
        ("Jogo", "Modo Hardcore"):                 gs.server_hardcore,
        ("Jogo", "Nível máx. jogador"):            gs.player_level_cap,
        ("Jogo", "Nível máx. dino"):               gs.dino_level_cap,
        ("Jogo", "Tamanho máx. de tribo"):         gs.max_tribe_size,
        ("Jogo", "Tempo de respawn de recursos"):  gs.resource_respawn_period_multiplier,
        ("Jogo", "Crescimento de plantações"):     gs.crop_growth_speed_multiplier,
        ("Jogo", "Velocidade de eclosão"):         gs.egg_hatch_speed_multiplier,
        ("Jogo", "Imprintação de bebê"):           gs.baby_imprinting_stat_scale_multiplier,
    }


def diff_snapshots(logger: ChangeLogger, before: dict, after: dict) -> int:
    """
    Compara dois snapshots e chama ``logger.log`` para cada campo alterado.
    Retorna a quantidade de mudanças registradas.
    """
    count = 0
    for (tab, label), old_val in before.items():
        new_val = after.get((tab, label), old_val)
        if str(old_val) != str(new_val):
            logger.log(tab, label, old_val, new_val)
            count += 1
    return count
