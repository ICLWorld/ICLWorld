#!/usr/bin/env python3
"""Controller-side verifier: private endpoint configuration is never mounted to the agent."""
import json,os,urllib.request,math
from pathlib import Path
cfg=json.loads(Path(os.environ['VIDEOICL_VERIFIER_CONFIG']).read_text())
if cfg.get('result_path'):
 result=json.loads(Path(cfg['result_path']).read_text())
else:
 req=urllib.request.Request(cfg['url'],data=json.dumps(cfg.get('body',{})).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+cfg['token']},method='POST')
 with urllib.request.urlopen(req,timeout=90) as r:result=json.load(r)
if type(result.get('success')) is not bool:raise ValueError('No authoritative evaluation; do not report an infrastructure failure as zero')
for key,value in cfg.get('expected_identity',{}).items():
 if type(result.get(key)) is not type(value) or result.get(key)!=value:raise ValueError('Evaluation identity mismatch: '+key)
score=result.get('score',result.get('completion',result.get('partial_credit',float(result['success']))))
if isinstance(score,dict):score=score.get('value',float(result['success']))
if type(score) not in (int,float) or not math.isfinite(score) or not 0<=score<=1:raise ValueError('Invalid normalized score')
out=Path(os.environ.get('HARBOR_VERIFIER_LOG_DIR','/logs/verifier'));out.mkdir(parents=True,exist_ok=True)
(out/'evaluation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
(out/'reward.json').write_text(json.dumps({'success':float(result['success']),'score':score})+'\n')
print(json.dumps({'success':result['success'],'score':score}))
