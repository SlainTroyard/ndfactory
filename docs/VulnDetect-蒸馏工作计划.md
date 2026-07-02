# VulnDetect 蒸馏实验 — 工作计划

> 版本 1.0 | 2026-07-02 | 预计工期 5-7 天

---

## 总览：阶段与依赖关系

```
Phase 0: 环境准备 ─────────────────────────────────────────────┐
│ 入口：计划审批通过                                             │
│ 出口：教师 API 可用 + 评测集构造完成                            │
└────────────────────────────┬─────────────────────────────────┤
                             │                                  │
        ┌────────────────────┼──────────────────────┐           │
        ▼                    ▼                      ▼           │
Phase 1: 代码样本收集   Phase 3: 基线训练     Phase 2: 教师数据  │
│ 入口：Phase 0 完成     │ 入口：Phase 0 完成   │ 入口：Phase 1   │
│ 出口：600+ 样本就绪    │ 出口：组 B 评测完成   │ 出口：500 条     │
│                        │                       │ 推理链就绪      │
└────────┬───────────────┴───────────────────────┴───────┬───────┤
         │                                               │       │
         └───────────────────┬───────────────────────────┘       │
                             ▼                                   │
                   Phase 4: 蒸馏模型训练                          │
                   │ 入口：Phase 2 + Phase 3 完成                 │
                   │ 出口：组 C 模型训练 + 评测完成                │
                   └────────────┬─────────────────────────────────┤
                                ▼                                 │
                      Phase 5: 结果分析与决策                     │
                      │ 入口：Phase 3 + Phase 4 完成              │
                      │ 出口：实验结论 + 下一步决策                │
                      └────────────┬─────────────────────────────┤
                                   ▼                              │
                         Phase 6: 收尾（可选）                     │
                         │ 入口：Phase 5 决定推进 DPO              │
                         │ 出口：组 D 模型训练 + 评测完成           │
                         └────────────────────────────────────────┘
```

---

## 实验最终状态

### 仓库文件结构（完成后）

```
ndfactory/
├── data/
│   ├── vulndetect/                       # 【已有】NVD 数据
│   │   ├── vulndetect_train.jsonl
│   │   └── vulndetect_val.jsonl
│   └── distil/                           # 【新增】蒸馏数据
│       ├── samples.jsonl                 #   全部代码样本（600+）
│       ├── samples_train.jsonl           #   训练用样本（500+，不含代码）
│       ├── samples_eval.jsonl            #   hold-out 评测样本（100）
│       ├── teacher_outputs_raw.jsonl     #   教师模型原始输出
│       ├── teacher_outputs_validated.jsonl  # 校验通过的输出
│       ├── distil_train.jsonl           #   格式转换后的训练数据
│       ├── distil_val.jsonl             #   格式转换后的验证数据
│       └── generation_report.json       #   数据生成报告（统计信息）
│
├── vulndetect/
│   ├── data_pipeline/
│   │   └── distil/                       # 【新增】蒸馏数据生成模块
│   │       ├── __init__.py
│   │       ├── collectors/
│   │       │   ├── __init__.py
│   │       │   ├── code_samples.py       #   代码样本采集器
│   │       │   └── patch_diff.py         #   CVE → diff 提取
│   │       ├── teacher.py                #   教师 API 调用封装
│   │       ├── prompts.py                #   Prompt 模板管理
│   │       ├── validator.py             #   质量校验器
│   │       └── pipeline.py              #   主流程入口
│   │
│   ├── config/experiments/
│   │   ├── exp001_sft.yaml              # 【已有】基线实验
│   │   ├── exp002_distil_sft.yaml       # 【新增】蒸馏 SFT 实验
│   │   └── exp003_distil_dpo.yaml       # 【新增】蒸馏 DPO 实验（可选）
│   │
│   └── evaluation/
│       └── benchmarks/
│           └── code_analysis.py          # 【新增】代码分析评测
│
├── experiments/
│   ├── qwen3b-sft-vulnbench-v1/         # 【已有/重新训练】组 B 基线模型
│   ├── qwen3b-distil-sft-v1/            # 【新增】组 C 蒸馏模型
│   └── qwen3b-distil-dpo-v1/            # 【新增】组 D 蒸馏+DPO（可选）
│
├── eval_output/
│   ├── eval_output_baseline/            # 【已有/重新评测】组 A 基座
│   ├── eval_output_nvd_sft/             # 【已有/重新评测】组 B 评测
│   ├── eval_output_distil_sft/          # 【新增】组 C 评测
│   └── eval_output_distil_dpo/          # 【新增】组 D 评测（可选）
│
├── docs/
│   ├── VulnDetect-项目说明.md            # 【已有】
│   ├── VulnDetect-项目说明.txt           # 【已有】
│   ├── VulnDetect-蒸馏实验方案.md         # 【已有】实验设计
│   ├── VulnDetect-蒸馏工作计划.md         # 【本文档】
│   └── VulnDetect-蒸馏实验结果报告.md     # 【待产出】实验结论
│
└── tests/
    └── data_pipeline/
        └── test_distil.py               # 【新增】蒸馏模块测试
```

