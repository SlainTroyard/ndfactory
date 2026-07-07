# VulnDetect 训练流程总览

> 2026-07-07 | 从数据到模型的完整链路

---

## 一、总览

```
                        数据层
                          │
    ┌─────────────────────┼─────────────────────┐
    ▼                     ▼                     ▼
 REEF 数据           NVD 数据             种子数据
(4,466条真实CVE)   (447条低质量)       (607条合成代码)
    │                     │                     │
    │  Phase 2            │  将被替换            │  暂缓
    │  Claude Opus        │                     │
    ▼                     │                     │
 ① CWE 标注              │                     │
 ② 描述重写              │                     │
 ③ 推理链生成            │                     │
    │                     │                     │
    └─────────┬───────────┘                     │
              ▼                                 │
        训练数据集                               │
    (OpenRLHF conversation 格式)                 │
              │                                 │
    ┌─────────┼─────────┐                       │
    ▼         ▼         ▼                       │
  SFT       DPO       PPO                       │
(已有)    (已有)    (骨架)                       │
    │         │         │                       │
    └─────────┼─────────┘                       │
              ▼                                 │
        评测 & 验证                              │
    ┌─────────┼─────────┐                       │
    ▼         ▼         ▼                       │
lm_eval  code_analysis  VulnBench               │
(5基准)   (自定义)      (甲方指定)               │
```

---

## 二、数据层

### 2.1 数据来源

| 数据源 | 数量 | 质量 | 状态 | 用途 |
|--------|------|------|------|------|
| **REEF** | 4,466 条 | 真实 CVE + patch，LLM_message 质量一般 | ✅ 已导入 `data/reef/reef_cleaned.jsonl` | **主力训练数据** |
| NVD | 447 条 | GPT 回复仅一句话，低质量 | ⚠️ 将被替换 | 当前基线（组 B） |
| 种子数据 | 607 条 | 合成代码片段 | 🔄 暂缓 | 安全代码场景补充 |

### 2.2 REEF 数据结构（导入后）

```json
{
  "cve_id": "CVE-2023-0493",
  "description": "原始 LLM_message（将被 Claude 重写）",
  "severity": "HIGH",
  "cvss_score": "8.8",
  "language": "C#",
  "cwe_ids": ["CWE-76"],
  "needs_cwe_classification": false,
  "code_snippet": "修复后的完整文件内容...",
  "fix": "unified diff 格式的补丁...",
  "origin_message": "原始 git commit message",
  "_is_multi_file": true
}
```

### 2.3 Claude Opus 处理管线（Phase 2，待执行）

```
REEF 4,466 条
    │
    ├── ① CWE 标注 (231 条 needs_cwe_classification=True)
    │     输入：code_snippet + fix + description
    │     输出：推断的 CWE-ID
    │
    ├── ② 描述重写 (全部 4,466 条)
    │     输入：code_snippet + fix + origin_message
    │     输出：结构化的高质量漏洞描述
    │
    └── ③ 推理链生成 (全部 4,466 条)
          输入：code_snippet + fix
          输出：7 部分安全审计推理链
              ## 1. 漏洞定位
              ## 2. 漏洞类型 (CWE-ID)
              ## 3. 根因分析
              ## 4. 利用场景
              ## 5. 严重度评估 (CVSS)
              ## 6. 修复方案
              ## 7. 预防建议
```

### 2.4 训练数据格式

所有数据最终转换为 **OpenRLHF conversation 格式**：

```json
{
  "conversations": [
    {
      "from": "human",
      "value": "请分析以下 Python 代码是否存在安全漏洞：\n```python\nquery = 'SELECT * FROM users WHERE id = ' + user_id\n```"
    },
    {
      "from": "gpt",
      "value": "## 1. 漏洞定位\n第 1 行：query = 'SELECT * FROM users WHERE id = ' + user_id\n\n## 2. 漏洞类型\nCWE-ID: CWE-89: SQL 注入\n..."
    }
  ]
}
```

---

## 三、训练层

### 3.1 模型架构

```
基座模型: Qwen/Qwen2.5-3B-Instruct
    │
    ├── 4-bit NF4 量化 (BitsAndBytes)
    ├── LoRA 适配器 (r=16, alpha=32, dropout=0.05)
    │   目标模块: q_proj, k_proj, v_proj, o_proj,
    │             gate_proj, up_proj, down_proj
    ├── DeepSpeed ZeRO-2
    └── Gradient Checkpointing

显存占用: ~12 GB (单卡 A6000 48GB 完全够用)
最大序列长度: 4096 tokens
```

### 3.2 训练阶段

| 阶段 | 命令 | 说明 | 耗时 |
|------|------|------|------|
| **SFT** | `python -m vulndetect.training.sft --config <exp>.yaml` | QLoRA 监督微调，HuggingFace Trainer | ~2h (4K条/3epoch) |
| **DPO** | `python -m vulndetect.training.dpo --config <exp>.yaml --sft_checkpoint <path>` | 直接偏好优化，纯 PyTorch 自研 | ~1h |
| **PPO** | 骨架已有，待完善 | 近端策略优化 | 待定 |

### 3.3 实验配置体系

