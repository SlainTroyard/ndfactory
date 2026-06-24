# VulnDetect 完整工作流文档

> 从零搭建漏洞检测 LLM 训练框架 → 数据采集 → 模型训练 → 评测对比 → Web 演示

---

## 一、整体流程

```
环境搭建 → 数据采集 → SFT训练 → 评测对比 → Web演示
  (5min)    (30s)    (2~10min)  (2min)    (持续)
```

---

## 二、环境搭建

```bash
# 1. 一键安装
bash vulndetect/scripts/setup_env.sh
source venv/bin/activate

# 2. 国内镜像
export HF_ENDPOINT=https://hf-mirror.com
```

首次运行会自动下载 Qwen-3B 模型（~6GB），缓存到 `~/.cache/huggingface/`。

---

## 三、数据采集

```bash
# 采集最近 30 天公开 CVE 漏洞数据
python -m vulndetect.data_pipeline.pipeline \
  --output-dir data/vulndetect \
  --days-back 30 \
  --nvd-pages 10 \
  --min-severity MEDIUM
```

**数据管线流程：**
```
NVD API → 去重 → 严重度过滤(>=MEDIUM) → 文本清洗 → Conversation 格式 → train/val 划分
```

产物：
- `data/vulndetect/vulndetect_train.jsonl` — 训练集
- `data/vulndetect/vulndetect_val.jsonl` — 验证集

数据格式（OpenRLHF conversation）：
```json
{
  "conversations": [
    {"from": "human", "value": "CVE ID: CVE-2024-1234 Severity: HIGH Description: Command injection in..."},
    {"from": "gpt", "value": "This vulnerability (CVE-2024-1234) has a severity of HIGH..."}
  ]
}
```

---

## 四、模型训练

### 4.1 启动训练

```bash
python -m vulndetect.training.sft --config config/experiments/exp001_sft.yaml
```

### 4.2 训练配置

```yaml
# config/experiments/exp001_sft.yaml
experiment:
  name: "qwen3b-sft-vulnbench-v1"

model:
  name_or_path: "Qwen/Qwen2.5-3B-Instruct"
  quantization: 4-bit QLoRA (bitsandbytes)
  lora: r=16, alpha=32

training:
  strategy: sft
  per_device_train_batch_size: 4
  gradient_accumulation_steps: 4
  learning_rate: 2.0e-4
  num_epochs: 3
```

### 4.3 训练产出

```
experiments/qwen3b-sft-vulnbench-v1/
├── checkpoints/
│   ├── checkpoint-69/       # 中间快照（自动保存）
│   └── final/                # 最终 LoRA 权重
└── logs/                     # TensorBoard 日志
```

### 4.4 Web UI 同步

先创建实验记录：
```bash
curl -s -X POST http://localhost:8000/api/experiments \
  -H "Content-Type: application/json" \
  -d '{"name": "qwen3b-sft-vulnbench-v1", "description": "Qwen-3B QLoRA SFT on VulnBench"}'
```

训练启动后 Web Dashboard 自动显示 `running`，每步 loss 实时写入曲线，训练完自动变 `completed`。

---

## 五、模型评测

### 5.1 评测微调后模型

```bash
lm_eval --model hf \
  --model_args "pretrained=Qwen/Qwen2.5-3B-Instruct,peft=experiments/qwen3b-sft-vulnbench-v1/checkpoints/final,trust_remote_code=True" \
  --tasks mmlu_computer_security \
  --batch_size 4
```

### 5.2 评测基座模型（对比基线）

```bash
lm_eval --model hf \
  --model_args "pretrained=Qwen/Qwen2.5-3B-Instruct,trust_remote_code=True" \
  --tasks mmlu_computer_security \
  --batch_size 4
```

### 5.3 评测结果

| 模型 | MMLU Computer Security | 说明 |
|------|----------------------|------|
| Qwen-3B（基座） | **71.0%** | 未经微调，开箱即用 |
| Qwen-3B + LoRA SFT | **72.0%** | 360 条漏洞数据 QLoRA 微调 3 轮 |
| 提升幅度 | **+1.0%** | — |

**解读：**
- 微调后安全知识能力**没有退化**（没有灾难性遗忘）
- 小幅提升说明 LoRA 在少量数据上有效保留了通用能力同时适配了安全领域
- 更大的提升需要更聚焦的评测集（如 VulnBench），而非通识类 MMLU 选择题
- 3B 小模型 + 400 条数据 + 3 轮训练 = 这个结果是合理的

> 结果写入 DB 后 Web UI 的 Evaluation 页面可直观对比基座 vs 微调分数。

---

## 六、启动 Web UI

### 6.1 启动命令

```bash
# 终端 1 — 后端
source venv/bin/activate
uvicorn vulndetect.backend.main:app --host 0.0.0.0 --port 8000

# 终端 2 — 前端
cd vulndetect/frontend
npm install    # 仅首次
npm run dev
```

浏览器打开 `http://<服务器IP>:5173`。

### 6.2 页面功能

| 页面 | 功能 | 演示要点 |
|------|------|---------|
| **Dashboard** | 实验概览：总数、运行中、已完成 | 展示系统在运行、多个实验可管理 |
| **Training Monitor** | 实时 loss 曲线、GPU 状态 | 训练过程可视化，loss 从高到低 |
| **Evaluation** | Benchmark 分数表格、对比 | 微调后 vs 基座模型的提升 |
| **Data** | 数据集信息、采集命令 | 展示数据来源（NVD 真实漏洞库） |
| **Playground** | 粘贴代码 → 模型检测漏洞 | 甲方亲手试用，最直观的演示 |

### 6.3 Playground 示例输入

```
Analyze this code for vulnerabilities:
import os
def run_command(user_input):
    os.system("ping " + user_input)
```

模型输出（示例）：
```
CWE-78: OS Command Injection. The code passes unsanitized user input 
to os.system(), allowing arbitrary command execution. 
Fix: Use subprocess.run() with a list of arguments instead.
```

---

## 七、项目结构

```
vulndetect/
├── config/                  # YAML 配置（换模型/参数只改这里）
├── data_pipeline/            # 数据采集（NVD + GitHub）
├── training/                 # 训练管线（SFT / DPO / PPO）
├── evaluation/               # 评测管线（lm_eval）
├── backend/                  # FastAPI + SQLite
├── frontend/                 # React + GitHub Dark UI
├── scripts/setup_env.sh      # 一键环境安装
└── experiments/              # 训练产物（checkpoint、日志）
```

---

## 八、常用命令速查

```bash
# 环境
bash vulndetect/scripts/setup_env.sh
source venv/bin/activate
export HF_ENDPOINT=https://hf-mirror.com

# 数据
python -m vulndetect.data_pipeline.pipeline --output-dir data/vulndetect --days-back 30 --nvd-pages 10

# 训练
python -m vulndetect.training.sft --config config/experiments/exp001_sft.yaml

# 评测（微调后）
lm_eval --model hf --model_args "pretrained=Qwen/Qwen2.5-3B-Instruct,peft=experiments/qwen3b-sft-vulnbench-v1/checkpoints/final,trust_remote_code=True" --tasks mmlu_computer_security --batch_size 4

# 评测（基座基线）
lm_eval --model hf --model_args "pretrained=Qwen/Qwen2.5-3B-Instruct,trust_remote_code=True" --tasks mmlu_computer_security --batch_size 4

# Web UI 后端
uvicorn vulndetect.backend.main:app --host 0.0.0.0 --port 8000

# Web UI 前端
cd vulndetect/frontend && npm run dev
```
