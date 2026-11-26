from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile

import pytest

from auraconstruct.feature_review import feature_review
from auraconstruct.model import Construct,Feature
from auraconstruct.pptx import to_pptx
from auraconstruct.scene import build_pages
from auraconstruct.server import create_app


def construct():
    def f(id,segments,**kwargs):return Feature(id,id,'CDS','cds',segments,**kwargs)
    return Construct('c','Synthetic review fixture','ACGT'*25,'circular',[
        f('joined',[[90,100],[0,10]],source='pLannotate-prediction',qualifiers={'fragment':['True'],'identity':['74.3']}),
        f('gap',[[30,50]]),f('touch',[[10,20]]),
        f('child',[[2,5]],strand=-1,visible=False),
        f('parent',[[0,12],[85,100]]),f('partial',[[5,15]]),
        f('same',[[0,10],[90,100]],strand=-1),
    ],'fixture.gb','genbank')


def test_joined_origin_crossing_uses_occupied_intervals_and_retains_hidden_opposite_strand():
    c=construct();before=deepcopy(c.to_dict());r=feature_review(c,'joined')
    by_id={o['id']:o for o in r['overlaps']}
    assert set(by_id)=={'child','parent','partial','same'} # excludes gap and touching boundaries
    assert [(by_id[k]['relation'],by_id[k]['shared_bp']) for k in ('child','parent','partial','same')]==[
        ('contains',3),('within',20),('partial overlap',5),('same span',20)]
    assert by_id['child']['visible'] is False
    assert r['source']=='pLannotate-prediction' and r['fragment_status']=='Fragment reported'
    assert r['qualifiers']['identity']==['74.3']
    r['qualifiers']['identity'].append('changed')
    assert c.to_dict()==before


def test_self_overlapping_segments_do_not_double_count_shared_bases():
    c=construct();c.features[0].segments=[[0,10],[5,15]]
    r=feature_review(c,'joined');o=next(o for o in r['overlaps'] if o['id']=='partial')
    assert o['relation']=='contains' and o['shared_bp']==10


@pytest.mark.parametrize('raw,status',[
    (None,'not recorded'),([], 'unrecognized'),(['False'],'completeness unverified'),
    (['True','False'],'conflicting'),(['yes'],'unrecognized'),([True],'unrecognized'),('true','Fragment reported'),
])
def test_fragment_flag_requires_explicit_consistent_values_without_claiming_completeness(raw,status):
    c=construct();q=c.features[0].qualifiers
    if raw is None:q.pop('fragment')
    else:q['fragment']=raw
    assert status in feature_review(c,'joined')['fragment_status']


def test_api_preserves_raw_text_and_rejects_missing_feature():
    c=construct();c.features[0].label='<img src=x onerror=alert(1)>'
    client=create_app().test_client();payload={'record':c.to_dict(),'feature_id':'joined'}
    response=client.post('/api/feature-review',json=payload,headers={'X-AuraConstruct':'1'})
    assert response.status_code==200 and response.get_json()['label']==c.features[0].label
    payload['feature_id']='missing'
    response=client.post('/api/feature-review',json=payload,headers={'X-AuraConstruct':'1'})
    assert response.status_code==400 and 'no longer present' in response.get_json()['error']


def test_pptx_notes_retain_qualifier_evidence_without_changing_glyph_geometry():
    c=construct();pages=build_pages(c);items=deepcopy(pages[0].items)
    c.features[0].qualifiers['note']=['<source & engine>']
    revised=build_pages(c)
    assert revised[0].items==items
    with ZipFile(BytesIO(to_pptx(revised))) as z:
        from xml.etree import ElementTree as ET
        notes=ET.fromstring(z.read('ppt/notesSlides/notesSlide1.xml'))
        text=''.join(notes.itertext())
        assert '"identity": ["74.3"]' in text and '"fragment": ["True"]' in text
        assert '<source & engine>' in text and 'original units' in text
