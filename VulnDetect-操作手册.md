# VulnDetect 操作手册

> 漏洞检测 LLM 训练与验证框架 | 版本 0.2.0 | 2026-06-24

---

## 一、系统概述

VulnDetect 是一个**漏洞检测模型训练与验证框架**，从数据采集到模型训练到 Web 演示全流程覆盖。

### 核心能力

| 模块 | 功能 |
|------|------|
| 数据管线 | NVD API 自动采集漏洞数据，清洗、格式化为训练数据 |
| 训练管线 | QLoRA SFT → DPO → PPO 完整链路（纯 PyTorch，不依赖 TRL） |
| 评测管线 | lm_eval 自动化评测，基座 vs SFT vs DPO 三路对比 |
| Web 后端 | FastAPI + SQLite，实验管理、实时指标推送、模型推理 |
| Web 前端 | React + GitHub Dark 风格，Dashboard / 双曲线训练监控 / Playground |

### 技术栈

- **训练**: PyTorch 2.5, Transformers 5.12, BitsAndBytes (4-bit), PEFT (LoRA), DeepSpeed ZeRO-2
- **评测**: lm-evaluation-harness
- **后端**: FastAPI + SQLAlchemy + SQLite + WebSocket
- **前端**: React 18 + TypeScript + Vite + Recharts + Tailwind CSS
- **硬件**: 单卡 A6000 (48GB)，Qwen-3B QLoRA ~12GB 显存

---

## 二、环境搭建

```bash
# 1. 一键安装
bash vulndetect/scripts/setup_env.sh
source venv/bin/activate

# 2. 国内 HuggingFace 镜像（写入 bashrc 永久生效）
echo 'export HF_ENDPOINT=https://hf-mirror.com' >> ~/.bashrc
export HF_ENDPOINT=https://hf-mirror.com

# 3. 前端依赖（仅首次）
cd vulndetect/frontend && npm install
```

---

## 三、Web UI 启动

**三个终端**（或用 tmux）：

```bash
# 终端 1 — 后端
source venv/bin/activate
export HF_ENDPOINT=https://hf-mirror.com
PYTHONPATH=/home/xiaofan/ndfactory uvicorn vulndetect.backend.main:app --host 0.0.0.0 --port 8000

# 终端 2 — 前端
cd vulndetect/frontend && npm run dev

# 终端 3 — 训练（需要时）
```

浏览器 → `http://<IP>:5173`

---

## 四、一键演示

```bash
source venv/bin/activate
export HF_ENDPOINT=https://hf-mirror.com

# 采集数据（仅首次，约 30 秒）
python -m vulndetect.data_pipeline.pipeline --output-dir data/vulndetect --days-back 30 --nvd-pages 10

# 完整训练 + 评测（约 5 分钟）
bash scripts/run_all.sh
```

---

## 五、辅助脚本

| 脚本 | 功能 |
|------|------|
| `bash scripts/setup_env.sh` | 环境安装（首次） |
| `bash scripts/run_all.sh` | 清数据 → SFT → DPO → 评测 → 写入 DB |
| `bash scripts/reset.sh` | 清训练产物的 DB（保留数据和代码） |
| `bash scripts/write_evals.sh` | 读取评测结果写入 DB |

---

## 六、Web UI 页面说明

### Dashboard
- 实验统计：总数 / Running / Completed
- 实验列表，5 秒刷新，状态颜色区分

### Training Monitor
- 选实验 → 选阶段（All/SFT/DPO/PPO）
- 蓝色=SFT loss，绿色=DPO loss，可叠加显示
- 3 秒实时刷新

### Evaluation
- 三行对比：基座 vs SFT vs DPO
- 典型结果：71% → 72% → 71%（3B 小模型 + 400 条数据）

### Data Manager
- 数据集信息：路径、样本数、格式

### Playground
- 自动检测 checkpoint（final / dpo-final）
- 粘贴代码 → 模型分析漏洞

**演示输入**：
```
Analyze this code for vulnerabilities:
import os
def ping_host(user_input):
    os.system("ping -c 1 " + user_input)
```

---

## 七、项目结构

```
vulndetect/
├── config/                     # YAML 配置
├── data_pipeline/               # 数据采集（NVD + GitHub）
├── training/                    # SFT / DPO / PPO
├── evaluation/                  # lm_eval 评测
├── backend/                     # FastAPI + SQLite
├── frontend/                    # React + GitHub Dark
├── scripts/
│   ├── setup_env.sh / run_all.sh / reset.sh / write_evals.sh
├── experiments/                 # checkpoint 输出
└── data/vulndetect/             # 训练数据
```

---

## 八、快速命令参考

```bash
# 环境
source venv/bin/activate
export HF_ENDPOINT=https://hf-mirror.com

# Web UI
PYTHONPATH=/home/xiaofan/ndfactory uvicorn vulndetect.backend.main:app --host 0.0.0.0 --port 8000
cd vulndetect/frontend && npm run dev

# 一键
bash scripts/run_all.sh

# 分步
bash scripts/reset.sh
python -m vulndetect.training.sft --config vulndetect/config/experiments/exp001_sft.yaml
python -m vulndetect.training.dpo --config vulndetect/config/experiments/exp001_sft.yaml --sft_checkpoint experiments/qwen3b-sft-vulnbench-v1/checkpoints/final
bash scripts/write_evals.sh

# 问题排查
kill $(lsof -ti:8000)   # 释放端口
rm -f vulndetect.db     # 清数据库
```
