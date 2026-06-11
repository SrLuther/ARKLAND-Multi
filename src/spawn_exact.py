"""
Fase 6.1 — Gerador de SpawnExactDino.

Produz o comando `cheat SpawnExactDino ...` byte-a-byte compatível com
ArkUtils (https://arkutils.netlify.app/tools/spawnexact).

Sintaxe do comando:
  cheat SpawnExactDino
    "<BlueprintPath>"         # blueprint da criatura
    "<SaddleBP>"              # saddle ou ""
    <SaddleQuality>           # float (0 = sem sela)
    <BaseLevel>               # soma(base_stats) + 1
    <ExtraLevels>             # soma(added_stats)
    "<base_stats>"            # "H,S,O,F,W,M,Sp,C"  (8 valores)
    "<added_stats>"           # "H,S,O,F,W,M,Sp,C"
    "<Name>"
    <Cloned>                  # 0/1
    <Neutered>                # 0/1
    "<TamedDate>"
    "<UploadedFrom>"
    "<ImprinterName>"
    <ImprinterID>             # UE4 ID (int64)
    <ImprintQuality>          # 0.0–1.0
    0                         # sempre 0
    "<Colors>"                # "r0,r1,r2,r3,r4,r5" ou ""
    <DinoID>                  # 0 = auto
    <Exp>                     # experiência
    <SpawnDist>               # distância à frente
    <SpawnY>                  # offset lateral
    <SpawnZ>                  # offset vertical
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


# Índices dos stats (ordem fixa do ARK)
STAT_NAMES = ["Health", "Stamina", "Oxygen", "Food", "Weight",
              "Melee", "Speed", "Crafting"]
STAT_COUNT = 8
COLOR_COUNT = 6


@dataclass
class SpawnExactParams:
    """Parâmetros completos para gerar o comando SpawnExactDino."""

    # Obrigatório
    blueprint: str = ""          # "Blueprint'/Game/.../Rex_Character_BP.Rex_Character_BP'"

    # Sela
    saddle_bp: str = ""          # "" = sem sela
    saddle_quality: float = 0.0

    # Níveis selvagens (wild) — 8 stats
    base_stats: List[int] = field(default_factory=lambda: [0] * STAT_COUNT)

    # Níveis domados (tamed additions)
    added_stats: List[int] = field(default_factory=lambda: [0] * STAT_COUNT)

    # Identidade
    name: str = ""
    cloned: bool = False
    neutered: bool = False
    tamed_date: str = ""
    uploaded_from: str = ""

    # Imprint
    imprinter_name: str = ""
    imprinter_id: int = 0
    imprint_quality: float = 0.0  # 0.0–1.0

    # Cores (6 regiões, 0 = padrão)
    colors: List[int] = field(default_factory=lambda: [0] * COLOR_COUNT)

    # Posição
    spawn_dist: float = 200.0
    spawn_y: float = 0.0
    spawn_z: float = 0.0

    # Misc
    dino_id: int = 0
    experience: float = 0.0


def _fmt_stats(stats: list[int]) -> str:
    return ",".join(str(max(0, v)) for v in stats)


def _fmt_colors(colors: list[int]) -> str:
    return ",".join(str(max(0, v)) for v in colors)


def _base_level(base_stats: list[int]) -> int:
    return sum(max(0, v) for v in base_stats) + 1


def _extra_levels(added_stats: list[int]) -> int:
    return sum(max(0, v) for v in added_stats)


def build_command(p: SpawnExactParams) -> str:
    """Gera o comando SpawnExactDino completo."""
    bp     = p.blueprint.strip()
    saddle = p.saddle_bp.strip()

    base   = _base_level(p.base_stats)
    extra  = _extra_levels(p.added_stats)

    bs = _fmt_stats(p.base_stats)
    ads = _fmt_stats(p.added_stats)
    cols = _fmt_colors(p.colors)

    parts = [
        f'cheat SpawnExactDino',
        f'"{bp}"',
        f'"{saddle}"',
        f'{p.saddle_quality:.1f}',
        f'{base}',
        f'{extra}',
        f'"{bs}"',
        f'"{ads}"',
        f'"{p.name}"',
        f'{"1" if p.cloned else "0"}',
        f'{"1" if p.neutered else "0"}',
        f'"{p.tamed_date}"',
        f'"{p.uploaded_from}"',
        f'"{p.imprinter_name}"',
        f'{p.imprinter_id}',
        f'{p.imprint_quality:.2f}',
        f'0',
        f'"{cols}"',
        f'{p.dino_id}',
        f'{p.experience:.0f}',
        f'{p.spawn_dist:.0f}',
        f'{p.spawn_y:.0f}',
        f'{p.spawn_z:.0f}',
    ]
    return " ".join(parts)


def _validate(p: SpawnExactParams) -> list[str]:
    """Retorna lista de erros de validação (vazia = OK)."""
    errs: list[str] = []
    if not p.blueprint:
        errs.append("Blueprint da criatura é obrigatório.")
    if len(p.base_stats) != STAT_COUNT:
        errs.append(f"base_stats deve ter {STAT_COUNT} elementos.")
    if len(p.added_stats) != STAT_COUNT:
        errs.append(f"added_stats deve ter {STAT_COUNT} elementos.")
    if len(p.colors) != COLOR_COUNT:
        errs.append(f"colors deve ter {COLOR_COUNT} elementos.")
    if not (0.0 <= p.imprint_quality <= 1.0):
        errs.append("imprint_quality deve estar entre 0.0 e 1.0.")
    return errs


def validate_and_build(p: SpawnExactParams) -> tuple[bool, str]:
    """Valida e gera o comando. Retorna (ok, comando_ou_erro)."""
    errs = _validate(p)
    if errs:
        return False, "\n".join(errs)
    return True, build_command(p)


# ─── Testes rápidos ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Exemplo do arkids.net (Brontosaurus)
    p = SpawnExactParams(
        blueprint="Blueprint'/Game/PrimalEarth/Dinos/Sauropod/Sauropod_Character_BP.Sauropod_Character_BP'",
        saddle_bp="Blueprint'/Game/PrimalEarth/CoreBlueprints/Items/Armor/Saddles/PrimalItemArmor_SauroSaddle.PrimalItemArmor_SauroSaddle'",
        saddle_quality=10.0,
        base_stats=[1, 2, 3, 4, 5, 6, 7, 8],
        added_stats=[1, 2, 3, 4, 5, 6, 7, 8],
        name="CoolDino",
        imprinter_name="John",
        imprinter_id=129475024,
        imprint_quality=1.0,
        colors=[1, 2, 3, 4, 5, 6],
        experience=1000,
        spawn_dist=100,
        spawn_y=200,
        spawn_z=300,
    )
    ok, cmd = validate_and_build(p)
    assert ok, cmd
    # Verifica base_level = sum(base_stats)+1 = 37
    assert " 37 " in cmd
    # Verifica extra_levels = sum(added_stats) = 36
    assert " 36 " in cmd
    print("spawn_exact OK")
    print(cmd[:120], "...")
