"""
AsmFolderManager — organiza servidores TEK em grupos/pastas.
Os grupos são derivados do campo `folder` de cada AsmServerConfig.
Não há arquivo separado — tudo vive nos próprios servidores.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    from .asm_config_manager import AsmConfigManager
    from .asm_server_config import AsmServerConfig

_ROOT = ""   # servidores sem pasta ficam na raiz (folder == "")


class AsmFolderManager:
    """Gerencia a organização lógica de servidores em grupos.

    Não persiste dados próprios — usa o campo ``srv.folder`` de
    cada :class:`AsmServerConfig` como fonte de verdade.
    """

    def __init__(self, config_manager: "AsmConfigManager") -> None:
        self._cm = config_manager

    # ── Consulta ─────────────────────────────────────────────────────────────

    def get_folders(self) -> List[str]:
        """Retorna lista ordenada de nomes de pastas (excluindo raiz)."""
        seen: set[str] = set()
        result: List[str] = []
        for s in self._cm.servers:
            f = (s.folder or "").strip()
            if f and f not in seen:
                seen.add(f)
                result.append(f)
        return sorted(result)

    def get_servers_in_folder(self, folder: str) -> List["AsmServerConfig"]:
        """Servidores pertencentes a uma pasta ('' = raiz)."""
        norm = (folder or "").strip()
        return [s for s in self._cm.servers if (s.folder or "").strip() == norm]

    def grouped(self) -> Dict[str, List["AsmServerConfig"]]:
        """Retorna {pasta: [servidores]}, incluindo '' para a raiz.
        Pastas aparecem em ordem alfabética; raiz (se houver) vem por último.
        """
        result: Dict[str, List["AsmServerConfig"]] = {}
        for srv in self._cm.servers:
            key = (srv.folder or "").strip()
            result.setdefault(key, []).append(srv)
        # reordenar: pastas com nome primeiro, raiz por último
        ordered: Dict[str, List["AsmServerConfig"]] = {}
        for k in sorted(k for k in result if k):
            ordered[k] = result[k]
        if "" in result:
            ordered[""] = result[""]
        return ordered

    # ── Mutação ───────────────────────────────────────────────────────────────

    def rename_folder(self, old: str, new: str) -> None:
        """Renomeia todos os servidores de `old` para `new`."""
        new = (new or "").strip()
        for srv in self._cm.servers:
            if (srv.folder or "").strip() == old.strip():
                srv.folder = new
        self._cm.save()

    def delete_folder(self, name: str) -> None:
        """Move todos os servidores da pasta para a raiz (folder = '')."""
        for srv in self._cm.servers:
            if (srv.folder or "").strip() == name.strip():
                srv.folder = ""
        self._cm.save()

    def move_server(self, server_id: str, folder: str) -> None:
        """Move um servidor para a pasta indicada ('' = raiz)."""
        srv = self._cm.get_server(server_id)
        if srv:
            srv.folder = (folder or "").strip()
            self._cm.save()
