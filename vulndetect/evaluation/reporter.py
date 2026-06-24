"""Eval result comparison and report generation"""
import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime


def compare_experiments(experiment_dirs: List[str]) -> Dict:
    comparison = {}
    for exp_dir in experiment_dirs:
        exp_path = Path(exp_dir)
        exp_name = exp_path.name
        comparison[exp_name] = {}
        eval_dir = exp_path / "evaluations"
        if not eval_dir.exists():
            continue
        eval_dirs = sorted([d for d in eval_dir.iterdir() if d.is_dir()], key=lambda x: x.name)
        if not eval_dirs:
            continue
        latest_eval = eval_dirs[-1] / "results.json"
        if latest_eval.exists():
            with open(latest_eval, "r") as f:
                results = json.load(f)
            for bench, scores in results.items():
                if bench != "_meta" and isinstance(scores, dict):
                    comparison[exp_name][bench] = scores.get("score", 0)
    return comparison


def generate_report(experiment_dir: str, fmt: str = "markdown") -> str:
    exp_path = Path(experiment_dir)
    eval_dir = exp_path / "evaluations"
    if not eval_dir.exists():
        return "No evaluation results yet."
    lines = [f"# Evaluation Report: {exp_path.name}", f"Generated: {datetime.now().isoformat()}", ""]
    for eval_subdir in sorted(eval_dir.iterdir()):
        if not eval_subdir.is_dir():
            continue
        rf = eval_subdir / "results.json"
        if not rf.exists():
            continue
        with open(rf, "r") as f:
            results = json.load(f)
        step = results.get("_meta", {}).get("checkpoint_step", "unknown")
        lines.append(f"## Checkpoint {step}")
        lines.append("| Benchmark | Score |")
        lines.append("|-----------|-------|")
        for bench, scores in results.items():
            if bench == "_meta":
                continue
            score = scores.get("score", "N/A")
            lines.append(f"| {bench} | {score:.4f} |")
        lines.append("")
    return "\n".join(lines)
