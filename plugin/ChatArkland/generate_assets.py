"""Gera o contrato compilado e as migrações; nunca lê credenciais reais."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugin" / "arkshop_web"))
from chat_arkland_config import DEFAULTS, validate_config
from chat_arkland_service import META
from chat_arkland_emojis import EMOJIS
from sqlalchemy.dialects import mysql, sqlite
from sqlalchemy.schema import CreateTable, CreateIndex

base = Path(__file__).resolve().parent
defaults = validate_config(DEFAULTS)
encoded = json.dumps(defaults, ensure_ascii=False, separators=(",", ":"))
(base / "src" / "ChatDefaults.h").write_text(
    '#pragma once\nnamespace ChatArkland { inline constexpr char kDefaultShared[] = R"CA_JSON('
    + encoded + ')CA_JSON"; }\n', encoding="utf-8", newline="\n")
(base / "src" / "ChatEmojis.h").write_text(
    '#pragma once\nnamespace ChatArkland { inline constexpr char kChatEmojis[] = R"CA_EMO_JSON('
    + json.dumps(EMOJIS, ensure_ascii=False, separators=(",", ":")) + ')CA_EMO_JSON"; }\n', encoding="utf-8", newline="\n")
example = {"Local": {"ServerKey": "", "ApiUrl": "https://arkland.com.br", "ApiKey": "", "ObserveOnly": True},
           "Shared": {"revision": 0, "config": defaults}, "Runtime": {"Cursor": 0, "Resume": False, "Players": {}, "Seen": []}}
(base / "configs" / "config.json").write_text(json.dumps(example, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
if "--contract-only" in sys.argv:
    print("Contrato C++, emojis e exemplo sem credenciais gerados; migrações preservadas.")
    raise SystemExit(0)
for name, dialect in (("mysql", mysql.dialect()), ("sqlite", sqlite.dialect())):
    statements = ["-- Chat Arkland: versão de esquema 1. Sem alterações em tabelas de outros sistemas."]
    for table in META.sorted_tables:
        statements.append(str(CreateTable(table, if_not_exists=True).compile(dialect=dialect)).strip() + ";")
        statements.extend(str(CreateIndex(index).compile(dialect=dialect)) + ";" for index in table.indexes)
    sql = "\n\n".join(statements)
    (base / "migrations" / f"001_up_{name}.sql").write_text("\n".join(line.rstrip() for line in sql.splitlines()) + "\n", encoding="utf-8", newline="\n")
down = ["-- REQUER BACKUP. Reverter o esquema remove mensagens, revisões e entregas pendentes.",
        "-- Não executar em produção sem exportar/restaurar chat_arkland_players. Nunca recrie IDs do zero sobre um cluster ativo."]
down.append("-- O registro de IDs é preservado também no downgrade, evitando reutilização indevida.")
down.extend(f"DROP TABLE IF EXISTS {table.name};" for table in reversed(META.sorted_tables) if table.name != "chat_arkland_players")
(base / "migrations" / "001_down.sql").write_text("\n".join(down) + "\n", encoding="utf-8", newline="\n")
print("Contrato C++, exemplo sem credenciais e migrações gerados.")
