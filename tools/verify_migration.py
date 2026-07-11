import json

fpath = 'plugin/CustomShop/configs/config.json'
with open(fpath, 'r', encoding='utf-8') as f:
    data = json.load(f)

items = data.get('Items', {})

print('=== VERIFICACAO POS-MIGRACAO ===\n')

# Check key converted items
key_items = ['dread_wyvern', 'ancient_wyvern', 'abyss_ankylo_abyssal', 'abyss_yuty_abyssal']
print('Items convertidos (verificacao):')
for iid in key_items:
    if iid in items:
        item = items[iid]
        dinos = item.get('Dinos', [])
        d = dinos[0] if dinos else {}
        print(f'  {iid}: Name={item.get("Name")} Level={d.get("Level")} Gender={d.get("Gender")} Price={item.get("Price")}')
    else:
        print(f'  {iid}: NOT FOUND')

# Check that removed items are gone
removed_check = ['armaedron', 'acro', 'bionicgigant', 'sb_broodmother_200', 'astrodelphis_200', 'sb_hydra_200']
print('\nItems removidos (devem estar ausentes):')
for iid in removed_check:
    present = iid in items
    status = 'PRESENTE (ERRO!)' if present else 'ausente (OK)'
    print(f'  {iid}: {status}')

# Check L1 counterparts still present
l1_check = ['armaedron_femea', 'acrocanto_femea', 'bionicgigant_femea', 'sb_broodmother', 'sb_hydra']
print('\nItems L1 ainda presentes:')
for iid in l1_check:
    if iid in items:
        item = items[iid]
        dinos = item.get('Dinos', [])
        d = dinos[0] if dinos else {}
        print(f'  {iid}: Level={d.get("Level")} Gender={d.get("Gender")} Price={item.get("Price")}')
    else:
        print(f'  {iid}: NOT FOUND (erro!)')

# Count all dino items by level
l1_count = 0
l200_count = 0
other_count = 0
for item in items.values():
    if item.get('Type', '').lower() == 'dino':
        dinos = item.get('Dinos', [])
        levels = [d.get('Level') for d in dinos]
        if 200 in levels:
            l200_count += 1
        elif 1 in levels:
            l1_count += 1
        else:
            other_count += 1

print(f'\nContagem final:')
print(f'  L1 dino items: {l1_count}')
print(f'  L200 dino items: {l200_count} (deve ser 0)')
print(f'  Outros niveis: {other_count}')

# Check kits
kits = data.get('Kits', {})
print('\nKits - dinos L200 restantes:')
for kit_id in ['kit_alfa', 'kit_beta', 'kit_gamma']:
    kit = kits.get(kit_id, {})
    l200_dinos = [d for d in kit.get('Dinos', []) if d.get('Level') == 200]
    l1_dinos = [d for d in kit.get('Dinos', []) if d.get('Level') == 1]
    print(f'  {kit_id}: L200={len(l200_dinos)} (deve ser 0), L1={len(l1_dinos)}')
