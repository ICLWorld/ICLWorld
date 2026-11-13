"""Choice-only branch: same viewed context; never operates or informs the task."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import httpx
from protocol import MODELS,qa_prompt,save,digest
from qa_completion import completed_answer
from request_context import context_headers

def branch_body(checkpoint,question):
    body=deepcopy(checkpoint['body']);route=checkpoint['route'];prompt=qa_prompt(question)
    if '/responses' in route:
        if body.get('previous_response_id'):
            raise ValueError('Server-only history cannot be exported as a complete branch')
        body.setdefault('input',[]).append({'role':'user','content':[{'type':'input_text','text':prompt}]})
        body['tool_choice']='none';body['store']=False;body['stream']=True
    elif '/messages' in route or '/chat/completions' in route:
        body['messages'].append({'role':'user','content':prompt})
        body['tool_choice']={'type':'none'} if '/messages' in route else 'none'
        body['stream']=True
    elif 'GenerateContent' in route or 'generateContent' in route:
        body['contents'].append({'role':'user','parts':[{'text':prompt}]})
        body.setdefault('toolConfig',{})['functionCallingConfig']={'mode':'NONE'}
        route=route.replace(':generateContent',':streamGenerateContent')
        if 'alt=sse' not in route:route+=('&' if '?' in route else '?')+'alt=sse'
    else:raise ValueError('Unknown captured transport')
    return route,body

def parse_answer(text):
    match=re.fullmatch(r'\s*([ABCD])[.。]?\s*',text)
    return match.group(1) if match else None

def raw_branch(root,model,case,checkpoint,directory):
    directory.mkdir(parents=True,exist_ok=True)
    captured=json.loads(checkpoint.read_text());from api_model_identity import api_model_id
    assert captured['model']==api_model_id(model)
    route,body=branch_body(captured,case['question'])
    provider=json.loads((root/'providers.private.json').read_text())[model]
    headers={'Authorization':'Bearer '+provider['key'],'x-api-key':provider['key'],
             'x-goog-api-key':provider['key'],'anthropic-version':'2023-06-01'}
    headers.update(context_headers(captured.get('request_headers',{})))
    save(directory/'request.json',body)
    result={'model':model,'task':case['name'],'condition':'video_mcq_context_branch','context_sha256':digest(checkpoint),
            'question_sha256':hashlib.sha256(qa_prompt(case['question']).encode()).hexdigest(),'graded':False,'started_at':time.time()}
    text=[];completed=False
    try:
        with httpx.Client(trust_env=False,timeout=httpx.Timeout(300,connect=30)) as c:
            with c.stream('POST',provider['base'].removesuffix('/v1')+route,headers=headers,json=body) as response:
                result['http_status']=response.status_code
                if response.status_code!=200:
                    result.update(outcome='infrastructure_error',error=response.read().decode(errors='replace').replace(provider['key'],'[REDACTED]')[:2000])
                else:
                    with (directory/'response.sse').open('w') as log:
                        for line in response.iter_lines():
                            if time.time()-result['started_at']>900:raise TimeoutError('QA branch exceeded 900 seconds')
                            log.write(line+'\n')
                            if not line.startswith('data:'):continue
                            data=line[5:].strip()
                            if data=='[DONE]':completed=True;continue
                            try:e=json.loads(data)
                            except ValueError:continue
                            if e.get('error'):raise ValueError(json.dumps(e['error']))
                            typ=e.get('type')
                            if typ=='content_block_delta' and e.get('delta',{}).get('type')=='text_delta':text.append(e['delta']['text'])
                            if typ=='response.output_text.delta':text.append(e.get('delta',''))
                            if typ in ('message_stop','response.completed'):completed=True
                            if typ in ('response.failed','error'):raise ValueError(json.dumps(e))
                            for choice in e.get('choices',[]):
                                text.append(choice.get('delta',{}).get('content') or '')
                                if choice.get('finish_reason') is not None:completed=True
                            for candidate in e.get('candidates',[]):
                                text.extend(p.get('text','') for p in candidate.get('content',{}).get('parts',[]) if not p.get('thought'))
                                if candidate.get('finishReason'):completed=True
                    result.update(graded=completed,outcome='answered' if completed else 'incomplete_stream')
    except (httpx.HTTPError,ValueError,TimeoutError) as e:
        result.update(outcome='infrastructure_error',error=str(e).replace(provider['key'],'[REDACTED]')[:1500])
    result['answer_text']=''.join(text);result['choice']=parse_answer(result['answer_text'])
    result['success']=bool(result['graded'] and result['choice']==case['question']['correct_answer'])
    result['correct_answer']=case['question']['correct_answer'];result['ended_at']=time.time()
    save(directory/'receipt.json',result)
    return result

def gpt_branch(root,model,case,directory):
    from vic_sdk.native_agent import codex_config,summarize
    d=directory;d.mkdir(parents=True,exist_ok=True);profile=d/'profile';profile.mkdir();work=d/'workspace';work.mkdir()
    source=root/'qa-checkpoints'/model/case['name']
    record=json.loads((source/'checkpoint.json').read_text());assert record['eligible']
    checkpoint=source/Path(record['checkpoint']).name
    assert digest(checkpoint)==record['checkpoint_sha256']
    # Copy only the reviewed pre-diagnosis prefix to an isolated profile. Native
    # `exec fork` creates the new session; the source baseline is never mutated.
    dst=profile/'sessions'/checkpoint.name;dst.parent.mkdir(parents=True);dst.write_bytes(checkpoint.read_bytes())
    first=json.loads(dst.read_text().splitlines()[0])['payload'];sid=first.get('session_id',first.get('id'))
    provider=json.loads((root/'providers.private.json').read_text())[model]
    from api_model_identity import api_model_id
    config=codex_config(api_model_id(model),provider['base'].removesuffix('/v1')+'/v1',{'command':'unused','args':[]},native_auth=True,code_mode=True,effort='high').split('[mcp_servers.vic]')[0]
    (profile/'config.toml').write_text(config);save(profile/'auth.json',{'auth_mode':'apikey','OPENAI_API_KEY':provider['key']})
    env={k:v for k,v in os.environ.items() if k.lower() not in ('http_proxy','https_proxy','all_proxy')}
    env['CODEX_HOME']=str(profile);env['PATH']=str(Path(os.environ['MATRIX_CLI_ROOT'])/'node-v22.21.1-linux-x64/bin')+':'+env['PATH']
    binary=root/'cli/node_modules/@openai/codex/bin/codex.js'
    cmd=[str(binary),'exec','--skip-git-repo-check','--json','--color','never','-C',str(work),'fork',sid,'-']
    started=time.time();timed=False
    with (d/'stdout.jsonl').open('w') as out,(d/'stderr.log').open('w') as err:
        proc=subprocess.Popen(cmd,env=env,cwd=work,stdin=subprocess.PIPE,stdout=out,stderr=err,text=True,start_new_session=True)
        try:proc.communicate(qa_prompt(case['question']),timeout=900)
        except subprocess.TimeoutExpired:timed=True;os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=15)
    (profile/'auth.json').unlink(missing_ok=True)
    result=summarize('codex',d/'stdout.jsonl',profile)
    result.update(model=model,task=case['name'],condition='video_mcq_native_fork',checkpoint_sha256=digest(checkpoint),
                  exit_code=proc.returncode,timed_out=timed,ended_at=time.time(),duration=time.time()-started)
    result['choice']=parse_answer(result.get('final_text',''))
    result['graded']=completed_answer(d/'stdout.jsonl',result)
    result['success']=bool(result['graded'] and result['choice']==case['question']['correct_answer'])
    result['correct_answer']=case['question']['correct_answer'];save(d/'receipt.json',result)
    return result
