import React, { useEffect, useMemo, useState } from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./FunctionsAndTools.css";
import {
  createCovenant,
  createGdprRetentionPolicy,
  createRopaActivity,
  createSlaContract,
  evaluateCovenants,
  evaluateGdprRetention,
  evaluateSla,
  fetchAmlDashboard,
  fetchCovenantDashboard,
  fetchFunctionsOverview,
  fetchGdprRetentionDashboard,
  fetchProductMap,
  fetchRopaDashboard,
  fetchSlaDashboard,
  ingestAmlSignal,
  listAmlCases,
  listCovenants,
  listGdprRetentionPolicies,
  listRopaActivities,
  listSlaContracts,
  monitorRopa,
  saveSarDraft,
  submitSar,
  type FunctionOverviewModule,
  type FunctionsOverviewResponse,
  type ProductMapResponse,
} from "../../../lib/api";

const FALLBACK_OVERVIEW: FunctionsOverviewResponse = {
  generated_at: "2026-05-06T00:00:00Z",
  implemented_count: 4,
  live_count: 4,
  planned_count: 5,
  implemented_modules: [
    {
      id: "aml_sar",
      name: "Audit trails / AML & SAR Workflow",
      status: "implemented",
      health: "live",
      metrics: {
        open_cases: 8,
        submitted_cases: 12,
        high_risk_signals_7d: 21,
      },
      routes: [
        "/v1/compliance/aml/signals",
        "/v1/compliance/aml/cases",
        "/v1/compliance/aml/dashboard",
      ],
      errors: [],
    },
    {
      id: "financial_covenants",
      name: "Financial Covenant & Debt Obligation Monitoring",
      status: "implemented",
      health: "live",
      metrics: {
        active_covenants: 11,
        breached_30d: 2,
        at_risk_30d: 4,
      },
      routes: ["/v1/compliance/covenants", "/v1/compliance/covenants/dashboard"],
      errors: [],
    },
    {
      id: "sla_credit_leakage",
      name: "SLA Breach + Credit Leakage Monitoring",
      status: "implemented",
      health: "live",
      metrics: {
        active_contracts: 14,
        breached_30d: 5,
        estimated_credits_30d: 18450,
      },
      routes: ["/v1/compliance/sla/contracts", "/v1/compliance/sla/dashboard"],
      errors: [],
    },
    {
      id: "gdpr_retention_ropa",
      name: "GDPR Data Retention & ROPA Monitoring",
      status: "implemented",
      health: "live",
      metrics: {
        retention: { breaches_30d: 3 },
        ropa: { overdue_reviews: 6, open_gdpr_cases: 4 },
      },
      routes: [
        "/v1/compliance/gdpr/retention/dashboard",
        "/v1/compliance/gdpr/ropa/dashboard",
      ],
      errors: [],
    },
  ],
  planned_modules: [
    {
      id: "rd_tax_credit_tracking",
      name: "R&D Tax Credit Activity Tracking",
      status: "planned",
      priority: "high",
      revenue_impact: "high",
    },
    {
      id: "esg_csrd",
      name: "ESG Data Collection & CSRD Compliance",
      status: "planned",
      priority: "medium",
      revenue_impact: "medium",
    },
    {
      id: "supplier_insolvency_monitoring",
      name: "Supplier Financial Health & Insolvency Monitoring",
      status: "planned",
      priority: "high",
      revenue_impact: "high",
    },
    {
      id: "hs_riddor_monitoring",
      name: "H&S Near-Miss & RIDDOR Compliance Monitoring",
      status: "planned",
      priority: "medium",
      revenue_impact: "medium",
    },
    {
      id: "competitor_signal_monitoring",
      name: "Competitor Intelligence & Strategic Signal Monitoring",
      status: "planned",
      priority: "medium",
      revenue_impact: "medium",
    },
  ],
};

