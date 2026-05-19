/**
 * Ironpass Dashboard — API client
 *
 * Wraps all calls to the FastAPI engine backend.
 * The IRONPASS_API_KEY is read from VITE_API_KEY env var for local dev,
 * or injected by the login flow (stored in sessionStorage).
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function getApiKey(): string {
  return (
    sessionStorage.getItem("ironpass_api_key") ||
    import.meta.env.VITE_API_KEY ||
    ""
  );
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const key = getApiKey();
  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(key ? { Authorization: `Bearer ${key}` } : {}),
      ...(options?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API ${path} → ${response.status}: ${body}`);
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Overview
// ---------------------------------------------------------------------------

export interface OverviewStats {
  total_requests: number;
  total_blocked: number;
  requests_24h: number;
  active_vault_tokens: number;
  avg_latency_ms: number;
  block_rate: number;
}

export async function fetchOverview(): Promise<OverviewStats> {
  return apiFetch<OverviewStats>("/dashboard/overview");
}

// ---------------------------------------------------------------------------
// Violations
// ---------------------------------------------------------------------------

export interface ViolationEntry {
  entry_id: string;
  timestamp: string;
  agent_id: string;
  rulesets_used: string[];
  detections: unknown[];
  actions_taken: unknown[];
  outcome: string;
}

export interface ViolationsResponse {
  violations: ViolationEntry[];
  total: number;
  limit: number;
  offset: number;
}

export async function fetchViolations(
  limit = 50,
  offset = 0
): Promise<ViolationsResponse> {
  return apiFetch<ViolationsResponse>(
    `/dashboard/violations?limit=${limit}&offset=${offset}`
  );
}

// ---------------------------------------------------------------------------
// Audit Log
// ---------------------------------------------------------------------------

export interface AuditEntry {
  entry_id: string;
  timestamp: string;
  agent_id: string;
  rulesets_used: string[];
  detections_count: number;
  actions_count: number;
  was_blocked: boolean;
  outcome: "passed" | "blocked" | "masked" | "error";
  latency_ms: number;
}

export interface AuditLogResponse {
  entries: AuditEntry[];
  total: number;
  limit: number;
  offset: number;
}

export async function fetchAuditLog(params?: {
  limit?: number;
  offset?: number;
  agent_id?: string;
  outcome?: string;
  ruleset?: string;
}): Promise<AuditLogResponse> {
  const qs = new URLSearchParams();
  if (params?.limit) qs.set("limit", String(params.limit));
  if (params?.offset) qs.set("offset", String(params.offset));
  if (params?.agent_id) qs.set("agent_id", params.agent_id);
  if (params?.outcome) qs.set("outcome", params.outcome);
  if (params?.ruleset) qs.set("ruleset", params.ruleset);
  return apiFetch<AuditLogResponse>(`/dashboard/audit?${qs.toString()}`);
}

// ---------------------------------------------------------------------------
// Audit integrity
// ---------------------------------------------------------------------------

export interface IntegrityReport {
  chain_status: "INTACT" | "BROKEN" | "EMPTY";
  tamper_detected: boolean;
  entries_verified: number;
  summary: string;
}

export async function verifyAuditChain(
  limit = 100
): Promise<IntegrityReport> {
  return apiFetch<IntegrityReport>(
    `/dashboard/audit/verify?limit=${limit}`
  );
}

// ---------------------------------------------------------------------------
// Rulesets
// ---------------------------------------------------------------------------

export interface RulesetSummary {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
  detector_count: number;
}

export async function fetchRulesets(): Promise<{ rulesets: RulesetSummary[] }> {
  return apiFetch<{ rulesets: RulesetSummary[] }>("/proxy/rulesets");
}

export async function updateActiveRulesets(
  rulesets: string[]
): Promise<{ active_rulesets: string[]; invalid_rulesets: string[] }> {
  return apiFetch<{ active_rulesets: string[]; invalid_rulesets: string[] }>(
    "/proxy/rulesets/active",
    {
      method: "PUT",
      body: JSON.stringify({ rulesets }),
    }
  );
}

export interface ScanRequestPayload {
  content: string;
  rulesets?: string[];
  target_url?: string;
  metadata?: Record<string, string>;
}

export interface ScanViolation {
  type: string;
  action: string;
  ruleset: string;
}

export interface ScanResponsePayload {
  sanitized_content: string;
  violations: ScanViolation[];
  was_blocked: boolean;
  audit_id: string;
  session_id: string;
  latency_ms: number;
}

export async function runComplianceScan(
  payload: ScanRequestPayload
): Promise<ScanResponsePayload> {
  return apiFetch<ScanResponsePayload>("/proxy/scan", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ---------------------------------------------------------------------------
// Product map / function suite
// ---------------------------------------------------------------------------

export interface ProductMapFeature {
  id: string;
  name: string;
  status: string;
  routes: string[];
}

export interface ProductMapCapability {
  id: string;
  name: string;
  description: string;
  must_have_features: string[];
}

export interface ProductMapFunction {
  id: string;
  name: string;
  status: "implemented" | "planned";
  priority: "critical" | "high" | "medium";
  revenue_impact: "high" | "medium";
}

export interface ProductMapResponse {
  generated_at: string;
  core_compliance_layer: {
    name: string;
    description: string;
    kpis: OverviewStats & {
      tenant_id: string;
      active_rulesets_count: number;
    };
    rulesets: {
      active_count: number;
      active_rulesets: string[];
      available_count: number;
      available_rulesets: string[];
    };
    features: ProductMapFeature[];
  };
  operations_function_suite: {
    name: string;
    description: string;
    implemented_count: number;
    planned_count: number;
    functions: ProductMapFunction[];
  };
  management_capabilities: ProductMapCapability[];
}

export async function fetchProductMap(): Promise<ProductMapResponse> {
  return apiFetch<ProductMapResponse>("/dashboard/product-map");
}

export interface FunctionOverviewModule {
  id: string;
  name: string;
  status: "implemented";
  health: "live" | "degraded" | "error";
  metrics: Record<string, unknown>;
  routes: string[];
  errors: string[];
}

export interface FunctionsOverviewResponse {
  generated_at: string;
  implemented_modules: FunctionOverviewModule[];
  implemented_count: number;
  live_count: number;
  planned_count: number;
  planned_modules: ProductMapFunction[];
}

export async function fetchFunctionsOverview(): Promise<FunctionsOverviewResponse> {
  return apiFetch<FunctionsOverviewResponse>("/dashboard/functions/overview");
}

// ---------------------------------------------------------------------------
// Operations function suite APIs (operational workflows)
// ---------------------------------------------------------------------------

function toQueryString(
  params: Record<string, string | number | boolean | undefined | null>
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

// AML / SAR
export interface AmlSignalIngestPayload {
  subject_id?: string | null;
  counterparty?: string | null;
  amount?: number | null;
  currency?: string;
  country_from?: string | null;
  country_to?: string | null;
  channel?: string | null;
  description?: string | null;
  pep_hit?: boolean;
  sanction_hit?: boolean;
  unusual_pattern?: boolean;
  new_customer?: boolean;
  metadata?: Record<string, unknown>;
}

export interface AmlSignalIngestResult {
  signal_id: string;
  risk_score: number;
  flags: string[];
  action: string;
  case_id: string | null;
}

export interface ComplianceCaseRecord {
  case_id: string;
  domain: string;
  case_type: string;
  title: string;
  summary: string | null;
  status: string;
  priority: string;
  risk_score: number;
  opened_at: string;
  updated_at: string;
}

export interface ComplianceCasesResult {
  total: number;
  items: ComplianceCaseRecord[];
}

export interface SarDraftPayload {
  suspicion_summary: string;
  narrative: string;
  report_payload?: Record<string, unknown>;
  jurisdiction?: string;
}

export interface SarSubmitPayload {
  submission_reference?: string | null;
}

export interface SarReportResult {
  report_id: string;
  case_id: string;
  status: string;
  jurisdiction: string;
  submission_reference: string | null;
  submitted_at: string | null;
  consent_deadline_at: string | null;
}

export interface AmlDashboardResult {
  open_cases: number;
  submitted_cases: number;
  high_risk_signals_7d: number;
  signals_7d: number;
}

export async function ingestAmlSignal(
  payload: AmlSignalIngestPayload
): Promise<AmlSignalIngestResult> {
  return apiFetch<AmlSignalIngestResult>("/v1/compliance/aml/signals", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listAmlCases(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<ComplianceCasesResult> {
  const query = toQueryString({
    status: params?.status,
    limit: params?.limit,
    offset: params?.offset,
  });
  return apiFetch<ComplianceCasesResult>(`/v1/compliance/aml/cases${query}`);
}

export async function saveSarDraft(
  caseId: string,
  payload: SarDraftPayload
): Promise<SarReportResult> {
  return apiFetch<SarReportResult>(`/v1/compliance/aml/cases/${caseId}/sar-draft`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function submitSar(
  caseId: string,
  payload: SarSubmitPayload
): Promise<SarReportResult> {
  return apiFetch<SarReportResult>(`/v1/compliance/aml/cases/${caseId}/submit`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchAmlDashboard(): Promise<AmlDashboardResult> {
  return apiFetch<AmlDashboardResult>("/v1/compliance/aml/dashboard");
}

// Financial covenants
export interface CreateCovenantPayload {
  name: string;
  metric_name: string;
  comparator: "<=" | ">=" | "<" | ">" | "=";
  threshold: number;
  warning_buffer_pct?: number;
  frequency?: string | null;
  owner?: string | null;
}

export interface CovenantRecord {
  covenant_id: string;
  name: string;
  metric_name: string;
  comparator: string;
  threshold: number;
  warning_buffer_pct: number;
  frequency: string | null;
  owner: string | null;
  status: string;
  updated_at: string;
}

export interface CovenantsResult {
  total: number;
  items: CovenantRecord[];
}

export interface EvaluateCovenantsPayload {
  period_end?: string | null;
  metrics: Record<string, number>;
  metadata?: Record<string, unknown>;
}

export interface CovenantEvaluationItem {
  covenant_id: string;
  metric_name: string;
  status: string;
  comparator: string;
  threshold: number;
  metric_value: number;
  distance_pct: number | null;
  case_id: string | null;
}

export interface EvaluateCovenantsResult {
  snapshot_id: string;
  breached_count: number;
  at_risk_count: number;
  compliant_count: number;
  items: CovenantEvaluationItem[];
}

export interface CovenantDashboardResult {
  active_covenants: number;
  breached_30d: number;
  at_risk_30d: number;
}

export async function createCovenant(
  payload: CreateCovenantPayload
): Promise<CovenantRecord> {
  return apiFetch<CovenantRecord>("/v1/compliance/covenants", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listCovenants(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<CovenantsResult> {
  const query = toQueryString({
    status: params?.status,
    limit: params?.limit,
    offset: params?.offset,
  });
  return apiFetch<CovenantsResult>(`/v1/compliance/covenants${query}`);
}

export async function evaluateCovenants(
  payload: EvaluateCovenantsPayload
): Promise<EvaluateCovenantsResult> {
  return apiFetch<EvaluateCovenantsResult>("/v1/compliance/covenants/evaluate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchCovenantDashboard(): Promise<CovenantDashboardResult> {
  return apiFetch<CovenantDashboardResult>("/v1/compliance/covenants/dashboard");
}

// SLA
export interface CreateSlaContractPayload {
  name: string;
  service_name: string;
  metric_name: string;
  comparator: "<=" | ">=" | "<" | ">" | "=";
  target_value: number;
  warning_buffer_pct?: number;
  credit_rate_pct?: number;
  max_credit_pct?: number;
  monthly_contract_value?: number | null;
  frequency?: string | null;
  owner?: string | null;
}

export interface SlaContractRecord {
  contract_id: string;
  name: string;
  service_name: string;
  metric_name: string;
  comparator: string;
  target_value: number;
  warning_buffer_pct: number;
  credit_rate_pct: number;
  max_credit_pct: number;
  monthly_contract_value: number | null;
  frequency: string | null;
  owner: string | null;
  status: string;
  updated_at: string;
}

export interface SlaContractsResult {
  total: number;
  items: SlaContractRecord[];
}

export interface SlaObservationPayload {
  contract_id?: string | null;
  service_name: string;
  metric_name: string;
  observed_value: number;
  impacted_requests?: number;
  metadata?: Record<string, unknown>;
}

export interface EvaluateSlaPayload {
  observations: SlaObservationPayload[];
  period_start?: string | null;
  period_end?: string | null;
  metadata?: Record<string, unknown>;
  create_cases?: boolean;
}

export interface SlaEvaluationItem {
  contract_id: string;
  contract_name: string;
  service_name: string;
  metric_name: string;
  status: string;
  comparator: string;
  target_value: number;
  observed_value: number;
  distance_pct: number | null;
  estimated_credit_amount: number;
  case_id: string | null;
}

export interface EvaluateSlaResult {
  snapshot_id: string;
  breached_count: number;
  at_risk_count: number;
  compliant_count: number;
  estimated_credit_exposure: number;
  items: SlaEvaluationItem[];
}

export interface SlaDashboardResult {
  active_contracts: number;
  breached_30d: number;
  at_risk_30d: number;
  estimated_credits_30d: number;
  open_sla_cases: number;
}

export async function createSlaContract(
  payload: CreateSlaContractPayload
): Promise<SlaContractRecord> {
  return apiFetch<SlaContractRecord>("/v1/compliance/sla/contracts", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listSlaContracts(params?: {
  status?: string;
  service_name?: string;
  metric_name?: string;
  limit?: number;
  offset?: number;
}): Promise<SlaContractsResult> {
  const query = toQueryString({
    status: params?.status,
    service_name: params?.service_name,
    metric_name: params?.metric_name,
    limit: params?.limit,
    offset: params?.offset,
  });
  return apiFetch<SlaContractsResult>(`/v1/compliance/sla/contracts${query}`);
}

export async function evaluateSla(
  payload: EvaluateSlaPayload
): Promise<EvaluateSlaResult> {
  return apiFetch<EvaluateSlaResult>("/v1/compliance/sla/evaluate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchSlaDashboard(): Promise<SlaDashboardResult> {
  return apiFetch<SlaDashboardResult>("/v1/compliance/sla/dashboard");
}

// GDPR retention + ROPA
export interface CreateGdprRetentionPolicyPayload {
  system_name: string;
  data_category: string;
  legal_basis?: string | null;
  retention_days: number;
  warning_buffer_days?: number;
  owner?: string | null;
  source?: string;
}

export interface GdprRetentionPolicyRecord {
  policy_id: string;
  system_name: string;
  data_category: string;
  legal_basis: string | null;
  retention_days: number;
  warning_buffer_days: number;
  owner: string | null;
  status: string;
  source: string;
  updated_at: string;
}

export interface GdprRetentionPoliciesResult {
  total: number;
  items: GdprRetentionPolicyRecord[];
}

export interface GdprRetentionObservationPayload {
  system_name: string;
  data_category: string;
  oldest_record_age_days: number;
  record_count?: number;
  metadata?: Record<string, unknown>;
}

export interface EvaluateGdprRetentionPayload {
  observations: GdprRetentionObservationPayload[];
  captured_at?: string | null;
  metadata?: Record<string, unknown>;
  create_cases?: boolean;
}

export interface GdprRetentionFindingItem {
  system_name: string;
  data_category: string;
  status: string;
  reason: string;
  retention_days: number | null;
  observed_oldest_age_days: number;
  excess_days: number | null;
  policy_id: string | null;
  case_id: string | null;
}

export interface EvaluateGdprRetentionResult {
  snapshot_id: string;
  breach_count: number;
  warning_count: number;
  no_policy_count: number;
  compliant_count: number;
  items: GdprRetentionFindingItem[];
}

export interface GdprRetentionDashboardResult {
  active_policies: number;
  breaches_30d: number;
  warnings_30d: number;
  no_policy_30d: number;
}

export interface CreateRopaActivityPayload {
  activity_name: string;
  purpose?: string | null;
  lawful_basis?: string | null;
  data_categories?: string[];
  data_subjects?: string[];
  recipients?: string[];
  transfer_countries?: string[];
  source_system?: string | null;
  dpa_reference?: string | null;
  owner?: string | null;
  status?: string;
  last_reviewed_at?: string | null;
  next_review_due_at?: string | null;
}

export interface RopaActivityRecord {
  activity_id: string;
  activity_name: string;
  purpose: string | null;
  lawful_basis: string | null;
  data_categories: string[];
  data_subjects: string[];
  recipients: string[];
  transfer_countries: string[];
  source_system: string | null;
  dpa_reference: string | null;
  owner: string | null;
  status: string;
  last_reviewed_at: string | null;
  next_review_due_at: string | null;
  updated_at: string;
}

export interface RopaActivitiesResult {
  total: number;
  items: RopaActivityRecord[];
}

export interface MonitorRopaPayload {
  due_soon_days?: number;
  create_cases?: boolean;
}

export interface MonitorRopaItem {
  activity_id: string;
  activity_name: string;
  status: string;
  reasons: string[];
  days_until_review_due: number | null;
  case_id: string | null;
}

export interface MonitorRopaResult {
  total_activities: number;
  critical_count: number;
  warning_count: number;
  compliant_count: number;
  items: MonitorRopaItem[];
}

export interface RopaDashboardResult {
  active_activities: number;
  overdue_reviews: number;
  due_soon_reviews: number;
  missing_lawful_basis: number;
  open_gdpr_cases: number;
}

export async function createGdprRetentionPolicy(
  payload: CreateGdprRetentionPolicyPayload
): Promise<GdprRetentionPolicyRecord> {
  return apiFetch<GdprRetentionPolicyRecord>("/v1/compliance/gdpr/retention-policies", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listGdprRetentionPolicies(params?: {
  status?: string;
  system_name?: string;
  data_category?: string;
  limit?: number;
  offset?: number;
}): Promise<GdprRetentionPoliciesResult> {
  const query = toQueryString({
    status: params?.status,
    system_name: params?.system_name,
    data_category: params?.data_category,
    limit: params?.limit,
    offset: params?.offset,
  });
  return apiFetch<GdprRetentionPoliciesResult>(`/v1/compliance/gdpr/retention-policies${query}`);
}

export async function evaluateGdprRetention(
  payload: EvaluateGdprRetentionPayload
): Promise<EvaluateGdprRetentionResult> {
  return apiFetch<EvaluateGdprRetentionResult>("/v1/compliance/gdpr/retention/evaluate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchGdprRetentionDashboard(): Promise<GdprRetentionDashboardResult> {
  return apiFetch<GdprRetentionDashboardResult>("/v1/compliance/gdpr/retention/dashboard");
}

export async function createRopaActivity(
  payload: CreateRopaActivityPayload
): Promise<RopaActivityRecord> {
  return apiFetch<RopaActivityRecord>("/v1/compliance/gdpr/ropa/activities", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listRopaActivities(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<RopaActivitiesResult> {
  const query = toQueryString({
    status: params?.status,
    limit: params?.limit,
    offset: params?.offset,
  });
  return apiFetch<RopaActivitiesResult>(`/v1/compliance/gdpr/ropa/activities${query}`);
}

export async function monitorRopa(
  payload: MonitorRopaPayload
): Promise<MonitorRopaResult> {
  return apiFetch<MonitorRopaResult>("/v1/compliance/gdpr/ropa/monitor", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchRopaDashboard(): Promise<RopaDashboardResult> {
  return apiFetch<RopaDashboardResult>("/v1/compliance/gdpr/ropa/dashboard");
}

// ---------------------------------------------------------------------------
// Agent security suite
// ---------------------------------------------------------------------------

export interface AgentSecurityControlStatus {
  control_id: string;
  title: string;
  objective: string;
  status: "operational" | "planned";
}

export interface AgentSecurityOverviewResponse {
  suite_name: string;
  generated_at: string;
  controls: AgentSecurityControlStatus[];
}

export interface AgentSecurityFinding {
  finding_id: string;
  category: string;
  severity: "low" | "medium" | "high" | "critical";
  title: string;
  evidence: string;
  recommendation: string;
}

export interface PromptInjectionAnalyzePayload {
  task_instruction: string;
  untrusted_content: string;
  allowed_actions?: string[];
  block_threshold?: number;
}

export interface PromptInjectionAnalyzeResult {
  risk_score: number;
  blocked: boolean;
  attack_strings_detected: string[];
  findings: AgentSecurityFinding[];
  sanitized_content: string;
}

export interface ContextExfiltrationAnalyzePayload {
  candidate_output: string;
  reasoning_trace?: string | null;
  tool_payloads?: Array<Record<string, unknown>>;
  allowed_destinations?: string[];
}

export interface ContextExfilLeakHit {
  leak_type: string;
  location: "candidate_output" | "reasoning_trace" | "tool_payload";
  preview: string;
}

export interface ContextExfiltrationAnalyzeResult {
  risk_score: number;
  findings: AgentSecurityFinding[];
  leak_hits: ContextExfilLeakHit[];
  redacted_output: string;
}

export interface ToolCapabilityPayload {
  tool_name: string;
  description?: string;
  scopes?: string[];
  data_domains?: string[];
  requires_approval?: boolean;
}

export interface ToolPermissionEvaluatePayload {
  task_description: string;
  tools: ToolCapabilityPayload[];
  requested_tools?: string[];
  max_tools?: number;
}

export interface GrantedToolPermissionResult {
  tool_name: string;
  granted_scopes: string[];
  reason: string;
}

export interface DeniedToolPermissionResult {
  tool_name: string;
  reason: string;
}

export interface ToolPermissionEvaluateResult {
  risk_score: number;
  findings: AgentSecurityFinding[];
  least_privilege_set: GrantedToolPermissionResult[];
  denied: DeniedToolPermissionResult[];
}

export interface SessionMemoryEventPayload {
  turn_id: string;
  role?: string;
  content: string;
  persisted?: boolean;
}

export interface MemorySessionAuditPayload {
  session_events: SessionMemoryEventPayload[];
  max_retention_turns?: number;
}

export interface MemoryLeakItemResult {
  turn_id: string;
  leak_type: string;
  preview: string;
  action: "scrub" | "summarize" | "keep";
  reason: string;
}

export interface MemorySessionAuditResult {
  risk_score: number;
  findings: AgentSecurityFinding[];
  flagged_items: MemoryLeakItemResult[];
  recommended_ttl_turns: number;
}

export async function fetchAgentSecurityOverview(): Promise<AgentSecurityOverviewResponse> {
  return apiFetch<AgentSecurityOverviewResponse>("/v1/agent-security/overview");
}

export async function analyzePromptInjection(
  payload: PromptInjectionAnalyzePayload
): Promise<PromptInjectionAnalyzeResult> {
  return apiFetch<PromptInjectionAnalyzeResult>("/v1/agent-security/prompt-injection/analyze", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function analyzeContextExfiltration(
  payload: ContextExfiltrationAnalyzePayload
): Promise<ContextExfiltrationAnalyzeResult> {
  return apiFetch<ContextExfiltrationAnalyzeResult>("/v1/agent-security/context-exfiltration/analyze", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function evaluateToolPermissions(
  payload: ToolPermissionEvaluatePayload
): Promise<ToolPermissionEvaluateResult> {
  return apiFetch<ToolPermissionEvaluateResult>("/v1/agent-security/tool-permissions/evaluate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function auditMemorySession(
  payload: MemorySessionAuditPayload
): Promise<MemorySessionAuditResult> {
  return apiFetch<MemorySessionAuditResult>("/v1/agent-security/memory/audit", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
