# vulndetect/training/checkpoint.py
"""Checkpoint 管理——保存、恢复、查找最新"""
import os
import json
from pathlib import Path
from typing import Optional, Dict


def save_checkpoint(model, tokenizer, output_dir: str, step: int, loss: float, metrics: Optional[Dict] = None):
    os.makedirs(output_dir, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    state = {"step": step, "loss": loss, "metrics": metrics or {}}
    with open(Path(output_dir) / "trainer_state.json", "w") as f:
        json.dump(state, f, indent=2)


def load_checkpoint_state(checkpoint_dir: str) -> Dict:
    state_path = Path(checkpoint_dir) / "trainer_state.json"
    if not state_path.exists():
        return {"step": 0, "loss": None, "metrics": {}}
    with open(state_path, "r") as f:
        return json.load(f)


def find_latest_checkpoint(experiment_dir: str) -> Optional[str]:
    checkpoints_dir = Path(experiment_dir) / "checkpoints"
    if not checkpoints_dir.exists():
        return None
    checkpoints = sorted(
        [d for d in checkpoints_dir.iterdir() if d.is_dir() and (d / "trainer_state.json").exists()],
        key=lambda x: int(x.name.replace("checkpoint-", "")),
        reverse=True,
    )
    return str(checkpoints[0]) if checkpoints else None
