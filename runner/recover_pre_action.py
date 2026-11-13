"""Recover an immutable viewing-only context when the source never acted."""
import json,gzip,hashlib
from pathlib import Path
from protocol import digest,save
from api_model_identity import api_model_id

def validate_context(capture,events,deadline):
 assert events and all(e.get('type') in ('observation','demo_frame') for e in events),'Source includes execution or unknown events'
 assert capture['captured_at']<=deadline and capture['captured_at']>=max(e['time'] for e in events),'Context is not the final viewing-only request within budget'
 allowed={'demo_info','demo_frame','demo_frames','computer_observe'};names=[]
 for message in capture['body'].get('messages',[]):
  for t in message.get('tool_calls',[]):names.append(t.get('function',{}).get('name',''))
  content=message.get('content',[])
  if isinstance(content,list):
   names.extend(x.get('name','') for x in content if x.get('type')=='tool_use')
 assert names and all(n.removeprefix('mcp__vic__').removeprefix('mcp_vic_') in allowed for n in names),'Source contains a non-viewing tool invocation'
 assert hashlib.sha256(json.dumps(capture['body']).encode()).hexdigest()==capture['request_sha256'],'Captured request identity mismatch'

def resolve(root,model,case,origin):
 a=Path(origin['attempt']);p=a/'video-checkpoint.json'
 if p.exists():return p
 source=a/'candidate-context.json';source=source if source.exists() else Path(str(source)+'.gz');raw=gzip.open(source,'rb').read() if source.suffix=='.gz' else source.read_bytes();capture=json.loads(raw);rp=Path(origin['result']);assert digest(rp)==origin['result_sha256'] and origin['graded'];meta=json.loads((rp.parent/'manifest.json').read_text());cfg=json.loads((rp.parent/'computer-private.json').read_text());assert meta['model']==api_model_id(model) and meta['seed']==4201 and meta['variant']==case['variant'];assert capture['model']==api_model_id(model);assert capture['body'].get('reasoning_effort',capture['body'].get('output_config',{}).get('effort'))=='high'
 events=[json.loads(l) for l in (rp.parent/'computer.jsonl').read_text().splitlines()];validate_context(capture,events,cfg['deadline_unix']);transport=[json.loads(l) for l in (a/'transport.jsonl').read_text().splitlines()];matched=any(e.get('request_sha256')==capture['request_sha256'] for e in transport)
 assert matched,'Captured request is not bound to its transport log'

 target=root/'evidence/pre-action-recovery'/model/case['name']/hashlib.sha256(raw).hexdigest();target.mkdir(parents=True,exist_ok=True,mode=0o700);p=target/'video-checkpoint.json'
 if p.exists():assert p.read_bytes()==raw
 else:p.write_bytes(raw);p.chmod(0o600)
 save(target/'proof.json',{'passed':True,'kind':'viewing-only immutable context recovery, not a new model score','source':str(source),'source_file_sha256':digest(source),'checkpoint_sha256':digest(p),'source_result_sha256':digest(rp),'computer_log_sha256':digest(rp.parent/'computer.jsonl'),'transport_log_sha256':digest(a/'transport.jsonl'),'model':model,'task':case['name'],'captured_at':capture['captured_at'],'deadline_unix':cfg['deadline_unix'],'event_count':len(events),'no_task_actions_or_finish':True});return p