const FALLBACK_MAP: ProductMapResponse = {
  generated_at: "2026-05-06T00:00:00Z",
  core_compliance_layer: {
    name: "Core Compliance Layer",
    description: "Compliance infrastructure layer.",
    kpis: {
      tenant_id: "demo_tenant",
      total_requests: 48291,
      total_blocked: 214,
      requests_24h: 2187,
      active_vault_tokens: 3847,
      avg_latency_ms: 138.0,
      block_rate: 0.4,
      active_rulesets_count: 3,
    },
    rulesets: {
      active_count: 3,
      active_rulesets: ["pci_dss", "hipaa", "gdpr"],
      available_count: 4,
      available_rulesets: ["gdpr", "hipaa", "pci_dss", "soc2"],
    },
    features: [],
  },
  operations_function_suite: {
    name: "Operations Functions",
    description: "High-ticket business workflows.",
    implemented_count: 4,
    planned_count: 5,
    functions: [
      ...FALLBACK_OVERVIEW.implemented_modules.map((m) => ({
        id: m.id,
        name: m.name,
        status: "implemented" as const,
        priority: "critical" as const,
        revenue_impact: "high" as const,
      })),
      ...FALLBACK_OVERVIEW.planned_modules,
    ],
  },
  management_capabilities: [
    {
      id: "control_plane",
      name: "Unified Control Plane",
      description: "Tenant-aware module status and governance.",
      must_have_features: ["module enable/disable", "tenant scoping", "versioned config"],
    },
    {
      id: "case_workflow",
      name: "Case & Escalation Workflow",
      description: "Cross-function investigations and timelines.",
      must_have_features: ["status transitions", "assignment", "escalation ladders"],
    },
    {
      id: "evidence_reporting",
      name: "Evidence & Reporting",
      description: "Regulator-ready exports and executive summaries.",
      must_have_features: ["tamper-evident logs", "CSV/PDF exports", "periodic reporting"],
    },
  ],
};

type WorkbenchModuleId =
  | "aml_sar"
  | "financial_covenants"
  | "sla_credit_leakage"
  | "gdpr_retention_ropa";

type WorkbenchOperationId =
  | "aml_ingest_signal"
  | "aml_list_cases"
  | "aml_save_sar_draft"
  | "aml_submit_sar"
  | "aml_dashboard"
  | "covenant_create"
  | "covenant_list"
  | "covenant_evaluate"
  | "covenant_dashboard"
  | "sla_create"
  | "sla_list"
  | "sla_evaluate"
  | "sla_dashboard"
  | "gdpr_create_policy"
  | "gdpr_list_policies"
  | "gdpr_evaluate_retention"
  | "gdpr_create_ropa_activity"
  | "gdpr_list_ropa_activities"
  | "gdpr_monitor_ropa"
  | "gdpr_dashboard_retention"
  | "gdpr_dashboard_ropa";

interface WorkbenchOperationDefinition {
  id: WorkbenchOperationId;
  label: string;
  description: string;
  method: "GET" | "POST";
  route: string;
  requiresCaseId?: boolean;
}

