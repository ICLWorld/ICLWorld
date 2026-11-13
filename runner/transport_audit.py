"""Conservative, reproducible transport-timeout audit; never changes raw grades."""
import collections
import datetime
import hashlib
import json
from pathlib import Path

POLICY = 'network-timeout-v1'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_timeout(directory, result):
    directory = Path(directory)
    report = dict(policy=POLICY, confirmed=False, intervals=[])
    if not result.get('timed_out') or result.get('agent_finished') or result.get('outcome') in ('evaluation_error', 'environment_error'):
        return report
    if (result.get('evaluation') or {}).get('success'):
        return report
    errors = result.get('errors', [])
    if sum('waiting for network' in str(e) for e in errors) < 3:
        return report
    logs = sorted(directory.glob('stdout-*.jsonl'), key=lambda p:int(p.stem.split('-')[-1]))
    if len(logs) != 1:
        report['reason'] = 'multiple_or_missing_native_streams'
        return report
    calls, waits = [], collections.Counter()
    for line in logs[0].open():
        e = json.loads(line)
        item = e.get('item', {})
        if e.get('type') == 'item.completed' and item.get('type') == 'mcp_tool_call':
            calls.append((item.get('tool'), item.get('arguments')))
        if e.get('type') == 'error' and 'waiting for network' in str(e.get('message', '')):
            waits[len(calls)] += 1
    session = result.get('session_id')
    rollouts = list((directory/'profile/sessions').rglob(f'*{session}*.jsonl')) if session else []
    if len(rollouts) != 1:
        report['reason'] = 'missing_or_ambiguous_rollout'
        return report
    times, recorded = [], []
    for line in rollouts[0].open():
        e = json.loads(line); payload = e.get('payload', {}); item = payload.get('item', {})
        if e.get('type') == 'event_msg' and payload.get('type') == 'item_completed' and item.get('type') == 'McpToolCall':
            recorded.append((item.get('tool'), item.get('arguments')))
            times.append(datetime.datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00')).timestamp())
    if calls != recorded:
        report['reason'] = 'native_stream_rollout_mismatch'
        return report
    config = json.loads((directory/'computer-private.json').read_text())
    end = config['deadline_unix']; budget = config['timeout_seconds']; start = end-budget
    if budget != 3600 or times != sorted(times) or any(t < start-2 or t > end+5 for t in times):
        report['reason'] = 'invalid_timeline'
        return report
    bounds = [start] + times + [end]
    for index, count in sorted(waits.items()):
        gap = bounds[index+1]-bounds[index]
        if count >= 3 and gap >= 600:
            report['intervals'].append(dict(start=bounds[index], end=bounds[index+1],
                tool_progress_gap_seconds=round(gap,3), native_network_wait_events=count))
    report['confirmed'] = bool(report['intervals'])
    report['reason'] = 'repeated_native_network_wait_in_long_tool_progress_gap' if report['confirmed'] else 'insufficient_correlated_evidence'
    report['evidence_hashes'] = {str(p):digest(p) for p in (logs[0], rollouts[0], directory/'computer-private.json')}
    return report


def load_quarantine(root):
    """Exact hashes authorize exclusions, never a broad retry of graded failures."""
    root = Path(root).resolve(); path = root/'transport-quarantine.json'
    if not path.exists():return {}
    data = json.loads(path.read_text())
    assert data['policy'] == POLICY and data['user_authorized'] is True
    mapping = {}
    for entry in data['cases']:
        p = Path(entry['result_file']).resolve()
        assert p.is_relative_to(root) and digest(p) == entry['result_sha256']
        attempt = p.parent.parent
        assert digest(attempt/'attempt.json') == entry['attempt_sha256']
        assert digest(entry['archived_receipt']) == entry['receipt_sha256']
        raw = json.loads(p.read_text())
        assert raw.get('outcome') == 'fail' and raw.get('evaluation',{}).get('success') is False
        assert entry['audit']['confirmed'] is True
        for evidence, expected in entry['audit']['evidence_hashes'].items():
            assert Path(evidence).resolve().is_relative_to(p.parent) and digest(evidence) == expected
        mapping[str(p)] = entry
    return mapping


def is_quarantined(receipt, mapping):
    return str(Path(receipt.get('result_file') or '').resolve()) in mapping
