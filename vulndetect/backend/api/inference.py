"""Model inference API — loads LoRA checkpoints for real inference"""
import torch
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
from pathlib import Path
from threading import Lock

router = APIRouter(prefix="/api/inference", tags=["inference"])

# 模型缓存：避免每次请求都重新加载
_model_cache: Dict[str, tuple] = {}
_cache_lock = Lock()


class ChatRequest(BaseModel):
    checkpoint_path: str
    prompt: str
    max_new_tokens: int = 512
    temperature: float = 0.7


class ChatResponse(BaseModel):
    text: str
    checkpoint: str


def _load_model(checkpoint_path: str):
    """加载基座模型 + LoRA adapter（带缓存）"""
    with _cache_lock:
        if checkpoint_path in _model_cache:
            return _model_cache[checkpoint_path]

        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import PeftModel

        # QLoRA 基座配置
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )

        model = AutoModelForCausalLM.from_pretrained(
            "Qwen/Qwen2.5-3B-Instruct",
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
        )

        tokenizer = AutoTokenizer.from_pretrained(
            "Qwen/Qwen2.5-3B-Instruct",
            trust_remote_code=True,
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = PeftModel.from_pretrained(model, checkpoint_path)
        model.eval()

        _model_cache[checkpoint_path] = (model, tokenizer)
        # 清掉旧缓存（只保留最新加载的模型，避免显存爆炸）
        for old_path in list(_model_cache.keys()):
            if old_path != checkpoint_path:
                del _model_cache[old_path]
        return model, tokenizer


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not Path(req.checkpoint_path).exists():
        raise HTTPException(status_code=404, detail=f"Checkpoint not found: {req.checkpoint_path}")

    try:
        model, tokenizer = _load_model(req.checkpoint_path)

        messages = [
            {"role": "system", "content": "You are a security vulnerability analysis assistant. Analyze code for vulnerabilities and provide clear, accurate assessments."},
            {"role": "user", "content": req.prompt},
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=req.max_new_tokens,
                temperature=req.temperature,
                do_sample=req.temperature > 0,
                pad_token_id=tokenizer.pad_token_id,
            )

        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        # 去掉 prompt 部分
        if text in response:
            response = response[len(text):].strip()

        return ChatResponse(text=response, checkpoint=req.checkpoint_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checkpoints")
def list_checkpoints(experiment_id: Optional[int] = None):
    checkpoints = []
    exp_dir = Path("experiments")
    if exp_dir.exists():
        for exp in exp_dir.iterdir():
            if exp.is_dir():
                ckpt_dir = exp / "checkpoints"
                if ckpt_dir.exists():
                    for ckpt in sorted(ckpt_dir.iterdir()):
                        if ckpt.is_dir() and ckpt.name.startswith("checkpoint-"):
                            checkpoints.append({
                                "experiment": exp.name,
                                "step": ckpt.name.replace("checkpoint-", ""),
                                "path": str(ckpt),
                            })
    return checkpoints
