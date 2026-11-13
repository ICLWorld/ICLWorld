"""Preserve exact tool images already sent within one native Claude session."""
import copy, hashlib, json, os
from pathlib import Path

def fingerprint(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def tools(body):
    for m in body.get('messages',[]):
        if isinstance(m.get('content'),list):
            for b in m['content']:
                if b.get('type')=='tool_result' and b.get('tool_use_id'):yield b

def images(content):return [b for b in content if b.get('type')=='image']
def nonimages(content):return [b for b in content if b.get('type')!='image']

class ImageHistory:
    def __init__(self,directory):
        self.directory=Path(directory);self.directory.mkdir(exist_ok=True,mode=0o700)
        self.index={}
    def apply(self,body):
        repaired=copy.deepcopy(body);restored=[];new=[]
        for b in tools(repaired):
            ident=b['tool_use_id'];c=b.get('content');old_path=self.index.get(ident)
            if old_path:
                old=json.loads(old_path.read_text())
                if not isinstance(c,list) or nonimages(c)!=nonimages(old):
                    raise ValueError('signed tool history non-image content changed')
                current=[fingerprint(x) for x in images(c)];original=[fingerprint(x) for x in images(old)]
                # Native pruning removes image blocks; any replacement is a different fault.
                cursor=iter(original)
                if not all(any(y==x for y in cursor) for x in current):
                    raise ValueError('signed tool history image changed')
                if c!=old:
                    if len(current)>=len(original):raise ValueError('signed tool history order changed')
                    b['content']=old;restored.append({'tool_use_id':ident,'image_sha256':original})
            elif isinstance(c,list) and images(c):
                path=self.directory/(hashlib.sha256(ident.encode()).hexdigest()+'.json')
                fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                with os.fdopen(fd,'w') as f:json.dump(c,f)
                new.append((ident,path))
        for ident,path in new:self.index[ident]=path
        return repaired,{'restored_tools':restored,'cached_tools':len(self.index),
                         'native_body_sha256':fingerprint(body),'forwarded_body_sha256':fingerprint(repaired)}
