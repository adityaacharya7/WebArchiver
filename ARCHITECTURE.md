# Website Archive Submitter & Automated Backup Repository
## Technical Architecture Documentation

### 1. Architectural Overview

The **Website Archive Submitter & Automated Backup Repository** is an automated, high-throughput pipeline designed for multi-domain website discovery, canonical normalization, persistent queue-based archival submission, and historical preservation repository management.

The system is engineered following modern modular architecture principles, avoiding monolithic coupling and ensuring that every core component can scale independently from small local single-domain crawls to enterprise multi-domain archives with hundreds of thousands of URLs.

```
                                 ┌──────────────────────────────────────────────┐
                                 │               Web Dashboard UI               │
                                 │   (FastAPI Jinja2 + Modern Glassmorphic CSS  │
                                 │      + Real-Time Progress & Interactive      │
                                 │        Search/Filter/Export Console)         │
                                 └──────────────────────┬───────────────────────┘
                                                        │ REST / Polling API
                                                        ▼
                                 ┌──────────────────────────────────────────────┐
                                 │               FastAPI Backend                │
                                 │     (App Lifecycle, Routes & Controllers)    │
                                 └──────────────┬───────────────────────────────┘
                                                │
                 ┌──────────────────────────────┼──────────────────────────────┐
                 ▼                              ▼                              ▼
    ┌────────────────────────┐    ┌───────────────────────────┐   ┌───────────────────────────┐
    │    Discovery Engine    │    │  Normalizer & Deduplicator│   │  Change Detection Engine  │
    │  - Robots.txt parser   │    │  - RFC 3986 Canonicalize │   │  - Content Hashing        │
    │  - Sitemap.xml index   │───▶│  - Query Param Stripping  │──▶│  - Snapshot Comparison    │
    │  - Async HTML BFS      │    │  - SHA-256 URL Hashing    │   │  - Delta Enqueueing       │
    │  - Feed Auto-discovery │    │  - Redirect Resolver      │   │                           │
    │  - Playwright (JS/DOM) │    │                           │   │                           │
    └────────────────────────┘    └───────────────────────────┘   └───────────────────────────┘
                                                │
                                                ▼
                                  ┌───────────────────────────┐
                                  │   SQLite Repository (WAL) │
                                  │   - domains, urls         │
                                  │   - queue_items           │
                                  │   - submissions           │
                                  └─────────────┬─────────────┘
                                                │ Persistent Lease Dequeue
                                                ▼
                                  ┌───────────────────────────┐
                                  │  Queue Worker Pool Engine │
                                  │  - Token-Bucket Limiter   │
                                  │  - Atomic Crash Lease     │
                                  │  - Exponential Backoff    │
                                  └─────────────┬─────────────┘
                                                │
                 ┌──────────────────────────────┼──────────────────────────────┐
                 ▼                              ▼                              ▼
    ┌────────────────────────┐    ┌───────────────────────────┐   ┌───────────────────────────┐
    │   Wayback Submitter    │    │  Archive.today Submitter  │   │  Ghostarchive Submitter   │
    │   (Save Page Now API)  │    │  (Defensive Form POST)    │   │  (Public Web Archive)     │
    └────────────────────────┘    └───────────────────────────┘   └───────────────────────────┘
```

---

### 2. Core Subsystems Breakdown

#### 2.1 URL Discovery Engine (`backend/app/crawler/`)
The Discovery Engine implements the **Strategy Pattern** across multiple discovery vectors:
1. **`RobotsParser` (`robots.py`)**: Fetches `/robots.txt` using async HTTP, extracts `Sitemap:` directives, and isolates disallowed rules.
2. **`SitemapParser` (`sitemap.py`)**: Handles both standard `<urlset>` documents and recursive `<sitemapindex>` files, extracting canonical location tags (`<loc>`).
3. **`HtmlCrawler` (`html_crawler.py`)**: Asynchronous breadth-first search (BFS) crawler utilizing `httpx` and `BeautifulSoup4`. Evaluates outgoing hyperlinks (`<a href>`), canonical declarations (`<link rel="canonical">`), and pagination hints (`<link rel="next">`). Enforces domain boundary restrictions, configurable crawl depth, and maximum page limits.
4. **`FeedParser` (`feeds.py`)**: Autodiscovers RSS 2.0 and Atom feeds linked from document headers and extracts item URLs.
5. **`PlaywrightCrawler` (`playwright_crawler.py`)** *(Bonus Challenge)*: Headless Chromium browser automation executing dynamic JavaScript. Renders client-side single page applications (SPAs) and social page structures (e.g. public Instagram links) without bypassing security or authentication barriers.
6. **`DiscoveryManager` (`discovery_manager.py`)**: Unified coordinator that executes discovery strategies, normalizes discovered URLs, and commits them to the database repository.

