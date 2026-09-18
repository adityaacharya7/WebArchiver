"""
REST API endpoints for domains, discovery, queue, repository search, and bonuses.
"""
import asyncio
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Response, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc

from backend.app.db.database import get_db, get_db_context
from backend.app.db.models import Domain, Url, QueueItem, Submission, Schedule, User, utc_now
from backend.app.routes.auth import get_current_user
from backend.app.normalizer.normalizer import clean_domain_name, normalize_url, compute_url_hash
from backend.app.crawler.discovery_manager import DiscoveryManager
from backend.app.crawler.playwright_crawler import PlaywrightCrawler
from backend.app.queue.queue_manager import QueueManager
from backend.app.queue.worker_pool import worker_pool
from backend.app.services.change_detector import ChangeDetector
from backend.app.services.diff_service import DiffService
from backend.app.services.export_service import ExportService
from backend.app.scheduler.scheduler_service import scheduler_service
from backend.app.submitters.registry import list_available_services

router = APIRouter(prefix="/api")


# --- System & Dashboard Metrics ---
@router.get("/stats")
def get_system_stats(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Summary metrics for the dashboard, scoped to the active user if authenticated."""
    if current_user:
        dom_ids = [d[0] for d in db.query(Domain.id).filter(Domain.user_id == current_user.id).all()]
        total_domains = len(dom_ids)
        total_urls = db.query(Url).filter(Url.domain_id.in_(dom_ids)).count() if dom_ids else 0
        total_submissions = (
            db.query(Submission).join(Url).filter(Url.domain_id.in_(dom_ids)).count() if dom_ids else 0
        )
        success_submissions = (
            db.query(Submission).join(Url).filter(Url.domain_id.in_(dom_ids), Submission.status == "success").count()
            if dom_ids else 0
        )
        failed_submissions = (
            db.query(Submission).join(Url).filter(Url.domain_id.in_(dom_ids), Submission.status == "failed").count()
            if dom_ids else 0
        )
        q_stats = QueueManager.get_stats(db, domain_id=dom_ids[0] if len(dom_ids) == 1 else None)
    else:
        total_domains = db.query(Domain).count()
        total_urls = db.query(Url).count()
        q_stats = QueueManager.get_stats(db)
        total_submissions = db.query(Submission).count()
        success_submissions = db.query(Submission).filter(Submission.status == "success").count()
        failed_submissions = db.query(Submission).filter(Submission.status == "failed").count()

    # Success rate
    rate = round((success_submissions / total_submissions * 100), 1) if total_submissions > 0 else 0.0

    # Per-service performance & latency metrics (Section 17)
    services_metrics = {}
    for s_name in list_available_services():
        s_query = db.query(Submission).filter(Submission.service == s_name)
        if current_user and dom_ids:
            s_query = s_query.join(Url).filter(Url.domain_id.in_(dom_ids))
        s_subs = s_query.all()
        s_count = len(s_subs)
        s_success = sum(1 for s in s_subs if s.status == "success")
        durations = [
            (s.completed_at - s.submitted_at).total_seconds()
            for s in s_subs
            if s.completed_at and s.submitted_at and (s.completed_at >= s.submitted_at)
        ]
        avg_dur = round(sum(durations) / len(durations), 2) if durations else 0.0
        services_metrics[s_name] = {
            "total": s_count,
            "success": s_success,
            "failed": s_count - s_success,
            "avg_latency_seconds": avg_dur,
        }

    return {
        "total_domains": total_domains,
        "total_urls_discovered": total_urls,
        "queue": q_stats,
        "submissions": {
            "total": total_submissions,
            "success": success_submissions,
            "failed": failed_submissions,
            "success_rate_percent": rate,
        },
        "service_performance": services_metrics,
        "worker": worker_pool.get_status(),
        "available_services": list_available_services(),
    }


# --- Domain Management ---
@router.get("/domains")
def list_domains(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """List registered domains, scoped to the current user if authenticated."""
    query = db.query(Domain)
    if current_user:
        query = query.filter(Domain.user_id == current_user.id)
    domains = query.order_by(Domain.id.desc()).all()
    results = []

    for d in domains:
        url_count = db.query(Url).filter(Url.domain_id == d.id).count()
        q_stats = QueueManager.get_stats(db, domain_id=d.id)
        
        subs_success = (
            db.query(Submission)
            .join(Url)
            .filter(Url.domain_id == d.id, Submission.status == "success")
            .count()
        )
        subs_failed = (
            db.query(Submission)
            .join(Url)
            .filter(Url.domain_id == d.id, Submission.status == "failed")
            .count()
        )

        d_dict = d.to_dict()
        d_dict.update({
            "urls_discovered": url_count,
            "queue_pending": q_stats["pending"],
            "queue_in_progress": q_stats["in_progress"],
            "queue_done": q_stats["done"],
            "queue_failed": q_stats["failed_permanent"],
            "submissions_success": subs_success,
            "submissions_failed": subs_failed,
        })
        results.append(d_dict)

    return results


@router.post("/domains")
def create_domain(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Register a new domain for archiving, linked to current user."""
    raw_domain = payload.get("domain", "").strip()
    if not raw_domain:
        raise HTTPException(status_code=400, detail="Domain cannot be empty.")

    clean_name = clean_domain_name(raw_domain)
    if not clean_name:
        raise HTTPException(status_code=400, detail="Invalid domain name format.")

    existing = db.query(Domain).filter(Domain.domain == clean_name).first()
    if existing:
        if current_user and existing.user_id is None:
            existing.user_id = current_user.id
            db.commit()
            db.refresh(existing)
        return {"status": "exists", "domain": existing.to_dict()}

    new_domain = Domain(
        domain=clean_name,
        status="active",
        user_id=current_user.id if current_user else None,
    )
    db.add(new_domain)
    db.commit()
    db.refresh(new_domain)

    return {"status": "created", "domain": new_domain.to_dict()}


@router.delete("/domains/{domain_id}")
def delete_domain(domain_id: int, db: Session = Depends(get_db)):
    """Delete a domain and all associated URLs and submissions."""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found.")

    scheduler_service.remove_schedule(domain_id)
    db.delete(domain)
    db.commit()
    return {"status": "deleted", "domain_id": domain_id}


# --- Discovery Engine Trigger ---
async def _async_run_discovery(domain_str: str, max_depth: int, max_pages: int, enable_sitemaps: bool, enable_feeds: bool):
    with get_db_context() as db:
        manager = DiscoveryManager(
            domain_name=domain_str,
            max_depth=max_depth,
            max_pages=max_pages,
            enable_sitemaps=enable_sitemaps,
            enable_feeds=enable_feeds,
        )
        await manager.run_discovery(db)


@router.post("/domains/{domain_id}/discover")
async def trigger_discovery(
    domain_id: int,
    background_tasks: BackgroundTasks,
    payload: dict = None,
    db: Session = Depends(get_db),
):
    """Trigger multi-strategy discovery for a domain."""
    payload = payload or {}
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found.")

    max_depth = payload.get("max_depth", 3)
    max_pages = payload.get("max_pages", 500)
    enable_sitemaps = payload.get("enable_sitemaps", True)
    enable_feeds = payload.get("enable_feeds", True)
    allow_external = payload.get("allow_external", False)

    manager = DiscoveryManager(
        domain_name=domain.domain,
        max_depth=max_depth,
        max_pages=max_pages,
        enable_sitemaps=enable_sitemaps,
        enable_feeds=enable_feeds,
        allow_external=allow_external,
    )
    # Execute discovery
    report = await manager.run_discovery(db)
    return {"status": "completed", "report": report}


# --- Queue & Enqueueing Operations ---
@router.get("/domains/{domain_id}/inventory")
def get_domain_inventory(domain_id: int, db: Session = Depends(get_db)):
    """Inspect domain inventory (archived vs unarchived counts)."""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found.")
    return ChangeDetector.inspect_domain_inventory(db, domain_id)


@router.post("/domains/{domain_id}/enqueue")
def enqueue_domain_urls(domain_id: int, payload: dict = None, db: Session = Depends(get_db)):
    """Enqueue domain URLs for archival submission."""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found.")

    payload = payload or {}
    services = payload.get("services", ["wayback"])
    mode = payload.get("mode", "")
    force_all = payload.get("force_all", False) or mode in ("force_all", "all")
    rearchive_changed = payload.get("rearchive_changed", False) or mode == "rearchive_changed"
    priority = payload.get("priority", 0)

    result = ChangeDetector.enqueue_incremental(
        db=db,
        domain_id=domain_id,
        services=services,
        force_all=force_all,
        rearchive_changed=rearchive_changed,
        priority=priority,
    )
    return result


@router.post("/domains/enqueue-all")
def enqueue_all_domains(payload: dict = None, db: Session = Depends(get_db)):
    """
    Combined processing queue (Section 4 deliverable):
    Enqueues URLs across all active registered domains into the common processing queue.
    """
    payload = payload or {}
    services = payload.get("services", ["wayback"])
    mode = payload.get("mode", "incremental")
    force_all = payload.get("force_all", False) or mode in ("force_all", "all")
    rearchive_changed = payload.get("rearchive_changed", False) or mode == "rearchive_changed"
    priority = payload.get("priority", 0)

    domains = db.query(Domain).filter(Domain.status == "active").all()
    total_enqueued = 0
    domain_reports = []

    for d in domains:
        res = ChangeDetector.enqueue_incremental(
            db=db,
            domain_id=d.id,
            services=services,
            force_all=force_all,
            rearchive_changed=rearchive_changed,
            priority=priority,
        )
        total_enqueued += res.get("items_enqueued", 0)
        domain_reports.append(res)

    return {
        "status": "enqueued_all",
        "domains_count": len(domains),
        "total_items_enqueued": total_enqueued,
        "services": services,
        "details": domain_reports,
    }


@router.get("/queue/items")
def list_queue_items(
    limit: int = 50,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """List recent queue items with normalized URL and status."""
    query = db.query(QueueItem)
    if current_user:
        query = query.join(Url).join(Domain).filter(Domain.user_id == current_user.id)
    if status:
        query = query.filter(QueueItem.status == status)

    items = query.order_by(QueueItem.id.desc()).limit(limit).all()
    return [item.to_dict() for item in items]


@router.post("/queue/pause")
def pause_queue():
    """Pause background submission processing."""
    worker_pool.pause()
    return {"status": "paused", "worker": worker_pool.get_status()}


@router.post("/queue/resume")
def resume_queue():
    """Resume background submission processing."""
    worker_pool.resume()
    return {"status": "resumed", "worker": worker_pool.get_status()}


@router.post("/queue/retry-failed")
def retry_failed_queue_items(domain_id: int | None = None, db: Session = Depends(get_db)):
    """Reset failed_permanent items back to pending for retry."""
    count = QueueManager.retry_permanent_failures(db, domain_id=domain_id)
    return {"status": "retried", "reset_count": count}


# --- Repository Search & Filter API ---
@router.get("/repository/urls")
def search_repository_urls(
    domain_id: int | None = None,
    search: str | None = None,
    service: str | None = None,
    status: str | None = None,
    source: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """
    Search and filter the archival repository:
    - Search by URL pattern or domain
    - Filter by service (wayback, archive_today, ghostarchive)
    - Filter by submission status (success, failed, pending)
    - Filter by discovery source (html, sitemap, feed, robots)
    """
    query = db.query(Url)
    if current_user:
        query = query.join(Domain).filter(Domain.user_id == current_user.id)

    if domain_id:
        query = query.filter(Url.domain_id == domain_id)

    if search and search.strip():
        search_pat = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Url.normalized_url.ilike(search_pat),
                Url.original_url.ilike(search_pat),
                Url.domain.has(Domain.domain.ilike(search_pat)),
            )
        )

    if source:
        query = query.filter(Url.discovery_source == source)

    # Filter by service and status using .any() correlated subqueries to avoid duplicate join conflicts
    if service and status:
        if status in ("success", "failed"):
            query = query.filter(
                Url.submissions.any(and_(Submission.service == service, Submission.status == status))
            )
        elif status == "pending":
            query = query.filter(
                Url.queue_items.any(
                    and_(QueueItem.service == service, QueueItem.status.in_(["pending", "in_progress"]))
                )
            )
        elif status == "modified":
            query = query.filter(Url.content_changed == True)
        elif status == "unarchived":
            query = query.filter(~Url.submissions.any(Submission.service == service))
    elif service:
        query = query.filter(
            or_(
                Url.submissions.any(Submission.service == service),
                Url.queue_items.any(QueueItem.service == service),
            )
        )
    elif status:
        if status in ("success", "failed"):
            query = query.filter(Url.submissions.any(Submission.status == status))
        elif status == "pending":
            query = query.filter(Url.queue_items.any(QueueItem.status.in_(["pending", "in_progress"])))
        elif status == "modified":
            query = query.filter(Url.content_changed == True)
        elif status == "unarchived":
            query = query.filter(~Url.submissions.any(Submission.status == "success"))

    total_count = query.distinct().count()
    offset = (page - 1) * page_size
    urls = query.distinct().order_by(Url.id.desc()).offset(offset).limit(page_size).all()

    items = []
    for u in urls:
        u_dict = u.to_dict()
        # Attach latest submissions
        latest_subs = (
            db.query(Submission)
            .filter(Submission.url_id == u.id)
            .order_by(Submission.id.desc())
            .limit(3)
            .all()
        )
        u_dict["recent_submissions"] = [s.to_dict() for s in latest_subs]

        # Check if currently active in queue
        is_queued = db.query(QueueItem).filter(
            QueueItem.url_id == u.id,
            QueueItem.status.in_(["pending", "in_progress"]),
        ).first() is not None
        u_dict["is_queued"] = is_queued

        items.append(u_dict)

    return {
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_count + page_size - 1) // page_size if total_count > 0 else 1,
        "items": items,
    }