const WORKBENCH_OPERATIONS: Record<WorkbenchModuleId, WorkbenchOperationDefinition[]> = {
  aml_sar: [
    {
      id: "aml_ingest_signal",
      label: "Ingest AML Signal",
      description: "Push a transaction/customer risk signal and auto-open escalated cases.",
      method: "POST",
      route: "/v1/compliance/aml/signals",
    },
    {
      id: "aml_list_cases",
      label: "List AML Cases",
      description: "Fetch current AML/SAR investigation cases for triage.",
      method: "GET",
      route: "/v1/compliance/aml/cases",
    },
    {
      id: "aml_save_sar_draft",
      label: "Save SAR Draft",
      description: "Save draft narrative/evidence for a selected AML case.",
      method: "POST",
      route: "/v1/compliance/aml/cases/{case_id}/sar-draft",
      requiresCaseId: true,
    },
    {
      id: "aml_submit_sar",
      label: "Submit SAR",
      description: "Mark a SAR draft submitted with regulator reference.",
      method: "POST",
      route: "/v1/compliance/aml/cases/{case_id}/submit",
      requiresCaseId: true,
    },
    {
      id: "aml_dashboard",
      label: "AML Dashboard",
      description: "Live AML module metrics.",
      method: "GET",
      route: "/v1/compliance/aml/dashboard",
    },
  ],
  financial_covenants: [
    {
      id: "covenant_create",
      label: "Create Covenant",
      description: "Define covenant guardrails and ownership.",
      method: "POST",
      route: "/v1/compliance/covenants",
    },
    {
      id: "covenant_list",
      label: "List Covenants",
      description: "List covenant definitions by status.",
      method: "GET",
      route: "/v1/compliance/covenants",
    },
    {
      id: "covenant_evaluate",
      label: "Evaluate Snapshot",
      description: "Evaluate current metrics and open risk cases.",
      method: "POST",
      route: "/v1/compliance/covenants/evaluate",
    },
    {
      id: "covenant_dashboard",
      label: "Covenant Dashboard",
      description: "Live covenant health and breach trend.",
      method: "GET",
      route: "/v1/compliance/covenants/dashboard",
    },
  ],
  sla_credit_leakage: [
    {
      id: "sla_create",
      label: "Create SLA Contract",
      description: "Register SLA terms, penalty rates, and thresholds.",
      method: "POST",
      route: "/v1/compliance/sla/contracts",
    },
    {
      id: "sla_list",
      label: "List SLA Contracts",
      description: "Review active SLA definitions.",
      method: "GET",
      route: "/v1/compliance/sla/contracts",
    },
    {
      id: "sla_evaluate",
      label: "Evaluate SLA Observations",
      description: "Run observed delivery metrics against contracts.",
      method: "POST",
      route: "/v1/compliance/sla/evaluate",
    },
    {
      id: "sla_dashboard",
      label: "SLA Dashboard",
      description: "Credit leakage and SLA risk metrics.",
      method: "GET",
      route: "/v1/compliance/sla/dashboard",
    },
  ],
  gdpr_retention_ropa: [
    {
      id: "gdpr_create_policy",
      label: "Create Retention Policy",
      description: "Add retention policy guardrails by system and data category.",
      method: "POST",
      route: "/v1/compliance/gdpr/retention-policies",
    },
    {
      id: "gdpr_list_policies",
      label: "List Retention Policies",
      description: "Inspect configured retention controls.",
      method: "GET",
      route: "/v1/compliance/gdpr/retention-policies",
    },
    {
      id: "gdpr_evaluate_retention",
      label: "Evaluate Retention Observations",
      description: "Run retention scan findings and auto-open GDPR cases.",
      method: "POST",
      route: "/v1/compliance/gdpr/retention/evaluate",
    },
    {
      id: "gdpr_create_ropa_activity",
      label: "Create ROPA Activity",
      description: "Register processing activity metadata for Article 30 coverage.",
      method: "POST",
      route: "/v1/compliance/gdpr/ropa/activities",
    },
    {
      id: "gdpr_list_ropa_activities",
      label: "List ROPA Activities",
      description: "Fetch recorded activities and review cadence state.",
      method: "GET",
      route: "/v1/compliance/gdpr/ropa/activities",
    },
    {
      id: "gdpr_monitor_ropa",
      label: "Monitor ROPA Health",
      description: "Run monitor job for due reviews and missing legal basis.",
      method: "POST",
      route: "/v1/compliance/gdpr/ropa/monitor",
    },
    {
      id: "gdpr_dashboard_retention",
      label: "Retention Dashboard",
      description: "Live retention breach / no-policy metrics.",
      method: "GET",
      route: "/v1/compliance/gdpr/retention/dashboard",
    },
    {
      id: "gdpr_dashboard_ropa",
      label: "ROPA Dashboard",
      description: "Live ROPA coverage and review health metrics.",
      method: "GET",
      route: "/v1/compliance/gdpr/ropa/dashboard",
    },
  ],
};

