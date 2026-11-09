"""Atualização automática dos plugins oficiais antes de reinícios agendados."""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Callable

from .plugin_versions import (
    OFFICIAL_PLUGINS,
    bundled_plugin_info_path,
    compare_versions,
    expected_plugin_version,
    get_installed_plugin_version,
    is_plugin_dll_installed,
    server_plugin_dir,
)


def _bundled_files_by_plugin() -> dict[str, Callable[[], dict[str, Path]]]:
    from .shop_integration import (
        bundled_arkeventhunt_files,
        bundled_arkplayer_files,
        bundled_customdino_files,
        bundled_customshop_files,
        bundled_engramlevel_files,
        bundled_fazendarecursos_files,
    )

    return {
        "CustomShop": bundled_customshop_files,
        "CustomDinoDeliver": bundled_customdino_files,
        "ArkPlayer": bundled_arkplayer_files,
        "ArkEventHunt": bundled_arkeventhunt_files,
        "EngramLevel": bundled_engramlevel_files,
        "FazendaRecursos": bundled_fazendarecursos_files,
    }


def update_outdated_official_plugins(install_dir: str) -> str:
    """Atualiza apenas DLLs próprias instaladas e comprovadamente desatualizadas.

    Copia arquivos apenas para a pasta ArkApi/Plugins/<plugin> correspondente.
    Não instala plugins ausentes e não executa instaladores que alterem configs,
    pastas de suporte ou plugins de terceiros.
    """
    if not install_dir or not Path(install_dir).is_dir():
        return "Atualização automática de plugins ignorada: diretório do servidor inválido."

    providers = _bundled_files_by_plugin()
    updated: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    for plugin_name, metadata in OFFICIAL_PLUGINS.items():
        if not is_plugin_dll_installed(install_dir, plugin_name):
            continue

        expected = expected_plugin_version(plugin_name)
        installed = get_installed_plugin_version(install_dir, plugin_name)
        if not expected or not installed or not re.fullmatch(r"\d+(?:\.\d+)*", expected.strip()) or not re.fullmatch(r"\d+(?:\.\d+)*", installed.strip()):
            skipped.append(f"{plugin_name} (versão não identificável)")
            continue
        if compare_versions(installed, expected) >= 0:
            continue

        try:
            payload = providers[plugin_name]()
            dll_name = metadata["dll"]
            if dll_name not in payload or not payload[dll_name].is_file():
                errors.append(f"{plugin_name}: DLL atual ausente no pacote do app")
                continue
            plugin_dir = server_plugin_dir(install_dir, plugin_name)
            plugin_dir.mkdir(parents=True, exist_ok=True)
            # DLL principal por último: falha ao copiar dependências não deve
            # substituir primeiro o binário que ainda está carregável.
            ordered_payload = [
                (filename, source)
                for filename, source in payload.items()
                if filename != dll_name
            ] + [(dll_name, payload[dll_name])]
            for filename, source in ordered_payload:
                if not source.is_file():
                    raise FileNotFoundError(f"arquivo do pacote não encontrado: {filename}")
                shutil.copy2(source, plugin_dir / filename)

            info_source = bundled_plugin_info_path(plugin_name)
            if not info_source or not info_source.is_file():
                raise FileNotFoundError("PluginInfo.json atual ausente no pacote do app")
            shutil.copy2(info_source, plugin_dir / "PluginInfo.json")
            updated.append(f"{plugin_name} {installed} → {expected}")
        except Exception as exc:
            errors.append(f"{plugin_name}: {exc}")

    parts = ["Plugins ARKLAND: atualização antes do reinício concluída."]
    parts.append("Atualizados: " + (", ".join(updated) if updated else "nenhum"))
    if skipped:
        parts.append("Ignorados (versão não identificável): " + ", ".join(skipped))
    if errors:
        parts.append("Falhas: " + "; ".join(errors))
    return " ".join(parts)
