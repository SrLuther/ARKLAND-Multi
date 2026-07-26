"""
Helper standalone para emitir diagnóstico de crash e registrar no CrashStore.
Extraído de server_manager.py para manter o módulo abaixo de 1000 linhas.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

if TYPE_CHECKING:
    pass


def _register_crash_event(server_id: str, server_name: str, install_dir: str,
                          kind: str, info: str, exit_code_val: Optional[int]) -> None:
    """Registra o crash no CrashStore para notificação em tempo real."""
    import uuid as _uuid
    from .crash_ai import needs_ai_upgrade, schedule_crash_ai_analysis
    from .crash_parser import _list_crash_records
    from .crash_store import CrashEvent, CrashStore
    records = _list_crash_records(install_dir)
    evt: CrashEvent | None = None
    if records:
        rec = records[0]
        evt = CrashEvent(
            event_id=str(_uuid.uuid4()), server_id=server_id, server_name=server_name,
            kind=kind, timestamp=rec["timestamp"].isoformat(), exit_code=exit_code_val,
            log_tail=rec.get("call_stack") or rec.get("log_lines", []),
            culprit=rec.get("culprit", ""), diagnosis=rec.get("diagnosis", ""),
        )
        CrashStore.instance().add(evt)
    elif info:
        evt = CrashEvent(
            event_id=str(_uuid.uuid4()), server_id=server_id, server_name=server_name,
            kind=kind, timestamp=datetime.now().isoformat(), exit_code=exit_code_val,
            log_tail=info.splitlines()[:40], culprit="", diagnosis=info[:300],
        )
        CrashStore.instance().add(evt)

    if evt is not None and needs_ai_upgrade(evt.diagnosis):
        schedule_crash_ai_analysis(
            evt.event_id,
            server_name=server_name,
            install_dir=install_dir,
            kind=kind,
            culprit=evt.culprit,
            log_tail=list(evt.log_tail or []),
            heuristic_diagnosis=evt.diagnosis,
        )


def emit_crash_details(
    instances: Dict[str, Any],
    emit_log: Callable[[str, str, str], None],
    server_id: str,
    install_dir: str,
    kind: str = "crash",
) -> None:
    """Lê arquivos de crash do ARK, emite diagnóstico nos logs e registra no CrashStore."""
    from .crash_parser import _read_crash_info
    try:
        time.sleep(1.5)
        info = _read_crash_info(install_dir)
        if info:
            inst = instances.get(server_id)
            if inst:
                inst.last_crash_info = info
            emit_log(server_id, "─── Diagnóstico de Crash ───────────────────────────────", "error")
            for line in info.splitlines():
                emit_log(server_id, line, "error" if line.startswith("**") else "warning")
            emit_log(server_id, "────────────────────────────────────────────────────────", "error")
        try:
            inst2 = instances.get(server_id)
            server_name: str = server_id
            if inst2 and hasattr(inst2, "config"):
                server_name = getattr(inst2.config, "name", server_id) or server_id
            exit_code_val: Optional[int] = None
            if inst2 and inst2.process:
                try:
                    exit_code_val = inst2.process.returncode
                except Exception:
                    pass
            _register_crash_event(server_id, server_name, install_dir, kind, info, exit_code_val)
        except Exception:
            pass
    except Exception as exc:
        emit_log(server_id, f"Não foi possível ler arquivos de crash: {exc}", "debug")
