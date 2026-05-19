"""Router for the enterprise Agent Security Suite."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from engine.agent_security.schemas import (
    AgentSecurityOverviewResponse,
    AgentSecurityPolicyResponse,
    AgentSecurityPolicyUpdateRequest,
    ContextExfiltrationAnalyzeRequest,
    ContextExfiltrationAnalyzeResponse,
    MemorySessionAuditRequest,
    MemorySessionAuditResponse,
    PromptInjectionAnalyzeRequest,
    PromptInjectionAnalyzeResponse,
    SecurityDecisionEvaluateRequest,
    SecurityDecisionEvaluateResponse,
    ToolPermissionEvaluateRequest,
    ToolPermissionEvaluateResponse,
)
from engine.agent_security.service import AgentSecurityService
from engine.auth.models import Tenant
from engine.dependencies import get_db, verify_api_key

router = APIRouter(prefix="/v1/agent-security", tags=["agent-security"])


@router.get("/overview", response_model=AgentSecurityOverviewResponse)
async def agent_security_overview(
    _tenant: Tenant = Depends(verify_api_key),
):
    service = AgentSecurityService()
    return service.get_overview()


@router.get("/policy", response_model=AgentSecurityPolicyResponse)
async def get_agent_security_policy(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = AgentSecurityService(db)
    return await service.get_or_create_policy(tenant.id)


@router.put("/policy", response_model=AgentSecurityPolicyResponse)
async def update_agent_security_policy(
    body: AgentSecurityPolicyUpdateRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = AgentSecurityService(db)
    try:
        return await service.update_policy(tenant.id, body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post(
    "/decision/evaluate",
    response_model=SecurityDecisionEvaluateResponse,
)
async def evaluate_security_decision(
    body: SecurityDecisionEvaluateRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = AgentSecurityService(db)
    return await service.evaluate_decision(tenant.id, body)


@router.post(
    "/prompt-injection/analyze",
    response_model=PromptInjectionAnalyzeResponse,
)
async def analyze_prompt_injection(
    body: PromptInjectionAnalyzeRequest,
    _tenant: Tenant = Depends(verify_api_key),
):
    service = AgentSecurityService()
    return service.analyze_prompt_injection(body)


@router.post(
    "/context-exfiltration/analyze",
    response_model=ContextExfiltrationAnalyzeResponse,
)
async def analyze_context_exfiltration(
    body: ContextExfiltrationAnalyzeRequest,
    _tenant: Tenant = Depends(verify_api_key),
):
    service = AgentSecurityService()
    return service.analyze_context_exfiltration(body)


@router.post(
    "/tool-permissions/evaluate",
    response_model=ToolPermissionEvaluateResponse,
)
async def evaluate_tool_permissions(
    body: ToolPermissionEvaluateRequest,
    _tenant: Tenant = Depends(verify_api_key),
):
    service = AgentSecurityService()
    return service.evaluate_tool_permissions(body)


@router.post(
    "/memory/audit",
    response_model=MemorySessionAuditResponse,
)
async def audit_memory_session(
    body: MemorySessionAuditRequest,
    _tenant: Tenant = Depends(verify_api_key),
):
    service = AgentSecurityService()
    return service.audit_memory_session(body)
