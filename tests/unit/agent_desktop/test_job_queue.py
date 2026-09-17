from __future__ import annotations

import json
from pathlib import Path

from azmeth_agent.job_queue import load_job_csv_path


def test_load_job_csv_path(tmp_path: Path) -> None:
    job_dir = tmp_path / "job-1"
    job_dir.mkdir()
    (job_dir / "metadata.json").write_text(
        json.dumps({"csv_path": "/tmp/job-1/processed-leads.csv"}),
        encoding="utf-8",
    )

    assert load_job_csv_path(tmp_path, "job-1") == Path("/tmp/job-1/processed-leads.csv")
