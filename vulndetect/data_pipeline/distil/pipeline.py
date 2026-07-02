# vulndetect/data_pipeline/distil/pipeline.py
"""Distillation data generation pipeline — CLI entry point.

Orchestrates the full flow:
  1. Load code samples from JSONL
  2. Generate security audit analyses via teacher model (Claude Opus)
  3. Validate outputs against quality criteria
  4. Convert validated outputs to OpenRLHF conversation format
  5. Split into train/val sets and save as JSONL

Usage:
    python -m vulndetect.data_pipeline.distil.pipeline \\
        --input data/distil/samples_train.jsonl \\
        --output-dir data/distil
"""
import argparse
import json
import logging
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

SAMPLE_REQUIRED_FIELDS = {"id", "language"}


def load_code_samples(path: str) -> List[Dict]:
    """Load code samples from a JSONL file.

    Args:
        path: Path to a JSONL file with one JSON object per line.

    Returns:
        List of sample dicts. Invalid lines are skipped with a warning.

    Raises:
        FileNotFoundError: If the input file does not exist.
    """
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    samples = []
    skipped = 0
    with open(input_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                sample = json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning("Line %d: invalid JSON — %s", line_num, e)
                skipped += 1
                continue

            # Check required fields
            missing = SAMPLE_REQUIRED_FIELDS - set(sample.keys())
            if missing:
                logger.warning("Line %d (%s): missing fields %s — skipping",
                               line_num, sample.get("id", "?"), missing)
                skipped += 1
                continue

            # Normalize: ensure vulnerable_code or code_snippet exists
            if "vulnerable_code" not in sample and "code_snippet" not in sample:
                logger.warning("Line %d (%s): no code field — skipping",
                               line_num, sample.get("id", "?"))
                skipped += 1
                continue

            samples.append(sample)

    logger.info("Loaded %d samples from %s (%d skipped)", len(samples), path, skipped)
    return samples


def process_sample(
    sample: Dict,
    teacher,
    max_retries: int = 2,
) -> Optional[Dict]:
    """Generate and validate analysis for a single sample.

    Args:
        sample: Code sample dict with vulnerable_code, language, is_safe fields.
        teacher: TeacherClient instance for generation.
        max_retries: Max retry attempts if generation or validation fails.

    Returns:
        The sample dict augmented with teacher_output and validation fields,
        or None if all retries exhausted.
    """
    from vulndetect.data_pipeline.distil.validator import validate_analysis

    code = sample.get("vulnerable_code") or sample.get("code_snippet", "")
    language = sample.get("language", "")
    is_safe = sample.get("is_safe", False)
    sample_id = sample.get("id", "?")

    for attempt in range(max_retries + 1):
        if attempt > 0:
            logger.info("%s: retry %d/%d", sample_id, attempt, max_retries)

        output = teacher.generate_analysis(code, language=language, is_safe=is_safe)
        if output is None:
            if teacher._is_available():
                logger.warning("%s: generation returned None (attempt %d)", sample_id, attempt + 1)
                continue
            else:
                # Teacher unavailable — skip gracefully
                sample["teacher_output"] = None
                sample["teacher_tokens"] = 0
                sample["validation_passed"] = False
                sample["validation_errors"] = ["Teacher API unavailable"]
                return sample

        # Validate
        result = validate_analysis(output, code_snippet=code, language=language)
        if result["fixed_output"]:
            output = result["fixed_output"]

        sample["teacher_output"] = output
        sample["teacher_tokens"] = len(output) // 4 if output else 0
        sample["validation_passed"] = result["passed"]
        sample["validation_errors"] = result["errors"]
        sample["validation_warnings"] = result.get("warnings", [])

        if result["passed"]:
            return sample

        logger.warning("%s: validation failed — %s", sample_id, "; ".join(result["errors"]))

    logger.error("%s: exhausted %d retries, dropping sample", sample_id, max_retries + 1)
    return None


def convert_to_conversation(sample: Dict) -> Dict:
    """Convert a processed sample to OpenRLHF conversation format.

    Args:
        sample: Sample dict with teacher_output, language, vulnerable_code fields.

    Returns:
        Dict in OpenRLHF conversation format:
        {"conversations": [{"from": "human", "value": "..."}, {"from": "gpt", "value": "..."}]}
    """
    language = sample.get("language", "")
    code = sample.get("vulnerable_code") or sample.get("code_snippet", "")
    teacher_output = sample.get("teacher_output", "")
    is_safe = sample.get("is_safe", False)

    if is_safe:
        human_value = (
            f"请分析以下{language}代码为何是安全的：\n"
            f"```{language}\n{code}\n```"
        )
    else:
        human_value = (
            f"请分析以下{language}代码是否存在安全漏洞：\n"
            f"```{language}\n{code}\n```"
        )

    return {
        "conversations": [
            {"from": "human", "value": human_value},
            {"from": "gpt", "value": teacher_output},
        ]
    }


def save_as_jsonl(data: List[Dict], file_path: str):
    """Save a list of dicts as a JSONL file (one JSON object per line)."""
    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    logger.info("Saved %d records to %s", len(data), file_path)


def split_dataset(data: List[Dict], val_split: float = 0.1, seed: int = 42) -> tuple:
    """Shuffle and split data into train and validation sets."""
    rng = random.Random(seed)
    shuffled = list(data)
    rng.shuffle(shuffled)
    split_idx = int(len(shuffled) * (1 - val_split))
    return shuffled[:split_idx], shuffled[split_idx:]


def run_distillation(
    input_path: str,
    output_dir: str = "data/distil",
    val_split: float = 0.1,
    max_concurrent: int = 5,
    max_samples: Optional[int] = None,
    skip_teacher: bool = False,
) -> Dict[str, str]:
    """Run the full distillation data generation pipeline.

    Args:
        input_path: Path to input JSONL with code samples.
        output_dir: Directory for output files.
        val_split: Fraction of data to use for validation.
        max_concurrent: Max concurrent teacher API calls.
        max_samples: Limit number of samples to process (for testing).
        skip_teacher: If True, skip generation and use existing teacher_output in input.

    Returns:
        Dict with keys "train" and "val" pointing to output file paths.
    """
    from vulndetect.data_pipeline.distil.teacher import TeacherClient
    from vulndetect.data_pipeline.distil.validator import validate_batch

    # 1. Load samples
    samples = load_code_samples(input_path)
    if max_samples and max_samples < len(samples):
        samples = samples[:max_samples]
        logger.info("Limited to %d samples", max_samples)

    if not samples:
        logger.error("No valid samples loaded, aborting")
        sys.exit(1)

    # 2. Generate teacher analyses (unless skipped)
    if not skip_teacher:
        teacher = TeacherClient()
        samples = teacher.generate_batch(samples, max_concurrent=max_concurrent)

        # Validate each generated output (no re-generation here — generate_batch already did it)
        from vulndetect.data_pipeline.distil.validator import validate_analysis

        processed = []
        failed_count = 0
        for sample in samples:
            output = sample.get("teacher_output")
            if output is None:
                failed_count += 1
                continue

            code = sample.get("vulnerable_code") or sample.get("code_snippet", "")
            language = sample.get("language", "")
            result = validate_analysis(output, code_snippet=code, language=language)

            if result["fixed_output"]:
                sample["teacher_output"] = result["fixed_output"]
                sample["teacher_output_original"] = output

            sample["validation_passed"] = result["passed"]
            sample["validation_errors"] = result["errors"]
            sample["validation_warnings"] = result.get("warnings", [])

            if result["passed"]:
                processed.append(sample)
            else:
                # Retry once if validation failed
                retry_output = teacher.generate_analysis(code, language=language, is_safe=sample.get("is_safe", False))
                if retry_output:
                    retry_result = validate_analysis(retry_output, code_snippet=code, language=language)
                    if retry_result["passed"]:
                        sample["teacher_output"] = retry_output
                        sample["validation_passed"] = True
                        sample["validation_errors"] = []
                        sample["validation_warnings"] = retry_result.get("warnings", [])
                        processed.append(sample)
                    else:
                        failed_count += 1
                else:
                    failed_count += 1

        logger.info("Generation complete: %d valid, %d failed",
                     len(processed), failed_count)
        samples = processed
    else:
        logger.info("Skipping teacher generation (--skip-teacher), using existing outputs")
        # Still validate existing outputs
        for sample in samples:
            from vulndetect.data_pipeline.distil.validator import validate_analysis
            code = sample.get("vulnerable_code") or sample.get("code_snippet", "")
            result = validate_analysis(
                sample.get("teacher_output", ""),
                code_snippet=code,
                language=sample.get("language", ""),
            )
            sample["validation_passed"] = result["passed"]
            sample["validation_errors"] = result["errors"]
            sample["validation_warnings"] = result.get("warnings", [])

        # Filter out invalid
        passed = [s for s in samples if s.get("validation_passed")]
        logger.info("Validation: %d/%d passed (skip-teacher mode)", len(passed), len(samples))
        samples = passed

    if not samples:
        logger.error("No samples survived processing, aborting")
        sys.exit(1)

    # 3. Batch validation stats
    stats = validate_batch(samples)
    logger.info("Batch stats: %s", json.dumps(stats, indent=2))

    # 4. Convert to conversation format
    conversations = [convert_to_conversation(s) for s in samples]
    logger.info("Converted %d samples to conversation format", len(conversations))

    # 5. Split and save
    train_data, val_data = split_dataset(conversations, val_split=val_split)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    train_path = output_path / "distil_train.jsonl"
    val_path = output_path / "distil_val.jsonl"
    save_as_jsonl(train_data, str(train_path))
    save_as_jsonl(val_data, str(val_path))

    # Save generation report
    report = {
        "input_path": input_path,
        "total_samples": len(samples),
        "train_samples": len(train_data),
        "val_samples": len(val_data),
        "validation_stats": stats,
    }
    report_path = output_path / "generation_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info("Distillation complete: %d train, %d val", len(train_data), len(val_data))
    return {"train": str(train_path), "val": str(val_path)}


def main():
    parser = argparse.ArgumentParser(
        description="Distillation data generation pipeline — "
                    "generate security audit training data via teacher model",
    )
    parser.add_argument(
        "--input", type=str, required=True,
        help="Path to input JSONL file with code samples",
    )
    parser.add_argument(
        "--output-dir", type=str, default="data/distil",
        help="Output directory for generated data (default: data/distil)",
    )
    parser.add_argument(
        "--val-split", type=float, default=0.1,
        help="Fraction of data for validation (default: 0.1)",
    )
    parser.add_argument(
        "--max-concurrent", type=int, default=5,
        help="Maximum concurrent teacher API calls (default: 5)",
    )
    parser.add_argument(
        "--max-samples", type=int, default=None,
        help="Limit number of samples to process (for testing)",
    )
    parser.add_argument(
        "--skip-teacher", action="store_true",
        help="Skip teacher generation and use existing teacher_output in input",
    )

    args = parser.parse_args()
    result = run_distillation(
        input_path=args.input,
        output_dir=args.output_dir,
        val_split=args.val_split,
        max_concurrent=args.max_concurrent,
        max_samples=args.max_samples,
        skip_teacher=args.skip_teacher,
    )
    print(f"Train: {result['train']}")
    print(f"Val:   {result['val']}")


if __name__ == "__main__":
    main()
