"""Testes de tribe_service — Área de Tribo ARKLAND MVP.

Cobre:
  - Criação e busca de tribe_owner
  - Vínculo de mapa (map_link principal / fob)
  - record_presence + auto-link de owner
  - get_my_tribes
  - Regulamento: salvar, versionar, limite de caracteres
  - Split R1 (gap ≥ 10 p.p.) e R2 (soma = 100%)
  - Split R4 recalc proporcional no opt-out
  - Split R8 (mínimo 1000 Âmbares)
  - Split R11 (máximo 10 membros)
  - Opt-out de membro e recálculo
  - Desativar split (R5)
  - apply_split_payout distribui corretamente
"""
from __future__ import annotations

import json
import math
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tribe_service as ts
from tribe_service import (
    SPLIT_GAP_MIN_PP,
    SPLIT_MAX_MEMBERS,
    SPLIT_MIN_SALE_AMBER,
    apply_split_payout,
    create_or_update_split,
    disable_split,
    ensure_tribe_schema,
    get_active_split,
    get_members_by_map,
    get_my_tribes,
    get_or_create_owner,
    get_owner,
    get_regulation,
    get_split_snapshot_for_listing,
    member_optout,
    record_presence,
    recalc_proportional,
    save_regulation,
    upsert_map_link,
    validate_split_config,
)

USER_A = "76561198000000001"
USER_B = "76561198000000002"
USER_C = "76561198000000003"
USER_D = "76561198000000004"

SERVER_ISLAND = "the_island"
SERVER_RAG = "ragnarok"


@pytest.fixture()
def engine(tmp_path):
    path = tmp_path / "tribe_test.db"
    eng = create_engine(f"sqlite:///{path}", future=True)
    # Cria tabela players (necessária para split payout)
    with eng.connect() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS players "
            "(steam_id TEXT PRIMARY KEY, points INTEGER DEFAULT 0, kits TEXT DEFAULT '{}')"
        ))
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS market_listings "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, status TEXT, seller_steam_id TEXT, "
            "effective_price INTEGER, tribe_split_id INTEGER, split_snapshot TEXT)"
        ))
        conn.commit()
    ensure_tribe_schema(eng)
    return eng


@pytest.fixture()
def db(engine):
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


# ────────────────────────────────────────────────────────────
# tribe_owner
# ────────────────────────────────────────────────────────────

def test_get_or_create_owner(db):
    owner = get_or_create_owner(db, USER_A, "Jogador A")
    assert owner["steam_id"] == USER_A
    assert owner["display_name"] == "Jogador A"
    # Idempotente
    owner2 = get_or_create_owner(db, USER_A, "Outro Nome")
    assert owner2["id"] == owner["id"]


def test_get_owner_nao_existe(db):
    assert get_owner(db, "nao_existe") is None


# ────────────────────────────────────────────────────────────
# map_links
# ────────────────────────────────────────────────────────────

def test_upsert_map_link_principal(db):
    owner = get_or_create_owner(db, USER_A)
    link = upsert_map_link(
        db,
        tribe_owner_id=owner["id"],
        server_id=SERVER_ISLAND,
        tribe_id=12345,
        tribe_name_local="ARKLAND BR",
        tribe_type="principal",
    )
    assert link["tribe_type"] == "principal"
    assert link["tribe_id"] == 12345
    assert link["is_active"] is True


def test_upsert_map_link_fob(db):
    owner = get_or_create_owner(db, USER_A)
    link = upsert_map_link(
        db,
        tribe_owner_id=owner["id"],
        server_id=SERVER_RAG,
        tribe_id=99999,
        tribe_name_local="ARKLAND Fob Rag",
        tribe_type="fob",
        fob_owner_steam_id=USER_B,
    )
    assert link["tribe_type"] == "fob"
    assert link["fob_owner_steam_id"] == USER_B


def test_upsert_map_link_tipo_invalido(db):
    owner = get_or_create_owner(db, USER_A)
    with pytest.raises(ValueError, match="tribe_type inválido"):
        upsert_map_link(
            db, tribe_owner_id=owner["id"], server_id=SERVER_ISLAND,
            tribe_id=1, tribe_name_local="Teste", tribe_type="INVALIDO",
        )


