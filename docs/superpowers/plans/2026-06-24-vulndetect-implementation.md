# VulnDetect 实现计划

> **面向 AI 代理的工作者：** 使用 superpowers:subagent-driven-development 逐任务实现。步骤使用复选框（`- [ ]`）跟踪进度。

**目标：** 从零搭建漏洞检测模型训练与验证框架 + Web UI，Qwen-3B QLoRA 单卡 A6000 跑通 SFT→DPO→PPO。

**架构：** 5 模块松耦合——数据管线、训练管线（OpenRLHF 封装）、评测管线（lm-eval-harness）、推理服务、Web UI（React+FastAPI）。配置驱动（YAML），模块间通过 SQLite + 文件系统通信。

**技术栈：** PyTorch, bitsandbytes, PEFT, DeepSpeed ZeRO-2, OpenRLHF, lm-evaluation-harness, FastAPI, SQLAlchemy, SQLite, React 18, TypeScript, Vite, shadcn/ui, Tailwind CSS, Recharts

---

## 阶段 0：项目脚手架

### 任务 0.1：创建目录结构和依赖配置

- 创建：`vulndetect/requirements.txt`
- 创建：`vulndetect/config/model/qwen3b.yaml`
- 创建：`vulndetect/config/data/vulnbench.yaml`

- [ ] **步骤 1：创建目录结构**

```bash
mkdir -p vulndetect/{config/{model,data,train,experiments},data_pipeline/{collectors,cleaners,formatters},training/openrlhf_wrapper,evaluation/benchmarks,backend/{api,models,services},frontend/src/{layouts,pages,components,hooks,lib},scripts,experiments}
```

- [ ] **步骤 2：编写 requirements.txt**

```txt
torch>=2.4.0
transformers>=4.44.0
datasets>=2.20.0
accelerate>=0.33.0
bitsandbytes>=0.43.0
peft>=0.12.0
deepspeed>=0.14.0
trl>=0.9.0
fastapi>=0.112.0
uvicorn[standard]>=0.30.0
sqlalchemy>=2.0.0
websockets>=12.0
pyyaml>=6.0
wandb>=0.17.0
tensorboard>=2.17.0
requests>=2.32.0
rich>=13.0.0
pydantic>=2.0.0
pytest>=8.0.0
```

- [ ] **步骤 3：编写模型配置**

创建 `vulndetect/config/model/qwen3b.yaml`：

```yaml
model:
  name_or_path: "Qwen/Qwen2.5-3B-Instruct"
  trust_remote_code: true

quantization:
  load_in_4bit: true
  bnb_4bit_compute_dtype: "bfloat16"
  bnb_4bit_use_double_quant: true
  bnb_4bit_quant_type: "nf4"

lora:
  r: 16
  alpha: 32
  dropout: 0.05
  target_modules:
    - q_proj
    - k_proj
    - v_proj
    - o_proj
    - gate_proj
    - up_proj
    - down_proj
```

- [ ] **步骤 4：编写数据集配置**

创建 `vulndetect/config/data/vulnbench.yaml`：

```yaml
dataset:
  name: "vulnbench"
  source: "https://github.com/vulnbench/vulnbench"
  format: "conversation"

preprocessing:
  max_seq_length: 2048
  val_split: 0.1
  shuffle: true
  seed: 42

splits:
  train: "data/train"
  val: "data/val"
  test: "data/test"
```

- [ ] **步骤 5：Commit**

```bash
git add -A && git commit -m "chore: scaffold project structure and configs"
```

---

## 阶段 1：环境搭建 + SFT 跑通

### 任务 1.1：编写环境初始化脚本

- 创建：`vulndetect/scripts/setup_env.sh`

- [ ] **步骤 1：编写环境检测和初始化脚本**

```bash
#!/bin/bash
# vulndetect/scripts/setup_env.sh
set -e

echo "=== VulnDetect Environment Setup ==="

# Check GPU
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    echo "CUDA available: $(python3 -c 'import torch; print(torch.cuda.is_available())')"
else
    echo "WARNING: nvidia-smi not found"
fi

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Created virtual environment: venv/"
fi

source venv/bin/activate

# Install PyTorch with CUDA 12.1
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install dependencies
pip install -r requirements.txt

# Verify key packages
python3 -c "
import torch
import transformers
import bitsandbytes
import peft
print(f'PyTorch: {torch.__version__}')
print(f'CUDA Available: {torch.cuda.is_available()}')
print(f'GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB')
print(f'Transformers: {transformers.__version__}')
print(f'Bitsandbytes: {bitsandbytes.__version__}')
print(f'PEFT: {peft.__version__}')
"

echo "=== Setup Complete ==="
```

- [ ] **步骤 2：添加执行权限并测试**

```bash
chmod +x vulndetect/scripts/setup_env.sh
bash vulndetect/scripts/setup_env.sh
```

预期输出：显示 GPU 信息、CUDA 可用、各库版本号

- [ ] **步骤 3：Commit**

```bash
git add vulndetect/scripts/setup_env.sh && git commit -m "feat: add environment setup script"
```

### 任务 1.2：OpenRLHF 封装层——数据加载适配

- 创建：`vulndetect/training/openrlhf_wrapper/__init__.py`
- 创建：`vulndetect/training/openrlhf_wrapper/datasets.py`
- 创建：`vulndetect/tests/training/test_datasets.py`

- [ ] **步骤 1：编写失败的测试**

```python
# vulndetect/tests/training/test_datasets.py
import pytest
import json
import tempfile
from pathlib import Path

@pytest.fixture
def sample_conversation_data():
    """创建 OpenRLHF conversation 格式的样本数据"""
    return [
        {
            "conversations": [
                {"from": "human", "value": "这段代码有漏洞吗？\n```python\nimport os\ncmd = input()\nos.system(cmd)\n```"},
                {"from": "gpt", "value": "是的，存在命令注入漏洞。os.system(cmd) 直接执行用户输入的命令，攻击者可以注入任意系统命令。"}
            ]
        }
    ]


def test_load_conversation_dataset(sample_conversation_data):
    """测试加载 conversation 格式数据集"""
    from vulndetect.training.openrlhf_wrapper.datasets import load_conversation_dataset

    with tempfile.TemporaryDirectory() as tmpdir:
        data_file = Path(tmpdir) / "train.jsonl"
        with open(data_file, "w") as f:
            for item in sample_conversation_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        dataset = load_conversation_dataset(str(data_file))
        assert len(dataset) == 1
        assert "human" in dataset[0]
        assert "gpt" in dataset[0]


def test_format_for_sft(sample_conversation_data):
    """测试 SFT 格式转换：conversation -> prompt + response"""
    from vulndetect.training.openrlhf_wrapper.datasets import format_for_sft

    formatted = format_for_sft(sample_conversation_data[0])
    assert "prompt" in formatted
    assert "response" in formatted
    assert "os.system(cmd)" in formatted["prompt"]
    assert "命令注入" in formatted["response"]


def test_format_for_dpo(sample_conversation_data):
    """测试 DPO 格式转换：需要 chosen 和 rejected"""
    from vulndetect.training.openrlhf_wrapper.datasets import format_for_dpo

    dpo_item = {
        "conversations": [
            {"from": "human", "value": "问题"}
        ],
        "chosen": {"from": "gpt", "value": "好的回答"},
        "rejected": {"from": "gpt", "value": "差的回答"}
    }
    formatted = format_for_dpo(dpo_item)
    assert "prompt" in formatted
    assert "chosen" in formatted
    assert "rejected" in formatted
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd vulndetect && python -m pytest tests/training/test_datasets.py -v
```

预期：FAIL，ModuleNotFoundError

- [ ] **步骤 3：编写实现**

```python
# vulndetect/training/openrlhf_wrapper/__init__.py
"""OpenRLHF 封装层——单卡适配"""
```

```python
# vulndetect/training/openrlhf_wrapper/datasets.py
"""数据集加载与格式转换——兼容 OpenRLHF conversation 格式"""
import json
from pathlib import Path
from typing import Dict, List, Optional


def load_conversation_dataset(file_path: str) -> List[Dict]:
    """从 JSONL 文件加载 conversation 格式数据集"""
    data = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def format_for_sft(item: Dict) -> Dict[str, str]:
    """将 conversation 格式转换为 SFT 的 prompt + response"""
    conversations = item.get("conversations", [])
    human_msgs = [c["value"] for c in conversations if c["from"] == "human"]
    gpt_msgs = [c["value"] for c in conversations if c["from"] == "gpt"]

    prompt = "\n".join(human_msgs)
    response = "\n".join(gpt_msgs)
    return {"prompt": prompt, "response": response}


def format_for_dpo(item: Dict) -> Dict[str, str]:
    """将 conversation 格式转换为 DPO 的 prompt + chosen + rejected"""
    conversations = item.get("conversations", [])
    human_msgs = [c["value"] for c in conversations if c["from"] == "human"]
    prompt = "\n".join(human_msgs)

    chosen = item.get("chosen", {}).get("value", "")
    rejected = item.get("rejected", {}).get("value", "")
    return {"prompt": prompt, "chosen": chosen, "rejected": rejected}


def save_conversation_dataset(data: List[Dict], file_path: str):
    """保存数据集为 JSONL 格式"""
    with open(file_path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def split_dataset(data: List[Dict], val_split: float = 0.1, seed: int = 42):
    """划分训练集和验证集"""
    import random
    random.seed(seed)
    random.shuffle(data)
    split_idx = int(len(data) * (1 - val_split))
    return data[:split_idx], data[split_idx:]
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd vulndetect && python -m pytest tests/training/test_datasets.py -v
```

预期：3 PASSED

- [ ] **步骤 5：Commit**

```bash
git add vulndetect/training/openrlhf_wrapper/ vulndetect/tests/ && git commit -m "feat: add OpenRLHF dataset loading and format conversion"
```

### 任务 1.3：OpenRLHF 封装层——模型加载适配

- 创建：`vulndetect/training/openrlhf_wrapper/models.py`
- 创建：`vulndetect/tests/training/test_models.py`

- [ ] **步骤 1：编写模型加载测试**

