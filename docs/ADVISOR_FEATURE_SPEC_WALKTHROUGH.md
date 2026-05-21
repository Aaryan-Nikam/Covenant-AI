# Ironpass Technical Build Walkthrough (What Is Already Built)

As-of date: 2026-05-20
Audience: External technical advisor / architecture reviewer
Purpose: Describe the implemented system, features, and module internals (not product prompts/journey)

## 1) System Overview
Ironpass is a FastAPI-based multi-tenant compliance platform with two primary product surfaces:
1. Core Compliance Layer (proxy interception, detection, action enforcement, vault, immutable audit)
2. Function Suite (9 domain modules for high-value backend compliance/operations workflows)

The app also includes:
- Agent Security Suite (prompt injection, exfiltration, least-privilege tools, memory hygiene)
- Unified Decisioning API (single signed compliance+security decision contract)
- Admin provisioning APIs (tenant + key lifecycle)
- Tenant audit query APIs
- Dashboard backend APIs for operational visibility

## 2) Runtime and Architecture

### 2.1 Application Composition
- Entry point: `engine/main.py`
- Framework: FastAPI
- DB access: SQLAlchemy async engine/sessionmaker
- Startup lifecycle:
  - verifies the live DB is at Alembic head (`init_db`)
  - pre-warms shared HTTP client pool
  - loads rulesets from YAML
- Middleware and platform controls:
  - CORS middleware
  - rate limiting (`slowapi`, default `100/minute`)
  - Prometheus endpoint `/metrics`

### 2.2 Database Schemas and Tables
The current model footprint is:
- `public` schema:
  - tenant/auth tables: `tenants`, `tenant_api_keys`
  - function-suite tables: 25 compliance tables
  - agent-security tables: 2 tables
- `audit` schema:
  - `audit_log` (append-only tamper-evident chain)
- `vault` schema:
  - `vault_tokens` (AES-GCM encrypted token map)

### 2.3 API Surface (Implemented Endpoint Count)
- Proxy router: 8 endpoints
- Compliance router: 44 endpoints
- Agent Security router: 8 endpoints
- Unified Decisions router: 1 endpoint
- Admin router: 6 endpoints
- Logs router: 2 endpoints
- Dashboard backend router: 6 endpoints

## 3) Authentication, Tenant Isolation, and Access

### 3.1 Tenant API Authentication
- Auth path: `verify_api_key` -> `authenticate_request`
- Flow:
  - requires Bearer key with `dbnc_live_` prefix
  - hashes raw key (`SHA-256`) and looks up `tenant_api_keys.key_hash`
  - checks revoked/inactive/expired states
  - checks tenant active status
  - returns tenant context used by all tenant-scoped endpoints

### 3.2 Admin Authentication
- Admin endpoints protected by `IRONPASS_ADMIN_SECRET` bearer token
- Admin API is separate from tenant keys

### 3.3 Isolation Guarantees in Code
- Compliance and security evaluations are keyed by `tenant_id`
- Audit queries scope by `agent_id` (mapped to tenant)
- Vault retrieval enforces both `tenant_id` and `agent_id`
- Tenant active rulesets are configurable per-tenant

## 4) Core Compliance Layer (Built Features)

### 4.1 Provider Proxy Interception
Implemented provider proxy endpoints:
- `POST /openai/v1/chat/completions`
- `POST /anthropic/v1/messages`
- `POST /google/v1/models/{model}:generateContent`
- `POST /proxy/scan` (scan-only mode)

Pipeline behavior:
1. Extract structured provider payload content
2. Run compliance pipeline (`process_request`)
3. Apply detection/actions using active rulesets
4. Forward sanitized content to upstream provider (proxy endpoints)
5. De-tokenize provider response where session token map exists
6. Log audit entry (async non-blocking)

### 4.2 Detection Engine
Detection layers (orchestrated by `DetectionEngine`):
- Layer 1: regex detector
- Layer 2: Luhn validation (credit card false-positive filtering)
- Layer 3: NER detector (spaCy-based)
- Deduplication strategy:
  - by position
  - ruleset priority + confidence + layer order

### 4.3 Action Engine
`ActionExecutor` applies actions in reverse position order to preserve text offsets.
Supported actions:
- `block`
- `tokenize`
- `mask`
- `pseudonymize`