# ────────────────────────────────────────────────────────────
# record_presence + auto-link + members
# ────────────────────────────────────────────────────────────

def test_record_presence_auto_link(db):
    get_or_create_owner(db, USER_A, "Jogador A")
    record_presence(
        db,
        steam_id=USER_A,
        server_id=SERVER_ISLAND,
        map_name="The Island",
        tribe_id=10001,
        tribe_name="ARKLAND BR",
        is_owner=True,
        members=[
            {"steam_id": USER_A, "character_name": "PlayerA", "is_owner": True},
            {"steam_id": USER_B, "character_name": "PlayerB", "is_owner": False},
        ],
    )
    members = get_members_by_map(db, server_id=SERVER_ISLAND, tribe_id=10001)
    assert any(m["steam_id"] == USER_A for m in members)
    assert any(m["steam_id"] == USER_B for m in members)

    tribes = get_my_tribes(db, USER_A)
    assert tribes["is_owner"] is True
    assert tribes["panel_activated"] is True
    assert any(m["server_id"] == SERVER_ISLAND for m in tribes["maps"])


def test_register_backfill_from_presence(db):
    """Presença como líder *antes* de ativar o painel → register vincula o mapa."""
    from tribe_service import backfill_owner_links_from_presence

    # Login in-game como líder sem tribe_owners ainda
    record_presence(
        db,
        steam_id=USER_A,
        server_id=SERVER_ISLAND,
        map_name="The Island",
        tribe_id=20002,
        tribe_name="Tribo Previa",
        is_owner=True,
        members=[{"steam_id": USER_A, "character_name": "A", "is_owner": True}],
    )
    # Sem owner → sem map_link
    assert get_owner(db, USER_A) is None
    empty = get_my_tribes(db, USER_A)
    assert empty["is_owner"] is False

    owner = get_or_create_owner(db, USER_A, "Jogador A")
    linked = backfill_owner_links_from_presence(db, USER_A)
    assert linked == 1
    tribes = get_my_tribes(db, USER_A)
    assert tribes["is_owner"] is True
    assert tribes["owner"]["id"] == owner["id"]
    assert any(m["tribe_id"] == 20002 for m in tribes["maps"])


def test_record_presence_auto_link_sem_tribe_name(db):
    """tribe_name vazio não deve bloquear auto-link do mapa."""
    get_or_create_owner(db, USER_A, "Jogador A")
    record_presence(
        db,
        steam_id=USER_A,
        server_id=SERVER_ISLAND,
        map_name="The Island",
        tribe_id=40004,
        tribe_name="",
        is_owner=True,
    )
    tribes = get_my_tribes(db, USER_A)
    assert any(m["tribe_id"] == 40004 for m in tribes["maps"])


def test_record_presence_rank_proprietario_sem_flag(db):
    """Rank Proprietário implica ownership mesmo com is_owner=false no payload."""
    get_or_create_owner(db, USER_A, "Cyane")
    record_presence(
        db,
        steam_id=USER_A,
        server_id=SERVER_ISLAND,
        map_name="The Island",
        tribe_id=50005,
        tribe_name="[STAFF]",
        is_owner=False,
        member_rank="Proprietário",
    )
    tribes = get_my_tribes(db, USER_A)
    assert any(m["server_id"] == SERVER_ISLAND and m["tribe_id"] == 50005 for m in tribes["maps"])


def test_backfill_from_rank_when_is_owner_flag_zero(db):
    """Presença antiga com is_owner=0 mas rank Owner ainda backfill."""
    from tribe_service import backfill_owner_links_from_presence, sync_owner_maps

    record_presence(
        db,
        steam_id=USER_A,
        server_id=SERVER_RAG,
        map_name="Ragnarok",
        tribe_id=60006,
        tribe_name="[STAFF]",
        is_owner=False,
        member_rank="Owner",
    )
    get_or_create_owner(db, USER_A, "Cyane")
    linked = backfill_owner_links_from_presence(db, USER_A)
    assert linked == 1
    sync = sync_owner_maps(db, USER_A)
    assert sync["panel_activated"] is True
    assert any(m["tribe_id"] == 60006 for m in sync["maps"])
    assert sync["hint"] is None


