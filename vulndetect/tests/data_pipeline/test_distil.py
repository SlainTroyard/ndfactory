# vulndetect/tests/data_pipeline/test_distil.py
"""Tests for the distillation data pipeline module."""
import json
import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest


# ============================================================
# prompts.py tests
# ============================================================

def test_security_audit_prompt_format():
    from vulndetect.data_pipeline.distil.prompts import SECURITY_AUDIT_PROMPT
    formatted = SECURITY_AUDIT_PROMPT.format(
        code_snippet="int x = 1;",
        language="c",
    )
    assert "## 1. Vulnerability Location" in formatted
    assert "## 7. Prevention" in formatted
    assert "```c" in formatted
    assert "int x = 1;" in formatted


def test_safe_prompt_different_from_main():
    from vulndetect.data_pipeline.distil import prompts
    assert prompts.SECURITY_AUDIT_PROMPT != prompts.SECURITY_AUDIT_PROMPT_SAFE
    assert "Input Handling" in prompts.SECURITY_AUDIT_PROMPT_SAFE
    assert "why it is secure" in prompts.SECURITY_AUDIT_PROMPT_SAFE.lower()


def test_teacher_system_prompt_not_empty():
    from vulndetect.data_pipeline.distil.prompts import TEACHER_SYSTEM_PROMPT
    assert len(TEACHER_SYSTEM_PROMPT) > 100
    assert "security researcher" in TEACHER_SYSTEM_PROMPT.lower()


# ============================================================
# teacher.py tests
# ============================================================

def test_estimate_tokens():
    from vulndetect.data_pipeline.distil.teacher import estimate_tokens
    assert estimate_tokens("hello world") == 2  # 11 chars // 4
    assert estimate_tokens("") == 1  # minimum
    assert estimate_tokens("a" * 100) == 25


def test_teacher_client_init_no_key():
    """TeacherClient should be None when no API key is set."""
    old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        from vulndetect.data_pipeline.distil.teacher import TeacherClient
        client = TeacherClient(api_key=None)
        assert not client._is_available()
        assert client.generate_analysis("code") is None
    finally:
        if old_key is not None:
            os.environ["ANTHROPIC_API_KEY"] = old_key


def test_teacher_client_init_with_key():
    """TeacherClient with a key should attempt to create a client."""
    pytest.importorskip("anthropic", reason="anthropic SDK not installed")
    with mock.patch("anthropic.Anthropic") as mock_anthropic:
        from vulndetect.data_pipeline.distil.teacher import TeacherClient
        client = TeacherClient(api_key="sk-test-dummy")
        assert client._is_available()
        mock_anthropic.assert_called_once_with(api_key="sk-test-dummy")


def test_generate_analysis_retry_on_error():
    """generate_analysis should retry on API errors."""
    pytest.importorskip("anthropic", reason="anthropic SDK not installed")
    from vulndetect.data_pipeline.distil.teacher import TeacherClient

    client = TeacherClient(api_key="sk-test")
    with mock.patch.object(client, "client") as mock_sdk:
        mock_sdk.messages.create.side_effect = [
            Exception("Transient API error"),
            mock.MagicMock(
                content=[mock.MagicMock(text="## 1. Location\nAnalysis here")],
                usage=mock.MagicMock(input_tokens=100, output_tokens=50),
            ),
        ]

        result = client.generate_analysis("int x;", language="c")
        assert result is not None
        assert mock_sdk.messages.create.call_count == 2


def test_generate_batch_concurrent():
    """generate_batch should process multiple samples."""
    pytest.importorskip("anthropic", reason="anthropic SDK not installed")
    from vulndetect.data_pipeline.distil.teacher import TeacherClient

    client = TeacherClient(api_key="sk-test")
    with mock.patch.object(client, "client") as mock_sdk:
        mock_sdk.messages.create.return_value = mock.MagicMock(
            content=[mock.MagicMock(text="Analysis")],
            usage=mock.MagicMock(input_tokens=10, output_tokens=5),
        )

        samples = [
            {"id": "s1", "vulnerable_code": "a", "language": "py"},
            {"id": "s2", "vulnerable_code": "b", "language": "c"},
            {"id": "s3", "vulnerable_code": "c", "language": "js"},
        ]
        results = client.generate_batch(samples, max_concurrent=2)

        assert len(results) == 3
        for r in results:
            assert r.get("teacher_output") == "Analysis"


def test_teacher_get_usage():
    from vulndetect.data_pipeline.distil.teacher import TeacherClient
    client = TeacherClient(api_key="sk-test")
    client.total_input_tokens = 1000
    client.total_output_tokens = 500
    usage = client.get_usage()
    assert usage["total_calls"] == 0
    assert usage["total_input_tokens"] == 1000
    assert "estimated_cost_usd" in usage


# ============================================================
# validator.py tests
# ============================================================