```
vulndetect/config/
├── model/qwen3b.yaml           ← 模型 + QLoRA 配置
├── train/sft_qlora.yaml        ← SFT 超参 (lr=2e-4, batch=16, epochs=3)
├── train/dpo.yaml              ← DPO 超参 (beta=0.1, batch=16, epochs=1)
├── train/ppo.yaml              ← PPO 超参 (骨架)
└── experiments/
    ├── exp001_sft.yaml          ← 基线 (NVD 数据)
    ├── exp002_distil_sft.yaml   ← 蒸馏 SFT (REEF 推理链)
    └── exp003_distil_dpo.yaml   ← 蒸馏 DPO (REEF 偏好对)
```

### 3.4 训练监控

- 指标实时写入 SQLite（`vulndetect.db`）
- WebSocket 推送前端 Dashboard
- 前端双曲线实时对比（SFT/DPO loss）
- TensorBoard 日志

---

## 四、评测层

### 4.1 评测矩阵

| 评测 | 类型 | 题目数 | 指标 | 状态 |
|------|------|--------|------|------|
| **lm_eval × 5** | 选择题/知识问答 | 不等 | accuracy, F1 | ✅ 已集成 |
| mmlu_compsec | 计算机安全知识 | ~100 | accuracy | ✅ |
| vulnbench | 漏洞检测 | - | accuracy, F1 | ✅ |
| seceval | 9 领域安全 | - | accuracy | ✅ |
| cybermetric | 网络安全 | - | accuracy | ✅ |
| ctibench | 威胁情报 | - | accuracy | ✅ |
| **code_vuln_analysis** | 代码分析生成 | 100 | Recall/Precision/F1/FPR | ✅ 已实现 |
| **VulnBench** | 漏洞修复补丁生成 | 200/1650 | Pass Rate | 🔜 待集成 |

### 4.2 评测命令

```bash
# lm_eval 通用评测
python -m vulndetect.evaluation.harness \
  --model experiments/<exp>/checkpoints/final \
  --tasks vulnbench,seceval,mmlu_compsec,cybermetric,ctibench \
  --output eval_output_<name>/

# 自定义代码分析评测
python -m vulndetect.evaluation.benchmarks.code_analysis \
  --model experiments/<exp>/checkpoints/final \
  --eval-set data/distil/samples_eval.jsonl \
  --output eval_output_<name>/code_vuln_analysis.json

# VulnBench (甲方指定，待集成)
python -m benchmark.run_eval \
  --benchmark data/benchmark/vulnbench_200.json \
  --model <our-model> \
  --judge-model openrouter/deepseek/deepseek-chat-v3
```

### 4.3 实验对照设计

| 组 | 名称 | 训练数据 | 数据量 | 目的 |
|---|------|---------|--------|------|
| A | Baseline | 无（基座原始） | 0 | 能力天花板 |
| B | NVD-SFT | NVD CVE 描述 | ~400 | 当前方案基线 |
| C | REEF-Desc | Claude 重写的漏洞描述 | ~4,000 | 真实数据 vs NVD |
| D | REEF-Reason | Claude 生成的推理链 | ~4,000 | **核心假设** |
| E | REEF-Mix | 描述 + 推理链混合 | ~8,000 | 混合效果 |

---

## 五、执行进度

| 步骤 | 内容 | 状态 |
|------|------|------|
| 代码开发 | prompts/teacher/validator/pipeline/code_analysis | ✅ 完成 |
| 平台验证 | 21 个单元测试通过，模块导入正常 | ✅ 完成 |
| Phase 1 | REEF 数据导入（4,466 条 → `reef_cleaned.jsonl`） | ✅ 完成 |
| Phase 2 | Claude Opus 处理（CWE标注+描述重写+推理链） | 🔜 等待 API Key |
| Phase 3 | 基线训练 + 评测（组 A + 组 B） | 🔜 可与 Phase 2 并行 |
| Phase 4 | 蒸馏训练（组 C/D/E） | 🔜 依赖 Phase 2 |
| Phase 5 | VulnBench 环境搭建 | 🔜 待执行 |
| Phase 6 | 结果分析 + 实验报告 | 🔜 最后一步 |

---

## 六、关键命令速查

```bash
# === 数据准备 ===
# REEF 数据导入
python -m vulndetect.data_pipeline.distil.collectors.reef_importer

# Claude Opus 处理 (Phase 2, 需要 ANTHROPIC_API_KEY)
python -m vulndetect.data_pipeline.distil.pipeline \
  --input data/reef/reef_cleaned.jsonl \
  --output-dir data/distil

# === 训练 ===
# 基线训练 (NVD 数据)
python -m vulndetect.training.sft \
  --config vulndetect/config/experiments/exp001_sft.yaml

# 蒸馏训练 (REEF 推理链)
python -m vulndetect.training.sft \
  --config vulndetect/config/experiments/exp002_distil_sft.yaml

# DPO (可选)
python -m vulndetect.training.dpo \
  --config vulndetect/config/experiments/exp003_distil_dpo.yaml \
  --sft_checkpoint experiments/qwen3b-distil-sft-v1/checkpoints/final

# === 评测 ===
# lm_eval
python -m vulndetect.evaluation.harness \
  --model experiments/<exp>/checkpoints/final \
  --tasks vulnbench,seceval,mmlu_compsec,cybermetric,ctibench \
  --output eval_output_<name>/

# 代码分析评测
python -m vulndetect.evaluation.benchmarks.code_analysis \
  --model experiments/<exp>/checkpoints/final \
  --eval-set data/distil/samples_eval.jsonl \
  --output eval_output_<name>/code_vuln_analysis.json
```
