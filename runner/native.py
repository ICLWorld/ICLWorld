"""Frozen run creation/scoring with native harness adapters and isolated QA capture."""
import json
import os
from pathlib import Path
import sys
from vic_sdk import native_agent as native
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from transport_audit import audit_timeout
from capture_proxy import capture_proxy
from protocol import MODELS, save
from api_model_identity import api_model_id
from timeout_transport import review_events

original_run=native.run
# Isolated no-rule adapter: suppress SDK auto-assigned OS video, without changing grading.
if os.environ.get('MATRIX_NO_RULE')=='1':
    import inspect
    src=inspect.getsource(original_run)
    needle='if not args.demo and not getattr(args, "rule_file", None):'
    assert src.count(needle)==1
    namespace=dict(native.__dict__)
    exec(src.replace(needle, 'if False:  # no-rule ablation: no automatic demo download'),namespace)
    original_run=namespace['run']

original_command=native.cli_command
original_evaluate=native.evaluate_result
original_summarize=native.summarize
ENGINE=os.environ['MATRIX_ENGINE']
HERE=Path(__file__).resolve().parent

def cli_command(engine,profile,workspace,model,server,**kwargs):
    cfg_file=Path(server['args'][-1]);cfg=json.loads(cfg_file.read_text())
    cfg['capture_root']=os.environ['MATRIX_CAPTURE_ROOT'];cfg['rule_diagnostic']=False
    save(cfg_file,cfg)
    server={'command':sys.executable,'args':[str(HERE/'checkpoint_mcp.py'),'--config',str(cfg_file),'--capture-root',os.environ['MATRIX_CAPTURE_ROOT']]}
    # Refresh native MCP configuration to point at the checkpoint-only wrapper.
    if ENGINE=='codex':
        text=(profile/'config.toml').read_text()
        old=json.dumps(['-m','vic_sdk.computer_mcp','--config',str(cfg_file)])
        (profile/'config.toml').write_text(text.replace(old,json.dumps(server['args'])))
        return original_command(engine,profile,workspace,model,server,**kwargs)
    save(profile/'mcp.json',{'mcpServers':{'vic':server}})
    if ENGINE=='claude':
        cmd,env=original_command(engine,profile,workspace,model,server,**kwargs)
        cmd+=['--effort','high']
        # No arbitrary dollar cap: retain the shared wall/action budgets.
        n=cmd.index('--max-budget-usd');del cmd[n:n+2]
        return cmd,env
    save(profile/'server.json',server)
    return [sys.executable,str(HERE/'harness_entry.py'),ENGINE,str(profile),str(workspace),model,str(profile/'server.json')],dict(native.clean_env(),MATRIX_CLI_ROOT=os.environ['MATRIX_CLI_ROOT'],ICLWORLD_API_MODEL_ID=api_model_id(model))

def summarize(engine,output,profile,session_id=None):
    if ENGINE in ('codex','claude'):return original_summarize(engine,output,profile,session_id)
    result={'engine':ENGINE,'session_id':None,'final_text':'','errors':[],'tool_calls':[],'compaction_events':[],'usage':None}
    for line in output.read_text().splitlines():
        try:e=json.loads(line)
        except ValueError:continue
        if not isinstance(e,dict):continue
        if e.get('type')=='error' or e.get('error'):result['errors'].append(e.get('error',e.get('message')))
        if e.get('is_error'):result['is_error']=True
        if e.get('type')=='result':result['final_text']=e.get('response',e.get('result',''))
        if e.get('role')=='assistant' and isinstance(e.get('content'),str):result['final_text']=e['content']
    return result

def evaluate(args,cfg,meta,result):
    meta.update(api_model_requested=api_model_id(args.model),native_harness=ENGINE,protocol='videoicl-frames-text-mcq-v2-20261101',reasoning_effort_requested='high',open_ended_diagnosis=False)
    if os.environ.get('MATRIX_NO_RULE')=='1':
        assert cfg.get('demo_video') is None
        meta.update(input_condition='no_rule',demo_representation='none')
    save(Path(cfg['output_dir'])/'manifest.json',meta)
    capture=Path(os.environ['MATRIX_CAPTURE_ROOT'])
    if (capture/'boundary-violation.json').exists():
        result.update(outcome='evaluation_error',evaluation_error={'type':'boundary_violation'})
        return result
    from finish_scoring import terminal_finish
    computer_events=[json.loads(line) for line in (Path(cfg['output_dir'])/'computer.jsonl').read_text().splitlines()] if (Path(cfg['output_dir'])/'computer.jsonl').exists() else []
    transport_events=[json.loads(line) for line in (capture/'transport.jsonl').read_text().splitlines()] if (capture/'transport.jsonl').exists() else []
    if terminal_finish(result,computer_events,transport_events,cfg.get('deadline_unix')):
        save(capture/'terminal-finish-scoring.json',{'terminal_finish_time':computer_events[-1]['time'],'deadline_unix':cfg['deadline_unix'],'scoring':'unchanged frozen authoritative grader; success and failure both accepted'})
        return original_evaluate(args,cfg,meta,result)
    if result.get('timed_out') and ENGINE!='codex':
        events=[json.loads(line) for line in (capture/'transport.jsonl').read_text().splitlines()] if (capture/'transport.jsonl').exists() else []
        if review_events(events,cfg.get('deadline_unix')):
            result.update(outcome='agent_error',execution_status='transport_timeout_requires_audit')
            result.setdefault('errors',[]).append({'message':'Transport errors during timed-out attempt; requires evidence audit before retry/scoring'})
            return result
    audit=audit_timeout(cfg['output_dir'],result)
    if audit['confirmed']:
        result.update(outcome='agent_error',execution_status='network_timeout',transport_audit=audit)
        result.setdefault('errors',[]).append({'message':'Network outage consumed execution budget; ungraded infrastructure failure'})
        return result
    from provider_errors import explicit_quota_reply
    if explicit_quota_reply(result.get('final_text','')):
        result.update(outcome='agent_error',execution_status='provider_quota')
        result.setdefault('errors',[]).append({'message':'insufficient_quota: provider returned an explicit quota notice as assistant text'})
        return result
    return original_evaluate(args,cfg,meta,result)

def run(args):
    if args.rule_diagnostic:raise ValueError('Open-ended diagnosis is forbidden')
    provider=json.loads(args.credentials.read_text())[args.engine]
    output=args.output_root.resolve();output.mkdir(parents=True,exist_ok=True)
    os.environ['MATRIX_CAPTURE_ROOT']=str(output)
    upstream=provider['base_url'].removesuffix('/v1')
    with capture_proxy(upstream,provider['api_key'],output,api_model_id(args.model)) as (base,key):
        args.base_url=base+('/v1' if ENGINE=='codex' else '')
        os.environ['MATRIX_PROXY_KEY']=key;args.api_key_env='MATRIX_PROXY_KEY'
        return original_run(args)

native.run=run;native.cli_command=cli_command;native.summarize=summarize;native.evaluate_result=evaluate
if os.environ.get('MATRIX_NO_RULE')=='1':
    original_run.__globals__.update(cli_command=cli_command,summarize=summarize,evaluate_result=evaluate)
if __name__=='__main__':native.main()
