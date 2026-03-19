# Ironpass — Full System Architecture & Coding Agent Prompt

> Note: parts of this architecture document still use the earlier working name "AgentComply".
> In this repository, the project is presented as **Ironpass**.

> **This document is the single source of truth for building AgentComply.**
> Every component, every spec, every decision is documented here.
> A coding agent should be able to build every part of this system using only this document.
> Do not deviate from the specs. Do not add features not listed. Build exactly what is described.

---

## Project Overview

**What it is:** A modular compliance proxy that intercepts all AI agent requests, detects sensitive data, applies ruleset-defined actions, logs everything immutably, and returns sanitized data to the agent.

**What it is not:** A full agent orchestration platform. Not a cost optimizer. Not a human approval system. Not a rollback engine. Those are future versions. This document covers v1 only.

**Core principle:** The proxy is the only path. No agent request reaches an LLM or external API without passing through AgentComply first. There are no bypass routes. There are no exceptions.

---

## System At A Glance

```
[AI Agent]
    │
    │ HTTP request (prompt / data)
    ▼
[AgentComply Proxy] ← The system described in this document
    │   ├── Detection Engine
    │   ├── Action Executor
    │   ├── Token Vault
    │   ├── Ruleset Engine
    │   └── Audit Logger
    │
    │ Sanitized request (tokens replacing raw sensitive data)
    ▼
[LLM API / External Service]
    │
    │ Response (may contain tokens)
    ▼
[AgentComply Proxy] ← Reverse pass: de-tokenize for authorized output
    │
    ▼
[AI Agent receives clean response]
```

---

## Tech Stack — Locked In, No Debates

| Layer | Technology | Reason |
|---|---|---|
| API / Proxy | Python 3.11 + FastAPI | Async, fast, excellent ecosystem |
| Detection Layer 1 | Python `re` (regex) | Zero dependencies, deterministic |
| Detection Layer 2 | Luhn algorithm (custom impl) | Card validation, runs locally |
| Detection Layer 3 | spaCy 3.x (en_core_web_lg model) | NER, runs 100% locally, no external calls |
| Token Vault Storage | PostgreSQL 15 + SQLAlchemy | ACID, reliable, encrypted columns |
| Vault Encryption | AES-256-GCM via Python `cryptography` library | Industry standard |
| Key Management | HashiCorp Vault (self-hosted) or AWS KMS | Keys never in application DB |
| Audit Log DB | PostgreSQL (separate schema, append-only) | Immutable entries, signed |
| Log Signing | Python `cryptography` — HMAC-SHA256 | Tamper-proof chain |
| Cache / Sessions | Redis 7 | Fast lookups, rate limiting |
| Ruleset Format | YAML | Human-readable, version-controllable |
| Dashboard Backend | FastAPI (same service, separate router) | Keep stack unified |
| Dashboard Frontend | React 18 + TailwindCSS | Fast to build, clean UI |
| SDK | Python package + Node.js npm package | Two most common agent environments |
| Containerization | Docker + Docker Compose | Reproducible, easy self-hosting |
| Orchestration (prod) | Kubernetes (optional, documented) | For scale |
| Secrets | Environment variables + HashiCorp Vault | Never hardcoded |

---

## Repository Structure

```
agentcomply/
├── README.md
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── Makefile
│
├── engine/                          # Core backend — Python
│   ├── main.py                      # FastAPI app entry point
│   ├── config.py                    # All configuration, loaded from env
│   ├── dependencies.py              # FastAPI dependency injection
│   │
│   ├── proxy/                       # Component 1: Proxy Interceptor
│   │   ├── __init__.py
│   │   ├── router.py                # FastAPI router for proxy endpoints
│   │   ├── interceptor.py           # Core interception logic
│   │   └── request_model.py        # Pydantic models for requests
│   │
│   ├── detection/                   # Component 2: Detection Engine
│   │   ├── __init__.py
│   │   ├── engine.py                # Orchestrates all detectors
│   │   ├── regex_detector.py        # Layer 1: Pattern matching
│   │   ├── luhn_validator.py        # Layer 2: Card validation
│   │   ├── ner_detector.py          # Layer 3: spaCy NER
│   │   └── models.py                # Detection result data models
│   │
│   ├── actions/                     # Component 3: Action Executor
│   │   ├── __init__.py
│   │   ├── executor.py              # Routes to correct action handler
│   │   ├── tokenizer.py             # Calls vault, replaces with token
│   │   ├── masker.py                # Irreversible masking
│   │   ├── blocker.py               # Raises ComplianceViolation
│   │   └── pseudonymizer.py         # Consistent fake replacement
│   │
│   ├── vault/                       # Component 4: Token Vault
│   │   ├── __init__.py
│   │   ├── vault.py                 # Main vault interface
│   │   ├── encryption.py            # AES-256-GCM encrypt/decrypt
│   │   ├── key_manager.py           # Fetches keys from KMS/HashiCorp
│   │   └── models.py                # Vault DB models
│   │
│   ├── audit/                       # Component 5: Audit Logger
│   │   ├── __init__.py
│   │   ├── logger.py                # Main audit interface
│   │   ├── signer.py                # HMAC-SHA256 chain signing
│   │   └── models.py                # Audit log DB models
│   │
│   ├── rulesets/                    # Component 6: Ruleset Engine
│   │   ├── __init__.py
│   │   ├── loader.py                # Loads and validates YAML rulesets
│   │   ├── validator.py             # Validates ruleset schema
│   │   ├── registry.py              # Runtime registry of active rulesets
│   │   └── definitions/             # Built-in ruleset YAML files
│   │       ├── pci_dss.yaml
│   │       ├── hipaa.yaml
│   │       ├── gdpr.yaml
│   │       └── soc2.yaml
│   │
│   ├── database/                    # DB connection and migrations
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   ├── base.py                  # SQLAlchemy base
│   │   └── migrations/              # Alembic migrations
│   │
│   └── exceptions.py                # All custom exceptions defined here
│
├── dashboard/                       # Component 7: Dashboard
│   ├── backend/
│   │   ├── router.py                # Dashboard API routes
│   │   └── service.py               # Dashboard business logic
│   └── frontend/                    # React app
│       ├── src/
│       │   ├── App.jsx
│       │   ├── pages/
│       │   │   ├── Overview.jsx
│       │   │   ├── Violations.jsx
│       │   │   ├── AuditLog.jsx
│       │   │   └── Rulesets.jsx
│       │   └── components/
│       └── package.json
│
├── sdk/                             # Component 8: SDKs
│   ├── python/
│   │   ├── agentcomply/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   └── models.py
│   │   └── setup.py
│   └── nodejs/
│       ├── src/
│       │   ├── index.ts
│       │   └── client.ts
│       └── package.json
│
└── tests/
    ├── unit/
    ├── integration/
    └── fixtures/
```

