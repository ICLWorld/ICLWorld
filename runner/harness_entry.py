"""Configure and exec native CLIs. No replacement model/tool loop."""
import json
import os
from pathlib import Path
import sys
import subprocess
import yaml
from protocol import save
from api_model_identity import api_model_id

def command(engine,profile,workspace,model,server,base,key,prompt):
    model=api_model_id(model)
    runtime=Path(os.environ['MATRIX_CLI_ROOT'])
    env={k:v for k,v in os.environ.items() if k.lower() not in ('http_proxy','https_proxy','all_proxy') and not k.startswith(('ANTHROPIC_','CLAUDE_'))}
    env['PATH']=str(runtime/'node-v22.21.1-linux-x64/bin')+':'+env['PATH']
    server=dict(server)
    if engine=='kimi':
        env.update(KIMI_CODE_HOME=str(profile),VIC_MODEL_API_KEY=key)
        (profile/'config.toml').write_text('''default_model = "eval"
default_permission_mode = "manual"
telemetry = false
[providers.eval]
type = "openai"
base_url = "'''+base+'''/v1"
api_key_env = "VIC_MODEL_API_KEY"
[models.eval]
provider = "eval"
model = "'''+model+'''"
max_context_size = 1048576
capabilities = ["thinking", "always_thinking", "image_in", "tool_use"]
support_efforts = ["high"]
default_effort = "high"
[thinking]
enabled = true
effort = "high"
keep = "all"
[tools]
enabled = ["mcp__vic__*"]
[[permission.rules]]
decision = "allow"
pattern = "mcp__vic__*"
''')
        save(profile/'mcp.json',{'mcpServers':{'vic':server}})
        cmd=[str(runtime/'kimi/bin/kimi'),'-m','eval','--skills-dir',str(profile/'empty-skills'),'-p',prompt,'--output-format','stream-json']
    elif engine=='dsh':
        wire_model=api_model_id(model)
        env.update(DSH_HOME=str(profile),VIC_MODEL_API_KEY=key)
        patch=[{'id':'llm-pi-ai','config':{'providers':{'eval':{'apiKeyEnv':'VIC_MODEL_API_KEY','api':'openai-completions',
            'baseURL':base+'/v1','reasoning':'high','streamIdleTimeoutMs':900000,'retryPolicy':{'mode':'normal','maxRetries':1},
            'models':[{'id':wire_model,'name':wire_model,'contextWindow':1048576,'input':['text','image'],'reasoningEfforts':{'high':'high'}}]}}}},
            {'id':'agent-default-model','config':{'provider':'eval','model':wire_model}}]
        for name in ['bash','pwsh','web','subagent','subagent-fork','subagent-control','fs','fs-search','str-replace-editor','cordis',
                     'terminal','working-directory','workspace-dependencies','session-query','schedule','skill','goal','jobs','workflow','ralph','subagent-list-agents','todo','plan']:
            patch.append({'id':'tool-'+name,'disabled':True})
        patch.append({'insert':[{'id':'mcp-vic','name':'@deepseek-ai/dsh-mcp-client','config':{'serverName':'vic','transport':'stdio',**server,'failOnStartupError':True,'toolCallTimeoutMs':120000}}]})
        (profile/'patch.yml').write_text(yaml.safe_dump(patch,sort_keys=False))
        cmd=[str(runtime/'dsh/node_modules/.bin/dsh'),'--profile','headless','--patch',str(profile/'patch.yml'),'--json',prompt]
    elif engine=='zcode':
        provider=profile/'provider.private.json'
        save(provider,{'schemaVersion':1,'config':{'providerConfigRules':{'providerRules':[{'providerId':'eval','providerName':'VideoICL',
            'config':{'group':'standard-personal','access':{'type':'api-key','apiKey':key},
                'api':{'type':'openai-chat-completions','baseUrl':base+'/v1'},'personalModelIds':[model]}}]},
            'modelConfigRules':{'providerModelRules':[{'providerId':'eval','modelId':model,'config':{'properties':{'inputFormat':{'supportsImage':True}}}}],
                'manualProviderModelRules':[]},'defaultModelSelection':{'providerId':'eval','modelId':model,'options':{'reasoningLevel':'high'}}}})
        env.update(ZCODE_DATA_BASE_DIR=str(profile),ZCODE_PERSONAL_PROVIDER_CONFIG_FILE=str(provider),ZCODE_STORAGE_DIR=str(profile/'storage'),ZCODE_LOG_DIR=str(profile/'logs'))
        env['PATH']=str(runtime/'zcode-tools/node_modules/.bin')+':'+env['PATH']
        # Project configuration is in a private empty workspace, never the repository.
        save(workspace/'.zcode/config.json',{'mcp':{'servers':{'vic':{'type':'stdio',**server,'alwaysLoad':True}}},
             'features':{'memory':False,'skill':False,'subagent':False},'memory':{'use':False}})
        subprocess.run([str(runtime/'zcode-tools/node_modules/.bin/node'),str(runtime/'trust-zcode-bundle.mjs'),str(workspace)],env=env,check=True,stdout=sys.stderr)
        cmd=[str(runtime/'zcode-tools/node_modules/.bin/node'),str(runtime/'zcode-source/apps/zcode-cli/packages/cli/dist/zcode.iclworld.cjs'),
             '--prompt',prompt,'--cwd',str(workspace),'--mode','yolo','--disallowed-tools',
             'Bash Read Edit Write Agent Task WebSearch WebFetch Glob Grep List TodoWrite ToolSearch Computer Browser NodeRepl AskUserQuestion EnterPlanMode ExitPlanMode SendMessage Skill TaskOutput TaskStop TodoRead ReadSessionContext',
             '--output-format','json','--no-color']
    else:raise ValueError(engine)
    return cmd,env

if __name__=='__main__':
    engine,profile,workspace,model,server_file=sys.argv[1:]
    base=os.environ['ANTHROPIC_BASE_URL'];key=os.environ['ANTHROPIC_AUTH_TOKEN']
    cmd,env=command(engine,Path(profile),Path(workspace),model,json.loads(Path(server_file).read_text()),base,key,sys.stdin.read())
    os.execvpe(cmd[0],cmd,env)
