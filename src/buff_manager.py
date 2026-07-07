"""
Gerenciador de Eventos Sazonais (rates temporários) para servidores ARK: Survival Evolved.

Eventos sazonais são eventos globais temporários que alteram multiplicadores do servidor
automaticamente com início e fim programados, equivalentes aos eventos oficiais
da Studio Wildcard.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .ark_ini import ArkIniManager, get_ini_path
from .buff_ini_backups import (
    backup_ini_files,
    list_ini_backups,
    restore_ini_from_backup,
)
from .rcon_client import RconClient

# Multiplicador base assumido do servidor (rates nos INIs = base × este valor)
DEFAULT_SERVER_RATE_MULT = 5.0
EMERGENCY_RESTORE_DELAY_SEC = 300  # 5 minutos
_SAVEWORLD_WAIT_SEC = 15

_SECTOR_SKIP_FIELDS = frozenset({"baby_imprinting_stat_scale_multiplier"})
_FIELD_ALIASES: Dict[str, List[str]] = {
    "baby_imprinting_stat_scale_multiplier": ["baby_imprinting_stat_scale"],
}

# ── Fuso horário de Brasília (UTC-3 fixo — BR não usa horário de verão desde 2019)
_TZ_BRASILIA = timezone(timedelta(hours=-3))


def now_brasilia() -> datetime:
    """Retorna datetime atual no fuso de Brasília (naive, sem tzinfo)."""
    return datetime.now(tz=_TZ_BRASILIA).replace(tzinfo=None)


# ── Tipos de evento ──────────────────────────────────────────────────────────────
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

# ── Recorrência ──────────────────────────────────────────────────────────────
BUFF_RECURRENCE_NONE    = None
BUFF_RECURRENCE_DAILY   = "daily"
BUFF_RECURRENCE_WEEKLY  = "weekly"
BUFF_RECURRENCE_WEEKEND = "weekend"

BUFF_RECURRENCE_LABELS: Dict[Optional[str], str] = {
    None:                  "Sem repetição",
    BUFF_RECURRENCE_DAILY:   "Diariamente",
    BUFF_RECURRENCE_WEEKLY:  "Semanalmente",
    BUFF_RECURRENCE_WEEKEND: "Fins de semana",
}

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


def stack_buff_rate(base: float, buff_factor: float) -> float:
    """Multiplica a rate base pelo fator (legado / snapshot)."""
    if base <= 0:
        base = 1.0
    return round(base * buff_factor, 4)


def compute_buff_field_value(
    current: float,
    target_mult: float,
    *,
    is_inverse: bool,
    server_mult: float = DEFAULT_SERVER_RATE_MULT,
) -> float:
    """
    Calcula valor INI alvo a partir do valor atual e multiplicador desejado.

    Normal: base = current / server_mult; new = base × target
    Inverso: base = current × server_mult; new = base / target
    """
    if current <= 0:
        current = 1.0
    if server_mult <= 0:
        server_mult = DEFAULT_SERVER_RATE_MULT
    if target_mult <= 0:
        target_mult = 1.0
    if is_inverse:
        return round((current * server_mult) / target_mult, 4)
    return round((current / server_mult) * target_mult, 4)


def _read_rate_from_config(cfg: object, field_name: str) -> float:
    """Lê o valor atual de um multiplicador na config do servidor."""
    for name in [field_name] + _FIELD_ALIASES.get(field_name, []):
        if hasattr(cfg, "game_settings"):
            val = getattr(cfg.game_settings, name, None)
        else:
            val = getattr(cfg, name, None)
        if val is not None:
            try:
                f = float(val)
                if f > 0:
                    return f
            except (TypeError, ValueError):
                pass
    return 1.0


def _sector_mult_for_type(sector_mults: "BuffSectorMults", buff_type: str) -> Optional[float]:
    mapping = {
        BUFF_TYPE_XP: "xp",
        BUFF_TYPE_DOMA: "doma",
        BUFF_TYPE_BREEDING: "breeding",
        BUFF_TYPE_FARM: "farm",
    }
    attr = mapping.get(buff_type)
    if not attr:
        return None
    val = getattr(sector_mults, attr, None)
    return float(val) if val is not None else None


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class BuffSectorMults:
    """Multiplicadores alvo por setor (XP, Doma, Breeding, Farm)."""
    xp:       Optional[float] = None
    doma:     Optional[float] = None
    breeding: Optional[float] = None
    farm:     Optional[float] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> "BuffSectorMults":
        if not data:
            return cls()
        valid = set(cls.__dataclass_fields__)
        return cls(**{k: float(v) for k, v in data.items() if k in valid and v is not None})

    def summary(self, types: Optional[List[str]] = None) -> str:
        labels = {
            "xp": "XP",
            "doma": "Doma",
            "breeding": "Breeding",
            "farm": "Farm",
        }
        type_to_attr = {
            BUFF_TYPE_XP: "xp",
            BUFF_TYPE_DOMA: "doma",
            BUFF_TYPE_BREEDING: "breeding",
            BUFF_TYPE_FARM: "farm",
        }
        parts: List[str] = []
        attrs = types or list(BUFF_TYPE_LABELS.keys())
        for t in attrs:
            attr = type_to_attr.get(t)
            if not attr:
                continue
            val = getattr(self, attr, None)
            if val is not None:
                parts.append(f"{labels[attr]}: {val:g}x")
        return "  |  ".join(parts) if parts else "—"

    def has_any(self) -> bool:
        return any(
            getattr(self, f) is not None
            for f in ("xp", "doma", "breeding", "farm")
        )


def _quick_preset_sectors(multiplier: int) -> BuffSectorMults:
    """Preset rápido: mesmo multiplicador em todos os setores."""
    m = float(multiplier)
    return BuffSectorMults(xp=m, doma=m, breeding=m, farm=m)


QUICK_PRESET_MULTS: Dict[int, BuffSectorMults] = {
    5:  _quick_preset_sectors(5),
    10: _quick_preset_sectors(10),
    15: _quick_preset_sectors(15),
}

# Compatibilidade com imports antigos
QUICK_PRESETS = QUICK_PRESET_MULTS


@dataclass
class BuffRates:
    """Multiplicadores a aplicar durante o evento. None = campo não modificado."""
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
    sector_mults: BuffSectorMults = field(default_factory=BuffSectorMults)
    broadcast_message: str = ""
    broadcast_interval_min: int = 0

    def to_dict(self) -> dict:
        d = {
            "id":    self.id,
            "name":  self.name,
            "types": self.types,
            "rates": self.rates.to_dict(),
            "sector_mults": self.sector_mults.to_dict(),
        }
        if self.broadcast_message:
            d["broadcast_message"] = self.broadcast_message
        if self.broadcast_interval_min:
            d["broadcast_interval_min"] = self.broadcast_interval_min
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "BuffPreset":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            types=data.get("types", []),
            rates=BuffRates.from_dict(data.get("rates", {})),
            sector_mults=BuffSectorMults.from_dict(data.get("sector_mults", {})),
            broadcast_message=data.get("broadcast_message", ""),
            broadcast_interval_min=int(data.get("broadcast_interval_min", 0) or 0),
        )


@dataclass
class BuffEvent:
    """Evento sazonal: agendado, ativo, finalizado ou cancelado."""
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
    recurrence: Optional[str] = None  # BUFF_RECURRENCE_*
    sector_mults: BuffSectorMults = field(default_factory=BuffSectorMults)
    broadcast_message: str = ""
    broadcast_interval_min: int = 0

    def start_datetime(self) -> datetime:
        return datetime.fromisoformat(self.start_dt)

    def end_datetime(self) -> datetime:
        return datetime.fromisoformat(self.end_dt)

    def duration(self) -> timedelta:
        return self.end_datetime() - self.start_datetime()

    def rates_summary(self) -> str:
        if self.sector_mults.has_any():
            return self.sector_mults.summary(self.types)
        return self.rates.summary()

    def to_dict(self) -> dict:
        d = {
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
            "recurrence":  self.recurrence,
            "sector_mults": self.sector_mults.to_dict(),
        }
        if self.broadcast_message:
            d["broadcast_message"] = self.broadcast_message
        if self.broadcast_interval_min:
            d["broadcast_interval_min"] = self.broadcast_interval_min
        return d

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
            recurrence=data.get("recurrence"),
            sector_mults=BuffSectorMults.from_dict(data.get("sector_mults", {})),
            broadcast_message=data.get("broadcast_message", ""),
            broadcast_interval_min=int(data.get("broadcast_interval_min", 0) or 0),
        )


# ══════════════════════════════════════════════════════════════════════════════

class BuffManager:
    """
    Gerencia Eventos Sazonais de rates temporários.

    Thread-safe. Possui scheduler automático (verificação a cada 30s) que ativa
    e desativa eventos automaticamente com base nos horários configurados.
    """

    def __init__(
        self,
        data_dir: Path,
        get_server_config,    # Callable[[str], Optional[ServerConfig]]
        start_server,         # Callable[[str], None]
        stop_server,          # Callable[[str], None]
        get_server_status,    # Callable[[str], str]
        on_log: Optional[Callable[[str, str], None]] = None,
        discord_notify: Optional[Callable] = None,  # Callable[[str, BuffEvent], None]
        persist_server_config: Optional[Callable[[str, object], None]] = None,
        list_all_servers: Optional[Callable[[], List[str]]] = None,
        server_mult: float = DEFAULT_SERVER_RATE_MULT,
    ) -> None:
        self._data_dir          = data_dir
        self._get_server_config = get_server_config
        self._start_server      = start_server
        self._stop_server       = stop_server
        self._get_server_status = get_server_status
        self._persist_server_config = persist_server_config
        self._list_all_servers  = list_all_servers or (lambda: [])
        self._server_mult       = server_mult if server_mult > 0 else DEFAULT_SERVER_RATE_MULT
        self._on_log            = on_log or (lambda m, lvl: None)
        self._discord_notify    = discord_notify  # (action, event) → None

        self._buffs_file   = data_dir / "buffs.json"
        self._presets_file = data_dir / "buff_presets.json"

        self._events:  List[BuffEvent]  = []
        self._presets: List[BuffPreset] = []
        self._lock = threading.Lock()
        self._change_callbacks: List[Callable] = []
        self._activating: set[str] = set()
        self._deactivating: set[str] = set()
        self._rcon_warnings_sent: set = set()
        self._buff_broadcast_last: Dict[str, float] = {}
        self._emergency_active = False
        self._emergency_deadline: float = 0.0
        self._emergency_server_ids: List[str] = []
        self._emergency_backup_paths: Dict[str, str] = {}

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
        events_file = self._buffs_file
        if not events_file.exists():
            alias = self._data_dir / "seasonal_events.json"
            if alias.exists():
                events_file = alias
        presets_file = self._presets_file
        if not presets_file.exists():
            alias = self._data_dir / "seasonal_event_presets.json"
            if alias.exists():
                presets_file = alias
        for path, dest, cls in (
            (events_file,   self._events,   BuffEvent),
            (presets_file, self._presets,  BuffPreset),
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

    def get_activating_event(self, server_id: str) -> Optional[BuffEvent]:
        """Evento agendado/ativo em processo de ativação (reinício + INI)."""
        with self._lock:
            for e in self._events:
                if e.server_id == server_id and e.id in self._activating:
                    return e
        return None

    def is_activating(self, event_id: str) -> bool:
        with self._lock:
            return event_id in self._activating

    def is_deactivating(self, event_id: str) -> bool:
        with self._lock:
            return event_id in self._deactivating

    def get_scheduled_events(self, server_id: Optional[str] = None) -> List[BuffEvent]:
        with self._lock:
            evts = [
                e for e in self._events
                if e.status == BUFF_STATUS_SCHEDULED
                and e.id not in self._activating
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
            return "Informe o nome do evento."
        if not event.types:
            return "Selecione ao menos um tipo de evento."
        if not event.sector_mults.has_any() and not event.rates.to_dict():
            return "Informe ao menos um multiplicador de setor."
        try:
            start = event.start_datetime()
            end   = event.end_datetime()
        except ValueError:
            return "Data/hora inválida."
        if end <= start:
            return "A data de término deve ser posterior ao início."
        if (end - start).total_seconds() / 86400 > BUFF_MAX_DAYS:
            return f"A duração máxima de um evento sazonal é de {BUFF_MAX_DAYS} dias."

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
                        f"Não é possível agendar este evento.\n"
                        f"Já existe um evento ativo ou programado neste intervalo:\n"
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

    def update_event(self, event: BuffEvent) -> Optional[str]:
        """Substitui um evento agendado existente. Retorna erro ou None."""
        with self._lock:
            existing = next((e for e in self._events if e.id == event.id), None)
            if not existing:
                return "Evento não encontrado."
            if existing.status != BUFF_STATUS_SCHEDULED:
                return "Só é possível editar eventos com status 'agendado'."
        err = self.validate_event(event)
        if err:
            return err
        with self._lock:
            for i, e in enumerate(self._events):
                if e.id == event.id:
                    self._events[i] = event
                    break
            # Remove avisos RCON associados ao evento editado
            self._rcon_warnings_sent = {
                k for k in self._rcon_warnings_sent
                if not k.startswith(event.id + ":")
            }
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

    def stop_active_event(self, event_id: str) -> Optional[str]:
        """Encerra um evento ativo: restaura INI do backup e reinicia o servidor."""
        with self._lock:
            event = next((e for e in self._events if e.id == event_id), None)
            if not event:
                return "Evento não encontrado."
            if event.status != BUFF_STATUS_ACTIVE:
                return "Só é possível encerrar eventos ativos."
            if event.id in self._deactivating:
                return "Evento já está sendo encerrado."
            self._deactivating.add(event.id)

        threading.Thread(
            target=self._deactivate_worker,
            args=(event,),
            kwargs={"cancelled": True},
            daemon=True,
            name=f"ARKBuffStop-{event_id[:8]}",
        ).start()
        self._notify()
        return None

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

    def list_ini_backups_for(self, server_id: str) -> List[Path]:
        cfg = self._get_server_config(server_id)
        if not cfg:
            return []
        return list_ini_backups(cfg)

    def get_emergency_state(self) -> Optional[dict]:
        with self._lock:
            if not self._emergency_active:
                return None
            return {
                "deadline": self._emergency_deadline,
                "server_ids": list(self._emergency_server_ids),
            }

    def start_emergency_restore(
        self,
        server_ids: List[str],
        backup_paths: Optional[Dict[str, str]] = None,
        *,
        cluster_wide_warning: bool = True,
    ) -> Optional[str]:
        """Restauração: aviso global (opcional) → aguarda 5 min → save/stop/restore/start."""
        if not server_ids:
            return "Nenhum servidor selecionado."
        with self._lock:
            if self._emergency_active:
                return "Já existe uma restauração de emergência em andamento."

        threading.Thread(
            target=self._emergency_restore_worker,
            args=(list(server_ids), backup_paths or {}),
            kwargs={"cluster_wide_warning": cluster_wide_warning},
            daemon=True,
            name="ARKBuffEmergency",
        ).start()
        return None

    # ── INI backup / restore / apply ──────────────────────────────────────────

    def _backup_ini(self, server_id: str, buff_name: str) -> Optional[str]:
        cfg = self._get_server_config(server_id)
        if not cfg:
            return None
        path = backup_ini_files(cfg, buff_name)
        if path:
            self._on_log(f"[Evento Sazonal] Backup INI (zip): {path}", "info")
        else:
            self._on_log("[Evento Sazonal] Falha ao criar backup INI.", "error")
        return path

    def _restore_ini(self, server_id: str, backup_path: str) -> bool:
        cfg = self._get_server_config(server_id)
        if not cfg:
            return False
        if not backup_path:
            backups = list_ini_backups(cfg)
            if not backups:
                self._on_log("[Evento Sazonal] Nenhum backup .ini disponível.", "error")
                return False
            backup_path = str(backups[0])
        ok = restore_ini_from_backup(cfg, backup_path)
        if ok:
            self._on_log(f"[Evento Sazonal] INI restaurado de: {backup_path}", "info")
        else:
            self._on_log(f"[Evento Sazonal] Falha ao restaurar backup: {backup_path}", "error")
        return ok

    def _apply_event_rates(self, server_id: str, event: BuffEvent) -> bool:
        return self._apply_rates(
            server_id,
            event.rates,
            types=event.types,
            sector_mults=event.sector_mults,
        )

    def _apply_rates(
        self,
        server_id: str,
        rates: BuffRates,
        *,
        types: Optional[List[str]] = None,
        sector_mults: Optional[BuffSectorMults] = None,
    ) -> bool:
        cfg = self._get_server_config(server_id)
        if not cfg or not getattr(cfg, "install_dir", ""):
            self._on_log("[Evento Sazonal] install_dir não configurado — rates não aplicados.", "error")
            return False

        use_sectors = sector_mults is not None and sector_mults.has_any()
        active_types = types or list(BUFF_RATE_FIELDS.keys())

        def _set_field(target: object, field_name: str, new_val: float) -> None:
            if hasattr(target, field_name):
                setattr(target, field_name, new_val)
                return
            for alias in _FIELD_ALIASES.get(field_name, []):
                if hasattr(target, alias):
                    setattr(target, alias, new_val)
                    return

        try:
            from .asm_engine.asm_server_config import AsmServerConfig

            ini = None
            if isinstance(cfg, AsmServerConfig):
                target_cfg = cfg
            elif hasattr(cfg, "game_settings"):
                ini = ArkIniManager(cfg.install_dir)
                ini.load_game_user_settings(cfg)
                ini.load_game_ini(cfg)
                target_cfg = cfg.game_settings
            else:
                self._on_log("[Evento Sazonal] Tipo de servidor não suportado para aplicar rates.", "error")
                return False

            for buff_type in active_types:
                fields = BUFF_RATE_FIELDS.get(buff_type, [])
                sector_target = (
                    _sector_mult_for_type(sector_mults, buff_type) if use_sectors else None
                )
                for field_name, _label, is_inv in fields:
                    if field_name in _SECTOR_SKIP_FIELDS:
                        continue
                    if use_sectors:
                        if sector_target is None:
                            continue
                        current = _read_rate_from_config(cfg, field_name)
                        new_val = compute_buff_field_value(
                            current,
                            sector_target,
                            is_inverse=is_inv,
                            server_mult=self._server_mult,
                        )
                        _set_field(target_cfg, field_name, new_val)
                        self._on_log(
                            f"[Evento Sazonal] {field_name}: {current} → {new_val} "
                            f"(setor {sector_target:g}x)",
                            "debug",
                        )
                    else:
                        buff_val = getattr(rates, field_name, None)
                        if buff_val is None:
                            continue
                        current = _read_rate_from_config(cfg, field_name)
                        stacked = stack_buff_rate(current, buff_val)
                        _set_field(target_cfg, field_name, stacked)

            if isinstance(cfg, AsmServerConfig):
                from .asm_engine.asm_ini_manager import write_ini
                write_ini(cfg)
                if self._persist_server_config:
                    self._persist_server_config(server_id, cfg)
            elif ini is not None:
                ini.save_game_user_settings(cfg)
                ini.save_game_ini(cfg)
        except Exception as exc:
            self._on_log(f"[Evento Sazonal] Falha ao aplicar rates: {exc}", "error")
            return False

        self._on_log("[Evento Sazonal] Rates aplicados e gravados nos INIs.", "info")
        return True

    @staticmethod
    def _cfg_rcon_password(cfg: object) -> str:
        return (
            getattr(cfg, "rcon_password", "") or getattr(cfg, "admin_password", "") or ""
        ).strip()

    # ── RCON ──────────────────────────────────────────────────────────────────

    def _rcon_broadcast(self, server_id: str, message: str) -> None:
        from .server_config import SERVER_STATUS_RUNNING
        cfg = self._get_server_config(server_id)
        pwd = self._cfg_rcon_password(cfg) if cfg else ""
        if not cfg or not cfg.rcon_enabled or not pwd:
            return
        if self._get_server_status(server_id) != SERVER_STATUS_RUNNING:
            return
        try:
            client = RconClient("127.0.0.1", cfg.rcon_port, pwd)
            client.connect()
            client.send_command(f"Broadcast {message}")
            client.disconnect()
        except Exception as exc:
            self._on_log(f"[Evento Sazonal] RCON broadcast falhou: {exc}", "warning")

    def _rcon_broadcast_all(self, message: str) -> None:
        for sid in self._list_all_servers():
            self._rcon_broadcast(sid, message)

    def _rcon_saveworld(self, server_id: str) -> None:
        from .server_config import SERVER_STATUS_RUNNING
        cfg = self._get_server_config(server_id)
        pwd = self._cfg_rcon_password(cfg) if cfg else ""
        if not cfg or not cfg.rcon_enabled or not pwd:
            return
        if self._get_server_status(server_id) != SERVER_STATUS_RUNNING:
            return
        try:
            client = RconClient("127.0.0.1", cfg.rcon_port, pwd)
            client.connect()
            client.send_command_safe("SaveWorld")
            client.disconnect()
        except Exception as exc:
            self._on_log(f"[Evento Sazonal] SaveWorld falhou ({server_id}): {exc}", "warning")

    def _graceful_stop(self, server_id: str) -> None:
        """SaveWorld + aguarda + para o servidor."""
        self._rcon_saveworld(server_id)
        time.sleep(_SAVEWORLD_WAIT_SEC)
        self._stop_server(server_id)

    def _build_buff_broadcast_message(self, event: BuffEvent) -> str:
        custom = (event.broadcast_message or "").strip()
        summary = event.rates_summary()
        if custom:
            return f"{custom}  |  Rates: {summary}"
        return f"[Evento Sazonal] ⚡ '{event.name}' ativo — {summary}"

    def _maybe_broadcast_active_buff(self, event: BuffEvent) -> None:
        interval = int(event.broadcast_interval_min or 0)
        if interval <= 0:
            return
        now = time.time()
        last = self._buff_broadcast_last.get(event.id, 0.0)
        if now - last < interval * 60:
            return
        self._buff_broadcast_last[event.id] = now
        self._rcon_broadcast(event.server_id, self._build_buff_broadcast_message(event))

    # ── Wait helpers ──────────────────────────────────────────────────────────

    def _wait_stopped(self, server_id: str, timeout: int = 180) -> bool:
        from .server_config import SERVER_STATUS_STOPPED
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._get_server_status(server_id) == SERVER_STATUS_STOPPED:
                return True
            time.sleep(2)
        return False

    def _wait_running(self, server_id: str, timeout: int = 300) -> bool:
        from .server_config import SERVER_STATUS_RUNNING
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._get_server_status(server_id) == SERVER_STATUS_RUNNING:
                return True
            time.sleep(3)
        return False

    # ── Activation / deactivation workers ─────────────────────────────────────

    def _activate_worker(self, event: BuffEvent) -> None:
        self._on_log(f"[Evento Sazonal] Ativando: '{event.name}'", "info")
        with self._lock:
            if event.id in self._activating:
                return
            self._activating.add(event.id)

        try:
            self._rcon_broadcast(
                event.server_id,
                "[Evento Sazonal] Servidor reiniciará para ativação de rates especiais.",
            )
            time.sleep(10)

            self._graceful_stop(event.server_id)
            if not self._wait_stopped(event.server_id):
                self._on_log("[Evento Sazonal] Timeout aguardando parada do servidor.", "warning")

            backup_path = self._backup_ini(event.server_id, event.name)
            if not self._apply_event_rates(event.server_id, event):
                raise RuntimeError("Falha ao aplicar rates nos INIs")

            with self._lock:
                for e in self._events:
                    if e.id == event.id:
                        e.backup_path = backup_path
                        break
                self._save()

            self._start_server(event.server_id)
            if not self._wait_running(event.server_id):
                raise RuntimeError("Servidor não voltou a ficar online após reinício")

            with self._lock:
                for e in self._events:
                    if e.id == event.id:
                        e.status = BUFF_STATUS_ACTIVE
                        break
                self._save()
            self._buff_broadcast_last[event.id] = time.time()
            self._notify()
            self._on_log(f"[Evento Sazonal] '{event.name}' ativado com sucesso.", "info")

            if self._discord_notify:
                try:
                    self._discord_notify("start", event)
                except Exception:
                    pass
        except Exception as exc:
            self._on_log(f"[Evento Sazonal] Falha ao ativar '{event.name}': {exc}", "error")
            with self._lock:
                for e in self._events:
                    if e.id == event.id and e.status != BUFF_STATUS_ACTIVE:
                        e.status = BUFF_STATUS_SCHEDULED
                        break
                self._save()
            self._notify()
        finally:
            with self._lock:
                self._activating.discard(event.id)

    def _deactivate_worker(self, event: BuffEvent, *, cancelled: bool = False) -> None:
        label = "cancelado" if cancelled else "finalizado"
        self._on_log(f"[Evento Sazonal] Desativando ({label}): '{event.name}'", "info")

        try:
            msg = (
                "[Evento Sazonal] Evento cancelado. Restaurando configurações do servidor."
                if cancelled
                else "[Evento Sazonal] Evento finalizado. Restaurando configurações do servidor."
            )
            self._rcon_broadcast(event.server_id, msg)
            time.sleep(10)

            self._graceful_stop(event.server_id)
            if not self._wait_stopped(event.server_id):
                self._on_log("[Evento Sazonal] Timeout aguardando parada do servidor.", "warning")

            restored = False
            if event.backup_path:
                restored = self._restore_ini(event.server_id, event.backup_path)
            if not restored:
                self._restore_ini(event.server_id, "")

            self._start_server(event.server_id)

            final_status = BUFF_STATUS_CANCELLED if cancelled else BUFF_STATUS_FINISHED
            with self._lock:
                for e in self._events:
                    if e.id == event.id:
                        e.status = final_status
                        break
                self._save()
            self._buff_broadcast_last.pop(event.id, None)
            self._notify()
            self._on_log(f"[Evento Sazonal] '{event.name}' {label}.", "info")

            if self._discord_notify:
                try:
                    self._discord_notify("end", event)
                except Exception:
                    pass

            if event.recurrence and not cancelled:
                self._reschedule_recurring(event)
        finally:
            with self._lock:
                self._deactivating.discard(event.id)

    def _emergency_restore_worker(
        self,
        server_ids: List[str],
        backup_paths: Dict[str, str],
        *,
        cluster_wide_warning: bool = True,
    ) -> None:
        with self._lock:
            self._emergency_active = True
            self._emergency_deadline = time.monotonic() + (
                EMERGENCY_RESTORE_DELAY_SEC if cluster_wide_warning else 0
            )
            self._emergency_server_ids = list(server_ids)
            self._emergency_backup_paths = dict(backup_paths)
        self._notify()

        if cluster_wide_warning:
            warn = (
                "[EMERGÊNCIA] Restauração de rates originais em 5 minutos. "
                "O servidor será reiniciado — salve seu progresso."
            )
            self._on_log("[BUFF] Emergência: aviso enviado a todos os servidores.", "warning")
            self._rcon_broadcast_all(warn)
            deadline = time.monotonic() + EMERGENCY_RESTORE_DELAY_SEC
            while time.monotonic() < deadline:
                if self._stop_evt.is_set():
                    break
                time.sleep(5)
        else:
            for sid in server_ids:
                self._rcon_broadcast(
                    sid,
                    "[BUFF] Restaurando configurações originais — servidor reiniciará em instantes.",
                )
            time.sleep(10)

        for sid in server_ids:
            self._on_log(f"[Evento Sazonal] Emergência: restaurando servidor {sid}…", "warning")
            self._graceful_stop(sid)
            if not self._wait_stopped(sid):
                self._on_log(f"[Evento Sazonal] Emergência: timeout parada ({sid}).", "warning")

            bp = backup_paths.get(sid, "")
            if not self._restore_ini(sid, bp):
                self._on_log(f"[Evento Sazonal] Emergência: falha ao restaurar INI ({sid}).", "error")

            active = self.get_active_event(sid)
            if active:
                with self._lock:
                    for e in self._events:
                        if e.id == active.id:
                            e.status = BUFF_STATUS_CANCELLED
                            break
                    self._save()

            self._start_server(sid)

        with self._lock:
            self._emergency_active = False
            self._emergency_deadline = 0.0
            self._emergency_server_ids = []
            self._emergency_backup_paths = {}
        self._notify()
        self._on_log("[Evento Sazonal] Restauração de emergência concluída.", "info")

    def _reschedule_recurring(self, event: BuffEvent) -> None:
        """Cria o próximo evento recorrente com base na recorrência configurada."""
        try:
            start = event.start_datetime()
            dur   = event.duration()
            rec   = event.recurrence

            if rec == BUFF_RECURRENCE_DAILY:
                next_start = start + timedelta(days=1)
            elif rec == BUFF_RECURRENCE_WEEKLY:
                next_start = start + timedelta(weeks=1)
            elif rec == BUFF_RECURRENCE_WEEKEND:
                # Próximo sábado a partir do início original
                days_ahead = (5 - start.weekday()) % 7  # 5 = sábado
                if days_ahead == 0:
                    days_ahead = 7
                next_start = start + timedelta(days=days_ahead)
            else:
                return

            next_end = next_start + dur
            new_event = BuffEvent(
                id=str(uuid.uuid4()),
                name=event.name,
                server_id=event.server_id,
                types=list(event.types),
                rates=event.rates,
                start_dt=next_start.isoformat(),
                end_dt=next_end.isoformat(),
                status=BUFF_STATUS_SCHEDULED,
                preset_id=event.preset_id,
                recurrence=event.recurrence,
                sector_mults=event.sector_mults,
                broadcast_message=event.broadcast_message,
                broadcast_interval_min=event.broadcast_interval_min,
            )
            err = self.add_event(new_event)
            if err:
                self._on_log(f"[Evento Sazonal] Não foi possível reagendar '{event.name}': {err}", "warning")
            else:
                self._on_log(
                    f"[Evento Sazonal] '{event.name}' reagendado para "
                    f"{next_start.strftime('%d/%m/%Y %H:%M')}.",
                    "info",
                )
        except Exception as exc:
            self._on_log(f"[Evento Sazonal] Erro ao reagendar: {exc}", "error")

    # ── Scheduler ─────────────────────────────────────────────────────────────

    def _scheduler_loop(self) -> None:
        while not self._stop_evt.is_set():
            try:
                self._tick()
            except Exception as exc:
                self._on_log(f"[Evento Sazonal] Erro no scheduler: {exc}", "error")
            self._stop_evt.wait(30)

    def _tick(self) -> None:
        now = now_brasilia()
        to_activate: List[BuffEvent]   = []
        to_deactivate: List[BuffEvent] = []
        to_warn: List[tuple] = []  # (event, label, key)
        active_broadcast: List[BuffEvent] = []

        with self._lock:
            for e in self._events:
                if e.status == BUFF_STATUS_SCHEDULED:
                    try:
                        start = e.start_datetime()
                        if start <= now:
                            to_activate.append(e)
                        else:
                            # Avisos antes do início
                            secs_left = (start - now).total_seconds()
                            for threshold, label in (
                                (900, "15 minutos"),
                                (300, "5 minutos"),
                                (60,  "1 minuto"),
                            ):
                                key = f"{e.id}:start:{threshold}"
                                if secs_left <= threshold and key not in self._rcon_warnings_sent:
                                    to_warn.append((e, label, key, "start"))
                    except ValueError:
                        pass
                elif e.status == BUFF_STATUS_ACTIVE:
                    if e.id in self._deactivating:
                        continue
                    active_broadcast.append(e)
                    try:
                        end = e.end_datetime()
                        if end <= now:
                            to_deactivate.append(e)
                        else:
                            # Aviso antes do fim
                            secs_left = (end - now).total_seconds()
                            for threshold, label in (
                                (300, "5 minutos"),
                                (60,  "1 minuto"),
                            ):
                                key = f"{e.id}:end:{threshold}"
                                if secs_left <= threshold and key not in self._rcon_warnings_sent:
                                    to_warn.append((e, label, key, "end"))
                    except ValueError:
                        pass

        for e, label, key, phase in to_warn:
            with self._lock:
                self._rcon_warnings_sent.add(key)
            if phase == "start":
                self._rcon_broadcast(
                    e.server_id,
                    f"[Evento Sazonal] ⚡ '{e.name}' começa em {label}!",
                )
            else:
                self._rcon_broadcast(
                    e.server_id,
                    f"[Evento Sazonal] ⏳ '{e.name}' encerra em {label}.",
                )

        for e in active_broadcast:
            self._maybe_broadcast_active_buff(e)

        for e in to_activate:
            with self._lock:
                if e.id in self._activating:
                    continue
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
