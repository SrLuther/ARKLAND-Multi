import json

for fpath in ['plugin/CustomShop/configs/config.json', 'plugin/CustomShop/bin/config.json']:
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f'=== {fpath} ===')
    items = data.get('Items', {})
    print(f'Items type: {type(items)}')
    
    if isinstance(items, dict):
        print(f'Items keys (first 10): {list(items.keys())[:10]}')
        # Show a sample item
        first_key = list(items.keys())[0] if items else None
        if first_key:
            print(f'Sample item "{first_key}":')
            print(json.dumps(items[first_key], indent=2)[:600])
    elif isinstance(items, list):
        print(f'Items count: {len(items)}')
        if items:
            print(f'Sample item[0]:')
            print(json.dumps(items[0], indent=2)[:600])
    
    # Kits structure
    kits = data.get('Kits', {})
    print(f'\nKits type: {type(kits)}')
    if isinstance(kits, dict):
        print(f'Kits keys (first 5): {list(kits.keys())[:5]}')
        first_kit = list(kits.keys())[0] if kits else None
        if first_kit:
            print(f'Sample Kit "{first_kit}":')
            print(json.dumps(kits[first_kit], indent=2)[:600])
    print()
