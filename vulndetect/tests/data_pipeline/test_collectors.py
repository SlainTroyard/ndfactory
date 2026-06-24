import pytest

def test_dedup_removes_duplicates():
    from vulndetect.data_pipeline.cleaners.dedup import deduplicate
    items = [
        {"cve_id": "CVE-2024-0001", "description": "First vuln"},
        {"cve_id": "CVE-2024-0001", "description": "Duplicate vuln"},
        {"cve_id": "CVE-2024-0002", "description": "Second vuln"},
    ]
    result = deduplicate(items, key="cve_id")
    assert len(result) == 2
    assert result[0]["description"] == "First vuln"

def test_filter_by_severity():
    from vulndetect.data_pipeline.cleaners.dedup import filter_by_severity
    items = [
        {"cve_id": "CVE-HIGH", "severity": "HIGH"},
        {"cve_id": "CVE-MEDIUM", "severity": "MEDIUM"},
        {"cve_id": "CVE-LOW", "severity": "LOW"},
    ]
    result = filter_by_severity(items, min_severity="MEDIUM")
    assert len(result) == 2

def test_formatter():
    from vulndetect.data_pipeline.formatters.openrlhf_format import format_vuln_to_conversation
    vuln = {"cve_id": "CVE-2024-1234", "description": "Command injection in X", "severity": "CRITICAL", "code_snippet": "os.system(input)", "fix": "Use subprocess.run"}
    conv = format_vuln_to_conversation(vuln)
    assert "conversations" in conv
    assert conv["conversations"][0]["from"] == "human"
    assert conv["conversations"][1]["from"] == "gpt"
    assert "subprocess.run" in conv["conversations"][1]["value"]

def test_normalizer():
    from vulndetect.data_pipeline.cleaners.normalizer import normalize_text
    assert normalize_text("  <p>Hi</p> extra  ") == "Hi extra"
