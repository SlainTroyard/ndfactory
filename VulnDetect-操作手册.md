# VulnDetect 操作手册

> 漏洞检测 LLM 训练与验证框架 | 版本 0.1.0 | 2026-06-24

---

## 一、系统概述

VulnDetect 是一个从零搭建的**漏洞检测模型训练与验证框架**，支持 QLoRA 微调 + DPO/PPO 强化学习全流程，配备 Web UI 进行训练监控和模型演示。

### 核心能力

| 模块 | 功能 | 状态 |
|------|------|------|
| 数据管线 | NVD + GitHub Advisory 自动采集、清洗、格式化为训练数据 | ✅ |
| 训练管线 | QLoRA SFT → DPO → PPO 完整链路，单卡 A6000 可跑 | ✅ |
| 评测管线 | lm-eval-harness 封装，CTIBench/SecEval/CyberMetric 自动评测 | ✅ |
| Web 后端 | FastAPI + SQLite，实验管理、训练状态推送、模型推理 | ✅ |
| Web 前端 | React + GitHub Dark 风格，Dashboard / 训练监控 / Playground | ✅ |

### 技术栈

- **训练**: PyTorch 2.4+, Transformers 4.44+, bitsandbytes (4-bit), PEFT (LoRA), DeepSpeed ZeRO-2, TRL
- **评测**: lm-evaluation-harness
- **后端**: FastAPI + SQLAlchemy + SQLite + WebSocket
- **前端**: React 18 + TypeScript + Vite + Recharts + Tailwind CSS
- **环境**: Python 3.11+, Node 18+, CUDA 12.x, 单卡 A6000 (48GB)

---

## 二、环境搭建

### 2.1 前置要求

- NVIDIA GPU（推荐 A6000 48GB 或更高）
- CUDA 12.1+
- Python 3.11+
- Node.js 18+
- Git

### 2.2 一键安装

```bash
# 克隆项目
cd /path/to/ndfactory

# 运行环境初始化脚本（自动检测 GPU、创建 venv、安装依赖）
bash vulndetect/scripts/setup_env.sh

# 激活虚拟环境
source venv/bin/activate
```

脚本会自动完成：
1. 检测 GPU 型号和显存
2. 创建 Python 虚拟环境
3. 安装 PyTorch (CUDA 12.1)
4. 安装所有 Python 依赖（transformers, peft, bitsandbytes, fastapi 等）

### 2.3 国内网络配置

如果服务器无法访问 HuggingFace（报 `Network is unreachable`），设置镜像：

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

建议写入 `~/.bashrc` 永久生效：
```bash
echo 'export HF_ENDPOINT=https://hf-mirror.com' >> ~/.bashrc
```

首次训练时 transformers 会自动下载 Qwen-3B 模型（约 6GB），缓存到 `~/.cache/huggingface/`。

---

## 三、数据采集

### 3.1 自动采集漏洞数据

```bash
# 采集最近 30 天发布的 CVE（MEDIUM 及以上严重度）
python -m vulndetect.data_pipeline.pipeline \
  --output-dir data/vulndetect \
  --days-back 30 \
  --nvd-pages 10

# 参数说明
# --output-dir   数据输出目录
# --days-back    采集最近 N 天发布的 CVE
# --nvd-pages    从 NVD API 拉取的页数（每页 50 条）
# --min-severity 最低严重度过滤：LOW / MEDIUM / HIGH / CRITICAL
```

### 3.2 采集 GitHub Advisory（可选）

```bash
# 需要 GitHub Personal Access Token
export GITHUB_TOKEN=ghp_xxxxxxxxxxxx

python -m vulndetect.data_pipeline.pipeline \
  --output-dir data/vulndetect \
  --days-back 60 \
  --nvd-pages 20 \
  --github-pages 3 \
  --min-severity MEDIUM
```

### 3.3 数据管线流程

```
NVD API ───────┐
               ├──→ 去重 → 严重度过滤 → 文本清洗 → 格式转换 → train/val 划分 → JSONL
GitHub Advisory┘
```

产物：
- `data/vulndetect/vulndetect_train.jsonl` — 训练集
- `data/vulndetect/vulndetect_val.jsonl` — 验证集

每条数据为 OpenRLHF 标准 conversation 格式：
```json
{
  "conversations": [
    {"from": "human", "value": "CVE ID: CVE-2026-49069 Severity: HIGH ..."},
    {"from": "gpt", "value": "This vulnerability (CVE-2026-49069) has a severity of HIGH..."}
  ]
}
```

---

## 四、模型训练

### 4.1 SFT 监督微调（第一阶段）

