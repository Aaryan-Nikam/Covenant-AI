from __future__ import annotations

import json
from pathlib import Path


def load_job_csv_path(queue_dir: Path, job_id: str) -> Path:
    metadata_path = queue_dir.expanduser() / job_id / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Upload job metadata not found: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    csv_path = metadata.get("csv_path")
    if not isinstance(csv_path, str) or not csv_path:
        raise ValueError(f"Upload job {job_id} is missing csv_path.")
    return Path(csv_path)
