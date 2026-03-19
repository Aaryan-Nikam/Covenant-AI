# Ironpass — Option B: Transparent Drop-In Proxy
# Production Plan + Coding Agent Prompt
# =========================================
# Give this file to your coding agent alongside architecture.md
# This supersedes the proxy router described in architecture.md
# Everything else in architecture.md remains unchanged

---

## What We're Building (One Paragraph)

Ironpass positions itself as a transparent drop-in replacement for the OpenAI API.
The customer changes ONE line of code — their base URL. Everything else in their
agent stays identical. Ironpass intercepts the request, scans it, sanitizes it,
forwards it to the real OpenAI, de-tokenizes the response, and returns it in
standard OpenAI format. The agent never knows Ironpass is in the middle.

---

## The One Line Change For The Customer

BEFORE Ironpass:
```python
client = OpenAI(
    api_key="sk-openai-xxxx",
    base_url="https://api.openai.com"
)
```

AFTER Ironpass (one line changed):
```python
client = OpenAI(
    api_key="sk-openai-xxxx",
    base_url="https://api.ironpass.io/openai",
    default_headers={
        "Authorization": "Bearer dbnc_live_xxxx",   # Ironpass API key
        "X-OpenAI-Key": "sk-openai-xxxx"            # Their OpenAI key passed through
    }
)
```

That is the entire integration. No SDK. No code changes. No new libraries.

---

## Authentication Design

Two separate keys travel with every request:

```
Header 1: Authorization: Bearer dbnc_live_xxxx
          → Identifies the tenant in Ironpass
          → Ironpass verifies this, loads ruleset config
          → NEVER forwarded to OpenAI

Header 2: X-OpenAI-Key: sk-openai-xxxx
          → Customer's real OpenAI API key
          → NEVER stored by Ironpass
          → Used only to forward the sanitized request to OpenAI
          → Logged only as "present" or "absent" in audit log
          → Stripped from any logs, never written to DB
```

Why this design:
- Ironpass never stores the customer's OpenAI key (zero liability)
- Customer controls their own OpenAI billing directly
- Security team can verify: "your OpenAI key never rests on their servers"
- Easy to rotate either key independently

---

## Complete Request/Response Flow

```
[Customer Agent]
      │
      │ POST https://api.ironpass.io/openai/v1/chat/completions
      │ Authorization: Bearer dbnc_live_xxxx
      │ X-OpenAI-Key: sk-openai-xxxx
      │ Content-Type: application/json
      │ Body: standard OpenAI chat completions payload
      ↓
[AWS ALB + Nginx]
      │ SSL termination
      │ Rate limiting: 100 req/min per IP, burst 20
      │ Health check routing
      ↓
[Ironpass Proxy — FastAPI]
      │
      ├─ Step 1: Verify Authorization header → identify tenant
      ├─ Step 2: Extract X-OpenAI-Key (use only, never store)
      ├─ Step 3: Parse OpenAI messages[] array
      ├─ Step 4: Extract all text content from messages
      ├─ Step 5: ContentNormalizer → strip evasion characters
      ├─ Step 6: DetectionEngine → scan active rulesets
      ├─ Step 7: ActionExecutor → tokenize/mask/block
      ├─ Step 8: AuditLogger.write() → background task
      ├─ Step 9: If BLOCKED → return 400 ComplianceViolation, stop
      ├─ Step 10: Rebuild sanitized messages[] array
      │
      │ POST https://api.openai.com/v1/chat/completions
      │ Authorization: Bearer {X-OpenAI-Key}
      │ Body: sanitized payload (tokens replacing real data)
      ↓
[Real OpenAI API]
      │ Processes sanitized content
      │ Never sees card numbers, SSNs, CVVs
      │ Sees: "charge TOK_CARD_a4f2b891 for order"
      ↓
[Ironpass Proxy — response path]
      │
      ├─ Step 11: Receive OpenAI response
      ├─ Step 12: Extract response content
      ├─ Step 13: De-tokenize (restore tokens to display-safe values)
      ├─ Step 14: Rebuild response in standard OpenAI format
      │
      ↓
[Customer Agent]
      Receives standard OpenAI response
      Sees display-safe values (last 4 of card, etc.)
      Zero code changes beyond the base_url
```