```bash
# 激活环境
source venv/bin/activate

# 如有网络问题
export HF_ENDPOINT=https://hf-mirror.com

# 启动训练
python -m vulndetect.training.sft --config config/experiments/exp001_sft.yaml
```

训练配置在 `vulndetect/config/experiments/exp001_sft.yaml`：

```yaml
experiment:
  name: "qwen3b-sft-vulnbench-v1"

model:
  name_or_path: "Qwen/Qwen2.5-3B-Instruct"  # 基座模型
  # QLoRA: 4-bit 量化 + LoRA (r=16, alpha=32)

training:
  strategy: sft
  per_device_train_batch_size: 4
  gradient_accumulation_steps: 4
  learning_rate: 2.0e-4
  num_epochs: 3
  save_steps: 200              # 每 200 步保存 checkpoint
```

产物：
```
experiments/qwen3b-sft-vulnbench-v1/
├── checkpoints/
│   ├── checkpoint-200/        # 每 200 步自动保存
│   ├── checkpoint-400/
│   └── final/                 # 训练完成后的最终模型
├── logs/                      # TensorBoard 日志
└── metrics.json               # 训练指标
```

### 4.2 DPO 偏好对齐（第二阶段）

```bash
python -m vulndetect.training.dpo \
  --config config/experiments/exp001_sft.yaml \
  --sft_checkpoint experiments/qwen3b-sft-vulnbench-v1/checkpoints/final
```

DPO 需要 `chosen/rejected` 格式数据。确认数据存在：
```bash
ls data/vulndetect/vulndetect_train_dpo.jsonl
```
如不存在，需先准备 DPO 格式数据（包含正确和错误的漏洞分析对比）。

### 4.3 PPO 强化学习（第三阶段，需要 Reward Model）

```bash
python -m vulndetect.training.ppo \
  --config config/experiments/exp001_sft.yaml \
  --sft_checkpoint experiments/qwen3b-sft-vulnbench-v1/checkpoints/final
```

PPO 需要 Reward Model 对模型输出打分。推荐使用规则打分（漏洞检测准确率）或单独训练的 Reward Model。

### 4.4 断点续训

训练过程支持 `Ctrl+C` 中断后恢复：

```bash
# 重新运行相同命令，自动从最新 checkpoint 恢复
python -m vulndetect.training.sft --config config/experiments/exp001_sft.yaml
```

### 4.5 换模型 / 换参数

只需修改 YAML 配置，不动代码：

```yaml
# 换成 14B 模型（需要更多显存）
model:
  name_or_path: "Qwen/Qwen2.5-14B-Instruct"

# 调整 LoRA 参数
lora:
  r: 8
  alpha: 16

# 切换训练策略
training:
  strategy: dpo   # sft → dpo → ppo
```

---

## 五、模型评测

### 5.1 对 Checkpoint 自动评测

训练过程中，评测调度器自动对新 checkpoint 运行 Benchmark：

```bash
python -m vulndetect.evaluation.scheduler \
  --experiment experiments/qwen3b-sft-vulnbench-v1 \
  --benchmarks vulnbench,seceval,cybermetric
```

### 5.2 手动评测

```bash
# 评测特定 checkpoint
python -c "
from vulndetect.evaluation.harness import run_evaluation
results = run_evaluation(
    'experiments/qwen3b-sft-vulnbench-v1/checkpoints/final',
    ['vulnbench', 'seceval'],
    'eval_output'
)
print(results)
"
```

### 5.3 生成评测报告

```python
from vulndetect.evaluation.reporter import generate_report

report = generate_report("experiments/qwen3b-sft-vulnbench-v1")
print(report)
# 输出 Markdown 格式的对比报告
```

---

## 六、Web UI 使用指南

### 6.1 启动 Web UI

需要**三个终端窗口**，或使用 tmux：

```bash
# 终端 1：FastAPI 后端
source venv/bin/activate
uvicorn vulndetect.backend.main:app --host 0.0.0.0 --port 8000

# 终端 2：React 前端
cd vulndetect/frontend
npm install   # 仅首次
npm run dev

# 终端 3：训练（可选）
source venv/bin/activate
python -m vulndetect.training.sft --config config/experiments/exp001_sft.yaml
```

### 6.2 tmux 一键启动（推荐）

```bash
tmux new -s vulndetect

# 第一块面板：训练
source venv/bin/activate
python -m vulndetect.training.sft --config config/experiments/exp001_sft.yaml

# Ctrl+b %  竖切第二块面板
source venv/bin/activate
uvicorn vulndetect.backend.main:app --host 0.0.0.0 --port 8000

# Ctrl+b "  横切第三块面板
cd vulndetect/frontend && npm run dev

# Ctrl+b d  脱离 tmux（后台运行）
# tmux attach -t vulndetect  重新连接
```

