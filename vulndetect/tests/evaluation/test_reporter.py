import pytest
import tempfile
import json
from pathlib import Path

def test_generate_report():
    from vulndetect.evaluation.reporter import generate_report
    with tempfile.TemporaryDirectory() as tmpdir:
        eval_dir = Path(tmpdir) / "evaluations" / "step-200"
        eval_dir.mkdir(parents=True)
        with open(eval_dir / "results.json", "w") as f:
            json.dump({"_meta": {"checkpoint_step": 200}, "vulnbench": {"score": 0.765}, "seceval": {"score": 0.821}}, f)
        report = generate_report(tmpdir)
        assert "Checkpoint 200" in report
        assert "0.7650" in report
