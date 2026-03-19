"""
Ironpass — Masker: irreversible data masking.

No vault. No recovery. Use when data must never be seen again.

Masking rules by type (from architecture doc):
  - credit_card:   Show last 4 digits → ****-****-****-9012
  - ssn:           Show last 4 digits → ***-**-6789
  - cvv:           Full mask → ***
  - email:         Mask local part → j***@example.com
  - phone:         Show last 4 → ***-***-1234
  - dob:           Mask day and month → **/**/1985
  - api_key:       Full mask → [REDACTED_API_KEY]
  - person_name:   First name + last initial → John D.
  - ip_address:    Mask last two octets → 192.168.*.*
  - password:      Full mask → [REDACTED_PASSWORD]
  - passport:      Show first 2 chars → AB*******
  - bank_account:  Show last 4 → ****...****1234
"""

import logging
import re

logger = logging.getLogger("ironpass.actions.masker")


class Masker:
    """
    Irreversible masking. No vault. No recovery.
    Each data type has specific masking rules for compliance.
    """

    def mask(self, value: str, data_type: str, mask_type: str = "partial") -> str:
        """Apply type-appropriate masking to the value based on mask_type strategy."""
        if mask_type == "length_preserving":
            return "*" * len(value)
        elif mask_type == "label":
            return f"[{data_type.upper()}]"
            
        maskers = {
            "credit_card": self._mask_credit_card,
            "ssn": self._mask_ssn,
            "cvv": self._mask_cvv,
            "email": self._mask_email,
            "phone_number": self._mask_phone,
            "date_of_birth": self._mask_dob,
            "api_key": self._mask_api_key,
            "person_name": self._mask_person_name,
            "ip_address": self._mask_ip,
            "password": self._mask_password,
            "passport": self._mask_passport,
            "bank_account": self._mask_bank_account,
            "card_expiry": self._mask_card_expiry,
            "diagnosis_code": self._mask_generic,
            "npi_number": self._mask_generic,
        }

        masker_fn = maskers.get(data_type, self._mask_generic)
        masked = masker_fn(value)
        logger.debug(f"Masked {data_type}: {len(value)} chars → {masked}")
        return masked

    def _mask_credit_card(self, value: str) -> str:
        """Show last 4 digits: ****-****-****-9012"""
        digits = re.sub(r'\D', '', value)
        if len(digits) >= 4:
            return f"****-****-****-{digits[-4:]}"
        return "****-****-****-****"

    def _mask_ssn(self, value: str) -> str:
        """Show last 4 digits: ***-**-6789"""
        digits = re.sub(r'\D', '', value)
        if len(digits) >= 4:
            return f"***-**-{digits[-4:]}"
        return "***-**-****"

    def _mask_cvv(self, value: str) -> str:
        """Full mask: ***"""
        return "***"

    def _mask_email(self, value: str) -> str:
        """Mask local part: j***@example.com"""
        parts = value.split("@")
        if len(parts) == 2:
            local = parts[0]
            domain = parts[1]
            if len(local) > 1:
                return f"{local[0]}***@{domain}"
            return f"***@{domain}"
        return "[REDACTED_EMAIL]"

    def _mask_phone(self, value: str) -> str:
        """Show last 4: ***-***-1234"""
        digits = re.sub(r'\D', '', value)
        if len(digits) >= 4:
            return f"***-***-{digits[-4:]}"
        return "***-***-****"

    def _mask_dob(self, value: str) -> str:
        """Mask day and month: **/**/1985"""
        # Try to extract the year
        parts = re.split(r'[/\-]', value)
        if len(parts) >= 3:
            year = parts[-1]
            return f"**/**/{year}"
        return "**/**/****"

    def _mask_api_key(self, value: str) -> str:
        """Full mask"""
        return "[REDACTED_API_KEY]"

    def _mask_person_name(self, value: str) -> str:
        """First name + last initial: John D."""
        parts = value.strip().split()
        if len(parts) >= 2:
            return f"{parts[0]} {parts[-1][0]}."
        if len(parts) == 1:
            return f"{parts[0][0]}."
        return "[REDACTED_NAME]"

    def _mask_ip(self, value: str) -> str:
        """Mask last two octets: 192.168.*.*"""
        parts = value.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.*.*"
        return "[REDACTED_IP]"

    def _mask_password(self, value: str) -> str:
        """Full mask"""
        return "[REDACTED_PASSWORD]"

    def _mask_passport(self, value: str) -> str:
        """Show first 2 chars"""
        if len(value) >= 2:
            return f"{value[:2]}{'*' * (len(value) - 2)}"
        return "***"

    def _mask_bank_account(self, value: str) -> str:
        """Show last 4 chars"""
        if len(value) >= 4:
            return f"{'*' * (len(value) - 4)}{value[-4:]}"
        return "****"

    def _mask_card_expiry(self, value: str) -> str:
        """Full mask"""
        return "**/**"

    def _mask_generic(self, value: str) -> str:
        """Generic masking for unrecognized types"""
        return "[REDACTED]"
