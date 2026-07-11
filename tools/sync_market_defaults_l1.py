"""
sync_market_defaults_l1.py
===========================
Atualiza market_species_defaults.json:
1. catalog_item_id/catalog_item_ids: substitui IDs L200 removidos pelos L1 equivalentes
2. root_value: aplica precos propostos para especies convertidas
"""
import json

MARKET_DEFAULTS_PATH = 'plugin/arkshop_web/data/market_species_defaults.json'

# Mapeamento: id_removido -> id_l1_substituto
REMOVED_TO_L1 = {
    'armaedron': 'armaedron_femea',
    'acro': 'acrocanto_femea',
    'bionicgigant': 'bionicgigant_femea',
    'bionicrex': 'bionicrex_femea',
    'carcha': 'carcha_femea',
    'deinonychus': 'deinonychus_femea',
    'desmodus': 'desmodus_femea',
    'giga': 'giga_femea',
    'indominus': 'indominus_femea',
    'indoraptor': 'indoraptor_femea',
    'lionfish': 'lionfish_femea',
    'megalosaurus': 'megalosaurus_femea',
    'megalosaurus_aberrant': 'megalosaurus_aberrant_femea',
    'rex': 'rex_femea',
    'tekstrider': 'tekstrider_femea',
    'volcanorex': 'volcanorex_femea',
    'xenomorph': 'xenomorph_femea',
    'xenomorphgen2': 'xenomorphgen2_femea',
    # _200 suffix -> L1 (already have aliases, but market might reference them)
    'astrodelphis_200': 'astrodelphis_1',
    'sb_broodmother_200': 'sb_broodmother',
    'sb_crystal_blood_200': 'sb_crystal_blood',
    'sb_crystal_ember_200': 'sb_crystal_ember',
    'sb_crystal_queen_200': 'sb_crystal_queen',
    'sb_crystal_tropical_200': 'sb_crystal_tropical',
    'sb_cyclops_200': 'sb_cyclops',
    'sb_desert_titan_200': 'sb_desert_titan',
    'sb_dodoreaper_200': 'sb_dodoreaper',
    'sb_dodorex_200': 'sb_dodorex',
    'sb_dodowyvern_200': 'sb_dodowyvern',
    'sb_drake_fire_200': 'sb_drake_fire',
    'sb_fire_elemental_200': 'sb_fire_elemental',
    'sb_fire_elemental_tame_200': 'sb_fire_elemental_tame',
    'sb_hippocampus_200': 'sb_hippocampus',
    'sb_hydra_200': 'sb_hydra',
    'sb_manticore_200': 'sb_manticore',
    'sb_megapithecus_200': 'sb_megapithecus',
    'sb_moeder_200': 'sb_moeder',
    'sb_small_dragon_200': 'sb_small_dragon',
    'sb_volcano_dragon_200': 'sb_volcano_dragon',
}

# Precos propostos para especies convertidas in-place
PRICE_MAP = {
    'dread_wyvern': 33000,
    'ancient_wyvern': 32000,
    'abyss_rex_abyssal': 16500,
    'abyss_reaper_abyssal': 16000,
    'abyss_yuty_abyssal': 10000,
    'abyss_dakosaurus': 3500,
    'abyss_thyla_abyssal': 3500,
    'abyss_vulcanite': 3500,
    'abyss_riftcrawler': 3500,
    'abyss_theriz_abyssal': 2500,
    'archelon': 2500,
    'brachio': 2500,
    'abyss_mantis_shrimp': 1500,
    'abyss_onchopristis': 1200,
    'abyss_water_wyvern': 6500,
    'abyss_stego_abyssal': 800,
    'abyss_stereolepis': 800,
    'abyss_tiktaalik': 800,
    'abyss_tridacna': 800,
    'abyss_ankylo_abyssal': 700,
    'abyss_qarmoutus': 700,
    'abyss_ocepechelon': 700,
    'abyss_malleocephalus': 700,
    'abyss_kathreptis': 700,
    'abyss_homarus': 700,
    'abyss_takifugu': 700,
    'abyss_thunnus': 700,
    'abyss_mudpuppy': 650,
    'abyss_seahorse': 650,
    'abyss_monodon': 600,
    'abyss_moschops_abyssal': 600,
    'abyss_istiophorus': 1000,
    'shimosaur': 9500,
    'puretotokage': 9500,
    'concavenator': 3500,
    'cryolophosaurus': 3500,
    'deinosuchus': 3500,
    'kutsu_ya_ku': 3500,
    'xiphactinus': 3500,
    'diru_ya_ku': 1500,
}

with open(MARKET_DEFAULTS_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

species_list = data.get('species', [])
changed = []

for sp in species_list:
    species_key = sp.get('species_key', '')
    modified = False
    
    # Update catalog_item_id if it points to a removed item
    cid = sp.get('catalog_item_id', '')
    if cid in REMOVED_TO_L1:
        new_cid = REMOVED_TO_L1[cid]
        print(f'  [{species_key}] catalog_item_id: {cid} -> {new_cid}')
        sp['catalog_item_id'] = new_cid
        modified = True
    
    # Update reference_catalog_item_id
    rcid = sp.get('reference_catalog_item_id', '')
    if rcid in REMOVED_TO_L1:
        new_rcid = REMOVED_TO_L1[rcid]
        sp['reference_catalog_item_id'] = new_rcid
        modified = True
    
    # Update catalog_item_ids list
    new_ids = []
    for iid in sp.get('catalog_item_ids', []):
        if iid in REMOVED_TO_L1:
            new_id = REMOVED_TO_L1[iid]
            if new_id not in new_ids:
                new_ids.append(new_id)
            modified = True
        else:
            if iid not in new_ids:
                new_ids.append(iid)
    if modified:
        sp['catalog_item_ids'] = new_ids
    
    # Update root_value for converted species
    if species_key in PRICE_MAP:
        old_rv = sp.get('root_value', 0)
        new_rv = PRICE_MAP[species_key]
        if old_rv != new_rv:
            print(f'  [{species_key}] root_value: {old_rv} -> {new_rv}')
            sp['root_value'] = new_rv
            # Recalculate premium_budget = market_absolute_max - root_value
            # market_absolute_max = 150000 for S+, 130000 for lionfish, etc.
            # Just note the change; keep existing budget or recalculate
            modified = True
    
    if modified:
        changed.append(species_key)

print(f'\nTotal de especies atualizadas no market_species_defaults: {len(changed)}')
print('Species alteradas:', changed)

with open(MARKET_DEFAULTS_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('market_species_defaults.json atualizado com sucesso.')
