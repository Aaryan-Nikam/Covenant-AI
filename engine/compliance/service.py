"""
Ironpass — Compliance operations service layer.

First module implemented: AML/SAR workflow with reusable obligations support.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from engine.compliance.models import (
    AMLSignal,
    ComplianceCase,
    ComplianceCaseEvent,
    ComplianceObligation,
    CompetitorProfile,
    CompetitorSignalAssessment,
    CovenantEvaluation,
    ESGCSRDSubmission,
    ESGMetric,
    FinancialCovenant,
    FinancialSnapshot,
    GDPRProcessingActivity,
    GDPRRetentionFinding,
    GDPRRetentionPolicy,
    GDPRRetentionSnapshot,
    HSIncident,
    HSRiddorAssessment,
    RDTaxActivity,
    RDTaxAssessment,
    SLAContract,
    SLAEvaluation,
    SLASnapshot,
    SARReport,
    SupplierProfile,
    SupplierRiskAssessment,
)
from engine.compliance.schemas import (
    AMLDashboardResponse,
    AMLSignalIngestRequest,
    AMLSignalIngestResponse,
    CompetitorProfileResponse,
    CompetitorProfilesResponse,
    CompetitorSignalAssessmentSummary,
    CompetitorSignalsDashboardResponse,
    CompetitorSignalObservation,
    CreateCompetitorProfileRequest,
    CreateESGMetricRequest,
    CreateHSIncidentRequest,
    CreateRDTaxActivityRequest,
    CreateSupplierProfileRequest,
    ComplianceCasesResponse,
    ComplianceCaseSummary,
    CovenantDashboardResponse,
    CovenantEvaluationSummary,
    CovenantResponse,
    CovenantsResponse,
    ESGCSRDDashboardResponse,
    ESGCSRDFindingSummary,
    ESGDisclosureObservation,
    ESGMetricResponse,
    ESGMetricsResponse,
    CreateGDPRRetentionPolicyRequest,
    CreateObligationRequest,
    CreateROPAActivityRequest,
    CreateSLAContractRequest,
    CreateCovenantRequest,
    EvaluateCompetitorSignalsRequest,
    EvaluateCompetitorSignalsResponse,
    EvaluateESGCSRDRequest,
    EvaluateESGCSRDResponse,
    EvaluateGDPRRetentionRequest,
    EvaluateGDPRRetentionResponse,
    EvaluateRDTaxRequest,
    EvaluateRDTaxResponse,
    EvaluateSLARequest,
    EvaluateSLAResponse,
    EvaluateSupplierRiskRequest,
    EvaluateSupplierRiskResponse,
    EvaluateCovenantsRequest,
    EvaluateCovenantsResponse,
    GDPRRetentionDashboardResponse,
    GDPRRetentionFindingSummary,
    GDPRRetentionPoliciesResponse,
    GDPRRetentionPolicyResponse,
    HSIncidentResponse,
    HSIncidentsResponse,
    HSRiddorAssessmentSummary,
    HSRiddorDashboardResponse,
    MonitorROPARequest,
    MonitorROPAResponse,
    MonitorHSRiddorRequest,
    MonitorHSRiddorResponse,
    ObligationResponse,
    ObligationsResponse,
    RDTaxActivitiesResponse,
    RDTaxActivityResponse,
    RDTaxAssessmentSummary,
    RDTaxDashboardResponse,
    ROPAActivitiesResponse,
    ROPAActivityResponse,
    ROPADashboardResponse,
    ROPAMonitoringItem,
    SLAContractResponse,
    SLAContractsResponse,
    SLADashboardResponse,
    SLAEvaluationSummary,
    SLAObservation,
    SARReportResponse,
    SARDraftRequest,
    SupplierProfileResponse,
    SupplierProfilesResponse,
    SupplierRiskAssessmentSummary,
    SupplierRiskDashboardResponse,
    SupplierRiskObservation,
)

logger = logging.getLogger("ironpass.compliance.service")

_HIGH_RISK_COUNTRIES = {"IR", "KP", "SY", "RU", "BY", "MM"}
_VALID_COVENANT_COMPARATORS = {"<=", ">=", "<", ">", "="}
_VALID_SLA_COMPARATORS = {"<=", ">=", "<", ">", "="}


@dataclass
class RiskScoreResult:
    score: int
    flags: list[str]


@dataclass
class CovenantStatusResult:
    status: str
    distance_pct: Decimal | None


@dataclass
class GDPRRetentionStatusResult:
    status: str
    reason: str
    excess_days: int | None


@dataclass
class ROPAActivityStatusResult:
    status: str
    reasons: list[str]
    days_until_review_due: int | None


@dataclass
class RDTaxProjectAssessmentResult:
    status: str
    qualifying_ratio_pct: Decimal
    estimated_credit_amount: Decimal
    missing_evidence_count: int
    reasons: list[str]


@dataclass
class ESGMetricStatusResult:
    status: str
    reason: str


@dataclass
class SupplierRiskStatusResult:
    status: str
    risk_score: int
    reasons: list[str]


@dataclass
class HSRiddorStatusResult:
    reportable: bool
    status: str
    deadline_at: datetime | None
    days_until_deadline: int | None
    reasons: list[str]


@dataclass
class CompetitorSignalStatusResult:
    status: str
    priority_score: int
    reasons: list[str]


def score_aml_signal(signal: AMLSignalIngestRequest) -> RiskScoreResult:
    """Deterministic AML risk score for escalation decisions."""
    score = 0
    flags: list[str] = []

    amount = Decimal(str(signal.amount)) if signal.amount is not None else Decimal("0")
    if amount >= Decimal("10000"):
        score += 35
        flags.append("high_value_transaction")
    elif amount >= Decimal("5000"):
        score += 20
        flags.append("elevated_transaction_value")

    if signal.channel and signal.channel.lower() == "cash":
        score += 20
        flags.append("cash_channel")

    country_from = (signal.country_from or "").upper()
    country_to = (signal.country_to or "").upper()
    if country_from in _HIGH_RISK_COUNTRIES or country_to in _HIGH_RISK_COUNTRIES:
        score += 30
        flags.append("high_risk_jurisdiction")

    if signal.pep_hit:
        score += 30
        flags.append("pep_match")

    if signal.sanction_hit:
        score += 60
        flags.append("sanctions_match")

    if signal.unusual_pattern:
        score += 20
        flags.append("unusual_pattern")

    if signal.new_customer and amount >= Decimal("5000"):
        score += 15
        flags.append("new_customer_large_transaction")

    return RiskScoreResult(score=min(score, 100), flags=flags)


def evaluate_covenant_value(
    metric_value: Decimal,
    comparator: str,
    threshold: Decimal,
    warning_buffer_pct: Decimal,
) -> CovenantStatusResult:
    """
    Evaluate covenant status as compliant, at_risk, or breached.

    `at_risk` means within warning_buffer_pct of threshold while still compliant.
    """
    if comparator not in _VALID_COVENANT_COMPARATORS:
        raise ValueError(f"Unsupported comparator: {comparator}")

    breached = False
    if comparator == "<=":
        breached = metric_value > threshold
    elif comparator == "<":
        breached = metric_value >= threshold
    elif comparator == ">=":
        breached = metric_value < threshold
    elif comparator == ">":
        breached = metric_value <= threshold
    elif comparator == "=":
        breached = metric_value != threshold

    if breached:
        if threshold == 0:
            return CovenantStatusResult(status="breached", distance_pct=None)
        distance_pct = (abs(metric_value - threshold) / abs(threshold)) * Decimal("100")
        return CovenantStatusResult(status="breached", distance_pct=distance_pct)

    # "=" style covenants are binary and don't need warning bands.
    if comparator == "=":
        return CovenantStatusResult(status="compliant", distance_pct=Decimal("0"))

    if threshold == 0:
        return CovenantStatusResult(status="compliant", distance_pct=None)

    distance_pct = (abs(metric_value - threshold) / abs(threshold)) * Decimal("100")
    if distance_pct <= warning_buffer_pct:
        return CovenantStatusResult(status="at_risk", distance_pct=distance_pct)
    return CovenantStatusResult(status="compliant", distance_pct=distance_pct)


def evaluate_gdpr_retention_observation(
    oldest_record_age_days: int,
    retention_days: int | None,
    warning_buffer_days: int,
) -> GDPRRetentionStatusResult:
    """Classify retention posture for one data observation."""
    if retention_days is None:
        return GDPRRetentionStatusResult(
            status="no_policy",
            reason="No retention policy configured for this data category/system",
            excess_days=None,
        )

    if oldest_record_age_days > retention_days:
        excess_days = oldest_record_age_days - retention_days
        return GDPRRetentionStatusResult(
            status="breach",
            reason=f"Oldest record age exceeds retention limit by {excess_days} days",
            excess_days=excess_days,
        )

    if warning_buffer_days > 0 and oldest_record_age_days >= max(retention_days - warning_buffer_days, 0):
        return GDPRRetentionStatusResult(
            status="warning",
            reason="Oldest record age is approaching retention limit",
            excess_days=0,
        )

    return GDPRRetentionStatusResult(
        status="compliant",
        reason="Retention posture is within policy bounds",
        excess_days=0,
    )


def assess_ropa_activity(
    *,
    purpose: str | None,
    lawful_basis: str | None,
    data_categories: list[str],
    next_review_due_at: datetime | None,
    due_soon_days: int,
    now: datetime,
) -> ROPAActivityStatusResult:
    """Evaluate ROPA activity health for monitoring workflows."""
    reasons: list[str] = []
    days_until_review_due: int | None = None

    if not (lawful_basis or "").strip():
        reasons.append("missing_lawful_basis")
    if not (purpose or "").strip():
        reasons.append("missing_purpose")
    if len(data_categories) == 0:
        reasons.append("missing_data_categories")

    if next_review_due_at is not None:
        delta_days = (next_review_due_at - now).days
        days_until_review_due = delta_days
        if delta_days < 0:
            reasons.append("review_overdue")
        elif delta_days <= due_soon_days:
            reasons.append("review_due_soon")

    critical_reasons = {
        "missing_lawful_basis",
        "missing_purpose",
        "missing_data_categories",
        "review_overdue",
    }
    if any(reason in critical_reasons for reason in reasons):
        status = "critical"
    elif "review_due_soon" in reasons:
        status = "warning"
    else:
        status = "compliant"

    return ROPAActivityStatusResult(
        status=status,
        reasons=reasons or ["healthy"],
        days_until_review_due=days_until_review_due,
    )


def evaluate_sla_value(
    observed_value: Decimal,
    comparator: str,
    target_value: Decimal,
    warning_buffer_pct: Decimal,
) -> CovenantStatusResult:
    """
    Evaluate SLA metric status.

    Uses the same threshold semantics as covenant checks.
    """
    if comparator not in _VALID_SLA_COMPARATORS:
        raise ValueError(f"Unsupported comparator: {comparator}")
    return evaluate_covenant_value(
        metric_value=observed_value,
        comparator=comparator,
        threshold=target_value,
        warning_buffer_pct=warning_buffer_pct,
    )


def estimate_sla_credit_amount(
    *,
    status: str,
    monthly_contract_value: Decimal | None,
    credit_rate_pct: Decimal,
    max_credit_pct: Decimal,
    distance_pct: Decimal | None,
) -> Decimal:
    """Estimate service credit leakage for breached SLAs."""
    if status != "breached" or monthly_contract_value is None:
        return Decimal("0.00")

    base_pct = max(Decimal("0"), credit_rate_pct)
    cap_pct = max(base_pct, max_credit_pct)

    multiplier = Decimal("1")
    if distance_pct is not None and distance_pct > 0:
        # Increase credit rate by breach severity in 10% bands.
        multiplier = max(Decimal("1"), distance_pct / Decimal("10"))

    credit_pct = min(cap_pct, base_pct * multiplier)
    amount = (monthly_contract_value * credit_pct) / Decimal("100")
    return amount.quantize(Decimal("0.01"))


def evaluate_rd_tax_project(
    *,
    qualifying_cost: Decimal,
    total_cost: Decimal,
    missing_evidence_count: int,
    min_qualifying_ratio_pct: Decimal,
    credit_rate_pct: Decimal,
) -> RDTaxProjectAssessmentResult:
    """Assess R&D tax claim readiness for one project window."""
    reasons: list[str] = []
    ratio = Decimal("0")
    estimated_credit_amount = Decimal("0.00")

    if total_cost <= 0:
        reasons.append("no_eligible_cost_captured")
        return RDTaxProjectAssessmentResult(
            status="non_compliant",
            qualifying_ratio_pct=Decimal("0"),
            estimated_credit_amount=Decimal("0.00"),
            missing_evidence_count=missing_evidence_count,
            reasons=reasons,
        )

    ratio = (qualifying_cost / total_cost) * Decimal("100")

    if missing_evidence_count > 0:
        reasons.append("missing_evidence")
    if ratio < min_qualifying_ratio_pct:
        reasons.append("qualifying_ratio_below_threshold")

    if reasons:
        status = "non_compliant"
    elif ratio < (min_qualifying_ratio_pct + Decimal("10")):
        status = "at_risk"
        reasons.append("qualifying_ratio_near_threshold")
    else:
        status = "eligible"
        reasons.append("claim_ready")

    if status in {"eligible", "at_risk"} and qualifying_cost > 0:
        estimated_credit_amount = (
            (qualifying_cost * max(Decimal("0"), credit_rate_pct)) / Decimal("100")
        ).quantize(Decimal("0.01"))

    return RDTaxProjectAssessmentResult(
        status=status,
        qualifying_ratio_pct=ratio.quantize(Decimal("0.01")),
        estimated_credit_amount=estimated_credit_amount,
        missing_evidence_count=missing_evidence_count,
        reasons=reasons,
    )


def evaluate_esg_metric_observation(
    *,
    required: bool,
    observation: ESGDisclosureObservation | None,
    stale_after_days: int,
    now: datetime,
) -> ESGMetricStatusResult:
    """Determine if an ESG/CSRD metric disclosure is compliant."""
    if observation is None:
        if required:
            return ESGMetricStatusResult(
                status="missing_required",
                reason="Required metric has no submission in this assessment run",
            )
        return ESGMetricStatusResult(
            status="not_required",
            reason="Optional metric not provided",
        )

    has_value = bool((observation.reported_value or "").strip())
    has_evidence = len(observation.evidence_refs) > 0
    if required and (not has_value or not has_evidence):
        return ESGMetricStatusResult(
            status="missing_required",
            reason="Required metric is missing value or evidence",
        )

    if observation.reported_at is not None:
        age_days = (now - observation.reported_at).days
        if age_days > stale_after_days:
            return ESGMetricStatusResult(
                status="stale",
                reason=f"Submission is stale ({age_days} days old)",
            )

    return ESGMetricStatusResult(
        status="compliant",
        reason="Metric has value, evidence, and acceptable freshness",
    )


def assess_supplier_risk(
    observation: SupplierRiskObservation,
) -> SupplierRiskStatusResult:
    """Calculate supplier financial distress status and reasons."""
    score = 0
    reasons: list[str] = []

    pd = Decimal(str(observation.probability_default_pct))
    if pd >= Decimal("40"):
        score += 50
        reasons.append("high_default_probability")
    elif pd >= Decimal("20"):
        score += 30
        reasons.append("elevated_default_probability")
    elif pd >= Decimal("10"):
        score += 15
        reasons.append("watch_default_probability")

    if observation.payment_delay_days >= 60:
        score += 25
        reasons.append("severe_payment_delay")
    elif observation.payment_delay_days >= 30:
        score += 15
        reasons.append("payment_delay")

    if observation.watchlist_hit:
        score += 35
        reasons.append("insolvency_watchlist_hit")

    if observation.covenant_breach_signal:
        score += 25
        reasons.append("covenant_breach_signal")

    score = min(score, 100)
    if score >= 70:
        status = "critical"
    elif score >= 40:
        status = "warning"
    else:
        status = "stable"

    if not reasons:
        reasons.append("no_adverse_signal")

    return SupplierRiskStatusResult(
        status=status,
        risk_score=score,
        reasons=reasons,
    )


def assess_hs_riddor(
    *,
    incident_type: str,
    severity: str,
    lost_time_days: int,
    occurred_at: datetime,
    reported_to_authority_at: datetime | None,
    due_soon_days: int,
    now: datetime,
) -> HSRiddorStatusResult:
    """Assess RIDDOR reporting obligations and timeline risk."""
    incident_key = incident_type.strip().lower()
    severity_key = severity.strip().lower()
    reasons: list[str] = []

    immediate_reportable_types = {
        "fatality",
        "major_injury",
        "dangerous_occurrence",
        "occupational_disease",
    }
    reportable = (
        incident_key in immediate_reportable_types
        or lost_time_days >= 7
        or severity_key in {"critical", "fatal"}
    )
    if not reportable:
        return HSRiddorStatusResult(
            reportable=False,
            status="not_reportable",
            deadline_at=None,
            days_until_deadline=None,
            reasons=["not_in_riddor_scope"],
        )

    deadline_days = 10 if incident_key in immediate_reportable_types else 15
    deadline_at = occurred_at + timedelta(days=deadline_days)
    days_until_deadline = (deadline_at - now).days

    if reported_to_authority_at is not None:
        if reported_to_authority_at <= deadline_at:
            status = "reported_on_time"
            reasons.append("report_submitted_within_deadline")
        else:
            status = "reported_late"
            reasons.append("report_submitted_after_deadline")
    else:
        if now > deadline_at:
            status = "overdue"
            reasons.append("reporting_deadline_missed")
        elif days_until_deadline <= due_soon_days:
            status = "due_soon"
            reasons.append("reporting_deadline_near")
        else:
            status = "pending_report"
            reasons.append("reporting_pending_within_window")

    return HSRiddorStatusResult(
        reportable=True,
        status=status,
        deadline_at=deadline_at,
        days_until_deadline=days_until_deadline,
        reasons=reasons,
    )


def assess_competitor_signal(
    observation: CompetitorSignalObservation,
) -> CompetitorSignalStatusResult:
    """Score competitor strategic signals into tracking tiers."""
    signal_type = observation.signal_type.strip().lower()
    priority_score = (
        (observation.signal_strength * 0.5)
        + (observation.source_confidence_pct * 0.2)
        + (observation.revenue_impact_pct * 0.3)
    )
    reasons: list[str] = []

    high_impact_types = {
        "pricing_cut",
        "major_product_launch",
        "exclusive_partnership",
        "regulatory_win",
        "funding_round",
    }
    if signal_type in high_impact_types:
        priority_score += 10
        reasons.append("high_impact_signal_type")

    if observation.revenue_impact_pct >= 40:
        reasons.append("high_revenue_impact")
    if observation.source_confidence_pct < 35:
        reasons.append("low_source_confidence")

    bounded_score = max(0, min(int(round(priority_score)), 100))
    if bounded_score >= 75:
        status = "critical"
    elif bounded_score >= 50:
        status = "warning"
    else:
        status = "tracking"

    if not reasons:
        reasons.append("normal_signal")

    return CompetitorSignalStatusResult(
        status=status,
        priority_score=bounded_score,
        reasons=reasons,
    )


class ComplianceOpsService:
    """Compliance operations service with tenant isolation."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def ingest_aml_signal(
        self,
        tenant_id: str,
        request: AMLSignalIngestRequest,
    ) -> AMLSignalIngestResponse:
        score = score_aml_signal(request)
        now = datetime.now(timezone.utc)
        status = "escalated" if score.score >= 70 or request.sanction_hit else "logged"

        signal = AMLSignal(
            tenant_id=tenant_id,
            subject_id=request.subject_id,
            counterparty=request.counterparty,
            amount=Decimal(str(request.amount)) if request.amount is not None else None,
            currency=request.currency.upper(),
            country_from=(request.country_from or "").upper() or None,
            country_to=(request.country_to or "").upper() or None,
            channel=request.channel,
            description=request.description,
            risk_score=score.score,
            flags=score.flags,
            signal_metadata=request.metadata,
            status=status,
            created_at=now,
            updated_at=now,
        )
        self.db.add(signal)
        await self.db.flush()

        action = "logged"
        case_id: str | None = None

        if status == "escalated":
            case = ComplianceCase(
                tenant_id=tenant_id,
                domain="aml",
                case_type="sar",
                title=self._build_case_title(request),
                summary=self._build_case_summary(request, score),
                status="in_review",
                priority="critical" if request.sanction_hit else "high",
                risk_score=score.score,
                source_signal_id=signal.id,
                opened_at=now,
                created_at=now,
                updated_at=now,
            )
            self.db.add(case)
            await self.db.flush()

            case_id = case.id
            signal.related_case_id = case_id
            signal.updated_at = now

            event = ComplianceCaseEvent(
                tenant_id=tenant_id,
                case_id=case_id,
                event_type="aml_signal_escalated",
                event_data={
                    "signal_id": signal.id,
                    "risk_score": score.score,
                    "flags": score.flags,
                },
                created_at=now,
            )
            self.db.add(event)
            action = "escalated_to_case"

        logger.info(
            "AML signal processed tenant=%s signal=%s score=%s action=%s",
            tenant_id,
            signal.id,
            score.score,
            action,
        )

        return AMLSignalIngestResponse(
            signal_id=signal.id,
            risk_score=score.score,
            flags=score.flags,
            action=action,
            case_id=case_id,
        )

    async def list_aml_cases(
        self,
        tenant_id: str,
        status: str | None,
        limit: int,
        offset: int,
    ) -> ComplianceCasesResponse:
        filters = [ComplianceCase.tenant_id == tenant_id, ComplianceCase.domain == "aml"]
        if status:
            filters.append(ComplianceCase.status == status)

        base_query = select(ComplianceCase).where(and_(*filters))
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_query)).scalar_one()

        rows = (
            await self.db.execute(
                base_query
                .order_by(ComplianceCase.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()

        items = [
            ComplianceCaseSummary(
                case_id=row.id,
                domain=row.domain,
                case_type=row.case_type,
                title=row.title,
                summary=row.summary,
                status=row.status,
                priority=row.priority,
                risk_score=row.risk_score,
                opened_at=row.opened_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        return ComplianceCasesResponse(total=total, items=items)

    async def get_case(
        self,
        tenant_id: str,
        case_id: str,
    ) -> ComplianceCaseSummary | None:
        row = (
            await self.db.execute(
                select(ComplianceCase).where(
                    ComplianceCase.id == case_id,
                    ComplianceCase.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()

        if row is None:
            return None

        return ComplianceCaseSummary(
            case_id=row.id,
            domain=row.domain,
            case_type=row.case_type,
            title=row.title,
            summary=row.summary,
            status=row.status,
            priority=row.priority,
            risk_score=row.risk_score,
            opened_at=row.opened_at,
            updated_at=row.updated_at,
        )

    async def upsert_sar_draft(
        self,
        tenant_id: str,
        case_id: str,
        request: SARDraftRequest,
    ) -> SARReportResponse | None:
        case = (
            await self.db.execute(
                select(ComplianceCase).where(
                    ComplianceCase.id == case_id,
                    ComplianceCase.tenant_id == tenant_id,
                    ComplianceCase.domain == "aml",
                )
            )
        ).scalar_one_or_none()

        if case is None:
            return None

        now = datetime.now(timezone.utc)
        report = (
            await self.db.execute(
                select(SARReport).where(
                    SARReport.case_id == case_id,
                    SARReport.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()

        if report is None:
            report = SARReport(
                tenant_id=tenant_id,
                case_id=case_id,
                jurisdiction=request.jurisdiction,
                status="draft",
                suspicion_summary=request.suspicion_summary,
                narrative=request.narrative,
                report_payload=request.report_payload,
                created_at=now,
                updated_at=now,
            )
            self.db.add(report)
            await self.db.flush()
        else:
            report.jurisdiction = request.jurisdiction
            report.suspicion_summary = request.suspicion_summary
            report.narrative = request.narrative
            report.report_payload = request.report_payload
            report.updated_at = now

        case.status = "in_review"
        case.updated_at = now

        self.db.add(
            ComplianceCaseEvent(
                tenant_id=tenant_id,
                case_id=case_id,
                event_type="sar_draft_saved",
                event_data={"report_id": report.id},
                created_at=now,
            )
        )

        return SARReportResponse(
            report_id=report.id,
            case_id=case_id,
            status=report.status,
            jurisdiction=report.jurisdiction,
            submission_reference=report.submission_reference,
            submitted_at=report.submitted_at,
            consent_deadline_at=report.consent_deadline_at,
        )

    async def submit_sar(
        self,
        tenant_id: str,
        case_id: str,
        submission_reference: str | None,
    ) -> SARReportResponse | None:
        report = (
            await self.db.execute(
                select(SARReport).where(
                    SARReport.case_id == case_id,
                    SARReport.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()

        case = (
            await self.db.execute(
                select(ComplianceCase).where(
                    ComplianceCase.id == case_id,
                    ComplianceCase.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()

        if report is None or case is None:
            return None

        now = datetime.now(timezone.utc)
        report.status = "consent_pending"
        report.submitted_at = now
        report.consent_deadline_at = now + timedelta(days=7)
        report.submission_reference = submission_reference or f"SAR-{case_id[:8]}-{int(now.timestamp())}"
        report.updated_at = now

        case.status = "submitted"
        case.updated_at = now

        self.db.add(
            ComplianceCaseEvent(
                tenant_id=tenant_id,
                case_id=case_id,
                event_type="sar_submitted",
                event_data={
                    "report_id": report.id,
                    "submission_reference": report.submission_reference,
                    "consent_deadline_at": report.consent_deadline_at.isoformat(),
                },
                created_at=now,
            )
        )

        return SARReportResponse(
            report_id=report.id,
            case_id=case_id,
            status=report.status,
            jurisdiction=report.jurisdiction,
            submission_reference=report.submission_reference,
            submitted_at=report.submitted_at,
            consent_deadline_at=report.consent_deadline_at,
        )

    async def aml_dashboard(self, tenant_id: str) -> AMLDashboardResponse:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=7)

        open_cases = (
            await self.db.execute(
                select(func.count(ComplianceCase.id)).where(
                    ComplianceCase.tenant_id == tenant_id,
                    ComplianceCase.domain == "aml",
                    ComplianceCase.status.in_(["open", "in_review", "escalated"]),
                )
            )
        ).scalar_one()

        submitted_cases = (
            await self.db.execute(
                select(func.count(ComplianceCase.id)).where(
                    ComplianceCase.tenant_id == tenant_id,
                    ComplianceCase.domain == "aml",
                    ComplianceCase.status == "submitted",
                )
            )
        ).scalar_one()

        high_risk_signals_7d = (
            await self.db.execute(
                select(func.count(AMLSignal.id)).where(
                    AMLSignal.tenant_id == tenant_id,
                    AMLSignal.created_at >= window_start,
                    AMLSignal.risk_score >= 70,
                )
            )
        ).scalar_one()

        signals_7d = (
            await self.db.execute(
                select(func.count(AMLSignal.id)).where(
                    AMLSignal.tenant_id == tenant_id,
                    AMLSignal.created_at >= window_start,
                )
            )
        ).scalar_one()

        return AMLDashboardResponse(
            open_cases=open_cases,
            submitted_cases=submitted_cases,
            high_risk_signals_7d=high_risk_signals_7d,
            signals_7d=signals_7d,
        )

    async def create_obligation(
        self,
        tenant_id: str,
        request: CreateObligationRequest,
    ) -> ObligationResponse:
        now = datetime.now(timezone.utc)
        row = ComplianceObligation(
            tenant_id=tenant_id,
            domain=request.domain,
            title=request.title,
            description=request.description,
            severity=request.severity,
            owner=request.owner,
            frequency=request.frequency,
            source=request.source,
            status="active",
            next_due_at=request.next_due_at,
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        await self.db.flush()

        return ObligationResponse(
            obligation_id=row.id,
            domain=row.domain,
            title=row.title,
            description=row.description,
            severity=row.severity,
            owner=row.owner,
            frequency=row.frequency,
            status=row.status,
            source=row.source,
            next_due_at=row.next_due_at,
            updated_at=row.updated_at,
        )

    async def list_obligations(
        self,
        tenant_id: str,
        domain: str | None,
        status: str | None,
        due_before: datetime | None,
        limit: int,
        offset: int,
    ) -> ObligationsResponse:
        filters = [ComplianceObligation.tenant_id == tenant_id]
        if domain:
            filters.append(ComplianceObligation.domain == domain)
        if status:
            filters.append(ComplianceObligation.status == status)
        if due_before:
            filters.append(ComplianceObligation.next_due_at <= due_before)

        base_query = select(ComplianceObligation).where(and_(*filters))
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_query)).scalar_one()

        rows = (
            await self.db.execute(
                base_query
                .order_by(ComplianceObligation.next_due_at.asc().nullslast())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()

        items = [
            ObligationResponse(
                obligation_id=row.id,
                domain=row.domain,
                title=row.title,
                description=row.description,
                severity=row.severity,
                owner=row.owner,
                frequency=row.frequency,
                status=row.status,
                source=row.source,
                next_due_at=row.next_due_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        return ObligationsResponse(total=total, items=items)

    async def create_covenant(
        self,
        tenant_id: str,
        request: CreateCovenantRequest,
    ) -> CovenantResponse:
        comparator = request.comparator.strip()
        if comparator not in _VALID_COVENANT_COMPARATORS:
            raise ValueError(
                f"Invalid comparator '{request.comparator}'. "
                f"Expected one of {_VALID_COVENANT_COMPARATORS}"
            )

        now = datetime.now(timezone.utc)
        row = FinancialCovenant(
            tenant_id=tenant_id,
            name=request.name,
            metric_name=request.metric_name,
            comparator=comparator,
            threshold=Decimal(str(request.threshold)),
            warning_buffer_pct=Decimal(str(request.warning_buffer_pct)),
            frequency=request.frequency,
            owner=request.owner,
            status="active",
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        await self.db.flush()

        return CovenantResponse(
            covenant_id=row.id,
            name=row.name,
            metric_name=row.metric_name,
            comparator=row.comparator,
            threshold=float(row.threshold),
            warning_buffer_pct=float(row.warning_buffer_pct),
            frequency=row.frequency,
            owner=row.owner,
            status=row.status,
            updated_at=row.updated_at,
        )

    async def list_covenants(
        self,
        tenant_id: str,
        status: str | None,
        limit: int,
        offset: int,
    ) -> CovenantsResponse:
        filters = [FinancialCovenant.tenant_id == tenant_id]
        if status:
            filters.append(FinancialCovenant.status == status)

        base_query = select(FinancialCovenant).where(and_(*filters))
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_query)).scalar_one()

        rows = (
            await self.db.execute(
                base_query
                .order_by(FinancialCovenant.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()

        items = [
            CovenantResponse(
                covenant_id=row.id,
                name=row.name,
                metric_name=row.metric_name,
                comparator=row.comparator,
                threshold=float(row.threshold),
                warning_buffer_pct=float(row.warning_buffer_pct),
                frequency=row.frequency,
                owner=row.owner,
                status=row.status,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        return CovenantsResponse(total=total, items=items)

    async def evaluate_covenants(
        self,
        tenant_id: str,
        request: EvaluateCovenantsRequest,
    ) -> EvaluateCovenantsResponse:
        now = datetime.now(timezone.utc)
        snapshot = FinancialSnapshot(
            tenant_id=tenant_id,
            period_end=request.period_end or now,
            metrics=request.metrics,
            snapshot_metadata=request.metadata,
            created_at=now,
        )
        self.db.add(snapshot)
        await self.db.flush()

        covenants = (
            await self.db.execute(
                select(FinancialCovenant).where(
                    FinancialCovenant.tenant_id == tenant_id,
                    FinancialCovenant.status == "active",
                )
            )
        ).scalars().all()

        items: list[CovenantEvaluationSummary] = []
        breached_count = 0
        at_risk_count = 0
        compliant_count = 0

        for covenant in covenants:
            if covenant.metric_name not in request.metrics:
                continue

            metric_value = Decimal(str(request.metrics[covenant.metric_name]))
            result = evaluate_covenant_value(
                metric_value=metric_value,
                comparator=covenant.comparator,
                threshold=Decimal(str(covenant.threshold)),
                warning_buffer_pct=Decimal(str(covenant.warning_buffer_pct)),
            )

            case_id: str | None = None
            if result.status in {"breached", "at_risk"}:
                case = ComplianceCase(
                    tenant_id=tenant_id,
                    domain="covenant",
                    case_type=(
                        "covenant_breach" if result.status == "breached"
                        else "covenant_risk"
                    ),
                    title=f"Covenant Alert — {covenant.name}",
                    summary=(
                        f"metric={covenant.metric_name} value={metric_value} "
                        f"comparator={covenant.comparator} threshold={covenant.threshold}"
                    ),
                    status="in_review",
                    priority="critical" if result.status == "breached" else "high",
                    risk_score=95 if result.status == "breached" else 75,
                    source_signal_id=covenant.id,
                    opened_at=now,
                    created_at=now,
                    updated_at=now,
                )
                self.db.add(case)
                await self.db.flush()
                case_id = case.id

                self.db.add(
                    ComplianceCaseEvent(
                        tenant_id=tenant_id,
                        case_id=case.id,
                        event_type="covenant_evaluation_alert",
                        event_data={
                            "covenant_id": covenant.id,
                            "snapshot_id": snapshot.id,
                            "status": result.status,
                        },
                        created_at=now,
                    )
                )

            evaluation = CovenantEvaluation(
                tenant_id=tenant_id,
                covenant_id=covenant.id,
                snapshot_id=snapshot.id,
                metric_name=covenant.metric_name,
                metric_value=metric_value,
                threshold=Decimal(str(covenant.threshold)),
                comparator=covenant.comparator,
                status=result.status,
                distance_pct=result.distance_pct,
                case_id=case_id,
                created_at=now,
            )
            self.db.add(evaluation)

            if result.status == "breached":
                breached_count += 1
            elif result.status == "at_risk":
                at_risk_count += 1
            else:
                compliant_count += 1

            items.append(
                CovenantEvaluationSummary(
                    covenant_id=covenant.id,
                    metric_name=covenant.metric_name,
                    status=result.status,
                    comparator=covenant.comparator,
                    threshold=float(covenant.threshold),
                    metric_value=float(metric_value),
                    distance_pct=(
                        float(result.distance_pct)
                        if result.distance_pct is not None else None
                    ),
                    case_id=case_id,
                )
            )

        return EvaluateCovenantsResponse(
            snapshot_id=snapshot.id,
            breached_count=breached_count,
            at_risk_count=at_risk_count,
            compliant_count=compliant_count,
            items=items,
        )

    async def covenant_dashboard(self, tenant_id: str) -> CovenantDashboardResponse:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=30)

        active_covenants = (
            await self.db.execute(
                select(func.count(FinancialCovenant.id)).where(
                    FinancialCovenant.tenant_id == tenant_id,
                    FinancialCovenant.status == "active",
                )
            )
        ).scalar_one()

        breached_30d = (
            await self.db.execute(
                select(func.count(CovenantEvaluation.id)).where(
                    CovenantEvaluation.tenant_id == tenant_id,
                    CovenantEvaluation.status == "breached",
                    CovenantEvaluation.created_at >= window_start,
                )
            )
        ).scalar_one()

        at_risk_30d = (
            await self.db.execute(
                select(func.count(CovenantEvaluation.id)).where(
                    CovenantEvaluation.tenant_id == tenant_id,
                    CovenantEvaluation.status == "at_risk",
                    CovenantEvaluation.created_at >= window_start,
                )
            )
        ).scalar_one()

        return CovenantDashboardResponse(
            active_covenants=active_covenants,
            breached_30d=breached_30d,
            at_risk_30d=at_risk_30d,
        )

    async def create_sla_contract(
        self,
        tenant_id: str,
        request: CreateSLAContractRequest,
    ) -> SLAContractResponse:
        comparator = request.comparator.strip()
        if comparator not in _VALID_SLA_COMPARATORS:
            raise ValueError(
                f"Invalid comparator '{request.comparator}'. "
                f"Expected one of {_VALID_SLA_COMPARATORS}"
            )
        if request.max_credit_pct < request.credit_rate_pct:
            raise ValueError("max_credit_pct must be greater than or equal to credit_rate_pct")

        now = datetime.now(timezone.utc)
        row = SLAContract(
            tenant_id=tenant_id,
            name=request.name.strip(),
            service_name=request.service_name.strip(),
            metric_name=request.metric_name.strip(),
            comparator=comparator,
            target_value=Decimal(str(request.target_value)),
            warning_buffer_pct=Decimal(str(request.warning_buffer_pct)),
            credit_rate_pct=Decimal(str(request.credit_rate_pct)),
            max_credit_pct=Decimal(str(request.max_credit_pct)),
            monthly_contract_value=(
                Decimal(str(request.monthly_contract_value))
                if request.monthly_contract_value is not None
                else None
            ),
            frequency=request.frequency,
            owner=request.owner,
            status="active",
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        await self.db.flush()

        return SLAContractResponse(
            contract_id=row.id,
            name=row.name,
            service_name=row.service_name,
            metric_name=row.metric_name,
            comparator=row.comparator,
            target_value=float(row.target_value),
            warning_buffer_pct=float(row.warning_buffer_pct),
            credit_rate_pct=float(row.credit_rate_pct),
            max_credit_pct=float(row.max_credit_pct),
            monthly_contract_value=(
                float(row.monthly_contract_value)
                if row.monthly_contract_value is not None
                else None
            ),
            frequency=row.frequency,
            owner=row.owner,
            status=row.status,
            updated_at=row.updated_at,
        )

    async def list_sla_contracts(
        self,
        tenant_id: str,
        status: str | None,
        service_name: str | None,
        metric_name: str | None,
        limit: int,
        offset: int,
    ) -> SLAContractsResponse:
        filters = [SLAContract.tenant_id == tenant_id]
        if status:
            filters.append(SLAContract.status == status)
        if service_name:
            filters.append(SLAContract.service_name == service_name)
        if metric_name:
            filters.append(SLAContract.metric_name == metric_name)

        base_query = select(SLAContract).where(and_(*filters))
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_query)).scalar_one()

        rows = (
            await self.db.execute(
                base_query
                .order_by(SLAContract.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()

        items = [
            SLAContractResponse(
                contract_id=row.id,
                name=row.name,
                service_name=row.service_name,
                metric_name=row.metric_name,
                comparator=row.comparator,
                target_value=float(row.target_value),
                warning_buffer_pct=float(row.warning_buffer_pct),
                credit_rate_pct=float(row.credit_rate_pct),
                max_credit_pct=float(row.max_credit_pct),
                monthly_contract_value=(
                    float(row.monthly_contract_value)
                    if row.monthly_contract_value is not None
                    else None
                ),
                frequency=row.frequency,
                owner=row.owner,
                status=row.status,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        return SLAContractsResponse(total=total, items=items)

    async def evaluate_sla(
        self,
        tenant_id: str,
        request: EvaluateSLARequest,
    ) -> EvaluateSLAResponse:
        now = datetime.now(timezone.utc)
        period_end = request.period_end or now
        period_start = request.period_start or (period_end - timedelta(days=7))

        snapshot = SLASnapshot(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            snapshot_metadata=request.metadata,
            created_at=now,
        )
        self.db.add(snapshot)
        await self.db.flush()

        contracts = (
            await self.db.execute(
                select(SLAContract).where(
                    SLAContract.tenant_id == tenant_id,
                    SLAContract.status == "active",
                )
            )
        ).scalars().all()

        observations_by_contract: dict[str, SLAObservation] = {}
        observations_by_metric: dict[tuple[str, str], SLAObservation] = {}
        for observation in request.observations:
            if observation.contract_id:
                observations_by_contract[observation.contract_id.strip()] = observation
            observations_by_metric[
                (
                    observation.service_name.strip().lower(),
                    observation.metric_name.strip().lower(),
                )
            ] = observation

        breached_count = 0
        at_risk_count = 0
        compliant_count = 0
        estimated_credit_exposure = Decimal("0.00")
        items: list[SLAEvaluationSummary] = []

        for contract in contracts:
            observation = self._resolve_sla_observation(
                contract,
                observations_by_contract,
                observations_by_metric,
            )
            if observation is None:
                continue

            observed_value = Decimal(str(observation.observed_value))
            result = evaluate_sla_value(
                observed_value=observed_value,
                comparator=contract.comparator,
                target_value=Decimal(str(contract.target_value)),
                warning_buffer_pct=Decimal(str(contract.warning_buffer_pct)),
            )
            estimated_credit_amount = estimate_sla_credit_amount(
                status=result.status,
                monthly_contract_value=(
                    Decimal(str(contract.monthly_contract_value))
                    if contract.monthly_contract_value is not None
                    else None
                ),
                credit_rate_pct=Decimal(str(contract.credit_rate_pct)),
                max_credit_pct=Decimal(str(contract.max_credit_pct)),
                distance_pct=result.distance_pct,
            )

            case_id: str | None = None
            if request.create_cases and result.status == "breached":
                summary = (
                    f"metric={contract.metric_name} observed={observed_value} "
                    f"target={contract.comparator}{contract.target_value} "
                    f"estimated_credit={estimated_credit_amount}"
                )
                case_id = await self._create_or_reuse_sla_case(
                    tenant_id=tenant_id,
                    case_type="sla_breach",
                    title=f"SLA Breach Alert — {contract.name}",
                    summary=summary,
                    priority="critical",
                    risk_score=89,
                    source_signal_id=contract.id,
                    now=now,
                    event_type="sla_breach_detected",
                    event_data={
                        "contract_id": contract.id,
                        "snapshot_id": snapshot.id,
                        "service_name": contract.service_name,
                        "metric_name": contract.metric_name,
                        "observed_value": float(observed_value),
                        "target_value": float(contract.target_value),
                        "estimated_credit_amount": float(estimated_credit_amount),
                    },
                )

            self.db.add(
                SLAEvaluation(
                    tenant_id=tenant_id,
                    contract_id=contract.id,
                    snapshot_id=snapshot.id,
                    service_name=contract.service_name,
                    metric_name=contract.metric_name,
                    observed_value=observed_value,
                    target_value=Decimal(str(contract.target_value)),
                    comparator=contract.comparator,
                    status=result.status,
                    distance_pct=result.distance_pct,
                    estimated_credit_amount=estimated_credit_amount,
                    case_id=case_id,
                    created_at=now,
                )
            )

            estimated_credit_exposure += estimated_credit_amount
            if result.status == "breached":
                breached_count += 1
            elif result.status == "at_risk":
                at_risk_count += 1
            else:
                compliant_count += 1

            items.append(
                SLAEvaluationSummary(
                    contract_id=contract.id,
                    contract_name=contract.name,
                    service_name=contract.service_name,
                    metric_name=contract.metric_name,
                    status=result.status,
                    comparator=contract.comparator,
                    target_value=float(contract.target_value),
                    observed_value=float(observed_value),
                    distance_pct=(
                        float(result.distance_pct)
                        if result.distance_pct is not None
                        else None
                    ),
                    estimated_credit_amount=float(estimated_credit_amount),
                    case_id=case_id,
                )
            )

        return EvaluateSLAResponse(
            snapshot_id=snapshot.id,
            breached_count=breached_count,
            at_risk_count=at_risk_count,
            compliant_count=compliant_count,
            estimated_credit_exposure=float(estimated_credit_exposure),
            items=items,
        )

    async def sla_dashboard(self, tenant_id: str) -> SLADashboardResponse:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=30)

        active_contracts = (
            await self.db.execute(
                select(func.count(SLAContract.id)).where(
                    SLAContract.tenant_id == tenant_id,
                    SLAContract.status == "active",
                )
            )
        ).scalar_one()

        breached_30d = (
            await self.db.execute(
                select(func.count(SLAEvaluation.id)).where(
                    SLAEvaluation.tenant_id == tenant_id,
                    SLAEvaluation.status == "breached",
                    SLAEvaluation.created_at >= window_start,
                )
            )
        ).scalar_one()

        at_risk_30d = (
            await self.db.execute(
                select(func.count(SLAEvaluation.id)).where(
                    SLAEvaluation.tenant_id == tenant_id,
                    SLAEvaluation.status == "at_risk",
                    SLAEvaluation.created_at >= window_start,
                )
            )
        ).scalar_one()

        estimated_credits_30d = (
            await self.db.execute(
                select(func.coalesce(func.sum(SLAEvaluation.estimated_credit_amount), 0)).where(
                    SLAEvaluation.tenant_id == tenant_id,
                    SLAEvaluation.created_at >= window_start,
                )
            )
        ).scalar_one()

        open_sla_cases = (
            await self.db.execute(
                select(func.count(ComplianceCase.id)).where(
                    ComplianceCase.tenant_id == tenant_id,
                    ComplianceCase.domain == "sla",
                    ComplianceCase.status.in_(["open", "in_review", "escalated"]),
                )
            )
        ).scalar_one()

        return SLADashboardResponse(
            active_contracts=active_contracts,
            breached_30d=breached_30d,
            at_risk_30d=at_risk_30d,
            estimated_credits_30d=float(estimated_credits_30d or 0),
            open_sla_cases=open_sla_cases,
        )

    async def create_gdpr_retention_policy(
        self,
        tenant_id: str,
        request: CreateGDPRRetentionPolicyRequest,
    ) -> GDPRRetentionPolicyResponse:
        now = datetime.now(timezone.utc)
        row = GDPRRetentionPolicy(
            tenant_id=tenant_id,
            system_name=request.system_name.strip(),
            data_category=request.data_category.strip(),
            legal_basis=request.legal_basis.strip() if request.legal_basis else None,
            retention_days=request.retention_days,
            warning_buffer_days=request.warning_buffer_days,
            owner=request.owner,
            status="active",
            source=request.source,
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        await self.db.flush()

        return GDPRRetentionPolicyResponse(
            policy_id=row.id,
            system_name=row.system_name,
            data_category=row.data_category,
            legal_basis=row.legal_basis,
            retention_days=row.retention_days,
            warning_buffer_days=row.warning_buffer_days,
            owner=row.owner,
            status=row.status,
            source=row.source,
            updated_at=row.updated_at,
        )

    async def list_gdpr_retention_policies(
        self,
        tenant_id: str,
        status: str | None,
        system_name: str | None,
        data_category: str | None,
        limit: int,
        offset: int,
    ) -> GDPRRetentionPoliciesResponse:
        filters = [GDPRRetentionPolicy.tenant_id == tenant_id]
        if status:
            filters.append(GDPRRetentionPolicy.status == status)
        if system_name:
            filters.append(GDPRRetentionPolicy.system_name == system_name)
        if data_category:
            filters.append(GDPRRetentionPolicy.data_category == data_category)

        base_query = select(GDPRRetentionPolicy).where(and_(*filters))
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_query)).scalar_one()

        rows = (
            await self.db.execute(
                base_query
                .order_by(GDPRRetentionPolicy.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()

        items = [
            GDPRRetentionPolicyResponse(
                policy_id=row.id,
                system_name=row.system_name,
                data_category=row.data_category,
                legal_basis=row.legal_basis,
                retention_days=row.retention_days,
                warning_buffer_days=row.warning_buffer_days,
                owner=row.owner,
                status=row.status,
                source=row.source,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        return GDPRRetentionPoliciesResponse(total=total, items=items)

    async def evaluate_gdpr_retention(
        self,
        tenant_id: str,
        request: EvaluateGDPRRetentionRequest,
    ) -> EvaluateGDPRRetentionResponse:
        now = datetime.now(timezone.utc)
        snapshot = GDPRRetentionSnapshot(
            tenant_id=tenant_id,
            captured_at=request.captured_at or now,
            snapshot_metadata=request.metadata,
            created_at=now,
        )
        self.db.add(snapshot)
        await self.db.flush()

        policies = (
            await self.db.execute(
                select(GDPRRetentionPolicy).where(
                    GDPRRetentionPolicy.tenant_id == tenant_id,
                    GDPRRetentionPolicy.status == "active",
                )
            )
        ).scalars().all()

        policy_map: dict[tuple[str, str], GDPRRetentionPolicy] = {}
        for policy in policies:
            policy_map[
                (
                    policy.system_name.strip().lower(),
                    policy.data_category.strip().lower(),
                )
            ] = policy

        items: list[GDPRRetentionFindingSummary] = []
        breach_count = 0
        warning_count = 0
        no_policy_count = 0
        compliant_count = 0

        for observation in request.observations:
            system_key = observation.system_name.strip().lower()
            category_key = observation.data_category.strip().lower()
            policy = policy_map.get((system_key, category_key)) or policy_map.get(
                ("*", category_key)
            )

            result = evaluate_gdpr_retention_observation(
                oldest_record_age_days=observation.oldest_record_age_days,
                retention_days=policy.retention_days if policy else None,
                warning_buffer_days=policy.warning_buffer_days if policy else 0,
            )

            case_id: str | None = None
            if request.create_cases and result.status in {"breach", "no_policy"}:
                case_type = (
                    "gdpr_retention_breach"
                    if result.status == "breach"
                    else "gdpr_retention_policy_gap"
                )
                title = (
                    "GDPR Retention Alert — "
                    f"{observation.system_name}/{observation.data_category}"
                )
                summary = (
                    f"status={result.status} oldest_age_days={observation.oldest_record_age_days} "
                    f"retention_days={policy.retention_days if policy else 'n/a'} "
                    f"record_count={observation.record_count}"
                )
                case_id = await self._create_or_reuse_gdpr_case(
                    tenant_id=tenant_id,
                    case_type=case_type,
                    title=title,
                    summary=summary,
                    priority="critical",
                    risk_score=92 if result.status == "breach" else 88,
                    source_signal_id=policy.id if policy else None,
                    now=now,
                    event_type="gdpr_retention_alert",
                    event_data={
                        "snapshot_id": snapshot.id,
                        "status": result.status,
                        "system_name": observation.system_name,
                        "data_category": observation.data_category,
                        "oldest_record_age_days": observation.oldest_record_age_days,
                        "retention_days": policy.retention_days if policy else None,
                    },
                )

            finding = GDPRRetentionFinding(
                tenant_id=tenant_id,
                snapshot_id=snapshot.id,
                policy_id=policy.id if policy else None,
                system_name=observation.system_name,
                data_category=observation.data_category,
                observed_oldest_age_days=observation.oldest_record_age_days,
                retention_days=policy.retention_days if policy else None,
                status=result.status,
                excess_days=result.excess_days,
                reason=result.reason,
                case_id=case_id,
                created_at=now,
            )
            self.db.add(finding)

            if result.status == "breach":
                breach_count += 1
            elif result.status == "warning":
                warning_count += 1
            elif result.status == "no_policy":
                no_policy_count += 1
            else:
                compliant_count += 1

            items.append(
                GDPRRetentionFindingSummary(
                    system_name=observation.system_name,
                    data_category=observation.data_category,
                    status=result.status,
                    reason=result.reason,
                    retention_days=policy.retention_days if policy else None,
                    observed_oldest_age_days=observation.oldest_record_age_days,
                    excess_days=result.excess_days,
                    policy_id=policy.id if policy else None,
                    case_id=case_id,
                )
            )

        return EvaluateGDPRRetentionResponse(
            snapshot_id=snapshot.id,
            breach_count=breach_count,
            warning_count=warning_count,
            no_policy_count=no_policy_count,
            compliant_count=compliant_count,
            items=items,
        )

    async def gdpr_retention_dashboard(
        self,
        tenant_id: str,
    ) -> GDPRRetentionDashboardResponse:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=30)

        active_policies = (
            await self.db.execute(
                select(func.count(GDPRRetentionPolicy.id)).where(
                    GDPRRetentionPolicy.tenant_id == tenant_id,
                    GDPRRetentionPolicy.status == "active",
                )
            )
        ).scalar_one()

        breaches_30d = (
            await self.db.execute(
                select(func.count(GDPRRetentionFinding.id)).where(
                    GDPRRetentionFinding.tenant_id == tenant_id,
                    GDPRRetentionFinding.status == "breach",
                    GDPRRetentionFinding.created_at >= window_start,
                )
            )
        ).scalar_one()

        warnings_30d = (
            await self.db.execute(
                select(func.count(GDPRRetentionFinding.id)).where(
                    GDPRRetentionFinding.tenant_id == tenant_id,
                    GDPRRetentionFinding.status == "warning",
                    GDPRRetentionFinding.created_at >= window_start,
                )
            )
        ).scalar_one()

        no_policy_30d = (
            await self.db.execute(
                select(func.count(GDPRRetentionFinding.id)).where(
                    GDPRRetentionFinding.tenant_id == tenant_id,
                    GDPRRetentionFinding.status == "no_policy",
                    GDPRRetentionFinding.created_at >= window_start,
                )
            )
        ).scalar_one()

        return GDPRRetentionDashboardResponse(
            active_policies=active_policies,
            breaches_30d=breaches_30d,
            warnings_30d=warnings_30d,
            no_policy_30d=no_policy_30d,
        )

    async def create_ropa_activity(
        self,
        tenant_id: str,
        request: CreateROPAActivityRequest,
    ) -> ROPAActivityResponse:
        now = datetime.now(timezone.utc)
        row = GDPRProcessingActivity(
            tenant_id=tenant_id,
            activity_name=request.activity_name.strip(),
            purpose=request.purpose.strip() if request.purpose else None,
            lawful_basis=request.lawful_basis.strip() if request.lawful_basis else None,
            data_categories=request.data_categories,
            data_subjects=request.data_subjects,
            recipients=request.recipients,
            transfer_countries=request.transfer_countries,
            source_system=request.source_system,
            dpa_reference=request.dpa_reference,
            owner=request.owner,
            status=request.status,
            last_reviewed_at=request.last_reviewed_at,
            next_review_due_at=request.next_review_due_at,
            created_at=now,
            updated_at=now,
        )
        self.db.add(row)
        await self.db.flush()

        return ROPAActivityResponse(
            activity_id=row.id,
            activity_name=row.activity_name,
            purpose=row.purpose,
            lawful_basis=row.lawful_basis,
            data_categories=row.data_categories,
            data_subjects=row.data_subjects,
            recipients=row.recipients,
            transfer_countries=row.transfer_countries,
            source_system=row.source_system,
            dpa_reference=row.dpa_reference,
            owner=row.owner,
            status=row.status,
            last_reviewed_at=row.last_reviewed_at,
            next_review_due_at=row.next_review_due_at,
            updated_at=row.updated_at,
        )

    async def list_ropa_activities(
        self,
        tenant_id: str,
        status: str | None,
        limit: int,
        offset: int,
    ) -> ROPAActivitiesResponse:
        filters = [GDPRProcessingActivity.tenant_id == tenant_id]
        if status:
            filters.append(GDPRProcessingActivity.status == status)

        base_query = select(GDPRProcessingActivity).where(and_(*filters))
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_query)).scalar_one()

        rows = (
            await self.db.execute(
                base_query
                .order_by(GDPRProcessingActivity.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()

        items = [
            ROPAActivityResponse(
                activity_id=row.id,
                activity_name=row.activity_name,
                purpose=row.purpose,
                lawful_basis=row.lawful_basis,
                data_categories=row.data_categories,
                data_subjects=row.data_subjects,
                recipients=row.recipients,
                transfer_countries=row.transfer_countries,
                source_system=row.source_system,
                dpa_reference=row.dpa_reference,
                owner=row.owner,
                status=row.status,
                last_reviewed_at=row.last_reviewed_at,
                next_review_due_at=row.next_review_due_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        return ROPAActivitiesResponse(total=total, items=items)

    async def monitor_ropa(
        self,
        tenant_id: str,
        request: MonitorROPARequest,
    ) -> MonitorROPAResponse:
        now = datetime.now(timezone.utc)
        activities = (
            await self.db.execute(
                select(GDPRProcessingActivity).where(
                    GDPRProcessingActivity.tenant_id == tenant_id,
                    GDPRProcessingActivity.status == "active",
                )
            )
        ).scalars().all()

        items: list[ROPAMonitoringItem] = []
        critical_count = 0
        warning_count = 0
        compliant_count = 0

        for activity in activities:
            result = assess_ropa_activity(
                purpose=activity.purpose,
                lawful_basis=activity.lawful_basis,
                data_categories=activity.data_categories or [],
                next_review_due_at=activity.next_review_due_at,
                due_soon_days=request.due_soon_days,
                now=now,
            )

            case_id: str | None = None
            if request.create_cases and result.status == "critical":
                has_gap = any(
                    reason in {
                        "missing_lawful_basis",
                        "missing_purpose",
                        "missing_data_categories",
                    }
                    for reason in result.reasons
                )
                case_type = (
                    "gdpr_ropa_record_gap"
                    if has_gap else "gdpr_ropa_review_overdue"
                )
                summary = (
                    f"activity={activity.activity_name} reasons={','.join(result.reasons)} "
                    f"days_until_review_due={result.days_until_review_due}"
                )
                case_id = await self._create_or_reuse_gdpr_case(
                    tenant_id=tenant_id,
                    case_type=case_type,
                    title=f"GDPR ROPA Alert — {activity.activity_name}",
                    summary=summary,
                    priority="critical",
                    risk_score=90 if has_gap else 82,
                    source_signal_id=activity.id,
                    now=now,
                    event_type="gdpr_ropa_alert",
                    event_data={
                        "activity_id": activity.id,
                        "status": result.status,
                        "reasons": result.reasons,
                        "days_until_review_due": result.days_until_review_due,
                    },
                )

            if result.status == "critical":
                critical_count += 1
            elif result.status == "warning":
                warning_count += 1
            else:
                compliant_count += 1

            items.append(
                ROPAMonitoringItem(
                    activity_id=activity.id,
                    activity_name=activity.activity_name,
                    status=result.status,
                    reasons=result.reasons,
                    days_until_review_due=result.days_until_review_due,
                    case_id=case_id,
                )
            )

        return MonitorROPAResponse(
            total_activities=len(activities),
            critical_count=critical_count,
            warning_count=warning_count,
            compliant_count=compliant_count,
            items=items,
        )

    async def ropa_dashboard(self, tenant_id: str) -> ROPADashboardResponse:
        now = datetime.now(timezone.utc)
        due_soon_end = now + timedelta(days=30)

        active_activities = (
            await self.db.execute(
                select(func.count(GDPRProcessingActivity.id)).where(
                    GDPRProcessingActivity.tenant_id == tenant_id,
                    GDPRProcessingActivity.status == "active",
                )
            )
        ).scalar_one()

        overdue_reviews = (
            await self.db.execute(
                select(func.count(GDPRProcessingActivity.id)).where(
                    GDPRProcessingActivity.tenant_id == tenant_id,
                    GDPRProcessingActivity.status == "active",
                    GDPRProcessingActivity.next_review_due_at.is_not(None),
                    GDPRProcessingActivity.next_review_due_at < now,
                )
            )
        ).scalar_one()

        due_soon_reviews = (
            await self.db.execute(
                select(func.count(GDPRProcessingActivity.id)).where(
                    GDPRProcessingActivity.tenant_id == tenant_id,
                    GDPRProcessingActivity.status == "active",
                    GDPRProcessingActivity.next_review_due_at.is_not(None),
                    GDPRProcessingActivity.next_review_due_at >= now,
                    GDPRProcessingActivity.next_review_due_at <= due_soon_end,
                )
            )
        ).scalar_one()

        missing_lawful_basis = (
            await self.db.execute(
                select(func.count(GDPRProcessingActivity.id)).where(
                    GDPRProcessingActivity.tenant_id == tenant_id,
                    GDPRProcessingActivity.status == "active",
                    or_(
                        GDPRProcessingActivity.lawful_basis.is_(None),
                        GDPRProcessingActivity.lawful_basis == "",
                    ),
                )
            )
        ).scalar_one()

        open_gdpr_cases = (
            await self.db.execute(
                select(func.count(ComplianceCase.id)).where(
                    ComplianceCase.tenant_id == tenant_id,
                    ComplianceCase.domain == "gdpr",
                    ComplianceCase.status.in_(["open", "in_review", "escalated"]),
                )
            )
        ).scalar_one()

        return ROPADashboardResponse(
            active_activities=active_activities,
            overdue_reviews=overdue_reviews,
            due_soon_reviews=due_soon_reviews,
            missing_lawful_basis=missing_lawful_basis,
            open_gdpr_cases=open_gdpr_cases,
        )

    async def create_rd_tax_activity(
        self,
        tenant_id: str,
        request: CreateRDTaxActivityRequest,
    ) -> RDTaxActivityResponse:
        now = datetime.now(timezone.utc)
        activity = RDTaxActivity(
            tenant_id=tenant_id,
            project_code=request.project_code.strip(),
            activity_name=request.activity_name.strip(),
            activity_date=request.activity_date or now,
            qualifying_category=request.qualifying_category.strip().lower(),
            technical_uncertainty=request.technical_uncertainty,
            narrative_present=request.narrative_present,
            staff_hours=Decimal(str(request.staff_hours)),
            cost_amount=Decimal(str(request.cost_amount)),
            evidence_refs=request.evidence_refs,
            source=request.source,
            status="logged",
            created_at=now,
            updated_at=now,
        )
        self.db.add(activity)
        await self.db.flush()

        return RDTaxActivityResponse(
            activity_id=activity.id,
            project_code=activity.project_code,
            activity_name=activity.activity_name,
            activity_date=activity.activity_date,
            qualifying_category=activity.qualifying_category,
            technical_uncertainty=activity.technical_uncertainty,
            narrative_present=activity.narrative_present,
            staff_hours=float(activity.staff_hours),
            cost_amount=float(activity.cost_amount),
            evidence_refs=activity.evidence_refs,
            source=activity.source,
            status=activity.status,
            updated_at=activity.updated_at,
        )

    async def list_rd_tax_activities(
        self,
        tenant_id: str,
        status: str | None,
        project_code: str | None,
        limit: int,
        offset: int,
    ) -> RDTaxActivitiesResponse:
        filters = [RDTaxActivity.tenant_id == tenant_id]
        if status:
            filters.append(RDTaxActivity.status == status)
        if project_code:
            filters.append(RDTaxActivity.project_code == project_code)

        base_query = select(RDTaxActivity).where(and_(*filters))
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_query)).scalar_one()

        rows = (
            await self.db.execute(
                base_query
                .order_by(RDTaxActivity.activity_date.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()

        return RDTaxActivitiesResponse(
            total=total,
            items=[
                RDTaxActivityResponse(
                    activity_id=row.id,
                    project_code=row.project_code,
                    activity_name=row.activity_name,
                    activity_date=row.activity_date,
                    qualifying_category=row.qualifying_category,
                    technical_uncertainty=row.technical_uncertainty,
                    narrative_present=row.narrative_present,
                    staff_hours=float(row.staff_hours),
                    cost_amount=float(row.cost_amount),
                    evidence_refs=row.evidence_refs,
                    source=row.source,
                    status=row.status,
                    updated_at=row.updated_at,
                )
                for row in rows
            ],
        )

    async def evaluate_rd_tax(
        self,
        tenant_id: str,
        request: EvaluateRDTaxRequest,
    ) -> EvaluateRDTaxResponse:
        now = datetime.now(timezone.utc)
        period_end = request.period_end or now
        period_start = request.period_start or (period_end - timedelta(days=90))
        assessment_id = str(uuid.uuid4())

        filters = [
            RDTaxActivity.tenant_id == tenant_id,
            RDTaxActivity.activity_date >= period_start,
            RDTaxActivity.activity_date <= period_end,
        ]
        if request.project_codes:
            filters.append(RDTaxActivity.project_code.in_(request.project_codes))

        activities = (
            await self.db.execute(
                select(RDTaxActivity).where(and_(*filters))
            )
        ).scalars().all()

        grouped: dict[str, list[RDTaxActivity]] = {}
        for activity in activities:
            grouped.setdefault(activity.project_code, []).append(activity)

        min_ratio = Decimal(str(request.min_qualifying_ratio_pct))
        credit_rate = Decimal(str(request.credit_rate_pct))
        eligible_categories = {
            category.strip().lower() for category in request.qualifying_categories
        }

        items: list[RDTaxAssessmentSummary] = []
        eligible_count = 0
        at_risk_count = 0
        non_compliant_count = 0
        estimated_credit_total = Decimal("0.00")

        for project_code, project_activities in grouped.items():
            total_cost = Decimal("0")
            qualifying_cost = Decimal("0")
            missing_evidence_count = 0

            for activity in project_activities:
                cost = Decimal(str(activity.cost_amount or 0))
                total_cost += cost
                has_evidence = len(activity.evidence_refs or []) > 0
                qualifies = (
                    activity.qualifying_category in eligible_categories
                    and activity.technical_uncertainty
                    and activity.narrative_present
                    and has_evidence
                )
                if qualifies:
                    qualifying_cost += cost
                else:
                    if not has_evidence or not activity.narrative_present:
                        missing_evidence_count += 1

            assessment = evaluate_rd_tax_project(
                qualifying_cost=qualifying_cost,
                total_cost=total_cost,
                missing_evidence_count=missing_evidence_count,
                min_qualifying_ratio_pct=min_ratio,
                credit_rate_pct=credit_rate,
            )

            case_id: str | None = None
            if request.create_cases and assessment.status == "non_compliant":
                case_id = await self._create_or_reuse_domain_case(
                    tenant_id=tenant_id,
                    domain="rd_tax",
                    case_type="rd_tax_claim_readiness_gap",
                    title=f"R&D Tax Readiness Gap — {project_code}",
                    summary=(
                        f"qualifying_ratio={assessment.qualifying_ratio_pct} "
                        f"missing_evidence={assessment.missing_evidence_count} "
                        f"total_cost={total_cost}"
                    ),
                    priority="high",
                    risk_score=86,
                    source_signal_id=project_activities[0].id,
                    now=now,
                    event_type="rd_tax_assessment_alert",
                    event_data={
                        "project_code": project_code,
                        "assessment_id": assessment_id,
                        "qualifying_ratio_pct": float(assessment.qualifying_ratio_pct),
                        "missing_evidence_count": assessment.missing_evidence_count,
                    },
                )

            self.db.add(
                RDTaxAssessment(
                    tenant_id=tenant_id,
                    assessment_batch_id=assessment_id,
                    project_code=project_code,
                    period_start=period_start,
                    period_end=period_end,
                    total_cost=total_cost,
                    qualifying_cost=qualifying_cost,
                    qualifying_ratio_pct=assessment.qualifying_ratio_pct,
                    missing_evidence_count=assessment.missing_evidence_count,
                    status=assessment.status,
                    estimated_credit_amount=assessment.estimated_credit_amount,
                    case_id=case_id,
                    reasons=assessment.reasons,
                    created_at=now,
                )
            )

            if assessment.status == "eligible":
                eligible_count += 1
            elif assessment.status == "at_risk":
                at_risk_count += 1
            else:
                non_compliant_count += 1

            estimated_credit_total += assessment.estimated_credit_amount
            items.append(
                RDTaxAssessmentSummary(
                    project_code=project_code,
                    status=assessment.status,
                    total_cost=float(total_cost),
                    qualifying_cost=float(qualifying_cost),
                    qualifying_ratio_pct=float(assessment.qualifying_ratio_pct),
                    missing_evidence_count=assessment.missing_evidence_count,
                    estimated_credit_amount=float(assessment.estimated_credit_amount),
                    reasons=assessment.reasons,
                    case_id=case_id,
                )
            )

        return EvaluateRDTaxResponse(
            assessment_id=assessment_id,
            project_count=len(items),
            eligible_count=eligible_count,
            at_risk_count=at_risk_count,
            non_compliant_count=non_compliant_count,
            estimated_credit_total=float(estimated_credit_total),
            items=items,
        )

    async def rd_tax_dashboard(self, tenant_id: str) -> RDTaxDashboardResponse:
        now = datetime.now(timezone.utc)
        window_30 = now - timedelta(days=30)
        window_90 = now - timedelta(days=90)

        activities_30d = (
            await self.db.execute(
                select(func.count(RDTaxActivity.id)).where(
                    RDTaxActivity.tenant_id == tenant_id,
                    RDTaxActivity.created_at >= window_30,
                )
            )
        ).scalar_one()

        non_compliant_assessments_90d = (
            await self.db.execute(
                select(func.count(RDTaxAssessment.id)).where(
                    RDTaxAssessment.tenant_id == tenant_id,
                    RDTaxAssessment.status == "non_compliant",
                    RDTaxAssessment.created_at >= window_90,
                )
            )
        ).scalar_one()

        at_risk_assessments_90d = (
            await self.db.execute(
                select(func.count(RDTaxAssessment.id)).where(
                    RDTaxAssessment.tenant_id == tenant_id,
                    RDTaxAssessment.status == "at_risk",
                    RDTaxAssessment.created_at >= window_90,
                )
            )
        ).scalar_one()

        estimated_credit_90d = (
            await self.db.execute(
                select(func.coalesce(func.sum(RDTaxAssessment.estimated_credit_amount), 0)).where(
                    RDTaxAssessment.tenant_id == tenant_id,
                    RDTaxAssessment.created_at >= window_90,
                )
            )
        ).scalar_one()

        open_rd_tax_cases = (
            await self.db.execute(
                select(func.count(ComplianceCase.id)).where(
                    ComplianceCase.tenant_id == tenant_id,
                    ComplianceCase.domain == "rd_tax",
                    ComplianceCase.status.in_(["open", "in_review", "escalated"]),
                )
            )
        ).scalar_one()

        return RDTaxDashboardResponse(
            activities_30d=activities_30d,
            non_compliant_assessments_90d=non_compliant_assessments_90d,
            at_risk_assessments_90d=at_risk_assessments_90d,
            estimated_credit_90d=float(estimated_credit_90d or 0),
            open_rd_tax_cases=open_rd_tax_cases,
        )

    async def create_esg_metric(
        self,
        tenant_id: str,
        request: CreateESGMetricRequest,
    ) -> ESGMetricResponse:
        pillar = request.pillar.strip().upper()
        if pillar not in {"E", "S", "G"}:
            raise ValueError("pillar must be one of E, S, G")

        now = datetime.now(timezone.utc)
        metric = ESGMetric(
            tenant_id=tenant_id,
            metric_code=request.metric_code.strip(),
            metric_name=request.metric_name.strip(),
            pillar=pillar,
            reporting_frequency=request.reporting_frequency.strip().lower(),
            required=request.required,
            owner=request.owner,
            status="active",
            created_at=now,
            updated_at=now,
        )
        self.db.add(metric)
        await self.db.flush()

        return ESGMetricResponse(
            metric_id=metric.id,
            metric_code=metric.metric_code,
            metric_name=metric.metric_name,
            pillar=metric.pillar,
            reporting_frequency=metric.reporting_frequency,
            required=metric.required,
            owner=metric.owner,
            status=metric.status,
            updated_at=metric.updated_at,
        )

    async def list_esg_metrics(
        self,
        tenant_id: str,
        status: str | None,
        pillar: str | None,
        limit: int,
        offset: int,
    ) -> ESGMetricsResponse:
        filters = [ESGMetric.tenant_id == tenant_id]
        if status:
            filters.append(ESGMetric.status == status)
        if pillar:
            filters.append(ESGMetric.pillar == pillar.strip().upper())

        base_query = select(ESGMetric).where(and_(*filters))
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_query)).scalar_one()

        rows = (
            await self.db.execute(
                base_query
                .order_by(ESGMetric.metric_code.asc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()

        return ESGMetricsResponse(
            total=total,
            items=[
                ESGMetricResponse(
                    metric_id=row.id,
                    metric_code=row.metric_code,
                    metric_name=row.metric_name,
                    pillar=row.pillar,
                    reporting_frequency=row.reporting_frequency,
                    required=row.required,
                    owner=row.owner,
                    status=row.status,
                    updated_at=row.updated_at,
                )
                for row in rows
            ],
        )

    async def evaluate_esg_csrd(
        self,
        tenant_id: str,
        request: EvaluateESGCSRDRequest,
    ) -> EvaluateESGCSRDResponse:
        now = datetime.now(timezone.utc)
        assessment_id = str(uuid.uuid4())

        metrics = (
            await self.db.execute(
                select(ESGMetric).where(
                    ESGMetric.tenant_id == tenant_id,
                    ESGMetric.status == "active",
                )
            )
        ).scalars().all()
        observations = {
            observation.metric_code.strip().lower(): observation
            for observation in request.observations
        }

        required_metrics = len([metric for metric in metrics if metric.required])
        missing_required_count = 0
        stale_count = 0
        compliant_count = 0
        items: list[ESGCSRDFindingSummary] = []

        for metric in metrics:
            observation = observations.get(metric.metric_code.strip().lower())
            result = evaluate_esg_metric_observation(
                required=metric.required,
                observation=observation,
                stale_after_days=request.stale_after_days,
                now=now,
            )

            case_id: str | None = None
            if request.create_cases and result.status in {"missing_required", "stale"}:
                case_id = await self._create_or_reuse_domain_case(
                    tenant_id=tenant_id,
                    domain="esg",
                    case_type=(
                        "csrd_required_metric_gap"
                        if result.status == "missing_required"
                        else "csrd_metric_stale"
                    ),
                    title=f"CSRD Metric Alert — {metric.metric_code}",
                    summary=result.reason,
                    priority="high",
                    risk_score=84 if result.status == "missing_required" else 72,
                    source_signal_id=metric.id,
                    now=now,
                    event_type="esg_csrd_metric_alert",
                    event_data={
                        "assessment_id": assessment_id,
                        "metric_code": metric.metric_code,
                        "status": result.status,
                        "reason": result.reason,
                    },
                )

            self.db.add(
                ESGCSRDSubmission(
                    tenant_id=tenant_id,
                    assessment_batch_id=assessment_id,
                    metric_id=metric.id,
                    metric_code=metric.metric_code,
                    reported_value=observation.reported_value if observation else None,
                    reported_at=observation.reported_at if observation else None,
                    evidence_refs=observation.evidence_refs if observation else [],
                    assurance_level=observation.assurance_level if observation else None,
                    status=result.status,
                    reason=result.reason,
                    case_id=case_id,
                    created_at=now,
                )
            )

            if result.status == "missing_required":
                missing_required_count += 1
            elif result.status == "stale":
                stale_count += 1
            elif result.status == "compliant":
                compliant_count += 1

            items.append(
                ESGCSRDFindingSummary(
                    metric_id=metric.id,
                    metric_code=metric.metric_code,
                    metric_name=metric.metric_name,
                    pillar=metric.pillar,
                    status=result.status,
                    reason=result.reason,
                    case_id=case_id,
                )
            )

        coverage_denominator = max(required_metrics, 1)
        coverage_pct = (
            (required_metrics - missing_required_count) / coverage_denominator
        ) * 100

        return EvaluateESGCSRDResponse(
            assessment_id=assessment_id,
            required_metrics=required_metrics,
            missing_required_count=missing_required_count,
            stale_count=stale_count,
            compliant_count=compliant_count,
            coverage_pct=round(coverage_pct, 2),
            items=items,
        )

    async def esg_csrd_dashboard(self, tenant_id: str) -> ESGCSRDDashboardResponse:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=30)

        active_metrics = (
            await self.db.execute(
                select(func.count(ESGMetric.id)).where(
                    ESGMetric.tenant_id == tenant_id,
                    ESGMetric.status == "active",
                )
            )
        ).scalar_one()

        required_metrics = (
            await self.db.execute(
                select(func.count(ESGMetric.id)).where(
                    ESGMetric.tenant_id == tenant_id,
                    ESGMetric.status == "active",
                    ESGMetric.required.is_(True),
                )
            )
        ).scalar_one()

        missing_required_30d = (
            await self.db.execute(
                select(func.count(ESGCSRDSubmission.id)).where(
                    ESGCSRDSubmission.tenant_id == tenant_id,
                    ESGCSRDSubmission.status == "missing_required",
                    ESGCSRDSubmission.created_at >= window_start,
                )
            )
        ).scalar_one()

        stale_30d = (
            await self.db.execute(
                select(func.count(ESGCSRDSubmission.id)).where(
                    ESGCSRDSubmission.tenant_id == tenant_id,
                    ESGCSRDSubmission.status == "stale",
                    ESGCSRDSubmission.created_at >= window_start,
                )
            )
        ).scalar_one()

        open_esg_cases = (
            await self.db.execute(
                select(func.count(ComplianceCase.id)).where(
                    ComplianceCase.tenant_id == tenant_id,
                    ComplianceCase.domain == "esg",
                    ComplianceCase.status.in_(["open", "in_review", "escalated"]),
                )
            )
        ).scalar_one()

        return ESGCSRDDashboardResponse(
            active_metrics=active_metrics,
            required_metrics=required_metrics,
            missing_required_30d=missing_required_30d,
            stale_30d=stale_30d,
            open_esg_cases=open_esg_cases,
        )

    async def create_supplier_profile(
        self,
        tenant_id: str,
        request: CreateSupplierProfileRequest,
    ) -> SupplierProfileResponse:
        now = datetime.now(timezone.utc)
        profile = SupplierProfile(
            tenant_id=tenant_id,
            supplier_name=request.supplier_name.strip(),
            country=request.country.strip() if request.country else None,
            criticality=request.criticality.strip().lower(),
            owner=request.owner,
            status="active",
            created_at=now,
            updated_at=now,
        )
        self.db.add(profile)
        await self.db.flush()

        return SupplierProfileResponse(
            supplier_id=profile.id,
            supplier_name=profile.supplier_name,
            country=profile.country,
            criticality=profile.criticality,
            owner=profile.owner,
            status=profile.status,
            updated_at=profile.updated_at,
        )

    async def list_supplier_profiles(
        self,
        tenant_id: str,
        status: str | None,
        criticality: str | None,
        limit: int,
        offset: int,
    ) -> SupplierProfilesResponse:
        filters = [SupplierProfile.tenant_id == tenant_id]
        if status:
            filters.append(SupplierProfile.status == status)
        if criticality:
            filters.append(SupplierProfile.criticality == criticality.strip().lower())

        base_query = select(SupplierProfile).where(and_(*filters))
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_query)).scalar_one()

        rows = (
            await self.db.execute(
                base_query
                .order_by(SupplierProfile.supplier_name.asc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()

        return SupplierProfilesResponse(
            total=total,
            items=[
                SupplierProfileResponse(
                    supplier_id=row.id,
                    supplier_name=row.supplier_name,
                    country=row.country,
                    criticality=row.criticality,
                    owner=row.owner,
                    status=row.status,
                    updated_at=row.updated_at,
                )
                for row in rows
            ],
        )

    async def evaluate_supplier_risk(
        self,
        tenant_id: str,
        request: EvaluateSupplierRiskRequest,
    ) -> EvaluateSupplierRiskResponse:
        now = datetime.now(timezone.utc)
        assessment_id = str(uuid.uuid4())

        suppliers = (
            await self.db.execute(
                select(SupplierProfile).where(
                    SupplierProfile.tenant_id == tenant_id,
                    SupplierProfile.status == "active",
                )
            )
        ).scalars().all()
        suppliers_by_id = {supplier.id: supplier for supplier in suppliers}
        suppliers_by_name = {
            supplier.supplier_name.strip().lower(): supplier
            for supplier in suppliers
        }

        critical_count = 0
        warning_count = 0
        stable_count = 0
        items: list[SupplierRiskAssessmentSummary] = []

        for observation in request.observations:
            supplier: SupplierProfile | None = None
            if observation.supplier_id:
                supplier = suppliers_by_id.get(observation.supplier_id)
            if supplier is None and observation.supplier_name:
                supplier = suppliers_by_name.get(observation.supplier_name.strip().lower())

            status_result = assess_supplier_risk(observation)
            supplier_id = supplier.id if supplier else None
            supplier_name = (
                supplier.supplier_name
                if supplier is not None
                else (observation.supplier_name or "unknown_supplier")
            )

            reasons = list(status_result.reasons)
            if supplier is None:
                reasons.append("supplier_not_registered")

            case_id: str | None = None
            if request.create_cases and status_result.status == "critical":
                case_id = await self._create_or_reuse_domain_case(
                    tenant_id=tenant_id,
                    domain="supplier",
                    case_type="supplier_insolvency_risk",
                    title=f"Supplier Risk Alert — {supplier_name}",
                    summary=(
                        f"risk_score={status_result.risk_score} "
                        f"pd={observation.probability_default_pct} "
                        f"delay_days={observation.payment_delay_days} "
                        f"watchlist_hit={observation.watchlist_hit}"
                    ),
                    priority="critical",
                    risk_score=min(95, max(70, status_result.risk_score)),
                    source_signal_id=supplier_id,
                    now=now,
                    event_type="supplier_risk_alert",
                    event_data={
                        "assessment_id": assessment_id,
                        "supplier_name": supplier_name,
                        "risk_score": status_result.risk_score,
                        "reasons": reasons,
                    },
                )

            self.db.add(
                SupplierRiskAssessment(
                    tenant_id=tenant_id,
                    assessment_batch_id=assessment_id,
                    supplier_id=supplier_id,
                    supplier_name=supplier_name,
                    probability_default_pct=Decimal(str(observation.probability_default_pct)),
                    payment_delay_days=observation.payment_delay_days,
                    watchlist_hit=observation.watchlist_hit,
                    covenant_breach_signal=observation.covenant_breach_signal,
                    source=observation.source,
                    risk_score=status_result.risk_score,
                    status=status_result.status,
                    reasons=reasons,
                    case_id=case_id,
                    created_at=now,
                )
            )

            if status_result.status == "critical":
                critical_count += 1
            elif status_result.status == "warning":
                warning_count += 1
            else:
                stable_count += 1

            items.append(
                SupplierRiskAssessmentSummary(
                    supplier_id=supplier_id,
                    supplier_name=supplier_name,
                    status=status_result.status,
                    risk_score=status_result.risk_score,
                    reasons=reasons,
                    case_id=case_id,
                )
            )

        return EvaluateSupplierRiskResponse(
            assessment_id=assessment_id,
            critical_count=critical_count,
            warning_count=warning_count,
            stable_count=stable_count,
            items=items,
        )

    async def supplier_risk_dashboard(
        self,
        tenant_id: str,
    ) -> SupplierRiskDashboardResponse:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=30)

        active_suppliers = (
            await self.db.execute(
                select(func.count(SupplierProfile.id)).where(
                    SupplierProfile.tenant_id == tenant_id,
                    SupplierProfile.status == "active",
                )
            )
        ).scalar_one()

        critical_signals_30d = (
            await self.db.execute(
                select(func.count(SupplierRiskAssessment.id)).where(
                    SupplierRiskAssessment.tenant_id == tenant_id,
                    SupplierRiskAssessment.status == "critical",
                    SupplierRiskAssessment.created_at >= window_start,
                )
            )
        ).scalar_one()

        warning_signals_30d = (
            await self.db.execute(
                select(func.count(SupplierRiskAssessment.id)).where(
                    SupplierRiskAssessment.tenant_id == tenant_id,
                    SupplierRiskAssessment.status == "warning",
                    SupplierRiskAssessment.created_at >= window_start,
                )
            )
        ).scalar_one()

        watchlist_hits_30d = (
            await self.db.execute(
                select(func.count(SupplierRiskAssessment.id)).where(
                    SupplierRiskAssessment.tenant_id == tenant_id,
                    SupplierRiskAssessment.watchlist_hit.is_(True),
                    SupplierRiskAssessment.created_at >= window_start,
                )
            )
        ).scalar_one()

        open_supplier_cases = (
            await self.db.execute(
                select(func.count(ComplianceCase.id)).where(
                    ComplianceCase.tenant_id == tenant_id,
                    ComplianceCase.domain == "supplier",
                    ComplianceCase.status.in_(["open", "in_review", "escalated"]),
                )
            )
        ).scalar_one()

        return SupplierRiskDashboardResponse(
            active_suppliers=active_suppliers,
            critical_signals_30d=critical_signals_30d,
            warning_signals_30d=warning_signals_30d,
            watchlist_hits_30d=watchlist_hits_30d,
            open_supplier_cases=open_supplier_cases,
        )

    async def create_hs_incident(
        self,
        tenant_id: str,
        request: CreateHSIncidentRequest,
    ) -> HSIncidentResponse:
        now = datetime.now(timezone.utc)
        incident_ref = request.incident_ref or f"HS-{int(now.timestamp())}-{uuid.uuid4().hex[:6].upper()}"
        incident = HSIncident(
            tenant_id=tenant_id,
            incident_ref=incident_ref,
            site=request.site.strip(),
            incident_type=request.incident_type.strip().lower(),
            severity=request.severity.strip().lower(),
            occurred_at=request.occurred_at,
            lost_time_days=request.lost_time_days,
            affected_people=request.affected_people,
            narrative=request.narrative,
            corrective_actions=request.corrective_actions,
            reported_to_authority_at=request.reported_to_authority_at,
            status="open",
            created_at=now,
            updated_at=now,
        )
        self.db.add(incident)
        await self.db.flush()

        return HSIncidentResponse(
            incident_id=incident.id,
            incident_ref=incident.incident_ref,
            site=incident.site,
            incident_type=incident.incident_type,
            severity=incident.severity,
            occurred_at=incident.occurred_at,
            lost_time_days=incident.lost_time_days,
            affected_people=incident.affected_people,
            narrative=incident.narrative,
            corrective_actions=incident.corrective_actions,
            reported_to_authority_at=incident.reported_to_authority_at,
            status=incident.status,
            updated_at=incident.updated_at,
        )

    async def list_hs_incidents(
        self,
        tenant_id: str,
        status: str | None,
        incident_type: str | None,
        limit: int,
        offset: int,
    ) -> HSIncidentsResponse:
        filters = [HSIncident.tenant_id == tenant_id]
        if status:
            filters.append(HSIncident.status == status)
        if incident_type:
            filters.append(HSIncident.incident_type == incident_type.strip().lower())

        base_query = select(HSIncident).where(and_(*filters))
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_query)).scalar_one()

        rows = (
            await self.db.execute(
                base_query
                .order_by(HSIncident.occurred_at.desc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()

        return HSIncidentsResponse(
            total=total,
            items=[
                HSIncidentResponse(
                    incident_id=row.id,
                    incident_ref=row.incident_ref,
                    site=row.site,
                    incident_type=row.incident_type,
                    severity=row.severity,
                    occurred_at=row.occurred_at,
                    lost_time_days=row.lost_time_days,
                    affected_people=row.affected_people,
                    narrative=row.narrative,
                    corrective_actions=row.corrective_actions,
                    reported_to_authority_at=row.reported_to_authority_at,
                    status=row.status,
                    updated_at=row.updated_at,
                )
                for row in rows
            ],
        )

    async def monitor_hs_riddor(
        self,
        tenant_id: str,
        request: MonitorHSRiddorRequest,
    ) -> MonitorHSRiddorResponse:
        now = datetime.now(timezone.utc)
        filters = [HSIncident.tenant_id == tenant_id, HSIncident.status == "open"]
        if request.incident_ids:
            filters.append(HSIncident.id.in_(request.incident_ids))

        incidents = (
            await self.db.execute(
                select(HSIncident).where(and_(*filters))
            )
        ).scalars().all()

        items: list[HSRiddorAssessmentSummary] = []
        reportable_count = 0
        overdue_count = 0
        due_soon_count = 0
        compliant_count = 0

        for incident in incidents:
            result = assess_hs_riddor(
                incident_type=incident.incident_type,
                severity=incident.severity,
                lost_time_days=incident.lost_time_days,
                occurred_at=incident.occurred_at,
                reported_to_authority_at=incident.reported_to_authority_at,
                due_soon_days=request.due_soon_days,
                now=now,
            )

            case_id: str | None = None
            if request.create_cases and result.reportable and result.status in {"overdue", "reported_late"}:
                case_id = await self._create_or_reuse_domain_case(
                    tenant_id=tenant_id,
                    domain="hs",
                    case_type="riddor_reporting_breach",
                    title=f"RIDDOR Reporting Alert — {incident.incident_ref}",
                    summary=(
                        f"status={result.status} incident_type={incident.incident_type} "
                        f"deadline={result.deadline_at.isoformat() if result.deadline_at else 'n/a'}"
                    ),
                    priority="critical",
                    risk_score=91,
                    source_signal_id=incident.id,
                    now=now,
                    event_type="riddor_reporting_alert",
                    event_data={
                        "incident_id": incident.id,
                        "incident_ref": incident.incident_ref,
                        "status": result.status,
                        "deadline_at": (
                            result.deadline_at.isoformat()
                            if result.deadline_at else None
                        ),
                    },
                )

            self.db.add(
                HSRiddorAssessment(
                    tenant_id=tenant_id,
                    incident_id=incident.id,
                    reportable=result.reportable,
                    status=result.status,
                    deadline_at=result.deadline_at,
                    days_until_deadline=result.days_until_deadline,
                    reasons=result.reasons,
                    case_id=case_id,
                    created_at=now,
                )
            )

            if result.reportable:
                reportable_count += 1

            if result.status in {"overdue", "reported_late"}:
                overdue_count += 1
            elif result.status == "due_soon":
                due_soon_count += 1
            else:
                compliant_count += 1

            items.append(
                HSRiddorAssessmentSummary(
                    incident_id=incident.id,
                    incident_ref=incident.incident_ref,
                    reportable=result.reportable,
                    status=result.status,
                    deadline_at=result.deadline_at,
                    days_until_deadline=result.days_until_deadline,
                    reasons=result.reasons,
                    case_id=case_id,
                )
            )

        return MonitorHSRiddorResponse(
            total_incidents=len(incidents),
            reportable_count=reportable_count,
            overdue_count=overdue_count,
            due_soon_count=due_soon_count,
            compliant_count=compliant_count,
            items=items,
        )

    async def hs_riddor_dashboard(self, tenant_id: str) -> HSRiddorDashboardResponse:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=30)

        open_incidents = (
            await self.db.execute(
                select(func.count(HSIncident.id)).where(
                    HSIncident.tenant_id == tenant_id,
                    HSIncident.status == "open",
                )
            )
        ).scalar_one()

        reportable_open = (
            await self.db.execute(
                select(func.count(HSRiddorAssessment.id)).where(
                    HSRiddorAssessment.tenant_id == tenant_id,
                    HSRiddorAssessment.created_at >= window_start,
                    HSRiddorAssessment.reportable.is_(True),
                    HSRiddorAssessment.status.in_(["pending_report", "due_soon", "overdue"]),
                )
            )
        ).scalar_one()

        overdue_reports_30d = (
            await self.db.execute(
                select(func.count(HSRiddorAssessment.id)).where(
                    HSRiddorAssessment.tenant_id == tenant_id,
                    HSRiddorAssessment.created_at >= window_start,
                    HSRiddorAssessment.status.in_(["overdue", "reported_late"]),
                )
            )
        ).scalar_one()

        near_miss_30d = (
            await self.db.execute(
                select(func.count(HSIncident.id)).where(
                    HSIncident.tenant_id == tenant_id,
                    HSIncident.incident_type == "near_miss",
                    HSIncident.occurred_at >= window_start,
                )
            )
        ).scalar_one()

        open_hs_cases = (
            await self.db.execute(
                select(func.count(ComplianceCase.id)).where(
                    ComplianceCase.tenant_id == tenant_id,
                    ComplianceCase.domain == "hs",
                    ComplianceCase.status.in_(["open", "in_review", "escalated"]),
                )
            )
        ).scalar_one()

        return HSRiddorDashboardResponse(
            open_incidents=open_incidents,
            reportable_open=reportable_open,
            overdue_reports_30d=overdue_reports_30d,
            near_miss_30d=near_miss_30d,
            open_hs_cases=open_hs_cases,
        )

    async def create_competitor_profile(
        self,
        tenant_id: str,
        request: CreateCompetitorProfileRequest,
    ) -> CompetitorProfileResponse:
        now = datetime.now(timezone.utc)
        profile = CompetitorProfile(
            tenant_id=tenant_id,
            competitor_name=request.competitor_name.strip(),
            segment=request.segment.strip() if request.segment else None,
            strategic_priority=request.strategic_priority.strip().lower(),
            owner=request.owner,
            status="active",
            created_at=now,
            updated_at=now,
        )
        self.db.add(profile)
        await self.db.flush()

        return CompetitorProfileResponse(
            competitor_id=profile.id,
            competitor_name=profile.competitor_name,
            segment=profile.segment,
            strategic_priority=profile.strategic_priority,
            owner=profile.owner,
            status=profile.status,
            updated_at=profile.updated_at,
        )

    async def list_competitor_profiles(
        self,
        tenant_id: str,
        status: str | None,
        strategic_priority: str | None,
        limit: int,
        offset: int,
    ) -> CompetitorProfilesResponse:
        filters = [CompetitorProfile.tenant_id == tenant_id]
        if status:
            filters.append(CompetitorProfile.status == status)
        if strategic_priority:
            filters.append(
                CompetitorProfile.strategic_priority == strategic_priority.strip().lower()
            )

        base_query = select(CompetitorProfile).where(and_(*filters))
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_query)).scalar_one()

        rows = (
            await self.db.execute(
                base_query
                .order_by(CompetitorProfile.competitor_name.asc())
                .limit(limit)
                .offset(offset)
            )
        ).scalars().all()

        return CompetitorProfilesResponse(
            total=total,
            items=[
                CompetitorProfileResponse(
                    competitor_id=row.id,
                    competitor_name=row.competitor_name,
                    segment=row.segment,
                    strategic_priority=row.strategic_priority,
                    owner=row.owner,
                    status=row.status,
                    updated_at=row.updated_at,
                )
                for row in rows
            ],
        )

    async def evaluate_competitor_signals(
        self,
        tenant_id: str,
        request: EvaluateCompetitorSignalsRequest,
    ) -> EvaluateCompetitorSignalsResponse:
        now = datetime.now(timezone.utc)
        assessment_id = str(uuid.uuid4())

        competitors = (
            await self.db.execute(
                select(CompetitorProfile).where(
                    CompetitorProfile.tenant_id == tenant_id,
                    CompetitorProfile.status == "active",
                )
            )
        ).scalars().all()
        competitors_by_id = {competitor.id: competitor for competitor in competitors}
        competitors_by_name = {
            competitor.competitor_name.strip().lower(): competitor
            for competitor in competitors
        }

        critical_count = 0
        warning_count = 0
        tracking_count = 0
        items: list[CompetitorSignalAssessmentSummary] = []

        for observation in request.observations:
            competitor: CompetitorProfile | None = None
            if observation.competitor_id:
                competitor = competitors_by_id.get(observation.competitor_id)
            if competitor is None and observation.competitor_name:
                competitor = competitors_by_name.get(
                    observation.competitor_name.strip().lower()
                )

            competitor_name = (
                competitor.competitor_name
                if competitor is not None
                else (observation.competitor_name or "unknown_competitor")
            )
            competitor_id = competitor.id if competitor else None
            result = assess_competitor_signal(observation)
            reasons = list(result.reasons)
            if competitor is None:
                reasons.append("competitor_not_registered")

            case_id: str | None = None
            if request.create_cases and result.status == "critical":
                case_id = await self._create_or_reuse_domain_case(
                    tenant_id=tenant_id,
                    domain="competitor",
                    case_type="strategic_signal_critical",
                    title=f"Competitor Strategic Alert — {competitor_name}",
                    summary=(
                        f"signal={observation.signal_type} score={result.priority_score} "
                        f"revenue_impact_pct={observation.revenue_impact_pct}"
                    ),
                    priority="high",
                    risk_score=min(92, max(70, result.priority_score)),
                    source_signal_id=competitor_id,
                    now=now,
                    event_type="competitor_signal_alert",
                    event_data={
                        "assessment_id": assessment_id,
                        "competitor_name": competitor_name,
                        "signal_type": observation.signal_type,
                        "priority_score": result.priority_score,
                        "reasons": reasons,
                    },
                )

            self.db.add(
                CompetitorSignalAssessment(
                    tenant_id=tenant_id,
                    assessment_batch_id=assessment_id,
                    competitor_id=competitor_id,
                    competitor_name=competitor_name,
                    signal_type=observation.signal_type.strip().lower(),
                    signal_strength=observation.signal_strength,
                    source_confidence_pct=Decimal(str(observation.source_confidence_pct)),
                    revenue_impact_pct=Decimal(str(observation.revenue_impact_pct)),
                    observed_at=observation.observed_at or now,
                    summary=observation.summary,
                    priority_score=result.priority_score,
                    status=result.status,
                    reasons=reasons,
                    case_id=case_id,
                    created_at=now,
                )
            )

            if result.status == "critical":
                critical_count += 1
            elif result.status == "warning":
                warning_count += 1
            else:
                tracking_count += 1

            items.append(
                CompetitorSignalAssessmentSummary(
                    competitor_id=competitor_id,
                    competitor_name=competitor_name,
                    signal_type=observation.signal_type,
                    status=result.status,
                    priority_score=result.priority_score,
                    reasons=reasons,
                    case_id=case_id,
                )
            )

        return EvaluateCompetitorSignalsResponse(
            assessment_id=assessment_id,
            critical_count=critical_count,
            warning_count=warning_count,
            tracking_count=tracking_count,
            items=items,
        )

    async def competitor_signals_dashboard(
        self,
        tenant_id: str,
    ) -> CompetitorSignalsDashboardResponse:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=30)

        tracked_competitors = (
            await self.db.execute(
                select(func.count(CompetitorProfile.id)).where(
                    CompetitorProfile.tenant_id == tenant_id,
                    CompetitorProfile.status == "active",
                )
            )
        ).scalar_one()

        critical_signals_30d = (
            await self.db.execute(
                select(func.count(CompetitorSignalAssessment.id)).where(
                    CompetitorSignalAssessment.tenant_id == tenant_id,
                    CompetitorSignalAssessment.status == "critical",
                    CompetitorSignalAssessment.created_at >= window_start,
                )
            )
        ).scalar_one()

        warning_signals_30d = (
            await self.db.execute(
                select(func.count(CompetitorSignalAssessment.id)).where(
                    CompetitorSignalAssessment.tenant_id == tenant_id,
                    CompetitorSignalAssessment.status == "warning",
                    CompetitorSignalAssessment.created_at >= window_start,
                )
            )
        ).scalar_one()

        high_revenue_impact_signals_30d = (
            await self.db.execute(
                select(func.count(CompetitorSignalAssessment.id)).where(
                    CompetitorSignalAssessment.tenant_id == tenant_id,
                    CompetitorSignalAssessment.revenue_impact_pct >= Decimal("40"),
                    CompetitorSignalAssessment.created_at >= window_start,
                )
            )
        ).scalar_one()

        open_competitor_cases = (
            await self.db.execute(
                select(func.count(ComplianceCase.id)).where(
                    ComplianceCase.tenant_id == tenant_id,
                    ComplianceCase.domain == "competitor",
                    ComplianceCase.status.in_(["open", "in_review", "escalated"]),
                )
            )
        ).scalar_one()

        return CompetitorSignalsDashboardResponse(
            tracked_competitors=tracked_competitors,
            critical_signals_30d=critical_signals_30d,
            warning_signals_30d=warning_signals_30d,
            high_revenue_impact_signals_30d=high_revenue_impact_signals_30d,
            open_competitor_cases=open_competitor_cases,
        )

    def _resolve_sla_observation(
        self,
        contract: SLAContract,
        observations_by_contract: dict[str, SLAObservation],
        observations_by_metric: dict[tuple[str, str], SLAObservation],
    ) -> SLAObservation | None:
        by_contract = observations_by_contract.get(contract.id)
        if by_contract is not None:
            return by_contract
        return observations_by_metric.get(
            (contract.service_name.strip().lower(), contract.metric_name.strip().lower())
        )

    async def _create_or_reuse_domain_case(
        self,
        *,
        tenant_id: str,
        domain: str,
        case_type: str,
        title: str,
        summary: str,
        priority: str,
        risk_score: int,
        source_signal_id: str | None,
        now: datetime,
        event_type: str,
        event_data: dict,
    ) -> str:
        existing_case = (
            await self.db.execute(
                select(ComplianceCase).where(
                    ComplianceCase.tenant_id == tenant_id,
                    ComplianceCase.domain == domain,
                    ComplianceCase.case_type == case_type,
                    ComplianceCase.title == title,
                    ComplianceCase.status.in_(["open", "in_review", "escalated"]),
                )
            )
        ).scalar_one_or_none()

        if existing_case is not None:
            existing_case.summary = summary
            existing_case.updated_at = now
            return existing_case.id

        case = ComplianceCase(
            tenant_id=tenant_id,
            domain=domain,
            case_type=case_type,
            title=title,
            summary=summary,
            status="in_review",
            priority=priority,
            risk_score=risk_score,
            source_signal_id=(source_signal_id or "")[:36] or None,
            opened_at=now,
            created_at=now,
            updated_at=now,
        )
        self.db.add(case)
        await self.db.flush()

        self.db.add(
            ComplianceCaseEvent(
                tenant_id=tenant_id,
                case_id=case.id,
                event_type=event_type,
                event_data=event_data,
                created_at=now,
            )
        )
        return case.id

    async def _create_or_reuse_sla_case(
        self,
        tenant_id: str,
        case_type: str,
        title: str,
        summary: str,
        priority: str,
        risk_score: int,
        source_signal_id: str | None,
        now: datetime,
        event_type: str,
        event_data: dict,
    ) -> str:
        existing_case = (
            await self.db.execute(
                select(ComplianceCase).where(
                    ComplianceCase.tenant_id == tenant_id,
                    ComplianceCase.domain == "sla",
                    ComplianceCase.case_type == case_type,
                    ComplianceCase.title == title,
                    ComplianceCase.status.in_(["open", "in_review", "escalated"]),
                )
            )
        ).scalar_one_or_none()

        if existing_case is not None:
            existing_case.summary = summary
            existing_case.updated_at = now
            return existing_case.id

        case = ComplianceCase(
            tenant_id=tenant_id,
            domain="sla",
            case_type=case_type,
            title=title,
            summary=summary,
            status="in_review",
            priority=priority,
            risk_score=risk_score,
            source_signal_id=(source_signal_id or "")[:36] or None,
            opened_at=now,
            created_at=now,
            updated_at=now,
        )
        self.db.add(case)
        await self.db.flush()

        self.db.add(
            ComplianceCaseEvent(
                tenant_id=tenant_id,
                case_id=case.id,
                event_type=event_type,
                event_data=event_data,
                created_at=now,
            )
        )
        return case.id

    async def _create_or_reuse_gdpr_case(
        self,
        tenant_id: str,
        case_type: str,
        title: str,
        summary: str,
        priority: str,
        risk_score: int,
        source_signal_id: str | None,
        now: datetime,
        event_type: str,
        event_data: dict,
    ) -> str:
        existing_case = (
            await self.db.execute(
                select(ComplianceCase).where(
                    ComplianceCase.tenant_id == tenant_id,
                    ComplianceCase.domain == "gdpr",
                    ComplianceCase.case_type == case_type,
                    ComplianceCase.title == title,
                    ComplianceCase.status.in_(["open", "in_review", "escalated"]),
                )
            )
        ).scalar_one_or_none()

        if existing_case is not None:
            existing_case.summary = summary
            existing_case.updated_at = now
            return existing_case.id

        case = ComplianceCase(
            tenant_id=tenant_id,
            domain="gdpr",
            case_type=case_type,
            title=title,
            summary=summary,
            status="in_review",
            priority=priority,
            risk_score=risk_score,
            source_signal_id=(source_signal_id or "")[:36] or None,
            opened_at=now,
            created_at=now,
            updated_at=now,
        )
        self.db.add(case)
        await self.db.flush()

        self.db.add(
            ComplianceCaseEvent(
                tenant_id=tenant_id,
                case_id=case.id,
                event_type=event_type,
                event_data=event_data,
                created_at=now,
            )
        )
        return case.id

    def _build_case_title(self, request: AMLSignalIngestRequest) -> str:
        base = request.subject_id or request.counterparty or "unknown-subject"
        return f"SAR Review — {base}"

    def _build_case_summary(
        self,
        request: AMLSignalIngestRequest,
        score: RiskScoreResult,
    ) -> str:
        bits = []
        if request.amount is not None:
            bits.append(f"amount={request.amount} {request.currency.upper()}")
        if request.country_from or request.country_to:
            bits.append(
                f"route={request.country_from or '--'}->{request.country_to or '--'}"
            )
        if request.channel:
            bits.append(f"channel={request.channel}")
        bits.append(f"flags={','.join(score.flags) if score.flags else 'none'}")
        return " | ".join(bits)