def test_sync_owner_maps_hint_sem_presenca(db):
    from tribe_service import sync_owner_maps

    get_or_create_owner(db, USER_A, "Cyane")
    sync = sync_owner_maps(db, USER_A)
    assert sync["maps"] == []
    assert sync["hint"]
    assert "presença" in sync["hint"].lower() or "Relogue" in sync["hint"]


def test_presence_unknown_server_id_nao_vincula(db):
    """server_id=unknown não deve criar tribe_map_links (falta CrossChat.ServerId)."""
    from tribe_service import sync_owner_maps

    get_or_create_owner(db, USER_A, "Cyana")
    record_presence(
        db,
        steam_id=USER_A,
        server_id="unknown",
        map_name="unknown",
        tribe_id=70007,
        tribe_name="[STAFF]",
        is_owner=True,
        member_rank="Proprietário",
    )
    sync = sync_owner_maps(db, USER_A)
    assert sync["maps"] == []
    assert sync["hint"]
    assert "ServerId" in sync["hint"] or "unknown" in sync["hint"].lower()


def test_rank_implies_owner_helpers():
    from tribe_service import rank_implies_owner, resolve_is_owner

    assert rank_implies_owner("Proprietário") is True
    assert rank_implies_owner("Owner") is True
    assert rank_implies_owner("Admin") is False
    assert rank_implies_owner("Leader") is False
    assert resolve_is_owner(is_owner="true") is True
    assert resolve_is_owner(is_owner=0, member_rank="proprietario") is True


def test_manual_add_member(db):
    from tribe_service import manual_add_member

    owner = get_or_create_owner(db, USER_A, "Owner")
    upsert_map_link(
        db,
        tribe_owner_id=owner["id"],
        server_id=SERVER_ISLAND,
        tribe_id=30003,
        tribe_name_local="ARKLAND",
        tribe_type="principal",
    )
    result = manual_add_member(
        db,
        owner_steam_id=USER_A,
        server_id=SERVER_ISLAND,
        tribe_id=30003,
        member_steam_id=USER_B,
        character_name="Amigo",
    )
    assert result["steam_id"] == USER_B
    members = get_members_by_map(db, server_id=SERVER_ISLAND, tribe_id=30003)
    assert any(m["steam_id"] == USER_B and m["character_name"] == "Amigo" for m in members)

    # Membro não-dono vê o mapa
    as_member = get_my_tribes(db, USER_B)
    assert as_member["is_owner"] is False
    assert any(m["tribe_id"] == 30003 for m in as_member["maps"])


def test_manual_add_member_steamid_invalido(db):
    from tribe_service import manual_add_member

    owner = get_or_create_owner(db, USER_A)
    upsert_map_link(
        db, tribe_owner_id=owner["id"], server_id=SERVER_ISLAND,
        tribe_id=1, tribe_name_local="X", tribe_type="principal",
    )
    with pytest.raises(ValueError, match="SteamID64"):
        manual_add_member(
            db, owner_steam_id=USER_A, server_id=SERVER_ISLAND,
            tribe_id=1, member_steam_id="123",
        )


# ────────────────────────────────────────────────────────────
# Regulamento
# ────────────────────────────────────────────────────────────

def test_save_regulation_cria_e_versiona(db):
    owner = get_or_create_owner(db, USER_A)
    reg = save_regulation(
        db,
        tribe_owner_id=owner["id"],
        content_text="Regra 1: Respeito mútuo.",
        actor_steam_id=USER_A,
        visibility="private",
    )
    assert reg["version"] == 1
    assert reg["content_text"] == "Regra 1: Respeito mútuo."

    reg2 = save_regulation(
        db,
        tribe_owner_id=owner["id"],
        content_text="Regra 1: Respeito mútuo. Regra 2: Sem traição.",
        actor_steam_id=USER_A,
    )
    assert reg2["version"] == 2


