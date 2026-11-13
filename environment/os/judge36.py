"""Trusted, state-based judges for the 36-task catalogue.

Contracts are created by the trusted fixture generator, never by HTTP callers.
No reference actions or UI coordinates are used to score a state.
"""
import json
from collections import Counter


def _file(state, identifier):
    return next(f for f in state['files'] if f['id'] == identifier and not f.get('deleted'))


from os_content_formats import normal as _normal

def check_goal(goal, episode):
    import workflows as w
    state = episode['state']
    kind = goal['type']
    if kind == 'field':
        if goal['collection'] == 'settings':
            actual = state['settings'][goal['id']]
        else:
            item = next(x for x in state[goal['collection']] if x['id']==goal['id'])
            actual = item[goal['field']]
        return actual == goal['value']
    if kind == 'file':
        f = next(x for x in state['files'] if x['id']==goal['id']) if goal['fields'].get('deleted') else _file(state,goal['id'])
        return all(f.get(k)==v for k,v in goal['fields'].items())
    if kind == 'content':
        f = _file(state,goal['id'])
        return _normal(f['content'],goal.get('mode')) == _normal(goal['value'],goal.get('mode'))
    if kind == 'copy':
        candidates = [f for f in state['files'] if not f.get('deleted') and f['parent']==goal['parent'] and f['name']==goal['name']]
        if len(candidates)!=1:
            return False
        f=candidates[0]
        source=_file(episode['initial'],goal['source'])
        return f.get('source')==source.get('source',source['id']) and f.get('source_hash')==w.digest(source['content']) and f['content']==goal.get('content',source['content'])
    if kind == 'folder':
        folder=w.resolve_folder(state,goal['path'])
        return _file(state,folder)['kind']=='folder'
    if kind == 'members':
        actual=[f['name'] for f in state['files'] if not f.get('deleted') and f['parent']==goal['parent'] and f['kind']!='folder']
        return sorted(actual)==sorted(goal['names'])
    if kind == 'export':
        initial=_file(episode['initial'],goal['source'])
        rows=[json.loads(x) for x in initial['content'].splitlines() if x]
        expected=[r for r in rows if goal['start']<=r['time']<=goal['end']]
        found=[f for f in state['files'] if not f.get('deleted') and f['parent']==goal['parent'] and f['name']==goal['name']]
        return len(found)==1 and found[0].get('source')==initial['id'] and _normal(found[0]['content'],'jsonl')==expected and any(
            e['file']==found[0]['id'] and e['source']==initial['id'] and e['start']==goal['start'] and e['end']==goal['end'] for e in state.get('log_exports',[]))
    if kind == 'job':
        jobs=[j for j in state['jobs'] if j['name']==goal['name']]
        return len(jobs)==1 and all(jobs[0].get(k)==v for k,v in goal['fields'].items())
    if kind == 'pipeline':
        finals=[j for j in state['jobs'] if j['kind']==goal['final'] and j['status'] in {'Completed','Scheduled'} and j['input']==goal['input']]
        for final in finals:
            chain=[]; current=final; seen=set(); valid=True
            while current:
                if current['id'] in seen:
                    valid=False;break
                seen.add(current['id']);chain.append(current)
                artifact=_file(state,current['artifact']); p=artifact.get('provenance',{})
                if artifact['content']!=json.dumps(p,indent=2) or current.get('snapshot')!=w.digest(p):
                    valid=False;break
                if any(w.digest(_file(state,k)['content'])!=v for k,v in p.get('hashes',{}).items()):
                    valid=False;break
                dependency=next((j for j in state['jobs'] if j['name']==current['dependency']),None)
                if current['dependency'] and (dependency is None or dependency['status']!='Completed' or p.get('dependency_artifact')!=dependency['artifact']):
                    valid=False;break
                current=dependency
            kinds=[j['kind'] for j in reversed(chain)]
            pos=0
            for k in kinds:
                if pos<len(goal['kinds']) and goal['kinds'][pos]==k:pos+=1
            if valid and pos==len(goal['kinds']):
                return True
        return False
    if kind == 'probe':
        for receipt in state.get('receipts',[]):
            if receipt['kind']!=goal['kind'] or receipt['target']!=goal['target']:continue
            actual={f['id']:w.digest(f['content']) for f in state['files'] if not f.get('deleted') and f['parent']==receipt['target'] and f['kind']!='folder'}
            if receipt['files']!=actual:continue
            candidate=__import__('copy').deepcopy(state)
            outcome=w.domain_checks.probe(candidate,{'kind':goal['kind'],'target':goal['target']},w.get_file,w.path,w.digest)
            if outcome['result']==receipt['result']:return True
        return False
    if kind == 'domain':
        return _domain(goal,episode)
    raise ValueError('Unknown trusted predicate: '+kind)