### 6.3 页面功能说明

访问 `http://<服务器IP>:5173`

#### Dashboard（首页）

```
┌─────────────────────────────────────────────────────┐
│  VulnDetect                              Dashboard  │
├──────────┬──────────┬──────────┬────────────────────┤
│  3       │  1       │  2       │                    │
│  Total   │ Running  │Completed │  快速入口           │
│  Experiments          │          │                    │
├──────────┴──────────┴──────────┴────────────────────┤
│  Recent Experiments                                  │
│  ┌─────────────────────────────────────┐            │
│  │ qwen3b-sft-vulnbench-v1  running   │            │
│  │ Qwen-3B QLoRA SFT on VulnBench     │            │
│  └─────────────────────────────────────┘            │
└─────────────────────────────────────────────────────┘
```

功能：
- **统计卡片**：实验总数、运行中、已完成数量
- **实验列表**：显示所有实验的名称、状态、描述
- **自动刷新**：每 5 秒自动拉取最新状态
- **状态颜色**：绿色=running, 蓝色=completed, 红色=failed, 黄色=paused

#### Training Monitor（训练监控）

```
┌─────────────────────────────────────────────────────┐
│  Training Monitor                                    │
│  [qwen3b-sft-v1] [exp002] [exp003]                  │
│  ┌─────────────────────────────────────────────────┐│
│  │  Loss Curve                                📈   ││
│  │  ·· ·  ··                                       ││
│  │ ·    ··    ··    ·                              ││
│  │·                ··    ··                         ││
│  │                      ··    ·                     ││
│  │                           ··                     ││
│  └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

功能：
- **实验切换**：顶部按钮切换不同实验
- **Loss 曲线**：Recharts 实时绘制，3 秒刷新
- 训练完成后会显示最终 loss 值

#### Evaluation（评测报告）

功能：
- 各 Benchmark 分数表格（CTIBench / SecEval / CyberMetric）
- 不同 Checkpoint 间对比
- 历史实验排行榜

#### Data（数据管理）

功能：
- 数据集列表及样本数
- 数据采集状态

#### Playground（模型对话演示）

```
┌─────────────────────────────────────────────────────┐
│  Model Playground                                    │
│  Checkpoint: experiments/.../final                   │
│  ┌─────────────────────────────────────────────────┐│
│  │ Paste code or ask a security question...        ││
│  │                                                 ││
│  │ import os                                       ││
│  │ user_input = request.args.get('cmd')            ││
│  │ os.system(user_input)                           ││
│  │                                                 ││
│  └─────────────────────────────────────────────────┘│
│  [Send]                                              │
│  ┌─────────────────────────────────────────────────┐│
│  │ Response:                                        ││
│  │ CVE Pattern: CWE-78 (OS Command Injection)      ││
│  │ Severity: CRITICAL                              ││
│  │ The code passes unsanitized user input to        ││
│  │ os.system() allowing arbitrary command execution ││
│  └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

功能：
- **代码粘贴分析**：粘贴代码片段，模型判断漏洞
- **安全问答**：提问安全相关问题
- **Checkpoint 切换**：选择不同训练的模型版本

---

## 七、项目结构

