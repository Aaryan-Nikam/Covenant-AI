from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from engine.agent_ops.schemas import JobStatus, ProcessedCsvWebhook, UploadJobSummary


DEFAULT_QUEUE_DIR = Path(os.getenv("AGENT_OPS_QUEUE_DIR", "/tmp/azmeth-agent/upload-jobs"))
MAX_CSV_BYTES = int(os.getenv("AGENT_OPS_MAX_CSV_BYTES", "10000000"))


@dataclass(frozen=True)
class CsvInspection:
    row_count: int
    columns: list[str]
    content_hash: str


class AgentOpsService:
    def __init__(self, queue_dir: Path = DEFAULT_QUEUE_DIR) -> None:
        self.queue_dir = queue_dir
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def create_job(self, payload: ProcessedCsvWebhook) -> UploadJobSummary:
        csv_content = normalize_csv_content(payload.csv_content)
        inspection = inspect_csv(csv_content)
        if payload.idempotency_key:
            existing = self._find_by_idempotency_key(payload.idempotency_key)
            if existing:
                return existing

        job_id = str(uuid4())
        now = timestamp()
        job_dir = self.queue_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        csv_path = job_dir / "processed-leads.csv"
        meta_path = job_dir / "metadata.json"
        csv_path.write_text(csv_content, encoding="utf-8", newline="")
        metadata = {
            "id": job_id,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "campaign_name": payload.campaign_name,
            "campaign_url": payload.campaign_url,
            "source": payload.source,
            "source_project_id": payload.source_project_id,
            "source_project_name": payload.source_project_name,
            "row_count": inspection.row_count,
            "columns": inspection.columns,
            "csv_path": str(csv_path),
            "content_hash": inspection.content_hash,
            "idempotency_key": payload.idempotency_key,
            "metadata": payload.metadata,
            "error": None,
            "run_log_path": None,
        }
        meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        return summary_from_metadata(metadata)

    def list_jobs(self) -> list[UploadJobSummary]:
        jobs = []
        for meta_path in self.queue_dir.glob("*/metadata.json"):
            try:
                jobs.append(summary_from_metadata(json.loads(meta_path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError, KeyError, TypeError):
                continue
        return sorted(jobs, key=lambda job: job.created_at, reverse=True)

    def get_job(self, job_id: str) -> UploadJobSummary:
        return summary_from_metadata(self._read_metadata(job_id))

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error: str | None = None,
        run_log_path: str | None = None,
    ) -> UploadJobSummary:
        metadata = self._read_metadata(job_id)
        metadata["status"] = status
        metadata["updated_at"] = timestamp()
        metadata["error"] = error
        if run_log_path is not None:
            metadata["run_log_path"] = run_log_path
        self._metadata_path(job_id).write_text(
            json.dumps(metadata, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return summary_from_metadata(metadata)

    def _find_by_idempotency_key(self, key: str) -> UploadJobSummary | None:
        for meta_path in self.queue_dir.glob("*/metadata.json"):
            try:
                metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if metadata.get("idempotency_key") == key:
                return summary_from_metadata(metadata)
        return None

    def _metadata_path(self, job_id: str) -> Path:
        path = self.queue_dir / job_id / "metadata.json"
        if not path.exists():
            raise FileNotFoundError(f"Upload job not found: {job_id}")
        return path

    def _read_metadata(self, job_id: str) -> dict[str, Any]:
        return json.loads(self._metadata_path(job_id).read_text(encoding="utf-8"))


def normalize_csv_content(content: str) -> str:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    encoded = normalized.encode("utf-8")
    if len(encoded) > MAX_CSV_BYTES:
        raise ValueError("CSV exceeds configured size limit.")
    if not normalized.strip():
        raise ValueError("CSV is empty.")
    return normalized if normalized.endswith("\n") else f"{normalized}\n"


def inspect_csv(content: str) -> CsvInspection:
    reader = csv.DictReader(content.splitlines())
    columns = list(reader.fieldnames or [])
    if not columns:
        raise ValueError("CSV header row is required.")
    row_count = 0
    for _row in reader:
        row_count += 1
    if row_count == 0:
        raise ValueError("CSV must contain at least one lead row.")
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return CsvInspection(row_count=row_count, columns=columns, content_hash=content_hash)


def summary_from_metadata(metadata: dict[str, Any]) -> UploadJobSummary:
    return UploadJobSummary(
        id=metadata["id"],
        status=metadata["status"],
        created_at=metadata["created_at"],
        updated_at=metadata["updated_at"],
        campaign_name=metadata.get("campaign_name"),
        campaign_url=metadata.get("campaign_url"),
        source=metadata.get("source"),
        source_project_id=metadata.get("source_project_id"),
        source_project_name=metadata.get("source_project_name"),
        row_count=int(metadata.get("row_count") or 0),
        columns=list(metadata.get("columns") or []),
        csv_path=metadata["csv_path"],
        error=metadata.get("error"),
        run_log_path=metadata.get("run_log_path"),
    )


def timestamp() -> str:
    return datetime.now(UTC).isoformat()
