"""Grade a sealed first-answer record outside the model process."""
import argparse,hashlib,json
from pathlib import Path
def grade(dataset,out):
 raw=(out/'first-valid-answer.private.json').read_bytes();answer=json.loads(raw);result=json.loads((out/'result.json').read_text())
 if result['identity']!=answer['identity'] or hashlib.sha256(raw).hexdigest()!=result['answer_sha256']:raise ValueError('Answer identity/hash mismatch')
 ledger=result['api_timing']
 if not ledger['ledger_integrity_valid'] or not ledger['transport_quiescent_confirmed'] or ledger['active'] or ledger['uncertain']:raise ValueError('Incomplete API ledger')
 data=dataset/'robot/evaluation';rows=[json.loads(x) for x in (data/'qa_questions.jsonl').read_text().splitlines()];row=next(x for x in rows if x['qa_id']==answer['identity']['qa_id'])
 if {k:row[k] for k in ('qa_id','task','variant','seed')}!=answer['identity'] or row['demonstration']['sha256']!=answer['source_sha256'] or row['question_id']!=answer['question_id'] or not answer['first_valid']:raise ValueError('Wrong QA source')
 keys=[json.loads(x) for x in (data/'author_qa_answers.jsonl').read_text().splitlines()];key=next(x for x in keys if x['task_id']==row['task'] and x['question_id']==row['question_id'])
 if answer['selected_option'] not in list('ABCD'):raise ValueError('Invalid answer')
 return {'qa_id':row['qa_id'],'correct':answer['selected_option']==key['answers'][row['variant']]}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(json.dumps(grade(a.dataset,a.out)))
