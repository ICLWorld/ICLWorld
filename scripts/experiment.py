#!/usr/bin/env python3
"""Materialize frozen cases and launch native execution / independent QA branches."""
import argparse,concurrent.futures,hashlib,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');p.chmod(0o600)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jobs(suite,models,cases):
 out=[]
 for model in models:
  for c in cases:
   if suite=='main':conds=['video','text']
   else:conds=['video','qa']+(['none'] if c['variant']=='C' else [])
   out.extend(dict(model=model,task=c['name'],condition=k) for k in conds)
 return out

def main():
 p=argparse.ArgumentParser();p.add_argument('suite',choices=['main','ablation']);p.add_argument('--dataset',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--providers',type=Path);p.add_argument('--models',nargs='+');p.add_argument('--workers',type=int,default=8);p.add_argument('--dry-run',action='store_true');p.add_argument('--task');p.add_argument('--reuse-main',type=Path);a=p.parse_args()
 assert 1<=a.workers<=96
 dataset=a.dataset.resolve();work=a.work.resolve();spec=read(ROOT/'experiments'/f'{a.suite}.json');models=a.models or list(spec['models']);assert all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',m) for m in models),'Use filesystem-safe model labels'
 public_names={(x['native_domain'],str(x['native_task_id'])):x['task_name'] for x in read(dataset/'public-task-names.json')} if (dataset/'public-task-names.json').exists() else {}
 cases=[]
 for row in read(dataset/'metadata'/f'{a.suite}.json'):
  task=dataset/'tasks'/row['task'];video=dataset/row['video'];cfg=read(task/'environment/config.json');instruction=dataset/row['instruction']
  assert digest(video)==cfg['demo_sha256'];assert digest(instruction)==row['instruction_sha256']
  cases.append(dict(row,public_task_name=public_names.get((row['kind'],str(row['task_id']))),task_dir=str(task),source_name=row['task'],seed=row['actual_seed'],instruction=instruction.read_text(),instruction_sha256=digest(instruction),text_rule=(task/'context/text.md').read_text(),demo=dict(path=str(video),sha256=cfg['demo_sha256']),question=read(task/'qa.json')))
 if a.task:cases=[x for x in cases if x['name']==a.task or x.get('public_task_name')==a.task];assert cases,'Unknown task'
 todo=jobs(a.suite,models,cases)
 if a.dry_run:print(json.dumps(dict(suite=a.suite,cases=len(cases),models=models,trials=len(todo),by_condition={k:sum(j['condition']==k for j in todo) for k in ['video','text','none','qa']}),indent=2));return
 if not a.providers:raise SystemExit('--providers is required (see providers.example.json)')
 providers=read(a.providers);envconf=dict(l.split('=',1) for l in (ROOT/'.env').read_text().splitlines() if l and not l.startswith('#'))
 if not work.exists():shutil.copytree(ROOT/'runner',work,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
 elif not (work/'private/cases.json').exists():raise SystemExit('Work directory exists but is not an initialized experiment')
 # Bind the deployed source to this release; preserve the reference build identity separately.
 import urllib.request
 request=urllib.request.Request('http://127.0.0.1:'+envconf['ICLWORLD_PORT']+'/release/identity',headers={'Authorization':'Bearer '+envconf['ICLWORLD_ADMIN_TOKEN']})
 with urllib.request.urlopen(request,timeout=60) as response:identity=json.load(response)
 assert identity['release_sha256']==digest(ROOT/'environment/release-lock.json'),'Server is not this release'
 for c in cases:
  if c['kind']=='web':
   c['reference_implementation_digest']=c['implementation_digest']
   c['implementation_digest']=identity['implementation']['implementation_digest']
 save(work/'runtime/release-identity.json',identity)
 # Guard the resume identity: changing inputs cannot silently resume prior results.
 model_settings={m:{k:providers[m][k] for k in ['engine','api_model']} for m in models}
 contract=dict(suite=a.suite,cases_sha256=hashlib.sha256(json.dumps(cases,sort_keys=True).encode()).hexdigest(),models=models,model_settings=model_settings)
 if (work/'experiment.json').exists():assert read(work/'experiment.json')==contract,'Resume contract changed'
 save(work/'model-config.json',model_settings)
 save(work/'experiment.json',contract);save(work/'private/cases.json',cases)
 token=work/'runtime/admin.token';token.parent.mkdir(parents=True,exist_ok=True);token.write_text(envconf['ICLWORLD_ADMIN_TOKEN']);token.chmod(0o600)
 save(work/'runtime/connection.json',dict(control_url='http://127.0.0.1:'+envconf['ICLWORLD_PORT'],token_file=str(token)))
 runtime=Path(os.environ.get('MATRIX_CLI_ROOT',ROOT/'.runtime')).resolve();env=dict(os.environ,MATRIX_CLI_ROOT=str(runtime),ICLWORLD_CLAUDE_BINARY=os.environ.get('ICLWORLD_CLAUDE_BINARY',str(runtime/'claude/node_modules/.bin/claude')))
 env['PYTHONPATH']=str(work/'sdk')+os.pathsep+env.get('PYTHONPATH','')
 if not (work/'cli').exists():(work/'cli').symlink_to(runtime/'cli',target_is_directory=True)
 public_providers={}
 for model in models:
  cfg=providers[model];key=os.environ.get(cfg['key_env']);assert key,'Missing '+cfg['key_env'];engine=cfg['engine'];assert engine in {'codex','claude','kimi','dsh','zcode'}
  save(work/'private'/f'{model}-primary.json',{('codex' if engine=='codex' else 'claude'):dict(base_url=cfg['base_url'],api_key=key)})
  public_providers[model]=dict(base=cfg['base_url'].removesuffix('/v1'),key=key)
 save(work/'providers.private.json',public_providers)
 # Main C trials may be reused only when their model, prompt, video and result identities match.
 reused=[]
 if a.reuse_main:
  assert a.suite=='ablation'
  for c in cases:
   if c['variant']!='C':continue
   for m in models:
    source_contract=read(a.reuse_main.resolve()/'experiment.json')
    if source_contract.get('model_settings',{}).get(m)!=model_settings[m]:continue
    src=a.reuse_main.resolve()/'outputs'/m/'video'/c['name']/'receipt.json'
    if not src.exists():continue
    rec=read(src);assert rec.get('graded') and rec['model']==m and rec['task']==c['name'] and rec['condition']=='video'
    result=Path(rec['result']);assert digest(result)==rec['result_sha256']
    inp=read(Path(rec['attempt'])/'input-contract.json');assert inp['demo_sha256']==c['demo']['sha256'] and inp['instruction_sha256']==c['instruction_sha256']
    dst=work/'outputs'/m/'video'/c['name']/'receipt.json';save(dst,rec);reused.append(dict(model=m,task=c['name'],result_sha256=rec['result_sha256']))
  save(work/'reuse-manifest.json',reused)
 def launch(job):
  home=work/'outputs'/job['model']/job['condition']/job['task'];rec=home/'receipt.json'
  if rec.exists():
   existing=read(rec)
   if existing.get('graded'):return 'complete'
   return 'review_required' # No unreviewed automatic retry of transport failures.
  cmd=[sys.executable,str(work/'run_one.py'),'--root',str(work),'--model',job['model'],'--task',job['task'],'--condition',job['condition']]
  log=work/'launcher-logs'/job['model']/job['condition']/(job['task']+'.log');log.parent.mkdir(parents=True,exist_ok=True)
  jobenv=dict(env)
  jobenv['ICLWORLD_API_MODEL_ID']=providers[job['model']]['api_model']
  jobenv['ICLWORLD_MODEL_LABEL']=job['model']
  with log.open('w') as f:r=subprocess.run(cmd,env=jobenv,stdout=f,stderr=subprocess.STDOUT)
  return 'finished' if r.returncode==0 else 'review_required'
 import psutil
 # Execution always precedes its QA fork. An ungraded attempt is retained for review.
 for phase in [False,True]:
  queue=[j for j in todo if (j['condition']=='qa')==phase];active={}
  with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
   while queue or active:
    done=[f for f in active if f.done()]
    for f in done:
     j=active.pop(f)
     try:state=f.result()
     except Exception as exc:state='review_required:'+type(exc).__name__
     print(json.dumps(dict(j,state=state)),flush=True)
    ram=psutil.virtual_memory().available/2**30;disk=shutil.disk_usage(work).free/2**30;cpu=psutil.cpu_percent(interval=.1)
    slots=min(a.workers-len(active),8,max(0,int((ram-18)/.6))) if ram>=16 and disk>=20 and cpu<=95 else 0
    for _ in range(min(slots,len(queue))):
     j=queue.pop(0);active[pool.submit(launch,j)]=j
    if queue or active:time.sleep(15)
 print('All submitted jobs have terminated. Run scripts/scores.py; review_required is not a valid completion.')
if __name__=='__main__':main()
