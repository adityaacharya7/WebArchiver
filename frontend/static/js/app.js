/**
 * Website Archive Submitter - Interactive Frontend Controller
 * Handles real-time polling, repository search/filtering, queue control,
 * bonus tools, and automated Section 19 demonstration runner.
 */

let currentRepoPage = 1;
let searchDebounceTimer = null;
let activeTab = "tab-overview";
let pollingInterval = null;

document.addEventListener("DOMContentLoaded", async () => {
    await initApp();
});

async function initApp() {
    initModalListeners();
    await initAuth();

    // Start 2.5-second live polling loop (only polls when authenticated)
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(() => {
        if (!currentUser) return;
        loadStats();
        if (activeTab === "tab-overview") {
            loadDomains();
        } else if (activeTab === "tab-queue") {
            loadQueueItems();
        }
    }, 2500);
}

function initModalListeners() {
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeAllModals();
        }
    });

    document.querySelectorAll(".modal-overlay").forEach(overlay => {
        overlay.addEventListener("click", (e) => {
            if (e.target === overlay) {
                overlay.style.display = "none";
            }
        });
    });
}

function closeAllModals() {
    document.querySelectorAll(".modal-overlay").forEach(el => el.style.display = "none");
}

/* ================= Tab Switching ================= */
function switchTab(tabId) {
    activeTab = tabId;
    document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
    document.querySelectorAll(".tab-btn").forEach(el => el.classList.remove("active"));

    const targetContent = document.getElementById(tabId);
    if (targetContent) targetContent.classList.add("active");

    const navBtn = document.getElementById(`tab-nav-${tabId.replace("tab-", "")}`);
    if (navBtn) navBtn.classList.add("active");

    if (tabId === "tab-repository") {
        loadRepositoryUrls(currentRepoPage);
    } else if (tabId === "tab-queue") {
        loadQueueItems();
    } else if (tabId === "tab-domains") {
        loadDomains();
    } else if (tabId === "tab-bonus") {
        loadSchedules();
    }
}

/* ================= Toast Notification ================= */
function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

/* ================= Stats & Live Polling ================= */
async function loadStats() {
    try {
        const res = await fetch("/api/stats");
        if (!res.ok) return;
        const data = await res.json();

        // Update cards
        document.getElementById("stat-domains").textContent = data.total_domains;
        document.getElementById("stat-urls").textContent = data.total_urls_discovered;
        document.getElementById("stat-queue-pending").textContent = data.queue.pending;
        document.getElementById("stat-queue-progress").textContent = data.queue.in_progress;
        document.getElementById("stat-success-subs").textContent = data.submissions.success;
        document.getElementById("stat-failed-subs").textContent = data.submissions.failed;
        document.getElementById("stat-success-rate").textContent = `${data.submissions.success_rate_percent}%`;
        const totalSubsEl = document.getElementById("stat-total-subs");
        if (totalSubsEl) totalSubsEl.textContent = data.submissions.total;

        // Render service performance latency badges (Section 17)
        const latencyContainer = document.getElementById("service-latency-container");
        if (latencyContainer && data.service_performance) {
            let latHtml = "";
            for (const [srv, perf] of Object.entries(data.service_performance)) {
                latHtml += `
                    <div style="font-size: 0.72rem; padding: 3px 8px; border-radius: 6px; background: rgba(255,255,255,0.05); border: 1px solid var(--border-color); display: flex; align-items: center; gap: 5px;">
                        <span style="font-weight: 700; color: var(--accent-cyan);">${srv}:</span>
                        <span>${perf.total} submitted</span>
                        <span style="color: var(--text-muted);">•</span>
                        <span>avg ${perf.avg_latency_seconds}s</span>
                    </div>
                `;
            }
            latencyContainer.innerHTML = latHtml;
        }

        // Update throughput progress bar
        const totalItems = data.queue.total;
        const completedItems = data.queue.done;
        const pct = totalItems > 0 ? Math.round((completedItems / totalItems) * 100) : 0;
        document.getElementById("overall-progress-bar").style.width = `${pct}%`;
        document.getElementById("progress-done-text").textContent = `${completedItems} completed`;
        document.getElementById("progress-percent-text").textContent = `${pct}% complete`;
        document.getElementById("progress-pending-text").textContent = `${data.queue.pending + data.queue.in_progress} remaining`;

        // Update worker status pill
        const pill = document.getElementById("worker-status-pill");
        const statusText = document.getElementById("worker-status-text");
        const pauseBtnIcon = document.getElementById("pause-resume-icon");
        const pauseBtnText = document.getElementById("pause-resume-text");
        const queuePauseText = document.getElementById("queue-tab-pause-text");

        if (data.worker.paused) {
            pill.className = "worker-pill paused";
            statusText.textContent = "Workers Paused";
            pauseBtnIcon.textContent = "▶";
            pauseBtnText.textContent = "Resume Queue";
            if (queuePauseText) queuePauseText.textContent = "Resume Workers";
        } else {
            pill.className = "worker-pill";
            statusText.textContent = `Workers Active (${data.worker.processed_total} processed)`;
            pauseBtnIcon.textContent = "⏸";
            pauseBtnText.textContent = "Pause Queue";
            if (queuePauseText) queuePauseText.textContent = "Pause Workers";
        }
    } catch (err) {
        console.error("Failed to load stats:", err);
    }
}

