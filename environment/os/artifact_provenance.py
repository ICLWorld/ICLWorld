"""Stable implementation and interaction provenance for reproducible recordings."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SOURCES=('os_outcome_scoring.py','os_content_formats.py','workflows.py','domain_checks.py','protocols.py','server.py','tasks36.py','judge36.py','docs/TASK_CATALOGUE_36.json',
         'static/desktop.js','static/desktop.css','static/index.html',
         'static/recording.html','static/recording-studio.html','render_video.py',
         'scripts/audit_v2_browser.py','artifact_provenance.py')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def capture():
    hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCES}
    return {'source_hashes':hashes,'fingerprint':digest(hashes)}


def assert_unchanged(implementation):
    if capture()['fingerprint']!=implementation['fingerprint']:
        raise RuntimeError('Implementation changed during the recording run. Preserve the trace and start a new versioned run; do not mix artifacts.')


def video_metadata(session):
    episode=session['episode']
    return {'schema_version':1,'source':'browser-interaction-replay',
            'actor':session.get('recording_actor','not-attested'),
            'benchmark_version':episode['benchmark_version'],
            'implementation_fingerprint':episode['implementation']['fingerprint'],
            'trace_sha256':digest(session['ui_events']),
            'final_state_sha256':digest(episode['state']), 'replay_verified':True}
