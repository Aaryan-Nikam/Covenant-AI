"""Schemas for the unified compliance + agent security decision endpoint."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from engine.agent_security.schemas import SessionMemoryEvent, ToolCapability


DecisionOutcome = Literal["allow", "block", "review"]
RiskTier = Literal["low", "medium", "high", "critical"]
EvidenceType = Literal["PII", "INJECTION", "EXFILTRATION", "TOOL", "MEMORY"]


class UnifiedDecisionEvaluateRequest(BaseModel):
    request_id: str | None = Field(default=None, max_length=128)
    agent_id: str | None = Field(default=None, max_length=128)
    task_instruction: str = Field(default="", max_length=20_000)
    task_description: str = Field(default="", max_length=20_000)
    untrusted_content: str = Field(default="", max_length=200_000)
    candidate_output: str = Field(default="", max_length=200_000)
    reasoning_trace: str | None = Field(default=None, max_length=200_000)
    tool_payloads: list[dict[str, Any]] = Field(default_factory=list, max_length=128)
    tools: list[ToolCapability] = Field(default_factory=list, max_length=128)
    requested_tools: list[str] = Field(default_factory=list, max_length=128)
    session_events: list[SessionMemoryEvent] = Field(default_factory=list, max_length=1000)
    allowed_actions: list[str] = Field(default_factory=list, max_length=64)
    allowed_destinations: list[str] = Field(default_factory=list, max_length=128)
    rulesets: list[str] = Field(default_factory=list, max_length=32)


class WeightedRiskComponent(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)


class UnifiedRiskComponents(BaseModel):
    pii_detection: WeightedRiskComponent
    prompt_injection: WeightedRiskComponent
    exfiltration: WeightedRiskComponent
    tool_permissions: WeightedRiskComponent
    memory_hygiene: WeightedRiskComponent


class UnifiedRiskBreakdown(BaseModel):
    overall_score: float = Field(ge=0.0, le=1.0)
    tier: RiskTier
    components: UnifiedRiskComponents


class UnifiedEvidenceDetection(BaseModel):
    type: EvidenceType
    detector: Literal["regex", "luhn", "ner", "heuristic"]
    field: Literal["prompt", "tool_call", "memory_ref", "candidate_output", "reasoning_trace"]
    severity: Literal["low", "medium", "high", "critical"]
    action_applied: Literal["block", "tokenize", "mask", "pseudonymize", "flag"]
    redacted: bool = True


class UnifiedEvidence(BaseModel):
    detections: list[UnifiedEvidenceDetection]
    ruleset_version: str
    policy_version: str


class UnifiedDecisionError(BaseModel):
    code: Literal["PIPELINE_TIMEOUT", "DETECTION_FAILURE", "VAULT_UNAVAILABLE", "INTERNAL_ERROR"]
    message: str
    recoverable: bool


class UnifiedDecisionEvaluateResponse(BaseModel):
    decision_id: str
    request_id: str
    tenant_id: str
    agent_id: str
    timestamp: str
    outcome: DecisionOutcome
    signed: bool
    signature: str
    risk: UnifiedRiskBreakdown
    evidence: UnifiedEvidence
    actions_applied: list[str]
    audit_entry_id: str
    error: UnifiedDecisionError | None = None