---

## Component 1: Proxy Interceptor

### What It Is
The entry point for every request. An HTTP proxy built on FastAPI that receives agent requests, passes them through the full compliance pipeline, and either returns a sanitized version or raises a compliance violation error.

### What It Must Do
- Accept any HTTP POST request containing text data (prompt, message, document)
- Extract the text content regardless of format (raw string, JSON field, nested JSON)
- Pass content through Detection Engine → Action Executor → Audit Logger
- Return sanitized content in the same format the request arrived in
- On Block action: return HTTP 403 with structured error, never forward request
- On successful pass: forward sanitized request to the target URL (LLM API)
- On response from LLM: reverse pass — de-tokenize any tokens in the response
- Measure and log latency for every request

### What It Must NOT Do
- Never log raw sensitive data before the detection engine runs
- Never forward a request that has not passed through every active ruleset
- Never silently swallow errors — every failure must be logged and surfaced
- Never cache raw sensitive data
- Never trust agent-provided metadata about what data is or isn't sensitive

### File: `engine/proxy/interceptor.py`

```python
# IMPLEMENT EXACTLY AS DESCRIBED

class ProxyInterceptor:
    """
    Orchestrates the full compliance pipeline for every request.
    
    Pipeline order (MUST NOT change):
    1. Parse request
    2. Run Detection Engine on content
    3. Run Action Executor on detections
    4. Write Audit Log
    5. If no BLOCK: forward sanitized request to target
    6. Receive response from target
    7. Run reverse de-tokenization on response
    8. Return de-tokenized response to agent
    """
    
    def __init__(
        self,
        detection_engine: DetectionEngine,
        action_executor: ActionExecutor,
        audit_logger: AuditLogger,
        vault: TokenVault,
    ):
        # All dependencies injected — no direct instantiation inside this class
        pass

    async def process_request(
        self,
        content: str,
        agent_id: str,
        target_url: str,
        metadata: dict,
        active_rulesets: list[str],
    ) -> ProxyResult:
        # Returns ProxyResult containing:
        # - sanitized_content: str
        # - violations: list[Violation]
        # - was_blocked: bool
        # - audit_id: str
        # - latency_ms: int
        pass

    async def process_response(
        self,
        response_content: str,
        session_token_map: dict,
        agent_id: str,
    ) -> str:
        # De-tokenize response using session token map
        # Only restores tokens to authorized display values
        # Cards: show last 4 only
        # SSN: never restore in response
        # Names: restore fully
        pass
```

### File: `engine/proxy/router.py`

```python
# FastAPI router
# Endpoints:

# POST /proxy/execute
# Body: { agent_id, target_url, content, rulesets: ["pci_dss", "hipaa"] }
# Returns: { sanitized_content, violations, blocked, audit_id, latency_ms }

# POST /proxy/response
# Body: { agent_id, session_id, response_content }
# Returns: { detokenized_content }
```

### Request/Response Models

```python
# engine/proxy/request_model.py

class ProxyRequest(BaseModel):
    agent_id: str                    # Unique identifier for the agent
    target_url: HttpUrl              # Where to forward the sanitized request
    content: str                     # Raw text content to scan
    rulesets: list[str]             # Active ruleset IDs e.g. ["pci_dss"]
    metadata: dict = {}             # Optional: agent name, version, env

class ProxyResult(BaseModel):
    sanitized_content: str
    violations: list[ViolationResult]
    was_blocked: bool
    audit_id: str
    session_id: str                  # For de-tokenizing the response
    latency_ms: int

class ViolationResult(BaseModel):
    ruleset_id: str
    detector_id: str
    action_taken: str               # tokenized / masked / blocked / pseudonymized
    data_type: str                  # e.g. "credit_card", "ssn", "patient_name"
    position: tuple[int, int]       # Character position in original content
```

---

## Component 2: Detection Engine

### What It Is
Three-layer detector that scans text content and returns a list of all sensitive data found, with type, position, confidence score, and which layer detected it.

### What It Must Do
- Run all three detection layers in sequence on the same content
- Layer 1 (Regex): Fast pattern matching for known formats
- Layer 2 (Luhn): Validate card number candidates from Layer 1
- Layer 3 (NER): Context-aware detection for names, addresses, organisations
- Return unified list of Detection objects regardless of which layer found them
- Deduplicate overlapping detections (same position, different layers)
- Only run rulesets that are active for this request — never run all rulesets always
- Assign confidence score to every detection

### What It Must NOT Do
- Never call external APIs for detection — all detection runs locally
- Never load the spaCy model on every request — load once at startup, reuse
- Never return a detection without a confidence score
- Never run Layer 3 if the content has zero Layer 1/2 hits (performance)
- Never mutate the original content — return detections only, not modified text

### File: `engine/detection/engine.py`

```python
class DetectionEngine:
    """
    Orchestrates all detection layers.
    Returns list of Detection objects — never modifies content.
    """
    
    def __init__(self, ruleset_registry: RulesetRegistry):
        self.regex_detector = RegexDetector()
        self.luhn_validator = LuhnValidator()
        self.ner_detector = NERDetector()           # Loads spaCy at init
        self.ruleset_registry = ruleset_registry
    
    async def scan(
        self,
        content: str,
        active_rulesets: list[str],
    ) -> list[Detection]:
        """
        Returns all detections across all active rulesets.
        Deduplicates by position.
        """
        pass
```

### File: `engine/detection/regex_detector.py`

