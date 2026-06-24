# VulnDetect 完整工作流文档

> 从零搭建 → 数据采集 → SFT 训练 → DPO 强化学习 → 评测对比 → Web 演示

---

## 一、整体流程

```
bash scripts/run_all.sh    ← 一键完成下面所有步骤
     │
     ├── 1. 清旧数据 + 重启后端 + 初始化 DB
     ├── 2. SFT 训练 (360条漏洞数据, 3轮, ~2分钟)
     ├── 3. 基座评测 (后台)
     ├── 4. SFT 评测 (后台)
     ├── 5. 生成 DPO 数据 + DPO 训练 (50对, 1轮, ~1分钟)
     ├── 6. DPO 评测 (后台)
     └── 7. 写入评测对比结果到 DB
```

---

## 二、环境搭建（仅首次）

```bash
# 1. 一键安装 Python 环境 + GPU 依赖
bash vulndetect/scripts/setup_env.sh
source venv/bin/activate

# 2. 国内 HuggingFace 镜像
export HF_ENDPOINT=https://hf-mirror.com

# 3. 前端（仅首次）
cd vulndetect/frontend && npm install
```

---

## 三、启动 Web UI

```bash
# 终端 1 — 后端
source venv/bin/activate
export HF_ENDPOINT=https://hf-mirror.com
PYTHONPATH=/home/xiaofan/ndfactory uvicorn vulndetect.backend.main:app --host 0.0.0.0 --port 8000

# 终端 2 — 前端
cd vulndetect/frontend && npm run dev
```

浏览器打开 `http://<服务器IP>:5173`

---

## 四、数据采集（仅首次）

```bash
# 采集最近 30 天 NVD 公开漏洞（MEDIUM 及以上）
python -m vulndetect.data_pipeline.pipeline \
  --output-dir data/vulndetect \
  --days-back 30 \
  --nvd-pages 10 \
  --min-severity MEDIUM
```

产物：`data/vulndetect/vulndetect_train.jsonl` + `vulndetect_val.jsonl`

---

## 五、一键演示流程

```bash
source venv/bin/activate
export HF_ENDPOINT=https://hf-mirror.com
bash scripts/run_all.sh
```

脚本自动执行：清旧数据 → SFT 训练 → DPO 训练 → 三路评测 → 写 DB。

### 分步执行

```bash
# 仅清理（保留数据和代码）
bash scripts/reset.sh

# SFT 训练
python -m vulndetect.training.sft --config vulndetect/config/experiments/exp001_sft.yaml

# DPO 训练
python -m vulndetect.training.dpo \
  --config vulndetect/config/experiments/exp001_sft.yaml \
  --sft_checkpoint experiments/qwen3b-sft-vulnbench-v1/checkpoints/final

# 评测三模型
# 基座
lm_eval --model hf --model_args "pretrained=Qwen/Qwen2.5-3B-Instruct,trust_remote_code=True" \
  --tasks mmlu_computer_security --batch_size 4 --output_path eval_output_baseline
# SFT
lm_eval --model hf --model_args "pretrained=Qwen/Qwen2.5-3B-Instruct,peft=experiments/qwen3b-sft-vulnbench-v1/checkpoints/final,trust_remote_code=True" \
  --tasks mmlu_computer_security --batch_size 4 --output_path eval_output_sft
# DPO
lm_eval --model hf --model_args "pretrained=Qwen/Qwen2.5-3B-Instruct,peft=experiments/qwen3b-sft-vulnbench-v1/checkpoints/dpo-final,trust_remote_code=True" \
  --tasks mmlu_computer_security --batch_size 4 --output_path eval_output_dpo

# 写入评测结果
bash scripts/write_evals.sh
```

---

## 六、Web UI 页面说明

### Dashboard（首页）

- 实验统计卡片：总数 / Running / Completed
- 实验列表，实时状态，5 秒自动刷新
- 状态颜色：绿=running, 蓝=completed, 红=failed, 黄=paused

### Training Monitor

- **实验选择按钮** → 选 `qwen3b-sft-vulnbench-v1`
- **阶段选择标签**：All / SFT / DPO / PPO
- **双曲线叠加显示**：蓝色=SFT loss，绿色=DPO loss
- 每个点显示 step / loss / learning rate / GPU 内存
- 3 秒实时刷新

### Evaluation

三行对比数据，每次训练完成后自动生成：