### 数据库状态（完成后）

SQLite `vulndetect.db` 中应包含以下实验记录：

| 实验名称 | 状态 | 阶段 | Benchmarks 评测数 |
|---------|------|------|------------------|
| `qwen3b-sft-vulnbench-v1` | completed | sft | 6 |
| `qwen3b-distil-sft-v1` | completed | sft | 6 |
| `qwen3b-distil-dpo-v1` | completed（可选） | dpo | 6 |

### 结论状态（最终输出）

无论成功还是失败，实验结束时必须有明确的**书面结论**：

```
✅ 成功判据（满足任一即视为成功）：
   - code_vuln_analysis F1 >= 40%，且通用 benchmark 下降均 < 3 分
   - 至少 2 个通用 benchmark 提升 > 3 分，且 code_vuln_analysis F1 >= 30%

❌ 失败判据（满足任一即视为失败）：
   - code_vuln_analysis F1 < 30%
   - 3 个以上通用 benchmark 分数下降 > 5 分
   - FPR > 60%

⚠️ 不确定（介于两者之间）：
   - 需要进一步分析原因，可能需要调整数据策略后重新实验
```

---

## Phase 0：环境与前置准备

**目标**：确保所有基础设施就绪，实验可以顺利启动。

**预计工时**：2 小时

### 入口条件

- [x] 蒸馏实验方案已设计完成（`docs/VulnDetect-蒸馏实验方案.md`）
- [x] 工作计划已审批（本文档）
- [ ] A6000 GPU 可用（48GB），驱动正常
- [ ] Python 环境就绪（venv 已安装所有依赖）
- [ ] 前端环境就绪（npm install）
- [ ] HuggingFace 镜像可用（`HF_ENDPOINT=https://hf-mirror.com`）
- [ ] Qwen2.5-3B-Instruct 基座模型已下载

### 任务清单

- [ ] **P0.1 检查 GPU 环境**
  ```bash
  nvidia-smi
  python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
  ```
- [ ] **P0.2 检查 Python 依赖**
  ```bash
  source venv/bin/activate
  pip list | grep -E "torch|transformers|peft|bitsandbytes|deepspeed|datasets"
  ```
- [ ] **P0.3 检查基座模型**
  ```bash
  python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('Qwen/Qwen2.5-3B-Instruct', trust_remote_code=True)"
  ```
- [ ] **P0.4 配置教师模型 API Key**
  - 在 `.env` 中配置 `ANTHROPIC_API_KEY=xxx`
  - 验证 API 可用：
    ```bash
    python -c "import anthropic; c=anthropic.Anthropic(); print(c.messages.create(model='claude-opus-4-8-20250514', max_tokens=10, messages=[{'role':'user','content':'ping'}]))"
    ```
- [ ] **P0.5 构造 hold-out 评测集**
  - 从各种来源挑选 100 个代码样本（50 漏洞 + 50 安全）
  - 这些样本**在整个实验过程中不参与训练**
  - 保存到 `data/distil/samples_eval.jsonl`

### 交付物

| 文件 | 内容 |
|------|------|
| `.env` | 已配置 API Key |
| `data/distil/samples_eval.jsonl` | 100 条 hold-out 评测样本 |

### 验收标准

- [ ] `nvidia-smi` 显示 A6000 可用，显存 > 40GB free
- [ ] `import torch` + `import transformers` + `import peft` 无报错
- [ ] 基座模型可正常加载（tokenizer + model config）
- [ ] `ping` 教师模型 API 返回 `"pong"`（或正常响应）
- [ ] `samples_eval.jsonl` 包含 100 条样本，人工确认 50 漏洞 + 50 安全

### 阻塞项

> 无。所有资源均为本地/已有。

---

## Phase 1：代码样本收集

**目标**：收集 600+ 真实代码漏洞样本，预留 100 条评测后，500+ 条用于蒸馏。

**预计工时**：1 天

### 入口条件

- [x] Phase 0 验收通过（GPU / 依赖 / 模型 / API）

### 任务清单

- [ ] **P1.1 扩展 GitHub Advisory 采集器**
  - 文件：`vulndetect/data_pipeline/distil/collectors/code_samples.py`
  - 功能：从 GitHub Advisory 提取关联 commit，获取漏洞修复前后的代码 diff
  - 目标：200 个样本
  ```bash
  python -m vulndetect.data_pipeline.distil.pipeline --source github_advisory --limit 200
  ```

