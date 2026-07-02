# vulndetect/evaluation/benchmarks/code_analysis.py
"""Custom code vulnerability analysis evaluation with LLM-as-Judge.

Evaluates a model's ability to:
  - Detect whether code contains a vulnerability (recall/precision)
  - Correctly classify the CWE type (CWE accuracy)
  - Propose a workable fix (fix correctness)

Uses the teacher model (Claude Opus) as an impartial judge to assess
the student model's outputs against ground truth.

Usage:
    python -m vulndetect.evaluation.benchmarks.code_analysis \\
        --model experiments/qwen3b-distil-sft-v1/checkpoints/final \\
        --eval-set data/distil/samples_eval.jsonl \\
        --output eval_output/code_vuln_analysis.json
"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

JUDGE_PROMPT = """\
You are an impartial judge evaluating a code security analysis produced by a student model.

You are given:
1. The original code
2. The ground truth (whether a vulnerability exists, and if so what type)
3. The student model's analysis output

Judge the student's analysis on the following criteria. Answer each with YES or NO only.

## Ground Truth
- Has vulnerability: {has_vuln}
- CWE ID: {cwe_id}
- Vulnerability type: {vuln_type}

## Student Analysis
{model_output}

## Judging Criteria
1. Vulnerability Detection: Did the student CORRECTLY identify whether the code has a vulnerability?
   Answer YES if:
   - Ground truth says HAS vulnerability AND student found a real vulnerability (not hallucinated)
   - Ground truth says NO vulnerability AND student concluded the code is safe
   Answer NO if:
   - Student missed a real vulnerability
   - Student hallucinated a vulnerability that doesn't exist

2. CWE Classification: If a real vulnerability exists, did the student classify it with the correct CWE type?
   Answer YES if the CWE matches or is closely related (same category).
   Answer NO if the CWE is wrong.
   Answer N/A if there is no vulnerability.

3. Fix Correctness: If a fix was proposed, is it correct and practical?
   Answer YES if the fix would actually resolve the vulnerability.
   Answer NO if the fix is wrong, incomplete, or would break the code.
   Answer N/A if no fix was proposed or no vulnerability was found.

4. Reasoning Quality: Is the student's reasoning logical and well-structured?
   Answer YES if the analysis follows a clear logic chain.
   Answer NO if the reasoning is confused, contradictory, or nonsensical.