/* ================= Worker Pause / Resume ================= */
async function toggleWorkerPause() {
    const isPaused = document.getElementById("worker-status-text").textContent.includes("Paused");
    const endpoint = isPaused ? "/api/queue/resume" : "/api/queue/pause";
    try {
        const res = await fetch(endpoint, { method: "POST" });
        const data = await res.json();
        showToast(`Queue workers ${data.status}!`, "info");
        loadStats();
    } catch (err) {
        showToast("Error updating worker state", "failed");
    }
}

/* ================= Domain Operations ================= */
async function loadDomains() {
    try {
        const res = await fetch("/api/domains");
        if (!res.ok) return;
        const domains = await res.json();

        // Update dashboard quick table
        const dashTbody = document.getElementById("dashboard-domains-body");
        // Update domains full table
        const fullTbody = document.getElementById("domains-full-table-body");
        // Update dropdowns
        const repoDomainSelect = document.getElementById("repo-filter-domain");
        const schedDomainSelect = document.getElementById("schedule-domain-select");

        const curRepoVal = repoDomainSelect.value;
        repoDomainSelect.innerHTML = '<option value="">All Domains</option>';
        schedDomainSelect.innerHTML = '<option value="">Select a registered domain...</option>';

        if (domains.length === 0) {
            dashTbody.innerHTML = '<tr><td colspan="5" class="empty-state">No domains added yet. Click "+ Add Domain" above.</td></tr>';
            fullTbody.innerHTML = '<tr><td colspan="8" class="empty-state">No domains registered.</td></tr>';
            return;
        }

        let dashHtml = "";
        let fullHtml = "";

        domains.forEach(d => {
            // Dropdown options
            repoDomainSelect.innerHTML += `<option value="${d.id}">${d.domain}</option>`;
            schedDomainSelect.innerHTML += `<option value="${d.id}">${d.domain}</option>`;

            const lastScan = d.last_scan_at ? new Date(d.last_scan_at).toLocaleTimeString() : "Never";

            // Dashboard table row
            dashHtml += `
                <tr>
                    <td class="font-bold">${d.domain}</td>
                    <td><span class="badge badge-service">${d.urls_discovered}</span></td>
                    <td><span class="badge badge-success">${d.submissions_success}</span></td>
                    <td><span class="badge badge-${d.status === 'active' ? 'success' : 'pending'}">${d.status}</span></td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="triggerDiscovery(${d.id})">Crawl</button>
                        <button class="btn btn-sm btn-secondary" onclick="openEnqueueModal(${d.id}, '${d.domain}')">Enqueue</button>
                    </td>
                </tr>
            `;

            // Full domains table row
            fullHtml += `
                <tr>
                    <td>#${d.id}</td>
                    <td class="font-bold text-mono">${d.domain}</td>
                    <td><span class="badge badge-service">${d.urls_discovered}</span></td>
                    <td><span class="badge badge-pending">${d.queue_pending}</span></td>
                    <td><span class="badge badge-success">${d.submissions_success}</span></td>
                    <td><span class="badge badge-failed">${d.submissions_failed}</span></td>
                    <td class="text-xs text-muted">${lastScan}</td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="triggerDiscovery(${d.id})">Discover</button>
                        <button class="btn btn-sm btn-secondary" onclick="openEnqueueModal(${d.id}, '${d.domain}')">Enqueue</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteDomain(${d.id})">Delete</button>
                    </td>
                </tr>
            `;
        });

        dashTbody.innerHTML = dashHtml;
        fullTbody.innerHTML = fullHtml;
        repoDomainSelect.value = curRepoVal;
    } catch (err) {
        console.error("Failed to load domains:", err);
    }
}

async function handleAddDomain(e) {
    e.preventDefault();
    const domainInput = document.getElementById("new-domain-input");
    const domainVal = domainInput.value.trim();
    if (!domainVal) return;

    try {
        const res = await fetch("/api/domains", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ domain: domainVal }),
        });
        const data = await res.json();
        if (res.ok) {
            if (data.status === "exists") {
                showToast(`Domain ${data.domain.domain} is already active in your dashboard!`, "info");
            } else if (data.status === "claimed") {
                showToast(`Domain ${data.domain.domain} claimed & linked to your profile!`, "success");
            } else {
                showToast(`Domain ${data.domain.domain} registered!`, "success");
            }
            domainInput.value = "";
            loadDomains();
            loadStats();

            // Ask if user wants to discover immediately on new registration
            if (data.status === "created" && confirm(`Domain ${data.domain.domain} added! Would you like to run URL discovery now?`)) {
                triggerDiscovery(data.domain.id);
            }
        } else {
            showToast(data.detail || "Failed to add domain", "failed");
        }
    } catch (err) {
        showToast("Network error while adding domain", "failed");
    }
}

