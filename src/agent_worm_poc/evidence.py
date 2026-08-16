from __future__ import annotations
from pathlib import Path
import json,shutil,zipfile
from .util import sha256_file,write_json,utc_stamp


def build_manifest(root:Path,exclude_names:set[str]|None=None)->dict:
    exclude_names=exclude_names or set();files=[]
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.name not in exclude_names:
            files.append({'path':str(path.relative_to(root)),'size':path.stat().st_size,'sha256':sha256_file(path)})
    return {'created_utc':utc_stamp(),'file_count':len(files),'files':files}


def package_results(project_root:Path,run_dir:Path,output_path:Path)->dict:
    package_root=run_dir/'evidence_package'
    if package_root.exists():shutil.rmtree(package_root)
    package_root.mkdir(parents=True)
    shutil.copytree(run_dir,package_root/'run',dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('evidence_package','*.zip','*.pyc','__pycache__'))
    snapshot=package_root/'source_snapshot';snapshot.mkdir(parents=True,exist_ok=True)
    for name in ('configs','data','src','scripts','docs','.github'):
        if (project_root/name).exists():
            shutil.copytree(project_root/name,snapshot/name,dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('__pycache__','*.pyc','.pytest_cache','*.egg-info'))
    for name in ('pyproject.toml','Dockerfile','README.md','START_HERE.md','CODING_HANDOFF.md',
                 'DEPLOYMENT_CHECKLIST.md','VERSION','SOURCE_HASHES.sha256','RELEASE_MANIFEST.json',
                 'AUDIT_REPORT.md','FINAL_VALIDATION_REPORT.md'):
        if (project_root/name).exists():shutil.copy2(project_root/name,snapshot/name)
    # Supplement the human-readable snapshot layout with every integrity-manifested
    # release file, including tests and top-level dotfiles.
    release_manifest_path=project_root/'RELEASE_MANIFEST.json'
    if release_manifest_path.exists():
        release_manifest=json.loads(release_manifest_path.read_text(encoding='utf-8'))
        project_resolved=project_root.resolve()
        for row in release_manifest.get('files',[]):
            relative=Path(str(row['path']))
            if relative.is_absolute() or '..' in relative.parts:
                raise RuntimeError(f'Unsafe release-manifest path: {relative}')
            source=project_root/relative
            resolved=source.resolve(strict=True)
            if not resolved.is_relative_to(project_resolved) or source.is_symlink() or not source.is_file():
                raise RuntimeError(f'Invalid release-manifest source file: {relative}')
            if source.stat().st_size!=int(row['size']) or sha256_file(source)!=row['sha256']:
                raise RuntimeError(f'Release-manifest mismatch while packaging: {relative}')
            destination=snapshot/relative
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,destination)
    manifest=build_manifest(package_root);write_json(package_root/'PACKAGE_MANIFEST.json',manifest)
    output_path.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output_path,'w',zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
        for path in sorted(package_root.rglob('*')):
            if path.is_file():archive.write(path,path.relative_to(package_root.parent))
    with zipfile.ZipFile(output_path) as archive:
        bad=archive.testzip()
        if bad:raise RuntimeError(f'Created evidence ZIP failed integrity test at {bad}')
    result={'zip':str(output_path),'sha256':sha256_file(output_path),'size':output_path.stat().st_size,
            'manifest_files':manifest['file_count']}
    write_json(output_path.with_suffix(output_path.suffix+'.json'),result)
    output_path.with_suffix(output_path.suffix+'.sha256').write_text(result['sha256']+'  '+output_path.name+'\n',encoding='utf-8')
    return result