```python
# vulndetect/tests/training/test_models.py
import pytest


def test_build_qlora_config():
    """测试 QLoRA 配置构建"""
    from vulndetect.training.openrlhf_wrapper.models import build_qlora_config

    model_config = {
        "quantization": {
            "load_in_4bit": True,
            "bnb_4bit_compute_dtype": "bfloat16",
            "bnb_4bit_use_double_quant": True,
            "bnb_4bit_quant_type": "nf4"
        },
        "lora": {
            "r": 8,
            "alpha": 16,
            "dropout": 0.05,
            "target_modules": ["q_proj", "v_proj"]
        }
    }

    bnb_config, lora_config = build_qlora_config(model_config)
    assert bnb_config is not None
    assert lora_config.r == 8
    assert lora_config.lora_alpha == 16
    assert "q_proj" in lora_config.target_modules


def test_build_qlora_config_defaults():
    """测试默认配置"""
    from vulndetect.training.openrlhf_wrapper.models import build_qlora_config

    default_config = {}
    bnb_config, lora_config = build_qlora_config(default_config)
    assert bnb_config is not None
    assert lora_config.r == 16  # default
    assert lora_config.lora_alpha == 32  # default


def test_get_target_modules_qwen():
    """测试 Qwen 模型的 target modules"""
    from vulndetect.training.openrlhf_wrapper.models import get_target_modules

    modules = get_target_modules("qwen")
    assert "q_proj" in modules
    assert "v_proj" in modules
    assert len(modules) >= 4
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd vulndetect && python -m pytest tests/training/test_models.py -v
```

预期：FAIL

- [ ] **步骤 3：编写实现**

```python
# vulndetect/training/openrlhf_wrapper/models.py
"""模型加载——QLoRA 配置 + 基座模型加载"""
from typing import Dict, Tuple, List
from transformers import BitsAndBytesConfig
from peft import LoraConfig


def build_qlora_config(config: Dict) -> Tuple[BitsAndBytesConfig, LoraConfig]:
    """从配置字典构建 QLoRA 的量化配置和 LoRA 配置"""
    quant_cfg = config.get("quantization", {})
    lora_cfg = config.get("lora", {})

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=quant_cfg.get("load_in_4bit", True),
        bnb_4bit_compute_dtype=quant_cfg.get("bnb_4bit_compute_dtype", "bfloat16"),
        bnb_4bit_use_double_quant=quant_cfg.get("bnb_4bit_use_double_quant", True),
        bnb_4bit_quant_type=quant_cfg.get("bnb_4bit_quant_type", "nf4"),
    )

    lora_config = LoraConfig(
        r=lora_cfg.get("r", 16),
        lora_alpha=lora_cfg.get("alpha", 32),
        lora_dropout=lora_cfg.get("dropout", 0.05),
        target_modules=lora_cfg.get("target_modules", get_target_modules("qwen")),
        bias="none",
        task_type="CAUSAL_LM",
    )

    return bnb_config, lora_config


def get_target_modules(model_family: str = "qwen") -> List[str]:
    """获取不同模型家族的默认 LoRA target modules"""
    target_modules_map = {
        "qwen": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        "llama": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        "mistral": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    }
    return target_modules_map.get(model_family, target_modules_map["qwen"])


def load_model_and_tokenizer(model_config: Dict):
    """加载基座模型和 tokenizer（QLoRA 量化）"""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_name = model_config.get("model", {}).get("name_or_path", "Qwen/Qwen2.5-3B-Instruct")
    trust_remote = model_config.get("model", {}).get("trust_remote_code", True)
    bnb_config, _ = build_qlora_config(model_config)

    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        trust_remote_code=trust_remote,
        padding_side="right",
    )

    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=trust_remote,
        torch_dtype=torch.bfloat16,
    )

    return model, tokenizer
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd vulndetect && python -m pytest tests/training/test_models.py -v
```

预期：3 PASSED

- [ ] **步骤 5：Commit**

```bash
git add vulndetect/training/openrlhf_wrapper/models.py vulndetect/tests/training/test_models.py && git commit -m "feat: add QLoRA model loading and config builder"
```

### 任务 1.4：配置加载器

- 创建：`vulndetect/training/config_loader.py`
- 创建：`vulndetect/tests/training/test_config_loader.py`

- [ ] **步骤 1：编写测试**

```python
# vulndetect/tests/training/test_config_loader.py
import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def sample_yaml_config():
    return """
experiment:
  name: "test-exp"
  description: "test"

model:
  name_or_path: "Qwen/Qwen2.5-3B-Instruct"
  trust_remote_code: true

quantization:
  load_in_4bit: true
  bnb_4bit_compute_dtype: "bfloat16"

lora:
  r: 8
  alpha: 16
  dropout: 0.05
  target_modules:
    - q_proj
    - v_proj

training:
  strategy: "sft"
  sft:
    lora_r: 8
    lora_alpha: 16
  max_seq_length: 2048
  per_device_train_batch_size: 2
  learning_rate: 2.0e-4
  num_epochs: 1

data:
  train_dataset: "vulnbench"
  val_split: 0.1

evaluation:
  benchmarks:
    - vulnbench
    - seceval
"""


def test_load_experiment_config(sample_yaml_config):
    """测试加载实验配置文件"""
    from vulndetect.training.config_loader import load_config

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(sample_yaml_config)
        config_path = f.name

    config = load_config(config_path)
    assert config["experiment"]["name"] == "test-exp"
    assert config["training"]["strategy"] == "sft"
    assert config["model"]["name_or_path"] == "Qwen/Qwen2.5-3B-Instruct"

    Path(config_path).unlink()


def test_merge_configs():
    """测试配置合并：实验配置覆盖基础配置"""
    from vulndetect.training.config_loader import merge_configs

    base = {"training": {"max_seq_length": 2048, "num_epochs": 1}}
    override = {"training": {"num_epochs": 3}}

    merged = merge_configs(base, override)
    assert merged["training"]["max_seq_length"] == 2048
    assert merged["training"]["num_epochs"] == 3
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd vulndetect && python -m pytest tests/training/test_config_loader.py -v
```

预期：FAIL

- [ ] **步骤 3：编写实现**

```python
# vulndetect/training/config_loader.py
"""YAML 配置加载——支持多文件合并和变量替换"""
import yaml
from pathlib import Path
from typing import Dict, Any
from copy import deepcopy


def load_config(config_path: str) -> Dict[str, Any]:
    """加载单个 YAML 配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """深度合并两个配置字典，override 中的值覆盖 base"""
    merged = deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def load_experiment_config(experiment_path: str) -> Dict[str, Any]:
    """加载实验配置——自动合并 model/data/train 基础配置"""
    exp_config = load_config(experiment_path)

    config_dir = Path("config")

    # 合并模型配置
    model_config_path = exp_config.get("includes", {}).get("model", None)
    if model_config_path:
        exp_config = merge_configs(load_config(str(config_dir / model_config_path)), exp_config)

    # 合并训练配置
    train_config_path = exp_config.get("includes", {}).get("training", None)
    if train_config_path:
        exp_config = merge_configs(load_config(str(config_dir / train_config_path)), exp_config)

    return exp_config
```

- [ ] **步骤 4：运行测试验证通过**

```bash
cd vulndetect && python -m pytest tests/training/test_config_loader.py -v
```

预期：2 PASSED

- [ ] **步骤 5：Commit**

```bash
git add vulndetect/training/config_loader.py vulndetect/tests/training/test_config_loader.py && git commit -m "feat: add YAML config loader with merge support"
```

### 任务 1.5：QLoRA SFT 训练脚本

- 创建：`vulndetect/training/__init__.py`
- 创建：`vulndetect/training/trainer.py`
- 创建：`vulndetect/training/checkpoint.py`
- 创建：`vulndetect/training/sft.py`

- [ ] **步骤 1：编写断点续训管理**

```python
# vulndetect/training/checkpoint.py
"""Checkpoint 管理——保存、恢复、查找最新"""
import os
import json
from pathlib import Path
from typing import Optional, Dict


def save_checkpoint(
    model, tokenizer, output_dir: str, step: int, loss: float, metrics: Optional[Dict] = None
):
    """保存 checkpoint（LoRA adapter + training state）"""
    os.makedirs(output_dir, exist_ok=True)

    # 保存 LoRA adapter
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    # 保存训练状态
    state = {
        "step": step,
        "loss": loss,
        "metrics": metrics or {},
    }
    with open(Path(output_dir) / "trainer_state.json", "w") as f:
        json.dump(state, f, indent=2)


def load_checkpoint(model, checkpoint_dir: str) -> Dict:
    """从 checkpoint 恢复训练状态"""
    from peft import PeftModel

    state_path = Path(checkpoint_dir) / "trainer_state.json"
    if not state_path.exists():
        return {"step": 0, "loss": None, "metrics": {}}

    with open(state_path, "r") as f:
        state = json.load(f)

    return state


def find_latest_checkpoint(experiment_dir: str) -> Optional[str]:
    """查找最新的 checkpoint"""
    checkpoints_dir = Path(experiment_dir) / "checkpoints"
    if not checkpoints_dir.exists():
        return None

    checkpoints = sorted(
        [d for d in checkpoints_dir.iterdir() if d.is_dir() and (d / "trainer_state.json").exists()],
        key=lambda x: int(x.name.replace("checkpoint-", "")),
        reverse=True,
    )
    return str(checkpoints[0]) if checkpoints else None
```

- [ ] **步骤 2：编写统一 Trainer 类**

```python
# vulndetect/training/trainer.py
"""统一 Trainer——封装 SFT/DPO/PPO 训练循环"""
import os
import json
import time
import torch
from pathlib import Path
from typing import Dict, Optional, Callable
from transformers import (
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq,
    EarlyStoppingCallback,
)
from trl import SFTTrainer
from peft import get_peft_model, prepare_model_for_kbit_training

from vulndetect.training.checkpoint import save_checkpoint, find_latest_checkpoint
from vulndetect.training.openrlhf_wrapper.models import build_qlora_config, load_model_and_tokenizer


class VulnDetectTrainer:
    """通用训练器——支持 SFT/DPO/PPO，配置驱动"""

    def __init__(self, config: Dict):
        self.config = config
        self.model = None
        self.tokenizer = None
        self.trainer = None
        self.experiment_dir = Path("experiments") / config["experiment"]["name"]
        self.checkpoints_dir = self.experiment_dir / "checkpoints"
        self.logs_dir = self.experiment_dir / "logs"

    def setup(self):
        """初始化模型、tokenizer、LoRA"""
        os.makedirs(self.checkpoints_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

        self.model, self.tokenizer = load_model_and_tokenizer(self.config)
        self.model = prepare_model_for_kbit_training(self.model)
        _, lora_config = build_qlora_config(self.config)
        self.model = get_peft_model(self.model, lora_config)
        self.model.config.use_cache = False

        # 恢复 checkpoint
        latest = find_latest_checkpoint(str(self.experiment_dir))
        if latest:
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(self.model, latest)
            print(f"Resumed from checkpoint: {latest}")

    def train_sft(self, train_dataset, eval_dataset=None):
        """执行 QLoRA SFT 训练"""
        train_cfg = self.config.get("training", {})

        training_args = TrainingArguments(
            output_dir=str(self.checkpoints_dir),
            per_device_train_batch_size=train_cfg.get("per_device_train_batch_size", 4),
            gradient_accumulation_steps=train_cfg.get("gradient_accumulation_steps", 4),
            learning_rate=train_cfg.get("learning_rate", 2.0e-4),
            num_train_epochs=train_cfg.get("num_epochs", 3),
            logging_steps=train_cfg.get("logging_steps", 10),
            save_steps=train_cfg.get("save_steps", 200),
            eval_steps=train_cfg.get("eval_steps", 200),
            evaluation_strategy="steps" if eval_dataset else "no",
            save_total_limit=3,
            fp16=False,
            bf16=True,
            warmup_ratio=train_cfg.get("warmup_ratio", 0.1),
            lr_scheduler_type=train_cfg.get("lr_scheduler_type", "cosine"),
            gradient_checkpointing=train_cfg.get("gradient_checkpointing", True),
            report_to=["tensorboard"],
            logging_dir=str(self.logs_dir),
            ddp_find_unused_parameters=False,
            remove_unused_columns=False,
            dataloader_num_workers=2,
        )

        data_collator = DataCollatorForSeq2Seq(
            tokenizer=self.tokenizer,
            padding=True,
        )

        self.trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            data_collator=data_collator,
        )

        self.trainer.train()

        # 保存最终模型
        final_dir = str(self.checkpoints_dir / "final")
        self.model.save_pretrained(final_dir)
        self.tokenizer.save_pretrained(final_dir)

        return self.trainer.state
```

