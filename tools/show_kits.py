import json

fpath = 'plugin/CustomShop/configs/config.json'
with open(fpath, 'r', encoding='utf-8') as f:
    data = json.load(f)

kits = data.get('Kits', {})
for kit_id in ['kit_alfa', 'kit_beta', 'kit_gamma']:
    kit = kits.get(kit_id, {})
    print(f'=== {kit_id} ===')
    print(json.dumps(kit, indent=2, ensure_ascii=False))
    print()