def _domain(goal,episode):
    import workflows as w
    import domain_checks as d
    s=episode['state']; initial=episode['initial']; name=goal['name']
    if name == 'old_content':
        return any(not f.get('deleted') and f['content']==goal['content'] and (f['id']==goal['id'] or f.get('source')==goal['id']) for f in s['files'])
    if name == 'preview':
        expected=w.preview_dimensions(goal['preset'])
        previews=[f for f in s['files'] if not f.get('deleted') and f.get('source') in {'source-0','source-1'} and f.get('generated_by')]
        parsed=[]
        for f in previews:
            try:p=json.loads(f['content'])
            except ValueError:continue
            if p.get('virtual_preview'):parsed.append(p)
        source_clips={json.loads(_file(initial,f'source-{i}')['content'])['clip_id']:w.digest(_file(initial,f'source-{i}')['content']) for i in [0,1]}
        captions={x['clip_id']:x['text'] for x in json.loads(_file(initial,'source-2')['content'])['captions'] if x['clip_id'] in source_clips}
        return len(parsed)==2 and all((p['width'],p['height'])==expected and p['source_hash']==source_clips.get(p['clip_id']) and p['caption']==captions.get(p['clip_id']) for p in parsed) and {p['clip_id'] for p in parsed}==set(source_clips)
    if name == 'print_profile':
        expected=goal['profile']
        jobs=[j for j in s['jobs'] if j['kind']=='proof' and j['status']=='Completed']
        for j in jobs:
            f=_file(s,j['artifact']);p=f['provenance'];profile=p['processing']
            if f['content']!=json.dumps(p,indent=2) or w.digest(p)!=j['snapshot']:continue
            if any(w.digest(_file(s,k)['content'])!=v for k,v in p['hashes'].items()):continue
            if not profile.get('proof_passed') or not all(profile.get(k)==v for k,v in expected.items()):continue
            layout=next(x for x in s['jobs'] if x['name']==j['dependency'])
            pages=_file(s,layout['artifact'])['provenance']['processing']['pages']
            printer=next(x for x in s['devices'] if x['id']==profile['printer'])
            if pages and all(page['lines']<=printer.get('page_line_limit',40) for page in pages):return True
        return False
    if name == 'resource_content':
        deliver=next(j for j in reversed(s['jobs']) if j['kind']=='deliver' and j['status'] in {'Completed','Scheduled'})
        records=_file(s,deliver['artifact'])['provenance']['resources']
        matching=[r for r in records if r.get('source')==goal['source']]
        return len(matching)==1 and _normal(matching[0]['content'],goal.get('mode'))==_normal(goal['value'],goal.get('mode'))
    if name == 'print_submission':
        queues=[q for q in s.get('print_queue',[]) if q['status'] in {'Queued','Paused'} and q['id'] not in goal.get('exclude',[])]
        if len(queues)!=1:return False
        q=queues[0]; p=_file(s,q['proof_artifact'])
        if any(q.get(k)!=v for k,v in goal.get('profile',{}).items()):return False
        if w.digest(p['content'])!=q['proof_sha256']:return False
        profile=p['provenance']['processing']
        if any(q[k]!=profile[k] for k in ['printer','paper','duplex','order']):return False
        payload={k:q[k] for k in ['printer','paper','duplex','order','pages','documents']}
        if w.digest(payload)!=q['payload_sha256']:return False
        expected=[{'name':f['name'],'content':f['content'],'source':f['source']} for f in s['files'] if not f.get('deleted') and f['parent']==goal['input'] and f.get('source','').startswith('source-')]
        delivery=_file(s,q['delivery_artifact'])['provenance']['processing']
        return bool(expected) and sorted(q['documents'],key=lambda r:r['source'])==sorted(expected,key=lambda r:r['source']) and delivery['payload_sha256']==q['payload_sha256'] and delivery['print_job']==q['id'] and all(w.digest(_file(s,fid)['content'])==v for fid,v in p['provenance']['hashes'].items())
    if name == 'configuration':
        jobs=[j for j in s['jobs'] if j['status']=='Completed' and j['id'] not in {x['id'] for x in initial['jobs']}]
        return bool(jobs) and all(all(j.get('configuration',{}).get(k)==v for k,v in goal['settings'].items()) for j in jobs)
    if name == 'signature':
        import hmac,hashlib
        job=next(j for j in s['jobs'] if j['id']==goal['job'] and j['status']=='Completed')
        details=_file(s,job['artifact'])['provenance']['processing']
        signed=_file(s,details['signed_artifact'])
        expected=hmac.new(b'OS-ICL virtual signing authority',signed['content'].encode(),hashlib.sha256).hexdigest()
        return hmac.compare_digest(details['signature'],expected)
    if name == 'local_redaction':
        job=next(j for j in s['jobs'] if j['id']==goal['job'] and j['status']=='Completed')
        artifact=_file(s,job['artifact']);p=artifact['provenance'];folder=p['processing']['redacted_folder']
        expected=[]
        for identifier in ['source-0','source-1']:
            for row in map(json.loads,_file(initial,identifier)['content'].splitlines()):
                if initial['incident']['start']<=row['time']<=initial['incident']['end']:
                    expected.append(d.redact_record(row,initial['sensitive_fields'],goal['method']))
        actual=[]
        for f in s['files']:
            if not f.get('deleted') and f['parent']==folder:actual.extend(map(json.loads,f['content'].splitlines()))
        return p['processing']['method']==goal['method'] and sorted(actual,key=lambda r:r['event_id'])==sorted(expected,key=lambda r:r['event_id'])
    if name == 'checks':
        checks=d.checks(s,initial,episode['case'],w.get_file,w.digest,w.media_catalogue,goal.get('redaction','mask'))
        return bool(goal['keys']) and all(checks.get(k,False) for k in goal['keys'])
    raise ValueError('Unknown domain predicate: '+name)


