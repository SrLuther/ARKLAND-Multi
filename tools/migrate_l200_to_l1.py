"""
migrate_l200_to_l1.py
=====================
Converte/remove todas as entradas L200 do CustomShop para somente L1.

Regras:
  1) Items com sufixo _200 -> REMOVIDOS (L1 counterpart já existe)
  2) Canonical L200 items com _femea/_1 counterpart -> REMOVIDOS
  3) Canonical L200 items sem counterpart -> CONVERTIDOS in-place (Level 1, Gender female, preço atualizado)
  4) Kits (kit_alfa, kit_beta, kit_gamma) -> Level 200->1, Gender female

Aplica em ambos configs:
  - plugin/CustomShop/configs/config.json
  - plugin/CustomShop/bin/config.json

Atualiza catalog_id_migration.json com novos aliases.
"""

import json, re, copy

# -------------------------------------------------------
# Preços propostos (TABELA_PRECOS_DINOS.md - R proposto)
# -------------------------------------------------------
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

# Nomes legíveis para substituição de "Nível 200" → "Fêmea Nível 1" nas descrições
# (mapeamento de item_id → nome base limpo sem nível)
NAME_BASE_MAP = {
    'ancient_wyvern': 'Ancient Wyvern',
    'archelon': 'Archelon',
    'abyss_ankylo_abyssal': 'Anquilossauro Abissal',
    'abyss_dakosaurus': 'Dakosaurus',
    'abyss_homarus': 'Lagosta (Homarus)',
    'abyss_istiophorus': 'Marlim (Istiophorus)',
    'abyss_kathreptis': 'Kathreptis',
    'abyss_malleocephalus': 'Malleocephalus',
    'abyss_mantis_shrimp': 'Camarão-mantis',
    'abyss_monodon': 'Narval (Monodon)',
    'abyss_moschops_abyssal': 'Moschops Abissal',
    'abyss_mudpuppy': 'Mudpuppy',
    'abyss_ocepechelon': 'Ocepechelon',
    'abyss_onchopristis': 'Onchopristis',
    'abyss_qarmoutus': 'Qarmoutus',
    'abyss_reaper_abyssal': 'Reaper Abissal',
    'abyss_rex_abyssal': 'Rex Abissal',
    'abyss_riftcrawler': 'Rift Crawler',
    'abyss_seahorse': 'Cavalo-marinho',
    'abyss_stego_abyssal': 'Stegossauro Abissal',
    'abyss_stereolepis': 'Stereolepis',
    'abyss_takifugu': 'Baiacu (Takifugu)',
    'abyss_theriz_abyssal': 'Therizinosaur Abissal',
    'abyss_thunnus': 'Atum (Thunnus)',
    'abyss_thyla_abyssal': 'Thylacoleo Abissal',
    'abyss_tiktaalik': 'Tiktaalik',
    'abyss_tridacna': 'Tridacna',
    'abyss_vulcanite': 'Vulcanita',
    'abyss_water_wyvern': 'Wyvern Aquática',
    'abyss_yuty_abyssal': 'Yutyrannus Abissal',
    'brachio': 'Brachiosaurus',
    'concavenator': 'Concavenator',
    'cryolophosaurus': 'Cryolophosaurus',
    'deinosuchus': 'Deinosuchus',
    'diru_ya_ku': 'Diru-Ya-Ku',
    'dread_wyvern': 'Dread Wyvern',
    'kutsu_ya_ku': 'Kutsu-Ya-Ku',
    'puretotokage': 'Puretotokage',
    'shimosaur': 'Shimosaur',
    'xiphactinus': 'Xiphactinus',
}

# Canonical L200 items that ALREADY have a L1 counterpart -> REMOVE these
# (mapping: canonical_l200_id -> existing_l1_id)
REMOVE_L200_MAP = {
    'acro': 'acrocanto_femea',
    'armaedron': 'armaedron_femea',
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
}

