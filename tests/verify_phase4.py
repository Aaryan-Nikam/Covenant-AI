"""Quick verification test for Phase 4 proxy and audit components."""
import sys
sys.path.insert(0, '.')

import os
os.environ.setdefault('REDIS_URL', 'redis://localhost')
os.environ.setdefault('AUDIT_HMAC_KEY', 'a' * 64)
os.environ.setdefault('PSEUDONYM_SECRET_KEY', 'b' * 64)
os.environ.setdefault('KEY_BACKEND', 'local')
os.environ.setdefault('LOCAL_VAULT_KEY', 'c' * 64)

# Test 1: Syntax check
import py_compile
files = [
    'engine/audit/signer.py',
    'engine/audit/logger.py',
    'engine/proxy/request_model.py',
    'engine/proxy/interceptor.py',
    'engine/proxy/router.py',
    'engine/main.py',
]
for f in files:
    py_compile.compile(f, doraise=True)
    print(f'✅ Syntax OK: {f}')
print()

# Test 2: Audit signer — sign and verify chain
from datetime import datetime, timezone
from engine.audit.signer import AuditSigner

signer = AuditSigner()

entries = []
prev_hash = None

for i in range(3):
    entry_id = f"entry-{i}"
    ts = datetime.now(timezone.utc)
    sig = signer.sign_entry(
        entry_id=entry_id, timestamp=ts, agent_id="agent-1",
        request_hash="abc123", rulesets_used=["pci_dss"],
        detections=[], actions_taken=[], was_blocked=False,
        target_url="https://api.openai.com", latency_ms=50,
        outcome="passed", prev_entry_hash=prev_hash,
    )
    entries.append({
        "entry_id": entry_id, "timestamp": ts.isoformat(),
        "agent_id": "agent-1", "request_hash": "abc123",
        "rulesets_used": ["pci_dss"], "detections": [],
        "actions_taken": [], "was_blocked": False,
        "target_url": "https://api.openai.com", "latency_ms": 50,
        "outcome": "passed", "hmac_signature": sig,
        "prev_entry_hash": prev_hash,
    })
    prev_hash = signer.compute_entry_hash(entry_id, sig)

is_valid, error = signer.verify_chain(entries)
assert is_valid, f"Chain should be valid: {error}"
print('✅ Audit signer: 3-entry chain signed and verified')

# Test 3: Verify tampering is detected
tampered = [e.copy() for e in entries]
tampered[1]["agent_id"] = "HACKER"
is_valid, error = signer.verify_chain(tampered)
assert not is_valid, "Tampered chain should be invalid"
assert "Signature mismatch" in error
print(f'✅ Audit signer: tampering detected — "{error[:50]}..."')

# Test 4: Proxy models validate correctly
from engine.proxy.request_model import ProxyRequest, ProxyResponse, BlockedResponse

req = ProxyRequest(
    target_url="https://api.openai.com/v1/chat/completions",
    content='{"messages": [{"role": "user", "content": "My card is 4111111111111111"}]}',
    agent_id="agent-1",
    rulesets=["pci_dss"],
)
assert req.target_url == "https://api.openai.com/v1/chat/completions"
assert len(req.rulesets) == 1
print('✅ Proxy models: request/response models validate correctly')

# Test 5: Router imports and can create FastAPI router
from engine.proxy.router import router
assert len(router.routes) > 0
route_paths = [r.path for r in router.routes]
assert "/scan" in route_paths
assert "/rulesets" in route_paths
print(f'✅ Proxy router: {len(router.routes)} routes registered ({", ".join(route_paths)})')

print('\n🎉 All Phase 4 verification tests passed!')
