from __future__ import annotations
import subprocess
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def get_cpu_temp(app: "ARKServerManagerApp") -> "Optional[float]":
    """Tenta obter temperatura do CPU via psutil (Linux) ou ACPI WMI (Windows)."""
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
    # Fallback Windows: ACPI via WMI
    import subprocess
    try:
        out = subprocess.check_output(
            ["wmic", "/namespace:\\\\root\\wmi", "path",
             "MSAcpi_ThermalZoneTemperature",
             "get", "CurrentTemperature", "/value"],
            creationflags=0x08000000,
            stderr=subprocess.DEVNULL,
            timeout=5,
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
            return max(vals)
    except Exception:
        pass
    return None

