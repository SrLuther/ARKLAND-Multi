"""Contrato do ArkPlayer: /mindwipe, /loot e /kill não podem cancelar à toa."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (ROOT / "plugin/ArkPlayer/src/PlayerCommands.cpp").read_text(encoding="utf-8")
POINTS = (ROOT / "plugin/ArkPlayer/src/PlayerPoints.cpp").read_text(encoding="utf-8")
SHOP = (ROOT / "plugin/CustomShop/src/ShopPoints.cpp").read_text(encoding="utf-8")


def _between(src: str, start: str, end: str) -> str:
    return src.split(start, 1)[1].split(end, 1)[0]


def test_handcuff_does_not_match_empty_buff_tag():
    kill = _between(COMMANDS, "void CmdKill", "void CmdAdminReload")
    code = "\n".join(
        line for line in kill.splitlines() if not line.strip().startswith("//")
    )
    assert 'FName("Handcuffed"' not in code
    assert "HasBuffWithCustomTag" not in code
    assert 'HasRealBuff(ch, "handcuff", "handcuffed")' in kill
    assert "ComparisonIndex != 0" in COMMANDS


def test_points_bind_retries_and_uses_customshop():
    assert "g_tried" not in POINTS
    assert "CustomShop_PointsReady" in POINTS
    assert "CustomShop_GetPoints" in POINTS
    assert "CustomShop_SpendPoints" in POINTS
    assert "if (g_get && g_spend) return;" in POINTS


def test_insufficient_balance_is_not_unavailable():
    charge = _between(COMMANDS, "bool ChargePoints", "bool WorldReady")
    assert "EverythingFree" in charge
    assert "PointsUnavailable" in charge
    assert "NoPoints" in charge
    assert "balance < 0" in charge
    assert "balance < price" in charge


def test_chat_sends_wide_so_accents_survive():
    send = _between(COMMANDS, "void SendMsg", "std::string ToLower")
    assert "CP_UTF8" in COMMANDS
    assert "ClientServerChatDirectMessage" in send
    assert "SendServerMessage" not in send


def test_customshop_exports_points_api():
    assert "dllexport) bool CustomShop_PointsReady" in SHOP
    assert "dllexport) int CustomShop_GetPoints" in SHOP
    assert "dllexport) bool CustomShop_SpendPoints" in SHOP


def test_loot_accepts_death_item_cache_and_corpse():
    loot = _between(COMMANDS, "void CmdLoot", "void CmdNome")
    assert "kMinLootFoundations" in COMMANDS
    assert "IsDeathCacheClass" in loot
    assert "deathitem" in COMMANDS
    assert "ComponentToWorld" in COMMANDS
    assert "AShooterCharacter::GetPrivateStaticClass" in loot
    assert "IsDead" in loot
    assert "ServerTransferAllFromRemoteInventory_Implementation" in COMMANDS
    assert "PullInventory" in loot
    assert "bUseDeathCacheCharacterID()()) continue" not in loot
    assert "ChargePoints" in loot


def test_rename_persists_beyond_the_pawn():
    nome = _between(COMMANDS, "void CmdNome", "void CmdKill")
    assert "PersistCharacterName" in nome
    assert "SavePlayerData" in COMMANDS
    assert "names.json" in COMMANDS
    assert "MyPlayerCharacterConfigField" in COMMANDS
    assert "ApplyToPlayerCharacter" in COMMANDS
    assert "ch->RenamePlayer" not in nome


def test_mindwipe_loot_kill_still_perform_the_action():
    mind = _between(COMMANDS, "void CmdMindwipe", "void CmdMissao")
    loot = _between(COMMANDS, "void CmdLoot", "void CmdNome")
    kill = _between(COMMANDS, "void CmdKill", "void CmdAdminReload")
    assert "ChargePoints" in mind and "DoRespec" in mind
    assert "ChargePoints" in loot and "PullInventory" in loot
    assert "ChargePoints" in kill and "Suicide()" in kill
