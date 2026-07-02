# VulnDetect 蒸馏实验方案

> 目的：验证"教师模型推理链蒸馏"是否优于"直接 SFT on CVE 描述" | 2026-07-02

---

## 一、核心假设

> **让模型学会像安全专家一样思考，而不是背诵 CVE 字典。**

| 对比维度 | 当前方案 (Baseline) | 蒸馏方案 (Proposed) |
|----------|-------------------|-------------------|
| 数据来源 | NVD CVE 描述 | 真实代码 + 教师模型分析 |
| 训练目标 | 复述漏洞信息 | 推理漏洞发现过程 |
| 数据质量 | 低（GPT 回复仅一句话） | 高（含完整推理链） |
| 模型能力 | 知道某个 CVE 是什么 | 能分析陌生代码找漏洞 |
| 泛化性 | 弱（背答案） | 强（学推理方法） |

**当前训练数据示例**（447 条全是这种质量）：
```json
{
  "human": "CVE ID: CVE-2018-25380 ... SQL injection ...",
  "gpt": "This vulnerability has a severity of HIGH.\nNo specific fix provided."
}
```
模型从这种数据学不到任何漏洞检测能力——它只是学会了"看到 CVE 就说 severity HIGH"。

**蒸馏数据目标质量**（每条都是完整的安全分析）：
```json
{
  "human": "请分析以下代码是否存在安全漏洞：\n[真实代码]",
  "gpt": "1. 审计输入源...\n2. 第X行存在...\n3. 漏洞原理...\n4. 修复方案...\n5. CWE 归类...\n6. CVSS 评分..."
}
```

---

## 二、实验设计：三组对照

### 实验组设置

| 组别 | 名称 | 基座模型 | 训练数据 | 数据量 | 训练方式 |
|------|------|---------|---------|--------|---------|
| **A（对照组）** | Baseline | Qwen2.5-3B | 无 | 0 | 无 |
| **B（当前方案）** | SFT-NVD | Qwen2.5-3B | NVD CVE 描述 | 402 train / 45 val | QLoRA SFT |
| **C（蒸馏方案）** | SFT-Distill | Qwen2.5-3B | 教师推理链 | ~500 train / ~50 val | QLoRA SFT |
| **D（蒸馏+DPO）** | Distill-DPO | Qwen2.5-3B | C 的 SFT 模型 + 偏好对 | ~500 SFT + ~100 DPO pairs | QLoRA SFT → DPO |

*注：D 组为可选进阶，视 C 组结果决定是否执行。*

### 控制变量

所有组保持一致的：
- 基座模型：`Qwen/Qwen2.5-3B-Instruct`
- 训练超参：沿用 `config/train/sft_qlora.yaml`（lr=2e-4, batch=4×4, 3 epochs）
- QLoRA 配置：r=16, alpha=32, 4-bit NF4（沿用 `config/model/qwen3b.yaml`）
- max_seq_length：**4096**（当前为 2048，蒸馏推理链需要更长上下文）
- 评测集：5 个安全 benchmarks + 自定义代码分析评测

---

## 三、数据策略

### 3.1 代码样本收集（目标：500-1000 个）

| 来源 | 类型 | 预计数量 | 说明 |
|------|------|---------|------|
| **GitHub Security Advisory** | 真实漏洞 + fix commit | ~200 | 已有 GitHub Advisory 采集器，需扩展提取 diff |
| **NVD CVE + 关联补丁** | 真实 CVE diff | ~200 | 添加 CVE → commit 关联查询 |
| **SARD/NIST Juliet** | 合成漏洞样本 | ~100 | 有 ground truth 的测试套件 |
| **OSS-Fuzz 报告** | 真实 crash + 修复 | ~50 | 模糊测试发现的漏洞 |
| **手动精选案例** | 经典 CWE 示例 | ~50 | OWASP Top 10 各选 5 个典型案例 |

### 3.2 教师模型推理数据生成

**教师模型**：Claude Opus 4.8（通过 API）

**数据生成 Pipeline**：

```
代码样本 → 构造 prompt → 教师模型推理 → 质量验证 → 格式转换 → 训练数据
```

**教师 Prompt 模板**（关键设计）：

