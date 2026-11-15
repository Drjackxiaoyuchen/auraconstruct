import json
import hashlib
from types import SimpleNamespace
import pytest

from auraconstruct import engine
from auraconstruct.model import Construct
from auraconstruct.scene import build_pages,to_svg


def test_engine_isolates_python_and_discovers_its_search_tools(monkeypatch):
    monkeypatch.setenv('PYTHONPATH','/unrelated/packages')
    monkeypatch.setenv('PYTHONHOME','/unrelated/python')
    env=engine.environment('/isolated/env/bin/plannotate')
    assert env['PATH'].split(':')[0]=='/isolated/env/bin'
    assert env['PYTHONNOUSERSITE']=='1'
    assert 'PYTHONPATH' not in env and 'PYTHONHOME' not in env


def test_engine_presence_is_not_reported_as_database_readiness(monkeypatch):
    monkeypatch.setattr(engine,'executable',lambda:'/fake/bin/plannotate')
    monkeypatch.setattr(engine.shutil,'which',lambda *a,**k:'/fake/tool')
    def fake(args,**kwargs):
        return SimpleNamespace(returncode=0,stdout='pLannotate 2.0.0\n',stderr='') if '--version' in args else SimpleNamespace(returncode=1,stdout='',stderr='no database')
    monkeypatch.setattr(engine.subprocess,'run',fake)
    result=engine.status()
    assert result['installed'] and not result['ready'] and 'Database bundle' in result['reason']


def test_annotation_provenance_does_not_label_private_input_as_a_public_demo():
    c=Construct('x','Uploaded construct','ACGT'*50,'linear',[],'upload.gb','genbank',
                provenance={'annotation_runs':[{'engine':'pLannotate','version':'pLannotate 2.0.0','database_version':2}]})
    p=build_pages(c)[0];svg=to_svg(p)
    assert 'Annotation: pLannotate 2.0.0' in svg
    assert 'Public sequence example' not in svg and 'Public demo provenance' not in p.notes


def fake_database_cli(monkeypatch,root,manifest,*,report_root=True):
    monkeypatch.setattr(engine,'executable',lambda:'/fake/bin/plannotate')
    monkeypatch.setattr(engine.shutil,'which',lambda *a,**k:'/fake/tool')
    def fake(args,**kwargs):
        text='pLannotate 2.0.0\n'+(f'database path: {root}\n' if report_root else '')
        return SimpleNamespace(returncode=0,stdout=text if '--version' in args else json.dumps(manifest),stderr='')
    monkeypatch.setattr(engine.subprocess,'run',fake)


def test_full_database_verification_detects_content_corruption(tmp_path,monkeypatch):
    content=b'example search index';index=tmp_path/'index.nsq';index.write_bytes(content)
    manifest={'database_version':2,'files':{'index.nsq':{'sha256':hashlib.sha256(content).hexdigest()}}}
    fake_database_cli(monkeypatch,tmp_path,manifest)
    fast=engine.status()
    assert fast['ready'] and fast['database_integrity']=='unchecked'
    verified=engine.status(verify_databases=True)
    assert verified['ready'] and verified['database_integrity']=='verified'
    assert verified['database_files_checked']==1 and verified['database_bytes_checked']==len(content)
    index.write_bytes(b'corrupted search index')
    failed=engine.status(verify_databases=True)
    assert not failed['ready'] and failed['database_integrity']=='failed'
    assert 'checksum mismatch' in failed['reason']


def test_manifest_without_a_reported_database_directory_is_not_ready(tmp_path,monkeypatch):
    manifest={'files':{'index.nsq':{'sha256':'0'*64}}}
    fake_database_cli(monkeypatch,tmp_path,manifest,report_root=False)
    result=engine.status()
    assert not result['ready'] and 'absolute database directory' in result['reason']


@pytest.mark.parametrize('name,checksum',[('../outside.nsq','0'*64),('/outside.nsq','0'*64),('index.nsq','invalid')])
def test_database_manifest_rejects_unsafe_paths_and_invalid_hashes(tmp_path,name,checksum):
    with pytest.raises(ValueError):
        engine._database_files({'files':{name:{'sha256':checksum}}},str(tmp_path))


@pytest.mark.parametrize('ready',[True,False])
def test_doctor_cli_emits_json_and_a_machine_readable_exit_status(monkeypatch,capsys,ready):
    from auraconstruct.cli import main
    monkeypatch.setattr('sys.argv',['auraconstruct','doctor','--verify-databases'])
    def fake_status(verify_databases=False):
        assert verify_databases
        return {'ready':ready,'database_integrity':'verified' if ready else 'failed'}
    monkeypatch.setattr(engine,'status',fake_status)
    if ready:main()
    else:
        with pytest.raises(SystemExit) as exc:main()
        assert exc.value.code==1
    assert json.loads(capsys.readouterr().out)['ready']==ready
