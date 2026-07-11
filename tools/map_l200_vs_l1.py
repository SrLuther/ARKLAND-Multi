import json

fpath = 'plugin/CustomShop/configs/config.json'
with open(fpath, 'r', encoding='utf-8') as f:
    data = json.load(f)

items = data.get('Items', {})

# Classify all dino items
l200_items = {}  # id -> item
l1_items = {}    # id -> item

for item_id, item in items.items():
    if item.get('Type', '').lower() == 'dino':
        dinos = item.get('Dinos', [])
        levels = [d.get('Level', 0) for d in dinos]
        if 200 in levels:
            l200_items[item_id] = item
        elif 1 in levels:
            l1_items[item_id] = item

print('=== ALL L1 DINO ITEMS ===')
for iid, item in sorted(l1_items.items()):
    dinos = item.get('Dinos', [])
    gender = dinos[0].get('Gender', 'none') if dinos else 'none'
    blueprint = dinos[0].get('Blueprint', '').split('.')[-1] if dinos else 'n/a'
    print(f'  {iid:45s} | gender={gender:6s} | bp={blueprint} | price={item.get("Price", 0)}')

print(f'\nTotal L1: {len(l1_items)}')

print('\n=== ALL L200 DINO ITEMS (grouped: _200 suffix vs canonical) ===')
canonical_l200 = {k: v for k, v in l200_items.items() if not k.endswith('_200') and not k.endswith('_1')}
suffixed_l200 = {k: v for k, v in l200_items.items() if k.endswith('_200')}

print(f'Canonical IDs with L200 (need conversion or removal): {len(canonical_l200)}')
for iid in sorted(canonical_l200.keys()):
    item = canonical_l200[iid]
    dinos = item.get('Dinos', [])
    bp = dinos[0].get('Blueprint', '').split('.')[-1] if dinos else 'n/a'
    # Check if L1 counterpart exists
    # Possible L1 counterparts: iid + '_femea', iid + '_1', 'acrocanto_femea' for 'acro', etc.
    possible_l1 = [k for k in l1_items if iid in k or k.startswith(iid)]
    print(f'  {iid:40s} bp={bp}')
    if possible_l1:
        print(f'    -> Possible L1: {possible_l1}')
    else:
        print(f'    -> NO L1 COUNTERPART FOUND')

print(f'\nSuffixed _200 items (pure L200 variants, to REMOVE): {len(suffixed_l200)}')
for iid in sorted(suffixed_l200.keys()):
    print(f'  {iid}')
