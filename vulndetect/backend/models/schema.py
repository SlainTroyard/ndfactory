"""SQLAlchemy ORM models"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from vulndetect.backend.database import Base


class Experiment(Base):
    __tablename__ = "experiments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, default="")
    config_yaml = Column(Text, default="")
    status = Column(String(50), default="created")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    checkpoints = relationship("Checkpoint", back_populates="experiment")
    metrics = relationship("TrainingMetric", back_populates="experiment")
    evaluations = relationship("Evaluation", back_populates="experiment")


class Checkpoint(Base):
    __tablename__ = "checkpoints"
    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"))
    step = Column(Integer, nullable=False)
    path = Column(String(512), nullable=False)
    loss = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    experiment = relationship("Experiment", back_populates="checkpoints")
    evaluations = relationship("Evaluation", back_populates="checkpoint")


class TrainingMetric(Base):
    __tablename__ = "training_metrics"
    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"))
    step = Column(Integer, nullable=False)
    loss = Column(Float, nullable=True)
    learning_rate = Column(Float, nullable=True)
    gpu_memory_mb = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    experiment = relationship("Experiment", back_populates="metrics")


class Evaluation(Base):
    __tablename__ = "evaluations"
    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"))
    checkpoint_id = Column(Integer, ForeignKey("checkpoints.id"))
    benchmark_name = Column(String(255), nullable=False)
    score = Column(Float, nullable=False)
    details_json = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    experiment = relationship("Experiment", back_populates="evaluations")
    checkpoint = relationship("Checkpoint", back_populates="evaluations")


class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    source = Column(String(512), default="")
    num_samples = Column(Integer, default=0)
    status = Column(String(50), default="pending")
    last_collected_at = Column(DateTime, nullable=True)
