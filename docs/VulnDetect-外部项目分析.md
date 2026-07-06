# VulnDetect 外部项目集成分析

> 分析日期：2026-07-07 | 基于实际代码审查

---

## 一、OpenRLHF 强化学习框架

**仓库**：https://github.com/OpenRLHF/OpenRLHF | 已 clone 至 `~/coding/OpenRLHF/`

### 1.1 框架概况

OpenRLHF 是社区最成熟的开源 RLHF 框架之一，基于 Ray + DeepSpeed + vLLM + HuggingFace Transformers。支持 PPO、DPO、REINFORCE++、GRPO、RLOO、KTO、Rejection Sampling、知识蒸馏等多种算法。

### 1.2 与我们框架的对比

| 维度 | 我们的 VulnDetect | OpenRLHF |
|------|-----------------|----------|
| **SFT 训练** | HuggingFace Trainer 封装 | 自己的 DeepSpeed Trainer |
| **DPO 训练** | **纯 PyTorch 自研** | 自己的 DeepSpeed Trainer |
| **PPO 训练** | ❌ 不支持（仅有骨架） | ✅ 完整 Ray+vLLM 分布式 PPO |
| **vLLM 推理加速** | ❌ 不支持 | ✅ 内置，生成阶段快 2-4x |
| **QLoRA** | ✅ 4-bit + LoRA | ✅ 同样支持 |
| **单卡训练** | ✅ A6000 48GB 够用 | SFT/DPO 可行；PPO 需多卡 |
| **RLHF 算法丰富度** | 仅 SFT/DPO | PPO + REINFORCE++ + GRPO 等 |
| **数据格式** | OpenRLHF conversation 格式 | 通用 input/output key 映射 |
| **与 HuggingFace 兼容** | ✅ 原生 HF Trainer | ✅ 原生 HF 模型加载 |

### 1.3 结论：哪个更好？

**各有优势，互补而非替代。**

- **我们的框架更好**：SFT + DPO 流程简洁、与现有工具链无缝集成、代码可控（~400 行 vs OpenRLHF 的复杂架构）
- **OpenRLHF 更好**：如果我们后续需要 PPO/RLHF 训练，它是唯一可行的选择（我们的 PPO 只是骨架）

**建议策略**：保留我们现有的 SFT/DPO 流程（它更简洁、已验证），当蒸馏实验完成后如果需要 RL 阶段（用 reward model 进一步优化漏洞检测），再引入 OpenRLHF 做 PPO。

### 1.4 复现可行性

**单卡 A6000 (48GB) 可运行 SFT/DPO**。PPO 需要 4 个模型实例（actor + ref + critic + reward + vLLM），即使是 Qwen-3B + QLoRA 在单卡上也极度紧张，建议至少 2 卡或使用 REINFORCE++（无需 critic）。

---

## 二、REEF 漏洞数据集

**仓库**：https://github.com/ASE-REEF/REEF-data | 已 clone 至 `~/coding/REEF-data/`

### 2.1 数据集概况

| 维度 | 数据 |
|------|------|
| 总样本 | **4,466 条** |
| 语言 | C (1,575), Python (863), JS (636), Java (541), C++ (411), Go (355), C# (85) |
| CWE 覆盖 | **237 种** |
| 数据格式 | JSONL，每行一个完整漏洞记录 |
| 总大小 | ~617 MB |

### 2.2 每条样本包含的字段

```json
{
  "index": 42,
  "cve_id": "CVE-2021-4315",
  "CWEs": ["CWE-1336"],
  "language": "Python",
  "cvss": "8.8",
  "origin_message": "原始 git commit message",
  "LLM_message": "LLM 生成的漏洞描述与修复说明",
  "url": "GitHub API URL",
  "html_url": "GitHub 网页链接",
  "details": [
    {
      "raw_url": "...",
      "raw_code": "修复后完整文件内容",
      "patch": "unified diff 格式的修复补丁"
    }
  ]
}
```

### 2.3 可否集成到我们的数据集？

**可以，而且建议集成。** 优势：

1. **格式兼容**：REEF 是 JSONL，与我们的 pipeline 输出格式一致
2. **字段映射简单**：
   - `cve_id` → 直接使用
   - `cvss` (如 "8.8") → 映射为 `severity`（>=9.0 CRITICAL, >=7.0 HIGH, >=4.0 MEDIUM）
   - `LLM_message` → 可作为 `description`
   - `details[0].raw_code` → 可作为 `code_snippet`
   - `details[0].patch` → 可作为 `fix`
3. **自动去重**：我们的 pipeline 已有 `dedup(by="cve_id")`，REEF 和 NVD 数据的 CVE 重叠会自动处理
4. **447 条 → 4,913 条**：加上 REEF 的 4,466 条，我们的训练数据可直接扩充 10 倍

### 2.4 需要注意的问题

- **LLM_message 质量参差不齐**：部分样本的 LLM_message 很简陋（如 "This is a test to verify CVE-XXX is fixed"），不适合直接作为训练标签
- **NVD-CWE-noinfo**：231 条样本的 CWE 是占位符，应过滤
- **多文件漏洞**：部分漏洞修改多个文件，我们当前的单文件格式只能取每个样本的第一个文件

