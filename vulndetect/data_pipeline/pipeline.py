"""Data pipeline: collect -> clean -> format -> split -> save"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from vulndetect.data_pipeline.cleaners.dedup import deduplicate, filter_by_severity
from vulndetect.data_pipeline.cleaners.normalizer import normalize_text
from vulndetect.data_pipeline.formatters.openrlhf_format import (
    format_vuln_to_conversation,
    save_as_jsonl,
)
from vulndetect.training.openrlhf_wrapper.datasets import split_dataset

logger = logging.getLogger(__name__)


def run_pipeline(
    raw_items: List[Dict],
    dedup_key: str = "cve_id",
    min_severity: str = "MEDIUM",
    val_split: float = 0.1,
    output_dir: str = "data/processed",
    dataset_name: str = "vulndetect",
) -> Dict[str, str]:
    """Run the full data pipeline: collect -> clean -> format -> split -> save.

    Args:
        raw_items: List of raw vulnerability dicts from collectors.
        dedup_key: Field to use for deduplication.
        min_severity: Minimum severity threshold for filtering.
        val_split: Fraction of data to use for validation.
        output_dir: Directory to save processed datasets.
        dataset_name: Base name for output files.

    Returns:
        Dict mapping split names ("train", "val") to their file paths.
    """
    # Step 1: Clean - deduplicate
    items = deduplicate(raw_items, key=dedup_key)
    logger.info("After dedup: %d items", len(items))

    # Step 2: Clean - filter by severity
    items = filter_by_severity(items, min_severity=min_severity)
    logger.info("After severity filter (>=%s): %d items", min_severity, len(items))

    # Step 3: Clean - normalize descriptions
    for item in items:
        if "description" in item:
            item["description"] = normalize_text(item["description"])

    # Step 4: Format to OpenRLHF conversation format
    conversations = [format_vuln_to_conversation(item) for item in items]
    logger.info("Formatted %d items to conversation format", len(conversations))

    # Step 5: Split into train/val
    train_data, val_data = split_dataset(conversations, val_split=val_split)
    logger.info(
        "Split: %d train, %d val (split=%.2f)",
        len(train_data),
        len(val_data),
        val_split,
    )

    # Step 6: Save
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    train_path = str(output_path / f"{dataset_name}_train.jsonl")
    val_path = str(output_path / f"{dataset_name}_val.jsonl")

    save_as_jsonl(train_data, train_path)
    save_as_jsonl(val_data, val_path)

    logger.info("Pipeline complete. Train: %s, Val: %s", train_path, val_path)
    return {"train": train_path, "val": val_path}
