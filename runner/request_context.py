"""Retain protocol headers without retaining authentication credentials."""
import json

CONTEXT_HEADERS={'anthropic-version','anthropic-beta','user-agent','x-app',
                 'x-claude-code-session-id','x-claude-code-agent-id',
                 'x-claude-code-parent-agent-id'}

def context_headers(headers):
    return {k.lower():v for k,v in headers.items() if k.lower() in CONTEXT_HEADERS}

def unsupported_count_endpoint(route,status,raw):
    """Only cache an explicit missing countTokens route, never a token count."""
    if not route.endswith(':countTokens') or status!=404:return False
    try:error=json.loads(raw)['error']
    except (ValueError,KeyError,TypeError):return False
    return (isinstance(error,dict) and error.get('type')=='invalid_request_error'
            and error.get('message')==f'Invalid URL (POST {route})')
