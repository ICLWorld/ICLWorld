"""Prepare portable robot runtime and immutable physical cases; makes no API requests."""
from pathlib import Path
import argparse,hashlib,json,os,shlex,shutil
ROBOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text())
def write(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepare(dataset,out,experiment=None,task=None):
 data=dataset.resolve()/'robot';out=out.resolve()
 if out.exists():raise ValueError('Use a fresh output directory')
 if task and task.startswith('iclworld_robot_'):
  matches={x['native_task_id'] for x in read(dataset.resolve()/'public-task-names.json') if x['task_name']==task}
  if len(matches)!=1:raise ValueError('Unknown public robot task')
  task=matches.pop()
 specs=read(data/'metadata/cases.json')
 rows=[x for x in specs if (not experiment or experiment in x['experiments']) and (not task or x['task']==task)]
 if not rows:raise ValueError('No cases match the selection')
 # Validate every runtime byte before materializing a workspace.
 manifest=read(ROBOT/'runtime-manifest.json');sources={}
 for rel,record in manifest.items():
  p=(ROBOT/'runtime'/rel) if record['store']=='code' else (data/'environment/runtime'/rel)
  if sha(p)!=record['sha256']:raise ValueError('Runtime hash mismatch: '+rel)
  sources[rel]=p
 out.mkdir(parents=True)
 for rel,p in sources.items():
  q=out/'runtime'/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
 shutil.copytree(data/'environment/bindings',out/'bindings')
 for row in rows:
  package=data/row['task_package'];dest=out/row['task_package']
  if not dest.exists():
   shutil.copytree(package,dest)
   native=read(dest/'environment/native.json')
   for field in ('demo','demo_sim'):
    if field in native:
     p=(package/native[field]['path']).resolve()
     if not p.is_relative_to(data) or sha(p)!=native[field]['sha256']:raise ValueError('Invalid demo '+str(p))
     native[field]['path']=str(p)
   write(dest/'environment/native.json',native)
  row['task_package']=str(dest);row['task_root']=str(dest.parent)
  row['bindings']=str(out/'bindings'/row['bindings'])
  row['robot']=str(out/'runtime/configs'/row['robot'])
  if not Path(row['bindings']).is_file() or not Path(row['robot']).is_file():raise ValueError('Missing robot/bindings')
  write(out/'cases'/f"{row['episode_id']}.json",{'cases':[row]})
 write(out/'cases.json',{'cases':rows})
 roots=data/'environment/asset_roots'
 env={p.name:str(p) for p in roots.iterdir() if p.is_dir()}
 env.update(VIC_INFERENCE_ASSETS=str(out/'runtime/inference-generalization-v1/assets'),VIC_EXECUTION_DESIGN_ASSETS=str(out/'runtime/execution-design-v3/assets'),VIDEOICL_SENSOR_DEPTH='1')
 robot=out/'runtime/assets/embodiments/robotwin-r5/franka-panda/robot.usd'
 if not robot.is_file():raise ValueError('Missing Franka USD')
 env['VIC_FRANKA_ROBOTWIN_USD']=str(robot)
 (out/'environment.sh').write_text('\n'.join('export '+k+'='+shlex.quote(v) for k,v in sorted(env.items()))+'\n')
 write(out/'preparation.json',{'case_count':len(rows),'runtime_files':len(manifest),'source_dataset':str(dataset.resolve()),'model_requests':0})
 return rows
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--experiment',choices=['main','generalization','ablation4','ablation_abc','ablation_none']);p.add_argument('--task');a=p.parse_args();rows=prepare(a.dataset,a.out,a.experiment,a.task);print('Prepared',len(rows),'cases. Use one file from cases/ per isolated GPU instance.')