```
You are a senior security researcher conducting a code audit.
Analyze the following code for security vulnerabilities.

For each vulnerability found, provide:
1. LOCATION: exact line numbers and code snippets
2. VULNERABILITY TYPE: CWE ID and name
3. ROOT CAUSE: why this is a vulnerability
4. EXPLOIT SCENARIO: how an attacker could exploit it
5. SEVERITY: CVSS 3.1 score and vector
6. FIX: concrete code fix with before/after comparison
7. PREVENTION: how to prevent this class of vulnerability

If no vulnerability exists, explain why the code is safe.

CODE TO AUDIT:
```language
{code_snippet}
```
```

**质量验证**（关键步骤）：

| 验证项 | 方法 | 不通过处理 |
|--------|------|-----------|
| 格式完整性 | 正则检查 7 部分是否齐全 | 重新生成 |
| CWE 有效性 | 查 CWE 字典 | 修正或丢弃 |
| 代码位置准确 | 验证行号在代码范围内 | 重新生成 |
| 修复方案可编译 | 实际编译测试（可选） | 标记 warning |
| 严重度合理 | CVSS 计算器校验 | 修正 |
| 无幻觉 | 人工抽查 10% | 调整 prompt |

### 3.3 预算估算

| 阶段 | 样本数 | Token/样本 (in+out) | 总 Token | Claude Opus 成本 |
|------|--------|-------------------|---------|-----------------|
| 试运行 | 50 | ~3000+2000 | ~250K | ~$5 |
| 正式生成 | 500 | ~3000+2000 | ~2.5M | ~$50 |
| 验证+重试 (20%) | 100 | ~3000+2000 | ~500K | ~$10 |
| **合计** | **650** | - | **~3.25M** | **~$65** |

*Claude Max 套餐 (20×) 的 API 额度可覆盖此成本。*

---

## 四、新增文件清单

### 4.1 数据生成管线

```
vulndetect/data_pipeline/
├── distil/                          # 新增：蒸馏数据生成
│   ├── __init__.py
│   ├── collectors/
│   │   ├── code_samples.py          # 代码样本采集器
│   │   └── patch_diff.py            # CVE → commit → diff 提取
│   ├── teacher.py                   # 教师模型 API 调用封装
│   ├── prompts.py                   # Prompt 模板管理
│   ├── validator.py                 # 生成结果质量校验
│   └── pipeline.py                  # 蒸馏数据生成主流程
```

### 4.2 实验配置

```
vulndetect/config/experiments/
├── exp002_distil_sft.yaml            # 新增：蒸馏 SFT 实验
└── exp003_distil_dpo.yaml            # 新增：蒸馏 DPO 实验（可选）
```

### 4.3 自定义评测

```
vulndetect/evaluation/
├── benchmarks/
│   └── code_analysis.py              # 新增：代码分析能力评测
```

---

## 五、实验配置文件

### 5.1 `exp002_distil_sft.yaml`

```yaml
# vulndetect/config/experiments/exp002_distil_sft.yaml
experiment:
  name: "qwen3b-distil-sft-v1"
  description: "Qwen-3B QLoRA SFT on teacher-distilled code analysis data"

includes:
  model: "model/qwen3b.yaml"
  training: "train/sft_qlora.yaml"

data:
  dataset:
    name: "distil_code_analysis"      # 蒸馏数据
  preprocessing:
    max_seq_length: 4096              # 推理链需要更长上下文
    val_split: 0.1
    shuffle: true
    seed: 42

evaluation:
  benchmarks:
    - vulnbench
    - seceval
    - mmlu_compsec
    - cybermetric
    - ctibench
    - code_vuln_analysis             # 新增：自定义代码分析评测
  eval_on_checkpoint: true
  eval_every_n_steps: 200
```

### 5.2 `exp003_distil_dpo.yaml`（可选）

```yaml
# vulndetect/config/experiments/exp003_distil_dpo.yaml
experiment:
  name: "qwen3b-distil-dpo-v1"
  description: "Qwen-3B QLoRA DPO on distilled code analysis + preference pairs"

includes:
  model: "model/qwen3b.yaml"
  training: "train/dpo.yaml"

data:
  dataset:
    name: "distil_code_analysis"
  preprocessing:
    max_seq_length: 4096
    val_split: 0.1

evaluation:
  benchmarks:
    - vulnbench
    - seceval
    - mmlu_compsec
    - cybermetric
    - ctibench
    - code_vuln_analysis
```