---

## New Files To Build

These are NEW files. They replace or extend the proxy described in architecture.md.
Everything else (detection, vault, audit, rulesets) is unchanged.

```
engine/proxy/
├── router.py                ← ADD new /openai/* endpoints (keep existing /proxy/scan)
├── content_extractor.py     ← NEW: extract/rebuild OpenAI message format
├── forwarder.py             ← NEW: async HTTP client to forward to OpenAI
├── interceptor.py           ← UNCHANGED: core pipeline logic
└── request_model.py         ← ADD: OpenAI-format request/response models
```

---

## File: engine/proxy/content_extractor.py

```python
"""
Extracts text content from OpenAI message format for scanning.
Rebuilds sanitized messages array after scanning.

OpenAI messages format:
[
    {"role": "system", "content": "You are a helpful assistant"},
    {"role": "user", "content": "Charge card 4111111111111111"},
    {"role": "assistant", "content": "I'll process that payment"}
]

Content can also be an array (vision API):
[
    {"role": "user", "content": [
        {"type": "text", "text": "Here is my card: 4111111111111111"},
        {"type": "image_url", "image_url": {"url": "..."}}
    ]}
]

Rules:
- Extract ALL text content from ALL messages
- Preserve role and position information for rebuilding
- Handle both string content and array content
- Never modify image_url content
- Track position of each extracted text segment for rebuilding
"""

from dataclasses import dataclass


@dataclass
class TextSegment:
    """A piece of text extracted from the messages array"""
    message_index: int          # Which message this came from
    content_index: int | None   # If content is array, which item
    original_text: str          # The raw text before scanning
    sanitized_text: str | None  # Set after scanning, None until then


class ContentExtractor:

    def extract(self, messages: list[dict]) -> tuple[str, list[TextSegment]]:
        """
        Extracts all text from messages array.

        Returns:
            combined_content: str
                Single string of all text concatenated with newlines.
                This is what gets passed to the DetectionEngine.

            segments: list[TextSegment]
                Ordered list of where each piece of text came from.
                Used by rebuild() to put sanitized text back in the right place.
        """
        segments = []
        text_parts = []

        for msg_idx, message in enumerate(messages):
            content = message.get("content", "")

            if isinstance(content, str):
                # Simple string content
                segment = TextSegment(
                    message_index=msg_idx,
                    content_index=None,
                    original_text=content,
                    sanitized_text=None
                )
                segments.append(segment)
                text_parts.append(content)

            elif isinstance(content, list):
                # Array content (vision API, tool results, etc.)
                for content_idx, content_item in enumerate(content):
                    if content_item.get("type") == "text":
                        text = content_item.get("text", "")
                        segment = TextSegment(
                            message_index=msg_idx,
                            content_index=content_idx,
                            original_text=text,
                            sanitized_text=None
                        )
                        segments.append(segment)
                        text_parts.append(text)
                    # Skip image_url and other non-text types
                    # They are passed through unchanged

        combined = "\n---\n".join(text_parts)
        return combined, segments

    def rebuild(
        self,
        messages: list[dict],
        segments: list[TextSegment],
        sanitized_combined: str,
    ) -> list[dict]:
        """
        Rebuilds the messages array with sanitized content.

        Takes the sanitized combined string, splits it back by the
        separator used in extract(), and maps each piece back to
        the correct message and content position.

        Returns a new messages array — never mutates the original.
        """
        # Split sanitized content back into segments
        sanitized_parts = sanitized_combined.split("\n---\n")

        # Map sanitized text back to segments
        for i, segment in enumerate(segments):
            if i < len(sanitized_parts):
                segment.sanitized_text = sanitized_parts[i]
            else:
                # Fallback: keep original if mapping fails
                segment.sanitized_text = segment.original_text

        # Build segment lookup: (message_index, content_index) -> sanitized_text
        segment_map = {
            (s.message_index, s.content_index): s.sanitized_text
            for s in segments
        }

        # Rebuild messages array
        import copy
        rebuilt = copy.deepcopy(messages)

        for msg_idx, message in enumerate(rebuilt):
            content = message.get("content", "")

            if isinstance(content, str):
                key = (msg_idx, None)
                if key in segment_map:
                    message["content"] = segment_map[key]

            elif isinstance(content, list):
                for content_idx, content_item in enumerate(content):
                    if content_item.get("type") == "text":
                        key = (msg_idx, content_idx)
                        if key in segment_map:
                            content_item["text"] = segment_map[key]

        return rebuilt
```

