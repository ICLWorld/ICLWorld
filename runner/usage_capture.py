"""Observe provider usage without altering bytes forwarded to native CLIs."""
import json
class UsageCapture:
    def __init__(self):
        self.pending=b''; self.events=[]; self.raw={}; self.model_ids=set(); self.complete=False; self.finish_reasons=set(); self.stream_error_count=0; self.error_events=[]; self.model_output_seen=False
    def feed(self,chunk):
        self.pending+=chunk
        while b'\n' in self.pending:
            line,self.pending=self.pending.split(b'\n',1)
            self.line(line)
    def line(self,line):
        line=line.strip()
        if line==b'data: [DONE]': self.complete=True;return
        if not line.startswith(b'data:'):return
        try: d=json.loads(line[5:].strip())
        except ValueError:return
        self.consume(d)
    def consume(self,d):
        if not isinstance(d,dict):return
        # Framing completion is not business success: providers may emit error then DONE.
        if d.get('type') in ['error','response.failed'] or d.get('error'):
            self.stream_error_count+=1
            if len(self.error_events)<8:self.error_events.append(d)
        response=d.get('response')
        if isinstance(response,dict) and (response.get('error') or response.get('status')=='failed'):
            self.stream_error_count+=1
            if len(self.error_events)<8:self.error_events.append(d)
        for choice in d.get('choices',[]):
            delta=choice.get('delta',{}) if isinstance(choice,dict) else {}
            if any(delta.get(k) for k in ('content','reasoning_content','reasoning','tool_calls','function_call')):self.model_output_seen=True
        for choice in d.get('choices',[]):
            if isinstance(choice,dict) and choice.get('finish_reason'):self.finish_reasons.add(choice['finish_reason'])
        delta=d.get('delta')
        if isinstance(delta,dict) and delta.get('stop_reason'):self.finish_reasons.add(delta['stop_reason'])
        if d.get('modelVersion'):self.model_ids.add(d['modelVersion'])
        if isinstance(d.get('usageMetadata'),dict):
            self.events.append({'type':'gemini','usage':d['usageMetadata']});self.raw.update(d['usageMetadata'])
        for candidate in d.get('candidates',[]):
            reason=candidate.get('finishReason')
            if reason:self.finish_reasons.add(reason)
            if reason=='STOP':self.complete=True
        payload=d.get('message') if d.get('type')=='message_start' else d.get('response') if d.get('type')=='response.completed' else d
        if isinstance(payload,dict):
            if payload.get('model'):self.model_ids.add(payload['model'])
            u=payload.get('usage')
            if isinstance(u,dict):
                self.events.append({'type':d.get('type','chat'), 'usage':u})
                for k,v in u.items():
                    if v is not None:self.raw[k]=v
        if d.get('type') in ['message_stop','response.completed']:self.complete=True
    def finish(self):
        if self.pending:
            if self.pending.lstrip().startswith(b'{'):
                try:self.consume(json.loads(self.pending))
                except ValueError:pass
            else:self.line(self.pending)
        u=self.raw;n=None
        if 'promptTokenCount' in u:
            cached=u.get('cachedContentTokenCount',0);n={'input_total':u['promptTokenCount'],'input_cached':cached,'input_uncached':u['promptTokenCount']-cached,'output':u.get('candidatesTokenCount',0)+u.get('thoughtsTokenCount',0),'reasoning':u.get('thoughtsTokenCount',0)}
        elif 'prompt_tokens' in u:
            cached=u.get('prompt_tokens_details',{}).get('cached_tokens',u.get('prompt_cache_hit_tokens'))
            n={'input_total':u['prompt_tokens'],'input_cached':cached,'input_uncached':u.get('prompt_cache_miss_tokens',u['prompt_tokens']-cached if cached is not None else None),'output':u.get('completion_tokens'),'reasoning':u.get('completion_tokens_details',{}).get('reasoning_tokens')}
        elif 'input_tokens' in u:
            read=u.get('cache_read_input_tokens');write=u.get('cache_creation_input_tokens')
            n={'input_total':u['input_tokens']+(read or 0)+(write or 0),'input_uncached':u['input_tokens'],'input_cached':read,'input_cache_write':write,'output':u.get('output_tokens'),'reasoning':u.get('output_tokens_details',{}).get('thinking_tokens')}
        return {'usage_events':self.events,'usage_raw':u,'usage_normalized':n,'response_models':sorted(self.model_ids),'stream_completed':self.complete,'stream_error_count':self.stream_error_count,'response_valid':self.complete and self.stream_error_count==0,'finish_reasons':sorted(self.finish_reasons)}

if __name__=='__main__':
    a=UsageCapture();a.feed(b'data: {"type":"message_start","message":{"model":"q","usage":{"input_tokens":10,"cache_read_input_tokens":90,"cache_creation_input_tokens":0,"output_tokens":1}}}\n\ndata: {"type":"message_delta","usage":{"output_tokens":8}}\n\ndata: {"type":"message_stop"}\n');r=a.finish();assert r['usage_normalized']['input_total']==100 and r['usage_normalized']['output']==8 and r['stream_completed']
    a=UsageCapture();data=b'data: {"usage":{"prompt_tokens":100,"prompt_tokens_details":{"cached_tokens":80},"completion_tokens":9}}\n\ndata: [DONE]\n';[a.feed(bytes([x])) for x in data];r=a.finish();assert r['usage_normalized']['input_uncached']==20 and r['usage_normalized']['output']==9
    a=UsageCapture();a.feed(b'data: {"usage":{"prompt_tokens":100,"completion_tokens":9}}\n');assert a.finish()['usage_normalized']['input_cached'] is None
    print('usage observer: 3 checks passed')
