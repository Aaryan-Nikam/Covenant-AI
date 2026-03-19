"""
Ironpass — Layer 1: Regex pattern matching detector.

Fast, deterministic pattern detection. No ML.
Every pattern defined in active rulesets is run against content.
Only runs patterns specified by active rulesets — never all patterns always.
"""

import logging
import re

from engine.detection.models import Detection, DetectorConfig

logger = logging.getLogger("ironpass.detection.regex")


class RegexDetector:
    """
    Layer 1: Pattern-based detection.
    Runs only the regex patterns specified by the active rulesets.
    Returns a list of Detection objects with position, confidence, and context.
    """

    def scan(
        self,
        content: str,
        detectors: list[DetectorConfig],
        ruleset_id: str,
    ) -> list[Detection]:
        """
        Run regex patterns from the given detectors against content.
        Returns all matches as Detection objects.
        """
        detections: list[Detection] = []

        for detector in detectors:
            if not detector.patterns:
                continue
            for pattern in detector.patterns:
                try:
                    compiled = re.compile(pattern)
                except re.error as e:
                    logger.warning(
                        f"Invalid regex pattern in detector '{detector.id}': {e}"
                    )
                    continue

                for match in compiled.finditer(content):
                    # If regex has capture groups, use group 1, else entire match
                    if compiled.groups > 0:
                        value = match.group(1)
                        start, end = match.start(1), match.end(1)
                    else:
                        value = match.group()
                        start, end = match.start(), match.end()

                    # Check context_required if present
                    if detector.context_required and "keywords" in detector.context_required:
                        keywords = detector.context_required["keywords"]
                        window_start = max(0, start - 100)
                        window_end = min(len(content), end + 100)
                        window_text = content[window_start:window_end].lower()
                        
                        has_context = any(keyword.lower() in window_text for keyword in keywords)
                        if not has_context:
                            continue  # Skip detection if required context is missing

                    # Extract context — 50 chars each side
                    ctx_start = max(0, start - 50)
                    ctx_end = min(len(content), end + 50)
                    context = content[ctx_start:ctx_end]

                    detection = Detection(
                        detector_id=detector.id,
                        data_type=detector.data_type,
                        value=value,
                        position=(start, end),
                        confidence=detector.confidence_threshold,
                        layer=1,
                        ruleset_id=ruleset_id,
                        context=context,
                    )
                    detections.append(detection)

        return detections
