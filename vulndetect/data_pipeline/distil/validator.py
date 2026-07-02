# vulndetect/data_pipeline/distil/validator.py
"""Quality validation for teacher model generated analysis outputs.

Checks structural completeness, CWE/CVSS format validity, line number
accuracy, and minimum content length.
"""
import re
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Pre-compiled patterns
SECTION_HEADER_RE = re.compile(r"^##\s*\d+\.", re.MULTILINE)
CWE_ID_RE = re.compile(r"CWE-(\d+)")
CWE_FORMAT_RE = re.compile(r"CWE-ID:\s*CWE-\d+")
CVSS_VECTOR_RE = re.compile(r"CVSS:3\.[01]/AV:[NALP](/AC:[LH])?(/PR:[NLH])?(/UI:[NR])?(/S:[UC])?(/C:[NLH])?(/I:[NLH])?(/A:[NLH])?")
LINE_NUM_RE = re.compile(r"\bline\s+(\d+)\b", re.IGNORECASE)
WORD_RE = re.compile(r"\b\w+\b")
EXPECTED_SECTIONS = 7

SECTION_NAMES = [
    "Vulnerability Location|Input Handling",
    "Vulnerability Type|Absence of Common",
    "Root Cause|Data Flow Analysis",
    "Exploit Scenario|Authentication",
    "Severity Assessment|Cryptographic",
    "Fix Recommendation|Error Handling",
    "Prevention|Defense-in-Depth",
]


def _count_sections(text: str) -> int:
    """Count distinct numbered section headers (## 1. ... ## 7. ...)."""
    matches = SECTION_HEADER_RE.findall(text)
    return len(matches)


def _validate_cwe_format(text: str) -> List[str]:
    """Check CWE references are properly formatted. Returns list of errors."""
    errors = []
    cwe_matches = CWE_ID_RE.findall(text)
    if cwe_matches:
        # Check if any CWE reference lacks proper formatting
        if not CWE_FORMAT_RE.search(text):
            errors.append("CWE reference found but not in 'CWE-ID: CWE-XXX' format")
    return errors


def _fix_cwe_format(text: str) -> str:
    """Attempt to fix CWE formatting: 'CWE-89' -> 'CWE-ID: CWE-89'."""
    fixed = text
    for match in CWE_ID_RE.finditer(text):
        cwe_str = match.group(0)
        formatted = f"CWE-ID: {cwe_str}"
        # Only fix standalone CWE references, not already formatted ones
        before = max(0, match.start() - 10)
        if "CWE-ID:" not in text[before:match.start()]:
            fixed = fixed.replace(cwe_str, formatted, 1)
    return fixed


def _validate_cvss_format(text: str) -> List[str]:
    """Check CVSS vector strings are valid. Returns list of errors."""
    errors = []
    if "CVSS" in text and not "CVSS:3" in text:
        # CVSS mentioned but not in 3.x format
        pass  # soft warning only, not a hard error
    return errors


def _validate_line_numbers(text: str, code_snippet: str) -> List[str]:
    """Check referenced line numbers exist within the code snippet. Returns list of errors."""
    errors = []
    max_lines = len(code_snippet.splitlines()) if code_snippet else 0
    if max_lines == 0:
        return errors

    for match in LINE_NUM_RE.finditer(text):
        line_num = int(match.group(1))
        if line_num < 1 or line_num > max_lines:
            errors.append(f"Referenced line {line_num} is out of range (code has {max_lines} lines)")
    return errors


def _count_words(text: str) -> int:
    """Count words in text."""
    return len(WORD_RE.findall(text))


def _check_language_match(text: str, language: str) -> List[str]:
    """Basic heuristic: check for glaring language mismatches in code references."""
    errors = []
    if not language:
        return errors

    lang_lower = language.lower()
    # Check for C-specific patterns in non-C code analysis
    if lang_lower not in ("c", "cpp", "c++"):
        c_patterns = ["buffer overflow", "use-after-free", "dangling pointer", "malloc", "free(",
                       "undefined behavior", "segmentation fault"]
        c_count = sum(1 for p in c_patterns if p in text.lower())
        # Only flag if many C-specific terms appear in non-C analysis
        # (a few generic terms like "buffer overflow" can apply across languages)
        if c_count > 3 and lang_lower in ("python", "javascript", "java", "ruby", "go"):
            errors.append(f"Analysis contains {c_count} C/C++ specific vulnerability terms "
                          f"but code language is '{language}'")
    return errors


