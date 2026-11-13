"""Generalization is independent of task difficulty and private rule variant."""
from copy import deepcopy

VERSION='generalization-20261102'


def modes(difficulty):
    return ['R','I','E'] if difficulty in ('easy','low') else ['I','E']


def validate(difficulty, mode, recording=False):
    if recording and mode!='I':raise ValueError('示范录制保持原环境；R/I/E 仅用于执行实验')
    if mode not in modes(difficulty):raise ValueError('中长程任务只支持 I/E；局部规则示范不能作为整题复现')


def decorate(state, mode, replay=None):
    out=deepcopy(state)
    out['generalization']=dict(version=VERSION,mode=mode,surface='alternate' if mode=='E' else 'native')
    if replay:out['generalization']['replay']=replay
    return out
