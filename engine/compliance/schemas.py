"""Pydantic schemas for compliance operations APIs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AMLSignalIngestRequest(BaseModel):
    subject_id: str | None = None
    counterparty: str | None = None
    amount: float | None = Field(default=None, ge=0)
    currency: str = "GBP"
    country_from: str | None = None
    country_to: str | None = None
    channel: str | None = None
    description: str | None = None
    pep_hit: bool = False
    sanction_hit: bool = False
    unusual_pattern: bool = False
    new_customer: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class AMLSignalIngestResponse(BaseModel):
    signal_id: str
    risk_score: int
    flags: list[str]
    action: str
    case_id: str | None = None


class ComplianceCaseSummary(BaseModel):
    case_id: str
    domain: str
    case_type: str
    title: str
    summary: str | None
    status: str
    priority: str
    risk_score: int
    opened_at: datetime
    updated_at: datetime


class ComplianceCasesResponse(BaseModel):
    total: int
    items: list[ComplianceCaseSummary]


class SARDraftRequest(BaseModel):
    suspicion_summary: str
    narrative: str
    report_payload: dict[str, Any] = Field(default_factory=dict)
    jurisdiction: str = "UK_NCA"


class SARReportResponse(BaseModel):
    report_id: str
    case_id: str
    status: str
    jurisdiction: str
    submission_reference: str | None = None
    submitted_at: datetime | None = None
    consent_deadline_at: datetime | None = None


class SARSubmitRequest(BaseModel):
    submission_reference: str | None = None


class AMLDashboardResponse(BaseModel):
    open_cases: int
    submitted_cases: int
    high_risk_signals_7d: int
    signals_7d: int


class CreateObligationRequest(BaseModel):
    domain: str
    title: str
    description: str | None = None
    severity: str = "high"
    owner: str | None = None
    frequency: str | None = None
    source: str = "manual"
    next_due_at: datetime | None = None


class ObligationResponse(BaseModel):
    obligation_id: str
    domain: str
    title: str
    description: str | None
    severity: str
    owner: str | None
    frequency: str | None
    status: str
    source: str
    next_due_at: datetime | None
    updated_at: datetime


class ObligationsResponse(BaseModel):
    total: int
    items: list[ObligationResponse]


class CreateCovenantRequest(BaseModel):
    name: str
    metric_name: str
    comparator: str = Field(description="One of <=, >=, <, >, =")
    threshold: float
    warning_buffer_pct: float = Field(default=10, ge=0)
    frequency: str | None = None
    owner: str | None = None


class CovenantResponse(BaseModel):
    covenant_id: str
    name: str
    metric_name: str
    comparator: str
    threshold: float
    warning_buffer_pct: float
    frequency: str | None
    owner: str | None
    status: str
    updated_at: datetime


class CovenantsResponse(BaseModel):
    total: int
    items: list[CovenantResponse]


class EvaluateCovenantsRequest(BaseModel):
    period_end: datetime | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CovenantEvaluationSummary(BaseModel):
    covenant_id: str
    metric_name: str
    status: str
    comparator: str
    threshold: float
    metric_value: float
    distance_pct: float | None = None
    case_id: str | None = None


class EvaluateCovenantsResponse(BaseModel):
    snapshot_id: str
    breached_count: int
    at_risk_count: int
    compliant_count: int
    items: list[CovenantEvaluationSummary]


class CovenantDashboardResponse(BaseModel):
    active_covenants: int
    breached_30d: int
    at_risk_30d: int


class CreateSLAContractRequest(BaseModel):
    name: str
    service_name: str
    metric_name: str
    comparator: str = Field(description="One of <=, >=, <, >, =")
    target_value: float
    warning_buffer_pct: float = Field(default=10, ge=0)
    credit_rate_pct: float = Field(default=5, ge=0)
    max_credit_pct: float = Field(default=25, ge=0)
    monthly_contract_value: float | None = Field(default=None, ge=0)
    frequency: str | None = None
    owner: str | None = None


class SLAContractResponse(BaseModel):
    contract_id: str
    name: str
    service_name: str
    metric_name: str
    comparator: str
    target_value: float
    warning_buffer_pct: float
    credit_rate_pct: float
    max_credit_pct: float
    monthly_contract_value: float | None
    frequency: str | None
    owner: str | None
    status: str
    updated_at: datetime


class SLAContractsResponse(BaseModel):
    total: int
    items: list[SLAContractResponse]


class SLAObservation(BaseModel):
    contract_id: str | None = None
    service_name: str
    metric_name: str
    observed_value: float
    impacted_requests: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluateSLARequest(BaseModel):
    observations: list[SLAObservation] = Field(default_factory=list)
    period_start: datetime | None = None
    period_end: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    create_cases: bool = True


class SLAEvaluationSummary(BaseModel):
    contract_id: str
    contract_name: str
    service_name: str
    metric_name: str
    status: str
    comparator: str
    target_value: float
    observed_value: float
    distance_pct: float | None = None
    estimated_credit_amount: float
    case_id: str | None = None


class EvaluateSLAResponse(BaseModel):
    snapshot_id: str
    breached_count: int
    at_risk_count: int
    compliant_count: int
    estimated_credit_exposure: float
    items: list[SLAEvaluationSummary]


class SLADashboardResponse(BaseModel):
    active_contracts: int
    breached_30d: int
    at_risk_30d: int
    estimated_credits_30d: float
    open_sla_cases: int


class CreateGDPRRetentionPolicyRequest(BaseModel):
    system_name: str
    data_category: str
    legal_basis: str | None = None
    retention_days: int = Field(ge=1)
    warning_buffer_days: int = Field(default=30, ge=0)
    owner: str | None = None
    source: str = "manual"


class GDPRRetentionPolicyResponse(BaseModel):
    policy_id: str
    system_name: str
    data_category: str
    legal_basis: str | None
    retention_days: int
    warning_buffer_days: int
    owner: str | None
    status: str
    source: str
    updated_at: datetime


class GDPRRetentionPoliciesResponse(BaseModel):
    total: int
    items: list[GDPRRetentionPolicyResponse]


class GDPRRetentionObservation(BaseModel):
    system_name: str
    data_category: str
    oldest_record_age_days: int = Field(ge=0)
    record_count: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluateGDPRRetentionRequest(BaseModel):
    observations: list[GDPRRetentionObservation] = Field(default_factory=list)
    captured_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    create_cases: bool = True


class GDPRRetentionFindingSummary(BaseModel):
    system_name: str
    data_category: str
    status: str
    reason: str
    retention_days: int | None = None
    observed_oldest_age_days: int
    excess_days: int | None = None
    policy_id: str | None = None
    case_id: str | None = None


class EvaluateGDPRRetentionResponse(BaseModel):
    snapshot_id: str
    breach_count: int
    warning_count: int
    no_policy_count: int
    compliant_count: int
    items: list[GDPRRetentionFindingSummary]


class GDPRRetentionDashboardResponse(BaseModel):
    active_policies: int
    breaches_30d: int
    warnings_30d: int
    no_policy_30d: int


class CreateROPAActivityRequest(BaseModel):
    activity_name: str
    purpose: str | None = None
    lawful_basis: str | None = None
    data_categories: list[str] = Field(default_factory=list)
    data_subjects: list[str] = Field(default_factory=list)
    recipients: list[str] = Field(default_factory=list)
    transfer_countries: list[str] = Field(default_factory=list)
    source_system: str | None = None
    dpa_reference: str | None = None
    owner: str | None = None
    status: str = "active"
    last_reviewed_at: datetime | None = None
    next_review_due_at: datetime | None = None


class ROPAActivityResponse(BaseModel):
    activity_id: str
    activity_name: str
    purpose: str | None
    lawful_basis: str | None
    data_categories: list[str]
    data_subjects: list[str]
    recipients: list[str]
    transfer_countries: list[str]
    source_system: str | None
    dpa_reference: str | None
    owner: str | None
    status: str
    last_reviewed_at: datetime | None
    next_review_due_at: datetime | None
    updated_at: datetime


class ROPAActivitiesResponse(BaseModel):
    total: int
    items: list[ROPAActivityResponse]


class MonitorROPARequest(BaseModel):
    due_soon_days: int = Field(default=30, ge=1, le=180)
    create_cases: bool = True


class ROPAMonitoringItem(BaseModel):
    activity_id: str
    activity_name: str
    status: str
    reasons: list[str]
    days_until_review_due: int | None = None
    case_id: str | None = None


class MonitorROPAResponse(BaseModel):
    total_activities: int
    critical_count: int
    warning_count: int
    compliant_count: int
    items: list[ROPAMonitoringItem]


class ROPADashboardResponse(BaseModel):
    active_activities: int
    overdue_reviews: int
    due_soon_reviews: int
    missing_lawful_basis: int
    open_gdpr_cases: int


class CreateRDTaxActivityRequest(BaseModel):
    project_code: str
    activity_name: str
    activity_date: datetime | None = None
    qualifying_category: str
    technical_uncertainty: bool = False
    narrative_present: bool = False
    staff_hours: float = Field(default=0, ge=0)
    cost_amount: float = Field(default=0, ge=0)
    evidence_refs: list[str] = Field(default_factory=list)
    source: str = "manual"


class RDTaxActivityResponse(BaseModel):
    activity_id: str
    project_code: str
    activity_name: str
    activity_date: datetime
    qualifying_category: str
    technical_uncertainty: bool
    narrative_present: bool
    staff_hours: float
    cost_amount: float
    evidence_refs: list[str]
    source: str
    status: str
    updated_at: datetime


class RDTaxActivitiesResponse(BaseModel):
    total: int
    items: list[RDTaxActivityResponse]


class EvaluateRDTaxRequest(BaseModel):
    period_start: datetime | None = None
    period_end: datetime | None = None
    project_codes: list[str] = Field(default_factory=list)
    qualifying_categories: list[str] = Field(default_factory=lambda: ["staffing", "software", "contractor", "prototype"])
    min_qualifying_ratio_pct: float = Field(default=60, ge=0, le=100)
    credit_rate_pct: float = Field(default=13, ge=0, le=100)
    create_cases: bool = True


class RDTaxAssessmentSummary(BaseModel):
    project_code: str
    status: str
    total_cost: float
    qualifying_cost: float
    qualifying_ratio_pct: float
    missing_evidence_count: int
    estimated_credit_amount: float
    reasons: list[str]
    case_id: str | None = None


class EvaluateRDTaxResponse(BaseModel):
    assessment_id: str
    project_count: int
    eligible_count: int
    at_risk_count: int
    non_compliant_count: int
    estimated_credit_total: float
    items: list[RDTaxAssessmentSummary]


class RDTaxDashboardResponse(BaseModel):
    activities_30d: int
    non_compliant_assessments_90d: int
    at_risk_assessments_90d: int
    estimated_credit_90d: float
    open_rd_tax_cases: int


class CreateESGMetricRequest(BaseModel):
    metric_code: str
    metric_name: str
    pillar: str = Field(description="E, S, or G")
    reporting_frequency: str = "quarterly"
    required: bool = True
    owner: str | None = None


class ESGMetricResponse(BaseModel):
    metric_id: str
    metric_code: str
    metric_name: str
    pillar: str
    reporting_frequency: str
    required: bool
    owner: str | None
    status: str
    updated_at: datetime


class ESGMetricsResponse(BaseModel):
    total: int
    items: list[ESGMetricResponse]


class ESGDisclosureObservation(BaseModel):
    metric_code: str
    reported_value: str | None = None
    reported_at: datetime | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    assurance_level: str | None = None


class EvaluateESGCSRDRequest(BaseModel):
    observations: list[ESGDisclosureObservation] = Field(default_factory=list)
    stale_after_days: int = Field(default=60, ge=1, le=365)
    create_cases: bool = True


class ESGCSRDFindingSummary(BaseModel):
    metric_id: str | None = None
    metric_code: str
    metric_name: str
    pillar: str
    status: str
    reason: str
    case_id: str | None = None


class EvaluateESGCSRDResponse(BaseModel):
    assessment_id: str
    required_metrics: int
    missing_required_count: int
    stale_count: int
    compliant_count: int
    coverage_pct: float
    items: list[ESGCSRDFindingSummary]


class ESGCSRDDashboardResponse(BaseModel):
    active_metrics: int
    required_metrics: int
    missing_required_30d: int
    stale_30d: int
    open_esg_cases: int


class CreateSupplierProfileRequest(BaseModel):
    supplier_name: str
    country: str | None = None
    criticality: str = "medium"
    owner: str | None = None


class SupplierProfileResponse(BaseModel):
    supplier_id: str
    supplier_name: str
    country: str | None
    criticality: str
    owner: str | None
    status: str
    updated_at: datetime


class SupplierProfilesResponse(BaseModel):
    total: int
    items: list[SupplierProfileResponse]


class SupplierRiskObservation(BaseModel):
    supplier_id: str | None = None
    supplier_name: str | None = None
    probability_default_pct: float = Field(default=0, ge=0, le=100)
    payment_delay_days: int = Field(default=0, ge=0)
    watchlist_hit: bool = False
    covenant_breach_signal: bool = False
    source: str | None = None


class EvaluateSupplierRiskRequest(BaseModel):
    observations: list[SupplierRiskObservation] = Field(default_factory=list)
    create_cases: bool = True


class SupplierRiskAssessmentSummary(BaseModel):
    supplier_id: str | None = None
    supplier_name: str
    status: str
    risk_score: int
    reasons: list[str]
    case_id: str | None = None


class EvaluateSupplierRiskResponse(BaseModel):
    assessment_id: str
    critical_count: int
    warning_count: int
    stable_count: int
    items: list[SupplierRiskAssessmentSummary]


class SupplierRiskDashboardResponse(BaseModel):
    active_suppliers: int
    critical_signals_30d: int
    warning_signals_30d: int
    watchlist_hits_30d: int
    open_supplier_cases: int


class CreateHSIncidentRequest(BaseModel):
    incident_ref: str | None = None
    site: str
    incident_type: str
    severity: str = "medium"
    occurred_at: datetime
    lost_time_days: int = Field(default=0, ge=0)
    affected_people: int = Field(default=1, ge=1)
    narrative: str | None = None
    corrective_actions: list[str] = Field(default_factory=list)
    reported_to_authority_at: datetime | None = None


class HSIncidentResponse(BaseModel):
    incident_id: str
    incident_ref: str
    site: str
    incident_type: str
    severity: str
    occurred_at: datetime
    lost_time_days: int
    affected_people: int
    narrative: str | None
    corrective_actions: list[str]
    reported_to_authority_at: datetime | None
    status: str
    updated_at: datetime


class HSIncidentsResponse(BaseModel):
    total: int
    items: list[HSIncidentResponse]


class MonitorHSRiddorRequest(BaseModel):
    incident_ids: list[str] = Field(default_factory=list)
    due_soon_days: int = Field(default=3, ge=1, le=30)
    create_cases: bool = True


class HSRiddorAssessmentSummary(BaseModel):
    incident_id: str
    incident_ref: str
    reportable: bool
    status: str
    deadline_at: datetime | None = None
    days_until_deadline: int | None = None
    reasons: list[str]
    case_id: str | None = None


class MonitorHSRiddorResponse(BaseModel):
    total_incidents: int
    reportable_count: int
    overdue_count: int
    due_soon_count: int
    compliant_count: int
    items: list[HSRiddorAssessmentSummary]


class HSRiddorDashboardResponse(BaseModel):
    open_incidents: int
    reportable_open: int
    overdue_reports_30d: int
    near_miss_30d: int
    open_hs_cases: int


class CreateCompetitorProfileRequest(BaseModel):
    competitor_name: str
    segment: str | None = None
    strategic_priority: str = "medium"
    owner: str | None = None


class CompetitorProfileResponse(BaseModel):
    competitor_id: str
    competitor_name: str
    segment: str | None
    strategic_priority: str
    owner: str | None
    status: str
    updated_at: datetime


class CompetitorProfilesResponse(BaseModel):
    total: int
    items: list[CompetitorProfileResponse]


class CompetitorSignalObservation(BaseModel):
    competitor_id: str | None = None
    competitor_name: str | None = None
    signal_type: str
    signal_strength: int = Field(default=0, ge=0, le=100)
    source_confidence_pct: float = Field(default=0, ge=0, le=100)
    revenue_impact_pct: float = Field(default=0, ge=0, le=100)
    observed_at: datetime | None = None
    summary: str | None = None


class EvaluateCompetitorSignalsRequest(BaseModel):
    observations: list[CompetitorSignalObservation] = Field(default_factory=list)
    create_cases: bool = True


class CompetitorSignalAssessmentSummary(BaseModel):
    competitor_id: str | None = None
    competitor_name: str
    signal_type: str
    status: str
    priority_score: int
    reasons: list[str]
    case_id: str | None = None


class EvaluateCompetitorSignalsResponse(BaseModel):
    assessment_id: str
    critical_count: int
    warning_count: int
    tracking_count: int
    items: list[CompetitorSignalAssessmentSummary]


class CompetitorSignalsDashboardResponse(BaseModel):
    tracked_competitors: int
    critical_signals_30d: int
    warning_signals_30d: int
    high_revenue_impact_signals_30d: int
    open_competitor_cases: int
