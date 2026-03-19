"""
Ironpass — Action Executor.

Takes the list of detections from the Detection Engine and applies
the action defined in the ruleset config for each detection type.
Returns modified content with sensitive data replaced.

Critical Rule #2: Actions applied in REVERSE position order (end → start)
to preserve character positions.

Critical Rule #7: If BLOCK triggered, raise ComplianceViolation immediately.

Action priority for overlapping detections:
  BLOCK > TOKENIZE > PSEUDONYMIZE > MASK
"""

import logging

from engine.actions.blocker import Blocker
from engine.actions.masker import Masker
from engine.actions.pseudonymizer import Pseudonymizer
from engine.actions.tokenizer import Tokenizer
from engine.detection.models import ActionConfig, ActionTaken, Detection
from engine.exceptions import ComplianceViolation
from engine.vault.vault import TokenVault

logger = logging.getLogger("ironpass.actions.executor")


# Action priority — higher number = higher severity
ACTION_PRIORITY = {
    "mask": 1,
    "pseudonymize": 2,
    "tokenize": 3,
    "block": 4,
}


class ExecutionResult:
    """Result of action execution on content."""

    def __init__(
        self,
        modified_content: str,
        actions_taken: list[ActionTaken],
        session_token_map: dict[str, str],
        was_blocked: bool,
    ):
        self.modified_content = modified_content
        self.actions_taken = actions_taken
        self.session_token_map = session_token_map
        self.was_blocked = was_blocked


