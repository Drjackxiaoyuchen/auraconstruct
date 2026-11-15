"""Discover and check an isolated pLannotate 2 installation without changing user Python."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from .library import data_dir


def executable():
    explicit=os.environ.get('AURACONSTRUCT_PLANNOTATE')
    if explicit:return shutil.which(explicit)
    managed=data_dir()/'plannotate-env/bin/plannotate'
    return str(managed) if managed.is_file() else shutil.which('plannotate')


def environment(exe):
    env=os.environ.copy()
    env['PATH']=str(Path(exe).parent)+os.pathsep+env.get('PATH','')
    env['PYTHONNOUSERSITE']='1'
    env.pop('PYTHONPATH',None);env.pop('PYTHONHOME',None)
    return env


def _database_files(manifest,root):
    """Validate the manifest and keep all index reads inside the reported bundle."""
    entries=manifest.get('files')
    if not isinstance(entries,dict) or not entries:
        raise ValueError('Database manifest is missing file checksums.')
    if not root or not Path(root).is_absolute() or not Path(root).is_dir():
        raise ValueError('pLannotate did not report an available absolute database directory.')
    root=Path(root).resolve();files=[]
    for name,metadata in entries.items():
        if not isinstance(name,str) or not name or Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('Database manifest contains an unsafe file path.')
        path=(root/name).resolve()
        if not path.is_relative_to(root):raise ValueError('Database file resolves outside its bundle.')
        expected=metadata.get('sha256') if isinstance(metadata,dict) else None
        if not isinstance(expected,str) or not re.fullmatch(r'[0-9a-fA-F]{64}',expected):
            raise ValueError(f'Database manifest has no valid SHA-256 for {name}.')
        if not path.is_file():raise ValueError(f'Database bundle is incomplete: {name}')
        files.append((name,path,expected.lower()))
    return files


def status(verify_databases=False):
    exe=executable()
    result={'installed':bool(exe),'ready':False,'version':None,'database_version':None,
            'database_fingerprint':None,'database_integrity':'unchecked','database_files_checked':0,
            'database_bytes_checked':0,'reason':'pLannotate is not installed. See docs/ANNOTATION.md.'}
    if not exe:return result
    env=environment(exe)
    missing=[t for t in ('blastn','diamond','cmscan') if not shutil.which(t,path=env['PATH'])]
    if missing:
        result['reason']='Missing pLannotate search tools: '+', '.join(missing);return result
    try:
        version=subprocess.run([exe,'--version'],env=env,capture_output=True,text=True,timeout=20,check=False)
        if version.returncode:raise ValueError((version.stderr or version.stdout)[-500:])
        lines=version.stdout.splitlines();result['version']=lines[0].strip() if lines else 'unknown'
        databases=subprocess.run([exe,'databases'],env=env,capture_output=True,text=True,timeout=20,check=False)
        if databases.returncode:raise ValueError('Database bundle is not ready. Run plannotate setupdb.')
        manifest=json.loads(databases.stdout)
        if not isinstance(manifest,dict):raise ValueError('Database manifest must be a JSON object.')
        root=next((line.split(': ',1)[1] for line in lines if line.startswith('database path: ')),None)
        files=_database_files(manifest,root)
        result.update(database_version=manifest.get('database_version',manifest.get('bundle')),
                      database_fingerprint=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest())
        if verify_databases:
            mismatches=[]
            for name,path,expected in files:
                digest=hashlib.sha256()
                with path.open('rb') as stream:
                    for block in iter(lambda:stream.read(1024*1024),b''):
                        digest.update(block);result['database_bytes_checked']+=len(block)
                result['database_files_checked']+=1
                if digest.hexdigest()!=expected:mismatches.append(name)
            if mismatches:raise ValueError('Database checksum mismatch: '+', '.join(mismatches[:3]))
            result['database_integrity']='verified'
        result.update(ready=True,reason='pLannotate and its database bundle are ready.' if not verify_databases
                      else 'pLannotate is ready; all database file SHA-256 checks passed.')
    except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
        if verify_databases:result['database_integrity']='failed'
        result['reason']='pLannotate readiness check failed: '+str(exc)[-500:]
    return result
