"""App model for database."""

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.sql import func

from app.db.base import Base


class App(Base):
    """Vision App model."""

    __tablename__ = "apps"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    version = Column(String(50), nullable=True)
    desc = Column(Text, nullable=True)
    framework = Column(String(50), nullable=True)
    compute_capability = Column(String(20), nullable=True)
    platform = Column(String(50), nullable=True)

    # JSON fields for complex data
    models = Column(JSON, nullable=True)  # List of model info
    outputs = Column(JSON, nullable=True)  # List of outputs
    properties = Column(JSON, nullable=True)  # Pipeline config

    # Performance metrics
    app_memory_usage = Column(Float, nullable=True)
    app_max_fps = Column(Float, nullable=True)

    # File paths
    storage_path = Column(String(512), nullable=True)  # Where app files are stored
    cover_path = Column(String(512), nullable=True)  # Cover image path

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    def __repr__(self) -> str:
        return f"<App {self.id}: {self.name}>"