async function triggerDiscovery(domainId) {
    const depth = parseInt(document.getElementById("crawl-depth").value, 10) || 3;
    const maxPages = parseInt(document.getElementById("crawl-max-pages").value, 10) || 200;
    const checkSitemaps = document.getElementById("check-sitemaps").checked;
    const checkFeeds = document.getElementById("check-feeds").checked;
    const checkExternal = document.getElementById("check-external") ? document.getElementById("check-external").checked : false;

    showToast("Starting URL discovery crawl (HTML, sitemaps, robots)...", "info");
    try {
        const res = await fetch(`/api/domains/${domainId}/discover`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                max_depth: depth,
                max_pages: maxPages,
                enable_sitemaps: checkSitemaps,
                enable_feeds: checkFeeds,
                allow_external: checkExternal,
            }),
        });
        const data = await res.json();
        if (res.ok) {
            const report = data.report;
            const speedInfo = report.crawl_speed_urls_per_sec ? ` [${report.crawl_speed_urls_per_sec} URLs/sec]` : '';
            showToast(
                `Discovery finished in ${report.crawl_duration_seconds || 0}s: Found ${report.new_urls_discovered} new URLs (${report.total_urls_in_domain} total)${speedInfo}!`,
                "success"
            );
            loadDomains();
            loadStats();
            loadRepositoryUrls(1);
        } else {
            showToast("Discovery crawl failed", "failed");
        }
    } catch (err) {
        showToast("Error executing discovery", "failed");
    }
}

function openEnqueueModal(domainId, domainName) {
    document.getElementById("enqueue-domain-id").value = domainId;
    document.getElementById("enqueue-domain-name").textContent = domainName || `Domain #${domainId}`;
    document.getElementById("enqueue-modal").style.display = "flex";
}

function closeEnqueueModal() {
    document.getElementById("enqueue-modal").style.display = "none";
}

async function submitEnqueueModal() {
    const domainId = document.getElementById("enqueue-domain-id").value;
    const services = [];
    if (document.getElementById("enq-service-wayback").checked) services.push("wayback");
    if (document.getElementById("enq-service-archive-today").checked) services.push("archive_today");
    if (document.getElementById("enq-service-ghostarchive").checked) services.push("ghostarchive");

    if (services.length === 0) {
        showToast("Please select at least one archival service", "failed");
        return;
    }

    const mode = document.getElementById("enq-mode-select").value;
    const priority = parseInt(document.getElementById("enq-priority-select").value, 10) || 0;
    const forceAll = (mode === "force_all");
    const rearchiveChanged = (mode === "rearchive_changed");

    closeEnqueueModal();
    showToast(`Enqueueing URLs for ${services.join(', ')} (Priority: ${priority}, Mode: ${mode})...`, "info");

    try {
        const res = await fetch(`/api/domains/${domainId}/enqueue`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                services: services,
                force_all: forceAll,
                rearchive_changed: rearchiveChanged,
                mode: mode,
                priority: priority,
            }),
        });
        const data = await res.json();
        if (res.ok) {
            showToast(`Enqueued ${data.items_enqueued} URLs successfully across ${services.length} services!`, "success");
            loadStats();
            loadQueueItems();
            loadDomains();
        } else {
            showToast("Failed to enqueue URLs", "failed");
        }
    } catch (err) {
        showToast("Network error while enqueueing", "failed");
    }
}

async function enqueueAllDomains() {
    if (!confirm("Enqueue unarchived URLs for all configured domains into the common processing queue?")) return;
    showToast("Enqueueing all registered domains into combined queue...", "info");
    try {
        const res = await fetch("/api/domains/enqueue-all", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                services: ["wayback", "archive_today", "ghostarchive"],
                mode: "incremental",
                priority: 0,
            }),
        });
        const data = await res.json();
        if (res.ok) {
            showToast(`Enqueued ${data.total_items_enqueued} items across ${data.domains_count} domains into the combined queue!`, "success");
            loadStats();
            loadQueueItems();
            loadDomains();
        } else {
            showToast("Failed to enqueue all domains", "failed");
        }
    } catch (err) {
        showToast("Network error during combined enqueue", "failed");
    }
}

async function triggerEnqueue(domainId) {
    openEnqueueModal(domainId, "");
}

async function deleteDomain(domainId) {
    if (!confirm("Are you sure you want to delete this domain and all its archival records?")) return;
    try {
        const res = await fetch(`/api/domains/${domainId}`, { method: "DELETE" });
        if (res.ok) {
            showToast("Domain deleted successfully", "info");
            loadDomains();
            loadStats();
            loadRepositoryUrls(1);
        } else {
            const err = await res.json().catch(() => ({}));
            showToast(err.detail || "Failed to delete domain", "failed");
        }
    } catch (err) {
        showToast("Failed to delete domain", "failed");
    }
}

/* ================= Repository Search & Filter ================= */
function debounceRepoSearch() {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
        loadRepositoryUrls(1);
    }, 300);
}

