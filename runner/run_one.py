"""One immutable trial; native CLI acts and the frozen grader checks identity."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from protocol import MODELS,SEED,TIMEOUT,MAX_ACTIONS,execution_prompt,save,digest
from qa import raw_branch,gpt_branch
from api_model_identity import api_model_id

def verify(case,result_file,attempt):
    result=json.loads(result_file.read_text());meta=json.loads((result_file.parent/'manifest.json').read_text())
    identity={k:meta[k] for k in ('run_id','task_id','variant','seed','suite','epoch')}
    assert identity['task_id']==(int(case['task_id']) if case['kind']=='web' else case['task_id']) and identity['variant']==case['variant'] and identity['seed']==case['actual_seed']
    assert meta['generalization']==case['generalization']
    evaluation=attempt/'authoritative-evaluation.json';save(evaluation,result['evaluation'])
    config=attempt/'verifier-private.json';save(config,{'result_path':str(evaluation),'expected_identity':identity})
    subprocess.run(['sh',str(Path(case['task_dir'])/'tests/test.sh')],env=dict(os.environ,VIDEOICL_PYTHON=sys.executable,
        VIDEOICL_VERIFIER_CONFIG=str(config),HARBOR_VERIFIER_LOG_DIR=str(attempt/'logs/verifier')),check=True,capture_output=True)
    return json.loads((attempt/'logs/verifier/reward.json').read_text())

def execute(root,model,case,condition,attempt):
    attempt.mkdir(parents=True,exist_ok=False)
    engine=MODELS[model][0];internal='codex' if engine=='codex' else 'claude'
    conn=json.loads((root/'runtime/connection.json').read_text())
    prompt=execution_prompt(case['instruction'],condition,case['text_rule'] if condition=='text' else None)
    (attempt/'prompt.txt').write_text(prompt)
    cmd=[sys.executable,str(root/'native.py'),internal,'--model',api_model_id(model),'--effort','high',
         '--credentials',str(root/'private'/f'{model}-{os.environ.get("CAMPAIGN_PROVIDER","primary")}.json'),'--control-url',conn['control_url'],
         '--admin-token-file',conn['token_file'],'--output-root',str(attempt),'--variant',case['variant'],
         '--seed',str(SEED),'--timeout',str(TIMEOUT),'--max-actions',str(MAX_ACTIONS),'--prompt',prompt,'--evaluate']
    if case['kind']=='os':cmd+=['--os-case',str(case['task_id'])]
    else:cmd+=['--task',str(case['task_id'])]
    if condition=='video':cmd+=['--demo',case['demo']['path']]
    elif condition=='text':
        (attempt/'rule.txt').write_text(case['text_rule']);cmd+=['--rule-file',str(attempt/'rule.txt')]
    if engine=='codex':cmd+=['--binary',str(root/'cli/node_modules/@openai/codex/bin/codex.js'),'--code-mode']
    if engine=='claude':cmd+=['--binary',os.environ['ICLWORLD_CLAUDE_BINARY']]
    env={k:v for k,v in os.environ.items() if k.lower() not in ('http_proxy','https_proxy','all_proxy')}
    env.update(MATRIX_ENGINE=engine,PATH=str(Path(os.environ['MATRIX_CLI_ROOT'])/'node-v22.21.1-linux-x64/bin')+':'+env['PATH'])
    replay=case.get('replay_source') or {}
    replay_params={}
    if case['generalization']=='R':
        replay_params=({'replay_recording_id':replay['recording'],'replay_example':replay['example']} if case['kind']=='os' else {'replay_run_id':replay['run_id'],'replay_epoch':replay['epoch'],'replay_example':replay['example']})
    env.update(MATRIX_NO_RULE='1' if condition=='none' else '0')
    env.update(MATRIX_GENERALIZATION=case['generalization'],MATRIX_REPLAY_PARAMS=json.dumps(replay_params),MATRIX_EXPECTED_CASE=json.dumps(dict(generalization=case['generalization'],actual_seed=case['actual_seed'],demo_sha256=case['demo']['sha256'],benchmark_version=case.get('benchmark_version'),task_digest=case.get('task_digest'),implementation_digest=case.get('implementation_digest'))))
    save(attempt/'input-contract.json',{'task':case['name'],'condition':condition,'generalization':case['generalization'],'seed':case['actual_seed'],'instruction_sha256':case['instruction_sha256'],'demo_sha256':case['demo']['sha256'],'provider':os.environ.get('CAMPAIGN_PROVIDER','primary')})
    started=time.time()
    with (attempt/'driver.stdout').open('w') as out,(attempt/'driver.stderr').open('w') as err:
        proc=subprocess.Popen(cmd,stdout=out,stderr=err,env=env,start_new_session=True)
        save(attempt/'active.json',{'pid':proc.pid,'model':model,'task':case['name'],'condition':condition,'started_at':started})
        try:proc.wait(timeout=TIMEOUT+600)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGTERM);proc.wait(timeout=30)
    found=list(attempt.glob('*/result.json'))
    result=json.loads(found[0].read_text()) if len(found)==1 else {}
    graded=result.get('outcome') in ('success','fail') and isinstance(result.get('evaluation'),dict)
    receipt={'model':model,'task':case['name'],'condition':condition,'graded':graded,
             'success':result.get('evaluation',{}).get('success') if graded else None,
             'outcome':result.get('outcome','missing_result'),'result':str(found[0]) if len(found)==1 else None,
             'result_sha256':digest(found[0]) if len(found)==1 else None,'exit_code':proc.returncode,
             'started_at':started,'ended_at':time.time(),'attempt':str(attempt)}
    if graded:
        reward=verify(case,found[0],attempt);receipt['partial_score']=reward['score']
        assert bool(reward['success'])==receipt['success']
    save(attempt/'receipt.json',receipt)
    return receipt

def run(root,model,task,condition):
    cases={c['name']:c for c in json.loads((root/'private/cases.json').read_text())};case=cases[task]
    home=root/'outputs'/model/condition/task;home.mkdir(parents=True,exist_ok=True)
    with (home/'lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        current=home/'receipt.json'
        if current.exists() and json.loads(current.read_text()).get('graded'):
            return json.loads(current.read_text())
        if condition!='qa':
            for prior in home.glob('attempt-*/*/result.json'):
                raw=json.loads(prior.read_text())
                if raw.get('outcome') in ('success','fail'):
                    raise RuntimeError('Existing authoritative result needs receipt recovery; refuse rerun: '+str(prior))
        attempt=home/f'attempt-{len(list(home.glob("attempt-*")))+1:03}'
        if condition=='qa':
            if MODELS[model][0]=='codex':
                from prepare_qa_checkpoint import prepare
                prepare(root,model,case)
                result=gpt_branch(root,model,case,attempt)
            else:
                video=root/'outputs'/model/'video'/task/'receipt.json'
                if not video.exists():return {'outcome':'waiting_video','graded':False}
                origin=json.loads(video.read_text());assert origin.get('graded') and digest(Path(origin['result']))==origin['result_sha256'],'QA requires a verified execution receipt'
                checkpoint=Path(origin['attempt'])/'video-checkpoint.json'
                if not checkpoint.exists():
                    from recover_pre_action import resolve
                    checkpoint=resolve(root,model,case,origin)
                result=raw_branch(root,model,case,checkpoint,attempt)
            result['attempt']=str(attempt)
        else:result=execute(root,model,case,condition,attempt)
        save(current,result)
        return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--model',choices=MODELS,required=True);p.add_argument('--task',required=True);p.add_argument('--condition',choices=['video','text','none','qa'],required=True);a=p.parse_args()
    print(json.dumps(run(a.root,a.model,a.task,a.condition),ensure_ascii=False))