```python
class RegexDetector:
    """
    Layer 1: Pattern-based detection.
    Every pattern defined in active rulesets is run against content.
    Fast. Deterministic. No ML.
    """
    
    BUILT_IN_PATTERNS = {
        # PCI-DSS
        "visa":           r'\b4[0-9]{12}(?:[0-9]{3})?\b',
        "mastercard":     r'\b5[1-5][0-9]{14}\b',
        "amex":           r'\b3[47][0-9]{13}\b',
        "discover":       r'\b6(?:011|5[0-9]{2})[0-9]{12}\b',
        "cvv":            r'\b[0-9]{3,4}\b',
        "card_expiry":    r'\b(0[1-9]|1[0-2])\/?([0-9]{2}|[0-9]{4})\b',
        
        # HIPAA
        "ssn":            r'\b(?!000|666)[0-9]{3}-(?!00)[0-9]{2}-(?!0000)[0-9]{4}\b',
        "icd10_code":     r'\b[A-Z][0-9]{2}\.?[0-9A-Z]{0,4}\b',
        "dob":            r'\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b',
        "npi_number":     r'\b[0-9]{10}\b',
        
        # GDPR
        "email":          r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b',
        "eu_phone":       r'\b(\+?3[0-9]|0)[0-9\s\-]{7,14}\b',
        "passport":       r'\b[A-Z]{1,2}[0-9]{6,9}\b',
        "iban":           r'\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}\b',
        
        # General
        "us_phone":       r'\b(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
        "ip_address":     r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
        "api_key":        r'\b(sk|pk|api|key|token|secret)[-_]?[A-Za-z0-9]{20,}\b',
    }
    
    def scan(self, content: str, patterns: list[str]) -> list[Detection]:
        """
        Runs only the patterns specified by active rulesets.
        Never runs all patterns always.
        """
        pass
```

### File: `engine/detection/luhn_validator.py`

```python
class LuhnValidator:
    """
    Layer 2: Mathematical validation of card number candidates.
    Called only on regex hits for card number patterns.
    Eliminates false positives from Layer 1.
    
    Luhn algorithm:
    1. Starting from rightmost digit, double every second digit
    2. If doubled value > 9, subtract 9
    3. Sum all digits
    4. If total mod 10 == 0: valid card number
    """
    
    def validate(self, candidate: str) -> bool:
        """
        Returns True if candidate passes Luhn check.
        Strip spaces and hyphens before checking.
        """
        pass
    
    def filter_detections(self, detections: list[Detection]) -> list[Detection]:
        """
        Takes card number detections from regex.
        Returns only those that pass Luhn.
        Marks failed ones with confidence: 0.0 (excluded from results).
        """
        pass
```

### File: `engine/detection/ner_detector.py`

```python
class NERDetector:
    """
    Layer 3: Context-aware Named Entity Recognition.
    Uses spaCy en_core_web_lg model.
    
    CRITICAL: Load model ONCE at class instantiation.
    Never reload on each scan call.
    
    Detects:
    - PERSON: Patient names, employee names
    - ORG: Company names (for GDPR data mapping)
    - GPE: Geographic locations (for data residency)
    - DATE: DOB candidates (in medical context)
    
    Only runs when:
    - HIPAA ruleset is active AND content contains medical keywords
    - GDPR ruleset is active AND content contains EU indicators
    
    Context keywords for HIPAA:
    ["patient", "diagnosis", "prescription", "doctor", "hospital", 
     "medical", "health", "treatment", "clinical", "pharmacy"]
    
    Context keywords for GDPR:
    ["customer", "user", "subscriber", "resident", "citizen",
     "personal data", "data subject"]
    """
    
    def __init__(self):
        import spacy
        self.nlp = spacy.load("en_core_web_lg")   # Load once
    
    def scan(
        self,
        content: str,
        entity_types: list[str],
        context_required: list[str] | None,
    ) -> list[Detection]:
        """
        If context_required is set:
          Only run NER if at least one context keyword found in content.
          This prevents expensive NER on every request.
        """
        pass
```

### Detection Data Model

```python
# engine/detection/models.py

class Detection(BaseModel):
    detector_id: str           # e.g. "visa", "ssn", "patient_name"
    data_type: str             # e.g. "credit_card", "ssn", "person_name"
    value: str                 # The actual matched value (raw, before action)
    position: tuple[int, int]  # (start, end) character index in content
    confidence: float          # 0.0 to 1.0
    layer: int                 # 1 = regex, 2 = luhn, 3 = ner
    ruleset_id: str            # Which ruleset triggered this detection
    context: str | None        # Surrounding text for audit context (50 chars each side)
```

---

## Component 3: Action Executor

### What It Is
Takes the list of detections from the Detection Engine and applies the action defined in the ruleset config for each detection type. Returns modified content with sensitive data replaced.

### What It Must Do
- Read action type from ruleset config for each detection: tokenize / mask / block / pseudonymize
- Apply actions to content in reverse position order (end to start) to preserve character positions
- For tokenize: call Token Vault, get token, replace in content
- For mask: replace with type-appropriate mask string
- For block: immediately raise ComplianceViolation — do not process further
- For pseudonymize: generate consistent fake replacement (same input always same output)
- Return modified content and list of actions taken
- If multiple detections at overlapping positions: highest severity action wins

### What It Must NOT Do
- Never apply actions in forward order (breaks character positions)
- Never store the original value anywhere outside the vault
- Never generate pseudonyms randomly — they must be deterministic (same name always same fake name)
- Never silently skip a detection — every detection must result in a logged action

### Action Priority (when overlapping)
```
BLOCK > TOKENIZE > PSEUDONYMIZE > MASK
```

### File: `engine/actions/executor.py`

```python
class ActionExecutor:
    """
    Applies ruleset-defined actions to detected sensitive data.
    Processes detections in REVERSE position order to preserve indices.
    """
    
    def __init__(self, vault: TokenVault):
        self.vault = vault
        self.tokenizer = Tokenizer(vault)
        self.masker = Masker()
        self.blocker = Blocker()
        self.pseudonymizer = Pseudonymizer()
    
    async def execute(
        self,
        content: str,
        detections: list[Detection],
        ruleset_actions: dict,      # {detector_id: ActionConfig}
    ) -> ExecutionResult:
        """
        Returns ExecutionResult with:
        - modified_content: str
        - actions_taken: list[ActionTaken]
        - session_token_map: dict  # For de-tokenizing responses
        - was_blocked: bool
        """
        # Sort detections by position DESCENDING before processing
        pass
```