- [ ] **P1.2 实现 CVE → commit diff 提取**
  - 文件：`vulndetect/data_pipeline/distil/collectors/patch_diff.py`
  - 功能：通过 NVD API 获取 CVE 的 reference links，解析 GitHub commit URL，提取 diff
  - 目标：200 个样本
  ```bash
  python -m vulndetect.data_pipeline.distil.pipeline --source cve_patch --limit 200
  ```

- [ ] **P1.3 下载 SARD/Juliet 测试套件**
  - 功能：解析 SARD/Juliet XML 数据集，提取 C/C++/Java 漏洞代码
  - 目标：100 个样本（按 CWE 分布采样）
  ```bash
  python -m vulndetect.data_pipeline.distil.pipeline --source sard --limit 100
  ```

- [ ] **P1.4 手工整理 OWASP Top 10 经典案例**
  - 每个 CWE 类别精选 5 个代表性代码片段
  - 目标：50 个样本
  - 格式：`data/distil/manual_owasp_top10.jsonl`

- [ ] **P1.5 合并 + 去重 + 按 CWE 分布检查**
  - 合并所有来源的样本
  - 按 CWE ID 去重（同 CWE+同文件路径→保留一个）
  - 检查 CWE 类型覆盖度（确保 Top 10 每类 >= 5 条）
  - 输出：`data/distil/samples.jsonl`
  - 移除与 `samples_eval.jsonl` 重复的样本

- [ ] **P1.6 划分训练/验证集**
  - 从 `samples.jsonl` 中拆分 90/10
  - 输出：`data/distil/samples_train.jsonl` + `data/distil/samples_val.jsonl`

### 交付物

| 文件 | 内容 | 最小数量 |
|------|------|---------|
| `data/distil/samples.jsonl` | 全部代码样本（不含评测集） | 600+ |
| `data/distil/samples_train.jsonl` | 训练集 | 540+ |
| `data/distil/samples_val.jsonl` | 验证集 | 60+ |
| `data/distil/samples_eval.jsonl` | hold-out 评测集（Phase 0 产出） | 100 |
| `vulndetect/data_pipeline/distil/collectors/__init__.py` | 采集器模块 | - |
| `vulndetect/data_pipeline/distil/collectors/code_samples.py` | GitHub Advisory 采集 | - |
| `vulndetect/data_pipeline/distil/collectors/patch_diff.py` | CVE diff 提取 | - |

### 验收标准

- [ ] 总样本数 >= 600（训练+验证 >= 600，另加评测 100）
- [ ] CWE Top 10 每类 >= 5 条样本
- [ ] 每个样本包含字段：`id`, `source`, `cwe_id`, `language`, `vulnerable_code`, `fixed_code`（或 `is_safe: true`）
- [ ] 评测集 100 条与训练/验证集无重叠（以 `id` 和代码哈希双重校验）
- [ ] `wc -l data/distil/samples_train.jsonl` >= 540

### 阻塞项

| 阻塞 | 应对 |
|------|------|
| GitHub Advisory 采集器获取不到 diff | NVD CVE reference links 作为备选 |
| SARD 样本质量差（合成代码不真实） | 降低 SARD 比例，增加 GitHub Advisory |
| 某类 CWE 样本不足 | 手工补充或放宽该类的最低要求 |

---

## Phase 2：教师推理数据生成

**目标**：用 Claude Opus 4.8 为 500 个训练样本生成高质量漏洞分析推理链。

**预计工时**：1 天（含 pilot 验证 2h + 批量生成 4h + 校验清洗 2h）

### 入口条件

- [x] Phase 1 验收通过（样本 >= 600）
- [ ] 教师 API 可用（Phase 0 已验证）

### 任务清单

- [ ] **P2.1 实现 Prompt 模板管理**
  - 文件：`vulndetect/data_pipeline/distil/prompts.py`
  - 包含：
    - `SECURITY_AUDIT_PROMPT`：标准 7 部分分析模板
    - `SECURITY_AUDIT_PROMPT_NO_VULN`：安全代码专用模板（强调"如果安全，说明为什么安全"）
    - `SECURITY_AUDIT_PROMPT_SHORT`：短代码模板（< 50 行）
    - 每种模板支持 `{language}` 和 `{code_snippet}` 占位符

- [ ] **P2.2 实现教师 API 调用封装**
  - 文件：`vulndetect/data_pipeline/distil/teacher.py`
  - 功能：
    - `generate_analysis(code_snippet, language)` → 返回推理链文本
    - 支持 3 次自动重试（exponential backoff: 2s, 4s, 8s）
    - 超过 4096 output token 时自动截断并续写
    - 记录每次调用的 token 使用量和耗时
    - Rate limit 保护（最多 5 并发请求）
  - 使用 Anthropic Python SDK

