# VulnDetect：漏洞检测模型训练与验证框架设计

> 日期：2026-06-24 | 状态：已批准

## 1. 项目概述

为甲方构建聚焦漏洞检测/修复的 LLM 后训练系统。基座模型 **Qwen-3B**，硬件 **单卡 A6000 (48GB)**，使用 QLoRA 微调。基于 OpenRLHF 框架，支持 SFT → DPO → PPO 完整训练链路。

### 1.1 核心目标

| 优先级 | 目标 | 验收标准 |
|--------|------|---------|
| P0 | 训练管线 | 单卡 A6000 跑通 Qwen-3B QLoRA SFT + DPO + PPO |
| P0 | 评测管线 | 自动运行 VulnBench、CTIBench、SecEval、CyberMetric，checkpoint 自动评估对比 |
| P1 | Web UI | 训练监控面板 + 评测报告仪表盘 + 模型对话 Playground |
| P2 | 数据管线 | REEF 风格漏洞数据持续采集（NVD、GitHub Advisory、ExploitDB），完整清洗/标注 pipeline |

### 1.2 不做的事

- 不做 14B 及以上模型的全量微调（硬件不支持）
- 不做自博弈/对抗训练（超出范围）
- 第一阶段不做 CPT（持续预训练），架构保留扩展点
- 不依赖需要联系作者才能获取的私有数据集

---

## 2. 架构设计

### 2.1 系统总览

```
React + TypeScript (Web UI, Port 5173)
        │ REST / WebSocket
        ▼
FastAPI Backend (Port 8000)
  训练管理 · 评测调度 · 模型推理 · 实验追踪
        │
   ┌────┼────┬──────────┐
   ▼    ▼     ▼          ▼
 数据  训练  评测       推理
 管线  管线  管线       服务
   │    │     │          │
   └────┴─────┴──────────┘
        │
   ┌────┴────┐
   ▼         ▼
 文件系统   SQLite
 (权重/数据) (实验/评测)
```

### 2.2 五大模块

**模块 1：数据管线（P2）**
- 采集器（Collectors）：NVD API、GitHub Advisory Database、ExploitDB
- 清洗器（Cleaners）：去重、格式标准化、敏感信息过滤
- 格式化器（Formatters）：转换为 OpenRLHF 标准格式（conversation + chosen + rejected）
- 输出：JSONL 格式，按比例划分 train/val/test

**模块 2：训练管线（P0）**
- 封装 OpenRLHF 核心模块，单卡适配
- QLoRA SFT：bitsandbytes 4-bit 量化 + PEFT LoRA
- DPO：LoRA adapter 加载，reference model 为基座模型
- PPO：QLoRA actor + critic，单卡简化版
- 配置驱动，切换训练策略只改 YAML 的 `training_strategy` 字段
- 支持断点续训、梯度检查点（gradient checkpointing）

**模块 3：评测管线（P0）**
- 封装 lm-evaluation-harness
- 内置评测集：VulnBench、CTIBench、SecEval、CyberMetric、MMLU-CompSec
- 训练过程中自动评测每个 checkpoint
- 结果持久化到 SQLite，支持多次实验对比

**模块 4：推理服务（P1）**
- 加载训练好的 LoRA adapter 做推理
- 为 Web UI Playground 提供 API
- 支持切换不同 checkpoint

**模块 5：Web UI（P1）**
- React + TypeScript + Vite
- 视觉风格：GitHub Dark（深蓝灰底 + 荧光色点缀）
- 组织方式：统一 Dashboard 首页 + 子页面导航
- 页面：Dashboard | 训练监控 | 评测报告 | 数据管理 | 模型对话

### 2.3 数据流

```
config YAML → 数据管线预处理 → OpenRLHF 格式数据
                                        │
                                        ▼
                              训练管线 (SFT/DPO/PPO)
                              │       │
                              │       ▼
                              │     checkpoint → 评测管线 → results DB
                              ▼
                         metrics → SQLite → Web UI
```

---

## 3. 技术选型

| 层级 | 技术 | 理由 |
|------|------|-----|
| 训练框架 | OpenRLHF（封装） | 甲方要求 |
| 量化 | bitsandbytes 4-bit | A6000 显存约束 |
| 微调 | PEFT (LoRA/QLoRA) | 参数高效，快速迭代 |
| 分布式 | DeepSpeed ZeRO-2 | 单卡显存优化 |
| 评测 | lm-evaluation-harness | 业界标准，评测集生态完整 |
| 后端 | FastAPI + SQLAlchemy | 异步支持，生态成熟 |
| 数据库 | SQLite | 单机零配置，满足量级 |
| 前端 | React + TypeScript + Vite | 生态丰富，组件库选择多 |
| UI 组件库 | shadcn/ui | 现代、可定制、暗色主题友好 |
| 图表 | Recharts | React 原生，轻量 |
| 样式 | Tailwind CSS | 与 shadcn/ui 深度集成 |

---

## 4. 项目结构

