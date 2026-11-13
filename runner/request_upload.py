"""Stream a byte-identical fixed-length body with bounded writes; no re-encoding."""
from pathlib import Path
import os
CHUNK=65536

def prepare(data,headers,model,output):
 root=Path(__file__).parent
 enabled=os.environ.get('MATRIX_ENGINE')=='codex'
 if not enabled:return data,headers,False
 h={k:v for k,v in headers.items() if k.lower() not in ('content-length','transfer-encoding')};h['Content-Length']=str(len(data))
 return (data[i:i+CHUNK] for i in range(0,len(data),CHUNK)),h,True
