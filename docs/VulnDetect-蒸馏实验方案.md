# VulnDetect 蒸馏实验方案

> 目的：验证"教师模型推理链蒸馏"是否优于"直接 SFT on CVE 描述" | 2026-07-07

---

## 一、核心假设

> **让模型学会像安全专家一样思考，而不是背诵 CVE 字典。**

| 对比维度 | 当前方案 (Baseline) | 蒸馏方案 (Proposed) |
|----------|-------------------|-------------------|
| 数据来源 | NVD CVE 描述 | REEF 真实漏洞 + 教师模型分析 |
| 训练目标 | 复述漏洞信息 | 推理漏洞发现与修复过程 |
| 数据质量 | 低（GPT 回复仅一句话） | 高（含完整推理链 + 真实 patch） |
| 模型能力 | 知道某个 CVE 是什么 | 能分析陌生代码找漏洞并生成修复 |
| 泛化性 | 弱（背答案） | 强（学推理方法） |

**当前训练数据示例**（447 条全是这种质量）：
```json
{
  "human": "CVE ID: CVE-2018-25380 ... SQL injection ...",
  "gpt": "This vulnerability has a severity of HIGH.\nNo specific fix provided."
}
```
模型从这种数据学不到任何漏洞检测能力——它只是学会了"看到 CVE 就说 severity HIGH"。

**蒸馏数据目标**：基于 REEF 数据集（4,466 条真实 CVE，含漏洞代码 + git diff patch），用 Claude Opus 生成包含完整推理链的高质量训练数据。

---

## 二、数据策略

### 2.1 主数据源：REEF 数据集

| 维度 | 数据 |
|------|------|
| 总样本 | **4,466 条**（已 clone 至 `~/coding/REEF-data/`） |
| 语言 | C (1,575), Python (863), JS (636), Java (541), C++ (411), Go (355), C# (85) |
| CWE 覆盖 | **237 种** |
| 数据格式 | JSONL，每条含 `cve_id` / `CWEs` / `cvss` / `LLM_message` / `details[].patch` / `details[].raw_code` |
| 与我们现有数据重叠 | **0 个 CVE 重叠**（完全互补） |

**选用 REEF 而非自己采集的理由**：REEF 是 ASE 2023 论文数据集，已从 GitHub 提取了 4,466 个真实 CVE 的 fix commit 和 diff，我们不需要重新爬取。

### 2.2 两步数据处理管线

所有处理均由 Claude Opus 4.8 完成，分两步：

```
REEF 数据 (4,466条)
    │
    ├── Step 1: LLM_message 修复
    │   输入：REEF 的 patch + raw_code + 原始 LLM_message
    │   输出：高质量漏洞描述与修复说明
    │   用途：直接作为 SFT 训练数据（描述型）
    │   数量：4,466 条 → 过滤低质量后 ~4,000 条
    │
    └── Step 2: 推理链蒸馏
        输入：REEF 的 patch + raw_code（漏洞修复前后的代码）
        输出：7 部分安全审计推理链
        用途：SFT 训练数据（推理型），教模型像安全专家一样分析
        数量：~4,000 条
```

### 2.3 两步产物的区别

| | Step 1 产物（描述型） | Step 2 产物（推理型） |
|---|---|---|
| **内容** | "CVE-XXX 是一个 XSS 漏洞，位于第 42 行..." | "## 1. 漏洞定位\n第42行...\n## 2. CWE-79\n..." |
| **训练目标** | 让模型学会描述漏洞 | 让模型学会推理发现漏洞 |
| **格式** | 自然段落 | 结构化 7 章节 |
| **难度** | 低（有正确答案可参考） | 高（需要从代码推理） |

### 2.4 种子合成数据

Phase 1 生成的 607 条合成代码样本**暂不使用**。待 REEF 管线跑通后，评估是否需要补充。

### 2.5 预算估算（重新计算）

| 步骤 | 样本数 | Token/样本 | 总 Token | 预估成本 |
|------|--------|-----------|---------|---------|
| Step 1 pilot | 50 | ~2,000+1,500 | ~175K | ~$3 |
| Step 1 全量 | 4,000 | ~2,000+1,500 | ~14M | ~$210 |
| Step 2 pilot | 50 | ~3,000+2,500 | ~275K | ~$6 |
| Step 2 全量 | 4,000 | ~3,000+2,500 | ~22M | ~$400 |
| **合计（pilot + 全量）** | **~8,000 次调用** | — | **~36M** | **~$620** |

*注：可用 Claude Max 套餐额度覆盖。如预算有限，可先用 1,000 条子集做 Step 1+2，验证效果后再扩量。*

