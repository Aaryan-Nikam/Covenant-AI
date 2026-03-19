"""
Ironpass — Detection Engine.

Orchestrates all 3 detection layers: regex → luhn → NER.
Returns a unified, deduplicated list of Detection objects.

Detection flow:
1. Get active rulesets from registry
2. Run Layer 1 (regex) on all active detector patterns
3. Run Layer 2 (luhn) on credit_card detections to filter false positives
4. Run Layer 3 (NER) only if content has context keywords AND Layer 1/2 had hits
5. Deduplicate overlapping detections (same position)
6. Return sorted detections list

Architecture doc reference: Component 2 — Detection Engine.
"""

import logging

from engine.detection.luhn_validator import LuhnValidator
from engine.detection.models import Detection
from engine.detection.ner_detector import NERDetector
from engine.detection.regex_detector import RegexDetector
from engine.detection.normalizer import ContentNormalizer
from engine.rulesets.registry import RulesetRegistry
from engine.config import get_settings

logger = logging.getLogger("ironpass.detection.engine")


class DetectionEngine:
    """
    Orchestrates all detection layers.
    Returns list of Detection objects — never modifies content.
    """

    def __init__(self, ruleset_registry: RulesetRegistry):
        self.normalizer = ContentNormalizer()
        self.regex_detector = RegexDetector()
        self.luhn_validator = LuhnValidator()
        self.ner_detector = NERDetector()  # Loads spaCy model at init (Critical Rule #5)
        self.ruleset_registry = ruleset_registry

    async def scan(
        self,
        content: str,
        active_rulesets: list[str],
    ) -> list[Detection]:
        """
        Run all detection layers across all active rulesets.
        Returns deduplicated list of Detection objects.

        Detection pipeline:
        1. Regex (Layer 1) — fast pattern matching
        2. Luhn (Layer 2) — validate card numbers from Layer 1
        3. NER (Layer 3) — context-aware NER, only if Layer 1/2 had hits

        Architecture rule: Never run Layer 3 if content has zero Layer 1/2 hits.
        """
        all_detections: list[Detection] = []
        normalized_content = self.normalizer.normalize(content)

        for ruleset_id in active_rulesets:
            ruleset = self.ruleset_registry.get(ruleset_id)

            # --- Layer 1: Regex ---
            layer1_detectors = [d for d in ruleset.detectors if d.layer == 1]
            regex_hits = self.regex_detector.scan(
                normalized_content, layer1_detectors, ruleset_id
            )
            logger.debug(
                f"[{ruleset_id}] Layer 1 (regex): {len(regex_hits)} hits"
            )

            # --- Layer 2: Luhn validation (card numbers only) ---
            validated_hits = self.luhn_validator.filter_detections(regex_hits)
            logger.debug(
                f"[{ruleset_id}] Layer 2 (luhn): "
                f"{len(regex_hits)} → {len(validated_hits)} after validation"
            )

            all_detections.extend(validated_hits)

            # --- Layer 3: NER (only if Layer 1/2 had hits) ---
            ner_detectors = ruleset.get_ner_detectors()
            if ner_detectors and len(validated_hits) > 0:
                ner_hits = self.ner_detector.scan(
                    normalized_content, ner_detectors, ruleset_id
                )
                logger.debug(
                    f"[{ruleset_id}] Layer 3 (NER): {len(ner_hits)} hits"
                )
                all_detections.extend(ner_hits)
            elif ner_detectors:
                logger.debug(
                    f"[{ruleset_id}] Layer 3 (NER): skipped — "
                    f"no Layer 1/2 hits (performance optimization)"
                )

        # --- Deduplicate overlapping detections ---
        deduplicated = self._deduplicate(all_detections)
        logger.info(
            f"Detection complete: {len(all_detections)} raw → "
            f"{len(deduplicated)} after dedup"
        )

        return deduplicated

    def _deduplicate(self, detections: list[Detection]) -> list[Detection]:
        """
        Remove overlapping detections at the same position.

        When multiple detections at the same (start, end) exist:
        - Keep the one with the highest confidence
        - If tied, prefer higher layer (NER > Luhn > Regex)
        """
        if not detections:
            return []

        # Group by position
        by_position: dict[tuple[int, int], list[Detection]] = {}
        for det in detections:
            pos = det.position
            if pos not in by_position:
                by_position[pos] = []
            by_position[pos].append(det)

        # For each position, keep the best detection
        priority_list = get_settings().ruleset_priority

        def get_rs_rank(rid: str) -> int:
            try:
                return len(priority_list) - priority_list.index(rid)
            except ValueError:
                return -1

        result: list[Detection] = []
        for pos, dets in by_position.items():
            best = max(
                dets,
                key=lambda d: (get_rs_rank(d.ruleset_id), d.confidence, d.layer),
            )
            result.append(best)

        # Sort by position (ascending) for stable output
        result.sort(key=lambda d: d.position[0])

        return result