def test_regulamento_limite_chars(db):
    owner = get_or_create_owner(db, USER_A)
    texto_longo = "A" * (ts.REGULAMENTO_MAX_CHARS + 1)
    with pytest.raises(ValueError, match="caracteres"):
        save_regulation(db, tribe_owner_id=owner["id"], content_text=texto_longo, actor_steam_id=USER_A)


# ────────────────────────────────────────────────────────────
# Split — validação R1 + R2
# ────────────────────────────────────────────────────────────

def _make_members(*pct_list: int, seller_index: int = 0) -> list[dict]:
    members = []
    steam_ids = [USER_A, USER_B, USER_C, USER_D]
    for i, pct in enumerate(pct_list):
        members.append({
            "steam_id": steam_ids[i % len(steam_ids)] + str(i),
            "percentage": pct,
            "is_seller": i == seller_index,
            "opted_out": False,
        })
    return members


class TestValidateSplitConfig:
    def test_valido_gap_exato_10pp(self):
        members = _make_members(40, 30, 30)
        validate_split_config(members)  # deve passar — gap=10 (limite)

    def test_valido_60_40(self):
        members = _make_members(60, 40)
        validate_split_config(members)

    def test_invalido_gap_menor_10pp(self):
        members = _make_members(38, 32, 30)
        with pytest.raises(ValueError, match="Gap mínimo"):
            validate_split_config(members)

    def test_invalido_empate_vendedor(self):
        members = _make_members(35, 35, 30)
        with pytest.raises(ValueError, match="maior"):
            validate_split_config(members)

    def test_invalido_soma_diferente_100(self):
        members = _make_members(50, 30, 15)  # soma=95
        with pytest.raises(ValueError, match="100%"):
            validate_split_config(members)

    def test_invalido_apenas_1_membro(self):
        members = _make_members(100)
        with pytest.raises(ValueError, match="ao menos 2"):
            validate_split_config(members)

    def test_invalido_mais_de_10_membros(self):
        pcts = [20] + [8] * 10  # 11 membros, soma=100
        members = _make_members(*pcts)
        with pytest.raises(ValueError, match="máximo"):
            validate_split_config(members)

    def test_invalido_sem_vendedor(self):
        members = [
            {"steam_id": USER_A, "percentage": 60, "is_seller": False, "opted_out": False},
            {"steam_id": USER_B, "percentage": 40, "is_seller": False, "opted_out": False},
        ]
        with pytest.raises(ValueError, match="vendedor"):
            validate_split_config(members)

    def test_valido_55_25_20(self):
        members = _make_members(55, 25, 20)
        validate_split_config(members)

    def test_invalido_vendedor_menor_que_membro(self):
        # Vendedor tem 30%, membro tem 40% → inválido
        members = [
            {"steam_id": USER_A, "percentage": 30, "is_seller": True, "opted_out": False},
            {"steam_id": USER_B, "percentage": 40, "is_seller": False, "opted_out": False},
            {"steam_id": USER_C, "percentage": 30, "is_seller": False, "opted_out": False},
        ]
        with pytest.raises(ValueError, match="maior"):
            validate_split_config(members)


# ────────────────────────────────────────────────────────────
# Split — recálculo proporcional no opt-out (R4)
# ────────────────────────────────────────────────────────────

