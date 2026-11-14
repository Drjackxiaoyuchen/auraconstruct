import sqlite3
from Bio.Seq import Seq

from auraconstruct.library import ingest,stats,seed_demos,reference_genbank,annotate_library
from auraconstruct.model import Construct,Feature
from auraconstruct.sequence_io import to_genbank,read_bytes


def fixture():
    # Canonical reverse complement differs; matching must retain biological orientation.
    return Construct('ref','ref','TTGCGTACCGTATGCAAGTC','linear',[
        Feature('a','Part A','CDS','cds',[[0,20]],1)
    ],'ref.gb','genbank')


def test_dedup_keeps_aliases_and_source_observations(tmp_path):
    db=tmp_path/'library.db';a=fixture();raw=to_genbank(a)
    first=ingest(raw,'ref.gb',source_url='https://example.org/a',license_notice='test fixture',path=db)
    second=ingest(raw,'ref.gb',source_url='https://example.org/a',license_notice='test fixture',path=db)
    assert first['added']['parts']==1 and second['added']['records']==0
    a.name='alias';a.id='alias';a.features[0].label='Alternative name'
    ingest(to_genbank(a),'alias.gb',source_url='https://example.org/b',license_notice='different source terms',path=db)
    counts=stats(db)
    assert counts==dict(sources=2,records=2,parts=1,observations=2,matchable_parts=1)
    refs,revision=reference_genbank(db);parsed=read_bytes(refs,'references.gb')
    assert len(parsed)==1 and len(revision)==64
    assert parsed[0].features[0].qualifiers['library_aliases']==['Alternative name','Part A']
    with sqlite3.connect(db) as con:
        assert con.execute('SELECT count(*) FROM contexts').fetchone()[0]==2
    assert all(p.read_bytes() for p in (tmp_path/'raw').iterdir())


def test_library_match_retains_strand_coordinates_and_sequence(tmp_path):
    db=tmp_path/'library.db';c=fixture()
    ingest(to_genbank(c),'ref.gb',source_url='https://example.org/a',license_notice='test fixture',path=db)
    for strand,seq in [(1,c.sequence),(-1,str(Seq(c.sequence).reverse_complement()))]:
        target=Construct('target','target','CCCC'+seq+'GGGG','linear',[],'x.fa','fasta')
        result=annotate_library(target,db)
        assert result.sequence==target.sequence and len(result.features)==1
        f=result.features[0]
        assert f.segments==[[4,24]] and f.strand==strand and f.role=='cds'
        assert f.source.startswith('exact-reference:local-library-')
        assert 'https://example.org/a' in f.qualifiers['library_source_urls']


def test_seed_is_idempotent_and_keeps_raw_feature_counts(tmp_path):
    db=tmp_path/'library.db'
    a,b=seed_demos(db),seed_demos(db)
    assert a['added_records']==6 and b['added_records']==0
    assert b['total']['observations']==187 and b['total']['parts']==118


def test_same_sequence_role_conflicts_stay_visible(tmp_path):
    db=tmp_path/'library.db';a=fixture()
    ingest(to_genbank(a),'a.gb',source_url='https://example.org/a',license_notice='test',path=db)
    a.id=a.name='b';a.features[0].role='promoter';a.features[0].type='promoter'
    ingest(to_genbank(a),'b.gb',source_url='https://example.org/b',license_notice='test',path=db)
    raw,_=reference_genbank(db);f=read_bytes(raw,'ref.gb')[0].features[0]
    assert f.role=='generic' and f.qualifiers['library_role_issue']==['true']