Overlap resolution priority:
- `block > tokenize > pseudonymize > mask`

Fallback behavior:
- if primary action fails, fallback action is attempted from ruleset config

### 4.4 Rulesets (Current)
Loaded YAML rulesets from `engine/rulesets/definitions`:
- `pci_dss` (6 detectors)
- `hipaa` (5 detectors)
- `gdpr` (5 detectors)
- `soc2` (3 detectors)

Ruleset management endpoints:
- `GET /proxy/rulesets`
- `GET /proxy/rulesets/{ruleset_id}`
- `PUT /proxy/rulesets/active` (per-tenant active rulesets)

### 4.5 Vault and Tokenization
- Vault table: `vault.vault_tokens`
- Encryption: AES-256-GCM
- Keys are fetched via key manager, not stored in app DB
- Tokens are tenant-scoped and agent-scoped
- Supports invalidation and expiry cleanup workflows

### 4.6 Immutable Audit Layer
- Audit table: `audit.audit_log`
- Chain model:
  - each entry has HMAC signature
  - each entry stores previous entry hash link
- Verification:
  - dashboard endpoint verifies chain integrity
- Tenant-facing audit query excludes internal signature/hash fields

## 5) Agent Security Suite (Built)
Base route: `/v1/agent-security`

Implemented endpoints:
- `GET /overview`
- `GET /policy`
- `PUT /policy`
- `POST /decision/evaluate`
- `POST /prompt-injection/analyze`
- `POST /context-exfiltration/analyze`
- `POST /tool-permissions/evaluate`
- `POST /memory/audit`

### 5.1 Policy Model
Per-tenant persisted policy includes:
- mode: `monitor | enforce`
- block/review thresholds
- max tools per task
- strict tool allowlist mode
- memory retention controls
- allowed destination domains

### 5.2 Decision Engine
Composite `decision/evaluate` runs four controls and returns signed decision payload.
Controls:
1. Prompt injection shield
2. Context exfiltration guard
3. Least-privilege tool gate
4. Memory hygiene audit

Overall risk score weighting:
- prompt injection: 35%
- exfiltration: 35%
- tool permissions: 20%
- memory audit: 10%

Action resolution:
- hard-block conditions can return `block` (or `review` in monitor mode)
- otherwise review threshold check
- else `allow`

Idempotency behavior:
- decision logs keyed by `tenant_id + request_id`
- repeated `request_id` returns existing persisted decision

## 5.3 Unified Compliance+Security Decision (New)
Base route: `/v1/decisions`

Endpoint:
- `POST /evaluate`

What it does:
- runs agent-security composite decisioning
- runs PII detection (regex/luhn/NER) against tenant-active rulesets
- computes weighted unified risk:
  - pii detection: 20%
  - prompt injection: 30%
  - exfiltration: 25%
  - tool permissions: 15%
  - memory hygiene: 10%
- returns one signed decision contract:
  - `allow | review | block`
  - component risk breakdown
  - normalized evidence list
  - applied actions
  - audit trail link (`audit_entry_id`)

Persistence and idempotency:
- new table: `public.unified_decision_logs`
- uniqueness key: `tenant_id + request_id`
- repeated request IDs return the existing stored payload

## 6) Function Suite (9/9 Implemented)
Base route: `/v1/compliance`

### 6.1 Shared Cross-Module Patterns
Across modules, implementation includes:
- table-backed state and snapshots
- per-module create/list/evaluate APIs
- dashboard metrics API
- case escalation to shared `compliance_cases`
- immutable `compliance_case_events` timeline records
- case dedupe/reuse for open in-review states where implemented

### 6.2 Module 1: AML + SAR Workflow
Key tables:
- `aml_signals`, `compliance_cases`, `sar_reports`, `compliance_case_events`

Endpoints:
- `POST /aml/signals`
- `GET /aml/cases`
- `GET /aml/cases/{case_id}`
- `POST /aml/cases/{case_id}/sar-draft`
- `POST /aml/cases/{case_id}/submit`
- `GET /aml/dashboard`