- [ ] **P2.3 实现质量校验器**
  - 文件：`vulndetect/data_pipeline/distil/validator.py`
  - 自动校验规则：
    | 规则 | 方法 | 不通过操作 |
    |------|------|-----------|
    | 7 部分完整性 | 正则匹配 7 个章节标题 | `retry`：重写该条 |
    | CWE 有效性 | 对照 CWE 字典（cwe.csv） | `fix`：自动修正为最近似 CWE |
    | 行号有效性 | 解析行号，检查是否在代码范围内 | `retry` |
    | CVSS 格式 | 正则 `CVSS:3.[01]/AV:[NALP]/...` | `retry` |
    | 最小长度 | >= 200 words | `drop`：丢弃 |
    | 空响应 | 检测无意义输出 | `retry` |

- [ ] **P2.4 Pilot Run（50 条验证）**
  ```bash
  python -m vulndetect.data_pipeline.distil.pipeline \
    --step teacher \
    --input data/distil/samples_train.jsonl \
    --limit 50 \
    --output data/distil/teacher_pilot.jsonl
  ```
  - 人工抽查 10 条（20%），按以下维度打分（1-5）：
    - 漏洞识别准确性
    - CWE 归类正确性
    - 修复方案可行性
    - 推理逻辑清晰度
  - 通过标准：平均分 >= 3.5，单条无 < 2 分
  - **如果不通过**：调整 prompt 模板，重复 pilot run

- [ ] **P2.5 批量生成（500 条）**
  ```bash
  python -m vulndetect.data_pipeline.distil.pipeline \
    --step teacher \
    --input data/distil/samples_train.jsonl \
    --output data/distil/teacher_outputs_raw.jsonl
  ```
  - 预计耗时：~4 小时（500 条 × ~30s/条，5 并发）
  - 预计成本：~$50

- [ ] **P2.6 质量校验 + 重试**
  ```bash
  python -m vulndetect.data_pipeline.distil.pipeline \
    --step validate \
    --input data/distil/teacher_outputs_raw.jsonl \
    --output data/distil/teacher_outputs_validated.jsonl \
    --retry-failed
  ```
  - 目标通过率 >= 90%
  - 对不通过的条目自动重试（最多 3 次）
  - 三次重试仍不通过 → 丢弃并记录原因

- [ ] **P2.7 格式转换 → 训练数据**
  ```bash
  python -m vulndetect.data_pipeline.distil.pipeline \
    --step format \
    --input data/distil/teacher_outputs_validated.jsonl \
    --output-train data/distil/distil_train.jsonl \
    --output-val data/distil/distil_val.jsonl \
    --val-split 0.1
  ```
  - 转换为 OpenRLHF conversation 格式
  - Human: `"请分析以下{language}代码是否存在安全漏洞：\n```{language}\n{code}\n```"`
  - GPT: 完整的 7 部分分析文本

- [ ] **P2.8 生成数据报告**
  - 记录：样本数、通过率、CWE 分布、平均 token 数、API 成本
  - 输出：`data/distil/generation_report.json`

### 交付物

| 文件 | 内容 | 数量 |
|------|------|------|
| `vulndetect/data_pipeline/distil/prompts.py` | Prompt 模板 | 3+ 模板 |
| `vulndetect/data_pipeline/distil/teacher.py` | API 调用封装 | - |
| `vulndetect/data_pipeline/distil/validator.py` | 自动校验器 | - |
| `data/distil/teacher_outputs_raw.jsonl` | 教师原始输出 | ~500 条 |
| `data/distil/teacher_outputs_validated.jsonl` | 校验通过的输出 | >= 450 条 |
| `data/distil/distil_train.jsonl` | 训练数据（conversation 格式） | >= 400 条 |
| `data/distil/distil_val.jsonl` | 验证数据（conversation 格式） | >= 45 条 |
| `data/distil/generation_report.json` | 数据生成统计 | 1 份 |

### 验收标准

- [ ] Pilot run 人工评分平均 >= 3.5/5
- [ ] 批量生成完成率 >= 90%（生成成功数 / 样本总数）
- [ ] 校验通过率 >= 90%（通过校验数 / 生成成功数）
- [ ] 最终训练数据 >= 400 条，验证数据 >= 45 条
- [ ] 训练数据中 CWE Top 10 每类 >= 3 条
- [ ] 分析文本平均长度 >= 500 tokens
- [ ] API 总成本 <= $100（含重试）
- [ ] `generation_report.json` 数据完整

### 关键风险

