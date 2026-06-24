# vulndetect/tests/training/test_datasets.py
import pytest
import json
import tempfile
from pathlib import Path


@pytest.fixture
def sample_conversation_data():
    """创建 OpenRLHF conversation 格式的样本数据"""
    return [
        {
            "conversations": [
                {"from": "human", "value": "这段代码有漏洞吗？\n```python\nimport os\ncmd = input()\nos.system(cmd)\n```"},
                {"from": "gpt", "value": "是的，存在命令注入漏洞。os.system(cmd) 直接执行用户输入的命令，攻击者可以注入任意系统命令。"}
            ]
        }
    ]


def test_load_conversation_dataset(sample_conversation_data):
    """测试加载 conversation 格式数据集"""
    from vulndetect.training.openrlhf_wrapper.datasets import load_conversation_dataset

    with tempfile.TemporaryDirectory() as tmpdir:
        data_file = Path(tmpdir) / "train.jsonl"
        with open(data_file, "w") as f:
            for item in sample_conversation_data:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        dataset = load_conversation_dataset(str(data_file))
        assert len(dataset) == 1
        assert "conversations" in dataset[0]


def test_format_for_sft(sample_conversation_data):
    """测试 SFT 格式转换：conversation -> prompt + response"""
    from vulndetect.training.openrlhf_wrapper.datasets import format_for_sft

    formatted = format_for_sft(sample_conversation_data[0])
    assert "prompt" in formatted
    assert "response" in formatted
    assert "os.system(cmd)" in formatted["prompt"]
    assert "命令注入" in formatted["response"]


def test_format_for_dpo():
    """测试 DPO 格式转换：需要 chosen 和 rejected"""
    from vulndetect.training.openrlhf_wrapper.datasets import format_for_dpo

    dpo_item = {
        "conversations": [
            {"from": "human", "value": "问题"}
        ],
        "chosen": {"from": "gpt", "value": "好的回答"},
        "rejected": {"from": "gpt", "value": "差的回答"}
    }
    formatted = format_for_dpo(dpo_item)
    assert "prompt" in formatted
    assert "chosen" in formatted
    assert "rejected" in formatted
