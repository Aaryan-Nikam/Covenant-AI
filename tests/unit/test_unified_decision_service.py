"""Unit tests for unified decision service."""

import asyncio
import os
from types import SimpleNamespace

os.environ.setdefault("REDIS_URL", "redis://localhost")
os.environ.setdefault(
    "AUDIT_HMAC_KEY",
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
)
os.environ.setdefault(
    "PSEUDONYM_SECRET_KEY",
    "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
)
os.environ.setdefault("KEY_BACKEND", "local")
os.environ.setdefault("LOCAL_VAULT_KEY", "11" * 32)

from engine.agent_security.schemas import (  # noqa: E402
    AgentSecurityPolicyConfig,
    AgentSecurityPolicyResponse,
    ContextExfiltrationAnalyzeResponse,
    DeniedToolPermission,
    MemorySessionAuditResponse,
    PromptInjectionAnalyzeResponse,
    SecurityDecisionEnforcementPlan,
    SecurityDecisionEvaluateResponse,
    SecurityFinding,
    ToolPermissionEvaluateResponse,
)
from engine.decisions.schemas import UnifiedDecisionEvaluateRequest  # noqa: E402
from engine.decisions.service import UnifiedDecisionService  # noqa: E402
from engine.detection.models import ActionConfig, Detection  # noqa: E402


class _FakeExecuteResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDB:
    def __init__(self, existing=None):
        self.existing = existing
        self.added = []

    async def execute(self, _query):
        return _FakeExecuteResult(self.existing)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None


class _FakeAuditWriter:
    async def log_request(self, **_kwargs):
        return "audit-entry-123"


class _FakeDetectionEngine:
    async def scan(self, _content, _active_rulesets):
        return [
            Detection(
                detector_id="visa_card",
                data_type="credit_card",
                value="4111111111111111",
                position=(10, 26),
                confidence=0.99,
                layer=2,
                ruleset_id="pci_dss",
                context="card 4111111111111111",
            )
        ]


class _FakeRegistry:
    def get_merged_actions(self, _active_rulesets):
        return {
            "credit_card": ActionConfig(
                primary="tokenize",
                fallback="block",
                log_level="critical",
            )
        }

    def get(self, ruleset_id):
        if ruleset_id != "pci_dss":
            raise KeyError(ruleset_id)
        return SimpleNamespace(ruleset_id="pci_dss", version="4.0")


class _FakeAgentSecurityService:
    async def get_or_create_policy(self, tenant_id):
        return AgentSecurityPolicyResponse(
            tenant_id=tenant_id,
            version=2,
            updated_at="2026-05-20T00:00:00+00:00",
            config=AgentSecurityPolicyConfig(mode="enforce"),
        )

    async def evaluate_decision(self, tenant_id, request):
        return SecurityDecisionEvaluateResponse(
            request_id=request.request_id or "req-1",
            tenant_id=tenant_id,
            policy_version=2,
            action="review",
            overall_risk_score=62,
            decision_timestamp="2026-05-20T00:00:00+00:00",
            security_signature="a" * 64,
            findings=[
                SecurityFinding(
                    finding_id="pi-1",
                    category="prompt_injection",
                    severity="high",
                    title="Prompt Injection Signal",
                    evidence="ignore previous instructions",
                    recommendation="block",
                )
            ],
            prompt_injection=PromptInjectionAnalyzeResponse(
                risk_score=70,
                blocked=True,
                attack_strings_detected=["ignore previous instructions"],
                findings=[],
                sanitized_content="sanitized",
            ),
            context_exfiltration=ContextExfiltrationAnalyzeResponse(
                risk_score=60,
                findings=[],
                leak_hits=[],
                redacted_output="safe",
            ),
            tool_permissions=ToolPermissionEvaluateResponse(
                risk_score=20,
                findings=[],
                least_privilege_set=[],
                denied=[DeniedToolPermission(tool_name="payments", reason="irrelevant")],
            ),
            memory_audit=MemorySessionAuditResponse(
                risk_score=10,
                findings=[],
                flagged_items=[],
                recommended_ttl_turns=10,
            ),
            enforcement_plan=SecurityDecisionEnforcementPlan(
                sanitized_untrusted_content="sanitized",
                redacted_output="safe",
                granted_tools=[],
                denied_tools=[],
                memory_actions=[],
            ),
        )


class TestUnifiedDecisionService:
    def test_returns_signed_unified_decision(self):
        tenant = SimpleNamespace(id="tenant-1", agent_id="agent-1", active_rulesets=["pci_dss"])
        request = UnifiedDecisionEvaluateRequest(
            request_id="req-123",
            task_instruction="Review SLA breaches",
            untrusted_content="customer card 4111111111111111",
            candidate_output="summary",
            rulesets=["pci_dss"],
        )
        service = UnifiedDecisionService(
            _FakeDB(),
            agent_security_service=_FakeAgentSecurityService(),
            audit_writer=_FakeAuditWriter(),
        )
        result = asyncio.get_event_loop().run_until_complete(
            service.evaluate_decision(
                tenant=tenant,
                request=request,
                registry=_FakeRegistry(),
                detection_engine=_FakeDetectionEngine(),
            )
        )
        assert result.outcome in {"review", "block"}
        assert result.signed is True
        assert len(result.signature) == 64
        assert result.audit_entry_id == "audit-entry-123"
        assert result.risk.components.pii_detection.weight == 0.2
        assert "tokenize" in result.actions_applied
        assert result.evidence.policy_version == "2"
        assert any(item.type == "PII" for item in result.evidence.detections)

    def test_idempotent_returns_existing_payload(self):
        payload = {
            "decision_id": "d-1",
            "request_id": "req-1",
            "tenant_id": "tenant-1",
            "agent_id": "agent-1",
            "timestamp": "2026-05-20T00:00:00+00:00",
            "outcome": "allow",
            "signed": True,
            "signature": "a" * 64,
            "risk": {
                "overall_score": 0.1,
                "tier": "low",
                "components": {
                    "pii_detection": {"score": 0.0, "weight": 0.2},
                    "prompt_injection": {"score": 0.1, "weight": 0.3},
                    "exfiltration": {"score": 0.1, "weight": 0.25},
                    "tool_permissions": {"score": 0.0, "weight": 0.15},
                    "memory_hygiene": {"score": 0.0, "weight": 0.1},
                },
            },
            "evidence": {"detections": [], "ruleset_version": "none", "policy_version": "2"},
            "actions_applied": [],
            "audit_entry_id": "audit-existing",
            "error": None,
        }
        existing_log = SimpleNamespace(decision_payload=payload)
        service = UnifiedDecisionService(
            _FakeDB(existing=existing_log),
            agent_security_service=_FakeAgentSecurityService(),
            audit_writer=_FakeAuditWriter(),
        )
        tenant = SimpleNamespace(id="tenant-1", agent_id="agent-1", active_rulesets=["pci_dss"])
        request = UnifiedDecisionEvaluateRequest(request_id="req-1")
        result = asyncio.get_event_loop().run_until_complete(
            service.evaluate_decision(
                tenant=tenant,
                request=request,
                registry=_FakeRegistry(),
                detection_engine=_FakeDetectionEngine(),
            )
        )
        assert result.decision_id == "d-1"
        assert result.audit_entry_id == "audit-existing"

