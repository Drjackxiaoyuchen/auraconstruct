import sqlite3
import pytest
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


@pytest.mark.parametrize('source,evidence',[
    ('pLannotate-prediction','predicted'),('exact-reference:parts.gb','reference-match'),
    ('manual','manual'),('unrecognized-tool','unreviewed')])
def test_derived_annotations_are_preserved_without_becoming_source_references(tmp_path,source,evidence):
    db=tmp_path/'library.db';c=fixture();c.features[0].source=source;raw=to_genbank(c)
    result=ingest(raw,'derived.gb',source_url='https://example.org/derived',license_notice='test',path=db)
    assert result['total']['parts']==1 and result['total']['observations']==1
    assert stats(db)['matchable_parts']==0
    with sqlite3.connect(db) as con:
        assert con.execute('SELECT evidence FROM observations').fetchone()[0]==evidence
        raw_path=con.execute('SELECT raw_path FROM sources').fetchone()[0]
    from pathlib import Path
    assert Path(raw_path).read_bytes()==raw
    with pytest.raises(ValueError,match='no eligible source-annotated'):reference_genbank(db)


def test_legacy_prediction_rows_cannot_launder_evidence_or_aliases(tmp_path):
    db=tmp_path/'library.db';source=fixture()
    ingest(to_genbank(source),'source.gb',source_url='https://example.org/source',license_notice='source terms',path=db)
    _,revision=reference_genbank(db)
    derived=fixture();derived.name='derived';derived.features[0].label='Unreviewed prediction'
    derived.features[0].type='promoter';derived.features[0].role='promoter'
    # Engine metadata catches predictions even if their source field was lost or rewritten.
    derived.features[0].qualifiers['ac_engine_version']=['pLannotate 2.0.0']
    ingest(to_genbank(derived),'derived.gb',source_url='https://example.org/prediction',license_notice='prediction terms',path=db)
    with sqlite3.connect(db) as con:
        con.execute("UPDATE observations SET evidence='source-annotation'")
    raw,after_revision=reference_genbank(db);f=read_bytes(raw,'reference.gb')[0].features[0]
    assert after_revision==revision and f.qualifiers['library_aliases']==['Part A']
    assert f.type=='CDS' and f.role=='cds'
    assert f.qualifiers['library_source_urls']==['https://example.org/source']
    assert f.qualifiers['library_licenses']==['source terms']
    assert stats(db)['observations']==2 and stats(db)['matchable_parts']==1
    with sqlite3.connect(db) as con:
        con.execute("DELETE FROM observations WHERE qualifiers NOT LIKE '%ac_engine_version%'")
    assert stats(db)['matchable_parts']==0
    with pytest.raises(ValueError,match='no eligible source-annotated'):reference_genbank(db)


@pytest.mark.parametrize('kind',['old_sequence','misc_difference','variation','unsure'])
def test_historical_annotations_are_retained_but_not_used_as_reference_parts(tmp_path,kind):
    db=tmp_path/'library.db';c=fixture();c.features[0].type=kind
    ingest(to_genbank(c),'history.gb',source_url='https://example.org/history',license_notice='test',path=db)
    assert stats(db)['observations']==1 and stats(db)['matchable_parts']==0
    with sqlite3.connect(db) as con:
        assert con.execute('SELECT evidence FROM observations').fetchone()[0]=='historical-annotation'


def test_reimporting_a_library_export_does_not_create_independent_source_evidence(tmp_path):
    first=tmp_path/'first.db';second=tmp_path/'second.db'
    ingest(to_genbank(fixture()),'source.gb',source_url='https://example.org/source',license_notice='test',path=first)
    raw,_=reference_genbank(first)
    ingest(raw,'library-export.gb',source_url='https://example.org/export',license_notice='test',path=second)
    assert stats(second)['observations']==1 and stats(second)['matchable_parts']==0
    with sqlite3.connect(second) as con:
        assert con.execute('SELECT evidence FROM observations').fetchone()[0]=='reference-match'
