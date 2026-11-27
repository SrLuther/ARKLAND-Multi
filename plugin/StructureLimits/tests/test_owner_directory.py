import copy
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from owner_directory import build_directory,u32

STEAM='76561198000000001'


def manifest():
    return {'instance':'09THE05','canonical_instance_path':'E:\\Mapas\\05','files':[
        {'name':'123.arktribe','source':'E:\\Mapas\\05\\ShooterGame\\Saved\\savegame\\123.arktribe','sha256':'a'*64,'bytes':100},
        {'name':STEAM+'.arkprofile','source':'E:\\Mapas\\05\\ShooterGame\\Saved\\savegame\\'+STEAM+'.arkprofile','sha256':'b'*64,'bytes':200}]}


def test_verified_tribe_and_explicit_solo_export_only_used_sources():
    result=build_directory(manifest(),[{'tribe_id':123,'source':'123.arktribe','member_ids':[10]}],
        [{'player_id':456,'raw_tribe_id':0,'steam_id':STEAM,'source':STEAM+'.arkprofile'}])
    assert result['tribes']==[{'tribe_id':123,'source':'123.arktribe'}]
    assert result['solos'][0]['player_data_id']==456
    assert result['enforcement_authority'] is False and len(result['sources'])==2


@pytest.mark.parametrize('raw', [None,False,123])
def test_missing_or_non_solo_membership_never_uses_auto_tribe_fallback(raw):
    result=build_directory(manifest(),[{'tribe_id':123,'source':'123.arktribe'}],
        [{'player_id':456,'raw_tribe_id':raw,'steam_id':STEAM,'source':STEAM+'.arkprofile'}])
    assert not result['solos'] and len(result['sources'])==1


@pytest.mark.parametrize('case', ['other_map','traversal','hash','duplicate','mismatched_tribe'])
def test_bad_checkpoint_is_not_accepted(case):
    value=manifest();tribes=[{'tribe_id':123,'source':'123.arktribe'}]
    if case=='other_map':value['files'][0]['source']=value['files'][0]['source'].replace('Mapas\\05','Mapas\\04')
    if case=='traversal':value['files'][0]['name']='../123.arktribe'
    if case=='hash':value['files'][0]['sha256']='bad'
    if case=='duplicate':value['files'].append(copy.deepcopy(value['files'][0]))
    if case=='mismatched_tribe':tribes[0]['tribe_id']=124
    with pytest.raises(ValueError):build_directory(value,tribes,[])


def test_membership_conflict_is_not_guessed():
    with pytest.raises(ValueError):
        build_directory(manifest(),[{'tribe_id':123,'source':'123.arktribe','member_ids':[456]}],
            [{'player_id':456,'raw_tribe_id':0,'steam_id':STEAM,'source':STEAM+'.arkprofile'}])


def test_unsigned_ids_are_preserved_and_sentinels_rejected():
    assert u32(-2147483648)==2147483648
    for id in [0,-1,True,2**32]:
        with pytest.raises(ValueError):u32(id)
