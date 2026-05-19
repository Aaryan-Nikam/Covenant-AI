"""
Ironpass — Dashboard backend service.

Business logic for the dashboard API:
- tenant-scoped overview and audit surfaces
- product map separating core compliance layer vs operations functions
- live operations-function module metrics
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from engine.audit.models import AuditLog
from engine.auth.models import Tenant
from engine.compliance.service import ComplianceOpsService
from engine.rulesets.loader import RulesetLoader
from engine.vault.models import VaultToken

logger = logging.getLogger("ironpass.dashboard.service")


class DashboardService:
    """Business logic for the dashboard."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def get_overview(self, tenant: Tenant) -> dict:
        """
        Tenant-scoped dashboard overview stats:
        - Total requests processed
        - Total blocked
        - Requests in last 24h
        - Active tokens in vault
        - Avg latency and block rate
        """
        now = datetime.now(timezone.utc)
        last_24h = now - timedelta(hours=24)

        total_result = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.agent_id == tenant.agent_id
            )
        )
        total_requests = total_result.scalar() or 0

        blocked_result = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.agent_id == tenant.agent_id,
                AuditLog.was_blocked.is_(True),
            )
        )
        total_blocked = blocked_result.scalar() or 0

        recent_result = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.agent_id == tenant.agent_id,
                AuditLog.timestamp >= last_24h,
            )
        )
        requests_24h = recent_result.scalar() or 0

        active_tokens_result = await self.db.execute(
            select(func.count(VaultToken.token)).where(
                VaultToken.tenant_id == tenant.id,
                VaultToken.expires_at > now,
                VaultToken.invalidated_at.is_(None),
            )
        )
        active_tokens = active_tokens_result.scalar() or 0

        avg_latency_result = await self.db.execute(
            select(func.avg(AuditLog.latency_ms)).where(
                AuditLog.agent_id == tenant.agent_id
            )
        )
        avg_latency = avg_latency_result.scalar() or 0

        return {
            "tenant_id": tenant.id,
            "total_requests": total_requests,
            "total_blocked": total_blocked,
            "requests_24h": requests_24h,
            "active_vault_tokens": active_tokens,
            "avg_latency_ms": round(float(avg_latency), 1),
            "block_rate": round(
                (total_blocked / total_requests * 100) if total_requests > 0 else 0,
                1,
            ),
            "active_rulesets_count": len(tenant.active_rulesets or []),
        }

    async def get_violations(
        self,
        tenant: Tenant,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Get tenant-scoped recent blocked request entries."""
        result = await self.db.execute(
            select(AuditLog)
            .where(
                AuditLog.agent_id == tenant.agent_id,
                AuditLog.was_blocked.is_(True),
            )
            .order_by(desc(AuditLog.timestamp))
            .limit(limit)
            .offset(offset)
        )
        entries = result.scalars().all()

        count_result = await self.db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.agent_id == tenant.agent_id,
                AuditLog.was_blocked.is_(True),
            )
        )
        total = count_result.scalar() or 0

        return {
            "violations": [
                {
                    "entry_id": str(e.entry_id),
                    "timestamp": e.timestamp.isoformat(),
                    "agent_id": e.agent_id,
                    "rulesets_used": e.rulesets_used,
                    "detections": e.detections,
                    "actions_taken": e.actions_taken,
                    "outcome": e.outcome,
                }
                for e in entries
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_audit_log(
        self,
        tenant: Tenant,
        limit: int = 50,
        offset: int = 0,
        agent_id: str | None = None,
        outcome: str | None = None,
        ruleset: str | None = None,
    ) -> dict:
        """Get tenant-scoped audit log entries with optional filters."""
        if agent_id and agent_id != tenant.agent_id:
            return {
                "entries": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
            }

        query = (
            select(AuditLog)
            .where(AuditLog.agent_id == tenant.agent_id)
            .order_by(desc(AuditLog.timestamp))
        )
        count_query = select(func.count(AuditLog.id)).where(
            AuditLog.agent_id == tenant.agent_id
        )

        if outcome:
            query = query.where(AuditLog.outcome == outcome)
            count_query = count_query.where(AuditLog.outcome == outcome)

        if ruleset:
            query = query.where(AuditLog.rulesets_used.contains([ruleset]))
            count_query = count_query.where(AuditLog.rulesets_used.contains([ruleset]))

        result = await self.db.execute(query.limit(limit).offset(offset))
        entries = result.scalars().all()

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        return {
            "entries": [
                {
                    "entry_id": str(e.entry_id),
                    "timestamp": e.timestamp.isoformat(),
                    "agent_id": e.agent_id,
                    "rulesets_used": e.rulesets_used,
                    "detections_count": len(e.detections) if e.detections else 0,
                    "actions_count": len(e.actions_taken) if e.actions_taken else 0,
                    "was_blocked": e.was_blocked,
                    "outcome": e.outcome,
                    "latency_ms": e.latency_ms,
                }
                for e in entries
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def verify_audit_integrity(self, tenant: Tenant, limit: int = 100) -> dict:
        """
        Verify tenant-scoped audit chain integrity.
        """
        from engine.audit.signer import AuditSigner

        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.agent_id == tenant.agent_id)
            .order_by(AuditLog.timestamp.asc())
            .limit(limit)
        )
        entries = result.scalars().all()

        if not entries:
            return {
                "chain_status": "EMPTY",
                "tamper_detected": False,
                "entries_verified": 0,
                "time_range": None,
                "summary": "No audit entries to verify. Chain is empty.",
                "details": {},
            }

        signer = AuditSigner()
        chain_data = [
            {
                "entry_id": str(e.entry_id),
                "timestamp": e.timestamp.isoformat(),
                "agent_id": e.agent_id,
                "request_hash": e.request_hash,
                "rulesets_used": e.rulesets_used,
                "detections": e.detections or [],
                "actions_taken": e.actions_taken or [],
                "was_blocked": e.was_blocked,
                "target_url": e.target_url,
                "latency_ms": e.latency_ms,
                "outcome": e.outcome,
                "hmac_signature": e.hmac_signature,
                "prev_entry_hash": e.prev_entry_hash,
            }
            for e in entries
        ]
        is_valid, error = signer.verify_chain(chain_data)

        first_ts = entries[0].timestamp
        last_ts = entries[-1].timestamp
        unique_agents = list(set(e.agent_id for e in entries))
        outcomes: dict[str, int] = {}
        total_detections = 0
        for e in entries:
            outcomes[e.outcome] = outcomes.get(e.outcome, 0) + 1
            if e.detections:
                total_detections += len(e.detections)

        time_range_seconds = (last_ts - first_ts).total_seconds()

        if is_valid:
            summary = (
                f"Chain INTACT — {len(entries)} entries verified, "
                f"covering {_format_duration(time_range_seconds)}."
            )
        else:
            summary = (
                f"Chain BROKEN — {error}. "
                f"Checked {len(entries)} entries over {_format_duration(time_range_seconds)}."
            )

        return {
            "chain_status": "INTACT" if is_valid else "BROKEN",
            "tamper_detected": not is_valid,
            "tamper_error": error if not is_valid else None,
            "entries_verified": len(entries),
            "time_range": {
                "first_entry": first_ts.isoformat(),
                "last_entry": last_ts.isoformat(),
                "duration_seconds": int(time_range_seconds),
                "duration_human": _format_duration(time_range_seconds),
            },
            "agents": unique_agents,
            "outcomes": outcomes,
            "total_detections": total_detections,
            "summary": summary,
        }

    async def get_product_map(self, tenant: Tenant) -> dict[str, Any]:
        """
        Returns product structure in two clear surfaces:
        - core compliance layer (infrastructure layer)
        - operations function suite (business workflows)
        """
        try:
            overview = await self.get_overview(tenant)
        except Exception as exc:
            logger.warning("Overview unavailable in product_map fallback: %s", exc)
            overview = {
                "tenant_id": tenant.id,
                "total_requests": 0,
                "total_blocked": 0,
                "requests_24h": 0,
                "active_vault_tokens": 0,
                "avg_latency_ms": 0.0,
                "block_rate": 0.0,
                "active_rulesets_count": len(tenant.active_rulesets or []),
            }
        total_rulesets, all_rulesets = self._load_ruleset_inventory()

        functions_catalog = self._get_functions_catalog()
        implemented = [f for f in functions_catalog if f["status"] == "implemented"]
        planned = [f for f in functions_catalog if f["status"] == "planned"]

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "core_compliance_layer": {
                "name": "Core Compliance Layer",
                "description": (
                    "Traffic interception, policy enforcement, secure tokenization, "
                    "audit evidence, and governance controls."
                ),
                "kpis": overview,
                "rulesets": {
                    "active_count": len(tenant.active_rulesets or []),
                    "active_rulesets": tenant.active_rulesets or [],
                    "available_count": total_rulesets,
                    "available_rulesets": all_rulesets,
                },
                "features": [
                    {
                        "id": "proxy_interception",
                        "name": "Provider Proxy Interception",
                        "status": "live",
                        "routes": [
                            "/openai/v1/chat/completions",
                            "/anthropic/v1/messages",
                            "/google/v1/models/{model}:generateContent",
                            "/proxy/scan",
                        ],
                    },
                    {
                        "id": "policy_enforcement",
                        "name": "Ruleset Detection + Actions",
                        "status": "live",
                        "routes": [
                            "/proxy/rulesets",
                            "/proxy/rulesets/{ruleset_id}",
                        ],
                    },
                    {
                        "id": "immutable_audit",
                        "name": "Immutable Audit + Chain Verification",
                        "status": "live",
                        "routes": [
                            "/dashboard/audit",
                            "/dashboard/audit/verify",
                            "/v1/logs",
                        ],
                    },
                    {
                        "id": "vault_security",
                        "name": "Token Vault and De-tokenization",
                        "status": "live",
                        "routes": [
                            "/dashboard/overview",
                        ],
                    },
                    {
                        "id": "tenant_governance",
                        "name": "Tenant Governance + Access Control",
                        "status": "live",
                        "routes": [
                            "/v1/admin/tenants",
                            "/v1/admin/tenants/{tenant_id}",
                        ],
                    },
                ],
            },
            "operations_function_suite": {
                "name": "Operations Functions",
                "description": (
                    "High-ticket business workflows built on top of the compliance layer."
                ),
                "implemented_count": len(implemented),
                "planned_count": len(planned),
                "functions": functions_catalog,
            },
            "management_capabilities": self._get_management_capabilities(),
        }

    async def get_functions_overview(self, tenant: Tenant) -> dict[str, Any]:
        """
        Live module overview for implemented operations functions.
        """
        compliance = ComplianceOpsService(self.db)
        modules: list[dict[str, Any]] = []

        aml_metrics = await self._safe_async_call(
            "aml_sar_dashboard",
            compliance.aml_dashboard(tenant.id),
        )
        modules.append(
            {
                "id": "aml_sar",
                "name": "Audit trails / AML & SAR Workflow",
                "status": "implemented",
                "health": aml_metrics["health"],
                "metrics": aml_metrics["metrics"],
                "routes": [
                    "/v1/compliance/aml/signals",
                    "/v1/compliance/aml/cases",
                    "/v1/compliance/aml/cases/{case_id}/sar-draft",
                    "/v1/compliance/aml/cases/{case_id}/submit",
                    "/v1/compliance/aml/dashboard",
                ],
                "errors": aml_metrics["errors"],
            }
        )

        covenant_metrics = await self._safe_async_call(
            "covenant_dashboard",
            compliance.covenant_dashboard(tenant.id),
        )
        modules.append(
            {
                "id": "financial_covenants",
                "name": "Financial Covenant & Debt Obligation Monitoring",
                "status": "implemented",
                "health": covenant_metrics["health"],
                "metrics": covenant_metrics["metrics"],
                "routes": [
                    "/v1/compliance/covenants",
                    "/v1/compliance/covenants/evaluate",
                    "/v1/compliance/covenants/dashboard",
                ],
                "errors": covenant_metrics["errors"],
            }
        )

        sla_metrics = await self._safe_async_call(
            "sla_dashboard",
            compliance.sla_dashboard(tenant.id),
        )
        modules.append(
            {
                "id": "sla_credit_leakage",
                "name": "SLA Breach + Credit Leakage Monitoring",
                "status": "implemented",
                "health": sla_metrics["health"],
                "metrics": sla_metrics["metrics"],
                "routes": [
                    "/v1/compliance/sla/contracts",
                    "/v1/compliance/sla/evaluate",
                    "/v1/compliance/sla/dashboard",
                ],
                "errors": sla_metrics["errors"],
            }
        )

        gdpr_retention_metrics = await self._safe_async_call(
            "gdpr_retention_dashboard",
            compliance.gdpr_retention_dashboard(tenant.id),
        )
        ropa_metrics = await self._safe_async_call(
            "gdpr_ropa_dashboard",
            compliance.ropa_dashboard(tenant.id),
        )
        modules.append(
            {
                "id": "gdpr_retention_ropa",
                "name": "GDPR Data Retention & ROPA Monitoring",
                "status": "implemented",
                "health": (
                    "live"
                    if gdpr_retention_metrics["health"] == "live"
                    and ropa_metrics["health"] == "live"
                    else "degraded"
                ),
                "metrics": {
                    "retention": gdpr_retention_metrics["metrics"],
                    "ropa": ropa_metrics["metrics"],
                },
                "routes": [
                    "/v1/compliance/gdpr/retention-policies",
                    "/v1/compliance/gdpr/retention/evaluate",
                    "/v1/compliance/gdpr/retention/dashboard",
                    "/v1/compliance/gdpr/ropa/activities",
                    "/v1/compliance/gdpr/ropa/monitor",
                    "/v1/compliance/gdpr/ropa/dashboard",
                ],
                "errors": [
                    *gdpr_retention_metrics["errors"],
                    *ropa_metrics["errors"],
                ],
            }
        )

        rd_tax_metrics = await self._safe_async_call(
            "rd_tax_dashboard",
            compliance.rd_tax_dashboard(tenant.id),
        )
        modules.append(
            {
                "id": "rd_tax_credit_tracking",
                "name": "R&D Tax Credit Activity Tracking",
                "status": "implemented",
                "health": rd_tax_metrics["health"],
                "metrics": rd_tax_metrics["metrics"],
                "routes": [
                    "/v1/compliance/rd-tax/activities",
                    "/v1/compliance/rd-tax/evaluate",
                    "/v1/compliance/rd-tax/dashboard",
                ],
                "errors": rd_tax_metrics["errors"],
            }
        )

        esg_metrics = await self._safe_async_call(
            "esg_csrd_dashboard",
            compliance.esg_csrd_dashboard(tenant.id),
        )
        modules.append(
            {
                "id": "esg_csrd",
                "name": "ESG Data Collection & CSRD Compliance",
                "status": "implemented",
                "health": esg_metrics["health"],
                "metrics": esg_metrics["metrics"],
                "routes": [
                    "/v1/compliance/esg/metrics",
                    "/v1/compliance/esg/csrd/evaluate",
                    "/v1/compliance/esg/csrd/dashboard",
                ],
                "errors": esg_metrics["errors"],
            }
        )

        supplier_metrics = await self._safe_async_call(
            "supplier_risk_dashboard",
            compliance.supplier_risk_dashboard(tenant.id),
        )
        modules.append(
            {
                "id": "supplier_insolvency_monitoring",
                "name": "Supplier Financial Health & Insolvency Monitoring",
                "status": "implemented",
                "health": supplier_metrics["health"],
                "metrics": supplier_metrics["metrics"],
                "routes": [
                    "/v1/compliance/supplier/profiles",
                    "/v1/compliance/supplier/financial-health/evaluate",
                    "/v1/compliance/supplier/financial-health/dashboard",
                ],
                "errors": supplier_metrics["errors"],
            }
        )

        hs_metrics = await self._safe_async_call(
            "hs_riddor_dashboard",
            compliance.hs_riddor_dashboard(tenant.id),
        )
        modules.append(
            {
                "id": "hs_riddor_monitoring",
                "name": "H&S Near-Miss & RIDDOR Compliance Monitoring",
                "status": "implemented",
                "health": hs_metrics["health"],
                "metrics": hs_metrics["metrics"],
                "routes": [
                    "/v1/compliance/hs/incidents",
                    "/v1/compliance/hs/riddor/monitor",
                    "/v1/compliance/hs/riddor/dashboard",
                ],
                "errors": hs_metrics["errors"],
            }
        )

        competitor_metrics = await self._safe_async_call(
            "competitor_signals_dashboard",
            compliance.competitor_signals_dashboard(tenant.id),
        )
        modules.append(
            {
                "id": "competitor_signal_monitoring",
                "name": "Competitor Intelligence & Strategic Signal Monitoring",
                "status": "implemented",
                "health": competitor_metrics["health"],
                "metrics": competitor_metrics["metrics"],
                "routes": [
                    "/v1/compliance/competitor/profiles",
                    "/v1/compliance/competitor/signals/evaluate",
                    "/v1/compliance/competitor/signals/dashboard",
                ],
                "errors": competitor_metrics["errors"],
            }
        )

        planned = [f for f in self._get_functions_catalog() if f["status"] == "planned"]
        live_count = len([m for m in modules if m["health"] == "live"])

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "implemented_modules": modules,
            "implemented_count": len(modules),
            "live_count": live_count,
            "planned_count": len(planned),
            "planned_modules": planned,
        }

    async def _safe_async_call(self, label: str, coroutine) -> dict[str, Any]:
        try:
            result = await coroutine
            return {"health": "live", "metrics": result, "errors": []}
        except Exception as exc:
            logger.exception("Dashboard call failed for %s", label)
            return {
                "health": "error",
                "metrics": {},
                "errors": [str(exc)],
            }

    def _load_ruleset_inventory(self) -> tuple[int, list[str]]:
        try:
            rulesets = RulesetLoader().load_all()
            ids = sorted(rulesets.keys())
            return len(ids), ids
        except Exception as exc:
            logger.warning("Ruleset inventory load failed: %s", exc)
            return 0, []

    def _get_functions_catalog(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "aml_sar",
                "name": "Audit trails / AML & SAR Workflow",
                "status": "implemented",
                "priority": "critical",
                "revenue_impact": "high",
            },
            {
                "id": "sla_credit_leakage",
                "name": "SLA Problems + Credit Leakage",
                "status": "implemented",
                "priority": "critical",
                "revenue_impact": "high",
            },
            {
                "id": "financial_covenants",
                "name": "Financial Covenant & Debt Obligation Monitoring",
                "status": "implemented",
                "priority": "critical",
                "revenue_impact": "high",
            },
            {
                "id": "gdpr_retention_ropa",
                "name": "GDPR Data Retention & ROPA Monitoring",
                "status": "implemented",
                "priority": "critical",
                "revenue_impact": "high",
            },
            {
                "id": "rd_tax_credit_tracking",
                "name": "R&D Tax Credit Activity Tracking",
                "status": "implemented",
                "priority": "high",
                "revenue_impact": "high",
            },
            {
                "id": "esg_csrd",
                "name": "ESG Data Collection & CSRD Compliance",
                "status": "implemented",
                "priority": "medium",
                "revenue_impact": "medium",
            },
            {
                "id": "supplier_insolvency_monitoring",
                "name": "Supplier Financial Health & Insolvency Monitoring",
                "status": "implemented",
                "priority": "high",
                "revenue_impact": "high",
            },
            {
                "id": "hs_riddor_monitoring",
                "name": "H&S Near-Miss & RIDDOR Compliance Monitoring",
                "status": "implemented",
                "priority": "medium",
                "revenue_impact": "medium",
            },
            {
                "id": "competitor_signal_monitoring",
                "name": "Competitor Intelligence & Strategic Signal Monitoring",
                "status": "implemented",
                "priority": "medium",
                "revenue_impact": "medium",
            },
        ]

    def _get_management_capabilities(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "control_plane",
                "name": "Unified Control Plane",
                "description": "Tenant-aware feature flags, module status, and global policy governance.",
                "must_have_features": [
                    "module enable/disable",
                    "tenant scoping",
                    "environment separation",
                    "versioned configuration",
                ],
            },
            {
                "id": "case_workflow",
                "name": "Case & Escalation Workflow",
                "description": "Cross-function investigations with ownership, SLA timers, and immutable timeline events.",
                "must_have_features": [
                    "status transitions",
                    "assignment",
                    "escalation ladders",
                    "audit events",
                ],
            },
            {
                "id": "evidence_reporting",
                "name": "Evidence & Reporting",
                "description": "Regulator-ready evidence exports and executive reporting for renewal/upsell motion.",
                "must_have_features": [
                    "tamper-evident logs",
                    "dashboard snapshots",
                    "CSV/PDF exports",
                    "periodic reporting",
                ],
            },
            {
                "id": "integration_automation",
                "name": "Integrations & Automation",
                "description": "Operational sync with ERP/CRM/ticketing/finance systems to avoid manual workflows.",
                "must_have_features": [
                    "webhooks",
                    "scheduled jobs",
                    "bi-directional sync",
                    "retry + dead-letter handling",
                ],
            },
            {
                "id": "commercial_controls",
                "name": "Commercial & Risk Controls",
                "description": "Revenue exposure tracking and value realization by function and tenant.",
                "must_have_features": [
                    "credit leakage estimation",
                    "financial risk scoring",
                    "module ROI analytics",
                    "account-level value summaries",
                ],
            },
        ]


def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    if seconds < 86400:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    return f"{days}d {hours}h"