| 风险 | 应对 |
|------|------|
| **Pilot 人工评分 < 3.5** | 这是最大风险。需迭代 prompt：增加示例（few-shot）、更具体的要求、要求引用行号 |
| **批量生成大量失败** | 检查 API rate limit、网络超时、output token 截断；降低并发数 |
| **CWE 覆盖度不均** | 某些 CWE 类的代码样本本身少，接受分布不均，在报告中注明 |
| **API 成本超 $100** | 停止生成，检查 token 消耗，评估已生成数据的数量是否足够做有意义的训练 |

---

## Phase 3：基线训练（实验组 B）

**目标**：用现有 NVD 数据训练 SFT 模型，建立性能基线。

**预计工时**：0.5 天（训练 ~2 小时 + 评测 ~1 小时）

### 入口条件

- [x] Phase 0 验收通过（环境就绪）
- [ ] NVD 数据存在（`data/vulndetect/vulndetect_train.jsonl`）
- [ ] `exp001_sft.yaml` 配置确认无误

### 任务清单

- [ ] **P3.1 确认 max_seq_length 配置**
  - 为保持与蒸馏组（Phase 4）的可比性，将基线训练的 `max_seq_length` 也临时调整为 4096
  - 修改方式：直接在 SFT 命令中指定或创建临时 config overlay

- [ ] **P3.2 运行基线 SFT 训练**
  ```bash
  python -m vulndetect.training.sft \
    --config vulndetect/config/experiments/exp001_sft.yaml
  ```
  - 预计训练时间：~2 小时（402 条数据, 3 epochs, batch=16）
  - 检查 checkpoint 保存正常：`experiments/qwen3b-sft-vulnbench-v1/checkpoints/`

- [ ] **P3.3 评测组 A：基座模型（Baseline）**
  ```bash
  python -m vulndetect.evaluation.harness \
    --model Qwen/Qwen2.5-3B-Instruct \
    --benchmarks vulnbench,seceval,mmlu_compsec,cybermetric,ctibench \
    --output eval_output_baseline/
  ```

- [ ] **P3.4 评测组 B：NVD-SFT 模型**
  ```bash
  python -m vulndetect.evaluation.harness \
    --model experiments/qwen3b-sft-vulnbench-v1/checkpoints/final \
    --benchmarks vulnbench,seceval,mmlu_compsec,cybermetric,ctibench \
    --output eval_output_nvd_sft/
  ```

- [ ] **P3.5 评测 code_vuln_analysis**
  ```bash
  # 对组 A 基座
  python -m vulndetect.evaluation.code_analysis \
    --model Qwen/Qwen2.5-3B-Instruct \
    --eval-set data/distil/samples_eval.jsonl \
    --output eval_output_baseline/code_vuln_analysis.json

  # 对组 B NVD-SFT
  python -m vulndetect.evaluation.code_analysis \
    --model experiments/qwen3b-sft-vulnbench-v1/checkpoints/final \
    --eval-set data/distil/samples_eval.jsonl \
    --output eval_output_nvd_sft/code_vuln_analysis.json
  ```

- [ ] **P3.6 写入 DB**
  ```bash
  bash scripts/write_evals.sh
  ```

### 交付物

| 路径 | 内容 |
|------|------|
| `experiments/qwen3b-sft-vulnbench-v1/` | 组 B 模型 checkpoint |
| `eval_output_baseline/results.json` | 组 A 基座评测分数 |
| `eval_output_nvd_sft/results.json` | 组 B NVD-SFT 评测分数 |
| `eval_output_baseline/code_vuln_analysis.json` | 组 A 代码分析评测 |
| `eval_output_nvd_sft/code_vuln_analysis.json` | 组 B 代码分析评测 |

### 验收标准

- [ ] 训练正常完成，无 OOM、无崩溃
- [ ] checkpoint 可正常加载：`AutoPeftModelForCausalLM.from_pretrained()`
- [ ] 5 个 benchmark 评测全部完成，分数在合理范围（不应与已知数据差异 > 10 分）
- [ ] code_vuln_analysis 评测完成（LLM-as-Judge 评估通过）
- [ ] **记录下组 B 的所有分数，作为 Phase 5 对比基线**

### 阻塞项

> 无。这是已运行的训练链路。

---

## Phase 4：蒸馏模型训练（实验组 C）

**目标**：用蒸馏数据训练 SFT 模型，这是整个实验的核心步骤。

**预计工时**：0.5 天（训练 ~2.5 小时 + 评测 ~1 小时）

### 入口条件

- [x] Phase 2 验收通过（蒸馏训练数据 >= 400 条）
- [x] Phase 3 验收通过（基线评测完成，分数已记录）

### 任务清单

