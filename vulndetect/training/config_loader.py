"""YAML 配置加载——支持多文件合并"""
import yaml
from pathlib import Path
from typing import Dict, Any
from copy import deepcopy

# vulndetect/ 包根目录
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def load_config(config_path: str) -> Dict[str, Any]:
    path = Path(config_path)
    if not path.is_absolute():
        # Try CWD first, then relative to package root (vulndetect/)
        if not path.exists():
            path = _PACKAGE_ROOT / path
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def merge_configs(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def load_experiment_config(experiment_path: str) -> Dict[str, Any]:
    exp_config = load_config(experiment_path)
    config_dir = _PACKAGE_ROOT / "config"

    includes = exp_config.get("includes", {})
    if "model" in includes:
        model_path = config_dir / includes["model"]
        if model_path.exists():
            exp_config = merge_configs(load_config(str(model_path)), exp_config)
    if "training" in includes:
        train_path = config_dir / includes["training"]
        if train_path.exists():
            exp_config = merge_configs(load_config(str(train_path)), exp_config)

    return exp_config