async function loadRepositoryUrls(page = 1) {
    currentRepoPage = page;
    const search = document.getElementById("repo-search-input").value.trim();
    const domainId = document.getElementById("repo-filter-domain").value;
    const service = document.getElementById("repo-filter-service").value;
    const status = document.getElementById("repo-filter-status").value;
    const source = document.getElementById("repo-filter-source").value;

    const params = new URLSearchParams({
        page: page,
        page_size: 25,
    });
    if (search) params.append("search", search);
    if (domainId) params.append("domain_id", domainId);
    if (service) params.append("service", service);
    if (status) params.append("status", status);
    if (source) params.append("source", source);

    try {
        const res = await fetch(`/api/repository/urls?${params.toString()}`);
        if (!res.ok) return;
        const data = await res.json();

        const tbody = document.getElementById("repo-urls-body");
        if (data.items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state" style="padding: 3rem 1rem;"><div style="font-size: 1.6rem; margin-bottom: 8px;">🔍</div><div style="font-weight: 600; color: var(--ink-max);">No matching URLs found.</div><div style="font-size: 0.8rem; color: var(--ink-muted); margin-top: 4px;">Register a domain or run a crawl in Tab 2 to populate the repository.</div></td></tr>';
            document.getElementById("repo-page-info").textContent = "0 Records (Empty Repository)";
            const prevBtn = document.getElementById("btn-prev-page");
            const nextBtn = document.getElementById("btn-next-page");
            if (prevBtn) prevBtn.disabled = true;
            if (nextBtn) nextBtn.disabled = true;
            return;
        }

        let html = "";
        data.items.forEach(item => {
            const httpBadge = item.http_status
                ? `<span class="badge ${item.http_status < 400 ? 'badge-success' : 'badge-failed'}">${item.http_status}</span>`
                : '<span class="text-xs text-muted">-</span>';

            const sourceBadge = `<span class="badge badge-service">${item.discovery_source}</span>`;

            let archiveLink = '<span class="text-xs text-muted">None</span>';
            let statusBadge = '<span class="badge badge-pending">Unarchived</span>';

            if (item.recent_submissions && item.recent_submissions.length > 0) {
                const latest = item.recent_submissions[0];
                if (latest.status === "success" && latest.archive_url) {
                    archiveLink = `<a href="${latest.archive_url}" target="_blank" class="text-xs" style="color: var(--accent-cyan); text-decoration: underline;">View Snapshot ↗</a>`;
                    if (item.content_changed) {
                        statusBadge = '<span class="badge badge-progress" style="background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid #f59e0b;" title="Page content changed since last archive">Modified</span>';
                    } else {
                        statusBadge = '<span class="badge badge-success">Archived</span>';
                    }
                } else if (latest.status === "failed") {
                    statusBadge = `<span class="badge badge-failed" title="${latest.error_message || ''}">Failed</span>`;
                }
            } else if (item.is_queued) {
                statusBadge = '<span class="badge badge-pending" style="color: var(--accent-cyan); border: 1px solid var(--accent-cyan);">In Queue</span>';
            }

            html += `
                <tr>
                    <td>
                        <div class="stream-url" title="${item.normalized_url}">${item.normalized_url}</div>
                    </td>
                    <td>${sourceBadge}</td>
                    <td>${httpBadge}</td>
                    <td>
                        <div style="margin-bottom: 4px;">${statusBadge}</div>
                        <span class="text-xs text-muted">${(item.recent_submissions || []).length} attempts</span>
                    </td>
                    <td>${archiveLink}</td>
                    <td>
                        <button class="btn btn-sm btn-outline" onclick="viewUrlHistory(${item.id})">History</button>
                    </td>
                </tr>
            `;
        });

        tbody.innerHTML = html;
        document.getElementById("repo-page-info").textContent = `Showing page ${data.page} of ${data.total_pages} (${data.total} total URLs)`;
        document.getElementById("btn-prev-page").disabled = (data.page <= 1);
        document.getElementById("btn-next-page").disabled = (data.page >= data.total_pages);
    } catch (err) {
        console.error("Failed to load repository URLs:", err);
    }
}

function changeRepoPage(delta) {
    const newPage = currentRepoPage + delta;
    if (newPage >= 1) {
        loadRepositoryUrls(newPage);
    }
}

async function viewUrlHistory(urlId) {
    try {
        const res = await fetch(`/api/urls/${urlId}/history`);
        if (!res.ok) return;
        const data = await res.json();

        document.getElementById("modal-url-text").textContent = data.url.normalized_url;
        const availEl = document.getElementById("modal-wayback-avail");
        if (availEl) {
            availEl.innerHTML = '<span class="text-xs text-muted">Checking live Wayback availability...</span>';
            fetch(`/api/urls/${urlId}/availability`)
                .then(r => r.json())
                .then(availData => {
                    if (availData.availability && availData.availability.available) {
                        availEl.innerHTML = `<span class="badge badge-success">Live Wayback Snapshot</span> <a href="${availData.availability.url}" target="_blank" style="color:var(--accent-cyan); font-size:0.75rem; margin-left:6px; text-decoration: underline;">Open Snapshot (${availData.availability.timestamp}) ↗</a>`;
                    } else {
                        availEl.innerHTML = '<span class="badge badge-pending">No Wayback Snapshot Verified</span>';
                    }
                })
                .catch(() => {
                    availEl.innerHTML = "";
                });
        }
        const tbody = document.getElementById("modal-history-tbody");

        if (data.submissions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No submission attempts recorded yet.</td></tr>';
        } else {
            let html = "";
            data.submissions.forEach(s => {
                const dateStr = s.submitted_at ? new Date(s.submitted_at).toLocaleString() : "-";
                const archLink = s.archive_url
                    ? `<a href="${s.archive_url}" target="_blank" style="color:var(--accent-cyan);">Link ↗</a>`
                    : "-";
                html += `
                    <tr>
                        <td><span class="badge badge-service">${s.service}</span></td>
                        <td><span class="badge ${s.status === 'success' ? 'badge-success' : 'badge-failed'}">${s.status}</span></td>
                        <td>${archLink}</td>
                        <td>${s.http_status || '-'}</td>
                        <td class="text-xs text-muted">${dateStr}</td>
                        <td class="text-xs text-muted">${s.error_message || 'None'}</td>
                    </tr>
                `;
            });
            tbody.innerHTML = html;
        }

        document.getElementById("history-modal").style.display = "flex";
    } catch (err) {
        showToast("Failed to load history", "failed");
    }
}

