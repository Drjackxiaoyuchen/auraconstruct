"""Private local sequence library; source observations remain separate from deduped parts."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from Bio.Seq import Seq

from .model import Construct, Feature
from .sequence_io import read_bytes, to_genbank


def data_dir():
    return Path(os.environ.get('AURACONSTRUCT_DATA_DIR',Path.home()/'.local/share/auraconstruct')).expanduser()


def library_path():
    return Path(os.environ.get('AURACONSTRUCT_LIBRARY',data_dir()/'library/library.sqlite3')).expanduser()


def _hash(value):
    return hashlib.sha256(value.encode() if isinstance(value,str) else value).hexdigest()


def _connect(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=20)
    db.execute('PRAGMA foreign_keys=ON')
    if db.execute('PRAGMA user_version').fetchone()[0] not in (0,1):
        db.close();raise ValueError('This library schema is newer than this application supports.')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS sources (
        id TEXT PRIMARY KEY, file_name TEXT NOT NULL, raw_path TEXT NOT NULL, first_seen TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS contexts (
        source_id TEXT REFERENCES sources(id), url TEXT NOT NULL, license TEXT NOT NULL,
        access_note TEXT NOT NULL, retrieved TEXT NOT NULL,
        UNIQUE(source_id,url,license,access_note));
      CREATE TABLE IF NOT EXISTS records (
        id TEXT PRIMARY KEY, source_id TEXT REFERENCES sources(id), record_index INTEGER,
        name TEXT, length INTEGER, sequence_sha256 TEXT, sequence TEXT, topology TEXT);
      CREATE TABLE IF NOT EXISTS parts (
        id TEXT PRIMARY KEY, sequence TEXT NOT NULL, length INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS observations (
        id TEXT PRIMARY KEY, record_id TEXT REFERENCES records(id), part_id TEXT REFERENCES parts(id),
        feature_id TEXT, label TEXT, type TEXT, role TEXT, role_source TEXT,
        segments TEXT, strand INTEGER, canonical_orientation INTEGER,
        qualifiers TEXT, fuzzy INTEGER, evidence TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS part_observations ON observations(part_id);
      PRAGMA user_version=1;
    ''')
    return db


def stats(path=None):
    path=Path(path or library_path())
    if not path.exists():return dict(sources=0,records=0,parts=0,observations=0,matchable_parts=0)
    with sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro',uri=True) as db:
        counts={table:db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
                for table in ('sources','records','parts','observations')}
        counts['matchable_parts']=db.execute("SELECT count(*) FROM parts p WHERE length>=12 AND sequence NOT GLOB '*[^ACGT]*' AND EXISTS (SELECT 1 FROM observations o WHERE o.part_id=p.id AND o.fuzzy=0)").fetchone()[0]
    return counts


def ingest(data,file_name,*,source_url,license_notice,access_note='',path=None):
    if not source_url or not license_notice:
        raise ValueError('Record a source URL and a license notice, including unknown/review-needed when applicable.')
    records=read_bytes(data,file_name)  # Validate before creating library files.
    path=Path(path or library_path());before=stats(path)
    source_id=_hash(data);now=datetime.now(timezone.utc).isoformat()
    raw_dir=path.parent/'raw';raw_dir.mkdir(parents=True,exist_ok=True)
    raw_path=raw_dir/(source_id+'.bin')
    if raw_path.exists() and _hash(raw_path.read_bytes())!=source_id:
        raise ValueError('A stored raw source failed its checksum; ingestion stopped.')
    if not raw_path.exists():raw_path.write_bytes(data)
    db=_connect(path)
    try:
        with db:
            db.execute('INSERT OR IGNORE INTO sources VALUES (?,?,?,?)',(source_id,Path(file_name).name,str(raw_path),now))
            db.execute('INSERT OR IGNORE INTO contexts VALUES (?,?,?,?,?)',(source_id,source_url,license_notice,access_note,now))
            for index,c in enumerate(records):
                record_id=_hash(f'{source_id}:{index}')
                db.execute('INSERT OR IGNORE INTO records VALUES (?,?,?,?,?,?,?,?)',
                           (record_id,source_id,index,c.name,c.length,_hash(c.sequence),c.sequence,c.topology))
                for f in c.features:
                    strands=f.segment_strands or [f.strand]*len(f.segments)
                    seq=''.join(c.sequence[a:b] if strand!=-1 else str(Seq(c.sequence[a:b]).reverse_complement())
                                for (a,b),strand in zip(f.segments,strands))
                    rev=str(Seq(seq).reverse_complement());canonical=min(seq,rev);part_id=_hash(canonical)
                    db.execute('INSERT OR IGNORE INTO parts VALUES (?,?,?)',(part_id,canonical,len(canonical)))
                    observation_id=_hash(f'{record_id}:{f.id}')
                    db.execute('INSERT OR IGNORE INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                               (observation_id,record_id,part_id,f.id,f.label,f.type,f.role,f.role_source,
                                json.dumps(f.segments),f.strand,1 if canonical==seq else -1,
                                json.dumps(f.qualifiers,ensure_ascii=False),int(f.fuzzy),'source-annotation'))
    finally:db.close()
    after=stats(path)
    return dict(source_sha256=source_id,added={k:after[k]-before[k] for k in after},total=after)


def seed_demos(path=None):
    from .demos import ROOT,manifest
    seen=set();results=[]
    for entry in manifest():
        if entry['file'] in seen:continue
        seen.add(entry['file']);raw=(ROOT/entry['file']).read_bytes()
        if _hash(raw)!=entry['file_sha256']:raise ValueError('Bundled source checksum failed.')
        results.append(ingest(raw,entry['file'],source_url=entry['source_url'],license_notice=entry['license'],
                              access_note='Existing bundled demonstration source; not a new download. DOI: '+entry['doi']+
                              '; archive: '+entry['download_url'],path=path))
    return dict(ingested_files=len(results),added_records=sum(r['added']['records'] for r in results),total=stats(path))


def reference_genbank(path=None):
    path=Path(path or library_path())
    if not path.exists():raise ValueError('The local library is empty. Ingest annotated reference records first.')
    output=[];observation_ids=[]
    with sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        for part in db.execute("SELECT * FROM parts WHERE length>=12 AND sequence NOT GLOB '*[^ACGT]*' ORDER BY id"):
            obs=db.execute('SELECT * FROM observations WHERE part_id=? AND fuzzy=0 ORDER BY id',(part['id'],)).fetchall()
            if not obs:continue
            contexts=db.execute('''SELECT DISTINCT c.url,c.license FROM contexts c JOIN records r ON c.source_id=r.source_id
                                  JOIN observations o ON o.record_id=r.id WHERE o.part_id=?''',(part['id'],)).fetchall()
            orientations=sorted({o['canonical_orientation'] for o in obs})
            for orientation in orientations:
                group=[o for o in obs if o['canonical_orientation']==orientation]
                labels=sorted({o['label'] for o in group});roles={o['role'] for o in group};types={o['type'] for o in group}
                label=' / '.join(labels);label=label if len(label)<=240 else label[:237]+'...'
                role=next(iter(roles)) if len(roles)==1 else 'generic'
                kind=next(iter(types)) if len(types)==1 else 'misc_feature'
                q={'library_part_sha256':[part['id']],'library_aliases':labels,
                   'library_source_urls':sorted({c['url'] for c in contexts}),
                   'library_licenses':sorted({c['license'] for c in contexts}),
                   'library_role_issue':['true' if len(roles)>1 else 'false'],
                   'library_strand_issue':['true' if len(orientations)>1 else 'false'],
                   'note':['Source feature annotation; identity/function has not been independently validated.']}
                f=Feature('part',label,kind,role,[[0,part['length']]],orientation,role_source='library-source-consensus',qualifiers=q)
                name=part['id'][:18]+('p' if orientation==1 else 'm')
                c=Construct(name,name,part['sequence'],'linear',[f],'local-library','genbank')
                output.append(to_genbank(c));observation_ids.extend(o['id'] for o in group)
    if not output:raise ValueError('The library has no unambiguous, non-fuzzy reference parts of at least 12 bases.')
    return b''.join(output),_hash('\n'.join(sorted(observation_ids)))


def annotate_library(construct,path=None):
    from .annotate import exact_annotate
    raw,revision=reference_genbank(path)
    result=exact_annotate(construct,raw,f'local-library-{revision[:12]}.gb')
    result.provenance={**result.provenance,'local_library_revision':revision}
    return result
