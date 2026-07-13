"""Pacote Regulamento — mensagens curtas para o ciclo de broadcasts TEK.

Catálogo curado (não sync automático do markdown) com IDs estáveis ligados
às seções do Regulamento oficial. Admin carrega/atualiza pelo painel Broadcasts.
"""
from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..app_tek import ARKServerManagerApp

from .broadcast_profile_io import get_library, merge_library, normalize_entry, set_library

REGULAMENTO_SOURCE = "regulamento"
REGULAMENTO_CATEGORY = "Regulamento"
PACK_VERSION = "1.1"

# IDs estáveis — re-seed atualiza por id sem duplicar.
_REGULAMENTO_PACK: list[dict[str, Any]] = [
    {
        "id": "arkland-reg-3.5-doacao-licenca",
        "label": "Reg §3.5 — Doação / licença",
        "section": "3.5",
        "message": (
            "[ARKLAND] Proibido doar recursos, dinos ou itens que exigem licença "
            "ativa a quem não a possui. Violação: punição administrativa."
        ),
    },
    {
        "id": "arkland-reg-5.4-rmt",
        "label": "Reg §5.4 — RMT",
        "section": "5.4",
        "message": (
            "[ARKLAND] Proibido negociar itens, dinos ou contas por dinheiro real. "
            "Use apenas a loja e o mercado P2P em Âmbares."
        ),
    },
    {
        "id": "arkland-reg-6.1-cheats",
        "label": "Reg §6.1 — Cheats",
        "section": "6.1",
        "message": (
            "[ARKLAND] Cheats, hacks e duplicação: ban permanente. "
            "Reporte exploits por ticket — não divulgue o método."
        ),
    },
    {
        "id": "arkland-reg-6.3-duplicacao",
        "label": "Reg §6.3 — Duplicação",
        "section": "6.3",
        "message": (
            "[ARKLAND] Itens ou Âmbares obtidos por duplicação serão removidos. "
            "Transações no mercado envolvendo itens duplicados podem ser revertidas."
        ),
    },
    {
        "id": "arkland-reg-5.2-conduta",
        "label": "Reg §5.2 — Conduta",
        "section": "5.2",
        "message": (
            "[ARKLAND] Ódio, assédio, doxxing e spam no chat são proibidos. "
            "Sanção conforme o Regulamento — respeite a comunidade."
        ),
    },
    {
        "id": "arkland-reg-4.3-estruturas",
        "label": "Reg §4.3 — Estruturas",
        "section": "4.3",
        "message": (
            "[ARKLAND] Bloquear spawns, land claim tóxico e griefing estrutural "
            "são proibidos e sujeitos a punição administrativa."
        ),
    },
    {
        "id": "arkland-reg-8.7-mercado",
        "label": "Reg §8.7 — Mercado",
        "section": "8.7",
        "message": (
            "[ARKLAND] Mercado: anúncio falso, conluio, wash trading ou RMT = sanção. "
            "Disputas apenas por ticket (Mercado de dinos)."
        ),
    },
    {
        "id": "arkland-reg-8.5-licencas",
        "label": "Reg §8.5 — Licenças",
        "section": "8.5",
        "message": (
            "[ARKLAND] Licenças são pessoais e intransferíveis. "
            "Kits e benefícios do catálogo exigem a licença ativa correspondente."
        ),
    },
    {
        "id": "arkland-reg-4.2-tribos",
        "label": "Reg §4.2 — Tribos",
        "section": "4.2",
        "message": (
            "[ARKLAND] Proibido criar tribos laranjas para burlar limites ou ocultar "
            "identidade. Nomes ofensivos ou que imitem a staff são proibidos."
        ),
    },
    {
        "id": "arkland-reg-10-denuncias",
        "label": "Reg §10 — Denúncias",
        "section": "10",
        "message": (
            "[ARKLAND] Denúncias e pedidos de punição: somente por ticket na Web Store, "
            "com prova. Chat e Discord não substituem o canal oficial."
        ),
    },
]


def regulamento_pack_catalog() -> list[dict[str, Any]]:
    """Cópia do catálogo oficial (imutável para o caller)."""
    return deepcopy(_REGULAMENTO_PACK)


def build_regulamento_pack_entries() -> list[dict[str, Any]]:
    """Normaliza o catálogo para o formato da biblioteca de broadcasts."""
    entries: list[dict[str, Any]] = []
    for raw in _REGULAMENTO_PACK:
        entries.append(
            normalize_entry({
                **raw,
                "source": REGULAMENTO_SOURCE,
                "category": REGULAMENTO_CATEGORY,
            })
        )
    return entries


def seed_regulamento_pack(
    app: "ARKServerManagerApp",
    *,
    update_existing: bool = True,
) -> tuple[int, int]:
    """Mescla o pacote Regulamento na biblioteca.

    Retorna ``(adicionados, atualizados)``.
    Se ``update_existing`` for False, só adiciona IDs ainda ausentes.
    """
    imported = build_regulamento_pack_entries()
    current = get_library(app)
    before_ids = {str(e.get("id")) for e in current if e.get("id")}

    if update_existing:
        merged = merge_library(current, imported)
    else:
        to_add = [e for e in imported if str(e.get("id")) not in before_ids]
        merged = list(current) + to_add

    set_library(app, merged)
    after_ids = {str(e.get("id")) for e in merged}
    added = len(after_ids - before_ids)
    if update_existing:
        updated = sum(1 for e in imported if str(e.get("id")) in before_ids)
    else:
        updated = 0
    return added, updated
