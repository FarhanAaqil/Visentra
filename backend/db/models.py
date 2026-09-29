import uuid
import datetime
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Text, Float, Integer, JSON, func, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def _uuid() -> str:
    return str(uuid.uuid4())

def _now() -> datetime.datetime:
    return datetime.datetime.utcnow()

class Contributor(Base):
    __tablename__ = "contributor"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime, default=_now)

    datasets = relationship("Dataset", back_populates="contributor")
    models = relationship("Model", back_populates="contributor")

class Dataset(Base):
    __tablename__ = "dataset"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    contributor_id = Column(UUID(as_uuid=False), ForeignKey("contributor.id"), nullable=False, index=True)
    version = Column(String(64), nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    status = Column(String(32), default="pending", index=True)
    created_at = Column(DateTime, default=_now)

    contributor = relationship("Contributor", back_populates="datasets")
    samples = relationship("DatasetSample", back_populates="dataset")
    findings = relationship("Finding", primaryjoin="and_(Finding.artifact_type=='dataset', foreign(Finding.artifact_id)==Dataset.id)")

class DatasetSample(Base):
    __tablename__ = "dataset_sample"
   

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    dataset_id = Column(UUID(as_uuid=False), ForeignKey("dataset.id"), nullable=False, index=True)
    path = Column(String(512), nullable=False)
    phash = Column(String(64), index=True)
    embedding_ref = Column(String(256))
    flags = Column(JSON, default=list)

    dataset = relationship("Dataset", back_populates="samples")

class Model(Base):
    __tablename__ = "model"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    contributor_id = Column(UUID(as_uuid=False), ForeignKey("contributor.id"), nullable=False, index=True)
    version = Column(String(64), nullable=False)
    framework = Column(String(32), nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    arch_fingerprint = Column(String(256))
    status = Column(String(32), default="pending", index=True)
    created_at = Column(DateTime, default=_now)

    contributor = relationship("Contributor", back_populates="models")
    inferences = relationship("Inference", back_populates="model")
    backdoor_findings = relationship("BackdoorFinding", back_populates="model")

class BackdoorFinding(Base):
    __tablename__ = "backdoor_finding"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    model_id = Column(UUID(as_uuid=False), ForeignKey("model.id"), nullable=False, index=True)
    trigger_type = Column(String(64))
    target_class = Column(Integer)
    consistency_rate = Column(Float)
    anomaly_index = Column(Float)
    cluster_score = Column(Float)
    confidence = Column(Float, index=True)
    evidence_ref = Column(Text)
    created_at = Column(DateTime, default=_now)

    model = relationship("Model", back_populates="backdoor_findings")

class Inference(Base):
    __tablename__ = "inference"
    __table_args__ = (
        Index("ix_inference_model_time", "model_id", "timestamp"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    model_id = Column(UUID(as_uuid=False), ForeignKey("model.id"), nullable=False, index=True)
    input_sha256 = Column(String(64), index=True)
    config_sha256 = Column(String(64))
    output = Column(JSON)
    confidence = Column(Float)
    timestamp = Column(DateTime, default=_now, index=True)
    signature = Column(Text)
    status = Column(String(32), default="ok", index=True)

    model = relationship("Model", back_populates="inferences")

class Finding(Base):
    __tablename__ = "finding"
    __table_args__ = (
        Index("ix_finding_artifact", "artifact_type", "artifact_id"),
        Index("ix_finding_lookup", "artifact_type", "artifact_id", "check_type"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    artifact_type = Column(String(32), nullable=False, index=True)
    artifact_id = Column(UUID(as_uuid=False), nullable=False, index=True)
    check_type = Column(String(64), nullable=False)
    evidence_json = Column(JSON)
    severity = Column(String(16), default="info")
    created_at = Column(DateTime, default=_now, index=True)

class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_artifact_time", "artifact_id", "timestamp"),
    )

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    actor = Column(String(128))
    action = Column(String(64))
    artifact_id = Column(UUID(as_uuid=False), index=True)
    before = Column(JSON)
    after = Column(JSON)
    timestamp = Column(DateTime, default=_now, index=True)
