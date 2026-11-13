"""Private per-run HTTP transport recorder. Native harness owns the agent loop."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import hashlib
import json
import secrets
import os
import threading
import time
from urllib.parse import urlsplit, parse_qsl, urlencode
import httpx
from protocol import save
from usage_capture import UsageCapture
from sse_comments import CommentFilter
from request_context import context_headers,unsupported_count_endpoint

HOP={'host','content-length','connection','transfer-encoding','accept-encoding','authorization','x-api-key','x-goog-api-key'}

def error_fields(raw,secrets):
    try:error=json.loads(raw).get('error',{})
    except (ValueError,AttributeError):return {}
    if not isinstance(error,dict):return {}
    fields={}
    for key in ('type','code','message'):
        if error.get(key) is None:continue
        value=str(error[key])
        for secret in secrets:
            if secret:value=value.replace(secret,'[REDACTED]')
        fields['upstream_error_'+key]=value[:800]
    return fields

def tool_boundary(body, *, formal):
    declared=[]
    for tool in body.get('tools',[]):
        if 'functionDeclarations' in tool:
            declared.extend(x.get('name','') for x in tool['functionDeclarations'])
        else:
            declared.append(tool.get('function',tool).get('name',''))
    safe={'exit_plan_mode','list_mcp_resource_templates','list_mcp_resources','read_mcp_resource'}
    invalid=[n for n in declared if not isinstance(n,str) or not (n.startswith(('mcp__vic__','mcp_vic_')) or n in safe)]
    required={'computer_observe','computer_act','computer_sequence','demo_info','demo_frame','demo_frames','finish'}
    raw={n.removeprefix('mcp__vic__').removeprefix('mcp_vic_') for n in declared if isinstance(n,str)}
    # Native CLIs also issue tool-free title/loop-detection requests. They cannot
    # operate the application and must not replace the agent's QA checkpoint.
    missing=required-raw if formal and declared else set()
    return declared,invalid,missing

@contextmanager
def capture_proxy(upstream, api_key, output, model, *, images_lift=False):
    engine=os.environ.get('MATRIX_ENGINE','')
    label=os.environ.get('ICLWORLD_MODEL_LABEL',model)
    output=Path(output);local_key=secrets.token_urlsafe(32);lock=threading.Lock();events=output/'transport.jsonl'
    client=httpx.Client(timeout=httpx.Timeout(300,connect=30,write=900 if engine=='codex' else 300),trust_env=False)
    unsupported_counts={}
    from opus_history_images import ImageHistory
    image_history=ImageHistory(output/"signed-image-history") if label=="claude-opus-5-5" else None
    from opus_signed_prefix import PrefixHistory
    prefix_history=PrefixHistory(output/"signed-prefix-history") if label=="claude-opus-5-5" else None
    from lossless_png_transport import LosslessPNG
    png_transport=LosslessPNG(output/"lossless-png-cache") if label=="qwen3.8-max" else None
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def log_message(self,*_):pass
        def do_POST(self):self.forward()
        def do_GET(self):self.forward()
        def forward(self):
            parsed=urlsplit(self.path)
            auth=self.headers.get('Authorization','').removeprefix('Bearer ') or self.headers.get('x-api-key') or self.headers.get('x-goog-api-key') or dict(parse_qsl(parsed.query)).get('key')
            if auth!=local_key:
                self.send_error(401);return
            data=self.rfile.read(int(self.headers.get('Content-Length','0')))
            try:body=json.loads(data) if data else None
            except ValueError:body=None
            # Drop local credential query parameters and bind the configured model.
            query=urlencode([(k,v) for k,v in parse_qsl(parsed.query) if k!='key'])
            route=parsed.path+('?' + query if query else '')
            # A missing endpoint is independent of the input. Preserve the real
            # 404 for the native CLI's fallback, without repeatedly waiting on
            # a route already proven absent. No token count is synthesized.
            with lock:cached=unsupported_counts.get(route)
            if cached and time.monotonic()-cached['at']<300:
                self.send_response(404)
                self.send_header('Content-Type',cached['content_type'])
                self.send_header('Content-Length',str(len(cached['body'])))
                self.end_headers();self.wfile.write(cached['body']);self.wfile.flush()
                with lock:
                    with events.open('a') as f:f.write(json.dumps({'time':time.time(),'route':parsed.path,'model':model,
                        'http_status':404,'source':'cached_unsupported_endpoint','upstream_called':False,
                        'response_sha256':hashlib.sha256(cached['body']).hexdigest()})+'\n')
                return
            headers={k:v for k,v in self.headers.items() if k.lower() not in HOP}
            headers['Authorization']='Bearer '+api_key
            headers['x-api-key']=api_key;headers['x-goog-api-key']=api_key
            is_model=body is not None and any(s in route for s in ('/messages','/responses','/chat/completions',':generateContent',':streamGenerateContent')) and 'count_tokens' not in route
            if is_model and prefix_history is not None and (output/'boundary-violation.json').exists():
                self.send_error(409,'boundary_violation: prior signed history failure');return
            if is_model:
                checkpoint_eligible='/responses' in route
                if '/responses' not in route:
                    declared,invalid,missing=tool_boundary(body,formal=(output/'prompt.txt').exists())
                    checkpoint_eligible=bool(declared) and not invalid and not missing
                    if missing:
                        save(output/'boundary-violation.json',{'type':'missing_required_tools','names':sorted(missing),'time':time.time()})
                        self.send_error(409,'boundary_violation: missing required tools');return
                    if invalid:
                        save(output/'boundary-violation.json',{'type':'unapproved_tools','names':invalid,'time':time.time()})
                        self.send_error(409,'boundary_violation: unapproved tools');return
                actual=body.get('model')
                if actual is not None and actual!=model:
                    self.send_error(400,'Unapproved model switch');return
                if actual is None and model not in parsed.path:
                    self.send_error(400,'Model identity missing');return
                # Record the exact requested effort, independently of model names
                # such as Qwen-Max. Provider-side alias mapping is not inferred.
                if '/responses' in route:
                    body.setdefault('reasoning',{})['effort']='high'
                elif '/chat/completions' in route:
                    body['reasoning_effort']='high'
                elif '/messages' in route:
                    body.setdefault('output_config',{})['effort']='high'
                elif 'GenerateContent' in route or 'generateContent' in route:
                    cfg=body.setdefault('generationConfig',{}).setdefault('thinkingConfig',{})
                    cfg.pop('thinkingBudget',None)
                    cfg['thinkingLevel']='HIGH'
                if png_transport is not None:
                    try:
                        with lock:
                            body,png_validation=png_transport.apply(body)
                            with (output/'lossless-png-validation.jsonl').open('a') as f:
                                f.write(json.dumps(dict(time=time.time(),model=model,effort=body.get('output_config',{}).get('effort'),**png_validation))+'\n')
                    except (ValueError,OSError,AssertionError) as error:
                        save(output/'boundary-violation.json',{'type':'lossless_png_encoding','error':str(error),'time':time.time()})
                        self.send_error(409,'boundary_violation: lossless PNG encoding');return
                if images_lift:
                    from vic_sdk.anthropic_image_proxy import lift_tool_images
                    body,_=lift_tool_images(body)
                if engine=='zcode':
                    from glm_request_guard import inspect_request
                    validation=inspect_request(body)
                    with lock:
                        with (output/'request-validation.jsonl').open('a') as f:
                            f.write(json.dumps(dict(time=time.time(),model=model,**validation))+'\n')
                    if validation['errors']:
                        save(output/'boundary-violation.json',dict(type='glm_input_contract',time=time.time(),**validation))
                        self.send_error(409,'boundary_violation: GLM image/effort contract');return
                if image_history is not None and '/messages' in route:
                    try:
                        with lock:
                            body,history_validation=image_history.apply(body)
                            with (output/'image-history-validation.jsonl').open('a') as f:
                                f.write(json.dumps(dict(time=time.time(),model=model,effort=body.get('output_config',{}).get('effort'),**history_validation))+'\n')
                    except (ValueError,OSError) as error:
                        save(output/'boundary-violation.json',{'type':'signed_image_history','error':str(error),'time':time.time()})
                        self.send_error(409,'boundary_violation: signed image history');return
                if prefix_history is not None and '/messages' in route:
                    try:
                        with lock:
                            body,prefix_validation=prefix_history.apply(body)
                            with (output/'signed-prefix-validation.jsonl').open('a') as f:
                                f.write(json.dumps(dict(time=time.time(),model=model,effort=body.get('output_config',{}).get('effort'),**prefix_validation))+'\n')
                    except (ValueError,OSError) as error:
                        save(output/'boundary-violation.json',{'type':'signed_prefix_history','error':str(error),'time':time.time()})
                        self.send_error(409,'boundary_violation: signed prefix history');return
                data=json.dumps(body).encode()
                with lock:
                    if checkpoint_eligible and not (output/'video-checkpoint.json').exists():
                        save(output/'candidate-context.json',{'route':route,'body':body,'model':model,'captured_at':time.time(),
                            'request_headers':context_headers(self.headers),
                            'request_sha256':hashlib.sha256(data).hexdigest()})
            signature_observer=prefix_history.observer(body) if prefix_history is not None and is_model else None
            start=time.time();status=None;error_body=bytearray();usage_observer=UsageCapture()
            headers_at=None;first_byte_at=None;transport_error=None
            response_bytes=0;response_hash=hashlib.sha256();response_type=None;comment_filter=None
            trace_times={}
            def transport_trace(event,info):
                if event in ('http11.send_request_body.started','http11.send_request_body.complete','http11.receive_response_headers.started','http11.receive_response_headers.complete'):
                    trace_times[event]=time.time()-start
            # Keep the last Gemini stream privately for native-parser failures.
            # Never alter or repair provider bytes on the agent-facing path.
            diagnostic=bytearray() if ':streamGenerateContent' in parsed.path else None
            target=upstream.rstrip('/')+route;wire_data=data;request_headers=headers
            chunk_details={}
            try:
                from request_upload import prepare as prepare_upload
                upload_data,request_headers,segmented_upload=prepare_upload(wire_data,request_headers,model,output)
                chunk_details.update(segmented_upload=segmented_upload,upload_chunk_bytes=65536 if segmented_upload else None)
                with client.stream(self.command,target,headers=request_headers,content=upload_data,extensions={'trace':transport_trace}) as response:
                    status=response.status_code
                    headers_at=time.time()
                    response_type=response.headers.get('content-type')
                    if ':streamGenerateContent' in parsed.path and response_type and response_type.split(';')[0].strip()=='text/event-stream':
                        comment_filter=CommentFilter()
                    self.send_response(status)
                    for k,v in response.headers.items():
                        if k.lower() not in HOP and k.lower() not in ('content-encoding',):self.send_header(k,v)
                    self.send_header('Connection','close');self.end_headers()
                    for chunk in response.iter_bytes():
                        if first_byte_at is None:first_byte_at=time.time()
                        response_bytes+=len(chunk);response_hash.update(chunk)
                        if is_model:usage_observer.feed(chunk)
                        if is_model and engine=='dsh' and usage_observer.stream_error_count:
                            # Private evidence exists before native error classification; bytes untouched.
                            import os
                            early_path=output/('stream-error-'+hashlib.sha256(data).hexdigest()+'.private.json')
                            early={'time':time.time(),'route':route,'model':model,'body':body,'http_status':status,
                                'request_sha256':hashlib.sha256(data).hexdigest(),'response_sha256':response_hash.hexdigest(),
                                'error_events':usage_observer.error_events,'model_output_seen':usage_observer.model_output_seen}
                            fd=os.open(early_path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600);os.fchmod(fd,0o600)
                            with os.fdopen(fd,'w') as ef:json.dump(early,ef)

                        if signature_observer is not None and status==200:
                            try:
                                with lock:signature_observer.feed(chunk)
                            except ValueError as error:
                                save(output/'boundary-violation.json',{'type':'signed_prefix_response','error':str(error),'time':time.time()})
                                raise httpx.ProtocolError('signed prefix response violation')
                        if diagnostic is not None and len(diagnostic)<1048576:
                            diagnostic.extend(chunk[:1048576-len(diagnostic)])
                        if status>=400 and len(error_body)<65536:error_body.extend(chunk[:65536-len(error_body)])
                        forwarded=comment_filter.feed(chunk) if comment_filter else chunk
                        self.wfile.write(forwarded);self.wfile.flush()
                    if comment_filter:
                        self.wfile.write(comment_filter.finish());self.wfile.flush()
            except (httpx.HTTPError,OSError) as e:
                transport_error=type(e).__name__
                if status is None:
                    try:self.send_error(502,type(e).__name__)
                    except OSError:pass
                with lock:
                    with events.open('a') as f:f.write(json.dumps({'time':time.time(),'error':type(e).__name__,'stage':'transport','duration':time.time()-start})+'\n')
            finally:
                self.close_connection=True
                with lock:
                    details=error_fields(error_body,(api_key,local_key)) if error_body else {}
                    if is_model:details.update(usage_observer.finish())
                    if is_model and details.get('stream_error_count'):
                        # Preserve exact rejected wire input and SSE error privately.
                        # This observer never changes the bytes sent to the native CLI.
                        import os
                        request_sha=hashlib.sha256(data).hexdigest()
                        failure_path=output/f'stream-error-{request_sha}.private.json'
                        failure={'time':time.time(),'route':route,'model':model,'body':body,
                            'http_status':status,'request_sha256':request_sha,
                            'response_sha256':response_hash.hexdigest(),
                            'error_events':usage_observer.error_events,'model_output_seen':usage_observer.model_output_seen}
                        fd=os.open(failure_path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
                        os.fchmod(fd,0o600)
                        with os.fdopen(fd,'w') as f:json.dump(failure,f,ensure_ascii=False)
                        details['stream_error_evidence_file']=failure_path.name
                    if prefix_history is not None and status==400 and 'Invalid `signature` in `thinking` block' in details.get('upstream_error_message',''):
                        save(output/'boundary-violation.json',{'type':'upstream_signed_prefix_rejected','time':time.time(),'request_sha256':hashlib.sha256(data).hexdigest()})
                    if is_model:details['request_tool_count']=len(body.get('tools',[]))
                    details.update(response_bytes=response_bytes,response_sha256=response_hash.hexdigest(),response_content_type=response_type,request_bytes=len(data),request_sha256=hashlib.sha256(data).hexdigest(),transport_egress='direct',egress_wire_bytes=len(wire_data)+chunk_details.get('chunk_upload_bytes',0),transport_trace_seconds=trace_times,**chunk_details)
                    details.update(headers_after_seconds=headers_at-start if headers_at else None,
                        first_byte_after_seconds=first_byte_at-start if first_byte_at else None,
                        transport_error=transport_error)
                    if not transport_error and unsupported_count_endpoint(route,status,error_body):
                        unsupported_counts[route]={'at':time.monotonic(),'body':bytes(error_body),'content_type':response_type or 'application/json'}
                    if is_model and status is not None and status>=400:
                        # Preserve the actual rejected prefix for diagnosis;
                        # never print it or expose it to another agent session.
                        request_sha=hashlib.sha256(data).hexdigest()
                        save(output/f'rejected-request-{request_sha}.json',{'route':route,'body':body,
                            'request_headers':context_headers(self.headers),'http_status':status,
                            'request_sha256':request_sha,'error':details})
                    if comment_filter:details['sse_comment_lines_removed']=comment_filter.removed
                    if diagnostic is not None:
                        import os
                        path=output/'last-gemini-upstream.bin'
                        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
                        with os.fdopen(fd,'wb') as f:f.write(diagnostic)
                        details['diagnostic_truncated']=response_bytes>len(diagnostic)
                    with events.open('a') as f:f.write(json.dumps({'time':time.time(),'route':parsed.path,'model':model,'http_status':status,'duration':time.time()-start,**details})+'\n')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{server.server_port}',local_key
    finally:server.shutdown();server.server_close();client.close();thread.join()
