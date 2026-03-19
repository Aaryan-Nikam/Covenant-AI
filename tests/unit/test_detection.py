"""
Ironpass — Unit tests for detection components.

Tests:
- RegexDetector: pattern matching, position tracking, context extraction
- LuhnValidator: valid/invalid card numbers, filter_detections
- RulesetLoader: YAML loading and validation
- RulesetRegistry: registration, lookup, action merging
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

os.environ.setdefault("DATABASE_URL", "postgresql://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost")
os.environ.setdefault("AUDIT_HMAC_KEY", "a" * 64)
os.environ.setdefault("PSEUDONYM_SECRET_KEY", "b" * 64)
os.environ.setdefault("KEY_BACKEND", "local")
os.environ.setdefault("LOCAL_VAULT_KEY", "c" * 64)

from engine.detection.models import DetectorConfig, Detection
from engine.detection.regex_detector import RegexDetector
from engine.detection.luhn_validator import LuhnValidator
from engine.rulesets.loader import RulesetLoader
from engine.rulesets.registry import RulesetRegistry
from engine.rulesets.validator import RulesetValidator
from engine.exceptions import RulesetValidationError, RulesetNotFoundError


# ===========================================================================
# RegexDetector Tests
# ===========================================================================

class TestRegexDetector:
    def setup_method(self):
        self.regex = RegexDetector()

    def test_visa_detection(self):
        det = DetectorConfig(id="visa", name="Visa", data_type="credit_card", layer=1,
                             patterns=[r"\b4[0-9]{12}(?:[0-9]{3})?\b"], confidence_threshold=0.95)
        hits = self.regex.scan("My card is 4111111111111111", [det], "pci_dss")
        assert len(hits) == 1
        assert hits[0].value == "4111111111111111"
        assert hits[0].data_type == "credit_card"
        assert hits[0].position == (11, 27)

    def test_ssn_detection(self):
        det = DetectorConfig(id="ssn", name="SSN", data_type="ssn", layer=1,
                             patterns=[r"\b(?!000|666)[0-9]{3}-(?!00)[0-9]{2}-(?!0000)[0-9]{4}\b"],
                             confidence_threshold=0.99)
        hits = self.regex.scan("SSN: 123-45-6789", [det], "hipaa")
        assert len(hits) == 1
        assert hits[0].value == "123-45-6789"

    def test_email_detection(self):
        det = DetectorConfig(id="email", name="Email", data_type="email", layer=1,
                             patterns=[r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b"],
                             confidence_threshold=0.99)
        hits = self.regex.scan("Contact john@example.com for info", [det], "gdpr")
        assert len(hits) == 1
        assert hits[0].value == "john@example.com"

    def test_api_key_detection(self):
        det = DetectorConfig(id="api_key", name="API Key", data_type="api_key", layer=1,
                             patterns=[r"\bsk-[A-Za-z0-9]{48}\b"], confidence_threshold=0.9)
        fake_key = "sk-" + "a" * 48
        hits = self.regex.scan(f"Key: {fake_key}", [det], "soc2")
        assert len(hits) == 1

    def test_multiple_detections(self):
        visa = DetectorConfig(id="visa", name="Visa", data_type="credit_card", layer=1,
                              patterns=[r"\b4[0-9]{12}(?:[0-9]{3})?\b"], confidence_threshold=0.95)
        ssn = DetectorConfig(id="ssn", name="SSN", data_type="ssn", layer=1,
                             patterns=[r"\b(?!000|666)[0-9]{3}-(?!00)[0-9]{2}-(?!0000)[0-9]{4}\b"],
                             confidence_threshold=0.99)
        hits = self.regex.scan("Card 4111111111111111 SSN 123-45-6789", [visa, ssn], "test")
        assert len(hits) == 2

    def test_no_match(self):
        det = DetectorConfig(id="visa", name="Visa", data_type="credit_card", layer=1,
                             patterns=[r"\b4[0-9]{12}(?:[0-9]{3})?\b"], confidence_threshold=0.95)
        hits = self.regex.scan("No sensitive data here", [det], "test")
        assert len(hits) == 0

    def test_context_extraction(self):
        det = DetectorConfig(id="visa", name="Visa", data_type="credit_card", layer=1,
                             patterns=[r"\b4[0-9]{12}(?:[0-9]{3})?\b"], confidence_threshold=0.95)
        content = "Here is the number " + "4111111111111111" + " end of data"
        hits = self.regex.scan(content, [det], "test")
        assert len(hits) == 1
        assert hits[0].context is not None
        assert "4111111111111111" in hits[0].context

    def test_skips_ner_detectors(self):
        ner_det = DetectorConfig(id="name", name="Name", data_type="person_name", layer=3,
                                 entity_class="PERSON", confidence_threshold=0.8)
        hits = self.regex.scan("John Smith patient", [ner_det], "test")
        assert len(hits) == 0


# ===========================================================================
# LuhnValidator Tests
# ===========================================================================

class TestLuhnValidator:
    def setup_method(self):
        self.luhn = LuhnValidator()

    def test_valid_visa(self):
        assert self.luhn.validate("4111111111111111") is True

    def test_valid_mastercard(self):
        assert self.luhn.validate("5500000000000004") is True

    def test_valid_amex(self):
        assert self.luhn.validate("378282246310005") is True

    def test_valid_discover(self):
        assert self.luhn.validate("6011111111111117") is True

    def test_invalid_random(self):
        assert self.luhn.validate("1234567890123456") is False

    def test_too_short(self):
        assert self.luhn.validate("12345") is False

    def test_strips_hyphens(self):
        assert self.luhn.validate("4111-1111-1111-1111") is True

    def test_strips_spaces(self):
        assert self.luhn.validate("4111 1111 1111 1111") is True

    def test_filter_detections_validates_cards(self):
        detections = [
            Detection(detector_id="visa", data_type="credit_card", value="4111111111111111",
                      position=(0, 16), confidence=0.95, layer=1, ruleset_id="pci_dss"),
            Detection(detector_id="fake", data_type="credit_card", value="1234567890123456",
                      position=(20, 36), confidence=0.95, layer=1, ruleset_id="pci_dss"),
            Detection(detector_id="ssn", data_type="ssn", value="123-45-6789",
                      position=(40, 51), confidence=0.99, layer=1, ruleset_id="hipaa"),
        ]
        filtered = self.luhn.filter_detections(detections)
        assert len(filtered) == 2  # Valid visa + SSN passthrough
        assert filtered[0].data_type == "credit_card"
        assert filtered[0].layer == 2  # Upgraded
        assert filtered[1].data_type == "ssn"  # Passthrough


# ===========================================================================
# Ruleset Tests
# ===========================================================================

class TestRulesetLoader:
    def test_load_all_rulesets(self):
        loader = RulesetLoader()
        rulesets = loader.load_all()
        assert len(rulesets) == 4
        assert "pci_dss" in rulesets
        assert "hipaa" in rulesets
        assert "gdpr" in rulesets
        assert "soc2" in rulesets

    def test_pci_dss_has_card_detectors(self):
        loader = RulesetLoader()
        rulesets = loader.load_all()
        pci = rulesets["pci_dss"]
        detector_ids = pci.get_detector_ids()
        assert "visa_card" in detector_ids
        assert "mastercard" in detector_ids
        assert "amex_card" in detector_ids

    def test_hipaa_has_ner_detector(self):
        loader = RulesetLoader()
        rulesets = loader.load_all()
        hipaa = rulesets["hipaa"]
        ner = hipaa.get_ner_detectors()
        assert len(ner) == 1
        assert ner[0].entity_class == "PERSON"

    def test_cvv_is_always_blocked(self):
        loader = RulesetLoader()
        rulesets = loader.load_all()
        pci = rulesets["pci_dss"]
        cvv_action = pci.get_action_for_data_type("cvv")
        assert cvv_action is not None
        assert cvv_action.primary == "block"


class TestRulesetValidator:
    def test_rejects_missing_fields(self):
        validator = RulesetValidator()
        with pytest.raises(RulesetValidationError):
            validator.validate({"ruleset_id": "test"})

    def test_rejects_cvv_non_block(self):
        validator = RulesetValidator()
        raw = {
            "ruleset_id": "test", "name": "Test", "version": "1",
            "industry": "test", "description": "test",
            "detectors": [{"id": "cvv", "name": "CVV", "data_type": "cvv",
                           "layer": 1, "patterns": [r"\d{3}"]}],
            "actions": {"cvv": {"primary": "tokenize", "fallback": "block", "log_level": "critical"}},
            "audit": {"retention_days": 365, "required_fields": ["timestamp"]},
        }
        with pytest.raises(RulesetValidationError) as exc_info:
            validator.validate(raw)
        assert "CVV must always have action 'block'" in str(exc_info.value)


class TestRulesetRegistry:
    def test_register_and_lookup(self):
        loader = RulesetLoader()
        rulesets = loader.load_all()
        registry = RulesetRegistry()
        registry.register_all(rulesets)
        assert registry.is_registered("pci_dss")
        pci = registry.get("pci_dss")
        assert pci.name == "PCI-DSS v4.0"

    def test_not_found_raises(self):
        registry = RulesetRegistry()
        with pytest.raises(RulesetNotFoundError):
            registry.get("nonexistent")

    def test_merge_actions_highest_severity_wins(self):
        loader = RulesetLoader()
        rulesets = loader.load_all()
        registry = RulesetRegistry()
        registry.register_all(rulesets)
        merged = registry.get_merged_actions(["pci_dss", "hipaa"])
        assert "credit_card" in merged
        assert "ssn" in merged


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
