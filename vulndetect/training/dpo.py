#!/usr/bin/env python3
"""DPO training — 不依赖 TRL，纯 PyTorch 实现"""
import argparse
import os
import torch
import torch.nn.functional as F
from pathlib import Path
from datetime import datetime
from torch.utils.data import DataLoader
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, get_cosine_schedule_with_warmup
from peft import PeftModel, get_peft_model, LoraConfig
from datasets import Dataset
from tqdm import tqdm

from vulndetect.training.config_loader import load_experiment_config
from vulndetect.training.openrlhf_wrapper.datasets import load_conversation_dataset, format_for_dpo


def _update_db_status(exp_name: str, status: str):
    try:
        from vulndetect.backend.database import SessionLocal
        from vulndetect.backend.models.schema import Experiment
        db = SessionLocal()
        exp = db.query(Experiment).filter(Experiment.name == exp_name).first()
        if exp:
            exp.status = status
            db.commit()
        db.close()
    except Exception:
        pass


def _log_metric(exp_name: str, step: int, loss: float, lr: float):
    try:
        from vulndetect.backend.database import SessionLocal
        from vulndetect.backend.models.schema import TrainingMetric, Experiment
        db = SessionLocal()
        exp = db.query(Experiment).filter(Experiment.name == exp_name).first()
        if exp:
            gpu_mem = torch.cuda.memory_reserved(0) / (1024 * 1024) if torch.cuda.is_available() else 0
            db.add(TrainingMetric(experiment_id=exp.id, step=step, loss=loss, learning_rate=lr, gpu_memory_mb=round(gpu_mem, 1), timestamp=datetime.utcnow()))
            db.commit()
        db.close()
    except Exception:
        pass


def dpo_loss(policy_logps_chosen, policy_logps_rejected, ref_logps_chosen, ref_logps_rejected, beta=0.1):
    """DPO loss: 让 chosen 的 relative log-prob 高于 rejected"""
    policy_ratio_chosen = policy_logps_chosen - ref_logps_chosen
    policy_ratio_rejected = policy_logps_rejected - ref_logps_rejected
    logits = beta * (policy_ratio_chosen - policy_ratio_rejected)
    return -F.logsigmoid(logits).mean()