class TestRecalcProportional:
    def test_optout_membro_simples(self):
        """3 membros: vendedor 50%, A 30%, B 20%. B faz opt-out."""
        members = [
            {"steam_id": USER_A, "percentage": 50, "is_seller": True, "opted_out": False},
            {"steam_id": USER_B, "percentage": 30, "is_seller": False, "opted_out": False},
            {"steam_id": USER_C, "percentage": 20, "is_seller": False, "opted_out": False},
        ]
        new_members = recalc_proportional(members, USER_C)
        assert len(new_members) == 2
        total = sum(m["percentage"] for m in new_members)
        assert total == 100

    def test_optout_membro_2_membros(self):
        """2 membros: vendedor 60%, A 40%. A faz opt-out → vendedor fica com 100%."""
        members = [
            {"steam_id": USER_A, "percentage": 60, "is_seller": True, "opted_out": False},
            {"steam_id": USER_B, "percentage": 40, "is_seller": False, "opted_out": False},
        ]
        new_members = recalc_proportional(members, USER_B)
        assert len(new_members) == 1
        assert new_members[0]["steam_id"] == USER_A
        assert new_members[0]["percentage"] == 100

    def test_optout_vendedor_bloqueado(self):
        members = [
            {"steam_id": USER_A, "percentage": 60, "is_seller": True, "opted_out": False},
            {"steam_id": USER_B, "percentage": 40, "is_seller": False, "opted_out": False},
        ]
        with pytest.raises(ValueError, match="vendedor"):
            recalc_proportional(members, USER_A)

    def test_remainder_vai_ao_vendedor(self):
        """Com 3 membros e valores com arredondamento, o remainder deve ir ao vendedor."""
        members = [
            {"steam_id": USER_A, "percentage": 50, "is_seller": True, "opted_out": False},
            {"steam_id": USER_B, "percentage": 30, "is_seller": False, "opted_out": False},
            {"steam_id": USER_C, "percentage": 20, "is_seller": False, "opted_out": False},
        ]
        new_members = recalc_proportional(members, USER_C)
        total = sum(m["percentage"] for m in new_members)
        assert total == 100


# ────────────────────────────────────────────────────────────
# Split — criação e opt-out no DB
# ────────────────────────────────────────────────────────────

def test_create_split_e_optout(db):
    owner = get_or_create_owner(db, USER_A)
    # Vincula como principal
    upsert_map_link(db, tribe_owner_id=owner["id"], server_id=SERVER_ISLAND,
                    tribe_id=10001, tribe_name_local="ARKLAND BR", tribe_type="principal")

    members = [
        {"steam_id": USER_A, "percentage": 55, "is_seller": True, "display_name": "PlayerA"},
        {"steam_id": USER_B, "percentage": 25, "is_seller": False, "display_name": "PlayerB"},
        {"steam_id": USER_C, "percentage": 20, "is_seller": False, "display_name": "PlayerC"},
    ]
    split = create_or_update_split(
        db,
        tribe_owner_id=owner["id"],
        tribe_id=10001,
        server_id=SERVER_ISLAND,
        tribe_name="ARKLAND BR",
        members=members,
        actor_steam_id=USER_A,
    )
    assert split["status"] == "PENDING_COOLDOWN"
    assert len(split["members"]) == 3

    # Opt-out de USER_C
    new_members = member_optout(
        db,
        split_id=split["id"],
        steam_id=USER_C,
        actor_steam_id=USER_C,
    )
    # USER_C deve estar marcado como opted_out=True
    user_c_entry = next((m for m in new_members if m["steam_id"] == USER_C), None)
    assert user_c_entry is not None
    assert user_c_entry["opted_out"] is True
    # Soma dos percentuais dos membros ativos deve ser 100
    total = sum(m["percentage"] for m in new_members if not m.get("opted_out"))
    assert total == 100


def test_create_split_fob_bloqueado(db):
    owner = get_or_create_owner(db, USER_A)
    upsert_map_link(db, tribe_owner_id=owner["id"], server_id=SERVER_RAG,
                    tribe_id=99999, tribe_name_local="Fob Rag", tribe_type="fob")
    members = [
        {"steam_id": USER_A, "percentage": 60, "is_seller": True},
        {"steam_id": USER_B, "percentage": 40, "is_seller": False},
    ]
    with pytest.raises(ValueError, match="Fobs"):
        create_or_update_split(
            db, tribe_owner_id=owner["id"], tribe_id=99999, server_id=SERVER_RAG,
            tribe_name="Fob Rag", members=members, actor_steam_id=USER_A,
        )


def test_disable_split(db):
    owner = get_or_create_owner(db, USER_A)
    upsert_map_link(db, tribe_owner_id=owner["id"], server_id=SERVER_ISLAND,
                    tribe_id=10001, tribe_name_local="ARKLAND BR", tribe_type="principal")
    members = [
        {"steam_id": USER_A, "percentage": 60, "is_seller": True},
        {"steam_id": USER_B, "percentage": 40, "is_seller": False},
    ]
    create_or_update_split(
        db, tribe_owner_id=owner["id"], tribe_id=10001, server_id=SERVER_ISLAND,
        tribe_name="ARKLAND BR", members=members, actor_steam_id=USER_A,
    )
    disable_split(db, tribe_owner_id=owner["id"], actor_steam_id=USER_A)
    split = get_active_split(db, owner["id"])
    assert split is None


