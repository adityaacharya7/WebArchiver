# Demonstration Video Walkthrough Script
## Mapping to Section 19: Mandatory Demonstration

This guide provides a step-by-step script for recording the demonstration video required by Section 19 and Section 20 of the assignment.

---

### Step 1: Launch Application & Overview (0:00 - 0:45)
- **Action**: Open terminal and execute `python run.py`.
- **Show**: Point out that the system initializes SQLite WAL mode, reclaims any previous worker leases, starts background workers, and launches Uvicorn on `http://localhost:8000`.
- **UI Screen**: Open browser to `http://localhost:8000`.
- **Narrate**: Point out the Executive Dashboard cards (Domains, Discovered URLs, Queue, Archived Snapshots, Success Rate) and live throughput progress bar.

---

### Step 2: Add One Domain (Section 19.1) (0:45 - 1:15)
- **Action**: Click the "+ Add Domain" button or go to the "Domains & Crawling" tab.
- **Input**: Enter a test domain (e.g., `example.com` or your designated test target).
- **Show**: Domain is registered in the database with status `active` and 0 discovered URLs.

---

### Step 3: Automatically Discover its URLs (Section 19.2) (1:15 - 2:00)
- **Action**: Click the "Discover" or "Crawl" button for the newly added domain.
- **Explain**: The unified discovery manager executes:
  - Fetches `/robots.txt` and parses sitemaps
  - Reads `/sitemap.xml` and nested sitemap indexes
  - Initiates asynchronous BFS HTML link traversal
  - Autodiscovers RSS/Atom feeds
  - Normalizes and deduplicates URLs via SHA-256 canonical hashes
- **Show**: Toast notification displays: `Discovery finished: Found X new URLs!`.

---

### Step 4: Show Discovered URL Inventory (Section 19.3) (2:00 - 2:45)
- **Action**: Switch to the "Search & Repository" tab.
- **Show**: Discovered URLs listed in the table with:
  - Canonical normalized URL
  - Discovery source badge (`HTML`, `SITEMAP`, `FEED`, `ROBOTS`)
  - HTTP status code
  - Current submission status (`Unarchived` / `Pending`)

---

### Step 5: Create the Submission Queue (Section 19.4) (2:45 - 3:15)
- **Action**: In the Domains tab or Dashboard, click "Enqueue" for the domain.
- **Show**: Switch to "Live Submission Queue" tab.
- **Explain**: The database-backed persistent queue (`queue_items`) is populated with pending items. Point out priority levels and attempt counters.

---

### Step 6: Submit URLs to Archive Services (Section 19.5 & 19.6) (3:15 - 4:00)
- **Action**: Watch background workers claim batches.
- **Show**:
  - Worker status pill updates (`Workers Active (X processed)`).
  - Status transitions from `pending` -> `in_progress` (with worker lease timestamp) -> `done` or `failed`.
  - Executive Dashboard throughput bar fills up in real-time.
  - Success and failure split is reflected on the Dashboard metrics.

---

### Step 7: Show Stored Archive URLs (Section 19.7) (4:00 - 4:45)
- **Action**: In the Repository Explorer, filter status by `Success` or click "View Snapshot ↗".
- **Show**: Click the archive URL (e.g. `https://web.archive.org/web/...`).
- **Action**: Click "History" on a URL row to display the modal showing historical submission records, archive IDs, HTTP response codes, and timestamps.

---

### Step 8: Interrupt Process and Demonstrate Resume (Section 19.8) (4:45 - 5:30)
- **Action**:
  - In terminal, press `Ctrl+C` to terminate `run.py` while queue items are active, or click "Pause Queue" in the UI.
  - Restart the application (`python run.py`).
- **Explain**: State is persisted in SQLite WAL database, not in temporary memory.
- **Show**: The server logs state: `Crash recovery: reclaimed X in-progress queue items`. Queue processing resumes seamlessly without duplicate submissions or lost state.

---

### Step 9: Re-scan Domain to Demonstrate Deduplication (Section 19.9) (5:30 - 6:15)
- **Action**: Click "Crawl" again on the same domain.
- **Show**: The discovery report shows:
  - `New URLs discovered: 0`
  - `Existing URLs refreshed: X`
- **Explain**: The canonical normalizer and SHA-256 `url_hash` prevent duplicate entries from being created in the repository.

---

### Step 10: Demonstrate Multi-Domain Architecture (Section 19.10) (6:15 - 7:00)
- **Action**: Add a second domain (e.g. `python.org`).
- **Show**:
  - Both domains appear in the Domains list with independent queues and per-domain statistics.
  - Repository search dropdown filters URLs strictly by selected domain.
  - Overall Dashboard provides combined pipeline oversight.

---

### Step 11: Bonus Features Walkthrough (7:00 - 8:00)
- **Action**: Switch to the "Bonus Center" tab.
- **Show**:
  1. **Playwright JS Rendering**: Enter a dynamic SPA URL and click "Render Page" to show extracted client-rendered DOM links.
  2. **Snapshot Diff Inspector**: Compare original vs updated content and show unified text diff lines with additions/deletions.
  3. **Automated Recurring Scheduler**: Configure a scheduled scan interval.
  4. **Export Inventory**: Click "Export CSV" and "Export JSON" to demonstrate one-click full data exports.
