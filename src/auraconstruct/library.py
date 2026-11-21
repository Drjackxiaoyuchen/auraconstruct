"""Private local sequence library; source observations remain separate from deduped parts."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from Bio.Seq import Seq

from .model import Construct, Feature, infer_role
from .sequence_io import read_bytes, to_genbank

REFERENCE_POLICY='source-semantics-v2'


def data_dir():
    return Path(os.environ.get('AURACONSTRUCT_DATA_DIR',Path.home()/'.local/share/auraconstruct')).expanduser()


def library_path():
    return Path(os.environ.get('AURACONSTRUCT_LIBRARY',data_dir()/'library/library.sqlite3')).expanduser()


def _hash(value):
    return hashlib.sha256(value.encode() if isinstance(value,str) else value).hexdigest()


def _evidence(kind,qualifiers,source='imported'):
    sources={source,*qualifiers.get('auraconstruct_source',[])}
    if 'pLannotate-prediction' in sources or any(qualifiers.get(k) for k in ('ac_engine_version','ac_db_fingerprint')):
        return 'predicted'
    if any(s.startswith('exact-reference:') for s in sources) or qualifiers.get('library_part_sha256'):
        return 'reference-match'
    if sources & {'manual','user'}:return 'manual'
    if sources-{'imported'}:return 'unreviewed'
    if kind in {'old_sequence','misc_difference','variation','unsure'}:return 'historical-annotation'
    return 'source-annotation'


def _eligible(observation):
    # Recheck legacy rows too: earlier imports labeled every observation as source evidence.
    return (observation['evidence']=='source-annotation' and
            _evidence(observation['type'],json.loads(observation['qualifiers']))=='source-annotation')


def _consensus(group):
    """Prefer explicit feature semantics over context, retaining functional conflicts."""
    roles={o['role'] for o in group};types={o['type'] for o in group};typed=[];inconsistent=False
    for o in group:
        role,reason=infer_role(o['type'],json.loads(o['qualifiers']),o['label'])
        if reason in ('feature-type','regulatory-class','sequence-ontology') and role!='generic':
            typed.append((role,o['type']))
            if role!=o['role']:inconsistent=True
    explicit_roles={role for role,kind in typed}
    if inconsistent or len(explicit_roles)>1:return 'generic','misc_feature','unresolved'
    if len(explicit_roles)==1:
        role=next(iter(explicit_roles));explicit_types={kind for r,kind in typed}
        # A different functional role remains a conflict, even if inferred from a label.
        if roles <= {role,'generic','region'}:
            return role,next(iter(explicit_types)) if len(explicit_types)==1 else 'misc_feature','source-semantics'
    if len(roles)==1:return next(iter(roles)),next(iter(types)) if len(types)==1 else 'misc_feature','consensus'
    return 'generic','misc_feature','unresolved'


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
        db.row_factory=sqlite3.Row
        counts={table:db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
                for table in ('sources','records','parts','observations')}
        candidates=db.execute("SELECT o.* FROM observations o JOIN parts p ON o.part_id=p.id WHERE p.length>=12 AND p.sequence NOT GLOB '*[^ACGT]*' AND o.fuzzy=0")
        counts['matchable_parts']=len({o['part_id'] for o in candidates if _eligible(o)})
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
                                json.dumps(f.qualifiers,ensure_ascii=False),int(f.fuzzy),_evidence(f.type,f.qualifiers,f.source)))
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
    output=[]
    with sqlite3.connect(f'{path.resolve().as_uri()}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        for part in db.execute("SELECT * FROM parts WHERE length>=12 AND sequence NOT GLOB '*[^ACGT]*' ORDER BY id"):
            obs=[o for o in db.execute('''SELECT o.*,r.source_id FROM observations o JOIN records r ON o.record_id=r.id
                                          WHERE o.part_id=? AND o.fuzzy=0 ORDER BY o.id''',(part['id'],)) if _eligible(o)]
            if not obs:continue
            source_ids={o['source_id'] for o in obs}
            contexts=db.execute('''SELECT DISTINCT c.source_id,c.url,c.license FROM contexts c JOIN records r ON c.source_id=r.source_id
                                  JOIN observations o ON o.record_id=r.id WHERE o.part_id=?''',(part['id'],)).fetchall()
            contexts=[c for c in contexts if c['source_id'] in source_ids]
            orientations=sorted({o['canonical_orientation'] for o in obs})
            for orientation in orientations:
                group=[o for o in obs if o['canonical_orientation']==orientation]
                labels=sorted({o['label'] for o in group});roles={o['role'] for o in group};types={o['type'] for o in group}
                label=' / '.join(labels);label=label if len(label)<=240 else label[:237]+'...'
                role,kind,choice=_consensus(group)
                q={'library_part_sha256':[part['id']],'library_aliases':labels,
                   'library_evidence':['source-annotation'],
                   'library_ref_policy':[REFERENCE_POLICY],
                   'library_source_urls':sorted({c['url'] for c in contexts}),
                   'library_licenses':sorted({c['license'] for c in contexts}),
                   'library_role_issue':['true' if len(roles)>1 or choice=='unresolved' else 'false'],
                   'library_role_choice':[choice],'library_role_alts':sorted(roles),'library_type_alts':sorted(types),
                   'library_strand_issue':['true' if len(orientations)>1 else 'false'],
                   'note':['Source feature annotation; identity/function has not been independently validated.']}
                f=Feature('part',label,kind,role,[[0,part['length']]],orientation,role_source='library-'+choice,qualifiers=q)
                name=part['id'][:18]+('p' if orientation==1 else 'm')
                c=Construct(name,name,part['sequence'],'linear',[f],'local-library','genbank')
                output.append(to_genbank(c))
    if not output:raise ValueError('The library has no eligible source-annotated, unambiguous, non-fuzzy reference parts of at least 12 bases.')
    raw=b''.join(output)
    # Exported source URLs/terms can change without adding any observation IDs.
    return raw,_hash(b'auraconstruct-reference-v2\n'+raw)


def annotate_library(construct,path=None):
    from .annotate import exact_annotate
    raw,revision=reference_genbank(path)
    result=exact_annotate(construct,raw,f'local-library-{revision[:12]}.gb')
    result.provenance={**result.provenance,'local_library_revision':revision,'local_library_policy':REFERENCE_POLICY}
    return result
