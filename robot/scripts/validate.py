"""Validate robot task/media pairing, muted videos and physical case inputs."""
from pathlib import Path
import argparse,json,hashlib,subprocess

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def validate(dataset,media=False):
 root=dataset.resolve()/'robot';videos=[]
 for i in range(1,51):
  for variant in 'ABC':
   p=root/'tasks'/f'E{i:02d}'/variant
   meta=json.loads((p/'task.json').read_text())
   assert meta['task_id']==f'E{i:02d}' and meta['variant']==variant
   for kind in ['real','sim']:
    f=p/(kind+'.mp4');assert f.is_file() and digest(f)==meta[kind]['sha256'],f
    videos.append(f)
   assert (p/'prompt.md').is_file() and (p/'text_rule.md').is_file()
 for f in (root/'evaluation/media').glob('*.mp4'):videos.append(f)
 assignments=[json.loads(x) for x in (root/'evaluation/assignments.jsonl').read_text().splitlines()]
 cases=json.loads((root/'metadata/cases.json').read_text());assert len(cases)==255==len(assignments)
 assert len({x['episode_id'] for x in cases})==255
 for c in cases:
  p=root/c['task_package'];n=json.loads((p/'environment/native.json').read_text())
  assert n['task_id']==c['task'] and n['variant']==c['variant'] and n['seed']==c['seed']
  assert n['generalization_condition']==c['generalization_condition']
  assert digest(p/'instruction.md')==n['instruction_sha256']
  for field in ('demo','demo_sim'):
   if field in n:
    v=(p/n[field]['path']).resolve();assert v.is_relative_to(root) and digest(v)==n[field]['sha256']
 if media:
  for f in videos:
   d=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(f)]))
   assert len([s for s in d['streams'] if s['codec_type']=='video'])==1,f
   assert not any(s['codec_type']=='audio' for s in d['streams']),f
   assert float(d['format']['duration'])>0,f
 return {'families':50,'variants':150,'real_videos':150,'sim_videos':150,'evaluation_videos':len(videos)-300,'physical_cases':255,'media_checked':media,'status':'passed'}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',type=Path,required=True);p.add_argument('--media',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args();r=validate(a.dataset,a.media);s=json.dumps(r,indent=2);print(s)
 if a.output:a.output.write_text(s+'\n')
