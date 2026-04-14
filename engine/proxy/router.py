"""
Proxy router — two sets of endpoints:

Set 1: Transparent OpenAI proxy (Option B — primary)
    POST /openai/v1/chat/completions
    → Drop-in replacement for OpenAI API
    → Customer changes one URL, zero other changes
    → Handles OpenAI message format natively

Set 2: Explicit scan endpoint (kept for direct SDK use)
    POST /proxy/scan
    → Original endpoint from architecture.md
    → For agents that want explicit control
    GET  /proxy/rulesets
    GET  /proxy/rulesets/{id}

Both sets go through the same compliance pipeline.
Authentication is the same for both.
"""

from fastapi import APIRouter, Request, Header, HTTPException, BackgroundTasks, Depends
from typing import Annotated

from slowapi import Limiter
from slowapi.util import get_remote_address

from engine.dependencies import verify_api_key, get_interceptor, get_forwarder, Tenant, get_registry
from engine.rulesets.registry import RulesetRegistry
from engine.exceptions import RulesetNotFoundError
from engine.proxy.extractors.openai import OpenAIContentExtractor
from engine.proxy.extractors.anthropic import AnthropicContentExtractor
from engine.proxy.extractors.google import GoogleContentExtractor
from engine.proxy.forwarder import OpenAIForwarder
from engine.proxy.interceptor import ProxyInterceptor
from engine.proxy.request_model import (
    OpenAIProxyRequest,
    ScanRequest,
    ScanResponse,
    ComplianceViolationError,
)
from engine.exceptions import ComplianceViolation

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# Provider-specific extractors — instantiated once, stateless
_openai_extractor = OpenAIContentExtractor()
_anthropic_extractor = AnthropicContentExtractor()
_google_extractor = GoogleContentExtractor()


# ---------------------------------------------------------------------------
# TRANSPARENT OPENAI PROXY — Primary endpoint
# ---------------------------------------------------------------------------

@router.post("/openai/v1/chat/completions")
@limiter.limit("200/minute")  # Runaway agent protection — 429 if exceeded
async def openai_chat_completions_proxy(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: Annotated[str, Header()],
    x_openai_key: Annotated[str, Header(alias="X-OpenAI-Key")],
    tenant: Tenant = Depends(verify_api_key),
    interceptor: ProxyInterceptor = Depends(get_interceptor),
    forwarder: OpenAIForwarder = Depends(get_forwarder),
):
    """
    Transparent drop-in proxy for OpenAI chat completions.

    Customer integration:
        base_url = "https://api.ironpass.io/openai"
        default_headers = {
            "Authorization": "Bearer dbnc_live_xxxx",
            "X-OpenAI-Key": "sk-openai-xxxx"
        }

    The X-OpenAI-Key header:
        - Is used to forward the request to OpenAI
        - Is NEVER stored in any database
        - Is logged ONLY as present/absent (never the actual value)
        - Is stripped from all audit log entries
    """

    # Parse request body
    body = await request.json()

    # Streaming is incompatible with compliance de-tokenization.
    # We always get the full response, de-tokenize, then return.
    # Clients requesting stream=True get a non-streamed compliant response.
    body.pop("stream", None)

    messages = body.get("messages", [])

    if not messages:
        raise HTTPException(400, {"error": "messages array is required"})

    # Extract text content from OpenAI messages format
    combined_content, segments = _openai_extractor.extract(body)

    # Run through compliance pipeline
    try:
        result = await interceptor.process_request(
            content=combined_content,
            agent_id=tenant.agent_id,
            tenant_id=tenant.id,
            target_url="https://api.openai.com/v1/chat/completions",
            metadata={
                "model": body.get("model", "unknown"),
                "message_count": len(messages),
                "openai_key_present": bool(x_openai_key),
                # NEVER log the actual key value
            },
            active_rulesets=tenant.active_rulesets,
        )

    except ComplianceViolation as e:
        # Hard block — do not forward to OpenAI
        # Log the block as background task
        background_tasks.add_task(
            interceptor.audit_logger.write_block,
            agent_id=tenant.agent_id,
            reason=str(e),
            rulesets_used=tenant.active_rulesets,
        )
        raise HTTPException(400, {
            "error": {
                "type": "compliance_violation",
                "code": "CONTENT_BLOCKED",
                "message": "Request blocked by active compliance policy",
                "violations": [v.dict() for v in e.violations],
                "ironpass_request_id": e.request_id,
            }
        })

    # Rebuild sanitized messages array
    sanitized_body = _openai_extractor.rebuild(
        body=body,
        segments=segments,
        sanitized_combined=result.sanitized_content,
    )

    # Forward sanitized request to real OpenAI
    forward_result = await forwarder.forward(
        path="/v1/chat/completions",
        payload=sanitized_body,
        openai_api_key=x_openai_key,
    )

    # Write audit log as background task — never blocks response
    background_tasks.add_task(
        interceptor.audit_logger.write,
        agent_id=tenant.agent_id,
        request_hash=result.request_hash,
        rulesets_used=tenant.active_rulesets,
        detections=result.detections,
        actions_taken=result.actions_taken,
        was_blocked=False,
        target_url="https://api.openai.com/v1/chat/completions",
        latency_ms=forward_result.latency_ms,
        outcome="passed",
    )

    # Handle upstream errors
    if not forward_result.success:
        raise HTTPException(
            forward_result.status_code,
            {
                "error": {
                    "type": forward_result.error_type,
                    "message": forward_result.error_message,
                }
            }
        )

    # De-tokenize response from OpenAI
    openai_response = forward_result.response_body
    response_content = (
        openai_response
        .get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )

    if response_content and getattr(result, "session_token_map", None):
        detokenized = await interceptor.process_response(
            response_content=response_content,
            session_token_map=result.session_token_map,
            agent_id=tenant.agent_id,
        )
        openai_response["choices"][0]["message"]["content"] = detokenized

    # Return standard OpenAI format — agent cannot tell this went through Ironpass
    return openai_response