Output your judgments in this exact format (one per line):
VULN_DETECT: YES/NO
CWE_CLASSIFY: YES/NO/N/A
FIX_CORRECT: YES/NO/N/A
REASONING: YES/NO
"""


def load_eval_set(path: str) -> List[Dict]:
    """Load evaluation samples from a JSONL file.

    Expected fields per sample:
        id: str
        vulnerable_code: str (or code_snippet)
        language: str
        ground_truth: dict with keys: has_vuln (bool), cwe_id (str or None),
                      vuln_type (str), severity (str), fix_reference (str)
    """
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"Eval set not found: {path}")

    samples = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            sample = json.loads(line)
            if "ground_truth" not in sample:
                logger.warning("Sample %s missing ground_truth, skipping", sample.get("id", "?"))
                continue
            samples.append(sample)

    logger.info("Loaded %d eval samples from %s", len(samples), path)
    return samples


def generate_model_analysis(
    model_path: str,
    sample: Dict,
    max_new_tokens: int = 2048,
    model_type: str = "peft",
) -> str:
    """Generate a vulnerability analysis using the trained student model.

    Args:
        model_path: Path to the trained model checkpoint.
        sample: Eval sample with vulnerable_code and language fields.
        max_new_tokens: Maximum tokens to generate.
        model_type: "peft" for QLoRA adapters, "hf" for base HuggingFace model.

    Returns:
        Generated analysis text.
    """
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

    code = sample.get("vulnerable_code") or sample.get("code_snippet", "")
    language = sample.get("language", "")

    prompt = (
        f"请分析以下{language}代码是否存在安全漏洞：\n"
        f"```{language}\n{code}\n```"
    )

    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

    if model_type == "peft":
        from peft import PeftModel

        # Load base model with 4-bit quantization
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )

        # Try to infer base model from checkpoint config
        base_model_name = "Qwen/Qwen2.5-3B-Instruct"  # default
        try:
            adapter_config_path = Path(model_path) / "adapter_config.json"
            if adapter_config_path.exists():
                with open(adapter_config_path) as f:
                    adapter_cfg = json.load(f)
                base_model_name = adapter_cfg.get("base_model_name_or_path", base_model_name)
        except Exception:
            pass

        model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            quantization_config=bnb_config,
            trust_remote_code=True,
            device_map="auto",
        )
        model = PeftModel.from_pretrained(model, model_path)
    else:
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            device_map="auto",
        )

    model.eval()
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            temperature=0.1,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )

    # Decode only the generated part (remove prompt)
    input_len = inputs["input_ids"].shape[1]
    generated = tokenizer.decode(outputs[0][input_len:], skip_special_tokens=True)

    return generated


def judge_analysis(model_output: str, ground_truth: Dict) -> Dict:
    """Use teacher model (Claude Opus) as a judge to evaluate the student's analysis.

    Args:
        model_output: The text output from the student model.
        ground_truth: Dict with has_vuln, cwe_id, vuln_type, severity, fix_reference.

    Returns:
        Dict with keys:
            vuln_detect: bool
            cwe_classify: bool or None (None if N/A)
            fix_correct: bool or None
            reasoning: bool
            raw_judgment: str
    """
    from vulndetect.data_pipeline.distil.teacher import TeacherClient

    has_vuln = ground_truth.get("has_vuln", False)
    cwe_id = ground_truth.get("cwe_id") or "N/A"
    vuln_type = ground_truth.get("vuln_type") or "N/A"

    judge_prompt = JUDGE_PROMPT.format(
        has_vuln="YES" if has_vuln else "NO",
        cwe_id=cwe_id,
        vuln_type=vuln_type,
        model_output=model_output[:3000],  # Truncate very long outputs
    )

    teacher = TeacherClient()
    if not teacher._is_available():
        logger.warning("Teacher API not available for judging, returning defaults")
        return {
            "vuln_detect": False,
            "cwe_classify": None,
            "fix_correct": None,
            "reasoning": False,
            "raw_judgment": "JUDGE_UNAVAILABLE",
        }

    # Use a simpler API call pattern (not generate_analysis, which uses the audit prompt)
    import anthropic
    response = teacher.client.messages.create(
        model=teacher.model,
        max_tokens=200,
        messages=[{"role": "user", "content": judge_prompt}],
    )
    judgment_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            judgment_text += block.text

    # Parse the structured judgment
    def _parse_line(prefix, text):
        for line in text.strip().splitlines():
            if line.strip().startswith(prefix):
                value = line.split(":")[-1].strip()
                if value == "N/A":
                    return None
                return value == "YES"
        return None

    return {
        "vuln_detect": _parse_line("VULN_DETECT:", judgment_text),
        "cwe_classify": _parse_line("CWE_CLASSIFY:", judgment_text),
        "fix_correct": _parse_line("FIX_CORRECT:", judgment_text),
        "reasoning": _parse_line("REASONING:", judgment_text),
        "raw_judgment": judgment_text,
    }


def compute_metrics(eval_results: List[Dict]) -> Dict:
    """Compute evaluation metrics from a list of per-sample judgments.

    Args:
        eval_results: List of dicts, each with at least:
            ground_truth.has_vuln: bool
            judgment.vuln_detect: bool or None

    Returns:
        Dict of metric name → value.
    """
    tp = fp = tn = fn = 0
    cwe_correct = 0
    cwe_total = 0
    fix_correct = 0
    fix_total = 0

    for result in eval_results:
        gt = result.get("ground_truth", {})
        judgment = result.get("judgment", {})
        has_vuln_gt = gt.get("has_vuln", False)
        vuln_detect = judgment.get("vuln_detect")

        # Classification metrics
        if vuln_detect is True and has_vuln_gt is True:
            tp += 1
        elif vuln_detect is True and has_vuln_gt is False:
            fp += 1
        elif vuln_detect is False and has_vuln_gt is False:
            tn += 1
        elif vuln_detect is False and has_vuln_gt is True:
            fn += 1
        # vuln_detect is None → skip (judge unavailable)

        # CWE accuracy (only for samples with vulnerabilities)
        if has_vuln_gt and vuln_detect is True:
            cwe_total += 1
            if judgment.get("cwe_classify") is True:
                cwe_correct += 1

        # Fix correctness (only when a fix was proposed)
        if judgment.get("fix_correct") is not None:
            fix_total += 1
            if judgment.get("fix_correct") is True:
                fix_correct += 1

    total_vuln = tp + fn
    total_predicted = tp + fp

    recall = tp / max(total_vuln, 1)
    precision = tp / max(total_predicted, 1)
    f1 = 2 * precision * recall / max(precision + recall, 0.001)
    cwe_accuracy = cwe_correct / max(cwe_total, 1)
    fix_correctness = fix_correct / max(fix_total, 1)
    fpr = fp / max(fp + tn, 1)

    metrics = {
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "f1": round(f1, 4),
        "cwe_accuracy": round(cwe_accuracy, 4),
        "fix_correctness": round(fix_correctness, 4),
        "fpr": round(fpr, 4),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "total": len(eval_results),
        "judged": tp + fp + tn + fn,
    }
    return metrics


def run_eval(
    model_path: str,
    eval_set_path: str,
    output_path: str,
    max_samples: Optional[int] = None,
    model_type: str = "peft",
):
    """Run the full code analysis evaluation pipeline.

    Args:
        model_path: Path to the trained model checkpoint.
        eval_set_path: Path to hold-out eval set JSONL.
        output_path: Path for the output JSON results file.
        max_samples: Limit number of samples to evaluate (for testing).
        model_type: "peft" for QLoRA adapters, "hf" for base model.
    """
    samples = load_eval_set(eval_set_path)
    if max_samples and max_samples < len(samples):
        samples = samples[:max_samples]

    results = []
    for i, sample in enumerate(samples):
        sample_id = sample.get("id", f"sample-{i}")
        logger.info("[%d/%d] Evaluating %s", i + 1, len(samples), sample_id)

        # Generate student model analysis
        try:
            model_output = generate_model_analysis(
                model_path, sample, model_type=model_type,
            )
        except Exception as e:
            logger.error("Generation failed for %s: %s", sample_id, e)
            model_output = ""

        # Judge the analysis
        judgment = judge_analysis(model_output, sample.get("ground_truth", {}))

        results.append({
            "id": sample_id,
            "language": sample.get("language", ""),
            "ground_truth": sample.get("ground_truth", {}),
            "model_output": model_output,
            "judgment": judgment,
        })

    # Compute and attach metrics
    metrics = compute_metrics(results)

    output = {
        "model_path": model_path,
        "eval_set": eval_set_path,
        "metrics": metrics,
        "results": results,
    }

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info("Evaluation complete. Summary:")
    logger.info("  Recall:    %.3f", metrics["recall"])
    logger.info("  Precision: %.3f", metrics["precision"])
    logger.info("  F1:        %.3f", metrics["f1"])
    logger.info("  CWE Acc:   %.3f", metrics["cwe_accuracy"])
    logger.info("  Fix Corr:  %.3f", metrics["fix_correctness"])
    logger.info("  FPR:       %.3f", metrics["fpr"])
    logger.info("Results saved to %s", output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Code vulnerability analysis evaluation with LLM-as-Judge",
    )
    parser.add_argument(
        "--model", type=str, required=True,
        help="Path to trained model checkpoint",
    )
    parser.add_argument(
        "--eval-set", type=str, required=True,
        help="Path to hold-out eval set JSONL",
    )
    parser.add_argument(
        "--output", type=str, required=True,
        help="Output path for evaluation results JSON",
    )
    parser.add_argument(
        "--max-samples", type=int, default=None,
        help="Limit number of samples (for testing)",
    )
    parser.add_argument(
        "--model-type", type=str, default="peft",
        choices=["peft", "hf"],
        help="Model type: 'peft' for QLoRA adapters, 'hf' for base model (default: peft)",
    )

    args = parser.parse_args()
    run_eval(
        model_path=args.model,
        eval_set_path=args.eval_set,
        output_path=args.output,
        max_samples=args.max_samples,
        model_type=args.model_type,
    )


if __name__ == "__main__":
    main()
