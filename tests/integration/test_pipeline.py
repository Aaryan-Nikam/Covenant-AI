"""
Ironpass — Integration tests.

Tests the full detection + action pipeline end-to-end without
a real database (vault operations are not tested here as they
require PostgreSQL).

Tests:
- Full pipeline: content → detections → actions → sanitized output
- Multiple rulesets active simultaneously
- Audit chain integrity over multiple entries
- Endpoint accessibility via live server
"""

import sys
import os
import pytest
import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

os.environ.setdefault("DATABASE_URL", "postgresql://x:x@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost")
os.environ.setdefault("AUDIT_HMAC_KEY", "a" * 64)
os.environ.setdefault("PSEUDONYM_SECRET_KEY", "b" * 64)
os.environ.setdefault("KEY_BACKEND", "local")
os.environ.setdefault("LOCAL_VAULT_KEY", "c" * 64)

from engine.detection.regex_detector import RegexDetector
from engine.detection.luhn_validator import LuhnValidator
from engine.detection.models import DetectorConfig
from engine.actions.masker import Masker
from engine.actions.pseudonymizer import Pseudonymizer
from engine.rulesets.loader import RulesetLoader
from engine.rulesets.registry import RulesetRegistry


# ===========================================================================
# Integration: Detection + Action Pipeline
# ===========================================================================

class TestDetectionToActionPipeline:
    """Test the complete detection → action flow without DB."""

    def setup_method(self):
        self.regex = RegexDetector()
        self.luhn = LuhnValidator()
        self.masker = Masker()
        self.pseudo = Pseudonymizer()
        # Load real rulesets
        loader = RulesetLoader()
        self.rulesets = loader.load_all()
        self.registry = RulesetRegistry()
        self.registry.register_all(self.rulesets)

    def test_pci_dss_card_detection_and_masking(self):
        """PCI-DSS: detect a Visa card, validate with Luhn, mask it."""
        content = "Pay with card 4111111111111111 for order #1234"
        pci = self.rulesets["pci_dss"]

        # Layer 1: Regex
        layer1_dets = [d for d in pci.detectors if d.layer == 1]
        regex_hits = self.regex.scan(content, layer1_dets, "pci_dss")
        # Should detect the Visa card
        card_hits = [h for h in regex_hits if h.data_type == "credit_card"]
        assert len(card_hits) >= 1
        assert card_hits[0].value == "4111111111111111"

        # Layer 2: Luhn
        validated = self.luhn.filter_detections(regex_hits)
        card_validated = [d for d in validated if d.data_type == "credit_card"]
        assert len(card_validated) >= 1
        assert card_validated[0].layer == 2

        # Apply mask action (PCI-DSS action for credit_card is tokenize, but we test mask)
        masked = self.masker.mask("4111111111111111", "credit_card")
        assert masked == "****-****-****-1111"
        assert "4111" not in masked[:15]

    def test_hipaa_ssn_detection(self):
        """HIPAA: detect SSN."""
        content = "Patient SSN: 123-45-6789 admitted today"
        hipaa = self.rulesets["hipaa"]

        layer1_dets = [d for d in hipaa.detectors if d.layer == 1]
        regex_hits = self.regex.scan(content, layer1_dets, "hipaa")
        ssn_hits = [h for h in regex_hits if h.data_type == "ssn"]
        assert len(ssn_hits) == 1
        assert ssn_hits[0].value == "123-45-6789"

    def test_gdpr_email_detection(self):
        """GDPR: detect email addresses."""
        content = "Contact user at john.doe@example.com for GDPR inquiry"
        gdpr = self.rulesets["gdpr"]

        layer1_dets = [d for d in gdpr.detectors if d.layer == 1]
        regex_hits = self.regex.scan(content, layer1_dets, "gdpr")
        email_hits = [h for h in regex_hits if h.data_type == "email"]
        assert len(email_hits) == 1
        assert email_hits[0].value == "john.doe@example.com"

    def test_soc2_api_key_detection(self):
        """SOC2: detect API keys."""
        fake_key = "sk-" + "a" * 48
        content = f"Using API key {fake_key} for production"
        soc2 = self.rulesets["soc2"]

        layer1_dets = [d for d in soc2.detectors if d.layer == 1]
        regex_hits = self.regex.scan(content, layer1_dets, "soc2")
        key_hits = [h for h in regex_hits if h.data_type == "api_key"]
        assert len(key_hits) >= 1

    def test_multi_ruleset_detection(self):
        """Multiple rulesets: detect card + SSN in same content."""
        content = "Card: 4111111111111111, SSN: 123-45-6789, Email: test@example.com"

        all_detections = []
        for rid in ["pci_dss", "hipaa", "gdpr"]:
            rs = self.rulesets[rid]
            layer1 = [d for d in rs.detectors if d.layer == 1]
            hits = self.regex.scan(content, layer1, rid)
            all_detections.extend(hits)

        data_types = {d.data_type for d in all_detections}
        assert "credit_card" in data_types
        assert "ssn" in data_types
        assert "email" in data_types

    def test_no_false_positives_on_clean_text(self):
        """No detections on clean text."""
        content = "This is a perfectly normal business email about quarterly reports."
        all_detections = []
        for rid, rs in self.rulesets.items():
            layer1 = [d for d in rs.detectors if d.layer == 1]
            hits = self.regex.scan(content, layer1, rid)
            all_detections.extend(hits)
        assert len(all_detections) == 0

    def test_action_merge_priority(self):
        """Merged actions: highest severity wins."""
        merged = self.registry.get_merged_actions(["pci_dss", "hipaa"])
        # credit_card should be tokenize (from PCI-DSS)
        assert merged["credit_card"].primary == "tokenize"
        # ssn should be tokenize (from HIPAA)
        assert merged["ssn"].primary == "tokenize"

    def test_pseudonymizer_consistency(self):
        """Pseudonymized names are consistent across calls."""
        name1 = self.pseudo.pseudonymize("Dr. Sarah Johnson", "person_name")
        name2 = self.pseudo.pseudonymize("Dr. Sarah Johnson", "person_name")
        name3 = self.pseudo.pseudonymize("Dr. John Smith", "person_name")
        assert name1 == name2
        assert name1 != name3

    def test_luhn_rejects_invalid_then_valid(self):
        """Luhn correctly filters mixed valid/invalid cards."""
        dets = [
            DetectorConfig(id="visa", name="Visa", data_type="credit_card", layer=1,
                           patterns=[r"\b4[0-9]{15}\b"], confidence_threshold=0.95),
        ]
        content = "Cards: 4111111111111111 and 4999999999999999"
        hits = self.regex.scan(content, dets, "test")
        validated = self.luhn.filter_detections(hits)
        # Only the valid Visa should survive
        card_hits = [d for d in validated if d.data_type == "credit_card"]
        for h in card_hits:
            assert self.luhn.validate(h.value) is True