- [ ] **P4.1 创建实验配置文件**
  - 文件：`vulndetect/config/experiments/exp002_distil_sft.yaml`
  - 内容：参照蒸馏实验方案第五节
  - max_seq_length: 4096

- [ ] **P4.2 确认训练数据路径正确**
  ```bash
  ls -la data/distil/distil_train.jsonl data/distil/distil_val.jsonl
  head -1 data/distil/distil_train.jsonl | python -m json.tool
  ```

- [ ] **P4.3 运行蒸馏 SFT 训练**
  ```bash
  python -m vulndetect.training.sft \
    --config vulndetect/config/experiments/exp002_distil_sft.yaml
  ```
  - 预计训练时间：~2.5 小时（400+ 条数据, 3 epochs, batch=16）
  - **监控项**：
    - 训练 loss 是否正常下降
    - GPU 显存使用是否在 48GB 以内
    - 无 OOM

- [ ] **P4.4 评测组 C：蒸馏 SFT 模型**
  ```bash
  # 通用 benchmarks
  python -m vulndetect.evaluation.harness \
    --model experiments/qwen3b-distil-sft-v1/checkpoints/final \
    --benchmarks vulnbench,seceval,mmlu_compsec,cybermetric,ctibench \
    --output eval_output_distil_sft/

  # 代码分析评测
  python -m vulndetect.evaluation.code_analysis \
    --model experiments/qwen3b-distil-sft-v1/checkpoints/final \
    --eval-set data/distil/samples_eval.jsonl \
    --output eval_output_distil_sft/code_vuln_analysis.json
  ```

- [ ] **P4.5 写入 DB**
  ```bash
  bash scripts/write_evals.sh
  ```

### 交付物

| 路径 | 内容 |
|------|------|
| `vulndetect/config/experiments/exp002_distil_sft.yaml` | 蒸馏实验配置 |
| `experiments/qwen3b-distil-sft-v1/` | 组 C 模型 checkpoint |
| `eval_output_distil_sft/results.json` | 组 C 通用 benchmark 评测 |
| `eval_output_distil_sft/code_vuln_analysis.json` | 组 C 代码分析评测 |

### 验收标准

- [ ] 训练正常完成，无 OOM
- [ ] checkpoint 可正常加载
- [ ] 5 个 benchmark + code_vuln_analysis 评测全部完成
- [ ] **记录下组 C 的所有分数**

### 阻塞项

| 阻塞 | 应对 |
|------|------|
| 4096 context 导致 OOM | 降为 3072 或 2048，截断推理链（保留 LOCATION + VULN + FIX 优先） |
| 训练 loss 不下降 | 检查数据格式，可能 teacher output 未正确转换 |
| 训练时间超出预期 | 减少 epochs 为 2，更大 batch 或更少数据 |

---

## Phase 5：结果分析与决策

**目标**：量化对比三组实验结果，形成明确结论。

**预计工时**：0.5 天

### 入口条件

- [x] Phase 3 验收通过（组 A + 组 B 评测完成）
- [x] Phase 4 验收通过（组 C 评测完成）

### 任务清单

- [ ] **P5.1 生成三组对比表**

  | Benchmark | Base (A) | NVD-SFT (B) | Distil-SFT (C) | Δ(B→C) | 趋势 |
  |-----------|----------|-------------|----------------|---------|------|
  | mmlu_compsec | _TBD_ | _TBD_ | _TBD_ | _TBD_ | - |
  | vulnbench | _TBD_ | _TBD_ | _TBD_ | _TBD_ | - |
  | seceval | _TBD_ | _TBD_ | _TBD_ | _TBD_ | - |
  | cybermetric | _TBD_ | _TBD_ | _TBD_ | _TBD_ | - |
  | ctibench | _TBD_ | _TBD_ | _TBD_ | _TBD_ | - |
  | **code_vuln_analysis** | _TBD_ | _TBD_ | _TBD_ | _TBD_ | - |

- [ ] **P5.2 分析 code_vuln_analysis 细粒度指标**

  | 指标 | Base (A) | NVD-SFT (B) | Distil-SFT (C) |
  |------|----------|-------------|----------------|
  | Recall | _TBD_ | _TBD_ | _TBD_ |
  | Precision | _TBD_ | _TBD_ | _TBD_ |
  | **F1** | _TBD_ | _TBD_ | _TBD_ |
  | CWE Accuracy | _TBD_ | _TBD_ | _TBD_ |
  | Fix Correctness | _TBD_ | _TBD_ | _TBD_ |
  | FPR | _TBD_ | _TBD_ | _TBD_ |

- [ ] **P5.3 按 CWE 类别分析 Distil-SFT(C) 的优劣势**
  - 哪些 CWE 类型检测效果好？（F1 > 60%）
  - 哪些 CWE 类型检测效果差？（F1 < 30%）
  - 与训练数据中该 CWE 的样本量做相关分析
  - 分析误报集中在哪些类型

