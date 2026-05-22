from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..app import ARKServerManagerApp


def validate_server_ports(app: "ARKServerManagerApp", server_id: str, server_port: int, query_port: int, rcon_port: int) -> list:
    """Valida unicidade de portas entre todos os servidores. Retorna lista de erros (vazia = OK)."""
    peer_port = server_port + 1
    errors: list = []

    # ── Conflitos internos (mesmo servidor) ──────────────────────────────
    own_ports = [
        ("Porta do Servidor", server_port),
        ("Porta Par",         peer_port),
        ("Porta Query",       query_port),
        ("Porta RCON",        rcon_port),
    ]
    seen: dict = {}
    for lbl, p in own_ports:
        if p in seen:
            errors.append(f"'{lbl}' e '{seen[p]}' têm o mesmo valor ({p}).")
        else:
            seen[p] = lbl

    # ── Conflitos com outros servidores ───────────────────────────────────
    for other in app.config_manager.servers:
        if other.id == server_id:
            continue
        other_map = {
            other.server_port:     "Porta do Servidor",
            other.server_port + 1: "Porta Par",
            other.query_port:      "Porta Query",
            other.rcon_port:       "Porta RCON",
        }
        for lbl, p in own_ports:
            if p in other_map:
                errors.append(
                    f"'{lbl}' ({p}) já usada pelo servidor '{other.name}'"
                    f" como {other_map[p]}."
                )

    return errors