---

## 三、实验设计：三组对照

### 实验组设置

| 组别 | 名称 | 基座模型 | 训练数据 | 数据量 | 训练方式 |
|------|------|---------|---------|--------|---------|
| **A（对照组）** | Baseline | Qwen2.5-3B | 无 | 0 | 无 |
| **B（当前方案）** | SFT-NVD | Qwen2.5-3B | NVD CVE 描述 | 402 train / 45 val | QLoRA SFT |
| **C（Step1 产物）** | SFT-REEF-Desc | Qwen2.5-3B | REEF 修复后的漏洞描述 | ~3,600 train / 400 val | QLoRA SFT |
| **D（Step2 产物）** | SFT-REEF-Reason | Qwen2.5-3B | REEF 推理链蒸馏数据 | ~3,600 train / 400 val | QLoRA SFT |
| **E（Step1+2 混合）** | SFT-REEF-Mix | Qwen2.5-3B | 描述 + 推理链混合 | ~7,200 train / 800 val | QLoRA SFT |

*注：组 C/D/E 可根据预算灵活调整。优先验证组 D（推理链），因为它是核心假设。*

### 控制变量

所有组保持一致：
- 基座模型：`Qwen/Qwen2.5-3B-Instruct`
- 训练超参：`config/train/sft_qlora.yaml`（lr=2e-4, batch=4×4, 3 epochs）
- QLoRA 配置：r=16, alpha=32, 4-bit NF4（`config/model/qwen3b.yaml`）
- max_seq_length：**4096**
- 评测：5 个安全 benchmarks + VulnBench

---

## 四、执行计划

### 总体流程

```
Phase 0: 环境准备 ✅ 已完成
Phase 1: REEF 数据导入（新增）
Phase 2: Step 1 — Claude Opus 修复 LLM_message
Phase 3: Step 2 — Claude Opus 生成 7 部分推理链
Phase 4: 基线训练（组 A + 组 B）
Phase 5: 蒸馏训练（组 C / D / E）
Phase 6: 评测对比（含 VulnBench）
Phase 7: 结果分析
```

### Phase 1：REEF 数据导入（0.5 天）

- 编写 REEF → 内部格式的转换脚本
- 字段映射：cvss→severity, LLM_message→description, details[].patch→fix
- 过滤：去除 NVD-CWE-noinfo（231 条）、CVSS < 4.0（低危）样本
- 产出：`data/reef/reef_cleaned.jsonl`（~4,000 条）

### Phase 2：Step 1 — LLM_message 修复（1-2 天）

- 用 Claude Opus 重写每条 REEF 样本的漏洞描述
- prompt：输入 patch + raw_code + 原始 LLM_message，输出结构化的漏洞说明
- Pilot 50 条 → 人工检查 → 批量 4,000 条
- 产出：`data/reef/reef_descriptions_train.jsonl`

### Phase 3：Step 2 — 推理链蒸馏（1-2 天）

- 用 Claude Opus 对每条样本生成 7 部分安全审计推理链
- prompt：复用已有的 `SECURITY_AUDIT_PROMPT`
- Pilot 50 条 → 人工检查 → 批量 4,000 条
- 质量校验：已有的 `validator.py` 自动检查
- 产出：`data/reef/reef_reasoning_train.jsonl`

### Phase 4-7：训练 + 评测 + 分析

沿用原方案，训练数据来源替换为 REEF 产物。评测增加 VulnBench（甲方指定）。

---

## 五、预期结果

| Benchmark | Base (A) | NVD-SFT (B) | REEF-Desc (C) | REEF-Reason (D) |
|-----------|----------|-------------|---------------|-----------------|
| VulnBench pass rate | ~5% | ~8% | ~12% | **~20%** |
| mmlu_compsec | ~65 | ~72 | ~73 | ~74 |
| code_vuln_analysis F1 | ~10 | ~15 | ~30 | **~50** |

核心假设：**推理链数据（组 D）在代码分析能力上显著优于描述数据（组 C）和 NVD 数据（组 B）。**

---

## 六、关键风险

| 风险 | 概率 | 应对 |
|------|------|------|
| API 成本超预算 ($600+) | 中 | 先用 1,000 条子集验证，确认 ROI 后扩量 |
| REEF LLM_message 批量修复耗时 | 中 | 提高并发（max_concurrent=10），预计 4-6 小时 |
| 推理链质量不如预期 | 低 | Pilot 50 条先行验证，调整 prompt |
| VulnBench 输出格式不匹配 | 中 | 模型需学习输出 unified diff 格式，在 prompt 中明确要求 |