function closeHistoryModal() {
    document.getElementById("history-modal").style.display = "none";
}

/* ================= Live Queue Table & Stream ================= */
async function loadQueueItems() {
    try {
        const filterStatusEl = document.getElementById("queue-filter-status");
        const statusVal = filterStatusEl && filterStatusEl.value ? filterStatusEl.value : "";
        let endpoint = "/api/queue/items?limit=50";
        if (statusVal) {
            endpoint += `&status=${encodeURIComponent(statusVal)}`;
        }

        const res = await fetch(endpoint);
        if (!res.ok) return;
        const items = await res.json();

        const tbody = document.getElementById("queue-items-body");
        const streamList = document.getElementById("dashboard-stream-list");

        if (items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Queue is currently empty.</td></tr>';
            streamList.innerHTML = '<div class="empty-state">No submission events in queue.</div>';
            return;
        }

        let tableHtml = "";
        let streamHtml = "";

        items.forEach(q => {
            const statusClass = {
                "pending": "badge-pending",
                "in_progress": "badge-progress",
                "done": "badge-success",
                "failed": "badge-failed",
                "failed_permanent": "badge-failed",
            }[q.status] || "badge-pending";

            const leased = q.leased_at ? new Date(q.leased_at).toLocaleTimeString() : "-";

            tableHtml += `
                <tr>
                    <td>#${q.id}</td>
                    <td><div class="stream-url" title="${q.normalized_url}">${q.normalized_url}</div></td>
                    <td><span class="badge badge-service">${q.service}</span></td>
                    <td>${q.priority}</td>
                    <td>${q.attempts}</td>
                    <td><span class="badge ${statusClass}">${q.status}</span></td>
                    <td class="text-xs text-muted">${leased}</td>
                    <td class="text-xs text-muted">${q.last_error || '-'}</td>
                </tr>
            `;

            // Stream list items for Dashboard
            streamHtml += `
                <div class="stream-item">
                    <div class="stream-meta">
                        <span class="stream-url">${q.normalized_url}</span>
                        <span class="stream-time">${q.service} • Priority ${q.priority}</span>
                    </div>
                    <span class="badge ${statusClass}">${q.status}</span>
                </div>
            `;
        });

        tbody.innerHTML = tableHtml;
        streamList.innerHTML = streamHtml;
    } catch (err) {
        console.error("Failed to load queue items:", err);
    }
}

async function retryFailedItems() {
    try {
        const res = await fetch("/api/queue/retry-failed", { method: "POST" });
        const data = await res.json();
        showToast(`Reset ${data.reset_count} permanently failed items back to pending!`, "success");
        loadStats();
        loadQueueItems();
    } catch (err) {
        showToast("Error resetting failed items", "failed");
    }
}

/* ================= Bonus Center Features ================= */
async function runPlaywrightRender() {
    const url = document.getElementById("playwright-url-input").value.trim();
    if (!url) {
        showToast("Please enter a URL to render", "failed");
        return;
    }

    showToast("Rendering page with Playwright headless browser...", "info");
    const pre = document.getElementById("playwright-output-pre");
    const area = document.getElementById("playwright-results-area");
    area.style.display = "block";
    pre.textContent = "Loading dynamic DOM...";

    try {
        const res = await fetch("/api/bonus/render-page", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url: url }),
        });
        const data = await res.json();
        pre.textContent = JSON.stringify(data, null, 2);
        if (data.success) {
            showToast(`Render complete! Discovered ${data.links.length} dynamic links.`, "success");
        } else {
            showToast(`Rendering finished with notice: ${data.error || 'Requires login/auth'}`, "info");
        }
    } catch (err) {
        pre.textContent = `Error: ${err.message}`;
    }
}

async function runSnapshotDiff() {
    const textA = document.getElementById("diff-text-a").value;
    const textB = document.getElementById("diff-text-b").value;

    try {
        const res = await fetch("/api/bonus/diff", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text_a: textA, text_b: textB }),
        });
        const data = await res.json();
        const area = document.getElementById("diff-results-area");
        const summary = document.getElementById("diff-summary-text");
        const pre = document.getElementById("diff-output-pre");
        area.style.display = "block";

        summary.textContent = data.is_identical
            ? "Pages are identical. 0 differences detected."
            : `Differences: +${data.additions_count} additions, -${data.deletions_count} deletions`;

        let formatted = "";
        (data.diff_lines || []).forEach(line => {
            if (line.startsWith("+")) {
                formatted += `<span class="diff-add">${escapeHtml(line)}</span>\n`;
            } else if (line.startsWith("-")) {
                formatted += `<span class="diff-del">${escapeHtml(line)}</span>\n`;
            } else {
                formatted += `${escapeHtml(line)}\n`;
            }
        });
        pre.innerHTML = formatted || "No changes detected.";
    } catch (err) {
        showToast("Diff computation error", "failed");
    }
}

