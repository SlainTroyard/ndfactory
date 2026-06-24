#!/bin/bash
# 读取所有评测结果写入数据库
set -e
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
source venv/bin/activate

EXPERIMENT_NAME="${1:-qwen3b-sft-vulnbench-v1}"

python -c "
from vulndetect.backend.database import SessionLocal, init_db
from vulndetect.backend.models.schema import Evaluation, Experiment
import json, glob

init_db()
db = SessionLocal()
exp = db.query(Experiment).filter(Experiment.name == '$EXPERIMENT_NAME').first()
if not exp:
    print('Experiment not found:', '$EXPERIMENT_NAME')
    db.close()
    exit(1)

db.query(Evaluation).filter(Evaluation.experiment_id == exp.id).delete()

results = {
    'eval_output_baseline': 'Qwen-3B Base (baseline)',
    'eval_output_sft': '+ LoRA SFT',
    'eval_output_dpo': '+ SFT + DPO',
}
for path, label in results.items():
    files = glob.glob(f'{path}/**/results_*.json', recursive=True)
    if files:
        with open(files[0]) as f:
            data = json.load(f)
        for task, metrics in data.get('results', {}).items():
            if 'acc' in metrics:
                db.add(Evaluation(experiment_id=exp.id, benchmark_name=label, score=metrics['acc'], details_json={'task': task}))
                print(f'{label}: {metrics[\"acc\"]*100:.1f}%')
    else:
        print(f'{label}: not found')

db.commit()
db.close()
print('Done! Refresh Evaluation page.')
"
