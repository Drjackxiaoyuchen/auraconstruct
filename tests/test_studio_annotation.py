from copy import deepcopy

import pytest

from auraconstruct.model import Construct,Feature
from auraconstruct.server import create_app

HEADERS={'X-AuraConstruct':'1'}


def record():
    return Construct('test','Test construct','ACGT'*100,'circular',[
        Feature('imported','Imported part','CDS','cds',[[10,40]],1)
    ],'source.gb','genbank').to_dict()


@pytest.mark.parametrize('mode',[None,'default','detailed'])
def test_annotation_api_routes_explicit_and_legacy_default_modes_without_losing_imports(monkeypatch,mode):
    original=record();expected=mode or 'default'
    def annotate(c,*,mode):
        assert mode==expected and c.sequence==original['sequence']
        c=deepcopy(c);c.features.append(Feature('p','Predicted part','promoter','promoter',[[50,70]],1,source='pLannotate-prediction'))
        c.provenance['annotation_runs']=[{'annotation_mode':mode}];return c
    monkeypatch.setattr('auraconstruct.server.plannotate',annotate)
    payload={'engine':'plannotate','record':original}
    if mode is not None:payload['annotation_mode']=mode
    response=create_app().test_client().post('/api/annotate',json=payload,headers=HEADERS)
    assert response.status_code==200
    result=response.get_json()['record']
    assert result['features'][0]==original['features'][0] and result['sequence']==original['sequence']
    assert result['features'][1]['source']=='pLannotate-prediction'
    assert result['provenance']['annotation_runs'][0]['annotation_mode']==expected


@pytest.mark.parametrize('mode',['unsupported',None,{},1])
def test_annotation_api_rejects_invalid_modes_before_invoking_engine(monkeypatch,mode):
    def unexpected(*a,**k):raise AssertionError('Invalid request must not invoke engine.')
    monkeypatch.setattr('auraconstruct.server.plannotate',unexpected)
    response=create_app().test_client().post('/api/annotate',json={'engine':'plannotate','record':record(),'annotation_mode':mode},headers=HEADERS)
    assert response.status_code==400 and 'Unknown annotation mode' in response.get_json()['error']


@pytest.mark.parametrize('detailed_available',[False,True])
def test_status_reports_mode_capability_separately_from_base_readiness(monkeypatch,detailed_available):
    monkeypatch.setattr('auraconstruct.engine.status',lambda:{'ready':True,'reason':'Base engine ready'})
    def flags(mode):
        if not detailed_available:raise ValueError('Unsupported mode')
        return ['--detailed']
    monkeypatch.setattr('auraconstruct.engine.annotation_flags',flags)
    monkeypatch.setattr('auraconstruct.library.stats',lambda:{'sources':0})
    response=create_app().test_client().get('/api/status');data=response.get_json()
    assert response.status_code==200 and data['plannotate']
    assert data['annotation_modes']['default']['available'] and data['annotation_modes']['detailed']['available']==detailed_available