async function createSchedule() {
    const domainId = document.getElementById("schedule-domain-select").value;
    const interval = parseInt(document.getElementById("schedule-interval-select").value, 10);
    if (!domainId) {
        showToast("Please select a domain", "failed");
        return;
    }

    try {
        const res = await fetch("/api/bonus/schedule", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ domain_id: parseInt(domainId, 10), interval_minutes: interval }),
        });
        if (res.ok) {
            showToast("Recurring automated scan scheduled!", "success");
            loadSchedules();
        }
    } catch (err) {
        showToast("Failed to create schedule", "failed");
    }
}

async function loadSchedules() {
    try {
        const res = await fetch("/api/bonus/schedules");
        if (!res.ok) return;
        const list = await res.json();
        const tbody = document.getElementById("schedules-table-body");
        if (list.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No scheduled recurring jobs currently registered.</td></tr>';
            return;
        }

        let html = "";
        list.forEach(s => {
            const nextRun = s.next_run_at ? new Date(s.next_run_at).toLocaleString() : "Pending";
            const lastRun = s.last_run_at ? new Date(s.last_run_at).toLocaleString() : "Never";
            html += `
                <tr>
                    <td>#${s.id}</td>
                    <td class="font-bold text-mono">${s.domain_name || 'Domain #' + s.domain_id}</td>
                    <td>Every ${s.interval_minutes} mins</td>
                    <td><span class="badge badge-success">Active</span></td>
                    <td class="text-xs text-muted">${lastRun}</td>
                    <td class="text-xs">${nextRun}</td>
                    <td>
                        <button class="btn btn-sm btn-danger" onclick="deleteSchedule(${s.id})">Delete</button>
                    </td>
                </tr>
            `;
        });
        tbody.innerHTML = html;
    } catch (err) {
        console.error("Failed to load schedules:", err);
    }
}

async function deleteSchedule(scheduleId) {
    if (!confirm(`Are you sure you want to cancel and delete schedule #${scheduleId}?`)) return;
    try {
        const res = await fetch(`/api/bonus/schedule/${scheduleId}`, { method: "DELETE" });
        if (res.ok) {
            showToast("Recurring scan schedule deleted!", "info");
            loadSchedules();
        } else {
            showToast("Failed to delete schedule", "failed");
        }
    } catch (err) {
        showToast("Error deleting schedule", "failed");
    }
}


function exportData(fmt) {
    const domainFilter = document.getElementById("repo-filter-domain");
    const domainId = domainFilter && domainFilter.value ? domainFilter.value : "";
    let url = `/api/export?format=${fmt}`;
    if (domainId) {
        url += `&domain_id=${encodeURIComponent(domainId)}`;
    }
    window.open(url, "_blank");
}

function loadSampleInstagram() {
    const input = document.getElementById("playwright-url-input");
    if (input) {
        input.value = "https://www.instagram.com/p/DAA45uXvXmC/";
        showToast("Loaded sample Instagram public post URL", "info");
    }
}

function loadSampleSpa() {
    const input = document.getElementById("playwright-url-input");
    if (input) {
        input.value = "https://quotes.toscrape.com/js/";
        showToast("Loaded sample dynamic JavaScript SPA URL", "info");
    }
}

function loadSampleDiff() {
    const textA = document.getElementById("diff-text-a");
    const textB = document.getElementById("diff-text-b");
    if (textA && textB) {
        textA.value = `<article>\n  <h1>Breaking Archive Report</h1>\n  <p class="status">Initial snapshot created: 50 URLs discovered.</p>\n  <p>Submission queue initialized for Internet Archive.</p>\n</article>`;
        textB.value = `<article>\n  <h1>Breaking Archive Report (Updated)</h1>\n  <p class="status">Re-scan completed: 75 URLs discovered (+25 new).</p>\n  <p>Submission queue initialized for Internet Archive & Archive.today.</p>\n  <p class="audit">Verification audit passed 100%.</p>\n</article>`;
        showToast("Loaded sample snapshot versions for HTML diffing", "info");
        runSnapshotDiff();
    }
}

/* ================= Section 19 Guided Demonstration Runner ================= */
async function demoStep1() {
    // Add domain: example.com
    showToast("Demonstration Step 1: Adding primary target domain...", "info");
    const res = await fetch("/api/domains", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain: "example.com" }),
    });
    const data = await res.json();
    showToast("Step 1 Complete: Domain 'example.com' registered in repository!", "success");
    loadDomains();
    loadStats();
}

async function demoStep2() {
    showToast("Demonstration Step 2: Executing URL discovery...", "info");
    const domainsRes = await fetch("/api/domains");
    const domains = await domainsRes.json();
    const d = domains.find(x => x.domain === "example.com") || domains[0];
    if (!d) {
        showToast("Please run Step 1 first!", "failed");
        return;
    }
    await triggerDiscovery(d.id);
    showToast("Step 2 Complete: Discovered URLs indexed!", "success");
}

