#!/usr/bin/env python3
"""DPO training entry point -- single-GPU QLoRA"""
import argparse
import os
import torch
from pathlib import Path
from transformers import TrainingArguments
from trl import DPOTrainer
from peft import get_peft_model, prepare_model_for_kbit_training, PeftModel

from vulndetect.training.config_loader import load_experiment_config
from vulndetect.training.openrlhf_wrapper.models import build_qlora_config, load_model_and_tokenizer
from vulndetect.training.openrlhf_wrapper.datasets import load_conversation_dataset, format_for_dpo
from vulndetect.training.trainer import MetricsDBCallback


def _update_db_status(exp_name: str, status: str):
    """更新 SQLite 中实验状态"""
    try:
        from vulndetect.backend.database import SessionLocal
        from vulndetect.backend.models.schema import Experiment
        db = SessionLocal()
        exp = db.query(Experiment).filter(Experiment.name == exp_name).first()
        if exp:
            exp.status = status
            db.commit()
            print(f"Status -> {status}")
        db.close()
    except Exception as e:
        print(f"DB update skipped: {e}")


def prepare_dpo_dataset(data_config):
    from datasets import Dataset
    dataset_name = data_config.get("dataset", {}).get("name", "vulndetect")
    # Try multiple paths (DPO data may be named with or without _dpo suffix)
    paths = [
        f"data/{dataset_name}/{dataset_name}_train_dpo.jsonl",
        f"data/{dataset_name}/train_dpo.jsonl",
    ]
    data_path = None
    for p in paths:
        if os.path.exists(p):
            data_path = p
            break
    if not data_path:
        raise FileNotFoundError(f"DPO data not found. Tried: {paths}")
    print(f"Loading DPO data: {data_path}")
    raw_data = load_conversation_dataset(data_path)
    formatted = [format_for_dpo(item) for item in raw_data]
    return Dataset.from_list(formatted)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--sft_checkpoint", type=str, required=True)
    args = parser.parse_args()

    config = load_experiment_config(args.config)
    exp_name = config["experiment"]["name"]
    print(f"DPO Training: {exp_name}")

    model, tokenizer = load_model_and_tokenizer(config)
    model = prepare_model_for_kbit_training(model)
    _, lora_config = build_qlora_config(config)
    model = get_peft_model(model, lora_config)

    sft_model = PeftModel.from_pretrained(model, args.sft_checkpoint, is_trainable=True)

    ref_model = PeftModel.from_pretrained(model, args.sft_checkpoint)
    for param in ref_model.parameters():
        param.requires_grad = False

    dataset = prepare_dpo_dataset(config.get("data", {}))

    train_cfg = config.get("training", {})
    dpo_cfg = train_cfg.get("dpo", {})

    exp_dir = Path("experiments") / exp_name / "checkpoints"
    exp_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(exp_dir / "dpo"),
        per_device_train_batch_size=dpo_cfg.get("per_device_train_batch_size", 2),
        gradient_accumulation_steps=dpo_cfg.get("gradient_accumulation_steps", 8),
        learning_rate=dpo_cfg.get("learning_rate", 5e-5),
        num_train_epochs=dpo_cfg.get("num_epochs", 1),
        logging_steps=1,
        save_steps=200,
        bf16=True,
        gradient_checkpointing=True,
        remove_unused_columns=False,
        report_to=[],
    )

    _update_db_status(exp_name, "running")
    print("Status -> running")

    dpo_trainer = DPOTrainer(
        model=sft_model, ref_model=ref_model, args=training_args,
        train_dataset=dataset, tokenizer=tokenizer,
        beta=dpo_cfg.get("beta", 0.1),
        loss_type=dpo_cfg.get("loss_type", "sigmoid"),
        max_length=train_cfg.get("max_seq_length", 2048),
        max_prompt_length=train_cfg.get("max_prompt_length", 1024),
        callbacks=[MetricsDBCallback(exp_name)],
    )

    dpo_trainer.train()

    # Save DPO checkpoint
    dpo_dir = str(exp_dir / "dpo-final")
    sft_model.save_pretrained(dpo_dir)
    tokenizer.save_pretrained(dpo_dir)
    print(f"DPO checkpoint saved to {dpo_dir}")

    _update_db_status(exp_name, "completed")
    print("DPO Training complete!")


if __name__ == "__main__":
    main()
