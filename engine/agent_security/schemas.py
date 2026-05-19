"""Pydantic schemas for the Agent Security Suite."""

from typing import Any, Literal

from pydantic import BaseModel, Field


Severity = Literal["low", "medium", "high", "critical"]
DecisionAction = Literal["allow", "review", "block"]
PolicyMode = Literal["monitor", "enforce"]


class SecurityFinding(BaseModel):
    finding_id: str
    category: str
    severity: Severity
    title: str
    evidence: str
    recommendation: str


class PromptInjectionAnalyzeRequest(BaseModel):
    task_instruction: str = Field(default="", max_length=20_000)
    untrusted_content: str = Field(max_length=200_000)
    allowed_actions: list[str] = Field(default_factory=list, max_length=64)
    block_threshold: int = Field(default=60, ge=1, le=100)


class PromptInjectionAnalyzeResponse(BaseModel):
    risk_score: int
    blocked: bool
    attack_strings_detected: list[str]
    findings: list[SecurityFinding]
    sanitized_content: str


class ContextExfiltrationAnalyzeRequest(BaseModel):
    candidate_output: str = Field(max_length=200_000)
    reasoning_trace: str | None = Field(default=None, max_length=200_000)
    tool_payloads: list[dict[str, Any]] = Field(default_factory=list, max_length=128)
    allowed_destinations: list[str] = Field(default_factory=list, max_length=128)


class LeakHit(BaseModel):
    leak_type: str
    location: Literal["candidate_output", "reasoning_trace", "tool_payload"]
    preview: str


class ContextExfiltrationAnalyzeResponse(BaseModel):
    risk_score: int
    findings: list[SecurityFinding]
    leak_hits: list[LeakHit]
    redacted_output: str


class ToolCapability(BaseModel):
    tool_name: str = Field(max_length=128)
    description: str = Field(default="", max_length=500)
    scopes: list[str] = Field(default_factory=list, max_length=64)
    data_domains: list[str] = Field(default_factory=list, max_length=64)
    requires_approval: bool = False


class ToolPermissionEvaluateRequest(BaseModel):
    task_description: str = Field(max_length=20_000)
    tools: list[ToolCapability] = Field(default_factory=list, max_length=128)
    requested_tools: list[str] = Field(default_factory=list, max_length=128)
    max_tools: int = Field(default=5, ge=1, le=25)


class GrantedToolPermission(BaseModel):
    tool_name: str
    granted_scopes: list[str]
    reason: str


class DeniedToolPermission(BaseModel):
    tool_name: str
    reason: str


class ToolPermissionEvaluateResponse(BaseModel):
    risk_score: int
    findings: list[SecurityFinding]
    least_privilege_set: list[GrantedToolPermission]
    denied: list[DeniedToolPermission]


class SessionMemoryEvent(BaseModel):
    turn_id: str = Field(max_length=128)
    role: str = Field(default="assistant", max_length=64)
    content: str = Field(max_length=50_000)
    persisted: bool = True


class MemorySessionAuditRequest(BaseModel):
    session_events: list[SessionMemoryEvent] = Field(default_factory=list, max_length=1000)
    max_retention_turns: int = Field(default=20, ge=1, le=500)


class MemoryLeakItem(BaseModel):
    turn_id: str
    leak_type: str
    preview: str
    action: Literal["scrub", "summarize", "keep"]
    reason: str


class MemorySessionAuditResponse(BaseModel):
    risk_score: int
    findings: list[SecurityFinding]
    flagged_items: list[MemoryLeakItem]
    recommended_ttl_turns: int


class AgentSecurityControlStatus(BaseModel):
    control_id: str
    title: str
    objective: str
    status: Literal["operational", "planned"]


class AgentSecurityOverviewResponse(BaseModel):
    suite_name: str
    generated_at: str
    controls: list[AgentSecurityControlStatus]


class AgentSecurityPolicyConfig(BaseModel):
    mode: PolicyMode = "enforce"
    prompt_injection_block_threshold: int = Field(default=60, ge=1, le=100)
    context_exfil_block_threshold: int = Field(default=70, ge=1, le=100)
    context_exfil_review_threshold: int = Field(default=40, ge=1, le=100)
    max_tools_per_task: int = Field(default=5, ge=1, le=25)
    strict_tool_allowlist: bool = True
    block_on_sensitive_memory_residue: bool = False
    memory_max_retention_turns: int = Field(default=20, ge=1, le=500)
    allowed_destinations: list[str] = Field(default_factory=list, max_length=128)


class AgentSecurityPolicyResponse(BaseModel):
    tenant_id: str
    version: int
    updated_at: str
    config: AgentSecurityPolicyConfig


class AgentSecurityPolicyUpdateRequest(BaseModel):
    expected_version: int | None = Field(default=None, ge=1)
    updated_by: str | None = Field(default=None, max_length=128)
    config: AgentSecurityPolicyConfig


class SecurityDecisionEvaluateRequest(BaseModel):
    request_id: str | None = Field(default=None, max_length=128)
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


class SecurityDecisionEnforcementPlan(BaseModel):
    sanitized_untrusted_content: str
    redacted_output: str
    granted_tools: list[GrantedToolPermission]
    denied_tools: list[DeniedToolPermission]
    memory_actions: list[MemoryLeakItem]


class SecurityDecisionEvaluateResponse(BaseModel):
    request_id: str
    tenant_id: str
    policy_version: int
    action: DecisionAction
    overall_risk_score: int
    decision_timestamp: str
    security_signature: str
    findings: list[SecurityFinding]
    prompt_injection: PromptInjectionAnalyzeResponse
    context_exfiltration: ContextExfiltrationAnalyzeResponse
    tool_permissions: ToolPermissionEvaluateResponse
    memory_audit: MemorySessionAuditResponse
    enforcement_plan: SecurityDecisionEnforcementPlan
