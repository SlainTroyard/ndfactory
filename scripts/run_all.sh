#!/bin/bash
# ============================================
# VulnDetect 完整演示流程
# 用法: bash scripts/run_all.sh
# ============================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

source venv/bin/activate
export HF_ENDPOINT=https://hf-mirror.com
export EXPERIMENT_NAME="qwen3b-sft-vulnbench-v1"

echo "=============================================="
echo " VulnDetect 完整演示流程"
echo "=============================================="

# ---- 清理旧数据 ----
echo ""
echo "[0/7] 清理旧数据 + 重启后端..."
rm -f vulndetect.db
rm -rf experiments/
rm -rf eval_output_baseline eval_output_sft eval_output_dpo
# 重启后端以释放 DB 锁
kill $(lsof -ti:8000) 2>/dev/null || true
sleep 1
cd "$PROJECT_DIR" && PYTHONPATH="$PROJECT_DIR" nohup venv/bin/uvicorn vulndetect.backend.main:app --host 0.0.0.0 --port 8000 > /tmp/vulndetect-backend.log 2>&1 &
sleep 2
echo "  已清理，后端已重启"

# ---- 初始化数据库 ----
echo ""
echo "[1/7] 初始化数据库 + 创建实验记录..."
python -c "
from vulndetect.backend.database import init_db, SessionLocal
from vulndetect.backend.models.schema import Experiment

init_db()
db = SessionLocal()
db.query(Experiment).delete()
exp = Experiment(name='$EXPERIMENT_NAME', description='Qwen-3B QLoRA SFT + DPO', status='created')
db.add(exp)
db.commit()
print(f'  Experiment: {exp.name} (id={exp.id})')
db.close()
"

# ---- SFT 训练 ----
echo ""
echo "[2/7] SFT 训练（360条漏洞数据, 3轮）..."
python -m vulndetect.training.sft --config vulndetect/config/experiments/exp001_sft.yaml

# ---- 基座评测（后台）----
echo ""
echo "[3/7] 基座模型评测（后台）..."
lm_eval --model hf --model_args "pretrained=Qwen/Qwen2.5-3B-Instruct,trust_remote_code=True" \
  --tasks mmlu_computer_security --batch_size 4 --output_path eval_output_baseline &
PID_BASE=$!
echo "   PID=$PID_BASE"

# ---- SFT 评测（后台）----
echo ""
echo "[4/7] SFT 模型评测（后台）..."
lm_eval --model hf --model_args "pretrained=Qwen/Qwen2.5-3B-Instruct,peft=experiments/$EXPERIMENT_NAME/checkpoints/final,trust_remote_code=True" \
  --tasks mmlu_computer_security --batch_size 4 --output_path eval_output_sft &
PID_SFT=$!
echo "   PID=$PID_SFT"

# ---- 生成 DPO 数据 ----
echo ""
echo "[5/7] 生成 DPO 偏好数据 + DPO 训练..."
python -c "
import json, os
with open('data/vulndetect/vulndetect_train.jsonl') as f:
    sft_data = [json.loads(l) for l in f if l.strip()]
dpo_data = []
for item in sft_data[:50]:
    convs = item['conversations']
    human = [c for c in convs if c['from'] == 'human'][0]
    gpt = [c for c in convs if c['from'] == 'gpt'][0]
    dpo_data.append({
        'conversations': [human],
        'chosen': gpt,
        'rejected': {'from': 'gpt', 'value': 'This code appears safe. No issues found.'},
    })
with open('data/vulndetect/vulndetect_train_dpo.jsonl', 'w') as f:
    for item in dpo_data:
        f.write(json.dumps(item, ensure_ascii=False) + '\n')
print(f'  DPO data: {len(dpo_data)} pairs')
"

python -m vulndetect.training.dpo --config vulndetect/config/experiments/exp001_sft.yaml \
  --sft_checkpoint experiments/$EXPERIMENT_NAME/checkpoints/final

# ---- DPO 评测（后台）----
echo ""
echo "[6/7] DPO 模型评测（后台）..."
lm_eval --model hf --model_args "pretrained=Qwen/Qwen2.5-3B-Instruct,peft=experiments/$EXPERIMENT_NAME/checkpoints/dpo-final,trust_remote_code=True" \
  --tasks mmlu_computer_security --batch_size 4 --output_path eval_output_dpo &
PID_DPO=$!
echo "   PID=$PID_DPO"

# ---- 等待所有评测完成 ----
echo ""
echo "[7/7] 等待评测完成..."
wait $PID_BASE $PID_SFT $PID_DPO 2>/dev/null
echo "  所有评测完成"

# ---- 写入 DB ----
echo ""
echo "写入评测结果到数据库..."
python -c "
from vulndetect.backend.database import SessionLocal, init_db
from vulndetect.backend.models.schema import Evaluation, Experiment
import json, glob

init_db()
db = SessionLocal()
exp = db.query(Experiment).filter(Experiment.name == '$EXPERIMENT_NAME').first()
if not exp:
    print('  Experiment not found, skipping DB write')
    db.close()
    exit()

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
                print(f'  {label}: {metrics[\"acc\"]*100:.1f}%')

db.commit()
db.close()
print('  写入完成')
"

echo ""
echo "=============================================="
echo " 全部完成!"
echo " Dashboard: http://localhost:5173"
echo " Playground checkpoint: experiments/$EXPERIMENT_NAME/checkpoints/dpo-final"
echo "=============================================="
