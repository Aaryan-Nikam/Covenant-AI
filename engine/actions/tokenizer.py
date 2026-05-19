"""
Ironpass — Tokenizer: replaces sensitive values with vault tokens.

Token format: TOK_{TYPE}_{8_CHAR_RANDOM_HEX}
Example: TOK_CARD_a4f2b891

The vault stores: token → encrypted(original_value)
The token map (token → display value) lives only in memory for the session.
"""

import logging
import uuid

from engine.vault.vault import TokenVault

logger = logging.getLogger("ironpass.actions.tokenizer")


class Tokenizer:
    """
    Replaces sensitive value with a vault token.
    Calls Token Vault to encrypt and store the original value.
    """

    def __init__(self, vault: TokenVault):
        self.vault = vault

    async def tokenize(
        self,
        value: str,
        data_type: str,
        agent_id: str,
        tenant_id: str,
    ) -> str:
        """
        1. Generate token: TOK_{TYPE}_{uuid4().hex[:8]}
        2. Store in vault: vault.store(token, value, tenant_id)
        3. Return token string
        """
        # Map data_type to short type code for token
        type_code = self._get_type_code(data_type)
        token_id = uuid.uuid4().hex[:8]
        token = f"TOK_{type_code}_{token_id}"

        # Store encrypted value in vault, bound to this tenant
        await self.vault.store(
            token=token,
            plaintext=value,
            data_type=data_type,
            agent_id=agent_id,
            tenant_id=tenant_id,
        )

        logger.debug(f"Tokenized: {data_type} → {token} (tenant={tenant_id})")
        return token

    def _get_type_code(self, data_type: str) -> str:
        """Map data_type to a short uppercase code for the token format."""
        type_codes = {
            "credit_card": "CARD",
            "ssn": "SSN",
            "person_name": "NAME",
            "email": "EMAIL",
            "phone_number": "PHONE",
            "passport": "PASSPORT",
            "bank_account": "BANK",
            "npi_number": "NPI",
            "date_of_birth": "DOB",
            "diagnosis_code": "DIAG",
            "ip_address": "IP",
            "api_key": "KEY",
            "password": "PWD",
            "cvv": "CVV",
            "card_expiry": "EXP",
        }
        return type_codes.get(data_type, data_type.upper()[:8])
