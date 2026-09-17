from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class ProcessedCsvWebhook(BaseModel):
    csv_content: str = Field(min_length=1)
    campaign_name: str | None = None
    campaign_url: str | None = None
    source: str | None = None
    source_project_id: str | None = None
    source_project_name: str | None = None
    idempotency_key: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class UploadJobSummary(BaseModel):
    id: str
    status: JobStatus
    created_at: str
    updated_at: str
    campaign_name: str | None
    campaign_url: str | None
    source: str | None
    source_project_id: str | None
    source_project_name: str | None
    row_count: int
    columns: list[str]
    csv_path: str
    error: str | None = None
    run_log_path: str | None = None


class UploadJobList(BaseModel):
    jobs: list[UploadJobSummary]
    total: int


class UploadJobCreated(BaseModel):
    job: UploadJobSummary


class UploadJobStatusUpdate(BaseModel):
    status: JobStatus
    error: str | None = None
    run_log_path: str | None = None


class VisualAgentDecisionRequest(BaseModel):
    screenshot_data_url: str
    instruction: str
    current_url: str | None = None
    visible_text: str | None = None
    campaign_name: str | None = None
    clickable_targets: list[dict[str, str | int | None]] = Field(default_factory=list)
    step_index: int = 0
    history: list[str] = Field(default_factory=list)


class VisualAgentAction(BaseModel):
    action_type: Literal[
        "click",
        "click_target",
        "click_text",
        "type_text",
        "scroll",
        "wait",
        "complete",
        "escalate",
    ]
    reason: str
    x: int | None = None
    y: int | None = None
    target_text: str | None = None
    target_index: int | None = None
    text: str | None = None
    delta_y: int | None = None
    seconds: float | None = None
    message: str | None = None


class VisualAgentDecisionResponse(BaseModel):
    action: VisualAgentAction