### File: `engine/actions/tokenizer.py`

```python
class Tokenizer:
    """
    Replaces sensitive value with a vault token.
    Token format: TOK_{TYPE}_{8_CHAR_RANDOM_HEX}
    Example: TOK_CARD_a4f2b891
    
    The vault stores: token → encrypted(original_value)
    The token map (token → original) lives only in memory for the session.
    After session ends, tokens can only be reversed via vault with auth.
    """
    
    async def tokenize(self, value: str, data_type: str) -> str:
        """
        1. Generate token: TOK_{TYPE}_{uuid4().hex[:8]}
        2. Store in vault: vault.store(token, value)
        3. Return token string
        """
        pass
```

### File: `engine/actions/masker.py`

```python
class Masker:
    """
    Irreversible. No vault. No recovery.
    Use when data must never be seen again, even by authorized users.
    
    Masking rules by type:
    - credit_card:   Show last 4 digits only → ****-****-****-9012
    - ssn:           Show last 4 digits only → ***-**-6789
    - cvv:           Full mask → ***
    - email:         Mask local part → j***@example.com
    - phone:         Show last 4 → ***-***-1234
    - dob:           Mask day and month → **/**/1985
    - api_key:       Full mask → [REDACTED_API_KEY]
    - person_name:   First name + last initial → John D.
    """
    
    def mask(self, value: str, data_type: str) -> str:
        pass
```

### File: `engine/actions/pseudonymizer.py`

```python
class Pseudonymizer:
    """
    Replaces with realistic but fake data.
    MUST be deterministic: same input always returns same output.
    Achieved via: HMAC(value, secret_key) → seed → fake data generator
    
    Use cases:
    - Patient names in HIPAA context: real name → consistent fake name
    - Company names in GDPR context: real company → consistent fake company
    
    Never use for financial data. Use tokenize for that.
    
    Implementation:
    1. HMAC-SHA256(original_value, PSEUDONYM_SECRET_KEY) → deterministic seed
    2. Use seed to select from name/company lists
    3. Same original value always returns same pseudonym
    4. Without the secret key, pseudonym cannot be reversed
    """
    
    def pseudonymize(self, value: str, data_type: str) -> str:
        pass
```

---

## Component 4: Token Vault

### What It Is
Encrypted storage for token-to-value mappings. The only place where real sensitive data lives after interception. Every value encrypted with AES-256-GCM before storage. Encryption keys never stored in the application database.

### What It Must Do
- Accept (token, plaintext_value, data_type, agent_id) → encrypt → store
- Accept (token, requesting_agent_id) → verify auth → decrypt → return value
- Encrypt every value with AES-256-GCM before writing to DB
- Fetch encryption key from key manager on every operation (never cache keys in memory longer than the operation)
- Log every store and retrieve operation to audit log
- Support token expiry — tokens older than configured TTL cannot be retrieved
- Support explicit token invalidation (for GDPR right-to-erasure)

### What It Must NOT Do
- Never store plaintext values anywhere — only ciphertext
- Never store encryption keys in the same database as vault data
- Never allow token retrieval without agent_id verification
- Never allow bulk token dumps — only single token retrieval
- Never expose vault internals via API — only through the ProxyInterceptor

### Database Schema

```sql
-- Vault table (PostgreSQL)
CREATE TABLE vault_tokens (
    token           VARCHAR(64) PRIMARY KEY,      -- TOK_CARD_a4f2b891
    ciphertext      BYTEA NOT NULL,               -- AES-256-GCM encrypted value
    nonce           BYTEA NOT NULL,               -- GCM nonce (unique per entry)
    data_type       VARCHAR(64) NOT NULL,          -- credit_card, ssn, etc.
    agent_id        VARCHAR(128) NOT NULL,         -- Who created this token
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,          -- TTL enforced
    invalidated_at  TIMESTAMPTZ,                   -- For GDPR erasure
    key_version     VARCHAR(32) NOT NULL           -- Which key version encrypted this
);

-- Index for cleanup jobs
CREATE INDEX idx_vault_expires ON vault_tokens(expires_at);
CREATE INDEX idx_vault_agent ON vault_tokens(agent_id);
```

### File: `engine/vault/vault.py`

```python
class TokenVault:
    """
    Single interface for all vault operations.
    No other component calls encryption directly.
    """
    
    def __init__(self, db_session, key_manager: KeyManager):
        self.db = db_session
        self.key_manager = key_manager
        self.encryptor = VaultEncryptor(key_manager)
    
    async def store(
        self,
        token: str,
        plaintext: str,
        data_type: str,
        agent_id: str,
        ttl_hours: int = 24,
    ) -> bool:
        """
        Encrypts plaintext and stores with token as key.
        Returns True on success.
        Logs the store operation (not the value) to audit log.
        """
        pass
    
    async def retrieve(
        self,
        token: str,
        requesting_agent_id: str,
    ) -> str | None:
        """
        Verifies agent_id matches token owner.
        Checks token not expired or invalidated.
        Decrypts and returns plaintext.
        Returns None if not found or unauthorized.
        Logs every retrieval attempt (success and failure).
        """
        pass
    
    async def invalidate(self, token: str, reason: str) -> bool:
        """
        Sets invalidated_at. Token cannot be retrieved after this.
        Used for GDPR right-to-erasure requests.
        """
        pass
    
    async def cleanup_expired(self) -> int:
        """
        Deletes expired tokens.
        Run as scheduled job every 24 hours.
        Returns count of deleted tokens.
        """
        pass
```

### File: `engine/vault/encryption.py`

