"""Informações de ambiente do app (boot + ``app_info.json`` do pacote de diagnóstico)."""
from __future__ import annotations

import os
import platform
import sys
from datetime import datetime
from typing import Any, Dict

from . import paths
from .events import CAT_BOOT, diag_event


def collect_app_info(mode: str = "?") -> Dict[str, Any]:
    """Dados do app/SO/Python — sem segredos."""
    try:
        from ..version import APP_VERSION, BUILD_DATE
    except Exception:  # noqa: BLE001
        APP_VERSION, BUILD_DATE = "?", "?"
    return {
        "app_version": APP_VERSION,
        "build_date": BUILD_DATE,
        "ui_mode": mode,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "python": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "executable": sys.executable,
        "cwd": os.getcwd(),
        "app_data_dir": str(paths.app_data_dir()),
        "pid": os.getpid(),
    }


def log_boot_event(mode: str) -> None:
    """Registra a linha de boot (versão, modo, caminhos) no ``arkland.log``."""
    info = collect_app_info(mode)
    diag_event(
        CAT_BOOT, "App iniciado",
        version=info["app_version"], mode=mode, frozen=info["frozen"],
        python=platform.python_version(), os=info["platform"],
        exe=info["executable"], app_data=info["app_data_dir"],
        log_file=str(paths.log_file_path()), pid=info["pid"],
    )