#### 2.2 Normalization & Deduplication (`backend/app/normalizer/`)
To guarantee deduplication across re-scans and large datasets:
- **Canonical Scheme & Host**: Lowercases schemes (`http`/`https`) and hostnames.
- **Port Stripping**: Removes standard ports (`:80` for HTTP, `:443` for HTTPS).
- **Fragment Stripping**: Strips URI fragments (`#hash`) from normalized forms while preserving the raw URL in `original_url`.
- **Query Parameter Sorting & Filtering**:
  - Strips tracking tags (`utm_*`, `fbclid`, `gclid`, `_ga`, session identifiers).
  - Alphabetically sorts query parameters (`?b=2&a=1` becomes `?a=1&b=2`).
- **Path Normalization**: Resolves relative segments (`/../`, `/./`) and collapses redundant slashes (`///`).
- **O(1) SHA-256 Hashing**: Generates a 64-character SHA-256 hash (`url_hash`) indexed as a UNIQUE constraint in the repository.

#### 2.3 Persistent Queue & Resilient Worker Pool (`backend/app/queue/`)
- **Database-Backed Queue**: The `queue_items` table acts as the durable persistent queue. No external message broker (RabbitMQ/Redis) is required, eliminating setup overhead while providing ACID guarantees.
- **Atomic Worker Leases & Crash Recovery**:
  - Workers atomically claim batches of pending items, setting `status = 'in_progress'` and `leased_at = NOW()`.
  - If a worker or server crashes mid-job, the `reclaim_expired_leases` function automatically recovers abandoned items whose leases have expired, resetting them to `'pending'`. On system startup, all uncompleted items are safely recovered.
- **Token Bucket Rate Limiting (`rate_limiter.py`)**:
  - Per-service rate limiters enforce compliance with external service terms (e.g. Wayback: 15 req/min, Archive.today: 6 req/min, Ghostarchive: 10 req/min).
- **Exponential Backoff Retry**:
  - Temporary failures (e.g., HTTP 429, timeouts) calculate exponential backoff: `delay = BASE_SECONDS * (2 ^ (attempts - 1))`.
  - Items exceeding maximum attempts transition to `failed_permanent` and remain visible in the dashboard for manual review and retry.

#### 2.4 Multi-Service Archival Integrations (`backend/app/submitters/`)
- **Extensible Base (`base.py`)**: Defines `BaseSubmitter` and structured `SubmissionResult` data classes.
- **`WaybackSubmitter` (`wayback.py`)**: Integrates with the Internet Archive "Save Page Now" interface (`https://web.archive.org/save/...`). Parses `Content-Location` response headers, extracts timestamp IDs, and stores verified archive permalinks.
- **`ArchiveTodaySubmitter` (`archive_today.py`)**: Submits URLs to Archive.today / Archive.ph. Defensively extracts permalinks and cleanly detects CAPTCHAs or anti-bot verification challenges without attempting to bypass them.
- **`GhostarchiveSubmitter` (`ghostarchive.py`)** *(Bonus Challenge)*: Third public web archiving integration providing alternative snapshot redundancy.
- **`Registry` (`registry.py`)**: Central registry for dynamic submitter lookup and batch fan-out.

#### 2.5 Change Detection & Snapshot Diffing (`backend/app/services/`)
- **`ChangeDetector` (`change_detector.py`)**: Categorizes URLs into unarchived, archived, and modified categories. Enables selective re-archiving of updated pages without submitting unchanged URLs.
- **`DiffService` (`diff_service.py`)**: Generates unified text/HTML diffs between two versions or snapshots of a web page.
- **`ExportService` (`export_service.py`)**: Serializes complete domain inventories and historical submissions into downloadable CSV and JSON formats.

