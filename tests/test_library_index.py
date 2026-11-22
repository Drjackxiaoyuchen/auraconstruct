from pathlib import Path
from types import SimpleNamespace
import json
import subprocess
import hashlib

import pytest

from auraconstruct import library_index,library
from auraconstruct.library import ingest,stats
from auraconstruct.model import Construct,Feature
from auraconstruct.sequence_io import to_genbank,read_bytes


def source():
    return Construct('source','source','TTGCGTACCGTATGCAAGTC','linear',[
        Feature('a','Part A','CDS','cds',[[0,20]],1)
    ],'source.gb','genbank')


def seeded(tmp_path):
    db=tmp_path/'library.db'
    ingest(to_genbank(source()),'source.gb',source_url='https://example.org/source',license_notice='test terms',path=db)
    return db


def fake_builder(monkeypatch,*,failure=False,timeout=False):
    monkeypatch.setattr(library_index.engine,'executable',lambda:'/fake/bin/plannotate')
    monkeypatch.setattr(library_index.shutil,'which',lambda *a,**k:'/fake/bin/makeblastdb')
    def run(args,**kwargs):
        if '--version' in args:return SimpleNamespace(returncode=0,stdout='pLannotate 2.0.0\n',stderr='')
        assert '--no-builtins' in args and args[args.index('-m')+1]=='blastn'
        assert kwargs['env']['PYTHONNOUSERSITE']=='1'
        if timeout:raise subprocess.TimeoutExpired(args,kwargs['timeout'])
        if failure:return SimpleNamespace(returncode=1,stdout='',stderr='builder failed')
        root=Path(args[args.index('-o')+1])
        for name in ('auraconstruct.nsq','auraconstruct.db','databases.yml'):(root/name).write_text('mock index artifact')
        return SimpleNamespace(returncode=0,stdout='mock build completed',stderr='')
    monkeypatch.setattr(library_index.subprocess,'run',run)


def test_private_builder_retains_biological_orientation_source_policy_and_snapshot(tmp_path,monkeypatch):
    db=seeded(tmp_path);before=stats(db);fake_builder(monkeypatch)
    out=tmp_path/'index';result=library_index.build_index(out,db)
    assert result['ready'] and result['entries']==1 and result['skipped']==0 and stats(db)==before
    m=json.loads((out/'manifest.json').read_text())
    assert m['entries'][0]['source_urls']==['https://example.org/source']
    assert m['entries'][0]['licenses']==['test terms'] and m['reference_policy']==library.REFERENCE_POLICY
    assert read_bytes((out/'parts.fasta').read_bytes(),'parts.fasta')[0].sequence==source().sequence
    assert len(m['index_fingerprint'])==len(m['reference_revision'])==64
    assert library_index.index_status(out)['ready']
    with pytest.raises(FileExistsError):library_index.build_index(out,db)


def test_index_readiness_rejects_modified_files_and_provenance(tmp_path,monkeypatch):
    db=seeded(tmp_path);fake_builder(monkeypatch);out=tmp_path/'index';library_index.build_index(out,db)
    path=out/'databases.yml';original=path.read_bytes();path.write_bytes(b'changed config')
    assert not library_index.index_status(out)['ready'] and 'checksum mismatch' in library_index.index_status(out)['reason']
    path.write_bytes(original)
    m=json.loads((out/'manifest.json').read_text());m['reference_revision']='0'*64;(out/'manifest.json').write_text(json.dumps(m))
    assert 'fingerprint mismatch' in library_index.index_status(out)['reason']


@pytest.mark.parametrize('mode',['failure','timeout'])
def test_failed_build_remains_auditable_and_not_ready(tmp_path,monkeypatch,mode):
    db=seeded(tmp_path);fake_builder(monkeypatch,failure=mode=='failure',timeout=mode=='timeout');out=tmp_path/'index'
    with pytest.raises(ValueError):library_index.build_index(out,db,timeout=1)
    m=json.loads((out/'manifest.json').read_text());assert m['status']=='failed' and m['error']
    assert not library_index.index_status(out)['ready'] and (out/'references.gb').exists()


def test_conflicting_reference_roles_are_retained_but_not_indexed(tmp_path):
    db=seeded(tmp_path);c=source();c.name='other';c.features[0].type='promoter';c.features[0].role='promoter'
    ingest(to_genbank(c),'other.gb',source_url='https://example.org/other',license_notice='test terms',path=db)
    with pytest.raises(ValueError,match='No conflict-free'):library_index.build_index(tmp_path/'index',db)
    assert stats(db)['observations']==2 and not (tmp_path/'index').exists()


def test_malformed_or_escaping_manifest_is_not_ready(tmp_path,monkeypatch):
    (tmp_path/'manifest.json').write_text('[]');assert not library_index.index_status(tmp_path)['ready']
    db=seeded(tmp_path);fake_builder(monkeypatch);out=tmp_path/'index';library_index.build_index(out,db)
    m=json.loads((out/'manifest.json').read_text());m['files']['../outside']={'sha256':'0'*64}
    (out/'manifest.json').write_text(json.dumps(m))
    assert 'unsafe file path' in library_index.index_status(out)['reason']


