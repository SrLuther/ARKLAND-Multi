"""Update TABELA_DINOS_COMPLETA.md and CATALOGO_DINOS_COMPLETO.md after L200 migration."""

# TABELA_DINOS_COMPLETA.md updates
with open('docs/TABELA_DINOS_COMPLETA.md', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Dread Wyvern price
content = content.replace(
    '| 148 | Dread Wyvern | `Wyvern_Character_BP_Dread` | \u2705 sim | `dread_wyvern` | 42.000 \u20b3 |',
    '| 148 | Dread Wyvern | `Wyvern_Character_BP_Dread` | \u2705 sim | `dread_wyvern` | 33.000 \u20b3 |'
)

# 2. Update Ancient Wyvern price
content = content.replace(
    '| 149 | Ancient Wyvern | `Wyvern_Character_BP_Ancient` | \u2705 sim | `ancient_wyvern` | 38.000 \u20b3 |',
    '| 149 | Ancient Wyvern | `Wyvern_Character_BP_Ancient` | \u2705 sim | `ancient_wyvern` | 32.000 \u20b3 |'
)

# 3. Update historical log - add new entry
old_hist = '| Jul 2026 | **91 BPs vanilla/DLC preenchidas via [arkids.net/creatures](https://arkids.net/creatures)**'
new_hist = (
    '| Jul 2026 | **Migracao somente L1:** 39 entradas L200 removidas (21 sufixo _200 + 18 com counterpart _femea), 40 convertidas in-place para L1 femea. Preco Dread Wyvern 42k->33k, Ancient Wyvern 38k->32k, Armaedron 35k (mantido). Kits alfa/beta/gamma: dinos L200->L1. |\n'
    '| Jul 2026 | **91 BPs vanilla/DLC preenchidas via [arkids.net/creatures](https://arkids.net/creatures)**'
)
content = content.replace(old_hist, new_hist)

with open('docs/TABELA_DINOS_COMPLETA.md', 'w', encoding='utf-8') as f:
    f.write(content)

print('TABELA_DINOS_COMPLETA.md atualizado OK')

# CATALOGO_DINOS_COMPLETO.md updates
with open('docs/CATALOGO_DINOS_COMPLETO.md', 'r', encoding='utf-8') as f:
    content2 = f.read()

# Update item count mention
content2 = content2.replace(
    'Entradas `Type:dino` em `config.json` | **118** (inclui variantes M/F e n\u00edvel 1 vs 200)',
    'Entradas `Type:dino` em `config.json` | **98** (somente L1 femea \u2014 migracao Jul/2026; entradas L200 removidas)'
)

with open('docs/CATALOGO_DINOS_COMPLETO.md', 'w', encoding='utf-8') as f:
    f.write(content2)

print('CATALOGO_DINOS_COMPLETO.md atualizado OK')
