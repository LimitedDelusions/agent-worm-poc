#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import argparse,hashlib,json,sys

ROOT=Path(__file__).resolve().parents[2]
EXCLUDED_DIRS={'.git','.venv','__pycache__','.pytest_cache','.ruff_cache','outputs','dist','build','*.egg-info'}
EXCLUDED_FILES={'SOURCE_HASHES.sha256','RELEASE_MANIFEST.json'}


def excluded(path:Path)->bool:
    rel=path.relative_to(ROOT)
    for part in rel.parts:
        if part in {'.git','.venv','__pycache__','.pytest_cache','.ruff_cache','outputs','dist','build'} or part.endswith('.egg-info'):
            return True
    return path.name in EXCLUDED_FILES or path.suffix in {'.pyc','.zip'}


def sha(path:Path)->str:
    value=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):value.update(chunk)
    return value.hexdigest()


def rows():
    return [{'path':str(path.relative_to(ROOT)).replace('\\','/'),'size':path.stat().st_size,'sha256':sha(path)}
            for path in sorted(ROOT.rglob('*')) if path.is_file() and not excluded(path)]


def write():
    values=rows()
    with (ROOT/'SOURCE_HASHES.sha256').open('w',encoding='utf-8',newline='\n') as handle:
        handle.write(''.join(f"{row['sha256']}  {row['path']}\n" for row in values))
    manifest={'schema_version':1,'release':(ROOT/'VERSION').read_text().strip(),'file_count':len(values),'files':values}
    with (ROOT/'RELEASE_MANIFEST.json').open('w',encoding='utf-8',newline='\n') as handle:
        handle.write(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'written':True,'file_count':len(values)},indent=2))


def check()->int:
    manifest_path=ROOT/'RELEASE_MANIFEST.json'
    if not manifest_path.exists():print('RELEASE_MANIFEST.json missing',file=sys.stderr);return 1
    expected=json.loads(manifest_path.read_text(encoding='utf-8'))
    current=rows();expected_map={row['path']:row for row in expected['files']};current_map={row['path']:row for row in current}
    errors=[]
    for name in sorted(set(expected_map)-set(current_map)):errors.append(f'missing: {name}')
    for name in sorted(set(current_map)-set(expected_map)):errors.append(f'unexpected: {name}')
    for name in sorted(set(expected_map)&set(current_map)):
        if expected_map[name]['sha256']!=current_map[name]['sha256']:errors.append(f'hash mismatch: {name}')
        if int(expected_map[name]['size'])!=int(current_map[name]['size']):errors.append(f'size mismatch: {name}')
    hash_file=ROOT/'SOURCE_HASHES.sha256'
    if not hash_file.exists():errors.append('SOURCE_HASHES.sha256 missing')
    else:
        lines={line.split('  ',1)[1]:line.split('  ',1)[0] for line in hash_file.read_text().splitlines() if '  ' in line}
        if lines!={name:row['sha256'] for name,row in expected_map.items()}:errors.append('SOURCE_HASHES.sha256 does not match RELEASE_MANIFEST.json')
    result={'passed':not errors,'file_count':len(current),'errors':errors}
    print(json.dumps(result,indent=2));return 0 if not errors else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    raise SystemExit(check() if args.check else (write() or 0))
