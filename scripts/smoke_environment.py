#!/usr/bin/env python3
"""Reset, observe, score and release frozen configurations without requesting a model."""
import argparse,base64,concurrent.futures,hashlib,json,time,urllib.request,urllib.error
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--all',action='store_true');p.add_argument('--screenshots',action='store_true');p.add_argument('--workers',type=int,default=4);a=p.parse_args();assert 1<=a.workers<=4
root=Path(__file__).resolve().parents[1];conf=dict(l.split('=',1) for l in (root/'.env').read_text().splitlines() if l and not l.startswith('#'));base='http://127.0.0.1:'+conf['ICLWORLD_PORT']
def request(path,body=None,method=None):
 req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+conf['ICLWORLD_ADMIN_TOKEN'],'Content-Type':'application/json'},method=method)
 try:
  with urllib.request.urlopen(req,timeout=180) as r:return json.load(r)
 except urllib.error.HTTPError as e:raise RuntimeError(f'{e.code}: '+e.read().decode()[:400])
identity=request('/release/identity');assert identity['release_sha256']==hashlib.sha256((root/'environment/release-lock.json').read_bytes()).hexdigest()
rows=json.loads((a.dataset/'metadata/main.json').read_text())
if a.all:
 baselines={(c['kind'],str(c['task_id'])):c for c in rows if c['generalization']=='I'}
 chosen=[]
 for task in json.loads((a.dataset/'metadata/tasks.json').read_text()):
  c=dict(baselines[(task['kind'],str(task['task_id']))],variant=task['variant'],name=task['name']+'-i',task=task['name'])
  chosen.append(c)
 chosen.extend(c for c in rows if c['generalization']!='I')
else:chosen=[next(c for c in rows if c['kind']==k and c['generalization']==g) for k in ['web','os'] for g in ['I','R','E']]
report=[];a.output.mkdir(parents=True,exist_ok=True)
def run_case(c):
 item={'task':c['name'],'kind':c['kind'],'generalization':c['generalization']};run=None
 try:
  payload=dict(variant=c['variant'],seed=4201,generalization=c['generalization'],interaction='agent',timeout_seconds=120,max_actions=800)
  if c['kind']=='web':payload.update(task_id=c['task_id'],suite='v2',mode='eval',runtime='browser');prefix='/v1/runs'
  else:payload['case_id']=c['task_id'];prefix='/os-api/runs'
  r=c.get('replay_source') or {}
  if c['generalization']=='R':payload.update(dict(replay_run_id=r['run_id'],replay_epoch=r['epoch'],replay_example=r['example']) if c['kind']=='web' else dict(replay_recording_id=r['recording'],replay_example=r['example']))
  run=request(prefix,payload);assert run['seed']==c['actual_seed'];sid=run['id'];item['run_id']=sid
  if c['kind']=='web':assert run['manifest']['task_digest']==c['task_digest'];assert run['manifest']['implementation']['implementation_digest']==identity['implementation']['implementation_digest']
  else:assert run['benchmark_version']==c['benchmark_version']
  obs=request(prefix+'/'+sid+'/observation');assert obs['image'].startswith('data:image/') and obs['width']>0 and obs['height']>0
  raw=base64.b64decode(obs['image'].split(',',1)[1]);assert len(raw)>1000
  item['screenshot_sha256']=hashlib.sha256(raw).hexdigest()
  if a.screenshots:
   images=a.output/'screenshots';images.mkdir(exist_ok=True);(images/(c['name']+('.png' if obs['image'].startswith('data:image/png') else '.jpg'))).write_bytes(raw)
  result=request(f'/v2/tasks/{c["task_id"]}/eval',{'run_id':sid}) if c['kind']=='web' else request(prefix+'/'+sid+'/eval',{'run_id':sid})
  assert type(result.get('success')) is bool and result['run_id']==sid and result['seed']==c['actual_seed']
  item.update(status='passed',evaluation_identity_valid=True)
 except Exception as exc:item.update(status='failed',error=str(exc)[:600])
 finally:
  if run and c['kind']=='web':
   try:request('/v1/runs/'+run['id'],method='DELETE');item['released']=True
   except Exception as exc:item['release_error']=str(exc)[:200]
  if run and c['kind']=='os' and item.get('status')=='failed':
   try:request(prefix+'/'+run['id']+'/eval',{'run_id':run['id']});item['released']=True
   except Exception as exc:item['release_error']=str(exc)[:200]
 return item
with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
 for item in pool.map(run_case,chosen):
  report.append(item);(a.output/'environment-smoke.json').write_text(json.dumps(dict(model_requests=0,identity=identity,planned=len(chosen),checks=report),indent=2)+'\n');print(json.dumps(item),flush=True)
if any(x['status']!='passed' for x in report):raise SystemExit(1)
