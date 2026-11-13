"""Outcome milestones for newly generated environments; never rewrite old receipts."""
from copy import deepcopy

VERSION = 'outcome-milestones-20261102'


def web(initial, final, variant, events, result, evaluate):
    if initial.get('assessment_version') != VERSION:
        return result
    checks = result['checks']
    integrity = [c for c in checks if c['id'].startswith(('input:', 'unchanged:', 'delivery:source:'))]
    safe = all(c['passed'] for c in integrity)
    active = bool(events)
    # First milestone excludes delivery, but includes all business outcome predicates.
    business = [c for c in checks if not c['id'].startswith(('input:', 'unchanged:', 'delivery:', 'handoff:')) and c['id'] != 'activity']
    local = active and safe and bool(business) and all(c['passed'] for c in business)
    ready = False
    if initial.get('workset_delivery') and final.get('workset_delivery', {}).get('draft'):
        # Validate the saved document without demanding that it was already sent.
        # This is a private, side-effect-free check, never an agent operation.
        from vic_apps.workset_delivery import apply
        try:
            candidate = apply(deepcopy(final), 'assignment.publish')
            predicted = evaluate(initial, candidate, variant, events)
            delivery = [c for c in predicted['checks'] if c['id'].startswith('delivery:')]
            ready = local and bool(delivery) and all(c['passed'] for c in delivery)
        except (ValueError, KeyError, TypeError):
            pass
    elif initial.get('workset_delivery'):
        ready = False
    elif initial.get('cross_platform'):
        from vic_apps.cross_platform import resources
        ready = local and bool(resources(final))
    else:
        # Native workflow judges include save/check/provenance in local outcomes.
        ready = local
    if result['success']:
        # Equivalent successful paths need not expose a separately saved draft.
        local = ready = True
    milestones = [
        dict(id='application_result', title='应用内结果正确', weight=.35, passed=bool(local)),
        dict(id='deliverable_ready', title='可交付成果已保存并核验', weight=.25, passed=bool(ready)),
        dict(id='final', title='完整业务目标与约束', weight=.4, passed=bool(result['success'])),
    ]
    if initial.get('assessment_difficulty') in ('low', 'easy') or initial.get('generalization', {}).get('mode') == 'R':
        # Atomic task scores continue to reflect object-level completion.
        return dict(result, score_version=VERSION)
    score = round(sum(m['weight'] for m in milestones if m['passed']), 4)
    return dict(result, check_fraction=result['completion'], completion=score,
                process_score=score, milestones=milestones, score_version=VERSION)
