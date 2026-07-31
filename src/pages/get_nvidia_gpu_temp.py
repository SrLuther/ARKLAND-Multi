from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .hw_temp_sensors import read_gpu_temp

if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def get_nvidia_gpu_temp(_app: "ARKServerManagerApp") -> "Optional[float]":
    """Temperatura GPU: nvidia-smi, senão Libre/OpenHardwareMonitor.

    GPUs antigas (ex. GeForce G210) sem nvidia-smi e sem monitor de hardware
    devolvem None — a UI mostra N/D (não inventa valores).
    """
    try:
        return read_gpu_temp()
    except Exception:
        return None