---

## File: engine/proxy/forwarder.py

```python
"""
Forwards sanitized requests to the real OpenAI API.
Handles timeouts, retries, and error translation.

Rules:
- Use httpx AsyncClient — never requests (blocking)
- 30 second timeout on all requests
- Retry ONCE on 429 (rate limit) after 1 second delay
- Never retry on 4xx errors (except 429) — they are agent errors
- Never retry on 5xx more than once — OpenAI problem, not ours
- Never expose OpenAI error details directly — translate them
- Always include latency in the return value
- X-OpenAI-Key is used here and only here — never stored, never logged in full
"""

import httpx
import asyncio
import time
from dataclasses import dataclass


OPENAI_BASE_URL = "https://api.openai.com"
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES_ON_RATE_LIMIT = 1
RATE_LIMIT_RETRY_DELAY_SECONDS = 1


@dataclass
class ForwardResult:
    success: bool
    response_body: dict | None
    status_code: int
    latency_ms: int
    error_type: str | None        # None on success
    error_message: str | None     # None on success


class OpenAIForwarder:

    async def forward(
        self,
        path: str,                  # e.g. "/v1/chat/completions"
        payload: dict,              # Sanitized OpenAI payload
        openai_api_key: str,        # Customer's OpenAI key — use, never store
        additional_headers: dict = {},
    ) -> ForwardResult:
        """
        Forwards sanitized payload to OpenAI.
        Returns ForwardResult with response or structured error.
        """
        url = f"{OPENAI_BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {openai_api_key}",
            "Content-Type": "application/json",
            **additional_headers
        }

        start_time = time.monotonic()

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            try:
                response = await self._send_with_retry(
                    client=client,
                    url=url,
                    payload=payload,
                    headers=headers,
                )

                latency_ms = int((time.monotonic() - start_time) * 1000)

                return ForwardResult(
                    success=True,
                    response_body=response.json(),
                    status_code=response.status_code,
                    latency_ms=latency_ms,
                    error_type=None,
                    error_message=None,
                )

            except httpx.TimeoutException:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                return ForwardResult(
                    success=False,
                    response_body=None,
                    status_code=504,
                    latency_ms=latency_ms,
                    error_type="upstream_timeout",
                    error_message="AI provider did not respond in time",
                )

            except httpx.HTTPStatusError as e:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                return ForwardResult(
                    success=False,
                    response_body=None,
                    status_code=502,
                    latency_ms=latency_ms,
                    error_type="upstream_error",
                    error_message="AI provider returned an error",
                )

            except Exception as e:
                latency_ms = int((time.monotonic() - start_time) * 1000)
                return ForwardResult(
                    success=False,
                    response_body=None,
                    status_code=500,
                    latency_ms=latency_ms,
                    error_type="internal_error",
                    error_message="Unexpected error forwarding request",
                )

    async def _send_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        payload: dict,
        headers: dict,
    ) -> httpx.Response:
        """
        Sends request. Retries once on 429.
        Raises httpx.HTTPStatusError on non-retryable errors.
        """
        for attempt in range(MAX_RETRIES_ON_RATE_LIMIT + 1):
            response = await client.post(url, json=payload, headers=headers)

            if response.status_code == 429 and attempt == 0:
                # Rate limited — wait and retry once
                await asyncio.sleep(RATE_LIMIT_RETRY_DELAY_SECONDS)
                continue

            response.raise_for_status()
            return response

        # Should not reach here
        response.raise_for_status()
        return response
```