```python
class VaultEncryptor:
    """
    AES-256-GCM encryption and decryption.
    
    Why AES-256-GCM:
    - AES-256: 256-bit key, computationally infeasible to brute force
    - GCM mode: Provides both encryption AND authentication
      (detects if ciphertext was tampered with)
    
    Implementation rules:
    - Generate new random 96-bit nonce for EVERY encryption operation
    - Never reuse a nonce with the same key
    - Store nonce alongside ciphertext in DB
    - On decryption: GCM authentication tag verified automatically
      If tampered: InvalidTag exception raised, log critical alert
    
    Key format: 32 bytes (256 bits), fetched from KeyManager
    """
    
    def encrypt(self, plaintext: str, key: bytes) -> tuple[bytes, bytes]:
        """Returns (ciphertext, nonce)"""
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        # Generate random 96-bit nonce
        # Encrypt with AESGCM
        # Return (ciphertext_with_tag, nonce)
        pass
    
    def decrypt(self, ciphertext: bytes, nonce: bytes, key: bytes) -> str:
        """
        Returns plaintext string.
        Raises InvalidTag if ciphertext was tampered with.
        NEVER catch InvalidTag silently — always propagate and alert.
        """
        pass
```

### File: `engine/vault/key_manager.py`

```python
class KeyManager:
    """
    Fetches encryption keys from external key management system.
    Never stores keys in application DB.
    Never caches keys longer than the current operation.
    
    Supports two backends (configured via environment variable KEY_BACKEND):
    1. HashiCorp Vault (self-hosted): KEY_BACKEND=hashicorp
    2. AWS KMS: KEY_BACKEND=aws_kms
    3. Local (development ONLY, never production): KEY_BACKEND=local
    
    Key versioning:
    - Keys are versioned (v1, v2, v3...)
    - Old keys kept for decryption of old tokens
    - New tokens always encrypted with current key version
    - Key rotation: increment version, old tokens migrate on next retrieval
    """
    
    async def get_current_key(self) -> tuple[bytes, str]:
        """Returns (key_bytes, key_version)"""
        pass
    
    async def get_key_by_version(self, version: str) -> bytes:
        """For decrypting tokens encrypted with older key versions"""
        pass
```

---

## Component 5: Audit Logger

### What It Is
Append-only, cryptographically signed audit log. Records every proxy request, every detection, every action taken, and every vault operation. Entries cannot be modified after writing.

### What It Must Do
- Write a log entry for every proxy request, regardless of outcome
- Include: timestamp, agent_id, request hash, rulesets applied, detections found, actions taken, latency, outcome
- Cryptographically sign each entry using HMAC-SHA256
- Chain entries: each entry includes hash of previous entry (blockchain-style)
- This means tampering with any entry breaks the chain and is detectable
- Support querying by: agent_id, time range, ruleset_id, violation type
- Generate compliance reports in JSON and PDF format
- Never delete entries — only mark as archived after retention period

### What It Must NOT Do
- Never log raw sensitive values — only detection type and position
- Never allow UPDATE or DELETE on audit entries via any API
- Never write to audit log synchronously in the request path — use background task
  (Audit write failure must not block the proxy response)
- Never skip logging a request even if it was blocked

### Database Schema

```sql
-- Audit log (PostgreSQL, separate schema from vault)
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    entry_id        UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_id        VARCHAR(128) NOT NULL,
    request_hash    VARCHAR(64) NOT NULL,        -- SHA-256 of sanitized request
    rulesets_used   TEXT[] NOT NULL,             -- ["pci_dss", "hipaa"]
    detections      JSONB NOT NULL,              -- list of Detection objects (no raw values)
    actions_taken   JSONB NOT NULL,              -- list of ActionTaken objects
    was_blocked     BOOLEAN NOT NULL DEFAULT FALSE,
    target_url      VARCHAR(512),
    latency_ms      INTEGER NOT NULL,
    outcome         VARCHAR(32) NOT NULL,        -- "passed", "blocked", "error"
    hmac_signature  VARCHAR(64) NOT NULL,        -- HMAC-SHA256 of this entry
    prev_entry_hash VARCHAR(64),                 -- Hash of previous entry (chain)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- No UPDATE permitted on this table — enforced by DB role permissions
-- Application DB user has INSERT and SELECT only, never UPDATE or DELETE
REVOKE UPDATE, DELETE ON audit_log FROM agentcomply_app;

CREATE INDEX idx_audit_agent ON audit_log(agent_id, timestamp DESC);
CREATE INDEX idx_audit_outcome ON audit_log(outcome, timestamp DESC);
CREATE INDEX idx_audit_rulesets ON audit_log USING GIN(rulesets_used);
```

### File: `engine/audit/logger.py`

```python
class AuditLogger:
    """
    Append-only audit logger with cryptographic chain.
    
    Write flow:
    1. Build entry dict from request data (NO raw sensitive values)
    2. Get hash of last entry in DB (for chain)
    3. Compute HMAC-SHA256 of (entry_json + prev_hash) using AUDIT_HMAC_KEY
    4. Write to DB with signature and prev_hash
    5. All writes are async background tasks — never block proxy response
    
    Chain verification:
    - Recompute HMAC for each entry
    - Verify prev_entry_hash matches actual previous entry hash
    - Any mismatch = tampering detected = critical alert
    """
    
    async def write(
        self,
        agent_id: str,
        request_hash: str,
        rulesets_used: list[str],
        detections: list[Detection],
        actions_taken: list[ActionTaken],
        was_blocked: bool,
        target_url: str,
        latency_ms: int,
        outcome: str,
    ) -> str:
        """Returns entry_id. Runs as background task."""
        pass
    
    async def verify_chain(self, from_entry_id: str, to_entry_id: str) -> ChainVerifyResult:
        """
        Verifies integrity of audit chain between two entry IDs.
        Returns: {valid: bool, tampered_entry_id: str | None}
        Used for compliance audits.
        """
        pass
    
    async def query(
        self,
        agent_id: str | None,
        from_time: datetime | None,
        to_time: datetime | None,
        ruleset_id: str | None,
        outcome: str | None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEntry]:
        pass
    
    async def generate_compliance_report(
        self,
        from_time: datetime,
        to_time: datetime,
        rulesets: list[str],
        format: str,  # "json" or "pdf"
    ) -> bytes:
        """
        Generates audit report for compliance teams / SOC2 auditors.
        JSON: full data export
        PDF: formatted report with summary stats and sample entries
        """
        pass
```

