"""Experiment management business logic"""
from typing import List, Optional
from sqlalchemy.orm import Session
from vulndetect.backend.models.schema import Experiment, Checkpoint, TrainingMetric, Evaluation


def create_experiment(db: Session, name: str, description: str, config_yaml: str) -> Experiment:
    exp = Experiment(name=name, description=description, config_yaml=config_yaml)
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


def list_experiments(db: Session, limit: int = 20) -> List[Experiment]:
    return db.query(Experiment).order_by(Experiment.created_at.desc()).limit(limit).all()


def get_experiment(db: Session, experiment_id: int) -> Optional[Experiment]:
    return db.query(Experiment).filter(Experiment.id == experiment_id).first()


def update_experiment_status(db: Session, experiment_id: int, status: str) -> Optional[Experiment]:
    exp = get_experiment(db, experiment_id)
    if exp:
        exp.status = status
        db.commit()
        db.refresh(exp)
    return exp


def get_experiment_metrics(db: Session, experiment_id: int, limit: int = 2000, stage: str = None) -> List[TrainingMetric]:
    q = db.query(TrainingMetric).filter(TrainingMetric.experiment_id == experiment_id)
    if stage:
        q = q.filter(TrainingMetric.stage == stage)
    return q.order_by(TrainingMetric.step.asc()).limit(limit).all()


def get_experiment_evaluations(db: Session, experiment_id: int) -> List[Evaluation]:
    return db.query(Evaluation).filter(Evaluation.experiment_id == experiment_id).order_by(Evaluation.created_at.desc()).all()