---

## 六、自定义评测设计：`code_vuln_analysis`

现有 benchmarks 偏向**知识问答**（选择题、判断题），蒸馏方案的核心能力是**代码分析推理**，需要一个自定义评测。

### 评测集构造（100 条 hold-out）

从代码样本池中预留 100 条**不参与训练**的样本作为评测集：

- 50 条含漏洞（覆盖 OWASP Top 10：注入、XSS、认证失效、敏感数据泄露、XXE、访问控制失效、安全配置错误、反序列化、已知漏洞组件、日志监控不足）
- 50 条安全代码（作为 negative case，测试误报率）

### 评测指标

| 指标 | 含义 | 计算方法 |
|------|------|---------|
| **Recall** | 真实漏洞被正确识别的比例 | TP / (TP + FN) |
| **Precision** | 报告为漏洞的代码中真正有漏洞的比例 | TP / (TP + FP) |
| **F1** | Precision 和 Recall 的调和平均 | 2 × P × R / (P + R) |
| **CWE Accuracy** | CWE 类型归类正确的比例 | CWE 正确数 / 检出漏洞总数 |
| **Fix Correctness** | 修复方案正确的比例 | 修复正确数 / 检出漏洞总数 |
| **False Positive Rate** | 安全代码被误报为漏洞的比例 | FP / 安全代码总数 |

### 评测方式

由于漏洞分析是开放式生成任务，评测需要 LLM-as-Judge：

1. 模型对每条代码生成分析报告
2. Claude Opus 作为 Judge 评判：
   - 漏洞是否存在
   - CWE 归类是否正确
   - 修复方案是否有效
3. 计算上述指标

---

## 七、执行计划（5 步，预计 5-7 天）

### Step 1：代码样本收集（1 天）

```
目标：收集 600+ 代码样本

行动：
1. 扩展 GitHub Advisory 采集器，提取关联 commit diff
2. 从 SARD/Juliet 数据集下载 100 个样本
3. 手动整理 50 个 OWASP Top 10 经典案例
4. 预留 100 条作为评测集，其余 500+ 用于训练

产出：
data/distil/samples.jsonl          # 所有代码样本
data/distil/samples_train.jsonl    # 训练用 500+
data/distil/samples_eval.jsonl     # 评测用 100（hold-out）
```

### Step 2：教师推理数据生成（1 天）

```
目标：为 500 个训练样本生成推理链

行动：
1. 实现 teacher.py（Claude API 调用封装，支持重试）
2. 实现 prompts.py（安全审计 prompt 模板）
3. 对 50 个样本 pilot run，人工检查质量
4. 调整 prompt → 批量生成 500 条
5. 质量校验（validator.py 自动检查 + 10% 人工抽查）

产出：
data/distil/teacher_outputs.jsonl  # 教师模型原始输出
data/distil/distil_train.jsonl     # 格式转换后的训练数据
data/distil/distil_val.jsonl       # 验证集

成本：~$65（Claude API）
```

### Step 3：基线训练（0.5 天）

```
目标：复现实验组 B（当前 SFT-NVD 方案），建立基线

行动：
1. 用现有 NVD 数据训练 exp001_sft 的完整版
2. 在 5 个 benchmarks + code_vuln_analysis 上评测
3. 记录所有分数作为基线

命令：
python -m vulndetect.training.sft \
  --config vulndetect/config/experiments/exp001_sft.yaml

产出：
eval_output_baseline/              # 基线评测结果
```

### Step 4：蒸馏模型训练（0.5 天）

```
目标：训练实验组 C（蒸馏 SFT）

行动：
1. 用蒸馏数据训练 exp002_distil_sft
2. 在相同 benchmarks 上评测
3. 与 A（基座）和 B（NVD-SFT）对比

命令：
python -m vulndetect.training.sft \
  --config vulndetect/config/experiments/exp002_distil_sft.yaml

产出：
experiments/qwen3b-distil-sft-v1/  # 蒸馏模型 checkpoint
eval_output_distil/                # 蒸馏评测结果
```

