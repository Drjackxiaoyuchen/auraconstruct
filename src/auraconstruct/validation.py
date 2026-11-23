"""Local, annotation-withheld runs and explicitly limited coordinate comparisons."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import monotonic

from .annotate import plannotate
from .model import Construct
from .pptx import to_pptx
from .scene import build_pages, to_svg
from .sequence_io import read_bytes, to_genbank


def _intervals(feature):
    merged=[]
    for a,b in sorted(feature.segments):
        if b<=a:raise ValueError('Comparison requires nonempty feature intervals.')
        if merged and a<=merged[-1][1]:merged[-1][1]=max(b,merged[-1][1])
        else:merged.append([a,b])
    return merged


def _features(construct,kind):
    rows=[]
    for index,f in enumerate(construct.features):
        if f.type!=kind:continue
        reason=('fuzzy boundaries' if f.fuzzy else
                'unknown or mixed strand' if f.strand not in (-1,1) or
                any(s!=f.strand for s in f.segment_strands) else None)
        rows.append({'index':index,'id':f.id,'label':f.label,'segments':deepcopy(f.segments),
                     'strand':f.strand,'excluded_reason':reason,'intervals':_intervals(f)})
    return rows


def _check_options(feature_type,minimum_overlap):
    if not 0<minimum_overlap<=1:raise ValueError('Minimum reciprocal overlap must be greater than 0 and at most 1.')
    if not feature_type:raise ValueError('Choose a GenBank feature type to compare.')


def compare_annotations(reference,predicted,feature_type='CDS',minimum_overlap=.9):
    """Compare same-type, known-strand interval coverage, without claiming accuracy."""
    if reference.sequence!=predicted.sequence or reference.topology!=predicted.topology:
        raise ValueError('Comparison requires identical DNA and topology; no rotation or realignment is performed.')
    _check_options(feature_type,minimum_overlap)
    refs=_features(reference,feature_type);preds=_features(predicted,feature_type)
    eligible_refs=[f for f in refs if not f['excluded_reason']]
    eligible_preds=[f for f in preds if not f['excluded_reason']]
    if len(eligible_refs)*len(eligible_preds)>1_000_000:
        raise ValueError('Comparison exceeds one million feature pairs; select a narrower feature type.')
    pairs=[]
    for r in eligible_refs:
        for p in eligible_preds:
            if r['strand']!=p['strand']:continue
            shared=sum(max(0,min(b,d)-max(a,c)) for a,b in r['intervals'] for c,d in p['intervals'])
            nr=sum(b-a for a,b in r['intervals']);np=sum(b-a for a,b in p['intervals'])
            if shared/nr>=minimum_overlap and shared/np>=minimum_overlap:
                pairs.append({'reference_index':r['index'],'prediction_index':p['index'],
                              'intersection_bp':shared,'reference_overlap':shared/nr,'prediction_overlap':shared/np,
                              'exact_interval_coverage':r['intervals']==p['intervals']})
    rc=Counter(p['reference_index'] for p in pairs);pc=Counter(p['prediction_index'] for p in pairs)
    # Do not silently assign duplicate/overlapping annotations to a single best-looking pair.
    unique=[p for p in pairs if rc[p['reference_index']]==pc[p['prediction_index']]==1]
    return {'feature_type':feature_type,'minimum_reciprocal_overlap':minimum_overlap,
            'assessment_available':bool(eligible_refs),
            'assessment_note':('Coordinate candidates require review; this is not an accuracy estimate.' if eligible_refs else
                               'No eligible reference features of this GenBank type; coordinate agreement cannot be assessed.'),
            'coordinate_system':'0-based half-open; original ordered segments retained',
            'reference_features':refs,'prediction_features':preds,'coordinate_candidates':pairs,
            'unambiguous_pairs':unique,
            'unmatched_reference_features':[r for r in eligible_refs if r['index'] not in rc],
            'unmatched_prediction_features':[p for p in eligible_preds if p['index'] not in pc],
            'summary':{'reference_total':len(refs),'prediction_total':len(preds),
                       'reference_eligible':len(eligible_refs),'prediction_eligible':len(eligible_preds),
                       'reference_with_candidates':len(rc),'prediction_with_candidates':len(pc),
                       'unambiguous_pairs':len(unique),'exact_unambiguous_pairs':sum(p['exact_interval_coverage'] for p in unique),
                       'ambiguous_reference_indices':sorted(i for i,n in rc.items() if n>1),
                       'ambiguous_prediction_indices':sorted(i for i,n in pc.items() if n>1)},
            'interpretation':'Coordinate agreement only. Names are not matching criteria. Counts are features, not genes or verified functions. '
                             'Deposited annotations may be incomplete or wrong; unmatched predictions are not established false positives. '
                             'Fuzzy/unknown/mixed-strand features are excluded from agreement counts. Duplicates and ambiguous overlaps remain explicit.'}


def validate_annotation(input_path,output_dir,*,topology=None,feature_type='CDS',minimum_overlap=.9,annotation_mode='default'):
    """Run pLannotate on DNA alone; retain the original for comparison only afterwards."""
    input_path=Path(input_path);output_dir=Path(output_dir)
    raw=input_path.read_bytes();records=read_bytes(raw,input_path.name)
    if len(records)!=1:raise ValueError('Validation requires exactly one sequence record per input file.')
    reference=records[0]
    if topology:reference.topology=topology
    if reference.topology not in ('linear','circular'):raise ValueError('Set linear or circular topology before validation.')
    # Validate comparison options before starting a potentially long search.
    _check_options(feature_type,minimum_overlap)
    if annotation_mode not in ('default','detailed'):raise ValueError('Unknown annotation mode: '+str(annotation_mode))
    output_dir.mkdir(parents=True,exist_ok=False)
    query=Construct(reference.id,reference.name,reference.sequence,reference.topology,[],input_path.name,'fasta')
    report={'schema_version':1,'status':'running','started_utc':datetime.now(timezone.utc).isoformat(),
            'input_name':input_path.name,'input_raw_sha256':hashlib.sha256(raw).hexdigest(),
            'sequence_sha256':hashlib.sha256(query.sequence.encode()).hexdigest(),'length':query.length,
            'topology':query.topology,'withheld_features':len(reference.features),'engine_input_features':0,
            'annotation_mode':annotation_mode}
    report['source_feature_types']=dict(Counter(f.type for f in reference.features))
    report_path=output_dir/'report.json'
    def save():report_path.write_text(json.dumps(report,indent=2))
    save();started=monotonic()
    try:
        (output_dir/'source-input.bin').write_bytes(raw)
        (output_dir/'query.fa').write_text('>query\n'+query.sequence+'\n')
        predicted=plannotate(query,mode=annotation_mode)
        comparison=compare_annotations(reference,predicted,feature_type,minimum_overlap)
        pages=build_pages(predicted,layout='singleline',palette='aureka',coordinates=True,detail='detailed')
        if len(pages)!=1:raise ValueError('Single-line validation export did not produce exactly one figure page.')
        (output_dir/'predicted.gb').write_bytes(to_genbank(predicted))
        (output_dir/'predicted.json').write_text(json.dumps(predicted.to_dict(),indent=2))
        (output_dir/'figure.pptx').write_bytes(to_pptx(pages))
        (output_dir/'figure.svg').write_text(to_svg(pages[0]))
        report.update(status='completed',sequence_unchanged=predicted.sequence==reference.sequence,
                      predictions=len(predicted.features),figure_pages=len(pages),
                      predicted_feature_types=dict(Counter(f.type for f in predicted.features)),
                      annotation_runs=predicted.provenance.get('annotation_runs',[]),comparison=comparison,
                      artifact_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in sorted(output_dir.iterdir()) if p.name!='report.json' and p.is_file()})
    except Exception as exc:
        report.update(status='failed',error=str(exc),error_type=type(exc).__name__);raise
    finally:
        report.update(seconds=round(monotonic()-started,3),finished_utc=datetime.now(timezone.utc).isoformat());save()
    return report
