"""Inicia um servidor ASM com validação de config e conflito de portas."""
from __future__ import annotations
from typing import TYPE_CHECKING
from ..asm_engine.asm_config import AsmServerConfig
if TYPE_CHECKING:
    from ..app_tek import ARKTEKApp


def asm_start_server(app: "ARKTEKApp", srv: AsmServerConfig, no_mods: bool = False) -> None:
    """Delega ao fluxo central do app (persist + validação + start)."""
    app._asm_start_server(srv, no_mods=no_mods)