---

## Component 6: Ruleset Engine

### What It Is
Loads compliance ruleset definitions from YAML files, validates their schema, registers them in memory at startup, and provides the active ruleset config for each request.

### What It Must Do
- Load all YAML ruleset files from `engine/rulesets/definitions/` at startup
- Validate every ruleset against a strict schema before loading (reject invalid ones)
- Register valid rulesets in an in-memory registry
- Allow rulesets to be activated/deactivated per tenant via API (no restart required)
- Provide the merged config for any combination of active rulesets
- Support adding a new ruleset by dropping a YAML file (no code changes required)

### What It Must NOT Do
- Never run a ruleset that failed schema validation
- Never allow a ruleset to define an action type not in the supported list
- Never require a code change to add a new industry ruleset
- Never merge conflicting actions for the same detector — highest severity wins

### Ruleset YAML Schema

```yaml
# Every ruleset MUST have all these fields — no optional top-level fields

ruleset_id: string          # Unique. snake_case. e.g. "pci_dss"
name: string                # Human readable. e.g. "PCI-DSS v4.0"
version: string             # e.g. "4.0"
industry: string            # finance / healthcare / legal / general
description: string

detectors:
  - id: string              # Unique within ruleset. snake_case.
    name: string
    data_type: string       # Maps to action config key
    layer: integer          # 1 (regex) or 3 (ner). Layer 2 is automatic for cards.
    
    # For layer 1 (regex):
    patterns: list[string]  # List of regex patterns
    
    # For layer 3 (ner):
    entity_class: string    # PERSON / ORG / GPE / DATE
    context_required:       # Optional — only run NER if these words present
      keywords: list[string]
    
    confidence_threshold: float  # 0.0 to 1.0. Default 0.9.

actions:
  detector_id:              # Must match a detector id above
    primary: string         # tokenize / mask / block / pseudonymize
    fallback: string        # Action if primary fails. Usually "block".
    log_level: string       # critical / high / medium / low

audit:
  retention_days: integer
  required_fields: list[string]
```

### Built-in Ruleset: PCI-DSS

```yaml
ruleset_id: pci_dss
name: "PCI-DSS v4.0"
version: "4.0"
industry: finance
description: "Payment Card Industry Data Security Standard v4.0. Protects cardholder data."

detectors:
  - id: visa_card
    name: "Visa Card Number"
    data_type: credit_card
    layer: 1
    patterns:
      - '\b4[0-9]{12}(?:[0-9]{3})?\b'
    confidence_threshold: 0.95

  - id: mastercard
    name: "Mastercard Number"
    data_type: credit_card
    layer: 1
    patterns:
      - '\b5[1-5][0-9]{14}\b'
      - '\b2(?:2[2-9][1-9]|[3-6][0-9]{2}|7[01][0-9]|720)[0-9]{12}\b'
    confidence_threshold: 0.95

  - id: amex_card
    name: "American Express Card Number"
    data_type: credit_card
    layer: 1
    patterns:
      - '\b3[47][0-9]{13}\b'
    confidence_threshold: 0.95

  - id: discover_card
    name: "Discover Card Number"
    data_type: credit_card
    layer: 1
    patterns:
      - '\b6(?:011|5[0-9]{2})[0-9]{12}\b'
    confidence_threshold: 0.95

  - id: cvv
    name: "Card Verification Value"
    data_type: cvv
    layer: 1
    patterns:
      - '\b[0-9]{3,4}\b'
    confidence_threshold: 0.7

  - id: card_expiry
    name: "Card Expiry Date"
    data_type: card_expiry
    layer: 1
    patterns:
      - '\b(0[1-9]|1[0-2])\/?([0-9]{2}|[0-9]{4})\b'
    confidence_threshold: 0.8

actions:
  credit_card:
    primary: tokenize
    fallback: block
    log_level: critical

  cvv:
    primary: block
    fallback: block
    log_level: critical

  card_expiry:
    primary: mask
    fallback: block
    log_level: high

audit:
  retention_days: 365
  required_fields:
    - timestamp
    - agent_id
    - data_type
    - action_taken
    - request_hash
```

### Built-in Ruleset: HIPAA

```yaml
ruleset_id: hipaa
name: "HIPAA"
version: "2024"
industry: healthcare
description: "Health Insurance Portability and Accountability Act. Protects Protected Health Information (PHI)."

detectors:
  - id: ssn
    name: "Social Security Number"
    data_type: ssn
    layer: 1
    patterns:
      - '\b(?!000|666)[0-9]{3}-(?!00)[0-9]{2}-(?!0000)[0-9]{4}\b'
    confidence_threshold: 0.99

  - id: patient_name
    name: "Patient Name"
    data_type: person_name
    layer: 3
    entity_class: PERSON
    context_required:
      keywords:
        - patient
        - diagnosis
        - prescription
        - doctor
        - hospital
        - medical
        - health
        - treatment
        - clinical
        - pharmacy
        - symptom
    confidence_threshold: 0.85

  - id: icd10
    name: "ICD-10 Diagnosis Code"
    data_type: diagnosis_code
    layer: 1
    patterns:
      - '\b[A-Z][0-9]{2}\.?[0-9A-Z]{0,4}\b'
    confidence_threshold: 0.9

  - id: dob
    name: "Date of Birth"
    data_type: date_of_birth
    layer: 1
    patterns:
      - '\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b'
    confidence_threshold: 0.8

  - id: npi
    name: "National Provider Identifier"
    data_type: npi_number
    layer: 1
    patterns:
      - '\b[0-9]{10}\b'
    confidence_threshold: 0.75

actions:
  ssn:
    primary: tokenize
    fallback: block
    log_level: critical

  person_name:
    primary: pseudonymize
    fallback: mask
    log_level: high

  diagnosis_code:
    primary: mask
    fallback: block
    log_level: high

  date_of_birth:
    primary: mask
    fallback: block
    log_level: high

  npi_number:
    primary: tokenize
    fallback: block
    log_level: high

audit:
  retention_days: 2555
  required_fields:
    - timestamp
    - agent_id
    - data_type
    - action_taken
    - access_reason
    - request_hash
```

