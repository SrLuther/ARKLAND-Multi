#!/usr/bin/env python3
"""Refresh the bundled ASE INI and command-line catalogs from the official wiki."""
from __future__ import annotations

import argparse
from datetime import date
from html import unescape
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from src.asm_engine.asm_game_list_ini import REPEATED_KEY_PREFIXES  # noqa: E402

SOURCE_URL = "https://ark.wiki.gg/wiki/Server_configuration?action=raw"
INI_OUT = ROOT / "src/data/ark_ase_server_ini_catalog.json"
CLI_OUT = ROOT / "src/data/ark_ase_server_cli_catalog.json"
_PARAM_RE = re.compile(r"^\|\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*(.*)$")


def fetch_wikitext(source_file: Path | None) -> str:
    if source_file:
        return source_file.read_text(encoding="utf-8")
    request = Request(SOURCE_URL, headers={"User-Agent": "ARKLAND-ServerManager config catalog"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def iter_templates(text: str):
    """Yield balanced Server config variable templates with source offsets."""
    pos = 0
    prefix = "{{Server config variable"
    while (start := text.find(prefix, pos)) >= 0:
        depth = 0
        cursor = start
        while cursor < len(text):
            if text.startswith("{{", cursor):
                depth += 1
                cursor += 2
            elif text.startswith("}}", cursor):
                depth -= 1
                cursor += 2
                if depth == 0:
                    break
            else:
                cursor += 1
        if depth:
            raise ValueError(f"Unclosed Server config variable template at offset {start}")
        yield start, cursor, text[start:cursor]
        pos = cursor


def parse_template(template: str) -> dict[str, str]:
    params: dict[str, str] = {}
    current: str | None = None
    positional: list[str] = []
    for line in template[len("{{Server config variable"):-2].splitlines():
        match = _PARAM_RE.match(line)
        if match:
            current = match.group(1)
            params[current] = match.group(2).strip()
        elif line.startswith("|"):
            positional.append(line[1:].strip())
        elif current and line.strip():
            params[current] += "\n" + line.strip()
    if positional:
        params["description"] = " ".join(positional)
    if params.get("info"):
        params["description"] = params["info"]
    return params


def clean_wiki_text(value: str) -> str:
    value = re.sub(r"(?is)<table\b.*?</table>", " ", value)
    value = re.sub(r"(?is)<ref\b.*?</ref>", " ", value)
    value = re.sub(r"(?is)<(code|nowiki)\b[^>]*>(.*?)</\1>", r"\2", value)
    value = re.sub(r"(?i)<br\s*/?>", " ", value)
    value = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", value)
    value = re.sub(r"\[\[([^\]]+)\]\]", r"\1", value)
    value = re.sub(r"\[(?:https?://\S+\s+)?([^\]]+)\]", r"\1", value)
    value = value.replace("{{=}}", "=")
    value = re.sub(r"\{\{[^{}]*\}\}", " ", value)
    value = re.sub(r"</?[A-Za-z][^>]*>", " ", value)
    value = value.replace("'''", "").replace("''", "")
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _section_at(text: str, end: int, default: str) -> str:
    marker = None
    for match in re.finditer(r"<!--start of \[?([^>]+?)\]?-->", text[:end]):
        marker = match.group(1).strip()
    return marker or default


def _record(params: dict[str, str], *, file_name: str, section: str) -> dict[str, str | bool]:
    name = params.get("name", "").strip()
    description = clean_wiki_text(params.get("description", ""))
    default = clean_wiki_text(params.get("default", ""))
    record: dict[str, str | bool] = {
        "file": file_name,
        "section": section,
        "key": name,
        "type": clean_wiki_text(params.get("type", "")),
        "default": default,
        "description": description,
        "since": clean_wiki_text(params.get("version", "")),
        "command_line": params.get("cli", "").strip().lower() == "yes",
    }
    if file_name == "Game.ini" and name.casefold() in {key.casefold() for key in REPEATED_KEY_PREFIXES}:
        record["repeatable"] = True
    return record


def _dedupe(records: list[dict]) -> list[dict]:
    by_key: dict[tuple[str, str, str], dict] = {}
    for record in records:
        key = (record["file"], record["section"], record["key"])
        by_key[key] = record
    return sorted(by_key.values(), key=lambda item: (item["file"], item["section"].casefold(), item["key"].casefold()))


def build_catalogs(wikitext: str, old_ini: dict) -> tuple[list[dict], list[dict]]:
    ini: list[dict] = []
    command_line: list[dict] = []
    command_start = wikitext.find("<!--start of command line-->")
    command_end = wikitext.find("<!--end of command line-->")
    gus_start = wikitext.find("<!--start of GameUserSettings.ini-->")
    gus_end = wikitext.find("<!--end of GameUserSettings.ini-->")
    game_start = wikitext.find("<!--start of Game.ini-->")
    game_end = wikitext.find("<!--end of Game.ini-->")
    ranges = {
        "CommandLine": (command_start, command_end),
        "GameUserSettings.ini": (gus_start, gus_end),
        "Game.ini": (game_start, game_end),
    }
    if any(start < 0 or end <= start for start, end in ranges.values()):
        raise ValueError("Expected command line, GameUserSettings.ini and Game.ini markers are missing")

    for file_name, (start, end) in ranges.items():
        text = wikitext[start:end]
        for offset, _end, template in iter_templates(text):
            params = parse_template(template)
            if params.get("inASE", "").split("\n", 1)[0].strip().casefold() != "yes":
                continue
            name = params.get("name", "").strip()
            if not name:
                continue
            if file_name == "CommandLine":
                section = "Startup Arguments"
                record = _record(params, file_name=file_name, section=section)
                record["argument"] = name
                record["key"] = name
                record["syntax"] = "question" if name.startswith("?") else "flag"
                record["value_required"] = "=" in name
                command_line.append(record)
                continue
            if file_name == "Game.ini":
                local_before = text[:offset]
                section = "/Script/ShooterGame.ShooterGameMode"
                if "====[ModInstaller]====" in local_before:
                    section = "ModInstaller"
            else:
                section = _section_at(text, offset, "ServerSettings")
                section = section.strip("[]")
            ini.append(_record(params, file_name=file_name, section=section))

    existing_structured = [
        item for item in old_ini.get("entries", [])
        if item.get("file") == "Game.ini" and item.get("repeatable")
        and not any(existing.get("file") == "Game.ini" and existing.get("key") == item.get("key") for existing in ini)
    ]
    ini.extend(existing_structured)
    return _dedupe(ini), _dedupe(command_line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-file", type=Path, help="Use a saved official wiki raw-text snapshot instead of the network")
    parser.add_argument("--check", action="store_true", help="Parse and report counts without writing catalog files")
    args = parser.parse_args()
    text = fetch_wikitext(args.source_file)
    old_ini = json.loads(INI_OUT.read_text(encoding="utf-8"))
    ini, cli = build_catalogs(text, old_ini)
    if not ini or not cli:
        raise SystemExit("Catalog generation returned no entries")
    missing = [item for item in ini + cli if not item.get("description")]
    if missing:
        raise SystemExit(f"Refusing to write: {len(missing)} ASE entries have no description")
    print(f"INI ASE entries: {len(ini)} (GUS={sum(i['file']=='GameUserSettings.ini' for i in ini)}, Game.ini={sum(i['file']=='Game.ini' for i in ini)})")
    print(f"CLI ASE entries: {len(cli)}")
    if args.check:
        return 0
    date_stamp = date.today().isoformat()
    ini_doc = {"source": "https://ark.wiki.gg/wiki/Server_configuration", "retrieved": date_stamp, "entries": ini}
    cli_doc = {"source": "https://ark.wiki.gg/wiki/Server_configuration", "retrieved": date_stamp, "entries": cli}
    INI_OUT.write_text(json.dumps(ini_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CLI_OUT.write_text(json.dumps(cli_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
