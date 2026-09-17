from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from engine.agent_ops import router as agent_ops_router


def test_processed_csv_webhook_raw_body(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AGENT_OPS_QUEUE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENT_OPS_WEBHOOK_SECRET", "secret")
    app = FastAPI()
    app.include_router(agent_ops_router.router)
    client = TestClient(app)

    response = client.post(
        "/agent-ops/webhooks/processed-csv",
        content="name,email\nJane,jane@example.com\n",
        headers={
            "Content-Type": "text/csv",
            "X-Agent-Webhook-Secret": "secret",
            "X-Campaign-Name": "Founders",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job"]["campaign_name"] == "Founders"
    assert body["job"]["row_count"] == 1
    assert Path(body["job"]["csv_path"]).exists()


def test_processed_csv_webhook_rejects_bad_secret(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AGENT_OPS_QUEUE_DIR", str(tmp_path))
    monkeypatch.setenv("AGENT_OPS_WEBHOOK_SECRET", "secret")
    app = FastAPI()
    app.include_router(agent_ops_router.router)
    client = TestClient(app)

    response = client.post(
        "/agent-ops/webhooks/processed-csv",
        content="name,email\nJane,jane@example.com\n",
        headers={"Content-Type": "text/csv", "X-Agent-Webhook-Secret": "wrong"},
    )

    assert response.status_code == 401
