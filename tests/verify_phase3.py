"""Quick verification test for Phase 3 actions and vault components."""
import sys
sys.path.insert(0, '.')

# Test 1: Syntax check all Phase 3 files
import py_compile
files = [
    'engine/vault/key_manager.py',
    'engine/vault/encryption.py',
    'engine/vault/vault.py',
    'engine/actions/tokenizer.py',
    'engine/actions/masker.py',
    'engine/actions/blocker.py',
    'engine/actions/pseudonymizer.py',
    'engine/actions/executor.py',
]
for f in files:
    py_compile.compile(f, doraise=True)
    print(f'✅ Syntax OK: {f}')

print()

# Test 2: AES-256-GCM encryption round-trip
import os
os.environ.setdefault('REDIS_URL', 'redis://localhost')
os.environ.setdefault('AUDIT_HMAC_KEY', 'a' * 64)
os.environ.setdefault('PSEUDONYM_SECRET_KEY', 'b' * 64)
os.environ.setdefault('KEY_BACKEND', 'local')
os.environ.setdefault('LOCAL_VAULT_KEY', 'c' * 64)

from engine.vault.encryption import VaultEncryptor
enc = VaultEncryptor(None)

key = bytes.fromhex('c' * 64)
plaintext = "4111111111111111"
ct, nonce = enc.encrypt(plaintext, key)
decrypted = enc.decrypt(ct, nonce, key)
assert decrypted == plaintext, f"Round-trip failed: {decrypted} != {plaintext}"
print('✅ AES-256-GCM: encryption round-trip passed')

# Verify nonce is unique per call
_, nonce2 = enc.encrypt(plaintext, key)
assert nonce != nonce2, "Nonces must be unique (Critical Rule #12)"
print('✅ AES-256-GCM: unique nonces verified')

# Test 3: Masker
from engine.actions.masker import Masker
masker = Masker()

assert masker.mask("4111111111111111", "credit_card") == "****-****-****-1111"
assert masker.mask("123-45-6789", "ssn") == "***-**-6789"
assert masker.mask("123", "cvv") == "***"
assert masker.mask("john@example.com", "email") == "j***@example.com"
assert masker.mask("John Smith", "person_name") == "John S."
assert masker.mask("192.168.1.100", "ip_address") == "192.168.*.*"
assert masker.mask("sk_live_abc123", "api_key") == "[REDACTED_API_KEY]"
assert masker.mask("password=s3cret", "password") == "[REDACTED_PASSWORD]"
print('✅ Masker: all 8 type-specific masks correct')

# Test 4: Pseudonymizer determinism
from engine.actions.pseudonymizer import Pseudonymizer
pseudo = Pseudonymizer()

name1 = pseudo.pseudonymize("John Smith", "person_name")
name2 = pseudo.pseudonymize("John Smith", "person_name")
name3 = pseudo.pseudonymize("Jane Doe", "person_name")
assert name1 == name2, "Same input must produce same output"
assert name1 != name3, "Different inputs should produce different outputs"
print(f'✅ Pseudonymizer: deterministic (John Smith → {name1})')

# Test 5: Blocker raises ComplianceViolation
from engine.actions.blocker import Blocker
from engine.detection.models import Detection
from engine.exceptions import ComplianceViolation

blocker = Blocker()
det = Detection(
    detector_id='cvv', data_type='cvv', value='123',
    position=(0, 3), confidence=0.9, layer=1, ruleset_id='pci_dss',
)
try:
    blocker.block(det)
    assert False, "Should have raised"
except ComplianceViolation as e:
    assert e.data_type == 'cvv'
    print(f'✅ Blocker: ComplianceViolation raised for CVV')

# Test 6: Key manager (local backend)
from engine.vault.key_manager import KeyManager
import asyncio

async def test_key_manager():
    km = KeyManager()
    key, version = await km.get_current_key()
    assert len(key) == 32, f"Key must be 32 bytes, got {len(key)}"
    assert version == "v1"
    print(f'✅ Key manager: local backend, key={len(key)} bytes, version={version}')

asyncio.run(test_key_manager())

print('\n🎉 All Phase 3 verification tests passed!')
