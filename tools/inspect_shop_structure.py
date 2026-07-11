import json

for fpath in ['plugin/CustomShop/configs/config.json', 'plugin/CustomShop/bin/config.json']:
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f'=== {fpath} ===')
    print(f'Top-level keys: {list(data.keys())}')
    
    cats = data.get('Categories', {})
    print(f'Categories count: {len(cats)}')
    print(f'Category names: {list(cats.keys())[:20]}')
    
    # Get unique Type values across all items
    types = set()
    total_items = 0
    for cat_name, cat_data in cats.items():
        items = cat_data.get('Items', [])
        total_items += len(items)
        for item in items:
            types.add(item.get('Type', 'NO_TYPE'))
    
    print(f'Total items: {total_items}')
    print(f'Unique Type values: {types}')
    
    # Show sample items from first category
    first_cat = list(cats.keys())[0] if cats else None
    if first_cat:
        print(f'\nSample from category "{first_cat}":')
        for item in cats[first_cat].get('Items', [])[:3]:
            print(json.dumps(item, indent=2)[:400])
            print('---')
    print()
