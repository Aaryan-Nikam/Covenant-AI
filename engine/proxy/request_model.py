"""
Pydantic models for incoming requests and outgoing responses.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# OpenAI Proxy Request Models (Transparent)
# We don't strictly validate the entire OpenAI spec, we just need 'messages'.
# ---------------------------------------------------------------------------
class OpenAIProxyRequest(BaseModel):
    messages: list[dict[str, Any]]
    model: str = Field(default="unknown")
    
    class Config:
        extra = "allow"  # Allow any other OpenAI kwargs to pass through

# ---------------------------------------------------------------------------
# Explicit Scan Request Models (Original SDK)
# ---------------------------------------------------------------------------
class ScanRequest(BaseModel):
    """Payload for explicit scan requests"""
    content: str = Field(..., description="The text to scan and sanitize")
    rulesets: list[str] | None = Field(
        default=None,
        description="Optional list of rulesets to apply. If omitted, uses tenant defaults.",
    )
    target_url: str | None = Field(
        default=None,
        description="Optional upstream URL the request is heading to (for auditing)",
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Optional metadata to attach to the audit log",
    )


class Violation(BaseModel):
    """A compliance violation that blocked the request"""
    type: str = Field(description="The data type that was detected (e.g., credit_card)")
    action: str = Field(description="The action taken (e.g., blocked)")
    ruleset: str = Field(description="The ruleset that triggered this action")


class ScanResponse(BaseModel):
    """Response from explicit scan endpoint"""
    sanitized_content: str = Field(description="The content with sensitive data removed")
    violations: list[Violation] = Field(description="List of detections and actions taken")
    was_blocked: bool = Field(description="True if the request was blocked")
    audit_id: str = Field(description="Unique ID for the audit log entry")
    session_id: str = Field(description="Unique ID for the scanning session")
    latency_ms: int = Field(description="Processing latency in milliseconds")


class ComplianceViolationError(BaseModel):
    """Error format when a request is blocked"""
    violations: list[Violation]
    request_id: str

# ---------------------------------------------------------------------------
# Legacy Models (Required by interceptor.py)
# ---------------------------------------------------------------------------
class ProxyRequest(BaseModel):
    content: str
    target_url: str
    metadata: dict[str, str] = {}
    rulesets: list[str] = []

class DetectionSummary(BaseModel):
    detector_id: str
    data_type: str
    position: list[int]
    confidence: float
    layer: int
    ruleset_id: str
    
class ActionSummary(BaseModel):
    detector_id: str
    data_type: str
    action: str
    ruleset_id: str
    log_level: str

class ProxyResponse(BaseModel):
    status: str
    target_status_code: int | None
    target_response: str | None
    detections_count: int
    detections: list[DetectionSummary]
    actions_taken: list[ActionSummary]
    audit_entry_id: str | None
    latency_ms: int
    
    # NEW fields to pass out detokenization map from interceptor 
    # (since process_request processes detokenization state)
    sanitized_content: str = ""
    request_hash: str = ""
    rulesets_used: list[str] = []
    was_blocked: bool = False
    violations: list[Violation] = []
    session_id: str = ""
    session_token_map: dict | None = None

class BlockedResponse(BaseModel):
    error: str
    data_type: str
    ruleset_id: str
    detector_id: str
    audit_entry_id: str | None
