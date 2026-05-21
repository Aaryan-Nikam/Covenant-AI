"""Business logic for unified decisioning."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engine.agent_security.schemas import SecurityDecisionEvaluateRequest
from engine.agent_security.service import AgentSecurityService
from engine.audit.logger import AuditLogger
from engine.auth.models import Tenant
from engine.decisions.models import UnifiedDecisionLog
from engine.decisions.schemas import (
    UnifiedDecisionError,
    UnifiedDecisionEvaluateRequest,
    UnifiedDecisionEvaluateResponse,
    UnifiedEvidence,
    UnifiedEvidenceDetection,
    UnifiedRiskBreakdown,
    UnifiedRiskComponents,
    WeightedRiskComponent,
)
from engine.detection.engine import DetectionEngine
from engine.detection.models import ActionTaken, Detection
from engine.config import get_settings
from engine.rulesets.registry import RulesetRegistry

WEIGHTS = {
    "pii_detection": 0.20,
    "prompt_injection": 0.30,
    "exfiltration": 0.25,
    "tool_permissions": 0.15,
    "memory_hygiene": 0.10,
}

SEVERITY_POINTS = {
    "low": 0.08,
    "medium": 0.15,
    "high": 0.25,
    "critical": 0.40,
}


class AuditWriter(Protocol):
    async def log_request(
        self,
        *,
        agent_id: str,
        request_content: str,
        rulesets_used: list[str],
        detections: list[Detection],
        actions_taken: list[ActionTaken],
        was_blocked: bool,
        target_url: str | None,
        latency_ms: int,
        outcome: str,
    ) -> str:
        ...


class UnifiedDecisionService:
    """Composes detection + agent security into one signed decision contract."""

    def __init__(
        self,
        db_session: AsyncSession,
        *,
        agent_security_service: AgentSecurityService | None = None,
        audit_writer: AuditWriter | None = None,
    ):
        self.db = db_session
        self.agent_security_service = agent_security_service or AgentSecurityService(db_session)
        self.audit_writer = audit_writer or AuditLogger(db_session)
        self._hmac_key = bytes.fromhex(get_settings().audit_hmac_key)

    async def evaluate_decision(
        self,
        *,
        tenant: Tenant,
        request: UnifiedDecisionEvaluateRequest,
        registry: RulesetRegistry,
        detection_engine: DetectionEngine,
    ) -> UnifiedDecisionEvaluateResponse:
        request_id = request.request_id or str(uuid.uuid4())
        existing = await self._get_decision_log(tenant_id=tenant.id, request_id=request_id)
        if existing is not None:
            return UnifiedDecisionEvaluateResponse.model_validate(existing.decision_payload)

        decision_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        policy_mode = "enforce"
        policy_version = "unknown"
        try:
            policy = await self.agent_security_service.get_or_create_policy(tenant.id)
            policy_mode = policy.config.mode
            policy_version = str(policy.version)

            active_rulesets = request.rulesets or tenant.active_rulesets or []
            task_context = request.task_instruction or request.task_description
            security_decision = await self.agent_security_service.evaluate_decision(
                tenant.id,
                SecurityDecisionEvaluateRequest(
                    request_id=request_id,
                    task_instruction=request.task_instruction,
                    task_description=request.task_description,
                    untrusted_content=request.untrusted_content,
                    candidate_output=request.candidate_output,
                    reasoning_trace=request.reasoning_trace,
                    tool_payloads=request.tool_payloads,
                    tools=request.tools,
                    requested_tools=request.requested_tools,
                    session_events=request.session_events,
                    allowed_actions=request.allowed_actions,
                    allowed_destinations=request.allowed_destinations,
                ),
            )

            content_for_detection = "\n".join(
                part
                for part in [
                    task_context,
                    request.untrusted_content,
                    request.candidate_output,
                    request.reasoning_trace or "",
                ]
                if part
            )
            pii_detections = (
                await detection_engine.scan(content_for_detection, active_rulesets)
                if content_for_detection and active_rulesets
                else []
            )

            merged_actions = (
                registry.get_merged_actions(active_rulesets) if active_rulesets else {}
            )
            pii_evidence, pii_actions, action_records = _build_pii_evidence(
                pii_detections,
                merged_actions,
            )
            pii_score = _score_pii(pii_evidence)

            security_evidence = _build_security_evidence(security_decision.findings)
            evidence = UnifiedEvidence(
                detections=[*pii_evidence, *security_evidence],
                ruleset_version=_ruleset_version_string(registry, active_rulesets),
                policy_version=policy_version,
            )

            prompt_score = round(security_decision.prompt_injection.risk_score / 100.0, 4)
            exfiltration_score = round(security_decision.context_exfiltration.risk_score / 100.0, 4)
            tool_score = round(security_decision.tool_permissions.risk_score / 100.0, 4)
            memory_score = round(security_decision.memory_audit.risk_score / 100.0, 4)

            overall_score = round(
                (
                    pii_score * WEIGHTS["pii_detection"]
                    + prompt_score * WEIGHTS["prompt_injection"]
                    + exfiltration_score * WEIGHTS["exfiltration"]
                    + tool_score * WEIGHTS["tool_permissions"]
                    + memory_score * WEIGHTS["memory_hygiene"]
                ),
                4,
            )

            outcome = _resolve_outcome(
                base_action=security_decision.action,
                policy_mode=policy_mode,
                pii_evidence=pii_evidence,
            )

            signature = self._sign_payload(
                {
                    "decision_id": decision_id,
                    "request_id": request_id,
                    "tenant_id": tenant.id,
                    "outcome": outcome,
                    "overall_score": overall_score,
                    "timestamp": timestamp,
                }
            )

            start = time.monotonic()
            audit_entry_id = await self.audit_writer.log_request(
                agent_id=request.agent_id or tenant.agent_id,
                request_content=_audit_payload(request),
                rulesets_used=active_rulesets,
                detections=pii_detections,
                actions_taken=action_records,
                was_blocked=outcome == "block",
                target_url=None,
                latency_ms=int((time.monotonic() - start) * 1000),
                outcome=outcome,
            )

            response = UnifiedDecisionEvaluateResponse(
                decision_id=decision_id,
                request_id=request_id,
                tenant_id=tenant.id,
                agent_id=request.agent_id or tenant.agent_id,
                timestamp=timestamp,
                outcome=outcome,
                signed=True,
                signature=signature,
                risk=UnifiedRiskBreakdown(
                    overall_score=overall_score,
                    tier=_risk_tier(overall_score),
                    components=UnifiedRiskComponents(
                        pii_detection=WeightedRiskComponent(
                            score=pii_score,
                            weight=WEIGHTS["pii_detection"],
                        ),
                        prompt_injection=WeightedRiskComponent(
                            score=prompt_score,
                            weight=WEIGHTS["prompt_injection"],
                        ),
                        exfiltration=WeightedRiskComponent(
                            score=exfiltration_score,
                            weight=WEIGHTS["exfiltration"],
                        ),
                        tool_permissions=WeightedRiskComponent(
                            score=tool_score,
                            weight=WEIGHTS["tool_permissions"],
                        ),
                        memory_hygiene=WeightedRiskComponent(
                            score=memory_score,
                            weight=WEIGHTS["memory_hygiene"],
                        ),
                    ),
                ),
                evidence=evidence,
                actions_applied=sorted(set(pii_actions)),
                audit_entry_id=audit_entry_id,
                error=None,
            )

            log_record = UnifiedDecisionLog(
                tenant_id=tenant.id,
                request_id=request_id,
                decision_id=decision_id,
                outcome=outcome,
                overall_risk_score=int(overall_score * 100),
                decision_payload=response.model_dump(mode="json"),
                signature=signature,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(log_record)
            await self.db.flush()

            return response

        except Exception as exc:
            outcome = "block" if policy_mode == "enforce" else "allow"
            error = UnifiedDecisionError(
                code=_error_code(exc),
                message=str(exc),
                recoverable=True,
            )
            return UnifiedDecisionEvaluateResponse(
                decision_id=decision_id,
                request_id=request_id,
                tenant_id=tenant.id,
                agent_id=request.agent_id or tenant.agent_id,
                timestamp=timestamp,
                outcome=outcome,
                signed=False,
                signature="",
                risk=UnifiedRiskBreakdown(
                    overall_score=1.0 if outcome == "block" else 0.0,
                    tier="critical" if outcome == "block" else "low",
                    components=UnifiedRiskComponents(
                        pii_detection=WeightedRiskComponent(score=0.0, weight=WEIGHTS["pii_detection"]),
                        prompt_injection=WeightedRiskComponent(score=0.0, weight=WEIGHTS["prompt_injection"]),
                        exfiltration=WeightedRiskComponent(score=0.0, weight=WEIGHTS["exfiltration"]),
                        tool_permissions=WeightedRiskComponent(score=0.0, weight=WEIGHTS["tool_permissions"]),
                        memory_hygiene=WeightedRiskComponent(score=0.0, weight=WEIGHTS["memory_hygiene"]),
                    ),
                ),
                evidence=UnifiedEvidence(
                    detections=[],
                    ruleset_version="unknown",
                    policy_version=policy_version,
                ),
                actions_applied=[],
                audit_entry_id="",
                error=error,
            )

    async def _get_decision_log(
        self,
        *,
        tenant_id: str,
        request_id: str,
    ) -> UnifiedDecisionLog | None:
        result = await self.db.execute(
            select(UnifiedDecisionLog).where(
                UnifiedDecisionLog.tenant_id == tenant_id,
                UnifiedDecisionLog.request_id == request_id,
            )
        )
        return result.scalar_one_or_none()

    def _sign_payload(self, payload: dict[str, object]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hmac.new(self._hmac_key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _severity_from_detection(detection: Detection) -> str:
    if detection.layer == 3 or detection.confidence >= 0.97:
        return "high"
    if detection.layer == 2 or detection.confidence >= 0.92:
        return "medium"
    return "low"


def _score_pii(pii_evidence: list[UnifiedEvidenceDetection]) -> float:
    if not pii_evidence:
        return 0.0
    score = sum(SEVERITY_POINTS.get(item.severity, 0.05) for item in pii_evidence)
    score += min(0.25, len(pii_evidence) * 0.03)
    return round(min(1.0, score), 4)


def _risk_tier(score: float) -> str:
    if score >= 0.85:
        return "critical"
    if score >= 0.65:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"


def _build_pii_evidence(
    detections: list[Detection],
    merged_actions: dict,
) -> tuple[list[UnifiedEvidenceDetection], list[str], list[ActionTaken]]:
    evidence: list[UnifiedEvidenceDetection] = []
    actions_applied: list[str] = []
    action_records: list[ActionTaken] = []

    for det in detections:
        action_cfg = merged_actions.get(det.data_type)
        action_applied = action_cfg.primary if action_cfg else "flag"
        severity = action_cfg.log_level if action_cfg else _severity_from_detection(det)
        detector = {1: "regex", 2: "luhn", 3: "ner"}.get(det.layer, "heuristic")
        evidence.append(
            UnifiedEvidenceDetection(
                type="PII",
                detector=detector,
                field="prompt",
                severity=severity,
                action_applied=action_applied,
                redacted=True,
            )
        )
        actions_applied.append(action_applied)
        action_records.append(
            ActionTaken(
                detector_id=det.detector_id,
                data_type=det.data_type,
                action=action_applied,
                original_position=det.position,
                replacement=f"[{action_applied.upper()}]",
                ruleset_id=det.ruleset_id,
                log_level=severity,
            )
        )

    return evidence, actions_applied, action_records


def _build_security_evidence(findings: list) -> list[UnifiedEvidenceDetection]:
    evidence: list[UnifiedEvidenceDetection] = []
    for finding in findings:
        mapped_type = {
            "prompt_injection": "INJECTION",
            "context_exfiltration": "EXFILTRATION",
            "over_permissioned_tools": "TOOL",
            "memory_session_persistence": "MEMORY",
        }.get(finding.category, "TOOL")
        mapped_field = {
            "prompt_injection": "prompt",
            "context_exfiltration": "candidate_output",
            "over_permissioned_tools": "tool_call",
            "memory_session_persistence": "memory_ref",
        }.get(finding.category, "tool_call")
        evidence.append(
            UnifiedEvidenceDetection(
                type=mapped_type,
                detector="heuristic",
                field=mapped_field,
                severity=finding.severity,
                action_applied="block" if finding.severity == "critical" else "flag",
                redacted=True,
            )
        )
    return evidence


def _resolve_outcome(
    *,
    base_action: str,
    policy_mode: str,
    pii_evidence: list[UnifiedEvidenceDetection],
) -> str:
    if base_action == "block":
        return "block"
    if base_action == "review":
        return "review"

    has_pii_block = any(item.action_applied == "block" for item in pii_evidence)
    has_high_pii = any(item.severity in {"high", "critical"} for item in pii_evidence)
    if has_pii_block and policy_mode == "enforce":
        return "block"
    if has_high_pii:
        return "review"
    return "allow"


def _ruleset_version_string(registry: RulesetRegistry, active_rulesets: list[str]) -> str:
    if not active_rulesets:
        return "none"

    versions: list[str] = []
    for ruleset_id in active_rulesets:
        try:
            ruleset = registry.get(ruleset_id)
        except Exception:
            continue
        versions.append(f"{ruleset.ruleset_id}@{ruleset.version}")

    return "|".join(versions) if versions else "unknown"


def _audit_payload(request: UnifiedDecisionEvaluateRequest) -> str:
    return json.dumps(
        {
            "task_instruction": request.task_instruction,
            "task_description": request.task_description,
            "untrusted_content": request.untrusted_content,
            "candidate_output": request.candidate_output,
            "reasoning_trace": request.reasoning_trace,
            "requested_tools": request.requested_tools,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _error_code(exc: Exception) -> str:
    message = str(exc).lower()
    if isinstance(exc, TimeoutError):
        return "PIPELINE_TIMEOUT"
    if "vault" in message or "key manager" in message:
        return "VAULT_UNAVAILABLE"
    if "detect" in message or "ruleset" in message:
        return "DETECTION_FAILURE"
    return "INTERNAL_ERROR"
