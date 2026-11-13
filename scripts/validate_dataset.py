#!/usr/bin/env python3
"""Validate Harbor layout, immutable input hashes, and experiment coverage."""
import argparse,hashlib,json,tomllib,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('dataset',type=Path);p.add_argument('--media',action='store_true');p.add_argument('--harbor',action='store_true');a=p.parse_args();d=a.dataset.resolve()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rows=json.loads((d/'metadata/tasks.json').read_text());assert len(rows)==330;assert len({(r['kind'],str(r['task_id'])) for r in rows})==110
for r in rows:
 t=d/'tasks'/r['name'];config=tomllib.loads((t/'task.toml').read_text());assert config['schema_version']=='1.3';assert config['agent']['timeout_sec']==3600
 for name,key in [('instruction.md','instruction_sha256'),('context/text.md','text_sha256')]:assert sha(t/name)==r[key],r['name']
 v=d/r['video'];assert sha(v)==r['video_sha256'];q=json.loads((t/'qa.json').read_text());assert set(q['options'])==set('ABCD') and q['correct_answer'] in q['options']
 assert (t/'tests/test.sh').exists() and (t/'environment/config.json').exists()
 env=json.loads((t/'environment/config.json').read_text());assert str(env['task_id'])==str(r['task_id']) and env['variant']==r['variant'] and env['kind']==r['kind'] and env['demo_sha256']==r['video_sha256']
 context=json.loads((t/'context/video.json').read_text());assert (t/'context'/context['path']).resolve()==v.resolve() and context['sha256']==r['video_sha256']
 if a.media:
  x=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type','-of','json',str(v)]));assert float(x['format']['duration'])>0 and any(s['codec_type']=='video' for s in x['streams'])
 if a.harbor:
  from harbor.models.task.task import Task
  Task(t)
for tag,n in [('main',160),('ablation',111)]:
 records=json.loads((d/'metadata'/f'{tag}.json').read_text());assert len(records)==n
 for r in records:assert sha(d/r['instruction'])==r['instruction_sha256'];assert (d/'tasks'/r['task']).exists()
for r in json.loads((d/'metadata/web-replays.json').read_text()):assert hashlib.sha256(json.dumps(json.loads((d/r['initial']).read_text()),sort_keys=True).encode()).hexdigest()==r['initial_sha256']
print(json.dumps(dict(tasks=330,web_families=75,os_families=35,main_configurations=160,ablation_configurations=111,media_checked=a.media,harbor_parser_checked=a.harbor,status='passed')))