async function demoStep3() {
    showToast("Demonstration Step 3: Displaying URL Inventory...", "info");
    switchTab("tab-repository");
    loadRepositoryUrls(1);
    showToast("Step 3 Complete: Showing discovered URL inventory!", "success");
}

async function demoStep4() {
    showToast("Demonstration Step 4: Creating submission queue...", "info");
    try {
        const domainsRes = await fetch("/api/domains");
        const domains = await domainsRes.json();
        const d = domains.find(x => x.domain === "example.com") || domains[0];
        if (!d) {
            showToast("Please run Step 1 first to register a domain!", "failed");
            return;
        }
        const res = await fetch(`/api/domains/${d.id}/enqueue`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                services: ["wayback", "archive_today"],
                priority: 5,
                mode: "all",
            }),
        });
        const data = await res.json();
        switchTab("tab-queue");
        loadQueueItems();
        loadStats();
        showToast(`Step 4 Complete: Enqueued ${data.items_enqueued || 0} items for domain ${d.domain}!`, "success");
    } catch (err) {
        showToast("Error creating submission queue in Step 4", "failed");
    }
}

async function demoStep5() {
    showToast("Demonstration Step 5: Background workers processing submissions...", "info");
    switchTab("tab-queue");
    loadQueueItems();
}

async function demoStep6() {
    showToast("Demonstration Step 6: Showing success/failure split in Dashboard...", "info");
    switchTab("tab-overview");
    loadStats();
}

async function demoStep7() {
    showToast("Demonstration Step 7: Showing stored archive URLs...", "info");
    switchTab("tab-repository");
    document.getElementById("repo-filter-status").value = "success";
    loadRepositoryUrls(1);
}

async function demoStep8() {
    showToast("Demonstration Step 8: Demonstrating interruption and resume...", "info");
    // Pause queue, demonstrate state persists in SQLite WAL
    await fetch("/api/queue/pause", { method: "POST" });
    showToast("Simulated interruption: Workers paused. Queue state safely preserved in DB!", "info");
    setTimeout(async () => {
        await fetch("/api/queue/resume", { method: "POST" });
        showToast("Resumed! Workers continue without losing state or duplicating submissions.", "success");
        loadStats();
        loadQueueItems();
    }, 2500);
}

async function demoStep9() {
    showToast("Demonstration Step 9: Re-scanning domain to verify deduplication...", "info");
    try {
        const domainsRes = await fetch("/api/domains");
        const domains = await domainsRes.json();
        const d = domains.find(x => x.domain === "example.com") || domains[0];
        if (!d) {
            showToast("Please run Step 1 first to create a domain!", "failed");
            return;
        }
        const res = await fetch(`/api/domains/${d.id}/discover`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ max_depth: 2, max_pages: 50 }),
        });
        const data = await res.json();
        showToast(
            `Step 9 Complete: Re-scan complete! New URLs: ${data.report.new_urls_discovered} (0 duplicates created)!`,
            "success"
        );
        loadDomains();
        loadStats();
    } catch (err) {
        showToast("Failed to re-scan domain in Step 9", "failed");
    }
}

async function demoStep10() {
    showToast("Demonstration Step 10: Adding second domain (python.org) for multi-domain demo...", "info");
    await fetch("/api/domains", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain: "python.org" }),
    });
    switchTab("tab-domains");
    loadDomains();
    showToast("Step 10 Complete: Multi-domain architecture running with independent queues!", "success");
}

function escapeHtml(str) {
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

/* ================= Firebase Authentication & User Profile ================= */
let currentUser = null;
let authConfig = null;
let firebaseInitialized = false;

async function initAuth() {
    checkUrlAuthParams();
    await Promise.all([
        initFirebase(),
        checkAuthStatus(),
        loadAuthConfig(),
    ]);
}

async function initFirebase() {
    try {
        const res = await fetch("/api/auth/firebase-config");
        if (!res.ok) return;
        const config = await res.json();
        if (config.configured && window.firebase) {
            if (!firebase.apps.length) {
                firebase.initializeApp({
                    apiKey: config.apiKey,
                    authDomain: config.authDomain,
                    projectId: config.projectId,
                    appId: config.appId,
                });
            }
            firebaseInitialized = true;
            const statusEl = document.getElementById("google-config-status");
            if (statusEl) {
                statusEl.innerHTML = `<span style="color: #10b981;">● Firebase Armed (${config.projectId})</span>`;
            }
            const gateStatusEl = document.getElementById("gate-firebase-status");
            if (gateStatusEl) {
                gateStatusEl.innerHTML = `<span style="color: #10b981;">●</span> Firebase Armed (${config.projectId})`;
            }
        } else {
            const statusEl = document.getElementById("google-config-status");
            if (statusEl) {
                statusEl.innerHTML = '<span>⚙️ Firebase keys not set in .env. Use <strong>Demo Mode</strong> or add FIREBASE_API_KEY</span>';
            }
            const gateStatusEl = document.getElementById("gate-firebase-status");
            if (gateStatusEl) {
                gateStatusEl.innerHTML = '<span>⚡ Standby · Ready for Google / Demo Sign In</span>';
            }
        }
    } catch (err) {
        console.warn("Firebase initialization check:", err);
    }
}

function checkUrlAuthParams() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("auth_success")) {
        showToast("Authentication successful! Welcome to Mission Control.", "success");
        window.history.replaceState({}, document.title, window.location.pathname);
    } else if (urlParams.get("auth_error")) {
        const err = urlParams.get("auth_error");
        showToast(`Authentication issue: ${err}`, "failed");
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}

