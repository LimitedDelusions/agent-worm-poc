from __future__ import annotations
from pathlib import Path
import shutil,zipfile
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
                            ignore=shutil.ignore_patterns('__pycache__','*.pyc','.pytest_cache'))
    for name in ('pyproject.toml','Dockerfile','README.md','START_HERE.md','CODING_HANDOFF.md',
                 'DEPLOYMENT_CHECKLIST.md','VERSION','SOURCE_HASHES.sha256','RELEASE_MANIFEST.json',
                 'AUDIT_REPORT.md','FINAL_VALIDATION_REPORT.md'):
        if (project_root/name).exists():shutil.copy2(project_root/name,snapshot/name)
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
