# VulnDetect 项目进度报告

> 报告日期：2026-07-02 | 本周工作总结

---

## 一、本周完成工作

### 1.1 项目文档体系建立

完成 6 份技术文档，覆盖项目介绍、实验方案、工作计划和进展汇报：

| 文档 | 用途 |
|------|------|
| `VulnDetect-项目说明.md` | 项目完整介绍（面向外部） |
| `VulnDetect-项目说明.txt` | 纯文本版（方便粘贴汇报） |
| `VulnDetect-进展汇报.md` | 面向领导的进展汇报 |
| `VulnDetect-蒸馏实验方案.md` | 技术方案设计 |
| `VulnDetect-蒸馏工作计划.md` | 6 阶段执行计划 |
| `VulnDetect-进度报告-20260702.md` | 本文档 |

### 1.2 蒸馏实验架构设计与实现

完成蒸馏实验的全部代码开发（10 个文件，1800+ 行）：

**蒸馏数据生成管线** (`vulndetect/data_pipeline/distil/`)：
- `prompts.py` — 教师模型 prompt 模板（安全审计 / 安全代码分析 / 系统提示）
- `teacher.py` — Claude API 封装（重试机制、并发批量生成、Token 用量追踪）
- `validator.py` — 质量校验器（6 项自动检查：章节完整性、CWE 格式、行号有效性、CVSS 格式、最小长度、语言匹配）
- `pipeline.py` — CLI 编排入口（加载→生成→校验→格式转换→保存）

**评测模块** (`vulndetect/evaluation/benchmarks/code_analysis.py`)：
- LLM-as-Judge 评测机制，复用 Claude 作为评判者
- 6 项评测指标：Recall、Precision、F1、CWE Accuracy、Fix Correctness、FPR

**实验配置**：
- `exp002_distil_sft.yaml` — 蒸馏 SFT 实验（max_seq 4096）
- `exp003_distil_dpo.yaml` — 蒸馏 DPO 实验（可选 Phase 6）

**测试** (`tests/data_pipeline/test_distil.py`)：
- 24 个 pytest 测试用例，21 pass / 3 skip（需 Anthropic SDK）

### 1.3 评测数据集构建（Phase 0 + Phase 1）

**评测集**（hold-out，不参与训练）：
- 100 条代码样本（50 漏洞 + 50 安全）
- 覆盖 13 种 CWE 类型、10 种编程语言
- 每条包含 ground truth（CWE ID、漏洞类型、严重度、修复参考）

**训练集**（用于教师模型生成推理链）：
- 607 条代码样本（381 漏洞 + 226 安全）
- 覆盖 16 种 CWE 类型、9 种编程语言
- 已划分为训练集 546 条 + 验证集 61 条

**CWE 覆盖度**：

| CWE | 类型 | 覆盖情况 |
|-----|------|---------|
| CWE-89 | SQL 注入 | ✅ |
| CWE-79 | 跨站脚本 (XSS) | ✅ |
| CWE-78 | 命令注入 | ✅ |
| CWE-22 | 路径遍历 | ✅ |
| CWE-502 | 不安全的反序列化 | ✅ |
| CWE-120 | 缓冲区溢出 | ✅ |
| CWE-190 | 整数溢出 | ✅ |
| CWE-327 | 弱加密算法 | ✅ |
| CWE-798 | 硬编码凭据 | ✅ |
| CWE-200 | 信息泄露 | ✅ |
| CWE-287/306 | 认证绕过 | ✅ |
| CWE-434 | 不受限的文件上传 | ✅ |
| CWE-918 | SSRF | ✅ |
| CWE-416 | 释放后使用 | ✅ |
| CWE-601 | 开放重定向 | ✅ |
| CWE-311 | 敏感数据未加密 | ✅ |

---

## 二、当前状态

### 平台层

| 子系统 | 状态 | 说明 |
|--------|------|------|
| 数据管线 | ✅ 完成 | NVD + GitHub Advisory + 蒸馏生成 |
| 训练管线 | ✅ 完成 | QLoRA SFT/DPO/PPO |
| 评测管线 | ✅ 完成 | lm_eval 5 benchmarks + 自定义代码分析 |
| Web 后端 | ✅ 完成 | FastAPI + WebSocket + SQLite |
| Web 前端 | ✅ 完成 | React 5 页面 Dashboard |
| 代码测试 | ✅ 完成 | 21 个蒸馏模块测试通过 |

