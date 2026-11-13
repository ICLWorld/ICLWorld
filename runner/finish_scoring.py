"""Recognize a terminal MCP finish without treating a model claim as a score."""
def terminal_finish(result,events,transport,deadline):
 if not result.get('agent_finished') or not events or not deadline:return False
 if events[-1].get('type')!='finish':return False
 t=events[-1].get('time')
 if not isinstance(t,(int,float)) or not deadline-3600<=t<=deadline:return False
 # Rejected requests (including signature/identity failures) require their own audit.
 if any(x.get('route') and isinstance(x.get('http_status'),int) and x['http_status']>=400 for x in transport):return False
 return True
