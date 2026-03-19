"""
Ironpass — Blocker: raises ComplianceViolation.

When a detection's action is "block", the request is NOT forwarded.
The agent receives HTTP 403 with structured error.

Critical Rule #7: Block is immediate. No further detections processed.
Critical Rule #11: CVV is always blocked. No exceptions.
"""

import logging

from engine.detection.models import Detection
from engine.exceptions import ComplianceViolation

logger = logging.getLogger("ironpass.actions.blocker")


class Blocker:
    """
    Raises ComplianceViolation immediately.
    The request is never forwarded to the target LLM.
    No further detections are processed after a block.
    """

    def block(self, detection: Detection) -> None:
        """
        Raise ComplianceViolation — stops the pipeline immediately.

        This is not a normal return — it raises an exception that
        propagates up through the ActionExecutor and ProxyInterceptor,
        resulting in an HTTP 403 response to the agent.
        """
        logger.warning(
            f"BLOCKED: {detection.data_type} detected by "
            f"'{detection.detector_id}' in ruleset '{detection.ruleset_id}' "
            f"at position {detection.position}"
        )

        raise ComplianceViolation(
            ruleset_id=detection.ruleset_id,
            detector_id=detection.detector_id,
            data_type=detection.data_type,
            message=(
                f"Compliance violation: {detection.data_type} detected. "
                f"Request blocked by {detection.ruleset_id} ruleset."
            ),
        )
