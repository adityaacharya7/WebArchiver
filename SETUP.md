# Setup & Installation Guide
## Website Archive Submitter & Automated Backup Repository

Follow these instructions to set up, test, and run the Website Archive Submitter system on your local machine.

---

### 1. Prerequisites
- **Python 3.11 or higher**
- Modern Web Browser (Chrome, Edge, Firefox, or Safari)
- Internet connection (for live crawling and archival submissions)

---

### 2. Quick Installation

1. **Clone or Navigate to the Project Directory**:
   ```bash
   cd "c:\Users\adity\Desktop\Projects\SMA ASSIGNMENT"
   ```

2. **(Optional) Create and Activate a Virtual Environment**:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On Linux/macOS:
   source venv/bin/activate
   ```

3. **Install Python Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **(Optional - For JavaScript Rendering Bonus)** Install Playwright Chromium Browser:
   ```bash
   playwright install chromium
   ```
   *Note: If standalone Playwright browser binaries are not installed, the application automatically falls back to your installed Microsoft Edge or Google Chrome.*

---

### 3. Running Automated Tests

Run the complete test suite (42 unit and integration tests):
```bash
python -m pytest tests/ -v
```

Run the **Section 19 Mandatory Demonstration Verification Script**:
```bash
python tests/demo_verification.py
```
This script programmatically validates all 10 evaluation criteria from Section 19 of the assignment.

---

### 4. Starting the Web Application

Launch the FastAPI web server:
```bash
python run.py
```

Output:
```
=================================================================
  Website Archive Submitter & Automated Backup Repository
  Starting server at http://localhost:8000
=================================================================
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Initializing database...
INFO:     Starting background submission worker pool...
INFO:     Starting background scheduler...
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

Open your browser and navigate to:
👉 **`http://localhost:8000`**

---

### 5. Configuration & Environment Variables (`.env`)

Default settings are configured for out-of-the-box local execution. To override settings, you can create a `.env` file in the project root:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/archiver.db` | Database connection string (SQLite WAL or PostgreSQL) |
| `DEFAULT_MAX_CRAWL_DEPTH` | `3` | Maximum crawl depth for BFS crawler |
| `DEFAULT_MAX_CRAWL_PAGES` | `500` | Maximum pages discovered per domain crawl |
| `WORKER_POOL_SIZE` | `3` | Concurrent worker batches processed |
| `WORKER_LEASE_TIMEOUT_SECONDS` | `120` | Timeout after which abandoned queue items are recovered |
| `WAYBACK_RATE_LIMIT_PER_MINUTE` | `15` | Requests per minute to Wayback Machine |
| `ARCHIVE_TODAY_RATE_LIMIT_PER_MINUTE` | `6` | Requests per minute to Archive.today |
| `GHOSTARCHIVE_RATE_LIMIT_PER_MINUTE` | `10` | Requests per minute to Ghostarchive |

---

### 6. Troubleshooting
- **Database Locked in SQLite**: The system automatically enables `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=30000`, preventing lock contentions during concurrent reads and writes.
- **Wayback Machine Throttling**: The built-in Token Bucket rate limiter regulates requests to ~15 requests/minute. If Wayback temporarily returns HTTP 429, the system automatically backs off exponentially.
- **Port 8000 in Use**: If port 8000 is occupied, run with a custom port:
  ```bash
  uvicorn backend.app.main:app --port 8080
  ```
