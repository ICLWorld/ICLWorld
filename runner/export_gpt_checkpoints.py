"""Read-only export of GPT history before rule diagnosis or environment actions."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from protocol import save, digest

BOUNDARY = re.compile(r'(?:report_inferred_rule|computer_act|computer_sequence|finish)[\"\x27\]]*\s*\(')
VIDEO_CALL = re.compile(r'demo_frame[s]?[\"\x27\]]*\s*\(')

def prefix(lines, *, allow_view_only=False):
    kept=[]
    calls={}
    frame_outputs=0
    last_video_output=None
    cutoff=None
    for n,line in enumerate(lines,1):
        event=json.loads(line)
        p=event.get('payload',{})
        if event.get('type') == 'response_item':
            typ=p.get('type','')
            if typ in ('custom_tool_call','function_call'):
                code=p.get('input',p.get('arguments',''))
                if re.search(r'(?:report_inferred_rule|computer_act|computer_sequence|finish)$',p.get('name','')) or BOUNDARY.search(code):
                    cutoff=n
                    break
                calls[p.get('call_id')]=bool(VIDEO_CALL.search(code) or re.search(r'demo_frame[s]?$',p.get('name','')))
            if typ in ('custom_tool_call_output','function_call_output') and calls.get(p.get('call_id')):
                frame_outputs+=1
                last_video_output=n
        kept.append(line)
    if not frame_outputs or cutoff is None and not allow_view_only:
        raise ValueError('No completed video-viewing checkpoint before action/diagnosis')
    if cutoff is None:
        return kept[:last_video_output], {'boundary_line':None,'retained_lines':last_video_output,'video_tool_outputs':frame_outputs,'viewing_only_terminal':True}
    # Remove assistant planning after the last completed tool result: it may
    # already spell out the rule even though report_inferred_rule was not called.
    end=max(i for i,l in enumerate(kept) if json.loads(l).get('type')=='response_item'
            and json.loads(l).get('payload',{}).get('type') in ('custom_tool_call_output','function_call_output'))+1
    return kept[:end], {'boundary_line':cutoff,'retained_lines':end,'video_tool_outputs':frame_outputs}

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();records=[]
    for receipt in sorted(a.source.glob('gpt-*/*/receipt.json')):
        r=json.loads(receipt.read_text())
        if not r.get('graded'):raise ValueError('Unfinished baseline '+str(receipt))
        result=Path(r['result_file']);run=result.parent
        rollouts=list((run/'profile/sessions').rglob('*.jsonl'))
        if len(rollouts)!=1:raise ValueError('Ambiguous original rollout '+str(run))
        src=rollouts[0];dest=a.output/r['model']/r['task'];dest.mkdir(parents=True,exist_ok=True)
        record={'model':r['model'],'task':r['task'],'receipt_sha256':digest(receipt),'result_sha256':digest(result),
                'source_rollout':str(src),'source_rollout_sha256':digest(src),'graded_baseline_preserved':True}
        try:
            with src.open() as f:lines,detail=prefix(f)
            target=dest/src.name;target.write_text(''.join(lines));target.chmod(0o600)
            record.update(detail,checkpoint=str(target),checkpoint_sha256=digest(target),eligible=True)
        except ValueError as e:
            record.update(eligible=False,error=str(e))
        save(dest/'checkpoint.json',record);records.append(record)
    save(a.output/'manifest.json',records)
    print(json.dumps({'count':len(records),'eligible':sum(r['eligible'] for r in records)}))

if __name__=='__main__':main()