### Built-in Ruleset: GDPR

```yaml
ruleset_id: gdpr
name: "GDPR"
version: "2018"
industry: general
description: "General Data Protection Regulation. Protects EU personal data."

detectors:
  - id: email
    name: "Email Address"
    data_type: email
    layer: 1
    patterns:
      - '\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b'
    confidence_threshold: 0.99

  - id: eu_phone
    name: "EU Phone Number"
    data_type: phone_number
    layer: 1
    patterns:
      - '\b(\+?3[0-9]|0)[0-9\s\-]{7,14}\b'
    confidence_threshold: 0.85

  - id: passport
    name: "Passport Number"
    data_type: passport
    layer: 1
    patterns:
      - '\b[A-Z]{1,2}[0-9]{6,9}\b'
    confidence_threshold: 0.8

  - id: iban
    name: "IBAN Bank Account"
    data_type: bank_account
    layer: 1
    patterns:
      - '\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}\b'
    confidence_threshold: 0.95

  - id: eu_person_name
    name: "EU Data Subject Name"
    data_type: person_name
    layer: 3
    entity_class: PERSON
    context_required:
      keywords:
        - customer
        - user
        - subscriber
        - resident
        - citizen
        - data subject
        - personal data
    confidence_threshold: 0.8

actions:
  email:
    primary: mask
    fallback: block
    log_level: high

  phone_number:
    primary: mask
    fallback: block
    log_level: high

  passport:
    primary: tokenize
    fallback: block
    log_level: critical

  bank_account:
    primary: tokenize
    fallback: block
    log_level: critical

  person_name:
    primary: pseudonymize
    fallback: mask
    log_level: medium

audit:
  retention_days: 1095
  required_fields:
    - timestamp
    - agent_id
    - data_type
    - action_taken
    - request_hash
    - data_subject_region
```

### Built-in Ruleset: SOC2

```yaml
ruleset_id: soc2
name: "SOC2 Type II"
version: "2017"
industry: general
description: "SOC2 compliance. Focuses on audit trail completeness and access logging."

detectors:
  - id: api_key
    name: "API Key or Secret"
    data_type: api_key
    layer: 1
    patterns:
      - '\b(sk|pk|api|key|token|secret)[-_]?[A-Za-z0-9]{20,}\b'
      - '\bsk-[A-Za-z0-9]{48}\b'
    confidence_threshold: 0.9

  - id: internal_ip
    name: "Internal IP Address"
    data_type: ip_address
    layer: 1
    patterns:
      - '\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'
      - '\b192\.168\.\d{1,3}\.\d{1,3}\b'
      - '\b172\.(1[6-9]|2[0-9]|3[01])\.\d{1,3}\.\d{1,3}\b'
    confidence_threshold: 0.95

  - id: password_pattern
    name: "Password in Content"
    data_type: password
    layer: 1
    patterns:
      - '(?i)(password|passwd|pwd)\s*[=:]\s*\S+'
    confidence_threshold: 0.85

actions:
  api_key:
    primary: block
    fallback: block
    log_level: critical

  ip_address:
    primary: mask
    fallback: block
    log_level: medium

  password:
    primary: block
    fallback: block
    log_level: critical

audit:
  retention_days: 365
  required_fields:
    - timestamp
    - agent_id
    - data_type
    - action_taken
    - request_hash
```

### File: `engine/rulesets/loader.py`

```python
class RulesetLoader:
    """
    Loads and validates YAML rulesets at startup.
    Any ruleset that fails validation is rejected with clear error message.
    Valid rulesets are registered in RulesetRegistry.
    
    Validation checks:
    - All required top-level fields present
    - Every detector has required fields (id, name, data_type, layer)
    - Layer 1 detectors have patterns list
    - Layer 3 detectors have entity_class
    - Every detector id referenced in actions exists in detectors
    - action.primary is one of: tokenize, mask, block, pseudonymize
    - audit.retention_days is positive integer
    """
    
    DEFINITIONS_PATH = "engine/rulesets/definitions/"
    
    def load_all(self) -> dict[str, Ruleset]:
        """
        Loads all YAML files from definitions directory.
        Returns dict of {ruleset_id: Ruleset}.
        Logs warning for any failed rulesets, continues loading others.
        """
        pass
    
    def load_from_file(self, filepath: str) -> Ruleset:
        pass
    
    def validate(self, raw: dict) -> Ruleset:
        """Raises RulesetValidationError with specific field message if invalid"""
        pass
```

---

## Component 7: Dashboard

### What It Is
A web dashboard for operators and compliance teams to monitor agent activity, view violations, download reports, and manage active rulesets.

### What It Must Do
- Show real-time (30-second refresh) overview: requests processed, violations, blocks
- Show paginated list of audit log entries with filtering
- Show violation detail: detection type, ruleset, action taken (no raw values ever)
- Allow downloading compliance report (JSON or PDF) for a date range
- Allow activating/deactivating rulesets per tenant
- Show chain integrity status (is the audit log tampered?)
- Require authentication (API key or JWT for operator access)

### What It Must NOT Do
- Never display raw sensitive values — only detection types and masked previews
- Never allow modifying audit log entries
- Never expose vault tokens or encrypted data
- No public access — dashboard always behind authentication

### Dashboard Pages

```
1. Overview
   - Total requests today / this week / this month
   - Violation count by ruleset
   - Top violation types (bar chart)
   - Recent blocks (table, last 10)
   - System health (vault status, DB status)

2. Audit Log
   - Paginated table: timestamp, agent_id, outcome, rulesets, violations count
   - Filters: agent_id, date range, outcome, ruleset
   - Click row → detail view (full detection list, actions taken, latency)
   - Export filtered results as JSON

3. Violations
   - Violations only (blocked or modified requests)
   - Grouped by: data_type, agent_id, ruleset
   - Time series chart (violations per hour)

4. Compliance Reports
   - Select date range + rulesets
   - Generate JSON or PDF report
   - Download immediately

5. Rulesets
   - List all available rulesets with status (active/inactive)
   - Toggle active/inactive per tenant
   - View ruleset config (read-only)

6. Chain Integrity
   - Verify audit log chain for a date range
   - Shows: valid / tampered (and which entry)
   - For SOC2 auditors
```

