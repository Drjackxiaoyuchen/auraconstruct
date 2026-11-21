"""Build a private, standalone pLannotate nucleotide index from source references."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from Bio.Seq import Seq

from . import engine,library
from .sequence_io import read_bytes

SELECTION_POLICY='eligible-source-semantics-without-unresolved-conflicts-v2'


def _sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def _fingerprint(manifest):
    keys=('schema_version','reference_revision','reference_policy','selection_policy','engine_version',
          'method','config','entries','skipped','files')
    return hashlib.sha256(json.dumps({k:manifest[k] for k in keys},sort_keys=True).encode()).hexdigest()


def index_status(directory):
    """Verify recorded bytes and metadata; this does not execute an annotation query."""
    root=Path(directory).resolve();result={'ready':False,'files_checked':0,'bytes_checked':0}
    try:
        m=json.loads((root/'manifest.json').read_text())
        if not isinstance(m,dict):raise ValueError('Index manifest must be a JSON object.')
        if m.get('schema_version')!=1 or m.get('status')!='ready':raise ValueError('Index build is not ready.')
        if m.get('config')!='databases.yml' or m['config'] not in m.get('files',{}):raise ValueError('Index configuration is missing.')
        for name,path,expected in engine._database_files(m,str(root)):
            if _sha(path)!=expected:raise ValueError('Index checksum mismatch: '+name)
            result['files_checked']+=1;result['bytes_checked']+=path.stat().st_size
        if _fingerprint(m)!=m.get('index_fingerprint'):raise ValueError('Index manifest fingerprint mismatch.')
        result.update(ready=True,index_fingerprint=m['index_fingerprint'],reference_revision=m['reference_revision'],
                      entries=len(m['entries']),skipped=len(m['skipped']),config=str(root/m['config']),
                      reason='Recorded index files and provenance passed verification; query behavior is checked separately.')
    except (OSError,ValueError,KeyError,TypeError) as exc:result['reason']=str(exc)
    return result


def build_index(directory,path=None,timeout=180):
    if timeout<=0:raise ValueError('Index build timeout must be positive.')
    raw,revision=library.reference_genbank(path)
    records=read_bytes(raw,'references.gb');entries=[];skipped=[];sequences=[]
    for i,c in enumerate(records,1):
        f=c.features[0];q=f.qualifiers
        entry={'id':f'part_{i:06d}','part_sha256':q['library_part_sha256'][0],
               'name':f.label,'type':f.type,'role':f.role,'source_orientation':f.strand,
               'aliases':q['library_aliases'],'source_urls':q['library_source_urls'],'licenses':q['library_licenses'],
               'role_resolution':q.get('library_role_choice',['legacy-consensus'])[0],
               'role_alternatives':q.get('library_role_alts',[f.role]),'type_alternatives':q.get('library_type_alts',[f.type])}
        issues=[]
        if q.get('library_strand_issue')==['true']:issues.append('library_strand_issue')
        if q.get('library_role_issue')==['true'] and entry['role_resolution']!='source-semantics':issues.append('library_role_issue')
        if issues:
            skipped.append({**entry,'reasons':issues});continue
        sequence=c.sequence if f.strand==1 else str(Seq(c.sequence).reverse_complement())
        sequences.append(sequence);entries.append(entry)
    if not entries:raise ValueError('No conflict-free eligible source references are available for indexing.')
    exe=engine.executable()
    if not exe:raise ValueError('pLannotate is not installed.')
    env=engine.environment(exe)
    if not shutil.which('makeblastdb',path=env['PATH']):raise ValueError('Missing index builder: makeblastdb.')
    try:version=subprocess.run([exe,'--version'],env=env,capture_output=True,text=True,timeout=20,check=False)
    except subprocess.TimeoutExpired as exc:raise ValueError('pLannotate version check timed out.') from exc
    if version.returncode:raise ValueError('Cannot read pLannotate version: '+(version.stderr or version.stdout)[-500:])
    if not version.stdout.strip():raise ValueError('pLannotate did not report a version.')
    root=Path(directory).resolve();root.mkdir(parents=True,exist_ok=False)
    m={'schema_version':1,'status':'building','created_utc':datetime.now(timezone.utc).isoformat(),
       'reference_revision':revision,'reference_policy':library.REFERENCE_POLICY,'selection_policy':SELECTION_POLICY,
       'engine_version':version.stdout.splitlines()[0].strip(),'method':'blastn','config':'databases.yml',
       'entries':entries,'skipped':skipped}
    manifest=root/'manifest.json'
    def save():manifest.write_text(json.dumps(m,indent=2))
    save()
    try:
        (root/'references.gb').write_bytes(raw)
        with (root/'parts.fasta').open('w') as fasta:
            for e,sequence in zip(entries,sequences):fasta.write('>'+e['id']+'\n'+sequence+'\n')
        with (root/'descriptions.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=['sseqid','name','type','blurb']);writer.writeheader()
            for e in entries:
                blurb='Source annotation; function unverified. '+json.dumps({'library_revision':revision,**e},sort_keys=True)
                writer.writerow(dict(sseqid=e['id'],name=e['name'],type=e['type'],blurb=blurb))
        command=[exe,'makedb','-i',str(root/'parts.fasta'),'-n','auraconstruct','-m','blastn',
                 '-c',str(root/'descriptions.csv'),'-o',str(root),'--no-builtins']
        try:result=subprocess.run(command,env=env,capture_output=True,text=True,timeout=timeout,check=False)
        except subprocess.TimeoutExpired as exc:raise ValueError(f'pLannotate index build exceeded {timeout} seconds.') from exc
        (root/'build.log').write_text(result.stdout+'\n'+result.stderr)
        if result.returncode:raise ValueError('pLannotate index build failed: '+(result.stderr or result.stdout)[-1000:])
        if not (root/'databases.yml').is_file() or not list(root.rglob('*.nsq')) or not list(root.rglob('*.db')):
            raise ValueError('Index builder did not produce configuration, nucleotide index and descriptions database.')
        m['files']={}
        for p in sorted(root.rglob('*')):
            if not p.is_file() or p.name in ('manifest.json','build.log'):continue
            if p.is_symlink() or not p.resolve().is_relative_to(root):raise ValueError('Index output resolves outside its bundle.')
            m['files'][str(p.relative_to(root))]={'sha256':_sha(p),'bytes':p.stat().st_size}
        m.update(status='ready',finished_utc=datetime.now(timezone.utc).isoformat())
        m['index_fingerprint']=_fingerprint(m);save()
        verified=index_status(root)
        if not verified['ready']:raise ValueError(verified['reason'])
        return verified
    except Exception as exc:
        m.update(status='failed',error=str(exc),finished_utc=datetime.now(timezone.utc).isoformat());save();raise
