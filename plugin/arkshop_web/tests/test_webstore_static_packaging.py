"""Garante que o pacote WebStore nao embute PNGs de pipeline (raw/demo/preview)."""
from __future__ import annotations

from pathlib import Path


def _would_package(rel_posix: str) -> bool:
    prefixes = (
        "species/icons/generated/raw/",
        "species/icons/generated/preview/",
        "species/icons/demo/",
    )
    return not any(rel_posix.startswith(p) for p in prefixes)


def test_webstore_static_excludes_pipeline_icon_dirs():
    assert not _would_package("species/icons/generated/raw/rex.png")
    assert not _would_package("species/icons/generated/preview/rex_frame_v1.png")
    assert not _would_package("species/icons/demo/foo.webp")
    assert _would_package("species/icons/generated/rex.webp")
    assert _would_package("ambar.png")
    assert _would_package("logo.png")
    assert _would_package("SeasonLand_Logo.png")
    assert _would_package("ArkLnd_Equipes.png")


def test_generated_webp_exist_without_needing_raw_at_runtime():
    static = Path(__file__).resolve().parents[1] / "static"
    webp_dir = static / "species" / "icons" / "generated"
    webps = list(webp_dir.glob("*.webp"))
    assert len(webps) >= 50
    # raw continua no tree para o gerador, mas nao e necessario para servir
    assert (webp_dir / "manifest.json").is_file()
