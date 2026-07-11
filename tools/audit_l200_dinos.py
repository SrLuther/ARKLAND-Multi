import json

# Price mapping from TABELA_PRECOS_DINOS.md (R proposto)
PRICE_MAP = {
    'armaedron': 35000,
    'dread_wyvern': 33000,
    'ancient_wyvern': 32000,
    'indoraptor': 32000,
    'indominus': 28000,
    'sb_hydra': 24000,
    'bionicgigant': 22000,
    'bionicrex': 21000,
    'lionfish': 22000,
    'tekstrider': 26000,
    'sb_volcano_dragon': 26000,
    'sb_small_dragon': 25500,
    'sb_broodmother': 25000,
    'sb_fire_elemental': 25000,
    'sb_fire_elemental_tame': 25000,
    'carcha': 25000,
    'sb_crystal_queen': 25000,
    'sb_desert_titan': 25000,
    'sb_dodoreaper': 25000,
    'sb_dodorex': 25000,
    'sb_manticore': 24500,
    'sb_megapithecus': 24500,
    'sb_cyclops': 24000,
    'giga': 22500,
    'acro': 22000,
    'rex': 18000,
    'abyss_rex_abyssal': 16500,
    'abyss_reaper_abyssal': 16000,
    'xenomorphgen2': 16000,
    'xenomorph': 16000,
    'sb_drake_fire': 15500,
    'sb_crystal_blood': 15000,
    'sb_crystal_ember': 15000,
    'abyss_yuty_abyssal': 10000,
    'volcanorex': 9500,
    'deinonychus': 9500,
    'puretotokage': 9500,
    'shimosaur': 9500,
    'megalosaurus_aberrant': 9500,
    'megalosaurus': 9000,
    'astrodelphis': 7000,
    'desmodus': 7000,
    'abyss_water_wyvern': 6500,
    'sb_hippocampus': 6500,
    'sb_dodowyvern': 6000,
    'sb_moeder': 5000,
    'abyss_dakosaurus': 3500,
    'deinosuchus': 3500,
    'abyss_vulcanite': 3500,
    'sb_crystal_tropical': 3500,
    'xiphactinus': 3500,
    'abyss_riftcrawler': 3500,
    'abyss_thyla_abyssal': 3500,
    'concavenator': 3500,
    'cryolophosaurus': 3500,
    'kutsu_ya_ku': 3500,
    'brachio': 2500,
    'abyss_theriz_abyssal': 2500,
    'archelon': 2500,
    'diru_ya_ku': 1500,
    'abyss_mantis_shrimp': 1500,
    'abyss_onchopristis': 1200,
    'abyss_istiophorus': 1000,
    'abyss_stego_abyssal': 800,
    'abyss_stereolepis': 800,
    'abyss_tiktaalik': 800,
    'abyss_tridacna': 800,
    'abyss_thunnus': 700,
    'abyss_ankylo_abyssal': 700,
    'abyss_qarmoutus': 700,
    'abyss_ocepechelon': 700,
    'abyss_malleocephalus': 700,
    'abyss_kathreptis': 700,
    'abyss_homarus': 700,
    'abyss_takifugu': 700,
    'abyss_mudpuppy': 650,
    'abyss_seahorse': 650,
    'abyss_monodon': 600,
    'abyss_moschops_abyssal': 600,
}

for fpath in ['plugin/CustomShop/configs/config.json', 'plugin/CustomShop/bin/config.json']:
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    items = data.get('Items', {})
    l200_ids = []
    l1_ids = []
    
    for item_id, item in items.items():
        if item.get('Type', '').lower() == 'dino':
            dinos = item.get('Dinos', [])
            has_200 = any(d.get('Level') == 200 for d in dinos)
            has_1 = any(d.get('Level') == 1 for d in dinos)
            if has_200:
                l200_ids.append(item_id)
            if has_1:
                l1_ids.append(item_id)

    print(f'=== {fpath} ===')
    print(f'L200 dino items ({len(l200_ids)}):')
    for iid in sorted(l200_ids):
        item = items[iid]
        price = item.get('Price', 0)
        proposed = PRICE_MAP.get(iid, price)
        gender = item['Dinos'][0].get('Gender', 'none') if item.get('Dinos') else 'n/a'
        print(f'  {iid:45s} price={price:6d}  proposed={proposed:6d}  gender={gender}')
    
    print(f'\nL1 dino items ({len(l1_ids)}):')
    for iid in sorted(l1_ids)[:10]:
        print(f'  {iid}')
    if len(l1_ids) > 10:
        print(f'  ... and {len(l1_ids)-10} more')
    
    # Items in L200 but NOT in L1 (only L200 version exists)
    only_l200 = [iid for iid in l200_ids if iid not in l1_ids]
    print(f'\nItems with ONLY L200 (no L1 counterpart): {len(only_l200)}')
    for iid in only_l200:
        print(f'  {iid}')
    print()