### Step 5：结果分析（0.5 天）

```
目标：量化对比，回答"蒸馏是否有效"

行动：
1. 生成三组对比表（Base vs NVD-SFT vs Distil-SFT）
2. 分析 code_vuln_analysis 细粒度指标
3. 决定是否推进 DPO（实验组 D）
4. 撰写实验报告

产出：
docs/蒸馏实验结果报告.md
```

---

## 八、预期结果

### 乐观预期

| Benchmark | Base (A) | NVD-SFT (B) | Distil-SFT (C) | B→C 提升 |
|-----------|----------|-------------|----------------|----------|
| mmlu_compsec | ~65 | ~72 | ~75 | +3 |
| vulnbench | ~42 | ~59 | ~65 | +6 |
| seceval | ~39 | ~52 | ~58 | +6 |
| cybermetric | ~44 | ~57 | ~62 | +5 |
| ctibench | ~32 | ~45 | ~50 | +5 |
| **code_vuln_analysis (F1)** | ~10 | ~15 | **~55** | **+40** |

*code_vuln_analysis 的提升会最显著，因为这恰好是蒸馏数据训练的能力。*

### 保守预期

- 通用 benchmarks 上蒸馏与 NVD-SFT 持平或微优于 NVD-SFT（+2~3 分）
- code_vuln_analysis 上蒸馏显著优于 NVD-SFT（+20~30 分 F1）
- 蒸馏模型的误报率（FPR）可能较高（需要 DPO 对齐来缓解）

### 失败判据

以下任一条件触发时，认为蒸馏方案对 VulnDetect 不适用：
1. code_vuln_analysis F1 < 30%（即无法有效检测漏洞）
2. 3 个以上通用 benchmark 分数下降 > 5 分（灾难性遗忘）
3. 误报率 > 60%（实用价值低）

---

## 九、关键风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| 教师模型幻觉（编造不存在的漏洞） | 中 | 高 | 10% 人工抽查 + CVSS 校验 + 代码行号验证 |
| 2048→4096 上下文超出显存 | 低 | 中 | QLoRA 4-bit + DeepSpeed ZeRO-2 + gradient checkpointing 已足够；A6000 48GB 远大于 yuxinlu1 的 32GB |
| 蒸馏后通用能力下降（灾难性遗忘） | 中 | 中 | 监控 5 个通用 benchmark；必要时 mixed data（蒸馏数据 + 通用数据混合训练） |
| 代码样本不够真实 | 中 | 中 | 优先 GitHub Advisory（真实漏洞），SARD/Juliet 作为补充 |
| DPO 偏好对构造困难 | 高 | 低 | D 组为可选；chosen=教师推理链，rejected=基座模型输出 |
| API 成本超预算 | 低 | 低 | 先在 50 条上验证 prompt 和效果，确认 ROI 后再扩量 |

---

## 十、与 yuxinlu1 方案的对比总结

| 维度 | yuxinlu1 方案 | VulnDetect 蒸馏方案 |
|------|-------------|-------------------|
| **领域** | 通用编程 | 漏洞检测（垂直领域） |
| **学生模型** | Gemma-4-12B | Qwen2.5-3B-Instruct |
| **教师模型** | Fable 5 / Opus 4.8 | Opus 4.8 |
| **数据量** | ~10K | ~500（Pilot） |
| **验证闭环** | 代码跑测试 | CWE 字典 + CVSS 校验 + 人工抽查 |
| **部署** | GGUF (llama.cpp) | QLoRA（后续可 GGUF） |
| **差异化** | 通用 coding agent | 专注安全审计 |
| **优势** | 验证了"个人开发者蒸馏大模型"这条路可行 | 垂直领域竞争少、评测标准明确（CWE/CVSS）、有落地场景 |

yuxinlu1 的成功证明了这条路的核心逻辑：**不需要大厂资源，关键是数据质量和专注一个具体痛点**。对 VulnDetect 而言，漏洞检测是天然适合蒸馏的方向——有明确的评判标准（CWE/CVSS/是否有漏洞），有真实的落地需求，且 3B 模型足够轻量，蒸馏后的部署门槛极低。
