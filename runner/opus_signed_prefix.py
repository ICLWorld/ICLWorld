"""Restore original signed input when native compaction reuses an old signature.
No thinking/tool/image bytes are removed or replaced. Only a recognized native
summary prefix can be replaced by the original prefix bound to that signature.
"""
import copy,hashlib,json,os
from pathlib import Path

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':')).encode()
def sha(x):return hashlib.sha256(canonical(x)).hexdigest()
def semantic(x):
 if isinstance(x,dict):return {k:semantic(v) for k,v in x.items() if k!='cache_control'}
 if isinstance(x,list):return [semantic(v) for v in x]
 return x
class PrefixHistory:
 def __init__(self,path):
  self.path=Path(path);self.path.mkdir(mode=0o700,exist_ok=True);self.bindings={}
 def remember(self,signature,messages):
  if not signature:return
  key=hashlib.sha256(signature.encode()).hexdigest();refs=[]
  for m in messages:
   h=sha(m);p=self.path/(h+'.json')
   if not p.exists():
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:f.write(json.dumps(m).encode())
   refs.append(h)
  if key in self.bindings and self.bindings[key]!=refs:raise ValueError('signature rebound to different prefix')
  self.bindings[key]=refs
 def apply(self,body):
  out=copy.deepcopy(body);restored=[];messages=out.get('messages',[])
  for i,m in enumerate(messages):
   if m.get('role')!='assistant' or not isinstance(m.get('content'),list):continue
   for b in m['content']:
    sig=b.get('signature') if b.get('type')=='thinking' else None
    if not sig:continue
    key=hashlib.sha256(sig.encode()).hexdigest();refs=self.bindings.get(key)
    if refs is None:continue
    prefix=[json.loads((self.path/(h+'.json')).read_text()) for h in refs]
    if semantic(messages[:i])==semantic(prefix):continue
    text='\n'.join(c.get('text','') for x in messages[:i] if x.get('role')=='user' and isinstance(x.get('content'),list) for c in x['content'] if isinstance(c,dict))
    if 'This session is being continued' not in text or len(prefix)<=i:raise ValueError('signed prefix changed outside recognized native compaction')
    tail=copy.deepcopy(messages[i:]);out['messages']=prefix+tail
    assert out['messages'][len(prefix):]==tail
    restored.append({'signature_sha256':key,'original_prefix_sha256':sha(prefix),'native_prefix_sha256':sha(messages[:i]),'restored_messages':len(prefix),'native_prefix_messages':i,'signed_tail_sha256':sha(tail)})
    # A restored prefix can contain older signed blocks; they are original bytes.
    for j,n in enumerate(out['messages']):
     if n.get('role')!='assistant' or not isinstance(n.get('content'),list):continue
     for c in n['content']:
      k=hashlib.sha256(c.get('signature','').encode()).hexdigest() if c.get('type')=='thinking' else None
      if k in self.bindings:
       expected=[json.loads((self.path/(h+'.json')).read_text()) for h in self.bindings[k]]
       if semantic(out['messages'][:j])!=semantic(expected):raise ValueError('restored signed chain mismatch')
    return out,{'restored_prefixes':restored,'known_signatures':len(self.bindings)}
  return out,{'restored_prefixes':restored,'known_signatures':len(self.bindings)}
 def observer(self,body):return SignatureObserver(self,copy.deepcopy(body.get('messages',[])))
class SignatureObserver:
 def __init__(self,history,prefix):self.history=history;self.prefix=prefix;self.buffer=b'';self.signatures={}
 def feed(self,chunk):
  self.buffer+=chunk
  while b'\n' in self.buffer:
   line,self.buffer=self.buffer.split(b'\n',1)
   if not line.startswith(b'data:'):continue
   try:e=json.loads(line[5:].strip())
   except ValueError:continue
   if e.get('type')=='content_block_start' and e.get('content_block',{}).get('type')=='thinking':self.signatures[e['index']]=e['content_block'].get('signature','')
   if e.get('type')=='content_block_delta' and e.get('delta',{}).get('type')=='signature_delta':self.signatures[e['index']]=self.signatures.get(e['index'],'')+e['delta']['signature']
   if e.get('type')=='content_block_stop':
    sig=self.signatures.get(e.get('index'))
    if sig:self.history.remember(sig,self.prefix)
