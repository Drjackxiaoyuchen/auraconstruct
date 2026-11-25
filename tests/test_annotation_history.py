from copy import deepcopy
import hashlib
import io
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import pytest

from auraconstruct.annotation_history import annotation_summary
from auraconstruct.model import Construct,Feature
from auraconstruct.scene import build_pages
from auraconstruct.pptx import to_pptx,A
from auraconstruct.server import create_app


def construct():
    c=Construct('test','Test construct','ACGT'*100,'circular',[
        Feature('source','Imported feature','CDS','cds',[[10,40]],1)
    ],'source.gb','genbank')
    c.provenance={'annotation_runs':[{'engine':'pLannotate','version':'pLannotate test','database_version':2,
        'annotation_mode':'detailed','sequence_sha256':hashlib.sha256(c.sequence.encode()).hexdigest(),
        'topology':'circular','time_utc':'2026-11-25T00:00:00+00:00','features_added':1}]}
    return c


def test_summary_uses_saved_mode_and_identifiers_without_mutating_record():
    c=construct();original=deepcopy(c.to_dict());s=annotation_summary(c)
    assert s['recorded_runs']==1 and s['last_run']['mode']=='detailed'
    assert s['last_run']['query_status']=='match' and s['last_run']['features_added']==1
    assert c.to_dict()==original


@pytest.mark.parametrize('mode',[None,'unknown',{'invalid':'mode'}])
def test_missing_or_unknown_mode_is_not_inferred_from_features_or_current_defaults(mode):
    c=construct();c.provenance['annotation_runs'][0]['annotation_mode']=mode
    c.features[0].qualifiers['ac_annotation_mode']=['default']
    assert annotation_summary(c)['last_run']['mode_label']=='Search mode not recorded'


@pytest.mark.parametrize('change',['DNA','topology'])
def test_changed_query_identifiers_are_exposed_without_removing_features(change):
    c=construct();saved=deepcopy(c.provenance)
    if change=='DNA':c.sequence='T'+c.sequence[1:]
    else:c.topology='linear'
    assert annotation_summary(c)['last_run']['query_status']=='changed'
    assert c.provenance==saved and len(c.features)==1


@pytest.mark.parametrize('missing',['sequence_sha256','topology'])
def test_incomplete_legacy_metadata_does_not_claim_a_full_query_match(missing):
    c=construct();c.provenance['annotation_runs'][0].pop(missing)
    assert annotation_summary(c)['last_run']['query_status']=='incomplete'


@pytest.mark.parametrize('history',[None,'invalid',[None,'invalid',4],[]])
def test_absent_or_malformed_history_does_not_hide_imported_annotations_or_break_figures(history):
    c=construct();c.provenance['annotation_runs']=history
    assert annotation_summary(c)['last_run'] is None
    assert len(build_pages(c))==1 and len(c.features)==1


def test_last_plannotate_entry_is_selected_without_assuming_other_tools_are_plannotate():
    c=construct();c.provenance['annotation_runs'].append({'engine':'Other tool','annotation_mode':'default'})
    assert annotation_summary(c)['recorded_runs']==1 and annotation_summary(c)['last_run']['mode']=='detailed'


def test_render_summary_recomputes_identity_instead_of_trusting_submitted_record_hash():
    c=construct();data=c.to_dict();data['sequence']='T'+data['sequence'][1:]
    response=create_app().test_client().post('/api/render',json={'record':data},headers={'X-AuraConstruct':'1'})
    assert response.status_code==200 and len(response.get_json()['pages'])==1
    assert response.get_json()['annotation_summary']['last_run']['query_status']=='changed'


def test_powerpoint_notes_keep_applied_mode_and_query_mismatch_with_raw_provenance():
    c=construct();c.topology='linear'
    with ZipFile(io.BytesIO(to_pptx(build_pages(c)))) as z:
        notes=ET.fromstring(z.read('ppt/notesSlides/notesSlide1.xml'))
        text=' '.join(e.text or '' for e in notes.findall(f'.//{{{A}}}t'))
        assert 'Include overlapping features' in text and 'differs from the recorded query' in text
        assert 'Construct provenance' in text and 'does not verify biological function' in text
