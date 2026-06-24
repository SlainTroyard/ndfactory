"""Deduplication and severity filtering for vulnerability data"""
import logging
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def deduplicate(items: List[Dict], key: str = "cve_id") -> List[Dict]:
    """Remove duplicate items based on a key field.

    Preserves the first occurrence of each key value.

    Args:
        items: List of vulnerability dicts.
        key: Field name to use for deduplication.

    Returns:
        Deduplicated list.
    """
    seen = set()
    result = []
    for item in items:
        val = item.get(key)
        if val not in seen:
            seen.add(val)
            result.append(item)
    logger.info("Dedup: %d items -> %d items (key=%s)", len(items), len(result), key)
    return result


def filter_by_severity(
    items: List[Dict], min_severity: str = "MEDIUM"
) -> List[Dict]:
    """Filter items to only include those at or above a minimum severity level.

    Severity hierarchy: LOW < MEDIUM < HIGH < CRITICAL.
    Items with unknown severity are included if min_severity is LOW or MEDIUM.

    Args:
        items: List of vulnerability dicts with a 'severity' field.
        min_severity: Minimum severity threshold (LOW, MEDIUM, HIGH, CRITICAL).

    Returns:
        Filtered list.
    """
    min_idx = SEVERITY_ORDER.index(min_severity.upper()) if min_severity.upper() in SEVERITY_ORDER else 0

    result = []
    for item in items:
        severity = item.get("severity", "LOW").upper()
        if severity in SEVERITY_ORDER:
            severity_idx = SEVERITY_ORDER.index(severity)
        else:
            severity_idx = 0  # Unknown defaults to LOW

        if severity_idx >= min_idx:
            result.append(item)

    return result
