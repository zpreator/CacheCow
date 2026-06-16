from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings as app_settings
from app.database import Base


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    channels: Mapped[list["Channel"]] = relationship(back_populates="tag")


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    link: Mapped[str] = mapped_column(String(500), nullable=False)
    image: Mapped[str] = mapped_column(String(500), default="")
    subscribe: Mapped[bool] = mapped_column(default=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id"), nullable=False)
    use_global_settings: Mapped[bool] = mapped_column(default=True)
    download_all: Mapped[bool] = mapped_column(default=False)
    max_duration: Mapped[int] = mapped_column(default=60)
    days: Mapped[int] = mapped_column(default=8)
    items: Mapped[int] = mapped_column(default=5)
    include_keywords: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    exclude_keywords: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    tag: Mapped["Tag"] = relationship(back_populates="channels")


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    download_path: Mapped[str] = mapped_column(String(500), default=app_settings.download_path)
    minutes_between_runs: Mapped[int] = mapped_column(default=360)
    random_interval_lower: Mapped[int] = mapped_column(default=15)
    random_interval_upper: Mapped[int] = mapped_column(default=45)
    max_duration: Mapped[int] = mapped_column(default=60)
    days: Mapped[int] = mapped_column(default=8)
    items: Mapped[int] = mapped_column(default=5)
    remove_old_files: Mapped[bool] = mapped_column(default=True)
    clean_threshold: Mapped[int] = mapped_column(default=90)
    # Overrides APP_PASS_HASH env var when set
    password_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    setup_complete: Mapped[bool] = mapped_column(default=False)


class DownloadLog(Base):
    __tablename__ = "download_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[Optional[int]] = mapped_column(ForeignKey("channels.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    videos_downloaded: Mapped[int] = mapped_column(default=0)
    label: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    channel: Mapped[Optional["Channel"]] = relationship()


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    youtube_id: Mapped[str] = mapped_column(String(100), unique=True)
    channel_id: Mapped[Optional[int]] = mapped_column(ForeignKey("channels.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    duration: Mapped[Optional[int]] = mapped_column(nullable=True)
    upload_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(nullable=True)
    uploader: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    downloaded_at: Mapped[datetime] = mapped_column(server_default=func.now())
    download_log_id: Mapped[Optional[int]] = mapped_column(ForeignKey("download_log.id"), nullable=True)

    channel: Mapped[Optional["Channel"]] = relationship()
    download_log: Mapped[Optional["DownloadLog"]] = relationship()


def ensure_defaults(db):
    """Create default tag and settings row if they don't exist."""
    # Run column migrations before any ORM query so SQLAlchemy doesn't SELECT
    # columns that don't exist yet on old databases.
    _add_column_if_missing(db, "settings", "password_hash", "VARCHAR(128)")
    _add_column_if_missing(db, "settings", "username", "VARCHAR(100)")
    _add_column_if_missing(db, "settings", "setup_complete", "BOOLEAN DEFAULT 0")
    _add_column_if_missing(db, "videos", "uploader", "VARCHAR(500)")
    _add_column_if_missing(db, "videos", "download_log_id", "INTEGER")
    _add_column_if_missing(db, "download_log", "label", "VARCHAR(500)")
    db.expire_all()

    if not db.query(Tag).filter(Tag.name == "other").first():
        db.add(Tag(name="other"))
        db.commit()
    if not db.query(Settings).first():
        from app.paths import DEFAULT_DOWNLOAD_DIR
        db.add(Settings(download_path=str(DEFAULT_DOWNLOAD_DIR)))
        db.commit()


def _add_column_if_missing(db, table: str, column: str, col_type: str):
    from sqlalchemy import text
    try:
        result = db.execute(text(f"PRAGMA table_info({table})")).fetchall()
        existing = {row[1] for row in result}
        if column not in existing:
            db.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            db.commit()
            print(f"[MIGRATE] Added column {table}.{column}")
    except Exception as e:
        print(f"[MIGRATE] Failed to add column {table}.{column}: {e}")
        db.rollback()
