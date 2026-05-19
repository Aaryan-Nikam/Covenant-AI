"""Compliance operations API router."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from engine.auth.models import Tenant
from engine.compliance.schemas import (
    AMLDashboardResponse,
    AMLSignalIngestRequest,
    AMLSignalIngestResponse,
    CompetitorProfileResponse,
    CompetitorProfilesResponse,
    CompetitorSignalsDashboardResponse,
    CreateCompetitorProfileRequest,
    CreateESGMetricRequest,
    CreateHSIncidentRequest,
    CreateRDTaxActivityRequest,
    CreateSupplierProfileRequest,
    ComplianceCasesResponse,
    ComplianceCaseSummary,
    CovenantDashboardResponse,
    CovenantsResponse,
    CovenantResponse,
    ESGCSRDDashboardResponse,
    ESGMetricsResponse,
    ESGMetricResponse,
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
    GDPRRetentionPoliciesResponse,
    GDPRRetentionPolicyResponse,
    HSIncidentResponse,
    HSIncidentsResponse,
    HSRiddorDashboardResponse,
    MonitorROPARequest,
    MonitorROPAResponse,
    MonitorHSRiddorRequest,
    MonitorHSRiddorResponse,
    ObligationResponse,
    ObligationsResponse,
    RDTaxActivitiesResponse,
    RDTaxActivityResponse,
    RDTaxDashboardResponse,
    ROPAActivitiesResponse,
    ROPAActivityResponse,
    ROPADashboardResponse,
    SLAContractResponse,
    SLAContractsResponse,
    SLADashboardResponse,
    SARReportResponse,
    SARSubmitRequest,
    SARDraftRequest,
    SupplierProfilesResponse,
    SupplierProfileResponse,
    SupplierRiskDashboardResponse,
)
from engine.compliance.service import ComplianceOpsService
from engine.dependencies import get_db, verify_api_key

router = APIRouter(prefix="/v1/compliance", tags=["compliance"])


@router.post("/aml/signals", response_model=AMLSignalIngestResponse)
async def ingest_aml_signal(
    body: AMLSignalIngestRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.ingest_aml_signal(tenant.id, body)


@router.get("/aml/cases", response_model=ComplianceCasesResponse)
async def list_aml_cases(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.list_aml_cases(tenant.id, status, limit, offset)


@router.get("/aml/cases/{case_id}", response_model=ComplianceCaseSummary)
async def get_aml_case(
    case_id: str,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    case = await service.get_case(tenant.id, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.post("/aml/cases/{case_id}/sar-draft", response_model=SARReportResponse)
async def save_sar_draft(
    case_id: str,
    body: SARDraftRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    report = await service.upsert_sar_draft(tenant.id, case_id, body)
    if report is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return report


@router.post("/aml/cases/{case_id}/submit", response_model=SARReportResponse)
async def submit_sar(
    case_id: str,
    body: SARSubmitRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    report = await service.submit_sar(tenant.id, case_id, body.submission_reference)
    if report is None:
        raise HTTPException(status_code=404, detail="SAR draft not found for case")
    return report


@router.get("/aml/dashboard", response_model=AMLDashboardResponse)
async def aml_dashboard(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.aml_dashboard(tenant.id)


@router.post("/obligations", response_model=ObligationResponse)
async def create_obligation(
    body: CreateObligationRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.create_obligation(tenant.id, body)


@router.get("/obligations", response_model=ObligationsResponse)
async def list_obligations(
    domain: str | None = Query(default=None),
    status: str | None = Query(default=None),
    due_before: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.list_obligations(
        tenant.id, domain, status, due_before, limit, offset
    )


@router.post("/covenants", response_model=CovenantResponse)
async def create_covenant(
    body: CreateCovenantRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    try:
        return await service.create_covenant(tenant.id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/covenants", response_model=CovenantsResponse)
async def list_covenants(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.list_covenants(tenant.id, status, limit, offset)


@router.post("/covenants/evaluate", response_model=EvaluateCovenantsResponse)
async def evaluate_covenants(
    body: EvaluateCovenantsRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.evaluate_covenants(tenant.id, body)


@router.get("/covenants/dashboard", response_model=CovenantDashboardResponse)
async def covenant_dashboard(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.covenant_dashboard(tenant.id)


@router.post(
    "/sla/contracts",
    response_model=SLAContractResponse,
)
async def create_sla_contract(
    body: CreateSLAContractRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    try:
        return await service.create_sla_contract(tenant.id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/sla/contracts",
    response_model=SLAContractsResponse,
)
async def list_sla_contracts(
    status: str | None = Query(default=None),
    service_name: str | None = Query(default=None),
    metric_name: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.list_sla_contracts(
        tenant.id,
        status,
        service_name,
        metric_name,
        limit,
        offset,
    )


@router.post(
    "/sla/evaluate",
    response_model=EvaluateSLAResponse,
)
async def evaluate_sla(
    body: EvaluateSLARequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.evaluate_sla(tenant.id, body)


@router.get(
    "/sla/dashboard",
    response_model=SLADashboardResponse,
)
async def sla_dashboard(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.sla_dashboard(tenant.id)


@router.post(
    "/gdpr/retention-policies",
    response_model=GDPRRetentionPolicyResponse,
)
async def create_gdpr_retention_policy(
    body: CreateGDPRRetentionPolicyRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.create_gdpr_retention_policy(tenant.id, body)


@router.get(
    "/gdpr/retention-policies",
    response_model=GDPRRetentionPoliciesResponse,
)
async def list_gdpr_retention_policies(
    status: str | None = Query(default=None),
    system_name: str | None = Query(default=None),
    data_category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.list_gdpr_retention_policies(
        tenant.id,
        status,
        system_name,
        data_category,
        limit,
        offset,
    )


@router.post(
    "/gdpr/retention/evaluate",
    response_model=EvaluateGDPRRetentionResponse,
)
async def evaluate_gdpr_retention(
    body: EvaluateGDPRRetentionRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.evaluate_gdpr_retention(tenant.id, body)


@router.get(
    "/gdpr/retention/dashboard",
    response_model=GDPRRetentionDashboardResponse,
)
async def gdpr_retention_dashboard(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.gdpr_retention_dashboard(tenant.id)


@router.post(
    "/gdpr/ropa/activities",
    response_model=ROPAActivityResponse,
)
async def create_ropa_activity(
    body: CreateROPAActivityRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.create_ropa_activity(tenant.id, body)


@router.get(
    "/gdpr/ropa/activities",
    response_model=ROPAActivitiesResponse,
)
async def list_ropa_activities(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.list_ropa_activities(tenant.id, status, limit, offset)


@router.post(
    "/gdpr/ropa/monitor",
    response_model=MonitorROPAResponse,
)
async def monitor_ropa(
    body: MonitorROPARequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.monitor_ropa(tenant.id, body)


@router.get(
    "/gdpr/ropa/dashboard",
    response_model=ROPADashboardResponse,
)
async def ropa_dashboard(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.ropa_dashboard(tenant.id)


@router.post(
    "/rd-tax/activities",
    response_model=RDTaxActivityResponse,
)
async def create_rd_tax_activity(
    body: CreateRDTaxActivityRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.create_rd_tax_activity(tenant.id, body)


@router.get(
    "/rd-tax/activities",
    response_model=RDTaxActivitiesResponse,
)
async def list_rd_tax_activities(
    status: str | None = Query(default=None),
    project_code: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.list_rd_tax_activities(
        tenant.id,
        status,
        project_code,
        limit,
        offset,
    )


@router.post(
    "/rd-tax/evaluate",
    response_model=EvaluateRDTaxResponse,
)
async def evaluate_rd_tax(
    body: EvaluateRDTaxRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.evaluate_rd_tax(tenant.id, body)


@router.get(
    "/rd-tax/dashboard",
    response_model=RDTaxDashboardResponse,
)
async def rd_tax_dashboard(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.rd_tax_dashboard(tenant.id)


@router.post(
    "/esg/metrics",
    response_model=ESGMetricResponse,
)
async def create_esg_metric(
    body: CreateESGMetricRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    try:
        return await service.create_esg_metric(tenant.id, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/esg/metrics",
    response_model=ESGMetricsResponse,
)
async def list_esg_metrics(
    status: str | None = Query(default=None),
    pillar: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.list_esg_metrics(
        tenant.id,
        status,
        pillar,
        limit,
        offset,
    )


@router.post(
    "/esg/csrd/evaluate",
    response_model=EvaluateESGCSRDResponse,
)
async def evaluate_esg_csrd(
    body: EvaluateESGCSRDRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.evaluate_esg_csrd(tenant.id, body)


@router.get(
    "/esg/csrd/dashboard",
    response_model=ESGCSRDDashboardResponse,
)
async def esg_csrd_dashboard(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.esg_csrd_dashboard(tenant.id)


@router.post(
    "/supplier/profiles",
    response_model=SupplierProfileResponse,
)
async def create_supplier_profile(
    body: CreateSupplierProfileRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.create_supplier_profile(tenant.id, body)


@router.get(
    "/supplier/profiles",
    response_model=SupplierProfilesResponse,
)
async def list_supplier_profiles(
    status: str | None = Query(default=None),
    criticality: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.list_supplier_profiles(
        tenant.id,
        status,
        criticality,
        limit,
        offset,
    )


@router.post(
    "/supplier/financial-health/evaluate",
    response_model=EvaluateSupplierRiskResponse,
)
async def evaluate_supplier_risk(
    body: EvaluateSupplierRiskRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.evaluate_supplier_risk(tenant.id, body)


@router.get(
    "/supplier/financial-health/dashboard",
    response_model=SupplierRiskDashboardResponse,
)
async def supplier_risk_dashboard(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.supplier_risk_dashboard(tenant.id)


@router.post(
    "/hs/incidents",
    response_model=HSIncidentResponse,
)
async def create_hs_incident(
    body: CreateHSIncidentRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.create_hs_incident(tenant.id, body)


@router.get(
    "/hs/incidents",
    response_model=HSIncidentsResponse,
)
async def list_hs_incidents(
    status: str | None = Query(default=None),
    incident_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.list_hs_incidents(
        tenant.id,
        status,
        incident_type,
        limit,
        offset,
    )


@router.post(
    "/hs/riddor/monitor",
    response_model=MonitorHSRiddorResponse,
)
async def monitor_hs_riddor(
    body: MonitorHSRiddorRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.monitor_hs_riddor(tenant.id, body)


@router.get(
    "/hs/riddor/dashboard",
    response_model=HSRiddorDashboardResponse,
)
async def hs_riddor_dashboard(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.hs_riddor_dashboard(tenant.id)


@router.post(
    "/competitor/profiles",
    response_model=CompetitorProfileResponse,
)
async def create_competitor_profile(
    body: CreateCompetitorProfileRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.create_competitor_profile(tenant.id, body)


@router.get(
    "/competitor/profiles",
    response_model=CompetitorProfilesResponse,
)
async def list_competitor_profiles(
    status: str | None = Query(default=None),
    strategic_priority: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.list_competitor_profiles(
        tenant.id,
        status,
        strategic_priority,
        limit,
        offset,
    )


@router.post(
    "/competitor/signals/evaluate",
    response_model=EvaluateCompetitorSignalsResponse,
)
async def evaluate_competitor_signals(
    body: EvaluateCompetitorSignalsRequest,
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.evaluate_competitor_signals(tenant.id, body)


@router.get(
    "/competitor/signals/dashboard",
    response_model=CompetitorSignalsDashboardResponse,
)
async def competitor_signals_dashboard(
    tenant: Tenant = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    service = ComplianceOpsService(db)
    return await service.competitor_signals_dashboard(tenant.id)
