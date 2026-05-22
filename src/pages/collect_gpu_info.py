from __future__ import annotations
from typing import TYPE_CHECKING
import subprocess
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def collect_gpu_info(app: "ARKServerManagerApp") -> None:
    import subprocess
    try:
        _NO_WINDOW = 0x08000000
        out = subprocess.check_output(
            ["wmic", "path", "Win32_VideoController",
             "get", "Name,AdapterRAM", "/value"],
            creationflags=_NO_WINDOW,
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).decode(errors="replace")

        gpus: list = []
        current: dict = {}
        for raw in out.splitlines():
            line = raw.strip()
            if not line:
                if current:
                    gpus.append(current)
                    current = {}
                continue
            if "=" in line:
                key, _, val = line.partition("=")
                current[key.strip()] = val.strip()
        if current:
            gpus.append(current)

        parts = []
        for g in gpus:
            name = g.get("Name", "").strip()
            if not name:
                continue
            vram_raw = g.get("AdapterRAM", "0")
            try:
                vram_mb = int(vram_raw) // (1024 * 1024)
                vram_str = f"{vram_mb:,} MB VRAM" if vram_mb > 0 else ""
            except ValueError:
                vram_str = ""
            parts.append(f"{name}\n{vram_str}" if vram_str else name)

        info = "\n\n".join(parts) if parts else "Não detectada"
    except Exception:
        info = "Informação indisponível"

    def _set():
        if app._perf_gpu_info_var:
            app._perf_gpu_info_var.set(info)
    try:
        app.after(0, _set)
    except Exception:
        pass

