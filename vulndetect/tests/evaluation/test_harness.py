import pytest

def test_build_eval_command():
    from vulndetect.evaluation.harness import build_eval_command
    cmd = build_eval_command(
        model_path="experiments/exp001/checkpoints/checkpoint-200",
        benchmarks=["vulnbench", "seceval"],
        output_dir="/tmp/eval_output",
    )
    assert "lm_eval" in cmd[0]
    assert "--model" in cmd
    assert "/tmp/eval_output" in " ".join(cmd)

def test_parse_eval_results():
    from vulndetect.evaluation.harness import parse_eval_results
    sample_output = """
    |  Groups  |Version|Filter|n-shot|Metric|   |Value |   |Stderr|
    |----------|------:|------|------|------|---|-----:|---|-----:|
    |vulnbench | 1.0   |none  | 0    |acc   |...|0.7654|...|0.0123|
    |seceval   | 1.0   |none  | 0    |acc   |...|0.8210|...|0.0098|
    """
    results = parse_eval_results(sample_output)
    assert len(results) == 2
    assert results["vulnbench"]["score"] == 0.7654
    assert results["seceval"]["score"] == 0.8210