- [ ] **步骤 3：编写 SFT 入口脚本**

```python
# vulndetect/training/sft.py
#!/usr/bin/env python3
"""QLoRA SFT 训练入口——配置驱动，单卡运行"""
import sys
import argparse
from datasets import load_dataset
from vulndetect.training.config_loader import load_experiment_config
from vulndetect.training.trainer import VulnDetectTrainer
from vulndetect.training.openrlhf_wrapper.datasets import (
    load_conversation_dataset,
    format_for_sft,
    split_dataset,
)


def prepare_sft_dataset(data_config, tokenizer, max_seq_length=2048):
    """准备 SFT 数据集——加载 + 格式化 + tokenize"""
    dataset_name = data_config.get("dataset", {}).get("name", "vulnbench")
    val_split = data_config.get("preprocessing", {}).get("val_split", 0.1)

    # 加载原始数据（优先本地 JSONL，其次 HuggingFace datasets）
    import os
    local_path = f"data/{dataset_name}/train.jsonl"
    if os.path.exists(local_path):
        raw_data = load_conversation_dataset(local_path)
        train_data, val_data = split_dataset(raw_data, val_split)
    else:
        # 尝试从 HuggingFace 加载
        dataset = load_dataset(dataset_name, split="train")
        train_data, val_data = dataset.train_test_split(test_size=val_split).values()

    # 格式化为 prompt+response
    def format_fn(item):
        formatted = format_for_sft(item)
        return {
            "text": f"{formatted['prompt']}\n\n{formatted['response']}"
        }

    # 这里返回原始数据列表，由 Trainer 内部 tokenize
    # 简化处理——实际使用时需要更复杂的 dataset 类
    return train_data, val_data


def main():
    parser = argparse.ArgumentParser(description="QLoRA SFT Training")
    parser.add_argument("--config", type=str, required=True, help="Path to experiment YAML config")
    args = parser.parse_args()

    config = load_experiment_config(args.config)
    print(f"Experiment: {config['experiment']['name']}")
    print(f"Strategy: {config['training']['strategy']}")

    trainer = VulnDetectTrainer(config)
    trainer.setup()

    train_data, val_data = prepare_sft_dataset(
        config.get("data", {}),
        trainer.tokenizer,
        config.get("training", {}).get("max_seq_length", 2048),
    )

    print(f"Train samples: {len(train_data)}, Val samples: {len(val_data)}")
    trainer.train_sft(train_data, val_data)
    print("Training complete!")


if __name__ == "__main__":
    main()
```

- [ ] **步骤 4：编写实验配置**

```yaml
# vulndetect/config/experiments/exp001_sft.yaml
experiment:
  name: "qwen3b-sft-vulnbench-v1"
  description: "Qwen-3B QLoRA SFT on VulnBench"

includes:
  model: "model/qwen3b.yaml"
  training: "train/sft_qlora.yaml"

data:
  dataset:
    name: "vulnbench"
  preprocessing:
    max_seq_length: 2048
    val_split: 0.1
    shuffle: true
    seed: 42

evaluation:
  benchmarks:
    - vulnbench
    - seceval
  eval_on_checkpoint: true
  eval_every_n_steps: 200
```

```yaml
# vulndetect/config/train/sft_qlora.yaml
training:
  strategy: "sft"
  sft:
    lora_r: 16
    lora_alpha: 32
    lora_dropout: 0.05
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
```

- [ ] **步骤 5：运行训练验证（空跑——检查组件加载正常）**

```bash
cd vulndetect && python -c "
from training.config_loader import load_config
cfg = load_config('config/experiments/exp001_sft.yaml')
print('Config loaded OK:', cfg['experiment']['name'])
print('Strategy:', cfg['training']['strategy'])
print('Benchmarks:', cfg['evaluation']['benchmarks'])
"
```

预期输出：显示配置信息

- [ ] **步骤 6：Commit**

```bash
git add vulndetect/training/ vulndetect/config/experiments/ vulndetect/config/train/ && git commit -m "feat: add QLoRA SFT trainer and entry script"
```


---

## 阶段 2：评测管线

### 任务 2.1：lm-eval-harness 封装

- 创建：`vulndetect/evaluation/__init__.py`
- 创建：`vulndetect/evaluation/harness.py`
- 创建：`vulndetect/tests/evaluation/test_harness.py`

- [ ] **步骤 1：编写测试**

```python
# vulndetect/tests/evaluation/test_harness.py
import pytest
import json
import tempfile
from pathlib import Path


def test_build_eval_command():
    """测试构建 lm-eval 命令"""
    from vulndetect.evaluation.harness import build_eval_command

    cmd = build_eval_command(
        model_path="experiments/exp001/checkpoints/checkpoint-200",
        benchmarks=["vulnbench", "seceval"],
        output_dir="/tmp/eval_output",
    )
    assert "lm_eval" in cmd[0]
    assert "--model" in cmd
    assert "vulnbench,seceval" in " ".join(cmd)
    assert "/tmp/eval_output" in " ".join(cmd)


def test_parse_eval_results():
    """测试解析 lm-eval 输出"""
    from vulndetect.evaluation.harness import parse_eval_results

    sample_output = """
    |  Groups  |Version|Filter|n-shot|Metric|   |Value |   |Stderr|
    |----------|------:|------|------|------|---|-----:|---|-----:|
    |vulnbench | 1.0   |none  | 0    |acc   |↑  |0.7654|±  |0.0123|
    |seceval   | 1.0   |none  | 0    |acc   |↑  |0.8210|±  |0.0098|
    """

    results = parse_eval_results(sample_output)
    assert len(results) == 2
    assert results["vulnbench"]["score"] == 0.7654
    assert results["seceval"]["score"] == 0.8210
```

- [ ] **步骤 2：运行测试验证失败**

```bash
cd vulndetect && python -m pytest tests/evaluation/test_harness.py -v
```

预期：FAIL

- [ ] **步骤 3：编写实现**

```python
# vulndetect/evaluation/__init__.py
"""评测管线——lm-eval-harness 封装 + 自动调度"""
```

```python
# vulndetect/evaluation/harness.py
"""lm-evaluation-harness 封装——命令构建 + 结果解析"""
import subprocess
import json
import re
import os
from pathlib import Path
from typing import List, Dict, Optional


def build_eval_command(
    model_path: str,
    benchmarks: List[str],
    output_dir: str,
    model_type: str = "hf",
    batch_size: str = "auto",
) -> List[str]:
    """构建 lm_eval 命令行参数"""
    return [
        "lm_eval",
        "--model", model_type,
        "--model_args", f"pretrained={model_path},trust_remote_code=True",
        "--tasks", ",".join(benchmarks),
        "--batch_size", batch_size,
        "--output_path", output_dir,
        "--log_samples",
    ]


def run_evaluation(
    model_path: str,
    benchmarks: List[str],
    output_dir: str,
) -> Dict[str, Dict]:
    """运行 lm-eval 并返回解析后的结果"""
    cmd = build_eval_command(model_path, benchmarks, output_dir)
    os.makedirs(output_dir, exist_ok=True)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=3600,  # 1 hour timeout
    )

    if result.returncode != 0:
        raise RuntimeError(f"lm_eval failed: {result.stderr}")

    return parse_eval_results(result.stdout)


def parse_eval_results(output: str) -> Dict[str, Dict]:
    """从 lm_eval 表格输出解析分数"""
    results = {}

    # 匹配表格行：|benchmark|version|filter|n-shot|metric||value||stderr|
    pattern = r'\|\s*(\S+)\s*\|\s*\S+\s*\|\s*\S+\s*\|\s*\d+\s*\|\s*(\S+)\s*\|\s*\S*\|\s*([\d.]+)\s*\|\s*\S*\|\s*([\d.]+)\s*\|'
    for match in re.finditer(pattern, output):
        benchmark = match.group(1)
        metric = match.group(2)
        score = float(match.group(3))
        stderr = float(match.group(4))
        results[benchmark] = {
            "metric": metric,
            "score": score,
            "stderr": stderr,
        }

    return results


def load_results_from_file(output_dir: str) -> Dict:
    """从 lm_eval 输出的 JSON 文件加载结果"""
    results_file = Path(output_dir) / "results.json"
    if results_file.exists():
        with open(results_file, "r") as f:
            return json.load(f)
    return {}
```

- [ ] **步骤 4：运行测试通过**

```bash
cd vulndetect && python -m pytest tests/evaluation/test_harness.py -v
```

预期：2 PASSED

- [ ] **步骤 5：Commit**

```bash
git add vulndetect/evaluation/ vulndetect/tests/evaluation/ && git commit -m "feat: add lm-eval-harness wrapper"
```

### 任务 2.2：Benchmark 注册 + 评测调度器

- 创建：`vulndetect/evaluation/benchmarks/__init__.py`
- 创建：`vulndetect/evaluation/benchmarks/registry.py`
- 创建：`vulndetect/evaluation/scheduler.py`
- 创建：`vulndetect/evaluation/reporter.py`

- [ ] **步骤 1：编写 benchmark 注册表**

```python
# vulndetect/evaluation/benchmarks/__init__.py
"""安全评测 Benchmark 注册——统一管理所有评测集"""
```

