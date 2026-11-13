"""Demonstrated operating procedures and public tool prerequisites.

Tool acceptance is context-independent. The chosen organizational procedure is
used only by trusted authoring and final-state evaluation, never error hints.
"""


def pipeline_for(case, convention):
    pipeline=list(case['pipeline'])
    if convention==1:
        if case['domain'] in {'backup','storage'}:
            pipeline.insert(pipeline.index('backup'),'validate')
        else:
            operation=next(kind for kind in pipeline if kind not in {'inventory','validate'})
            pipeline.insert(pipeline.index(operation),'backup')
    if convention==2:
        pipeline.insert(pipeline.index('verify')+1,'audit')
    return pipeline


def dependencies(cases):
    """Union of legitimate tool dependencies; independent of episode context."""
    result={}
    for case in cases:
        for convention in range(3):
            pipeline=pipeline_for(case,convention)
            for i,kind in enumerate(pipeline):
                result.setdefault(kind,set()).add(pipeline[i-1] if i else None)
    return result
