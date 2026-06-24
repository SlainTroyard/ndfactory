# vulndetect/training/trainer.py
"""统一 Trainer——封装 SFT/DPO/PPO 训练循环"""
import os
from pathlib import Path
from typing import Dict, Optional
from transformers import TrainingArguments, Trainer, DataCollatorForSeq2Seq
from peft import get_peft_model, prepare_model_for_kbit_training, PeftModel

from vulndetect.training.checkpoint import find_latest_checkpoint
from vulndetect.training.openrlhf_wrapper.models import build_qlora_config, load_model_and_tokenizer


class VulnDetectTrainer:
    def __init__(self, config: Dict):
        self.config = config
        self.model = None
        self.tokenizer = None
        self.trainer = None
        exp_name = config["experiment"]["name"]
        self.experiment_dir = Path("experiments") / exp_name
        self.checkpoints_dir = self.experiment_dir / "checkpoints"
        self.logs_dir = self.experiment_dir / "logs"

    def setup(self):
        os.makedirs(self.checkpoints_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
        self.model, self.tokenizer = load_model_and_tokenizer(self.config)
        self.model = prepare_model_for_kbit_training(self.model)
        _, lora_config = build_qlora_config(self.config)
        self.model = get_peft_model(self.model, lora_config)
        self.model.config.use_cache = False

        latest = find_latest_checkpoint(str(self.experiment_dir))
        if latest:
            self.model = PeftModel.from_pretrained(self.model, latest)
            print(f"Resumed from checkpoint: {latest}")

    def train_sft(self, train_dataset, eval_dataset=None):
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
            remove_unused_columns=False,
        )

        data_collator = DataCollatorForSeq2Seq(tokenizer=self.tokenizer, padding=True)

        self.trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=eval_dataset,
            data_collator=data_collator,
        )

        self.trainer.train()

        final_dir = str(self.checkpoints_dir / "final")
        self.model.save_pretrained(final_dir)
        self.tokenizer.save_pretrained(final_dir)

        return self.trainer.state
