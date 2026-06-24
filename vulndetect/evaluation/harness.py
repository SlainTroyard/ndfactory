"""lm-evaluation-harness wrapper"""
import subprocess
import json
import re
import os
from pathlib import Path
from typing import List, Dict


def build_eval_command(model_path: str, benchmarks: List[str], output_dir: str, model_type: str = "hf", batch_size: str = "auto") -> List[str]:
    return [
        "lm_eval", "--model", model_type,
        "--model_args", f"pretrained={model_path},trust_remote_code=True",
        "--tasks", ",".join(benchmarks),
        "--batch_size", batch_size,
        "--output_path", output_dir,
    ]


def run_evaluation(model_path: str, benchmarks: List[str], output_dir: str) -> Dict:
    cmd = build_eval_command(model_path, benchmarks, output_dir)
    os.makedirs(output_dir, exist_ok=True)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        raise RuntimeError(f"lm_eval failed: {result.stderr}")
    return parse_eval_results(result.stdout)


def parse_eval_results(output: str) -> Dict[str, Dict]:
    results = {}
    pattern = r'\|\s*(\S+)\s*\|\s*\S+\s*\|\s*\S+\s*\|\s*\d+\s*\|\s*(\S+)\s*\|\s*\S*\|\s*([\d.]+)\s*\|\s*\S*\|\s*([\d.]+)\s*\|'
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        match = re.match(pattern, line)
        if match:
            benchmark = match.group(1)
            metric = match.group(2)
            score = float(match.group(3))
            stderr = float(match.group(4))
            results[benchmark] = {"metric": metric, "score": score, "stderr": stderr}
    return results


def load_results_from_file(output_dir: str) -> Dict:
    results_file = Path(output_dir) / "results.json"
    if results_file.exists():
        with open(results_file, "r") as f:
            return json.load(f)
    return {}