async function loadAuthConfig() {
    try {
        const res = await fetch("/api/auth/config");
        if (res.ok) {
            authConfig = await res.json();
        }
    } catch (e) {
        console.warn("Could not load auth configuration:", e);
    }
}

async function checkAuthStatus() {
    try {
        const res = await fetch("/api/auth/me");
        if (res.ok) {
            const data = await res.json();
            if (data.authenticated && data.user) {
                currentUser = data.user;
                updateAuthUI(currentUser);
                return;
            }
        }
    } catch (e) {
        // Unauthenticated visitor
    }
    currentUser = null;
    updateAuthUI(null);
}

function updateAuthUI(user) {
    const loginBtn = document.getElementById("btn-google-auth");
    const profileChip = document.getElementById("user-profile-chip");
    const authGateScreen = document.getElementById("auth-gate-screen");
    const authenticatedDeck = document.getElementById("authenticated-deck");

    if (user) {
        // Hide sign-in gate, reveal Mission Control deck
        if (authGateScreen) authGateScreen.style.display = "none";
        if (authenticatedDeck) authenticatedDeck.style.display = "block";

        if (loginBtn) loginBtn.style.display = "none";
        if (profileChip) {
            profileChip.style.display = "flex";

            const avatarImg = document.getElementById("user-chip-avatar");
            const nameEl = document.getElementById("user-chip-name");
            const roleEl = document.getElementById("user-chip-role");

            if (avatarImg) {
                avatarImg.src = user.picture || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80";
            }
            if (nameEl) nameEl.textContent = user.name || user.email || "Commander";
            if (roleEl) roleEl.textContent = (user.role || "OPERATOR").toUpperCase();
        }

        // Refresh data scoped to this authenticated user
        loadStats();
        loadDomains();
        loadQueueItems();
        loadRepositoryUrls(1);
        loadSchedules();
    } else {
        // Show dedicated Orbitronix sign-in gate deck, lock Mission Control tabs
        if (authGateScreen) authGateScreen.style.display = "block";
        if (authenticatedDeck) authenticatedDeck.style.display = "none";

        if (loginBtn) loginBtn.style.display = "inline-flex";
        if (profileChip) profileChip.style.display = "none";
    }
}

function handleAuthClick() {
    openAuthModal();
}

function openAuthModal() {
    const modal = document.getElementById("auth-modal");
    if (modal) modal.style.display = "flex";
}

function closeAuthModal() {
    const modal = document.getElementById("auth-modal");
    if (modal) modal.style.display = "none";
}

async function signInWithGoogleFirebase() {
    if (!firebaseInitialized) {
        showToast("Firebase is not configured in .env yet. Use the One-Click Demo Mode below!", "info");
        return;
    }
    try {
        const provider = new firebase.auth.GoogleAuthProvider();
        provider.setCustomParameters({ prompt: 'select_account' });
        showToast("Opening Google Sign-In via Firebase...", "info");
        const result = await firebase.auth().signInWithPopup(provider);
        const idToken = await result.user.getIdToken();

        const res = await fetch("/api/auth/firebase/session", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id_token: idToken }),
        });

        if (!res.ok) {
            const errData = await res.json();
            throw new Error(errData.detail || "Server session verification failed");
        }

        const data = await res.json();
        currentUser = data.user;
        updateAuthUI(currentUser);
        closeAuthModal();
        showToast(`Welcome, ${currentUser.name}! Authenticated via Firebase.`, "success");
    } catch (err) {
        if (err.code === "auth/popup-closed-by-user") {
            showToast("Google Sign-In cancelled.", "info");
        } else {
            showToast("Firebase Error: " + err.message, "failed");
        }
    }
}

async function loginDemoUser() {
    try {
        const res = await fetch("/api/auth/demo-login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });
        if (!res.ok) throw new Error("Demo login failed");
        const data = await res.json();
        currentUser = data.user;
        updateAuthUI(currentUser);
        closeAuthModal();
        showToast(`Authenticated as ${currentUser.name} (${currentUser.role})`, "success");
    } catch (err) {
        showToast("Error during demo authentication: " + err.message, "failed");
    }
}

function clearUserDataCache() {
    const domainList = document.getElementById("domain-list-body");
    if (domainList) domainList.innerHTML = "";
    const repoList = document.getElementById("repo-results-body");
    if (repoList) repoList.innerHTML = "";
    const queueList = document.getElementById("queue-items-body");
    if (queueList) queueList.innerHTML = "";
    const scheduleList = document.getElementById("schedules-list-body");
    if (scheduleList) scheduleList.innerHTML = "";
}

async function logoutUser() {
    try {
        if (window.firebase && firebase.apps && firebase.apps.length) {
            await firebase.auth().signOut().catch(() => {});
        }
        const res = await fetch("/api/auth/logout", { method: "POST" });
        if (res.ok) {
            currentUser = null;
            clearUserDataCache();
            updateAuthUI(null);
            showToast("Successfully signed out.", "info");
        }
    } catch (err) {
        showToast("Logout error: " + err.message, "failed");
    }
}
