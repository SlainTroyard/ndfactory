#!/usr/bin/env python3
"""PPO training entry point -- single-GPU simplified version"""
import argparse
import torch
from trl import PPOConfig
from peft import prepare_model_for_kbit_training

from vulndetect.training.config_loader import load_experiment_config
from vulndetect.training.openrlhf_wrapper.models import load_model_and_tokenizer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--sft_checkpoint", type=str, required=True)
    args = parser.parse_args()

    config = load_experiment_config(args.config)
    print(f"PPO Training: {config['experiment']['name']}")

    model, tokenizer = load_model_and_tokenizer(config)
    model = prepare_model_for_kbit_training(model)

    ppo_cfg = config.get("training", {}).get("ppo", {})

    ppo_config = PPOConfig(
        model_name=config["experiment"]["name"],
        learning_rate=config["training"].get("learning_rate", 1e-5),
        ppo_epochs=ppo_cfg.get("ppo_epochs", 4),
        batch_size=ppo_cfg.get("batch_size", 64),
        mini_batch_size=ppo_cfg.get("mini_batch_size", 8),
        gradient_accumulation_steps=config["training"].get("gradient_accumulation_steps", 16),
    )

    print("PPO config ready. Reward model required for actual training.")
    print(f"Config: {ppo_config}")
    print("For Qwen-3B on A6000, use a rule-based reward or small reward model.")


if __name__ == "__main__":
    main()
