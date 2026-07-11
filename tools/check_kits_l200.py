import json

for fpath in ['plugin/CustomShop/configs/config.json', 'plugin/CustomShop/bin/config.json']:
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    kits = data.get('Kits', {})
    print(f'=== {fpath} - Kits with L200 dinos ===')
    l200_kits = []
    for kit_id, kit in kits.items():
        dinos = kit.get('Dinos', [])
        has_200 = any(d.get('Level') == 200 for d in dinos)
        if has_200:
            l200_kits.append(kit_id)
            print(f'  {kit_id} | {kit.get("Name", "")} | price={kit.get("Price", 0)}')
            for d in dinos[:3]:
                print(f'    Dino: Level={d.get("Level")} Gender={d.get("Gender", "none")} BP={d.get("Blueprint", "").split(".")[-1]}')
    
    if not l200_kits:
        print('  (none)')
    print()
