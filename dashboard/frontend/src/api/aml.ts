import { api } from './client';

export interface AMLSignal {
  id: string;
  tenant_id: string;
  customer_id: string;
  amount: number;
  channel: string;
  jurisdiction: string;
  is_pep: boolean;
  is_sanctioned: boolean;
  unusual_pattern: boolean;
  risk_score: number;
  created_at: string;
}

export interface ComplianceCase {
  id: string;
  tenant_id: string;
  module: string;
  status: string;        // open | in_review | submitted | closed
  risk_score: number;
  created_at: string;
  updated_at: string;
  events: CaseEvent[];
}

export interface CaseEvent {
  id: string;
  case_id: string;
  event_type: string;
  description: string;
  created_at: string;
}

export interface SARReport {
  id: string;
  case_id: string;
  draft_content: string;
  status: string;        // draft | submitted
  submitted_at?: string;
}

export interface AMLDashboardData {
  open_cases: number;
  high_risk_signals: number;
  overdue_cases: number;
  signals_today: number;
}

export interface SignalCreatePayload {
  customer_id: string;
  amount: number;
  channel: string;
  jurisdiction: string;
  is_pep: boolean;
  is_sanctioned: boolean;
  unusual_pattern: boolean;
  new_customer: boolean;
}

export const amlApi = {
  submitSignal: (payload: SignalCreatePayload) =>
    api.post<AMLSignal>('/v1/compliance/aml/signals', payload),

  listCases: () =>
    api.get<ComplianceCase[]>('/v1/compliance/aml/cases'),

  getCase: (caseId: string) =>
    api.get<ComplianceCase>(`/v1/compliance/aml/cases/${caseId}`),

  generateSARDraft: (caseId: string) =>
    api.post<SARReport>(`/v1/compliance/aml/cases/${caseId}/sar-draft`, {}),

  submitSAR: (caseId: string) =>
    api.post<SARReport>(`/v1/compliance/aml/cases/${caseId}/submit`, {}),

  getDashboard: () =>
    api.get<AMLDashboardData>('/v1/compliance/aml/dashboard'),
};
