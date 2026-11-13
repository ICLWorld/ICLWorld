import json
from pathlib import Path
from protocol import save,digest
from export_gpt_checkpoints import prefix

def prepare(root,model,case):
 source=json.loads((root/'outputs'/model/'video'/case['name']/'receipt.json').read_text());run=Path(source['result']).parent
 assert source.get('graded') and digest(Path(source['result']))==source['result_sha256'],'QA requires a verified execution receipt'
 events=[json.loads(l) for l in (run/'computer.jsonl').read_text().splitlines()]
 viewing_only=bool(events) and all(e.get('type') in ('observation','demo_frame') for e in events)
 files=list((run/'profile/sessions').rglob('*.jsonl'));assert len(files)==1,'Need exactly one native Codex rollout'
 dest=root/'qa-checkpoints'/model/case['name'];dest.mkdir(parents=True,exist_ok=True)
 src=files[0];kept,detail=prefix(src.read_text().splitlines(keepends=True),allow_view_only=viewing_only);target=dest/src.name;target.write_text(''.join(kept));target.chmod(0o600)
 save(dest/'checkpoint.json',{'eligible':True,'checkpoint':str(target),'checkpoint_sha256':digest(target),'source_sha256':digest(src),**detail})
