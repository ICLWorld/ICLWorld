"""Accept a completed native QA answer after explicitly recovered reconnects."""
import json

def completed_answer(stdout, result):
    if result.get('exit_code') != 0 or result.get('timed_out'):
        return False
    events=[json.loads(line) for line in stdout.read_text().splitlines() if line.strip()]
    if not events or events[-1].get('type') != 'turn.completed':
        return False
    starts=[i for i,e in enumerate(events) if e.get('type')=='turn.started']
    if not starts:return False
    turn=events[starts[-1]:]
    messages=[e['item'].get('text') for e in turn if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
    if not messages or messages[-1]!=result.get('final_text'):return False
    errors=[e for e in turn if e.get('type') in ('error','turn.failed')]
    return all(e.get('type')=='error' and str(e.get('message','')).startswith('Reconnecting...') for e in errors)
