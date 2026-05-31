"""
SQLAlchemy модели для работы с PostgreSQL.
"""

import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import (
    create_engine, Column, String, Text, DateTime,
    ForeignKey, Integer, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

Base = declarative_base()


def get_engine():
    user = os.getenv("POSTGRES_USER", "fstek_admin")
    password = os.getenv("POSTGRES_PASSWORD", "")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5434")
    db = os.getenv("POSTGRES_DB", "fstek_attestation")
    url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url, echo=False)


def get_session():
    return sessionmaker(bind=get_engine())()


class System(Base):
    __tablename__ = "systems"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(500), nullable=False)
    classification_level = Column(String(50), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    components = relationship("SystemComponent", back_populates="system", cascade="all, delete-orphan")


class SystemComponent(Base):
    __tablename__ = "system_components"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_id = Column(UUID(as_uuid=True), ForeignKey("systems.id", ondelete="CASCADE"))
    component_name = Column(String(300), nullable=False)
    component_type = Column(String(100))
    certificate_number = Column(String(200))
    certificate_valid_until = Column(DateTime)
    current_configuration = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    system = relationship("System", back_populates="components")


class NPARequirement(Base):
    __tablename__ = "npa_requirements"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document = Column(String(500), nullable=False)
    paragraph_id = Column(String(50))
    requirement_text = Column(Text, nullable=False)
    class_relevance = Column(JSON)
    extra_meta = Column("metadata", JSON)
    created_at = Column(DateTime, default=datetime.now)


class AuditTrail(Base):
    __tablename__ = "audit_trail"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    system_id = Column(UUID(as_uuid=True), ForeignKey("systems.id", ondelete="CASCADE"))
    requirement_id = Column(UUID(as_uuid=True), ForeignKey("npa_requirements.id", ondelete="CASCADE"))
    component_id = Column(UUID(as_uuid=True), ForeignKey("system_components.id", ondelete="CASCADE"))
    iteration = Column(Integer, default=1)
    status = Column(String(50))
    ai_assessment = Column(JSON)
    ai_recommendation = Column(Text)
    human_decision = Column(String(50))
    human_comment = Column(Text)
    expert_name = Column(String(200))
    final_resolution = Column(Text)
    resolution_evidence = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    system = relationship("System")


def init_db():
    Base.metadata.create_all(get_engine())
    print("✅ Таблицы PostgreSQL созданы")


if __name__ == "__main__":
    init_db()
