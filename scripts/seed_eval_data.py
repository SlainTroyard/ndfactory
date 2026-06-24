#!/usr/bin/env python3
"""写入演示评测数据到 DB"""
from vulndetect.backend.database import SessionLocal, init_db
from vulndetect.backend.models.schema import Evaluation, Experiment

init_db()
db = SessionLocal()
exp = db.query(Experiment).filter(Experiment.name == 'qwen3b-sft-vulnbench-v1').first()

if not exp:
    print('Experiment not found!')
    exit(1)

scores = {
    'vulnbench': 0.73,
    'seceval': 0.78,
    'cybermetric_80': 0.65,
    'mmlu_computer_security': 0.70,
}

for bench, score in scores.items():
    db.add(Evaluation(
        experiment_id=exp.id,
        checkpoint_id=1,
        benchmark_name=bench,
        score=score,
        details_json={},
    ))

db.commit()
exp_name = exp.name
print(f'Done! {len(scores)} evaluation scores saved for {exp_name}.')
db.close()
