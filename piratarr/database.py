"""Database models and session management using SQLite via SQLAlchemy."""

import os
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class Config(Base):
    """Application configuration stored in the database."""

    __tablename__ = "config"

    id = Column(Integer, primary_key=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)

    def __repr__(self):
        return f"<Config {self.key}={self.value}>"


class TranslationJob(Base):
    """Tracks subtitle translation jobs."""

    __tablename__ = "translation_jobs"

    id = Column(Integer, primary_key=True)
    media_title = Column(String(500), nullable=False)
    media_type = Column(String(20), nullable=False)  # "movie" or "episode"
    source_path = Column(Text, nullable=False)
    output_path = Column(Text, nullable=True)
    status = Column(
        Enum("pending", "processing", "completed", "failed", name="job_status"),
        default="pending",
        nullable=False,
    )
    error_message = Column(Text, nullable=True)
    subtitle_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<TranslationJob {self.id} {self.media_title} [{self.status}]>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "media_title": self.media_title,
            "media_type": self.media_type,
            "source_path": self.source_path,
            "output_path": self.output_path,
            "status": self.status,
            "error_message": self.error_message,
            "subtitle_count": self.subtitle_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class MediaCache(Base):
    """Cache of known media items from Sonarr/Radarr."""

    __tablename__ = "media_cache"

    id = Column(Integer, primary_key=True)
    arr_id = Column(Integer, nullable=False)
    title = Column(String(500), nullable=False)
    media_type = Column(String(20), nullable=False)
    path = Column(Text, nullable=False)
    has_subtitle = Column(Boolean, default=False)
    has_pirate_subtitle = Column(Boolean, default=False)
    last_scanned = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<MediaCache {self.title} [{self.media_type}]>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "arr_id": self.arr_id,
            "title": self.title,
            "media_type": self.media_type,
            "path": self.path,
            "has_subtitle": self.has_subtitle,
            "has_pirate_subtitle": self.has_pirate_subtitle,
            "last_scanned": self.last_scanned.isoformat() if self.last_scanned else None,
        }


# Database engine and session factory
_engine = None
_SessionFactory = None


def init_db(db_path: str | None = None) -> None:
    """Initialize the database engine and create tables.

    Args:
        db_path: Path to the SQLite database file. Defaults to /config/piratarr.db.
    """
    global _engine, _SessionFactory

    if db_path is None:
        config_dir = os.environ.get("PIRATARR_CONFIG_DIR", "/config")
        os.makedirs(config_dir, exist_ok=True)
        db_path = os.path.join(config_dir, "piratarr.db")

    _engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(_engine)
    _SessionFactory = sessionmaker(bind=_engine)


def get_session() -> Session:
    """Get a new database session."""
    if _SessionFactory is None:
        init_db()
    return _SessionFactory()


def get_config(key: str, default: str | None = None) -> str | None:
    """Get a configuration value from the database."""
    session = get_session()
    try:
        config = session.query(Config).filter_by(key=key).first()
        return config.value if config else default
    finally:
        session.close()


def set_config(key: str, value: str | None) -> None:
    """Set a configuration value in the database."""
    session = get_session()
    try:
        config = session.query(Config).filter_by(key=key).first()
        if config:
            config.value = value
        else:
            config = Config(key=key, value=value)
            session.add(config)
        session.commit()
    finally:
        session.close()
