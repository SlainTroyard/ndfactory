"""Experiment CRUD API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
from vulndetect.backend.database import get_db
from vulndetect.backend.services import experiment_service

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


class ExperimentCreate(BaseModel):
    name: str
    description: str = ""
    config_yaml: str = ""


class ExperimentResponse(BaseModel):
    id: int
    name: str
    description: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[ExperimentResponse])
def list_experiments(db: Session = Depends(get_db)):
    return experiment_service.list_experiments(db)


@router.post("", response_model=ExperimentResponse)
def create_experiment(req: ExperimentCreate, db: Session = Depends(get_db)):
    return experiment_service.create_experiment(db, req.name, req.description, req.config_yaml)


@router.get("/{experiment_id}", response_model=ExperimentResponse)
def get_experiment(experiment_id: int, db: Session = Depends(get_db)):
    exp = experiment_service.get_experiment(db, experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp


@router.post("/{experiment_id}/start")
def start_experiment(experiment_id: int, db: Session = Depends(get_db)):
    exp = experiment_service.update_experiment_status(db, experiment_id, "running")
    if not exp:
        raise HTTPException(status_code=404)
    return {"status": "started", "experiment_id": experiment_id}


@router.post("/{experiment_id}/pause")
def pause_experiment(experiment_id: int, db: Session = Depends(get_db)):
    exp = experiment_service.update_experiment_status(db, experiment_id, "paused")
    if not exp:
        raise HTTPException(status_code=404)
    return {"status": "paused", "experiment_id": experiment_id}


@router.get("/{experiment_id}/metrics")
def get_metrics(experiment_id: int, db: Session = Depends(get_db)):
    metrics = experiment_service.get_experiment_metrics(db, experiment_id)
    return [{"step": m.step, "loss": m.loss, "learning_rate": m.learning_rate, "gpu_memory_mb": m.gpu_memory_mb, "timestamp": str(m.timestamp)} for m in metrics]


@router.get("/{experiment_id}/evaluations")
def get_evaluations(experiment_id: int, db: Session = Depends(get_db)):
    evals = experiment_service.get_experiment_evaluations(db, experiment_id)
    return [{"benchmark": e.benchmark_name, "score": e.score, "checkpoint_step": e.checkpoint_id, "details": e.details_json} for e in evals]
