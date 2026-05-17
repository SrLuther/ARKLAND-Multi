"""
Gerenciador de BUFFs de rates temporários para servidores ARK: Survival Evolved.

BUFFs são eventos globais temporários que alteram multiplicadores do servidor
automaticamente com início e fim programados, equivalentes aos eventos oficiais
da Studio Wildcard.
"""
from __future__ import annotations

import json
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .ark_ini import ArkIniManager, get_ini_path
from .rcon_client import RconClient

# ── Fuso horário de Brasília (UTC-3 fixo — BR não usa horário de verão desde 2019)
_TZ_BRASILIA = timezone(timedelta(hours=-3))


def now_brasilia() -> datetime:
    """Retorna datetime atual no fuso de Brasília (naive, sem tzinfo)."""
    return datetime.now(tz=_TZ_BRASILIA).replace(tzinfo=None)


# ── Tipos de BUFF ──────────────────────────────────────────────────────────────
BUFF_TYPE_XP       = "XP"
BUFF_TYPE_DOMA     = "DOMA"
BUFF_TYPE_BREEDING = "BREEDING"
BUFF_TYPE_FARM     = "FARM"

BUFF_TYPE_LABELS: Dict[str, str] = {
    BUFF_TYPE_XP:       "XP ⭐",
    BUFF_TYPE_DOMA:     "DOMA 🦖",
    BUFF_TYPE_BREEDING: "BREEDING 🥚",
    BUFF_TYPE_FARM:     "FARM 🌿",
}

# ── Status ─────────────────────────────────────────────────────────────────────
BUFF_STATUS_SCHEDULED = "scheduled"
BUFF_STATUS_ACTIVE    = "active"
BUFF_STATUS_FINISHED  = "finished"
BUFF_STATUS_CANCELLED = "cancelled"

BUFF_MAX_DAYS = 30

# ── Definição dos campos de rate por tipo ──────────────────────────────────────
# (campo_python, label_exibido, dica_inverso)
BUFF_RATE_FIELDS: Dict[str, List[tuple]] = {
    BUFF_TYPE_XP: [
        ("xp_multiplier",          "Exp. Geral",      False),
        ("kill_xp_multiplier",     "XP por Kill",     False),
        ("harvest_xp_multiplier",  "XP por Coleta",   False),
        ("craft_xp_multiplier",    "XP por Crafting", False),
    ],
    BUFF_TYPE_DOMA: [
        ("taming_speed_multiplier", "Velocidade de Tame", False),
    ],
    BUFF_TYPE_BREEDING: [
        ("baby_mature_speed_multiplier",        "Maturação",         False),
        ("egg_hatch_speed_multiplier",          "Incubação",         False),
        ("mating_interval_multiplier",          "Interval. Acasalamento", True),
        ("baby_cuddle_interval_multiplier",     "Interval. Cuddle",  True),
        ("baby_imprinting_stat_scale_multiplier", "Bônus Imprint",   False),
    ],
    BUFF_TYPE_FARM: [
        ("harvest_amount_multiplier",          "Qtd. Recursos",  False),
        ("harvest_health_multiplier",          "Resist. Nodo",   False),
        ("resource_respawn_period_multiplier", "Respawn",        True),
    ],
}


def _quick_preset_for(multiplier: int) -> Dict[str, Dict[str, float]]:
    """Retorna valores {tipo: {campo: valor}} para o multiplicador rápido."""
    m = float(multiplier)
    inv = round(1.0 / m, 4)
    return {
        BUFF_TYPE_XP: {
            "xp_multiplier":         m,
            "kill_xp_multiplier":    m,
            "harvest_xp_multiplier": m,
            "craft_xp_multiplier":   m,
        },
        BUFF_TYPE_DOMA: {
            "taming_speed_multiplier": m,
        },
        BUFF_TYPE_BREEDING: {
            "baby_mature_speed_multiplier":          m,
            "egg_hatch_speed_multiplier":            m,
            "mating_interval_multiplier":            inv,
            "baby_cuddle_interval_multiplier":       inv,
            "baby_imprinting_stat_scale_multiplier": 1.0,
        },
        BUFF_TYPE_FARM: {
            "harvest_amount_multiplier":          m,
            "harvest_health_multiplier":          round(m / 2.5, 2),
            "resource_respawn_period_multiplier": inv,
        },
    }