```python
# vulndetect/evaluation/benchmarks/registry.py
"""Benchmark 注册表——名称 → lm_eval task 映射"""
from typing import Dict

BENCHMARK_REGISTRY: Dict[str, Dict] = {
    "vulnbench": {
        "task": "vulnbench",
        "type": "security",
        "description": "漏洞检测能力评测",
        "metrics": ["accuracy", "f1"],
    },
    "ctibench": {
        "task": "ctibench",
        "type": "security",
        "description": "威胁情报推理评测",
        "metrics": ["accuracy"],
    },
    "seceval": {
        "task": "seceval",
        "type": "security",
        "description": "9大安全领域综合评测",
        "metrics": ["accuracy"],
    },
    "cybermetric": {
        "task": "cybermetric_80",
        "type": "security",
        "description": "安全知识选择题评测",
        "metrics": ["accuracy"],
    },
    "mmlu_compsec": {
        "task": "mmlu_computer_security",
        "type": "general",
        "description": "MMLU 计算机安全子集",
        "metrics": ["accuracy"],
    },
}


def get_task_name(benchmark_name: str) -> str:
    """获取 lm_eval 的 task 名称"""
    if benchmark_name in BENCHMARK_REGISTRY:
        return BENCHMARK_REGISTRY[benchmark_name]["task"]
    return benchmark_name


def list_benchmarks(benchmark_type: str = None) -> list:
    """列出所有注册的 benchmark"""
    if benchmark_type:
        return [name for name, info in BENCHMARK_REGISTRY.items()
                if info.get("type") == benchmark_type]
    return list(BENCHMARK_REGISTRY.keys())
```

- [ ] **步骤 2：编写评测调度器**

```python
# vulndetect/evaluation/scheduler.py
"""评测调度器——checkpoint 完成后自动触发评测"""
import os
import json
import time
from pathlib import Path
from typing import Dict, List, Callable, Optional
from datetime import datetime

from vulndetect.evaluation.harness import run_evaluation
from vulndetect.evaluation.benchmarks.registry import get_task_name


def evaluate_checkpoint(
    model_path: str,
    checkpoint_step: int,
    benchmarks: List[str],
    experiment_dir: str,
) -> Dict:
    """对单个 checkpoint 运行所有 benchmark"""
    output_dir = Path(experiment_dir) / "evaluations" / f"step-{checkpoint_step}"
    os.makedirs(output_dir, exist_ok=True)

    tasks = [get_task_name(b) for b in benchmarks]
    results = run_evaluation(str(model_path), tasks, str(output_dir))

    # 添加元信息
    results["_meta"] = {
        "checkpoint_step": checkpoint_step,
        "model_path": model_path,
        "timestamp": datetime.now().isoformat(),
        "benchmarks_run": benchmarks,
    }

    # 保存到 JSON
    with open(output_dir / "results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return results


def watch_and_evaluate(
    checkpoints_dir: str,
    experiment_dir: str,
    benchmarks: List[str],
    callback: Optional[Callable] = None,
    interval_seconds: int = 30,
):
    """监控 checkpoints 目录，新 checkpoint 出现时自动评测"""
    seen = set()
    while True:
        checkpoints_dir = Path(checkpoints_dir)
        if checkpoints_dir.exists():
            for d in sorted(checkpoints_dir.iterdir()):
                if d.is_dir() and d.name.startswith("checkpoint-"):
                    if d.name not in seen:
                        seen.add(d.name)
                        step = int(d.name.replace("checkpoint-", ""))
                        print(f"Evaluating {d.name}...")
                        results = evaluate_checkpoint(
                            str(d), step, benchmarks, experiment_dir
                        )
                        if callback:
                            callback(step, results)
        time.sleep(interval_seconds)
```

- [ ] **步骤 3：编写结果报告器**

```python
# vulndetect/evaluation/reporter.py
"""评测结果汇总与对比——生成实验报告"""
import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime


def compare_experiments(experiment_dirs: List[str]) -> Dict:
    """对比多个实验的评测结果"""
    comparison = {}
    for exp_dir in experiment_dirs:
        exp_path = Path(exp_dir)
        exp_name = exp_path.name
        comparison[exp_name] = {}

        eval_dir = exp_path / "evaluations"
        if not eval_dir.exists():
            continue

        # 找最新 checkpoint 的评测结果
        eval_dirs = sorted([d for d in eval_dir.iterdir() if d.is_dir()],
                          key=lambda x: x.name)
        if not eval_dirs:
            continue

        latest_eval = eval_dirs[-1] / "results.json"
        if latest_eval.exists():
            with open(latest_eval, "r") as f:
                results = json.load(f)
            for bench, scores in results.items():
                if bench != "_meta" and isinstance(scores, dict):
                    comparison[exp_name][bench] = scores.get("score", 0)

    return comparison


def generate_report(experiment_dir: str, format: str = "markdown") -> str:
    """生成实验评测报告"""
    exp_path = Path(experiment_dir)
    eval_dir = exp_path / "evaluations"

    if not eval_dir.exists():
        return "No evaluation results yet."

    lines = [f"# 评测报告：{exp_path.name}", f"生成时间：{datetime.now().isoformat()}", ""]

    for eval_subdir in sorted(eval_dir.iterdir()):
        if not eval_subdir.is_dir():
            continue
        results_file = eval_subdir / "results.json"
        if not results_file.exists():
            continue

        with open(results_file, "r") as f:
            results = json.load(f)

        step = results.get("_meta", {}).get("checkpoint_step", "unknown")
        lines.append(f"## Checkpoint {step}")
        lines.append("")
        lines.append("| Benchmark | Score |")
        lines.append("|-----------|-------|")
        for bench, scores in results.items():
            if bench == "_meta":
                continue
            score = scores.get("score", "N/A")
            lines.append(f"| {bench} | {score:.4f} |")
        lines.append("")

    return "\n".join(lines)
```

- [ ] **步骤 4：运行测试**

```python
# tests/evaluation/test_reporter.py
def test_generate_report():
    """测试报告生成"""
    import tempfile
    from pathlib import Path
    from vulndetect.evaluation.reporter import generate_report

    with tempfile.TemporaryDirectory() as tmpdir:
        eval_dir = Path(tmpdir) / "evaluations" / "step-200"
        eval_dir.mkdir(parents=True)
        import json
        with open(eval_dir / "results.json", "w") as f:
            json.dump({
                "_meta": {"checkpoint_step": 200},
                "vulnbench": {"score": 0.765},
                "seceval": {"score": 0.821},
            }, f)

        report = generate_report(tmpdir)
        assert "Checkpoint 200" in report
        assert "0.7650" in report
        print(report)
```

```bash
cd vulndetect && python -m pytest tests/evaluation/ -v
```

- [ ] **步骤 5：Commit**

```bash
git add vulndetect/evaluation/ && git commit -m "feat: add benchmark registry, scheduler, and reporter"
```


---

## 阶段 3：RL 管线（DPO + PPO）

### 任务 3.1：DPO 训练脚本

- 创建：`vulndetect/training/dpo.py`
- 创建：`vulndetect/config/train/dpo.yaml`

- [ ] **步骤 1：编写 DPO 配置**

```yaml
# vulndetect/config/train/dpo.yaml
training:
  strategy: "dpo"
  dpo:
    beta: 0.1
    reference_model: null
    loss_type: "sigmoid"
  max_seq_length: 2048
  max_prompt_length: 1024
  per_device_train_batch_size: 2
  gradient_accumulation_steps: 8
  learning_rate: 5.0e-5
  num_epochs: 1
  save_steps: 200
  eval_steps: 200
  logging_steps: 10
  warmup_ratio: 0.1
  lr_scheduler_type: "cosine"
  gradient_checkpointing: true
```

- [ ] **步骤 2：编写 DPO 训练脚本**

```python
# vulndetect/training/dpo.py
#!/usr/bin/env python3
"""DPO 训练入口——单卡 QLoRA"""
import argparse
import torch
from transformers import TrainingArguments
from trl import DPOTrainer
from peft import get_peft_model, prepare_model_for_kbit_training, PeftModel

from vulndetect.training.config_loader import load_experiment_config
from vulndetect.training.openrlhf_wrapper.models import build_qlora_config, load_model_and_tokenizer
from vulndetect.training.openrlhf_wrapper.datasets import load_conversation_dataset, format_for_dpo


def prepare_dpo_dataset(data_config, tokenizer):
    """准备 DPO 数据集——需要 chosen + rejected pairs"""
    import os
    from datasets import Dataset

    data_path = f"data/{data_config.get('dataset', {}).get('name', 'vulnbench')}/train_dpo.jsonl"
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"DPO data not found: {data_path}. DPO requires 'chosen' and 'rejected' fields.")

    raw_data = load_conversation_dataset(data_path)
    formatted = [format_for_dpo(item) for item in raw_data]

    return Dataset.from_list(formatted)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--sft_checkpoint", type=str, required=True,
                       help="Path to SFT checkpoint (LoRA adapter)")
    args = parser.parse_args()

    config = load_experiment_config(args.config)
    print(f"DPO Training: {config['experiment']['name']}")

    # 加载 SFT 后的模型
    model_config = config
    model, tokenizer = load_model_and_tokenizer(model_config)
    model = prepare_model_for_kbit_training(model)
    _, lora_config = build_qlora_config(model_config)
    model = get_peft_model(model, lora_config)

    # 从 SFT checkpoint 加载 adapter（reference model 也加载同样的）
    sft_model = PeftModel.from_pretrained(model, args.sft_checkpoint, is_trainable=True)

    # DPO reference model（冻结）
    ref_model = PeftModel.from_pretrained(model, args.sft_checkpoint)
    for param in ref_model.parameters():
        param.requires_grad = False

    # 准备数据
    dataset = prepare_dpo_dataset(config.get("data", {}), tokenizer)

    train_cfg = config.get("training", {}).get("dpo", {})

    training_args = TrainingArguments(
        output_dir=f"experiments/{config['experiment']['name']}/checkpoints",
        per_device_train_batch_size=train_cfg.get("per_device_train_batch_size", 2),
        gradient_accumulation_steps=train_cfg.get("gradient_accumulation_steps", 8),
        learning_rate=train_cfg.get("learning_rate", 5e-5),
        num_train_epochs=train_cfg.get("num_epochs", 1),
        logging_steps=10,
        save_steps=200,
        bf16=True,
        gradient_checkpointing=True,
        remove_unused_columns=False,
        report_to=["tensorboard"],
    )

    dpo_trainer = DPOTrainer(
        model=sft_model,
        ref_model=ref_model,
        args=training_args,
        train_dataset=dataset,
        tokenizer=tokenizer,
        beta=train_cfg.get("beta", 0.1),
        loss_type=train_cfg.get("loss_type", "sigmoid"),
        max_length=train_cfg.get("max_seq_length", 2048),
        max_prompt_length=train_cfg.get("max_prompt_length", 1024),
    )

    dpo_trainer.train()
    print("DPO Training complete!")


if __name__ == "__main__":
    main()
```

