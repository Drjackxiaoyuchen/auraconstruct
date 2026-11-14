import json
from types import SimpleNamespace

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