QUICK_PRESETS: Dict[int, Dict[str, Dict[str, float]]] = {
    5:  _quick_preset_for(5),
    10: _quick_preset_for(10),
    15: _quick_preset_for(15),
}


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class BuffRates:
    """Multiplicadores a aplicar durante o BUFF. None = campo não modificado."""
    # XP
    xp_multiplier:              Optional[float] = None
    kill_xp_multiplier:         Optional[float] = None
    harvest_xp_multiplier:      Optional[float] = None
    craft_xp_multiplier:        Optional[float] = None
    # DOMA
    taming_speed_multiplier:    Optional[float] = None
    # BREEDING
    mating_interval_multiplier:            Optional[float] = None
    egg_hatch_speed_multiplier:            Optional[float] = None
    baby_mature_speed_multiplier:          Optional[float] = None
    baby_cuddle_interval_multiplier:       Optional[float] = None
    baby_imprinting_stat_scale_multiplier: Optional[float] = None
    # FARM
    harvest_amount_multiplier:             Optional[float] = None
    harvest_health_multiplier:             Optional[float] = None
    resource_respawn_period_multiplier:    Optional[float] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> "BuffRates":
        valid = set(cls.__dataclass_fields__)
        return cls(**{k: float(v) for k, v in data.items() if k in valid and v is not None})

    def summary(self) -> str:
        """Resumo legível dos rates definidos."""
        parts = []
        for fields in BUFF_RATE_FIELDS.values():
            for fname, label, inv in fields:
                v = getattr(self, fname)
                if v is not None:
                    parts.append(f"{label}: {v}x" if not inv else f"{label}: {v}")
        return "  |  ".join(parts) if parts else "—"


@dataclass
class BuffPreset:
    """Configuração de rates reutilizável (template/preset)."""
    id: str
    name: str
    types: List[str]
    rates: BuffRates

    def to_dict(self) -> dict:
        return {
            "id":    self.id,
            "name":  self.name,
            "types": self.types,
            "rates": self.rates.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BuffPreset":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            types=data.get("types", []),
            rates=BuffRates.from_dict(data.get("rates", {})),
        )


@dataclass
class BuffEvent:
    """Evento de BUFF: agendado, ativo, finalizado ou cancelado."""
    id: str
    name: str
    server_id: str
    types: List[str]
    rates: BuffRates
    start_dt: str    # ISO 8601
    end_dt: str      # ISO 8601
    status: str      # BUFF_STATUS_*
    preset_id: Optional[str] = None
    backup_path: Optional[str] = None

    def start_datetime(self) -> datetime:
        return datetime.fromisoformat(self.start_dt)

    def end_datetime(self) -> datetime:
        return datetime.fromisoformat(self.end_dt)

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "name":        self.name,
            "server_id":   self.server_id,
            "types":       self.types,
            "rates":       self.rates.to_dict(),
            "start_dt":    self.start_dt,
            "end_dt":      self.end_dt,
            "status":      self.status,
            "preset_id":   self.preset_id,
            "backup_path": self.backup_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BuffEvent":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            server_id=data.get("server_id", ""),
            types=data.get("types", []),
            rates=BuffRates.from_dict(data.get("rates", {})),
            start_dt=data.get("start_dt", ""),
            end_dt=data.get("end_dt", ""),
            status=data.get("status", BUFF_STATUS_SCHEDULED),
            preset_id=data.get("preset_id"),
            backup_path=data.get("backup_path"),
        )


# ══════════════════════════════════════════════════════════════════════════════

