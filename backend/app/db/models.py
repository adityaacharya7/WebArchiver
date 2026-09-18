"""
SQLAlchemy ORM models for Website Archive Submitter & Automated Backup Repository.
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from backend.app.db.database import Base


def utc_now():
    """Return timezone-naive UTC timestamp."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Domain(Base):
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(String(50), default="active", nullable=False)  # active | paused | completed
    created_at = Column(DateTime, default=utc_now, nullable=False)
    last_scan_at = Column(DateTime, nullable=True)
    last_submission_at = Column(DateTime, nullable=True)

    # Relationships
    urls = relationship("Url", back_populates="domain", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="domain", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "domain": self.domain,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_scan_at": self.last_scan_at.isoformat() if self.last_scan_at else None,
            "last_submission_at": self.last_submission_at.isoformat() if self.last_submission_at else None,
        }


class Url(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain_id = Column(Integer, ForeignKey("domains.id", ondelete="CASCADE"), nullable=False, index=True)
    original_url = Column(Text, nullable=False)
    normalized_url = Column(Text, nullable=False)
    url_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256 dedupe key
    discovery_source = Column(String(50), nullable=False)  # html | sitemap | robots | feed | playwright
    discovery_timestamp = Column(DateTime, default=utc_now, nullable=False)
    last_seen = Column(DateTime, default=utc_now, nullable=False)
    http_status = Column(Integer, nullable=True)
    content_hash = Column(String(64), nullable=True)  # SHA-256 of body for change detection
    previous_content_hash = Column(String(64), nullable=True)
    content_changed = Column(Boolean, default=False, nullable=False)
    is_redirect = Column(Boolean, default=False, nullable=False)
    resolved_url = Column(Text, nullable=True)

    # Relationships
    domain = relationship("Domain", back_populates="urls")
    queue_items = relationship("QueueItem", back_populates="url", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="url", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_urls_domain_hash", "domain_id", "url_hash"),
        Index("idx_urls_normalized", "normalized_url"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "domain_id": self.domain_id,
            "domain_name": self.domain.domain if self.domain else None,
            "original_url": self.original_url,
            "normalized_url": self.normalized_url,
            "url_hash": self.url_hash,
            "discovery_source": self.discovery_source,
            "discovery_timestamp": self.discovery_timestamp.isoformat() if self.discovery_timestamp else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "http_status": self.http_status,
            "content_hash": self.content_hash,
            "previous_content_hash": self.previous_content_hash,
            "content_changed": self.content_changed,
            "is_redirect": self.is_redirect,
            "resolved_url": self.resolved_url,
        }


class QueueItem(Base):
    __tablename__ = "queue_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url_id = Column(Integer, ForeignKey("urls.id", ondelete="CASCADE"), nullable=False, index=True)
    service = Column(String(50), nullable=False, index=True)  # wayback | archive_today | ghostarchive
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending | in_progress | done | failed | failed_permanent
    priority = Column(Integer, default=0, nullable=False, index=True)  # higher integer = higher priority
    attempts = Column(Integer, default=0, nullable=False)
    leased_at = Column(DateTime, nullable=True)  # timestamp when worker claimed the item
    created_at = Column(DateTime, default=utc_now, nullable=False)
    last_error = Column(Text, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)

    # Relationships
    url = relationship("Url", back_populates="queue_items")

    __table_args__ = (
        Index("idx_queue_status_priority", "status", "priority", "created_at"),
        Index("idx_queue_lease", "status", "leased_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "url_id": self.url_id,
            "normalized_url": self.url.normalized_url if self.url else None,
            "service": self.service,
            "status": self.status,
            "priority": self.priority,
            "attempts": self.attempts,
            "leased_at": self.leased_at.isoformat() if self.leased_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_error": self.last_error,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
        }


class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url_id = Column(Integer, ForeignKey("urls.id", ondelete="CASCADE"), nullable=False, index=True)
    service = Column(String(50), nullable=False, index=True)  # wayback | archive_today | ghostarchive
    submitted_at = Column(DateTime, default=utc_now, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, index=True)  # success | failed
    archive_url = Column(Text, nullable=True)  # e.g., https://web.archive.org/web/2026...
    archive_id = Column(String(255), nullable=True)  # archive timestamp or ID
    http_status = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    last_attempted = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    url = relationship("Url", back_populates="submissions")

    __table_args__ = (
        Index("idx_submissions_url_service", "url_id", "service"),
        Index("idx_submissions_service_status", "service", "status"),
        Index("idx_submissions_submitted_at", "submitted_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "url_id": self.url_id,
            "normalized_url": self.url.normalized_url if self.url else None,
            "service": self.service,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "archive_url": self.archive_url,
            "archive_id": self.archive_id,
            "http_status": self.http_status,
            "error_message": self.error_message,
            "last_attempted": self.last_attempted.isoformat() if self.last_attempted else None,
        }


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    domain_id = Column(Integer, ForeignKey("domains.id", ondelete="CASCADE"), nullable=False, index=True)
    interval_minutes = Column(Integer, default=1440, nullable=False)  # default: 24h
    is_active = Column(Boolean, default=True, nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    domain = relationship("Domain", back_populates="schedules")

    def to_dict(self):
        return {
            "id": self.id,
            "domain_id": self.domain_id,
            "domain_name": self.domain.domain if self.domain else None,
            "interval_minutes": self.interval_minutes,
            "is_active": self.is_active,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
