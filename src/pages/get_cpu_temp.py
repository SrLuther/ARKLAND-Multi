from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Optional

try:
    import psutil as _psutil  # type: ignore[reportMissingModuleSource]
    _PSUTIL_OK = True
except Exception:
    _psutil = None  # type: ignore[assignment]
    _PSUTIL_OK = False

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp

# wmic/ACPI costuma falhar ou demorar em hosts sem sensor térmico exposto —
# após 1 falha, não bloquear o loop de Desempenho de novo.
_WMI_TEMP_OK: Optional[bool] = None


def get_cpu_temp(_app: "ARKServerManagerApp") -> "Optional[float]":
    """Tenta obter temperatura do CPU via psutil (Linux) ou ACPI WMI (Windows)."""
    global _WMI_TEMP_OK

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

    if _WMI_TEMP_OK is False:
        return None

    try:
        out = subprocess.check_output(
            ["wmic", "/namespace:\\\\root\\wmi", "path",
             "MSAcpi_ThermalZoneTemperature",
             "get", "CurrentTemperature", "/value"],
            creationflags=0x08000000,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).decode(errors="replace")
        vals = []
        for ln in out.splitlines():
            ln = ln.strip()
            if ln.lower().startswith("currenttemperature="):
                try:
                    raw = int(ln.partition("=")[2].strip())
                    celsius = raw / 10 - 273.15
                    if 10 < celsius < 110:
                        vals.append(celsius)
                except ValueError:
                    pass
        if vals:
            _WMI_TEMP_OK = True
            return max(vals)
        _WMI_TEMP_OK = False
    except Exception:
        _WMI_TEMP_OK = False
    return None
