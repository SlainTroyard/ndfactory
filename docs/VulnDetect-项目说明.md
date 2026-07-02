# VulnDetect 项目说明

> 漏洞检测大语言模型训练与验证框架 | 版本 0.2.0 | 2026-07-02

---

## 一、项目概述

VulnDetect 是一个**漏洞检测领域大语言模型（LLM）的训练与验证框架**，覆盖从数据采集、模型训练（SFT/DPO/PPO）、自动化评测到 Web 推理演示的完整链路。项目以 Qwen2.5-3B-Instruct 为基座模型，采用 QLoRA（4-bit 量化 + LoRA 低秩适配）高效微调方案，在单卡 A6000 (48GB) 上即可完成全部训练。

**核心目标**：通过监督微调（SFT）和偏好对齐（DPO），让通用 LLM 获得漏洞检测领域的专业能力，并在多个安全 benchmarks 上量化评估效果。

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────┐
│                    Web 前端 (React)                    │
│   Dashboard │ 训练监控 │ 评测报告 │ 数据管理 │ Playground │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP/WebSocket
┌──────────────────────┴──────────────────────────────┐
│                  Web 后端 (FastAPI)                    │
│   实验管理 │ 指标查询 │ 评测结果 │ 模型推理 (LoRA 动态加载)  │
└──────┬───────────────┬───────────────┬──────────────┘
       │               │               │
┌──────┴──────┐ ┌──────┴──────┐ ┌──────┴──────┐
│  数据管线    │ │  训练管线    │ │  评测管线    │
│ NVD/GitHub  │ │ SFT→DPO→PPO │ │  lm_eval    │
│ Advisory    │ │ QLoRA+Deep  │ │  5 benchmarks│
│ 采集→清洗    │ │ Speed ZeRO-2│ │  自动对比    │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │
       └───────────────┼───────────────┘
                       │
              ┌────────┴────────┐
              │   SQLite 数据库   │
              │ 实验/指标/评测/数据 │
              └─────────────────┘
```

### 数据流

1. **数据采集** → NVD API / GitHub Advisory GraphQL API 自动采集漏洞数据
2. **数据清洗** → 去重、严重度过滤、文本规范化
3. **格式转换** → 转为 OpenRLHF 对话格式 (JSONL)
4. **SFT 训练** → 对话式监督微调（360 条漏洞数据，3 epochs）
5. **DPO 训练** → 直接偏好优化（50 对偏好数据，1 epoch）
6. **自动化评测** → lm_eval 在 5 个安全 benchmark 上运行评测
7. **Web 展示** → Dashboard 总览 + 实时训练曲线 + 评测对比表 + 交互式 Playground

---

## 三、核心模块

### 3.1 数据管线 (`vulndetect/data_pipeline/`)

| 组件 | 功能 | 技术细节 |
|------|------|----------|
| NVD 采集器 | 从 NVD API 拉取 CVE 漏洞数据 | 分页、日期/严重度过滤 |
| GitHub Advisory 采集器 | 从 GitHub Security Advisory GraphQL API 拉取 | GraphQL 分页 |
| 去重与过滤 | 按 CVE ID 去重，按严重度分级过滤 | HIGH/CRITICAL 优先 |
| 文本规范化 | 去除 HTML 标签、合并空白 | 正则清理 |
| 格式转换 | 转换为 OpenRLHF 对话格式 | `{"messages": [{"role":"human",...},{"role":"gpt",...}]}` |

### 3.2 训练管线 (`vulndetect/training/`)

| 阶段 | 方法 | 实现 | 参数规模 |
|------|------|------|----------|
| SFT | 监督微调 | HuggingFace Trainer + QLoRA | Qwen-3B, LoRA r=16, ~12GB |
| DPO | 直接偏好优化 | **纯 PyTorch 自研实现**（不依赖 TRL）| beta=0.1, sigmoid loss |
| PPO | 近端策略优化 | TRL PPOConfig（骨架）| 待接入 reward model |

**训练加速**：DeepSpeed ZeRO-2, 4-bit NF4 量化, 双重量化, gradient checkpointing

**训练监控**：实时写入 SQLite 数据库，WebSocket 推送前端，支持双曲线（SFT/DPO）同图对比

### 3.3 评测管线 (`vulndetect/evaluation/`)

基于 lm-evaluation-harness，支持 5 个安全领域 benchmark：

| Benchmark | 含义 | 类型 |
|-----------|------|------|
| mmlu_computer_security | MMLU 计算机安全子集 | 多选题 |
| vulnbench | 漏洞检测基准 | 专业安全评测 |
| seceval | 安全评估基准 | 综合安全能力 |
| cybermetric | 网络安全度量 | 网络攻防知识 |
| ctibench | 威胁情报基准 | CTI 领域能力 |

支持**基座模型 / SFT 模型 / DPO 模型**三路对比评测，自动生成对比表格。

### 3.4 Web 后端 (`vulndetect/backend/`)

- **框架**: FastAPI + SQLAlchemy + SQLite
- **功能**:
  - 实验 CRUD（创建/启动/暂停/查询）
  - 训练指标实时查询（step, loss, learning_rate, gpu_memory）
  - 评测结果查询（benchmark, score, checkpoint step）
  - 模型推理 API（动态加载 QLoRA checkpoint，支持聊天接口）
  - WebSocket 实时推送训练状态
- **数据库**: 5 张表 —— Experiment, Checkpoint, TrainingMetric, Evaluation, Dataset

### 3.5 Web 前端 (`vulndetect/frontend/`)

- **技术栈**: React 18 + TypeScript + Vite + Tailwind CSS + Recharts + TanStack React Query
- **设计风格**: GitHub Dark 主题 (#0d1117)
- **5 个页面**:
  1. **Dashboard** — 实验总数/运行中/已完成统计卡片，自动刷新
  2. **训练监控** — 实验选择器 + 阶段筛选 + SFT/DPO 双曲线同图展示
  3. **评测报告** — 基准选择 + 多实验分数对比表 + 颜色标注
  4. **数据管理** — 数据集元信息展示 + 采集命令
  5. **Playground** — Checkpoint 自动发现 + 交互式推理对话

---

## 四、技术栈总览

| 层级 | 技术 | 版本 |
|------|------|------|
| **深度学习框架** | PyTorch + Transformers + PEFT | 2.5 / 5.12 / 0.12 |
| **量化** | BitsAndBytes (4-bit NF4) | 0.43 |
| **分布式训练** | DeepSpeed ZeRO-2 | 0.14 |
| **基座模型** | Qwen2.5-3B-Instruct | - |
| **评测框架** | lm-evaluation-harness | latest |
| **后端** | FastAPI + SQLAlchemy + SQLite | 0.112 / 2.0 / 3 |
| **实时通信** | WebSocket | 12.0 |
| **前端** | React 18 + TypeScript + Vite | 5.4 |
| **图表** | Recharts | 2.12 |
| **样式** | Tailwind CSS | 3.4 |
| **测试** | pytest | 8.0 |

---

## 五、一键运行

```bash
# 完整流程（数据清洗 → SFT → DPO → 评测 → DB 写入）
bash scripts/run_all.sh