- [ ] **步骤 3：Commit**

```bash
git add vulndetect/training/dpo.py vulndetect/config/train/dpo.yaml && git commit -m "feat: add DPO training script"
```

### 任务 3.2：PPO 训练脚本（单卡简化版）

- 创建：`vulndetect/training/ppo.py`
- 创建：`vulndetect/config/train/ppo.yaml`

- [ ] **步骤 1：编写 PPO 配置**

```yaml
# vulndetect/config/train/ppo.yaml
training:
  strategy: "ppo"
  ppo:
    num_episodes: 100
    ppo_epochs: 4
    batch_size: 64
    mini_batch_size: 8
    kl_coef: 0.1
    clip_range: 0.2
    value_clip_range: 0.2
    gamma: 1.0
    lam: 0.95
    max_new_tokens: 256
    temperature: 0.7
  per_device_train_batch_size: 1
  gradient_accumulation_steps: 16
  learning_rate: 1.0e-5
  max_seq_length: 2048
  logging_steps: 10
  gradient_checkpointing: true
```

- [ ] **步骤 2：编写 PPO 训练脚本**

```python
# vulndetect/training/ppo.py
#!/usr/bin/env python3
"""PPO 训练入口——单卡简化版，QLoRA actor + critic"""
import argparse
import torch
from transformers import TrainingArguments, AutoTokenizer
from trl import PPOTrainer, PPOConfig, AutoModelForCausalLMWithValueHead
from peft import get_peft_model, prepare_model_for_kbit_training

from vulndetect.training.config_loader import load_experiment_config
from vulndetect.training.openrlhf_wrapper.models import build_qlora_config, load_model_and_tokenizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--sft_checkpoint", type=str, required=True)
    args = parser.parse_args()

    config = load_experiment_config(args.config)
    print(f"PPO Training: {config['experiment']['name']}")

    # 加载 SFT 模型（作为 PPO 的初始 policy）
    model, tokenizer = load_model_and_tokenizer(config)
    model = prepare_model_for_kbit_training(model)

    # PPO 使用 TRL 的 AutoModelForCausalLMWithValueHead
    # 简化版：在单卡上跑，使用小 batch + gradient checkpointing
    ppo_cfg = config.get("training", {}).get("ppo", {})

    ppo_config = PPOConfig(
        model_name=config["experiment"]["name"],
        learning_rate=config["training"].get("learning_rate", 1e-5),
        ppo_epochs=ppo_cfg.get("ppo_epochs", 4),
        batch_size=ppo_cfg.get("batch_size", 64),
        mini_batch_size=ppo_cfg.get("mini_batch_size", 8),
        gradient_accumulation_steps=config["training"].get("gradient_accumulation_steps", 16),
    )

    # 创建 reward model（简化：使用规则或小模型打分）
    # 实际使用时需要替换为真正的 reward model

    print("PPO training requires a reward model.")
    print("For Qwen-3B on A6000, use a simple rule-based reward or a small classifier.")
    print("PPO framework ready. Implement reward model before actual training.")


if __name__ == "__main__":
    main()
```

- [ ] **步骤 3：Commit**

```bash
git add vulndetect/training/ppo.py vulndetect/config/train/ppo.yaml && git commit -m "feat: add PPO training script skeleton"
```

---

## 阶段 4：Web 后端（FastAPI）

### 任务 4.1：数据库模型和 FastAPI 骨架

- 创建：`vulndetect/backend/__init__.py`
- 创建：`vulndetect/backend/database.py`
- 创建：`vulndetect/backend/models/schema.py`
- 创建：`vulndetect/backend/main.py`

- [ ] **步骤 1：编写数据库连接**

```python
# vulndetect/backend/__init__.py
"""VulnDetect Backend——FastAPI + SQLite"""
```

```python
# vulndetect/backend/database.py
"""SQLite 数据库连接管理"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///vulndetect.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """获取数据库 session（FastAPI 依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库表"""
    Base.metadata.create_all(bind=engine)
```

- [ ] **步骤 2：编写数据模型**

```python
# vulndetect/backend/models/schema.py
"""SQLAlchemy ORM 模型"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from vulndetect.backend.database import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, default="")
    config_yaml = Column(Text, default="")
    status = Column(String(50), default="created")  # created|running|paused|completed|failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    checkpoints = relationship("Checkpoint", back_populates="experiment")
    metrics = relationship("TrainingMetric", back_populates="experiment")
    evaluations = relationship("Evaluation", back_populates="experiment")


class Checkpoint(Base):
    __tablename__ = "checkpoints"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"))
    step = Column(Integer, nullable=False)
    path = Column(String(512), nullable=False)
    loss = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    experiment = relationship("Experiment", back_populates="checkpoints")
    evaluations = relationship("Evaluation", back_populates="checkpoint")


class TrainingMetric(Base):
    __tablename__ = "training_metrics"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"))
    step = Column(Integer, nullable=False)
    loss = Column(Float, nullable=True)
    learning_rate = Column(Float, nullable=True)
    gpu_memory_mb = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    experiment = relationship("Experiment", back_populates="metrics")


class Evaluation(Base):
    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"))
    checkpoint_id = Column(Integer, ForeignKey("checkpoints.id"))
    benchmark_name = Column(String(255), nullable=False)
    score = Column(Float, nullable=False)
    details_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)

    experiment = relationship("Experiment", back_populates="evaluations")
    checkpoint = relationship("Checkpoint", back_populates="evaluations")


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    source = Column(String(512), default="")
    num_samples = Column(Integer, default=0)
    status = Column(String(50), default="pending")
    last_collected_at = Column(DateTime, nullable=True)
```

- [ ] **步骤 3：编写 FastAPI 主入口**

```python
# vulndetect/backend/main.py
"""FastAPI 应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from vulndetect.backend.database import init_db

app = FastAPI(title="VulnDetect API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "vulndetect"}
```

- [ ] **步骤 4：Commit**

```bash
git add vulndetect/backend/ && git commit -m "feat: add FastAPI skeleton with SQLite models"
```

### 任务 4.2：API 端点实现

- 创建：`vulndetect/backend/api/__init__.py`
- 创建：`vulndetect/backend/api/experiments.py`
- 创建：`vulndetect/backend/api/training.py`
- 创建：`vulndetect/backend/api/evaluation.py`
- 创建：`vulndetect/backend/api/inference.py`
- 创建：`vulndetect/backend/services/experiment_service.py`

- [ ] **步骤 1：编写 Experiment Service**

```python
# vulndetect/backend/services/experiment_service.py
"""实验管理业务逻辑"""
import yaml
from pathlib import Path
from typing import List, Optional
from sqlalchemy.orm import Session
from vulndetect.backend.models.schema import Experiment, Checkpoint, TrainingMetric, Evaluation


def create_experiment(db: Session, name: str, description: str, config_yaml: str) -> Experiment:
    exp = Experiment(name=name, description=description, config_yaml=config_yaml)
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


def list_experiments(db: Session, limit: int = 20) -> List[Experiment]:
    return db.query(Experiment).order_by(Experiment.created_at.desc()).limit(limit).all()


def get_experiment(db: Session, experiment_id: int) -> Optional[Experiment]:
    return db.query(Experiment).filter(Experiment.id == experiment_id).first()


def update_experiment_status(db: Session, experiment_id: int, status: str) -> Optional[Experiment]:
    exp = get_experiment(db, experiment_id)
    if exp:
        exp.status = status
        db.commit()
        db.refresh(exp)
    return exp


def get_experiment_metrics(db: Session, experiment_id: int, limit: int = 1000) -> List[TrainingMetric]:
    return (
        db.query(TrainingMetric)
        .filter(TrainingMetric.experiment_id == experiment_id)
        .order_by(TrainingMetric.step.asc())
        .limit(limit)
        .all()
    )


def get_experiment_evaluations(db: Session, experiment_id: int) -> List[Evaluation]:
    return (
        db.query(Evaluation)
        .filter(Evaluation.experiment_id == experiment_id)
        .order_by(Evaluation.created_at.desc())
        .all()
    )
```

- [ ] **步骤 2：编写 REST API 路由**

```python
# vulndetect/backend/api/__init__.py
"""API 路由模块"""
```

```python
# vulndetect/backend/api/experiments.py
"""实验管理 API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from vulndetect.backend.database import get_db
from vulndetect.backend.services import experiment_service

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


class ExperimentCreate(BaseModel):
    name: str
    description: str = ""
    config_yaml: str = ""


class ExperimentResponse(BaseModel):
    id: int
    name: str
    description: str
    status: str
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[ExperimentResponse])
def list_experiments(db: Session = Depends(get_db)):
    return experiment_service.list_experiments(db)


@router.post("", response_model=ExperimentResponse)
def create_experiment(req: ExperimentCreate, db: Session = Depends(get_db)):
    return experiment_service.create_experiment(db, req.name, req.description, req.config_yaml)


@router.get("/{experiment_id}", response_model=ExperimentResponse)
def get_experiment(experiment_id: int, db: Session = Depends(get_db)):
    exp = experiment_service.get_experiment(db, experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp


@router.post("/{experiment_id}/start")
def start_experiment(experiment_id: int, db: Session = Depends(get_db)):
    exp = experiment_service.update_experiment_status(db, experiment_id, "running")
    if not exp:
        raise HTTPException(status_code=404)
    # 触发训练（实际实现中启动子进程）
    return {"status": "started", "experiment_id": experiment_id}


@router.post("/{experiment_id}/pause")
def pause_experiment(experiment_id: int, db: Session = Depends(get_db)):
    exp = experiment_service.update_experiment_status(db, experiment_id, "paused")
    if not exp:
        raise HTTPException(status_code=404)
    return {"status": "paused", "experiment_id": experiment_id}


@router.get("/{experiment_id}/metrics")
def get_metrics(experiment_id: int, db: Session = Depends(get_db)):
    metrics = experiment_service.get_experiment_metrics(db, experiment_id)
    return [
        {"step": m.step, "loss": m.loss, "learning_rate": m.learning_rate,
         "gpu_memory_mb": m.gpu_memory_mb, "timestamp": str(m.timestamp)}
        for m in metrics
    ]


@router.get("/{experiment_id}/evaluations")
def get_evaluations(experiment_id: int, db: Session = Depends(get_db)):
    evals = experiment_service.get_experiment_evaluations(db, experiment_id)
    return [
        {"benchmark": e.benchmark_name, "score": e.score,
         "checkpoint_step": e.checkpoint_id, "details": e.details_json}
        for e in evals
    ]
```

