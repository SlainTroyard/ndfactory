"""Checkpoint evaluation scheduler"""
import os
import json
import time
from pathlib import Path
from typing import Dict, List, Callable, Optional
from datetime import datetime
from vulndetect.evaluation.harness import run_evaluation
from vulndetect.evaluation.benchmarks.registry import get_task_name


def evaluate_checkpoint(model_path: str, checkpoint_step: int, benchmarks: List[str], experiment_dir: str) -> Dict:
    output_dir = Path(experiment_dir) / "evaluations" / f"step-{checkpoint_step}"
    os.makedirs(output_dir, exist_ok=True)
    tasks = [get_task_name(b) for b in benchmarks]
    results = run_evaluation(str(model_path), tasks, str(output_dir))
    results["_meta"] = {"checkpoint_step": checkpoint_step, "model_path": model_path, "timestamp": datetime.now().isoformat(), "benchmarks_run": benchmarks}
    with open(output_dir / "results.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    return results


def watch_and_evaluate(checkpoints_dir: str, experiment_dir: str, benchmarks: List[str], callback: Optional[Callable] = None, interval_seconds: int = 30):
    seen = set()
    while True:
        cp_dir = Path(checkpoints_dir)
        if cp_dir.exists():
            for d in sorted(cp_dir.iterdir()):
                if d.is_dir() and d.name.startswith("checkpoint-"):
                    if d.name not in seen:
                        seen.add(d.name)
                        step = int(d.name.replace("checkpoint-", ""))
                        print(f"Evaluating {d.name}...")
                        results = evaluate_checkpoint(str(d), step, benchmarks, experiment_dir)
                        if callback:
                            callback(step, results)
        time.sleep(interval_seconds)
