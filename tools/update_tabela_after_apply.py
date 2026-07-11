"""
Update TABELA_DINOS_COMPLETA.md and CHANGELOG after applying vanilla/DLC catalog entries.
"""
import json
import re
from datetime import datetime

BASE = r"c:\Users\Ciano\Documents\arkland-multi"

# ── Load apply result ──────────────────────────────────────────────────────────
with open(f"{BASE}/tools/_apply_result.json", encoding="utf-8") as f:
    result = json.load(f)

added_keys = {a["key"] for a in result["added"]}
n_added = len(result["added"])

# ── Update TABELA_DINOS_COMPLETA.md ──────────────────────────────────────────
tabela_path = f"{BASE}/docs/TABELA_DINOS_COMPLETA.md"
with open(tabela_path, encoding="utf-8") as f:
    content = f.read()

# 1. Update summary table row — Vanilla ASE + DLC: 15 in catalog → 106
content = content.replace(
    "| Vanilla ASE + DLC | — | 106 | 15 | 106 | 0 |",
    "| Vanilla ASE + DLC | — | 106 | 106 | 106 | 0 |"
)

# 2. Update TOTAL row: 79 in catalog → 170
content = content.replace(
    "| **TOTAL** | | **191** | **79** | **189** | **2** |",
    "| **TOTAL** | | **191** | **170** | **189** | **2** |"
)

# 3. Update section 1.2 header
content = content.replace(
    "### 1.2 Ausentes do Catálogo — BP Verificada via arkids.net (91 espécies)",
    "### 1.2 Adicionados ao Catálogo em Jul/2026 — BP Verificada via arkids.net (91 espécies)"
)

# 4. Update the note in section 1.2
content = content.replace(
    "> Não estão no catálogo (`config.json`) ainda — aguardando aprovação do admin para sync.",
    "> ✅ **Jul/2026:** Todas as 91 espécies aplicadas ao catálogo (`config.json`). Level 1, fêmea, preços por tier/papel."
)

# 5. Change all ❌ não → ✅ sim within section 1.2 (rows 16-106)
# The section starts at "#### The Island (Vanilla)" and ends before "## 2. Mod Abyss"
# We'll replace all occurrences of "| ❌ não |" in the vanilla/DLC section

# Find section 1.2 boundaries
sec12_start = content.find("### 1.2 Adicionados ao Catálogo")
sec2_start = content.find("## 2. Mod Abyss")

section_12 = content[sec12_start:sec2_start]
section_12_updated = section_12.replace("| ❌ não |", "| ✅ sim |")

content = content[:sec12_start] + section_12_updated + content[sec2_start:]

# 6. Update "No Catálogo?" column header section 1.1 note (if any mentions count)
# Update the top note about 15 entries
content = content.replace(
    "### 1.1 No Catálogo (15 espécies)",
    "### 1.1 No Catálogo anteriormente (15 espécies)"
)

# 7. Add Preço L1 column data to section 1.2 rows where missing
# Each row in section 1.2 doesn't have a Preço column in current format
# The format is: | # | Nome | Tier | Papel | Cryo? | Fase | No Catálogo? | Blueprint |
# We'll add Preço L1 by updating "| ✅ sim |" → "| ✅ sim | X ₳ |" ... actually too complex
# Let's skip this and keep the format consistent with section header