# 单独启动 Web UI
PYTHONPATH=. uvicorn vulndetect.backend.main:app --host 0.0.0.0 --port 8000
cd vulndetect/frontend && npm run dev -- --host 0.0.0.0

# 数据采集
python -m vulndetect.data_pipeline.pipeline

# 单独训练
python -m vulndetect.training.sft --config vulndetect/config/experiments/exp001_sft.yaml
python -m vulndetect.training.dpo --config vulndetect/config/experiments/exp001_sft.yaml --sft_checkpoint experiments/qwen3b-sft-vulnbench-v1/checkpoint-27
```

---

## 六、实验配置（可复现）

实验配置文件位于 `vulndetect/config/experiments/exp001_sft.yaml`，采用模块化 YAML 设计：

```yaml
experiment:
  name: "qwen3b-sft-vulnbench-v1"
includes:
  model: "model/qwen3b.yaml"      # 基座模型 + QLoRA 配置
  training: "train/sft_qlora.yaml" # 训练超参数
data:
  preprocessing: { max_seq_length: 2048, val_split: 0.1 }
evaluation:
  benchmarks: [vulnbench, seceval]
  eval_on_checkpoint: true
  eval_every_n_steps: 200
```

通过 `includes` 机制实现模型/训练/数据的解耦复用，方便快速切换不同配置组合进行对比实验。

---

## 七、自动化脚本

| 脚本 | 功能 |
|------|------|
| `scripts/run_all.sh` | 一键完整流程：清数据 → SFT → DPO → 评测 → DB 写入 |
| `scripts/write_evals.sh` | 将已有的 eval_output 结果写入 SQLite |
| `scripts/reset.sh` | 清理 DB + experiments + eval_output（保留源码和数据） |
| `scripts/seed_eval_data.py` | 写入演示用评测数据 |
| `vulndetect/scripts/setup_env.sh` | 一键环境搭建（GPU 检测 + venv + PyTorch CUDA 12.1） |

---

## 八、评测结果示例

| Benchmark | Base (Qwen-3B) | SFT | DPO | 提升 |
|-----------|----------------|-----|-----|------|
| mmlu_computer_security | 65.2 | 71.8 | 73.4 | +8.2 |
| vulnbench | 42.1 | 58.6 | 61.3 | +19.2 |
| seceval | 38.7 | 52.4 | 55.1 | +16.4 |
| cybermetric | 44.3 | 56.9 | 58.2 | +13.9 |
| ctibench | 31.5 | 45.2 | 47.8 | +16.3 |

*注：上表为预期效果示意，实际结果见 `eval_output_*` 目录下的 lm_eval 结果文件。*

---

## 九、项目亮点

1. **完整闭环**：从数据采集到模型部署的端到端流程，一键复现
2. **高效微调**：QLoRA 4-bit 量化，单卡 A6000 (48GB) 即可完成全部训练
3. **自研 DPO**：纯 PyTorch 实现 DPO，不依赖 TRL，完全可控可调
4. **实时监控**：WebSocket 推送训练指标，前端双曲线同图对比 SFT/DPO
5. **模块化配置**：模型/训练/数据 YAML 解耦，通过 includes 组合复用
6. **多基准评测**：5 个安全 benchmark 自动化评测，基座/SFT/DPO 三路对比
7. **交互式推理**：Web Playground 支持动态加载任意 checkpoint 进行对话测试
8. **Web UI 完善**：GitHub Dark 风格，5 页 Dashboard，3-5 秒自动刷新

---

## 十、代码统计

| 类别 | 文件数 | 说明 |
|------|--------|------|
| Python 源码 | ~25 | 核心包 vulndetect（5 个子模块） |
| TypeScript/React | ~15 | 前端页面与组件 |
| 配置文件 | ~6 | YAML 模型/训练/实验配置 |
| Shell 脚本 | ~5 | 自动化流程脚本 |
| 测试文件 | ~6 | pytest 单元测试与集成测试 |
| 文档 | ~3 | 操作手册 + 工作流文档 + 项目说明 |

---

## 十一、仓库信息

- **GitHub**: https://github.com/SlainTroyard/ndfactory
- **分支**: master
- **许可证**: 待定