| 模型 | 分数（MMLU Computer Security） |
|------|------|
| Qwen-3B Base | ~71% |
| + LoRA SFT | ~72% |
| + SFT + DPO | ~71% |

### Data Manager

展示数据集信息：名称、路径、样本数（train 360 + val 41）、格式（OpenRLHF JSONL）。

### Playground

模型对话演示，给甲方试用的核心页面：

**Checkpoint 选择**：自动检测所有可用 checkpoint（final / dpo-final）

**示例输入 1 — 命令注入**：
```
Analyze this code for vulnerabilities:
import os
def ping_host(user_input):
    os.system("ping -c 1 " + user_input)
```

**示例输入 2 — SQL 注入**：
```
Analyze this code for vulnerabilities:
def get_user(username):
    query = "SELECT * FROM users WHERE name = '" + username + "'"
    cursor.execute(query)
    return cursor.fetchone()
```

**示例输入 3 — 路径遍历**：
```
Analyze this code for vulnerabilities:
from flask import request, send_file
@app.route('/download')
def download():
    filename = request.args.get('file')
    return send_file('/var/www/files/' + filename)
```

---

## 七、项目结构

```
vulndetect/
├── config/                  # YAML 配置（模型/数据/训练超参）
├── data_pipeline/            # NVD + GitHub 数据采集
├── training/                 # SFT / DPO / PPO 训练
├── evaluation/               # lm_eval 评测封装
├── backend/                  # FastAPI + SQLite
├── frontend/                 # React + TypeScript + GitHub Dark
├── scripts/
│   ├── setup_env.sh          # 一键环境安装
│   ├── run_all.sh            # 一键全流程
│   ├── reset.sh              # 清理训练产物
│   └── write_evals.sh        # 写入评测结果到 DB
├── experiments/              # 训练产物（checkpoint）
├── data/vulndetect/          # 训练数据（JSONL）
└── requirements.txt
```

---

## 八、API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/experiments` | 实验列表 |
| POST | `/api/experiments` | 创建实验 |
| GET | `/api/experiments/{id}` | 实验详情 |
| GET | `/api/experiments/{id}/metrics?stage=sft` | 训练指标（支持按阶段筛选） |
| GET | `/api/experiments/{id}/evaluations` | 评测结果 |
| WS | `/ws/experiments/{id}/training` | 训练状态推送 |
| POST | `/api/inference/chat` | 模型对话 |
| GET | `/api/inference/checkpoints` | 可用 checkpoint |

---

## 九、常见问题

**Q: HuggingFace 无法访问**
```bash
export HF_ENDPOINT=https://hf-mirror.com
```

**Q: 显存不足**
```yaml
# config/train/sft_qlora.yaml 中减小
per_device_train_batch_size: 1
gradient_accumulation_steps: 16
```

**Q: 端口被占用**
```bash
kill $(lsof -ti:8000)
kill $(lsof -ti:5173)
```

**Q: DPO 报错**
DPO 已改用纯 PyTorch 实现，不依赖 TRL，不会有兼容问题。

**Q: Playground 一直 Analyzing**
检查 `HF_ENDPOINT` 是否设置，后端是否重启过（首次推理需加载模型到 GPU，约 10 秒）。

**Q: 如何完全重置**
```bash
bash scripts/reset.sh   # 清 DB + 训练产物
# 然后重新跑 bash scripts/run_all.sh
```

---

## 十、快速参考

```bash
# ═══ 环境 ═══
bash vulndetect/scripts/setup_env.sh          # 首次安装
source venv/bin/activate                       # 激活环境
export HF_ENDPOINT=https://hf-mirror.com       # 国内镜像

# ═══ Web UI ═══
PYTHONPATH=/home/xiaofan/ndfactory uvicorn vulndetect.backend.main:app --host 0.0.0.0 --port 8000  # 后端
cd vulndetect/frontend && npm run dev           # 前端

# ═══ 一键演示 ═══
bash scripts/run_all.sh                        # 清数据 → SFT → DPO → 评测 → DB

# ═══ 分步 ═══
bash scripts/reset.sh                          # 清训练产物
python -m vulndetect.training.sft --config vulndetect/config/experiments/exp001_sft.yaml          # SFT
python -m vulndetect.training.dpo --config vulndetect/config/experiments/exp001_sft.yaml \        # DPO
  --sft_checkpoint experiments/qwen3b-sft-vulnbench-v1/checkpoints/final
bash scripts/write_evals.sh                    # 写评测结果
```
