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
    from vulndetect.training.config_loader import merge_configs

    base = {"training": {"max_seq_length": 2048, "num_epochs": 1}}
    override = {"training": {"num_epochs": 3}}

    merged = merge_configs(base, override)
    assert merged["training"]["max_seq_length"] == 2048
    assert merged["training"]["num_epochs"] == 3


def test_merge_configs_new_key():
    from vulndetect.training.config_loader import merge_configs

    base = {"training": {"lr": 1e-4}}
    override = {"evaluation": {"benchmarks": ["test"]}}

    merged = merge_configs(base, override)
    assert merged["training"]["lr"] == 1e-4
    assert merged["evaluation"]["benchmarks"] == ["test"]
