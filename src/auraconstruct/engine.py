"""Discover and check an isolated pLannotate 2 installation without changing user Python."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
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


def status():
    exe=executable()
    result={'installed':bool(exe),'ready':False,'version':None,'database_version':None,
            'database_fingerprint':None,'reason':'pLannotate is not installed. See docs/ANNOTATION.md.'}
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
        if not isinstance(manifest,dict) or not manifest.get('files'):raise ValueError('Database manifest is missing file checksums.')
        root=next((line.split(': ',1)[1] for line in lines if line.startswith('database path: ')),None)
        if root:
            root=Path(root)
            missing_files=[name for name in manifest['files'] if not (root/name).is_file()]
            if missing_files:raise ValueError('Database bundle is incomplete: '+', '.join(missing_files[:3]))
        result.update(ready=True,database_version=manifest.get('database_version',manifest.get('bundle')),
                      database_fingerprint=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),
                      reason='pLannotate and its database bundle are ready.')
    except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
        result['reason']='pLannotate readiness check failed: '+str(exc)[-500:]
    return result
