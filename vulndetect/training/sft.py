#!/usr/bin/env python3
# vulndetect/training/sft.py
"""QLoRA SFT 训练入口——配置驱动，单卡运行"""
import argparse
import os
from vulndetect.training.config_loader import load_experiment_config
from vulndetect.training.trainer import VulnDetectTrainer
from vulndetect.training.openrlhf_wrapper.datasets import load_conversation_dataset, format_for_sft, split_dataset


def prepare_sft_dataset(data_config, tokenizer, max_seq_length=2048):
    dataset_name = data_config.get("dataset", {}).get("name", "vulnbench")
    val_split = data_config.get("preprocessing", {}).get("val_split", 0.1)

    # Try multiple local paths
    local_paths = [
        f"data/{dataset_name}/{dataset_name}_train.jsonl",
        f"data/{dataset_name}/train.jsonl",
    ]
    local_path = None
    for p in local_paths:
        if os.path.exists(p):
            local_path = p
            break

    if not local_path:
        raise FileNotFoundError(
            f"No local data found for '{dataset_name}'. "
            f"Tried: {local_paths}. Run the data pipeline first:\n"
            f"  python -m vulndetect.data_pipeline.pipeline --output-dir data/{dataset_name}"
        )

    print(f"Loading local data: {local_path}")
    raw_data = load_conversation_dataset(local_path)

    # Convert conversation format to text and tokenize
    texts = []
    for item in raw_data:
        conversations = item.get("conversations", [])
        parts = []
        for conv in conversations:
            role = "User" if conv["from"] == "human" else "Assistant"
            parts.append(f"{role}: {conv['value']}")
        texts.append("\n".join(parts))

    # Tokenize all texts
    encodings = tokenizer(
        texts,
        truncation=True,
        padding=False,
        max_length=max_seq_length,
        return_tensors=None,
    )

    from datasets import Dataset
    dataset = Dataset.from_dict({
        "input_ids": [e for e in encodings["input_ids"]],
        "attention_mask": [e for e in encodings["attention_mask"]],
        "labels": [e for e in encodings["input_ids"]],  # causal LM: labels = input_ids
    })

    splits = dataset.train_test_split(test_size=val_split, seed=42)
    print(f"Tokenized: {len(splits['train'])} train, {len(splits['test'])} val")
    return splits["train"], splits["test"]


def main():
    parser = argparse.ArgumentParser(description="QLoRA SFT Training")
    parser.add_argument("--config", type=str, required=True, help="Path to experiment YAML config")
    args = parser.parse_args()

    config = load_experiment_config(args.config)
    print(f"Experiment: {config['experiment']['name']}")
    print(f"Strategy: {config['training']['strategy']}")

    trainer = VulnDetectTrainer(config)
    trainer.setup()

    train_data, val_data = prepare_sft_dataset(config.get("data", {}), trainer.tokenizer)
    print(f"Train samples: {len(train_data)}, Val samples: {len(val_data)}")

    trainer.train_sft(train_data, val_data)
    print("Training complete!")


if __name__ == "__main__":
    main()
