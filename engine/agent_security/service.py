"""Business logic for the enterprise Agent Security Suite."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from engine.agent_security.models import AgentSecurityDecisionLog, AgentSecurityPolicy
from engine.agent_security.schemas import (
    AgentSecurityControlStatus,
    AgentSecurityOverviewResponse,
    AgentSecurityPolicyConfig,
    AgentSecurityPolicyResponse,
    AgentSecurityPolicyUpdateRequest,
    ContextExfiltrationAnalyzeRequest,
    ContextExfiltrationAnalyzeResponse,
    DecisionAction,
    DeniedToolPermission,
    GrantedToolPermission,
    LeakHit,
    MemoryLeakItem,
    MemorySessionAuditRequest,
    MemorySessionAuditResponse,
    PromptInjectionAnalyzeRequest,
    PromptInjectionAnalyzeResponse,
    SecurityDecisionEnforcementPlan,
    SecurityDecisionEvaluateRequest,
    SecurityDecisionEvaluateResponse,
    SecurityFinding,
    ToolPermissionEvaluateRequest,
    ToolPermissionEvaluateResponse,
)
from engine.config import get_settings

PROMPT_INJECTION_RULES: list[tuple[str, str, str, int, str]] = [
    (
        r"(?is)\b(ignore|disregard|bypass|override)\b.{0,80}\b(previous|system|developer|instruction)s?\b",
        "Instruction Override Attempt",
        "critical",
        35,
        "Treat this segment as untrusted data and preserve original task constraints.",
    ),
    (
        r"(?is)\b(system prompt|developer message|chain[- ]of[- ]thought|internal policy|secret policy)\b",
        "Prompt Boundary Probing",
        "high",
        20,
        "Block requests for hidden instructions and keep hidden reasoning private.",
    ),
    (
        r"(?is)\b(email|send|post|upload|forward|exfiltrat(?:e|ion)|leak|webhook)\b.{0,100}\b(password|secret|token|account|credential|api key|customer data|pii)\b",
        "Data Exfiltration Instruction",
        "critical",
        35,
        "Reject exfiltration instructions and force human review.",
    ),
    (
        r"(?is)<!--|display\s*:\s*none|opacity\s*:\s*0|font-size\s*:\s*0|visibility\s*:\s*hidden",
        "Hidden Content Channel",
        "high",
        25,
        "Strip hidden content and only process visible, trusted inputs.",
    ),
    (
        r"[\u200b-\u200f\u2060\ufeff]",
        "Invisible Unicode Obfuscation",
        "medium",
        15,
        "Normalize and remove invisible characters before agent parsing.",
    ),
    (
        r"(?is)\bbase64\b.{0,60}\b(decode|execute|eval|shell|curl|wget)\b",
        "Obfuscated Payload Trigger",
        "high",
        20,
        "Do not decode or execute obfuscated payloads from untrusted context.",
    ),
]

EXFIL_PATTERNS: list[tuple[str, str, int]] = [
    ("openai_key", r"\bsk-[A-Za-z0-9]{20,}\b", 30),
    ("aws_access_key", r"\bAKIA[0-9A-Z]{16}\b", 30),
    ("bearer_token", r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}\b", 25),
    ("jwt", r"\b[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\b", 25),
    ("credit_card", r"\b(?:\d[ -]*?){13,19}\b", 20),
    ("ssn", r"\b\d{3}-\d{2}-\d{4}\b", 20),
    ("email", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", 10),
]

READ_ONLY_VERBS = {
    "read",
    "review",
    "view",
    "monitor",
    "inspect",
    "audit",
    "check",
    "analyze",
    "analyse",
    "list",
    "search",
    "lookup",
    "find",
}

WRITE_VERBS = {
    "write",
    "update",
    "delete",
    "create",
    "send",
    "post",
    "modify",
    "grant",
    "revoke",
    "trigger",
}


class AgentSecurityService:
    """Enterprise analyzers and policy-driven decisioning for agent security."""

    def __init__(self, db_session: AsyncSession | None = None):
        self.db = db_session
        self.settings = get_settings()
        self._hmac_key = bytes.fromhex(self.settings.audit_hmac_key)

    def get_overview(self) -> AgentSecurityOverviewResponse:
        controls = [
            AgentSecurityControlStatus(
                control_id="prompt_injection_shield",
                title="Prompt Injection Shield",
                objective="Detect and neutralize hidden instructions in untrusted inputs.",
                status="operational",
            ),
            AgentSecurityControlStatus(
                control_id="context_exfiltration_guard",
                title="Context Exfiltration Guard",
                objective="Prevent sensitive data from leaking in outputs, traces, or tool payloads.",
                status="operational",
            ),
            AgentSecurityControlStatus(
                control_id="least_privilege_tool_gate",
                title="Least-Privilege Tool Gate",
                objective="Enforce minimal tool scope per task and deny irrelevant tool access.",
                status="operational",
            ),
            AgentSecurityControlStatus(
                control_id="memory_hygiene_auditor",
                title="Memory Hygiene Auditor",
                objective="Find and scrub sensitive long-lived session memory.",
                status="operational",
            ),
        ]
        return AgentSecurityOverviewResponse(
            suite_name="Agent Security Suite",
            generated_at=datetime.now(timezone.utc).isoformat(),
            controls=controls,
        )

    async def get_or_create_policy(self, tenant_id: str) -> AgentSecurityPolicyResponse:
        record = await self._get_policy_record(tenant_id)
        if record is None:
            if self.db is None:
                return AgentSecurityPolicyResponse(
                    tenant_id=tenant_id,
                    version=1,
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    config=AgentSecurityPolicyConfig(),
                )

            now = datetime.now(timezone.utc)
            record = AgentSecurityPolicy(
                tenant_id=tenant_id,
                version=1,
                policy_config=AgentSecurityPolicyConfig().model_dump(mode="json"),
                updated_by="system",
                created_at=now,
                updated_at=now,
            )
            self.db.add(record)
            await self.db.flush()

        config = AgentSecurityPolicyConfig.model_validate(record.policy_config or {})
        return AgentSecurityPolicyResponse(
            tenant_id=tenant_id,
            version=record.version,
            updated_at=record.updated_at.replace(tzinfo=timezone.utc).isoformat()
            if record.updated_at.tzinfo is None
            else record.updated_at.isoformat(),
            config=config,
        )

    async def update_policy(
        self,
        tenant_id: str,
        body: AgentSecurityPolicyUpdateRequest,
    ) -> AgentSecurityPolicyResponse:
        if self.db is None:
            raise RuntimeError("Database session is required for policy updates")

        record = await self._get_policy_record(tenant_id)
        now = datetime.now(timezone.utc)
        if record is None:
            record = AgentSecurityPolicy(
                tenant_id=tenant_id,
                version=1,
                policy_config=body.config.model_dump(mode="json"),
                updated_by=body.updated_by,
                created_at=now,
                updated_at=now,
            )
            self.db.add(record)
            await self.db.flush()
        else:
            if body.expected_version is not None and body.expected_version != record.version:
                raise ValueError(
                    f"Policy version mismatch. expected={body.expected_version}, actual={record.version}"
                )
            record.version += 1
            record.policy_config = body.config.model_dump(mode="json")
            record.updated_by = body.updated_by
            record.updated_at = now
            await self.db.flush()

        return AgentSecurityPolicyResponse(
            tenant_id=tenant_id,
            version=record.version,
            updated_at=record.updated_at.isoformat(),
            config=AgentSecurityPolicyConfig.model_validate(record.policy_config),
        )

    async def evaluate_decision(
        self,
        tenant_id: str,
        request: SecurityDecisionEvaluateRequest,
    ) -> SecurityDecisionEvaluateResponse:
        policy = await self.get_or_create_policy(tenant_id)
        request_id = request.request_id or str(uuid.uuid4())

        existing = await self._get_decision_log(tenant_id=tenant_id, request_id=request_id)
        if existing is not None:
            return SecurityDecisionEvaluateResponse.model_validate(existing.decision_payload)

        allowed_destinations = request.allowed_destinations or policy.config.allowed_destinations
        task_context = request.task_instruction or request.task_description

        prompt_result = self.analyze_prompt_injection(
            PromptInjectionAnalyzeRequest(
                task_instruction=task_context,
                untrusted_content=request.untrusted_content,
                allowed_actions=request.allowed_actions,
                block_threshold=policy.config.prompt_injection_block_threshold,
            )
        )

        exfil_result = self.analyze_context_exfiltration(
            ContextExfiltrationAnalyzeRequest(
                candidate_output=request.candidate_output,
                reasoning_trace=request.reasoning_trace,
                tool_payloads=request.tool_payloads,
                allowed_destinations=allowed_destinations,
            )
        )

        tool_result = self.evaluate_tool_permissions(
            ToolPermissionEvaluateRequest(
                task_description=task_context,
                tools=request.tools,
                requested_tools=request.requested_tools,
                max_tools=policy.config.max_tools_per_task,
            )
        )

        memory_result = self.audit_memory_session(
            MemorySessionAuditRequest(
                session_events=request.session_events,
                max_retention_turns=policy.config.memory_max_retention_turns,
            )
        )

        action = self._resolve_action(
            policy_mode=policy.config.mode,
            policy=policy.config,
            prompt_result=prompt_result,
            exfil_result=exfil_result,
            tool_result=tool_result,
            memory_result=memory_result,
        )

        overall_risk = _clamp_score(
            round(
                (
                    prompt_result.risk_score * 0.35
                    + exfil_result.risk_score * 0.35
                    + tool_result.risk_score * 0.2
                    + memory_result.risk_score * 0.1
                )
            )
        )

        aggregated_findings = _sort_findings(
            [
                *prompt_result.findings,
                *exfil_result.findings,
                *tool_result.findings,
                *memory_result.findings,
            ]
        )

        decision_timestamp = datetime.now(timezone.utc).isoformat()
        signature_payload = {
            "request_id": request_id,
            "tenant_id": tenant_id,
            "policy_version": policy.version,
            "action": action,
            "overall_risk_score": overall_risk,
            "decision_timestamp": decision_timestamp,
            "finding_count": len(aggregated_findings),
        }
        signature = self._sign_payload(signature_payload)

        response = SecurityDecisionEvaluateResponse(
            request_id=request_id,
            tenant_id=tenant_id,
            policy_version=policy.version,
            action=action,
            overall_risk_score=overall_risk,
            decision_timestamp=decision_timestamp,
            security_signature=signature,
            findings=aggregated_findings,
            prompt_injection=prompt_result,
            context_exfiltration=exfil_result,
            tool_permissions=tool_result,
            memory_audit=memory_result,
            enforcement_plan=SecurityDecisionEnforcementPlan(
                sanitized_untrusted_content=prompt_result.sanitized_content,
                redacted_output=exfil_result.redacted_output,
                granted_tools=tool_result.least_privilege_set,
                denied_tools=tool_result.denied,
                memory_actions=memory_result.flagged_items,
            ),
        )

        if self.db is not None:
            log_record = AgentSecurityDecisionLog(
                tenant_id=tenant_id,
                request_id=request_id,
                action=action,
                overall_risk_score=overall_risk,
                decision_payload=response.model_dump(mode="json"),
                signature=signature,
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(log_record)
            await self.db.flush()

        return response

    def analyze_prompt_injection(
        self,
        request: PromptInjectionAnalyzeRequest,
    ) -> PromptInjectionAnalyzeResponse:
        findings: list[SecurityFinding] = []
        attack_strings: list[str] = []
        risk_score = 0

        normalized_content = _normalize_untrusted_content(request.untrusted_content)

        for idx, (pattern, title, severity, score, recommendation) in enumerate(
            PROMPT_INJECTION_RULES,
            start=1,
        ):
            for match in re.finditer(pattern, normalized_content):
                evidence = _snippet(normalized_content, match.start(), match.end())
                findings.append(
                    SecurityFinding(
                        finding_id=f"pi-{idx}-{len(findings)+1}",
                        category="prompt_injection",
                        severity=severity,
                        title=title,
                        evidence=evidence,
                        recommendation=recommendation,
                    )
                )
                risk_score += score
                attack_strings.append(match.group(0)[:140])
                if len([f for f in findings if f.title == title]) >= 2:
                    break

        sanitized_lines: list[str] = []
        for line in normalized_content.splitlines():
            if any(re.search(rule[0], line) for rule in PROMPT_INJECTION_RULES):
                continue
            sanitized_lines.append(line)
        sanitized_content = "\n".join(sanitized_lines).strip() or "[content removed by injection shield]"

        if request.allowed_actions:
            lowered = normalized_content.lower()
            unseen_actions = [
                action for action in request.allowed_actions
                if action.strip() and action.lower() not in lowered
            ]
            if unseen_actions:
                risk_score += 4
                findings.append(
                    SecurityFinding(
                        finding_id=f"pi-allow-{len(findings)+1}",
                        category="prompt_injection",
                        severity="medium",
                        title="Action Allowlist Drift",
                        evidence=f"Observed content tried to introduce actions outside allowlist context: {', '.join(unseen_actions[:4])}",
                        recommendation="Run only allowlisted actions from the parent task.",
                    )
                )

        risk_score = _clamp_score(risk_score)
        blocked = risk_score >= request.block_threshold or any(
            finding.severity == "critical" for finding in findings
        )

        return PromptInjectionAnalyzeResponse(
            risk_score=risk_score,
            blocked=blocked,
            attack_strings_detected=attack_strings,
            findings=findings,
            sanitized_content=sanitized_content,
        )

    def analyze_context_exfiltration(
        self,
        request: ContextExfiltrationAnalyzeRequest,
    ) -> ContextExfiltrationAnalyzeResponse:
        findings: list[SecurityFinding] = []
        leak_hits: list[LeakHit] = []
        risk_score = 0

        blobs: list[tuple[str, str]] = [("candidate_output", request.candidate_output)]
        if request.reasoning_trace:
            blobs.append(("reasoning_trace", request.reasoning_trace))
        for payload in request.tool_payloads:
            blobs.append(("tool_payload", json.dumps(payload, sort_keys=True)))

        for leak_type, pattern, weight in EXFIL_PATTERNS:
            regex = re.compile(pattern)
            for location, text in blobs:
                for match in regex.finditer(text):
                    preview = _preview(match.group(0))
                    leak_hits.append(
                        LeakHit(
                            leak_type=leak_type,
                            location=location,
                            preview=preview,
                        )
                    )
                    risk_score += weight
                    if location != "candidate_output":
                        risk_score += 10

        if request.allowed_destinations:
            for match in re.finditer(
                r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b",
                request.candidate_output,
            ):
                domain = match.group(1).lower()
                if not any(domain.endswith(allowed.lower()) for allowed in request.allowed_destinations):
                    findings.append(
                        SecurityFinding(
                            finding_id=f"ce-domain-{len(findings)+1}",
                            category="context_exfiltration",
                            severity="high",
                            title="Unapproved Data Destination",
                            evidence=f"Detected destination domain outside allowlist: {domain}",
                            recommendation="Restrict outbound channels to approved domains only.",
                        )
                    )
                    risk_score += 20

        redacted_output = request.candidate_output
        for leak_type, pattern, _weight in EXFIL_PATTERNS:
            redacted_output = re.sub(
                pattern,
                f"[REDACTED:{leak_type.upper()}]",
                redacted_output,
            )

        if leak_hits:
            findings.append(
                SecurityFinding(
                    finding_id=f"ce-{len(findings)+1}",
                    category="context_exfiltration",
                    severity="critical" if risk_score >= 70 else "high",
                    title="Sensitive Context Exposure",
                    evidence=f"Detected {len(leak_hits)} sensitive artifacts across output/trace/tool payloads.",
                    recommendation="Redact secrets before output, disable trace logging for sensitive runs, and mask tool payloads.",
                )
            )

        return ContextExfiltrationAnalyzeResponse(
            risk_score=_clamp_score(risk_score),
            findings=findings,
            leak_hits=leak_hits,
            redacted_output=redacted_output,
        )

    def evaluate_tool_permissions(
        self,
        request: ToolPermissionEvaluateRequest,
    ) -> ToolPermissionEvaluateResponse:
        findings: list[SecurityFinding] = []
        granted: list[GrantedToolPermission] = []
        denied: list[DeniedToolPermission] = []
        risk_score = 0

        task_tokens = _tokenize(request.task_description)
        read_only = _is_read_only_task(request.task_description)

        requested = set(request.requested_tools)
        candidate_tools = [
            tool for tool in request.tools
            if not requested or tool.tool_name in requested
        ]

        ranked: list[tuple[int, str, object]] = []
        for tool in candidate_tools:
            haystack = " ".join(
                [tool.tool_name, tool.description, " ".join(tool.data_domains), " ".join(tool.scopes)]
            )
            relevance = _overlap_score(task_tokens, _tokenize(haystack))
            ranked.append((relevance, tool.tool_name, tool))

        ranked.sort(key=lambda row: row[0], reverse=True)

        for relevance, _tool_name, tool in ranked:
            wildcard_scope = any("*" in scope for scope in tool.scopes)
            if relevance == 0:
                denied.append(
                    DeniedToolPermission(
                        tool_name=tool.tool_name,
                        reason="Tool not relevant to current task context.",
                    )
                )
                risk_score += 10
                if wildcard_scope or tool.requires_approval:
                    risk_score += 12
                continue

            if len(granted) >= request.max_tools:
                denied.append(
                    DeniedToolPermission(
                        tool_name=tool.tool_name,
                        reason="Exceeded max_tools limit for least-privilege session.",
                    )
                )
                risk_score += 8
                continue

            narrowed_scopes = _narrow_scopes(tool.scopes, read_only=read_only)
            granted.append(
                GrantedToolPermission(
                    tool_name=tool.tool_name,
                    granted_scopes=narrowed_scopes,
                    reason="Relevant to task with reduced scope set.",
                )
            )

            if wildcard_scope:
                findings.append(
                    SecurityFinding(
                        finding_id=f"tp-{len(findings)+1}",
                        category="over_permissioned_tools",
                        severity="high",
                        title="Wildcard Scope Narrowed",
                        evidence=f"Tool '{tool.tool_name}' had wildcard scope and was reduced.",
                        recommendation="Persist narrow scopes as default policy for this task type.",
                    )
                )
                risk_score += 15

        if denied:
            findings.append(
                SecurityFinding(
                    finding_id=f"tp-{len(findings)+1}",
                    category="over_permissioned_tools",
                    severity="medium" if len(denied) < 3 else "high",
                    title="Irrelevant Tools Denied",
                    evidence=f"Denied {len(denied)} tool(s) outside least-privilege set.",
                    recommendation="Keep tool grants task-scoped and session-scoped.",
                )
            )

        if requested and not granted:
            findings.append(
                SecurityFinding(
                    finding_id=f"tp-{len(findings)+1}",
                    category="over_permissioned_tools",
                    severity="critical",
                    title="Requested Toolset Fully Rejected",
                    evidence="None of the requested tools matched task relevance rules.",
                    recommendation="Require human approval before overriding least-privilege gating.",
                )
            )
            risk_score += 25

        return ToolPermissionEvaluateResponse(
            risk_score=_clamp_score(risk_score),
            findings=findings,
            least_privilege_set=granted,
            denied=denied,
        )

    def audit_memory_session(
        self,
        request: MemorySessionAuditRequest,
    ) -> MemorySessionAuditResponse:
        findings: list[SecurityFinding] = []
        flagged_items: list[MemoryLeakItem] = []
        risk_score = 0

        total_events = len(request.session_events)
        for index, event in enumerate(request.session_events):
            age_from_latest = total_events - index
            for leak_type, pattern, weight in EXFIL_PATTERNS:
                match = re.search(pattern, event.content)
                if match is None:
                    continue

                preview = _preview(match.group(0))
                if age_from_latest > request.max_retention_turns:
                    action = "scrub"
                    reason = "Sensitive item exceeds retention window."
                    risk_score += weight + 8
                elif event.persisted:
                    action = "summarize"
                    reason = "Sensitive item still persisted in active memory."
                    risk_score += weight
                else:
                    action = "keep"
                    reason = "Sensitive marker detected but event not persisted."
                    risk_score += max(weight - 8, 0)

                flagged_items.append(
                    MemoryLeakItem(
                        turn_id=event.turn_id,
                        leak_type=leak_type,
                        preview=preview,
                        action=action,
                        reason=reason,
                    )
                )

        if flagged_items:
            findings.append(
                SecurityFinding(
                    finding_id="mem-1",
                    category="memory_session_persistence",
                    severity="high" if risk_score >= 50 else "medium",
                    title="Sensitive Session Memory Residue",
                    evidence=f"Detected {len(flagged_items)} sensitive memory item(s) across session history.",
                    recommendation="Apply automatic memory scrubbing and short TTL for credential/PII classes.",
                )
            )

        recommended_ttl = max(3, min(request.max_retention_turns, 15))

        return MemorySessionAuditResponse(
            risk_score=_clamp_score(risk_score),
            findings=findings,
            flagged_items=flagged_items,
            recommended_ttl_turns=recommended_ttl,
        )

    async def _get_policy_record(self, tenant_id: str) -> AgentSecurityPolicy | None:
        if self.db is None:
            return None
        result = await self.db.execute(
            select(AgentSecurityPolicy).where(AgentSecurityPolicy.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def _get_decision_log(
        self,
        *,
        tenant_id: str,
        request_id: str,
    ) -> AgentSecurityDecisionLog | None:
        if self.db is None:
            return None
        result = await self.db.execute(
            select(AgentSecurityDecisionLog).where(
                AgentSecurityDecisionLog.tenant_id == tenant_id,
                AgentSecurityDecisionLog.request_id == request_id,
            )
        )
        return result.scalar_one_or_none()

    def _resolve_action(
        self,
        *,
        policy_mode: str,
        policy: AgentSecurityPolicyConfig,
        prompt_result: PromptInjectionAnalyzeResponse,
        exfil_result: ContextExfiltrationAnalyzeResponse,
        tool_result: ToolPermissionEvaluateResponse,
        memory_result: MemorySessionAuditResponse,
    ) -> DecisionAction:
        hard_block = False

        if prompt_result.blocked:
            hard_block = True

        if exfil_result.risk_score >= policy.context_exfil_block_threshold:
            hard_block = True

        if policy.strict_tool_allowlist and tool_result.denied and not tool_result.least_privilege_set:
            hard_block = True

        if policy.block_on_sensitive_memory_residue and any(
            item.action == "scrub" for item in memory_result.flagged_items
        ):
            hard_block = True

        if hard_block:
            return "review" if policy_mode == "monitor" else "block"

        review_score = max(
            exfil_result.risk_score,
            prompt_result.risk_score,
            tool_result.risk_score,
            memory_result.risk_score,
        )
        if review_score >= policy.context_exfil_review_threshold:
            return "review"

        return "allow"

    def _sign_payload(self, payload: dict[str, object]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hmac.new(self._hmac_key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _clamp_score(score: int) -> int:
    return max(0, min(100, score))


def _snippet(text: str, start: int, end: int, radius: int = 60) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return text[left:right].replace("\n", " ").strip()


def _preview(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-2:]}"


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def _overlap_score(task_tokens: set[str], tool_tokens: set[str]) -> int:
    if not task_tokens or not tool_tokens:
        return 0
    return len(task_tokens.intersection(tool_tokens))


def _is_read_only_task(task_description: str) -> bool:
    tokens = _tokenize(task_description)
    if tokens.intersection(WRITE_VERBS):
        return False
    return bool(tokens.intersection(READ_ONLY_VERBS))


def _narrow_scopes(scopes: list[str], *, read_only: bool) -> list[str]:
    if not scopes:
        return []

    cleaned = [scope.strip() for scope in scopes if scope.strip()]
    if not cleaned:
        return []

    if read_only:
        read_scopes = [
            scope for scope in cleaned
            if scope.startswith(("read", "list", "get"))
        ]
        if read_scopes:
            return read_scopes[:3]

    non_wildcards = [scope for scope in cleaned if "*" not in scope]
    if non_wildcards:
        return non_wildcards[:3]

    return cleaned[:1]


def _normalize_untrusted_content(content: str) -> str:
    normalized = content
    normalized = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", normalized)
    normalized = re.sub(r"<!--.*?-->", " ", normalized, flags=re.S)
    normalized = re.sub(r"<style.*?>.*?</style>", " ", normalized, flags=re.S | re.I)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _sort_findings(findings: Iterable[SecurityFinding]) -> list[SecurityFinding]:
    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    return sorted(
        findings,
        key=lambda finding: severity_rank.get(finding.severity, 0),
        reverse=True,
    )
