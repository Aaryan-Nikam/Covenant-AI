"""
Ironpass Python SDK — Data models.

Pydantic models matching the proxy API request/response schema.
"""

from pydantic import BaseModel, Field


class ScanRequest(BaseModel):
    """Request to scan content through the compliance proxy."""

    target_url: str
    content: str
    agent_id: str
    rulesets: list[str]
    headers: dict[str, str] = Field(default_factory=dict)
    method: str = "POST"


class DetectionInfo(BaseModel):
    """Detected sensitive data (no raw values)."""

    detector_id: str
    data_type: str
    position: list[int]
    confidence: float
    layer: int
    ruleset_id: str


class ActionInfo(BaseModel):
    """Action taken on detected data."""

    detector_id: str
    data_type: str
    action: str
    ruleset_id: str
    log_level: str


class ScanResponse(BaseModel):
    """Response from the compliance proxy."""

    status: str
    target_status_code: int | None = None
    target_response: str | None = None
    detections_count: int = 0
    detections: list[DetectionInfo] = Field(default_factory=list)
    actions_taken: list[ActionInfo] = Field(default_factory=list)
    audit_entry_id: str | None = None
    latency_ms: int = 0


class BlockedError(Exception):
    """Raised when a request is blocked by the compliance proxy."""

    def __init__(self, data_type: str, ruleset_id: str, detector_id: str, message: str):
        self.data_type = data_type
        self.ruleset_id = ruleset_id
        self.detector_id = detector_id
        super().__init__(message)


class RulesetInfo(BaseModel):
    """Ruleset metadata."""

    ruleset_id: str
    name: str
    version: str
    industry: str
    description: str
    detectors_count: int
