"""
Ironpass — Unit tests for action components.

Tests:
- Masker: type-specific masking rules
- Blocker: ComplianceViolation raising
- Pseudonymizer: deterministic output
- AuditSigner: chain signing and verification
- VaultEncryptor: AES-256-GCM round-trip
- KeyManager: local backend key retrieval
"""

import sys
import os
import asyncio
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

os.environ.setdefault("REDIS_URL", "redis://localhost")
os.environ.setdefault("AUDIT_HMAC_KEY", "a" * 64)
os.environ.setdefault("PSEUDONYM_SECRET_KEY", "b" * 64)
os.environ.setdefault("KEY_BACKEND", "local")
os.environ.setdefault("LOCAL_VAULT_KEY", "c" * 64)

from datetime import datetime, timezone
from engine.actions.masker import Masker
from engine.actions.blocker import Blocker
from engine.actions.pseudonymizer import Pseudonymizer
from engine.audit.signer import AuditSigner
from engine.vault.encryption import VaultEncryptor
from engine.vault.key_manager import KeyManager
from engine.detection.models import Detection
from engine.exceptions import ComplianceViolation


# ===========================================================================
# Masker Tests
# ===========================================================================

class TestMasker:
    def setup_method(self):
        self.masker = Masker()

    def test_credit_card(self):
        assert self.masker.mask("4111111111111111", "credit_card") == "****-****-****-1111"

    def test_ssn(self):
        assert self.masker.mask("123-45-6789", "ssn") == "***-**-6789"

    def test_cvv(self):
        assert self.masker.mask("123", "cvv") == "***"

    def test_email(self):
        assert self.masker.mask("john@example.com", "email") == "j***@example.com"

    def test_person_name(self):
        assert self.masker.mask("John Smith", "person_name") == "John S."

    def test_ip_address(self):
        assert self.masker.mask("192.168.1.100", "ip_address") == "192.168.*.*"

    def test_api_key(self):
        assert self.masker.mask("sk_live_abc123", "api_key") == "[REDACTED_API_KEY]"

    def test_password(self):
        assert self.masker.mask("password=s3cret", "password") == "[REDACTED_PASSWORD]"

    def test_passport(self):
        assert self.masker.mask("AB1234567", "passport") == "AB*******"

    def test_bank_account(self):
        assert self.masker.mask("GB29NWBK60161331926819", "bank_account") == "******************6819"

    def test_dob(self):
        result = self.masker.mask("01/15/1985", "date_of_birth")
        assert "1985" in result

    def test_phone(self):
        result = self.masker.mask("555-123-4567", "phone_number")
        assert result.endswith("4567")

    def test_generic(self):
        assert self.masker.mask("anything", "unknown_type") == "[REDACTED]"


# ===========================================================================
# Blocker Tests
# ===========================================================================

class TestBlocker:
    def test_raises_compliance_violation(self):
        blocker = Blocker()
        det = Detection(
            detector_id="cvv", data_type="cvv", value="123",
            position=(0, 3), confidence=0.9, layer=1, ruleset_id="pci_dss",
        )
        with pytest.raises(ComplianceViolation) as exc_info:
            blocker.block(det)
        assert exc_info.value.data_type == "cvv"
        assert exc_info.value.ruleset_id == "pci_dss"
        assert exc_info.value.detector_id == "cvv"


# ===========================================================================
# Pseudonymizer Tests
# ===========================================================================

class TestPseudonymizer:
    def setup_method(self):
        self.pseudo = Pseudonymizer()

    def test_deterministic(self):
        r1 = self.pseudo.pseudonymize("John Smith", "person_name")
        r2 = self.pseudo.pseudonymize("John Smith", "person_name")
        assert r1 == r2

    def test_different_inputs_different_outputs(self):
        r1 = self.pseudo.pseudonymize("John Smith", "person_name")
        r2 = self.pseudo.pseudonymize("Jane Doe", "person_name")
        assert r1 != r2

    def test_email_format(self):
        result = self.pseudo.pseudonymize("john@example.com", "email")
        assert "@" in result
        assert ".com" in result or ".org" in result or ".net" in result

    def test_phone_format(self):
        result = self.pseudo.pseudonymize("+1-555-123-4567", "phone_number")
        assert result.startswith("+1-")


# ===========================================================================
# AuditSigner Tests
# ===========================================================================