---

## 三、VulnBench 评测框架

**仓库**：https://github.com/vulnbench/vulnbench | 已 clone 至 `~/coding/vulnbench/`

### 3.1 评测方式

**代码生成 + LLM-as-Judge 评测**，不是选择题/分类题。

流程：
1. 给模型 CVE 描述 + 漏洞代码 → 模型**生成 unified diff 补丁**
2. 提取模型输出的 diff → 与 gold patch（真实修复）一起发给 **Claude Opus + GPT-5.5** 双法官评判
3. 法官打分 0-1，score >= 0.5 且 verdict="pass" → 该题通过
4. 主要指标：**Pass Rate**（通过率）、Mean Score（平均分）

### 3.2 数据集规模

| 数据集 | 样本数 | 大小 | 用途 |
|--------|--------|------|------|
| vulnbench_full.json | **1,650** | 15 MB | 完整评测 |
| vulnbench_200.json | **200** | 1.2 MB | 精选评测子集 |
| vulnbench_mini.json | **50** | 281 KB | 快速调试 |

- 888 个仓库、55 个 CWE 类型
- 语言分布：npm (70%), pip (29%), 其他 (1%)
- 难度分三级：Tier 1 (354 模式修复) / Tier 2 (1,106 逻辑修复) / Tier 3 (190 深度推理)

### 3.3 运行成本估算

| 项目 | vulnbench_mini (50) | vulnbench_200 | vulnbench_full (1650) |
|------|---------------------|---------------|----------------------|
| 模型生成 API 费用 | ~$1-2 | ~$5-8 | ~$40-70 |
| 法官 API 费用 | ~$0.8-1.5 | ~$3-5 | ~$25-40 |
| **单次总费用** | **~$2-4** | **~$8-13** | **~$65-110** |
| 运行时间 | ~10 分钟 | ~30 分钟 | ~3-4 小时 |

*注：以上为使用 OpenRouter API 的估算。如果是本地模型（如我们训练的 Qwen-3B），模型生成费用为零，只需付法官费用。*

### 3.4 接入我们模型的方式

**三种方式：**

**方式一（最简单）**：我们的模型部署为 OpenAI 兼容 API 后，通过 `--model` 参数直接调用
```bash
python -m benchmark.run_eval \
  --benchmark data/benchmark/vulnbench_200.json \
  --model openai/qwen3b-distil-sft-v1 \
  --api-base http://localhost:8000/v1
```

**方式二（推荐）**：实现 ModelAdapter 协议，只需一个函数
```python
class VulnDetectAdapter:
    def generate_patch(self, prompt: str) -> str:
        # 加载我们的 QLoRA checkpoint，推理
        return generated_diff
```

**方式三（已有基础设施）**：我们的 `vulndetect/backend/main.py` 已有 inference API，可以对接。

### 3.5 可行性评估

**完全可行，建议集成。**

- 依赖简单：`pip install litellm pydantic pyyaml requests tqdm`
- 使用 OpenRouter 作为 API 中转（避免直接对接多个 LLM 厂商）
- 本地模型零额外费用（只需付法官评测费）
- 有完整的 checkpoint/resume 机制，中断后可续跑

### 3.6 潜在问题

- **模型必须输出 unified diff 格式**——我们的模型需要训练/提示它学会输出 diff 格式
- **默认数据集以 JS/npm 为主**（70%）——C/C++/Python 安全漏洞较少
- **LiteLLM 有供应链攻击历史**（1.82.7/1.82.8 版本）——需锁定安全版本
- **不支持批量推理**——循环逐个评估，对本地模型较慢

---

## 四、综合建议

### 优先级排序

| 优先级 | 项目 | 行动 | 原因 |
|--------|------|------|------|
| **P0（必须）** | VulnBench | 集成评测 | 甲方要求，且这是业界标准的漏洞检测评测。先用 vulnbench_mini (50 题) 验证流程 |
| **P1（强烈建议）** | REEF 数据 | 集成到数据管线 | 4,466 条高质量真实漏洞数据，直接扩充 10 倍，无需 API 费用 |
| **P2（后续）** | OpenRLHF | 暂不集成 | 当前 SFT/DPO 流程满足需求。等蒸馏实验完成，需要 RL 阶段时再引入 PPO |

### 对现有规划的影响

**不冲突，可并行推进。** 现有的 6 阶段蒸馏实验计划保持不变，同时：

1. **Phase 0.5（新增）**：将 REEF 数据导入我们的数据管线，扩充训练数据集
2. **Phase 3.5（新增）**：搭建 VulnBench 评测环境，用 vulnbench_mini 验证流程
3. **Phase 5 补充**：蒸馏实验结果在 VulnBench 上也要评测，作为主要指标之一

### 关于甲方的判断

**甲方的选择是合理的：**
- OpenRLHF 是目前社区最强的开源 RLHF 框架，论文和工程都扎实
- REEF 是 ASE 2023 论文数据集，学术可信度高，4,466 条真实 CVE
- VulnBench 是专业的漏洞修复评测基准，1,650 条精心筛选的 CVE，双法官机制严谨

**不存在吹牛**：三个项目都是学术/工业界经过验证的成果，代码和数据均可复现。
