"""Immutable experiment identities and public/private input boundaries."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

PROTOCOL = 'videoicl-frames-text-mcq-v2-20261101'
MODELS = {
    'gpt-6-astra': ('codex', 'gpt-6-astra'),
    'claude-opus-5-5': ('claude', 'claude-opus-5-5'),
    'qwen3.8-max': ('claude', 'qwen3.8-max'),
    'kimi-k3': ('kimi', 'kimi-k3'),
    'glm-5.3-flash': ('zcode', 'glm-5.3-flash'),
    'deepseek-v4.1-flash': ('dsh', 'deepseek-v4.1-flash'),
}
# User-defined model labels and native CLI selection, local to this workspace.
_config = Path(__file__).with_name('model-config.json')
if _config.exists():
    for _label, _settings in json.loads(_config.read_text()).items():
        if _settings['engine'] not in {'codex','claude','kimi','dsh','zcode'}:
            raise ValueError('Unsupported native engine: '+_settings['engine'])
        MODELS[_label] = (_settings['engine'], _label)
SEED = 4201
TIMEOUT = 3600
MAX_ACTIONS = 800

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.chmod(0o600)
    tmp.replace(path)

def public_question(row):
    """No task id, variant, option sources or answer key enters the branch."""
    assert set(row['options']) == set('ABCD')
    return {'question': row['question'], 'options': dict(row['options'])}

def qa_prompt(row):
    q = public_question(row)
    return ('这是独立的视频理解选择题分支。停止应用操作，不执行任务；'
            '仅依据分支之前实际看到的视频画面回答，不使用应用执行结果。\n'
            + q['question'] + '\n'
            + '\n'.join(f'{k}. {q["options"][k]}' for k in 'ABCD')
            + '\n只输出一个选项字母 A、B、C 或 D，不输出推理过程或解释。')

def execution_prompt(instruction, condition, rule=None):
    assert condition in ('video', 'text', 'none')
    if condition == 'text':
        if not rule or not rule.strip():
            raise ValueError('Text condition requires its complete frozen rule')
        prefix = ('本次提供文字方法说明，不提供示范视频。下面目标中所有“示范视频”“视频”'
                  '均指以下文字给出的同一种方法；应用业务资料中的具体参数仍以业务资料为准。\n'
                  '方法说明：\n' + rule + '\n任务目标：\n')
    elif condition == 'none':
        if rule is not None:raise ValueError('No-rule input must not contain a private rule')
        prefix = '本次不提供示范视频或私有方法说明。请依据公开业务资料完成下述任务；目标中提及的示范材料不可用。\n'
    else:
        if rule is not None:
            raise ValueError('Rule text must not enter the video condition')
        prefix = ('请先查看指定示范视频的多个时间点，学习目标中要求的转换方法、分类对应关系、'
                  '选择顺序或停止条件，再完成任务。无需口头说明你归纳的方法。\n')
    return (prefix + instruction.strip() + '\n只通过 vic 的截图和坐标键鼠工具操作应用。'
            '不要读取内部状态、源码或评分答案。完成或无法继续时调用 finish。'
            f'总时限 {TIMEOUT} 秒，最多 {MAX_ACTIONS} 个输入动作。')

def validate_bank(questions, sources):
    q = {r['task']: r for r in questions}
    s = {r['name']: r for r in sources}
    assert len(q) == len(s) == 333 and q.keys() == s.keys()
    for key, row in q.items():
        assert row['video_variant'] == s[key]['variant']
        assert set(row['options']) == set('ABCD')
        assert len(set(row['options'].values())) == 4
        assert row['option_sources'][row['correct_answer']] == row['video_variant']
        assert row['correct_rule'] == row['options'][row['correct_answer']]
    return q, s
