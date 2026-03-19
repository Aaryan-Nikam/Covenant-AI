"""
Ironpass — Detection result data models.

All detection layers return Detection objects.
The Detection Engine returns a unified list regardless of which layer found them.
"""

from pydantic import BaseModel, Field


class Detection(BaseModel):
    """
    A single sensitive data detection.
    Returned by all detection layers — regex, luhn, and NER.
    """

    detector_id: str = Field(
        ...,
        description='Unique detector identifier, e.g. "visa_card", "ssn", "patient_name"',
    )
    data_type: str = Field(
        ...,
        description='Data classification, e.g. "credit_card", "ssn", "person_name"',
    )
    value: str = Field(
        ...,
        description="The actual matched value (raw, before any action is applied)",
    )
    position: tuple[int, int] = Field(
        ...,
        description="(start, end) character index in the original content",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score from 0.0 to 1.0",
    )
    layer: int = Field(
        ...,
        description="Which detection layer found this: 1=regex, 2=luhn, 3=ner",
    )
    ruleset_id: str = Field(
        ...,
        description="Which ruleset triggered this detection",
    )
    context: str | None = Field(
        default=None,
        description="Surrounding text for audit context (50 chars each side)",
    )


class ActionConfig(BaseModel):
    """Action configuration for a specific data type within a ruleset."""

    primary: str = Field(
        ...,
        description='Primary action: "tokenize", "mask", "block", or "pseudonymize"',
    )
    fallback: str = Field(
        ...,
        description="Fallback action if primary fails. Usually 'block'.",
    )
    log_level: str = Field(
        ...,
        description='Severity: "critical", "high", "medium", "low"',
    )
    mask_type: str = Field(
        default="partial",
        description="Masking strategy: 'partial', 'length_preserving', or 'label'",
    )


class DetectorConfig(BaseModel):
    """Configuration for a single detector within a ruleset."""

    id: str
    name: str
    data_type: str
    layer: int = Field(..., ge=1, le=3)

    # Layer 1 (regex) fields
    patterns: list[str] | None = None

    # Layer 3 (NER) fields
    entity_class: str | None = None
    context_required: dict | None = None

    confidence_threshold: float = Field(default=0.9, ge=0.0, le=1.0)


class AuditConfig(BaseModel):
    """Audit configuration for a ruleset."""

    retention_days: int = Field(..., gt=0)
    required_fields: list[str]


class Ruleset(BaseModel):
    """
    A complete parsed and validated ruleset.
    Loaded from YAML, validated, and registered in the RulesetRegistry.
    """

    ruleset_id: str
    name: str
    version: str
    industry: str
    description: str
    detectors: list[DetectorConfig]
    actions: dict[str, ActionConfig]
    audit: AuditConfig

    def get_detector_ids(self) -> list[str]:
        """Return all detector IDs in this ruleset."""
        return [d.id for d in self.detectors]

    def get_patterns_for_layer(self, layer: int) -> dict[str, list[str]]:
        """Return {detector_id: patterns} for all detectors of a given layer."""
        result = {}
        for d in self.detectors:
            if d.layer == layer and d.patterns:
                result[d.id] = d.patterns
        return result

    def get_action_for_data_type(self, data_type: str) -> ActionConfig | None:
        """Get the action config for a specific data type."""
        return self.actions.get(data_type)

    def get_ner_detectors(self) -> list[DetectorConfig]:
        """Return all NER (layer 3) detectors."""
        return [d for d in self.detectors if d.layer == 3]


class ActionTaken(BaseModel):
    """Records what action was applied to a detection."""

    detector_id: str
    data_type: str
    action: str  # tokenize / mask / block / pseudonymize
    original_position: tuple[int, int]
    replacement: str  # The token, masked value, or pseudonym that replaced it
    ruleset_id: str
    log_level: str
