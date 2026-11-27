"""Export observational owner facts from stable copied ASE tribe/profile files."""
from __future__ import annotations
import argparse
import hashlib
import json
import ntpath
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

PARSER_COMMIT='1d9a3e2b1a8052fdfc187174edfc920ca53216f3'


def u32(value):
    if type(value) is not int or not -2147483648 <= value <= 4294967294:
        raise ValueError('Invalid owner ID')
    result=value & 0xffffffff
    if result in (0,0xffffffff):raise ValueError('Missing owner ID')
    return result


def build_directory(manifest, tribes, profiles):
    root=ntpath.normcase(ntpath.normpath(manifest['canonical_instance_path']))
    sources={};folder=None
    for source in manifest['files']:
        name=source['name'];path=ntpath.normcase(ntpath.normpath(source['source']))
        parent=ntpath.dirname(path)
        if not re.fullmatch(r'[0-9]{1,20}\.(?:arktribe|arkprofile)',name) or ntpath.basename(path)!=name:
            raise ValueError('Invalid source name')
        expected=ntpath.join(root,'shootergame','saved',ntpath.basename(parent))
        if parent!=expected or not re.fullmatch(r'[a-z0-9_-]{1,64}',ntpath.basename(parent)):
            raise ValueError('Source is outside the instance save directory')
        if folder is not None and folder!=ntpath.basename(parent):raise ValueError('Mixed save directories')
        folder=ntpath.basename(parent)
        if name in sources:raise ValueError('Duplicate source')
        sources[name]={'name':name,'sha256':str(source['sha256']).lower(),'bytes':source['bytes']}
        if not re.fullmatch(r'[0-9a-f]{64}',sources[name]['sha256']) or type(source['bytes']) is not int or not 0<source['bytes']<=8*1024*1024:
            raise ValueError('Invalid source fingerprint')
    if not folder:raise ValueError('No copied ownership sources')
    tribe_rows=[];solo_rows=[];known=set();members=set();used=set();player_ids=set()
    for tribe in tribes:
        id=u32(tribe['tribe_id']);name=tribe['source']
        if id in known or name!=f'{id}.arktribe' or name not in sources:raise ValueError('Conflicting tribe proof')
        known.add(id);members.update(u32(member) for member in tribe.get('member_ids',[]))
        used.add(name);tribe_rows.append({'tribe_id':id,'source':name})
    for profile in profiles:
        id=u32(profile['player_id'])
        if id in player_ids:raise ValueError('Ambiguous player data ID')
        player_ids.add(id)
        # Do not use parser.tribe_id: it invents an auto-tribe for solo players.
        if type(profile.get('raw_tribe_id')) is not int or profile['raw_tribe_id']!=0:continue
        steam=profile.get('steam_id','');name=profile['source']
        if not re.fullmatch(r'7656119[0-9]{10}',steam) or name!=steam+'.arkprofile' or name not in sources:
            raise ValueError('Solo profile identity is not proven')
        if id in known or id in members:raise ValueError('Contradictory solo membership')
        used.add(name);solo_rows.append({'player_data_id':id,'steam_id':steam,'raw_tribe_id':0,'source':name})
    selected=[sources[name] for name in sorted(used)]
    if len(selected)>1024 or sum(s['bytes'] for s in selected)>64*1024*1024:raise ValueError('Ownership source budget exceeded')
    return {'format':'arkland-owner-directory-v1','instance':manifest['instance'],
        'canonical_instance_path':root,'saved_directory':folder,'parser_commit':PARSER_COMMIT,
        'created_at_utc':datetime.now(timezone.utc).isoformat(),'enforcement_authority':False,
        'sources':selected,'tribes':sorted(tribe_rows,key=lambda r:r['tribe_id']),
        'solos':sorted(solo_rows,key=lambda r:r['player_data_id'])}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--parser-root',type=Path,required=True)
    parser.add_argument('--expected-instance',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=args.checkpoint.resolve()
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8-sig'))
    if manifest.get('format')!='arkland-owner-sources-v1' or manifest.get('instance')!=args.expected_instance or manifest.get('enforcement_authority') is not False:
        raise ValueError('Wrong checkpoint scope')
    revision=subprocess.run(['git','-C',str(args.parser_root),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
    if revision!=PARSER_COMMIT or subprocess.run(['git','-C',str(args.parser_root),'diff','--quiet','HEAD','--','arkparser']).returncode:
        raise ValueError('Parser is not the reviewed clean revision')
    sys.path.insert(0,str(args.parser_root.resolve()))
    from arkparser import Tribe,Profile
    tribes=[];profiles=[];paths=[]
    for source in manifest['files']:
        name=source['name']
        if Path(name).name!=name or '/' in name or '\\' in name:raise ValueError('Unsafe input path')
        path=root/name
        if ntpath.normcase(str(path))==ntpath.normcase(ntpath.normpath(source['source'])):
            raise ValueError('Refusing to parse a live ownership file')
        data=path.read_bytes()
        if len(data)!=source['bytes'] or hashlib.sha256(data).hexdigest()!=source['sha256'].lower():raise ValueError('Copied source changed')
        obj=Tribe.load(path) if name.endswith('.arktribe') else Profile.load(path)
        if obj.is_asa or getattr(obj,'parse_errors',[]):raise ValueError('Unsupported or partially parsed ownership file')
        if name.endswith('.arktribe'):
            tribes.append({'tribe_id':obj.tribe_id,'member_ids':obj.member_ids,'source':name})
        else:
            profiles.append({'player_id':obj.player_id,'raw_tribe_id':obj.raw_tribe_id,'steam_id':obj.unique_id,'source':name})
        paths.append((path,source))
    result=build_directory(manifest,tribes,profiles)
    for path,source in paths:
        if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256'].lower():raise ValueError('Copied source changed while parsing')
    output=args.output.resolve()
    if output in {root/'manifest.json',root/'observed-inventory.json',*(p for p,_ in paths)}:raise ValueError('Output would replace checkpoint evidence')
    with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=output.parent,delete=False) as handle:
        json.dump(result,handle,ensure_ascii=False,indent=2);handle.write('\n');temporary=handle.name
    os.replace(temporary,output)
    print(json.dumps({'instance':result['instance'],'tribes':len(result['tribes']),'solos':len(result['solos']),
        'verified_sources':len(result['sources']),'enforcement_authority':False}))


if __name__=='__main__':main()