Scoring logic highlights:
- deterministic risk score with factors:
  - amount bands (>=5k, >=10k)
  - cash channel
  - high-risk jurisdictions
  - PEP hit
  - sanctions hit
  - unusual pattern
  - new customer + high amount
- score caps at 100
- escalation to case when score >= 70 or sanction hit

### 6.3 Module 2: Financial Covenant + Debt Monitoring
Key tables:
- `financial_covenants`, `financial_snapshots`, `covenant_evaluations`

Endpoints:
- `POST /covenants`
- `GET /covenants`
- `POST /covenants/evaluate`
- `GET /covenants/dashboard`

Evaluation logic:
- comparator-based checks (`<=`, `>=`, `<`, `>`, `=`)
- statuses: `compliant | at_risk | breached`
- warning band based on threshold distance percentage
- case creation for `at_risk` and `breached`

### 6.4 Module 3: SLA Breach + Credit Leakage Monitoring
Key tables:
- `sla_contracts`, `sla_snapshots`, `sla_evaluations`

Endpoints:
- `POST /sla/contracts`
- `GET /sla/contracts`
- `POST /sla/evaluate`
- `GET /sla/dashboard`

Evaluation logic:
- comparator checks against observed values
- estimated credit leakage calculation for breaches:
  - base rate + severity multiplier by distance bands
  - capped by max credit percent
- breach case creation + event timeline

### 6.5 Module 4: GDPR Retention + ROPA Monitoring
Key tables:
- `gdpr_retention_policies`, `gdpr_retention_snapshots`, `gdpr_retention_findings`
- `gdpr_processing_activities`

Endpoints:
- `POST /gdpr/retention-policies`
- `GET /gdpr/retention-policies`
- `POST /gdpr/retention/evaluate`
- `GET /gdpr/retention/dashboard`
- `POST /gdpr/ropa/activities`
- `GET /gdpr/ropa/activities`
- `POST /gdpr/ropa/monitor`
- `GET /gdpr/ropa/dashboard`

Evaluation logic:
- retention statuses: `compliant | warning | breach | no_policy`
- ROPA monitoring statuses: `compliant | warning | critical`
- critical triggers include missing lawful basis/purpose/categories and overdue review

### 6.6 Module 5: R&D Tax Credit Activity Tracking
Key tables:
- `rd_tax_activities`, `rd_tax_assessments`

Endpoints:
- `POST /rd-tax/activities`
- `GET /rd-tax/activities`
- `POST /rd-tax/evaluate`
- `GET /rd-tax/dashboard`

Evaluation logic:
- groups activities by project within period window
- qualifying cost requires:
  - qualifying category match
  - technical uncertainty true
  - narrative present
  - evidence references present
- statuses: `eligible | at_risk | non_compliant`
- estimated credit amount computed from qualifying cost and credit rate

### 6.7 Module 6: ESG Data + CSRD Compliance
Key tables:
- `esg_metrics`, `esg_csrd_submissions`

Endpoints:
- `POST /esg/metrics`
- `GET /esg/metrics`
- `POST /esg/csrd/evaluate`
- `GET /esg/csrd/dashboard`

Evaluation logic:
- checks required metric coverage, evidence presence, and staleness window
- statuses: `compliant | stale | missing_required | not_required`
- computes coverage percentage for required metrics

### 6.8 Module 7: Supplier Financial Health + Insolvency Monitoring
Key tables:
- `supplier_profiles`, `supplier_risk_assessments`

Endpoints:
- `POST /supplier/profiles`
- `GET /supplier/profiles`
- `POST /supplier/financial-health/evaluate`
- `GET /supplier/financial-health/dashboard`

Risk logic:
- weighted score inputs:
  - probability of default
  - payment delay days
  - watchlist hit
  - covenant breach signal
- statuses: `stable | warning | critical`
- case escalation for critical outcomes

### 6.9 Module 8: H&S Near-Miss + RIDDOR Monitoring
Key tables:
- `hs_incidents`, `hs_riddor_assessments`

Endpoints:
- `POST /hs/incidents`
- `GET /hs/incidents`
- `POST /hs/riddor/monitor`
- `GET /hs/riddor/dashboard`

Evaluation logic:
- reportability checks by incident type, severity, and lost-time days
- deadline logic for reporting windows
- statuses include:
  - `not_reportable`, `pending_report`, `due_soon`, `overdue`, `reported_on_time`, `reported_late`

