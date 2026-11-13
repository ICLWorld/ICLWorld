"""Exact provider-generated quota notices, never infer quota from model task failure."""
import re
NOTICES={
 '您的对话额度已用完，请充值后继续使用～',
 '您的对话额度已用完，请充值后继续使用~',
 '您的对话额度已用完，请充值后继续使用。',
 'API key 额度已用完',
 'Quota exceeded',
 'insufficient_quota',
}
def explicit_quota_reply(text):
 s=re.sub(r'^[\s⚠️]+','',str(text)).strip()
 return s in NOTICES

SPENDING_LIMIT_MESSAGES={
 'This API key has reached its spending limit. Adjust the limit in API key settings and enable the key to continue.',
 'Due to the usage limit set on your key, the current limit has been exhausted. Please go to the key management page to find the key, modify the limit, and activate it.',
}
def terminal_spending_limit(event):
 if event.get('http_status') not in (401,403):return False
 text=str(event.get('upstream_error_message','')).strip()
 text=re.sub(r' \(tid: [A-Za-z0-9_-]+\)$','',text)
 return text in SPENDING_LIMIT_MESSAGES or (event.get('http_status')==403 and event.get('upstream_error_code') in (None,'','insufficient_user_quota') and text=='Your account balance is insufficient. Please recharge your account to continue using the API.')