#### 2.6 Automated Recurring Scheduler (`backend/app/scheduler/`)
- Integrates `APScheduler` running in-process background interval triggers.
- Allows configuring automated daily, weekly, or hourly discovery and archival scans per domain.

---

### 3. Database Schema Specification

```sql
CREATE TABLE domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'active' NOT NULL,
    created_at DATETIME NOT NULL,
    last_scan_at DATETIME,
    last_submission_at DATETIME
);
CREATE INDEX ix_domains_domain ON domains(domain);

CREATE TABLE urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER REFERENCES domains(id) ON DELETE CASCADE NOT NULL,
    original_url TEXT NOT NULL,
    normalized_url TEXT NOT NULL,
    url_hash VARCHAR(64) UNIQUE NOT NULL,
    discovery_source VARCHAR(50) NOT NULL,
    discovery_timestamp DATETIME NOT NULL,
    last_seen DATETIME NOT NULL,
    http_status INTEGER,
    content_hash VARCHAR(64),
    is_redirect BOOLEAN DEFAULT 0 NOT NULL,
    resolved_url TEXT
);
CREATE INDEX idx_urls_domain_hash ON urls(domain_id, url_hash);
CREATE INDEX idx_urls_normalized ON urls(normalized_url);

CREATE TABLE queue_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_id INTEGER REFERENCES urls(id) ON DELETE CASCADE NOT NULL,
    service VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending' NOT NULL,
    priority INTEGER DEFAULT 0 NOT NULL,
    attempts INTEGER DEFAULT 0 NOT NULL,
    leased_at DATETIME,
    created_at DATETIME NOT NULL,
    last_error TEXT,
    next_retry_at DATETIME
);
CREATE INDEX idx_queue_status_priority ON queue_items(status, priority, created_at);
CREATE INDEX idx_queue_lease ON queue_items(status, leased_at);

CREATE TABLE submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url_id INTEGER REFERENCES urls(id) ON DELETE CASCADE NOT NULL,
    service VARCHAR(50) NOT NULL,
    submitted_at DATETIME NOT NULL,
    completed_at DATETIME,
    status VARCHAR(50) NOT NULL,
    archive_url TEXT,
    archive_id VARCHAR(255),
    http_status INTEGER,
    error_message TEXT,
    last_attempted DATETIME NOT NULL
);
CREATE INDEX idx_submissions_url_service ON submissions(url_id, service);
CREATE INDEX idx_submissions_service_status ON submissions(service, status);
```

---

### 4. Concurrency & Production Scale Path

| Workload Tier | Database & Queue Architecture | Worker Configuration |
|---|---|---|
| **Demo / Local Testing** | SQLite (WAL mode, busy timeout 30s) | In-process thread pool (1-3 workers) with Token Bucket |
| **Thousands of URLs** | SQLite WAL on SSD | Multi-threaded async workers (5-10 workers) |
| **Hundreds of Thousands+** | PostgreSQL (change `DATABASE_URL` only) | Multi-process Celery / standalone Python daemons with `SKIP LOCKED` |

Because SQLite in WAL mode allows concurrent readers while writes execute in microsecond transactions, and because the schema strictly mirrors PostgreSQL relational standards, transitioning to PostgreSQL requires updating only the connection string.

---

### 5. Viva & Evaluation Defense Guide

When explaining and defending this architecture in an academic or technical evaluation, use these precise architectural explanations:

#### Q1: How does your queue recover after an abrupt process kill or crash?
> **Answer**: "The queue utilizes a persistent database-backed lease mechanism inspired by distributed job queues like `python-job-queue` and `Task_Queue`. When a worker claims a batch of items via `QueueManager.claim_next_batch()`, each item's status transitions from `'pending'` to `'in_progress'`, and an atomic lease timestamp (`leased_at = utc_now()`) is stamped.
> If the process is abruptly terminated (`kill -9`, server power cut, or unhandled crash), no items are lost or trapped. Upon application reboot (configured in the FastAPI lifespan hook in `backend/app/main.py`), `QueueManager.reclaim_expired_leases(db, lease_timeout_seconds=0)` runs immediately. Any item left with `status = 'in_progress'` whose lease timed out is safely reset to `'pending'`, clearing `leased_at` and setting `next_retry_at = utc_now()`. The worker pool picks it up immediately without duplicate submissions or corrupted state."