---

## File: engine/proxy/router.py — Full Updated Version

```python
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

from engine.dependencies import verify_api_key, get_interceptor, get_forwarder
from engine.proxy.content_extractor import ContentExtractor
from engine.proxy.forwarder import OpenAIForwarder
from engine.proxy.interceptor import ProxyInterceptor
from engine.proxy.request_model import (
    OpenAIProxyRequest,
    ScanRequest,
    ScanResponse,
    ComplianceViolationError,
)
from engine.models import Tenant
from engine.exceptions import ComplianceViolation

router = APIRouter()
extractor = ContentExtractor()


# ---------------------------------------------------------------------------
# TRANSPARENT OPENAI PROXY — Primary endpoint
# ---------------------------------------------------------------------------

@router.post("/openai/v1/chat/completions")
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
    messages = body.get("messages", [])

    if not messages:
        raise HTTPException(400, {"error": "messages array is required"})

    # Extract text content from OpenAI messages format
    combined_content, segments = extractor.extract(messages)

    # Run through compliance pipeline
    try:
        result = await interceptor.process_request(
            content=combined_content,
            agent_id=tenant.agent_id,
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
    sanitized_messages = extractor.rebuild(
        messages=messages,
        segments=segments,
        sanitized_combined=result.sanitized_content,
    )

    # Build sanitized OpenAI payload
    sanitized_body = {**body, "messages": sanitized_messages}

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

    if response_content and result.session_token_map:
        detokenized = await interceptor.process_response(
            response_content=response_content,
            session_token_map=result.session_token_map,
            agent_id=tenant.agent_id,
        )
        openai_response["choices"][0]["message"]["content"] = detokenized

    # Return standard OpenAI format — agent cannot tell this went through Ironpass
    return openai_response


# ---------------------------------------------------------------------------
# EXPLICIT SCAN ENDPOINT — Secondary, for direct SDK use
# ---------------------------------------------------------------------------

@router.post("/proxy/scan", response_model=ScanResponse)
async def explicit_scan(
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
async def list_rulesets(tenant: Tenant = Depends(verify_api_key)):
    """Returns all available rulesets and which are active for this tenant"""
    pass  # Implement: return registry.list_all() with active flags


@router.get("/proxy/rulesets/{ruleset_id}")
async def get_ruleset(
    ruleset_id: str,
    tenant: Tenant = Depends(verify_api_key)
):
    """Returns full ruleset config for inspection"""
    pass  # Implement: return registry.get(ruleset_id)


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
        from engine.database.connection import get_db
        # Execute simple query
        return True
    except Exception:
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
```

---

## Production Environment Variables — Updated

```bash
# .env.production
# All variables from architecture.md PLUS these new ones:

# Deployment
APP_ENV=production
APP_VERSION=1.0.0
API_HOST=0.0.0.0
API_PORT=8000

# AWS
AWS_REGION=us-east-1
AWS_KMS_KEY_ID=arn:aws:kms:us-east-1:xxxx:key/xxxx
KEY_BACKEND=aws_kms

# Database (RDS)
DATABASE_URL=postgresql+asyncpg://ironpass:xxx@rds-endpoint:5432/ironpass

# Redis (ElastiCache)
REDIS_URL=redis://elasticache-endpoint:6379/0

# Security
AUDIT_HMAC_KEY=<64 hex chars>
PSEUDONYM_SECRET_KEY=<64 hex chars>

# Rate limiting
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_BURST=20

# Upstream timeout
OPENAI_FORWARD_TIMEOUT_SECONDS=30

# Token TTL
VAULT_TOKEN_TTL_HOURS=24

# Gunicorn workers
GUNICORN_WORKERS=4
```

---

## Nginx Configuration — Production