def validate_analysis(
    raw_output: str,
    code_snippet: str = "",
    language: str = "",
) -> Dict:
    """Validate a teacher model analysis output against quality criteria.

    Args:
        raw_output: The full text output from the teacher model.
        code_snippet: The original code that was analyzed (for line number checking).
        language: The programming language of the code (for mismatch detection).

    Returns:
        Dict with keys:
            passed: bool — True if all checks pass.
            errors: List[str] — List of error descriptions.
            warnings: List[str] — Non-fatal warnings.
            fixed_output: Optional[str] — Corrected output, or None if no fixes applied.
    """
    errors = []
    warnings = []
    fixed = raw_output

    if not raw_output or not raw_output.strip():
        return {
            "passed": False,
            "errors": ["Empty output from teacher model"],
            "warnings": [],
            "fixed_output": None,
        }

    # 1. Check all 7 sections are present
    section_count = _count_sections(raw_output)
    if section_count < EXPECTED_SECTIONS:
        errors.append(f"Only {section_count}/{EXPECTED_SECTIONS} sections found "
                      f"(expected {EXPECTED_SECTIONS})")

    # 2. Check CWE format
    cwe_errors = _validate_cwe_format(raw_output)
    if cwe_errors:
        fixed = _fix_cwe_format(fixed)
        errors.extend(cwe_errors)

    # 3. Check line number validity
    line_errors = _validate_line_numbers(raw_output, code_snippet)
    errors.extend(line_errors)

    # 4. Check CVSS format
    cvss_errors = _validate_cvss_format(raw_output)
    warnings.extend(cvss_errors)  # CVSS issues are warnings, not hard errors

    # 5. Minimum length check
    word_count = _count_words(raw_output)
    if word_count < 200:
        errors.append(f"Output too short: {word_count} words (minimum 200)")

    # 6. Language match check
    lang_errors = _check_language_match(raw_output, language)
    warnings.extend(lang_errors)

    passed = len(errors) == 0

    if not passed:
        logger.debug("Validation failed: %s", "; ".join(errors))
    if warnings:
        logger.debug("Validation warnings: %s", "; ".join(warnings))

    return {
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
        "fixed_output": fixed if fixed != raw_output else None,
    }


def validate_batch(records: List[Dict]) -> Dict:
    """Validate a batch of teacher outputs and return aggregate statistics.

    Args:
        records: List of dicts, each with at least:
            id: str — unique identifier,
            teacher_output: str — the raw analysis text,
            code_snippet: str — the original code (optional),
            language: str — the programming language (optional).

    Returns:
        Dict with keys:
            total: int,
            passed: int,
            failed: int,
            fixed: int — number of records that had auto-fixes applied,
            error_distribution: Dict[str, int] — error message → count.
    """
    stats = {
        "total": len(records),
        "passed": 0,
        "failed": 0,
        "fixed": 0,
        "error_distribution": {},
    }

    for record in records:
        output = record.get("teacher_output", "")
        code = record.get("code_snippet", record.get("vulnerable_code", ""))
        lang = record.get("language", "")

        result = validate_analysis(output, code_snippet=code, language=lang)

        record["validation_passed"] = result["passed"]
        record["validation_errors"] = result["errors"]
        record["validation_warnings"] = result["warnings"]

        if result["passed"]:
            stats["passed"] += 1
        else:
            stats["failed"] += 1

        if result["fixed_output"]:
            record["teacher_output"] = result["fixed_output"]
            record["teacher_output_original"] = output
            stats["fixed"] += 1

        for error in result["errors"]:
            # Use a simplified key for distribution counting
            key = error.split(":")[0] if ":" in error else error[:60]
            stats["error_distribution"][key] = stats["error_distribution"].get(key, 0) + 1

    pass_rate = stats["passed"] / max(stats["total"], 1) * 100
    logger.info("Validation complete: %d/%d passed (%.1f%%), %d auto-fixed",
                stats["passed"], stats["total"], pass_rate, stats["fixed"])

    return stats
