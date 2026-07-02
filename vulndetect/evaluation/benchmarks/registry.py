"""Benchmark registry"""
from typing import Dict

BENCHMARK_REGISTRY: Dict[str, Dict] = {
    "vulnbench": {"task": "vulnbench", "type": "security", "description": "Vulnerability detection benchmark", "metrics": ["accuracy", "f1"]},
    "ctibench": {"task": "ctibench", "type": "security", "description": "CTI reasoning benchmark", "metrics": ["accuracy"]},
    "seceval": {"task": "seceval", "type": "security", "description": "9-domain security eval", "metrics": ["accuracy"]},
    "cybermetric": {"task": "cybermetric_80", "type": "security", "description": "Cyber knowledge MCQs", "metrics": ["accuracy"]},
    "mmlu_compsec": {"task": "mmlu_computer_security", "type": "general", "description": "MMLU computer security subset", "metrics": ["accuracy"]},
    "code_vuln_analysis": {"task": "code_vuln_analysis", "type": "code_security", "description": "Code vulnerability analysis with LLM-as-Judge", "metrics": ["recall", "precision", "f1", "cwe_accuracy", "fix_correctness", "fpr"]},
}

def get_task_name(benchmark_name: str) -> str:
    if benchmark_name in BENCHMARK_REGISTRY:
        return BENCHMARK_REGISTRY[benchmark_name]["task"]
    return benchmark_name

def list_benchmarks(benchmark_type: str = None) -> list:
    if benchmark_type:
        return [name for name, info in BENCHMARK_REGISTRY.items() if info.get("type") == benchmark_type]
    return list(BENCHMARK_REGISTRY.keys())