class TestAuditSigner:
    def setup_method(self):
        self.signer = AuditSigner()

    def test_sign_returns_hex_string(self):
        sig = self.signer.sign_entry(
            entry_id="test-1", timestamp=datetime.now(timezone.utc),
            agent_id="agent-1", request_hash="abc", rulesets_used=["pci_dss"],
            detections=[], actions_taken=[], was_blocked=False,
            target_url="https://api.openai.com", latency_ms=50,
            outcome="passed", prev_entry_hash=None,
        )
        assert len(sig) == 64  # SHA-256 hex = 64 chars
        assert all(c in "0123456789abcdef" for c in sig)

    def test_chain_verified(self):
        entries = []
        prev_hash = None
        for i in range(5):
            eid = f"entry-{i}"
            ts = datetime.now(timezone.utc)
            sig = self.signer.sign_entry(
                entry_id=eid, timestamp=ts, agent_id="agent",
                request_hash="hash", rulesets_used=["pci_dss"],
                detections=[], actions_taken=[], was_blocked=False,
                target_url=None, latency_ms=10, outcome="passed",
                prev_entry_hash=prev_hash,
            )
            entries.append({
                "entry_id": eid, "timestamp": ts.isoformat(),
                "agent_id": "agent", "request_hash": "hash",
                "rulesets_used": ["pci_dss"], "detections": [],
                "actions_taken": [], "was_blocked": False,
                "target_url": None, "latency_ms": 10,
                "outcome": "passed", "hmac_signature": sig,
                "prev_entry_hash": prev_hash,
            })
            prev_hash = self.signer.compute_entry_hash(eid, sig)
        valid, err = self.signer.verify_chain(entries)
        assert valid is True
        assert err is None

    def test_tampering_detected(self):
        entries = []
        prev_hash = None
        for i in range(3):
            eid = f"entry-{i}"
            ts = datetime.now(timezone.utc)
            sig = self.signer.sign_entry(
                entry_id=eid, timestamp=ts, agent_id="agent",
                request_hash="hash", rulesets_used=["test"],
                detections=[], actions_taken=[], was_blocked=False,
                target_url=None, latency_ms=10, outcome="passed",
                prev_entry_hash=prev_hash,
            )
            entries.append({
                "entry_id": eid, "timestamp": ts.isoformat(),
                "agent_id": "agent", "request_hash": "hash",
                "rulesets_used": ["test"], "detections": [],
                "actions_taken": [], "was_blocked": False,
                "target_url": None, "latency_ms": 10,
                "outcome": "passed", "hmac_signature": sig,
                "prev_entry_hash": prev_hash,
            })
            prev_hash = self.signer.compute_entry_hash(eid, sig)
        # Tamper with entry 1
        entries[1]["agent_id"] = "HACKER"
        valid, err = self.signer.verify_chain(entries)
        assert valid is False
        assert "Signature mismatch" in err


# ===========================================================================
# Encryption Tests
# ===========================================================================

class TestVaultEncryption:
    def test_round_trip(self):
        enc = VaultEncryptor(None)
        key = bytes.fromhex("c" * 64)
        plaintext = "4111111111111111"
        ct, nonce = enc.encrypt(plaintext, key)
        result = enc.decrypt(ct, nonce, key)
        assert result == plaintext

    def test_unique_nonces(self):
        enc = VaultEncryptor(None)
        key = bytes.fromhex("c" * 64)
        _, n1 = enc.encrypt("test1", key)
        _, n2 = enc.encrypt("test2", key)
        _, n3 = enc.encrypt("test3", key)
        assert n1 != n2
        assert n2 != n3

    def test_tamper_detection(self):
        from engine.exceptions import VaultDecryptionError
        enc = VaultEncryptor(None)
        key = bytes.fromhex("c" * 64)
        ct, nonce = enc.encrypt("secret", key)
        tampered = bytearray(ct)
        tampered[0] ^= 0xFF  # Flip a byte
        with pytest.raises(VaultDecryptionError):
            enc.decrypt(bytes(tampered), nonce, key)


# ===========================================================================
# KeyManager Tests
# ===========================================================================

class TestKeyManager:
    def test_local_backend(self):
        km = KeyManager()
        key, version = asyncio.get_event_loop().run_until_complete(
            km.get_current_key()
        )
        assert len(key) == 32
        assert version == "v1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
