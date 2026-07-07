# vulndetect/data_pipeline/distil/collectors/reef_importer.py
"""REEF dataset importer — converts REEF JSONL to VulnDetect internal format.

REEF (Real-world vulnErabilities and Fixes) dataset from ASE 2023:
  https://github.com/ASE-REEF/REEF-data

Each REEF sample contains:
  - cve_id, CWEs, cvss, language, LLM_message, origin_message
  - details[].patch (unified diff), details[].raw_code (full file after fix)

This module converts REEF data to the format expected by our SFT pipeline:
  {cve_id, description, severity, language, code_snippet, fix, cwe_ids}

Usage:
    python -m vulndetect.data_pipeline.distil.collectors.reef_importer \\
        --reef-dir ~/coding/REEF-data/data \\
        --output data/reef/reef_cleaned.jsonl
"""
import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def cvss_to_severity(cvss_str: str) -> str:
    """Map CVSS numeric score to severity level."""
    try:
        score = float(cvss_str)
    except (ValueError, TypeError):
        return "MEDIUM"
    if score >= 9.0:
        return "CRITICAL"
    elif score >= 7.0:
        return "HIGH"
    elif score >= 4.0:
        return "MEDIUM"
    else:
        return "LOW"


def load_reef_samples(reef_dir: str) -> List[Dict]:
    """Load all REEF JSONL files from a directory."""
    data_dir = Path(reef_dir)
    samples = []
    for jsonl_path in sorted(data_dir.glob("*.jsonl")):
        with open(jsonl_path, "r", encoding="utf-8") as f:
            count = 0
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    samples.append(json.loads(line))
                    count += 1
                except json.JSONDecodeError:
                    logger.warning("Skipping invalid JSON in %s", jsonl_path.name)
        logger.info("Loaded %d samples from %s", count, jsonl_path.name)
    return samples


def should_filter(sample: Dict) -> Optional[str]:
    """Check if a REEF sample should be filtered out. Returns reason or None."""
    # Filter: no patch details (truly unusable)
    details = sample.get("details", [])
    if not details:
        return "no patch details"

    # Filter: patch is empty
    if all(not d.get("patch", "").strip() for d in details):
        return "empty patch"

    return None


def extract_first_patch(details: List[Dict]) -> Dict:
    """Extract the first file's patch from details list.

    For multi-file vulnerabilities, we take only the first file to keep
    the data format simple (single code_snippet + single fix).
    """
    if not details:
        return {"patch": "", "raw_code": ""}
    d = details[0]
    return {
        "patch": d.get("patch", ""),
        "raw_code": d.get("raw_code", ""),
    }


def convert_sample(sample: Dict) -> Dict:
    """Convert a single REEF sample to VulnDetect internal format."""
    details = extract_first_patch(sample.get("details", []))

    # Build a descriptive text from the best available source
    # Priority: LLM_message > origin_message (commit msg)
    description = sample.get("LLM_message", "") or sample.get("origin_message", "")

    cwes = sample.get("CWEs", [])
    needs_cwe = "NVD-CWE-noinfo" in cwes

    return {
        "cve_id": sample.get("cve_id", ""),
        "description": description,
        "severity": cvss_to_severity(sample.get("cvss", "")),
        "cvss_score": sample.get("cvss", ""),
        "language": sample.get("language", ""),
        "cwe_ids": [c for c in cwes if c != "NVD-CWE-noinfo"],
        "primary_cwe": next((c for c in cwes if c != "NVD-CWE-noinfo"), "UNKNOWN"),
        "needs_cwe_classification": needs_cwe,  # Flag for Claude to classify
        "code_snippet": details["raw_code"],
        "fix": details["patch"],
        "origin_message": sample.get("origin_message", ""),
        "html_url": sample.get("html_url", ""),
        "_source": "REEF",
        "_reef_index": sample.get("index", -1),
        "_is_multi_file": len(sample.get("details", [])) > 1,
    }


def import_reef(
    reef_dir: str,
    output_path: str,
    max_samples: Optional[int] = None,
) -> Dict:
    """Import and clean REEF dataset.

    Args:
        reef_dir: Path to directory containing REEF JSONL files.
        output_path: Path to write the cleaned JSONL output.
        min_cvss: Minimum CVSS score to keep (default 4.0 = MEDIUM+).
        min_msg_length: Minimum LLM_message length to keep (default 200 chars).
        max_samples: Limit output size (for testing).

    Returns:
        Stats dict with counts of total, filtered, kept, by reason.
    """
    samples = load_reef_samples(reef_dir)
    stats = {
        "total_loaded": len(samples),
        "kept": 0,
        "filtered": 0,
        "filter_reasons": {},
        "cwe_count": 0,
        "language_dist": {},
    }

    kept_samples = []
    for sample in samples:
        reason = should_filter(sample)
        if reason:
            stats["filtered"] += 1
            stats["filter_reasons"][reason] = stats["filter_reasons"].get(reason, 0) + 1
            continue

        converted = convert_sample(sample)
        kept_samples.append(converted)
        stats["kept"] += 1

        # Track statistics
        stats["language_dist"][converted["language"]] = (
            stats["language_dist"].get(converted["language"], 0) + 1
        )

        if max_samples and stats["kept"] >= max_samples:
            break

    # Count unique CWEs
    all_cwes = set()
    for s in kept_samples:
        all_cwes.update(s["cwe_ids"])
    stats["cwe_count"] = len(all_cwes)

    # Write output
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        for sample in kept_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    logger.info("=" * 50)
    logger.info("REEF Import Summary")
    logger.info("=" * 50)
    logger.info("  Loaded:  %d", stats["total_loaded"])
    logger.info("  Kept:    %d", stats["kept"])
    logger.info("  Filtered: %d", stats["filtered"])
    for reason, count in sorted(stats["filter_reasons"].items()):
        logger.info("    - %s: %d", reason, count)
    logger.info("  Unique CWEs: %d", stats["cwe_count"])
    logger.info("  Languages: %s", stats["language_dist"])
    logger.info("  Output: %s", output_path)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Import and clean REEF vulnerability dataset"
    )
    parser.add_argument(
        "--reef-dir", type=str,
        default=str(Path.home() / "coding/REEF-data/data"),
        help="Path to REEF data directory (default: ~/coding/REEF-data/data)",
    )
    parser.add_argument(
        "--output", type=str, default="data/reef/reef_cleaned.jsonl",
        help="Output path for cleaned JSONL (default: data/reef/reef_cleaned.jsonl)",
    )
    parser.add_argument(
        "--max-samples", type=int, default=None,
        help="Limit output samples (for testing)",
    )

    args = parser.parse_args()
    import_reef(
        reef_dir=args.reef_dir,
        output_path=args.output,
        max_samples=args.max_samples,
    )


if __name__ == "__main__":
    main()