def preservation(episode):
    """Check initial business entities, with narrowly declared writable fields."""
    initial,state=episode['initial'],episode['state']; contract=episode['_judge36']
    writable=contract.get('writable',{})
    checks={}
    for collection in ['files','jobs','devices','processes','print_queue','transfers']:
        for before in initial.get(collection,[]):
            identifier=before['id']; allowed=set(writable.get(collection,{}).get(identifier,[]))
            after=next((x for x in state.get(collection,[]) if x['id']==identifier),None)
            checks[f'preserve.{collection}.{identifier}']=after is not None and all(after.get(k)==v for k,v in before.items() if k not in allowed)
    allowed_settings=set(writable.get('settings',[]))
    for k,v in initial['settings'].items():
        if k not in allowed_settings:checks['preserve.setting.'+k]=state['settings'].get(k)==v
    initial_ids={f['id'] for f in initial['files']}
    actual=Counter(f['source'] for f in state['files'] if not f.get('deleted') and f['id'] not in initial_ids and f.get('source') and not f.get('generated_by'))
    checks['preserve.copy_scope']=dict(actual)==contract.get('copy_sources',{})
    checks['preserve.delivery_scope']=sum(j['kind']=='deliver' and j['status'] in {'Completed','Scheduled'} for j in state['jobs'])==contract.get('active_deliveries',0)
    return checks


def evaluate(episode):
    checks={}
    for i,g in enumerate(episode['_judge36']['goals']):
        try:
            # Resolve created entities by their saved business location/name,
            # so harmless changes in creation order do not change the answer.
            resolved=__import__('copy').deepcopy(g)
            for key in ['id','parent','input','target','job']:
                identifier=resolved.get(key);selector=episode['_judge36'].get('selectors',{}).get(identifier)
                if selector:
                    if 'path' in selector:
                        import workflows as w
                        resolved[key]=next(f['id'] for f in episode['state']['files'] if not f.get('deleted') and w.path(episode['state'],f['id'])==selector['path'])
                    else:
                        resolved[key]=next(j['id'] for j in episode['state']['jobs'] if j['name']==selector['job_name'] and j['kind']==selector['job_kind'])
            checks[g.get('label',f'result.{i:03}')]=bool(check_goal(resolved,episode))
        except (ValueError,KeyError,TypeError,StopIteration,IndexError):checks[g.get('label',f'result.{i:03}')]=False
    checks.update(preservation(episode))
    success=bool(checks) and all(checks.values())
    return {'success':success,'goal_success':success,'rule_compliance':all(v for k,v in checks.items() if not k.startswith('preserve.')),
            'side_effect_free':all(v for k,v in checks.items() if k.startswith('preserve.')),
            'checks':checks,'failed_checks':[k for k,v in checks.items() if not v],
            'partial_credit':round(sum(checks.values())/max(1,len(checks)),4),
            'benchmark_version':episode['benchmark_version'],'catalogue_version':'36.1-dev',
            'scope':episode['task36_scope'],'judge_version':1}

from os_outcome_scoring import install as _install_outcomes
_install_outcomes(globals())