# ---------------------------------------------------------------------------
# ANTHROPIC PROXY — Claude models
# ---------------------------------------------------------------------------

@router.post("/anthropic/v1/messages")
@limiter.limit("200/minute")
async def anthropic_messages_proxy(
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: Annotated[str, Header()],
    x_anthropic_key: Annotated[str, Header(alias="X-Anthropic-Key")],
    tenant: Tenant = Depends(verify_api_key),
    interceptor: ProxyInterceptor = Depends(get_interceptor),
):
    """
    Transparent proxy for Anthropic Messages API (Claude).

    Customer integration:
        base_url = "https://api.ironpass.io/anthropic"
        default_headers = {
            "Authorization": "Bearer dbnc_live_xxxx",
            "X-Anthropic-Key": "sk-ant-xxxx"
        }
    """
    body = await request.json()
    if not body.get("messages"):
        raise HTTPException(400, {"error": "messages array is required"})

    combined_content, segments = _anthropic_extractor.extract(body)

    try:
        result = await interceptor.process_request(
            content=combined_content,
            agent_id=tenant.agent_id,
            tenant_id=tenant.id,
            target_url="https://api.anthropic.com/v1/messages",
            active_rulesets=tenant.active_rulesets,
        )
    except ComplianceViolation as e:
        raise HTTPException(400, {
            "error": {
                "type": "compliance_violation",
                "code": "CONTENT_BLOCKED",
                "message": "Request blocked by active compliance policy",
                "violations": [v.dict() for v in e.violations],
            }
        })

    sanitized_body = _anthropic_extractor.rebuild(
        body=body,
        segments=segments,
        sanitized_combined=result.sanitized_content,
    )

    # Forward to Anthropic
    import httpx
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            json=sanitized_body,
            headers={
                "x-api-key": x_anthropic_key,
                "anthropic-version": request.headers.get("anthropic-version", "2023-06-01"),
                "content-type": "application/json",
            },
        )

    background_tasks.add_task(
        interceptor.audit_logger.write,
        agent_id=tenant.agent_id,
        request_hash=result.request_hash,
        rulesets_used=tenant.active_rulesets,
        detections=result.detections,
        actions_taken=result.actions_taken,
        was_blocked=False,
        target_url="https://api.anthropic.com/v1/messages",
        latency_ms=0,
        outcome="passed",
    )

    return resp.json()


# ---------------------------------------------------------------------------
# GOOGLE PROXY — Gemini models
# ---------------------------------------------------------------------------

@router.post("/google/v1/models/{model}:generateContent")
@limiter.limit("200/minute")
async def google_generate_content_proxy(
    model: str,
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: Annotated[str, Header()],
    x_google_key: Annotated[str, Header(alias="X-Google-Key")],
    tenant: Tenant = Depends(verify_api_key),
    interceptor: ProxyInterceptor = Depends(get_interceptor),
):
    """
    Transparent proxy for Google Generative Language API (Gemini).

    Customer integration:
        base_url = "https://api.ironpass.io/google"
        default_headers = {
            "Authorization": "Bearer dbnc_live_xxxx",
            "X-Google-Key": "AIza..."
        }
    """
    body = await request.json()
    if not body.get("contents"):
        raise HTTPException(400, {"error": "contents array is required"})

    combined_content, segments = _google_extractor.extract(body)

    try:
        result = await interceptor.process_request(
            content=combined_content,
            agent_id=tenant.agent_id,
            tenant_id=tenant.id,
            target_url=f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent",
            active_rulesets=tenant.active_rulesets,
        )
    except ComplianceViolation as e:
        raise HTTPException(400, {
            "error": {
                "type": "compliance_violation",
                "code": "CONTENT_BLOCKED",
                "message": "Request blocked by active compliance policy",
            }
        })

    sanitized_body = _google_extractor.rebuild(
        body=body,
        segments=segments,
        sanitized_combined=result.sanitized_content,
    )

    # Forward to Google
    import httpx
    target = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent"
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            target,
            json=sanitized_body,
            params={"key": x_google_key},
            headers={"content-type": "application/json"},
        )

    background_tasks.add_task(
        interceptor.audit_logger.write,
        agent_id=tenant.agent_id,
        request_hash=result.request_hash,
        rulesets_used=tenant.active_rulesets,
        detections=result.detections,
        actions_taken=result.actions_taken,
        was_blocked=False,
        target_url=target,
        latency_ms=0,
        outcome="passed",
    )

    return resp.json()


