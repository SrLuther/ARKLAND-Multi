"""
Script one-shot: varre src/pages/*.py e src/dialogs/*.py,
detecta símbolos usados sem importação e adiciona os imports faltantes.
"""
from __future__ import annotations
import ast
import re
from pathlib import Path

ROOT = Path(__file__).parent

# ── Mapa: símbolo → módulo relativo (relativo a src/pages/ ou src/dialogs/)
SYMBOL_MODULE: dict[str, str] = {}

def _reg(module: str, *symbols: str) -> None:
    for s in symbols:
        SYMBOL_MODULE[s] = module

# ui_constants
_reg("..ui_constants",
     "_TZ_BRASILIA", "now_brasilia",
     "_GREEN", "_GREEN_DARK", "_GREEN_HOVER", "_RED_DARK", "_RED_HOVER",
     "_BLUE", "_BLUE_HOVER", "_SIDEBAR_BG", "_CARD_BG", "_BG",
     "_MAX_SYNC_CYCLES", "_MAX_SYNC_FOLDERS",
     "_FORM_FONT_BOLD", "_FORM_FONT_HINT", "_FORM_LABEL_FG", "_FORM_HINT_FG",
     "_STATUS_COLOR", "_STATUS_LABEL",
     "_ARK_OFFICIAL_EVENTS", "_ARK_EVENT_ID_TO_LABEL", "_ARK_EVENT_LABEL_TO_ID",
     "_parse_listplayers", "_set_windows_startup", "_resource_path", "_hostname",
     "_safe_extract_zip", "_Tooltip",
)
# version
_reg("..version", "APP_VERSION", "BUILD_DATE", "CHANGELOG")
# server_config
_reg("..server_config",
     "ARK_MAPS", "ARK_MAP_NAMES",
     "SERVER_STATUS_STOPPED", "SERVER_STATUS_STARTING", "SERVER_STATUS_RUNNING",
     "SERVER_STATUS_STOPPING", "SERVER_STATUS_CRASHED", "SERVER_STATUS_UPDATING",
     "ServerConfig",
)
# buff_manager
_reg("..buff_manager",
     "BuffManager", "BuffEvent", "BuffPreset", "BuffRates",
     "BUFF_TYPE_XP", "BUFF_TYPE_DOMA", "BUFF_TYPE_BREEDING", "BUFF_TYPE_FARM",
     "BUFF_TYPE_LABELS", "BUFF_RATE_FIELDS", "QUICK_PRESETS",
     "BUFF_STATUS_SCHEDULED", "BUFF_STATUS_CANCELLED",
)
# rcon_client
_reg("..rcon_client", "RconClient", "RconError")
# change_logger
_reg("..change_logger", "ChangeLogger", "snapshot_server", "diff_snapshots")
# ark_ini
_reg("..ark_ini",
     "ArkIniManager", "parse_ini_text_to_sections",
     "sections_to_ini_text", "build_dynamic_config",
)
# breeding_calculator
_reg("..breeding_calculator", "open_breeding_calculator")
# plugin_manager
_reg("..plugin_manager", "PluginManager")
# misc services
_reg("..discord_notifier", "DiscordNotifier")
_reg("..backup_manager", "BackupManager")
_reg("..mod_auto_updater", "ModAutoUpdater")
_reg("..updater", "UpdateChecker")
_reg("..dynamic_config_server", "DynamicConfigServer")
_reg("..sync_engine", "SyncEngine")
_reg("..config_manager", "ConfigManager")
_reg("..server_manager", "ServerManager")
_reg("..mod_manager", "ModManager", "ModConfig")
_reg("..remote_agent",
     "RemoteAgent", "RemoteClient",
     "make_identity_code", "parse_identity_code", "local_ip",
)
# battlemetrics
_reg("..battlemetrics_client", "BattlemetricsClient")


def _collect_used_names(source: str) -> set[str]:
    """Retorna todos os nomes simples referenciados no arquivo."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    return {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}


def _collect_imported_names(source: str) -> set[str]:
    """Retorna todos os nomes que já estão importados."""
    imported: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return imported
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported.add(alias.asname or alias.name)
    return imported


def _already_imports_from(source: str, module: str) -> set[str]:
    """Retorna os nomes já importados 'from <module> import ...'."""
    imported: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return imported
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module.lstrip("."):
            for alias in node.names:
                imported.add(alias.asname or alias.name)
    return imported


def _insert_import_line(source: str, module: str, names: list[str]) -> str:
    """Insere 'from <module> import <names>' logo após o último import top-level."""
    new_line = f"from {module} import {', '.join(sorted(names))}\n"

    lines = source.splitlines(keepends=True)

    # Encontra a última linha de import que NÃO está indentada (top-level)
    last_import_idx = -1
    for i, line in enumerate(lines):
        if line.startswith(" ") or line.startswith("\t"):
            continue  # ignora imports indentados (ex: dentro de if TYPE_CHECKING)
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            last_import_idx = i

    insert_at = last_import_idx + 1 if last_import_idx >= 0 else 0
    lines.insert(insert_at, new_line)
    return "".join(lines)


def fix_file(path: Path) -> bool:
    """Retorna True se o arquivo foi modificado."""
    source = path.read_text(encoding="utf-8")
    used = _collect_used_names(source)
    imported = _collect_imported_names(source)

    missing_by_module: dict[str, list[str]] = {}
    for name in used:
        if name in SYMBOL_MODULE and name not in imported:
            mod = SYMBOL_MODULE[name]
            missing_by_module.setdefault(mod, []).append(name)

    if not missing_by_module:
        return False

    modified = source
    for mod, names in missing_by_module.items():
        # Verifica se já existe um 'from <mod> import ...' e acrescenta a ele
        # Em vez de inserir um import duplicado, modifica o existente
        rel_mod = mod.lstrip(".")
        pattern = re.compile(
            r"^(from\s+" + re.escape(mod) + r"\s+import\s+)([^\n]+)$",
            re.MULTILINE,
        )
        m = pattern.search(modified)
        if m:
            existing_names = {n.strip() for n in m.group(2).split(",")}
            all_names = sorted(existing_names | set(names))
            if len(all_names) > 4:
                # formato multi-linha
                joined = ",\n    ".join(all_names)
                new_stmt = f"from {mod} import (\n    {joined},\n)"
            else:
                new_stmt = f"from {mod} import {', '.join(all_names)}"
            modified = pattern.sub(new_stmt, modified, count=1)
        else:
            modified = _insert_import_line(modified, mod, names)

    if modified != source:
        path.write_text(modified, encoding="utf-8")
        return True
    return False


def main() -> None:
    dirs = [ROOT / "src" / "pages", ROOT / "src" / "dialogs"]
    changed = 0
    total = 0
    for d in dirs:
        for py in sorted(d.glob("*.py")):
            total += 1
            if fix_file(py):
                changed += 1
                print(f"  ✔ {py.relative_to(ROOT)}")

    print(f"\nTotal: {changed}/{total} arquivos corrigidos.")


if __name__ == "__main__":
    main()
