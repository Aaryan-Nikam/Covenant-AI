"""
Ironpass — Calibration dataset.

Structured test cases for validating the 3-layer detection pipeline:
    Layer 1: Regex    — fast, deterministic pattern matching
    Layer 2: Luhn     — credit card checksum validation
    Layer 3: NER      — spaCy ML model (people, locations, orgs)

Each case has:
    input           — the raw text to scan
    expected_types  — data_types that MUST be detected
    must_not_flag   — strings that must NOT appear in detections (false positive traps)
    category        — what this group tests
    difficulty      — easy / medium / hard
    notes           — why this case exists

Cases are ordered by difficulty within each category.
"""

from dataclasses import dataclass, field


@dataclass
class CalibrationCase:
    id: str
    category: str
    difficulty: str           # "easy" | "medium" | "hard"
    description: str
    input: str
    expected_types: list[str]       # data_type values that must appear in detections
    must_not_flag: list[str] = field(default_factory=list)  # values that must NOT be detected
    notes: str = ""


# ---------------------------------------------------------------------------
# Credit Card Numbers (PCI-DSS)
# ---------------------------------------------------------------------------

CREDIT_CARD_CASES: list[CalibrationCase] = [
    CalibrationCase(
        id="cc_001",
        category="credit_card",
        difficulty="easy",
        description="Naked Visa number",
        input="Please charge 4111111111111111 for the order.",
        expected_types=["credit_card"],
        notes="Baseline — unformatted, passes Luhn",
    ),
    CalibrationCase(
        id="cc_002",
        category="credit_card",
        difficulty="easy",
        description="Formatted with dashes",
        input="Card number: 4111-1111-1111-1111",
        expected_types=["credit_card"],
        notes="Dashes stripped before Luhn check",
    ),
    CalibrationCase(
        id="cc_003",
        category="credit_card",
        difficulty="easy",
        description="Formatted with spaces",
        input="Visa 4111 1111 1111 1111 exp 12/26 CVV 123",
        expected_types=["credit_card"],
        notes="Space-separated, common in copy-paste from bank statements",
    ),
    CalibrationCase(
        id="cc_004",
        category="credit_card",
        difficulty="medium",
        description="Embedded in prose sentence",
        input="My card ending in 4111111111111111 was declined, can you retry?",
        expected_types=["credit_card"],
        notes="Card number inside a sentence, not labelled",
    ),
    CalibrationCase(
        id="cc_005",
        category="credit_card",
        difficulty="medium",
        description="Mastercard number",
        input="Process refund to Mastercard 5500005555555559",
        expected_types=["credit_card"],
        notes="Different card network — ensure Luhn works for non-Visa",
    ),
    CalibrationCase(
        id="cc_006",
        category="credit_card",
        difficulty="hard",
        description="False positive trap — fails Luhn checksum",
        input="The order number is 4111111111111112 and was shipped yesterday.",
        expected_types=[],
        must_not_flag=["4111111111111112"],
        notes="One digit off from valid card. Luhn must reject this. "
              "If we flag it, that's a false positive.",
    ),
    CalibrationCase(
        id="cc_007",
        category="credit_card",
        difficulty="hard",
        description="False positive trap — sequential-looking number",
        input="Invoice #4111232154451222 for services rendered.",
        expected_types=[],
        must_not_flag=["4111232154451222"],
        notes="Looks like a card number but fails Luhn. Common in invoice IDs.",
    ),
    CalibrationCase(
        id="cc_008",
        category="credit_card",
        difficulty="hard",
        description="Multiple card numbers in one message",
        input="Primary card 4111111111111111 declined, try backup 5500005555555559.",
        expected_types=["credit_card"],
        notes="Both should be detected. Ensure detection runs on all matches.",
    ),
]

# ---------------------------------------------------------------------------
# Social Security Numbers (HIPAA / SOC2)
# ---------------------------------------------------------------------------

SSN_CASES: list[CalibrationCase] = [
    CalibrationCase(
        id="ssn_001",
        category="ssn",
        difficulty="easy",
        description="Standard SSN with dashes",
        input="SSN: 123-45-6789",
        expected_types=["ssn"],
        notes="Baseline — explicitly labelled",
    ),
    CalibrationCase(
        id="ssn_002",
        category="ssn",
        difficulty="medium",
        description="SSN without dashes in prose",
        input="My social security number is 123456789, please update your records.",
        expected_types=["ssn"],
        notes="No dashes, 'social security number' label present",
    ),
    CalibrationCase(
        id="ssn_003",
        category="ssn",
        difficulty="hard",
        description="False positive trap — likely employee/order ID",
        input="Employee id 123456789 needs access to the benefits portal.",
        expected_types=[],
        must_not_flag=["123456789"],
        notes="9-digit number but context is 'employee id'. "
              "NER context should help avoid this. Known hard case.",
    ),
    CalibrationCase(
        id="ssn_004",
        category="ssn",
        difficulty="hard",
        description="SSN alongside name in medical context",
        input="Patient Jane Doe, SSN 987-65-4321, admitted for outpatient surgery.",
        expected_types=["ssn"],
        notes="HIPAA scenario — SSN in clinical context alongside PII",
    ),
]

# ---------------------------------------------------------------------------
# Personal Names (HIPAA / GDPR)
# ---------------------------------------------------------------------------