def test_index_status_cli_emits_nonzero_json_result_for_missing_bundle(tmp_path,monkeypatch,capsys):
    from auraconstruct.cli import main
    monkeypatch.setattr('sys.argv',['auraconstruct','library','index-status',str(tmp_path/'missing')])
    with pytest.raises(SystemExit) as exc:main()
    assert exc.value.code==1 and json.loads(capsys.readouterr().out)['ready'] is False


def test_index_keeps_resolved_context_alternatives_and_explicit_cds_type(tmp_path,monkeypatch):
    db=seeded(tmp_path);c=source();c.name='context';f=c.features[0]
    f.label='Gene context';f.type='gene';f.role='generic'
    ingest(to_genbank(c),'context.gb',source_url='https://example.org/context',license_notice='test terms',path=db)
    fake_builder(monkeypatch);out=tmp_path/'index';result=library_index.build_index(out,db)
    m=json.loads((out/'manifest.json').read_text());entry=m['entries'][0]
    assert result['entries']==1 and result['skipped']==0 and entry['type']=='CDS' and entry['role']=='cds'
    assert entry['role_resolution']=='source-semantics' and entry['role_alternatives']==['cds','generic']
    assert entry['type_alternatives']==['CDS','gene'] and stats(db)['observations']==2


@pytest.mark.parametrize('context_role',['generic','region','engineered_region'])
def test_parts_profile_audits_excluded_context_without_changing_source_snapshot(tmp_path,monkeypatch,context_role):
    db=seeded(tmp_path);c=source();c.sequence+='ACGATCGTAGCTAGTCAGCA';c.name='wrapped'
    c.features=[Feature('context','Broad context','misc_feature',context_role,[[0,40]],1)]
    ingest(to_genbank(c),'context.gb',source_url='https://example.org/context',license_notice='context terms',path=db)
    before=stats(db);fake_builder(monkeypatch)
    full=tmp_path/'source';parts=tmp_path/'parts'
    assert library_index.build_index(full,db)['entries']==2
    result=library_index.build_index(parts,db,profile='parts')
    m=json.loads((parts/'manifest.json').read_text())
    assert result['profile']=='parts' and result['entries']==1 and result['skipped']==1
    assert m['entries'][0]['type']=='CDS' and m['skipped'][0]['role']==context_role
    assert m['skipped'][0]['source_urls']==['https://example.org/context']
    assert m['skipped'][0]['reasons']==['context_role_excluded_by_parts_profile']
    assert (full/'references.gb').read_bytes()==(parts/'references.gb').read_bytes()
    assert stats(db)==before


def test_legacy_schema_one_index_still_verifies_and_new_profile_is_integrity_checked(tmp_path,monkeypatch):
    db=seeded(tmp_path);fake_builder(monkeypatch);out=tmp_path/'index';library_index.build_index(out,db)
    path=out/'manifest.json';m=json.loads(path.read_text());original=json.loads(path.read_text())
    m['profile']='parts';m['selection_policy']=library_index.PROFILES['parts'];path.write_text(json.dumps(m))
    assert 'fingerprint mismatch' in library_index.index_status(out)['reason']
    # Reconstruct a v0.7.1 manifest using its recorded hash contract, without a profile.
    m=original;m['schema_version']=1;m.pop('profile')
    keys=('schema_version','reference_revision','reference_policy','selection_policy','engine_version','method','config','entries','skipped','files')
    m['index_fingerprint']=hashlib.sha256(json.dumps({k:m[k] for k in keys},sort_keys=True).encode()).hexdigest()
    path.write_text(json.dumps(m))
    assert library_index.index_status(out)['ready'] and library_index.index_status(out)['profile']=='source'


def test_parts_profile_keeps_conflicts_excluded_and_rejects_empty_or_unknown_selection(tmp_path):
    db=seeded(tmp_path);c=source();c.name='other';c.features[0].type='promoter';c.features[0].role='promoter'
    ingest(to_genbank(c),'other.gb',source_url='https://example.org/other',license_notice='test',path=db)
    with pytest.raises(ValueError,match='No conflict-free'):library_index.build_index(tmp_path/'empty',db,profile='parts')
    with pytest.raises(ValueError,match='Unknown index profile'):library_index.build_index(tmp_path/'bad',db,profile='unknown')
    assert not (tmp_path/'empty').exists() and not (tmp_path/'bad').exists()


def test_index_builder_cli_passes_explicit_parts_profile(tmp_path,monkeypatch,capsys):
    from auraconstruct.cli import main
    captured={}
    def build(directory,path,timeout,*,profile):
        captured.update(directory=directory,path=path,timeout=timeout,profile=profile)
        return {'ready':True,'profile':profile}
    monkeypatch.setattr(library_index,'build_index',build)
    monkeypatch.setattr('sys.argv',['auraconstruct','library','build-index','-o',str(tmp_path/'out'),'--profile','parts'])
    main()
    assert captured['profile']=='parts' and json.loads(capsys.readouterr().out)['profile']=='parts'
