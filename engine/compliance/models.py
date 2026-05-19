"""
Ironpass — Compliance operations models.

Focused on high-stakes, high-value backend operations:
- obligations tracking
- AML signal monitoring
- SAR case workflow
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB

from engine.database.base import Base


class ComplianceObligation(Base):
    """Tenant-scoped recurring compliance obligation."""

    __tablename__ = "compliance_obligations"
    __table_args__ = (
        Index("idx_obligation_tenant_domain", "tenant_id", "domain"),
        Index("idx_obligation_tenant_status_due", "tenant_id", "status", "next_due_at"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    domain = Column(String(64), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(16), nullable=False, default="high")
    owner = Column(String(128), nullable=True)
    frequency = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default="active")
    source = Column(String(64), nullable=False, default="manual")
    next_due_at = Column(DateTime(timezone=True), nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class AMLSignal(Base):
    """AML signal/event produced by transaction/customer monitoring."""

    __tablename__ = "aml_signals"
    __table_args__ = (
        Index("idx_aml_signal_tenant_created", "tenant_id", "created_at"),
        Index("idx_aml_signal_tenant_status", "tenant_id", "status"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    subject_id = Column(String(128), nullable=True)
    counterparty = Column(String(255), nullable=True)
    amount = Column(Numeric(18, 2), nullable=True)
    currency = Column(String(8), nullable=False, default="GBP")
    country_from = Column(String(2), nullable=True)
    country_to = Column(String(2), nullable=True)
    channel = Column(String(32), nullable=True)
    description = Column(Text, nullable=True)
    risk_score = Column(Integer, nullable=False, default=0)
    flags = Column(JSONB, nullable=False, default=list)
    signal_metadata = Column("metadata", JSONB, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="logged")
    related_case_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class ComplianceCase(Base):
    """Case management entity for high-risk investigations."""

    __tablename__ = "compliance_cases"
    __table_args__ = (
        Index("idx_compliance_case_tenant_domain_status", "tenant_id", "domain", "status"),
        Index("idx_compliance_case_tenant_created", "tenant_id", "created_at"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    domain = Column(String(64), nullable=False, default="aml")
    case_type = Column(String(64), nullable=False, default="sar")
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="open")
    priority = Column(String(16), nullable=False, default="high")
    risk_score = Column(Integer, nullable=False, default=0)
    assigned_to = Column(String(128), nullable=True)
    source_signal_id = Column(String(36), nullable=True)
    opened_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class SARReport(Base):
    """Suspicious Activity Report draft/submission record."""

    __tablename__ = "sar_reports"
    __table_args__ = (
        Index("idx_sar_report_tenant_case", "tenant_id", "case_id"),
        Index("idx_sar_report_tenant_status", "tenant_id", "status"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    case_id = Column(String(36), nullable=False)
    jurisdiction = Column(String(32), nullable=False, default="UK_NCA")
    status = Column(String(32), nullable=False, default="draft")
    suspicion_summary = Column(Text, nullable=False)
    narrative = Column(Text, nullable=False)
    report_payload = Column(JSONB, nullable=False, default=dict)
    submission_reference = Column(String(128), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    consent_deadline_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class ComplianceCaseEvent(Base):
    """Immutable timeline events for compliance case actions."""

    __tablename__ = "compliance_case_events"
    __table_args__ = (
        Index("idx_case_event_tenant_case_created", "tenant_id", "case_id", "created_at"),
        {"schema": "public"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(String(36), nullable=False)
    case_id = Column(String(36), nullable=False)
    event_type = Column(String(64), nullable=False)
    event_data = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class FinancialCovenant(Base):
    """Tenant-defined financial covenant from debt agreements."""

    __tablename__ = "financial_covenants"
    __table_args__ = (
        Index("idx_covenant_tenant_status", "tenant_id", "status"),
        Index("idx_covenant_tenant_metric", "tenant_id", "metric_name"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    name = Column(String(255), nullable=False)
    metric_name = Column(String(128), nullable=False)
    comparator = Column(String(8), nullable=False)  # <=, >=, <, >, =
    threshold = Column(Numeric(18, 6), nullable=False)
    warning_buffer_pct = Column(Numeric(8, 3), nullable=False, default=10)
    frequency = Column(String(64), nullable=True)
    owner = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class FinancialSnapshot(Base):
    """Periodic financial metrics snapshot used for covenant checks."""

    __tablename__ = "financial_snapshots"
    __table_args__ = (
        Index("idx_fin_snapshot_tenant_period", "tenant_id", "period_end"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    metrics = Column(JSONB, nullable=False, default=dict)
    snapshot_metadata = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class CovenantEvaluation(Base):
    """Result of evaluating one covenant against one snapshot."""

    __tablename__ = "covenant_evaluations"
    __table_args__ = (
        Index("idx_cov_eval_tenant_snapshot", "tenant_id", "snapshot_id"),
        Index("idx_cov_eval_tenant_status", "tenant_id", "status"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    covenant_id = Column(String(36), nullable=False)
    snapshot_id = Column(String(36), nullable=False)
    metric_name = Column(String(128), nullable=False)
    metric_value = Column(Numeric(18, 6), nullable=False)
    threshold = Column(Numeric(18, 6), nullable=False)
    comparator = Column(String(8), nullable=False)
    status = Column(String(32), nullable=False)  # compliant, at_risk, breached
    distance_pct = Column(Numeric(10, 4), nullable=True)
    case_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class GDPRRetentionPolicy(Base):
    """Tenant-scoped retention policy for a data category and source system."""

    __tablename__ = "gdpr_retention_policies"
    __table_args__ = (
        Index("idx_gdpr_policy_tenant_status", "tenant_id", "status"),
        Index(
            "idx_gdpr_policy_tenant_system_category",
            "tenant_id",
            "system_name",
            "data_category",
        ),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    system_name = Column(String(128), nullable=False)
    data_category = Column(String(128), nullable=False)
    legal_basis = Column(String(128), nullable=True)
    retention_days = Column(Integer, nullable=False)
    warning_buffer_days = Column(Integer, nullable=False, default=30)
    owner = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="active")
    source = Column(String(64), nullable=False, default="manual")
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class GDPRRetentionSnapshot(Base):
    """Captured retention scan input payload metadata."""

    __tablename__ = "gdpr_retention_snapshots"
    __table_args__ = (
        Index("idx_gdpr_snapshot_tenant_captured", "tenant_id", "captured_at"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    captured_at = Column(DateTime(timezone=True), nullable=False)
    snapshot_metadata = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class GDPRRetentionFinding(Base):
    """Outcome of retention checks against data observations."""

    __tablename__ = "gdpr_retention_findings"
    __table_args__ = (
        Index("idx_gdpr_finding_tenant_snapshot", "tenant_id", "snapshot_id"),
        Index("idx_gdpr_finding_tenant_status_created", "tenant_id", "status", "created_at"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    snapshot_id = Column(String(36), nullable=False)
    policy_id = Column(String(36), nullable=True)
    system_name = Column(String(128), nullable=False)
    data_category = Column(String(128), nullable=False)
    observed_oldest_age_days = Column(Integer, nullable=False)
    retention_days = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False)  # compliant, warning, breach, no_policy
    excess_days = Column(Integer, nullable=True)
    reason = Column(Text, nullable=True)
    case_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class GDPRProcessingActivity(Base):
    """GDPR Article 30 Record of Processing Activities (ROPA) entry."""

    __tablename__ = "gdpr_processing_activities"
    __table_args__ = (
        Index("idx_gdpr_ropa_tenant_status", "tenant_id", "status"),
        Index("idx_gdpr_ropa_tenant_review_due", "tenant_id", "next_review_due_at"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    activity_name = Column(String(255), nullable=False)
    purpose = Column(Text, nullable=True)
    lawful_basis = Column(String(64), nullable=True)
    data_categories = Column(JSONB, nullable=False, default=list)
    data_subjects = Column(JSONB, nullable=False, default=list)
    recipients = Column(JSONB, nullable=False, default=list)
    transfer_countries = Column(JSONB, nullable=False, default=list)
    source_system = Column(String(128), nullable=True)
    dpa_reference = Column(String(128), nullable=True)
    owner = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="active")
    last_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    next_review_due_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class SLAContract(Base):
    """Tenant-defined SLA contract threshold and penalty settings."""

    __tablename__ = "sla_contracts"
    __table_args__ = (
        Index("idx_sla_contract_tenant_status", "tenant_id", "status"),
        Index("idx_sla_contract_tenant_service_metric", "tenant_id", "service_name", "metric_name"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    name = Column(String(255), nullable=False)
    service_name = Column(String(128), nullable=False)
    metric_name = Column(String(128), nullable=False)
    comparator = Column(String(8), nullable=False)  # <=, >=, <, >, =
    target_value = Column(Numeric(18, 6), nullable=False)
    warning_buffer_pct = Column(Numeric(8, 3), nullable=False, default=10)
    credit_rate_pct = Column(Numeric(8, 3), nullable=False, default=5)
    max_credit_pct = Column(Numeric(8, 3), nullable=False, default=25)
    monthly_contract_value = Column(Numeric(18, 2), nullable=True)
    frequency = Column(String(64), nullable=True)
    owner = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class SLASnapshot(Base):
    """Periodic SLA observation batch metadata."""

    __tablename__ = "sla_snapshots"
    __table_args__ = (
        Index("idx_sla_snapshot_tenant_period", "tenant_id", "period_end"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    snapshot_metadata = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class SLAEvaluation(Base):
    """Result of evaluating one SLA contract against one observation batch."""

    __tablename__ = "sla_evaluations"
    __table_args__ = (
        Index("idx_sla_eval_tenant_snapshot", "tenant_id", "snapshot_id"),
        Index("idx_sla_eval_tenant_status_created", "tenant_id", "status", "created_at"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    contract_id = Column(String(36), nullable=False)
    snapshot_id = Column(String(36), nullable=False)
    service_name = Column(String(128), nullable=False)
    metric_name = Column(String(128), nullable=False)
    observed_value = Column(Numeric(18, 6), nullable=False)
    target_value = Column(Numeric(18, 6), nullable=False)
    comparator = Column(String(8), nullable=False)
    status = Column(String(32), nullable=False)  # compliant, at_risk, breached
    distance_pct = Column(Numeric(10, 4), nullable=True)
    estimated_credit_amount = Column(Numeric(18, 2), nullable=False, default=0)
    case_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class RDTaxActivity(Base):
    """R&D tax credit activity log with evidence capture metadata."""

    __tablename__ = "rd_tax_activities"
    __table_args__ = (
        Index("idx_rd_tax_activity_tenant_project_date", "tenant_id", "project_code", "activity_date"),
        Index("idx_rd_tax_activity_tenant_status", "tenant_id", "status"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    project_code = Column(String(128), nullable=False)
    activity_name = Column(String(255), nullable=False)
    activity_date = Column(DateTime(timezone=True), nullable=False)
    qualifying_category = Column(String(64), nullable=False)
    technical_uncertainty = Column(Boolean, nullable=False, default=False)
    narrative_present = Column(Boolean, nullable=False, default=False)
    staff_hours = Column(Numeric(12, 2), nullable=False, default=0)
    cost_amount = Column(Numeric(18, 2), nullable=False, default=0)
    evidence_refs = Column(JSONB, nullable=False, default=list)
    source = Column(String(64), nullable=False, default="manual")
    status = Column(String(32), nullable=False, default="logged")
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class RDTaxAssessment(Base):
    """Assessment run output for R&D claim readiness by project."""

    __tablename__ = "rd_tax_assessments"
    __table_args__ = (
        Index("idx_rd_tax_assess_tenant_batch", "tenant_id", "assessment_batch_id"),
        Index("idx_rd_tax_assess_tenant_status", "tenant_id", "status"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    assessment_batch_id = Column(String(36), nullable=False)
    project_code = Column(String(128), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False)
    total_cost = Column(Numeric(18, 2), nullable=False, default=0)
    qualifying_cost = Column(Numeric(18, 2), nullable=False, default=0)
    qualifying_ratio_pct = Column(Numeric(10, 4), nullable=False, default=0)
    missing_evidence_count = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False)  # eligible, at_risk, non_compliant
    estimated_credit_amount = Column(Numeric(18, 2), nullable=False, default=0)
    case_id = Column(String(36), nullable=True)
    reasons = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class ESGMetric(Base):
    """CSRD/ESG metric registry used to evaluate disclosure readiness."""

    __tablename__ = "esg_metrics"
    __table_args__ = (
        Index("idx_esg_metric_tenant_status", "tenant_id", "status"),
        Index("idx_esg_metric_tenant_code", "tenant_id", "metric_code"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    metric_code = Column(String(64), nullable=False)
    metric_name = Column(String(255), nullable=False)
    pillar = Column(String(1), nullable=False)  # E, S, G
    reporting_frequency = Column(String(32), nullable=False, default="quarterly")
    required = Column(Boolean, nullable=False, default=True)
    owner = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class ESGCSRDSubmission(Base):
    """One metric submission/result in a CSRD assessment run."""

    __tablename__ = "esg_csrd_submissions"
    __table_args__ = (
        Index("idx_esg_sub_tenant_batch", "tenant_id", "assessment_batch_id"),
        Index("idx_esg_sub_tenant_status_created", "tenant_id", "status", "created_at"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    assessment_batch_id = Column(String(36), nullable=False)
    metric_id = Column(String(36), nullable=True)
    metric_code = Column(String(64), nullable=False)
    reported_value = Column(Text, nullable=True)
    reported_at = Column(DateTime(timezone=True), nullable=True)
    evidence_refs = Column(JSONB, nullable=False, default=list)
    assurance_level = Column(String(32), nullable=True)
    status = Column(String(32), nullable=False)  # compliant, stale, missing_required, not_required
    reason = Column(Text, nullable=False, default="")
    case_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class SupplierProfile(Base):
    """Supplier master record for financial health monitoring."""

    __tablename__ = "supplier_profiles"
    __table_args__ = (
        Index("idx_supplier_profile_tenant_status", "tenant_id", "status"),
        Index("idx_supplier_profile_tenant_name", "tenant_id", "supplier_name"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    supplier_name = Column(String(255), nullable=False)
    country = Column(String(64), nullable=True)
    criticality = Column(String(32), nullable=False, default="medium")
    owner = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class SupplierRiskAssessment(Base):
    """Supplier risk signal evaluation row."""

    __tablename__ = "supplier_risk_assessments"
    __table_args__ = (
        Index("idx_supplier_risk_tenant_batch", "tenant_id", "assessment_batch_id"),
        Index("idx_supplier_risk_tenant_status_created", "tenant_id", "status", "created_at"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    assessment_batch_id = Column(String(36), nullable=False)
    supplier_id = Column(String(36), nullable=True)
    supplier_name = Column(String(255), nullable=False)
    probability_default_pct = Column(Numeric(8, 3), nullable=False, default=0)
    payment_delay_days = Column(Integer, nullable=False, default=0)
    watchlist_hit = Column(Boolean, nullable=False, default=False)
    covenant_breach_signal = Column(Boolean, nullable=False, default=False)
    source = Column(String(128), nullable=True)
    risk_score = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False)  # stable, warning, critical
    reasons = Column(JSONB, nullable=False, default=list)
    case_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class HSIncident(Base):
    """Health & safety incident record used for near-miss and RIDDOR controls."""

    __tablename__ = "hs_incidents"
    __table_args__ = (
        Index("idx_hs_incident_tenant_type_date", "tenant_id", "incident_type", "occurred_at"),
        Index("idx_hs_incident_tenant_status", "tenant_id", "status"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    incident_ref = Column(String(64), nullable=False)
    site = Column(String(128), nullable=False)
    incident_type = Column(String(64), nullable=False)
    severity = Column(String(32), nullable=False, default="medium")
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    lost_time_days = Column(Integer, nullable=False, default=0)
    affected_people = Column(Integer, nullable=False, default=1)
    narrative = Column(Text, nullable=True)
    corrective_actions = Column(JSONB, nullable=False, default=list)
    reported_to_authority_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="open")
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class HSRiddorAssessment(Base):
    """Assessment output for RIDDOR reporting obligations."""

    __tablename__ = "hs_riddor_assessments"
    __table_args__ = (
        Index("idx_hs_riddor_tenant_incident", "tenant_id", "incident_id"),
        Index("idx_hs_riddor_tenant_status_created", "tenant_id", "status", "created_at"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    incident_id = Column(String(36), nullable=False)
    reportable = Column(Boolean, nullable=False, default=False)
    status = Column(String(32), nullable=False)  # not_reportable, pending_report, due_soon, overdue, reported_on_time, reported_late
    deadline_at = Column(DateTime(timezone=True), nullable=True)
    days_until_deadline = Column(Integer, nullable=True)
    reasons = Column(JSONB, nullable=False, default=list)
    case_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class CompetitorProfile(Base):
    """Tracked competitor baseline metadata."""

    __tablename__ = "competitor_profiles"
    __table_args__ = (
        Index("idx_competitor_profile_tenant_status", "tenant_id", "status"),
        Index("idx_competitor_profile_tenant_name", "tenant_id", "competitor_name"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    competitor_name = Column(String(255), nullable=False)
    segment = Column(String(128), nullable=True)
    strategic_priority = Column(String(32), nullable=False, default="medium")
    owner = Column(String(128), nullable=True)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class CompetitorSignalAssessment(Base):
    """Strategic signal scoring output for competitor monitoring."""

    __tablename__ = "competitor_signal_assessments"
    __table_args__ = (
        Index("idx_comp_signal_tenant_batch", "tenant_id", "assessment_batch_id"),
        Index("idx_comp_signal_tenant_status_created", "tenant_id", "status", "created_at"),
        {"schema": "public"},
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), nullable=False)
    assessment_batch_id = Column(String(36), nullable=False)
    competitor_id = Column(String(36), nullable=True)
    competitor_name = Column(String(255), nullable=False)
    signal_type = Column(String(64), nullable=False)
    signal_strength = Column(Integer, nullable=False, default=0)
    source_confidence_pct = Column(Numeric(8, 3), nullable=False, default=0)
    revenue_impact_pct = Column(Numeric(8, 3), nullable=False, default=0)
    observed_at = Column(DateTime(timezone=True), nullable=False)
    summary = Column(Text, nullable=True)
    priority_score = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False)  # tracking, warning, critical
    reasons = Column(JSONB, nullable=False, default=list)
    case_id = Column(String(36), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
