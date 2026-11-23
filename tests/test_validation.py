from copy import deepcopy
import hashlib
import json
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import pytest

from auraconstruct.model import Construct,Feature
from auraconstruct.pptx import P
from auraconstruct.sequence_io import to_genbank,read_bytes
from auraconstruct.validation import compare_annotations,validate_annotation


def construct(features,topology='circular'):
    return Construct('example','example','ACGT'*250,topology,features,'source.gb','genbank')


def feature(identifier,start,end,*,strand=1,label=None):
    return Feature(identifier,label or identifier,'CDS','cds',[[start,end]],strand)


def test_coordinate_agreement_uses_both_denominators_and_strand_not_label():
    source=construct([feature('a',100,200),feature('b',300,400)])
    predicted=construct([feature('x',103,200,label='renamed'),feature('y',300,400,strand=-1),feature('z',600,700,label='b')])
    report=compare_annotations(source,predicted)
    assert report['summary']['reference_eligible']==2 and report['summary']['prediction_eligible']==3
    assert report['summary']['reference_with_candidates']==report['summary']['prediction_with_candidates']==1
    pair=report['unambiguous_pairs'][0]
    assert pair['reference_overlap']==.97 and pair['prediction_overlap']==1 and not pair['exact_interval_coverage']
    assert [f['id'] for f in report['unmatched_reference_features']]==['b']
    assert [f['id'] for f in report['unmatched_prediction_features']]==['y','z']
    assert not compare_annotations(source,predicted,minimum_overlap=.99)['coordinate_candidates']


def test_circular_joins_and_overlapping_segments_use_interval_unions():
    f=feature('seam',900,1000,strand=-1);f.segments=[[900,1000],[0,100]];f.segment_strands=[-1,-1]
    g=deepcopy(f);g.id='prediction'
    report=compare_annotations(construct([f]),construct([g]))
    assert report['coordinate_candidates'][0]['intersection_bp']==200
    assert report['summary']['exact_unambiguous_pairs']==1
    assert report['reference_features'][0]['segments']==[[900,1000],[0,100]]
    f.segments=[[0,20],[10,30]];f.segment_strands=[-1,-1]
    g.segments=[[0,30]];g.segment_strands=[-1]
    assert compare_annotations(construct([f]),construct([g]))['coordinate_candidates'][0]['intersection_bp']==30


def test_duplicate_source_annotations_remain_ambiguous_instead_of_being_counted_as_unique_matches():
    source=construct([feature('a',100,200),feature('b',100,200)])
    report=compare_annotations(source,construct([feature('p',100,200)]))
    assert report['summary']['reference_with_candidates']==2 and report['summary']['prediction_with_candidates']==1
    assert report['summary']['unambiguous_pairs']==0
    assert report['summary']['ambiguous_prediction_indices']==[0]


def test_uncertain_boundaries_and_strands_are_explicitly_excluded_and_empty_denominators_stay_zero():
    fuzzy=feature('fuzzy',10,30);fuzzy.fuzzy=True
    mixed=feature('mixed',50,70);mixed.segment_strands=[-1]
    source=construct([fuzzy,mixed,feature('unknown',100,130,strand=0)])
    report=compare_annotations(source,construct([]))
    assert not report['assessment_available'] and 'cannot be assessed' in report['assessment_note']
    assert report['summary']['reference_total']==3 and report['summary']['reference_eligible']==0
    assert len([f for f in report['reference_features'] if f['excluded_reason']])==3
    assert report['summary']['unambiguous_pairs']==0 and not report['unmatched_reference_features']


@pytest.mark.parametrize('change',['DNA','topology'])
def test_comparison_rejects_changed_sequence_or_framing(change):
    a=construct([]);b=deepcopy(a)
    if change=='DNA':b.sequence='T'+b.sequence[1:]
    else:b.topology='linear'
    with pytest.raises(ValueError,match='identical DNA and topology'):compare_annotations(a,b)


