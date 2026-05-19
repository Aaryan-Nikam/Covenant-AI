"""Unit tests for compliance operations risk scoring."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from engine.compliance.schemas import (
    AMLSignalIngestRequest,
    CompetitorSignalObservation,
    ESGDisclosureObservation,
    SupplierRiskObservation,
)
from engine.compliance.service import (
    assess_competitor_signal,
    assess_ropa_activity,
    assess_hs_riddor,
    assess_supplier_risk,
    evaluate_esg_metric_observation,
    evaluate_covenant_value,
    evaluate_gdpr_retention_observation,
    evaluate_rd_tax_project,
    evaluate_sla_value,
    estimate_sla_credit_amount,
    score_aml_signal,
)


def test_score_aml_signal_caps_at_100_and_flags_high_risk():
    request = AMLSignalIngestRequest(
        subject_id="cust_001",
        amount=12500,
        currency="GBP",
        country_from="GB",
        country_to="IR",
        channel="cash",
        pep_hit=True,
        sanction_hit=True,
        unusual_pattern=True,
        new_customer=True,
    )

    result = score_aml_signal(request)

    assert result.score == 100
    assert "high_value_transaction" in result.flags
    assert "high_risk_jurisdiction" in result.flags
    assert "cash_channel" in result.flags
    assert "pep_match" in result.flags
    assert "sanctions_match" in result.flags
    assert "unusual_pattern" in result.flags


def test_score_aml_signal_medium_case_without_escalation_profile():
    request = AMLSignalIngestRequest(
        subject_id="cust_002",
        amount=5500,
        currency="GBP",
        country_from="GB",
        country_to="GB",
        channel="bank_transfer",
        pep_hit=False,
        sanction_hit=False,
        unusual_pattern=False,
        new_customer=True,
    )

    result = score_aml_signal(request)

    assert result.score == 35
    assert "elevated_transaction_value" in result.flags
    assert "new_customer_large_transaction" in result.flags


def test_evaluate_covenant_value_breached_for_upper_bound():
    result = evaluate_covenant_value(
        metric_value=Decimal("3.80"),
        comparator="<=",
        threshold=Decimal("3.50"),
        warning_buffer_pct=Decimal("10"),
    )
    assert result.status == "breached"
    assert result.distance_pct is not None
    assert float(result.distance_pct) > 0


def test_evaluate_covenant_value_at_risk_near_threshold():
    result = evaluate_covenant_value(
        metric_value=Decimal("3.45"),
        comparator="<=",
        threshold=Decimal("3.50"),
        warning_buffer_pct=Decimal("2"),
    )
    assert result.status == "at_risk"


def test_evaluate_covenant_value_compliant_outside_warning_band():
    result = evaluate_covenant_value(
        metric_value=Decimal("2.80"),
        comparator="<=",
        threshold=Decimal("3.50"),
        warning_buffer_pct=Decimal("5"),
    )
    assert result.status == "compliant"


def test_evaluate_gdpr_retention_observation_breach_when_limit_exceeded():
    result = evaluate_gdpr_retention_observation(
        oldest_record_age_days=460,
        retention_days=365,
        warning_buffer_days=30,
    )
    assert result.status == "breach"
    assert result.excess_days == 95


def test_evaluate_gdpr_retention_observation_no_policy_when_missing_policy():
    result = evaluate_gdpr_retention_observation(
        oldest_record_age_days=100,
        retention_days=None,
        warning_buffer_days=0,
    )
    assert result.status == "no_policy"
    assert result.excess_days is None


def test_assess_ropa_activity_critical_for_missing_basis_and_overdue_review():
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    result = assess_ropa_activity(
        purpose="Fraud monitoring",
        lawful_basis="",
        data_categories=["transaction_data"],
        next_review_due_at=now - timedelta(days=2),
        due_soon_days=30,
        now=now,
    )
    assert result.status == "critical"
    assert "missing_lawful_basis" in result.reasons
    assert "review_overdue" in result.reasons


def test_assess_ropa_activity_warning_for_due_soon_review():
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    result = assess_ropa_activity(
        purpose="Customer support operations",
        lawful_basis="legitimate_interest",
        data_categories=["customer_profile"],
        next_review_due_at=now + timedelta(days=10),
        due_soon_days=30,
        now=now,
    )
    assert result.status == "warning"
    assert "review_due_soon" in result.reasons


def test_evaluate_sla_value_breached_for_response_time_target():
    result = evaluate_sla_value(
        observed_value=Decimal("120"),
        comparator="<=",
        target_value=Decimal("90"),
        warning_buffer_pct=Decimal("10"),
    )
    assert result.status == "breached"
    assert result.distance_pct is not None


def test_evaluate_sla_value_at_risk_near_target():
    result = evaluate_sla_value(
        observed_value=Decimal("88"),
        comparator="<=",
        target_value=Decimal("90"),
        warning_buffer_pct=Decimal("5"),
    )
    assert result.status == "at_risk"


def test_estimate_sla_credit_amount_caps_to_max_credit_pct():
    amount = estimate_sla_credit_amount(
        status="breached",
        monthly_contract_value=Decimal("50000"),
        credit_rate_pct=Decimal("5"),
        max_credit_pct=Decimal("12"),
        distance_pct=Decimal("40"),
    )
    assert amount == Decimal("6000.00")


def test_estimate_sla_credit_amount_zero_for_non_breach():
    amount = estimate_sla_credit_amount(
        status="at_risk",
        monthly_contract_value=Decimal("50000"),
        credit_rate_pct=Decimal("5"),
        max_credit_pct=Decimal("12"),
        distance_pct=Decimal("2"),
    )
    assert amount == Decimal("0.00")


def test_evaluate_rd_tax_project_non_compliant_when_missing_evidence():
    result = evaluate_rd_tax_project(
        qualifying_cost=Decimal("65000"),
        total_cost=Decimal("100000"),
        missing_evidence_count=2,
        min_qualifying_ratio_pct=Decimal("60"),
        credit_rate_pct=Decimal("13"),
    )
    assert result.status == "non_compliant"
    assert "missing_evidence" in result.reasons


def test_evaluate_rd_tax_project_eligible_when_ratio_healthy():
    result = evaluate_rd_tax_project(
        qualifying_cost=Decimal("78000"),
        total_cost=Decimal("100000"),
        missing_evidence_count=0,
        min_qualifying_ratio_pct=Decimal("60"),
        credit_rate_pct=Decimal("13"),
    )
    assert result.status == "eligible"
    assert result.estimated_credit_amount == Decimal("10140.00")


def test_evaluate_esg_metric_observation_detects_missing_required():
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    result = evaluate_esg_metric_observation(
        required=True,
        observation=None,
        stale_after_days=60,
        now=now,
    )
    assert result.status == "missing_required"


def test_evaluate_esg_metric_observation_marks_stale_submission():
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    observation = ESGDisclosureObservation(
        metric_code="E1-1",
        reported_value="23.4",
        reported_at=now - timedelta(days=90),
        evidence_refs=["evidence://source-1"],
    )
    result = evaluate_esg_metric_observation(
        required=True,
        observation=observation,
        stale_after_days=60,
        now=now,
    )
    assert result.status == "stale"


def test_assess_supplier_risk_critical_with_watchlist_and_high_pd():
    observation = SupplierRiskObservation(
        supplier_name="Acme Metals",
        probability_default_pct=48,
        payment_delay_days=65,
        watchlist_hit=True,
        covenant_breach_signal=True,
    )
    result = assess_supplier_risk(observation)
    assert result.status == "critical"
    assert result.risk_score >= 70


def test_assess_hs_riddor_overdue_when_deadline_missed():
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    result = assess_hs_riddor(
        incident_type="dangerous_occurrence",
        severity="critical",
        lost_time_days=0,
        occurred_at=now - timedelta(days=12),
        reported_to_authority_at=None,
        due_soon_days=3,
        now=now,
    )
    assert result.reportable is True
    assert result.status == "overdue"


def test_assess_competitor_signal_critical_for_high_impact_signal():
    observation = CompetitorSignalObservation(
        competitor_name="FastRival",
        signal_type="pricing_cut",
        signal_strength=88,
        source_confidence_pct=82,
        revenue_impact_pct=55,
    )
    result = assess_competitor_signal(observation)
    assert result.status == "critical"
    assert result.priority_score >= 75