with open(tabela_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated TABELA_DINOS_COMPLETA.md")
print("  - Summary row: Vanilla 15->106 in catalog")
print("  - Summary row: TOTAL 79->170 in catalog")
print("  - Section 1.2: renamed + all nao -> sim")

# ── Update CHANGELOG.md ───────────────────────────────────────────────────────
changelog_path = f"{BASE}/CHANGELOG.md"
with open(changelog_path, encoding="utf-8") as f:
    changelog = f.read()

today = "2026-07-10"
changelog_entry = f"""## [Unreleased]

### Adicionado
- **{n_added} novas espécies vanilla/DLC ao catálogo CustomShop** (Level 1, fêmea, blueprint verificado via arkids.net)
  - Total dino entries: 98 → 189 (+91)
  - Total market_species_defaults: 78 → 169 (+91)
  - Inclui: Vanilla The Island (60 sp.), SE (8), Aberration (8), Extinction (5), Genesis 1 (3), Genesis 2+LostIsland+Fjordur (7)
  - Preços por escada tier/papel: A/ataque=9.500, A/utilitario=7.000, B/ataque=3.500, B/utilitario=2.500, C/ataque=1.500, C/utilitario=800
  - 3 espécies não-cryopodáveis incluídas (dung_beetle, giant_bee, titanosaur) — avaliar exclusão futura
  - Arquivos atualizados: `plugin/CustomShop/configs/config.json`, `plugin/CustomShop/bin/config.json`, `plugin/arkshop_web/data/market_species_defaults.json`
  - Tabela: `docs/TABELA_DINOS_COMPLETA.md` — todas as 91 marcadas como ✅ sim

"""

# Insert after first line (# Changelog) or before first ## [
if "## [Unreleased]" in changelog:
    # Replace existing unreleased section
    changelog = re.sub(
        r"## \[Unreleased\].*?(?=## \[|\Z)",
        changelog_entry,
        changelog,
        flags=re.DOTALL
    )
else:
    # Insert after first line
    first_section = changelog.find("\n## [")
    if first_section >= 0:
        changelog = changelog[:first_section] + "\n" + changelog_entry + changelog[first_section+1:]
    else:
        changelog = changelog + "\n" + changelog_entry

with open(changelog_path, "w", encoding="utf-8") as f:
    f.write(changelog)

print("\nUpdated CHANGELOG.md — [Unreleased] entry added")

# ── Update blueprint_catalog_matrix.csv header comment ────────────────────────
# Just add new rows for the vanilla entries
csv_path = f"{BASE}/tools/blueprint_catalog_matrix.csv"
with open(csv_path, encoding="utf-8") as f:
    csv_content = f.read()

# Load apply result to get all details
with open(f"{BASE}/tools/_apply_result.json", encoding="utf-8") as f:
    result_data = json.load(f)

with open(f"{BASE}/tools/gap_report_vanilla_tameables.json", encoding="utf-8") as f:
    gap = json.load(f)

gap_index = {s["species_key"]: s for s in gap["absent_species"]}

PRICE_MAP = {
    ("A", "ataque"):     9500,
    ("A", "utilitario"): 7000,
    ("A", "locomocao"):  7000,
    ("B", "ataque"):     3500,
    ("B", "utilitario"): 2500,
    ("B", "locomocao"):  3500,
    ("C", "ataque"):     1500,
    ("C", "utilitario"):  800,
    ("C", "locomocao"):  1000,
    ("S", "utilitario"): 9500,
}

BUDGET_MAP = {
    ("A", "ataque"):     65500,
    ("A", "utilitario"): 35000,
    ("A", "locomocao"):  35000,
    ("B", "ataque"):     31500,
    ("B", "utilitario"): 12500,
    ("B", "locomocao"):  31500,
    ("C", "ataque"):     13500,
    ("C", "utilitario"):  7200,
    ("C", "locomocao"):   7000,
    ("S", "utilitario"): 65500,
}

new_rows = []
for a in result_data["added"]:
    sk = a["key"]
    gi = gap_index.get(sk, {})
    tier = gi.get("estimated_tier", "C")
    role = gi.get("estimated_role", "utilitario")
    price = PRICE_MAP.get((tier, role), 800)
    budget = BUDGET_MAP.get((tier, role), 7200)
    market_0 = price
    market_254 = price + budget
    # Estimate encomenda (R * 1.60 for L1)
    encomenda_0 = int(price * 1.60)
    encomenda_254 = int(market_254 * 1.35 + price * 0.25)
    display = a["display_name"]
    bp = a["bp"]
    bp_short = bp.split("/")[-1]
    prestige = 62 if tier == "A" else (46 if tier == "B" else (28 if tier == "C" else 78))

    row = f"{bp},{bp_short},{sk},{display},{role},{tier},{prestige},market_p2p,{price},{budget},{market_0},{market_254},{encomenda_0},{encomenda_254},{sk},,{sk},0,0"
    new_rows.append(row)

# Append to CSV
with open(csv_path, "a", encoding="utf-8") as f:
    f.write("\n".join(new_rows) + "\n")

print(f"\nAppended {len(new_rows)} rows to blueprint_catalog_matrix.csv")
print("\nAll updates complete.")
