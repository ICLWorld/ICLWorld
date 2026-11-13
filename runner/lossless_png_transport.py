"""Lossless PNG serialization; preserve image count, dimensions and every pixel."""
import base64,copy,hashlib,io,json,os
from pathlib import Path
from PIL import Image
class LosslessPNG:
 def __init__(self,path):self.path=Path(path);self.path.mkdir(mode=0o700,exist_ok=True);self.index={}
 def apply(self,body):
  out=copy.deepcopy(body);records=[]
  def walk(x):
   if isinstance(x,dict):
    if x.get('type')=='image' and x.get('source',{}).get('type')=='base64' and x['source'].get('media_type')=='image/png':
     s=x['source'];raw=base64.b64decode(s['data'],validate=True);key=hashlib.sha256(raw).hexdigest()
     if key not in self.index:
      im=Image.open(io.BytesIO(raw));im.load();assert im.format=='PNG';buf=io.BytesIO();im.save(buf,format='PNG',optimize=True,compress_level=9);packed=buf.getvalue();check=Image.open(io.BytesIO(packed));check.load()
      if not(im.mode==check.mode and im.size==check.size and im.tobytes()==check.tobytes() and im.convert('RGBA').tobytes()==check.convert('RGBA').tobytes()):raise ValueError('PNG pixel identity mismatch')
      metadata_keys=('icc_profile','gamma','srgb','transparency')
      if any(im.info.get(k)!=check.info.get(k) for k in metadata_keys):packed=raw
      if len(packed)>=len(raw):packed=raw
      p=self.path/(key+'.png');fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
      with os.fdopen(fd,'wb') as f:f.write(packed)
      self.index[key]={'original_sha256':key,'encoded_sha256':hashlib.sha256(packed).hexdigest(),'original_bytes':len(raw),'encoded_bytes':len(packed),'size':list(im.size),'mode':im.mode,'pixels_sha256':hashlib.sha256(im.convert('RGBA').tobytes()).hexdigest(),'pixels_identical':True,'color_metadata_preserved':True,'path':str(p)}
     rec=self.index[key];packed=Path(rec['path']).read_bytes();assert hashlib.sha256(packed).hexdigest()==rec['encoded_sha256'];s['data']=base64.b64encode(packed).decode();records.append({k:v for k,v in rec.items() if k!='path'})
    for v in x.values():walk(v)
   elif isinstance(x,list):
    for v in x:walk(v)
  walk(out)
  return out,{'images':records,'image_count':len(records),'native_body_sha256':hashlib.sha256(json.dumps(body).encode()).hexdigest(),'forwarded_body_sha256':hashlib.sha256(json.dumps(out).encode()).hexdigest()}