const WORKBENCH_TEMPLATES: Record<WorkbenchOperationId, Record<string, unknown>> = {
  aml_ingest_signal: {
    subject_id: "acct-8842",
    counterparty: "ALFA TRADING LLC",
    amount: 12500,
    currency: "GBP",
    country_from: "GB",
    country_to: "RU",
    channel: "cash",
    description: "Multiple rapid transfers",
    pep_hit: false,
    sanction_hit: false,
    unusual_pattern: true,
    new_customer: true,
    metadata: { source: "ops_workbench" },
  },
  aml_list_cases: {
    status: "open",
    limit: 20,
    offset: 0,
  },
  aml_save_sar_draft: {
    suspicion_summary: "Pattern indicates possible layering activity.",
    narrative: "Transactions appear structured over 48h with high-risk corridor exposure.",
    jurisdiction: "UK_NCA",
    report_payload: { prepared_by: "compliance_ops" },
  },
  aml_submit_sar: {
    submission_reference: "NCA-REF-2026-001",
  },
  aml_dashboard: {},
  covenant_create: {
    name: "Net Leverage Ratio",
    metric_name: "net_leverage_ratio",
    comparator: "<=",
    threshold: 3.5,
    warning_buffer_pct: 10,
    frequency: "monthly",
    owner: "finance-controller",
  },
  covenant_list: {
    status: "active",
    limit: 50,
    offset: 0,
  },
  covenant_evaluate: {
    period_end: "2026-05-06T00:00:00Z",
    metrics: {
      net_leverage_ratio: 3.7,
      interest_coverage_ratio: 2.9,
    },
    metadata: { source: "ops_workbench" },
  },
  covenant_dashboard: {},
  sla_create: {
    name: "API Availability SLA",
    service_name: "core-api",
    metric_name: "uptime_pct",
    comparator: ">=",
    target_value: 99.95,
    warning_buffer_pct: 0.5,
    credit_rate_pct: 5,
    max_credit_pct: 25,
    monthly_contract_value: 75000,
    frequency: "monthly",
    owner: "service-delivery",
  },
  sla_list: {
    status: "active",
    limit: 50,
    offset: 0,
  },
  sla_evaluate: {
    observations: [
      {
        service_name: "core-api",
        metric_name: "uptime_pct",
        observed_value: 99.2,
        impacted_requests: 42000,
        metadata: { window: "monthly" },
      },
    ],
    create_cases: true,
    metadata: { source: "ops_workbench" },
  },
  sla_dashboard: {},
  gdpr_create_policy: {
    system_name: "crm",
    data_category: "customer_profile",
    legal_basis: "contract",
    retention_days: 1095,
    warning_buffer_days: 30,
    owner: "dpo",
    source: "manual",
  },
  gdpr_list_policies: {
    status: "active",
    limit: 50,
    offset: 0,
  },
  gdpr_evaluate_retention: {
    observations: [
      {
        system_name: "crm",
        data_category: "customer_profile",
        oldest_record_age_days: 1220,
        record_count: 8300,
      },
    ],
    create_cases: true,
    metadata: { source: "ops_workbench" },
  },
  gdpr_create_ropa_activity: {
    activity_name: "Customer onboarding KYC",
    purpose: "Identity verification and fraud prevention",
    lawful_basis: "legal_obligation",
    data_categories: ["identity", "address", "financial"],
    data_subjects: ["prospects", "customers"],
    recipients: ["compliance-team"],
    transfer_countries: ["GB"],
    source_system: "kyc-platform",
    owner: "dpo",
    next_review_due_at: "2026-12-31T00:00:00Z",
  },
  gdpr_list_ropa_activities: {
    status: "active",
    limit: 50,
    offset: 0,
  },
  gdpr_monitor_ropa: {
    due_soon_days: 30,
    create_cases: true,
  },
  gdpr_dashboard_retention: {},
  gdpr_dashboard_ropa: {},
};

function getHighlights(module: FunctionOverviewModule): Array<{ label: string; value: string }> {
  const metrics = module.metrics as Record<string, unknown>;

  if (module.id === "aml_sar") {
    return [
      { label: "Open Cases", value: String(metrics.open_cases ?? "-") },
      { label: "Submitted", value: String(metrics.submitted_cases ?? "-") },
      { label: "High Risk (7d)", value: String(metrics.high_risk_signals_7d ?? "-") },
    ];
  }

  if (module.id === "financial_covenants") {
    return [
      { label: "Active Covenants", value: String(metrics.active_covenants ?? "-") },
      { label: "Breached (30d)", value: String(metrics.breached_30d ?? "-") },
      { label: "At Risk (30d)", value: String(metrics.at_risk_30d ?? "-") },
    ];
  }

  if (module.id === "sla_credit_leakage") {
    return [
      { label: "Active Contracts", value: String(metrics.active_contracts ?? "-") },
      { label: "Breached (30d)", value: String(metrics.breached_30d ?? "-") },
      { label: "Credits (30d)", value: String(metrics.estimated_credits_30d ?? "-") },
    ];
  }

  if (module.id === "gdpr_retention_ropa") {
    const retention = (metrics.retention || {}) as Record<string, unknown>;
    const ropa = (metrics.ropa || {}) as Record<string, unknown>;
    return [
      { label: "Retention Breaches (30d)", value: String(retention.breaches_30d ?? "-") },
      { label: "ROPA Overdue", value: String(ropa.overdue_reviews ?? "-") },
      { label: "Open GDPR Cases", value: String(ropa.open_gdpr_cases ?? "-") },
    ];
  }

  return [];
}

function formatJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function parsePayload(text: string): Record<string, unknown> {
  if (!text.trim()) return {};
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new Error("Payload must be valid JSON.");
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Payload JSON must be an object.");
  }
  return parsed as Record<string, unknown>;
}

async function runWorkbenchOperation(
  operationId: WorkbenchOperationId,
  payload: Record<string, unknown>,
  caseId: string
): Promise<unknown> {
  switch (operationId) {
    case "aml_ingest_signal":
      return ingestAmlSignal(payload);
    case "aml_list_cases":
      return listAmlCases(payload as { status?: string; limit?: number; offset?: number });
    case "aml_save_sar_draft":
      if (!caseId) throw new Error("case_id is required for SAR draft.");
      return saveSarDraft(caseId, payload as any);
    case "aml_submit_sar":
      if (!caseId) throw new Error("case_id is required for SAR submission.");
      return submitSar(caseId, payload as any);
    case "aml_dashboard":
      return fetchAmlDashboard();

    case "covenant_create":
      return createCovenant(payload as any);
    case "covenant_list":
      return listCovenants(payload as { status?: string; limit?: number; offset?: number });
    case "covenant_evaluate":
      return evaluateCovenants(payload as any);
    case "covenant_dashboard":
      return fetchCovenantDashboard();

    case "sla_create":
      return createSlaContract(payload as any);
    case "sla_list":
      return listSlaContracts(payload as {
        status?: string;
        service_name?: string;
        metric_name?: string;
        limit?: number;
        offset?: number;
      });
    case "sla_evaluate":
      return evaluateSla(payload as any);
    case "sla_dashboard":
      return fetchSlaDashboard();

    case "gdpr_create_policy":
      return createGdprRetentionPolicy(payload as any);
    case "gdpr_list_policies":
      return listGdprRetentionPolicies(payload as {
        status?: string;
        system_name?: string;
        data_category?: string;
        limit?: number;
        offset?: number;
      });
    case "gdpr_evaluate_retention":
      return evaluateGdprRetention(payload as any);
    case "gdpr_create_ropa_activity":
      return createRopaActivity(payload as any);
    case "gdpr_list_ropa_activities":
      return listRopaActivities(payload as { status?: string; limit?: number; offset?: number });
    case "gdpr_monitor_ropa":
      return monitorRopa(payload as any);
    case "gdpr_dashboard_retention":
      return fetchGdprRetentionDashboard();
    case "gdpr_dashboard_ropa":
      return fetchRopaDashboard();
    default:
      throw new Error(`Unsupported operation: ${String(operationId)}`);
  }
}