```
vulndetect/
├── config/                          # 所有配置文件（YAML）
│   ├── model/qwen3b.yaml             # 模型配置（基座路径、量化参数）
│   ├── data/vulnbench.yaml           # 数据集配置
│   ├── train/
│   │   ├── sft_qlora.yaml            # SFT 超参数
│   │   ├── dpo.yaml                  # DPO 超参数
│   │   └── ppo.yaml                  # PPO 超参数
│   └── experiments/
│       └── exp001_sft.yaml           # 实验配置（组合入口）
│
├── training/                         # 训练管线
│   ├── sft.py                        # SFT 训练入口
│   ├── dpo.py                        # DPO 训练入口
│   ├── ppo.py                        # PPO 训练入口
│   ├── trainer.py                    # 统一 Trainer 类
│   ├── checkpoint.py                 # 断点续训管理
│   ├── config_loader.py              # YAML 配置加载与合并
│   └── openrlhf_wrapper/             # OpenRLHF 适配层
│       ├── datasets.py               # 数据集加载/格式转换
│       └── models.py                 # QLoRA 配置/模型加载
│
├── evaluation/                       # 评测管线
│   ├── harness.py                    # lm-eval 封装
│   ├── scheduler.py                  # 自动评测调度
│   ├── reporter.py                   # 评测报告生成
│   └── benchmarks/
│       └── registry.py               # Benchmark 注册表
│
├── data_pipeline/                    # 数据采集管线
│   ├── pipeline.py                   # 管线入口（CLI）
│   ├── collectors/
│   │   ├── nvd.py                    # NVD API 采集器
│   │   └── github_advisory.py        # GitHub Advisory 采集器
│   ├── cleaners/
│   │   ├── dedup.py                  # 去重 + 严重度过滤
│   │   └── normalizer.py             # 文本清洗
│   └── formatters/
│       └── openrlhf_format.py        # → Conversation 格式
│
├── backend/                          # Web 后端
│   ├── main.py                       # FastAPI 入口
│   ├── database.py                   # SQLite 连接
│   ├── models/schema.py              # ORM 数据模型
│   ├── services/                     # 业务逻辑
│   └── api/
│       ├── experiments.py            # 实验 CRUD
│       ├── training.py               # WebSocket 推送
│       └── inference.py              # 模型推理 API
│
├── frontend/                         # Web 前端
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx                   # 路由
│       ├── layouts/
│       │   └── DashboardLayout.tsx    # GitHub Dark 布局
│       ├── pages/
│       │   ├── Dashboard.tsx          # 首页仪表盘
│       │   ├── TrainingMonitor.tsx    # 训练监控 + 曲线
│       │   ├── EvalReport.tsx         # 评测报告
│       │   ├── DataManager.tsx        # 数据管理
│       │   └── Playground.tsx         # 模型对话
│       └── lib/api.ts                # API 客户端
│
├── scripts/
│   └── setup_env.sh                  # 一键环境安装
├── tests/                            # 测试（20 项）
└── requirements.txt                  # Python 依赖
```

---

## 八、API 接口文档

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/experiments` | 实验列表 |
| POST | `/api/experiments` | 创建实验 |
| GET | `/api/experiments/{id}` | 实验详情 |
| POST | `/api/experiments/{id}/start` | 标记为运行中 |
| POST | `/api/experiments/{id}/pause` | 暂停 |
| GET | `/api/experiments/{id}/metrics` | 训练指标（loss/lr/gpu） |
| GET | `/api/experiments/{id}/evaluations` | 评测结果 |
| WS | `/ws/experiments/{id}/training` | 训练状态实时推送 |
| POST | `/api/inference/chat` | 模型对话 |
| GET | `/api/inference/checkpoints` | 可用 checkpoint 列表 |

示例：
```bash
# 创建实验
curl -X POST http://localhost:8000/api/experiments \
  -H "Content-Type: application/json" \
  -d '{"name": "my-experiment", "description": "Test"}'

# 查看状态
curl http://localhost:8000/api/experiments

# 模型推理
curl -X POST http://localhost:8000/api/inference/chat \
  -H "Content-Type: application/json" \
  -d '{"checkpoint_path": "experiments/.../final", "prompt": "分析这段代码"}'
```

---

## 九、常见问题

### Q1: HuggingFace 无法访问
```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### Q2: 显存不足 (OOM)
减小 batch size：
```yaml
# config/train/sft_qlora.yaml
per_device_train_batch_size: 1
gradient_accumulation_steps: 16  # 增大以保持有效 batch size
```

### Q3: 端口被占用
```bash
kill $(lsof -ti:8000)   # 杀掉占用 8000 端口的进程
kill $(lsof -ti:5173)   # 杀掉占用 5173 端口的进程
```

### Q4: 如何恢复中断的训练
直接重新运行相同的训练命令，Trainer 会自动检测最新 checkpoint 并从断点继续。

### Q5: 如何用 14B 模型
修改 `config/model/qwen3b.yaml`：
```yaml
model:
  name_or_path: "Qwen/Qwen2.5-14B-Instruct"
```
其他不变。14B QLoRA 在 A6000 上约需 35GB 显存。

---

## 十、快速参考卡片

```bash
# ═══ 环境 ═══
bash vulndetect/scripts/setup_env.sh   # 一键安装
source venv/bin/activate               # 激活环境
export HF_ENDPOINT=https://hf-mirror.com  # 国内镜像

# ═══ 数据 ═══
python -m vulndetect.data_pipeline.pipeline \
  --output-dir data/vulndetect --days-back 30 --nvd-pages 10

# ═══ 训练 ═══
python -m vulndetect.training.sft \
  --config config/experiments/exp001_sft.yaml

# ═══ Web ═══
# 终端 1
uvicorn vulndetect.backend.main:app --host 0.0.0.0 --port 8000
# 终端 2
cd vulndetect/frontend && npm install && npm run dev
# 浏览器打开 http://<IP>:5173

# ═══ 测试 ═══
python -m pytest vulndetect/tests/ -v
```