```nginx
# deploy/nginx.conf

worker_processes auto;

events {
    worker_connections 1024;
}

http {
    # Rate limiting zone
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m;
    limit_req_zone $binary_remote_addr zone=health:1m rate=60r/m;

    # Hide nginx version
    server_tokens off;

    upstream ironpass_app {
        server 127.0.0.1:8000;
        keepalive 32;
    }

    server {
        listen 80;
        server_name api.ironpass.io;

        # Redirect all HTTP to HTTPS
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl;
        server_name api.ironpass.io;

        # SSL — managed by AWS Certificate Manager via ALB
        # Nginx handles SSL termination from ALB

        # Security headers
        add_header X-Content-Type-Options nosniff;
        add_header X-Frame-Options DENY;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000" always;

        # Health check — no rate limit
        location /health {
            limit_req zone=health burst=10 nodelay;
            proxy_pass http://ironpass_app;
            proxy_set_header Host $host;
        }

        # OpenAI proxy — rate limited
        location /openai/ {
            limit_req zone=api burst=20 nodelay;
            limit_req_status 429;

            proxy_pass http://ironpass_app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

            # Match OpenAI's timeout
            proxy_read_timeout 60s;
            proxy_connect_timeout 10s;

            # Don't log X-OpenAI-Key header value — ever
            proxy_hide_header X-OpenAI-Key;
        }

        # Proxy scan endpoint
        location /proxy/ {
            limit_req zone=api burst=20 nodelay;
            limit_req_status 429;

            proxy_pass http://ironpass_app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # Dashboard
        location /dashboard/ {
            limit_req zone=api burst=10 nodelay;
            proxy_pass http://ironpass_app;
            proxy_set_header Host $host;
        }
    }
}
```

---

## Dockerfile.prod

```dockerfile
# Dockerfile.prod
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_lg

# Copy application code
COPY engine/ ./engine/

# No .env files in image — all config from environment variables
# No dev dependencies
# No --reload flag

# Run with Gunicorn + Uvicorn workers
CMD ["gunicorn", "engine.main:app", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "60", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
```

---

## AWS Infrastructure — Exact Setup

```
1. EC2 t3.medium (ap-south-1 or closest to customer)
   - Ubuntu 22.04 LTS
   - Docker + Docker Compose installed
   - Nginx installed
   - Open ports: 80, 443 inbound only

2. RDS PostgreSQL 15 (db.t3.micro to start)
   - Multi-AZ: No (add later)
   - Automated backups: Yes, 7 day retention
   - Encryption at rest: Yes (AWS managed key)
   - NOT publicly accessible
   - Same VPC as EC2

3. ElastiCache Redis (cache.t3.micro)
   - Single node to start
   - NOT publicly accessible
   - Same VPC as EC2

4. Application Load Balancer
   - HTTPS listener on 443
   - HTTP listener on 80 → redirect to 443
   - SSL cert from AWS Certificate Manager (free)
   - Target: EC2 instance on port 80 (nginx)
   - Health check: GET /health every 30s

5. AWS KMS
   - One symmetric key for vault encryption
   - Key policy: only EC2 instance role can use it
   - Automatic annual rotation: enabled
   - Cost: $1/month
```

---

## The Demo Script (Exact Commands)

Run these live in front of the customer:

```bash
# Step 1: Show the system is running
curl https://demo.ironpass.io/health
# Expected: {"status": "healthy", "version": "1.0.0"}

# Step 2: Show PCI-DSS detection
curl -X POST https://demo.ironpass.io/proxy/scan \
  -H "Authorization: Bearer dbnc_demo_xxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Process payment for Visa card 4111111111111111 CVV 123 expiry 12/26",
    "rulesets": ["pci_dss"]
  }'

# Expected response — show this on screen:
# {
#   "sanitized_content": "Process payment for Visa card TOK_CARD_a4f2 [BLOCKED:CVV] expiry **/**",
#   "violations": [
#     {"type": "credit_card", "action": "tokenized", "ruleset": "pci_dss"},
#     {"type": "cvv", "action": "blocked", "ruleset": "pci_dss"},
#     {"type": "card_expiry", "action": "masked", "ruleset": "pci_dss"}
#   ],
#   "was_blocked": false,
#   "latency_ms": 34
# }

# Step 3: Show the audit trail exists
curl https://demo.ironpass.io/dashboard/audit \
  -H "Authorization: Bearer dbnc_demo_xxxx"

# Step 4: Show the one-line integration
echo "This is the only change your engineers make:"
echo ""
echo "BEFORE: base_url='https://api.openai.com'"
echo "AFTER:  base_url='https://api.ironpass.io/openai'"
```