export function FunctionsAndTools() {
  const [activePage, setActivePage] = useState<any>("functions-tools");
  const [productMap, setProductMap] = useState<ProductMapResponse | null>(null);
  const [overview, setOverview] = useState<FunctionsOverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiLive, setApiLive] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);

  const [activeModule, setActiveModule] = useState<WorkbenchModuleId>("aml_sar");
  const [activeOperationId, setActiveOperationId] = useState<WorkbenchOperationId>("aml_ingest_signal");
  const [caseIdInput, setCaseIdInput] = useState("");
  const [payloadText, setPayloadText] = useState(formatJson(WORKBENCH_TEMPLATES.aml_ingest_signal));
  const [runLoading, setRunLoading] = useState(false);
  const [runError, setRunError] = useState("");
  const [runResult, setRunResult] = useState<unknown>(null);
  const [lastRunMeta, setLastRunMeta] = useState<{
    at: string;
    route: string;
    method: "GET" | "POST";
    operationLabel: string;
  } | null>(null);
  const [recentRuns, setRecentRuns] = useState<Array<{
    at: string;
    operationLabel: string;
    status: "success" | "error";
  }>>([]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [mapResp, overviewResp] = await Promise.all([
          fetchProductMap(),
          fetchFunctionsOverview(),
        ]);
        if (cancelled) return;
        setProductMap(mapResp);
        setOverview(overviewResp);
        setApiLive(true);
      } catch {
        // Fallback mode if backend is unavailable.
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [refreshTick]);

  const map = productMap ?? FALLBACK_MAP;
  const liveOverview = overview ?? FALLBACK_OVERVIEW;

  const moduleStatusMap = useMemo(() => {
    const out: Partial<Record<WorkbenchModuleId, FunctionOverviewModule>> = {};
    for (const module of liveOverview.implemented_modules) {
      if (module.id in WORKBENCH_OPERATIONS) {
        out[module.id as WorkbenchModuleId] = module;
      }
    }
    return out;
  }, [liveOverview.implemented_modules]);

  const availableModuleIds = useMemo(() => {
    const ordered: WorkbenchModuleId[] = [
      "aml_sar",
      "financial_covenants",
      "sla_credit_leakage",
      "gdpr_retention_ropa",
    ];
    return ordered.filter((id) => moduleStatusMap[id]);
  }, [moduleStatusMap]);

  useEffect(() => {
    if (!availableModuleIds.includes(activeModule) && availableModuleIds.length > 0) {
      setActiveModule(availableModuleIds[0]);
    }
  }, [availableModuleIds, activeModule]);

  const operationsForModule = WORKBENCH_OPERATIONS[activeModule] ?? [];
  const activeOperation =
    operationsForModule.find((op) => op.id === activeOperationId) ?? operationsForModule[0] ?? null;

  useEffect(() => {
    if (!activeOperation) return;
    setActiveOperationId(activeOperation.id);
    setPayloadText(formatJson(WORKBENCH_TEMPLATES[activeOperation.id] || {}));
    setRunError("");
    setRunResult(null);
  }, [activeModule]);

  useEffect(() => {
    if (!activeOperation) return;
    setPayloadText(formatJson(WORKBENCH_TEMPLATES[activeOperation.id] || {}));
    setRunError("");
    setRunResult(null);
  }, [activeOperationId]);

  const plannedFunctions = useMemo(() => {
    return map.operations_function_suite.functions.filter((item) => item.status === "planned");
  }, [map]);

  async function executeOperation() {
    if (!activeOperation) return;

    setRunLoading(true);
    setRunError("");

    try {
      const payload = parsePayload(payloadText);
      const result = await runWorkbenchOperation(activeOperation.id, payload, caseIdInput.trim());
      setRunResult(result);

      const now = new Date().toISOString();
      setLastRunMeta({
        at: now,
        route: activeOperation.route,
        method: activeOperation.method,
        operationLabel: activeOperation.label,
      });
      setRecentRuns((current) => [
        { at: now, operationLabel: activeOperation.label, status: "success" },
        ...current,
      ].slice(0, 8));

      setRefreshTick((value) => value + 1);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Operation failed";
      setRunError(message);
      setRecentRuns((current) => [
        {
          at: new Date().toISOString(),
          operationLabel: activeOperation.label,
          status: "error",
        },
        ...current,
      ].slice(0, 8));
    } finally {
      setRunLoading(false);
    }
  }

  function resetPayloadTemplate() {
    if (!activeOperation) return;
    setPayloadText(formatJson(WORKBENCH_TEMPLATES[activeOperation.id] || {}));
    setRunError("");
  }

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">Functions & Tools</div>
          <div className="ip-page-subtitle">
            Pain-driven independent tools and generic function suites.
            {apiLive && (
              <span style={{ marginLeft: 8, fontSize: 11, color: "var(--status-passed-dot)" }}>
                Live
              </span>
            )}
            {!apiLive && !loading && (
              <span style={{ marginLeft: 8, fontSize: 11, color: "var(--text-tertiary)" }}>
                Backend unavailable
              </span>
            )}
          </div>
        </div>
        <div className="ip-page-header-actions">
          <button className="ip-btn-ghost" onClick={() => (window.location.hash = "compliance-layer")}>
            Core Layer
          </button>
        </div>
      </div>

      <div className="ip-content">
        <div className="ip-kpi-row">
          <div className="ip-sheet ip-kpi-card">
            <div className="ip-kpi-label">Implemented Functions</div>
            <div className="ip-kpi-value">{liveOverview.implemented_count}</div>
            <div className="ip-kpi-delta">shipping now</div>
          </div>
          <div className="ip-sheet ip-kpi-card">
            <div className="ip-kpi-label">Live Modules</div>
            <div className="ip-kpi-value">{liveOverview.live_count}</div>
            <div className="ip-kpi-delta">healthy module dashboards</div>
          </div>
          <div className="ip-sheet ip-kpi-card">
            <div className="ip-kpi-label">Planned Functions</div>
            <div className="ip-kpi-value">{liveOverview.planned_count}</div>
            <div className="ip-kpi-delta">next build queue</div>
          </div>
          <div className="ip-sheet ip-kpi-card">
            <div className="ip-kpi-label">Separation Model</div>
            <div className="ip-kpi-value">2 Layers</div>
            <div className="ip-kpi-delta">Core Layer + Function Suite</div>
          </div>
        </div>

        <div className="ip-section-heading" style={{ marginBottom: 12 }}>
          Implemented Functions
        </div>
        <div className="ip-ops-grid">
          {liveOverview.implemented_modules.map((module) => (
            <div key={module.id} className="ip-sheet ip-ops-card">
              <div className="ip-ops-card-head">
                <div style={{ fontWeight: 600 }}>{module.name}</div>
                <span className="ip-tag" style={{ fontFamily: "var(--font-sans)" }}>
                  {module.health.toUpperCase()}
                </span>
              </div>

              <div className="ip-ops-highlight-grid">
                {getHighlights(module).map((item) => (
                  <div key={item.label} className="ip-ops-highlight-item">
                    <div className="ip-ops-highlight-label">{item.label}</div>
                    <div className="ip-ops-highlight-value">{item.value}</div>
                  </div>
                ))}
              </div>

              <div className="ip-ops-route-list">
                {module.routes.map((route) => (
                  <code key={route}>{route}</code>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="ip-sheet ip-ops-workbench">
          <div className="ip-ops-workbench-head">
            <div>
              <div className="ip-section-heading" style={{ marginBottom: 6 }}>Operations Workbench</div>
              <div className="ip-ops-workbench-subtitle">
                Execute live operations with tenant-scoped payloads, evidence-ready outputs, and backend sync.
              </div>
            </div>
            {lastRunMeta && (
              <div className="ip-ops-last-run">
                <div className="ip-ops-last-run-label">Last run</div>
                <div className="ip-ops-last-run-value">{lastRunMeta.operationLabel}</div>
                <div className="ip-ops-last-run-meta">{new Date(lastRunMeta.at).toLocaleString()}</div>
              </div>
            )}
          </div>

          <div className="ip-ops-workbench-grid">
            <div className="ip-ops-module-list">
              {availableModuleIds.map((moduleId) => {
                const module = moduleStatusMap[moduleId];
                if (!module) return null;
                const selected = activeModule === moduleId;
                return (
                  <button
                    key={moduleId}
                    className={`ip-ops-module-btn${selected ? " ip-ops-module-btn--active" : ""}`}
                    onClick={() => setActiveModule(moduleId)}
                  >
                    <div className="ip-ops-module-btn-top">
                      <span>{module.name}</span>
                      <span className="ip-tag" style={{ fontFamily: "var(--font-sans)" }}>
                        {module.health}
                      </span>
                    </div>
                    <div className="ip-ops-module-btn-sub">{WORKBENCH_OPERATIONS[moduleId].length} actions</div>
                  </button>
                );
              })}
            </div>

            <div className="ip-ops-runner">
              {activeOperation && (
                <>
                  <div className="ip-ops-runner-row">
                    <div className="ip-ops-runner-label">Operation</div>
                    <select
                      className="ip-input"
                      value={activeOperationId}
                      onChange={(event) => setActiveOperationId(event.target.value as WorkbenchOperationId)}
                    >
                      {operationsForModule.map((operation) => (
                        <option key={operation.id} value={operation.id}>
                          {operation.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="ip-ops-op-meta">
                    <span className="ip-tag">{activeOperation.method}</span>
                    <code>{activeOperation.route}</code>
                  </div>
                  <div className="ip-ops-op-description">{activeOperation.description}</div>

                  {activeOperation.requiresCaseId && (
                    <div className="ip-ops-runner-row">
                      <div className="ip-ops-runner-label">Case ID</div>
                      <input
                        className="ip-input"
                        value={caseIdInput}
                        onChange={(event) => setCaseIdInput(event.target.value)}
                        placeholder="e.g. 42f3f9da-..."
                      />
                    </div>
                  )}

                  <div className="ip-ops-runner-row">
                    <div className="ip-ops-runner-label">Payload JSON</div>
                    <textarea
                      className="ip-input ip-ops-json-editor"
                      value={payloadText}
                      onChange={(event) => setPayloadText(event.target.value)}
                      spellCheck={false}
                    />
                  </div>

                  <div className="ip-ops-runner-actions">
                    <button className="ip-btn-ghost" onClick={resetPayloadTemplate}>
                      Reset Template
                    </button>
                    <button
                      className="ip-btn-primary"
                      onClick={executeOperation}
                      disabled={runLoading}
                      style={{ opacity: runLoading ? 0.6 : 1 }}
                    >
                      {runLoading ? "Running..." : "Run Operation"}
                    </button>
                  </div>

                  {runError && <div className="ip-ops-run-error">{runError}</div>}

                  <div className="ip-ops-result-panel">
                    <div className="ip-section-heading" style={{ marginBottom: 8 }}>Result</div>
                    {!runResult && (
                      <div className="ip-ops-result-empty">
                        Execute an operation to view live response payloads.
                      </div>
                    )}
                    {runResult && <pre>{formatJson(runResult)}</pre>}
                  </div>
                </>
              )}
            </div>
          </div>

          {recentRuns.length > 0 && (
            <div className="ip-ops-recent-runs">
              <div className="ip-section-heading" style={{ marginBottom: 8 }}>Recent Runs</div>
              <div className="ip-ops-recent-run-list">
                {recentRuns.map((run) => (
                  <div key={`${run.at}-${run.operationLabel}`} className="ip-ops-recent-run-item">
                    <span>{run.operationLabel}</span>
                    <span className={`ip-ops-recent-status ip-ops-recent-status--${run.status}`}>
                      {run.status}
                    </span>
                    <span className="ip-mono">{new Date(run.at).toLocaleTimeString()}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="ip-ops-lower-grid">
          <div className="ip-sheet ip-ops-card">
            <div className="ip-section-heading">Planned Function Backlog</div>
            <div className="ip-ops-planned-list">
              {plannedFunctions.map((fn) => (
                <div key={fn.id} className="ip-ops-planned-item">
                  <div>
                    <div style={{ fontWeight: 500 }}>{fn.name}</div>
                    <div style={{ color: "var(--text-secondary)", fontSize: 12 }}>
                      priority: {fn.priority} · revenue impact: {fn.revenue_impact}
                    </div>
                  </div>
                  <span className="ip-tag" style={{ fontFamily: "var(--font-sans)" }}>
                    {fn.status.toUpperCase()}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="ip-sheet ip-ops-card">
            <div className="ip-section-heading">Management Capabilities Required</div>
            <div className="ip-ops-capabilities">
              {map.management_capabilities.map((capability) => (
                <div key={capability.id} className="ip-ops-capability-card">
                  <div style={{ fontWeight: 600, marginBottom: 4 }}>{capability.name}</div>
                  <div style={{ color: "var(--text-secondary)", fontSize: 12, marginBottom: 8 }}>
                    {capability.description}
                  </div>
                  <div className="ip-ops-cap-chip-row">
                    {capability.must_have_features.map((feature) => (
                      <span key={feature} className="ip-tag">
                        {feature}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