def compute_logprobs(model, input_ids, attention_mask, labels):
    """计算 labels 部分的 log probabilities"""
    with torch.no_grad():
        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
    logits = outputs.logits[:, :-1, :]
    shift_labels = labels[:, 1:]
    # Clamp out-of-vocab token IDs to safe range
    vocab_size = logits.size(-1)
    shift_labels = shift_labels.clamp(0, vocab_size - 1)
    log_probs = F.log_softmax(logits, dim=-1)
    token_logprobs = log_probs.gather(-1, shift_labels.unsqueeze(-1)).squeeze(-1)
    mask = (labels[:, 1:] != -100)
    return (token_logprobs * mask).sum(-1) / mask.sum(-1).clamp(min=1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True)
    parser.add_argument("--sft_checkpoint", type=str, required=True)
    args = parser.parse_args()

    config = load_experiment_config(args.config)
    exp_name = config["experiment"]["name"]
    print(f"DPO Training: {exp_name}")

    train_cfg = config.get("training", {})
    dpo_cfg = train_cfg.get("dpo", {})
    beta = dpo_cfg.get("beta", 0.1)
    lr = dpo_cfg.get("learning_rate", 5e-5)
    epochs = dpo_cfg.get("num_epochs", 1)
    batch_size = dpo_cfg.get("per_device_train_batch_size", 2)
    max_length = train_cfg.get("max_seq_length", 2048)

    # Load model
    print("Loading base model...")
    bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True, bnb_4bit_quant_type="nf4")
    model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-3B-Instruct", quantization_config=bnb_config, device_map="auto", trust_remote_code=True, torch_dtype=torch.bfloat16)
    tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-3B-Instruct", trust_remote_code=True)

    # Load SFT adapter for policy model (trainable)
    lora_config = LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05, target_modules=["q_proj", "k_proj", "v_proj", "o_proj"], bias="none", task_type="CAUSAL_LM")
    model = get_peft_model(model, lora_config)
    model = PeftModel.from_pretrained(model, args.sft_checkpoint, is_trainable=True)
    policy = model

    # Reference model (frozen, same SFT checkpoint)
    ref_model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen2.5-3B-Instruct", quantization_config=bnb_config, device_map="auto", trust_remote_code=True, torch_dtype=torch.bfloat16)
    ref_model = get_peft_model(ref_model, lora_config)
    ref_model = PeftModel.from_pretrained(ref_model, args.sft_checkpoint)
    for p in ref_model.parameters():
        p.requires_grad = False
    ref_model.eval()

    # Load DPO data
    data_cfg = config.get("data", {})
    dataset_name = data_cfg.get("dataset", {}).get("name", "vulndetect")
    paths = [f"data/{dataset_name}/{dataset_name}_train_dpo.jsonl", f"data/{dataset_name}/train_dpo.jsonl"]
    data_path = None
    for p in paths:
        if os.path.exists(p):
            data_path = p
            break
    if not data_path:
        raise FileNotFoundError(f"DPO data not found. Tried: {paths}")
    raw_data = load_conversation_dataset(data_path)
    formatted = [format_for_dpo(item) for item in raw_data]
    print(f"DPO data: {len(formatted)} pairs")

    # Tokenize
    def tokenize_fn(item):
        prompt = tokenizer(item["prompt"], truncation=True, max_length=max_length)["input_ids"]
        chosen = tokenizer(item["chosen"], truncation=True, max_length=max_length)["input_ids"]
        rejected = tokenizer(item["rejected"], truncation=True, max_length=max_length)["input_ids"]
        return {"prompt_ids": prompt, "chosen_ids": chosen, "rejected_ids": rejected}

    dataset = Dataset.from_list(formatted).map(tokenize_fn)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True, collate_fn=lambda batch: batch)

    # Optimizer
    optimizer = torch.optim.AdamW(policy.parameters(), lr=lr)
    total_steps = epochs * len(dataloader)
    scheduler = get_cosine_schedule_with_warmup(optimizer, num_warmup_steps=max(1, total_steps // 10), num_training_steps=total_steps)

    _update_db_status(exp_name, "running")
    print(f"Training {epochs} epoch(s), {len(dataloader)} steps/epoch, beta={beta}, lr={lr}")

    exp_dir = Path("experiments") / exp_name / "checkpoints"
    exp_dir.mkdir(parents=True, exist_ok=True)
    global_step = 0

    for epoch in range(epochs):
        policy.train()
        epoch_loss = 0
        pbar = tqdm(dataloader, desc=f"Epoch {epoch+1}/{epochs}")
        for batch in pbar:
            # Pad prompts and responses
            max_p = max(len(item["prompt_ids"]) for item in batch)
            max_c = max(len(item["chosen_ids"]) for item in batch)
            max_r = max(len(item["rejected_ids"]) for item in batch)
            max_len = max_p + max(max_c, max_r)

            def build_batch(key):
                ids, masks, labels = [], [], []
                for item in batch:
                    p_ids = item["prompt_ids"]
                    r_ids = item[key + "_ids"]
                    full = p_ids + r_ids
                    pad_len = max_len - len(full)
                    ids.append(full + [tokenizer.pad_token_id] * pad_len)
                    m = [1] * len(full) + [0] * pad_len
                    masks.append(m)
                    lab = [-100] * len(p_ids) + r_ids + [-100] * pad_len
                    labels.append(lab)
                return (torch.tensor(ids).cuda(), torch.tensor(masks).cuda(), torch.tensor(labels).cuda())

            c_ids, c_mask, c_labels = build_batch("chosen")
            r_ids, r_mask, r_labels = build_batch("rejected")

            # Reference model logprobs (no grad)
            ref_logps_c = compute_logprobs(ref_model, c_ids, c_mask, c_labels)
            ref_logps_r = compute_logprobs(ref_model, r_ids, r_mask, r_labels)

            # Policy model logprobs
            def policy_logps(ids, mask, labels):
                outputs = policy(input_ids=ids, attention_mask=mask)
                logits = outputs.logits[:, :-1, :]
                shift_labels = labels[:, 1:]
                vocab_size = logits.size(-1)
                shift_labels = shift_labels.clamp(0, vocab_size - 1)
                lp = F.log_softmax(logits, dim=-1)
                token_lp = lp.gather(-1, shift_labels.unsqueeze(-1)).squeeze(-1)
                valid = (labels[:, 1:] != -100)
                return (token_lp * valid).sum(-1) / valid.sum(-1).clamp(min=1)

            policy_logps_c = policy_logps(c_ids, c_mask, c_labels)
            policy_logps_r = policy_logps(r_ids, r_mask, r_labels)

            loss = dpo_loss(policy_logps_c, policy_logps_r, ref_logps_c, ref_logps_r, beta)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            scheduler.step()

            epoch_loss += loss.item()
            global_step += 1
            pbar.set_postfix({"loss": f"{loss.item():.4f}", "lr": f"{scheduler.get_last_lr()[0]:.2e}"})

            if global_step % 5 == 0:
                _log_metric(exp_name, global_step, loss.item(), scheduler.get_last_lr()[0])

        print(f"Epoch {epoch+1}: avg_loss={epoch_loss/len(dataloader):.4f}")

    # Save
    dpo_dir = str(exp_dir / "dpo-final")
    policy.save_pretrained(dpo_dir)
    tokenizer.save_pretrained(dpo_dir)
    print(f"DPO checkpoint saved to {dpo_dir}")

    _update_db_status(exp_name, "completed")
    print("DPO Training complete!")


if __name__ == "__main__":
    main()
