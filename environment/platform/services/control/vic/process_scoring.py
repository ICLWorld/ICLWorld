"""Outcome milestones for newly generated environments; never rewrite old receipts."""

VERSION = 'single-rule-checkpoint-20261102'


def web(initial, final, variant, events, result, evaluate):
    if initial.get('assessment_version') != VERSION:
        from .process_scoring_rule_gated_legacy import web as legacy
        return legacy(initial, final, variant, events, result, evaluate)
    checks = result['checks']
    integrity = [c for c in checks if c['id'].startswith(('input:', 'unchanged:', 'delivery:source:'))]
    safe = all(c['passed'] for c in integrity)
    active = bool(events)
    # First milestone excludes delivery, but includes all business outcome predicates.
    business = [c for c in checks if not c['id'].startswith(('input:', 'unchanged:', 'delivery:', 'handoff:')) and c['id'] != 'activity']
    local = active and safe and bool(business) and all(c['passed'] for c in business)
    if result['success']:
        # Equivalent successful paths need not expose a separately saved draft.
        local = True
    milestones = [dict(id='rule_application', title='私有规则已正确应用', weight=.4, passed=bool(local))]
    if initial.get('assessment_difficulty') in ('low', 'easy') or initial.get('generalization', {}).get('mode') == 'R':
        # Atomic task scores continue to reflect object-level completion.
        return dict(result, score_version=VERSION)
    score = 1.0 if result['success'] else (.4 if local else 0.0)
    return dict(result, check_fraction=result['completion'], completion=score,
                process_score=score, rule_checkpoint_passed=bool(local), milestones=milestones, score_version=VERSION)