- [ ] **P5.4 代入失败判据判断结论**
  ```
  检查项 1: code_vuln_analysis F1 >= 30%？       → [PASS / FAIL]
  检查项 2: 通用 benchmark 下降 > 5 分的个数？    → [0 / 1 / 2 / 3+]
  检查项 3: FPR <= 60%？                        → [PASS / FAIL]
  
  结论：✅ 成功 / ⚠️ 不确定 / ❌ 失败
  ```

- [ ] **P5.5 抽查模型输出质量（定性分析）**
  - 从 code_vuln_analysis 评测集中随机选 10 条
  - 人工阅读组 C 模型的输出
  - 评估：
    - 推理逻辑是否合理？
    - 是否存在明显幻觉（编造行号、编造漏洞）？
    - 修复建议是否实际可用？
  - 记录典型的好案例和坏案例

- [ ] **P5.6 决定下一步**
  - 如果结论为 ✅ **成功**：
    → 推进 Phase 6（DPO 对齐）或 直接进入 GGUF 量化部署
  - 如果结论为 ⚠️ **不确定**：
    → 分析失败维度，制定改进计划（如：增加某类 CWE 数据、调整 prompt、提高数据量），重新实验
  - 如果结论为 ❌ **失败**：
    → 分析失败原因，决定是放弃蒸馏路线还是从根本上调整数据策略

- [ ] **P5.7 撰写实验结果报告**
  - 文件：`docs/VulnDetect-蒸馏实验结果报告.md`
  - 结构：
    1. 实验环境复述
    2. 三组对比表 + 可视化图表
    3. code_vuln_analysis 细粒度分析
    4. 定性分析（好案例 / 坏案例）
    5. 结论与下一步计划
    6. 附录：完整数据、配置、训练日志路径

### 交付物

| 文件 | 内容 |
|------|------|
| `docs/VulnDetect-蒸馏实验结果报告.md` | 完整实验报告 |

### 验收标准

- [ ] 三组（A/B/C）的全部评测分数已填入对比表
- [ ] code_vuln_analysis 6 个指标均已计算
- [ ] 失败判据已逐项检查，结论明确（✅/⚠️/❌）
- [ ] 至少 10 条模型输出已人工定性分析
- [ ] 下一步计划已明确写出
- [ ] 实验报告已 push 到 GitHub（作为实验的历史记录）

---

## Phase 6：DPO 对齐（可选）

**前置条件**：Phase 5 结论为 ✅ 成功，且 Distil-SFT(C) 存在以下任一问题：
- 误报率（FPR）> 30%
- 推理链质量不稳定（输出格式不规整）
- 对安全代码过度敏感

**目标**：用 DPO 训练降低误报率、提高输出质量。

**预计工时**：0.5 天

### 入口条件

- [x] Phase 5 结论为 ✅ 成功
- [ ] Phase 5 报告中建议推进 DPO
- [ ] 蒸馏 SFT 模型 checkpoint 存在

### 任务清单

- [ ] **P6.1 构造 DPO 偏好对**
  - 来源：从 code_vuln_analysis 评测结果中提取
  - `chosen`：教师模型推理链（高质量）
  - `rejected`：
    - 方案 A：基座模型对同一代码的输出（零上下文，低质量）
    - 方案 B：SFT 模型输出中 Judge 判定为错误的
  - 目标：100 对
  - 输出：`data/distil/dpo_pairs.jsonl`

- [ ] **P6.2 创建 DPO 配置**
  - 文件：`vulndetect/config/experiments/exp003_distil_dpo.yaml`
  - 内容：参照蒸馏实验方案 5.2 节

- [ ] **P6.3 运行 DPO 训练**
  ```bash
  python -m vulndetect.training.dpo \
    --config vulndetect/config/experiments/exp003_distil_dpo.yaml \
    --sft_checkpoint experiments/qwen3b-distil-sft-v1/checkpoints/final
  ```

- [ ] **P6.4 评测组 D**
  - 同上：5 benchmarks + code_vuln_analysis
  - 与组 C 对比，重点观察 FPR 是否下降

### 交付物

| 路径 | 内容 |
|------|------|
| `experiments/qwen3b-distil-dpo-v1/` | 组 D 模型 |
| `eval_output_distil_dpo/` | 组 D 评测结果 |

### 验收标准

- [ ] DPO 训练完成
- [ ] code_vuln_analysis F1 未显著下降（>= 组 C 的 90%）
- [ ] FPR 相比组 C 下降（理想的改善 > 5 个百分点）
- [ ] 通用 benchmark 分数未显著下降（<= 组 C 的 95%）

