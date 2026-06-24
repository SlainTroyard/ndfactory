"""Conversation format conversion for OpenRLHF training data"""
import json
import logging
from typing import Dict, List, Any

from vulndetect.data_pipeline.cleaners.normalizer import normalize_text

logger = logging.getLogger(__name__)


def format_vuln_to_conversation(vuln: Dict) -> Dict[str, Any]:
    """Convert a vulnerability dict to OpenRLHF conversation format.

    Produces a JSON object with a "conversations" list containing alternating
    human and gpt messages suitable for SFT training.

    Args:
        vuln: Vulnerability dict with keys: cve_id, description, severity,
              code_snippet (optional), fix (optional).

    Returns:
        Dict in OpenRLHF conversation format:
        {"conversations": [{"from": "human", "value": "..."}, {"from": "gpt", "value": "..."}]}
    """
    cve_id = vuln.get("cve_id", "UNKNOWN")
    description = vuln.get("description", "")
    severity = vuln.get("severity", "UNKNOWN")
    code_snippet = vuln.get("code_snippet", "")
    fix = vuln.get("fix", "")

    # Build human question
    human_parts = [
        f"CVE ID: {cve_id}",
        f"Severity: {severity}",
        f"Description: {description}",
    ]
    if code_snippet:
        human_parts.append(f"Code:\n```\n{code_snippet}\n```")

    human_value = "\n".join(human_parts)
    human_value = normalize_text(human_value)

    # Build GPT answer
    gpt_parts = [f"This vulnerability ({cve_id}) has a severity of {severity}."]
    if fix:
        gpt_parts.append(f"Recommended fix: {fix}")
    else:
        gpt_parts.append("No specific fix provided.")

    gpt_value = "\n".join(gpt_parts)

    return {
        "conversations": [
            {"from": "human", "value": human_value},
            {"from": "gpt", "value": gpt_value},
        ]
    }


def save_as_jsonl(data: List[Dict], file_path: str):
    """Save a list of conversation dicts as a JSONL file.

    Args:
        data: List of dicts in OpenRLHF conversation format.
        file_path: Output file path.
    """
    with open(file_path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    logger.info("Saved %d conversations to %s", len(data), file_path)