### 6.10 Module 9: Competitor Intelligence + Strategic Signals
Key tables:
- `competitor_profiles`, `competitor_signal_assessments`

Endpoints:
- `POST /competitor/profiles`
- `GET /competitor/profiles`
- `POST /competitor/signals/evaluate`
- `GET /competitor/signals/dashboard`

Scoring logic:
- priority score from:
  - signal strength (50%)
  - source confidence (20%)
  - revenue impact (30%)
  - plus boost for high-impact signal types
- statuses: `tracking | warning | critical`
- critical signals escalate to cases

## 7) Control Plane and Reporting Surfaces

### 7.1 Dashboard Backend
Implemented dashboard APIs:
- `GET /dashboard/overview`
- `GET /dashboard/violations`
- `GET /dashboard/audit`
- `GET /dashboard/audit/verify`
- `GET /dashboard/product-map`
- `GET /dashboard/functions/overview`

Current product-map catalog reports all 9 function modules as implemented.

### 7.2 Admin and Tenant Lifecycle APIs
Implemented admin endpoints:
- `POST /v1/admin/tenants`
- `GET /v1/admin/tenants`
- `PATCH /v1/admin/tenants/{tenant_id}`
- `POST /v1/admin/tenants/{tenant_id}/keys`
- `POST /v1/admin/tenants/{tenant_id}/keys/{key_id}/revoke`
- `DELETE /v1/admin/tenants/{tenant_id}`

### 7.3 Tenant Audit Query APIs
Implemented tenant audit query endpoints:
- `GET /v1/logs`
- `GET /v1/logs/{entry_id}`

## 8) Current Validation Snapshot

### 8.1 Unit Tests
- `pytest -q tests/unit`: 84 passed, 1 warning
- `pytest -q tests/unit/test_compliance_service.py`: 20 passed
- `pytest -q tests/unit/test_agent_security_service.py`: 5 passed

### 8.2 Full Suite Snapshot
- `pytest -q`: 102 passed, 62 skipped, 3 failed
- Current failing tests are integration tests in `tests/integration/test_pipeline.py` expecting unauthenticated access to `/proxy/rulesets*` endpoints; current implementation returns `403` without auth.

## 9) What Is Built vs. What Is Not Built

### Built (Concrete)
- End-to-end request interception + compliance pipeline for OpenAI/Anthropic/Google
- YAML-driven ruleset system with detection/action execution
- Vault tokenization with encrypted storage and de-tokenization support
- Immutable audit chain with verification endpoint
- Tenant provisioning/key lifecycle APIs
- Agent security policy + decisioning service with signed outcomes
- Nine operational compliance function modules with persistence + dashboards + case workflows

### Not Yet in Current Implementation (Technical Gaps)
- Advisor-grade auto-generated architecture diagrams from code (manual documentation only)
- Full green integration suite (3 integration tests currently mismatched with auth behavior)
- Documented migration system for schema evolution (tables are created via startup model registration)
- Unified single API that atomically combines core proxy compliance decision + agent security decision in one call path (currently separate surfaces)

## 10) File Map for Advisor Review
Start here for direct code inspection:
- App wiring: `engine/main.py`
- DB init: `engine/database/connection.py`
- Auth: `engine/dependencies.py`, `engine/auth/service.py`, `engine/auth/models.py`
- Proxy + policy enforcement: `engine/proxy/router.py`, `engine/proxy/interceptor.py`
- Detection: `engine/detection/engine.py`
- Action execution: `engine/actions/executor.py`
- Rulesets: `engine/rulesets/definitions/*.yaml`
- Vault: `engine/vault/models.py`, `engine/vault/vault.py`
- Audit: `engine/audit/models.py`, `engine/audit/signer.py`
- Compliance suite: `engine/compliance/models.py`, `engine/compliance/schemas.py`, `engine/compliance/service.py`, `engine/compliance/router.py`
- Agent Security suite: `engine/agent_security/models.py`, `engine/agent_security/schemas.py`, `engine/agent_security/service.py`, `engine/agent_security/router.py`
- Dashboard backend: `dashboard/backend/service.py`, `dashboard/backend/router.py`