NAME_CASES: list[CalibrationCase] = [
    CalibrationCase(
        id="name_001",
        category="person_name",
        difficulty="easy",
        description="Full name in medical context",
        input="Patient John Smith was admitted on March 15th.",
        expected_types=["person_name"],
        notes="Baseline — NER should catch this as PERSON entity",
    ),
    CalibrationCase(
        id="name_002",
        category="person_name",
        difficulty="medium",
        description="Name without medical label",
        input="Please book a flight for Sarah Johnson departing from JFK.",
        expected_types=["person_name"],
        notes="No explicit patient/customer label — pure NER trigger",
    ),
    CalibrationCase(
        id="name_003",
        category="person_name",
        difficulty="hard",
        description="False positive trap — common noun / company name",
        input="Please route this to the Phoenix team for review.",
        expected_types=[],
        must_not_flag=["Phoenix"],
        notes="Phoenix is an org name / city, not a person. Challenging for NER.",
    ),
    CalibrationCase(
        id="name_004",
        category="person_name",
        difficulty="hard",
        description="Name embedded in technical context",
        input="The API was developed by Michael Chen and the key is sk-abc123def456.",
        expected_types=["person_name"],
        notes="NER should catch Michael Chen even in a technical sentence",
    ),
]

# ---------------------------------------------------------------------------
# Email Addresses (GDPR / SOC2)
# ---------------------------------------------------------------------------

EMAIL_CASES: list[CalibrationCase] = [
    CalibrationCase(
        id="email_001",
        category="email",
        difficulty="easy",
        description="Plain email address",
        input="Contact john.smith@acmecorp.com for pricing.",
        expected_types=["email"],
        notes="Baseline regex case",
    ),
    CalibrationCase(
        id="email_002",
        category="email",
        difficulty="medium",
        description="Email in a support ticket context",
        input="Customer reported issue from email address jane.doe+support@gmail.com",
        expected_types=["email"],
        notes="Plus-addressing in email — regex must handle the '+' character",
    ),
    CalibrationCase(
        id="email_003",
        category="email",
        difficulty="hard",
        description="False positive trap — email-looking placeholder",
        input="Send to <user>@<domain>.com as per the template.",
        expected_types=[],
        must_not_flag=["<user>@<domain>.com"],
        notes="Template placeholder, not a real email address",
    ),
]

# ---------------------------------------------------------------------------
# Multi-PII (realistic agentic requests)
# Agents orchestrating real workflows send all PII in one message.
# These are the inputs that matter most in production.
# ---------------------------------------------------------------------------

MULTI_PII_CASES: list[CalibrationCase] = [
    CalibrationCase(
        id="multi_001",
        category="multi_pii",
        difficulty="hard",
        description="Full checkout payload",
        input=(
            "Process payment for John Smith, "
            "card 4111-1111-1111-1111 exp 12/26 CVV 123, "
            "billing address 123 Main St, Boston MA 02101. "
            "Contact: john.smith@example.com"
        ),
        expected_types=["credit_card", "email"],
        notes="Realistic e-commerce agent payload. Card + email mandatory. "
              "Name and address detection is a bonus if NER catches them.",
    ),
    CalibrationCase(
        id="multi_002",
        category="multi_pii",
        difficulty="hard",
        description="Medical intake form",
        input=(
            "Patient: Sarah Johnson, DOB: 01/15/1980, SSN: 987-65-4321. "
            "Insurance: Blue Cross, policy number BC-123456. "
            "Referring physician: Dr. Marcus Webb, NPI: 1234567893."
        ),
        expected_types=["ssn"],
        notes="HIPAA scenario. SSN mandatory. Name and NPI are bonus.",
    ),
    CalibrationCase(
        id="multi_003",
        category="multi_pii",
        difficulty="hard",
        description="HR data export",
        input=(
            "Employee ID: 98765, Name: David Kim, SSN: 456-78-9012, "
            "Email: d.kim@company.com, Salary: $125,000, "
            "Emergency contact: Lisa Kim at 555-867-5309."
        ),
        expected_types=["ssn", "email"],
        notes="HR export — multiple PII types. SSN and email are critical detections.",
    ),
]

# ---------------------------------------------------------------------------
# Edge Cases and Noise
# ---------------------------------------------------------------------------

EDGE_CASES: list[CalibrationCase] = [
    CalibrationCase(
        id="edge_001",
        category="edge_case",
        difficulty="easy",
        description="Empty string",
        input="",
        expected_types=[],
        notes="Empty input must not crash or return detections",
    ),
    CalibrationCase(
        id="edge_002",
        category="edge_case",
        difficulty="easy",
        description="Clean input — no PII",
        input="What is the capital of France?",
        expected_types=[],
        notes="Baseline clean input — must produce zero detections",
    ),
    CalibrationCase(
        id="edge_003",
        category="edge_case",
        difficulty="medium",
        description="Only whitespace and punctuation",
        input="   ---   ...   !!!   ",
        expected_types=[],
        notes="Noise input — must handle gracefully",
    ),
    CalibrationCase(
        id="edge_004",
        category="edge_case",
        difficulty="medium",
        description="False positive trap — version number looks like card",
        input="Upgrade failed on version 4.1.1.1111 of the firmware.",
        expected_types=[],
        must_not_flag=["4.1.1.1111"],
        notes="Version string with dots. Regex must not strip dots and match as card.",
    ),
    CalibrationCase(
        id="edge_005",
        category="edge_case",
        difficulty="hard",
        description="Mixed language input",
        input="Patient name: 山田太郎, card number: 4111111111111111",
        expected_types=["credit_card"],
        notes="Non-ASCII in same input. Card must still be detected.",
    ),
]

# ---------------------------------------------------------------------------
# Full dataset
# ---------------------------------------------------------------------------

ALL_CASES: list[CalibrationCase] = (
    CREDIT_CARD_CASES
    + SSN_CASES
    + NAME_CASES
    + EMAIL_CASES
    + MULTI_PII_CASES
    + EDGE_CASES
)
