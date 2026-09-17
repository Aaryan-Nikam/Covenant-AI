from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException, Request

from engine.agent_ops.schemas import (
    ProcessedCsvWebhook,
    UploadJobCreated,
    UploadJobList,
    UploadJobStatusUpdate,
    VisualAgentDecisionRequest,
    VisualAgentDecisionResponse,
)
from engine.agent_ops.service import AgentOpsService
from engine.agent_ops.vision_agent import decide_next_action

router = APIRouter(prefix="/agent-ops")


def get_service() -> AgentOpsService:
    return AgentOpsService()


def verify_webhook_secret(secret: str | None) -> None:
    expected = os.getenv("AGENT_OPS_WEBHOOK_SECRET")
    if expected and secret != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook secret.")


@router.post("/webhooks/processed-csv", response_model=UploadJobCreated)
async def receive_processed_csv(
    request: Request,
    x_agent_webhook_secret: str | None = Header(default=None),
    x_campaign_name: str | None = Header(default=None),
    x_campaign_url: str | None = Header(default=None),
    x_source_project_id: str | None = Header(default=None),
    x_source_project_name: str | None = Header(default=None),
    x_idempotency_key: str | None = Header(default=None),
):
    verify_webhook_secret(x_agent_webhook_secret)
    content_type = request.headers.get("content-type", "")
    try:
        if "application/json" in content_type:
            payload = ProcessedCsvWebhook.model_validate(await request.json())
        else:
            body = (await request.body()).decode("utf-8")
            payload = ProcessedCsvWebhook(
                csv_content=body,
                campaign_name=x_campaign_name,
                campaign_url=x_campaign_url,
                source="raw_csv_webhook",
                source_project_id=x_source_project_id,
                source_project_name=x_source_project_name,
                idempotency_key=x_idempotency_key,
            )
        job = get_service().create_job(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return UploadJobCreated(job=job)


@router.get("/upload-jobs", response_model=UploadJobList)
async def list_upload_jobs():
    jobs = get_service().list_jobs()
    return UploadJobList(jobs=jobs, total=len(jobs))


@router.get("/upload-jobs/{job_id}")
async def get_upload_job(job_id: str):
    try:
        return get_service().get_job(job_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/upload-jobs/{job_id}/status")
async def update_upload_job_status(job_id: str, payload: UploadJobStatusUpdate):
    try:
        return get_service().update_job_status(
            job_id,
            status=payload.status,
            error=payload.error,
            run_log_path=payload.run_log_path,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/agent/decide", response_model=VisualAgentDecisionResponse)
async def decide_visual_agent_action(payload: VisualAgentDecisionRequest):
    return VisualAgentDecisionResponse(action=decide_next_action(payload))
