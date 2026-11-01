"""
SQLAlchemy Database Model & Connection Engine.
Supports PostgreSQL for production and SQLite for local development/testing.
"""
import json
import os
from typing import Any, Dict, Optional
from sqlalchemy import Column, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class ProjectModel(Base):
    """Persistent database model for transcription projects."""

    __tablename__ = "projects"

    project_id = Column(String(64), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    artist = Column(String(255), default="Unknown Artist")
    original_filename = Column(String(255), nullable=False)
    upload_object_key = Column(String(512), nullable=False)
    status = Column(String(32), default="pending", index=True)
    stage = Column(String(64), default="queued", index=True)
    progress_percent = Column(Float, default=0.0)
    created_at = Column(String(64), nullable=False)
    duration_seconds = Column(Float, nullable=True)
    total_notes = Column(Integer, nullable=True)
    tracks_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)


def get_database_url() -> str:
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url

    # Fallback to local SQLite database in storage_data/
    local_dir = os.getenv("LOCAL_STORAGE_DIR", "storage_data")
    os.makedirs(local_dir, exist_ok=True)
    db_path = os.path.join(local_dir, "transcription.db").replace("\\", "/")
    return f"sqlite:///{db_path}"


def get_engine():
    db_url = get_database_url()
    if db_url.startswith("sqlite"):
        return create_engine(db_url, connect_args={"check_same_thread": False})
    return create_engine(db_url, pool_pre_ping=True, pool_size=10, max_overflow=20)


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Auto-create tables
Base.metadata.create_all(bind=engine)

