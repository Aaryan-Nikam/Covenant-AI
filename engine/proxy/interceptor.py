"""
Ironpass — Proxy Interceptor.

The main compliance pipeline. Every agent request flows through here:

1. DETECT — Run detection engine on content
2. ACT — Apply actions (tokenize/mask/block/pseudonymize) 
3. FORWARD — Forward sanitized content to target LLM
4. LOG — Audit log (background, never blocks response)

Architecture doc reference: Component 1 — Proxy Router & Interceptor.

Critical Rule #6: Audit writes are background tasks.
Critical Rule #7: Block is immediate — stops pipeline.
Critical Rule #8: Pipeline must complete in <200ms for regex/mask.
"""

import asyncio
import hashlib
import logging
import time
import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from engine.actions.executor import ActionExecutor, ExecutionResult
from engine.audit.logger import AuditLogger
from engine.detection.engine import DetectionEngine
from engine.detection.models import ActionTaken, Detection
from engine.exceptions import ComplianceViolation
from engine.proxy.request_model import (
    ActionSummary,
    DetectionSummary,
    ProxyResponse,
)
from engine.rulesets.registry import RulesetRegistry

logger = logging.getLogger("ironpass.proxy.interceptor")


class ProxyInterceptor:
    """
    The core compliance proxy pipeline.
    Detect → Act → Forward → Log.
    """

    def __init__(
        self,
        detection_engine: DetectionEngine,
        action_executor: ActionExecutor,
        ruleset_registry: RulesetRegistry,
        db_session: AsyncSession,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.detection_engine = detection_engine
        self.action_executor = action_executor
        self.ruleset_registry = ruleset_registry
        self.audit_logger = AuditLogger(db_session)
        # Use shared client if provided, otherwise fall back to per-request
        self._http_client = http_client

    async def process_request(
        self,
        content: str,
        target_url: str | None,
        agent_id: str,
        tenant_id: str,
        active_rulesets: list[str],
        metadata: dict | None = None,
        forward: bool = True,
        headers: dict[str, str] | None = None,
        method: str = "POST",
    ) -> ProxyResponse:
        """
        Full compliance pipeline:
        1. DETECT — Scan content for sensitive data
        2. ACT — Apply actions from ruleset config
        3. FORWARD — Send sanitized content to target
        4. LOG — Audit log (background)
        """
        start_time = time.monotonic()
        request_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        session_id = str(uuid.uuid4())
        detections: list[Detection] = []
        actions_taken: list[ActionTaken] = []
        was_blocked = False
        target_status_code = None
        target_response = None
        outcome = "passed"

        try:
            # ---- STEP 1: DETECT ----
            detections = await self.detection_engine.scan(
                content=content,
                active_rulesets=active_rulesets,
            )

            if not detections:
                # No detections — forward as-is unless caller requested scan-only mode.
                if forward and target_url:
                    logger.debug(f"No detections — forwarding to {target_url}")
                    target_status_code, target_response = await self._forward(
                        content=content,
                        target_url=target_url,
                        headers=headers or {},
                        method=method,
                    )
                outcome = "passed"

            else:
                # ---- STEP 2: ACT ----
                merged_actions = self.ruleset_registry.get_merged_actions(
                    active_rulesets
                )

                result: ExecutionResult = await self.action_executor.execute(
                    content=content,
                    detections=detections,
                    ruleset_actions=merged_actions,
                    agent_id=agent_id,
                    tenant_id=tenant_id,
                )
                actions_taken = result.actions_taken

                # ---- STEP 3: FORWARD (sanitized content) ----
                if forward and target_url:
                    target_status_code, target_response = await self._forward(
                        content=result.modified_content,
                        target_url=target_url,
                        headers=headers or {},
                        method=method,
                    )
                outcome = "sanitized"

        except ComplianceViolation as violation:
            # ---- BLOCKED ----
            was_blocked = True
            outcome = "blocked"
            latency_ms = int((time.monotonic() - start_time) * 1000)

            logger.warning(
                f"Request BLOCKED: {violation.data_type} by "
                f"{violation.ruleset_id}/{violation.detector_id}"
            )

            # Log the blocked request (background)
            audit_entry_id = await self._log_audit(
                agent_id=agent_id,
                request_content=content,
                rulesets_used=active_rulesets,
                detections=detections,
                actions_taken=actions_taken,
                was_blocked=True,
                target_url=target_url,
                latency_ms=latency_ms,
                outcome=outcome,
            )

            # Bubble up to route layer after auditing so each endpoint can return
            # the provider-specific HTTP response shape.
            raise

        # ---- STEP 4: LOG (fire-and-forget — never blocks response) ----
        latency_ms = int((time.monotonic() - start_time) * 1000)

        asyncio.create_task(self._log_audit(
            agent_id=agent_id,
            request_content=content,
            rulesets_used=active_rulesets,
            detections=detections,
            actions_taken=actions_taken,
            was_blocked=was_blocked,
            target_url=target_url,
            latency_ms=latency_ms,
            outcome=outcome,
        ))
        audit_entry_id = None  # Not available immediately; logged asynchronously

        # Build response
        detection_summaries = [
            DetectionSummary(
                detector_id=d.detector_id,
                data_type=d.data_type,
                position=list(d.position),
                confidence=d.confidence,
                layer=d.layer,
                ruleset_id=d.ruleset_id,
            )
            for d in detections
        ]

        action_summaries = [
            ActionSummary(
                detector_id=a.detector_id,
                data_type=a.data_type,
                action=a.action,
                ruleset_id=a.ruleset_id,
                log_level=a.log_level,
            )
            for a in actions_taken
        ]

        return ProxyResponse(
            status=outcome,
            target_status_code=target_status_code,
            target_response=target_response,
            detections_count=len(detections),
            detections=detection_summaries,
            actions_taken=action_summaries,
            audit_entry_id=audit_entry_id,
            latency_ms=latency_ms,
            sanitized_content=result.modified_content if 'result' in locals() else content,
            request_hash=request_hash,
            rulesets_used=active_rulesets,
            was_blocked=False,
            session_id=session_id,
            session_token_map=result.session_token_map if 'result' in locals() else {},
        )

    async def _forward(
        self,
        content: str,
        target_url: str,
        headers: dict[str, str],
        method: str,
    ) -> tuple[int, str]:
        """
        Forward (sanitized) content to the target LLM API.
        Uses the process-level shared httpx client (warm TCP/TLS pool).
        Returns (status_code, response_body).
        """
        # Use shared client if available, otherwise create a temporary one
        if self._http_client and not self._http_client.is_closed:
            client = self._http_client
            should_close = False
        else:
            client = httpx.AsyncClient(timeout=30.0)
            should_close = True

        try:
            if method.upper() == "POST":
                response = await client.post(
                    target_url,
                    content=content,
                    headers={"Content-Type": "application/json", **headers},
                )
            elif method.upper() == "GET":
                response = await client.get(target_url, headers=headers)
            else:
                response = await client.request(
                    method.upper(),
                    target_url,
                    content=content,
                    headers={"Content-Type": "application/json", **headers},
                )
            return response.status_code, response.text

        except httpx.TimeoutException:
            logger.error(f"Target timeout: {target_url}")
            return 504, '{"error": "Target API timeout"}'
        except httpx.ConnectError:
            logger.error(f"Target unreachable: {target_url}")
            return 502, '{"error": "Target API unreachable"}'
        except Exception as e:
            logger.error(f"Forward error: {e}")
            return 500, f'{{"error": "Proxy forward error: {str(e)}"}}'
        finally:
            if should_close:
                await client.aclose()
    async def _log_audit(
        self,
        agent_id: str,
        request_content: str,
        rulesets_used: list[str],
        detections: list[Detection],
        actions_taken: list[ActionTaken],
        was_blocked: bool,
        target_url: str | None,
        latency_ms: int,
        outcome: str,
    ) -> str | None:
        """
        Log to audit trail. Runs as background task.
        Never blocks the proxy response (Critical Rule #6).
        Returns entry_id or None on failure.
        """
        try:
            entry_id = await self.audit_logger.log_request(
                agent_id=agent_id,
                request_content=request_content,
                rulesets_used=rulesets_used,
                detections=detections,
                actions_taken=actions_taken,
                was_blocked=was_blocked,
                target_url=target_url,
                latency_ms=latency_ms,
                outcome=outcome,
            )
            return entry_id
        except Exception as e:
            # Audit failure should NEVER block the proxy
            logger.error(f"Audit logging failed (non-blocking): {e}")
            return None

    async def process_response(
        self,
        response_content: str,
        session_token_map: dict[str, str],
        agent_id: str,
    ) -> str:
        """
        De-tokenize the OpenAI response before returning it to the agent.

        Scans response_content for any TOK_* tokens present in session_token_map
        and replaces them with their display-safe values.

        Examples:
            TOK_CARD_a4f2b891  →  ****4242
            TOK_SSN_c3d1e2f0   →  [SSN PROTECTED]
            TOK_NAME_b7a9c011  →  John Smith

        This runs synchronously — we must de-tokenize before returning
        the response to the agent (unlike audit writes which are background).
        """
        if not session_token_map:
            return response_content

        detokenized = response_content
        replaced_count = 0

        for token, display_value in session_token_map.items():
            if token in detokenized:
                detokenized = detokenized.replace(token, display_value)
                replaced_count += 1

        if replaced_count > 0:
            logger.debug(
                f"De-tokenized {replaced_count} token(s) in response "
                f"(agent={agent_id})"
            )

        return detokenized
