import json, re

for fpath in ['plugin/CustomShop/configs/config.json', 'plugin/CustomShop/bin/config.json']:
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Show all dino type entries - first 20 per file, show structure
    dino_count = 0
    sample = []
    all_ids = []
    for cat_name, cat_data in data.get('Categories', {}).items():
        for item in cat_data.get('Items', []):
            if item.get('Type', '').lower() == 'dino':
                dino_count += 1
                # Check all fields for "200" or level references
                item_str = json.dumps(item)
                has_200 = '200' in item_str
                level_val = None
                lm = re.search(r'"Level"\s*:\s*(\d+)', item_str)
                if lm:
                    level_val = lm.group(1)
                
                all_ids.append({
                    'cat': cat_name,
                    'id': item.get('Id', ''),
                    'title': item.get('Title', ''),
                    'price': item.get('Cost', {}).get('Points', 0),
                    'has_200': has_200,
                    'level': level_val
                })
                if len(sample) < 5:
                    sample.append(item)

    print(f'=== {fpath} ===')
    print(f'Total dino entries: {dino_count}')
    print(f'\nSample (first 5 dino items):')
    for s in sample:
        print(json.dumps(s, indent=2)[:500])
        print('---')
    
    print(f'\nDino IDs with "200" anywhere:')
    found_200 = [x for x in all_ids if x['has_200']]
    print(f'Count: {len(found_200)}')
    for x in found_200:
        print(f'  [{x["cat"]}] {x["id"]} | {x["title"]} | price={x["price"]} | level={x["level"]}')
    
    print(f'\nAll unique Level values in dino entries:')
    levels = set(x['level'] for x in all_ids if x['level'])
    print(levels)
    print()