@pytest.mark.parametrize('annotation_mode',['default','detailed'])
def test_validation_withholds_annotations_and_saves_checksummed_native_exports(tmp_path,monkeypatch,annotation_mode):
    source=construct([feature('source-a',10,40),feature('source-b',100,130)])
    source.provenance={'private_source_note':'not engine input'}
    raw=to_genbank(source);path=tmp_path/'source.gb';path.write_bytes(raw)
    def fake(query,*,mode):
        assert mode==annotation_mode
        assert query.features==[] and query.provenance=={} and query.sequence==source.sequence
        result=deepcopy(query);result.features=[feature('predicted',10,40,label='Different label')]
        result.features[0].source='pLannotate-prediction';return result
    monkeypatch.setattr('auraconstruct.validation.plannotate',fake)
    output=tmp_path/'run';report=validate_annotation(path,output,annotation_mode=annotation_mode)
    assert report['status']=='completed' and report['withheld_features']==2 and report['engine_input_features']==0
    assert report['source_feature_types']=={'CDS':2} and report['comparison']['assessment_available']
    assert report['annotation_mode']==annotation_mode
    assert report['sequence_unchanged'] and report['comparison']['summary']['unambiguous_pairs']==1
    assert (output/'source-input.bin').read_bytes()==raw
    query=read_bytes((output/'query.fa').read_bytes(),'query.fa')[0];assert not query.features and query.sequence==source.sequence
    for name,digest in report['artifact_sha256'].items():assert hashlib.sha256((output/name).read_bytes()).hexdigest()==digest
    with ZipFile(output/'figure.pptx') as z:
        root=ET.fromstring(z.read('ppt/slides/slide1.xml'))
        assert len(root.findall(f'.//{{{P}}}grpSp'))==1
    with pytest.raises(FileExistsError):validate_annotation(path,output)


def test_failed_engine_run_is_recorded_without_a_completed_figure(tmp_path,monkeypatch):
    path=tmp_path/'source.gb';path.write_bytes(to_genbank(construct([feature('a',10,40)])))
    def fail(query,*,mode):raise ValueError('Search tool failed')
    monkeypatch.setattr('auraconstruct.validation.plannotate',fail)
    output=tmp_path/'failed'
    with pytest.raises(ValueError,match='Search tool failed'):validate_annotation(path,output)
    report=json.loads((output/'report.json').read_text())
    assert report['status']=='failed' and report['error']=='Search tool failed' and report['finished_utc']
    assert not (output/'figure.pptx').exists()


def test_validation_cli_requires_explicit_topology_for_unknown_inputs(tmp_path,monkeypatch,capsys):
    from auraconstruct.cli import main
    path=tmp_path/'query.fa';path.write_text('>example\n'+'ACGT'*30+'\n')
    monkeypatch.setattr('sys.argv',['auraconstruct','validate-annotation',str(path),'-o',str(tmp_path/'run')])
    with pytest.raises(SystemExit) as exc:main()
    assert exc.value.code==2 and 'Set linear or circular topology' in capsys.readouterr().err


def test_validation_cli_passes_annotation_mode(tmp_path,monkeypatch,capsys):
    from auraconstruct.cli import main
    def fake(input_path,output,**kwargs):
        assert kwargs['annotation_mode']=='detailed'
        return {'status':'completed','predictions':0,'comparison':{'assessment_available':False,'assessment_note':'No source features','summary':{}}}
    monkeypatch.setattr('auraconstruct.validation.validate_annotation',fake)
    monkeypatch.setattr('sys.argv',['auraconstruct','validate-annotation','source.gb','-o',str(tmp_path/'run'),'--annotation-mode','detailed'])
    main();assert json.loads(capsys.readouterr().out)['status']=='completed'


def test_export_rejects_annotation_mode_without_an_annotation_request(tmp_path,monkeypatch,capsys):
    from auraconstruct.cli import main
    monkeypatch.setattr('sys.argv',['auraconstruct','export','source.gb','-o',str(tmp_path/'figure.pptx'),'--annotation-mode','detailed'])
    with pytest.raises(SystemExit) as exc:main()
    assert exc.value.code==2 and 'requires --annotate plannotate' in capsys.readouterr().err
    assert not (tmp_path/'figure.pptx').exists()
