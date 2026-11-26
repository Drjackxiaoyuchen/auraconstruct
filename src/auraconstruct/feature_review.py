"""Read-only feature evidence and geometric overlaps, without biological inference."""
from copy import deepcopy


def _intervals(feature):
    result=[]
    for a,b in sorted(feature.segments):
        if result and a<=result[-1][1]:result[-1][1]=max(b,result[-1][1])
        else:result.append([a,b])
    return result


def feature_review(construct,feature_id):
    feature=next((f for f in construct.features if f.id==feature_id),None)
    if feature is None:raise ValueError('The selected feature is no longer present.')
    intervals=_intervals(feature);length=sum(b-a for a,b in intervals)
    overlaps=[]
    for other in construct.features:
        if other.id==feature.id:continue
        spans=_intervals(other);other_length=sum(b-a for a,b in spans)
        shared=sum(max(0,min(b,d)-max(a,c)) for a,b in intervals for c,d in spans)
        if not shared:continue
        relation=('same span' if shared==length==other_length else
                  'within' if shared==length else 'contains' if shared==other_length else 'partial overlap')
        overlaps.append({'id':other.id,'label':other.label,'type':other.type,'source':other.source,
                         'visible':other.visible,'relation':relation,'shared_bp':shared})
    raw=feature.qualifiers.get('fragment')
    flags=raw if isinstance(raw,list) else [raw]
    # Only explicit, consistent boolean strings have meaning here. Missing, empty,
    # conflicting or unfamiliar qualifiers never establish a complete feature.
    normalized=[v.strip().lower() if isinstance(v,str) else None for v in flags]
    fragment=('Fragment reported' if normalized and all(v=='true' for v in normalized) else
              'Fragment not reported by this flag; completeness unverified' if normalized and all(v=='false' for v in normalized) else
              'Fragment status not recorded' if raw is None else 'Fragment flag unrecognized or conflicting')
    return {'id':feature.id,'label':feature.label,'type':feature.type,'source':feature.source,
            'role':feature.role,'role_source':feature.role_source,'fragment_status':fragment,
            'qualifiers':deepcopy(feature.qualifiers),'overlaps':overlaps,
            'note':'Overlaps compare occupied sequence intervals on either strand, including hidden features. '
                   'They do not establish biological relationships. Qualifier values are source or engine claims; '
                   'scores retain their original units and are not measures of biological function.'}
