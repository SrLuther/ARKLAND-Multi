from __future__ import annotations

from typing import TYPE_CHECKING, Optional

try:
    import psutil as _psutil  # type: ignore[reportMissingModuleSource]
    _PSUTIL_OK = True
except Exception:
    _psutil = None  # type: ignore[assignment]
    _PSUTIL_OK = False

from .hw_temp_sensors import read_cpu_temp_windows

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def get_cpu_temp(_app: "ARKServerManagerApp") -> "Optional[float]":
    """Temperatura do CPU: psutil (Linux) ou backends Windows multi-fonte.

    Windows: LibreHardwareMonitor / OpenHardwareMonitor (se a correr) →
    contador de zona térmica → MSAcpi CIM → wmic legado.
    Sem sensor exposto (comum em Xeon/servidor), devolve None → UI «N/D».
    """
    if _PSUTIL_OK and _psutil is not None:
        try:
            temps = _psutil.sensors_temperatures()
            if temps:
                for key in ("coretemp", "k10temp", "cpu_thermal", "acpitz"):
                    if key in temps and temps[key]:
                        return max(e.current for e in temps[key])
                for entries in temps.values():
                    if entries:
                        return max(e.current for e in entries)
        except Exception:
            pass

    try:
        return read_cpu_temp_windows()
    except Exception:
        return None
