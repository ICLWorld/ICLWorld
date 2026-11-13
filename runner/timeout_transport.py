"""Distinguish a deadline-cancelled client from an upstream transport failure."""
def review_events(events,deadline):
    errors=[]
    # An optional token-count capability probe may be unsupported. The native
    # CLI handles this exact response; it is not a failed model-generation call.
    # Retain slow probes for review rather than hide material budget loss.
    probes=[e for e in events if e.get('route','').endswith(':countTokens')
            and e.get('http_status')==404
            and e.get('upstream_error_type')=='invalid_request_error'
            and e.get('upstream_error_message')=='Invalid URL (POST '+e.get('route','')+')']
    known_hashes={e.get('response_sha256') for e in probes if e.get('response_sha256')}
    probe_seconds=sum(e.get('duration',0) for e in probes)
    for event in events:
        if not (event.get('error') or (event.get('http_status') or 0)>=400):continue
        cached=(event.get('source')=='cached_unsupported_endpoint'
                and event.get('upstream_called') is False
                and event.get('http_status')==404
                and event.get('route','').endswith(':countTokens')
                and event.get('response_sha256') in known_hashes)
        if probe_seconds<=60 and not event.get('error') and (event in probes or cached):continue
        # The native CLI is terminated at its fixed deadline. A subsequent
        # write to that closed client is a consequence, not a cause, of timeout.
        if (event.get('error') in ('BrokenPipeError','ConnectionResetError') and deadline is not None
                and deadline<=event.get('time',0)<=deadline+30):continue
        errors.append(event)
    return errors
