#!/usr/bin/env python3
"""Produce fixed-denominator main/generalization or ablation tables from checked receipts."""
import argparse,hashlib,json
from pathlib import Path
from experiment import jobs
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path);a=p.parse_args();w=a.work.resolve()
read=lambda p:json.loads(p.read_text())
contract=read(w/'experiment.json');cases=read(w/'private/cases.json');index={c['name']:c for c in cases};planned=jobs(contract['suite'],contract['models'],cases);review=[];records=[]
for j in planned:
 f=w/'outputs'/j['model']/j['condition']/j['task']/'receipt.json';r=read(f) if f.exists() else {};valid=bool(r.get('graded'))
 if valid:
  if r.get('result'):
   raw=Path(r['result']);assert hashlib.sha256(raw.read_bytes()).hexdigest()==r['result_sha256'],str(f)
   reward=read(Path(r['attempt'])/'logs/verifier/reward.json');assert bool(reward['success'])==r['success']
  else:assert j['condition']=='qa','Execution receipt without authoritative result'
 elif r:review.append(str(f))
 c=index[j['task']];records.append(dict(j,kind=c['kind'],difficulty=c['difficulty'],generalization=c['generalization'],variant=c['variant'],valid=valid,success=bool(valid and r.get('success')),process=r.get('partial_score') if valid else None))
def aggregate(model,**filters):
 q=[r for r in records if r['model']==model and all(r[k]==v for k,v in filters.items())];v=sum(r['valid'] for r in q);s=sum(r['success'] for r in q);scores=[r['process'] for r in q if r['process'] is not None]
 return dict(correct=s,valid=v,planned=len(q),accuracy=s/v if v else None,process_score=sum(scores)/len(scores) if scores else None)
def cell(v):return f"{v['correct']}/{v['valid']}/{v['planned']} ({100*v['accuracy']:.1f}%)" if v['valid'] else f"0/0/{v['planned']} (—)"
tables={};markdown=['# ICLWorld Web/OS results','', 'Cells: correct / valid completed / planned (completed accuracy).','']
if contract['suite']=='main':
 columns=[item for k in ['web','os'] for item in [(f'{k} {d}',dict(kind=k,difficulty=d,generalization='I')) for d in ['easy','medium','hard']]+[(f'{k} avg',dict(kind=k,generalization='I'))]]+[('I avg',dict(generalization='I'))]
 specs=[('Main I',columns),('Generalization',[(g,dict(generalization=g)) for g in ['R','I','E']]+[('avg',{})])]
else:
 specs=[('Ablations',[('None C',dict(condition='none',variant='C'))]+[(f'Video {v}',dict(condition='video',variant=v)) for v in 'ABC']+[(f'QA {v}',dict(condition='qa',variant=v)) for v in 'ABC'])]
for name,columns in specs:
 markdown+=['## '+name,'','| Model | '+' | '.join(k for k,_ in columns)+' |','|---|'+'---|'*len(columns)]
 table={}
 for m in contract['models']:
  table[m]={label:aggregate(m,**filters) for label,filters in columns};markdown.append('| '+m+' | '+' | '.join(cell(v) for v in table[m].values())+' |')
 markdown+=[''];tables[name]=table
markdown+=['## Execution process score','','| Model | Average |','|---|---|']
for m in contract['models']:
 scores=[r['process'] for r in records if r['model']==m and r['condition']!='qa' and r['process'] is not None];markdown.append(f"| {m} | {sum(scores)/len(scores):.4f} |" if scores else f'| {m} | — |')
markdown+=['',f"Valid completion: {sum(r['valid'] for r in records)}/{len(records)}. Ungraded receipts requiring review: {len(review)}.",'','R/E are stratified subsets; aggregate differences are not a causal generalization comparison.']
report='\n'.join(markdown)+'\n'
if a.output:
 a.output.mkdir(parents=True,exist_ok=True);(a.output/'RESULTS.md').write_text(report);(a.output/'scores.json').write_text(json.dumps(dict(tables=tables,review_required=review),indent=2)+'\n')
print(report)
