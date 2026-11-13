"""Validate GLM provider-bound image/effort controls; never alter model content."""
import base64,hashlib
MARKERS=('MCP image content saved instead of being inlined:', 'MCP image content omitted:')
def inspect_request(body):
    errors=[];nested=body.get('reasoning',{}).get('effort')
    if body.get('reasoning_effort')!='high':errors.append('reasoning_effort_not_high')
    if nested not in (None,'high'):errors.append('conflicting_nested_reasoning_effort')
    hashes=[]
    def inspect_images(v):
        if isinstance(v,dict):
            for x in v.values():inspect_images(x)
        elif isinstance(v,list):
            for x in v:inspect_images(x)
        elif isinstance(v,str) and v.startswith('data:image/') and ';base64,' in v:
            hashes.append(hashlib.sha256(base64.b64decode(v.split(';base64,',1)[1])).hexdigest())
    def omitted(v):
        if isinstance(v,str):return any(m in v for m in MARKERS)
        if isinstance(v,list):return any(omitted(x) for x in v)
        if isinstance(v,dict):return any(omitted(x) for x in v.values())
        return False
    for message in body.get('messages',[]):
        if message.get('role')=='tool' and omitted(message.get('content')):errors.append('native_mcp_image_omitted')
        inspect_images(message.get('content'))
    return {'errors':sorted(set(errors)), 'reasoning_effort':body.get('reasoning_effort'), 'nested_effort':nested,'image_count':len(hashes),'image_sha256':hashes}
