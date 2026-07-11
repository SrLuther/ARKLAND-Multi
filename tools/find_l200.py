import json, re, sys

for fpath in ['plugin/CustomShop/configs/config.json', 'plugin/CustomShop/bin/config.json']:
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    l200_entries = []
    for cat_name, cat_data in data.get('Categories', {}).items():
        for item in cat_data.get('Items', []):
            if item.get('Type', '').lower() == 'dino':
                cmd = item.get('Command', '')
                # SpawnDino "BP" X Y Z LEVEL
                lvl_match = re.search(r'SpawnDino\s+\S+\s+[\d.\-]+\s+[\d.\-]+\s+[\d.\-]+\s+(\d+)', cmd)
                if lvl_match and lvl_match.group(1) == '200':
                    l200_entries.append({
                        'category': cat_name,
                        'id': item.get('Id', ''),
                        'title': item.get('Title', ''),
                        'price': item.get('Cost', {}).get('Points', 0),
                        'cmd': cmd[:150]
                    })

    print(f'=== {fpath} ===')
    print(f'Total L200 dino entries: {len(l200_entries)}')
    for e in l200_entries:
        cat = e['category']
        eid = e['id']
        title = e['title']
        price = e['price']
        cmd = e['cmd']
        print(f'  [{cat}] {eid} | {title} | {price} pts')
        print(f'    CMD: {cmd}')
    print()
