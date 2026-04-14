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
