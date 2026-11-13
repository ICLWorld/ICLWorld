#!/usr/bin/env python3
"""Create fresh local deployment credentials; never uses evaluation-server secrets."""
import argparse,os,secrets
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,required=True);p.add_argument('--port',type=int,default=8765);a=p.parse_args()
root=Path(__file__).resolve().parents[1];dst=root/'.env';dataset=a.dataset.resolve()
assert (dataset/'metadata/tasks.json').is_file(),'Not an ICLWorld dataset'
if dst.exists():raise SystemExit('.env already exists; keep its credentials or move it explicitly')
fd=os.open(dst,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as f:f.write(f'ICLWORLD_DATASET={dataset}\nICLWORLD_PORT={a.port}\nICLWORLD_ADMIN_TOKEN={secrets.token_hex(32)}\nICLWORLD_APP_TOKEN={secrets.token_hex(32)}\n')
print('Wrote private .env; no credentials printed.')
