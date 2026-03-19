"""
Ironpass — Pseudonymizer: deterministic fake data replacement.

Replaces sensitive values with realistic but fake data.
MUST be deterministic: same input always returns same output.
Achieved via: HMAC(value, secret_key) → seed → fake data.

Use cases:
  - Patient names in HIPAA context → consistent fake name
  - Company names in GDPR context → consistent fake company

Never use for financial data — use tokenize for that.
"""

import hashlib
import hmac
import logging

from engine.config import get_settings

logger = logging.getLogger("ironpass.actions.pseudonymizer")

# Deterministic name pools — indexed by seed
FIRST_NAMES = [
    "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
    "Linda", "David", "Elizabeth", "William", "Barbara", "Richard", "Susan",
    "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Daniel",
    "Lisa", "Matthew", "Nancy", "Anthony", "Betty", "Mark", "Margaret",
    "Donald", "Sandra", "Steven", "Ashley", "Andrew", "Dorothy", "Paul",
    "Kimberly", "Joshua", "Emily", "Kenneth", "Donna", "Kevin", "Michelle",
    "Brian", "Carol", "George", "Amanda", "Timothy", "Melissa", "Ronald",
    "Deborah",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts",
]

COMPANY_NAMES = [
    "Apex Industries", "Vertex Solutions", "Pinnacle Corp", "Meridian Tech",
    "Summit Group", "Atlas Partners", "Zenith Holdings", "Horizon Labs",
    "Vanguard Systems", "Nexus Global", "Prism Analytics", "Forge Digital",
    "Catalyst Networks", "Beacon Services", "Keystone Ventures",
    "Lighthouse Data", "Compass Financial", "Orbit Consulting",
    "Cardinal Health Corp", "Sterling Associates",
]

LOCATION_NAMES = [
    "Springfield", "Riverside", "Fairview", "Madison", "Georgetown",
    "Franklin", "Clinton", "Arlington", "Greenville", "Bristol",
    "Manchester", "Burlington", "Chester", "Salem", "Dover",
    "Newport", "Oxford", "Cambridge", "Windsor", "Kingston",
]


class Pseudonymizer:
    """
    Replaces with realistic but fake data.
    MUST be deterministic: same input + same key = same output.
    Without the secret key, pseudonym cannot be reversed.
    """

    def __init__(self):
        settings = get_settings()
        self._secret_key = settings.pseudonym_secret_key.encode("utf-8")

    def pseudonymize(self, value: str, data_type: str) -> str:
        """
        Generate a deterministic pseudonym for the given value.

        1. HMAC-SHA256(original_value, PSEUDONYM_SECRET_KEY) → deterministic seed
        2. Use seed to select from name/company lists
        3. Same original value always returns same pseudonym
        """
        seed = self._generate_seed(value)

        pseudonymizers = {
            "person_name": self._pseudo_person_name,
            "email": self._pseudo_email,
            "phone_number": self._pseudo_phone,
        }

        pseudo_fn = pseudonymizers.get(data_type, self._pseudo_generic)
        result = pseudo_fn(value, seed)

        logger.debug(f"Pseudonymized {data_type}")
        return result

    def _generate_seed(self, value: str) -> int:
        """
        HMAC-SHA256(value, secret_key) → deterministic integer seed.
        Same value + same key = same seed every time.
        """
        h = hmac.new(
            self._secret_key,
            value.encode("utf-8"),
            hashlib.sha256,
        )
        # Use first 8 bytes of HMAC digest as integer seed
        return int.from_bytes(h.digest()[:8], byteorder="big")

    def _pseudo_person_name(self, value: str, seed: int) -> str:
        """Generate a deterministic fake person name."""
        first = FIRST_NAMES[seed % len(FIRST_NAMES)]
        last = LAST_NAMES[(seed >> 8) % len(LAST_NAMES)]
        return f"{first} {last}"

    def _pseudo_email(self, value: str, seed: int) -> str:
        """Generate a deterministic fake email."""
        first = FIRST_NAMES[seed % len(FIRST_NAMES)].lower()
        last = LAST_NAMES[(seed >> 8) % len(LAST_NAMES)].lower()
        domain_idx = (seed >> 16) % 3
        domains = ["example.com", "example.org", "example.net"]
        return f"{first}.{last}@{domains[domain_idx]}"

    def _pseudo_phone(self, value: str, seed: int) -> str:
        """Generate a deterministic fake phone number."""
        # Use seed to generate fake digits
        area = 200 + (seed % 800)
        mid = 200 + ((seed >> 10) % 800)
        last = seed % 10000
        return f"+1-{area:03d}-{mid:03d}-{last:04d}"

    def _pseudo_generic(self, value: str, seed: int) -> str:
        """Generic pseudonym using company names for unrecognized types."""
        return COMPANY_NAMES[seed % len(COMPANY_NAMES)]
