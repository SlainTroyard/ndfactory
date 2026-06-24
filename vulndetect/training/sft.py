#!/usr/bin/env python3
# vulndetect/training/sft.py
"""QLoRA SFT 训练入口——配置驱动，单卡运行"""
import argparse
import os
from vulndetect.training.config_loader import load_experiment_config
from vulndetect.training.trainer import VulnDetectTrainer
from vulndetect.training.openrlhf_wrapper.datasets import load_conversation_dataset, format_for_sft, split_dataset


def prepare_sft_dataset(data_config):
    dataset_name = data_config.get("dataset", {}).get("name", "vulnbench")
    val_split = data_config.get("preprocessing", {}).get("val_split", 0.1)

    local_path = f"data/{dataset_name}/train.jsonl"
    if os.path.exists(local_path):
        raw_data = load_conversation_dataset(local_path)
        train_data, val_data = split_dataset(raw_data, val_split)
    else:
        from datasets import load_dataset
        dataset = load_dataset(dataset_name, split="train")
        splits = dataset.train_test_split(test_size=val_split)
        train_data = splits["train"]
        val_data = splits["test"]

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

    train_data, val_data = prepare_sft_dataset(config.get("data", {}))
    print(f"Train samples: {len(train_data)}, Val samples: {len(val_data)}")

    trainer.train_sft(train_data, val_data)
    print("Training complete!")


if __name__ == "__main__":
    main()