```
vulndetect/
├── config/                    # YAML 配置
│   ├── model/
│   │   └── qwen3b.yaml        # 模型配置（基座路径、量化参数）
│   ├── data/
│   │   └── vulnbench.yaml     # 数据集配置（来源、格式、划分）
│   ├── train/
│   │   ├── sft_qlora.yaml     # SFT 训练超参
│   │   ├── dpo.yaml           # DPO 训练超参
│   │   └── ppo.yaml           # PPO 训练超参
│   └── experiments/
│       └── exp001.yaml        # 实验配置（组合上述配置）
├── data_pipeline/             # 数据管线
│   ├── collectors/
│   │   ├── nvd.py
│   │   ├── github_advisory.py
│   │   └── exploitdb.py
│   ├── cleaners/
│   │   ├── dedup.py
│   │   └── normalizer.py
│   ├── formatters/
│   │   └── openrlhf_format.py
│   └── pipeline.py            # 数据管线入口
├── training/                  # 训练管线
│   ├── sft.py                 # QLoRA SFT 入口
│   ├── dpo.py                 # DPO 入口
│   ├── ppo.py                 # PPO 入口
│   ├── trainer.py             # 统一 Trainer 类
│   ├── checkpoint.py          # 断点续训管理
│   └── openrlhf_wrapper/      # OpenRLHF 封装层
│       ├── datasets.py        # 数据集适配
│       └── models.py          # 模型加载适配
├── evaluation/                # 评测管线
│   ├── harness.py             # lm-eval 封装
│   ├── benchmarks/
│   │   ├── vulnbench.py
│   │   ├── ctibench.py
│   │   ├── seceval.py
│   │   └── cybermetric.py
│   ├── scheduler.py           # 评测调度（checkpoint 触发）
│   └── reporter.py            # 结果汇总与对比
├── backend/                   # FastAPI 后端
│   ├── main.py                # 应用入口
│   ├── api/
│   │   ├── experiments.py     # 实验 CRUD
│   │   ├── training.py        # 训练状态 + WebSocket
│   │   ├── evaluation.py      # 评测结果查询
│   │   ├── data.py            # 数据管理
│   │   └── inference.py       # 模型推理
│   ├── models/
│   │   └── schema.py          # SQLAlchemy 模型
│   ├── services/
│   │   ├── experiment_service.py
│   │   ├── training_service.py
│   │   └── eval_service.py
│   └── database.py            # DB 连接管理
├── frontend/                  # React + TypeScript
│   ├── src/
│   │   ├── App.tsx
│   │   ├── layouts/
│   │   │   └── DashboardLayout.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── TrainingMonitor.tsx
│   │   │   ├── EvalReport.tsx
│   │   │   ├── DataManager.tsx
│   │   │   └── Playground.tsx
│   │   ├── components/        # 共享组件
│   │   ├── hooks/             # 自定义 hooks
│   │   └── lib/               # 工具函数 + API client
│   ├── package.json
│   └── vite.config.ts
├── scripts/                   # 运维脚本
│   ├── setup_env.sh           # 环境初始化
│   ├── start_train.sh         # 启动训练
│   └── start_web.sh           # 启动 Web 服务
├── experiments/               # 实验输出（gitignore）
│   └── {run_name}/
│       ├── checkpoints/
│       ├── logs/
│       └── metrics.json
├── requirements.txt           # Python 依赖
└── README.md
```

---

## 5. 配置驱动设计

### 5.1 实验配置 YAML 示例

```yaml
# config/experiments/exp001_sft_qwen3b_vulnbench.yaml
experiment:
  name: "qwen3b-sft-vulnbench-v1"
  description: "Qwen-3B QLoRA SFT on VulnBench"

model:
  base_model: "Qwen/Qwen2.5-3B-Instruct"
  load_in_4bit: true
  bnb_4bit_compute_dtype: "bfloat16"
  bnb_4bit_use_double_quant: true

training:
  strategy: sft  # sft | dpo | ppo
  sft:
    lora_r: 16
    lora_alpha: 32
    lora_dropout: 0.05
    target_modules: ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
  max_seq_length: 2048
  per_device_train_batch_size: 4
  gradient_accumulation_steps: 4
  learning_rate: 2.0e-4
  num_epochs: 3
  save_steps: 200
  eval_steps: 200
  logging_steps: 10
  warmup_ratio: 0.1
  lr_scheduler_type: "cosine"
  deepspeed_stage: 2
  gradient_checkpointing: true

data:
  train_dataset: "vulnbench"
  val_split: 0.1
  preprocessing:
    shuffle: true
    seed: 42

evaluation:
  benchmarks: ["vulnbench", "ctibench", "seceval", "cybermetric"]
  eval_on_checkpoint: true
  eval_every_n_steps: 200
```

### 5.2 策略切换

从 SFT 切换到 DPO 只需修改两处：

```yaml
training:
  strategy: dpo  # ← 改这里
  dpo:            # ← 加 DPO 配置
    beta: 0.1
    reference_model: null  # null = 基座模型
```

---

## 6. Web UI 页面设计

### 6.1 页面结构