@router.get("/urls/{url_id}/history")
def get_url_history(url_id: int, db: Session = Depends(get_db)):
    """Retrieve complete submission history for a URL."""
    url = db.query(Url).filter(Url.id == url_id).first()
    if not url:
        raise HTTPException(status_code=404, detail="URL not found.")

    subs = db.query(Submission).filter(Submission.url_id == url_id).order_by(Submission.submitted_at.desc()).all()
    queue_items = db.query(QueueItem).filter(QueueItem.url_id == url_id).order_by(QueueItem.id.desc()).all()

    return {
        "url": url.to_dict(),
        "submissions": [s.to_dict() for s in subs],
        "queue_entries": [q.to_dict() for q in queue_items],
    }


@router.get("/urls/{url_id}/availability")
async def check_url_wayback_availability(url_id: int, db: Session = Depends(get_db)):
    """Check Wayback Machine Availability API (inspired by waybackpy) for an existing snapshot."""
    url = db.query(Url).filter(Url.id == url_id).first()
    if not url:
        raise HTTPException(status_code=404, detail="URL not found.")

    from backend.app.submitters.wayback import WaybackSubmitter
    wayback = WaybackSubmitter()
    availability = await wayback.check_availability(url.normalized_url)
    return {
        "url_id": url.id,
        "normalized_url": url.normalized_url,
        "availability": availability,
    }


