from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .hw_temp_sensors import read_gpu_util

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def get_nvidia_gpu_pct(_app: "ARKServerManagerApp") -> "Optional[float]":
    """Uso de GPU: nvidia-smi, senão Load do Libre/OpenHardwareMonitor."""
    try:
        return read_gpu_util()
    except Exception:
        return None
