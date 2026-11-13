"""Independent video QA using native CLI adapters and public-only MCP tools."""
import argparse,hashlib,json,os,secrets,subprocess,sys,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SDK=ROOT/'harness/VideoICLBench/packages/sdk'
sys.path[:0]=[str(ROOT/'harness/worker'),str(SDK)]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');p.chmod(0o600)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--dataset',type=Path,required=True);p.add_argument('--qa-id',required=True);p.add_argument('--out',type=Path,required=True)
 p.add_argument('--engine',choices=['codex','dsh','zcode'],required=True);p.add_argument('--model',required=True);p.add_argument('--binary',type=Path,required=True)
 p.add_argument('--api-base',required=True);p.add_argument('--key-env',default='MODEL_API_KEY');p.add_argument('--effort',default='high');p.add_argument('--context-window',type=int);p.add_argument('--compact-tokens',type=int);p.add_argument('--codex-model-catalog',type=Path);p.add_argument('--codex-model-catalog-sha256');p.add_argument('--execute',action='store_true')
 a=p.parse_args();data=a.dataset.resolve()/'robot'
 rows=[json.loads(x) for x in (data/'evaluation/qa_questions.jsonl').read_text().splitlines()];found=[x for x in rows if x['qa_id']==a.qa_id]
 if len(found)!=1:raise ValueError('QA identity must match exactly once')
 row=found[0];video=(data/row['demonstration']['path']).resolve()
 if not video.is_relative_to(data) or sha(video)!=row['demonstration']['sha256']:raise ValueError('QA video mismatch')
 from run import worker_settings,adapter_runtime
 settings=worker_settings(a)
 from provider_routes import https_origin
 os.environ['VIC_UPSTREAM_ORIGIN']=a.api_base;https_origin('VIC_UPSTREAM_ORIGIN');os.environ['VIC_PROVIDER_DIRECT']='1'
 if not a.execute:print(json.dumps({'qa_id':a.qa_id,'settings':settings,'video_sha256':sha(video),'model_requests':0}));return
 key=os.environ.get(a.key_env)
 if not key:raise ValueError('Set the API key environment variable')
 out=a.out.resolve();os.umask(0o077);out.mkdir(parents=True,exist_ok=False)
 ident={k:row[k] for k in ['qa_id','task','variant','seed']};timing=out/'api-timing.private.jsonl';token=secrets.token_urlsafe(32)
 import transport
 transport.TOOLS={'demo_info','demo_frames','qa_question','qa_answer'}
 if a.engine=='codex':factory=transport.make_relay
 else:
  from anthropic_guard_relay import make_relay
  factory=make_relay
 relay=factory(a.engine,a.model,token,key,out,timing);thread=threading.Thread(target=relay.serve_forever,daemon=True);thread.start()
 try:
  cfg={'schema':'standalone-video-qa-v1','identity':ident,'video_path':str(video),'video_sha256':sha(video),'question':{k:row[k] for k in ['question_id','prompt','options','response_instruction']},'output_dir':str(out),'api_timing_log':str(timing)}
  put(out/'qa-tools.json',cfg);put(out/'effective-config.json',settings)
  profile=out/'profile';work=out/'workspace';profile.mkdir();work.mkdir()
  mcp={'command':sys.executable,'args':[str(ROOT/'qa/standalone_qa_tools.py'),'--config',str(out/'qa-tools.json'),'--sdk-root',str(SDK)],'tool_timeout_sec':86400,'env':{}}
  if a.engine=='zcode':mcp['env']['ICLWORLD_QA_IMAGE_LEDGER']=str(out/'image-ledger.jsonl')
  base=f'http://127.0.0.1:{relay.server_port}';provider={'base_url':base+('/v1' if a.engine=='codex' else ''),'api_key':token,'wire_api':'responses' if a.engine=='codex' else 'messages'}
  module,binary=adapter_runtime(a.engine,a.binary)
  instructions='Watch the assigned video with demo_info and demo_frames, then call qa_question and submit one uppercase A/B/C/D through qa_answer. First valid answer is final. This is independent video QA; no simulation, physical actions, text rule or correctness feedback is available.'
  if a.engine=='codex':
   import vic_sdk.embodied_codex_mcp as roles
   roles.NATIVE_MODEL_INSTRUCTIONS=instructions;roles.NATIVE_TOOL_INSTRUCTIONS=instructions
  module.configure(profile,work,a.model,mcp,provider,settings)
  cmd,env=module.command(profile,work,a.model,binary=binary)
  env.update(PATH=os.environ['PATH'],NO_PROXY='localhost,127.0.0.1',HOME=str(profile))
  with (out/'stdout.jsonl').open('xb') as stdout,(out/'stderr.log').open('xb') as stderr:
   child=subprocess.run(cmd,cwd=work,env=env,input=instructions.encode(),stdout=stdout,stderr=stderr)
  from vic_sdk.api_timing import ApiTimingLedger
  ledger=ApiTimingLedger(timing).snapshot();answer=out/'first-valid-answer.private.json'
  put(out/'result.json',{'identity':ident,'CLI_exit_code':child.returncode,'answer_recorded':answer.is_file(),'answer_sha256':sha(answer) if answer.is_file() else None,'api_timing':ledger,'simulation_starts':0,'graded':False})
 finally:relay.shutdown();relay.server_close();thread.join()
if __name__=='__main__':main()
