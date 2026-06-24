"""模型加载——QLoRA 配置 + 基座模型加载"""
from typing import Dict, Tuple, List, Any


def build_qlora_config(config: Dict) -> Tuple[Any, Any]:
    from transformers import BitsAndBytesConfig
    from peft import LoraConfig

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
    target_modules_map = {
        "qwen": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        "llama": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        "mistral": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    }
    return target_modules_map.get(model_family, target_modules_map["qwen"])


def load_model_and_tokenizer(model_config: Dict):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model_name = model_config.get("model", {}).get("name_or_path", "Qwen/Qwen2.5-3B-Instruct")
    trust_remote = model_config.get("model", {}).get("trust_remote_code", True)
    bnb_config, _ = build_qlora_config(model_config)

    tokenizer = AutoTokenizer.from_pretrained(
        model_name, trust_remote_code=trust_remote, padding_side="right",
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_name, quantization_config=bnb_config, device_map="auto",
        trust_remote_code=trust_remote, torch_dtype=torch.bfloat16,
    )
    return model, tokenizer
