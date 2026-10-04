"""Contrato do plugin EngramLevel: um nível por clique, sem buyout do catálogo."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin" / "EngramLevel"


def _src(*parts: str) -> str:
    return (PLUGIN.joinpath(*parts)).read_text(encoding="utf-8")


def applied_level_span(
    before_base: int,
    after_base: int,
    before_char: int,
    after_char: int,
    available_before: int,
    available_after: int,
) -> list[int]:
    """Espelho de AppliedLevelSpan — níveis deste apply, não a faixa 1..atual."""
    if after_base > before_base and after_base > 0:
        return [after_base]
    if after_char > before_char and after_char > 0:
        return [after_char]
    if available_before > available_after and before_char > 1:
        points = available_before - available_after
        first = before_char - available_before + 1
        if first < 1:
            first = 1
        out: list[int] = []
        for i in range(points):
            level = first + i
            if level > before_char:
                break
            out.append(level)
        return out
    if after_char > 0:
        return [after_char]
    return [before_char] if before_char > 0 else []


def applied_level(
    before_base: int,
    after_base: int,
    before_char: int,
    after_char: int,
    available_before: int,
    available_after: int,
) -> int:
    span = applied_level_span(
        before_base, after_base, before_char, after_char,
        available_before, available_after,
    )
    return span[0] if span else 0


def grant_batches(levels: list[int], unlock_non_tek: bool, unlock_total: bool):
    """Espelho de GrantBatchesForSpentLevels. bool True = lote tek."""
    if len(levels) <= 1:
        return []
    out: list[tuple[int, bool]] = []
    for level in levels:
        if level <= 0:
            continue
        non_tek_step = unlock_total or unlock_non_tek
        if not non_tek_step:
            continue
        out.append((level, False))
        if unlock_total:
            out.append((level, True))
    return out


def engram_filter_hits(internal_name: str, shown_name: str, filt: str) -> bool:
    def norm(value: str) -> str:
        return value.strip().lower()

    token = norm(filt)
    if not token or "primalitem" in token or "/game/" in token:
        return False
    return norm(internal_name) == token or norm(shown_name) == token


def test_applied_level_is_one_level_not_the_catalog():
    header = _src("src", "EngramGrant.h")
    assert "AppliedLevelSpan" in header
    assert "before_char - available_before + 1" in header
    assert "kDefaultCatalogBuyoutPoints = 999" in header

    # Level up em que o nível sobe.
    assert applied_level(10, 11, 10, 11, 1, 0) == 11
    assert applied_level(49, 49, 49, 50, 1, 0) == 50
    # Mindwipe: nível 200 fica, 199 pontos voltam. Cada clique é um nível.
    assert applied_level(200, 200, 200, 200, 199, 198) == 2
    assert applied_level(200, 200, 200, 200, 100, 99) == 101
    assert applied_level(200, 200, 200, 200, 1, 0) == 200
    # Não devolve a soma nem o tamanho do catálogo.
    assert applied_level(200, 200, 200, 200, 199, 198) != 200
    assert applied_level(200, 200, 200, 200, 199, 198) < 999
    # Vários pontos no mesmo apply: a faixa, não só o primeiro.
    assert applied_level_span(200, 200, 200, 200, 199, 194) == [2, 3, 4, 5, 6]
    assert applied_level_span(200, 200, 200, 200, 199, 0) == list(range(2, 201))
    assert applied_level(200, 200, 200, 200, 199, 194) == 2


def test_hook_suppresses_auto_unlock_and_skips_buyout():
    hooks = _src("src", "EngramHooks.cpp")
    grant = _src("src", "EngramGrant.cpp")
    original = "UPrimalCharacterStatusComponent_ServerApplyLevelUp_original"
    flag_off = "bAutoUnlockAllEngramsField() = false"
    assert "ServerApplyLevelUp" in hooks
    assert flag_off in hooks
    # O return cedo (dino / desligado) chama o original antes. No caminho do
    # jogador a flag sai primeiro e o original vem depois.
    assert original in hooks[hooks.index(flag_off):]
    assert "IsCatalogBuyout" in hooks
    assert "points[i] = 0" in hooks
    assert "ScheduleOwnedReread" in hooks
    assert "UnlockExactLevel" not in hooks
    assert "ServerUnlockEngram" not in hooks
    assert "required != level" in grant
    assert "GetRequiredLevel" in grant
    assert "GiveEngrams" not in grant
    assert "GiveEngrams" not in hooks
    assert "UnlockAll(" not in grant
    assert "UnlockAll(" not in hooks
    assert "AddChatCommand" not in _src("src", "Main.cpp")


def test_config_buyout_is_999_and_version_matches():
    cfg = json.loads(_src("configs", "config.json"))
    block = cfg["EngramLevel"]
    assert block["Enabled"] is True
    assert block["UnlockNonTek"] is True
    assert block["UnlockTotal"] is False
    assert block["Engrams"] == []
    assert block["ExtraEngrams"] == []
    assert block["RemovedEngrams"] == []
    assert block["SuppressAutoUnlockDuringLevelUp"] is True
    assert block["UnlockOnlyAppliedLevel"] is True
    assert block["CatalogBuyoutPoints"] == 999

    version = (PLUGIN / "plugin_version.txt").read_text(encoding="utf-8").strip()
    info = json.loads(_src("configs", "PluginInfo.json"))
    assert info["VersionLabel"] == version == "0.1.0"
    assert 'ARKLAND_PLUGIN_VERSION "0.1.0"' in _src("src", "plugin_version.h")
    assert "mindwipe" in _src("README.md").lower()
    assert "## [0.1.0]" in _src("CHANGELOG.md")


def test_grant_tier_never_mixes_tek_and_non_tek():
    header = _src("src", "EngramGrant.h")
    assert "ChooseGrantTier" in header
    assert "unlock_total" in header
    # Total desligado: só não tek. Total ligado: um tipo por clique.
    assert _tier(False, False, True) == "none"
    assert _tier(True, False, True) == "nontek"
    assert _tier(True, True, True) == "nontek"
    assert _tier(False, True, True) == "nontek"
    assert _tier(True, True, False) == "tek"
    assert _tier(False, True, False) == "tek"


def _tier(unlock_non_tek: bool, unlock_total: bool, any_locked_non_tek: bool) -> str:
    if unlock_total:
        return "nontek" if any_locked_non_tek else "tek"
    if unlock_non_tek:
        return "nontek"
    return "none"


def _merge(embedded, configured, use_configured, extra, removed):
    base = list(configured) if use_configured else list(embedded)
    out: list[str] = []
    for raw in list(base) + list(extra):
        item = raw.strip().lower()
        if item and item not in out:
            out.append(item)
    dropped = {r.strip().lower() for r in removed}
    return [item for item in out if item not in dropped]


def test_extra_engrams_are_added_and_do_not_replace_the_base():
    header = _src("src", "EngramGrant.h")
    assert "use_configured ? configured : embedded" in header
    assert "ExtraEngrams" in _src("src", "EngramConfig.cpp")
    embedded = ["pike", "tek_rifle"]
    # Engrams vazio: a base fica, o extra soma.
    merged = _merge(embedded, [], False, ["mod_sword"], [])
    assert merged == ["pike", "tek_rifle", "mod_sword"]
    # Extra repetido não duplica e não apaga a base.
    assert _merge(embedded, [], False, ["pike"], []) == ["pike", "tek_rifle"]
    # Lista preenchida é a base editada; o extra continua a somar.
    edited = _merge(embedded, ["pike"], True, ["mod_sword"], [])
    assert edited == ["pike", "mod_sword"]
    assert "tek_rifle" not in edited
    # Apagar um item tira só esse.
    assert _merge(embedded, [], False, ["mod_sword"], ["Pike"]) == [
        "tek_rifle",
        "mod_sword",
    ]


def test_autoengram_starts_off_and_tek_follows_unlock_total():
    """Novo jogador desligado. Tek só com UnlockTotal, e nunca no mesmo clique."""
    header = _src("src", "EngramCommands.h")
    commands = _src("src", "EngramCommands.cpp")
    hooks = _src("src", "EngramHooks.cpp")
    grant = _src("src", "EngramGrant.cpp")
    readme = _src("README.md")

    assert "return false" in header
    assert "autoengram.json" in commands
    assert '"OptedIn"' in commands
    assert "AddChatCommand" in commands
    assert "/autoengram" in commands
    assert "Desbloqueio automático ligado" in _src("src", "EngramGrant.h")
    assert "engramas não tek na fila até o nível" in _src("src", "EngramGrant.h")
    assert "Desbloqueados " in _src("src", "EngramGrant.h")
    assert "engramas não tek até o nível" in _src("src", "EngramGrant.h")
    assert "entraram na fila até o nível" in _src("src", "EngramGrant.h")
    assert "Nenhum engrama pendente até o nível" in _src("src", "EngramGrant.h")
    assert "kQueueBlock = 10" in _src("src", "EngramGrant.h")
    assert "kQueueDelaySeconds = 1" in _src("src", "EngramGrant.h")
    assert "return !block_already_sent" in _src("src", "EngramGrant.h")
    assert "sem jogador" in _src("src", "EngramGrant.h")
    assert "lista vazia" in _src("src", "EngramGrant.h")
    assert "nível 0" in _src("src", "EngramGrant.h")
    assert "todos já constavam como aprendidos" in _src("src", "EngramGrant.h")
    assert "nenhum com esse nível" in _src("src", "EngramGrant.h")
    assert "CatchUpChat" in commands
    assert "Desbloqueio automático desligado" in commands
    assert "Desbloqueio automático desligado no servidor." in commands
    enabled_gate = commands.index("!EngramLevel::Config::Get().Enabled()")
    toggle_call = commands.index("Prefs::Toggle")
    assert enabled_gate < toggle_call

    auto_gate = hooks.index("Prefs::IsAutoEnabled")
    assert auto_gate < hooks.index("ScheduleOwnedReread")
    assert "UnlockExactLevel" not in hooks
    assert "UnlockSpentLevels" not in hooks
    assert "ServerUnlockEngram" not in hooks
    assert "UnlockExactLevel" not in commands
    assert "UnlockSpentLevels" not in commands
    toggle_on = commands.split("if (on)", 1)[1].split("SendPlayer", 1)[0]
    assert "BeginOwnedQueue" in toggle_on
    assert "UnlockOwnedNonTek" not in toggle_on
    assert "bAutoUnlockAllEngrams" not in commands
    assert "GiveEngrams" not in commands
    assert "UnlockAll(" not in commands

    # O gate de tek do apply olha só os não tek deste nível.
    assert "required != level" in grant
    assert "required > known_level" not in grant
    assert "OwnedNonTekFits" in grant
    owned = grant.split("UnlockReport UnlockOwnedNonTek", 1)[1]
    assert "GrantTier::NonTek" in owned
    assert "GrantTier::Tek" not in owned
    assert "ServerUnlockEngram" in grant
    assert "EngramItemBlueprintsField" in grant
    assert "HasEngram(" not in grant
    assert "ClientNotifyUnlockedEngram" in grant
    assert "bAutoUnlockAllEngrams" not in grant
    assert "ApplyChat" not in hooks
    assert "FinishChat" in grant
    assert "DelayExecute" in grant
    assert "EngramLevel.Queue" in grant
    assert "AddOnTimerCallback" in grant
    assert "/ae" in commands
    assert "RefreshOwnedQueue" in commands
    assert "CancelPlayerQueue" in commands
    assert "LevelUpRestartsWait" in grant
    assert "kQueueBlock" in grant

    opted: list[str] = []
    assert "76561198000000000" not in opted
    opted.append("76561198000000000")
    assert "76561198000000000" in opted
    opted.remove("76561198000000000")
    assert "76561198000000000" not in opted

    # UnlockTotal false: o comando não escolhe tek.
    assert _tier(True, False, False) == "nontek"
    assert _tier(True, False, True) == "nontek"
    # UnlockTotal true: não tek deste nível primeiro; tek só quando já foram.
    assert _tier(True, True, True) == "nontek"
    assert _tier(True, True, False) == "tek"

    assert "desligado" in readme.lower()
    assert "UnlockTotal: false" in readme
    assert "UnlockTotal: true" in readme


def test_mask_stays_off_until_unload_or_enabled_false():
    """A flag e o buyout não voltam no fim do apply. Isso rearmava o crash."""
    hooks = _src("src", "EngramHooks.cpp")
    main = _src("src", "Main.cpp")
    hook = hooks.split("void Hook_UPrimalCharacterStatusComponent_ServerApplyLevelUp", 1)[1]
    hook = hook.split("} // namespace", 1)[0]
    last_original = hook.rindex("UPrimalCharacterStatusComponent_ServerApplyLevelUp_original")
    after = hook[last_original:]
    assert "bAutoUnlockAllEngramsField() =" not in after
    assert "points[i] = 0" not in after
    assert "ReleaseCrashMask" not in hook
    assert "RestoreCrashMask" not in hook

    assert "bAutoUnlockAllEngramsField() = false" in hooks
    assert "points[i] = 0" in hooks
    assert "bAutoUnlockAllEngramsField() = g_saved_auto_unlock" in hooks
    assert "ReleaseCrashMask" in main
    assert main.index("Hooks::Unregister") < main.index("ReleaseCrashMask")
    assert "SyncCrashMask" in main
    assert "enquanto o plugin estiver ligado" in hooks


def test_null_game_mode_skips_original_and_does_not_rearm_the_flag():
    hooks = _src("src", "EngramHooks.cpp")
    hook = hooks.split("void Hook_UPrimalCharacterStatusComponent_ServerApplyLevelUp", 1)[1]
    hook = hook.split("} // namespace", 1)[0]
    log = (
        "ServerApplyLevelUp sem GameMode alcançável — "
        "original não foi chamado e a flag não foi reativada"
    )
    assert log in hook
    assert "ApplyCrashMask(status, by_pc)" in hook
    assert hook.index("g_in_level_up = false") < hook.index(log)
    assert hook.index(log) < hook.rindex("ServerApplyLevelUp_original")
    window = hook[hook.index(log):hook.index(log) + 400]
    assert "return" in window
    assert "bAutoUnlockAllEngramsField() = g_saved_auto_unlock" not in window
    assert "não foi reativada" in hooks
    assert "não mascarou" not in log
    assert "mapa ainda sem mundo" not in log
    # Apply real: mundo do componente, dono, outer e controller.
    assert "AuthorityGameModeField()" in hooks
    assert "status->GetWorld()" in hooks
    assert "status->GetOwner()" in hooks
    assert "CachedOwnerField()" in hooks
    assert "OuterField()" in hooks
    assert "WorldFromOuter(status)" in hooks
    assert "ModeFromActor(by_pc" in hooks
    # Arranque e Reload antes do mapa: nenhum log.
    assert "não mascarou bAutoUnlockAllEngrams" not in hooks
    assert "mapa ainda sem mundo" not in hooks
    sync = hooks.split("void SyncCrashMask", 1)[1].split("void ReleaseCrashMask", 1)[0]
    assert "Log::GetLog()" not in sync
    assert "g_in_level_up = true" not in sync


def test_autoengram_write_is_atomic_and_bad_json_keeps_memory():
    commands = _src("src", "EngramCommands.cpp")
    assert "MoveFileExA" in commands
    assert ".tmp" in commands
    assert "CreateDirectoryA" in commands
    assert "MOVEFILE_REPLACE_EXISTING" in commands
    load = commands.split("void Load()", 1)[1].split("bool IsAutoEnabled", 1)[0]
    assert "g_opted_in.clear()" not in commands
    assert "g_opted_in.clear()" not in load
    assert "mantendo o último estado em memória" in load
    assert "inválido" in load


def test_engram_filter_is_exact_name_not_a_substring():
    header = _src("src", "EngramGrant.h")
    grant = _src("src", "EngramGrant.cpp")
    readme = _src("README.md")
    assert "EngramFilterHits" in header
    assert "EngramListHits" in grant
    assert ".find(" not in grant
    assert "npos" not in grant
    assert engram_filter_hits("EngramEntry_TekRifle_C", "Tek Rifle", "rifle") is False
    assert engram_filter_hits("EngramEntry_Rifle_C", "Rifle", "rifle") is True
    assert engram_filter_hits("EngramEntry_TekRifle_C", "Tek Rifle", "tek rifle") is True
    assert engram_filter_hits(
        "EngramEntry_TekRifle_C", "Tek Rifle", "engramentry_tekrifle_c"
    ) is True
    assert engram_filter_hits(
        "EngramEntry_StoneHatchet_C",
        "Machado de Pedra",
        "PrimalItem_WeaponStoneHatchet_C",
    ) is False
    assert engram_filter_hits(
        "EngramEntry_StoneHatchet_C",
        "Machado de Pedra",
        "/Game/PrimalEarth/CoreBlueprints/Weapons/PrimalItem_WeaponStoneHatchet",
    ) is False
    assert "EngramIdRejected" in header
    assert "exata" in readme.lower()
    assert "rifle" in readme.lower()


def test_mindwipe_multi_point_unlocks_one_level_at_a_time():
    header = _src("src", "EngramGrant.h")
    hooks = _src("src", "EngramHooks.cpp")
    grant = _src("src", "EngramGrant.cpp")
    readme = _src("README.md")
    assert "GrantBatchesForSpentLevels" in header
    assert "UnlockSpentLevels" in grant
    assert "UnlockSpentLevels" not in hooks
    assert "ScheduleOwnedReread" in hooks
    assert hooks.index("ServerApplyLevelUp_original") < hooks.index("ScheduleOwnedReread")
    assert "GetRequiredLevel" in grant
    assert "RequiredCharacterLevelField" in grant

    assert grant_batches([2], True, True) == []
    assert grant_batches([2, 3], True, False) == [(2, False), (3, False)]
    assert grant_batches([2, 3], False, False) == []
    batches = grant_batches([2, 3], True, True)
    assert batches == [(2, False), (2, True), (3, False), (3, True)]
    # Tek do nível 2 só depois do não tek desse nível, nunca no mesmo lote.
    assert batches[0] == (2, False)
    assert batches[1] == (2, True)
    assert all(batches[i][1] != batches[i + 1][1] or batches[i][0] != batches[i + 1][0]
               for i in range(len(batches) - 1))
    assert "antes de `/autoengram`" in readme or "antes do /autoengram" in readme.lower()
    assert "mindwipe" in readme.lower()


def test_preset_999_is_the_buyout_the_plugin_refuses():
    """O 999 do nivel200.txt é o valor que o plugin não concede. 800 fica."""
    from src.player_level_200 import level_200_engram_points

    points = level_200_engram_points()
    assert 999 in points
    assert max(p for p in points if p != 999) <= 800
