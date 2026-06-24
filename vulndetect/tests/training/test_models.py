import pytest


def test_build_qlora_config():
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
    from vulndetect.training.openrlhf_wrapper.models import build_qlora_config

    default_config = {}
    bnb_config, lora_config = build_qlora_config(default_config)
    assert bnb_config is not None
    assert lora_config.r == 16
    assert lora_config.lora_alpha == 32


def test_get_target_modules_qwen():
    from vulndetect.training.openrlhf_wrapper.models import get_target_modules

    modules = get_target_modules("qwen")
    assert "q_proj" in modules
    assert "v_proj" in modules
    assert len(modules) >= 4


def test_get_target_modules_llama():
    from vulndetect.training.openrlhf_wrapper.models import get_target_modules

    modules = get_target_modules("llama")
    assert len(modules) >= 4
