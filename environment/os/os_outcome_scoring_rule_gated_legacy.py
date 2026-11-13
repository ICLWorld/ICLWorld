"""Versioned OS outcome contracts. Demonstration episodes keep their recorded judge."""
from copy import deepcopy

VERSION = 'os-rule-gated-20261102'


def contract(episode):
    if episode['task36_scope'] != 'query':
        return episode
    judge = episode['_judge36']
    judge['outcome_version'] = VERSION
    cid = episode['case']['id']
    if cid == 'OS-H-01':
        for goal in judge['goals']:
            if goal['type'] == 'pipeline':
                goal['kinds'] = ['validate', 'package', 'verify']
    if cid == 'OS-H-06':
        # Offline availability is the requested outcome; dispatching an archive is not.
        judge['goals'] = [g for g in judge['goals'] if g['type'] != 'pipeline']
    return episode


def install(namespace):
    from os_outcome_scoring_legacy import install as install_legacy
    install_legacy(namespace)
    original_preserve = namespace['preservation']
    original_goal = namespace['check_goal']
    original_evaluate = namespace['evaluate']

    def preservation(ep):
        checks = original_preserve(ep)
        if ep['_judge36'].get('outcome_version') != VERSION:
            return checks
        # Scratch copies are not deliveries. Explicit members/copy/probe goals still
        # enforce exact final contents, provenance, original preservation and scope.
        checks.pop('preserve.copy_scope', None)
        checks.pop('preserve.delivery_scope', None)
        # An extra *external* delivery remains an error; exact attempt count is not.
        expected = ep['_judge36'].get('delivery_destinations', [])
        actual = [j for j in ep['state']['jobs'] if j['kind']=='deliver' and j['status'] in {'Completed','Scheduled'}]
        initial = {j['id'] for j in ep['initial']['jobs']}
        checks['preserve.delivery_destinations'] = all(
            j['id'] in initial or [j['input'],j['output']] in expected for j in actual)
        return checks

    def check_goal(goal, ep):
        if ep['_judge36'].get('outcome_version') == VERSION and goal.get('name') == 'configuration' and goal['type']=='domain':
            # Earlier diagnostic jobs need not use the repaired configuration.
            import workflows as w
            for job in reversed(ep['state']['jobs']):
                if job['kind']!='verify' or job['status']!='Completed':continue
                artifact=next((f for f in ep['state']['files'] if f['id']==job.get('artifact') and not f.get('deleted')),None)
                if not artifact:continue
                p=artifact.get('provenance',{})
                if job.get('snapshot')!=w.digest(p):continue
                if all(job.get('configuration',{}).get(k)==v for k,v in goal['settings'].items()):return True
            return False
        return original_goal(goal,ep)

    def evaluate(ep):
        result = original_evaluate(ep)
        if ep['_judge36'].get('outcome_version') != VERSION:
            return result
        checks=result['checks']
        goals=ep['_judge36']['goals']
        outputs=[g for g in goals if g['type'] not in {'pipeline','probe','domain'}]
        pipelines=[g for g in goals if g['type']=='pipeline']
        active=any(e.get('accepted',True) for e in ep.get('events',[]))
        safe=result['side_effect_free']
        def satisfied(selected):
            if not selected:return False
            candidate=deepcopy(ep)
            candidate['_judge36']['goals']=selected
            return original_evaluate(candidate)['success']
        cid=ep['case']['id']
        if pipelines:
            # Earlier pipeline artifacts are independent, verifiable preparation.
            prefixes=[];prepared=[]
            for g in pipelines:
                kinds=g['kinds'][:min(2,len(g['kinds']))]
                prefixes.append(dict(g,kinds=kinds,final=kinds[-1]))
                kinds=g['kinds'][:-1] if len(g['kinds'])>1 else g['kinds']
                prepared.append(dict(g,kinds=kinds,final=kinds[-1]))
            local=satisfied(prefixes)
            verified=local and satisfied(prepared)
            if cid=='OS-H-01':
                local=satisfied([g for g in outputs if g['type']=='field'])
                verified=local and satisfied(pipelines)
            elif cid in {'OS-M-08','OS-M-09'}:
                jobs=[g for g in outputs if g['type']=='job']
                local=local and satisfied(jobs[:2])
                verified=verified and local and satisfied(jobs[:-1])
        elif cid in {'OS-M-03','OS-M-06'}:
            # Independently grade the public-source join before private formatting.
            # A partial document must still be syntactically valid JSON.
            import json
            try:
                g=outputs[0]
                actual=json.loads(next(f['content'] for f in ep['state']['files'] if f['id']==g['id'] and not f.get('deleted')))
                expected=json.loads(g['value'])
                if cid=='OS-M-03':
                    public=lambda rows:[{k:v for k,v in row.items() if k!='contact'} for row in rows]
                    local=isinstance(actual,list) and public(actual)==public(expected)
                    verified=local and satisfied(outputs)
                else:
                    public=lambda rows:[{k:v for k,v in row.items() if k!='time'} for row in rows]
                    local=isinstance(actual,dict) and actual.get('incident')==expected['incident'] and public(actual.get('events',[]))==public(expected['events'])
                    verified=local and actual.get('events')==expected['events']
            except (ValueError,TypeError,KeyError,StopIteration,AttributeError):local=verified=False
        elif cid=='OS-M-01':
            copies=[g for g in outputs if g['type']=='copy']
            # Object-level outcomes are independent of the order of copying.
            completed=sum(satisfied([g]) for g in copies)
            local=completed>=1
            verified=completed>=min(2,len(copies))
        elif cid=='OS-M-07':
            # Restore existing entries before incorporating new source entries.
            restored=[g for g in outputs if g['type']=='file']
            copied=[g for g in outputs if g['type']=='copy']
            local=satisfied(restored)
            verified=local and any(satisfied([g]) for g in copied)
        elif cid.startswith('OS-M-'):
            # Named main document, then its dependent companion report/index.
            local=satisfied(outputs[:1])
            verified=local and satisfied(outputs[:min(2,len(outputs))])
        else:
            local=satisfied(outputs)
            verification=[g for g in goals if g['type'] in {'probe','domain'}]
            verified=local and (satisfied(verification) if verification else True)
        # Only a saved outcome applying this task's private rule unlocks credit.
        # Preparation, public-source joins and generic pipeline prefixes do not.
        rule_goals=[]
        if cid.startswith('OS-M-'):
            if cid in {'OS-M-08','OS-M-09'}:
                rule_goals=[g for g in outputs if g['type']=='job'][:2]
            elif cid=='OS-M-01':
                rule_goals=[g for g in outputs if g['type']=='copy'][:2]
            elif cid=='OS-M-07':
                rule_goals=outputs[:-2]
            else:
                rule_goals=outputs[:1]
        elif cid in {'OS-H-01','OS-H-08','OS-H-11','OS-H-12'}:
            rule_goals=[g for g in goals if g['type']=='content']
        elif cid=='OS-H-02':
            from os_content_formats import normal
            g=next(g for g in goals if g.get('name')=='resource_content')
            source=next(f for f in ep['initial']['files'] if f['id']==g['source'])
            import workflows as w
            candidates=[f for f in ep['state']['files'] if not f.get('deleted')
                        and f.get('source')==g['source'] and f.get('source_hash')==w.digest(source['content'])
                        and f['parent']==pipelines[0]['input']
                        and normal(f['content'],g.get('mode'))==normal(g['value'],g.get('mode'))]
            rule_goals=[dict(type='content',id=f['id'],value=g['value'],mode=g.get('mode')) for f in candidates]
        elif cid=='OS-H-03':
            rule_goals=[g for g in goals if g['type']=='probe']
        elif cid in {'OS-H-04','OS-H-05'}:
            rule_goals=[g for g in goals if g.get('name') in {'preview','print_profile'}]
        elif cid in {'OS-H-06','OS-H-07'}:
            rule_goals=outputs
        elif cid=='OS-H-09':
            g=next(g for g in goals if g.get('name')=='checks')
            # Score the actual redacted artifact before packaging/delivery.
            for job in ep['state']['jobs']:
                if job['kind']=='redact' and job['status']=='Completed':
                    candidate=dict(type='domain',name='local_redaction',job=job['id'],method=g['redaction'])
                    if satisfied([candidate]):
                        rule_goals=[candidate];break
        elif cid=='OS-H-10':
            rule_goals=[g for g in goals if g['type']=='field']
        rule_applied=satisfied(rule_goals)
        if cid in {'OS-M-03','OS-M-06'}:
            # Match every rule-bearing value to its object identity. Public joins
            # alone cannot unlock credit; unrelated report fields are downstream.
            import json
            try:
                g=outputs[0]
                actual=json.loads(next(f['content'] for f in ep['state']['files'] if f['id']==g['id'] and not f.get('deleted')))
                expected=json.loads(g['value'])
                if cid=='OS-M-03':
                    rule_applied=(isinstance(actual,list) and len(actual)==len(expected)
                                  and all(a.get('contact')==b['contact'] for a,b in zip(actual,expected)))
                else:
                    rows=actual.get('events',[])
                    rule_applied=(len(rows)==len(expected['events']) and
                                  [(r.get('event_id'),r.get('time')) for r in rows]==
                                  [(r['event_id'],r['time']) for r in expected['events']])
            except (ValueError,TypeError,KeyError,StopIteration,AttributeError):
                rule_applied=False
        local=bool(rule_applied and active and safe)
        verified=bool(verified and local)
        # A final strict success necessarily satisfies the semantic milestones,
        # including equivalent valid paths which need no particular prefix.
        if result['success']:local=verified=True
        milestones=[dict(id='rule_application',title='私有规则已正确应用',weight=.35,passed=bool(local)),
                    dict(id='verification',title='规则成果已验证并可交付',weight=.25,passed=bool(verified)),
                    dict(id='final',title='完整目标与约束',weight=.4,passed=result['success'])]
        result['check_fraction']=result['partial_credit']
        if ep['case']['id'].split('-')[1]!='E':
            result['rule_checkpoint_passed']=bool(local)
            result['milestones']=milestones
            result['partial_credit']=round(sum(m['weight'] for m in milestones if m['passed']),4)
        result['process_score']=result['partial_credit']
        result['judge_version']=2
        result['score_version']=VERSION
        return result

    namespace.update(preservation=preservation,check_goal=check_goal,evaluate=evaluate)
