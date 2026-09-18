"""
Archival inventory export service (CSV and JSON deliverables).
"""
import io
import csv
import json
from sqlalchemy.orm import Session
from backend.app.db.models import Domain, Url, Submission


class ExportService:
    """Exports domain and archival submission records to CSV and JSON."""

    @staticmethod
    def get_inventory_rows(db: Session, domain_id: int | None = None, user_id: int | None = None) -> list[dict]:
        """Fetch joined inventory rows for export."""
        query = (
            db.query(
                Domain.domain,
                Url.original_url,
                Url.normalized_url,
                Url.discovery_source,
                Url.discovery_timestamp,
                Url.http_status,
                Url.content_hash,
                Url.content_changed,
                Submission.service,
                Submission.status.label("submission_status"),
                Submission.archive_url,
                Submission.archive_id,
                Submission.error_message,
                Submission.last_attempted,
            )
            .join(Url, Url.domain_id == Domain.id)
            .outerjoin(Submission, Submission.url_id == Url.id)
        )

        if domain_id:
            query = query.filter(Domain.id == domain_id)
        elif user_id:
            query = query.filter(Domain.user_id == user_id)

        rows = query.all()
        results = []
        for r in rows:
            results.append({
                "domain": r.domain,
                "original_url": r.original_url,
                "normalized_url": r.normalized_url,
                "discovery_source": r.discovery_source,
                "discovery_timestamp": r.discovery_timestamp.isoformat() if r.discovery_timestamp else None,
                "http_status": r.http_status,
                "content_hash": r.content_hash or "",
                "content_changed": bool(r.content_changed),
                "service": r.service or "unsubmitted",
                "submission_status": r.submission_status or "pending",
                "archive_url": r.archive_url or "",
                "archive_id": r.archive_id or "",
                "error_message": r.error_message or "",
                "last_attempted": r.last_attempted.isoformat() if r.last_attempted else None,
            })
        return results

    @staticmethod
    def export_csv(db: Session, domain_id: int | None = None, user_id: int | None = None) -> str:
        """Export inventory to CSV formatted string with formula-injection defenses."""
        rows = ExportService.get_inventory_rows(db, domain_id=domain_id, user_id=user_id)
        output = io.StringIO()
        if not rows:
            return "domain,original_url,normalized_url,discovery_source,discovery_timestamp,http_status,content_hash,content_changed,service,submission_status,archive_url,archive_id,error_message,last_attempted\n"

        # Sanitize cells to prevent CSV formula injection (=, +, -, @)
        sanitized_rows = []
        for row in rows:
            clean_row = {}
            for k, v in row.items():
                if isinstance(v, str) and len(v) > 0 and v[0] in ("=", "@", "\t", "\r"):
                    clean_row[k] = f"'{v}"
                else:
                    clean_row[k] = v
            sanitized_rows.append(clean_row)

        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sanitized_rows)
        return output.getvalue()

    @staticmethod
    def export_json(db: Session, domain_id: int | None = None, user_id: int | None = None) -> str:
        """Export inventory to indented JSON formatted string."""
        rows = ExportService.get_inventory_rows(db, domain_id=domain_id, user_id=user_id)
        return json.dumps(rows, indent=2)
