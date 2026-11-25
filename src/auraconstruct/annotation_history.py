"""Describe saved annotation history without changing it or validating biology."""
from __future__ import annotations

import hashlib
import re


def annotation_summary(construct):
    runs=construct.provenance.get('annotation_runs',[])
    runs=[r for r in runs if isinstance(r,dict) and r.get('engine')=='pLannotate'] if isinstance(runs,list) else []
    result={'recorded_runs':len(runs),'last_run':None,
            'note':'Saved run metadata describes predictions; it does not verify biological function.'}
    if not runs:return result
    run=runs[-1]
    def text(value):return value[:160] if isinstance(value,str) and value else None
    mode=run.get('annotation_mode')
    mode=mode if mode in ('default','detailed') else None
    mode_label={'default':'Default search','detailed':'Include overlapping features'}.get(mode,'Search mode not recorded')
    digest=run.get('sequence_sha256')
    sequence_status='not_recorded'
    if isinstance(digest,str) and re.fullmatch(r'[0-9a-fA-F]{64}',digest):
        sequence_status='match' if digest.lower()==hashlib.sha256(construct.sequence.encode()).hexdigest() else 'different'
    topology=run.get('topology')
    topology_status=('match' if topology==construct.topology else 'different') if topology in ('linear','circular') else 'not_recorded'
    states=(sequence_status,topology_status)
    if 'different' in states:
        status='changed';message='Current DNA or topology differs from the recorded query. Review these annotations before reuse.'
    elif states==('match','match'):
        status='match';message='Current DNA and topology match the saved query identifiers.'
    else:status='incomplete';message='Query identity is incomplete in the saved run metadata.'
    database=run.get('database_version');added=run.get('features_added')
    result['last_run']={'mode':mode,'mode_label':mode_label,'engine_version':text(run.get('version')),
        'database_version':text(str(database)) if isinstance(database,(str,int)) and not isinstance(database,bool) else None,
        'time_utc':text(run.get('time_utc')) or text(run.get('completed_utc')),
        'features_added':added if isinstance(added,int) and not isinstance(added,bool) and added>=0 else None,
        'sequence_status':sequence_status,'topology_status':topology_status,'query_status':status,'query_message':message}
    return result
