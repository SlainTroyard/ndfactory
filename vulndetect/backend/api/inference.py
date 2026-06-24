"""Model inference API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path

router = APIRouter(prefix="/api/inference", tags=["inference"])


class ChatRequest(BaseModel):
    checkpoint_path: str
    prompt: str
    max_new_tokens: int = 512
    temperature: float = 0.7


class ChatResponse(BaseModel):
    text: str
    checkpoint: str


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        return ChatResponse(
            text=f"[Inference from {req.checkpoint_path}] Response to: {req.prompt[:100]}...",
            checkpoint=req.checkpoint_path,
        )
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
