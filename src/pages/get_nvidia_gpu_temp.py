from __future__ import annotations
import subprocess
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def get_nvidia_gpu_temp(app: "ARKServerManagerApp") -> "Optional[float]":
    """Tenta obter temperatura da GPU via nvidia-smi."""
    import subprocess
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=temperature.gpu",
             "--format=csv,noheader,nounits"],
            creationflags=0x08000000,
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).decode().strip()
        lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
        if lines:
            return float(lines[0])
    except Exception:
        pass
    return None

