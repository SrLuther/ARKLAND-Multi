"""Contrato estático do plugin CustomShop (Vitrine de Recursos) <-> spec/backend.

Não compila C++: valida que o código-fonte referencia as rotas do backend, que o `/confirmar`
mantém a ordem documentada, que o módulo entra nos três sistemas de build e que a versão
(txt/header/PluginInfo/CHANGELOG) está alinhada.
Spec: docs/VITRINE_RECURSOS_SPEC.md
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugin" / "CustomShop"
SRC = PLUGIN / "src"
ROUTES = ROOT / "plugin" / "arkshop_web" / "resource_vitrine_routes.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_vitrine_sources_exist() -> None:
    assert (SRC / "ShopVitrine.cpp").is_file()
    assert (SRC / "ShopVitrine.h").is_file()


@pytest.mark.parametrize(
    "build_file, needles",
    [
        ("build_cl.bat", ("ShopVitrine.cpp", "ShopVitrine.obj")),
        ("CMakeLists.txt", ("src/ShopVitrine.cpp",)),
        ("CustomShop.vcxproj", ("src\\ShopVitrine.cpp", "src\\ShopVitrine.h")),
    ],
)
def test_vitrine_in_every_build_system(build_file: str, needles: tuple[str, ...]) -> None:
    text = _read(PLUGIN / build_file)
    for needle in needles:
        assert needle in text, f"{build_file} sem {needle}"


def test_vitrine_command_registered_and_configurable() -> None:
    vit = _read(SRC / "ShopVitrine.cpp")
    assert 'AddChatCommand("/vitrine"' in vit
    assert 'RemoveChatCommand("/vitrine")' in vit

    cmds = _read(SRC / "Commands.cpp")
    assert "Vitrine::RegisterCommands()" in cmds
    assert "Vitrine::UnregisterCommands()" in cmds
    assert "VitrineCommandEnabled()" in cmds

    cfg_h = _read(SRC / "ShopConfig.h")
    cfg_cpp = _read(SRC / "ShopConfig.cpp")
    for key in ("VitrineCommandEnabled", "VitrinePreviewTtlSeconds"):
        assert key in cfg_h and key in cfg_cpp


def test_plugin_api_paths_match_backend_routes() -> None:
    """Toda rota usada pelo C++ existe no blueprint de rotas do backend (prefixo plugin/)."""
    routes = _read(ROUTES)
    backend = set(re.findall(r'f"\{PREFIX\}/plugin(/[^"]*)"', routes))
    assert backend, "rotas plugin/ não encontradas no backend"

    def norm(path: str) -> str:
        return re.sub(r"<[^>]+>", "<x>", path.rstrip("/"))

    backend_norm = {norm(p) for p in backend}

    vit = _read(SRC / "ShopVitrine.cpp")
    assert 'kApi = "/api/market/resources/plugin"' in vit
    assert 'PREFIX = "/api/market/resources"' in routes

    used = {
        "/config",
        "/stock/<x>",
        "/upload",
        "/upload/<x>",
        "/upload/cancel",
        "/pending/<x>",
        "/claims/claim",
        "/claims/release",
        "/claims/delivered",
    }
    # /upload/<x> e /upload/cancel coexistem no backend; confere cada uma.
    assert used <= backend_norm, f"rotas do plugin ausentes no backend: {used - backend_norm}"

    for fragment in (
        '"/config"',
        '"/stock/"',
        '"/upload"',
        '"/upload/cancel"',
        '"/upload/" + upload_id',
        '"/pending/"',
        '"/claims/claim"',
        '"/claims/release"',
        '"/claims/delivered"',
    ):
        assert fragment in vit, f"ShopVitrine.cpp sem {fragment}"


def test_confirmar_dispatch_order() -> None:
    """engramas -> notas -> marco -> vitrine -> mercado (/enviar de dino)."""
    text = _read(SRC / "ShopMarket.cpp")
    start = text.index("void ShopMarket::CmdConfirmar")
    body = text[start:]
    order = [
        "Engrams::HasPendingUnlock(sid)",
        "Notes::HasPendingUnlock(sid)",
        "Teams::HasPendingDeposit(sid)",
        "Vitrine::HasPending(sid)",
        "g_confirm_exec_mutex",
    ]
    positions = [body.index(token) for token in order]
    assert positions == sorted(positions), dict(zip(order, positions))
    assert "Vitrine::ConfirmPending(player)" in body


def test_single_pending_guards_both_directions() -> None:
    vit = _read(SRC / "ShopVitrine.cpp")
    for token in (
        "Engrams::HasPendingUnlock",
        "Notes::HasPendingUnlock",
        "Teams::HasPendingDeposit",
        "ShopMarket::HasPendingEnviar",
    ):
        assert token in vit, f"/vitrine não verifica {token}"

    assert "Vitrine::HasPending" in _read(SRC / "ShopMarket.cpp")  # /enviar + /confirmar
    assert "Vitrine::HasPending" in _read(SRC / "ShopTeams.cpp")  # /marco
    cmds = _read(SRC / "Commands.cpp")  # /engramas e /notas
    assert cmds.count("Vitrine::HasPending") >= 2
    assert "HasPendingEnviar" in _read(SRC / "ShopMarket.h")


def test_item_safety_flow_markers() -> None:
    """Journal -> remove -> POST idempotente -> cancel/devolve; ordem no ConfirmPending."""
    vit = _read(SRC / "ShopVitrine.cpp")
    assert "vitrine_journal" in vit
    assert "MOVEFILE_REPLACE_EXISTING" in vit and "FlushFileBuffers" in vit
    for state in ('"planned"', '"removed"'):
        assert state in vit

    body = vit[vit.index("void ConfirmPending"):]
    order = [
        "SaveJournal(j)",  # planned antes de remover
        "RemovePlain(player",
        'j.state = "removed"',
        "PostUpload(j)",
        "CancelUpload(j)",
    ]
    positions = [body.index(token) for token in order]
    assert positions == sorted(positions), dict(zip(order, positions))
    # Depois do cancel confirmado (CANCELLED) os itens são devolvidos.
    assert body.rindex("ReturnItems(j, player)") > body.index("CancelUpload(j)")

    # Recuperação: login, /vitrine, /mercado e inicialização do mapa.
    assert "RecoverForSteamId" in _read(SRC / "Main.cpp")
    assert "RecoverAll" in _read(SRC / "Main.cpp")
    assert "RecoverForPlayer" in _read(SRC / "ShopMarket.cpp")
    assert "RecoverForPlayer(player)" in vit

    # Entrega no /mercado: stacks via Store + dinos primeiro.
    assert "GiveResourceStacks" in _read(SRC / "ShopStore.h")
    market = _read(SRC / "ShopMarket.cpp")
    assert "Vitrine::DeliverMarketClaims" in market


def test_version_aligned_across_artifacts() -> None:
    version = _read(PLUGIN / "plugin_version.txt").strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    assert f'"{version}"' in _read(SRC / "plugin_version.h")
    for rel in ("configs/PluginInfo.json", "bin/PluginInfo.json"):
        info = json.loads(_read(PLUGIN / rel))
        assert info["VersionLabel"] == version, rel
    assert f"## [{version}]" in _read(PLUGIN / "CHANGELOG.md")
    # A feature entrou em 1.10.41 ou posterior.
    parts = tuple(int(x) for x in version.split("."))
    assert parts >= (1, 10, 41)
    assert "## [1.10.41]" in _read(PLUGIN / "CHANGELOG.md")


def test_normalize_blueprint_matches_plugin_inputs() -> None:
    """O backend normaliza o nome completo da classe do item como o C++ espera."""
    sys.path.insert(0, str(ROOT / "plugin" / "arkshop_web"))
    try:
        svc = pytest.importorskip("resource_vitrine_service")
    finally:
        sys.path.pop(0)

    stone = "/Game/PrimalEarth/CoreBlueprints/Resources/PrimalItemResource_Stone.PrimalItemResource_Stone"
    pkg = stone.rsplit(".", 1)[0]
    for raw in (
        f"BlueprintGeneratedClass {stone}_C",  # GetFullName da classe do item
        f"Blueprint'{stone}'",
        f"{stone}_C",
        f"{stone}_c",
        stone,
        # GetFullName do default object (CDO): .../Stone.Default__PrimalItemResource_Stone_C
        f"PrimalItemResource_Stone_C {pkg}.Default__PrimalItemResource_Stone_C",
    ):
        assert svc.normalize_blueprint(raw) == (stone, stone.lower()), raw

    vit = _read(SRC / "ShopVitrine.cpp")
    # O plugin nao pode casar so com GetFullName: ClassToStringReference e o texto do giveitem.
    assert "ClassToStringReference" in vit
    assert "Default__" in vit
    assert "GetDefaultObject" in vit
    assert "ResourceVitrine" in vit
    assert "origem=" in vit

    sys.path.insert(0, str(ROOT / "plugin" / "arkshop_web"))
    try:
        match = pytest.importorskip("vitrine_match")
    finally:
        sys.path.pop(0)
    for raw in match.HIDE_ARK_FORMS:
        assert match.resources_match(match.HIDE_BLUEPRINT, raw), raw
    assert match.choose_vitrine_source(True, [], [{"blueprint": match.HIDE_BLUEPRINT}])[0] == "arquivo"
    assert match.choose_vitrine_source(False, None, [{"blueprint": match.HIDE_BLUEPRINT}])[0] == "arquivo"
    assert match.choose_vitrine_source(True, [{"blueprint": match.HIDE_BLUEPRINT}], [])[0] == "mysql"
    # Lista vazia e "nao esta carregando" sao mensagens diferentes.
    assert "Nenhum recurso esta autorizado na vitrine ainda" in vit
    assert "Nenhum recurso autorizado no seu inventario pessoal" in vit
    assert "tem durabilidade" in vit
