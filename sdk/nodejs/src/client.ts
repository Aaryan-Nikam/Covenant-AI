/**
 * Ironpass Node.js SDK — TypeScript Client.
 *
 * Usage:
 *   import { IronpassClient } from '@ironpass/sdk';
 *
 *   const client = new IronpassClient('http://localhost:8000');
 *
 *   const response = await client.scan({
 *     targetUrl: 'https://api.openai.com/v1/chat/completions',
 *     content: '{"messages": [...]}',
 *     agentId: 'my-agent',
 *     rulesets: ['pci_dss', 'hipaa'],
 *     headers: { Authorization: 'Bearer sk-...' },
 *   });
 */

// --- Types ---

export interface ScanRequest {
    targetUrl: string;
    content: string;
    agentId: string;
    rulesets: string[];
    headers?: Record<string, string>;
    method?: string;
}

export interface DetectionInfo {
    detector_id: string;
    data_type: string;
    position: number[];
    confidence: number;
    layer: number;
    ruleset_id: string;
}

export interface ActionInfo {
    detector_id: string;
    data_type: string;
    action: string;
    ruleset_id: string;
    log_level: string;
}

export interface ScanResponse {
    status: 'passed' | 'sanitized' | 'blocked';
    target_status_code: number | null;
    target_response: string | null;
    detections_count: number;
    detections: DetectionInfo[];
    actions_taken: ActionInfo[];
    audit_entry_id: string | null;
    latency_ms: number;
}

export interface RulesetInfo {
    ruleset_id: string;
    name: string;
    version: string;
    industry: string;
    description: string;
    detectors_count: number;
}

export interface HealthResponse {
    status: string;
    service: string;
    version: string;
    environment: string;
}

export class BlockedError extends Error {
    public readonly dataType: string;
    public readonly rulesetId: string;
    public readonly detectorId: string;

    constructor(dataType: string, rulesetId: string, detectorId: string, message: string) {
        super(message);
        this.name = 'BlockedError';
        this.dataType = dataType;
        this.rulesetId = rulesetId;
        this.detectorId = detectorId;
    }
}

// --- Client ---

export class IronpassClient {
    private baseUrl: string;
    private timeout: number;

    constructor(baseUrl: string = 'http://localhost:8000', timeout: number = 60000) {
        this.baseUrl = baseUrl.replace(/\/$/, '');
        this.timeout = timeout;
    }

    /**
     * Send content through the compliance proxy.
     * Returns ScanResponse on success.
     * Throws BlockedError if content is blocked (HTTP 403).
     */
    async scan(request: ScanRequest): Promise<ScanResponse> {
        const body = {
            target_url: request.targetUrl,
            content: request.content,
            agent_id: request.agentId,
            rulesets: request.rulesets,
            headers: request.headers || {},
            method: request.method || 'POST',
        };

        const response = await fetch(`${this.baseUrl}/proxy/scan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            signal: AbortSignal.timeout(this.timeout),
        });

        if (response.status === 403) {
            const detail = (await response.json()).detail || {};
            throw new BlockedError(
                detail.data_type || 'unknown',
                detail.ruleset_id || 'unknown',
                detail.detector_id || 'unknown',
                detail.error || 'Request blocked',
            );
        }

        if (!response.ok) {
            throw new Error(`Ironpass API error: ${response.status} ${response.statusText}`);
        }

        return (await response.json()) as ScanResponse;
    }

    /** List all available rulesets. */
    async listRulesets(): Promise<RulesetInfo[]> {
        const response = await fetch(`${this.baseUrl}/proxy/rulesets`, {
            signal: AbortSignal.timeout(this.timeout),
        });
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        const data = await response.json();
        return data.rulesets as RulesetInfo[];
    }

    /** Get detailed info about a specific ruleset. */
    async getRuleset(rulesetId: string): Promise<Record<string, unknown>> {
        const response = await fetch(`${this.baseUrl}/proxy/rulesets/${rulesetId}`, {
            signal: AbortSignal.timeout(this.timeout),
        });
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        return (await response.json()) as Record<string, unknown>;
    }

    /** Check if the Ironpass server is healthy. */
    async health(): Promise<HealthResponse> {
        const response = await fetch(`${this.baseUrl}/health`, {
            signal: AbortSignal.timeout(this.timeout),
        });
        if (!response.ok) throw new Error(`API error: ${response.status}`);
        return (await response.json()) as HealthResponse;
    }
}
