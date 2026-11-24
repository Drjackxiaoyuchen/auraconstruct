import json
import hashlib
import subprocess
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


def test_default_annotation_mode_requires_no_help_probe_and_unknown_modes_fail(monkeypatch):
    def unexpected(*a,**k):raise AssertionError('Default mode must not probe help.')
    monkeypatch.setattr(engine.subprocess,'run',unexpected)
    assert engine.annotation_flags('default')==[]
    with pytest.raises(ValueError,match='Unknown annotation mode'):engine.annotation_flags('unknown')


@pytest.mark.parametrize('help_text',['│    --detailed    -d   retain nested calls\n','  \x1b[1m--detailed\x1b[0m  retain nested calls\n'])
def test_detailed_mode_checks_installed_isolated_help(monkeypatch,help_text):
    monkeypatch.setattr(engine,'executable',lambda:'/isolated/bin/plannotate')
    def probe(args,**kwargs):
        assert args==['/isolated/bin/plannotate','batch','--help'] and kwargs['timeout']==20
        assert kwargs['env']['PYTHONNOUSERSITE']=='1'
        return SimpleNamespace(returncode=0,stdout=help_text,stderr='')
    monkeypatch.setattr(engine.subprocess,'run',probe)
    assert engine.annotation_flags('detailed')==['--detailed']


@pytest.mark.parametrize('help_text',['  --detailed-mode  a different option\n','  Remove --detailed from old command lines.\n'])
def test_missing_legacy_flag_is_not_assumed_supported_from_version_or_mentions(monkeypatch,help_text):
    monkeypatch.setattr(engine,'executable',lambda:'/isolated/bin/plannotate')
    monkeypatch.setattr(engine.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout=help_text,stderr=''))
    with pytest.raises(ValueError,match='does not advertise'):engine.annotation_flags('detailed')


@pytest.mark.parametrize('failure',['nonzero','timeout','oserror'])
def test_detailed_help_probe_errors_prevent_search(monkeypatch,failure):
    monkeypatch.setattr(engine,'executable',lambda:'/isolated/bin/plannotate')
    def probe(*a,**k):
        if failure=='timeout':raise subprocess.TimeoutExpired(a[0],20)
        if failure=='oserror':raise OSError('Cannot execute')
        return SimpleNamespace(returncode=2,stdout='',stderr='Unsupported')
    monkeypatch.setattr(engine.subprocess,'run',probe)
    with pytest.raises(ValueError,match='Cannot'):engine.annotation_flags('detailed')


def test_mode_availability_does_not_probe_an_unready_engine(monkeypatch):
    def unexpected(*a,**k):raise AssertionError('Unready engine must not be probed.')
    monkeypatch.setattr(engine,'annotation_flags',unexpected)
    result=engine.annotation_modes({'ready':False,'reason':'Database unavailable'})
    assert not result['default']['available'] and not result['detailed']['available']
    assert result['default']['reason']=='Database unavailable'


def test_mode_availability_keeps_default_usable_when_detailed_probe_fails(monkeypatch):
    def unsupported(mode):raise ValueError('Installed flag is absent')
    monkeypatch.setattr(engine,'annotation_flags',unsupported)
    result=engine.annotation_modes({'ready':True})
    assert result['default']['available'] and not result['detailed']['available']
    assert result['detailed']['diagnostic']=='Installed flag is absent'


def test_mode_availability_uses_the_existing_capability_gate(monkeypatch):
    calls=[]
    def supported(mode):calls.append(mode);return ['--detailed']
    monkeypatch.setattr(engine,'annotation_flags',supported)
    result=engine.annotation_modes({'ready':True})
    assert calls==['detailed'] and all(item['available'] for item in result.values())