# ────────────────────────────────────────────────────────────
# Split — R8 mínimo de venda e get_split_snapshot
# ────────────────────────────────────────────────────────────

def test_split_snapshot_abaixo_minimo(db):
    owner = get_or_create_owner(db, USER_A)
    # Mesmo com split ACTIVE, abaixo de R8 (1000 Âmbares) retorna None
    snapshot = get_split_snapshot_for_listing(db, owner["id"], price=999)
    assert snapshot is None


def test_split_snapshot_sem_split_ativo(db):
    owner = get_or_create_owner(db, USER_A)
    snapshot = get_split_snapshot_for_listing(db, owner["id"], price=5000)
    assert snapshot is None


# ────────────────────────────────────────────────────────────
# apply_split_payout
# ────────────────────────────────────────────────────────────

class TestApplySplitPayout:
    def test_distribuicao_50_30_20(self):
        """Venda de 10.000: vendedor 50% = 5000, B 30% = 3000, C 20% = 2000."""
        creditos: dict[str, int] = {}

        def mock_credit(db, steam_id, amount):
            creditos[steam_id] = creditos.get(steam_id, 0) + amount
            return amount

        snapshot = json.dumps({
            "split_id": 1,
            "members": [
                {"steam_id": USER_A, "percentage": 50, "is_seller": True, "opted_out": False},
                {"steam_id": USER_B, "percentage": 30, "is_seller": False, "opted_out": False},
                {"steam_id": USER_C, "percentage": 20, "is_seller": False, "opted_out": False},
            ],
        })
        payouts = apply_split_payout(
            None, split_snapshot_json=snapshot, price=10_000,
            seller_steam_id=USER_A, listing_id=1, credit_fn=mock_credit,
        )
        assert creditos[USER_B] == 3000
        assert creditos[USER_C] == 2000
        seller_payout = next(p for p in payouts if p["leg"] == "seller")
        assert seller_payout["amount"] == 5000

    def test_remainder_vai_ao_vendedor(self):
        """Com arredondamento: total deve ser exatamente igual ao preço."""
        creditos: dict[str, int] = {}

        def mock_credit(db, steam_id, amount):
            creditos[steam_id] = creditos.get(steam_id, 0) + amount
            return amount

        snapshot = json.dumps({
            "split_id": 1,
            "members": [
                {"steam_id": USER_A, "percentage": 50, "is_seller": True, "opted_out": False},
                {"steam_id": USER_B, "percentage": 33, "is_seller": False, "opted_out": False},
                {"steam_id": USER_C, "percentage": 17, "is_seller": False, "opted_out": False},
            ],
        })
        apply_split_payout(
            None, split_snapshot_json=snapshot, price=1001,
            seller_steam_id=USER_A, listing_id=1, credit_fn=mock_credit,
        )
        total = sum(creditos.values())
        assert total == 1001  # nenhum Âmbar perdido

    def test_sem_membros_fallback_vendedor(self):
        """Snapshot vazio → 100% ao vendedor."""
        creditos: dict[str, int] = {}

        def mock_credit(db, steam_id, amount):
            creditos[steam_id] = creditos.get(steam_id, 0) + amount
            return amount

        snapshot = json.dumps({"split_id": 1, "members": []})
        apply_split_payout(
            None, split_snapshot_json=snapshot, price=5000,
            seller_steam_id=USER_A, listing_id=1, credit_fn=mock_credit,
        )
        assert creditos.get(USER_A, 0) == 5000


# ────────────────────────────────────────────────────────────
# Constantes
# ────────────────────────────────────────────────────────────

def test_constantes_especificadas():
    """Verifica que as constantes do spec estão corretas."""
    assert SPLIT_MIN_SALE_AMBER == 1_000   # R8 — D7
    assert SPLIT_MAX_MEMBERS == 10          # R11 — D5
    assert SPLIT_GAP_MIN_PP == 10           # R1 — D1