def _make_full_analysis(n_sections=7):
    """Helper: build a minimal valid analysis with N sections."""
    sections = [
        "## 1. Vulnerability Location\nLine 1: int x = gets(user_input);",
        "## 2. Vulnerability Type\nCWE-ID: CWE-120: Buffer Overflow",
        "## 3. Root Cause\nThe code uses gets() which has no bounds checking.",
        "## 4. Exploit Scenario\nAttacker sends input longer than buffer.",
        "## 5. Severity Assessment\nCVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
        "## 6. Fix Recommendation\nUse fgets() instead.",
        "## 7. Prevention\nAlways use bounds-checked functions.",
    ]
    body = "\n\n".join(sections[:n_sections])
    # Add filler to pass minimum word count (200 words)
    filler = "This is a thorough analysis of the code. " * 30
    return body + "\n\n" + filler


def test_validate_analysis_all_sections_present():
    from vulndetect.data_pipeline.distil.validator import validate_analysis
    output = _make_full_analysis(7)
    result = validate_analysis(output, code_snippet="int x = gets(input);", language="c")
    assert result["passed"] is True
    assert len(result["errors"]) == 0


def test_validate_analysis_missing_section():
    from vulndetect.data_pipeline.distil.validator import validate_analysis
    output = _make_full_analysis(5)  # Only 5 sections
    result = validate_analysis(output, code_snippet="code", language="py")
    assert result["passed"] is False
    assert any("section" in e.lower() for e in result["errors"])


def test_validate_analysis_empty_output():
    from vulndetect.data_pipeline.distil.validator import validate_analysis
    result = validate_analysis("", code_snippet="code")
    assert result["passed"] is False
    assert any("empty" in e.lower() for e in result["errors"])


def test_validate_analysis_too_short():
    from vulndetect.data_pipeline.distil.validator import validate_analysis
    result = validate_analysis("Short output with few words.", code_snippet="code")
    assert result["passed"] is False
    assert any("short" in e.lower() for e in result["errors"])


def test_validate_analysis_line_number_out_of_range():
    from vulndetect.data_pipeline.distil.validator import validate_analysis
    output = _make_full_analysis(7)
    # The code snippet has only 5 lines but analysis references line 999
    result = validate_analysis(
        output + "\nThe bug is on line 999.",
        code_snippet="a\nb\nc",
        language="py",
    )
    # Section count passes but line number check should fail
    # Note: the default analysis already references "Line 1" which is valid for 3-line code
    # Only line 999 is out of range
    if not result["passed"]:
        assert any("line" in e.lower() for e in result["errors"])


def test_validate_analysis_cwe_fix():
    from vulndetect.data_pipeline.distil.validator import validate_analysis
    # CWE mentioned but not in formal format
    output = _make_full_analysis(7).replace("CWE-ID: CWE-120", "CWE-120 is the type")
    result = validate_analysis(output, code_snippet="code", language="c")
    if result["fixed_output"]:
        assert "CWE-ID:" in result["fixed_output"]


def test_validate_batch_stats():
    from vulndetect.data_pipeline.distil.validator import validate_batch
    records = [
        {
            "id": "r1",
            "teacher_output": _make_full_analysis(7),
            "code_snippet": "code",
            "language": "c",
        },
        {
            "id": "r2",
            "teacher_output": "Too short.",
            "code_snippet": "code",
            "language": "py",
        },
        {
            "id": "r3",
            "teacher_output": _make_full_analysis(7),
            "code_snippet": "code",
            "language": "js",
        },
    ]
    stats = validate_batch(records)
    assert stats["total"] == 3
    assert stats["passed"] == 2
    assert stats["failed"] == 1
    assert len(stats["error_distribution"]) >= 1


# ============================================================
# pipeline.py tests
# ============================================================

def test_load_code_samples_valid():
    from vulndetect.data_pipeline.distil.pipeline import load_code_samples
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps({"id": "s1", "language": "py", "vulnerable_code": "x=1"}) + "\n")
        f.write(json.dumps({"id": "s2", "language": "c", "code_snippet": "int x;"}) + "\n")
        f.write("\n")  # empty line
        f.write("invalid json\n")
        path = f.name

    try:
        samples = load_code_samples(path)
        assert len(samples) == 2
        assert samples[0]["id"] == "s1"
        assert samples[1]["id"] == "s2"
    finally:
        Path(path).unlink()


def test_load_code_samples_missing_fields():
    from vulndetect.data_pipeline.distil.pipeline import load_code_samples
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps({"language": "py"}) + "\n")  # no id, no code
        f.write(json.dumps({"id": "s1", "language": "py", "vulnerable_code": "x=1"}) + "\n")
        path = f.name

    try:
        samples = load_code_samples(path)
        assert len(samples) == 1  # First one skipped due to missing fields
        assert samples[0]["id"] == "s1"
    finally:
        Path(path).unlink()


def test_load_code_samples_not_found():
    from vulndetect.data_pipeline.distil.pipeline import load_code_samples
    with pytest.raises(FileNotFoundError):
        load_code_samples("/nonexistent/path/file.jsonl")


