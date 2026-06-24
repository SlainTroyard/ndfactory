#!/usr/bin/env python3
"""DPO training entry point -- single-GPU QLoRA"""
import argparse
import torch
from transformers import TrainingArguments
from trl import DPOTrainer
from peft import get_peft_model, prepare_model_for_kbit_training, PeftModel

from vulndetect.training.config_loader import load_experiment_config
from vulndetect.training.openrlhf_wrapper.models import build_qlora_config, load_model_and_tokenizer
from vulndetect.training.openrlhf_wrapper.datasets import load_conversation_dataset, format_for_dpo


def prepare_dpo_dataset(data_config):
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
    parser.add_argument("--sft_checkpoint", type=str, required=True, help="Path to SFT checkpoint (LoRA adapter)")
    args = parser.parse_args()

    config = load_experiment_config(args.config)
    print(f"DPO Training: {config['experiment']['name']}")

    model, tokenizer = load_model_and_tokenizer(config)
    model = prepare_model_for_kbit_training(model)
    _, lora_config = build_qlora_config(config)
    model = get_peft_model(model, lora_config)

    # SFT adapter as trainable; reference model frozen
    sft_model = PeftModel.from_pretrained(model, args.sft_checkpoint, is_trainable=True)

    ref_model = PeftModel.from_pretrained(model, args.sft_checkpoint)
    for param in ref_model.parameters():
        param.requires_grad = False

    dataset = prepare_dpo_dataset(config.get("data", {}))

    train_cfg = config.get("training", {})
    dpo_cfg = train_cfg.get("dpo", {})

    training_args = TrainingArguments(
        output_dir=f"experiments/{config['experiment']['name']}/checkpoints",
        per_device_train_batch_size=dpo_cfg.get("per_device_train_batch_size", 2),
        gradient_accumulation_steps=dpo_cfg.get("gradient_accumulation_steps", 8),
        learning_rate=dpo_cfg.get("learning_rate", 5e-5),
        num_train_epochs=dpo_cfg.get("num_epochs", 1),
        logging_steps=10,
        save_steps=200,
        bf16=True,
        gradient_checkpointing=True,
        remove_unused_columns=False,
        report_to=["tensorboard"],
    )

    dpo_trainer = DPOTrainer(
        model=sft_model, ref_model=ref_model, args=training_args,
        train_dataset=dataset, tokenizer=tokenizer,
        beta=dpo_cfg.get("beta", 0.1),
        loss_type=dpo_cfg.get("loss_type", "sigmoid"),
        max_length=train_cfg.get("max_seq_length", 2048),
        max_prompt_length=train_cfg.get("max_prompt_length", 1024),
    )

    dpo_trainer.train()
    print("DPO Training complete!")


if __name__ == "__main__":
    main()
