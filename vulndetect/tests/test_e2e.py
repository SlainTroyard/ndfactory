import pytest

def test_import_all_modules():
    modules = [
        "vulndetect.training.openrlhf_wrapper.datasets",
        "vulndetect.training.config_loader",
        "vulndetect.training.checkpoint",
        "vulndetect.evaluation.harness",
        "vulndetect.evaluation.benchmarks.registry",
        "vulndetect.data_pipeline.cleaners.dedup",
        "vulndetect.data_pipeline.formatters.openrlhf_format",
        "vulndetect.backend.main",
    ]
    # models.py needs optional deps (transformers/peft), test separately
    for m in modules:
        __import__(m)

def test_import_models_module():
    pytest.importorskip("transformers", reason="transformers not installed")
    __import__("vulndetect.training.openrlhf_wrapper.models")


def test_config_roundtrip():
    from pathlib import Path
    from vulndetect.training.config_loader import load_config
    config_path = Path(__file__).resolve().parent.parent / "config" / "experiments" / "exp001_sft.yaml"
    cfg = load_config(str(config_path))
    assert cfg["experiment"]["name"] != ""


def test_backend_health():
    from vulndetect.backend.main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