# --- Export Archival Repository (CSV & JSON) ---
@router.get("/export")
def export_repository(
    format: str = Query(default="csv", pattern="^(csv|json)$"),
    domain_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Export complete archival inventory in CSV or JSON format, scoped to user."""
    user_id = current_user.id if current_user else None
    if format == "csv":
        csv_data = ExportService.export_csv(db, domain_id=domain_id, user_id=user_id)
        filename = f"archive_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    else:
        json_data = ExportService.export_json(db, domain_id=domain_id, user_id=user_id)
        filename = f"archive_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        return Response(
            content=json_data,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )


# --- Bonus Features: Playwright JS rendering, Schedules, Diffing ---
@router.post("/bonus/render-page")
async def render_dynamic_page(payload: dict):
    """Render a dynamic JS page with Playwright and return rendered DOM and links."""
    url = payload.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL required.")
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    crawler = PlaywrightCrawler()
    res = await crawler.render_and_extract(url)
    return res


@router.post("/bonus/diff")
def compute_snapshot_diff(payload: dict):
    """Compare two snapshots or text versions."""
    text_a = payload.get("text_a", "")
    text_b = payload.get("text_b", "")
    label_a = payload.get("label_a", "Snapshot 1")
    label_b = payload.get("label_b", "Snapshot 2")
    return DiffService.compute_diff(text_a, text_b, from_label=label_a, to_label=label_b)


@router.post("/bonus/schedule")
def add_schedule(payload: dict, db: Session = Depends(get_db)):
    """Create or update automated recurring scan schedule for a domain."""
    domain_id = payload.get("domain_id")
    interval = payload.get("interval_minutes", 1440)  # default: daily

    if not isinstance(interval, int) or interval <= 0:
        raise HTTPException(status_code=400, detail="interval_minutes must be a positive integer.")

    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found.")

    sched = db.query(Schedule).filter(Schedule.domain_id == domain_id).first()
    now = utc_now()
    next_run = now + timedelta(minutes=interval)
    if not sched:
        sched = Schedule(
            domain_id=domain_id,
            interval_minutes=interval,
            is_active=True,
            next_run_at=next_run,
        )
        db.add(sched)
    else:
        sched.interval_minutes = interval
        sched.is_active = True
        sched.next_run_at = next_run

    db.commit()
    db.refresh(sched)
    scheduler_service.add_or_update_schedule(domain_id, interval)
    return {"status": "scheduled", "schedule": sched.to_dict()}


@router.get("/bonus/schedules")
def list_schedules(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    """List scheduled recurring scans, scoped to current user if authenticated."""
    query = db.query(Schedule)
    if current_user:
        query = query.join(Domain).filter(Domain.user_id == current_user.id)
    schedules = query.all()
    return [s.to_dict() for s in schedules]


@router.delete("/bonus/schedule/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    """Cancel and remove a recurring scheduled scan."""
    sched = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found.")
    scheduler_service.remove_schedule(sched.domain_id)
    db.delete(sched)
    db.commit()
    return {"status": "deleted", "schedule_id": schedule_id}