# ---------------------------------------------------------------------------
# EXPLICIT SCAN ENDPOINT — Secondary, for direct SDK use
# ---------------------------------------------------------------------------

@router.post("/proxy/scan", response_model=ScanResponse)
@limiter.limit("200/minute")
async def explicit_scan(
    request: Request,
    request_body: ScanRequest,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(verify_api_key),
    interceptor: ProxyInterceptor = Depends(get_interceptor),
):
    """
    Explicit scan endpoint for agents that want direct control.
    Returns sanitized content without forwarding to any upstream.
    Agent decides what to do with sanitized content.
    """
    try:
        result = await interceptor.process_request(
            content=request_body.content,
            agent_id=tenant.agent_id,
            tenant_id=tenant.id,
            target_url=str(request_body.target_url) if request_body.target_url else None,
            metadata=request_body.metadata,
            active_rulesets=request_body.rulesets or tenant.active_rulesets,
        )
    except ComplianceViolation as e:
        raise HTTPException(400, ComplianceViolationError(
            violations=e.violations,
            request_id=e.request_id,
        ).dict())

    background_tasks.add_task(
        interceptor.audit_logger.write,
        agent_id=tenant.agent_id,
        request_hash=result.request_hash,
        rulesets_used=result.rulesets_used,
        detections=result.detections,
        actions_taken=result.actions_taken,
        was_blocked=result.was_blocked,
        target_url=str(request_body.target_url) if request_body.target_url else None,
        latency_ms=result.latency_ms,
        outcome="blocked" if result.was_blocked else "passed",
    )

    return ScanResponse(
        sanitized_content=result.sanitized_content,
        violations=result.violations,
        was_blocked=result.was_blocked,
        audit_id=result.audit_id,
        session_id=result.session_id,
        latency_ms=result.latency_ms,
    )


# ---------------------------------------------------------------------------
# RULESET INFO ENDPOINTS
# ---------------------------------------------------------------------------

@router.get("/proxy/rulesets")
async def list_rulesets(
    tenant: Tenant = Depends(verify_api_key),
    registry: RulesetRegistry = Depends(get_registry)
):
    """Returns all available rulesets and which are active for this tenant"""
    all_rulesets = registry.list_all()
    response = []
    
    for rs in all_rulesets:
        response.append({
            "id": rs.ruleset_id,
            "name": rs.name,
            "description": rs.description,
            "is_active": rs.ruleset_id in tenant.active_rulesets,
            "detector_count": len(rs.detectors),
        })
        
    return {"rulesets": response}


@router.get("/proxy/rulesets/{ruleset_id}")
async def get_ruleset(
    ruleset_id: str,
    tenant: Tenant = Depends(verify_api_key),
    registry: RulesetRegistry = Depends(get_registry)
):
    """Returns full ruleset config for inspection"""
    try:
        ruleset = registry.get(ruleset_id)
        return ruleset.model_dump()
    except RulesetNotFoundError:
        raise HTTPException(status_code=404, detail="Ruleset not found")


# ---------------------------------------------------------------------------
# HEALTH CHECK — No auth required
# ---------------------------------------------------------------------------

@router.get("/health")
async def health_check(
    interceptor: ProxyInterceptor = Depends(get_interceptor),
):
    """
    Load balancer hits this every 30 seconds.
    Returns 200 if system is healthy.
    Returns 503 if any critical component is down.
    """
    db_status = await check_database_connection()
    vault_status = await check_vault_connection()

    all_healthy = db_status and vault_status

    response = {
        "status": "healthy" if all_healthy else "degraded",
        "version": "1.0.0",
        "components": {
            "database": "ok" if db_status else "error",
            "vault": "ok" if vault_status else "error",
        }
    }

    if not all_healthy:
         raise HTTPException(503, response)

    return response


async def check_database_connection() -> bool:
    """Ping the database. Returns True if reachable."""
    try:
        from engine.database.connection import get_session_factory
        from sqlalchemy import text
        async_session = get_session_factory()
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


async def check_vault_connection() -> bool:
    """Check vault is accessible. Returns True if reachable."""
    try:
        from engine.vault.key_manager import KeyManager
        km = KeyManager()
        await km.get_current_key()
        return True
    except Exception:
        return False
