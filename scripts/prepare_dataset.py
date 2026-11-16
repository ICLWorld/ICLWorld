#!/usr/bin/env python3
"""Build native Harbor workspaces from the unified ICLWorld dataset; no API calls."""
from pathlib import Path
import argparse,hashlib,json,os,shutil
ROOT=Path(__file__).resolve().parents[1]
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def prepare(dataset,out):
 dataset=dataset.resolve();out=out.resolve()
 if out.exists():raise ValueError('Choose a fresh output directory')
 records=[json.loads(s) for s in (dataset/'metadata.jsonl').read_text().splitlines() if s]
 keyed={(r['task_name'],r['variant']):r for r in records}
 if len(keyed)!=len(records):raise ValueError('Duplicate task/version')
 layout=json.loads((ROOT/'experiments/dataset_layout.json').read_text())
 for rel,x in layout['assets'].items():
  p=(dataset/x['path']).resolve()
  if not p.is_relative_to(dataset) or not p.is_file() or digest(p)!=x['sha256']:raise ValueError('Missing or modified asset: '+x['path'])
 shutil.copytree(ROOT/'experiments/native_layout',out)
 for rel,x in layout['assets'].items():
  p=dataset/x['path'];q=out/rel;q.parent.mkdir(parents=True,exist_ok=True)
  try:os.link(p,q)
  except OSError:shutil.copy2(p,q)
 # Materialize the recorded initial state for each declared Web R condition.
 bindings={(b['native_task_id'],b['variant']): b['task_name'] for b in layout['task_bindings'] if b['native_domain']=='web'}
 released_video_hashes={v['path']:v['sha256'] for v in layout['assets'].values()}
 replay_index=out/'metadata/web-replays.json';enabled=[]
 for r in json.loads(replay_index.read_text()):
  row=keyed[(bindings[(str(r['task_id']),r['variant'])],r['variant'])]
  entry=next((g for g in row['generalization'] if g['condition']=='R'),None)
  if entry is None:continue
  rel,=entry['resource_dependencies'];p=(dataset/rel).resolve()
  if not p.is_relative_to(dataset):raise ValueError('Invalid Web replay path')
  raw=p.read_bytes()
  if hashlib.sha256(json.dumps(json.loads(raw),sort_keys=True).encode()).hexdigest()!=r['initial_sha256']:raise ValueError('Web replay checksum mismatch: '+rel)
  video=row['videos'][0]['path']
  if released_video_hashes.get(video)!=r['video_sha256']:raise ValueError('Web replay demonstration mismatch: '+video)
  dest=out/r['initial']
  if not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
  enabled.append(r)
 replay_index.write_text(json.dumps(enabled,ensure_ascii=False,indent=2)+'\n')
 for b in layout['task_bindings']:
  r=keyed[(b['task_name'],b['variant'])];d=out/b['native_directory'];d.mkdir(parents=True,exist_ok=True)
  if r['domain'] in ['web','os']:
   (d/'instruction.md').write_text(r['prompt']);(d/'context/text.md').write_text(r['text_context'])
   (d/'qa.json').write_text(json.dumps(r['qa'],ensure_ascii=False,indent=2)+'\n')
  else:
   (d/'prompt.md').write_text(r['prompt']);(d/'text_rule.md').write_text(r['text_context'])
 # Native runtime identifiers are implementation details. Public names stay available to result consumers.
 (out/'public-task-names.json').write_text(json.dumps(layout['task_bindings'],indent=2)+'\n')
 return {'task_families':len({r['task_name'] for r in records}),'task_versions':len(records),'assets':len(layout['assets']),'model_requests':0}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('dataset',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(json.dumps(prepare(a.dataset,a.out)))