```
Dashboard (首页)
├── 训练状态卡片（当前实验、epoch、loss、GPU 利用率）
├── 最新评测分数卡片（各 benchmark 分数、排名变化）
├── 快速入口（启动训练、模型对话）
└── 最近实验列表

训练监控
├── 实时 loss/reward 曲线（WebSocket 推送）
├── GPU 状态面板（显存、温度、利用率）
├── 训练日志流
└── 实验管理（新建、暂停、恢复、对比）

评测报告
├── Benchmark 分数表格（按实验/checkpoint 对比）
├── 雷达图（多维度能力对比）
├── 排行榜（不同实验对比）
└── 单次评测详情

数据管理
├── 数据集列表（名称、样本数、状态）
├── 数据采集面板（源配置、采集状态）
└── 数据预览（样本抽查）

模型对话 (Playground)
├── 代码输入框（粘贴代码片段）
├── 漏洞检测结果展示
├── 模型选择（切换 checkpoint）
└── 对话历史
```

### 6.2 视觉风格

- **基调**：GitHub Dark —— `#0d1117` 底 + `#161b22` 卡片 + 荧光色点缀
- **色彩语义**：绿色 `#3fb950` = 好/通过，蓝色 `#58a6ff` = 信息/训练中，红色 `#f85149` = 告警/失败
- **字体**：Inter（正文）+ JetBrains Mono（代码/数据）
- **组件库**：shadcn/ui + Tailwind CSS
- **图表**：Recharts（深色主题配色）

---

## 7. API 设计（关键端点）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/experiments` | 实验列表 |
| POST | `/api/experiments` | 创建新实验 |
| GET | `/api/experiments/{id}` | 实验详情 |
| POST | `/api/experiments/{id}/start` | 启动训练 |
| POST | `/api/experiments/{id}/pause` | 暂停训练 |
| GET | `/api/experiments/{id}/metrics` | 训练指标 |
| WS | `/ws/experiments/{id}/training` | 实时训练推送 |
| GET | `/api/experiments/{id}/evaluations` | 评测结果 |
| POST | `/api/experiments/{id}/evaluate` | 手动触发评测 |
| GET | `/api/datasets` | 数据集列表 |
| POST | `/api/datasets/collect` | 触发数据采集 |
| POST | `/api/inference/chat` | 模型对话 |
| GET | `/api/inference/checkpoints` | 可用 checkpoint 列表 |

---

## 8. 数据库模型（SQLite）

```python
# Experiments
class Experiment:
    id, name, description, config_yaml, status, created_at, updated_at

# Checkpoints
class Checkpoint:
    id, experiment_id, step, path, loss, created_at

# Metrics
class TrainingMetric:
    id, experiment_id, step, loss, learning_rate, gpu_memory_mb, timestamp

# Evaluations
class Evaluation:
    id, experiment_id, checkpoint_id, benchmark_name, score, details_json, created_at

# Datasets
class Dataset:
    id, name, source, num_samples, status, last_collected_at
```

---

## 9. 实现计划（分阶段）

### 阶段 1：环境搭建 + SFT 跑通（预计 2-3 天）

1. Python 环境搭建（PyTorch、bitsandbytes、PEFT、DeepSpeed）
2. OpenRLHF 安装与验证
3. 单卡 QLoRA SFT 脚本（封装 OpenRLHF 核心）
4. Qwen-3B SFT 跑通，验证 loss 下降

### 阶段 2：评测管线（预计 1-2 天）

5. lm-evaluation-harness 集成
6. VulnBench + CTIBench + SecEval 评测脚本
7. checkpoint 自动评测调度
8. 结果持久化 + 对比报告

### 阶段 3：RL 管线（预计 2-3 天）

9. DPO 训练脚本（基于 OpenRLHF）
10. PPO 训练脚本（单卡简化版）
11. Qwen-3B DPO + PPO 跑通验证

### 阶段 4：Web 后端（预计 1-2 天）

12. FastAPI 项目骨架 + SQLite
13. 实验 CRUD API
14. 训练状态 WebSocket
15. 推理接口

### 阶段 5：Web 前端（预计 2-3 天）

16. Vite + React + shadcn/ui 脚手架
17. Dashboard 页面
18. 训练监控页面（实时图表）
19. 评测报告页面
20. 模型对话 Playground

### 阶段 6：数据管线（预计 1-2 天）

21. NVD + GitHub Advisory 采集器
22. 数据清洗 pipeline
23. OpenRLHF 格式转换

---

## 10. 风险与约束

| 风险 | 缓解措施 |
|------|---------|
| A6000 48GB 跑 PPO 四模型显存不足 | 使用 4-bit 量化所有模型；开启 gradient checkpointing；必要时 CPU offload |
| Qwen-3B 漏洞检测能力有限 | 明确预期——3B 跑通流程验证框架，模型能力非核心目标 |
| OpenRLHF 官方脚本依赖多卡环境 | 封装层做单卡适配，不改 OpenRLHF 核心逻辑 |
| VulnBench 数据质量/量级不足 | 预留数据管线扩展接口，方便接入更多数据集 |
| 甲方可能追加需求 | 模块化架构天然支持扩展，加模块不改现有代码 |