```python
# vulndetect/backend/api/training.py
"""训练状态 WebSocket + API"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json

router = APIRouter(prefix="/ws", tags=["training"])

active_connections: dict = {}


@router.websocket("/experiments/{experiment_id}/training")
async def training_websocket(websocket: WebSocket, experiment_id: int):
    await websocket.accept()
    active_connections[experiment_id] = websocket
    try:
        while True:
            # 保持连接，等待推送
            data = await websocket.receive_text()
            # 客户端可以发送命令（如 ping）
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        active_connections.pop(experiment_id, None)


async def push_training_update(experiment_id: int, data: dict):
    """推送训练更新到 WebSocket 客户端"""
    if experiment_id in active_connections:
        try:
            await active_connections[experiment_id].send_text(json.dumps(data))
        except Exception:
            active_connections.pop(experiment_id, None)
```

```python
# vulndetect/backend/api/inference.py
"""模型推理 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/api/inference", tags=["inference"])


class ChatRequest(BaseModel):
    checkpoint_path: str
    prompt: str
    max_new_tokens: int = 512
    temperature: float = 0.7


class ChatResponse(BaseModel):
    text: str
    checkpoint: str


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """模型对话——加载指定 checkpoint 推理"""
    # 实际实现中加载模型并推理
    try:
        # Placeholder: 接入实际的推理逻辑
        return ChatResponse(
            text=f"[Inference from {req.checkpoint_path}] Response to: {req.prompt[:100]}...",
            checkpoint=req.checkpoint_path,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checkpoints")
def list_checkpoints(experiment_id: Optional[int] = None):
    """列出可用 checkpoint"""
    from pathlib import Path
    checkpoints = []
    exp_dir = Path("experiments")
    if exp_dir.exists():
        for exp in exp_dir.iterdir():
            if exp.is_dir():
                ckpt_dir = exp / "checkpoints"
                if ckpt_dir.exists():
                    for ckpt in sorted(ckpt_dir.iterdir()):
                        if ckpt.is_dir() and ckpt.name.startswith("checkpoint-"):
                            checkpoints.append({
                                "experiment": exp.name,
                                "step": ckpt.name.replace("checkpoint-", ""),
                                "path": str(ckpt),
                            })
    return checkpoints
```

- [ ] **步骤 3：注册路由到 main.py**

在 `vulndetect/backend/main.py` 中添加路由注册：

```python
from vulndetect.backend.api import experiments, training, inference, evaluation

app.include_router(experiments.router)
app.include_router(training.router)
app.include_router(inference.router)
```

- [ ] **步骤 4：启动 FastAPI 测试**

```bash
cd vulndetect && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
sleep 2
curl http://localhost:8000/api/health
# 预期：{"status":"ok","service":"vulndetect"}
curl http://localhost:8000/api/experiments
# 预期：[]
```

- [ ] **步骤 5：Commit**

```bash
git add vulndetect/backend/ && git commit -m "feat: add REST API endpoints and WebSocket"
```


---

## 阶段 5：Web 前端（React + TypeScript）

### 任务 5.1：Vite + React 脚手架 + shadcn/ui

- 创建：`vulndetect/frontend/` 下所有前端文件

- [ ] **步骤 1：初始化 Vite + React + TypeScript 项目**

```bash
cd vulndetect/frontend
npm create vite@latest . -- --template react-ts
npm install
```

- [ ] **步骤 2：安装 shadcn/ui + Tailwind + 依赖**

```bash
cd vulndetect/frontend
npm install tailwindcss @tailwindcss/vite
npm install recharts lucide-react
npm install @tanstack/react-query
npx shadcn@latest init
# 选择：TypeScript, Tailwind CSS v4, Neutral, CSS variables
npx shadcn@latest add button card tabs select separator badge table
```

- [ ] **步骤 3：编写 Tailwind 暗色主题配置**

```css
/* vulndetect/frontend/src/index.css */
@import "tailwindcss";

:root {
  --background: #0d1117;
  --foreground: #e6edf3;
  --card: #161b22;
  --card-foreground: #e6edf3;
  --border: #30363d;
  --primary: #58a6ff;
  --primary-foreground: #ffffff;
  --success: #3fb950;
  --success-foreground: #ffffff;
  --danger: #f85149;
  --danger-foreground: #ffffff;
  --warning: #d2991d;
  --muted: #8b949e;
  --muted-foreground: #8b949e;
  --accent: #1f2937;
  --accent-foreground: #e6edf3;
  --radius: 0.5rem;
  --font-sans: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}

body {
  background: var(--background);
  color: var(--foreground);
  font-family: var(--font-sans);
}
```

- [ ] **步骤 4：编写 API client**

```typescript
// vulndetect/frontend/src/lib/api.ts
const BASE_URL = "http://localhost:8000";

export interface Experiment {
  id: number;
  name: string;
  description: string;
  status: string;
  created_at: string;
}

export interface TrainingMetrics {
  step: number;
  loss: number | null;
  learning_rate: number | null;
  gpu_memory_mb: number | null;
  timestamp: string;
}

export interface EvaluationResult {
  benchmark: string;
  score: number;
  checkpoint_step: number;
  details: Record<string, unknown>;
}

export async function fetchExperiments(): Promise<Experiment[]> {
  const res = await fetch(`${BASE_URL}/api/experiments`);
  if (!res.ok) throw new Error("Failed to fetch experiments");
  return res.json();
}

export async function fetchExperiment(id: number): Promise<Experiment> {
  const res = await fetch(`${BASE_URL}/api/experiments/${id}`);
  if (!res.ok) throw new Error("Experiment not found");
  return res.json();
}

export async function fetchMetrics(id: number): Promise<TrainingMetrics[]> {
  const res = await fetch(`${BASE_URL}/api/experiments/${id}/metrics`);
  if (!res.ok) throw new Error("Failed to fetch metrics");
  return res.json();
}

export async function fetchEvaluations(id: number): Promise<EvaluationResult[]> {
  const res = await fetch(`${BASE_URL}/api/experiments/${id}/evaluations`);
  if (!res.ok) throw new Error("Failed to fetch evaluations");
  return res.json();
}

export async function createExperiment(data: {
  name: string;
  description: string;
  config_yaml: string;
}): Promise<Experiment> {
  const res = await fetch(`${BASE_URL}/api/experiments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Failed to create experiment");
  return res.json();
}

export async function startExperiment(id: number): Promise<void> {
  await fetch(`${BASE_URL}/api/experiments/${id}/start`, { method: "POST" });
}

export async function chatInference(
  checkpointPath: string,
  prompt: string
): Promise<string> {
  const res = await fetch(`${BASE_URL}/api/inference/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ checkpoint_path: checkpointPath, prompt }),
  });
  if (!res.ok) throw new Error("Inference failed");
  const data = await res.json();
  return data.text;
}
```

- [ ] **步骤 5：编写 Dashboard Layout**

```tsx
// vulndetect/frontend/src/layouts/DashboardLayout.tsx
import { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

const NAV_ITEMS = [
  { path: "/", label: "Dashboard", icon: "◉" },
  { path: "/training", label: "Training", icon: "⚡" },
  { path: "/evaluation", label: "Evaluation", icon: "📊" },
  { path: "/data", label: "Data", icon: "📦" },
  { path: "/playground", label: "Playground", icon: "💬" },
];

export function DashboardLayout({ children }: { children: ReactNode }) {
  const location = useLocation();

  return (
    <div className="flex h-screen bg-[#0d1117] text-[#e6edf3]">
      {/* Sidebar */}
      <aside className="w-56 border-r border-[#30363d] bg-[#161b22] p-4">
        <div className="mb-6 text-lg font-bold tracking-tight text-[#58a6ff]">
          VulnDetect
        </div>
        <nav className="space-y-1">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors ${
                location.pathname === item.path
                  ? "bg-[#1f2937] text-[#58a6ff]"
                  : "text-[#8b949e] hover:bg-[#1f2937] hover:text-[#e6edf3]"
              }`}
            >
              <span>{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-6">{children}</main>
    </div>
  );
}
```

- [ ] **步骤 6：编写 App 入口**

```tsx
// vulndetect/frontend/src/App.tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DashboardLayout } from "./layouts/DashboardLayout";
import { Dashboard } from "./pages/Dashboard";
import { TrainingMonitor } from "./pages/TrainingMonitor";
import { EvalReport } from "./pages/EvalReport";
import { DataManager } from "./pages/DataManager";
import { Playground } from "./pages/Playground";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <DashboardLayout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/training" element={<TrainingMonitor />} />
            <Route path="/evaluation" element={<EvalReport />} />
            <Route path="/data" element={<DataManager />} />
            <Route path="/playground" element={<Playground />} />
          </Routes>
        </DashboardLayout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

- [ ] **步骤 7：编写 Dashboard 页面**

```tsx
// vulndetect/frontend/src/pages/Dashboard.tsx
import { useQuery } from "@tanstack/react-query";
import { fetchExperiments, Experiment } from "../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    running: "bg-[#3fb950]",
    paused: "bg-[#d2991d]",
    completed: "bg-[#58a6ff]",
    failed: "bg-[#f85149]",
    created: "bg-[#8b949e]",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs text-white ${colors[status] || colors.created}`}>
      {status}
    </span>
  );
}

