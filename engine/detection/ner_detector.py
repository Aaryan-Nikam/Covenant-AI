"""
Ironpass — Layer 3: spaCy Named Entity Recognition detector.

Context-aware detection using spaCy en_core_web_sm model.
Detects: PERSON, ORG, GPE, DATE entities.

Critical Rule #5: Load model ONCE at class instantiation.
Never reload on each scan call. NERDetector is a singleton.

Only runs when:
  - Active ruleset has NER detectors AND
  - Content contains required context keywords (if specified)
"""

import logging

from engine.detection.models import Detection, DetectorConfig

logger = logging.getLogger("ironpass.detection.ner")


class NERDetector:
    """
    Layer 3: Context-aware Named Entity Recognition.
    Uses spaCy en_core_web_lg model — loaded ONCE at init.
    """

    def __init__(self, model_name: str = "en_core_web_sm"):
        """
        Load spaCy model at initialization.
        Critical Rule #5: This only happens once. The NERDetector instance
        is reused across all requests via FastAPI dependency injection.
        """
        try:
            import spacy
            self.nlp = spacy.load(model_name)
            logger.info(f"spaCy model '{model_name}' loaded successfully")
        except ImportError:
            logger.warning(
                "spaCy not installed. NER detection disabled. "
                "Install with: pip install spacy && "
                f"python -m spacy download {model_name}"
            )
            self.nlp = None
        except OSError:
            logger.warning(
                f"spaCy model '{model_name}' not found. "
                f"NER detection disabled. "
                f"Install with: python -m spacy download {model_name}"
            )
            self.nlp = None

    def scan(
        self,
        content: str,
        detectors: list[DetectorConfig],
        ruleset_id: str,
    ) -> list[Detection]:
        """
        Run NER on content for the specified detectors.
        Only runs if context keywords are found (when context_required is set).

        Args:
            content: Text to scan
            detectors: NER detector configs (layer 3 only)
            ruleset_id: Which ruleset triggered this
        """
        if self.nlp is None:
            logger.debug("spaCy model not loaded — skipping NER")
            return []

        detections: list[Detection] = []
        doc = None

        for detector in detectors:
            if detector.layer != 3:
                continue

            # Check context keywords if required
            if detector.context_required:
                keywords = detector.context_required.get("keywords", [])
                if keywords and not self._has_context(content, keywords):
                    logger.debug(
                        f"NER detector '{detector.id}' skipped — "
                        f"no context keywords found"
                    )
                    continue

            # Run spaCy NER — parse doc only once per scan
            if doc is None:
                doc = self.nlp(content)

            for ent in doc.ents:
                # Only process entities matching the detector's entity_class
                if ent.label_ != detector.entity_class:
                    continue

                # Skip very short entities (likely noise)
                if len(ent.text.strip()) < 2:
                    continue

                # Calculate confidence based on spaCy's score
                # spaCy entities don't have a direct confidence, so we use
                # a heuristic based on entity length and context
                confidence = self._calculate_confidence(ent, content)

                if confidence < detector.confidence_threshold:
                    continue

                # Extract context — 50 chars each side
                ctx_start = max(0, ent.start_char - 50)
                ctx_end = min(len(content), ent.end_char + 50)
                context = content[ctx_start:ctx_end]

                detection = Detection(
                    detector_id=detector.id,
                    data_type=detector.data_type,
                    value=ent.text,
                    position=(ent.start_char, ent.end_char),
                    confidence=confidence,
                    layer=3,
                    ruleset_id=ruleset_id,
                    context=context,
                )
                detections.append(detection)

        return detections

    def _has_context(self, content: str, keywords: list[str]) -> bool:
        """Check if at least one context keyword is present in content."""
        content_lower = content.lower()
        return any(keyword.lower() in content_lower for keyword in keywords)

    def _calculate_confidence(self, entity, content: str) -> float:
        """
        Calculate a confidence score for a spaCy entity.
        Heuristic based on:
        - Entity text length (longer = more confident)
        - Whether entity is a multi-word name
        - Context proximity to other entities
        """
        base_confidence = 0.80

        # Multi-word names are more reliable
        words = entity.text.strip().split()
        if len(words) >= 2:
            base_confidence += 0.10
        if len(words) >= 3:
            base_confidence += 0.05

        # Longer entities tend to be more reliable
        if len(entity.text) > 10:
            base_confidence += 0.03

        return min(base_confidence, 1.0)
