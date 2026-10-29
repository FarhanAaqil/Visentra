import datetime
import uuid

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime.datetime:
    """Naive UTC timestamp (SQLite drops tzinfo anyway, so we keep it uniform)."""
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


def iso(ts: datetime.datetime | None) -> str:
    return ts.isoformat(timespec="milliseconds") + "Z" if ts else ""


class Contributor(Base):
    __tablename__ = "contributor"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False, index=True)
    role = Column(String(64), default="ML Engineer")
    created_at = Column(DateTime, default=utcnow)

    datasets = relationship("Dataset", back_populates="contributor")
    models = relationship("Model", back_populates="contributor")


class Dataset(Base):
    __tablename__ = "dataset"

    id = Column(String(36), primary_key=True, default=_uuid)
    contributor_id = Column(String(36), ForeignKey("contributor.id"), nullable=False, index=True)
    version = Column(String(64), nullable=False)
    name = Column(String(255), default="")
    sha256 = Column(String(64), nullable=False, index=True)
    actual_sha256 = Column(String(64))
    merkle_root = Column(String(64))
    sample_count = Column(Integer, default=0)
    status = Column(String(32), default="pending", index=True)
    created_at = Column(DateTime, default=utcnow)
    verified_at = Column(DateTime)

    contributor = relationship("Contributor", back_populates="datasets")
    samples = relationship("DatasetSample", back_populates="dataset", cascade="all, delete-orphan")
    models = relationship("Model", back_populates="dataset")


class DatasetSample(Base):
    __tablename__ = "dataset_sample"

    id = Column(String(36), primary_key=True, default=_uuid)
    dataset_id = Column(String(36), ForeignKey("dataset.id"), nullable=False, index=True)
    path = Column(String(512), nullable=False)
    name = Column(String(255), default="")
    sha256 = Column(String(64), index=True)
    phash = Column(String(64), index=True)
    embedding_ref = Column(String(256))
    flags = Column(JSON, default=list)

    dataset = relationship("Dataset", back_populates="samples")


class Model(Base):
    __tablename__ = "model"

    id = Column(String(36), primary_key=True, default=_uuid)
    contributor_id = Column(String(36), ForeignKey("contributor.id"), nullable=False, index=True)
    dataset_id = Column(String(36), ForeignKey("dataset.id"), index=True)
    version = Column(String(64), nullable=False)
    name = Column(String(255), default="")
    framework = Column(String(32), nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    actual_sha256 = Column(String(64))
    arch_fingerprint = Column(String(256))
    graph_summary = Column(JSON)
    status = Column(String(32), default="pending", index=True)
    created_at = Column(DateTime, default=utcnow)
    verified_at = Column(DateTime)

    contributor = relationship("Contributor", back_populates="models")
    dataset = relationship("Dataset", back_populates="models")
    inferences = relationship("Inference", back_populates="model")
    backdoor_findings = relationship("BackdoorFinding", back_populates="model")


class BackdoorFinding(Base):
    __tablename__ = "backdoor_finding"

    id = Column(String(36), primary_key=True, default=_uuid)
    model_id = Column(String(36), ForeignKey("model.id"), nullable=False, index=True)
    scan_id = Column(String(36), index=True)
    trigger_type = Column(String(64))
    target_class = Column(Integer)
    consistency_rate = Column(Float)
    anomaly_index = Column(Float)
    cluster_score = Column(Float)
    confidence = Column(Float, index=True)
    evidence_ref = Column(Text)
    created_at = Column(DateTime, default=utcnow)

    model = relationship("Model", back_populates="backdoor_findings")


class Inference(Base):
    __tablename__ = "inference"
    __table_args__ = (Index("ix_inference_model_time", "model_id", "timestamp"),)

    id = Column(String(36), primary_key=True, default=_uuid)
    model_id = Column(String(36), ForeignKey("model.id"), nullable=False, index=True)
    model_sha256 = Column(String(64))
    arch_fingerprint = Column(String(256))
    dataset_merkle_root = Column(String(64))
    input_sha256 = Column(String(64), index=True)
    config_sha256 = Column(String(64))
    output = Column(JSON)
    confidence = Column(Float)
    timestamp = Column(DateTime, default=utcnow, index=True)
    signature = Column(Text)
    public_key = Column(String(128))
    status = Column(String(32), default="ok", index=True)

    model = relationship("Model", back_populates="inferences")


class Finding(Base):
    __tablename__ = "finding"
    __table_args__ = (
        Index("ix_finding_artifact", "artifact_type", "artifact_id"),
        Index("ix_finding_lookup", "artifact_type", "artifact_id", "check_type"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    artifact_type = Column(String(32), nullable=False, index=True)
    artifact_id = Column(String(36), nullable=False, index=True)
    check_type = Column(String(64), nullable=False)
    evidence_json = Column(JSON)
    severity = Column(String(16), default="info")
    created_at = Column(DateTime, default=utcnow, index=True)


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_artifact_time", "artifact_id", "timestamp"),)

    id = Column(String(36), primary_key=True, default=_uuid)
    actor = Column(String(128))
    action = Column(String(64), index=True)
    artifact_type = Column(String(32))
    artifact_id = Column(String(36), index=True)
    before = Column(JSON)
    after = Column(JSON)
    timestamp = Column(DateTime, default=utcnow, index=True)
