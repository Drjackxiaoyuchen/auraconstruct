from pathlib import Path
from types import SimpleNamespace
import json
import subprocess

import pytest

from auraconstruct import library_index
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
    assert m['entries'][0]['licenses']==['test terms'] and m['reference_policy']=='source-annotation-v1'
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