#### Q2: How is race-condition-free atomic job leasing achieved with SQLite?
> **Answer**: "We enable SQLite Write-Ahead Logging (`PRAGMA journal_mode=WAL`), standardizing concurrency with a 30-second busy timeout (`PRAGMA busy_timeout=30000`). Database transactions are wrapped in short-lived, atomic context blocks (`get_db_context()`). During `claim_next_batch()`, the selection and state transition (`status = 'in_progress'`, `attempts += 1`, `leased_at = now`) occur within a single committed transaction, ensuring that concurrent threads or workers never claim the same queue item."

#### Q3: What is your Dead Letter Queue (DLQ) strategy and retry backoff?
> **Answer**: "Failed submissions follow exponential backoff: `delay = min(base_delay * 2^(attempts - 1), 3600)`. When attempts reach `MAX_SUBMISSION_RETRIES` (default: 3), the item is escalated into our Dead Letter Queue by marking its status as `'failed_permanent'` with the full diagnostic error message preserved in `last_error`. DLQ items are prevented from cycling indefinitely, avoiding wasted bandwidth. Administrators can inspect them in the UI via the 'Dead Letter Queue (DLQ)' filter and click 'Retry DLQ' to bulk-reset them via `POST /api/queue/retry-failed`."

#### Q4: How does your system comply with ethical crawling and Wayback SPN2 terms?
> **Answer**: "First, our `RobotsParser` fetches and enforces `/robots.txt` directives before crawling. Second, we enforce per-service Token Bucket Rate Limiters in `WorkerPool` (15 req/min for Wayback, 6 req/min for Archive.today, 10 req/min for Ghostarchive). Third, we do not attempt to bypass CAPTCHAs or Cloudflare turnstile challenges; when anti-automation checks are detected, the submitter records a structured diagnostic failure (`status='failed'`) and pauses gracefully. Fourth, our `WaybackSubmitter` supports both modern SPN2 JSON API inspection and optional S3 API credentials (`Authorization: LOW <access_key>:<secret_key>`) as documented in `wayback-machine-archiver`."

#### Q5: How do you guarantee zero duplicate URLs across multi-strategy discovery?
> **Answer**: "Every URL discovered—whether from HTML `<a>` tags, `<link rel='canonical'>`, XML sitemaps, recursive sitemap indexes, or RSS/Atom feeds—passes through our RFC 3986 URL Normalizer (`normalizer.py`). The normalizer lowercases scheme/host, strips standard ports (`:80`, `:443`), removes fragments (`#`), strips analytics/tracking parameters (`utm_*`, `fbclid`, `gclid`), sorts query parameters alphabetically, and normalizes trailing slashes. It then generates a deterministic SHA-256 hash (`url_hash`). The `urls` table enforces a `UNIQUE(url_hash)` constraint, guaranteeing that identical resources discovered via different mechanisms map to a single database record."

---

### 6. Architectural Reference Lineage & Open-Source Best Practices

This system was engineered by synthesizing established production design patterns from leading open-source projects:
- **Queue Engine & Recovery**: Incorporates the atomic lease, retry, and crash-recovery patterns from [`python-job-queue`](https://github.com/Veneelatelli/python-job-queue) and [`Task_Queue`](https://github.com/Sumit-Todwal/Task_Queue).
- **Crawler Architecture**: Follows the multi-vector discovery (HTML BFS, sitemap index traversal, robots compliance, and error categorization) demonstrated in [`clone_site`](https://github.com/arnabsikdar-codeclouds/clone_site).
- **Wayback Submitter**: Incorporates the SPN2 Save Page Now headers, redirect extraction, and optional S3 authentication headers proven in [`wayback-machine-archiver`](https://github.com/agude/wayback-machine-archiver) and [`waybackpy`](https://github.com/akamhy/waybackpy).
- **SQLite Concurrency**: Implements the WAL-mode pragmas, connection locking, and thread isolation techniques refined in [`SQLiteWorker`](https://github.com/gitstq/SQLiteWorker).