---

## Coding Agent Task List — Ordered

Do not work out of this order.

```
TASK 1: Dockerfile.prod + Gunicorn config
        Create Dockerfile.prod exactly as specified above
        Update docker-compose.prod.yml to use Dockerfile.prod
        Test locally: docker build -f Dockerfile.prod -t ironpass-prod .

TASK 2: AWS KMS backend in engine/vault/key_manager.py
        Implement get_current_key() using boto3 + AWS KMS
        Implement get_key_by_version() for old token decryption
        KEY_BACKEND=aws_kms must work end to end
        Test: generate key, encrypt something, decrypt it

TASK 3: engine/proxy/content_extractor.py
        Implement ContentExtractor exactly as specified above
        Test: extract from string content messages
        Test: extract from array content messages (vision format)
        Test: rebuild produces identical structure to input
        Test: rebuild with sanitized content replaces correctly

TASK 4: engine/proxy/forwarder.py
        Implement OpenAIForwarder exactly as specified above
        Test: successful forward returns ForwardResult(success=True)
        Test: timeout returns ForwardResult(error_type="upstream_timeout")
        Test: 429 triggers one retry then succeeds
        Test: 500 from OpenAI returns error without retry

TASK 5: engine/proxy/router.py — full replacement
        Implement both endpoint sets as specified above
        POST /openai/v1/chat/completions (transparent proxy)
        POST /proxy/scan (explicit scan)
        GET  /proxy/rulesets
        GET  /proxy/rulesets/{id}
        GET  /health (with DB + vault checks)

TASK 6: Nginx config
        Create deploy/nginx.conf exactly as specified above
        Rate limiting on /openai/ and /proxy/ endpoints
        Security headers present
        X-OpenAI-Key never logged

TASK 7: AWS infrastructure setup
        EC2, RDS, ElastiCache, ALB, KMS as specified above
        All in same VPC
        RDS and ElastiCache NOT publicly accessible
        Health check configured on ALB

TASK 8: Production .env
        All variables from architecture.md plus new ones above
        KEY_BACKEND=aws_kms
        APP_ENV=production
        No secrets committed to git — ever

TASK 9: Deploy and smoke test
        docker build -f Dockerfile.prod
        Run against RDS (not local postgres)
        Hit /health — must return healthy
        Run the 3 demo curl commands — all must work

TASK 10: Load test
        pip install locust
        50 concurrent users on /proxy/scan
        Target: p99 latency under 200ms
        If NER is the bottleneck: confirm it only runs for HIPAA ruleset
        For PCI-DSS only demo: NER should not run at all
```

---

## Critical Rules For This Phase

These are in addition to the 12 rules in architecture.md:

1. X-OpenAI-Key is NEVER written to any database, log file, or audit entry.
   Log only: "openai_key_present: true/false"

2. Gunicorn runs with 4 workers in production. Never run uvicorn directly.

3. APP_ENV=production must disable all debug output, stack traces in responses,
   and reload functionality.

4. The /health endpoint must check real database and vault connectivity.
   A health check that always returns 200 is worse than no health check.

5. Nginx hides the X-OpenAI-Key header from access logs using proxy_hide_header.

6. RDS and ElastiCache are never publicly accessible. EC2 only.

7. NER detector (spaCy) must not run on PCI-DSS only requests.
   Check active rulesets before running Layer 3. If only pci_dss is active,
   skip NER entirely. This is your latency optimization.
```