class ActionExecutor:
    """
    Applies ruleset-defined actions to detected sensitive data.
    Processes detections in REVERSE position order to preserve indices.
    """

    def __init__(self, vault: TokenVault | None):
        self.vault = vault
        self.tokenizer = Tokenizer(vault) if vault else None
        self.masker = Masker()
        self.blocker = Blocker()
        self.pseudonymizer = Pseudonymizer()

    async def execute(
        self,
        content: str,
        detections: list[Detection],
        ruleset_actions: dict[str, ActionConfig],
        agent_id: str,
    ) -> ExecutionResult:
        """
        Apply actions to all detections in reverse position order.

        Returns ExecutionResult with:
        - modified_content: str (sensitive data replaced)
        - actions_taken: list[ActionTaken]
        - session_token_map: dict (token → display value for de-tokenization)
        - was_blocked: bool

        Raises ComplianceViolation if a BLOCK action is triggered.
        """
        # Resolve overlapping detections — highest severity wins
        resolved = self._resolve_overlaps(detections, ruleset_actions)

        # Sort by position DESCENDING — process end-to-start (Critical Rule #2)
        resolved.sort(key=lambda d: d.position[0], reverse=True)

        modified = content
        actions_taken: list[ActionTaken] = []
        session_token_map: dict[str, str] = {}

        for detection in resolved:
            action_config = ruleset_actions.get(detection.data_type)
            if action_config is None:
                logger.warning(
                    f"No action config for data_type '{detection.data_type}' "
                    f"— skipping detection"
                )
                continue

            action_type = action_config.primary
            start, end = detection.position

            try:
                replacement = await self._apply_action(
                    action_type=action_type,
                    detection=detection,
                    agent_id=agent_id,
                    session_token_map=session_token_map,
                    action_config=action_config,
                )

                # Replace in content at the correct position
                modified = modified[:start] + replacement + modified[end:]

                actions_taken.append(
                    ActionTaken(
                        detector_id=detection.detector_id,
                        data_type=detection.data_type,
                        action=action_type,
                        original_position=detection.position,
                        replacement=replacement,
                        ruleset_id=detection.ruleset_id,
                        log_level=action_config.log_level,
                    )
                )

            except ComplianceViolation:
                # Block — log the action and re-raise
                actions_taken.append(
                    ActionTaken(
                        detector_id=detection.detector_id,
                        data_type=detection.data_type,
                        action="block",
                        original_position=detection.position,
                        replacement="[BLOCKED]",
                        ruleset_id=detection.ruleset_id,
                        log_level=action_config.log_level,
                    )
                )
                raise  # Critical Rule #7: block is immediate

            except Exception as e:
                # Primary action failed — try fallback
                logger.warning(
                    f"Primary action '{action_type}' failed for "
                    f"{detection.detector_id}: {e}. Trying fallback."
                )
                fallback_type = action_config.fallback
                try:
                    replacement = await self._apply_action(
                        action_type=fallback_type,
                        detection=detection,
                        agent_id=agent_id,
                        session_token_map=session_token_map,
                        action_config=action_config,
                    )
                    modified = modified[:start] + replacement + modified[end:]

                    actions_taken.append(
                        ActionTaken(
                            detector_id=detection.detector_id,
                            data_type=detection.data_type,
                            action=f"{fallback_type} (fallback)",
                            original_position=detection.position,
                            replacement=replacement,
                            ruleset_id=detection.ruleset_id,
                            log_level=action_config.log_level,
                        )
                    )
                except ComplianceViolation:
                    actions_taken.append(
                        ActionTaken(
                            detector_id=detection.detector_id,
                            data_type=detection.data_type,
                            action="block (fallback)",
                            original_position=detection.position,
                            replacement="[BLOCKED]",
                            ruleset_id=detection.ruleset_id,
                            log_level=action_config.log_level,
                        )
                    )
                    raise

        return ExecutionResult(
            modified_content=modified,
            actions_taken=actions_taken,
            session_token_map=session_token_map,
            was_blocked=False,
        )

    async def _apply_action(
        self,
        action_type: str,
        detection: Detection,
        agent_id: str,
        session_token_map: dict[str, str],
        action_config: ActionConfig,
    ) -> str:
        """Apply a single action and return the replacement string."""
        if action_type == "block":
            self.blocker.block(detection)
            return "[BLOCKED]"  # Never reached — block raises

        elif action_type == "tokenize":
            if self.tokenizer is None:
                raise RuntimeError(
                    "Vault unavailable — tokenize not possible. "
                    "Will fall back to mask."
                )
            token = await self.tokenizer.tokenize(
                value=detection.value,
                data_type=detection.data_type,
                agent_id=agent_id,
            )
            # Store mapping for de-tokenizing the response later
            session_token_map[token] = self._get_display_value(
                detection.value, detection.data_type
            )
            return token

        elif action_type == "mask":
            # Mask type might be partial, label, or length_preserving
            mask_type = getattr(action_config, "mask_type", "partial")
            return self.masker.mask(detection.value, detection.data_type, mask_type)

        elif action_type == "pseudonymize":
            return self.pseudonymizer.pseudonymize(
                detection.value, detection.data_type
            )

        else:
            raise ValueError(f"Unknown action type: {action_type}")

    def _resolve_overlaps(
        self,
        detections: list[Detection],
        ruleset_actions: dict[str, ActionConfig],
    ) -> list[Detection]:
        """
        When multiple detections overlap in position,
        keep only the one with the highest severity action.

        Action priority: BLOCK > TOKENIZE > PSEUDONYMIZE > MASK
        """
        if not detections:
            return []

        # Sort by start position, then by length descending
        sorted_dets = sorted(
            detections, key=lambda d: (d.position[0], -(d.position[1] - d.position[0]))
        )

        resolved: list[Detection] = []
        last_end = -1

        for det in sorted_dets:
            start, end = det.position

            if start >= last_end:
                # No overlap — add directly
                resolved.append(det)
                last_end = end
            else:
                # Overlap detected — compare priorities
                prev = resolved[-1]
                prev_action = ruleset_actions.get(prev.data_type)
                curr_action = ruleset_actions.get(det.data_type)

                prev_priority = ACTION_PRIORITY.get(
                    prev_action.primary if prev_action else "", 0
                )
                curr_priority = ACTION_PRIORITY.get(
                    curr_action.primary if curr_action else "", 0
                )

                if curr_priority > prev_priority:
                    # Current detection has higher priority — replace previous
                    resolved[-1] = det
                    last_end = end

        return resolved

    def _get_display_value(self, value: str, data_type: str) -> str:
        """
        Get a safe display value for de-tokenizing responses.
        Cards: show last 4 only
        SSN: never restore in response
        Names: restore fully
        """
        if data_type == "credit_card":
            digits = "".join(c for c in value if c.isdigit())
            return f"****{digits[-4:]}" if len(digits) >= 4 else "****"
        elif data_type == "ssn":
            return "[SSN PROTECTED]"  # SSN never restored in response
        elif data_type == "person_name":
            return value  # Names restore fully
        elif data_type == "passport":
            return f"{value[:2]}****" if len(value) >= 2 else "****"
        elif data_type == "bank_account":
            return f"****{value[-4:]}" if len(value) >= 4 else "****"
        else:
            return f"[{data_type.upper()}]"