# Canonical L200 items to CONVERT IN-PLACE (no L1 counterpart)
# These will have Level changed to 1, Gender added, Name/Description updated
CONVERT_IN_PLACE = [
    'ancient_wyvern',
    'archelon',
    'abyss_ankylo_abyssal',
    'abyss_dakosaurus',
    'abyss_homarus',
    'abyss_istiophorus',
    'abyss_kathreptis',
    'abyss_malleocephalus',
    'abyss_mantis_shrimp',
    'abyss_monodon',
    'abyss_moschops_abyssal',
    'abyss_mudpuppy',
    'abyss_ocepechelon',
    'abyss_onchopristis',
    'abyss_qarmoutus',
    'abyss_reaper_abyssal',
    'abyss_rex_abyssal',
    'abyss_riftcrawler',
    'abyss_seahorse',
    'abyss_stego_abyssal',
    'abyss_stereolepis',
    'abyss_takifugu',
    'abyss_theriz_abyssal',
    'abyss_thunnus',
    'abyss_thyla_abyssal',
    'abyss_tiktaalik',
    'abyss_tridacna',
    'abyss_vulcanite',
    'abyss_water_wyvern',
    'abyss_yuty_abyssal',
    'brachio',
    'concavenator',
    'cryolophosaurus',
    'deinosuchus',
    'diru_ya_ku',
    'dread_wyvern',
    'kutsu_ya_ku',
    'puretotokage',
    'shimosaur',
    'xiphactinus',
]