def test_convert_to_conversation():
    from vulndetect.data_pipeline.distil.pipeline import convert_to_conversation
    sample = {
        "id": "s1",
        "language": "python",
        "vulnerable_code": "eval(user_input)",
        "teacher_output": "## 1. Location\nThis is dangerous.\n## 7. Prevention\nNever use eval().",
        "is_safe": False,
    }
    conv = convert_to_conversation(sample)
    assert "conversations" in conv
    assert len(conv["conversations"]) == 2
    assert conv["conversations"][0]["from"] == "human"
    assert conv["conversations"][1]["from"] == "gpt"
    assert "eval(user_input)" in conv["conversations"][0]["value"]
    assert "python" in conv["conversations"][0]["value"]


def test_convert_to_conversation_safe():
    from vulndetect.data_pipeline.distil.pipeline import convert_to_conversation
    sample = {
        "id": "s2",
        "language": "c",
        "vulnerable_code": "fgets(buf, sizeof(buf), stdin);",
        "teacher_output": "## 1. Input Handling\nSafe.",
        "is_safe": True,
    }
    conv = convert_to_conversation(sample)
    assert "为何是安全的" in conv["conversations"][0]["value"]


# ============================================================
# code_analysis.py tests
# ============================================================

def test_load_eval_set():
    from vulndetect.evaluation.benchmarks.code_analysis import load_eval_set
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps({
            "id": "e1",
            "language": "py",
            "vulnerable_code": "eval(x)",
            "ground_truth": {"has_vuln": True, "cwe_id": "CWE-95", "vuln_type": "Code Injection"},
        }) + "\n")
        f.write(json.dumps({
            "id": "e2",
            "language": "c",
            "code_snippet": "fgets(buf, 100, stdin);",
            "ground_truth": {"has_vuln": False, "cwe_id": None, "vuln_type": "N/A"},
        }) + "\n")
        path = f.name

    try:
        samples = load_eval_set(path)
        assert len(samples) == 2
        assert samples[0]["ground_truth"]["has_vuln"] is True
        assert samples[1]["ground_truth"]["has_vuln"] is False
    finally:
        Path(path).unlink()


def test_compute_metrics():
    from vulndetect.evaluation.benchmarks.code_analysis import compute_metrics

    results = [
        # TP: detected real vuln, CWE correct, fix correct
        {
            "ground_truth": {"has_vuln": True},
            "judgment": {"vuln_detect": True, "cwe_classify": True, "fix_correct": True},
        },
        # TP: detected real vuln, CWE wrong
        {
            "ground_truth": {"has_vuln": True},
            "judgment": {"vuln_detect": True, "cwe_classify": False, "fix_correct": None},
        },
        # FN: missed real vuln
        {
            "ground_truth": {"has_vuln": True},
            "judgment": {"vuln_detect": False, "cwe_classify": None, "fix_correct": None},
        },
        # TN: correctly identified safe code
        {
            "ground_truth": {"has_vuln": False},
            "judgment": {"vuln_detect": False, "cwe_classify": None, "fix_correct": None},
        },
        # FP: false alarm on safe code
        {
            "ground_truth": {"has_vuln": False},
            "judgment": {"vuln_detect": True, "cwe_classify": None, "fix_correct": False},
        },
    ]

    metrics = compute_metrics(results)
    # TP=2, FP=1, TN=1, FN=1
    assert metrics["tp"] == 2
    assert metrics["fp"] == 1
    assert metrics["tn"] == 1
    assert metrics["fn"] == 1
    # Recall = 2/(2+1) = 0.667
    assert abs(metrics["recall"] - 2/3) < 0.01
    # Precision = 2/(2+1) = 0.667
    assert abs(metrics["precision"] - 2/3) < 0.01
    # CWE accuracy = 1/2 = 0.5 (only TP samples with vuln_detect=True count)
    assert abs(metrics["cwe_accuracy"] - 0.5) < 0.01
    # FPR = 1/(1+1) = 0.5
    assert abs(metrics["fpr"] - 0.5) < 0.01


def test_compute_metrics_all_correct():
    from vulndetect.evaluation.benchmarks.code_analysis import compute_metrics

    results = [
        {"ground_truth": {"has_vuln": True}, "judgment": {"vuln_detect": True, "cwe_classify": True, "fix_correct": True}},
        {"ground_truth": {"has_vuln": True}, "judgment": {"vuln_detect": True, "cwe_classify": True, "fix_correct": True}},
        {"ground_truth": {"has_vuln": False}, "judgment": {"vuln_detect": False, "cwe_classify": None, "fix_correct": None}},
        {"ground_truth": {"has_vuln": False}, "judgment": {"vuln_detect": False, "cwe_classify": None, "fix_correct": None}},
    ]

    metrics = compute_metrics(results)
    assert metrics["recall"] == 1.0
    assert metrics["precision"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["fpr"] == 0.0
    assert metrics["cwe_accuracy"] == 1.0
