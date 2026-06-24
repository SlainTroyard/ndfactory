# vulndetect/training/openrlhf_wrapper/datasets.py
"""数据集加载与格式转换——兼容 OpenRLHF conversation 格式"""
import json
from pathlib import Path
from typing import Dict, List


def load_conversation_dataset(file_path: str) -> List[Dict]:
    """从 JSONL 文件加载 conversation 格式数据集"""
    data = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def format_for_sft(item: Dict) -> Dict[str, str]:
    """将 conversation 格式转换为 SFT 的 prompt + response"""
    conversations = item.get("conversations", [])
    human_msgs = [c["value"] for c in conversations if c["from"] == "human"]
    gpt_msgs = [c["value"] for c in conversations if c["from"] == "gpt"]

    prompt = "\n".join(human_msgs)
    response = "\n".join(gpt_msgs)
    return {"prompt": prompt, "response": response}


def format_for_dpo(item: Dict) -> Dict[str, str]:
    """将 conversation 格式转换为 DPO 的 prompt + chosen + rejected"""
    conversations = item.get("conversations", [])
    human_msgs = [c["value"] for c in conversations if c["from"] == "human"]
    prompt = "\n".join(human_msgs)

    chosen = item.get("chosen", {}).get("value", "")
    rejected = item.get("rejected", {}).get("value", "")
    return {"prompt": prompt, "chosen": chosen, "rejected": rejected}


def save_conversation_dataset(data: List[Dict], file_path: str):
    """保存数据集为 JSONL 格式"""
    with open(file_path, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def split_dataset(data: List[Dict], val_split: float = 0.1, seed: int = 42):
    """划分训练集和验证集"""
    import random
    random.seed(seed)
    random.shuffle(data)
    split_idx = int(len(data) * (1 - val_split))
    return data[:split_idx], data[split_idx:]
