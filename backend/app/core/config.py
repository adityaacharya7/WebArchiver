"""
Configuration module for Website Archive Submitter & Automated Backup Repository.
"""
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    PROJECT_NAME: str = "Website Archive Submitter & Automated Backup Repository"
    VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Base Directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"

    # Database
    DATABASE_URL: str = Field(
        default=f"sqlite:///{(BASE_DIR / 'data' / 'archiver.db').as_posix()}",
        description="SQLAlchemy database URL (SQLite WAL default, Postgres compatible)"
    )

    # Crawler Settings
    DEFAULT_MAX_CRAWL_DEPTH: int = 3
    DEFAULT_MAX_CRAWL_PAGES: int = 500
    CRAWLER_TIMEOUT_SECONDS: float = 15.0
    CRAWLER_USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 (ArchivalCrawler/1.0)"
    )
    MAX_CONCURRENT_REQUESTS: int = 5

    # Queue & Worker Settings
    WORKER_POOL_SIZE: int = 3
    MAX_WORKERS: int = 5
    WORKER_POLL_INTERVAL: float = 1.0  # seconds between queue polls
    WORKER_LEASE_TIMEOUT_SECONDS: int = 120  # 2 minutes lease before re-queueing
    MAX_SUBMISSION_RETRIES: int = 3
    RETRY_BACKOFF_BASE_SECONDS: int = 10  # 10s, 20s, 40s

    # Archive Services Rate Limits (Requests per minute)
    WAYBACK_RATE_LIMIT_PER_MINUTE: int = 15
    ARCHIVE_TODAY_RATE_LIMIT_PER_MINUTE: int = 6
    GHOSTARCHIVE_RATE_LIMIT_PER_MINUTE: int = 10

    # Submitters configuration
    WAYBACK_SAVE_URL: str = "https://web.archive.org/save/"
    WAYBACK_ACCESS_KEY: str | None = "yIGWzWLyggX2qPYg"
    WAYBACK_SECRET_KEY: str | None = "RiSYyYHrrq6EwbOj"
    ARCHIVE_TODAY_SUBMIT_URL: str = "https://archive.ph/submit/"
    GHOSTARCHIVE_SUBMIT_URL: str = "https://ghostarchive.org/archive"
    DEMO_SIMULATION_MODE: bool = True

    # Playwright / JS rendering (Bonus)
    PLAYWRIGHT_ENABLED: bool = True
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_TIMEOUT_MS: int = 30000

    # Google OAuth 2.0 & Session Security
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    SESSION_SECRET_KEY: str = "orbitronix-super-secure-archival-session-secret-key-32b"
    AUTH_REDIRECT_URI: str | None = None  # Auto-computed if None

    model_config = {
        "env_file": ".env",
        "extra": "allow",
    }


settings = Settings()

# Ensure data directory exists
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