# ===========================================================================
# Integration: Audit Chain
# ===========================================================================

class TestAuditChainIntegrity:
    """Test HMAC chain integrity over multiple entries."""

    def test_long_chain(self):
        from engine.audit.signer import AuditSigner
        from datetime import datetime, timezone

        signer = AuditSigner()
        entries = []
        prev_hash = None

        for i in range(20):
            eid = f"entry-{i}"
            ts = datetime.now(timezone.utc)
            sig = signer.sign_entry(
                entry_id=eid, timestamp=ts, agent_id=f"agent-{i % 3}",
                request_hash=f"hash-{i}", rulesets_used=["pci_dss", "hipaa"],
                detections=[{"data_type": "credit_card"}] if i % 2 == 0 else [],
                actions_taken=[{"action": "tokenize"}] if i % 2 == 0 else [],
                was_blocked=(i % 5 == 0), target_url="https://api.openai.com",
                latency_ms=50 + i, outcome="blocked" if i % 5 == 0 else "passed",
                prev_entry_hash=prev_hash,
            )
            entries.append({
                "entry_id": eid, "timestamp": ts.isoformat(),
                "agent_id": f"agent-{i % 3}", "request_hash": f"hash-{i}",
                "rulesets_used": ["pci_dss", "hipaa"],
                "detections": [{"data_type": "credit_card"}] if i % 2 == 0 else [],
                "actions_taken": [{"action": "tokenize"}] if i % 2 == 0 else [],
                "was_blocked": (i % 5 == 0),
                "target_url": "https://api.openai.com",
                "latency_ms": 50 + i,
                "outcome": "blocked" if i % 5 == 0 else "passed",
                "hmac_signature": sig, "prev_entry_hash": prev_hash,
            })
            prev_hash = signer.compute_entry_hash(eid, sig)

        valid, err = signer.verify_chain(entries)
        assert valid is True, f"Chain should be valid: {err}"

    def test_middle_tamper_detected(self):
        """Tampering in the middle of a chain is detected."""
        from engine.audit.signer import AuditSigner
        from datetime import datetime, timezone

        signer = AuditSigner()
        entries = []
        prev_hash = None

        for i in range(10):
            eid = f"entry-{i}"
            ts = datetime.now(timezone.utc)
            sig = signer.sign_entry(
                entry_id=eid, timestamp=ts, agent_id="agent",
                request_hash="h", rulesets_used=["test"],
                detections=[], actions_taken=[], was_blocked=False,
                target_url=None, latency_ms=10, outcome="passed",
                prev_entry_hash=prev_hash,
            )
            entries.append({
                "entry_id": eid, "timestamp": ts.isoformat(),
                "agent_id": "agent", "request_hash": "h",
                "rulesets_used": ["test"], "detections": [],
                "actions_taken": [], "was_blocked": False,
                "target_url": None, "latency_ms": 10,
                "outcome": "passed", "hmac_signature": sig,
                "prev_entry_hash": prev_hash,
            })
            prev_hash = signer.compute_entry_hash(eid, sig)

        # Tamper entry 5
        entries[5]["latency_ms"] = 99999
        valid, err = signer.verify_chain(entries)
        assert valid is False
        assert "entry 5" in err.lower() or "entry-5" in err


# ===========================================================================
# Integration: Live Server Endpoints
# ===========================================================================

class TestLiveEndpoints:
    """Test live server endpoints (server must be running on port 8000)."""

    BASE = "http://localhost:8000"

    def _server_is_running(self) -> bool:
        try:
            r = httpx.get(f"{self.BASE}/health", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def test_health(self):
        if not self._server_is_running():
            pytest.skip("Server not running")
        r = httpx.get(f"{self.BASE}/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"

    def test_list_rulesets(self):
        if not self._server_is_running():
            pytest.skip("Server not running")
        r = httpx.get(f"{self.BASE}/proxy/rulesets")
        assert r.status_code == 200
        data = r.json()
        assert len(data["rulesets"]) == 4

    def test_get_ruleset_detail(self):
        if not self._server_is_running():
            pytest.skip("Server not running")
        r = httpx.get(f"{self.BASE}/proxy/rulesets/pci_dss")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "PCI-DSS v4.0"
        assert len(data["detectors"]) == 6

    def test_unknown_ruleset_404(self):
        if not self._server_is_running():
            pytest.skip("Server not running")
        r = httpx.get(f"{self.BASE}/proxy/rulesets/nonexistent")
        assert r.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