---

## Component 8: SDK

### What It Is
Client libraries in Python and Node.js that make it 3 lines of code to integrate AgentComply into any agent.

### Python SDK Usage

```python
from agentcomply import AgentComply

client = AgentComply(
    api_key="ac_sk_xxxx",
    agent_id="my_sales_agent",
    rulesets=["pci_dss", "soc2"]
)

# Use exactly like you'd call OpenAI directly
result = await client.proxy(
    content=prompt,
    target_url="https://api.openai.com/v1/chat/completions",
    target_payload=openai_payload
)

# result.content is sanitized
# result.violations is list of what was caught
# result.was_blocked is bool
```

### Node.js SDK Usage

```typescript
import { AgentComply } from '@agentcomply/sdk';

const client = new AgentComply({
  apiKey: 'ac_sk_xxxx',
  agentId: 'my_sales_agent',
  rulesets: ['pci_dss', 'soc2']
});

const result = await client.proxy({
  content: prompt,
  targetUrl: 'https://api.openai.com/v1/chat/completions',
  targetPayload: openaiPayload
});
```

### SDK Must Handle
- Authentication header injection
- Retry with exponential backoff (3 attempts, 1s/2s/4s)
- Timeout: 10 seconds default, configurable
- Parse and surface violations in structured format
- Raise typed exceptions (BlockedByCompliance, ProxyError, AuthError)
- Never silence errors

---

## Environment Variables

```bash
# Required — no defaults

DATABASE_URL=postgresql://user:pass@localhost:5432/agentcomply
REDIS_URL=redis://localhost:6379/0
AUDIT_HMAC_KEY=          # 64 hex chars — secret for signing audit chain
PSEUDONYM_SECRET_KEY=    # 64 hex chars — secret for deterministic pseudonyms

# Key management — choose one backend
KEY_BACKEND=hashicorp    # or "aws_kms" or "local" (dev only)

# If hashicorp:
HASHICORP_VAULT_URL=https://vault.internal:8200
HASHICORP_VAULT_TOKEN=

# If aws_kms:
AWS_KMS_KEY_ID=
AWS_REGION=

# Application
APP_ENV=production       # or "development"
LOG_LEVEL=INFO
API_HOST=0.0.0.0
API_PORT=8000

# Token TTL
VAULT_TOKEN_TTL_HOURS=24

# spaCy model (must be downloaded before start)
SPACY_MODEL=en_core_web_lg
```

---

## Database Setup

```sql
-- Run once at setup
-- Two separate schemas: vault and audit
-- App user has different permissions on each

CREATE SCHEMA vault;
CREATE SCHEMA audit;

-- App user permissions
GRANT SELECT, INSERT ON vault.vault_tokens TO agentcomply_app;
GRANT SELECT, INSERT ON audit.audit_log TO agentcomply_app;
-- Explicit deny on UPDATE and DELETE for both schemas
REVOKE UPDATE, DELETE ON vault.vault_tokens FROM agentcomply_app;
REVOKE UPDATE, DELETE ON audit.audit_log FROM agentcomply_app;
```

---

## Docker Compose (Development)

```yaml
version: '3.9'

services:
  api:
    build: ./engine
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://agentcomply:secret@db:5432/agentcomply
      - REDIS_URL=redis://redis:6379/0
      - KEY_BACKEND=local
      - APP_ENV=development
    depends_on:
      - db
      - redis
    volumes:
      - ./engine:/app

  dashboard:
    build: ./dashboard/frontend
    ports:
      - "3000:3000"
    depends_on:
      - api

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: agentcomply
      POSTGRES_USER: agentcomply
      POSTGRES_PASSWORD: secret
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

---

## Critical Rules For The Coding Agent

These rules override any assumptions. Read all of them before writing any code.

1. **Detection before logging.** The detection engine runs before any logging. Raw content is never written to any log.

2. **Actions in reverse order.** When applying actions to content, always sort detections by position descending and process end-to-start. Never process start-to-end.

3. **Vault keys never in app DB.** Encryption keys live only in HashiCorp Vault or AWS KMS. The app database stores only ciphertext and nonces.

4. **Audit log is append-only.** The DB role for the audit table has INSERT and SELECT only. No UPDATE. No DELETE. This is enforced at database level, not just application level.

5. **spaCy loads once.** The NER model is loaded in `NERDetector.__init__`. It is never reloaded per request. The `NERDetector` is a singleton injected via FastAPI dependency.

6. **Audit writes are background tasks.** `audit_logger.write()` is always called with `asyncio.create_task()` or FastAPI `BackgroundTasks`. It never blocks the proxy response.

7. **Block is immediate.** When an action of type `block` is triggered, the `ActionExecutor` raises `ComplianceViolation` immediately. No further detections are processed. The request is not forwarded.

8. **No external calls for detection.** All three detection layers run locally. No third-party ML API. No external service.

9. **Ruleset YAML is the only config.** Adding a new ruleset means adding a YAML file. No Python code changes required for new rulesets.

10. **SDK never swallows errors.** All proxy errors surface to the agent as typed exceptions. No silent failures.

11. **CVV is always blocked.** CVV action.primary must always be `block`. No ruleset may override CVV to tokenize or mask. If a ruleset YAML attempts this, the validator rejects it.

12. **Nonce is unique per encrypt call.** `VaultEncryptor.encrypt()` generates a fresh random 96-bit nonce on every call using `os.urandom(12)`. Never reuse nonces.

---

## What Success Looks Like

After this system is built, an agent operator can:

1. Spin up AgentComply with `docker-compose up` in under 5 minutes
2. Add 3 lines to their agent code using the SDK
3. Watch their agent's requests pass through the proxy
4. See any PCI/HIPAA/GDPR data caught, tokenized, and logged
5. Open the dashboard and see every violation
6. Download a PDF compliance report for their auditor
7. Add a new industry ruleset by dropping a YAML file with zero code changes
