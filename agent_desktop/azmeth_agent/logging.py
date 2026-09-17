from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class RunEvent:
    run_id: str
    event_type: str
    payload: dict[str, Any]
    timestamp: str
    previous_hash: str
    event_hash: str


class RunLedger:
    """Append-only JSONL ledger with hash chaining for tamper evidence."""

    def __init__(self, log_dir: Path, secret: str, run_id: str | None = None) -> None:
        if not secret:
            raise ValueError("RunLedger requires a non-empty secret.")
        self.log_dir = log_dir
        self.secret = secret.encode("utf-8")
        self.run_id = run_id or str(uuid4())
        self.previous_hash = "0" * 64
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.log_dir / f"{self.run_id}.jsonl"

    def append(self, event_type: str, payload: dict[str, Any]) -> RunEvent:
        timestamp = datetime.now(UTC).isoformat()
        canonical_payload = json.dumps(payload, sort_keys=True, default=str)
        body = f"{self.run_id}|{event_type}|{timestamp}|{self.previous_hash}|{canonical_payload}"
        event_hash = hmac.new(self.secret, body.encode("utf-8"), hashlib.sha256).hexdigest()
        event = RunEvent(
            run_id=self.run_id,
            event_type=event_type,
            payload=payload,
            timestamp=timestamp,
            previous_hash=self.previous_hash,
            event_hash=event_hash,
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), sort_keys=True, default=str) + "\n")
        self.previous_hash = event_hash
        return event