### 实验进度

| 阶段 | 状态 | 产出 |
|------|------|------|
| Phase 0：环境准备 | ✅ 完成 | GPU 验证、SDK 安装、评测集 100 条 |
| Phase 1：代码样本收集 | ✅ 完成 | 训练样本 607 条（546 train + 61 val） |
| Phase 2：教师推理数据生成 | 🔜 待开始 | 需配置 `ANTHROPIC_API_KEY` |
| Phase 3：基线训练 | 🔜 待开始 | 依赖 Phase 2 数据 |
| Phase 4：蒸馏模型训练 | 🔜 待开始 | 核心实验步骤 |
| Phase 5：结果分析 | 🔜 待开始 | 实验结论与决策 |

### 待配置项

| 配置 | 说明 |
|------|------|
| `ANTHROPIC_API_KEY` | Claude Opus API 密钥，Phase 2 需要 |

---

## 三、下一步计划

### 近期（下周）

1. **配置 API Key**，启动 Phase 2 教师推理数据生成
   - Pilot run：先 50 条验证 prompt 质量和输出格式
   - 批量生成：546 条训练数据，预计 $50-65 API 成本
2. **Phase 3 基线训练**（可与 Phase 2 并行）
   - 用现有 NVD 数据训练基线模型
   - 在 6 个 benchmarks 上评测（5 lm_eval + 1 自定义）
3. **Phase 4 蒸馏模型训练**
   - 用教师推理链数据训练蒸馏模型
   - 三组对照评测（Base vs NVD-SFT vs Distil-SFT）

### 预计时间

| 阶段 | 工时 | 累计 |
|------|------|------|
| Phase 2：教师数据生成 | 1 天 | — |
| Phase 3：基线训练 | 0.5 天 | 可并行 |
| Phase 4：蒸馏训练 | 0.5 天 | — |
| Phase 5：分析报告 | 0.5 天 | — |
| **合计** | **2-2.5 天** | |

---

## 四、仓库文件清单（当前状态）

```
ndfactory/
├── vulndetect/
│   ├── data_pipeline/distil/      # 【新增】蒸馏数据生成管线
│   │   ├── prompts.py             #   Prompt 模板
│   │   ├── teacher.py             #   Claude API 封装
│   │   ├── validator.py           #   质量校验
│   │   └── pipeline.py            #   CLI 入口
│   ├── config/experiments/
│   │   ├── exp001_sft.yaml        #   【已有】基线实验
│   │   ├── exp002_distil_sft.yaml #   【新增】蒸馏 SFT
│   │   └── exp003_distil_dpo.yaml #   【新增】蒸馏 DPO
│   ├── evaluation/benchmarks/
│   │   ├── registry.py            #   【修改】新增 code_vuln_analysis
│   │   └── code_analysis.py       #   【新增】代码分析评测
│   └── tests/
│       └── data_pipeline/
│           └── test_distil.py     #   【新增】蒸馏模块测试
├── data/distil/
│   ├── samples_eval.jsonl         #   评测集 100 条（hold-out）
│   ├── samples_train.jsonl        #   训练集 546 条
│   ├── samples_val.jsonl          #   验证集 61 条
│   └── samples.jsonl              #   全量备份 607 条
├── scripts/
│   ├── seed_eval_set.py           #   评测集生成脚本
│   └── seed_eval_set_extra.py     #   评测集补充脚本
└── docs/
    ├── VulnDetect-项目说明.md
    ├── VulnDetect-项目说明.txt
    ├── VulnDetect-进展汇报.md
    ├── VulnDetect-蒸馏实验方案.md
    ├── VulnDetect-蒸馏工作计划.md
    └── VulnDetect-进度报告-20260702.md
```

---

## 五、总结

**一句话**：蒸馏实验的基础设施和数据集已全部就绪，代码测试通过，下一步只需配置 API Key 即可启动核心实验（教师推理数据生成 + 模型训练 + 评测对比），预计 2-2.5 天完成全部实验。