---

## 附录 A：验收检查清单（汇总）

实验负责人可在完成每个 Phase 后逐项打勾。

### Phase 0
- [ ] GPU 环境正常（A6000, >40GB free）
- [ ] Python 依赖完整
- [ ] 基座模型可加载
- [ ] 教师 API 可用
- [ ] hold-out 评测集已构造（100 条）

### Phase 1
- [ ] 总样本数 >= 600
- [ ] CWE Top 10 每类 >= 5 条
- [ ] 评训练/评测集无重叠
- [ ] 采集器代码已合并到 vulndetect 包

### Phase 2
- [ ] Pilot run 人工评分 >= 3.5
- [ ] 训练数据 >= 400 条
- [ ] 校验通过率 >= 90%
- [ ] API 成本 <= $100
- [ ] generation_report.json 完整

### Phase 3
- [ ] 基线 SFT 训练完成
- [ ] 组 A + 组 B 评测完成（5 benchmarks + code_vuln_analysis）
- [ ] 评测结果已写入 DB

### Phase 4
- [ ] 蒸馏 SFT 训练完成
- [ ] 组 C 评测完成（5 benchmarks + code_vuln_analysis）
- [ ] 评测结果已写入 DB

### Phase 5
- [ ] 三组对比表完整
- [ ] code_vuln_analysis 6 指标完整
- [ ] 失败判据逐项检查
- [ ] 至少 10 条定性分析
- [ ] 实验报告已撰写并 push

### Phase 6（可选）
- [ ] DPO 训练完成
- [ ] 组 D 评测完成
- [ ] FPR 相比组 C 下降

---

## 附录 B：时间估算

| Phase | 内容 | 预计工时 | 可并行？ |
|-------|------|---------|---------|
| P0 | 环境准备 | 2h | - |
| P1 | 代码样本收集 | 1d | ✅ 可与 P0 并行 |
| P2 | 教师数据生成 | 1d | ❌ 依赖 P1 |
| P3 | 基线训练 | 0.5d | ✅ 可与 P1,P2 并行 |
| P4 | 蒸馏训练 | 0.5d | ❌ 依赖 P2+P3 |
| P5 | 结果分析 | 0.5d | ❌ 依赖 P3+P4 |
| P6 | DPO（可选） | 0.5d | ❌ 依赖 P5 决策 |
| **合计** | | **3.5-5.5d** | 关键路径: P0→P1→P2→P4→P5 = 3.5d |

**最快路径**：P0 + P1 并行启动 → P2 + P3 并行 → P4 → P5 = **4 天完成**（含 P6 则 4.5 天）

---

## 附录 C：关键命令速查

```bash
# === Phase 0: 环境检查 ===
nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"
source venv/bin/activate && pip list | grep -E "torch|transformers|peft"

# === Phase 1: 收集样本 ===
python -m vulndetect.data_pipeline.distil.pipeline --source all --limit 700

# === Phase 2: 教师数据 ===
# Pilot
python -m vulndetect.data_pipeline.distil.pipeline --step teacher --limit 50
# 全量
python -m vulndetect.data_pipeline.distil.pipeline --step teacher
# 校验
python -m vulndetect.data_pipeline.distil.pipeline --step validate
# 格式转换
python -m vulndetect.data_pipeline.distil.pipeline --step format

# === Phase 3: 基线训练 ===
python -m vulndetect.training.sft --config vulndetect/config/experiments/exp001_sft.yaml
python -m vulndetect.evaluation.harness --model Qwen/Qwen2.5-3B-Instruct --tasks vulnbench,seceval,mmlu_compsec,cybermetric,ctibench --output eval_output_baseline/
python -m vulndetect.evaluation.harness --model experiments/qwen3b-sft-vulnbench-v1/checkpoints/final --tasks vulnbench,seceval,mmlu_compsec,cybermetric,ctibench --output eval_output_nvd_sft/

# === Phase 4: 蒸馏训练 ===
python -m vulndetect.training.sft --config vulndetect/config/experiments/exp002_distil_sft.yaml
python -m vulndetect.evaluation.harness --model experiments/qwen3b-distil-sft-v1/checkpoints/final --tasks vulnbench,seceval,mmlu_compsec,cybermetric,ctibench --output eval_output_distil_sft/

# === Phase 5: 结果分析 ===
# 对比三个 eval_output 目录下的 results.json
# 执行 LLM-as-Judge 评测（code_vuln_analysis）

# === Phase 6: DPO（可选） ===
python -m vulndetect.training.dpo --config vulndetect/config/experiments/exp003_distil_dpo.yaml --sft_checkpoint experiments/qwen3b-distil-sft-v1/checkpoints/final
```
