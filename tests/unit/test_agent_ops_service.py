from __future__ import annotations

from pathlib import Path

import pytest

from engine.agent_ops.schemas import ProcessedCsvWebhook
from engine.agent_ops.service import AgentOpsService, inspect_csv, normalize_csv_content


def test_create_job_stores_csv_and_metadata(tmp_path: Path) -> None:
    service = AgentOpsService(tmp_path)

    job = service.create_job(
        ProcessedCsvWebhook(
            csv_content="name,email\nJane,jane@example.com\n",
            campaign_name="Founders",
            source_project_id="project-1",
        )
    )

    assert job.status == "queued"
    assert job.campaign_name == "Founders"
    assert job.source_project_id == "project-1"
    assert job.row_count == 1
    assert job.columns == ["name", "email"]
    assert Path(job.csv_path).read_text(encoding="utf-8") == "name,email\nJane,jane@example.com\n"


def test_idempotency_key_returns_existing_job(tmp_path: Path) -> None:
    service = AgentOpsService(tmp_path)
    first = service.create_job(
        ProcessedCsvWebhook(
            csv_content="name,email\nJane,jane@example.com\n",
            idempotency_key="run-1",
        )
    )
    second = service.create_job(
        ProcessedCsvWebhook(
            csv_content="name,email\nJohn,john@example.com\n",
            idempotency_key="run-1",
        )
    )

    assert second.id == first.id
    assert Path(second.csv_path).read_text(encoding="utf-8") == "name,email\nJane,jane@example.com\n"


def test_update_job_status(tmp_path: Path) -> None:
    service = AgentOpsService(tmp_path)
    job = service.create_job(ProcessedCsvWebhook(csv_content="name,email\nJane,jane@example.com\n"))

    updated = service.update_job_status(job.id, "completed", run_log_path="/tmp/run.jsonl")

    assert updated.status == "completed"
    assert updated.run_log_path == "/tmp/run.jsonl"


def test_inspect_csv_rejects_empty_csv() -> None:
    with pytest.raises(ValueError, match="at least one lead"):
        inspect_csv("name,email\n")


def test_normalize_csv_rejects_blank_content() -> None:
    with pytest.raises(ValueError, match="empty"):
        normalize_csv_content(" \n")
