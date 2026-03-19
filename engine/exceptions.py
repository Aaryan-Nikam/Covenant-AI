"""
Ironpass — All custom exceptions defined here.

Every component raises exceptions from this module.
No other module defines its own exception classes.
"""


class IronpassError(Exception):
    """Base exception for all Ironpass errors."""
    pass


# ---------------------------------------------------------------------------
# Compliance Exceptions
# ---------------------------------------------------------------------------

class ComplianceViolation(IronpassError):
    """
    Raised when a BLOCK action is triggered.
    The request is NOT forwarded. HTTP 403 returned to agent.
    
    Critical Rule #7: Block is immediate — no further detections processed.
    """

    def __init__(
        self,
        ruleset_id: str,
        detector_id: str,
        data_type: str,
        message: str = "Compliance violation: blocked content detected",
    ):
        self.ruleset_id = ruleset_id
        self.detector_id = detector_id
        self.data_type = data_type
        super().__init__(message)


# ---------------------------------------------------------------------------
# Ruleset Exceptions
# ---------------------------------------------------------------------------

class RulesetValidationError(IronpassError):
    """Raised when a YAML ruleset fails schema validation."""

    def __init__(self, ruleset_id: str, field: str, reason: str):
        self.ruleset_id = ruleset_id
        self.field = field
        self.reason = reason
        super().__init__(
            f"Ruleset '{ruleset_id}' validation failed: "
            f"field '{field}' — {reason}"
        )


class RulesetNotFoundError(IronpassError):
    """Raised when a requested ruleset is not in the registry."""

    def __init__(self, ruleset_id: str):
        self.ruleset_id = ruleset_id
        super().__init__(f"Ruleset '{ruleset_id}' not found in registry")


# ---------------------------------------------------------------------------
# Vault Exceptions
# ---------------------------------------------------------------------------

class VaultError(IronpassError):
    """Base exception for vault operations."""
    pass


class VaultEncryptionError(VaultError):
    """Raised when encryption fails."""
    pass


class VaultDecryptionError(VaultError):
    """
    Raised when decryption fails.
    This includes tampered ciphertext (InvalidTag from AES-GCM).
    NEVER catch silently — always propagate and alert.
    """
    pass


class VaultTokenExpiredError(VaultError):
    """Raised when a token has expired past its TTL."""

    def __init__(self, token: str):
        self.token = token
        super().__init__(f"Token '{token}' has expired")


class VaultTokenInvalidatedError(VaultError):
    """Raised when a token has been explicitly invalidated (e.g., GDPR erasure)."""

    def __init__(self, token: str):
        self.token = token
        super().__init__(f"Token '{token}' has been invalidated")


class VaultUnauthorizedError(VaultError):
    """Raised when requesting agent_id does not match token owner."""
    pass


# ---------------------------------------------------------------------------
# Key Management Exceptions
# ---------------------------------------------------------------------------

class KeyManagementError(IronpassError):
    """Raised when key retrieval from KMS / HashiCorp Vault fails."""
    pass


# ---------------------------------------------------------------------------
# Audit Exceptions
# ---------------------------------------------------------------------------

class AuditChainError(IronpassError):
    """Raised when audit chain integrity verification fails (tampering detected)."""

    def __init__(self, entry_id: str, message: str = "Audit chain integrity violation"):
        self.entry_id = entry_id
        super().__init__(f"{message} at entry '{entry_id}'")


# ---------------------------------------------------------------------------
# Proxy Exceptions
# ---------------------------------------------------------------------------

class ProxyError(IronpassError):
    """Base exception for proxy operations."""
    pass


class ProxyTargetError(ProxyError):
    """Raised when the target LLM/API returns an error."""

    def __init__(self, target_url: str, status_code: int, detail: str = ""):
        self.target_url = target_url
        self.status_code = status_code
        self.detail = detail
        super().__init__(
            f"Target '{target_url}' returned {status_code}: {detail}"
        )


class ProxyAuthError(ProxyError):
    """Raised for authentication/authorization failures."""
    pass


# ---------------------------------------------------------------------------
# Configuration Exceptions
# ---------------------------------------------------------------------------

class ConfigurationError(IronpassError):
    """Raised when required configuration is missing or invalid."""
    pass