class BuffManager:
    """
    Gerencia BUFFs de rates temporários.

    Thread-safe. Possui scheduler automático (verificação a cada 30s) que ativa
    e desativa BUFFs automaticamente com base nos horários configurados.
    """

    def __init__(
        self,
        data_dir: Path,
        get_server_config,    # Callable[[str], Optional[ServerConfig]]
        start_server,         # Callable[[str], None]
        stop_server,          # Callable[[str], None]
        get_server_status,    # Callable[[str], str]
        on_log: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self._data_dir          = data_dir
        self._get_server_config = get_server_config
        self._start_server      = start_server
        self._stop_server       = stop_server
        self._get_server_status = get_server_status
        self._on_log            = on_log or (lambda m, lvl: None)

        self._buffs_file   = data_dir / "buffs.json"
        self._presets_file = data_dir / "buff_presets.json"
        self._backups_dir  = data_dir / "backups" / "buffs"

        self._events:  List[BuffEvent]  = []
        self._presets: List[BuffPreset] = []
        self._lock = threading.Lock()
        self._change_callbacks: List[Callable] = []

        self._load()

        self._stop_evt    = threading.Event()
        self._sched_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True, name="ARKBuffScheduler"
        )
        self._sched_thread.start()

    # ── Change callbacks ───────────────────────────────────────────────────────

    def add_change_callback(self, cb: Callable) -> None:
        self._change_callbacks.append(cb)

    def _notify(self) -> None:
        for cb in self._change_callbacks:
            try:
                cb()
            except Exception:
                pass

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        self._events, self._presets = [], []
        for path, dest, cls in (
            (self._buffs_file,   self._events,   BuffEvent),
            (self._presets_file, self._presets,  BuffPreset),
        ):
            if not path.exists():
                continue
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    for item in json.load(fh):
                        try:
                            dest.append(cls.from_dict(item))  # type: ignore[arg-type]
                        except Exception:
                            pass
            except Exception:
                pass

    def _save(self) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        with open(self._buffs_file, "w", encoding="utf-8") as fh:
            json.dump([e.to_dict() for e in self._events], fh, indent=2, ensure_ascii=False)
        with open(self._presets_file, "w", encoding="utf-8") as fh:
            json.dump([p.to_dict() for p in self._presets], fh, indent=2, ensure_ascii=False)

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_events(self, server_id: Optional[str] = None) -> List[BuffEvent]:
        with self._lock:
            if server_id:
                return [e for e in self._events if e.server_id == server_id]
            return list(self._events)

    def get_active_event(self, server_id: str) -> Optional[BuffEvent]:
        with self._lock:
            for e in self._events:
                if e.server_id == server_id and e.status == BUFF_STATUS_ACTIVE:
                    return e
        return None

    def get_scheduled_events(self, server_id: Optional[str] = None) -> List[BuffEvent]:
        with self._lock:
            evts = [
                e for e in self._events
                if e.status == BUFF_STATUS_SCHEDULED
                and (server_id is None or e.server_id == server_id)
            ]
        return sorted(evts, key=lambda e: e.start_dt)

    def get_finished_events(self, server_id: Optional[str] = None, limit: int = 20) -> List[BuffEvent]:
        with self._lock:
            evts = [
                e for e in self._events
                if e.status in (BUFF_STATUS_FINISHED, BUFF_STATUS_CANCELLED)
                and (server_id is None or e.server_id == server_id)
            ]
        evts.sort(key=lambda e: e.end_dt, reverse=True)
        return evts[:limit]

    def get_presets(self) -> List[BuffPreset]:
        with self._lock:
            return list(self._presets)

    def validate_event(self, event: BuffEvent) -> Optional[str]:
        """Valida um evento. Retorna mensagem de erro ou None se válido."""
        if not event.name.strip():
            return "Informe o nome do BUFF."
        if not event.types:
            return "Selecione ao menos um tipo de BUFF."
        try:
            start = event.start_datetime()
            end   = event.end_datetime()
        except ValueError:
            return "Data/hora inválida."
        if end <= start:
            return "A data de término deve ser posterior ao início."
        if (end - start).total_seconds() / 86400 > BUFF_MAX_DAYS:
            return f"A duração máxima de um BUFF é de {BUFF_MAX_DAYS} dias."

        with self._lock:
            for ex in self._events:
                if ex.id == event.id:
                    continue
                if ex.server_id != event.server_id:
                    continue
                if ex.status in (BUFF_STATUS_FINISHED, BUFF_STATUS_CANCELLED):
                    continue
                try:
                    es, ee = ex.start_datetime(), ex.end_datetime()
                except ValueError:
                    continue
                if start < ee and end > es:
                    return (
                        f"Não é possível agendar este BUFF.\n"
                        f"Já existe um BUFF ativo ou programado neste intervalo:\n"
                        f'"{ex.name}" ({es.strftime("%d/%m %H:%M")} — {ee.strftime("%d/%m %H:%M")})'
                    )
        return None

    def add_event(self, event: BuffEvent) -> Optional[str]:
        """Adiciona evento. Retorna mensagem de erro ou None se sucesso."""
        err = self.validate_event(event)
        if err:
            return err
        with self._lock:
            self._events.append(event)
            self._save()
        self._notify()
        return None

    def cancel_event(self, event_id: str) -> None:
        with self._lock:
            for e in self._events:
                if e.id == event_id and e.status == BUFF_STATUS_SCHEDULED:
                    e.status = BUFF_STATUS_CANCELLED
                    break
            self._save()
        self._notify()

    def save_preset(self, preset: BuffPreset) -> None:
        with self._lock:
            for i, p in enumerate(self._presets):
                if p.id == preset.id:
                    self._presets[i] = preset
                    break
            else:
                self._presets.append(preset)
            self._save()
        self._notify()

    def delete_preset(self, preset_id: str) -> None:
        with self._lock:
            self._presets = [p for p in self._presets if p.id != preset_id]
            self._save()
        self._notify()

    # ── INI backup / restore / apply ──────────────────────────────────────────

    def _backup_ini(self, server_id: str, buff_name: str) -> Optional[str]:
        cfg = self._get_server_config(server_id)
        if not cfg or not cfg.install_dir:
            return None
        ts   = now_brasilia().strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in buff_name)
        bdir = self._backups_dir / safe / ts
        bdir.mkdir(parents=True, exist_ok=True)
        for fname in ("GameUserSettings.ini", "Game.ini"):
            src = get_ini_path(cfg.install_dir, fname)
            if src.exists():
                shutil.copy2(str(src), str(bdir / fname))
        self._on_log(f"[BUFF] Backup salvo em: {bdir}", "info")
        return str(bdir)

    def _restore_ini(self, server_id: str, backup_path: str) -> bool:
        cfg = self._get_server_config(server_id)
        if not cfg or not cfg.install_dir:
            return False
        bp = Path(backup_path)
        if not bp.exists():
            self._on_log(f"[BUFF] Backup não encontrado: {backup_path}", "error")
            return False
        for fname in ("GameUserSettings.ini", "Game.ini"):
            src = bp / fname
            dst = get_ini_path(cfg.install_dir, fname)
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dst))
        self._on_log("[BUFF] INI restaurado do backup.", "info")
        return True

    def _apply_rates(self, server_id: str, rates: BuffRates) -> bool:
        cfg = self._get_server_config(server_id)
        if not cfg or not cfg.install_dir:
            return False
        ini = ArkIniManager(cfg.install_dir)
        ini.load_game_user_settings(cfg)
        ini.load_game_ini(cfg)
        gs = cfg.game_settings
        for fname_group in BUFF_RATE_FIELDS.values():
            for field_name, _, _ in fname_group:
                val = getattr(rates, field_name, None)
                if val is not None:
                    setattr(gs, field_name, val)
        ini.save_game_user_settings(cfg)
        ini.save_game_ini(cfg)
        self._on_log("[BUFF] Rates aplicados nos INIs.", "info")
        return True

    # ── RCON ──────────────────────────────────────────────────────────────────

    def _rcon_broadcast(self, server_id: str, message: str) -> None:
        from .server_config import SERVER_STATUS_RUNNING
        cfg = self._get_server_config(server_id)
        if not cfg or not cfg.rcon_enabled or not cfg.rcon_password:
            return
        if self._get_server_status(server_id) != SERVER_STATUS_RUNNING:
            return
        try:
            client = RconClient("127.0.0.1", cfg.rcon_port, cfg.rcon_password)
            client.connect()
            client.send_command(f"ServerChat {message}")
            client.disconnect()
        except Exception as exc:
            self._on_log(f"[BUFF] RCON broadcast falhou: {exc}", "warning")

    # ── Wait helpers ──────────────────────────────────────────────────────────

    def _wait_stopped(self, server_id: str, timeout: int = 120) -> bool:
        from .server_config import SERVER_STATUS_STOPPED
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._get_server_status(server_id) == SERVER_STATUS_STOPPED:
                return True
            time.sleep(2)
        return False

    # ── Activation / deactivation workers ─────────────────────────────────────

    def _activate_worker(self, event: BuffEvent) -> None:
        self._on_log(f"[BUFF] Ativando BUFF: '{event.name}'", "info")

        # 1. Marca como ativo imediatamente (evita dupla ativação)
        with self._lock:
            for e in self._events:
                if e.id == event.id:
                    e.status = BUFF_STATUS_ACTIVE
                    break
            self._save()
        self._notify()

        # 2. Broadcast e aguarda
        self._rcon_broadcast(
            event.server_id,
            "[BUFF] Servidor reiniciará para ativação de rates especiais.",
        )
        time.sleep(10)

        # 3. Para o servidor
        self._stop_server(event.server_id)
        if not self._wait_stopped(event.server_id):
            self._on_log("[BUFF] Timeout aguardando parada do servidor.", "warning")

        # 4. Backup dos INIs originais
        backup_path = self._backup_ini(event.server_id, event.name)

        # 5. Aplica rates
        self._apply_rates(event.server_id, event.rates)

        # 6. Salva caminho do backup
        with self._lock:
            for e in self._events:
                if e.id == event.id:
                    e.backup_path = backup_path
                    break
            self._save()

        # 7. Liga o servidor
        self._start_server(event.server_id)
        self._notify()
        self._on_log(f"[BUFF] BUFF '{event.name}' ativado com sucesso.", "info")

    def _deactivate_worker(self, event: BuffEvent) -> None:
        self._on_log(f"[BUFF] Desativando BUFF: '{event.name}'", "info")

        # 1. Broadcast e aguarda
        self._rcon_broadcast(
            event.server_id,
            "[BUFF] Evento finalizado. Restaurando configurações do servidor.",
        )
        time.sleep(10)

        # 2. Para o servidor
        self._stop_server(event.server_id)
        if not self._wait_stopped(event.server_id):
            self._on_log("[BUFF] Timeout aguardando parada do servidor.", "warning")

        # 3. Restaura INI do backup
        if event.backup_path:
            self._restore_ini(event.server_id, event.backup_path)
        else:
            self._on_log("[BUFF] Nenhum backup disponível para restaurar.", "warning")

        # 4. Liga o servidor
        self._start_server(event.server_id)

        # 5. Marca como finalizado
        with self._lock:
            for e in self._events:
                if e.id == event.id:
                    e.status = BUFF_STATUS_FINISHED
                    break
            self._save()
        self._notify()
        self._on_log(f"[BUFF] BUFF '{event.name}' finalizado.", "info")

    # ── Scheduler ─────────────────────────────────────────────────────────────

    def _scheduler_loop(self) -> None:
        while not self._stop_evt.is_set():
            try:
                self._tick()
            except Exception as exc:
                self._on_log(f"[BUFF] Erro no scheduler: {exc}", "error")
            self._stop_evt.wait(30)

    def _tick(self) -> None:
        now = now_brasilia()
        to_activate: List[BuffEvent]   = []
        to_deactivate: List[BuffEvent] = []

        with self._lock:
            for e in self._events:
                if e.status == BUFF_STATUS_SCHEDULED:
                    try:
                        if e.start_datetime() <= now:
                            to_activate.append(e)
                    except ValueError:
                        pass
                elif e.status == BUFF_STATUS_ACTIVE:
                    try:
                        if e.end_datetime() <= now:
                            to_deactivate.append(e)
                    except ValueError:
                        pass

        for e in to_activate:
            threading.Thread(
                target=self._activate_worker,
                args=(e,),
                daemon=True,
                name=f"ARKBuffActivate-{e.id[:8]}",
            ).start()

        for e in to_deactivate:
            threading.Thread(
                target=self._deactivate_worker,
                args=(e,),
                daemon=True,
                name=f"ARKBuffDeactivate-{e.id[:8]}",
            ).start()

    def stop(self) -> None:
        """Para o scheduler. Chamar ao fechar a aplicação."""
        self._stop_evt.set()