def clean_name(name):
    """Remove 'Nível 200' variant text from name."""
    name = re.sub(r'\s*N[ií]vel\s*200', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\(Aquática\)', '', name, flags=re.IGNORECASE)
    name = name.strip()
    return name


def make_l1_name(item_id, current_name):
    """Generate a clean L1 name for the item."""
    base = NAME_BASE_MAP.get(item_id)
    if base:
        return f'{base} Fêmea Nível 1'
    # Fall back to cleaning current name
    cleaned = clean_name(current_name)
    return f'{cleaned} Fêmea Nível 1'


def convert_item_to_l1(item_id, item):
    """Convert a L200 item to L1 in-place."""
    new_item = copy.deepcopy(item)
    
    # Update Dinos array
    for dino in new_item.get('Dinos', []):
        dino['Level'] = 1
        dino['Gender'] = 'female'
    
    # Update Name and Description
    new_name = make_l1_name(item_id, item.get('Name', ''))
    new_item['Name'] = new_name
    new_item['Description'] = new_name
    
    # Update Price
    if item_id in PRICE_MAP:
        new_item['Price'] = PRICE_MAP[item_id]
    
    return new_item


def update_kits_to_l1(kits):
    """Update kit_alfa, kit_beta, kit_gamma dinos from L200 to L1."""
    changed = 0
    for kit_id in ['kit_alfa', 'kit_beta', 'kit_gamma']:
        if kit_id not in kits:
            continue
        kit = kits[kit_id]
        for dino in kit.get('Dinos', []):
            if dino.get('Level') == 200:
                dino['Level'] = 1
                dino['Gender'] = 'female'
                changed += 1
    return changed


def process_config(fpath):
    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    items = data.get('Items', {})
    
    removed_200suffix = []
    removed_canonical = []
    converted = []
    
    new_items = {}
    for item_id, item in items.items():
        if item.get('Type', '').lower() != 'dino':
            new_items[item_id] = item
            continue
        
        dinos = item.get('Dinos', [])
        has_200 = any(d.get('Level') == 200 for d in dinos)
        
        if not has_200:
            new_items[item_id] = item
            continue
        
        # Check if it's a _200 suffix item -> REMOVE
        if item_id.endswith('_200'):
            removed_200suffix.append(item_id)
            continue  # skip (don't add to new_items)
        
        # Check if canonical L200 with L1 counterpart -> REMOVE
        if item_id in REMOVE_L200_MAP:
            removed_canonical.append((item_id, REMOVE_L200_MAP[item_id]))
            continue  # skip
        
        # Convert in-place to L1
        if item_id in CONVERT_IN_PLACE:
            new_items[item_id] = convert_item_to_l1(item_id, item)
            converted.append(item_id)
        else:
            # Unknown L200 item - keep but warn
            print(f'  WARNING: Unknown L200 item not in any list: {item_id}')
            new_items[item_id] = item
    
    # Update kits
    kits = data.get('Kits', {})
    kit_changes = update_kits_to_l1(kits)
    
    data['Items'] = new_items
    
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return {
        'removed_200suffix': removed_200suffix,
        'removed_canonical': removed_canonical,
        'converted': converted,
        'kit_dino_changes': kit_changes,
    }


def update_catalog_migration(removed_canonical):
    """Add aliases for removed canonical L200 items -> their L1 counterparts."""
    migration_path = 'tools/catalog_id_migration.json'
    with open(migration_path, 'r', encoding='utf-8') as f:
        migration = json.load(f)
    
    aliases = migration.get('aliases', {})
    new_aliases = {}
    
    for l200_id, l1_id in removed_canonical:
        # Add: old L200 canonical ID -> new L1 ID
        new_aliases[l200_id] = l1_id
        # Remove the reverse entry if it exists (l1_id -> l200_id was the old mapping)
        # Keep it for backwards compat but update direction
    
    aliases.update(new_aliases)
    migration['aliases'] = aliases
    
    with open(migration_path, 'w', encoding='utf-8') as f:
        json.dump(migration, f, ensure_ascii=False, indent=2)
    
    return new_aliases


if __name__ == '__main__':
    print('=== MIGRACAO L200 -> L1 ===\n')
    
    all_removed_canonical = []
    
    for fpath in [
        'plugin/CustomShop/configs/config.json',
        'plugin/CustomShop/bin/config.json',
    ]:
        print(f'Processando: {fpath}')
        result = process_config(fpath)
        
        print(f'  Removidos (_200 suffix): {len(result["removed_200suffix"])}')
        for iid in result['removed_200suffix']:
            print(f'    - {iid}')
        
        print(f'  Removidos (canonical com L1 counterpart): {len(result["removed_canonical"])}')
        for l200_id, l1_id in result['removed_canonical']:
            print(f'    - {l200_id} -> (L1: {l1_id})')
        
        print(f'  Convertidos in-place (L200 -> L1): {len(result["converted"])}')
        for iid in result['converted']:
            print(f'    ~ {iid} -> Level=1, Gender=female, Price={PRICE_MAP.get(iid, "mantido")}')
        
        print(f'  Kit dinos atualizados: {result["kit_dino_changes"]}')
        
        if not all_removed_canonical:
            all_removed_canonical = result['removed_canonical']
        
        total_removed = len(result['removed_200suffix']) + len(result['removed_canonical'])
        total_converted = len(result['converted'])
        print(f'  TOTAL REMOVIDOS: {total_removed}')
        print(f'  TOTAL CONVERTIDOS: {total_converted}')
        print()
    
    # Update catalog migration
    print('Atualizando catalog_id_migration.json...')
    new_aliases = update_catalog_migration(all_removed_canonical)
    print(f'  {len(new_aliases)} novos aliases adicionados:')
    for k, v in new_aliases.items():
        print(f'    {k} -> {v}')
    
    print('\n=== CONCLUÍDO ===')
    print(f'Armaedron: 35.000 (mantido - tier apex S+)')
    print(f'Dread Wyvern: 33.000 (convertido L1)')
    print(f'Ancient Wyvern: 32.000 (convertido L1)')
    print(f'Hierarquia: Armaedron(35k) > Dread(33k) > Ancient/IndoRaptor(32k) > Indominus(28k) > ...')

