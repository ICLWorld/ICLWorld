"""Offline checks for configuration, input isolation and QA branch integrity."""
import copy, importlib.util, json, os, sys, tempfile, unittest, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import httpx
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'runner'),str(ROOT/'runner/sdk')]
from protocol import execution_prompt, public_question, qa_prompt
from qa import branch_body, parse_answer
from api_model_identity import api_model_id
from capture_proxy import error_fields, capture_proxy
from glm_request_guard import inspect_request

class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.question={'question':'Which rule matches the demonstration?', 'options':dict(A='One',B='Two',C='Three',D='Four'), 'correct_answer':'B', 'correct_rule':'PRIVATE_ANSWER'}
    def test_question_excludes_evaluator_fields(self):
        self.assertEqual(set(public_question(self.question)),{'question','options'})
        self.assertNotIn('PRIVATE_ANSWER',qa_prompt(self.question))
    def test_none_rejects_private_rule(self):
        with self.assertRaises(ValueError):execution_prompt('Public task','none','private rule')
    def test_video_rejects_text_context(self):
        with self.assertRaises(ValueError):execution_prompt('Public task','video','private rule')
    def test_text_requires_complete_rule(self):
        with self.assertRaises(ValueError):execution_prompt('Public task','text','')
        self.assertIn('complete rule',execution_prompt('Public task','text','complete rule'))
    def test_qa_preserves_prefix_and_source(self):
        for route in ['/v1/messages','/v1/chat/completions']:
            source={'route':route,'body':{'messages':[{'role':'user','content':[{'type':'text','text':'viewing prefix'}]}]}}
            before=copy.deepcopy(source);_,body=branch_body(source,self.question)
            self.assertEqual(source,before);self.assertEqual(body['messages'][:-1],before['body']['messages'])
            self.assertIn(body['tool_choice'],['none',{'type':'none'}])
    def test_responses_branch_requires_exported_history(self):
        with self.assertRaises(ValueError):branch_body({'route':'/v1/responses','body':{'previous_response_id':'server-only'}},self.question)
    def test_answer_is_one_option(self):
        self.assertEqual(parse_answer(' B. '),'B')
        self.assertIsNone(parse_answer('A or B'));self.assertIsNone(parse_answer('The answer is B'))
    def test_user_api_model_is_not_restricted(self):
        with patch.dict(os.environ,{'ICLWORLD_API_MODEL_ID':'organization/custom-vision-model'}):
            self.assertEqual(api_model_id('my-model'),'organization/custom-vision-model')
    def test_user_model_label_and_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'protocol.py';p.write_bytes((ROOT/'runner/protocol.py').read_bytes())
            p.with_name('model-config.json').write_text(json.dumps({'my-model':{'engine':'codex','api_model':'custom-model'}}))
            spec=importlib.util.spec_from_file_location('configured_protocol',p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            self.assertEqual(module.MODELS['my-model'],('codex','my-model'))
    def test_inconsistent_effort_and_omitted_images_are_rejected(self):
        report=inspect_request({'reasoning_effort':'high','reasoning':{'effort':'low'},'messages':[{'role':'tool','content':'MCP image content omitted:'}]})
        self.assertIn('conflicting_nested_reasoning_effort',report['errors']);self.assertIn('native_mcp_image_omitted',report['errors'])
    def test_upstream_error_redacts_credential(self):
        secret='private-test-credential';out=error_fields(json.dumps({'error':{'message':secret}}),[secret])
        self.assertNotIn(secret,json.dumps(out))

    def test_custom_endpoint_receives_complete_request_and_stream(self):
        seen=[]
        stream=b'data: {"choices":[{"delta":{"content":"A"},"finish_reason":null}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n'
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                seen.append((self.path,self.headers.get('Authorization'),json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(stream)));self.end_headers();self.wfile.write(stream)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        payload={'model':'custom-vision-model','messages':[{'role':'user','content':'public task'}],'stream':True,'reasoning_effort':'high'}
        try:
            with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MATRIX_ENGINE':'codex','ICLWORLD_MODEL_LABEL':'my-model'}):
                with capture_proxy('http://127.0.0.1:'+str(server.server_port),'unit-test-key',Path(tmp),'custom-vision-model') as (base,key):
                    response=httpx.post(base+'/v1/chat/completions',headers={'Authorization':'Bearer '+key},json=payload,timeout=10,trust_env=False)
                    self.assertEqual(response.status_code,200);self.assertEqual(response.content,stream)
                self.assertEqual(seen,[('/v1/chat/completions','Bearer unit-test-key',payload)])
                self.assertNotIn('unit-test-key',(Path(tmp)/'transport.jsonl').read_text())
        finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
