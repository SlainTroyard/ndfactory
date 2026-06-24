"""Data pipeline: collect -> clean -> format -> split -> save"""
import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from vulndetect.data_pipeline.cleaners.dedup import deduplicate, filter_by_severity
from vulndetect.data_pipeline.cleaners.normalizer import normalize_text
from vulndetect.data_pipeline.formatters.openrlhf_format import (
    format_vuln_to_conversation,
    save_as_jsonl,
)
from vulndetect.training.openrlhf_wrapper.datasets import split_dataset

logging.basicConfig(level=logging.INFO, format="%(message)s")
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


def collect_from_nvd(results_per_page: int = 50, max_pages: int = 3, days_back: int = 30) -> List[Dict]:
    """Collect CVEs from NVD and return normalized items."""
    from vulndetect.data_pipeline.collectors.nvd import fetch_cves, parse_cve
    logger.info("Fetching NVD CVEs (last %d days)...", days_back)
    raw = fetch_cves(results_per_page=results_per_page, max_pages=max_pages, days_back=days_back)
    items = [parse_cve(item) for item in raw]
    items = [i for i in items if i is not None]
    logger.info("NVD: %d CVEs collected", len(items))
    return items


def collect_from_github(token: str = None, max_pages: int = 1) -> List[Dict]:
    """Collect advisories from GitHub and return normalized items."""
    token = token or os.environ.get("GITHUB_TOKEN", "")
    if not token:
        logger.warning("No GitHub token provided, skipping GitHub Advisory collection")
        return []
    from vulndetect.data_pipeline.collectors.github_advisory import fetch_advisories, parse_advisory
    logger.info("Fetching GitHub Advisories...")
    raw = fetch_advisories(token=token, first=50, max_pages=max_pages)
    items = [parse_advisory(item) for item in raw]
    items = [i for i in items if i is not None]
    logger.info("GitHub: %d advisories collected", len(items))
    return items


def main():
    parser = argparse.ArgumentParser(description="VulnDetect data pipeline")
    parser.add_argument("--output-dir", default="data/vulndetect", help="Output directory for processed data")
    parser.add_argument("--nvd-pages", type=int, default=3, help="NVD API pages to fetch (50 per page)")
    parser.add_argument("--days-back", type=int, default=30, help="Days back for NVD CVE filter")
    parser.add_argument("--github-token", default=None, help="GitHub personal access token (or set GITHUB_TOKEN env)")
    parser.add_argument("--github-pages", type=int, default=1, help="GitHub API pages to fetch")
    parser.add_argument("--min-severity", default="MEDIUM", help="Minimum severity: LOW/MEDIUM/HIGH/CRITICAL")
    parser.add_argument("--val-split", type=float, default=0.1, help="Validation split ratio")
    args = parser.parse_args()

    # Collect
    all_items = []
    all_items.extend(collect_from_nvd(results_per_page=50, max_pages=args.nvd_pages, days_back=args.days_back))
    all_items.extend(collect_from_github(token=args.github_token, max_pages=args.github_pages))

    if not all_items:
        logger.error("No data collected! Check API connectivity or provide a GitHub token.")
        sys.exit(1)

    logger.info("Total collected: %d items", len(all_items))

    # Run pipeline
    run_pipeline(
        raw_items=all_items,
        dedup_key="cve_id",
        min_severity=args.min_severity,
        val_split=args.val_split,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
