"""
Ironpass — Ruleset schema validator.

Validates every YAML ruleset before it can be loaded into the registry.
Any ruleset that fails validation is rejected with a clear error message.

Critical Rule #9: Ruleset YAML is the only config — no Python code changes required.
Critical Rule #11: CVV is always blocked — validator enforces this.
"""

import logging

from engine.detection.models import (
    ActionConfig,
    AuditConfig,
    DetectorConfig,
    Ruleset,
)
from engine.exceptions import RulesetValidationError

logger = logging.getLogger("ironpass.rulesets.validator")

# Valid action types
VALID_ACTIONS = {"tokenize", "mask", "block", "pseudonymize"}

# Valid log levels
VALID_LOG_LEVELS = {"critical", "high", "medium", "low"}

# Valid NER entity classes
VALID_ENTITY_CLASSES = {"PERSON", "ORG", "GPE", "DATE"}

# Required top-level fields
REQUIRED_TOP_LEVEL = {"ruleset_id", "name", "version", "industry", "description", "detectors", "actions", "audit"}


class RulesetValidator:
    """
    Validates raw YAML dict against the ruleset schema.

    Validation checks:
    - All required top-level fields present
    - Every detector has required fields (id, name, data_type, layer)
    - Layer 1 detectors have patterns list
    - Layer 3 detectors have entity_class
    - Every detector's data_type referenced in actions exists
    - action.primary is one of: tokenize, mask, block, pseudonymize
    - audit.retention_days is positive integer
    - CVV data_type can only have action "block" (Critical Rule #11)
    """

    def validate(self, raw: dict) -> Ruleset:
        """
        Validate raw YAML dict and return a Ruleset object.
        Raises RulesetValidationError with specific field message if invalid.
        """
        ruleset_id = raw.get("ruleset_id", "<unknown>")

        # --- Top-level fields ---
        missing = REQUIRED_TOP_LEVEL - set(raw.keys())
        if missing:
            raise RulesetValidationError(
                ruleset_id=ruleset_id,
                field=", ".join(sorted(missing)),
                reason=f"Missing required top-level fields: {sorted(missing)}",
            )

        # --- Validate detectors ---
        raw_detectors = raw.get("detectors", [])
        if not isinstance(raw_detectors, list) or len(raw_detectors) == 0:
            raise RulesetValidationError(
                ruleset_id=ruleset_id,
                field="detectors",
                reason="Must be a non-empty list",
            )

        detectors: list[DetectorConfig] = []
        detector_ids: set[str] = set()
        data_types_from_detectors: set[str] = set()

        for i, det_raw in enumerate(raw_detectors):
            det = self._validate_detector(ruleset_id, det_raw, i)
            if det.id in detector_ids:
                raise RulesetValidationError(
                    ruleset_id=ruleset_id,
                    field=f"detectors[{i}].id",
                    reason=f"Duplicate detector id: '{det.id}'",
                )
            detector_ids.add(det.id)
            data_types_from_detectors.add(det.data_type)
            detectors.append(det)

        # --- Validate actions ---
        raw_actions = raw.get("actions", {})
        if not isinstance(raw_actions, dict) or len(raw_actions) == 0:
            raise RulesetValidationError(
                ruleset_id=ruleset_id,
                field="actions",
                reason="Must be a non-empty dict",
            )

        actions: dict[str, ActionConfig] = {}
        for data_type, action_raw in raw_actions.items():
            action = self._validate_action(ruleset_id, data_type, action_raw)

            # Critical Rule #11: CVV is always blocked
            if data_type == "cvv" and action.primary != "block":
                raise RulesetValidationError(
                    ruleset_id=ruleset_id,
                    field=f"actions.{data_type}.primary",
                    reason="CVV must always have action 'block'. "
                    "No ruleset may override CVV to tokenize or mask.",
                )

            actions[data_type] = action

        # Verify all detector data_types have actions defined
        for dt in data_types_from_detectors:
            if dt not in actions:
                raise RulesetValidationError(
                    ruleset_id=ruleset_id,
                    field=f"actions.{dt}",
                    reason=f"Detector data_type '{dt}' has no action defined",
                )

        # --- Validate audit ---
        raw_audit = raw.get("audit", {})
        audit = self._validate_audit(ruleset_id, raw_audit)

        # --- Build Ruleset ---
        return Ruleset(
            ruleset_id=raw["ruleset_id"],
            name=raw["name"],
            version=str(raw["version"]),
            industry=raw["industry"],
            description=raw["description"],
            detectors=detectors,
            actions=actions,
            audit=audit,
        )

    def _validate_detector(
        self, ruleset_id: str, raw: dict, index: int
    ) -> DetectorConfig:
        """Validate a single detector config."""
        prefix = f"detectors[{index}]"

        for field in ("id", "name", "data_type", "layer"):
            if field not in raw:
                raise RulesetValidationError(
                    ruleset_id=ruleset_id,
                    field=f"{prefix}.{field}",
                    reason=f"Missing required field '{field}'",
                )

        layer = raw["layer"]
        if layer not in (1, 3):
            raise RulesetValidationError(
                ruleset_id=ruleset_id,
                field=f"{prefix}.layer",
                reason=f"Layer must be 1 (regex) or 3 (NER), got {layer}",
            )

        # Layer 1 must have patterns
        if layer == 1:
            patterns = raw.get("patterns")
            if not patterns or not isinstance(patterns, list):
                raise RulesetValidationError(
                    ruleset_id=ruleset_id,
                    field=f"{prefix}.patterns",
                    reason="Layer 1 detectors must have a non-empty patterns list",
                )

        # Layer 3 must have entity_class
        if layer == 3:
            entity_class = raw.get("entity_class")
            if not entity_class:
                raise RulesetValidationError(
                    ruleset_id=ruleset_id,
                    field=f"{prefix}.entity_class",
                    reason="Layer 3 detectors must have entity_class",
                )
            if entity_class not in VALID_ENTITY_CLASSES:
                raise RulesetValidationError(
                    ruleset_id=ruleset_id,
                    field=f"{prefix}.entity_class",
                    reason=f"Invalid entity_class '{entity_class}'. "
                    f"Must be one of: {sorted(VALID_ENTITY_CLASSES)}",
                )

        return DetectorConfig(
            id=raw["id"],
            name=raw["name"],
            data_type=raw["data_type"],
            layer=layer,
            patterns=raw.get("patterns"),
            entity_class=raw.get("entity_class"),
            context_required=raw.get("context_required"),
            confidence_threshold=raw.get("confidence_threshold", 0.9),
        )

    def _validate_action(
        self, ruleset_id: str, data_type: str, raw: dict
    ) -> ActionConfig:
        """Validate a single action config."""
        for field in ("primary", "fallback", "log_level"):
            if field not in raw:
                raise RulesetValidationError(
                    ruleset_id=ruleset_id,
                    field=f"actions.{data_type}.{field}",
                    reason=f"Missing required field '{field}'",
                )

        if raw["primary"] not in VALID_ACTIONS:
            raise RulesetValidationError(
                ruleset_id=ruleset_id,
                field=f"actions.{data_type}.primary",
                reason=f"Invalid action '{raw['primary']}'. "
                f"Must be one of: {sorted(VALID_ACTIONS)}",
            )

        if raw["fallback"] not in VALID_ACTIONS:
            raise RulesetValidationError(
                ruleset_id=ruleset_id,
                field=f"actions.{data_type}.fallback",
                reason=f"Invalid fallback '{raw['fallback']}'. "
                f"Must be one of: {sorted(VALID_ACTIONS)}",
            )

        if raw["log_level"] not in VALID_LOG_LEVELS:
            raise RulesetValidationError(
                ruleset_id=ruleset_id,
                field=f"actions.{data_type}.log_level",
                reason=f"Invalid log_level '{raw['log_level']}'. "
                f"Must be one of: {sorted(VALID_LOG_LEVELS)}",
            )

        return ActionConfig(
            primary=raw["primary"],
            fallback=raw["fallback"],
            log_level=raw["log_level"],
        )

    def _validate_audit(self, ruleset_id: str, raw: dict) -> AuditConfig:
        """Validate audit config."""
        if "retention_days" not in raw:
            raise RulesetValidationError(
                ruleset_id=ruleset_id,
                field="audit.retention_days",
                reason="Missing required field",
            )

        if not isinstance(raw["retention_days"], int) or raw["retention_days"] <= 0:
            raise RulesetValidationError(
                ruleset_id=ruleset_id,
                field="audit.retention_days",
                reason="Must be a positive integer",
            )

        if "required_fields" not in raw or not isinstance(
            raw["required_fields"], list
        ):
            raise RulesetValidationError(
                ruleset_id=ruleset_id,
                field="audit.required_fields",
                reason="Must be a non-empty list",
            )

        return AuditConfig(
            retention_days=raw["retention_days"],
            required_fields=raw["required_fields"],
        )
