from __future__ import annotations

import json
from pathlib import Path

from azmeth_agent.logging import RunLedger


def test_run_ledger_hash_chains_events(tmp_path: Path) -> None:
    ledger = RunLedger(tmp_path, secret="test-secret", run_id="run-1")
    first = ledger.append("first", {"value": 1})
    second = ledger.append("second", {"value": 2})

    assert second.previous_hash == first.event_hash

    lines = [json.loads(line) for line in ledger.path.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["previous_hash"] == "0" * 64
    assert lines[1]["previous_hash"] == lines[0]["event_hash"]