function ExperimentCard({ exp }: { exp: Experiment }) {
  return (
    <Card className="border-[#30363d] bg-[#161b22]">
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-sm">
          {exp.name}
          <StatusBadge status={exp.status} />
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-xs text-[#8b949e]">{exp.description}</p>
        <p className="mt-2 text-xs text-[#8b949e]">
          Created: {new Date(exp.created_at).toLocaleDateString()}
        </p>
      </CardContent>
    </Card>
  );
}

export function Dashboard() {
  const { data: experiments, isLoading } = useQuery({
    queryKey: ["experiments"],
    queryFn: fetchExperiments,
    refetchInterval: 5000,
  });

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Dashboard</h1>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Quick Stats */}
        <Card className="border-[#30363d] bg-[#161b22]">
          <CardContent className="pt-6">
            <div className="text-3xl font-bold text-[#58a6ff]">
              {experiments?.length ?? 0}
            </div>
            <div className="text-sm text-[#8b949e]">Total Experiments</div>
          </CardContent>
        </Card>
        <Card className="border-[#30363d] bg-[#161b22]">
          <CardContent className="pt-6">
            <div className="text-3xl font-bold text-[#3fb950]">
              {experiments?.filter((e) => e.status === "running").length ?? 0}
            </div>
            <div className="text-sm text-[#8b949e]">Running</div>
          </CardContent>
        </Card>
        <Card className="border-[#30363d] bg-[#161b22]">
          <CardContent className="pt-6">
            <div className="text-3xl font-bold text-[#a371f7]">
              {experiments?.filter((e) => e.status === "completed").length ?? 0}
            </div>
            <div className="text-sm text-[#8b949e]">Completed</div>
          </CardContent>
        </Card>
      </div>

      <h2 className="mb-4 mt-8 text-lg font-semibold">Recent Experiments</h2>
      {isLoading ? (
        <p className="text-[#8b949e]">Loading...</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {experiments?.map((exp) => (
            <ExperimentCard key={exp.id} exp={exp} />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **步骤 8：编写 TrainingMonitor 页面**

```tsx
// vulndetect/frontend/src/pages/TrainingMonitor.tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { fetchExperiments, fetchMetrics } from "../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function TrainingMonitor() {
  const { data: experiments } = useQuery({ queryKey: ["experiments"], queryFn: fetchExperiments });
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const { data: metrics } = useQuery({
    queryKey: ["metrics", selectedId],
    queryFn: () => (selectedId ? fetchMetrics(selectedId) : Promise.resolve([])),
    enabled: !!selectedId,
    refetchInterval: 3000,
  });

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Training Monitor</h1>

      <div className="mb-4 flex gap-2">
        {experiments?.map((exp) => (
          <button
            key={exp.id}
            onClick={() => setSelectedId(exp.id)}
            className={`rounded-md px-3 py-1.5 text-sm ${
              selectedId === exp.id
                ? "bg-[#58a6ff] text-white"
                : "bg-[#161b22] text-[#8b949e] hover:text-[#e6edf3]"
            }`}
          >
            {exp.name}
          </button>
        ))}
      </div>

      {metrics && metrics.length > 0 && (
        <Card className="border-[#30363d] bg-[#161b22]">
          <CardHeader>
            <CardTitle className="text-sm">Loss Curve</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={metrics}>
                <CartesianGrid strokeDasharray="3 3" stroke="#30363d" />
                <XAxis dataKey="step" stroke="#8b949e" />
                <YAxis stroke="#8b949e" />
                <Tooltip
                  contentStyle={{ background: "#161b22", border: "1px solid #30363d" }}
                />
                <Line
                  type="monotone"
                  dataKey="loss"
                  stroke="#58a6ff"
                  dot={false}
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

- [ ] **步骤 9：编写 Playground 页面**

```tsx
// vulndetect/frontend/src/pages/Playground.tsx
import { useState } from "react";
import { chatInference } from "../lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function Playground() {
  const [input, setInput] = useState("");
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);
  const [checkpoint, setCheckpoint] = useState("experiments/qwen3b-sft-v1/checkpoints/final");

  const handleSend = async () => {
    if (!input.trim()) return;
    setLoading(true);
    try {
      const result = await chatInference(checkpoint, input);
      setResponse(result);
    } catch (e) {
      setResponse(`Error: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold">Model Playground</h1>

      <div className="mb-4">
        <label className="mb-1 block text-xs text-[#8b949e]">Checkpoint</label>
        <input
          value={checkpoint}
          onChange={(e) => setCheckpoint(e.target.value)}
          className="w-full rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 text-sm text-[#e6edf3] font-mono"
          placeholder="Path to checkpoint..."
        />
      </div>

      <Card className="mb-4 border-[#30363d] bg-[#161b22]">
        <CardHeader>
          <CardTitle className="text-sm">Input</CardTitle>
        </CardHeader>
        <CardContent>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            className="h-48 w-full resize-none rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-2 font-mono text-sm text-[#e6edf3]"
            placeholder="Paste code or ask a security question..."
          />
          <button
            onClick={handleSend}
            disabled={loading}
            className="mt-3 rounded-md bg-[#238636] px-4 py-2 text-sm font-medium text-white hover:bg-[#2ea043] disabled:opacity-50"
          >
            {loading ? "Analyzing..." : "Send"}
          </button>
        </CardContent>
      </Card>

      {response && (
        <Card className="border-[#30363d] bg-[#161b22]">
          <CardHeader>
            <CardTitle className="text-sm">Response</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap font-mono text-sm text-[#e6edf3]">
              {response}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

- [ ] **步骤 10：Commit**

```bash
cd vulndetect/frontend && git add -A && git commit -m "feat: add React frontend with Dashboard, Training, Playground pages"
```

---

## 阶段 6：数据采集管线

### 任务 6.1：NVD + GitHub Advisory 采集器

- 创建：`vulndetect/data_pipeline/__init__.py`
- 创建：`vulndetect/data_pipeline/collectors/__init__.py`
- 创建：`vulndetect/data_pipeline/collectors/nvd.py`
- 创建：`vulndetect/data_pipeline/collectors/github_advisory.py`
- 创建：`vulndetect/data_pipeline/cleaners/dedup.py`
- 创建：`vulndetect/data_pipeline/cleaners/normalizer.py`
- 创建：`vulndetect/data_pipeline/formatters/openrlhf_format.py`
- 创建：`vulndetect/data_pipeline/pipeline.py`
- 创建：`vulndetect/tests/data_pipeline/test_collectors.py`

- [ ] **步骤 1：编写测试**

```python
# vulndetect/tests/data_pipeline/test_collectors.py
import pytest
import json
from unittest.mock import patch, MagicMock


def test_nvd_collector_build_query():
    """测试 NVD API 查询构建"""
    from vulndetect.data_pipeline.collectors.nvd import build_query

    query = build_query(days_back=7, severity="HIGH")
    assert "pubStartDate" in query or "cvssV3Severity" in query


def test_github_advisory_parse():
    """测试 GitHub Advisory 数据解析"""
    from vulndetect.data_pipeline.collectors.github_advisory import parse_advisory

    sample = {
        "id": "GHSA-xxxx-yyyy-zzzz",
        "summary": "Command injection in example package",
        "description": "A command injection vulnerability exists...",
        "severity": "HIGH",
        "cwes": [{"cwe_id": "CWE-77"}],
        "identifiers": [{"type": "CVE", "value": "CVE-2024-1234"}],
    }

    result = parse_advisory(sample)
    assert result["source"] == "github_advisory"
    assert result["cve_id"] == "CVE-2024-1234"
    assert result["severity"] == "HIGH"
    assert "CWE-77" in result["cwes"]


def test_dedup_removes_duplicates():
    """测试去重逻辑"""
    from vulndetect.data_pipeline.cleaners.dedup import deduplicate

    items = [
        {"cve_id": "CVE-2024-0001", "description": "First vuln"},
        {"cve_id": "CVE-2024-0001", "description": "Duplicate vuln"},
        {"cve_id": "CVE-2024-0002", "description": "Second vuln"},
    ]

    result = deduplicate(items, key="cve_id")
    assert len(result) == 2
    assert result[0]["description"] == "First vuln"  # keeps first occurrence


def test_formatter_openrlhf():
    """测试转换为 OpenRLHF conversation 格式"""
    from vulndetect.data_pipeline.formatters.openrlhf_format import format_vuln_to_conversation

    vuln = {
        "cve_id": "CVE-2024-1234",
        "description": "Command injection in function X",
        "severity": "CRITICAL",
        "code_snippet": 'os.system(user_input)',
        "fix": "Use subprocess.run with shell=False",
    }

    conversation = format_vuln_to_conversation(vuln)
    assert "conversations" in conversation
    assert len(conversation["conversations"]) >= 2
    assert conversation["conversations"][0]["from"] == "human"
    assert conversation["conversations"][1]["from"] == "gpt"
    assert "Command injection" in conversation["conversations"][0]["value"]
    assert "subprocess.run" in conversation["conversations"][1]["value"]
```

- [ ] **步骤 2：编写 NVD 采集器**

```python
# vulndetect/data_pipeline/collectors/nvd.py
"""NVD (National Vulnerability Database) 采集器"""
import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Generator


NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"


def build_query(days_back: int = 7, severity: str = None) -> Dict:
    """构建 NVD API 查询参数"""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)

    params = {
        "pubStartDate": start_date.strftime("%Y-%m-%dT%H:%M:%S.000"),
        "pubEndDate": end_date.strftime("%Y-%m-%dT%H:%M:%S.000"),
        "resultsPerPage": 100,
    }

    if severity:
        params["cvssV3Severity"] = severity.upper()

    return params


def fetch_cves(days_back: int = 7, severity: str = None) -> List[Dict]:
    """从 NVD API 批量拉取 CVE 数据"""
    all_cves = []
    params = build_query(days_back, severity)
    start_index = 0

    while True:
        params["startIndex"] = start_index
        resp = requests.get(NVD_API_BASE, params=params, timeout=30)

        if resp.status_code == 200:
            data = resp.json()
            vulnerabilities = data.get("vulnerabilities", [])
            all_cves.extend(vulnerabilities)

            total_results = data.get("totalResults", 0)
            if start_index + len(vulnerabilities) >= total_results:
                break
            start_index += len(vulnerabilities)
        else:
            print(f"NVD API error: {resp.status_code}")
            break

        time.sleep(0.6)  # NVD API rate limit (no API key: ~5 req/30s)

    return all_cves


def parse_cve(cve_item: Dict) -> Dict:
    """解析单个 CVE 条目为统一格式"""
    cve = cve_item.get("cve", {})

    # 提取 CVSS 评分
    cvss_score = None
    cvss_severity = None
    metrics = cve.get("metrics", {})
    for version in ["cvssMetricV31", "cvssMetricV30"]:
        if version in metrics and metrics[version]:
            cvss_data = metrics[version][0].get("cvssData", {})
            cvss_score = cvss_data.get("baseScore")
            cvss_severity = cvss_data.get("baseSeverity")
            break

    # 提取 CWE
    cwes = []
    for weakness in cve.get("weaknesses", []):
        for desc in weakness.get("description", []):
            if desc.get("value", "").startswith("CWE-"):
                cwes.append(desc["value"])

    # 提取描述
    descriptions = cve.get("descriptions", [])
    en_desc = next((d["value"] for d in descriptions if d["lang"] == "en"), "")

    return {
        "cve_id": cve.get("id", ""),
        "source": "nvd",
        "description": en_desc,
        "severity": cvss_severity or "UNKNOWN",
        "cvss_score": cvss_score,
        "cwes": cwes,
        "published_date": cve.get("published", ""),
        "last_modified": cve.get("lastModified", ""),
        "references": [ref.get("url") for ref in cve.get("references", [])],
    }
```

- [ ] **步骤 3：编写 GitHub Advisory 采集器**

```python
# vulndetect/data_pipeline/collectors/github_advisory.py
"""GitHub Advisory Database 采集器"""
import requests
from typing import List, Dict


GHSA_API = "https://api.github.com/advisories"


def fetch_advisories(severity: str = None, per_page: int = 100, max_pages: int = 5) -> List[Dict]:
    """从 GitHub Advisory API 拉取安全公告"""
    all_advisories = []
    page = 1

    while page <= max_pages:
        params = {
            "per_page": per_page,
            "page": page,
            "type": "reviewed",
        }
        if severity:
            params["severity"] = severity.lower()

        resp = requests.get(
            GHSA_API,
            params=params,
            headers={"Accept": "application/vnd.github+json"},
            timeout=30,
        )

        if resp.status_code == 200:
            advisories = resp.json()
            if not advisories:
                break
            all_advisories.extend(advisories)
            page += 1
        else:
            print(f"GitHub API error: {resp.status_code}")
            break

    return [parse_advisory(a) for a in all_advisories]


def parse_advisory(advisory: Dict) -> Dict:
    """解析 GitHub Advisory 为统一格式"""
    cve_id = ""
    for ident in advisory.get("identifiers", []):
        if ident.get("type") == "CVE":
            cve_id = ident.get("value", "")
            break

    return {
        "cve_id": cve_id or advisory.get("ghsa_id", ""),
        "source": "github_advisory",
        "description": advisory.get("description", ""),
        "summary": advisory.get("summary", ""),
        "severity": (advisory.get("severity") or "UNKNOWN").upper(),
        "cwes": [c.get("cwe_id") for c in advisory.get("cwes", []) if c.get("cwe_id")],
        "published_date": advisory.get("published_at", ""),
        "references": [r.get("url") for r in advisory.get("references", [])],
        "permalink": advisory.get("html_url", ""),
    }
```

- [ ] **步骤 4：编写数据清洗器**

```python
# vulndetect/data_pipeline/cleaners/dedup.py
"""数据去重"""

def deduplicate(items: list, key: str = "cve_id") -> list:
    """按指定 key 去重，保留第一次出现的条目"""
    seen = set()
    result = []
    for item in items:
        item_key = item.get(key, "")
        if item_key and item_key not in seen:
            seen.add(item_key)
            result.append(item)
    return result


def filter_by_severity(items: list, min_severity: str = "MEDIUM") -> list:
    """按严重程度过滤"""
    severity_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}
    min_level = severity_order.get(min_severity.upper(), 0)
    return [
        item for item in items
        if severity_order.get(item.get("severity", "UNKNOWN").upper(), 0) >= min_level
    ]
```

```python
# vulndetect/data_pipeline/cleaners/normalizer.py
"""文本标准化——去除 HTML 标签、统一空白字符"""
import re


def normalize_text(text: str) -> str:
    """标准化文本：去除 HTML、统一空白、trim"""
    if not text:
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    # Trim
    return text.strip()


def normalize_vuln_item(item: dict) -> dict:
    """标准化单条漏洞数据的文本字段"""
    text_fields = ["description", "summary"]
    for field in text_fields:
        if field in item:
            item[field] = normalize_text(item[field])
    return item
```

- [ ] **步骤 5：编写 OpenRLHF 格式转换器**

```python
# vulndetect/data_pipeline/formatters/openrlhf_format.py
"""将漏洞数据转换为 OpenRLHF conversation 格式"""
from typing import Dict, List


def format_vuln_to_conversation(vuln: Dict) -> Dict:
    """将单条漏洞数据转换为 conversation 格式（SFT 用）"""
    cve_id = vuln.get("cve_id", "Unknown")
    description = vuln.get("description", "")
    severity = vuln.get("severity", "UNKNOWN")
    code_snippet = vuln.get("code_snippet", "")
    fix = vuln.get("fix", "")

    human_prompt = f"Analyze the following code for vulnerabilities:\n```\n{code_snippet}\n```" if code_snippet else \
        f"What is {cve_id}? Describe the vulnerability and potential impact."

    gpt_response = f"CVE ID: {cve_id}\nSeverity: {severity}\n\n{description}"

    if fix:
        gpt_response += f"\n\nRecommended Fix:\n{fix}"

    return {
        "conversations": [
            {"from": "human", "value": human_prompt},
            {"from": "gpt", "value": gpt_response},
        ]
    }


def format_vuln_to_dpo(item: Dict) -> Dict:
    """将漏洞数据转换为 DPO 格式（需要 chosen + rejected）"""
    # chosen = 正确的漏洞分析
    # rejected = 错误的或泛泛的分析
    return {
        "conversations": [
            {"from": "human", "value": f"Analyze {item.get('cve_id', 'this vulnerability')}:"}
        ],
        "chosen": {
            "from": "gpt",
            "value": item.get("description", "") + "\n\nMitigation: " + item.get("fix", "Review and patch immediately.")
        },
        "rejected": {
            "from": "gpt",
            "value": "This is a minor issue. No action needed."
        }
    }


def save_as_jsonl(data: List[Dict], output_path: str):
    """保存为 JSONL 格式"""
    import json
    with open(output_path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
```

- [ ] **步骤 6：编写数据管线入口**

```python
# vulndetect/data_pipeline/pipeline.py
#!/usr/bin/env python3
"""数据采集管线入口——拉取 → 清洗 → 格式化 → 存储"""
import argparse
import os
from pathlib import Path

from vulndetect.data_pipeline.collectors.nvd import fetch_cves, parse_cve
from vulndetect.data_pipeline.collectors.github_advisory import fetch_advisories
from vulndetect.data_pipeline.cleaners.dedup import deduplicate, filter_by_severity
from vulndetect.data_pipeline.cleaners.normalizer import normalize_vuln_item
from vulndetect.data_pipeline.formatters.openrlhf_format import (
    format_vuln_to_conversation,
    format_vuln_to_dpo,
    save_as_jsonl,
)


def run_pipeline(output_dir: str = "data/vulndetect", days_back: int = 30):
    """运行完整数据管线"""
    os.makedirs(output_dir, exist_ok=True)
    print(f"Collecting vulnerability data (last {days_back} days)...")

    # Step 1: 采集
    print("  Fetching NVD CVEs...")
    nvd_raw = fetch_cves(days_back=days_back, severity="HIGH")
    nvd_data = [parse_cve(item) for item in nvd_raw]
    print(f"  NVD: {len(nvd_data)} CVEs collected")

    print("  Fetching GitHub Advisories...")
    ghsa_data = fetch_advisories(severity="high")
    print(f"  GitHub: {len(ghsa_data)} advisories collected")

    # Step 2: 合并 + 清洗
    all_data = nvd_data + ghsa_data
    all_data = [normalize_vuln_item(item) for item in all_data]
    all_data = deduplicate(all_data, key="cve_id")
    all_data = filter_by_severity(all_data, min_severity="MEDIUM")
    print(f"  After dedup + filter: {len(all_data)} items")

    # Step 3: 格式化（SFT 和 DPO 两种格式）
    sft_data = [format_vuln_to_conversation(item) for item in all_data]
    sft_path = Path(output_dir) / "train_sft.jsonl"
    save_as_jsonl(sft_data, str(sft_path))
    print(f"  SFT data saved: {sft_path} ({len(sft_data)} samples)")

    dpo_data = [format_vuln_to_dpo(item) for item in all_data if item.get("fix")]
    dpo_path = Path(output_dir) / "train_dpo.jsonl"
    save_as_jsonl(dpo_data, str(dpo_path))
    print(f"  DPO data saved: {dpo_path} ({len(dpo_data)} samples)")

    # Step 4: 划分 train/val
    from vulndetect.training.openrlhf_wrapper.datasets import split_dataset, save_conversation_dataset
    train, val = split_dataset(sft_data, val_split=0.1)
    save_conversation_dataset(train, str(Path(output_dir) / "train.jsonl"))
    save_conversation_dataset(val, str(Path(output_dir) / "val.jsonl"))
    print(f"  Split: train={len(train)}, val={len(val)}")

    print("Pipeline complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="data/vulndetect")
    parser.add_argument("--days-back", type=int, default=30)
    args = parser.parse_args()
    run_pipeline(args.output_dir, args.days_back)
```

- [ ] **步骤 7：运行测试验证**

```bash
cd vulndetect && python -m pytest tests/data_pipeline/ -v
# 预期：3-4 PASSED
```

- [ ] **步骤 8：Commit**

```bash
git add vulndetect/data_pipeline/ vulndetect/tests/data_pipeline/ && git commit -m "feat: add NVD + GitHub Advisory collectors and data pipeline"
```

---

## 阶段 7：集成验证

### 任务 7.1：端到端烟雾测试

- [ ] **步骤 1：创建集成测试**

```python
# vulndetect/tests/test_e2e.py
"""端到端烟雾测试——验证各模块能正确导入和连接"""
import pytest


def test_import_all_modules():
    """测试所有模块能正常导入"""
    modules = [
        "vulndetect.training.openrlhf_wrapper.datasets",
        "vulndetect.training.openrlhf_wrapper.models",
        "vulndetect.training.config_loader",
        "vulndetect.training.checkpoint",
        "vulndetect.evaluation.harness",
        "vulndetect.evaluation.benchmarks.registry",
        "vulndetect.evaluation.scheduler",
        "vulndetect.evaluation.reporter",
        "vulndetect.data_pipeline.pipeline",
        "vulndetect.data_pipeline.collectors.nvd",
        "vulndetect.data_pipeline.collectors.github_advisory",
        "vulndetect.data_pipeline.cleaners.dedup",
        "vulndetect.data_pipeline.formatters.openrlhf_format",
        "vulndetect.backend.main",
    ]
    for module in modules:
        __import__(module)
        print(f"  OK: {module}")


def test_config_roundtrip():
    """测试配置加载往返——加载实验配置不报错"""
    from vulndetect.training.config_loader import load_config
    cfg = load_config("vulndetect/config/experiments/exp001_sft.yaml")
    assert cfg["experiment"]["name"] != ""
    assert len(cfg["evaluation"]["benchmarks"]) >= 2


def test_backend_health():
    """测试 FastAPI health endpoint"""
    from vulndetect.backend.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **步骤 2：运行全量测试**

```bash
cd vulndetect && python -m pytest tests/ -v --tb=short
# 预期：所有测试 PASS（~15-20 tests）
```

- [ ] **步骤 3：Commit**

```bash
git add -A && git commit -m "test: add e2e smoke tests and integration verification"
```

---

## 附录 A：启动命令速查

```bash
# 环境搭建
bash vulndetect/scripts/setup_env.sh

# 数据采集
cd vulndetect && python -m data_pipeline.pipeline --output-dir data/vulndetect --days-back 30

# SFT 训练
cd vulndetect && python -m training.sft --config config/experiments/exp001_sft.yaml

# DPO 训练
cd vulndetect && python -m training.dpo --config config/experiments/exp001_sft.yaml --sft_checkpoint experiments/qwen3b-sft-v1/checkpoints/final

# 评测
cd vulndetect && python -m evaluation.scheduler --experiment experiments/qwen3b-sft-v1 --benchmarks vulnbench,seceval

# 启动后端
cd vulndetect && uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 启动前端
cd vulndetect/frontend && npm run dev

# 全量测试
cd vulndetect && python -m pytest tests/ -v
```

